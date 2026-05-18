
#!/usr/bin/env python3
"""
Code RED Dynamite / Transport Car-Truck WSC Finder + Patcher

Purpose:
  Find likely dynamite / transport / escort WSC scripts inside imports/ and the
  content deep-scan candidate_payloads folder, then patch selected vehicle actor
  IDs into Truck01/Car01 using the same decoded RSC85 type-2 lane that worked
  for WagonThief, Ambush, and Prisoners.

Safety:
  - No source file is modified.
  - Preview before patching.
  - Blocks if replacement count exceeds --max-replacements unless --allow-many.
  - Blocks grown output unless --allow-grow.
  - Patches decoded binary IDs only; no ASCII digit-chain patching.
"""
from __future__ import annotations

import argparse, csv, hashlib, json, os, re, shutil, struct, subprocess, sys, tempfile, zlib
from pathlib import Path

AES_KEY_HASH = bytes.fromhex('87862497EE46855372B51C7A324A2BB5CD66F4AF')
AES_KEY_OFFSETS = [0x22A2300, 0x2293500]
DEFAULT_OLD_LOW = 1177
DEFAULT_OLD_HIGH = 1202
TRUCK_ID = 1193
CAR_ID = 1194
VEHICLE_NAMES = {
    1177:'Cart01',1178:'Cart02',1179:'Cart003',1180:'Cart004',1181:'Cart005',1182:'Cart006',
    1183:'Cart01',1184:'Cart02',1185:'Cart003',1186:'Cart004',1187:'Cart005',1188:'Cart006',
    1189:'Coach02',1190:'Coach03',1191:'Coach04',1192:'Coach05',1193:'Truck01',1194:'Car01',
    1195:'Wagon04',1196:'Wagon05',1197:'WagonPrison01',1198:'WagonGatling01',1199:'Wagon02',
    1200:'Chuckwagon',1201:'Chuckwagon02',1202:'Coach01'
}
DEFAULT_TERMS = ['dynamite','transport','escort','convoy','coach','wagon','stagecoach','explosive','crate','crates','ammo','powder']


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()

def sha1(data: bytes) -> bytes:
    return hashlib.sha1(data).digest()

def find_repo_root(start: Path) -> Path:
    p = start.resolve()
    for cur in [p, *p.parents]:
        if (cur/'tools').exists() or (cur/'Code_RED.bat').exists() or (cur/'main.py').exists():
            return cur
    return p

def likely_rdr_exe_paths(root: Path) -> list[Path]:
    paths = []
    if os.environ.get('CODERED_RDR_EXE'):
        paths.append(Path(os.environ['CODERED_RDR_EXE']))
    paths += [root/'rdr.exe', root.parent/'rdr.exe', Path.cwd()/'rdr.exe', Path.cwd().parent/'rdr.exe']
    out=[]; seen=set()
    for p in paths:
        k = str(p.resolve()) if p.exists() else str(p)
        if k not in seen:
            out.append(p); seen.add(k)
    return out

def search_aes_key_in_exe(exe: Path):
    info={'exe':str(exe),'exists':exe.exists(),'method':None,'key_sha1':None}
    if not exe.exists(): return None, info
    data=exe.read_bytes()
    for off in AES_KEY_OFFSETS:
        if 0 <= off <= len(data)-32:
            key=data[off:off+32]
            if sha1(key)==AES_KEY_HASH:
                info.update({'method':f'known_offset_0x{off:X}','key_sha1':sha1(key).hex().upper()})
                return key, info
    limit=min(len(data)-32, 1024*1024)
    for off in range(0, max(0, limit)+1, 4):
        key=data[off:off+32]
        if sha1(key)==AES_KEY_HASH:
            info.update({'method':f'fallback_scan_0x{off:X}','key_sha1':sha1(key).hex().upper()})
            return key, info
    info['method']='not_found'
    return None, info

