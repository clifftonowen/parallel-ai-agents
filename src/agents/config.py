"""
config.py

Environment configuration helpers shared by every entry point.

Kept separate from base_agent.py on purpose: base_agent.py is the agent ABC,
and benchmark_profile.py / the orchestrators should not have to import an
agent class just to read an environment variable.
"""

import os

__all__ = ["require_env"]


def require_env(name: str, purpose: str = "") -> str:
    """Return the value of an environment variable, or exit with a clear message.

    Replaces bare ``os.environ["X"]`` indexing, which raises an opaque KeyError
    from deep inside a run and gives the reader no idea which .env entry is
    missing or what it is for.

    Args:
        name:    Environment variable name, e.g. ``"ANTHROPIC_API_KEY"``.
        purpose: Short description of what the value is used for, shown in the
                 error message.

    Returns:
        The variable's value, stripped of surrounding whitespace.

    Raises:
        SystemExit: If the variable is unset or empty.
    """
    value = os.environ.get(name, "").strip()
    if not value:
        hint = f" ({purpose})" if purpose else ""
        raise SystemExit(
            f"ERROR: {name} is not set{hint}.\n"
            f"Copy .env.example to .env and fill in {name}, "
            f"or export it in your shell."
        )
    return value
