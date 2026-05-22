"""Ownership and context metadata for decoded-script candidates."""
from __future__ import annotations

import math
import re
import struct
from dataclasses import dataclass
from typing import Any

from .core import InstructionRow, branch_rows, disassemble, extract_strings, find_functions, native_rows


PURPOSE_TERMS = (
    "vehicle",
    "actor",
    "ped",
    "population",
    "sector",
    "enable",
    "disable",
    "flee",
    "driver",
    "mission",
    "spawn",
    "wanted",
    "law",
    "gang",
)
CANDIDATE_PREFIX = {
    "constants": "CONST",
    "strings": "STR",
    "native": "NATIVE",
    "branch": "BRANCH",
    "tables": "TABLE",
}
NEARBY_RADIUS = 128


@dataclass
class ContextIndex:
    data_size: int
    instructions: list[InstructionRow]
    functions: list[dict[str, Any]]
    strings: list[dict[str, Any]]
    natives: list[dict[str, Any]]
    branches: list[dict[str, Any]]
    tables: list[dict[str, Any]]


def build_context_index(data: bytes) -> ContextIndex:
    from .tables import table_rows

    instructions = disassemble(data)
    functions = function_ranges(find_functions(instructions), len(data))
    return ContextIndex(
        len(data),
        instructions,
        functions,
        extract_strings(data),
        native_rows(instructions),
        branch_rows(instructions),
        table_rows(data),
    )


def function_ranges(functions: list[dict[str, Any]], data_size: int) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index, function in enumerate(functions):
        start = int(function["offset"])
        hinted = function.get("end_hint")
        end = int(hinted) if isinstance(hinted, int) else data_size
        output.append(
            {
                **function,
                "start": start,
                "start_hex": f"0x{start:X}",
                "end": end,
                "end_hex": f"0x{end:X}",
                "size": max(0, end - start),
                "range": f"0x{start:X}..0x{end:X}",
                "index": index,
            }
        )
    return output


def owner_function(index: ContextIndex, offset: int) -> dict[str, Any] | None:
    for function in index.functions:
        if int(function["start"]) <= offset < int(function["end"]):
            return function
    return None


def in_range(row: dict[str, Any], offset: int, width: int = 1) -> bool:
    start = int(row.get("start", row.get("code_start", row.get("offset", 0))))
    end_value = row.get("end", row.get("code_end", start + int(row.get("size", row.get("length", 1)))))
    end = int(end_value) if end_value != "" else start + 1
    return start <= offset < end or start < offset + max(width, 1) <= end


def rows_near(rows: list[dict[str, Any]], offset: int, radius: int = NEARBY_RADIUS) -> list[dict[str, Any]]:
    return [row for row in rows if abs(int(row.get("offset", row.get("code_start", 0))) - offset) <= radius]


def texts_near(index: ContextIndex, offset: int) -> list[str]:
    function = owner_function(index, offset)
    rows = [row for row in index.strings if abs(int(row["offset"]) - offset) <= NEARBY_RADIUS]
    if function:
        rows.extend(row for row in index.strings if in_range(function, int(row["offset"])))
    output: list[str] = []
    for row in rows:
        text = str(row["text"])
        if text not in output:
            output.append(text)
    return output[:12]


def offsets_near(rows: list[dict[str, Any]], offset: int) -> list[str]:
    return [str(row.get("offset_hex", f"0x{int(row['offset']):X}")) for row in rows_near(rows, offset)[:12]]


def string_classification(text: str, row: dict[str, Any], function_names: set[str]) -> str:
    lower = text.lower()
    if row.get("population_term") or lower.startswith("animal_"):
        return "population pool name"
    if text in function_names or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_:.-]{2,}", text) and lower in {"main", "init", "update"}:
        return "label/function-ish"
    if any(term in lower for term in ("task", "event", "anim", "action")) and " " not in text:
        return "event/task name"
    if any(term in lower for term in PURPOSE_TERMS):
        return "likely logic anchor"
    if " " in text or any(char in text for char in "!?%[]"):
        return "debug/display text"
    return "unknown"