def get_aes_key(root: Path, explicit_exe: str|None=None):
    attempts=[]
    for p in ([Path(explicit_exe)] if explicit_exe else likely_rdr_exe_paths(root)):
        key, info = search_aes_key_in_exe(p)
        attempts.append(info)
        if key is not None: return key, attempts
    return None, attempts

def aes_crypt_block(data: bytes, key: bytes, decrypt: bool) -> bytes:
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend
    except Exception as exc:
        raise RuntimeError("Package 'cryptography' is required. Run install_dynamite_transport_cartruck_wsc_deps.bat") from exc
    n=len(data)&-16
    prefix=data[:n]; suffix=data[n:]
    if not prefix: return data
    cipher=Cipher(algorithms.AES(key), modes.ECB(), backend=default_backend())
    out=prefix
    for _ in range(16):
        ctx = cipher.decryptor() if decrypt else cipher.encryptor()
        out = ctx.update(out)+ctx.finalize()
    return out+suffix

def parse_rsc_header(data: bytes) -> dict:
    if len(data)<16: return {'is_rsc':False,'reason':'too_small'}
    magic=data[:4]
    if magic not in (b'RSC\x05', b'RSC\x85', b'RSC\x86'):
        return {'is_rsc':False,'magic_hex':magic.hex().upper()}
    resource_type=struct.unpack_from('<I', data, 4)[0]
    flag1=struct.unpack_from('<i', data, 8)[0]
    flag2=struct.unpack_from('<i', data, 12)[0]
    f1u=struct.unpack_from('<I', data, 8)[0]
    f2u=struct.unpack_from('<I', data, 12)[0]
    virtual_size=(f2u & 0x7FF)*4096
    physical_size=(f1u & 0x7FF)*4096
    return {'is_rsc':True,'magic':'RSC'+f'{magic[3]:02X}','resource_type':resource_type,'flag1_signed':flag1,'flag2_signed':flag2,
            'flag1_hex':f'0x{f1u:08X}','flag2_hex':f'0x{f2u:08X}','header_size':16,'payload_size':len(data)-16,
            'virtual_size':virtual_size,'physical_size':physical_size,'expected_unpacked_size':virtual_size+physical_size}

def zstd_decompress(data: bytes, expected_size: int|None=None) -> bytes:
    try:
        import zstandard as zstd
        dctx=zstd.ZstdDecompressor()
        try:
            return dctx.decompress(data, max_output_size=expected_size or 0)
        except Exception:
            with dctx.stream_reader(data) as r:
                return r.read()
    except Exception as py_exc:
        zstd_exe=shutil.which('zstd') or shutil.which('zstd.exe')
        if not zstd_exe: raise py_exc
        with tempfile.TemporaryDirectory() as td:
            inp=Path(td)/'in.zst'; out=Path(td)/'out.bin'
            inp.write_bytes(data)
            cp=subprocess.run([zstd_exe,'-d','-q','-f',str(inp),'-o',str(out)], text=True, capture_output=True)
            if cp.returncode!=0: raise RuntimeError(cp.stderr.strip())
            return out.read_bytes()

def zstd_compress(data: bytes, level:int=22, write_content_size: bool=True) -> bytes:
    try:
        import zstandard as zstd
        cctx=zstd.ZstdCompressor(level=level, write_content_size=write_content_size)
        return cctx.compress(data)
    except Exception as py_exc:
        zstd_exe=shutil.which('zstd') or shutil.which('zstd.exe')
        if not zstd_exe: raise py_exc
        with tempfile.TemporaryDirectory() as td:
            inp=Path(td)/'in.bin'; out=Path(td)/'out.zst'
            inp.write_bytes(data)
            args=[zstd_exe,f'-{level}','-q','-f',str(inp),'-o',str(out)]
            if not write_content_size: args.insert(1,'--no-content-size')
            cp=subprocess.run(args, text=True, capture_output=True)
            if cp.returncode!=0: raise RuntimeError(cp.stderr.strip())
            return out.read_bytes()

