#!/usr/bin/env python3
from __future__ import annotations

# Code RED Pass 15.30 cumulative RPF builder.
# Standalone package layout expected:
#   inputs/pass12/content.rpf
#   inputs/pass12/tune_d11generic.rpf
#   sources/placement_pass13_empty_world.xml
#   sources/placement_pass14_blackwater_chaos.xml
#   sources/lasso_pass14.tune
#   sources/base_lasso_pass14.weap
#   sources/sheriff_pass14.xml
#   tools/rpf_patch_utils.py
# Run with: python -S builders/build_codered_pass15_30_from_pass12.py

from pathlib import Path
import sys, shutil, json, hashlib, re, zipfile, importlib.util, time

for p in ('/usr/local/lib/python3.13/dist-packages', '/usr/lib/python3/dist-packages'):
    if p not in sys.path:
        sys.path.append(p)

BASE = Path(__file__).resolve().parents[1]
INPUT = BASE / 'inputs' / 'pass12'
SRC = BASE / 'sources'
TOOLS = BASE / 'tools'
OUT = BASE / 'output'
STAGES = OUT / 'stages'
FINAL_ZIP = OUT / 'CodeRED_Pass15_30_rebuilt_from_builder.zip'
CONTENT_PLACEMENT = 'root/content/ambient/placementglobals.xml'

PASS12_PAYLOADS = [
    'root/content/ambient/placementglobals.xml',
    'root/content/ambient/factionrelations.xml',
    'root/content/ai/game_main.tr',
    'root/tune/level/territory/level.pop',
    'root/tune/settings/default.traffic',
    'root/tune/settings/ambientmgrtuning.xml',
    'root/tune/ai/game_main.tr',
]
PASS12_MARKERS = [
    'CodeRed Wilderness Living World Events',
    'CodeRed Empty Country Trouble Events',
    'CodeRed Daily Rival Gang Showdown Events',
    'CodeRed Persistent Camps And War Debris',
]
PASS13_MARKERS = ['CodeRED Empty World Activity', 'beacon_transport_defend', 'event_broken_wagon01', 'event_criminal_chase']
EMPTY_WORLD_EVENTS = [
    'beacon_transport_defend', 'beacon_transport_simple', 'event_gnrc_rescue_beacon',
    'beacon_escort_criminals', 'beat_crime_wagonthief', 'event_broken_wagon01',
    'event_campfire01', 'event_criminal_chase', 'event_coyote_chase', 'event_loot_dead_body',
    'event_wild_animals', 'event_lone_stranger', 'event_hanging', 'event_landmark_attack',
    'tevent_rowdy_gangs', 'tevent_lone_lawman',
]
BLACKWATER_EVENTS = [
    'tevent_rowdy_gangs', 'tevent_lone_lawman', 'event_law_report_crime', 'event_law_repsonse_ai',
    'event_law_repsonse_local', 'event_law_repsonse_posse', 'event_law_repsonse_bounty',
    'event_law_repsonse_special', 'event_law_repsonse_stickup', 'job_nightwatch', 'event_bountyhunter',
    'event_wanted_poster', 'beat_crime_holdup', 'beat_crime_horsethief', 'beat_town_abduction',
    'beat_duel_notoriety', 'beat_duel_rude', 'beat_duel_lowhonor', 'first_time_duel', 'event_generic_1v1',
]
PASS14_MARKERS = ['CodeRED Blackwater Chaos Main Roads'] + BLACKWATER_EVENTS

PATH_INDEX_CACHE = {}

def resolve_index(rpf, archive: Path, internal: str) -> int:
    key = (str(archive.resolve()), internal.lower())
    if key in PATH_INDEX_CACHE:
        return PATH_INDEX_CACHE[key]
    info = rpf.parse(archive, with_debug=True)
    ent = rpf.find_entry(info, internal)
    if ent is None:
        raise KeyError(internal)
    PATH_INDEX_CACHE[key] = ent['index']
    return ent['index']

def load_rpf():
    util = TOOLS / 'rpf_patch_utils.py'
    spec = importlib.util.spec_from_file_location('rpf_patch_utils', str(util))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod

