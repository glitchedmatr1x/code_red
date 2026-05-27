#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")"
mkdir -p build

CXX=${CXX:-x86_64-w64-mingw32-g++}

"$CXX" \
  -std=c++17 \
  -O2 \
  -Wall \
  -Wextra \
  -Wno-cast-function-type \
  -Wno-unused-parameter \
  -Wno-unused-function \
  -D_CRT_SECURE_NO_WARNINGS \
  -shared \
  -static \
  -static-libgcc \
  -static-libstdc++ \
  -o build/CodeRED_AI_Menu.asi \
  CodeRED_AI_Menu.bridge_candidate.cpp \
  -luser32 \
  -lkernel32

printf '%s\n' "built build/CodeRED_AI_Menu.asi"
