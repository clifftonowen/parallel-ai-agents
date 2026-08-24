"""Tests for run grants.

A grant is what travels in a URL now, in place of the session token. So the
properties that matter are the ones that make it worth less to whoever finds it
in a log: it reads exactly one run, it expires, and it cannot be forged without
the key.
"""

import time

import pytest

import signing


@pytest.fixture(autouse=True)
def key(monkeypatch):
    """A fixed key, so no test touches the real one or writes a key file.

    _key_cache is module-level and would otherwise carry the first test's key
    into every later test, which is exactly the kind of thing that makes a
    forgery test pass for the wrong reason.
    """
    monkeypatch.setenv("SIGNING_SECRET", "test-key-not-a-real-one")
    monkeypatch.setattr(signing, "_key_cache", None)
    yield
    monkeypatch.setattr(signing, "_key_cache", None)


class TestScope:
    def test_a_grant_opens_its_own_run(self):
        grant, _ = signing.issue("run-a")
        assert signing.verify(grant, "run-a") is True

    def test_a_grant_does_not_open_another_run(self):
        """The whole point of signing the run id in. Without this a grant for
        one shared run would read every run on the server."""
        grant, _ = signing.issue("run-a")
        assert signing.verify(grant, "run-b") is False

    def test_the_run_id_is_matched_exactly(self):
        grant, _ = signing.issue("run-a")
        assert signing.verify(grant, "run-a ") is False
        assert signing.verify(grant, "run-A") is False


class TestExpiry:
    def test_a_fresh_grant_is_valid(self):
        grant, ttl = signing.issue("r", ttl=60)
        assert ttl == 60
        assert signing.verify(grant, "r") is True

    def test_an_expired_grant_is_not(self):
        grant, _ = signing.issue("r", ttl=-1)
        assert signing.verify(grant, "r") is False

    def test_it_expires_by_the_clock_not_by_use(self, monkeypatch):
        """No server-side state says a grant was spent, so the clock is the
        only thing that ends it."""
        grant, _ = signing.issue("r", ttl=60)
        assert signing.verify(grant, "r") is True
        later = time.time() + 61
        monkeypatch.setattr(signing.time, "time", lambda: later)
        assert signing.verify(grant, "r") is False

    def test_the_expiry_cannot_be_edited_forward(self):
        """The expiry is readable in the string, so it has to be signed."""
        grant, _ = signing.issue("r", ttl=60)
        _, _, sig = grant.partition(".")
        forged = f"{int(time.time()) + 99999}.{sig}"
        assert signing.verify(forged, "r") is False

    def test_the_default_ttl_outlives_a_run(self, monkeypatch):
        """A <video> re-requests its URL on every seek and EventSource
        reconnects to it by itself, so a grant shorter than a run breaks
        playback mid-file and streaming mid-run."""
        monkeypatch.delenv("GRANT_TTL_SECONDS", raising=False)
        assert signing.grant_ttl_seconds() >= 600

    def test_a_configured_ttl_is_used(self, monkeypatch):
        monkeypatch.setenv("GRANT_TTL_SECONDS", "300")
        assert signing.grant_ttl_seconds() == 300

    def test_a_silly_ttl_still_leaves_a_usable_floor(self, monkeypatch):
        monkeypatch.setenv("GRANT_TTL_SECONDS", "1")
        assert signing.grant_ttl_seconds() == 60

    def test_nonsense_falls_back_to_the_default(self, monkeypatch):
        monkeypatch.setenv("GRANT_TTL_SECONDS", "soon")
        assert signing.grant_ttl_seconds() == 2700


