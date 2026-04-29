from __future__ import annotations

# Code RED Pass 26: Model XML assembly/indexed-preview export/import patch.
# Adds LOD-family export, texture dictionary extraction, OBJ family preview, and safe import-back verification.

def apply(WorkbenchApp, g):
    import json
    import math
    import re
    import shutil
    import struct
    import subprocess
    import sys
    import time
    import tempfile
    import zlib
    from pathlib import Path
    from xml.sax.saxutils import escape

    tk = g.get('tk')
    filedialog = g.get('filedialog')
    messagebox = g.get('messagebox')
    OperationResult = g.get('OperationResult')
    ModuleInspection = g.get('ModuleInspection')
    MODULE_BY_NAME = g.get('MODULE_BY_NAME', {})
    read_bytes = g.get('read_bytes')
    parse_resource_header = g.get('parse_resource_header')
    extract_resource_payload = g.get('extract_resource_payload')
    parse_rpf6 = g.get('parse_rpf6')
    extract_rpf_entry = g.get('extract_rpf_entry')
    parse_dds_header = g.get('parse_dds_header')
    CODERED_APP_ROOT = g.get('CODERED_APP_ROOT', Path(__file__).resolve().parent)

    MODEL_EXTS = {'.wft', '.wfd', '.wvd', '.xft', '.xfd', '.xvd', '.wbd', '.wtb', '.wsi', '.wsp', '.wsg', '.wtl'}
    TEXTURE_EXTS = {'.dds', '.png', '.wtd', '.wtx', '.wsf', '.xtd', '.xtx', '.xsf'}

    def _safe_filename(value, default='asset'):
        value = str(value or default).replace('\\', '/')
        value = Path(value).name
        value = re.sub(r'[^A-Za-z0-9_.-]+', '_', value).strip('._')
        return (value or default)[:140]

    def _scan_ascii_strings(data: bytes, limit=2000):
        out = []
        seen = set()
        for m in re.finditer(rb'[A-Za-z0-9_./:\\-]{4,160}', data or b''):
            s = m.group().decode('latin-1', errors='ignore')
            if s in seen:
                continue
            seen.add(s)
            out.append(s)
            if len(out) >= limit:
                break
        return out

    def _scan_refs(data: bytes):
        strings = _scan_ascii_strings(data, limit=4000)
        refs = {}
        for ext in ['.dds', '.png', '.wtd', '.wtx', '.wsf', '.wtb', '.wvd', '.wfd', '.wft', '.fxc']:
            refs[ext] = sorted({s for s in strings if ext in s.lower()})[:160]
        bone_hints = sorted({
            s for s in strings
            if any(tok in s.lower() for tok in ('bone', 'spine', 'pelvis', 'head', 'neck', 'arm', 'leg', 'root', 'tail', 'finger'))
        })[:120]
        return strings, refs, bone_hints


    EDITABLE_REF_EXTS = ('.dds', '.png', '.wtd', '.wtx', '.wsf', '.xtd', '.xtx', '.xsf', '.fxc')
    MODEL_REF_EXTS = ('.wft', '.wfd', '.wvd', '.xft', '.xfd', '.xvd', '.wbd', '.wsi', '.wsp', '.wsg', '.wtl')

    def _xml_attr(value):
        return escape(str(value or ''), {'"': '&quot;'})

    def _classify_editable_string(text: str):
        lower = text.lower()
        if any(ext in lower for ext in EDITABLE_REF_EXTS):
            return 'texture-ref'
        if any(ext in lower for ext in MODEL_REF_EXTS):
            return 'model-ref'
        if any(tok in lower for tok in ('bone', 'spine', 'pelvis', 'head', 'neck', 'arm', 'leg', 'root', 'tail', 'finger')):
            return 'bone-name'
        if '/' in text or '\\' in text:
            return 'path'
        return 'string'

    def _scan_editable_strings(data: bytes, limit=900):
        rows = []
        for match in re.finditer(rb'[A-Za-z0-9_./:\\\-]{4,160}', data or b''):
            raw = match.group()
            text = raw.decode('latin-1', errors='ignore')
            group = _classify_editable_string(text)
            priority = {'texture-ref': 0, 'model-ref': 1, 'bone-name': 2, 'path': 3, 'string': 4}.get(group, 9)
            rows.append({'id': f's{len(rows):04d}', 'offset': int(match.start()), 'length': int(len(raw)), 'group': group, 'original': text, 'value': text, 'priority': priority})
        rows.sort(key=lambda r: (r['priority'], r['offset']))
        selected = rows[:limit]
        selected.sort(key=lambda r: r['offset'])
        for i, row in enumerate(selected):
            row['id'] = f's{i:04d}'
            row.pop('priority', None)
        return selected

    def _write_edit_text(path: Path, editable_strings):
        lines = [
            '# Code RED Model XML editable text sheet',
            '# Edit the value attributes in the XML for safest import.',
            '# This TXT file is also read on import for lines shaped exactly like:',
            '# replace OLD => NEW',
            '# Replacement text must be the same byte length or shorter; shorter values are NUL-padded.',
            '',
        ]
        for row in editable_strings[:500]:
            original = str(row.get('original', '')).replace('\\', '\\\\')
            lines.append(f'# {row.get("id")} offset={row.get("offset")} bytes={row.get("length")} group={row.get("group")}')
            lines.append(f'# replace {original} => {original}')
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    def __triplet_ok(x, y, z):
        vals = (x, y, z)
        if not all(math.isfinite(v) for v in vals):
            return False
        max_abs = max(abs(v) for v in vals)
        if max_abs <= 0.0001 or max_abs > 100000.0:
            return False
        if sum(1 for v in vals if abs(v) < 1.0e-20) >= 2:
            return False
        return True


    def _trim_points(points):
        if len(points) < 200:
            return points
        xs = sorted(p[0] for p in points)
        ys = sorted(p[1] for p in points)
        zs = sorted(p[2] for p in points)
        n = len(points)
        lo = max(0, int(n * 0.01))
        hi = min(n - 1, int(n * 0.99))
        bounds = ((xs[lo], xs[hi]), (ys[lo], ys[hi]), (zs[lo], zs[hi]))
        trimmed = [p for p in points if all(bounds[i][0] <= p[i] <= bounds[i][1] for i in range(3))]
        return trimmed if len(trimmed) >= 80 else points


    def _preview_points(points, limit=12000):
        if len(points) <= limit:
            return points
        step = max(1, len(points) // limit)
        return points[::step][:limit]


    def _heuristic_model_candidates(payload: bytes, limit=5, max_samples_per_layout=2500):
        """Fast vertex-stream detector for Model XML preview export."""
        candidates = []
        if not payload or len(payload) < 96:
            return candidates
        payload_len = len(payload)
        for stride in (12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56, 60, 64):
            for offset in range(0, min(stride, 64), 4):
                total_slots = max(0, (payload_len - 12 - offset) // stride)
                if total_slots < 80:
                    continue
                sample_step = max(1, total_slots // max_samples_per_layout)
                pts = []
                tested = 0
                valid = 0
                for slot in range(0, total_slots, sample_step):
                    pos = offset + slot * stride
                    try:
                        x, y, z = struct.unpack_from('<fff', payload, pos)
                    except Exception:
                        break
                    tested += 1
                    if _triplet_ok(x, y, z):
                        valid += 1
                        pts.append((float(x), float(y), float(z)))
                if len(pts) < 80 or tested <= 0:
                    continue
                valid_ratio = valid / max(1, tested)
                if valid_ratio < 0.025:
                    continue
                filtered = _trim_points(pts)
                xs = [p[0] for p in filtered]
                ys = [p[1] for p in filtered]
                zs = [p[2] for p in filtered]
                spans = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
                nonflat = sum(1 for span in spans if span > 0.05)
                if nonflat < 2:
                    continue
                unique_ratio = len({(round(a, 3), round(b, 3), round(c, 3)) for a, b, c in filtered}) / max(1, len(filtered))
                span_max = max(spans)
                span_penalty = 0.0 if span_max < 10000 else 0.75
                score = (
                    min(1.0, len(filtered) / 3000.0) * 2.2
                    + unique_ratio * 1.8
                    + valid_ratio * 1.2
                    + (nonflat / 3.0) * 0.8
                    - span_penalty
                )
                candidates.append({
                    'score': round(score, 3),
                    'stride': stride,
                    'offset': offset,
                    'count': int(total_slots),
                    'sampled': int(tested),
                    'filtered_count': len(filtered),
                    'unique_ratio': round(unique_ratio, 4),
                    'valid_ratio': round(valid_ratio, 4),
                    'sample_step': int(sample_step),
                    'extents': spans,
                    'bounds': ((min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))),
                    'points': _preview_points(filtered, 12000),
                })
        candidates.sort(key=lambda row: (row['score'], row['filtered_count'], row['unique_ratio']), reverse=True)
        return candidates[:limit]


    def _triangle_area_ok(a, b, c):
        ax, ay, az = a; bx, by, bz = b; cx, cy, cz = c
        ux, uy, uz = bx - ax, by - ay, bz - az
        vx, vy, vz = cx - ax, cy - ay, cz - az
        nx = uy * vz - uz * vy
        ny = uz * vx - ux * vz
        nz = ux * vy - uy * vx
        return (nx * nx + ny * ny + nz * nz) > 1.0e-12


    def _write_obj(path: Path, points, faces=False):
        with Path(path).open('w', encoding='utf-8') as f:
            f.write('# Code RED Model XML OBJ preview\n')
            f.write('# Generated from a detected float position stream.\n')
            f.write('# For edit safety, XML/raw-resource import remains the source of truth.\n')
            for x, y, z in points:
                f.write(f'v {x:.6f} {y:.6f} {z:.6f}\n')
            if faces:
                f.write('# Sequential preview faces follow; these are for viewing only unless verified against a real index stream.\n')
                usable = (len(points) // 3) * 3
                face_count = 0
                for i in range(0, usable, 3):
                    if _triangle_area_ok(points[i], points[i + 1], points[i + 2]):
                        f.write(f'f {i + 1} {i + 2} {i + 3}\n')
                        face_count += 1
                f.write(f'# preview_faces={face_count}\n')
            else:
                f.write('# point-cloud OBJ; use the tri_preview OBJ or the Code RED OBJ Viewer for easier viewing.\n')

    def _extract_embedded_texture_payloads(payload: bytes, textures_dir: Path, max_items=12):
        rows = []
        if not payload:
            return rows
        # PNG extraction is length-safe because IEND marks the end.
        png_sig = b'\x89PNG\r\n\x1a\n'
        for idx, match in enumerate(re.finditer(re.escape(png_sig), payload)):
            if len(rows) >= max_items:
                break
            end = payload.find(b'IEND', match.start())
            if end < 0:
                continue
            end += 8
            out = textures_dir / f'embedded_{idx:03d}.png'
            out.write_bytes(payload[match.start():end])
            rows.append({'kind': 'embedded_png', 'path': out.name, 'offset': match.start(), 'size': out.stat().st_size})
        # DDS size cannot always be trusted without full dictionary parsing, so split conservatively at next DDS or a safe cap.
        dds_positions = [m.start() for m in re.finditer(b'DDS ', payload)]
        for idx, pos in enumerate(dds_positions):
            if len(rows) >= max_items:
                break
            end = dds_positions[idx + 1] if idx + 1 < len(dds_positions) else min(len(payload), pos + 8 * 1024 * 1024)
            out = textures_dir / f'embedded_{idx:03d}.dds'
            out.write_bytes(payload[pos:end])
            meta = parse_dds_header(out.read_bytes()[:256]) if callable(parse_dds_header) else None
            rows.append({
                'kind': 'embedded_dds',
                'path': out.name,
                'offset': pos,
                'size': out.stat().st_size,
                'dds': meta or {},
            })
        return rows

    def _archive_companion_candidates(archive_path: Path, archive_entry: dict, refs: dict, limit=20):
        if not (archive_path and archive_entry and callable(parse_rpf6)):
            return []
        try:
            info = parse_rpf6(Path(archive_path))
        except Exception:
            info = None
        if not info:
            return []
        current_path = str(archive_entry.get('path') or archive_entry.get('name') or '')
        current_parent = str(Path(current_path).parent).lower()
        current_stem = Path(archive_entry.get('name') or current_path).stem.lower()
        ref_names = set()
        ref_stems = set()
        for ext, items in (refs or {}).items():
            if ext.lower() not in TEXTURE_EXTS:
                continue
            for item in items:
                ref_names.add(Path(item).name.lower())
                ref_stems.add(Path(item).stem.lower())
        rows = []
        for ent in info.get('entries', []):
            if ent.get('type') != 'file' or ent.get('index') == archive_entry.get('index'):
                continue
            ext = (ent.get('extension') or Path(ent.get('name', '')).suffix or '').lower()
            if ext not in TEXTURE_EXTS:
                continue
            ep = str(ent.get('path') or '').lower()
            en = str(ent.get('name') or '').lower()
            es = Path(en).stem.lower()
            score = 0
            reasons = []
            if en in ref_names or es in ref_stems:
                score += 300
                reasons.append('explicit-texture-ref')
            elif current_stem and (es == current_stem or es.startswith(current_stem + '_') or es.startswith(current_stem + '.')) and str(Path(ep).parent).lower() == current_parent:
                score += 120
                reasons.append('same-family-texture-name')
            else:
                continue
            if ext in {'.dds', '.png'}:
                score += 35
                reasons.append('direct-image')
            rows.append({'score': score, 'entry': ent, 'reasons': reasons})
        rows.sort(key=lambda r: (-r['score'], r['entry'].get('path', '')))
        return rows[:limit]

    def codered_export_modelxml_bundle(asset_path, archive_path=None, archive_entry=None, out_root=None, max_textures=24):
        """Export using the shared Model XML engine so the GUI and CLI stay identical."""
        asset_path = Path(asset_path)
        out_root = Path(out_root or (CODERED_APP_ROOT / 'exports' / 'modelxml_bundles'))
        out_root.mkdir(parents=True, exist_ok=True)
        data = read_bytes(asset_path) if callable(read_bytes) else asset_path.read_bytes()

        # Load the shared bundle engine by path. Keeping GUI export on the same code path
        # prevents the button workflow from drifting behind the command workflow.
        import importlib.util
        cli_path = Path(CODERED_APP_ROOT) / 'tools' / 'codered_modelxml_bundle_cli.py'
        spec = importlib.util.spec_from_file_location('codered_modelxml_bundle_cli_shared', cli_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f'Could not load Model XML bundle engine: {cli_path}')
        mod = importlib.util.module_from_spec(spec)
        sys.modules['codered_modelxml_bundle_cli_shared'] = mod
        spec.loader.exec_module(mod)

        archive_info = None
        archive_path_obj = Path(archive_path) if archive_path else None
        if archive_path_obj:
            try:
                archive_info = mod.parse_rpf6(archive_path_obj)
            except Exception:
                archive_info = None
        return mod.create_bundle(
            asset_path.name,
            data,
            out_root,
            archive_path=archive_path_obj,
            archive_entry=archive_entry,
            archive_info=archive_info,
            max_textures=max_textures,
            include_family=True,
        )

    # Expose helper for scripts/tests.
    g['codered_export_modelxml_bundle'] = codered_export_modelxml_bundle

    # Add an Export behavior to the Meshes module button.
    _prev_module_action = WorkbenchApp.module_action

    def _module_action_with_modelxml(self, module_name, action):
        if module_name in {'Meshes', 'World'} and action == 'Export':
            path = getattr(self, 'selected_path', None)
            if path and Path(path).is_file() and Path(path).suffix.lower() in MODEL_EXTS:
                try:
                    bundle, manifest = codered_export_modelxml_bundle(Path(path))
                    if hasattr(self, 'log'):
                        self.log(f'Model XML bundle exported: {bundle}')
                    if hasattr(self, '_show_result') and OperationResult:
                        self._show_result(OperationResult(True, 'Model XML bundle exported', f'Bundle written to:\n{bundle}\n\nXML: {Path(manifest["xml"]).name}\nOBJ: {Path(manifest["obj_preview"]).name if manifest.get("obj_preview") else "not generated"}\nIndexed OBJ: {Path(manifest["obj_indexed_preview"]).name if manifest.get("obj_indexed_preview") else "not generated"}\nFamily OBJ: {Path(manifest["obj_family_preview"]).name if manifest.get("obj_family_preview") else "not generated"}\nAssembly map: {Path(manifest["model_assembly_json"]).name if manifest.get("model_assembly_json") else "not generated"}\nLOD members: {len(manifest.get("model_family", []))}\nTexture refs: {sum(len(v) for v in manifest.get("texture_refs", {}).values())}\nTextures extracted/copied: {len(manifest.get("textures", []))}\nDecoded textures: {manifest.get("decoded_texture_count", 0)}'))
                    return
                except Exception as exc:
                    if hasattr(self, '_show_result') and OperationResult:
                        self._show_result(OperationResult(False, 'Model XML bundle export failed', str(exc)))
                    elif messagebox:
                        messagebox.showerror('Model XML bundle export failed', str(exc))
                    return
        return _prev_module_action(self, module_name, action)

    WorkbenchApp.module_action = _module_action_with_modelxml

    # Add a button to the model family dialog so archive-extracted entries can export with archive context.
    ModelFamilyDialog = g.get('ModelFamilyDialog')
    if ModelFamilyDialog is not None and tk is not None:
        _prev_model_init = ModelFamilyDialog.__init__

        def _model_init_with_modelxml(self, master, asset_path, archive_path=None, archive_entry=None, on_saved=None):
            _prev_model_init(self, master, asset_path, archive_path=archive_path, archive_entry=archive_entry, on_saved=on_saved)

            def _do_export():
                try:
                    bundle, manifest = codered_export_modelxml_bundle(Path(self.asset_path), archive_path=getattr(self, 'archive_path', None), archive_entry=getattr(self, 'archive_entry', None))
                    if hasattr(self.master_app, 'log'):
                        self.master_app.log(f'Model XML archive bundle exported: {bundle}')
                    if messagebox:
                        messagebox.showinfo(
                            'Model XML bundle exported',
                            f'Bundle written to:\n{bundle}\n\nXML: {Path(manifest["xml"]).name}\nOBJ: {Path(manifest["obj_preview"]).name if manifest.get("obj_preview") else "not generated"}\nIndexed OBJ: {Path(manifest["obj_indexed_preview"]).name if manifest.get("obj_indexed_preview") else "not generated"}\nFamily OBJ: {Path(manifest["obj_family_preview"]).name if manifest.get("obj_family_preview") else "not generated"}\nAssembly map: {Path(manifest["model_assembly_json"]).name if manifest.get("model_assembly_json") else "not generated"}\nLOD members: {len(manifest.get("model_family", []))}\nTexture refs: {sum(len(v) for v in manifest.get("texture_refs", {}).values())}\nTextures extracted/copied: {len(manifest.get("textures", []))}\nDecoded textures: {manifest.get("decoded_texture_count", 0)}',
                            parent=self,
                        )
                except Exception as exc:
                    if messagebox:
                        messagebox.showerror('Model XML bundle export failed', str(exc), parent=self)

            button_row = None
            for child in self.winfo_children():
                if isinstance(child, tk.Frame):
                    texts = [sub.cget('text') for sub in child.winfo_children() if isinstance(sub, tk.Button)]
                    if 'Open Current Bytes' in texts or 'Open Heuristic 3D Preview' in texts:
                        button_row = child
                        break
            if button_row is not None:
                close_btn = None
                for sub in button_row.winfo_children():
                    if isinstance(sub, tk.Button) and sub.cget('text') == 'Close':
                        close_btn = sub
                        break
                style_source = getattr(self, 'master_app', master)
                theme = getattr(style_source, 'theme', {'button': '#151515', 'fg': '#FFFFFF', 'accent': '#8B0000'})
                btn = tk.Button(button_row, text='Export Model XML Bundle', command=_do_export, bg=theme.get('accent', '#8B0000'), fg=theme.get('fg', '#FFFFFF'), relief='flat', padx=12, pady=7)
                if close_btn is not None:
                    btn.pack(side='left', padx=(8, 0), before=close_btn)
                else:
                    btn.pack(side='left', padx=(8, 0))

        ModelFamilyDialog.__init__ = _model_init_with_modelxml



    # --- Pass 21: Button-based Model XML import/readback workflow ---
    # Wraps the verified CLI import path in a GUI dialog so the user does not need to type commands.
    def _load_modelxml_import_tool():
        import importlib.util
        import sys
        tool_path = Path(CODERED_APP_ROOT) / 'tools' / 'codered_modelxml_bundle_import_cli.py'
        if not tool_path.exists():
            raise FileNotFoundError(f'Missing import tool: {tool_path}')
        tools_dir = str(tool_path.parent)
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
        spec = importlib.util.spec_from_file_location('codered_modelxml_bundle_import_cli_gui', tool_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f'Could not load import tool: {tool_path}')
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        return mod

    def _default_entry_query(asset_path=None, archive_entry=None):
        archive_entry = archive_entry or {}
        value = archive_entry.get('path') or archive_entry.get('name') or ''
        if value:
            return str(value)
        if asset_path:
            return Path(asset_path).stem
        return ''

    def _default_out_archive(archive_path, entry_query='modelxml_import'):
        archive_path = Path(archive_path) if archive_path else None
        safe_stem = _safe_filename(Path(str(entry_query or 'entry')).stem or 'entry')
        out_dir = Path(CODERED_APP_ROOT) / 'imports' / 'modelxml_roundtrip'
        out_dir.mkdir(parents=True, exist_ok=True)
        if archive_path:
            return out_dir / f'{archive_path.stem}__{safe_stem}_gui_import_copy{archive_path.suffix}'
        return out_dir / f'modelxml_{safe_stem}_gui_import_copy.rpf'

    def _report_to_text(result):
        try:
            import_result = result.get('import_result') or result
            archive_result = result.get('archive_import_result') or {}
            lines = []
            lines.append('Model XML Bundle Import Result')
            lines.append('=========================')
            lines.append('')
            lines.append(f"Import status: {import_result.get('status', '')}")
            lines.append(f"Imported file: {import_result.get('imported_file', '')}")
            lines.append(f"Byte-identical to bundle raw: {import_result.get('byte_identical_to_bundle_raw')}")
            lines.append(f"Payload identical to bundle payload: {import_result.get('payload_identical_to_bundle_payload')}")
            val = import_result.get('validation') or {}
            lines.append(f"Resource header read: {bool(val.get('resource'))}")
            lines.append(f"Texture refs found: {val.get('texture_ref_count', 0)}")
            lines.append(f"Heuristic streams found: {val.get('heuristic_stream_count', 0)}")
            xml_edits = import_result.get('xml_edits') or []
            text_edits = import_result.get('text_sheet_edits') or []
            reps = import_result.get('replacements') or []
            if xml_edits:
                lines.append('')
                lines.append('XML edits applied:')
                for row in xml_edits[:20]:
                    lines.append(f"- {row.get('id')} @ {row.get('offset')} | {row.get('old')} -> {row.get('new')} | padded={row.get('null_padded')}")
            if text_edits:
                lines.append('')
                lines.append('TXT edit-sheet replacements:')
                for row in text_edits[:20]:
                    lines.append(f"- {row.get('old')} -> {row.get('new')} | hits={row.get('hit_count')}")
            if reps:
                lines.append('')
                lines.append('Manual replacements:')
                for row in reps:
                    lines.append(f"- {row.get('old')} -> {row.get('new')} | hits={row.get('hit_count')} | offsets={row.get('hits')}")
            if archive_result:
                lines.append('')
                lines.append('Archive-copy readback:')
                lines.append(f"Archive status: {archive_result.get('status', '')}")
                lines.append(f"Archive copy: {archive_result.get('archive_copy', '')}")
                lines.append(f"Internal path: {archive_result.get('internal_path', '')}")
                lines.append(f"Reread matches imported: {archive_result.get('reread_matches_imported')}")
                lines.append(f"Resource header ok after reread: {archive_result.get('resource_header_ok_after_reread')}")
                lines.append(f"Report: {archive_result.get('report_path', '')}")
                if archive_result.get('reexport_proof_bundle'):
                    lines.append(f"Re-export proof bundle: {archive_result.get('reexport_proof_bundle')}")
            return '\n'.join(lines)
        except Exception:
            return json.dumps(result, indent=2, default=str)

    def codered_import_modelxml_bundle(bundle, out_root=None, mode='payload-sidecar', replacements=None, archive_path=None, entry_query=None, out_archive=None, reexport_proof=True):
        tool = _load_modelxml_import_tool()
        bundle = Path(bundle)
        out_root = Path(out_root) if out_root else Path(CODERED_APP_ROOT) / 'imports' / 'modelxml_roundtrip'
        repl = list(replacements or [])
        import_result = tool.build_imported_file(bundle, out_root, mode, repl)
        final = {'import_result': import_result}
        if archive_path:
            entry_query = entry_query or Path(import_result.get('source_raw_file') or '').name
            archive_result = tool.direct_slot_patch_archive_copy(
                Path(archive_path),
                entry_query,
                Path(import_result['imported_file']),
                out_archive=Path(out_archive) if out_archive else None,
                reexport_proof=bool(reexport_proof),
            )
            final['archive_import_result'] = archive_result
        return final

    g['codered_import_modelxml_bundle'] = codered_import_modelxml_bundle

    class ModelXMLImportDialog(tk.Toplevel):
        def __init__(self, master, bundle_path=None, archive_path=None, archive_entry=None, asset_path=None):
            super().__init__(master)
            self.master_app = getattr(master, 'master_app', master)
            self.asset_path = Path(asset_path) if asset_path else None
            self.archive_path = Path(archive_path) if archive_path else None
            self.archive_entry = archive_entry or {}
            self.last_result = None
            self.title('Code RED - Model XML Import / Readback')
            self.geometry('1120x760')
            self.minsize(900, 600)
            c = getattr(self.master_app, 'theme', {'bg': '#000000', 'panel': '#050505', 'fg': '#FFFFFF', 'button': '#151515', 'accent': '#8B0000'})
            self.theme = c
            self.configure(bg=c['bg'])

            root = tk.Frame(self, bg=c['bg'])
            root.pack(fill='both', expand=True, padx=12, pady=12)
            tk.Label(root, text='Model XML Bundle Import / Archive-Copy Verify', font=('SegoeUI', 15, 'bold'), bg=c['bg'], fg=c['fg'], anchor='w').pack(fill='x')
            tk.Label(root, text='Button workflow for editable XML/TXT imports, no-edit round trips, and same-size-safe texture/reference swaps. Source archives are copied; originals are not overwritten.', bg=c['bg'], fg=c['fg'], anchor='w', justify='left').pack(fill='x', pady=(4, 10))

            form = tk.Frame(root, bg=c['bg'])
            form.pack(fill='x')
            self.bundle_var = tk.StringVar(value=str(bundle_path or ''))
            self.archive_var = tk.StringVar(value=str(self.archive_path or ''))
            self.entry_var = tk.StringVar(value=_default_entry_query(self.asset_path, self.archive_entry))
            self.out_dir_var = tk.StringVar(value=str(Path(CODERED_APP_ROOT) / 'imports' / 'modelxml_roundtrip'))
            self.out_archive_var = tk.StringVar(value=str(_default_out_archive(self.archive_path, self.entry_var.get())) if self.archive_path else '')
            self.mode_var = tk.StringVar(value='raw-clone')
            self.old_var = tk.StringVar(value='')
            self.new_var = tk.StringVar(value='')
            self.reexport_var = tk.BooleanVar(value=True)

            def row(label, var, browse=None):
                line = tk.Frame(form, bg=c['bg'])
                line.pack(fill='x', pady=4)
                tk.Label(line, text=label, width=22, anchor='w', bg=c['bg'], fg=c['fg']).pack(side='left')
                ent = tk.Entry(line, textvariable=var, bg=c['panel'], fg=c['fg'], insertbackground=c['fg'], relief='flat')
                ent.pack(side='left', fill='x', expand=True, ipady=6)
                if browse:
                    tk.Button(line, text='Browse', command=browse, bg=c['button'], fg=c['fg'], relief='flat', padx=10, pady=6).pack(side='left', padx=(8, 0))
                return ent

            row('Bundle folder', self.bundle_var, self.browse_bundle)
            row('Source archive .rpf', self.archive_var, self.browse_archive)
            row('Archive entry search', self.entry_var, None)
            row('Output folder', self.out_dir_var, self.browse_out_dir)
            row('Patched archive copy', self.out_archive_var, self.browse_out_archive)

            options = tk.Frame(form, bg=c['bg'])
            options.pack(fill='x', pady=(6, 4))
            tk.Label(options, text='Import mode', width=22, anchor='w', bg=c['bg'], fg=c['fg']).pack(side='left')
            for text, value in [('Raw clone / safest for archive copy', 'raw-clone'), ('Payload sidecar rebuild / analysis only', 'payload-sidecar')]:
                tk.Radiobutton(options, text=text, variable=self.mode_var, value=value, bg=c['bg'], fg=c['fg'], selectcolor=c['panel'], activebackground=c['bg'], activeforeground=c['fg']).pack(side='left', padx=(0, 14))
            tk.Checkbutton(options, text='Re-export proof after archive import', variable=self.reexport_var, bg=c['bg'], fg=c['fg'], selectcolor=c['panel'], activebackground=c['bg'], activeforeground=c['fg']).pack(side='left')

            repl = tk.LabelFrame(form, text='Optional same-size-safe texture/reference swap', bg=c['bg'], fg=c['fg'], padx=8, pady=8)
            repl.pack(fill='x', pady=(6, 8))
            r1 = tk.Frame(repl, bg=c['bg'])
            r1.pack(fill='x')
            tk.Label(r1, text='Old text', width=12, anchor='w', bg=c['bg'], fg=c['fg']).pack(side='left')
            tk.Entry(r1, textvariable=self.old_var, bg=c['panel'], fg=c['fg'], insertbackground=c['fg'], relief='flat').pack(side='left', fill='x', expand=True, ipady=6)
            tk.Label(r1, text='New text', width=12, anchor='w', bg=c['bg'], fg=c['fg']).pack(side='left', padx=(8, 0))
            tk.Entry(r1, textvariable=self.new_var, bg=c['panel'], fg=c['fg'], insertbackground=c['fg'], relief='flat').pack(side='left', fill='x', expand=True, ipady=6)
            self.repl_status = tk.StringVar(value='Leave both blank to import XML/TXT edits only. Manual swaps must be the same byte length or shorter.')
            tk.Label(repl, textvariable=self.repl_status, anchor='w', bg=c['bg'], fg='#D8D8D8').pack(fill='x', pady=(6, 0))
            self.old_var.trace_add('write', lambda *_: self._update_repl_status())
            self.new_var.trace_add('write', lambda *_: self._update_repl_status())

            btns = tk.Frame(root, bg=c['bg'])
            btns.pack(fill='x', pady=(4, 8))
            tk.Button(btns, text='Build Imported File Only', command=self.run_import_only, bg=c['accent'], fg=c['fg'], relief='flat', padx=12, pady=8).pack(side='left')
            tk.Button(btns, text='Import Into Archive Copy + Verify', command=self.run_archive_verify, bg=c['accent'], fg=c['fg'], relief='flat', padx=12, pady=8).pack(side='left', padx=(8, 0))
            tk.Button(btns, text='Open Output Folder', command=self.open_output_folder, bg=c['button'], fg=c['fg'], relief='flat', padx=12, pady=8).pack(side='left', padx=(8, 0))
            tk.Button(btns, text='Close', command=self.destroy, bg=c['button'], fg=c['fg'], relief='flat', padx=12, pady=8).pack(side='right')

            self.result_text = tk.Text(root, wrap='word', bg=c['panel'], fg=c['fg'], insertbackground=c['fg'], relief='flat')
            self.result_text.pack(fill='both', expand=True)
            self._write_result('Ready. Export a Model XML bundle, edit the .modelxml.xml value fields or the .model_edits.txt replace lines, then use Build Imported File Only or Import Into Archive Copy + Verify.\n\nFor canoe files, first export the canoe WFT/WFD/WVD bundle, keep Raw clone selected, run a no-edit archive-copy verify, then edit only same-size-safe string/reference fields.')

        def _write_result(self, text):
            self.result_text.configure(state='normal')
            self.result_text.delete('1.0', 'end')
            self.result_text.insert('1.0', text)
            self.result_text.configure(state='disabled')

        def _update_repl_status(self):
            old = self.old_var.get()
            new = self.new_var.get()
            if not old and not new:
                self.repl_status.set('Leave both blank to import XML/TXT edits only. Manual swaps must be the same byte length or shorter.')
                return
            lo = len(old.encode('latin-1', errors='ignore'))
            ln = len(new.encode('latin-1', errors='ignore'))
            state = 'OK' if 0 < ln <= lo else 'BLOCKED'
            self.repl_status.set(f'{state}: old={lo} bytes, new={ln} bytes. New text must be the same length or shorter; shorter values are NUL-padded.')

        def browse_bundle(self):
            p = filedialog.askdirectory(parent=self, title='Select ModelXML export bundle folder')
            if p:
                self.bundle_var.set(p)

        def browse_archive(self):
            p = filedialog.askopenfilename(parent=self, title='Select source RPF archive', filetypes=[('RPF archives', '*.rpf'), ('All files', '*.*')])
            if p:
                self.archive_var.set(p)
                if not self.out_archive_var.get():
                    self.out_archive_var.set(str(_default_out_archive(Path(p), self.entry_var.get())))

        def browse_out_dir(self):
            p = filedialog.askdirectory(parent=self, title='Select output folder')
            if p:
                self.out_dir_var.set(p)

        def browse_out_archive(self):
            initial = self.out_archive_var.get() or str(_default_out_archive(self.archive_var.get(), self.entry_var.get()))
            p = filedialog.asksaveasfilename(parent=self, title='Save patched archive copy as', defaultextension='.rpf', initialfile=Path(initial).name, initialdir=str(Path(initial).parent), filetypes=[('RPF archives', '*.rpf'), ('All files', '*.*')])
            if p:
                self.out_archive_var.set(p)

        def _replacement_pairs(self):
            old = self.old_var.get()
            new = self.new_var.get()
            if not old and not new:
                return []
            if not old or not new:
                raise ValueError('Both old text and new text are required for a replacement, or leave both blank.')
            if len(new.encode('latin-1')) > len(old.encode('latin-1')):
                raise ValueError('Replacement blocked: new text must be the same byte length or shorter than old text.')
            return [(old, new)]

        def _common_args(self, include_archive=False):
            bundle = Path(self.bundle_var.get())
            if not bundle.exists():
                raise FileNotFoundError(f'Bundle folder does not exist: {bundle}')
            out_root = Path(self.out_dir_var.get() or (Path(CODERED_APP_ROOT) / 'imports' / 'modelxml_roundtrip'))
            args = {
                'bundle': bundle,
                'out_root': out_root,
                'mode': self.mode_var.get(),
                'replacements': self._replacement_pairs(),
            }
            if include_archive:
                archive = Path(self.archive_var.get())
                if not archive.exists():
                    raise FileNotFoundError(f'Archive does not exist: {archive}')
                entry = self.entry_var.get().strip()
                if not entry:
                    raise ValueError('Archive entry search is required for archive-copy import.')
                out_archive_text = self.out_archive_var.get().strip()
                args.update({
                    'archive_path': archive,
                    'entry_query': entry,
                    'out_archive': Path(out_archive_text) if out_archive_text else _default_out_archive(archive, entry),
                    'reexport_proof': self.reexport_var.get(),
                })
            return args

        def run_import_only(self):
            try:
                result = codered_import_modelxml_bundle(**self._common_args(include_archive=False))
                self.last_result = result
                self._write_result(_report_to_text(result))
                if hasattr(self.master_app, 'log'):
                    self.master_app.log('Model XML imported file built from bundle.')
            except Exception as exc:
                self._write_result('Import failed:\n\n' + str(exc))
                messagebox.showerror('Model XML import failed', str(exc), parent=self)

        def run_archive_verify(self):
            try:
                result = codered_import_modelxml_bundle(**self._common_args(include_archive=True))
                self.last_result = result
                text = _report_to_text(result)
                self._write_result(text)
                ok = bool((result.get('archive_import_result') or {}).get('reread_matches_imported'))
                if hasattr(self.master_app, 'log'):
                    self.master_app.log('Model XML archive-copy import verified.' if ok else 'Model XML archive-copy import completed with warnings.')
                messagebox.showinfo('Archive-copy verify complete' if ok else 'Archive-copy verify finished', text[:3000], parent=self)
            except Exception as exc:
                self._write_result('Archive-copy import failed:\n\n' + str(exc))
                messagebox.showerror('Archive-copy import failed', str(exc), parent=self)

        def open_output_folder(self):
            try:
                import os
                import subprocess
                import sys
                p = Path(self.out_dir_var.get() or (Path(CODERED_APP_ROOT) / 'imports' / 'modelxml_roundtrip'))
                p.mkdir(parents=True, exist_ok=True)
                if sys.platform.startswith('win'):
                    os.startfile(str(p))
                elif sys.platform == 'darwin':
                    subprocess.Popen(['open', str(p)])
                else:
                    subprocess.Popen(['xdg-open', str(p)])
            except Exception as exc:
                messagebox.showerror('Open folder failed', str(exc), parent=self)

    def _open_modelxml_import_dialog(self):
        ModelXMLImportDialog(self)

    try:
        setattr(WorkbenchApp, 'open_modelxml_import_dialog', _open_modelxml_import_dialog)
    except Exception:
        pass

    # Add import buttons to model family dialogs. This is the main no-command path.
    ModelFamilyDialog = g.get('ModelFamilyDialog')
    if ModelFamilyDialog is not None and tk is not None:
        _prev_import_model_init = ModelFamilyDialog.__init__

        def _model_init_with_modelxml_import(self, master, asset_path, archive_path=None, archive_entry=None, on_saved=None):
            _prev_import_model_init(self, master, asset_path, archive_path=archive_path, archive_entry=archive_entry, on_saved=on_saved)

            def _open_import_lab(bundle_path=None):
                ModelXMLImportDialog(self, bundle_path=bundle_path, archive_path=getattr(self, 'archive_path', None), archive_entry=getattr(self, 'archive_entry', None), asset_path=getattr(self, 'asset_path', None))

            def _roundtrip_verify_current():
                try:
                    if not getattr(self, 'archive_path', None):
                        messagebox.showinfo('Archive context needed', 'Open this model from inside an RPF archive first, then use Round-trip Verify Copy.', parent=self)
                        return
                    bundle, manifest = codered_export_modelxml_bundle(Path(self.asset_path), archive_path=getattr(self, 'archive_path', None), archive_entry=getattr(self, 'archive_entry', None))
                    entry = _default_entry_query(getattr(self, 'asset_path', None), getattr(self, 'archive_entry', None))
                    result = codered_import_modelxml_bundle(
                        bundle=bundle,
                        out_root=Path(CODERED_APP_ROOT) / 'imports' / 'modelxml_roundtrip',
                        mode='raw-clone',
                        replacements=[],
                        archive_path=Path(self.archive_path),
                        entry_query=entry,
                        out_archive=_default_out_archive(Path(self.archive_path), entry),
                        reexport_proof=True,
                    )
                    text = _report_to_text(result)
                    if hasattr(self.master_app, 'log'):
                        self.master_app.log(f'Model XML round-trip verify copy complete: {bundle}')
                    messagebox.showinfo('Round-trip verify complete', text[:3000], parent=self)
                    dlg = ModelXMLImportDialog(self, bundle_path=bundle, archive_path=getattr(self, 'archive_path', None), archive_entry=getattr(self, 'archive_entry', None), asset_path=getattr(self, 'asset_path', None))
                    dlg._write_result(text)
                except Exception as exc:
                    messagebox.showerror('Round-trip verify failed', str(exc), parent=self)

            button_row = None
            for child in self.winfo_children():
                if isinstance(child, tk.Frame):
                    texts = [sub.cget('text') for sub in child.winfo_children() if isinstance(sub, tk.Button)]
                    if 'Open Current Bytes' in texts or 'Export Model XML Bundle' in texts:
                        button_row = child
                        break
            if button_row is not None:
                close_btn = None
                for sub in button_row.winfo_children():
                    if isinstance(sub, tk.Button) and sub.cget('text') == 'Close':
                        close_btn = sub
                        break
                style_source = getattr(self, 'master_app', master)
                theme = getattr(style_source, 'theme', {'button': '#151515', 'fg': '#FFFFFF', 'accent': '#8B0000'})
                buttons = [
                    ('Import Model XML Bundle', lambda: _open_import_lab(None), theme.get('button', '#151515')),
                    ('Round-trip Verify Copy', _roundtrip_verify_current, theme.get('accent', '#8B0000')),
                ]
                for label, cmd, color in buttons:
                    btn = tk.Button(button_row, text=label, command=cmd, bg=color, fg=theme.get('fg', '#FFFFFF'), relief='flat', padx=12, pady=7)
                    if close_btn is not None:
                        btn.pack(side='left', padx=(8, 0), before=close_btn)
                    else:
                        btn.pack(side='left', padx=(8, 0))

        ModelFamilyDialog.__init__ = _model_init_with_modelxml_import




    # Add Model XML bundle buttons directly to the RPF Archive Browser as well.
    ArchiveBrowserDialog = g.get('ArchiveBrowserDialog')
    if ArchiveBrowserDialog is not None and tk is not None:
        _prev_archive_browser_init = ArchiveBrowserDialog.__init__

        def _archive_browser_init_with_modelxml(self, master, archive_path, info):
            _prev_archive_browser_init(self, master, archive_path, info)
            c = getattr(master, 'theme', {'bg': '#000000', 'button': '#151515', 'fg': '#FFFFFF', 'accent': '#8B0000'})
            button_row = None
            for child in self.winfo_children():
                if isinstance(child, tk.Frame):
                    texts = [sub.cget('text') for sub in child.winfo_children() if isinstance(sub, tk.Button)]
                    if 'Inspect Routed' in texts and 'Extract Selected' in texts:
                        button_row = child
                        break
            if button_row is None:
                return
            close_btn = None
            for sub in button_row.winfo_children():
                if isinstance(sub, tk.Button) and sub.cget('text') == 'Close':
                    close_btn = sub
                    break

            def _selected_model_entry():
                ent = self._selected_entry()
                if not ent:
                    return None
                if ent.get('type') != 'file':
                    messagebox.showinfo('Directory selected', 'Select a model/resource file entry first.', parent=self)
                    return None
                suffix = Path(ent.get('name', '')).suffix.lower()
                if suffix not in MODEL_EXTS:
                    messagebox.showinfo('Not a model entry', f'Select a WFT/WFD/WVD-style entry first.\n\nSelected suffix: {suffix or "(none)"}', parent=self)
                    return None
                return ent

            def _extract_model_entry(ent):
                data = extract_rpf_entry(self.archive_path, ent)
                temp_dir = Path(tempfile.mkdtemp(prefix='codered_modelxml_archive_'))
                temp_path = temp_dir / (Path(ent.get('name', '')).name or f"entry_{ent.get('index', 0)}.bin")
                temp_path.write_bytes(data)
                return temp_path

            def _export_selected_bundle():
                try:
                    ent = _selected_model_entry()
                    if not ent:
                        return
                    temp_path = _extract_model_entry(ent)
                    bundle, manifest = codered_export_modelxml_bundle(temp_path, archive_path=self.archive_path, archive_entry=ent)
                    if hasattr(self.master_app, 'log'):
                        self.master_app.log(f'Model XML bundle exported from archive browser: {bundle}')
                    messagebox.showinfo(
                        'Model XML bundle exported',
                        f'Bundle written to:\n{bundle}\n\nXML: {Path(manifest["xml"]).name}\nOBJ: {Path(manifest["obj_preview"]).name if manifest.get("obj_preview") else "not generated"}\nIndexed OBJ: {Path(manifest["obj_indexed_preview"]).name if manifest.get("obj_indexed_preview") else "not generated"}\nFamily OBJ: {Path(manifest["obj_family_preview"]).name if manifest.get("obj_family_preview") else "not generated"}\nAssembly map: {Path(manifest["model_assembly_json"]).name if manifest.get("model_assembly_json") else "not generated"}\nLOD members: {len(manifest.get("model_family", []))}\nTexture refs: {sum(len(v) for v in manifest.get("texture_refs", {}).values())}\nTextures extracted/copied: {len(manifest.get("textures", []))}\nDecoded textures: {manifest.get("decoded_texture_count", 0)}',
                        parent=self,
                    )
                except Exception as exc:
                    messagebox.showerror('ModelXML export failed', str(exc), parent=self)

            def _import_bundle_for_selected():
                ent = _selected_model_entry()
                if not ent:
                    return
                ModelXMLImportDialog(self, archive_path=self.archive_path, archive_entry=ent, asset_path=Path(ent.get('name', '') or 'asset.wvd'))

            def _roundtrip_selected():
                try:
                    ent = _selected_model_entry()
                    if not ent:
                        return
                    temp_path = _extract_model_entry(ent)
                    bundle, manifest = codered_export_modelxml_bundle(temp_path, archive_path=self.archive_path, archive_entry=ent)
                    entry = _default_entry_query(temp_path, ent)
                    result = codered_import_modelxml_bundle(
                        bundle=bundle,
                        out_root=Path(CODERED_APP_ROOT) / 'imports' / 'modelxml_roundtrip',
                        mode='raw-clone',
                        replacements=[],
                        archive_path=self.archive_path,
                        entry_query=entry,
                        out_archive=_default_out_archive(self.archive_path, entry),
                        reexport_proof=True,
                    )
                    text = _report_to_text(result)
                    if hasattr(self.master_app, 'log'):
                        self.master_app.log(f'Model XML archive-browser round-trip verify complete: {entry}')
                    messagebox.showinfo('Round-trip verify complete', text[:3000], parent=self)
                    dlg = ModelXMLImportDialog(self, bundle_path=bundle, archive_path=self.archive_path, archive_entry=ent, asset_path=temp_path)
                    dlg._write_result(text)
                except Exception as exc:
                    messagebox.showerror('Round-trip verify failed', str(exc), parent=self)

            for label, cmd, color in [
                ('Export Model XML Bundle', _export_selected_bundle, c.get('accent', '#8B0000')),
                ('Import Model XML Bundle', _import_bundle_for_selected, c.get('button', '#151515')),
                ('Round-trip Verify', _roundtrip_selected, c.get('accent', '#8B0000')),
            ]:
                btn = tk.Button(button_row, text=label, command=cmd, bg=color, fg=c.get('fg', '#FFFFFF'), relief='flat', padx=12, pady=7)
                if close_btn is not None:
                    btn.pack(side='left', padx=(0, 8), before=close_btn)
                else:
                    btn.pack(side='left', padx=(0, 8))

        ArchiveBrowserDialog.__init__ = _archive_browser_init_with_modelxml


    # Add visible capability status to the Meshes module.
    meshes = MODULE_BY_NAME.get('Meshes') if isinstance(MODULE_BY_NAME, dict) else None
    if meshes is not None:
        try:
            meshes.summary = str(getattr(meshes, 'summary', '')) + ' Model XML/texture export bundles are available.'
            cap_cls = g.get('FormatCapability')
            if cap_cls:
                meshes.capabilities.append(cap_cls('.modelxml.xml', 'Meshes', 'X/P', 'Code RED Model XML sidecar export: XML manifest, assembly map, raw payload, texture refs/extracts, and OBJ/indexed-preview files.'))
        except Exception:
            pass
