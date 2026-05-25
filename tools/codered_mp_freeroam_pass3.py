"""Build the Code RED MP Freeroam Pass 3 drop-in test package.

This pass intentionally avoids writing a new RPF.  The current overlay builder
can safely replace known resource entries, but adding a brand-new WSC resource
entry has not been proven enough for this bootstrap path.  The output is an
import-ready tree that combines the restored MP content, XML route, and Pass 2
normal update-thread hook.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUILD = ROOT / "build" / "mp_freeroam_pass3"
DEFAULT_REPORTS = ROOT / "reports"

PASS4_TREE = ROOT / "build" / "mp_content_restore_pass4" / "import_ready_full_tree"
PASS4_LANMENU = PASS4_TREE / "_ui_patch" / "lanmenu.sc.xml.decoded.xml"
PASS5_XML = ROOT / "build" / "mp_content_restore_pass5" / "xml_candidates" / "combined"
PASS2_DROPIN = ROOT / "build" / "mp_bootstrap_pass2" / "dropin"

XML_ROUTE_FILES = [
    (
        PASS5_XML / "content__ui__pausemenu__pausemenuscene.sc.xml.decoded.xml",
        Path("content/ui/pausemenu/pausemenuscene.sc.xml"),
        "xml_route",
        "Pass 5 combined pause parent route with PM_CodeRED_LAN marker",
    ),
    (
        PASS5_XML / "content__ui__pausemenu__networking.sc.xml.decoded.xml",
        Path("content/ui/pausemenu/networking.sc.xml"),
        "xml_route",
        "Pass 5 combined networking parent route with NetOffTab_CodeREDLAN marker",
    ),
    (
        PASS4_LANMENU,
        Path("content/ui/pausemenu/net/lanmenu.sc.xml"),
        "xml_route",
        "Pass 4 variant 02 LAN menu route with NetConf_PlayLAN access",
    ),
]

BOOTSTRAP_FILES = [
    (
        PASS2_DROPIN / "content" / "release64" / "scripting" / "designerdefined" / "long_update_thread.wsc",
        Path("content/release64/scripting/designerdefined/long_update_thread.wsc"),
        "wsc_bootstrap",
        "Pass 2 normal update-thread hook replacing trafficDebugThread path",
    ),
    (
        PASS2_DROPIN / "content" / "release64" / "scripting" / "designerdefined" / "codered_mp_bootstrap_minimal.wsc",
        Path("content/release64/scripting/designerdefined/codered_mp_bootstrap_minimal.wsc"),
        "wsc_bootstrap",
        "Pass 1 generated bootstrap WSC launched by Pass 2 hook",
    ),
]

REQUIRED_MARKERS = {
    Path("content/ui/pausemenu/pausemenuscene.sc.xml"): ["PM_CodeRED_LAN", "CodeRED"],
    Path("content/ui/pausemenu/networking.sc.xml"): ["NetOffTab_CodeREDLAN", "CodeRED", "NetConf_PlayLAN"],
    Path("content/ui/pausemenu/net/lanmenu.sc.xml"): ["NetConf_PlayLAN"],
}


def sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def crc32_file(path: Path) -> str:
    import zlib

    crc = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            crc = zlib.crc32(chunk, crc)
    return f"{crc & 0xFFFFFFFF:08X}"


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        if not fields:
            return
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def copy_one(
    source: Path,
    relative_target: Path,
    output_root: Path,
    component: str,
    note: str,
    operation: str,
) -> dict[str, Any]:
    if not source.exists():
        raise FileNotFoundError(source)
    target = output_root / relative_target
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return {
        "component": component,
        "operation": operation,
        "archive_path": "root/" + relative_target.as_posix(),
        "relative_path": relative_target.as_posix(),
        "source_path": str(source),
        "output_path": str(target),
        "extension": target.suffix,
        "size": target.stat().st_size,
        "sha1": sha1_file(target),
        "crc32": crc32_file(target),
        "note": note,
    }


def copy_tree_files(source_root: Path, output_root: Path, component: str) -> list[dict[str, Any]]:
    if not source_root.exists():
        raise FileNotFoundError(source_root)
    rows: list[dict[str, Any]] = []
    for source in sorted((source_root / "content").rglob("*")):
        if not source.is_file():
            continue
        relative = source.relative_to(source_root)
        rows.append(
            copy_one(
                source,
                relative,
                output_root,
                component,
                "Pass 4 full MP restore raw donor variant",
                "copy",
            )
        )
    return rows


def summarize_package(output_root: Path, manifest_rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_component = Counter(row["component"] for row in manifest_rows)
    by_release_ext: Counter[str] = Counter()
    for row in manifest_rows:
        path = row["relative_path"]
        ext = row["extension"] or "(no_ext)"
        if path.startswith("content/release64/multiplayer/"):
            by_release_ext[f"release64:{ext}"] += 1
        elif path.startswith("content/release/multiplayer/"):
            by_release_ext[f"release:{ext}"] += 1

    marker_status: list[dict[str, Any]] = []
    for relative, markers in REQUIRED_MARKERS.items():
        path = output_root / relative
        text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
        marker_status.append(
            {
                "relative_path": relative.as_posix(),
                "exists": path.exists(),
                "markers_present": [marker for marker in markers if marker in text],
                "markers_missing": [marker for marker in markers if marker not in text],
            }
        )

    required_paths = [
        Path("content/release64/multiplayer"),
        Path("content/release/multiplayer"),
        Path("content/release64/scripting/designerdefined/long_update_thread.wsc"),
        Path("content/release64/scripting/designerdefined/codered_mp_bootstrap_minimal.wsc"),
    ]
    required_status = [
        {"relative_path": path.as_posix(), "exists": (output_root / path).exists()} for path in required_paths
    ]

    return {
        "output_root": str(output_root),
        "total_files": len(manifest_rows),
        "by_component": dict(sorted(by_component.items())),
        "mp_extension_counts": dict(sorted(by_release_ext.items())),
        "required_status": required_status,
        "xml_marker_status": marker_status,
    }


def write_reports(build_root: Path, reports_root: Path, summary: dict[str, Any], manifest_rows: list[dict[str, Any]]) -> None:
    dropin = build_root / "dropin_import_ready"
    report = f"""# Code RED MP Freeroam Pass 3 Build Report