def zstd_skippable_padding(n:int) -> bytes:
    if n<=0: return b''
    # skippable frame: magic 0x184D2A50 + size + payload
    return struct.pack('<II', 0x184D2A50, max(0,n-8)) + (b'\x00'*max(0,n-8))

def try_decompress_payload(payload: bytes, expected: int|None=None):
    errors=[]
    try:
        dec=zstd_decompress(payload, expected)
        return dec, 'zstd', None
    except Exception as exc:
        errors.append(f'zstd:{exc}')
    for name, fn in [('zlib', lambda b: zlib.decompress(b)), ('raw-deflate', lambda b: zlib.decompress(b, -zlib.MAX_WBITS))]:
        try: return fn(payload), name, None
        except Exception as exc: errors.append(f'{name}:{exc}')
    return b'', 'unknown', '; '.join(errors)

def decode_rsc_script(path: Path, key: bytes):
    data=path.read_bytes()
    rsc=parse_rsc_header(data)
    if not rsc.get('is_rsc'):
        return {'input':str(path),'input_size':len(data),'input_sha256':sha256(data),'rsc':rsc,'decode':{'error':'not RSC'}}, data, b'', 'raw'
    payload=data[16:]
    dec_payload=aes_crypt_block(payload, key, True)
    decoded, codec, err=try_decompress_payload(dec_payload, rsc.get('expected_unpacked_size') or None)
    report={'input':str(path),'input_size':len(data),'input_sha256':sha256(data),'rsc':rsc,
            'decode':{'encrypted_payload_size':len(payload),'decrypted_payload_sha256':sha256(dec_payload),'codec':codec,'decompress_error':err,'decoded_size':len(decoded),'decoded_sha256':sha256(decoded) if decoded else None}}
    return report, data, decoded, codec

def extract_ascii_terms(data: bytes, min_len=4) -> list[str]:
    out=[]; cur=[]
    for b in data:
        if 32 <= b <= 126:
            cur.append(chr(b))
        else:
            if len(cur)>=min_len: out.append(''.join(cur))
            cur=[]
    if len(cur)>=min_len: out.append(''.join(cur))
    return out

def count_terms(decoded: bytes, terms: list[str]) -> dict[str,int]:
    low=decoded.lower()
    return {t: low.count(t.lower().encode('ascii','ignore')) for t in terms}

def pack_value(value:int, fmt:str) -> bytes:
    if fmt=='u16be': return struct.pack('>H', value)
    if fmt=='u16le': return struct.pack('<H', value)
    if fmt=='i16be': return struct.pack('>h', value)
    if fmt=='i16le': return struct.pack('<h', value)
    if fmt=='u32be': return struct.pack('>I', value)
    if fmt=='u32le': return struct.pack('<I', value)
    if fmt=='i32be': return struct.pack('>i', value)
    if fmt=='i32le': return struct.pack('<i', value)
    raise ValueError(f'unsupported int format: {fmt}')

def count_ids(decoded: bytes, old_ids: list[int], fmt='u16be') -> dict[int,int]:
    return {v: decoded.count(pack_value(v,fmt)) for v in old_ids}

def patch_ids(decoded: bytes, old_ids: list[int], replacements: list[int], fmt='u16be'):
    data=bytearray(decoded)
    rows=[]
    old_set=set(old_ids)
    step={'u16be':2,'u16le':2,'i16be':2,'i16le':2,'u32be':4,'u32le':4,'i32be':4,'i32le':4}[fmt]
    # collect exact hit offsets in file order so alternating is deterministic
    for off in range(0, len(data)-step+1):
        b=bytes(data[off:off+step])
        old=None
        for v in old_ids:
            if b == pack_value(v, fmt): old=v; break
        if old is None: continue
        new = replacements[len(rows) % len(replacements)]
        data[off:off+step] = pack_value(new, fmt)
        rows.append({'offset':off,'offset_hex':f'0x{off:X}','old':old,'old_name':VEHICLE_NAMES.get(old,''),'new':new,'new_name':VEHICLE_NAMES.get(new,''),'format':fmt})
    return bytes(data), rows

