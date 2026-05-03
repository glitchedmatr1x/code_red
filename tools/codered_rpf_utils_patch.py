from __future__ import annotations
from pathlib import Path
import struct, zlib, subprocess, hashlib
from collections import Counter
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

RPF6_AES_KEY = bytes([0xB7,0x62,0xDF,0xB6,0xE2,0xB2,0xC6,0xDE,0xAF,0x72,0x2A,0x32,0xD2,0xFB,0x6F,0x0C,0x98,0xA3,0x21,0x74,0x62,0xC9,0xC4,0xED,0xAD,0xAA,0x2E,0xD0,0xDD,0xF9,0x2F,0x10])

def rdr_name_hash(name: str) -> int:
    num2=0
    for ch in name.lower():
        num3=(num2+ord(ch))&0xffffffff
        num4=(num3+((num3<<10)&0xffffffff))&0xffffffff
        num2=(num4^(num4>>6))&0xffffffff
    num5=(num2+((num2<<3)&0xffffffff))&0xffffffff
    num6=(num5^(num5>>11))&0xffffffff
    return (num6+((num6<<15)&0xffffffff))&0xffffffff

def _crypt_blocks(data: bytes, decrypt: bool) -> bytes:
    if not data: return data
    block_len=len(data)&~0xf
    if block_len <= 0: return data
    cipher=Cipher(algorithms.AES(RPF6_AES_KEY), modes.ECB(), backend=default_backend())
    block=data[:block_len]
    for _ in range(16):
        ctx = cipher.decryptor() if decrypt else cipher.encryptor()
        block = ctx.update(block)+ctx.finalize()
    return block+data[block_len:]

def decrypt(data: bytes)->bytes: return _crypt_blocks(data, True)
def encrypt(data: bytes)->bytes: return _crypt_blocks(data, False)
def flag_res(f1): return (f1&0x80000000)!=0
def flag_ext(f2): return (f2&0x80000000)!=0
def flag_comp(f1,f2): return (not flag_ext(f2)) and ((f1>>30)&1)==1
def ent_offset(c,res): return ((c&0x7FFFFF00) if res else (c&0x7FFFFFFF))*8
def rtype(c): return c&0xff

def total_size(f1,f2):
    if not flag_res(f1): return f1&0xBFFFFFFF
    if flag_ext(f2): return ((f2&0x3fff)<<12)+(((f2>>14)&0x3fff)<<12)
    vpage0=(f1>>4)&0x7f; vpage1=(f1>>3)&1; vpage2=(f1>>2)&1; vpage3=(f1>>1)&1; vpage4=f1&1; vsize=(f1>>11)&0xf
    ppage0=(f1>>19)&0x7f; ppage1=(f1>>18)&1; ppage2=(f1>>17)&1; ppage3=(f1>>16)&1; ppage4=(f1>>15)&1; psize=(f1>>26)&0xf
    return ((vpage0+vpage1+vpage2+vpage3+vpage4)<<(vsize+8))+((ppage0+ppage1+ppage2+ppage3+ppage4)<<(psize+8))

