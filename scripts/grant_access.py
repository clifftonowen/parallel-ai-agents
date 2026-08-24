#!/usr/bin/env python3
"""Grant or revoke permission to start pipeline runs.

Deliberately a local script and not an HTTP route.

Granting is the most valuable action in this system: it lets an account spend
Anthropic and OpenAI credits on somebody's card. An endpoint for it would be a
privilege-escalation target, would need its own authorisation, its own CSRF
story, and an admin session worth stealing. A script has none of those: to use
it you already need the machine and the database.

Usage:
    python scripts/grant_access.py --list
    python scripts/grant_access.py --grant someone@example.com
    python scripts/grant_access.py --revoke someone@example.com
"""

from __future__ import annotations

import argparse
import os
import sys
import textwrap

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import auth_db  # noqa: E402


def show_queue(status: str) -> int:
    rows = auth_db.list_access_requests(status)
    if not rows:
        print(f"No {status} access requests.")
        return 0

    print(f"{len(rows)} {status} request(s):\n")
    for r in rows:
        # Printed, never rendered. The message is untrusted text from whoever
        # submitted it, so it goes to a terminal as-is and nowhere near HTML.
        print(f"  {r['email']}")
        print(f"    name     {r['name'] or '-'}")
        print(f"    org      {r['org'] or '-'}")
        print(f"    when     {r['created_at']}")
        wrapped = textwrap.fill(
            r["message"], width=72, initial_indent=" " * 13, subsequent_indent=" " * 13
        )
        print(f"    message\n{wrapped}")
        print(f"\n    grant with: python scripts/grant_access.py --grant {r['email']}\n")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--list", action="store_true", help="show pending requests")
    ap.add_argument("--status", default="pending",
                    choices=("pending", "granted", "declined"),
                    help="which queue to list (default: pending)")
    ap.add_argument("--grant", metavar="EMAIL", help="allow this account to start runs")
    ap.add_argument("--revoke", metavar="EMAIL", help="stop this account starting runs")
    args = ap.parse_args()

    if not any((args.list, args.grant, args.revoke)):
        ap.print_help()
        return 1

    auth_db.init_db()

    if args.list:
        return show_queue(args.status)

    email = args.grant or args.revoke
    allowed = args.grant is not None
    if auth_db.set_can_run(email, allowed):
        verb = "can now start runs" if allowed else "can no longer start runs"
        print(f"{email} {verb}.")
        return 0

    print(f"No account for {email}. They have to sign up first.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
