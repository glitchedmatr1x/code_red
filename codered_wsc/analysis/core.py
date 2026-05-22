"""Best-effort decoded RDR script reporting without source reconstruction."""
from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


PRINTABLE_RE = re.compile(rb"[\x20-\x7E]{4,}")
POPULATION_TERMS = {
    "ped_wilderness",
    "ped_traveller",
    "ped_law",
    "ped_bad_guys_local",
    "ped_bad_guys_generic",
    "ped_vehicle",
}
ACTOR_RANGES = [
    (1155, 1202, "vehicle_actor"),
    (467, 540, "gang_actor"),
    (424, 466, "law_actor"),
    (595, 598, "fbi_actor"),
    (0, 1294, "eActorEnum_candidate"),
]
OPCODE_NAMES = {
    37: "PushS8",
    38: "PushS16",
    39: "PushS24",
    40: "PushS32",
    41: "PushF32",
    42: "Dup",
    43: "Drop",
    44: "Native",
    45: "Enter",
    46: "Return",
    110: "Switch",
    111: "PushString",
    112: "PushArrayP",
    113: "PushStringNull",
}
for _op in range(52, 65):
    OPCODE_NAMES.setdefault(_op, f"Op{_op}_u8")
for _op in range(65, 106):
    OPCODE_NAMES.setdefault(_op, f"Op{_op}_u16")
for _op in range(106, 110):
    OPCODE_NAMES.setdefault(_op, f"Op{_op}_u24")
for _op in range(114, 118):
    OPCODE_NAMES.setdefault(_op, f"StringOp{_op}")
for _op in range(122, 138):
    OPCODE_NAMES.setdefault(_op, f"CompactReturn{_op}")


@dataclass
class InstructionRow:
    offset: int
    opcode: int
    name: str
    size: int
    operand_hex: str
    notes: str = ""

    def text(self) -> str:
        suffix = f" ; {self.notes}" if self.notes else ""
        operands = f" {self.operand_hex}" if self.operand_hex else ""
        return f"{self.offset:08X}: {self.opcode:02X} {self.name}{operands}{suffix}"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str] | None = None) -> None:
    rows = list(rows)
    ensure_dir(path.parent)
    if fields is None:
        fields = []
        for row in rows:
            for field in row:
                if field not in fields:
                    fields.append(field)
    with path.open("w", newline="", encoding="utf-8") as handle:
        if not fields:
            return
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def extract_strings(data: bytes) -> list[dict[str, Any]]:
    strings: list[dict[str, Any]] = []
    for match in PRINTABLE_RE.finditer(data):
        text = match.group().decode("ascii", errors="replace")
        strings.append(
            {
                "offset": match.start(),
                "offset_hex": f"0x{match.start():X}",
                "length": len(match.group()),
                "text": text,
                "population_term": text.lower() if text.lower() in POPULATION_TERMS else "",
            }
        )
    return strings


def actor_kind(value: int) -> str:
    for low, high, name in ACTOR_RANGES:
        if low <= value <= high:
            return name
    return ""


def operand_size(data: bytes, offset: int) -> tuple[int, str]:
    opcode = data[offset]
    remaining = len(data) - offset
    if opcode == 45 and remaining >= 5:
        return min(remaining, 5 + data[offset + 4]), "enter"
    if opcode == 46:
        return min(remaining, 3), "return"
    if opcode in (37, *range(52, 65), *range(114, 118)):
        return min(remaining, 2), "u8"
    if opcode in (38, 44, *range(65, 106)):
        return min(remaining, 3), "u16"
    if opcode in (39, *range(106, 110)):
        return min(remaining, 4), "u24"
    if opcode in (40, 41):
        return min(remaining, 5), "u32"
    if opcode == 110 and remaining >= 2:
        return min(remaining, 2 + data[offset + 1] * 6), "switch"
    if opcode == 111 and remaining >= 2:
        return min(remaining, 2 + data[offset + 1]), "push_string"
    if opcode == 112 and remaining >= 2:
        return min(remaining, 6 + data[offset + 1]), "push_array"
    return 1, "raw"


