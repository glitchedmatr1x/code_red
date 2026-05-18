#!/usr/bin/env python3
"""Code RED Content RPF Deep Scanner

Read-only scanner for RDR1 RPF6 archives. It was built for Code RED's current
vehicle/mounted-gun research pass: WSC scripts, gringos, train seats, car/truck
IDs, gatling/maxim strings, and seat-control clues.

It does NOT patch anything.
"""
from __future__ import annotations

import argparse, csv, hashlib, json, os, re, shutil, struct, sys, tempfile, zlib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
except Exception:
    Cipher = algorithms = modes = default_backend = None  # type: ignore

try:
    import zstandard as zstd  # type: ignore
except Exception:
    zstd = None  # type: ignore

TOOL = "Code RED Content RPF Deep Scanner"
VERSION = "1.0"
AES_KEY_SHA1 = bytes.fromhex("87862497EE46855372B51C7A324A2BB5CD66F4AF")
AES_KEY_OFFSETS = [0x22A2300, 0x2293500]

VEHICLE_ACTOR_NAMES = {
    1156:"TrainCar01",1157:"TrainCar02",1158:"TrainCar03",1159:"TrainCar04",1160:"TrainCar05",1161:"TrainCar06",1162:"TrainCar07",1163:"TrainCar08",1164:"TrainCar09",1165:"TrainEngine01",1166:"TrainCarFlat01",1167:"TrainCarFlat02",1168:"TrainEngine02",1169:"TrainCarNorth01",1170:"TrainCarNorth02",1171:"TrainCarNorth03",1172:"TrainCarNorth04",1173:"TrainCarNorth05",1174:"TrainCarNorth06",1175:"NorthTrainA",1176:"NorthTrainB",
    1177:"Buggy01",1178:"Buggy02",1179:"Buggy03",1180:"Buggy04",1181:"Buggy05",1182:"Buggy06",
    1183:"Cart01",1184:"Cart02",1185:"Cart003",1186:"Cart004",1187:"Cart005",1188:"Cart006",
    1189:"Stagecoach01",1190:"Stagecoach02",1191:"Stagecoach03",1192:"Stagecoach04",
    1193:"Truck01",1194:"Car01",1195:"Wagon04",1196:"Wagon05",1197:"WagonPrison01",1198:"WagonGatling01",1199:"Wagon02",1200:"Chuckwagon",1201:"Chuckwagon02",1202:"Coach01",
}

TARGET_STRINGS = [
    "Truck01","truck01","Car01","car01","WagonGatling01","WagonPrison01","Wagon05","Wagon02","Chuckwagon","Coach01",
    "GatlingShoot","GatlingShootTruck","GatlingShootWagon","GatlingShootCoach",
    "MaximShoot","MaximShootTruck","MaximShootWagon",
    "gattling_attach","gatling_attach","stagegat_attach","stagecoachgatling","stagecoachgatling01x",
    "ENABLE_VEHICLE_SEAT","SET_VEHICLE_ALLOWED_TO_DRIVE","ENABLE_VEHICLE_SEAT","SET_ACTOR_IN_VEHICLE",
    "SET_ACTOR_AUTO_TRANSITION_TO_DRIVER_SEAT","START_VEHICLE","SET_VEHICLE_ENGINE_RUNNING",
    "_TRAIN_ADD_NEW_TRAIN_CAR_FROM_ENUM","TRAIN_GET_NUM_CARS","nTrainName","FrontierTrain","NorthTrain",
    "VehicleList","GET_ACTORENUM_FROM_STRING","CREATE_ACTOR_IN_LAYOUT","CREATE_GRINGO_ON_OBJECT",
    "_GRINGO_SET_IS_USABLE_BY_PLAYER","GRINGO_SET_AVAILABILITY_EXT","SNAP_ACTOR_TO_GRINGO",
    "carSettings","SET_VEHICLE_EJECTION_ENABLED","bIgnoreStuckState",
    "climbontowagon","vehicle_generator","short_update_thread","long_update_thread","playercar",
    "beat_crime_wagonthief","wagonthief","beat_roadside_robbery","event_roadside_ambush","event_roadside_prisoners",
]