def sha1_bytes(b: bytes) -> str:
    return hashlib.sha1(b).hexdigest()

def copy_fast(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + '.tmp')
    with src.open('rb') as fsrc, tmp.open('wb') as fdst:
        for chunk in iter(lambda: fsrc.read(1024 * 1024), b''):
            fdst.write(chunk)
    if dst.exists():
        dst.unlink()
    tmp.replace(dst)

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def read_text(rpf, archive: Path, internal: str) -> str:
    idx = resolve_index(rpf, archive, internal)
    info = rpf.parse(archive, with_debug=False)
    ent = info['entries'][idx]
    return rpf.extract(archive, ent).decode('latin-1', 'ignore')

def patch_debug_path(rpf, archive: Path, internal: str, payload: bytes) -> dict:
    idx = resolve_index(rpf, archive, internal)
    info = rpf.parse(archive, with_debug=False)
    ent = info['entries'][idx]
    slot = rpf.read_slot(archive, ent)
    original = rpf.extract(archive, ent)
    if ent.get('is_resource'):
        raise NotImplementedError('resource entries intentionally disabled here')
    if ent.get('is_compressed'):
        coded, codec = rpf.compress_like(slot, payload)
        if rpf.extract_from_coded(coded, ent) != payload:
            raise AssertionError('pre-write compressed round-trip failed')
    else:
        coded, codec = payload, 'plain'
    relocated = len(coded) > ent['size_in_archive']
    if relocated:
        new_off = rpf.append_payload(archive, coded)
        rpf.update_metadata(archive, info, ent, new_size_in_archive=len(coded), new_total_size=len(payload), new_offset=new_off)
    else:
        with archive.open('r+b') as f:
            f.seek(ent['offset'])
            f.write(coded)
            if len(coded) < ent['size_in_archive']:
                f.write(b'\x00' * (ent['size_in_archive'] - len(coded)))
        rpf.update_metadata(archive, info, ent, new_size_in_archive=len(coded), new_total_size=len(payload))
    reread = rpf.parse(archive, with_debug=False)['entries'][idx]
    if rpf.extract(archive, reread) != payload:
        raise AssertionError('post-write re-read mismatch')
    return {
        'path': internal, 'entry_index': idx, 'codec': codec, 'relocated': relocated,
        'old_offset': ent['offset'], 'new_offset': reread['offset'],
        'original_payload_size': len(original), 'new_payload_size': len(payload),
        'original_slot_size': len(slot), 'new_slot_size': len(coded), 'sha1': sha1_bytes(payload),
    }

def item_block(xml: str, name: str) -> str | None:
    m = re.search(r'(?s)(\t*<Item>\s*<Name>' + re.escape(name) + r'</Name>.*?</Item>)', xml)
    return m.group(1) if m else None

def event_names(xml: str, name: str) -> list[str]:
    b = item_block(xml, name)
    if not b: return []
    names = re.findall(r'<Name>([^<]+)</Name>', b)
    return names[1:]

def add_names(xml: str, set_name: str, names: list[str]) -> str:
    start = xml.find(f'<Name>{set_name}</Name>')
    if start < 0: return xml
    end = xml.find('</EventNames>', start)
    if end < 0: return xml
    block = xml[start:end]
    add = ''.join(f'\t\t\t\t<Name>{n}</Name>\n' for n in names if f'<Name>{n}</Name>' not in block)
    return xml[:end] + add + xml[end:] if add else xml

def append_allow_item(xml: str, block: str) -> str:
    m = re.search(r'<Item>\s*<Name>([^<]+)</Name>', block, re.S)
    if m and f'<Name>{m.group(1)}</Name>' in xml:
        return xml
    pos = xml.find('</AllowEventSets>')
    if pos < 0: return xml + '\n' + block + '\n'
    if not block.startswith('\n'): block = '\n' + block
    if not block.endswith('\n'): block += '\n'
    return xml[:pos] + block + xml[pos:]

