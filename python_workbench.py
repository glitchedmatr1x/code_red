from __future__ import annotations

"""Code RED public workbench.

Focused GUI for the public package:
- Script Lab: view WSC/XSC/CSC/SCO resources, run Code RED inspection, build same-size recipes, and write patched copies.
- RPF Browser: read-only inventory of user-supplied RPF/ZIP archives.
- GPT Packet: concise JSON state export for users or AI agents.

The GUI intentionally avoids a giant button wall. Deep experiments remain available as tools/source files, but the app front door stays centered on script and RPF workflows.
"""

import argparse
import binascii
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterable, Optional

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog, ttk
except Exception:  # pragma: no cover - lets CLI self-tests work in headless envs
    tk = None  # type: ignore[assignment]
    ttk = None  # type: ignore[assignment]
    filedialog = None  # type: ignore[assignment]
    messagebox = None  # type: ignore[assignment]
    simpledialog = None  # type: ignore[assignment]

try:
    from codered_wsc.resource import KeyOptions, ResourceError, ScriptResource, open_script, repack_script, sha256
    from codered_wsc.analysis import extract_strings, write_inspect_report, write_map_report, write_scan_report
except Exception:  # pragma: no cover - public package can still open as a raw browser
    KeyOptions = None  # type: ignore[assignment]
    ResourceError = RuntimeError  # type: ignore[assignment]
    ScriptResource = object  # type: ignore[assignment]
    open_script = None  # type: ignore[assignment]
    repack_script = None  # type: ignore[assignment]
    extract_strings = None  # type: ignore[assignment]
    write_inspect_report = None  # type: ignore[assignment]
    write_map_report = None  # type: ignore[assignment]
    write_scan_report = None  # type: ignore[assignment]

try:
    from tools.codered_xbox_layer_resolver import LayerInput, analyze_layers, write_reports as write_layer_reports
except Exception:  # pragma: no cover - GUI still works without optional layer tool
    LayerInput = None  # type: ignore[assignment]
    analyze_layers = None  # type: ignore[assignment]
    write_layer_reports = None  # type: ignore[assignment]

try:
    from tools.codered_xiso_tool import (
        build_report as build_xiso_report,
        write_reports as write_xiso_reports,
        extract_file as xiso_extract_file,
        find_entry as xiso_find_entry,
        replacement_plan as xiso_replacement_plan,
        write_padded_replacement as xiso_write_padded_replacement,
        export_xenia_overlay as xiso_export_overlay,
        find_pattern_in_iso_entry as xiso_find_pattern_in_iso_entry,
        direct_nested_patch_plan as xiso_direct_nested_patch_plan,
        patch_copy_nested_same_size as xiso_patch_copy_nested_same_size,
    )
except Exception:  # pragma: no cover - GUI still works without optional ISO tool
    build_xiso_report = None  # type: ignore[assignment]
    write_xiso_reports = None  # type: ignore[assignment]
    xiso_extract_file = None  # type: ignore[assignment]
    xiso_find_entry = None  # type: ignore[assignment]
    xiso_replacement_plan = None  # type: ignore[assignment]
    xiso_write_padded_replacement = None  # type: ignore[assignment]
    xiso_export_overlay = None  # type: ignore[assignment]
    xiso_find_pattern_in_iso_entry = None  # type: ignore[assignment]
    xiso_direct_nested_patch_plan = None  # type: ignore[assignment]
    xiso_patch_copy_nested_same_size = None  # type: ignore[assignment]

APP_NAME = "Code RED"
APP_VERSION = "public-gui-xiso-nested-rpf-pass7"
ROOT = Path(__file__).resolve().parent
REPORT_DIR = ROOT / "reports" / "public_workbench"
SCRIPT_EXTS = {".wsc", ".xsc", ".csc", ".sco"}
ARCHIVE_EXTS = {".rpf", ".zip"}
TEXT_EXTS = {".txt", ".json", ".csv", ".xml", ".ini", ".md", ".yaml", ".yml"}
MAX_PREVIEW_BYTES = 256 * 1024
MAX_FOLDER_FILES = 5000

THEME = {
    "bg": "#100606",
    "panel": "#190a0a",
    "panel2": "#211010",
    "line": "#3a1616",
    "text": "#f4eeee",
    "muted": "#bd9c9c",
    "red": "#b51f1f",
    "red2": "#7d1b1b",
    "good": "#7bd47b",
    "warn": "#e0bd58",
    "dark_text": "#0f0707",
}

RPF_NAME_EXTENSIONS = sorted({
    "wsc", "xsc", "csc", "sco", "wsv", "strtbl", "txt", "csv", "json", "xml", "ini",
    "wtd", "wtx", "xtd", "xtx", "dds", "png", "jpg", "jpeg", "bmp",
    "wft", "wfd", "wvd", "wsi", "awc", "wav", "mp3", "ogg", "dat", "rpf", "bin", "cfg", "rel", "img",
})
RPF_NAME_PATTERN = re.compile(
    rb"[A-Za-z0-9_ ./\\\-]{1,180}\.(?:" + b"|".join(re.escape(ext.encode("ascii")) for ext in RPF_NAME_EXTENSIONS) + rb")",
    re.IGNORECASE,
)
PRINTABLE_RE = re.compile(rb"[\x20-\x7E]{4,}")


@dataclass
class ResourceRow:
    path: str
    kind: str
    ext: str
    size: int = 0
    source: str = "filesystem"
    notes: list[str] = field(default_factory=list)


@dataclass
class ScriptState:
    path: Optional[Path] = None
    resource: object | None = None
    raw: bytes = b""
    decoded: bytes = b""
    decode_ok: bool = False
    status: str = "No script loaded."
    strings: list[dict] = field(default_factory=list)
    last_report_dir: Optional[Path] = None


@dataclass
class ArchiveState:
    path: Optional[Path] = None
    rows: list[ResourceRow] = field(default_factory=list)
    status: str = "No archive loaded."


@dataclass
class LayerState:
    inputs: list[object] = field(default_factory=list)
    report: dict = field(default_factory=dict)
    report_paths: dict = field(default_factory=dict)
    status: str = "No Xbox layers loaded."


@dataclass
class IsoState:
    path: Optional[Path] = None
    report: object | None = None
    report_paths: dict = field(default_factory=dict)
    status: str = "No Xbox ISO loaded."


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def file_kind(path: Path | str) -> str:
    ext = Path(str(path).split("::")[-1]).suffix.lower()
    if ext in SCRIPT_EXTS or ext == ".wsv":
        return "Script"
    if ext in ARCHIVE_EXTS:
        return "Archive"
    if ext in TEXT_EXTS:
        return "Text"
    if ext in {".wtd", ".wtx", ".xtd", ".xtx", ".dds", ".png", ".jpg", ".jpeg", ".bmp"}:
        return "Texture"
    if ext in {".wft", ".wfd", ".wvd", ".wsi"}:
        return "Mesh"
    if ext in {".awc", ".wav", ".mp3", ".ogg"}:
        return "Audio"
    return "Other"