## Output

- Drop-in package: `{dropin}`
- RPF output: not written in this pass.

## Why this is a drop-in package

The current RPF overlay path is proven for full MP raw file adds and for replacing
existing resource entries.  Adding the new `codered_mp_bootstrap_minimal.wsc` as a
brand-new WSC resource entry is still risky because new WSC entries may not inherit
the correct resource-entry flags.  This pass therefore produces the allowed
import-ready folder instead of a cloned RPF.

## Included Pieces

- Full Pass 4 restored MP directory under `content/release64/multiplayer/`.
- Full Pass 4 restored MP directory under `content/release/multiplayer/`.
- Pass 5 combined XML route for `pausemenuscene.sc.xml` and `networking.sc.xml`.
- Pass 4 variant 02 LAN menu XML route for `net/lanmenu.sc.xml`.
- Pass 2 patched `long_update_thread.wsc`.
- Pass 1 generated `codered_mp_bootstrap_minimal.wsc`.

## Counts

- Total files staged: `{summary["total_files"]}`
- By component: `{summary["by_component"]}`
- MP extension counts: `{summary["mp_extension_counts"]}`

## Safety

- Original `game/content.rpf` was not modified.
- No public-server spoofing or public matchmaking patch is included.
- No default auth bypass is included.
- No optional sector/catacombs patch is included because Pass 5 did not validate a safe sector edit.
- This build does not depend on a nonexistent `multiplayer_update_thread.wsc`; it imports raw donor `.csc`/`.xsc` variants and starts from the normal PC `long_update_thread.wsc` hook.
"""
    (reports_root / "mp_freeroam_pass3_build_report.md").write_text(report, encoding="utf-8")

    risks = """# Code RED MP Freeroam Pass 3 Known Risks

