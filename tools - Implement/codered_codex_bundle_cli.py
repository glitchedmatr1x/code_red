#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import struct
import time
import zlib
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape

try:
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    HAVE_CRYPTO = True
except Exception:
    HAVE_CRYPTO = False

RPF6_AES_KEY = bytes([
    0xB7, 0x62, 0xDF, 0xB6, 0xE2, 0xB2, 0xC6, 0xDE,
    0xAF, 0x72, 0x2A, 0x32, 0xD2, 0xFB, 0x6F, 0x0C,
    0x98, 0xA3, 0x21, 0x74, 0x62, 0xC9, 0xC4, 0xED,
    0xAD, 0xAA, 0x2E, 0xD0, 0xDD, 0xF9, 0x2F, 0x10,
])

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

TEXTURE_EXTS = {'.dds', '.png', '.wtd', '.wtx', '.wsf', '.xtd', '.xtx', '.xsf', '.wtb'}
MODEL_EXTS = {'.wft', '.wfd', '.wvd', '.xft', '.xfd', '.xvd', '.wbd', '.wtb', '.wsi', '.wsp', '.wsg', '.wtl'}


def _rpf6_decrypt(data: bytes) -> bytes:
    if not data or not HAVE_CRYPTO:
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


def rdr_name_hash(name: str) -> int:
    num2 = 0
    for ch in name.lower():
        num3 = (num2 + ord(ch)) & 0xFFFFFFFF
        num4 = (num3 + ((num3 << 10) & 0xFFFFFFFF)) & 0xFFFFFFFF
        num2 = (num4 ^ (num4 >> 6)) & 0xFFFFFFFF
    num5 = (num2 + ((num2 << 3) & 0xFFFFFFFF)) & 0xFFFFFFFF
    num6 = (num5 ^ (num5 >> 11)) & 0xFFFFFFFF
    return (num6 + ((num6 << 15) & 0xFFFFFFFF)) & 0xFFFFFFFF


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
        return ((flag2 & 0x3FFF) << 12) + (((flag2 >> 14) & 0x3FFF) << 12)
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


def parse_rpf6(path: Path) -> dict | None:
    data = Path(path).read_bytes()
    if len(data) < 16 or data[:4] != b'RPF6':
        return None
    _, entry_count, debug_offset, enc_flag = struct.unpack('>4I', data[:16])
    toc_size = ((entry_count * 20) + 15) & ~15
    if len(data) < 16 + toc_size:
        return None
    toc = data[16:16 + toc_size]
    if enc_flag != 0:
        toc = _rpf6_decrypt(toc)
    entries = []
    for i in range(entry_count):
        a, b, c, d, e = struct.unpack('>5I', toc[i * 20:(i + 1) * 20])
        is_dir = ((c >> 24) & 0xFF) == 0x80
        entry = {'index': i, 'name_off': a, 'debug_name': None}
        if is_dir:
            entry.update({'type': 'dir', 'flags': b, 'start': c & 0x7FFFFFFF, 'count': d & 0x0FFFFFFF, 'unk': e})
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
        entries.append(entry)

    if debug_offset > 0 and debug_offset * 8 < len(data):
        debug_blob = _rpf6_decrypt(data[debug_offset * 8:])
        names_blob = debug_blob[entry_count * 8:]
        hash_map = {}
        for ent in entries:
            hash_map.setdefault(ent['name_off'], []).append(ent)
        for raw_name in names_blob.decode('latin-1', errors='ignore').split('\x00'):
            raw_name = raw_name.strip()
            if not raw_name:
                continue
            h = rdr_name_hash(raw_name)
            for ent in hash_map.get(h, []):
                if not ent.get('debug_name'):
                    ent['debug_name'] = raw_name
                    break

    def resolve_name(entry: dict) -> str:
        if entry['type'] == 'dir' and entry['name_off'] == 0:
            return 'root'
        return entry.get('debug_name') or f"0x{entry['name_off']:08X}"

    parents = [None] * len(entries)
    for entry in entries:
        if entry['type'] == 'dir':
            for child_index in range(entry['start'], entry['start'] + entry['count']):
                if 0 <= child_index < len(entries):
                    parents[child_index] = entry['index']

    ext_counts = Counter()
    resolved_count = 0
    for entry in entries:
        entry['name'] = resolve_name(entry)
        entry['parent_index'] = parents[entry['index']]
        if not entry['name'].startswith('0x') or entry['name'] == 'root':
            resolved_count += 1
        parent = parents[entry['index']]
        parts = [entry['name']]
        while parent is not None:
            parts.append(resolve_name(entries[parent]))
            parent = parents[parent]
        entry['path'] = '/'.join(reversed(parts))
        if entry['type'] == 'file':
            entry['extension'] = Path(entry['name']).suffix.lower() or '<none>'
            ext_counts[entry['extension']] += 1
    return {
        'entry_count': entry_count,
        'file_count': sum(1 for e in entries if e.get('type') == 'file'),
        'dir_count': sum(1 for e in entries if e.get('type') == 'dir'),
        'resolved_count': resolved_count,
        'ext_counts': ext_counts,
        'entries': entries,
    }


