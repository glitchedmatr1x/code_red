#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import sys, json, shutil, hashlib, zipfile, re, importlib.util, time

for p in ('/usr/local/lib/python3.13/dist-packages', '/usr/lib/python3/dist-packages'):
    if p not in sys.path:
        sys.path.append(p)

BASE = Path(__file__).resolve().parents[1]
INPUT = BASE / 'inputs' / 'pass12'
SRC = BASE / 'sources'
TOOLS = BASE / 'tools'
OUT = BASE / 'output'
STAGES = OUT / 'stages'
FINAL_ZIP = OUT / 'CodeRED_Pass15_50_AllTowns_RivalGangs.zip'
CONTENT_PLACEMENT_IDX = 48
TUNE_LASSO_IDX = 1516
TUNE_BASE_LASSO_IDX = 1556
TUNE_SHERIFF_IDX = 84

PASS12_CONTENT_INDICES = {
    'root/content/ambient/factionrelations.xml': 47,
    'root/content/ai/game_main.tr': 10,
}
PASS12_TUNE_INDICES = {
    'root/tune/level/territory/level.pop': 341,
    'root/tune/settings/default.traffic': 1538,
    'root/tune/settings/ambientmgrtuning.xml': 1546,
    'root/tune/ai/game_main.tr': 29,
}
PASS12_MARKERS = [
    'CodeRed Wilderness Living World Events',
    'CodeRed Empty Country Trouble Events',
    'CodeRed Daily Rival Gang Showdown Events',
    'CodeRed Persistent Camps And War Debris',
]
PASS15_30_MARKERS = [
    'CodeRED Empty World Activity',
    'CodeRED Blackwater Chaos Main Roads',
    'tevent_rowdy_gangs',
    'tevent_lone_lawman',
    'beat_duel_notoriety',
    'event_law_repsonse_posse',
]

TOWN_HIGH_ALERT_EVENTS = [
    'tevent_lone_lawman',
    'event_law_report_crime',
    'event_law_repsonse_ai',
    'event_law_repsonse_local',
    'event_law_repsonse_posse',
    'event_law_repsonse_bounty',
    'event_law_repsonse_special',
    'event_law_repsonse_stickup',
    'event_law_repsonse_wild',
    'event_bountyhunter',
    'event_wanted_poster',
    'job_nightwatch',
]
TOWN_CRIME_EVENTS = [
    'beat_crime_holdup',
    'beat_crime_horsethief',
    'beat_crime_wagonthief',
    'beat_town_abduction',
    'beat_roadside_robbery',
    'event_criminal_chase',
    'beacon_transport_defend',
    'beacon_transport_simple',
    'event_broken_wagon01',
]
TOWN_DUEL_EVENTS = [
    'beat_duel_notoriety',
    'beat_duel_rude',
    'beat_duel_lowhonor',
    'first_time_duel',
    'event_generic_1v1',
]
RIVAL_GANG_EVENTS = [
    'tevent_rowdy_gangs',
    'tevent_bh_rowdy_gangs',
    'event_roadside_ambush',
    'beat_roadside_robbery',
    'event_criminal_chase',
    'beacon_transport_defend',
    'beacon_escort_criminals',
    'event_roadside_execution',
    'event_raodside_prisoners',
]
DOG_EVENTS = [
    'beat_dog_fetch',
]

ALL_TOWN_EVENTS = TOWN_HIGH_ALERT_EVENTS + TOWN_CRIME_EVENTS + TOWN_DUEL_EVENTS + DOG_EVENTS
ALL_NEW_MARKERS = [
    'CodeRED All Towns High Alert Roads',
    'CodeRED Town Crime Duel Robbery Pressure',
    'CodeRED Two Rival Gangs Near Towns',
    'CodeRED Town Guard Dog Patrols',
    'tevent_bh_rowdy_gangs',
    'beat_dog_fetch',
]

