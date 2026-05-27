#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import re, csv, json, hashlib, argparse

def main():
    ap=argparse.ArgumentParser(description='Parse MagicRDR decompiled script for car/truck mission recipe clues.')
    ap.add_argument('decompiled_txt', type=Path)
    ap.add_argument('--outdir', type=Path, default=Path('reports/pass29_parse'))
    args=ap.parse_args()
    text=args.decompiled_txt.read_text(encoding='utf-8', errors='ignore')
    lines=text.splitlines()
    args.outdir.mkdir(parents=True, exist_ok=True)
    terms=['GET_ACTOR_ENUM','1194','1193','1197','carSettings','SET_ACTOR_IN_VEHICLE','START_VEHICLE','SET_VEHICLE_ENGINE_RUNNING','GET_RAND_ACTORENUM_FROM_POPULATION_NATIVE','MaximShootTruck','Local_6 + 1184[02]']
    rows=[]
    current='GLOBAL'; pos=''
    fre=re.compile(r'^(?:var|void|int|float|bool|struct<\d+>)\s+(Function_\d+)\([^\n]*\)\s*//Position: (0x[0-9A-Fa-f]+)')
    for i,line in enumerate(lines,1):
        m=fre.match(line)
        if m:
            current=m.group(1); pos=m.group(2)
        for term in terms:
            if term in line:
                rows.append({'line':i,'function':current,'position':pos,'term':term,'text':line.strip()})
    with (args.outdir/'line_hits.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['line','function','position','term','text']); w.writeheader(); w.writerows(rows)
    summary={'source':str(args.decompiled_txt),'sha1':hashlib.sha1(args.decompiled_txt.read_bytes()).hexdigest(),'hits':len(rows),'term_counts':{t:sum(1 for r in rows if r['term']==t) for t in terms}}
    (args.outdir/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))
if __name__=='__main__': main()
