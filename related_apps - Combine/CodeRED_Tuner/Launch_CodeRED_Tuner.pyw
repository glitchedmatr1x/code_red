#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
REQ = APP_DIR / "requirements.txt"
REQUIRED = [
    ("panda3d", "panda3d"),
    ("pygame", "pygame"),
    ("cryptography", "cryptography"),
]


def _status_window(title: str, message: str):
    try:
        import tkinter as tk
        root = tk.Tk()
        root.title(title)
        root.geometry("560x160")
        root.configure(bg="#090305")
        root.resizable(False, False)
        label = tk.Label(root, text=message + "\n\nby GLITCHED MATRIX Prototype Lab", bg="#090305", fg="#f4e9ea", justify="left", wraplength=520, font=("Segoe UI", 10))
        label.pack(fill="both", expand=True, padx=18, pady=18)
        root.update_idletasks()
        root.update()
        return root, label
    except Exception:
        return None, None


def _set_status(root, label, message: str) -> None:
    try:
        if label is not None:
            label.configure(text=message)
        if root is not None:
            root.update_idletasks()
            root.update()
    except Exception:
        pass


def _show_error(root, message: str) -> None:
    try:
        import tkinter.messagebox as messagebox
        messagebox.showerror("Code RED Tuner", message)
    except Exception:
        print(message, file=sys.stderr)
    try:
        if root is not None:
            root.destroy()
    except Exception:
        pass


def _missing_packages() -> list[str]:
    missing = []
    for module_name, package_name in REQUIRED:
        if importlib.util.find_spec(module_name) is None:
            missing.append(package_name)
    return missing


def _install_missing(root, label) -> None:
    missing = _missing_packages()
    if not missing:
        return
    _set_status(root, label, "Installing Code RED Tuner dependencies...\n" + ", ".join(missing))
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade"]
    if REQ.exists():
        cmd += ["-r", str(REQ)]
    else:
        cmd += missing
    proc = subprocess.run(cmd, cwd=str(APP_DIR), capture_output=True, text=True)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "pip install failed").strip()[-2400:]
        raise RuntimeError(detail)


def _launch_demo(root, label) -> int:
    script = APP_DIR / "code_red_arcade.py"
    settings = APP_DIR / "runtime" / "arcade_settings.json"
    if not script.exists():
        raise FileNotFoundError(script)
    _set_status(root, label, "Starting Code RED Test Demo...")
    subprocess.Popen([sys.executable, str(script), "--settings", str(settings), "--renderer", "panda"], cwd=str(APP_DIR))
    try:
        if root is not None:
            root.destroy()
    except Exception:
        pass
    return 0


def _launch_tuner(root, label) -> int:
    _set_status(root, label, "Opening Code RED Tuner interface...")
    try:
        if root is not None:
            root.destroy()
    except Exception:
        pass
    import codered_tuner
    return int(codered_tuner.main())


def main() -> int:
    target_demo = "--demo" in sys.argv[1:]
    root, label = _status_window("Code RED Tuner Launcher", "Preparing Code RED Tuner...")
    try:
        _install_missing(root, label)
        if target_demo:
            return _launch_demo(root, label)
        return _launch_tuner(root, label)
    except Exception as exc:
        _show_error(root, f"Code RED Tuner could not launch.\n\n{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
