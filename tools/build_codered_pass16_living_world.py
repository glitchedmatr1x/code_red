#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import codered_rpf_utils as rpf

CONTENT_PLACEMENT = 'root/content/ambient/placementglobals.xml'
TUNE_FILES = {
    'ambient': 'root/tune/settings/ambientmgrtuning.xml',
    'alloc': 'root/tune/settings/componentallocations.xml',
    'level_pop': 'root/tune/level/territory/level.pop',
    'lasso': 'root/tune/settings/lasso.tune',
    'base_lasso': 'root/tune/settings/weapons/base_lasso.weap',
    'sheriff': 'root/tune/asd/sheriff.xml',
    'npc': 'root/tune/asd/npc.xml',
    'dog': 'root/tune/template/template_base_domesticated_dog.xml',
    'human': 'root/tune/template/template_base_human.xml',
}

MARKER = 'CodeRED Pass16 Living World Working Mod'

LIVING_WORLD_EVENTS = [
    'event_roadside_ambush',
    'beat_roadside_robbery',
    'beat_crime_wagonthief',
    'event_stickup',
    'event_criminal_chase',
    'event_hanging',
    'event_night_procession',
    'event_landmark_attack',
    'mexican_rev_rebelCamp',
    'event_broken_wagon01',
    'event_campfire01',
    'event_loot_dead_body',
    'event_wild_animals',
]


def decode(data: bytes) -> str:
    return data.decode('utf-8-sig', errors='replace')


def encode(text: str) -> bytes:
    return text.encode('utf-8')


def xml_check(text: str, label: str) -> None:
    try:
        ET.fromstring(text)
    except Exception as exc:
        raise RuntimeError(f'{label} XML parse failed: {exc}')


def brace_balance(text: str) -> int:
    return text.count('{') - text.count('}')


def replace_xml_value(text: str, tag: str, value: str) -> str:
    pat = rf'(<{re.escape(tag)}\s+value=")[^"]+("\s*/>)'
    text2, count = re.subn(pat, rf'\g<1>{value}\g<2>', text, count=1)
    if count != 1:
        raise RuntimeError(f'Could not replace XML value tag: {tag}')
    return text2


def patch_component_allocations(text: str) -> str:
    targets = {
        'Mind': 130,
        'AIObstacle': 40,
        'Animator': 130,
        'Behavior': 130,
        'BehaviorAnimal': 130,
        'Ear': 130,
        'Entity': 130,
        'Eye': 130,
        'Health': 130,
        'Inventory': 130,
        'MoverSim': 130,
        'Net': 130,
        'Creature': 130,
        'Target': 130,
        'Vehicle': 32,
        'CreatureAudio': 130,
        'VehicleAudio': 32,
        'VehicleAnimator': 24,
        'DraftVehicle': 16,
        'Motives': 130,
        'Capabilities': 130,
        'Horse': 48,
        'QuadIK': 48,
        'BipedIK': 130,
        'SecondaryMotion': 4,
    }
    for name, value in targets.items():
        pat = rf'(<mp_ResourceName content="ascii">{re.escape(name)}</mp_ResourceName>\s*\r?\n\s*<iAllocCount value=")[^"]+("/>)'
        text, count = re.subn(pat, rf'\g<1>{value}\g<2>', text, count=1)
        if count != 1:
            raise RuntimeError(f'Could not patch allocation for {name}')
    if MARKER not in text:
        text = text.replace('<sagActorResourceUseFile>', f'<sagActorResourceUseFile>\n\t<!-- {MARKER}: resource headroom for recurring faction pressure -->', 1)
    xml_check(text, 'componentallocations.xml')
    return text


def add_events_to_allow_set(text: str, set_name: str, events: list[str]) -> str:
    item_pat = re.compile(r'(<Item>\s*<Name>' + re.escape(set_name) + r'</Name>.*?<EventNames>)(.*?)(\s*</EventNames>.*?</Item>)', re.S)
    m = item_pat.search(text)
    if not m:
        raise RuntimeError(f'Allow set not found: {set_name}')
    body = m.group(2)
    existing = set(re.findall(r'<Name>(.*?)</Name>', body))
    additions = ''.join(f'\n\t\t\t\t<Name>{ev}</Name>' for ev in events if ev not in existing)
    if not additions:
        return text
    return text[:m.start(2)] + body + additions + text[m.end(2):]