def disassemble(data: bytes) -> list[InstructionRow]:
    rows: list[InstructionRow] = []
    offset = 0
    while offset < len(data):
        size, kind = operand_size(data, offset)
        if size <= 0:
            size = 1
        opcode = data[offset]
        name = OPCODE_NAMES.get(opcode, f"RawOp{opcode}")
        operands = data[offset + 1 : offset + size]
        notes = ""
        if kind == "raw":
            notes = "operand width not inferred"
        elif opcode == 45 and len(operands) >= 4:
            name_bytes = operands[4 : 4 + operands[3]]
            function_name = name_bytes.decode("ascii", errors="replace") or "main"
            notes = f"params={operands[0]} locals={(operands[1] << 8) | operands[2]} name={function_name}"
        elif opcode == 44 and len(operands) == 2:
            notes = f"native_index_bits=0x{int.from_bytes(operands, 'little'):04X}"
        rows.append(InstructionRow(offset, opcode, name, size, operands.hex(" ").upper(), notes))
        offset += size
    return rows


def find_functions(rows: list[InstructionRow]) -> list[dict[str, Any]]:
    functions: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if row.opcode != 45:
            continue
        params = locals_count = name_length = 0
        name = "main" if row.offset == 0 else f"Function_{len(functions)}"
        raw = bytes.fromhex(row.operand_hex) if row.operand_hex else b""
        if len(raw) >= 4:
            params = raw[0]
            locals_count = (raw[1] << 8) | raw[2]
            name_length = raw[3]
            parsed_name = raw[4 : 4 + name_length].decode("ascii", errors="replace")
            if parsed_name:
                name = parsed_name
        next_offset = rows[index + 1].offset if index + 1 < len(rows) else row.offset + row.size
        functions.append(
            {
                "index": len(functions),
                "name": name,
                "offset": row.offset,
                "offset_hex": f"0x{row.offset:X}",
                "body_offset": next_offset,
                "parameters": params,
                "locals": locals_count,
                "enter_name_length": name_length,
            }
        )
    for index, function in enumerate(functions):
        function["end_hint"] = functions[index + 1]["offset"] if index + 1 < len(functions) else ""
    return functions