NAME_SEEDS = set(TARGET_STRINGS) | {
    "root","content","release","release64","scripting","designerdefined","gringo","itemscripts","multiplayer","regions","frontier",
    "blackwater","mexico","northernelizabeth","rio_bravo","gaptooth_ridge","benedict_point","rathskeller_fork",
    "main.csc","short_update_thread.wsc","long_update_thread.wsc","medium_update_thread.csc","playercar.wsc","vehicle_generator.wsc","climbontowagon.wsc",
    "commongringos.wgd","zombiepackmpgringos.wgd","placementglobals.xml",
}

ASCII_RE = re.compile(rb"[\x20-\x7e]{4,}")
UTF16LE_RE = re.compile(rb"(?:[\x20-\x7e]\x00){4,}")

# RPF extension IDs are stored in low byte of resource offset. This map is partial but useful.
RPF_EXT_BY_TYPE = {
    2:".wsc/.csc script", 5:"resource5", 6:"resource6", 10:".wtd/.wtx texture", 11:".wft fragment", 12:".wfd drawable", 13:".wgd gringo", 14:".wsi sector", 15:".wcg cover", 16:".wsg grass", 17:".wsp speedtree", 18:".wtb bounds", 19:".wat actiontree", 20:".wcdt clip", 21:".wedt expression", 22:".wpfl particle", 23:".wnm navmesh", 24:".wsf scaleform", 25:".wbd boundsdict", 26:".was animset",
}


def sha1(b: bytes) -> bytes: return hashlib.sha1(b).digest()
def sha1hex(b: bytes) -> str: return hashlib.sha1(b).hexdigest().upper()
def sha256hex(b: bytes) -> str: return hashlib.sha256(b).hexdigest().upper()

def u32be(b: bytes, off: int=0) -> int: return struct.unpack_from(">I", b, off)[0]
def i32be(b: bytes, off: int=0) -> int: return struct.unpack_from(">i", b, off)[0]
def u32le(b: bytes, off: int=0) -> int: return struct.unpack_from("<I", b, off)[0]
def i32le(b: bytes, off: int=0) -> int: return struct.unpack_from("<i", b, off)[0]

def joaat(s: str) -> int:
    # Jenkins one-at-a-time, the hash family CodeX calls JenkHash.
    h = 0
    for ch in s.lower().encode("utf-8", "ignore"):
        h = (h + ch) & 0xFFFFFFFF
        h = (h + ((h << 10) & 0xFFFFFFFF)) & 0xFFFFFFFF
        h ^= (h >> 6)
    h = (h + ((h << 3) & 0xFFFFFFFF)) & 0xFFFFFFFF
    h ^= (h >> 11)
    h = (h + ((h << 15) & 0xFFFFFFFF)) & 0xFFFFFFFF
    return h & 0xFFFFFFFF

def aes_16_rounds(data: bytes, key: bytes, decrypt: bool=True) -> bytes:
    if Cipher is None:
        raise RuntimeError("Python package 'cryptography' is required. Run install deps first.")
    buf = bytearray(data)
    n = len(buf) & ~15
    if n <= 0: return bytes(buf)
    cipher = Cipher(algorithms.AES(key), modes.ECB(), backend=default_backend())
    for _ in range(16):
        ctx = cipher.decryptor() if decrypt else cipher.encryptor()
        buf[:n] = ctx.update(bytes(buf[:n])) + ctx.finalize()
    return bytes(buf)

