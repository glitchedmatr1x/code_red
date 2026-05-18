#!/usr/bin/env python3
"""Code RED Short Update Seat Unlocker

Focused WSC tool for the current Code RED pass:
- decode RSC85 type-2 WSC scripts using rdr.exe AES key
- zstd-decompress the script payload
- scan for ENABLE_VEHICLE_SEAT native hash windows
- preview/patch only literal zero arguments near those native calls

The intended first target is short_update_thread.wsc, especially the mounted-gun
truck lane around MaximShootTruck / gattling_attach. This does not touch
population WSCs, vehicle ID pools, or mission replacement ranges.
"""
from __future__ import annotations

import argparse, csv, hashlib, json, os, re, shutil, struct, subprocess, sys, tempfile
from pathlib import Path
from typing import Any

AES_KEY_HASH = bytes.fromhex("87862497EE46855372B51C7A324A2BB5CD66F4AF")
AES_KEY_OFFSETS = [0x22A2300, 0x2293500]
TOOL = "Code RED Short Update Seat Unlocker"
VERSION = "2.0"

TARGET_DEFAULT_STRINGS = ["MaximShootTruck", "GatlingShootTruck", "gattling_attach", "stagegat_attach"]
NATIVE_DEFAULT = "ENABLE_VEHICLE_SEAT"


def sha1(data: bytes) -> bytes: return hashlib.sha1(data).digest()
def sha256(data: bytes) -> str: return hashlib.sha256(data).hexdigest().upper()

def joaat(s: str) -> int:
    h=0
    for ch in s.lower().encode('utf-8','ignore'):
        h=(h+ch)&0xffffffff
        h=(h+((h<<10)&0xffffffff))&0xffffffff
        h ^= h >> 6
    h=(h+((h<<3)&0xffffffff))&0xffffffff
    h ^= h >> 11
    h=(h+((h<<15)&0xffffffff))&0xffffffff
    return h & 0xffffffff

def find_repo_root(start: Path) -> Path:
    p=start.resolve()
    for cur in [p,*p.parents]:
        if (cur/'tools').exists() or (cur/'Code_RED.bat').exists() or (cur/'main.py').exists():
            return cur
    return Path.cwd()

def likely_rdr_exe_paths(root: Path) -> list[Path]:
    paths=[]
    env=os.environ.get('CODERED_RDR_EXE')
    if env: paths.append(Path(env))
    paths += [root/'rdr.exe', root.parent/'rdr.exe', Path.cwd()/'rdr.exe', Path.cwd().parent/'rdr.exe']
    out=[]; seen=set()
    for p in paths:
        k=str(p.resolve()) if p.exists() else str(p)
        if k.lower() not in seen:
            seen.add(k.lower()); out.append(p)
    return out

def search_aes_key_in_exe(exe: Path) -> tuple[bytes|None,dict[str,Any]]:
    info={"exe":str(exe),"exists":exe.exists(),"method":None,"key_sha1":None}
    if not exe.exists(): return None,info
    data=exe.read_bytes()
    for off in AES_KEY_OFFSETS:
        if off+32<=len(data):
            k=data[off:off+32]
            if sha1(k)==AES_KEY_HASH:
                info.update({"method":f"known_offset_0x{off:X}","key_sha1":sha1(k).hex().upper()})
                return k,info
    # fallback first MiB, same as CodeX style
    limit=min(len(data)-32,1048576)
    for off in range(0,max(0,limit)+1,4):
        k=data[off:off+32]
        if sha1(k)==AES_KEY_HASH:
            info.update({"method":f"fallback_scan_0x{off:X}","key_sha1":sha1(k).hex().upper()})
            return k,info
    info['method']='not_found'
    return None,info

def get_aes_key(root: Path, explicit: str|None=None) -> tuple[bytes|None,list[dict[str,Any]]]:
    attempts=[]
    paths=[Path(explicit)] if explicit else likely_rdr_exe_paths(root)
    for p in paths:
        k,info=search_aes_key_in_exe(p)
        attempts.append(info)
        if k is not None: return k,attempts
    return None,attempts

