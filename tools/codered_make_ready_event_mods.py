from __future__ import annotations
import hashlib, json, os, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
READY = ROOT / "ready_modded_files"
LOGS = ROOT / "logs" / "ready_event_mods"

TASKS = [
    {
        "name": "WagonThief truck/car",
        "input": "beat_crime_wagonthief.wsc",
        "output": "beat_crime_wagonthief.wsc",
        "script": "codered_wagonthief_cartruck_wsc.py",
        "args": [
            "patch", "--mode", "binary-range", "--int-format", "u16be",
            "--old-low", "1183", "--old-high", "1197",
            "--new-low", "1193", "--new-high", "1194",
        ],
        "note": "Known-good WagonThief lane: 1183..1197 -> alternating Truck01/Car01.",
    },
    {
        "name": "Roadside Ambush truck/car",
        "input": "event_roadside_ambush.wsc",
        "output": "event_roadside_ambush.wsc",
        "script": "codered_ambush_cartruck_wsc.py",
        "args": [
            "patch", "--mode", "binary-range", "--int-format", "u16be",
            "--old-low", "1177", "--old-high", "1188",
            "--new-low", "1193", "--new-high", "1194",
        ],
        "note": "Confirmed one-vehicle ambush lane: 1177..1188 -> alternating Truck01/Car01.",
    },
    {
        "name": "Roadside Prisoners truck-only",
        "input": "event_roadside_prisoners.wsc",
        "output": "event_roadside_prisoners.wsc",
        "script": "codered_roadside_robbery_cartruck_wsc.py",
        "args": [
            "patch", "--mode", "direct-ids", "--int-format", "u16be",
            "--old-ids", "1197", "--target-id", "1193",
            "--max-replacements", "8", "--allow-grow",
        ],
        "note": "Transport lane: 1197 WagonPrison01 -> 1193 Truck01 only.",
    },
]

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()

def find_input(filename: str) -> Path | None:
    preferred = [ROOT / "imports" / filename, ROOT / filename]
    for p in preferred:
        if p.exists():
            return p
    # Last-resort search, avoiding generated output folders.
    skip_parts = {"ready_modded_files", "ready_to_test", "ready_to_test_current", "logs"}
    for p in ROOT.rglob(filename):
        if any(part in skip_parts for part in p.parts):
            continue
        if p.is_file():
            return p
    return None

def run_task(task: dict, rdr_exe: str | None) -> dict:
    inp = find_input(task["input"])
    if not inp:
        return {"task": task["name"], "status": "missing-input", "input": task["input"]}
    out = READY / task["output"]
    out.parent.mkdir(parents=True, exist_ok=True)
    script = TOOLS / task["script"]
    cmd = [sys.executable, str(script), *task["args"], "--input", str(inp), "--out", str(out)]
    if rdr_exe:
        cmd += ["--rdr-exe", rdr_exe]
    proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
    result = {
        "task": task["name"],
        "status": "ok" if proc.returncode == 0 and out.exists() else "failed",
        "input": str(inp),
        "output": str(out),
        "note": task.get("note", ""),
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }
    if out.exists():
        result.update({"output_size": out.stat().st_size, "output_sha256": sha256(out)})
    return result

def main() -> int:
    READY.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    rdr_exe = os.environ.get("CODERED_RDR_EXE")
    if rdr_exe and not Path(rdr_exe).exists():
        print(f"WARNING: CODERED_RDR_EXE does not exist: {rdr_exe}")
    print(f"Code RED ready event mod builder")
    print(f"Root: {ROOT}")
    print(f"Ready output: {READY}")
    print(f"CODERED_RDR_EXE: {rdr_exe or '(not set)'}")
    results = []
    for task in TASKS:
        print(f"\n=== {task['name']} ===")
        r = run_task(task, rdr_exe)
        results.append(r)
        print(json.dumps({k: v for k, v in r.items() if k not in ('stdout_tail','stderr_tail')}, indent=2))
        if r.get("status") != "ok":
            print("STDOUT tail:")
            print(r.get("stdout_tail", ""))
            print("STDERR tail:")
            print(r.get("stderr_tail", ""))
    manifest = {
        "status": "complete" if all(r.get("status") == "ok" for r in results) else "incomplete",
        "root": str(ROOT),
        "ready_output": str(READY),
        "rdr_exe": rdr_exe,
        "files": results,
    }
    (LOGS / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    lines = ["Code RED Ready Event Mods", "", f"Status: {manifest['status']}", f"Output: {READY}", ""]
    for r in results:
        lines += [
            f"- {r['task']}: {r['status']}",
            f"  input: {r.get('input')}",
            f"  output: {r.get('output')}",
            f"  sha256: {r.get('output_sha256', '')}",
            f"  note: {r.get('note', '')}",
            "",
        ]
    (LOGS / "manifest.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"\nManifest written: {LOGS / 'manifest.txt'}")
    return 0 if manifest["status"] == "complete" else 1

if __name__ == "__main__":
    raise SystemExit(main())
