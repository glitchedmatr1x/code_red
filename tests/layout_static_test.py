from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import code_red_main

source = (ROOT / "code_red_main.py").read_text(encoding="utf-8")
tree = ast.parse(source)

assert code_red_main.APP_TITLE.startswith("Code RED")
assert "Archives" in code_red_main.RESOURCE_LANES
assert "Scripts" in code_red_main.RESOURCE_LANES
assert len(code_red_main.TOP_ACTIONS) == 5
assert ".place(" not in source, "absolute placement is blocked in the consolidated shell"
assert source.count("def _button") == 1, "button creation should be centralized"
assert source.count("ttk.Button(") == 1, "buttons should be created through _button only"

# Tkinter pack/grid can coexist only when confined to different parents, but this pass
# keeps the shell grid-only to avoid the old scattered-button behavior.
assert ".pack(" not in source, "grid-only shell expected"

print("PASS layout_static_test")