def aes_crypt(data: bytes, key: bytes, decrypt: bool) -> bytes:
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend
    except Exception as exc:
        raise RuntimeError('Install dependency first: py -3 -m pip install cryptography') from exc
    n=len(data)&~15
    prefix=data[:n]; suffix=data[n:]
    if not prefix: return data
    cipher=Cipher(algorithms.AES(key), modes.ECB(), backend=default_backend())
    out=prefix
    for _ in range(16):
        ctx=cipher.decryptor() if decrypt else cipher.encryptor()
        out=ctx.update(out)+ctx.finalize()
    return out+suffix

def parse_rsc_header(data: bytes) -> dict[str,Any]:
    if len(data)<16:
        return {"is_rsc":False,"reason":"too_small"}
    magic=data[:4]
    if magic not in (b'RSC\x05',b'RSC\x85',b'RSC\x86'):
        return {"is_rsc":False,"magic_hex":magic.hex().upper()}
    typ=struct.unpack_from('<I',data,4)[0]
    f1s=struct.unpack_from('<i',data,8)[0]; f2s=struct.unpack_from('<i',data,12)[0]
    f1=struct.unpack_from('<I',data,8)[0]; f2=struct.unpack_from('<I',data,12)[0]
    # RSC85 extended flags: lower 14 bits of flag2 are virtual pages; next 14 are physical pages.
    virtual=(f2 & 0x3FFF)<<12
    physical=((f2>>14)&0x3FFF)<<12
    if magic==b'RSC\x05':
        virtual=(f1 & 0x7FF)<<(((f1>>11)&0xF)+8)
        physical=((f1>>15)&0x7FF)<<(((f1>>26)&0xF)+8)
    return {"is_rsc":True,"magic":"RSC"+f"{magic[3]:02X}","resource_type":typ,"flag1_signed":f1s,"flag2_signed":f2s,"flag1_hex":f"0x{f1:08X}","flag2_hex":f"0x{f2:08X}","header_size":16,"payload_size":len(data)-16,"virtual_size":virtual,"physical_size":physical,"expected_unpacked_size":virtual+physical}

def zstd_cli() -> str|None: return shutil.which('zstd') or shutil.which('zstd.exe')

def zstd_decompress(data: bytes, expected: int|None=None) -> bytes:
    try:
        import zstandard as zstd # type: ignore
        dctx=zstd.ZstdDecompressor()
        try:
            return dctx.decompress(data, max_output_size=expected or 0)
        except Exception:
            with dctx.stream_reader(data) as reader:
                return reader.read()
    except Exception as py_exc:
        exe=zstd_cli()
        if exe:
            with tempfile.TemporaryDirectory(prefix='codered_seat_zstd_') as td:
                inp=Path(td)/'in.zst'; out=Path(td)/'out.bin'; inp.write_bytes(data)
                proc=subprocess.run([exe,'-d','-f','-q',str(inp),'-o',str(out)],capture_output=True,text=True)
                if proc.returncode==0 and out.exists(): return out.read_bytes()
                raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or 'zstd.exe decompression failed')
        raise RuntimeError('zstandard support unavailable or failed: '+str(py_exc))

def zstd_compress(data: bytes, level:int=22, **kwargs) -> bytes:
    try:
        import zstandard as zstd # type: ignore
        opts={"level":level,"write_checksum":False,"write_dict_id":False}
        opts.update(kwargs)
        return zstd.ZstdCompressor(**opts).compress(data)
    except Exception as py_exc:
        exe=zstd_cli()
        if exe and not kwargs:
            with tempfile.TemporaryDirectory(prefix='codered_seat_zstd_') as td:
                inp=Path(td)/'in.bin'; out=Path(td)/'out.zst'; inp.write_bytes(data)
                proc=subprocess.run([exe,'-f','-q',f'-{level}',str(inp),'-o',str(out)],capture_output=True,text=True)
                if proc.returncode==0 and out.exists(): return out.read_bytes()
                raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or 'zstd.exe compression failed')
        raise RuntimeError('zstandard support unavailable or failed: '+str(py_exc))

