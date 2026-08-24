"""Tests for the access-request layer.

Having an account and being allowed to spend API credits are deliberately
separate. These tests pin that separation, the input sanitising, and the
one-pending-request-per-account rule -- all of which are security properties
rather than conveniences.
"""

import sqlite3

import pytest

import auth_db


@pytest.fixture
def db(tmp_path, monkeypatch):
    """A throwaway database, so tests never touch the real one.

    Deliberately NOT importlib.reload(auth_db): reloading rebinds AuthError to
    a new class object, so `pytest.raises(AuthError)` in any module that
    imported it earlier silently stops matching. Point the module at a fresh
    file and drop the cached connection instead.
    """
    monkeypatch.setattr(auth_db, "_DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(auth_db, "_conn", None)
    auth_db.init_db()
    yield auth_db
    if auth_db._conn is not None:
        auth_db._conn.close()


@pytest.fixture
def user(db):
    return db.create_user("someone@example.com", "longenough")


class TestSigningUpGrantsNothing:
    """The whole point: an account is free, spending money is not."""

    def test_new_accounts_cannot_run(self, db, user):
        token = db.create_session(user["id"])
        assert db.user_for_token(token)["can_run"] is False

    def test_granting_is_what_flips_it(self, db, user):
        assert db.set_can_run("someone@example.com", True) is True
        token = db.create_session(user["id"])
        assert db.user_for_token(token)["can_run"] is True

    def test_revoking_takes_it_away_again(self, db, user):
        db.set_can_run("someone@example.com", True)
        db.set_can_run("someone@example.com", False)
        token = db.create_session(user["id"])
        assert db.user_for_token(token)["can_run"] is False

    def test_granting_an_unknown_account_reports_failure(self, db):
        assert db.set_can_run("nobody@example.com", True) is False

    def test_grant_is_case_and_whitespace_insensitive(self, db, user):
        assert db.set_can_run("  SOMEONE@Example.COM  ", True) is True


class TestOnePendingRequestPerAccount:
    def test_first_request_is_recorded(self, db, user):
        assert db.create_access_request(user["id"], "Jane", "Acme", "please") is True
        assert db.count_pending_access_requests() == 1

    def test_second_request_is_refused_rather_than_raising(self, db, user):
        db.create_access_request(user["id"], "Jane", "Acme", "please")
        assert db.create_access_request(user["id"], "Jane", "Acme", "again") is False
        assert db.count_pending_access_requests() == 1

    def test_the_rule_is_enforced_by_the_database(self, db, user):
        """A read-then-write check would race under concurrent submits."""
        db.create_access_request(user["id"], "Jane", "Acme", "please")
        with pytest.raises(sqlite3.IntegrityError):
            with auth_db._lock:
                auth_db._get_conn().execute(
                    "INSERT INTO access_requests (user_id, name, org, message, created_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (user["id"], "x", "y", "z", auth_db._now()),
                )

    def test_granting_clears_the_pending_request(self, db, user):
        db.create_access_request(user["id"], "Jane", "Acme", "please")
        db.set_can_run("someone@example.com", True)
        assert db.count_pending_access_requests() == 0
        assert db.pending_access_request(user["id"]) is None

    def test_a_revoked_user_can_ask_again(self, db, user):
        db.create_access_request(user["id"], "Jane", "Acme", "please")
        db.set_can_run("someone@example.com", True)
        db.set_can_run("someone@example.com", False)
        assert db.create_access_request(user["id"], "Jane", "Acme", "again") is True

    def test_two_users_can_each_have_one_pending(self, db, user):
        other = db.create_user("other@example.com", "longenough")
        assert db.create_access_request(user["id"], "A", "X", "m") is True
        assert db.create_access_request(other["id"], "B", "Y", "m") is True
        assert db.count_pending_access_requests() == 2


class TestInputIsCleaned:
    """This text is read by whoever holds the grant, which makes them the
    highest-value target in the system."""

    @pytest.mark.parametrize("bad", ["\x00", "\x07", "\x1b[31m"])
    def test_control_characters_are_stripped(self, db, bad):
        assert bad not in db._clean(f"Ja{bad}ne", 100)

    def test_newlines_do_not_survive_in_single_line_fields(self, db):
        assert "\n" not in db._clean("line1\r\nline2", 100)

    def test_stripping_whitespace_does_not_join_words(self, db):
        # "line1\r\nline2" must not become "line1line2".
        assert db._clean("line1\r\nline2", 100) == "line1 line2"

    def test_paragraph_breaks_survive_in_the_message(self, db):
        assert db._clean("para one\n\npara two", 1000, allow_newlines=True) == (
            "para one\n\npara two"
        )

    def test_a_wall_of_blank_lines_is_capped(self, db):
        assert db._clean("a\n\n\n\n\n\nb", 1000, allow_newlines=True) == "a\n\nb"

    @pytest.mark.parametrize(
        "field, limit",
        [("name", auth_db.NAME_MAX), ("org", auth_db.ORG_MAX), ("message", auth_db.MESSAGE_MAX)],
    )
    def test_fields_are_truncated(self, db, user, field, limit):
        payload = {"name": "n", "org": "o", "message": "m"}
        payload[field] = "A" * (limit + 500)
        db.create_access_request(user["id"], **payload)
        assert len(db.list_access_requests()[0][field]) == limit

    def test_markup_is_stored_verbatim_for_the_view_to_escape(self, db, user):
        """Sanitising happens at render, not at write.

        Mangling the text here would hide what somebody actually sent. The
        admin view renders these as React text children, which escapes them.
        """
        db.create_access_request(user["id"], "<script>alert(1)</script>", "o", "m")
        assert db.list_access_requests()[0]["name"] == "<script>alert(1)</script>"

    def test_none_values_do_not_crash(self, db, user):
        assert db.create_access_request(user["id"], None, None, "m") is True


class TestQueue:
    def test_lists_pending_with_the_requester_email(self, db, user):
        db.create_access_request(user["id"], "Jane", "Acme", "please")
        row = db.list_access_requests("pending")[0]
        assert row["email"] == "someone@example.com"
        assert row["name"] == "Jane"

    def test_granted_requests_move_off_the_pending_queue(self, db, user):
        db.create_access_request(user["id"], "Jane", "Acme", "please")
        db.set_can_run("someone@example.com", True)
        assert db.list_access_requests("pending") == []
        assert len(db.list_access_requests("granted")) == 1

    def test_empty_queue_is_empty_not_an_error(self, db):
        assert db.list_access_requests("pending") == []
        assert db.count_pending_access_requests() == 0


class TestSessionExpiry:
    """Sessions used to live forever: a token lifted from localStorage or a log
    worked indefinitely."""

    def test_a_fresh_session_resolves(self, db, user):
        assert db.user_for_token(db.create_session(user["id"])) is not None

    def test_an_aged_session_stops_resolving(self, db, user):
        from datetime import datetime, timedelta, timezone

        token = db.create_session(user["id"])
        old = (
            datetime.now(timezone.utc) - timedelta(days=db.SESSION_MAX_AGE_DAYS + 1)
        ).isoformat()
        with db._lock:
            db._get_conn().execute(
                "UPDATE sessions SET created_at = ? WHERE token = ?", (old, token)
            )
            db._get_conn().commit()
        # Enforced on lookup, not only by the periodic purge, so it stops
        # working immediately rather than whenever cleanup next runs.
        assert db.user_for_token(token) is None

    def test_purge_removes_only_the_expired_ones(self, db, user):
        from datetime import datetime, timedelta, timezone

        fresh = db.create_session(user["id"])
        stale = db.create_session(user["id"])
        old = (
            datetime.now(timezone.utc) - timedelta(days=db.SESSION_MAX_AGE_DAYS + 1)
        ).isoformat()
        with db._lock:
            db._get_conn().execute(
                "UPDATE sessions SET created_at = ? WHERE token = ?", (old, stale)
            )
            db._get_conn().commit()
        assert db.purge_expired_sessions() == 1
        assert db.user_for_token(fresh) is not None

    def test_an_unknown_token_resolves_to_nobody(self, db):
        assert db.user_for_token("not-a-real-token") is None
        assert db.user_for_token(None) is None


class TestDailyRunCount:
    """The daily quota is counted from the runs table so a restart does not
    hand somebody a fresh allowance."""

    def _cutoff(self, hours=24):
        from datetime import datetime, timedelta, timezone

        return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    def test_a_new_account_has_used_nothing(self, db, user):
        assert db.runs_started_since(user["id"], self._cutoff()) == 0

    def test_runs_inside_the_window_are_counted(self, db, user):
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        db.upsert_run("r1", user["id"], "t", "running", now)
        db.upsert_run("r2", user["id"], "t", "complete", now)
        assert db.runs_started_since(user["id"], self._cutoff()) == 2

    def test_runs_outside_the_window_are_not(self, db, user):
        from datetime import datetime, timedelta, timezone

        old = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        db.upsert_run("r1", user["id"], "t", "complete", old)
        assert db.runs_started_since(user["id"], self._cutoff()) == 0

    def test_another_account_does_not_count_against_this_one(self, db, user):
        from datetime import datetime, timezone

        other = db.create_user("other@example.com", "longenough")
        now = datetime.now(timezone.utc).isoformat()
        db.upsert_run("r1", other["id"], "t", "running", now)
        assert db.runs_started_since(user["id"], self._cutoff()) == 0
        assert db.runs_started_since(other["id"], self._cutoff()) == 1

    def test_a_failed_run_still_counts(self, db, user):
        """It spent the tokens before it failed."""
        from datetime import datetime, timezone

        db.upsert_run("r1", user["id"], "t", "error", datetime.now(timezone.utc).isoformat())
        assert db.runs_started_since(user["id"], self._cutoff()) == 1