def extract_rpf_entry(archive_path: Path, entry: dict) -> bytes:
    with Path(archive_path).open('rb') as f:
        f.seek(entry['offset'])
        raw = f.read(entry['size_in_archive'])
    if entry.get('is_resource'):
        return raw
    if entry.get('is_compressed'):
        for wbits in (-15, 15, 31):
            try:
                return zlib.decompress(raw, wbits)
            except Exception:
                continue
        raise ValueError('Compressed file could not be decompressed by fallback path.')
    return raw


def parse_resource_header(data: bytes) -> dict | None:
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
        return int.from_bytes(data[offset:offset + 4], field_endian, signed=False) if offset + 4 <= len(data) else 0

    resource_type = read_u32(4)
    flag1 = read_u32(8)
    flag2 = read_u32(12) if ident in {1381188485, 1381188486, 2235781970, 2252559186} and len(data) >= 16 else 0
    normalized_map = {'05CSR': 'RSC05', '06CSR': 'RSC06', '85CSR': 'RSC85', '86CSR': 'RSC86'}
    normalized = normalized_map.get(RSC_IDENTIFIERS[ident], RSC_IDENTIFIERS[ident])
    return {
        'ident_name': normalized,
        'raw_ident_name': RSC_IDENTIFIERS[ident],
        'endian': display_endian,
        'resource_type': resource_type,
        'flag1': flag1,
        'flag2': flag2,
        'is_extended': _rpf_flag_is_extended(flag2) if normalized in {'RSC85', 'RSC86'} else False,
        'is_compressed': _rpf_flag_is_compressed(flag1, flag2) if normalized in {'RSC05', 'RSC06'} else False,
        'total_size': _rpf_total_size(flag1, flag2),
    }


def resource_header_size(resource: dict | None) -> int:
    if not resource:
        return 0
    return 16 if resource['ident_name'] in {'RSC85', 'RSC86'} else 12


def extract_resource_payload(data: bytes, resource: dict | None = None) -> dict:
    resource = resource or parse_resource_header(data)
    if not resource:
        return {'payload': data, 'notes': ['No resource header; raw bytes used.'], 'header_size': 0}
    header_size = resource_header_size(resource)
    payload = data[header_size:] if len(data) > header_size else b''
    notes = [f'Resource payload starts at byte {header_size}.']
    if payload and resource['resource_type'] == 2 and resource['ident_name'] in {'RSC85', 'RSC86'}:
        dec = _rpf6_decrypt(payload)
        if dec != payload:
            payload = dec
            notes.append('Applied AES payload decryption for RSC85/RSC86 resource type 2.')
    coded = payload
    if coded and (coded[:2] in {b"x\x9c", b"x\xda", b"x\x01", b"x^", b"\x78\x5e", b"\x78\x9c", b"\x78\xda"} or resource.get('is_compressed')):
        for wbits in (-15, 15, 31):
            try:
                payload = zlib.decompress(coded, wbits)
                notes.append(f'Payload decompressed using zlib({wbits}).')
                break
            except Exception:
                pass
    notes.append(f'Payload length after processing: {len(payload):,} bytes.')
    return {'payload': payload, 'notes': notes, 'header_size': header_size}


