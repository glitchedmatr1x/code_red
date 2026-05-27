# Code RED Base Override Menu Scan — 2026-05-03

## User correction

The uploaded `base.zip` is a real game-folder override set. It should not be confused with same-name archives from other resource folders.

## Archives inside base.zip

```text
fragments.rpf
mapres.rpf
content.rpf
cutscene.rpf
```

## Scan result

`content.rpf` in this override set is small and contains only two script/mission files:

```text
root/content/release64/frontier/missions/marshal04/marshal04.sco
root/content/release64/frontier/missions/marshal04/marshal04.wsc
```

This means this override set is probably not the global pause/cheat UI shell. It is a mission-script override candidate.

## Hash/proof notes from scan

```text
marshal04.sco
- size: 84467
- sha1: 4fc52d0be5a07de05aec8d47ca09e756af22503a
- decode note: raw SCR-style script payload

marshal04.wsc
- archive slot size: 76513
- reported total size: 208896
- sha1 of extracted RSC wrapper: 9dfe4051fda8843aafa3c01c00b9b7717063803a
- decode note: RSC85 payload + AES standard resource decode path
```

## Cutscene side files

`cutscene.rpf` contains:

```text
root/cutscene/cutscenelist_z.txt
root/cutscene/cutscenelist.txt
root/cutscene/rebel_leader_06/rebel_leader_06.cutbin
root/cutscene/rebel_leader_06/dict-0.wcdt
root/cutscene/rebel_leader_06/dict-1.wcdt
root/cutscene/rebel_leader_06/dict-2.wcdt
```

The cutscene lists include normal mission/cutscene offsets, including marshal04 entries, but not cheat/debug menu code.

## Important conclusion

The previous cheat UI XML chain is still valid for the built-in visible cheat menu shell:

```text
content/ui/userinterface.sc.xml
content/ui/debug.sc.xml
content/ui/pausemenu/options.sc.xml
content/ui/pausemenu/extras.sc.xml
content/ui/pausemenu/pausemenuscene.sc.xml
```

But this `base.zip` override does not contain those UI XML files. Instead, its best lead is `marshal04.sco/.wsc` as a mission-script override.

## Tool added

Added:

```text
tools/codered_override_menu_finder.py
```

Example command:

```bat
py -3 tools\codered_override_menu_finder.py path\to\base.zip --out reports\override_menu_finder --extract-hits
```

The tool is read-only and writes:

```text
override_menu_finder_summary.json
override_rpf_entries.csv
override_menu_script_hits.csv
override_menu_finder_report.md
```

## Next pass

1. Compare this override `marshal04.sco/.wsc` against a stock/default `marshal04` copy if available.
2. Search game executable/DLL files for `rdrExtrasLayer`, `CheatsList`, `UI_CheatEntered`, `GameCheat_Label_`, and `DebugMenu`.
3. Add a script-bytecode identity/comparison tool before attempting any patch.

No patching should be done from this pass alone.
