#!/usr/bin/env python3
"""
Build a Code RED Remote Menu sector catalog from territory_swall exports, RPF parent names,
and optional Code RED Workbench sector_inventory.csv files.

This intentionally does not edit game files. It produces JSON/CSV the trainer menu can use to
show parent territories and sector children before Codex wires the live ASI UI.
"""
from __future__ import annotations
import argparse, csv, json, re, zipfile
from pathlib import Path

TOKEN_RE = re.compile(r"(?:[a-z]{2,4}_[a-zA-Z0-9_]+|dlc\d{2}x|mp_[a-zA-Z0-9_]+)")


def clean_parent_name(name: str) -> str:
    p = Path(name.replace('\\', '/'))
    stem = p.stem if p.suffix else p.name
    return stem.lower()


def add_entry(entries, parent, name, kind='unknown', state='unknown', source=''):
    if not name or len(name) < 3:
        return
    key = (parent, name, kind)
    if key in entries:
        old = entries[key]
        if old.get('state') == 'unknown' and state != 'unknown': old['state'] = state
        if source and source not in old.get('source',''):
            old['source'] = (old.get('source','') + ';' + source).strip(';')
        return
    entries[key] = {'parent': parent, 'name': name, 'kind': kind, 'state': state, 'source': source}


def scan_zip(path: Path, entries):
    with zipfile.ZipFile(path) as z:
        for zi in z.infolist():
            name = zi.filename.replace('\\', '/')
            low = name.lower()
            if low.endswith('.rpf'):
                parent = clean_parent_name(name)
                add_entry(entries, parent, parent, 'world', 'unknown', f'{path.name}:rpf_parent')
            # If user exported folders/files from inside RPFs, infer parent from first path segment or rpf stem.
            parts = [p for p in name.split('/') if p]
            parent = clean_parent_name(parts[0]) if parts else clean_parent_name(path.name)
            for token in TOKEN_RE.findall(name):
                kind = 'world' if re.fullmatch(r'dlc\d{2}x', token) else 'child'
                add_entry(entries, parent, token, kind, 'unknown', f'{path.name}:path_token')
            # Small text members may contain sector names.
            if zi.file_size and zi.file_size < 2_000_000 and any(low.endswith(ext) for ext in ('.xml','.txt','.csv','.sc.xml','.json')):
                try:
                    data = z.read(zi)
                    text = data.decode('utf-8', errors='ignore')
                except Exception:
                    continue
                for token in TOKEN_RE.findall(text):
                    kind = 'world' if re.fullmatch(r'dlc\d{2}x', token) else 'child'
                    add_entry(entries, parent, token, kind, 'unknown', f'{path.name}:text_token')


def scan_directory(path: Path, entries):
    for p in path.rglob('*'):
        if p.is_dir():
            continue
        rel = p.relative_to(path).as_posix()
        parent = clean_parent_name(rel.split('/')[0]) if '/' in rel else clean_parent_name(path.name)
        if p.suffix.lower() == '.rpf':
            parent = clean_parent_name(p.name)
            add_entry(entries, parent, parent, 'world', 'unknown', f'{path}:rpf_parent')
        for token in TOKEN_RE.findall(rel):
            kind = 'world' if re.fullmatch(r'dlc\d{2}x', token) else 'child'
            add_entry(entries, parent, token, kind, 'unknown', f'{path.name}:path_token')
        if p.stat().st_size < 2_000_000 and p.suffix.lower() in ('.xml','.txt','.csv','.json') or p.name.lower().endswith('.sc.xml'):
            try: text = p.read_text(encoding='utf-8', errors='ignore')
            except Exception: continue
            for token in TOKEN_RE.findall(text):
                kind = 'world' if re.fullmatch(r'dlc\d{2}x', token) else 'child'
                add_entry(entries, parent, token, kind, 'unknown', f'{path.name}:text_token')


def merge_inventory_csv(path: Path, entries):
    with path.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get('sector') or row.get('name') or row.get('text') or ''
            parent = row.get('parent') or row.get('owner') or row.get('file') or 'wsc'
            call = (row.get('call') or row.get('type') or row.get('kind') or '').lower()
            state = 'enabled' if 'enable' in call else 'disabled' if 'disable' in call else row.get('state','unknown')
            kind = 'world' if 'world' in call else 'child' if 'child' in call else row.get('kind','unknown')
            if name:
                add_entry(entries, clean_parent_name(parent), name, kind, state, f'{path.name}:workbench_inventory')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('inputs', nargs='+', help='territory_swall zips/folders and optional sector_inventory.csv files')
    ap.add_argument('--out', default='sector_catalog_out', help='output folder')
    args = ap.parse_args()
    entries = {}
    for raw in args.inputs:
        p = Path(raw)
        if not p.exists():
            print(f'[warn] missing: {p}')
            continue
        if p.suffix.lower() == '.zip': scan_zip(p, entries)
        elif p.suffix.lower() == '.csv': merge_inventory_csv(p, entries)
        elif p.is_dir(): scan_directory(p, entries)
        else:
            scan_directory(p.parent, entries)
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    rows = sorted(entries.values(), key=lambda r:(r['parent'], r['kind'], r['name']))
    (out/'sector_catalog.json').write_text(json.dumps({'schema':'CodeRED.RemoteMenu.SectorCatalog.v1','sectors':rows}, indent=2), encoding='utf-8')
    with (out/'sector_catalog.csv').open('w', newline='', encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=['parent','name','kind','state','source']); w.writeheader(); w.writerows(rows)
    parents = {}
    for r in rows: parents.setdefault(r['parent'], 0); parents[r['parent']] += 1
    report = ['# Code RED Remote Menu Sector Catalog', '', f'Sectors: {len(rows)}', f'Parents: {len(parents)}', '', '## Parent counts']
    for k,v in sorted(parents.items()): report.append(f'- {k}: {v}')
    (out/'sector_catalog_report.md').write_text('\n'.join(report)+'\n', encoding='utf-8')
    print(f'wrote {out}')

if __name__ == '__main__': main()