- If there is no behavior change, the redirected `trafficDebugThread` launch slot may not be reached at runtime.
- If the game crashes when the script starts, the bootstrap likely fired but the restored MP backend script format/path/resource wrapper is wrong.
- If loading starts and hangs, the backend likely starts partially and the next blocker is session or game state.
- Magic RDR import/export verification is required before launch.  If Magic RDR does not encode/import decoded `.sc.xml` resources correctly, use the existing Pass 5 RPF as the base and import only the Pass 2 WSC files.
- Donor CSC/XSC files are included as raw variants only.  XSC/CSC-to-PC-WSC conversion remains blocked until the wrapper/compression lane is proven.
- The bootstrap path is a same-size replacement of an existing script path, not a new bytecode launch block.
"""
    (reports_root / "mp_freeroam_pass3_known_risks.md").write_text(risks, encoding="utf-8")

    steps = f"""# Code RED MP Freeroam Pass 3 Test Steps

1. Back up the current game `content.rpf`.
2. Import the package at:
   `{dropin}`
3. Reopen the target RPF in Magic RDR before launching.
4. Export and byte-compare spot checks:
   - `root/content/release64/scripting/designerdefined/long_update_thread.wsc`
   - `root/content/release64/scripting/designerdefined/codered_mp_bootstrap_minimal.wsc`
   - `root/content/ui/pausemenu/pausemenuscene.sc.xml`
   - `root/content/ui/pausemenu/networking.sc.xml`
   - `root/content/ui/pausemenu/net/lanmenu.sc.xml`
   - one restored `freemode`/`pr_multiplayer` MP script from `release64/multiplayer`
5. Launch the game.
6. Open the pause/menu route and select the Code RED Free Roam / LAN / MP option.
7. Record whether:
   - backend scripts start,
   - loading starts,
   - Free Roam world state appears,
   - crash/hang behavior changes,
   - missing script/resource behavior changes.
8. Interpret first failure:
   - no change: normal thread hook did not fire,
   - crash on script start: bootstrap fired but MP backend script format/path/resource is wrong,
   - loading begins then hangs: backend partially starts and next blocker is session/game state,
   - world loads: keep iterating from this build.
9. Restore the original `content.rpf` after testing if needed.
"""
    (reports_root / "mp_freeroam_pass3_test_steps.md").write_text(steps, encoding="utf-8")

    write_csv(reports_root / "mp_freeroam_pass3_manifest.csv", manifest_rows)
    write_json(build_root / "mp_freeroam_pass3_summary.json", summary)


def build_package(build_root: Path, reports_root: Path) -> dict[str, Any]:
    dropin = build_root / "dropin_import_ready"
    if build_root.exists():
        shutil.rmtree(build_root)
    dropin.mkdir(parents=True, exist_ok=True)
    reports_root.mkdir(parents=True, exist_ok=True)

    manifest_rows: list[dict[str, Any]] = []
    manifest_rows.extend(copy_tree_files(PASS4_TREE, dropin, "mp_restore"))

    for source, relative, component, note in XML_ROUTE_FILES:
        manifest_rows.append(copy_one(source, relative, dropin, component, note, "replace_or_import"))

    for source, relative, component, note in BOOTSTRAP_FILES:
        manifest_rows.append(copy_one(source, relative, dropin, component, note, "replace_or_import"))

    summary = summarize_package(dropin, manifest_rows)

    missing_required = [row for row in summary["required_status"] if not row["exists"]]
    missing_markers = [row for row in summary["xml_marker_status"] if row["markers_missing"]]
    if missing_required:
        raise RuntimeError(f"Missing required package paths: {missing_required}")
    if missing_markers:
        raise RuntimeError(f"Missing XML route markers: {missing_markers}")

    write_reports(build_root, reports_root, summary, manifest_rows)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-root", type=Path, default=DEFAULT_BUILD)
    parser.add_argument("--reports", type=Path, default=DEFAULT_REPORTS)
    args = parser.parse_args()

    summary = build_package(args.build_root, args.reports)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
