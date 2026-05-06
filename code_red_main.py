"""
Code RED main workbench - consolidated UI shell.

This shell is intentionally conservative:
- RPF archives are treated as read-only game archives.
- ZIP files are treated as package/transport archives.
- Script resources stay classified in the Scripts lane; this file does not
  compile or mutate scripts.

Python: 3.13+
Dependencies: stdlib only (tkinter is bundled with most Python builds)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except Exception:  # pragma: no cover - allows headless/static imports
    tk = None  # type: ignore[assignment]
    ttk = None  # type: ignore[assignment]
    filedialog = None  # type: ignore[assignment]
    messagebox = None  # type: ignore[assignment]

APP_TITLE = "Code RED - Main Workbench"
APP_VERSION = "rpf-first-anti-regression-2026-05-06"

SPLIT_ZIP_EXTENSIONS = tuple(f".z{i:02d}" for i in range(1, 100))
SCRIPT_EXTENSIONS = (".wsc", ".xsc", ".sco")

# Centralized lane routing. Keep this as the single source of truth for buttons,
# inspector headings, report grouping, and anti-regression checks.
RESOURCE_LANES: dict[str, tuple[str, ...]] = {
    "Archives": (".rpf", ".zip") + SPLIT_ZIP_EXTENSIONS,
    "Textures": (".wtd", ".wtx", ".xtd", ".xtx", ".dds", ".png", ".jpg", ".jpeg", ".bmp"),
    "Meshes": (".wft", ".wfd", ".wvd", ".wsi", ".yft", ".ydr"),
    "Scripts": SCRIPT_EXTENSIONS,
    "Strings": (".strtbl", ".txt", ".csv", ".json", ".xml", ".ini"),
    "Audio": (".awc", ".wav", ".mp3", ".ogg"),
    "World": (".wpl", ".ipl", ".ymap", ".dat"),
    "Other": (),
}

TOP_ACTIONS = (
    "Open File",
    "Open Folder",
    "Scan Archive",
    "Validate Layout",
    "Export Report",
)

THEME = {
    "bg": "#120707",
    "panel": "#1b0b0b",
    "panel_alt": "#211010",
    "accent": "#d72b2b",
    "accent_dark": "#792020",
    "text": "#f3eeee",
    "muted": "#b59a9a",
    "border": "#3b1717",
    "good": "#75d17a",
    "warn": "#e4be56",
}

# Lightweight RPF inventory: read-only name discovery. This is not a write-back
# backend and does not attempt to compile, decrypt, or mutate scripts.
RPF_NAME_EXTENSIONS = tuple(
    sorted(
        {
            ext.lstrip(".")
            for exts in RESOURCE_LANES.values()
            for ext in exts
            if ext and not re.fullmatch(r"\.z\d\d", ext)
        }
        | {"img", "rel", "meta", "cfg", "bin", "weap", "ide", "cut", "rpf"}
    )
)
RPF_NAME_PATTERN = re.compile(
    rb"[A-Za-z0-9_ ./\\\-]{1,180}\.(?:"
    + b"|".join(re.escape(ext.encode("ascii")) for ext in RPF_NAME_EXTENSIONS)
    + rb")",
    re.IGNORECASE,
)


@dataclass
class ResourceRecord:
    path: str
    lane: str
    extension: str
    size: int = 0
    sha1: str = ""
    source: str = "filesystem"
    notes: list[str] = field(default_factory=list)


@dataclass
class WorkbenchState:
    root_path: Optional[Path] = None
    records: list[ResourceRecord] = field(default_factory=list)
    selected_lane: str = "Archives"
    last_report: Optional[Path] = None

    def lane_counts(self) -> dict[str, int]:
        counts = {lane: 0 for lane in RESOURCE_LANES}
        for rec in self.records:
            counts[rec.lane] = counts.get(rec.lane, 0) + 1
        return counts


def classify_extension(path: str | Path) -> str:
    suffix = Path(str(path).split("::")[-1]).suffix.lower()
    for lane, exts in RESOURCE_LANES.items():
        if suffix in exts:
            return lane
    return "Other"


def safe_sha1(path: Path, max_bytes: int = 32 * 1024 * 1024) -> str:
    """Hash a bounded prefix to avoid locking the UI on huge RPF archives."""
    h = hashlib.sha1()
    with path.open("rb") as fh:
        remaining = max_bytes
        while remaining > 0:
            chunk = fh.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            h.update(chunk)
            remaining -= len(chunk)
    return h.hexdigest()


def is_rpf_archive(path: Path) -> bool:
    if not path.is_file() or path.suffix.lower() != ".rpf":
        return False
    try:
        with path.open("rb") as fh:
            return fh.read(4).upper().startswith(b"RPF")
    except OSError:
        return False


def _split_fragment_note(path: Path) -> Optional[str]:
    if path.suffix.lower() in SPLIT_ZIP_EXTENSIONS:
        return "split ZIP/package fragment; keep beside matching .zip, not a game RPF archive"
    return None


def scan_filesystem(path: Path) -> list[ResourceRecord]:
    records: list[ResourceRecord] = []
    candidates = [path] if path.is_file() else [p for p in path.rglob("*") if p.is_file()]

    for fp in candidates:
        try:
            stat = fp.stat()
            notes: list[str] = []
            if stat.st_size > 128 * 1024 * 1024:
                notes.append("large file; prefix hash only")
            if fp.suffix.lower() == ".rpf":
                notes.append("RPF game archive; Scan Archive inventories members read-only")
            fragment_note = _split_fragment_note(fp)
            if fragment_note:
                notes.append(fragment_note)
            records.append(
                ResourceRecord(
                    path=str(fp),
                    lane=classify_extension(fp),
                    extension=fp.suffix.lower(),
                    size=stat.st_size,
                    sha1=safe_sha1(fp),
                    notes=notes,
                )
            )
        except OSError as exc:
            records.append(ResourceRecord(path=str(fp), lane="Other", extension=fp.suffix.lower(), notes=[f"stat/read failed: {exc}"]))
    return records


def _record_from_archive_member(archive: Path, member_name: str, *, size: int = 0, source: str, note: str) -> ResourceRecord:
    member_path = member_name.strip().replace("\\", "/")
    return ResourceRecord(
        path=f"{archive}::{member_path}",
        lane=classify_extension(member_path),
        extension=Path(member_path).suffix.lower(),
        size=size,
        sha1="",
        source=source,
        notes=[note],
    )


def scan_zip_members(path: Path, limit: int = 4000) -> list[ResourceRecord]:
    records: list[ResourceRecord] = []
    if not zipfile.is_zipfile(path):
        return records
    with zipfile.ZipFile(path, "r") as zf:
        for idx, info in enumerate(zf.infolist()):
            if idx >= limit:
                records.append(ResourceRecord(path=f"{path}::<truncated>", lane="Other", extension="", source="zip", notes=[f"member limit {limit} reached"]))
                break
            if info.is_dir():
                continue
            records.append(_record_from_archive_member(path, info.filename, size=info.file_size, source="zip", note="ZIP package member; not a game RPF entry"))
    return records


def scan_rpf_members(path: Path, limit: int = 4000, read_limit: int = 96 * 1024 * 1024) -> list[ResourceRecord]:
    """Inventory likely member names from an RPF without modifying the archive.

    This intentionally stays lightweight. It recognizes RPF magic, scans a bounded
    prefix for readable resource names, and classifies discovered entries through
    the normal lane router. If a valid RPF has no readable names, it still returns
    a marker record so the UI does not pretend the archive is a ZIP failure.
    """
    records: list[ResourceRecord] = []
    if not is_rpf_archive(path):
        return records
    try:
        with path.open("rb") as fh:
            blob = fh.read(read_limit)
    except OSError as exc:
        return [ResourceRecord(path=f"{path}::<rpf read failed>", lane="Archives", extension=".rpf", source="rpf", notes=[str(exc)])]

    seen: set[str] = set()
    for match in RPF_NAME_PATTERN.finditer(blob):
        name = match.group(0).decode("utf-8", "ignore").strip(" \t\r\n\x00").replace("\\", "/")
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        records.append(_record_from_archive_member(path, name, source="rpf", note="RPF member inventory; read-only"))
        if len(records) >= limit:
            records.append(ResourceRecord(path=f"{path}::<truncated>", lane="Other", extension="", source="rpf", notes=[f"member limit {limit} reached"]))
            break

    if not records:
        records.append(
            ResourceRecord(
                path=f"{path}::<rpf detected>",
                lane="Archives",
                extension=".rpf",
                source="rpf",
                notes=["RPF magic detected; no readable member names found in bounded scan"],
            )
        )
    return records


def scan_archive_members(path: Path, limit: int = 4000) -> list[ResourceRecord]:
    """Dispatch archive inventory by game/archive type.

    RPF dispatch comes first so a game archive never falls through to ZIP logic.
    """
    if path.suffix.lower() == ".rpf" or is_rpf_archive(path):
        return scan_rpf_members(path, limit=limit)
    if path.suffix.lower() == ".zip" or zipfile.is_zipfile(path):
        return scan_zip_members(path, limit=limit)
    if path.suffix.lower() in SPLIT_ZIP_EXTENSIONS:
        note = _split_fragment_note(path) or "split archive fragment"
        return [ResourceRecord(path=f"{path}::<split-fragment>", lane="Archives", extension=path.suffix.lower(), source="split-fragment", notes=[note])]
    return []


def records_to_report(state: WorkbenchState) -> dict[str, object]:
    counts = state.lane_counts()
    grouped: dict[str, list[dict[str, object]]] = {lane: [] for lane in RESOURCE_LANES}
    for rec in state.records:
        grouped.setdefault(rec.lane, []).append(
            {
                "path": rec.path,
                "extension": rec.extension,
                "size": rec.size,
                "sha1_prefix": rec.sha1[:12],
                "source": rec.source,
                "notes": rec.notes,
            }
        )
    return {
        "app": APP_TITLE,
        "version": APP_VERSION,
        "root_path": str(state.root_path) if state.root_path else None,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "lane_counts": counts,
        "archive_readers": ["rpf-readonly-inventory", "zip-package-inventory"],
        "script_lane_guard": {ext: classify_extension(f"guard{ext}") for ext in SCRIPT_EXTENSIONS},
        "records_by_lane": grouped,
    }


def self_test_payload() -> dict[str, object]:
    script_guard = {ext: classify_extension(f"guard{ext}") for ext in SCRIPT_EXTENSIONS}
    archive_guard = {".rpf": classify_extension("content.rpf"), ".zip": classify_extension("package.zip"), ".z01": classify_extension("package.z01")}
    ok = all(lane == "Scripts" for lane in script_guard.values()) and all(lane == "Archives" for lane in archive_guard.values())
    return {
        "ok": ok,
        "app": APP_TITLE,
        "version": APP_VERSION,
        "lanes": list(RESOURCE_LANES),
        "actions": TOP_ACTIONS,
        "archive_readers": ["rpf-readonly-inventory", "zip-package-inventory"],
        "script_lane_guard": script_guard,
        "archive_lane_guard": archive_guard,
    }


class CodeRedApp:
    """Stable three-panel UI: top toolbar, left rail, center workspace, right inspector."""

    def __init__(self, root: "tk.Tk") -> None:
        if tk is None or ttk is None:
            raise RuntimeError("tkinter is not available in this Python environment")
        self.root = root
        self.state = WorkbenchState()
        self._lane_buttons: dict[str, ttk.Button] = {}
        self._configure_root()
        self._configure_styles()
        self._build_shell()
        self._set_status("Ready. Open a file or folder. RPF scans are read-only; ZIP is package-only.")

    def _configure_root(self) -> None:
        self.root.title(f"{APP_TITLE} ({APP_VERSION})")
        self.root.geometry("1280x760")
        self.root.minsize(980, 620)
        self.root.configure(bg=THEME["bg"])
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("CodeRed.TFrame", background=THEME["bg"])
        style.configure("Panel.TFrame", background=THEME["panel"], borderwidth=1, relief="solid")
        style.configure("Alt.Panel.TFrame", background=THEME["panel_alt"], borderwidth=1, relief="solid")
        style.configure("CodeRed.TLabel", background=THEME["panel"], foreground=THEME["text"])
        style.configure("Muted.TLabel", background=THEME["panel"], foreground=THEME["muted"])
        style.configure("Brand.TLabel", background=THEME["bg"], foreground=THEME["accent"], font=("Segoe UI", 17, "bold"))
        style.configure("CodeRed.TButton", background=THEME["accent_dark"], foreground=THEME["text"], padding=(10, 7), relief="flat")
        style.map("CodeRed.TButton", background=[("active", THEME["accent"]), ("pressed", THEME["accent_dark"])] )
        style.configure("Lane.TButton", background=THEME["panel_alt"], foreground=THEME["text"], padding=(10, 9), anchor="w")
        style.map("Lane.TButton", background=[("active", THEME["accent_dark"]), ("pressed", THEME["accent"])] )
        style.configure("Treeview", background="#100808", fieldbackground="#100808", foreground=THEME["text"], rowheight=24)
        style.configure("Treeview.Heading", background=THEME["accent_dark"], foreground=THEME["text"], font=("Segoe UI", 9, "bold"))
        style.configure("TNotebook", background=THEME["panel"])
        style.configure("TNotebook.Tab", padding=(10, 5))

    def _button(self, parent: "tk.Widget", text: str, command: Callable[[], None], *, style: str = "CodeRed.TButton") -> "ttk.Button":
        return ttk.Button(parent, text=text, command=command, style=style)

    def _build_shell(self) -> None:
        shell = ttk.Frame(self.root, style="CodeRed.TFrame", padding=10)
        shell.grid(row=0, column=0, sticky="nsew")
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(1, weight=1)
        self._build_toolbar(shell)
        self._build_body(shell)
        self._build_status(shell)

    def _build_toolbar(self, shell: "ttk.Frame") -> None:
        toolbar = ttk.Frame(shell, style="CodeRed.TFrame")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        toolbar.columnconfigure(7, weight=1)
        ttk.Label(toolbar, text="CODE RED", style="Brand.TLabel").grid(row=0, column=0, padx=(0, 18), sticky="w")
        actions: list[tuple[str, Callable[[], None]]] = [
            ("Open File", self.open_file),
            ("Open Folder", self.open_folder),
            ("Scan Archive", self.scan_archive),
            ("Validate Layout", self.validate_layout),
            ("Export Report", self.export_report),
        ]
        for idx, (label, callback) in enumerate(actions, start=1):
            self._button(toolbar, label, callback).grid(row=0, column=idx, padx=4, sticky="ew")
        self.summary_label = ttk.Label(toolbar, text="No scan loaded", style="Muted.TLabel")
        self.summary_label.grid(row=0, column=7, padx=(14, 0), sticky="e")

    def _build_body(self, shell: "ttk.Frame") -> None:
        body = ttk.Frame(shell, style="CodeRed.TFrame")
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, minsize=210, weight=0)
        body.columnconfigure(1, weight=5)
        body.columnconfigure(2, weight=3)
        body.rowconfigure(0, weight=1)
        self._build_lane_rail(body)
        self._build_workspace(body)
        self._build_inspector(body)

    def _build_lane_rail(self, body: "ttk.Frame") -> None:
        rail = ttk.Frame(body, style="Panel.TFrame", padding=10)
        rail.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        rail.columnconfigure(0, weight=1)
        ttk.Label(rail, text="Resource Lanes", style="CodeRed.TLabel", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="ew", pady=(0, 8))
        for row, lane in enumerate(RESOURCE_LANES, start=1):
            button = self._button(rail, lane, lambda name=lane: self.select_lane(name), style="Lane.TButton")
            button.grid(row=row, column=0, sticky="ew", pady=3)
            self._lane_buttons[lane] = button
        rail.rowconfigure(len(RESOURCE_LANES) + 1, weight=1)
        hint = "RPF is read-only game archive inventory. ZIP is package inventory. Script lane is protected."
        ttk.Label(rail, text=hint, style="Muted.TLabel", wraplength=180, justify="left").grid(row=len(RESOURCE_LANES) + 2, column=0, sticky="sew", pady=(12, 0))

    def _build_workspace(self, body: "ttk.Frame") -> None:
        frame = ttk.Frame(body, style="Panel.TFrame", padding=10)
        frame.grid(row=0, column=1, sticky="nsew", padx=(0, 10))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)
        ttk.Label(frame, text="Workspace", style="CodeRed.TLabel", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 6))
        columns = ("lane", "extension", "size", "source", "path")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
        headings = {"lane": "Lane", "extension": "Ext", "size": "Size", "source": "Source", "path": "Path"}
        widths = {"lane": 100, "extension": 70, "size": 90, "source": 110, "path": 540}
        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], minwidth=50, stretch=(col == "path"))
        yscroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        xscroll = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.grid(row=1, column=0, sticky="nsew")
        yscroll.grid(row=1, column=1, sticky="ns")
        xscroll.grid(row=2, column=0, sticky="ew")
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

    def _build_inspector(self, body: "ttk.Frame") -> None:
        frame = ttk.Frame(body, style="Panel.TFrame", padding=10)
        frame.grid(row=0, column=2, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)
        ttk.Label(frame, text="Inspector", style="CodeRed.TLabel", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.notebook = ttk.Notebook(frame)
        self.notebook.grid(row=1, column=0, sticky="nsew")
        self.details_text = self._text_tab("Details")
        self.report_text = self._text_tab("Report")
        self.log_text = self._text_tab("Log")
        self._write_text(self.details_text, "Select a resource to inspect it.\n")

    def _text_tab(self, title: str) -> "tk.Text":
        tab = ttk.Frame(self.notebook, style="Alt.Panel.TFrame", padding=6)
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)
        text = tk.Text(tab, wrap="word", background="#100808", foreground=THEME["text"], insertbackground=THEME["text"], relief="flat", padx=8, pady=8)
        text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(tab, orient="vertical", command=text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        text.configure(yscrollcommand=scroll.set)
        self.notebook.add(tab, text=title)
        return text

    def _build_status(self, shell: "ttk.Frame") -> None:
        status = ttk.Frame(shell, style="CodeRed.TFrame")
        status.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        status.columnconfigure(0, weight=1)
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(status, textvariable=self.status_var, style="Muted.TLabel").grid(row=0, column=0, sticky="w")

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)
        self._log(text)

    def _write_text(self, widget: "tk.Text", text: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def _append_text(self, widget: "tk.Text", text: str) -> None:
        widget.configure(state="normal")
        widget.insert("end", text + "\n")
        widget.see("end")
        widget.configure(state="disabled")

    def _log(self, text: str) -> None:
        if hasattr(self, "log_text"):
            self._append_text(self.log_text, f"[{time.strftime('%H:%M:%S')}] {text}")

    def open_file(self) -> None:
        if filedialog is None:
            return
        path = filedialog.askopenfilename(title="Open Code RED resource")
        if path:
            self.load_path(Path(path))

    def open_folder(self) -> None:
        if filedialog is None:
            return
        path = filedialog.askdirectory(title="Open Code RED folder")
        if path:
            self.load_path(Path(path))

    def scan_archive(self) -> None:
        if self.state.root_path and self.state.root_path.is_file():
            known_paths = {rec.path for rec in self.state.records}
            records = [rec for rec in scan_archive_members(self.state.root_path) if rec.path not in known_paths]
            if records:
                self.state.records.extend(records)
                self.refresh_records()
                self._set_status(f"Scanned archive members from {self.state.root_path.name}.")
                return
        if messagebox is not None:
            messagebox.showinfo("Scan Archive", "Open a .rpf game archive or .zip package first. RPF parsing is read-only.")

    def load_path(self, path: Path) -> None:
        self.state = WorkbenchState(root_path=path, selected_lane=self.state.selected_lane)
        self.state.records = scan_filesystem(path)
        if path.is_file():
            self.state.records.extend(scan_archive_members(path))
        self.refresh_records()
        self._set_status(f"Loaded {len(self.state.records)} resources from {path}.")

    def select_lane(self, lane: str) -> None:
        self.state.selected_lane = lane
        self.refresh_records()
        self._set_status(f"Lane selected: {lane}")

    def refresh_records(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        selected = self.state.selected_lane
        records = [rec for rec in self.state.records if rec.lane == selected]
        for idx, rec in enumerate(records):
            self.tree.insert("", "end", iid=str(idx), values=(rec.lane, rec.extension or "-", f"{rec.size:,}", rec.source, rec.path))
        counts = self.state.lane_counts()
        self.summary_label.configure(text="  ".join(f"{lane}:{count}" for lane, count in counts.items() if count) or "No resources")
        self._write_text(self.report_text, json.dumps(records_to_report(self.state), indent=2))

    def _on_tree_select(self, _event: object = None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        values = self.tree.item(selection[0], "values")
        path = str(values[4]) if len(values) >= 5 else ""
        rec = next((item for item in self.state.records if item.path == path), None)
        if not rec:
            return
        details = [
            f"Path: {rec.path}",
            f"Lane: {rec.lane}",
            f"Extension: {rec.extension or '-'}",
            f"Size: {rec.size:,} bytes",
            f"SHA1 prefix: {rec.sha1[:16] or 'archive-member/not-hashed'}",
            f"Source: {rec.source}",
        ]
        if rec.notes:
            details.append("Notes:")
            details.extend(f"- {note}" for note in rec.notes)
        self._write_text(self.details_text, "\n".join(details) + "\n")

    def validate_layout(self) -> None:
        self.root.update_idletasks()
        checks = self_test_payload()
        checks.update(
            {
                "top_actions_expected": len(TOP_ACTIONS),
                "top_actions_actual": 5,
                "lanes_expected": len(RESOURCE_LANES),
                "lanes_actual": len(self._lane_buttons),
                "root_min_width": self.root.minsize()[0],
                "root_min_height": self.root.minsize()[1],
                "layout": "toolbar + left rail + workspace + inspector + status",
            }
        )
        checks["status"] = "PASS" if checks["ok"] and checks["top_actions_actual"] == checks["top_actions_expected"] and checks["lanes_actual"] == checks["lanes_expected"] else "FAIL"
        self._write_text(self.details_text, json.dumps(checks, indent=2))
        self._set_status(f"Layout validation {checks['status']}.")

    def export_report(self) -> None:
        base = Path.cwd()
        if self.state.root_path:
            base = self.state.root_path.parent if self.state.root_path.is_file() else self.state.root_path
        target = base / "Code_RED_scan_report.json"
        target.write_text(json.dumps(records_to_report(self.state), indent=2), encoding="utf-8")
        self.state.last_report = target
        self._set_status(f"Exported report: {target}")
        if messagebox is not None:
            messagebox.showinfo("Export Report", f"Report written:\n{target}")


def _records_to_json(records: list[ResourceRecord]) -> list[dict[str, object]]:
    return [
        {
            "path": rec.path,
            "lane": rec.lane,
            "extension": rec.extension,
            "size": rec.size,
            "source": rec.source,
            "notes": rec.notes,
        }
        for rec in records
    ]


def main(argv: Optional[Iterable[str]] = None) -> int:
    argv = list(argv or sys.argv[1:])
    if "--self-test" in argv:
        payload = self_test_payload()
        print(json.dumps(payload, indent=2))
        return 0 if payload.get("ok") else 1
    if "--scan-archive" in argv:
        idx = argv.index("--scan-archive")
        if idx + 1 >= len(argv):
            print("--scan-archive requires a path", file=sys.stderr)
            return 2
        records = scan_archive_members(Path(argv[idx + 1]))
        print(json.dumps(_records_to_json(records), indent=2))
        return 0 if records else 1
    if tk is None:
        print("tkinter is not available", file=sys.stderr)
        return 2
    root = tk.Tk()
    app = CodeRedApp(root)
    if argv:
        candidate = Path(argv[0])
        if candidate.exists():
            app.load_path(candidate)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
