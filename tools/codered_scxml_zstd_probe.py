#!/usr/bin/env python3
"""Probe/export Zstandard-compressed SC XML UI targets.

The decoder probe showed many packed UI targets begin with bytes:

    28 b5 2f fd

That is the Zstandard frame magic. This helper tries to decode those targets
safely and exports only outputs that are text/XML-like enough to inspect.

It is read-only against the source files and does not patch archives.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "logs" / "content_mp_ui_gate_target_pack" / "targets"
DEFAULT_DECODER = ROOT / "logs" / "content_mp_scxml_decoder_probe" / "scxml_decoder_probe_files.json"
DEFAULT_OUT = ROOT / "logs" / "content_mp_scxml_zstd_probe"
ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"
XML_HINT_RE = re.compile(rb"<\s*(?:\?xml|root|screen|scene|menu|data|movie|object|item|entry|page|component|state|button|text|image|panel|list)\b", re.I)
MENU_HINTS = (b"menu", b"frontend", b"pause", b"lobby", b"network", b"system", b"link", b"xlive", b"profile", b"signin", b"multiplayer", b"freemode", b"button", b"playmp", b"offline", b"lan")
TEXT_EXTS = {".xml", ".txt", ".csv", ".strtbl", ".dat"}
SCRIPT_EXTS = {".csc", ".sco", ".wsc", ".xsc", ".wsv"}


@dataclass
class ZstdResult:
    path: str
    extension: str
    size: int
    header_hex: str
    has_zstd_magic: bool
    zstd_offset: int | None
    method: str
    ok: bool
    decoded_size: int
    text_ratio: float
    xml_like: bool
    menu_hint_count: int
    output_path: str
    error: str
    recommendation: str
    preview: str


def iter_files(source: Path) -> Iterable[Path]:
    if source.is_file():
        return [source]
    return sorted((p for p in source.rglob("*") if p.is_file()), key=lambda p: str(p).lower())


def clean_preview(data: bytes, limit: int = 500) -> str:
    text = data[:limit].decode("utf-8", "replace").replace("\x00", " ")
    return re.sub(r"\s+", " ", text).strip()[:limit]


def text_ratio(data: bytes) -> float:
    if not data:
        return 0.0
    sample = data[:16384]
    return round(sum(1 for b in sample if b in (9, 10, 13) or 32 <= b < 127) / len(sample), 4)


def xml_like(data: bytes) -> bool:
    sample = data[:65536]
    return bool(XML_HINT_RE.search(sample)) or (b"<" in sample and b">" in sample and (b"</" in sample or b"/>" in sample))


def menu_hint_count(data: bytes) -> int:
    low = data[:262144].lower()
    return sum(low.count(hint) for hint in MENU_HINTS)


def safe_name(path: Path) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", path.name)[:180]


def try_python_zstd(payload: bytes) -> tuple[bytes | None, str]:
    try:
        import zstandard as zstd  # type: ignore
    except Exception as exc:
        return None, f"python zstandard unavailable: {exc}"
    try:
        dctx = zstd.ZstdDecompressor()
        return dctx.decompress(payload), ""
    except Exception as exc:
        return None, str(exc)


def try_cli_zstd(payload: bytes, out_dir: Path, stem: str) -> tuple[bytes | None, str]:
    exe = shutil.which("zstd") or shutil.which("zstd.exe")
    if not exe:
        return None, "zstd executable not found on PATH"
    in_path = out_dir / f"{stem}.zst"
    out_path = out_dir / f"{stem}.cli.tmp"
    in_path.write_bytes(payload)
    try:
        proc = subprocess.run([exe, "-d", "-f", "-q", str(in_path), "-o", str(out_path)], capture_output=True, text=True, check=False, timeout=60)
        if proc.returncode != 0:
            return None, proc.stderr.strip() or proc.stdout.strip() or f"zstd returned {proc.returncode}"
        return out_path.read_bytes(), ""
    except Exception as exc:
        return None, str(exc)


def decode_zstd(data: bytes, out_dir: Path, stem: str, prefer_cli: bool = False) -> tuple[bytes | None, str, str]:
    off = data.find(ZSTD_MAGIC)
    if off < 0:
        return None, "none", "zstd magic not found"
    payload = data[off:]
    methods = ["cli", "python"] if prefer_cli else ["python", "cli"]
    errors = []
    for method in methods:
        if method == "python":
            decoded, err = try_python_zstd(payload)
        else:
            decoded, err = try_cli_zstd(payload, out_dir, stem)
        if decoded is not None:
            return decoded, method, ""
        errors.append(f"{method}: {err}")
    return None, "+".join(methods), "; ".join(errors)


def load_decoder_rows(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out = {}
    if isinstance(rows, list):
        for row in rows:
            p = str(row.get("path") or "")
            if p:
                out[Path(p).name.lower()] = row
    return out


def probe_file(path: Path, out_dir: Path, decoder_rows: dict[str, dict], prefer_cli: bool) -> ZstdResult:
    data = path.read_bytes()
    off = data.find(ZSTD_MAGIC)
    header = data[:32].hex(" ")
    output_path = ""
    method = "none"
    err = ""
    ok = False
    decoded = b""
    if off >= 0 and path.suffix.lower() not in SCRIPT_EXTS:
        decoded_bytes, method, err = decode_zstd(data, out_dir, safe_name(path), prefer_cli)
        if decoded_bytes is not None:
            decoded = decoded_bytes
            ok = True
            suffix = ".xml" if xml_like(decoded) or text_ratio(decoded) > 0.75 else ".bin"
            target = out_dir / "decoded" / f"{safe_name(path)}.decoded{suffix}"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(decoded)
            output_path = str(target)
    elif path.suffix.lower() in SCRIPT_EXTS:
        err = "script binary skipped"
    else:
        err = "zstd magic not found"
    tr = text_ratio(decoded) if decoded else 0.0
    xl = xml_like(decoded) if decoded else False
    hints = menu_hint_count(decoded) if decoded else 0
    if path.suffix.lower() in SCRIPT_EXTS:
        rec = "script binary; keep in Script Workshop/decompiler lane"
    elif ok and xl:
        rec = "decoded XML-like UI resource; inspect route/button/menu IDs before patch planning"
    elif ok and tr > 0.70:
        rec = "decoded text-like UI resource; inspect manually before patch planning"
    elif off >= 0:
        rec = "Zstandard frame found but decoded output was not XML/text-like; inspect binary output or resource wrapper"
    else:
        rec = "no Zstandard frame found; compare with MagicRDR/resource-viewer output"
    return ZstdResult(
        path=str(path),
        extension=path.suffix.lower(),
        size=len(data),
        header_hex=header,
        has_zstd_magic=off >= 0,
        zstd_offset=off if off >= 0 else None,
        method=method,
        ok=ok,
        decoded_size=len(decoded),
        text_ratio=tr,
        xml_like=xl,
        menu_hint_count=hints,
        output_path=output_path,
        error=err,
        recommendation=rec,
        preview=clean_preview(decoded) if decoded else "",
    )


def write_outputs(out_dir: Path, source: Path, results: list[ZstdResult]) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    counts = Counter("script" if r.extension in SCRIPT_EXTS else "zstd" if r.has_zstd_magic else "no_zstd" for r in results)
    decoded_xml = [r for r in results if r.ok and r.xml_like]
    decoded_text = [r for r in results if r.ok and not r.xml_like and r.text_ratio > 0.70]
    failed_zstd = [r for r in results if r.has_zstd_magic and not r.ok]
    summary = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": str(source),
        "file_count": len(results),
        "counts": dict(counts),
        "decoded_xml_like_count": len(decoded_xml),
        "decoded_text_like_count": len(decoded_text),
        "failed_zstd_count": len(failed_zstd),
        "status": "zstd_decoded_xml_available" if decoded_xml else "zstd_decoder_needed_or_not_xml",
        "decoded_outputs": [r.output_path for r in decoded_xml + decoded_text if r.output_path],
        "top_decoded_xml": [asdict(r) for r in decoded_xml[:20]],
        "next_actions": [
            "Open decoded XML outputs and inspect menu route/button ids for MP/network/lobby visibility gates.",
            "Prioritize decoded networking, lobby/main, generalmenus, net_profile, lanmenu, plaympconf, and offlinemenu if available.",
            "If high-priority files do not decode through Zstandard, compare with MagicRDR/resource-viewer export.",
            "Only patch via copied archive/patch layer after decoded route IDs are confirmed.",
        ],
    }
    (out_dir / "scxml_zstd_probe_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "scxml_zstd_probe_files.json").write_text(json.dumps([asdict(r) for r in results], indent=2), encoding="utf-8")
    with (out_dir / "scxml_zstd_probe_files.csv").open("w", newline="", encoding="utf-8") as fh:
        fields = ["path", "extension", "size", "header_hex", "has_zstd_magic", "zstd_offset", "method", "ok", "decoded_size", "text_ratio", "xml_like", "menu_hint_count", "output_path", "error", "recommendation"]
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for r in results:
            row = asdict(r)
            row.pop("preview", None)
            writer.writerow(row)
    lines = [
        "# Code RED SC XML Zstandard Probe",
        "",
        f"Generated: {summary['generated_at']}",
        f"Source: `{source}`",
        f"Files: {len(results)}",
        f"Status: `{summary['status']}`",
        "",
        "## Counts",
    ]
    for name, count in sorted(counts.items()):
        lines.append(f"- {name}: {count}")
    lines.extend(["", "## Decoded XML-like outputs"])
    for r in decoded_xml[:30]:
        lines.append(f"- `{r.path}` -> `{r.output_path}` hints={r.menu_hint_count} method={r.method}")
    if not decoded_xml:
        lines.append("- No XML-like Zstandard decoded outputs found.")
    lines.extend(["", "## Priority non-decoded Zstandard targets"])
    priority = [r for r in results if r.has_zstd_magic and not r.ok]
    for r in priority[:30]:
        lines.append(f"- `{r.path}` :: {r.error}")
    lines.extend(["", "## Next actions"])
    for action in summary["next_actions"]:
        lines.append(f"- {action}")
    (out_dir / "scxml_zstd_probe_report.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Decode Zstandard SC XML UI targets when possible.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--decoder", type=Path, default=DEFAULT_DECODER)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--prefer-cli", action="store_true", help="Prefer zstd executable over Python zstandard module.")
    args = parser.parse_args(argv)
    if not args.source.exists():
        raise SystemExit(f"Source not found: {args.source}")
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    decoder_rows = load_decoder_rows(args.decoder)
    results = [probe_file(path, out, decoder_rows, args.prefer_cli) for path in iter_files(args.source)]
    summary = write_outputs(out, args.source, results)
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("decoded_xml_like_count", 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
