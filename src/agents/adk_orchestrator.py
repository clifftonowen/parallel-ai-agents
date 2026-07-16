"""
adk_orchestrator.py
-------------------
ADKStudyOrchestrator — Google ADK-based replacement for StudyOrchestrator.

Uses SequentialAgent + ParallelAgent composition to express the three-phase
pipeline declaratively. Drop-in interface: same __init__ and run(topic) as
StudyOrchestrator in orchestrator.py.

Pipeline structure:
    SequentialAgent("study_pipeline")
      ├─ SequentialAgent("phase1")
      │   ├─ NotesLlmAgent  (LlmAgent + AnthropicLlm + parallel tool dispatch)
      │   └─ NotesPostProcessAgent  (splits ---TIMING---, saves files)
      ├─ ParallelAgent("phase2")
      │   ├─ FlashcardLlmAgent  (LlmAgent + AnthropicLlm)
      │   └─ VideoADKAgent  (custom BaseAgent, runs VideoAgent in executor)
      ├─ FlashcardSaveAgent  (saves flashcards.md)
      └─ ParallelAgent("phase3")
          ├─ PDFADKAgent → notes.pdf
          └─ PDFADKAgent → flashcards.pdf

Key advantage over ThreadPoolExecutor-based StudyOrchestrator:
  ADK's LlmAgent dispatches multiple tool_use blocks from one model turn
  concurrently via asyncio.gather — the web_search and image_search calls
  that Claude issues during Notes generation now run in parallel.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from google.adk.agents import ParallelAgent, SequentialAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

from src.agents.adk_agents import (  # noqa: E402
    NotesPostProcessAgent,
    PDFADKAgent,
    VideoADKAgent,
    make_flashcard_agent,
    make_notes_agent,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

_APP_NAME = "study_generator"


class ADKStudyOrchestrator:
    """ADK-based three-phase study material generation pipeline.

    Drop-in replacement for StudyOrchestrator. Produces the same output
    artifacts in the same timestamped run directory.

    Args:
        anthropic_api_key: Anthropic API key (also read from ANTHROPIC_API_KEY env var).
        openai_api_key:    OpenAI API key for TTS (also read from OPENAI_API_KEY env var).
        output_dir:        Root directory for all generated artifacts.
    """

    def __init__(
        self,
        anthropic_api_key: str,
        openai_api_key: str,
        output_dir: str = "output",
    ) -> None:
        self.anthropic_api_key = anthropic_api_key
        self.openai_api_key = openai_api_key
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self._session_service = InMemorySessionService()

    def run(self, topic: str) -> dict[str, Any]:
        """Execute the full ADK study material generation pipeline.

        Args:
            topic: The subject to generate study materials about.

        Returns:
            Summary dict with keys: topic, run_dir, notes_md_path, video_path,
            pptx_path, notes_pdf_path, flashcards_pdf_path.
        """
        # Build timestamped run directory (same convention as StudyOrchestrator)
        topic_slug = re.sub(r"[^a-z0-9]+", "_", topic.lower()).strip("_")[:30]
        run_id = f"{topic_slug}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        run_dir = os.path.join(os.path.abspath(self.output_dir), run_id)
        os.makedirs(run_dir, exist_ok=True)
        log.info("ADK run directory: %s", run_dir)

        # Build pipeline — notes_agent is topic-specific so constructed here
        pipeline = SequentialAgent(
            name="study_pipeline",
            sub_agents=[
                # Phase 1: Notes generation + post-processing (sequential)
                SequentialAgent(
                    name="phase1",
                    sub_agents=[
                        make_notes_agent(topic),
                        NotesPostProcessAgent(anthropic_api_key=self.anthropic_api_key),
                    ],
                ),
                # Phase 2: Flashcards ‖ Video ‖ notes.pdf (parallel)
                # FlashcardAgent saves flashcards.md via after_agent_callback
                # while VideoADKAgent is still running — no sequential save step needed.
                # notes.pdf only depends on notes_md_path (written by Phase 1's
                # NotesPostProcessAgent), so it runs alongside flashcards/video
                # instead of waiting for Phase 2 to finish.
                ParallelAgent(
                    name="phase2",
                    sub_agents=[
                        make_flashcard_agent(),
                        VideoADKAgent(name="video_agent"),
                        PDFADKAgent(
                            name="notes_pdf_agent",
                            md_state_key="notes_md_path",
                            pdf_state_key="notes_pdf_path",
                        ),
                    ],
                ),
                # Phase 3: flashcards.pdf (needs flashcards_md_path from phase2)
                ParallelAgent(
                    name="phase3",
                    sub_agents=[
                        PDFADKAgent(
                            name="flashcards_pdf_agent",
                            md_state_key="flashcards_md_path",
                            pdf_state_key="flashcards_pdf_path",
                        ),
                    ],
                ),
            ],
        )

        runner = Runner(
            app_name=_APP_NAME,
            agent=pipeline,
            session_service=self._session_service,
        )

        # Create session with initial state
        session = self._session_service.create_session_sync(
            app_name=_APP_NAME,
            user_id="default",
            state={
                "topic": topic,
                "run_dir": run_dir,
                "anthropic_api_key": self.anthropic_api_key,
                "openai_api_key": self.openai_api_key,
            },
        )

        _banner("ADK Pipeline — starting", detail=f"topic: {topic!r}")

        # Drive the runner; collect events for downstream profiling/timing analysis
        _collected_events: list = []
        for event in runner.run(
            user_id="default",
            session_id=session.id,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text=f"Generate study materials for: {topic}")],
            ),
        ):
            _collected_events.append(event)
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if getattr(part, "text", None):
                        log.info("[%s] %s", event.author, part.text[:200])

        # Read final session state (get_session is async in ADK 1.27.1 — use sync variant)
        final_session = self._session_service.get_session_sync(
            app_name=_APP_NAME,
            user_id="default",
            session_id=session.id,
        )
        state: dict = final_session.state if final_session else {}

        summary: dict[str, Any] = {
            "topic": topic,
            "run_dir": run_dir,
            "notes_md_path":       state.get("notes_md_path", ""),
            "video_path":          state.get("video_path", ""),
            "pptx_path":           state.get("pptx_path", ""),
            "notes_pdf_path":      state.get("notes_pdf_path", ""),
            "flashcards_pdf_path": state.get("flashcards_pdf_path", ""),
            "video_benchmark":     state.get("video_benchmark", {}),
            "_adk_events":         _collected_events,
        }

        _banner("ADK Pipeline — complete")
        for key, val in summary.items():
            print(f"  {key:<25} {val}")
        print()

        return summary


def _banner(title: str, detail: str = "") -> None:
    suffix = f"  |  {detail}" if detail else ""
    print(f"\n{'=' * 60}")
    print(f"  {title}{suffix}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    orchestrator = ADKStudyOrchestrator(
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
        openai_api_key=os.environ["OPENAI_API_KEY"],
    )
    result = orchestrator.run(topic="machine learning basics")
    print(result)
