"""Recipe loading and same-size decoded script patches."""
from __future__ import annotations

import difflib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..analysis import ensure_dir, patch_candidates, write_csv, write_json
from ..pools import PoolMap, scan_population_pools
from ..resource import ResourceError, ScriptResource, repack_script, sha256
from .primitives import DecodedEdit, integer_bytes, parse_hex as parse_primitive_hex, parse_int as parse_primitive_int, replace_at as primitive_replace_at
from .validation import byte_diff_rows, hex_lines, protected_overlap_violations, string_offsets, validate_population_isolation


SUPPORTED_PATCHES = {
    "replace_constant",
    "replace_enum_operand",
    "replace_bytes",
    "same_length_string_replace",
    "population_actor_pool_replace",
    "population_vehicle_pool_replace",
}
PLANNED_PATCHES = {
    "flip_boolean_constant",
    "nop_instruction",
    "nop_call",
    "force_function_return",
    "disable_branch",
    "force_branch",
    "invert_branch",
    "replace_call_target",
    "replace_float_operand",
    "replace_hash_operand",
    "replace_table_values",
    "replace_native_arg_when_mapped",
}


class PatchError(RuntimeError):
    """Raised when a patch recipe cannot be applied conservatively."""


@dataclass
class PatchResult:
    decoded: bytes
    edits: list[DecodedEdit]
    required_strings: list[str]
    skipped: list[dict[str, Any]]
    pool_map: PoolMap | None
    targeted_pools: list[str]
    population_patch_types: list[str]


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
    return parse_primitive_int(value, label, PatchError)


def parse_hex(value: Any, label: str) -> bytes:
    return parse_primitive_hex(value, label, PatchError)


def validate_required_strings(decoded: bytes, recipe: dict[str, Any]) -> list[str]:
    expected = recipe.get("input_expected", {}).get("strings_required", [])
    missing = [term for term in expected if str(term).encode("ascii", errors="ignore") not in decoded]
    if missing:
        raise PatchError(f"Recipe required strings missing from decoded input: {missing}")
    return [str(term) for term in expected]


def replace_at(data: bytearray, offset: int, before: bytes, after: bytes, patch_type: str, note: str) -> DecodedEdit:
    return primitive_replace_at(data, offset, before, after, patch_type, note, PatchError)


def enum_bytes(value: int, width: int, endian: str) -> bytes:
    return integer_bytes(value, width, endian, PatchError, "Enum")


def patch_allows_unowned(recipe: dict[str, Any], patch: dict[str, Any]) -> bool:
    return bool(patch.get("allow_unowned", recipe.get("allow_unowned", False)))


def annotate_edit(edit: DecodedEdit, candidate: dict[str, Any]) -> DecodedEdit:
    edit.candidate_id = str(candidate.get("candidate_id", ""))
    edit.section = str(candidate.get("section", ""))
    edit.owner_type = str(candidate.get("owner_type", ""))
    edit.owner_name = str(candidate.get("owner_name", ""))
    edit.patchability_level = str(candidate.get("patchability_level", candidate.get("patchability", "")))
    edit.safety_reason = str(candidate.get("safety_reason", candidate.get("reason", "")))
    return edit


def candidate_search_text(candidate: dict[str, Any]) -> str:
    values = [
        candidate.get("owner_function_name", ""),
        candidate.get("owner_name", ""),
        *candidate.get("owner_function_purpose_tags", []),
        *candidate.get("nearby_strings", []),
    ]
    return " ".join(str(value) for value in values).lower()


def term_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def candidate_matches_text(candidate: dict[str, Any], key: str, required: list[Any]) -> bool:
    terms = [str(term).lower() for term in required if str(term)]
    if not terms:
        return True
    if key == "nearby_string_contains":
        haystack = " ".join(str(value) for value in candidate.get("nearby_strings", [])).lower()
    else:
        haystack = candidate_search_text(candidate)
    return all(term in haystack for term in terms)


