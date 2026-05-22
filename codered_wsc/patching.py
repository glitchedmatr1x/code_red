"""Recipe loading and same-size decoded script patches."""
from __future__ import annotations

import difflib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .analysis import ensure_dir, write_csv, write_json
from .resource import ResourceError, ScriptResource, repack_script, sha256


SUPPORTED_PATCHES = {"replace_enum_operand", "replace_bytes", "same_length_string_replace"}
PLANNED_PATCHES = {
    "population_actor_pool_replace",
    "population_vehicle_pool_replace",
    "flip_boolean_constant",
    "nop_instruction",
    "force_function_return",
    "disable_branch",
}


class PatchError(RuntimeError):
    """Raised when a patch recipe cannot be applied conservatively."""


@dataclass
class DecodedEdit:
    patch_type: str
    offset: int
    before: bytes
    after: bytes
    note: str

    def csv_row(self) -> dict[str, Any]:
        return {
            "type": self.patch_type,
            "offset": self.offset,
            "offset_hex": f"0x{self.offset:X}",
            "size": len(self.before),
            "before_hex": self.before.hex(" ").upper(),
            "after_hex": self.after.hex(" ").upper(),
            "note": self.note,
        }


def load_recipe(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - environment failure
        raise PatchError("YAML recipes require the Python package 'PyYAML'") from exc
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PatchError(f"Recipe must be a YAML mapping: {path}")
    payload.setdefault("patches", [])
    if not isinstance(payload["patches"], list):
        raise PatchError("Recipe patches must be a list")
    return payload


def validate_recipe(recipe: dict[str, Any]) -> dict[str, Any]:
    patch_types = [str(patch.get("type", "")) for patch in recipe.get("patches", []) if isinstance(patch, dict)]
    unsupported = [patch_type for patch_type in patch_types if patch_type not in SUPPORTED_PATCHES]
    return {
        "name": recipe.get("name", ""),
        "patch_count": len(patch_types),
        "supported_patch_types": sorted(set(patch_types) & SUPPORTED_PATCHES),
        "planned_patch_types": sorted(set(unsupported) & PLANNED_PATCHES),
        "unknown_patch_types": sorted(set(unsupported) - PLANNED_PATCHES),
        "ready": not unsupported and bool(patch_types),
    }


def parse_int(value: Any, label: str) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError as exc:
            raise PatchError(f"{label} is not an integer: {value}") from exc
    raise PatchError(f"{label} is not an integer: {value!r}")


def parse_hex(value: Any, label: str) -> bytes:
    if not isinstance(value, str):
        raise PatchError(f"{label} must be hex text")
    try:
        return bytes.fromhex(value.replace(",", " "))
    except ValueError as exc:
        raise PatchError(f"{label} is not valid hex: {value}") from exc


def validate_required_strings(decoded: bytes, recipe: dict[str, Any]) -> list[str]:
    expected = recipe.get("input_expected", {}).get("strings_required", [])
    missing = [term for term in expected if str(term).encode("ascii", errors="ignore") not in decoded]
    if missing:
        raise PatchError(f"Recipe required strings missing from decoded input: {missing}")
    return [str(term) for term in expected]


def replace_at(data: bytearray, offset: int, before: bytes, after: bytes, patch_type: str, note: str) -> DecodedEdit:
    if len(before) != len(after):
        raise PatchError(f"{patch_type} would change decoded length at 0x{offset:X}")
    if offset < 0 or offset + len(before) > len(data):
        raise PatchError(f"{patch_type} range 0x{offset:X}..0x{offset + len(before):X} is outside decoded bytes")
    actual = bytes(data[offset : offset + len(before)])
    if actual != before:
        raise PatchError(f"{patch_type} expected {before.hex(' ')} at 0x{offset:X}, found {actual.hex(' ')}")
    data[offset : offset + len(after)] = after
    return DecodedEdit(patch_type, offset, before, after, note)


def enum_bytes(value: int, width: int, endian: str) -> bytes:
    if width not in (1, 2, 4):
        raise PatchError(f"Enum width {width} is not safe in milestone one")
    if value < 0 or value >= 1 << (width * 8):
        raise PatchError(f"Enum value {value} does not fit {width} bytes")
    order = "big" if endian in ("big", "be") else "little" if endian in ("little", "le") else ""
    if not order:
        raise PatchError(f"Enum endian must be big/be or little/le, got {endian}")
    return value.to_bytes(width, order)


def apply_recipe(decoded: bytes, recipe: dict[str, Any]) -> tuple[bytes, list[DecodedEdit], list[str]]:
    status = validate_recipe(recipe)
    if status["planned_patch_types"] or status["unknown_patch_types"]:
        raise PatchError(
            "Recipe contains patch types not implemented safely yet: "
            + ", ".join(status["planned_patch_types"] + status["unknown_patch_types"])
        )
    required_strings = validate_required_strings(decoded, recipe)
    output = bytearray(decoded)
    edits: list[DecodedEdit] = []
    for ordinal, patch in enumerate(recipe.get("patches", []), start=1):
        if not isinstance(patch, dict):
            raise PatchError(f"Patch #{ordinal} must be a mapping")
        patch_type = str(patch.get("type", ""))
        if patch_type == "replace_enum_operand":
            offset = parse_int(patch.get("offset"), "replace_enum_operand offset")
            width = parse_int(patch.get("width", 2), "replace_enum_operand width")
            endian = str(patch.get("endian", "big"))
            before = enum_bytes(parse_int(patch.get("expected"), "replace_enum_operand expected"), width, endian)
            after = enum_bytes(parse_int(patch.get("value"), "replace_enum_operand value"), width, endian)
            edits.append(replace_at(output, offset, before, after, patch_type, f"enum {int.from_bytes(before, 'big')} -> {int.from_bytes(after, 'big')}"))
        elif patch_type == "replace_bytes":
            offset = parse_int(patch.get("offset"), "replace_bytes offset")
            edits.append(
                replace_at(
                    output,
                    offset,
                    parse_hex(patch.get("expected_hex", ""), "replace_bytes expected_hex"),
                    parse_hex(patch.get("hex", ""), "replace_bytes hex"),
                    patch_type,
                    "exact decoded byte replacement",
                )
            )
        elif patch_type == "same_length_string_replace":
            old = str(patch.get("find", "")).encode(str(patch.get("encoding", "ascii")))
            new = str(patch.get("replace", "")).encode(str(patch.get("encoding", "ascii")))
            if not old or len(old) != len(new):
                raise PatchError("same_length_string_replace requires equal non-zero byte lengths")
            occurrence = patch.get("occurrence", "first")
            offsets: list[int] = []
            start = 0
            while True:
                offset = bytes(output).find(old, start)
                if offset < 0:
                    break
                offsets.append(offset)
                start = offset + len(old)
            if occurrence == "first":
                offsets = offsets[:1]
            elif occurrence != "all":
                index = parse_int(occurrence, "same_length_string_replace occurrence") - 1
                offsets = offsets[index : index + 1]
            if not offsets:
                raise PatchError(f"same_length_string_replace did not find {old!r}")
            edits.extend(replace_at(output, offset, old, new, patch_type, f"{old!r} -> {new!r}") for offset in offsets)
        else:
            raise PatchError(f"Patch type is not supported: {patch_type}")
    return bytes(output), edits, required_strings


def byte_diff_rows(before: bytes, after: bytes) -> list[dict[str, Any]]:
    if len(before) != len(after):
        raise PatchError("Decoded diff expects same-length byte arrays")
    rows: list[dict[str, Any]] = []
    for offset, (old, new) in enumerate(zip(before, after)):
        if old != new:
            rows.append({"offset": offset, "offset_hex": f"0x{offset:X}", "before_hex": f"{old:02X}", "after_hex": f"{new:02X}"})
    return rows


def hex_lines(data: bytes, width: int = 16) -> list[str]:
    return [f"{offset:08X}: {data[offset:offset + width].hex(' ').upper()}" for offset in range(0, len(data), width)]


def write_patch_bundle(resource: ScriptResource, recipe_path: Path, recipe: dict[str, Any], out_file: Path) -> dict[str, Any]:
    patched_decoded, edits, required_strings = apply_recipe(resource.decoded, recipe)
    output, repack = repack_script(resource, patched_decoded)
    ensure_dir(out_file.parent)
    report_dir = out_file.parent / f"{out_file.stem}_patch"
    ensure_dir(report_dir)
    out_file.write_bytes(output)
    backup = report_dir / f"{resource.path.name}.original_backup"
    backup.write_bytes(resource.original)
    (report_dir / "decompressed_original.bin").write_bytes(resource.decoded)
    (report_dir / "decompressed_patched.bin").write_bytes(patched_decoded)
    diff_rows = byte_diff_rows(resource.decoded, patched_decoded)
    write_csv(report_dir / "binary_patch.csv", [edit.csv_row() for edit in edits])
    (report_dir / "binary.diff.txt").write_text("\n".join(json.dumps(row, sort_keys=True) for row in diff_rows) + "\n", encoding="utf-8")
    decompressed_diff = difflib.unified_diff(
        hex_lines(resource.decoded),
        hex_lines(patched_decoded),
        fromfile="decompressed_original.bin",
        tofile="decompressed_patched.bin",
        lineterm="",
    )
    (report_dir / "decompressed.diff.txt").write_text("\n".join(decompressed_diff) + "\n", encoding="utf-8")
    expected_offsets = {
        edit.offset + index
        for edit in edits
        for index, (old, new) in enumerate(zip(edit.before, edit.after))
        if old != new
    }
    actual_offsets = {row["offset"] for row in diff_rows}
    no_unrelated = expected_offsets == actual_offsets
    validation = {
        "resource_reopens": repack["validate_ok"],
        "roundtrip_decompress": repack["validate_ok"],
        "decoded_size_unchanged": len(resource.decoded) == len(patched_decoded),
        "no_unrelated_decoded_bytes_changed": no_unrelated,
        "required_strings_present_before_patch": required_strings,
        "require_strings_unchanged": not any(edit.patch_type == "same_length_string_replace" for edit in edits),
        "note": "String-table rebuild is not implemented. Same-length string replacements are explicit recipe operations.",
    }
    if not all((validation["resource_reopens"], validation["decoded_size_unchanged"], no_unrelated)):
        raise ResourceError("Patch validation failed before manifest completion")
    manifest = {
        "tool": "codered_wsc",
        "recipe": str(recipe_path),
        "recipe_name": recipe.get("name", ""),
        "input": str(resource.path),
        "input_sha256": sha256(resource.original),
        "output": str(out_file),
        "output_sha256": sha256(output),
        "report_dir": str(report_dir),
        "decoded_original_sha256": sha256(resource.decoded),
        "decoded_patched_sha256": sha256(patched_decoded),
        "edits": [edit.csv_row() for edit in edits],
        "repack": repack,
        "validation": validation,
    }
    write_json(report_dir / "manifest.json", manifest)
    patch_report = [
        "# Code RED Script Patch Report",
        "",
        f"- Input: `{resource.path}`",
        f"- Output: `{out_file}`",
        f"- Recipe: `{recipe_path}`",
        f"- Decoded same-size edits: `{len(edits)}`",
        f"- Decoded changed bytes: `{len(diff_rows)}`",
        f"- Repack mode: `{repack['fit_mode']}`",
        "",
        "This bundle records decoded byte changes and rebuild validation. The original input was not overwritten.",
    ]
    (report_dir / "patch_report.md").write_text("\n".join(patch_report) + "\n", encoding="utf-8")
    validation_report = [
        "# Code RED Script Patch Validation",
        "",
        *(f"- {key}: `{value}`" for key, value in validation.items() if key != "note"),
        "",
        validation["note"],
    ]
    (report_dir / "validation_report.md").write_text("\n".join(validation_report) + "\n", encoding="utf-8")
    return manifest
