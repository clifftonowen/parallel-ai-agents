"""
orchestrator.py
StudyOrchestrator — three-phase pipeline runner for the multi-agent
study material generator.

Phase 1 (sequential): NotesAgent → notes.md + timing.json sidecar
Phase 2 (parallel):   FlashcardAgent + VideoAgent consume notes.md;
                      PDFAgent renders notes.md → notes.pdf alongside them
                      (notes.pdf has no dependency on Phase 2's output, so
                      it runs concurrently instead of waiting for it).
Phase 3 (sequential): PDFAgent renders flashcards.md → flashcards.pdf,
                      once flashcards.md exists.
"""

import logging
import os
import sys
from concurrent.futures import Future, ThreadPoolExecutor
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


class StudyOrchestrator:
    """Three-phase pipeline that produces notes, flashcards, a video, and PDFs.

    Phase 1 (sequential): NotesAgent must complete before anything else starts.
    Phase 2 (parallel):   FlashcardAgent, VideoAgent, and the notes.pdf render
                          run simultaneously — notes.pdf only depends on
                          Phase 1's output, so it doesn't need to wait for
                          flashcards or video.
    Phase 3 (sequential): PDFAgent converts flashcards.md to PDF once
                          flashcards.md exists (skipped if flashcards failed).
    """

    def __init__(
        self,
        anthropic_api_key: str,
        openai_api_key: str,
        output_dir: str = OUTPUT_ROOT,
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
            ``topic``, ``run_dir``, ``notes_md``, ``flashcards_md``,
            ``video``, ``notes_pdf``, ``flashcards_pdf``.
            Each value is the raw agent result dict (or an empty dict if the
            agent was skipped due to an upstream error).

        Raises:
            RuntimeError: If NotesAgent fails or its output is invalid —
                          the pipeline cannot continue without notes.
        """
        # -------------------------------------------------------- #
        # PHASE 1 — Notes (sequential)                             #
        # -------------------------------------------------------- #
        banner("Phase 1 — NotesAgent", detail=f"topic: {topic!r}")

        # Build a timestamped run directory so every orchestrator call
        # produces a self-contained folder:
        #   output/{topic_slug}_{YYYYMMDD_HHMMSS}/
        run_dir = make_run_dir(self.output_dir, topic)
        log.info("Run directory: %s", run_dir)

        notes_result = self.notes_agent.run(topic=topic, output_dir=run_dir)

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

        timing_json: list = load_timing_sections(notes_result["timing_path"])

        # -------------------------------------------------------- #
        # PHASE 2 — Flashcards + Video + notes.pdf (parallel)      #
        # -------------------------------------------------------- #
        # notes.pdf only depends on notes.md (Phase 1's output), so it runs
        # alongside flashcards/video instead of waiting for them.
        banner(
            "Phase 2 — FlashcardAgent + VideoAgent + notes.pdf",
            detail="parallel",
        )

        try:
            with ThreadPoolExecutor(max_workers=3) as pool:
                fc_future: Future = pool.submit(
                    self.flashcard_agent.run,
                    notes_content=notes_content,
                    output_dir=run_dir,
                )
                vid_future: Future = pool.submit(
                    self.video_agent.run,
                    notes_content=notes_content,
                    timing_json=timing_json,
                    output_dir=run_dir,
                )
                npdf_future: Future = pool.submit(
                    self.pdf_agent.run,
                    input_md_path=notes_path,
                )
            # All three futures have completed (or failed) here — the
            # executor waited for them before exiting the with block.
        except KeyboardInterrupt:
            print("\n[Orchestrator] Interrupted during Phase 2 — stopping.")
            raise SystemExit(1)

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

        notes_pdf_result: dict = {}
        try:
            notes_pdf_result = npdf_future.result()
        except Exception as exc:
            log.error("PDFAgent (notes) raised: %s", exc)
            print(f"[Orchestrator] Notes PDF error (non-fatal): {exc}")

        # -------------------------------------------------------- #
        # PHASE 3 — flashcards.pdf (sequential, after flashcards)  #
        # -------------------------------------------------------- #
        banner("Phase 3 — PDFAgent (flashcards)")

        flashcards_pdf_result: dict = {}
        if flashcard_result.get("flashcards_path"):
            try:
                flashcards_pdf_result = self.pdf_agent.run(
                    input_md_path=flashcard_result["flashcards_path"],
                )
            except Exception as exc:
                log.error("PDFAgent (flashcards) raised: %s", exc)
                print(f"[Orchestrator] Flashcards PDF error (non-fatal): {exc}")
        else:
            print("[Orchestrator] Skipping flashcards PDF — no flashcard output.")

        # -------------------------------------------------------- #
        # Summary                                                   #
        # -------------------------------------------------------- #
        summary: dict[str, Any] = build_summary(
            topic, run_dir,
            notes_md=notes_result,
            flashcards_md=flashcard_result,
            video=video_result,
            notes_pdf=notes_pdf_result,
            flashcards_pdf=flashcards_pdf_result,
        )
        print_summary(summary, "Pipeline complete")

        return summary




if __name__ == "__main__":

    # Windows cp1252 terminals can't encode all Unicode chars the LLM may emit.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    orchestrator = StudyOrchestrator(
        anthropic_api_key=require_env("ANTHROPIC_API_KEY", "Claude pipeline"),
        openai_api_key=require_env("OPENAI_API_KEY", "TTS + embeddings"),
    )
    result = orchestrator.run(topic="Convolutional Neural Networks (CNNs) in Deep Learning")
    print(result)
