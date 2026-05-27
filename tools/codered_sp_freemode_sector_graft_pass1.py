#!/usr/bin/env python3
"""SP FreeMode sector graft pass 1 reports.

This pass treats multiplayer/free mode scripts as a content library. It does
not launch MP scripts, patch networking, or write the live game content.rpf.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from codered_wsc.resource import KeyOptions, open_script  # noqa: E402

REPORT_ROOT = ROOT / "reports" / "sp_freemode_sector_graft_pass1"
BUILD_ROOT = ROOT / "build" / "sp_freemode_sector_graft_pass1"
SOURCE_EXTRACT = BUILD_ROOT / "source_wsc_extract"
PASS5_BASE = ROOT / "build" / "mp_content_restore_pass5" / "content_mp_restore_pass5_access_trainer_sectors.rpf"
TARGET_BASE_SHA1 = "91304EBA24B3759AE206783EBE4CA42EA0F2A134"
MAGIC_PS1 = ROOT / "tools" / "codered_magicrdr_wsc_compat.ps1"
POWERSHELL32 = Path(os.environ.get("WINDIR", r"%LOCAL_PATH%")) / "SysWOW64" / "WindowsPowerShell" / "v1.0" / "powershell.exe"

SP_FILES = {
    "release64/pressstart.wsc": SOURCE_EXTRACT / "content" / "release64" / "pressstart.wsc",
    "release64/sp_idle.wsc": SOURCE_EXTRACT / "content" / "release64" / "sp_idle.wsc",
    "release64/main.wsc": SOURCE_EXTRACT / "content" / "release64" / "main.wsc",
    "release64/init/rdr2init.wsc": SOURCE_EXTRACT / "content" / "release64" / "init" / "rdr2init.wsc",
}
MP_FIXED = ROOT / "build" / "mp_script_conversion_probe" / "import_ready_xsc_magicrdr_fixed_wsc" / "content" / "release64" / "multiplayer"
MP_FILES = {
    "multiplayer/freemode/freemode.wsc": MP_FIXED / "freemode" / "freemode.wsc",
    "multiplayer/PR_Multiplayer.wsc": MP_FIXED / "pr_multiplayer.wsc",
    "multiplayer/multiplayer_system_thread.wsc": MP_FIXED / "multiplayer_system_thread.wsc",
    "multiplayer/multiplayer_update_thread.wsc": MP_FIXED / "multiplayer_update_thread.wsc",
}

BLOCKED_MP_CALLS = {
    "net.EnterOnline",
    "TriggerMultiplayerLoad",
    "StartGameWish",
    "freemode.wsc",
    "PR_Multiplayer.wsc",
    "multiplayer_system_thread.wsc",
    "multiplayer_update_thread.wsc",
}
SECTOR_NATIVE_RE = re.compile(r"\b(ENABLE_CHILD_SECTOR|DISABLE_CHILD_SECTOR|ENABLE_WORLD_SECTOR|DISABLE_WORLD_SECTOR)\s*\(([^)]*)\)", re.I)
STRING_RE = re.compile(rb"[\x20-\x7E]{4,}")
TOKEN_RE = re.compile(
    r"(?i)(mp_[a-z0-9_]+|[a-z]{3}_flags[0-9a-z_]*|[a-z0-9_]*(?:sector|spawnvol|spawn|action|territory|region|ambient|base|coop|ffa|platform)[a-z0-9_]*)"
)
KNOWN_SECTOR_NAMES = {
    "mp_tes_coop01ax",
    "mp_tes_coop01bx",
    "mp_tes_coop01cx",
    "mp_tes_coop02x",
    "mp_tes_base01x",
    "mp_gap_minelid01x",
    "mp_fom_coop01x",
    "mp_fom_burntdebris01x",
    "mp_wld_base03x",
    "mp_nos_coop01ax",
    "mp_nos_coop01bx",
    "mp_nos_coop01cx",
    "mp_nos_coop01dx",
    "mp_nos_coop01ex",
    "mp_scr_coop01x",
    "arm_flags01x",
    "chu_flags01x",
    "esc_flags01x",
    "han_flags01x",
    "hen_flags01x",
    "mtp_flags01x",
    "mp_arm_base01x",
    "mp_cas_base01x",
    "mp_pik_base01x",
    "mp_tum_base01x",
    "mp_arm_ffa01x",
    "mp_chu_ffa01x",
    "mp_esc_ffa01x",
    "mp_hen_ffa01x",
    "mp_lsh_ffa01x",
    "mp_pik_ffa01x",
    "mp_upr_ffa01x",
    "mp_chu_platforms01x",
    "mp_mtp_base01x",
    "mp_fom_base01x",
    "mp_fom_ffa01x",
    "mp_wld_base01x",
    "mp_chu_base01x",
}
KNOWN_LOW_RISK = [
    "mp_chu_platforms01x",
    "mp_tes_base01x",
    "mp_arm_base01x",
    "mp_fom_base01x",
    "mp_wld_base01x",
    "mp_chu_base01x",
]


def sha1_file(path: Path) -> str:
    import hashlib

    h = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def likely_region(name: str) -> str:
    lower = name.lower()
    if lower.startswith("mp_") and len(lower.split("_")) >= 2:
        return lower.split("_")[1]
    prefix = lower.split("_")[0]
    return prefix if len(prefix) == 3 else ""


def risk_for(name: str, source_kind: str, call_kind: str) -> str:
    lower = name.lower()
    if any(block.lower() in lower for block in BLOCKED_MP_CALLS):
        return "blocked"
    if lower in KNOWN_LOW_RISK or lower in KNOWN_SECTOR_NAMES:
        return "low"
    if source_kind == "mp" and ("coop" in lower or "ffa" in lower or "base" in lower or "platform" in lower):
        return "medium"
    if call_kind.upper().startswith("DISABLE"):
        return "medium"
    return "review"


def classify_token(name: str) -> str:
    lower = name.lower()
    if "spawnvol" in lower or "spawn" in lower:
        return "spawn_volume"
    if "ambient" in lower:
        return "ambient_world"
    if "territory" in lower or "region" in lower:
        return "region_territory"
    if "action" in lower or "_aa" in lower:
        return "action_area"
    if "sector" in lower or lower.startswith("mp_") or "base" in lower or "coop" in lower or "ffa" in lower or "flags" in lower:
        return "sector"
    return "token"


def decompile_with_magic(path: Path, label: str) -> tuple[Path, dict[str, Any]]:
    out = REPORT_ROOT / "magicrdr_decompiled" / (label.replace("/", "__") + ".c")
    command = [
        str(POWERSHELL32),
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(MAGIC_PS1),
        "-InputPath",
        str(path.resolve()),
        "-Platform",
        "Switch",
        "-DecompiledOut",
        str(out.resolve()),
    ]
    proc = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True, timeout=90, check=False)
    payload = {}
    if proc.stdout.strip():
        try:
            payload = json.loads(proc.stdout.strip().splitlines()[-1])
        except Exception:
            payload = {"ok": False, "error": "could_not_parse_magicrdr_json", "stdout": proc.stdout[-1000:]}
    payload.update({"returncode": proc.returncode, "stderr": proc.stderr[-1000:]})
    return out, payload


def scan_file(label: str, path: Path, source_kind: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows, {"source_file": label, "path": str(path), "exists": False, "magic_ok": False, "error": "missing"}
    decomp, magic = decompile_with_magic(path, label)
    text = decomp.read_text(encoding="utf-8", errors="ignore") if decomp.exists() else ""
    seen: set[tuple[str, str, int]] = set()
    for line_no, line in enumerate(text.splitlines(), start=1):
        for native, args in SECTOR_NATIVE_RE.findall(line):
            strings = re.findall(r'"([^"]+)"', args)
            sector_name = strings[0] if strings else args.strip()
            key = (sector_name.lower(), native.upper(), line_no)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "source_file": label,
                    "source_path": str(path),
                    "source_kind": source_kind,
                    "function_callsite": f"line:{line_no}",
                    "native_call_kind": native.upper(),
                    "sector_name": sector_name,
                    "token_class": classify_token(sector_name),
                    "enabled_or_disabled": "enable" if native.upper().startswith("ENABLE") else "disable",
                    "likely_region": likely_region(sector_name),
                    "mp_or_sp": source_kind,
                    "risk_level": risk_for(sector_name, source_kind, native),
                    "notes": "MagicRDR decompile native call",
                }
            )
        for match in TOKEN_RE.findall(line):
            token = match.strip('"').strip()
            if len(token) < 4:
                continue
            key = (token.lower(), "decompile_token", line_no)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "source_file": label,
                    "source_path": str(path),
                    "source_kind": source_kind,
                    "function_callsite": f"line:{line_no}",
                    "native_call_kind": "string_or_symbol",
                    "sector_name": token,
                    "token_class": classify_token(token),
                    "enabled_or_disabled": "reference",
                    "likely_region": likely_region(token),
                    "mp_or_sp": source_kind,
                    "risk_level": risk_for(token, source_kind, "string"),
                    "notes": "MagicRDR decompile token",
                }
            )
    try:
        resource = open_script(path, KeyOptions(rdr_exe=str(ROOT.parent / "RDR.exe")))
        data = resource.decoded
        decoded_note = "decoded WSC payload"
    except Exception:
        data = path.read_bytes()
        decoded_note = "raw WSC bytes"
    for m in STRING_RE.finditer(data):
        try:
            token = m.group(0).decode("ascii", errors="ignore")
        except Exception:
            continue
        if not TOKEN_RE.fullmatch(token) and not TOKEN_RE.search(token):
            continue
        token = TOKEN_RE.search(token).group(1)
        key = (token.lower(), "decoded_string", m.start())
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "source_file": label,
                "source_path": str(path),
                "source_kind": source_kind,
                "function_callsite": f"decoded_offset:0x{m.start():X}",
                "native_call_kind": "decoded_string",
                "sector_name": token,
                "token_class": classify_token(token),
                "enabled_or_disabled": "reference",
                "likely_region": likely_region(token),
                "mp_or_sp": source_kind,
                "risk_level": risk_for(token, source_kind, "string"),
                    "notes": decoded_note,
            }
        )
    return rows, {"source_file": label, "path": str(path), "exists": True, "magic_ok": bool(magic.get("ok")), "magic": magic}


def build_counterparts(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sp = [r for r in rows if r["source_kind"] == "sp"]
    mp = [r for r in rows if r["source_kind"] == "mp"]
    counterparts: list[dict[str, Any]] = []
    overlap: list[dict[str, Any]] = []
    for m in mp:
        if m["token_class"] not in {"sector", "action_area", "spawn_volume", "ambient_world", "region_territory"}:
            continue
        region = m["likely_region"]
        candidates = [s for s in sp if region and s["likely_region"] == region]
        for s in candidates[:20]:
            counterparts.append(
                {
                    "mp_sector_name": m["sector_name"],
                    "mp_source_file": m["source_file"],
                    "sp_counterpart_candidate": s["sector_name"],
                    "sp_source_file": s["source_file"],
                    "likely_region": region,
                    "confidence": "region-prefix",
                    "recommended_action": "review_before_disable",
                }
            )
        if candidates:
            overlap.append(
                {
                    "likely_region": region,
                    "mp_sector_name": m["sector_name"],
                    "mp_source_file": m["source_file"],
                    "sp_candidate_count": len(candidates),
                    "first_sp_candidates": "; ".join(c["sector_name"] for c in candidates[:6]),
                }
            )
    return counterparts, overlap


def write_recommendations(candidates: list[dict[str, Any]]) -> None:
    lows = [r for r in candidates if r["risk_level"] == "low"]
    mediums = [r for r in candidates if r["risk_level"] == "medium"]
    ordered = lows + mediums
    lines = [
        "# Recommended Sector Test Order",
        "",
        "Do not enter multiplayer and do not launch MP scripts. Test one cloned RPF at a time.",
        "",
        "## First Choices",
        "",
    ]
    for i, row in enumerate(ordered[:12], start=1):
        lines.append(f"{i}. `{row['sector_name']}` from `{row['source_file']}` risk=`{row['risk_level']}` region=`{row['likely_region']}`")
    lines.extend(
        [
            "",
            "## Variant Intent",
            "",
            "- A0: repack control only, no content changes.",
            "- A1: SP WSC no-op/log probe only if a safe authoring slot is available.",
            "- A2: enable exactly one MP sector, recommended first candidate above.",
            "- A3: enable one MP sector and disable one reviewed SP counterpart.",
            "- A4: enable 2-4 same-region MP sectors only after A2/A3 are stable.",
            "- A5: marker/action-area only after sector visibility is proven.",
        ]
    )
    (REPORT_ROOT / "recommended_sector_test_order.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_variant_placeholders(base_found: bool, base_path: str) -> None:
    variants = [
        ("A0_repack_control", "no content changes", "", "", "none", "low"),
        ("A1_sp_wsc_noop_probe", "SP-side no-op/log probe only", "", "", "sp_idle/main/rdr2init late safe point", "review"),
        ("A2_one_mp_sector_only", "enable exactly one low-risk MP sector", "first recommended low-risk candidate", "", "SP-side sector probe", "medium"),
        ("A3_one_mp_sector_plus_sp_counterpart_unload", "enable one MP sector and disable one reviewed SP counterpart", "first recommended low-risk candidate", "one reviewed SP counterpart", "SP-side sector probe", "high"),
        ("A4_small_region_sector_set", "enable 2-4 related MP sectors", "same region set", "", "SP-side sector probe", "high"),
        ("A5_sector_plus_one_blip_or_action_area_marker", "sector plus one marker/action-area", "one proven sector", "", "SP-side sector probe", "high"),
    ]
    rows = []
    for name, expected, enable, disable, launch, risk in variants:
        rows.append(
            {
                "variant_name": name,
                "base_sha1": TARGET_BASE_SHA1,
                "base_path": base_path,
                "base_found": base_found,
                "changed_files": "not built" if not base_found else "pending_safe_wsc_authoring",
                "sector_enabled": enable,
                "sector_disabled": disable,
                "launch_point": launch,
                "expected_behavior": expected,
                "risk": risk,
                "output_rpf_path": "",
                "readback_status": "blocked_base_missing" if not base_found else "not_built_authoring_guard",
                "magicrdr_status": "not_applicable",
            }
        )
    write_csv(REPORT_ROOT / "sector_test_variants.csv", rows)
    write_csv(REPORT_ROOT / "rpf_readback.csv", [])
    write_csv(REPORT_ROOT / "wsc_edit_validation.csv", [])
    write_csv(REPORT_ROOT / "magicrdr_compat.csv", [])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-rpf", default="")
    args = parser.parse_args()
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict[str, Any]] = []
    magic_rows: list[dict[str, Any]] = []
    for label, path in SP_FILES.items():
        rows, magic = scan_file(label, path, "sp")
        all_rows.extend(rows)
        magic_rows.append(magic)
    for label, path in MP_FILES.items():
        rows, magic = scan_file(label, path, "mp")
        all_rows.extend(rows)
        magic_rows.append(magic)
    write_csv(REPORT_ROOT / "sector_inventory_all.csv", all_rows)
    mp_candidates = [
        r
        for r in all_rows
        if (r["source_kind"] == "mp" or r["sector_name"].lower().startswith("mp_") or r["sector_name"].lower() in KNOWN_SECTOR_NAMES)
        and r["token_class"] in {"sector", "action_area", "spawn_volume", "ambient_world", "region_territory"}
        and r["risk_level"] != "blocked"
    ]
    write_csv(REPORT_ROOT / "mp_sector_candidates.csv", mp_candidates)
    counterparts, overlap = build_counterparts(all_rows)
    write_csv(REPORT_ROOT / "sp_sector_counterparts.csv", counterparts)
    write_csv(REPORT_ROOT / "sector_overlap_map.csv", overlap)
    write_csv(REPORT_ROOT / "magicrdr_source_open.csv", magic_rows)
    write_recommendations(mp_candidates)

    base_path = Path(args.base_rpf) if args.base_rpf else None
    if base_path is None or not base_path.exists() or not base_path.is_file():
        base_found = False
        base_label = ""
    else:
        base_found = sha1_file(base_path) == TARGET_BASE_SHA1
        base_label = str(base_path)
    write_variant_placeholders(base_found, base_label)
    lines = [
        "# SP FreeMode Sector Graft Pass 1",
        "",
        "No live `content.rpf`, `RDR.exe`, ASI, trainer, networking, or MP launch changes were made.",
        "",
        f"- Required base SHA1: `{TARGET_BASE_SHA1}`",
        f"- Required base found: `{base_found}`",
        f"- Base path used: `{base_label or 'not found'}`",
        f"- Inventory rows: `{len(all_rows)}`",
        f"- MP sector/action candidates: `{len(mp_candidates)}`",
        f"- SP counterpart candidates: `{len(counterparts)}`",
        "",
        "## Build Status",
        "",
    ]
    if not base_found:
        lines.append("Cloned RPF variants were not built because the exact `A_disable_update_thread_refs.rpf` base was not found locally. This is intentional; the pass does not silently substitute a different archive.")
    else:
        lines.append("Base archive was found, but WSC authoring/insertion remains gated pending a safe single-sector carrier. No MP launch path was added.")
    lines.extend(
        [
            "",
            "## Files Scanned",
            "",
        ]
    )
    for row in magic_rows:
        lines.append(f"- `{row['source_file']}` exists=`{row['exists']}` MagicRDR=`{row.get('magic_ok')}`")
    lines.extend(
        [
            "",
            "## Next Safe Step",
            "",
            "Place or point the tool at the exact `A_disable_update_thread_refs.rpf` base, then build A0 only first. After A0 boots, create a single SP-side sector carrier for the first recommended low-risk candidate.",
        ]
    )
    (REPORT_ROOT / "pass_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"inventory_rows": len(all_rows), "mp_candidates": len(mp_candidates), "counterparts": len(counterparts), "base_found": base_found, "reports": str(REPORT_ROOT)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
