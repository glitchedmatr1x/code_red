#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,struct
from dataclasses import asdict
from pathlib import Path
from codered_wsi_explorer import RPF6,VBASE,SAG_SECTORINFO_VFT,hash_map,load_names,rsc_decode,sha1


def u8(b,o): return b[o] if 0<=o<len(b) else 0
def u16(b,o): return struct.unpack_from('<H',b,o)[0] if o+2<=len(b) else 0
def u32(b,o): return struct.unpack_from('<I',b,o)[0] if o+4<=len(b) else 0
def f32(b,o): return struct.unpack_from('<f',b,o)[0] if o+4<=len(b) else 0.0
def vec4(b,o): return [round(x,6) for x in struct.unpack_from('<4f',b,o)] if o+16<=len(b) else [0,0,0,0]
def target(v,size): return v-VBASE if VBASE<=v<VBASE+size else None
def ptr_hex(v): return f'0x{v:08X}' if v else ''
def cstr(b,o,max_len=256):
    if o is None or o<0 or o>=len(b): return ''
    e=o
    while e<len(b) and e-o<max_len and b[e]!=0: e+=1
    return b[o:e].decode('latin-1','replace')

def arr_desc(b,o):
    ptr=u32(b,o)
    return dict(ptr=ptr,ptr_hex=ptr_hex(ptr),offset=target(ptr,len(b)),count=u16(b,o+4),capacity=u16(b,o+6))

def sector_offsets(payload):
    sig=struct.pack('<I',SAG_SECTORINFO_VFT); out=[]; start=0
    while True:
        off=payload.find(sig,start)
        if off<0: break
        if off%4==0 and off+480<=len(payload): out.append(off)
        start=off+4
    return out

ARRAY_FIELDS={
    'props':0xD4,
    'doors_attributes':0xDC,
    'children':0xE8,
    'child_ptrs':0xF4,
    'drawable_instances':0xFC,
    'drawable_instances2':0x104,
    'occluders':0x17C,
    'locators':0x1A0,
}
PTR_FIELDS={'placed_lights_group':0xD0,'child_group':0xF0,'bound_instances':0x1D0}


def parse_sector(payload,off,names):
    name_ptr=u32(payload,off+8); scope_ptr=u32(payload,off+0x1b0)
    scoped_hash=u32(payload,off+0x1c); name_hash=u32(payload,off+0x178); flags=u32(payload,off+0x1c8)
    row=dict(
        sector_offset=off,
        sector_offset_hex=f'0x{off:08X}',
        name=cstr(payload,target(name_ptr,len(payload))),
        scope=cstr(payload,target(scope_ptr,len(payload))),
        scoped_name_hash=f'0x{scoped_hash:08X}' if scoped_hash else '',
        scoped_name_resolved=names.get(scoped_hash,''),
        sector_name_hash=f'0x{name_hash:08X}' if name_hash else '',
        sector_name_resolved=names.get(name_hash,''),
        bound_min=vec4(payload,off+0xb0),
        bound_max=vec4(payload,off+0xc0),
        flags=f'0x{flags:08X}',
        disabled_flag_guess=bool(flags&0x01000000),
        resident_status=u32(payload,off+0x188),
        district=u8(payload,off+0x1bd),
        ref_count=u8(payload,off+0x1c5),
    )
    for name,rel in ARRAY_FIELDS.items():
        desc=arr_desc(payload,off+rel)
        row[name+'_ptr']=desc['ptr_hex']; row[name+'_offset']=desc['offset']; row[name+'_count']=desc['count']; row[name+'_capacity']=desc['capacity']
    for name,rel in PTR_FIELDS.items():
        val=u32(payload,off+rel); row[name+'_ptr']=ptr_hex(val); row[name+'_offset']=target(val,len(payload))
    return row

def parse_child_group(payload,owner_off,cg_off):
    rows=[]; details=[]
    if cg_off is None or cg_off<0 or cg_off+28>len(payload): return rows,details
    sectors=arr_desc(payload,cg_off+0); parents=arr_desc(payload,cg_off+8); indices=arr_desc(payload,cg_off+16); scope_ptr=u32(payload,cg_off+24)
    rows.append(dict(owner_sector_offset=owner_off,owner_sector_offset_hex=f'0x{owner_off:08X}',child_group_offset=cg_off,child_group_offset_hex=f'0x{cg_off:08X}',scope=cstr(payload,target(scope_ptr,len(payload))),sectors_ptr=sectors['ptr_hex'],sectors_offset=sectors['offset'],sectors_count=sectors['count'],parents_ptr=parents['ptr_hex'],parents_offset=parents['offset'],parents_count=parents['count'],indices_ptr=indices['ptr_hex'],indices_offset=indices['offset'],indices_count=indices['count']))
    if sectors['offset'] is not None:
        for i in range(sectors['count']):
            val=u32(payload,sectors['offset']+i*4)
            details.append(dict(kind='child_group_sector',owner_sector_offset=owner_off,child_group_offset=cg_off,index=i,value_ptr=ptr_hex(val),value_offset=target(val,len(payload))))
    if parents['offset'] is not None:
        for i in range(parents['count']):
            val=u32(payload,parents['offset']+i*4)
            details.append(dict(kind='child_group_parent',owner_sector_offset=owner_off,child_group_offset=cg_off,index=i,value_ptr=ptr_hex(val),value_offset=target(val,len(payload))))
    if indices['offset'] is not None:
        for i in range(indices['count']):
            val=u16(payload,indices['offset']+i*2)
            details.append(dict(kind='child_group_index',owner_sector_offset=owner_off,child_group_offset=cg_off,index=i,value_ptr='',value_offset=val))
    return rows,details

