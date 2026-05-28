#!/usr/bin/env python3
from pathlib import Path

installer = Path(r"%RDR_GAME_DIR%\Code_RED\tools\codered_mp_freeroam_pass3_installer.py")
if not installer.exists():
    raise SystemExit(f"Installer not found: {installer}")

backup = installer.with_suffix(installer.suffix + ".bak_resource_replace_fix")
if not backup.exists():
    backup.write_bytes(installer.read_bytes())

text = installer.read_text(encoding="utf-8")
old = 'action, node = overlay.add_or_replace_file(wb, root, row["archive_path"], row["payload"], "replace")'
new = 'action, node = overlay.add_or_replace_file(wb, root, row["archive_path"], row["payload"], "replace", allow_resource_replace=True)'

if new in text:
    print("Installer already has allow_resource_replace=True.")
elif old in text:
    installer.write_text(text.replace(old, new), encoding="utf-8")
    print(f"Patched installer: {installer}")
else:
    raise SystemExit("Could not find expected add_or_replace_file call. Edit manually and add allow_resource_replace=True.")

print(r"""
Now run:
cd "%RDR_GAME_DIR%\Code_RED"
$env:PYTHONPATH='.'
py -3 tools\codered_mp_freeroam_pass3_installer.py
""")