def safe_filename(value: str, default='asset') -> str:
    value = str(value or default).replace('\\', '/')
    value = Path(value).name
    value = re.sub(r'[^A-Za-z0-9_.-]+', '_', value).strip('._')
    return (value or default)[:140]


def scan_refs(data: bytes):
    strings = []
    seen = set()
    for m in re.finditer(rb'[A-Za-z0-9_./:\\-]{4,160}', data or b''):
        s = m.group().decode('latin-1', errors='ignore')
        if s in seen:
            continue
        seen.add(s)
        strings.append(s)
        if len(strings) >= 4000:
            break
    refs = {}
    for ext in ['.dds', '.png', '.wtd', '.wtx', '.wsf', '.wtb', '.wvd', '.wfd', '.wft', '.fxc']:
        refs[ext] = sorted({s for s in strings if ext in s.lower()})[:160]
    bone_hints = sorted({
        s for s in strings
        if any(tok in s.lower() for tok in ('bone', 'spine', 'pelvis', 'head', 'neck', 'arm', 'leg', 'root', 'tail', 'finger'))
    })[:120]
    return refs, bone_hints


def triplet_ok(x, y, z):
    vals = (x, y, z)
    return all(math.isfinite(v) for v in vals) and 0.0001 < max(abs(v) for v in vals) < 100000.0


def model_candidates(payload: bytes, limit=5):
    candidates = []
    for stride in (12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56, 60, 64):
        for offset in range(0, min(stride, 64), 4):
            pts = []
            suspicious = 0
            for pos in range(offset, len(payload) - 12, stride):
                try:
                    x, y, z = struct.unpack_from('<fff', payload, pos)
                except Exception:
                    break
                if triplet_ok(x, y, z):
                    pts.append((float(x), float(y), float(z)))
                else:
                    suspicious += 1
            if len(pts) < 80:
                continue
            filtered = pts
            if len(pts) >= 200:
                xs = sorted(p[0] for p in pts); ys = sorted(p[1] for p in pts); zs = sorted(p[2] for p in pts)
                n = len(pts); lo = max(0, int(n * 0.01)); hi = min(n - 1, int(n * 0.99))
                bounds = ((xs[lo], xs[hi]), (ys[lo], ys[hi]), (zs[lo], zs[hi]))
                trial = [p for p in pts if all(bounds[i][0] <= p[i] <= bounds[i][1] for i in range(3))]
                if len(trial) >= 80:
                    filtered = trial
            xs = [p[0] for p in filtered]; ys = [p[1] for p in filtered]; zs = [p[2] for p in filtered]
            spans = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
            nonflat = sum(1 for span in spans if span > 0.05)
            if nonflat < 2:
                continue
            unique_ratio = len({(round(a, 3), round(b, 3), round(c, 3)) for a, b, c in filtered}) / max(1, len(filtered))
            score = min(1.0, len(filtered) / 3000.0) * 2.5 + unique_ratio * 1.8 + (nonflat / 3.0) * 0.8 + len(filtered) / max(1, len(pts)) * 0.9 + (1 - suspicious / max(1, suspicious + len(pts))) * 0.8
            candidates.append({
                'score': round(score, 3),
                'stride': stride,
                'offset': offset,
                'count': len(pts),
                'filtered_count': len(filtered),
                'unique_ratio': round(unique_ratio, 4),
                'extents': spans,
                'bounds': ((min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))),
                'points': filtered[:12000],
            })
    candidates.sort(key=lambda row: (row['score'], row['filtered_count'], row['unique_ratio']), reverse=True)
    return candidates[:limit]


