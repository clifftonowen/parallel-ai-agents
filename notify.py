"""Best-effort push notifications for events worth interrupting someone over.

Right now that is exactly one event: somebody asked for access to run the
pipeline.

Three properties, all deliberate:

**The database is the source of truth, this is not.** Callers write their row
first and notify afterwards. A missing webhook, a network blip or a 500 from
the chat provider loses a notification, never a request.

**The payload carries no attacker-controlled text.** It names who asked and
says to open the admin page. Chat clients render markdown, and `_EMAIL_RE` in
auth_db is loose enough to allow it (`a*b*c@x.co` validates), so the request's
name, organisation and message stay in the admin view, which renders them as
plain text.

**No mail library.** Composing SMTP headers from user input is how open relays
and header injection happen. A single JSON POST reaches Discord, Slack and
ntfy directly, and ntfy will forward to email on request, so mail arrives
without this project holding SMTP credentials or a mail API key.

Two shapes, picked by whether ALERT_NTFY_TOPIC is set:

* Unset, the body is ``{"content": ..., "text": ...}``, which Discord reads as
  ``content`` and Slack reads as ``text``. One variable works with either.
* Set, the body is ntfy's JSON publish format, which takes an ``email`` field
  and delivers the message there.

Set ALERT_WEBHOOK_URL (or ALERT_NTFY_TOPIC) to enable. Unset, notifications are
silently skipped, which is the normal state on a laptop.

**An ntfy topic is a password, not a name.** Anyone who knows a topic can read
everything published to it, and these messages name the person waiting. Use a
long random string, never something guessable like "urop-requests".
"""

from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request

_TIMEOUT_S = 5


#: Where ntfy lives when only a topic is configured. The public instance is
#: fine for this: the messages are small and the topic is the only secret.
_NTFY_DEFAULT = "https://ntfy.sh"


def _ntfy_topic() -> str:
    return os.environ.get("ALERT_NTFY_TOPIC", "").strip()


def _alert_email() -> str:
    return os.environ.get("ALERT_EMAIL", "").strip()


def _webhook_url() -> str:
    """The endpoint to POST to, or "" when notifications are off.

    A topic on its own is enough to turn ntfy on, since the server has an
    obvious default and making people set both would only be a way to get one
    of them wrong.
    """
    explicit = os.environ.get("ALERT_WEBHOOK_URL", "").strip()
    if explicit:
        return explicit
    return _NTFY_DEFAULT if _ntfy_topic() else ""


def _payload(text: str, title: str = "") -> bytes:
    """The request body, in whichever shape the configured service reads.

    ntfy when a topic is set, because only ntfy can turn this into an email.
    Otherwise the Discord/Slack shape: Discord reads "content", Slack reads
    "text", and sending both means one variable works with either without the
    caller knowing which it is.
    """
    topic = _ntfy_topic()
    if not topic:
        return json.dumps({"content": text, "text": text}).encode("utf-8")

    body: dict[str, object] = {"topic": topic, "message": text}
    if title:
        body["title"] = title
    email = _alert_email()
    if email:
        # ntfy sends the message on to this address. Free-tier email delivery
        # is rate limited to a handful a day, which is far above the rate
        # anyone asks for access at.
        body["email"] = email
    return json.dumps(body).encode("utf-8")


def _post(url: str, body: bytes) -> None:
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "urop-notify"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S):
            pass
    except (urllib.error.URLError, OSError, ValueError) as exc:
        # Same "[api]" prefix the run log uses, which infer_phase filters out.
        print(f"[api] Warning: alert webhook failed: {exc}")


def send(text: str, title: str = "") -> bool:
    """Fire a notification in the background. Returns whether one was attempted.

    Runs on a daemon thread so a slow or hanging webhook cannot add five
    seconds to the request that triggered it.
    """
    url = _webhook_url()
    if not url:
        return False
    body = _payload(text, title)
    threading.Thread(target=_post, args=(url, body), daemon=True).start()
    return True


def access_requested(email: str, pending_total: int) -> bool:
    """Somebody asked for permission to run the pipeline.

    Only the account's email appears, and only because it is needed to know who
    is waiting. Everything the requester typed stays in the admin view.
    """
    return send(
        f"New access request from {email}. "
        f"{pending_total} pending. Open the app's Requests page to review.",
        title="Access request",
    )