def remove_deny_set(text: str, set_name: str) -> str:
    pat = re.compile(r'\s*<Item>\s*<Name>' + re.escape(set_name) + r'</Name>.*?</Item>', re.S)
    text2, count = pat.subn('', text, count=1)
    return text2


def patch_placementglobals(text: str) -> str:
    # Add more existing events into existing parent allow sets, instead of inventing unknown event scripts.
    for set_name in [
        'Roadside Events',
        'Trailside Events',
        'Wilderness Normal (30-60m from any road/train/path)',
        'Wilderness Isolated (60m from any road/train/path)',
    ]:
        text = add_events_to_allow_set(text, set_name, LIVING_WORLD_EVENTS)

    # Add a named support set for future tools; existing engine-used sets above are also patched.
    if 'CodeRED Pass16 Recurring Wilderness Anchors' not in text:
        block = '\n\t\t<Item>\n\t\t\t<Name>CodeRED Pass16 Recurring Wilderness Anchors</Name>\n\t\t\t<DistanceRoadMin value="10.0"/>\n\t\t\t<DistanceRoadMax value="90.0"/>\n\t\t\t<DistanceHorseTrailMin value="5.0"/>\n\t\t\t<EventNames>'
        block += ''.join(f'\n\t\t\t\t<Name>{ev}</Name>' for ev in LIVING_WORLD_EVENTS)
        block += '\n\t\t\t</EventNames>\n\t\t</Item>\n'
        text = text.replace('\n\t</AllowEventSets>', block + '\t</AllowEventSets>', 1)

    # Pass 15 lineage called this out: loosen pathfinding deny so wilderness pressure can actually trigger.
    text = remove_deny_set(text, 'Approach Events / Pathfinding issues')

    if MARKER not in text:
        text = text.replace('<PlacementData>', f'<PlacementData>\n\t<!-- {MARKER}: recurring wilderness/event pressure layer -->', 1)
    xml_check(text, 'placementglobals.xml')
    return text


def patch_ambient(text: str) -> str:
    replacements = {
        'MaxVisibleRange': '75.000000',
        'DespawnMaxCheckDistance': '35.000000',
        'DespawnNotVisibleTime': '12.000000',
        'MaxNumActorsTotal': '130',
        'NumActorsPreemptiveDestroy': '0',
        'SpawnExcludeTime': '1.500000',
        'CheckExcludeTime': '2.000000',
    }
    for tag, val in replacements.items():
        text = replace_xml_value(text, tag, val)
    if MARKER not in text:
        text = text.replace('<aiwAmbientManagerTuning>', f'<aiwAmbientManagerTuning>\n\t<!-- {MARKER}: keep more ambient actors alive/visible -->', 1)
    xml_check(text, 'ambientmgrtuning.xml')
    return text


def patch_density(text: str, condition: str, density: str) -> str:
    pat = re.compile(r'(Condition "' + re.escape(condition) + r'"\s*\{\s*Density\s+)([0-9.]+)', re.S)
    text2, count = pat.subn(rf'\g<1>{density}', text, count=1)
    if count != 1:
        raise RuntimeError(f'Could not patch density for {condition}')
    return text2


def patch_alt_probability(text: str, random_name: str, ref_name: str, value: int) -> str:
    block_pat = re.compile(r'(PedWithEquipmentRandom "' + re.escape(random_name) + r'"\s*\{.*?\n\s*\}\s*\n\s*\})', re.S)
    m = block_pat.search(text)
    if not m:
        raise RuntimeError(f'Random ped block not found: {random_name}')
    block = m.group(1)
    alt_pat = re.compile(r'(Alternative\s*\{\s*Probability\s+)(\d+)(\s*\r?\n\s*Ref "' + re.escape(ref_name) + r'"\s*\})', re.S)
    block2, count = alt_pat.subn(rf'\g<1>{value}\g<3>', block, count=1)
    if count != 1:
        raise RuntimeError(f'Could not patch {random_name} -> {ref_name}')
    return text[:m.start(1)] + block2 + text[m.end(1):]


