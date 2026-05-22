from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from codered_wsc.analysis import disasm_artifacts, patch_candidates, write_candidates_report, write_inspect_report, write_map_report, write_scan_report
from codered_wsc.patching import PatchError, apply_recipe, apply_recipe_detailed, validate_recipe, write_patch_bundle
from codered_wsc.pools import scan_population_pools
from codered_wsc.resource import (
    KeyOptions,
    aes_crypt_16_passes,
    open_script,
    repack_script,
    swap32,
    zstd_compress_variants,
    zstd_skippable_padding,
)


TEST_KEY = bytes(range(32))


def decoded_fixture() -> bytes:
    enter = bytes([45, 0, 0, 1, 4]) + b"main"
    body = bytes([38, 0x04, 0xA9, 44, 0x01, 0x02, 46, 0, 0])
    strings = b"\0ped_wilderness\0vehicle\0driver flee sector\0"
    return (enter + body + strings).ljust(4096, b"\0")


def push_string(value: str) -> bytes:
    raw = value.encode("ascii") + b"\0"
    return bytes([111, len(raw)]) + raw


def pool_decoded_fixture() -> bytes:
    enter = bytes([45, 0, 0, 1, 4]) + b"main"
    pools = b"".join(
        (
            push_string("ped_wilderness"),
            bytes([37, 111, 149]),
            push_string("ped_traveller"),
            bytes([37, 115, 149]),
            push_string("ped_vehicle"),
            bytes([65, 0x04, 0x9F, 150]),
        )
    )
    return (enter + pools + bytes([46, 0, 0])).ljust(4096, b"\0")


def rsc85_fixture(decoded: bytes, payload_capacity: int = 512) -> bytes:
    _, _, compressed = zstd_compress_variants(decoded)[0]
    if len(compressed) + 8 > payload_capacity:
        payload_capacity = len(compressed) + 16
    payload = compressed + zstd_skippable_padding(payload_capacity - len(compressed))
    header = b"RSC\x85" + struct.pack("<III", 2, 0x80000000, 0x80000001)
    return header + aes_crypt_16_passes(payload, TEST_KEY, decrypt=False)


