"""Printable string anchors and same-size string patch candidates."""
from __future__ import annotations

from typing import Any

from .core import extract_strings


def string_rows(data: bytes) -> list[dict[str, Any]]:
    """Return decoded printable string anchors."""
    return extract_strings(data)


def string_patch_candidates(data: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in extract_strings(data):
        rows.append(
            {
                **row,
                "candidate_kind": "string",
                "patchability": "SAME_SIZE_SAFE",
                "safe_patch_type": "same_length_string_replace",
                "confidence": "0.95",
                "reason": "decoded printable bytes can be replaced only with equal encoded length",
                "length_change_patchability": "REBUILD_REQUIRED",
            }
        )
    return rows
