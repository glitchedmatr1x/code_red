#!/usr/bin/env python3
"""Probe a local SC-CL-master source folder for Red Dead Redemption readiness.

This does not build SC-CL. It tells Code RED whether the staged SC-CL source
appears to be the right family for RDR script compilation and whether a built
SC-CL.exe already exists in common output locations.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

VERSION = "1.0.0-sccl-source-probe"
REPORT_JSON = Path("logs/CodeRED_SCCL_Source_Probe_Report.json")
REPORT_MD = Path("logs/CodeRED_SCCL_Source_Probe_Report.md")

RDR_TOKENS = [
    "Red Dead Redemption",
    "RDR_SCO",
    "RDR_#SC",
    "SCO format",
    "XSC format",
    "CSC format",
]

SOURCE_MARKERS = [
    "README.md",
    "README.txt",
    "CMakeLists.txt",
    "SC-CL.sln",
    "llvm-14.0.0.src",
    "src",
    "include",
]

EXE_CANDIDATES = [
    "SC-CL.exe",
    "bin/SC-CL.exe",
    "build/SC-CL.exe",
    "Release/SC-CL.exe",
    "x64/Release/SC-CL.exe",
    "llvm-14.0.0.src/MinSizeRel/bin/SC-CL.exe",
]


@dataclass
class SourceCandidate:
    path: str
    exists: bool
    score: int = 0
    rdr_tokens_found: list[str] = field(default_factory=list)
    markers_found: list[str] = field(default_factory=list)
    exe_found: str | None = None
    readme: str | None = None


@dataclass
class ProbeReport:
    version: str
    generated_utc: str
    root: str
    ok: bool
    best_source: str | None
    rdr_ready: bool
    sccl_exe: str | None
    candidates: list[SourceCandidate]
    next_steps: list[str]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def root_from_arg(raw: str | None) -> Path:
    return Path(raw).resolve() if raw else Path(__file__).resolve().parents[1]


def candidate_dirs(root: Path, explicit: str | None) -> list[Path]:
    out: list[Path] = []
    if explicit:
        out.append(Path(explicit).resolve())
    out.extend([
        root / "SC-CL-master",
        root / "SC-CL",
        root / "resources" / "SC-CL-master",
        root / "resources" / "SC-CL",
        root / "resources" / "sc-cl-master",
        root / "related_apps" / "code_red_sccl_attempt_bundle_v1" / "SC-CL-master",
        root / "related_apps" / "code_red_sccl_attempt_bundle_v1" / "SC-CL",
    ])
    seen: set[str] = set()
    unique: list[Path] = []
    for path in out:
        key = str(path).lower()
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def probe_candidate(path: Path) -> SourceCandidate:
    cand = SourceCandidate(path=str(path), exists=path.exists())
    if not path.exists():
        return cand
    for marker in SOURCE_MARKERS:
        if (path / marker).exists():
            cand.markers_found.append(marker)
            cand.score += 1
    for rel in EXE_CANDIDATES:
        exe = path / rel
        if exe.exists():
            cand.exe_found = str(exe)
            cand.score += 5
            break
    readme_paths = [path / "README.md", path / "README.txt", path / "readme.md", path / "readme.txt"]
    text_parts: list[str] = []
    for readme in readme_paths:
        if readme.exists():
            cand.readme = str(readme)
            text_parts.append(read_file(readme))
    if not text_parts:
        for maybe in list(path.glob("*.md"))[:5] + list(path.glob("*.txt"))[:5]:
            text_parts.append(read_file(maybe))
    blob = "\n".join(text_parts)
    for token in RDR_TOKENS:
        if token.lower() in blob.lower():
            cand.rdr_tokens_found.append(token)
            cand.score += 3
    # Also search shallow source files for target tokens if README is absent.
    if not cand.rdr_tokens_found:
        for file in list(path.rglob("*"))[:1000]:
            if file.is_file() and file.suffix.lower() in {".h", ".hpp", ".cpp", ".c", ".txt", ".md"}:
                txt = read_file(file)
                hits = [t for t in RDR_TOKENS if t.lower() in txt.lower()]
                if hits:
                    for hit in hits:
                        if hit not in cand.rdr_tokens_found:
                            cand.rdr_tokens_found.append(hit)
                            cand.score += 3
                    break
    return cand


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def markdown(report: ProbeReport) -> str:
    lines = [
        "# Code RED SC-CL Source Probe Report",
        "",
        f"Generated UTC: `{report.generated_utc}`",
        f"RDR-ready source detected: **{report.rdr_ready}**",
        f"SC-CL.exe detected: `{report.sccl_exe}`",
        f"Best source: `{report.best_source}`",
        "",
        "## Candidates",
        "",
    ]
    for cand in report.candidates:
        lines.extend([
            f"### `{cand.path}`",
            f"- exists: `{cand.exists}`",
            f"- score: `{cand.score}`",
            f"- exe_found: `{cand.exe_found}`",
            f"- readme: `{cand.readme}`",
            f"- markers: `{', '.join(cand.markers_found)}`",
            f"- rdr_tokens: `{', '.join(cand.rdr_tokens_found)}`",
            "",
        ])
    lines.extend(["## Next Steps", ""])
    lines.extend(f"- {step}" for step in report.next_steps)
    return "\n".join(lines) + "\n"


def run_probe(root: Path, explicit: str | None) -> ProbeReport:
    cands = [probe_candidate(path) for path in candidate_dirs(root, explicit)]
    best = max(cands, key=lambda c: c.score, default=None)
    exe = next((c.exe_found for c in cands if c.exe_found), None)
    rdr_ready = any("RDR_SCO" in c.rdr_tokens_found or "RDR_#SC" in c.rdr_tokens_found or "Red Dead Redemption" in c.rdr_tokens_found for c in cands)
    next_steps: list[str]
    if exe:
        next_steps = [
            f"Run: py -3 tools\\codered_sccl_easy_setup.py adopt --sccl \"{exe}\" --run-validator",
            "Run: related_apps\\code_red_sccl_attempt_bundle_v1\\code_red_sccl_windows_build_kit_v1\\run_build_then_compile_vehicle_menu_probe.bat",
        ]
    elif rdr_ready:
        next_steps = [
            "This appears to be the right SC-CL source family for RDR, but no SC-CL.exe was found.",
            "Build SC-CL from this source or obtain its Windows executable, then place SC-CL.exe in resources\\SC-CL_DROP_HERE.",
            "Run: py -3 tools\\codered_sccl_easy_setup.py adopt --sccl resources\\SC-CL_DROP_HERE\\SC-CL.exe --run-validator",
        ]
    else:
        next_steps = [
            "No RDR-ready SC-CL source markers were found. Confirm the folder is GTAResources/SC-CL or equivalent.",
            "A correct README should mention Red Dead Redemption and targets RDR_SCO / RDR_#SC.",
        ]
    report = ProbeReport(
        version=VERSION,
        generated_utc=utc_now(),
        root=str(root),
        ok=rdr_ready,
        best_source=best.path if best and best.exists else None,
        rdr_ready=rdr_ready,
        sccl_exe=exe,
        candidates=cands,
        next_steps=next_steps,
    )
    write_json(root / REPORT_JSON, asdict(report))
    write_text(root / REPORT_MD, markdown(report))
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe a local SC-CL-master folder for RDR readiness.")
    parser.add_argument("--root", default=None)
    parser.add_argument("--source", default=None, help="Explicit SC-CL source folder")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    root = root_from_arg(args.root)
    report = run_probe(root, args.source)
    print(markdown(report))
    return 0 if report.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