def find_aes_key(rdr_exe: Path|None=None) -> tuple[bytes|None, list[dict[str,Any]]]:
    attempts=[]
    candidates=[]
    env=os.environ.get("CODERED_RDR_EXE")
    if rdr_exe: candidates.append(Path(rdr_exe))
    if env: candidates.append(Path(env))
    cwd=Path.cwd()
    candidates += [cwd/"rdr.exe", cwd.parent/"rdr.exe"]
    seen=set()
    for exe in candidates:
        exe=exe.resolve()
        if str(exe).lower() in seen: continue
        seen.add(str(exe).lower())
        rec={"exe":str(exe),"exists":exe.exists(),"method":None,"key_sha1":None}
        if not exe.exists():
            attempts.append(rec); continue
        data=exe.read_bytes()
        for off in AES_KEY_OFFSETS:
            if off+32<=len(data):
                k=data[off:off+32]
                if sha1(k)==AES_KEY_SHA1:
                    rec["method"]=f"known_offset_0x{off:X}"; rec["key_sha1"]=sha1hex(k); attempts.append(rec); return k, attempts
        # Fallback rolling search by expected SHA1. Slow but okay once.
        for off in range(0, max(0,len(data)-32), 4):
            k=data[off:off+32]
            if sha1(k)==AES_KEY_SHA1:
                rec["method"]=f"linear_search_0x{off:X}"; rec["key_sha1"]=sha1hex(k); attempts.append(rec); return k, attempts
        attempts.append(rec)
    return None, attempts

@dataclass
class FlagInfo:
    flag1: int
    flag2: int
    @property
    def is_resource(self) -> bool: return bool(self.flag1 & 0x80000000)
    @property
    def is_extended(self) -> bool: return bool(self.flag2 & 0x80000000)
    @property
    def is_compressed(self) -> bool: return self.is_extended or bool((self.flag1>>30)&1)
    @property
    def rsc85_total_v(self) -> int: return (self.flag2 & 0x3FFF) << 12
    @property
    def rsc85_total_p(self) -> int: return ((self.flag2 >> 14) & 0x3FFF) << 12
    @property
    def rsc05_total_v(self) -> int: return (self.flag1 & 0x7FF) << (((self.flag1 >> 11) & 0xF)+8)
    @property
    def rsc05_total_p(self) -> int: return ((self.flag1 >> 15) & 0x7FF) << (((self.flag1 >> 26) & 0xF)+8)
    @property
    def total_size(self) -> int:
        if self.is_resource:
            if self.is_extended: return self.rsc85_total_v + self.rsc85_total_p
            return self.rsc05_total_v + self.rsc05_total_p
        return self.flag1 & 0xBFFFFFFF

@dataclass
class RpfEntry:
    index:int; name_hash:int; name:str; path:str; is_dir:bool; parent:int|None
    size:int=0; offset_raw:int=0; flag1:int=0; flag2:int=0; resource_type:int|None=None
    entries_index:int=0; entries_count:int=0; unk:int=0
    children:list[int]|None=None
    @property
    def flags(self) -> FlagInfo: return FlagInfo(self.flag1 & 0xFFFFFFFF, self.flag2 & 0xFFFFFFFF)
    def file_offset(self) -> int:
        if self.is_dir: return 0
        if self.flags.is_resource: return (self.offset_raw & 0x7FFFFF00) * 8
        return (self.offset_raw & 0x7FFFFFFF) * 8
    def file_size(self) -> int:
        if self.size: return self.size
        return self.flags.total_size


def load_name_index(extra_paths: list[Path]) -> dict[int,str]:
    names=set(NAME_SEEDS)
    for p in extra_paths:
        if not p.exists(): continue
        if p.is_file(): files=[p]
        else: files=list(p.rglob("*"))
        for f in files:
            if f.is_file() and f.suffix.lower() in {".txt",".csv",".xml",".json",".cs",".md"} and f.stat().st_size < 8_000_000:
                try:
                    txt=f.read_text(errors="ignore")
                except Exception: continue
                for m in re.finditer(r"[A-Za-z0-9_./\\$-]{3,}", txt):
                    s=m.group(0).strip().replace("/","\\")
                    if len(s) <= 128:
                        names.add(s.lower())
                        names.add(Path(s).name.lower())
                        if "." in s:
                            names.add(Path(s).stem.lower())
    d={}
    for s in names:
        d[joaat(s)] = s
    return d


