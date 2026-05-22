"""Native-call candidates recovered from decoded script instructions."""
from __future__ import annotations

from typing import Any

from .core import InstructionRow, native_rows


def native_patch_candidates(rows: list[InstructionRow]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in native_rows(rows):
        output.append(
            {
                **row,
                "candidate_kind": "native",
                "patchability": "READ_ONLY",
                "confidence": "0.85",
                "reason": "native index bits are decoded but call and argument edits are not proven safe",
            }
        )
    return output
