#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from codered_wsi_explorer import RPF6, rdr_hash, sha1, zstd_dec


CODE_RED_ROOT = Path(__file__).resolve().parents[1]
GAME_ROOT = CODE_RED_ROOT.parent / "game"
DEFAULT_OUT_DIR = CODE_RED_ROOT / "logs" / "car_truck_inventory"

REFERENCE_ROOTS = [
    ("rdr1_mods_root", GAME_ROOT / "BACKUP BEFORE MODDING" / "rdr1" / "mods" / "root"),
    ("driveable_vehicles_backup", GAME_ROOT / "BACKUP BEFORE MODDING" / "Game - Driveable vehicles +"),
    ("codered_stock_vehicle_files", CODE_RED_ROOT / "related_apps" / "CodeRED_Tuner" / "stock_vehicle_files"),
    (
        "codered_driveable_vehicles_mod",
        CODE_RED_ROOT / "related_apps" / "CodeRED_Tuner" / "Mods" / "Game - Driveable vehicles +",
    ),
]

TARGETS_BY_ARCHIVE = {
    "tune_d11generic.rpf": {
        "tune_metadata": [
            "car01x.vehsim",
            "car01x.vehinput",
            "car01x.vehmodel",
            "car01x.vehgyro",
            "car01x.vehstuck",
            "truck01x.vehsim",
            "truck01x.vehinput",
            "truck01x.vehmodel",
            "truck01x.vehgyro",
            "truck01x.vehstuck",
        ],
        "locsets": ["locset_car01.xml", "locset_truck01.xml"],
        "templates": [
            "template_vehicle.xml",
            "template_draftvehicle.xml",
            "template_vehiclecar01.xml",
            "template_vehicletruck01.xml",
        ],
        "input_profiles": ["input_car.xml"],
        "materials": ["veh_car_body_metal.mtl", "veh_car_wheel_rubber.mtl"],
    },
    "fragments.rpf": {
        "fragments_models": ["car01x.wft", "truck01x.wft"],
        "textures": ["car01x_hilod.wtd", "truck01x_hilod.wtd"],
    },
    "navres.rpf": {
        "nav": ["car01x.wnm", "truck01x.wnm"],
    },
    "camera.rpf": {
        "camera": [
            "cinvehiclewindowleft.txt",
            "cinvehicleskyright.txt",
            "cinvehiclewindowright.txt",
            "cinvehicletracking.txt",
            "cinvehiclewheel.txt",
            "cinvehiclefronttobackjb.txt",
            "cinvehiclestaticground.txt",
            "cinvehiclestaticgroundfast.txt",
            "cinvehiclepassengers.txt",
            "cinvehicleskyleft.txt",
            "mountwagon02left.txt",
            "mountwagon02right.txt",
            "mountwagondriver.txt",
            "mountwagonshotgun.txt",
            "wagongatlingvehenter.txt",
        ],
    },
    "content.rpf": {
        "scripts": [
            "car_gringo.wsc",
            "playercar.wsc",
            "vehicle_generator.wsc",
            "gen_vehicle_brain.wsc",
            "carcrank_gringo.wsc",
            "traincar_gringo.wsc",
            "traincarbaggage_gringo.wsc",
            "traincarcaboose_gringo.wsc",
            "traincarsteamer_gringo.wsc",
            "traincarwood_gringo.wsc",
            "traincarbox01_gringo.wsc",
            "traincarbox02_gringo.wsc",
            "traincarbox03_gringo.wsc",
            "traincarbox04_gringo.wsc",
            "traincarbox05_gringo.wsc",
            "traincarcattle_gringo.wsc",
            "traincararmored_gringo.wsc",
            "traincarflat_gringo.wsc",
        ],
    },
}

TEXT_EXTS = {
    ".xml",
    ".txt",
    ".wsc",
    ".vehsim",
    ".vehinput",
    ".vehmodel",
    ".vehgyro",
    ".vehstuck",
    ".vehdraft",
    ".refgroup",
    ".mtl",
}

REFERENCE_CONTENT_PATTERNS = [
    "car01x",
    "truck01x",
    "locset_car01",
    "locset_truck01",
    "template_vehiclecar01",
    "template_vehicletruck01",
    "carcamera",
    "car_passenger",
    "cinvehicle",
]