def read_rpf_entries(rpf: Path, key: bytes|None, name_index: dict[int,str]) -> tuple[list[RpfEntry], dict[str,Any]]:
    data=rpf.read_bytes()
    if len(data)<16: raise RuntimeError("RPF too small")
    magic=data[:4]
    if magic!=b"RPF6": raise RuntimeError(f"Not RPF6: {magic!r}")
    entry_count=u32be(data,4)
    string_table_offset=u32be(data,8)
    enc_flag=i32be(data,12)
    toc_size=(((entry_count*5)*4)+15) & 0xFFFFFFF0
    toc=data[16:16+toc_size]
    encrypted=enc_flag!=0
    if encrypted:
        if key is None:
            raise RuntimeError("RPF TOC is encrypted and no AES key was found. Set CODERED_RDR_EXE or run beside rdr.exe.")
        toc=aes_16_rounds(toc,key,True)
    entries=[]
    for i in range(entry_count):
        off=i*20; e=toc[off:off+20]
        if len(e)<20: break
        typ=e[8]
        name_hash=u32be(e,0)
        name=name_index.get(name_hash, f"0x{name_hash:08X}")
        if typ==0x80:
            flags=u32be(e,4); entries_index=i32be(e,8)&0x7FFFFFFF; entries_count=i32be(e,12)&0x0FFFFFFF; unk=i32be(e,16)
            entries.append(RpfEntry(i,name_hash,name,name,True,None,entries_index=entries_index,entries_count=entries_count,unk=unk,children=[]))
        else:
            size=i32be(e,4)&0x0FFFFFFF; offset_raw=i32be(e,8)&0xFFFFFFFF; flag1=i32be(e,12)&0xFFFFFFFF; flag2=i32be(e,16)&0xFFFFFFFF
            res_type=offset_raw & 0xFF if (flag1 & 0x80000000) else None
            entries.append(RpfEntry(i,name_hash,name,name,False,None,size=size,offset_raw=offset_raw,flag1=flag1,flag2=flag2,resource_type=res_type))
    # Build paths from directory entry ranges.
    if entries:
        root=entries[0]; root.name="root"; root.path="root"; root.parent=None
        stack=[0]
        while stack:
            di=stack.pop(); d=entries[di]
            if not d.is_dir: continue
            d.children=[]
            for ci in range(d.entries_index, min(len(entries), d.entries_index+d.entries_count)):
                if ci==di: continue
                c=entries[ci]; c.parent=di
                c.path=d.path+"\\"+c.name
                d.children.append(ci)
                if c.is_dir: stack.append(ci)
    meta={"version":"RPF6","entry_count":entry_count,"toc_size":toc_size,"string_table_offset":string_table_offset,"enc_flag":enc_flag,"encrypted":encrypted,"file_size":len(data),"sha256":sha256hex(data)}
    return entries, meta


def rsc_info(data: bytes) -> dict[str,Any]|None:
    if len(data)<16 or data[:3]!=b"RSC": return None
    magic=data[:4]
    typ=u32le(data,4)
    flag1=i32le(data,8)&0xFFFFFFFF
    header=12; flag2=None
    if magic in (b"RSC\x85",b"RSC\x86"):
        flag2=i32le(data,12)&0xFFFFFFFF; header=16
    info={"magic":magic.decode("latin1"),"resource_type":typ,"flag1_hex":f"0x{flag1:08X}","header_size":header,"payload_size":max(0,len(data)-header)}
    if flag2 is not None:
        vs=(flag2&0x3FFF)<<12; ps=((flag2>>14)&0x3FFF)<<12
        info.update({"flag2_hex":f"0x{flag2:08X}","virtual_size":vs,"physical_size":ps,"expected_unpacked_size":vs+ps})
    else:
        vs=(flag1&0x7FF)<<(((flag1>>11)&0xF)+8); ps=((flag1>>15)&0x7FF)<<(((flag1>>26)&0xF)+8)
        info.update({"virtual_size":vs,"physical_size":ps,"expected_unpacked_size":vs+ps})
    return info


