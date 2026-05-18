#!/usr/bin/env python3
"""
Code RED Arm Population Micro Tests
Safely generate one-ID-at-a-time WSC vehicle replacements for arm_population.wsc.

This is intentionally narrow. It decodes RSC85 type-2 WSC resources using the RDR1
AES key from rdr.exe, patches exact u16be actor IDs, repacks to the original payload
size when possible, validates the output, and never modifies the source file.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

AES_KEY_HASH = bytes.fromhex("87862497EE46855372B51C7A324A2BB5CD66F4AF")
AES_KEY_OFFSETS = (0x22A2300, 0x2293500)
DEFAULT_OLD_IDS = [1183,1184,1185,1186,1187,1188,1195,1196,1197,1198,1199,1200,1201,1202]
VEHICLE_NAMES = {
    1177:"Stagecoach", 1178:"Stagecoach002", 1179:"Stagecoach003", 1180:"Stagecoach004",
    1181:"dlc_Vehicle01x", 1182:"StagecoachGatling01", 1183:"Cart01", 1184:"Cart02",
    1185:"Cart003", 1186:"Cart004", 1187:"Cart005", 1188:"Cart006", 1189:"Canoe01",
    1190:"Raft02", 1191:"Raft03", 1192:"Raft01", 1193:"Truck01", 1194:"Car01",
    1195:"Wagon04", 1196:"Wagon05", 1197:"WagonPrison01", 1198:"WagonGatling01",
    1199:"Wagon02", 1200:"Chuckwagon", 1201:"Chuckwagon02", 1202:"Coach01",
}

try:
    import zstandard as zstd
except Exception:  # pragma: no cover
    zstd = None

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
except Exception:  # pragma: no cover
    Cipher = None


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()

def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest().upper()

@dataclass
class RscInfo:
    magic: str
    resource_type: int
    flag1: int
    flag2: int
    header_size: int
    payload_size: int
    virtual_size: int
    physical_size: int
    expected_unpacked_size: int


def signed32(v: int) -> int:
    return struct.unpack('<i', struct.pack('<I', v & 0xFFFFFFFF))[0]


def parse_rsc(data: bytes) -> RscInfo:
    if len(data) < 16 or data[:3] != b'RSC':
        raise ValueError('not an RSC resource')
    magic = 'RSC%02X' % data[3]
    resource_type, flag1, flag2 = struct.unpack_from('<III', data, 4)
    # RDR1 compact size flags used by the files we have been patching.
    virtual_pages = flag2 & 0x7FFF
    virtual_size = virtual_pages * 4096
    physical_size = 0
    return RscInfo(
        magic=magic,
        resource_type=resource_type,
        flag1=signed32(flag1),
        flag2=signed32(flag2),
        header_size=16,
        payload_size=len(data) - 16,
        virtual_size=virtual_size,
        physical_size=physical_size,
        expected_unpacked_size=virtual_size + physical_size,
    )


def find_rdr_exe(cwd: Path, override: Optional[str]) -> List[Path]:
    paths: List[Path] = []
    if override:
        paths.append(Path(override))
    env = os.environ.get('CODERED_RDR_EXE')
    if env:
        paths.append(Path(env))
    paths.append(cwd / 'rdr.exe')
    paths.append(cwd.parent / 'rdr.exe')
    # de-duplicate preserving order
    seen = set()
    out = []
    for p in paths:
        rp = str(p.resolve()) if p.exists() else str(p)
        if rp not in seen:
            seen.add(rp)
            out.append(p)
    return out


def find_aes_key(cwd: Path, override: Optional[str]=None) -> Tuple[Optional[bytes], List[dict]]:
    attempts = []
    for exe in find_rdr_exe(cwd, override):
        item = {"exe": str(exe), "exists": exe.exists(), "method": None, "key_sha1": None}
        if not exe.exists():
            attempts.append(item)
            continue
        data = exe.read_bytes()
        for off in AES_KEY_OFFSETS:
            if off + 32 <= len(data):
                key = data[off:off+32]
                if hashlib.sha1(key).digest() == AES_KEY_HASH:
                    item["method"] = f"known_offset_0x{off:X}"
                    item["key_sha1"] = sha1(key)
                    attempts.append(item)
                    return key, attempts
        # Slow fallback: scan 4-byte aligned windows. Keep limited but useful.
        for off in range(0, max(0, len(data)-32), 4):
            key = data[off:off+32]
            if hashlib.sha1(key).digest() == AES_KEY_HASH:
                item["method"] = f"scan_0x{off:X}"
                item["key_sha1"] = sha1(key)
                attempts.append(item)
                return key, attempts
        attempts.append(item)
    return None, attempts


def _aes_crypt(data: bytes, key: bytes, encrypt: bool) -> bytes:
    if Cipher is None:
        raise RuntimeError('Missing cryptography package. Run install_arm_population_microtest_deps.bat')
    buf = bytearray(data)
    length = len(buf) & ~15
    if length <= 0:
        return bytes(buf)
    cipher = Cipher(algorithms.AES(key), modes.ECB(), backend=default_backend())
    for _ in range(16):
        ctx = cipher.encryptor() if encrypt else cipher.decryptor()
        block = ctx.update(bytes(buf[:length])) + ctx.finalize()
        buf[:length] = block
    return bytes(buf)


def aes_decrypt(data: bytes, key: bytes) -> bytes:
    return _aes_crypt(data, key, False)


def aes_encrypt(data: bytes, key: bytes) -> bytes:
    return _aes_crypt(data, key, True)


def zstd_decompress(data: bytes, expected_size: int) -> bytes:
    if zstd is None:
        raise RuntimeError('Missing zstandard package. Run install_arm_population_microtest_deps.bat')
    dctx = zstd.ZstdDecompressor()
    try:
        return dctx.decompress(data, max_output_size=max(expected_size, 1))
    except Exception:
        with dctx.stream_reader(data) as reader:
            return reader.read()


def zstd_compress_variants(data: bytes) -> List[Tuple[str, bytes]]:
    if zstd is None:
        raise RuntimeError('Missing zstandard package. Run install_arm_population_microtest_deps.bat')
    variants = []
    for level in range(22, 0, -1):
        for write_content_size in (False, True):
            cctx = zstd.ZstdCompressor(level=level, write_content_size=write_content_size)
            name = f"zstd-level-{level}-{'content-size' if write_content_size else 'no-content-size'}"
            try:
                variants.append((name, cctx.compress(data)))
            except Exception:
                pass
    variants.sort(key=lambda x: len(x[1]))
    return variants


def zstd_skippable_padding(pad_len: int) -> Optional[bytes]:
    if pad_len == 0:
        return b''
    if pad_len < 8:
        return None
    # 0x184D2A50 little-endian is a valid zstd skippable frame magic.
    payload_len = pad_len - 8
    return struct.pack('<II', 0x184D2A50, payload_len) + (b'\x00' * payload_len)

@dataclass
class DecodedWsc:
    source: Path
    original: bytes
    rsc: RscInfo
    encrypted_payload: bytes
    decrypted_payload: bytes
    decoded_payload: bytes
    aes_key: bytes
    key_attempts: List[dict]


def decode_wsc(path: Path, cwd: Path, rdr_exe: Optional[str]) -> DecodedWsc:
    original = path.read_bytes()
    rsc = parse_rsc(original)
    if rsc.magic not in ('RSC85','RSC05','RSC86'):
        raise ValueError(f'unsupported RSC magic {rsc.magic}')
    if rsc.resource_type != 2:
        raise ValueError(f'resource_type {rsc.resource_type} is not WSC/script type 2')
    key, attempts = find_aes_key(cwd, rdr_exe)
    if not key:
        raise RuntimeError('Could not find RDR AES key. Set CODERED_RDR_EXE to rdr.exe, not PlayRDR.exe')
    encrypted_payload = original[16:]
    decrypted_payload = aes_decrypt(encrypted_payload, key)
    decoded = zstd_decompress(decrypted_payload, rsc.expected_unpacked_size)
    if rsc.expected_unpacked_size and len(decoded) != rsc.expected_unpacked_size:
        # Not fatal, but preserve the warning via reports.
        pass
    return DecodedWsc(path, original, rsc, encrypted_payload, decrypted_payload, decoded, key, attempts)


def find_u16be_hits(data: bytes, ids: Iterable[int]) -> List[dict]:
    ids = list(ids)
    needles = {struct.pack('>H', i): i for i in ids if 0 <= i <= 0xFFFF}
    hits = []
    for off in range(0, len(data) - 1):
        val = needles.get(data[off:off+2])
        if val is not None:
            hits.append({
                'offset': off,
                'old_id': val,
                'old_name': VEHICLE_NAMES.get(val, ''),
                'before_hex': data[max(0, off-8):off].hex(' ').upper(),
                'value_hex': data[off:off+2].hex(' ').upper(),
                'after_hex': data[off+2:min(len(data), off+10)].hex(' ').upper(),
            })
    return hits


def apply_u16be_patch(data: bytes, old_id: int, target_id: int) -> Tuple[bytes, List[dict]]:
    out = bytearray(data)
    hits = find_u16be_hits(data, [old_id])
    new_bytes = struct.pack('>H', target_id)
    repl = []
    for h in hits:
        off = int(h['offset'])
        out[off:off+2] = new_bytes
        row = dict(h)
        row.update({'target_id': target_id, 'target_name': VEHICLE_NAMES.get(target_id, ''), 'new_value_hex': new_bytes.hex(' ').upper()})
        repl.append(row)
    return bytes(out), repl


def repack_wsc(decoded: DecodedWsc, new_payload: bytes, allow_variable_size: bool=False, max_growth: int=0) -> Tuple[Optional[bytes], dict]:
    original_payload_size = decoded.rsc.payload_size
    attempts = []
    chosen = None
    for name, comp in zstd_compress_variants(new_payload):
        attempts.append({'codec': name, 'size': len(comp), 'delta': len(comp) - original_payload_size})
        if len(comp) == original_payload_size:
            chosen = (name, comp, 'exact')
            break
        if len(comp) < original_payload_size:
            pad = original_payload_size - len(comp)
            padding = zstd_skippable_padding(pad)
            if padding is not None:
                chosen = (name, comp + padding, 'zstd-skippable-padding')
                break
    if chosen is None:
        smallest_name, smallest = min(zstd_compress_variants(new_payload), key=lambda x: len(x[1]))
        growth = len(smallest) - original_payload_size
        if allow_variable_size and growth <= max_growth:
            chosen = (smallest_name, smallest, 'variable-size-rpf-required')
        else:
            return None, {
                'fit_mode': 'blocked-compressed-output-too-large',
                'original_payload_size': original_payload_size,
                'smallest_size': len(smallest),
                'smallest_over_by': growth,
                'attempts': attempts,
            }
    name, compressed, fit_mode = chosen
    encrypted = aes_encrypt(compressed, decoded.aes_key)
    output = decoded.original[:16] + encrypted
    # Validate by decoding the newly packed resource.
    try:
        val_dec = aes_decrypt(output[16:], decoded.aes_key)
        val_payload = zstd_decompress(val_dec, decoded.rsc.expected_unpacked_size)
        validate_ok = (val_payload == new_payload)
        validate_error = None
    except Exception as e:
        validate_ok = False
        validate_error = repr(e)
    return output, {
        'fit_mode': fit_mode,
        'chosen_codec': name,
        'original_payload_size': original_payload_size,
        'compressed_or_padded_size': len(compressed),
        'output_size': len(output),
        'output_sha256': sha256(output),
        'validate_ok': validate_ok,
        'validate_decoded_size': len(new_payload) if validate_ok else None,
        'validate_error': validate_error,
        'attempts': attempts[:12],
    }


def write_csv(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text('', encoding='utf-8')
        return
    # Summary rows intentionally have different fields depending on status
    # (skipped, preview-only, blocked, patched).  Python csv.DictWriter
    # throws if later rows contain fields not present in the first row, so
    # build a stable union of all keys before writing.
    preferred = [
        'old_id', 'old_name', 'target_id', 'target_name', 'status', 'hits',
        'output', 'validate_ok', 'fit_mode', 'preview_csv', 'replacements_csv',
        'original_payload_size', 'smallest_size', 'smallest_over_by'
    ]
    seen = set()
    keys = []
    for k in preferred:
        if any(k in row for row in rows):
            keys.append(k)
            seen.add(k)
    for row in rows:
        for k in row.keys():
            if k not in seen:
                keys.append(k)
                seen.add(k)
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def cmd_status(args) -> int:
    cwd = Path.cwd()
    key, attempts = find_aes_key(cwd, getattr(args, 'rdr_exe', None))
    print(json.dumps({
        'tool': 'Code RED Arm Population Micro Tests',
        'version': '1.1',
        'cwd': str(cwd),
        'aes_key_available': key is not None,
        'aes_key_attempts': attempts,
        'default_input': 'imports\\arm_population.wsc',
        'default_ids': DEFAULT_OLD_IDS,
        'notes': [
            'Generates one-ID-at-a-time arm_population WSC variants.',
            'Uses u16be direct actor IDs only by default.',
            'Never modifies the original file.',
        ]
    }, indent=2))
    return 0


def cmd_scan(args) -> int:
    cwd = Path.cwd()
    inp = Path(args.input)
    out = Path(args.out)
    ids = args.old_ids or DEFAULT_OLD_IDS
    try:
        dec = decode_wsc(inp, cwd, args.rdr_exe)
        hits = find_u16be_hits(dec.decoded_payload, ids)
        write_csv(out / f'{inp.name}.u16be_vehicle_hits.csv', hits)
        counts: Dict[str,int] = {}
        for h in hits:
            k = f"{h['old_id']} {h['old_name']}"
            counts[k] = counts.get(k, 0) + 1
        report = {
            'input': str(inp),
            'input_size': len(dec.original),
            'input_sha256': sha256(dec.original),
            'rsc': dec.rsc.__dict__,
            'decode': {'codec':'zstd','decoded_size':len(dec.decoded_payload),'decoded_sha256':sha256(dec.decoded_payload)},
            'int_format': 'u16be',
            'scan_ids': ids,
            'hits': len(hits),
            'counts': counts,
            'hits_csv': str(out / f'{inp.name}.u16be_vehicle_hits.csv'),
        }
        out.mkdir(parents=True, exist_ok=True)
        (out / f'{inp.name}.scan_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({'status':'error','error':repr(e)}, indent=2))
        return 1


def cmd_make_micro(args) -> int:
    cwd = Path.cwd()
    inp = Path(args.input)
    out_dir = Path(args.out_dir)
    old_ids = args.old_ids or DEFAULT_OLD_IDS
    target_ids = args.target_ids or [1194]
    max_replacements = args.max_replacements
    allow_variable = args.allow_variable_size
    max_growth = args.max_growth
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = []
    try:
        dec = decode_wsc(inp, cwd, args.rdr_exe)
    except Exception as e:
        print(json.dumps({'status':'error','stage':'decode','error':repr(e)}, indent=2))
        return 1

    for old_id in old_ids:
        hits = find_u16be_hits(dec.decoded_payload, [old_id])
        preview_csv = out_dir / f'{inp.stem}_{old_id}_{VEHICLE_NAMES.get(old_id,"unknown")}_preview_hits.csv'
        write_csv(preview_csv, hits)
        if not hits:
            summary.append({'old_id': old_id, 'old_name': VEHICLE_NAMES.get(old_id,''), 'status': 'skipped-no-hits', 'hits': 0})
            continue
        if len(hits) > max_replacements:
            summary.append({'old_id': old_id, 'old_name': VEHICLE_NAMES.get(old_id,''), 'status': 'blocked-too-many-hits', 'hits': len(hits), 'preview_csv': str(preview_csv)})
            continue
        for target_id in target_ids:
            patched_payload, repl = apply_u16be_patch(dec.decoded_payload, old_id, target_id)
            target_name = VEHICLE_NAMES.get(target_id, f'id{target_id}')
            output_name = f'{inp.stem}_{old_id}_{VEHICLE_NAMES.get(old_id,"ID").replace("/","_")}_to_{target_id}_{target_name}.wsc'
            output_path = out_dir / output_name
            replacements_csv = output_path.with_suffix(output_path.suffix + '.replacements.csv')
            write_csv(replacements_csv, repl)
            if args.preview_only:
                summary.append({'old_id': old_id, 'old_name': VEHICLE_NAMES.get(old_id,''), 'target_id': target_id, 'target_name': target_name, 'status': 'preview-only', 'hits': len(hits), 'preview_csv': str(preview_csv)})
                continue
            output, fit = repack_wsc(dec, patched_payload, allow_variable_size=allow_variable, max_growth=max_growth)
            if output is None:
                summary.append({'old_id': old_id, 'old_name': VEHICLE_NAMES.get(old_id,''), 'target_id': target_id, 'target_name': target_name, 'status': 'blocked-fit', 'hits': len(hits), **fit})
                continue
            output_path.write_bytes(output)
            report = {
                'input': str(inp),
                'output': str(output_path),
                'input_sha256': sha256(dec.original),
                'output_sha256': sha256(output),
                'rsc': dec.rsc.__dict__,
                'mode': 'arm-population-micro-one-id',
                'int_format': 'u16be',
                'old_id': old_id,
                'old_name': VEHICLE_NAMES.get(old_id,''),
                'target_id': target_id,
                'target_name': target_name,
                'replacements': len(repl),
                'preview_hits_csv': str(preview_csv),
                'replacements_csv': str(replacements_csv),
                'fit_report': fit,
                'status': 'patched' if fit.get('validate_ok') else 'patched-but-validation-failed',
            }
            output_path.with_suffix(output_path.suffix + '.report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            summary.append({'old_id': old_id, 'old_name': VEHICLE_NAMES.get(old_id,''), 'target_id': target_id, 'target_name': target_name, 'status': report['status'], 'hits': len(hits), 'output': str(output_path), 'validate_ok': fit.get('validate_ok'), 'fit_mode': fit.get('fit_mode')})
    summary_csv = out_dir / 'arm_population_microtest_summary.csv'
    write_csv(summary_csv, summary)
    final = {'status':'complete', 'input': str(inp), 'out_dir': str(out_dir), 'summary_csv': str(summary_csv), 'variants': summary}
    (out_dir / 'arm_population_microtest_summary.json').write_text(json.dumps(final, indent=2), encoding='utf-8')
    print(json.dumps(final, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='Code RED Arm Population Micro Tests')
    sub = p.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('status')
    s.add_argument('--rdr-exe')
    s.set_defaults(func=cmd_status)

    s = sub.add_parser('scan')
    s.add_argument('--input', default='imports/arm_population.wsc')
    s.add_argument('--out', default='logs/arm_population_microtests/scan')
    s.add_argument('--old-ids', nargs='*', type=int)
    s.add_argument('--rdr-exe')
    s.set_defaults(func=cmd_scan)

    s = sub.add_parser('make-micro-tests')
    s.add_argument('--input', default='imports/arm_population.wsc')
    s.add_argument('--out-dir', default='patches/arm_population_microtests')
    s.add_argument('--old-ids', nargs='*', type=int)
    s.add_argument('--target-ids', nargs='*', type=int, default=[1194])
    s.add_argument('--max-replacements', type=int, default=4)
    s.add_argument('--preview-only', action='store_true')
    s.add_argument('--allow-variable-size', action='store_true')
    s.add_argument('--max-growth', type=int, default=64)
    s.add_argument('--rdr-exe')
    s.set_defaults(func=cmd_make_micro)
    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)

if __name__ == '__main__':
    raise SystemExit(main())
