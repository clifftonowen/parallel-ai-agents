#!/usr/bin/env python3
"""
benchmark_profile.py
--------------------
Profiling harness comparing StudyOrchestrator (ThreadPoolExecutor),
ADKStudyOrchestrator (Google ADK), and AsyncStudyOrchestrator (pure asyncio
with model tiering + prompt caching) on the same topic.

Usage:
    python benchmark_profile.py [--topic "..."]
                                [--adk-only | --original-only | --async-only]
                                [--no-cprofile] [--otel]

Outputs:
    - Side-by-side console comparison table
    - profiling_results_YYYYMMDD_HHMMSS.json  (at project root)
    - original.prof, adk.prof, async.prof     (if --no-cprofile not set)
"""

from __future__ import annotations

import argparse
import cProfile
import io
import json
import os
import pstats
import sys
import threading
import time
import warnings
from datetime import datetime
from typing import Any

# ── path setup ────────────────────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, ".env"))

from src.agents.config import require_env  # noqa: E402

# Suppress DeprecationWarnings from ADK's _sync session methods
warnings.filterwarnings("ignore", category=DeprecationWarning, module="google.adk")

# ── token spy for original (non-ADK) path ────────────────────────────────────

_api_calls: list[dict] = []
_api_calls_lock = threading.Lock()


def _make_spy_create(original_create):
    """Wrap anthropic.resources.Messages.create to capture timing + token usage."""
    def spy(self_resource, **kwargs):
        t0 = time.monotonic()
        resp = original_create(self_resource, **kwargs)
        elapsed = time.monotonic() - t0
        with _api_calls_lock:
            _api_calls.append({
                "elapsed_s": round(elapsed, 4),
                "input_tokens": getattr(resp.usage, "input_tokens", 0) or 0,
                "output_tokens": getattr(resp.usage, "output_tokens", 0) or 0,
            })
        return resp
    return spy


# ── ADK event helpers ─────────────────────────────────────────────────────────

_PHASE_AGENTS = {
    "phase1": ["notes_agent", "notes_post_process"],
    "phase2": ["flashcard_agent", "video_agent", "notes_pdf_agent"],
    "phase3": ["flashcards_pdf_agent"],
}


def _extract_adk_tokens(events: list) -> dict:
    """Parse usage_metadata from ADK events, grouped by agent author."""
    token_by_agent: dict[str, dict] = {}
    for event in events:
        if event.usage_metadata is None:
            continue
        bucket = token_by_agent.setdefault(
            event.author,
            {"input_tokens": 0, "output_tokens": 0, "llm_events": 0},
        )
        bucket["input_tokens"] += event.usage_metadata.prompt_token_count or 0
        bucket["output_tokens"] += event.usage_metadata.candidates_token_count or 0
        bucket["llm_events"] += 1
    return token_by_agent


def _compute_adk_phase_times(events: list) -> dict:
    """Compute phase wall-clock times from event.timestamp deltas.

    For each agent, first_event.timestamp = start, last_event.timestamp = end.
    Phase wall time = max(agent_end) - min(agent_start) for agents in that phase.
    """
    bounds: dict[str, dict] = {}
    for event in events:
        a, ts = event.author, event.timestamp
        if a not in bounds:
            bounds[a] = {"first": ts, "last": ts}
        else:
            bounds[a]["first"] = min(bounds[a]["first"], ts)
            bounds[a]["last"] = max(bounds[a]["last"], ts)

    phase_times: dict[str, float] = {}
    for phase, agents in _PHASE_AGENTS.items():
        starts = [bounds[a]["first"] for a in agents if a in bounds]
        ends = [bounds[a]["last"] for a in agents if a in bounds]
        if starts and ends:
            phase_times[phase] = round(max(ends) - min(starts), 3)
    return phase_times