def bounded_hexdump(data: bytes, limit: int = MAX_PREVIEW_BYTES) -> str:
    view = data[:limit]
    lines: list[str] = []
    for offset in range(0, len(view), 16):
        chunk = view[offset:offset + 16]
        hex_part = " ".join(f"{b:02X}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
        lines.append(f"{offset:08X}  {hex_part:<47}  {ascii_part}")
    if len(data) > limit:
        lines.append(f"\n... preview truncated at {limit:,} of {len(data):,} bytes ...")
    return "\n".join(lines)


def printable_strings(data: bytes, limit: int = 1000) -> list[dict]:
    if extract_strings is not None:
        try:
            return list(extract_strings(data))[:limit]
        except Exception:
            pass
    rows = []
    for match in PRINTABLE_RE.finditer(data):
        rows.append({
            "offset": match.start(),
            "offset_hex": f"0x{match.start():X}",
            "length": len(match.group()),
            "text": match.group().decode("ascii", errors="replace"),
        })
        if len(rows) >= limit:
            break
    return rows


def is_rpf(path: Path) -> bool:
    if path.suffix.lower() != ".rpf":
        return False
    try:
        return path.read_bytes()[:4].upper().startswith(b"RPF")
    except OSError:
        return False


def scan_zip(path: Path, limit: int = 6000) -> list[ResourceRow]:
    rows: list[ResourceRow] = []
    with zipfile.ZipFile(path, "r") as zf:
        for idx, info in enumerate(zf.infolist()):
            if idx >= limit:
                rows.append(ResourceRow(f"{path}::<truncated>", "Other", "", 0, "zip", [f"member limit {limit} reached"]))
                break
            if info.is_dir():
                continue
            member = info.filename.replace("\\", "/")
            rows.append(ResourceRow(f"{path}::{member}", file_kind(member), Path(member).suffix.lower(), info.file_size, "zip", ["ZIP package member; read-only listing"]))
    return rows


def scan_rpf(path: Path, limit: int = 6000, read_limit: int = 128 * 1024 * 1024) -> list[ResourceRow]:
    if not is_rpf(path):
        return []
    try:
        with path.open("rb") as fh:
            blob = fh.read(min(path.stat().st_size, read_limit))
    except OSError as exc:
        return [ResourceRow(f"{path}::<read failed>", "Archive", ".rpf", 0, "rpf", [str(exc)])]
    rows: list[ResourceRow] = []
    seen: set[str] = set()
    for match in RPF_NAME_PATTERN.finditer(blob):
        name = match.group(0).decode("utf-8", "ignore").strip(" \t\r\n\x00").replace("\\", "/")
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        rows.append(ResourceRow(f"{path}::{name}", file_kind(name), Path(name).suffix.lower(), 0, "rpf", ["RPF member name probe; archive remains read-only"]))
        if len(rows) >= limit:
            rows.append(ResourceRow(f"{path}::<truncated>", "Other", "", 0, "rpf", [f"member limit {limit} reached"]))
            break
    if not rows:
        rows.append(ResourceRow(f"{path}::<rpf detected>", "Archive", ".rpf", path.stat().st_size, "rpf", ["RPF magic detected; no readable names found in bounded scan"]))
    return rows


def scan_archive(path: Path) -> list[ResourceRow]:
    if path.suffix.lower() == ".rpf" or is_rpf(path):
        return scan_rpf(path)
    if path.suffix.lower() == ".zip" or zipfile.is_zipfile(path):
        return scan_zip(path)
    return []


def scan_folder(path: Path, limit: int = MAX_FOLDER_FILES) -> list[ResourceRow]:
    rows: list[ResourceRow] = []
    count = 0
    for fp in sorted(path.rglob("*")):
        if not fp.is_file():
            continue
        if any(part in {".git", "__pycache__", "build", "logs", "CodeRED_Backups"} for part in fp.parts):
            continue
        try:
            rows.append(ResourceRow(str(fp), file_kind(fp), fp.suffix.lower(), fp.stat().st_size, "filesystem", []))
        except OSError as exc:
            rows.append(ResourceRow(str(fp), "Other", fp.suffix.lower(), 0, "filesystem", [str(exc)]))
        count += 1
        if count >= limit:
            rows.append(ResourceRow(str(path / "<truncated>"), "Other", "", 0, "filesystem", [f"folder limit {limit} reached"]))
            break
    return rows


def make_same_length_recipe(script_path: Path, old: str, new: str) -> str:
    before = old.encode("ascii", errors="strict")
    after = new.encode("ascii", errors="strict")
    if len(before) != len(after):
        raise ValueError("Replacement must be the same ASCII byte length as the original.")
    return "\n".join([
        "name: same_length_string_replace_from_gui",
        "description: Width-preserving string edit generated by Code RED Public Workbench.",
        "allow_unowned: false",
        "input_expected:",
        "  strings_required:",
        f"    - {json.dumps(old)}",
        "patches:",
        "  - type: same_length_string_replace",
        f"    old: {json.dumps(old)}",
        f"    new: {json.dumps(new)}",
        "    max_matches: 1",
        "",
        f"# Input: {script_path.name}",
        "# Keep this recipe public-safe. Do not include the source script file.",
    ])


def gpt_packet(script: ScriptState, archive: ArchiveState, workspace_rows: list[ResourceRow], layer_state: LayerState | None = None) -> dict:
    script_payload = {
        "path": str(script.path) if script.path else "",
        "status": script.status,
        "decode_ok": script.decode_ok,
        "raw_size": len(script.raw),
        "decoded_size": len(script.decoded),
        "raw_sha256": sha256_bytes(script.raw) if script.raw else "",
        "decoded_sha256": sha256_bytes(script.decoded) if script.decoded else "",
        "string_count": len(script.strings),
        "last_report_dir": str(script.last_report_dir) if script.last_report_dir else "",
    }
    archive_payload = {
        "path": str(archive.path) if archive.path else "",
        "status": archive.status,
        "row_count": len(archive.rows),
        "counts_by_kind": {},
    }
    counts: dict[str, int] = {}
    for row in archive.rows:
        counts[row.kind] = counts.get(row.kind, 0) + 1
    archive_payload["counts_by_kind"] = counts
    workspace_counts: dict[str, int] = {}
    for row in workspace_rows:
        workspace_counts[row.kind] = workspace_counts.get(row.kind, 0) + 1
    layer_payload = {
        "status": layer_state.status if layer_state else "No Xbox layer report.",
        "layer_count": len(layer_state.inputs) if layer_state else 0,
        "effective_file_count": (layer_state.report or {}).get("effective_file_count", 0) if layer_state else 0,
        "counts_by_status": (layer_state.report or {}).get("counts_by_status", {}) if layer_state else {},
        "focus_file_count": (layer_state.report or {}).get("focus_file_count", 0) if layer_state else 0,
        "focus_files_preview": ((layer_state.report or {}).get("focus_files", [])[:60] if layer_state else []),
        "report_paths": layer_state.report_paths if layer_state else {},
    }
    return {
        "app": APP_NAME,
        "version": APP_VERSION,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "public_safety": {
            "raw_game_files_bundled": False,
            "rpf_operations": "read-only inventory in GUI; patcher remains external/copy-first",
            "script_edits": "same-size copy output only",
            "xbox_layers": "read-only effective-tree resolver; no raw file payloads exported",
            "xiso": "read/index/extract and exact-size copy-write planning; original ISO is never modified in place",
        },
        "script": script_payload,
        "archive": archive_payload,
        "xbox_layers": layer_payload,
        "xiso": {"status": getattr(globals().get("_dummy", None), "status", "ISO state is GUI-only in this packet helper")},
        "workspace_counts": workspace_counts,
        "recommended_next_prompt_for_gpt": "Use this packet to inspect the current Code RED script/RPF/layer state. Keep public repo clean and never include raw game files.",
    }


class WorkbenchApp(tk.Tk):  # type: ignore[misc]
    """Focused Code RED front door for script/RPF work."""

    def __init__(self, startup_workspace: Optional[Path] = None):
        if tk is None or ttk is None:
            raise RuntimeError("tkinter is not available")
        super().__init__()
        self.title(f"{APP_NAME} - Script Lab + RPF Browser")
        self.geometry("1420x860")
        self.minsize(1120, 720)
        self.configure(bg=THEME["bg"])
        self.script_state = ScriptState()
        self.archive_state = ArchiveState()
        self.layer_state = LayerState()
        self.iso_state = IsoState()
        self.workspace_rows: list[ResourceRow] = []
        self.selected_row: ResourceRow | None = None
        self._setup_style()
        self._build_ui()
        self._log("Code RED public workbench ready. Main lanes: Script Lab and RPF Browser.")
        if startup_workspace and startup_workspace.exists():
            if startup_workspace.is_file():
                if startup_workspace.suffix.lower() in SCRIPT_EXTS:
                    self.open_script_path(startup_workspace)
                elif startup_workspace.suffix.lower() in ARCHIVE_EXTS:
                    self.open_archive_path(startup_workspace)
                else:
                    self.load_workspace(startup_workspace.parent)
            else:
                self.load_workspace(startup_workspace)

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("CR.TFrame", background=THEME["bg"])
        style.configure("Panel.TFrame", background=THEME["panel"], bordercolor=THEME["line"], relief="solid")
        style.configure("CR.TLabel", background=THEME["bg"], foreground=THEME["text"])
        style.configure("Panel.TLabel", background=THEME["panel"], foreground=THEME["text"])
        style.configure("Muted.TLabel", background=THEME["panel"], foreground=THEME["muted"])
        style.configure("Brand.TLabel", background=THEME["bg"], foreground=THEME["red"], font=("Segoe UI", 18, "bold"))
        style.configure("CR.TButton", background=THEME["red2"], foreground=THEME["text"], padding=(10, 7), relief="flat")
        style.map("CR.TButton", background=[("active", THEME["red"]), ("pressed", THEME["red2"])])
        style.configure("Treeview", background="#0d0505", fieldbackground="#0d0505", foreground=THEME["text"], rowheight=24)
        style.map("Treeview", background=[("selected", THEME["red2"])] , foreground=[("selected", THEME["text"])])
        style.configure("Treeview.Heading", background=THEME["red2"], foreground=THEME["text"], font=("Segoe UI", 9, "bold"))
        style.configure("TNotebook", background=THEME["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=THEME["panel2"], foreground=THEME["text"], padding=(12, 7))
        style.map("TNotebook.Tab", background=[("selected", THEME["red2"])])

    def _build_ui(self) -> None:
        root = ttk.Frame(self, style="CR.TFrame", padding=10)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)
        self._build_topbar(root)
        self._build_body(root)
        self._build_status(root)

    def _build_topbar(self, root: ttk.Frame) -> None:
        bar = ttk.Frame(root, style="CR.TFrame")
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        bar.columnconfigure(7, weight=1)
        ttk.Label(bar, text="CODE RED", style="Brand.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 20))
        actions = [
            ("Open Script", self.ask_open_script),
            ("Open RPF/ZIP", self.ask_open_archive),
            ("Open Folder", self.ask_open_folder),
            ("Inspect", self.run_script_inspect),
            ("Save Patch Copy", self.apply_same_size_copy),
            ("Export GPT Packet", self.export_gpt_packet),
        ]
        for i, (label, cmd) in enumerate(actions, start=1):
            ttk.Button(bar, text=label, command=cmd, style="CR.TButton").grid(row=0, column=i, padx=4, sticky="ew")
        self.top_summary = tk.StringVar(value="Ready")
        ttk.Label(bar, textvariable=self.top_summary, style="CR.TLabel").grid(row=0, column=7, sticky="e", padx=(12, 0))

    def _build_body(self, root: ttk.Frame) -> None:
        body = ttk.Frame(root, style="CR.TFrame")
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, minsize=330, weight=0)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        self._build_resource_rail(body)
        self._build_tabs(body)

    def _build_resource_rail(self, body: ttk.Frame) -> None:
        rail = ttk.Frame(body, style="Panel.TFrame", padding=10)
        rail.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        rail.columnconfigure(0, weight=1)
        rail.rowconfigure(3, weight=1)
        ttk.Label(rail, text="Workspace", style="Panel.TLabel", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh_workspace_tree())
        search = tk.Entry(rail, textvariable=self.search_var, bg="#0d0505", fg=THEME["text"], insertbackground=THEME["text"], relief="flat")
        search.grid(row=1, column=0, sticky="ew", pady=(8, 8), ipady=6)
        hint = "Open a folder, script, or archive. Double-click script/archive rows to load them."
        ttk.Label(rail, text=hint, style="Muted.TLabel", wraplength=285).grid(row=2, column=0, sticky="ew", pady=(0, 8))
        self.workspace_tree = ttk.Treeview(rail, columns=("kind", "ext", "size", "path"), show="headings", selectmode="browse")
        for col, title, width in [("kind", "Kind", 70), ("ext", "Ext", 55), ("size", "Size", 75), ("path", "Path", 360)]:
            self.workspace_tree.heading(col, text=title)
            self.workspace_tree.column(col, width=width, stretch=(col == "path"), anchor="w")
        self.workspace_tree.grid(row=3, column=0, sticky="nsew")
        self.workspace_tree.bind("<Double-1>", self.open_selected_workspace_row)
        self.workspace_tree.bind("<<TreeviewSelect>>", self.select_workspace_row)
        scroll = ttk.Scrollbar(rail, orient="vertical", command=self.workspace_tree.yview)
        scroll.grid(row=3, column=1, sticky="ns")
        self.workspace_tree.configure(yscrollcommand=scroll.set)

    def _build_tabs(self, body: ttk.Frame) -> None:
        self.notebook = ttk.Notebook(body)
        self.notebook.grid(row=0, column=1, sticky="nsew")
        self._build_script_tab()
        self._build_archive_tab()
        self._build_layers_tab()
        self._build_xiso_tab()
        self._build_recipe_tab()
        self._build_packet_tab()
        self._build_log_tab()

    def _make_tab(self, title: str) -> ttk.Frame:
        frame = ttk.Frame(self.notebook, style="Panel.TFrame", padding=10)
        self.notebook.add(frame, text=title)
        return frame

    def _build_script_tab(self) -> None:
        tab = self._make_tab("Script Lab")
        tab.columnconfigure(0, weight=3)
        tab.columnconfigure(1, weight=2)
        tab.rowconfigure(3, weight=1)
        self.script_path_var = tk.StringVar(value="No script loaded")
        ttk.Label(tab, textvariable=self.script_path_var, style="Panel.TLabel", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, columnspan=2, sticky="ew")
        keybar = ttk.Frame(tab, style="Panel.TFrame")
        keybar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 8))
        keybar.columnconfigure(1, weight=1)
        keybar.columnconfigure(4, weight=1)
        ttk.Label(keybar, text="AES key hex", style="Panel.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.aes_key_var = tk.StringVar(value=os.environ.get("CODERED_RDR_AES_KEY_HEX", ""))
        tk.Entry(keybar, textvariable=self.aes_key_var, bg="#0d0505", fg=THEME["text"], insertbackground=THEME["text"], relief="flat", show="*").grid(row=0, column=1, sticky="ew", padx=(0, 10), ipady=4)
        ttk.Label(keybar, text="rdr.exe", style="Panel.TLabel").grid(row=0, column=2, sticky="w", padx=(0, 6))
        self.rdr_exe_var = tk.StringVar(value=os.environ.get("CODERED_RDR_EXE", ""))
        tk.Entry(keybar, textvariable=self.rdr_exe_var, bg="#0d0505", fg=THEME["text"], insertbackground=THEME["text"], relief="flat").grid(row=0, column=3, sticky="ew", padx=(0, 6), ipady=4)
        ttk.Button(keybar, text="Browse", command=self.ask_rdr_exe, style="CR.TButton").grid(row=0, column=4, sticky="w")
        self.script_status = tk.StringVar(value="Script status will appear here.")
        ttk.Label(tab, textvariable=self.script_status, style="Muted.TLabel", wraplength=950).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        panes = ttk.Frame(tab, style="Panel.TFrame")
        panes.grid(row=3, column=0, columnspan=2, sticky="nsew")
        panes.columnconfigure(0, weight=3)
        panes.columnconfigure(1, weight=2)
        panes.rowconfigure(0, weight=1)
        preview_frame = ttk.Frame(panes, style="Panel.TFrame")
        preview_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        preview_frame.rowconfigure(0, weight=1)
        preview_frame.columnconfigure(0, weight=1)
        self.script_preview = tk.Text(preview_frame, wrap="none", bg="#0d0505", fg=THEME["text"], insertbackground=THEME["text"], relief="flat", padx=8, pady=8, font=("Consolas", 10))
        self.script_preview.grid(row=0, column=0, sticky="nsew")
        ttk.Scrollbar(preview_frame, orient="vertical", command=self.script_preview.yview).grid(row=0, column=1, sticky="ns")
        self.script_preview.configure(yscrollcommand=lambda *args: None)
        string_frame = ttk.Frame(panes, style="Panel.TFrame")
        string_frame.grid(row=0, column=1, sticky="nsew")
        string_frame.rowconfigure(1, weight=1)
        string_frame.columnconfigure(0, weight=1)
        ttk.Label(string_frame, text="Decoded / raw strings", style="Panel.TLabel", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.strings_tree = ttk.Treeview(string_frame, columns=("off", "len", "text"), show="headings", selectmode="browse")
        for col, title, width in [("off", "Offset", 80), ("len", "Len", 50), ("text", "Text", 400)]:
            self.strings_tree.heading(col, text=title)
            self.strings_tree.column(col, width=width, stretch=(col == "text"), anchor="w")
        self.strings_tree.grid(row=1, column=0, sticky="nsew")
        self.strings_tree.bind("<<TreeviewSelect>>", self.use_selected_string_as_find)
        patch = ttk.Frame(tab, style="Panel.TFrame")
        patch.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        patch.columnconfigure(1, weight=1)
        patch.columnconfigure(3, weight=1)
        ttk.Label(patch, text="Find", style="Panel.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.find_var = tk.StringVar()
        tk.Entry(patch, textvariable=self.find_var, bg="#0d0505", fg=THEME["text"], insertbackground=THEME["text"], relief="flat").grid(row=0, column=1, sticky="ew", padx=(0, 12), ipady=5)
        ttk.Label(patch, text="Replace", style="Panel.TLabel").grid(row=0, column=2, sticky="w", padx=(0, 6))
        self.replace_var = tk.StringVar()
        tk.Entry(patch, textvariable=self.replace_var, bg="#0d0505", fg=THEME["text"], insertbackground=THEME["text"], relief="flat").grid(row=0, column=3, sticky="ew", padx=(0, 12), ipady=5)
        ttk.Button(patch, text="Build Recipe", command=self.build_recipe_from_fields, style="CR.TButton").grid(row=0, column=4, padx=4)
        ttk.Button(patch, text="Refresh Decode", command=self.refresh_script_decode, style="CR.TButton").grid(row=0, column=5, padx=4)

    def _build_archive_tab(self) -> None:
        tab = self._make_tab("RPF Browser")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)
        self.archive_status = tk.StringVar(value="Open an RPF or ZIP. RPF operations here are read-only inventory/proof only.")
        ttk.Label(tab, textvariable=self.archive_status, style="Panel.TLabel", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="ew")
        ttk.Label(tab, text="Use this for discovery and reports. Actual RPF patch builds should stay copy-first through CodeRED_RPF_Patcher_Lite or Code Red Syringe.", style="Muted.TLabel", wraplength=950).grid(row=1, column=0, sticky="ew", pady=(4, 8))
        self.archive_tree = ttk.Treeview(tab, columns=("kind", "ext", "size", "source", "path"), show="headings")
        for col, title, width in [("kind", "Kind", 90), ("ext", "Ext", 70), ("size", "Size", 90), ("source", "Source", 80), ("path", "Member / Path", 800)]:
            self.archive_tree.heading(col, text=title)
            self.archive_tree.column(col, width=width, stretch=(col == "path"), anchor="w")
        self.archive_tree.grid(row=2, column=0, sticky="nsew")
        controls = ttk.Frame(tab, style="Panel.TFrame")
        controls.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(controls, text="Export Archive Report", command=self.export_archive_report, style="CR.TButton").pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="Copy Patcher Command", command=self.copy_patcher_command, style="CR.TButton").pack(side="left", padx=6)

    def _build_layers_tab(self) -> None:
        tab = self._make_tab("Xbox Layers")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(3, weight=1)
        self.layer_status = tk.StringVar(value="Add base/layer folders, ZIPs, or RPFs in priority order. Base first; highest override last.")
        ttk.Label(tab, textvariable=self.layer_status, style="Panel.TLabel", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="ew")
        ttk.Label(tab, text="This is a read-only resolver for Xbox/Xenia layered content. It tells you which path wins before you edit anything.", style="Muted.TLabel", wraplength=1050).grid(row=1, column=0, sticky="ew", pady=(4, 8))
        controls = ttk.Frame(tab, style="Panel.TFrame")
        controls.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(controls, text="Add Folder Layer", command=self.ask_add_layer_folder, style="CR.TButton").pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="Add ZIP/RPF Layer", command=self.ask_add_layer_archive, style="CR.TButton").pack(side="left", padx=6)
        ttk.Button(controls, text="Build Effective Tree", command=self.build_layer_report_from_gui, style="CR.TButton").pack(side="left", padx=6)
        ttk.Button(controls, text="Export Layer Report", command=self.export_layer_report, style="CR.TButton").pack(side="left", padx=6)
        ttk.Button(controls, text="Clear", command=self.clear_layers, style="CR.TButton").pack(side="left", padx=6)
        self.layer_tree = ttk.Treeview(tab, columns=("status", "layer", "kind", "layers", "tags", "path"), show="headings", selectmode="browse")
        for col, title, width in [("status", "Status", 160), ("layer", "Winner", 120), ("kind", "Kind", 75), ("layers", "In Layers", 170), ("tags", "Tags", 190), ("path", "Effective Path", 760)]:
            self.layer_tree.heading(col, text=title)
            self.layer_tree.column(col, width=width, stretch=(col == "path"), anchor="w")
        self.layer_tree.grid(row=3, column=0, sticky="nsew")
        self.layer_tree.bind("<Double-1>", self.copy_selected_layer_path)
        lower = ttk.Frame(tab, style="Panel.TFrame")
        lower.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        self.layer_input_text = tk.Text(lower, height=4, wrap="word", bg="#0d0505", fg=THEME["text"], insertbackground=THEME["text"], relief="flat", padx=8, pady=8, font=("Consolas", 9))
        self.layer_input_text.pack(fill="x", expand=True)
        self.refresh_layer_input_text()

    def ask_add_layer_folder(self) -> None:
        path = filedialog.askdirectory(title="Add Xbox content layer folder")
        if path:
            self.add_layer_path(Path(path))

    def ask_add_layer_archive(self) -> None:
        path = filedialog.askopenfilename(title="Add Xbox layer ZIP/RPF", filetypes=[("Layer archives", "*.zip *.rpf"), ("All files", "*.*")])
        if path:
            self.add_layer_path(Path(path))

    def add_layer_path(self, path: Path) -> None:
        if LayerInput is None:
            self._show_error("Xbox Layers", "Layer resolver module is not importable.")
            return
        name = path.stem.replace(" ", "_") or f"layer_{len(self.layer_state.inputs)}"
        if len(self.layer_state.inputs) == 0:
            name = "base_" + name
        elif "layer" not in name.lower():
            name = f"layer_{len(self.layer_state.inputs)}_{name}"
        self.layer_state.inputs.append(LayerInput(name=name, path=str(path), priority=len(self.layer_state.inputs)))
        self.layer_state.status = f"Added layer {name}: {path}"
        self.layer_status.set(self.layer_state.status)
        self.refresh_layer_input_text()
        self._log(self.layer_state.status)

    def clear_layers(self) -> None:
        self.layer_state = LayerState()
        self.layer_status.set(self.layer_state.status)
        self.refresh_layer_input_text()
        self.refresh_layer_tree()
        self.refresh_gpt_packet()
        self._log("Xbox layer list cleared.")

    def refresh_layer_input_text(self) -> None:
        if not hasattr(self, "layer_input_text"):
            return
        self.layer_input_text.delete("1.0", "end")
        if not self.layer_state.inputs:
            self.layer_input_text.insert("1.0", "No layers yet. Add base/disc first, then layer_0/update/DLC overrides.\n")
            return
        lines = []
        for item in self.layer_state.inputs:
            lines.append(f"{getattr(item, 'priority', '?')}: {getattr(item, 'name', 'layer')} = {getattr(item, 'path', '')}")
        self.layer_input_text.insert("1.0", "\n".join(lines) + "\n")

    def build_layer_report_from_gui(self) -> None:
        if analyze_layers is None:
            self._show_error("Xbox Layers", "Layer resolver module is not importable.")
            return
        if not self.layer_state.inputs:
            self._show_error("Xbox Layers", "Add at least one layer first.")
            return
        try:
            report = analyze_layers(self.layer_state.inputs)
            self.layer_state.report = report
            self.layer_state.status = f"Effective tree built: {report.get('effective_file_count', 0):,} files; {report.get('focus_file_count', 0):,} profile/init focus hits."
            self.layer_status.set(self.layer_state.status)
            self.refresh_layer_tree()
            self.refresh_gpt_packet()
            self._log(self.layer_state.status)
        except Exception as exc:
            self._show_error("Xbox Layers", str(exc))

    def refresh_layer_tree(self) -> None:
        if not hasattr(self, "layer_tree"):
            return
        for item in self.layer_tree.get_children():
            self.layer_tree.delete(item)
        report = self.layer_state.report or {}
        rows = report.get("focus_files") or report.get("effective_files") or []
        # Focus hits first; cap UI rows to keep the workbench responsive.
        for idx, row in enumerate(rows[:1800]):
            self.layer_tree.insert("", "end", iid=str(idx), values=(
                row.get("status", ""),
                row.get("effective_layer", ""),
                row.get("kind", ""),
                ";".join(row.get("present_in_layers", [])),
                ";".join(row.get("focus_tags", [])),
                row.get("norm_path", ""),
            ))

    def export_layer_report(self) -> None:
        if write_layer_reports is None:
            self._show_error("Xbox Layers", "Layer report writer is not importable.")
            return
        if not self.layer_state.report:
            self.build_layer_report_from_gui()
            if not self.layer_state.report:
                return
        out_dir = REPORT_DIR / "xbox_layer_resolver"
        try:
            self.layer_state.report_paths = write_layer_reports(self.layer_state.report, out_dir)
            self.refresh_gpt_packet()
            self._log(f"Xbox layer reports written: {out_dir}")
        except Exception as exc:
            self._show_error("Xbox Layers", str(exc))

    def copy_selected_layer_path(self, _event: object = None) -> None:
        sel = self.layer_tree.selection() if hasattr(self, "layer_tree") else []
        if not sel:
            return
        values = self.layer_tree.item(sel[0], "values")
        if not values:
            return
        path = str(values[-1])
        self.clipboard_clear()
        self.clipboard_append(path)
        self._log(f"Copied effective layer path: {path}")


    def _build_xiso_tab(self) -> None:
        tab = self._make_tab("ISO/XDVDFS")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(3, weight=1)
        self.xiso_status = tk.StringVar(value="Open an Xbox ISO to index XDVDFS files, extract RPFs, and build safe replacement plans.")
        ttk.Label(tab, textvariable=self.xiso_status, style="Panel.TLabel", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="ew")
        ttk.Label(tab, text="Copy-first Xbox/Xenia lane. Index/extract RPFs, plan safe replacement, stage exact-size padded files, or export an overlay when the edited RPF is too large.", style="Muted.TLabel", wraplength=1050).grid(row=1, column=0, sticky="ew", pady=(4, 8))
        controls = ttk.Frame(tab, style="Panel.TFrame")
        controls.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(controls, text="Open ISO", command=self.ask_open_xiso, style="CR.TButton").pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="Index ISO", command=self.index_xiso_from_gui, style="CR.TButton").pack(side="left", padx=6)
        ttk.Button(controls, text="Export ISO Report", command=self.export_xiso_report, style="CR.TButton").pack(side="left", padx=6)
        ttk.Button(controls, text="Extract Selected", command=self.extract_selected_xiso_entry, style="CR.TButton").pack(side="left", padx=6)
        ttk.Button(controls, text="Plan RPF Replace", command=self.plan_selected_xiso_replacement, style="CR.TButton").pack(side="left", padx=6)
        ttk.Button(controls, text="Stage Exact/Padded", command=self.stage_selected_xiso_replacement, style="CR.TButton").pack(side="left", padx=6)
        ttk.Button(controls, text="Export Overlay", command=self.export_selected_xiso_overlay, style="CR.TButton").pack(side="left", padx=6)
        ttk.Button(controls, text="Find Text Inside", command=self.find_text_inside_selected_xiso_entry, style="CR.TButton").pack(side="left", padx=6)
        ttk.Button(controls, text="Nested Patch Copy", command=self.nested_patch_selected_xiso_entry, style="CR.TButton").pack(side="left", padx=6)
        ttk.Button(controls, text="Copy CLI Commands", command=self.copy_xiso_commands, style="CR.TButton").pack(side="left", padx=6)
        self.xiso_tree = ttk.Treeview(tab, columns=("kind", "sector", "size", "offset", "tags", "path"), show="headings", selectmode="browse")
        for col, title, width in [("kind", "Kind", 70), ("sector", "Sector", 90), ("size", "Size", 95), ("offset", "Offset", 110), ("tags", "Tags", 210), ("path", "ISO Path", 820)]:
            self.xiso_tree.heading(col, text=title)
            self.xiso_tree.column(col, width=width, stretch=(col == "path"), anchor="w")
        self.xiso_tree.grid(row=3, column=0, sticky="nsew")
        self.xiso_tree.bind("<Double-1>", self.copy_selected_xiso_path)
        self.xiso_note = tk.Text(tab, height=5, wrap="word", bg="#0d0505", fg=THEME["text"], insertbackground=THEME["text"], relief="flat", padx=8, pady=8, font=("Consolas", 9))
        self.xiso_note.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        self.xiso_note.insert("1.0", "No ISO indexed yet. Use this to find layer_0.rpf/content.rpf/default.xex, extract the RPF, plan/stage safe replacement, or do guarded same-length nested string patches inside an RPF without changing RPF/ISO size. Larger edited RPFs should use overlay/rebuild, not ISO sector overwrite.\n")

    def ask_open_xiso(self) -> None:
        path = filedialog.askopenfilename(title="Open Xbox ISO", filetypes=[("ISO images", "*.iso"), ("All files", "*.*")])
        if path:
            self.iso_state.path = Path(path)
            self.iso_state.status = f"ISO selected: {path}"
            self.xiso_status.set(self.iso_state.status)
            self._log(self.iso_state.status)

    def index_xiso_from_gui(self) -> None:
        if build_xiso_report is None:
            self._show_error("ISO/XDVDFS", "XISO tool module is not importable.")
            return
        if not self.iso_state.path:
            self.ask_open_xiso()
            if not self.iso_state.path:
                return
        try:
            self.iso_state.report = build_xiso_report(self.iso_state.path)
            files = getattr(self.iso_state.report, "files", [])
            focus = getattr(self.iso_state.report, "focus_files", [])
            self.iso_state.status = f"ISO indexed: {len(files):,} files; {len(focus):,} focus hits."
            self.xiso_status.set(self.iso_state.status)
            self.refresh_xiso_tree()
            self.refresh_gpt_packet()
            self._log(self.iso_state.status)
        except Exception as exc:
            self._show_error("ISO/XDVDFS", str(exc))

    def refresh_xiso_tree(self) -> None:
        if not hasattr(self, "xiso_tree"):
            return
        for item in self.xiso_tree.get_children():
            self.xiso_tree.delete(item)
        report = self.iso_state.report
        if report is None:
            return
        rows = getattr(report, "focus_files", []) or getattr(report, "files", [])
        for idx, row in enumerate(rows[:2500]):
            kind = "Dir" if row.get("is_dir") else "File"
            self.xiso_tree.insert("", "end", iid=str(idx), values=(
                kind,
                row.get("sector", ""),
                row.get("size", ""),
                row.get("absolute_offset", ""),
                ";".join(row.get("tags", [])),
                row.get("path", ""),
            ))
        if hasattr(self, "xiso_note"):
            self.xiso_note.delete("1.0", "end")
            desc = getattr(report, "selected_descriptor", None)
            warnings = getattr(report, "warnings", [])
            self.xiso_note.insert("1.0", "Selected descriptor:\n" + json.dumps(desc, indent=2)[:1600] + "\nWarnings:\n" + json.dumps(warnings, indent=2)[:1200])

    def export_xiso_report(self) -> None:
        if write_xiso_reports is None:
            self._show_error("ISO/XDVDFS", "XISO report writer is not importable.")
            return
        if self.iso_state.report is None:
            self.index_xiso_from_gui()
            if self.iso_state.report is None:
                return
        out_dir = REPORT_DIR / "xiso"
        try:
            self.iso_state.report_paths = write_xiso_reports(self.iso_state.report, out_dir)
            self.refresh_gpt_packet()
            self._log(f"ISO/XDVDFS reports written: {out_dir}")
        except Exception as exc:
            self._show_error("ISO/XDVDFS", str(exc))

    def _selected_xiso_path(self) -> str:
        sel = self.xiso_tree.selection() if hasattr(self, "xiso_tree") else []
        if not sel:
            return ""
        values = self.xiso_tree.item(sel[0], "values")
        return str(values[-1]) if values else ""

    def copy_selected_xiso_path(self, _event: object = None) -> None:
        path = self._selected_xiso_path()
        if path:
            self.clipboard_clear()
            self.clipboard_append(path)
            self._log(f"Copied ISO path: {path}")

    def extract_selected_xiso_entry(self) -> None:
        if xiso_find_entry is None or xiso_extract_file is None:
            self._show_error("ISO/XDVDFS", "XISO extraction functions are not importable.")
            return
        if self.iso_state.report is None or not self.iso_state.path:
            self.index_xiso_from_gui()
            if self.iso_state.report is None or not self.iso_state.path:
                return
        path = self._selected_xiso_path()
        if not path:
            self._show_error("ISO/XDVDFS", "Select a file entry first.")
            return
        out_dir = filedialog.askdirectory(title="Choose extraction output folder")
        if not out_dir:
            return
        try:
            entry = xiso_find_entry(self.iso_state.report, path)
            out_path = Path(out_dir) / entry.path
            xiso_extract_file(self.iso_state.path, entry, out_path)
            self._log(f"Extracted ISO file: {entry.path} -> {out_path}")
        except Exception as exc:
            self._show_error("ISO/XDVDFS", str(exc))

    def _select_xiso_replacement_file(self) -> Path | None:
        path = filedialog.askopenfilename(title="Choose modified replacement file", filetypes=[("RPF/files", "*.rpf;*.*"), ("All files", "*.*")])
        return Path(path) if path else None

    def plan_selected_xiso_replacement(self) -> None:
        if xiso_find_entry is None or xiso_replacement_plan is None:
            self._show_error("ISO/XDVDFS", "XISO replacement planner is not importable.")
            return
        if self.iso_state.report is None or not self.iso_state.path:
            self.index_xiso_from_gui()
            if self.iso_state.report is None or not self.iso_state.path:
                return
        path = self._selected_xiso_path()
        if not path:
            self._show_error("ISO/XDVDFS", "Select the ISO file entry you want to replace.")
            return
        replacement = self._select_xiso_replacement_file()
        if not replacement:
            return
        try:
            entry = xiso_find_entry(self.iso_state.report, path)
            plan = xiso_replacement_plan(self.iso_state.path, entry, replacement)
            out_dir = REPORT_DIR / "xiso_replace"
            out_dir.mkdir(parents=True, exist_ok=True)
            out = out_dir / "xiso_replace_plan.json"
            out.write_text(json.dumps(plan, indent=2), encoding="utf-8")
            self.xiso_note.delete("1.0", "end")
            self.xiso_note.insert("1.0", json.dumps(plan, indent=2)[:4000])
            self._log(f"Replacement plan written: {out} | {plan.get('decision')}")
        except Exception as exc:
            self._show_error("ISO/XDVDFS", str(exc))

    def stage_selected_xiso_replacement(self) -> None:
        if xiso_find_entry is None or xiso_write_padded_replacement is None or xiso_replacement_plan is None:
            self._show_error("ISO/XDVDFS", "XISO staging functions are not importable.")
            return
        if self.iso_state.report is None or not self.iso_state.path:
            self.index_xiso_from_gui()
            if self.iso_state.report is None or not self.iso_state.path:
                return
        path = self._selected_xiso_path()
        if not path:
            self._show_error("ISO/XDVDFS", "Select the ISO file entry you want to replace.")
            return
        replacement = self._select_xiso_replacement_file()
        if not replacement:
            return
        try:
            entry = xiso_find_entry(self.iso_state.report, path)
            plan = xiso_replacement_plan(self.iso_state.path, entry, replacement)
            if not plan.get("safe_copy_write_with_padding"):
                self.xiso_note.delete("1.0", "end")
                self.xiso_note.insert("1.0", json.dumps(plan, indent=2)[:4000])
                self._show_error("ISO/XDVDFS", "Replacement is larger than the original ISO entry. Use Export Overlay or rebuild layout instead of sector overwrite.")
                return
            out_dir = REPORT_DIR / "xiso_staged_replacements"
            out_path = out_dir / (Path(entry.path).name + ".exactsize")
            info = xiso_write_padded_replacement(replacement, entry.size, out_path)
            info["plan"] = plan
            sidecar = out_path.with_suffix(out_path.suffix + ".json")
            sidecar.write_text(json.dumps(info, indent=2), encoding="utf-8")
            self.xiso_note.delete("1.0", "end")
            self.xiso_note.insert("1.0", json.dumps(info, indent=2)[:4000])
            self._log(f"Staged exact-size replacement: {out_path}")
        except Exception as exc:
            self._show_error("ISO/XDVDFS", str(exc))

    def export_selected_xiso_overlay(self) -> None:
        if xiso_find_entry is None or xiso_export_overlay is None:
            self._show_error("ISO/XDVDFS", "XISO overlay exporter is not importable.")
            return
        if self.iso_state.report is None or not self.iso_state.path:
            self.index_xiso_from_gui()
            if self.iso_state.report is None or not self.iso_state.path:
                return
        path = self._selected_xiso_path()
        if not path:
            self._show_error("ISO/XDVDFS", "Select the ISO file entry you want to replace.")
            return
        replacement = self._select_xiso_replacement_file()
        if not replacement:
            return
        out_dir = filedialog.askdirectory(title="Choose overlay output folder")
        if not out_dir:
            return
        try:
            entry = xiso_find_entry(self.iso_state.report, path)
            manifest = xiso_export_overlay(entry, replacement, Path(out_dir), iso_path=self.iso_state.path)
            self.xiso_note.delete("1.0", "end")
            self.xiso_note.insert("1.0", json.dumps(manifest, indent=2)[:4000])
            self._log(f"Xenia overlay exported: {manifest.get('overlay_file')}")
        except Exception as exc:
            self._show_error("ISO/XDVDFS", str(exc))

    def find_text_inside_selected_xiso_entry(self) -> None:
        if xiso_find_entry is None or xiso_find_pattern_in_iso_entry is None:
            self._show_error("ISO/XDVDFS", "XISO nested search functions are not importable.")
            return
        if simpledialog is None:
            self._show_error("ISO/XDVDFS", "Tk simpledialog is unavailable in this environment.")
            return
        if self.iso_state.report is None or not self.iso_state.path:
            self.index_xiso_from_gui()
            if self.iso_state.report is None or not self.iso_state.path:
                return
        path = self._selected_xiso_path()
        if not path:
            self._show_error("ISO/XDVDFS", "Select an ISO file entry first, usually layer_0.rpf or content.rpf.")
            return
        needle = simpledialog.askstring("Find Text Inside ISO Entry", "Text/bytes to search inside the selected ISO entry:")
        if not needle:
            return
        try:
            entry = xiso_find_entry(self.iso_state.report, path)
            matches = xiso_find_pattern_in_iso_entry(self.iso_state.path, entry, needle.encode("utf-8"), max_matches=50)
            result = {"container_path": entry.path, "needle": needle, "match_count": len(matches), "matches": matches}
            out_dir = REPORT_DIR / "xiso_nested"
            out_dir.mkdir(parents=True, exist_ok=True)
            out = out_dir / "nested_find_report.json"
            out.write_text(json.dumps(result, indent=2), encoding="utf-8")
            self.xiso_note.delete("1.0", "end")
            self.xiso_note.insert("1.0", json.dumps(result, indent=2)[:4000])
            self._log(f"Nested search completed in {entry.path}: {len(matches)} matches")
        except Exception as exc:
            self._show_error("ISO/XDVDFS", str(exc))

    def nested_patch_selected_xiso_entry(self) -> None:
        if xiso_find_entry is None or xiso_patch_copy_nested_same_size is None:
            self._show_error("ISO/XDVDFS", "XISO nested patch functions are not importable.")
            return
        if simpledialog is None:
            self._show_error("ISO/XDVDFS", "Tk simpledialog is unavailable in this environment.")
            return
        if self.iso_state.report is None or not self.iso_state.path:
            self.index_xiso_from_gui()
            if self.iso_state.report is None or not self.iso_state.path:
                return
        path = self._selected_xiso_path()
        if not path:
            self._show_error("ISO/XDVDFS", "Select an ISO file entry first, usually layer_0.rpf or content.rpf.")
            return
        old = simpledialog.askstring("Nested Patch Copy", "Old text to replace inside selected ISO entry. Must match exactly:")
        if old is None:
            return
        new = simpledialog.askstring("Nested Patch Copy", "New text. Must be the same byte length as old:")
        if new is None:
            return
        old_b = old.encode("utf-8")
        new_b = new.encode("utf-8")
        if len(old_b) != len(new_b):
            self._show_error("ISO/XDVDFS", f"Nested patch requires same UTF-8 byte length ({len(old_b)} != {len(new_b)}).")
            return
        out_iso = filedialog.asksaveasfilename(title="Save copied patched ISO", defaultextension=".iso", filetypes=[("ISO images", "*.iso"), ("All files", "*.*")])
        if not out_iso:
            return
        try:
            entry = xiso_find_entry(self.iso_state.report, path)
            plan = xiso_patch_copy_nested_same_size(self.iso_state.path, entry, old_b, new_b, Path(out_iso), match_index=0, max_matches=50)
            out_dir = REPORT_DIR / "xiso_nested"
            out_dir.mkdir(parents=True, exist_ok=True)
            report_path = out_dir / "nested_patch_copy_report.json"
            report_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
            self.xiso_note.delete("1.0", "end")
            self.xiso_note.insert("1.0", json.dumps(plan, indent=2)[:4000])
            self._log(f"Nested same-size patch copied ISO written: {out_iso}")
        except Exception as exc:
            self._show_error("ISO/XDVDFS", str(exc))


    def copy_xiso_commands(self) -> None:
        iso = str(self.iso_state.path) if self.iso_state.path else "<path_to_game.iso>"
        selected = self._selected_xiso_path() or "layer_0.rpf"
        commands = "\n".join([
            f"python tools\\codered_xiso_tool.py index {json.dumps(iso)} --out reports\\xiso",
            f"python tools\\codered_xiso_tool.py extract {json.dumps(iso)} --path {json.dumps(selected)} --out extracted_iso_files",
            f"python tools\\codered_xiso_tool.py plan-replace {json.dumps(iso)} --path {json.dumps(selected)} --replacement <modified_file> --out reports\\xiso_replace_plan.json",
            f"python tools\\codered_xiso_tool.py replace-copy-exact {json.dumps(iso)} --path {json.dumps(selected)} --replacement <exact_size_modified_file> --output-iso <copy_output.iso>",
        ])
        self.clipboard_clear()
        self.clipboard_append(commands)
        self._log("Copied ISO/XDVDFS CLI commands to clipboard.")

    def _build_recipe_tab(self) -> None:
        tab = self._make_tab("Recipe")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)
        ttk.Label(tab, text="Recipe Builder", style="Panel.TLabel", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.recipe_text = tk.Text(tab, wrap="none", bg="#0d0505", fg=THEME["text"], insertbackground=THEME["text"], relief="flat", padx=8, pady=8, font=("Consolas", 10))
        self.recipe_text.grid(row=1, column=0, sticky="nsew")
        bottom = ttk.Frame(tab, style="Panel.TFrame")
        bottom.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(bottom, text="Save Recipe", command=self.save_recipe, style="CR.TButton").pack(side="left", padx=(0, 6))
        ttk.Button(bottom, text="Validate Recipe", command=self.validate_recipe_text, style="CR.TButton").pack(side="left", padx=6)
        ttk.Button(bottom, text="Open Reports Folder", command=lambda: self.open_path(REPORT_DIR), style="CR.TButton").pack(side="left", padx=6)
        self._set_recipe_text("# Build a same-size string recipe from Script Lab, or paste a Code RED YAML recipe here.\n")

    def _build_packet_tab(self) -> None:
        tab = self._make_tab("GPT Packet")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)
        ttk.Label(tab, text="Compact state for GPT / users", style="Panel.TLabel", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.packet_text = tk.Text(tab, wrap="word", bg="#0d0505", fg=THEME["text"], insertbackground=THEME["text"], relief="flat", padx=8, pady=8, font=("Consolas", 10))
        self.packet_text.grid(row=1, column=0, sticky="nsew")
        ttk.Button(tab, text="Refresh Packet", command=self.refresh_gpt_packet, style="CR.TButton").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.refresh_gpt_packet()

    def _build_log_tab(self) -> None:
        tab = self._make_tab("Log")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)
        self.log_text = tk.Text(tab, wrap="word", bg="#0d0505", fg=THEME["text"], insertbackground=THEME["text"], relief="flat", padx=8, pady=8, font=("Consolas", 10))
        self.log_text.grid(row=0, column=0, sticky="nsew")

    def _build_status(self, root: ttk.Frame) -> None:
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(root, textvariable=self.status_var, style="CR.TLabel").grid(row=2, column=0, sticky="ew", pady=(8, 0))

    def _log(self, text: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        if hasattr(self, "log_text"):
            self.log_text.insert("end", f"[{stamp}] {text}\n")
            self.log_text.see("end")
        self.status_var.set(text if len(text) < 180 else text[:177] + "...")
        self.top_summary.set(text if len(text) < 80 else text[:77] + "...")

    def ask_open_script(self) -> None:
        path = filedialog.askopenfilename(title="Open WSC/XSC/CSC/SCO", filetypes=[("Script resources", "*.wsc *.xsc *.csc *.sco"), ("All files", "*.*")])
        if path:
            self.open_script_path(Path(path))

    def ask_open_archive(self) -> None:
        path = filedialog.askopenfilename(title="Open RPF or ZIP", filetypes=[("Archives", "*.rpf *.zip"), ("All files", "*.*")])
        if path:
            self.open_archive_path(Path(path))

    def ask_open_folder(self) -> None:
        path = filedialog.askdirectory(title="Open workspace folder")
        if path:
            self.load_workspace(Path(path))

    def ask_rdr_exe(self) -> None:
        path = filedialog.askopenfilename(title="Select rdr.exe", filetypes=[("RDR executable", "rdr.exe *.exe"), ("All files", "*.*")])
        if path:
            self.rdr_exe_var.set(path)

    def open_script_path(self, path: Path) -> None:
        self.script_state = ScriptState(path=path)
        self.script_path_var.set(str(path))
        self.refresh_script_decode()
        self.notebook.select(0)
        self.refresh_gpt_packet()

    def refresh_script_decode(self) -> None:
        path = self.script_state.path
        if not path:
            self._log("No script selected.")
            return
        try:
            raw = path.read_bytes()
        except OSError as exc:
            self.script_state.status = f"Read failed: {exc}"
            self.script_status.set(self.script_state.status)
            self._log(self.script_state.status)
            return
        self.script_state.raw = raw
        resource = None
        decoded = raw
        decode_ok = False
        status = "Raw preview only."
        if open_script is not None and KeyOptions is not None:
            try:
                opts = KeyOptions(aes_key_hex=self.aes_key_var.get().strip(), aes_key_file="", rdr_exe=self.rdr_exe_var.get().strip())
                resource = open_script(path, opts)
                decoded = getattr(resource, "decoded", b"") or b""
                if decoded:
                    decode_ok = True
                    status = f"Decoded script: {len(decoded):,} bytes. Header family: {getattr(getattr(resource, 'header', None), 'family', 'unknown')}"
                else:
                    status = getattr(resource, "decode_error", "Script opened but decoded payload is empty.") or "Script opened but decoded payload is empty."
            except Exception as exc:
                status = f"Decode unavailable: {exc}. Showing raw bytes."
        self.script_state.resource = resource
        self.script_state.decoded = decoded if decoded else raw
        self.script_state.decode_ok = decode_ok
        self.script_state.status = status
        self.script_state.strings = printable_strings(self.script_state.decoded)
        self.script_status.set(status)
        self.update_script_preview()
        self.update_strings_tree()
        self._log(status)
        self.refresh_gpt_packet()

    def update_script_preview(self) -> None:
        data = self.script_state.decoded or self.script_state.raw
        header = {
            "path": str(self.script_state.path) if self.script_state.path else "",
            "status": self.script_state.status,
            "raw_size": len(self.script_state.raw),
            "decoded_size": len(self.script_state.decoded),
            "raw_sha256": sha256_bytes(self.script_state.raw) if self.script_state.raw else "",
            "decoded_sha256": sha256_bytes(self.script_state.decoded) if self.script_state.decoded else "",
        }
        text = json.dumps(header, indent=2) + "\n\n" + bounded_hexdump(data)
        self.script_preview.delete("1.0", "end")
        self.script_preview.insert("1.0", text)

    def update_strings_tree(self) -> None:
        for item in self.strings_tree.get_children():
            self.strings_tree.delete(item)
        for idx, row in enumerate(self.script_state.strings[:1000]):
            text = str(row.get("text", ""))
            self.strings_tree.insert("", "end", iid=str(idx), values=(row.get("offset_hex", f"0x{row.get('offset', 0):X}"), row.get("length", len(text)), text[:240]))

    def use_selected_string_as_find(self, _event: object = None) -> None:
        sel = self.strings_tree.selection()
        if not sel:
            return
        values = self.strings_tree.item(sel[0], "values")
        if len(values) >= 3:
            self.find_var.set(str(values[2]))

    def build_recipe_from_fields(self) -> None:
        if not self.script_state.path:
            self._log("Open a script before building a recipe.")
            return
        old = self.find_var.get()
        new = self.replace_var.get()
        try:
            recipe = make_same_length_recipe(self.script_state.path, old, new)
        except Exception as exc:
            self._show_error("Recipe", str(exc))
            return
        self._set_recipe_text(recipe)
        self.notebook.select(2)
        self._log("Built same-size string recipe. Review it before applying or sharing.")

    def apply_same_size_copy(self) -> None:
        if not self.script_state.path:
            self._show_error("Save Patch Copy", "Open a script first.")
            return
        old = self.find_var.get().encode("ascii", errors="strict")
        new = self.replace_var.get().encode("ascii", errors="strict")
        if not old or len(old) != len(new):
            self._show_error("Save Patch Copy", "Find and Replace must be non-empty and the same ASCII byte length.")
            return
        data = self.script_state.decoded if self.script_state.decode_ok else self.script_state.raw
        count = data.count(old)
        if count != 1:
            self._show_error("Save Patch Copy", f"Expected exactly 1 match in {'decoded' if self.script_state.decode_ok else 'raw'} bytes, found {count}.")
            return
        out = filedialog.asksaveasfilename(
            title="Write patched copy",
            initialfile=self.script_state.path.stem + "_patched" + self.script_state.path.suffix,
            defaultextension=self.script_state.path.suffix,
        )
        if not out:
            return
        patched_decoded = data.replace(old, new, 1)
        try:
            if self.script_state.decode_ok and self.script_state.resource is not None and repack_script is not None:
                output, report = repack_script(self.script_state.resource, patched_decoded, allow_growth=False)  # type: ignore[arg-type]
                Path(out).write_bytes(output)
                Path(out + ".codered_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            else:
                Path(out).write_bytes(patched_decoded)
                Path(out + ".codered_report.json").write_text(json.dumps({"mode": "raw-same-size-copy", "sha256": sha256_bytes(patched_decoded)}, indent=2), encoding="utf-8")
            self._log(f"Wrote patched copy: {out}")
        except Exception as exc:
            self._show_error("Save Patch Copy", str(exc))

    def run_script_inspect(self) -> None:
        if not self.script_state.path:
            self._show_error("Inspect", "Open a script first.")
            return
        if not self.script_state.decode_ok or self.script_state.resource is None:
            self.refresh_script_decode()
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        out_dir = REPORT_DIR / (self.script_state.path.stem + "_inspect")
        out_dir.mkdir(parents=True, exist_ok=True)
        if self.script_state.resource is not None and self.script_state.decode_ok and write_inspect_report is not None:
            try:
                header = self.script_state.resource.header_dict()  # type: ignore[attr-defined]
                summary = write_inspect_report(out_dir, header, self.script_state.decoded)
                if write_map_report is not None:
                    try:
                        write_map_report(out_dir / "map", header, self.script_state.decoded)
                    except Exception:
                        pass
                self.script_state.last_report_dir = out_dir
                self._log(f"Inspect report written: {out_dir}")
                self.refresh_gpt_packet()
                return
            except Exception as exc:
                self._log(f"Full inspect failed; writing raw fallback report: {exc}")
        fallback = {
            "path": str(self.script_state.path),
            "status": self.script_state.status,
            "raw_size": len(self.script_state.raw),
            "decoded_size": len(self.script_state.decoded),
            "strings": self.script_state.strings[:500],
            "raw_sha256": sha256_bytes(self.script_state.raw),
            "decoded_sha256": sha256_bytes(self.script_state.decoded) if self.script_state.decoded else "",
        }
        (out_dir / "fallback_inspect.json").write_text(json.dumps(fallback, indent=2), encoding="utf-8")
        self.script_state.last_report_dir = out_dir
        self._log(f"Fallback inspect report written: {out_dir}")
        self.refresh_gpt_packet()

    def open_archive_path(self, path: Path) -> None:
        rows = scan_archive(path)
        self.archive_state = ArchiveState(path=path, rows=rows, status=f"Loaded {len(rows):,} archive entries from {path.name}.")
        self.archive_status.set(self.archive_state.status)
        self.refresh_archive_tree()
        self.notebook.select(1)
        self._log(self.archive_state.status)
        self.refresh_gpt_packet()

    def refresh_archive_tree(self) -> None:
        for item in self.archive_tree.get_children():
            self.archive_tree.delete(item)
        for idx, row in enumerate(self.archive_state.rows):
            self.archive_tree.insert("", "end", iid=str(idx), values=(row.kind, row.ext or "-", f"{row.size:,}" if row.size else "", row.source, row.path))

    def export_archive_report(self) -> None:
        if not self.archive_state.path:
            self._show_error("Archive Report", "Open an archive first.")
            return
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        out = REPORT_DIR / f"{self.archive_state.path.stem}_archive_inventory.json"
        payload = {"archive": str(self.archive_state.path), "status": self.archive_state.status, "rows": [asdict(r) for r in self.archive_state.rows]}
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self._log(f"Archive report written: {out}")

    def copy_patcher_command(self) -> None:
        text = "python CodeRED_RPF_Patcher_Lite.py --help"
        if self.archive_state.path:
            text = f"python CodeRED_RPF_Patcher_Lite.py --game-dir <your_game_folder> --mod-dir <your_patch_folder> --target-rpf {self.archive_state.path.name} --dry-run"
        self.clipboard_clear()
        self.clipboard_append(text)
        self._log("Copied copy-first patcher command template to clipboard.")

    def load_workspace(self, path: Path) -> None:
        self.workspace_rows = scan_folder(path)
        self.refresh_workspace_tree()
        self._log(f"Workspace loaded: {path} ({len(self.workspace_rows):,} files indexed)")
        self.refresh_gpt_packet()

    def refresh_workspace_tree(self) -> None:
        for item in self.workspace_tree.get_children():
            self.workspace_tree.delete(item)
        query = self.search_var.get().strip().lower() if hasattr(self, "search_var") else ""
        shown = 0
        for idx, row in enumerate(self.workspace_rows):
            hay = f"{row.kind} {row.ext} {row.path}".lower()
            if query and query not in hay:
                continue
            self.workspace_tree.insert("", "end", iid=str(idx), values=(row.kind, row.ext or "-", f"{row.size:,}" if row.size else "", row.path))
            shown += 1
            if shown >= 1500:
                break

    def select_workspace_row(self, _event: object = None) -> None:
        sel = self.workspace_tree.selection()
        if not sel:
            self.selected_row = None
            return
        try:
            self.selected_row = self.workspace_rows[int(sel[0])]
        except Exception:
            self.selected_row = None

    def open_selected_workspace_row(self, _event: object = None) -> None:
        self.select_workspace_row()
        row = self.selected_row
        if not row:
            return
        path = Path(row.path)
        if row.kind == "Script" and path.exists():
            self.open_script_path(path)
        elif row.kind == "Archive" and path.exists():
            self.open_archive_path(path)
        else:
            self._log(f"Selected {row.kind}: {row.path}")

    def _set_recipe_text(self, text: str) -> None:
        self.recipe_text.delete("1.0", "end")
        self.recipe_text.insert("1.0", text)

    def save_recipe(self) -> None:
        out = filedialog.asksaveasfilename(title="Save recipe", defaultextension=".yaml", filetypes=[("YAML", "*.yaml *.yml"), ("All files", "*.*")])
        if not out:
            return
        Path(out).write_text(self.recipe_text.get("1.0", "end").strip() + "\n", encoding="utf-8")
        self._log(f"Recipe saved: {out}")

    def validate_recipe_text(self) -> None:
        text = self.recipe_text.get("1.0", "end").strip()
        if not text:
            self._show_error("Recipe", "Recipe text is empty.")
            return
        required = ["patches:", "type:"]
        missing = [item for item in required if item not in text]
        if missing:
            self._show_error("Recipe", f"Recipe appears incomplete. Missing: {', '.join(missing)}")
            return
        if "same_length_string_replace" in text:
            self._log("Recipe basic validation passed for same_length_string_replace. Run the CLI patch dry-run for full validation.")
        else:
            self._log("Recipe has patch entries. Use python -m codered_wsc recipe <file> for full validation.")

    def refresh_gpt_packet(self) -> None:
        packet = gpt_packet(self.script_state, self.archive_state, self.workspace_rows, self.layer_state)
        if hasattr(self, "packet_text"):
            self.packet_text.delete("1.0", "end")
            self.packet_text.insert("1.0", json.dumps(packet, indent=2))

    def export_gpt_packet(self) -> None:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        packet = gpt_packet(self.script_state, self.archive_state, self.workspace_rows, self.layer_state)
        out = REPORT_DIR / "Code_RED_GPT_packet.json"
        out.write_text(json.dumps(packet, indent=2), encoding="utf-8")
        self.refresh_gpt_packet()
        self._log(f"GPT packet exported: {out}")

    def open_path(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True) if path.suffix == "" else None
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            self._log(f"Could not open path: {exc}")

    def _show_error(self, title: str, text: str) -> None:
        self._log(f"{title}: {text}")
        if messagebox is not None:
            messagebox.showerror(title, text)


def self_test() -> dict:
    checks = {
        "app": APP_NAME,
        "version": APP_VERSION,
        "top_level_action_count": 6,
        "main_tabs": ["Script Lab", "RPF Browser", "Xbox Layers", "ISO/XDVDFS", "Recipe", "GPT Packet", "Log"],
        "script_exts": sorted(SCRIPT_EXTS),
        "archive_exts": sorted(ARCHIVE_EXTS),
        "codered_wsc_importable": open_script is not None,
        "rpf_scanner_pattern_ready": bool(RPF_NAME_PATTERN.pattern),
        "xbox_layer_resolver_importable": analyze_layers is not None,
        "xiso_tool_importable": build_xiso_report is not None,
        "public_safety_mode": "copy-first/read-only archive/layer/ISO resolver",
    }
    checks["ok"] = checks["top_level_action_count"] <= 6 and checks["codered_wsc_importable"] and checks["xbox_layer_resolver_importable"] and checks["xiso_tool_importable"]
    return checks


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Launch Code RED public script/RPF workbench.")
    parser.add_argument("path", nargs="?", help="Optional startup script, archive, or workspace folder.")
    parser.add_argument("--self-test", action="store_true", help="Run non-GUI sanity checks and exit.")
    parser.add_argument("--scan-archive", help="Print read-only archive inventory JSON and exit.")
    parser.add_argument("--xbox-layer", action="append", default=[], help="Read-only Xbox layer resolver input as name=path. Repeat base first, overrides last.")
    parser.add_argument("--xbox-layer-out", default=str(REPORT_DIR / "xbox_layer_cli"), help="Output folder for --xbox-layer reports.")
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.self_test:
        payload = self_test()
        print(json.dumps(payload, indent=2))
        return 0 if payload.get("ok") else 1
    if args.scan_archive:
        rows = scan_archive(Path(args.scan_archive))
        print(json.dumps([asdict(r) for r in rows], indent=2))
        return 0 if rows else 1
    if args.xbox_layer:
        if LayerInput is None or analyze_layers is None or write_layer_reports is None:
            print("Xbox layer resolver module is not available.", file=sys.stderr)
            return 2
        layer_inputs = []
        for idx, value in enumerate(args.xbox_layer):
            if "=" in value:
                name, raw_path = value.split("=", 1)
            else:
                raw_path = value
                name = Path(value).stem or f"layer_{idx}"
            layer_inputs.append(LayerInput(name=name.strip(), path=raw_path.strip(), priority=idx))
        report = analyze_layers(layer_inputs)
        paths = write_layer_reports(report, Path(args.xbox_layer_out))
        print(json.dumps({"ok": True, "report_paths": paths, "summary": {"effective_file_count": report.get("effective_file_count"), "focus_file_count": report.get("focus_file_count"), "counts_by_status": report.get("counts_by_status", {})}}, indent=2))
        return 0
    if tk is None:
        print("tkinter is not available in this runtime.", file=sys.stderr)
        return 2
    startup = Path(args.path) if args.path else None
    app = WorkbenchApp(startup_workspace=startup)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