def constant_matches(decoded: bytes, patch: dict[str, Any], patch_type: str) -> list[dict[str, Any]]:
    candidates = patch_candidates(decoded, "constants")
    raw_match = patch.get("match", {})
    if raw_match and not isinstance(raw_match, dict):
        raise PatchError(f"{patch_type} match must be a mapping")
    match = dict(raw_match) if isinstance(raw_match, dict) else {}
    legacy_offset = patch.get("offset")
    if legacy_offset is not None:
        match.setdefault("decoded_offset", legacy_offset)
    if patch.get("expected") is not None:
        match.setdefault("value", patch.get("expected"))
    width_value = patch.get("expected_width", patch.get("width"))
    selected: list[dict[str, Any]] = []
    for candidate in candidates:
        if match.get("candidate_id") and str(candidate["candidate_id"]) != str(match["candidate_id"]):
            continue
        if match.get("decoded_offset") is not None and int(candidate["decoded_offset"]) != parse_int(match["decoded_offset"], f"{patch_type} match decoded_offset"):
            continue
        if match.get("value") is not None and int(candidate["candidate_value"]) != parse_int(match["value"], f"{patch_type} match value"):
            continue
        if width_value is not None and int(candidate["operand_width"]) != parse_int(width_value, f"{patch_type} expected_width"):
            continue
        if not candidate_matches_text(candidate, "owner_function_contains_terms", term_list(match.get("owner_function_contains_terms"))):
            continue
        if not candidate_matches_text(candidate, "nearby_string_contains", term_list(match.get("nearby_string_contains"))):
            continue
        required_patchability = str(patch.get("require_patchability", match.get("require_patchability", "SAME_SIZE_SAFE")))
        if required_patchability and str(candidate["patchability_level"]) != required_patchability:
            continue
        selected.append(candidate)
    exact = bool(match.get("candidate_id") or match.get("decoded_offset") is not None)
    if not exact and patch.get("max_matches") is None:
        raise PatchError(f"{patch_type} requires max_matches unless match uses candidate_id or decoded_offset")
    if patch.get("max_matches") is not None and len(selected) > parse_int(patch["max_matches"], f"{patch_type} max_matches"):
        raise PatchError(f"{patch_type} matched {len(selected)} constants, over max_matches={patch['max_matches']}")
    return selected


def apply_constant_patch(output: bytearray, decoded: bytes, recipe: dict[str, Any], patch: dict[str, Any], patch_type: str) -> list[DecodedEdit]:
    selected = constant_matches(decoded, patch, patch_type)
    endian = str(patch.get("endian", "big"))
    replacement = patch.get("replacement", patch.get("value"))
    if replacement is None:
        raise PatchError(f"{patch_type} requires replacement or value")
    edits: list[DecodedEdit] = []
    for candidate in selected:
        width = int(candidate["operand_width"])
        before = integer_bytes(int(candidate["candidate_value"]), width, endian, PatchError, "Constant")
        after = integer_bytes(parse_int(replacement, f"{patch_type} replacement"), width, endian, PatchError, "Constant")
        byteorder = "big" if endian in ("big", "be") else "little"
        label = "enum" if patch_type == "replace_enum_operand" else "constant"
        edit = replace_at(
            output,
            int(candidate["decoded_offset"]),
            before,
            after,
            patch_type,
            f"{label} {int.from_bytes(before, byteorder)} -> {int.from_bytes(after, byteorder)} via {candidate['candidate_id']}",
        )
        edits.append(annotate_edit(edit, candidate))
    if edits:
        return edits
    if not patch_allows_unowned(recipe, patch):
        raise PatchError(f"{patch_type} did not match an owned constant candidate; set allow_unowned: true only after manual review")
    if patch.get("offset") is None or patch.get("expected") is None:
        raise PatchError(f"{patch_type} allow_unowned fallback requires offset and expected")
    width = parse_int(patch.get("expected_width", patch.get("width", 2)), f"{patch_type} width")
    before = integer_bytes(parse_int(patch["expected"], f"{patch_type} expected"), width, endian, PatchError, "Constant")
    after = integer_bytes(parse_int(replacement, f"{patch_type} replacement"), width, endian, PatchError, "Constant")
    edit = replace_at(output, parse_int(patch["offset"], f"{patch_type} offset"), before, after, patch_type, "manually allowed unowned constant replacement")
    edit.allow_unowned = True
    edit.safety_reason = "recipe explicitly allowed an unowned replacement"
    return [edit]


