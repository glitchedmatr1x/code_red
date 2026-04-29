#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import struct
import zlib
from pathlib import Path


def read_obj_vertices(path: Path, limit=50000):
    pts = []
    faces = []
    for line in Path(path).read_text(encoding='utf-8', errors='ignore').splitlines():
        if line.startswith('v '):
            parts = line.split()
            if len(parts) >= 4:
                try: pts.append((float(parts[1]), float(parts[2]), float(parts[3])))
                except Exception: pass
        elif line.startswith('f '):
            ids=[]
            for tok in line.split()[1:4]:
                try: ids.append(int(tok.split('/')[0])-1)
                except Exception: pass
            if len(ids)==3: faces.append(tuple(ids))
    if len(pts) > limit:
        step = max(1, len(pts)//limit)
        pts = pts[::step][:limit]
        faces = []
    return pts, faces


def put_px(buf, w, h, x, y, rgb):
    x = int(round(x)); y = int(round(y))
    if 0 <= x < w and 0 <= y < h:
        i = (y*w+x)*3
        buf[i:i+3] = bytes(rgb)


def line(buf,w,h,x0,y0,x1,y1,rgb):
    x0=int(round(x0)); y0=int(round(y0)); x1=int(round(x1)); y1=int(round(y1))
    dx=abs(x1-x0); sx=1 if x0<x1 else -1
    dy=-abs(y1-y0); sy=1 if y0<y1 else -1
    err=dx+dy
    while True:
        put_px(buf,w,h,x0,y0,rgb)
        if x0==x1 and y0==y1: break
        e2=2*err
        if e2>=dy: err+=dy; x0+=sx
        if e2<=dx: err+=dx; y0+=sy


def project(pts,w,h):
    if not pts: return []
    xs=[p[0] for p in pts]; ys=[p[1] for p in pts]; zs=[p[2] for p in pts]
    cx=(min(xs)+max(xs))*0.5; cy=(min(ys)+max(ys))*0.5; cz=(min(zs)+max(zs))*0.5
    span=max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs), 1e-6)
    rx=math.radians(-18); ry=math.radians(28)
    sx=math.sin(rx); cxr=math.cos(rx); sy=math.sin(ry); cyr=math.cos(ry)
    scale=min(w,h)*0.78/span
    out=[]
    for x,y,z in pts:
        x-=cx; y-=cy; z-=cz
        x2=x*cyr+z*sy; z2=-x*sy+z*cyr
        y2=y*cxr-z2*sx; z3=y*sx+z2*cxr
        out.append((w*0.5+x2*scale, h*0.53-y2*scale, z3))
    return out


def write_png(path, w, h, rgb):
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw.extend(rgb[y*w*3:(y+1)*w*3])
    def chunk(tag,data):
        return struct.pack('>I',len(data))+tag+data+struct.pack('>I', zlib.crc32(tag+data)&0xffffffff)
    png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB',w,h,8,2,0,0,0)) + chunk(b'IDAT', zlib.compress(bytes(raw),9)) + chunk(b'IEND', b'')
    Path(path).write_bytes(png)


def render(obj: Path, out: Path, w=1100, h=760):
    pts, faces = read_obj_vertices(obj)
    buf = bytearray([5,5,5])*(w*h)
    p = project(pts,w,h)
    if faces:
        rows=[]
        for a,b,c in faces[:22000]:
            if 0<=a<len(p) and 0<=b<len(p) and 0<=c<len(p): rows.append(((p[a][2]+p[b][2]+p[c][2])/3,a,b,c))
        rows.sort()
        for _,a,b,c in rows:
            line(buf,w,h,p[a][0],p[a][1],p[b][0],p[b][1],(56,216,255))
            line(buf,w,h,p[b][0],p[b][1],p[c][0],p[c][1],(56,216,255))
            line(buf,w,h,p[c][0],p[c][1],p[a][0],p[a][1],(56,216,255))
    else:
        skip=max(1,len(p)//45000)
        for x,y,_ in p[::skip]:
            put_px(buf,w,h,x,y,(56,216,255))
    write_png(out,w,h,buf)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('obj', type=Path)
    ap.add_argument('--out', type=Path, default=None)
    args=ap.parse_args()
    out=args.out or args.obj.with_suffix('.preview.png')
    render(args.obj,out)
    print(out)
if __name__=='__main__': main()
