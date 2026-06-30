from .specialist_agent import FlashcardAgent, NotesAgent, PDFAgent, VideoAgent
from .base_agent import AbstractStudyAgent, TOOL_DEFINITIONS

# ADK layer (additive — does not affect existing imports)
from .adk_tools import WEB_SEARCH_TOOL, IMAGE_SEARCH_TOOL
from .adk_agents import (
    make_notes_agent,
    NotesPostProcessAgent,
    make_flashcard_agent,
    FlashcardSaveAgent,
    VideoADKAgent,
    PDFADKAgent,
)
from .adk_orchestrator import ADKStudyOrchestrator

__all__ = [
    # Original agents
    "AbstractStudyAgent",
    "TOOL_DEFINITIONS",
    "NotesAgent",
    "FlashcardAgent",
    "VideoAgent",
    "PDFAgent",
    # ADK tools
    "WEB_SEARCH_TOOL",
    "IMAGE_SEARCH_TOOL",
    # ADK agents
    "make_notes_agent",
    "NotesPostProcessAgent",
    "make_flashcard_agent",
    "FlashcardSaveAgent",
    "VideoADKAgent",
    "PDFADKAgent",
    # ADK orchestrator
    "ADKStudyOrchestrator",
]
