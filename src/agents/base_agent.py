"""
base_agent.py
Abstract base class for all study-material generation agents.
"""

import os
import uuid
from abc import ABC, abstractmethod
from typing import Any

import anthropic


# ---------------------------------------------------------------------------
# Tool definitions registry — subclasses pull from here
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: dict[str, dict] = {
    "web_search": {
        "name": "web_search",
        "description": (
            "Search the web for current information, diagrams, or external "
            "sources on a topic."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query",
                }
            },
            "required": ["query"],
        },
    },
    "image_search": {
        "name": "image_search",
        "description": (
            "Search for diagrams, charts, or visual illustrations to embed "
            "in study notes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Image search query, e.g. 'gradient descent diagram'"
                    ),
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max images to return",
                    "default": 3,
                },
            },
            "required": ["query"],
        },
    },
}


class AbstractStudyAgent(ABC):
    """Abstract base class for all study-material generation agents.

    Provides shared infrastructure: Anthropic API client, an agentic
    tool-use loop, web/image search implementations, and file I/O helpers.
    Subclasses must implement build_prompt, run, and validate_output.
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        api_key: str | None = None,
    ) -> None:
        """Initialise the agent.

        Args:
            model:   Anthropic model ID to use for generation.
            api_key: Anthropic API key. Reads ANTHROPIC_API_KEY env var if None.
        """
        self.model = model
        self.api_key = api_key
        self.client = anthropic.Anthropic(api_key=api_key)
        self.tools: list[dict] = []   # subclasses append TOOL_DEFINITIONS entries
        self.agent_id: str = str(uuid.uuid4())[:5]

    # ------------------------------------------------------------------
    # Abstract interface — every concrete agent must implement these
    # ------------------------------------------------------------------

    @abstractmethod
    def build_prompt(self, topic: str) -> str:
        """Return the fully formatted prompt string for the given topic.

        Args:
            topic: The subject the agent should generate material about.

        Returns:
            A ready-to-send prompt string.
        """
        ...

    @abstractmethod
    def run(self, **kwargs: Any) -> dict:
        """Execute the agent's primary task.

        Returns:
            A dict containing at minimum:
            ``{"status": "ok" | "error", "output": <primary result>}``
        """
        ...

    @abstractmethod
    def validate_output(self, output: dict) -> bool:
        """Return True if the output dict meets quality requirements.

        Args:
            output: The dict returned by run().
        """
        ...

    # ------------------------------------------------------------------
    # API — single entry point, handles tool-use loop internally
    # ------------------------------------------------------------------

    def _call_api(
        self,
        prompt: str,
        system: str | None = None,
        use_tools: bool = False,
    ) -> str:
        """Send a prompt to the Anthropic API, optionally driving a tool-use loop.

        When use_tools is True and self.tools is non-empty, tools are included
        in every request. If the model issues a tool_use stop, each call is
        dispatched to _handle_tool_call and the result fed back; the loop
        continues until stop_reason == "end_turn".

        Args:
            prompt:    User-turn text to send.
            system:    Optional system prompt string.
            use_tools: Whether to attach self.tools to the request.

        Returns:
            The final text response from the model as a plain string.
        """
        messages: list[dict] = [{"role": "user", "content": prompt}]
        create_kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": messages,
        }
        if system:
            create_kwargs["system"] = system
        if use_tools and self.tools:
            create_kwargs["tools"] = self.tools

        while True:
            response = self.client.messages.create(**create_kwargs)

            if response.stop_reason == "end_turn":
                for block in response.content:
                    if hasattr(block, "text"):
                        return block.text
                return ""

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})
                tool_results: list[dict] = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = self._handle_tool_call(block.name, block.input)
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result,
                            }
                        )
                messages.append({"role": "user", "content": tool_results})
                create_kwargs["messages"] = messages
            else:
                # Unexpected stop reason — surface whatever text is present
                for block in response.content:
                    if hasattr(block, "text"):
                        return block.text
                return ""

    # ------------------------------------------------------------------
    # Tool dispatch
    # ------------------------------------------------------------------

    def _handle_tool_call(self, tool_name: str, tool_input: dict) -> str:
        """Dispatch a model-issued tool call to the correct implementation.

        Args:
            tool_name:  Name of the tool the model wants to call.
            tool_input: Input dict the model supplied for the tool.

        Returns:
            A string result to inject as a tool_result content block.
        """
        if tool_name == "web_search":
            return self._web_search(tool_input["query"])
        if tool_name == "image_search":
            return self._image_search(
                tool_input["query"],
                tool_input.get("max_results", 3),
            )
        return f"[tool error] Unknown tool: {tool_name}"

    def _web_search(self, query: str) -> str:
        """Search the web and return the top 3 results as formatted text.

        Uses the duckduckgo_search package. Falls back to an informative
        error string if the package is not installed.

        Args:
            query: The search query string.

        Returns:
            Formatted string per result:
            "Title: ...\\nURL: ...\\nSnippet: ...\\n\\n"
        """
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
            return (
                "[web_search] duckduckgo_search not installed. "
                "Run: pip install duckduckgo_search"
            )
        except Exception as exc:
            return f"[web_search error] {exc}"

    def _image_search(self, query: str, max_results: int = 3) -> str:
        """Search for images and return Markdown image links.

        Uses DuckDuckGo image search via the duckduckgo_search package.

        Args:
            query:       Image search query, e.g. 'gradient descent diagram'.
            max_results: Maximum number of image results to return.

        Returns:
            Newline-separated Markdown image links: "![title](url)"
        """
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
            return (
                "[image_search] duckduckgo_search not installed. "
                "Run: pip install duckduckgo_search"
            )
        except Exception as exc:
            return f"[image_search error] {exc}"

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------

    def _save_output(self, content: str, filename: str) -> str:
        """Write content to output/{filename}, creating parent dirs as needed.

        Args:
            content:  Text content to write.
            filename: Path relative to the project output/ directory,
                      e.g. "notes/notes_abc12.md".

        Returns:
            The absolute path of the written file.
        """
        base_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        path = os.path.join(base_dir, "output", filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path
