#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import shutil
import struct
import subprocess
import tempfile
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

RPF6_AES_KEY = bytes([
    0xB7,0x62,0xDF,0xB6,0xE2,0xB2,0xC6,0xDE,0xAF,0x72,0x2A,0x32,0xD2,0xFB,0x6F,0x0C,
    0x98,0xA3,0x21,0x74,0x62,0xC9,0xC4,0xED,0xAD,0xAA,0x2E,0xD0,0xDD,0xF9,0x2F,0x10,
])
VBASE = 0x50000000
MODEL_EXTS = {'.wft', '.wedt', '.wfd', '.wvd', '.wdd', '.wtd', '.wtx', '.wbd', '.xtd', '.xft', '.xdr'}
# Current RDR1 evidence from fragments2.rpf. These labels are deliberately cautious.
RESOURCE_TYPE_HINTS = {
    1: 'fragment_or_drawable_candidate_type1',
    11: 'wedt_or_editdata_candidate_type11',
    138: 'texture_or_aux_drawable_candidate_type138',
}
ROOT_VFT_HINTS = {
    0x00DDC0A0: 'root_vft_type1_fragment_candidate',
    0x00D0E590: 'root_vft_type11_editdata_candidate',
    0x00DDB8E4: 'root_vft_type138_texture_aux_candidate',
}
ASCII_RE = re.compile(rb'[\x20-\x7E]{4,}')
UTF16_RE = re.compile(rb'(?:[\x20-\x7E]\x00){4,}')


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
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes  # type: ignore
        from cryptography.hazmat.backends import default_backend  # type: ignore
        cipher = Cipher(algorithms.AES(RPF6_AES_KEY), modes.ECB(), backend=default_backend())
        blk = data[:n]
        for _ in range(16):
            ctx = cipher.decryptor() if decrypt else cipher.encryptor()
            blk = ctx.update(blk) + ctx.finalize()
        return blk + data[n:]
    except Exception:
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
        self.exts = Counter(e.ext for e in self.entries if e.ext)

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
        raw = []
        names = self._debug_names() if debug else {}
        for i in range(self.count):
            a, b, c, d, e = struct.unpack('>5I', self.toc[i * 20:(i + 1) * 20])
            is_dir = ((c >> 24) & 0xFF) == 0x80
            if is_dir:
                raw.append(dict(i=i, h=a, t='dir', start=c & 0x7FFFFFFF, count=d & 0x0FFFFFFF))
            else:
                res = is_res(d)
                raw.append(dict(
                    i=i, h=a, t='file', size=b & 0x0FFFFFFF, oraw=c, off=ent_off(c, res),
                    f1=d, f2=e, res=res, comp=is_comp(d, e), rt=rtype(c) if res else None, total=total_size(d, e),
                ))
        parents = [None] * len(raw)
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
                x['i'], x['h'], x['name'], path, x['par'], x['t'], x.get('start', 0), x.get('count', 0),
                x.get('size', 0), x.get('oraw', 0), x.get('off', 0), x.get('f1', 0), x.get('f2', 0),
                x.get('res', False), x.get('comp', False), x.get('rt'), x.get('total', 0), ext,
            ))
        return out

    def files(self) -> list[Entry]:
        return [e for e in self.entries if e.type == 'file']

    def slot(self, e: Entry) -> bytes:
        return self.data[e.offset:e.offset + e.size]

    def summary(self) -> dict:
        return dict(
            archive=str(self.path), entry_count=self.count, file_count=sum(e.type == 'file' for e in self.entries),
            dir_count=sum(e.type == 'dir' for e in self.entries), encrypted_toc=bool(self.enc),
            debug_offset_word=self.debug_word, extensions=dict(sorted(self.exts.items())),
        )


