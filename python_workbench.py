from __future__ import annotations

import ast
import argparse
import csv
import io
import json
import os
import re
import shutil
import struct
import zipfile
import subprocess
import sys
import tempfile
import traceback
import zlib
from dataclasses import dataclass
from collections import Counter
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    _HAVE_CRYPTO = True
except Exception:
    Cipher = algorithms = modes = default_backend = None
    _HAVE_CRYPTO = False

try:
    from PIL import Image, ImageOps, ImageTk
    _HAVE_PIL = True
except Exception:
    Image = ImageOps = ImageTk = None
    _HAVE_PIL = False

try:
    import numpy as np
    _HAVE_NUMPY = True
except Exception:
    np = None
    _HAVE_NUMPY = False

try:
    import zstandard as _zstd
    _HAVE_ZSTD = True
except Exception:
    _zstd = None
    _HAVE_ZSTD = False

try:
    import matplotlib
    matplotlib.use('TkAgg')
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    _HAVE_MPL = True
except Exception:
    Figure = FigureCanvasTkAgg = NavigationToolbar2Tk = None
    _HAVE_MPL = False

IMAGE_MAGICK_BIN = shutil.which('magick') or shutil.which('convert')


SOURCE_CODE_EXTENSIONS = ('.c', '.cs', '.h', '.hpp', '.hh', '.cpp', '.cc', '.cxx', '.py', '.lua')
SCRIPT_BINARY_EXTENSIONS = ('.wsc', '.xsc', '.sco')


def _codered_is_code_bearing_extension(suffix: str) -> bool:
    return suffix.lower() in SOURCE_CODE_EXTENSIONS


def _codered_source_language_for_suffix(suffix: str) -> str:
    suffix = suffix.lower()
    if suffix == '.c':
        return 'C source'
    if suffix == '.cs':
        return 'C# source'
    if suffix in {'.h', '.hpp', '.hh'}:
        return 'C/C++ header'
    if suffix in {'.cpp', '.cc', '.cxx'}:
        return 'C++ source'
    if suffix == '.py':
        return 'Python source'
    if suffix == '.lua':
        return 'Lua source'
    return 'Source code'


def _codered_detect_source_validation_tooling() -> dict:
    c_compiler = shutil.which('clang') or shutil.which('gcc') or shutil.which('cc')
    cpp_compiler = shutil.which('clang++') or shutil.which('g++') or shutil.which('c++') or c_compiler
    cs_compiler = shutil.which('csc') or shutil.which('mcs')
    dotnet = shutil.which('dotnet')
    return {
        'c_compiler': c_compiler,
        'cpp_compiler': cpp_compiler,
        'cs_compiler': cs_compiler,
        'dotnet': dotnet,
    }


def _codered_source_probe_include_dirs(path: Path) -> List[Path]:
    candidates: List[Path] = []
    seen: set[str] = set()

    def add(candidate: Path) -> None:
        try:
            resolved = str(candidate.resolve())
        except Exception:
            resolved = str(candidate)
        if resolved in seen or not candidate.exists() or not candidate.is_dir():
            return
        seen.add(resolved)
        candidates.append(candidate)

    add(path.parent)
    for base in [path.parent, *list(path.parents)[:6]]:
        add(base)
        for name in ('include', 'Include', 'inc', 'Inc'):
            add(base / name)
    return candidates


def _codered_run_compile_probe(command: List[str], cwd: Path) -> tuple[bool, str]:
    try:
        result = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True, timeout=20, check=False)
    except Exception as exc:
        return False, f'Probe launch failed: {exc}'
    merged = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part).strip()
    if merged:
        merged = "\n".join(merged.splitlines()[:12])
    return result.returncode == 0, merged


def _codered_probe_native_source(path: Path, suffix: str) -> dict:
    tooling = _codered_detect_source_validation_tooling()
    c_family = {'.c', '.h'}
    cpp_family = {'.cpp', '.cc', '.cxx', '.hpp', '.hh'}
    if suffix in c_family:
        compiler = tooling.get('c_compiler')
        family = 'C'
    elif suffix in cpp_family:
        compiler = tooling.get('cpp_compiler')
        family = 'C++'
    elif suffix == '.cs':
        compiler = tooling.get('cs_compiler')
        family = 'C#'
    else:
        return {'available': False, 'ok': False, 'tool_name': '', 'status': 'No compile-aware probe is wired for this source family yet.'}

    if suffix == '.cs' and compiler is None and tooling.get('dotnet'):
        return {'available': False, 'ok': False, 'tool_name': 'dotnet', 'status': 'dotnet is present, but direct single-file C# validation is not wired yet in this build.'}
    if compiler is None:
        return {'available': False, 'ok': False, 'tool_name': '', 'status': f'No {family} compiler probe is available in this runtime. The file remains editable but not compile-proven here.'}

    include_dirs = _codered_source_probe_include_dirs(path)
    temp_dir = None
    command: List[str] = [compiler]
    try:
        if suffix in {'.c', '.cpp', '.cc', '.cxx'}:
            command.extend(['-fsyntax-only', str(path)])
        elif suffix == '.cs':
            command.extend(['-nologo', '-target:library', str(path)])
        elif suffix in {'.h', '.hpp', '.hh'}:
            temp_dir = tempfile.TemporaryDirectory(prefix='codered_header_probe_')
            wrapper_suffix = '.cpp' if suffix in {'.hpp', '.hh'} else '.c'
            compile_target = Path(temp_dir.name) / f'header_probe{wrapper_suffix}'
            include_target = str(path).replace("\\", "/").replace('"', '\"')
            compile_target.write_text(f'#include "{include_target}"\nint main(void){{return 0;}}\n', encoding='utf-8')
            command.extend(['-fsyntax-only', str(compile_target)])
        if suffix in c_family | cpp_family:
            for inc in include_dirs:
                command.extend(['-I', str(inc)])
        ok, output = _codered_run_compile_probe(command, path.parent)
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()
    tool_name = Path(compiler).name
    if ok:
        return {'available': True, 'ok': True, 'tool_name': tool_name, 'status': f'{family} compile probe passed via {tool_name}.'}
    detail = f'\n{output}' if output else ''
    return {'available': True, 'ok': False, 'tool_name': tool_name, 'status': f'{family} compile probe failed via {tool_name}.{detail}'}


def _codered_analyze_source_text(path: Path, text: str) -> dict:
    suffix = path.suffix.lower()
    lines = text.splitlines()
    line_count = len(lines)
    non_empty_lines = sum(1 for line in lines if line.strip())
    proof_level = 'text-only'
    syntax_status = 'No syntax-aware parser is wired for this source family yet.'
    syntax_ok = False
    syntax_error = ''
    tool_name = ''
    if suffix == '.py':
        try:
            ast.parse(text)
            proof_level = 'syntax-aware'
            syntax_status = 'Python AST parse passed.'
            syntax_ok = True
            tool_name = 'ast'
        except SyntaxError as exc:
            syntax_status = f'Python AST parse failed at line {exc.lineno}, column {exc.offset}: {exc.msg}'
            syntax_error = syntax_status
            tool_name = 'ast'
    elif suffix in {'.c', '.cpp', '.cc', '.cxx', '.cs', '.h', '.hpp', '.hh'}:
        probe = _codered_probe_native_source(path, suffix)
        tool_name = probe.get('tool_name', '')
        syntax_status = probe['status']
        if probe.get('available'):
            proof_level = 'compile-aware'
            syntax_ok = bool(probe.get('ok'))
            if not syntax_ok:
                syntax_error = syntax_status
    elif suffix == '.lua':
        syntax_status = 'Lua source is editable here, but no luac-style probe is available in this runtime yet.'
    return {
        'language': _codered_source_language_for_suffix(suffix),
        'proof_level': proof_level,
        'syntax_ok': syntax_ok,
        'syntax_status': syntax_status,
        'syntax_error': syntax_error,
        'tool_name': tool_name,
        'line_count': line_count,
        'non_empty_lines': non_empty_lines,
        'char_count': len(text),
    }



CODERED_APP_ROOT = Path(__file__).resolve().parent


def _codered_detect_companion_root() -> Path:
    candidates = [
        CODERED_APP_ROOT / 'related_apps' / 'Code_RED_MP_Companion_v19',
        CODERED_APP_ROOT / 'data' / 'Code_RED_MP_Companion_v19',
        CODERED_APP_ROOT / 'Code_RED_MP_Companion_v19',
        CODERED_APP_ROOT.parent / 'Code_RED_MP_Companion_v19',
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


CODERED_COMPANION_ROOT = _codered_detect_companion_root()
CODERED_COMPANION_CONFIG = CODERED_COMPANION_ROOT / 'config'
CODERED_COMPANION_SYNC_PATH = CODERED_COMPANION_CONFIG / 'workbench_sync.json'
CODERED_COMPANION_SCRIPT = CODERED_COMPANION_ROOT / 'mp_companion.py'
CODERED_WORKBENCH_CRASH_DIR = CODERED_APP_ROOT / 'logs'

CODERED_PRIMARY_ARCHIVE_CANDIDATES = [
    CODERED_APP_ROOT / 'content.rpf',
    CODERED_APP_ROOT / 'imports' / 'content.rpf',
    CODERED_APP_ROOT / 'game' / 'content.rpf',
]
CODERED_PRIMARY_ARCHIVE = next((p for p in CODERED_PRIMARY_ARCHIVE_CANDIDATES if p.exists()), CODERED_PRIMARY_ARCHIVE_CANDIDATES[0])

CODERED_SCAN_SKIP_DIR_NAMES = {
    '.git', '.hg', '.svn', '.vs', '__pycache__', '.pytest_cache', '.mypy_cache',
    'node_modules', 'dist', 'build', 'Build', 'Debug', 'Release', 'x64', 'x86',
    'ipch', '.idea', '.vscode',
}
CODERED_SCAN_SKIP_FILE_SUFFIXES = {'.pyc', '.pyo', '.pch', '.pdb', '.ipdb', '.iobj', '.vsidx', '.suo', '.vc.db'}
CODERED_SCAN_MAX_COUNT_FILES = int(os.environ.get('CODERED_SCAN_MAX_COUNT_FILES', '12000'))
CODERED_TREE_MAX_NODES = int(os.environ.get('CODERED_TREE_MAX_NODES', '3500'))


def _codered_should_skip_scan_dir(path: Path) -> bool:
    name = path.name
    if name in CODERED_SCAN_SKIP_DIR_NAMES:
        return True
    lower = name.lower()
    return lower in {'.git', '.vs', '__pycache__', 'node_modules', 'dist', 'build', 'debug', 'release', 'x64', 'x86', 'ipch'}


def _codered_should_skip_scan_file(path: Path) -> bool:
    suffix = path.suffix.lower()
    if suffix in CODERED_SCAN_SKIP_FILE_SUFFIXES:
        return True
    name = path.name.lower()
    if name.endswith('.vc.db') or name.endswith('.browse.vc.db'):
        return True
    return False

for folder in (CODERED_APP_ROOT / 'imports', CODERED_APP_ROOT / 'game', CODERED_APP_ROOT / 'logs', CODERED_APP_ROOT / 'combine updates'):
    folder.mkdir(parents=True, exist_ok=True)


def _codered_copy_tree_or_file(src: Path, dest: Path) -> None:
    if src.is_dir():
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


def _codered_read_json_quiet(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _codered_human_size(num_bytes: int) -> str:
    value = float(max(0, int(num_bytes)))
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if value < 1024.0 or unit == 'TB':
            return f'{value:.0f} {unit}' if unit == 'B' else f'{value:.1f} {unit}'
        value /= 1024.0
    return f'{value:.1f} TB'


def _codered_open_path_in_os(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f'Path does not exist: {path}')
    if sys.platform.startswith('win') and hasattr(os, 'startfile'):
        os.startfile(str(path))
        return f'Opened in file browser: {path}'
    for candidate in (['xdg-open', str(path)], ['open', str(path)]):
        exe = shutil.which(candidate[0])
        if exe is None:
            continue
        subprocess.Popen([exe, candidate[1]])
        return f'Opened in file browser: {path}'
    raise RuntimeError(f'No file browser opener was available for: {path}')


def _codered_bundled_demo_archive_candidates() -> List[Path]:
    root = CODERED_COMPANION_ROOT / 'hotswap' / 'staged' / 'content.rpf'
    if not root.exists():
        return []
    candidates = sorted(root.glob('*.rpf'), key=lambda item: item.stat().st_mtime, reverse=True)
    return candidates


def _codered_latest_bundled_demo_archive() -> Optional[Path]:
    candidates = _codered_bundled_demo_archive_candidates()
    return candidates[0] if candidates else None


def _codered_stage_demo_archive(workspace_root: Path, source_archive: Optional[Path] = None) -> Path:
    source = source_archive or _codered_latest_bundled_demo_archive()
    if source is None or not source.exists():
        raise FileNotFoundError('No bundled demo content.rpf was found in the staged companion resources.')
    target = workspace_root / 'imports' / 'content.rpf'
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target


def _codered_latest_archive_proof_summary_path(workspace_root: Optional[Path]) -> Optional[Path]:
    root = workspace_root if workspace_root and workspace_root.exists() else CODERED_APP_ROOT
    candidate = root / 'logs' / 'code_red_archive_proof_latest.md'
    return candidate if candidate.exists() else None


def _codered_collect_workspace_counts(workspace: Optional[Path]) -> dict:
    counts = {'files': 0, 'dirs': 0, 'bytes': 0, 'archives': 0, 'scripts': 0, 'code': 0, 'textures': 0, 'models': 0, 'audio': 0, 'skipped_dirs': 0, 'skipped_files': 0, 'truncated': False}
    if workspace is None or not workspace.exists():
        return counts
    archive_exts = {'.rpf', '.zip', '.img'}
    texture_exts = {'.dds', '.png', '.jpg', '.jpeg', '.tga', '.bmp'}
    model_exts = {'.wft', '.wtd', '.ytd', '.ydr', '.ydd', '.obj', '.fbx', '.glb', '.gltf'}
    audio_exts = {'.awc', '.wav', '.ogg', '.mp3'}
    max_files = max(250, int(CODERED_SCAN_MAX_COUNT_FILES))
    for current_root, dirnames, filenames in os.walk(workspace):
        kept_dirs = []
        for dirname in dirnames:
            child_dir = Path(current_root) / dirname
            if _codered_should_skip_scan_dir(child_dir):
                counts['skipped_dirs'] += 1
                continue
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs
        counts['dirs'] += len(kept_dirs)
        for filename in filenames:
            path = Path(current_root) / filename
            if _codered_should_skip_scan_file(path):
                counts['skipped_files'] += 1
                continue
            counts['files'] += 1
            suffix = path.suffix.lower()
            if suffix in archive_exts:
                counts['archives'] += 1
            if suffix in SCRIPT_BINARY_EXTENSIONS:
                counts['scripts'] += 1
            if suffix in SOURCE_CODE_EXTENSIONS:
                counts['code'] += 1
            if suffix in texture_exts:
                counts['textures'] += 1
            if suffix in model_exts:
                counts['models'] += 1
            if suffix in audio_exts:
                counts['audio'] += 1
            try:
                counts['bytes'] += path.stat().st_size
            except Exception:
                pass
            if counts['files'] >= max_files:
                counts['truncated'] = True
                dirnames[:] = []
                break
        if counts['truncated']:
            break
    return counts


def _codered_stage_action_lines(workspace_root: Path, primary_archive: Optional[Path]) -> List[str]:
    imports_dir = workspace_root / 'imports'
    logs_dir = workspace_root / 'logs'
    bundled_demo = _codered_latest_bundled_demo_archive()
    latest_proof = _codered_latest_archive_proof_summary_path(workspace_root)
    lines = [f'- Imports folder: {imports_dir}', f'- Logs folder: {logs_dir}']
    if primary_archive is not None:
        lines.append(f'- Primary archive target staged: {primary_archive}')
        lines.append('- Next real proof step: run Archive audit or Run Archive Proof Pass on that staged archive.')
    else:
        lines.append(f'- Expected archive drop path: {imports_dir / "content.rpf"}')
        if bundled_demo is not None:
            lines.append(f'- Bundled demo archive available now: {bundled_demo}')
            lines.append('- Fastest path: use Stage Bundled Archive, then Run Archive Proof Pass.')
    lines.append(f'- Latest archive proof report: {latest_proof if latest_proof else "not run yet"}')
    return lines


def _codered_build_stage_report(workspace: Optional[Path] = None) -> dict:
    workspace_root = workspace if workspace and workspace.exists() else CODERED_APP_ROOT
    tooling = _codered_detect_script_resource_tooling()
    source_tooling = _codered_detect_source_validation_tooling()
    counts = _codered_collect_workspace_counts(workspace_root)
    archive_candidates = [workspace_root / 'imports' / 'content.rpf', workspace_root / 'game' / 'content.rpf', workspace_root / 'content.rpf']
    primary_archive = next((candidate for candidate in archive_candidates if candidate.exists()), None)
    bundled_demo = _codered_latest_bundled_demo_archive()
    latest_proof_md = _codered_latest_archive_proof_summary_path(workspace_root)
    latest_proof = _codered_read_json_quiet(latest_proof_md.with_suffix('.json')) if latest_proof_md else {}
    archive_proof_ok = bool(latest_proof.get('ok'))
    lanes = [
        ('Python fallback UI', True, 'WorkbenchApp boots and the main interface is live in this branch.'),
        ('Archive inventory/export', True, 'RPF6 parse, inventory, export, and archive-copy patching are wired in the Python runner.'),
        ('Archive proof pass', archive_proof_ok, 'Latest copied-archive proof report passes on a real content.rpf.' if archive_proof_ok else 'A copied-archive proof pass has not been completed yet in this workspace.'),
        ('Source file editing', True, 'Code-bearing text files can be reviewed and edited directly.'),
        ('Source validation probes', bool(source_tooling.get('c_compiler') or source_tooling.get('cpp_compiler') or source_tooling.get('cs_compiler')), 'Host-native C/C++/C# validation probes are available for at least part of the helper-source lane.'),
        ('MP companion handoff', CODERED_COMPANION_SCRIPT.exists(), f'Bundled companion path: {CODERED_COMPANION_SCRIPT}'),
        ('Script compile-back', tooling.get('compile_state') == 'available', 'Compiler-backed rebuild remains Windows-first and depends on SC-CL availability.'),
        ('Rebuild-proven existing game scripts', False, 'Existing binary scripts are still not rebuild-proven end-to-end.'),
    ]
    ready_count = sum(1 for _, ok, _ in lanes if ok)
    score = int(round((ready_count / len(lanes)) * 100)) if lanes else 0
    lines = [
        'Code RED Stage Report',
        '=====================',
        '',
        f'Overall readiness snapshot: {score}% of the currently tracked lanes are directly usable in this packaged fallback build.',
        '',
        'Live branch',
        f'- Python fallback runner: {CODERED_APP_ROOT / "main.py"}',
        f'- Workspace root: {workspace_root}',
        f'- Primary archive target: {primary_archive if primary_archive else "not staged yet"}',
        f'- Bundled demo archive: {bundled_demo if bundled_demo else "not found"}',
        f'- Latest archive proof: {latest_proof_md if latest_proof_md else "not run yet"}',
        f'- MP Companion: {CODERED_COMPANION_SCRIPT if CODERED_COMPANION_SCRIPT.exists() else "missing"}',
        '',
        'Workspace footprint',
        f"- Files: {counts['files']:,}",
        f"- Folders: {counts['dirs']:,}",
        f"- Size: {_codered_human_size(counts['bytes'])}",
        f"- Archives: {counts['archives']:,}",
        f"- Code-bearing files: {counts['code']:,}",
        f"- Compiled scripts: {counts['scripts']:,}",
        f"- Skipped generated/cache folders: {counts.get('skipped_dirs', 0):,}",
        f"- Skipped generated/cache files: {counts.get('skipped_files', 0):,}",
        f"- Scan capped: {'yes' if counts.get('truncated') else 'no'}",
        '',
        'Lane status',
    ]
    for label, ok, note in lanes:
        lines.append(f"- [{'READY' if ok else 'PARTIAL'}] {label}: {note}")
    lines.extend([
        '',
        'Host source-validation tooling',
        f"- C compiler probe: {source_tooling.get('c_compiler') or 'missing'}",
        f"- C++ compiler probe: {source_tooling.get('cpp_compiler') or 'missing'}",
        f"- C# compiler probe: {source_tooling.get('cs_compiler') or 'missing'}",
        f"- dotnet host: {source_tooling.get('dotnet') or 'missing'}",
        '',
        'Bundled script tooling',
        f"- Compile state: {tooling.get('compile_state', 'missing')}",
        f"- SC-CL compiler detected: {'yes' if tooling.get('compiler_path') else 'no'}",
        f"- Magic-RDR staged: {'yes' if tooling.get('magic_rdr_exe') else 'no'}",
        '',
        'Most doable next',
        '- 1. Use Stage Bundled Archive or drop a real content.rpf, then run Archive Proof Pass.',
        '- 2. Use the Source lane to validate C/C++ helper files with the host compiler probes now available in this runtime.',
        '- 3. Keep tightening guided one-click actions for imports, logs, and the primary archive target.',
        '',
        'Actionable staging',
    ])
    lines.extend(_codered_stage_action_lines(workspace_root, primary_archive))
    return {'score': score, 'primary_archive': primary_archive, 'text': '\n'.join(lines), 'lines': lines}


def _codered_build_completion_report(workspace: Optional[Path] = None) -> dict:
    stage = _codered_build_stage_report(workspace)
    source_tooling = _codered_detect_source_validation_tooling()
    native_probe_state = 'usable now' if (source_tooling.get('c_compiler') or source_tooling.get('cpp_compiler') or source_tooling.get('cs_compiler')) else 'partial'
    proof_rows = [
        ('Archive inventory/export', 'usable now', 'Audit/export and copied-archive patching are wired in the fallback runner.'),
        ('Archive proof pass', 'usable now' if _codered_latest_archive_proof_summary_path(workspace if workspace and workspace.exists() else CODERED_APP_ROOT) else 'partial', 'Run the included archive proof pass to stage a demo content.rpf and verify copied patch apply on real archive data.'),
        ('Safe text editing', 'usable now', 'Direct review/edit of safe text-based files is available now.'),
        ('Source validation', native_probe_state, 'Native helper validation probes are available for part of the C/C++/C# lane in this runtime.' if native_probe_state == 'usable now' else 'Python remains syntax-aware, but native helper compile probes are not available yet in this runtime.'),
        ('Compiled script rebuild', 'partial', 'Requires SC-CL/Magic-RDR lane staged and end-to-end rebuilt output proof.'),
        ('MP bridge handoff', 'usable now', 'Still needs a game-side consumer that reacts to the bridge in-engine.'),
        ('Full completion', 'not yet', 'Requires live archive proof, rebuild proof, and in-engine proof together.'),
    ]
    lines = [
        'Code RED Completion Planner',
        '===========================',
        '',
        f"Current readiness snapshot: {stage['score']}%.",
        '',
        'What is most doable right now',
        '1. Use Stage Bundled Archive or drop a real content.rpf, then run Archive Proof Pass.',
        '2. Use the Source lane on C/C++ helper files to see compile-aware probe results where host compilers are available.',
        '3. Keep using guided file actions to move directly between imports, logs, and the primary archive target.',
        '',
        'Proof-state matrix',
    ]
    for label, state, gate in proof_rows:
        lines.append(f'- {label}: {state} -> {gate}')
    lines.extend(['', 'Actionable paths'])
    lines.extend(_codered_stage_action_lines(workspace if workspace and workspace.exists() else CODERED_APP_ROOT, stage.get('primary_archive')))
    return {'text': '\n'.join(lines), 'lines': lines, 'stage': stage}


def _codered_run_archive_proof_pass(workspace_root: Path, archive_path: Optional[Path] = None) -> dict:
    root = workspace_root if workspace_root.exists() else CODERED_APP_ROOT
    logs_root = root / 'logs' / 'archive_proof'
    logs_root.mkdir(parents=True, exist_ok=True)
    source_archive = archive_path
    staged_from_demo = False
    if source_archive is None or not source_archive.exists():
        for candidate in (root / 'imports' / 'content.rpf', root / 'game' / 'content.rpf', root / 'content.rpf'):
            if candidate.exists():
                source_archive = candidate
                break
    if source_archive is None or not source_archive.exists():
        demo = _codered_latest_bundled_demo_archive()
        if demo is None or not demo.exists():
            raise FileNotFoundError('No real content.rpf is staged and no bundled demo archive is available.')
        source_archive = _codered_stage_demo_archive(root, demo)
        staged_from_demo = True
    patch_root = CODERED_COMPANION_ROOT / 'patches' / '_runtime' / 'content.rpf'
    stamp = __import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')
    run_root = logs_root / f'archive_proof_{stamp}'
    run_root.mkdir(parents=True, exist_ok=True)
    audit = audit_rpf6_archive(source_archive, include_hashes=False, include_extract=False)
    patch_result = _codered_apply_patch_folder_to_archive_copy(source_archive, patch_root, output_archive=run_root / f'{source_archive.stem}__patched_copy{source_archive.suffix}')
    ok = bool(audit) and int(patch_result.get('blocked') or 0) == 0
    summary = {
        'ok': ok,
        'archive_path': str(source_archive),
        'staged_from_demo': staged_from_demo,
        'patch_root': str(patch_root),
        'audit_counts': {
            'file_count': int((audit or {}).get('file_count') or 0),
            'script_entry_count': int((audit or {}).get('script_entry_count') or 0),
            'code_entry_count': int((audit or {}).get('code_entry_count') or 0),
            'extract_success': int((audit or {}).get('extract_success') or 0),
            'extract_fail': int((audit or {}).get('extract_fail') or 0),
        },
        'applied': int(patch_result.get('applied') or 0),
        'blocked': int(patch_result.get('blocked') or 0),
        'relocated': int(patch_result.get('relocated') or 0),
        'identical': int(patch_result.get('identical') or 0),
        'working_copy': str(patch_result.get('working_copy') or ''),
        'report_path': str(patch_result.get('report_path') or ''),
    }
    lines = [
        'Code RED Archive Proof Pass',
        '===========================',
        '',
        f"Archive: {summary['archive_path']}",
        f"Patch root: {summary['patch_root']}",
        f"Applied patches on copied archive: {summary['applied']}",
        f"Blocked: {summary['blocked']}",
        f"Relocated: {summary['relocated']}",
        f"Working copy: {summary['working_copy']}",
        '',
        f"Overall proof result: {'PASS' if ok else 'PARTIAL'}",
        '- This proves the fallback runner can patch a copied content.rpf using the bundled runtime patch folder without touching the source archive.' if ok else '- Audit or copied-archive patch proof did not fully pass in this run.',
        '- This still does not prove in-engine consumption by the live game.',
    ]
    summary_md = run_root / 'code_red_archive_proof_summary.md'
    summary_json = run_root / 'code_red_archive_proof_summary.json'
    summary_md.write_text('\n'.join(lines), encoding='utf-8')
    summary_json.write_text(json.dumps(summary, indent=2), encoding='utf-8')
    latest_md = root / 'logs' / 'code_red_archive_proof_latest.md'
    latest_json = root / 'logs' / 'code_red_archive_proof_latest.json'
    shutil.copy2(summary_md, latest_md)
    shutil.copy2(summary_json, latest_json)
    summary['summary_md'] = str(summary_md)
    summary['summary_json'] = str(summary_json)
    summary['latest_md'] = str(latest_md)
    summary['latest_json'] = str(latest_json)
    return summary


def _codered_build_script_toolchain_pack(export_root: Path, analysis: Optional[dict] = None) -> dict:
    export_root.mkdir(parents=True, exist_ok=True)
    pack_root = export_root / 'Code_RED_Script_Toolchain_Pack'
    if pack_root.exists():
        shutil.rmtree(pack_root)
    pack_root.mkdir(parents=True, exist_ok=True)
    resources_root = CODERED_APP_ROOT / 'resources'
    copy_targets = [
        ('Magic-RDR-main', resources_root / 'Magic-RDR-main'),
        ('SC-CL-master', resources_root / 'SC-CL-master'),
        ('SC-CL-Windows-Build-Kit', resources_root / 'SC-CL-Windows-Build-Kit'),
        ('Code_RED_Script_Compile_Lab_v1', resources_root / 'Code_RED_Script_Compile_Lab_v1'),
        ('Trainer 2', resources_root / 'trainers' / 'Trainer 2'),
        ('RedHook', resources_root / 'RedHook'),
        ('ScriptHookRDR', resources_root / 'ScriptHookRDR'),
    ]
    copied = []
    missing = []
    for label, src in copy_targets:
        if src.exists():
            _codered_copy_tree_or_file(src, pack_root / 'resources' / label)
            copied.append({'label': label, 'source': str(src)})
        else:
            missing.append({'label': label, 'source': str(src)})
    for rel in ['data/natives.json', 'docs/long_update_thread_z_pseudo_decompile.c.txt', 'docs/v14_script_lab_roundtrip_report.md', 'docs/MULTIPLAYER_RESTORATION_NOTES.md']:
        src = CODERED_APP_ROOT / rel
        if src.exists():
            _codered_copy_tree_or_file(src, pack_root / rel)
            copied.append({'label': rel, 'source': str(src)})
        else:
            missing.append({'label': rel, 'source': str(src)})
    analysis_summary = {}
    if analysis is not None:
        analysis_summary = {
            'path': analysis.get('path').as_posix() if analysis.get('path') else '',
            'resource': analysis.get('resource') or {},
            'payload_info': analysis.get('payload_info') or {},
            'context_tags': analysis.get('context_tags') or {},
            'native_hits': len(analysis.get('native_hits') or []),
            'strong_native_hits': len(analysis.get('strong_native_hits') or []),
            'asset_paths': len(analysis.get('asset_paths') or []),
            'gameplay_terms': len(analysis.get('gameplay_terms') or []),
        }
        script_dir = pack_root / 'script_session'
        script_dir.mkdir(parents=True, exist_ok=True)
        (script_dir / 'report.txt').write_text(analysis.get('report', ''), encoding='utf-8')
        payload = analysis.get('payload')
        if payload is not None:
            (script_dir / 'payload.bin').write_bytes(payload)
        (script_dir / 'analysis.json').write_text(json.dumps(analysis_summary, indent=2, default=str), encoding='utf-8')
    manifest = {
        'copied': copied,
        'missing': missing,
        'analysis_summary': analysis_summary,
    }
    (pack_root / 'toolchain_manifest.json').write_text(json.dumps(manifest, indent=2, default=str), encoding='utf-8')
    readme_lines = [
        'Code RED Script Toolchain Pack',
        '=============================',
        '',
        'Purpose',
        '- Stage Magic-RDR, SC-CL, donor trainer source, and Code RED compile-lab assets into one exportable toolkit.',
        '- Treat pseudo-decompile .c output as reference text only; do not assume direct compile-back is safe.',
        '',
        'Included lanes',
    ]
    for row in copied:
        readme_lines.append(f"- {row['label']}")
    if missing:
        readme_lines.extend(['', 'Missing at export time'])
        for row in missing:
            readme_lines.append(f"- {row['label']}")
    if analysis_summary:
        readme_lines.extend([
            '',
            'Current script analysis summary',
            f"- path: {analysis_summary.get('path', '')}",
            f"- strong_native_hits: {analysis_summary.get('strong_native_hits', 0)}",
            f"- context_tags: {json.dumps(analysis_summary.get('context_tags', {}), indent=2)}",
        ])
    (pack_root / 'README.md').write_text('\n'.join(readme_lines), encoding='utf-8')
    return {'pack_root': pack_root, 'manifest_path': pack_root / 'toolchain_manifest.json', 'copied': copied, 'missing': missing}


def _codered_detect_script_resource_tooling() -> dict:
    resources_root = CODERED_APP_ROOT / 'resources'
    trainer2_root = resources_root / 'trainers' / 'Trainer 2'
    mod_menu_root = resources_root / 'trainers' / 'Mod Menu'
    magic_rdr_root = resources_root / 'Magic-RDR-main'
    sccl_windows_kit_root = resources_root / 'SC-CL-Windows-Build-Kit'
    compile_lab_root = resources_root / 'Code_RED_Script_Compile_Lab_v1'
    compile_bats = sorted((trainer2_root / 'tools').glob('compile*.bat')) if trainer2_root.exists() else []
    compiler_candidates = [
        trainer2_root / 'lib' / 'SC-CL' / 'bin' / 'SC-CL.exe',
        trainer2_root / 'tools' / 'SC-CL.exe',
        resources_root / 'SC-CL-master' / 'llvm-14.0.0.src' / 'MinSizeRel' / 'bin' / 'SC-CL.exe',
        resources_root / 'SC-CL-master' / 'bin' / 'SC-CL.exe',
    ]
    compiler_path = next((candidate for candidate in compiler_candidates if candidate.exists()), None)
    project_files = []
    source_files = []
    header_files = []
    if trainer2_root.exists():
        project_files = sorted(list(trainer2_root.glob('*.sln')) + list((trainer2_root / 'src').glob('*.vcxproj')))
        source_files = sorted(trainer2_root.glob('src/**/*.c'))
        header_files = sorted(trainer2_root.glob('include/**/*.h'))
    donor_wsc = sorted(mod_menu_root.glob('**/*.wsc')) if mod_menu_root.exists() else []
    donor_sco = sorted(mod_menu_root.glob('**/*.sco')) if mod_menu_root.exists() else []
    magic_rdr_exe = magic_rdr_root / 'MagicRDR.exe'
    magic_rdr_pdb = magic_rdr_root / 'MagicRDR.pdb'
    magic_imported_names = [candidate for candidate in [magic_rdr_root / 'ImportedFileNames.txt', magic_rdr_root / 'Settings' / 'ImportedFileNames.txt'] if candidate.exists()]
    xcompress_candidates = [
        magic_rdr_root / 'xcompress32.dll',
        magic_rdr_root / 'Assemblies' / 'xcompress32.dll',
        resources_root / 'SC-CL-master' / 'bin' / 'Release' / 'xcompress32.dll',
        resources_root / 'SC-CL-master' / 'lib' / 'xcompress64.lib',
    ]
    xcompress_assets = [candidate for candidate in xcompress_candidates if candidate.exists()]
    compile_state = 'missing'
    if compiler_path is not None:
        compile_state = 'available'
    elif compile_bats or project_files or source_files:
        compile_state = 'project-present-compiler-missing'
    notes = []
    if trainer2_root.exists():
        notes.append(f'Trainer 2 source project detected: {trainer2_root}')
    if project_files:
        notes.append(f'Project files: {len(project_files)}')
    if source_files:
        notes.append(f'C source files: {len(source_files)}')
    if header_files:
        notes.append(f'Headers: {len(header_files)}')
    if compile_bats:
        notes.append('Compile batch files: ' + ', '.join(p.name for p in compile_bats[:4]))
    if compiler_path is not None:
        notes.append(f'SC-CL compiler detected: {compiler_path}')
    elif compile_state == 'project-present-compiler-missing':
        notes.append('SC-CL compiler is not present in the workspace, so compile-back is not currently runnable here.')
    else:
        notes.append('No donor script compiler/toolchain was detected in the workspace.')
    if magic_rdr_exe.exists():
        notes.append(f'Magic-RDR binary staged: {magic_rdr_exe}')
    else:
        notes.append('Magic-RDR binary is not staged in resources yet.')
    if magic_rdr_pdb.exists():
        notes.append('Magic-RDR PDB is present; script/xcompress lane can be studied more deeply on Windows.')
    if magic_imported_names:
        notes.append(f'Magic-RDR imported-name lists detected: {len(magic_imported_names)}')
    if xcompress_assets:
        notes.append('xcompress assets detected: ' + ', '.join(p.name for p in xcompress_assets))
    else:
        notes.append('No xcompress helper assets were detected in the staged tooling.')
    if sccl_windows_kit_root.exists():
        notes.append(f'SC-CL Windows build kit staged: {sccl_windows_kit_root}')
    if compile_lab_root.exists():
        notes.append(f'Code RED compile lab staged: {compile_lab_root}')
    if donor_wsc or donor_sco:
        notes.append(f'Donor compiled script examples in resources: {len(donor_wsc)} .wsc / {len(donor_sco)} .sco')
    notes.append('Decompiler-style .c output is treated as readable working text only. Existing binary .wsc/.xsc/.sco files still do not have a proven source-faithful decode/recompile path in the current workbench.')
    notes.append('Safe round-trip today means payload-aware inspection, export, clone verification, archive-copy probe validation, and external Windows toolchain staging.')
    return {
        'resources_root': resources_root,
        'trainer2_root': trainer2_root,
        'mod_menu_root': mod_menu_root,
        'magic_rdr_root': magic_rdr_root,
        'magic_rdr_exe': magic_rdr_exe if magic_rdr_exe.exists() else None,
        'magic_rdr_pdb': magic_rdr_pdb if magic_rdr_pdb.exists() else None,
        'magic_imported_names': magic_imported_names,
        'xcompress_assets': xcompress_assets,
        'sccl_windows_kit_root': sccl_windows_kit_root if sccl_windows_kit_root.exists() else None,
        'compile_lab_root': compile_lab_root if compile_lab_root.exists() else None,
        'compile_bats': compile_bats,
        'compiler_path': compiler_path,
        'project_files': project_files,
        'source_files': source_files,
        'header_files': header_files,
        'donor_wsc': donor_wsc,
        'donor_sco': donor_sco,
        'compile_state': compile_state,
        'can_compile_source_project_here': bool(compiler_path is not None and os.name == 'nt'),
        'can_recompile_existing_wsc': False,
        'notes': notes,
    }


@dataclass
class FormatCapability:
    extension: str
    category: str
    capability: str
    notes: str


@dataclass
class ModuleInspection:
    module_name: str
    title: str
    summary: str
    details: str
    warning: str = ""
    preview_text: str = ""
    can_edit_preview_text: bool = False


@dataclass
class OperationResult:
    success: bool
    title: str
    message: str


class ModuleBase:
    name = "Base"
    extensions: tuple[str, ...] = ()
    summary = ""
    capabilities: List[FormatCapability] = []

    def can_handle(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions

    def inspect(self, path: Path) -> ModuleInspection:
        raise NotImplementedError

    def validate(self, path: Path) -> OperationResult:
        raise NotImplementedError

    def status_report(self) -> str:
        return self.summary

    def replace_with(self, target: Path, source: Path) -> OperationResult:
        return safe_backup_replace(target, source)


def read_bytes(path: Path, max_len: Optional[int] = None) -> bytes:
    with path.open("rb") as f:
        return f.read() if max_len is None else f.read(max_len)


def hex_preview(data: bytes, limit: int = 256) -> str:
    data = data[:limit]
    lines = []
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hex_part = " ".join(f"{b:02X}" for b in chunk)
        text_part = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
        lines.append(f"{i:08X}  {hex_part:<47}  {text_part}")
    return "\n".join(lines)


def _looks_like_utf16_text(data: bytes) -> bool:
    if not data:
        return False
    sample = data[:4096]
    candidate_offsets = [0]
    for marker in (b"\xff\xfe", b"\xfe\xff"):
        off = sample.find(marker)
        if off not in {-1, 0} and off < 512:
            candidate_offsets.append(off)
    for offset in candidate_offsets:
        chunk = sample[offset:offset + 4096]
        for enc in ("utf-16-le", "utf-16-be"):
            try:
                decoded = chunk.decode(enc)
            except Exception:
                continue
            decoded = decoded.replace("\x00", "")
            if not decoded:
                continue
            printable = sum(1 for ch in decoded if ch.isprintable() or ch in "\r\n\t")
            alpha = sum(1 for ch in decoded if ch.isalpha())
            if printable / max(1, len(decoded)) >= 0.72 and alpha >= 8:
                return True
    return False


def is_probably_text(data: bytes) -> bool:
    if not data:
        return True
    if _looks_like_utf16_text(data):
        return True
    nul_ratio = data.count(0) / max(1, len(data))
    if nul_ratio > 0.05:
        return False
    try:
        data[:4096].decode("utf-8")
        return True
    except UnicodeDecodeError:
        try:
            data[:4096].decode("latin-1")
            return True
        except UnicodeDecodeError:
            return False


def decode_best_effort(data: bytes) -> str:
    for enc in ("utf-8", "utf-16-le", "latin-1"):
        try:
            return data.decode(enc)
        except Exception:
            continue
    return data.decode("utf-8", errors="replace")


def parse_dds_header(data: bytes) -> Optional[dict]:
    if len(data) < 128 or data[:4] != b"DDS ":
        return None
    pf_flags = int.from_bytes(data[80:84], "little")
    fourcc_raw = data[84:88]
    fourcc = fourcc_raw.decode("latin-1", errors="replace").strip("\x00 ") or "-"
    rgb_bits = int.from_bytes(data[88:92], "little")
    return {
        "width": int.from_bytes(data[16:20], "little"),
        "height": int.from_bytes(data[12:16], "little"),
        "mips": int.from_bytes(data[28:32], "little"),
        "fourcc": fourcc,
        "pf_flags": pf_flags,
        "rgb_bits": rgb_bits,
    }


def parse_png_header(data: bytes) -> Optional[dict]:
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return {
        "width": int.from_bytes(data[16:20], "big"),
        "height": int.from_bytes(data[20:24], "big"),
    }

def open_image_for_preview(path: Path) -> Optional["Image.Image"]:
    if not _HAVE_PIL:
        return None
    try:
        img = Image.open(path)
        img.load()
        return img
    except Exception:
        return None


def get_image_dimensions(path: Path) -> Optional[tuple[int, int]]:
    data = read_bytes(path, 256)
    if path.suffix.lower() == '.png':
        hdr = parse_png_header(data)
        if hdr:
            return hdr['width'], hdr['height']
    if path.suffix.lower() == '.dds':
        hdr = parse_dds_header(data)
        if hdr:
            return hdr['width'], hdr['height']
    if _HAVE_PIL:
        img = open_image_for_preview(path)
        if img is not None:
            return img.width, img.height
    if IMAGE_MAGICK_BIN:
        try:
            cmd = [IMAGE_MAGICK_BIN]
            if Path(IMAGE_MAGICK_BIN).name == 'magick':
                cmd.append('identify')
            else:
                cmd.extend(['identify'])
            cmd.extend(['-format', '%wx%h', str(path)])
            proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
            out = proc.stdout.strip().lower()
            if 'x' in out:
                w, h = out.split('x', 1)
                return int(w), int(h)
        except Exception:
            pass
    return None


def is_viewable_image(path: Path) -> bool:
    if path.suffix.lower() not in {'.png', '.dds'}:
        return False
    return get_image_dimensions(path) is not None


def extract_candidate_strings(data: bytes, ascii_min: int = 4, utf16_min: int = 4, limit: int = 120) -> List[str]:
    found: List[str] = []
    seen = set()

    for m in re.finditer(rb"[ -~]{%d,}" % ascii_min, data):
        try:
            s = m.group(0).decode("latin-1").strip()
        except Exception:
            continue
        if s and s not in seen:
            seen.add(s)
            found.append(s)
            if len(found) >= limit:
                return found

    utf16_pattern = re.compile(rb"(?:[ -~]\x00){%d,}" % utf16_min)
    for m in utf16_pattern.finditer(data):
        raw = m.group(0)
        try:
            s = raw.decode("utf-16-le").strip()
        except Exception:
            continue
        if s and s not in seen:
            seen.add(s)
            found.append(s)
            if len(found) >= limit:
                return found

    return found


def safe_backup_replace(target: Path, source: Path) -> OperationResult:
    backup = target.with_suffix(target.suffix + ".bak")
    shutil.copy2(target, backup)
    shutil.copy2(source, target)
    return OperationResult(True, "Replace complete", f"Replaced {target.name}\nBackup: {backup.name}")


def normalize_texture_stem(name: str) -> str:
    stem = Path(name).stem.lower()
    stem = re.sub(r"[^a-z0-9]+", "_", stem).strip("_")
    suffixes = ("_new", "_replacement", "_replace", "_repl", "_edited", "_edit", "_alt", "_copy", "_v2", "_v3")
    changed = True
    while changed:
        changed = False
        for suffix in suffixes:
            if stem.endswith(suffix):
                stem = stem[: -len(suffix)].rstrip("_")
                changed = True
    return stem


def inspect_texture_payload(path: Path) -> Optional[dict]:
    suffix = path.suffix.lower()
    data = read_bytes(path, 256)
    if suffix == ".dds":
        header = parse_dds_header(data)
        if not header:
            return None
        header["suffix"] = suffix
        header["name"] = path.name
        header["normalized_stem"] = normalize_texture_stem(path.name)
        return header
    if suffix == ".png":
        header = parse_png_header(data)
        if not header:
            return None
        header.update({
            "suffix": suffix,
            "name": path.name,
            "normalized_stem": normalize_texture_stem(path.name),
        })
        return header
    return None


def texture_payload_compatibility(target: Path, source: Path) -> OperationResult:
    target_meta = inspect_texture_payload(target)
    source_meta = inspect_texture_payload(source)
    if not target_meta or not source_meta:
        return OperationResult(False, "Replace blocked", "Could not validate headers on both texture files.")
    if target_meta["suffix"] != source_meta["suffix"]:
        return OperationResult(False, "Replace blocked", f"Texture suffix differs. Target={target_meta['suffix']}, Source={source_meta['suffix']}")
    if (target_meta["width"], target_meta["height"]) != (source_meta["width"], source_meta["height"]):
        return OperationResult(False, "Replace blocked", f"Texture dimensions differ. Target={target_meta['width']}x{target_meta['height']}, Source={source_meta['width']}x{source_meta['height']}")
    if target_meta["suffix"] == ".dds" and target_meta.get("fourcc") != source_meta.get("fourcc"):
        return OperationResult(False, "Replace blocked", f"DDS compression/fourcc differs. Target={target_meta.get('fourcc')}, Source={source_meta.get('fourcc')}")
    return OperationResult(True, "Texture payload compatible", f"Compatible {target_meta['suffix']} payload detected for {target.name}")


def score_texture_name_match(candidate_name: str, reference_name: str) -> tuple[int, List[str]]:
    candidate_stem = normalize_texture_stem(candidate_name)
    reference_stem = normalize_texture_stem(reference_name)
    score = 0
    reasons: List[str] = []
    if candidate_name.lower() == reference_name.lower():
        score += 300
        reasons.append("exact-name")
    if candidate_stem == reference_stem:
        score += 240
        reasons.append("normalized-stem")
    if candidate_stem.startswith(reference_stem) or reference_stem.startswith(candidate_stem):
        score += 90
        reasons.append("stem-prefix")
    c_tokens = {t for t in candidate_stem.split("_") if t}
    r_tokens = {t for t in reference_stem.split("_") if t}
    overlap = c_tokens & r_tokens
    if overlap:
        score += 15 * len(overlap)
        reasons.append("token-overlap:" + ",".join(sorted(overlap)[:4]))
    return score, reasons


def write_plan_file(target: Path, source: Path, title: str, lines: List[str]) -> Path:
    plan_path = target.with_name(target.name + ".replace_plan.txt")
    body = [title, "=" * len(title), "", f"Target: {target}", f"Source: {source}", ""] + lines
    plan_path.write_text("\n".join(body), encoding="utf-8")
    return plan_path


RPF6_AES_KEY = bytes([
    0xB7, 0x62, 0xDF, 0xB6, 0xE2, 0xB2, 0xC6, 0xDE,
    0xAF, 0x72, 0x2A, 0x32, 0xD2, 0xFB, 0x6F, 0x0C,
    0x98, 0xA3, 0x21, 0x74, 0x62, 0xC9, 0xC4, 0xED,
    0xAD, 0xAA, 0x2E, 0xD0, 0xDD, 0xF9, 0x2F, 0x10,
])
_IMPORTED_NAME_CACHE: Optional[Dict[int, str]] = None


def rdr_name_hash(name: str) -> int:
    num2 = 0
    for ch in name.lower():
        num3 = (num2 + ord(ch)) & 0xFFFFFFFF
        num4 = (num3 + ((num3 << 10) & 0xFFFFFFFF)) & 0xFFFFFFFF
        num2 = (num4 ^ (num4 >> 6)) & 0xFFFFFFFF
    num5 = (num2 + ((num2 << 3) & 0xFFFFFFFF)) & 0xFFFFFFFF
    num6 = (num5 ^ (num5 >> 11)) & 0xFFFFFFFF
    return (num6 + ((num6 << 15) & 0xFFFFFFFF)) & 0xFFFFFFFF


def _load_imported_name_cache() -> Dict[int, str]:
    global _IMPORTED_NAME_CACHE
    if _IMPORTED_NAME_CACHE is not None:
        return _IMPORTED_NAME_CACHE
    cache: Dict[int, str] = {}
    root = Path(__file__).resolve().parent
    txt_candidates = [root / 'ImportedFileNames.txt', root / 'resources' / 'Magic-RDR-main' / 'ImportedFileNames.txt', Path.cwd() / 'ImportedFileNames.txt']
    lines: List[str] = []
    for candidate in txt_candidates:
        if candidate.exists():
            try:
                lines = candidate.read_text(encoding='latin-1', errors='ignore').splitlines()
                break
            except Exception:
                pass
    if not lines:
        zip_candidates = [root / 'Magic-RDR-main.zip', root / 'resources' / 'Magic-RDR-main.zip', Path.cwd() / 'Magic-RDR-main.zip']
        for candidate in zip_candidates:
            if candidate.exists():
                try:
                    with zipfile.ZipFile(candidate) as zf:
                        lines = zf.read('Magic-RDR-main/ImportedFileNames.txt').decode('latin-1', errors='ignore').splitlines()
                    break
                except Exception:
                    pass
    for line in lines:
        line = line.strip()
        if not line:
            continue
        cache[rdr_name_hash(line)] = line
    _IMPORTED_NAME_CACHE = cache
    return cache


def _rpf6_decrypt(data: bytes) -> bytes:
    if not data or not _HAVE_CRYPTO:
        return data
    block_len = len(data) & ~0xF
    if block_len <= 0:
        return data
    cipher = Cipher(algorithms.AES(RPF6_AES_KEY), modes.ECB(), backend=default_backend())
    block = data[:block_len]
    for _ in range(16):
        decryptor = cipher.decryptor()
        block = decryptor.update(block) + decryptor.finalize()
    return block + data[block_len:]


def _rpf_flag_is_resource(flag1: int) -> bool:
    return (flag1 & 0x80000000) != 0


def _rpf_flag_is_extended(flag2: int) -> bool:
    return (flag2 & 0x80000000) != 0


def _rpf_flag_is_compressed(flag1: int, flag2: int) -> bool:
    return not _rpf_flag_is_extended(flag2) and ((flag1 >> 30) & 1) == 1


def _rpf_offset(offset_raw: int, is_resource: bool) -> int:
    return ((offset_raw & 0x7FFFFF00) if is_resource else (offset_raw & 0x7FFFFFFF)) * 8


def _rpf_resource_type(offset_raw: int) -> int:
    return offset_raw & 0xFF


def _rpf_total_size(flag1: int, flag2: int) -> int:
    if not _rpf_flag_is_resource(flag1):
        return flag1 & 0xBFFFFFFF
    if _rpf_flag_is_extended(flag2):
        total_v = (flag2 & 0x3FFF) << 12
        total_p = ((flag2 >> 14) & 0x3FFF) << 12
        return total_v + total_p
    vpage0 = (flag1 >> 4) & 0x7F
    vpage1 = (flag1 >> 3) & 1
    vpage2 = (flag1 >> 2) & 1
    vpage3 = (flag1 >> 1) & 1
    vpage4 = flag1 & 1
    vsize = (flag1 >> 11) & 0xF
    ppage0 = (flag1 >> 19) & 0x7F
    ppage1 = (flag1 >> 18) & 1
    ppage2 = (flag1 >> 17) & 1
    ppage3 = (flag1 >> 16) & 1
    ppage4 = (flag1 >> 15) & 1
    psize = (flag1 >> 26) & 0xF
    total_v = ((vpage0 + vpage1 + vpage2 + vpage3 + vpage4) << (vsize + 8))
    total_p = ((ppage0 + ppage1 + ppage2 + ppage3 + ppage4) << (psize + 8))
    return total_v + total_p


RSC_IDENTIFIERS = {
    1381188357: "05CSR",
    1381188358: "06CSR",
    1381188485: "85CSR",
    1381188486: "86CSR",
    88298322: "RSC05",
    105075538: "RSC06",
    2235781970: "RSC85",
    2252559186: "RSC86",
}


def parse_resource_header(data: bytes) -> Optional[dict]:
    if len(data) < 12:
        return None
    ident_be = int.from_bytes(data[:4], 'big', signed=False)
    ident_le = int.from_bytes(data[:4], 'little', signed=False)
    ascii_header = ident_be in {1381188357, 1381188358, 1381188485, 1381188486}
    if ascii_header:
        ident = ident_be
        field_endian = 'little'
        display_endian = 'mixed/ascii'
    elif ident_le in RSC_IDENTIFIERS:
        ident = ident_le
        field_endian = 'little'
        display_endian = 'little'
    elif ident_be in RSC_IDENTIFIERS:
        ident = ident_be
        field_endian = 'big'
        display_endian = 'big'
    else:
        return None
    def read_u32(offset: int) -> int:
        if offset + 4 > len(data):
            return 0
        return int.from_bytes(data[offset:offset+4], field_endian, signed=False)
    resource_type = read_u32(4)
    flag1 = read_u32(8)
    flag2 = read_u32(12) if ident in {1381188485, 1381188486, 2235781970, 2252559186} and len(data) >= 16 else 0
    normalized_map = {'05CSR': 'RSC05', '06CSR': 'RSC06', '85CSR': 'RSC85', '86CSR': 'RSC86'}
    normalized = normalized_map.get(RSC_IDENTIFIERS[ident], RSC_IDENTIFIERS[ident])
    return {
        'ident': ident,
        'ident_name': normalized,
        'raw_ident_name': RSC_IDENTIFIERS[ident],
        'endian': display_endian,
        'resource_type': resource_type,
        'flag1': flag1,
        'flag2': flag2,
        'is_resource_stream': True,
        'is_extended': _rpf_flag_is_extended(flag2) if normalized in {'RSC85', 'RSC86'} else False,
        'is_compressed': _rpf_flag_is_compressed(flag1, flag2) if normalized in {'RSC05', 'RSC06'} else False,
        'total_size': _rpf_total_size(flag1, flag2),
    }


def append_resource_lines(details: List[str], resource: Optional[dict]) -> None:
    if not resource:
        return
    details.extend([
        f"Resource header: {resource['ident_name']} [{resource['raw_ident_name']}] ({resource['endian']})",
        f"Resource type: {resource['resource_type']}",
        f"Resource flag1: 0x{resource['flag1']:08X}",
    ])
    if resource['ident_name'] in {'RSC85', 'RSC86'}:
        details.append(f"Resource flag2: 0x{resource['flag2']:08X}")
    details.extend([
        f"Resource stream: {resource['is_resource_stream']}",
        f"Extended flags: {resource['is_extended']}",
        f"Compressed: {resource['is_compressed']}",
        f"Declared total size: {resource['total_size']:,} bytes",
    ])


def resource_header_size(resource: Optional[dict]) -> int:
    if not resource:
        return 0
    return 16 if resource['ident_name'] in {'RSC85', 'RSC86'} else 12


def _looks_like_zlib_payload(data: bytes) -> bool:
    if len(data) < 2:
        return False
    return data[:2] in {b"x\x9c", b"x\xda", b"x\x01", b"x^", b"\x78\x5e", b"\x78\x9c", b"\x78\xda"}


def _codered_try_zstd_decompress(data: bytes, expected_size: int = 0) -> tuple[Optional[bytes], str]:
    if not data or not data.startswith(b'\x28\xB5\x2F\xFD'):
        return None, ''
    if _HAVE_ZSTD and _zstd is not None:
        dctx = _zstd.ZstdDecompressor()
        try:
            return dctx.decompress(data), 'python-zstandard'
        except Exception:
            if expected_size > 0:
                try:
                    return dctx.decompress(data, max_output_size=expected_size), f'python-zstandard(max_output_size={expected_size})'
                except Exception:
                    pass
            try:
                with dctx.stream_reader(io.BytesIO(data)) as reader:
                    return reader.read(), 'python-zstandard(stream)'
            except Exception:
                pass
    zstd_bin = shutil.which('zstd')
    if zstd_bin:
        try:
            proc = subprocess.run([zstd_bin, '-d', '-q', '--stdout'], input=data, capture_output=True, check=True)
            if proc.stdout:
                return proc.stdout, 'zstd-cli'
        except Exception:
            pass
    return None, ''


def extract_resource_payload(data: bytes, resource: Optional[dict] = None) -> dict:
    resource = resource or parse_resource_header(data)
    if not resource:
        return {
            'payload': data,
            'raw_payload': data,
            'coded_payload': data,
            'zstd_frame': None,
            'notes': ['No resource header; raw file bytes used for analysis.'],
            'decrypted': False,
            'decompressed': False,
            'header_size': 0,
        }

    header_size = resource_header_size(resource)
    raw_payload = data[header_size:] if len(data) > header_size else b''
    payload = raw_payload
    notes: List[str] = [f"Resource payload starts at byte {header_size}."]
    decrypted = False
    decompressed = False

    if payload and resource['resource_type'] == 2 and resource['ident_name'] in {'RSC85', 'RSC86'}:
        dec = _rpf6_decrypt(payload)
        if dec != payload:
            payload = dec
            decrypted = True
            notes.append('Applied AES payload decryption for RSC85/RSC86 resource type 2.')
        else:
            notes.append('AES payload decryption path was attempted, but payload bytes were unchanged.')

    coded_payload = payload
    zstd_frame = _codered_parse_zstd_frame(coded_payload) if coded_payload.startswith(b'\x28\xB5\x2F\xFD') else None
    if zstd_frame:
        window_size = zstd_frame.get('window_size')
        window_desc = f"{window_size:,} B" if isinstance(window_size, int) else 'unknown'
        notes.append(
            f"Zstd frame detected: descriptor=0x{zstd_frame['frame_descriptor']:02X}, window={window_desc}, checksum={'yes' if zstd_frame.get('checksum_flag') else 'no'}."
        )

    decompressed_payload = None
    codec = None
    if coded_payload:
        if zstd_frame:
            decompressed_payload, codec = _codered_try_zstd_decompress(coded_payload, int(resource.get('total_size') or 0))
            if decompressed_payload is None:
                notes.append('Zstandard payload detected but fallback decompression failed.')
        if decompressed_payload is None and (_looks_like_zlib_payload(coded_payload) or resource.get('is_compressed')):
            for wbits in (-15, 15, 31):
                try:
                    trial = zlib.decompress(coded_payload, wbits)
                    if trial:
                        decompressed_payload = trial
                        codec = f'zlib(wbits={wbits})'
                        break
                except Exception:
                    continue
        if decompressed_payload is not None:
            payload = decompressed_payload
            decompressed = True
            notes.append(f'Payload decompressed using {codec}.')
        elif resource.get('is_compressed'):
            notes.append('Payload appears compressed, but no supported decompressor succeeded in the fallback path.')

    if resource.get('total_size') and payload:
        notes.append(f"Payload length after processing: {len(payload):,} bytes (declared total size {resource['total_size']:,}).")
    elif payload:
        notes.append(f"Payload length after processing: {len(payload):,} bytes.")
    else:
        notes.append('No payload bytes were available after the resource header.')

    return {
        'payload': payload,
        'raw_payload': raw_payload,
        'coded_payload': coded_payload,
        'zstd_frame': zstd_frame,
        'notes': notes,
        'decrypted': decrypted,
        'decompressed': decompressed,
        'header_size': header_size,
    }

def candidate_strings_from_payload(data: bytes, resource: Optional[dict], limit: int = 120) -> List[str]:
    payload_info = extract_resource_payload(data, resource) if resource else {'payload': data}
    payload = payload_info.get('payload', data)
    return extract_candidate_strings(payload if payload else data, limit=limit)


def parse_rpf6(path: Path) -> Optional[dict]:
    data = read_bytes(path)
    if len(data) < 16 or data[:4] != b'RPF6':
        return None
    _, entry_count, debug_offset, enc_flag = struct.unpack('>4I', data[:16])
    toc_size = ((entry_count * 20) + 15) & ~15
    if len(data) < 16 + toc_size:
        return None
    toc = data[16:16 + toc_size]
    if enc_flag != 0:
        toc = _rpf6_decrypt(toc)
    entries: List[dict] = []
    file_count = 0
    dir_count = 0
    for i in range(entry_count):
        chunk = toc[i * 20:(i + 1) * 20]
        if len(chunk) < 20:
            break
        a, b, c, d, e = struct.unpack('>5I', chunk)
        is_dir = ((c >> 24) & 0xFF) == 0x80
        entry = {'index': i, 'name_off': a, 'debug_name': None}
        if is_dir:
            entry.update({'type': 'dir', 'flags': b, 'start': c & 0x7FFFFFFF, 'count': d & 0x0FFFFFFF, 'unk': e})
            dir_count += 1
        else:
            is_resource = _rpf_flag_is_resource(d)
            entry.update({
                'type': 'file',
                'size_in_archive': b & 0x0FFFFFFF,
                'offset_raw': c,
                'flag1': d,
                'flag2': e,
                'is_resource': is_resource,
                'is_compressed': _rpf_flag_is_compressed(d, e),
                'resource_type': _rpf_resource_type(c) if is_resource else None,
                'offset': _rpf_offset(c, is_resource),
                'total_size': _rpf_total_size(d, e),
            })
            file_count += 1
        entries.append(entry)

    if debug_offset > 0 and debug_offset * 8 < len(data):
        debug_blob = _rpf6_decrypt(data[debug_offset * 8:])
        names_blob = debug_blob[entry_count * 8:]
        for raw_name in names_blob.decode('latin-1', errors='ignore').split('\x00'):
            raw_name = raw_name.strip()
            if not raw_name:
                continue
            h = rdr_name_hash(raw_name)
            for entry in entries:
                if entry['name_off'] == h and not entry['debug_name']:
                    entry['debug_name'] = raw_name
                    break

    imported = _load_imported_name_cache()

    def resolve_name(entry: dict) -> str:
        if entry['type'] == 'dir' and entry['name_off'] == 0:
            return 'root'
        return entry.get('debug_name') or imported.get(entry['name_off']) or f"0x{entry['name_off']:08X}"

    parent_indices: List[Optional[int]] = [None] * len(entries)
    for entry in entries:
        if entry['type'] == 'dir':
            for child_index in range(entry['start'], entry['start'] + entry['count']):
                if 0 <= child_index < len(entries):
                    parent_indices[child_index] = entry['index']

    resolved_count = 0
    ext_counts: Counter[str] = Counter()
    sample_paths: List[str] = []
    for entry in entries:
        entry['name'] = resolve_name(entry)
        entry['parent_index'] = parent_indices[entry['index']]
        if not entry['name'].startswith('0x') or entry['name'] == 'root':
            resolved_count += 1
        parent = parent_indices[entry['index']]
        parts = [entry['name']]
        while parent is not None:
            parts.append(resolve_name(entries[parent]))
            parent = parent_indices[parent]
        entry['path'] = '/'.join(reversed(parts))
        entry['extension'] = ('.' + entry['name'].lower().rsplit('.', 1)[-1]) if (entry['type'] == 'file' and '.' in entry['name']) else ''
        if entry['extension']:
            ext_counts[entry['extension']] += 1
        if len(sample_paths) < 40:
            sample_paths.append(entry['path'])

    return {
        'entry_count': entry_count,
        'toc_size': toc_size,
        'debug_offset': debug_offset,
        'enc_flag': enc_flag,
        'encrypted': enc_flag != 0,
        'file_count': file_count,
        'dir_count': dir_count,
        'resolved_count': resolved_count,
        'ext_counts': ext_counts,
        'entries': entries,
        'sample_paths': sample_paths,
    }


def extract_rpf_entry(archive_path: Path, entry: dict) -> bytes:
    if entry.get('type') != 'file':
        raise ValueError('Only file entries can be extracted')
    with archive_path.open('rb') as f:
        f.seek(entry['offset'])
        raw = f.read(entry['size_in_archive'])
    if entry.get('is_resource'):
        return raw
    if entry.get('is_compressed'):
        target_size = entry.get('total_size') or 0
        if raw.startswith(b'\x28\xB5\x2F\xFD'):
            try:
                proc = subprocess.run(['zstd', '-d', '-q', '--stdout'], input=raw, capture_output=True, check=True)
                if proc.stdout:
                    return proc.stdout
            except Exception:
                pass
        for wbits in (-15, 15, 31):
            try:
                payload = zlib.decompress(raw, wbits)
                if not target_size or len(payload) == target_size or len(payload) > 0:
                    return payload
            except Exception:
                continue
        raise ValueError('Compressed file could not be decompressed with current fallback path')
    return raw


class ArchiveModule(ModuleBase):
    name = "Archive"
    extensions = (".rpf",)
    summary = "Encrypted RPF6 inventory, contained-file export, and patch-folder apply to copied archives."
    capabilities = [
        FormatCapability(".rpf", "Archive", "V/E/I/X/R", "Encrypted RPF6 TOC inventory, content export, and patch-folder apply are available in the Python fallback.")
    ]

    def inspect(self, path: Path) -> ModuleInspection:
        info = parse_rpf6(path)
        details = [f"Path: {path}", f"Size: {path.stat().st_size:,} bytes", f"Extension: {path.suffix.lower()}"]
        warning = ""
        if info is None:
            data = read_bytes(path, 256)
            summary = "Archive inspection baseline."
            if data[:4] == b"RPF6":
                summary = "RPF6 archive signature detected, but TOC parse failed."
                warning = "Header is present, but encrypted/deeper TOC parsing did not complete."
            else:
                warning = "Unknown archive signature."
            return ModuleInspection(self.name, f"Archive - {path.name}", summary, "\n".join(details), warning, hex_preview(data))

        summary = "Encrypted RPF6 TOC inventory parsed successfully."
        details.extend([
            f"Entries: {info['entry_count']}",
            f"Files: {info['file_count']}",
            f"Directories: {info['dir_count']}",
            f"TOC Size: {info['toc_size']:,} bytes",
            f"Debug Name Offset: {info['debug_offset']} (x8 => {info['debug_offset'] * 8:,} bytes)",
            f"Encrypted TOC: {info['encrypted']}",
            f"Resolved Names: {info['resolved_count']}/{info['entry_count']}",
        ])
        file_entries = [ent for ent in info['entries'] if ent.get('type') == 'file']
        if file_entries:
            storage_counts = Counter(_codered_storage_kind(ent) for ent in file_entries)
            module_counts = Counter(_codered_module_name_for_virtual_path(ent.get('name', '')) for ent in file_entries)
            script_paths = [ent.get('path', '') for ent in file_entries if ent.get('extension') in SCRIPT_BINARY_EXTENSIONS]
            source_paths = [ent.get('path', '') for ent in file_entries if _codered_is_code_bearing_extension(ent.get('extension', ''))]
            details.append("Storage profile:")
            details.extend(f"- {kind}: {count}" for kind, count in storage_counts.most_common())
            details.append("Module routing profile:")
            details.extend(f"- {name}: {count}" for name, count in module_counts.most_common())
            if script_paths:
                details.append("Compiled script entries:")
                details.extend(f"- {item}" for item in script_paths[:20])
            if source_paths:
                details.append("Code-bearing entries:")
                details.extend(f"- {item}" for item in source_paths[:20])
        if info['ext_counts']:
            details.append("Top contained file types:")
            details.extend(f"- {ext}: {count}" for ext, count in info['ext_counts'].most_common(20))
        details.append("Use Archive -> Open Viewer for the browser and Archive -> Export for a full totality audit bundle.")
        preview = "\n".join(["Archive paths:"] + info['sample_paths'])
        if info['resolved_count'] < info['entry_count']:
            warning = "Some archive entry names remain unresolved hashes after debug-name and imported-name lookup."
        return ModuleInspection(self.name, f"Archive - {path.name}", summary, "\n".join(details), warning, preview)

    def validate(self, path: Path) -> OperationResult:
        info = parse_rpf6(path)
        if info is None:
            data = read_bytes(path, 16)
            if len(data) < 4:
                return OperationResult(False, "Archive validation failed", "File is too small.")
            if data[:4] == b"RPF6":
                return OperationResult(False, "Archive validation partial", "RPF6 signature detected, but TOC inventory parse failed.")
            return OperationResult(False, "Archive validation failed", "Expected RPF6 signature at file start.")
        audit = audit_rpf6_archive(path, include_hashes=False, include_extract=True)
        msg = f"RPF6 inventory parsed. Files={info['file_count']}, Directories={info['dir_count']}, Resolved Names={info['resolved_count']}/{info['entry_count']}"
        if info['ext_counts']:
            top_ext, top_count = info['ext_counts'].most_common(1)[0]
            msg += f"\nMost common contained type: {top_ext} ({top_count})"
        if audit is not None:
            msg += f"\nArchive totality extract pass: ok={audit['extract_success']} fail={audit['extract_fail']}"
            if audit['script_entry_count']:
                msg += f"\nScript-like entries discovered: {audit['script_entry_count']}"
        return OperationResult(True, "Archive validation passed", msg)


class StringsModule(ModuleBase):
    name = "Strings"
    extensions = (".sst", ".wst", ".strtbl", ".strbl", ".txt", ".xml", ".json", ".ini", ".cfg", ".list")
    summary = "String table and text-like assets with editable preview/save in the Python fallback."
    capabilities = [
        FormatCapability(".sst", "Strings", "V/E/X/I/R", "Readable-text editing path is staged."),
        FormatCapability(".wst", "Strings", "V/E/X/I/R", "Readable-text editing path is staged."),
        FormatCapability(".strtbl", "Strings", "V/E/X/I/R", "Readable-text editing path is staged."),
        FormatCapability(".strbl", "Strings", "V/E/X/I/R", "Large binary string-table lane with heuristic preview and routed editing support."),
    ]

    def inspect(self, path: Path) -> ModuleInspection:
        data = read_bytes(path)
        resource = parse_resource_header(data)
        suffix = path.suffix.lower()
        payload_info = extract_resource_payload(data, resource) if resource else {'payload': data, 'notes': []}
        analysis_bytes = payload_info.get('payload', data) or data
        textlike = (suffix in {'.txt', '.xml', '.json', '.ini', '.cfg', '.list'}) or is_probably_text(analysis_bytes)
        extracted = [] if textlike else extract_candidate_strings(analysis_bytes, limit=160)
        preview = decode_best_effort(analysis_bytes) if textlike else "\n".join(extracted[:160])
        details = [
            f"Path: {path}",
            f"Size: {path.stat().st_size:,} bytes",
            f"Text-like after payload processing: {textlike}",
        ]
        append_resource_lines(details, resource)
        if resource:
            details.append('Resource payload processing:')
            details.extend(f"- {note}" for note in payload_info.get('notes', []))
        warning = ""
        if not textlike:
            details.append(f"Extracted candidate strings: {len(extracted)}")
            warning = "Binary string tables still need donor-backed parsing for full fidelity. Candidate strings are extracted heuristically."
        summary = "String/text inspection routed successfully." if not resource else "String-family inspection with resource-header aware payload analysis routed successfully."
        return ModuleInspection(
            self.name,
            f"Strings - {path.name}",
            summary,
            "\n".join(details),
            warning,
            preview if preview else hex_preview(data),
            can_edit_preview_text=textlike and suffix in {'.txt', '.xml', '.json', '.ini', '.cfg', '.list'},
        )

    def validate(self, path: Path) -> OperationResult:
        data = read_bytes(path, 65536)
        resource = parse_resource_header(data)
        payload_info = extract_resource_payload(data, resource) if resource else {'payload': data, 'notes': []}
        analysis_bytes = payload_info.get('payload', data) or data
        if is_probably_text(analysis_bytes):
            msg = "File appears text-like after payload processing."
            if resource:
                msg += f" Resource header={resource['ident_name']} type={resource['resource_type']}."
            return OperationResult(True, "Strings validation passed", msg)
        extracted = extract_candidate_strings(analysis_bytes, limit=20)
        if extracted:
            msg = f"Binary string-like asset detected. Extracted {len(extracted)} candidate strings after payload processing."
            if resource:
                msg += f" Resource header={resource['ident_name']} type={resource['resource_type']}."
            return OperationResult(True, "Strings validation partial", msg)
        if resource:
            return OperationResult(True, "Strings validation partial", f"Binary string-like resource detected. Header={resource['ident_name']} type={resource['resource_type']}. Payload processing notes: {'; '.join(payload_info.get('notes', []))}")
        return OperationResult(True, "Strings validation partial", "Binary string-like asset detected. Full structure-aware validation is pending.")


class TexturesModule(ModuleBase):
    name = "Textures"
    extensions = (".wtd", ".wtx", ".wsf", ".xtd", ".xtx", ".xsf", ".dds", ".png")
    summary = "Magic-leaning texture lane: DDS/PNG validation now, container rules next."
    capabilities = [
        FormatCapability(".wtd", "Textures", "V/E/X/I/R", "Primary texture dictionary target."),
        FormatCapability(".wtx", "Textures", "V/E/R", "Payload mapping target."),
        FormatCapability(".dds", "Textures", "V/E/I/R", "DDS header validation and guarded replace are live."),
        FormatCapability(".png", "Textures", "V/E/I/R", "PNG header validation and guarded replace are live."),
    ]
    _container_exts = {".wtd", ".wtx", ".wsf", ".xtd", ".xtx", ".xsf"}

    def inspect(self, path: Path) -> ModuleInspection:
        data = read_bytes(path)
        suffix = path.suffix.lower()
        resource = parse_resource_header(data) if suffix in self._container_exts else None
        payload_info = extract_resource_payload(data, resource) if resource else {'payload': data, 'notes': []}
        details = [f"Path: {path}", f"Size: {path.stat().st_size:,} bytes", f"Extension: {suffix}"]
        append_resource_lines(details, resource)
        if resource:
            details.append('Resource payload processing:')
            details.extend(f"- {note}" for note in payload_info.get('notes', []))
        summary = "Texture/container inspection baseline."
        warning = ""
        dds = parse_dds_header(data) if suffix == ".dds" else None
        png = parse_png_header(data) if suffix == ".png" else None
        hints = candidate_strings_from_payload(data, resource, limit=80) if suffix in self._container_exts else []
        dds_hints = [h for h in hints if h.lower().endswith(".dds")][:40]
        if dds:
            summary = "DDS header parsed successfully."
            details.extend([
                f"Width: {dds['width']}",
                f"Height: {dds['height']}",
                f"Mip Count: {dds['mips']}",
                f"FourCC: {dds['fourcc']}",
            ])
        elif png:
            summary = "PNG header parsed successfully."
            details.extend([f"Width: {png['width']}", f"Height: {png['height']}"])
        else:
            summary = "Texture container inspection with resource-header awareness." if resource else summary
            warning = "RDR1 texture container detected or unknown texture payload. Full dictionary parsing remains staged."
            if dds_hints:
                details.append("Embedded texture-name hints:")
                details.extend(f"- {h}" for h in dds_hints)
        preview = "\n".join(dds_hints) if dds_hints else hex_preview(data)
        return ModuleInspection(self.name, f"Textures - {path.name}", summary, "\n".join(details), warning, preview)

    def validate(self, path: Path) -> OperationResult:
        data = read_bytes(path, 512)
        suffix = path.suffix.lower()
        if suffix == ".dds":
            dds = parse_dds_header(data)
            if dds:
                return OperationResult(True, "Texture validation passed", f"DDS header looks valid: {dds['width']}x{dds['height']}, {dds['fourcc']}, mips={dds['mips']}")
            return OperationResult(False, "Texture validation failed", "Missing DDS header.")
        if suffix == ".png":
            png = parse_png_header(data)
            if png:
                return OperationResult(True, "Texture validation passed", f"PNG header looks valid: {png['width']}x{png['height']}")
            return OperationResult(False, "Texture validation failed", "Missing PNG signature.")
        resource = parse_resource_header(data) if suffix in self._container_exts else None
        hints = [s for s in candidate_strings_from_payload(data, resource, limit=30) if s.lower().endswith(".dds")]
        msg = f"Container routed successfully. Embedded texture-name hints found: {len(hints)}"
        if resource:
            msg += f" Resource header={resource['ident_name']} type={resource['resource_type']}."
        if extra_hints:
            msg += f" Payload notes/hints={len(extra_hints)}."
            msg += f" Payload notes: {'; '.join(payload_info.get('notes', []))}"
        return OperationResult(True, "Texture validation partial", msg)

    def replace_with(self, target: Path, source: Path) -> OperationResult:
        target_ext = target.suffix.lower()
        source_ext = source.suffix.lower()
        if target_ext in {".dds", ".png"}:
            result = texture_payload_compatibility(target, source)
            if not result.success:
                return result
            return safe_backup_replace(target, source)
        if target_ext in self._container_exts:
            if source_ext == target_ext:
                return safe_backup_replace(target, source)
            if source_ext in {".dds", ".png"}:
                hints = [s for s in extract_candidate_strings(read_bytes(target), limit=60) if s.lower().endswith(".dds")]
                scored = []
                for hint in hints:
                    score, reasons = score_texture_name_match(source.name, hint)
                    scored.append((score, hint, reasons))
                scored.sort(reverse=True)
                lines = [
                    "Direct injection of standalone textures into RDR1 texture containers is not implemented in the fallback workbench.",
                    f"Container extension: {target_ext}",
                    f"Source extension: {source_ext}",
                    "",
                    "Embedded texture-name hints discovered:",
                    *([f"- {h}" for h in hints] if hints else ["- none found by heuristic scan"]),
                ]
                if scored:
                    lines.extend(["", "Best source-to-slot name matches:"])
                    lines.extend(f"- score={score}: {hint} [{' | '.join(reasons) if reasons else 'weak-name-match'}]" for score, hint, reasons in scored[:12])
                lines.extend(["", "Safe action taken:", "- Wrote this replacement plan instead of mutating the binary container blindly."])
                plan = write_plan_file(target, source, "Texture Container Replacement Plan", lines)
                return OperationResult(True, "Plan written", f"Direct container injection was not attempted. Replacement plan written to:\n{plan}")
        return safe_backup_replace(target, source)




class MeshesModule(ModuleBase):
    name = "Meshes"
    extensions = (".wvd", ".wft", ".wfd", ".wbd", ".wtb", ".xvd", ".xft", ".xfd", ".xbd", ".xtb")
    summary = "CodeX-leaning mesh lane with dependency discovery, texture-carrier hints, and guarded companion targeting."
    capabilities = [
        FormatCapability(".wft", "Meshes", "V/E/X/P", "Fragment files may carry embedded texture dictionaries or shader-group texture refs."),
        FormatCapability(".wfd", "Meshes", "V/E/X/P", "Frag drawables can carry texture dictionaries."),
        FormatCapability(".wvd", "Meshes", "V/E/X/P", "Visual dictionaries can carry texture dictionaries."),
    ]

    _texture_carrier_exts = {".wft", ".wfd", ".wvd", ".xft", ".xfd", ".xvd"}
    _standalone_texture_exts = {".dds", ".png"}

    def _scan_hints(self, data: bytes, ext: str) -> List[str]:
        found = set()
        pattern = rb"([A-Za-z0-9_:\-/\.]{3,96}" + re.escape(ext.encode("ascii")) + rb")"
        for m in re.finditer(pattern, data, re.IGNORECASE):
            try:
                s = m.group(1).decode("latin-1", errors="ignore")
            except Exception:
                continue
            if s:
                found.add(s)
        return sorted(found)[:60]

    def _classify(self, suffix: str) -> tuple[str, str]:
        mapping = {
            ".wft": ("Fragment", "Likely fragment root with drawable, bounds, and possibly embedded or linked textures."),
            ".xft": ("Fragment", "Likely console fragment root with drawable, bounds, and possibly embedded or linked textures."),
            ".wfd": ("FragDrawable", "Likely drawable root with explicit TextureDictionary + Drawable pairing."),
            ".xfd": ("FragDrawable", "Likely console frag drawable root with explicit TextureDictionary + Drawable pairing."),
            ".wvd": ("VisualDictionary", "Likely visual dictionary root with Drawables + TextureDictionary."),
            ".xvd": ("VisualDictionary", "Likely console visual dictionary root with Drawables + TextureDictionary."),
            ".wbd": ("Bounds", "Likely bounds or collision family resource."),
            ".xbd": ("Bounds", "Likely bounds or collision family resource."),
            ".wtb": ("MeshSupport", "Mesh-side support file; exact structure still staged."),
            ".xtb": ("MeshSupport", "Mesh-side support file; exact structure still staged."),
        }
        return mapping.get(suffix, ("Mesh-family", "Mesh-family resource."))

    def _search_roots(self, path: Path) -> List[Path]:
        roots = [path.parent]
        parent = path.parent.parent
        if parent != path.parent and parent.exists():
            roots.append(parent)
            for child in parent.iterdir():
                if child.is_dir() and child != path.parent:
                    roots.append(child)
        return roots

    def _related_files(self, path: Path) -> Dict[str, List[str]]:
        groups = {
            "textures": {".wtd", ".wtx", ".wsf", ".xtd", ".xtx", ".xsf", ".dds", ".png"},
            "world": {".wsi", ".wtl", ".wsg", ".wsp", ".wnm", ".wcg", ".wgd"},
            "strings": {".sst", ".wst", ".strtbl", ".strbl"},
            "shaders": {".fxc", ".fxlist", ".shaderlist"},
        }
        roots = self._search_roots(path)
        seen = set()
        out: Dict[str, List[str]] = {k: [] for k in groups}
        stem = path.stem.lower()
        token = stem[: max(3, min(8, len(stem)))] if stem else ""
        base = path.parent.parent if path.parent.parent.exists() else path.parent
        for root in roots:
            try:
                for item in root.iterdir():
                    if not item.is_file() or item in seen:
                        continue
                    seen.add(item)
                    sfx = item.suffix.lower()
                    itemstem = item.stem.lower()
                    for group_name, exts in groups.items():
                        if sfx in exts and (stem in itemstem or itemstem in stem or (token and itemstem.startswith(token))):
                            try:
                                rel = str(item.relative_to(base))
                            except Exception:
                                rel = str(item)
                            out[group_name].append(rel)
            except Exception:
                continue
        return {k: sorted(v)[:60] for k, v in out.items() if v}

    def _texture_candidates(self, target: Path, source: Optional[Path] = None) -> List[dict]:
        data = read_bytes(target)
        hints = self._scan_hints(data, ".dds")
        source_name = source.name if source else ""
        source_stem = normalize_texture_stem(source_name) if source else ""
        candidates: List[dict] = []
        roots = self._search_roots(target)
        seen = set()
        for root in roots:
            try:
                for item in root.iterdir():
                    if not item.is_file() or item in seen or item.suffix.lower() not in self._standalone_texture_exts:
                        continue
                    if source is not None:
                        try:
                            if item.resolve() == source.resolve():
                                continue
                        except Exception:
                            if item == source:
                                continue
                    seen.add(item)
                    score = 0
                    reasons: List[str] = []
                    matched_hint = ""
                    for hint in hints:
                        hint_score, hint_reasons = score_texture_name_match(item.name, hint)
                        if hint_score > score:
                            score = hint_score
                            reasons = hint_reasons[:]
                            matched_hint = hint
                    if source_name:
                        source_score, source_reasons = score_texture_name_match(item.name, source_name)
                        score += source_score
                        reasons.extend(source_reasons)
                    if source_stem and normalize_texture_stem(item.name) == source_stem:
                        score += 160
                        reasons.append("source-normalized-stem")
                    if target.stem.lower() in item.stem.lower() or item.stem.lower() in target.stem.lower():
                        score += 20
                        reasons.append("mesh-stem-overlap")
                    if score > 0:
                        meta = inspect_texture_payload(item) or {"suffix": item.suffix.lower()}
                        candidates.append({
                            "path": item,
                            "score": score,
                            "reasons": sorted(set(reasons)),
                            "matched_hint": matched_hint,
                            "meta": meta,
                        })
            except Exception:
                continue
        candidates.sort(key=lambda c: (-c["score"], c["path"].name.lower()))
        return candidates[:24]

    def _structured_preview(self, path: Path, source: Optional[Path] = None) -> tuple[List[str], List[dict], List[str], List[str], List[str]]:
        raw_data = read_bytes(path)
        resource = parse_resource_header(raw_data)
        payload_info = extract_resource_payload(raw_data, resource) if resource else {'payload': raw_data, 'notes': []}
        analysis_bytes = payload_info.get('payload', raw_data) or raw_data
        dds_hints = self._scan_hints(analysis_bytes, '.dds')
        shader_hints = self._scan_hints(analysis_bytes, '.fxc')
        bone_hints = [
            s for s in extract_candidate_strings(analysis_bytes, limit=200)
            if any(tok in s.lower() for tok in ('spine', 'pelvis', 'clavicle', 'arm_', 'wrist', 'finger_', 'toe_', 'head', 'neck', 'tail'))
        ][:60]
        texture_candidates = self._texture_candidates(path, source)
        relation_lines: List[str] = []
        for candidate in texture_candidates[:10]:
            rel_name = candidate["path"].name
            reason_text = ", ".join(candidate["reasons"]) if candidate["reasons"] else "heuristic-match"
            hint_text = f" -> hint {candidate['matched_hint']}" if candidate["matched_hint"] else ""
            relation_lines.append(f"- score={candidate['score']}: {rel_name}{hint_text} [{reason_text}]")
        return dds_hints, texture_candidates, shader_hints, relation_lines, bone_hints + payload_info.get('notes', [])

    def inspect(self, path: Path) -> ModuleInspection:
        suffix = path.suffix.lower()
        resource = parse_resource_header(read_bytes(path, 64))
        texture_carrier = suffix in self._texture_carrier_exts
        root_type, root_notes = self._classify(suffix)
        dds_hints, texture_candidates, shader_hints, relation_lines, extra_hints = self._structured_preview(path)
        related = self._related_files(path)
        details = [
            f"Path: {path}",
            f"Size: {path.stat().st_size:,} bytes",
            f"Extension: {suffix}",
            f"Likely root object: {root_type}",
            f"Likely texture carrier: {texture_carrier}",
            f"Root notes: {root_notes}",
            f"Embedded texture hints found: {len(dds_hints)}",
            f"Ranked companion texture candidates: {len(texture_candidates)}",
        ]
        append_resource_lines(details, resource)
        if dds_hints:
            details.append("Embedded .dds name hints:")
            details.extend(f"- {h}" for h in dds_hints)
        if shader_hints:
            details.append("Embedded shader/fxc name hints:")
            details.extend(f"- {h}" for h in shader_hints)
        if relation_lines:
            details.append("Ranked external companion targets:")
            details.extend(relation_lines)
        if extra_hints:
            details.append("Additional payload-derived hints:")
            details.extend(f"- {h}" for h in extra_hints[:40])
        if related:
            details.append("Dependency graph (nearby file matches):")
            for group, items in related.items():
                details.append(f"- {group}:")
                details.extend(f"  - {r}" for r in items)
        summary = "Mesh-family inspection with fragment/drawable/dictionary heuristics, ranked companion targeting, and dependency discovery."
        warning = "Structure-aware binary parsing for fragment/drawable/visual-dictionary objects is still pending, so these are guided heuristics rather than trusted parse results."
        preview_parts = []
        if dds_hints:
            preview_parts.append("Embedded texture hints:")
            preview_parts.extend(dds_hints)
        if relation_lines:
            if preview_parts:
                preview_parts.append("")
            preview_parts.append("Ranked external companion targets:")
            preview_parts.extend(relation_lines)
        if shader_hints:
            if preview_parts:
                preview_parts.append("")
            preview_parts.append("Embedded shader hints:")
            preview_parts.extend(shader_hints)
        if extra_hints:
            if preview_parts:
                preview_parts.append("")
            preview_parts.append("Payload-derived notes:")
            preview_parts.extend(extra_hints[:40])
        preview = "\n".join(preview_parts) if preview_parts else hex_preview(read_bytes(path))
        return ModuleInspection(self.name, f"Meshes - {path.name}", summary, "\n".join(details), warning, preview)

    def validate(self, path: Path) -> OperationResult:
        size = path.stat().st_size
        if size <= 0:
            return OperationResult(False, "Mesh validation failed", "File is empty.")
        dds_hints, texture_candidates, shader_hints, _, extra_hints = self._structured_preview(path)
        resource = parse_resource_header(read_bytes(path, 64))
        msg = f"Mesh-family resource scanned. Embedded texture hints={len(dds_hints)}, shader hints={len(shader_hints)}, ranked companion targets={len(texture_candidates)}"
        if resource:
            msg += f" Resource header={resource['ident_name']} type={resource['resource_type']}."
        return OperationResult(True, "Mesh validation partial", msg)

    def replace_with(self, target: Path, source: Path) -> OperationResult:
        target_ext = target.suffix.lower()
        source_ext = source.suffix.lower()
        if source_ext in self._standalone_texture_exts and target_ext in self._texture_carrier_exts:
            dds_hints, texture_candidates, shader_hints, relation_lines = self._structured_preview(target, source)
            exact_candidates = [c for c in texture_candidates if c["score"] >= 400 and c["path"].suffix.lower() == source_ext]
            if exact_candidates:
                candidate = exact_candidates[0]
                second_score = exact_candidates[1]["score"] if len(exact_candidates) > 1 else -1
                clearly_dominant = candidate["score"] >= second_score + 150
                if len(exact_candidates) == 1 or clearly_dominant:
                    compatibility = texture_payload_compatibility(candidate["path"], source)
                    if compatibility.success:
                        result = safe_backup_replace(candidate["path"], source)
                        return OperationResult(True, "Redirected replace complete", f"Selected mesh-family file was treated as a texture carrier.\nResolved a dominant external companion target:\n{candidate['path'].name}\nScore: {candidate['score']}\n\n{result.message}")
            lines = [
                "Direct injection of standalone textures into mesh-carried texture lanes is not implemented in the fallback workbench.",
                f"Target classification: {self._classify(target_ext)[0]}",
                "",
                "Embedded texture-name hints discovered:",
                *([f"- {h}" for h in dds_hints] if dds_hints else ["- none found by heuristic scan"]),
                "",
                "Embedded shader/fxc hints discovered:",
                *([f"- {h}" for h in shader_hints] if shader_hints else ["- none found by heuristic scan"]),
            ]
            if relation_lines:
                lines.extend(["", "Ranked external companion targets:"])
                lines.extend(relation_lines)
            lines.extend(["", "Safe action taken:", "- Wrote this replacement plan instead of mutating the mesh-family binary blindly."])
            plan = write_plan_file(target, source, "Mesh Texture Carrier Replacement Plan", lines)
            return OperationResult(True, "Plan written", f"Direct mesh-carried texture injection was not attempted. Replacement plan written to:\n{plan}")
        if source_ext == target_ext:
            return safe_backup_replace(target, source)
        return OperationResult(False, "Replace blocked", "Mesh-family resources only support same-extension whole-file replacement in the fallback workbench, or guarded companion targeting for DDS/PNG texture candidates.")



class SourceCodeModule(ModuleBase):
    name = "Source"
    extensions = SOURCE_CODE_EXTENSIONS
    summary = "Editable code-bearing source lane with explicit proof labels: Python is syntax-aware, and native helper-source probes can be compile-aware when host compilers are available."
    capabilities = [
        FormatCapability('.c', 'Source', 'V/E/X/I', 'Editable C source lane. Uses host compile-aware validation when a native compiler is available.'),
        FormatCapability('.cs', 'Source', 'V/E/X', 'Editable C# source lane. Uses host compile-aware validation when csc or mcs is available.'),
        FormatCapability('.py', 'Source', 'V/E/X/I', 'Editable Python source lane with AST-based syntax-aware validation.'),
        FormatCapability('.lua', 'Source', 'V/E/X', 'Editable Lua source lane. Syntax-aware validation is pending donor-backed parser integration.'),
    ]

    def inspect(self, path: Path) -> ModuleInspection:
        data = read_bytes(path)
        text = decode_best_effort(data)
        analysis = _codered_analyze_source_text(path, text)
        details = [
            f"Path: {path}",
            f"Size: {path.stat().st_size:,} bytes",
            f"Language: {analysis['language']}",
            f"Proof level: {analysis['proof_level']}",
            f"Lines: {analysis['line_count']:,} ({analysis['non_empty_lines']:,} non-empty)",
            f"Characters: {analysis['char_count']:,}",
            f"Syntax status: {analysis['syntax_status']}",
            f"Validation tool: {analysis['tool_name'] if analysis['tool_name'] else 'none wired for this file family in this runtime'}",
        ]
        warning = "Edits are allowed, but rebuild/compile safety is not implied unless the proof level explicitly says so."
        return ModuleInspection(
            self.name,
            f"Source - {path.name}",
            "Code-bearing source inspection routed successfully.",
            "\n".join(details),
            warning,
            text,
            can_edit_preview_text=True,
        )

    def validate(self, path: Path) -> OperationResult:
        text = decode_best_effort(read_bytes(path))
        analysis = _codered_analyze_source_text(path, text)
        if analysis['syntax_ok']:
            return OperationResult(True, 'Source validation passed', f"{analysis['language']} validated at proof level {analysis['proof_level']}. {analysis['syntax_status']}")
        if analysis['syntax_error']:
            return OperationResult(False, 'Source validation failed', f"{analysis['language']} failed validation at proof level {analysis['proof_level']}. {analysis['syntax_status']}")
        title = 'Source validation partial'
        message = f"{analysis['language']} routed as editable text at proof level {analysis['proof_level']}. {analysis['syntax_status']}"
        return OperationResult(True, title, message)


class ScriptsModule(ModuleBase):
    name = "Scripts"
    extensions = SCRIPT_BINARY_EXTENSIONS
    summary = "Compiled script lane with pseudo-decompile export, round-trip clone verification, and archive-copy probe validation for exact-size candidates."
    capabilities = [
        FormatCapability(".wsc", "Scripts", "V/E/P", "Binary compiled script resource. Script Lab supports pseudo-decompile export, round-trip clone verification, and archive-copy probe validation for exact-size candidates."),
    ]

    def inspect(self, path: Path) -> ModuleInspection:
        data = read_bytes(path)
        resource = parse_resource_header(data)
        payload_info = extract_resource_payload(data, resource) if resource else {'payload': data, 'notes': []}
        analysis_bytes = payload_info.get('payload', data) or data
        textlike = is_probably_text(analysis_bytes) and resource is None and path.suffix.lower() not in SCRIPT_BINARY_EXTENSIONS
        preview_strings = [] if textlike else extract_candidate_strings(analysis_bytes, limit=120)
        warning = "Decompiler-style .c output is readable only. It is not treated as safe round-trip source."
        details = [f"Path: {path}", f"Size: {path.stat().st_size:,} bytes", f"Text-like after payload processing: {textlike}"]
        append_resource_lines(details, resource)
        if resource:
            details.append('Resource payload processing:')
            details.extend(f"- {note}" for note in payload_info.get('notes', []))
        if not textlike:
            details.append(f"Candidate strings extracted: {len(preview_strings)}")
        return ModuleInspection(
            self.name,
            f"Scripts - {path.name}",
            "Script inspection routed successfully." if not resource else "Compiled script inspection with resource-header aware payload analysis routed successfully.",
            "\n".join(details),
            warning,
            decode_best_effort(analysis_bytes) if textlike else ("\n".join(preview_strings[:120]) if preview_strings else hex_preview(data)),
            can_edit_preview_text=False,
        )

    def validate(self, path: Path) -> OperationResult:
        data = read_bytes(path, 65536)
        resource = parse_resource_header(data)
        payload_info = extract_resource_payload(data, resource) if resource else {'payload': data, 'notes': []}
        analysis_bytes = payload_info.get('payload', data) or data
        strings = extract_candidate_strings(analysis_bytes, limit=20)
        msg = f"Compiled or binary script path detected. Extracted {len(strings)} candidate strings after payload processing."
        if resource:
            msg += f" Resource header={resource['ident_name']} type={resource['resource_type']}."
        return OperationResult(True, "Script validation partial", msg)


class AudioModule(ModuleBase):
    name = "Audio"
    extensions = (".awc", ".dat", ".wav")
    summary = "Audio lane with AWC/WAV header validation and DAT staging."
    capabilities = [
        FormatCapability(".awc", "Audio", "V/E/P", "AWC playback/export donor path is staged."),
        FormatCapability(".dat", "Audio", "V/E/P", "DAT analysis path is present."),
        FormatCapability(".wav", "Audio", "V/E", "WAV validation is live."),
    ]

    def inspect(self, path: Path) -> ModuleInspection:
        data = read_bytes(path)
        summary = "Audio inspection baseline."
        details = f"Path: {path}\nSize: {path.stat().st_size:,} bytes\nExtension: {path.suffix.lower()}"
        warning = ""
        if data[:4] == b"TADA":
            summary = "AWC signature detected."
        elif data[:4] == b"RIFF" and data[8:12] == b"WAVE":
            summary = "WAV signature detected."
        elif path.suffix.lower() == ".dat":
            warning = "DAT structure-aware analysis is still staged behind the host merge."
        return ModuleInspection(self.name, f"Audio - {path.name}", summary, details, warning, hex_preview(data))

    def validate(self, path: Path) -> OperationResult:
        data = read_bytes(path, 16)
        sfx = path.suffix.lower()
        if sfx == ".awc":
            return OperationResult(data[:4] == b"TADA", "Audio validation passed" if data[:4] == b"TADA" else "Audio validation failed", "AWC signature detected." if data[:4] == b"TADA" else "Missing TADA header.")
        if sfx == ".wav":
            ok = len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE"
            return OperationResult(ok, "Audio validation passed" if ok else "Audio validation failed", "WAV signature detected." if ok else "Missing RIFF/WAVE header.")
        return OperationResult(True, "Audio validation partial", "DAT or unknown audio-family asset routed successfully.")


WTB_TILE_RE = re.compile(r'^(?P<x>[0-9a-fA-F]{4})(?P<y>[0-9a-fA-F]{4})_bnd\.wtb$')


def _codered_signed16_from_hex(text: str) -> int:
    value = int(text, 16)
    return value - 0x10000 if value & 0x8000 else value


def _codered_wtb_tile_metadata(path: Path) -> dict:
    match = WTB_TILE_RE.match(path.name)
    if not match:
        return {}
    x_hex = match.group('x').lower()
    y_hex = match.group('y').lower()
    x = _codered_signed16_from_hex(x_hex)
    y = _codered_signed16_from_hex(y_hex)
    return {
        'grid_x_hex': x_hex,
        'grid_y_hex': y_hex,
        'grid_x_s16': x,
        'grid_y_s16': y,
        'grid_x_u16': int(x_hex, 16),
        'grid_y_u16': int(y_hex, 16),
        'cell_size_guess': 0x40,
        'world_min_guess': f'{x}, {y}',
        'world_max_guess': f'{x + 0x40}, {y + 0x40}',
    }


def _codered_float3_samples(data: bytes, limit: int = 24) -> list[str]:
    rows: list[str] = []
    for off in range(0, max(0, len(data) - 12), 4):
        x, y, z = struct.unpack_from('<3f', data, off)
        if all(-100000.0 <= v <= 100000.0 and v == v for v in (x, y, z)) and max(abs(x), abs(y), abs(z)) >= 1.0:
            rows.append(f'- 0x{off:06X}: {x:.6g}, {y:.6g}, {z:.6g}')
            if len(rows) >= limit:
                break
    return rows


class WorldModule(ModuleBase):
    name = "World"
    extensions = (".wsi", ".wtb", ".wtl", ".wsg", ".wsp", ".wnm", ".wcg", ".wgd")
    summary = "World/runtime resource inspection lane, including terrain-bound WTB resources."
    capabilities = [
        FormatCapability(".wsi", "World", "V/E/X/I/P", "High-value sector/world target."),
        FormatCapability(".wtb", "World", "V/E/X/I/P", "Terrain-bound tile resource; RSC05/zstd payload inspection and archive-copy replacement are available."),
        FormatCapability(".wnm", "World", "V/E/P", "Navmesh inspection target."),
    ]

    def inspect(self, path: Path) -> ModuleInspection:
        data = read_bytes(path)
        suffix = path.suffix.lower()
        resource = parse_resource_header(data)
        payload_info = extract_resource_payload(data, resource) if resource else {'payload': data, 'notes': ['No RSC header detected.']}
        payload = payload_info.get('payload', data) or data
        details = [
            f"Path: {path}",
            f"Size: {path.stat().st_size:,} bytes",
            f"Extension: {suffix}",
        ]
        append_resource_lines(details, resource)
        if suffix == '.wtb':
            tile = _codered_wtb_tile_metadata(path)
            if tile:
                details.extend([
                    'Terrain-bound tile metadata:',
                    f"- Grid hex: {tile['grid_x_hex']}, {tile['grid_y_hex']}",
                    f"- Grid signed: {tile['grid_x_s16']}, {tile['grid_y_s16']}",
                    f"- Grid unsigned: {tile['grid_x_u16']}, {tile['grid_y_u16']}",
                    f"- Cell size guess: {tile['cell_size_guess']}",
                    f"- World bounds guess: {tile['world_min_guess']} -> {tile['world_max_guess']}",
                ])
            if resource:
                details.append('Resource payload processing:')
                details.extend(f"- {note}" for note in payload_info.get('notes', []))
            details.extend([
                f"Decoded/analysis payload size: {len(payload):,} bytes",
                f"Decoded/analysis payload SHA1: {_codered_sha1_hex(payload)}",
            ])
            strings = extract_candidate_strings(payload, limit=24)
            if strings:
                details.append('Candidate strings:')
                details.extend(f"- {item}" for item in strings[:24])
            float_lines = _codered_float3_samples(payload)
            if float_lines:
                details.append('Float3 candidate sample:')
                details.extend(float_lines)
            warning = "WTB semantic editing is still conservative. Use Archive Browser replacement or tools/codered_terrainboundres_tool.py to patch only copied archives with verification."
            return ModuleInspection(self.name, f"World WTB - {path.name}", "Terrain-bound WTB inspection routed with RSC/zstd payload analysis.", "\n".join(details), warning, hex_preview(payload))
        if resource:
            details.append('Resource payload processing:')
            details.extend(f"- {note}" for note in payload_info.get('notes', []))
        return ModuleInspection(self.name, f"World - {path.name}", "World/runtime resource inspection routed successfully.", "\n".join(details), "Deep world/map services remain part of the longer host merge path.", hex_preview(payload))

    def validate(self, path: Path) -> OperationResult:
        if path.suffix.lower() == '.wtb':
            data = read_bytes(path)
            resource = parse_resource_header(data)
            if not resource:
                return OperationResult(False, "WTB validation failed", "Missing RSC05 resource header.")
            if resource.get('resource_type') != 36:
                return OperationResult(False, "WTB validation failed", f"Expected resource type 36, got {resource.get('resource_type')}.")
            payload_info = extract_resource_payload(data, resource)
            payload = payload_info.get('payload') or b''
            if not payload:
                return OperationResult(False, "WTB validation failed", "WTB resource payload could not be decoded.")
            return OperationResult(True, "WTB validation passed", f"RSC resource type 36 decoded for inspection. Payload size={len(payload):,} bytes.")
        return OperationResult(path.stat().st_size > 0, "World validation partial" if path.stat().st_size > 0 else "World validation failed", "World asset is present." if path.stat().st_size > 0 else "File is empty.")


ALL_MODULES: List[ModuleBase] = [
    ArchiveModule(), StringsModule(), TexturesModule(), MeshesModule(), SourceCodeModule(), ScriptsModule(), AudioModule(), WorldModule()
]
MODULE_BY_NAME = {m.name: m for m in ALL_MODULES}


def infer_module_for_path(path: Path) -> Optional[ModuleBase]:
    for mod in ALL_MODULES:
        if mod.can_handle(path):
            return mod
    if path.suffix.lower() == '' and path.exists() and path.is_file():
        try:
            data = read_bytes(path, 65536)
            resource = parse_resource_header(data)
            payload_info = extract_resource_payload(data, resource) if resource else {'payload': data, 'notes': []}
            analysis_bytes = payload_info.get('payload', data) or data
            if is_probably_text(analysis_bytes):
                return MODULE_BY_NAME.get('Strings')
            extracted = extract_candidate_strings(analysis_bytes, limit=32)
            if len(extracted) >= 4 and any(len(item) >= 12 for item in extracted):
                return MODULE_BY_NAME.get('Strings')
        except Exception:
            pass
    return None


def _codered_module_name_for_virtual_path(name: str) -> str:
    suffix = Path(name).suffix.lower()
    for mod in ALL_MODULES:
        if suffix in mod.extensions:
            return mod.name
    return 'Unknown'


def _codered_storage_kind(entry: dict) -> str:
    if entry.get('type') != 'file':
        return 'dir'
    if entry.get('is_resource'):
        return 'resource'
    if entry.get('is_compressed'):
        return 'compressed'
    return 'plain'


def _codered_top_counter_lines(counter: Counter, limit: int = 12, prefix: str = '- ') -> list[str]:
    return [f"{prefix}{key}: {value}" for key, value in counter.most_common(limit)]


def audit_rpf6_archive(path: Path, include_hashes: bool = True, include_extract: bool = True) -> Optional[dict]:
    info = parse_rpf6(path)
    if info is None:
        return None
    storage_counts: Counter[str] = Counter()
    module_counts: Counter[str] = Counter()
    extract_success = 0
    extract_fail = 0
    entries_audit: list[dict] = []
    largest_files: list[dict] = []
    script_entries: list[dict] = []
    code_entries: list[dict] = []

    for ent in info['entries']:
        row = {
            'index': int(ent.get('index') or 0),
            'type': ent.get('type', ''),
            'name': ent.get('name', ''),
            'path': ent.get('path', ''),
            'extension': ent.get('extension', ''),
            'storage': _codered_storage_kind(ent),
        }
        if ent.get('type') != 'file':
            entries_audit.append(row)
            continue
        row['size_in_archive'] = int(ent.get('size_in_archive') or 0)
        row['total_size'] = int(ent.get('total_size') or 0)
        row['offset'] = int(ent.get('offset') or 0)
        row['module'] = _codered_module_name_for_virtual_path(row['name'])
        storage_counts[row['storage']] += 1
        module_counts[row['module']] += 1
        if include_hashes:
            try:
                slot = _codered_read_archive_slot_bytes(path, ent)
                row['slot_sha1'] = _codered_sha1_hex(slot)
            except Exception as exc:
                row['slot_sha1_error'] = str(exc)
        if include_extract:
            try:
                extracted = extract_rpf_entry(path, ent)
                row['extract_ok'] = True
                row['extracted_size'] = len(extracted)
                if include_hashes:
                    row['extracted_sha1'] = _codered_sha1_hex(extracted)
                resource = parse_resource_header(extracted)
                if resource:
                    row['resource_ident'] = resource.get('ident_name', '')
                    row['resource_type'] = int(resource.get('resource_type') or 0)
                    row['resource_total_size'] = int(resource.get('total_size') or 0)
                    payload_info = extract_resource_payload(extracted, resource)
                    payload = payload_info.get('payload', extracted) or extracted
                    row['processed_payload_size'] = len(payload)
                    coded_payload = payload_info.get('coded_payload')
                    if coded_payload is not None:
                        row['coded_payload_size'] = len(coded_payload)
                    zstd_frame = payload_info.get('zstd_frame')
                    if zstd_frame:
                        row['zstd_window_size'] = zstd_frame.get('window_size')
                        row['zstd_checksum'] = bool(zstd_frame.get('checksum_flag'))
                extract_success += 1
            except Exception as exc:
                row['extract_ok'] = False
                row['extract_error'] = str(exc)
                extract_fail += 1
        largest_files.append(row)
        if row['extension'] in SCRIPT_BINARY_EXTENSIONS:
            script_entries.append(row)
        if _codered_is_code_bearing_extension(row['extension']):
            code_entries.append(row)
        entries_audit.append(row)

    largest_files = sorted(largest_files, key=lambda item: int(item.get('size_in_archive') or 0), reverse=True)
    return {
        'archive_path': str(path),
        'entry_count': info['entry_count'],
        'file_count': info['file_count'],
        'dir_count': info['dir_count'],
        'resolved_count': info['resolved_count'],
        'storage_counts': storage_counts,
        'module_counts': module_counts,
        'extension_counts': info['ext_counts'],
        'extract_success': extract_success,
        'extract_fail': extract_fail,
        'script_entry_count': len(script_entries),
        'script_entries': script_entries,
        'code_entry_count': len(code_entries),
        'code_entries': code_entries,
        'largest_files': largest_files[:20],
        'entries': entries_audit,
    }


def render_rpf6_audit_report(audit: dict) -> str:
    lines = [
        'Code RED Archive Totality Audit',
        '===============================',
        '',
        f"Archive: {audit['archive_path']}",
        f"Entries: {audit['entry_count']}  Files: {audit['file_count']}  Directories: {audit['dir_count']}",
        f"Resolved names: {audit['resolved_count']}/{audit['entry_count']}",
        f"Extract success: {audit['extract_success']}  Extract fail: {audit['extract_fail']}",
        f"Compiled script entries: {audit['script_entry_count']}",
        f"Code-bearing entries: {audit.get('code_entry_count', 0)}",
        '',
        'Storage profile:',
    ]
    lines.extend(_codered_top_counter_lines(audit['storage_counts']))
    lines.extend(['', 'Module routing profile:'])
    lines.extend(_codered_top_counter_lines(audit['module_counts']))
    lines.extend(['', 'Contained extensions:'])
    lines.extend(_codered_top_counter_lines(audit['extension_counts']))
    lines.extend(['', 'Largest file entries:'])
    for row in audit['largest_files'][:12]:
        extract_state = 'ok' if row.get('extract_ok') else ('fail' if row.get('extract_ok') is False else 'n/a')
        lines.append(
            f"- {row.get('path', '')} | storage={row.get('storage', '')} | module={row.get('module', 'Unknown')} | size_in_archive={int(row.get('size_in_archive') or 0):,} | extracted={int(row.get('extracted_size') or 0):,} | extract={extract_state}"
        )
    if audit['script_entries']:
        lines.extend(['', 'Compiled script entries:'])
        for row in audit['script_entries']:
            extra = []
            if row.get('processed_payload_size'):
                extra.append(f"processed_payload={int(row.get('processed_payload_size') or 0):,}")
            if row.get('coded_payload_size') is not None:
                extra.append(f"coded_payload={int(row.get('coded_payload_size') or 0):,}")
            if row.get('zstd_window_size'):
                extra.append(f"zstd_window={int(row.get('zstd_window_size') or 0):,}")
            suffix = (' | ' + ' | '.join(extra)) if extra else ''
            lines.append(f"- {row.get('path', '')} | storage={row.get('storage', '')} | extracted={int(row.get('extracted_size') or 0):,}{suffix}")
    if audit.get('code_entries'):
        lines.extend(['', 'Code-bearing entries:'])
        for row in audit['code_entries'][:24]:
            lines.append(f"- {row.get('path', '')} | storage={row.get('storage', '')} | module={row.get('module', 'Unknown')} | extracted={int(row.get('extracted_size') or 0):,}")
    lines.extend(['', 'Per-entry digest:'])
    for row in audit['entries']:
        if row.get('type') != 'file':
            continue
        extract_state = 'ok' if row.get('extract_ok') else ('fail' if row.get('extract_ok') is False else 'n/a')
        line = f"- [{row.get('index')}] {row.get('path', '')} | ext={row.get('extension', '')} | storage={row.get('storage', '')} | module={row.get('module', 'Unknown')} | size={int(row.get('size_in_archive') or 0):,} | extract={extract_state}"
        if row.get('slot_sha1'):
            line += f" | slot_sha1={row['slot_sha1']}"
        if row.get('extracted_sha1'):
            line += f" | extracted_sha1={row['extracted_sha1']}"
        if row.get('extract_error'):
            line += f" | error={row['extract_error']}"
        lines.append(line)
    return '\n'.join(lines)


def export_rpf6_audit_bundle(archive_path: Path, base_target: Path) -> tuple[Path, Path]:
    audit = audit_rpf6_archive(archive_path)
    if audit is None:
        raise ValueError('Could not parse RPF6 archive for audit export.')
    text_target = base_target if base_target.suffix.lower() == '.txt' else base_target.with_suffix('.txt')
    json_target = text_target.with_suffix('.json')
    text_target.write_text(render_rpf6_audit_report(audit), encoding='utf-8')
    json_target.write_text(json.dumps(audit, indent=2, default=list), encoding='utf-8')
    return text_target, json_target


def _codered_internal_rel_path(internal_path: str, fallback_name: str) -> Path:
    parts = [part for part in internal_path.replace('\\', '/').split('/') if part not in {'', '.', '..'}]
    if parts and parts[0].lower() == 'root':
        parts = parts[1:]
    if not parts:
        parts = [fallback_name]
    return Path(*parts)


def render_rpf6_contents_manifest_report(manifest: dict) -> str:
    lines = [
        'Code RED Archive Contents Bundle',
        '==============================',
        '',
        f"Archive: {manifest['archive_path']}",
        f"Extract root: {manifest['extract_root']}",
        f"Files exported: {manifest['file_count']}",
        f"Export success: {manifest['extract_success']}  Export fail: {manifest['extract_fail']}",
        '',
        'Exported entries:',
    ]
    for row in manifest.get('entries', []):
        status = 'ok' if row.get('export_ok') else ('fail' if row.get('export_ok') is False else 'n/a')
        line = f"- [{row.get('index')}] {row.get('internal_path', '')} | storage={row.get('storage', '')} | module={row.get('module', 'Unknown')} | size={int(row.get('size_in_archive') or 0):,} | export={status}"
        if row.get('relative_output_path'):
            line += f" | out={row['relative_output_path']}"
        if row.get('slot_sha1'):
            line += f" | slot_sha1={row['slot_sha1']}"
        if row.get('exported_sha1'):
            line += f" | exported_sha1={row['exported_sha1']}"
        if row.get('export_error'):
            line += f" | error={row['export_error']}"
        lines.append(line)
    return '\n'.join(lines)


def export_rpf6_contents_bundle(archive_path: Path, target_dir: Path) -> tuple[Path, Path, Path]:
    info = parse_rpf6(archive_path)
    if info is None:
        raise ValueError('Could not parse RPF6 archive for content export.')
    target_dir.mkdir(parents=True, exist_ok=True)
    extract_root = target_dir / f'{archive_path.stem}_contents'
    extract_root.mkdir(parents=True, exist_ok=True)
    manifest_entries = []
    extract_success = 0
    extract_fail = 0
    file_entries = [ent for ent in info.get('entries', []) if ent.get('type') == 'file']
    for ent in file_entries:
        internal_path = ent.get('path', '')
        rel_path = _codered_internal_rel_path(internal_path, Path(ent.get('name', '')).name or f"entry_{ent.get('index', 0)}")
        out_path = extract_root / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            'index': ent.get('index'),
            'internal_path': internal_path,
            'name': ent.get('name', ''),
            'extension': ent.get('extension', ''),
            'module': _codered_module_name_for_virtual_path(internal_path),
            'storage': _codered_storage_kind(ent),
            'size_in_archive': int(ent.get('size_in_archive') or 0),
            'total_size': int(ent.get('total_size') or 0),
            'relative_output_path': str(rel_path).replace('\\', '/'),
        }
        try:
            slot_bytes = _codered_read_archive_slot_bytes(archive_path, ent)
            row['slot_sha1'] = _codered_sha1_hex(slot_bytes)
        except Exception as exc:
            row['slot_sha1_error'] = str(exc)
        try:
            data = extract_rpf_entry(archive_path, ent)
            out_path.write_bytes(data)
            row['export_ok'] = True
            row['exported_size'] = len(data)
            row['exported_sha1'] = _codered_sha1_hex(data)
            extract_success += 1
        except Exception as exc:
            row['export_ok'] = False
            row['export_error'] = str(exc)
            extract_fail += 1
        manifest_entries.append(row)
    manifest = {
        'archive_path': str(archive_path),
        'extract_root': str(extract_root),
        'file_count': len(file_entries),
        'extract_success': extract_success,
        'extract_fail': extract_fail,
        'entries': manifest_entries,
    }
    text_target = target_dir / f'{archive_path.stem}_contents_manifest.txt'
    json_target = target_dir / f'{archive_path.stem}_contents_manifest.json'
    text_target.write_text(render_rpf6_contents_manifest_report(manifest), encoding='utf-8')
    json_target.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return extract_root, text_target, json_target


class ImagePreviewDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, image_path: Path, title: Optional[str] = None, on_saved: Optional[Callable[[str, Path], None]] = None):
        super().__init__(master)
        self.image_path = Path(image_path)
        self.on_saved = on_saved
        self._ops: List[str] = []
        self._temp_preview_file: Optional[str] = None
        dims = get_image_dimensions(self.image_path)
        if dims is None:
            raise ValueError(f"Could not open image for preview: {self.image_path}")
        self.image_size = dims
        self.title(title or f"Image Preview - {self.image_path.name}")
        self.geometry("1120x820")
        self.minsize(780, 520)
        c = getattr(master, 'theme', {'bg': '#000000', 'panel': '#050505', 'fg': '#FFFFFF', 'button': '#151515', 'accent': '#8B0000'})
        self.configure(bg=c['bg'])
        header = tk.Frame(self, bg=c['bg'])
        header.pack(fill='x', padx=12, pady=(12, 8))
        tk.Label(header, text=self.image_path.name, font=("SegoeUI", 15, "bold"), bg=c['bg'], fg=c['fg'], anchor='w').pack(fill='x')
        tk.Label(header, text=f"Format: {self.image_path.suffix.upper().lstrip('.')}  Size: {self.image_size[0]}x{self.image_size[1]}", bg=c['bg'], fg=c['fg'], anchor='w').pack(fill='x', pady=(4,0))

        controls = tk.Frame(self, bg=c['bg'])
        controls.pack(fill='x', padx=12, pady=(0, 8))
        self._mkbtn(controls, 'Rotate ⟲', self._rotate_left, c).pack(side='left', padx=(0,8))
        self._mkbtn(controls, 'Rotate ⟳', self._rotate_right, c).pack(side='left', padx=(0,8))
        self._mkbtn(controls, 'Flip Horizontal', self._flip_horizontal, c).pack(side='left', padx=(0,8))
        self._mkbtn(controls, 'Flip Vertical', self._flip_vertical, c).pack(side='left', padx=(0,8))
        self._mkbtn(controls, 'Reset', self._reset, c).pack(side='left', padx=(0,8))
        self._mkbtn(controls, 'Save as PNG', self._save_png, c, accent=True).pack(side='left', padx=(12,8))
        if self.image_path.suffix.lower() == '.png':
            self._mkbtn(controls, 'Save Over PNG', self._save_png_overwrite, c, accent=True).pack(side='left', padx=(0,8))
        self._mkbtn(controls, 'Close', self._on_close, c).pack(side='right')

        frame = tk.Frame(self, bg=c['panel'], highlightbackground=c['accent'], highlightthickness=1)
        frame.pack(fill='both', expand=True, padx=12, pady=(0,12))
        self.canvas = tk.Canvas(frame, bg=c['panel'], highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<Configure>', lambda _e: self._render())
        self._tk_image = None
        self.protocol('WM_DELETE_WINDOW', self._on_close)
        self._render()

    def _mkbtn(self, parent, text, command, colors, accent=False):
        return tk.Button(parent, text=text, command=command, bg=colors['accent' if accent else 'button'], fg=colors['fg'], relief='flat', padx=12, pady=7)

    def _rotate_left(self):
        self._ops.append('-rotate')
        self._ops.append('90')
        self._render()

    def _rotate_right(self):
        self._ops.append('-rotate')
        self._ops.append('-90')
        self._render()

    def _flip_horizontal(self):
        self._ops.append('-flop')
        self._render()

    def _flip_vertical(self):
        self._ops.append('-flip')
        self._render()

    def _reset(self):
        self._ops.clear()
        self._render()

    def _on_close(self):
        if self._temp_preview_file:
            try:
                Path(self._temp_preview_file).unlink(missing_ok=True)
            except Exception:
                pass
        self.destroy()

    def _build_convert_command(self, resize: Optional[tuple[int, int]] = None, output: Optional[str] = None) -> List[str]:
        if IMAGE_MAGICK_BIN:
            cmd = [IMAGE_MAGICK_BIN]
            if Path(IMAGE_MAGICK_BIN).name == 'magick':
                cmd.append('convert')
            cmd.append(str(self.image_path))
            cmd.extend(self._ops)
            if resize:
                cmd.extend(['-resize', f'{resize[0]}x{resize[1]}'])
            cmd.append(output or 'png:-')
            return cmd
        raise RuntimeError('No image converter available.')

    def _save_png(self):
        target = filedialog.asksaveasfilename(parent=self, title='Save Image as PNG', defaultextension='.png', filetypes=[('PNG image','*.png')], initialfile=self.image_path.stem + '.png')
        if target:
            try:
                subprocess.run(self._build_convert_command(output=str(target)), check=True, capture_output=True)
                target_path = Path(target)
                if self.on_saved is not None:
                    self.on_saved('save_png', target_path)
                messagebox.showinfo('Saved', f'Saved PNG preview to\n{target}', parent=self)
            except Exception as exc:
                messagebox.showerror('Save failed', str(exc), parent=self)

    def _save_png_overwrite(self):
        try:
            subprocess.run(self._build_convert_command(output=str(self.image_path)), check=True, capture_output=True)
            if self.on_saved is not None:
                self.on_saved('overwrite_png', self.image_path)
            messagebox.showinfo('Saved', f'Overwrote PNG file\n{self.image_path}', parent=self)
        except Exception as exc:
            messagebox.showerror('Save failed', str(exc), parent=self)

    def _render(self):
        self.canvas.delete('all')
        if not IMAGE_MAGICK_BIN:
            self.canvas.create_text(20, 20, anchor='nw', fill='#FFFFFF', text='Image preview unavailable (no converter).')
            return
        cw = max(self.canvas.winfo_width(), 1)
        ch = max(self.canvas.winfo_height(), 1)
        max_w = max(cw - 20, 1)
        max_h = max(ch - 20, 1)
        fd, temp_name = tempfile.mkstemp(prefix='rdr1_img_preview_', suffix='.png')
        os.close(fd)
        try:
            if self._temp_preview_file:
                Path(self._temp_preview_file).unlink(missing_ok=True)
        except Exception:
            pass
        self._temp_preview_file = temp_name
        try:
            subprocess.run(self._build_convert_command(resize=(max_w, max_h), output=temp_name), check=True, capture_output=True)
            self._tk_image = tk.PhotoImage(file=temp_name)
            self.canvas.create_image(cw // 2, ch // 2, image=self._tk_image, anchor='center')
        except Exception as exc:
            self.canvas.create_text(20, 20, anchor='nw', fill='#FFFFFF', text=f'Image preview failed: {exc}')


class TextPreviewDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, title: str, text: str, editable: bool, save_callback: Optional[Callable[[str], None]] = None):
        super().__init__(master)
        self.title(title)
        self.geometry("1000x700")
        self.minsize(800, 500)
        c = getattr(master, "theme", {"bg": "#000000", "panel": "#050505", "fg": "#FFFFFF", "button": "#151515", "accent": "#8B0000"})
        self.configure(bg=c["bg"])
        self.save_callback = save_callback
        self.textbox = tk.Text(self, wrap="none", undo=True, maxundo=-1, bg=c["panel"], fg=c["fg"], insertbackground=c["fg"], relief="flat")
        self.textbox.insert("1.0", text)
        if not editable:
            self.textbox.configure(state="disabled")
        self.textbox.pack(fill="both", expand=True, padx=12, pady=(12, 6))
        btns = tk.Frame(self, bg=c["bg"])
        btns.pack(fill="x", padx=12, pady=(0, 12))
        if editable:
            if save_callback is not None:
                tk.Button(btns, text="Save", command=self._save, bg=c["accent"], fg=c["fg"], relief="flat", padx=16, pady=8).pack(side="left")
            tk.Button(btns, text="Undo", command=self._undo, bg=c["button"], fg=c["fg"], relief="flat", padx=14, pady=8).pack(side="left", padx=(8, 0))
            tk.Button(btns, text="Redo", command=self._redo, bg=c["button"], fg=c["fg"], relief="flat", padx=14, pady=8).pack(side="left", padx=(8, 0))
            self.bind('<Control-s>', lambda _e: self._save())
            self.bind('<Control-z>', lambda _e: self._undo())
            self.bind('<Control-y>', lambda _e: self._redo())
        tk.Button(btns, text="Close", command=self.destroy, bg=c["button"], fg=c["fg"], relief="flat", padx=16, pady=8).pack(side="right")

    def _save(self) -> None:
        if self.save_callback is not None:
            self.save_callback(self.textbox.get("1.0", "end-1c"))

    def _undo(self) -> None:
        try:
            self.textbox.edit_undo()
        except Exception:
            pass

    def _redo(self) -> None:
        try:
            self.textbox.edit_redo()
        except Exception:
            pass

class ArchiveBrowserDialog(tk.Toplevel):
    def __init__(self, master: "WorkbenchApp", archive_path: Path, info: dict):
        super().__init__(master)
        self.master_app = master
        self.archive_path = archive_path
        self.info = info
        self.title(f"Code RED - Archive Browser - {archive_path.name}")
        self.geometry("1280x760")
        self.minsize(980, 560)
        c = master.theme
        self.configure(bg=c['bg'])

        header = tk.Frame(self, bg=c['bg'])
        header.pack(fill='x', padx=12, pady=(12, 8))
        tk.Label(header, text=archive_path.name, font=("SegoeUI", 15, "bold"), anchor='w', bg=c['bg'], fg=c['fg']).pack(fill='x')
        tk.Label(
            header,
            text=f"Entries: {info['entry_count']}  Files: {info['file_count']}  Directories: {info['dir_count']}  Resolved: {info['resolved_count']}/{info['entry_count']}",
            anchor='w', bg=c['bg'], fg=c['fg']
        ).pack(fill='x', pady=(4, 0))

        filter_row = tk.Frame(self, bg=c['bg'])
        filter_row.pack(fill='x', padx=12, pady=(0, 8))
        tk.Label(filter_row, text='Filter:', bg=c['bg'], fg=c['fg']).pack(side='left')
        self.filter_var = tk.StringVar(value='')
        entry = tk.Entry(filter_row, textvariable=self.filter_var, bg=c['panel'], fg=c['fg'], insertbackground=c['fg'], relief='flat')
        entry.pack(side='left', fill='x', expand=True, padx=(8, 8))
        entry.bind('<KeyRelease>', lambda _e: self.refresh())
        tk.Button(filter_row, text='Refresh', command=self.refresh, bg=c['accent'], fg=c['fg'], relief='flat', padx=12, pady=6).pack(side='left')

        self.tree = ttk.Treeview(self, columns=('type', 'ext', 'storage', 'size', 'path'), show='headings')
        for col, title, width in [
            ('type', 'Type', 70),
            ('ext', 'Ext', 70),
            ('storage', 'Storage', 110),
            ('size', 'Size', 100),
            ('path', 'Path', 820),
        ]:
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width, anchor='w')
        self.tree.pack(fill='both', expand=True, padx=12, pady=(0, 8))
        self.tree.bind('<Double-1>', lambda _e: self.inspect_selected())
        self._id_to_entry: Dict[str, dict] = {}

        buttons = tk.Frame(self, bg=c['bg'])
        buttons.pack(fill='x', padx=12, pady=(0, 12))
        tk.Button(buttons, text='Inspect Routed', command=self.inspect_selected, bg=c['accent'], fg=c['fg'], relief='flat', padx=12, pady=7).pack(side='left', padx=(0, 8))
        tk.Button(buttons, text='Extract Selected', command=self.extract_selected, bg=c['button'], fg=c['fg'], relief='flat', padx=12, pady=7).pack(side='left', padx=(0, 8))
        tk.Button(buttons, text='Replace in Copy', command=self.replace_selected_in_copy, bg=c['button'], fg=c['fg'], relief='flat', padx=12, pady=7).pack(side='left', padx=(0, 8))
        tk.Button(buttons, text='Apply Patch Folder', command=self.apply_patch_folder, bg=c['button'], fg=c['fg'], relief='flat', padx=12, pady=7).pack(side='left', padx=(0, 8))
        tk.Button(buttons, text='Export Audit', command=self.export_audit, bg=c['button'], fg=c['fg'], relief='flat', padx=12, pady=7).pack(side='left', padx=(0, 8))
        tk.Button(buttons, text='Export All', command=self.export_all, bg=c['button'], fg=c['fg'], relief='flat', padx=12, pady=7).pack(side='left', padx=(0, 8))
        tk.Button(buttons, text='Copy Internal Path', command=self.copy_path, bg=c['button'], fg=c['fg'], relief='flat', padx=12, pady=7).pack(side='left', padx=(0, 8))
        tk.Button(buttons, text='Close', command=self.destroy, bg=c['button'], fg=c['fg'], relief='flat', padx=12, pady=7).pack(side='right')
        self.refresh()

    def refresh(self) -> None:
        query = self.filter_var.get().strip().lower()
        self.tree.delete(*self.tree.get_children())
        self._id_to_entry.clear()
        for ent in self.info['entries']:
            path = ent.get('path', '')
            if query and query not in path.lower() and query not in ent.get('name', '').lower() and query not in ent.get('extension', '').lower():
                continue
            storage = 'dir' if ent['type'] == 'dir' else ('resource' if ent.get('is_resource') else ('compressed' if ent.get('is_compressed') else 'plain'))
            size = ent.get('size_in_archive') if ent['type'] == 'file' else ent.get('count', 0)
            iid = self.tree.insert('', 'end', values=(ent['type'], ent.get('extension', ''), storage, size, path))
            self._id_to_entry[iid] = ent

    def _selected_entry(self) -> Optional[dict]:
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning('No archive entry selected', 'Select an internal archive entry first.', parent=self)
            return None
        return self._id_to_entry.get(sel[0])

    def inspect_selected(self) -> None:
        ent = self._selected_entry()
        if not ent:
            return
        if ent['type'] != 'file':
            messagebox.showinfo('Directory selected', 'Select a file entry to inspect.', parent=self)
            return
        try:
            data = extract_rpf_entry(self.archive_path, ent)
        except Exception as exc:
            messagebox.showerror('Extraction failed', f'Could not extract internal entry\n{exc}', parent=self)
            return
        temp_dir = Path(tempfile.mkdtemp(prefix='rdr1_rpf_entry_'))
        out_name = Path(ent['name']).name or f"entry_{ent['index']}"
        temp_path = temp_dir / out_name
        temp_path.write_bytes(data)
        self.master_app.inspect_extracted_entry(temp_path, ent, self.archive_path)

    def extract_selected(self) -> None:
        ent = self._selected_entry()
        if not ent:
            return
        if ent['type'] != 'file':
            messagebox.showinfo('Directory selected', 'Directories cannot be extracted as a single payload.', parent=self)
            return
        target = filedialog.asksaveasfilename(parent=self, title='Extract Archive Entry', initialfile=Path(ent['name']).name or f"entry_{ent['index']}")
        if not target:
            return
        try:
            data = extract_rpf_entry(self.archive_path, ent)
            Path(target).write_bytes(data)
        except Exception as exc:
            messagebox.showerror('Extraction failed', f'Could not extract internal entry\n{exc}', parent=self)
            return
        self.master_app.log(f"Extracted archive entry: {ent['path']} -> {target}")
        messagebox.showinfo('Extraction complete', f'Extracted internal entry to\n{target}', parent=self)

    def _extract_entry_to_temp(self, ent: dict) -> Path:
        data = extract_rpf_entry(self.archive_path, ent)
        temp_dir = Path(tempfile.mkdtemp(prefix='rdr1_rpf_replace_'))
        out_name = Path(ent.get('name', '')).name or f"entry_{ent.get('index', 0)}"
        temp_path = temp_dir / out_name
        temp_path.write_bytes(data)
        return temp_path

    def replace_selected_in_copy(self) -> None:
        ent = self._selected_entry()
        if not ent:
            return
        if ent.get('type') != 'file':
            messagebox.showinfo('Directory selected', 'Select a file entry to replace.', parent=self)
            return
        internal_path = ent.get('path', '')
        suffix = Path(ent.get('name', '')).suffix.lower()
        if suffix in SCRIPT_BINARY_EXTENSIONS:
            messagebox.showinfo('Script entry gated', 'Compiled script archive entries remain on the stricter Script Lab round-trip lane. Use the dedicated script round-trip/archive-probe path instead of archive-browser replacement.', parent=self)
            return
        source = filedialog.askopenfilename(parent=self, title='Replace Archive Entry In Copy')
        if not source:
            return
        source_path = Path(source)
        if source_path.suffix.lower() != suffix:
            messagebox.showerror('Suffix mismatch', f'Replacement suffix must match the selected archive entry\nExpected: {suffix}\nGot: {source_path.suffix.lower()}', parent=self)
            return
        mod = infer_module_for_path(source_path)
        validation = mod.validate(source_path)
        if not validation.success:
            messagebox.showerror(validation.title, validation.message, parent=self)
            return
        try:
            original_extract = self._extract_entry_to_temp(ent)
            probe_result = _codered_apply_non_script_candidate_to_archive_copy(original_extract, source_path, ent, self.archive_path)
        except Exception as exc:
            messagebox.showerror('Archive copy replace failed', str(exc), parent=self)
            return
        lines = [
            'Code RED Archive Copy Replacement Probe',
            '=====================================',
            '',
            f"Archive: {self.archive_path}",
            f"Internal path: {internal_path}",
            f"Selected source: {source_path}",
            f"Validation: {validation.title}",
            validation.message,
            '',
        ]
        for key in ('status', 'reason', 'storage_kind', 'current_slot_sha1', 'current_slot_matches_original_extract', 'archive_slot_exact_size_match', 'archive_slot_size_delta', 'new_size_in_archive', 'probe_archive_path', 'probe_slot_sha1', 'probe_extract_sha1'):
            if key in probe_result:
                lines.append(f"{key}: {probe_result[key]}")
        for note in (probe_result.get('notes') or [])[:6]:
            lines.append(f"note: {note}")
        report_path = source_path.with_name(source_path.name + '.archive_copy_replace_probe.txt')
        report_path.write_text('\n'.join(lines), encoding='utf-8')
        self.master_app.log(f'Archive copy replace report: {report_path}')
        title = 'Archive copy replace verified' if probe_result.get('status') in {'archive_copy_replace_verified', 'archive_copy_replace_relocated_verified'} else ('Archive copy replace unchanged' if probe_result.get('status') == 'identical' else 'Archive copy replace blocked')
        messagebox.showinfo(title, '\n'.join(lines[-10:]) + f"\n\nReport:\n{report_path}", parent=self)

    def apply_patch_folder(self) -> None:
        patch_root = filedialog.askdirectory(parent=self, title='Select Archive Patch Folder')
        if not patch_root:
            return
        patch_path = Path(patch_root)
        try:
            result = _codered_apply_patch_folder_to_archive_copy(self.archive_path, patch_path)
        except Exception as exc:
            messagebox.showerror('Patch folder apply failed', str(exc), parent=self)
            return
        self.master_app.log(f"Archive patch folder applied: {result['applied']} ok, {result.get('relocated', 0)} relocated, {result.get('identical', 0)} identical, {result['blocked']} blocked, {len(result['unmatched'])} unmatched")
        messagebox.showinfo(
            'Patch folder applied',
            f"Working copy: {result['working_copy']}\n\nApplied: {result['applied']}\nRelocated: {result.get('relocated', 0)}\nIdentical: {result.get('identical', 0)}\nBlocked: {result['blocked']}\nUnmatched: {len(result['unmatched'])}\n\nReport:\n{result['report_path']}",
            parent=self,
        )

    def export_all(self) -> None:
        target_dir = filedialog.askdirectory(parent=self, title='Export Full Archive Contents')
        if not target_dir:
            return
        try:
            extract_root, txt_path, json_path = export_rpf6_contents_bundle(self.archive_path, Path(target_dir))
        except Exception as exc:
            messagebox.showerror('Archive export failed', f'Could not export full archive contents\n{exc}', parent=self)
            return
        self.master_app.log(f'Archive contents exported: {extract_root}')
        self.master_app.log(f'Archive contents manifest: {txt_path}')
        self.master_app.log(f'Archive contents manifest: {json_path}')
        messagebox.showinfo('Archive contents exported', f'Extract root:\n{extract_root}\n\nText manifest:\n{txt_path}\n\nJSON manifest:\n{json_path}', parent=self)

    def copy_path(self) -> None:
        ent = self._selected_entry()
        if not ent:
            return
        self.clipboard_clear()
        self.clipboard_append(ent.get('path', ''))
        self.master_app.log(f"Copied archive path: {ent.get('path', '')}")

    def export_audit(self) -> None:
        target = filedialog.asksaveasfilename(parent=self, title='Export Archive Audit', initialfile=f'{self.archive_path.stem}_archive_audit.txt')
        if not target:
            return
        try:
            txt_path, json_path = export_rpf6_audit_bundle(self.archive_path, Path(target))
        except Exception as exc:
            messagebox.showerror('Archive audit export failed', f'Could not export archive audit\n{exc}', parent=self)
            return
        self.master_app.log(f'Archive audit exported: {txt_path}')
        self.master_app.log(f'Archive audit exported: {json_path}')
        messagebox.showinfo('Archive audit exported', f'Text report:\n{txt_path}\n\nJSON report:\n{json_path}', parent=self)


CODERED_REGRESSION_REMINDER_TEXT = """Regression + missing-feature preflight:
- Confirm the authoritative live source file before editing.
- State the requested change and what must remain unchanged.
- Check neighboring systems for regressions or dropped features.
- Search for obvious missing feature hooks before calling a lane complete.
- Validate controls, UI bounds, asset paths, launch/shutdown, and latest crash logs.
- Do not present the patch as finished unless the latest validation pass is clean."""


def _codered_infer_game_dir_from_path(path: Path | None) -> str:
    if path is None:
        return ''
    candidate = path if path.is_dir() else path.parent
    try:
        parents = [candidate, *candidate.parents[:6]]
    except Exception:
        parents = [candidate]
    for parent in parents:
        try:
            if any(parent.glob('*.exe')) or ((parent / 'bin').exists() and any((parent / 'bin').glob('*.exe'))):
                return str(parent)
        except Exception:
            continue
    return str(candidate)


def _codered_write_workbench_crash(exc: BaseException) -> Path:
    CODERED_WORKBENCH_CRASH_DIR.mkdir(parents=True, exist_ok=True)
    stamp = __import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')
    path = CODERED_WORKBENCH_CRASH_DIR / f'code_red_workbench_crash_{stamp}.log'
    payload = [
        'Code RED Workbench Crash',
        '=========================',
        '',
        f'type: {type(exc).__name__}',
        f'message: {exc}',
        '',
        traceback.format_exc(),
    ]
    path.write_text('\n'.join(payload), encoding='utf-8')
    return path



def _codered_text_preview(path: Path, *, limit: int = 9000) -> str:
    try:
        data = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"Preview unavailable: {exc}"
    if len(data) > limit:
        return data[:limit] + "\n\n... preview truncated ..."
    return data


def _codered_safe_rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except Exception:
        return str(path)


def _codered_add_research_entry(entries: list[dict], seen: set[str], *, source: str, topic: str, title: str, path: Path, notes: str = "") -> None:
    try:
        key = str(path.resolve())
    except Exception:
        key = str(path)
    if key in seen:
        return
    seen.add(key)
    exists = path.exists()
    try:
        size = path.stat().st_size if exists and path.is_file() else 0
    except Exception:
        size = 0
    entries.append({
        "source": source,
        "topic": topic or "index",
        "title": title or path.name,
        "path": str(path),
        "relative_path": _codered_safe_rel(CODERED_APP_ROOT, path),
        "format": path.suffix.lstrip(".").lower() or "folder",
        "notes": notes or "",
        "exists": exists,
        "size": size,
    })


def _codered_resolve_manifest_path(root: Path, raw: str) -> Path:
    rel = Path(str(raw or "").strip())
    candidates = []
    if rel.is_absolute():
        candidates.append(rel)
    else:
        candidates.extend([
            root / rel,
            root / "research" / rel,
            root / "logs" / rel,
            root / "docs" / rel,
        ])
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0] if candidates else root / str(raw)


def _codered_load_research_browser_entries(root: Path) -> list[dict]:
    entries: list[dict] = []
    seen: set[str] = set()

    manifest = root / "research" / "CodeRED_RESEARCH_MANIFEST.csv"
    if manifest.exists():
        try:
            with manifest.open("r", encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    path = _codered_resolve_manifest_path(root, row.get("path", ""))
                    _codered_add_research_entry(
                        entries,
                        seen,
                        source="research manifest",
                        topic=row.get("topic", "research"),
                        title=row.get("title", path.name),
                        path=path,
                        notes=row.get("notes", ""),
                    )
        except Exception as exc:
            _codered_add_research_entry(entries, seen, source="error", topic="research", title="Manifest read error", path=manifest, notes=str(exc))

    for path, title, topic in [
        (root / "logs" / "CodeRED_LOG_INDEX.md", "Code RED Log Index", "index"),
        (root / "logs" / "code_red_stage_report_latest.md", "Code RED Stage Report", "status"),
        (root / "README.md", "README", "readme"),
        (root / "docs" / "CodeRED_One_App_Upgrade_Plan_2026-05-03.md", "One-App Upgrade Plan", "planning"),
        (root / "docs" / "REPO_STRUCTURE.md", "Repository Structure", "planning"),
    ]:
        if path.exists():
            _codered_add_research_entry(entries, seen, source="curated", topic=topic, title=title, path=path)

    logs_dir = root / "logs"
    if logs_dir.exists():
        for path in sorted(logs_dir.glob("CodeRED_*.md")):
            _codered_add_research_entry(entries, seen, source="logs", topic="pass/report", title=path.stem.replace("_", " "), path=path)
        for path in sorted(logs_dir.glob("CodeRed_*.txt")):
            _codered_add_research_entry(entries, seen, source="logs", topic="pass/report", title=path.stem.replace("_", " "), path=path)
        for path in sorted(logs_dir.glob("README*.txt")):
            _codered_add_research_entry(entries, seen, source="logs", topic="readme", title=path.stem.replace("_", " "), path=path)
        for path in sorted(logs_dir.glob("CodeRED_*Report*.json")):
            _codered_add_research_entry(entries, seen, source="proof json", topic="proof", title=path.stem.replace("_", " "), path=path)

    research_dir = root / "research"
    if research_dir.exists():
        for pattern in ("CodeRED_*.md", "CodeRed_*.txt", "*_handoff*.md", "*_report*.md"):
            for path in sorted(research_dir.glob(pattern)):
                _codered_add_research_entry(entries, seen, source="research", topic="research", title=path.stem.replace("_", " "), path=path)

    docs_dir = root / "docs"
    if docs_dir.exists():
        for path in sorted(docs_dir.glob("*.md")):
            _codered_add_research_entry(entries, seen, source="docs", topic="docs", title=path.stem.replace("_", " "), path=path)

    for pattern in ("Code_RED_*patch*.zip", "Code_RED_*pass*.zip", "CodeRED_*patch*.zip", "CodeRED_*pass*.zip"):
        for path in sorted(root.glob(pattern)):
            _codered_add_research_entry(entries, seen, source="regression zip", topic="checkpoint", title=path.name, path=path, notes="Regression checkpoint zip")

    entries.sort(key=lambda item: (not bool(item.get("exists")), str(item.get("topic", "")), str(item.get("title", "")).lower()))
    return entries


def _codered_build_research_browser_report(root: Path) -> dict:
    entries = _codered_load_research_browser_entries(root)
    counts = Counter(str(item.get("topic", "unknown")) for item in entries)
    missing = [item for item in entries if not item.get("exists")]
    lines = [
        "Code RED Research Browser Report",
        "================================",
        "",
        f"Root: {root}",
        f"Entries indexed: {len(entries)}",
        f"Missing referenced entries: {len(missing)}",
        "",
        "Topic counts:",
    ]
    for topic, count in sorted(counts.items()):
        lines.append(f"- {topic}: {count}")
    lines.extend(["", "Indexed entries:"])
    for item in entries:
        mark = "OK" if item.get("exists") else "MISSING"
        lines.append(f"- [{mark}] {item.get('topic')} / {item.get('title')} -> {item.get('relative_path')}")
    logs = root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    md = logs / "CodeRED_Research_Browser_Report.md"
    js = logs / "CodeRED_Research_Browser_Report.json"
    payload = {"root": str(root), "entries": entries, "counts": dict(sorted(counts.items())), "missing_count": len(missing)}
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    js.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {"markdown": str(md), "json": str(js), "entries": entries, "counts": payload["counts"], "missing_count": len(missing), "text": "\n".join(lines)}


class WorkbenchApp(tk.Tk):
    def __init__(self, startup_workspace: Optional[Path] = None):
        super().__init__()
        self.title("Code RED")
        self.geometry("1600x960")
        self.minsize(1280, 720)
        self.theme = {"bg": "#000000", "panel": "#060606", "fg": "#FFFFFF", "accent": "#8B0000", "accent_active": "#B00000", "button": "#151515"}
        self.configure(bg=self.theme["bg"])
        self.workspace: Optional[Path] = None
        self.selected_path: Optional[Path] = None
        self.output_boxes: Dict[str, tk.Text] = {}
        self._setup_theme()
        self._build_ui()
        self._populate_one_app_dashboard()
        self._populate_research_browser()
        self._populate_home()
        self._populate_stage()
        self._populate_completion()
        self._populate_capabilities()
        self.log("Code RED ready.")
        self.log("Fallback runner active.")
        if CODERED_NATIVE_DB_COUNT:
            self.log(f"Native DB loaded: {CODERED_NATIVE_DB_COUNT:,} entries.")
        else:
            self.log("Native DB not found yet; Script Lab will fall back to heuristic labeling.")
        if CODERED_PRIMARY_ARCHIVE and CODERED_PRIMARY_ARCHIVE.exists():
            self.log(f"Primary archive target ready: {CODERED_PRIMARY_ARCHIVE}")
        if startup_workspace:
            self.set_workspace(startup_workspace)

    def _setup_theme(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        bg = self.theme["bg"]
        panel = self.theme["panel"]
        fg = self.theme["fg"]
        accent = self.theme["accent"]
        accent_active = self.theme["accent_active"]
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TNotebook", background=bg, borderwidth=0)
        style.configure("TNotebook.Tab", background=accent, foreground=fg, padding=(12, 8))
        style.map("TNotebook.Tab", background=[("selected", accent_active)], foreground=[("selected", fg)])
        style.configure("Treeview", background=panel, foreground=fg, fieldbackground=panel, borderwidth=0)
        style.map("Treeview", background=[("selected", accent)], foreground=[("selected", fg)])
        style.configure("Treeview.Heading", background=accent, foreground=fg)

    def _build_ui(self) -> None:
        c = self.theme
        top = tk.Frame(self, bg=c["bg"])
        top.pack(side="top", fill="x")
        tk.Label(top, text="Code RED", font=("SegoeUI", 16, "bold"), bg=c["bg"], fg=c["fg"]).grid(row=0, column=0, sticky="nw", padx=(10, 18), pady=10)
        toolbar_actions = [
            ("Open Workspace", self.open_workspace),
            ("Open Tuner", self.open_code_red_tuner),
            ("Test Demo", self.open_code_red_test_demo),
            ("Scan Selected Folder", self.scan_workspace),
            ("Inspect Selection", self.inspect_selection),
            ("Refresh Stage Check", self.refresh_stage_report),
            ("Refresh Dashboard", self.refresh_one_app_dashboard),
            ("Write Status Report", self.write_one_app_status_report),
            ("Regression Guard", self.run_regression_guard_lane),
            ("Regression Guard", self.run_regression_guard_lane),
            ("Refresh Research", self.refresh_research_browser),
            ("Write Research Index", self.write_research_browser_report),
            ("Validate AI Trainer", self.validate_ai_trainer_lane),
            ("Validate Archives", self.validate_archive_lane),
            ("Validate File IO", self.validate_file_io_lane),
            ("Validate CodeX", self.validate_codex_modelxml_lane),
            ("Build Native DB", self.build_native_database_lane),
            ("Generate Bridge", self.generate_native_bridge_lane),
            ("Prep AI Bridge", self.prepare_ai_menu_bridge_lane),
            ("Validate Scripts", self.validate_script_compile_lane),
            ("Validate Script Workshop", self.validate_script_workshop_decode_lane),
            ("Prep Script Workshop", self.prepare_script_workshop_compile_lane),
            ("Script Pipeline", self.run_script_pipeline_lane),
            ("Validate Terrain", self.validate_terrainboundres_lane),
            ("Stage Bundled Archive", self.stage_bundled_archive),
            ("Run Archive Proof Pass", self.run_archive_proof_pass),
            ("Audit Primary Archive", self.audit_primary_archive),
            ("Open Imports", self.open_imports_folder),
            ("Open Logs", self.open_logs_folder),
            ("Jump To Archive", self.open_primary_archive_target),
            ("Sync MP Companion", self.sync_mp_companion),
            ("Open MP Companion", self.open_mp_companion),
            ("Build Script Pack", self.export_script_toolchain_pack),
            ("Regression Reminder", self.show_regression_reminder),
            ("Clear Log", self.clear_log),
        ]
        toolbar = tk.Frame(top, bg=c["bg"])
        toolbar.grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=6)
        top.grid_columnconfigure(1, weight=1)
        toolbar_cols = 5
        for idx, (caption, cmd) in enumerate(toolbar_actions):
            btn = tk.Button(toolbar, text=caption, command=cmd, bg=c["accent"], fg=c["fg"], relief="flat", padx=12, pady=8)
            btn.grid(row=idx // toolbar_cols, column=idx % toolbar_cols, sticky="ew", padx=4, pady=4)
        for col in range(toolbar_cols):
            toolbar.grid_columnconfigure(col, weight=1)

        main = tk.PanedWindow(self, orient="horizontal", sashrelief="flat", sashwidth=8, bg=c["bg"])
        main.pack(fill="both", expand=True)

        left = tk.Frame(main, bg=c["bg"])
        right = tk.Frame(main, bg=c["bg"])
        main.add(left, width=360)
        main.add(right)

        self.workspace_var = tk.StringVar(value="Workspace: none")
        self.selection_var = tk.StringVar(value="Selection: none")
        tk.Label(left, textvariable=self.workspace_var, anchor="w").pack(fill="x", padx=10, pady=(10, 4))
        tk.Label(left, textvariable=self.selection_var, anchor="w").pack(fill="x", padx=10, pady=(0, 8))

        self.tree = ttk.Treeview(left, show="tree")
        self.tree.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.node_to_path: Dict[str, Path] = {}

        tk.Label(left, text="Browse the workspace, open supported files, and use the module tools on the active selection.", wraplength=320, justify="left", bg=c["bg"], fg=c["fg"]).pack(fill="x", padx=10, pady=(0, 10))

        self.notebook = ttk.Notebook(right)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.dashboard_frame = self._add_one_app_dashboard_tab()
        self.research_frame = self._add_research_browser_tab()
        self.home_text = self._add_text_tab("Home")
        self.stage_text = self._add_text_tab("Stage")
        self.completion_text = self._add_text_tab("Completion")
        self.cap_tree = ttk.Treeview(self.notebook, columns=("ext", "cat", "cap", "notes"), show="headings")
        for col, title, width in [("ext", "Extension", 100), ("cat", "Category", 100), ("cap", "Capability", 140), ("notes", "Notes", 650)]:
            self.cap_tree.heading(col, text=title)
            self.cap_tree.column(col, width=width, anchor="w")
        self.notebook.add(self.cap_tree, text="Capabilities")

        module_desc = {
            "Archive": "Browse RPF archives, inspect entries, extract files, and apply patch folders to a copied archive.",
            "Strings": "Inspect readable string assets and edit text-like files when a safe text path is available.",
            "Textures": "Validate common texture files and stage guarded replacements for supported texture resources.",
            "Meshes": "Inspect mesh-family files, nearby companions, and texture-carrier relationships.",
            "Source": "Open code-bearing source files for review and editing, with syntax checks where available.",
            "Scripts": "Inspect compiled script resources, export readable working text, and run guarded round-trip checks.",
            "Audio": "Inspect and validate supported audio files without overclaiming playback or rebuild support.",
            "World": "Inspect world-related files and keep structural editing claims conservative until proven.",
        }
        for name, desc in module_desc.items():
            self.output_boxes[name] = self._add_module_tab(name, desc)

        self.log_text = self._add_text_tab("Log")

        self.status_var = tk.StringVar(value="Ready")
        status = tk.Label(self, textvariable=self.status_var, anchor="w", bg=c["accent"], fg=c["fg"])
        status.pack(side="bottom", fill="x")

    def _add_one_app_dashboard_tab(self) -> tk.Frame:
        frame = tk.Frame(self.notebook, bg=self.theme["bg"])
        self.notebook.add(frame, text="Dashboard")

        header = tk.Frame(frame, bg=self.theme["bg"])
        header.pack(fill="x", padx=14, pady=(14, 6))
        self.one_app_summary_var = tk.StringVar(value="One-app status not loaded yet")
        tk.Label(
            header,
            text="Code RED One-App Command Center",
            font=("SegoeUI", 14, "bold"),
            bg=self.theme["accent"],
            fg=self.theme["fg"],
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            header,
            textvariable=self.one_app_summary_var,
            bg=self.theme["bg"],
            fg=self.theme["fg"],
            anchor="w",
            justify="left",
        ).pack(fill="x", pady=(6, 0))

        buttons = tk.Frame(frame, bg=self.theme["bg"])
        buttons.pack(fill="x", padx=14, pady=(0, 8))
        for caption, command in (
            ("Refresh Dashboard", self.refresh_one_app_dashboard),
            ("Write Status Report", self.write_one_app_status_report),
            ("Refresh Research", self.refresh_research_browser),
            ("Write Research Index", self.write_research_browser_report),
            ("Validate AI Trainer", self.validate_ai_trainer_lane),
            ("Validate Archives", self.validate_archive_lane),
            ("Validate File IO", self.validate_file_io_lane),
            ("Validate CodeX", self.validate_codex_modelxml_lane),
            ("Build Native DB", self.build_native_database_lane),
            ("Generate Bridge", self.generate_native_bridge_lane),
            ("Prep AI Bridge", self.prepare_ai_menu_bridge_lane),
            ("Validate Scripts", self.validate_script_compile_lane),
            ("Validate Script Workshop", self.validate_script_workshop_decode_lane),
            ("Prep Script Workshop", self.prepare_script_workshop_compile_lane),
            ("Script Pipeline", self.run_script_pipeline_lane),
            ("Validate Terrain", self.validate_terrainboundres_lane),
            ("Open Logs", self.open_logs_folder),
            ("Open Imports", self.open_imports_folder),
        ):
            tk.Button(buttons, text=caption, command=command, bg=self.theme["accent"], fg=self.theme["fg"], relief="flat", padx=10, pady=6).pack(side="left", padx=(0, 8))

        split = tk.PanedWindow(frame, orient="vertical", sashrelief="flat", sashwidth=6, bg=self.theme["bg"])
        split.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        tree_frame = tk.Frame(split, bg=self.theme["bg"])
        self.one_app_tree = ttk.Treeview(
            tree_frame,
            columns=("state", "category", "lane", "required", "proof"),
            show="headings",
            height=12,
        )
        for col, title, width in (
            ("state", "State", 130),
            ("category", "Category", 120),
            ("lane", "Lane", 280),
            ("required", "Required", 120),
            ("proof", "Proof", 120),
        ):
            self.one_app_tree.heading(col, text=title)
            self.one_app_tree.column(col, width=width, anchor="w")
        self.one_app_tree.pack(fill="both", expand=True)
        self.one_app_tree.bind("<<TreeviewSelect>>", self._on_one_app_lane_select)

        detail_frame = tk.Frame(split, bg=self.theme["bg"])
        self.one_app_detail_text = tk.Text(detail_frame, wrap="word", bg=self.theme["panel"], fg=self.theme["fg"], insertbackground=self.theme["fg"], relief="flat")
        self.one_app_detail_text.pack(fill="both", expand=True)

        split.add(tree_frame, height=330)
        split.add(detail_frame)
        return frame

    def _populate_one_app_dashboard(self) -> None:
        try:
            from codered_app.launcher_registry import build_status_report
        except Exception as exc:
            self.one_app_summary_var.set(f"One-app registry import failed: {exc}")
            self._set_text_widget_content(self.one_app_detail_text, f"One-app registry import failed:\n{exc}")
            return

        report = build_status_report(CODERED_APP_ROOT)
        self.one_app_report = report
        counts = report.get("counts", {})
        self.one_app_summary_var.set(
            " | ".join([
                f"Root: {report.get('root')}",
                f"Readiness: {report.get('score', 0)}%",
                f"Ready: {counts.get('ready', 0)}",
                f"Needs proof: {counts.get('ready-no-proof', 0)}",
                f"Missing: {counts.get('missing', 0)}",
            ])
        )
        for item in self.one_app_tree.get_children():
            self.one_app_tree.delete(item)
        first_item = None
        for lane in report.get("lanes", []):
            required = f"{lane.get('ready_required', 0)}/{lane.get('total_required', 0)}"
            proof = str(len(lane.get("present_proof", [])))
            item = self.one_app_tree.insert(
                "",
                "end",
                iid=lane.get("id") or None,
                values=(lane.get("state", ""), lane.get("category", ""), lane.get("title", ""), required, proof),
            )
            if first_item is None:
                first_item = item
        if first_item:
            self.one_app_tree.selection_set(first_item)
            self.one_app_tree.focus(first_item)
            self._show_one_app_lane_detail(first_item)
        else:
            self._set_text_widget_content(self.one_app_detail_text, "No one-app lanes are registered yet.")

    def refresh_one_app_dashboard(self) -> None:
        self._populate_one_app_dashboard()
        self.notebook.select(self._tab_index_for_name("Dashboard"))
        self.log("One-app dashboard refreshed.")

    def write_one_app_status_report(self) -> None:
        try:
            from codered_app.launcher_registry import write_status_outputs
            result = write_status_outputs(CODERED_APP_ROOT)
            self._populate_one_app_dashboard()
            self.notebook.select(self._tab_index_for_name("Dashboard"))
            self._show_result(OperationResult(True, "One-app status written", f"Markdown:\n{result['markdown']}\n\nJSON:\n{result['json']}"))
            self.log("One-app status report written.")
        except Exception as exc:
            self._show_result(OperationResult(False, "One-app status write failed", str(exc)))

    def validate_archive_lane(self) -> None:
        script = CODERED_APP_ROOT / "tools" / "codered_archive_lane_validation.py"
        if not script.exists():
            self._show_result(OperationResult(False, "Archive validator missing", f"Missing validator:\n{script}"))
            return
        try:
            proc = subprocess.run(
                [sys.executable, str(script), "--root", str(CODERED_APP_ROOT)],
                cwd=str(CODERED_APP_ROOT),
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
        except Exception as exc:
            self._show_result(OperationResult(False, "Archive validation failed", str(exc)))
            return
        output = "\n".join(part.strip() for part in (proc.stdout, proc.stderr) if part and part.strip())
        report_md = CODERED_APP_ROOT / "logs" / "CodeRED_Archive_Lane_Validation_Report.md"
        if report_md.exists():
            try:
                output = report_md.read_text(encoding="utf-8")
            except Exception:
                pass
        self._populate_one_app_dashboard()
        try:
            self.one_app_tree.selection_set("rpf_edit_lab")
            self.one_app_tree.focus("rpf_edit_lab")
        except Exception:
            pass
        self.notebook.select(self._tab_index_for_name("Dashboard"))
        detail_output = output or "Archive validation produced no output."
        self._set_text_widget_content(self.one_app_detail_text, detail_output)
        self.after_idle(lambda text=detail_output: self._set_text_widget_content(self.one_app_detail_text, text))
        if proc.returncode == 0:
            self.log("Archive validation passed.")
            self._show_result(OperationResult(True, "Archive validation passed", "RPF inventory and sample-read proof passed. Reports were written to logs/."))
        else:
            self.log("Archive validation partial/failed.")
            self._show_result(OperationResult(False, "Archive validation partial/failed", output or f"Exit code: {proc.returncode}"))

    def run_regression_guard_lane(self) -> None:
        script = CODERED_APP_ROOT / "tools" / "codered_regression_guard.py"
        if not script.exists():
            self._show_result(OperationResult(False, "Regression Guard missing", f"Missing validator:\n{script}"))
            return
        baseline_candidates = [
            CODERED_APP_ROOT / "Code_RED.zip",
            CODERED_APP_ROOT / "imports" / "Code_RED.zip",
            CODERED_APP_ROOT.parent / "Code_RED.zip",
        ]
        command = [sys.executable, str(script), "--root", str(CODERED_APP_ROOT)]
        baseline = next((candidate for candidate in baseline_candidates if candidate.exists()), None)
        if baseline is not None:
            command.extend(["--baseline", str(baseline)])
        try:
            proc = subprocess.run(
                command,
                cwd=str(CODERED_APP_ROOT),
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except Exception as exc:
            self._show_result(OperationResult(False, "Regression Guard failed", str(exc)))
            return
        output = "\n".join(part.strip() for part in (proc.stdout, proc.stderr) if part and part.strip())
        report_md = CODERED_APP_ROOT / "logs" / "CodeRED_Regression_Guard_Report.md"
        if report_md.exists():
            try:
                output = report_md.read_text(encoding="utf-8")
            except Exception:
                pass
        self._populate_one_app_dashboard()
        try:
            self.one_app_tree.selection_set("regression_guard")
            self.one_app_tree.focus("regression_guard")
        except Exception:
            pass
        self.notebook.select(self._tab_index_for_name("Dashboard"))
        detail_output = output or "Regression Guard produced no output."
        self._set_text_widget_content(self.one_app_detail_text, detail_output)
        self.after_idle(lambda text=detail_output: self._set_text_widget_content(self.one_app_detail_text, text))
        if proc.returncode == 0:
            self.log("Regression Guard passed.")
            self._show_result(OperationResult(True, "Regression Guard passed", "Checkpoint comparison, obsolete-file guard, critical-file checks, and source decode checks passed."))
        else:
            self.log("Regression Guard found issues.")
            self._show_result(OperationResult(False, "Regression Guard found issues", output or f"Exit code: {proc.returncode}"))

    def validate_file_io_lane(self) -> None:
        script = CODERED_APP_ROOT / "tools" / "codered_file_io_validation.py"
        if not script.exists():
            self._show_result(OperationResult(False, "File IO validator missing", f"Missing validator:\n{script}"))
            return
        try:
            proc = subprocess.run(
                [sys.executable, str(script), "--root", str(CODERED_APP_ROOT)],
                cwd=str(CODERED_APP_ROOT),
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
        except Exception as exc:
            self._show_result(OperationResult(False, "File IO validation failed", str(exc)))
            return
        output = "\n".join(part.strip() for part in (proc.stdout, proc.stderr) if part and part.strip())
        report_md = CODERED_APP_ROOT / "logs" / "CodeRED_File_IO_Decode_Report.md"
        if report_md.exists():
            try:
                output = report_md.read_text(encoding="utf-8")
            except Exception:
                pass
        self._populate_one_app_dashboard()
        try:
            self.one_app_tree.selection_set("file_io_decode")
            self.one_app_tree.focus("file_io_decode")
        except Exception:
            pass
        self.notebook.select(self._tab_index_for_name("Dashboard"))
        detail_output = output or "File IO validation produced no output."
        self._set_text_widget_content(self.one_app_detail_text, detail_output)
        self.after_idle(lambda text=detail_output: self._set_text_widget_content(self.one_app_detail_text, text))
        if proc.returncode == 0:
            self.log("File IO / full decode validation passed.")
            self._show_result(OperationResult(True, "File IO validation passed", "Full-file read/decode and staged archive entry extraction proof passed. Reports were written to logs/."))
        else:
            self.log("File IO / full decode validation partial/failed.")
            self._show_result(OperationResult(False, "File IO validation partial/failed", output or f"Exit code: {proc.returncode}"))

    def validate_codex_modelxml_lane(self) -> None:
        script = CODERED_APP_ROOT / "tools" / "codered_codex_modelxml_validation.py"
        if not script.exists():
            self._show_result(OperationResult(False, "CodeX / ModelXML validator missing", f"Missing validator:\n{script}"))
            return
        try:
            proc = subprocess.run(
                [sys.executable, str(script), "--root", str(CODERED_APP_ROOT)],
                cwd=str(CODERED_APP_ROOT),
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
        except Exception as exc:
            self._show_result(OperationResult(False, "CodeX / ModelXML validation failed", str(exc)))
            return
        output = "\n".join(part.strip() for part in (proc.stdout, proc.stderr) if part and part.strip())
        report_md = CODERED_APP_ROOT / "logs" / "CodeRED_CodeX_ModelXML_Validation_Report.md"
        if report_md.exists():
            try:
                output = report_md.read_text(encoding="utf-8")
            except Exception:
                pass
        self._populate_one_app_dashboard()
        try:
            self.one_app_tree.selection_set("codex_bundle")
            self.one_app_tree.focus("codex_bundle")
        except Exception:
            pass
        self.notebook.select(self._tab_index_for_name("Dashboard"))
        detail_output = output or "CodeX / ModelXML validation produced no output."
        self._set_text_widget_content(self.one_app_detail_text, detail_output)
        self.after_idle(lambda text=detail_output: self._set_text_widget_content(self.one_app_detail_text, text))
        if proc.returncode == 0:
            self.log("CodeX / ModelXML validation passed.")
            self._show_result(OperationResult(True, "CodeX / ModelXML validation passed", "Bundle export/import and copied-archive readback proof passed. Reports were written to logs/."))
        else:
            self.log("CodeX / ModelXML validation failed.")
            self._show_result(OperationResult(False, "CodeX / ModelXML validation failed", output or f"Exit code: {proc.returncode}"))

    def validate_ai_trainer_lane(self) -> None:
        script = CODERED_APP_ROOT / "tools" / "codered_ai_trainer_validation.py"
        if not script.exists():
            self._show_result(OperationResult(False, "AI Trainer validator missing", f"Missing validator:\n{script}"))
            return
        try:
            proc = subprocess.run(
                [sys.executable, str(script), "--root", str(CODERED_APP_ROOT)],
                cwd=str(CODERED_APP_ROOT),
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except Exception as exc:
            self._show_result(OperationResult(False, "AI Trainer validation failed", str(exc)))
            return
        output = "\n".join(part.strip() for part in (proc.stdout, proc.stderr) if part and part.strip())
        report_md = CODERED_APP_ROOT / "logs" / "CodeRED_AI_Trainer_Validation_Report.md"
        if report_md.exists():
            try:
                output = report_md.read_text(encoding="utf-8")
            except Exception:
                pass
        self._populate_one_app_dashboard()
        try:
            self.one_app_tree.selection_set("ai_trainer_menu")
            self.one_app_tree.focus("ai_trainer_menu")
        except Exception:
            pass
        self.notebook.select(self._tab_index_for_name("Dashboard"))
        detail_output = output or "AI Trainer validation produced no output."
        self._set_text_widget_content(self.one_app_detail_text, detail_output)
        self.after_idle(lambda text=detail_output: self._set_text_widget_content(self.one_app_detail_text, text))
        if proc.returncode == 0:
            self.log("AI Trainer validation passed.")
            self._show_result(OperationResult(True, "AI Trainer validation passed", "Enum map, roster, behavior actions, INI, and native-hook source checks passed. Reports were written to logs/."))
        else:
            self.log("AI Trainer validation failed.")
            self._show_result(OperationResult(False, "AI Trainer validation failed", output or f"Exit code: {proc.returncode}"))

    def build_native_database_lane(self) -> None:
        script = CODERED_APP_ROOT / "tools" / "codered_native_database.py"
        if not script.exists():
            self._show_result(OperationResult(False, "Native database builder missing", f"Missing builder:\n{script}"))
            return
        try:
            proc = subprocess.run(
                [sys.executable, str(script), "--root", str(CODERED_APP_ROOT)],
                cwd=str(CODERED_APP_ROOT),
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
        except Exception as exc:
            self._show_result(OperationResult(False, "Native database build failed", str(exc)))
            return
        output = "\n".join(part.strip() for part in (proc.stdout, proc.stderr) if part and part.strip())
        report_md = CODERED_APP_ROOT / "logs" / "CodeRED_Native_Database_Report.md"
        if report_md.exists():
            try:
                output = report_md.read_text(encoding="utf-8")
            except Exception:
                pass
        self._populate_one_app_dashboard()
        try:
            self.one_app_tree.selection_set("native_probe")
            self.one_app_tree.focus("native_probe")
        except Exception:
            pass
        self.notebook.select(self._tab_index_for_name("Dashboard"))
        detail_output = output or "Native database build produced no output."
        self._set_text_widget_content(self.one_app_detail_text, detail_output)
        self.after_idle(lambda text=detail_output: self._set_text_widget_content(self.one_app_detail_text, text))
        if proc.returncode == 0:
            self.log("Native database build passed.")
            self._show_result(OperationResult(True, "Native database build passed", "Native database, legacy data/natives.json, and bridge-prep stubs were written."))
        else:
            self.log("Native database build failed.")
            self._show_result(OperationResult(False, "Native database build failed", output or f"Exit code: {proc.returncode}"))

    def generate_native_bridge_lane(self) -> None:
        script = CODERED_APP_ROOT / "tools" / "codered_native_bridge_generation.py"
        if not script.exists():
            self._show_result(OperationResult(False, "Native bridge generator missing", f"Missing generator:\n{script}"))
            return
        try:
            proc = subprocess.run(
                [sys.executable, str(script), "--root", str(CODERED_APP_ROOT)],
                cwd=str(CODERED_APP_ROOT),
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
        except Exception as exc:
            self._show_result(OperationResult(False, "Native bridge generation failed", str(exc)))
            return
        output = "\n".join(part.strip() for part in (proc.stdout, proc.stderr) if part and part.strip())
        report_md = CODERED_APP_ROOT / "logs" / "CodeRED_Native_Bridge_Generation_Report.md"
        if report_md.exists():
            try:
                output = report_md.read_text(encoding="utf-8")
            except Exception:
                pass
        self._populate_one_app_dashboard()
        try:
            self.one_app_tree.selection_set("native_probe")
            self.one_app_tree.focus("native_probe")
        except Exception:
            pass
        self.notebook.select(self._tab_index_for_name("Dashboard"))
        detail_output = output or "Native bridge generation produced no output."
        self._set_text_widget_content(self.one_app_detail_text, detail_output)
        self.after_idle(lambda text=detail_output: self._set_text_widget_content(self.one_app_detail_text, text))
        if proc.returncode == 0:
            self.log("Native bridge generation passed.")
            self._show_result(OperationResult(True, "Native bridge generation passed", "Selected native wrappers, manifest, and bridge prep report were written."))
        else:
            self.log("Native bridge generation partial/failed.")
            self._show_result(OperationResult(False, "Native bridge generation partial/failed", output or f"Exit code: {proc.returncode}"))

    def prepare_ai_menu_bridge_lane(self) -> None:
        script = CODERED_APP_ROOT / "tools" / "codered_ai_menu_bridge_integration.py"
        if not script.exists():
            self._show_result(OperationResult(False, "AI Menu bridge integration tool missing", f"Missing tool:\n{script}"))
            return
        try:
            proc = subprocess.run(
                [sys.executable, str(script), "--root", str(CODERED_APP_ROOT)],
                cwd=str(CODERED_APP_ROOT),
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
        except Exception as exc:
            self._show_result(OperationResult(False, "AI Menu bridge prep failed", str(exc)))
            return
        output = "\n".join(part.strip() for part in (proc.stdout, proc.stderr) if part and part.strip())
        report_md = CODERED_APP_ROOT / "logs" / "CodeRED_AI_Menu_Bridge_Integration_Report.md"
        if report_md.exists():
            try:
                output = report_md.read_text(encoding="utf-8")
            except Exception:
                pass
        self._populate_one_app_dashboard()
        try:
            self.one_app_tree.selection_set("ai_menu_bridge_integration")
            self.one_app_tree.focus("ai_menu_bridge_integration")
        except Exception:
            pass
        self.notebook.select(self._tab_index_for_name("Dashboard"))
        detail_output = output or "AI Menu bridge integration produced no output."
        self._set_text_widget_content(self.one_app_detail_text, detail_output)
        self.after_idle(lambda text=detail_output: self._set_text_widget_content(self.one_app_detail_text, text))
        if proc.returncode == 0:
            self.log("AI Menu bridge integration prep passed.")
            self._show_result(OperationResult(True, "AI Menu bridge prep passed", "Bridge candidate source, candidate build helper, manifest, and diff were written. Review before compiling/installing."))
        else:
            self.log("AI Menu bridge integration prep failed.")
            self._show_result(OperationResult(False, "AI Menu bridge prep failed", output or f"Exit code: {proc.returncode}"))

    def validate_script_compile_lane(self) -> None:
        script = CODERED_APP_ROOT / "tools" / "codered_script_compile_validation.py"
        if not script.exists():
            self._show_result(OperationResult(False, "Script Compile validator missing", f"Missing validator:\n{script}"))
            return
        try:
            proc = subprocess.run(
                [sys.executable, str(script), "--root", str(CODERED_APP_ROOT)],
                cwd=str(CODERED_APP_ROOT),
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        except Exception as exc:
            self._show_result(OperationResult(False, "Script Compile validation failed", str(exc)))
            return
        output = "\n".join(part.strip() for part in (proc.stdout, proc.stderr) if part and part.strip())
        report_md = CODERED_APP_ROOT / "logs" / "CodeRED_Script_Compile_Validation_Report.md"
        if report_md.exists():
            try:
                output = report_md.read_text(encoding="utf-8")
            except Exception:
                pass
        self._populate_one_app_dashboard()
        try:
            self.one_app_tree.selection_set("script_compile_lab")
            self.one_app_tree.focus("script_compile_lab")
        except Exception:
            pass
        self.notebook.select(self._tab_index_for_name("Dashboard"))
        detail_output = output or "Script Compile validation produced no output."
        self._set_text_widget_content(self.one_app_detail_text, detail_output)
        self.after_idle(lambda text=detail_output: self._set_text_widget_content(self.one_app_detail_text, text))
        if proc.returncode == 0:
            self.log("Script Compile validation passed.")
            self._show_result(OperationResult(True, "Script Compile validation passed", "Compile-lab source, required symbols, constants, and Windows build-kit staging were validated. Reports were written to logs/."))
        else:
            self.log("Script Compile validation failed.")
            self._show_result(OperationResult(False, "Script Compile validation failed", output or f"Exit code: {proc.returncode}"))

    def validate_script_workshop_decode_lane(self) -> None:
        script = CODERED_APP_ROOT / "tools" / "codered_script_workshop_decode.py"
        if not script.exists():
            self._show_result(OperationResult(False, "Script Workshop decoder missing", f"Missing validator:\n{script}"))
            return
        try:
            proc = subprocess.run(
                [sys.executable, str(script), "--root", str(CODERED_APP_ROOT)],
                cwd=str(CODERED_APP_ROOT),
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except Exception as exc:
            self._show_result(OperationResult(False, "Script Workshop decode validation failed", str(exc)))
            return
        output = "\n".join(part.strip() for part in (proc.stdout, proc.stderr) if part and part.strip())
        report_md = CODERED_APP_ROOT / "logs" / "CodeRED_Script_Workshop_Decode_Report.md"
        if report_md.exists():
            try:
                output = report_md.read_text(encoding="utf-8")
            except Exception:
                pass
        self._populate_one_app_dashboard()
        try:
            self.one_app_tree.selection_set("script_workshop_decode")
            self.one_app_tree.focus("script_workshop_decode")
        except Exception:
            pass
        self.notebook.select(self._tab_index_for_name("Dashboard"))
        detail_output = output or "Script Workshop decode validation produced no output."
        self._set_text_widget_content(self.one_app_detail_text, detail_output)
        self.after_idle(lambda text=detail_output: self._set_text_widget_content(self.one_app_detail_text, text))
        if proc.returncode == 0:
            self.log("Script Workshop decode validation passed.")
            self._show_result(OperationResult(True, "Script Workshop decode validation passed", "Script Lab/Workshop full decode, editable manifest, binary script reads, and capability proof were written."))
        else:
            self.log("Script Workshop decode validation failed.")
            self._show_result(OperationResult(False, "Script Workshop decode validation failed", output or f"Exit code: {proc.returncode}"))

    def prepare_script_workshop_compile_lane(self) -> None:
        script = CODERED_APP_ROOT / "tools" / "codered_script_workshop_compile_prep.py"
        if not script.exists():
            self._show_result(OperationResult(False, "Script Workshop compile prep missing", f"Missing prep tool:\n{script}"))
            return
        try:
            proc = subprocess.run(
                [sys.executable, str(script), "--root", str(CODERED_APP_ROOT)],
                cwd=str(CODERED_APP_ROOT),
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except Exception as exc:
            self._show_result(OperationResult(False, "Script Workshop compile prep failed", str(exc)))
            return
        output = "\n".join(part.strip() for part in (proc.stdout, proc.stderr) if part and part.strip())
        report_md = CODERED_APP_ROOT / "logs" / "CodeRED_Script_Workshop_Compile_Prep_Report.md"
        if report_md.exists():
            try:
                output = report_md.read_text(encoding="utf-8")
            except Exception:
                pass
        self._populate_one_app_dashboard()
        try:
            self.one_app_tree.selection_set("script_workshop_compile_prep")
            self.one_app_tree.focus("script_workshop_compile_prep")
        except Exception:
            pass
        self.notebook.select(self._tab_index_for_name("Dashboard"))
        detail_output = output or "Script Workshop compile/edit prep produced no output."
        self._set_text_widget_content(self.one_app_detail_text, detail_output)
        self.after_idle(lambda text=detail_output: self._set_text_widget_content(self.one_app_detail_text, text))
        if proc.returncode == 0:
            self.log("Script Workshop compile/edit prep passed.")
            self._show_result(OperationResult(True, "Script Workshop compile/edit prep passed", "Safe edit copies, source compile candidates, native dependency maps, and compile-proof workspace were written."))
        else:
            self.log("Script Workshop compile/edit prep failed.")
            self._show_result(OperationResult(False, "Script Workshop compile/edit prep failed", output or f"Exit code: {proc.returncode}"))

    def run_script_pipeline_lane(self) -> None:
        script = CODERED_APP_ROOT / "tools" / "codered_script_pipeline.py"
        if not script.exists():
            self._show_result(OperationResult(False, "Script Pipeline tool missing", f"Missing tool:\n{script}"))
            return
        try:
            proc = subprocess.run(
                [sys.executable, str(script), "--root", str(CODERED_APP_ROOT)],
                cwd=str(CODERED_APP_ROOT),
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
        except Exception as exc:
            self._show_result(OperationResult(False, "Script Pipeline failed", str(exc)))
            return
        output = "\n".join(part.strip() for part in (proc.stdout, proc.stderr) if part and part.strip())
        report_md = CODERED_APP_ROOT / "logs" / "CodeRED_Script_Pipeline_Report.md"
        if report_md.exists():
            try:
                output = report_md.read_text(encoding="utf-8")
            except Exception:
                pass
        self._populate_one_app_dashboard()
        try:
            self.one_app_tree.selection_set("script_pipeline")
            self.one_app_tree.focus("script_pipeline")
        except Exception:
            pass
        self.notebook.select(self._tab_index_for_name("Dashboard"))
        detail_output = output or "Script Pipeline produced no output."
        self._set_text_widget_content(self.one_app_detail_text, detail_output)
        self.after_idle(lambda text=detail_output: self._set_text_widget_content(self.one_app_detail_text, text))
        if proc.returncode == 0:
            self.log("Script Pipeline passed.")
            self._show_result(OperationResult(True, "Script Pipeline passed", "Script scan/read/open/edit/decompiled-export/import/recompile queues and new script templates were generated."))
        else:
            self.log("Script Pipeline failed or partial.")
            self._show_result(OperationResult(False, "Script Pipeline failed or partial", output or f"Exit code: {proc.returncode}"))

    def validate_terrainboundres_lane(self) -> None:
        script = CODERED_APP_ROOT / "tools" / "codered_terrainboundres_validation.py"
        if not script.exists():
            self._show_result(OperationResult(False, "Terrainboundres validator missing", f"Missing validator:\n{script}"))
            return
        try:
            proc = subprocess.run(
                [sys.executable, str(script), "--root", str(CODERED_APP_ROOT)],
                cwd=str(CODERED_APP_ROOT),
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
        except Exception as exc:
            self._show_result(OperationResult(False, "Terrainboundres validation failed", str(exc)))
            return
        output = "\n".join(part.strip() for part in (proc.stdout, proc.stderr) if part and part.strip())
        report_md = CODERED_APP_ROOT / "logs" / "CodeRED_Terrainboundres_Validation_Report.md"
        if report_md.exists():
            try:
                output = report_md.read_text(encoding="utf-8")
            except Exception:
                pass
        self._populate_one_app_dashboard()
        try:
            self.one_app_tree.selection_set("terrain_tools")
            self.one_app_tree.focus("terrain_tools")
        except Exception:
            pass
        self.notebook.select(self._tab_index_for_name("Dashboard"))
        detail_output = output or "Terrainboundres validation produced no output."
        self._set_text_widget_content(self.one_app_detail_text, detail_output)
        self.after_idle(lambda text=detail_output: self._set_text_widget_content(self.one_app_detail_text, text))
        if proc.returncode == 0:
            self.log("Terrainboundres validation passed.")
            self._show_result(OperationResult(True, "Terrainboundres validation passed", "Inventory/decode proof passed. Reports were written to logs/."))
        else:
            self.log("Terrainboundres validation failed.")
            self._show_result(OperationResult(False, "Terrainboundres validation failed", output or f"Exit code: {proc.returncode}"))

    def _on_one_app_lane_select(self, event=None) -> None:
        del event
        selection = self.one_app_tree.selection()
        if not selection:
            return
        self._show_one_app_lane_detail(selection[0])

    def _show_one_app_lane_detail(self, lane_id: str) -> None:
        report = getattr(self, "one_app_report", {}) or {}
        lane = next((item for item in report.get("lanes", []) if item.get("id") == lane_id), None)
        if not lane:
            self._set_text_widget_content(self.one_app_detail_text, "Lane detail not found.")
            return
        command = " ".join(str(part) for part in lane.get("command", []))
        lines = [
            lane.get("title", "Unknown lane"),
            "=" * max(8, len(lane.get("title", "Unknown lane"))),
            "",
            f"State: {lane.get('state')}",
            f"Category: {lane.get('category')}",
            f"Command: {command}",
            "",
            lane.get("description", ""),
            "",
            "Required files present:",
        ]
        present_required = lane.get("present_required", []) or []
        missing_required = lane.get("missing_required", []) or []
        present_optional = lane.get("present_optional", []) or []
        present_proof = lane.get("present_proof", []) or []
        replaces_external = lane.get("replaces_external", []) or []
        lines.extend([f"- {item}" for item in present_required] or ["- none"])
        lines.extend(["", "Missing required files:"])
        lines.extend([f"- {item}" for item in missing_required] or ["- none"])
        lines.extend(["", "Optional files present:"])
        lines.extend([f"- {item}" for item in present_optional] or ["- none"])
        lines.extend(["", "Proof files present:"])
        lines.extend([f"- {item}" for item in present_proof] or ["- none"])
        if replaces_external:
            lines.extend(["", "External/manual workflows this lane is intended to replace:"])
            lines.extend([f"- {item}" for item in replaces_external])
        if lane.get("notes"):
            lines.extend(["", "Notes:", lane.get("notes", "")])
        self._set_text_widget_content(self.one_app_detail_text, "\n".join(lines))


    def _add_research_browser_tab(self) -> tk.Frame:
        frame = tk.Frame(self.notebook, bg=self.theme["bg"])
        self.notebook.add(frame, text="Research")

        header = tk.Frame(frame, bg=self.theme["bg"])
        header.pack(fill="x", padx=14, pady=(14, 6))
        self.research_summary_var = tk.StringVar(value="Research browser not loaded yet")
        tk.Label(
            header,
            text="Code RED Logs / Research Browser",
            font=("SegoeUI", 14, "bold"),
            bg=self.theme["accent"],
            fg=self.theme["fg"],
            anchor="w",
        ).pack(fill="x")
        tk.Label(header, textvariable=self.research_summary_var, bg=self.theme["bg"], fg=self.theme["fg"], anchor="w", justify="left").pack(fill="x", pady=(6, 0))

        buttons = tk.Frame(frame, bg=self.theme["bg"])
        buttons.pack(fill="x", padx=14, pady=(0, 8))
        for caption, command in (
            ("Refresh Research", self.refresh_research_browser),
            ("Write Research Index", self.write_research_browser_report),
            ("Open Selected", self.open_selected_research_item),
            ("Open Logs", self.open_logs_folder),
            ("Open Research Folder", self.open_research_folder),
        ):
            tk.Button(buttons, text=caption, command=command, bg=self.theme["accent"], fg=self.theme["fg"], relief="flat", padx=10, pady=6).pack(side="left", padx=(0, 8))

        split = tk.PanedWindow(frame, orient="vertical", sashrelief="flat", sashwidth=6, bg=self.theme["bg"])
        split.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        tree_frame = tk.Frame(split, bg=self.theme["bg"])
        self.research_tree = ttk.Treeview(
            tree_frame,
            columns=("topic", "source", "title", "path", "state"),
            show="headings",
            height=13,
        )
        for col, title, width in (
            ("topic", "Topic", 130),
            ("source", "Source", 150),
            ("title", "Title", 320),
            ("path", "Path", 420),
            ("state", "State", 90),
        ):
            self.research_tree.heading(col, text=title)
            self.research_tree.column(col, width=width, anchor="w")
        self.research_tree.pack(fill="both", expand=True)
        self.research_tree.bind("<<TreeviewSelect>>", self._on_research_select)

        detail_frame = tk.Frame(split, bg=self.theme["bg"])
        self.research_detail_text = tk.Text(detail_frame, wrap="word", bg=self.theme["panel"], fg=self.theme["fg"], insertbackground=self.theme["fg"], relief="flat")
        self.research_detail_text.pack(fill="both", expand=True)

        split.add(tree_frame, height=350)
        split.add(detail_frame)
        self.research_entries_by_id: dict[str, dict] = {}
        return frame

    def _populate_research_browser(self) -> None:
        try:
            entries = _codered_load_research_browser_entries(CODERED_APP_ROOT)
        except Exception as exc:
            self.research_summary_var.set(f"Research browser load failed: {exc}")
            self._set_text_widget_content(self.research_detail_text, f"Research browser load failed:\n{exc}")
            return
        self.research_entries_by_id = {}
        for item in self.research_tree.get_children():
            self.research_tree.delete(item)
        missing = 0
        first_item = None
        for idx, entry in enumerate(entries):
            iid = f"research_{idx:04d}"
            self.research_entries_by_id[iid] = entry
            state = "OK" if entry.get("exists") else "MISSING"
            if state == "MISSING":
                missing += 1
            item = self.research_tree.insert(
                "",
                "end",
                iid=iid,
                values=(entry.get("topic", ""), entry.get("source", ""), entry.get("title", ""), entry.get("relative_path", ""), state),
            )
            if first_item is None:
                first_item = item
        self.research_summary_var.set(f"Indexed: {len(entries)} | Missing referenced: {missing} | Root: {CODERED_APP_ROOT}")
        if first_item:
            self.research_tree.selection_set(first_item)
            self.research_tree.focus(first_item)
            self._show_research_detail(first_item)
        else:
            self._set_text_widget_content(self.research_detail_text, "No research/log entries found.")

    def refresh_research_browser(self) -> None:
        self._populate_research_browser()
        self.notebook.select(self._tab_index_for_name("Research"))
        self.log("Research browser refreshed.")

    def write_research_browser_report(self) -> None:
        try:
            result = _codered_build_research_browser_report(CODERED_APP_ROOT)
            self._populate_research_browser()
            self.notebook.select(self._tab_index_for_name("Research"))
            self._set_text_widget_content(self.research_detail_text, result.get("text", ""))
            self._show_result(OperationResult(True, "Research browser report written", f"Markdown:\n{result['markdown']}\n\nJSON:\n{result['json']}"))
            self.log("Research browser report written.")
        except Exception as exc:
            self._show_result(OperationResult(False, "Research browser report failed", str(exc)))

    def _on_research_select(self, event=None) -> None:
        del event
        selection = self.research_tree.selection()
        if not selection:
            return
        self._show_research_detail(selection[0])

    def _show_research_detail(self, item_id: str) -> None:
        entry = self.research_entries_by_id.get(item_id)
        if not entry:
            self._set_text_widget_content(self.research_detail_text, "Research detail not found.")
            return
        path = Path(entry.get("path", ""))
        lines = [
            str(entry.get("title", path.name)),
            "=" * max(8, len(str(entry.get("title", path.name)))),
            "",
            f"Topic: {entry.get('topic')}",
            f"Source: {entry.get('source')}",
            f"Format: {entry.get('format')}",
            f"State: {'present' if entry.get('exists') else 'missing'}",
            f"Path: {entry.get('relative_path')}",
            f"Full path: {entry.get('path')}",
            f"Size: {_codered_human_size(int(entry.get('size') or 0))}",
        ]
        if entry.get("notes"):
            lines.extend(["", "Notes:", str(entry.get("notes"))])
        if path.exists() and path.is_file() and path.suffix.lower() in {".md", ".txt", ".csv", ".json", ".xml", ".ini", ".log"}:
            lines.extend(["", "Preview:", _codered_text_preview(path)])
        elif path.exists():
            lines.extend(["", "Preview:", "Binary/archive/folder item. Use Open Selected to inspect it in the OS file browser."])
        else:
            lines.extend(["", "Preview:", "Referenced file is missing in this package/workspace."])
        self._set_text_widget_content(self.research_detail_text, "\n".join(lines))

    def open_selected_research_item(self) -> None:
        selection = self.research_tree.selection()
        if not selection:
            self._show_result(OperationResult(False, "No research item selected", "Select a row in the Research tab first."))
            return
        entry = self.research_entries_by_id.get(selection[0]) or {}
        path = Path(entry.get("path", ""))
        if not path.exists():
            self._show_result(OperationResult(False, "Research item missing", f"Missing:\n{path}"))
            return
        try:
            msg = _codered_open_path_in_os(path)
            self.log(msg)
        except Exception as exc:
            self._show_result(OperationResult(False, "Open selected research item failed", str(exc)))

    def open_research_folder(self) -> None:
        path = CODERED_APP_ROOT / "research"
        try:
            msg = _codered_open_path_in_os(path)
            self.log(msg)
        except Exception as exc:
            self._show_result(OperationResult(False, "Open research folder failed", str(exc)))

    def _add_text_tab(self, title: str) -> tk.Text:
        txt = tk.Text(self.notebook, wrap="word", bg=self.theme["panel"], fg=self.theme["fg"], insertbackground=self.theme["fg"], relief="flat")
        self.notebook.add(txt, text=title)
        return txt

    def _add_module_tab(self, name: str, description: str) -> tk.Text:
        frame = tk.Frame(self.notebook, bg=self.theme["bg"])
        self.notebook.add(frame, text=name)
        tk.Label(frame, text=name, font=("SegoeUI", 14, "bold"), anchor="w", bg=self.theme["accent"], fg=self.theme["fg"]).pack(fill="x", padx=14, pady=(14, 2))
        tk.Label(frame, text=description, justify="left", wraplength=950, anchor="w", bg=self.theme["bg"], fg=self.theme["fg"]).pack(fill="x", padx=14)
        btns = tk.Frame(frame, bg=self.theme["bg"])
        btns.pack(fill="x", padx=14, pady=10)
        for caption in ["Open Viewer", "Export", "Import", "Replace", "Validate"]:
            tk.Button(btns, text=caption, command=lambda n=name, c=caption: self.module_action(n, c), bg=self.theme["accent"], fg=self.theme["fg"], relief="flat", padx=10, pady=6).pack(side="left", padx=(0, 8))
        txt = tk.Text(frame, wrap="word", bg=self.theme["panel"], fg=self.theme["fg"], insertbackground=self.theme["fg"], relief="flat")
        txt.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        txt.insert("1.0", MODULE_BY_NAME[name].status_report())
        txt.configure(state="disabled")
        return txt

    def _populate_home(self) -> None:
        stage = _codered_build_stage_report(self.workspace or CODERED_APP_ROOT)
        archive_note = str(stage['primary_archive']) if stage.get('primary_archive') else 'not staged yet'
        text = (
            "Code RED\n"
            "========\n\n"
            f"Readiness snapshot: {stage['score']}%\n"
            f"Primary archive target: {archive_note}\n\n"
            "Core lanes\n"
            "- Archive\n"
            "- Strings\n"
            "- Textures\n"
            "- Meshes\n"
            "- Source\n"
            "- Scripts\n"
            "- Audio\n"
            "- World\n\n"
            "Current focus\n"
            "- content.rpf inventory and contained-file workflows\n"
            "- patch-folder apply to copied archives\n"
            "- readable text editing where the file path is genuinely safe\n"
            "- guided stage actions so the next proof step is obvious\n"
            "- one-click demo archive staging and archive proof pass\n"
            "- compile-aware helper-source validation where host compilers are available\n\n"
            "Fast start\n"
            "1. Open a workspace\n"
            "2. Hit Refresh Stage Check to see what is actually staged and missing\n"
            "3. Use Stage Bundled Archive when you want a real built-in content.rpf to work against\n"
            "4. Run Archive Proof Pass for the fastest completion-oriented proof lane\n"
            "5. Use Open Imports, Open Logs, or Jump To Archive to move to the active proof lane\n"
            "6. Select a supported file\n"
            "7. Open the matching module tab\n"
            "8. Run Export, Import, Replace, or Validate on that file type\n\n"
            "This Linux build is the live fallback runner for Code RED while the WinForms host remains a separate branch.\n"
        )
        self._set_text_widget_content(self.home_text, text)

    def _populate_stage(self) -> None:
        report = _codered_build_stage_report(self.workspace or CODERED_APP_ROOT)
        self._set_text_widget_content(self.stage_text, report['text'])

    def _populate_completion(self) -> None:
        report = _codered_build_completion_report(self.workspace or CODERED_APP_ROOT)
        self._set_text_widget_content(self.completion_text, report['text'])

    def _populate_capabilities(self) -> None:
        for mod in ALL_MODULES:
            for cap in mod.capabilities:
                self.cap_tree.insert("", "end", values=(cap.extension, cap.category, cap.capability, cap.notes))

    def _set_text_widget_content(self, widget: tk.Text, content: str) -> None:
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('1.0', content)
        widget.configure(state='disabled')

    def refresh_stage_report(self) -> None:
        report = _codered_build_stage_report(self.workspace or CODERED_APP_ROOT)
        self._set_text_widget_content(self.stage_text, report['text'])
        self._set_text_widget_content(self.home_text, self._build_home_text(report))
        self._set_text_widget_content(self.completion_text, _codered_build_completion_report(self.workspace or CODERED_APP_ROOT)['text'])
        report_path = CODERED_WORKBENCH_CRASH_DIR / 'code_red_stage_report_latest.md'
        report_path.write_text(report['text'], encoding='utf-8')
        self.log(f"Stage report refreshed - readiness {report['score']}%")

    def _build_home_text(self, stage: dict) -> str:
        archive_note = str(stage['primary_archive']) if stage.get('primary_archive') else 'not staged yet'
        return (
            "Code RED\n"
            "========\n\n"
            f"Readiness snapshot: {stage['score']}%\n"
            f"Primary archive target: {archive_note}\n\n"
            "Core lanes\n"
            "- Archive\n"
            "- Strings\n"
            "- Textures\n"
            "- Meshes\n"
            "- Source\n"
            "- Scripts\n"
            "- Audio\n"
            "- World\n\n"
            "Current focus\n"
            "- content.rpf inventory and contained-file workflows\n"
            "- patch-folder apply to copied archives\n"
            "- readable text editing where the file path is genuinely safe\n"
            "- guided stage actions so the next proof step is obvious\n"
            "- one-click demo archive staging and archive proof pass\n"
            "- compile-aware helper-source validation where host compilers are available\n\n"
            "Fast start\n"
            "1. Open a workspace\n"
            "2. Hit Refresh Stage Check to see what is actually staged and missing\n"
            "3. Use Stage Bundled Archive when you want a real built-in content.rpf to work against\n"
            "4. Run Archive Proof Pass for the fastest completion-oriented proof lane\n"
            "5. Use Open Imports, Open Logs, or Jump To Archive to move to the active proof lane\n"
            "6. Select a supported file\n"
            "7. Open the matching module tab\n"
            "8. Run Export, Import, Replace, or Validate on that file type\n\n"
            "This Linux build is the live fallback runner for Code RED while the WinForms host remains a separate branch.\n"
        )

    def _code_red_tuner_root(self) -> Path:
        return CODERED_APP_ROOT / "related_apps" / "CodeRED_Tuner"

    def _launch_tuner_entry(self, demo: bool = False) -> None:
        tuner_root = self._code_red_tuner_root()
        launcher_pyw = tuner_root / "Launch_CodeRED_Tuner.pyw"
        launcher_py = tuner_root / "Launch_CodeRED_Tuner.py"
        script = launcher_pyw if launcher_pyw.exists() else launcher_py
        if not script.exists():
            self._show_result(OperationResult(False, "Code RED Tuner missing", f"Tuner launcher was not found at:\n{script}"))
            return
        try:
            args = []
            pyw = shutil.which("pyw")
            pythonw = shutil.which("pythonw")
            if pyw and launcher_pyw.exists():
                args = [pyw, "-3", str(launcher_pyw)]
            elif pythonw and launcher_pyw.exists():
                args = [pythonw, str(launcher_pyw)]
            else:
                args = [sys.executable, str(launcher_py if launcher_py.exists() else script)]
            if demo:
                args.append("--demo")
            subprocess.Popen(args, cwd=str(tuner_root))
            self.log("Opened Code RED Test Demo." if demo else "Opened Code RED Tuner.")
        except Exception as exc:
            self._show_result(OperationResult(False, "Code RED Tuner launch failed", str(exc)))

    def open_code_red_tuner(self) -> None:
        self._launch_tuner_entry(demo=False)

    def open_code_red_test_demo(self) -> None:
        self._launch_tuner_entry(demo=True)

    def open_imports_folder(self) -> None:
        try:
            msg = _codered_open_path_in_os((self.workspace or CODERED_APP_ROOT) / 'imports')
            self.log(msg)
        except Exception as exc:
            self._show_result(OperationResult(False, 'Open imports failed', str(exc)))

    def open_logs_folder(self) -> None:
        try:
            msg = _codered_open_path_in_os((self.workspace or CODERED_APP_ROOT) / 'logs')
            self.log(msg)
        except Exception as exc:
            self._show_result(OperationResult(False, 'Open logs failed', str(exc)))

    def open_primary_archive_target(self) -> None:
        stage = _codered_build_stage_report(self.workspace or CODERED_APP_ROOT)
        target = stage.get('primary_archive')
        if not target:
            expected = (self.workspace or CODERED_APP_ROOT) / 'imports' / 'content.rpf'
            self._show_result(OperationResult(False, 'Primary archive not staged', f'No archive target is staged yet. Expected drop path:\n{expected}'))
            return
        try:
            msg = _codered_open_path_in_os(target)
            self.log(msg)
        except Exception as exc:
            self._show_result(OperationResult(False, 'Open archive target failed', str(exc)))

    def stage_bundled_archive(self) -> None:
        try:
            staged = _codered_stage_demo_archive(self.workspace or CODERED_APP_ROOT)
            self.refresh_stage_report()
            self._show_result(OperationResult(True, 'Bundled archive staged', f'Placed demo content.rpf here:\n{staged}'))
        except Exception as exc:
            self._show_result(OperationResult(False, 'Bundled archive stage failed', str(exc)))

    def run_archive_proof_pass(self) -> None:
        try:
            result = _codered_run_archive_proof_pass(self.workspace or CODERED_APP_ROOT)
            self.refresh_stage_report()
            detail = [
                f"Archive: {result['archive_path']}",
                f"Applied patches: {result['applied']}",
                f"Blocked: {result['blocked']}",
                f"Relocated: {result['relocated']}",
                f"Latest report: {result['latest_md']}",
            ]
            self._show_result(OperationResult(bool(result['ok']), 'Archive proof pass complete' if result['ok'] else 'Archive proof pass partial', '\n'.join(detail)))
        except Exception as exc:
            self._show_result(OperationResult(False, 'Archive proof pass failed', str(exc)))

    def log(self, message: str) -> None:
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.status_var.set(message)

    def clear_log(self) -> None:
        self.log_text.delete("1.0", "end")
        self.status_var.set("Log cleared")

    def show_regression_reminder(self) -> None:
        messagebox.showinfo("Regression Reminder", CODERED_REGRESSION_REMINDER_TEXT)
        self.status_var.set("Regression reminder displayed")

    def audit_primary_archive(self) -> None:
        archive_path = None
        if self.selected_path and self.selected_path.is_file() and self.selected_path.suffix.lower() == '.rpf':
            archive_path = self.selected_path
        elif CODERED_PRIMARY_ARCHIVE.exists():
            archive_path = CODERED_PRIMARY_ARCHIVE
        elif self.workspace and self.workspace.is_file() and self.workspace.suffix.lower() == '.rpf':
            archive_path = self.workspace
        if archive_path is None:
            messagebox.showwarning('No archive target', 'Select an .rpf file or ensure content.rpf is present.')
            return
        info = parse_rpf6(archive_path)
        if info is None:
            self._show_result(OperationResult(False, 'Archive audit failed', 'RPF6 parse failed for the selected archive.'))
            return
        audit = audit_rpf6_archive(archive_path)
        insp = MODULE_BY_NAME['Archive'].inspect(archive_path)
        self._write_module_output('Archive', insp)
        self.notebook.select(self._tab_index_for_name('Archive'))
        ArchiveBrowserDialog(self, archive_path, info)
        if audit is not None:
            self.log(f"Archive totality audit ready: files={audit['file_count']} scripts={audit['script_entry_count']} code={audit.get('code_entry_count', 0)} extract_ok={audit['extract_success']} extract_fail={audit['extract_fail']}")

    def set_workspace(self, path: Path) -> None:
        self.workspace = path
        self.workspace_var.set(f"Workspace: {path}")
        self.scan_workspace()
        self.refresh_stage_report()

    def open_workspace(self) -> None:
        directory = filedialog.askdirectory(title="Open Workspace")
        if directory:
            self.set_workspace(Path(directory))

    def scan_workspace(self) -> None:
        if not self.workspace or not self.workspace.exists():
            messagebox.showwarning("No workspace", "Open a workspace first.")
            return
        self.tree.delete(*self.tree.get_children())
        self.node_to_path.clear()
        self._scan_truncated = False
        skipped_dirs = 0
        skipped_files = 0
        max_nodes = max(250, int(CODERED_TREE_MAX_NODES))

        def add_node(parent: str, current: Path) -> None:
            nonlocal skipped_dirs, skipped_files
            if len(self.node_to_path) >= max_nodes:
                self._scan_truncated = True
                return
            node = self.tree.insert(parent, "end", text=current.name)
            self.node_to_path[node] = current
            if current.is_dir():
                try:
                    children = sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
                except Exception:
                    children = []
                filtered_children = []
                for child in children:
                    if child.is_dir() and _codered_should_skip_scan_dir(child):
                        skipped_dirs += 1
                        continue
                    if child.is_file() and _codered_should_skip_scan_file(child):
                        skipped_files += 1
                        continue
                    filtered_children.append(child)
                for child in filtered_children:
                    add_node(node, child)
                    if self._scan_truncated:
                        break

        add_node("", self.workspace)
        roots = self.tree.get_children()
        if roots:
            self.tree.item(roots[0], open=True)
        note = f"Workspace scanned: {self.workspace}"
        if skipped_dirs or skipped_files or self._scan_truncated:
            note += f" | skipped cache dirs={skipped_dirs}, files={skipped_files}, capped={'yes' if self._scan_truncated else 'no'}"
        self.log(note)

    def _on_tree_select(self, _event=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        path = self.node_to_path.get(sel[0])
        if path is None:
            return
        self.selected_path = path
        self.selection_var.set(f"Selection: {path}")
        if path.is_file():
            mod = self.resolve_module(path)
            if mod:
                self._write_module_output(mod.name, mod.inspect(path))
                self.log(f"Selection routed to module: {mod.name}")
            else:
                self.log(f"No module registered for: {path.name}")

    def resolve_module(self, path: Path) -> Optional[ModuleBase]:
        for mod in ALL_MODULES:
            if mod.can_handle(path):
                return mod
        return None

    def inspect_selection(self) -> None:
        path = self.selected_path
        if not path or not path.is_file():
            messagebox.showwarning("No file selected", "Select a file first.")
            return
        mod = self.resolve_module(path)
        if not mod:
            messagebox.showwarning("No module", f"No module can handle {path.suffix.lower()}.")
            return
        insp = mod.inspect(path)
        self._write_module_output(mod.name, insp)
        self.notebook.select(self._tab_index_for_name(mod.name))
        self.log(f"Inspected: {path.name} with {mod.name}")

    def _tab_index_for_name(self, name: str) -> int:
        labels = [self.notebook.tab(i, option="text") for i in range(self.notebook.index("end"))]
        return labels.index(name)

    def _write_module_output(self, module_name: str, inspection: ModuleInspection) -> None:
        txt = self.output_boxes[module_name]
        txt.configure(state="normal")
        txt.delete("1.0", "end")
        body = [inspection.title, "=" * len(inspection.title), "", inspection.summary, "", inspection.details]
        if inspection.warning:
            body.extend(["", "Warning:", inspection.warning])
        if inspection.preview_text:
            body.extend(["", "Preview:", inspection.preview_text[:20000]])
        txt.insert("1.0", "\n".join(body))
        txt.configure(state="disabled")

    def inspect_extracted_entry(self, temp_path: Path, archive_entry: dict, archive_path: Path) -> None:
        mod = self.resolve_module(temp_path)
        if not mod:
            preview = ModuleInspection(
                'Archive',
                f"Archive Entry - {archive_entry['name']}",
                'Extracted internal entry has no dedicated module yet.',
                f"Archive: {archive_path}\nInternal path: {archive_entry.get('path', '')}\nTemp extract: {temp_path}",
                preview_text=hex_preview(read_bytes(temp_path, 512)),
            )
            self._write_module_output('Archive', preview)
            self.notebook.select(self._tab_index_for_name('Archive'))
            self.log(f"Extracted archive entry without module route: {archive_entry.get('path', '')}")
            return

        def write_archive_plan(saved_path: Path, action_label: str) -> None:
            plan_path = temp_path.with_name(temp_path.name + '.archive_reintegrate_plan.txt')
            plan_lines = [
                'Archive Reintegrate Plan',
                '======================',
                '',
                f'Archive source: {archive_path}',
                f'Internal path: {archive_entry.get("path", "")}',
                f'Temp extract: {temp_path}',
                f'Edited or exported output: {saved_path}',
                f'Action: {action_label}',
                '',
                'Status:',
                '- The extracted/archive-derived asset has been edited or exported.',
                '- Automatic write-back into the RPF archive is not implemented yet.',
                '- Use this file and plan as the basis for future validated reintegration.',
            ]
            plan_path.write_text('\n'.join(plan_lines), encoding='utf-8')
            self.log(f"Wrote archive reintegration plan: {plan_path.name}")

        insp = mod.inspect(temp_path)
        details = [
            f"Archive source: {archive_path}",
            f"Internal path: {archive_entry.get('path', '')}",
            f"Temp extract: {temp_path}",
            '',
            insp.details,
        ]
        routed = ModuleInspection(mod.name, insp.title, insp.summary, '\n'.join(details), insp.warning, insp.preview_text, insp.can_edit_preview_text)
        self._write_module_output(mod.name, routed)
        self.notebook.select(self._tab_index_for_name(mod.name))
        self.log(f"Routed archive entry to {mod.name}: {archive_entry.get('path', '')}")

        if is_viewable_image(temp_path):
            try:
                ImagePreviewDialog(self, temp_path, routed.title, on_saved=lambda action, saved_path: write_archive_plan(saved_path, f'image-{action}'))
            except Exception as exc:
                self._show_result(OperationResult(False, 'Image preview failed', str(exc)))
            return

        if routed.preview_text:
            editable = routed.can_edit_preview_text
            def save_callback(new_text: str) -> None:
                if editable:
                    temp_path.write_text(new_text, encoding='utf-8')
                    self.log(f"Saved temp archive preview text: {temp_path.name}")
                    write_archive_plan(temp_path, 'text-save')
            TextPreviewDialog(self, routed.title, routed.preview_text, editable, save_callback if editable else None)

    def module_action(self, module_name: str, action: str) -> None:
        mod = MODULE_BY_NAME[module_name]
        path = self.selected_path
        if action == "Import":
            self._action_import(mod)
            return
        if not path or not path.is_file():
            messagebox.showwarning("No file selected", "Select a file first.")
            return
        if not mod.can_handle(path):
            messagebox.showwarning("Wrong module", f"Selected file routes to {self.resolve_module(path).name if self.resolve_module(path) else 'no module'}, not {module_name}.")
            return
        if action == "Validate":
            result = mod.validate(path)
            self._show_result(result)
            return
        if action == "Open Viewer":
            insp = mod.inspect(path)
            self._write_module_output(mod.name, insp)
            editable = insp.can_edit_preview_text
            if is_viewable_image(path):
                try:
                    ImagePreviewDialog(self, path, insp.title)
                except Exception as exc:
                    self._show_result(OperationResult(False, 'Image preview failed', str(exc)))
            elif insp.preview_text:
                def save_callback(new_text: str) -> None:
                    if not editable:
                        return
                    path.write_text(new_text, encoding="utf-8")
                    self.log(f"Saved text preview back to file: {path.name}")
                TextPreviewDialog(self, insp.title, insp.preview_text, editable, save_callback if editable else None)
            else:
                self._show_result(OperationResult(True, "Inspection opened", f"Inspection updated in the {module_name} tab."))
            return
        if action == "Export":
            target = filedialog.asksaveasfilename(title="Export Selected File", initialfile=path.name)
            if target:
                shutil.copy2(path, target)
                self._show_result(OperationResult(True, "Export complete", f"Exported to {target}"))
            return
        if action == "Replace":
            source = filedialog.askopenfilename(title="Replace With")
            if source:
                result = mod.replace_with(path, Path(source))
                self._show_result(result)
            return

    def _action_import(self, mod: ModuleBase) -> None:
        if not self.workspace:
            messagebox.showwarning("No workspace", "Open a workspace first.")
            return
        source = filedialog.askopenfilename(title="Import File")
        if not source:
            return
        src = Path(source)
        target_dir = self.selected_path if self.selected_path and self.selected_path.is_dir() else (self.selected_path.parent if self.selected_path and self.selected_path.is_file() else self.workspace)
        target = target_dir / src.name
        shutil.copy2(src, target)
        self.scan_workspace()
        self._show_result(OperationResult(True, "Import complete", f"Imported into {target}"))


    def _current_archive_target(self) -> Optional[Path]:
        candidates = []
        if self.selected_path and self.selected_path.is_file() and self.selected_path.suffix.lower() == '.rpf':
            candidates.append(self.selected_path)
        if CODERED_PRIMARY_ARCHIVE.exists():
            candidates.append(CODERED_PRIMARY_ARCHIVE)
        if self.workspace and self.workspace.is_file() and self.workspace.suffix.lower() == '.rpf':
            candidates.append(self.workspace)
        if self.workspace and self.workspace.is_dir():
            for rel in ('imports/content.rpf', 'game/content.rpf'):
                candidate = self.workspace / rel
                if candidate.exists():
                    candidates.append(candidate)
        for candidate in candidates:
            if candidate and candidate.exists():
                return candidate
        return None

    def export_script_toolchain_pack(self) -> None:
        target = filedialog.askdirectory(title='Export Script Toolchain Pack')
        if not target:
            return
        analysis = None
        if self.selected_path and self.selected_path.is_file() and self.selected_path.suffix.lower() in {'.wsc', '.xsc', '.sco'}:
            try:
                analysis = analyze_script_payload(self.selected_path)
            except Exception:
                analysis = None
        try:
            result = _codered_build_script_toolchain_pack(Path(target), analysis=analysis)
            self._show_result(OperationResult(True, 'Script toolchain pack exported', f"Pack root: {result['pack_root']}\nManifest: {result['manifest_path']}\nCopied lanes: {len(result['copied'])}\nMissing lanes: {len(result['missing'])}"))
        except Exception as exc:
            self._show_result(OperationResult(False, 'Script toolchain pack failed', str(exc)))

    def sync_mp_companion(self, show_message: bool = True) -> Optional[Path]:
        if not CODERED_COMPANION_SCRIPT.exists():
            result = OperationResult(False, 'MP Companion missing', f'Companion script was not found at {CODERED_COMPANION_SCRIPT}')
            if show_message:
                self._show_result(result)
            else:
                self.log(result.message)
            return None
        archive = self._current_archive_target()
        game_dir = _codered_infer_game_dir_from_path(archive or self.workspace)
        payload = {
            'ts': __import__('datetime').datetime.now().isoformat(timespec='seconds'),
            'workspace': str(self.workspace) if self.workspace else '',
            'selected_path': str(self.selected_path) if self.selected_path else '',
            'content_rpf': str(archive) if archive else '',
            'game_dir': game_dir,
            'world': 'freemode',
            'boot_target': 'MULTI_FREE_ROAM',
            'route_note': 'Workbench sync handoff from Code RED',
        }
        CODERED_COMPANION_CONFIG.mkdir(parents=True, exist_ok=True)
        CODERED_COMPANION_SYNC_PATH.write_text(json.dumps(payload, indent=2), encoding='utf-8')
        self.log(f'MP Companion sync written: {CODERED_COMPANION_SYNC_PATH}')
        if show_message:
            self._show_result(OperationResult(True, 'MP Companion synced', str(CODERED_COMPANION_SYNC_PATH)))
        return CODERED_COMPANION_SYNC_PATH

    def open_mp_companion(self) -> None:
        if not CODERED_COMPANION_SCRIPT.exists():
            self._show_result(OperationResult(False, 'MP Companion missing', f'Companion script was not found at {CODERED_COMPANION_SCRIPT}'))
            return
        archive = self._current_archive_target()
        if archive or self.workspace:
            try:
                self.sync_mp_companion(show_message=False)
            except Exception as exc:
                self.log(f'MP Companion sync skipped before launch: {exc}')
        try:
            subprocess.Popen([sys.executable, str(CODERED_COMPANION_SCRIPT)], cwd=str(CODERED_COMPANION_ROOT))
            self.log('Opened MP Companion.')
        except Exception as exc:
            self._show_result(OperationResult(False, 'MP Companion launch failed', str(exc)))

    def _show_result(self, result: OperationResult) -> None:
        self.log(result.message)
        if result.success:
            messagebox.showinfo(result.title, result.message)
        else:
            messagebox.showerror(result.title, result.message)


def run_dotnet_if_possible(project_root: Path) -> bool:
    project = project_root / "RDR1MergeWorkbench.csproj"
    if not project.exists():
        return False
    try:
        proc = subprocess.run(["dotnet", "build", str(project), "-nologo"], cwd=project_root, capture_output=True, text=True, timeout=20)
        if proc.returncode != 0:
            return False
        subprocess.Popen(["dotnet", "run", "--project", str(project)], cwd=project_root)
        return True
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Code RED Python fallback runner")
    parser.add_argument("--workspace", type=str, default=None)
    parser.add_argument("--prefer-dotnet", action="store_true", help="Try to run the dotnet project first if buildable.")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    if args.prefer_dotnet and run_dotnet_if_possible(project_root):
        return 0
    startup = Path(args.workspace) if args.workspace else (CODERED_PRIMARY_ARCHIVE if CODERED_PRIMARY_ARCHIVE.exists() else None)
    try:
        app = WorkbenchApp(startup)
        app.mainloop()
        return 0
    except Exception as exc:
        crash_path = _codered_write_workbench_crash(exc)
        try:
            messagebox.showerror('Code RED crash', f'Crash log written to:\n{crash_path}\n\n{exc}')
        except Exception:
            pass
        return 1



if __name__ == "__main__":
    raise SystemExit(main())

# --- Code RED Script Lab patch (v14) ---
import hashlib as _codered_hashlib


def _codered_rpf6_encrypt(data: bytes) -> bytes:
    if not data or not _HAVE_CRYPTO:
        return data
    block_len = len(data) & ~0xF
    if block_len <= 0:
        return data
    cipher = Cipher(algorithms.AES(RPF6_AES_KEY), modes.ECB(), backend=default_backend())
    block = data[:block_len]
    for _ in range(16):
        encryptor = cipher.encryptor()
        block = encryptor.update(block) + encryptor.finalize()
    return block + data[block_len:]


def _codered_unique_preserve(seq: list[str], limit: int) -> list[str]:
    out: list[str] = []
    seen = set()
    for item in seq:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
        if len(out) >= limit:
            break
    return out


def _codered_parse_zstd_frame(data: bytes) -> dict | None:
    if len(data) < 6 or not data.startswith(b'\x28\xB5\x2F\xFD'):
        return None
    desc = data[4]
    fcs_flag = (desc >> 6) & 0x3
    single_segment = bool((desc >> 5) & 0x1)
    checksum_flag = bool((desc >> 2) & 0x1)
    dict_id_flag = desc & 0x3
    offset = 5
    window_descriptor = None
    window_log = None
    window_size = None
    if not single_segment:
        if offset >= len(data):
            return None
        window_descriptor = data[offset]
        exponent = window_descriptor >> 3
        mantissa = window_descriptor & 0x7
        window_log = 10 + exponent
        window_base = 1 << window_log
        window_add = (window_base >> 3) * mantissa
        window_size = window_base + window_add
        offset += 1
    dict_id_size = {0: 0, 1: 1, 2: 2, 3: 4}.get(dict_id_flag, 0)
    if offset + dict_id_size > len(data):
        return None
    dict_id = int.from_bytes(data[offset:offset + dict_id_size], 'little', signed=False) if dict_id_size else None
    offset += dict_id_size
    fcs_size = 0
    if fcs_flag == 0:
        fcs_size = 1 if single_segment else 0
    elif fcs_flag == 1:
        fcs_size = 2
    elif fcs_flag == 2:
        fcs_size = 4
    elif fcs_flag == 3:
        fcs_size = 8
    frame_content_size = None
    if fcs_size and offset + fcs_size <= len(data):
        frame_content_size = int.from_bytes(data[offset:offset + fcs_size], 'little', signed=False)
        if single_segment and fcs_flag == 0:
            frame_content_size += 256
        elif fcs_flag == 1:
            frame_content_size += 256
        offset += fcs_size
    return {
        'frame_descriptor': desc,
        'single_segment': single_segment,
        'checksum_flag': checksum_flag,
        'dict_id_flag': dict_id_flag,
        'dict_id_size': dict_id_size,
        'dict_id': dict_id,
        'frame_content_size_flag': fcs_flag,
        'frame_content_size': frame_content_size,
        'window_descriptor': window_descriptor,
        'window_log': window_log,
        'window_size': window_size,
        'header_size': offset,
    }


def _codered_zstd_recompress_command(zstd_frame: dict | None = None, level: int | None = None, single_thread: bool = False) -> tuple[list[str], str]:
    cmd = ['zstd', '-q', '-z', '--stdout']
    label_parts: list[str] = ['zstd']
    selected_level = None
    if level is not None:
        selected_level = int(level)
    elif zstd_frame:
        selected_level = 18
    if selected_level is not None:
        if selected_level > 19:
            cmd.append('--ultra')
        cmd.append(f'-{selected_level}')
        label_parts.append(f'level={selected_level}')
    if zstd_frame:
        if not zstd_frame.get('checksum_flag', False):
            cmd.append('--no-check')
            label_parts.append('no-check')
        window_log = zstd_frame.get('window_log')
        if window_log is not None:
            cmd.append(f'--zstd=wlog={int(window_log)}')
            label_parts.append(f'wlog={int(window_log)}')
    if single_thread:
        cmd.append('--single-thread')
        label_parts.append('single-thread')
    if len(label_parts) > 1:
        return cmd, f"{label_parts[0]}({', '.join(label_parts[1:])})"
    return cmd, 'zstd'


def _codered_select_zstd_candidate(payload: bytes, zstd_frame: dict | None, reference_size: int | None = None, target_size: int | None = None, prefer_fit_within_target: bool = False) -> tuple[bytes, str, list[str]]:
    candidate_levels = [18]
    if target_size is not None or reference_size is not None:
        candidate_levels = [18, 19, 20, 21, 22, 17, 16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1]
    candidates: list[dict] = []
    for level in candidate_levels:
        cmd, codec_label = _codered_zstd_recompress_command(zstd_frame, level=level)
        try:
            proc = subprocess.run(cmd, input=payload, capture_output=True, check=True)
        except Exception:
            continue
        rebuilt = proc.stdout
        rebuilt_frame = _codered_parse_zstd_frame(rebuilt) if rebuilt.startswith(b'\x28\xB5\x2F\xFD') else None
        frame_compare = _codered_compare_zstd_frames(zstd_frame, rebuilt_frame)
        if zstd_frame and frame_compare:
            if not (frame_compare.get('frame_descriptor_match') and frame_compare.get('window_size_match') and frame_compare.get('checksum_flag_match') and frame_compare.get('dict_id_match')):
                continue
        size = len(rebuilt)
        if target_size is not None and prefer_fit_within_target:
            within = size <= target_size
            score = (
                0 if within else 1,
                (target_size - size) if within else (size - target_size),
                abs((reference_size if reference_size is not None else target_size) - size),
                abs(level - 18),
            )
        elif target_size is not None:
            within = size <= target_size
            score = (
                abs(size - target_size),
                0 if within else 1,
                abs((reference_size if reference_size is not None else target_size) - size),
                abs(level - 18),
            )
        else:
            target = reference_size if reference_size is not None else size
            score = (abs(size - target), abs(level - 18))
        candidates.append({
            'score': score,
            'bytes': rebuilt,
            'label': codec_label,
            'level': level,
            'size': size,
            'frame': rebuilt_frame,
        })
    if not candidates:
        cmd, codec_label = _codered_zstd_recompress_command(zstd_frame)
        proc = subprocess.run(cmd, input=payload, capture_output=True, check=True)
        fallback = proc.stdout
        return fallback, codec_label, ['Adaptive zstd parity search found no matching-frame candidates; fell back to a single parity-style encode pass.']
    best = min(candidates, key=lambda item: item['score'])
    notes: list[str] = []
    if len(candidates) > 1:
        if target_size is not None and prefer_fit_within_target:
            delta = best['size'] - target_size
            notes.append(
                f"Adaptive zstd parity search tested {len(candidates)} frame-matching candidates and chose {best['label']} for target-coded-size {target_size:,} (delta {delta:+,})."
            )
        elif target_size is not None:
            delta = best['size'] - target_size
            notes.append(
                f"Adaptive zstd parity search tested {len(candidates)} frame-matching candidates and chose {best['label']} closest to target-coded-size {target_size:,} (delta {delta:+,})."
            )
        elif reference_size is not None:
            delta = best['size'] - reference_size
            notes.append(
                f"Adaptive zstd parity search tested {len(candidates)} frame-matching candidates and chose {best['label']} closest to reference-coded-size {reference_size:,} (delta {delta:+,})."
            )
    return best['bytes'], best['label'], notes


def _codered_compare_zstd_frames(original_frame: dict | None, rebuilt_frame: dict | None) -> dict | None:
    if not original_frame and not rebuilt_frame:
        return None
    return {
        'available': bool(original_frame and rebuilt_frame),
        'frame_descriptor_match': bool(original_frame and rebuilt_frame and original_frame.get('frame_descriptor') == rebuilt_frame.get('frame_descriptor')),
        'window_size_match': bool(original_frame and rebuilt_frame and original_frame.get('window_size') == rebuilt_frame.get('window_size')),
        'checksum_flag_match': bool(original_frame and rebuilt_frame and original_frame.get('checksum_flag') == rebuilt_frame.get('checksum_flag')),
        'dict_id_match': bool(original_frame and rebuilt_frame and original_frame.get('dict_id') == rebuilt_frame.get('dict_id')),
        'original': original_frame or {},
        'rebuilt': rebuilt_frame or {},
    }


def _codered_extract_payload_codec(notes: list[str]) -> tuple[str | None, int | None]:
    for note in notes:
        if 'Payload decompressed using zstd.' in note:
            return 'zstd', None
        m = re.search(r"Payload decompressed using zlib\(wbits=([-0-9]+)\)\.", note)
        if m:
            return 'zlib', int(m.group(1))
    return None, None


def codered_compress_payload_like(payload: bytes, payload_info: dict, target_coded_size: int | None = None, prefer_fit_within_target: bool = False) -> tuple[bytes, str, list[str]]:
    if not payload_info.get('decompressed'):
        return payload, 'none', []
    codec, zlib_wbits = _codered_extract_payload_codec(payload_info.get('notes', []))
    if codec == 'zstd':
        coded_reference = payload_info.get('coded_payload', b'') or b''
        rebuilt, codec_label, codec_notes = _codered_select_zstd_candidate(
            payload,
            payload_info.get('zstd_frame'),
            reference_size=len(coded_reference) if coded_reference else None,
            target_size=target_coded_size,
            prefer_fit_within_target=prefer_fit_within_target,
        )
        return rebuilt, codec_label, codec_notes
    if codec == 'zlib':
        wbits = zlib_wbits if zlib_wbits is not None else 15
        if wbits == 15:
            return zlib.compress(payload, level=9), f'zlib(wbits={wbits})', []
        comp = zlib.compressobj(level=9, wbits=wbits)
        return comp.compress(payload) + comp.flush(), f'zlib(wbits={wbits})', []
    raise RuntimeError('Unsupported or unknown payload recompression codec in fallback path.')


def rebuild_resource_stream_from_processed_payload(original_data: bytes, processed_payload: bytes, target_coded_size: int | None = None, prefer_fit_within_target: bool = False) -> tuple[bytes | None, list[str]]:
    resource = parse_resource_header(original_data)
    if not resource:
        return None, ['No resource header; rebuild path only supports resource-backed files in the current fallback.']
    payload_info = extract_resource_payload(original_data, resource)
    notes: list[str] = []
    if payload_info.get('payload', b'') == processed_payload:
        notes.append('Processed payload unchanged; reused original resource stream bytes for exact round-trip parity.')
        return original_data, notes
    try:
        raw_payload, codec_name, codec_notes = codered_compress_payload_like(
            processed_payload,
            payload_info,
            target_coded_size=target_coded_size,
            prefer_fit_within_target=prefer_fit_within_target,
        )
        if payload_info.get('decompressed'):
            notes.append(f'Recompressed processed payload using {codec_name}.')
        notes.extend(codec_notes)
    except Exception as exc:
        return None, [str(exc)]
    if payload_info.get('decrypted'):
        raw_payload = _codered_rpf6_encrypt(raw_payload)
        notes.append('Re-applied AES payload encryption for resource type 2.')
    rebuilt = original_data[:resource_header_size(resource)] + raw_payload
    return rebuilt, notes


def verify_resource_roundtrip(original_data: bytes, rebuilt_data: bytes) -> tuple[bool, str]:
    resource = parse_resource_header(original_data)
    rebuilt_resource = parse_resource_header(rebuilt_data)
    orig_info = extract_resource_payload(original_data, resource) if resource else {'payload': original_data}
    new_info = extract_resource_payload(rebuilt_data, rebuilt_resource) if rebuilt_resource else {'payload': rebuilt_data}
    same = (orig_info.get('payload', b'') == new_info.get('payload', b''))
    if same:
        return True, 'Processed payload bytes matched after rebuild verification.'
    return False, f'Processed payload mismatch after rebuild verification (original={len(orig_info.get("payload", b"")):,} bytes, rebuilt={len(new_info.get("payload", b"")):,} bytes).'



def _codered_native_db_candidate_paths() -> list[Path]:
    here = Path(__file__).resolve().parent
    return [
        here / 'data' / 'natives.json',
        here / 'natives.json',
        Path.cwd() / 'natives.json',
    ]


def _codered_parse_native_hash(text_hash: str) -> int | None:
    try:
        return int(str(text_hash), 16)
    except Exception:
        return None


def load_codered_native_db() -> tuple[dict[int, dict], int, list[str]]:
    db: dict[int, dict] = {}
    loaded_from: list[str] = []
    for cand in _codered_native_db_candidate_paths():
        if not cand.exists():
            continue
        try:
            data = json.loads(cand.read_text(encoding='utf-8'))
        except Exception:
            continue
        for category, bucket in data.items():
            if not isinstance(bucket, dict):
                continue
            for raw_hash, meta in bucket.items():
                hash_int = _codered_parse_native_hash(raw_hash)
                if hash_int is None or not isinstance(meta, dict):
                    continue
                db[hash_int] = {
                    'hash': hash_int,
                    'hash_text': str(raw_hash),
                    'category': str(category),
                    'name': str(meta.get('name') or f'UNKNOWN_{raw_hash}'),
                    'return_type': str(meta.get('return_type') or 'Unknown'),
                    'params': list(meta.get('params') or []),
                    'comment': str(meta.get('comment') or ''),
                }
        loaded_from.append(str(cand))
        if db:
            break
    return db, len(db), loaded_from


CODERED_NATIVE_DB, CODERED_NATIVE_DB_COUNT, CODERED_NATIVE_DB_SOURCES = load_codered_native_db()


def scan_native_hits(payload: bytes, *, limit: int = 80) -> list[dict]:
    if not payload or not CODERED_NATIVE_DB:
        return []
    hits: dict[int, dict] = {}
    n = len(payload)
    for offset in range(0, max(0, n - 3)):
        val = int.from_bytes(payload[offset:offset + 4], 'little', signed=False)
        meta = CODERED_NATIVE_DB.get(val)
        if not meta:
            continue
        rec = hits.setdefault(val, {
            'hash': val,
            'name': meta['name'],
            'category': meta['category'],
            'return_type': meta['return_type'],
            'params': meta['params'],
            'comment': meta['comment'],
            'count': 0,
            'aligned_count': 0,
            'offsets': [],
            'aligned_offsets': [],
            'score': 0,
            'confidence': 'low',
            'region_hits': 0,
        })
        rec['count'] += 1
        if len(rec['offsets']) < 12:
            rec['offsets'].append(offset)
        if offset % 4 == 0:
            rec['aligned_count'] += 1
            if len(rec['aligned_offsets']) < 12:
                rec['aligned_offsets'].append(offset)
        rec['score'] = rec['count'] * 10 + rec['aligned_count'] * 8
    ordered = sorted(hits.values(), key=lambda x: (-x['score'], -x['aligned_count'], -x['count'], x['name']))
    return ordered[:limit]


def _codered_find_native_table_regions(payload: bytes) -> list[dict]:
    if not payload or not CODERED_NATIVE_DB:
        return []
    aligned_hits: list[tuple[int, int]] = []
    for offset in range(0, max(0, len(payload) - 3), 4):
        val = int.from_bytes(payload[offset:offset + 4], 'little', signed=False)
        if val in CODERED_NATIVE_DB:
            aligned_hits.append((offset, val))
    if not aligned_hits:
        return []
    regions: list[dict] = []
    start = aligned_hits[0][0]
    prev = aligned_hits[0][0]
    values = [aligned_hits[0][1]]
    offsets = [aligned_hits[0][0]]
    for off, val in aligned_hits[1:]:
        if off - prev <= 0x80:
            prev = off
            values.append(val)
            offsets.append(off)
            continue
        unique_count = len(set(values))
        if len(offsets) >= 3:
            regions.append({
                'start': start,
                'end': prev + 4,
                'count': len(offsets),
                'unique_count': unique_count,
                'density': len(offsets) / max(1, ((prev + 4 - start) // 4)),
                'sample_hashes': values[:12],
            })
        start = prev = off
        values = [val]
        offsets = [off]
    unique_count = len(set(values))
    if len(offsets) >= 3:
        regions.append({
            'start': start,
            'end': prev + 4,
            'count': len(offsets),
            'unique_count': unique_count,
            'density': len(offsets) / max(1, ((prev + 4 - start) // 4)),
            'sample_hashes': values[:12],
        })
    regions.sort(key=lambda r: (-r['count'], -r['unique_count'], -r['density'], r['start']))
    return regions[:8]


def _codered_native_table_region_for_offset(regions: list[dict], offset: int) -> dict | None:
    for region in regions:
        if region['start'] <= offset < region['end']:
            return region
    return None


def _codered_apply_native_confidence(hits: list[dict], regions: list[dict]) -> list[dict]:
    for hit in hits:
        region_hits = 0
        for off in hit.get('aligned_offsets', []):
            region = _codered_native_table_region_for_offset(regions, off)
            if region:
                region_hits += 1
        hit['region_hits'] = region_hits
        score = hit.get('score', 0) + region_hits * 20
        hit['score'] = score
        if region_hits > 0 and hit.get('aligned_count', 0) > 0:
            hit['confidence'] = 'high'
        elif hit.get('aligned_count', 0) > 0:
            hit['confidence'] = 'medium'
        else:
            hit['confidence'] = 'low'
    hits.sort(key=lambda x: (-x['score'], -x.get('region_hits', 0), -x.get('aligned_count', 0), -x['count'], x['name']))
    return hits


def _codered_is_virtual_script_ptr(value: int) -> bool:
    return 0x50000000 <= value < 0x60000000


def _codered_virtual_ptr_to_offset(value: int) -> int:
    return value & 0x0FFFFFFF


def _codered_scan_virtual_pointer_array(payload: bytes, offset: int, *, limit: int = 256) -> list[int]:
    values: list[int] = []
    pos = offset
    while pos + 4 <= len(payload) and len(values) < limit:
        val = int.from_bytes(payload[pos:pos + 4], 'little', signed=False)
        if not _codered_is_virtual_script_ptr(val):
            break
        values.append(val)
        pos += 4
    return values


def _codered_find_native_table_descriptor(payload: bytes, native_regions: list[dict]) -> dict | None:
    if not payload or not native_regions:
        return None
    best: dict | None = None
    for region in native_regions:
        region_start = int(region['start'])
        region_ptr = 0x50000000 | region_start
        count = int(region['count'])
        search_start = max(0, region_start - 0x80)
        search_end = max(search_start, region_start - 4)
        for off in range(search_start, search_end + 1, 4):
            val = int.from_bytes(payload[off:off + 4], 'little', signed=False)
            if val != count:
                continue
            ptr_off = off + 4
            if ptr_off + 4 > len(payload):
                continue
            ptr_val = int.from_bytes(payload[ptr_off:ptr_off + 4], 'little', signed=False)
            if ptr_val != region_ptr:
                continue
            descriptor_off = max(0, off - 32)
            words = [int.from_bytes(payload[descriptor_off + i:descriptor_off + i + 4], 'little', signed=False) for i in range(0, min(48, len(payload) - descriptor_off), 4)]
            candidate_ptrs = [(descriptor_off + i * 4, w) for i, w in enumerate(words) if _codered_is_virtual_script_ptr(w)]
            page_map = None
            for word_off, w in candidate_ptrs:
                if w == region_ptr:
                    continue
                ptr_target = _codered_virtual_ptr_to_offset(w)
                if ptr_target >= len(payload):
                    continue
                arr = _codered_scan_virtual_pointer_array(payload, ptr_target)
                if len(arr) >= 4:
                    page_map = {
                        'field_offset': word_off,
                        'virtual_ptr': w,
                        'offset': ptr_target,
                        'count': len(arr),
                        'first': arr[:6],
                        'last': arr[-1],
                    }
                    break
            entry_hashes: list[int] = []
            for pos in range(region_start, min(region_start + 16 * 4, len(payload)), 4):
                entry_hashes.append(int.from_bytes(payload[pos:pos + 4], 'little', signed=False))
            descriptor = {
                'region_start': region_start,
                'region_end': int(region['end']),
                'region_count': count,
                'region_unique_count': int(region['unique_count']),
                'region_density': float(region['density']),
                'count_field_offset': off,
                'pointer_field_offset': ptr_off,
                'native_virtual_ptr': region_ptr,
                'native_offset': region_start,
                'descriptor_offset': descriptor_off,
                'descriptor_words': words,
                'entry_hashes_head': entry_hashes,
                'page_map': page_map,
            }
            if best is None or region['count'] > best['region_count']:
                best = descriptor
    return best


def _codered_format_descriptor_word(value: int) -> str:
    if _codered_is_virtual_script_ptr(value):
        return f'0x{value:08X}->0x{_codered_virtual_ptr_to_offset(value):X}'
    return f'0x{value:08X}'


def _codered_bswap32(value: int) -> int:
    return int.from_bytes(int(value & 0xFFFFFFFF).to_bytes(4, 'little'), 'big', signed=False)


def _codered_classify_pointer_target(payload: bytes, offset: int, native_descriptor: dict | None = None) -> dict:
    words = [int.from_bytes(payload[pos:pos + 4], 'little', signed=False) for pos in range(offset, min(len(payload), offset + 16 * 4), 4)]
    virtual_values = [w for w in words if _codered_is_virtual_script_ptr(w)]
    virtual_count = len(virtual_values)
    zero_count = sum(1 for w in words if w == 0)
    pad_count = sum(1 for w in words if w == 0xCDCDCDCD)
    native_count = sum(1 for w in words if w in CODERED_NATIVE_DB)
    unique_nonzero = len({w for w in words if w != 0})
    monotonic_virtual = all(b > a for a, b in zip(virtual_values, virtual_values[1:])) if len(virtual_values) >= 2 else False
    contiguous_virtual_run = 0
    for w in words:
        if _codered_is_virtual_script_ptr(w):
            contiguous_virtual_run += 1
        else:
            break
    contiguous_native_run = 0
    for w in words:
        if w in CODERED_NATIVE_DB:
            contiguous_native_run += 1
        else:
            break
    kind = 'mixed_data'
    if native_descriptor and offset == native_descriptor.get('region_start'):
        kind = 'native_hash_table'
    elif contiguous_virtual_run >= 4 or (virtual_count >= 6 and monotonic_virtual):
        kind = 'virtual_pointer_array'
    elif contiguous_native_run >= 4 or native_count >= 4:
        kind = 'native_hash_table'
    elif zero_count + pad_count >= max(8, len(words) - 1):
        kind = 'padding_or_zero_block'
    return {
        'offset': offset,
        'kind': kind,
        'virtual_count': virtual_count,
        'zero_count': zero_count,
        'pad_count': pad_count,
        'native_count': native_count,
        'unique_nonzero': unique_nonzero,
        'monotonic_virtual': monotonic_virtual,
        'contiguous_virtual_run': contiguous_virtual_run,
        'contiguous_native_run': contiguous_native_run,
        'sample_words': words[:8],
    }


def _codered_describe_page_map(payload: bytes, page_map: dict | None, native_descriptor: dict | None = None) -> dict | None:
    if not page_map:
        return None
    entries = _codered_scan_virtual_pointer_array(payload, int(page_map['offset']), limit=max(256, int(page_map.get('count', 0)) + 8))
    if not entries:
        return None
    page_offsets = [_codered_virtual_ptr_to_offset(v) for v in entries]
    strictly_increasing = all(b > a for a, b in zip(page_offsets, page_offsets[1:])) if len(page_offsets) >= 2 else True
    spans: list[dict] = []
    covering_index = None
    coverage_start = page_offsets[0] if page_offsets else None
    coverage_end = None
    region_start = int(native_descriptor['region_start']) if native_descriptor else None
    for index, off in enumerate(page_offsets):
        next_off = page_offsets[index + 1] if index + 1 < len(page_offsets) else len(payload)
        span = {
            'index': index,
            'virtual_ptr': entries[index],
            'offset': off,
            'next_offset': next_off,
            'size': max(0, next_off - off),
        }
        spans.append(span)
        if region_start is not None and off <= region_start < next_off and covering_index is None:
            covering_index = index
    if spans:
        coverage_end = spans[-1]['next_offset']
    size_counter = Counter(span['size'] for span in spans[:-1] if span['size'] > 0)
    page_size_guess = size_counter.most_common(1)[0][0] if size_counter else (spans[0]['size'] if spans else 0)
    tail_size = spans[-1]['size'] if spans else 0
    covers_native_region = False
    if region_start is not None and coverage_start is not None and coverage_end is not None:
        covers_native_region = coverage_start <= region_start < coverage_end
    return {
        'page_count': len(entries),
        'page_size_guess': page_size_guess,
        'tail_page_size': tail_size,
        'strictly_increasing': strictly_increasing,
        'coverage_start': coverage_start,
        'coverage_end': coverage_end,
        'covers_native_region': covers_native_region,
        'region_covering_page_index': covering_index,
        'spans': spans,
    }


def _codered_analyze_descriptor_layout(payload: bytes, native_descriptor: dict | None) -> dict | None:
    if not native_descriptor:
        return None
    descriptor_words = list(native_descriptor.get('descriptor_words') or [])[:12]
    page_map = native_descriptor.get('page_map')
    page_layout = _codered_describe_page_map(payload, page_map, native_descriptor)
    pointer_targets = []
    confidence_score = 0
    if native_descriptor.get('native_virtual_ptr') in descriptor_words:
        confidence_score += 3
    if page_map:
        confidence_score += 2
    if page_layout and page_layout.get('strictly_increasing'):
        confidence_score += 1
    if page_layout and page_layout.get('covers_native_region'):
        confidence_score += 1
    for index, value in enumerate(descriptor_words):
        if not _codered_is_virtual_script_ptr(value):
            continue
        target_off = _codered_virtual_ptr_to_offset(value)
        if target_off >= len(payload):
            continue
        target = _codered_classify_pointer_target(payload, target_off, native_descriptor)
        target['word_index'] = index
        target['virtual_ptr'] = value
        if value == native_descriptor.get('native_virtual_ptr'):
            target['role'] = 'native_table_ptr'
        elif page_map and value == page_map.get('virtual_ptr'):
            target['role'] = 'page_map_ptr'
        else:
            target['role'] = 'aux_virtual_ptr'
        if target['kind'] in {'virtual_pointer_array', 'native_hash_table'} and target['role'] == 'aux_virtual_ptr':
            confidence_score += 1
        pointer_targets.append(target)
    if confidence_score >= 7:
        confidence = 'high'
    elif confidence_score >= 4:
        confidence = 'medium'
    else:
        confidence = 'low'
    aux_pointer_targets = [t for t in pointer_targets if t.get('role') == 'aux_virtual_ptr']
    return {
        'descriptor_offset': int(native_descriptor['descriptor_offset']),
        'descriptor_span_bytes': len(descriptor_words) * 4,
        'descriptor_to_table_gap': int(native_descriptor['region_start']) - int(native_descriptor['descriptor_offset']),
        'table_to_page_map_gap': (int(page_map['offset']) - int(native_descriptor['region_end'])) if page_map else None,
        'pointer_targets': pointer_targets,
        'aux_pointer_targets': aux_pointer_targets,
        'page_layout': page_layout,
        'confidence_score': confidence_score,
        'confidence': confidence,
    }


def _codered_compare_descriptor_to_scr(scr_info: dict | None, native_descriptor: dict | None) -> dict | None:
    if not scr_info or not native_descriptor:
        return None
    scr_words = {
        0x04: _codered_bswap32(int(scr_info['u32_le_04'])),
        0x08: _codered_bswap32(int(scr_info['u32_le_08'])),
        0x0C: _codered_bswap32(int(scr_info['u32_le_0C'])),
        0x10: _codered_bswap32(int(scr_info['u32_le_10'])),
        0x14: _codered_bswap32(int(scr_info['u32_le_14'])),
        0x18: _codered_bswap32(int(scr_info['u32_le_18'])),
        0x1C: _codered_bswap32(int(scr_info['u32_le_1C'])),
    }
    matches: list[dict] = []
    descriptor_words = list(native_descriptor.get('descriptor_words') or [])[:12]
    for desc_index, desc_value in enumerate(descriptor_words):
        if desc_value == 0:
            continue
        for hdr_off, scr_value in scr_words.items():
            if scr_value == 0:
                continue
            if desc_value == scr_value:
                matches.append({
                    'descriptor_word_index': desc_index,
                    'descriptor_value': desc_value,
                    'scr_header_offset': hdr_off,
                    'scr_header_be_value': scr_value,
                })
    if not matches:
        return None
    return {'match_count': len(matches), 'matches': matches[:16]}


def _codered_find_companion_scr_crosscheck(path: Path, companions: list[Path], native_descriptor: dict | None) -> dict | None:
    if not native_descriptor:
        return None
    for comp in companions:
        if comp.suffix.lower() != '.sco' or not comp.exists():
            continue
        scr_info = _codered_analyze_scr_container(read_bytes(comp))
        cross = _codered_compare_descriptor_to_scr(scr_info, native_descriptor)
        if cross:
            cross['companion'] = comp
            return cross
    return None


def _codered_find_wsc_descriptor_from_companions(path: Path, companions: list[Path]) -> tuple[dict | None, Path | None]:
    for comp in companions:
        if comp.suffix.lower() != '.wsc' or not comp.exists() or comp == path:
            continue
        try:
            analysis = analyze_script_payload(comp)
        except Exception:
            continue
        if analysis.get('native_descriptor'):
            return analysis.get('native_descriptor'), comp
    return None, None


def _codered_sha1_hex(data: bytes) -> str:
    return _codered_hashlib.sha1(data).hexdigest()


def _codered_read_archive_slot_bytes(archive_path: Path, archive_entry: dict) -> bytes:
    if archive_entry.get('type') != 'file':
        raise ValueError('Only file archive entries have a byte slot.')
    with archive_path.open('rb') as f:
        f.seek(int(archive_entry.get('offset') or 0))
        return f.read(int(archive_entry.get('size_in_archive') or 0))


def _codered_find_archive_entry(parsed_archive: dict | None, archive_entry: dict) -> dict | None:
    if not parsed_archive:
        return None
    target_index = archive_entry.get('index')
    target_path = archive_entry.get('path')
    for candidate in parsed_archive.get('entries', []):
        if candidate.get('type') != 'file':
            continue
        if target_index is not None and candidate.get('index') == target_index:
            return candidate
        if target_path and candidate.get('path') == target_path:
            return candidate
    return None


def _codered_try_decompress_like(coded_bytes: bytes, compressed_hint: bool = True) -> tuple[bytes | None, str | None, int | None]:
    if coded_bytes.startswith(b'\x28\xB5\x2F\xFD'):
        try:
            proc = subprocess.run(['zstd', '-d', '-q', '--stdout'], input=coded_bytes, capture_output=True, check=True)
            return proc.stdout, 'zstd', None
        except Exception:
            pass
    if compressed_hint or _looks_like_zlib_payload(coded_bytes):
        for wbits in (-15, 15, 31):
            try:
                return zlib.decompress(coded_bytes, wbits), 'zlib', wbits
            except Exception:
                continue
    return None, None, None


def _codered_rebuild_non_resource_compressed_stream(original_coded: bytes, processed_payload: bytes, target_coded_size: int | None = None, prefer_fit_within_target: bool = False) -> tuple[bytes | None, list[str], str | None]:
    notes: list[str] = []
    payload, codec, zlib_wbits = _codered_try_decompress_like(original_coded, compressed_hint=True)
    if payload is None or codec is None:
        return None, ['Could not determine a supported compression codec for the current archive slot.'], None
    if payload == processed_payload:
        return original_coded, ['Processed payload unchanged; reused original coded slot bytes.'], codec
    if codec == 'zstd':
        rebuilt, codec_label, codec_notes = _codered_select_zstd_candidate(
            processed_payload,
            _codered_parse_zstd_frame(original_coded),
            reference_size=len(original_coded),
            target_size=target_coded_size,
            prefer_fit_within_target=prefer_fit_within_target,
        )
        notes.append(f'Recompressed payload using {codec_label}.')
        notes.extend(codec_notes)
        return rebuilt, notes, 'zstd'
    levels = [9, 8, 7, 6, 5, 4, 3, 2, 1]
    candidates: list[tuple[tuple[int, int, int], bytes, int]] = []
    for level in levels:
        try:
            if zlib_wbits == 15:
                rebuilt = zlib.compress(processed_payload, level=level)
            else:
                comp = zlib.compressobj(level=level, wbits=zlib_wbits if zlib_wbits is not None else 15)
                rebuilt = comp.compress(processed_payload) + comp.flush()
        except Exception:
            continue
        size = len(rebuilt)
        target = target_coded_size if target_coded_size is not None else len(original_coded)
        if prefer_fit_within_target and target_coded_size is not None:
            score = (0 if size <= target else 1, abs(target - size), abs(len(original_coded) - size))
        else:
            score = (abs(target - size), 0 if size <= target else 1, abs(len(original_coded) - size))
        candidates.append((score, rebuilt, level))
    if not candidates:
        return None, ['Zlib recompression failed for all tested levels.'], 'zlib'
    _, rebuilt, level = min(candidates, key=lambda item: item[0])
    notes.append(f'Recompressed payload using zlib(wbits={zlib_wbits}, level={level}).')
    return rebuilt, notes, 'zlib'


def _codered_update_rpf6_entry_metadata(archive_copy_path: Path, archive_info: dict, archive_entry: dict, new_size_in_archive: int | None = None, new_total_size: int | None = None, new_offset: int | None = None) -> None:
    data = bytearray(read_bytes(archive_copy_path))
    toc_start = 16
    toc_size = int(archive_info.get('toc_size') or 0)
    toc = bytes(data[toc_start:toc_start + toc_size])
    if archive_info.get('enc_flag'):
        toc = _rpf6_decrypt(toc)
    toc_buf = bytearray(toc)
    idx = int(archive_entry.get('index') or 0)
    off = idx * 20
    if off + 20 > len(toc_buf):
        raise ValueError('Archive TOC entry offset is out of range.')
    a, b, c, d, e = struct.unpack('>5I', bytes(toc_buf[off:off + 20]))
    if new_size_in_archive is not None:
        b = (b & 0xF0000000) | (int(new_size_in_archive) & 0x0FFFFFFF)
    if new_total_size is not None and not archive_entry.get('is_resource'):
        d = (d & 0xC0000000) | (int(new_total_size) & 0x3FFFFFFF)
    if new_offset is not None:
        aligned_offset = int(new_offset)
        if aligned_offset % 8 != 0:
            raise ValueError('Archive entry offsets must stay 8-byte aligned.')
        if archive_entry.get('is_resource'):
            c = ((aligned_offset // 8) & 0x7FFFFF00) | (_rpf_resource_type(c) & 0xFF)
        else:
            c = (aligned_offset // 8) & 0x7FFFFFFF
    toc_buf[off:off + 20] = struct.pack('>5I', a, b, c, d, e)
    out_toc = _codered_rpf6_encrypt(bytes(toc_buf)) if archive_info.get('enc_flag') else bytes(toc_buf)
    data[toc_start:toc_start + toc_size] = out_toc
    archive_copy_path.write_bytes(data)


def _codered_prepare_archive_candidate_bytes(original_slot: bytes, original_extract: bytes, saved_data: bytes, archive_entry: dict) -> tuple[bytes | None, int | None, int | None, list[str], str | None]:
    notes: list[str] = []
    storage_kind = 'resource' if archive_entry.get('is_resource') else ('compressed' if archive_entry.get('is_compressed') else 'plain')
    slot_size = int(archive_entry.get('size_in_archive') or 0)
    total_size = int(archive_entry.get('total_size') or 0)
    if archive_entry.get('is_resource'):
        original_resource = parse_resource_header(original_slot)
        saved_resource = parse_resource_header(saved_data)
        if not original_resource or not saved_resource:
            return None, None, None, ['Resource-backed archive entry requires a valid resource stream replacement.'], storage_kind
        if original_resource.get('ident_raw') != saved_resource.get('ident_raw') or original_resource.get('resource_type') != saved_resource.get('resource_type'):
            return None, None, None, ['Replacement resource stream does not preserve the original resource identity/type.'], storage_kind
        original_payload = extract_resource_payload(original_slot, original_resource).get('payload', b'')
        saved_payload = extract_resource_payload(saved_data, saved_resource).get('payload', b'')
        if len(saved_payload) != len(original_payload):
            return None, None, None, ['Resource payload length changed; current safe lane keeps resource total size fixed.'], storage_kind
        rebuilt, rebuild_notes = rebuild_resource_stream_from_processed_payload(original_slot, saved_payload, target_coded_size=slot_size, prefer_fit_within_target=True)
        if rebuilt is None:
            return None, None, None, rebuild_notes or ['Resource rebuild failed.'], storage_kind
        notes.extend(rebuild_notes)
        verify_ok, verify_msg = verify_resource_roundtrip(saved_data, rebuilt)
        notes.append(verify_msg)
        if not verify_ok:
            return None, None, None, notes, storage_kind
        if len(rebuilt) > slot_size:
            notes.append(f'Resource stream grew beyond the original slot ({len(rebuilt):,} > {slot_size:,}); relocation-to-appended-span will be required in the archive copy.')
        return rebuilt, len(rebuilt), total_size, notes, storage_kind
    if archive_entry.get('is_compressed'):
        rebuilt, rebuild_notes, codec = _codered_rebuild_non_resource_compressed_stream(original_coded=original_slot, processed_payload=saved_data, target_coded_size=slot_size, prefer_fit_within_target=True)
        notes.extend(rebuild_notes)
        if rebuilt is None:
            return None, None, None, notes, storage_kind
        check_payload, _, _ = _codered_try_decompress_like(rebuilt, compressed_hint=True)
        if check_payload != saved_data:
            notes.append('Rebuilt compressed stream did not decompress back to the replacement payload cleanly.')
            return None, None, None, notes, storage_kind
        if len(rebuilt) > slot_size:
            notes.append(f'Compressed stream grew beyond the original slot ({len(rebuilt):,} > {slot_size:,}); relocation-to-appended-span will be required in the archive copy.')
        notes.append(f'Compressed entry rebuild verified through {codec or "codec"} re-read.')
        return rebuilt, len(rebuilt), len(saved_data), notes, storage_kind
    if len(saved_data) != slot_size:
        notes.append(f'Plain archive entry size changed ({len(saved_data):,} vs {slot_size:,}); relocation-to-appended-span will be required in the archive copy.')
    return saved_data, len(saved_data), len(saved_data), notes, storage_kind


def _codered_append_archive_payload(archive_copy_path: Path, payload: bytes) -> int:
    current_size = archive_copy_path.stat().st_size
    aligned_size = (current_size + 7) & ~7
    padding = aligned_size - current_size
    with archive_copy_path.open('ab') as f:
        if padding:
            f.write(b'\x00' * padding)
        f.write(payload)
    return aligned_size


def _codered_patch_archive_copy_entry(archive_copy_path: Path, archive_entry: dict, source_path: Path) -> dict:
    result = {
        'status': 'blocked',
        'reason': 'Archive copy patch did not run.',
        'archive_copy_path': str(archive_copy_path),
        'source_path': str(source_path),
        'internal_path': str(archive_entry.get('path', '')),
    }
    try:
        current_archive = parse_rpf6(archive_copy_path)
        if current_archive is None:
            result['reason'] = 'Patched archive copy could not be parsed.'
            return result
        live_entry = _codered_find_archive_entry(current_archive, archive_entry)
        if not live_entry:
            result['reason'] = 'Target archive entry could not be resolved in the working copy.'
            return result
        if source_path.suffix.lower() != Path(live_entry.get('name', '')).suffix.lower():
            result['reason'] = 'Replacement suffix must match the target archive entry suffix.'
            return result
        original_slot = _codered_read_archive_slot_bytes(archive_copy_path, live_entry)
        original_extract = extract_rpf_entry(archive_copy_path, live_entry)
        saved_data = read_bytes(source_path)
        if saved_data == original_extract:
            result['status'] = 'identical'
            result['reason'] = 'Replacement file already matches the extracted archive entry payload.'
            result['storage_kind'] = 'resource' if live_entry.get('is_resource') else ('compressed' if live_entry.get('is_compressed') else 'plain')
            result['probe_slot_sha1'] = _codered_sha1_hex(original_slot)
            result['probe_extract_sha1'] = _codered_sha1_hex(original_extract)
            result['archive_slot_exact_size_match'] = True
            result['archive_slot_size_delta'] = 0
            result['new_size_in_archive'] = int(live_entry.get('size_in_archive') or len(original_slot))
            result['relocated'] = False
            return result
        candidate_bytes, new_size_in_archive, new_total_size, notes, storage_kind = _codered_prepare_archive_candidate_bytes(original_slot, original_extract, saved_data, live_entry)
        result['storage_kind'] = storage_kind
        result['notes'] = notes
        if candidate_bytes is None or new_size_in_archive is None:
            result['reason'] = notes[-1] if notes else 'Candidate could not be prepared for archive copy patching.'
            return result
        slot_size = int(live_entry.get('size_in_archive') or 0)
        original_offset = int(live_entry.get('offset') or 0)
        relocated = new_size_in_archive > slot_size
        result['relocated'] = relocated
        if relocated:
            new_offset = _codered_append_archive_payload(archive_copy_path, candidate_bytes)
            _codered_update_rpf6_entry_metadata(archive_copy_path, current_archive, live_entry, new_size_in_archive=new_size_in_archive, new_total_size=new_total_size, new_offset=new_offset)
            result['new_offset'] = new_offset
            result['old_offset'] = original_offset
        else:
            with archive_copy_path.open('r+b') as f:
                f.seek(original_offset)
                f.write(candidate_bytes)
                if new_size_in_archive < slot_size:
                    f.write(b'\x00' * (slot_size - new_size_in_archive))
            _codered_update_rpf6_entry_metadata(archive_copy_path, current_archive, live_entry, new_size_in_archive=new_size_in_archive, new_total_size=new_total_size)
        reparsed = parse_rpf6(archive_copy_path)
        copied_entry = _codered_find_archive_entry(reparsed, live_entry)
        if not copied_entry:
            result['reason'] = 'Patched archive copy was written, but the target entry could not be found afterwards.'
            return result
        extracted = extract_rpf_entry(archive_copy_path, copied_entry)
        result['probe_slot_sha1'] = _codered_sha1_hex(_codered_read_archive_slot_bytes(archive_copy_path, copied_entry))
        result['probe_extract_sha1'] = _codered_sha1_hex(extracted)
        result['archive_slot_exact_size_match'] = (new_size_in_archive == slot_size)
        result['archive_slot_size_delta'] = new_size_in_archive - slot_size
        result['new_size_in_archive'] = new_size_in_archive
        result['new_offset'] = int(copied_entry.get('offset') or original_offset)
        if extracted == saved_data:
            if relocated:
                result['status'] = 'archive_copy_replace_relocated_verified'
                result['reason'] = 'Patched a copied archive, relocated the entry to an appended span, and re-read the target entry successfully.'
            else:
                result['status'] = 'archive_copy_replace_verified'
                result['reason'] = 'Patched a copied archive and re-read the target entry successfully.'
            return result
        result['reason'] = 'Patched archive copy did not re-read back to the replacement payload cleanly.'
        return result
    except Exception as exc:
        result['reason'] = f'Archive copy patch failed: {exc}'
        return result


def _codered_apply_non_script_candidate_to_archive_copy(original_path: Path, saved_path: Path, archive_entry: dict, archive_path: Path) -> dict:
    result = {
        'status': 'probe_blocked',
        'reason': 'Archive copy replace did not run.',
    }
    try:
        original_data = read_bytes(original_path)
    except Exception as exc:
        result['reason'] = str(exc)
        return result
    if original_path.suffix.lower() != saved_path.suffix.lower():
        result['reason'] = 'Replacement suffix must match the extracted archive entry suffix.'
        return result
    try:
        current_extract = extract_rpf_entry(archive_path, archive_entry)
        current_slot = _codered_read_archive_slot_bytes(archive_path, archive_entry)
    except Exception as exc:
        result['reason'] = f'Could not read current archive data: {exc}'
        return result
    result['current_slot_matches_original_extract'] = (current_extract == original_data)
    result['current_slot_sha1'] = _codered_sha1_hex(current_slot)
    if not result['current_slot_matches_original_extract']:
        result['reason'] = 'The current archive entry no longer matches the extracted source file; blocked to avoid patching stale data.'
        return result
    probe_archive = saved_path.with_name(f"{archive_path.stem}__{saved_path.stem}_archive_copy_replace{archive_path.suffix}")
    try:
        shutil.copy2(archive_path, probe_archive)
        probe_result = _codered_patch_archive_copy_entry(probe_archive, archive_entry, saved_path)
        result.update({k: v for k, v in probe_result.items() if k != 'source_path'})
        return result
    except Exception as exc:
        result['reason'] = f'Archive copy replace failed: {exc}'
        return result


def _codered_normalize_patch_root(archive_path: Path, patch_root: Path) -> Path:
    direct = patch_root / f'{archive_path.stem}_contents'
    if direct.exists() and direct.is_dir():
        return direct
    if patch_root.name.lower() == f'{archive_path.stem}_contents'.lower():
        return patch_root
    return patch_root


def _codered_match_patch_file_to_archive_entry(patch_file: Path, patch_root: Path, archive_info: dict) -> tuple[dict | None, str]:
    rel = patch_file.relative_to(patch_root).as_posix().lower()
    normalized_rel = rel[5:] if rel.startswith('root/') else rel
    direct_map = {}
    direct_root_map = {}
    name_map: dict[str, list[dict]] = {}
    for entry in archive_info.get('entries', []):
        if entry.get('type') != 'file':
            continue
        path_lower = str(entry.get('path', '')).lower()
        direct_map[path_lower[5:] if path_lower.startswith('root/') else path_lower] = entry
        direct_root_map[path_lower] = entry
        name_map.setdefault(str(entry.get('name', '')).lower(), []).append(entry)
    if rel in direct_root_map:
        return direct_root_map[rel], 'internal-path'
    if normalized_rel in direct_map:
        return direct_map[normalized_rel], 'relative-path'
    by_name = name_map.get(patch_file.name.lower(), [])
    if len(by_name) == 1:
        return by_name[0], 'unique-name'
    return None, 'unmatched'


def _codered_apply_patch_folder_to_archive_copy(archive_path: Path, patch_root: Path, output_archive: Path | None = None) -> dict:
    archive_info = parse_rpf6(archive_path)
    if archive_info is None:
        raise ValueError('RPF6 parse failed for the selected archive.')
    patch_root = _codered_normalize_patch_root(archive_path, patch_root)
    patch_files = sorted([p for p in patch_root.rglob('*') if p.is_file()])
    if not patch_files:
        raise ValueError('Patch folder does not contain any files.')
    if output_archive is None:
        output_archive = patch_root / f'{archive_path.stem}__patched_copy{archive_path.suffix}'
    working_copy_created = False
    results: list[dict] = []
    unmatched: list[str] = []
    for patch_file in patch_files:
        entry, match_mode = _codered_match_patch_file_to_archive_entry(patch_file, patch_root, archive_info)
        if entry is None:
            unmatched.append(str(patch_file.relative_to(patch_root)).replace('\\', '/'))
            continue
        if not working_copy_created:
            shutil.copy2(archive_path, output_archive)
            working_copy_created = True
        current_info = parse_rpf6(output_archive)
        current_entry = _codered_find_archive_entry(current_info, entry)
        if current_entry is None:
            results.append({'patch': str(patch_file), 'status': 'blocked', 'reason': 'Target entry could not be found in the working copy.', 'match_mode': match_mode})
            continue
        patch_result = _codered_patch_archive_copy_entry(output_archive, current_entry, patch_file)
        patch_result['patch'] = str(patch_file)
        patch_result['match_mode'] = match_mode
        results.append(patch_result)
    if not working_copy_created:
        shutil.copy2(archive_path, output_archive)
    applied = sum(1 for item in results if item.get('status') in {'archive_copy_replace_verified', 'archive_copy_replace_relocated_verified'})
    identical = sum(1 for item in results if item.get('status') == 'identical')
    blocked = sum(1 for item in results if item.get('status') not in {'archive_copy_replace_verified', 'archive_copy_replace_relocated_verified', 'identical'})
    relocated = sum(1 for item in results if item.get('status') == 'archive_copy_replace_relocated_verified')
    report_path = output_archive.with_name(output_archive.stem + '_patch_folder_report.txt')
    lines = [
        'Code RED Archive Patch Folder Report',
        '==================================',
        '',
        f'Archive source: {archive_path}',
        f'Working copy: {output_archive}',
        f'Patch folder: {patch_root}',
        f'Patch files scanned: {len(patch_files)}',
        f'Applied: {applied}',
        f'Applied with relocation: {relocated}',
        f'Identical: {identical}',
        f'Blocked: {blocked}',
        f'Unmatched: {len(unmatched)}',
        '',
    ]
    if unmatched:
        lines.append('Unmatched patch files:')
        lines.extend(f'- {item}' for item in unmatched[:80])
        lines.append('')
    lines.append('Patch results:')
    for item in results:
        lines.append(f"- [{item.get('status', 'blocked')}] {Path(item.get('patch', '')).name} -> {item.get('internal_path', '')} | match={item.get('match_mode', '')} | reason={item.get('reason', '')}")
        if item.get('relocated'):
            lines.append(f"    relocation: old_offset=0x{int(item.get('old_offset') or 0):X} new_offset=0x{int(item.get('new_offset') or 0):X}")
        notes = item.get('notes') or []
        for note in notes[:6]:
            lines.append(f'    note: {note}')
    report_path.write_text('\n'.join(lines), encoding='utf-8')
    return {
        'archive_source': archive_path,
        'working_copy': output_archive,
        'patch_root': patch_root,
        'scanned': len(patch_files),
        'applied': applied,
        'identical': identical,
        'blocked': blocked,
        'relocated': relocated,
        'unmatched': unmatched,
        'results': results,
        'report_path': report_path,
    }


def _codered_apply_script_candidate_to_archive_copy(original_path: Path, saved_path: Path, archive_entry: dict, archive_path: Path) -> dict:
    result = {
        'status': 'probe_blocked',
        'reason': 'Archive copy probe did not run.',
    }
    assessment = _codered_build_script_reintegration_assessment(
        original_path,
        saved_path,
        'script-roundtrip-clone',
        archive_entry=archive_entry,
        archive_path=archive_path,
    )
    result['assessment_status'] = assessment.get('status')
    result['assessment_reason'] = assessment.get('reason')
    try:
        original_data = read_bytes(original_path)
        saved_data = read_bytes(saved_path)
    except Exception as exc:
        result['reason'] = str(exc)
        return result
    try:
        current_slot = _codered_read_archive_slot_bytes(archive_path, archive_entry)
    except Exception as exc:
        result['reason'] = f'Could not read current archive slot bytes: {exc}'
        return result
    result['current_slot_matches_original_extract'] = (current_slot == original_data)
    result['current_slot_sha1'] = _codered_sha1_hex(current_slot)
    if not result['current_slot_matches_original_extract']:
        result['reason'] = 'The current archive slot bytes no longer match the extracted source file; blocked to avoid patching against stale extraction data.'
        return result
    core_ok = bool(assessment.get('same_suffix')) and bool(assessment.get('resource_header_match')) and bool(assessment.get('processed_payload_match'))
    slot_ok = bool(assessment.get('archive_slot_exact_size_match'))
    if not core_ok:
        result['reason'] = 'Candidate failed the required script verification gates for archive copy probing.'
        return result
    if not slot_ok:
        result['reason'] = 'Candidate does not exactly match the current archive byte span; copy probe requires exact slot-size parity.'
        return result
    probe_archive = saved_path.with_name(f"{archive_path.stem}__{saved_path.stem}_archive_copy_probe{archive_path.suffix}")
    try:
        shutil.copy2(archive_path, probe_archive)
        with probe_archive.open('r+b') as f:
            f.seek(int(archive_entry.get('offset') or 0))
            f.write(saved_data)
        parsed_copy = parse_rpf6(probe_archive)
        copied_entry = _codered_find_archive_entry(parsed_copy, archive_entry)
        if not copied_entry:
            result['status'] = 'probe_failed'
            result['reason'] = 'Patched archive copy was written, but the target entry could not be resolved afterwards.'
            result['probe_archive_path'] = str(probe_archive)
            return result
        copied_slot = _codered_read_archive_slot_bytes(probe_archive, copied_entry)
        result['probe_archive_path'] = str(probe_archive)
        result['probe_slot_sha1'] = _codered_sha1_hex(copied_slot)
        result['probe_slot_matches_saved_bytes'] = (copied_slot == saved_data)
        if copied_entry.get('is_resource'):
            ok, verify_msg = verify_resource_roundtrip(saved_data, copied_slot)
        else:
            ok = (copied_slot == saved_data)
            verify_msg = 'Patched archive copy slot bytes matched the saved candidate exactly.' if ok else 'Patched archive copy slot bytes did not match the saved candidate.'
        result['probe_verify_message'] = verify_msg
        result['probe_processed_payload_match'] = ok
        if result['probe_slot_matches_saved_bytes'] and ok:
            result['status'] = 'archive_copy_probe_verified'
            result['reason'] = 'Patched a copied archive in-place at the existing slot and re-verified the saved candidate against the copied archive entry.'
        else:
            result['status'] = 'probe_failed'
            result['reason'] = 'Patched archive copy did not round-trip cleanly during re-verification.'
        return result
    except Exception as exc:
        result['reason'] = f'Archive copy probe failed: {exc}'
        return result


def _codered_build_script_reintegration_assessment(original_path: Path, saved_path: Path, action_label: str, archive_entry: dict | None = None, archive_path: Path | None = None) -> dict:
    result = {
        'action': action_label,
        'status': 'hold',
        'reason': 'Direct original-archive write-back remains unimplemented in the current fallback; archive-copy probing may still be available for exact-size candidates.',
    }
    if archive_entry:
        result['archive_path'] = str(archive_path) if archive_path is not None else ''
        result['archive_internal_path'] = str(archive_entry.get('path', ''))
        result['archive_storage_kind'] = 'resource' if archive_entry.get('is_resource') else ('compressed' if archive_entry.get('is_compressed') else 'plain')
        result['archive_entry_size_in_archive'] = int(archive_entry.get('size_in_archive') or 0)
        result['archive_entry_total_size'] = int(archive_entry.get('total_size') or 0)
        result['archive_offset'] = int(archive_entry.get('offset') or 0)
        result['archive_size_match_meaningful'] = bool(archive_entry.get('is_resource') or not archive_entry.get('is_compressed'))
    if action_label != 'script-roundtrip-clone':
        result['status'] = 'not_reimport_candidate'
        result['reason'] = 'Only a round-trip clone is even eligible for payload-level comparison.'
        return result
    try:
        original_data = read_bytes(original_path)
        saved_data = read_bytes(saved_path)
    except Exception as exc:
        result['status'] = 'candidate_unreadable'
        result['reason'] = str(exc)
        return result
    result['original_sha1'] = _codered_sha1_hex(original_data)
    result['saved_sha1'] = _codered_sha1_hex(saved_data)
    result['original_size'] = len(original_data)
    result['saved_size'] = len(saved_data)
    result['size_delta'] = len(saved_data) - len(original_data)
    result['byte_identical'] = (original_data == saved_data)
    result['same_suffix'] = (original_path.suffix.lower() == saved_path.suffix.lower())
    if archive_entry:
        slot_size = int(archive_entry.get('size_in_archive') or 0)
        result['archive_slot_exact_size_match'] = (len(saved_data) == slot_size) if slot_size > 0 else False
        result['archive_slot_within_span'] = (len(saved_data) <= slot_size) if slot_size > 0 else False
        result['archive_slot_headroom'] = (slot_size - len(saved_data)) if slot_size > 0 and len(saved_data) <= slot_size else None
        result['archive_slot_size_delta'] = (len(saved_data) - slot_size) if slot_size > 0 else None
        try:
            current_slot = _codered_read_archive_slot_bytes(archive_path, archive_entry) if archive_path is not None else b''
            if current_slot:
                result['archive_slot_current_sha1'] = _codered_sha1_hex(current_slot)
                result['archive_slot_matches_original_extract'] = (current_slot == original_data)
        except Exception as exc:
            result['archive_slot_read_error'] = str(exc)
    orig_res = parse_resource_header(original_data)
    saved_res = parse_resource_header(saved_data)
    result['resource_header_match'] = bool(orig_res and saved_res and orig_res.get('ident_name') == saved_res.get('ident_name') and orig_res.get('resource_type') == saved_res.get('resource_type'))
    if orig_res and saved_res:
        orig_info = extract_resource_payload(original_data, orig_res)
        saved_info = extract_resource_payload(saved_data, saved_res)
        ok, verify_msg = verify_resource_roundtrip(original_data, saved_data)
        result['processed_payload_match'] = ok
        result['verify_message'] = verify_msg
        frame_compare = _codered_compare_zstd_frames(orig_info.get('zstd_frame'), saved_info.get('zstd_frame'))
        if frame_compare:
            result['zstd_frame_compare'] = frame_compare
            result['original_zstd_frame'] = orig_info.get('zstd_frame')
            result['saved_zstd_frame'] = saved_info.get('zstd_frame')
    else:
        result['processed_payload_match'] = False
        result['verify_message'] = 'Round-trip verification unavailable because one side is not a parsed resource.'
    core_ok = result['same_suffix'] and result['resource_header_match'] and result['processed_payload_match']
    if archive_entry and result.get('archive_size_match_meaningful'):
        slot_ok = bool(result.get('archive_slot_exact_size_match'))
        result['archive_slot_gate_pass'] = slot_ok
        if core_ok and slot_ok and result.get('byte_identical'):
            result['status'] = 'exact_roundtrip_clone_candidate'
            result['reason'] = 'Saved file is byte-identical to the extracted archive entry and fits the current archive entry span in dry-run. Direct original-archive mutation is still unimplemented, but an archive-copy probe may be used.'
        elif core_ok and slot_ok:
            result['status'] = 'dry_run_slot_fit_candidate'
            result['reason'] = 'Processed payload matches, and saved byte size matches the current archive entry span in dry-run. Direct original-archive mutation is still unimplemented, but an archive-copy probe may be used.'
        elif core_ok:
            result['status'] = 'payload_verified_clone_only'
            result['reason'] = 'Processed payload matches, but the saved byte size does not match the current archive entry span for a simple in-place dry-run.'
        else:
            result['status'] = 'do_not_reimport'
            result['reason'] = 'Candidate failed one or more required gating checks.'
    else:
        if core_ok:
            result['status'] = 'payload_verified_clone_only'
            result['reason'] = 'Processed payload matches after rebuild verification, but byte identity and archive write-back are still unproven.'
        else:
            result['status'] = 'do_not_reimport'
            result['reason'] = 'Candidate failed one or more required gating checks.'
    return result


def _codered_analyze_scr_container(data: bytes) -> dict | None:
    if len(data) < 32 or data[:3] != b'SCR':
        return None
    return {
        'magic': data[:4].decode('latin-1', errors='replace'),
        'u32_le_04': int.from_bytes(data[4:8], 'little', signed=False),
        'u32_le_08': int.from_bytes(data[8:12], 'little', signed=False),
        'u32_le_0C': int.from_bytes(data[12:16], 'little', signed=False),
        'u32_le_10': int.from_bytes(data[16:20], 'little', signed=False),
        'u32_le_14': int.from_bytes(data[20:24], 'little', signed=False),
        'u32_le_18': int.from_bytes(data[24:28], 'little', signed=False),
        'u32_le_1C': int.from_bytes(data[28:32], 'little', signed=False),
    }


def _codered_find_script_companions(path: Path) -> list[Path]:
    siblings: list[Path] = []
    if not path.exists():
        return siblings
    for ext in SCRIPT_BINARY_EXTENSIONS + SOURCE_CODE_EXTENSIONS:
        cand = path.with_suffix(ext)
        if cand != path and cand.exists():
            siblings.append(cand)
    return siblings


def format_native_hit(hit: dict) -> str:
    param_parts = []
    for p in hit.get('params', [])[:8]:
        if isinstance(p, dict):
            ptype = str(p.get('type') or 'Any')
            pname = str(p.get('name') or 'arg')
            param_parts.append(f'{ptype} {pname}')
    signature = f"{hit.get('return_type', 'Unknown')} {hit.get('name', 'UNKNOWN')}({', '.join(param_parts)})"
    offset_text = ', '.join(f'0x{o:X}' for o in hit.get('offsets', [])[:6]) or '<none>'
    category = hit.get('category', 'UNKNOWN')
    conf = str(hit.get('confidence', 'low')).upper()
    aligned = hit.get('aligned_count', 0)
    region_hits = hit.get('region_hits', 0)
    return f"{signature}  // {category}  hash=0x{hit['hash']:08X}  hits={hit['count']}  aligned={aligned}  region={region_hits}  confidence={conf}  offsets={offset_text}"


CODERED_MAGIC_OPCODE_NAMES = [
    'Nop','iAdd','iSub','iMult','iDiv','iMod','iNot','iNeg','iCmpEq','iCmpNe','iCmpGt','iCmpGe','iCmpLt','iCmpLe',
    'fAdd','fSub','fMult','fDiv','fMod','fNeg','fCmpEq','fCmpNe','fCmpGt','fCmpGe','fCmpLt','fCmpLe',
    'vAdd','vSub','vMult','vDiv','vNeg','And','Or','Xor','ItoF','FtoI','FtoV','iPushByte1','iPushByte2','iPushByte3',
    'iPushInt','fPush','dup','pop','Native','Enter','Return','pGet','pSet','pPeekSet','ToStack','FromStack','pArray1','ArrayGet1','ArraySet1',
    'pFrame1','GetFrame1','SetFrame1','pStatic1','StaticGet1','StaticSet1','Add1','GetStruct1','SetStruct1','Mult1','iPushShort','Add2','GetStruct2','SetStruct2','Mult2',
    'pArray2','ArrayGet2','ArraySet2','pFrame2','GetFrame2','SetFrame2','pStatic2','StaticGet2','StaticSet2','pGlobal2','GlobalGet2','GlobalSet2',
    'Call2','Call2h1','Call2h2','Call2h3','Call2h4','Call2h5','Call2h6','Call2h7','Call2h8','Call2h9','Call2hA','Call2hB','Call2hC','Call2hD','Call2hE','Call2hF',
    'Jump','JumpFalse','JumpNe','JumpEq','JumpLe','JumpLt','JumpGe','JumpGt','pGlobal3','GlobalGet3','GlobalSet3','iPushI24','Switch','PushString','PushArrayP','PushStringNull','StrCopy','ItoS','StrConCat','StrConCatInt','MemCopy','Catch','Throw','pCall',
    'ReturnP0R0','ReturnP0R1','ReturnP0R2','ReturnP0R3','ReturnP1R0','ReturnP1R1','ReturnP1R2','ReturnP1R3','ReturnP2R0','ReturnP2R1','ReturnP2R2','ReturnP2R3','ReturnP3R0','ReturnP3R1','ReturnP3R2','ReturnP3R3',
    'iPush_n1','iPush_0','iPush_1','iPush_2','iPush_3','iPush_4','iPush_5','iPush_6','iPush_7','fPush_n1','fPush_0','fPush_1','fPush_2','fPush_3','fPush_4','fPush_5','fPush_6','fPush_7',
    'PatchRet','PatchTrap0','PatchTrap1','PatchTrap2','PatchTrap3','PatchTrap4','PatchTrap5','PatchTrap6','PatchTrap7','PatchTrap8','PatchTrap9','PatchTrapA','PatchTrapB','PatchTrapC','PatchTrapD','PatchTrapE','PatchTrapF','CallPatch','CallOutOfPatch','LoadRef','StoreRef','StoreVector','MakeVector'
]


def _codered_magic_opcode_name(opcode: int) -> str:
    if 0 <= opcode < len(CODERED_MAGIC_OPCODE_NAMES):
        return CODERED_MAGIC_OPCODE_NAMES[opcode]
    return f'OP_0x{opcode:02X}'


def _codered_is_magic_return_opcode(opcode: int) -> bool:
    return opcode == 46 or 122 <= opcode <= 137


def _codered_magic_instruction_length(code: bytes, offset: int, stop_offset: int | None = None) -> int | None:
    stop = len(code) if stop_offset is None else min(len(code), stop_offset)
    if offset >= stop:
        return None
    opcode = code[offset]
    if opcode == 37:
        length = 2
    elif opcode == 38:
        length = 3
    elif opcode == 39:
        length = 4
    elif opcode in (40, 41):
        length = 5
    elif opcode == 44:
        length = 3
    elif opcode == 45:
        if offset + 5 > stop:
            return None
        length = 5 + int(code[offset + 4])
    elif opcode == 46:
        length = 3
    elif 52 <= opcode <= 64:
        length = 2
    elif 65 <= opcode <= 109:
        length = 3 if opcode != 109 else 4
    elif opcode == 110:
        if offset + 2 > stop:
            return None
        length = 2 + int(code[offset + 1]) * 6
    elif opcode == 111:
        if offset + 2 > stop:
            return None
        length = 2 + int(code[offset + 1])
    elif opcode == 112:
        if offset + 5 > stop:
            return None
        raw_len = int.from_bytes(code[offset + 1:offset + 5], 'little', signed=False)
        if raw_len < 0 or raw_len > 0x100000:
            raw_len = int(code[offset + 1])
        length = 5 + raw_len
    elif opcode in (114, 115, 116, 117):
        length = 2
    elif 0 <= opcode <= 178:
        length = 1
    else:
        return None
    if offset + length > stop:
        return None
    return length


def _codered_collect_native_table_entries(payload: bytes, native_descriptor: dict | None, *, limit: int | None = None) -> list[dict]:
    if not native_descriptor:
        return []
    region_start = int(native_descriptor.get('region_start') or 0)
    count = int(native_descriptor.get('region_count') or 0)
    if count <= 0:
        return []
    max_count = count if limit is None else min(count, max(0, limit))
    entries: list[dict] = []
    for index in range(max_count):
        off = region_start + index * 4
        if off + 4 > len(payload):
            break
        val = int.from_bytes(payload[off:off + 4], 'little', signed=False)
        meta = CODERED_NATIVE_DB.get(val) or {}
        entries.append({
            'index': index,
            'offset': off,
            'hash': val,
            'name': str(meta.get('name') or f'UNKNOWN_0x{val:08X}'),
            'category': str(meta.get('category') or 'UNKNOWN'),
            'return_type': str(meta.get('return_type') or 'Unknown'),
            'params': list(meta.get('params') or []),
            'comment': str(meta.get('comment') or ''),
        })
    return entries


def _codered_find_owner_function(functions: list[dict], offset: int) -> dict | None:
    lo = 0
    hi = len(functions) - 1
    best: dict | None = None
    while lo <= hi:
        mid = (lo + hi) // 2
        func = functions[mid]
        start = int(func.get('enter_offset') or 0)
        end = int(func.get('end_offset') or start)
        if offset < start:
            hi = mid - 1
        elif offset >= end:
            lo = mid + 1
            best = func
        else:
            return func
    if best and int(best.get('enter_offset') or 0) <= offset < int(best.get('end_offset') or 0):
        return best
    return None


def _codered_scan_wsc_bytecode(payload: bytes, native_descriptor: dict | None) -> dict | None:
    if not payload:
        return None
    code_stop = int(native_descriptor.get('descriptor_offset') or len(payload)) if native_descriptor else len(payload)
    code_stop = max(0, min(code_stop, len(payload)))
    if code_stop <= 0:
        return None
    opcode_hist = Counter()
    parse_errors: list[str] = []
    functions: list[dict] = []
    retpos = -3
    offset = 0
    ordinal = 0
    while offset < code_stop:
        length = _codered_magic_instruction_length(payload, offset, code_stop)
        if not length:
            parse_errors.append(f'0x{offset:X}: invalid/truncated opcode 0x{payload[offset]:02X}')
            offset += 1
            continue
        opcode = payload[offset]
        opcode_hist[_codered_magic_opcode_name(opcode)] += 1
        if opcode == 45 and offset + 5 <= code_stop:
            name_len = int(payload[offset + 4])
            name_end = min(code_stop, offset + 5 + name_len)
            raw_name = payload[offset + 5:name_end]
            try:
                decoded_name = raw_name.decode('latin-1', errors='replace').strip('\x00')
            except Exception:
                decoded_name = ''
            if not decoded_name:
                decoded_name = 'main' if offset == 0 else f'Function_{ordinal}'
            body_offset = offset if retpos < 0 else retpos + 3
            functions.append({
                'ordinal': ordinal,
                'name': decoded_name,
                'enter_offset': offset,
                'body_offset': max(offset, body_offset),
                'param_count': int(payload[offset + 1]),
                'var_count': ((int(payload[offset + 2]) << 8) | int(payload[offset + 3])),
                'name_len': name_len,
                'header_size': length,
            })
            ordinal += 1
        if _codered_is_magic_return_opcode(opcode):
            retpos = offset
        offset += length
    if not functions and payload[0] != 45:
        return None
    for index, func in enumerate(functions):
        next_body = code_stop if index + 1 >= len(functions) else int(functions[index + 1]['body_offset'])
        func['end_offset'] = max(int(func['enter_offset']), min(code_stop, next_body))
        func['span_bytes'] = max(0, int(func['end_offset']) - int(func['enter_offset']))
    full_table = _codered_collect_native_table_entries(payload, native_descriptor, limit=None)
    entry_by_index = {int(e['index']): e for e in full_table}
    function_by_body = {int(f['body_offset']): f for f in functions}
    native_calls: list[dict] = []
    local_calls: list[dict] = []
    offset = 0
    while offset < code_stop:
        length = _codered_magic_instruction_length(payload, offset, code_stop)
        if not length:
            offset += 1
            continue
        opcode = payload[offset]
        owner = _codered_find_owner_function(functions, offset)
        if opcode == 44 and offset + 3 <= code_stop:
            a = int(payload[offset + 1])
            b = int(payload[offset + 2])
            native_index = (((a << 2) & 0x300) | b)
            param_count = ((a & 0x3E) >> 1)
            has_return = bool(a & 0x01)
            entry = entry_by_index.get(native_index)
            native_calls.append({
                'offset': offset,
                'function': owner.get('name') if owner else '<unknown>',
                'native_index': native_index,
                'param_count': param_count,
                'has_return': has_return,
                'entry': entry,
            })
        elif 82 <= opcode <= 97 and offset + 3 <= code_stop:
            call_operand = int.from_bytes(payload[offset + 1:offset + 3], 'big', signed=False)
            target_loc = call_operand | ((opcode - 0x52) << 16)
            target = function_by_body.get(target_loc) or function_by_body.get(target_loc + 2)
            local_calls.append({
                'offset': offset,
                'function': owner.get('name') if owner else '<unknown>',
                'opcode': opcode,
                'target_loc': target_loc,
                'target': target.get('name') if target else None,
            })
        offset += length
    resolved_local = sum(1 for item in local_calls if item.get('target'))
    confidence_score = 0
    if functions:
        confidence_score += 2
    if functions and payload[0] == 45:
        confidence_score += 2
    if native_calls:
        confidence_score += 1
    if local_calls:
        confidence_score += 1
    if resolved_local >= max(8, len(local_calls) // 4) and local_calls:
        confidence_score += 2
    confidence = 'high' if confidence_score >= 6 else ('medium' if confidence_score >= 3 else 'low')
    function_samples = [
        {
            'ordinal': int(f['ordinal']),
            'name': str(f['name']),
            'enter_offset': int(f['enter_offset']),
            'body_offset': int(f['body_offset']),
            'end_offset': int(f['end_offset']),
            'param_count': int(f['param_count']),
            'var_count': int(f['var_count']),
            'span_bytes': int(f['span_bytes']),
        }
        for f in functions
    ]
    opcode_top = [{'opcode': name, 'count': count} for name, count in opcode_hist.most_common(32)]
    return {
        'code_stop': code_stop,
        'function_count': len(functions),
        'functions': function_samples,
        'opcode_histogram': opcode_top,
        'opcode_total': int(sum(opcode_hist.values())),
        'parse_error_count': len(parse_errors),
        'parse_errors': parse_errors[:32],
        'native_call_count': len(native_calls),
        'native_calls': native_calls,
        'local_call_count': len(local_calls),
        'local_calls': local_calls,
        'resolved_local_call_count': resolved_local,
        'resolved_local_call_ratio': (resolved_local / len(local_calls)) if local_calls else 0.0,
        'confidence_score': confidence_score,
        'confidence': confidence,
        'native_table_entries_full': full_table,
    }


# --- Code RED built-in Script Lab convenience pass (vehicle/spawn cue scanner) ---
CODERED_KNOWN_SCRIPT_SIGNATURES = {
    '77466ace5aa9059c096ee01ce9e21a1b2e0e010182f28e2fe1a019696581d4b4': {
        'name': 'playercar.wsc',
        'label': 'Player car gringo wrapper',
        'confidence': 'confirmed',
        'plain_answer': 'This is the known drivable-car spawn wrapper. The key block is Function_8 at payload offset 0x0712-0x073D: it pushes PlayerCarGringo_Car, calls native[45] with 7 parameters and a return value, then stores the returned handle in static[0].',
        'chain': [
            'traincar or gringo slot loads playercar.wsc',
            'Function_8 resolves local placement/context handles',
            "PushString 'PlayerCarGringo_Car'",
            'Native native[45] params=7 ret=1 creates/loads the player-car gringo/object',
            'StoreRef static[0] preserves the returned handle',
            'streaming helper waits on template/resource loading',
            'car_gringo.wsc and carcrank_gringo.wsc provide drive/start behavior',
        ],
        'spawn_block': [
            '0x0712 pGlobal2 46715',
            '0x0715 LoadRef',
            "0x0716 PushString 'PlayerCarGringo_Car'",
            '0x072C iPushShort 1194',
            '0x072F iPush_2',
            '0x0730 pFrame1 3',
            '0x0732 ToStack',
            '0x0733 iPush_2',
            '0x0734 pFrame1 6',
            '0x0736 ToStack',
            '0x0737 Native native[45] params=7 ret=1',
            '0x073A pStatic1 0',
            '0x073C StoreRef',
        ],
        'support_strings': [
            'Streaming',
            'Done Streaming',
            'Not enough room in the streaming array to fit a template! Raise the array size to fix!',
        ],
        'drive_support_files': ['car_gringo.wsc', 'carcrank_gringo.wsc'],
    },
}

CODERED_SCRIPT_SPAWN_TERMS = (
    'spawn', 'create', 'vehicle', 'car', 'truck', 'wagon', 'coach', 'train', 'horse',
    'template', 'streaming', 'gringo', 'locset', 'entity', 'actor', 'mount', 'crank',
)


def _codered_read_pushstring_records(payload: bytes, bytecode: dict | None) -> list[dict]:
    """Recover PushString instructions from a decoded Magic/RDR script payload."""
    if not payload:
        return []
    code_stop = len(payload)
    functions = []
    if bytecode:
        code_stop = int(bytecode.get('code_stop') or code_stop)
        functions = list(bytecode.get('functions') or [])
    code_stop = max(0, min(code_stop, len(payload)))
    records: list[dict] = []
    offset = 0
    while offset < code_stop:
        length = _codered_magic_instruction_length(payload, offset, code_stop)
        if not length:
            offset += 1
            continue
        opcode = payload[offset]
        if opcode == 112 and offset + 5 <= code_stop:
            raw_len = int.from_bytes(payload[offset + 1:offset + 5], 'little', signed=False)
            if 0 <= raw_len <= 0x100000 and offset + 5 + raw_len <= code_stop:
                raw = payload[offset + 5:offset + 5 + raw_len]
            else:
                raw_len = int(payload[offset + 1]) if offset + 2 <= code_stop else 0
                raw = payload[offset + 5: min(code_stop, offset + 5 + raw_len)]
            try:
                text = raw.decode('latin-1', errors='replace').rstrip('\x00')
            except Exception:
                text = ''
            if text:
                owner = _codered_find_owner_function(functions, offset) if functions else None
                records.append({
                    'offset': offset,
                    'function': owner.get('name') if owner else '<unknown>',
                    'length': raw_len,
                    'text': text,
                })
        offset += length
    return records


def _codered_nearby_native_calls(bytecode: dict | None, center_offset: int, before: int = 48, after: int = 96) -> list[dict]:
    if not bytecode:
        return []
    out = []
    for call in bytecode.get('native_calls') or []:
        try:
            off = int(call.get('offset') or 0)
        except Exception:
            continue
        if center_offset - before <= off <= center_offset + after:
            entry = call.get('entry') or {}
            out.append({
                'offset': off,
                'function': call.get('function') or '<unknown>',
                'native_index': int(call.get('native_index') or 0),
                'param_count': int(call.get('param_count') or 0),
                'has_return': bool(call.get('has_return')),
                'name': entry.get('name') if isinstance(entry, dict) else None,
                'hash': entry.get('hash') if isinstance(entry, dict) else None,
            })
    return out


def _codered_script_spawn_kind(text: str) -> str | None:
    low = text.lower()
    if 'playercargringo_car' in low:
        return 'player-car spawn wrapper'
    if 'car' in low and 'gringo' in low:
        return 'car gringo reference'
    if 'truck' in low:
        return 'truck reference'
    if 'wagon' in low or 'coach' in low:
        return 'wagon/coach reference'
    if 'train' in low:
        return 'train reference'
    if 'template' in low or 'streaming' in low:
        return 'template/streaming reference'
    if 'vehicle' in low:
        return 'vehicle reference'
    if 'gringo' in low:
        return 'gringo reference'
    return None


def _codered_collect_script_spawn_insights(path: Path, data: bytes, payload: bytes, strings: list[str], bytecode: dict | None, payload_info: dict | None = None) -> dict:
    raw_sha256 = _codered_hashlib.sha256(data).hexdigest()
    payload_sha1 = _codered_hashlib.sha1(payload or b'').hexdigest() if payload else ''
    known = CODERED_KNOWN_SCRIPT_SIGNATURES.get(raw_sha256)
    push_records = _codered_read_pushstring_records(payload, bytecode)
    cue_records: list[dict] = []
    for rec in push_records:
        kind = _codered_script_spawn_kind(str(rec.get('text') or ''))
        if not kind:
            continue
        near = _codered_nearby_native_calls(bytecode, int(rec.get('offset') or 0))
        score = 1
        text_low = str(rec.get('text') or '').lower()
        if 'playercargringo_car' in text_low:
            score += 8
        if near:
            score += 2
        for n in near:
            if int(n.get('param_count') or 0) >= 5 and bool(n.get('has_return')):
                score += 3
        cue_records.append({
            'kind': kind,
            'score': score,
            'offset': int(rec.get('offset') or 0),
            'function': rec.get('function') or '<unknown>',
            'text': rec.get('text') or '',
            'nearby_natives': near[:8],
        })
    cue_records.sort(key=lambda r: (-int(r.get('score') or 0), int(r.get('offset') or 0)))
    string_cues = []
    seen = set()
    for item in strings[:1200]:
        low = item.lower()
        if item in seen:
            continue
        if any(term in low for term in CODERED_SCRIPT_SPAWN_TERMS):
            seen.add(item)
            string_cues.append(item)
        if len(string_cues) >= 80:
            break
    decode_state = []
    if payload_info:
        if payload_info.get('decompressed'):
            decode_state.append('decoded/decompressed payload available')
        elif payload_info.get('coded_payload') and payload and payload_info.get('coded_payload') == payload:
            decode_state.append('payload still appears coded; only header/hash/fallback cues are available')
        for note in payload_info.get('notes') or []:
            if 'compressed' in note.lower() or 'decrypt' in note.lower() or 'payload length' in note.lower():
                decode_state.append(note)
    return {
        'raw_sha256': raw_sha256,
        'payload_sha1': payload_sha1,
        'known_signature': known,
        'push_string_count': len(push_records),
        'cue_records': cue_records[:80],
        'string_cues': string_cues,
        'decode_state': decode_state[:12],
        'needs_deeper_decoder': bool(not cue_records and not known and payload_info and not payload_info.get('decompressed') and len(payload or b'') < int((parse_resource_header(data) or {}).get('total_size') or 0)),
    }


def _codered_format_script_spawn_insights(insights: dict) -> list[str]:
    lines: list[str] = []
    lines.append('// Script Lab built-in spawn/vehicle cue scan')
    lines.append(f"//   raw_sha256={insights.get('raw_sha256')}")
    if insights.get('payload_sha1'):
        lines.append(f"//   payload_sha1={insights.get('payload_sha1')}")
    known = insights.get('known_signature')
    if known:
        lines.append(f"//   KNOWN SIGNATURE: {known.get('label')} confidence={known.get('confidence')}")
        lines.append(f"//   Answer: {known.get('plain_answer')}")
        lines.append('//   Spawn chain:')
        for step in known.get('chain') or []:
            lines.append(f'//     - {step}')
        lines.append('//   Key spawn block:')
        for row in known.get('spawn_block') or []:
            lines.append(f'//     {row}')
        if known.get('support_strings'):
            lines.append('//   Streaming/support strings: ' + ', '.join(known.get('support_strings') or []))
        if known.get('drive_support_files'):
            lines.append('//   Drive support files: ' + ', '.join(known.get('drive_support_files') or []))
    cue_records = insights.get('cue_records') or []
    lines.append(f"//   decoded PushString count: {insights.get('push_string_count', 0)}")
    lines.append(f"//   spawn/vehicle cue records: {len(cue_records)}")
    if cue_records:
        for rec in cue_records[:24]:
            lines.append(f"//   [score {int(rec.get('score') or 0):02d}] 0x{int(rec.get('offset') or 0):X} {rec.get('function')} {rec.get('kind')}: {rec.get('text')}")
            for n in (rec.get('nearby_natives') or [])[:4]:
                ret = 'ret=1' if n.get('has_return') else 'ret=0'
                lines.append(f"//       nearby native 0x{int(n.get('offset') or 0):X}: native[{int(n.get('native_index') or 0)}] params={int(n.get('param_count') or 0)} {ret} {n.get('name') or ''}".rstrip())
    elif not known:
        lines.append('//   No decoded spawn block was recovered from this payload yet.')
    if insights.get('string_cues'):
        lines.append('//   String cue sample:')
        for item in insights.get('string_cues')[:40]:
            lines.append(f'//     - {item}')
    if insights.get('decode_state'):
        lines.append('//   Decode state:')
        for item in insights.get('decode_state'):
            lines.append(f'//     - {item}')
    if insights.get('needs_deeper_decoder'):
        lines.append('//   Next decoder lane needed: RDR RSC85 AES + XCompress/LZX expansion. Keep this inside Code RED; do not rely on a separate companion UI.')
    lines.append('//')
    return lines
# --- end Code RED built-in Script Lab convenience pass ---

def analyze_script_payload(path: Path) -> dict:
    data = read_bytes(path)
    resource = parse_resource_header(data)
    payload_info = extract_resource_payload(data, resource) if resource else {'payload': data, 'notes': ['No resource header; raw file bytes used for script analysis.'], 'decrypted': False, 'decompressed': False}
    payload = payload_info.get('payload', data) or data
    strings = extract_candidate_strings(payload, limit=3000)
    ident_re = re.compile(r'^[A-Za-z_][A-Za-z0-9_]{3,}$')
    enum_re = re.compile(r'^[A-Z0-9_]{4,}$')
    identifiers = _codered_unique_preserve([s for s in strings if ident_re.match(s) and not s.startswith('0x')], 280)
    enumish = _codered_unique_preserve([s for s in strings if enum_re.match(s)], 240)
    asset_paths = _codered_unique_preserve([s for s in strings if '/content/' in s.lower() or '$/' in s or '\\content\\' in s.lower()], 140)
    debug_msgs = _codered_unique_preserve([s for s in strings if len(s) >= 24 and (' ' in s or ':' in s)], 140)
    gameplay_terms = _codered_unique_preserve([s for s in strings if any(tag in s.lower() for tag in ('horse','bait','player','quest','tutorial','animal','gringo','item_','whistle','layout','mission','marshal'))], 200)
    native_hits = scan_native_hits(payload, limit=220)
    native_regions = _codered_find_native_table_regions(payload)
    native_hits = _codered_apply_native_confidence(native_hits, native_regions)
    native_descriptor = _codered_find_native_table_descriptor(payload, native_regions)
    descriptor_layout = _codered_analyze_descriptor_layout(payload, native_descriptor)
    strong_native_hits = [hit for hit in native_hits if hit.get('confidence') in {'high', 'medium'}][:120]
    native_names = [hit['name'] for hit in strong_native_hits]
    bytecode = _codered_scan_wsc_bytecode(payload, native_descriptor) if path.suffix.lower() in {'.wsc', '.xsc'} else None
    script_spawn_insights = _codered_collect_script_spawn_insights(path, data, payload, strings, bytecode, payload_info) if path.suffix.lower() in {'.wsc', '.xsc', '.sco'} else None
    native_table_entries_full = bytecode.get('native_table_entries_full', []) if bytecode else []
    native_table_entries = native_table_entries_full[:24]
    companions = _codered_find_script_companions(path)
    descriptor_scr_crosscheck = _codered_find_companion_scr_crosscheck(path, companions, native_descriptor)
    companion_summaries = []
    for comp in companions[:6]:
        comp_data = read_bytes(comp)
        comp_payload = comp_data
        comp_resource = parse_resource_header(comp_data)
        if comp_resource:
            comp_payload = extract_resource_payload(comp_data, comp_resource).get('payload', comp_data) or comp_data
        comp_strings = extract_candidate_strings(comp_payload, limit=800)
        companion_summaries.append(f'{comp.name} ({comp.suffix.lower()}): {len(comp_payload):,} processed bytes, {len(comp_strings)} candidate strings')
    scr_info = _codered_analyze_scr_container(data)
    script_tooling = _codered_detect_script_resource_tooling()
    scr_companion_crosscheck = None
    if scr_info and path.suffix.lower() == '.sco':
        companion_descriptor, companion_descriptor_path = _codered_find_wsc_descriptor_from_companions(path, companions)
        scr_companion_crosscheck = _codered_compare_descriptor_to_scr(scr_info, companion_descriptor)
        if scr_companion_crosscheck and companion_descriptor_path is not None:
            scr_companion_crosscheck['companion'] = companion_descriptor_path
    sha = _codered_hashlib.sha1(payload).hexdigest()
    report_lines = [
        f'// Code RED heuristic pseudo-decompile report for {path.name}',
        '// ------------------------------------------------------------',
        f'// File size: {path.stat().st_size:,} bytes',
        f'// Processed payload size: {len(payload):,} bytes',
    ]
    coded_payload = payload_info.get('coded_payload')
    if resource or coded_payload:
        report_lines.append(f'// Coded payload size: {len(coded_payload or b""):,} bytes')
    report_lines.extend([
        f'// Payload SHA1: {sha}',
        '//',
    ])
    if resource:
        report_lines.extend([
            f'// Resource header: {resource["ident_name"]} [{resource["raw_ident_name"]}] ({resource["endian"]})',
            f'// Resource type: {resource["resource_type"]}',
            f'// flag1: 0x{resource["flag1"]:08X}',
        ])
        if resource['ident_name'] in {'RSC85', 'RSC86'}:
            report_lines.append(f'// flag2: 0x{resource["flag2"]:08X}')
    if scr_info:
        report_lines.extend([
            f'// SCR container magic: {scr_info["magic"]}',
            f'// SCR header words: 0x04=0x{scr_info["u32_le_04"]:08X}  0x08=0x{scr_info["u32_le_08"]:08X}  0x0C=0x{scr_info["u32_le_0C"]:08X}',
            f'// SCR header words: 0x10=0x{scr_info["u32_le_10"]:08X}  0x14=0x{scr_info["u32_le_14"]:08X}  0x18=0x{scr_info["u32_le_18"]:08X}  0x1C=0x{scr_info["u32_le_1C"]:08X}',
        ])
    if CODERED_NATIVE_DB_COUNT:
        report_lines.append(f'// Native DB entries loaded: {CODERED_NATIVE_DB_COUNT:,}')
        if CODERED_NATIVE_DB_SOURCES:
            report_lines.append(f'// Native DB source: {CODERED_NATIVE_DB_SOURCES[0]}')
    report_lines.append('// Payload processing notes:')
    report_lines.extend([f'// - {note}' for note in payload_info.get('notes', [])])
    report_lines.append('// Build-back / donor tooling notes:')
    report_lines.extend([f'// - {note}' for note in script_tooling.get('notes', [])])
    zstd_frame = payload_info.get('zstd_frame')
    if zstd_frame:
        report_lines.append(
            f"// - Zstd frame summary: descriptor=0x{zstd_frame['frame_descriptor']:02X}  window={zstd_frame.get('window_size')}  checksum={zstd_frame.get('checksum_flag')}  single_segment={zstd_frame.get('single_segment')}"
        )
    report_lines.extend([
        '//',
        f'// Candidate strings scanned: {len(strings)}',
        f'// Likely identifiers: {len(identifiers)}',
        f'// Likely enum/constants: {len(enumish)}',
        f'// Asset/content paths: {len(asset_paths)}',
        f'// Debug/status strings: {len(debug_msgs)}',
        f'// Candidate native hits (raw): {len(native_hits)}',
        f'// Candidate native hits (medium/high confidence): {len(strong_native_hits)}',
        f'// Probable native table regions: {len(native_regions)}',
        f'// Native table descriptor recovered: {bool(native_descriptor)}',
        f'// Descriptor layout recovered: {bool(descriptor_layout)}',
        f'// Descriptor/SCR cross-check: {bool(descriptor_scr_crosscheck or scr_companion_crosscheck)}',
        f'// Companion script files: {len(companions)}',
        f'// Bytecode skeleton recovered: {bool(bytecode)}',
        f"// Function count: {bytecode.get('function_count', 0) if bytecode else 0}",
        f"// Native callsites recovered: {bytecode.get('native_call_count', 0) if bytecode else 0}",
        f"// Local callsites resolved: {bytecode.get('resolved_local_call_count', 0) if bytecode else 0}/{bytecode.get('local_call_count', 0) if bytecode else 0}",
        f"// Spawn/vehicle cue records: {len(script_spawn_insights.get('cue_records') or []) if script_spawn_insights else 0}",
        f"// Known script signature: {bool(script_spawn_insights.get('known_signature')) if script_spawn_insights else False}",
        '//',
        '/*',
        '  Heuristic observations:',
        '  - This is not a trusted source-level decompile.',
        '  - It is a symbol/string/native-oriented reconstruction aid built from the decrypted/decompressed script payload.',
        '  - Native hits are scored for 4-byte alignment and probable native-table region clustering.',
        '  - Use the round-trip clone path for rebuild validation, not this text as compile-back input.',
        '*/',
        '',
    ])
    def add_section(title: str, items: list[str], limit: int = 80):
        report_lines.append(f'// {title}')
        if not items:
            report_lines.append('//   <none>')
        else:
            for item in items[:limit]:
                report_lines.append(f'//   {item}')
        report_lines.append('//')
    add_section('Probable native table regions', [f"0x{r['start']:X}-0x{r['end']:X}  count={r['count']}  unique={r['unique_count']}  density={r['density']:.2f}" for r in native_regions], 24)
    if native_descriptor:
        descriptor_lines = [
            f"region=0x{native_descriptor['region_start']:X}-0x{native_descriptor['region_end']:X}  count={native_descriptor['region_count']}  unique={native_descriptor['region_unique_count']}  density={native_descriptor['region_density']:.2f}",
            f"count_field@0x{native_descriptor['count_field_offset']:X}=0x{native_descriptor['region_count']:X}",
            f"native_ptr_field@0x{native_descriptor['pointer_field_offset']:X}=0x{native_descriptor['native_virtual_ptr']:08X}->0x{native_descriptor['native_offset']:X}",
            'descriptor words: ' + ', '.join(_codered_format_descriptor_word(v) for v in native_descriptor['descriptor_words'][:12]),
        ]
        if descriptor_layout:
            descriptor_lines.append(f"descriptor_confidence={descriptor_layout.get('confidence', 'low')}  score={descriptor_layout.get('confidence_score', 0)}")
        page_map = native_descriptor.get('page_map')
        if page_map:
            descriptor_lines.append(
                f"page_map@0x{page_map['field_offset']:X}=0x{page_map['virtual_ptr']:08X}->0x{page_map['offset']:X}  pages={page_map['count']}  first={', '.join(hex(v) for v in page_map['first'][:4])}"
            )
        add_section('Recovered native table descriptor', descriptor_lines, 24)
        if descriptor_layout:
            layout_lines = [
                f"descriptor@0x{descriptor_layout['descriptor_offset']:X}  span=0x{descriptor_layout['descriptor_span_bytes']:X}  descriptor_to_table_gap=0x{descriptor_layout['descriptor_to_table_gap']:X}",
            ]
            gap = descriptor_layout.get('table_to_page_map_gap')
            if gap is not None:
                layout_lines.append(f"table_to_page_map_gap={gap:+#x}")
            page_layout = descriptor_layout.get('page_layout')
            if page_layout:
                layout_lines.append(f"page_layout: count={page_layout['page_count']}  guessed_page_size=0x{page_layout['page_size_guess']:X}  tail_size=0x{page_layout['tail_page_size']:X}  increasing={page_layout['strictly_increasing']}  covers_native_region={page_layout['covers_native_region']}")
                if page_layout.get('coverage_start') is not None and page_layout.get('coverage_end') is not None:
                    layout_lines.append(f"page_coverage: 0x{page_layout['coverage_start']:X}-0x{page_layout['coverage_end']:X}  native_page_index={page_layout.get('region_covering_page_index')}")
                for span in page_layout.get('spans', [])[:6]:
                    layout_lines.append(
                        f"page[{span['index']:02d}]  0x{span['virtual_ptr']:08X}->0x{span['offset']:X}  next=0x{span['next_offset']:X}  size=0x{span['size']:X}"
                    )
            for target in descriptor_layout.get('pointer_targets', [])[:8]:
                layout_lines.append(
                    f"desc_word[{target['word_index']}]  role={target.get('role', 'unknown')}  0x{target['virtual_ptr']:08X}->0x{target['offset']:X}  kind={target['kind']}  virt={target['virtual_count']}  native={target['native_count']}  zero={target['zero_count']}  pad={target['pad_count']}  uniq={target['unique_nonzero']}  mono={target['monotonic_virtual']}  sample={', '.join(hex(v) for v in target['sample_words'][:4])}"
                )
            aux_targets = descriptor_layout.get('aux_pointer_targets') or []
            if aux_targets:
                layout_lines.append('aux_virtual_ptrs: ' + '; '.join(
                    f"desc_word[{t['word_index']}] kind={t['kind']}@0x{t['offset']:X}" for t in aux_targets[:4]
                ))
            add_section('Recovered descriptor-adjacent layout', layout_lines, 40)
        if descriptor_scr_crosscheck:
            add_section('Descriptor <-> companion SCR header cross-check', [
                f"{descriptor_scr_crosscheck.get('companion', Path('<unknown>')).name}: desc_word[{m['descriptor_word_index']}] = 0x{m['descriptor_value']:08X}  matches SCR[0x{m['scr_header_offset']:02X}] byteswapped"
                for m in descriptor_scr_crosscheck.get('matches', [])
            ], 24)
        add_section('Recovered native table head entries', [f"[{e['index']:03d}]  0x{e['offset']:X}  0x{e['hash']:08X}  {e['name']}  // {e['category']}" for e in native_table_entries], 48)
    if scr_companion_crosscheck:
        add_section('SCR header <-> companion descriptor cross-check', [
            f"{scr_companion_crosscheck.get('companion', Path('<unknown>')).name}: SCR[0x{m['scr_header_offset']:02X}] byteswapped = 0x{m['descriptor_value']:08X}  matches desc_word[{m['descriptor_word_index']}]"
            for m in scr_companion_crosscheck.get('matches', [])
        ], 24)
    if script_spawn_insights:
        report_lines.extend(_codered_format_script_spawn_insights(script_spawn_insights))
    if bytecode:
        add_section('Recovered bytecode skeleton', [
            f"code_scan_stop=0x{bytecode.get('code_stop', 0):X}  functions={bytecode.get('function_count', 0)}  opcode_total={bytecode.get('opcode_total', 0)}  confidence={bytecode.get('confidence', 'low')} ({bytecode.get('confidence_score', 0)})",
            f"native_calls={bytecode.get('native_call_count', 0)}  local_calls={bytecode.get('local_call_count', 0)}  resolved_local_calls={bytecode.get('resolved_local_call_count', 0)}  ratio={bytecode.get('resolved_local_call_ratio', 0.0):.2f}",
            f"parse_errors={bytecode.get('parse_error_count', 0)}",
        ], 12)
        add_section('Recovered function table', [
            f"[{f['ordinal']:03d}] {f['name']}  enter=0x{f['enter_offset']:X}  body=0x{f['body_offset']:X}  end=0x{f['end_offset']:X}  params={f['param_count']}  vars={f['var_count']}  span=0x{f['span_bytes']:X}"
            for f in bytecode.get('functions', [])
        ], 80)
        add_section('Recovered native callsites', [
            f"0x{c['offset']:X}  {c['function']}  native[{c['native_index']:03d}] params={c['param_count']} ret={int(c['has_return'])} -> {((c.get('entry') or {}).get('name') or '<unknown>')}"
            for c in bytecode.get('native_calls', [])
        ], 120)
        add_section('Recovered local callsites', [
            f"0x{c['offset']:X}  {c['function']}  { _codered_magic_opcode_name(c['opcode']) } -> 0x{c['target_loc']:X}  {c.get('target') or '<unresolved>'}"
            for c in bytecode.get('local_calls', [])
        ], 120)
        add_section('Opcode histogram (top)', [
            f"{item['opcode']}: {item['count']}" for item in bytecode.get('opcode_histogram', [])
        ], 48)
        if bytecode.get('parse_errors'):
            add_section('Bytecode parse warnings', list(bytecode.get('parse_errors') or []), 24)
    add_section('Likely native hits (medium/high confidence)', [format_native_hit(hit) for hit in strong_native_hits], 100)
    add_section('All native hits (top ranked)', [format_native_hit(hit) for hit in native_hits], 120)
    add_section('Companion script files', companion_summaries, 24)
    add_section('Likely identifiers', identifiers, 140)
    add_section('Likely enum/constants', enumish, 140)
    add_section('Asset/content paths', asset_paths, 100)
    add_section('Gameplay-relevant terms', gameplay_terms, 140)
    add_section('Debug/status strings', debug_msgs, 100)
    report_lines.append('/* First candidate strings in scan order */')
    for item in strings[:240]:
        report_lines.append(f'// {item}')
    return {
        'path': path,
        'data': data,
        'resource': resource,
        'payload_info': payload_info,
        'payload': payload,
        'strings': strings,
        'identifiers': identifiers,
        'enumish': enumish,
        'asset_paths': asset_paths,
        'debug_msgs': debug_msgs,
        'gameplay_terms': gameplay_terms,
        'native_hits': native_hits,
        'strong_native_hits': strong_native_hits,
        'native_names': native_names,
        'native_regions': native_regions,
        'native_descriptor': native_descriptor,
        'descriptor_layout': descriptor_layout,
        'descriptor_scr_crosscheck': descriptor_scr_crosscheck,
        'scr_companion_crosscheck': scr_companion_crosscheck,
        'native_table_entries': native_table_entries,
        'native_table_entries_full': native_table_entries_full,
        'bytecode': bytecode,
        'script_spawn_insights': script_spawn_insights,
        'companions': companions,
        'companion_summaries': companion_summaries,
        'scr_info': scr_info,
        'script_tooling': script_tooling,
        'context_tags': infer_script_context_tags(path, strings, asset_paths, gameplay_terms, identifiers),
        'report': '\n'.join(report_lines),
    }


def infer_script_context_tags(path: Path, strings: List[str], asset_paths: List[str], gameplay_terms: List[str], identifiers: List[str]) -> dict:
    path_lower = path.as_posix().lower()
    corpus = '\n'.join([path_lower] + [s.lower() for s in strings[:400]] + [s.lower() for s in asset_paths[:200]] + [s.lower() for s in gameplay_terms[:200]] + [s.lower() for s in identifiers[:200]])
    dlc_candidates = ['zombiepack', 'bonuspack', 'ultimate', 'titlestorage', 'mooutfitspack', 'dlc']
    region_candidates = [
        'armadillo', 'blackwater', 'cholla_springs', 'coots_chapel', 'ridgewood_farm', 'thieves_landing',
        'gaptooth', 'tumbleweed', 'hennigans', 'great_plains', 'tall_trees', 'manzanita', 'beechershope',
        'chuparosa', 'escalera', 'tesoro_azul', 'nosalida', 'el_presidio', 'diez_coronas', 'agave_viejo',
        'perdido', 'rio_bravo', 'punta_orgullo', 'torquemada', 'las_hermanas', 'solomons_folly', 'pikes_basin',
        'fort_mercer', 'twin_rocks', 'tes', 'sol', 'esc', 'rio', 'blk', 'arm', 'chu', 'tum', 'thi', 'mtp', 'upr'
    ]
    mode_candidates = ['freemode', 'freeroam', 'multiplayer', 'posse', 'lobby', 'public', 'private', 'lan', 'coop', 'deathmatch', 'ctf']
    system_candidates = ['population', 'gringo', 'transport', 'law', 'weather', 'graveyards', 'zombie', 'survivor', 'horse', 'train', 'hud']
    def hits(cands):
        return sorted({c for c in cands if c in corpus})
    set_refs = sorted({s for s in strings if ('_set' in s or s.endswith('_layout') or s.endswith('layout'))})[:80]
    return {
        'dlc_tags': hits(dlc_candidates),
        'region_tags': hits(region_candidates),
        'mode_tags': hits(mode_candidates),
        'system_tags': hits(system_candidates),
        'population_or_layout_refs': set_refs,
    }


class ScriptLabDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, analysis: dict, archive_plan_callback: Optional[Callable[[Path, str], None]] = None):
        super().__init__(master)
        self.analysis = analysis
        self.archive_plan_callback = archive_plan_callback
        self.original_report = analysis['report']
        self.title(f"Code RED - Script Lab - {analysis['path'].name}")
        self.geometry('1240x820')
        self.minsize(980, 620)
        c = getattr(master, 'theme', {'bg': '#000000', 'panel': '#050505', 'fg': '#FFFFFF', 'button': '#151515', 'accent': '#8B0000'})
        self.configure(bg=c['bg'])
        header = tk.Frame(self, bg=c['bg'])
        header.pack(fill='x', padx=12, pady=(12,8))
        tk.Label(header, text=f"Script Lab - {analysis['path'].name}", font=('SegoeUI', 15, 'bold'), anchor='w', bg=c['accent'], fg=c['fg']).pack(fill='x')
        spawn_info = analysis.get('script_spawn_insights') or {}
        spawn_known = bool(spawn_info.get('known_signature'))
        spawn_count = len(spawn_info.get('cue_records') or [])
        subtitle = 'Pseudo-decompile working session with built-in spawn/vehicle cue scan. You can edit, save, undo, and export the working text here. Direct compile-back from edited decompile text is not yet promised.'
        if spawn_known or spawn_count:
            subtitle += f' Spawn cues: {spawn_count}; known signature: {spawn_known}.'
        tk.Label(header, text=subtitle, anchor='w', justify='left', bg=c['bg'], fg=c['fg']).pack(fill='x', pady=(6,0))
        tooling = analysis.get('script_tooling') or {}
        self.compile_var = tk.StringVar(value=self._compile_status_text(tooling))
        tk.Label(header, textvariable=self.compile_var, anchor='w', justify='left', bg=c['bg'], fg='#D8D8D8').pack(fill='x', pady=(4,0))
        btns = tk.Frame(self, bg=c['bg'])
        btns.pack(fill='x', padx=12, pady=(0,8))
        button_defs = [
            ('Save Working Text', self.save_working_text, c['accent']),
            ('Undo', self._undo, c['button']),
            ('Redo', self._redo, c['button']),
            ('Reload Original', self.reload_original, c['button']),
            ('Export Payload', self.export_payload, c['accent']),
            ('Export Spawn Notes', self.export_spawn_notes, c['accent']),
            ('Export Session Pack', self.export_session_pack, c['accent']),
            ('Export Toolchain Pack', self.export_toolchain_pack, c['accent']),
            ('Round-trip Clone', self.roundtrip_clone, c['accent']),
            ('Compile Status', self.show_compile_status, c['button']),
            ('Close', self.destroy, c['button']),
        ]
        for text_label, cmd, color in button_defs:
            tk.Button(btns, text=text_label, command=cmd, bg=color, fg=c['fg'], relief='flat', padx=12, pady=8).pack(side='left', padx=(0,8))
        self.textbox = tk.Text(self, wrap='none', undo=True, maxundo=-1, bg=c['panel'], fg=c['fg'], insertbackground=c['fg'], relief='flat')
        self.textbox.insert('1.0', self.original_report)
        self.textbox.pack(fill='both', expand=True, padx=12, pady=(0,12))
        self.bind('<Control-s>', lambda _e: self.save_working_text())
        self.bind('<Control-z>', lambda _e: self._undo())
        self.bind('<Control-y>', lambda _e: self._redo())
        self.bind('<F5>', lambda _e: self.show_compile_status())

    def _current_text(self) -> str:
        return self.textbox.get('1.0', 'end-1c')

    def _undo(self) -> None:
        try:
            self.textbox.edit_undo()
        except Exception:
            pass

    def _redo(self) -> None:
        try:
            self.textbox.edit_redo()
        except Exception:
            pass

    def reload_original(self) -> None:
        if self._current_text() == self.original_report:
            return
        self.textbox.delete('1.0', 'end')
        self.textbox.insert('1.0', self.original_report)

    def _compile_status_text(self, tooling: dict) -> str:
        compile_state = tooling.get('compile_state', 'missing')
        if compile_state == 'available':
            if tooling.get('can_compile_source_project_here'):
                return 'Donor compile tooling detected for source projects. Existing binary WSC recompilation is still unproven.'
            return 'SC-CL compiler asset detected, but this Linux fallback cannot execute the Windows build path directly.'
        if compile_state == 'project-present-compiler-missing':
            if tooling.get('magic_rdr_exe') or tooling.get('xcompress_assets'):
                return 'Trainer 2 source project is present and Magic-RDR/xcompress assets are staged, but the SC-CL compiler is still missing. Working-text save and bridge-pack export are ready; compile-back is not.'
            return 'Trainer 2 source project is present, but the SC-CL compiler is missing. Working-text save is ready; compile-back is not.'
        if tooling.get('magic_rdr_exe') or tooling.get('xcompress_assets'):
            return 'Magic-RDR/xcompress assets are staged for study and bridge-pack export, but no working SC-CL compiler is available yet.'
        return 'No donor script compiler detected in resources. Working-text edit/save is available; compile-back is not.'

    def show_compile_status(self) -> None:
        tooling = self.analysis.get('script_tooling') or {}
        lines = [
            self._compile_status_text(tooling),
            '',
            'Proof state:',
            '- Existing .wsc/.xsc/.sco binaries can be inspected, pseudo-decompiled, exported, and round-trip cloned.',
            '- Edited pseudo-decompile text is treated as a working note/source artifact only.',
            '- Source-project compilation is only plausible if a donor compiler/toolchain is actually present.',
            '- Magic-RDR can be staged as a helper viewer/decompiler/xcompress lane, but its exported .c text is still treated as reference only.',
            '- Export Toolchain Pack will gather Magic-RDR, SC-CL, trainer source, and Code RED compile-lab assets into one Windows-side kit.',
        ]
        for note in tooling.get('notes', []):
            lines.append(f'- {note}')
        messagebox.showinfo('Script compile status', '\n'.join(lines), parent=self)

    def save_working_text(self) -> None:
        target = filedialog.asksaveasfilename(parent=self, title='Save Working Script Text', defaultextension='.txt', initialfile=f"{self.analysis['path'].stem}_working_pseudo_decompile.c.txt")
        if not target:
            return
        out = Path(target)
        out.write_text(self._current_text(), encoding='utf-8')
        if self.archive_plan_callback:
            self.archive_plan_callback(out, 'script-working-text-save')
        messagebox.showinfo('Working text saved', f'Working script text written to\n{out}', parent=self)

    def export_report(self) -> None:
        self.save_working_text()

    def export_payload(self) -> None:
        target = filedialog.asksaveasfilename(parent=self, title='Export Processed Script Payload', initialfile=f"{self.analysis['path'].stem}_payload.bin")
        if not target:
            return
        out = Path(target)
        out.write_bytes(self.analysis['payload'])
        if self.archive_plan_callback:
            self.archive_plan_callback(out, 'script-payload-export')
        messagebox.showinfo('Export complete', f'Processed payload written to\n{out}', parent=self)

    def export_spawn_notes(self) -> None:
        insights = self.analysis.get('script_spawn_insights') or {}
        target = filedialog.asksaveasfilename(parent=self, title='Save Spawn / Vehicle Cue Notes', defaultextension='.txt', initialfile=f"{self.analysis['path'].stem}_spawn_vehicle_cues.txt")
        if not target:
            return
        lines = _codered_format_script_spawn_insights(insights) if insights else ['// No script spawn insight object was available for this file.']
        Path(target).write_text('\n'.join(lines) + '\n', encoding='utf-8')
        messagebox.showinfo('Spawn notes exported', f'Spawn/vehicle cue notes written to\n{target}', parent=self)

    def export_session_pack(self) -> None:
        target = filedialog.askdirectory(parent=self, title='Export Script Session Pack Folder')
        if not target:
            return
        root = Path(target) / f"{self.analysis['path'].stem}_script_session"
        root.mkdir(parents=True, exist_ok=True)
        (root / 'report.txt').write_text(self._current_text(), encoding='utf-8')
        (root / 'payload.bin').write_bytes(self.analysis['payload'])
        metadata = {
            'path': self.analysis['path'].as_posix(),
            'size_bytes': len(self.analysis['data']),
            'resource': self.analysis.get('resource') or {},
            'payload_notes': list((self.analysis.get('payload_info') or {}).get('notes') or []),
            'context_tags': self.analysis.get('context_tags') or {},
            'native_hit_count': len(self.analysis.get('native_hits') or []),
            'strong_native_hit_count': len(self.analysis.get('strong_native_hits') or []),
            'asset_path_count': len(self.analysis.get('asset_paths') or []),
            'gameplay_term_count': len(self.analysis.get('gameplay_terms') or []),
        }
        (root / 'metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
        if self.archive_plan_callback:
            self.archive_plan_callback(root, 'script-session-pack-export')
        messagebox.showinfo('Session pack exported', f'Script session pack written to\n{root}', parent=self)

    def export_toolchain_pack(self) -> None:
        target = filedialog.askdirectory(parent=self, title='Export Script Toolchain Pack Folder')
        if not target:
            return
        result = _codered_build_script_toolchain_pack(Path(target), analysis=self.analysis)
        if self.archive_plan_callback:
            self.archive_plan_callback(result['pack_root'], 'script-toolchain-pack-export')
        messagebox.showinfo('Toolchain pack exported', f"Pack root: {result['pack_root']}\nManifest: {result['manifest_path']}\nCopied lanes: {len(result['copied'])}\nMissing lanes: {len(result['missing'])}", parent=self)

    def roundtrip_clone(self) -> None:
        rebuilt, notes = rebuild_resource_stream_from_processed_payload(self.analysis['data'], self.analysis['payload'])
        if rebuilt is None:
            messagebox.showerror('Round-trip clone failed', '\n'.join(notes), parent=self)
            return
        ok, verify_msg = verify_resource_roundtrip(self.analysis['data'], rebuilt)
        target = filedialog.asksaveasfilename(parent=self, title='Write Round-Trip Clone', initialfile=f"{self.analysis['path'].stem}_roundtrip{self.analysis['path'].suffix}")
        if not target:
            return
        out = Path(target)
        out.write_bytes(rebuilt)
        if self.archive_plan_callback:
            self.archive_plan_callback(out, 'script-roundtrip-clone')
        note_text = ('\n'.join(notes) if notes else '')
        message = f'Round-trip clone written to\n{out}\n\n{verify_msg}'
        if note_text:
            message += f'\n{note_text}'
        if ok:
            messagebox.showinfo('Round-trip clone written', message, parent=self)
        else:
            messagebox.showwarning('Clone written with warning', message, parent=self)

def _codered_scripts_inspect(self, path: Path) -> ModuleInspection:
    analysis = analyze_script_payload(path)
    resource = analysis['resource']
    payload_info = analysis['payload_info']
    textlike = False
    warning = "Decompiler-style .c output is readable only. It is not treated as safe round-trip source. Script Lab now allows editable working-text sessions with undo/redo and save, but compile-back from edited decompile text is still unproven."
    details = [
        f"Path: {path}",
        f"Size: {path.stat().st_size:,} bytes",
        f"Text-like after payload processing: {textlike}",
        f"Processed payload size: {len(analysis['payload']):,} bytes",
        f"Candidate strings extracted: {len(analysis['strings'])}",
        f"Likely identifiers: {len(analysis['identifiers'])}",
        f"Likely asset/content paths: {len(analysis['asset_paths'])}",
        f"Likely debug/status strings: {len(analysis['debug_msgs'])}",
        f"Candidate native hits (raw): {len(analysis['native_hits'])}",
        f"Candidate native hits (medium/high confidence): {len(analysis['strong_native_hits'])}",
        f"Probable native-table regions: {len(analysis['native_regions'])}",
        f"Recovered native table descriptor: {bool(analysis.get('native_descriptor'))}",
        f"Companion script files: {len(analysis['companions'])}",
    ]
    append_resource_lines(details, resource)
    if resource:
        details.append('Resource payload processing:')
        details.extend(f"- {note}" for note in payload_info.get('notes', []))
    script_tooling = analysis.get('script_tooling') or {}
    details.append(f"Donor compile state: {script_tooling.get('compile_state', 'missing')}")
    if script_tooling.get('compiler_path'):
        details.append(f"SC-CL compiler candidate: {script_tooling['compiler_path']}")
    elif script_tooling.get('trainer2_root'):
        details.append(f"Trainer 2 donor root: {script_tooling['trainer2_root']}")
    if analysis.get('scr_info'):
        scr = analysis['scr_info']
        details.append(f"SCR container: {scr['magic']}  hdr04=0x{scr['u32_le_04']:08X}  hdr08=0x{scr['u32_le_08']:08X}  hdr0C=0x{scr['u32_le_0C']:08X}")
    if analysis.get('native_regions'):
        details.append('Probable native-table regions:')
        for region in analysis['native_regions'][:4]:
            details.append(f"- 0x{region['start']:X}-0x{region['end']:X}  count={region['count']}  unique={region['unique_count']}  density={region['density']:.2f}")
    if analysis.get('bytecode'):
        bc = analysis['bytecode']
        details.append('Recovered bytecode skeleton:')
        details.append(f"- functions = {bc.get('function_count', 0)}  opcode_total = {bc.get('opcode_total', 0)}  confidence={bc.get('confidence', 'low')} ({bc.get('confidence_score', 0)})")
        details.append(f"- native_calls = {bc.get('native_call_count', 0)}  local_calls = {bc.get('resolved_local_call_count', 0)}/{bc.get('local_call_count', 0)} resolved")
        if bc.get('functions'):
            preview = '; '.join(f"{f['name']}@0x{f['enter_offset']:X}" for f in bc.get('functions', [])[:6])
            details.append(f"- function head = {preview}")
        if bc.get('native_calls'):
            preview = '; '.join(f"0x{c['offset']:X}:{((c.get('entry') or {}).get('name') or '<unknown>')}" for c in bc.get('native_calls', [])[:5])
            details.append(f"- native call head = {preview}")
    if analysis.get('native_descriptor'):
        desc = analysis['native_descriptor']
        details.append('Recovered native-table descriptor:')
        details.append(f"- count field @ 0x{desc['count_field_offset']:X} = 0x{desc['region_count']:X}")
        details.append(f"- native ptr @ 0x{desc['pointer_field_offset']:X} = 0x{desc['native_virtual_ptr']:08X} -> 0x{desc['native_offset']:X}")
        page_map = desc.get('page_map')
        if page_map:
            details.append(f"- page map @ 0x{page_map['field_offset']:X} = 0x{page_map['virtual_ptr']:08X} -> 0x{page_map['offset']:X}  pages={page_map['count']}")
        layout = analysis.get('descriptor_layout')
        if layout:
            details.append(f"- descriptor span = 0x{layout['descriptor_span_bytes']:X}  descriptor_to_table_gap = 0x{layout['descriptor_to_table_gap']:X}  confidence={layout.get('confidence', 'low')} ({layout.get('confidence_score', 0)})")
            page_layout = layout.get('page_layout')
            if page_layout:
                details.append(f"- page layout guess: count={page_layout['page_count']} page_size=0x{page_layout['page_size_guess']:X} tail=0x{page_layout['tail_page_size']:X} increasing={page_layout['strictly_increasing']} covers_native_region={page_layout['covers_native_region']}")
            aux_targets = layout.get('aux_pointer_targets') or []
            if aux_targets:
                details.append('- aux descriptor pointers: ' + '; '.join(f"desc_word[{t['word_index']}]={t['kind']}@0x{t['offset']:X}" for t in aux_targets[:3]))
        if analysis.get('descriptor_scr_crosscheck'):
            cross = analysis['descriptor_scr_crosscheck']
            details.append(f"- companion SCR cross-check: {cross.get('companion', Path('<unknown>')).name}  matches={cross.get('match_count', 0)}")
        if analysis.get('native_table_entries'):
            details.append('Recovered native-table head entries:')
            for entry in analysis['native_table_entries'][:6]:
                details.append(f"- [{entry['index']:03d}] 0x{entry['offset']:X}  0x{entry['hash']:08X}  {entry['name']}")
    if analysis.get('scr_companion_crosscheck'):
        cross = analysis['scr_companion_crosscheck']
        details.append(f"SCR companion descriptor cross-check: {cross.get('companion', Path('<unknown>')).name}  matches={cross.get('match_count', 0)}")
    if analysis.get('companion_summaries'):
        details.append('Companion script files:')
        for line in analysis['companion_summaries'][:4]:
            details.append(f"- {line}")
    preview_text = decode_best_effort(analysis['payload']) if textlike else analysis['report']
    return ModuleInspection(
        self.name,
        f"Scripts - {path.name}",
        "Script inspection routed successfully." if not resource else "Compiled script inspection with pseudo-decompile and round-trip lab support routed successfully.",
        "\n".join(details),
        warning,
        preview_text,
        can_edit_preview_text=False,
    )


def _codered_scripts_validate(self, path: Path) -> OperationResult:
    analysis = analyze_script_payload(path)
    resource = analysis['resource']
    if resource:
        rebuilt, notes = rebuild_resource_stream_from_processed_payload(analysis['data'], analysis['payload'])
        if rebuilt is not None:
            ok, verify_msg = verify_resource_roundtrip(analysis['data'], rebuilt)
            title = "Script validation passed" if ok else "Script validation partial"
            return OperationResult(ok, title, f"Round-trip rebuild self-test {'passed' if ok else 'completed with mismatch'}. {verify_msg} Resource header={resource['ident_name']} type={resource['resource_type']}." + (f" Notes: {'; '.join(notes)}" if notes else ''))
    msg = f"Compiled or binary script path detected. Extracted {len(analysis['strings'])} candidate strings, {len(analysis['native_hits'])} raw native hits, and {len(analysis['strong_native_hits'])} medium/high-confidence native hits after payload processing."
    if resource:
        msg += f" Resource header={resource['ident_name']} type={resource['resource_type']}."
    return OperationResult(True, "Script validation partial", msg)


ScriptsModule.inspect = _codered_scripts_inspect
ScriptsModule.validate = _codered_scripts_validate
if 'Scripts' in MODULE_BY_NAME:
    MODULE_BY_NAME['Scripts'].summary = "Compiled script lane with pseudo-decompile export, editable working-text sessions with undo/redo/save, donor compiler detection, round-trip clone verification, and dry-run archive-copy probe validation for exact-size candidates."
    MODULE_BY_NAME['Scripts'].capabilities = [
        FormatCapability('.wsc', 'Scripts', 'V/E/P', 'Binary compiled script resource. Script Lab supports pseudo-decompile export, editable working-text sessions with undo/redo/save, donor compiler detection, round-trip clone verification, and archive-copy probe validation for exact-size candidates.'),
    ]


_CODERED_ORIG_INSPECT_EXTRACTED = WorkbenchApp.inspect_extracted_entry
_CODERED_ORIG_MODULE_ACTION = WorkbenchApp.module_action


def _codered_inspect_extracted_entry(self, temp_path: Path, archive_entry: dict, archive_path: Path) -> None:
    mod = self.resolve_module(temp_path)
    if mod and mod.name == 'Scripts' and temp_path.suffix.lower() in {'.wsc', '.xsc', '.sco'}:
        def write_archive_plan(saved_path: Path, action_label: str) -> None:
            plan_path = temp_path.with_name(temp_path.name + '.archive_reintegrate_plan.txt')
            assessment = _codered_build_script_reintegration_assessment(temp_path, saved_path, action_label, archive_entry=archive_entry, archive_path=archive_path)
            plan_lines = [
                'Archive Reintegrate Plan',
                '======================',
                '',
                f'Archive source: {archive_path}',
                f'Internal path: {archive_entry.get("path", "")}',
                f'Archive storage: {'resource' if archive_entry.get('is_resource') else ('compressed' if archive_entry.get('is_compressed') else 'plain')}',
                f'Archive offset: 0x{int(archive_entry.get("offset") or 0):X}',
                f'Archive size_in_archive: {int(archive_entry.get("size_in_archive") or 0):,}',
                f'Archive total_size: {int(archive_entry.get("total_size") or 0):,}',
                f'Temp extract: {temp_path}',
                f'Edited or exported output: {saved_path}',
                f'Action: {action_label}',
                '',
                'Gate result:',
                f"- status: {assessment.get('status', 'hold')}",
                f"- reason: {assessment.get('reason', '')}",
            ]
            if 'original_sha1' in assessment:
                plan_lines.append(f"- original_sha1: {assessment['original_sha1']}")
            if 'saved_sha1' in assessment:
                plan_lines.append(f"- saved_sha1: {assessment['saved_sha1']}")
            if 'original_size' in assessment:
                plan_lines.append(f"- original_size: {assessment['original_size']}")
            if 'saved_size' in assessment:
                plan_lines.append(f"- saved_size: {assessment['saved_size']}")
            if 'size_delta' in assessment:
                plan_lines.append(f"- size_delta: {assessment['size_delta']}")
            if 'same_suffix' in assessment:
                plan_lines.append(f"- same_suffix: {assessment['same_suffix']}")
            if 'resource_header_match' in assessment:
                plan_lines.append(f"- resource_header_match: {assessment['resource_header_match']}")
            if 'processed_payload_match' in assessment:
                plan_lines.append(f"- processed_payload_match: {assessment['processed_payload_match']}")
            if 'byte_identical' in assessment:
                plan_lines.append(f"- byte_identical: {assessment['byte_identical']}")
            frame_compare = assessment.get('zstd_frame_compare')
            if frame_compare:
                plan_lines.append(f"- zstd_frame_descriptor_match: {frame_compare.get('frame_descriptor_match')}")
                plan_lines.append(f"- zstd_window_size_match: {frame_compare.get('window_size_match')}")
                plan_lines.append(f"- zstd_checksum_flag_match: {frame_compare.get('checksum_flag_match')}")
                orig_frame = frame_compare.get('original') or {}
                saved_frame = frame_compare.get('rebuilt') or {}
                plan_lines.append(f"- zstd_original_frame: desc=0x{int(orig_frame.get('frame_descriptor') or 0):02X} window={orig_frame.get('window_size')} checksum={orig_frame.get('checksum_flag')}")
                plan_lines.append(f"- zstd_saved_frame: desc=0x{int(saved_frame.get('frame_descriptor') or 0):02X} window={saved_frame.get('window_size')} checksum={saved_frame.get('checksum_flag')}")
            if 'archive_size_match_meaningful' in assessment:
                plan_lines.append(f"- archive_size_match_meaningful: {assessment['archive_size_match_meaningful']}")
            if 'archive_slot_current_sha1' in assessment:
                plan_lines.append(f"- archive_slot_current_sha1: {assessment['archive_slot_current_sha1']}")
            if 'archive_slot_matches_original_extract' in assessment:
                plan_lines.append(f"- archive_slot_matches_original_extract: {assessment['archive_slot_matches_original_extract']}")
            if 'archive_slot_exact_size_match' in assessment:
                plan_lines.append(f"- archive_slot_exact_size_match: {assessment['archive_slot_exact_size_match']}")
            if 'archive_slot_within_span' in assessment:
                plan_lines.append(f"- archive_slot_within_span: {assessment['archive_slot_within_span']}")
            if assessment.get('archive_slot_headroom') is not None:
                plan_lines.append(f"- archive_slot_headroom: {assessment['archive_slot_headroom']}")
            if assessment.get('archive_slot_size_delta') is not None:
                plan_lines.append(f"- archive_slot_size_delta: {assessment['archive_slot_size_delta']}")
            if assessment.get('verify_message'):
                plan_lines.append(f"- verify: {assessment['verify_message']}")
            probe_result = None
            probe_report_path = None
            if action_label == 'script-roundtrip-clone':
                probe_result = _codered_apply_script_candidate_to_archive_copy(temp_path, saved_path, archive_entry, archive_path)
                probe_report_path = temp_path.with_name(temp_path.name + '.archive_copy_probe.txt')
                probe_lines = [
                    'Archive Copy Probe',
                    '==================',
                    '',
                    f'Archive source: {archive_path}',
                    f'Internal path: {archive_entry.get("path", "")}',
                    f'Source extract: {temp_path}',
                    f'Candidate file: {saved_path}',
                    '',
                    f"- status: {probe_result.get('status', 'probe_blocked')}",
                    f"- reason: {probe_result.get('reason', '')}",
                ]
                for key in ('assessment_status', 'assessment_reason', 'current_slot_sha1', 'current_slot_matches_original_extract', 'probe_archive_path', 'probe_slot_sha1', 'probe_slot_matches_saved_bytes', 'probe_processed_payload_match', 'probe_verify_message'):
                    if key in probe_result:
                        probe_lines.append(f"- {key}: {probe_result[key]}")
                probe_report_path.write_text('\n'.join(probe_lines), encoding='utf-8')
                self.log(f"Wrote archive copy probe report: {probe_report_path.name}")
                plan_lines.append(f"- archive_copy_probe_status: {probe_result.get('status', 'probe_blocked')}")
                plan_lines.append(f"- archive_copy_probe_reason: {probe_result.get('reason', '')}")
                if probe_result.get('probe_archive_path'):
                    plan_lines.append(f"- archive_copy_probe_archive: {probe_result['probe_archive_path']}")
                if probe_report_path:
                    plan_lines.append(f"- archive_copy_probe_report: {probe_report_path}")
            plan_lines.extend([
                '',
                'Status notes:',
                '- The original archive is still not modified directly by this fallback path.',
                '- For round-trip clone candidates, Code RED now supports an archive-copy probe that patches a copied archive at the current slot and re-verifies the result.',
                '- exact_roundtrip_clone_candidate means the saved file is byte-identical to the extracted archive entry and also fits the current archive span in dry-run.',
                '- dry_run_slot_fit_candidate means the rebuilt file cleared payload verification and byte-size fit checks against the current archive entry span only.',
                '- payload_verified_clone_only means the processed payload re-check passed, but direct archive reinsertion is still not proven safe.',
                '- not_reimport_candidate or do_not_reimport means hold the file for analysis only.',
                '- Keep the last known good archive untouched until a dedicated archive mutation path is validated.',
            ])
            plan_path.write_text('\n'.join(plan_lines), encoding='utf-8')
            self.log(f"Wrote archive reintegration plan: {plan_path.name}")
        insp = mod.inspect(temp_path)
        storage_kind = 'resource' if archive_entry.get('is_resource') else ('compressed' if archive_entry.get('is_compressed') else 'plain')
        details = [
            f"Archive source: {archive_path}",
            f"Internal path: {archive_entry.get('path', '')}",
            f"Archive storage: {storage_kind}",
            f"Archive offset: 0x{int(archive_entry.get('offset') or 0):X}",
            f"Archive size_in_archive: {int(archive_entry.get('size_in_archive') or 0):,}",
            f"Archive total_size: {int(archive_entry.get('total_size') or 0):,}",
            f"Temp extract: {temp_path}",
            '',
            insp.details,
        ]
        routed = ModuleInspection(mod.name, insp.title, insp.summary, '\n'.join(details), insp.warning, insp.preview_text, insp.can_edit_preview_text)
        self._write_module_output(mod.name, routed)
        self.notebook.select(self._tab_index_for_name(mod.name))
        self.log(f"Routed archive entry to {mod.name}: {archive_entry.get('path', '')}")
        ScriptLabDialog(self, analyze_script_payload(temp_path), archive_plan_callback=lambda saved_path, action: write_archive_plan(saved_path, action))
        return
    return _CODERED_ORIG_INSPECT_EXTRACTED(self, temp_path, archive_entry, archive_path)


def _codered_module_action(self, module_name: str, action: str) -> None:
    mod = MODULE_BY_NAME[module_name]
    path = self.selected_path
    if action == 'Open Viewer' and path and path.is_file() and mod.can_handle(path) and mod.name == 'Archive' and path.suffix.lower() == '.rpf':
        info = parse_rpf6(path)
        if info is None:
            self._show_result(OperationResult(False, 'Archive open failed', 'RPF6 parse failed for the selected archive.'))
            return
        insp = mod.inspect(path)
        self._write_module_output(mod.name, insp)
        self.notebook.select(self._tab_index_for_name(mod.name))
        ArchiveBrowserDialog(self, path, info)
        return
    if action == 'Import' and path and path.is_file() and mod.can_handle(path) and mod.name == 'Archive' and path.suffix.lower() == '.rpf':
        patch_root = filedialog.askdirectory(title='Select Archive Patch Folder')
        if patch_root:
            try:
                result = _codered_apply_patch_folder_to_archive_copy(path, Path(patch_root))
                self._show_result(OperationResult(True, 'Archive patch folder applied', f"Working copy: {result['working_copy']}\nApplied: {result['applied']}\nRelocated: {result.get('relocated', 0)}\nIdentical: {result.get('identical', 0)}\nBlocked: {result['blocked']}\nUnmatched: {len(result['unmatched'])}\nReport: {result['report_path']}"))
            except Exception as exc:
                self._show_result(OperationResult(False, 'Archive patch folder failed', str(exc)))
        return
    if action == 'Export' and path and path.is_file() and mod.can_handle(path) and mod.name == 'Archive' and path.suffix.lower() == '.rpf':
        target_dir = filedialog.askdirectory(title='Export Full Archive Contents')
        if target_dir:
            try:
                extract_root, txt_path, json_path = export_rpf6_contents_bundle(path, Path(target_dir))
                self._show_result(OperationResult(True, 'Archive export complete', f"Extract root: {extract_root}\nManifest: {txt_path}\nManifest JSON: {json_path}"))
            except Exception as exc:
                self._show_result(OperationResult(False, 'Archive export failed', str(exc)))
        return
    if action == 'Validate' and path and path.is_file() and mod.can_handle(path) and mod.name == 'Archive' and path.suffix.lower() == '.rpf':
        result = mod.validate(path)
        self._show_result(result)
        return
    if action == 'Open Viewer' and path and path.is_file() and mod.can_handle(path) and mod.name == 'Scripts' and path.suffix.lower() in {'.wsc', '.xsc', '.sco'}:
        insp = mod.inspect(path)
        self._write_module_output(mod.name, insp)
        ScriptLabDialog(self, analyze_script_payload(path))
        return
    if action == 'Export' and path and path.is_file() and mod.can_handle(path) and mod.name == 'Scripts' and path.suffix.lower() in {'.wsc', '.xsc', '.sco'}:
        analysis = analyze_script_payload(path)
        report_target = filedialog.asksaveasfilename(title='Export Script Pseudo-Decompile Report', initialfile=f'{path.stem}_pseudo_decompile.c.txt')
        if report_target:
            Path(report_target).write_text(analysis['report'], encoding='utf-8')
            clone_target = Path(report_target).with_name(f'{path.stem}_roundtrip_clone{path.suffix}')
            rebuilt, notes = rebuild_resource_stream_from_processed_payload(analysis['data'], analysis['payload'])
            if rebuilt is not None:
                clone_target.write_bytes(rebuilt)
                ok, verify_msg = verify_resource_roundtrip(analysis['data'], rebuilt)
                message = f'Report written to {report_target}\nRound-trip clone written to {clone_target}\n{verify_msg}'
                if notes:
                    message += f'\nNotes: {"; ".join(notes)}'
                self._show_result(OperationResult(ok, 'Script export complete', message))
            else:
                self._show_result(OperationResult(True, 'Script export complete', f'Report written to {report_target}\nRound-trip clone could not be built in this pass.'))
        return
    return _CODERED_ORIG_MODULE_ACTION(self, module_name, action)


WorkbenchApp.inspect_extracted_entry = _codered_inspect_extracted_entry
WorkbenchApp.module_action = _codered_module_action
# --- end Code RED Script Lab patch ---


# --- Code RED Mesh/Texture Viewer patch (v39) ---
_CODERED_MODEL_VIEW_EXTS = {'.wvd', '.wfd', '.wft', '.wbd', '.wtb', '.xvd', '.xfd', '.xft', '.xbd', '.xtb', '.wsi', '.wtl', '.wsg', '.wsp', '.wnm', '.wcg', '.wgd'}
_CODERED_TEXTURE_FAMILY_EXTS = {'.dds', '.png', '.wtd', '.wtx', '.wsf', '.xtd', '.xtx', '.xsf'}
_CODERED_RPF_PARSE_CACHE: Dict[str, Optional[dict]] = {}


def _codered_cached_parse_rpf6(path: Path) -> Optional[dict]:
    key = str(Path(path).resolve())
    if key in _CODERED_RPF_PARSE_CACHE:
        return _CODERED_RPF_PARSE_CACHE[key]
    try:
        info = parse_rpf6(Path(path))
    except Exception:
        info = None
    _CODERED_RPF_PARSE_CACHE[key] = info
    return info


def _codered_family_base_and_tier(name: str) -> tuple[str, str]:
    stem = Path(name).stem.lower()
    tier_map = [
        ('_vlow', 'vlow'),
        ('_low', 'low'),
        ('_med', 'med'),
        ('_mid', 'mid'),
        ('_high', 'high'),
        ('_vhigh', 'vhigh'),
        ('_lod', 'lod'),
        ('_hi', 'hi'),
    ]
    for suffix, tier in tier_map:
        if stem.endswith(suffix) and len(stem) > len(suffix):
            return stem[:-len(suffix)], tier
    return stem, 'base'


_CODERED_EXPECTED_COMPANION_EXTS = {
    '.wvd': {'.wvd': 180, '.wsi': 220, '.wbd': 110, '.wtb': 90, '.dds': 120, '.wtd': 110, '.png': 70},
    '.wsi': {'.wsi': 180, '.wvd': 220, '.wbd': 110, '.wtb': 90, '.dds': 120, '.wtd': 110, '.png': 70},
    '.wbd': {'.wbd': 180, '.wvd': 120, '.wsi': 120, '.wtb': 70},
    '.wtb': {'.wtb': 180, '.wvd': 110, '.wsi': 90, '.dds': 120, '.wtd': 110},
    '.wfd': {'.wfd': 180, '.wft': 220, '.dds': 120, '.wtd': 110},
    '.wft': {'.wft': 180, '.wfd': 220, '.dds': 120, '.wtd': 110},
    '.dds': {'.dds': 180, '.png': 120, '.wtd': 140, '.wtx': 120, '.wsf': 120},
    '.png': {'.png': 180, '.dds': 140, '.wtd': 120, '.wtx': 100},
}

_CODERED_RELATION_PAIR_RULES = {
    ('.wvd', '.wsi'): ('mesh-index companion', 180),
    ('.wsi', '.wvd'): ('index-mesh companion', 180),
    ('.wvd', '.wbd'): ('mesh-bounds companion', 120),
    ('.wbd', '.wvd'): ('bounds-mesh companion', 120),
    ('.wvd', '.wtb'): ('mesh-texture bundle', 130),
    ('.wtb', '.wvd'): ('texture-bundle mesh', 110),
    ('.wsi', '.wtb'): ('index-texture bundle', 120),
    ('.wtb', '.wsi'): ('texture-bundle index', 100),
    ('.dds', '.wtd'): ('texture-container companion', 140),
    ('.png', '.wtd'): ('texture-container companion', 120),
    ('.dds', '.wtx'): ('texture-container companion', 120),
    ('.png', '.wtx'): ('texture-container companion', 100),
    ('.dds', '.wsf'): ('streaming-texture companion', 110),
    ('.png', '.wsf'): ('streaming-texture companion', 90),
    ('.wtd', '.dds'): ('container-image member', 150),
    ('.wtd', '.png'): ('container-image member', 120),
    ('.wtx', '.dds'): ('container-image member', 140),
    ('.wtx', '.png'): ('container-image member', 110),
    ('.wsf', '.dds'): ('streaming-image member', 120),
    ('.wsf', '.png'): ('streaming-image member', 100),
    ('.wtd', '.wtx'): ('texture-container sibling', 100),
    ('.wtx', '.wtd'): ('texture-container sibling', 100),
}


def _codered_expected_companion_weight(current_ext: str, candidate_ext: str) -> int:
    return _CODERED_EXPECTED_COMPANION_EXTS.get(current_ext, {}).get(candidate_ext, 0)


def _codered_family_relation(current_name: str, candidate_name: str, same_archive: bool = False) -> tuple[str, int, list[str]]:
    current_path = Path(current_name)
    candidate_path = Path(candidate_name)
    current_ext = current_path.suffix.lower()
    candidate_ext = candidate_path.suffix.lower()
    current_base, current_tier = _codered_family_base_and_tier(current_path.name)
    candidate_base, candidate_tier = _codered_family_base_and_tier(candidate_path.name)
    relation = 'candidate'
    bonus = 0
    reasons: list[str] = []
    pair = _CODERED_RELATION_PAIR_RULES.get((current_ext, candidate_ext))
    same_parent = current_path.parent.as_posix().lower() == candidate_path.parent.as_posix().lower()
    if current_base and candidate_base and current_base == candidate_base:
        if current_ext == candidate_ext and current_tier != candidate_tier:
            relation = 'lod variant'
            bonus += 120
            reasons.append('lod-variant')
        elif current_ext == candidate_ext:
            relation = 'same-type sibling'
            bonus += 80
            reasons.append('same-type-sibling')
        elif pair:
            relation = pair[0]
            bonus += pair[1]
            reasons.append('paired-family-companion')
        else:
            relation = 'family companion'
            bonus += 70
            reasons.append('family-companion')
    elif pair:
        relation = pair[0]
        bonus += max(60, pair[1] // 2)
        reasons.append('paired-format-companion')
    if same_parent:
        bonus += 70 if same_archive else 45
        reasons.append('same-parent')
    if current_tier == candidate_tier and current_tier != 'base':
        bonus += 40
        reasons.append('same-tier')
    return relation, bonus, reasons


def _codered_path_family_tokens(name: str) -> set[str]:
    path = Path(name)
    raw_parts = [part.lower() for part in path.parts[:-1]]
    generic = {
        'root', 'content', 'game', 'games', 'release', 'release64', 'common', 'resources',
        'archive', 'archives', 'packs', 'pack', 'data', 'assets', 'world', 'models', 'textures',
        'stream', 'levels', 'zones', 'map', 'maps'
    }
    tokens = set()
    for part in raw_parts:
        if not part or len(part) < 3 or part in generic:
            continue
        if re.fullmatch(r'0x[0-9a-f]+', part):
            continue
        if re.fullmatch(r'[0-9a-f]{6,}', part):
            continue
        tokens.add(part)
    stem = normalize_texture_stem(path.name)
    if stem and stem not in generic:
        tokens.add(stem)
    base, _tier = _codered_family_base_and_tier(path.name)
    if base and base not in generic:
        tokens.add(base)
    return tokens


def _codered_dependency_confidence(score: int, reasons: list[str]) -> str:
    reasons = set(reasons or [])
    if score >= 520 or ('same-parent-token' in reasons and 'expected-ext' in reasons and any(r.startswith('exact-stem:') for r in reasons)):
        return 'confirmed'
    if score >= 320 or ('expected-ext' in reasons and any(r.startswith('normalized-match:') for r in reasons)):
        return 'probable'
    if score >= 160:
        return 'heuristic'
    return 'unsupported'


def _codered_stage_root_candidates(workspace_root: Path) -> list[Path]:
    workspace_root = Path(workspace_root)
    candidates = []
    for name in ('game', 'games'):
        root = workspace_root / name
        if root.exists() and root.is_dir():
            candidates.append(root)
    return candidates


def _codered_workspace_root_for(path: Path) -> Path:
    path = Path(path)
    if path.is_dir() and _codered_stage_root_candidates(path):
        return path
    if path.parent and _codered_stage_root_candidates(path.parent):
        return path.parent
    root = Path(__file__).resolve().parent
    if _codered_stage_root_candidates(root):
        return root
    return path.parent if path.parent.exists() else root


def _codered_collect_staged_rpfs(workspace_root: Path) -> list[Path]:
    items = []
    for stage_root in _codered_stage_root_candidates(workspace_root):
        for p in stage_root.rglob('*.rpf'):
            try:
                mtime = p.stat().st_mtime
            except Exception:
                mtime = 0.0
            items.append((-mtime, str(p).lower(), p))
    deduped = []
    seen = set()
    for _m, _sort_key, p in sorted(items):
        key = str(p.resolve())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(p)
    return deduped


def _codered_collect_archive_family_entries(archive_path: Optional[Path], current_name: str) -> list[dict]:
    if archive_path is None:
        return []
    info = _codered_cached_parse_rpf6(Path(archive_path))
    if not info:
        return []
    current_ext = Path(current_name).suffix.lower()
    family_base, _ = _codered_family_base_and_tier(current_name)
    current_tokens = _codered_path_family_tokens(current_name)
    current_parent = Path(current_name).parent.as_posix().lower()
    rows = []
    for ent in info.get('entries', []):
        if ent.get('type') != 'file':
            continue
        name = ent.get('name', '')
        path_text = ent.get('path', name)
        ext = Path(name).suffix.lower()
        if ext not in _CODERED_MODEL_VIEW_EXTS and ext not in _CODERED_TEXTURE_FAMILY_EXTS:
            continue
        base, tier = _codered_family_base_and_tier(name)
        relation, relation_bonus, relation_reasons = _codered_family_relation(current_name, path_text, same_archive=True)
        score = relation_bonus
        reasons = list(relation_reasons)
        if base == family_base:
            score += 300
            reasons.append('family-base')
        if family_base in base or base in family_base:
            score += 80
            reasons.append('family-overlap')
        if Path(name).stem.lower() == Path(current_name).stem.lower():
            score += 120
            reasons.append('exact-stem')
        ext_weight = _codered_expected_companion_weight(current_ext, ext)
        if ext_weight:
            score += ext_weight
            reasons.append('expected-ext')
        entry_parent = Path(path_text).parent.as_posix().lower()
        if current_parent and entry_parent == current_parent:
            score += 90
            reasons.append('same-parent')
        token_overlap = current_tokens & _codered_path_family_tokens(path_text)
        if token_overlap:
            score += min(120, 40 * len(token_overlap))
            reasons.append('path-token-overlap')
        if score <= 0:
            continue
        rows.append({
            'archive_path': Path(archive_path),
            'entry': ent,
            'name': name,
            'path': path_text,
            'ext': ext,
            'tier': tier,
            'family_base': base,
            'score': score,
            'relation': relation,
            'confidence': _codered_dependency_confidence(score, reasons),
            'reasons': reasons,
            'source_kind': 'current-archive',
            'size': int(ent.get('size_in_archive') or ent.get('total_size') or 0),
        })
    rows.sort(key=lambda r: (-r['score'], r['name'].lower()))
    return rows[:80]


def _codered_collect_cross_archive_dependencies(current_name: str, current_archive_path: Optional[Path], workspace_root: Path, hint_names: Optional[list[str]] = None) -> list[dict]:
    current_ext = Path(current_name).suffix.lower()
    family_base, _ = _codered_family_base_and_tier(current_name)
    tokens = {family_base}
    current_path_tokens = _codered_path_family_tokens(current_name)
    current_parent_tokens = _codered_path_family_tokens(str(Path(current_name).parent))
    for value in (hint_names or []):
        base, _ = _codered_family_base_and_tier(value)
        if base:
            tokens.add(base)
        stem = normalize_texture_stem(value)
        if stem:
            tokens.add(stem)
    rows = []
    current_archive_resolved = str(Path(current_archive_path).resolve()) if current_archive_path else None
    for archive_path in _codered_collect_staged_rpfs(workspace_root):
        try:
            resolved = str(archive_path.resolve())
        except Exception:
            resolved = str(archive_path)
        if current_archive_resolved and resolved == current_archive_resolved:
            continue
        info = _codered_cached_parse_rpf6(archive_path)
        if not info:
            continue
        archive_name_stem = normalize_texture_stem(archive_path.stem)
        for ent in info.get('entries', []):
            if ent.get('type') != 'file':
                continue
            name = ent.get('name', '')
            path_text = ent.get('path', name)
            ext = Path(name).suffix.lower()
            if ext not in _CODERED_MODEL_VIEW_EXTS and ext not in _CODERED_TEXTURE_FAMILY_EXTS:
                continue
            stem = normalize_texture_stem(name)
            raw_stem = Path(name).stem.lower()
            path_tokens = _codered_path_family_tokens(path_text)
            relation, relation_bonus, relation_reasons = _codered_family_relation(current_name, path_text, same_archive=False)
            score = relation_bonus
            reasons = list(relation_reasons)
            for token in sorted(tokens):
                if not token:
                    continue
                if stem == token:
                    score += 240
                    reasons.append('normalized-match:' + token)
                if raw_stem == token:
                    score += 260
                    reasons.append('exact-stem:' + token)
                if token in stem or stem in token:
                    score += 90
                    reasons.append('stem-overlap:' + token)
            ext_weight = _codered_expected_companion_weight(current_ext, ext)
            if ext_weight:
                score += ext_weight
                reasons.append('expected-ext')
            shared_tokens = current_path_tokens & path_tokens
            if shared_tokens:
                score += min(160, 40 * len(shared_tokens))
                reasons.append('path-token-overlap')
            parent_overlap = current_parent_tokens & path_tokens
            if parent_overlap:
                score += min(100, 25 * len(parent_overlap))
                reasons.append('same-parent-token')
            if archive_name_stem and (archive_name_stem in current_path_tokens or archive_name_stem == family_base):
                score += 60
                reasons.append('archive-theme-match')
            if ext in _CODERED_TEXTURE_FAMILY_EXTS:
                score += 20
                reasons.append('texture-family')
            if score <= 0:
                continue
            clean_reasons = sorted(set(reasons))
            rows.append({
                'archive_path': archive_path,
                'entry': ent,
                'name': name,
                'path': path_text,
                'ext': ext,
                'tier': _codered_family_base_and_tier(name)[1],
                'family_base': _codered_family_base_and_tier(name)[0],
                'score': score,
                'relation': relation,
                'confidence': _codered_dependency_confidence(score, clean_reasons),
                'reasons': clean_reasons,
                'source_kind': 'staged-archive',
                'size': int(ent.get('size_in_archive') or ent.get('total_size') or 0),
            })
    rows.sort(key=lambda r: (-r['score'], r['archive_path'].name.lower(), r['name'].lower()))
    return rows[:120]



def _codered_texture_payload_hints(path: Path) -> tuple[list[str], list[str]]:
    path = Path(path)
    try:
        data = read_bytes(path)
    except Exception:
        return [], []
    notes: list[str] = []
    hints: list[str] = []
    suffix = path.suffix.lower()
    if suffix == '.dds':
        hdr = parse_dds_header(data)
        if hdr:
            notes.append(f"DDS {hdr['width']}x{hdr['height']} FourCC={hdr['fourcc']} Mips={hdr['mips']}")
    strings = candidate_strings_from_payload(data, None, limit=80)
    wanted = ('.dds', '.png', '.wtd', '.wtx', '.wsf', '.xtd', '.xtx', '.xsf')
    seen = set()
    for s in strings:
        low = s.lower()
        if low.endswith(wanted) and low not in seen:
            hints.append(s)
            seen.add(low)
        if len(hints) >= 30:
            break
    return notes, hints


class TextureFamilyDialog(tk.Toplevel):
    def __init__(self, master: 'WorkbenchApp', asset_path: Path, archive_path: Optional[Path] = None, archive_entry: Optional[dict] = None, on_saved: Optional[Callable[[Path], None]] = None):
        super().__init__(master)
        self.master_app = master
        self.asset_path = Path(asset_path)
        self.archive_path = Path(archive_path) if archive_path else None
        self.archive_entry = archive_entry or {}
        self.on_saved = on_saved
        self.workspace_root = _codered_workspace_root_for(master.workspace or self.asset_path)
        self.title(f'Code RED - Texture Family - {self.asset_path.name}')
        self.geometry('1320x860')
        self.minsize(980, 620)
        c = getattr(master, 'theme', {'bg': '#000000', 'panel': '#050505', 'fg': '#FFFFFF', 'button': '#151515', 'accent': '#8B0000'})
        self.configure(bg=c['bg'])
        self._variant_rows: Dict[str, dict] = {}
        self._dep_rows: Dict[str, dict] = {}
        self._build_texture_data()

        header = tk.Frame(self, bg=c['bg'])
        header.pack(fill='x', padx=12, pady=(12, 8))
        tk.Label(header, text=self.asset_path.name, font=('SegoeUI', 15, 'bold'), bg=c['bg'], fg=c['fg'], anchor='w').pack(fill='x')
        tk.Label(header, text=f"Family base: {self.family_base}   Quality tier: {self.quality_tier}   Current archive texture rows: {len(self.current_variants)}   Cross-archive texture candidates: {len(self.dependencies)}", bg=c['bg'], fg=c['fg'], anchor='w').pack(fill='x', pady=(4, 0))
        if self.archive_path:
            tk.Label(header, text=f'Archive source: {self.archive_path}', bg=c['bg'], fg=c['fg'], anchor='w').pack(fill='x', pady=(4, 0))

        summary = tk.Text(self, height=12, wrap='word', bg=c['panel'], fg=c['fg'], relief='flat')
        summary.pack(fill='x', padx=12, pady=(0, 8))
        summary.insert('1.0', self._summary_text())
        summary.configure(state='disabled')

        controls = tk.Frame(self, bg=c['bg'])
        controls.pack(fill='x', padx=12, pady=(0, 8))
        tk.Button(controls, text='Open Current Bytes', command=self._open_current_bytes, bg=c['accent'], fg=c['fg'], relief='flat', padx=12, pady=7).pack(side='left')
        tk.Button(controls, text='Open Selected Variant', command=self._open_selected_variant, bg=c['button'], fg=c['fg'], relief='flat', padx=12, pady=7).pack(side='left', padx=(8, 0))
        tk.Button(controls, text='Open Selected Dependency', command=self._open_selected_dependency, bg=c['button'], fg=c['fg'], relief='flat', padx=12, pady=7).pack(side='left', padx=(8, 0))
        tk.Button(controls, text='Open Best Image Candidate', command=self._open_best_image_candidate, bg=c['button'], fg=c['fg'], relief='flat', padx=12, pady=7).pack(side='left', padx=(8, 0))
        tk.Button(controls, text='Close', command=self.destroy, bg=c['button'], fg=c['fg'], relief='flat', padx=12, pady=7).pack(side='right')

        panes = tk.PanedWindow(self, orient='horizontal', sashrelief='flat', sashwidth=8, bg=c['bg'])
        panes.pack(fill='both', expand=True, padx=12, pady=(0, 12))
        left = tk.Frame(panes, bg=c['bg'])
        right = tk.Frame(panes, bg=c['bg'])
        panes.add(left, width=560)
        panes.add(right)

        tk.Label(left, text='Current archive texture-family set', bg=c['bg'], fg=c['fg'], anchor='w').pack(fill='x', pady=(0, 6))
        self.variant_tree = ttk.Treeview(left, columns=('relation', 'confidence', 'tier', 'ext', 'size', 'path'), show='headings')
        for col, title, width in [('relation', 'Relation', 180), ('confidence', 'Confidence', 100), ('tier', 'Tier', 80), ('ext', 'Ext', 70), ('size', 'Size', 90), ('path', 'Path', 260)]:
            self.variant_tree.heading(col, text=title)
            self.variant_tree.column(col, width=width, anchor='w')
        self.variant_tree.pack(fill='both', expand=True)
        self.variant_tree.bind('<Double-1>', lambda _e: self._open_selected_variant())

        tk.Label(right, text='Cross-archive texture candidates', bg=c['bg'], fg=c['fg'], anchor='w').pack(fill='x', pady=(0, 6))
        self.dep_tree = ttk.Treeview(right, columns=('confidence', 'relation', 'score', 'archive', 'ext', 'path'), show='headings')
        for col, title, width in [('confidence', 'Confidence', 100), ('relation', 'Relation', 170), ('score', 'Score', 70), ('archive', 'Archive', 140), ('ext', 'Ext', 70), ('path', 'Path', 240)]:
            self.dep_tree.heading(col, text=title)
            self.dep_tree.column(col, width=width, anchor='w')
        self.dep_tree.pack(fill='both', expand=True)
        self.dep_tree.bind('<Double-1>', lambda _e: self._open_selected_dependency())
        self._populate_trees()

    def _build_texture_data(self) -> None:
        self.family_base, self.quality_tier = _codered_family_base_and_tier(self.asset_path.name)
        self.texture_notes, self.embedded_hints = _codered_texture_payload_hints(self.asset_path)
        current_ref_name = str(self.archive_entry.get('path') or self.archive_entry.get('name') or self.asset_path.name)
        hint_names = [current_ref_name, self.asset_path.name] + self.embedded_hints[:20]
        self.current_variants = [r for r in _codered_collect_archive_family_entries(self.archive_path, current_ref_name) if r['ext'] in _CODERED_TEXTURE_FAMILY_EXTS][:80]
        self.dependencies = [r for r in _codered_collect_cross_archive_dependencies(current_ref_name, self.archive_path, self.workspace_root, hint_names=hint_names) if r['ext'] in _CODERED_TEXTURE_FAMILY_EXTS][:120]

    def _summary_text(self) -> str:
        lines = [
            'Texture Family Viewer',
            '=====================',
            '',
            f'Asset path: {self.asset_path}',
            f'Family base: {self.family_base}',
            f'Quality tier: {self.quality_tier}',
            f'Current archive texture rows: {len(self.current_variants)}',
            f'Cross-archive texture candidates: {len(self.dependencies)}',
            '',
            'Texture notes:',
        ]
        lines.extend((f'- {s}' for s in self.texture_notes) or ['- none'])
        lines.extend(['', 'Embedded texture/container hints:'])
        lines.extend((f'- {s}' for s in self.embedded_hints[:24]) or ['- none'])
        if self.current_variants:
            lines.extend(['', 'Top current archive rows:'])
            for row in self.current_variants[:8]:
                lines.append(f"- {row.get('confidence','heuristic')} / {row.get('relation','candidate')} score={row['score']}: {row['path']} [{', '.join(row.get('reasons') or ['heuristic'])}]")
        if self.dependencies:
            lines.extend(['', 'Top staged cross-archive candidates:'])
            for row in self.dependencies[:8]:
                lines.append(f"- {row.get('confidence','heuristic')} / {row.get('relation','candidate')} score={row['score']}: {row['archive_path'].name} :: {row['path']} [{', '.join(row.get('reasons') or ['heuristic'])}]")
        lines.extend(['', 'This lane is structure-aware at the texture-family/dependency level and byte-editable through the hex editor. Full decoded texture-dictionary editing and rebuild-proven repacking remain future work.'])
        return '\n'.join(lines)

    def _populate_trees(self) -> None:
        for iid in self.variant_tree.get_children():
            self.variant_tree.delete(iid)
        for iid in self.dep_tree.get_children():
            self.dep_tree.delete(iid)
        self._variant_rows.clear()
        self._dep_rows.clear()
        for row in self.current_variants:
            iid = self.variant_tree.insert('', 'end', values=(row.get('relation', 'candidate'), row.get('confidence', 'heuristic'), row['tier'], row['ext'], row['size'], row['path']))
            self._variant_rows[iid] = row
        for row in self.dependencies:
            iid = self.dep_tree.insert('', 'end', values=(row.get('confidence', 'heuristic'), row.get('relation', 'candidate'), row['score'], row['archive_path'].name, row['ext'], row['path']))
            self._dep_rows[iid] = row

    def _open_current_bytes(self) -> None:
        BinaryHexEditorDialog(self, self.asset_path, on_saved=self.on_saved)

    def _open_selected_variant(self) -> None:
        sel = self.variant_tree.selection()
        if not sel:
            messagebox.showinfo('No variant selected', 'Select a current-archive texture-family row first.', parent=self)
            return
        row = self._variant_rows.get(sel[0])
        if row:
            self._open_archive_row(row)

    def _open_selected_dependency(self) -> None:
        sel = self.dep_tree.selection()
        if not sel:
            messagebox.showinfo('No dependency selected', 'Select a dependency candidate first.', parent=self)
            return
        row = self._dep_rows.get(sel[0])
        if row:
            self._open_archive_row(row)

    def _open_best_image_candidate(self) -> None:
        row = next((r for r in self.current_variants if r['ext'] in {'.dds', '.png'}), None)
        if row is None:
            row = next((r for r in self.dependencies if r['ext'] in {'.dds', '.png'}), None)
        if row is None:
            messagebox.showinfo('No image candidate', 'No image payload candidate is available yet.', parent=self)
            return
        self._open_archive_row(row)

    def _open_archive_row(self, row: dict) -> None:
        archive_path = row.get('archive_path')
        entry = row.get('entry')
        if archive_path is None or entry is None:
            return
        try:
            data = extract_rpf_entry(archive_path, entry)
        except Exception as exc:
            messagebox.showerror('Extraction failed', f'Could not extract dependency from archive\n{exc}', parent=self)
            return
        temp_dir = Path(tempfile.mkdtemp(prefix='codered_texture_family_'))
        temp_path = temp_dir / Path(entry.get('name') or row.get('name') or 'asset.bin').name
        temp_path.write_bytes(data)
        self.master_app.inspect_extracted_entry(temp_path, entry, archive_path)


class BinaryHexEditorDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, target_path: Path, title: Optional[str] = None, on_saved: Optional[Callable[[Path], None]] = None):
        super().__init__(master)
        self.target_path = Path(target_path)
        self.on_saved = on_saved
        self.title(title or f'Code RED - Hex Editor - {self.target_path.name}')
        self.geometry('1180x820')
        self.minsize(860, 580)
        c = getattr(master, 'theme', {'bg': '#000000', 'panel': '#050505', 'fg': '#FFFFFF', 'button': '#151515', 'accent': '#8B0000'})
        self.configure(bg=c['bg'])
        data = read_bytes(self.target_path)
        header = tk.Frame(self, bg=c['bg'])
        header.pack(fill='x', padx=12, pady=(12, 8))
        tk.Label(header, text=self.target_path.name, font=('SegoeUI', 15, 'bold'), bg=c['bg'], fg=c['fg'], anchor='w').pack(fill='x')
        tk.Label(header, text=f'Binary editor path: {self.target_path}   Size: {len(data):,} bytes', bg=c['bg'], fg=c['fg'], anchor='w').pack(fill='x', pady=(4, 0))
        if self.target_path.suffix.lower() == '.dds':
            hdr = parse_dds_header(data)
            if hdr:
                tk.Label(header, text=f"DDS {hdr['width']}x{hdr['height']}  FourCC: {hdr['fourcc']}  Mips: {hdr['mips']}", bg=c['bg'], fg=c['fg'], anchor='w').pack(fill='x', pady=(4, 0))
        self.editor = tk.Text(self, wrap='none', bg=c['panel'], fg=c['fg'], insertbackground=c['fg'], relief='flat')
        self.editor.pack(fill='both', expand=True, padx=12, pady=(0, 6))
        self.preview = tk.Text(self, height=8, wrap='none', bg=c['panel'], fg=c['fg'], relief='flat')
        self.preview.pack(fill='x', padx=12, pady=(0, 6))
        self.preview.configure(state='disabled')
        btns = tk.Frame(self, bg=c['bg'])
        btns.pack(fill='x', padx=12, pady=(0, 12))
        tk.Button(btns, text='Reload', command=self._reload, bg=c['button'], fg=c['fg'], relief='flat', padx=14, pady=7).pack(side='left')
        tk.Button(btns, text='Save Bytes', command=self._save, bg=c['accent'], fg=c['fg'], relief='flat', padx=14, pady=7).pack(side='left', padx=(8, 0))
        tk.Button(btns, text='Close', command=self.destroy, bg=c['button'], fg=c['fg'], relief='flat', padx=14, pady=7).pack(side='right')
        self._set_bytes(data)

    def _format_hex(self, data: bytes) -> str:
        hex_bytes = data.hex(' ')
        return '\n'.join(hex_bytes[i:i + (16 * 3 - 1)] for i in range(0, len(hex_bytes), 16 * 3))

    def _set_bytes(self, data: bytes) -> None:
        self.editor.delete('1.0', 'end')
        self.editor.insert('1.0', self._format_hex(data))
        self._set_preview(data)

    def _set_preview(self, data: bytes) -> None:
        preview_lines = []
        for offset in range(0, min(len(data), 512), 16):
            chunk = data[offset:offset + 16]
            hex_part = ' '.join(f'{b:02X}' for b in chunk)
            ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
            preview_lines.append(f'{offset:08X}  {hex_part:<47}  {ascii_part}')
        self.preview.configure(state='normal')
        self.preview.delete('1.0', 'end')
        self.preview.insert('1.0', '\n'.join(preview_lines))
        self.preview.configure(state='disabled')

    def _reload(self) -> None:
        self._set_bytes(read_bytes(self.target_path))

    def _save(self) -> None:
        raw = self.editor.get('1.0', 'end-1c')
        cleaned = re.sub(r'[^0-9A-Fa-f]', '', raw)
        if len(cleaned) % 2 != 0:
            messagebox.showerror('Invalid hex', 'Hex byte count must be even.', parent=self)
            return
        try:
            data = bytes.fromhex(cleaned)
        except ValueError as exc:
            messagebox.showerror('Invalid hex', str(exc), parent=self)
            return
        self.target_path.write_bytes(data)
        self._set_preview(data)
        if self.on_saved is not None:
            self.on_saved(self.target_path)
        messagebox.showinfo('Bytes saved', f'Saved {len(data):,} bytes to\n{self.target_path}', parent=self)


class ModelFamilyDialog(tk.Toplevel):
    def __init__(self, master: 'WorkbenchApp', asset_path: Path, archive_path: Optional[Path] = None, archive_entry: Optional[dict] = None, on_saved: Optional[Callable[[Path], None]] = None):
        super().__init__(master)
        self.master_app = master
        self.asset_path = Path(asset_path)
        self.archive_path = Path(archive_path) if archive_path else None
        self.archive_entry = archive_entry or {}
        self.on_saved = on_saved
        self.workspace_root = _codered_workspace_root_for(master.workspace or self.asset_path)
        self.title(f'Code RED - Model Family - {self.asset_path.name}')
        self.geometry('1320x860')
        self.minsize(980, 620)
        c = getattr(master, 'theme', {'bg': '#000000', 'panel': '#050505', 'fg': '#FFFFFF', 'button': '#151515', 'accent': '#8B0000'})
        self.configure(bg=c['bg'])
        self._variant_rows: Dict[str, dict] = {}
        self._dep_rows: Dict[str, dict] = {}
        self._build_family_data()

        header = tk.Frame(self, bg=c['bg'])
        header.pack(fill='x', padx=12, pady=(12, 8))
        tk.Label(header, text=self.asset_path.name, font=('SegoeUI', 15, 'bold'), bg=c['bg'], fg=c['fg'], anchor='w').pack(fill='x')
        tk.Label(header, text=f"Family base: {self.family_base}   Quality tier: {self.quality_tier}   Current archive variants: {len(self.current_variants)}   Cross-archive candidates: {len(self.dependencies)}", bg=c['bg'], fg=c['fg'], anchor='w').pack(fill='x', pady=(4, 0))
        if self.archive_path:
            tk.Label(header, text=f'Archive source: {self.archive_path}', bg=c['bg'], fg=c['fg'], anchor='w').pack(fill='x', pady=(4, 0))

        summary = tk.Text(self, height=12, wrap='word', bg=c['panel'], fg=c['fg'], relief='flat')
        summary.pack(fill='x', padx=12, pady=(0, 8))
        summary.insert('1.0', self._summary_text())
        summary.configure(state='disabled')

        controls = tk.Frame(self, bg=c['bg'])
        controls.pack(fill='x', padx=12, pady=(0, 8))
        tk.Button(controls, text='Open Current Bytes', command=self._open_current_bytes, bg=c['accent'], fg=c['fg'], relief='flat', padx=12, pady=7).pack(side='left')
        tk.Button(controls, text='Open Selected Variant', command=self._open_selected_variant, bg=c['button'], fg=c['fg'], relief='flat', padx=12, pady=7).pack(side='left', padx=(8, 0))
        tk.Button(controls, text='Open Selected Dependency', command=self._open_selected_dependency, bg=c['button'], fg=c['fg'], relief='flat', padx=12, pady=7).pack(side='left', padx=(8, 0))
        tk.Button(controls, text='Open Best Texture Candidate', command=self._open_best_texture_candidate, bg=c['button'], fg=c['fg'], relief='flat', padx=12, pady=7).pack(side='left', padx=(8, 0))
        tk.Button(controls, text='Close', command=self.destroy, bg=c['button'], fg=c['fg'], relief='flat', padx=12, pady=7).pack(side='right')

        panes = tk.PanedWindow(self, orient='horizontal', sashrelief='flat', sashwidth=8, bg=c['bg'])
        panes.pack(fill='both', expand=True, padx=12, pady=(0, 12))
        left = tk.Frame(panes, bg=c['bg'])
        right = tk.Frame(panes, bg=c['bg'])
        panes.add(left, width=560)
        panes.add(right)

        tk.Label(left, text='Current archive family set', bg=c['bg'], fg=c['fg'], anchor='w').pack(fill='x', pady=(0, 6))
        self.variant_tree = ttk.Treeview(left, columns=('relation', 'tier', 'ext', 'size', 'path'), show='headings')
        for col, title, width in [('relation', 'Relation', 180), ('tier', 'Tier', 80), ('ext', 'Ext', 70), ('size', 'Size', 90), ('path', 'Path', 280)]:
            self.variant_tree.heading(col, text=title)
            self.variant_tree.column(col, width=width, anchor='w')
        self.variant_tree.pack(fill='both', expand=True)
        self.variant_tree.bind('<Double-1>', lambda _e: self._open_selected_variant())

        tk.Label(right, text='Cross-archive dependency candidates', bg=c['bg'], fg=c['fg'], anchor='w').pack(fill='x', pady=(0, 6))
        self.dep_tree = ttk.Treeview(right, columns=('confidence', 'relation', 'score', 'archive', 'ext', 'path'), show='headings')
        for col, title, width in [('confidence', 'Confidence', 100), ('relation', 'Relation', 170), ('score', 'Score', 70), ('archive', 'Archive', 140), ('ext', 'Ext', 70), ('path', 'Path', 240)]:
            self.dep_tree.heading(col, text=title)
            self.dep_tree.column(col, width=width, anchor='w')
        self.dep_tree.pack(fill='both', expand=True)
        self.dep_tree.bind('<Double-1>', lambda _e: self._open_selected_dependency())
        self._populate_trees()

    def _build_family_data(self) -> None:
        self.family_base, self.quality_tier = _codered_family_base_and_tier(self.asset_path.name)
        mod = MODULE_BY_NAME.get('Meshes')
        dds_hints = []
        texture_candidates = []
        shader_hints = []
        relation_lines = []
        extra_hints = []
        if mod is not None and hasattr(mod, '_structured_preview'):
            try:
                dds_hints, texture_candidates, shader_hints, relation_lines, extra_hints = mod._structured_preview(self.asset_path)
            except Exception:
                pass
        current_ref_name = str(self.archive_entry.get('path') or self.archive_entry.get('name') or self.asset_path.name)
        hint_names = [current_ref_name, self.asset_path.name] + dds_hints[:20]
        self.current_variants = _codered_collect_archive_family_entries(self.archive_path, current_ref_name)
        self.dependencies = _codered_collect_cross_archive_dependencies(current_ref_name, self.archive_path, self.workspace_root, hint_names=hint_names)
        self.dds_hints = dds_hints
        self.texture_candidates = texture_candidates
        self.shader_hints = shader_hints
        self.relation_lines = relation_lines
        self.extra_hints = extra_hints

    def _summary_text(self) -> str:
        lines = [
            'Model Family Viewer',
            '===================',
            '',
            f'Asset path: {self.asset_path}',
            f'Family base: {self.family_base}',
            f'Quality tier: {self.quality_tier}',
            f'Current archive family rows: {len(self.current_variants)}',
            f'Cross-archive dependency candidates: {len(self.dependencies)}',
            f'Embedded texture hints: {len(self.dds_hints)}',
            f'Ranked companion texture targets: {len(self.texture_candidates)}',
            '',
            'Embedded texture hints:',
        ]
        lines.extend((f'- {s}' for s in self.dds_hints[:20]) or ['- none'])
        lines.extend(['', 'Shader hints:'])
        lines.extend((f'- {s}' for s in self.shader_hints[:20]) or ['- none'])
        if self.dependencies:
            lines.extend(['', 'Top staged cross-archive candidates:'])
            for row in self.dependencies[:8]:
                lines.append(f"- {row['confidence']} / {row.get('relation','candidate')} score={row['score']}: {row['archive_path'].name} :: {row['path']} [{', '.join(row.get('reasons') or ['heuristic'])}]")
        if self.texture_candidates:
            lines.extend(['', 'Best companion texture candidates:'])
            for row in self.texture_candidates[:10]:
                meta = row.get('meta') or {}
                dims = ''
                if meta.get('width') and meta.get('height'):
                    dims = f" {meta['width']}x{meta['height']}"
                lines.append(f"- score={row['score']}: {row['path'].name}{dims} [{', '.join(row.get('reasons') or ['heuristic'])}]")
        if self.extra_hints:
            lines.extend(['', 'Additional payload notes:'])
            lines.extend(f'- {s}' for s in self.extra_hints[:20])
        lines.extend(['', 'This lane is structure-aware at the family/dependency level and byte-editable through the hex editor. Full decoded 3D rendering and rebuild-proven mesh compilation remain future work.'])
        return '\n'.join(lines)

    def _populate_trees(self) -> None:
        for iid in self.variant_tree.get_children():
            self.variant_tree.delete(iid)
        for iid in self.dep_tree.get_children():
            self.dep_tree.delete(iid)
        self._variant_rows.clear()
        self._dep_rows.clear()
        for row in self.current_variants:
            iid = self.variant_tree.insert('', 'end', values=(row.get('relation', 'candidate'), row['tier'], row['ext'], row['size'], row['path']))
            self._variant_rows[iid] = row
        for row in self.dependencies:
            iid = self.dep_tree.insert('', 'end', values=(row.get('confidence', 'heuristic'), row.get('relation', 'candidate'), row['score'], row['archive_path'].name, row['ext'], row['path']))
            self._dep_rows[iid] = row

    def _open_current_bytes(self) -> None:
        BinaryHexEditorDialog(self, self.asset_path, on_saved=self.on_saved)

    def _open_selected_variant(self) -> None:
        sel = self.variant_tree.selection()
        if not sel:
            messagebox.showinfo('No variant selected', 'Select a current-archive family row first.', parent=self)
            return
        row = self._variant_rows.get(sel[0])
        if not row:
            return
        self._open_archive_row(row)

    def _open_selected_dependency(self) -> None:
        sel = self.dep_tree.selection()
        if not sel:
            messagebox.showinfo('No dependency selected', 'Select a dependency candidate first.', parent=self)
            return
        row = self._dep_rows.get(sel[0])
        if not row:
            return
        self._open_archive_row(row)

    def _open_best_texture_candidate(self) -> None:
        if self.texture_candidates:
            candidate = self.texture_candidates[0]
            if is_viewable_image(candidate['path']):
                ImagePreviewDialog(self, candidate['path'], f'Companion Texture - {candidate["path"].name}')
            else:
                BinaryHexEditorDialog(self, candidate['path'])
            return
        image_dep = next((row for row in self.dependencies if row['ext'] in {'.dds', '.png'}), None)
        if image_dep is None:
            messagebox.showinfo('No texture candidate', 'No ranked texture candidate is available yet.', parent=self)
            return
        self._open_archive_row(image_dep)

    def _open_archive_row(self, row: dict) -> None:
        archive_path = row.get('archive_path')
        entry = row.get('entry')
        if archive_path is None or entry is None:
            return
        try:
            data = extract_rpf_entry(archive_path, entry)
        except Exception as exc:
            messagebox.showerror('Extraction failed', f'Could not extract dependency from archive\n{exc}', parent=self)
            return
        temp_dir = Path(tempfile.mkdtemp(prefix='codered_model_family_'))
        temp_path = temp_dir / Path(entry.get('name') or row.get('name') or 'asset.bin').name
        temp_path.write_bytes(data)
        self.master_app.inspect_extracted_entry(temp_path, entry, archive_path)


_CODERED_V39_ORIG_IMAGE_PREVIEW_INIT = ImagePreviewDialog.__init__


def _codered_v39_image_preview_init(self, master: tk.Misc, image_path: Path, title: Optional[str] = None, on_saved: Optional[Callable[[str, Path], None]] = None):
    _CODERED_V39_ORIG_IMAGE_PREVIEW_INIT(self, master, image_path, title=title, on_saved=on_saved)
    c = getattr(master, 'theme', {'bg': '#000000', 'panel': '#050505', 'fg': '#FFFFFF', 'button': '#151515', 'accent': '#8B0000'})
    footer = tk.Frame(self, bg=c['bg'])
    footer.pack(fill='x', padx=12, pady=(0, 12))
    extra = []
    if Path(image_path).suffix.lower() == '.dds':
        hdr = parse_dds_header(read_bytes(Path(image_path), 256))
        if hdr:
            extra.append(f"DDS {hdr['width']}x{hdr['height']}  FourCC={hdr['fourcc']}  Mips={hdr['mips']}")
    if extra:
        tk.Label(footer, text='   '.join(extra), bg=c['bg'], fg=c['fg'], anchor='w').pack(side='left', fill='x', expand=True)
    if Path(image_path).suffix.lower() in _CODERED_TEXTURE_FAMILY_EXTS:
        tk.Button(footer, text='Open Texture Family', command=lambda: TextureFamilyDialog(self, Path(image_path)), bg=c['button'], fg=c['fg'], relief='flat', padx=12, pady=7).pack(side='right', padx=(8, 0))
    tk.Button(footer, text='Open Hex Editor', command=lambda: BinaryHexEditorDialog(self, Path(image_path)), bg=c['button'], fg=c['fg'], relief='flat', padx=12, pady=7).pack(side='right')


ImagePreviewDialog.__init__ = _codered_v39_image_preview_init

_CODERED_V39_PREV_INSPECT_EXTRACTED = WorkbenchApp.inspect_extracted_entry
_CODERED_V39_PREV_MODULE_ACTION = WorkbenchApp.module_action


def _codered_v39_inspect_extracted_entry(self, temp_path: Path, archive_entry: dict, archive_path: Path) -> None:
    mod = self.resolve_module(temp_path)
    def _saved(_p: Path) -> None:
        plan_path = temp_path.with_name(temp_path.name + '.archive_reintegrate_plan.txt')
        lines = [
            'Archive Reintegrate Plan',
            '======================',
            '',
            f'Archive source: {archive_path}',
            f'Internal path: {archive_entry.get("path", "")}',
            f'Temp extract: {temp_path}',
            f'Edited asset: {_p}',
            '',
            'Status:',
            '- Binary edits were saved to the extracted asset.',
            '- Automatic archive write-back is not implemented yet.',
            '- Use this edited file plus the plan as the basis for future validated reintegration.',
        ]
        plan_path.write_text('\n'.join(lines), encoding='utf-8')
        self.log(f'Wrote archive reintegration plan: {plan_path.name}')
    if mod and mod.name in {'Meshes', 'World'} and temp_path.suffix.lower() in _CODERED_MODEL_VIEW_EXTS:
        insp = mod.inspect(temp_path)
        self._write_module_output(mod.name, insp)
        self.notebook.select(self._tab_index_for_name(mod.name))
        ModelFamilyDialog(self, temp_path, archive_path=archive_path, archive_entry=archive_entry, on_saved=_saved)
        return
    if mod and mod.name == 'Textures' and temp_path.suffix.lower() in _CODERED_TEXTURE_FAMILY_EXTS:
        insp = mod.inspect(temp_path)
        self._write_module_output(mod.name, insp)
        self.notebook.select(self._tab_index_for_name(mod.name))
        if is_viewable_image(temp_path):
            ImagePreviewDialog(self, temp_path, insp.title)
        else:
            TextureFamilyDialog(self, temp_path, archive_path=archive_path, archive_entry=archive_entry, on_saved=_saved)
        return
    return _CODERED_V39_PREV_INSPECT_EXTRACTED(self, temp_path, archive_entry, archive_path)

def _codered_v39_module_action(self, module_name: str, action: str) -> None:
    mod = MODULE_BY_NAME[module_name]
    path = self.selected_path
    if action == 'Open Viewer' and path and path.is_file() and mod.can_handle(path) and mod.name in {'Meshes', 'World'} and path.suffix.lower() in _CODERED_MODEL_VIEW_EXTS:
        insp = mod.inspect(path)
        self._write_module_output(mod.name, insp)
        self.notebook.select(self._tab_index_for_name(mod.name))
        ModelFamilyDialog(self, path, archive_path=None, archive_entry=None)
        return
    if action == 'Open Viewer' and path and path.is_file() and mod.can_handle(path) and mod.name == 'Textures' and path.suffix.lower() in _CODERED_TEXTURE_FAMILY_EXTS:
        insp = mod.inspect(path)
        self._write_module_output(mod.name, insp)
        self.notebook.select(self._tab_index_for_name(mod.name))
        if is_viewable_image(path):
            ImagePreviewDialog(self, path, insp.title)
        else:
            TextureFamilyDialog(self, path, archive_path=None, archive_entry=None)
        return
    if action == 'Open Viewer' and path and path.is_file() and is_viewable_image(path):
        insp = mod.inspect(path)
        self._write_module_output(mod.name, insp)
        self.notebook.select(self._tab_index_for_name(mod.name))
        ImagePreviewDialog(self, path, insp.title)
        return
    return _CODERED_V39_PREV_MODULE_ACTION(self, module_name, action)


WorkbenchApp.inspect_extracted_entry = _codered_v39_inspect_extracted_entry
WorkbenchApp.module_action = _codered_v39_module_action
# --- end Code RED Mesh/Texture Viewer patch (v39) ---



def _codered_model_preview_payload(path: Path) -> tuple[bytes, list[str]]:
    data = read_bytes(path)
    resource = parse_resource_header(data)
    info = extract_resource_payload(data, resource)
    payload = info.get('payload') or data
    notes = list(info.get('notes') or [])
    if resource:
        notes.append(f"Resource {resource['ident_name']} type {resource['resource_type']} payload used for heuristic mesh scanning.")
    else:
        notes.append('Raw file bytes used for heuristic mesh scanning.')
    return payload, notes


def _codered_triplet_is_plausible(x: float, y: float, z: float) -> bool:
    import math
    values = (x, y, z)
    if not all(math.isfinite(v) for v in values):
        return False
    if max(abs(v) for v in values) > 100000.0:
        return False
    nonzero = 0
    significant = 0
    denormalish = 0
    for v in values:
        av = abs(v)
        if av > 1e-7:
            nonzero += 1
        if av > 0.0001:
            significant += 1
        elif 0.0 < av < 1e-20:
            denormalish += 1
    if denormalish >= 2:
        return False
    if nonzero == 0:
        return False
    if significant == 0:
        return False
    return True



def _codered_normalize_preview_points(points: list[tuple[float, float, float]], max_points: int = 12000) -> list[tuple[float, float, float]]:
    if max_points <= 0 or len(points) <= max_points:
        return points
    step = max(1, len(points) // max_points)
    sampled = points[::step]
    if sampled and sampled[-1] != points[-1]:
        sampled.append(points[-1])
    return sampled[:max_points]


def _codered_percentile_filter(points: list[tuple[float, float, float]], mode: str = '1-99') -> list[tuple[float, float, float]]:
    if not points or mode == 'None' or not _HAVE_NUMPY or np is None or len(points) < 64:
        return list(points)
    mode = str(mode or 'None')
    if '-' not in mode:
        return list(points)
    try:
        lo_p, hi_p = mode.split('-', 1)
        lo_v = float(lo_p)
        hi_v = float(hi_p)
    except Exception:
        return list(points)
    arr = np.array(points, dtype='float64')
    lo = np.percentile(arr, lo_v, axis=0)
    hi = np.percentile(arr, hi_v, axis=0)
    mask = np.all((arr >= lo) & (arr <= hi), axis=1)
    filtered = arr[mask]
    if filtered.shape[0] < max(40, len(points) // 10):
        return list(points)
    return [tuple(map(float, row)) for row in filtered.tolist()]


def _codered_heuristic_model_candidates(path: Path, limit: int = 10) -> list[dict]:
    import math
    import struct
    payload, payload_notes = _codered_model_preview_payload(path)
    if len(payload) < 64:
        return []
    candidates: list[dict] = []
    seen: set[tuple[int, int]] = set()
    stride_values = [12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56, 60, 64]
    for stride in stride_values:
        for offset in range(0, min(stride, 64), 4):
            if (stride, offset) in seen:
                continue
            seen.add((stride, offset))
            raw_points: list[tuple[float, float, float]] = []
            suspicious = 0
            for pos in range(offset, len(payload) - 12, stride):
                x, y, z = struct.unpack_from('<fff', payload, pos)
                if _codered_triplet_is_plausible(x, y, z):
                    raw_points.append((float(x), float(y), float(z)))
                else:
                    suspicious += 1
            if len(raw_points) < 90:
                continue
            filtered_points = _codered_percentile_filter(raw_points, '1-99')
            if len(filtered_points) < 80:
                filtered_points = raw_points
            xs = [p[0] for p in filtered_points]
            ys = [p[1] for p in filtered_points]
            zs = [p[2] for p in filtered_points]
            span_x = max(xs) - min(xs)
            span_y = max(ys) - min(ys)
            span_z = max(zs) - min(zs)
            max_span = max(span_x, span_y, span_z)
            min_span = min(span_x, span_y, span_z)
            if max_span <= 0.0:
                continue
            unique = len(set((round(a, 3), round(b, 3), round(c, 3)) for a, b, c in filtered_points))
            unique_ratio = unique / max(1, len(filtered_points))
            nonflat_axes = sum(1 for span in (span_x, span_y, span_z) if span > 0.05)
            if nonflat_axes < 2:
                continue
            suspicious_ratio = suspicious / max(1, suspicious + len(raw_points))
            filtered_ratio = len(filtered_points) / max(1, len(raw_points))
            scale_penalty = 0.0 if max_span < 10000 else min(0.5, math.log10(max_span / 10000.0 + 1.0) / 3.0)
            if min_span <= 0.0001:
                scale_penalty += 0.15
            score = (
                min(1.0, len(filtered_points) / 3000.0) * 2.5
                + unique_ratio * 1.8
                + (nonflat_axes / 3.0) * 0.8
                + filtered_ratio * 0.9
                + (1.0 - suspicious_ratio) * 0.8
                - scale_penalty
            )
            reason_parts = [
                f'raw={len(raw_points):,}',
                f'filtered={len(filtered_points):,}',
                f'unique={unique_ratio:.2f}',
                f'suspicious={suspicious_ratio:.2f}',
                f'span=({span_x:.1f}, {span_y:.1f}, {span_z:.1f})',
            ]
            preview_points = _codered_normalize_preview_points(filtered_points)
            candidates.append({
                'score': round(score, 3),
                'stride': stride,
                'offset': offset,
                'count': len(raw_points),
                'filtered_count': len(filtered_points),
                'unique_ratio': unique_ratio,
                'suspicious_ratio': suspicious_ratio,
                'filtered_ratio': filtered_ratio,
                'extents': (span_x, span_y, span_z),
                'bounds': ((min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))),
                'raw_points': raw_points,
                'points': preview_points,
                'notes': payload_notes,
                'summary': ', '.join(reason_parts),
            })
    candidates.sort(key=lambda row: (row['score'], row['filtered_count'], row['unique_ratio']), reverse=True)
    return candidates[:limit]


def _codered_axis_mapping(points: list[tuple[float, float, float]], mode: str) -> tuple[list[float], list[float], list[float]]:
    if mode == 'X / Z / Y':
        xs = [p[0] for p in points]
        ys = [p[2] for p in points]
        zs = [p[1] for p in points]
    elif mode == 'Y / X / Z':
        xs = [p[1] for p in points]
        ys = [p[0] for p in points]
        zs = [p[2] for p in points]
    elif mode == 'Y / Z / X':
        xs = [p[1] for p in points]
        ys = [p[2] for p in points]
        zs = [p[0] for p in points]
    elif mode == 'Z / X / Y':
        xs = [p[2] for p in points]
        ys = [p[0] for p in points]
        zs = [p[1] for p in points]
    elif mode == 'Z / Y / X':
        xs = [p[2] for p in points]
        ys = [p[1] for p in points]
        zs = [p[0] for p in points]
    else:
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        zs = [p[2] for p in points]
    return xs, ys, zs


def _codered_equalize_axes(ax, xs: list[float], ys: list[float], zs: list[float]) -> None:
    if not xs or not ys or not zs:
        return
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)
    cx = (min_x + max_x) / 2.0
    cy = (min_y + max_y) / 2.0
    cz = (min_z + max_z) / 2.0
    radius = max(max_x - min_x, max_y - min_y, max_z - min_z) / 2.0
    if radius <= 0:
        radius = 1.0
    ax.set_xlim(cx - radius, cx + radius)
    ax.set_ylim(cy - radius, cy + radius)
    ax.set_zlim(cz - radius, cz + radius)


class HeuristicModelPreviewDialog(tk.Toplevel):
    AXIS_MODES = ['X / Y / Z', 'X / Z / Y', 'Y / X / Z', 'Y / Z / X', 'Z / X / Y', 'Z / Y / X']
    OUTLIER_MODES = ['None', '1-99', '5-95', '10-90']

    def __init__(self, master: tk.Misc, asset_path: Path):
        super().__init__(master)
        self.asset_path = Path(asset_path)
        self.title(f'Code RED - Heuristic 3D Preview - {self.asset_path.name}')
        self.geometry('1460x920')
        self.minsize(1080, 720)
        c = getattr(master, 'theme', {'bg': '#000000', 'panel': '#050505', 'fg': '#FFFFFF', 'button': '#151515', 'accent': '#8B0000'})
        self.configure(bg=c['bg'])
        self.c = c
        self.candidates = _codered_heuristic_model_candidates(self.asset_path)
        self._candidate_rows: dict[str, dict] = {}
        self.axis_mode = tk.StringVar(value='X / Z / Y')
        self.outlier_mode = tk.StringVar(value='1-99')
        self.point_size = tk.DoubleVar(value=1.4)
        self.selected = None
        self._summary_text = tk.StringVar(value='')

        header = tk.Frame(self, bg=c['bg'])
        header.pack(fill='x', padx=12, pady=(12, 8))
        tk.Label(header, text='Heuristic 3D Point-Cloud Preview', font=('SegoeUI', 15, 'bold'), bg=c['bg'], fg=c['fg'], anchor='w').pack(fill='x')
        tk.Label(
            header,
            text='This preview is generated by scanning float triplets in the mesh payload and ranking candidate vertex streams. It is useful for seeing approximate 3D form before full format decoding and rebuild-proven import are wired.',
            bg=c['bg'], fg=c['fg'], anchor='w', justify='left', wraplength=1320,
        ).pack(fill='x', pady=(4, 0))

        top = tk.Frame(self, bg=c['bg'])
        top.pack(fill='x', padx=12, pady=(0, 8))
        tk.Label(top, text='Axis mapping', bg=c['bg'], fg=c['fg']).pack(side='left')
        axis_combo = ttk.Combobox(top, values=self.AXIS_MODES, textvariable=self.axis_mode, state='readonly', width=16)
        axis_combo.pack(side='left', padx=(8, 16))
        axis_combo.bind('<<ComboboxSelected>>', lambda _e: self._draw_selected())
        tk.Label(top, text='Outlier trim', bg=c['bg'], fg=c['fg']).pack(side='left')
        trim_combo = ttk.Combobox(top, values=self.OUTLIER_MODES, textvariable=self.outlier_mode, state='readonly', width=8)
        trim_combo.pack(side='left', padx=(8, 16))
        trim_combo.bind('<<ComboboxSelected>>', lambda _e: self._draw_selected())
        tk.Label(top, text='Point size', bg=c['bg'], fg=c['fg']).pack(side='left')
        point_scale = tk.Scale(top, from_=0.4, to=4.0, resolution=0.2, orient='horizontal', variable=self.point_size, command=lambda _v: self._draw_selected(), bg=c['bg'], fg=c['fg'], highlightthickness=0, troughcolor=c['panel'])
        point_scale.pack(side='left', padx=(8, 12))
        tk.Button(top, text='Reload', command=self._reload_candidates, bg=c['accent'], fg=c['fg'], relief='flat', padx=12, pady=7).pack(side='left')
        tk.Button(top, text='Open Hex Editor', command=lambda: BinaryHexEditorDialog(self, self.asset_path), bg=c['button'], fg=c['fg'], relief='flat', padx=12, pady=7).pack(side='left', padx=(8, 0))
        tk.Button(top, text='Close', command=self.destroy, bg=c['button'], fg=c['fg'], relief='flat', padx=12, pady=7).pack(side='right')

        panes = tk.PanedWindow(self, orient='horizontal', sashrelief='flat', sashwidth=8, bg=c['bg'])
        panes.pack(fill='both', expand=True, padx=12, pady=(0, 12))
        left = tk.Frame(panes, bg=c['bg'])
        right = tk.Frame(panes, bg=c['bg'])
        panes.add(left, width=460)
        panes.add(right)

        tk.Label(left, text='Candidate vertex streams', bg=c['bg'], fg=c['fg'], anchor='w').pack(fill='x', pady=(0, 6))
        self.tree = ttk.Treeview(left, columns=('score', 'stride', 'offset', 'count', 'span'), show='headings', height=12)
        for col, title, width in [('score', 'Score', 70), ('stride', 'Stride', 70), ('offset', 'Offset', 70), ('count', 'Points', 90), ('span', 'Extents', 180)]:
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width, anchor='w')
        self.tree.pack(fill='x')
        self.tree.bind('<<TreeviewSelect>>', lambda _e: self._draw_selected())

        info_box = tk.LabelFrame(left, text='Selection notes', bg=c['bg'], fg=c['fg'])
        info_box.pack(fill='both', expand=True, pady=(8, 0))
        self.info = tk.Text(info_box, height=18, wrap='word', bg=c['panel'], fg=c['fg'], relief='flat')
        self.info.pack(fill='both', expand=True, padx=8, pady=8)
        self.info.configure(state='disabled')

        if _HAVE_MPL:
            fig = Figure(figsize=(7.4, 7.4), dpi=100, facecolor=c['bg'])
            self.ax = fig.add_subplot(111, projection='3d')
            fig.subplots_adjust(left=0.02, right=0.98, bottom=0.02, top=0.98)
            self.canvas = FigureCanvasTkAgg(fig, master=right)
            toolbar = NavigationToolbar2Tk(self.canvas, right, pack_toolbar=False)
            toolbar.update()
            toolbar.pack(fill='x')
            self.canvas.get_tk_widget().pack(fill='both', expand=True)
            self._figure = fig
        else:
            self.ax = None
            self.canvas = None
            msg = tk.Text(right, wrap='word', bg=c['panel'], fg=c['fg'], relief='flat')
            msg.pack(fill='both', expand=True)
            msg.insert('1.0', 'Matplotlib is not available in this environment, so the heuristic 3D point-cloud preview cannot be rendered. The candidate list still exposes stride/offset hypotheses and can be paired with the hex editor and dependency viewer.')
            msg.configure(state='disabled')

        self._populate()

    def _populate(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self._candidate_rows.clear()
        for row in self.candidates:
            ext = row['extents']
            iid = self.tree.insert('', 'end', values=(row['score'], row['stride'], row['offset'], f"{row['count']:,}", f"{ext[0]:.0f}/{ext[1]:.0f}/{ext[2]:.0f}"))
            self._candidate_rows[iid] = row
        children = self.tree.get_children()
        if children:
            self.tree.selection_set(children[0])
            self.tree.focus(children[0])
            self._draw_selected()
        else:
            self._set_info('No plausible point-cloud candidates were found in the current heuristic pass. The file may use a different vertex packing scheme or the payload may require deeper format-specific decoding.')

    def _set_info(self, text: str) -> None:
        self.info.configure(state='normal')
        self.info.delete('1.0', 'end')
        self.info.insert('1.0', text)
        self.info.configure(state='disabled')

    def _reload_candidates(self) -> None:
        self.candidates = _codered_heuristic_model_candidates(self.asset_path)
        self._populate()

    def _draw_selected(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        row = self._candidate_rows.get(sel[0])
        if row is None:
            return
        self.selected = row
        bounds = row['bounds']
        axis_mode = self.axis_mode.get()
        info_lines = [
            f"Stride: {row['stride']} bytes",
            f"Offset: {row['offset']} bytes",
            f"Heuristic score: {row['score']}",
            f"Raw point count: {row['count']:,}",
            f"Filtered point count: {row.get('filtered_count', len(row['points'])):,}",
            f"Unique ratio: {row['unique_ratio']:.2f}",
            f"Suspicious ratio: {row['suspicious_ratio']:.2f}",
            f"Filtered ratio: {row.get('filtered_ratio', 1.0):.2f}",
            f"Axis mapping: {axis_mode}",
            f"Outlier trim: {self.outlier_mode.get()}",
            f"Bounds X: {bounds[0][0]:.2f} to {bounds[0][1]:.2f}",
            f"Bounds Y: {bounds[1][0]:.2f} to {bounds[1][1]:.2f}",
            f"Bounds Z: {bounds[2][0]:.2f} to {bounds[2][1]:.2f}",
            f"Extents: {row['extents'][0]:.2f}, {row['extents'][1]:.2f}, {row['extents'][2]:.2f}",
            '',
            'Selection summary:',
            row['summary'],
        ]
        if row.get('notes'):
            info_lines.extend(['', 'Payload notes:'])
            info_lines.extend(f'- {line}' for line in row['notes'][:12])
        info_lines.extend(['', 'Interpretation note: this is a point-cloud view of guessed vertex positions. It is intended to expose overall form while dictionary-aware mesh decoding is still being built.'])
        self._set_info('\n'.join(info_lines))
        if not _HAVE_MPL or self.ax is None or self.canvas is None:
            return
        self.ax.clear()
        render_points = _codered_percentile_filter(row.get('raw_points') or row['points'], self.outlier_mode.get())
        render_points = _codered_normalize_preview_points(render_points)
        xs, ys, zs = _codered_axis_mapping(render_points, axis_mode)
        self.ax.scatter(xs, ys, zs, s=float(self.point_size.get()), c=zs if zs else 'white', cmap='coolwarm', depthshade=False)
        _codered_equalize_axes(self.ax, xs, ys, zs)
        self.ax.set_title(f"{self.asset_path.name}\nscore {row['score']}  stride {row['stride']}  offset {row['offset']}  trim {self.outlier_mode.get()}", color='white', pad=16)
        self.ax.set_xlabel('X', color='white')
        self.ax.set_ylabel('Y', color='white')
        self.ax.set_zlabel('Z', color='white')
        self.ax.set_facecolor(self.c['panel'])
        self.ax.tick_params(colors='white')
        for axis in [self.ax.xaxis, self.ax.yaxis, self.ax.zaxis]:
            try:
                axis.pane.fill = True
                axis.pane.set_facecolor((0.03, 0.03, 0.03, 1.0))
                axis.pane.set_edgecolor((0.3, 0.3, 0.3, 1.0))
            except Exception:
                pass
        self.ax.grid(True, color='#444444')
        self.canvas.draw_idle()


_CODERED_V43_MODEL_SUMMARY = ModelFamilyDialog._summary_text
_CODERED_V43_MODEL_INIT = ModelFamilyDialog.__init__


def _codered_v43_model_summary(self) -> str:
    base = _CODERED_V43_MODEL_SUMMARY(self)
    candidates = _codered_heuristic_model_candidates(self.asset_path, limit=3)
    if not candidates:
        extra = '\n\nHeuristic 3D preview:\n- No plausible point-cloud candidates were detected in the current scan.'
    else:
        extra_lines = ['\n\nHeuristic 3D preview candidates:']
        for row in candidates:
            ext = row['extents']
            extra_lines.append(
                f"- score={row['score']} stride={row['stride']} offset={row['offset']} points={row['count']:,} extents=({ext[0]:.0f}, {ext[1]:.0f}, {ext[2]:.0f})"
            )
        extra = '\n'.join(extra_lines)
    extra += '\n- Use “Open Heuristic 3D Preview” to inspect a point-cloud rendering of guessed vertex data. This is approximate and not yet rebuild-proven.'
    return base + extra


def _codered_v43_model_init(self, master: 'WorkbenchApp', asset_path: Path, archive_path: Optional[Path] = None, archive_entry: Optional[dict] = None, on_saved: Optional[Callable[[Path], None]] = None):
    _CODERED_V43_MODEL_INIT(self, master, asset_path, archive_path=archive_path, archive_entry=archive_entry, on_saved=on_saved)
    button_row = None
    for child in self.winfo_children():
        if isinstance(child, tk.Frame):
            texts = [sub.cget('text') for sub in child.winfo_children() if isinstance(sub, tk.Button)]
            if 'Open Current Bytes' in texts and 'Open Best Texture Candidate' in texts:
                button_row = child
                break
    if button_row is not None:
        close_btn = None
        for sub in button_row.winfo_children():
            if isinstance(sub, tk.Button) and sub.cget('text') == 'Close':
                close_btn = sub
                break
        if close_btn is not None:
            tk.Button(button_row, text='Open Heuristic 3D Preview', command=lambda: HeuristicModelPreviewDialog(self, self.asset_path), bg=self.master_app.theme['button'], fg=self.master_app.theme['fg'], relief='flat', padx=12, pady=7).pack(side='left', padx=(8, 0), before=close_btn)
        else:
            tk.Button(button_row, text='Open Heuristic 3D Preview', command=lambda: HeuristicModelPreviewDialog(self, self.asset_path), bg=self.master_app.theme['button'], fg=self.master_app.theme['fg'], relief='flat', padx=12, pady=7).pack(side='left', padx=(8, 0))


ModelFamilyDialog._summary_text = _codered_v43_model_summary
ModelFamilyDialog.__init__ = _codered_v43_model_init


# --- Code RED external patch loader ---
def _codered_external_patch_candidates(filename: str) -> list[Path]:
    root = Path(__file__).resolve().parent
    candidates = [
        root / filename,
        root / 'combine updates' / filename,
    ]
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


_CODERED_EXTERNAL_PATCH_STATUS: dict[str, dict[str, object]] = {}


def _codered_apply_external_patch(filename: str) -> bool:
    patch_candidates = _codered_external_patch_candidates(filename)
    patch_path = next((candidate for candidate in patch_candidates if candidate.exists()), None)
    if patch_path is None:
        _CODERED_EXTERNAL_PATCH_STATUS[filename] = {
            'applied': False,
            'status': 'missing',
            'searched': [str(candidate) for candidate in patch_candidates],
        }
        return False
    try:
        import importlib.util
        import sys
        import traceback
        spec = importlib.util.spec_from_file_location(f'codered_patch_{patch_path.stem}', patch_path)
        if spec is None or spec.loader is None:
            _CODERED_EXTERNAL_PATCH_STATUS[filename] = {
                'applied': False,
                'status': 'invalid-spec',
                'path': str(patch_path),
                'searched': [str(candidate) for candidate in patch_candidates],
            }
            return False
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        apply_fn = getattr(module, 'apply', None)
        if not callable(apply_fn):
            _CODERED_EXTERNAL_PATCH_STATUS[filename] = {
                'applied': False,
                'status': 'no-apply-function',
                'path': str(patch_path),
                'searched': [str(candidate) for candidate in patch_candidates],
            }
            return False
        apply_fn(WorkbenchApp, globals())
        _CODERED_EXTERNAL_PATCH_STATUS[filename] = {
            'applied': True,
            'status': 'applied',
            'path': str(patch_path),
            'searched': [str(candidate) for candidate in patch_candidates],
        }
        return True
    except Exception:
        error_text = traceback.format_exc()
        _CODERED_EXTERNAL_PATCH_STATUS[filename] = {
            'applied': False,
            'status': 'error',
            'path': str(patch_path),
            'searched': [str(candidate) for candidate in patch_candidates],
            'error': error_text,
        }
        try:
            logs_dir = Path(__file__).resolve().parent / 'logs'
            logs_dir.mkdir(parents=True, exist_ok=True)
            (logs_dir / 'external_patch_loader_error.log').write_text(error_text, encoding='utf-8')
        except Exception:
            pass
        return False

_CODERED_EXTERNAL_PATCHES_APPLIED = {
    'codered_cross_rpf_search_patch.py': _codered_apply_external_patch('codered_cross_rpf_search_patch.py'),
    'codered_script_string_edit_patch.py': _codered_apply_external_patch('codered_script_string_edit_patch.py'),
    'codered_script_donor_patch.py': _codered_apply_external_patch('codered_script_donor_patch.py'),
    'codered_toolchain_studio_patch.py': _codered_apply_external_patch('codered_toolchain_studio_patch.py'),
    'codered_world_vfs_patch.py': _codered_apply_external_patch('codered_world_vfs_patch.py'),
    'codered_world_reference_patch.py': _codered_apply_external_patch('codered_world_reference_patch.py'),
    'codered_world_placement_patch.py': _codered_apply_external_patch('codered_world_placement_patch.py'),
    'codered_world_wsi_probe_patch.py': _codered_apply_external_patch('codered_world_wsi_probe_patch.py'),
    'codered_world_harmony_patch.py': _codered_apply_external_patch('codered_world_harmony_patch.py'),
    'codered_workspace_tighten_patch.py': _codered_apply_external_patch('codered_workspace_tighten_patch.py'),
}



def _codered_write_external_patch_status() -> None:
    try:
        logs_dir = Path(__file__).resolve().parent / 'logs'
        logs_dir.mkdir(parents=True, exist_ok=True)
        json_path = logs_dir / 'external_patch_status.json'
        md_path = logs_dir / 'external_patch_status.md'
        json_path.write_text(json.dumps(_CODERED_EXTERNAL_PATCH_STATUS, indent=2), encoding='utf-8')
        lines = ['# Code RED External Patch Status', '']
        for name, info in sorted(_CODERED_EXTERNAL_PATCH_STATUS.items()):
            lines.append(f"## {name}")
            lines.append(f"- applied: {info.get('applied')}")
            lines.append(f"- status: {info.get('status')}")
            if info.get('path'):
                lines.append(f"- path: `{info.get('path')}`")
            searched = info.get('searched') or []
            if searched:
                lines.append('- searched:')
                for candidate in searched:
                    lines.append(f"  - `{candidate}`")
            if info.get('error'):
                lines.append('```text')
                lines.append(str(info.get('error')).rstrip())
                lines.append('```')
            lines.append('')
        md_path.write_text('\n'.join(lines).rstrip() + '\n', encoding='utf-8')
    except Exception:
        pass


_codered_write_external_patch_status()

# --- Code RED World WSI Studio patch (v44) ---
# Adds a first-class RSC05/Zstandard world-sector lane for .wsi files.
# This is intentionally conservative: it supports decode, inspect, export,
# editable decoded-payload sessions, and verified rebuilt .wsi clones. It does
# not pretend to know the full proprietary placement schema yet.

def _codered_wsi_resource_analysis(path: Path) -> dict:
    import math as _math
    data = read_bytes(path)
    resource = parse_resource_header(data)
    payload_info = extract_resource_payload(data, resource) if resource else {
        'payload': data,
        'raw_payload': data,
        'coded_payload': data,
        'notes': ['No resource header; raw file bytes used.'],
        'decompressed': False,
        'decrypted': False,
        'zstd_frame': None,
        'header_size': 0,
    }
    payload = payload_info.get('payload') or b''
    strings = extract_candidate_strings(payload, limit=160)

    # Pointer-looking values in decoded RDR resources often sit around 0x50xxxxxx.
    ptr_samples = []
    ptr_count = 0
    for off in range(0, max(0, len(payload) - 3), 4):
        val = int.from_bytes(payload[off:off + 4], 'little', signed=False)
        if 0x50000000 <= val <= 0x50FFFFFF:
            ptr_count += 1
            if len(ptr_samples) < 80:
                ptr_samples.append({'offset': off, 'value': f'0x{val:08X}'})

    # Transform-like float triplets. These are rough navigation beacons for humans,
    # not a trusted parser. They help find placement-dense regions quickly.
    transform_samples = []
    transform_count = 0
    scan_limit = min(len(payload) - 12, 2_000_000)
    for off in range(0, max(0, scan_limit), 4):
        try:
            x, y, z = struct.unpack_from('<fff', payload, off)
        except Exception:
            break
        vals = (x, y, z)
        if all(_math.isfinite(v) for v in vals) and all(abs(v) <= 200000.0 for v in vals) and any(abs(v) >= 1.0 for v in vals):
            # Filter out common NaN sentinels and normalized vector noise.
            if not all(-1.05 <= v <= 1.05 for v in vals):
                transform_count += 1
                if len(transform_samples) < 120:
                    transform_samples.append({'offset': off, 'x': round(x, 4), 'y': round(y, 4), 'z': round(z, 4)})

    embedded_markers = []
    for label, marker in [
        ('RSC', b'RSC'),
        ('zstd', b'\x28\xB5\x2F\xFD'),
        ('zlib_789c', b'\x78\x9C'),
        ('zlib_78da', b'\x78\xDA'),
        ('maya_path', b'T:/'),
        ('model_ext_mb', b'.mb'),
        ('drawable_ext_wvd', b'.wvd'),
        ('xml_start', b'<'),
    ]:
        offs = []
        start = 0
        while len(offs) < 20:
            idx = payload.find(marker, start)
            if idx < 0:
                break
            offs.append(idx)
            start = idx + 1
        if offs:
            embedded_markers.append({'label': label, 'count_sampled': len(offs), 'offsets': offs})

    # Small focused hash probe for the current vehicle/prop investigation. If the
    # user's environment has ImportedFileNames.txt, future passes can widen this.
    candidate_names = [
        'p_gen_cart01x', 'p_gen_cart03x', 'p_gen_wheelbarrow01x', 'p_gen_lumberCart01x',
        'blk_carts', 'car01x', 'truck01x', 'armoredcar01x', 'template_vehiclecar01',
        'template_vehicletruck01', 'vehiclecar01', 'playercar', 'PlayerCarGringo_Car',
        'car_gringo', 'car01x.vehmodel', 'truck01x.vehmodel',
    ]
    hash_hits = []
    for name in candidate_names:
        hv = rdr_name_hash(name)
        le = hv.to_bytes(4, 'little')
        be = hv.to_bytes(4, 'big')
        le_count = payload.count(le)
        be_count = payload.count(be)
        if le_count or be_count:
            hash_hits.append({
                'name': name,
                'hash': f'0x{hv:08X}',
                'little_count': le_count,
                'big_count': be_count,
                'first_little': payload.find(le),
                'first_big': payload.find(be),
            })

    rebuilt_ok = False
    rebuilt_notes = []
    if resource:
        rebuilt, rebuilt_notes = rebuild_resource_stream_from_processed_payload(data, payload)
        if rebuilt is not None:
            rebuilt_ok, verify_msg = verify_resource_roundtrip(data, rebuilt)
            rebuilt_notes.append(verify_msg)
        else:
            rebuilt_notes.append('Round-trip rebuild did not produce bytes.')

    return {
        'path': str(path),
        'name': path.name,
        'size': len(data),
        'sha256': hashlib.sha256(data).hexdigest(),
        'resource': resource,
        'payload_info': {
            'notes': payload_info.get('notes') or [],
            'decompressed': bool(payload_info.get('decompressed')),
            'decrypted': bool(payload_info.get('decrypted')),
            'header_size': payload_info.get('header_size'),
            'raw_payload_size': len(payload_info.get('raw_payload') or b''),
            'coded_payload_size': len(payload_info.get('coded_payload') or b''),
            'processed_payload_size': len(payload),
            'processed_payload_sha256': hashlib.sha256(payload).hexdigest() if payload else '',
            'zstd_frame': payload_info.get('zstd_frame'),
        },
        'strings': strings,
        'string_count': len(strings),
        'pointer_like_count': ptr_count,
        'pointer_samples': ptr_samples,
        'transform_like_count': transform_count,
        'transform_samples': transform_samples,
        'embedded_markers': embedded_markers,
        'focused_hash_hits': hash_hits,
        'roundtrip_rebuild_ok': rebuilt_ok,
        'roundtrip_notes': rebuilt_notes,
    }


def _codered_wsi_report_text(path: Path, analysis: Optional[dict] = None) -> str:
    analysis = analysis or _codered_wsi_resource_analysis(path)
    res = analysis.get('resource') or {}
    pi = analysis.get('payload_info') or {}
    lines = [
        'Code RED WSI Studio',
        '===================',
        '',
        f"File: {analysis.get('path')}",
        f"File size: {analysis.get('size', 0):,} bytes",
        f"File sha256: {analysis.get('sha256')}",
        '',
        'Resource:',
    ]
    if res:
        lines.extend([
            f"- header: {res.get('ident_name')} [{res.get('raw_ident_name')}]",
            f"- type: {res.get('resource_type')}",
            f"- flag1: 0x{int(res.get('flag1') or 0):08X}",
            f"- compressed: {res.get('is_compressed')}",
            f"- declared total size: {int(res.get('total_size') or 0):,}",
        ])
    else:
        lines.append('- no resource header detected')
    lines.extend([
        '',
        'Payload:',
        f"- header size: {pi.get('header_size')}",
        f"- raw payload size: {pi.get('raw_payload_size'):,}",
        f"- coded payload size: {pi.get('coded_payload_size'):,}",
        f"- processed payload size: {pi.get('processed_payload_size'):,}",
        f"- processed payload sha256: {pi.get('processed_payload_sha256')}",
        f"- decompressed: {pi.get('decompressed')}",
        f"- decrypted: {pi.get('decrypted')}",
    ])
    zf = pi.get('zstd_frame')
    if zf:
        lines.append(f"- zstd frame: descriptor=0x{int(zf.get('frame_descriptor') or 0):02X}, window={zf.get('window_size')}, checksum={zf.get('checksum_flag')}, single_segment={zf.get('single_segment')}")
    notes = pi.get('notes') or []
    if notes:
        lines.append('- notes:')
        lines.extend(f'  - {note}' for note in notes)
    lines.extend([
        '',
        'Structure cues:',
        f"- printable candidate strings: {analysis.get('string_count', 0)}",
        f"- pointer-like 0x50xxxxxx values: {analysis.get('pointer_like_count', 0)}",
        f"- transform-like float triplets: {analysis.get('transform_like_count', 0)}",
        f"- focused vehicle/prop hash hits: {len(analysis.get('focused_hash_hits') or [])}",
        f"- round-trip rebuild verified: {analysis.get('roundtrip_rebuild_ok')}",
    ])
    if analysis.get('roundtrip_notes'):
        lines.append('- round-trip notes:')
        lines.extend(f"  - {n}" for n in analysis.get('roundtrip_notes') or [])
    markers = analysis.get('embedded_markers') or []
    if markers:
        lines.extend(['', 'Embedded marker samples:'])
        for rec in markers[:20]:
            lines.append(f"- {rec['label']}: offsets {rec['offsets']}")
    hits = analysis.get('focused_hash_hits') or []
    if hits:
        lines.extend(['', 'Focused hash hits:'])
        for rec in hits:
            lines.append(f"- {rec['name']} {rec['hash']} little={rec['little_count']} big={rec['big_count']} first_le={rec['first_little']} first_be={rec['first_big']}")
    ptrs = analysis.get('pointer_samples') or []
    if ptrs:
        lines.extend(['', 'Pointer-like samples:'])
        for rec in ptrs[:40]:
            lines.append(f"- 0x{rec['offset']:08X}: {rec['value']}")
    transforms = analysis.get('transform_samples') or []
    if transforms:
        lines.extend(['', 'Transform-like samples:'])
        for rec in transforms[:50]:
            lines.append(f"- 0x{rec['offset']:08X}: x={rec['x']} y={rec['y']} z={rec['z']}")
    strings = analysis.get('strings') or []
    if strings:
        lines.extend(['', 'Candidate strings:'])
        lines.extend(f'- {s}' for s in strings[:120])
    lines.extend([
        '',
        'Editing policy:',
        '- The decoded payload can be exported and edited as bytes.',
        '- Save Rebuilt WSI recompresses the edited payload back into an RSC05 resource clone and verifies decoded payload equality.',
        '- Direct prop-to-vehicle name replacement is not exposed until the placement record schema or hash map is confirmed.',
    ])
    return '\n'.join(lines)


def _codered_wsi_export_bundle(path: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    data = read_bytes(path)
    resource = parse_resource_header(data)
    payload_info = extract_resource_payload(data, resource) if resource else {'payload': data}
    payload = payload_info.get('payload') or b''
    analysis = _codered_wsi_resource_analysis(path)
    stem = path.stem
    decoded_path = out_dir / f'{stem}_decoded_payload.bin'
    report_path = out_dir / f'{stem}_wsi_report.txt'
    json_path = out_dir / f'{stem}_wsi_report.json'
    clone_path = out_dir / f'{stem}_roundtrip_clone.wsi'
    decoded_path.write_bytes(payload)
    report_path.write_text(_codered_wsi_report_text(path, analysis), encoding='utf-8')
    json_path.write_text(json.dumps(analysis, indent=2, default=str), encoding='utf-8')
    rebuilt, notes = rebuild_resource_stream_from_processed_payload(data, payload)
    clone_ok = False
    verify_msg = 'No rebuilt clone generated.'
    if rebuilt is not None:
        clone_path.write_bytes(rebuilt)
        clone_ok, verify_msg = verify_resource_roundtrip(data, rebuilt)
    return {
        'decoded_payload': str(decoded_path),
        'report': str(report_path),
        'json': str(json_path),
        'roundtrip_clone': str(clone_path) if rebuilt is not None else '',
        'roundtrip_ok': clone_ok,
        'verify_message': verify_msg,
        'notes': notes if rebuilt is not None else [],
    }


def _codered_wsi_rebuild_from_payload_file(original_wsi: Path, decoded_payload_file: Path, target_wsi: Path) -> tuple[bool, str, list[str]]:
    original = read_bytes(original_wsi)
    payload = read_bytes(decoded_payload_file)
    rebuilt, notes = rebuild_resource_stream_from_processed_payload(original, payload)
    if rebuilt is None:
        return False, 'Could not rebuild WSI resource from edited payload.', notes
    target_wsi.write_bytes(rebuilt)
    ok, msg = verify_resource_roundtrip(original, rebuilt)
    # If edited payload differs from original, verify against edited payload too.
    new_info = extract_resource_payload(rebuilt, parse_resource_header(rebuilt))
    if new_info.get('payload') == payload:
        ok = True
        msg = 'Edited decoded payload matched after rebuild verification.'
    return ok, msg, notes


_CODERED_ORIG_WORLD_INSPECT_V44 = WorldModule.inspect
_CODERED_ORIG_WORLD_VALIDATE_V44 = WorldModule.validate

def _codered_world_inspect_v44(self, path: Path) -> ModuleInspection:
    if path.suffix.lower() == '.wsi':
        analysis = _codered_wsi_resource_analysis(path)
        res = analysis.get('resource') or {}
        pi = analysis.get('payload_info') or {}
        details = [
            f"Path: {path}",
            f"Size: {path.stat().st_size:,} bytes",
            f"Extension: {path.suffix.lower()}",
            f"Resource header: {res.get('ident_name', 'none')} [{res.get('raw_ident_name', 'none')}], type={res.get('resource_type', 'n/a')}",
            f"Compressed: {res.get('is_compressed', False)}",
            f"Processed payload: {pi.get('processed_payload_size', 0):,} bytes",
            f"Candidate strings: {analysis.get('string_count', 0)}",
            f"Pointer-like values: {analysis.get('pointer_like_count', 0)}",
            f"Transform-like triplets: {analysis.get('transform_like_count', 0)}",
            f"Focused vehicle/prop hash hits: {len(analysis.get('focused_hash_hits') or [])}",
            f"Round-trip rebuild verified: {analysis.get('roundtrip_rebuild_ok')}",
        ]
        if pi.get('notes'):
            details.append('Payload processing notes:')
            details.extend(f"- {n}" for n in pi.get('notes') or [])
        warning = 'WSI binary editing is enabled through decoded-payload export/rebuild only. Prop-to-vehicle replacement still needs confirmed placement record offsets.'
        preview = _codered_wsi_report_text(path, analysis)
        return ModuleInspection(self.name, f"World WSI - {path.name}", 'RSC05/Zstandard world-sector inspection routed through built-in WSI Studio.', '\n'.join(details), warning, preview, can_edit_preview_text=False)
    return _CODERED_ORIG_WORLD_INSPECT_V44(self, path)


def _codered_world_validate_v44(self, path: Path) -> OperationResult:
    if path.suffix.lower() == '.wsi':
        try:
            analysis = _codered_wsi_resource_analysis(path)
            if analysis.get('roundtrip_rebuild_ok'):
                return OperationResult(True, 'WSI validation passed', f"Decoded payload size {analysis['payload_info']['processed_payload_size']:,} bytes. Round-trip rebuild verified.")
            return OperationResult(True, 'WSI validation partial', 'WSI decoded, but round-trip rebuild did not fully verify. Use Export to inspect the report before editing.')
        except Exception as exc:
            return OperationResult(False, 'WSI validation failed', str(exc))
    return _CODERED_ORIG_WORLD_VALIDATE_V44(self, path)

WorldModule.inspect = _codered_world_inspect_v44
WorldModule.validate = _codered_world_validate_v44


class WSIStudioDialog(tk.Toplevel):
    def __init__(self, master: 'WorkbenchApp', wsi_path: Path, archive_path: Optional[Path] = None, archive_entry: Optional[dict] = None, on_saved: Optional[Callable[[Path], None]] = None):
        super().__init__(master)
        self.master_app = master
        self.wsi_path = Path(wsi_path)
        self.archive_path = Path(archive_path) if archive_path else None
        self.archive_entry = archive_entry or {}
        self.on_saved = on_saved
        self.title(f'Code RED - WSI Studio - {self.wsi_path.name}')
        self.geometry('1320x860')
        self.minsize(940, 620)
        self.theme = getattr(master, 'theme', {'bg': '#000000', 'panel': '#050505', 'fg': '#FFFFFF', 'button': '#151515', 'accent': '#8B0000'})
        c = self.theme
        self.configure(bg=c['bg'])
        self.analysis = _codered_wsi_resource_analysis(self.wsi_path)
        header = tk.Frame(self, bg=c['bg'])
        header.pack(fill='x', padx=12, pady=(12, 8))
        tk.Label(header, text=f'WSI Studio - {self.wsi_path.name}', font=('SegoeUI', 15, 'bold'), bg=c['bg'], fg=c['fg'], anchor='w').pack(fill='x')
        pi = self.analysis.get('payload_info') or {}
        tk.Label(header, text=f"RSC payload: {pi.get('processed_payload_size', 0):,} decoded bytes   round-trip: {self.analysis.get('roundtrip_rebuild_ok')}   strings: {self.analysis.get('string_count', 0)}   transforms: {self.analysis.get('transform_like_count', 0)}", bg=c['bg'], fg=c['fg'], anchor='w').pack(fill='x', pady=(4, 0))
        if self.archive_path:
            tk.Label(header, text=f'Archive source: {self.archive_path}', bg=c['bg'], fg=c['fg'], anchor='w').pack(fill='x', pady=(4, 0))
        controls = tk.Frame(self, bg=c['bg'])
        controls.pack(fill='x', padx=12, pady=(0, 8))
        tk.Button(controls, text='Export WSI Bundle', command=self._export_bundle, bg=c['accent'], fg=c['fg'], relief='flat', padx=12, pady=7).pack(side='left')
        tk.Button(controls, text='Open Decoded Bytes', command=self._open_decoded_bytes, bg=c['button'], fg=c['fg'], relief='flat', padx=12, pady=7).pack(side='left', padx=(8, 0))
        tk.Button(controls, text='Build WSI from Decoded Payload', command=self._build_from_payload, bg=c['button'], fg=c['fg'], relief='flat', padx=12, pady=7).pack(side='left', padx=(8, 0))
        tk.Button(controls, text='Save Roundtrip Clone', command=self._save_roundtrip_clone, bg=c['button'], fg=c['fg'], relief='flat', padx=12, pady=7).pack(side='left', padx=(8, 0))
        tk.Button(controls, text='Open Raw Hex', command=lambda: BinaryHexEditorDialog(self, self.wsi_path), bg=c['button'], fg=c['fg'], relief='flat', padx=12, pady=7).pack(side='left', padx=(8, 0))
        tk.Button(controls, text='Close', command=self.destroy, bg=c['button'], fg=c['fg'], relief='flat', padx=12, pady=7).pack(side='right')
        self.report = tk.Text(self, wrap='none', bg=c['panel'], fg=c['fg'], insertbackground=c['fg'], relief='flat')
        self.report.pack(fill='both', expand=True, padx=12, pady=(0, 12))
        self.report.insert('1.0', _codered_wsi_report_text(self.wsi_path, self.analysis))
        self.report.configure(state='disabled')

    def _default_out_dir(self) -> Path:
        base = self.wsi_path.parent / f'{self.wsi_path.stem}_wsi_studio'
        base.mkdir(parents=True, exist_ok=True)
        return base

    def _export_bundle(self) -> None:
        target = filedialog.askdirectory(parent=self, title='Export WSI Studio Bundle')
        if not target:
            return
        try:
            result = _codered_wsi_export_bundle(self.wsi_path, Path(target))
            messagebox.showinfo('WSI export complete', f"Report: {result['report']}\nDecoded payload: {result['decoded_payload']}\nRoundtrip clone: {result['roundtrip_clone']}\nVerify: {result['verify_message']}", parent=self)
        except Exception as exc:
            messagebox.showerror('WSI export failed', str(exc), parent=self)

    def _open_decoded_bytes(self) -> None:
        try:
            out_dir = self._default_out_dir()
            data = read_bytes(self.wsi_path)
            payload = extract_resource_payload(data, parse_resource_header(data)).get('payload') or b''
            decoded = out_dir / f'{self.wsi_path.stem}_decoded_payload.bin'
            decoded.write_bytes(payload)
            def _saved(decoded_path: Path) -> None:
                # Build beside the edited decoded payload so the user has an immediate WSI candidate.
                rebuilt_target = decoded_path.with_name(f'{self.wsi_path.stem}_rebuilt_from_edited_payload.wsi')
                ok, msg, notes = _codered_wsi_rebuild_from_payload_file(self.wsi_path, decoded_path, rebuilt_target)
                if self.on_saved is not None and ok:
                    self.on_saved(rebuilt_target)
                messagebox.showinfo('Decoded payload saved', f'Rebuilt WSI: {rebuilt_target}\n{msg}\n' + ('\n'.join(notes[:8]) if notes else ''), parent=self)
            BinaryHexEditorDialog(self, decoded, title=f'Decoded WSI Payload - {self.wsi_path.name}', on_saved=_saved)
        except Exception as exc:
            messagebox.showerror('Open decoded bytes failed', str(exc), parent=self)

    def _build_from_payload(self) -> None:
        payload_path = filedialog.askopenfilename(parent=self, title='Select edited decoded payload', filetypes=[('Decoded payload', '*.bin'), ('All files', '*.*')])
        if not payload_path:
            return
        target = filedialog.asksaveasfilename(parent=self, title='Save rebuilt WSI', defaultextension='.wsi', initialfile=f'{self.wsi_path.stem}_rebuilt.wsi', filetypes=[('WSI world sector', '*.wsi'), ('All files', '*.*')])
        if not target:
            return
        try:
            ok, msg, notes = _codered_wsi_rebuild_from_payload_file(self.wsi_path, Path(payload_path), Path(target))
            messagebox.showinfo('WSI rebuild complete' if ok else 'WSI rebuild warning', f'{msg}\nSaved: {target}\n' + ('\n'.join(notes[:8]) if notes else ''), parent=self)
        except Exception as exc:
            messagebox.showerror('WSI rebuild failed', str(exc), parent=self)

    def _save_roundtrip_clone(self) -> None:
        target = filedialog.asksaveasfilename(parent=self, title='Save WSI Roundtrip Clone', defaultextension='.wsi', initialfile=f'{self.wsi_path.stem}_roundtrip_clone.wsi', filetypes=[('WSI world sector', '*.wsi'), ('All files', '*.*')])
        if not target:
            return
        try:
            data = read_bytes(self.wsi_path)
            payload = extract_resource_payload(data, parse_resource_header(data)).get('payload') or b''
            rebuilt, notes = rebuild_resource_stream_from_processed_payload(data, payload)
            if rebuilt is None:
                raise RuntimeError('; '.join(notes) if notes else 'roundtrip rebuild returned no data')
            Path(target).write_bytes(rebuilt)
            ok, msg = verify_resource_roundtrip(data, rebuilt)
            messagebox.showinfo('Roundtrip clone saved' if ok else 'Roundtrip clone warning', f'{msg}\nSaved: {target}\n' + ('\n'.join(notes[:8]) if notes else ''), parent=self)
        except Exception as exc:
            messagebox.showerror('Roundtrip clone failed', str(exc), parent=self)


_CODERED_V44_PREV_MODULE_ACTION = WorkbenchApp.module_action
_CODERED_V44_PREV_INSPECT_EXTRACTED = WorkbenchApp.inspect_extracted_entry

def _codered_v44_module_action(self, module_name: str, action: str) -> None:
    mod = MODULE_BY_NAME[module_name]
    path = self.selected_path
    if path and path.is_file() and mod.can_handle(path) and mod.name == 'World' and path.suffix.lower() == '.wsi':
        if action == 'Open Viewer':
            insp = mod.inspect(path)
            self._write_module_output(mod.name, insp)
            self.notebook.select(self._tab_index_for_name(mod.name))
            WSIStudioDialog(self, path)
            return
        if action == 'Export':
            target = filedialog.askdirectory(title='Export WSI Studio Bundle')
            if target:
                try:
                    result = _codered_wsi_export_bundle(path, Path(target))
                    self._show_result(OperationResult(True, 'WSI export complete', f"Report: {result['report']}\nDecoded payload: {result['decoded_payload']}\nRoundtrip clone: {result['roundtrip_clone']}\nVerify: {result['verify_message']}"))
                except Exception as exc:
                    self._show_result(OperationResult(False, 'WSI export failed', str(exc)))
            return
        if action == 'Replace':
            payload_path = filedialog.askopenfilename(title='Select edited decoded payload or WSI clone', filetypes=[('WSI / decoded payload', '*.wsi *.bin'), ('All files', '*.*')])
            if payload_path:
                src = Path(payload_path)
                try:
                    if src.suffix.lower() == '.wsi':
                        result = safe_backup_replace(path, src)
                    else:
                        target = path.with_name(path.stem + '_rebuilt_from_payload.wsi')
                        ok, msg, notes = _codered_wsi_rebuild_from_payload_file(path, src, target)
                        result = OperationResult(ok, 'WSI rebuilt from decoded payload', f'{msg}\nCandidate: {target}\n' + ('\n'.join(notes[:8]) if notes else ''))
                    self._show_result(result)
                except Exception as exc:
                    self._show_result(OperationResult(False, 'WSI replace/rebuild failed', str(exc)))
            return
    return _CODERED_V44_PREV_MODULE_ACTION(self, module_name, action)


def _codered_v44_inspect_extracted_entry(self, temp_path: Path, archive_entry: dict, archive_path: Path) -> None:
    mod = self.resolve_module(temp_path)
    if mod and mod.name == 'World' and temp_path.suffix.lower() == '.wsi':
        insp = mod.inspect(temp_path)
        details = [
            f"Archive source: {archive_path}",
            f"Internal path: {archive_entry.get('path', '')}",
            f"Temp extract: {temp_path}",
            '',
            insp.details,
        ]
        routed = ModuleInspection(mod.name, insp.title, insp.summary, '\n'.join(details), insp.warning, insp.preview_text, insp.can_edit_preview_text)
        self._write_module_output(mod.name, routed)
        self.notebook.select(self._tab_index_for_name(mod.name))
        def _saved(_p: Path) -> None:
            plan_path = temp_path.with_name(temp_path.name + '.archive_reintegrate_plan.txt')
            plan_path.write_text('\n'.join([
                'WSI Archive Reintegrate Plan',
                '============================',
                '',
                f'Archive source: {archive_path}',
                f'Internal path: {archive_entry.get("path", "")}',
                f'Temp extract: {temp_path}',
                f'Rebuilt/edited WSI: {_p}',
                '',
                'Status:',
                '- WSI decoded payload was rebuilt into a resource-stream clone.',
                '- Apply through the archive-copy patch lane only after slot-size/reintegration validation.',
            ]), encoding='utf-8')
            self.log(f'Wrote WSI archive reintegration plan: {plan_path.name}')
        WSIStudioDialog(self, temp_path, archive_path=archive_path, archive_entry=archive_entry, on_saved=_saved)
        return
    return _CODERED_V44_PREV_INSPECT_EXTRACTED(self, temp_path, archive_entry, archive_path)

WorkbenchApp.module_action = _codered_v44_module_action
WorkbenchApp.inspect_extracted_entry = _codered_v44_inspect_extracted_entry
# --- end Code RED World WSI Studio patch (v44) ---
