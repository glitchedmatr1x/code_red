# Code RED WSC Edit Workspace

- Name: `codered_wait_probe`
- Source RPF: `D:\Games\Red Dead Redemption\game\content.rpf`
- Archive path: `root/content/release64/init/initpopulation.wsc`
- Edit source: `src/main.c`
- Original binary: `D:\Games\Red Dead Redemption\Code_RED\build\wsc_edit\codered_wait_probe\original\content\release64\init\initpopulation.wsc`

Commands:

```bat
python tools\codered_wsc_edit_workflow.py compile --workspace "D:\Games\Red Dead Redemption\Code_RED\build\wsc_edit\codered_wait_probe"
python tools\codered_wsc_edit_workflow.py pack --workspace "D:\Games\Red Dead Redemption\Code_RED\build\wsc_edit\codered_wait_probe" --write
```

Boundary: this workspace does not pretend to decompile WSC bytecode into original source.
