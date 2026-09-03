#!/usr/bin/env python3
"""Run the thread-pool vs asyncio comparison N times per arm.

The committed comparison was one run per arm, which is why every page that
quotes it has to say "indicative". One run cannot separate a real difference
from the API having a slow minute. This runs both arms repeatedly and reports
the spread, so the claim can be stated with a number attached to it.

Two things this does that a shell loop would not:

**It alternates the order.** Round 1 runs the thread pool then asyncio, round 2
runs asyncio then the thread pool, and so on. If API latency drifts over the
twenty minutes this takes, running all of one arm and then all of the other
would hand the whole drift to one of them. Alternating cancels it.

**It holds everything else still.** Same topic every time, video off, cache off.
Video assembly is single-threaded ffmpeg and 76 to 81% of wall time, so leaving
it in buries the thing being measured. The cache is off because a hit would
skip the work entirely and time something else.

Usage:
    python scripts/repeat_benchmark.py --rounds 5
    python scripts/repeat_benchmark.py --rounds 2 --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from paths import PROJECT_ROOT, PYTHON  # noqa: E402

TOPIC = "gradient descent optimisation in machine learning"
ARMS = ("original", "async")
ARM_FLAG = {"original": "--original-only", "async": "--async-only"}


def one_run(arm: str, out_dir: str, index: int, dry: bool) -> dict | None:
    """One arm, once. Returns its report, or None if it failed."""
    run_root = os.path.join(out_dir, f"{arm}-{index}")
    out_json = os.path.join(out_dir, f"{arm}-{index}.json")
    cmd = [
        PYTHON, "benchmark_profile.py",
        "--topic", TOPIC,
        ARM_FLAG[arm],
        "--skip-video",
        "--no-cprofile",
        "--run-root", run_root,
        "--out-json", out_json,
    ]
    if dry:
        print("   would run:", " ".join(cmd[1:]))
        return None

    env = {
        **os.environ,
        # A cache hit would skip the work and time something else entirely.
        "CACHE_ENABLED": "0",
        "PYTHONUNBUFFERED": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    started = time.time()
    proc = subprocess.run(
        cmd, cwd=PROJECT_ROOT, env=env,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    elapsed = time.time() - started

    if proc.returncode != 0:
        tail = (proc.stdout or "")[-400:]
        print(f"   FAILED after {elapsed:.0f}s (exit {proc.returncode})")
        print("   " + tail.replace("\n", "\n   "))
        return None
    try:
        with open(out_json, encoding="utf-8") as fh:
            report = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"   no readable report: {exc}")
        return None

    wall = report.get(arm, {}).get("total_wall_s")
    print(f"   {arm:9} {wall:6.1f}s   (process {elapsed:.0f}s)")
    return report


def summarise(values: list[float]) -> dict:
    """Mean and spread. stdev needs two points, so n=1 reports 0."""
    return {
        "n": len(values),
        "mean_s": round(statistics.fmean(values), 2),
        "stdev_s": round(statistics.stdev(values), 2) if len(values) > 1 else 0.0,
        "min_s": round(min(values), 2),
        "max_s": round(max(values), 2),
        "runs_s": [round(v, 2) for v in values],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rounds", type=int, default=5, help="runs per arm (default 5)")
    ap.add_argument("--out-dir", default=None, help="where to put run artifacts")
    ap.add_argument("--dry-run", action="store_true", help="print the commands only")
    args = ap.parse_args()

    out_dir = args.out_dir or os.path.join(PROJECT_ROOT, "output", "bench-repeat")
    os.makedirs(out_dir, exist_ok=True)

    print(f"topic: {TOPIC}")
    print(f"{args.rounds} rounds, both arms, video off, cache off, order alternating\n")

    collected: dict[str, list[dict]] = {"original": [], "async": []}
    for i in range(args.rounds):
        # Alternate, so latency drift does not land on one arm.
        order = ARMS if i % 2 == 0 else tuple(reversed(ARMS))
        print(f"round {i + 1}/{args.rounds}  ({' then '.join(order)})")
        for arm in order:
            report = one_run(arm, out_dir, i, args.dry_run)
            if report:
                collected[arm].append(report)

    if args.dry_run:
        return 0

    print()
    summary: dict = {
        "topic": TOPIC,
        "timestamp": datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
        "conditions": {
            "skip_video": True,
            "cache_enabled": False,
            "cprofile": False,
            "order": "alternating",
        },
        "arms": {},
    }

    for arm in ARMS:
        reports = collected[arm]
        if not reports:
            print(f"{arm}: no successful runs")
            continue
        totals = [r[arm]["total_wall_s"] for r in reports]
        entry = {"total_wall_s": summarise(totals), "phases": {}}
        for phase in ("phase1_wall_s", "phase2_wall_s", "phase3_wall_s"):
            vals = [r[arm]["phases"][phase] for r in reports if phase in r[arm].get("phases", {})]
            if vals:
                entry["phases"][phase] = summarise(vals)
        toks = [r[arm].get("tokens", {}) for r in reports]
        entry["tokens"] = {
            k: summarise([t[k] for t in toks if t.get(k) is not None])
            for k in ("total_input", "total_output", "llm_calls")
            if any(t.get(k) is not None for t in toks)
        }
        summary["arms"][arm] = entry

        s = entry["total_wall_s"]
        print(f"{arm:9} {s['mean_s']:7.1f}s +/- {s['stdev_s']:.1f}  "
              f"(n={s['n']}, {s['min_s']:.1f}-{s['max_s']:.1f})")

    if len(summary["arms"]) == 2:
        o = summary["arms"]["original"]["total_wall_s"]["mean_s"]
        a = summary["arms"]["async"]["total_wall_s"]["mean_s"]
        summary["speedup_overall"] = round(o / a, 3)
        op = summary["arms"]["original"]["phases"].get("phase2_wall_s", {}).get("mean_s")
        apz = summary["arms"]["async"]["phases"].get("phase2_wall_s", {}).get("mean_s")
        if op and apz:
            summary["speedup_phase2"] = round(op / apz, 3)
            print(f"\noverall  {summary['speedup_overall']}x")
            print(f"phase 2  {summary['speedup_phase2']}x")

    dest = os.path.join(out_dir, "summary.json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    print(f"\nwrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
