"""Agent package.

Re-exports are LAZY on purpose (PEP 562).

This file used to import every submodule eagerly, which meant that touching
anything under ``src.agents`` — including ``src.agents.config``, which is
twenty lines of ``os.environ`` handling — pulled in anthropic, ddgs, moviepy,
Playwright, python-pptx and the whole google-adk stack. That is over a gigabyte
of dependencies to read one environment variable, and it is what made the test
suite impossible to run without the full runtime installed.

``from src.agents import NotesAgent`` still works exactly as before; the
submodule is imported on first attribute access instead of at package import.
Anything that needs a specific agent can also keep importing the module
directly (``from src.agents.specialist_agent import NotesAgent``), which skips
this indirection entirely.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

# name -> submodule it lives in. The submodule is imported on first access.
_EXPORTS: dict[str, str] = {
    # Original agents
    "AbstractStudyAgent": "base_agent",
    "TOOL_DEFINITIONS": "base_agent",
    "NotesAgent": "specialist_agent",
    "FlashcardAgent": "specialist_agent",
    "VideoAgent": "specialist_agent",
    "PDFAgent": "specialist_agent",
    # ADK tools
    "WEB_SEARCH_TOOL": "adk_tools",
    "IMAGE_SEARCH_TOOL": "adk_tools",
    # ADK agents
    "make_notes_agent": "adk_agents",
    "NotesPostProcessAgent": "adk_agents",
    "make_flashcard_agent": "adk_agents",
    "FlashcardSaveAgent": "adk_agents",
    "VideoADKAgent": "adk_agents",
    "PDFADKAgent": "adk_agents",
    # ADK orchestrator
    "ADKStudyOrchestrator": "adk_orchestrator",
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    """Import the owning submodule the first time a name is asked for."""
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    value = getattr(import_module(f".{module_name}", __name__), name)
    globals()[name] = value  # cache, so this runs once per name
    return value


def __dir__() -> list[str]:
    return sorted(__all__)


# Type checkers cannot follow PEP 562, so give them the real thing. This block
# never runs, so it costs nothing at import time.
if TYPE_CHECKING:  # pragma: no cover
    # noqa: F401 throughout — these exist so type checkers and IDEs can still
    # resolve the lazily-exported names. Ruff cannot tell them apart from a
    # genuinely unused import.
    from .adk_agents import (  # noqa: F401
        FlashcardSaveAgent,
        NotesPostProcessAgent,
        PDFADKAgent,
        VideoADKAgent,
        make_flashcard_agent,
        make_notes_agent,
    )
    from .adk_orchestrator import ADKStudyOrchestrator  # noqa: F401
    from .adk_tools import IMAGE_SEARCH_TOOL, WEB_SEARCH_TOOL  # noqa: F401
    from .base_agent import TOOL_DEFINITIONS, AbstractStudyAgent  # noqa: F401
    from .specialist_agent import (  # noqa: F401
        FlashcardAgent,
        NotesAgent,
        PDFAgent,
        VideoAgent,
    )
