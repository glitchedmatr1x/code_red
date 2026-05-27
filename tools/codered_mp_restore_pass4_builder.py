#!/usr/bin/env python3
"""Build a copied full-MP content.rpf for Code RED Pass 4 testing.

The live game archive is never written. Raw donor CSC/XSC/hash payloads are
staged under release and release64 paths, a narrow LAN-menu reachability patch
is applied to the copied archive, and conversion experiments remain separate
from the default test RPF unless they have their own validation path.
"""
from __future__ import annotations

import argparse
import binascii
import csv
import difflib
import hashlib
import importlib.util
import json
import shutil
import struct
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

try:
    import zstandard as zstd
except Exception:
    zstd = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
OVERLAY_TOOL = ROOT / "tools" / "codered_content_convert_overlay_builder.py"
XSC_SWAP_TOOL = ROOT / "tools" / "codered_xsc_to_wsc_candidate.py"
DECODED_UI = ROOT / "logs" / "content_mp_scxml_zstd_probe" / "decoded"
LIVE_CONTENT = Path(r"%RDR_GAME_DIR%")
BUILD_ROOT = ROOT / "build" / "mp_content_restore_pass4"
REPORT_FIELDS = [
    "source_kind",
    "source_path",
    "stage_path",
    "archive_path",
    "operation",
    "result",
    "extension",
    "size",
    "sha1",
    "crc32",
    "stored_size",
    "decoded_size",
    "compressed",
    "note",
]
VERIFY_FIELDS = [
    "archive_path",
    "stage_path",
    "entry_index",
    "verification_kind",
    "status",
    "stage_size",
    "archive_size",
    "stage_sha1",
    "archive_sha1",
    "stage_crc32",
    "archive_crc32",
    "note",
]
CONVERSION_FIELDS = [
    "input_path",
    "logical_path",
    "method",
    "output_path",
    "input_header",
    "output_header",
    "status",
    "validation",
    "note",
]
LANMENU_DECODED = "root_content_ui_pausemenu_net_lanmenu.sc.xml.decoded.xml"
PLAYMPCONF_DECODED = "root_content_ui_pausemenu_net_plaympconf.sc.xml.decoded.xml"
LANMENU_ARCHIVE = "root/content/ui/pausemenu/net/lanmenu.sc.xml"
KEY_VERIFY_SUFFIXES = {
    "freemode/freemode.csc",
    "freemode/freemode.xsc",
    "mp_idle.csc",
    "mp_idle.xsc",
    "multiplayer_system_thread.csc",
    "multiplayer_system_thread.xsc",
    "multiplayer_update_thread.csc",
    "multiplayer_update_thread.xsc",
    "pr_multiplayer.csc",
    "pr_multiplayer.xsc",
}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module at {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest().upper()


def crc32_bytes(data: bytes) -> str:
    return f"{binascii.crc32(data) & 0xFFFFFFFF:08X}"


def file_digest(path: Path) -> tuple[int, str, str]:
    data = path.read_bytes()
    return len(data), sha1_bytes(data), crc32_bytes(data)


def rel_from_multiplayer(path: Path) -> Path:
    parts = list(path.parts)
    lows = [part.lower() for part in parts]
    if "multiplayer" not in lows:
        raise ValueError(f"Path does not include multiplayer/: {path}")
    idx = lows.index("multiplayer")
    return Path(*parts[idx + 1 :])


def iter_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted((path for path in root.rglob("*") if path.is_file()), key=lambda path: path.as_posix().lower())


def mirror_stage_file(
    rows: list[dict[str, Any]],
    collisions: list[dict[str, Any]],
    stage_root: Path,
    source: Path,
    source_kind: str,
    rel_tail: Path,
    branch: str,
) -> None:
    dest = stage_root / "content" / branch / "multiplayer" / rel_tail
    size, sha1, crc32 = file_digest(source)
    base = {
        "source_kind": source_kind,
        "source_path": str(source),
        "stage_path": str(dest),
        "extension": source.suffix.lower(),
        "size": size,
        "sha1": sha1,
        "crc32": crc32,
    }
    if dest.exists():
        existing_size, existing_sha1, existing_crc = file_digest(dest)
        if existing_sha1 == sha1:
            rows.append({**base, "result": "stage_duplicate_identical", "note": "same staged bytes already present"})
            return
        collisions.append(
            {
                **base,
                "result": "stage_collision_kept_first",
                "existing_size": existing_size,
                "existing_sha1": existing_sha1,
                "existing_crc32": existing_crc,
                "note": "same archive-relative path from another donor differs; keep first staged raw payload",
            }
        )
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)
    rows.append({**base, "result": "staged", "note": ""})