def pushed_string_references(index: ContextIndex) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    string_by_start = {int(row["offset"]): row for row in index.strings}
    function_names = {str(row["name"]) for row in index.functions}
    for instruction in index.instructions:
        if instruction.opcode != 111 or not instruction.operand_hex:
            continue
        raw = bytes.fromhex(instruction.operand_hex)
        if not raw:
            continue
        decoded_offset = instruction.offset + 2
        text = raw[1 : 1 + raw[0]].rstrip(b"\0").decode("ascii", errors="replace")
        string = string_by_start.get(decoded_offset, {"offset": decoded_offset, "text": text, "population_term": ""})
        function = owner_function(index, instruction.offset)
        references.append(
            {
                "string_offset": decoded_offset,
                "string_offset_hex": f"0x{decoded_offset:X}",
                "string_text": text,
                "string_class": string_classification(text, string, function_names),
                "reference_instruction_offset": instruction.offset,
                "reference_instruction_offset_hex": f"0x{instruction.offset:X}",
                "owner_function_index": function["index"] if function else "",
                "owner_function": function["name"] if function else "",
                "owner_function_offset_range": function["range"] if function else "",
            }
        )
    return references


def function_context_rows(data: bytes, index: ContextIndex | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    index = index or build_context_index(data)
    reference_rows = pushed_string_references(index)
    details: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    for function in index.functions:
        strings = [ref for ref in reference_rows if ref["owner_function_index"] == function["index"]]
        raw_strings = [row["string_text"] for row in strings]
        natives = [row for row in index.natives if in_range(function, int(row["offset"]))]
        constants = [
            {"offset": row.offset, "offset_hex": f"0x{row.offset:X}", "opcode": row.opcode, "operand_hex": row.operand_hex}
            for row in index.instructions
            if row.opcode in (37, 38, 39, 40, 65) and in_range(function, row.offset)
        ]
        branches = [row for row in index.branches if in_range(function, int(row["offset"]))]
        tables = [row for row in index.tables if in_range(function, int(row["code_start"]))]
        tag_text = " ".join([str(function["name"]), *raw_strings]).lower()
        tags = [term for term in PURPOSE_TERMS if term in tag_text]
        detail = {
            "function_index": function["index"],
            "function_name": function["name"],
            "start_decoded_offset": function["start"],
            "start_decoded_offset_hex": function["start_hex"],
            "end_decoded_offset": function["end"],
            "end_decoded_offset_hex": function["end_hex"],
            "size": function["size"],
            "string_reference_count": len(strings),
            "native_call_count": len(natives),
            "constant_count": len(constants),
            "branch_count": len(branches),
            "table_block_count": len(tables),
            "purpose_tags": tags,
        }
        details.append(detail)
        contexts.append({**detail, "strings": strings, "native_calls": natives, "constants": constants, "branches": branches, "tables": tables})
    return details, contexts


def owner_defaults(kind: str, row: dict[str, Any]) -> tuple[str, str, str]:
    if kind == "strings":
        return "string", "string_table", str(row.get("text", ""))
    if kind == "native":
        return "native", "native_table", f"native_index_bits=0x{int(row.get('native_index_bits', 0)):X}"
    if kind == "branch":
        return "code", "branch_instruction", str(row.get("kind", "branch"))
    if kind == "tables":
        return "table", "population_pool" if row.get("table_kind") == "population_pool" else "generic_table", str(row.get("pool", row.get("table_kind", "")))
    return "code", "constant_operand", str(row.get("value", ""))


def candidate_offset(row: dict[str, Any]) -> int:
    return int(row.get("operand_offset", row.get("offset", row.get("string_offset", 0))))


def candidate_width(kind: str, row: dict[str, Any]) -> int:
    if kind == "strings":
        return int(row.get("length", 0))
    return int(row.get("operand_width", row.get("width", len(bytes.fromhex(str(row.get("operand_hex", "")))) if row.get("operand_hex") else 0)))


def constant_value_type(row: dict[str, Any], index: ContextIndex, offset: int) -> tuple[str, float]:
    value = int(row.get("value", 0))
    width = int(row.get("width", row.get("operand_width", 0)))
    actor_kind = str(row.get("actor_kind", ""))
    nearby_branches = rows_near(index.branches, offset, 32)
    in_pool = any(in_range(table, offset, max(width, 1)) for table in index.tables)
    if actor_kind == "vehicle_actor":
        return "enum-like vehicle", 0.98 if in_pool else 0.92
    if actor_kind:
        return "enum-like actor", 0.96 if in_pool else 0.88
    if value in (0, 1):
        return "bool-like 0/1", 0.92 if nearby_branches else 0.70
    if 0 < value < index.data_size:
        return "pointer/offset-like", 0.80
    if width == 4 and value > 0xFFFF and rows_near(index.natives, offset):
        return "hash-like 32-bit", 0.76
    if width == 4:
        decoded_float = struct.unpack(">f", value.to_bytes(4, "big"))[0]
        if math.isfinite(decoded_float) and 1e-6 <= abs(decoded_float) <= 1e6:
            return "float-like bit pattern", 0.62
    if width <= 2 or value < 256:
        return "small integer", 0.88
    return "unknown", 0.55


def candidate_value(kind: str, row: dict[str, Any], index: ContextIndex, offset: int) -> tuple[Any, str, float]:
    if kind == "strings":
        return row.get("text", ""), "string", float(row.get("confidence", 0.95))
    if kind == "native":
        return row.get("native_index_bits", ""), "native index bits", float(row.get("confidence", 0.85))
    if kind == "branch":
        return row.get("target_candidate", ""), "branch target candidate", float(row.get("confidence", 0.70))
    if kind == "tables":
        return row.get("enum", ""), str(row.get("likely_enum_category", "table value")), float(row.get("confidence", 0.50))
    value_type, confidence = constant_value_type(row, index, offset)
    return row.get("value", ""), value_type, confidence


def enrich_candidates(data: bytes, kind: str, rows: list[dict[str, Any]], index: ContextIndex | None = None) -> list[dict[str, Any]]:
    index = index or build_context_index(data)
    prefix = CANDIDATE_PREFIX[kind]
    function_tags = {function["index"]: function_purpose_tags(index, function) for function in index.functions}
    output: list[dict[str, Any]] = []
    for ordinal, row in enumerate(sorted(rows, key=candidate_offset), start=1):
        offset = candidate_offset(row)
        width = candidate_width(kind, row)
        function = owner_function(index, offset)
        section, owner_type, owner_name = owner_defaults(kind, row)
        value, value_type, confidence = candidate_value(kind, row, index, offset)
        patchability = str(row.get("patchability", "READ_ONLY"))
        nearby_strings = texts_near(index, offset)
        enriched = {
            **row,
            "candidate_id": f"{prefix}_{ordinal:06d}",
            "file_offset": "",
            "decoded_offset": offset,
            "decoded_offset_hex": f"0x{offset:X}",
            "section": section,
            "owner_type": owner_type,
            "owner_name": owner_name,
            "owner_function_index": function["index"] if function else "",
            "owner_function_offset_range": function["range"] if function else "",
            "owner_function_name": function["name"] if function else "",
            "owner_function_purpose_tags": function_tags.get(function["index"], []) if function else [],
            "nearby_strings": nearby_strings,
            "nearby_native_calls": offsets_near(index.natives, offset),
            "nearby_branches": offsets_near(index.branches, offset),
            "candidate_value": value,
            "candidate_value_type": value_type,
            "operand_width": width,
            "patchability_level": patchability,
            "confidence_score": f"{confidence:.2f}",
            "safety_reason": row.get("reason", "decoded candidate has no proven edit primitive"),
            "blocked_reason": "" if patchability in {"SAME_SIZE_SAFE", "CONTROL_FLOW_SAFE"} else row.get("reason", "ownership or edit primitive is not proven"),
            "unrelated_code_risk": "bounded operand or owned string/table bytes" if patchability == "SAME_SIZE_SAFE" else "editing could affect unrelated code until ownership and rewrite rules are proven",
        }
        output.append(enriched)
    return output


def function_purpose_tags(index: ContextIndex, function: dict[str, Any]) -> list[str]:
    refs = [row["string_text"] for row in pushed_string_references(index) if row["owner_function_index"] == function["index"]]
    text = " ".join([str(function["name"]), *refs]).lower()
    return [term for term in PURPOSE_TERMS if term in text]
