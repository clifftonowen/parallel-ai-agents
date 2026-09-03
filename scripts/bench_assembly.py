#!/usr/bin/env python3
"""Time the two video assembly paths, and sweep the parallel one's width.

Video assembly is 75 to 81% of a full pipeline run, and it is the one stage the
existing benchmark deletes with --skip-video rather than measures. This measures
it.

It costs nothing to run. Assembly needs slides and narration, both of which are
already on disk from earlier runs, so no model is called and no credit is spent.
That is why this can afford repetitions where the orchestration comparison
cannot: run it fifty times if you like.

What the sweep is for: each ffmpeg is itself multi-threaded, so more workers
than cores does not keep helping. The point where the curve flattens is where
true parallelism stops paying on this machine, and that flattening is the
result worth reporting, not the single best number.

Usage:
    python scripts/bench_assembly.py --list
    python scripts/bench_assembly.py --repeats 5
    python scripts/bench_assembly.py --repeats 5 --widths 1,2,4,8,16
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from paths import OUTPUT_ROOT, PROJECT_ROOT  # noqa: E402
from src.agents import video_assembly as va  # noqa: E402


def find_sources() -> list[tuple[str, list[str], list[str]]]:
    """Runs on disk that carry a complete, matched set of slides and audio."""
    found = []
    if not os.path.isdir(OUTPUT_ROOT):
        return found
    for name in sorted(os.listdir(OUTPUT_ROOT)):
        run = os.path.join(OUTPUT_ROOT, name)
        slides, audio = os.path.join(run, "slides"), os.path.join(run, "audio")
        if not (os.path.isdir(slides) and os.path.isdir(audio)):
            continue
        pngs = sorted(os.path.join(slides, f) for f in os.listdir(slides)
                      if f.endswith(".png"))
        mp3s = sorted(os.path.join(audio, f) for f in os.listdir(audio)
                      if f.endswith(".mp3"))
        # Unmatched counts mean a partial run. Timing one would compare
        # different amounts of work between configurations.
        if pngs and len(pngs) == len(mp3s):
            found.append((name, pngs, mp3s))
    return found


def time_once(fn, *args, **kwargs) -> float:
    start = time.monotonic()
    fn(*args, **kwargs)
    return time.monotonic() - start


def summarise(values: list[float]) -> dict:
    return {
        "n": len(values),
        "mean_s": round(statistics.fmean(values), 2),
        "stdev_s": round(statistics.stdev(values), 2) if len(values) > 1 else 0.0,
        "min_s": round(min(values), 2),
        "runs_s": [round(v, 2) for v in values],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", default=None, help="which output/ run to use")
    ap.add_argument("--repeats", type=int, default=5, help="timings per config")
    ap.add_argument("--widths", default="1,2,4,8,16",
                    help="parallel pool widths to sweep")
    ap.add_argument("--skip-sequential", action="store_true",
                    help="omit the MoviePy baseline (it is the slow one)")
    ap.add_argument("--list", action="store_true", help="show usable runs and exit")
    ap.add_argument("--out-json", default=None)
    args = ap.parse_args()

    sources = find_sources()
    if args.list or not sources:
        for name, pngs, _ in sources:
            print(f"  {name}  ({len(pngs)} slides)")
        if not sources:
            print("  no run in output/ has a matched slides/ and audio/ pair")
        return 0 if sources else 1

    if args.run:
        sources = [s for s in sources if s[0] == args.run]
        if not sources:
            print(f"no run named {args.run}")
            return 1
    # Default to the widest deck: more slides means more parallelism to find.
    name, pngs, mp3s = max(sources, key=lambda s: len(s[1]))

    work = os.path.join(OUTPUT_ROOT, "_assembly_bench")
    os.makedirs(work, exist_ok=True)
    widths = [int(w) for w in args.widths.split(",") if w.strip()]

    print(f"run:     {name}")
    print(f"slides:  {len(pngs)}")
    print(f"cores:   {os.cpu_count()}")
    print(f"repeats: {args.repeats}\n")

    results: dict = {
        "run": name,
        "slides": len(pngs),
        "cpu_count": os.cpu_count(),
        "repeats": args.repeats,
        "configs": {},
    }

    if not args.skip_sequential:
        print("sequential (MoviePy, one encode)")
        times = []
        for i in range(args.repeats):
            out = os.path.join(work, f"seq_{i}.mp4")
            times.append(time_once(va.assemble_sequential, pngs, mp3s, out))
            print(f"   {times[-1]:7.1f}s")
        results["configs"]["sequential"] = summarise(times)
        s = results["configs"]["sequential"]
        print(f"   mean {s['mean_s']:.1f}s +/- {s['stdev_s']:.1f}\n")

    for width in widths:
        if width > len(pngs):
            print(f"parallel width {width}: more workers than slides, skipping\n")
            continue
        print(f"parallel, {width} concurrent ffmpeg")
        times = []
        for i in range(args.repeats):
            out = os.path.join(work, f"par_{width}_{i}.mp4")
            times.append(time_once(va.assemble_parallel, pngs, mp3s, out,
                                   workers=width))
            print(f"   {times[-1]:7.1f}s")
        results["configs"][f"parallel_{width}"] = summarise(times)
        s = results["configs"][f"parallel_{width}"]
        print(f"   mean {s['mean_s']:.1f}s +/- {s['stdev_s']:.1f}\n")

    base = results["configs"].get("sequential", {}).get("mean_s")
    if base:
        print("speedup against the sequential path:")
        for key, cfg in results["configs"].items():
            if key.startswith("parallel_"):
                cfg["speedup"] = round(base / cfg["mean_s"], 2)
                print(f"   width {key.split('_')[1]:>2}: {cfg['speedup']:.2f}x")

    dest = args.out_json or os.path.join(PROJECT_ROOT, "benchmarks",
                                         "assembly-sweep.json")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)
    print(f"\nwrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