def stage_tree(args: argparse.Namespace, build_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    stage_root = build_root / "import_ready_full_tree"
    if stage_root.exists():
        if build_root.resolve() not in stage_root.resolve().parents:
            raise RuntimeError(f"Refusing to clear stage root outside Pass 4 build root: {stage_root}")
        shutil.rmtree(stage_root)
    rows: list[dict[str, Any]] = []
    collisions: list[dict[str, Any]] = []
    roots = [
        ("pass1_restore", Path(args.pass1_restore)),
        ("pass1_unresolved_psn", Path(args.pass1_unresolved) / "donor_psn"),
        ("pass1_unresolved_xenon", Path(args.pass1_unresolved) / "donor_xenon"),
        ("pass2_release64_csc", Path(args.pass2_release64_csc)),
        ("pass2_release_csc", Path(args.pass2_release_csc)),
        ("pass2_xsc_review", Path(args.pass2_xsc_review)),
    ]
    for source_kind, source_root in roots:
        for source in iter_files(source_root):
            try:
                tail = rel_from_multiplayer(source)
            except ValueError:
                continue
            # Every raw donor variant gets a release64 test path and release fallback.
            for branch in ("release64", "release"):
                mirror_stage_file(rows, collisions, stage_root, source, source_kind, tail, branch)
    return rows, collisions


def make_lanmenu_candidate(text: str) -> str:
    marker = '    <UIButton desc="mp_fe_goto_online"  target="NetConf_PlayPublic">'
    if "CodeRED Pass4 local LAN access" in text:
        return text
    insertion = """    <!-- CodeRED Pass4 local LAN access: explicit existing LAN/System Link confirmation route. No auth bypass. -->
    <UIButton desc="mp_fe_play_lan" target="NetConf_PlayLAN">
      <transition event="retry_action">
        <action expr="goto(NetConf_PlayLAN)"></action>
        <action expr="NetMachine.Authenticate('LAN Multiplayer')"></action>
      </transition>
    </UIButton>
"""
    if marker not in text:
        raise RuntimeError("LAN menu insertion marker not found")
    return text.replace(marker, insertion + marker, 1)


def make_optional_plaympconf_auth_experiment(text: str) -> str:
    old = """  <transition event="auth.fail_NotSignedIn">
    <action expr="Exit(arg0)"></action>
    <action expr="NetAlert_NotSignedIn"></action>
  </transition>"""
    new = """  <!-- OPTIONAL CodeRED local auth experiment. Not included in the default Pass4 RPF. -->
  <transition event="auth.fail_NotSignedIn">
    <action expr="Exit(arg0)"></action>
    <action expr="SendEvent('auth.success')"></action>
  </transition>"""
    if old not in text:
        raise RuntimeError("PlayMpConf auth.fail_NotSignedIn block not found")
    return text.replace(old, new, 1)


def write_diff(original: str, candidate: str, path: Path, left: str, right: str) -> None:
    diff = "\n".join(
        difflib.unified_diff(
            original.splitlines(),
            candidate.splitlines(),
            fromfile=left,
            tofile=right,
            lineterm="",
        )
    )
    write_text(path, diff + ("\n" if diff else ""))


def prepare_ui_patch(build_root: Path) -> dict[str, Path]:
    patch_root = build_root / "import_ready_full_tree" / "_ui_patch"
    optional_root = build_root / "optional_local_auth_experiment"
    patch_root.mkdir(parents=True, exist_ok=True)
    optional_root.mkdir(parents=True, exist_ok=True)
    lan_source = DECODED_UI / LANMENU_DECODED
    play_source = DECODED_UI / PLAYMPCONF_DECODED
    original_lan = lan_source.read_text(encoding="utf-8")
    default_lan = make_lanmenu_candidate(original_lan)
    default_lan_path = patch_root / "lanmenu.sc.xml.decoded.xml"
    write_text(default_lan_path, default_lan)
    write_text(patch_root / "lanmenu.sc.xml.original.decoded.xml", original_lan)
    write_diff(
        original_lan,
        default_lan,
        patch_root / "lanmenu.sc.xml.default_local_access.diff",
        str(lan_source),
        str(default_lan_path),
    )

    original_play = play_source.read_text(encoding="utf-8")
    optional_play = make_optional_plaympconf_auth_experiment(original_play)
    write_text(optional_root / "plaympconf.sc.xml.original.decoded.xml", original_play)
    write_text(optional_root / "plaympconf.sc.xml.optional_auth_candidate.decoded.xml", optional_play)
    write_diff(
        original_play,
        optional_play,
        optional_root / "plaympconf.sc.xml.optional_auth_candidate.diff",
        str(play_source),
        "optional_auth_candidate",
    )
    return {"default_lanmenu": default_lan_path, "optional_plaympconf": optional_root}


def backup_source(source: Path, build_root: Path) -> tuple[Path, dict[str, Any]]:
    size, sha1, crc = file_digest(source)
    backup = build_root / "original_backups" / f"{source.stem}_original_{sha1[:12]}{source.suffix}"
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        shutil.copy2(source, backup)
    return backup, {"path": str(source), "size": size, "sha1": sha1, "crc32": crc}


def archive_path_from_stage(stage_root: Path, path: Path) -> str:
    return "root/" + path.relative_to(stage_root).as_posix()


def write_archive_copy(
    overlay,
    source: Path,
    output: Path,
    stage_root: Path,
    ui_patch: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    wb = overlay.load_backend()
    info = wb.parse_rpf6(source)
    if info is None:
        raise RuntimeError(f"Source RPF does not parse: {source}")
    root = overlay.build_existing_tree(info)
    ops: list[dict[str, Any]] = []
    for stage_file in iter_files(stage_root / "content"):
        archive_path = archive_path_from_stage(stage_root, stage_file)
        payload = stage_file.read_bytes()
        action, node = overlay.add_or_replace_file(wb, root, archive_path, payload, "add")
        size, sha1, crc = file_digest(stage_file)
        ops.append(
            {
                "source_kind": "import_ready_full_tree",
                "source_path": str(stage_file),
                "stage_path": str(stage_file),
                "archive_path": archive_path,
                "operation": "add",
                "result": action,
                "extension": stage_file.suffix.lower(),
                "size": size,
                "sha1": sha1,
                "crc32": crc,
                "stored_size": node.stored_size,
                "decoded_size": node.decoded_size,
                "compressed": node.force_compressed,
                "note": "raw donor variant staged under its own extension",
            }
        )
    ui_bytes = ui_patch.read_bytes()
    action, node = overlay.add_or_replace_file(wb, root, LANMENU_ARCHIVE, ui_bytes, "replace")
    ops.append(
        {
            "source_kind": "default_ui_access_patch",
            "source_path": str(ui_patch),
            "stage_path": str(ui_patch),
            "archive_path": LANMENU_ARCHIVE,
            "operation": "replace",
            "result": action,
            "extension": ".xml",
            "size": len(ui_bytes),
            "sha1": sha1_bytes(ui_bytes),
            "crc32": crc32_bytes(ui_bytes),
            "stored_size": node.stored_size,
            "decoded_size": node.decoded_size,
            "compressed": node.force_compressed,
            "note": "default local LAN button; compressed SCXML replacement",
        }
    )
    nodes = overlay.flatten_tree(root)
    toc_size = overlay.align(len(nodes) * 20, 16)
    payload_floor = min(int(entry["offset"]) for entry in info["entries"] if entry.get("type") == "file")
    if 16 + toc_size > payload_floor:
        raise RuntimeError(f"New TOC ({16 + toc_size}) would overlap first payload at {payload_floor}")
    original = bytearray(source.read_bytes())
    appended: list[dict[str, Any]] = []
    for node in nodes:
        if node.kind != "file":
            continue
        if node.operation == "preserve":
            node.new_offset = int((node.original or {}).get("offset") or 0)
            continue
        node.new_offset = overlay.align(len(original), overlay.payload_alignment(node))
        if node.new_offset > len(original):
            original.extend(b"\x00" * (node.new_offset - len(original)))
        payload = node.source_bytes or b""
        original.extend(payload)
        padded = overlay.align(len(original), 8)
        if padded > len(original):
            original.extend(b"\x00" * (padded - len(original)))
        appended.append(
            {
                "archive_path": node.archive_path,
                "entry_index": node.index,
                "operation": node.operation,
                "offset": node.new_offset,
                "stored_size": node.stored_size,
                "decoded_size": node.decoded_size,
                "compressed": node.force_compressed,
            }
        )
    toc = overlay.pack_toc(wb, nodes, bool(info.get("enc_flag")))
    struct.pack_into(">4I", original, 0, 0x52504636, len(nodes), int(info.get("debug_offset") or 0), int(info.get("enc_flag") or 0))
    original[16 : 16 + len(toc)] = toc
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(original)
    check = wb.parse_rpf6(output)
    if check is None:
        raise RuntimeError(f"Built RPF does not parse: {output}")
    return (
        {
            "source_entry_count": info.get("entry_count"),
            "output_entry_count": check.get("entry_count"),
            "source_file_count": info.get("file_count"),
            "output_file_count": check.get("file_count"),
            "toc_size": toc_size,
            "payload_floor": payload_floor,
            "appended_count": len(appended),
            "appended": appended,
            "output_info": check,
        },
        ops,
    )


def raw_entry_payload(archive: Path, entry: dict[str, Any]) -> bytes:
    with archive.open("rb") as handle:
        handle.seek(int(entry["offset"]))
        return handle.read(int(entry["size_in_archive"]))


def entry_map(info: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(entry.get("path") or "").replace("\\", "/").lower(): entry
        for entry in info.get("entries", [])
        if entry.get("type") == "file"
    }


def verify_archive(
    archive: Path,
    info: dict[str, Any],
    ops: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entries = entry_map(info)
    rows: list[dict[str, Any]] = []
    for op in ops:
        archive_path = str(op["archive_path"])
        entry = entries.get(archive_path.lower())
        stage_path = Path(str(op["stage_path"]))
        if entry is None:
            rows.append({"archive_path": archive_path, "stage_path": str(stage_path), "status": "missing_entry"})
            continue
        payload = raw_entry_payload(archive, entry)
        staged = stage_path.read_bytes()
        if op["source_kind"] == "default_ui_access_patch":
            if zstd is None:
                rows.append(
                    {
                        "archive_path": archive_path,
                        "stage_path": str(stage_path),
                        "entry_index": entry.get("index"),
                        "verification_kind": "zstd_decoded_ui",
                        "status": "decoder_missing",
                        "note": "Python zstandard unavailable",
                    }
                )
                continue
            exported = zstd.ZstdDecompressor().decompress(payload)
            kind = "zstd_decoded_ui"
        else:
            exported = payload
            kind = "raw_added_payload"
        status = "exact_match" if exported == staged else "mismatch"
        rows.append(
            {
                "archive_path": archive_path,
                "stage_path": str(stage_path),
                "entry_index": entry.get("index"),
                "verification_kind": kind,
                "status": status,
                "stage_size": len(staged),
                "archive_size": len(exported),
                "stage_sha1": sha1_bytes(staged),
                "archive_sha1": sha1_bytes(exported),
                "stage_crc32": crc32_bytes(staged),
                "archive_crc32": crc32_bytes(exported),
                "note": op.get("note", ""),
            }
        )
    return rows


def swap32(data: bytes) -> bytes:
    words = len(data) // 4
    swapped = bytearray()
    for idx in range(words):
        swapped.extend(data[idx * 4 : idx * 4 + 4][::-1])
    swapped.extend(data[words * 4 :])
    return bytes(swapped)


def conversion_attempts(build_root: Path, stage_root: Path) -> list[dict[str, Any]]:
    converted_root = build_root / "converted"
    blocked_root = build_root / "conversion_blocked"
    converted_root.mkdir(parents=True, exist_ok=True)
    blocked_root.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    xsc_files = [path for path in iter_files(stage_root / "content" / "release64" / "multiplayer") if path.suffix.lower() == ".xsc"]
    for xsc in xsc_files:
        data = xsc.read_bytes()
        rel = xsc.relative_to(stage_root / "content" / "release64" / "multiplayer")
        out = converted_root / "xsc_word_swap_wsc_candidates" / rel.with_suffix(".wsc")
        candidate = swap32(data)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(candidate)
        rows.append(
            {
                "input_path": str(xsc),
                "logical_path": rel.as_posix(),
                "method": "existing_xsc_word_swap_candidate",
                "output_path": str(out),
                "input_header": data[:4].hex(" ").upper(),
                "output_header": candidate[:4].hex(" ").upper(),
                "status": "candidate_only",
                "validation": "header_rsc85" if candidate.startswith(b"RSC\x85") else "header_not_rsc85",
                "note": "existing Code RED word-swap method; not injected because arbitrary donor XSC runtime reopen compatibility is not proven",
            }
        )
    sccl = ROOT / "SC-CL-master" / "bin" / "SC-CL.exe"
    probe = ROOT / "logs" / "sccl_wsc_probe" / "codered_launch_freemode_probe.wsc"
    rows.append(
        {
            "input_path": str(sccl),
            "logical_path": "tiny_source_compile_feasibility",
            "method": "sccl_existing_probe",
            "output_path": str(probe) if probe.exists() else "",
            "input_header": "",
            "output_header": probe.read_bytes()[:4].hex(" ").upper() if probe.exists() else "",
            "status": "source_required" if sccl.exists() else "tool_missing",
            "validation": "existing_probe_rsc85" if probe.exists() and probe.read_bytes().startswith(b"RSC\x85") else "no_existing_rsc85_probe",
            "note": "SC-CL is source compiler evidence only here; it does not ingest donor compiled CSC/XSC/SCO in this pass",
        }
    )
    write_text(
        blocked_root / "README.md",
        "# Pass 4 Conversion Blocked\n\n"
        "Raw CSC/XSC/hash donor variants are still injected under their original extensions.\n\n"
        "XSC word-swap WSC files in `../converted/` are candidates only and are not included in the default RPF. "
        "CSC swapped RSC86 donor conversion has no validated PC rewrap path in this pass.\n",
    )
    return rows


def mp_counts(info: dict[str, Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for path in entry_map(info):
        if "/multiplayer/" not in path:
            continue
        if "/content/release64/" in path:
            branch = "release64"
        elif "/content/release/" in path:
            branch = "release"
        else:
            branch = "other"
        suffix = Path(path).suffix.lower() or "(no_ext)"
        counts[f"{branch}:{suffix}"] += 1
    return dict(counts)


def report_markdown(
    source_meta: dict[str, Any],
    backup: Path,
    output: Path,
    staged_rows: list[dict[str, Any]],
    collisions: list[dict[str, Any]],
    ops: list[dict[str, Any]],
    build: dict[str, Any],
    verify: list[dict[str, Any]],
) -> str:
    op_counts = Counter(str(row.get("result", "")) for row in ops)
    verify_counts = Counter(str(row.get("status", "")) for row in verify)
    counts = mp_counts(build["output_info"])
    lines = [
        "# Code RED Multiplayer Restore Pass 4 Build Report",
        "",
        "## Safety",
        "",
        f"- Source archive: `{source_meta['path']}`",
        f"- Source SHA1 before/after guard: `{source_meta['sha1']}`",
        f"- Copied source backup: `{backup}`",
        f"- Ready cloned RPF: `{output}`",
        "- Original archive is read and copied only. No install is performed.",
        "- Default RPF does not include the optional auth experiment.",
        "",
        "## Full MP tree",
        "",
        f"- Stage rows: `{len(staged_rows)}`",
        f"- Stage collisions kept-first: `{len(collisions)}`",
        f"- RPF operation results: `{dict(op_counts)}`",
        f"- Source entries: `{build['source_entry_count']}`",
        f"- Output entries: `{build['output_entry_count']}`",
        f"- Multiplayer entry counts by branch/extension: `{counts}`",
        "",
        "Pass 4 mirrors raw staged donor variants into both `content/release64/multiplayer/` and "
        "`content/release/multiplayer/`. Different extensions are preserved side by side. Same-path donor "
        "collisions keep the first staged raw payload and stay visible in the manifest.",
        "",
        "## Default UI access patch",
        "",
        "The default archive replaces only `content/ui/pausemenu/net/lanmenu.sc.xml` with a Zstandard-compressed "
        "decoded candidate that adds an explicit existing `NetConf_PlayLAN` button. It does not bypass auth, "
        "public matchmaking, profiles, or external services. Existing pause/networking/PlayMpConf/lobby route "
        "evidence is documented in `mp_pass4_ui_access_patch.md`.",
        "",
        "## Import/export verification",
        "",
        f"- Verification results: `{dict(verify_counts)}`",
        "- Raw injected payloads are read back from the cloned RPF and compared to staged source bytes.",
        "- The compressed UI patch is exported as raw RPF payload, Zstandard-decoded, then compared to its staged XML.",
        "",
    ]
    return "\n".join(lines) + "\n"


def conversion_blocked_md(rows: list[dict[str, Any]]) -> str:
    blocked = [row for row in rows if row["status"] in {"candidate_only", "source_required", "tool_missing"}]
    lines = [
        "# Code RED Pass 4 Conversion Blocked",
        "",
        "Failed or incomplete conversion does not block the raw full-MP RPF build.",
        "",
        f"- Conversion attempt rows: `{len(rows)}`",
        f"- Candidate/block rows: `{len(blocked)}`",
        "",
        "## Findings",
        "",
        "- XENON XSC word-swap can produce RSC85-looking WSC candidates through the existing Code RED method.",
        "- Those WSC candidates are kept in `converted/` and are not injected by default because runtime compatibility is not proven.",
        "- SC-CL exists and the prior tiny WSC probe has an RSC85 header, but SC-CL requires source input; it is not a donor compiled-script converter here.",
        "- PSN CSC swapped RSC86 donor conversion stays blocked without a validated RDR PC rewrap/reopen path.",
        "",
    ]
    return "\n".join(lines) + "\n"


def ui_patch_md(build_root: Path) -> str:
    return "\n".join(
        [
            "# Code RED Pass 4 UI Access Patch",
            "",
            "## Default patch in ready RPF",
            "",
            "- Archive path: `root/content/ui/pausemenu/net/lanmenu.sc.xml`",
            "- Change: add explicit LAN/System Link route button targeting `NetConf_PlayLAN`.",
            "- Candidate files and diff: `import_ready_full_tree/_ui_patch/`.",
            "- This keeps `NetMachine.Authenticate('LAN Multiplayer')` on the route. It is not an auth bypass.",
            "",
            "## Existing route context",
            "",
            "- `pausemenuscene.sc.xml` already enters `NetworkingLayerOffline`.",
            "- `networking.sc.xml` already includes the LAN tab and `NetConf_PlayLAN` message box.",
            "- `NetConf_PlayLAN` includes `net/PlayMpConf.sc` with LAN args.",
            "- `PlayMpConf.sc` leads from `auth.success` to `NetMachine.TriggerMultiplayerLoad(arg2)`.",
            "- lobby main resources already expose `MULTI_FREE_ROAM`, `SetGameWish`, and `StartGameWish` lanes.",
            "",
            "## Optional auth experiment",
            "",
            f"- Folder: `{build_root / 'optional_local_auth_experiment'}`",
            "- Candidate only: PlayMpConf `auth.fail_NotSignedIn` forwards to `auth.success`.",
            "- It is not in `content_mp_restore_pass4_full_mp.rpf` unless a later explicit build opts into it.",
            "",
        ]
    ) + "\n"


def test_steps_md(output: Path) -> str:
    return "\n".join(
        [
            "# Code RED Pass 4 Test Steps",
            "",
            f"Ready cloned RPF: `{output}`",
            "",
            "1. Back up the current active `content.rpf`.",
            "2. Temporarily replace the active `content.rpf` with `content_mp_restore_pass4_full_mp.rpf`.",
            "3. Launch the game.",
            "4. Check main menu, pause menu, and Networking route.",
            "5. Look for LAN, System Link, Multiplayer, and Free Roam route behavior.",
            "6. Record: option appears, option selects, PlayMpConf reachability, Authenticate failure, loading trigger, crash/hang/return result.",
            "7. Restore the original `content.rpf` if the test archive fails.",
            "",
            "The Pass 4 tool does not install this archive automatically.",
            "",
        ]
    ) + "\n"


def run(args: argparse.Namespace) -> dict[str, Any]:
    overlay = load_module(OVERLAY_TOOL, "codered_pass4_overlay")
    build_root = Path(args.build_root)
    reports = build_root / "reports"
    build_root.mkdir(parents=True, exist_ok=True)
    source = Path(args.source)
    backup, source_before = backup_source(source, build_root)
    staged_rows, collisions = stage_tree(args, build_root)
    ui_paths = prepare_ui_patch(build_root)
    stage_root = build_root / "import_ready_full_tree"
    output = build_root / "content_mp_restore_pass4_full_mp.rpf"
    build, ops = write_archive_copy(overlay, source, output, stage_root, ui_paths["default_lanmenu"])
    verify = verify_archive(output, build["output_info"], ops)
    conversions = conversion_attempts(build_root, stage_root)
    source_after = {"sha1": file_digest(source)[1], "crc32": file_digest(source)[2], "size": file_digest(source)[0]}
    if source_after["sha1"] != source_before["sha1"]:
        raise RuntimeError("Source content.rpf changed during Pass 4 build")
    write_csv(reports / "mp_pass4_rpf_injection_manifest.csv", ops, REPORT_FIELDS)
    write_csv(reports / "mp_pass4_conversion_attempts.csv", conversions, CONVERSION_FIELDS)
    write_csv(reports / "mp_pass4_import_export_verification.csv", verify, VERIFY_FIELDS)
    write_text(reports / "mp_pass4_build_report.md", report_markdown(source_before, backup, output, staged_rows, collisions, ops, build, verify))
    write_text(reports / "mp_pass4_conversion_blocked.md", conversion_blocked_md(conversions))
    write_text(reports / "mp_pass4_ui_access_patch.md", ui_patch_md(build_root))
    write_text(reports / "mp_pass4_test_steps.md", test_steps_md(output))
    write_csv(reports / "mp_pass4_stage_manifest.csv", staged_rows, ["source_kind", "source_path", "stage_path", "result", "extension", "size", "sha1", "crc32", "note"])
    write_csv(
        reports / "mp_pass4_stage_collisions.csv",
        collisions,
        ["source_kind", "source_path", "stage_path", "result", "extension", "size", "sha1", "crc32", "existing_size", "existing_sha1", "existing_crc32", "note"],
    )
    summary = {
        "tool": "codered_mp_restore_pass4_builder",
        "source_archive": str(source),
        "source_unchanged": True,
        "source_sha1": source_before["sha1"],
        "backup": str(backup),
        "output": str(output),
        "output_size": output.stat().st_size,
        "output_entry_count": build["output_entry_count"],
        "mp_counts": mp_counts(build["output_info"]),
        "operation_counts": dict(Counter(str(row["result"]) for row in ops)),
        "verification_counts": dict(Counter(str(row["status"]) for row in verify)),
        "conversion_counts": dict(Counter(str(row["status"]) for row in conversions)),
        "reports": str(reports),
        "optional_auth_experiment_in_default_rpf": False,
        "no_auto_install": True,
    }
    write_text(reports / "mp_pass4_build_summary.json", json.dumps(summary, indent=2) + "\n")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build copied Pass 4 full-MP content.rpf with narrow LAN UI access patch.")
    parser.add_argument("--source", default=str(LIVE_CONTENT))
    parser.add_argument("--build-root", default=str(BUILD_ROOT))
    parser.add_argument("--pass1-restore", default=str(ROOT / "build" / "mp_content_restore_pass1" / "restore"))
    parser.add_argument("--pass1-unresolved", default=str(ROOT / "build" / "mp_content_restore_pass1" / "unresolved"))
    parser.add_argument("--pass2-release64-csc", default=str(ROOT / "build" / "mp_content_restore_pass2" / "import_test_release64_csc"))
    parser.add_argument("--pass2-release-csc", default=str(ROOT / "build" / "mp_content_restore_pass2" / "import_test_release_csc"))
    parser.add_argument("--pass2-xsc-review", default=str(ROOT / "build" / "mp_content_restore_pass2" / "import_test_xsc_review"))
    args = parser.parse_args(argv)
    print(json.dumps(run(args), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