def zstd_decompress(payload: bytes, expected: int|None=None) -> bytes:
    if zstd is not None:
        dctx=zstd.ZstdDecompressor()
        try:
            return dctx.decompress(payload)
        except Exception:
            if expected:
                return dctx.decompress(payload, max_output_size=expected)
            raise
    exe=shutil.which("zstd") or shutil.which("zstd.exe")
    if exe:
        with tempfile.TemporaryDirectory(prefix="codered_zstd_") as td:
            src=Path(td)/"in.zst"; dst=Path(td)/"out.bin"; src.write_bytes(payload)
            import subprocess
            p=subprocess.run([exe,"-q","-d","-f",str(src),"-o",str(dst)],capture_output=True,text=True)
            if p.returncode!=0: raise RuntimeError(p.stderr or p.stdout or "zstd failed")
            return dst.read_bytes()
    raise RuntimeError("zstandard support unavailable. Run install_content_rpf_deep_scan_deps.bat")

def try_decompress(payload: bytes, expected: int|None=None) -> tuple[bytes|None,str,str|None]:
    if not payload: return b"","empty",None
    # Many RDR1 frames are zstd without advertised decompressed size.
    if payload.startswith(b"\x28\xb5\x2f\xfd"):
        try: return zstd_decompress(payload,expected),"zstd",None
        except Exception as e: return None,"zstd",str(e)
    # Some scripts are AES encrypted before zstd, so random-looking bytes are expected before decrypt.
    for wbits,label in [(-15,"zlib-raw"),(15,"zlib"),(31,"gzip")]:
        try: return zlib.decompress(payload,wbits),label,None
        except Exception: pass
    return None,"unknown",None

def decode_rsc(data: bytes, key: bytes|None) -> tuple[bytes|None, dict[str,Any]]:
    info=rsc_info(data)
    if not info: return None,{"is_rsc":False}
    header=info["header_size"]; payload=data[header:]
    expected=info.get("expected_unpacked_size")
    notes=[]
    decode_payload=payload
    if info.get("magic") in ("RSC\x85","RSC\x86") and info.get("resource_type")==2:
        if key is None:
            notes.append("script payload probably AES-protected; no key")
        else:
            decode_payload=aes_16_rounds(payload,key,True)
            notes.append("AES16-decrypted script payload")
    out,codec,err=try_decompress(decode_payload,expected)
    rep={"is_rsc":True, **info, "codec":codec, "decode_error":err, "decoded_size":len(out) if out is not None else 0, "notes":notes}
    return out, rep


def extract_strings(data: bytes, limit:int=5000) -> list[str]:
    out=[]
    for m in ASCII_RE.finditer(data):
        try: s=m.group(0).decode("ascii","ignore")
        except Exception: continue
        out.append(s)
        if len(out)>=limit: break
    for m in UTF16LE_RE.finditer(data):
        try: s=m.group(0).decode("utf-16le","ignore")
        except Exception: continue
        if s not in out: out.append(s)
        if len(out)>=limit: break
    return out

FORMATS = {
    "u16be":(">H",2), "u16le":("<H",2), "i16be":(">h",2), "i16le":("<h",2),
    "u32be":(">I",4), "u32le":("<I",4), "i32be":(">i",4), "i32le":("<i",4),
}