def patch_ped_wilderness(text: str) -> str:
    # Replace the tiny horse/coyote-only wilderness set with a conservative mix of animals, law, and gangs.
    start = text.find('PedWithEquipmentRandom "ped_wilderness"')
    if start < 0:
        raise RuntimeError('Could not find ped_wilderness block start')
    end_marker = '\n\t\tPedWithEquipmentSpecific "ped_banker"'
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError('Could not find ped_wilderness block end marker')
    replacement = 'PedWithEquipmentRandom "ped_wilderness"\n\t\t{\n\t\t\tDefault\n\t\t\t{\n\t\t\t\tAlternative\n\t\t\t\t{\tProbability 18\n\t\t\t\t\tRef "ped_generic_horse"\n\t\t\t\t}\n\t\t\t\tAlternative\n\t\t\t\t{\tProbability 45\n\t\t\t\t\tRef "ped_coyote"\n\t\t\t\t}\n\t\t\t\tAlternative\n\t\t\t\t{\tProbability 8\n\t\t\t\t\tRef "ped_law_WesternDeputy"\n\t\t\t\t}\n\t\t\t\tAlternative\n\t\t\t\t{\tProbability 12\n\t\t\t\t\tRef "ped_outlaw_bully"\n\t\t\t\t}\n\t\t\t\tAlternative\n\t\t\t\t{\tProbability 10\n\t\t\t\t\tRef "ped_bandito_desperado"\n\t\t\t\t}\n\t\t\t\tAlternative\n\t\t\t\t{\tProbability 7\n\t\t\t\t\tRef "ped_bandito_pistolero"\n\t\t\t\t}\n\t\t\t}\n\t\t}'
    return text[:start] + replacement + text[end:]

def patch_level_pop(text: str) -> str:
    for cond, density in {
        'cond_Cholla_Springs': '0.004',
        'cond_Armadillo': '0.012',
        'cond_Hennigans_Ranch': '0.008',
        'cond_Tumbleweed': '0.003',
        'cond_Town_Border': '0.001',
        'cond_Fort_Mercer': '0.006',
        'cond_Ridgewood_Farm': '0.003',
        'cond_Twin_Rocks': '0.005',
    }.items():
        text = patch_density(text, cond, density)
    text = patch_alt_probability(text, 'ped_armadillo', 'ped_outlaw_bully', 10)
    text = patch_ped_wilderness(text)
    if MARKER not in text:
        text = text.replace('version 2\n{', f'version 2\n{{\n\t# {MARKER}: faction-aware wilderness population support', 1)
    if brace_balance(text) != 0:
        raise RuntimeError(f'level.pop brace balance failed: {brace_balance(text)}')
    return text


def patch_lasso(text: str) -> str:
    scalar = {
        'StretchStrength': '18000.000000',
        'StretchDamping': '350.000000',
        'AirFriction': '14.000000',
        'BendStrength': '180.000000',
        'BendDamping': '2.000000',
        'RopeLen': '16.000000',
    }
    for key, val in scalar.items():
        text, count = re.subn(rf'({re.escape(key)}\s+)[0-9.]+', rf'\g<1>{val}', text, count=1)
        if count != 1:
            raise RuntimeError(f'Could not patch lasso key: {key}')
    if MARKER not in text:
        text = text.replace('LassoTune\n{', f'LassoTune\n{{\n\t# {MARKER}: stronger recurring-world lasso support', 1)
    if brace_balance(text) != 0:
        raise RuntimeError('lasso.tune brace balance failed')
    return text


def patch_base_lasso(text: str) -> str:
    for key, val in {
        'MaximumRange': '32.000000',
        'DesiredRange': '16.000000',
        'MaximumDamageRange': '32.000000',
        'ShooterStandardRange': '28.000000',
        'HardLockRangeEnd': '55',
        'BumpTargetRangeEnd': '55',
    }.items():
        text, count = re.subn(rf'({re.escape(key)}\s+)[0-9.]+', rf'\g<1>{val}', text, count=1)
        if count < 1:
            raise RuntimeError(f'Could not patch base_lasso key: {key}')
    if MARKER not in text:
        text = text.replace('BASEWEAPON "base_lasso"\n{', f'BASEWEAPON "base_lasso"\n{{\n\t// {MARKER}: AI lasso range support', 1)
    if brace_balance(text) != 0:
        raise RuntimeError('base_lasso.weap brace balance failed')
    return text


def patch_asd(text: str, label: str) -> str:
    for tag, val in {
        'LassoBreakoutTime': '9.000000',
        'LassoBreakDamageThreshold': '45.000000',
        'MinMountedConstraintLen': '6.000000',
        'ProbeCapsulseRadius': '0.750000',
        'AttachRange': '6.500000',
        'FindMeleeTargetAlwaysIncludeRadius': '4.000000',
        'FindMeleeTargetFactionWeight': '0.350000',
    }.items():
        text = replace_xml_value(text, tag, val)
    if MARKER not in text:
        text = text.replace('<aniActionSetData>', f'<aniActionSetData>\n\t<!-- {MARKER}: {label} lasso/target support -->', 1)
    xml_check(text, label)
    return text