def fallback_empty_item() -> str:
    lines = ['\t\t<Item>', '\t\t\t<Name>CodeRED Empty World Activity</Name>', '      <DistanceRoadMin value="12.0"/>', '      <DistanceRoadMax value="260.0"/>', '      <DistanceTrainMin value="12.0"/>', '      <DistanceHorseTrailMin value="6.0"/>', '      <EventNames>']
    lines += [f'\t\t\t\t<Name>{e}</Name>' for e in EMPTY_WORLD_EVENTS]
    lines += ['\t\t\t</EventNames>', '\t\t</Item>']
    return '\n'.join(lines)

def fallback_blackwater_item() -> str:
    lines = ['\t\t<Item>', '\t\t\t<Name>CodeRED Blackwater Chaos Main Roads</Name>', '      <DistanceRoadMin value="0.0"/>', '      <DistanceRoadMax value="95.0"/>', '      <DistanceTrainMin value="0.0"/>', '      <DistanceHorseTrailMin value="0.0"/>', '      <EventNames>']
    for e in BLACKWATER_EVENTS + ['beacon_transport_defend', 'beat_crime_wagonthief', 'event_roadside_ambush', 'beat_roadside_robbery', 'event_criminal_chase']:
        lines.append(f'\t\t\t\t<Name>{e}</Name>')
    lines += ['\t\t\t</EventNames>', '\t\t</Item>']
    return '\n'.join(lines)

def merge_empty(base: str, p13: str) -> str:
    out = base
    for s in ['All Events', 'Roadside Events', 'Trailside Events', 'Wilderness Normal (30-60m from any road/train/path)', 'Wilderness Isolated (60m from any road/train/path)']:
        out = add_names(out, s, event_names(p13, s) or EMPTY_WORLD_EVENTS)
    for s in ['CodeRed Wilderness Living World Events', 'CodeRed Empty Country Trouble Events', 'CodeRed Persistent Camps And War Debris']:
        out = add_names(out, s, EMPTY_WORLD_EVENTS)
    return append_allow_item(out, item_block(p13, 'CodeRED Empty World Activity') or fallback_empty_item())

def merge_blackwater(base: str, p14: str) -> str:
    out = base
    for s in ['All Events', 'Roadside Events', 'Trailside Events']:
        out = add_names(out, s, event_names(p14, s) or BLACKWATER_EVENTS)
        out = add_names(out, s, BLACKWATER_EVENTS)
    for s in ['CodeRed Daily Rival Gang Showdown Events', 'CodeRed Thieves Landing Chaos Events', 'CodeRed Rail Corridor Robbery Events', 'CodeRed Thieves Landing Posse Robbery Events']:
        out = add_names(out, s, BLACKWATER_EVENTS + ['beacon_transport_defend', 'beat_crime_wagonthief', 'event_criminal_chase'])
    for s in ['CodeRed Wilderness Living World Events', 'CodeRed Empty Country Trouble Events', 'CodeRed Persistent Camps And War Debris']:
        out = add_names(out, s, ['tevent_rowdy_gangs', 'tevent_lone_lawman', 'event_law_repsonse_posse', 'event_law_repsonse_bounty', 'event_bountyhunter'])
    return append_allow_item(out, item_block(p14, 'CodeRED Blackwater Chaos Main Roads') or fallback_blackwater_item())

def stage(name: str) -> Path:
    d = STAGES / name
    (d / 'archives').mkdir(parents=True, exist_ok=True)
    (d / 'modified_xml').mkdir(exist_ok=True)
    (d / 'modified_tune').mkdir(exist_ok=True)
    (d / 'reports').mkdir(exist_ok=True)
    return d

def copy_archives(src: Path, dst: Path) -> None:
    copy_fast(src / 'archives' / 'content.rpf', dst / 'archives' / 'content.rpf')
    copy_fast(src / 'archives' / 'tune_d11generic.rpf', dst / 'archives' / 'tune_d11generic.rpf')

