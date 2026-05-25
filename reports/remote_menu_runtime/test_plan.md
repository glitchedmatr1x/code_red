# Code RED Remote Menu Puppet Test Plan

1. Launch Red Dead Redemption single-player with only Code RED Remote Menu installed.
2. Wait at least 30 seconds after the game world loads.
3. Open `D:\Games\Red Dead Redemption\logs\codered_remote_menu.log`.
4. Confirm `Registration succeeded`.
5. Confirm `Native probe:` appears and reports a valid player actor and readable position.
6. Press `F9` once.
7. Confirm the log shows `Puppet spawned`.
8. Watch for `Puppet marker` log lines every 5 seconds.
9. Press `Backspace`.
10. Confirm the log shows `Puppet release`.

Do not test these yet:
- `F8/E` Soul Stealer actor capture
- `F6` player teleport write
- `F10` puppet teleport
- blip mode
- label mode
- overlay menu mode

If `F9` crashes:
- Do not retry with blip/label enabled.
- Send `logs\codered_remote_menu.log` and any Windows crash module.
- Next fix should focus only on the `CREATE_ACTOR_IN_LAYOUT` calling convention or actor enum/layout choice.
