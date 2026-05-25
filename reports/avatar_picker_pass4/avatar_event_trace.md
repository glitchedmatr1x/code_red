# Avatar Picker Access Pass 4 - Avatar Event Trace

## Known Script Handler

PC `fuieventmonitor.wsc` already contains and handles:

```text
LaunchAvatarPicker
```

The public PC decompile shows the owner:

```text
DECOR_CHECK_STRING(event, "Param", "LaunchAvatarPicker")
```

The handler then sets:

```text
Global_124888 = 4294967294
```

This means the first problem is reachability, not a missing script string.

## Existing SCXML Event Bridge

`lobby/main.sc.xml` already uses:

```text
NetMachine.SendScriptEvent('LaunchAvatarPicker')
```

inside:

```text
NetConf_AvatarPicker
```

That is the strongest known SCXML-to-fuieventmonitor bridge. This pass therefore uses `NetMachine.SendScriptEvent('LaunchAvatarPicker')`, not plain `SendEvent('LaunchAvatarPicker')`.

## Why Not SendEvent?

`SendEvent(...)` is used for SCXML-local UI events such as:

```text
loadStart
retry_action
PM.UnfocusInbox
```

The avatar picker path is different. The known working-style bridge is:

```text
NetMachine.SendScriptEvent('LaunchAvatarPicker')
```

which is intended to create the script/FUI event consumed by `fuieventmonitor`.

## Candidate Event Routes

### Route 1: Confirmation route

```text
Visible offline tab
-> goto(NetConf_AvatarPicker)
-> user accepts
-> NetMachine.SendScriptEvent('LaunchAvatarPicker')
```

Used by Variant B.

### Route 2: Direct visible route

```text
Visible offline tab
-> accept
-> NetMachine.SendScriptEvent('LaunchAvatarPicker')
```

Used by Variant C.

### Route 3: Current nag route

```text
User reaches network nag
-> OK/Accept
-> NetMachine.SendScriptEvent('LaunchAvatarPicker')
```

Used by Variant D only if the nag is the only reachable network UI screen.

## What Success Looks Like

Any of these count as progress:

```text
MP avatar picker opens
MP profile editor opens
MP_AvatarGroupSelector appears
different avatar/profile-specific blocker appears
```

If nothing visible happens after Variant C or D, then `LaunchAvatarPicker` may only set a global and a second runtime owner is missing/inactive in single-player. The next fallback would be direct SCXML entry to `MP_ProfileEditor`, still without WSC patching.
