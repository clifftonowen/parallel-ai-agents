import json
import os
import subprocess
import time
from datetime import datetime, timezone
from typing import Any

from .base_agent import AbstractStudyAgent, TOOL_DEFINITIONS


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
            "Guidelines:\n"
            "- Use ## headers for each major concept\n"
            "- Bullet-point key definitions and properties under each header\n"
            "- 1-2 concrete examples per section, labelled **Example:**\n"
            "- Where helpful, embed a relevant diagram as ![description](url)\n"
            "- 400-700 words total, Markdown only, no preamble before the first header\n"
            "- Use web_search to verify facts and incorporate accurate, current information\n"
            "- Use image_search to find diagram or illustration URLs to embed\n"
        )

    def run(self, **kwargs: Any) -> dict:
        """Generate notes, save notes.md + timing.json sidecar.

        Keyword Args:
            topic (str): The subject to generate notes about.

        Returns:
            ``{"status": "ok", "output": <notes content>, "md_path": str,
               "timing_path": str}``
        """
        topic: str = kwargs["topic"]
        t0 = time.monotonic()
        started_ts = datetime.now(timezone.utc).isoformat()

        content = self._call_api(self.build_prompt(topic), use_tools=True)

        duration = round(time.monotonic() - t0, 3)
        finished_ts = datetime.now(timezone.utc).isoformat()

        result: dict = {"status": "ok", "output": content, "md_path": "", "timing_path": ""}

        if not self.validate_output(result):
            return {"status": "error", "output": content, "md_path": "", "timing_path": ""}

        # Second LLM call: extract per-section timing data for VideoAgent.
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
            timing_raw = timing_raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        try:
            sections: list = json.loads(timing_raw)
        except json.JSONDecodeError:
            sections = []

        md_path = self._save_output(content, f"notes/notes_{self.agent_id}.md")
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
            f"notes/notes_{self.agent_id}.json",
        )

        result["md_path"] = md_path
        result["timing_path"] = timing_path
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
        model: str = "claude-sonnet-4-6",
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
            "Read the following study notes carefully, then generate between "
            "8 and 12 flashcards.\n\n"
            "NOTES:\n"
            f"{notes_content}\n\n"
            "Use this exact Markdown format for every card — no deviations:\n\n"
            "## {{question}} #flashcard\n\n"
            "{{answer — 1 to 3 sentences, uses the same framing as the notes}}\n\n"
            "---\n\n"
            "Card type mix (all three types are required):\n"
            "  • 3-4 definition cards   — question form: 'What is X?'\n"
            "  • 3-4 application cards  — question form: "
            "'How does X work in the context of Y?'\n"
            "  • 2-3 distinction cards  — question form: "
            "'What is the difference between X and Y?'\n\n"
            "Constraints:\n"
            "  • Every answer must be derivable directly from the notes above "
            "— introduce no new information\n"
            "  • Do not copy sentences verbatim from the notes — rephrase in "
            "your own words\n"
            "  • Return ONLY the Markdown flashcard content — no preamble, "
            "no closing remarks, nothing else\n"
        )

    def run(self, notes_content: str, output_dir: str = "output") -> dict:
        """Generate flashcards from notes and save them to flashcards.md.

        Args:
            notes_content: Full text of notes.md from Phase 1.
            output_dir:    Subdirectory prefix passed to _save_output.

        Returns:
            ``{"status": "ok", "flashcards_path": str, "flashcards_content": str}``
        """
        prompt = self.build_prompt(notes_content)
        response = self._call_api(prompt, use_tools=False)
        flashcards_path = self._save_output(response, f"flashcards/flashcards_{self.agent_id}.md")
        print(f"[Flashcards] Saved: {flashcards_path}")
        return {
            "status": "ok",
            "flashcards_path": flashcards_path,
            "flashcards_content": response,
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
# Phase 2b — VideoAgent
# ---------------------------------------------------------------------------

class VideoAgent(AbstractStudyAgent):
    """Converts notes.md + section timing data into a narrated MP4 study video.

    Pipeline:
      1. _build_narration_scripts — expand timing entries into full narrations (LLM)
      2. _generate_html_slides    — LLM-generated HTML slides → Playwright PNG screenshots
      3. _generate_audio          — OpenAI TTS, one MP3 per narration
      4. _assemble_video          — MoviePy stitches frames + audio into MP4
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        api_key: str | None = None,
        openai_api_key: str | None = None,
    ) -> None:
        """Initialise the agent.

        Args:
            model:          Anthropic model ID.
            api_key:        Anthropic API key.
            openai_api_key: OpenAI API key for TTS (falls back to OPENAI_API_KEY env var).
        """
        super().__init__(model=model, api_key=api_key)
        self.openai_api_key = openai_api_key

    def build_prompt(self, topic: str) -> str:
        """No-op — VideoAgent builds all prompts inline in its private methods.

        Args:
            topic: Unused; present to satisfy the abstract interface.

        Returns:
            An empty string.
        """
        return ""

    def run(
        self,
        notes_content: str,
        timing_json: list,
        output_path: str = "output/study_video.mp4",
    ) -> dict:
        """Generate a narrated study video from notes and section timing data.

        Args:
            notes_content: Full text of notes.md from Phase 1.
            timing_json:   List of section dicts, each with keys:
                           "section", "narration", "estimated_seconds".
            output_path:   Destination path for the final MP4.
                           Relative paths are resolved from the project root.

        Returns:
            ``{"status": "ok", "video_path": str}``

        Raises:
            AssertionError: If frame count and narration count diverge after
                            slide generation.
        """
        if not os.path.isabs(output_path):
            base_dir = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            output_path = os.path.join(base_dir, output_path)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        narrations = self._build_narration_scripts(notes_content, timing_json)
        frame_paths = self._generate_html_slides(timing_json, notes_content)

        assert len(frame_paths) == len(narrations), (
            f"Frame/narration count mismatch: {len(frame_paths)} frames vs "
            f"{len(narrations)} narrations."
        )

        audio_paths = self._generate_audio(narrations)
        final_path = self._assemble_video(frame_paths, audio_paths, output_path)

        result: dict = {"status": "ok", "video_path": final_path}
        if not self.validate_output(result):
            return {"status": "error", "video_path": final_path}

        print(f"[Video] Saved to: {final_path}")
        return result

    def validate_output(self, output: dict) -> bool:
        """Return True if the MP4 file exists and is non-empty.

        Args:
            output: The dict from run() — inspects output["video_path"].
        """
        path: str = output.get("video_path", "")
        return (
            isinstance(path, str)
            and path.endswith(".mp4")
            and os.path.isfile(path)
            and os.path.getsize(path) > 0
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_narration_scripts(
        self, notes_content: str, timing_json: list
    ) -> list[str]:
        """Expand each timing entry into a full spoken narration via the LLM.

        One API call is made per timing entry; the full notes are passed as
        context so the model can ground each narration in the wider material.

        Args:
            notes_content: Full text of notes.md — context for every call.
            timing_json:   List of section dicts with keys "narration" and
                           "estimated_seconds".

        Returns:
            List of expanded narration strings, one per timing entry, in order.
        """
        narrations: list[str] = []
        for entry in timing_json:
            prompt = (
                f"Given this section from study notes: {entry['narration']}\n"
                f"Expand this into a spoken narration of approximately "
                f"{entry['estimated_seconds']} seconds.\n"
                f"Use the following full notes as context: {notes_content}\n"
                "Tone: clear, educational, like a university lecturer.\n"
                "Return ONLY the narration text, no labels or headers."
            )
            narrations.append(self._call_api(prompt, use_tools=False))
        return narrations

    def _generate_html_slides(
        self, timing_json: list, notes_content: str
    ) -> list[str]:
        """Generate one HTML slide per timing entry and screenshot to PNG.

        Each slide is generated by the LLM as a complete, self-contained HTML
        document, saved to output/slides/, then converted to a 1280×720 PNG
        via a Playwright headless-Chromium screenshot.

        Args:
            timing_json:   List of section dicts with keys "section" and
                           "narration".
            notes_content: Full notes text passed as LLM context.

        Returns:
            List of absolute PNG file paths, one per timing entry, in order.
        """
        png_paths: list[str] = []
        for i, entry in enumerate(timing_json):
            prompt = (
                f"Generate a single self-contained HTML slide for the concept: "
                f"{entry['section']}\n"
                "The slide should:\n"
                "- Have a clean white background, 1280x720px\n"
                "- Show the section title in large text at top\n"
                "- Show 3-5 bullet points summarising the key ideas from the "
                f"narration: {entry['narration']}\n"
                "- Use simple inline CSS only — no external libraries\n"
                "- Be a complete HTML document that renders as a slide when "
                "opened in a browser\n"
                "Return ONLY the HTML, no explanation."
            )
            html_content = self._call_api(prompt, use_tools=False)

            html_path = self._save_output(html_content, f"slides/slide_{i:02d}.html")
            png_path = os.path.join(
                os.path.dirname(html_path), f"slide_{i:02d}.png"
            )
            self._html_to_png(html_path, png_path)
            png_paths.append(png_path)

        return png_paths

    def _html_to_png(self, html_path: str, output_png: str) -> str:
        """Convert an HTML file to a 1280×720 PNG using Playwright headless Chromium.

        Runs the async screenshot coroutine synchronously via asyncio.run so
        this method can be called from ordinary synchronous code.

        Args:
            html_path:  Absolute path to the .html file.
            output_png: Destination path for the .png screenshot.

        Returns:
            output_png path after successful conversion.
        """
        import asyncio
        asyncio.run(self._screenshot(html_path, output_png))
        return output_png

    async def _screenshot(self, html_path: str, output_png: str) -> None:
        """Take a headless Chromium screenshot of an HTML file at 1280×720.

        Args:
            html_path:  Absolute path to the .html file (loaded as file:// URL).
            output_png: Destination path for the .png screenshot.
        """
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            page = await browser.new_page(
                viewport={"width": 1280, "height": 720}
            )
            await page.goto(f"file://{html_path}")
            await page.screenshot(path=output_png, full_page=False)
            await browser.close()

    def _generate_audio(self, narrations: list[str]) -> list[str]:
        """Generate one TTS MP3 per narration using OpenAI tts-1-hd (voice: coral).

        Args:
            narrations: List of narration strings, one per slide.

        Returns:
            List of MP3 file paths in the same order as narrations.

        Raises:
            RuntimeError: If the produced file count does not match narrations.
        """
        import openai

        base_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        audio_dir = os.path.join(base_dir, "output", "videos", "audio")
        os.makedirs(audio_dir, exist_ok=True)

        client = openai.OpenAI(api_key=self.openai_api_key)
        audio_paths: list[str] = []
        for i, narration in enumerate(narrations):
            out_path = os.path.join(audio_dir, f"audio_{i:02d}.mp3")
            with client.audio.speech.with_streaming_response.create(
                model="tts-1-hd",
                voice="coral",
                input=narration,
            ) as response:
                response.stream_to_file(out_path)
            audio_paths.append(out_path)

        if len(audio_paths) != len(narrations):
            raise RuntimeError(
                f"Expected {len(narrations)} audio files, got {len(audio_paths)}."
            )
        return audio_paths

    def _assemble_video(
        self,
        frame_paths: list[str],
        audio_paths: list[str],
        output_path: str,
    ) -> str:
        """Combine PNG frames and MP3 clips into a single MP4 via MoviePy.

        Each (frame, audio) pair becomes one clip whose on-screen duration
        matches the length of its audio clip.

        Args:
            frame_paths: PNG file paths, one per slide.
            audio_paths: MP3 file paths, one per slide.
            output_path: Destination MP4 path.

        Returns:
            output_path after successful export.
        """
        from moviepy import AudioFileClip, ImageClip, concatenate_videoclips

        clips = []
        for frame, audio in zip(frame_paths, audio_paths):
            audio_clip = AudioFileClip(audio)
            clips.append(
                ImageClip(frame)
                .with_duration(audio_clip.duration)
                .with_audio(audio_clip)
            )

        final = concatenate_videoclips(clips, method="compose")
        final.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac")
        return output_path


# ---------------------------------------------------------------------------
# Phase 3 — PDFAgent
# ---------------------------------------------------------------------------

class PDFAgent(AbstractStudyAgent):
    """Converts a Markdown file to PDF via pandoc + xelatex.

    Does not call the LLM; build_prompt is a no-op to satisfy the ABC.
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        api_key: str | None = None,
    ) -> None:
        super().__init__(model=model, api_key=api_key)

    def build_prompt(self, topic: str) -> str:
        """PDFAgent uses pandoc, not LLM prompts."""
        return ""

    def run(
        self,
        input_md_path: str,
        output_pdf_path: str | None = None,
    ) -> dict:
        """Render a Markdown file to PDF with pandoc + xelatex.

        Args:
            input_md_path:   Absolute path to the source .md file.
            output_pdf_path: Destination .pdf path. If None, derived by
                             replacing the .md extension with .pdf.

        Returns:
            ``{"status": "ok", "pdf_path": str}``

        Raises:
            RuntimeError: If pandoc is not installed or exits non-zero.
        """
        if output_pdf_path is None:
            output_pdf_path = os.path.splitext(input_md_path)[0] + ".pdf"

        try:
            subprocess.run(
                [
                    "pandoc", input_md_path,
                    "-o", output_pdf_path,
                    "--pdf-engine=xelatex",
                    "-V", "geometry:margin=1in",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            raise RuntimeError(
                "pandoc is not installed or not on PATH. "
                "Install it from https://pandoc.org/installing.html "
                "and install a LaTeX engine (e.g. MiKTeX or TeX Live) "
                "for the --pdf-engine=xelatex flag."
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"pandoc failed:\n{exc.stderr}") from exc

        result: dict = {"status": "ok", "pdf_path": output_pdf_path}
        if not self.validate_output(result):
            return {"status": "error", "pdf_path": output_pdf_path}

        print(f"[PDF] Saved to: {output_pdf_path}")
        return result

    def validate_output(self, output: dict) -> bool:
        """Return True if the PDF exists on disk and has non-zero size.

        Args:
            output: The dict from run() — inspects output["pdf_path"].
        """
        path: str = output.get("pdf_path", "")
        return (
            isinstance(path, str)
            and path.endswith(".pdf")
            and os.path.isfile(path)
            and os.path.getsize(path) > 0
        )