VALUE_KEYS = [
    "Mass",
    "Size",
    "InertiaBox",
    "ModelOffset",
    "CenterOfMass",
    "BoundGravity",
    "BoundElasticity",
    "BoundFriction",
    "MaxHorsePower",
    "IdleRPM",
    "OptRPM",
    "MaxRPM",
    "BoostDuration",
    "BoostTorque",
    "NumGears",
    "HighGearMPH",
    "LowGearMPH",
    "RevGearMPH",
    "SSSValue",
    "SSSThreshold",
    "AutoReverseSpeed",
    "VehicleType",
    "LocationSetName",
    "VehicleFaction",
    "m_BoomCameraTuningName",
    "m_GameCameraPassengerArcOverrideName",
    "m_GameCameraPassengerHolsteredArcOverrideName",
    "m_GameCameraPassengerZoomArcOverrideName",
    "m_CinematicShotList",
]

KNOWN_CATEGORY_BY_NAME: dict[str, str] = {}
for archive_groups in TARGETS_BY_ARCHIVE.values():
    for category, names in archive_groups.items():
        for name in names:
            KNOWN_CATEGORY_BY_NAME[name.lower()] = category


@dataclass
class LiveEntry:
    category: str
    archive: str
    archive_path: str
    entry_index: int
    hash_name: str
    hash_value: str
    guessed_name: str
    entry_path: str
    offset: int
    stored_size: int
    total_size: int
    resource: bool
    resource_type: int | None
    compressed: bool
    raw_sha1: str
    decoded_sha1: str | None
    decoded_size: int | None
    decode_status: str
    reference_path: str | None
    reference_sha1: str | None
    raw_sha1_matches_reference: bool | None
    decoded_sha1_matches_reference: bool | None
    metadata: dict


@dataclass
class ReferenceEntry:
    category: str
    root_label: str
    root_path: str
    path: str
    relative_path: str
    name: str
    extension: str
    size: int
    sha1: str
    match_reason: str
    metadata: dict