def scan_ints(data: bytes, low:int=1156, high:int=1202) -> dict[str,dict[int,int]]:
    res={}
    n=len(data)
    for fmt,(sf,sz) in FORMATS.items():
        counts={}
        for off in range(0,n-sz+1):
            try: val=struct.unpack_from(sf,data,off)[0]
            except Exception: continue
            if low <= val <= high:
                counts[val]=counts.get(val,0)+1
        if counts: res[fmt]=counts
    return res


def scan_target_hashes(data: bytes, targets: list[str]) -> list[dict[str,Any]]:
    hits=[]
    # compiled code may use hashes instead of clear strings; report only low-count clues.
    for t in targets:
        h=joaat(t)
        pats=[("u32le",struct.pack("<I",h)),("u32be",struct.pack(">I",h))]
        for fmt,pat in pats:
            count=data.count(pat)
            if count:
                hits.append({"target":t,"joaat_hex":f"0x{h:08X}","format":fmt,"count":count})
    return hits


def relevance_score(strings: list[str], int_hits: dict[str,dict[int,int]], hash_hits: list[dict[str,Any]], path: str, rsc: dict[str,Any]) -> tuple[int,list[str]]:
    score=0; reasons=[]
    p=path.lower()
    for token,pts in [("short_update",80),("long_update",70),("wagon",20),("train",25),("playercar",60),("vehicle",35),("gringo",25),("beat_crime_wagonthief",80)]:
        if token in p: score+=pts; reasons.append(f"path:{token}")
    sjoin="\n".join(strings).lower()
    for token,pts in [("maximshoottruck",120),("gatlingshoottruck",120),("gatlingshoot",80),("maximshoot",80),("gattling_attach",90),("stagegat_attach",90),("enable_vehicle_seat",100),("_train_add_new_train_car_from_enum",90),("vehiclelist",50),("carsettings",60),("set_vehicle_ejection_enabled",50)]:
        if token in sjoin:
            score+=pts; reasons.append(f"string:{token}")
    # vehicle direct constants
    for fmt,counts in int_hits.items():
        if fmt in ("u16be","u16le"):
            for val,c in counts.items():
                if val in (1193,1194): score += 60 + min(c,5)*5; reasons.append(f"{fmt}:{val}:{c}")
                elif 1177 <= val <= 1202: score += min(c,10)*4
                elif 1156 <= val <= 1176: score += min(c,10)*3
    for hh in hash_hits:
        if hh["target"].lower() in {"maximshoottruck","gatlingshoottruck","gattling_attach","enable_vehicle_seat","truck01","car01"}:
            score += 35; reasons.append(f"hash:{hh['target']}")
    if rsc.get("resource_type")==2: score += 10
    return score, reasons[:20]


def ensure_dir(p: Path): p.mkdir(parents=True, exist_ok=True)

def write_csv(path: Path, rows: list[dict[str,Any]], fieldnames: list[str]|None=None):
    ensure_dir(path.parent)
    if fieldnames is None:
        keys=[]
        for r in rows:
            for k in r.keys():
                if k not in keys: keys.append(k)
        fieldnames=keys or ["empty"]
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fieldnames,extrasaction="ignore")
        w.writeheader(); w.writerows(rows)