def parse(path: Path|str, with_debug: bool=False):
    path=Path(path); data=path.read_bytes()
    if len(data)<16 or data[:4]!=b'RPF6': raise ValueError('not RPF6')
    _, entry_count, debug_offset, enc_flag = struct.unpack('>4I', data[:16])
    toc_size=((entry_count*20)+15)&~15
    toc=data[16:16+toc_size]
    if enc_flag: toc=decrypt(toc)
    entries=[]
    for i in range(entry_count):
        a,b,c,d,e=struct.unpack('>5I', toc[i*20:(i+1)*20])
        is_dir=((c>>24)&0xff)==0x80
        ent={'index':i,'name_off':a,'debug_name':None,'toc_words':(a,b,c,d,e)}
        if is_dir:
            ent.update(type='dir', flags=b, start=c&0x7fffffff, count=d&0x0fffffff, unk=e)
        else:
            res=flag_res(d)
            ent.update(type='file', size_in_archive=b&0x0fffffff, offset_raw=c, flag1=d, flag2=e, is_resource=res, is_compressed=flag_comp(d,e), resource_type=rtype(c) if res else None, offset=ent_offset(c,res), total_size=total_size(d,e))
        entries.append(ent)
    if with_debug and debug_offset > 0 and debug_offset*8 < len(data):
        dbg=decrypt(data[debug_offset*8:])
        names=dbg[entry_count*8:]
        byhash={}
        for ent in entries:
            byhash.setdefault(ent['name_off'], []).append(ent)
        for raw in names.decode('latin-1','ignore').split('\x00'):
            raw=raw.strip()
            if not raw: continue
            h=rdr_name_hash(raw)
            for ent in byhash.get(h, []):
                if not ent.get('debug_name'):
                    ent['debug_name']=raw
                    break
    def resolve(e):
        if e['type']=='dir' and e['name_off']==0: return 'root'
        return e.get('debug_name') or f"0x{e['name_off']:08X}"
    parents=[None]*len(entries)
    for ent in entries:
        if ent['type']=='dir':
            for ci in range(ent['start'], ent['start']+ent['count']):
                if 0<=ci<len(entries): parents[ci]=ent['index']
    extc=Counter(); resolved=0
    for ent in entries:
        ent['name']=resolve(ent)
        ent['parent_index']=parents[ent['index']]
        if not ent['name'].startswith('0x') or ent['name']=='root': resolved+=1
        parts=[ent['name']]
        p=parents[ent['index']]
        seen=set()
        while p is not None and p not in seen and 0<=p<len(entries):
            seen.add(p); parts.append(resolve(entries[p])); p=parents[p]
        ent['path']='/'.join(reversed(parts))
        ent['extension']=('.'+ent['name'].lower().rsplit('.',1)[-1]) if ent['type']=='file' and '.' in ent['name'] else ''
        if ent['extension']: extc[ent['extension']]+=1
    return {'path':str(path),'data':data,'entry_count':entry_count,'toc_size':toc_size,'debug_offset':debug_offset,'enc_flag':enc_flag,'entries':entries,'ext_counts':extc,'resolved_count':resolved,'file_count':sum(1 for e in entries if e['type']=='file'),'dir_count':sum(1 for e in entries if e['type']=='dir')}

def find_entry(info, internal_path: str):
    internal_path=internal_path.lower().replace('\\','/')
    for e in info['entries']:
        if e.get('type')=='file' and e.get('path','').lower()==internal_path:
            return e
    return None

def read_slot(archive: Path|str, ent: dict)->bytes:
    with Path(archive).open('rb') as f:
        f.seek(ent['offset']); return f.read(ent['size_in_archive'])