def rel_display(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def file_sha1(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def decode_live_payload(entry, raw: bytes) -> tuple[bytes | None, str]:
    if not entry.compressed:
        return raw, "plain"
    if entry.resource:
        return None, "compressed_resource_not_decoded"
    try:
        return zstd_dec(raw), "zstd_decoded"
    except Exception as first_exc:
        # RPF text payloads often omit the zstd content-size header; the TOC
        # still carries the expected inflated size.
        try:
            import zstandard as zstd

            return zstd.ZstdDecompressor().decompress(raw, max_output_size=entry.total), "zstd_decoded_with_toc_size"
        except Exception as exc:
            return None, f"zstd_decode_failed: {first_exc}; toc_size_retry_failed: {exc}"


def attrs_to_dict(elem: ET.Element) -> dict:
    if "value" in elem.attrib:
        return {"value": elem.attrib["value"], **{k: v for k, v in elem.attrib.items() if k != "value"}}
    if elem.attrib:
        return dict(elem.attrib)
    text = (elem.text or "").strip()
    return {"text": text} if text else {}


def extract_xml_metadata(text: str) -> dict:
    metadata: dict = {}
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return metadata

    metadata["root_tag"] = root.tag
    picked: dict[str, list[dict]] = {}
    locators: list[str] = []
    location_names: list[str] = []

    for elem in root.iter():
        if elem.tag in VALUE_KEYS:
            picked.setdefault(elem.tag, []).append(attrs_to_dict(elem))
        if elem.tag in {"Name", "AttachmentLocator", "Target", "LocationSetName"}:
            text_value = (elem.text or elem.attrib.get("value", "")).strip()
            if text_value:
                if elem.tag == "Name":
                    location_names.append(text_value)
                else:
                    locators.append(text_value)
        if elem.tag.endswith("Camera") or "Camera" in elem.tag:
            data = attrs_to_dict(elem)
            if data:
                picked.setdefault(elem.tag, []).append(data)

    if picked:
        metadata["picked_values"] = picked
    if location_names:
        metadata["names"] = sorted(set(location_names))
    if locators:
        metadata["locators"] = sorted(set(locators))
    return metadata


def extract_regex_metadata(text: str) -> dict:
    metadata: dict = {}
    actor = re.search(r'<actor\s+[^>]*name="([^"]+)"', text, re.I)
    if actor:
        metadata["actor_name"] = actor.group(1)
    for key in VALUE_KEYS:
        hits = re.findall(rf'<{re.escape(key)}\b([^>]*)/?>', text, re.I)
        if hits:
            metadata.setdefault("picked_values", {})[key] = [hit.strip() for hit in hits]
    camera_names = sorted(set(re.findall(r'value="([^"]*(?:Camera|Passenger|CinVehicle)[^"]*)"', text, re.I)))
    if camera_names:
        metadata["camera_related_values"] = camera_names
    return metadata


def extract_metadata(path_or_name: str, data: bytes | None) -> dict:
    if not data:
        return {}
    name = path_or_name.lower()
    if not (name.endswith(tuple(TEXT_EXTS)) or b"<" in data[:128]):
        return {}
    text = data.decode("utf-8", "replace")
    metadata = extract_xml_metadata(text)
    metadata.update({k: v for k, v in extract_regex_metadata(text).items() if k not in metadata})
    return metadata


def build_reference_index(reference_entries: list[ReferenceEntry]) -> dict[str, list[ReferenceEntry]]:
    by_name: dict[str, list[ReferenceEntry]] = {}
    for entry in reference_entries:
        by_name.setdefault(entry.name.lower(), []).append(entry)
    return by_name


def target_name_map() -> dict[int, tuple[str, str]]:
    output: dict[int, tuple[str, str]] = {}
    for archive_groups in TARGETS_BY_ARCHIVE.values():
        for category, names in archive_groups.items():
            for name in names:
                output[rdr_hash(name)] = (name, category)
    return output


def collect_reference_entries() -> list[ReferenceEntry]:
    wanted_names = set(KNOWN_CATEGORY_BY_NAME)
    content_re = re.compile("|".join(re.escape(p) for p in REFERENCE_CONTENT_PATTERNS), re.I)
    entries: list[ReferenceEntry] = []

    for label, root in REFERENCE_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            lower_name = path.name.lower()
            category = KNOWN_CATEGORY_BY_NAME.get(lower_name, "reference")
            reasons: list[str] = []
            data: bytes | None = None
            if lower_name in wanted_names:
                reasons.append("known_target_filename")
            elif "car01" in lower_name or "truck01" in lower_name:
                reasons.append("car_truck_filename")
                if lower_name.endswith((".wft", ".cft")):
                    category = "fragments_models"
                elif lower_name.endswith((".wtd", ".ctd", ".dds")):
                    category = "textures"
                elif lower_name.endswith(".wnm"):
                    category = "nav"
                elif lower_name.startswith("locset_"):
                    category = "locsets"
                elif lower_name.startswith("template_"):
                    category = "templates"
                elif ".veh" in lower_name:
                    category = "tune_metadata"
            elif path.suffix.lower() in TEXT_EXTS:
                try:
                    data = path.read_bytes()
                except OSError:
                    data = None
                if data is not None and content_re.search(data.decode("utf-8", "ignore")):
                    reasons.append("text_reference")
                    if lower_name.startswith("template_"):
                        category = "templates"
                    elif lower_name.startswith("locset_"):
                        category = "locsets"
                    elif lower_name.endswith(".wsc"):
                        category = "scripts"
            if not reasons:
                continue
            if data is None:
                try:
                    data = path.read_bytes()
                except OSError:
                    data = b""
            entries.append(
                ReferenceEntry(
                    category=category,
                    root_label=label,
                    root_path=str(root),
                    path=str(path),
                    relative_path=rel_display(path, root),
                    name=path.name,
                    extension=path.suffix.lower(),
                    size=path.stat().st_size,
                    sha1=hashlib.sha1(data).hexdigest(),
                    match_reason="+".join(reasons),
                    metadata=extract_metadata(path.name, data),
                )
            )
    return sorted(entries, key=lambda e: (e.category, e.name.lower(), e.path.lower()))


def choose_reference(name: str, refs_by_name: dict[str, list[ReferenceEntry]]) -> ReferenceEntry | None:
    candidates = refs_by_name.get(name.lower(), [])
    if not candidates:
        return None
    preferred = [
        "codered_stock_vehicle_files",
        "codered_driveable_vehicles_mod",
        "driveable_vehicles_backup",
        "rdr1_mods_root",
    ]
    return sorted(candidates, key=lambda e: (preferred.index(e.root_label) if e.root_label in preferred else 99, e.path))[0]


def collect_live_entries(reference_entries: list[ReferenceEntry]) -> tuple[list[LiveEntry], list[str]]:
    refs_by_name = build_reference_index(reference_entries)
    hash_targets = target_name_map()
    entries: list[LiveEntry] = []
    errors: list[str] = []

    for archive_name in TARGETS_BY_ARCHIVE:
        archive_path = GAME_ROOT / archive_name
        if not archive_path.exists():
            errors.append(f"missing archive: {archive_path}")
            continue
        try:
            rpf = RPF6(archive_path)
        except Exception as exc:
            errors.append(f"could not parse {archive_path}: {exc}")
            continue
        for entry in rpf.files():
            target = hash_targets.get(entry.name_hash)
            if not target:
                continue
            guessed_name, category = target
            raw = rpf.slot(entry)
            decoded, decode_status = decode_live_payload(entry, raw)
            ref = choose_reference(guessed_name, refs_by_name)
            ref_sha1 = ref.sha1 if ref else None
            decoded_sha1 = sha1(decoded) if decoded is not None else None
            entries.append(
                LiveEntry(
                    category=category,
                    archive=archive_name,
                    archive_path=str(archive_path),
                    entry_index=entry.index,
                    hash_name=entry.name,
                    hash_value=f"0x{entry.name_hash:08X}",
                    guessed_name=guessed_name,
                    entry_path=entry.path,
                    offset=entry.offset,
                    stored_size=entry.size,
                    total_size=entry.total,
                    resource=entry.resource,
                    resource_type=entry.resource_type,
                    compressed=entry.compressed,
                    raw_sha1=sha1(raw),
                    decoded_sha1=decoded_sha1,
                    decoded_size=len(decoded) if decoded is not None else None,
                    decode_status=decode_status,
                    reference_path=ref.path if ref else None,
                    reference_sha1=ref_sha1,
                    raw_sha1_matches_reference=(sha1(raw) == ref_sha1) if ref_sha1 else None,
                    decoded_sha1_matches_reference=(decoded_sha1 == ref_sha1) if decoded_sha1 and ref_sha1 else None,
                    metadata=extract_metadata(guessed_name, decoded if decoded is not None else raw),
                )
            )
    return sorted(entries, key=lambda e: (e.category, e.archive, e.guessed_name)), errors


def grouped_counts(rows: Iterable[object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        category = getattr(row, "category")
        counts[category] = counts.get(category, 0) + 1
    return dict(sorted(counts.items()))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def render_markdown(report: dict) -> str:
    lines = [
        "# Code RED Car/Truck RPF Metadata Inventory",
        "",
        f"Generated: {report['generated_at']}",
        f"Game root: `{report['game_root']}`",
        "",
        "## Summary",
        "",
        f"- Live RPF matches: {len(report['live_entries'])}",
        f"- Extracted/reference matches: {len(report['reference_entries'])}",
        f"- Live categories: {json.dumps(report['summary']['live_by_category'], sort_keys=True)}",
        f"- Reference categories: {json.dumps(report['summary']['references_by_category'], sort_keys=True)}",
        "",
        "## Live RPF Entries",
        "",
        "| Category | Archive | Name | Index | Hash | Size | Compressed | Decode | Reference Match |",
        "|---|---|---:|---:|---|---:|---|---|---|",
    ]
    for row in report["live_entries"]:
        match = row["decoded_sha1_matches_reference"]
        if match is None:
            match = row["raw_sha1_matches_reference"]
        match_text = "n/a" if match is None else str(bool(match)).lower()
        lines.append(
            "| {category} | {archive} | `{guessed_name}` | {entry_index} | `{hash_name}` | {stored_size} | {compressed} | {decode_status} | {match} |".format(
                **row, match=match_text
            )
        )
    lines.extend(["", "## Extracted Reference Highlights", ""])
    for category, count in report["summary"]["references_by_category"].items():
        lines.append(f"- {category}: {count}")
    lines.extend(["", "## Notes", ""])
    lines.append("- Live RPF names that are stored as hashes are resolved by RDR name hash against known extracted filenames.")
    lines.append("- Compressed resource entries are identified but not deep-decoded unless they are plain zstd non-resource payloads.")
    lines.append("- SHA1 mismatches are expected when extracted reference files come from older or modified roots.")
    if report["errors"]:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {err}" for err in report["errors"])
    return "\n".join(lines) + "\n"


def validate(report: dict) -> list[str]:
    live_names = {(row["archive"], row["guessed_name"]) for row in report["live_entries"]}
    required = [
        ("tune_d11generic.rpf", "car01x.vehsim"),
        ("tune_d11generic.rpf", "car01x.vehinput"),
        ("tune_d11generic.rpf", "car01x.vehmodel"),
        ("tune_d11generic.rpf", "car01x.vehgyro"),
        ("tune_d11generic.rpf", "car01x.vehstuck"),
        ("tune_d11generic.rpf", "truck01x.vehsim"),
        ("tune_d11generic.rpf", "truck01x.vehinput"),
        ("tune_d11generic.rpf", "truck01x.vehmodel"),
        ("tune_d11generic.rpf", "truck01x.vehgyro"),
        ("tune_d11generic.rpf", "truck01x.vehstuck"),
        ("tune_d11generic.rpf", "locset_car01.xml"),
        ("tune_d11generic.rpf", "locset_truck01.xml"),
        ("fragments.rpf", "car01x.wft"),
        ("fragments.rpf", "car01x_hilod.wtd"),
        ("fragments.rpf", "truck01x.wft"),
        ("fragments.rpf", "truck01x_hilod.wtd"),
        ("navres.rpf", "car01x.wnm"),
        ("navres.rpf", "truck01x.wnm"),
        ("content.rpf", "car_gringo.wsc"),
        ("content.rpf", "playercar.wsc"),
        ("content.rpf", "vehicle_generator.wsc"),
        ("content.rpf", "gen_vehicle_brain.wsc"),
    ]
    missing = [f"{archive}:{name}" for archive, name in required if (archive, name) not in live_names]
    return missing


def build_report() -> dict:
    reference_entries = collect_reference_entries()
    live_entries, errors = collect_live_entries(reference_entries)
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "game_root": str(GAME_ROOT),
        "reference_roots": [{"label": label, "path": str(path), "exists": path.exists()} for label, path in REFERENCE_ROOTS],
        "summary": {
            "live_by_category": grouped_counts(live_entries),
            "references_by_category": grouped_counts(reference_entries),
        },
        "live_entries": [asdict(entry) for entry in live_entries],
        "reference_entries": [asdict(entry) for entry in reference_entries],
        "errors": errors,
    }
    report["validation_missing"] = validate(report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inventory car01x/truck01x live RPF metadata and extracted references.")
    parser.add_argument("--outdir", default=str(DEFAULT_OUT_DIR), help="Output folder for JSON/CSV/Markdown reports.")
    args = parser.parse_args(argv)

    report = build_report()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    json_path = outdir / "car_truck_inventory.json"
    md_path = outdir / "car_truck_inventory.md"
    live_csv = outdir / "live_rpf_entries.csv"
    ref_csv = outdir / "reference_entries.csv"

    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    write_csv(
        live_csv,
        report["live_entries"],
        [
            "category",
            "archive",
            "entry_index",
            "hash_name",
            "hash_value",
            "guessed_name",
            "entry_path",
            "offset",
            "stored_size",
            "total_size",
            "resource",
            "resource_type",
            "compressed",
            "decode_status",
            "decoded_size",
            "raw_sha1",
            "decoded_sha1",
            "reference_path",
            "reference_sha1",
            "raw_sha1_matches_reference",
            "decoded_sha1_matches_reference",
        ],
    )
    write_csv(
        ref_csv,
        report["reference_entries"],
        [
            "category",
            "root_label",
            "path",
            "relative_path",
            "name",
            "extension",
            "size",
            "sha1",
            "match_reason",
        ],
    )

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Wrote {live_csv}")
    print(f"Wrote {ref_csv}")
    if report["validation_missing"]:
        print("Missing required live entries:")
        for item in report["validation_missing"]:
            print(f"  - {item}")
        return 2
    if report["errors"]:
        print("Completed with non-fatal errors:")
        for item in report["errors"]:
            print(f"  - {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
