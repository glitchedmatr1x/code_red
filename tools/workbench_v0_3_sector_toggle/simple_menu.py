from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON = [sys.executable]
TOOL = ROOT / "codered_mod_workbench.py"
REPORTS = ROOT / "reports"
PATCHED = ROOT / "patched"


def qpath(text: str) -> str:
    text = text.strip().strip('"')
    return text


def run(args: list[str]) -> int:
    cmd = PYTHON + [str(TOOL)] + args
    print("\nRunning:")
    print(" ".join(shlex.quote(x) for x in cmd))
    print()
    try:
        return subprocess.call(cmd, cwd=str(ROOT))
    except KeyboardInterrupt:
        print("\nCanceled.")
        return 130


def open_folder(path: Path) -> None:
    if os.name == "nt" and path.exists():
        subprocess.Popen(["explorer", str(path)])


def wait() -> None:
    input("\nPress Enter to return to the menu...")


def ask_file() -> Path | None:
    raw = input("Drag/drop file here, or paste full path: ").strip()
    if not raw:
        return None
    path = Path(qpath(raw))
    if not path.exists():
        print(f"File not found: {path}")
        return None
    return path


def scan_file() -> None:
    f = ask_file()
    if not f:
        wait(); return
    REPORTS.mkdir(exist_ok=True)
    out = REPORTS / f"{f.stem}_scan"
    code = run(["scan", str(f), "--out", str(out)])
    print(f"\nExit code: {code}")
    print(f"Report folder: {out}")
    summary = out / "summary.md"
    if summary.exists():
        print("\n--- summary.md ---")
        print(summary.read_text(errors="replace")[:4000])
    open_folder(out)
    wait()


def info_file() -> None:
    f = ask_file()
    if not f:
        wait(); return
    code = run(["info", str(f)])
    print(f"\nExit code: {code}")
    wait()


def replace_text() -> None:
    f = ask_file()
    if not f:
        wait(); return
    find = input("Text to find: ")
    if not find:
        print("Nothing entered."); wait(); return
    repl = input("Replace with: ")
    PATCHED.mkdir(exist_ok=True)
    out = PATCHED / f"{f.stem}_patched{f.suffix}"
    code = run(["replace", str(f), "--find", find, "--replace", repl, "--out", str(out)])
    print(f"\nExit code: {code}")
    if out.exists():
        print(f"Patched copy: {out}")
        print("Drop this copy into Magic RDR/RPF import, not the original.")
        open_folder(PATCHED)
    wait()


def interactive() -> None:
    f = ask_file()
    if not f:
        wait(); return
    PATCHED.mkdir(exist_ok=True)
    code = run(["interactive", str(f), "--outdir", str(PATCHED)])
    print(f"\nExit code: {code}")
    open_folder(PATCHED)
    wait()


def find_int() -> None:
    f = ask_file()
    if not f:
        wait(); return
    value = input("Value to find, example 1166: ").strip()
    if not value:
        wait(); return
    width = input("Byte width [2]: ").strip() or "2"
    endian = input("Endian little/big [little]: ").strip() or "little"
    REPORTS.mkdir(exist_ok=True)
    out = REPORTS / f"{f.stem}_value_{value}.csv"
    code = run(["find-int", str(f), "--value", value, "--width", width, "--endian", endian, "--out", str(out)])
    print(f"\nExit code: {code}")
    if out.exists():
        print(f"Report: {out}")
        try:
            print("\n--- first rows ---")
            print("\n".join(out.read_text(errors="replace").splitlines()[:30]))
        except Exception:
            pass
        open_folder(REPORTS)
    wait()


def replace_int() -> None:
    f = ask_file()
    if not f:
        wait(); return
    old = input("Old value, example 1166: ").strip()
    new = input("New value, example 1193: ").strip()
    if not old or not new:
        wait(); return
    width = input("Byte width [2]: ").strip() or "2"
    endian = input("Endian little/big [little]: ").strip() or "little"
    target = input("Target offset like 0x35D4A, or ALL after reviewing scan report: ").strip()
    if not target:
        wait(); return
    PATCHED.mkdir(exist_ok=True)
    out = PATCHED / f"{f.stem}_int_{old}_to_{new}{f.suffix}"
    args = ["replace-int", str(f), "--old", old, "--new", new, "--width", width, "--endian", endian, "--out", str(out)]
    if target.upper() == "ALL":
        args.insert(-2, "--all")
    else:
        args.insert(-2, "--offset")
        args.insert(-2, target)
    code = run(args)
    print(f"\nExit code: {code}")
    if out.exists():
        print(f"Patched copy: {out}")
        open_folder(PATCHED)
    wait()



