# Avatar Picker Pass 5 Cross-Platform / Version Diff

## Profile Editor

- PC extracted: `Code_RED/game/content_extracted/ui/net/profileeditor/main.sc.xml`
- Older root reference: `game/BACKUP BEFORE MODDING/rdr1/mods/root/content/ui/net/profileeditor/main.sc.xml`
- PC SHA1: `a326c0ffdbe1fe11fe3e6f82323a7f5dfff05e51`
- Root reference SHA1: `282d907132e1bd6152630e577858c9a5f50e40cd`

The files differ mainly in input event spelling: current PC uses `@UI.ACCEPT*RELEASED` / `@UI.CANCEL*RELEASED`, while the older extracted root uses `action_released` / `cancel_released`. The avatar group/model structure is otherwise the same: both define `MP_AvatarGroupSelector` with `mp_avatar_group0` through `mp_avatar_group25`, and `MP_AvatarModelSelector` with `mp_avatar0` through `mp_avatar13`.

## String Resources

Current PC `strings_d11generic.rpf` contains `mp_avatarpicker-*.wst` and `mp_avatarpicker_win32.strtbl`. The current `content.rpf` inventory does not contain `content/stringtable/mp_avatarpicker-*`, so the PC route should use the strings archive plus `StreamStringTable('mp_avatarpicker')` rather than importing old `.cst` files into content.rpf first.

## Save/Profile/Auth

PC and the older root both have save/autosave blockers and netstats authentication/read-success branches. These are recorded as blockers, but Pass 5 does not patch them because the blank menu is now narrower than full MP auth/session state.