class CodeRedWscToolsTests(unittest.TestCase):
    def test_open_repack_and_xsc_word_swap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            wsc = tmp_path / "fixture.wsc"
            wsc.write_bytes(rsc85_fixture(decoded_fixture()))
            resource = open_script(wsc, KeyOptions(aes_key_hex=TEST_KEY.hex()))
            self.assertEqual(resource.decoded, decoded_fixture())
            output, report = repack_script(resource, resource.decoded)
            self.assertTrue(report["validate_ok"])
            rebuilt = tmp_path / "rebuilt.wsc"
            rebuilt.write_bytes(output)
            self.assertEqual(open_script(rebuilt, KeyOptions(aes_key_hex=TEST_KEY.hex())).decoded, decoded_fixture())

            xsc = tmp_path / "fixture.xsc"
            xsc.write_bytes(swap32(wsc.read_bytes()))
            xsc_resource = open_script(xsc, KeyOptions(aes_key_hex=TEST_KEY.hex()))
            self.assertTrue(xsc_resource.header.normalized_from_xsc)
            self.assertEqual(xsc_resource.decoded, decoded_fixture())

    def test_reports_find_function_terms_and_native(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "inspect"
            info = {"path": "fixture.wsc", "family": "synthetic"}
            summary = write_inspect_report(out, info, decoded_fixture())
            scan = write_scan_report(Path(tmp) / "scan", info, decoded_fixture(), "vehicle,driver,ped_wilderness")
            disasm = disasm_artifacts(decoded_fixture())
            self.assertGreaterEqual(summary["functions"], 1)
            self.assertGreaterEqual(summary["natives"], 1)
            self.assertEqual(scan["hits"], 3)
            self.assertEqual(disasm["functions"][0]["name"], "main")
            self.assertTrue((out / "resource_info.json").exists())

    def test_same_size_enum_recipe_changes_only_operand(self) -> None:
        recipe = {
            "name": "synthetic_actor",
            "input_expected": {"strings_required": ["ped_wilderness"]},
            "patches": [{"type": "replace_enum_operand", "offset": 10, "width": 2, "endian": "big", "expected": 1193, "value": 1194}],
        }
        patched, edits, terms = apply_recipe(decoded_fixture(), recipe)
        self.assertEqual(terms, ["ped_wilderness"])
        self.assertEqual(len(edits), 1)
        self.assertEqual(patched[10:12], bytes.fromhex("04 AA"))
        self.assertEqual(patched[:10] + patched[12:], decoded_fixture()[:10] + decoded_fixture()[12:])

    def test_same_size_constant_recipe_uses_general_primitive(self) -> None:
        recipe = {
            "name": "synthetic_constant",
            "patches": [{"type": "replace_constant", "offset": 10, "width": 2, "endian": "big", "expected": 1193, "value": 1183}],
        }
        patched, edits, _ = apply_recipe(decoded_fixture(), recipe)
        self.assertEqual(edits[0].patch_type, "replace_constant")
        self.assertEqual(patched[10:12], bytes.fromhex("04 9F"))
        self.assertEqual(patched[:10] + patched[12:], decoded_fixture()[:10] + decoded_fixture()[12:])

    def test_patch_bundle_reopens_and_keeps_backup(self) -> None:
        recipe = {
            "name": "synthetic_actor",
            "input_expected": {"strings_required": ["ped_wilderness"]},
            "patches": [{"type": "replace_enum_operand", "offset": 10, "width": 2, "endian": "big", "expected": 1193, "value": 1194}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.wsc"
            source.write_bytes(rsc85_fixture(decoded_fixture()))
            recipe_path = root / "recipe.yaml"
            resource = open_script(source, KeyOptions(aes_key_hex=TEST_KEY.hex()))
            output = root / "patched" / "source.wsc"
            manifest = write_patch_bundle(resource, recipe_path, recipe, output)
            reopened = open_script(output, KeyOptions(aes_key_hex=TEST_KEY.hex()))
            self.assertEqual(reopened.decoded[10:12], bytes.fromhex("04 AA"))
            self.assertTrue(manifest["validation"]["roundtrip_decompress"])
            self.assertTrue((root / "patched" / "source_patch" / "source.wsc.original_backup").exists())

    def test_pool_scan_finds_actor_and_vehicle_pools(self) -> None:
        pool_map = scan_population_pools(pool_decoded_fixture())
        self.assertIsNotNone(pool_map.by_name("ped_wilderness"))
        self.assertIsNotNone(pool_map.by_name("ped_traveller"))
        self.assertIsNotNone(pool_map.by_name("ped_vehicle"))
        self.assertEqual(pool_map.candidates_for("ped_vehicle")[0]["enum"], 1183)

    def test_general_map_and_candidates_label_patchability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            info = {"path": "fixture.wsc", "family": "synthetic"}
            mapped = write_map_report(root / "map", info, pool_decoded_fixture())
            constants = write_candidates_report(root / "constant_candidates", info, decoded_fixture(), "constants")
            branches = write_candidates_report(root / "branch_candidates", info, decoded_fixture(), "branch")
            native = write_candidates_report(root / "native_candidates", info, decoded_fixture(), "native")
            self.assertGreaterEqual(mapped["tables"], 3)
            self.assertGreaterEqual(constants["patchability"]["SAME_SIZE_SAFE"], 1)
            self.assertEqual(branches["patchability"]["CONTROL_FLOW_SAFE"], 0)
            self.assertGreaterEqual(native["patchability"]["READ_ONLY"], 1)
            self.assertTrue((root / "map" / "script_map.json").exists())
            self.assertTrue((root / "map" / "functions_detailed.csv").exists())
            self.assertTrue((root / "map" / "function_context.json").exists())
            self.assertTrue((root / "map" / "function_context.md").exists())
            self.assertTrue((root / "map" / "string_references.csv").exists())
            self.assertTrue((root / "map" / "string_context.md").exists())
            self.assertTrue((root / "constant_candidates" / "constants_candidates.csv").exists())

    def test_candidate_reports_have_ownership_fields_for_every_kind(self) -> None:
        required = {
            "candidate_id",
            "decoded_offset",
            "section",
            "owner_type",
            "nearby_strings",
            "nearby_native_calls",
            "nearby_branches",
            "candidate_value",
            "candidate_value_type",
            "operand_width",
            "patchability_level",
            "confidence_score",
            "safety_reason",
            "blocked_reason",
        }
        data_by_kind = {"constants": decoded_fixture(), "strings": decoded_fixture(), "native": decoded_fixture(), "tables": pool_decoded_fixture()}
        with tempfile.TemporaryDirectory() as tmp:
            for kind, data in data_by_kind.items():
                rows = patch_candidates(data, kind)
                summary = write_candidates_report(Path(tmp) / kind, {"path": "fixture.wsc", "family": "synthetic"}, data, kind)
                self.assertTrue(rows, kind)
                self.assertGreater(summary["candidates"], 0)
                self.assertTrue(required.issubset(rows[0]), kind)
            branch_summary = write_candidates_report(Path(tmp) / "branch", {"path": "fixture.wsc", "family": "synthetic"}, decoded_fixture(), "branch")
            self.assertEqual(branch_summary["kind"], "branch")

    def test_replace_constant_by_candidate_and_match_limit(self) -> None:
        candidate = patch_candidates(decoded_fixture(), "constants")[0]
        recipe = {
            "patches": [
                {
                    "type": "replace_constant",
                    "match": {"candidate_id": candidate["candidate_id"]},
                    "replacement": 1183,
                    "expected_width": 2,
                    "require_patchability": "SAME_SIZE_SAFE",
                }
            ]
        }
        patched, edits, _ = apply_recipe(decoded_fixture(), recipe)
        self.assertEqual(edits[0].candidate_id, candidate["candidate_id"])
        self.assertEqual(patched[10:12], bytes.fromhex("04 9F"))
        too_broad = {"patches": [{"type": "replace_constant", "match": {"value": 1193}, "replacement": 1183, "expected_width": 2}]}
        with self.assertRaises(PatchError):
            apply_recipe(decoded_fixture(), too_broad)

    def test_unowned_raw_replacement_and_readonly_edits_stay_blocked(self) -> None:
        raw = {"patches": [{"type": "replace_bytes", "offset": 10, "expected_hex": "04 A9", "hex": "04 9F"}]}
        branch = {"patches": [{"type": "force_branch", "candidate_id": "BRANCH_000001", "value": True}]}
        native = {"patches": [{"type": "nop_call", "candidate_id": "NATIVE_000001"}]}
        with self.assertRaises(PatchError):
            apply_recipe(decoded_fixture(), raw)
        with self.assertRaises(PatchError):
            apply_recipe(decoded_fixture(), branch)
        with self.assertRaises(PatchError):
            apply_recipe(decoded_fixture(), native)

    def test_pool_actor_and_vehicle_recipes_change_only_selected_operands(self) -> None:
        actor_recipe = {
            "patches": [{"type": "population_actor_pool_replace", "pool": "ped_wilderness", "replace_all_human_actor_operands_with_cycle": [184]}]
        }
        vehicle_recipe = {
            "patches": [{"type": "population_vehicle_pool_replace", "pool": "ped_vehicle", "replace_vehicle_actor_operands": {1183: 1194}}]
        }
        actor_result = apply_recipe_detailed(pool_decoded_fixture(), actor_recipe)
        vehicle_result = apply_recipe_detailed(pool_decoded_fixture(), vehicle_recipe)
        self.assertEqual([(edit.old_enum, edit.new_enum, edit.pool) for edit in actor_result.edits], [(111, 184, "ped_wilderness")])
        self.assertEqual([(edit.old_enum, edit.new_enum, edit.pool) for edit in vehicle_result.edits], [(1183, 1194, "ped_vehicle")])
        self.assertEqual(actor_result.decoded.count(bytes([65, 0x04, 0x9F])), 1)
        self.assertEqual(vehicle_result.decoded.count(bytes([37, 111])), 1)

    def test_pool_width_and_bad_pool_fail_safely(self) -> None:
        too_wide = {
            "patches": [{"type": "population_actor_pool_replace", "pool": "ped_wilderness", "replace_all_human_actor_operands_with_cycle": [595]}]
        }
        bad_pool = {
            "patches": [{"type": "population_actor_pool_replace", "pool": "missing_pool", "replace_all_human_actor_operands_with_cycle": [184]}]
        }
        with self.assertRaises(PatchError):
            apply_recipe_detailed(pool_decoded_fixture(), too_wide)
        with self.assertRaises(PatchError):
            apply_recipe_detailed(pool_decoded_fixture(), bad_pool)

    def test_dry_run_patch_bundle_writes_manifest_without_patch_file(self) -> None:
        recipe = {
            "name": "synthetic_vehicle",
            "patches": [{"type": "population_vehicle_pool_replace", "pool": "ped_vehicle", "replace_vehicle_actor_operands": {1183: 1194}}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "population.wsc"
            source.write_bytes(rsc85_fixture(pool_decoded_fixture()))
            output = root / "patched" / "population.wsc"
            resource = open_script(source, KeyOptions(aes_key_hex=TEST_KEY.hex()))
            manifest = write_patch_bundle(resource, root / "dry_run.yaml", recipe, output, dry_run=True)
            real_manifest = write_patch_bundle(resource, root / "real.yaml", recipe, root / "real" / "population.wsc")
            self.assertFalse(output.exists())
            self.assertFalse(manifest["output_written"])
            self.assertTrue(real_manifest["output_written"])
            self.assertTrue({"would_change_count", "blocked_count", "skipped_count", "warnings"}.issubset(manifest))
            self.assertEqual(set(manifest), set(real_manifest))
            self.assertTrue((root / "patched" / "population_patch" / "manifest.json").exists())

    @unittest.skipUnless(Path("imports/grt_population.wsc").exists() and Path("../rdr.exe").exists(), "local grt WSC sample is absent")
    def test_local_grt_pool_sample_maps_requested_pools(self) -> None:
        resource = open_script(Path("imports/grt_population.wsc"), KeyOptions(rdr_exe="../rdr.exe"))
        pool_map = scan_population_pools(resource.decoded)
        for pool in ("ped_wilderness", "ped_traveller", "ped_law", "ped_bad_guys_local", "ped_bad_guys_generic", "ped_vehicle"):
            self.assertIsNotNone(pool_map.by_name(pool))


if __name__ == "__main__":
    unittest.main()