def write_obj(path: Path, points):
    with Path(path).open('w', encoding='utf-8') as f:
        f.write('# Code RED heuristic OBJ preview\n')
        f.write('# Vertices are guessed from float streams; faces are not invented.\n')
        for x, y, z in points:
            f.write(f'v {x:.6f} {y:.6f} {z:.6f}\n')
        f.write('# point-cloud only\n')


def archive_companions(archive_path: Path, archive_info: dict, archive_entry: dict, refs: dict, limit=20):
    current_path = str(archive_entry.get('path') or archive_entry.get('name') or '')
    current_parent = str(Path(current_path).parent).lower()
    current_stem = Path(archive_entry.get('name') or current_path).stem.lower()
    ref_tokens = set()
    for items in refs.values():
        for item in items:
            ref_tokens.add(Path(item).name.lower())
            ref_tokens.add(Path(item).stem.lower())
    rows = []
    for ent in archive_info.get('entries', []):
        if ent.get('type') != 'file' or ent.get('index') == archive_entry.get('index'):
            continue
        ext = (ent.get('extension') or '').lower()
        if ext not in TEXTURE_EXTS:
            continue
        ep = str(ent.get('path') or '').lower()
        en = str(ent.get('name') or '').lower()
        es = Path(en).stem.lower()
        score = 0
        reasons = []
        if str(Path(ep).parent).lower() == current_parent:
            score += 70; reasons.append('same-parent')
        if en in ref_tokens or es in ref_tokens:
            score += 260; reasons.append('texture-ref-match')
        if current_stem and (current_stem in es or es in current_stem):
            score += 90; reasons.append('family-stem-overlap')
        if ext in {'.dds', '.png'}:
            score += 35; reasons.append('image-ext')
        if score:
            rows.append({'score': score, 'entry': ent, 'reasons': reasons})
    rows.sort(key=lambda r: (-r['score'], r['entry'].get('path', '')))
    return rows[:limit]


