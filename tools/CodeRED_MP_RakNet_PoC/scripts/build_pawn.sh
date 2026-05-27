#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PAWNCC="${PAWNCC:-pawncc}"
GAMEMODE="${1:-gamemodes/codered_hello.pwn}"
OUTPUT="${2:-${GAMEMODE%.pwn}.amx}"

"$PAWNCC" "$GAMEMODE" \
  -iqawno/include \
  -o"$OUTPUT" \
  -Z \
  -d3

echo "built $OUTPUT"
