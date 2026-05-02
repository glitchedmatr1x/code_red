#!/usr/bin/env python3
from __future__ import annotations
import math, struct, sys, zlib, json
from pathlib import Path
from dataclasses import dataclass, field

@dataclass
class Node:
    name: str
    props: list
    children: list['Node'] = field(default_factory=list)

class FBXParser:
    def __init__(self, data: bytes):
        self.data=data
        if not data.startswith(b'Kaydara FBX Binary  \x00\x1a\x00'):
            raise ValueError('not binary FBX')
        self.version=struct.unpack_from('<I', data, 23)[0]
        self.word64=self.version>=7500
    def read_header(self,p:int):
        if self.word64:
            end,num,plen=struct.unpack_from('<QQQ', self.data, p); p+=24
        else:
            end,num,plen=struct.unpack_from('<III', self.data, p); p+=12
        name_len=self.data[p]; p+=1
        return end,num,plen,name_len,p
    def parse_prop(self,p:int):
        d=self.data; t=chr(d[p]); p+=1
        if t=='Y': v=struct.unpack_from('<h',d,p)[0]; p+=2
        elif t=='C': v=struct.unpack_from('<?',d,p)[0]; p+=1
        elif t=='I': v=struct.unpack_from('<i',d,p)[0]; p+=4
        elif t=='F': v=struct.unpack_from('<f',d,p)[0]; p+=4
        elif t=='D': v=struct.unpack_from('<d',d,p)[0]; p+=8
        elif t=='L': v=struct.unpack_from('<q',d,p)[0]; p+=8
        elif t in 'fdlib':
            length, enc, clen=struct.unpack_from('<III',d,p); p+=12
            raw=d[p:p+clen]; p+=clen
            if enc==1: raw=zlib.decompress(raw)
            fmt={'f':'f','d':'d','l':'q','i':'i','b':'?'}[t]
            v=list(struct.unpack_from('<'+fmt*length, raw, 0)) if length else []
        elif t in 'SR':
            length=struct.unpack_from('<I',d,p)[0]; p+=4
            raw=d[p:p+length]; p+=length
            v=raw.decode('utf-8','replace') if t=='S' else raw
        else:
            raise ValueError(f'unknown prop {t!r} at {p}')
        return v,p
    def parse_node(self,p:int, limit:int):
        if p+(25 if self.word64 else 13)>limit: return None,p
        end,num,plen,nlen,p2 = self.read_header(p)
        if end==0 and num==0 and plen==0 and nlen==0:
            return None,p2
        name=self.data[p2:p2+nlen].decode('utf-8','replace'); p2+=nlen
        props=[]
        for _ in range(num):
            v,p2=self.parse_prop(p2); props.append(v)
        children=[]; null_len=25 if self.word64 else 13
        while p2 < end-null_len:
            child,p2n=self.parse_node(p2,end)
            if child is None:
                p2=p2n; break
            children.append(child); p2=p2n
        return Node(name, props, children), end
    def parse(self):
        roots=[]; p=27; L=len(self.data)
        while p < L-160:
            node,p2=self.parse_node(p,L)
            if node is None: break
            roots.append(node); p=p2
        return roots

def walk(nodes):
    for n in nodes:
        yield n
        yield from walk(n.children)

def get_child(node:Node, name:str):
    for c in node.children:
        if c.name==name: return c
    return None

def props70(node:Node):
    out={}
    p70=get_child(node,'Properties70')
    if not p70: return out
    for p in p70.children:
        if p.name!='P' or len(p.props)<5: continue
        vals=p.props[4:]
        out[str(p.props[0])]=vals[0] if len(vals)==1 else vals
    return out

def clean_name(name:str)->str:
    return str(name).split('\x00',1)[0]
def sanitize(name:str)->str:
    name=clean_name(name)
    return ''.join(ch if ch.isalnum() or ch in '_-.' else '_' for ch in name) or 'mesh'
def selected_mesh(name:str)->bool:
    n=sanitize(name).lower()
    if n.startswith('wgt-') or n.startswith('plane'):
        return False
    return n == 'body' or n.startswith('bamper') or n.startswith('wbl_b1')

def mat_mul(A,B):
    return [[sum(A[r][k]*B[k][c] for k in range(4)) for c in range(4)] for r in range(4)]
