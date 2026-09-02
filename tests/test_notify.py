"""Tests for the access-request alert.

The alert is best effort by design: the database row is written first and a
lost notification is never a lost request. So what matters here is the shape of
what gets sent and, more importantly, that nothing is sent when nothing is
configured. An alert naming who asked for access must not go somewhere the
owner did not choose.
"""

import json

import pytest

import notify


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in ("ALERT_WEBHOOK_URL", "ALERT_NTFY_TOPIC", "ALERT_EMAIL"):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def sent(monkeypatch):
    """Capture what would have been posted, without posting it.

    Patches _post rather than urlopen so the daemon thread never starts: a
    real thread would make the assertions racy.
    """
    calls = []
    monkeypatch.setattr(
        notify.threading,
        "Thread",
        lambda target, args, daemon: type(
            "T", (), {"start": lambda _self: calls.append(args)}
        )(),
    )
    return calls


def body_of(calls):
    return json.loads(calls[0][1].decode("utf-8"))


class TestOffByDefault:
    def test_nothing_configured_sends_nothing(self, sent):
        """The normal state on a laptop, and it must stay silent rather than
        picking a default destination."""
        assert notify.send("hello") is False
        assert sent == []

    def test_an_email_alone_is_not_enough(self, sent):
        """An address with nowhere to send it through is not a configuration."""
        import os

        os.environ["ALERT_EMAIL"] = "someone@example.com"
        try:
            assert notify.send("hello") is False
            assert sent == []
        finally:
            del os.environ["ALERT_EMAIL"]


class TestDiscordAndSlack:
    def test_a_plain_webhook_gets_the_shape_both_read(self, sent, monkeypatch):
        monkeypatch.setenv("ALERT_WEBHOOK_URL", "https://example.invalid/hook")
        assert notify.send("hello") is True
        url, body = sent[0]
        assert url == "https://example.invalid/hook"
        assert body_of(sent) == {"content": "hello", "text": "hello"}

    def test_no_ntfy_fields_leak_into_it(self, sent, monkeypatch):
        """A topic-less webhook must not receive a "topic" key it will reject."""
        monkeypatch.setenv("ALERT_WEBHOOK_URL", "https://example.invalid/hook")
        monkeypatch.setenv("ALERT_EMAIL", "someone@example.com")
        notify.send("hello")
        assert "topic" not in body_of(sent)
        assert "email" not in body_of(sent)


class TestNtfy:
    def test_a_topic_alone_turns_it_on(self, sent, monkeypatch):
        """Requiring both the topic and the server URL would only be a way to
        get one of them wrong."""
        monkeypatch.setenv("ALERT_NTFY_TOPIC", "a-long-random-topic")
        assert notify.send("hello") is True
        url, _ = sent[0]
        assert url == "https://ntfy.sh"

    def test_the_topic_travels_in_the_body(self, sent, monkeypatch):
        monkeypatch.setenv("ALERT_NTFY_TOPIC", "a-long-random-topic")
        notify.send("hello")
        assert body_of(sent)["topic"] == "a-long-random-topic"
        assert body_of(sent)["message"] == "hello"

    def test_the_email_field_is_what_makes_it_mail(self, sent, monkeypatch):
        monkeypatch.setenv("ALERT_NTFY_TOPIC", "a-long-random-topic")
        monkeypatch.setenv("ALERT_EMAIL", "owner@example.com")
        notify.send("hello")
        assert body_of(sent)["email"] == "owner@example.com"

    def test_no_email_field_when_none_is_configured(self, sent, monkeypatch):
        """Otherwise ntfy would be asked to mail an empty address."""
        monkeypatch.setenv("ALERT_NTFY_TOPIC", "a-long-random-topic")
        notify.send("hello")
        assert "email" not in body_of(sent)

    def test_a_self_hosted_server_overrides_the_default(self, sent, monkeypatch):
        monkeypatch.setenv("ALERT_NTFY_TOPIC", "a-long-random-topic")
        monkeypatch.setenv("ALERT_WEBHOOK_URL", "https://ntfy.example.com")
        notify.send("hello")
        assert sent[0][0] == "https://ntfy.example.com"

    def test_a_title_is_included_when_given(self, sent, monkeypatch):
        monkeypatch.setenv("ALERT_NTFY_TOPIC", "a-long-random-topic")
        notify.send("hello", title="Access request")
        assert body_of(sent)["title"] == "Access request"


class TestAccessRequested:
    def test_it_names_who_is_waiting_and_how_many(self, sent, monkeypatch):
        monkeypatch.setenv("ALERT_NTFY_TOPIC", "a-long-random-topic")
        assert notify.access_requested("asker@example.com", 3) is True
        msg = body_of(sent)["message"]
        assert "asker@example.com" in msg
        assert "3 pending" in msg

    def test_it_carries_nothing_the_requester_typed(self, sent, monkeypatch):
        """Their name, organisation and message stay in the admin view, which
        renders them as text. Chat clients render markdown, so free text in a
        notification is a formatting injection at best."""
        monkeypatch.setenv("ALERT_NTFY_TOPIC", "a-long-random-topic")
        notify.access_requested("asker@example.com", 1)
        msg = body_of(sent)["message"]
        # The message is fully determined by the address and the count.
        assert msg == (
            "New access request from asker@example.com. "
            "1 pending. Open the app's Requests page to review."
        )

    def test_it_stays_silent_when_unconfigured(self, sent):
        assert notify.access_requested("asker@example.com", 1) is False
        assert sent == []