def patch_dog(text: str) -> str:
    for tag, val in {
        'm_ScoreBaseNeutral': '160.0',
        'm_ScoreBaseHostile': '1800.0',
    }.items():
        text = re.sub(rf'(<{re.escape(tag)} type="double" value=")[^"]+("/>)', rf'\g<1>{val}\g<2>', text, count=1)
    if MARKER not in text:
        text = text.replace('<actor name="template_base_domesticated_dog"', f'<!-- {MARKER}: guard dog target scoring support -->\n<actor name="template_base_domesticated_dog"', 1)
    xml_check(text, 'template_base_domesticated_dog.xml')
    return text


def patch_human(text: str) -> str:
    text = re.sub(r'(<m_LassoHardLockBias type="double" value=")[^"]+("/>)', r'\g<1>0.450\g<2>', text, count=1)
    if MARKER not in text:
        text = text.replace('<!DOCTYPE actor>', f'<!-- {MARKER}: lasso hard-lock target support -->\n<!DOCTYPE actor>', 1)
    xml_check(text, 'template_base_human.xml')
    return text


def patch_archive_text(archive_path: Path, internal_path: str, patch_fn, report: dict) -> None:
    info = rpf.parse(archive_path, with_debug=True)
    ent = rpf.find_entry(info, internal_path)
    if not ent:
        raise RuntimeError(f'Missing entry: {internal_path}')
    original = rpf.extract(archive_path, ent)
    original_text = decode(original)
    patched_text = patch_fn(original_text)
    if patched_text == original_text:
        report['patches'].append({'path': internal_path, 'status': 'unchanged'})
        return
    result = rpf.patch_entry(archive_path, internal_path, encode(patched_text))
    result['status'] = 'patched'
    report['patches'].append(result)