def pointer_array_items(payload,sector_off,name,desc):
    rows=[]
    if desc['offset'] is None: return rows
    for i in range(desc['count']):
        val=u32(payload,desc['offset']+i*4)
        rows.append(dict(sector_offset=sector_off,array_name=name,index=i,value_ptr=ptr_hex(val),value_offset=target(val,len(payload))))
    return rows

def parse_drawable_base(payload,sector_off,array_name,index,off):
    if off is None or off<0 or off+224>len(payload): return None
    return dict(
        sector_offset=sector_off,
        array_name=array_name,
        index=index,
        offset=off,
        offset_hex=f'0x{off:08X}',
        vft=f'0x{u32(payload,off):08X}',
        time_last_visible=round(f32(payload,off+4),6),
        last_known_position_and_flags=vec4(payload,off+0x10),
        node_raw=f'0x{u32(payload,off+0x20):08X}',
        matrix_guess=[vec4(payload,off+0x40+i*16) for i in range(4)],
        bbox_min_guess=vec4(payload,off+0x80),
        bbox_max_guess=vec4(payload,off+0x90),
        instance_hash_guess=f'0x{u32(payload,off+0xA0):08X}',
        name_ptr_guess=ptr_hex(u32(payload,off+0xB4)),
        name_guess=cstr(payload,target(u32(payload,off+0xB4),len(payload))),
        room_ptr_guess=ptr_hex(u32(payload,off+0xB8)),
        next_drawable_ptr_guess=ptr_hex(u32(payload,off+0xD4)),
    )

def write_table(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    if not rows:
        path.write_text('',encoding='utf-8'); return
    fields=[]
    for row in rows:
        for key in row:
            if key not in fields: fields.append(key)
    with path.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fields); writer.writeheader(); writer.writerows(rows)

def export_one(rpf,entry,names,outdir):
    _header,payload=rsc_decode(rpf.slot(entry)); sector_rows=[]; child_group_rows=[]; child_group_items=[]; pointer_items=[]; drawable_rows=[]
    for off in sector_offsets(payload):
        sector=parse_sector(payload,off,names); sector['wsi_path']=entry.path; sector['decoded_sha1']=sha1(payload); sector_rows.append(sector)
        cg_rows,cg_items=parse_child_group(payload,off,sector.get('child_group_offset')); child_group_rows+=cg_rows; child_group_items+=cg_items
        for name,rel in ARRAY_FIELDS.items():
            desc=arr_desc(payload,off+rel)
            if name in ('child_ptrs',): pointer_items+=pointer_array_items(payload,off,name,desc)
            if name in ('drawable_instances','drawable_instances2') and desc['offset'] is not None:
                for i in range(desc['count']):
                    item=parse_drawable_base(payload,off,name,i,desc['offset']+i*224)
                    if item: drawable_rows.append(item)
    safe=entry.path.replace('/','__').replace('\\','__')
    write_table(outdir/f'{safe}.sectors.csv',sector_rows)
    write_table(outdir/f'{safe}.child_groups.csv',child_group_rows)
    write_table(outdir/f'{safe}.child_group_items.csv',child_group_items)
    write_table(outdir/f'{safe}.pointer_items.csv',pointer_items)
    write_table(outdir/f'{safe}.drawable_instances.csv',drawable_rows)
    (outdir/f'{safe}.arrays.json').write_text(json.dumps(dict(entry=asdict(entry),sector_count=len(sector_rows),child_groups=child_group_rows,child_group_items=child_group_items,pointer_items=pointer_items,drawable_instances=drawable_rows),indent=2),encoding='utf-8')
    return dict(path=entry.path,decoded_size=len(payload),decoded_sha1=sha1(payload),sector_count=len(sector_rows),child_group_count=len(child_group_rows),child_group_item_count=len(child_group_items),pointer_item_count=len(pointer_items),drawable_instance_count=len(drawable_rows))

def main():
    parser=argparse.ArgumentParser(description='Code RED WSI array walker/exporter')
    parser.add_argument('archive')
    parser.add_argument('--path')
    parser.add_argument('--names',nargs='*',default=[])
    parser.add_argument('--outdir',default='exports/wsi_array_export')
    parser.add_argument('--no-debug',action='store_true')
    args=parser.parse_args()
    rpf=RPF6(args.archive,not args.no_debug); names=hash_map(rpf,load_names(args.names)); outdir=Path(args.outdir); outdir.mkdir(parents=True,exist_ok=True)
    entries=[rpf.find(args.path)] if args.path else rpf.files('.wsi') or [e for e in rpf.entries if e.type=='file' and e.resource and e.resource_type==134]
    master=[]
    for entry in entries:
        if entry is None: raise KeyError(args.path)
        result=export_one(rpf,entry,names,outdir); master.append(result); print('Exported arrays:',result)
    (outdir/'wsi_array_export_master.json').write_text(json.dumps(dict(archive=rpf.summary(),wsi=master),indent=2),encoding='utf-8')
    print('Wrote',outdir)

if __name__=='__main__': main()
