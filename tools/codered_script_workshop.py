#!/usr/bin/env python3
"""Code RED Script Workshop.

Compiler-aware, read-first workshop for RDR script/source lanes.

Default behavior is safe planning only:
- inventories script binaries and source files
- detects likely SC-CL / Magic-RDR / Code RED compiler resources
- creates a compile plan and reports
- does not compile unless --compile and --compiler-template are provided

Example dry run:
    python tools/codered_script_workshop.py --source scripts --out logs/script_workshop

Example explicit compile template:
    python tools/codered_script_workshop.py --source scripts --out build/scripts --compile \
      --compiler-template '"{compiler}" "{source}" -o "{output}"'
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_EXTS = {".c", ".h", ".hpp", ".cpp", ".cc", ".cxx", ".cs", ".lua", ".scp", ".sc", ".wscsrc", ".txt"}
SCRIPT_EXTS = {".sco", ".wsc", ".xsc", ".wsv"}
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "build", "dist", "logs", "node_modules", ".vs", ".vscode"}


@dataclass
class ScriptItem:
    path: str
    kind: str
    extension: str
    size: int
    sha1_prefix: str
    role: str
    notes: list[str]


@dataclass
class CompilePlanItem:
    source: str
    output: str
    compiler: str
    command: list[str]
    status: str
    notes: list[str]


def sha1_prefix(path: Path, limit: int = 16 * 1024 * 1024) -> str:
    h = hashlib.sha1()
    with path.open("rb") as fh:
        left = limit
        while left > 0:
            chunk = fh.read(min(1024 * 1024, left))
            if not chunk:
                break
            h.update(chunk)
            left -= len(chunk)
    return h.hexdigest()[:16]


def should_skip(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


def iter_files(roots: Iterable[Path]) -> Iterable[Path]:
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            if not should_skip(root):
                yield root
            continue
        for path in root.rglob("*"):
            if path.is_file() and not should_skip(path):
                yield path


def classify(path: Path) -> tuple[str, str, list[str]]:
    ext = path.suffix.lower()
    notes: list[str] = []
    if ext in SCRIPT_EXTS:
        role = "compiled_or_binary_script"
        if ext == ".wsv":
            notes.append("WSV script-adjacent resource; keep in Script Workshop lane")
        else:
            notes.append("compiled/script resource; do not mutate directly")
        return "script", role, notes
    if ext in SOURCE_EXTS:
        role = "candidate_source"
        if ext in {".txt", ".lua"}:
            notes.append("text source candidate; verify format before compile")
        else:
            notes.append("source candidate")
        return "source", role, notes
    return "other", "supporting_file", notes


def inventory(roots: list[Path]) -> list[ScriptItem]:
    items: list[ScriptItem] = []
    for path in iter_files(roots):
        ext = path.suffix.lower()
        kind, role, notes = classify(path)
        if kind == "other":
            continue
        try:
            size = path.stat().st_size
            digest = sha1_prefix(path)
        except OSError as exc:
            size = 0
            digest = ""
            notes.append(f"read/stat failed: {exc}")
        items.append(ScriptItem(str(path), kind, ext, size, digest, role, notes))
    return sorted(items, key=lambda item: (item.kind, item.extension, item.path.lower()))


def detect_tooling(repo_root: Path = REPO_ROOT) -> dict:
    env_candidates = [
        os.environ.get("CODERED_SCRIPT_COMPILER"),
        os.environ.get("CODERED_SC_CL"),
        os.environ.get("SC_CL"),
        os.environ.get("SCCL"),
    ]
    path_candidates = [shutil.which(name) for name in ("sc-cl", "sccl", "sccl.exe", "scc", "scc.exe")]
    resource_candidates = []
    for base in [repo_root / "resources", repo_root / "tools", repo_root / "related_apps", repo_root]:
        if not base.exists():
            continue
        for pattern in ("**/sc-cl*.exe", "**/sccl*.exe", "**/scc*.exe", "**/SC-CL*", "**/Magic-RDR*.exe"):
            resource_candidates.extend(str(p) for p in base.glob(pattern) if p.exists())
    candidates = [str(Path(c)) for c in env_candidates + path_candidates if c]
    candidates.extend(resource_candidates)
    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    primary = deduped[0] if deduped else ""
    return {
        "compiler_candidates": deduped,
        "primary_compiler": primary,
        "magic_rdr_candidates": [c for c in deduped if "magic" in c.lower() and "rdr" in c.lower()],
        "sc_cl_candidates": [c for c in deduped if "sc-cl" in c.lower() or "sccl" in c.lower() or Path(c).name.lower().startswith("scc")],
        "compile_available": bool(primary),
    }


def default_output_for(source: Path, out_root: Path) -> Path:
    stem = source.stem
    if source.suffix.lower() == ".wscsrc":
        stem = source.with_suffix("").stem
    return out_root / f"{stem}.sco"


def render_command(template: str, compiler: str, source: Path, output: Path) -> list[str]:
    rendered = template.format(compiler=compiler, source=str(source), output=str(output))
    if os.name == "nt":
        return shlex.split(rendered, posix=False)
    return shlex.split(rendered)


def build_compile_plan(items: list[ScriptItem], out_root: Path, compiler: str, template: str | None) -> list[CompilePlanItem]:
    plan: list[CompilePlanItem] = []
    for item in items:
        if item.kind != "source":
            continue
        source = Path(item.path)
        output = default_output_for(source, out_root)
        notes: list[str] = []
        if not compiler:
            status = "blocked_no_compiler_detected"
            command: list[str] = []
            notes.append("Set CODERED_SCRIPT_COMPILER or pass --compiler")
        elif not template:
            status = "planned_template_required"
            command = []
            notes.append("Pass --compiler-template to execute compile safely")
        else:
            status = "ready"
            command = render_command(template, compiler, source, output)
        plan.append(CompilePlanItem(str(source), str(output), compiler, command, status, notes))
    return plan


def run_compile_plan(plan: list[CompilePlanItem], timeout: int = 60) -> list[dict]:
    results: list[dict] = []
    for item in plan:
        row = asdict(item)
        if item.status != "ready" or not item.command:
            row.update({"returncode": None, "stdout": "", "stderr": "", "ran": False})
            results.append(row)
            continue
        output = Path(item.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            result = subprocess.run(item.command, capture_output=True, text=True, timeout=timeout, check=False)
            row.update({
                "returncode": result.returncode,
                "stdout": "\n".join(result.stdout.splitlines()[:80]),
                "stderr": "\n".join(result.stderr.splitlines()[:80]),
                "ran": True,
                "ok": result.returncode == 0 and output.exists(),
            })
        except Exception as exc:
            row.update({"returncode": None, "stdout": "", "stderr": str(exc), "ran": False, "ok": False})
        results.append(row)
    return results


def write_outputs(out_root: Path, items: list[ScriptItem], tooling: dict, plan: list[CompilePlanItem], results: list[dict] | None) -> dict:
    out_root.mkdir(parents=True, exist_ok=True)
    summary = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "repo_root": str(REPO_ROOT),
        "item_count": len(items),
        "source_count": sum(1 for item in items if item.kind == "source"),
        "script_resource_count": sum(1 for item in items if item.kind == "script"),
        "extensions": dict(sorted({ext: sum(1 for item in items if item.extension == ext) for ext in {item.extension for item in items}}.items())),
        "tooling": tooling,
        "compile_plan_count": len(plan),
        "compile_results_count": len(results or []),
    }
    (out_root / "script_workshop_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_root / "script_workshop_plan.json").write_text(json.dumps([asdict(item) for item in plan], indent=2), encoding="utf-8")
    if results is not None:
        (out_root / "script_workshop_compile_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

    with (out_root / "script_workshop_inventory.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["path", "kind", "extension", "size", "sha1_prefix", "role", "notes"])
        writer.writeheader()
        for item in items:
            row = asdict(item)
            row["notes"] = "; ".join(item.notes)
            writer.writerow(row)

    lines = [
        "# Code RED Script Workshop",
        "",
        f"Generated: {summary['generated_at']}",
        f"Items: {summary['item_count']}",
        f"Sources: {summary['source_count']}",
        f"Script resources: {summary['script_resource_count']}",
        "",
        "## Tooling",
        f"- Primary compiler: `{tooling.get('primary_compiler') or 'not detected'}`",
        f"- Compile available: {tooling.get('compile_available')}",
        f"- SC-CL candidates: {len(tooling.get('sc_cl_candidates', []))}",
        f"- Magic-RDR candidates: {len(tooling.get('magic_rdr_candidates', []))}",
        "",
        "## Extension counts",
    ]
    for ext, count in summary["extensions"].items():
        lines.append(f"- `{ext}`: {count}")
    lines.extend(["", "## Compile plan"])
    for item in plan[:200]:
        lines.append(f"- `{Path(item.source).name}` -> `{item.output}` [{item.status}]")
    if results is not None:
        lines.extend(["", "## Compile results"])
        for row in results[:200]:
            lines.append(f"- `{Path(row['source']).name}` ran={row.get('ran')} rc={row.get('returncode')} ok={row.get('ok')}")
    (out_root / "script_workshop_report.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Code RED Script Workshop")
    parser.add_argument("--source", action="append", type=Path, default=[], help="Source/script folder or file. Can be used multiple times.")
    parser.add_argument("--out", type=Path, default=Path("logs/script_workshop"), help="Output report/build folder.")
    parser.add_argument("--compiler", default="", help="Explicit compiler path. Overrides detected primary compiler.")
    parser.add_argument("--compiler-template", default="", help="Explicit command template using {compiler}, {source}, and {output}.")
    parser.add_argument("--compile", action="store_true", help="Run compile commands. Requires --compiler-template.")
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args(argv)

    roots = args.source or [REPO_ROOT / "scripts", REPO_ROOT / "resources", REPO_ROOT / "data"]
    items = inventory(roots)
    tooling = detect_tooling(REPO_ROOT)
    compiler = args.compiler or str(tooling.get("primary_compiler") or "")
    template = args.compiler_template or ""
    plan = build_compile_plan(items, args.out / "compiled", compiler, template)
    results = None
    if args.compile:
        if not template:
            print("--compile requires --compiler-template so Code RED does not guess compiler syntax", file=sys.stderr)
            return 2
        results = run_compile_plan(plan, timeout=args.timeout)
    summary = write_outputs(args.out, items, tooling, plan, results)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
