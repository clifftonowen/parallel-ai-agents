"""Turning (slide, narration) pairs into one MP4, two ways.

This stage is 75 to 81% of a full pipeline run in every profiling result on
disk, and until now it was one single-threaded pass over the whole timeline.
Everything upstream of it, the part the project has spent its effort
parallelising, is the other fifth. Amdahl's law does the rest.

The two paths here exist to be compared, not because one is a fallback:

``assemble_sequential``
    What the pipeline has always done. MoviePy builds the whole timeline in
    memory and hands one long encode to ffmpeg.

``assemble_parallel``
    One ffmpeg per slide, all in flight at once, then a concat with stream
    copy. Slides are independent, so nothing about the work forces it to be
    serial.

**Why a thread pool and not multiprocessing.** The encoding is already in
separate OS processes: ffmpeg is not Python and does not hold the GIL. Python's
only job is to start each one and wait, which is pure IO waiting, so threads are
the right tool and `multiprocessing` would add process spawn cost to buy
nothing. That distinction is the point of the exercise. "True parallelism"
comes from where the work runs, not from which Python module launched it, and a
thread pool reaches it here while an event loop over LLM calls never could.

The concat step re-encodes nothing (``-c copy``), so it is bounded by disk
rather than CPU. That is why every segment must be encoded with identical
settings: the concat demuxer refuses to join streams whose parameters differ.
"""

from __future__ import annotations

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor

__all__ = ["assemble_sequential", "assemble_parallel", "ffmpeg_path", "probe_duration"]

#: Frame rate for the output. Matches what the MoviePy path has always written,
#: so the two can be compared without the frame rate being a variable.
FPS = 24

#: Encoder settings shared by every segment. Identical across segments is not a
#: style choice: the concat demuxer joins streams without re-encoding and will
#: refuse a list whose parameters disagree.
_VCODEC = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS)]
_ACODEC = ["-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2"]


def ffmpeg_path() -> str:
    """The ffmpeg binary, preferring whatever MoviePy already resolved.

    imageio-ffmpeg ships one, so a machine that can run the existing pipeline
    can run this even with nothing on PATH.
    """
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def probe_duration(path: str) -> float:
    """Container duration in seconds, read back from the file itself.

    Used by the tests to compare the two paths. Reads the container rather than
    trusting what we asked for, because "the encoder was told 24fps" and "the
    file is the right length" are different claims.
    """
    out = subprocess.run(
        [ffmpeg_path(), "-hide_banner", "-i", path],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stderr
    for line in out.splitlines():
        if "Duration:" in line:
            stamp = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = stamp.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    raise ValueError(f"no duration in ffmpeg output for {path}")


# ── the path the pipeline has always used ────────────────────────────────────

def assemble_sequential(
    frame_paths: list[str], audio_paths: list[str], output_path: str
) -> str:
    """One MoviePy timeline, one encode. The original behaviour, unchanged."""
    from moviepy import AudioFileClip, ImageClip, concatenate_videoclips

    clips = []
    for frame, audio in zip(frame_paths, audio_paths):
        audio_clip = AudioFileClip(audio)
        clips.append(
            ImageClip(frame).with_duration(audio_clip.duration).with_audio(audio_clip)
        )
    final = concatenate_videoclips(clips, method="compose")
    final.write_videofile(
        output_path, fps=FPS, codec="libx264", audio_codec="aac", logger=None
    )
    return output_path


# ── one process per slide ────────────────────────────────────────────────────

def _encode_segment(args: tuple[str, str, str, int | None]) -> str:
    """Encode one slide against its narration. Runs in a worker thread.

    The length is set explicitly with `-t`, from the narration's own duration,
    rather than left to `-shortest`.

    `-shortest` was the obvious choice and it is wrong here. With `-loop 1` the
    image input never ends, and `-shortest` stops only after the in-flight
    packet, which overran by about 2.9 seconds per segment. Worse, it overran
    by a *different* amount on each run, so the same inputs produced videos of
    different lengths. For a slideshow that means every slide after the first
    drifts out of step with what is being said about it.
    """
    frame, audio, dest, threads = args
    duration = probe_duration(audio)
    cmd = [
        ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y",
        "-loop", "1", "-i", frame,
        "-i", audio,
        *_VCODEC, *_ACODEC,
        "-t", f"{duration:.3f}",
    ]
    if threads is not None:
        cmd += ["-threads", str(threads)]
    cmd.append(dest)

    proc = subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(
            f"segment encode failed for {os.path.basename(frame)}: "
            f"{(proc.stderr or '').strip()[:300]}"
        )
    return dest


def assemble_parallel(
    frame_paths: list[str],
    audio_paths: list[str],
    output_path: str,
    workers: int | None = None,
    threads_per_segment: int | None = None,
) -> str:
    """Encode every slide at once, then join without re-encoding.

    Args:
        workers: how many ffmpeg processes to keep in flight. Defaults to one
            per slide, capped at the CPU count. Each ffmpeg is itself threaded,
            so more workers than cores oversubscribes and the width sweep is
            what shows where that starts to cost.
        threads_per_segment: ``-threads`` for each ffmpeg. None leaves x264 to
            decide, which is the sensible default but means workers and
            internal threads multiply.
    """
    if len(frame_paths) != len(audio_paths):
        raise ValueError(
            f"{len(frame_paths)} slides against {len(audio_paths)} narrations; "
            "they pair up one to one"
        )
    if not frame_paths:
        raise ValueError("nothing to assemble")

    work_dir = os.path.join(os.path.dirname(output_path) or ".", "_segments")
    os.makedirs(work_dir, exist_ok=True)

    jobs = [
        (frame, audio, os.path.join(work_dir, f"seg_{i:03d}.mp4"), threads_per_segment)
        for i, (frame, audio) in enumerate(zip(frame_paths, audio_paths))
    ]
    width = workers or min(len(jobs), os.cpu_count() or 1)

    # Threads, not processes: the encoders are already separate OS processes and
    # this pool only starts them and waits. See the note at the top.
    with ThreadPoolExecutor(max_workers=width) as pool:
        # list() rather than as_completed: segments must stay in slide order,
        # and any exception surfaces here rather than being swallowed.
        segments = list(pool.map(_encode_segment, jobs))

    # The concat demuxer wants a file listing the parts. Paths are quoted and
    # single quotes escaped, because a run directory can contain anything.
    list_path = os.path.join(work_dir, "segments.txt")
    with open(list_path, "w", encoding="utf-8") as fh:
        for seg in segments:
            fh.write(f"file '{os.path.abspath(seg)}'\n".replace("\\", "/"))

    proc = subprocess.run(
        [
            ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", list_path,
            "-c", "copy",
            output_path,
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"concat failed: {(proc.stderr or '').strip()[:300]}")
    return output_path
