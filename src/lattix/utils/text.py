"""Text processing and terminal formatting utilities.

This module provides helpers for manipulating strings, specifically focusing
on cleaning and preparing text for display or serialization.
"""

import re

__all__ = ["strip_ansi"]


# ======================================================
# ANSI helper
# ======================================================
_ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences (color codes) from a string.

    Args:
        text: The string containing potential ANSI codes.

    Returns:
        str: The cleaned "plain text" string.
    """
    return _ANSI_ESCAPE_RE.sub("", text)
