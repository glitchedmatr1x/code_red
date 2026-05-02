#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, hashlib, json, math, re, shutil, struct, subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path

RPF6_AES_KEY=bytes([0xB7,0x62,0xDF,0xB6,0xE2,0xB2,0xC6,0xDE,0xAF,0x72,0x2A,0x32,0xD2,0xFB,0x6F,0x0C,0x98,0xA3,0x21,0x74,0x62,0xC9,0xC4,0xED,0xAD,0xAA,0x2E,0xD0,0xDD,0xF9,0x2F,0x10])
VBASE=0x50000000; SAG_SECTORINFO_VFT=0x01909C38

def rdr_hash(name:str)->int:
    h=0
    for ch in name.lower():
        a=(h+ord(ch))&0xffffffff; b=(a+((a<<10)&0xffffffff))&0xffffffff; h=(b^(b>>6))&0xffffffff
    a=(h+((h<<3)&0xffffffff))&0xffffffff; b=(a^(a>>11))&0xffffffff
    return (b+((b<<15)&0xffffffff))&0xffffffff

def sha1(b:bytes)->str: return hashlib.sha1(b).hexdigest()

def aes_blocks(data:bytes,decrypt=True)->bytes:
    n=len(data)&~0xf
    if n<=0: return data
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes
        from cryptography.hazmat.backends import default_backend
        c=Cipher(algorithms.AES(RPF6_AES_KEY),modes.ECB(),backend=default_backend())
        blk=data[:n]
        for _ in range(16):
            ctx=c.decryptor() if decrypt else c.encryptor(); blk=ctx.update(blk)+ctx.finalize()
        return blk+data[n:]
    except Exception:
        if not shutil.which('openssl'): raise RuntimeError('Encrypted RPF needs cryptography or openssl')
        blk=data[:n]; mode='-d' if decrypt else '-e'; key=RPF6_AES_KEY.hex()
        for _ in range(16):
            p=subprocess.run(['openssl','enc','-aes-256-ecb',mode,'-K',key,'-nopad','-nosalt'],input=blk,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
            blk=p.stdout
        return blk+data[n:]

def is_res(f1): return (f1&0x80000000)!=0
def is_ext(f2): return (f2&0x80000000)!=0
def is_comp(f1,f2): return (not is_ext(f2)) and ((f1>>30)&1)==1
def rtype(c): return c&0xff
def ent_off(c,res): return ((c&0x7fffff00) if res else (c&0x7fffffff))*8
def total_size(f1,f2):
    if not is_res(f1): return f1&0xbfffffff
    if is_ext(f2): return ((f2&0x3fff)<<12)+(((f2>>14)&0x3fff)<<12)
    vp=((f1>>4)&0x7f)+((f1>>3)&1)+((f1>>2)&1)+((f1>>1)&1)+(f1&1); vs=(f1>>11)&0xf
    pp=((f1>>19)&0x7f)+((f1>>18)&1)+((f1>>17)&1)+((f1>>16)&1)+((f1>>15)&1); ps=(f1>>26)&0xf
    return (vp<<(vs+8))+(pp<<(ps+8))

@dataclass
class Entry:
    index:int; name_hash:int; name:str; path:str; parent_index:int|None; type:str; start:int=0; count:int=0; size:int=0; offset_raw:int=0; offset:int=0; flag1:int=0; flag2:int=0; resource:bool=False; compressed:bool=False; resource_type:int|None=None; total:int=0; ext:str=''

class RPF6:
    def __init__(self,path,debug=True):
        self.path=Path(path); self.data=self.path.read_bytes()
        if self.data[:4]!=b'RPF6': raise ValueError('not RPF6')
        _,self.count,self.debug_word,self.enc=struct.unpack('>4I',self.data[:16]); self.toc_size=((self.count*20)+15)&~15
        toc=self.data[16:16+self.toc_size]; self.toc=aes_blocks(toc,True) if self.enc else toc
        self.entries=self._entries(debug); self.exts=Counter(e.ext for e in self.entries if e.ext)
    def _debug_names(self):
        off=self.debug_word*8
        if off<=0 or off>=len(self.data): return {}
        try: blob=aes_blocks(self.data[off:],True)[self.count*8:]
        except Exception: return {}
        out=defaultdict(list)
        for s in blob.decode('latin-1','ignore').split('\0'):
            s=s.strip()
            if s: out[rdr_hash(s)].append(s)
        return out
    def _entries(self,debug):
        raw=[]; names=self._debug_names() if debug else {}
        for i in range(self.count):
            a,b,c,d,e=struct.unpack('>5I',self.toc[i*20:(i+1)*20]); idir=((c>>24)&0xff)==0x80
            if idir: raw.append(dict(i=i,h=a,t='dir',start=c&0x7fffffff,count=d&0x0fffffff))
            else:
                res=is_res(d); raw.append(dict(i=i,h=a,t='file',size=b&0x0fffffff,oraw=c,off=ent_off(c,res),f1=d,f2=e,res=res,comp=is_comp(d,e),rt=rtype(c) if res else None,total=total_size(d,e)))
        parents=[None]*len(raw)
        for x in raw:
            if x['t']=='dir':
                for ci in range(x['start'],x['start']+x['count']):
                    if 0<=ci<len(raw): parents[ci]=x['i']
        def nm(x):
            if x['t']=='dir' and x['h']==0: return 'root'
            vals=names.get(x['h']); return vals.pop(0) if vals else f"0x{x['h']:08X}"
        for x in raw: x['name']=nm(x); x['par']=parents[x['i']]
        out=[]
        for x in raw:
            parts=[x['name']]; p=x['par']; seen=set()
            while p is not None and p not in seen and 0<=p<len(raw): seen.add(p); parts.append(raw[p]['name']); p=raw[p]['par']
            path='/'.join(reversed(parts)); ext='.'+x['name'].lower().rsplit('.',1)[-1] if x['t']=='file' and '.' in x['name'] else ''
            out.append(Entry(x['i'],x['h'],x['name'],path,x['par'],x['t'],x.get('start',0),x.get('count',0),x.get('size',0),x.get('oraw',0),x.get('off',0),x.get('f1',0),x.get('f2',0),x.get('res',False),x.get('comp',False),x.get('rt'),x.get('total',0),ext))
        return out
    def files(self,ext=None): return [e for e in self.entries if e.type=='file' and (ext is None or e.ext==ext.lower())]
    def find(self,path):
        want=path.replace('\\','/').lower()
        return next((e for e in self.entries if e.type=='file' and e.path.lower()==want),None)
    def slot(self,e): return self.data[e.offset:e.offset+e.size]
    def summary(self): return dict(archive=str(self.path),entry_count=self.count,file_count=sum(e.type=='file' for e in self.entries),dir_count=sum(e.type=='dir' for e in self.entries),encrypted_toc=bool(self.enc),debug_offset_word=self.debug_word,extensions=dict(sorted(self.exts.items())))

def zstd_dec(b):
    try:
        import zstandard as zstd; return zstd.ZstdDecompressor().decompress(b)
    except Exception: pass
    if not shutil.which('zstd'): raise RuntimeError('need zstandard package or zstd CLI')
    return subprocess.run(['zstd','-d','-q','--single-thread','--stdout'],input=b,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True).stdout

def zstd_enc(b,level=9):
    try:
        import zstandard as zstd; return zstd.ZstdCompressor(level=level,write_checksum=False).compress(b)
    except Exception: pass
    if not shutil.which('zstd'): raise RuntimeError('need zstandard package or zstd CLI')
    return subprocess.run(['zstd','-q','-z',f'-{level}','--no-check','--single-thread','--stdout'],input=b,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True).stdout

def rsc_decode(raw):
    if not raw.startswith(b'RSC') or len(raw)<12: raise ValueError('not RSC')
    return raw[:12], zstd_dec(raw[12:])
def rsc_encode(header,payload,level=9): return header+zstd_enc(payload,level)

def load_names(paths):
    out=[]
    for p in map(Path,paths or []):
        if p.is_dir():
            for q in p.rglob('*'):
                if q.is_file() and q.suffix.lower() in ('.txt','.hashes','.csv'): out+=load_names([q])
        elif p.exists():
            for line in p.read_text('utf-8','ignore').splitlines():
                s=line.strip()
                if not s or s.startswith('#'): continue
                if ',' in s: s=s.split(',',1)[0].strip()
                if '=' in s: s=s.split('=',1)[0].strip()
                if s: out.append(s.replace('\\','/'))
    return out

def hash_map(rpf,extra=()):
    names=set(extra)
    for e in rpf.entries:
        if e.name and not e.name.startswith('0x'):
            names.add(e.name); names.add(e.name.rsplit('.',1)[0])
        base=e.path.rsplit('/',1)[-1]
        if base and not base.startswith('0x'):
            names.add(base); names.add(base.rsplit('.',1)[0])
    return {rdr_hash(n):n for n in names if n}

def strings(payload,limit=500):
    cnt=0; sample=[]
    for m in re.finditer(rb'[\x20-\x7E]{4,}',payload):
        cnt+=1
        if len(sample)<limit: sample.append(dict(offset=m.start(),text=m.group(0).decode('latin-1','replace')))
    return cnt,sample

def ptrs(payload,limit=1000):
    cnt=0; sample=[]; n=len(payload)
    for off in range(0,max(0,n-4),4):
        v=struct.unpack_from('<I',payload,off)[0]
        if VBASE<=v<VBASE+n:
            cnt+=1
            if len(sample)<limit: sample.append(dict(offset=off,value=f'0x{v:08X}',target_offset=v-VBASE))
    return cnt,sample

def hits(payload,hmap,limit=2000):
    cnt=0; sample=[]
    for off in range(0,max(0,len(payload)-4),4):
        v=struct.unpack_from('<I',payload,off)[0]; name=hmap.get(v)
        if name:
            cnt+=1
            if len(sample)<limit: sample.append(dict(offset=off,hash=f'0x{v:08X}',name=name))
    return cnt,sample

def sector_vfts(payload):
    out=[]; sig=struct.pack('<I',SAG_SECTORINFO_VFT); st=0
    while True:
        off=payload.find(sig,st)
        if off<0: break
        row=dict(offset=off,vft=f'0x{SAG_SECTORINFO_VFT:08X}')
        if off+0xd0<=len(payload):
            for lab,rel in [('candidate_bound_min',0xb0),('candidate_bound_max',0xc0)]:
                row[lab]=[round(x,6) for x in struct.unpack_from('<4f',payload,off+rel)]
        out.append(row); st=off+4
    return out

def vecs(payload,limit=5000):
    out=[]
    for off in range(0,max(0,len(payload)-12),4):
        x,y,z=struct.unpack_from('<3f',payload,off)
        if all(math.isfinite(v) and -100000<=v<=100000 and abs(v)>1e-8 for v in (x,y,z)) and max(abs(x),abs(y),abs(z))>=1:
            out.append(dict(offset=off,x=x,y=y,z=z))
            if len(out)>=limit: break
    return out

def scan_payload(payload,hmap):
    sc,ss=strings(payload); pc,ps=ptrs(payload); hc,hs=hits(payload,hmap); vv=vecs(payload)
    return dict(decoded_size=len(payload),sha1=sha1(payload),strings_count=sc,strings_sample=ss,virtual_pointers_count=pc,virtual_pointers_sample=ps,hash_hits_count=hc,hash_hits_sample=hs,sectorinfo_vft_hits=sector_vfts(payload),vec3_candidates_sample=vv)

def write_csv(path,rows,fields):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    with open(path,'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fields); w.writeheader(); w.writerows(rows)

def cmd_inventory(a):
    r=RPF6(a.archive,not a.no_debug); files=[dict(index=e.index,path=e.path,extension=e.ext,size_in_archive=e.size,offset=e.offset,is_resource=e.resource,resource_type=e.resource_type,total_size=e.total) for e in r.entries if e.type=='file']
    out=r.summary(); out['files']=files; Path(a.out).parent.mkdir(parents=True,exist_ok=True); Path(a.out).write_text(json.dumps(out,indent=2),encoding='utf-8'); print('Wrote',a.out)

def cmd_scan(a):
    r=RPF6(a.archive,not a.no_debug); h=hash_map(r,load_names(a.names)); outdir=Path(a.outdir); outdir.mkdir(parents=True,exist_ok=True); master=dict(archive=r.summary(),wsi=[])
    entries=[r.find(a.path)] if a.path else r.files('.wsi')
    for e in entries:
        if not e: raise KeyError(a.path)
        header,payload=rsc_decode(r.slot(e)); sc=scan_payload(payload,h); safe=e.path.replace('/','__').replace('\\','__'); base=outdir/safe
        base.with_suffix('.decoded.bin').write_bytes(payload); base.with_suffix('.scan.json').write_text(json.dumps(dict(entry=asdict(e),rsc_header_hex=header.hex(),scan=sc),indent=2),encoding='utf-8')
        write_csv(base.with_suffix('.hash_hits.csv'),sc['hash_hits_sample'],['offset','hash','name']); write_csv(base.with_suffix('.vec3_candidates.csv'),sc['vec3_candidates_sample'],['offset','x','y','z'])
        master['wsi'].append(dict(path=e.path,resource_type=e.resource_type,slot_size=len(r.slot(e)),decoded_size=len(payload),sha1=sha1(payload),strings_count=sc['strings_count'],hash_hits_count=sc['hash_hits_count'],virtual_pointers_count=sc['virtual_pointers_count'],sectorinfo_vft_hits=sc['sectorinfo_vft_hits']))
        print('Scanned',e.path,'decoded',len(payload),'hash hits',sc['hash_hits_count'])
    (outdir/'wsi_scan_master.json').write_text(json.dumps(master,indent=2),encoding='utf-8'); print('Wrote',outdir)

def patch_toc(data,r,e,new_size,new_off):
    if new_off%2048: raise ValueError('RSC replacement must be 2048-byte aligned')
    toc=bytearray(r.toc); off=e.index*20; a,b,c,d,f=struct.unpack('>5I',toc[off:off+20])
    b=(b&0xf0000000)|(new_size&0x0fffffff); c=((new_off//8)&0x7fffff00)|(e.resource_type or rtype(c)); toc[off:off+20]=struct.pack('>5I',a,b,c,d,f)
    data[16:16+r.toc_size]=aes_blocks(bytes(toc),False) if r.enc else bytes(toc)

def cmd_patch(a):
    src=Path(a.archive); dst=Path(a.out)
    if src.resolve()==dst.resolve(): raise ValueError('refusing in-place patch')
    shutil.copy2(src,dst); r=RPF6(dst,not a.no_debug); e=r.find(a.path)
    if not e or e.ext!='.wsi' or not e.resource: raise ValueError('path must be a .wsi resource')
    head,payload=rsc_decode(r.slot(e)); buf=bytearray(payload); off=int(a.offset,0); repl=bytes.fromhex(a.hex.replace(' ','')); old=bytes(buf[off:off+len(repl)])
    if off<0 or off+len(repl)>len(buf): raise ValueError('patch outside decoded payload')
    buf[off:off+len(repl)]=repl; newres=rsc_encode(head,bytes(buf),a.zstd_level); assert rsc_decode(newres)[1]==bytes(buf)
    data=bytearray(dst.read_bytes()); newoff=(len(data)+2047)&~2047; data.extend(b'\0'*(newoff-len(data))); data.extend(newres); patch_toc(data,r,e,len(newres),newoff); dst.write_bytes(data)
    r2=RPF6(dst,not a.no_debug); e2=r2.find(a.path); assert rsc_decode(r2.slot(e2))[1]==bytes(buf)
    proof=dict(source=str(src),patched=str(dst),entry=a.path,decoded_offset=off,old_hex=old.hex(),new_hex=repl.hex(),decoded_size=len(buf),old_resource_size=len(r.slot(e)),new_resource_size=len(newres),new_rpf_offset=newoff,verified_after_reopen=True,decoded_sha1=sha1(bytes(buf)))
    p=Path(a.proof) if a.proof else dst.with_suffix(dst.suffix+'.patch_proof.json'); p.write_text(json.dumps(proof,indent=2),encoding='utf-8'); print('Patched copy:',dst); print('Proof:',p)

def main():
    p=argparse.ArgumentParser(description='Code RED WSI/RSC6 explorer')
    sub=p.add_subparsers(dest='cmd',required=True)
    q=sub.add_parser('inventory'); q.add_argument('archive'); q.add_argument('--out',default='exports/wsi_inventory.json'); q.add_argument('--no-debug',action='store_true'); q.set_defaults(fn=cmd_inventory)
    q=sub.add_parser('scan-wsi'); q.add_argument('archive'); q.add_argument('--path'); q.add_argument('--names',nargs='*',default=[]); q.add_argument('--outdir',default='exports/wsi_scan'); q.add_argument('--no-debug',action='store_true'); q.set_defaults(fn=cmd_scan)
    q=sub.add_parser('patch-wsi-bytes'); q.add_argument('archive'); q.add_argument('path'); q.add_argument('--offset',required=True); q.add_argument('--hex',required=True); q.add_argument('--out',required=True); q.add_argument('--proof'); q.add_argument('--zstd-level',type=int,default=9); q.add_argument('--no-debug',action='store_true'); q.set_defaults(fn=cmd_patch)
    a=p.parse_args(); a.fn(a)
if __name__=='__main__': main()
