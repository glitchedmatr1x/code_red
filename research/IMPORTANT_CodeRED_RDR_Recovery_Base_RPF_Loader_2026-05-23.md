# IMPORTANT - RDR Recovery and Base RPF Loader Notes - 2026-05-23

## Recovery Actions Taken

- Restored `D:\Games\Red Dead Redemption\game\base\content.rpf`, `cutscene.rpf`, `fragments.rpf`, and `mapres.rpf` from `game\base\base.zip`.
- Quarantined extra large/test RPFs from active `game\base` folders under `CodeRED_RECOVERY_QUARANTINE_20260523`.
- Verified all main `content.rpf` copies in root/game/clean/PUT BACK ASAP match SHA1 `E063FBEC79941AD2CA2504BA616596B1BB332B49`.
- SteamGG was inspected briefly by mistake, then restored to the pre-change state. Do not touch SteamGG in this recovery lane.

## Base RPF Loader Finding

The file controlling the current `/game/base/` base archive list is not `gent.xml`. The evidence is embedded strings in:

`D:\Games\Red Dead Redemption\RDR.exe`

Observed string offsets:

| String | Offset |
|---|---:|
| `base/content` | `0x1C79538` |
| `base/cutscene` | `0x1C79548` |
| `base/mapres` | `0x1C79558` |
| `base/fragments` | `0x1C79568` |
| `patch%i` | `0x1C79598` |
| `.rpf` | `0x1C795A0` |
| `d11generic` | `0x1C795B8`, `0x1D633E0` |

Current conclusion: the PC executable has a hard-coded base mount list for:

- `base/content.rpf`
- `base/cutscene.rpf`
- `base/mapres.rpf`
- `base/fragments.rpf`

Adding every RPF to `/game/base/` will not make the game read them unless the executable mount table is patched or a runtime loader hooks the archive-open path safely.

## Crash Note

Recent automated tests showed `RDRMessage.exe` crashing through:

`C:\ProgramData\A-Volute\DellInc.AlienwareSoundCenter\Modules\ScheduledModules\x64\NahimicOSD.dll`

That is an overlay/OSD injection crash, not an RPF parse error by itself. For stability testing, disable Nahimic/Alienware Sound Center OSD injection before launching RDR.
