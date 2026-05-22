"""Immediate constant and enum operand candidates."""
from __future__ import annotations

from typing import Any

from .core import InstructionRow, constant_rows, enum_candidates


def constant_patch_candidates(rows: list[InstructionRow]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in constant_rows(rows):
        width = int(row["width"])
        same_size = width in (1, 2, 4)
        candidates.append(
            {
                **row,
                "operand_offset": int(row["offset"]) + 1,
                "operand_offset_hex": f"0x{int(row['offset']) + 1:X}",
                "candidate_kind": "constant",
                "patchability": "SAME_SIZE_SAFE" if same_size else "READ_ONLY",
                "safe_patch_type": "replace_constant" if same_size else "",
                "confidence": "0.90" if same_size else "0.50",
                "reason": "decoded immediate operand with fixed width" if same_size else "constant operand width is not an implemented primitive",
            }
        )
    return candidates


def actor_enum_candidates(data: bytes, rows: list[InstructionRow]) -> list[dict[str, Any]]:
    """Return best-effort actor enum windows for review."""
    return enum_candidates(data, constant_rows(rows))
