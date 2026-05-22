"""Command line entry point for Code RED script inspection and patch bundles."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .analysis import write_disasm_report, write_inspect_report, write_json, write_scan_report
from .patching import PatchError, load_recipe, validate_recipe, write_patch_bundle
from .resource import KeyOptions, ResourceError, open_script, repack_script


def add_key_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--aes-key-hex", default="", help="Explicit 32-byte RDR AES key in hex.")
    parser.add_argument("--aes-key-file", default="", help="File containing 32 raw key bytes or hex.")
    parser.add_argument("--rdr-exe", default="", help="Optional local rdr.exe used only for known AES key offsets.")


def key_options(args: argparse.Namespace) -> KeyOptions:
    return KeyOptions(args.aes_key_hex, args.aes_key_file, args.rdr_exe)


def open_input(args: argparse.Namespace):
    return open_script(Path(args.input), key_options(args))


def cmd_inspect(args: argparse.Namespace) -> int:
    resource = open_input(args)
    summary = write_inspect_report(Path(args.out), resource.header_dict(), resource.decoded)
    print(json.dumps({"status": "inspected", "out": args.out, **summary}, indent=2))
    return 0


def cmd_disasm(args: argparse.Namespace) -> int:
    resource = open_input(args)
    require_decoded(resource)
    summary = write_disasm_report(Path(args.out), resource.header_dict(), resource.decoded)
    print(json.dumps({"status": "disassembled", "out": args.out, **summary}, indent=2))
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    resource = open_input(args)
    require_decoded(resource)
    summary = write_scan_report(Path(args.out), resource.header_dict(), resource.decoded, args.terms)
    print(json.dumps({"status": "scanned", "out": args.out, **summary}, indent=2))
    return 0


def cmd_repack(args: argparse.Namespace) -> int:
    resource = open_input(args)
    require_decoded(resource)
    output, report = repack_script(resource, resource.decoded, allow_growth=args.allow_growth)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(output)
    write_json(out.with_suffix(out.suffix + ".repack_report.json"), {"input": str(resource.path), "output": str(out), **report})
    print(json.dumps({"status": "repacked", "out": str(out), **report}, indent=2))
    return 0


def cmd_patch(args: argparse.Namespace) -> int:
    resource = open_input(args)
    require_decoded(resource)
    recipe_path = Path(args.recipe)
    recipe = load_recipe(recipe_path)
    manifest = write_patch_bundle(resource, recipe_path, recipe, Path(args.out))
    print(json.dumps({"status": "patched", "out": args.out, "manifest": manifest["report_dir"] + "\\manifest.json"}, indent=2))
    return 0


def cmd_recipe(args: argparse.Namespace) -> int:
    recipe_path = Path(args.recipe)
    report = validate_recipe(load_recipe(recipe_path))
    report["recipe"] = str(recipe_path)
    if args.out:
        write_json(Path(args.out), report)
    print(json.dumps(report, indent=2))
    return 0 if report["ready"] else 1


def require_decoded(resource) -> None:
    if resource.decode_error:
        raise ResourceError(resource.decode_error)


def add_input_and_out(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("input")
    parser.add_argument("--out", required=True)
    add_key_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m codered_wsc",
        description="Inspect, scan, report on, and safely patch decoded Red Dead Redemption WSC/XSC script resources.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    inspect = sub.add_parser("inspect", help="Decode a script resource and write resource/string/function reports.")
    add_input_and_out(inspect)
    inspect.set_defaults(func=cmd_inspect)

    disasm = sub.add_parser("disasm", help="Write best-effort bytecode disassembly and candidate maps.")
    add_input_and_out(disasm)
    disasm.set_defaults(func=cmd_disasm)

    scan = sub.add_parser("scan", help="Find terms in decoded script bytes and record nearby context.")
    add_input_and_out(scan)
    scan.add_argument("--terms", required=True, help="Comma-separated decoded byte/string anchors.")
    scan.set_defaults(func=cmd_scan)

    repack = sub.add_parser("repack", help="Decode and rebuild a script with no decoded byte changes.")
    repack.add_argument("input")
    repack.add_argument("--out", required=True)
    repack.add_argument("--allow-growth", action="store_true", help="Allow a larger rebuilt standalone RSC85 payload.")
    add_key_args(repack)
    repack.set_defaults(func=cmd_repack)

    patch = sub.add_parser("patch", help="Apply same-size decoded edits from a YAML recipe to a new script file.")
    patch.add_argument("input")
    patch.add_argument("--recipe", required=True)
    patch.add_argument("--out", required=True)
    add_key_args(patch)
    patch.set_defaults(func=cmd_patch)

    recipe = sub.add_parser("recipe", help="Validate recipe support without patching a script.")
    recipe.add_argument("recipe")
    recipe.add_argument("--out", default="")
    recipe.set_defaults(func=cmd_recipe)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (FileNotFoundError, PatchError, ResourceError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