def _check_tool_parallelism(spans: list) -> dict:
    """Detect whether tool calls ran concurrently by checking span time overlap."""
    tool_spans = [
        s for s in spans
        if (s.attributes or {}).get("gen_ai.operation.name") == "execute_tool"
        or "execute_tool" in getattr(s, "name", "")
    ]
    if len(tool_spans) < 2:
        return {"parallel_detected": False, "tool_call_count": len(tool_spans)}

    overlaps = 0
    for i, s1 in enumerate(tool_spans):
        for s2 in tool_spans[i + 1:]:
            if s1.start_time < s2.end_time and s2.start_time < s1.end_time:
                overlaps += 1

    return {
        "parallel_detected": overlaps > 0,
        "overlap_pairs": overlaps,
        "tool_call_count": len(tool_spans),
    }


# ── OTel setup ────────────────────────────────────────────────────────────────

def _setup_otel():
    """Install InMemorySpanExporter as the global OTel provider.

    Must be called BEFORE ADKStudyOrchestrator is instantiated so ADK's
    ProxyTracer resolves to this provider at first span creation.
    """
    try:
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry import trace

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        return exporter
    except ImportError:
        print("[OTel] opentelemetry-sdk not installed — skipping OTel tracing.")
        return None


def _extract_otel_stats(exporter) -> dict:
    """Summarise gen_ai spans from the InMemorySpanExporter."""
    if exporter is None:
        return {}

    spans = exporter.get_finished_spans()

    llm_spans = [s for s in spans if "generate_content" in getattr(s, "name", "")]
    tool_spans = [
        s for s in spans
        if "execute_tool" in getattr(s, "name", "")
        or (s.attributes or {}).get("gen_ai.operation.name") == "execute_tool"
    ]

    total_input = sum(
        (s.attributes or {}).get("gen_ai.usage.input_tokens", 0) for s in llm_spans
    )
    total_output = sum(
        (s.attributes or {}).get("gen_ai.usage.output_tokens", 0) for s in llm_spans
    )

    llm_latencies = [
        (s.end_time - s.start_time) / 1e9 for s in llm_spans if s.end_time
    ]
    tool_latencies = [
        (s.end_time - s.start_time) / 1e9 for s in tool_spans if s.end_time
    ]

    return {
        "llm_call_count": len(llm_spans),
        "total_input_tokens_otel": total_input,
        "total_output_tokens_otel": total_output,
        "avg_llm_latency_s": round(
            sum(llm_latencies) / len(llm_latencies), 3
        ) if llm_latencies else 0,
        "tool_call_count": len(tool_spans),
        "avg_tool_latency_s": round(
            sum(tool_latencies) / len(tool_latencies), 3
        ) if tool_latencies else 0,
        "tool_parallelism": _check_tool_parallelism(spans),
    }


# ── cProfile wrapper ──────────────────────────────────────────────────────────

def _run_with_cprofile(fn, *args, out_path: str, **kwargs):
    """Run fn(*args, **kwargs) under cProfile; dump .prof and print top-20."""
    pr = cProfile.Profile()
    pr.enable()
    try:
        result = fn(*args, **kwargs)
    finally:
        pr.disable()
    pr.dump_stats(out_path)
    s = io.StringIO()
    pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(20)
    print(s.getvalue())
    return result


# ── console output ────────────────────────────────────────────────────────────

def _fmt(val, unit: str = "s") -> str:
    if val is None or val == {} or val == "":
        return "     N/A"
    if isinstance(val, float):
        return f"{val:8.2f}{unit}"
    if isinstance(val, int):
        return f"{val:9d}"
    return f"  {str(val)[:10]:<10}"


def _diff(a, b) -> str:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and b:
        delta = a - b
        ratio = a / b
        sign = "+" if delta >= 0 else ""
        return f"{sign}{delta:.2f}s ({ratio:.2f}x)"
    return ""


