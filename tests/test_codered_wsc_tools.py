from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from codered_wsc.analysis import disasm_artifacts, write_inspect_report, write_scan_report
from codered_wsc.patching import PatchError, apply_recipe, validate_recipe, write_patch_bundle
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

    def test_planned_population_recipe_is_not_claimed_ready(self) -> None:
        recipe = {"patches": [{"type": "population_actor_pool_replace", "pool": "ped_law"}]}
        self.assertFalse(validate_recipe(recipe)["ready"])
        with self.assertRaises(PatchError):
            apply_recipe(decoded_fixture(), recipe)


if __name__ == "__main__":
    unittest.main()