def zstd_candidates(data: bytes) -> list[tuple[str,bytes]]:
    out=[]; seen=set()
    variants=[('default',{}),('no-content-size',{'write_content_size':False}),('content-size',{'write_content_size':True}),('no-content-size-no-dict',{'write_content_size':False,'write_dict_id':False})]
    for level in range(1,23):
        for label,kw in variants:
            try: b=zstd_compress(data,level,**kw)
            except Exception: continue
            h=sha256(b)
            if h in seen: continue
            seen.add(h); out.append((f'zstd-level-{level}-{label}',b))
    out.sort(key=lambda x:(len(x[1]),x[0]))
    return out

def zstd_skippable_padding(size:int)->bytes:
    if size==0: return b''
    if size<8: raise ValueError('zstd skippable padding needs at least 8 bytes')
    return struct.pack('<II',0x184D2A50,size-8)+(b'\x00'*(size-8))

def decode_wsc(path: Path, root: Path, rdr_exe: str|None=None) -> tuple[bytes,bytes,bytes,dict[str,Any]]:
    raw=path.read_bytes()
    rsc=parse_rsc_header(raw)
    rep={"input":str(path),"input_size":len(raw),"input_sha256":sha256(raw),"rsc":rsc}
    if not rsc.get('is_rsc'): raise RuntimeError('Input is not an RSC resource')
    if rsc.get('resource_type')!=2: raise RuntimeError('Input is not RSC resource_type 2 script data')
    key,attempts=get_aes_key(root,rdr_exe); rep['aes_key_attempts']=attempts
    if key is None:
        rep['status']='blocked-no-aes-key'; raise RuntimeError(json.dumps(rep,indent=2))
    encrypted=raw[16:]
    decrypted=aes_crypt(encrypted,key,True)
    expected=int(rsc.get('expected_unpacked_size') or 0) or None
    decoded=zstd_decompress(decrypted,expected)
    rep['decode']={"encrypted_payload_size":len(encrypted),"decrypted_payload_sha256":sha256(decrypted),"codec":"zstd","decoded_size":len(decoded),"decoded_sha256":sha256(decoded)}
    return raw,decoded,key,rep

def repack_wsc(raw: bytes, patched: bytes, key: bytes) -> tuple[bytes|None,dict[str,Any]]:
    rsc=parse_rsc_header(raw); original=int(rsc['payload_size'])
    attempts=[]; report={"original_payload_size":original,"attempts":attempts}
    chosen=None; payload=None
    for label,comp in zstd_candidates(patched):
        delta=len(comp)-original
        if len(attempts)<80: attempts.append({"codec":label,"size":len(comp),"delta":delta})
        if len(comp)==original:
            chosen=(label,'exact',0); payload=comp; break
        if len(comp)<original:
            pad=original-len(comp)
            if pad>=8:
                chosen=(label,'zstd-skippable-padding',pad); payload=comp+zstd_skippable_padding(pad); break
    if payload is None:
        smallest=min((len(c) for _,c in zstd_candidates(patched)), default=None)
        report.update({"fit_mode":"blocked-no-fit","smallest_candidate_size":smallest,"smallest_over_by":None if smallest is None else smallest-original})
        return None,report
    encrypted=aes_crypt(payload,key,False)
    out=raw[:16]+encrypted
    report.update({"chosen_codec":chosen[0],"fit_mode":chosen[1],"pad":chosen[2],"compressed_or_padded_size":len(payload),"output_size":len(out),"output_sha256":sha256(out)})
    try:
        dec=aes_crypt(out[16:],key,True)
        val=zstd_decompress(dec,int(rsc.get('expected_unpacked_size') or 0) or None)
        report['validate_ok']=(val==patched); report['validate_decoded_size']=len(val); report['validate_error']=None
    except Exception as exc:
        report['validate_ok']=False; report['validate_error']=str(exc)
    return out,report

def find_all(data: bytes, pat: bytes) -> list[int]:
    hits=[]; start=0
    while True:
        i=data.find(pat,start)
        if i<0: break
        hits.append(i); start=i+1
    return hits

def extract_ascii(data: bytes, off: int, radius:int=48)->str:
    a=max(0,off-radius); b=min(len(data),off+radius)
    chunk=data[a:b]
    return ''.join(chr(c) if 32<=c<=126 else '.' for c in chunk)

