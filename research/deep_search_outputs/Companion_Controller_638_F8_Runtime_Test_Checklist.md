# Companion Controller 638 F8 Runtime Test Checklist

## Install

Copy these into the active Red Dead Redemption game folder:

```text
D:\Games\Red Dead Redemption\Code_RED\tools\CodeRED_PeerCompanion\build\CodeRED_PeerCompanion.asi
D:\Games\Red Dead Redemption\Code_RED\tools\CodeRED_PeerCompanion\data\codered\peer_companion.ini
```

Install the INI as:

```text
D:\Games\Red Dead Redemption\data\codered\peer_companion.ini
```

The previous runtime log showed the INI was missing, so confirm this file exists before testing.

## Baseline INI

Use the current safe defaults:

```ini
enable_set_faction=true
enable_set_companion=false
enable_task_follow=true
enable_task_priority=false
enable_squad_route=false
debug_adopt_only=false
allow_any_target=false
adopt_actor_enum=638
adopt_radius=8.0
```

## Test Steps

1. Launch normal single-player.
2. Wait at least 15 seconds for startup delay.
3. Spawn or locate actor 638 / son / Jack test actor.
4. Aim/target actor 638.
5. Press `F6` snapshot.
6. Press `F8` adopt/follow.
7. Press `F6` snapshot again.
8. Press `F10` regroup/follow.
9. Press `F9` guard/wait.
10. Press `Backspace` release.

## Expected F8 Success Log

```text
[PeerCompanion] F8 key detected: adopt/follow requested
ENTER stage_a_get_target_actor
stage_a target_actor_handle=<nonzero>
ENTER adopt_actor_638
adopt_candidate source=GET_TARGET_ACTOR actor=<handle> enum=638 distance=<under radius>
ENTER companion_apply_state
stage_c SET_ACTOR_FACTION call reached
EXIT stage_c_set_actor_faction OK
EXIT stage_c_set_actor_is_companion SKIPPED enable_set_companion=false
ENTER companion_fallback_follow
stage_d TASK_FOLLOW_ACTOR call reached
EXIT stage_d_task_follow_actor OK
EXIT companion_fallback_follow OK
EXIT adopt_actor_638 OK
```

## If F8 Still Fails

Send back the last 80-120 lines of:

```text
D:\Games\Red Dead Redemption\logs\codered_peer_companion.log
```

The most important lines are:

```text
stage_a target_actor_handle=...
[PeerCompanion] F8 adopt failed: no valid targeted actor.
adopt_candidate source=GET_TARGET_ACTOR actor=... enum=... distance=...
stage_c_set_actor_faction exception=...
stage_d_task_follow_actor exception=...
```

## Isolation Toggles

If the game shows an error after adoption succeeds, isolate stages in this order:

### Stage B only

```ini
debug_adopt_only=true
```

This validates target acquisition and handle storage only.

### Stage C faction only

```ini
debug_adopt_only=false
enable_set_faction=true
enable_set_companion=false
enable_task_follow=false
```

### Stage D follow only

```ini
enable_set_faction=false
enable_set_companion=false
enable_task_follow=true
```

### Companion flag probe

Only after follow works:

```ini
enable_set_companion=true
```

### Task priority probe

Only after follow works:

```ini
enable_task_priority=true
```

### Squad route probe

Only after fallback follow works:

```ini
enable_squad_route=true
```

If squad route causes any error, turn it back off. The squad natives compile, but their `Any` arguments are not proven yet.
