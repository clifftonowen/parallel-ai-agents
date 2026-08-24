"""Tests for authorisation.

The two questions that matter: who may spend API credits, and who may read the
access-request queue. Both are enforced server-side; the UI only decides what
to offer.
"""

import pytest
from fastapi import HTTPException

import security


class TestAdminEmails:
    def test_unset_means_nobody(self, monkeypatch):
        """An unset variable must never mean "everybody"."""
        monkeypatch.delenv("ADMIN_EMAILS", raising=False)
        assert security.admin_emails() == set()
        assert security.is_admin({"email": "anyone@example.com"}) is False

    def test_empty_string_means_nobody(self, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAILS", "")
        assert security.admin_emails() == set()

    def test_parses_a_comma_separated_list(self, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAILS", "a@x.com, b@y.com ,, c@z.com")
        assert security.admin_emails() == {"a@x.com", "b@y.com", "c@z.com"}

    def test_matching_is_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAILS", "Admin@Example.COM")
        assert security.is_admin({"email": "admin@example.com"}) is True

    def test_anonymous_is_never_admin(self, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
        assert security.is_admin(None) is False


class TestRequireAdmin:
    def test_non_admin_gets_404_not_403(self, monkeypatch):
        """403 confirms the route exists and that somebody is an admin.

        404 gives an attacker nothing: to them the endpoint is simply absent.
        """
        monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
        monkeypatch.setattr(security, "current_user", lambda _a: {"email": "other@example.com"})
        with pytest.raises(HTTPException) as exc:
            security.require_admin("Bearer x")
        assert exc.value.status_code == 404

    def test_anonymous_gets_404(self, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
        monkeypatch.setattr(security, "current_user", lambda _a: None)
        with pytest.raises(HTTPException) as exc:
            security.require_admin(None)
        assert exc.value.status_code == 404

    def test_admin_passes(self, monkeypatch):
        monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
        monkeypatch.setattr(security, "current_user", lambda _a: {"email": "admin@example.com"})
        assert security.require_admin("Bearer x")["email"] == "admin@example.com"


class TestRequireRunner:
    def test_anonymous_gets_401(self, monkeypatch):
        monkeypatch.setattr(security, "current_user", lambda _a: None)
        with pytest.raises(HTTPException) as exc:
            security.require_runner(None)
        assert exc.value.status_code == 401

    def test_signed_in_without_permission_gets_403(self, monkeypatch):
        """Signing up must not grant the ability to spend money."""
        monkeypatch.setattr(
            security, "current_user", lambda _a: {"email": "x@y.com", "can_run": False}
        )
        with pytest.raises(HTTPException) as exc:
            security.require_runner("Bearer x")
        assert exc.value.status_code == 403
        # The message has to tell them what to do next.
        assert "request access" in exc.value.detail.lower()

    def test_a_missing_can_run_key_denies_rather_than_allows(self, monkeypatch):
        """Fail closed. A user dict from an older code path has no can_run."""
        monkeypatch.setattr(security, "current_user", lambda _a: {"email": "x@y.com"})
        with pytest.raises(HTTPException) as exc:
            security.require_runner("Bearer x")
        assert exc.value.status_code == 403

    def test_granted_user_passes(self, monkeypatch):
        monkeypatch.setattr(
            security, "current_user", lambda _a: {"email": "x@y.com", "can_run": True}
        )
        assert security.require_runner("Bearer x")["email"] == "x@y.com"


class TestTokenExtraction:
    @pytest.mark.parametrize(
        "header, expected",
        [
            ("Bearer abc123", "abc123"),
            ("bearer abc123", "abc123"),
            ("BEARER abc123", "abc123"),
            ("Bearer   abc123  ", "abc123"),
            ("Basic abc123", None),
            ("abc123", None),
            ("", None),
            (None, None),
        ],
    )
    def test_pulls_the_token_out(self, header, expected):
        assert security.token_from_header(header) == expected
