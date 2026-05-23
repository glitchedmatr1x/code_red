"""Control-flow candidates and dry-run-first review reports."""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from pathlib import Path
from typing import Any

from .core import InstructionRow, branch_rows, constant_rows, disassemble, ensure_dir, normalize_terms, write_csv, write_json


INVERT_BRANCH_OPCODE = {100: 101, 101: 100, 102: 105, 105: 102, 103: 104, 104: 103}
CONTROL_FLOW_BLOCKED_REASONS = {
    "UNKNOWN_OPCODE",
    "UNKNOWN_INSTRUCTION_WIDTH",
    "UNKNOWN_BRANCH_SEMANTICS",
    "NO_PROVEN_NOP_OPCODE",
    "UNKNOWN_STACK_EFFECT",
    "UNKNOWN_RETURN_CONVENTION",
    "LAYOUT_REBUILD_REQUIRED",
    "PROTECTED_SECTION_OVERLAP",
}


def branch_patch_candidates(rows: list[InstructionRow]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in branch_rows(rows):
        known_invert = int(row["opcode"]) in INVERT_BRANCH_OPCODE and int(row.get("instruction_size", 0)) == 3
        blocked = "" if known_invert else "UNKNOWN_BRANCH_SEMANTICS" if row.get("kind") == "branch_candidate" else "UNKNOWN_STACK_EFFECT"
        reason = (
            "RDR comparison branch has known three-byte width and invert opcode pair; target layout is preserved"
            if known_invert
            else "branch or call width is decoded, but a safe replacement with matching VM stack behavior is not available"
        )
        output.append(
            {
                **row,
                "candidate_kind": "branch",
                "patchability": "CONTROL_FLOW_SAFE" if known_invert else "READ_ONLY",
                "safe_patch_type": "force_branch" if known_invert else "",
                "supported_control_flow_modes": ["invert"] if known_invert else [],
                "replacement_opcode_invert": INVERT_BRANCH_OPCODE.get(int(row["opcode"]), ""),
                "blocked_reason": blocked,
                "confidence": "0.94" if known_invert else "0.70",
                "reason": reason,
            }
        )
    return output


def instruction_window(rows: list[InstructionRow], row_indexes: dict[int, int], offset: int, span: int = 10) -> list[dict[str, Any]]:
    index = row_indexes.get(offset)
    if index is None:
        return []
    selected = rows[max(0, index - span) : index + span + 1]
    return [{"role": "target" if row.offset == offset else "context", "offset": row.offset, "offset_hex": f"0x{row.offset:X}", "text": row.text()} for row in selected]


def rows_in_radius(rows: list[dict[str, Any]], offsets: list[int], offset: int, radius: int = 128) -> list[dict[str, Any]]:
    return rows[bisect_left(offsets, offset - radius) : bisect_right(offsets, offset + radius)]


def candidate_context(
    data: bytes,
    candidate: dict[str, Any],
    rows: list[InstructionRow],
    row_indexes: dict[int, int],
    constants: list[dict[str, Any]],
    constant_offsets: list[int],
) -> dict[str, Any]:
    offset = int(candidate["decoded_offset"])
    nearby_constants = rows_in_radius(constants, constant_offsets, offset)[:12]
    return {
        **candidate,
        "owner_function": candidate.get("owner_function_name", ""),
        "owner_function_id": candidate.get("owner_function_index", ""),
        "purpose_tags": candidate.get("owner_function_purpose_tags", []),
        "nearby_constants": nearby_constants,
        "instruction_context": instruction_window(rows, row_indexes, offset),
    }


def function_rank(candidate: dict[str, Any], terms: list[str]) -> int:
    text = " ".join(
        [
            str(candidate.get("owner_function_name", candidate.get("owner_name", ""))),
            *[str(value) for value in candidate.get("owner_function_purpose_tags", [])],
            *[str(value) for value in candidate.get("nearby_strings", [])],
        ]
    ).lower()
    return sum(1 for term in terms if term.lower() in text)


def write_control_flow_report(out: Path, source_info: dict[str, Any], data: bytes, terms: str | list[str]) -> dict[str, Any]:
    from .functions import function_patch_candidates
    from .native_calls import native_patch_candidates
    from .ownership import build_context_index, enrich_candidates

    ensure_dir(out)
    requested = normalize_terms(terms)
    rows = disassemble(data)
    constants = constant_rows(rows)
    row_indexes = {row.offset: index for index, row in enumerate(rows)}
    constant_offsets = [int(row["offset"]) for row in constants]
    context_index = build_context_index(data)
    candidates = [
        *enrich_candidates(data, "branch", branch_patch_candidates(rows), context_index),
        *enrich_candidates(data, "native", native_patch_candidates(rows), context_index),
        *enrich_candidates(data, "functions", function_patch_candidates(rows, len(data)), context_index),
    ]
    contexts = [candidate_context(data, candidate, rows, row_indexes, constants, constant_offsets) for candidate in candidates]
    write_csv(out / "control_flow_candidates.csv", candidates)
    write_json(out / "control_flow_candidates.json", {"source": source_info, "terms": requested, "candidates": contexts})
    ranked: dict[tuple[str, str], dict[str, Any]] = {}
    for candidate in candidates:
        key = (str(candidate.get("owner_function_index", "")), str(candidate.get("owner_function_name", candidate.get("owner_name", ""))))
        entry = ranked.setdefault(
            key,
            {
                "owner_function_index": key[0],
                "owner_function_name": key[1],
                "score": 0,
                "candidate_count": 0,
                "control_flow_safe_count": 0,
                "read_only_count": 0,
                "purpose_tags": candidate.get("owner_function_purpose_tags", []),
                "nearby_strings": candidate.get("nearby_strings", []),
            },
        )
        entry["score"] = max(entry["score"], function_rank(candidate, requested))
        entry["candidate_count"] += 1
        entry["control_flow_safe_count"] += int(candidate.get("patchability_level") == "CONTROL_FLOW_SAFE")
        entry["read_only_count"] += int(candidate.get("patchability_level") == "READ_ONLY")
    ranked_rows = sorted(ranked.values(), key=lambda row: (-int(row["score"]), str(row["owner_function_index"])))
    write_csv(out / "control_flow_ranked_functions.csv", ranked_rows)
    markdown = [
        "# Code RED Control Flow Context",
        "",
        f"- Source: `{source_info['path']}`",
        f"- Terms: `{', '.join(requested)}`",
        f"- Candidate rows: `{len(candidates)}`",
        f"- Ranked owner functions: `{len(ranked_rows)}`",
        "",
        "This report ranks decoded control-flow evidence only. Writes still require candidate targeting, dry-run review, and acknowledgement.",
        "",
    ]
    for context in contexts:
        markdown.extend(
            [
                f"## {context['candidate_id']} {context['candidate_kind']}",
                "",
                f"- Patchability: `{context['patchability_level']}`",
                f"- Blocked reason: `{context.get('blocked_reason') or 'none'}`",
                f"- Owner function: `{context.get('owner_function') or 'unknown'}` id `{context.get('owner_function_id')}`",
                f"- Purpose tags: `{', '.join(context.get('purpose_tags', [])) or 'none'}`",
                f"- Nearby strings: `{', '.join(context.get('nearby_strings', [])[:4]) or 'none'}`",
                "",
                "```text",
                *[row["text"] for row in context["instruction_context"]],
                "```",
                "",
            ]
        )
    (out / "control_flow_context.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    return {
        "terms": requested,
        "candidates": len(candidates),
        "functions": len(ranked_rows),
        "control_flow_safe": sum(1 for candidate in candidates if candidate.get("patchability_level") == "CONTROL_FLOW_SAFE"),
    }