def scan_rpf(args):
    rpf=Path(args.rpf)
    out=Path(args.out)
    ensure_dir(out)
    key, key_attempts = find_aes_key(Path(args.rdr_exe) if args.rdr_exe else None)
    name_paths = [Path(args.name_index_dir)] if args.name_index_dir else [Path.cwd()/"CodeX.Games.RDR1-main", Path.cwd()/"CODEWALKER-FOR-RDR1-CodeX.Games.RDR1-main", Path.cwd()/"docs"]
    name_index=load_name_index(name_paths)
    report={"tool":TOOL,"version":VERSION,"rpf":str(rpf),"out":str(out),"aes_key_available":key is not None,"aes_key_attempts":key_attempts,"name_index_count":len(name_index)}
    try:
        entries, meta = read_rpf_entries(rpf,key,name_index)
        report["rpf_meta"]=meta
    except Exception as e:
        report["status"]="blocked-rpf-parse-failed"
        report["error"]=str(e)
        # raw fallback: count RSC headers and target strings in raw archive.
        data=rpf.read_bytes()
        raw_offsets=[]; pos=0
        while True:
            i=data.find(b"RSC\x85",pos)
            if i<0: break
            if i+16<=len(data):
                typ=u32le(data,i+4); f1=i32le(data,i+8)&0xffffffff; f2=i32le(data,i+12)&0xffffffff
                raw_offsets.append({"offset":i,"resource_type":typ,"flag1_hex":f"0x{f1:08X}","flag2_hex":f"0x{f2:08X}"})
            pos=i+4
        raw_strs=extract_strings(data,limit=20000)
        raw_hits=[]
        for t in TARGET_STRINGS:
            c=sum(1 for s in raw_strs if t.lower() in s.lower())
            if c: raw_hits.append({"target":t,"count":c})
        write_csv(out/"raw_rsc85_offsets.csv",raw_offsets)
        write_csv(out/"raw_string_target_hits.csv",raw_hits)
        report["raw_rsc85_count"]=len(raw_offsets); report["raw_target_hits"]=raw_hits[:50]
        (out/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
        print(json.dumps(report,indent=2))
        return 2

    data=rpf.read_bytes()
    entry_rows=[]; candidate_rows=[]; id_rows=[]; str_rows=[]; hash_rows=[]; decode_rows=[]
    export_dir=out/"candidate_payloads"
    for e in entries:
        row={"index":e.index,"path":e.path,"name":e.name,"name_hash":f"0x{e.name_hash:08X}","is_dir":e.is_dir,"parent":e.parent,"size":e.size,"offset":e.file_offset() if not e.is_dir else "","resource_type":e.resource_type,"resource_type_hint":RPF_EXT_BY_TYPE.get(e.resource_type or -1,""),"flag1_hex":f"0x{e.flag1:08X}","flag2_hex":f"0x{e.flag2:08X}"}
        entry_rows.append(row)
        if e.is_dir: continue
        off=e.file_offset(); size=e.file_size()
        if off<0 or off+size>len(data) or size<=0:
            decode_rows.append({"index":e.index,"path":e.path,"status":"bad-offset-or-size","offset":off,"size":size})
            continue
        raw=data[off:off+size]
        decoded=None; rsc={"is_rsc":False}
        if raw.startswith(b"RSC"):
            decoded,rsc=decode_rsc(raw,key)
        scan_data = decoded if decoded is not None else raw
        strings=extract_strings(scan_data,limit=8000)
        int_hits=scan_ints(scan_data,args.scan_low,args.scan_high)
        hash_hits=scan_target_hashes(scan_data,TARGET_STRINGS)
        score,reasons=relevance_score(strings,int_hits,hash_hits,e.path,rsc)
        decode_rows.append({"index":e.index,"path":e.path,"raw_size":len(raw),"rsc":rsc.get("is_rsc"),"resource_type":rsc.get("resource_type"),"codec":rsc.get("codec"),"decoded_size":rsc.get("decoded_size"),"decode_error":rsc.get("decode_error"),"score":score,"reasons":";".join(reasons)})
        for fmt,counts in int_hits.items():
            for val,c in sorted(counts.items()):
                id_rows.append({"index":e.index,"path":e.path,"format":fmt,"actor_id":val,"actor_name":VEHICLE_ACTOR_NAMES.get(val,""),"count":c})
        s_low=[s for s in strings if any(t.lower() in s.lower() for t in TARGET_STRINGS)]
        for s in s_low[:200]:
            str_rows.append({"index":e.index,"path":e.path,"string":s[:500]})
        for hh in hash_hits[:200]:
            hash_rows.append({"index":e.index,"path":e.path,**hh})
        if score>0:
            candidate_rows.append({"index":e.index,"path":e.path,"name":e.name,"size":size,"resource_type":e.resource_type,"resource_type_hint":RPF_EXT_BY_TYPE.get(e.resource_type or -1,""),"score":score,"reasons":";".join(reasons),"decoded_size":len(decoded) if decoded is not None else "","decode_error":rsc.get("decode_error")})
            if args.export_candidates and score>=args.export_min_score:
                ensure_dir(export_dir)
                safe=re.sub(r"[^A-Za-z0-9_.-]+","_",f"{e.index:04d}_{e.path}")[:180]
                (export_dir/(safe+".raw.bin")).write_bytes(raw)
                if decoded is not None:
                    (export_dir/(safe+".decoded.bin")).write_bytes(decoded)
                    (export_dir/(safe+".strings.txt")).write_text("\n".join(strings),encoding="utf-8",errors="ignore")
    candidate_rows.sort(key=lambda r:int(r["score"]), reverse=True)
    write_csv(out/"entries.csv",entry_rows)
    write_csv(out/"decode_report.csv",decode_rows)
    write_csv(out/"candidate_files.csv",candidate_rows)
    write_csv(out/"vehicle_id_hits.csv",id_rows)
    write_csv(out/"target_string_hits.csv",str_rows)
    write_csv(out/"target_hash_hits.csv",hash_rows)
    report.update({
        "status":"complete", "entries":len(entries), "files":sum(1 for e in entries if not e.is_dir),
        "candidates":len(candidate_rows), "top_candidates":candidate_rows[:30],
        "outputs": {"entries_csv":str(out/"entries.csv"),"decode_report_csv":str(out/"decode_report.csv"),"candidate_files_csv":str(out/"candidate_files.csv"),"vehicle_id_hits_csv":str(out/"vehicle_id_hits.csv"),"target_string_hits_csv":str(out/"target_string_hits.csv"),"target_hash_hits_csv":str(out/"target_hash_hits.csv")}
    })
    (out/"summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    md=[]
    md.append(f"# {TOOL} v{VERSION}\n")
    md.append(f"RPF: `{rpf}`\n")
    md.append(f"Status: **{report['status']}**\n")
    md.append(f"Entries: {report['entries']}  Files: {report['files']}  Candidates: {report['candidates']}\n")
    md.append("\n## Top candidates\n")
    for c in candidate_rows[:30]:
        md.append(f"- score {c['score']} — `{c['path']}` — {c['reasons']}\n")
    md.append("\n## Output CSVs\n")
    for k,v in report["outputs"].items(): md.append(f"- {k}: `{v}`\n")
    (out/"summary.md").write_text("".join(md),encoding="utf-8")
    print(json.dumps(report,indent=2))
    return 0


def main(argv=None):
    ap=argparse.ArgumentParser(description=TOOL)
    sub=ap.add_subparsers(dest="cmd",required=True)
    p=sub.add_parser("scan", help="deep scan an RPF6 archive")
    p.add_argument("--rpf", default="content.rpf")
    p.add_argument("--out", default="logs/content_rpf_deep_scan")
    p.add_argument("--rdr-exe", default=None, help="path to real rdr.exe; env CODERED_RDR_EXE also works")
    p.add_argument("--name-index-dir", default=None, help="optional folder containing CodeX strings/txt/csv for hash name recovery")
    p.add_argument("--scan-low", type=int, default=1156)
    p.add_argument("--scan-high", type=int, default=1202)
    p.add_argument("--export-candidates", action="store_true", help="export raw/decoded payloads for high-scoring candidates")
    p.add_argument("--export-min-score", type=int, default=120)
    args=ap.parse_args(argv)
    if args.cmd=="scan":
        raise SystemExit(scan_rpf(args))

if __name__=="__main__": main()