def apply_recipe(decoded: bytes, recipe: dict[str, Any]) -> tuple[bytes, list[DecodedEdit], list[str]]:
    result = apply_recipe_detailed(decoded, recipe)
    return result.decoded, result.edits, result.required_strings


def skipped_candidate(candidate: dict[str, Any], reason: str, patch_type: str) -> dict[str, Any]:
    return {
        "type": patch_type,
        "pool": candidate.get("pool", ""),
        "operand_offset": candidate.get("operand_offset", ""),
        "operand_offset_hex": candidate.get("operand_offset_hex", ""),
        "operand_width": candidate.get("operand_width", ""),
        "enum": candidate.get("enum", ""),
        "enum_label": candidate.get("enum_label", ""),
        "likely_enum_category": candidate.get("likely_enum_category", ""),
        "safe_same_width_replace": candidate.get("safe_same_width_replace", ""),
        "reason": reason,
    }


def candidate_edit(output: bytearray, candidate: dict[str, Any], target: int, patch_type: str) -> DecodedEdit:
    width = int(candidate["operand_width"])
    before = enum_bytes(int(candidate["enum"]), width, "big")
    after = enum_bytes(target, width, "big")
    edit = replace_at(
        output,
        int(candidate["operand_offset"]),
        before,
        after,
        patch_type,
        f"{candidate['pool']} enum {candidate['enum']} -> {target}",
    )
    edit.pool = str(candidate["pool"])
    edit.enum_category = str(candidate["likely_enum_category"])
    edit.old_enum = int(candidate["enum"])
    edit.new_enum = target
    edit.section = "table"
    edit.owner_type = "population_pool"
    edit.owner_name = str(candidate["pool"])
    edit.patchability_level = "SAME_SIZE_SAFE"
    edit.safety_reason = str(candidate.get("confidence_reason", "mapped population pool enum operand"))
    return edit


def require_pool(pool_map: PoolMap, pool_name: str, patch_type: str) -> dict[str, Any]:
    pool = pool_map.by_name(pool_name)
    if pool is None:
        raise PatchError(f"{patch_type} pool was not mapped: {pool_name}")
    return pool


def apply_actor_pool_patch(
    output: bytearray,
    pool_map: PoolMap,
    patch: dict[str, Any],
    patch_type: str,
) -> tuple[list[DecodedEdit], list[dict[str, Any]], str]:
    pool_name = str(patch.get("pool", ""))
    pool = require_pool(pool_map, pool_name, patch_type)
    if pool["pool_kind"] != "actor_pool":
        raise PatchError(f"{patch_type} requires a human actor pool, got {pool_name}")
    if patch.get("preserve_operand_width", True) is not True:
        raise PatchError(f"{patch_type} only supports preserve_operand_width: true")
    targets = [parse_int(value, f"{patch_type} target actor") for value in patch.get("replace_all_human_actor_operands_with_cycle", [])]
    if not targets:
        raise PatchError(f"{patch_type} requires replace_all_human_actor_operands_with_cycle values")
    edits: list[DecodedEdit] = []
    skipped: list[dict[str, Any]] = []
    fail_width = bool(patch.get("fail_if_width_expansion_required", True))
    for candidate in pool_map.candidates_for(pool_name):
        if candidate["likely_enum_category"] != "human_actor":
            skipped.append(skipped_candidate(candidate, "not a human actor candidate", patch_type))
            continue
        if not candidate["safe_same_width_replace"]:
            skipped.append(skipped_candidate(candidate, "pool mapper did not mark candidate safe", patch_type))
            continue
        target = targets[len(edits) % len(targets)]
        try:
            edits.append(candidate_edit(output, candidate, target, patch_type))
        except PatchError as exc:
            if fail_width:
                raise
            skipped.append(skipped_candidate(candidate, str(exc), patch_type))
    if not edits:
        raise PatchError(f"{patch_type} did not find safe human actor operands in {pool_name}")
    return edits, skipped, pool_name


