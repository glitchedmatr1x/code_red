from __future__ import annotations

# Code RED Pass 19: CodeX-style WFT/WFD/WVD export bundle patch.
# Adds a safe export path: model resource -> XML sidecar + raw payload + texture refs/extracts + heuristic OBJ preview.
# This does not claim full rebuild/import parity yet.

def apply(WorkbenchApp, g):
    import json
    import math
    import re
    import shutil
    import struct
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
    TEXTURE_EXTS = {'.dds', '.png', '.wtd', '.wtx', '.wsf', '.xtd', '.xtx', '.xsf', '.wtb'}

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

    def _triplet_ok(x, y, z):
        vals = (x, y, z)
        if not all(math.isfinite(v) for v in vals):
            return False
        if max(abs(v) for v in vals) > 100000.0:
            return False
        if max(abs(v) for v in vals) <= 0.0001:
            return False
        if sum(1 for v in vals if 0.0 < abs(v) < 1e-20) >= 2:
            return False
        return True

    def _heuristic_model_candidates(payload: bytes, limit=5):
        native = g.get('_codered_heuristic_model_candidates')
        # The native helper needs a path, so this fallback works directly from payload bytes for exported bundles.
        candidates = []
        if not payload or len(payload) < 64:
            return candidates
        for stride in (12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56, 60, 64):
            for offset in range(0, min(stride, 64), 4):
                pts = []
                suspicious = 0
                for pos in range(offset, len(payload) - 12, stride):
                    try:
                        x, y, z = struct.unpack_from('<fff', payload, pos)
                    except Exception:
                        break
                    if _triplet_ok(x, y, z):
                        pts.append((float(x), float(y), float(z)))
                    else:
                        suspicious += 1
                if len(pts) < 80:
                    continue
                filtered = pts
                if len(pts) >= 200:
                    xs = sorted(p[0] for p in pts)
                    ys = sorted(p[1] for p in pts)
                    zs = sorted(p[2] for p in pts)
                    n = len(pts)
                    lo = max(0, int(n * 0.01))
                    hi = min(n - 1, int(n * 0.99))
                    bounds = ((xs[lo], xs[hi]), (ys[lo], ys[hi]), (zs[lo], zs[hi]))
                    trial = [p for p in pts if all(bounds[i][0] <= p[i] <= bounds[i][1] for i in range(3))]
                    if len(trial) >= 80:
                        filtered = trial
                xs = [p[0] for p in filtered]
                ys = [p[1] for p in filtered]
                zs = [p[2] for p in filtered]
                spans = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
                nonflat_axes = sum(1 for span in spans if span > 0.05)
                if nonflat_axes < 2:
                    continue
                unique_ratio = len({(round(a, 3), round(b, 3), round(c, 3)) for a, b, c in filtered}) / max(1, len(filtered))
                suspicious_ratio = suspicious / max(1, suspicious + len(pts))
                filtered_ratio = len(filtered) / max(1, len(pts))
                score = (
                    min(1.0, len(filtered) / 3000.0) * 2.5
                    + unique_ratio * 1.8
                    + (nonflat_axes / 3.0) * 0.8
                    + filtered_ratio * 0.9
                    + (1.0 - suspicious_ratio) * 0.8
                )
                candidates.append({
                    'score': round(score, 3),
                    'stride': stride,
                    'offset': offset,
                    'count': len(pts),
                    'filtered_count': len(filtered),
                    'unique_ratio': round(unique_ratio, 4),
                    'suspicious_ratio': round(suspicious_ratio, 4),
                    'filtered_ratio': round(filtered_ratio, 4),
                    'extents': spans,
                    'bounds': ((min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))),
                    'points': filtered[:12000],
                })
        candidates.sort(key=lambda row: (row['score'], row['filtered_count'], row['unique_ratio']), reverse=True)
        return candidates[:limit]

    def _write_obj(path: Path, points):
        with Path(path).open('w', encoding='utf-8') as f:
            f.write('# Code RED heuristic OBJ preview\n')
            f.write('# Vertex positions are guessed from float streams. Faces/topology are intentionally not invented.\n')
            for x, y, z in points:
                f.write(f'v {x:.6f} {y:.6f} {z:.6f}\n')
            f.write('# point-cloud only; topology decode/rebuild remains pending.\n')

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
        ref_tokens = set()
        for items in (refs or {}).values():
            for item in items:
                ref_tokens.add(Path(item).name.lower())
                ref_tokens.add(Path(item).stem.lower())
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
            if str(Path(ep).parent).lower() == current_parent:
                score += 70
                reasons.append('same-parent')
            if en in ref_tokens or es in ref_tokens:
                score += 260
                reasons.append('texture-ref-match')
            if current_stem and (current_stem in es or es in current_stem):
                score += 90
                reasons.append('family-stem-overlap')
            if ext in {'.dds', '.png'}:
                score += 35
                reasons.append('image-ext')
            if score > 0:
                rows.append({'score': score, 'entry': ent, 'reasons': reasons})
        rows.sort(key=lambda r: (-r['score'], r['entry'].get('path', '')))
        return rows[:limit]

    def codered_export_codex_bundle(asset_path, archive_path=None, archive_entry=None, out_root=None, max_textures=16):
        asset_path = Path(asset_path)
        data = read_bytes(asset_path) if callable(read_bytes) else asset_path.read_bytes()
        out_root = Path(out_root) if out_root else Path(CODERED_APP_ROOT) / 'exports' / 'codex_bundles'
        out_root.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime('%Y%m%d_%H%M%S')
        stem = asset_path.stem or 'asset'
        bundle = out_root / f'{_safe_filename(stem)}_codex_bundle_{stamp}'
        textures_dir = bundle / 'textures'
        sidecars_dir = bundle / 'sidecars'
        textures_dir.mkdir(parents=True, exist_ok=True)
        sidecars_dir.mkdir(parents=True, exist_ok=True)

        raw_copy = bundle / _safe_filename(asset_path.name)
        raw_copy.write_bytes(data)

        resource = parse_resource_header(data) if callable(parse_resource_header) else None
        payload_info = extract_resource_payload(data, resource) if callable(extract_resource_payload) else {'payload': data, 'notes': ['No host resource decoder available.']}
        payload = payload_info.get('payload') or data
        payload_path = sidecars_dir / f'{_safe_filename(asset_path.name)}.payload.bin'
        payload_path.write_bytes(payload)

        strings, refs, bone_hints = _scan_refs(payload)
        streams = _heuristic_model_candidates(payload, limit=5)

        obj_path = None
        if streams:
            obj_path = bundle / f'{_safe_filename(stem)}_preview.obj'
            _write_obj(obj_path, streams[0]['points'])

        texture_rows = []
        for row in _extract_embedded_texture_payloads(payload, textures_dir, max_items=max_textures):
            texture_rows.append(row)

        companion_rows = _archive_companion_candidates(Path(archive_path) if archive_path else None, archive_entry or {}, refs, limit=max_textures)
        for row in companion_rows:
            if len(texture_rows) >= max_textures:
                break
            ent = row['entry']
            try:
                companion_data = extract_rpf_entry(Path(archive_path), ent) if callable(extract_rpf_entry) else b''
            except Exception as exc:
                texture_rows.append({
                    'kind': 'archive_companion_failed',
                    'archive_path': ent.get('path', ''),
                    'score': row['score'],
                    'error': str(exc),
                    'size': 0,
                })
                continue
            name = _safe_filename(ent.get('name') or f'entry_{ent.get("index", 0)}.bin')
            out = textures_dir / name
            if out.exists():
                out = textures_dir / f'{ent.get("index", 0):04d}_{name}'
            out.write_bytes(companion_data)
            texture_rows.append({
                'kind': 'archive_companion',
                'path': out.name,
                'archive_path': ent.get('path', ''),
                'score': row['score'],
                'reasons': row['reasons'],
                'size': len(companion_data),
            })

        stream_manifest = []
        for row in streams:
            clean = {k: v for k, v in row.items() if k != 'points'}
            stream_manifest.append(clean)

        xml_lines = ['<?xml version="1.0" encoding="utf-8"?>', '<CodeREDCodeXBundle version="pass19">']
        xml_lines.append(f'  <Source name="{escape(asset_path.name)}" archive="{escape(str(archive_path or ""))}" internalPath="{escape(str((archive_entry or {}).get("path", "")))}" />')
        if resource:
            xml_lines.append(
                f'  <Resource ident="{resource.get("ident_name", "")}" rawIdent="{resource.get("raw_ident_name", "")}" '
                f'resourceType="{resource.get("resource_type", 0)}" flag1="0x{int(resource.get("flag1", 0)):08X}" '
                f'flag2="0x{int(resource.get("flag2", 0)):08X}" totalSize="{int(resource.get("total_size", 0))}" />'
            )
        xml_lines.append(f'  <Payload bytes="{len(payload)}" sidecar="sidecars/{escape(payload_path.name)}" />')
        xml_lines.append('  <TextureRefs>')
        for ext, items in refs.items():
            for item in items[:80]:
                xml_lines.append(f'    <Ref ext="{escape(ext)}">{escape(item)}</Ref>')
        xml_lines.append('  </TextureRefs>')
        xml_lines.append('  <BoneHints>')
        for item in bone_hints[:120]:
            xml_lines.append(f'    <Bone>{escape(item)}</Bone>')
        xml_lines.append('  </BoneHints>')
        xml_lines.append('  <HeuristicStreams>')
        for row in stream_manifest:
            extents = row.get('extents') or (0, 0, 0)
            xml_lines.append(
                f'    <Stream score="{row.get("score", 0)}" stride="{row.get("stride", 0)}" offset="{row.get("offset", 0)}" '
                f'points="{row.get("count", 0)}" filtered="{row.get("filtered_count", 0)}" '
                f'extents="{float(extents[0]):.6g},{float(extents[1]):.6g},{float(extents[2]):.6g}" />'
            )
        xml_lines.append('  </HeuristicStreams>')
        xml_lines.append('  <Textures>')
        for row in texture_rows:
            xml_lines.append(f'    <Texture kind="{escape(str(row.get("kind", "")))}" path="{escape(str(row.get("path", "")))}" size="{int(row.get("size", 0) or 0)}" />')
        xml_lines.append('  </Textures>')
        xml_lines.append('</CodeREDCodeXBundle>')
        xml_path = bundle / f'{_safe_filename(stem)}.codex.xml'
        xml_path.write_text('\n'.join(xml_lines) + '\n', encoding='utf-8')

        manifest = {
            'version': 'pass19-codex-bundle',
            'asset_path': str(asset_path),
            'asset_name': asset_path.name,
            'archive': str(archive_path or ''),
            'internal_path': str((archive_entry or {}).get('path', '')),
            'raw_bytes': len(data),
            'payload_bytes': len(payload),
            'resource': resource,
            'payload_notes': payload_info.get('notes', []),
            'xml': str(xml_path),
            'obj_preview': str(obj_path) if obj_path else '',
            'texture_refs': refs,
            'bone_hints': bone_hints,
            'heuristic_streams': stream_manifest,
            'textures': texture_rows,
            'warnings': [
                'Export bundle is safe/read-only against the source archive.',
                'XML is CodeX-style bridge data, not yet a guaranteed native CodeX round-trip XML.',
                'OBJ preview is a guessed point cloud until dictionary-aware topology decoding is complete.',
            ],
        }
        manifest_path = bundle / 'manifest.json'
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        report_path = bundle / 'extraction_report.txt'
        report_lines = [
            'Code RED CodeX-style Export Bundle',
            '==================================',
            '',
            f'Asset: {asset_path.name}',
            f'Archive: {archive_path or ""}',
            f'Internal path: {(archive_entry or {}).get("path", "")}',
            f'Raw bytes: {len(data):,}',
            f'Payload bytes: {len(payload):,}',
            f'XML: {xml_path.name}',
            f'OBJ preview: {obj_path.name if obj_path else "not generated"}',
            f'Texture refs: {sum(len(v) for v in refs.values())}',
            f'Texture files copied/extracted: {len(texture_rows)}',
            f'Heuristic streams: {len(stream_manifest)}',
            '',
            'Payload notes:',
        ]
        report_lines.extend(f'- {line}' for line in payload_info.get('notes', []))
        report_lines.extend([
            '',
            'Limitations:',
            '- This is an extraction/inspection bridge, not a full WFT/WFD/WVD rebuild importer yet.',
            '- It keeps source archives untouched.',
            '- It writes XML, raw payload, texture refs/extracts, and an OBJ point-cloud preview when float streams are plausible.',
        ])
        report_path.write_text('\n'.join(report_lines) + '\n', encoding='utf-8')
        return bundle, manifest

    # Expose helper for scripts/tests.
    g['codered_export_codex_bundle'] = codered_export_codex_bundle

    # Add an Export behavior to the Meshes module button.
    _prev_module_action = WorkbenchApp.module_action

    def _module_action_with_codex(self, module_name, action):
        if module_name in {'Meshes', 'World'} and action == 'Export':
            path = getattr(self, 'selected_path', None)
            if path and Path(path).is_file() and Path(path).suffix.lower() in MODEL_EXTS:
                try:
                    bundle, manifest = codered_export_codex_bundle(Path(path))
                    if hasattr(self, 'log'):
                        self.log(f'CodeX-style bundle exported: {bundle}')
                    if hasattr(self, '_show_result') and OperationResult:
                        self._show_result(OperationResult(True, 'CodeX bundle exported', f'Bundle written to:\n{bundle}\n\nXML: {Path(manifest["xml"]).name}\nOBJ: {Path(manifest["obj_preview"]).name if manifest.get("obj_preview") else "not generated"}\nTexture refs: {sum(len(v) for v in manifest.get("texture_refs", {}).values())}\nTextures extracted/copied: {len(manifest.get("textures", []))}'))
                    return
                except Exception as exc:
                    if hasattr(self, '_show_result') and OperationResult:
                        self._show_result(OperationResult(False, 'CodeX bundle export failed', str(exc)))
                    elif messagebox:
                        messagebox.showerror('CodeX bundle export failed', str(exc))
                    return
        return _prev_module_action(self, module_name, action)

    WorkbenchApp.module_action = _module_action_with_codex

    # Add a button to the model family dialog so archive-extracted entries can export with archive context.
    ModelFamilyDialog = g.get('ModelFamilyDialog')
    if ModelFamilyDialog is not None and tk is not None:
        _prev_model_init = ModelFamilyDialog.__init__

        def _model_init_with_codex(self, master, asset_path, archive_path=None, archive_entry=None, on_saved=None):
            _prev_model_init(self, master, asset_path, archive_path=archive_path, archive_entry=archive_entry, on_saved=on_saved)

            def _do_export():
                try:
                    bundle, manifest = codered_export_codex_bundle(Path(self.asset_path), archive_path=getattr(self, 'archive_path', None), archive_entry=getattr(self, 'archive_entry', None))
                    if hasattr(self.master_app, 'log'):
                        self.master_app.log(f'CodeX-style archive bundle exported: {bundle}')
                    if messagebox:
                        messagebox.showinfo(
                            'CodeX bundle exported',
                            f'Bundle written to:\n{bundle}\n\nXML: {Path(manifest["xml"]).name}\nOBJ: {Path(manifest["obj_preview"]).name if manifest.get("obj_preview") else "not generated"}\nTexture refs: {sum(len(v) for v in manifest.get("texture_refs", {}).values())}\nTextures extracted/copied: {len(manifest.get("textures", []))}',
                            parent=self,
                        )
                except Exception as exc:
                    if messagebox:
                        messagebox.showerror('CodeX bundle export failed', str(exc), parent=self)

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
                btn = tk.Button(button_row, text='Export CodeX Bundle', command=_do_export, bg=theme.get('accent', '#8B0000'), fg=theme.get('fg', '#FFFFFF'), relief='flat', padx=12, pady=7)
                if close_btn is not None:
                    btn.pack(side='left', padx=(8, 0), before=close_btn)
                else:
                    btn.pack(side='left', padx=(8, 0))

        ModelFamilyDialog.__init__ = _model_init_with_codex



    # --- Pass 21: Button-based CodeX import/readback workflow ---
    # Wraps the verified CLI import path in a GUI dialog so the user does not need to type commands.
    def _load_codex_import_tool():
        import importlib.util
        import sys
        tool_path = Path(CODERED_APP_ROOT) / 'tools' / 'codered_codex_bundle_import_cli.py'
        if not tool_path.exists():
            raise FileNotFoundError(f'Missing import tool: {tool_path}')
        tools_dir = str(tool_path.parent)
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
        spec = importlib.util.spec_from_file_location('codered_codex_bundle_import_cli_gui', tool_path)
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

    def _default_out_archive(archive_path, entry_query='codex_import'):
        archive_path = Path(archive_path) if archive_path else None
        safe_stem = _safe_filename(Path(str(entry_query or 'entry')).stem or 'entry')
        out_dir = Path(CODERED_APP_ROOT) / 'imports' / 'codex_roundtrip'
        out_dir.mkdir(parents=True, exist_ok=True)
        if archive_path:
            return out_dir / f'{archive_path.stem}__{safe_stem}_gui_import_copy{archive_path.suffix}'
        return out_dir / f'codex_{safe_stem}_gui_import_copy.rpf'

    def _report_to_text(result):
        try:
            import_result = result.get('import_result') or result
            archive_result = result.get('archive_import_result') or {}
            lines = []
            lines.append('CodeX Bundle Import Result')
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
            reps = import_result.get('replacements') or []
            if reps:
                lines.append('')
                lines.append('Same-length replacements:')
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

    def codered_import_codex_bundle(bundle, out_root=None, mode='payload-sidecar', replacements=None, archive_path=None, entry_query=None, out_archive=None, reexport_proof=True):
        tool = _load_codex_import_tool()
        bundle = Path(bundle)
        out_root = Path(out_root) if out_root else Path(CODERED_APP_ROOT) / 'imports' / 'codex_roundtrip'
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

    g['codered_import_codex_bundle'] = codered_import_codex_bundle

    class CodeXImportDialog(tk.Toplevel):
        def __init__(self, master, bundle_path=None, archive_path=None, archive_entry=None, asset_path=None):
            super().__init__(master)
            self.master_app = getattr(master, 'master_app', master)
            self.asset_path = Path(asset_path) if asset_path else None
            self.archive_path = Path(archive_path) if archive_path else None
            self.archive_entry = archive_entry or {}
            self.last_result = None
            self.title('Code RED - CodeX Import / Readback')
            self.geometry('1120x760')
            self.minsize(900, 600)
            c = getattr(self.master_app, 'theme', {'bg': '#000000', 'panel': '#050505', 'fg': '#FFFFFF', 'button': '#151515', 'accent': '#8B0000'})
            self.theme = c
            self.configure(bg=c['bg'])

            root = tk.Frame(self, bg=c['bg'])
            root.pack(fill='both', expand=True, padx=12, pady=12)
            tk.Label(root, text='CodeX Bundle Import / Archive-Copy Verify', font=('SegoeUI', 15, 'bold'), bg=c['bg'], fg=c['fg'], anchor='w').pack(fill='x')
            tk.Label(root, text='Button workflow for no-edit round trips and same-length texture/reference swaps. Source archives are copied; originals are not overwritten.', bg=c['bg'], fg=c['fg'], anchor='w', justify='left').pack(fill='x', pady=(4, 10))

            form = tk.Frame(root, bg=c['bg'])
            form.pack(fill='x')
            self.bundle_var = tk.StringVar(value=str(bundle_path or ''))
            self.archive_var = tk.StringVar(value=str(self.archive_path or ''))
            self.entry_var = tk.StringVar(value=_default_entry_query(self.asset_path, self.archive_entry))
            self.out_dir_var = tk.StringVar(value=str(Path(CODERED_APP_ROOT) / 'imports' / 'codex_roundtrip'))
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

            repl = tk.LabelFrame(form, text='Optional same-length texture/reference swap', bg=c['bg'], fg=c['fg'], padx=8, pady=8)
            repl.pack(fill='x', pady=(6, 8))
            r1 = tk.Frame(repl, bg=c['bg'])
            r1.pack(fill='x')
            tk.Label(r1, text='Old text', width=12, anchor='w', bg=c['bg'], fg=c['fg']).pack(side='left')
            tk.Entry(r1, textvariable=self.old_var, bg=c['panel'], fg=c['fg'], insertbackground=c['fg'], relief='flat').pack(side='left', fill='x', expand=True, ipady=6)
            tk.Label(r1, text='New text', width=12, anchor='w', bg=c['bg'], fg=c['fg']).pack(side='left', padx=(8, 0))
            tk.Entry(r1, textvariable=self.new_var, bg=c['panel'], fg=c['fg'], insertbackground=c['fg'], relief='flat').pack(side='left', fill='x', expand=True, ipady=6)
            self.repl_status = tk.StringVar(value='Leave both blank for a no-edit import. When used, old and new must have the same byte length.')
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
            self._write_result('Ready. Export a CodeX bundle, select it here, then use either Build Imported File Only or Import Into Archive Copy + Verify.\n\nFor canoe files, first export the canoe WFT/WFD/WVD bundle, keep Raw clone selected for archive-copy verification, then run a no-edit archive-copy verify before trying a same-length texture/reference swap.')

        def _write_result(self, text):
            self.result_text.configure(state='normal')
            self.result_text.delete('1.0', 'end')
            self.result_text.insert('1.0', text)
            self.result_text.configure(state='disabled')

        def _update_repl_status(self):
            old = self.old_var.get()
            new = self.new_var.get()
            if not old and not new:
                self.repl_status.set('Leave both blank for a no-edit import. When used, old and new must have the same byte length.')
                return
            lo = len(old.encode('latin-1', errors='ignore'))
            ln = len(new.encode('latin-1', errors='ignore'))
            state = 'OK' if lo == ln and lo > 0 else 'BLOCKED'
            self.repl_status.set(f'{state}: old={lo} bytes, new={ln} bytes. Same-size replacement is required for safe direct-slot import.')

        def browse_bundle(self):
            p = filedialog.askdirectory(parent=self, title='Select CodeX export bundle folder')
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
            if len(old.encode('latin-1')) != len(new.encode('latin-1')):
                raise ValueError('Replacement blocked: old and new text must be the exact same byte length.')
            return [(old, new)]

        def _common_args(self, include_archive=False):
            bundle = Path(self.bundle_var.get())
            if not bundle.exists():
                raise FileNotFoundError(f'Bundle folder does not exist: {bundle}')
            out_root = Path(self.out_dir_var.get() or (Path(CODERED_APP_ROOT) / 'imports' / 'codex_roundtrip'))
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
                result = codered_import_codex_bundle(**self._common_args(include_archive=False))
                self.last_result = result
                self._write_result(_report_to_text(result))
                if hasattr(self.master_app, 'log'):
                    self.master_app.log('CodeX imported file built from bundle.')
            except Exception as exc:
                self._write_result('Import failed:\n\n' + str(exc))
                messagebox.showerror('CodeX import failed', str(exc), parent=self)

        def run_archive_verify(self):
            try:
                result = codered_import_codex_bundle(**self._common_args(include_archive=True))
                self.last_result = result
                text = _report_to_text(result)
                self._write_result(text)
                ok = bool((result.get('archive_import_result') or {}).get('reread_matches_imported'))
                if hasattr(self.master_app, 'log'):
                    self.master_app.log('CodeX archive-copy import verified.' if ok else 'CodeX archive-copy import completed with warnings.')
                messagebox.showinfo('Archive-copy verify complete' if ok else 'Archive-copy verify finished', text[:3000], parent=self)
            except Exception as exc:
                self._write_result('Archive-copy import failed:\n\n' + str(exc))
                messagebox.showerror('Archive-copy import failed', str(exc), parent=self)

        def open_output_folder(self):
            try:
                import os
                import subprocess
                import sys
                p = Path(self.out_dir_var.get() or (Path(CODERED_APP_ROOT) / 'imports' / 'codex_roundtrip'))
                p.mkdir(parents=True, exist_ok=True)
                if sys.platform.startswith('win'):
                    os.startfile(str(p))
                elif sys.platform == 'darwin':
                    subprocess.Popen(['open', str(p)])
                else:
                    subprocess.Popen(['xdg-open', str(p)])
            except Exception as exc:
                messagebox.showerror('Open folder failed', str(exc), parent=self)

    def _open_codex_import_dialog(self):
        CodeXImportDialog(self)

    try:
        setattr(WorkbenchApp, 'open_codex_import_dialog', _open_codex_import_dialog)
    except Exception:
        pass

    # Add import buttons to model family dialogs. This is the main no-command path.
    ModelFamilyDialog = g.get('ModelFamilyDialog')
    if ModelFamilyDialog is not None and tk is not None:
        _prev_import_model_init = ModelFamilyDialog.__init__

        def _model_init_with_codex_import(self, master, asset_path, archive_path=None, archive_entry=None, on_saved=None):
            _prev_import_model_init(self, master, asset_path, archive_path=archive_path, archive_entry=archive_entry, on_saved=on_saved)

            def _open_import_lab(bundle_path=None):
                CodeXImportDialog(self, bundle_path=bundle_path, archive_path=getattr(self, 'archive_path', None), archive_entry=getattr(self, 'archive_entry', None), asset_path=getattr(self, 'asset_path', None))

            def _roundtrip_verify_current():
                try:
                    if not getattr(self, 'archive_path', None):
                        messagebox.showinfo('Archive context needed', 'Open this model from inside an RPF archive first, then use Round-trip Verify Copy.', parent=self)
                        return
                    bundle, manifest = codered_export_codex_bundle(Path(self.asset_path), archive_path=getattr(self, 'archive_path', None), archive_entry=getattr(self, 'archive_entry', None))
                    entry = _default_entry_query(getattr(self, 'asset_path', None), getattr(self, 'archive_entry', None))
                    result = codered_import_codex_bundle(
                        bundle=bundle,
                        out_root=Path(CODERED_APP_ROOT) / 'imports' / 'codex_roundtrip',
                        mode='raw-clone',
                        replacements=[],
                        archive_path=Path(self.archive_path),
                        entry_query=entry,
                        out_archive=_default_out_archive(Path(self.archive_path), entry),
                        reexport_proof=True,
                    )
                    text = _report_to_text(result)
                    if hasattr(self.master_app, 'log'):
                        self.master_app.log(f'CodeX round-trip verify copy complete: {bundle}')
                    messagebox.showinfo('Round-trip verify complete', text[:3000], parent=self)
                    dlg = CodeXImportDialog(self, bundle_path=bundle, archive_path=getattr(self, 'archive_path', None), archive_entry=getattr(self, 'archive_entry', None), asset_path=getattr(self, 'asset_path', None))
                    dlg._write_result(text)
                except Exception as exc:
                    messagebox.showerror('Round-trip verify failed', str(exc), parent=self)

            button_row = None
            for child in self.winfo_children():
                if isinstance(child, tk.Frame):
                    texts = [sub.cget('text') for sub in child.winfo_children() if isinstance(sub, tk.Button)]
                    if 'Open Current Bytes' in texts or 'Export CodeX Bundle' in texts:
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
                    ('Import CodeX Bundle', lambda: _open_import_lab(None), theme.get('button', '#151515')),
                    ('Round-trip Verify Copy', _roundtrip_verify_current, theme.get('accent', '#8B0000')),
                ]
                for label, cmd, color in buttons:
                    btn = tk.Button(button_row, text=label, command=cmd, bg=color, fg=theme.get('fg', '#FFFFFF'), relief='flat', padx=12, pady=7)
                    if close_btn is not None:
                        btn.pack(side='left', padx=(8, 0), before=close_btn)
                    else:
                        btn.pack(side='left', padx=(8, 0))

        ModelFamilyDialog.__init__ = _model_init_with_codex_import




    # Add CodeX bundle buttons directly to the RPF Archive Browser as well.
    ArchiveBrowserDialog = g.get('ArchiveBrowserDialog')
    if ArchiveBrowserDialog is not None and tk is not None:
        _prev_archive_browser_init = ArchiveBrowserDialog.__init__

        def _archive_browser_init_with_codex(self, master, archive_path, info):
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
                temp_dir = Path(tempfile.mkdtemp(prefix='codered_codex_archive_'))
                temp_path = temp_dir / (Path(ent.get('name', '')).name or f"entry_{ent.get('index', 0)}.bin")
                temp_path.write_bytes(data)
                return temp_path

            def _export_selected_bundle():
                try:
                    ent = _selected_model_entry()
                    if not ent:
                        return
                    temp_path = _extract_model_entry(ent)
                    bundle, manifest = codered_export_codex_bundle(temp_path, archive_path=self.archive_path, archive_entry=ent)
                    if hasattr(self.master_app, 'log'):
                        self.master_app.log(f'CodeX bundle exported from archive browser: {bundle}')
                    messagebox.showinfo(
                        'CodeX bundle exported',
                        f'Bundle written to:\n{bundle}\n\nXML: {Path(manifest["xml"]).name}\nOBJ: {Path(manifest["obj_preview"]).name if manifest.get("obj_preview") else "not generated"}\nTexture refs: {sum(len(v) for v in manifest.get("texture_refs", {}).values())}\nTextures extracted/copied: {len(manifest.get("textures", []))}',
                        parent=self,
                    )
                except Exception as exc:
                    messagebox.showerror('CodeX export failed', str(exc), parent=self)

            def _import_bundle_for_selected():
                ent = _selected_model_entry()
                if not ent:
                    return
                CodeXImportDialog(self, archive_path=self.archive_path, archive_entry=ent, asset_path=Path(ent.get('name', '') or 'asset.wvd'))

            def _roundtrip_selected():
                try:
                    ent = _selected_model_entry()
                    if not ent:
                        return
                    temp_path = _extract_model_entry(ent)
                    bundle, manifest = codered_export_codex_bundle(temp_path, archive_path=self.archive_path, archive_entry=ent)
                    entry = _default_entry_query(temp_path, ent)
                    result = codered_import_codex_bundle(
                        bundle=bundle,
                        out_root=Path(CODERED_APP_ROOT) / 'imports' / 'codex_roundtrip',
                        mode='raw-clone',
                        replacements=[],
                        archive_path=self.archive_path,
                        entry_query=entry,
                        out_archive=_default_out_archive(self.archive_path, entry),
                        reexport_proof=True,
                    )
                    text = _report_to_text(result)
                    if hasattr(self.master_app, 'log'):
                        self.master_app.log(f'CodeX archive-browser round-trip verify complete: {entry}')
                    messagebox.showinfo('Round-trip verify complete', text[:3000], parent=self)
                    dlg = CodeXImportDialog(self, bundle_path=bundle, archive_path=self.archive_path, archive_entry=ent, asset_path=temp_path)
                    dlg._write_result(text)
                except Exception as exc:
                    messagebox.showerror('Round-trip verify failed', str(exc), parent=self)

            for label, cmd, color in [
                ('Export CodeX Bundle', _export_selected_bundle, c.get('accent', '#8B0000')),
                ('Import CodeX Bundle', _import_bundle_for_selected, c.get('button', '#151515')),
                ('Round-trip Verify', _roundtrip_selected, c.get('accent', '#8B0000')),
            ]:
                btn = tk.Button(button_row, text=label, command=cmd, bg=color, fg=c.get('fg', '#FFFFFF'), relief='flat', padx=12, pady=7)
                if close_btn is not None:
                    btn.pack(side='left', padx=(0, 8), before=close_btn)
                else:
                    btn.pack(side='left', padx=(0, 8))

        ArchiveBrowserDialog.__init__ = _archive_browser_init_with_codex


    # Add visible capability status to the Meshes module.
    meshes = MODULE_BY_NAME.get('Meshes') if isinstance(MODULE_BY_NAME, dict) else None
    if meshes is not None:
        try:
            meshes.summary = str(getattr(meshes, 'summary', '')) + ' CodeX-style XML/texture export bundles are available.'
            cap_cls = g.get('FormatCapability')
            if cap_cls:
                meshes.capabilities.append(cap_cls('.codex.xml', 'Meshes', 'X/P', 'Code RED CodeX-style sidecar export: XML manifest, raw payload, texture refs/extracts, and OBJ point-cloud preview.'))
        except Exception:
            pass