def _print_comparison_table(results: dict) -> None:
    orig = results.get("original") or {}
    adk  = results.get("adk") or {}
    asyn = results.get("async") or {}

    o_phases = orig.get("phases", {})
    a_phases = adk.get("phases", {})
    s_phases = asyn.get("phases", {})
    o_agents = orig.get("agents", {})
    a_agents = adk.get("agents", {})
    s_agents = asyn.get("agents", {})
    o_tok = orig.get("tokens", {})
    a_tok = adk.get("tokens", {})
    s_tok = asyn.get("tokens", {})
    o_vid = o_agents.get("video", {})
    a_vid = a_agents.get("video", {})
    s_vid = s_agents.get("video", {})

    SEP = "-" * 90
    HDR = (f"\n{'Metric':<40} {'Original':>10} {'ADK':>10} {'Async':>10}"
           f"  {'Orig−Async':>12}")

    print(f"\n{SEP}")
    print(f"  BENCHMARK RESULTS — topic: {results['topic']}")
    print(f"  Run timestamp: {results['timestamp']}")
    print(SEP)
    print(HDR)
    print(SEP)

    rows: list[tuple] = [
        ("WALL-CLOCK TIMES", None, None, None),
        ("  Total end-to-end",
            orig.get("total_wall_s"), adk.get("total_wall_s"), asyn.get("total_wall_s")),
        ("  Phase 1  (Notes)",
            o_phases.get("phase1_wall_s"), a_phases.get("phase1"), s_phases.get("phase1_wall_s")),
        ("  Phase 2  (Flashcard + Video, parallel)",
            o_phases.get("phase2_wall_s"), a_phases.get("phase2"), s_phases.get("phase2_wall_s")),
        ("  Phase 3  (PDFs, parallel)",
            o_phases.get("phase3_wall_s"), a_phases.get("phase3"), s_phases.get("phase3_wall_s")),
        ("", None, None, None),
        ("AGENT TIMES", None, None, None),
        ("  Notes agent",
            o_agents.get("notes", {}).get("duration_s"), "(events)",
            s_agents.get("notes", {}).get("duration_s")),
        ("  Flashcard agent",
            o_agents.get("flashcard", {}).get("duration_s"), "(events)",
            s_agents.get("flashcard", {}).get("duration_s")),
        ("  Video — total",
            o_vid.get("total_s"), a_vid.get("total_s"), s_vid.get("total_s")),
        ("  Video — stage A  (narrations ‖ slides)",
            o_vid.get("stage_a_s"), a_vid.get("stage_a_s"), s_vid.get("stage_a_s")),
        ("  Video — stage BC (audio ‖ pptx)",
            o_vid.get("stage_bc_s"), a_vid.get("stage_bc_s"), s_vid.get("stage_bc_s")),
        ("  Video — stage D  (assemble)",
            o_vid.get("assemble_s"), a_vid.get("assemble_s"), s_vid.get("assemble_s")),
        ("", None, None, None),
        ("TOKEN USAGE", None, None, None),
        ("  Total input tokens",
            o_tok.get("total_input"), a_tok.get("total_input"), s_tok.get("total_input")),
        ("  Total output tokens",
            o_tok.get("total_output"), a_tok.get("total_output"), s_tok.get("total_output")),
        ("  LLM API calls",
            o_tok.get("llm_calls"), "(events)", s_tok.get("llm_calls")),
        ("  Cache read tokens (async)",
            None, None, s_tok.get("cache_read_tokens")),
    ]

    for row in rows:
        label, orig_val, adk_val, asyn_val = row
        if not label:
            print()
            continue
        if label.isupper():
            print(f"\n{label}")
            continue
        delta = _diff(orig_val, asyn_val) if isinstance(orig_val, (int, float)) and isinstance(asyn_val, (int, float)) else ""
        o_str = _fmt(orig_val)
        a_str = _fmt(adk_val) if not isinstance(adk_val, str) else f"  {adk_val:<10}"
        s_str = _fmt(asyn_val)
        print(f"{label:<40} {o_str:>10} {a_str:>10} {s_str:>10}  {delta:>12}")

    print(SEP)


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark StudyOrchestrator vs ADKStudyOrchestrator"
    )
    parser.add_argument(
        "--topic", default="machine learning basics",
        help="Topic to generate study materials for (default: 'machine learning basics')"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--adk-only", action="store_true",
                       help="Only run the ADK orchestrator")
    group.add_argument("--original-only", action="store_true",
                       help="Only run the original ThreadPoolExecutor orchestrator")
    group.add_argument("--async-only", action="store_true",
                       help="Only run the async orchestrator (Haiku tiering + caching)")
    parser.add_argument("--no-cprofile", action="store_true",
                        help="Skip cProfile (faster; omits .prof files)")
    parser.add_argument("--skip-video", action="store_true",
                        help="Skip the video stage (async orchestrator only). "
                             "Video assembly is 76-81%% of wall time, so this "
                             "cuts a run from ~10 minutes to ~2 and isolates "
                             "orchestration cost from ffmpeg encoding.")
    parser.add_argument("--run-root", default=None,
                        help="Directory to write this run's artifacts into. "
                             "Defaults to OUTPUT_ROOT. The API server passes a "
                             "per-run path so concurrent runs cannot collide.")
    parser.add_argument("--out-json", default=None,
                        help="Where to write the benchmark results JSON. "
                             "Defaults to a timestamped file at the repo root.")
    parser.add_argument("--otel", action="store_true",
                        help="Enable OpenTelemetry span collection for ADK path")
    args = parser.parse_args()

    anthropic_key = require_env("ANTHROPIC_API_KEY", "Claude pipeline")
    openai_key = require_env("OPENAI_API_KEY", "TTS + embeddings")

    topic = args.topic
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    _run_root_kw = {"output_dir": args.run_root} if args.run_root else {}
    results: dict[str, Any] = {
        "topic": topic,
        "timestamp": timestamp,
        "original": None,
        "adk": None,
        "async": None,
    }

    # ── ORIGINAL PATH ─────────────────────────────────────────────────────────
    if not args.adk_only and not args.async_only:
        print("\n" + "=" * 70)
        print("  BENCHMARKING: StudyOrchestrator (ThreadPoolExecutor)")
        print("=" * 70)

        import anthropic
        from unittest.mock import patch
        from src.agents.orchestrator import StudyOrchestrator

        _api_calls.clear()
        _orig_create = anthropic.resources.Messages.create

        orch_orig = StudyOrchestrator(
            anthropic_api_key=anthropic_key,
            openai_api_key=openai_key,
            **_run_root_kw,
        )

        t_start = time.monotonic()
        with patch.object(
            anthropic.resources.Messages, "create",
            _make_spy_create(_orig_create)
        ):
            if not args.no_cprofile:
                orig_summary = _run_with_cprofile(
                    orch_orig.run, topic,
                    out_path=os.path.join(_ROOT, "original.prof"),
                )
            else:
                orig_summary = orch_orig.run(topic)
        t_total = time.monotonic() - t_start

        orig_api_snapshot = list(_api_calls)

        # Extract per-agent timing from return dicts
        notes_res = orig_summary.get("notes_md", {})
        fc_res    = orig_summary.get("flashcards_md", {})
        vid_res   = orig_summary.get("video", {})
        npdf_res  = orig_summary.get("notes_pdf", {})
        fpdf_res  = orig_summary.get("flashcards_pdf", {})

        notes_dur = notes_res.get("duration_s", 0) or 0
        fc_dur    = fc_res.get("duration_s", 0) or 0
        vid_bench = vid_res.get("benchmark", {})
        vid_total = vid_bench.get("total_s", 0) or 0
        npdf_dur  = npdf_res.get("duration_s", 0) or 0
        fpdf_dur  = fpdf_res.get("duration_s", 0) or 0

        results.setdefault("run_dirs", {})["original"] = orig_summary.get("run_dir", "")
        results["original"] = {
            "total_wall_s": round(t_total, 3),
            "phases": {
                "phase1_wall_s": round(notes_dur, 3),
                "phase2_wall_s": round(max(fc_dur, vid_total, npdf_dur), 3),
                "phase3_wall_s": round(fpdf_dur, 3),
            },
            "agents": {
                "notes":          {"duration_s": notes_dur,
                                   "started_at": notes_res.get("started_at"),
                                   "finished_at": notes_res.get("finished_at")},
                "flashcard":      {"duration_s": fc_dur,
                                   "started_at": fc_res.get("started_at"),
                                   "finished_at": fc_res.get("finished_at")},
                "video":          vid_bench,
                "notes_pdf":      {"duration_s": npdf_dur,
                                   "started_at": npdf_res.get("started_at"),
                                   "finished_at": npdf_res.get("finished_at")},
                "flashcards_pdf": {"duration_s": fpdf_dur,
                                   "started_at": fpdf_res.get("started_at"),
                                   "finished_at": fpdf_res.get("finished_at")},
            },
            "tokens": {
                "total_input":  sum(c["input_tokens"] for c in orig_api_snapshot),
                "total_output": sum(c["output_tokens"] for c in orig_api_snapshot),
                "llm_calls":    len(orig_api_snapshot),
                "llm_total_s":  round(sum(c["elapsed_s"] for c in orig_api_snapshot), 3),
            },
        }

        if not args.no_cprofile:
            print(f"\n[Profile] original.prof saved to {_ROOT}")

    # ── ADK PATH ──────────────────────────────────────────────────────────────
    if not args.original_only and not args.async_only:
        print("\n" + "=" * 70)
        print("  BENCHMARKING: ADKStudyOrchestrator (Google ADK)")
        print("=" * 70)

        otel_exporter = None
        if args.otel:
            otel_exporter = _setup_otel()
            print("[OTel] InMemorySpanExporter installed.")

        from src.agents.adk_orchestrator import ADKStudyOrchestrator

        orch_adk = ADKStudyOrchestrator(
            anthropic_api_key=anthropic_key,
            openai_api_key=openai_key,
            **_run_root_kw,
        )

        t_start = time.monotonic()
        if not args.no_cprofile:
            adk_summary = _run_with_cprofile(
                orch_adk.run, topic,
                out_path=os.path.join(_ROOT, "adk.prof"),
            )
        else:
            adk_summary = orch_adk.run(topic)
        t_total = time.monotonic() - t_start

        adk_events = adk_summary.pop("_adk_events", [])
        adk_phase_times = _compute_adk_phase_times(adk_events)
        adk_token_by_agent = _extract_adk_tokens(adk_events)
        vid_bench_adk = adk_summary.get("video_benchmark", {})

        otel_stats: dict = {}
        if otel_exporter:
            otel_stats = _extract_otel_stats(otel_exporter)

        total_adk_input  = sum(v["input_tokens"]  for v in adk_token_by_agent.values())
        total_adk_output = sum(v["output_tokens"] for v in adk_token_by_agent.values())

        results.setdefault("run_dirs", {})["adk"] = adk_summary.get("run_dir", "")
        results["adk"] = {
            "total_wall_s": round(t_total, 3),
            "phases": adk_phase_times,
            "agents": {
                "notes":          adk_token_by_agent.get("notes_agent", {}),
                "flashcard":      adk_token_by_agent.get("flashcard_agent", {}),
                "video":          vid_bench_adk,
                "notes_pdf":      adk_token_by_agent.get("notes_pdf_agent", {}),
                "flashcards_pdf": adk_token_by_agent.get("flashcards_pdf_agent", {}),
            },
            "tokens": {
                "total_input":  total_adk_input,
                "total_output": total_adk_output,
                "by_agent":     adk_token_by_agent,
            },
            "otel": otel_stats,
        }

        if not args.no_cprofile:
            print(f"\n[Profile] adk.prof saved to {_ROOT}")

    # ── ASYNC PATH ────────────────────────────────────────────────────────────
    if not args.adk_only and not args.original_only:
        print("\n" + "=" * 70)
        print("  BENCHMARKING: AsyncStudyOrchestrator (asyncio + Haiku tiering + caching)")
        print("=" * 70)

        import anthropic
        from unittest.mock import patch
        from src.agents.async_orchestrator import AsyncStudyOrchestrator

        _api_calls.clear()
        _orig_create = anthropic.resources.Messages.create

        orch_async = AsyncStudyOrchestrator(
            anthropic_api_key=anthropic_key,
            openai_api_key=openai_key,
            **_run_root_kw,
        )

        t_start = time.monotonic()
        with patch.object(
            anthropic.resources.Messages, "create",
            _make_spy_create(_orig_create)
        ):
            if not args.no_cprofile:
                async_summary = _run_with_cprofile(
                    orch_async.run, topic,
                    out_path=os.path.join(_ROOT, "async.prof"),
                )
            else:
                async_summary = orch_async.run(topic, include_video=not args.skip_video)
        t_total = time.monotonic() - t_start

        async_api_snapshot = list(_api_calls)

        notes_res  = async_summary.get("notes_md", {})
        fc_res     = async_summary.get("flashcards_md", {})
        vid_res    = async_summary.get("video", {})
        npdf_res   = async_summary.get("notes_pdf", {})
        fpdf_res   = async_summary.get("flashcards_pdf", {})

        notes_dur = notes_res.get("duration_s", 0) or 0
        fc_dur    = fc_res.get("duration_s", 0) or 0
        vid_bench = vid_res.get("benchmark", {})
        vid_total = vid_bench.get("total_s", 0) or 0
        npdf_dur  = npdf_res.get("duration_s", 0) or 0
        fpdf_dur  = fpdf_res.get("duration_s", 0) or 0

        # Cache hit stats (populated when cache_control is active)
        cache_read   = sum(getattr(c.get("_resp_usage", None), "cache_read_input_tokens", 0) or 0
                           for c in async_api_snapshot)
        cache_create = sum(getattr(c.get("_resp_usage", None), "cache_creation_input_tokens", 0) or 0
                           for c in async_api_snapshot)

        results.setdefault("run_dirs", {})["async"] = async_summary.get("run_dir", "")
        results["async"] = {
            "total_wall_s": round(t_total, 3),
            "phases": {
                "phase1_wall_s": round(notes_dur, 3),
                "phase2_wall_s": round(max(fc_dur, vid_total, npdf_dur), 3),
                "phase3_wall_s": round(fpdf_dur, 3),
            },
            "agents": {
                "notes":          {"duration_s": notes_dur,
                                   "started_at": notes_res.get("started_at"),
                                   "finished_at": notes_res.get("finished_at")},
                "flashcard":      {"duration_s": fc_dur,
                                   "started_at": fc_res.get("started_at"),
                                   "finished_at": fc_res.get("finished_at")},
                "video":          vid_bench,
                "notes_pdf":      {"duration_s": npdf_dur,
                                   "started_at": npdf_res.get("started_at"),
                                   "finished_at": npdf_res.get("finished_at")},
                "flashcards_pdf": {"duration_s": fpdf_dur,
                                   "started_at": fpdf_res.get("started_at"),
                                   "finished_at": fpdf_res.get("finished_at")},
            },
            "tokens": {
                "total_input":        sum(c["input_tokens"] for c in async_api_snapshot),
                "total_output":       sum(c["output_tokens"] for c in async_api_snapshot),
                "llm_calls":          len(async_api_snapshot),
                "llm_total_s":        round(sum(c["elapsed_s"] for c in async_api_snapshot), 3),
                "cache_read_tokens":  cache_read,
                "cache_create_tokens": cache_create,
            },
        }

        if not args.no_cprofile:
            print(f"\n[Profile] async.prof saved to {_ROOT}")

    # ── OUTPUT ────────────────────────────────────────────────────────────────
    _print_comparison_table(results)

    # Strip large content fields before serializing
    _safe = json.loads(json.dumps(results, default=str))

    out_path = args.out_json or os.path.join(
        _ROOT, f"profiling_results_{timestamp}.json"
    )
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(_safe, f, indent=2)
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