def hex_context(data: bytes, off:int, width:int=4, radius:int=32)->str:
    a=max(0,off-radius); b=min(len(data),off+width+radius)
    return data[a:b].hex(' ').upper()

def native_hash_patterns(name: str) -> list[tuple[str,bytes]]:
    h=joaat(name)
    return [(f'{name}:u32le:0x{h:08X}',struct.pack('<I',h)),(f'{name}:u32be:0x{h:08X}',struct.pack('>I',h))]

def string_hits(data: bytes, strings: list[str]) -> list[dict[str,Any]]:
    rows=[]
    low=data.lower()
    for s in strings:
        bs=s.encode('ascii','ignore').lower()
        for i in find_all(low,bs):
            rows.append({"string":s,"offset":i,"offset_hex":f"0x{i:X}","context_ascii":extract_ascii(data,i,48)})
    return rows

def scan_candidates(decoded: bytes, *, native: str, near_strings:list[str], near_radius:int, window:int, placement:str) -> tuple[list[dict[str,Any]],list[dict[str,Any]],list[dict[str,Any]]]:
    strings=string_hits(decoded,near_strings)
    string_offsets=[int(r['offset']) for r in strings]
    hash_rows=[]; cand_rows=[]
    literal=b'\x41\x00\x00'  # common WSC literal prefix observed in Code RED script constants.
    for label,pat in native_hash_patterns(native):
        for h in find_all(decoded,pat):
            near=[]
            for srow in strings:
                so=int(srow['offset'])
                if abs(so-h)<=near_radius:
                    near.append(f"{srow['string']}@0x{so:X}")
            include=bool(near) if near_strings else True
            hash_rows.append({"native":native,"hash_pattern":label,"offset":h,"offset_hex":f"0x{h:X}","near_target_strings":";".join(near),"included":include,"context_hex":hex_context(decoded,h,4,48),"context_ascii":extract_ascii(decoded,h,64)})
            if not include: continue
            a=max(0,h-window); b=min(len(decoded),h+window)
            zeros=[z for z in find_all(decoded[a:b],literal)]
            zeros=[a+z for z in zeros]
            # Rank likely argument literal candidates: bytecode usually pushes args before a native call, so last literal before hash is a useful first test.
            if placement=='before':
                zeros=[z for z in zeros if z<h]
                ranked=sorted(zeros,key=lambda z: h-z)
            elif placement=='after':
                zeros=[z for z in zeros if z>h]
                ranked=sorted(zeros,key=lambda z: z-h)
            else:
                ranked=sorted(zeros,key=lambda z: abs(z-h))
            for rank,z in enumerate(ranked,1):
                cand_rows.append({"native_offset_hex":f"0x{h:X}","patch_offset":z+1, "patch_offset_hex":f"0x{z+1:X}","literal_start_hex":f"0x{z:X}","rank_for_native":rank,"distance_from_native":z-h,"old_bytes":"41 00 00","new_bytes":"41 00 01","near_target_strings":";".join(near),"context_hex":hex_context(decoded,z,3,48),"context_ascii":extract_ascii(decoded,z,64)})
    # de-dupe by patch offset, keep best rank/distance
    best={}
    for r in cand_rows:
        k=int(r['patch_offset'])
        cur=best.get(k)
        if cur is None or abs(int(r['distance_from_native']))<abs(int(cur['distance_from_native'])):
            best[k]=r
    cand=list(best.values())
    cand.sort(key=lambda r:(abs(int(r['distance_from_native'])), int(str(r['patch_offset']))))
    return strings,hash_rows,cand

def write_csv(path: Path, rows:list[dict[str,Any]], fieldnames:list[str]|None=None):
    path.parent.mkdir(parents=True,exist_ok=True)
    if fieldnames is None:
        keys=[]
        for r in rows:
            for k in r.keys():
                if k not in keys: keys.append(k)
        fieldnames=keys or ['empty']
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fieldnames,extrasaction='ignore')
        w.writeheader(); w.writerows(rows)