def apply_vehicle_pool_patch(
    output: bytearray,
    pool_map: PoolMap,
    patch: dict[str, Any],
    patch_type: str,
) -> tuple[list[DecodedEdit], list[dict[str, Any]], str]:
    pool_name = str(patch.get("pool", ""))
    pool = require_pool(pool_map, pool_name, patch_type)
    if pool["pool_kind"] != "vehicle_pool":
        raise PatchError(f"{patch_type} requires ped_vehicle, got {pool_name}")
    if patch.get("preserve_operand_width", True) is not True:
        raise PatchError(f"{patch_type} only supports preserve_operand_width: true")
    raw_map = patch.get("replace_vehicle_actor_operands", {})
    if not isinstance(raw_map, dict) or not raw_map:
        raise PatchError(f"{patch_type} requires replace_vehicle_actor_operands mapping")
    targets = {parse_int(old, f"{patch_type} old vehicle"): parse_int(new, f"{patch_type} new vehicle") for old, new in raw_map.items()}
    edits: list[DecodedEdit] = []
    skipped: list[dict[str, Any]] = []
    fail_width = bool(patch.get("fail_if_width_expansion_required", True))
    for candidate in pool_map.candidates_for(pool_name):
        if candidate["likely_enum_category"] != "vehicle_actor":
            skipped.append(skipped_candidate(candidate, "not a vehicle actor candidate", patch_type))
            continue
        if not candidate["safe_same_width_replace"]:
            skipped.append(skipped_candidate(candidate, "pool mapper did not mark candidate safe", patch_type))
            continue
        old = int(candidate["enum"])
        if old not in targets:
            skipped.append(skipped_candidate(candidate, "vehicle enum not explicitly requested", patch_type))
            continue
        try:
            edits.append(candidate_edit(output, candidate, targets[old], patch_type))
        except PatchError as exc:
            if fail_width:
                raise
            skipped.append(skipped_candidate(candidate, str(exc), patch_type))
    if not edits:
        raise PatchError(f"{patch_type} did not find requested safe vehicle operands in {pool_name}")
    return edits, skipped, pool_name


