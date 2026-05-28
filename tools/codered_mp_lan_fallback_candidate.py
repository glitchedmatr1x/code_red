#!/usr/bin/env python3
"""Generate LAN/System Link SCXML fallback candidates and validation reports.

This is a candidate lane only. It consumes decoded SCXML files from the
Zstandard probe, writes candidate decoded XML copies plus unified diffs, proves
Zstandard encode/decode round-trip integrity, and maps decoded filenames back to
real archive paths. It does not modify RPF archives or game files.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

try:
    import zstandard as zstd
except Exception:
    zstd = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DECODED = ROOT / "logs" / "content_mp_scxml_zstd_probe" / "decoded"
DEFAULT_OUT = ROOT / "logs" / "content_mp_lan_fallback_candidate"

APPROVED_DECODED_NAMES = {
    "root_content_ui_pausemenu_net_lanmenu.sc.xml.decoded.xml",
    "root_content_ui_pausemenu_net_plaympconf.sc.xml.decoded.xml",
}
BLOCKED_NAME_PATTERNS = re.compile(r"(online|profile|netstats|gamespy|publicmenu|privatemenu|titles)", re.I)


@dataclass
class CandidateFile:
    source_decoded: str
    archive_path: str
    candidate_decoded: str
    diff_path: str
    changed: bool
    original_sha1: str
    candidate_sha1: str


@dataclass
class ValidationFinding:
    ok: bool
    check: str
    detail: str


def sha1_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="strict")).hexdigest()


def map_decoded_name_to_archive_path(name: str) -> str:
    suffix = ".decoded.xml"
    if not name.endswith(suffix):
        raise ValueError(f"Decoded SCXML name must end with {suffix}: {name}")
    raw = name[: -len(suffix)]
    if not raw.startswith("root_"):
        raise ValueError(f"Decoded SCXML name must start with root_: {name}")
    return raw.replace("_", "/")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="strict")


def make_lanmenu_candidate(text: str) -> str:
    marker = '    <UIButton desc="mp_fe_goto_online"  target="NetConf_PlayPublic">'
    if "CodeRED_LAN_Fallback" in text:
        return text
    insertion = """    <!-- CodeRED LAN fallback candidate: add a direct LAN/System Link confirmation route without removing online/private routes. -->
    <UIButton desc="mp_fe_play_lan" target="NetConf_PlayLAN">
      <transition event="retry_action">
        <action expr="goto(NetConf_PlayLAN)"></action>
        <action expr="NetMachine.Authenticate('LAN Multiplayer')"></action>
      </transition>
    </UIButton>
