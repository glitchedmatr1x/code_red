from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
src = root / 'src' / 'main.c'
include = root / 'include' / 'RDR' / 'natives32.h'
consts = root / 'include' / 'RDR' / 'consts32.h'
text = src.read_text(encoding='utf-8')
natives = include.read_text(encoding='utf-8', errors='ignore')
constants = consts.read_text(encoding='utf-8', errors='ignore')

required_native_names = [
    '_CLEAR_PRINTS', '_PRINT_SUBTITLE', '_IS_KEY_PRESSED', 'GET_PLAYER_ACTOR',
    '_IS_LAYOUT_VALID', 'CREATE_LAYOUT', 'FIND_ACTOR_IN_LAYOUT', 'DESTROY_ACTOR',
    'STREAMING_REQUEST_ACTOR', 'CREATE_ACTOR_IN_LAYOUT', 'IS_ACTOR_VALID',
    'IS_ACTOR_VEHICLE', 'ENABLE_VEHICLE_SEAT', 'SET_VEHICLE_ALLOWED_TO_DRIVE',
    'SET_VEHICLE_ENGINE_RUNNING', 'VEHICLE_SET_HANDBRAKE', 'START_VEHICLE',
    'SET_ACTOR_IN_VEHICLE', 'SET_ACTOR_MAX_SPEED', 'SET_ACTOR_MAX_SPEED_ABSOLUTE',
    'SET_ACTOR_SPEED', 'ADD_PERSISTENT_SCRIPT', '_GET_ID_OF_THIS_SCRIPT', 'WAIT'
]
required_constants = [
    'ACTOR_VEHICLE_Car01', 'ACTOR_VEHICLE_Truck01',
    'KEY_F5', 'KEY_F6', 'KEY_F7', 'KEY_F8'
]
required_menu_tokens = [
    'CODE RED MENU v1 ready',
    'CR_SECTION_VEHICLES', 'CR_SECTION_PLAYER', 'CR_SECTION_DEBUG',
    'CR_VEHICLE_CAR', 'CR_VEHICLE_TRUCK', 'CR_VEHICLE_DELETE', 'CR_VEHICLE_TUNE',
    'CR_PLAYER_ENTER', 'CR_PLAYER_CLEAR',
    'CR_DEBUG_STATUS', 'CR_DEBUG_KEYS',
    'CR_ShowMenu', 'CR_NextSection', 'CR_NextOption', 'CR_ExecuteOption',
    'CR_KeyPressedOnce', 'KEY_F5', 'KEY_F6', 'KEY_F7', 'KEY_F8'
]

missing = []
for name in required_native_names:
    if name not in natives and name not in text:
        missing.append(name)
for name in required_constants:
    if name not in constants and name not in text:
        missing.append(name)
for token in required_menu_tokens:
    if token not in text:
        missing.append(token)

checks = {
    'source_exists': src.exists(),
    'brace_balance': text.count('{') == text.count('}'),
    'paren_balance': text.count('(') == text.count(')'),
    'has_main_loop': 'while (true)' in text and 'WAIT(0)' in text,
    'has_visible_menu': 'CODE RED MENU' in text and 'CR_ShowMenu' in text,
    'has_menu_sections': 'CR_SECTION_VEHICLES' in text and 'CR_SECTION_PLAYER' in text and 'CR_SECTION_DEBUG' in text,
    'has_vehicle_spawn': 'CR_SpawnVehicle' in text and 'ACTOR_VEHICLE_Car01' in text and 'ACTOR_VEHICLE_Truck01' in text,
    'has_vehicle_delete': 'CR_DestroyVehicle' in text and 'Delete vehicle' in text,
    'has_live_tune': 'CR_ApplyTune' in text and 'SET_ACTOR_MAX_SPEED_ABSOLUTE' in text,
    'has_player_actions': 'CR_PutPlayerInVehicle' in text and 'Clear prints' in text,
    'has_debug_actions': 'Spawn status' in text and 'F5 section / F6 option / F7 run / F8 hide' in text,
    'has_edge_triggered_keys': 'CR_KeyPressedOnce' in text and 'g_lastF5' in text and 'g_lastF8' in text,
    'missing_symbols': missing,
}

ok = all(v for k, v in checks.items() if k != 'missing_symbols') and not missing
for k, v in checks.items():
    print(f'{k}: {v}')
print('RESULT:', 'PASS' if ok else 'FAIL')
sys.exit(0 if ok else 1)