SCRIPT_SUPPORT_CONFIRMED = {
    'tevent_rowdy_gangs': 'root/content/release64/0xC06BF8AB/traffic/tevent_rowdy_gangs.wsc',
    'tevent_bh_rowdy_gangs': 'root/content/release64/0xC06BF8AB/traffic/tevent_bh_rowdy_gangs.wsc',
    'tevent_lone_lawman': 'root/content/release64/0xC06BF8AB/traffic/tevent_lone_lawman.wsc',
    'event_law_report_crime': 'root/content/release64/0xC06BF8AB/crimeresponse/event_law_report_crime.wsc',
    'event_law_repsonse_ai': 'root/content/release64/0xC06BF8AB/crimeresponse/event_law_repsonse_ai.wsc',
    'event_law_repsonse_local': 'root/content/release64/0xC06BF8AB/crimeresponse/event_law_repsonse_local.wsc',
    'event_law_repsonse_posse': 'root/content/release64/0xC06BF8AB/crimeresponse/event_law_repsonse_posse.wsc',
    'event_law_repsonse_bounty': 'root/content/release64/0xC06BF8AB/crimeresponse/event_law_repsonse_bounty.wsc',
    'event_law_repsonse_special': 'root/content/release64/0xC06BF8AB/crimeresponse/event_law_repsonse_special.wsc',
    'event_law_repsonse_stickup': 'root/content/release64/0xC06BF8AB/crimeresponse/event_law_repsonse_stickup.wsc',
    'event_law_repsonse_wild': 'root/content/release64/0xC06BF8AB/crimeresponse/event_law_repsonse_wild.wsc',
    'event_bountyhunter': 'root/content/release64/0xC06BF8AB/pointofinterest/event_bountyhunter.wsc',
    'event_wanted_poster': 'root/content/release64/0xC06BF8AB/pointofinterest/event_wanted_poster.wsc',
    'beat_crime_holdup': 'root/content/release64/0xC06BF8AB/town/beat_crime_holdup.wsc',
    'beat_crime_horsethief': 'root/content/release64/0xC06BF8AB/town/beat_crime_horsethief.wsc',
    'beat_crime_wagonthief': 'root/content/release64/0xC06BF8AB/town/beat_crime_wagonthief.wsc',
    'beat_town_abduction': 'root/content/release64/0xC06BF8AB/town/beat_town_abduction.wsc',
    'beat_duel_notoriety': 'root/content/release64/0xC06BF8AB/town/beat_duel_notoriety.wsc',
    'beat_duel_rude': 'root/content/release64/0xC06BF8AB/town/beat_duel_rude.wsc',
    'beat_duel_lowhonor': 'root/content/release64/0xC06BF8AB/town/beat_duel_lowhonor.wsc',
    'first_time_duel': 'root/content/release64/0xC06BF8AB/town/first_time_duel.wsc',
    'beat_dog_fetch': 'root/content/release64/0xC06BF8AB/town/beat_dog_fetch.wsc',
    'job_nightwatch': 'stringtable-supported; prior placement used this marker',
}
RESEARCH_ONLY = {
    'gatling_wagon': 'Only gatlingattachgringo.wsc found so far; no safe mounted-gun event vehicle controller confirmed in this pass.',
    'maxim_truck': 'No direct maxim/truck event hook confirmed in content/tune/string scans yet.',
    'radar_active_area': 'No safe field format for gang-raid radar/map active-area markers confirmed yet.',
    'weapon_distribution': 'NPC weapon-set ratio changes require a separate weapon-set pass; this pass keeps lasso tuning and event pressure only.',
}