def build(content_src: Path, tune_src: Path, out_root: Path) -> dict:
    drop = out_root / 'DROP_IN_CodeRED_Pass16_LivingWorld_Working_Mod'
    reports = drop / 'reports'
    tools = drop / 'tools'
    for p in (reports, tools): p.mkdir(parents=True, exist_ok=True)
    content_out = drop / 'content.rpf'
    tune_out = drop / 'tune_d11generic.rpf'
    shutil.copy2(content_src, content_out)
    shutil.copy2(tune_src, tune_out)
    report = {
        'name': 'Code RED Pass 16 Living World Working Mod',
        'version': '16.0-working-package',
        'generated_utc': datetime.utcnow().isoformat(timespec='seconds') + 'Z',
        'inputs': {'content': str(content_src), 'tune': str(tune_src)},
        'outputs': {'content': str(content_out), 'tune': str(tune_out)},
        'patches': [],
        'validation': {},
    }

    patch_archive_text(content_out, CONTENT_PLACEMENT, patch_placementglobals, report)
    patch_archive_text(tune_out, TUNE_FILES['ambient'], patch_ambient, report)
    patch_archive_text(tune_out, TUNE_FILES['alloc'], patch_component_allocations, report)
    patch_archive_text(tune_out, TUNE_FILES['level_pop'], patch_level_pop, report)
    patch_archive_text(tune_out, TUNE_FILES['lasso'], patch_lasso, report)
    patch_archive_text(tune_out, TUNE_FILES['base_lasso'], patch_base_lasso, report)
    patch_archive_text(tune_out, TUNE_FILES['sheriff'], lambda t: patch_asd(t, 'sheriff.xml'), report)
    patch_archive_text(tune_out, TUNE_FILES['npc'], lambda t: patch_asd(t, 'npc.xml'), report)
    patch_archive_text(tune_out, TUNE_FILES['dog'], patch_dog, report)
    patch_archive_text(tune_out, TUNE_FILES['human'], patch_human, report)

    # Validation reopen and marker checks.
    ci = rpf.parse(content_out, with_debug=True)
    ti = rpf.parse(tune_out, with_debug=True)
    placement = decode(rpf.extract(content_out, rpf.find_entry(ci, CONTENT_PLACEMENT)))
    ambient = decode(rpf.extract(tune_out, rpf.find_entry(ti, TUNE_FILES['ambient'])))
    level_pop = decode(rpf.extract(tune_out, rpf.find_entry(ti, TUNE_FILES['level_pop'])))
    lasso = decode(rpf.extract(tune_out, rpf.find_entry(ti, TUNE_FILES['lasso'])))
    report['validation'] = {
        'content_rpf_reopens': True,
        'tune_rpf_reopens': True,
        'placement_xml_parses': True,
        'placement_marker_present': MARKER in placement,
        'recurring_anchor_set_present': 'CodeRED Pass16 Recurring Wilderness Anchors' in placement,
        'pathfinding_deny_loosened': 'Approach Events / Pathfinding issues' not in placement,
        'ambient_actor_cap_130': '<MaxNumActorsTotal value="130"/>' in ambient,
        'ambient_visible_range_75': '<MaxVisibleRange value="75.000000"/>' in ambient,
        'level_pop_brace_balance': brace_balance(level_pop),
        'wilderness_faction_mix_present': all(x in level_pop for x in ['ped_outlaw_bully','ped_bandito_desperado','ped_law_WesternDeputy']),
        'lasso_rope_len_16': 'RopeLen\t\t16.000000' in lasso or 'RopeLen 16.000000' in lasso,
        'all_required_checks_pass': False,
    }
    report['validation']['all_required_checks_pass'] = all(v is True or v == 0 for k,v in report['validation'].items() if k != 'all_required_checks_pass')

    (reports / 'pass16_living_world_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    lines = [
        'Code RED Pass 16 Living World Working Mod',
        '==========================================',
        '',
        'Drop-in files:',
        '- content.rpf',
        '- tune_d11generic.rpf',
        '',
        'What this builder patches:',
        '- placementglobals.xml recurring wilderness/road/trail event pressure using existing event names',
        '- ambient manager cap/range/despawn support, preserving the Pass 15 actor-cap target of 130',
        '- component allocation headroom for actors, horses, vehicles, targets, behavior, and audio',
        '- level.pop density and faction-aware wilderness mix',
        '- lasso/base_lasso/sheriff/npc/human/dog support tuning from the prior lasso/hogtie lane',
        '',
        'Validation:',
    ]
    for k,v in report['validation'].items():
        lines.append(f'- {k}: {v}')
    lines += [
        '',
        'Install:',
        '1. Back up your existing content.rpf and tune_d11generic.rpf.',
        '2. Copy this package content.rpf and tune_d11generic.rpf into your test game/mod folder only.',
        '3. Load a save. If changes do not show, reload save, then exit to title/menu, then restart game.',
        '',
        'Do not overwrite your clean source archives.',
    ]
    (drop / 'README_INSTALL_AND_TEST_PASS16.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    shutil.copy2(Path(__file__), tools / 'build_codered_pass16_living_world.py')
    shutil.copy2(SCRIPT_DIR / 'codered_rpf_utils.py', tools / 'codered_rpf_utils.py')
    return report


def zip_folder(folder: Path, zip_path: Path) -> None:
    if zip_path.exists(): zip_path.unlink()
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for path in folder.rglob('*'):
            if path.is_file():
                z.write(path, path.relative_to(folder.parent))
    with zipfile.ZipFile(zip_path, 'r') as z:
        bad = z.testzip()
        if bad:
            raise RuntimeError(f'zip test failed at {bad}')


def main() -> int:
    ap = argparse.ArgumentParser(description='Build Code RED Pass16 Living World working mod from copied RPFs.')
    ap.add_argument('--content', type=Path, default=SCRIPT_DIR / 'content.rpf')
    ap.add_argument('--tune', type=Path, default=SCRIPT_DIR / 'tune_d11generic.rpf')
    ap.add_argument('--out', type=Path, default=SCRIPT_DIR / 'CodeRED_Pass16_LivingWorld_Working_Build')
    args = ap.parse_args()
    if not args.content.exists(): raise SystemExit(f'Missing content.rpf: {args.content}')
    if not args.tune.exists(): raise SystemExit(f'Missing tune_d11generic.rpf: {args.tune}')
    if args.out.exists(): shutil.rmtree(args.out)
    args.out.mkdir(parents=True)
    report = build(args.content, args.tune, args.out)
    drop = args.out / 'DROP_IN_CodeRED_Pass16_LivingWorld_Working_Mod'
    zip_path = SCRIPT_DIR / 'Code_RED_Pass16_LivingWorld_Working_Mod.zip'
    zip_folder(drop, zip_path)
    print(json.dumps({'zip': str(zip_path), 'report': report['validation']}, indent=2))
    return 0 if report['validation']['all_required_checks_pass'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
