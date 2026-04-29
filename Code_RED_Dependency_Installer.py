from __future__ import annotations
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REQ = ROOT / 'requirements.txt'
PACKAGES = ['pillow', 'cryptography', 'numpy', 'matplotlib', 'panda3d', 'pygame']

def run(cmd: list[str]) -> int:
    print('> ' + ' '.join(cmd))
    return subprocess.call(cmd)

python = sys.executable or 'python'
code = run([python, '-m', 'pip', 'install', '--upgrade', 'pip'])
if not code:
    if REQ.exists():
        code = run([python, '-m', 'pip', 'install', '-r', str(REQ)])
    else:
        code = run([python, '-m', 'pip', 'install', *PACKAGES])
print('\nExternal components such as RedHook and ScriptHookRDR are not bundled here.')
raise SystemExit(code)
