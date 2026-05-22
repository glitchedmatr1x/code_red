"""Control-flow candidates for report-only branch and call review."""
from __future__ import annotations

from typing import Any

from .core import InstructionRow, branch_rows


def branch_patch_candidates(rows: list[InstructionRow]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in branch_rows(rows):
        output.append(
            {
                **row,
                "candidate_kind": "branch",
                "patchability": "READ_ONLY",
                "confidence": "0.70",
                "reason": "branch target candidate decoded; branch rewrites wait for control-flow validation",
            }
        )
    return output