def sector_scan() -> None:
    f = ask_file()
    if not f:
        wait(); return
    REPORTS.mkdir(exist_ok=True)
    out = REPORTS / f"{f.stem}_sector_scan"
    code = run(["sector-scan", str(f), "--out", str(out)])
    print(f"\nExit code: {code}")
    print(f"Sector report folder: {out}")
    inv = out / "sector_inventory.csv"
    if inv.exists():
        print("\n--- first sector rows ---")
        print("\n".join(inv.read_text(errors="replace").splitlines()[:35]))
    open_folder(out)
    wait()


def sector_patch() -> None:
    f = ask_file()
    if not f:
        wait(); return
    sector = input("Sector name to patch, e.g. esc_villaWall04x: ").strip()
    if not sector:
        wait(); return
    print("State: 1 enabled, 2 disabled, blank keep current")
    state_choice = input("Choose state: ").strip()
    state = "enabled" if state_choice == "1" else "disabled" if state_choice == "2" else ""
    print("Type: 1 world, 2 child, blank keep current")
    type_choice = input("Choose type: ").strip()
    stype = "world" if type_choice == "1" else "child" if type_choice == "2" else ""
    replace_with = input("Replace sector name with (blank no rename): ").strip()
    patch_all = input("Patch ALL matching entries? [y/N]: ").strip().lower() == "y"
    PATCHED.mkdir(exist_ok=True)
    out = PATCHED / f"{f.stem}_sectorpatched{f.suffix}"
    args = ["sector-patch", str(f), "--sector", sector, "--out", str(out)]
    if state: args += ["--set-state", state]
    if stype: args += ["--set-type", stype]
    if replace_with: args += ["--replace-with", replace_with]
    if patch_all: args += ["--all"]
    code = run(args)
    print(f"\nExit code: {code}")
    if out.exists():
        print(f"Patched copy: {out}")
        man = out.with_suffix(out.suffix + ".manifest.json")
        if man.exists():
            print("\n--- manifest preview ---")
            print(man.read_text(errors="replace")[:4000])
        open_folder(PATCHED)
    wait()

def print_help() -> None:
    print("""
BASIC USE
1. Put this folder somewhere simple, like Desktop\codered_mod_workbench.
2. Run CodeRED_Workbench_Start.bat.
3. Choose option 1 to scan your file first.
4. Use option 3 for text/string replacements.
5. Use options 5 and 6 for enum/integer replacements like 1166 -> 1193.
6. Use options 7 and 8 for Morning Star-style world/child sector scanning and toggles.

WSC RULE
For WSC/RSC85 files, string replacements must be the same length or shorter.
Shorter strings are padded safely. Longer strings are blocked.

OUTPUT
Patched files are copies in the patched folder.
Reports are in the reports folder.
Your original file is never overwritten.
""")
    wait()


def main() -> int:
    PATCHED.mkdir(exist_ok=True)
    REPORTS.mkdir(exist_ok=True)
    while True:
        print("\n" + "=" * 62)
        print(" Code RED Mod Workbench v0.3 - Start Here")
        print("=" * 62)
        print("1) Scan a file and show readable candidates")
        print("2) Show file / RSC85 info")
        print("3) Replace text/string and save a patched copy")
        print("4) Interactive string replacement")
        print("5) Find integer/enum value, like 1166")
        print("6) Replace integer/enum value, like 1166 -> 1193")
        print("7) Scan world/child sector entries")
        print("8) Patch sector: enable/disable, world/child, optional rename")
        print("9) Help / what to do")
        print("0) Exit")
        choice = input("Choose: ").strip()
        if choice == "1": scan_file()
        elif choice == "2": info_file()
        elif choice == "3": replace_text()
        elif choice == "4": interactive()
        elif choice == "5": find_int()
        elif choice == "6": replace_int()
        elif choice == "7": sector_scan()
        elif choice == "8": sector_patch()
        elif choice == "9": print_help()
        elif choice == "0": return 0
        else: print("Unknown choice.")


if __name__ == "__main__":
    raise SystemExit(main())