def zstd_dec(data: bytes) -> bytes:
    try:
        import zstandard as zstd  # type: ignore
        return zstd.ZstdDecompressor().decompress(data)
    except Exception:
        pass
    if not shutil.which('zstd'):
        raise RuntimeError('need zstandard package or zstd CLI')
    return subprocess.run(
        ['zstd', '-d', '-q', '--single-thread', '--stdout'],
        input=data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout


def zstd_enc(data: bytes, level: int = 9) -> bytes:
    try:
        import zstandard as zstd  # type: ignore
        return zstd.ZstdCompressor(level=level, write_checksum=False).compress(data)
    except Exception:
        pass
    if not shutil.which('zstd'):
        raise RuntimeError('need zstandard package or zstd CLI')
    return subprocess.run(
        ['zstd', '-q', '-z', f'-{level}', '--no-check', '--single-thread', '--stdout'],
        input=data,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout


def rsc_decode(raw: bytes) -> tuple[bytes, bytes, str]:
    if not raw.startswith(b'RSC') or len(raw) < 12:
        return b'', raw, 'raw'
    return raw[:12], zstd_dec(raw[12:]), 'rsc_zstd'


def safe_name(text: str, fallback: str) -> str:
    text = text.replace('\\', '/').strip('/') or fallback
    return re.sub(r'[^A-Za-z0-9_.-]+', '__', text)[:180]


def u32(data: bytes, off: int) -> int:
    return struct.unpack_from('<I', data, off)[0] if 0 <= off <= len(data) - 4 else 0


def count_virtual_ptrs(data: bytes, sample_limit: int = 200) -> tuple[int, list[dict]]:
    count = 0
    sample: list[dict] = []
    n = len(data)
    for off in range(0, max(0, n - 4), 4):
        val = u32(data, off)
        if VBASE <= val < VBASE + n:
            count += 1
            if len(sample) < sample_limit:
                sample.append({'offset': off, 'offset_hex': f'0x{off:08X}', 'value': f'0x{val:08X}', 'target_offset': val - VBASE, 'target_hex': f'0x{val - VBASE:08X}'})
    return count, sample


def ascii_strings(data: bytes, sample_limit: int = 120) -> tuple[int, list[dict]]:
    count = 0
    sample: list[dict] = []
    for m in ASCII_RE.finditer(data):
        count += 1
        if len(sample) < sample_limit:
            sample.append({'offset': m.start(), 'offset_hex': f'0x{m.start():08X}', 'text': m.group(0).decode('latin-1', 'replace')})
    return count, sample


def utf16_strings(data: bytes, sample_limit: int = 80) -> tuple[int, list[dict]]:
    count = 0
    sample: list[dict] = []
    for m in UTF16_RE.finditer(data):
        count += 1
        if len(sample) < sample_limit:
            text = m.group(0).decode('utf-16le', 'replace').rstrip('\x00')
            sample.append({'offset': m.start(), 'offset_hex': f'0x{m.start():08X}', 'text': text})
    return count, sample


def vft_histogram(data: bytes, max_scan: int = 0, topn: int = 50) -> list[dict]:
    if max_scan <= 0 or max_scan > len(data):
        max_scan = len(data)
    counts: Counter[int] = Counter()
    for off in range(0, max(0, max_scan - 4), 4):
        val = u32(data, off)
        # RDR1 decoded resource class pointers commonly sit in low virtual/class ranges.
        if 0x00010000 <= val <= 0x02000000:
            counts[val] += 1
    return [{'value': f'0x{val:08X}', 'count': count, 'hint': ROOT_VFT_HINTS.get(val, '')} for val, count in counts.most_common(topn)]


def float3_probe(data: bytes, sample_limit: int = 200) -> tuple[int, list[dict]]:
    if sample_limit <= 0:
        return 0, []
    count = 0
    sample: list[dict] = []
    for off in range(0, max(0, len(data) - 12), 4):
        try:
            x, y, z = struct.unpack_from('<3f', data, off)
        except Exception:
            break
        if all(math.isfinite(v) and -100000.0 <= v <= 100000.0 for v in (x, y, z)):
            if max(abs(x), abs(y), abs(z)) >= 0.001 and not (abs(x) < 1e-7 and abs(y) < 1e-7 and abs(z) < 1e-7):
                count += 1
                if len(sample) < sample_limit:
                    sample.append({'offset': off, 'offset_hex': f'0x{off:08X}', 'x': round(x, 6), 'y': round(y, 6), 'z': round(z, 6)})
    return count, sample


def resource_label(e: Entry, root_vft: int) -> str:
    if e.ext in MODEL_EXTS:
        return f'extension_{e.ext[1:]}'
    if e.resource_type in RESOURCE_TYPE_HINTS:
        return RESOURCE_TYPE_HINTS[e.resource_type]
    if root_vft in ROOT_VFT_HINTS:
        return ROOT_VFT_HINTS[root_vft]
    return 'unknown_resource'


def should_scan(e: Entry, all_resources: bool) -> bool:
    if not e.resource:
        return False
    if all_resources:
        return True
    if e.ext in MODEL_EXTS:
        return True
    if e.resource_type in RESOURCE_TYPE_HINTS:
        return True
    return False


def collect_inputs(paths: Iterable[str], temp_root: Path) -> list[Path]:
    out: list[Path] = []
    for item in paths:
        path = Path(item)
        if path.is_dir():
            out.extend(sorted(path.rglob('*.rpf')))
        elif path.suffix.lower() == '.zip' and path.exists():
            with zipfile.ZipFile(path) as z:
                for info in z.infolist():
                    if info.filename.lower().endswith('.rpf'):
                        dest = temp_root / safe_name(Path(info.filename).name, 'archive.rpf')
                        with z.open(info) as src, open(dest, 'wb') as dst:
                            shutil.copyfileobj(src, dst, 1024 * 1024)
                        out.append(dest)
        elif path.exists() and path.suffix.lower() == '.rpf':
            out.append(path)
    # Keep stable order and remove duplicates.
    seen = set()
    clean = []
    for p in out:
        key = str(p.resolve()) if p.exists() else str(p)
        if key not in seen:
            seen.add(key)
            clean.append(p)
    return clean


def write_csv(path: Path, rows: list[dict]) -> None:
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


def scan_archive(rpf_path: Path, args: argparse.Namespace, outdir: Path) -> tuple[list[dict], list[dict], list[dict], list[dict], dict]:
    rpf = RPF6(rpf_path, debug=not args.no_debug)
    inventory_rows: list[dict] = []
    pointer_rows: list[dict] = []
    string_rows: list[dict] = []
    vft_rows: list[dict] = []
    roundtrip_rows: list[dict] = []
    decoded_count = 0
    processed_count = 0

    for e in rpf.files():
        if not should_scan(e, args.all_resources):
            continue
        if args.max_candidates and processed_count >= args.max_candidates:
            break
        processed_count += 1
        raw = rpf.slot(e)
        if not raw:
            inventory_rows.append({
                'archive': rpf_path.name, 'entry_index': e.index, 'entry_path': e.path,
                'resource_type': e.resource_type, 'error': 'empty slot or unresolved offset',
            })
            continue
        try:
            header, decoded, decode_mode = rsc_decode(raw)
        except Exception as exc:
            inventory_rows.append({
                'archive': rpf_path.name, 'entry_index': e.index, 'entry_path': e.path,
                'resource_type': e.resource_type, 'slot_size': len(raw), 'error': f'decode failed: {exc!r}',
            })
            continue
        root_vft = u32(decoded, 0)
        ptr_count, ptr_sample = count_virtual_ptrs(decoded, args.pointer_sample)
        ascii_count, ascii_sample = ascii_strings(decoded, args.string_sample)
        utf16_count, utf16_sample = utf16_strings(decoded, max(10, args.string_sample // 2))
        vfts = vft_histogram(decoded, args.vft_scan_bytes, args.vft_topn)
        vec_count, vec_sample = float3_probe(decoded, args.float_sample)
        label = resource_label(e, root_vft)
        safe = f'{rpf_path.stem}__{e.index:05d}__{safe_name(e.path, e.name)}'
        extracted_decoded = ''
        extracted_raw = ''
        if args.extract_decoded and decoded_count < args.extract_limit:
            decoded_dir = outdir / 'decoded_payloads'
            decoded_dir.mkdir(parents=True, exist_ok=True)
            p = decoded_dir / f'{safe}.decoded.bin'
            p.write_bytes(decoded)
            extracted_decoded = str(p.relative_to(outdir))
            decoded_count += 1
        if args.extract_raw and decoded_count <= args.extract_limit:
            raw_dir = outdir / 'raw_slots'
            raw_dir.mkdir(parents=True, exist_ok=True)
            p = raw_dir / f'{safe}.rsc_slot.bin'
            p.write_bytes(raw)
            extracted_raw = str(p.relative_to(outdir))
        roundtrip_ok = ''
        roundtrip_error = ''
        if args.roundtrip and decode_mode == 'rsc_zstd':
            try:
                recompressed = zstd_enc(decoded, args.zstd_level)
                redecompressed = zstd_dec(recompressed)
                roundtrip_ok = bool(redecompressed == decoded)
                roundtrip_rows.append({
                    'archive': rpf_path.name,
                    'entry_index': e.index,
                    'entry_path': e.path,
                    'resource_type': e.resource_type,
                    'decoded_size': len(decoded),
                    'decoded_sha1': sha1(decoded),
                    'recompressed_size': len(recompressed),
                    'roundtrip_ok': roundtrip_ok,
                })
            except Exception as exc:
                roundtrip_error = repr(exc)
                roundtrip_rows.append({
                    'archive': rpf_path.name,
                    'entry_index': e.index,
                    'entry_path': e.path,
                    'resource_type': e.resource_type,
                    'decoded_size': len(decoded),
                    'decoded_sha1': sha1(decoded),
                    'roundtrip_ok': False,
                    'error': roundtrip_error,
                })

        row = {
            'archive': rpf_path.name,
            'archive_path': str(rpf_path),
            'entry_index': e.index,
            'entry_name': e.name,
            'entry_path': e.path,
            'extension': e.ext,
            'name_hash': f'0x{e.name_hash:08X}',
            'resource_type': e.resource_type,
            'resource_hint': label,
            'slot_size': len(raw),
            'decoded_size': len(decoded),
            'decoded_sha1': sha1(decoded),
            'decode_mode': decode_mode,
            'root_vft': f'0x{root_vft:08X}',
            'root_vft_hint': ROOT_VFT_HINTS.get(root_vft, ''),
            'virtual_pointer_count': ptr_count,
            'ascii_string_count': ascii_count,
            'utf16_string_count': utf16_count,
            'float3_candidate_count': vec_count,
            'top_vfts_json': json.dumps(vfts[:10]),
            'decoded_extract': extracted_decoded,
            'raw_extract': extracted_raw,
            'roundtrip_ok': roundtrip_ok,
            'roundtrip_error': roundtrip_error,
            'toc_offset': e.offset,
            'toc_flag1': f'0x{e.flag1:08X}',
            'toc_flag2': f'0x{e.flag2:08X}',
            'toc_total_size': e.total,
        }
        inventory_rows.append(row)
        for item in ptr_sample:
            pointer_rows.append({'archive': rpf_path.name, 'entry_index': e.index, 'entry_path': e.path, **item})
        for item in ascii_sample:
            string_rows.append({'archive': rpf_path.name, 'entry_index': e.index, 'entry_path': e.path, 'encoding': 'ascii', **item})
        for item in utf16_sample:
            string_rows.append({'archive': rpf_path.name, 'entry_index': e.index, 'entry_path': e.path, 'encoding': 'utf16le', **item})
        for item in vfts:
            vft_rows.append({'archive': rpf_path.name, 'entry_index': e.index, 'entry_path': e.path, **item})
        if args.write_vec_samples:
            vec_path = outdir / 'float3_samples' / f'{safe}.float3_candidates.csv'
            write_csv(vec_path, vec_sample)
    master = {'archive': rpf.summary(), 'candidate_count': len(inventory_rows)}
    return inventory_rows, pointer_rows, string_rows, vft_rows, {'master': master, 'roundtrip_rows': roundtrip_rows}


def write_summary(outdir: Path, inventories: list[dict], roundtrips: list[dict], errors: list[dict]) -> None:
    by_type = Counter(str(r.get('resource_type', '')) for r in inventories if r.get('resource_type') != '')
    by_hint = Counter(r.get('resource_hint', '') for r in inventories)
    ok_rt = sum(1 for r in roundtrips if r.get('roundtrip_ok') is True)
    md = []
    md.append('# Code RED Model Resource Extract Report')
    md.append('')
    md.append('This is a read-only extraction and compression roundtrip research report. It does not rebuild WFT/WEDT structure and does not patch any RPF.')
    md.append('')
    md.append(f'- Candidate resources scanned: {len(inventories)}')
    md.append(f'- Roundtrip tests passed: {ok_rt}/{len(roundtrips)}')
    md.append(f'- Archive/errors: {len(errors)}')
    md.append('')
    md.append('## Resource type counts')
    for key, count in sorted(by_type.items()):
        md.append(f'- `{key}`: {count}')
    md.append('')
    md.append('## Hint counts')
    for key, count in by_hint.most_common():
        md.append(f'- `{key}`: {count}')
    md.append('')
    md.append('## Current boundary')
    md.append('')
    md.append('The pass can extract raw and decoded payloads, map virtual pointers, strings, root signatures, and prove zstd decode/recompress/decode equality. It is not yet a semantic WFT/WEDT model compiler. The next safe milestone is a byte-preserving decoded payload rebuilder or same-size texture replacement proof inside a copied RPF.')
    (outdir / 'model_extract_report.md').write_text('\n'.join(md), encoding='utf-8')


def main() -> None:
    parser = argparse.ArgumentParser(description='Code RED WFT/WEDT/WVD/WTD model resource extractor and no-op roundtrip researcher')
    parser.add_argument('inputs', nargs='+', help='RPF files, folders containing RPFs, or zip files containing RPFs')
    parser.add_argument('--outdir', default='exports/model_resource_extract')
    parser.add_argument('--all-resources', action='store_true', help='Scan all RPF resources, not only model/resource-type candidates')
    parser.add_argument('--max-candidates', type=int, default=0, help='Stop after this many candidate resources per archive; 0 means no limit')
    parser.add_argument('--no-debug', action='store_true', help='Skip encrypted debug-name table resolution for speed')
    parser.add_argument('--extract-decoded', action='store_true', help='Write decoded payload .bin files')
    parser.add_argument('--extract-raw', action='store_true', help='Write raw RSC slot .bin files')
    parser.add_argument('--extract-limit', type=int, default=12, help='Max decoded/raw payloads to write per archive')
    parser.add_argument('--roundtrip', action='store_true', help='Test zstd decode -> recompress -> decode equality')
    parser.add_argument('--zstd-level', type=int, default=9)
    parser.add_argument('--string-sample', type=int, default=120)
    parser.add_argument('--pointer-sample', type=int, default=200)
    parser.add_argument('--vft-topn', type=int, default=50)
    parser.add_argument('--vft-scan-bytes', type=int, default=0, help='0 scans full decoded payload')
    parser.add_argument('--float-sample', type=int, default=0, help='0 disables float3 candidate samples')
    parser.add_argument('--write-vec-samples', action='store_true')
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    tempdir = Path(tempfile.mkdtemp(prefix='codered_model_extract_'))
    all_inventory: list[dict] = []
    all_ptrs: list[dict] = []
    all_strings: list[dict] = []
    all_vfts: list[dict] = []
    all_roundtrips: list[dict] = []
    archive_masters: list[dict] = []
    errors: list[dict] = []
    try:
        rpfs = collect_inputs(args.inputs, tempdir)
        if not rpfs:
            raise SystemExit('No RPF files found.')
        for rpf_path in rpfs:
            try:
                inv, ptrs, strings, vfts, extra = scan_archive(rpf_path, args, outdir)
                all_inventory.extend(inv)
                all_ptrs.extend(ptrs)
                all_strings.extend(strings)
                all_vfts.extend(vfts)
                all_roundtrips.extend(extra['roundtrip_rows'])
                archive_masters.append(extra['master'])
                print(f'Scanned {rpf_path.name}: {len(inv)} candidate resources')
            except Exception as exc:
                errors.append({'archive_path': str(rpf_path), 'error': repr(exc)})
                print(f'Skipped {rpf_path}: {exc}')
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)

    write_csv(outdir / 'model_inventory.csv', all_inventory)
    write_csv(outdir / 'virtual_pointer_map.csv', all_ptrs)
    write_csv(outdir / 'strings.csv', all_strings)
    write_csv(outdir / 'vft_histogram.csv', all_vfts)
    write_csv(outdir / 'roundtrip_results.csv', all_roundtrips)
    write_csv(outdir / 'scan_errors.csv', errors)
    master = {
        'archives': archive_masters,
        'counts': {
            'candidate_resources': len(all_inventory),
            'virtual_pointer_rows': len(all_ptrs),
            'string_rows': len(all_strings),
            'vft_rows': len(all_vfts),
            'roundtrip_rows': len(all_roundtrips),
            'errors': len(errors),
        },
        'outputs': {
            'model_inventory': 'model_inventory.csv',
            'virtual_pointer_map': 'virtual_pointer_map.csv',
            'strings': 'strings.csv',
            'vft_histogram': 'vft_histogram.csv',
            'roundtrip_results': 'roundtrip_results.csv',
            'scan_errors': 'scan_errors.csv',
            'report': 'model_extract_report.md',
        },
        'safety': 'read-only; no RPF mutation; no semantic recompilation yet',
    }
    (outdir / 'model_resource_extract_master.json').write_text(json.dumps(master, indent=2), encoding='utf-8')
    write_summary(outdir, all_inventory, all_roundtrips, errors)
    print('Wrote', outdir)


if __name__ == '__main__':
    main()