def load_rpf():
    spec = importlib.util.spec_from_file_location('rpf_patch_utils', str(TOOLS / 'rpf_patch_utils.py'))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def copy_fast(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def read_idx(rpf, archive: Path, index: int) -> bytes:
    info = rpf.parse(archive, with_debug=False)
    ent = info['entries'][index]
    return rpf.extract(archive, ent)


def patch_idx(rpf, archive: Path, index: int, payload: bytes, label: str) -> dict:
    info = rpf.parse(archive, with_debug=False)
    ent = info['entries'][index]
    slot = rpf.read_slot(archive, ent)
    original = rpf.extract(archive, ent)
    if ent.get('is_resource'):
        raise NotImplementedError('resource entries are intentionally not patched by this builder')
    if ent.get('is_compressed'):
        coded, codec = rpf.compress_like(slot, payload)
        if rpf.extract_from_coded(coded, ent) != payload:
            raise AssertionError(f'{label}: pre-write compressed round-trip failed')
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
    reread_ent = rpf.parse(archive, with_debug=False)['entries'][index]
    reread_payload = rpf.extract(archive, reread_ent)
    if reread_payload != payload:
        raise AssertionError(f'{label}: post-write re-read mismatch')
    return {
        'label': label,
        'entry_index': index,
        'codec': codec,
        'relocated': relocated,
        'old_offset': ent['offset'],
        'new_offset': reread_ent['offset'],
        'original_payload_size': len(original),
        'new_payload_size': len(payload),
        'original_slot_size': len(slot),
        'new_slot_size': len(coded),
        'sha1': sha1_bytes(payload),
    }


def item_block(name: str, events: list[str], road_min='0.0', road_max='145.0', train_min='0.0', trail_min='0.0') -> str:
    seen=[]
    for event in events:
        if event not in seen:
            seen.append(event)
    lines = [
        '    <Item>',
        f'      <Name>{name}</Name>',
        f'      <DistanceRoadMin value="{road_min}"/>',
        f'      <DistanceRoadMax value="{road_max}"/>',
        f'      <DistanceTrainMin value="{train_min}"/>',
        f'      <DistanceHorseTrailMin value="{trail_min}"/>',
        '      <EventNames>',
    ]
    lines += [f'        <Name>{event}</Name>' for event in seen]
    lines += ['      </EventNames>', '    </Item>']
    return '\n'.join(lines)


def append_allow_item(xml: str, block: str) -> str:
    m = re.search(r'<Item>\s*<Name>([^<]+)</Name>', block, re.S)
    if m and f'<Name>{m.group(1)}</Name>' in xml:
        return xml
    pos = xml.find('</AllowEventSets>')
    if pos < 0:
        return xml + '\n' + block + '\n'
    return xml[:pos] + '\n' + block + '\n' + xml[pos:]


def add_names(xml: str, set_name: str, names: list[str]) -> str:
    start = xml.find(f'<Name>{set_name}</Name>')
    if start < 0:
        return xml
    end = xml.find('</EventNames>', start)
    if end < 0:
        return xml
    block = xml[start:end]
    additions = ''.join(f'        <Name>{n}</Name>\n' for n in names if f'<Name>{n}</Name>' not in block)
    return xml[:end] + additions + xml[end:] if additions else xml


def merge_all_towns(xml: str) -> str:
    out = xml
    for s in ['All Events', 'Roadside Events', 'Trailside Events']:
        out = add_names(out, s, ALL_TOWN_EVENTS + RIVAL_GANG_EVENTS)
    for s in ['CodeRed Daily Rival Gang Showdown Events', 'CodeRed Wilderness Living World Events', 'CodeRed Empty Country Trouble Events']:
        out = add_names(out, s, TOWN_HIGH_ALERT_EVENTS + RIVAL_GANG_EVENTS)
    out = append_allow_item(out, item_block('CodeRED All Towns High Alert Roads', TOWN_HIGH_ALERT_EVENTS + TOWN_DUEL_EVENTS, road_min='0.0', road_max='130.0'))
    out = append_allow_item(out, item_block('CodeRED Town Crime Duel Robbery Pressure', TOWN_CRIME_EVENTS + TOWN_DUEL_EVENTS, road_min='0.0', road_max='115.0'))
    out = append_allow_item(out, item_block('CodeRED Town Guard Dog Patrols', DOG_EVENTS + ['tevent_lone_lawman'], road_min='0.0', road_max='90.0'))
    return out


def merge_rival_gangs(xml: str) -> str:
    out = xml
    for s in ['All Events', 'Roadside Events', 'Trailside Events', 'CodeRed Daily Rival Gang Showdown Events', 'CodeRED Blackwater Chaos Main Roads']:
        out = add_names(out, s, RIVAL_GANG_EVENTS + TOWN_HIGH_ALERT_EVENTS)
    out = append_allow_item(out, item_block('CodeRED Two Rival Gangs Near Towns', RIVAL_GANG_EVENTS + TOWN_HIGH_ALERT_EVENTS + TOWN_CRIME_EVENTS, road_min='0.0', road_max='180.0'))
    return out


def stage(name: str) -> Path:
    d = STAGES / name
    (d / 'archives').mkdir(parents=True, exist_ok=True)
    (d / 'modified_xml').mkdir(parents=True, exist_ok=True)
    (d / 'modified_tune').mkdir(parents=True, exist_ok=True)
    (d / 'reports').mkdir(parents=True, exist_ok=True)
    return d


def copy_archives(src: Path, dst: Path) -> None:
    copy_fast(src / 'archives' / 'content.rpf', dst / 'archives' / 'content.rpf')
    copy_fast(src / 'archives' / 'tune_d11generic.rpf', dst / 'archives' / 'tune_d11generic.rpf')


def validate(rpf, d: Path, p12_report: dict, expect: list[str], require_pass15: bool=True, require_lasso: bool=True) -> dict:
    content = d / 'archives' / 'content.rpf'
    tune = d / 'archives' / 'tune_d11generic.rpf'
    placement = read_idx(rpf, content, CONTENT_PLACEMENT_IDX).decode('latin-1', 'ignore')
    p12_sha = {p['path']: p['sha1'] for p in p12_report['patches']}
    preserved = {}
    for path, idx in PASS12_CONTENT_INDICES.items():
        preserved[path] = sha1_bytes(read_idx(rpf, content, idx)) == p12_sha[path]
    for path, idx in PASS12_TUNE_INDICES.items():
        preserved[path] = sha1_bytes(read_idx(rpf, tune, idx)) == p12_sha[path]
    lasso = read_idx(rpf, tune, TUNE_LASSO_IDX).decode('latin-1', 'ignore')
    base_lasso = read_idx(rpf, tune, TUNE_BASE_LASSO_IDX).decode('latin-1', 'ignore')
    sheriff = read_idx(rpf, tune, TUNE_SHERIFF_IDX).decode('latin-1', 'ignore')
    checks = {
        'content_magic': content.open('rb').read(4) == b'RPF6',
        'tune_magic': tune.open('rb').read(4) == b'RPF6',
        'placement_item_balance': placement.count('<Item>') == placement.count('</Item>'),
        'pass12_markers': all(m in placement for m in PASS12_MARKERS),
        'pass15_30_markers': (not require_pass15) or all(m in placement for m in PASS15_30_MARKERS),
        'expected_new_markers': all(m in placement for m in expect),
        'pass12_nonplacement_preserved': all(preserved.values()),
        'lasso_15_30_still_applied': (not require_lasso) or (all(x in lasso for x in ['RopeLen\t\t18.000000', 'StretchStrength\t\t15000.000000']) and 'MaximumRange\t\t\t35.000000' in base_lasso and 'LassoBreakoutTime value="8.000000"' in sheriff),
    }
    return {
        'stage': d.name,
        'checks': checks,
        'pass12_nonplacement_preserved': preserved,
        'present_new_markers': {m: (m in placement) for m in expect},
        'script_support_confirmed': SCRIPT_SUPPORT_CONFIRMED,
        'research_only_not_forced': RESEARCH_ONLY,
        'placement_size': len(placement),
        'all_ok': all(checks.values()),
    }


def write_report(d: Path, patches: list[dict], validation: dict, note: str) -> None:
    (d / 'reports' / f'{d.name}_report.json').write_text(json.dumps({
        'stage': d.name,
        'note': note,
        'patches': patches,
        'validation': validation,
    }, indent=2), encoding='utf-8')


def package(final: Path, validations: list[dict], patches: list[dict]) -> None:
    manifest = {
        'pass': '15.50',
        'title': 'All Towns Active + Nearby Rival Gang Pressure',
        'base': 'Pass12 cumulative base rebuilt with Pass15.30 lasso/Blackwater layers, then 15.40/15.50 town pressure',
        'validated_stages': validations,
        'patches': patches,
        'content_sha256': sha256_file(final / 'archives/content.rpf'),
        'tune_sha256': sha256_file(final / 'archives/tune_d11generic.rpf'),
    }
    (OUT / 'PASS15_50_MANIFEST.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (OUT / 'README_INSTALL.txt').write_text('''Code RED Pass 15.50 - All Towns + Rival Gangs\n=================================================\n\nInstall:\n1. Back up your current content.rpf and tune_d11generic.rpf.\n2. Replace content.rpf with archives/content.rpf.\n3. Replace tune_d11generic.rpf with archives/tune_d11generic.rpf.\n4. Test one in-game day around Blackwater, Armadillo, Thieves Landing, Chuparosa, Escalera, Manzanita, and Rathskeller/Fork-style town areas.\n\nThis is cumulative from Pass 12. It preserves Pass 12 payloads, Pass 13 empty-world activity, Pass 14/15.30 Blackwater + lasso tuning, then adds all-town law/crime/duel/gang pressure and town dog patrol event pressure.\n''', encoding='utf-8')
    (OUT / 'PASS15_50_REPORT.txt').write_text('''Code RED Pass 15.50 Report\n===========================\n\nCompleted gates:\n- 15.00 Pass 12 preserved.\n- 15.30 Blackwater/lasso cumulative source applied.\n- 15.40 All towns high-alert/crime/duel/dog pressure added.\n- 15.50 Two-rival-gang-near-town pressure added.\n\nIncluded event pressure:\n- local law, posse, bounty, special law, wild law, lone lawman\n- rowdy gangs and bounty-hunter rowdy gangs\n- holdup, horse thief, wagon thief, abduction, road robbery\n- duel notoriety, rude, low honor, first-time duel, generic 1v1\n- dog fetch / town dog patrol pressure\n\nNot forced yet:\n- direct NPC weapon-set ratio edits\n- gatling wagon / Maxim truck assault spawns\n- radar/map active-area markers\n\nThose are held for later passes because this run found only gatlingattachgringo, no safe truck/maxim event controller, and no confirmed active-area marker field format yet.\n''', encoding='utf-8')
    with zipfile.ZipFile(FINAL_ZIP, 'w', zipfile.ZIP_STORED) as z:
        z.write(final / 'archives/content.rpf', 'archives/content.rpf')
        z.write(final / 'archives/tune_d11generic.rpf', 'archives/tune_d11generic.rpf')
        z.write(OUT / 'README_INSTALL.txt', 'README_INSTALL.txt')
        z.write(OUT / 'PASS15_50_REPORT.txt', 'PASS15_50_REPORT.txt')
        z.write(OUT / 'PASS15_50_MANIFEST.json', 'manifests/PASS15_50_MANIFEST.json')
        for p in sorted((final / 'modified_xml').glob('*')):
            z.write(p, f'modified_xml/{p.name}')
        for p in sorted((final / 'modified_tune').glob('*')):
            z.write(p, f'modified_tune/{p.name}')
        for p in sorted((final / 'reports').glob('*')):
            z.write(p, f'reports/{p.name}')
        z.write(Path(__file__), 'builders/build_codered_pass15_50_from_pass12.py')
        z.write(TOOLS / 'rpf_patch_utils.py', 'tools/rpf_patch_utils.py')
    with zipfile.ZipFile(FINAL_ZIP) as z:
        bad = z.testzip()
        if bad:
            raise RuntimeError(f'bad zip member: {bad}')


def main() -> None:
    t0 = time.time()
    rpf = load_rpf()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    p12_report = json.loads((SRC / 'PATCH_REPORT_PASS12.json').read_text(encoding='utf-8'))
    validations = []
    all_patches = []

    s00 = stage('15_00_pass12_base')
    copy_fast(INPUT / 'content.rpf', s00 / 'archives/content.rpf')
    copy_fast(INPUT / 'tune_d11generic.rpf', s00 / 'archives/tune_d11generic.rpf')
    v00 = validate(rpf, s00, p12_report, [], require_pass15=False, require_lasso=False)
    validations.append(v00)
    write_report(s00, [], v00, 'Exact Pass 12 archive base copied before cumulative overlays.')
    if not v00['all_ok']:
        raise RuntimeError('15.00 validation failed')

    s30 = stage('15_30_cumulative_blackwater_lasso')
    copy_archives(s00, s30)
    p30 = []
    p30.append(patch_idx(rpf, s30 / 'archives/content.rpf', CONTENT_PLACEMENT_IDX, (SRC / 'placementglobals_pass15_30_merged.xml').read_bytes(), 'placementglobals pass15.30 cumulative merge'))
    for idx, name, label in [
        (TUNE_LASSO_IDX, 'lasso_pass15.tune', 'lasso tune pass15.30'),
        (TUNE_BASE_LASSO_IDX, 'base_lasso_pass15.weap', 'base_lasso weapon pass15.30'),
        (TUNE_SHERIFF_IDX, 'sheriff_pass15.xml', 'sheriff lasso AI pass15.30'),
    ]:
        p30.append(patch_idx(rpf, s30 / 'archives/tune_d11generic.rpf', idx, (SRC / name).read_bytes(), label))
    (s30 / 'modified_xml/placementglobals_15_30_cumulative.xml').write_bytes((SRC / 'placementglobals_pass15_30_merged.xml').read_bytes())
    for name in ['lasso_pass15.tune', 'base_lasso_pass15.weap', 'sheriff_pass15.xml']:
        shutil.copyfile(SRC / name, s30 / 'modified_tune' / name)
    v30 = validate(rpf, s30, p12_report, [])
    validations.append(v30)
    all_patches += p30
    write_report(s30, p30, v30, 'Pass 15.30 cumulative Blackwater/lasso source applied onto Pass 12.')
    if not v30['all_ok']:
        raise RuntimeError('15.30 validation failed')

    s40 = stage('15_40_all_towns_active')
    copy_archives(s30, s40)
    xml40 = merge_all_towns(read_idx(rpf, s40 / 'archives/content.rpf', CONTENT_PLACEMENT_IDX).decode('latin-1', 'ignore'))
    (s40 / 'modified_xml/placementglobals_15_40_all_towns.xml').write_text(xml40, encoding='latin-1')
    p40 = [patch_idx(rpf, s40 / 'archives/content.rpf', CONTENT_PLACEMENT_IDX, xml40.encode('latin-1'), 'placementglobals 15.40 all towns active')]
    v40 = validate(rpf, s40, p12_report, ['CodeRED All Towns High Alert Roads', 'CodeRED Town Crime Duel Robbery Pressure', 'CodeRED Town Guard Dog Patrols'])
    validations.append(v40)
    all_patches += p40
    write_report(s40, p40, v40, 'All-town high-alert law/crime/duel/dog event pressure added.')
    if not v40['all_ok']:
        raise RuntimeError('15.40 validation failed')

    s50 = stage('15_50_rival_gang_towns')
    copy_archives(s40, s50)
    xml50 = merge_rival_gangs(read_idx(rpf, s50 / 'archives/content.rpf', CONTENT_PLACEMENT_IDX).decode('latin-1', 'ignore'))
    (s50 / 'modified_xml/placementglobals_15_50_rival_gang_towns.xml').write_text(xml50, encoding='latin-1')
    p50 = [patch_idx(rpf, s50 / 'archives/content.rpf', CONTENT_PLACEMENT_IDX, xml50.encode('latin-1'), 'placementglobals 15.50 rival gangs near towns')]
    v50 = validate(rpf, s50, p12_report, ALL_NEW_MARKERS)
    validations.append(v50)
    all_patches += p50
    write_report(s50, p50, v50, 'Two-rival-gang-near-town event pressure added on top of all-town activity.')
    if not v50['all_ok']:
        raise RuntimeError('15.50 validation failed')

    package(s50, validations, all_patches)
    print(json.dumps({'ok': True, 'output_zip': str(FINAL_ZIP), 'seconds': round(time.time() - t0, 2), 'final_validation': v50}, indent=2))

if __name__ == '__main__':
    main()
