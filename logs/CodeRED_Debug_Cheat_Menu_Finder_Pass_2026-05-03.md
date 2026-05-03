# Code RED Debug / Cheat Menu Finder Pass — 2026-05-03

## Goal

Find where the built-in debug/cheat menu is defined and whether DLC archives contain the missing menu script/code.

## Inputs scanned locally

Resource set assembled from uploaded archives:

```text
content.rpf
tune_d11generic.rpf
strings_d11generic.rpf
flash.rpf
camera.rpf
gringores.rpf
blackwater.rpf
dlc01x.rpf through dlc10x.rpf
```

## Main finding

The cheat menu shell is in `content.rpf` UI XML files, not in the uploaded DLC world RPFs.

Strong UI chain:

```text
content/ui/userinterface.sc.xml
  -> includes Debug.sc
  -> includes pausemenu/PauseMenuScene.sc
  -> options.sc.xml includes Extras.sc.xml
  -> Extras.sc.xml defines rdrExtrasLayer / CheatsList
  -> pausemenuscene.sc.xml handles popup_cheatInput and UI_Cheat* events
```

## Specific leads

```text
root/content/ui/userinterface.sc.xml
root/content/ui/debug.sc.xml
root/content/ui/pausemenu/options.sc.xml
root/content/ui/pausemenu/extras.sc.xml
root/content/ui/pausemenu/pausemenuscene.sc.xml
root/strings/interface_win32.strtbl
root/strings/global_win32.strtbl
root/flash/brplru/pause_main.wsf
root/flash/brplru/list.wsf
root/flash/brplru/popup.wsf
```

## Important negative result

The scanned `.wsc` and `.sco` scripts did not show normal readable `cheat`, `CheatsList`, `rdrExtrasLayer`, or `UI_Cheat*` string hits.

That means the actual cheat list filler / enable logic is probably one of these:

1. native UI class code backing `rdrExtrasLayer`
2. game executable / DLL code
3. undecoded Flash/WSF resources
4. script bytecode without readable string labels

Do not assume it is a normal DLC `.wsc` file until a real hit proves it.

## DLC result

The uploaded `dlc01x.rpf` through `dlc10x.rpf` archives looked like WSI/world/model placement archives for this search. They did not contain the actual cheat menu script code.

## Next no-guess step

Search the PC executable / DLL folder, if available, for:

```text
rdrExtrasLayer
CheatsList
GameCheat_Label_
GameCheat_Desc_
UI_CheatEntered
UI_OpenCheatsMsgBox
DebugMenu
```

Then add executable-string scan support to the finder if those files are provided.
