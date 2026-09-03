"""Tests for the two video assembly paths.

The parallel path exists to be faster, but speed is not what these check. A
video that is quicker to produce and drifts out of sync with its narration is
worth nothing, so the bar here is that the two paths produce the same film.

Anything that actually encodes is skipped when ffmpeg is missing, which is the
state in CI: requirements-dev.txt deliberately omits moviepy and the rest of
the media stack. The module itself imports nothing heavy at import time, so
collection works everywhere.
"""

import os
import shutil
import subprocess

import pytest

from src.agents import video_assembly as va

HAVE_FFMPEG = shutil.which("ffmpeg") is not None
needs_ffmpeg = pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg not on PATH")


class TestArgumentChecking:
    """Cheap, and they run everywhere including CI."""

    def test_mismatched_counts_are_refused(self):
        """One narration per slide. Zipping them silently would drop the tail
        and produce a video quietly missing its last section."""
        with pytest.raises(ValueError, match="one to one"):
            va.assemble_parallel(["a.png", "b.png"], ["a.mp3"], "out.mp4")

    def test_nothing_to_assemble_is_refused(self):
        with pytest.raises(ValueError, match="nothing to assemble"):
            va.assemble_parallel([], [], "out.mp4")


@pytest.fixture(scope="module")
def clip_source(tmp_path_factory):
    """A tiny three-slide deck, generated rather than committed.

    Real slides are 1280x720 PNGs and real narrations are tens of seconds, which
    would make this suite take minutes. The shapes are what matter.
    """
    if not HAVE_FFMPEG:
        pytest.skip("ffmpeg not on PATH")
    d = tmp_path_factory.mktemp("clips")
    frames, audios, durations = [], [], [1.0, 0.5, 1.5]
    for i, dur in enumerate(durations):
        png = str(d / f"slide_{i}.png")
        mp3 = str(d / f"audio_{i}.mp3")
        subprocess.run(
            [va.ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y",
             "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=0.1",
             "-frames:v", "1", png],
            check=True,
        )
        subprocess.run(
            [va.ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y",
             "-f", "lavfi", "-i", f"sine=frequency={300 + i * 100}:duration={dur}",
             mp3],
            check=True,
        )
        frames.append(png)
        audios.append(mp3)
    return frames, audios, sum(durations)


@needs_ffmpeg
class TestParallelOutput:
    def test_it_produces_a_playable_file(self, clip_source, tmp_path):
        frames, audios, _ = clip_source
        out = str(tmp_path / "out.mp4")
        va.assemble_parallel(frames, audios, out)
        assert os.path.isfile(out)
        assert os.path.getsize(out) > 0

    def test_the_length_is_the_sum_of_the_narrations(self, clip_source, tmp_path):
        """The failure this catches is the one that matters: a segment cut
        short or run long puts every later slide out of step with its audio."""
        frames, audios, expected = clip_source
        out = str(tmp_path / "out.mp4")
        va.assemble_parallel(frames, audios, out)
        assert va.probe_duration(out) == pytest.approx(expected, abs=0.35)

    def test_one_slide_still_works(self, clip_source, tmp_path):
        """Concat with a single entry is a different path from concat with
        several, and a one-section deck is a real thing the pipeline produces."""
        frames, audios, _ = clip_source
        out = str(tmp_path / "single.mp4")
        va.assemble_parallel(frames[:1], audios[:1], out)
        assert va.probe_duration(out) == pytest.approx(1.0, abs=0.35)

    def test_pool_width_does_not_change_the_result(self, clip_source, tmp_path):
        """Width is a performance knob. If it changed the output it would be a
        correctness knob, and the sweep would be measuring different films."""
        frames, audios, expected = clip_source
        lengths = []
        for width in (1, 3):
            out = str(tmp_path / f"w{width}.mp4")
            va.assemble_parallel(frames, audios, out, workers=width)
            lengths.append(va.probe_duration(out))
        assert lengths[0] == pytest.approx(lengths[1], abs=0.1)
        assert lengths[0] == pytest.approx(expected, abs=0.35)

    def test_a_missing_input_fails_loudly(self, clip_source, tmp_path):
        """Half a video is worse than an error, because the run would carry on
        and publish it."""
        frames, audios, _ = clip_source
        with pytest.raises(RuntimeError, match="segment encode failed"):
            va.assemble_parallel(
                frames[:2] + ["does-not-exist.png"], audios[:3],
                str(tmp_path / "broken.mp4"),
            )


@needs_ffmpeg
@pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="moviepy path needs the media stack"
)
class TestAgreementBetweenPaths:
    def test_both_paths_produce_the_same_length(self, clip_source, tmp_path):
        """The whole justification for the parallel path is that it is the same
        film, faster. This is that claim."""
        pytest.importorskip("moviepy", reason="moviepy not installed")
        frames, audios, _ = clip_source
        seq = str(tmp_path / "seq.mp4")
        par = str(tmp_path / "par.mp4")
        va.assemble_sequential(frames, audios, seq)
        va.assemble_parallel(frames, audios, par)
        assert va.probe_duration(par) == pytest.approx(va.probe_duration(seq), abs=0.35)
