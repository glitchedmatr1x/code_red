"""Function candidates recovered from decoded script instruction streams."""
from __future__ import annotations

from typing import Any

from .core import InstructionRow, find_functions


def function_rows(rows: list[InstructionRow]) -> list[dict[str, Any]]:
    """Return enter-pattern function candidates from decoded instructions."""
    return find_functions(rows)
