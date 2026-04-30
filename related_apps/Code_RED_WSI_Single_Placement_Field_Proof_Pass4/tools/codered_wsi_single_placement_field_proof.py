#!/usr/bin/env python3
from __future__ import annotations

import argparse, csv, hashlib, json, math, struct
from pathlib import Path
VBASE = 0x50000000

def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()

def u32(data: bytes, off: int) -> int:
    return struct.unpack_from('<I', data, off)[0] if off + 4 <= len(data) else 0

def vec4(data: bytes, off: int):
    if off + 16 > len(data): return []
    out=[]
    for v in struct.unpack_from('<4f', data, off): out.append(round(v, 6) if math.isfinite(v) else 'nan')
    return out

def ptr_target(ptr: int, size: int):
    return ptr - VBASE if VBASE <= ptr < VBASE + size else None

def cstr(data: bytes, off, max_len=512):
    if off is None or off < 0 or off >= len(data): return ''
    e=off
    while e < len(data) and e-off < max_len and data[e] != 0: e += 1
    return data[off:e].decode('latin-1', 'replace')

def parse_drawable_record(data: bytes, record_offset: int, record_size=224, name_ptr_rel=0xB8):
    name_ptr = u32(data, record_offset + name_ptr_rel)
    name_off = ptr_target(name_ptr, len(data))
    row3 = vec4(data, record_offset + 0x70)
    return {
        'record_offset': record_offset,
        'record_offset_hex': f'0x{record_offset:08X}',
        'record_size': record_size,
        'record_vft_hex': f'0x{u32(data, record_offset):08X}',
        'matrix_row0_guess': vec4(data, record_offset + 0x40),
        'matrix_row1_guess': vec4(data, record_offset + 0x50),
        'matrix_row2_guess': vec4(data, record_offset + 0x60),
        'matrix_row3_position_guess': row3,
        'position_guess': row3[:3] if len(row3) >= 3 else [],
        'bbox_min_guess': vec4(data, record_offset + 0x80),
        'bbox_max_guess': vec4(data, record_offset + 0x90),
        'instance_hash_guess_hex': f'0x{u32(data, record_offset + 0xA0):08X}',
        'drawable_flags_guess_hex': f'0x{u32(data, record_offset + 0xB0):08X}',
        'name_ptr_rel_guess': name_ptr_rel,
        'record_name_ptr_hex': f'0x{name_ptr:08X}' if name_ptr else '',
        'record_name_offset_hex': f'0x{name_off:08X}' if name_off is not None else '',
        'record_name': cstr(data, name_off),
        'raw_name_lane_hex': data[record_offset + 0xB0:record_offset + 0xC0].hex(),
        'record_sha1': sha1(data[record_offset:record_offset + record_size]),
    }

def write_csv(path: Path, rows):
    fields=[]
    for row in rows:
        for k in row:
            if k not in fields: fields.append(k)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        w=csv.DictWriter(f, fields); w.writeheader(); w.writerows(rows)

def main():
    ap=argparse.ArgumentParser(description='Code RED decoded WSI single-placement field proof')
    ap.add_argument('decoded_wsi')
    ap.add_argument('--record-offset', type=lambda s:int(s,0), required=True)
    ap.add_argument('--record-size', type=int, default=224)
    ap.add_argument('--name-ptr-rel', type=lambda s:int(s,0), default=0xB8)
    ap.add_argument('--expected-host', default='')
    ap.add_argument('--outdir', default='exports/wsi_single_placement_field_proof')
    args=ap.parse_args()
    path=Path(args.decoded_wsi); data=path.read_bytes(); outdir=Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)
    if args.record_offset < 0 or args.record_offset + args.record_size > len(data): raise SystemExit('record outside decoded WSI')
    rec=parse_drawable_record(data,args.record_offset,args.record_size,args.name_ptr_rel)
    rec_bytes=data[args.record_offset:args.record_offset+args.record_size]
    expected_ok=(not args.expected_host) or rec['record_name']==args.expected_host
    proof={
        'mode':'decoded_wsi_single_placement_field_proof',
        'decoded_wsi':str(path),
        'decoded_size':len(data),
        'decoded_sha1':sha1(data),
        'record_offset':args.record_offset,
        'record_offset_hex':f'0x{args.record_offset:08X}',
        'record_size':args.record_size,
        'expected_host':args.expected_host,
        'expected_host_matched':expected_ok,
        'record':rec,
        'record_bytes_hex':rec_bytes.hex(),
        'validation_passed':expected_ok and bool(rec['record_name']) and rec['record_vft_hex']=='0x01913300',
        'next_safe_action':'Use this exact decoded record as the first one-placement test target. Build archive rewrite only after final field choice is known.',
    }
    (outdir/'single_placement_field_proof.json').write_text(json.dumps(proof,indent=2), encoding='utf-8')
    write_csv(outdir/'single_placement_record.csv',[rec])
    (outdir/'record_bytes.hex.txt').write_text(rec_bytes.hex(),encoding='utf-8')
    (outdir/'single_placement_summary.txt').write_text('\n'.join([
        'Code RED decoded WSI single-placement field proof',
        f'decoded_wsi={path}',
        f'decoded_size={len(data)}',
        f'record_offset=0x{args.record_offset:08X}',
        f'record_name={rec["record_name"]}',
        f'expected_host={args.expected_host}',
        f'expected_host_matched={expected_ok}',
        f'position_guess={rec["position_guess"]}',
        f'record_sha1={rec["record_sha1"]}',
        f'validation_passed={proof["validation_passed"]}',
    ])+'\n', encoding='utf-8')
    print(json.dumps({'proof':str(outdir/'single_placement_field_proof.json'),'validation_passed':proof['validation_passed'],'record':rec},indent=2))
if __name__=='__main__': main()
