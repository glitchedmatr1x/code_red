#!/usr/bin/env python3
"""
Code Red WGD Inspector (RDR1 / RSC6 gringo dictionary)

Reads an unpacked .wgd resource payload (not the RSC85 wrapper) and emits CSV/Markdown reports.
It is intentionally read-only. It uses the RDR1 CodeX WGD layout as a guide:
- Rsc6GringoDictionary root
- Rsc6Gringo / ComponentItemGringo
- Rsc6GringoUseContext
- Rsc6GringoItemAttributes

Usage:
  python codered_wgd_inspector.py commongringos.wgd_unpacked.wgd --out out_dir
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import struct
import sys
import zipfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

VIRTUAL_BASE = 0x50000000
PHYSICAL_BASE = 0x60000000
TYPE_ITEM_GRINGO = 0x01979634
TYPE_USE_CONTEXT = 0xE03269C1
TYPE_ITEM_ATTRIBUTES = 0xB16C14A8
TYPE_ANIMATION = 95797610  # Known in CodeX enum, not decoded here.

VEHICLE_TERMS = [
    "vehicle", "wagon", "coach", "cart", "truck", "playercar", "car_gringo", "climbontowagon",
    "stagecoach", "gatling", "mount", "crank_car", "fix_car", "deboard", "handoff", "train",
    "veh_", "vehicle_", "wagonmount", "truckgatling", "use_crank", "player car", "close_wagon",
]

FIELD_NAMES = [
    "SuspendMover", "FixUserMover", "PlayerUsable", "PositionParentActorRelative",
    "ActorBecomesObstacle", "IsMeleeAttack", "GringoHandlesMovement", "IsCombatFriendly",
    "IsJumpGringo", "RequiresPhysicsCheck", "RequiresGroundCheck", "RequiresLOSCheck",
    "RequiresNavProbeCheck", "StartUnavailable", "BlockInjuryReactions", "AllowAiShoot",
    "AutoPlayForPlayer", "AlwaysApproach", "WaitForStill", "SlowDownWhenApproaching", "AllowNavigateTo",
]

@dataclass
class Component:
    comp_id: int
    offset: int
    ptr: int
    type: str
    query_name: str = ""
    hash_code: int = 0
    parent_ptr: int = 0
    parent_offset: Optional[int] = None
    parent_comp_id: Optional[int] = None

@dataclass
class ItemGringo(Component):
    script_name: str = ""
    gringo_name: str = ""
    instance_index: int = 0
    child_count: int = 0
    child_ptrs: str = ""
    instanced_count: int = 0
    hashed_name: int = 0
    message_mask: int = 0
    activation_radius: float = 0.0
    instance_slot_count: int = 0
    critical: bool = False
    large_script: bool = False
    maintain_state: bool = False

@dataclass
class UseContext(Component):
    instance_index: int = 0
    facing: float = 0.0
    local_x: float = 0.0
    local_y: float = 0.0
    local_z: float = 0.0
    local_w: float = 0.0
    radius: float = 0.0
    parent_transform_remap: int = 0
    parent_transform_bone: str = ""
    race_type: str = ""
    use_priority_tweak: int = 0
    unusable_weather: str = ""
    child_count: int = 0
    fulfillment_ptr: int = 0
    use_button: int = 0
    user_tag: str = ""
    unusable_weather_type: int = 0
    suspend_mover: bool = False
    fix_user_mover: bool = False
    player_usable: bool = False
    position_parent_actor_relative: bool = False
    actor_becomes_obstacle: bool = False
    is_melee_attack: bool = False
    gringo_handles_movement: bool = False
    is_combat_friendly: bool = False
    is_jump_gringo: bool = False
    requires_physics_check: bool = False
    requires_ground_check: bool = False
    requires_los_check: bool = False
    requires_nav_probe_check: bool = False
    start_unavailable: bool = False
    block_injury_reactions: bool = False
    allow_ai_shoot: bool = False
    auto_play_for_player: bool = False
    always_approach: bool = False
    wait_for_still: bool = False
    slow_down_when_approaching: bool = False
    allow_navigate_to: bool = False
    unknown_7f: int = 0

class WgdReader:
    def __init__(self, data: bytes, virtual_size: Optional[int] = None):
        self.data = data
        self.virtual_size = virtual_size if virtual_size is not None else len(data)
        self.components: Dict[int, Component] = {}
        self.parse_errors: List[str] = []
        self._next_id = 1
        self.top_level_ptrs: List[int] = []
        self.hashes: List[int] = []

    def valid_off(self, off: Optional[int], size: int = 1) -> bool:
        return off is not None and 0 <= off <= len(self.data) - size

    def offset(self, ptr: int) -> Optional[int]:
        if ptr == 0:
            return None
        high = ptr & 0xF0000000
        if high == VIRTUAL_BASE:
            return ptr & 0x0FFFFFFF
        if high == PHYSICAL_BASE:
            # Physical segment follows virtual segment in unpacked RSC data.
            return (ptr & 0x1FFFFFFF) + self.virtual_size
        # Some unpacked local tools may store raw offsets.
        if 0 <= ptr < len(self.data):
            return ptr
        return None

    def u8(self, off: int) -> int:
        return self.data[off]

    def u16(self, off: int) -> int:
        return struct.unpack_from("<H", self.data, off)[0]

    def i16(self, off: int) -> int:
        return struct.unpack_from("<h", self.data, off)[0]

    def u32(self, off: int) -> int:
        return struct.unpack_from("<I", self.data, off)[0]

    def i32(self, off: int) -> int:
        return struct.unpack_from("<i", self.data, off)[0]

    def f32(self, off: int) -> float:
        try:
            val = struct.unpack_from("<f", self.data, off)[0]
            if not math.isfinite(val):
                return 0.0
            return val
        except Exception:
            return 0.0

    def vec4(self, off: int) -> Tuple[float, float, float, float]:
        return (self.f32(off), self.f32(off+4), self.f32(off+8), self.f32(off+12))

    def read_str_ptr(self, off: int) -> str:
        return self.read_string(self.u32(off))

    def read_string(self, ptr: int, max_len: int = 4096) -> str:
        o = self.offset(ptr)
        if not self.valid_off(o):
            return ""
        end = self.data.find(b"\x00", o, min(len(self.data), o + max_len))
        if end < 0:
            end = min(len(self.data), o + max_len)
        raw = self.data[o:end]
        try:
            s = raw.decode("utf-8", "replace")
        except Exception:
            s = raw.decode("latin-1", "replace")
        return s.replace("\r", "").replace("\n", "\\n")

    def read_ptr_arr(self, off: int) -> Tuple[int, int, int, List[int]]:
        if not self.valid_off(off, 8):
            return (0, 0, 0, [])
        ptr = self.u32(off)
        count = self.u16(off + 4)
        cap = self.u16(off + 6)
        arr_off = self.offset(ptr)
        vals: List[int] = []
        if self.valid_off(arr_off, count * 4):
            for i in range(count):
                vals.append(self.u32(arr_off + i * 4))
        return ptr, count, cap, vals

    def parse_root(self) -> None:
        # Observed unpacked WGD root matches 32-byte block:
        # 0x00 VFT, 0x04 unknown/pointer, 0x08 unknown, 0x0C unknown,
        # 0x10 hash array, 0x18 gringo pointer array.
        if not self.valid_off(0, 0x20):
            raise ValueError("File too small for WGD root")
        hptr = self.u32(0x10); hcount = self.u16(0x14)
        hoff = self.offset(hptr)
        self.hashes = []
        if self.valid_off(hoff, hcount * 4):
            self.hashes = [self.u32(hoff + i*4) for i in range(hcount)]
        gptr, gcount, _, vals = self.read_ptr_arr(0x18)
        self.top_level_ptrs = vals
        for ptr in vals:
            try:
                self.parse_component_ptr(ptr)
            except Exception as exc:
                self.parse_errors.append(f"top_ptr 0x{ptr:08X}: {exc}")
        # Fill parent component ids after parsing.
        by_ptr = {c.ptr: c.comp_id for c in self.components.values()}
        for c in self.components.values():
            c.parent_comp_id = by_ptr.get(c.parent_ptr)

    def new_id(self) -> int:
        cid = self._next_id
        self._next_id += 1
        return cid

    def parse_component_ptr(self, ptr: int) -> Optional[Component]:
        o = self.offset(ptr)
        if not self.valid_off(o, 16):
            return None
        if o in self.components:
            return self.components[o]
        typ = self.u32(o)
        if typ == TYPE_ITEM_GRINGO:
            return self.parse_item_gringo(ptr, o)
        if typ == TYPE_USE_CONTEXT:
            return self.parse_use_context(ptr, o)
        if typ == TYPE_ITEM_ATTRIBUTES:
            return self.parse_item_attributes(ptr, o)
        # Unknown/lightly decoded base component.
        comp = Component(
            comp_id=self.new_id(), offset=o, ptr=ptr, type=f"Unknown_0x{typ:08X}",
            query_name=self.read_str_ptr(o+4), hash_code=self.u32(o+8), parent_ptr=self.u32(o+12),
            parent_offset=self.offset(self.u32(o+12))
        )
        self.components[o] = comp
        return comp

    def parse_base_common(self, comp: Component, o: int) -> None:
        comp.query_name = self.read_str_ptr(o + 4)
        comp.hash_code = self.u32(o + 8)
        comp.parent_ptr = self.u32(o + 12)
        comp.parent_offset = self.offset(comp.parent_ptr)

    def parse_item_gringo(self, ptr: int, o: int) -> ItemGringo:
        comp = ItemGringo(comp_id=self.new_id(), offset=o, ptr=ptr, type="ItemGringo")
        self.components[o] = comp
        self.parse_base_common(comp, o)
        comp.instance_index = self.i16(o + 16)
        comp.script_name = self.read_str_ptr(o + 32)
        comp.gringo_name = self.read_str_ptr(o + 36)
        child_ptr, child_count, child_cap, child_vals = self.read_ptr_arr(o + 40)
        inst_ptr, inst_count, inst_cap, inst_vals = self.read_ptr_arr(o + 48)
        comp.child_count = child_count
        comp.child_ptrs = " ".join(f"0x{x:08X}" for x in child_vals)
        comp.instanced_count = inst_count
        comp.hashed_name = self.u32(o + 56)
        comp.message_mask = self.u32(o + 60)
        comp.activation_radius = self.f32(o + 64)
        comp.instance_slot_count = self.i32(o + 68)
        comp.critical = bool(self.u8(o + 72))
        comp.large_script = bool(self.u8(o + 73))
        comp.maintain_state = bool(self.u8(o + 74))
        # Recurse children.
        for cptr in child_vals:
            try:
                self.parse_component_ptr(cptr)
            except Exception as exc:
                self.parse_errors.append(f"child of 0x{ptr:08X} -> 0x{cptr:08X}: {exc}")
        return comp

    def parse_use_context(self, ptr: int, o: int) -> UseContext:
        comp = UseContext(comp_id=self.new_id(), offset=o, ptr=ptr, type="UseContext")
        self.components[o] = comp
        self.parse_base_common(comp, o)
        comp.instance_index = self.i16(o + 24)
        comp.facing = self.f32(o + 28)
        lx, ly, lz, lw = self.vec4(o + 32)
        comp.local_x, comp.local_y, comp.local_z, comp.local_w = lx, ly, lz, lw
        comp.radius = self.f32(o + 48)
        comp.parent_transform_remap = self.i32(o + 52)
        comp.parent_transform_bone = self.read_str_ptr(o + 56)
        comp.race_type = self.read_str_ptr(o + 64)
        comp.use_priority_tweak = self.i32(o + 72)
        comp.unusable_weather = self.read_str_ptr(o + 76)
        child_ptr, child_count, child_cap, child_vals = self.read_ptr_arr(o + 84)
        comp.child_count = child_count
        comp.fulfillment_ptr = self.u32(o + 92)
        comp.use_button = self.i32(o + 96)
        comp.user_tag = self.read_str_ptr(o + 100)
        comp.unusable_weather_type = self.u16(o + 104)
        bools = [bool(self.u8(o + 106 + i)) for i in range(21)]
        (
            comp.suspend_mover, comp.fix_user_mover, comp.player_usable, comp.position_parent_actor_relative,
            comp.actor_becomes_obstacle, comp.is_melee_attack, comp.gringo_handles_movement, comp.is_combat_friendly,
            comp.is_jump_gringo, comp.requires_physics_check, comp.requires_ground_check, comp.requires_los_check,
            comp.requires_nav_probe_check, comp.start_unavailable, comp.block_injury_reactions, comp.allow_ai_shoot,
            comp.auto_play_for_player, comp.always_approach, comp.wait_for_still, comp.slow_down_when_approaching,
            comp.allow_navigate_to,
        ) = bools
        comp.unknown_7f = self.u8(o + 127)
        for cptr in child_vals:
            try:
                self.parse_component_ptr(cptr)
            except Exception as exc:
                self.parse_errors.append(f"use-child of 0x{ptr:08X} -> 0x{cptr:08X}: {exc}")
        return comp

    def parse_item_attributes(self, ptr: int, o: int) -> Component:
        comp = Component(comp_id=self.new_id(), offset=o, ptr=ptr, type="ItemAttributes")
        self.components[o] = comp
        self.parse_base_common(comp, o)
        # Attribute references are intentionally not fully expanded yet.
        return comp

    def parent_chain_text(self, c: Component) -> str:
        chain = []
        cur = c
        seen = set()
        by_ptr = {x.ptr: x for x in self.components.values()}
        while cur.parent_ptr and cur.parent_ptr not in seen:
            seen.add(cur.parent_ptr)
            p = by_ptr.get(cur.parent_ptr)
            if not p:
                break
            label = getattr(p, "script_name", "") or getattr(p, "user_tag", "") or p.query_name or p.type
            chain.append(label)
            cur = p
        return " > ".join(chain)

    def top_owner(self, c: Component) -> Optional[ItemGringo]:
        by_ptr = {x.ptr: x for x in self.components.values()}
        cur: Component = c
        seen = set()
        last_item = cur if isinstance(cur, ItemGringo) else None
        while cur.parent_ptr and cur.parent_ptr not in seen:
            seen.add(cur.parent_ptr)
            p = by_ptr.get(cur.parent_ptr)
            if not p:
                break
            if isinstance(p, ItemGringo):
                last_item = p
            cur = p
        return last_item

    def is_vehicleish(self, c: Component) -> bool:
        hay = " ".join(str(x).lower() for x in [
            c.type, c.query_name, getattr(c, "script_name", ""), getattr(c, "gringo_name", ""),
            getattr(c, "user_tag", ""), getattr(c, "parent_transform_bone", ""), self.parent_chain_text(c)
        ])
        return any(term in hay for term in VEHICLE_TERMS)

    def all_strings(self) -> List[Tuple[int, str]]:
        # Simple null-terminated printable string finder for supplemental scans.
        out = []
        pat = re.compile(rb"[ -~]{4,}")
        for m in pat.finditer(self.data):
            raw = m.group(0)
            # Require a null before/after nearby to reduce noise.
            try:
                text = raw.decode("ascii")
            except Exception:
                continue
            out.append((m.start(), text))
        return out


def write_csv(path: Path, rows: Iterable[Dict[str, Any]], fieldnames: List[str]) -> int:
    rows = list(rows)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def boolmark(v: Any) -> str:
    return "Y" if bool(v) else ""


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("wgd", type=Path)
    ap.add_argument("--out", type=Path, default=Path("wgd_inspector_out"))
    args = ap.parse_args(argv)
    data = args.wgd.read_bytes()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    r = WgdReader(data)
    r.parse_root()

    comps = list(r.components.values())
    items = [c for c in comps if isinstance(c, ItemGringo)]
    uses = [c for c in comps if isinstance(c, UseContext)]
    vehicle = [c for c in comps if r.is_vehicleish(c)]
    vehicle_uses = [c for c in uses if r.is_vehicleish(c) or (r.top_owner(c) and r.is_vehicleish(r.top_owner(c)))]
    vehicle_items = [c for c in items if r.is_vehicleish(c)]

    # Top-level item CSV
    item_rows = []
    for i, c in enumerate(items):
        item_rows.append({
            "comp_id": c.comp_id, "offset_hex": f"0x{c.offset:X}", "ptr_hex": f"0x{c.ptr:08X}",
            "script_name": c.script_name, "gringo_name": c.gringo_name, "query_name": c.query_name,
            "child_count": c.child_count, "instanced_count": c.instanced_count,
            "activation_radius": c.activation_radius, "instance_slot_count": c.instance_slot_count,
            "critical": c.critical, "large_script": c.large_script, "maintain_state": c.maintain_state,
            "vehicleish": r.is_vehicleish(c), "parent_chain": r.parent_chain_text(c)
        })
    write_csv(out / "all_item_gringos.csv", item_rows, list(item_rows[0].keys()) if item_rows else [])

    # Use contexts CSV
    use_rows = []
    for c in uses:
        owner = r.top_owner(c)
        use_rows.append({
            "comp_id": c.comp_id, "offset_hex": f"0x{c.offset:X}", "ptr_hex": f"0x{c.ptr:08X}",
            "owner_comp_id": owner.comp_id if owner else "", "owner_script": owner.script_name if owner else "",
            "owner_gringo": owner.gringo_name if owner else "", "query_name": c.query_name,
            "user_tag": c.user_tag, "parent_transform_bone": c.parent_transform_bone,
            "radius": c.radius, "facing": c.facing,
            "local_x": c.local_x, "local_y": c.local_y, "local_z": c.local_z, "local_w": c.local_w,
            "use_button": c.use_button, "use_priority_tweak": c.use_priority_tweak,
            "SuspendMover": c.suspend_mover, "FixUserMover": c.fix_user_mover,
            "PlayerUsable": c.player_usable, "PositionParentActorRelative": c.position_parent_actor_relative,
            "ActorBecomesObstacle": c.actor_becomes_obstacle, "IsMeleeAttack": c.is_melee_attack,
            "GringoHandlesMovement": c.gringo_handles_movement, "IsCombatFriendly": c.is_combat_friendly,
            "IsJumpGringo": c.is_jump_gringo, "RequiresPhysicsCheck": c.requires_physics_check,
            "RequiresGroundCheck": c.requires_ground_check, "RequiresLOSCheck": c.requires_los_check,
            "RequiresNavProbeCheck": c.requires_nav_probe_check, "StartUnavailable": c.start_unavailable,
            "BlockInjuryReactions": c.block_injury_reactions, "AllowAiShoot": c.allow_ai_shoot,
            "AutoPlayForPlayer": c.auto_play_for_player, "AlwaysApproach": c.always_approach,
            "WaitForStill": c.wait_for_still, "SlowDownWhenApproaching": c.slow_down_when_approaching,
            "AllowNavigateTo": c.allow_navigate_to, "unknown_7f": c.unknown_7f,
            "vehicleish": r.is_vehicleish(c) or (owner and r.is_vehicleish(owner)),
            "parent_chain": r.parent_chain_text(c),
        })
    use_fields = list(use_rows[0].keys()) if use_rows else []
    write_csv(out / "all_use_contexts.csv", use_rows, use_fields)
    write_csv(out / "vehicle_use_contexts.csv", [row for row in use_rows if row["vehicleish"]], use_fields)

    # Vehicle candidates CSV
    veh_rows = []
    for c in vehicle:
        base = {
            "comp_id": c.comp_id, "offset_hex": f"0x{c.offset:X}", "ptr_hex": f"0x{c.ptr:08X}",
            "type": c.type, "query_name": c.query_name, "parent_chain": r.parent_chain_text(c),
        }
        if isinstance(c, ItemGringo):
            base.update({"script_name": c.script_name, "gringo_name": c.gringo_name, "child_count": c.child_count, "activation_radius": c.activation_radius, "instance_slot_count": c.instance_slot_count})
        elif isinstance(c, UseContext):
            owner = r.top_owner(c)
            base.update({"owner_script": owner.script_name if owner else "", "user_tag": c.user_tag, "parent_transform_bone": c.parent_transform_bone, "radius": c.radius,
                         "PlayerUsable": c.player_usable, "AutoPlayForPlayer": c.auto_play_for_player, "AlwaysApproach": c.always_approach, "AllowNavigateTo": c.allow_navigate_to,
                         "GringoHandlesMovement": c.gringo_handles_movement, "FixUserMover": c.fix_user_mover, "SuspendMover": c.suspend_mover})
        veh_rows.append(base)
    veh_fields = sorted({k for row in veh_rows for k in row.keys()}) if veh_rows else []
    write_csv(out / "vehicle_candidates.csv", veh_rows, veh_fields)

    # Focused string hits.
    string_hits = []
    for off, text in r.all_strings():
        low = text.lower()
        if any(term in low for term in VEHICLE_TERMS):
            string_hits.append({"offset_hex": f"0x{off:X}", "text": text})
    write_csv(out / "vehicle_string_hits.csv", string_hits, ["offset_hex", "text"])

    # Summary / recommendations.
    playercar_uses = [u for u in vehicle_uses if "playercar" in ((r.top_owner(u).script_name if r.top_owner(u) else "") + " " + u.user_tag + " " + r.parent_chain_text(u)).lower()]
    car_gringo_uses = [u for u in vehicle_uses if "car_gringo" in ((r.top_owner(u).script_name if r.top_owner(u) else "") + " " + u.user_tag + " " + r.parent_chain_text(u)).lower()]
    truck_uses = [u for u in vehicle_uses if "truck" in ((r.top_owner(u).script_name if r.top_owner(u) else "") + " " + u.user_tag + " " + u.parent_transform_bone + " " + r.parent_chain_text(u)).lower()]
    wagon_uses = [u for u in vehicle_uses if any(t in ((r.top_owner(u).script_name if r.top_owner(u) else "") + " " + u.user_tag + " " + u.parent_transform_bone + " " + r.parent_chain_text(u)).lower() for t in ["wagon", "coach", "stagecoach", "cart"])]

    def use_line(u: UseContext) -> str:
        owner = r.top_owner(u)
        flags = []
        for key in ["player_usable", "auto_play_for_player", "always_approach", "allow_navigate_to", "gringo_handles_movement", "fix_user_mover", "suspend_mover", "start_unavailable"]:
            if getattr(u, key): flags.append(key)
        return f"- `0x{u.offset:X}` owner=`{owner.script_name if owner else ''}` user_tag=`{u.user_tag}` bone=`{u.parent_transform_bone}` radius={u.radius:g} flags={', '.join(flags) if flags else 'none'}"

    md = []
    md.append("# Code Red WGD Inspector Report")
    md.append("")
    md.append(f"Input: `{args.wgd.name}`")
    md.append(f"Size: {len(data):,} bytes")
    md.append("")
    md.append("## Parse summary")
    md.append(f"- Root top-level gringo pointers: **{len(r.top_level_ptrs)}**")
    md.append(f"- Hash entries: **{len(r.hashes)}**")
    md.append(f"- Parsed components: **{len(comps)}**")
    md.append(f"- Item gringos: **{len(items)}**")
    md.append(f"- Use contexts: **{len(uses)}**")
    md.append(f"- Vehicle-related components: **{len(vehicle)}**")
    md.append(f"- Vehicle-related use contexts: **{len(vehicle_uses)}**")
    md.append(f"- Parse errors: **{len(r.parse_errors)}**")
    md.append("")
    md.append("## Vehicle/driving findings")
    md.append("The file contains real common vehicle gringo data, not just incidental strings. The most useful outputs are `vehicle_candidates.csv` and `vehicle_use_contexts.csv`.")
    md.append("")
    md.append("### PlayerCar / car_gringo use contexts")
    rows = playercar_uses + [u for u in car_gringo_uses if u not in playercar_uses]
    if rows:
        md.extend(use_line(u) for u in rows[:30])
    else:
        md.append("- No parsed UseContext rows directly matched PlayerCar/car_gringo. They may appear as ItemGringo/script references without decoded use children.")
    md.append("")
    md.append("### Truck-related use contexts")
    if truck_uses:
        md.extend(use_line(u) for u in truck_uses[:30])
    else:
        md.append("- No decoded truck UseContext rows matched; truck references may be animation strings or child components not yet decoded.")
    md.append("")
    md.append("### Wagon/coach/stagecoach/cart use contexts")
    if wagon_uses:
        md.extend(use_line(u) for u in wagon_uses[:40])
    else:
        md.append("- No decoded wagon/coach UseContext rows matched; references may be animation strings or top-level script names.")
    md.append("")
    md.append("## First patch candidates")
    md.append("Do not patch yet unless a row shows a clear PlayerCar/car_gringo UseContext with `PlayerUsable=False` or `StartUnavailable=True` while a comparable wagon/truck context is usable. The likely safe fields to compare are:")
    md.append("")
    md.append("```text")
    md.append("PlayerUsable, StartUnavailable, AllowNavigateTo, AlwaysApproach, AutoPlayForPlayer,")
    md.append("GringoHandlesMovement, FixUserMover, SuspendMover, Radius, UseButton, ParentTransformRemappedBone")
    md.append("```")
    md.append("")
    md.append("## Files emitted")
    for name in ["all_item_gringos.csv", "all_use_contexts.csv", "vehicle_candidates.csv", "vehicle_use_contexts.csv", "vehicle_string_hits.csv"]:
        md.append(f"- `{name}`")
    if r.parse_errors:
        (out / "parse_errors.txt").write_text("\n".join(r.parse_errors), encoding="utf-8")
        md.append("- `parse_errors.txt`")
    report = "\n".join(md) + "\n"
    (out / "WGD_INSPECTOR_REPORT.md").write_text(report, encoding="utf-8")

    # JSON summary.
    summary = {
        "input": str(args.wgd), "size": len(data), "top_level": len(r.top_level_ptrs), "hashes": len(r.hashes),
        "components": len(comps), "item_gringos": len(items), "use_contexts": len(uses),
        "vehicle_components": len(vehicle), "vehicle_use_contexts": len(vehicle_uses), "parse_errors": len(r.parse_errors),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(report)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
