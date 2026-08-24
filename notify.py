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
ntfy directly, and reaches email through any relay you already use, without
this project holding a mail API key.

Set ALERT_WEBHOOK_URL to enable. Unset, notifications are silently skipped,
which is the normal state on a laptop.
"""

from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request

_TIMEOUT_S = 5


def _webhook_url() -> str:
    return os.environ.get("ALERT_WEBHOOK_URL", "").strip()


def _payload(text: str) -> bytes:
    """A body Discord, Slack and ntfy all accept.

    Discord reads "content", Slack reads "text"; sending both means one env var
    works with either without the caller knowing which it is.
    """
    return json.dumps({"content": text, "text": text}).encode("utf-8")


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


def send(text: str) -> bool:
    """Fire a notification in the background. Returns whether one was attempted.

    Runs on a daemon thread so a slow or hanging webhook cannot add five
    seconds to the request that triggered it.
    """
    url = _webhook_url()
    if not url:
        return False
    threading.Thread(target=_post, args=(url, _payload(text)), daemon=True).start()
    return True


def access_requested(email: str, pending_total: int) -> bool:
    """Somebody asked for permission to run the pipeline.

    Only the account's email appears, and only because it is needed to know who
    is waiting. Everything the requester typed stays in the admin view.
    """
    return send(
        f"New access request from {email}. "
        f"{pending_total} pending. Open the app's Requests page to review."
    )