def validate(rpf, d: Path, expected: dict, p12_report: dict) -> dict:
    content = d / 'archives' / 'content.rpf'
    tune = d / 'archives' / 'tune_d11generic.rpf'
    placement = read_text(rpf, content, CONTENT_PLACEMENT)
    v = {
        'stage': d.name,
        'content_magic': content.open('rb').read(4).decode('ascii', 'ignore'),
        'tune_magic': tune.open('rb').read(4).decode('ascii', 'ignore'),
        'placement_item_balance': placement.count('<Item>') - placement.count('</Item>'),
        'pass12_markers': {m: m in placement for m in PASS12_MARKERS},
    }
    p12_sha = {p['path']: p['sha1'] for p in p12_report['patches']}
    preserved = {}
    for internal in PASS12_PAYLOADS:
        if internal == CONTENT_PLACEMENT: continue
        archive = content if internal.startswith('root/content/') else tune
        preserved[internal] = sha1_bytes(read_text(rpf, archive, internal).encode('latin-1')) == p12_sha[internal]
    v['pass12_nonplacement_preserved'] = preserved
    if expected.get('empty'): v['empty_world_markers'] = {m: m in placement for m in PASS13_MARKERS}
    if expected.get('blackwater'): v['blackwater_markers'] = {m: m in placement for m in PASS14_MARKERS}
    if expected.get('lasso'):
        lasso = read_text(rpf, tune, 'root/tune/settings/lasso.tune')
        base_lasso = read_text(rpf, tune, 'root/tune/settings/weapons/base_lasso.weap')
        sheriff = read_text(rpf, tune, 'root/tune/asd/sheriff.xml')
        v['lasso_checks'] = {
            'rope_len_18': '18.000000' in lasso,
            'stretch_strength_15000': 'StretchStrength' in lasso and '15000.000000' in lasso,
            'max_range_35': 'MaximumRange' in base_lasso and '35.000000' in base_lasso,
            'desired_range_18': 'DesiredRange' in base_lasso and '18.000000' in base_lasso,
            'sheriff_hold_80': '80.000000' in sheriff,
            'fast_draw_0_2': '0.200000' in sheriff,
        }
    checks = [v['content_magic']=='RPF6', v['tune_magic']=='RPF6', v['placement_item_balance']==0]
    checks += list(v['pass12_markers'].values()) + list(v['pass12_nonplacement_preserved'].values())
    for key in ('empty_world_markers','blackwater_markers','lasso_checks'):
        if key in v: checks += list(v[key].values())
    v['all_ok'] = all(checks)
    return v

def write_report(d: Path, patches: list[dict], validation: dict, note: str) -> None:
    data = {'stage': d.name, 'note': note, 'patches': patches, 'validation': validation}
    (d / 'reports' / f'{d.name}_report.json').write_text(json.dumps(data, indent=2), encoding='utf-8')

