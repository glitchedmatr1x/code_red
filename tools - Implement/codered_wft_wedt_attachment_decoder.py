#!/usr/bin/env python3
"""CodeRED WFT/WEDT Attachment Decoder Pass.

Read-only scanner for RDR1 RPF6 model resources and attachment-related tune files.

This tool intentionally stops at decode/report level:
- no RPF mutation
- no WFT/WEDT rebuild claim
- no semantic model compiler claim

It extracts enough structure to drive ScriptHook attachment experiments:
- WFT/WFD/WEDT resource inventory
- decoded root signatures / virtual-pointer counts
- conservative local transform candidates
- SMIC-to-fragment actor hand/gunbelt maps
- base weapon IK/muzzle/camera comparison
- a ScriptHook dual-gun attachment plan JSON
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import struct
import subprocess
import tempfile
import zipfile
from collections import Counter, defaultdict, OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
except Exception:  # pragma: no cover
    Cipher = algorithms = modes = default_backend = None  # type: ignore

RPF6_AES_KEY = bytes([
    0xB7,0x62,0xDF,0xB6,0xE2,0xB2,0xC6,0xDE,0xAF,0x72,0x2A,0x32,0xD2,0xFB,0x6F,0x0C,
    0x98,0xA3,0x21,0x74,0x62,0xC9,0xC4,0xED,0xAD,0xAA,0x2E,0xD0,0xDD,0xF9,0x2F,0x10,
])
VBASE = 0x50000000
MODEL_EXTS = {'.wft', '.wedt', '.wfd', '.wvd', '.wdd', '.wtd', '.wtx', '.wbd', '.xtd', '.xft', '.xdr'}
# Updated from live named fragments2.rpf:
# .wfd => type 1, .wedt => type 11, .wft => type 138
RESOURCE_TYPE_HINTS = {
    1: 'wfd_fragment_drawable_candidate',
    11: 'wedt_editdata_candidate',
    138: 'wft_fragment_texture_or_model_candidate',
}
ROOT_VFT_HINTS = {
    0x00DDC0A0: 'wfd_root_vft_fragment_drawable',
    0x00D0E590: 'wedt_root_vft_editdata',
    0x00DDB8E4: 'wft_root_vft_fragment_texture_or_model',
}
WEAPON_FILES = [
    'base_dualpistol.weap',
    'base_pistol.weap',
    'base_rifle.weap',
    'base_repeater.weap',
    'base_shotgun.weap',
    'base_sniperrifle.weap',
    'base_bow.weap',
]
KEY_WEAPON_FIELDS = [
    'AnimType', 'TrigHoldMode', 'ACTFileName', 'ACTRoot', 'AnimSet',
    'IKOffset', 'IKOffsetHold', 'MuzzleOffset',
    'CameraSpeedScalar', 'CameraSpeedScalarZoomed',
    'WeaponArcGroupName', 'CanShootFromCamera',
]
ATTACHMENT_WORDS = ('hand', 'gunbelt', 'holster', 'weapon', 'pistol', 'dual', 'left', 'right')


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def rdr_hash(name: str) -> int:
    h = 0
    for ch in name.lower():
        a = (h + ord(ch)) & 0xFFFFFFFF
        b = (a + ((a << 10) & 0xFFFFFFFF)) & 0xFFFFFFFF
        h = (b ^ (b >> 6)) & 0xFFFFFFFF
    a = (h + ((h << 3) & 0xFFFFFFFF)) & 0xFFFFFFFF
    b = (a ^ (a >> 11)) & 0xFFFFFFFF
    return (b + ((b << 15) & 0xFFFFFFFF)) & 0xFFFFFFFF


def aes_blocks(data: bytes, decrypt: bool = True) -> bytes:
    n = len(data) & ~0xF
    if n <= 0:
        return data
    if Cipher is not None:
        cipher = Cipher(algorithms.AES(RPF6_AES_KEY), modes.ECB(), backend=default_backend())
        blk = data[:n]
        for _ in range(16):
            ctx = cipher.decryptor() if decrypt else cipher.encryptor()
            blk = ctx.update(blk) + ctx.finalize()
        return blk + data[n:]
    if not shutil.which('openssl'):
        raise RuntimeError('Encrypted RPF needs cryptography or openssl')
    blk = data[:n]
    mode = '-d' if decrypt else '-e'
    key = RPF6_AES_KEY.hex()
    for _ in range(16):
        p = subprocess.run(
            ['openssl', 'enc', '-aes-256-ecb', mode, '-K', key, '-nopad', '-nosalt'],
            input=blk,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        blk = p.stdout
    return blk + data[n:]


def is_res(f1: int) -> bool:
    return (f1 & 0x80000000) != 0


def is_ext(f2: int) -> bool:
    return (f2 & 0x80000000) != 0


def is_comp(f1: int, f2: int) -> bool:
    return (not is_ext(f2)) and ((f1 >> 30) & 1) == 1


def rtype(c: int) -> int:
    return c & 0xFF


def ent_off(c: int, res: bool) -> int:
    return ((c & 0x7FFFFF00) if res else (c & 0x7FFFFFFF)) * 8


def total_size(f1: int, f2: int) -> int:
    if not is_res(f1):
        return f1 & 0xBFFFFFFF
    if is_ext(f2):
        return ((f2 & 0x3FFF) << 12) + (((f2 >> 14) & 0x3FFF) << 12)
    vp = ((f1 >> 4) & 0x7F) + ((f1 >> 3) & 1) + ((f1 >> 2) & 1) + ((f1 >> 1) & 1) + (f1 & 1)
    vs = (f1 >> 11) & 0xF
    pp = ((f1 >> 19) & 0x7F) + ((f1 >> 18) & 1) + ((f1 >> 17) & 1) + ((f1 >> 16) & 1) + ((f1 >> 15) & 1)
    ps = (f1 >> 26) & 0xF
    return (vp << (vs + 8)) + (pp << (ps + 8))


@dataclass
class Entry:
    index: int
    name_hash: int
    name: str
    path: str
    parent_index: int | None
    type: str
    start: int = 0
    count: int = 0
    size: int = 0
    offset_raw: int = 0
    offset: int = 0
    flag1: int = 0
    flag2: int = 0
    resource: bool = False
    compressed: bool = False
    resource_type: int | None = None
    total: int = 0
    ext: str = ''


class RPF6:
    def __init__(self, path: str | Path, debug: bool = True):
        self.path = Path(path)
        self.data = self.path.read_bytes()
        if self.data[:4] != b'RPF6':
            raise ValueError(f'not RPF6: {self.path}')
        _, self.count, self.debug_word, self.enc = struct.unpack('>4I', self.data[:16])
        self.toc_size = ((self.count * 20) + 15) & ~15
        toc = self.data[16:16 + self.toc_size]
        self.toc = aes_blocks(toc, True) if self.enc else toc
        self.entries = self._entries(debug)

    def _debug_names(self) -> dict[int, list[str]]:
        off = self.debug_word * 8
        if off <= 0 or off >= len(self.data):
            return {}
        try:
            blob = aes_blocks(self.data[off:], True)[self.count * 8:]
        except Exception:
            return {}
        out: dict[int, list[str]] = defaultdict(list)
        for s in blob.decode('latin-1', 'ignore').split('\0'):
            s = s.strip()
            if s:
                out[rdr_hash(s)].append(s)
        return out

    def _entries(self, debug: bool) -> list[Entry]:
        names = self._debug_names() if debug else {}
        raw: list[dict] = []
        for i in range(self.count):
            a, b, c, d, e = struct.unpack('>5I', self.toc[i * 20:(i + 1) * 20])
            is_dir = ((c >> 24) & 0xFF) == 0x80
            if is_dir:
                raw.append(dict(i=i, h=a, t='dir', start=c & 0x7FFFFFFF, count=d & 0x0FFFFFFF))
            else:
                res = is_res(d)
                raw.append(dict(
                    i=i, h=a, t='file', size=b & 0x0FFFFFFF, oraw=c,
                    off=ent_off(c, res), f1=d, f2=e, res=res,
                    comp=is_comp(d, e), rt=rtype(c) if res else None,
                    total=total_size(d, e),
                ))

        parents: list[int | None] = [None] * len(raw)
        for x in raw:
            if x['t'] == 'dir':
                for ci in range(x['start'], x['start'] + x['count']):
                    if 0 <= ci < len(raw):
                        parents[ci] = x['i']

        def nm(x: dict) -> str:
            if x['t'] == 'dir' and x['h'] == 0:
                return 'root'
            vals = names.get(x['h'])
            return vals.pop(0) if vals else f'0x{x["h"]:08X}'

        for x in raw:
            x['name'] = nm(x)
            x['par'] = parents[x['i']]

        out: list[Entry] = []
        for x in raw:
            parts = [x['name']]
            p = x['par']
            seen = set()
            while p is not None and p not in seen and 0 <= p < len(raw):
                seen.add(p)
                parts.append(raw[p]['name'])
                p = raw[p]['par']
            path = '/'.join(reversed(parts))
            ext = '.' + x['name'].lower().rsplit('.', 1)[-1] if x['t'] == 'file' and '.' in x['name'] else ''
            out.append(Entry(
                x['i'], x['h'], x['name'], path, x['par'], x['t'],
                x.get('start', 0), x.get('count', 0), x.get('size', 0),
                x.get('oraw', 0), x.get('off', 0), x.get('f1', 0), x.get('f2', 0),
                x.get('res', False), x.get('comp', False), x.get('rt'),
                x.get('total', 0), ext,
            ))
        return out

    def files(self) -> list[Entry]:
        return [e for e in self.entries if e.type == 'file']

    def slot(self, e: Entry) -> bytes:
        return self.data[e.offset:e.offset + e.size]


def zstd_dec(data: bytes) -> bytes:
    try:
        import zstandard as zstd  # type: ignore
        return zstd.ZstdDecompressor().decompress(data)
    except Exception:
        pass
    if not shutil.which('zstd'):
        raise RuntimeError('need zstandard Python package or zstd CLI')
    return subprocess.run(
        ['zstd', '-d', '-q', '--single-thread', '--stdout'],
        input=data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout


def rsc_decode(raw: bytes) -> tuple[bytes, bytes, str]:
    if raw.startswith(b'RSC') and len(raw) >= 12:
        return raw[:12], zstd_dec(raw[12:]), 'rsc_zstd'
    if raw.startswith(b'\x28\xb5\x2f\xfd'):
        return b'', zstd_dec(raw), 'zstd'
    return b'', raw, 'raw'


def safe_name(text: str, fallback: str = 'item') -> str:
    text = text.replace('\\', '/').strip('/') or fallback
    return re.sub(r'[^A-Za-z0-9_.-]+', '__', text)[:180]


def write_csv(path: Path, rows: Sequence[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fields)
        if fields:
            writer.writeheader()
            writer.writerows(rows)


def u32(data: bytes, off: int) -> int:
    return struct.unpack_from('<I', data, off)[0] if 0 <= off <= len(data) - 4 else 0


def f32(data: bytes, off: int) -> float:
    return struct.unpack_from('<f', data, off)[0]


def count_virtual_ptrs(data: bytes) -> int:
    n = len(data)
    count = 0
    for off in range(0, max(0, n - 4), 4):
        val = u32(data, off)
        if VBASE <= val < VBASE + n:
            count += 1
    return count


def norm3(v: tuple[float, float, float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def dot3(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def sane_float(v: float, lim: float = 100000.0) -> bool:
    return math.isfinite(v) and -lim <= v <= lim


def scan_quat_transforms(data: bytes, entry_ref: dict, max_rows: int = 120, max_scan_bytes: int = 262144) -> list[dict]:
    rows: list[dict] = []
    scan_len = min(len(data), max_scan_bytes if max_scan_bytes > 0 else len(data))
    for off in range(0, max(0, scan_len - 28), 8):
        q = struct.unpack_from('<4f', data, off)
        t = struct.unpack_from('<3f', data, off + 16)
        qlen = math.sqrt(sum(x * x for x in q))
        if not (0.80 <= qlen <= 1.20):
            continue
        if not all(sane_float(v, 10000.0) for v in t):
            continue
        if max(abs(v) for v in t) > 30.0:
            continue
        if max(abs(v) for v in t) < 1e-6:
            continue
        rows.append({
            **entry_ref,
            'kind': 'quat_translate_candidate',
            'offset': off,
            'offset_hex': f'0x{off:08X}',
            'confidence': round(1.0 - abs(1.0 - qlen), 4),
            'qx': q[0], 'qy': q[1], 'qz': q[2], 'qw': q[3],
            'tx': t[0], 'ty': t[1], 'tz': t[2],
            'note': 'heuristic local transform; verify against CodeX/Magic-RDR viewer before patching',
        })
        if len(rows) >= max_rows:
            break
    return rows


def scan_matrix_candidates(data: bytes, entry_ref: dict, max_rows: int = 80, max_scan_bytes: int = 262144) -> list[dict]:
    rows: list[dict] = []
    scan_len = min(len(data), max_scan_bytes if max_scan_bytes > 0 else len(data))
    for off in range(0, max(0, scan_len - 64), 16):
        vals = struct.unpack_from('<16f', data, off)
        if not all(sane_float(v, 10000.0) for v in vals):
            continue
        r0, r1, r2 = vals[0:3], vals[4:7], vals[8:11]
        n0, n1, n2 = norm3(r0), norm3(r1), norm3(r2)
        if not (0.70 <= n0 <= 1.30 and 0.70 <= n1 <= 1.30 and 0.70 <= n2 <= 1.30):
            continue
        if abs(dot3(r0, r1)) > 0.25 or abs(dot3(r0, r2)) > 0.25 or abs(dot3(r1, r2)) > 0.25:
            continue
        tx, ty, tz = vals[12], vals[13], vals[14]
        if not all(sane_float(v, 10000.0) for v in (tx, ty, tz)):
            continue
        if max(abs(tx), abs(ty), abs(tz)) > 100.0:
            continue
        rows.append({
            **entry_ref,
            'kind': 'matrix4x4_candidate',
            'offset': off,
            'offset_hex': f'0x{off:08X}',
            'confidence': round(1.0 - min(1.0, abs(1-n0)+abs(1-n1)+abs(1-n2)), 4),
            'tx': tx, 'ty': ty, 'tz': tz,
            'row0': ' '.join(f'{v:.6g}' for v in vals[0:4]),
            'row1': ' '.join(f'{v:.6g}' for v in vals[4:8]),
            'row2': ' '.join(f'{v:.6g}' for v in vals[8:12]),
            'row3': ' '.join(f'{v:.6g}' for v in vals[12:16]),
            'note': 'heuristic transform/matrix candidate; not yet a named bone/socket',
        })
        if len(rows) >= max_rows:
            break
    return rows


def resource_hint(e: Entry, root_vft: int) -> str:
    if e.ext in MODEL_EXTS:
        return f'extension_{e.ext[1:]}'
    return RESOURCE_TYPE_HINTS.get(e.resource_type or -1, ROOT_VFT_HINTS.get(root_vft, 'unknown_resource'))


def basename_key(name: str) -> str:
    stem = Path(name).stem.lower()
    stem = re.sub(r'_(hi|med|lo)lod$', '', stem)
    stem = re.sub(r'_hilod$|_medlod$|_lod$', '', stem)
    return stem


def scan_model_archive(rpf_path: Path, outdir: Path, args: argparse.Namespace) -> tuple[list[dict], list[dict], list[dict]]:
    rpf = RPF6(rpf_path, debug=not args.no_debug)
    inventory_rows: list[dict] = []
    transform_rows: list[dict] = []
    bundle_map: dict[str, dict] = OrderedDict()

    model_files = [e for e in rpf.files() if e.resource and (e.ext in MODEL_EXTS or (e.resource_type in RESOURCE_TYPE_HINTS))]
    for idx, e in enumerate(model_files):
        if args.max_models and idx >= args.max_models:
            break
        raw = rpf.slot(e)
        try:
            _, decoded, decode_mode = rsc_decode(raw)
        except Exception as exc:
            inventory_rows.append({
                'archive': rpf_path.name,
                'entry_path': e.path,
                'entry_index': e.index,
                'extension': e.ext,
                'resource_type': e.resource_type,
                'error': repr(exc),
            })
            continue
        root_vft = u32(decoded, 0)
        ptr_count = count_virtual_ptrs(decoded)
        key = basename_key(e.name)
        bundle = bundle_map.setdefault(key, {
            'archive': rpf_path.name, 'bundle_key': key,
            'wft': '', 'wfd': '', 'wedt': '',
            'file_count': 0,
        })
        if e.ext in {'.wft', '.wfd', '.wedt'}:
            bundle[e.ext[1:]] = e.path
        bundle['file_count'] += 1

        decoded_extract = ''
        if args.extract_decoded_limit > 0 and len([p for p in (outdir / 'decoded_payloads').glob('*.decoded.bin')]) < args.extract_decoded_limit:
            dec_dir = outdir / 'decoded_payloads'
            dec_dir.mkdir(parents=True, exist_ok=True)
            dec_path = dec_dir / f'{rpf_path.stem}__{e.index:05d}__{safe_name(e.path)}.decoded.bin'
            dec_path.write_bytes(decoded)
            decoded_extract = str(dec_path.relative_to(outdir))

        inv = {
            'archive': rpf_path.name,
            'entry_index': e.index,
            'entry_name': e.name,
            'entry_path': e.path,
            'bundle_key': key,
            'extension': e.ext,
            'resource_type': e.resource_type,
            'resource_hint': resource_hint(e, root_vft),
            'root_vft': f'0x{root_vft:08X}',
            'root_vft_hint': ROOT_VFT_HINTS.get(root_vft, ''),
            'slot_size': len(raw),
            'decoded_size': len(decoded),
            'decoded_sha1': sha1(decoded),
            'decode_mode': decode_mode,
            'virtual_pointer_count': ptr_count,
            'toc_offset': e.offset,
            'toc_total_size': e.total,
            'decoded_extract': decoded_extract,
        }
        inventory_rows.append(inv)

        if args.scan_transforms and e.ext in {'.wft', '.wedt', '.wfd'}:
            ref = {
                'archive': rpf_path.name,
                'entry_index': e.index,
                'entry_name': e.name,
                'entry_path': e.path,
                'bundle_key': key,
                'extension': e.ext,
                'resource_type': e.resource_type,
            }
            transform_rows.extend(scan_quat_transforms(decoded, ref, max_rows=args.max_transforms_per_resource, max_scan_bytes=args.transform_scan_max_bytes))
            transform_rows.extend(scan_matrix_candidates(decoded, ref, max_rows=max(20, args.max_transforms_per_resource // 2), max_scan_bytes=args.transform_scan_max_bytes))

    bundles = list(bundle_map.values())
    return inventory_rows, transform_rows, bundles


def text_from_entry(rpf: RPF6, e: Entry) -> str | None:
    raw = rpf.slot(e)
    try:
        _, decoded, _ = rsc_decode(raw)
    except Exception:
        decoded = raw
    for enc in ('utf-8', 'utf-8-sig', 'latin-1'):
        try:
            return decoded.decode(enc)
        except Exception:
            continue
    return None


def scan_smic_maps(rpf_path: Path) -> list[dict]:
    rows: list[dict] = []
    rpf = RPF6(rpf_path)
    targets = [e for e in rpf.files() if e.name.lower() in {'smictofragmap.txt', 'smictofragmap_rm.txt'}]
    for e in targets:
        text = text_from_entry(rpf, e) or ''
        for line_no, line in enumerate(text.splitlines(), 1):
            clean = line.strip()
            if not clean or clean.startswith(('Version:', 'Count:', 'SectorCount:')):
                continue
            parts = clean.split()
            if len(parts) < 3:
                continue
            model = parts[0]
            try:
                count = int(parts[1])
            except Exception:
                continue
            smics = parts[2:]
            relevant = any(any(word in s.lower() for word in ATTACHMENT_WORDS) for s in [model, *smics])
            if not relevant:
                continue
            rows.append({
                'archive': rpf_path.name,
                'source_path': e.path,
                'line': line_no,
                'model': model,
                'declared_count': count,
                'smic_count': len(smics),
                'smics': ' '.join(smics),
                'has_player_hand': int(any('player_default_hand' in s.lower() for s in smics)),
                'has_gunbelt': int(any('gunbelt' in s.lower() for s in smics)),
                'has_holster': int(any('holster' in s.lower() for s in smics)),
                'has_left_or_right': int(any(('left' in s.lower() or 'right' in s.lower()) for s in smics)),
            })
    return rows


def parse_weapon_fields(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    # Longest field names first prevents IKOffsetHold from being captured as IKOffset,
    # and CameraSpeedScalarZoomed from being captured as CameraSpeedScalar.
    for line in text.splitlines():
        clean = line.strip()
        for field in sorted(KEY_WEAPON_FIELDS, key=len, reverse=True):
            pattern = r'^' + re.escape(field) + r'(?:\s+|$)(.*)$'
            match = re.match(pattern, clean, flags=re.IGNORECASE)
            if not match:
                continue
            value = match.group(1).strip().strip('"')
            out[field] = value
            break
    return out


def scan_weapon_files(rpf_path: Path) -> list[dict]:
    rows: list[dict] = []
    rpf = RPF6(rpf_path)
    for e in rpf.files():
        if e.name.lower() not in WEAPON_FILES:
            continue
        text = text_from_entry(rpf, e) or ''
        fields = parse_weapon_fields(text)
        row = {
            'archive': rpf_path.name,
            'entry_path': e.path,
            'weapon_file': e.name,
            'base_weapon': '',
        }
        m = re.search(r'BASEWEAPON\s+"([^"]+)"', text)
        if m:
            row['base_weapon'] = m.group(1)
        for field in KEY_WEAPON_FIELDS:
            row[field] = fields.get(field, '')
        row['has_real_act_animset'] = int(bool(row.get('ACTFileName') and row.get('ACTFileName') != 'donothing' and row.get('AnimSet') not in {'', '<none>'}))
        row['dual_gun_relevance'] = (
            'primary_target' if 'dualpistol' in e.name.lower()
            else 'pistol_baseline' if 'pistol' in e.name.lower()
            else 'long_gun_ik_reference' if e.name.lower() in {'base_rifle.weap', 'base_repeater.weap', 'base_shotgun.weap', 'base_sniperrifle.weap'}
            else ''
        )
        rows.append(row)
    return rows


def build_script_hook_plan(smic_rows: list[dict], weapon_rows: list[dict]) -> dict:
    locator_candidates: list[str] = []
    for row in smic_rows:
        for smic in str(row.get('smics', '')).split():
            low = smic.lower()
            if any(key in low for key in ['player_default_hand', 'gunbelt', 'holster']):
                if smic not in locator_candidates:
                    locator_candidates.append(smic)
    if not locator_candidates:
        locator_candidates = ['smic_player_default_hand_1_rm', 'smic_player_default_hand_1', 'smic_amb_gunbelt01_01']

    weapon_summary = {row['weapon_file']: {k: row.get(k, '') for k in KEY_WEAPON_FIELDS + ['has_real_act_animset']} for row in weapon_rows}

    return {
        'schema': 'codered.dualgun_attachment_lab.v1',
        'mode': 'read_only_plan',
        'purpose': 'Use WFT/WEDT + tune data to drive ScriptHook left-hand prop/weapon attachment experiments.',
        'guardrails': [
            'Do not patch WFT/WEDT yet.',
            'Use ScriptHook runtime attach first.',
            'Keep normal right-hand/player weapon path intact.',
            'Use simulated/raycast left-fire until native left/right weapon tasks are proven.',
        ],
        'candidate_locators_from_smic_maps': locator_candidates[:30],
        'recommended_first_locators': [
            'smic_player_default_hand_1_rm',
            'smic_player_default_hand_1',
            'smic_amb_gunbelt01_01',
        ],
        'weapon_tune_summary': weapon_summary,
        'script_hook_actions_to_add': [
            'DualGunLab_Open',
            'DualGunLab_AttachLeftPistolProp',
            'DualGunLab_NudgeLeftPistolOffset',
            'DualGunLab_SaveOffsetPreset',
            'DualGunLab_LeftFireRaycast',
            'DualGunLab_DebugDrawMuzzle',
        ],
        'left_pistol_initial_attach': {
            'TargetActor': 'PLAYER_ACTOR',
            'PropModel': 'pistol_model_or_weapon_fragment_candidate',
            'AttachLocator': 'smic_player_default_hand_1_rm',
            'AttachOffset': [0.0, 0.0, 0.0],
            'AttachEulers': [0.0, 0.0, 0.0],
            'NudgeStep': 0.005,
        },
        'right_hand': {
            'Mode': 'native_weapon',
            'Reason': 'Keep the base game weapon path stable while left hand is proved.',
        },
        'left_hand': {
            'Mode': 'attached_prop_plus_simulated_fire',
            'Reason': 'Independent native dual-wield aim is not proven; ScriptHook raycast can prove independent trigger logic first.',
        },
    }


def collect_inputs(inputs: Iterable[str], temp_root: Path) -> list[Path]:
    out: list[Path] = []
    for item in inputs:
        path = Path(item)
        if path.is_dir():
            out.extend(sorted(path.rglob('*.rpf')))
        elif path.suffix.lower() == '.zip' and path.exists():
            with zipfile.ZipFile(path) as z:
                for info in z.infolist():
                    if not info.filename.lower().endswith('.rpf'):
                        continue
                    dest = temp_root / Path(info.filename).name
                    with z.open(info) as src, open(dest, 'wb') as dst:
                        shutil.copyfileobj(src, dst, 1024 * 1024)
                    out.append(dest)
        elif path.exists() and path.suffix.lower() == '.rpf':
            out.append(path)
    seen = set()
    clean: list[Path] = []
    for p in out:
        key = str(p.resolve())
        if key not in seen:
            seen.add(key)
            clean.append(p)
    return clean


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='CodeRED WFT/WEDT attachment-data scanner')
    parser.add_argument('inputs', nargs='+', help='RPF files, folders, or ZIPs containing RPFs')
    parser.add_argument('--outdir', default='reports/wft_wedt_attachment_lab')
    parser.add_argument('--max-models', type=int, default=0, help='0 means no limit')
    parser.add_argument('--extract-decoded-limit', type=int, default=8)
    parser.add_argument('--no-debug', action='store_true')
    parser.add_argument('--scan-transforms', action='store_true', default=True)
    parser.add_argument('--max-transforms-per-resource', type=int, default=80)
    parser.add_argument('--transform-scan-max-bytes', type=int, default=262144, help='Max decoded bytes to scan per resource for transform candidates; 0 scans full payload')
    args = parser.parse_args(argv)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    temp_root = Path(tempfile.mkdtemp(prefix='codered_wft_wedt_'))
    all_inventory: list[dict] = []
    all_transforms: list[dict] = []
    all_bundles: list[dict] = []
    all_smic: list[dict] = []
    all_weapons: list[dict] = []
    errors: list[dict] = []

    try:
        rpfs = collect_inputs(args.inputs, temp_root)
        if not rpfs:
            raise SystemExit('No RPF inputs found.')
        for rpf_path in rpfs:
            try:
                inv, transforms, bundles = scan_model_archive(rpf_path, outdir, args)
                all_inventory.extend(inv)
                all_transforms.extend(transforms)
                all_bundles.extend(bundles)
                all_smic.extend(scan_smic_maps(rpf_path))
                all_weapons.extend(scan_weapon_files(rpf_path))
                print(f'scanned {rpf_path.name}: models={len(inv)} transforms={len(transforms)} bundles={len(bundles)}')
            except Exception as exc:
                errors.append({'archive': str(rpf_path), 'error': repr(exc)})
                print(f'error {rpf_path}: {exc}')
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)

    write_csv(outdir / 'model_resource_summary.csv', all_inventory)
    write_csv(outdir / 'candidate_transforms.csv', all_transforms)
    write_csv(outdir / 'fragment_bundle_map.csv', all_bundles)
    write_csv(outdir / 'smic_attachment_map.csv', all_smic)
    write_csv(outdir / 'weapon_dualgun_comparison.csv', all_weapons)
    write_csv(outdir / 'scan_errors.csv', errors)

    plan = build_script_hook_plan(all_smic, all_weapons)
    (outdir / 'script_hook_dualgun_attachment_plan.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')

    counts = {
        'model_resources': len(all_inventory),
        'candidate_transforms': len(all_transforms),
        'fragment_bundles': len(all_bundles),
        'smic_attachment_rows': len(all_smic),
        'weapon_rows': len(all_weapons),
        'errors': len(errors),
        'extensions': dict(Counter(row.get('extension', '') for row in all_inventory)),
        'resource_types': dict(Counter(str(row.get('resource_type', '')) for row in all_inventory)),
    }
    master = {
        'schema': 'codered.wft_wedt_attachment_scan.v1',
        'counts': counts,
        'outputs': {
            'model_resource_summary': 'model_resource_summary.csv',
            'candidate_transforms': 'candidate_transforms.csv',
            'fragment_bundle_map': 'fragment_bundle_map.csv',
            'smic_attachment_map': 'smic_attachment_map.csv',
            'weapon_dualgun_comparison': 'weapon_dualgun_comparison.csv',
            'script_hook_dualgun_attachment_plan': 'script_hook_dualgun_attachment_plan.json',
            'scan_errors': 'scan_errors.csv',
        },
        'safety': 'read-only; no archive mutation; transform candidates are heuristic until matched to CodeX/Magic-RDR semantic classes',
    }
    (outdir / 'wft_wedt_attachment_master.json').write_text(json.dumps(master, indent=2), encoding='utf-8')

    report_lines = [
        '# CodeRED WFT/WEDT Attachment Scan Report',
        '',
        'Read-only pass for extracting model-resource and attachment-adjacent data.',
        '',
        '## Counts',
        '',
    ]
    for key, value in counts.items():
        report_lines.append(f'- `{key}`: `{value}`')
    report_lines.extend([
        '',
        '## Important read',
        '',
        '- `.wfd`, `.wft`, and `.wedt` resources are now separately inventoried.',
        '- `smictofragmap*.txt` is treated as the first actor/fragments attachment map.',
        '- `base_dualpistol.weap` is compared against pistol and long-gun bases.',
        '- `candidate_transforms.csv` is heuristic only; use it for offset discovery, not patching.',
        '',
        '## Next runtime target',
        '',
        'Add a ScriptHook menu lab that attaches a left-hand pistol prop using `SpatialAttach`/native attach behavior, then uses a simulated left-fire raycast while the right-hand weapon stays native.',
    ])
    (outdir / 'wft_wedt_attachment_report.md').write_text('\n'.join(report_lines), encoding='utf-8')
    print('wrote', outdir)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
