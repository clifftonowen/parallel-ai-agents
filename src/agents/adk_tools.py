"""
adk_tools.py
------------
Async FunctionTool wrappers for DuckDuckGo web and image search.

Both callables are `async def` so ADK's LlmAgent can dispatch multiple
tool calls from a single model turn concurrently via asyncio.gather.
The blocking DuckDuckGo I/O runs in a thread pool via asyncio.to_thread,
keeping the event loop free while network calls are in flight.

Usage:
    from src.agents.adk_tools import WEB_SEARCH_TOOL, IMAGE_SEARCH_TOOL
    agent = LlmAgent(..., tools=[WEB_SEARCH_TOOL, IMAGE_SEARCH_TOOL])
"""

import asyncio

from google.adk.tools import FunctionTool


def _web_search_sync(query: str) -> str:
    try:
        from duckduckgo_search import DDGS

        results: list[str] = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=3):
                results.append(
                    f"Title: {r['title']}\n"
                    f"URL: {r['href']}\n"
                    f"Snippet: {r['body']}\n"
                )
        return "\n".join(results) or "No results found."
    except ImportError:
        return "[web_search] duckduckgo_search not installed. Run: pip install duckduckgo_search"
    except Exception as exc:
        return f"[web_search error] {exc}"


def _image_search_sync(query: str, max_results: int = 3) -> str:
    try:
        from duckduckgo_search import DDGS

        lines: list[str] = []
        with DDGS() as ddgs:
            for r in ddgs.images(query, max_results=max_results):
                title = r.get("title", query)
                url = r.get("image", "")
                if url:
                    lines.append(f"![{title}]({url})")
        return "\n".join(lines) or "No images found."
    except ImportError:
        return "[image_search] duckduckgo_search not installed. Run: pip install duckduckgo_search"
    except Exception as exc:
        return f"[image_search error] {exc}"


async def web_search(query: str) -> str:
    """Search the web for current information on a topic.

    Uses DuckDuckGo and returns the top 3 results as Title/URL/Snippet blocks.
    Call this at least twice before writing notes to ground every major concept.

    Args:
        query: The search query string, e.g. 'gradient descent machine learning'.

    Returns:
        Newline-separated result blocks, each with Title, URL, and Snippet.
        Returns 'No results found.' if DuckDuckGo returns nothing.
        Returns an error string prefixed with '[web_search error]' on failure.
    """
    return await asyncio.to_thread(_web_search_sync, query)


async def image_search(query: str, max_results: int = 3) -> str:
    """Search for diagrams, charts, or visual illustrations to embed in study notes.

    Uses DuckDuckGo image search and returns Markdown image links ready to
    embed directly in Markdown notes. Call this for every ## section heading.

    Args:
        query: Image search query, e.g. 'gradient descent diagram'.
        max_results: Maximum number of image results to return (default 3).

    Returns:
        Newline-separated Markdown image links: '![title](url)'.
        Returns 'No images found.' if DuckDuckGo returns nothing.
        Returns an error string prefixed with '[image_search error]' on failure.
    """
    return await asyncio.to_thread(_image_search_sync, query, max_results)


WEB_SEARCH_TOOL = FunctionTool(web_search)
IMAGE_SEARCH_TOOL = FunctionTool(image_search)
