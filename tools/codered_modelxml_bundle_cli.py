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

TEXTURE_EXTS = {'.dds', '.png', '.wtd', '.wtx', '.wsf', '.xtd', '.xtx', '.xsf'}
# EDT-style files are treated as structure/layout companions. They are not imported
# as geometry yet, but exporting them beside the model makes the model bundle much
# closer to the way the game keeps drawable pieces, LODs, texture dictionaries,
# placement/entity maps, and dependency references together.
STRUCTURE_EXTS = {'.wedt', '.xedt', '.yedt', '.wsi', '.wsp', '.wsg', '.wbd', '.wtl'}
MODEL_EXTS = {'.wft', '.wfd', '.wvd', '.xft', '.xfd', '.xvd', '.wbd', '.wtb', '.wsi', '.wsp', '.wsg', '.wtl', '.wedt', '.xedt', '.yedt'}
RENDER_MODEL_EXTS = {'.wft', '.wfd', '.wvd', '.xft', '.xfd', '.xvd', '.wtb'}


LOD_PATTERNS = [
    ('hi', re.compile(r'(?i)(?:^|[_\-.])(hi|high|hilod|lod0)(?:$|[_\-.])')),
    ('main', re.compile(r'(?i)(?:^|[_\-.])(main|base|lod)(?:$|[_\-.])')),
    ('med', re.compile(r'(?i)(?:^|[_\-.])(med|medium|medlod|lod1)(?:$|[_\-.])')),
    ('low', re.compile(r'(?i)(?:^|[_\-.])(low|lowlod|lod2)(?:$|[_\-.])')),
    ('vlow', re.compile(r'(?i)(?:^|[_\-.])(vlow|vlo|verylow|slod|lod3|lod4|lod5)(?:$|[_\-.])')),
]
LOD_ORDER = {'hi': 0, 'main': 1, 'med': 2, 'low': 3, 'vlow': 4, 'unknown': 5}


def model_family_key(name_or_path: str) -> str:
    """Return a conservative family key for LOD sibling grouping.

    It removes only common trailing LOD markers, so selecting `canoe_med.wft`
    can pull `canoe_hi.wft` / `canoe_low.wft`, but it will not pull random
    same-folder meshes.
    """
    stem = Path(str(name_or_path or '')).stem.lower()
    stem = re.sub(r'(?i)([_\-.])(hi|high|hilod|med|medium|medlod|low|lowlod|vlow|vlo|verylow|slod|lod[0-9])$', '', stem)
    stem = re.sub(r'(?i)([_\-.])(drawable|model|mesh)$', '', stem)
    return stem.strip('_.-') or Path(str(name_or_path or 'asset')).stem.lower()


def lod_label(name_or_path: str) -> str:
    stem = Path(str(name_or_path or '')).stem.lower()
    for label, pat in LOD_PATTERNS:
        if pat.search(stem):
            return label
    return 'unknown'


def lod_sort_key(entry: dict) -> tuple:
    label = lod_label(entry.get('name') or entry.get('path') or '')
    return (LOD_ORDER.get(label, 9), -int(entry.get('size_in_archive') or 0), str(entry.get('path') or ''))


def same_parent_path(entry: dict) -> str:
    return str(Path(str(entry.get('path') or '')).parent).lower()


def archive_model_family(archive_info: dict | None, archive_entry: dict | None, max_members: int = 12) -> list[dict]:
    if not archive_info or not archive_entry:
        return []
    primary_parent = same_parent_path(archive_entry)
    primary_key = model_family_key(archive_entry.get('name') or archive_entry.get('path') or '')
    rows = []
    for ent in archive_info.get('entries', []):
        if ent.get('type') != 'file':
            continue
        ext = (ent.get('extension') or '').lower()
        if ext not in RENDER_MODEL_EXTS:
            continue
        if same_parent_path(ent) != primary_parent:
            continue
        key = model_family_key(ent.get('name') or ent.get('path') or '')
        if key != primary_key:
            continue
        rows.append(dict(ent))
    rows.sort(key=lod_sort_key)
    # Keep primary first in tie-sensitive UIs but still expose ordered LOD labels.
    for row in rows:
        row['family_key'] = primary_key
        row['lod_label'] = lod_label(row.get('name') or row.get('path') or '')
        row['is_primary'] = row.get('index') == archive_entry.get('index')
    return rows[:max_members]


def _extract_embedded_texture_blobs(payload: bytes, out_dir: Path, prefix: str, start_index: int = 0, max_count: int = 16) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    idx = start_index
    png_sig = b'\x89PNG\r\n\x1a\n'
    for match in re.finditer(re.escape(png_sig), payload or b''):
        if len(rows) >= max_count:
            break
        end = payload.find(b'IEND', match.start())
        if end >= 0:
            end += 8
            out = out_dir / f'{safe_filename(prefix)}_embedded_{idx:03d}.png'
            out.write_bytes(payload[match.start():end])
            rows.append({'kind': 'embedded_png', 'path': out.name, 'offset': match.start(), 'size': out.stat().st_size})
            idx += 1
    dds_positions = [m.start() for m in re.finditer(b'DDS ', payload or b'')]
    for pos_i, pos in enumerate(dds_positions):
        if len(rows) >= max_count:
            break
        end = dds_positions[pos_i + 1] if pos_i + 1 < len(dds_positions) else min(len(payload), pos + 8 * 1024 * 1024)
        out = out_dir / f'{safe_filename(prefix)}_embedded_{idx:03d}.dds'
        out.write_bytes(payload[pos:end])
        rows.append({'kind': 'embedded_dds', 'path': out.name, 'offset': pos, 'size': out.stat().st_size})
        idx += 1
    return rows


def decode_texture_container_bytes(raw: bytes, texture_name: str, out_dir: Path, max_count: int = 24) -> dict:
    """Extract viewable texture blobs from a direct image or texture dictionary-like file."""
    out_dir.mkdir(parents=True, exist_ok=True)
    name = safe_filename(texture_name or 'texture')
    ext = Path(name).suffix.lower()
    report = {'source': texture_name, 'decoded': [], 'refs': {}, 'payload_bytes': 0, 'notes': []}
    if ext in {'.dds', '.png'}:
        out = out_dir / name
        out.write_bytes(raw)
        report['decoded'].append({'kind': f'direct_{ext[1:]}', 'path': out.name, 'size': len(raw)})
        report['payload_bytes'] = len(raw)
        return report
    resource = parse_resource_header(raw)
    payload_info = extract_resource_payload(raw, resource)
    payload = payload_info.get('payload') or raw
    report['payload_bytes'] = len(payload)
    report['notes'] = payload_info.get('notes', [])
    refs, _bones = scan_refs(payload)
    report['refs'] = refs
    report['decoded'] = _extract_embedded_texture_blobs(payload, out_dir, Path(name).stem, 0, max_count)
    if not report['decoded']:
        sidecar = out_dir / f'{Path(name).stem}.texture_payload.bin'
        sidecar.write_bytes(payload)
        report['sidecar'] = sidecar.name
        report['notes'].append('No direct DDS/PNG blob was found; wrote texture payload sidecar for inspection.')
    return report