def fit_compress(decoded: bytes, target_payload_size: int, allow_grow: bool):
    attempts=[]
    best=None
    # first try levels/content-size permutations; prefer zstd because original WSCs are zstd in this project
    for level in [22,21,20,19,18,17,16,15,12,9,6,3,1]:
        for wcs in [False, True]:
            try:
                comp=zstd_compress(decoded, level, write_content_size=wcs)
                attempts.append({'codec':f'zstd-level-{level}' + ('-no-content-size' if not wcs else ''),'size':len(comp),'fit':'exact' if len(comp)==target_payload_size else ('under' if len(comp)<target_payload_size else 'too-large')})
                if len(comp) <= target_payload_size:
                    pad=target_payload_size-len(comp)
                    return comp + zstd_skippable_padding(pad), {'fit_mode':'exact' if pad==0 else 'zstd-skippable-padding','codec':attempts[-1]['codec'],'pad':pad,'attempts':attempts,'compressed_or_padded_size':target_payload_size}
                if best is None or len(comp)<len(best[1]): best=(attempts[-1]['codec'], comp)
            except Exception as exc:
                attempts.append({'codec':f'zstd-level-{level}' + ('-no-content-size' if not wcs else ''),'error':str(exc)})
    if allow_grow and best:
        codec, comp=best
        return comp, {'fit_mode':'allow-grow-variable-size','codec':codec,'pad':0,'original_payload_size':target_payload_size,'grown_payload_size':len(comp),'over_by':len(comp)-target_payload_size,'attempts':attempts,'warning':'Output WSC is larger than original. Use an RPF importer that updates file size metadata.'}
    over=None
    if best: over=len(best[1])-target_payload_size
    raise RuntimeError(json.dumps({'fit_mode':'blocked-compressed-output-too-large','smallest_over_by':over,'attempts':attempts}, indent=2))

def repack_rsc(original: bytes, patched_decoded: bytes, key: bytes, codec: str, allow_grow: bool):
    rsc=parse_rsc_header(original)
    if not rsc.get('is_rsc'): raise RuntimeError('Input is not RSC')
    target_payload_size=len(original)-16
    comp, fit = fit_compress(patched_decoded, target_payload_size, allow_grow)
    encrypted=aes_crypt_block(comp, key, False)
    out=original[:16]+encrypted
    # Validate output by decrypt/decompress roundtrip
    dec=aes_crypt_block(out[16:], key, True)
    decoded2, vcodec, verr=try_decompress_payload(dec, rsc.get('expected_unpacked_size') or None)
    fit.update({'output_size':len(out),'output_sha256':sha256(out),'validate_codec':vcodec,'validate_error':verr,'validate_decoded_size':len(decoded2),'validate_ok':decoded2==patched_decoded})
    return out, fit