def command_status(args):
    root=find_repo_root(Path.cwd())
    key,attempts=get_aes_key(root,args.rdr_exe)
    print(json.dumps({"tool":TOOL,"version":VERSION,"cwd":str(Path.cwd()),"repo_root_guess":str(root),"aes_key_available":key is not None,"aes_key_attempts":attempts,"native_hashes":{NATIVE_DEFAULT:f"0x{joaat(NATIVE_DEFAULT):08X}"},"notes":["First target: short_update_thread.wsc only.","v1 only looked for 41 00 00 near the raw ENABLE_VEHICLE_SEAT hash. In this WSC the hash may be a native table entry, not the real call site.","Use literal-map to produce a safer review report before exact-offset patching.","patch-exact only changes offsets you explicitly pass from a reviewed CSV.","Do not use this on population WSCs."]},indent=2))
    return 0

def command_scan(args):
    root=find_repo_root(Path.cwd())
    p=Path(args.input)
    out=Path(args.out)
    raw,decoded,key,rep=decode_wsc(p,root,args.rdr_exe)
    strings,hashes,cands=scan_candidates(decoded,native=args.native,near_strings=args.near_string,near_radius=args.near_radius,window=args.window,placement=args.placement)
    out.mkdir(parents=True,exist_ok=True)
    (out/f"{p.name}.decoded_payload.bin").write_bytes(decoded)
    write_csv(out/f"{p.name}.target_strings.csv",strings)
    write_csv(out/f"{p.name}.native_hash_windows.csv",hashes)
    write_csv(out/f"{p.name}.seat_zero_literal_candidates.csv",cands)
    rep.update({"status":"scanned","native":args.native,"near_strings":args.near_string,"near_radius":args.near_radius,"window":args.window,"placement":args.placement,"target_string_hits":len(strings),"native_hash_hits":len(hashes),"zero_literal_candidates":len(cands),"outputs":{"decoded_payload":str(out/f'{p.name}.decoded_payload.bin'),"target_strings_csv":str(out/f'{p.name}.target_strings.csv'),"native_hash_windows_csv":str(out/f'{p.name}.native_hash_windows.csv'),"seat_zero_literal_candidates_csv":str(out/f'{p.name}.seat_zero_literal_candidates.csv')}})
    (out/f"{p.name}.scan_report.json").write_text(json.dumps(rep,indent=2),encoding='utf-8')
    print(json.dumps(rep,indent=2))
    return 0