def apply_recipe_detailed(decoded: bytes, recipe: dict[str, Any]) -> PatchResult:
    status = validate_recipe(recipe)
    if status["planned_patch_types"] or status["unknown_patch_types"]:
        raise PatchError(
            "Recipe contains patch types not implemented safely yet: "
            + ", ".join(status["planned_patch_types"] + status["unknown_patch_types"])
        )
    required_strings = validate_required_strings(decoded, recipe)
    output = bytearray(decoded)
    edits: list[DecodedEdit] = []
    skipped: list[dict[str, Any]] = []
    pool_map = scan_population_pools(decoded) if any(str(patch.get("type", "")).startswith("population_") for patch in recipe.get("patches", []) if isinstance(patch, dict)) else None
    targeted_pools: list[str] = []
    population_patch_types: list[str] = []
    for ordinal, patch in enumerate(recipe.get("patches", []), start=1):
        if not isinstance(patch, dict):
            raise PatchError(f"Patch #{ordinal} must be a mapping")
        patch_type = str(patch.get("type", ""))
        if patch_type in {"replace_constant", "replace_enum_operand"}:
            edits.extend(apply_constant_patch(output, decoded, recipe, patch, patch_type))
        elif patch_type == "replace_bytes":
            if not patch_allows_unowned(recipe, patch):
                raise PatchError("replace_bytes is unowned by default; set allow_unowned: true only for a reviewed exact decoded range")
            offset = parse_int(patch.get("offset"), "replace_bytes offset")
            edit = replace_at(
                output,
                offset,
                parse_hex(patch.get("expected_hex", ""), "replace_bytes expected_hex"),
                parse_hex(patch.get("hex", ""), "replace_bytes hex"),
                patch_type,
                "exact decoded byte replacement",
            )
            edit.allow_unowned = True
            edit.safety_reason = "recipe explicitly allowed exact unowned decoded bytes"
            edits.append(edit)
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
            for offset in offsets:
                edit = replace_at(output, offset, old, new, patch_type, f"{old!r} -> {new!r}")
                edit.section = "string"
                edit.owner_type = "string_table"
                edit.owner_name = old.decode(str(patch.get("encoding", "ascii")), errors="replace")
                edit.patchability_level = "SAME_SIZE_SAFE"
                edit.safety_reason = "explicit same-length string replacement owns these decoded string bytes"
                edits.append(edit)
        elif patch_type == "population_actor_pool_replace":
            if pool_map is None:
                raise PatchError("population pool map was not created")
            pool_edits, pool_skipped, pool_name = apply_actor_pool_patch(output, pool_map, patch, patch_type)
            edits.extend(pool_edits)
            skipped.extend(pool_skipped)
            targeted_pools.append(pool_name)
            population_patch_types.append(patch_type)
        elif patch_type == "population_vehicle_pool_replace":
            if pool_map is None:
                raise PatchError("population pool map was not created")
            pool_edits, pool_skipped, pool_name = apply_vehicle_pool_patch(output, pool_map, patch, patch_type)
            edits.extend(pool_edits)
            skipped.extend(pool_skipped)
            targeted_pools.append(pool_name)
            population_patch_types.append(patch_type)
        else:
            raise PatchError(f"Patch type is not supported: {patch_type}")
    unowned = [edit for edit in edits if not edit.owner_type and not edit.allow_unowned]
    if unowned:
        raise PatchError("Patch contains unowned edits; candidate ownership is required unless allow_unowned is explicit")
    return PatchResult(bytes(output), edits, required_strings, skipped, pool_map, targeted_pools, population_patch_types)