def ident(): return [[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
def trans(v):
    M=ident(); M[0][3]=v[0]; M[1][3]=v[1]; M[2][3]=v[2]; return M
def scale(v):
    M=ident(); M[0][0]=v[0]; M[1][1]=v[1]; M[2][2]=v[2]; return M
def rotx(a):
    c=math.cos(a); s=math.sin(a); return [[1,0,0,0],[0,c,-s,0],[0,s,c,0],[0,0,0,1]]
def roty(a):
    c=math.cos(a); s=math.sin(a); return [[c,0,s,0],[0,1,0,0],[-s,0,c,0],[0,0,0,1]]
def rotz(a):
    c=math.cos(a); s=math.sin(a); return [[c,-s,0,0],[s,c,0,0],[0,0,1,0],[0,0,0,1]]
def transform_point(M,p):
    x,y,z=p; return (M[0][0]*x+M[0][1]*y+M[0][2]*z+M[0][3], M[1][0]*x+M[1][1]*y+M[1][2]*z+M[1][3], M[2][0]*x+M[2][1]*y+M[2][2]*z+M[2][3])

def model_matrix(model:Node):
    props=props70(model)
    t=props.get('Lcl Translation',[0,0,0]); r=props.get('Lcl Rotation',[0,0,0]); s=props.get('Lcl Scaling',[1,1,1])
    if not isinstance(t,list): t=[t,0,0]
    if not isinstance(r,list): r=[r,0,0]
    if not isinstance(s,list): s=[s,1,1]
    rx,ry,rz=[math.radians(float(x)) for x in (r+[0,0,0])[:3]]
    return mat_mul(trans([float(x) for x in (t+[0,0,0])[:3]]), mat_mul(rotz(rz), mat_mul(roty(ry), mat_mul(rotx(rx), scale([float(x) for x in (s+[1,1,1])[:3]])))))

def build_meshes(inf:Path):
    roots=FBXParser(inf.read_bytes()).parse()
    geoms={}; models={}; conns=[]
    for n in walk(roots):
        if n.name=='Geometry' and n.props: geoms[int(n.props[0])] = n
        elif n.name=='Model' and n.props: models[int(n.props[0])] = n
        elif n.name=='C' and len(n.props)>=3: conns.append(n.props)
    geom_to_model={}; parent={}
    for p in conns:
        if p[0]=='OO':
            a=int(p[1]); b=int(p[2])
            if a in geoms and b in models: geom_to_model[a]=b
            if a in models and b in models: parent[a]=b
    memo={}
    def world(mid:int):
        if mid not in models: return ident()
        if mid in memo: return memo[mid]
        M=model_matrix(models[mid])
        if mid in parent: M=mat_mul(world(parent[mid]), M)
        memo[mid]=M; return M
    meshes=[]; skipped=[]
    for gid,g in geoms.items():
        verts_node=get_child(g,'Vertices'); idx_node=get_child(g,'PolygonVertexIndex')
        if not verts_node or not idx_node or not verts_node.props or not idx_node.props: continue
        mid=geom_to_model.get(gid)
        name=clean_name(models[mid].props[1] if mid in models and len(models[mid].props)>1 else g.props[1])
        if not selected_mesh(name):
            skipped.append(sanitize(name)); continue
        verts_raw=verts_node.props[0]; indices=idx_node.props[0]
        verts=[tuple(float(x) for x in verts_raw[i:i+3]) for i in range(0,len(verts_raw),3)]
        M=world(mid) if mid in models else ident()
        verts=[transform_point(M,v) for v in verts]
        polys=[]; cur=[]
        for idx in indices:
            idx=int(idx)
            if idx<0:
                cur.append(-idx-1); polys.append(cur); cur=[]
            else:
                cur.append(idx)
        if cur: polys.append(cur)
        meshes.append((sanitize(name), verts, polys))
    return meshes, {'geometry_count':len(geoms), 'models':len(models), 'connected_meshes':len(geom_to_model), 'skipped':skipped}

def main():
    if len(sys.argv)<3:
        print('usage: fbx_to_obj_static.py input.fbx output.obj'); return 2
    inf=Path(sys.argv[1]); outf=Path(sys.argv[2]); outf.parent.mkdir(parents=True, exist_ok=True)
    meshes, meta=build_meshes(inf)
    allv=[v for _,verts,_ in meshes for v in verts]
    if not allv: raise RuntimeError('no selected vehicle meshes found')
    minv=[min(v[i] for v in allv) for i in range(3)]; maxv=[max(v[i] for v in allv) for i in range(3)]
    cen=[(minv[i]+maxv[i])/2 for i in range(3)]
    length=maxv[0]-minv[0] or 1.0
    scale_factor=72.0/length
    # FBX: X length, Y up, Z width -> Panda: X length, Y width, Z up.
    out=['# Static OBJ converted from FBX by Code RED arcade importer', 'o code_red_vehicle_model']
    offset=1; tri_count=0; vert_count=0
    for name,verts,polys in meshes:
        out.append(f'g {name}')
        for x,y,z in verts:
            nx=(x-cen[0])*scale_factor
            ny=(z-cen[2])*scale_factor
            nz=(y-minv[1])*scale_factor
            out.append(f'v {nx:.6f} {ny:.6f} {nz:.6f}')
        for poly in polys:
            if len(poly)<3: continue
            for i in range(1,len(poly)-1):
                out.append(f'f {offset+poly[0]} {offset+poly[i]} {offset+poly[i+1]}')
                tri_count+=1
        offset += len(verts); vert_count += len(verts)
    outf.write_text('\n'.join(out)+'\n', encoding='utf-8')
    summary={**meta, 'input':str(inf), 'output':str(outf), 'mesh_count':len(meshes), 'triangles':tri_count, 'vertices':vert_count, 'bbox_min':minv, 'bbox_max':maxv, 'scale_factor':scale_factor, 'axis_mapping':'FBX X,Y,Z -> Panda X,Z,Y', 'mesh_names':[m[0] for m in meshes]}
    Path(str(outf)+'.json').write_text(json.dumps(summary,indent=2), encoding='utf-8')
    print(json.dumps(summary,indent=2))
    return 0
if __name__=='__main__': raise SystemExit(main())
