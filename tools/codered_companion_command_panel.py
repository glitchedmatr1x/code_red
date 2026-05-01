#!/usr/bin/env python3
"""Code RED Companion Command Panel.

Small standalone Tk panel for writing CodeREDCompanion ASI proof commands.
Pass 0.6 writes command files and override manifests only. It does not execute game actions or enable file redirects.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

ROOT = Path(__file__).resolve().parents[1]
WRITER = ROOT / "tools" / "codered_companion_command_writer.py"
OVERRIDE_TOOL = ROOT / "tools" / "codered_override_manifest_tool.py"
DEFAULT_GAME_ROOT = Path.cwd()

SAFE_COMMANDS = ["PING", "STATUS", "VERSION", "HELP", "SCAN_OVERRIDES"]
FUTURE_COMMANDS = ["SPAWN_ACTOR", "FOLLOW", "GUARD", "ATTACK", "DISMISS", "MOUNT", "WAYPOINT", "TELEPORT", "SET_FORMATION"]
PRESETS = ["tune-refgroup", "tune-table", "string-table", "script-source", "config-json", "text-note"]
ACTORS = [
    "ACTOR_CAUCASIAN_ARMY_Easy01",
    "AE_CAUCASIAN_ARMY_EASY01",
    "ACTOR_CAUCASIAN_MALE_TownFolk02",
    "ACTOR_RIDEABLE_ANIMAL_Horse01",
    "ACTOR_RIDEABLE_ANIMAL_MEX_Mule01",
    "ACTOR_VEHICLE_Car01",
    "ACTOR_VEHICLE_Truck01",
    "ACTOR_VEHICLE_Stagecoach",
    "ACTOR_VEHICLE_Wagon02",
    "ACTOR_VEHICLE_Coach01",
]


class CompanionCommandPanel(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Code RED Companion Command Panel")
        self.geometry("980x740")
        self.minsize(820, 620)
        self.configure(bg="#120202")

        self.game_root = tk.StringVar(value=str(DEFAULT_GAME_ROOT))
        self.command = tk.StringVar(value="PING")
        self.actor = tk.StringVar(value=ACTORS[0])
        self.extra_args = tk.StringVar(value="")
        self.command_id = tk.StringVar(value="")
        self.replace_file = tk.BooleanVar(value=False)
        self.override_source = tk.StringVar(value="")
        self.override_virtual_path = tk.StringVar(value="content/tune/refgroups/example.xtbl")
        self.override_preset = tk.StringVar(value=PRESETS[0])
        self.override_preset_name = tk.StringVar(value="example")
        self.override_rule = tk.StringVar(value="")

        self._build_ui()
        self._refresh_paths()

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#120202")
        style.configure("TLabelframe", background="#120202", foreground="#ffdddd")
        style.configure("TLabelframe.Label", background="#120202", foreground="#ff4b4b", font=("Segoe UI", 10, "bold"))
        style.configure("TLabel", background="#120202", foreground="#f0d0d0")
        style.configure("TButton", padding=6)

        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        tk.Label(root, text="Code RED Companion Command Panel", bg="#120202", fg="#ff3b3b", font=("Segoe UI", 17, "bold")).pack(anchor="w")
        tk.Label(
            root,
            text="Pass 0.6 proof lane: commands + override manifest editor. Actor execution and file redirects remain disabled.",
            bg="#120202",
            fg="#f0c0c0",
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(2, 10))

        game = ttk.LabelFrame(root, text="Target game folder")
        game.pack(fill="x", pady=(0, 10))
        game_inner = ttk.Frame(game, padding=8)
        game_inner.pack(fill="x")
        ttk.Entry(game_inner, textvariable=self.game_root).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Button(game_inner, text="Browse", command=self._browse_game_root).pack(side="left")
        ttk.Button(game_inner, text="Refresh", command=self._refresh_paths).pack(side="left", padx=(8, 0))

        paths = ttk.LabelFrame(root, text="Resolved files")
        paths.pack(fill="x", pady=(0, 10))
        self.paths_text = tk.Text(paths, height=6, wrap="word", bg="#1b0505", fg="#f4dddd", insertbackground="#ffffff")
        self.paths_text.pack(fill="x", padx=8, pady=8)

        form = ttk.LabelFrame(root, text="Command")
        form.pack(fill="x", pady=(0, 10))
        grid = ttk.Frame(form, padding=8)
        grid.pack(fill="x")
        for i in range(2):
            grid.columnconfigure(i, weight=1)

        ttk.Label(grid, text="Command").grid(row=0, column=0, sticky="w")
        command_box = ttk.Combobox(grid, textvariable=self.command, values=SAFE_COMMANDS + FUTURE_COMMANDS, state="readonly")
        command_box.grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=(2, 8))
        command_box.bind("<<ComboboxSelected>>", lambda _evt: self._refresh_hint())

        ttk.Label(grid, text="Actor / target candidate").grid(row=0, column=1, sticky="w")
        ttk.Combobox(grid, textvariable=self.actor, values=ACTORS).grid(row=1, column=1, sticky="ew", pady=(2, 8))

        ttk.Label(grid, text="Extra args").grid(row=2, column=0, sticky="w")
        ttk.Entry(grid, textvariable=self.extra_args).grid(row=3, column=0, sticky="ew", padx=(0, 8), pady=(2, 8))

        ttk.Label(grid, text="Command ID (optional)").grid(row=2, column=1, sticky="w")
        ttk.Entry(grid, textvariable=self.command_id).grid(row=3, column=1, sticky="ew", pady=(2, 8))
        ttk.Checkbutton(grid, text="Replace command file instead of appending", variable=self.replace_file).grid(row=4, column=0, columnspan=2, sticky="w")
        self.hint = tk.Label(grid, text="", bg="#120202", fg="#ffd0d0", justify="left")
        self.hint.grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))

        override = ttk.LabelFrame(root, text="Override manifest proof editor")
        override.pack(fill="x", pady=(0, 10))
        og = ttk.Frame(override, padding=8)
        og.pack(fill="x")
        og.columnconfigure(1, weight=1)
        og.columnconfigure(3, weight=1)
        ttk.Label(og, text="Source file").grid(row=0, column=0, sticky="w")
        ttk.Entry(og, textvariable=self.override_source).grid(row=0, column=1, sticky="ew", padx=(6, 6))
        ttk.Button(og, text="Browse", command=self._browse_override_source).grid(row=0, column=2, padx=(0, 10))
        ttk.Label(og, text="Virtual path").grid(row=0, column=3, sticky="w")
        ttk.Entry(og, textvariable=self.override_virtual_path).grid(row=0, column=4, sticky="ew", padx=(6, 0))
        ttk.Label(og, text="Preset").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(og, textvariable=self.override_preset, values=PRESETS, state="readonly").grid(row=1, column=1, sticky="ew", padx=(6, 6), pady=(8, 0))
        ttk.Label(og, text="Preset name").grid(row=1, column=2, sticky="w", pady=(8, 0))
        ttk.Entry(og, textvariable=self.override_preset_name).grid(row=1, column=3, sticky="ew", padx=(6, 6), pady=(8, 0))
        ttk.Label(og, text="Rule id/path").grid(row=1, column=4, sticky="w", pady=(8, 0))
        ttk.Entry(og, textvariable=self.override_rule).grid(row=1, column=5, sticky="ew", padx=(6, 0), pady=(8, 0))

        buttons = ttk.Frame(root)
        buttons.pack(fill="x", pady=(0, 10))
        for label, command in [
            ("Write Command", self._write_command),
            ("Dry Run", lambda: self._write_command(dry_run=True)),
            ("Init Manifest", self._init_override_manifest),
            ("Add Override", self._add_override),
            ("Add Preset", self._add_override_preset),
            ("Validate Manifest", self._validate_manifest),
            ("Write Report", self._write_manifest_report),
            ("Scan Overrides Command", self._scan_overrides_command),
            ("Open Logs", self._open_logs),
            ("Read Status", self._read_status),
        ]:
            ttk.Button(buttons, text=label, command=command).pack(side="left", padx=(0, 6))

        out_frame = ttk.LabelFrame(root, text="Output")
        out_frame.pack(fill="both", expand=True)
        self.output = tk.Text(out_frame, wrap="word", bg="#160404", fg="#fff2f2", insertbackground="#ffffff")
        self.output.pack(fill="both", expand=True, padx=8, pady=8)
        self._refresh_hint()

    def _game_root_path(self) -> Path:
        return Path(self.game_root.get()).expanduser()

    def _command_file(self) -> Path:
        return self._game_root_path() / "data" / "codered" / "companion_commands.txt"

    def _logs_folder(self) -> Path:
        return self._game_root_path() / "CodeRED_ASI_Logs"

    def _status_file(self) -> Path:
        return self._logs_folder() / "companion_status.json"

    def _override_root(self) -> Path:
        return self._game_root_path() / "CodeRED_Overrides"

    def _refresh_paths(self) -> None:
        self.paths_text.delete("1.0", "end")
        self.paths_text.insert("end", f"Command file:   {self._command_file()}\n")
        self.paths_text.insert("end", f"Override root:  {self._override_root()}\n")
        self.paths_text.insert("end", f"Override manifest: {self._override_root() / 'manifest.json'}\n")
        self.paths_text.insert("end", f"ASI logs:       {self._logs_folder()}\n")
        self.paths_text.insert("end", f"Status JSON:    {self._status_file()}\n")
        self.paths_text.insert("end", f"Validation report: {self._logs_folder() / 'override_manifest_validation_report.json'}\n")

    def _refresh_hint(self) -> None:
        cmd = self.command.get().upper()
        if cmd == "SCAN_OVERRIDES":
            text = "Override proof command: scans CodeRED_Overrides and writes file_override_stub.json. No redirects."
        elif cmd in SAFE_COMMANDS:
            text = "Safe proof command: accepted by ASI, still no game action."
        else:
            text = "Future command: ASI validates/logs it, writes trainer_bridge_stub.json, but does not execute it."
        self.hint.configure(text=text)

    def _browse_game_root(self) -> None:
        chosen = filedialog.askdirectory(title="Choose folder containing the game executable")
        if chosen:
            self.game_root.set(chosen)
            self._refresh_paths()

    def _browse_override_source(self) -> None:
        chosen = filedialog.askopenfilename(title="Choose override source file")
        if chosen:
            self.override_source.set(chosen)

    def _writer_args(self, dry_run: bool) -> list[str]:
        args = [sys.executable, str(WRITER), self.command.get(), "--game-root", str(self._game_root_path())]
        cmd = self.command.get().upper()
        if cmd in FUTURE_COMMANDS:
            args.extend(["--actor", self.actor.get()])
        if self.extra_args.get().strip():
            args.extend(self.extra_args.get().split())
        if self.command_id.get().strip():
            args.extend(["--id", self.command_id.get().strip()])
        if self.replace_file.get():
            args.append("--replace")
        if dry_run:
            args.append("--dry-run")
        return args

    def _run(self, args: list[str]) -> None:
        self._refresh_paths()
        try:
            result = subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True, check=False)
        except Exception as exc:
            messagebox.showerror("Command failed", str(exc))
            return
        self.output.insert("end", "$ " + " ".join(args) + "\n")
        if result.stdout:
            self.output.insert("end", result.stdout + "\n")
        if result.stderr:
            self.output.insert("end", result.stderr + "\n")
        self.output.insert("end", f"exit={result.returncode}\n\n")
        self.output.see("end")

    def _write_command(self, dry_run: bool = False) -> None:
        self._run(self._writer_args(dry_run))

    def _init_override_manifest(self) -> None:
        self._run([sys.executable, str(OVERRIDE_TOOL), "--game-root", str(self._game_root_path()), "--replace", "init"])

    def _add_override(self) -> None:
        if not self.override_source.get().strip():
            messagebox.showwarning("Missing source", "Choose an override source file first.")
            return
        self._run([sys.executable, str(OVERRIDE_TOOL), "--game-root", str(self._game_root_path()), "--replace", "add", self.override_source.get(), self.override_virtual_path.get()])

    def _add_override_preset(self) -> None:
        if not self.override_source.get().strip():
            messagebox.showwarning("Missing source", "Choose an override source file first.")
            return
        self._run([sys.executable, str(OVERRIDE_TOOL), "--game-root", str(self._game_root_path()), "--replace", "add-preset", self.override_preset.get(), self.override_preset_name.get(), self.override_source.get()])

    def _validate_manifest(self) -> None:
        self._run([sys.executable, str(OVERRIDE_TOOL), "--game-root", str(self._game_root_path()), "validate"])

    def _write_manifest_report(self) -> None:
        self._run([sys.executable, str(OVERRIDE_TOOL), "--game-root", str(self._game_root_path()), "write-report"])

    def _scan_overrides_command(self) -> None:
        self.command.set("SCAN_OVERRIDES")
        self.command_id.set("")
        self.replace_file.set(False)
        self._refresh_hint()
        self._write_command(dry_run=False)

    def _open_logs(self) -> None:
        folder = self._logs_folder()
        folder.mkdir(parents=True, exist_ok=True)
        if sys.platform.startswith("win"):
            import os
            os.startfile(str(folder))  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(folder)])

    def _read_status(self) -> None:
        path = self._status_file()
        if not path.exists():
            self.output.insert("end", f"No status file yet: {path}\n\n")
            self.output.see("end")
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            text = json.dumps(payload, indent=2)
        except Exception:
            text = path.read_text(encoding="utf-8", errors="replace")
        self.output.insert("end", text + "\n\n")
        self.output.see("end")


def main() -> int:
    app = CompanionCommandPanel()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
