#!/usr/bin/env python3
"""Code RED full-backend RPF6 harness.

This is the next step after raw RPF probing. It calls the protected
`python_workbench.py` backend instead of reimplementing the weaker stable-shell
scanner.

Goals:
- run full backend RPF6 audit/export paths on real archives
- locate init/SCO/WSV/script entries in the backend audit result
- collect extracted script candidates if the backend can export them
- separate non-z init scripts from zombie/z-prefixed scripts
- optionally hand extracted script files to the Script Decompile Attempt workflow

This tool is read-first. It does not mutate the source RPF.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
FULL_BACKEND_PATH = REPO_ROOT / "python_workbench.py"
DECOMPILE_ATTEMPT = REPO_ROOT / "tools" / "codered_script_decompile_attempt.py"
SCRIPT_EXTS = {".sco", ".wsc", ".xsc", ".wsv"}
WATCH_WORDS = ("init", "startup", "main", "script", "sco", "wsc", "xsc", "wsv", "mp_", "freemode", "network", "graveyard", "zombie")
DEFAULT_EXCLUDE_PREFIXES = ("z",)


@dataclass
class BackendEntryHit:
    source_field: str
    value: str
    extension: str
    category: str
    raw_preview: str
    init_named: bool
    z_prefixed: bool
    selected: bool
    reject_reason: str


def load_backend() -> Any:
    if not FULL_BACKEND_PATH.exists():
        raise FileNotFoundError(f"Missing full backend: {FULL_BACKEND_PATH}")
    spec = importlib.util.spec_from_file_location("python_workbench", FULL_BACKEND_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import {FULL_BACKEND_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def flatten_values(obj: Any, prefix: str = "root", limit: int = 200000) -> Iterable[tuple[str, Any]]:
    stack: list[tuple[str, Any]] = [(prefix, obj)]
    seen = 0
    while stack and seen < limit:
        field, value = stack.pop()
        seen += 1
        yield field, value
        if isinstance(value, dict):
            for key, sub in value.items():
                stack.append((f"{field}.{key}", sub))
        elif isinstance(value, (list, tuple)):
            for idx, sub in enumerate(value):
                stack.append((f"{field}[{idx}]", sub))


def basename_token(value: str) -> str:
    token = str(value).replace("\\", "/").split("/")[-1]
    token = token.split("::")[-1]
    return Path(token).name.lower()


def is_init_named(value: str) -> bool:
    return "init" in basename_token(value)


def is_prefixed(value: str, prefixes: tuple[str, ...]) -> bool:
    name = basename_token(value)
    stem = Path(name).stem.lower()
    return any(stem.startswith(prefix.lower()) for prefix in prefixes if prefix)


def categorize(value: str) -> tuple[str, str]:
    low = value.lower()
    ext = Path(low).suffix
    if ext in SCRIPT_EXTS:
        if "init" in basename_token(value):
            return ext, "init_script_entry"
        return ext, "script_entry"
    if "init" in low:
        return ext, "init_signal"
    if any(word in low for word in ("mp_", "freemode", "network", "graveyard", "zombie")):
        return ext, "mp_signal"
    if any(word in low for word in ("sco", "wsc", "xsc", "wsv", "script")):
        return ext, "script_signal"
    return ext, "other"


def selection_status(value: str, category: str, *, init_only: bool, exclude_prefixes: tuple[str, ...]) -> tuple[bool, str]:
    init_named = is_init_named(value)
    z_prefixed = is_prefixed(value, exclude_prefixes)
    if init_only and not init_named:
        return False, "not_init_named"
    if z_prefixed:
        return False, "excluded_prefix"
    if category not in {"init_script_entry", "script_entry", "init_signal"}:
        return False, "not_script_or_init_category"
    return True, ""


def find_backend_hits(audit: Any, *, init_only: bool, exclude_prefixes: tuple[str, ...]) -> list[BackendEntryHit]:
    hits: list[BackendEntryHit] = []
    seen: set[tuple[str, str]] = set()
    for field, value in flatten_values(audit):
        if not isinstance(value, (str, int, float)):
            continue
        text = str(value)
        low = text.lower()
        if not any(word in low for word in WATCH_WORDS) and Path(low).suffix not in SCRIPT_EXTS:
            continue
        ext, category = categorize(text)
        selected, reject_reason = selection_status(text, category, init_only=init_only, exclude_prefixes=exclude_prefixes)
        key = (field, text.lower())
        if key in seen:
            continue
        seen.add(key)
        hits.append(
            BackendEntryHit(
                field,
                text,
                ext,
                category,
                repr(value)[:240],
                is_init_named(text),
                is_prefixed(text, exclude_prefixes),
                selected,
                reject_reason,
            )
        )
    return sorted(hits, key=lambda h: (not h.selected, h.reject_reason, h.category, h.extension, h.value.lower()))


def find_extracted_scripts(root: Path, *, init_only: bool, exclude_prefixes: tuple[str, ...]) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    scripts = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SCRIPT_EXTS:
            continue
        init_named = "init" in path.name.lower()
        excluded_prefix = is_prefixed(path.name, exclude_prefixes)
        selected = True
        reject_reason = ""
        if init_only and not init_named:
            selected = False
            reject_reason = "not_init_named"
        elif excluded_prefix:
            selected = False
            reject_reason = "excluded_prefix"
        scripts.append(
            {
                "path": str(path),
                "extension": path.suffix.lower(),
                "size": path.stat().st_size,
                "init_named": init_named,
                "excluded_prefix": excluded_prefix,
                "selected": selected,
                "reject_reason": reject_reason,
            }
        )
    return sorted(scripts, key=lambda r: (not r["selected"], not r["init_named"], r["extension"], r["path"].lower()))


def call_backend_audit(backend: Any, archive: Path, extract_root: Path, do_extract: bool) -> dict[str, Any]:
    if not hasattr(backend, "audit_rpf6_archive"):
        raise AttributeError("python_workbench.py does not expose audit_rpf6_archive")
    audit_fn = backend.audit_rpf6_archive
    attempts: list[dict[str, Any]] = []
    call_variants = [
        {"include_hashes": False, "include_extract": do_extract, "extract_root": extract_root},
        {"include_hashes": False, "include_extract": do_extract},
        {"include_hashes": False},
        {},
    ]
    for kwargs in call_variants:
        try:
            result = audit_fn(archive, **kwargs)
            return {"ok": True, "kwargs": {k: str(v) for k, v in kwargs.items()}, "result": result, "attempts": attempts}
        except TypeError as exc:
            attempts.append({"kwargs": {k: str(v) for k, v in kwargs.items()}, "error": f"TypeError: {exc}"})
        except Exception as exc:
            attempts.append({"kwargs": {k: str(v) for k, v in kwargs.items()}, "error": f"{type(exc).__name__}: {exc}"})
            break
    return {"ok": False, "kwargs": {}, "result": None, "attempts": attempts}


def run_decompile_attempt(scripts_root: Path, out_dir: Path) -> dict[str, Any]:
    if not DECOMPILE_ATTEMPT.exists() or not scripts_root.exists():
        return {"ran": False, "reason": "decompile attempt tool or script root missing"}
    cmd = [sys.executable, str(DECOMPILE_ATTEMPT), "--source", str(scripts_root), "--out", str(out_dir)]
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), text=True, capture_output=True, check=False)
    return {
        "ran": True,
        "returncode": proc.returncode,
        "stdout": "\n".join(proc.stdout.splitlines()[:80]),
        "stderr": "\n".join(proc.stderr.splitlines()[:80]),
    }


def write_report(
    out_dir: Path,
    archive: Path,
    backend_result: dict[str, Any],
    hits: list[BackendEntryHit],
    extracted_scripts: list[dict[str, Any]],
    decompile_attempt: dict[str, Any],
    *,
    init_only: bool,
    exclude_prefixes: tuple[str, ...],
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    categories: dict[str, int] = {}
    selected_categories: dict[str, int] = {}
    for hit in hits:
        categories[hit.category] = categories.get(hit.category, 0) + 1
        if hit.selected:
            selected_categories[hit.category] = selected_categories.get(hit.category, 0) + 1
    selected_hits = [hit for hit in hits if hit.selected]
    selected_scripts = [script for script in extracted_scripts if script.get("selected")]
    init_scripts = [script for script in extracted_scripts if script.get("init_named")]
    non_z_init_scripts = [script for script in extracted_scripts if script.get("init_named") and not script.get("excluded_prefix")]
    summary = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "archive": str(archive),
        "backend_ok": backend_result.get("ok"),
        "backend_kwargs": backend_result.get("kwargs"),
        "backend_attempts": backend_result.get("attempts"),
        "filters": {"init_only": init_only, "exclude_prefixes": list(exclude_prefixes)},
        "hit_count": len(hits),
        "selected_hit_count": len(selected_hits),
        "category_counts": categories,
        "selected_category_counts": selected_categories,
        "extracted_script_count": len(extracted_scripts),
        "selected_extracted_script_count": len(selected_scripts),
        "init_extracted_script_count": len(init_scripts),
        "non_z_init_extracted_script_count": len(non_z_init_scripts),
        "decrypt_extract_status": "confirmed_non_z_init_scripts_extracted" if non_z_init_scripts else "not_confirmed_non_z_init_scripts_extracted",
        "decompile_attempt": decompile_attempt,
    }
    (out_dir / "full_backend_rpf6_harness_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    (out_dir / "full_backend_rpf6_harness_audit.json").write_text(json.dumps(backend_result.get("result"), indent=2, default=str), encoding="utf-8")
    (out_dir / "full_backend_rpf6_harness_hits.json").write_text(json.dumps([asdict(h) for h in hits], indent=2), encoding="utf-8")
    (out_dir / "full_backend_rpf6_harness_selected_hits.json").write_text(json.dumps([asdict(h) for h in selected_hits], indent=2), encoding="utf-8")
    (out_dir / "full_backend_rpf6_harness_extracted_scripts.json").write_text(json.dumps(extracted_scripts, indent=2), encoding="utf-8")
    (out_dir / "full_backend_rpf6_harness_selected_scripts.json").write_text(json.dumps(selected_scripts, indent=2), encoding="utf-8")
    lines = [
        "# Code RED Full Backend RPF6 Harness",
        "",
        f"Archive: `{archive}`",
        f"Backend audit OK: {summary['backend_ok']}",
        f"Backend kwargs: `{summary['backend_kwargs']}`",
        f"Filters: init_only={init_only}, exclude_prefixes={list(exclude_prefixes)}",
        f"Backend entry/signal hits: {summary['hit_count']}",
        f"Selected hits: {summary['selected_hit_count']}",
        f"Extracted scripts: {summary['extracted_script_count']}",
        f"Selected extracted scripts: {summary['selected_extracted_script_count']}",
        f"Init-named extracted scripts: {summary['init_extracted_script_count']}",
        f"Non-z init extracted scripts: {summary['non_z_init_extracted_script_count']}",
        f"Decrypt/extract status: `{summary['decrypt_extract_status']}`",
        "",
        "## Hit categories",
    ]
    for category, count in sorted(categories.items()):
        lines.append(f"- {category}: {count}")
    lines.extend(["", "## Selected init/script highlights"])
    for hit in selected_hits[:200]:
        lines.append(f"- [{hit.category}] `{hit.value}` via `{hit.source_field}`")
    if not selected_hits:
        lines.append("- No selected non-excluded init/script backend hits yet.")
    lines.extend(["", "## Selected extracted scripts"])
    for script in selected_scripts[:200]:
        lines.append(f"- `{script['path']}` size={script['size']} ext={script['extension']}")
    if not selected_scripts:
        lines.append("- No selected extracted scripts yet.")
    lines.extend(["", "## Decompile attempt"])
    lines.append(json.dumps(decompile_attempt, indent=2, default=str))
    (out_dir / "full_backend_rpf6_harness_report.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def parse_prefixes(values: list[str], default: tuple[str, ...]) -> tuple[str, ...]:
    prefixes: list[str] = []
    for value in values:
        for part in value.split(","):
            part = part.strip().lower()
            if part:
                prefixes.append(part)
    return tuple(prefixes) if prefixes else default


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Code RED full backend RPF6 audit/export harness")
    parser.add_argument("archive", type=Path, help="RPF archive to inspect")
    parser.add_argument("--out", type=Path, default=Path("logs/full_backend_rpf6_harness"))
    parser.add_argument("--extract", action="store_true", help="Ask the backend to export/extract if supported")
    parser.add_argument("--decompile-attempt", action="store_true", help="Run decompile-attempt inventory on extracted scripts")
    parser.add_argument("--init-only", action="store_true", help="Select only init-named backend hits and extracted scripts")
    parser.add_argument("--exclude-prefix", action="append", default=[], help="Exclude basename/stem prefixes. Can be repeated or comma-separated. Default: z")
    parser.add_argument("--include-z", action="store_true", help="Do not exclude z-prefixed scripts")
    args = parser.parse_args(argv)

    exclude_prefixes = () if args.include_z else parse_prefixes(args.exclude_prefix, DEFAULT_EXCLUDE_PREFIXES)
    backend = load_backend()
    extract_root = args.out / "extracted"
    backend_result = call_backend_audit(backend, args.archive, extract_root, args.extract)
    hits = find_backend_hits(backend_result.get("result"), init_only=args.init_only, exclude_prefixes=exclude_prefixes) if backend_result.get("ok") else []
    extracted_scripts = find_extracted_scripts(extract_root, init_only=args.init_only, exclude_prefixes=exclude_prefixes)
    decompile_attempt = run_decompile_attempt(extract_root, args.out / "decompile_attempt") if args.decompile_attempt else {"ran": False, "reason": "not requested"}
    summary = write_report(
        args.out,
        args.archive,
        backend_result,
        hits,
        extracted_scripts,
        decompile_attempt,
        init_only=args.init_only,
        exclude_prefixes=exclude_prefixes,
    )
    print(json.dumps(summary, indent=2, default=str))
    return 0 if backend_result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
