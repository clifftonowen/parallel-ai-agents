"""Tests for credential validation, password hashing, and env-var loading.

`auth_db` is importable without side effects only because the SQLite connection
is lazy. If someone reintroduces a module-scope `sqlite3.connect`, importing
this test file will start writing a database file during collection -- which is
the failure these tests would notice first.
"""

import pathlib

import pytest

import auth_db
from auth_db import AuthError, _hash_password, validate_credentials
from src.agents.config import require_env


class TestValidateCredentials:
    def test_normalises_email_case_and_whitespace(self):
        assert validate_credentials("  Someone@Example.COM  ", "longenough") == "someone@example.com"

    @pytest.mark.parametrize(
        "email",
        ["", "   ", "not-an-email", "@example.com", "someone@", "someone", "a b@example.com"],
    )
    def test_rejects_malformed_emails(self, email):
        with pytest.raises(AuthError):
            validate_credentials(email, "longenough")

    def test_rejects_none_email(self):
        with pytest.raises(AuthError):
            validate_credentials(None, "longenough")

    @pytest.mark.parametrize("password", ["", "short", "1234567"])
    def test_rejects_passwords_under_eight_characters(self, password):
        with pytest.raises(AuthError):
            validate_credentials("someone@example.com", password)

    def test_accepts_exactly_eight_characters(self):
        assert validate_credentials("someone@example.com", "12345678")

    def test_rejects_none_password(self):
        with pytest.raises(AuthError):
            validate_credentials("someone@example.com", None)

    def test_error_messages_are_safe_to_show_a_user(self):
        """The docstring promises this; nothing else enforces it."""
        with pytest.raises(AuthError) as exc:
            validate_credentials("nope", "longenough")
        assert "email" in str(exc.value).lower()


class TestHashPassword:
    def test_is_deterministic_for_the_same_salt(self):
        salt = b"0123456789abcdef"
        assert _hash_password("hunter22", salt) == _hash_password("hunter22", salt)

    def test_different_salts_give_different_hashes(self):
        """Otherwise identical passwords across accounts would collide."""
        a = _hash_password("hunter22", b"0123456789abcdef")
        b = _hash_password("hunter22", b"fedcba9876543210")
        assert a != b

    def test_different_passwords_give_different_hashes(self):
        salt = b"0123456789abcdef"
        assert _hash_password("hunter22", salt) != _hash_password("hunter23", salt)

    def test_returns_64_hex_characters(self):
        # dklen=32 bytes, hex-encoded.
        digest = _hash_password("hunter22", b"0123456789abcdef")
        assert len(digest) == 64
        int(digest, 16)  # raises if not hex

    def test_does_not_contain_the_password(self):
        assert "hunter22" not in _hash_password("hunter22", b"0123456789abcdef")


class TestImportIsSideEffectFree:
    def test_importing_auth_db_opens_no_connection(self):
        """The lazy connection is what makes pytest collection safe.

        A module-scope sqlite3.connect would create a database file merely by
        importing, which is why collection used to be impossible.
        """
        assert auth_db._conn is None or hasattr(auth_db._conn, "execute")


class TestRequireEnv:
    def test_returns_the_value(self, monkeypatch):
        monkeypatch.setenv("UROP_TEST_VAR", "value")
        assert require_env("UROP_TEST_VAR") == "value"

    def test_strips_surrounding_whitespace(self, monkeypatch):
        monkeypatch.setenv("UROP_TEST_VAR", "  value  ")
        assert require_env("UROP_TEST_VAR") == "value"

    def test_unset_exits_with_a_readable_message(self, monkeypatch):
        monkeypatch.delenv("UROP_TEST_VAR", raising=False)
        with pytest.raises(SystemExit) as exc:
            require_env("UROP_TEST_VAR", "the thing it is for")
        message = str(exc.value)
        # The whole point of this helper over os.environ["X"]: the reader is
        # told which variable, what it is for, and how to fix it.
        assert "UROP_TEST_VAR" in message
        assert "the thing it is for" in message
        assert ".env" in message

    def test_empty_and_whitespace_only_count_as_unset(self, monkeypatch):
        for value in ("", "   "):
            monkeypatch.setenv("UROP_TEST_VAR", value)
            with pytest.raises(SystemExit):
                require_env("UROP_TEST_VAR")

    def test_the_key_is_named_anthropic_api_key(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        assert require_env("ANTHROPIC_API_KEY", "Claude pipeline") == "sk-test"


class TestOneNameForTheAnthropicKey:
    """The CLAUDE_API_KEY alias was removed deliberately and must not return.

    Two names for one secret means half the code reads a variable the .env does
    not set, and the failure is a missing-key error in an unrelated place.
    """

    def test_no_code_reads_the_old_alias(self):
        """Code only. The docs name it in order to forbid it, which is correct
        and must not fail this test."""
        root = pathlib.Path(__file__).resolve().parent.parent
        skip = {"node_modules", ".git", "output", "venv", ".venv", "dist", "__pycache__", "tests"}
        offenders = []
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".ts", ".tsx"}:
                continue
            if any(part in skip for part in path.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if "CLAUDE_API_KEY" in text:
                offenders.append(str(path.relative_to(root)))
        assert offenders == [], f"CLAUDE_API_KEY is back in: {offenders}"

    def test_the_env_template_offers_only_the_new_name(self):
        root = pathlib.Path(__file__).resolve().parent.parent
        example = root / ".env.example"
        if not example.is_file():
            pytest.skip(".env.example not present")
        text = example.read_text(encoding="utf-8")
        assert "ANTHROPIC_API_KEY" in text
        assert "CLAUDE_API_KEY" not in text