def extract(archive: Path|str, ent: dict)->bytes:
    raw=read_slot(archive, ent)
    if ent.get('is_resource'): return raw
    if ent.get('is_compressed'):
        if raw.startswith(b'\x28\xB5\x2F\xFD'):
            p=subprocess.run(['zstd','-d','-q','--single-thread','--stdout'],input=raw,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
            return p.stdout
        for wb in (-15,15,31):
            try: return zlib.decompress(raw,wb)
            except Exception: pass
        raise ValueError('decompress failed')
    return raw

# --- Patch support added for Pass7 builder ---
def compress_like(original_slot: bytes, payload: bytes):
    if original_slot.startswith(b'\x28\xB5\x2F\xFD'):
        levels = [18, 9, 3] if len(payload) < 50000 else [9, 3]
        first_raw=None; first_label=None
        for level in levels:
            cmd=['zstd','-q','-z',f'-{level}','--no-check','--single-thread','--stdout']
            p=subprocess.run(cmd,input=payload,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=120)
            raw=p.stdout
            q=subprocess.run(['zstd','-d','-q','--single-thread','--stdout'],input=raw,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=120)
            if q.stdout!=payload: continue
            if first_raw is None:
                first_raw=raw; first_label=f'zstd-{level}'
            if len(raw) <= len(original_slot):
                return raw, f'zstd-{level}'
        if first_raw is not None: return first_raw, first_label
        raise RuntimeError('zstd recompress failed')
    for wb in (-15,15,31):
        try: zlib.decompress(original_slot,wb)
        except Exception: continue
        raw = zlib.compress(payload,9) if wb==15 else (lambda co: co.compress(payload)+co.flush())(zlib.compressobj(level=9,wbits=wb))
        if zlib.decompress(raw,wb)==payload: return raw, f'zlib-w{wb}-l9'
    raise ValueError('no compression path')

def extract_from_coded(coded: bytes, ent: dict):
    if ent.get('is_compressed'):
        if coded.startswith(b'\x28\xB5\x2F\xFD'):
            p=subprocess.run(['zstd','-d','-q','--single-thread','--stdout'],input=coded,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
            return p.stdout
        for wb in (-15,15,31):
            try: return zlib.decompress(coded,wb)
            except Exception: pass
        raise ValueError('decompress coded failed')
    return coded

def update_metadata(archive_copy_path: Path|str, info: dict, ent: dict, new_size_in_archive=None, new_total_size=None, new_offset=None):
    archive_copy_path=Path(archive_copy_path)
    data=bytearray(archive_copy_path.read_bytes())
    toc=bytes(data[16:16+info['toc_size']])
    if info.get('enc_flag'): toc=decrypt(toc)
    buf=bytearray(toc)
    off=ent['index']*20
    a,b,c,d,e=struct.unpack('>5I', bytes(buf[off:off+20]))
    if new_size_in_archive is not None:
        b=(b&0xF0000000)|(int(new_size_in_archive)&0x0FFFFFFF)
    if new_total_size is not None and not ent.get('is_resource'):
        d=(d&0xC0000000)|(int(new_total_size)&0x3FFFFFFF)
    if new_offset is not None:
        if new_offset%8: raise ValueError('unaligned offset')
        if ent.get('is_resource'):
            c=((new_offset//8)&0x7FFFFF00)|(rtype(c)&0xff)
        else:
            c=(new_offset//8)&0x7fffffff
    buf[off:off+20]=struct.pack('>5I',a,b,c,d,e)
    out=encrypt(bytes(buf)) if info.get('enc_flag') else bytes(buf)
    data[16:16+info['toc_size']]=out
    archive_copy_path.write_bytes(data)

def append_payload(archive_copy_path: Path|str, payload: bytes)->int:
    archive_copy_path=Path(archive_copy_path)
    cur=archive_copy_path.stat().st_size
    aligned=(cur+7)&~7
    with archive_copy_path.open('ab') as f:
        if aligned>cur: f.write(b'\x00'*(aligned-cur))
        f.write(payload)
    return aligned

def patch_entry(archive_copy_path: Path|str, internal_path: str, payload: bytes):
    import hashlib
    archive_copy_path=Path(archive_copy_path)
    info=parse(archive_copy_path, with_debug=True)
    ent=find_entry(info, internal_path)
    if not ent: raise KeyError(internal_path)
    slot=read_slot(archive_copy_path, ent)
    original=extract(archive_copy_path, ent)
    if ent.get('is_resource'): raise NotImplementedError('resource entries unsupported')
    if ent.get('is_compressed'):
        coded, codec=compress_like(slot,payload)
        if extract_from_coded(coded, ent)!=payload: raise AssertionError('verify failed')
    else:
        coded, codec=payload, 'plain'
    relocated=len(coded)>ent['size_in_archive']
    if relocated:
        new_off=append_payload(archive_copy_path,coded)
        update_metadata(archive_copy_path, info, ent, new_size_in_archive=len(coded), new_total_size=len(payload), new_offset=new_off)
    else:
        with archive_copy_path.open('r+b') as f:
            f.seek(ent['offset']); f.write(coded)
            if len(coded)<ent['size_in_archive']: f.write(b'\x00'*(ent['size_in_archive']-len(coded)))
        update_metadata(archive_copy_path, info, ent, new_size_in_archive=len(coded), new_total_size=len(payload))
    info2=parse(archive_copy_path, with_debug=True)
    ent2=find_entry(info2,internal_path)
    out=extract(archive_copy_path, ent2)
    if out!=payload: raise AssertionError('re-read mismatch')
    return {'path':internal_path,'original_payload_size':len(original),'new_payload_size':len(payload),'original_slot_size':len(slot),'new_slot_size':len(coded),'relocated':relocated,'codec':codec,'old_offset':ent['offset'],'new_offset':ent2['offset'],'sha1':hashlib.sha1(payload).hexdigest()}