"""
    if marker not in text:
        raise ValueError("lanmenu candidate marker not found")
    return text.replace(marker, insertion + marker, 1)


def make_plaympconf_candidate(text: str) -> str:
    old = """  <transition event="auth.fail_NotSignedIn">
    <action expr="Exit(arg0)"></action>
    <action expr="NetAlert_NotSignedIn"></action>
  </transition>"""
    new = """  <!-- CodeRED LAN fallback candidate: if the LAN/System Link confirmation hits the obsolete sign-in branch, reuse the existing auth.success transition instead of opening the sign-in alert. Candidate only; inspect before archive patching. -->
  <transition event="auth.fail_NotSignedIn">
    <action expr="Exit(arg0)"></action>
    <action expr="SendEvent('auth.success')"></action>
  </transition>"""
    if new in text:
        return text
    if old not in text:
        raise ValueError("plaympconf auth.fail_NotSignedIn block not found")
    return text.replace(old, new, 1)


def make_candidate_for(path: Path, text: str) -> str:
    low = path.name.lower()
    if "net_lanmenu.sc.xml.decoded.xml" in low:
        return make_lanmenu_candidate(text)
    if "net_plaympconf.sc.xml.decoded.xml" in low:
        return make_plaympconf_candidate(text)
    raise ValueError(f"Unsupported candidate target: {path.name}")


def iter_all_decoded_xml(decoded: Path) -> list[Path]:
    return sorted(decoded.glob("*.decoded.xml"), key=lambda p: p.name.lower())


def validate_candidate_shape(decoded: Path, changed_files: list[CandidateFile], candidate_texts: dict[str, str]) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    changed_names = {Path(item.source_decoded).name for item in changed_files if item.changed}
    findings.append(
        ValidationFinding(
            changed_names <= APPROVED_DECODED_NAMES,
            "approved_file_scope",
            f"changed={sorted(changed_names)} approved={sorted(APPROVED_DECODED_NAMES)}",
        )
    )
    blocked = [name for name in changed_names if BLOCKED_NAME_PATTERNS.search(name)]
    findings.append(ValidationFinding(not blocked, "blocked_online_profile_netstats_gamespy_scope", f"blocked={blocked}"))

    originals: dict[str, str] = {}
    merged: dict[str, str] = {}
    for path in iter_all_decoded_xml(decoded):
        text = read_text(path)
        originals[path.name] = text
        merged[path.name] = candidate_texts.get(path.name, text)

    original_all = "\n".join(originals.values())
    merged_all = "\n".join(merged.values())
    orig_auth = len(re.findall(r"NetMachine\.Authenticate\s*\(", original_all))
    new_auth = len(re.findall(r"NetMachine\.Authenticate\s*\(", merged_all))
    findings.append(
        ValidationFinding(
            not (orig_auth > 0 and new_auth == 0),
            "does_not_remove_all_authenticate_calls_globally",
            f"original={orig_auth} candidate={new_auth}",
        )
    )
    orig_signin = len(re.findall(r"NetMachine\.ShowSignInUI\s*\(", original_all))
    new_signin = len(re.findall(r"NetMachine\.ShowSignInUI\s*\(", merged_all))
    findings.append(
        ValidationFinding(
            not (orig_signin > 0 and new_signin == 0),
            "does_not_remove_all_show_signin_calls_globally",
            f"original={orig_signin} candidate={new_signin}",
        )
    )
    findings.append(
        ValidationFinding(
            "NetMachine.TriggerMultiplayerLoad(arg2)" in merged_all,
            "preserves_trigger_multiplayer_load_arg2",
            "required call present" if "NetMachine.TriggerMultiplayerLoad(arg2)" in merged_all else "required call missing",
        )
    )
    arg2_changes: list[str] = []
    for name, original in originals.items():
        candidate = merged[name]
        if len(re.findall(r"\barg2\b", original)) != len(re.findall(r"\barg2\b", candidate)):
            arg2_changes.append(name)
    findings.append(
        ValidationFinding(
            not arg2_changes,
            "arg2_unchanged_or_reported",
            f"arg2 count changes={arg2_changes}",
        )
    )
    return findings


def zstd_encode(data: bytes) -> tuple[bytes, str]:
    if zstd is not None:
        return zstd.ZstdCompressor(level=3).compress(data), "python-zstandard"
    zstd_exe = shutil.which("zstd") or shutil.which("zstd.exe")
    if not zstd_exe:
        raise RuntimeError("No Python zstandard module or zstd.exe found")
    proc = subprocess.run([zstd_exe, "-q", "-3", "-c"], input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return proc.stdout, "zstd.exe"


def zstd_decode(data: bytes) -> tuple[bytes, str]:
    if zstd is not None:
        return zstd.ZstdDecompressor().decompress(data), "python-zstandard"
    zstd_exe = shutil.which("zstd") or shutil.which("zstd.exe")
    if not zstd_exe:
        raise RuntimeError("No Python zstandard module or zstd.exe found")
    proc = subprocess.run([zstd_exe, "-q", "-d", "-c"], input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return proc.stdout, "zstd.exe"


def write_roundtrip_report(out: Path, candidates: list[CandidateFile]) -> dict:
    encoded_dir = out / "zstd_encoded"
    encoded_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for item in candidates:
        text = read_text(Path(item.candidate_decoded))
        raw = text.encode("utf-8")
        encoded, encode_method = zstd_encode(raw)
        decoded, decode_method = zstd_decode(encoded)
        encoded_path = encoded_dir / (Path(item.candidate_decoded).name.replace(".decoded.xml", ".zstd"))
        encoded_path.write_bytes(encoded)
        rows.append(
            {
                "candidate_decoded": item.candidate_decoded,
                "archive_path": item.archive_path,
                "encoded_path": str(encoded_path),
                "encode_method": encode_method,
                "decode_method": decode_method,
                "decoded_sha1": hashlib.sha1(raw).hexdigest(),
                "roundtrip_sha1": hashlib.sha1(decoded).hexdigest(),
                "encoded_sha1": hashlib.sha1(encoded).hexdigest(),
                "decoded_size": len(raw),
                "encoded_size": len(encoded),
                "ok": decoded == raw,
            }
        )
    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "candidate_count": len(rows),
        "ok_count": sum(1 for row in rows if row["ok"]),
        "fail_count": sum(1 for row in rows if not row["ok"]),
        "rows": rows,
    }
    (out / "zstd_roundtrip_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def run(decoded: Path, out: Path) -> dict:
    candidate_dir = out / "decoded_candidates"
    diff_dir = out / "candidate_diffs"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    diff_dir.mkdir(parents=True, exist_ok=True)

    candidates: list[CandidateFile] = []
    candidate_texts: dict[str, str] = {}
    for name in sorted(APPROVED_DECODED_NAMES):
        source = decoded / name
        if not source.exists():
            raise FileNotFoundError(source)
        original = read_text(source)
        candidate = make_candidate_for(source, original)
        candidate_texts[source.name] = candidate
        archive_path = map_decoded_name_to_archive_path(source.name)
        candidate_path = candidate_dir / source.name
        diff_path = diff_dir / f"{source.name}.candidate.diff"
        candidate_path.write_bytes(candidate.encode("utf-8"))
        diff = "\n".join(
            difflib.unified_diff(
                original.splitlines(),
                candidate.splitlines(),
                fromfile=str(source),
                tofile=str(candidate_path),
                lineterm="",
            )
        )
        diff_path.write_text(diff + ("\n" if diff else ""), encoding="utf-8")
        candidates.append(
            CandidateFile(
                source_decoded=str(source),
                archive_path=archive_path,
                candidate_decoded=str(candidate_path),
                diff_path=str(diff_path),
                changed=original != candidate,
                original_sha1=sha1_text(original),
                candidate_sha1=sha1_text(candidate),
            )
        )

    findings = validate_candidate_shape(decoded, candidates, candidate_texts)
    roundtrip = write_roundtrip_report(out, candidates)
    ok = all(f.ok for f in findings) and roundtrip["fail_count"] == 0
    summary = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "pass" if ok else "fail",
        "decoded_source": str(decoded),
        "out": str(out),
        "approved_targets": sorted(APPROVED_DECODED_NAMES),
        "candidate_files": [asdict(item) for item in candidates],
        "validation_findings": [asdict(item) for item in findings],
        "zstd_roundtrip_report": str(out / "zstd_roundtrip_report.json"),
        "archive_path_map": {Path(item.source_decoded).name: item.archive_path for item in candidates},
        "rpf_test_prep": {
            "backup": r"%RDR_GAME_DIR%\game\content.rpf",
            "candidate": str(ROOT / "build" / "content_mp_lan_fallback_test" / "content.rpf"),
            "install_target": r"%RDR_GAME_DIR%\game\content.rpf",
            "auto_install": False,
        },
        "first_rpf_test_questions": [
            "Does the game boot?",
            "Does the pause menu still open?",
            "Does LAN/System Link route show or behave differently?",
            "Does it reach loading/MP transition or fail at a later runtime state?",
        ],
    }
    (out / "candidate_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out / "archive_path_map.json").write_text(json.dumps(summary["archive_path_map"], indent=2), encoding="utf-8")
    lines = [
        "# Code RED LAN/System Link Fallback Candidate",
        "",
        f"Status: `{summary['status']}`",
        "",
        "This is a candidate-only lane. It writes decoded XML copies and diffs, not a real RPF patch.",
        "",
        "## Candidate Files",
        "",
    ]
    for item in candidates:
        lines.append(f"- `{item.archive_path}`")
        lines.append(f"  - decoded: `{item.candidate_decoded}`")
        lines.append(f"  - diff: `{item.diff_path}`")
    lines.extend(["", "## Validation", ""])
    for finding in findings:
        lines.append(f"- `{finding.check}`: `{'ok' if finding.ok else 'fail'}` - {finding.detail}")
    lines.extend(
        [
            "",
            "## Zstandard Round Trip",
            "",
            f"- Report: `{out / 'zstd_roundtrip_report.json'}`",
            f"- Failures: `{roundtrip['fail_count']}`",
            "",
            "## RPF Test Prep",
            "",
            r"- backup: `%RDR_GAME_DIR%\game\content.rpf`",
            f"- candidate: `{ROOT / 'build' / 'content_mp_lan_fallback_test' / 'content.rpf'}`",
            r"- install target: `%RDR_GAME_DIR%\game\content.rpf`",
            "- Auto-copy/install: `false`",
        ]
    )
    (out / "LAN_FALLBACK_CANDIDATE_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate LAN/System Link SCXML fallback candidates only.")
    parser.add_argument("--decoded", type=Path, default=DEFAULT_DECODED)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    if not args.decoded.exists():
        raise SystemExit(f"Decoded SCXML folder not found: {args.decoded}")
    summary = run(args.decoded, args.out)
    print(json.dumps({k: v for k, v in summary.items() if k != "candidate_files"}, indent=2))
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
