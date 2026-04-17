import uuid
import os
from abc import ABC, abstractmethod
import anthropic


class BaseAgent(ABC):
    """Shared interface for all study material generation agents."""

    def __init__(self, model: str = "claude-sonnet-4-6", api_key: str | None = None):
        self.model = model
        self.agent_id = str(uuid.uuid4())[:5]
        self.client = anthropic.Anthropic(api_key=api_key)

    @abstractmethod
    def build_prompt(self, topic: str) -> str:
        """Return a fully formatted prompt string for the given topic."""
        ...

    @abstractmethod
    def run(self, topic: str) -> str:
        """Generate and return study material for the given topic."""
        ...

    @abstractmethod
    def validate_output(self, output: str) -> bool:
        """Return True if the output meets quality requirements."""
        ...

    def _call_api(self, prompt: str) -> str:
        """Send a prompt to the Anthropic API and return the text response."""
        message = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text

    def _output_path(self, folder: str, filename: str) -> str:
        """Return the full path for an output file, creating the directory if needed."""
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        output_dir = os.path.join(base_dir, "output", folder)
        os.makedirs(output_dir, exist_ok=True)
        return os.path.join(output_dir, filename)