class TestForgery:
    @pytest.mark.parametrize(
        "junk",
        ["", "x", "abc.def", "9999999999.", ".sig", "9999999999.AAAA", "not-a-grant"],
    )
    def test_malformed_input_is_rejected_rather_than_raising(self, junk):
        """This runs on every media request and the input is entirely
        attacker-controlled, so it must never throw."""
        assert signing.verify(junk, "r") is False

    def test_none_is_rejected(self):
        assert signing.verify(None, "r") is False

    def test_a_different_key_does_not_verify(self, monkeypatch):
        grant, _ = signing.issue("r")
        monkeypatch.setenv("SIGNING_SECRET", "a-different-key")
        monkeypatch.setattr(signing, "_key_cache", None)
        assert signing.verify(grant, "r") is False

    def test_a_grant_is_not_a_session_token(self, tmp_path, monkeypatch):
        """It carries no user, so nothing can trade it back for an account.

        Against a throwaway database, not the real one. Without that this
        passes locally only because study_bench.db happens to exist, and CI --
        where it does not -- errors on a missing table instead of asserting.
        """
        import auth_db

        monkeypatch.setattr(auth_db, "_DB_PATH", str(tmp_path / "t.db"))
        monkeypatch.setattr(auth_db, "_conn", None)
        auth_db.init_db()
        try:
            grant, _ = signing.issue("r")
            assert auth_db.user_for_token(grant) is None
        finally:
            if auth_db._conn is not None:
                auth_db._conn.close()
            auth_db._conn = None


class TestKeyDurability:
    def test_a_generated_key_is_written_and_reused(self, tmp_path, monkeypatch):
        """uvicorn --reload restarts the child on every save. A key that
        changed with it would invalidate every outstanding grant each time
        anyone touched the code, and video would break for no visible reason.
        """
        monkeypatch.delenv("SIGNING_SECRET", raising=False)
        monkeypatch.setattr(signing, "KEY_PATH", str(tmp_path / ".signing_key"))
        monkeypatch.setattr(signing, "_key_cache", None)
        grant, _ = signing.issue("r")

        # Same as a restart: the process forgets, the file does not.
        monkeypatch.setattr(signing, "_key_cache", None)
        assert signing.verify(grant, "r") is True

    @pytest.mark.parametrize("edge", [b" ", b"\n", b"\r", b"\t", b"\x0b", b"\x0c"])
    def test_a_key_with_whitespace_at_the_edges_survives(self, edge, tmp_path, monkeypatch):
        """Regression. The key was stored as raw bytes and read back with
        .strip(), which ate a leading or trailing whitespace byte. 32 random
        bytes start or end with one about 5% of the time, so roughly one
        restart in twenty came back with a key one byte short of the one it
        had signed with, and every outstanding grant stopped verifying for no
        visible reason.
        """
        monkeypatch.delenv("SIGNING_SECRET", raising=False)
        monkeypatch.setattr(signing, "KEY_PATH", str(tmp_path / ".signing_key"))
        monkeypatch.setattr(signing, "_key_cache", None)
        monkeypatch.setattr(
            signing.secrets, "token_bytes", lambda n: edge + b"k" * (n - 2) + edge
        )

        grant, _ = signing.issue("r")
        monkeypatch.setattr(signing, "_key_cache", None)
        assert signing.verify(grant, "r") is True

    def test_an_unreadable_key_file_does_not_crash_the_server(self, tmp_path, monkeypatch):
        """Better to sign with a fresh key, which only invalidates outstanding
        grants, than to refuse every media request."""
        monkeypatch.delenv("SIGNING_SECRET", raising=False)
        path = tmp_path / ".signing_key"
        path.write_text("this is not base64 !!!", encoding="ascii")
        monkeypatch.setattr(signing, "KEY_PATH", str(path))
        monkeypatch.setattr(signing, "_key_cache", None)
        grant, _ = signing.issue("r")
        assert signing.verify(grant, "r") is True

    def test_the_env_key_wins_over_the_file(self, tmp_path, monkeypatch):
        """More than one process serving the app has to agree on the key, and
        a file on one container's disk does not do that."""
        monkeypatch.setattr(signing, "KEY_PATH", str(tmp_path / ".signing_key"))
        monkeypatch.setattr(signing, "_key_cache", None)
        signing.issue("r")
        assert not (tmp_path / ".signing_key").exists()