def native_rows(rows: list[InstructionRow]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        if row.opcode == 44 and row.operand_hex:
            raw = bytes.fromhex(row.operand_hex)
            output.append(
                {
                    "offset": row.offset,
                    "offset_hex": f"0x{row.offset:X}",
                    "operand_hex": row.operand_hex,
                    "native_index_bits": int.from_bytes(raw, "little"),
                    "returns_flag": raw[0] & 1,
                    "param_count_bits": (raw[0] & 0x3E) >> 1,
                }
            )
    return output


def branch_rows(rows: list[InstructionRow]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        if 82 <= row.opcode <= 105 and row.size == 3:
            operands = bytes.fromhex(row.operand_hex)
            delta = int.from_bytes(operands, "big", signed=True)
            output.append(
                {
                    "offset": row.offset,
                    "offset_hex": f"0x{row.offset:X}",
                    "opcode": row.opcode,
                    "kind": "branch_or_call_candidate",
                    "delta": delta,
                    "target_candidate": row.offset + row.size + delta,
                }
            )
    return output


def constant_rows(rows: list[InstructionRow]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        if row.opcode not in (37, 38, 39, 40, 65):
            continue
        raw = bytes.fromhex(row.operand_hex)
        value = int.from_bytes(raw, "big", signed=False)
        output.append(
            {
                "offset": row.offset,
                "offset_hex": f"0x{row.offset:X}",
                "opcode": row.opcode,
                "width": len(raw),
                "value": value,
                "actor_kind": actor_kind(value),
                "operand_hex": row.operand_hex,
            }
        )
    return output


def enum_candidates(data: bytes, constants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = [row for row in constants if row["actor_kind"]]
    seen = {(row["offset"], row["width"]) for row in candidates}
    for offset in range(max(0, len(data) - 1)):
        value = int.from_bytes(data[offset : offset + 2], "big")
        kind = actor_kind(value)
        if not kind or (offset, 2) in seen:
            continue
        candidates.append(
            {
                "offset": offset,
                "offset_hex": f"0x{offset:X}",
                "opcode": "",
                "width": 2,
                "value": value,
                "actor_kind": kind,
                "operand_hex": data[offset : offset + 2].hex(" ").upper(),
                "candidate_source": "raw_u16be_window",
            }
        )
    return candidates


def disasm_artifacts(data: bytes) -> dict[str, Any]:
    rows = disassemble(data)
    constants = constant_rows(rows)
    return {
        "instructions": rows,
        "functions": find_functions(rows),
        "natives": native_rows(rows),
        "branches": branch_rows(rows),
        "constants": constants,
        "enums": enum_candidates(data, constants),
    }


def write_inspect_report(out: Path, source_info: dict[str, Any], data: bytes) -> dict[str, Any]:
    ensure_dir(out)
    strings = extract_strings(data)
    disasm = disasm_artifacts(data)
    write_json(out / "resource_info.json", source_info)
    (out / "decompressed.bin").write_bytes(data)
    (out / "code_sections.bin").write_bytes(data)
    (out / "strings.txt").write_text("\n".join(row["text"] for row in strings) + ("\n" if strings else ""), encoding="utf-8")
    write_csv(out / "strings.csv", strings, ["offset", "offset_hex", "length", "text", "population_term"])
    write_csv(out / "native_table.csv", disasm["natives"], ["offset", "offset_hex", "operand_hex", "native_index_bits", "returns_flag", "param_count_bits"])
    write_csv(out / "statics.csv", [], ["status", "note"])
    write_csv(out / "globals.csv", [], ["status", "note"])
    write_csv(out / "functions.csv", disasm["functions"])
    report = [
        "# Code RED Script Inspect Report",
        "",
        f"- Source: `{source_info['path']}`",
        f"- Resource family: `{source_info['family']}`",
        f"- Decoded size: `{len(data)}` bytes",
        f"- Printable strings: `{len(strings)}`",
        f"- Enter-pattern function candidates: `{len(disasm['functions'])}`",
        f"- Native-call candidates: `{len(disasm['natives'])}`",
        "",
        "## Boundary",
        "",
        "This is decoded-resource inspection. `statics.csv` and `globals.csv` are placeholders until their table layout is validated.",
        "Strings are anchors for review, not proof of behavior.",
    ]
    if source_info.get("decode_error"):
        report.extend(["", "## Decode Limit", "", source_info["decode_error"]])
    (out / "inspect_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return {"strings": len(strings), "functions": len(disasm["functions"]), "natives": len(disasm["natives"])}


def write_disasm_report(out: Path, source_info: dict[str, Any], data: bytes) -> dict[str, Any]:
    ensure_dir(out)
    artifacts = disasm_artifacts(data)
    rows: list[InstructionRow] = artifacts["instructions"]
    (out / "disassembly.txt").write_text("\n".join(row.text() for row in rows) + "\n", encoding="utf-8")
    write_json(out / "disassembly.json", [asdict(row) for row in rows])
    write_csv(out / "function_map.csv", artifacts["functions"])
    write_csv(out / "branch_map.csv", artifacts["branches"])
    write_csv(out / "native_calls.csv", artifacts["natives"])
    write_csv(out / "constants.csv", artifacts["constants"])
    write_csv(out / "enum_candidates.csv", artifacts["enums"])
    function_dir = out / "functions"
    ensure_dir(function_dir)
    for index, function in enumerate(artifacts["functions"]):
        start = function["offset"]
        next_start = artifacts["functions"][index + 1]["offset"] if index + 1 < len(artifacts["functions"]) else len(data)
        selected = [row.text() for row in rows if start <= row.offset < next_start]
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(function["name"]))[:80] or f"Function_{index}"
        (function_dir / f"{index:04d}_{safe_name}.asm.txt").write_text("\n".join(selected) + "\n", encoding="utf-8")
    report = [
        "# Code RED Script Disassembly Report",
        "",
        f"- Source: `{source_info['path']}`",
        f"- Instructions walked: `{len(rows)}`",
        f"- Function candidates: `{len(artifacts['functions'])}`",
        f"- Branch/call candidates: `{len(artifacts['branches'])}`",
        f"- Enum candidates: `{len(artifacts['enums'])}`",
        "",
        "Unknown opcode widths are emitted as one raw byte and are never rewritten by this report.",
        "Branch targets and actor enum windows are candidates until bytecode structure is confirmed for the script.",
    ]
    (out / "disasm_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return {"instructions": len(rows), "functions": len(artifacts["functions"]), "branches": len(artifacts["branches"])}


def normalize_terms(terms: str | Iterable[str]) -> list[str]:
    if isinstance(terms, str):
        values = terms.split(",")
    else:
        values = list(terms)
    return [value.strip() for value in values if value.strip()]


def write_scan_report(out: Path, source_info: dict[str, Any], data: bytes, terms: str | Iterable[str]) -> dict[str, Any]:
    ensure_dir(out)
    requested = normalize_terms(terms)
    rows: list[dict[str, Any]] = []
    contexts: list[str] = []
    lower = data.lower()
    for term in requested:
        needle = term.encode("ascii", errors="ignore").lower()
        start = 0
        while needle:
            offset = lower.find(needle, start)
            if offset < 0:
                break
            before = max(0, offset - 48)
            after = min(len(data), offset + len(needle) + 48)
            context = data[before:after]
            row = {
                "term": term,
                "offset": offset,
                "offset_hex": f"0x{offset:X}",
                "context_ascii": "".join(chr(byte) if 32 <= byte <= 126 else "." for byte in context),
                "context_hex": context.hex(" ").upper(),
            }
            rows.append(row)
            contexts.extend([f"## {term} at 0x{offset:X}", row["context_ascii"], row["context_hex"], ""])
            start = offset + 1
    anchors = [
        {
            "term": row["term"],
            "offset": row["offset"],
            "offset_hex": row["offset_hex"],
            "status": "manual_review_required",
            "reason": "decoded string or byte anchor; inspect nearby code and callers before patching",
        }
        for row in rows
    ]
    write_csv(out / "term_hits.csv", rows)
    (out / "nearby_code_context.txt").write_text("\n".join(contexts), encoding="utf-8")
    write_csv(out / "likely_logic_anchors.csv", anchors)
    report = [
        "# Code RED Script Scan Report",
        "",
        f"- Source: `{source_info['path']}`",
        f"- Terms: `{', '.join(requested)}`",
        f"- Hits: `{len(rows)}`",
        "",
        "Hits are decoded byte anchors. Use disassembly and patch manifests before treating a hit as script behavior.",
    ]
    (out / "scan_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return {"terms": requested, "hits": len(rows)}


PATCHABILITY_LEVELS = ["READ_ONLY", "SAME_SIZE_SAFE", "CONTROL_FLOW_SAFE", "REBUILD_REQUIRED", "UNSUPPORTED"]
CANDIDATE_KINDS = ("branch", "native", "constants", "strings", "tables")


def map_artifacts(data: bytes) -> dict[str, Any]:
    from .tables import table_rows

    disasm = disasm_artifacts(data)
    return {
        **disasm,
        "strings": extract_strings(data),
        "tables": table_rows(data),
    }


def write_map_report(out: Path, source_info: dict[str, Any], data: bytes) -> dict[str, Any]:
    ensure_dir(out)
    artifacts = map_artifacts(data)
    write_json(out / "script_map.json", {"source": source_info, "patchability_levels": PATCHABILITY_LEVELS, **artifacts_to_json(artifacts)})
    write_csv(out / "functions.csv", artifacts["functions"])
    write_csv(out / "strings.csv", artifacts["strings"])
    write_csv(out / "constants.csv", artifacts["constants"])
    write_csv(out / "native_calls.csv", artifacts["natives"])
    write_csv(out / "branch_map.csv", artifacts["branches"])
    write_csv(out / "tables.csv", artifacts["tables"])
    report = [
        "# Code RED Decoded Script Map",
        "",
        f"- Source: `{source_info['path']}`",
        f"- Function candidates: `{len(artifacts['functions'])}`",
        f"- String anchors: `{len(artifacts['strings'])}`",
        f"- Constant operands: `{len(artifacts['constants'])}`",
        f"- Native-call candidates: `{len(artifacts['natives'])}`",
        f"- Branch/call candidates: `{len(artifacts['branches'])}`",
        f"- Known table blocks: `{len(artifacts['tables'])}`",
        "",
        "This map separates decoded evidence from patch candidates. Use `candidates` and dry-run recipes before editing a decoded range.",
        "Population pools are currently the first known table mapper; update-thread, mission, sector, and state tables can join this surface when their ownership is proven.",
    ]
    (out / "map_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return {
        "functions": len(artifacts["functions"]),
        "strings": len(artifacts["strings"]),
        "constants": len(artifacts["constants"]),
        "natives": len(artifacts["natives"]),
        "branches": len(artifacts["branches"]),
        "tables": len(artifacts["tables"]),
    }


def artifacts_to_json(artifacts: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for name, value in artifacts.items():
        if name == "instructions":
            output[name] = [asdict(row) for row in value]
        else:
            output[name] = value
    return output


def patch_candidates(data: bytes, kind: str) -> list[dict[str, Any]]:
    rows = disassemble(data)
    if kind == "branch":
        from .control_flow import branch_patch_candidates

        return branch_patch_candidates(rows)
    if kind == "native":
        from .native_calls import native_patch_candidates

        return native_patch_candidates(rows)
    if kind == "constants":
        from .constants import constant_patch_candidates

        return constant_patch_candidates(rows)
    if kind == "strings":
        from .strings import string_patch_candidates

        return string_patch_candidates(data)
    if kind == "tables":
        from .tables import table_patch_candidates

        return table_patch_candidates(data)
    raise ValueError(f"Candidate kind must be one of {', '.join(CANDIDATE_KINDS)}, got {kind}")


def write_candidates_report(out: Path, source_info: dict[str, Any], data: bytes, kind: str) -> dict[str, Any]:
    ensure_dir(out)
    candidates = patch_candidates(data, kind)
    counts = {level: sum(1 for row in candidates if row.get("patchability") == level) for level in PATCHABILITY_LEVELS}
    write_csv(out / f"{kind}_candidates.csv", candidates)
    write_json(
        out / f"{kind}_candidates.json",
        {"source": source_info, "kind": kind, "patchability_levels": PATCHABILITY_LEVELS, "counts": counts, "candidates": candidates},
    )
    report = [
        "# Code RED Patch Candidate Report",
        "",
        f"- Source: `{source_info['path']}`",
        f"- Candidate kind: `{kind}`",
        f"- Candidate rows: `{len(candidates)}`",
        *(f"- {level}: `{counts[level]}`" for level in PATCHABILITY_LEVELS),
        "",
        "Patchability labels describe the current tool guarantee. `READ_ONLY` candidates are analysis evidence and must not be edited by a recipe yet.",
        "Current `SAME_SIZE_SAFE` coverage is fixed-width constant operands, same-length printable strings, and mapped population table enum operands.",
    ]
    (out / f"{kind}_candidates_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return {"kind": kind, "candidates": len(candidates), "patchability": counts}
