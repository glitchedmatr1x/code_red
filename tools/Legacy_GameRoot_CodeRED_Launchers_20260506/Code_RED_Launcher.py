from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BRIDGE_DIR = ROOT / 'Code_RED_Launch'
TARGETS = {'primary': 'PlayRDR.exe', 'play': 'PlayRDR.exe', 'direct': 'RDR.exe'}
mode = sys.argv[1].strip().lower() if len(sys.argv) > 1 else 'primary'
target_name = TARGETS.get(mode, TARGETS['primary'])
target = ROOT / target_name
env = os.environ.copy()
env['CODERED_BRIDGE_DIR'] = str(BRIDGE_DIR)
env['CODERED_ACTIVE_SESSION'] = str(BRIDGE_DIR / 'active_session.json')
env['CODERED_LAUNCH_PLAN'] = str(BRIDGE_DIR / 'launch_plan.json')
env['CODERED_HOOK_BOOTSTRAP'] = str(ROOT / 'Code_RED_HookBridge' / 'hook_bootstrap.json')
env['CODERED_HOOK_PACK_DIR'] = str(ROOT / 'Code_RED_HookBridge')
runtime = BRIDGE_DIR / 'codered_bridge_runtime.py'
for candidate in (['py', '-3'], ['python']):
    if runtime.exists():
        try:
            subprocess.Popen(candidate + [str(runtime), str(BRIDGE_DIR)], cwd=str(ROOT), env=env)
            break
        except Exception:
            pass
if target.exists():
    subprocess.Popen([str(target)], cwd=str(ROOT), env=env)
else:
    print(f'Target executable not found: {target}')
