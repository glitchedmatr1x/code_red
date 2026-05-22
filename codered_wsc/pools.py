"""Population pool discovery and same-width enum candidate mapping."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .analysis import InstructionRow, disassemble, find_functions, write_csv, write_json


POOL_NAMES = {
    "ped_wilderness",
    "ped_traveller",
    "ped_law",
    "ped_bad_guys_local",
    "ped_bad_guys_generic",
    "ped_vehicle",
}
VEHICLE_RANGE = range(1155, 1203)
VALID_ACTOR_RANGE = range(0, 1295)
ENUM_PATH = Path(__file__).resolve().parents[1] / "data" / "eActorEnum_minimal.csv"


@dataclass
class EnumRecord:
    start: int
    end: int
    label: str
    category: str


@dataclass
class PoolMap:
    pools: list[dict[str, Any]]
    candidates: list[dict[str, Any]]
    instructions: list[InstructionRow]
    functions: list[dict[str, Any]]

    def by_name(self, name: str) -> dict[str, Any] | None:
        return next((pool for pool in self.pools if pool["pool"] == name), None)

    def candidates_for(self, name: str) -> list[dict[str, Any]]:
        return [candidate for candidate in self.candidates if candidate["pool"] == name]


def load_enum_records(path: Path = ENUM_PATH) -> list[EnumRecord]:
    records: list[EnumRecord] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if not row.get("enum_start"):
                continue
            records.append(
                EnumRecord(
                    int(row["enum_start"], 0),
                    int(row["enum_end"] or row["enum_start"], 0),
                    row.get("label", ""),
                    row.get("category", ""),
                )
            )
    # Exact labels win over broad range rows.
    records.sort(key=lambda item: (item.end - item.start, 0 if item.label else 1, item.start))
    return records


def enum_lookup(value: int, records: list[EnumRecord]) -> dict[str, str]:
    for record in records:
        if record.start <= value <= record.end:
            return {"enum_label": record.label, "dictionary_category": record.category}
    return {"enum_label": "", "dictionary_category": ""}


def pushed_string(row: InstructionRow) -> str:
    if row.opcode != 111 or not row.operand_hex:
        return ""
    raw = bytes.fromhex(row.operand_hex)
    if not raw:
        return ""
    return raw[1 : 1 + raw[0]].rstrip(b"\0").decode("ascii", errors="replace")


def is_pool_name(name: str) -> bool:
    return name in POOL_NAMES or name.startswith("animal_")


def function_for_offset(functions: list[dict[str, Any]], offset: int) -> dict[str, Any] | None:
    selected = None
    for function in functions:
        if int(function["offset"]) <= offset:
            selected = function
        else:
            break
    return selected


def unsigned_immediate(row: InstructionRow) -> tuple[int | None, int, bytes]:
    # Population scripts observed here use the short push family for low enum
    # IDs and opcode 0x41 with a two-byte operand for larger actor/vehicle IDs.
    if row.opcode not in (37, 38, 39, 40, 65) or not row.operand_hex:
        return None, 0, b""
    raw = bytes.fromhex(row.operand_hex)
    return int.from_bytes(raw, "big", signed=False), len(raw), raw


def pool_candidate_category(pool: str, value: int, dictionary_category: str) -> tuple[str, float, str]:
    if value not in VALID_ACTOR_RANGE:
        return "unknown", 0.0, "outside eActorEnum range"
    if value in VEHICLE_RANGE or dictionary_category == "vehicle_actor":
        return "vehicle_actor", 0.98 if pool == "ped_vehicle" else 0.45, "vehicle enum range"
    if pool.startswith("animal_") or dictionary_category == "animal_actor":
        return "animal_actor", 0.92 if pool.startswith("animal_") else 0.40, "animal pool or enum dictionary"
    if pool.startswith("ped_") and pool != "ped_vehicle":
        confidence = 0.96 if dictionary_category == "human_actor" else 0.88
        reason = "dictionary human actor" if dictionary_category == "human_actor" else "ped pool immediate enum"
        return "human_actor", confidence, reason
    return "unknown", 0.20, "pool and enum dictionary do not agree"


def safe_for_pool(pool: str, category: str, confidence: float, width: int) -> bool:
    if width not in (1, 2, 4) or confidence < 0.80:
        return False
    if pool == "ped_vehicle":
        return category == "vehicle_actor"
    if pool.startswith("animal_"):
        return category == "animal_actor"
    return pool.startswith("ped_") and category == "human_actor"


def scan_population_pools(data: bytes, records: list[EnumRecord] | None = None) -> PoolMap:
    records = records or load_enum_records()
    instructions = disassemble(data)
    functions = find_functions(instructions)
    anchors: list[tuple[InstructionRow, str]] = []
    for row in instructions:
        name = pushed_string(row)
        if is_pool_name(name):
            anchors.append((row, name))
    pools: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for index, (row, name) in enumerate(anchors):
        end = anchors[index + 1][0].offset if index + 1 < len(anchors) else len(data)
        function = function_for_offset(functions, row.offset)
        pool = {
            "pool": name,
            "pool_kind": "vehicle_pool" if name == "ped_vehicle" else "animal_pool" if name.startswith("animal_") else "actor_pool",
            "string_instruction_offset": row.offset,
            "string_instruction_offset_hex": f"0x{row.offset:X}",
            "string_offset": row.offset + 2,
            "string_offset_hex": f"0x{row.offset + 2:X}",
            "function": function["name"] if function else "",
            "function_offset": function["offset"] if function else "",
            "code_start": row.offset,
            "code_start_hex": f"0x{row.offset:X}",
            "code_end": end,
            "code_end_hex": f"0x{end:X}",
        }
        pools.append(pool)
        for candidate_index, candidate_row in enumerate(instructions):
            if not (row.offset < candidate_row.offset < end):
                continue
            value, width, raw = unsigned_immediate(candidate_row)
            if value is None or value not in VALID_ACTOR_RANGE:
                continue
            enum_info = enum_lookup(value, records)
            category, confidence, reason = pool_candidate_category(name, value, enum_info["dictionary_category"])
            following_opcode = instructions[candidate_index + 1].opcode if candidate_index + 1 < len(instructions) else -1
            if candidate_row.opcode == 37 and following_opcode == 79:
                confidence = min(confidence, 0.35)
                reason += "; low immediate followed by pool control"
            candidate = {
                "pool": name,
                "instruction_offset": candidate_row.offset,
                "instruction_offset_hex": f"0x{candidate_row.offset:X}",
                "operand_offset": candidate_row.offset + 1,
                "operand_offset_hex": f"0x{candidate_row.offset + 1:X}",
                "opcode": candidate_row.opcode,
                "operand_width": width,
                "operand_bytes_hex": raw.hex(" ").upper(),
                "enum": value,
                **enum_info,
                "likely_enum_category": category,
                "confidence": f"{confidence:.2f}",
                "confidence_reason": reason,
                "safe_same_width_replace": safe_for_pool(name, category, confidence, width),
            }
            candidates.append(candidate)
    for pool in pools:
        selected = [candidate for candidate in candidates if candidate["pool"] == pool["pool"]]
        pool["candidate_enum_operands"] = len(selected)
        pool["safe_candidates"] = sum(1 for candidate in selected if candidate["safe_same_width_replace"])
    return PoolMap(pools, candidates, instructions, functions)


def write_pool_scan_report(out: Path, source_info: dict[str, Any], data: bytes) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    pool_map = scan_population_pools(data)
    actor_candidates = [candidate for candidate in pool_map.candidates if candidate["likely_enum_category"] != "vehicle_actor"]
    vehicle_candidates = [candidate for candidate in pool_map.candidates if candidate["likely_enum_category"] == "vehicle_actor"]
    write_csv(out / "population_pools.csv", pool_map.pools)
    write_json(out / "population_pools.json", {"source": source_info, "pools": pool_map.pools, "candidates": pool_map.candidates})
    write_csv(out / "pool_actor_candidates.csv", actor_candidates)
    write_csv(out / "pool_vehicle_candidates.csv", vehicle_candidates)
    contexts: list[str] = []
    for pool in pool_map.pools:
        contexts.append(f"## {pool['pool']} {pool['code_start_hex']}..{pool['code_end_hex']}")
        for row in pool_map.instructions:
            if pool["code_start"] <= row.offset < pool["code_end"]:
                contexts.append(row.text())
        contexts.append("")
    (out / "pool_context_disasm.txt").write_text("\n".join(contexts), encoding="utf-8")
    report = [
        "# Code RED Population Pool Scan",
        "",
        f"- Source: `{source_info['path']}`",
        f"- Pools found: `{len(pool_map.pools)}`",
        f"- Actor candidate rows: `{len(actor_candidates)}`",
        f"- Vehicle candidate rows: `{len(vehicle_candidates)}`",
        "",
        "Pool blocks start at an inline population pool `PushString` and stop at the next population pool `PushString`.",
        "Only immediate enum operands marked safe are eligible for milestone-two population patch recipes.",
    ]
    (out / "pool_scan_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return {"pools": len(pool_map.pools), "actor_candidates": len(actor_candidates), "vehicle_candidates": len(vehicle_candidates)}
