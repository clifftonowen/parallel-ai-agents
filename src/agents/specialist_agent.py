import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any
from .run_context import notes_system_block, split_notes_and_timing
from .base_agent import AbstractStudyAgent, TOOL_DEFINITIONS

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Phase 1 — NotesAgent
# ---------------------------------------------------------------------------

class NotesAgent(AbstractStudyAgent):
    """Generates structured Markdown notes (notes.md) + timing.json sidecar.

    Equipped with web_search and image_search tools so the model can verify
    facts and embed relevant diagram URLs directly in the output.
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        api_key: str | None = None,
    ) -> None:
        super().__init__(model=model, api_key=api_key)
        self.tools.append(TOOL_DEFINITIONS["web_search"])
        self.tools.append(TOOL_DEFINITIONS["image_search"])

    def build_prompt(self, topic: str) -> str:
        """Return the notes-generation prompt for the given topic.

        Args:
            topic: The subject to write notes about.

        Returns:
            A fully formatted prompt string.
        """
        return (
            f'Write comprehensive study notes on: "{topic}".\n\n'
            "INSTRUCTIONS — follow all steps in order:\n\n"
            "1. WEB SEARCH (strongly preferred): Call web_search at least twice "
            "before writing. If the first query returns no results, retry with a "
            "broader query. Ground every major concept in something you found.\n\n"
            "2. IMAGE EMBEDDING: For every ## section heading, call image_search "
            "and embed the best result immediately below the heading:\n"
            "   ![description](url)\n"
            "   *Caption: one-line description.*\n"
            "If image_search fails or returns no results, skip the image for that "
            "section and continue — do NOT stop generating notes.\n\n"
            "3. FALLBACK: If ALL web_search calls fail or return errors, write the "
            "notes from your internal knowledge. Still produce complete notes — "
            "do not output any error messages or refuse to generate content.\n\n"
            "FORMAT REQUIREMENTS:\n"
            "- Use ## headers for each major concept (required)\n"
            "- Bullet-point key definitions and properties under each header\n"
            "- 1-2 concrete examples per section, labelled **Example:**\n"
            "- 400-700 words total, Markdown only, no preamble before the first header\n\n"
            "AFTER your Markdown notes, on its own line write exactly:\n"
            "---TIMING---\n"
            "Then write a JSON array, one object per ## section:\n"
            '[{"section": "heading without ##", "narration": "1-2 sentence summary", '
            '"estimated_seconds": <int 20-60>}]\n'
            "Return ONLY the JSON array after the separator — no code fences, no explanation.\n"
        )

    def run(self, output_dir: str | None = None, **kwargs: Any) -> dict:
        """Generate notes, save notes.md + timing.json sidecar.

        Keyword Args:
            topic (str):        The subject to generate notes about.
            output_dir (str):   Absolute path to the run's output directory.
                                Both output files are written flat into this
                                directory as ``notes.md`` and ``timing.json``.
                                Falls back to ``output/`` at the project root
                                when None.

        Returns:
            ``{"status": "ok", "output": <notes content>, "md_path": str,
               "timing_path": str}``
        """
        topic: str = kwargs["topic"]

        if output_dir is None:
            _base = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            output_dir = os.path.join(_base, "output")
        os.makedirs(output_dir, exist_ok=True)

        t0 = time.monotonic()
        started_ts = datetime.now(timezone.utc).isoformat()

        content = self._call_api(self.build_prompt(topic), use_tools=True)

        duration = round(time.monotonic() - t0, 3)
        finished_ts = datetime.now(timezone.utc).isoformat()

        result: dict = {"status": "ok", "output": content, "md_path": "", "timing_path": ""}

        if not self.validate_output(result):
            log.error(
                "NotesAgent validate_output FAILED.\n"
                "  has '## ': %s\n"
                "  word count: %d\n"
                "  first 300 chars: %r",
                "## " in content,
                len(content.split()),
                content[:300],
            )
            return {"status": "error", "output": content, "md_path": "", "timing_path": ""}

        # Attempt to extract timing data from the combined output (saves a second LLM call).
        # build_prompt instructs Claude to append ---TIMING--- then a JSON array.
        content, sections = split_notes_and_timing(content)
        if sections:
            log.info("[Notes] Timing extracted inline — skipping second LLM call.")

        if not sections:
            # Fallback: dedicated second LLM call (original behaviour).
            # VideoAgent._build_narration_scripts and _generate_html_slides both
            # iterate over this list and key into "section", "narration",
            # "estimated_seconds" — the flat metadata dict would cause a KeyError.
            timing_prompt = (
                "Given these study notes, return a JSON array where each element "
                "represents one ## section. Each object must have exactly these keys:\n"
                '  "section": the heading text (without the ## prefix),\n'
                '  "narration": 1-2 sentence summary of what to say about this section,\n'
                '  "estimated_seconds": integer seconds to speak about it '
                "(typically 20-60 per section).\n\n"
                "Return ONLY valid JSON — no markdown fences, no explanation.\n\n"
                f"NOTES:\n{content}"
            )
            timing_raw = self._call_api(timing_prompt, use_tools=False).strip()
            if timing_raw.startswith("```"):
                lines = timing_raw.split("\n", 1)
                timing_raw = lines[1].rsplit("```", 1)[0].strip() if len(lines) > 1 else ""
            try:
                sections = json.loads(timing_raw)
            except json.JSONDecodeError:
                sections = []

        md_path = self._save_output(content, "notes.md", output_dir=output_dir)
        timing_path = self._save_output(
            json.dumps(
                {
                    "agent_id": self.agent_id,
                    "topic": topic,
                    "started_at": started_ts,
                    "finished_at": finished_ts,
                    "duration_seconds": duration,
                    "sections": sections,
                },
                indent=2,
            ),
            "timing.json",
            output_dir=output_dir,
        )

        result["md_path"] = md_path
        result["timing_path"] = timing_path
        result["duration_s"] = duration
        result["started_at"] = started_ts
        result["finished_at"] = finished_ts
        print(f"[Notes] Saved:  {md_path}")
        print(f"[Notes] Timing: {timing_path}")
        return result

    def validate_output(self, output: dict) -> bool:
        """Return True if the notes content passes structural and length checks.

        Args:
            output: The dict from run() — inspects output["output"].
        """
        if output.get("status") == "error":
            return False
        content: str = output.get("output", "")
        if not isinstance(content, str) or not content.strip():
            return False
        if "## " not in content:
            return False
        return 200 <= len(content.split()) <= 2000


# ---------------------------------------------------------------------------
# Phase 2a — FlashcardAgent
# ---------------------------------------------------------------------------

class FlashcardAgent(AbstractStudyAgent):
    """Transforms notes.md into Obsidian-compatible spaced-repetition flashcards.

    No tools needed — the agent reads the provided notes and rephrases them
    into structured active-recall cards without consulting external sources.
    """

    def __init__(
        self,
        model: str = "claude-haiku-4-5-20251001",
        api_key: str | None = None,
    ) -> None:
        super().__init__(model=model, api_key=api_key)

    def build_prompt(self, notes_content: str) -> str:
        """Return the flashcard-generation prompt.

        Instructs the model to produce 8-12 Obsidian-style flashcards with a
        prescribed mix of definition, application, and distinction cards.

        Args:
            notes_content: Full text of notes.md from Phase 1.

        Returns:
            A fully formatted prompt string.
        """
        return (
            "Read the study notes in the system prompt carefully, then generate "
            "between 12 and 15 flashcards.\n\n"
            "Use this exact Markdown format for every card — no deviations:\n\n"
            "## {{question}} #flashcard\n\n"
            "{{answer — see ANSWER REQUIREMENTS below}}\n\n"
            "---\n\n"
            "ANSWER REQUIREMENTS — all four rules apply to every single card:\n"
            "  1. Minimum 3 sentences per answer — no exceptions.\n"
            "  2. Every answer must include EITHER a concrete real-world example "
            "OR an explicit comparison to a related concept.\n"
            "  3. End every answer with a sentence starting exactly 'Why it matters:' "
            "that explains the practical relevance of the concept.\n"
            "  4. Every answer must be derivable directly from the notes above "
            "— introduce no new information.\n\n"
            "Card type mix (all three types required, totalling 12-15):\n"
            "  • 4-5 definition cards    — question form: 'What is X?'\n"
            "  • 4-5 application cards   — question form: "
            "'How does X work in the context of Y?'\n"
            "  • 3-5 distinction cards   — question form: "
            "'What is the difference between X and Y?'\n\n"
            "Additional constraints:\n"
            "  • Do not copy sentences verbatim from the notes — rephrase in "
            "your own words.\n"
            "  • Return ONLY the Markdown flashcard content — no preamble, "
            "no closing remarks, nothing else.\n"
        )

    def run(self, notes_content: str, output_dir: str = "output") -> dict:
        """Generate flashcards from notes and save them to flashcards.md.

        Args:
            notes_content: Full text of notes.md from Phase 1.
            output_dir:    Subdirectory prefix passed to _save_output.

        Returns:
            ``{"status": "ok", "flashcards_path": str, "flashcards_content": str}``
        """
        t0 = time.monotonic()
        started_at = datetime.now(timezone.utc).isoformat()
        prompt = self.build_prompt(notes_content)
        # Notes go in the cached system block rather than the user turn:
        # every agent downstream of Phase 1 sends the same notes, so they
        # share one cache entry instead of each re-sending thousands of
        # tokens.
        response = self._call_api(
            prompt, system=notes_system_block(notes_content), use_tools=False
        )
        duration_s = round(time.monotonic() - t0, 3)
        finished_at = datetime.now(timezone.utc).isoformat()
        # Write into the run directory as flashcards.md — api_server.py maps
        # "flashcards_md" -> "flashcards.md" and serves it from run_dir, so a
        # global output/flashcards/<uuid>.md path is unreachable by the frontend.
        flashcards_path = self._save_output(
            response, "flashcards.md", output_dir=output_dir
        )
        print(f"[Flashcards] Saved: {flashcards_path}")
        return {
            "status": "ok",
            "flashcards_path": flashcards_path,
            "flashcards_content": response,
            "duration_s": duration_s,
            "started_at": started_at,
            "finished_at": finished_at,
        }

    def validate_output(self, output: dict) -> bool:
        """Return True if the flashcard content meets structural requirements.

        Passes only when the content contains at least 6 H2 headers, 6
        #flashcard tags, and 6 horizontal-rule separators — a proxy for
        having produced at least 6 well-formed cards.

        Args:
            output: The dict from run() — inspects output["flashcards_content"].
        """
        content: str = output.get("flashcards_content", "")
        if not isinstance(content, str) or not content.strip():
            return False
        return (
            content.count("## ") >= 6
            and content.count("#flashcard") >= 6
            and content.count("---") >= 6
        )


# ---------------------------------------------------------------------------
# Back-compat re-exports
# ---------------------------------------------------------------------------
# VideoAgent and PDFAgent moved to their own modules, but all three
# orchestrators (and src/agents/__init__.py) import them from here. Re-exported
# so the split is invisible to callers.
from .pdf_agent import PDFAgent  # noqa: E402,F401
from .video_agent import VideoAgent  # noqa: E402,F401
