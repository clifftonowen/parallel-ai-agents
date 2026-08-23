"""
adk_agents.py
-------------
ADK-specific agent wrappers for the study material generation pipeline.

All existing specialist_agent.py agents are preserved unchanged. This module
layers Google ADK (ParallelAgent / SequentialAgent / LlmAgent) on top of the
existing architecture without replacing it.

Model: AnthropicLlm(model="claude-sonnet-4-6") — uses ANTHROPIC_API_KEY from
environment. No Vertex AI or Gemini credentials required.

Tool parallelism: ADK's LlmAgent dispatches multiple tool_use blocks from a
single model turn concurrently via asyncio.gather internally. This fixes the
serial tool dispatch loop in base_agent.py._call_api for free.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import AsyncGenerator

from google.adk.agents import LlmAgent, BaseAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.anthropic_llm import AnthropicLlm
from google.adk.events import Event
from google.genai import types

from .adk_tools import WEB_SEARCH_TOOL, IMAGE_SEARCH_TOOL
from .specialist_agent import NotesAgent, VideoAgent, PDFAgent

log = logging.getLogger(__name__)

_CLAUDE_MODEL = "claude-sonnet-4-6"
_CLAUDE_HAIKU = "claude-haiku-4-5-20251001"

# ---------------------------------------------------------------------------
# Prompt fragments reused across factories
# ---------------------------------------------------------------------------

_NOTES_PROMPT_TIMING_SUFFIX = (
    "\n\nAFTER your Markdown notes, on its own line write exactly:\n"
    "---TIMING---\n"
    "Then write a JSON array, one object per ## section:\n"
    '[{"section": "heading without ##", "narration": "1-2 sentence summary", '
    '"estimated_seconds": <int 20-60>}]\n'
    "Return ONLY the JSON array after the separator — no code fences, no explanation.\n"
)

_FLASHCARD_PREFIX = (
    "Read the following study notes carefully, then generate between "
    "12 and 15 flashcards.\n\nNOTES:\n"
)

_FLASHCARD_SUFFIX = (
    "\n\nUse this exact Markdown format for every card:\n\n"
    "## {question} #flashcard\n\n"
    "{answer}\n\n"
    "---\n\n"
    "ANSWER REQUIREMENTS — all four rules apply to every single card:\n"
    "  1. Minimum 3 sentences per answer.\n"
    "  2. Every answer must include a concrete real-world example OR a comparison.\n"
    "  3. End every answer with 'Why it matters:' explaining practical relevance.\n"
    "  4. Every answer must be derivable directly from the notes — no new information.\n\n"
    "Card type mix (totalling 12-15):\n"
    "  4-5 definition cards — 'What is X?'\n"
    "  4-5 application cards — 'How does X work in context Y?'\n"
    "  3-5 distinction cards — 'What is the difference between X and Y?'\n\n"
    "Return ONLY the Markdown flashcard content — no preamble, no closing remarks.\n"
)


# ---------------------------------------------------------------------------
# Phase 1 helpers
# ---------------------------------------------------------------------------

def make_notes_agent(topic: str) -> LlmAgent:
    """Create an ADK LlmAgent that generates notes + inline timing JSON.

    The agent uses web_search and image_search tools. ADK dispatches
    multiple tool calls from one model turn concurrently via asyncio.gather,
    eliminating the serial tool loop present in base_agent._call_api.

    Args:
        topic: The subject to generate study materials about.

    Returns:
        A configured LlmAgent ready to be used in a SequentialAgent.
    """
    # Reuse NotesAgent.build_prompt for consistent prompt quality,
    # then append the timing merge suffix.
    _stub = NotesAgent.__new__(NotesAgent)
    base_prompt = NotesAgent.build_prompt(_stub, topic)

    return LlmAgent(
        name="notes_agent",
        model=AnthropicLlm(model=_CLAUDE_MODEL),
        instruction=base_prompt + _NOTES_PROMPT_TIMING_SUFFIX,
        tools=[WEB_SEARCH_TOOL, IMAGE_SEARCH_TOOL],
        output_key="notes_raw",
        description="Generates structured Markdown study notes with web research.",
    )


class NotesPostProcessAgent(BaseAgent):
    """Post-process the LlmAgent notes output: split timing, save files.

    Reads session.state["notes_raw"], splits on ---TIMING---, writes
    notes_content and timing_json back to session state, and saves
    notes.md + timing.json to run_dir. Falls back to a second LLM call
    if the separator is absent or the JSON is malformed.
    """

    model_config = {"arbitrary_types_allowed": True}

    def __init__(self, anthropic_api_key: str | None = None) -> None:
        super().__init__(name="notes_post_process")
        self._anthropic_api_key = anthropic_api_key

    async def _run_async_impl(
        self, ctx  # google.adk.agents.invocation_context.InvocationContext
    ) -> AsyncGenerator[Event, None]:
        raw: str = ctx.session.state.get("notes_raw", "")
        run_dir: str = ctx.session.state["run_dir"]
        topic: str = ctx.session.state["topic"]

        sections: list = []
        notes_md: str = raw

        if "---TIMING---" in raw:
            notes_part, timing_raw = raw.split("---TIMING---", 1)
            notes_md = notes_part.strip()
            timing_raw = (
                timing_raw.strip()
                .lstrip("```json").lstrip("```")
                .rstrip("```").strip()
            )
            try:
                sections = json.loads(timing_raw)
                log.info("[NotesPostProcess] Timing extracted inline.")
            except json.JSONDecodeError:
                log.warning("[NotesPostProcess] Inline timing JSON malformed — fallback.")

        if not sections:
            # Fallback: second LLM call via the existing NotesAgent machinery.
            # Run in thread to avoid blocking ADK's event loop.
            _agent = NotesAgent(api_key=self._anthropic_api_key)
            timing_prompt = (
                "Given these study notes, return a JSON array where each element "
                "represents one ## section with keys: "
                '"section", "narration", "estimated_seconds". '
                "Return ONLY valid JSON — no markdown fences.\n\n"
                f"NOTES:\n{notes_md}"
            )
            timing_raw = (await asyncio.to_thread(
                _agent._call_api, timing_prompt, False
            )).strip()
            if timing_raw.startswith("```"):
                lines = timing_raw.split("\n", 1)
                timing_raw = lines[1].rsplit("```", 1)[0].strip() if len(lines) > 1 else ""
            try:
                sections = json.loads(timing_raw)
            except json.JSONDecodeError:
                sections = []
            log.info("[NotesPostProcess] Timing extracted via fallback LLM call.")

        # Save files to disk
        os.makedirs(run_dir, exist_ok=True)
        notes_path = os.path.join(run_dir, "notes.md")
        timing_path = os.path.join(run_dir, "timing.json")
        with open(notes_path, "w", encoding="utf-8") as f:
            f.write(notes_md)
        import datetime
        with open(timing_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "topic": topic,
                    "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "sections": sections,
                },
                f,
                indent=2,
            )

        # Publish to session state for downstream agents
        ctx.session.state["notes_content"] = notes_md
        ctx.session.state["timing_json"] = sections
        ctx.session.state["notes_md_path"] = notes_path

        log.info("[NotesPostProcess] Saved notes.md and timing.json to %s", run_dir)
        yield Event(
            author=self.name,
            content=types.Content(
                role="model",
                parts=[types.Part(text=f"Notes saved: {notes_path}")],
            ),
        )


# ---------------------------------------------------------------------------
# Phase 2a — Flashcard helpers
# ---------------------------------------------------------------------------

async def _inject_notes_into_flashcard(
    callback_context: CallbackContext,
) -> types.Content | None:
    """before_agent_callback: inject notes_content from session state into prompt."""
    notes = callback_context.state.get("notes_content", "")
    if not notes:
        log.warning("[FlashcardAgent] notes_content missing from session state.")
    return types.Content(
        role="user",
        parts=[types.Part(text=_FLASHCARD_PREFIX + notes + _FLASHCARD_SUFFIX)],
    )


async def _save_flashcard_after(callback_context: CallbackContext) -> None:
    """after_agent_callback: save flashcards_content to disk inside Phase 2.

    Runs while VideoADKAgent is still executing, eliminating the sequential
    FlashcardSaveAgent step that previously ran after Phase 2 completed.
    """
    content: str = callback_context.state.get("flashcards_content", "")
    run_dir: str = callback_context.state.get("run_dir", "")
    if not content or not run_dir:
        log.warning("[FlashcardAgent] flashcards_content or run_dir missing — skipping save.")
        callback_context.state["flashcards_md_path"] = ""
        return
    path = os.path.join(run_dir, "flashcards.md")
    await asyncio.to_thread(_write_file, path, content)
    callback_context.state["flashcards_md_path"] = path
    log.info("[FlashcardAgent] Saved flashcards.md to %s", path)


def _write_file(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def make_flashcard_agent() -> LlmAgent:
    """Create an ADK LlmAgent that generates Obsidian-compatible flashcards.

    Uses before_agent_callback to inject notes_content from session state
    at runtime (not at construction time, since notes don't exist yet).

    Returns:
        A configured LlmAgent ready for Phase 2 ParallelAgent.
    """
    return LlmAgent(
        name="flashcard_agent",
        model=AnthropicLlm(model=_CLAUDE_HAIKU),
        instruction="",  # overridden by before_agent_callback at runtime
        output_key="flashcards_content",
        description="Transforms study notes into spaced-repetition flashcards.",
        before_agent_callback=_inject_notes_into_flashcard,
        after_agent_callback=_save_flashcard_after,
    )


class FlashcardSaveAgent(BaseAgent):
    """Save flashcards_content from session state to flashcards.md on disk."""

    def __init__(self) -> None:
        super().__init__(name="flashcard_save")

    async def _run_async_impl(self, ctx) -> AsyncGenerator[Event, None]:
        content: str = ctx.session.state.get("flashcards_content", "")
        run_dir: str = ctx.session.state["run_dir"]

        if not content:
            log.warning("[FlashcardSave] flashcards_content is empty — skipping save.")
            ctx.session.state["flashcards_md_path"] = ""
            yield Event(
                author=self.name,
                content=types.Content(
                    role="model",
                    parts=[types.Part(text="Flashcards empty — skipped.")],
                ),
            )
            return

        path = os.path.join(run_dir, "flashcards.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        ctx.session.state["flashcards_md_path"] = path
        log.info("[FlashcardSave] Saved flashcards.md to %s", path)
        yield Event(
            author=self.name,
            content=types.Content(
                role="model",
                parts=[types.Part(text=f"Flashcards saved: {path}")],
            ),
        )


# ---------------------------------------------------------------------------
# Phase 2b — VideoAgent wrapper
# ---------------------------------------------------------------------------

class VideoADKAgent(BaseAgent):
    """ADK wrapper around VideoAgent.

    Runs VideoAgent.run() inside loop.run_in_executor to avoid blocking
    ADK's event loop. VideoAgent.run() internally uses the Stage A / B+C
    parallel ThreadPoolExecutor structure from specialist_agent.py.
    """

    model_config = {"arbitrary_types_allowed": True}

    def __init__(self, name: str = "video_agent") -> None:
        super().__init__(name=name)

    async def _run_async_impl(self, ctx) -> AsyncGenerator[Event, None]:
        notes_content: str = ctx.session.state.get("notes_content", "")
        timing_json: list = ctx.session.state.get("timing_json", [])
        run_dir: str = ctx.session.state["run_dir"]
        anthropic_key: str | None = ctx.session.state.get("anthropic_api_key")
        openai_key: str | None = ctx.session.state.get("openai_api_key")

        if not timing_json:
            log.error("[VideoADKAgent] timing_json is empty — cannot generate video.")
            ctx.session.state["video_path"] = ""
            ctx.session.state["pptx_path"] = ""
            yield Event(
                author=self.name,
                content=types.Content(
                    role="model",
                    parts=[types.Part(text="Video skipped — timing_json missing.")],
                ),
            )
            return

        worker = VideoAgent(api_key=anthropic_key, openai_api_key=openai_key)

        loop = asyncio.get_event_loop()
        result: dict = await loop.run_in_executor(
            None,
            lambda: worker.run(
                notes_content=notes_content,
                timing_json=timing_json,
                output_dir=run_dir,
            ),
        )

        ctx.session.state["video_path"] = result.get("video_path", "")
        ctx.session.state["pptx_path"] = result.get("pptx_path", "")
        ctx.session.state["video_benchmark"] = result.get("benchmark", {})

        status = result.get("status", "unknown")
        log.info("[VideoADKAgent] status=%s video=%s", status, result.get("video_path"))
        yield Event(
            author=self.name,
            content=types.Content(
                role="model",
                parts=[types.Part(text=f"Video [{status}]: {result.get('video_path', '')}")]
            ),
        )


# ---------------------------------------------------------------------------
# Phase 3 — PDF wrapper
# ---------------------------------------------------------------------------

class PDFADKAgent(BaseAgent):
    """ADK wrapper around PDFAgent.

    Reads the markdown file path from session state (md_state_key),
    runs PDFAgent.run() in an executor, and writes the pdf path to
    session state (pdf_state_key).

    Args:
        name:         Unique agent name within the pipeline.
        md_state_key: session.state key holding the .md file path.
        pdf_state_key: session.state key to write the .pdf path into.
    """

    model_config = {"arbitrary_types_allowed": True}

    def __init__(self, name: str, md_state_key: str, pdf_state_key: str) -> None:
        super().__init__(name=name)
        self._md_state_key = md_state_key
        self._pdf_state_key = pdf_state_key

    async def _run_async_impl(self, ctx) -> AsyncGenerator[Event, None]:
        md_path: str = ctx.session.state.get(self._md_state_key, "")

        if not md_path or not os.path.isfile(md_path):
            log.warning(
                "[%s] Markdown path '%s' not found — skipping PDF.", self.name, md_path
            )
            ctx.session.state[self._pdf_state_key] = ""
            yield Event(
                author=self.name,
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=f"PDF skipped — {md_path!r} not found.")],
                ),
            )
            return

        worker = PDFAgent()
        loop = asyncio.get_event_loop()
        result: dict = await loop.run_in_executor(
            None,
            lambda: worker.run(input_md_path=md_path),
        )

        pdf_path = result.get("pdf_path", "")
        ctx.session.state[self._pdf_state_key] = pdf_path
        log.info("[%s] PDF saved: %s", self.name, pdf_path)
        yield Event(
            author=self.name,
            content=types.Content(
                role="model",
                parts=[types.Part(text=f"PDF [{result.get('status')}]: {pdf_path}")],
            ),
        )