def package(final: Path, validations: list[dict]) -> None:
    manifest = {'final_stage': final.name, 'validations': validations, 'content_sha256': sha256_file(final/'archives/content.rpf'), 'tune_sha256': sha256_file(final/'archives/tune_d11generic.rpf')}
    (OUT / 'PASS15_30_BUILDER_MANIFEST.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    with zipfile.ZipFile(FINAL_ZIP, 'w', zipfile.ZIP_STORED) as z:
        z.write(final/'archives/content.rpf', 'archives/content.rpf')
        z.write(final/'archives/tune_d11generic.rpf', 'archives/tune_d11generic.rpf')
        z.write(OUT/'PASS15_30_BUILDER_MANIFEST.json', 'PASS15_30_BUILDER_MANIFEST.json')
        for p in sorted((final/'modified_xml').glob('*')): z.write(p, f'modified_xml/{p.name}')
        for p in sorted((final/'modified_tune').glob('*')): z.write(p, f'modified_tune/{p.name}')
        for p in sorted((final/'reports').glob('*')): z.write(p, f'reports/{p.name}')
    with zipfile.ZipFile(FINAL_ZIP, 'r') as z:
        bad = z.testzip()
        if bad: raise RuntimeError(f'bad zip member: {bad}')

def main() -> None:
    t0 = time.time()
    print("[start] loading rpf utils", flush=True)
    rpf = load_rpf()
    print("[start] loaded", flush=True)
    if OUT.exists(): shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    p12_report = json.loads((SRC/'PATCH_REPORT_PASS12.json').read_text(encoding='utf-8'))
    validations = []

    print("[15.00] base", flush=True)
    s00 = stage('15_00_pass12_base')
    print('[15.00] copy content', flush=True)
    copy_fast(INPUT/'content.rpf', s00/'archives/content.rpf')
    print('[15.00] copy tune', flush=True)
    copy_fast(INPUT/'tune_d11generic.rpf', s00/'archives/tune_d11generic.rpf')
    print('[15.00] validate', flush=True)
    v00 = validate(rpf, s00, {}, p12_report); validations.append(v00); print('[15.00] write report', flush=True)
    write_report(s00, [], v00, 'Exact Pass 12 base copied.')
    print('[15.00] ok?', v00.get('all_ok'), flush=True)
    if not v00['all_ok']: raise RuntimeError('15.00 failed')

    print("[15.10] empty world", flush=True)
    s10 = stage('15_10_empty_world')
    copy_archives(s00, s10)
    xml10 = merge_empty(read_text(rpf, s10/'archives/content.rpf', CONTENT_PLACEMENT), (SRC/'placement_pass13_empty_world.xml').read_text(encoding='latin-1'))
    (s10/'modified_xml/placementglobals_15_10_empty_world.xml').write_text(xml10, encoding='latin-1')
    p10 = [patch_debug_path(rpf, s10/'archives/content.rpf', CONTENT_PLACEMENT, xml10.encode('latin-1'))]
    v10 = validate(rpf, s10, {'empty': True}, p12_report); validations.append(v10); write_report(s10, p10, v10, 'Pass 13 empty-world placement layered onto Pass 12.')
    if not v10['all_ok']: raise RuntimeError('15.10 failed')

    print("[15.20] blackwater", flush=True)
    s20 = stage('15_20_blackwater_chaos')
    copy_archives(s10, s20)
    xml20 = merge_blackwater(read_text(rpf, s20/'archives/content.rpf', CONTENT_PLACEMENT), (SRC/'placement_pass14_blackwater_chaos.xml').read_text(encoding='latin-1'))
    (s20/'modified_xml/placementglobals_15_20_blackwater_chaos.xml').write_text(xml20, encoding='latin-1')
    p20 = [patch_debug_path(rpf, s20/'archives/content.rpf', CONTENT_PLACEMENT, xml20.encode('latin-1'))]
    v20 = validate(rpf, s20, {'empty': True, 'blackwater': True}, p12_report); validations.append(v20); write_report(s20, p20, v20, 'Pass 14 Blackwater chaos layered onto cumulative placement.')
    if not v20['all_ok']: raise RuntimeError('15.20 failed')

    print("[15.30] lasso", flush=True)
    s30 = stage('15_30_lasso_tuning')
    copy_archives(s20, s30)
    p30 = []
    for internal, src_name in {
        'root/tune/settings/lasso.tune': 'lasso_pass14.tune',
        'root/tune/settings/weapons/base_lasso.weap': 'base_lasso_pass14.weap',
        'root/tune/asd/sheriff.xml': 'sheriff_pass14.xml',
    }.items():
        payload = (SRC/src_name).read_bytes()
        (s30/'modified_tune'/src_name.replace('pass14','pass15_30')).write_bytes(payload)
        p30.append(patch_debug_path(rpf, s30/'archives/tune_d11generic.rpf', internal, payload))
    v30 = validate(rpf, s30, {'empty': True, 'blackwater': True, 'lasso': True}, p12_report); validations.append(v30); write_report(s30, p30, v30, 'Pass 14 lasso/sheriff tuning layered onto cumulative tune archive.')
    if not v30['all_ok']: raise RuntimeError('15.30 failed')

    print("[package]", flush=True)
    package(s30, validations)
    print(json.dumps({'ok': True, 'output_zip': str(FINAL_ZIP), 'seconds': round(time.time()-t0, 2), 'final_validation': v30}, indent=2))

if __name__ == '__main__':
    main()