def write_patch_bundle(resource: ScriptResource, recipe_path: Path, recipe: dict[str, Any], out_file: Path, dry_run: bool = False) -> dict[str, Any]:
    result = apply_recipe_detailed(resource.decoded, recipe)
    patched_decoded, edits, required_strings = result.decoded, result.edits, result.required_strings
    # Prefer exact-slot fits, but population edits must still be exportable for
    # RPF import when valid Zstandard padding cannot preserve the stored size.
    output, repack = repack_script(resource, patched_decoded, allow_growth=True)
    ensure_dir(out_file.parent)
    report_dir = out_file.parent / f"{out_file.stem}_patch"
    ensure_dir(report_dir)
    if not dry_run:
        out_file.write_bytes(output)
    backup = report_dir / f"{resource.path.name}.original_backup"
    backup.write_bytes(resource.original)
    (report_dir / "decompressed_original.bin").write_bytes(resource.decoded)
    (report_dir / "decompressed_patched.bin").write_bytes(patched_decoded)
    diff_rows = byte_diff_rows(resource.decoded, patched_decoded, PatchError)
    write_csv(report_dir / "binary_patch.csv", [edit.csv_row() for edit in edits])
    write_csv(report_dir / "skipped_entries.csv", result.skipped)
    write_csv(report_dir / "vehicle_patch_manifest.csv", [edit.csv_row() for edit in edits if edit.enum_category == "vehicle_actor"])
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
    requested_string_patch = any(edit.patch_type == "same_length_string_replace" for edit in edits)
    changed_string_offsets = actual_offsets & string_offsets(resource.decoded)
    isolation = validate_population_isolation(result)
    protected_overlaps = protected_overlap_violations(resource.decoded, edits)
    decoded_size_allowed = bool(recipe.get("allow_decompressed_size_change", False))
    validation = {
        "resource_reopens": repack["validate_ok"],
        "roundtrip_decompress": repack["validate_ok"],
        "decoded_size_unchanged": len(resource.decoded) == len(patched_decoded),
        "decoded_size_change_allowed_by_recipe": decoded_size_allowed,
        "no_unrelated_decoded_bytes_changed": no_unrelated,
        "edits_have_candidate_ownership_or_explicit_unowned_allowance": all(edit.owner_type or edit.allow_unowned for edit in edits),
        "required_strings_present_before_patch": required_strings,
        "no_string_bytes_changed_without_string_patch": requested_string_patch or not changed_string_offsets,
        "changed_string_byte_offsets": [f"0x{offset:X}" for offset in sorted(changed_string_offsets)],
        "no_protected_metadata_overlap": not protected_overlaps,
        "protected_metadata_overlap_violations": protected_overlaps,
        "all_skipped_candidates_reported": True,
        **isolation,
        "note": "String-table rebuild is not implemented. Same-length string replacements are explicit recipe operations.",
    }
    required_validation = [
        validation["resource_reopens"],
        validation["decoded_size_unchanged"] or decoded_size_allowed,
        no_unrelated,
        validation["edits_have_candidate_ownership_or_explicit_unowned_allowance"],
        validation["no_string_bytes_changed_without_string_patch"],
        validation["no_protected_metadata_overlap"],
        *isolation.values(),
    ]
    if not all(required_validation):
        raise ResourceError("Patch validation failed before manifest completion")
    all_pools = [pool["pool"] for pool in result.pool_map.pools] if result.pool_map else []
    warnings = []
    if repack.get("compressed_size") != repack.get("payload_capacity"):
        warnings.append("rebuilt compressed stream size differs from the source slot and was fit with the recorded RSC85 repack mode")
    if len(output) != len(resource.original):
        warnings.append("rebuilt standalone file size differs from the input; replace through Magic RDR/RPF import, not raw offset overwrite")
    manifest = {
        "tool": "codered_wsc",
        "recipe": str(recipe_path),
        "recipe_name": recipe.get("name", ""),
        "input": str(resource.path),
        "input_sha256": sha256(resource.original),
        "output": str(out_file),
        "dry_run": dry_run,
        "output_written": not dry_run,
        "output_sha256": sha256(output),
        "report_dir": str(report_dir),
        "decoded_original_sha256": sha256(resource.decoded),
        "decoded_patched_sha256": sha256(patched_decoded),
        "edits": [edit.csv_row() for edit in edits],
        "would_change_count": len(edits),
        "blocked_count": 0,
        "skipped_count": len(result.skipped),
        "skipped_entries": result.skipped,
        "pools_touched": sorted(set(result.targeted_pools)),
        "pools_untouched": [pool for pool in all_pools if pool not in set(result.targeted_pools)],
        "warnings": warnings,
        "repack": repack,
        "validation": validation,
    }
    write_json(report_dir / "manifest.json", manifest)
    patch_report = [
        "# Code RED Script Patch Report",
        "",
        f"- Input: `{resource.path}`",
        f"- Output: `{out_file}`",
        f"- Dry run: `{dry_run}`",
        f"- Recipe: `{recipe_path}`",
        f"- Decoded same-size edits: `{len(edits)}`",
        f"- Decoded changed bytes: `{len(diff_rows)}`",
        f"- Repack mode: `{repack['fit_mode']}`",
        f"- Pools touched: `{', '.join(sorted(set(result.targeted_pools))) or 'none'}`",
        f"- Skipped candidates: `{len(result.skipped)}`",
        "",
        "This bundle records decoded byte changes and rebuild validation. The original input was not overwritten.",
    ]
    if warnings:
        patch_report.extend(["", "## Warnings", "", *(f"- {warning}" for warning in warnings)])
    if len(output) != len(resource.original):
        patch_report.extend(["", "## Install", "", "Replace this file through Magic RDR/RPF import, not raw offset overwrite."])
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
