"""
run_context.py

Small helpers the three orchestrators all need, kept in one place.

Each of these existed as two, three or four byte-identical copies. The slug in
particular had a fourth copy in api_server.py that independently re-derived it
for download filenames, so changing the rule in one place silently desynced the
ZIP name from the run directory it came from.

Everything here is pure except `bootstrap`, which is kept separate precisely so
that importing this module has no side effects.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime

__all__ = [
    "PDF_ENGINES",
    "slugify_topic",
    "make_run_dir",
    "banner",
    "load_timing_sections",
    "build_summary",
    "print_summary",
    "split_notes_and_timing",
    "strip_code_fence",
]

# Marker the notes agent emits between the prose and its timing sidecar.
TIMING_MARKER = "---TIMING---"

#: PDF engines pandoc can drive, in the order they are tried. Lives here rather
#: than in pdf_agent because the API server probes for them at startup, and
#: importing pdf_agent would pull anthropic and httpx into the web process for
#: the sake of a list of six strings.
PDF_ENGINES = [
    "xelatex", "lualatex", "pdflatex", "tectonic", "wkhtmltopdf", "weasyprint",
]

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_SLUG_MAX_LEN = 30


def slugify_topic(topic: str) -> str:
    """Filesystem-safe stem for a topic.

    Lowercased, runs of non-alphanumerics collapsed to underscores, trimmed to
    30 characters. Used for both run directory names and download filenames --
    they must agree, which is why there is only one of these now.
    """
    return _SLUG_RE.sub("_", topic.lower()).strip("_")[:_SLUG_MAX_LEN]


def make_run_dir(output_dir: str, topic: str, when: datetime | None = None) -> str:
    """Create and return `output_dir/{slug}_{YYYYMMDD_HHMMSS}/`.

    Every orchestrator call gets a self-contained folder so runs never mix.
    """
    stamp = (when or datetime.now()).strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(
        os.path.abspath(output_dir), f"{slugify_topic(topic)}_{stamp}"
    )
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def banner(title: str, detail: str = "") -> None:
    """Print a section header to stdout.

    Not decoration: api_server infers run progress by regex-matching these
    lines, so the wording is load-bearing.
    """
    suffix = f"  |  {detail}" if detail else ""
    print(f"\n{'=' * 60}")
    print(f"  {title}{suffix}")
    print(f"{'=' * 60}")


def load_timing_sections(timing_path: str) -> list:
    """Read the per-section timing sidecar that paces the video narration.

    Returns an empty list if the file is missing or malformed -- a bad sidecar
    should cost the video stage, not the whole run.
    """
    try:
        with open(timing_path, encoding="utf-8") as f:
            return json.load(f).get("sections", [])
    except (OSError, json.JSONDecodeError):
        return []


def split_notes_and_timing(raw: str) -> tuple[str, list]:
    """Split the notes agent's reply into markdown and parsed timing sections.

    The prompt asks the model to append the marker followed by a JSON array,
    which saves a second LLM call. Models routinely wrap that array in a
    ```json fence anyway, so the fence is stripped before parsing.

    Returns (notes_markdown, sections). `sections` is empty when the marker is
    absent or the JSON does not parse, which callers treat as "ask separately"
    rather than as a failure.
    """
    if TIMING_MARKER not in raw:
        return raw.strip(), []

    notes_part, _, timing_raw = raw.partition(TIMING_MARKER)
    timing_raw = strip_code_fence(timing_raw)
    try:
        sections = json.loads(timing_raw)
    except json.JSONDecodeError:
        sections = []
    if not isinstance(sections, list):
        sections = []
    return notes_part.strip(), sections



def strip_code_fence(text: str) -> str:
    """Remove one wrapping markdown code fence, if the model added one.

    Every prompt here says "return ONLY the HTML" or "no markdown fences", and
    models wrap the answer in ```lang ... ``` regardless. Where the payload is
    JSON that shows up as a parse failure, which is at least loud. Where it is
    HTML it is silent: the browser renders the stray ```html as body text
    before the doctype, so it appears in the corner of every rendered slide,
    and from there in every frame of every video the pipeline has produced.

    Only a fence that opens the string is removed, and only up to its matching
    close. A fence in the middle of the text is content -- notes about code
    legitimately contain them -- and is left alone.

    Written line-wise rather than with lstrip("```json"), which reads like a
    prefix strip but is a character-set strip: it removes any leading ` j s o n
    in any order, so a payload starting with "null" loses its first two
    characters. That version happened to work only because every payload it saw
    began with [ or {.
    """
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped

    # Drop the opening fence line, which may carry a language tag.
    _, newline, rest = stripped.partition("\n")
    if not newline:
        # A one-line string that is nothing but a fence.
        return ""

    closing = rest.rfind("```")
    if closing == -1:
        # Opened but never closed. Take what there is rather than returning
        # nothing: a truncated response is still worth saving.
        return rest.strip()
    return rest[:closing].strip()


def notes_system_block(notes_content: str) -> str:
    """The cacheable system prompt shared by every agent downstream of notes.

    Anthropic caches on an exact prefix match, so this must be byte-identical
    across agents for them to share one cache entry rather than each paying to
    create their own. That is the whole point: FlashcardAgent writes the entry,
    and VideoAgent's per-section narration and slide calls -- dozens of them,
    each of which previously repeated the full notes in its user prompt -- read
    it back.

    Measured caveat, so nobody "fixes" this later without the numbers:
    Anthropic's minimum cacheable prefix is model-dependent, and Haiku 4.5's is
    4096 tokens against Sonnet's 1024. FlashcardAgent and VideoAgent both
    default to Haiku, and typical notes here produce a ~1700-token block -- so
    on normal-length notes this **does not cache**, silently, with no error.
    Verified against the live API: no cache entry at 3918 tokens, cached from
    4655.

    It is still the right structure. It caches on Sonnet, it caches on Haiku
    once notes exceed roughly 13k characters, and it stops the narration loop
    repeating the full notes inside every per-section user prompt. But do not
    expect a cache hit on a short topic, and do not pad this block to reach the
    threshold -- that would buy a benchmark number with tokens rather than
    design.
    """
    return (
        "You are generating study materials from a fixed set of notes.\n"
        "The complete notes follow. Every instruction you receive in this "
        "session refers to them.\n\n"
        "----- BEGIN NOTES -----\n"
        f"{notes_content}\n"
        "----- END NOTES -----"
    )


def build_summary(topic: str, run_dir: str, **agent_results) -> dict:
    """Assemble the dict an orchestrator returns from its per-agent results.

    Key order matters only for the printed summary, not for consumers.
    """
    summary = {"topic": topic, "run_dir": run_dir}
    summary.update(agent_results)
    return summary


#: Summary keys that are measurements about the run rather than results from an
#: agent. They are carried in the summary for the benchmark harness and skipped
#: in the printed table, which lists what each agent produced.
_META_KEYS = frozenset({"phase_wall_s"})


def print_summary(summary: dict, title: str) -> None:
    """Print the closing summary block.

    A faithful extraction of what the orchestrators already printed, down to
    the column width and the trailing blank line: api_server infers progress by
    matching these lines, so "improving" the format would move the progress bar.
    The banner title stays per-orchestrator for the same reason.
    """
    banner(title)
    for key, val in summary.items():
        if key in _META_KEYS:
            continue
        status = val.get("status", "-") if isinstance(val, dict) else val
        print(f"  {key:<20} {status}")
    print()
