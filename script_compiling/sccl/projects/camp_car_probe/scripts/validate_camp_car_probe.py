from __future__ import annotations

from pathlib import Path
import re
import sys

root = Path(__file__).resolve().parents[1]
scc_lane = root.parents[1]
src = root / 'src' / 'main.c'
project_include = root / 'include' / 'RDR' / 'natives32.h'
project_consts = root / 'include' / 'RDR' / 'consts32.h'
lane_include = scc_lane / 'include' / 'RDR' / 'natives32.h'
lane_consts = scc_lane / 'include' / 'RDR' / 'consts32.h'

text = src.read_text(encoding='utf-8') if src.exists() else ''

def read(path: Path) -> str:
    return path.read_text(encoding='utf-8', errors='ignore') if path.exists() else ''

natives = read(project_include)
constants = read(project_consts)
lane_natives = read(lane_include)

fake_header_markers = [
    'Minimal Code RED proof natives',
    'source-proof shims',
    'Final SC-CL native hashes should be supplied',
]

required_native_names = [
    '_CLEAR_PRINTS', '_PRINT_SUBTITLE', '_IS_KEY_PRESSED', 'GET_PLAYER_ACTOR',
    '_IS_LAYOUT_VALID', 'CREATE_LAYOUT', 'FIND_ACTOR_IN_LAYOUT', 'DESTROY_ACTOR',
    'STREAMING_REQUEST_ACTOR', 'CREATE_ACTOR_IN_LAYOUT', 'IS_ACTOR_VALID',
    'IS_ACTOR_VEHICLE', 'ENABLE_VEHICLE_SEAT', 'SET_VEHICLE_ALLOWED_TO_DRIVE',
    'SET_VEHICLE_ENGINE_RUNNING', 'VEHICLE_SET_HANDBRAKE', 'START_VEHICLE',
    'SET_ACTOR_IN_VEHICLE', 'SET_ACTOR_MAX_SPEED', 'SET_ACTOR_MAX_SPEED_ABSOLUTE',
    'SET_ACTOR_SPEED', 'ADD_PERSISTENT_SCRIPT', '_GET_ID_OF_THIS_SCRIPT', 'WAIT',
    'GET_POSITION'
]
required_constants = ['ACTOR_VEHICLE_Car01', 'KEY_F5', 'KEY_F6', 'KEY_F7', 'KEY_F8']
required_tokens = [
    'CODE RED CAMP CAR', 'CR_SpawnCampCar', 'CR_DeleteCampCar', 'CR_TuneCar',
    'CR_PutPlayerInCar', 'CodeREDCampCarProbeV1', 'CodeREDCampCar01',
    'ACTOR_VEHICLE_Car01', 'spawnPos.x = spawnPos.x + 4.0f',
    'spawnPos.y = spawnPos.y + 2.0f', 'F5 spawns Car01 nearby'
]

missing = []
for name in required_native_names:
    if name not in natives and name not in text:
        missing.append(name)
for name in required_constants:
    if name not in constants and name not in text:
        missing.append(name)
for token in required_tokens:
    if token not in text:
        missing.append(token)

project_header_is_fake = any(marker in natives for marker in fake_header_markers)
lane_header_is_fake = any(marker in lane_natives for marker in fake_header_markers)
project_header_looks_real = "This file is part of SC-CL's include library" in natives and '_native' in natives
create_actor_real_sig = bool(re.search(r'CREATE_ACTOR_IN_LAYOUT\s*\([^\n]*vector3\s+Position\s*,\s*vector3\s+Rotation', natives))
source_uses_vector3_create_actor = 'CREATE_ACTOR_IN_LAYOUT(g_campCarLayout, "CodeREDCampCar01", ACTOR_VEHICLE_Car01, spawnPos, spawnRot)' in text
source_uses_loose_create_actor = 'CREATE_ACTOR_IN_LAYOUT(g_campCarLayout, "CodeREDCampCar01", ACTOR_VEHICLE_Car01, 0.0f' in text
source_uses_unverified_vector_ctor = 'Vector3(' in text
subtitle_realish_sig = '_PRINT_SUBTITLE(text, 3000.0f, true, 1, 0, 0, 0, 0)' in text

checks = {
    'source_exists': src.exists(),
    'project_include_exists': project_include.exists(),
    'project_consts_exists': project_consts.exists(),
    'lane_include_exists': lane_include.exists(),
    'project_header_looks_real_sccl': project_header_looks_real,
    'project_header_is_not_fake_shim': not project_header_is_fake,
    'lane_header_is_not_fake_shim': not lane_header_is_fake,
    'create_actor_uses_real_vector3_signature': create_actor_real_sig,
    'source_uses_vector3_create_actor_call': source_uses_vector3_create_actor,
    'source_does_not_use_loose_float_create_actor': not source_uses_loose_create_actor,
    'source_does_not_use_unverified_Vector3_constructor': not source_uses_unverified_vector_ctor,
    'subtitle_call_uses_real_8_arg_shape': subtitle_realish_sig,
    'brace_balance': text.count('{') == text.count('}'),
    'paren_balance': text.count('(') == text.count(')'),
    'has_main_loop': 'while (true)' in text and 'WAIT(0)' in text,
    'has_runtime_boundary': 'runtime proof only' in text.lower() and 'does not install into game archives' in text.lower(),
    'has_spawn': 'CR_SpawnCampCar' in text and 'ACTOR_VEHICLE_Car01' in text,
    'has_delete': 'CR_DeleteCampCar' in text and 'DESTROY_ACTOR' in text,
    'has_tune': 'CR_TuneCar' in text and 'SET_ACTOR_MAX_SPEED_ABSOLUTE' in text,
    'has_player_enter': 'CR_PutPlayerInCar' in text and 'SET_ACTOR_IN_VEHICLE' in text,
    'has_edge_triggered_keys': 'CR_KeyPressedOnce' in text and 'g_lastF5' in text and 'g_lastF8' in text,
    'missing_symbols': missing,
}

ok = all(v for k, v in checks.items() if k != 'missing_symbols') and not missing
for k, v in checks.items():
    print(f'{k}: {v}')
print('RESULT:', 'PASS' if ok else 'FAIL')
if project_header_is_fake or lane_header_is_fake:
    print('ACTION: run script_compiling\\sccl\\promote_real_sccl_headers_windows.ps1 before compiling')
sys.exit(0 if ok else 1)
