from pathlib import Path
print("script top", flush=True)
import struct, zlib, shutil, json, hashlib, subprocess
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
print("imports done", flush=True)
KEY=bytes([0xB7,0x62,0xDF,0xB6,0xE2,0xB2,0xC6,0xDE,0xAF,0x72,0x2A,0x32,0xD2,0xFB,0x6F,0x0C,0x98,0xA3,0x21,0x74,0x62,0xC9,0xC4,0xED,0xAD,0xAA,0x2E,0xD0,0xDD,0xF9,0x2F,0x10])
def h(name):
    n=0
    for ch in name.lower():
        a=(n+ord(ch))&0xffffffff; b=(a+((a<<10)&0xffffffff))&0xffffffff; n=(b^(b>>6))&0xffffffff
    a=(n+((n<<3)&0xffffffff))&0xffffffff; b=(a^(a>>11))&0xffffffff
    return (b+((b<<15)&0xffffffff))&0xffffffff
def crypt(data, enc):
    bl=len(data)&~0xf
    cipher=Cipher(algorithms.AES(KEY), modes.ECB(), backend=default_backend())
    block=data[:bl]
    for _ in range(16):
        ctx=cipher.encryptor() if enc else cipher.decryptor(); block=ctx.update(block)+ctx.finalize()
    return block+data[bl:]
def is_res(f1): return (f1&0x80000000)!=0
def is_ext(f2): return (f2&0x80000000)!=0
def is_comp(f1,f2): return (not is_ext(f2)) and ((f1>>30)&1)==1
def offset(c,res): return ((c&0x7fffff00) if res else (c&0x7fffffff))*8
def total(f1,f2): return f1&0xBfffffff if not is_res(f1) else 0
def read_toc(path):
    data=path.read_bytes(); magic,count,debug,encflag=struct.unpack('>4I', data[:16]); assert magic==0x52504636
    size=((count*20)+15)&~15; toc=data[16:16+size];
    if encflag: toc=crypt(toc, False)
    entries=[]
    for i in range(count):
        a,b,c,d,e=struct.unpack('>5I', toc[i*20:(i+1)*20]); isdir=((c>>24)&0xff)==0x80
        entries.append({'index':i,'a':a,'b':b,'c':c,'d':d,'e':e,'type':'dir' if isdir else 'file','size':b&0x0fffffff,'offset': offset(c,is_res(d)) if not isdir else None,'compressed':is_comp(d,e) if not isdir else False,'resource':is_res(d) if not isdir else False,'total':total(d,e) if not isdir else None})
    return {'count':count,'encflag':encflag,'toc_size':size,'entries':entries}
def get_entry(info, filename):
    hh=h(filename); hits=[e for e in info['entries'] if e['type']=='file' and e['a']==hh]
    if len(hits)!=1: raise ValueError(f'{filename} hits={len(hits)} {[x["index"] for x in hits]}')
    return hits[0]
def extract(path, ent):
    raw=path.read_bytes()[ent['offset']:ent['offset']+ent['size']]
    if ent['resource']: return raw
    if ent['compressed']:
        if raw.startswith(b'\x28\xB5\x2F\xFD'):
            return subprocess.run(['zstd','-d','-q','--stdout'], input=raw, capture_output=True, check=True, timeout=10).stdout
        for wb in (-15,15,31):
            try: return zlib.decompress(raw,wb)
            except Exception: pass
        raise ValueError('decompress failed')
    return raw
def compress_like(old_raw, payload):
    if old_raw.startswith(b'\x28\xB5\x2F\xFD'):
        out=subprocess.run(['zstd','-12','-q','--stdout'], input=payload, capture_output=True, check=True, timeout=10).stdout
        chk=subprocess.run(['zstd','-d','-q','--stdout'], input=out, capture_output=True, check=True, timeout=10).stdout
        assert chk==payload
        return out,'zstd-12'
    for wb in (-15,15,31):
        try: zlib.decompress(old_raw, wb); mode=wb; break
        except Exception: pass
    else: raise ValueError('codec unknown')
    c=zlib.compressobj(level=9,wbits=mode); out=c.compress(payload)+c.flush(); assert zlib.decompress(out,mode)==payload
    return out,f'zlib {mode}'
def update(path, info, ent, new_size, new_total, new_offset):
    data=bytearray(path.read_bytes()); toc=data[16:16+info['toc_size']]
    if info['encflag']: toc=crypt(bytes(toc),False)
    toc=bytearray(toc); off=ent['index']*20; a,b,c,d,e=struct.unpack('>5I',toc[off:off+20])
    b=(b&0xf0000000)|(new_size&0x0fffffff); d=(d&0xc0000000)|(new_total&0x3fffffff)
    if new_offset is not None: c=(new_offset//8)&0x7fffffff
    toc[off:off+20]=struct.pack('>5I',a,b,c,d,e)
    data[16:16+info['toc_size']]=crypt(bytes(toc),True) if info['encflag'] else bytes(toc)
    path.write_bytes(data)
def patch_one(out, filename, source):
    info=read_toc(out); ent=get_entry(info, filename)
    old_raw=out.read_bytes()[ent['offset']:ent['offset']+ent['size']]; old=extract(out, ent); new=source.read_bytes()
    coded,codec=compress_like(old_raw,new) if ent['compressed'] else (new,'plain')
    new_offset=None
    if len(coded)<=ent['size']:
        with out.open('r+b') as f: f.seek(ent['offset']); f.write(coded); f.write(b'\0'*(ent['size']-len(coded)))
    else:
        cur=out.stat().st_size; aligned=(cur+7)&~7
        with out.open('ab') as f:
            if aligned>cur: f.write(b'\0'*(aligned-cur))
            f.write(coded)
        new_offset=aligned
    update(out, info, ent, len(coded), len(new), new_offset)
    info2=read_toc(out); ent2=get_entry(info2, filename); ok=extract(out, ent2)==new
    return {'file':filename,'index':ent['index'],'old_payload':len(old),'new_payload':len(new),'old_coded':ent['size'],'new_coded':len(coded),'codec':codec,'relocated':new_offset is not None,'new_offset':new_offset,'verified':ok,'sha1':hashlib.sha1(new).hexdigest()}
if __name__=='__main__':
    source=Path('/mnt/data/content.rpf'); out=Path('/mnt/data/codered_ui_patch_work/output/content_codered_ui_settings_proof.rpf')
    out.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source,out)
    root=Path('/mnt/data/codered_ui_patch_work/patch_root')
    plan=[('networking.sc.xml', root/'root/content/ui/pausemenu/networking.sc.xml'),('offlinemenu.sc.xml', root/'root/content/ui/pausemenu/0x007B97C6/offlinemenu.sc.xml')]
    results=[]
    for fn,src in plan:
        print('patch',fn,flush=True); r=patch_one(out,fn,src); print(r,flush=True); results.append(r)
    report=out.with_name(out.stem+'_patch_report.json'); report.write_text(json.dumps(results,indent=2),encoding='utf-8')
    print('wrote',out,out.stat().st_size,report)
