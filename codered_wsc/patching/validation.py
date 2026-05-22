"""Patch validation helpers shared by recipe patch bundles."""
from __future__ import annotations

from typing import Any

from ..analysis import disassemble
from .primitives import DecodedEdit


def byte_diff_rows(before: bytes, after: bytes, error_factory) -> list[dict[str, Any]]:
    if len(before) != len(after):
        raise error_factory("Decoded diff expects same-length byte arrays")
    rows: list[dict[str, Any]] = []
    for offset, (old, new) in enumerate(zip(before, after)):
        if old != new:
            rows.append({"offset": offset, "offset_hex": f"0x{offset:X}", "before_hex": f"{old:02X}", "after_hex": f"{new:02X}"})
    return rows


def hex_lines(data: bytes, width: int = 16) -> list[str]:
    return [f"{offset:08X}: {data[offset:offset + width].hex(' ').upper()}" for offset in range(0, len(data), width)]


def string_offsets(data: bytes) -> set[int]:
    offsets: set[int] = set()
    for row in disassemble(data):
        if row.opcode != 111 or not row.operand_hex:
            continue
        raw = bytes.fromhex(row.operand_hex)
        if raw:
            offsets.update(range(row.offset + 2, row.offset + 2 + raw[0]))
    return offsets


def validate_population_isolation(result) -> dict[str, Any]:
    population_edits: list[DecodedEdit] = [edit for edit in result.edits if edit.patch_type.startswith("population_")]
    actor_only = bool(result.population_patch_types) and set(result.population_patch_types) == {"population_actor_pool_replace"}
    vehicle_only = bool(result.population_patch_types) and set(result.population_patch_types) == {"population_vehicle_pool_replace"}
    return {
        "pools_touched_are_targeted": all(edit.pool in result.targeted_pools for edit in population_edits),
        "no_vehicle_pool_changed_during_actor_only_recipe": not actor_only or all(edit.enum_category == "human_actor" and edit.pool != "ped_vehicle" for edit in population_edits),
        "no_actor_pool_changed_during_vehicle_only_recipe": not vehicle_only or all(edit.enum_category == "vehicle_actor" and edit.pool == "ped_vehicle" for edit in population_edits),
    }