def write_family_obj(path: Path, member_rows: list[dict], faces: bool = True, mtl_name: str | None = None) -> int:
    vertex_base = 1
    face_total = 0
    with Path(path).open('w', encoding='utf-8') as f:
        f.write('# Code RED Model XML family OBJ preview\n')
        f.write('# Combines the best detected position stream from each matching LOD sibling.\n')
        if mtl_name:
            f.write(f'mtllib {mtl_name}\n')
        for member in member_rows:
            points = member.get('points') or []
            if not points:
                continue
            group_name = safe_filename(member.get('name') or 'member')
            f.write(f'o {group_name}\n')
            f.write(f'g {group_name}\n')
            f.write('usemtl material_0\n')
            for x, y, z in points:
                f.write(f'v {x:.6f} {y:.6f} {z:.6f}\n')
            if faces:
                usable = (len(points) // 3) * 3
                for i in range(0, usable, 3):
                    if _triangle_area_ok(points[i], points[i + 1], points[i + 2]):
                        f.write(f'f {vertex_base + i} {vertex_base + i + 1} {vertex_base + i + 2}\n')
                        face_total += 1
            vertex_base += len(points)
        f.write(f'# preview_faces={face_total}\n')
    return face_total


def write_basic_mtl(path: Path, textures: list[dict]) -> str:
    chosen = ''
    for row in textures:
        candidate = row.get('decoded_path') or row.get('path') or ''
        if candidate.lower().endswith(('.png', '.dds')):
            chosen = candidate
            break
    with Path(path).open('w', encoding='utf-8') as f:
        f.write('# Code RED Model XML material preview\n')
        f.write('newmtl material_0\n')
        f.write('Kd 0.8 0.8 0.8\n')
        if chosen:
            f.write(f'map_Kd textures_decoded/{Path(chosen).name}\n')
    return chosen


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
    for ext in ['.dds', '.png', '.wtd', '.wtx', '.wsf', '.xtd', '.xtx', '.xsf', '.wtb', '.wvd', '.wfd', '.wft', '.xvd', '.xfd', '.xft', '.wbd', '.wedt', '.xedt', '.yedt', '.fxc']:
        refs[ext] = sorted({s for s in strings if ext in s.lower()})[:160]
    bone_hints = sorted({
        s for s in strings
        if any(tok in s.lower() for tok in ('bone', 'spine', 'pelvis', 'head', 'neck', 'arm', 'leg', 'root', 'tail', 'finger'))
    })[:120]
    return refs, bone_hints



EDITABLE_REF_EXTS = ('.dds', '.png', '.wtd', '.wtx', '.wsf', '.xtd', '.xtx', '.xsf', '.fxc')
MODEL_REF_EXTS = ('.wft', '.wfd', '.wvd', '.xft', '.xfd', '.xvd', '.wbd', '.wsi', '.wsp', '.wsg', '.wtl', '.wedt', '.xedt', '.yedt')


def _xml_attr(value: object) -> str:
    return escape(str(value or ''), {'"': '&quot;'})


def _classify_editable_string(text: str) -> str:
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


def scan_editable_strings(data: bytes, limit: int = 900) -> list[dict]:
    rows: list[dict] = []
    fallback: list[dict] = []
    for match in re.finditer(rb'[A-Za-z0-9_./:\\-]{4,160}', data or b''):
        raw = match.group()
        text = raw.decode('latin-1', errors='ignore')
        group = _classify_editable_string(text)
        priority = {'texture-ref': 0, 'model-ref': 1, 'bone-name': 2, 'path': 3, 'string': 4}.get(group, 9)
        row = {
            'id': f's{len(rows):04d}',
            'offset': int(match.start()),
            'length': int(len(raw)),
            'group': group,
            'original': text,
            'value': text,
            'priority': priority,
        }
        # Keep real references editable and avoid filling the XML with random
        # printable bytes from vertex/buffer data. A small fallback is kept only
        # when no meaningful references are present.
        if group in {'texture-ref', 'model-ref', 'bone-name'} or (group == 'path' and any(ch in text for ch in './\\')):
            rows.append(row)
        elif len(fallback) < 60:
            fallback.append(row)
    if not rows:
        rows = fallback
    rows.sort(key=lambda r: (r['priority'], r['offset']))
    selected = rows[:limit]
    selected.sort(key=lambda r: r['offset'])
    for i, row in enumerate(selected):
        row['id'] = f's{i:04d}'
        row.pop('priority', None)
    return selected


def write_edit_text(path: Path, editable_strings: list[dict]) -> None:
    lines = [
        '# Code RED Model XML editable text sheet',
        '# Edit the value="..." attributes in the XML for safest import.',
        '# This TXT file is also read on import for lines shaped exactly like:',
        '# replace OLD => NEW',
        '# Replacement text must be the same byte length or shorter; shorter values are NUL-padded to keep file size unchanged.',
        '',
    ]
    for row in editable_strings[:500]:
        original = str(row.get('original', '')).replace('\\', '\\\\')
        lines.append(f'# {row.get("id")} offset={row.get("offset")} bytes={row.get("length")} group={row.get("group")}')
        lines.append(f'# replace {original} => {original}')
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')

def triplet_ok(x, y, z):
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


def model_candidates(payload: bytes, limit=5, max_samples_per_layout=2500):
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
                if triplet_ok(x, y, z):
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


def write_obj(path: Path, points, faces=False, mtl_name: str | None = None, material: str = 'material_0'):
    with Path(path).open('w', encoding='utf-8') as f:
        f.write('# Code RED Model XML OBJ preview\n')
        f.write('# Generated from a detected float position stream.\n')
        f.write('# For edit safety, XML/raw-resource import remains the source of truth.\n')
        if mtl_name:
            f.write(f'mtllib {mtl_name}\n')
            f.write(f'usemtl {material}\n')
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


def extract_vertices_for_stream(payload: bytes, stream: dict, max_vertices: int = 65000):
    """Build a slot-indexed vertex table for a detected stream.

    The preview detector samples aggressively, which is good for speed but not
    enough for reconstructing faces. This pass adds a safer full-window read of
    the selected stream so possible index-buffer runs can point back to the
    right vertex slots.
    """
    stride = int(stream.get('stride') or 0)
    offset = int(stream.get('offset') or 0)
    total = int(stream.get('count') or 0)
    if stride < 12 or offset < 0 or total <= 0:
        return [], {}
    limit = min(total, max_vertices)
    vertices = []
    slot_to_vertex = {}
    for slot in range(limit):
        pos = offset + slot * stride
        if pos + 12 > len(payload):
            break
        try:
            x, y, z = struct.unpack_from('<fff', payload, pos)
        except Exception:
            break
        if not triplet_ok(float(x), float(y), float(z)):
            continue
        slot_to_vertex[slot] = len(vertices) + 1
        vertices.append((float(x), float(y), float(z)))
    return vertices, slot_to_vertex


def _face_from_indices(values, slot_to_vertex: dict, vertices: list[tuple[float, float, float]]):
    if values[0] == values[1] or values[1] == values[2] or values[0] == values[2]:
        return None
    try:
        face = (slot_to_vertex[values[0]], slot_to_vertex[values[1]], slot_to_vertex[values[2]])
    except KeyError:
        return None
    a, b, c = vertices[face[0] - 1], vertices[face[1] - 1], vertices[face[2] - 1]
    return face if _triangle_area_ok(a, b, c) else None


def find_index_faces(payload: bytes, slot_to_vertex: dict, vertices: list[tuple[float, float, float]], max_scan_bytes: int = 8_000_000, max_faces: int = 24000) -> dict:
    """Find a plausible compact index-buffer run for the detected vertices.

    This is intentionally proof-oriented: it does not claim perfect format
    decoding, but when a strong uint16/uint32 run exists it produces a much more
    model-like OBJ than sequential triples.
    """
    if len(vertices) < 24 or not slot_to_vertex:
        return {'ok': False, 'faces': [], 'reason': 'not enough vertices'}
    max_slot = max(slot_to_vertex)
    scan_len = min(len(payload), max_scan_bytes)
    best = {'ok': False, 'faces': [], 'index_width': 0, 'offset': 0, 'face_count': 0, 'reason': 'no plausible index run found'}
    for width, fmt in ((2, '<H'), (4, '<I')):
        # uint32 scans are more expensive and much less likely in the tiny test resources.
        if width == 4 and max_slot <= 65535:
            pass
        for align in range(width):
            i = align
            current = []
            current_start = align
            while i + width * 3 <= scan_len:
                try:
                    a = struct.unpack_from(fmt, payload, i)[0]
                    b = struct.unpack_from(fmt, payload, i + width)[0]
                    c = struct.unpack_from(fmt, payload, i + width * 2)[0]
                except Exception:
                    break
                face = None
                if a <= max_slot and b <= max_slot and c <= max_slot:
                    face = _face_from_indices((int(a), int(b), int(c)), slot_to_vertex, vertices)
                if face:
                    if not current:
                        current_start = i
                    current.append(face)
                    if len(current) >= max_faces:
                        break
                    i += width * 3
                    continue
                if len(current) > best.get('face_count', 0):
                    best = {'ok': True, 'faces': current[:], 'index_width': width, 'offset': current_start, 'face_count': len(current), 'max_slot': max_slot}
                current = []
                i += width
            if len(current) > best.get('face_count', 0):
                best = {'ok': True, 'faces': current[:], 'index_width': width, 'offset': current_start, 'face_count': len(current), 'max_slot': max_slot}
    if best.get('face_count', 0) < 32:
        return {'ok': False, 'faces': [], 'reason': f'best run had only {best.get("face_count", 0)} faces', 'best_face_count': best.get('face_count', 0)}
    return best


def write_indexed_preview_obj(path: Path, payload: bytes, stream: dict, mtl_name: str | None = None) -> dict:
    vertices, slot_to_vertex = extract_vertices_for_stream(payload, stream)
    index_result = find_index_faces(payload, slot_to_vertex, vertices)
    if not index_result.get('ok'):
        return {'ok': False, 'path': '', 'vertex_count': len(vertices), **{k: v for k, v in index_result.items() if k != 'faces'}}
    with Path(path).open('w', encoding='utf-8') as f:
        f.write('# Code RED Model XML indexed OBJ preview\n')
        f.write('# Faces were reconstructed from a detected index-like buffer run. Verify visually before treating as final topology.\n')
        if mtl_name:
            f.write(f'mtllib {mtl_name}\nusemtl material_0\n')
        for x, y, z in vertices:
            f.write(f'v {x:.6f} {y:.6f} {z:.6f}\n')
        for a, b, c in index_result['faces']:
            f.write(f'f {a} {b} {c}\n')
    return {
        'ok': True,
        'path': str(path),
        'vertex_count': len(vertices),
        'face_count': int(index_result.get('face_count', 0)),
        'index_width': int(index_result.get('index_width', 0)),
        'index_offset': int(index_result.get('offset', 0)),
        'max_slot': int(index_result.get('max_slot', 0)),
    }


def build_model_assembly(stem: str, family_members: list[dict], texture_dictionaries: list[dict], textures: list[dict], structure_companions: list[dict], refs: dict) -> dict:
    lods = {}
    for member in family_members:
        label = member.get('lod') or 'unknown'
        lods.setdefault(label, []).append({k: member.get(k) for k in ('name', 'archive_path', 'raw_path', 'payload_sidecar', 'obj_preview', 'obj_pointcloud', 'indexed_obj_preview', 'raw_bytes', 'payload_bytes', 'is_primary')})
    texture_refs = []
    for ext, items in (refs or {}).items():
        if ext.lower() in TEXTURE_EXTS:
            texture_refs.extend(items)
    structure_refs = []
    for row in structure_companions:
        row_refs = []
        for ext, items in (row.get('refs') or {}).items():
            if ext.lower() in MODEL_EXTS or ext.lower() in STRUCTURE_EXTS or ext.lower() in TEXTURE_EXTS:
                row_refs.extend(items[:25])
        structure_refs.append({
            'name': row.get('name', ''),
            'extension': row.get('extension', ''),
            'archive_path': row.get('archive_path', ''),
            'raw_path': row.get('raw_path', ''),
            'payload_sidecar': row.get('payload_sidecar', ''),
            'score': row.get('score', 0),
            'reasons': row.get('reasons', []),
            'refs': sorted(set(row_refs))[:80],
            'heuristic_stream_count': len(row.get('heuristic_streams') or []),
        })
    return {
        'asset_family': model_family_key(stem),
        'lod_order': [label for label in ('hi', 'main', 'med', 'low', 'vlow', 'unknown') if label in lods],
        'lods': lods,
        'texture_refs': sorted(set(texture_refs))[:240],
        'texture_dictionaries': texture_dictionaries,
        'textures': textures,
        'structure_companions': structure_refs,
        'assembly_notes': [
            'LOD siblings are grouped by same parent folder and same model-family suffix stripping.',
            'Texture dictionaries are attached only by explicit refs or strict same-family/same-parent matches.',
            'Structure companions are exported as assembly evidence; they are not blindly merged as meshes.',
            'Indexed OBJ preview is emitted only when a strong index-like run is found.'
        ],
    }


def write_assembly_text(path: Path, assembly: dict) -> None:
    lines = ['Code RED Model Assembly Map', '===========================', '']
    lines.append(f'Family: {assembly.get("asset_family", "")}')
    lines.append('')
    lines.append('LOD members:')
    for label in assembly.get('lod_order', []):
        for member in assembly.get('lods', {}).get(label, []):
            lines.append(f'- {label}: {member.get("name", "")}  raw={member.get("raw_path", "")}  obj={member.get("obj_preview", "")}  indexed={member.get("indexed_obj_preview", "")}')
    lines.append('')
    lines.append('Texture dictionaries / decoded textures:')
    for tex in assembly.get('texture_dictionaries', []):
        lines.append(f'- {tex.get("name", "")} score={tex.get("score", 0)} decoded={tex.get("decoded_count", 0)} reasons={",".join(tex.get("reasons", []) or [])}')
    if not assembly.get('texture_dictionaries'):
        lines.append('- none matched')
    lines.append('')
    lines.append('Structure companions:')
    for comp in assembly.get('structure_companions', []):
        lines.append(f'- {comp.get("name", "")} {comp.get("extension", "")} score={comp.get("score", 0)} refs={len(comp.get("refs", []) or [])} reasons={",".join(comp.get("reasons", []) or [])}')
    if not assembly.get('structure_companions'):
        lines.append('- none matched')
    lines.append('')
    lines.append('Texture refs seen in model payload:')
    for ref in assembly.get('texture_refs', [])[:120]:
        lines.append(f'- {ref}')
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def archive_companions(archive_path: Path, archive_info: dict, archive_entry: dict, refs: dict, limit=24):
    current_path = str(archive_entry.get('path') or archive_entry.get('name') or '')
    current_parent = str(Path(current_path).parent).lower()
    current_stem = Path(archive_entry.get('name') or current_path).stem.lower()
    current_family = model_family_key(current_stem)
    ref_names = set()
    ref_stems = set()
    for ext, items in (refs or {}).items():
        # Only texture/image references are allowed to pull companion files into the texture bundle.
        if ext.lower() not in TEXTURE_EXTS:
            continue
        for item in items:
            ref_names.add(Path(item).name.lower())
            ref_stems.add(Path(item).stem.lower())
    rows = []
    for ent in archive_info.get('entries', []):
        if ent.get('type') != 'file' or ent.get('index') == archive_entry.get('index'):
            continue
        ext = (ent.get('extension') or '').lower()
        if ext not in TEXTURE_EXTS:
            continue
        ep = str(ent.get('path') or '').lower()
        parent = str(Path(ep).parent).lower()
        en = str(ent.get('name') or '').lower()
        es = Path(en).stem.lower()
        family = model_family_key(es)
        score = 0
        reasons = []
        if en in ref_names or es in ref_stems:
            score += 360
            reasons.append('explicit-texture-ref')
        if parent == current_parent and family == current_family:
            score += 180
            reasons.append('same-family-texture-dictionary')
        if parent == current_parent and current_stem and (es == current_stem or es.startswith(current_stem + '_') or current_stem.startswith(es + '_')):
            score += 100
            reasons.append('same-stem-texture-name')
        if score <= 0:
            continue
        if ext in {'.dds', '.png'}:
            score += 40
            reasons.append('direct-image')
        elif ext in {'.xtd', '.wtd', '.wtx', '.xtx'}:
            score += 30
            reasons.append('texture-container')
        rows.append({'score': score, 'entry': ent, 'reasons': reasons})
    rows.sort(key=lambda r: (-r['score'], r['entry'].get('path', '')))
    return rows[:limit]



def archive_structure_companions(archive_path: Path, archive_info: dict, archive_entry: dict, refs: dict, limit=24):
    """Find likely layout/entity/structure companions for the selected model.

    This is intentionally conservative: it prefers same parent + same model
    family, explicit model refs, and EDT/WBD-style resource files. It should not
    drag unrelated same-folder meshes into the exported model bundle.
    """
    current_path = str(archive_entry.get('path') or archive_entry.get('name') or '')
    current_parent = str(Path(current_path).parent).lower()
    current_stem = Path(archive_entry.get('name') or current_path).stem.lower()
    current_family = model_family_key(current_stem)
    ref_names = set()
    ref_stems = set()
    for ext, items in (refs or {}).items():
        if ext.lower() not in MODEL_EXTS and ext.lower() not in STRUCTURE_EXTS:
            continue
        for item in items:
            ref_names.add(Path(item).name.lower())
            ref_stems.add(Path(item).stem.lower())
    rows = []
    for ent in archive_info.get('entries', []):
        if ent.get('type') != 'file' or ent.get('index') == archive_entry.get('index'):
            continue
        ext = (ent.get('extension') or '').lower()
        if ext not in STRUCTURE_EXTS:
            continue
        ep = str(ent.get('path') or '').lower()
        parent = str(Path(ep).parent).lower()
        en = str(ent.get('name') or '').lower()
        es = Path(en).stem.lower()
        family = model_family_key(es)
        score = 0
        reasons = []
        if en in ref_names or es in ref_stems:
            score += 400
            reasons.append('explicit-structure-ref')
        if parent == current_parent and family == current_family:
            score += 260
            reasons.append('same-family-structure')
        if parent == current_parent and current_stem and (es == current_stem or es.startswith(current_stem + '_') or current_stem.startswith(es + '_')):
            score += 140
            reasons.append('same-stem-structure')
        if ext in {'.wedt', '.xedt', '.yedt'}:
            score += 80
            reasons.append('edt-layout-candidate')
        if ext in {'.wbd', '.wtl', '.wsi', '.wsp', '.wsg'}:
            score += 30
            reasons.append('model-structure-candidate')
        if score <= 0:
            continue
        rows.append({'score': score, 'entry': ent, 'reasons': reasons})
    rows.sort(key=lambda r: (-r['score'], r['entry'].get('path', '')))
    return rows[:limit]


def summarize_structure_resource(raw: bytes, name: str, out_payload_path: Path | None = None) -> dict:
    resource = parse_resource_header(raw)
    payload_info = extract_resource_payload(raw, resource)
    payload = payload_info.get('payload') or raw
    if out_payload_path:
        out_payload_path.parent.mkdir(parents=True, exist_ok=True)
        out_payload_path.write_bytes(payload)
    refs, bone_hints = scan_refs(payload)
    streams = model_candidates(payload, limit=2)
    return {
        'name': name,
        'resource': resource,
        'raw_bytes': len(raw),
        'payload_bytes': len(payload),
        'payload_notes': payload_info.get('notes', []),
        'refs': refs,
        'bone_hints': bone_hints[:40],
        'heuristic_streams': [{k: v for k, v in row.items() if k != 'points'} for row in streams],
    }

def create_bundle(asset_name: str, data: bytes, out_root: Path, archive_path: Path | None = None, archive_entry: dict | None = None, archive_info: dict | None = None, max_textures=24, include_family: bool = True):
    stamp = time.strftime('%Y%m%d_%H%M%S')
    stem = Path(asset_name).stem or 'asset'
    bundle = Path(out_root) / f'{safe_filename(stem)}_modelxml_bundle_{stamp}'
    textures_dir = bundle / 'textures'
    textures_decoded_dir = bundle / 'textures_decoded'
    lods_dir = bundle / 'model_lods'
    structure_dir = bundle / 'structure'
    sidecars_dir = bundle / 'sidecars'
    lod_sidecars_dir = sidecars_dir / 'model_lods'
    structure_sidecars_dir = sidecars_dir / 'structure'
    textures_dir.mkdir(parents=True, exist_ok=True)
    textures_decoded_dir.mkdir(parents=True, exist_ok=True)
    lods_dir.mkdir(parents=True, exist_ok=True)
    structure_dir.mkdir(parents=True, exist_ok=True)
    sidecars_dir.mkdir(parents=True, exist_ok=True)
    lod_sidecars_dir.mkdir(parents=True, exist_ok=True)
    structure_sidecars_dir.mkdir(parents=True, exist_ok=True)

    raw_path = bundle / safe_filename(asset_name)
    raw_path.write_bytes(data)
    resource = parse_resource_header(data)
    payload_info = extract_resource_payload(data, resource)
    payload = payload_info.get('payload') or data
    payload_path = sidecars_dir / f'{safe_filename(asset_name)}.payload.bin'
    payload_path.write_bytes(payload)

    refs, bone_hints = scan_refs(payload)
    editable_strings = scan_editable_strings(data)
    edit_txt_path = bundle / f'{safe_filename(stem)}.model_edits.txt'
    write_edit_text(edit_txt_path, editable_strings)
    streams = model_candidates(payload)
    obj_path = None
    obj_point_path = None
    indexed_obj_path = None
    indexed_obj_report = {'ok': False, 'reason': 'no stream'}
    preview_mtl_path = None
    preview_texture_choice = ''
    if streams:
        obj_point_path = bundle / f'{safe_filename(stem)}_points.obj'
        obj_path = bundle / f'{safe_filename(stem)}_tri_preview.obj'
        indexed_obj_path = bundle / f'{safe_filename(stem)}_indexed_preview.obj'

    textures = []
    texture_dictionaries = []
    # Embedded PNG/DDS scan from the model payload itself.
    for row in _extract_embedded_texture_blobs(payload, textures_decoded_dir, safe_filename(stem), 0, max_textures):
        row['kind'] = 'model_' + row.get('kind', 'embedded')
        row['decoded_path'] = row.get('path', '')
        textures.append(row)

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
            tex_report = decode_texture_container_bytes(companion_data, ent.get('name') or out.name, textures_decoded_dir, max_count=max(1, max_textures - len(textures)))
            decoded = tex_report.get('decoded') or []
            if decoded:
                for dec in decoded:
                    textures.append({'kind': 'decoded_texture', 'path': out.name, 'decoded_path': dec.get('path', ''), 'archive_path': ent.get('path', ''), 'score': row['score'], 'reasons': row['reasons'], 'size': dec.get('size', 0)})
            else:
                textures.append({'kind': 'archive_texture_container', 'path': out.name, 'archive_path': ent.get('path', ''), 'score': row['score'], 'reasons': row['reasons'], 'size': len(companion_data), 'sidecar': tex_report.get('sidecar', '')})
            texture_dictionaries.append({'archive_path': ent.get('path', ''), 'name': ent.get('name', ''), 'score': row['score'], 'reasons': row['reasons'], 'raw_path': out.name, 'decoded_count': len(decoded), 'payload_bytes': tex_report.get('payload_bytes', 0), 'refs': tex_report.get('refs', {})})

    structure_companions = []
    if archive_path and archive_entry and archive_info:
        for row in archive_structure_companions(archive_path, archive_info, archive_entry, refs, limit=24):
            ent = row['entry']
            try:
                companion_data = extract_rpf_entry(archive_path, ent)
                out = structure_dir / safe_filename(ent.get('name') or f'entry_{ent["index"]}.bin')
                if out.exists():
                    out = structure_dir / f'{ent["index"]:04d}_{out.name}'
                out.write_bytes(companion_data)
                payload_out = structure_sidecars_dir / f'{out.name}.payload.bin'
                summary = summarize_structure_resource(companion_data, ent.get('name') or out.name, payload_out)
                structure_companions.append({
                    'name': ent.get('name', ''),
                    'archive_path': ent.get('path', ''),
                    'index': ent.get('index'),
                    'extension': ent.get('extension', ''),
                    'score': row['score'],
                    'reasons': row['reasons'],
                    'raw_path': str(out.relative_to(bundle)),
                    'payload_sidecar': str(payload_out.relative_to(bundle)),
                    'raw_bytes': len(companion_data),
                    'payload_bytes': summary.get('payload_bytes', 0),
                    'resource': summary.get('resource'),
                    'refs': summary.get('refs', {}),
                    'bone_hints': summary.get('bone_hints', []),
                    'heuristic_streams': summary.get('heuristic_streams', []),
                })
            except Exception as exc:
                structure_companions.append({'name': ent.get('name', ''), 'archive_path': ent.get('path', ''), 'index': ent.get('index'), 'error': str(exc), 'score': row.get('score', 0), 'reasons': row.get('reasons', [])})

    # Now that texture dictionaries have been collected, write OBJ previews with an MTL
    # so external OBJ viewers can at least attach the best decoded texture candidate.
    if streams:
        preview_mtl_path = bundle / f'{safe_filename(stem)}_preview.mtl'
        preview_texture_choice = write_basic_mtl(preview_mtl_path, textures)
        write_obj(obj_point_path, streams[0]['points'], faces=False, mtl_name=preview_mtl_path.name)
        write_obj(obj_path, streams[0]['points'], faces=True, mtl_name=preview_mtl_path.name)
        indexed_obj_report = write_indexed_preview_obj(indexed_obj_path, payload, streams[0], mtl_name=preview_mtl_path.name)
        if not indexed_obj_report.get('ok'):
            indexed_obj_path = None

    family_members = []
    family_obj_path = None
    family_mtl_path = None
    family_face_count = 0
    if include_family and archive_path and archive_entry and archive_info:
        for ent in archive_model_family(archive_info, archive_entry, max_members=12):
            try:
                member_data = data if ent.get('index') == archive_entry.get('index') else extract_rpf_entry(archive_path, ent)
                member_resource = parse_resource_header(member_data)
                member_payload_info = extract_resource_payload(member_data, member_resource)
                member_payload = member_payload_info.get('payload') or member_data
                member_streams = streams if ent.get('index') == archive_entry.get('index') else model_candidates(member_payload, limit=3)
                raw_member_path = lods_dir / safe_filename(ent.get('name') or f'entry_{ent["index"]}.bin')
                if ent.get('index') != archive_entry.get('index'):
                    raw_member_path.write_bytes(member_data)
                else:
                    # Keep a light pointer copy for a complete family folder without duplicating the primary root copy in reports.
                    raw_member_path.write_bytes(member_data)
                member_payload_path = lod_sidecars_dir / f'{raw_member_path.name}.payload.bin'
                member_payload_path.write_bytes(member_payload)
                member_obj = ''
                member_points_obj = ''
                member_indexed_obj = ''
                member_indexed_report = {'ok': False, 'reason': 'no stream'}
                best_points = []
                if member_streams:
                    best_points = member_streams[0].get('points') or []
                    member_tag = safe_filename(raw_member_path.name).replace('.', '_')
                    member_points_obj_path = lods_dir / f'{member_tag}_points.obj'
                    member_obj_path = lods_dir / f'{member_tag}_tri_preview.obj'
                    member_indexed_obj_path = lods_dir / f'{member_tag}_indexed_preview.obj'
                    write_obj(member_points_obj_path, best_points, faces=False, mtl_name=(('../' + preview_mtl_path.name) if preview_mtl_path else None))
                    write_obj(member_obj_path, best_points, faces=True, mtl_name=(('../' + preview_mtl_path.name) if preview_mtl_path else None))
                    member_indexed_report = write_indexed_preview_obj(member_indexed_obj_path, member_payload, member_streams[0], mtl_name=(('../' + preview_mtl_path.name) if preview_mtl_path else None))
                    member_obj = str(member_obj_path.relative_to(bundle))
                    member_points_obj = str(member_points_obj_path.relative_to(bundle))
                    if member_indexed_report.get('ok'):
                        member_indexed_obj = str(member_indexed_obj_path.relative_to(bundle))
                family_members.append({
                    'name': ent.get('name', ''),
                    'archive_path': ent.get('path', ''),
                    'index': ent.get('index'),
                    'lod': ent.get('lod_label') or lod_label(ent.get('name') or ent.get('path') or ''),
                    'family_key': ent.get('family_key') or model_family_key(ent.get('name') or ent.get('path') or ''),
                    'is_primary': bool(ent.get('index') == archive_entry.get('index')),
                    'raw_path': str(raw_member_path.relative_to(bundle)),
                    'payload_sidecar': str(member_payload_path.relative_to(bundle)),
                    'raw_bytes': len(member_data),
                    'payload_bytes': len(member_payload),
                    'obj_preview': member_obj,
                    'obj_pointcloud': member_points_obj,
                    'indexed_obj_preview': member_indexed_obj,
                    'indexed_obj_report': {k: v for k, v in member_indexed_report.items() if k != 'faces'},
                    'heuristic_streams': [{k: v for k, v in row.items() if k != 'points'} for row in member_streams],
                    'points': best_points,
                })
            except Exception as exc:
                family_members.append({'name': ent.get('name', ''), 'archive_path': ent.get('path', ''), 'index': ent.get('index'), 'error': str(exc)})
        if family_members:
            family_mtl_path = bundle / f'{safe_filename(stem)}_family_preview.mtl'
            write_basic_mtl(family_mtl_path, textures)
            family_obj_path = bundle / f'{safe_filename(stem)}_family_tri_preview.obj'
            family_face_count = write_family_obj(family_obj_path, family_members, faces=True, mtl_name=family_mtl_path.name)

    assembly = build_model_assembly(stem, family_members, texture_dictionaries, textures, structure_companions, refs)
    assembly_json_path = bundle / f'{safe_filename(stem)}.model_assembly.json'
    assembly_txt_path = bundle / f'{safe_filename(stem)}.model_assembly.txt'
    assembly_json_path.write_text(json.dumps(assembly, indent=2), encoding='utf-8')
    write_assembly_text(assembly_txt_path, assembly)

    stream_manifest = [{k: v for k, v in row.items() if k != 'points'} for row in streams]
    best_stream = stream_manifest[0] if stream_manifest else {}
    best_bounds = best_stream.get('bounds') or ((0, 0), (0, 0), (0, 0))
    best_extents = best_stream.get('extents') or (0, 0, 0)
    model_profile = {
        'raw_bytes': len(data),
        'payload_bytes': len(payload),
        'resource_header_bytes': max(0, len(data) - len(payload)) if resource else 0,
        'resource_total_size': int((resource or {}).get('total_size', 0) or 0),
        'archive_packed_bytes': int((archive_entry or {}).get('size_in_archive', 0) or 0),
        'archive_total_size': int((archive_entry or {}).get('total_size', 0) or 0),
        'best_stream': {k: v for k, v in best_stream.items() if k not in {'bounds', 'extents'}},
        'bounds': best_bounds,
        'dimensions': best_extents,
        'xml_import_mode': 'raw-clone or payload-sidecar; full geometry rebuild remains dictionary-aware work',
    }
    xml_lines = ['<?xml version="1.0" encoding="utf-8"?>', '<CodeREDModelXMLBundle version="pass26" editPolicy="same-or-shorter-keeps-size">']
    xml_lines.append(f'  <Source name="{_xml_attr(asset_name)}" archive="{_xml_attr(str(archive_path or ""))}" internalPath="{_xml_attr(str((archive_entry or {}).get("path", "")))}" />')
    xml_lines.append(f'  <ImportSource rawFile="{_xml_attr(raw_path.name)}" payloadSidecar="sidecars/{_xml_attr(payload_path.name)}" editText="{_xml_attr(edit_txt_path.name)}" />')
    bx, by, bz = best_bounds
    dx, dy, dz = best_extents
    xml_lines.append('  <ModelProfile>')
    xml_lines.append(f'    <FileSizes rawBytes="{len(data)}" payloadBytes="{len(payload)}" headerBytes="{model_profile["resource_header_bytes"]}" archivePackedBytes="{model_profile["archive_packed_bytes"]}" archiveTotalSize="{model_profile["archive_total_size"]}" resourceTotalSize="{model_profile["resource_total_size"]}" />')
    xml_lines.append(f'    <DetectedDimensions x="{float(dx):.6g}" y="{float(dy):.6g}" z="{float(dz):.6g}" />')
    xml_lines.append(f'    <DetectedBounds minX="{float(bx[0]):.6g}" maxX="{float(bx[1]):.6g}" minY="{float(by[0]):.6g}" maxY="{float(by[1]):.6g}" minZ="{float(bz[0]):.6g}" maxZ="{float(bz[1]):.6g}" />')
    if best_stream:
        xml_lines.append(f'    <PrimaryStream stride="{best_stream.get("stride", 0)}" offset="{best_stream.get("offset", 0)}" points="{best_stream.get("count", 0)}" filtered="{best_stream.get("filtered_count", 0)}" score="{best_stream.get("score", 0)}" />')
    xml_lines.append('    <ImportPlan mode="editable-xml" notes="Import reads this XML, applies enabled same-size-safe edits, then writes the resource back into a copied archive slot." />')
    xml_lines.append('  </ModelProfile>')
    if resource:
        xml_lines.append(
            f'  <Resource ident="{resource["ident_name"]}" rawIdent="{resource["raw_ident_name"]}" resourceType="{resource["resource_type"]}" '
            f'flag1="0x{resource["flag1"]:08X}" flag2="0x{resource.get("flag2", 0):08X}" totalSize="{resource.get("total_size", 0)}" />'
        )
    xml_lines.append(f'  <Payload bytes="{len(payload)}" sidecar="sidecars/{_xml_attr(payload_path.name)}" />')
    xml_lines.append('  <EditableStrings offsetSpace="raw-resource" encoding="latin-1" lengthPolicy="same-or-shorter-null-padded">')
    for row in editable_strings:
        xml_lines.append(f'    <String id="{row["id"]}" offset="{row["offset"]}" length="{row["length"]}" group="{_xml_attr(row["group"])}" original="{_xml_attr(row["original"])}" value="{_xml_attr(row["value"])}" />')
    xml_lines.append('  </EditableStrings>')
    xml_lines.append('  <EditableBytePatches offsetSpace="raw-resource" encoding="hex">')
    xml_lines.append('    <Patch id="p0000" enabled="false" offset="0" length="0" hex="" />')
    xml_lines.append('  </EditableBytePatches>')
    xml_lines.append(f'  <ModelFamily key="{_xml_attr(model_family_key(asset_name))}" memberCount="{len(family_members)}" combinedOBJ="{_xml_attr(family_obj_path.name if family_obj_path else "")}" materialFile="{_xml_attr(family_mtl_path.name if family_mtl_path else "")}">')
    for member in family_members:
        xml_lines.append(f'    <Member name="{_xml_attr(member.get("name", ""))}" lod="{_xml_attr(member.get("lod", ""))}" primary="{str(bool(member.get("is_primary"))).lower()}" raw="{_xml_attr(member.get("raw_path", ""))}" payload="{_xml_attr(member.get("payload_sidecar", ""))}" obj="{_xml_attr(member.get("obj_preview", ""))}" pointsObj="{_xml_attr(member.get("obj_pointcloud", ""))}" indexedObj="{_xml_attr(member.get("indexed_obj_preview", ""))}" rawBytes="{int(member.get("raw_bytes", 0) or 0)}" payloadBytes="{int(member.get("payload_bytes", 0) or 0)}" />')
    xml_lines.append('  </ModelFamily>')
    xml_lines.append(f'  <ModelAssembly json="{_xml_attr(assembly_json_path.name)}" text="{_xml_attr(assembly_txt_path.name)}" textureCandidate="{_xml_attr(preview_texture_choice)}" indexedOBJ="{_xml_attr(indexed_obj_path.name if indexed_obj_path else "")}" indexedFaces="{int(indexed_obj_report.get("face_count", 0) or 0)}" />')
    xml_lines.append(f'  <StructureCompanions memberCount="{len(structure_companions)}" note="EDT/WBD/etc files can describe placement, entity/layout, bounds, or model dependency data. These are exported for inspection and future rebuild mapping.">')
    for row in structure_companions:
        xml_lines.append(f'    <Companion name="{_xml_attr(row.get("name", ""))}" ext="{_xml_attr(row.get("extension", ""))}" archivePath="{_xml_attr(row.get("archive_path", ""))}" raw="{_xml_attr(row.get("raw_path", ""))}" payload="{_xml_attr(row.get("payload_sidecar", ""))}" rawBytes="{int(row.get("raw_bytes", 0) or 0)}" payloadBytes="{int(row.get("payload_bytes", 0) or 0)}" score="{int(row.get("score", 0) or 0)}" reasons="{_xml_attr(",".join(row.get("reasons", []) or []))}" />')
    xml_lines.append('  </StructureCompanions>')
    xml_lines.append('  <TextureRefs>')
    for ext, items in refs.items():
        for item in items:
            xml_lines.append(f'    <Ref ext="{escape(ext)}">{escape(item)}</Ref>')
    xml_lines.append('  </TextureRefs>')
    xml_lines.append('  <BoneHints>')
    for item in bone_hints:
        xml_lines.append(f'    <Bone>{escape(item)}</Bone>')
    xml_lines.append('  </BoneHints>')
    if obj_path or obj_point_path or indexed_obj_path:
        xml_lines.append(f'  <OBJPreview triPreview="{_xml_attr(obj_path.name if obj_path else "")}" pointCloud="{_xml_attr(obj_point_path.name if obj_point_path else "")}" indexedPreview="{_xml_attr(indexed_obj_path.name if indexed_obj_path else "")}" materialFile="{_xml_attr(preview_mtl_path.name if preview_mtl_path else "")}" viewHint="Open with tools/codered_obj_viewer.py or View_Model_OBJ.bat" />')
    xml_lines.append('  <HeuristicStreams>')
    for row in stream_manifest:
        extents = row.get('extents') or (0, 0, 0)
        xml_lines.append(f'    <Stream score="{row.get("score", 0)}" stride="{row.get("stride", 0)}" offset="{row.get("offset", 0)}" points="{row.get("count", 0)}" filtered="{row.get("filtered_count", 0)}" extents="{float(extents[0]):.6g},{float(extents[1]):.6g},{float(extents[2]):.6g}" />')
    xml_lines.append('  </HeuristicStreams>')
    xml_lines.append('  <TextureDictionaries>')
    for row in texture_dictionaries:
        xml_lines.append(f'    <Dictionary name="{_xml_attr(row.get("name", ""))}" archivePath="{_xml_attr(row.get("archive_path", ""))}" raw="textures/{_xml_attr(row.get("raw_path", ""))}" decodedCount="{int(row.get("decoded_count", 0) or 0)}" score="{int(row.get("score", 0) or 0)}" />')
    xml_lines.append('  </TextureDictionaries>')
    xml_lines.append('  <Textures>')
    for row in textures:
        xml_lines.append(f'    <Texture kind="{escape(str(row.get("kind", "")))}" path="{escape(str(row.get("path", "")))}" size="{int(row.get("size", 0) or 0)}" />')
    xml_lines.append('  </Textures>')
    xml_lines.append('</CodeREDModelXMLBundle>')
    xml_path = bundle / f'{safe_filename(stem)}.modelxml.xml'
    xml_path.write_text('\n'.join(xml_lines) + '\n', encoding='utf-8')

    manifest = {
        'version': 'pass26-modelxml-indexed-assembly-bundle-cli',
        'asset_name': asset_name,
        'archive': str(archive_path or ''),
        'internal_path': str((archive_entry or {}).get('path', '')),
        'raw_bytes': len(data),
        'payload_bytes': len(payload),
        'model_profile': model_profile,
        'resource': resource,
        'edit_xml': str(xml_path),
        'edit_text': str(edit_txt_path),
        'editable_string_count': len(editable_strings),
        'payload_notes': payload_info.get('notes', []),
        'xml': str(xml_path),
        'obj_preview': str(obj_path) if obj_path else '',
        'obj_pointcloud': str(obj_point_path) if obj_point_path else '',
        'obj_indexed_preview': str(indexed_obj_path) if indexed_obj_path else '',
        'obj_indexed_report': {k: v for k, v in indexed_obj_report.items() if k != 'faces'},
        'obj_preview_material': str(preview_mtl_path) if preview_mtl_path else '',
        'obj_preview_texture': preview_texture_choice,
        'obj_family_preview': str(family_obj_path) if family_obj_path else '',
        'obj_family_material': str(family_mtl_path) if family_mtl_path else '',
        'family_face_count': family_face_count,
        'model_assembly_json': str(assembly_json_path),
        'model_assembly_text': str(assembly_txt_path),
        'model_assembly': assembly,
        'model_family': [{k: v for k, v in row.items() if k != 'points'} for row in family_members],
        'texture_dictionaries': texture_dictionaries,
        'structure_companions': structure_companions,
        'decoded_texture_count': sum(1 for row in textures if row.get('decoded_path') or str(row.get('path','')).lower().endswith(('.dds','.png'))),
        'texture_refs': refs,
        'bone_hints': bone_hints,
        'heuristic_streams': stream_manifest,
        'textures': textures,
        'warnings': [
            'Export bundle is safe/read-only against the source archive.',
            'XML contains editable string/reference fields; import preserves file size and blocks unsafe growth.',
            'OBJ previews are generated for viewing; XML/raw-resource import remains the safe edit path.',
            'EDT/WBD-style structure companions are exported for inspection, but full scene-layout rebuild is still guarded.',
            'Indexed OBJ preview is emitted when an index-like face run is confidently detected; otherwise sequential and point previews remain available.',
        ],
    }
    (bundle / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (bundle / 'extraction_report.txt').write_text(
        'Code RED Model XML Export Bundle\n'
        '==================================\n\n'
        f'Asset: {asset_name}\n'
        f'Archive: {archive_path or ""}\n'
        f'Internal path: {(archive_entry or {}).get("path", "")}\n'
        f'Raw bytes: {len(data):,}\n'
        f'Payload bytes: {len(payload):,}\n'
        f'Detected dimensions: {float(model_profile["dimensions"][0]):.6g}, {float(model_profile["dimensions"][1]):.6g}, {float(model_profile["dimensions"][2]):.6g}\n'
        f'Primary stream stride/offset: {model_profile["best_stream"].get("stride", 0)}/{model_profile["best_stream"].get("offset", 0)}\n'
        f'XML: {xml_path.name}\n'
        f'Editable TXT: {edit_txt_path.name}\n'
        f'Editable strings: {len(editable_strings)}\n'
        f'OBJ tri-preview: {Path(obj_path).name if obj_path else "not generated"}\n'
        f'OBJ point-cloud: {Path(obj_point_path).name if obj_point_path else "not generated"}\n'
        f'OBJ indexed-preview: {Path(indexed_obj_path).name if indexed_obj_path else "not generated"} faces={int(indexed_obj_report.get("face_count", 0) or 0)}\n'
        f'OBJ material: {Path(preview_mtl_path).name if preview_mtl_path else "not generated"} texture={preview_texture_choice or "none"}\n'
        f'Family OBJ preview: {Path(family_obj_path).name if family_obj_path else "not generated"}\n'
        f'Model assembly JSON: {assembly_json_path.name}\n'
        f'LOD/family members: {len(family_members)}\n'
        f'Texture refs: {sum(len(v) for v in refs.values())}\n'
        f'Texture files copied/extracted: {len(textures)}\n'
        f'Texture dictionaries matched: {len(texture_dictionaries)}\n'
        f'Structure/EDT companions matched: {len(structure_companions)}\n'
        f'Decoded texture files: {sum(1 for row in textures if row.get("decoded_path") or str(row.get("path","")).lower().endswith((".dds",".png")))}\n'
        f'Heuristic streams: {len(stream_manifest)}\n\n'
        'Payload notes:\n' + '\n'.join(f'- {line}' for line in payload_info.get('notes', [])) + '\n',
        encoding='utf-8',
    )
    return bundle, manifest


def main():
    parser = argparse.ArgumentParser(description='Code RED Model XML model export bundle tool.')
    parser.add_argument('--asset', type=Path, help='Direct WFT/WFD/WVD/WBD/WTB/etc file to export.')
    parser.add_argument('--archive', type=Path, help='RPF6 archive to extract from.')
    parser.add_argument('--entry', help='Case-insensitive substring for the internal entry path/name.')
    parser.add_argument('--out', type=Path, default=Path('exports/modelxml_bundles'), help='Output root folder.')
    parser.add_argument('--list', action='store_true', help='List model-like entries in an archive instead of exporting.')
    parser.add_argument('--no-family', action='store_true', help='Export only the selected model entry, without same-family LOD siblings.')
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
        bundle, manifest = create_bundle(entry.get('name') or f'entry_{entry["index"]}.bin', data, args.out, archive_path=args.archive, archive_entry=entry, archive_info=info, include_family=not args.no_family)
        print(json.dumps({'bundle': str(bundle), 'manifest': str(bundle / 'manifest.json'), 'xml': manifest.get('xml'), 'obj_preview': manifest.get('obj_preview'), 'obj_family_preview': manifest.get('obj_family_preview'), 'obj_indexed_preview': manifest.get('obj_indexed_preview'), 'indexed_faces': (manifest.get('obj_indexed_report') or {}).get('face_count', 0), 'assembly': manifest.get('model_assembly_json'), 'family_members': len(manifest.get('model_family', [])), 'texture_refs': sum(len(v) for v in manifest.get('texture_refs', {}).values()), 'textures': len(manifest.get('textures', [])), 'decoded_textures': manifest.get('decoded_texture_count', 0), 'texture_dictionaries': len(manifest.get('texture_dictionaries', [])), 'structure_companions': len(manifest.get('structure_companions', [])), 'heuristic_streams': len(manifest.get('heuristic_streams', []))}, indent=2))
        return 0

    if args.asset:
        data = args.asset.read_bytes()
        bundle, manifest = create_bundle(args.asset.name, data, args.out)
        print(json.dumps({'bundle': str(bundle), 'manifest': str(bundle / 'manifest.json'), 'xml': manifest.get('xml'), 'obj_preview': manifest.get('obj_preview'), 'obj_family_preview': manifest.get('obj_family_preview'), 'obj_indexed_preview': manifest.get('obj_indexed_preview'), 'indexed_faces': (manifest.get('obj_indexed_report') or {}).get('face_count', 0), 'assembly': manifest.get('model_assembly_json'), 'family_members': len(manifest.get('model_family', [])), 'texture_refs': sum(len(v) for v in manifest.get('texture_refs', {}).values()), 'textures': len(manifest.get('textures', [])), 'decoded_textures': manifest.get('decoded_texture_count', 0), 'texture_dictionaries': len(manifest.get('texture_dictionaries', [])), 'structure_companions': len(manifest.get('structure_companions', [])), 'heuristic_streams': len(manifest.get('heuristic_streams', []))}, indent=2))
        return 0

    raise SystemExit('Use --asset or --archive.')


if __name__ == '__main__':
    raise SystemExit(main())