def csv_write(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    keys=[]
    for r in rows:
        for k in r.keys():
            if k not in keys: keys.append(k)
    with path.open('w', newline='', encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=keys)
        w.writeheader(); w.writerows(rows)

def make_candidate_paths(root: Path, input_dirs: list[str], include_deepscan: bool):
    paths=[]
    for d in input_dirs:
        p=Path(d)
        if not p.is_absolute(): p=root/p
        if p.exists():
            paths += sorted(p.glob('*.wsc')) + sorted(p.glob('*.raw.bin'))
    if include_deepscan:
        cp = root/'logs'/'content_rpf_deep_scan'/'candidate_payloads'
        if cp.exists():
            paths += sorted(cp.glob('*.raw.bin')) + sorted(cp.glob('*.wsc'))
    # dedupe
    out=[]; seen=set()
    for p in paths:
        try: k=str(p.resolve())
        except Exception: k=str(p)
        if k not in seen:
            out.append(p); seen.add(k)
    return out

def cmd_status(args):
    root=find_repo_root(Path.cwd())
    key, attempts=get_aes_key(root, args.rdr_exe)
    print(json.dumps({'tool':'Code RED Dynamite/Transport Car-Truck WSC Finder','version':'1.0','cwd':str(Path.cwd()),'repo_root_guess':str(root),'default_terms':DEFAULT_TERMS,'default_patch':'1177..1202 -> alternating 1193 Truck01 / 1194 Car01','aes_key_available':key is not None,'aes_key_attempts':attempts}, indent=2))
    return 0

def cmd_scan(args):
    root=find_repo_root(Path.cwd())
    key, attempts=get_aes_key(root, args.rdr_exe)
    if key is None:
        print(json.dumps({'status':'blocked-no-aes-key','aes_key_attempts':attempts}, indent=2)); return 2
    terms=args.terms or DEFAULT_TERMS
    old_ids=args.old_ids or list(range(args.old_low, args.old_high+1))
    rows=[]
    candidates=make_candidate_paths(root, args.input_dirs, args.include_deepscan)
    outdir=Path(args.out_dir); outdir.mkdir(parents=True, exist_ok=True)
    for path in candidates:
        try:
            report, original, decoded, codec = decode_rsc_script(path, key)
            term_counts=count_terms(decoded, terms) if decoded else {}
            id_counts=count_ids(decoded, old_ids, args.int_format) if decoded else {}
            term_score=sum(term_counts.values())
            id_hits=sum(id_counts.values())
            interesting = term_score>0 or id_hits>0 or (args.all_files)
            if not interesting: continue
            # Save per-file minimal string sample if terms found
            sample=[]
            if term_score>0:
                strings=extract_ascii_terms(decoded)
                for s in strings:
                    sl=s.lower()
                    if any(t.lower() in sl for t in terms):
                        sample.append(s[:140])
                        if len(sample)>=8: break
            rel=str(path)
            rows.append({'input':rel,'size':report.get('input_size'),'sha256':report.get('input_sha256'),'resource_type':report.get('rsc',{}).get('resource_type'),
                         'decoded_size':report.get('decode',{}).get('decoded_size'),'decode_codec':report.get('decode',{}).get('codec'),'decode_error':report.get('decode',{}).get('decompress_error'),
                         'term_hits':term_score,'vehicle_hits':id_hits,'id_counts_json':json.dumps({str(k):v for k,v in id_counts.items() if v}, sort_keys=True),
                         'term_counts_json':json.dumps({k:v for k,v in term_counts.items() if v}, sort_keys=True),'sample_strings':' | '.join(sample)})
        except Exception as exc:
            rows.append({'input':str(path),'status':'error','error':repr(exc)})
    rows.sort(key=lambda r:(int(r.get('term_hits') or 0), int(r.get('vehicle_hits') or 0)), reverse=True)
    csv_path=outdir/'dynamite_transport_scan.csv'
    csv_write(csv_path, rows)
    print(json.dumps({'status':'complete','files_scanned':len(candidates),'matches':len(rows),'terms':terms,'out_csv':str(csv_path),'top':rows[:15]}, indent=2))
    return 0

def cmd_patch(args):
    root=find_repo_root(Path.cwd())
    key, attempts=get_aes_key(root, args.rdr_exe)
    if key is None:
        print(json.dumps({'status':'blocked-no-aes-key','aes_key_attempts':attempts}, indent=2)); return 2
    inp=Path(args.input)
    if not inp.is_absolute(): inp=root/inp
    out=Path(args.out)
    if not out.is_absolute(): out=root/out
    report, original, decoded, codec = decode_rsc_script(inp, key)
    if not decoded:
        print(json.dumps({'status':'blocked-decode-failed', **report}, indent=2)); return 3
    old_ids=args.old_ids or list(range(args.old_low, args.old_high+1))
    if args.mode=='car-only': repl=[CAR_ID]
    elif args.mode=='truck-only': repl=[TRUCK_ID]
    else: repl=[TRUCK_ID, CAR_ID]
    before=count_ids(decoded, old_ids, args.int_format)
    patched, rows=patch_ids(decoded, old_ids, repl, args.int_format)
    after=count_ids(patched, old_ids, args.int_format)
    preview_csv=out.with_suffix(out.suffix+'.preview_replacements.csv')
    csv_write(preview_csv, rows)
    base={**report,'mode':args.mode,'int_format':args.int_format,'old_ids':old_ids,'replacement_ids':repl,
          'before_counts':{str(k):v for k,v in before.items() if v},'candidate_replacements':len(rows),'after_counts':{str(k):v for k,v in after.items() if v},'preview_csv':str(preview_csv)}
    if args.preview_only:
        base['status']='preview-only'
        print(json.dumps(base, indent=2)); return 0
    if len(rows)==0:
        base.update({'status':'blocked-no-replacements'}); print(json.dumps(base, indent=2)); return 4
    if len(rows)>args.max_replacements and not args.allow_many:
        base.update({'status':'blocked-too-many-replacements','max_replacements':args.max_replacements,'note':'Use more specific --old-ids or --allow-many only after preview review.'})
        print(json.dumps(base, indent=2)); return 5
    try:
        output, fit=repack_rsc(original, patched, key, codec, args.allow_grow)
    except Exception as exc:
        base.update({'status':'blocked-repack-fit-failed','repack_error':str(exc)})
        print(json.dumps(base, indent=2)); return 6
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(output)
    edits_csv=out.with_suffix(out.suffix+'.replacements.csv')
    csv_write(edits_csv, rows)
    base.update({'status':'patched','output':str(out),'output_size':len(output),'output_sha256':sha256(output),'edits_csv':str(edits_csv),'fit_report':fit})
    print(json.dumps(base, indent=2)); return 0

def build_parser():
    p=argparse.ArgumentParser()
    p.add_argument('--rdr-exe', default=None)
    sub=p.add_subparsers(dest='cmd', required=True)
    sp=sub.add_parser('status'); sp.set_defaults(func=cmd_status)
    sp=sub.add_parser('scan')
    sp.add_argument('--input-dirs', nargs='*', default=['imports'])
    sp.add_argument('--include-deepscan', action='store_true')
    sp.add_argument('--out-dir', default='logs/dynamite_transport_cartruck_scan')
    sp.add_argument('--terms', nargs='*', default=None)
    sp.add_argument('--old-ids', nargs='*', type=int, default=None)
    sp.add_argument('--old-low', type=int, default=DEFAULT_OLD_LOW)
    sp.add_argument('--old-high', type=int, default=DEFAULT_OLD_HIGH)
    sp.add_argument('--int-format', default='u16be')
    sp.add_argument('--all-files', action='store_true')
    sp.set_defaults(func=cmd_scan)
    sp=sub.add_parser('patch')
    sp.add_argument('--input', required=True)
    sp.add_argument('--out', required=True)
    sp.add_argument('--mode', choices=['car-truck','car-only','truck-only'], default='car-truck')
    sp.add_argument('--old-ids', nargs='*', type=int, default=None)
    sp.add_argument('--old-low', type=int, default=DEFAULT_OLD_LOW)
    sp.add_argument('--old-high', type=int, default=DEFAULT_OLD_HIGH)
    sp.add_argument('--int-format', default='u16be')
    sp.add_argument('--max-replacements', type=int, default=32)
    sp.add_argument('--allow-many', action='store_true')
    sp.add_argument('--allow-grow', action='store_true')
    sp.add_argument('--preview-only', action='store_true')
    sp.set_defaults(func=cmd_patch)
    return p

def main(argv=None):
    args=build_parser().parse_args(argv)
    return args.func(args)

if __name__=='__main__':
    raise SystemExit(main())