def command_patch(args):
    root=find_repo_root(Path.cwd())
    p=Path(args.input); outp=Path(args.out)
    raw,decoded,key,rep=decode_wsc(p,root,args.rdr_exe)
    strings,hashes,cands=scan_candidates(decoded,native=args.native,near_strings=args.near_string,near_radius=args.near_radius,window=args.window,placement=args.placement)
    selected=cands[:args.max_replacements]
    if args.exact_offsets:
        offset_set=set()
        for t in args.exact_offsets:
            t=t.strip()
            offset_set.add(int(t,16) if t.lower().startswith('0x') else int(t))
        selected=[r for r in cands if int(r['patch_offset']) in offset_set]
    preview_dir=outp.parent
    preview_dir.mkdir(parents=True,exist_ok=True)
    write_csv(outp.with_suffix(outp.suffix+'.candidate_offsets.csv'),cands)
    write_csv(outp.with_suffix(outp.suffix+'.selected_offsets.csv'),selected)
    rep.update({"mode":"patch-seat-disable-literals","native":args.native,"near_strings":args.near_string,"near_radius":args.near_radius,"window":args.window,"placement":args.placement,"candidate_replacements":len(cands),"selected_replacements":len(selected),"preview_csv":str(outp.with_suffix(outp.suffix+'.selected_offsets.csv'))})
    if len(cands)==0:
        rep.update({"status":"blocked-no-candidates","reason":"No 41 00 00 literal-zero candidates found in the chosen native/string windows."})
        print(json.dumps(rep,indent=2)); return 2
    if len(selected)==0:
        rep.update({"status":"blocked-no-selected-candidates"})
        print(json.dumps(rep,indent=2)); return 2
    if len(selected)>args.max_replacements and not args.exact_offsets:
        rep.update({"status":"blocked-too-many-selected","max_replacements":args.max_replacements})
        print(json.dumps(rep,indent=2)); return 2
    if args.preview_only:
        rep.update({"status":"preview-only"})
        print(json.dumps(rep,indent=2)); return 0
    patched=bytearray(decoded)
    repl_rows=[]
    for r in selected:
        off=int(r['patch_offset'])
        # literal is 41 00 00, patch last byte only at literal_start+2 = patch_offset+1? Stored patch_offset is z+1, so validate full range.
        lit_start=int(r['literal_start_hex'],16)
        if bytes(patched[lit_start:lit_start+3])!=b'\x41\x00\x00':
            rep.update({"status":"blocked-validation-mismatch","bad_offset":f"0x{lit_start:X}","found":bytes(patched[lit_start:lit_start+3]).hex(' ').upper()})
            print(json.dumps(rep,indent=2)); return 2
        patched[lit_start+2]=1
        rr=dict(r); rr['actual_patch_byte_offset_hex']=f"0x{lit_start+2:X}"; repl_rows.append(rr)
    patched=bytes(patched)
    out_raw,fit=repack_wsc(raw,patched,key)
    rep['fit_report']=fit
    rep['replacements']=len(repl_rows)
    write_csv(outp.with_suffix(outp.suffix+'.replacements.csv'),repl_rows)
    if out_raw is None or not fit.get('validate_ok'):
        rep.update({"status":"blocked-repack-validation-failed"})
        print(json.dumps(rep,indent=2)); return 2
    outp.parent.mkdir(parents=True,exist_ok=True)
    outp.write_bytes(out_raw)
    rep.update({"status":"patched","output":str(outp),"output_size":len(out_raw),"output_sha256":sha256(out_raw),"replacements_csv":str(outp.with_suffix(outp.suffix+'.replacements.csv'))})
    print(json.dumps(rep,indent=2))
    return 0


def literal_patterns() -> list[tuple[str, bytes, bytes, str]]:
    """Candidate encodings for a false/0 constant and their true/1 replacements.

    WSC bytecode constants are not fully documented in this tool. These patterns
    are used for review mapping only. patch-exact requires explicit offsets.
    """
    return [
        ("literal_i16be_41_0000", bytes.fromhex("410000"), bytes.fromhex("410001"), "wide literal seen in earlier Code RED probes"),
        ("literal_i16le_41_0000", bytes.fromhex("410000"), bytes.fromhex("410100"), "alternate wide literal interpretation"),
        ("literal_u8_40_00", bytes.fromhex("4000"), bytes.fromhex("4001"), "possible short literal"),
        ("literal_u8_2c_00", bytes.fromhex("2c00"), bytes.fromhex("2c01"), "possible short literal"),
        ("literal_u8_2d_00", bytes.fromhex("2d00"), bytes.fromhex("2d01"), "possible short literal"),
    ]

