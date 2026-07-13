"""
orchestrator.py
StudyOrchestrator — three-phase pipeline runner for the multi-agent
study material generator.

Phase 1 (sequential): NotesAgent     → notes.md + timing.json sidecar
Phase 2 (parallel):   FlashcardAgent + VideoAgent consume notes.md
Phase 3 (sequential): PDFAgent renders notes.md and flashcards.md to PDF
"""

import json
import logging
import os
import sys
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from dotenv import load_dotenv

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

from src.agents.specialist_agent import (  # noqa: E402
    FlashcardAgent,
    NotesAgent,
    PDFAgent,
    VideoAgent,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


class StudyOrchestrator:
    """Three-phase pipeline that produces notes, flashcards, a video, and PDFs.

    Phase 1 (sequential): NotesAgent must complete before anything else starts.
    Phase 2 (parallel):   FlashcardAgent and VideoAgent run simultaneously.
    Phase 3 (sequential): PDFAgent converts notes and flashcards to PDF after
                          Phase 2 finishes, regardless of Phase 2 errors.
    """

    def __init__(
        self,
        anthropic_api_key: str,
        openai_api_key: str,
        output_dir: str = "output",
    ) -> None:
        """Initialise all agents and ensure the output directory exists.

        Args:
            anthropic_api_key: Anthropic API key passed to every Claude agent.
            openai_api_key:    OpenAI API key used by VideoAgent for TTS.
            output_dir:        Root directory for all generated artifacts.
                               Created if it does not already exist.
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        self.notes_agent = NotesAgent(api_key=anthropic_api_key)
        self.flashcard_agent = FlashcardAgent(api_key=anthropic_api_key)
        self.video_agent = VideoAgent(
            api_key=anthropic_api_key,
            openai_api_key=openai_api_key,
        )
        self.pdf_agent = PDFAgent(api_key=anthropic_api_key)

    def run(self, topic: str) -> dict[str, Any]:
        """Execute the full three-phase study material generation pipeline.

        Args:
            topic: The subject to generate study materials about.

        Returns:
            Summary dict with keys:
            ``topic``, ``notes_md``, ``flashcards_md``, ``video``,
            ``notes_pdf``, ``flashcards_pdf``.
            Each value is the raw agent result dict (or an empty dict if the
            agent was skipped due to an upstream error).

        Raises:
            RuntimeError: If NotesAgent fails or its output is invalid —
                          the pipeline cannot continue without notes.
        """
        # -------------------------------------------------------- #
        # PHASE 1 — Notes (sequential)                             #
        # -------------------------------------------------------- #
        _banner("Phase 1 — NotesAgent", detail=f"topic: {topic!r}")

        notes_result = self.notes_agent.run(topic=topic)

        if notes_result["status"] != "ok":
            raise RuntimeError("Notes agent failed — aborting pipeline")

        if not self.notes_agent.validate_output(notes_result):
            raise RuntimeError(
                "Notes agent output failed validation — aborting pipeline"
            )

        # Adapt NotesAgent's return keys to the names used below.
        # NotesAgent currently returns:  output → md_path → timing_path
        # This orchestrator treats them as: notes_content, notes_path, timing sidecar
        notes_content: str = notes_result["output"]
        notes_path: str = notes_result["md_path"]

        with open(notes_result["timing_path"], encoding="utf-8") as _f:
            timing_json: list = json.load(_f).get("sections", [])

        # -------------------------------------------------------- #
        # PHASE 2 — Flashcards + Video (parallel)                  #
        # -------------------------------------------------------- #
        _banner("Phase 2 — FlashcardAgent + VideoAgent", detail="parallel")

        with ThreadPoolExecutor(max_workers=2) as pool:
            fc_future: Future = pool.submit(
                self.flashcard_agent.run, notes_content=notes_content
            )
            vid_future: Future = pool.submit(
                self.video_agent.run,
                notes_content=notes_content,
                timing_json=timing_json,
            )
        # Both futures have completed (or failed) here — the executor
        # waited for both before exiting the with block.

        flashcard_result: dict = {}
        try:
            flashcard_result = fc_future.result()
        except Exception as exc:
            log.error("FlashcardAgent raised: %s", exc)
            print(f"[Orchestrator] FlashcardAgent error (non-fatal): {exc}")

        video_result: dict = {}
        try:
            video_result = vid_future.result()
        except Exception as exc:
            log.error("VideoAgent raised: %s", exc)
            print(f"[Orchestrator] VideoAgent error (non-fatal): {exc}")

        # -------------------------------------------------------- #
        # PHASE 3 — PDF export (sequential, after phase 2)         #
        # -------------------------------------------------------- #
        _banner("Phase 3 — PDFAgent")

        notes_pdf_result = self.pdf_agent.run(input_md_path=notes_path)

        flashcards_pdf_result: dict = {}
        if flashcard_result.get("flashcards_path"):
            flashcards_pdf_result = self.pdf_agent.run(
                input_md_path=flashcard_result["flashcards_path"]
            )
        else:
            print("[Orchestrator] Skipping flashcards PDF — no flashcard output.")

        # -------------------------------------------------------- #
        # Summary                                                   #
        # -------------------------------------------------------- #
        summary: dict[str, Any] = {
            "topic": topic,
            "notes_md": notes_result,
            "flashcards_md": flashcard_result,
            "video": video_result,
            "notes_pdf": notes_pdf_result,
            "flashcards_pdf": flashcards_pdf_result,
        }

        _banner("Pipeline complete")
        for key, val in summary.items():
            status = val.get("status", "—") if isinstance(val, dict) else val
            print(f"  {key:<20} {status}")
        print()

        return summary


def _banner(title: str, detail: str = "") -> None:
    """Print a formatted section header to stdout."""
    suffix = f"  |  {detail}" if detail else ""
    print(f"\n{'=' * 60}")
    print(f"  {title}{suffix}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    import os

    anthropic_api_key = os.environ.get("CLAUDE_API_KEY") or os.environ.get(
        "ANTHROPIC_API_KEY"
    )
    if not anthropic_api_key:
        raise SystemExit(
            "Set CLAUDE_API_KEY (or ANTHROPIC_API_KEY) in your .env file."
        )

    orchestrator = StudyOrchestrator(
        anthropic_api_key=anthropic_api_key,
        openai_api_key=os.environ["OPENAI_API_KEY"],
    )
    result = orchestrator.run(topic="Convolutional Neural Networks (CNNs) in Deep Learning")
    print(result)
