"""
pdf_agent.py

Phase 3 of the pipeline: renders Markdown to PDF via pandoc.

Split out of specialist_agent.py because the tool-resolution and image-screening
helpers belong with the agent that uses them, and nothing else does. They are
also the most testable code in the project -- pure functions over paths and
strings -- so grouping them in a module with no LLM dependency makes them easy
to cover.
"""

import logging
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from .base_agent import AbstractStudyAgent

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Phase 3 — PDFAgent
# ---------------------------------------------------------------------------

# Directories where pandoc / LaTeX engines commonly land on Windows but which
# are not always reflected in the *current process'* PATH (e.g. when a terminal
# was launched before the installer updated the environment). We search these
# explicitly so a stale PATH can never break PDF generation again.
# These are Windows install locations only. On Linux the env vars are unset,
# so this list is empty and _resolve_tool degrades to a plain shutil.which --
# meaning every binary MUST be on PATH there. Gated explicitly so it does not
# read as a working fallback on platforms where it does nothing.
_EXTRA_TOOL_DIRS: list[str] = []
if sys.platform == "win32":
    _EXTRA_TOOL_DIRS = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Pandoc"),
        os.path.join(os.environ.get("ProgramFiles", ""), "Pandoc"),
        os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Pandoc"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Links"),
        os.path.join(os.environ.get("USERPROFILE", ""), "scoop", "shims"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Tectonic"),
    ]
# Extra colon/semicolon-separated dirs, for images that install tools oddly.
_EXTRA_TOOL_DIRS += [
    p for p in os.environ.get("EXTRA_TOOL_DIRS", "").split(os.pathsep) if p.strip()
]

# LaTeX engines can only size a narrow set of image formats. A .webp, .svg or
# .gif reference makes xelatex abort the whole document with
# "Cannot determine size of graphic", which is why a single bad image from the
# notes research step used to take out notes.pdf entirely.
_LATEX_SAFE_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".pdf"}

_MD_IMAGE_RE = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<url>[^)\s]+)(?P<title>\s+\"[^\"]*\")?\)")


def _image_is_renderable(url: str, base_dir: str) -> bool:
    """True if a LaTeX engine can actually embed this image reference.

    Rejects formats LaTeX cannot size, local files that do not exist, and
    remote URLs that do not resolve to a reachable image.
    """
    ext = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower()

    if url.startswith(("http://", "https://")):
        if ext and ext not in _LATEX_SAFE_IMAGE_EXTS:
            return False
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                if resp.status != 200:
                    return False
                ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        except Exception:
            return False
        return ctype in ("image/png", "image/jpeg", "image/jpg", "application/pdf")

    # Local path, resolved relative to the markdown file.
    if ext not in _LATEX_SAFE_IMAGE_EXTS:
        return False
    candidate = url if os.path.isabs(url) else os.path.join(base_dir, url)
    return os.path.isfile(candidate)


def _strip_unrenderable_images(md_text: str, base_dir: str) -> tuple[str, int]:
    """Drop image references a LaTeX engine would choke on.

    Returns the cleaned markdown and the number of images removed. The alt
    text is kept as plain italic text so the surrounding prose still reads.
    """
    removed = 0

    def _sub(match: "re.Match[str]") -> str:
        nonlocal removed
        url = match.group("url")
        if _image_is_renderable(url, base_dir):
            return match.group(0)
        removed += 1
        alt = (match.group("alt") or "").strip()
        log.info("[PDF] Dropping unrenderable image: %s", url)
        return f"*{alt}*" if alt else ""

    return _MD_IMAGE_RE.sub(_sub, md_text), removed


# Candidate PDF engines, in order of preference. The first one found wins.
_PDF_ENGINES = ["xelatex", "lualatex", "pdflatex", "tectonic", "wkhtmltopdf", "weasyprint"]