def command_literal_map(args):
    root=find_repo_root(Path.cwd())
    p=Path(args.input); out=Path(args.out)
    raw,decoded,key,rep=decode_wsc(p,root,args.rdr_exe)
    strings=string_hits(decoded,args.near_string)
    hash_rows=[]
    for label,pat in native_hash_patterns(args.native):
        for h in find_all(decoded,pat):
            near=[]
            for srow in strings:
                so=int(srow['offset'])
                if abs(so-h)<=args.near_radius:
                    near.append(f"{srow['string']}@0x{so:X}")
            hash_rows.append({"native":args.native,"hash_pattern":label,"offset":h,"offset_hex":f"0x{h:X}","near_target_strings":";".join(near),"context_hex":hex_context(decoded,h,4,args.context_radius),"context_ascii":extract_ascii(decoded,h,args.context_radius)})
    rows=[]
    anchors=[]
    for srow in strings:
        anchors.append((f"string:{srow['string']}", int(srow['offset'])))
    for hrow in hash_rows:
        anchors.append((f"native:{hrow['hash_pattern']}", int(hrow['offset'])))
    seen=set()
    for anchor_label,anchor_off in anchors:
        a=max(0,anchor_off-args.radius); b=min(len(decoded),anchor_off+args.radius)
        region=decoded[a:b]
        for pname,oldb,newb,note in literal_patterns():
            for rel in find_all(region,oldb):
                off=a+rel
                k=(off,pname)
                if k in seen: continue
                seen.add(k)
                rows.append({
                    "anchor":anchor_label,
                    "anchor_offset_hex":f"0x{anchor_off:X}",
                    "pattern":pname,
                    "note":note,
                    "literal_offset":off,
                    "literal_offset_hex":f"0x{off:X}",
                    "old_hex":oldb.hex(' ').upper(),
                    "new_hex":newb.hex(' ').upper(),
                    "distance_from_anchor":off-anchor_off,
                    "context_hex":hex_context(decoded,off,len(oldb),args.context_radius),
                    "context_ascii":extract_ascii(decoded,off,args.context_radius),
                })
    rows.sort(key=lambda r:(str(r['anchor']), abs(int(r['distance_from_anchor'])), int(r['literal_offset'])))
    out.mkdir(parents=True,exist_ok=True)
    (out/f"{p.name}.decoded_payload.bin").write_bytes(decoded)
    write_csv(out/f"{p.name}.target_strings.csv",strings)
    write_csv(out/f"{p.name}.native_hash_windows.csv",hash_rows)
    write_csv(out/f"{p.name}.literal_map.csv",rows)
    rep.update({"status":"literal-map-complete","native":args.native,"target_string_hits":len(strings),"native_hash_hits":len(hash_rows),"literal_candidates":len(rows),"radius":args.radius,"outputs":{"decoded_payload":str(out/f'{p.name}.decoded_payload.bin'),"target_strings_csv":str(out/f'{p.name}.target_strings.csv'),"native_hash_windows_csv":str(out/f'{p.name}.native_hash_windows.csv'),"literal_map_csv":str(out/f'{p.name}.literal_map.csv')}})
    (out/f"{p.name}.literal_map_report.json").write_text(json.dumps(rep,indent=2),encoding='utf-8')
    print(json.dumps(rep,indent=2))
    return 0

def parse_hex_bytes(s: str) -> bytes:
    s=s.strip().replace('0x','').replace(' ','').replace('-','')
    if len(s)%2: raise ValueError(f'hex byte string has odd length: {s}')
    return bytes.fromhex(s)

def command_patch_exact(args):
    root=find_repo_root(Path.cwd())
    p=Path(args.input); outp=Path(args.out)
    raw,decoded,key,rep=decode_wsc(p,root,args.rdr_exe)
    if not args.edit or len(args.edit)==0:
        rep.update({"status":"blocked-no-edits","reason":"Pass one or more --edit OFFSET:OLDHEX:NEWHEX entries from a reviewed literal_map CSV."})
        print(json.dumps(rep,indent=2)); return 2
    patched=bytearray(decoded); rows=[]
    for item in args.edit:
        parts=item.split(':')
        if len(parts)!=3:
            rep.update({"status":"blocked-bad-edit","edit":item,"expected":"OFFSET:OLDHEX:NEWHEX"})
            print(json.dumps(rep,indent=2)); return 2
        off_s,old_s,new_s=parts
        off=int(off_s,16) if off_s.lower().startswith('0x') else int(off_s)
        oldb=parse_hex_bytes(old_s); newb=parse_hex_bytes(new_s)
        found=bytes(patched[off:off+len(oldb)])
        if found!=oldb:
            rep.update({"status":"blocked-validation-mismatch","edit":item,"offset_hex":f"0x{off:X}","expected_old_hex":oldb.hex(' ').upper(),"found_hex":found.hex(' ').upper()})
            print(json.dumps(rep,indent=2)); return 2
        if len(oldb)!=len(newb):
            rep.update({"status":"blocked-size-change","edit":item,"reason":"old/new byte lengths must match"})
            print(json.dumps(rep,indent=2)); return 2
        patched[off:off+len(oldb)]=newb
        rows.append({"offset_hex":f"0x{off:X}","old_hex":oldb.hex(' ').upper(),"new_hex":newb.hex(' ').upper(),"context_before_hex":hex_context(decoded,off,len(oldb),32),"context_after_hex":hex_context(bytes(patched),off,len(newb),32)})
    if args.preview_only:
        preview=outp.with_suffix(outp.suffix+'.preview_edits.csv')
        write_csv(preview,rows)
        rep.update({"status":"preview-only","edits":len(rows),"preview_csv":str(preview)})
        print(json.dumps(rep,indent=2)); return 0
    out_raw,fit=repack_wsc(raw,bytes(patched),key)
    rep['fit_report']=fit
    repl_csv=outp.with_suffix(outp.suffix+'.exact_edits.csv')
    write_csv(repl_csv,rows)
    if out_raw is None or not fit.get('validate_ok'):
        rep.update({"status":"blocked-repack-validation-failed","edits_csv":str(repl_csv)})
        print(json.dumps(rep,indent=2)); return 2
    outp.parent.mkdir(parents=True,exist_ok=True)
    outp.write_bytes(out_raw)
    rep.update({"status":"patched-exact","output":str(outp),"output_size":len(out_raw),"output_sha256":sha256(out_raw),"edits":len(rows),"edits_csv":str(repl_csv)})
    print(json.dumps(rep,indent=2))
    return 0


