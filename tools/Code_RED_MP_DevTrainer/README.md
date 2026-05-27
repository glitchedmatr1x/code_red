# Code RED MP Dev Trainer

`CodeRED_MP_DevTrainer.asi` is a local/offline ScriptHookRDR diagnostics scaffold for the restored multiplayer menu lane. It logs registration and hotkey attempts to:

```text
logs/codered_mp_dev_trainer.log
```

Install the ASI beside `RDR.exe` with the config at:

```text
data/codered/mp_dev_trainer.ini
```

Hotkeys:

| Key | Current action |
| --- | --- |
| F5 | Reload config |
| F6 | Dump trainer and optional actor snapshot state |
| F7 | Log local LAN route request and point to Pass 5 XML route |
| F8 | Log `MULTI_FREE_ROAM` game-wish request |
| F9 | Log `TriggerMultiplayerLoad` probe |
| F10 | Log `StartGameWish` probe |
| F11 | Log catacombs sector toggle probe |
| F12 | Log MP/Blackwater/free-roam sector toggle probe |
| NUM1 | Log catacombs teleport probe |
| NUM2 | Log Blackwater MP teleport probe |
| NUM3 | Dump nearby actor probe if ScriptHook exposes `worldGetAllActors` |

Route/load/start/sector/teleport probes stay skipped when no safe native bridge is mapped. The trainer must not spoof public services or auth. Optional auth experiments remain separate from this ASI and disabled in the default Pass 5 package.

Build from the Code_RED repo root:

```bat
related_apps\Code_RED_MP_DevTrainer\build_bridge.bat
```