def _resolve_tool(name: str) -> str | None:
    """Locate an executable by name, searching PATH and known install dirs.

    Returns the absolute path to the executable, or None if not found.
    Works even when the running process inherited a stale PATH.
    """
    found = shutil.which(name)
    if found:
        return found
    for d in _EXTRA_TOOL_DIRS:
        if not d:
            continue
        candidate = shutil.which(name, path=d)
        if candidate:
            return candidate
    return None


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

        pandoc = _resolve_tool("pandoc")
        if pandoc is None:
            raise RuntimeError(
                "pandoc could not be found on PATH or in any known install "
                "location. Install it from https://pandoc.org/installing.html "
                "(or `winget install JohnMacFarlane.Pandoc`)."
            )

        engine = next((e for e in _PDF_ENGINES if _resolve_tool(e)), None)
        if engine is None:
            raise RuntimeError(
                "pandoc is installed, but no PDF engine was found. Install one "
                "of: a LaTeX engine such as tectonic "
                "(`winget install TectonicTypesetting.Tectonic`), MiKTeX, or "
                "TeX Live (provides xelatex/pdflatex), or wkhtmltopdf "
                "(`winget install wkhtmltopdf.wkhtmltox`)."
            )

        # Eisvogel is a LaTeX template, so only probe for it when the resolved
        # engine is a LaTeX one. HTML engines (wkhtmltopdf/weasyprint) ignore or
        # error on --template and on the -V geometry flags.
        _is_latex = engine in ("xelatex", "lualatex", "pdflatex", "tectonic")
        _eisvogel = None
        if _is_latex:
            _eisvogel_candidates = [
                # Explicit override first - how a container points at its copy.
                os.environ.get("EISVOGEL_TEMPLATE", ""),
                # Windows. expandvars only understands %VAR% on win32, so these
                # stay literal elsewhere and simply fail the isfile check.
                os.path.expandvars(r"%APPDATA%\pandoc\templates\eisvogel.latex"),
                os.path.expandvars(r"%USERPROFILE%\.pandoc\templates\eisvogel.latex"),
                # POSIX: per-user, then the system-wide path a Docker image uses.
                os.path.join(
                    os.path.expanduser("~"), ".pandoc", "templates", "eisvogel.latex"
                ),
                "/usr/share/pandoc/templates/eisvogel.latex",
            ]
            _eisvogel = next(
                (p for p in _eisvogel_candidates if p and os.path.isfile(p)), None
            )

        # LaTeX aborts the whole document on one unsizeable image, and the notes
        # research step routinely cites .webp/.svg or dead URLs. Render from a
        # sanitised copy so a bad citation costs one figure, not the PDF.
        pandoc_input = input_md_path
        if _is_latex:
            with open(input_md_path, encoding="utf-8") as _f:
                _md = _f.read()
            _clean, _removed = _strip_unrenderable_images(
                _md, os.path.dirname(os.path.abspath(input_md_path))
            )
            if _removed:
                pandoc_input = os.path.splitext(input_md_path)[0] + ".pdfsrc.md"
                with open(pandoc_input, "w", encoding="utf-8") as _f:
                    _f.write(_clean)
                log.info(
                    "[PDF] Removed %d unrenderable image(s) before rendering %s",
                    _removed, os.path.basename(output_pdf_path),
                )

        cmd = [
            pandoc, pandoc_input,
            "-o", output_pdf_path,
            f"--pdf-engine={_resolve_tool(engine)}",
        ]
        if _eisvogel:
            cmd += [
                f"--template={_eisvogel}",
                "-V", "geometry:margin=0.75in",
                "-V", "linkcolor=blue",
                "-V", "urlcolor=blue",
                "-V", "colorlinks=true",
                "-V", "numbersections",
                "-V", "toc",
                "--highlight-style=tango",
                "--dpi=300",
            ]
            log.info("[PDF] Using Eisvogel template: %s", _eisvogel)
        elif _is_latex:
            cmd += [
                "-V", "geometry:margin=1in",
                "-V", "colorlinks=true",
                "-V", "linkcolor=blue",
                "--highlight-style=tango",
            ]
            log.info(
                "[PDF] Eisvogel template not found - using basic formatting. "
                "See the Eisvogel section in README.md to install it."
            )

        def _pandoc(source: str) -> None:
            # Decode output as UTF-8 with replacement: pandoc/LaTeX engines can
            # emit non-cp1252 bytes (e.g. tectonic's font diagnostics), which
            # would otherwise crash the capture thread on Windows.
            subprocess.run(
                [source if a is pandoc_input else a for a in cmd],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

        t0 = time.monotonic()
        started_at = datetime.now(timezone.utc).isoformat()
        text_only_path = ""
        try:
            try:
                _pandoc(pandoc_input)
            except subprocess.CalledProcessError as exc:
                # Screening images by extension and content-type is not enough:
                # a URL can advertise image/png and still serve bytes LaTeX
                # cannot size, and it only shows up as "Cannot determine size of
                # graphic" after pandoc has downloaded it. Rather than lose the
                # document over one bad figure, retry once with every image
                # removed. A text-only PDF beats no PDF.
                if "size of graphic" not in (exc.stderr or "") and _is_latex:
                    raise RuntimeError(
                        f"pandoc failed (engine={engine}):\n{exc.stderr}"
                    ) from exc
                with open(input_md_path, encoding="utf-8") as _f:
                    stripped = _MD_IMAGE_RE.sub("", _f.read())
                text_only_path = os.path.splitext(input_md_path)[0] + ".textonly.md"
                with open(text_only_path, "w", encoding="utf-8") as _f:
                    _f.write(stripped)
                log.warning(
                    "[PDF] An image defeated the PDF engine; re-rendering %s "
                    "without figures.",
                    os.path.basename(output_pdf_path),
                )
                try:
                    _pandoc(text_only_path)
                except subprocess.CalledProcessError as exc2:
                    raise RuntimeError(
                        f"pandoc failed (engine={engine}), including without "
                        f"images:\n{exc2.stderr}"
                    ) from exc2
        finally:
            # Drop the intermediates; the original .md is untouched.
            for tmp in (pandoc_input, text_only_path):
                if tmp and tmp != input_md_path:
                    try:
                        os.remove(tmp)
                    except OSError:
                        pass

        duration_s = round(time.monotonic() - t0, 3)
        finished_at = datetime.now(timezone.utc).isoformat()
        result: dict = {
            "status": "ok",
            "pdf_path": output_pdf_path,
            "duration_s": duration_s,
            "started_at": started_at,
            "finished_at": finished_at,
        }
        if not self.validate_output(result):
            return {"status": "error", "pdf_path": output_pdf_path, "duration_s": duration_s}

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
