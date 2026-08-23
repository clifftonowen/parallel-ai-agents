"""
seed_demo.py

Make already-generated runs reachable from the UI.

A finished bundle under output/ is invisible to the app: nothing walks the
output directory, and /runs only ever returns what is in memory or in the
database. So a fresh server has nothing to show and the only way to see
anything is a 6-11 minute generation.

This registers existing bundles two ways:

  * in the semantic prompt cache, so typing a similar topic returns the
    materials instantly, signed out. This is the interesting one.
  * optionally in the runs table for an account, so /history has content.

Both go through the same functions the pipeline itself uses
(prompt_cache.remember, run_manager.collect_outputs), so the stored shape
cannot drift from what the front-end expects.

Usage:
    python scripts/seed_demo.py                      # seed the cache, then self-test
    python scripts/seed_demo.py --user you@x.com     # also populate that account's history
    python scripts/seed_demo.py --check              # test only, change nothing
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import auth_db  # noqa: E402
import prompt_cache  # noqa: E402
import run_manager  # noqa: E402
from paths import OUTPUT_ROOT  # noqa: E402

# Phrasings a demo is likely to type, each mapped to a fragment of the topic it
# should resolve to.
#
# These are seeded as cache entries in their own right, not just tested. A short
# query does not clear the 0.78 threshold against a long topic sentence on its
# own -- "Gaussian processes" against "Teach me about Gaussian Processes in
# Machine Learning" scores below it, purely from the length mismatch. Warming
# the cache with the natural phrasings is the honest fix; lowering the threshold
# would risk serving one topic's materials for another.
DEMO_PHRASINGS = {
    "Gaussian processes": "gaussian",
    "gaussian processes in machine learning": "gaussian",
    "teach me about gaussian processes": "gaussian",
    "explain gaussian processes to me": "gaussian",
    "how logistic regression works": "logistic",
    "logistic regression": "logistic",
    "explain logistic regression": "logistic",
}

# An entry is only worth showing if the learner app can render all three
# material types; flashcards_md in particular drives the package page.
_REQUIRED = ("notes_md", "flashcards_md")


def discover_bundles() -> list[dict]:
    """Completed run directories under OUTPUT_ROOT, best-first per topic."""
    found: list[dict] = []
    if not os.path.isdir(OUTPUT_ROOT):
        return found

    # Two layouts coexist. Older runs sit directly under output/ as
    # {slug}_{timestamp}/. Newer ones sit under output/{run_id}/{slug}_{ts}/,
    # because the server now names the parent after the run id so concurrent
    # runs cannot collide. Look one level deep to catch both.
    candidates: list[str] = []
    for name in sorted(os.listdir(OUTPUT_ROOT)):
        top = os.path.join(OUTPUT_ROOT, name)
        if not os.path.isdir(top) or name.startswith("_"):
            continue
        candidates.append(top)
        candidates.extend(
            os.path.join(top, sub)
            for sub in sorted(os.listdir(top))
            if os.path.isdir(os.path.join(top, sub))
        )

    for run_dir in candidates:
        timing = os.path.join(run_dir, "timing.json")
        if not os.path.isfile(timing):
            continue
        name = os.path.basename(run_dir)
        try:
            with open(timing, encoding="utf-8") as f:
                topic = (json.load(f).get("topic") or "").strip()
        except (OSError, json.JSONDecodeError):
            continue
        if not topic:
            continue

        outputs = run_manager.collect_outputs(run_dir)
        missing = [k for k in _REQUIRED if k not in outputs]
        if missing:
            print(f"  skip  {name}\n        incomplete, missing {', '.join(missing)}")
            continue

        found.append({
            "run_dir": run_dir,
            "topic": topic,
            "outputs": outputs,
            "has_video": "video" in outputs,
            "size": sum(
                os.path.getsize(p) for p in outputs.values() if os.path.isfile(p)
            ),
        })

    # One entry per topic: several runs of the same topic would compete for the
    # same query at near-identical scores. Prefer video, then the larger bundle.
    best: dict[str, dict] = {}
    for b in found:
        key = b["topic"].lower()
        cur = best.get(key)
        if cur is None or (b["has_video"], b["size"]) > (cur["has_video"], cur["size"]):
            best[key] = b
    return list(best.values())


def seed_cache(bundles: list[dict]) -> None:
    for b in bundles:
        prompt_cache.remember(b["topic"], b["run_dir"], b["outputs"])
        video = "with video" if b["has_video"] else "no video"
        print(f"  cached  {b['topic']!r}\n          {len(b['outputs'])} files, {video}")

    # Warm the short phrasings too, as their own entries -- see DEMO_PHRASINGS.
    for phrase, fragment in DEMO_PHRASINGS.items():
        target = next(
            (b for b in bundles if fragment.lower() in b["topic"].lower()), None
        )
        if target is None:
            print(f"  alias   {phrase!r}: no bundle matches {fragment!r} -- skipped")
            continue
        prompt_cache.remember(phrase, target["run_dir"], target["outputs"])
        print(f"  alias   {phrase!r} -> {target['topic']!r}")


def seed_history(bundles: list[dict], email: str) -> None:
    """Attach the bundles to an account so /history and the package page work."""
    # auth_db exposes no lookup-by-email (nothing in the app needs one), so read
    # the row directly rather than widening its API for a maintenance script.
    row = auth_db._get_conn().execute(
        "SELECT id FROM users WHERE email = ?", (email.strip().lower(),)
    ).fetchone()
    if row is None:
        print(f"  no account for {email} — sign up in the app first, or omit --user")
        return
    user = {"id": row["id"]}

    import uuid
    from datetime import datetime, timezone

    for b in bundles:
        run_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        auth_db.upsert_run(run_id, user["id"], b["topic"], "complete", now)
        auth_db.set_run_result(run_id, "complete", b["run_dir"], b["outputs"])
        print(f"  history {b['topic']!r} -> {run_id}")


def check(bundles: list[dict]) -> bool:
    """Confirm the phrasings a demo will actually type resolve to a cache hit."""
    print(f"\nthreshold {prompt_cache._THRESHOLD} — every phrasing must clear it\n")
    ok = True
    for phrase in DEMO_PHRASINGS:
        hit = prompt_cache.find_similar(phrase)
        if hit:
            has_video = os.path.isfile(hit["outputs"].get("video", ""))
            print(f"  HIT   {phrase!r}\n        {hit['score']} -> {hit['cached_topic']!r}"
                  f" ({'video' if has_video else 'no video'})")
        else:
            ok = False
            print(f"  MISS  {phrase!r}  <-- would fall through to a full generation")
    return ok


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--user", default=None,
                    help="email of an existing account to attach run history to")
    ap.add_argument("--check", action="store_true",
                    help="only test the phrasings; seed nothing")
    args = ap.parse_args()

    auth_db.init_db()

    print(f"scanning {OUTPUT_ROOT}\n")
    bundles = discover_bundles()
    if not bundles:
        sys.exit("no complete bundles found — run the pipeline at least once first")

    if not args.check:
        print()
        seed_cache(bundles)
        if args.user:
            print()
            seed_history(bundles, args.user)

    ok = check(bundles)
    print()
    if ok:
        print("All demo phrasings resolve. Safe to type any of them live.")
    else:
        sys.exit("Some phrasings miss. Fix before demoing — add the exact wording "
                 "to DEMO_PHRASINGS and reseed, or lower CACHE_SIM_THRESHOLD.")


if __name__ == "__main__":
    main()