def main(argv=None):
    ap=argparse.ArgumentParser(description=TOOL)
    ap.add_argument('--rdr-exe',default=None)
    sub=ap.add_subparsers(dest='cmd',required=True)
    st=sub.add_parser('status')
    sc=sub.add_parser('scan')
    sc.add_argument('--input',required=True)
    sc.add_argument('--out',default='logs/short_update_seat_unlock/scan')
    sc.add_argument('--native',default=NATIVE_DEFAULT)
    sc.add_argument('--near-string',action='append',default=None,help='target string that must be near the native hash; repeatable')
    sc.add_argument('--near-radius',type=int,default=16384)
    sc.add_argument('--window',type=int,default=96)
    sc.add_argument('--placement',choices=['before','after','either'],default='before')
    pa=sub.add_parser('patch')
    pa.add_argument('--input',required=True)
    pa.add_argument('--out',required=True)
    pa.add_argument('--native',default=NATIVE_DEFAULT)
    pa.add_argument('--near-string',action='append',default=None)
    pa.add_argument('--near-radius',type=int,default=16384)
    pa.add_argument('--window',type=int,default=96)
    pa.add_argument('--placement',choices=['before','after','either'],default='before')
    pa.add_argument('--max-replacements',type=int,default=6)
    pa.add_argument('--exact-offsets',nargs='*',help='optional exact patch_offset values from the scan CSV')
    pa.add_argument('--preview-only',action='store_true')
    lm=sub.add_parser('literal-map')
    lm.add_argument('--input',required=True)
    lm.add_argument('--out',default='logs/short_update_seat_unlock/literal_map')
    lm.add_argument('--native',default=NATIVE_DEFAULT)
    lm.add_argument('--near-string',action='append',default=None)
    lm.add_argument('--near-radius',type=int,default=16384)
    lm.add_argument('--radius',type=int,default=8192,help='bytes around each target string/native hash to map candidate literals')
    lm.add_argument('--context-radius',type=int,default=48)
    pe=sub.add_parser('patch-exact')
    pe.add_argument('--input',required=True)
    pe.add_argument('--out',required=True)
    pe.add_argument('--edit',action='append',default=[],help='OFFSET:OLDHEX:NEWHEX, e.g. 0x1234:410000:410001; repeatable')
    pe.add_argument('--preview-only',action='store_true')
    args=ap.parse_args(argv)
    if getattr(args,'near_string',None) is None:
        args.near_string=list(TARGET_DEFAULT_STRINGS)
    if args.cmd=='status': return command_status(args)
    if args.cmd=='scan': return command_scan(args)
    if args.cmd=='patch': return command_patch(args)
    if args.cmd=='literal-map': return command_literal_map(args)
    if args.cmd=='patch-exact': return command_patch_exact(args)
    return 1

if __name__=='__main__':
    raise SystemExit(main())
