# Avatar Picker Pass 5 Candidate Patch Plan

## Test Order

1. Test Variant E first.
   - File: `D:\Games\Red Dead Redemption\Code_RED\build\avatar_picker_access_pass5\variant_E_direct_avatar_plus_clean_cancel\networking.sc.xml`
   - Install target: `root/content/ui/pausemenu/networking.sc.xml`
   - Expected: same avatar opening behavior as Variant C, with Variant D's clean cancel/back/no-nag behavior.

2. If Variant E still opens a blank picker, test Variant F together with Variant E.
   - File: `D:\Games\Red Dead Redemption\Code_RED\build\avatar_picker_access_pass5\variant_F_profileeditor_stream_avatar_strings\main.sc.xml`
   - Install target: `root/content/ui/net/profileeditor/main.sc.xml`
   - Expected: avatar group/model labels should populate if the blank state is caused by missing streamed string tables.

## Variant F Patch

Adds only:

```xml
<onactivate expr="StreamStringTable('multiplayer')"></onactivate>
<onactivate expr="StreamStringTable('mp_avatarpicker')"></onactivate>
<ondeactivate expr="UnstreamStringTable('mp_avatarpicker')"></ondeactivate>
<ondeactivate expr="UnstreamStringTable('multiplayer')"></ondeactivate>
```

## If Variant F Still Blank

Next candidate should inspect profile stat/unlock hydration, not full MP boot:

- netstats `stats.readSuccess` / `stats.readFail`
- MP profile globals or stat reads feeding avatar unlocks
- save/autosave blockers only if avatar selections cannot be applied

Do not patch Gamespy/Online auth globally and do not force session state globally.