def create_bundle(asset_name: str, data: bytes, out_root: Path, archive_path: Path | None = None, archive_entry: dict | None = None, archive_info: dict | None = None, max_textures=16):
    stamp = time.strftime('%Y%m%d_%H%M%S')
    stem = Path(asset_name).stem or 'asset'
    bundle = Path(out_root) / f'{safe_filename(stem)}_codex_bundle_{stamp}'
    textures_dir = bundle / 'textures'
    sidecars_dir = bundle / 'sidecars'
    textures_dir.mkdir(parents=True, exist_ok=True)
    sidecars_dir.mkdir(parents=True, exist_ok=True)

    raw_path = bundle / safe_filename(asset_name)
    raw_path.write_bytes(data)
    resource = parse_resource_header(data)
    payload_info = extract_resource_payload(data, resource)
    payload = payload_info.get('payload') or data
    payload_path = sidecars_dir / f'{safe_filename(asset_name)}.payload.bin'
    payload_path.write_bytes(payload)

    refs, bone_hints = scan_refs(payload)
    streams = model_candidates(payload)
    obj_path = None
    if streams:
        obj_path = bundle / f'{safe_filename(stem)}_preview.obj'
        write_obj(obj_path, streams[0]['points'])

    textures = []
    # Embedded PNG/DDS scan
    png_sig = b'\x89PNG\r\n\x1a\n'
    for idx, match in enumerate(re.finditer(re.escape(png_sig), payload)):
        if len(textures) >= max_textures:
            break
        end = payload.find(b'IEND', match.start())
        if end >= 0:
            end += 8
            out = textures_dir / f'embedded_{idx:03d}.png'
            out.write_bytes(payload[match.start():end])
            textures.append({'kind': 'embedded_png', 'path': out.name, 'offset': match.start(), 'size': out.stat().st_size})
    dds_positions = [m.start() for m in re.finditer(b'DDS ', payload)]
    for idx, pos in enumerate(dds_positions):
        if len(textures) >= max_textures:
            break
        end = dds_positions[idx + 1] if idx + 1 < len(dds_positions) else min(len(payload), pos + 8 * 1024 * 1024)
        out = textures_dir / f'embedded_{idx:03d}.dds'
        out.write_bytes(payload[pos:end])
        textures.append({'kind': 'embedded_dds', 'path': out.name, 'offset': pos, 'size': out.stat().st_size})

    if archive_path and archive_entry and archive_info:
        for row in archive_companions(archive_path, archive_info, archive_entry, refs, limit=max_textures):
            if len(textures) >= max_textures:
                break
            ent = row['entry']
            try:
                companion_data = extract_rpf_entry(archive_path, ent)
            except Exception as exc:
                textures.append({'kind': 'archive_companion_failed', 'archive_path': ent.get('path', ''), 'score': row['score'], 'error': str(exc), 'size': 0})
                continue
            out = textures_dir / safe_filename(ent.get('name') or f'entry_{ent["index"]}.bin')
            if out.exists():
                out = textures_dir / f'{ent["index"]:04d}_{out.name}'
            out.write_bytes(companion_data)
            textures.append({'kind': 'archive_companion', 'path': out.name, 'archive_path': ent.get('path', ''), 'score': row['score'], 'reasons': row['reasons'], 'size': len(companion_data)})

    stream_manifest = [{k: v for k, v in row.items() if k != 'points'} for row in streams]
    xml_lines = ['<?xml version="1.0" encoding="utf-8"?>', '<CodeREDCodeXBundle version="pass19">']
    xml_lines.append(f'  <Source name="{escape(asset_name)}" archive="{escape(str(archive_path or ""))}" internalPath="{escape(str((archive_entry or {}).get("path", "")))}" />')
    if resource:
        xml_lines.append(
            f'  <Resource ident="{resource["ident_name"]}" rawIdent="{resource["raw_ident_name"]}" resourceType="{resource["resource_type"]}" '
            f'flag1="0x{resource["flag1"]:08X}" flag2="0x{resource.get("flag2", 0):08X}" totalSize="{resource.get("total_size", 0)}" />'
        )
    xml_lines.append(f'  <Payload bytes="{len(payload)}" sidecar="sidecars/{escape(payload_path.name)}" />')
    xml_lines.append('  <TextureRefs>')
    for ext, items in refs.items():
        for item in items:
            xml_lines.append(f'    <Ref ext="{escape(ext)}">{escape(item)}</Ref>')
    xml_lines.append('  </TextureRefs>')
    xml_lines.append('  <BoneHints>')
    for item in bone_hints:
        xml_lines.append(f'    <Bone>{escape(item)}</Bone>')
    xml_lines.append('  </BoneHints>')
    xml_lines.append('  <HeuristicStreams>')
    for row in stream_manifest:
        extents = row.get('extents') or (0, 0, 0)
        xml_lines.append(f'    <Stream score="{row.get("score", 0)}" stride="{row.get("stride", 0)}" offset="{row.get("offset", 0)}" points="{row.get("count", 0)}" filtered="{row.get("filtered_count", 0)}" extents="{float(extents[0]):.6g},{float(extents[1]):.6g},{float(extents[2]):.6g}" />')
    xml_lines.append('  </HeuristicStreams>')
    xml_lines.append('  <Textures>')
    for row in textures:
        xml_lines.append(f'    <Texture kind="{escape(str(row.get("kind", "")))}" path="{escape(str(row.get("path", "")))}" size="{int(row.get("size", 0) or 0)}" />')
    xml_lines.append('  </Textures>')
    xml_lines.append('</CodeREDCodeXBundle>')
    xml_path = bundle / f'{safe_filename(stem)}.codex.xml'
    xml_path.write_text('\n'.join(xml_lines) + '\n', encoding='utf-8')

    manifest = {
        'version': 'pass19-codex-bundle-cli',
        'asset_name': asset_name,
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
        'textures': textures,
        'warnings': [
            'Export bundle is safe/read-only against the source archive.',
            'XML is CodeX-style bridge data, not yet a guaranteed native CodeX round-trip XML.',
            'OBJ preview is a guessed point cloud until dictionary-aware topology decoding is complete.',
        ],
    }
    (bundle / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (bundle / 'extraction_report.txt').write_text(
        'Code RED CodeX-style Export Bundle\n'
        '==================================\n\n'
        f'Asset: {asset_name}\n'
        f'Archive: {archive_path or ""}\n'
        f'Internal path: {(archive_entry or {}).get("path", "")}\n'
        f'Raw bytes: {len(data):,}\n'
        f'Payload bytes: {len(payload):,}\n'
        f'XML: {xml_path.name}\n'
        f'OBJ preview: {Path(obj_path).name if obj_path else "not generated"}\n'
        f'Texture refs: {sum(len(v) for v in refs.values())}\n'
        f'Texture files copied/extracted: {len(textures)}\n'
        f'Heuristic streams: {len(stream_manifest)}\n\n'
        'Payload notes:\n' + '\n'.join(f'- {line}' for line in payload_info.get('notes', [])) + '\n',
        encoding='utf-8',
    )
    return bundle, manifest


def main():
    parser = argparse.ArgumentParser(description='Code RED CodeX-style model export bundle tool.')
    parser.add_argument('--asset', type=Path, help='Direct WFT/WFD/WVD/WBD/WTB/etc file to export.')
    parser.add_argument('--archive', type=Path, help='RPF6 archive to extract from.')
    parser.add_argument('--entry', help='Case-insensitive substring for the internal entry path/name.')
    parser.add_argument('--out', type=Path, default=Path('exports/codex_bundles'), help='Output root folder.')
    parser.add_argument('--list', action='store_true', help='List model-like entries in an archive instead of exporting.')
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    if args.archive:
        info = parse_rpf6(args.archive)
        if not info:
            raise SystemExit(f'Could not parse RPF6 archive: {args.archive}')
        model_entries = [e for e in info['entries'] if e.get('type') == 'file' and (e.get('extension') or '').lower() in MODEL_EXTS]
        if args.list:
            print(json.dumps([{'path': e.get('path'), 'size': e.get('size_in_archive'), 'index': e.get('index')} for e in model_entries[:500]], indent=2))
            return 0
        if not args.entry:
            raise SystemExit('--entry is required with --archive unless --list is used.')
        needle = args.entry.lower()
        matches = [e for e in model_entries if needle in (e.get('path', '') + ' ' + e.get('name', '')).lower()]
        if not matches:
            raise SystemExit(f'No model-like archive entry matched: {args.entry}')
        entry = sorted(matches, key=lambda e: e.get('size_in_archive', 0), reverse=True)[0]
        data = extract_rpf_entry(args.archive, entry)
        bundle, manifest = create_bundle(entry.get('name') or f'entry_{entry["index"]}.bin', data, args.out, archive_path=args.archive, archive_entry=entry, archive_info=info)
        print(json.dumps({'bundle': str(bundle), 'manifest': str(bundle / 'manifest.json'), 'xml': manifest.get('xml'), 'obj_preview': manifest.get('obj_preview'), 'texture_refs': sum(len(v) for v in manifest.get('texture_refs', {}).values()), 'textures': len(manifest.get('textures', [])), 'heuristic_streams': len(manifest.get('heuristic_streams', []))}, indent=2))
        return 0

    if args.asset:
        data = args.asset.read_bytes()
        bundle, manifest = create_bundle(args.asset.name, data, args.out)
        print(json.dumps({'bundle': str(bundle), 'manifest': str(bundle / 'manifest.json'), 'xml': manifest.get('xml'), 'obj_preview': manifest.get('obj_preview'), 'texture_refs': sum(len(v) for v in manifest.get('texture_refs', {}).values()), 'textures': len(manifest.get('textures', [])), 'heuristic_streams': len(manifest.get('heuristic_streams', []))}, indent=2))
        return 0

    raise SystemExit('Use --asset or --archive.')


if __name__ == '__main__':
    raise SystemExit(main())
