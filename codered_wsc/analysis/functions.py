"""Function candidates recovered from decoded script instruction streams."""
from __future__ import annotations

from typing import Any

from .core import InstructionRow, find_functions
from .ownership import function_ranges


def function_rows(rows: list[InstructionRow]) -> list[dict[str, Any]]:
    """Return enter-pattern function candidates from decoded instructions."""
    return find_functions(rows)


def function_patch_candidates(rows: list[InstructionRow], data_size: int) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for function in function_ranges(find_functions(rows), data_size):
        output.append(
            {
                **function,
                "offset": function["start"],
                "offset_hex": function["start_hex"],
                "candidate_kind": "function",
                "patchability": "READ_ONLY",
                "confidence": "0.80",
                "blocked_reason": "UNKNOWN_RETURN_CONVENTION",
                "reason": "function entry is mapped, but early-return stack and default return conventions are not proven",
            }
        )
    return output
