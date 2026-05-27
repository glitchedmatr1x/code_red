#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../../.."
python3 related_apps/CodeRED_Script_Workshop/CodeRED_Script_Workshop.py scan --refresh
python3 -m py_compile related_apps/CodeRED_Script_Workshop/CodeRED_Script_Workshop.py
echo 'Linux prep check passed. Windows compiler proof still runs on Windows.'
