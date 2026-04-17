import re
import os
from pptx import Presentation
from .base_agent import BaseAgent


# --- Notes Specialist ---
class NotesAgent(BaseAgent):
    """Generates structured markdown study notes saved as .txt."""

    def __init__(self, model: str = "claude-sonnet-4-6", api_key: str | None = None):
        super().__init__(model=model, api_key=api_key)

    def build_prompt(self, topic: str) -> str:
        return (
            f'Write structured study notes on: "{topic}".\n\n'
            "- Use ## headers for each major concept\n"
            "- Bullet-point definitions under each header\n"
            "- 1-2 concrete examples per section labelled 'Example:'\n"
            "- 400-700 words, Markdown only, no intro before the first header\n"
        )

    def run(self, topic: str) -> str:
        output = self._call_api(self.build_prompt(topic))
        if not self.validate_output(output):
            raise ValueError(f"Output failed validation for topic: '{topic}'")
        path = self._output_path("notes", f"notes_{self.agent_id}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"[Notes] Saved to: {path}")
        return output

    def validate_output(self, output: str) -> bool:
        if not isinstance(output, str) or not output.strip():
            return False
        if "## " not in output:
            return False
        return 300 <= len(output.split()) <= 900


# --- Flashcard Specialist ---
class FlashcardAgent(BaseAgent):
    """Generates Q&A flashcards saved as .pptx."""

    def __init__(self, model: str = "claude-sonnet-4-6", api_key: str | None = None):
        super().__init__(model=model, api_key=api_key)
        self.pairs: list[tuple[str, str]] = []

    def build_prompt(self, topic: str) -> str:
        return (
            f'Create 10 active recall flashcards for the topic: "{topic}".\n\n'
            "Output each card in exactly this format with a blank line between cards:\n"
            "Q: [question]\n"
            "A: [answer]\n\n"
            "No numbering, no extra text, no preamble — just the Q/A pairs.\n"
        )

    def run(self, topic: str) -> str:
        output = self._call_api(self.build_prompt(topic))
        if not self.validate_output(output):
            raise ValueError(f"Output failed validation for topic: '{topic}'")
        self.pairs = self._parse_pairs(output)
        path = self._output_path("flashcards", f"flashcards_{self.agent_id}.pptx")
        self._save_pptx(self.pairs, path)
        print(f"[Flashcards] Saved to: {path}")
        return path

    def validate_output(self, output: str) -> bool:
        if not isinstance(output, str) or not output.strip():
            return False
        return len(self._parse_pairs(output)) >= 3

    def _parse_pairs(self, text: str) -> list[tuple[str, str]]:
        pairs = re.findall(r'Q:\s*(.+?)\nA:\s*(.+?)(?=\nQ:|\Z)', text.strip(), re.DOTALL)
        return [(q.strip(), a.strip()) for q, a in pairs]

    def _save_pptx(self, pairs: list[tuple[str, str]], path: str) -> None:
        prs = Presentation()
        layout = prs.slide_layouts[1]
        for question, answer in pairs:
            slide = prs.slides.add_slide(layout)
            slide.shapes.title.text = question
            slide.placeholders[1].text = answer
        prs.save(path)


# --- Video Specialist ---
class VideoAgent(BaseAgent):
    """Converts Q/A pairs + narrations into a single MP4 study video."""

    def __init__(self, model: str = "claude-sonnet-4-6", api_key: str | None = None):
        super().__init__(model=model, api_key=api_key)

    def build_prompt(self, topic: str) -> str:
        raise NotImplementedError("VideoAgent does not use prompt-based generation.")

    def run(
        self,
        pairs: list[tuple[str, str]],
        narrations: list[str],
        output_path: str | None = None,
    ) -> str:
        """
        Run the 3-step pipeline: render frames → generate audio → assemble MP4.

        Args:
            pairs: List of (question, answer) tuples from FlashcardAgent.
            narrations: One narration string per pair for TTS.
            output_path: Destination MP4 path. Defaults to output/videos/video_{id}.mp4.

        Raises:
            ValueError: If len(pairs) != len(narrations).
        """
        if len(pairs) != len(narrations):
            raise ValueError(
                f"Mismatch: {len(pairs)} pairs but {len(narrations)} narrations provided."
            )
        if output_path is None:
            output_path = self._output_path("videos", f"video_{self.agent_id}.mp4")
        else:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        frame_paths = self._export_frames(pairs)
        audio_paths = self._generate_audio(narrations)
        final_path = self._assemble_video(frame_paths, audio_paths, output_path)
        print(f"[Video] Saved to: {final_path}")
        return final_path

    def validate_output(self, output: str) -> bool:
        """Return True if output path exists, is non-empty, and ends in .mp4."""
        return (
            isinstance(output, str)
            and output.endswith(".mp4")
            and os.path.isfile(output)
            and os.path.getsize(output) > 0
        )

    def _export_frames(self, pairs: list[tuple[str, str]]) -> list[str]:
        """
        Render each Q/A pair as a 1280x720 PNG using Pillow.

        Args:
            pairs: List of (question, answer) tuples.

        Returns:
            List of PNG file paths, one per pair.

        Raises:
            RuntimeError: If no frames were produced.
        """
        import textwrap
        from PIL import Image, ImageDraw, ImageFont

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        frames_dir = os.path.join(base_dir, "output", "videos", "frames")
        os.makedirs(frames_dir, exist_ok=True)

        try:
            font_q = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 40)
            font_a = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 32)
        except OSError:
            font_q = ImageFont.load_default()
            font_a = ImageFont.load_default()

        paths = []
        for i, (question, answer) in enumerate(pairs):
            img = Image.new("RGB", (1280, 720), color=(20, 20, 35))
            draw = ImageDraw.Draw(img)

            q_wrapped = textwrap.fill(f"Q: {question}", width=60)
            a_wrapped = textwrap.fill(f"A: {answer}", width=65)

            draw.text((80, 120), q_wrapped, fill=(255, 255, 255), font=font_q)
            draw.line([(80, 370), (1200, 370)], fill=(100, 100, 150), width=2)
            draw.text((80, 400), a_wrapped, fill=(180, 210, 255), font=font_a)

            path = os.path.join(frames_dir, f"frame_{i:02d}.png")
            img.save(path)
            paths.append(path)

        if not paths:
            raise RuntimeError("Frame export produced no images.")
        return paths

    def _generate_audio(self, narrations: list[str]) -> list[str]:
        """
        Generate one TTS MP3 per narration using OpenAI tts-1-hd (voice: coral).
        Reads OPENAI_API_KEY automatically from the environment.

        Args:
            narrations: List of narration strings.

        Returns:
            List of MP3 file paths in the same order as narrations.

        Raises:
            RuntimeError: If audio file count doesn't match narrations count.
        """
        import openai

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        audio_dir = os.path.join(base_dir, "output", "videos", "audio")
        os.makedirs(audio_dir, exist_ok=True)

        client = openai.OpenAI()  # auto-reads OPENAI_API_KEY from environment
        audio_paths = []

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
                f"Expected {len(narrations)} audio files, produced {len(audio_paths)}."
            )
        return audio_paths

    def _assemble_video(
        self,
        frame_paths: list[str],
        audio_paths: list[str],
        output_path: str,
    ) -> str:
        """
        Combine PNG frames and MP3 clips into a single MP4.

        Each (frame, audio) pair becomes one clip whose duration matches the audio.

        Args:
            frame_paths: PNG file paths, one per slide.
            audio_paths: MP3 file paths, one per slide.
            output_path: Destination MP4 path.

        Returns:
            The output_path string after successful export.
        """
        from moviepy import ImageClip, AudioFileClip, concatenate_videoclips

        clips = []
        for frame, audio in zip(frame_paths, audio_paths):
            audio_clip = AudioFileClip(audio)
            image_clip = (
                ImageClip(frame)
                .with_duration(audio_clip.duration)
                .with_audio(audio_clip)
            )
            clips.append(image_clip)

        final = concatenate_videoclips(clips, method="compose")
        final.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac")
        return output_path
