#!/usr/bin/env python3
from __future__ import annotations
import json, math, struct
from pathlib import Path

import argparse

DEFAULT_DST = Path(__file__).resolve().parents[1] / 'related_apps' / 'CodeRED_Tuner' / 'assets' / 'vehicles' / 'concept_car_arcade_rig.glb'
SRC = Path('concept_car.glb')
DST = DEFAULT_DST
MANIFEST = DST.with_suffix('.manifest.json')
SCALE = 17.0
WHEEL_ROOTS = {51:'wheel_rear_right',61:'wheel_front_right',71:'wheel_front_left',81:'wheel_rear_left'}
# Names are assigned for arcade +X forward using the existing Code Red steering convention.
# Original glTF axis: X lateral, Y up, Z length. We map arcade X=-Z, Y=X, Z=Y.

FMT_MAP = {5126:('f',4),5125:('I',4),5123:('H',2),5121:('B',1),5122:('h',2),5120:('b',1)}
COMP_NUM = {'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}

def read_glb(path: Path):
    raw = path.read_bytes()
    magic, version, declared = struct.unpack_from('<III', raw, 0)
    if magic != 0x46546C67 or version != 2:
        raise ValueError('not a glTF 2.0 GLB')
    pos = 12; doc = None; bin_blob = b''
    while pos + 8 <= len(raw):
        clen, ctype = struct.unpack_from('<I4s', raw, pos); pos += 8
        chunk = raw[pos:pos+clen]; pos += clen
        if ctype == b'JSON':
            doc = json.loads(chunk.rstrip(b'\x00 \t\r\n').decode('utf-8'))
        elif ctype == b'BIN\x00':
            bin_blob = bytes(chunk)
    if doc is None:
        raise ValueError('no JSON chunk')
    return doc, bin_blob

def mat_identity():
    return [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]

def mat_mul(a,b):
    out=[0.0]*16
    for col in range(4):
        for row in range(4):
            out[col*4+row]=sum(a[k*4+row]*b[col*4+k] for k in range(4))
    return out

def trans_mat(t):
    m=mat_identity(); m[12],m[13],m[14]=map(float,t); return m

def scale_mat(s):
    m=mat_identity(); m[0],m[5],m[10]=map(float,s); return m

def quat_mat(q):
    x,y,z,w=map(float,q); xx=x*x; yy=y*y; zz=z*z; xy=x*y; xz=x*z; yz=y*z; wx=w*x; wy=w*y; wz=w*z
    return [1-2*(yy+zz), 2*(xy+wz), 2*(xz-wy),0, 2*(xy-wz),1-2*(xx+zz),2*(yz+wx),0, 2*(xz+wy),2*(yz-wx),1-2*(xx+yy),0, 0,0,0,1]

def node_mat(n):
    if 'matrix' in n:
        return [float(v) for v in n['matrix']]
    m=mat_identity()
    if 'translation' in n: m=mat_mul(m,trans_mat(n['translation']))
    if 'rotation' in n: m=mat_mul(m,quat_mat(n['rotation']))
    if 'scale' in n: m=mat_mul(m,scale_mat(n['scale']))
    return m

def transform(m,p):
    x,y,z=map(float,p)
    return (m[0]*x+m[4]*y+m[8]*z+m[12], m[1]*x+m[5]*y+m[9]*z+m[13], m[2]*x+m[6]*y+m[10]*z+m[14])

def read_accessor(doc, bin_blob, ai):
    acc=doc['accessors'][int(ai)]; view=doc['bufferViews'][int(acc.get('bufferView',0))]
    fmt, comp_size = FMT_MAP[int(acc['componentType'])]
    comps = COMP_NUM[str(acc.get('type','SCALAR'))]
    count = int(acc.get('count',0))
    stride = int(view.get('byteStride', comp_size * comps) or (comp_size * comps))
    base = int(view.get('byteOffset',0)) + int(acc.get('byteOffset',0))
    out=[]
    for i in range(count):
        vals = struct.unpack_from('<' + fmt*comps, bin_blob, base + i*stride)
        if comps == 1:
            out.append(int(vals[0]))
        else:
            out.append(tuple(float(v) for v in vals))
    return out

def pad4(data: bytes, fill=b'\x00') -> bytes:
    return data + fill * ((4 - len(data) % 4) % 4)

def build(src: Path | None = None, dst: Path | None = None):
    global SRC, DST, MANIFEST
    if src is not None:
        SRC = Path(src)
    if dst is not None:
        DST = Path(dst)
        MANIFEST = DST.with_suffix('.manifest.json')
    doc, bin_blob = read_glb(SRC)
    nodes = doc['nodes']
    children = {i:n.get('children',[]) for i,n in enumerate(nodes)}
    roots=[]
    for sc in doc.get('scenes',[{}]): roots += sc.get('nodes',[])
    if not roots: roots=[0]
    world={}; parent={}; wheel_owner={}
    def rec(i, pm, owner=None):
        if i in WHEEL_ROOTS: owner = WHEEL_ROOTS[i]
        m = mat_mul(pm, node_mat(nodes[i])); world[i]=m; wheel_owner[i]=owner
        for c in children.get(i,[]):
            parent[c]=i; rec(c, m, owner)
    for r in roots: rec(r, mat_identity(), None)

    # Determine original model bounds for a stable ground and center transform.
    all_pts=[]
    mesh_positions_cache={}
    mesh_indices_cache={}
    for ni,n in enumerate(nodes):
        if 'mesh' not in n: continue
        mesh = doc['meshes'][int(n['mesh'])]
        for pi, prim in enumerate(mesh.get('primitives',[])):
            if int(prim.get('mode',4)) != 4 or 'POSITION' not in prim.get('attributes',{}):
                continue
            key=(int(n['mesh']), pi)
            positions = mesh_positions_cache.get(key)
            if positions is None:
                positions = read_accessor(doc, bin_blob, prim['attributes']['POSITION'])
                mesh_positions_cache[key]=positions
            for p in positions:
                all_pts.append(transform(world[ni], p))
    if not all_pts:
        raise ValueError('source GLB did not contain readable triangle positions')
    min_y = min(p[1] for p in all_pts)
    center_z = (min(p[2] for p in all_pts) + max(p[2] for p in all_pts)) * 0.5
    center_x = (min(p[0] for p in all_pts) + max(p[0] for p in all_pts)) * 0.5
    def to_arcade(p):
        ox,oy,oz=p
        return (-(oz - center_z) * SCALE, (ox - center_x) * SCALE, (oy - min_y) * SCALE)

    role_centers={}
    for root, role in WHEEL_ROOTS.items():
        role_centers[role] = to_arcade(transform(world[root], (0,0,0)))

    parts={role:{'positions':[], 'indices':[]} for role in ['body'] + list(WHEEL_ROOTS.values())}
    # Merge every source primitive into a body or wheel part using transformed vertices.
    for ni,n in enumerate(nodes):
        if 'mesh' not in n: continue
        role = wheel_owner.get(ni) or 'body'
        mesh = doc['meshes'][int(n['mesh'])]
        for pi, prim in enumerate(mesh.get('primitives',[])):
            if int(prim.get('mode',4)) != 4 or 'POSITION' not in prim.get('attributes',{}) or 'indices' not in prim:
                continue
            k=(int(n['mesh']),pi)
            positions = mesh_positions_cache.get(k) or read_accessor(doc, bin_blob, prim['attributes']['POSITION'])
            mesh_positions_cache[k]=positions
            ik=int(prim['indices'])
            indices = mesh_indices_cache.get(ik)
            if indices is None:
                indices = read_accessor(doc, bin_blob, ik)
                mesh_indices_cache[ik]=indices
            base = len(parts[role]['positions'])
            center = role_centers.get(role, (0,0,0))
            for p in positions:
                ap = to_arcade(transform(world[ni], p))
                parts[role]['positions'].append((ap[0]-center[0], ap[1]-center[1], ap[2]-center[2]))
            parts[role]['indices'].extend(base + int(i) for i in indices)

    # Drop any empty role defensively, then compact to a stylized actual-mesh wire LOD.
    # This keeps the source shape while avoiding a dense black triangle blob and expensive
    # repeated arcade car instances. It is not a box/frame approximation: all retained
    # vertices come from the real source GLB geometry after transforms.
    for role, stride in [('body', 8), ('wheel_front_left', 2), ('wheel_front_right', 2), ('wheel_rear_left', 2), ('wheel_rear_right', 2)]:
        pos = parts[role]['positions']; idx = parts[role]['indices']
        if not pos or not idx:
            continue
        kept_tris = []
        tri_no = 0
        for i in range(0, len(idx) - 2, 3):
            if tri_no % stride == 0:
                kept_tris.append((idx[i], idx[i+1], idx[i+2]))
            tri_no += 1
        used = {}
        new_pos = []
        new_idx = []
        for tri in kept_tris:
            for old_i in tri:
                old_i = int(old_i)
                if old_i not in used:
                    used[old_i] = len(new_pos)
                    new_pos.append(pos[old_i])
                new_idx.append(used[old_i])
        parts[role]['positions'] = new_pos
        parts[role]['indices'] = new_idx
        parts[role]['lod_stride'] = stride

    roles=[r for r in ['body','wheel_front_left','wheel_front_right','wheel_rear_left','wheel_rear_right'] if parts[r]['positions'] and parts[r]['indices']]

    buffer=bytearray(); buffer_views=[]; accessors=[]; meshes=[]; nodes_out=[]
    def add_blob(blob: bytes, target: int|None = None):
        while len(buffer) % 4: buffer.append(0)
        offset=len(buffer); buffer.extend(blob)
        bv={'buffer':0,'byteOffset':offset,'byteLength':len(blob)}
        if target is not None: bv['target']=target
        buffer_views.append(bv)
        return len(buffer_views)-1
    def add_mesh(role):
        pos=parts[role]['positions']; idx=parts[role]['indices']
        pos_blob=b''.join(struct.pack('<fff', *p) for p in pos)
        pos_bv=add_blob(pos_blob, 34962)
        xs=[p[0] for p in pos]; ys=[p[1] for p in pos]; zs=[p[2] for p in pos]
        pos_acc={'bufferView':pos_bv,'byteOffset':0,'componentType':5126,'count':len(pos),'type':'VEC3','min':[min(xs),min(ys),min(zs)],'max':[max(xs),max(ys),max(zs)]}
        accessors.append(pos_acc); pos_ai=len(accessors)-1
        idx_blob=b''.join(struct.pack('<I', int(i)) for i in idx)
        idx_bv=add_blob(idx_blob, 34963)
        idx_acc={'bufferView':idx_bv,'byteOffset':0,'componentType':5125,'count':len(idx),'type':'SCALAR','min':[min(idx) if idx else 0],'max':[max(idx) if idx else 0]}
        accessors.append(idx_acc); idx_ai=len(accessors)-1
        mesh={'name':role+'_actual_wiremesh','primitives':[{'attributes':{'POSITION':pos_ai},'indices':idx_ai,'mode':4}]}
        meshes.append(mesh)
        return len(meshes)-1
    for role in roles:
        mesh_i=add_mesh(role)
        node={'name':role, 'mesh':mesh_i, 'extras':{'code_red_rig_role':role, 'code_red_source':'concept_car.glb', 'code_red_wiremesh':'actual triangle mesh, not bounding frame'}}
        if role!='body':
            node['translation']=[round(v,6) for v in role_centers[role]]
        else:
            node['translation']=[0,0,0]
        nodes_out.append(node)

    outdoc={
        'asset': {'version':'2.0','generator':'Code RED concept_vehicle_glb_importer actual-wiremesh-rig'},
        'scene':0,
        'scenes':[{'nodes':list(range(len(nodes_out)))}],
        'nodes':nodes_out,
        'meshes':meshes,
        'buffers':[{'byteLength':len(buffer)}],
        'bufferViews':buffer_views,
        'accessors':accessors,
        'extras': {
            'code_red_asset':'concept_car_arcade_rig',
            'source_file':SRC.name,
            'scale':SCALE,
            'axis_map':'arcade_x=-source_z, arcade_y=source_x, arcade_z=source_y-ground',
            'note':'Actual source mesh converted to wireframe-ready GLB with separate wheel controls.'
        }
    }
    json_blob=pad4(json.dumps(outdoc,separators=(',',':')).encode('utf-8'), b' ')
    bin_blob2=pad4(bytes(buffer), b'\x00')
    total=12+8+len(json_blob)+8+len(bin_blob2)
    glb=bytearray()
    glb.extend(struct.pack('<III',0x46546C67,2,total))
    glb.extend(struct.pack('<I4s',len(json_blob),b'JSON')); glb.extend(json_blob)
    glb.extend(struct.pack('<I4s',len(bin_blob2),b'BIN\x00')); glb.extend(bin_blob2)
    DST.parent.mkdir(parents=True,exist_ok=True)
    DST.write_bytes(glb)
    def bounds(pos):
        return {'count':len(pos), 'min':[min(p[k] for p in pos) for k in range(3)], 'max':[max(p[k] for p in pos) for k in range(3)]}
    manifest={'source':str(SRC),'output':str(DST),'roles':{r: {'vertices':len(parts[r]['positions']),'indices':len(parts[r]['indices']),'triangles':len(parts[r]['indices'])//3,'center': role_centers.get(r, [0,0,0]), 'bounds': bounds(parts[r]['positions'])} for r in roles}, 'source_bounds': {'min_y':min_y,'center_z':center_z,'center_x':center_x}, 'scale':SCALE}
    MANIFEST.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(manifest, indent=2)[:4000])

def main(argv=None):
    parser = argparse.ArgumentParser(description='Convert a source concept_car.glb into Code Red Arcade actual-wiremesh vehicle rig.')
    parser.add_argument('source', nargs='?', default=str(SRC), help='Source concept car GLB.')
    parser.add_argument('--output', default=str(DEFAULT_DST), help='Output arcade rig GLB.')
    ns = parser.parse_args(argv)
    build(Path(ns.source), Path(ns.output))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
