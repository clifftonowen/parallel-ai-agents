"""
async_orchestrator.py
---------------------
AsyncStudyOrchestrator — pure asyncio variant of the pipeline.

The single difference from StudyOrchestrator (ThreadPoolExecutor):
  asyncio.gather — Phase 2 (flashcard ‖ video ‖ notes.pdf) runs concurrently
                   without thread overhead.

Two things this file used to claim as advantages, corrected after measuring:

  Model tiering is NOT a difference between the orchestrators. Neither passes
  model= anywhere, so both use the agent class defaults — Sonnet for notes,
  Haiku for flashcards and video. The tiering is real, but it lives in the
  agent definitions and applies equally to both arms.

  Prompt caching does not currently engage. cache_control is attached
  correctly (see run_context.notes_system_block), but Haiku 4.5 requires a
  4096-token prefix and typical notes produce ~1700. Measured on this
  pipeline: no cache at 3918 tokens, caching from 4655. Since the agents with
  the repeatable calls worth caching are exactly the Haiku ones, caching only
  begins to pay off for unusually long notes (~13k characters and up).

  That tension is itself the interesting result: the cheaper model carries a
  4x higher cache threshold, so model tiering and prompt caching pull against
  each other. Sonnet's minimum is 1024, so the same block caches there.

Pipeline structure:
    Phase 1:  await _run_notes(topic)           # Sonnet + caching + tools
    Phase 2:  await asyncio.gather(
                  _run_flashcards(notes),       # Haiku + caching
                  _run_video(notes, timing),    # Haiku for narrations/slides
                  _run_pdf(notes_md_path),      # only depends on Phase 1
              )
    Phase 3:  await _run_pdf(flashcards_md_path)  # needs flashcards.md first
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from dotenv import load_dotenv

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

from paths import OUTPUT_ROOT  # noqa: E402
from src.agents.run_context import (  # noqa: E402
    banner, build_summary, load_timing_sections, make_run_dir, print_summary,
)
from src.agents.config import require_env  # noqa: E402
from src.agents.specialist_agent import (  # noqa: E402
    FlashcardAgent,
    NotesAgent,
    PDFAgent,
    VideoAgent,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

_EXECUTOR = ThreadPoolExecutor(max_workers=6)


class AsyncStudyOrchestrator:
    """Pure asyncio study material pipeline with model tiering and prompt caching.

    Drop-in interface: same __init__ and run(topic) as StudyOrchestrator.
    """

    def __init__(
        self,
        anthropic_api_key: str,
        openai_api_key: str,
        output_dir: str = OUTPUT_ROOT,
    ) -> None:
        self.anthropic_api_key = anthropic_api_key
        self.openai_api_key = openai_api_key
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def run(self, topic: str, include_video: bool = True) -> dict[str, Any]:
        """Synchronous entry point — runs the async pipeline to completion.

        Args:
            include_video: When False, skip the video stage entirely. Video
                assembly is single-threaded ffmpeg and 76-81% of wall time,
                so skipping it turns a 6-11 minute run into roughly two
                minutes while still producing notes, flashcards and both
                PDFs. Used for the fast path and to isolate orchestration
                cost when benchmarking.
        """
        return asyncio.run(self._run_async(topic, include_video=include_video))

    # ------------------------------------------------------------------
    # Async pipeline
    # ------------------------------------------------------------------

    async def _run_async(self, topic: str, include_video: bool = True) -> dict[str, Any]:
        run_dir = make_run_dir(self.output_dir, topic)
        log.info("[Async] Run directory: %s", run_dir)

        banner("Async Pipeline — starting", detail=f"topic: {topic!r}")

        # Phase 1: Notes (must finish before Phase 2)
        banner("Phase 1 — NotesAgent (Sonnet + caching)")

        # Bracketed, not inferred. The benchmark used to report
        # max(component durations) for a phase, which excludes exactly the
        # coordination overhead the two arms differ on.
        _t_phase1 = time.monotonic()
        notes_result = await self._run_notes(topic, run_dir)

        if notes_result.get("status") != "ok":
            raise RuntimeError("[Async] NotesAgent failed — aborting pipeline")

        notes_content: str = notes_result["output"]

        timing_json: list = load_timing_sections(notes_result["timing_path"])

        notes_md_path: str = notes_result["md_path"]
        phase1_wall = time.monotonic() - _t_phase1

        # Phase 2: Flashcards ‖ Video ‖ notes.pdf (parallel)
        # notes.pdf only depends on notes_md_path (Phase 1's output), so it
        # runs alongside flashcards/video instead of waiting for them.
        _t_phase2 = time.monotonic()
        if include_video:
            banner("Phase 2 — FlashcardAgent ‖ VideoAgent ‖ notes.pdf (Haiku + caching, parallel)")
            flashcard_result, video_result, notes_pdf_result = await asyncio.gather(
                self._run_flashcards(notes_content, run_dir),
                self._run_video(notes_content, timing_json, run_dir),
                self._run_pdf(notes_md_path),
                return_exceptions=True,
            )
        else:
            banner("Phase 2 — FlashcardAgent ‖ notes.pdf (Haiku + caching, parallel)",
                   detail="video skipped")
            flashcard_result, notes_pdf_result = await asyncio.gather(
                self._run_flashcards(notes_content, run_dir),
                self._run_pdf(notes_md_path),
                return_exceptions=True,
            )
            # Reported rather than omitted, so a consumer can tell "skipped"
            # apart from "attempted and failed".
            video_result = {"status": "skipped"}

        if isinstance(flashcard_result, Exception):
            log.error("[Async] FlashcardAgent raised: %s", flashcard_result)
            flashcard_result = {}
        if isinstance(video_result, Exception):
            log.error("[Async] VideoAgent raised: %s", video_result)
            video_result = {}
        if isinstance(notes_pdf_result, Exception):
            log.error("[Async] PDFAgent (notes) raised: %s", notes_pdf_result)
            notes_pdf_result = {}

        phase2_wall = time.monotonic() - _t_phase2

        flashcards_md_path: str = (flashcard_result or {}).get("flashcards_path", "")

        # Phase 3: flashcards.pdf (needs flashcards.md to exist first)
        banner("Phase 3 — PDFAgent (flashcards)")
        _t_phase3 = time.monotonic()
        flashcards_pdf_result: dict = {}
        if flashcards_md_path:
            flashcards_pdf_result = await self._run_pdf(flashcards_md_path)
            if isinstance(flashcards_pdf_result, Exception):
                log.error("[Async] PDFAgent (flashcards) raised: %s", flashcards_pdf_result)
                flashcards_pdf_result = {}
        else:
            log.info("[Async] Skipping flashcards PDF — no flashcard output.")

        phase3_wall = time.monotonic() - _t_phase3

        summary: dict[str, Any] = build_summary(
            topic, run_dir,
            notes_md=notes_result,
            flashcards_md=flashcard_result,
            video=video_result,
            notes_pdf=notes_pdf_result,
            flashcards_pdf=flashcards_pdf_result,
            phase_wall_s={
                "phase1": round(phase1_wall, 3),
                "phase2": round(phase2_wall, 3),
                "phase3": round(phase3_wall, 3),
            },
        )
        print_summary(summary, "Async Pipeline — complete")

        return summary

    # ------------------------------------------------------------------
    # Per-agent async wrappers (run blocking agents in thread executor)
    # ------------------------------------------------------------------

    async def _run_notes(self, topic: str, run_dir: str) -> dict:
        agent = NotesAgent(api_key=self.anthropic_api_key)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _EXECUTOR,
            lambda: agent.run(topic=topic, output_dir=run_dir),
        )

    async def _run_flashcards(self, notes_content: str, run_dir: str) -> dict:
        agent = FlashcardAgent(api_key=self.anthropic_api_key)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _EXECUTOR,
            lambda: agent.run(notes_content=notes_content, output_dir=run_dir),
        )

    async def _run_video(
        self, notes_content: str, timing_json: list, run_dir: str
    ) -> dict:
        agent = VideoAgent(
            api_key=self.anthropic_api_key,
            openai_api_key=self.openai_api_key,
        )
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _EXECUTOR,
            lambda: agent.run(
                notes_content=notes_content,
                timing_json=timing_json,
                output_dir=run_dir,
            ),
        )

    async def _run_pdf(self, md_path: str) -> dict:
        agent = PDFAgent()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _EXECUTOR,
            lambda: agent.run(input_md_path=md_path),
        )




if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    orchestrator = AsyncStudyOrchestrator(
        anthropic_api_key=require_env("ANTHROPIC_API_KEY", "Claude pipeline"),
        openai_api_key=require_env("OPENAI_API_KEY", "TTS + embeddings"),
    )
    result = orchestrator.run(topic="machine learning basics")
    print(result)
