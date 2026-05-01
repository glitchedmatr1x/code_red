# CodeRED Handoff — AI Script Control for Trainer-Spawned Players / Actors

Date: 2026-05-01  
Status: New direction / Xenia on hold  
Project owner: GLITCHED MATRIX / CodeRED

## Decision

Hold off on Xenia multiplayer work for now.

The Xenia path consumed too much time and still has unresolved connection blockers:
- Singleplayer Host can reportedly host a state/session.
- LAN/private/public Freeroam connection is not working yet.
- Xenia bridge work is useful research, but not the fastest route to visible AI-controlled “players.”

The new direction is:

> Use a trainer or mod script to spawn an actor/player-like companion, then use an AI/script controller to command it.

This can potentially work without Xenia if the target game/runtime supports local trainer spawning, script hooks, or native mod APIs.

## Core idea

Instead of making the game believe a real network player joined, create or reuse a locally spawned character entity and control it through script logic.

Conceptual pipeline:

```text
Trainer / mod menu spawns actor
→ CodeRED AI Controller detects or receives entity handle
→ Behavior script assigns state: follow, guard, attack, regroup, dismiss
→ Game-side script applies movement/combat/task commands
→ External controller updates behavior goals and logs state
```

## Why this is better than the current Xenia route

This avoids the hardest unsolved pieces:
- no fake Xbox Live required
- no system-link connection required
- no Freeroam join required
- no second emulator instance required
- no Xenia networking port conflicts
- no packet/session emulation needed for the first proof

It also fits the user’s original gameplay goal better: visible AI-controlled allies/companions.

## Safety / scope boundary

Keep this for:
- singleplayer
- offline play
- private test environments
- modding/sandbox use
- preservation/research prototypes

Do not aim this at:
- public online cheating
- anti-cheat bypass
- impersonating real players in public services
- griefing other users
- bypassing official authentication or paid services

## Main technical approaches

### Approach A — Trainer-spawned NPC companion

Best first target.

The trainer spawns a ped/actor. The CodeRED script takes control of that actor using behavior commands.

Behavior commands:
- `spawn`
- `follow`
- `guard`
- `defend`
- `attack`
- `idle`
- `regroup`
- `mount`
- `dismount`
- `dismiss`
- `status`

Expected result:
- visible companion
- follows player
- attacks hostiles
- returns if too far
- can be dismissed or reset
- can be controlled from a simple menu or command file

### Approach B — Trainer-spawned “fake player” body

If the trainer can spawn a player-like model or clone, use that as the AI guest body.

The AI controller should still treat it as an entity handle, not a real network player.

Expected result:
- more player-like appearance
- script-controlled movement/combat
- no networking dependency

Risk:
- player clones may not support all NPC tasks
- animations, weapons, mounts, and combat groups may need per-game tuning

### Approach C — External input-controlled second local client

Only for later.

A script controls a second process/client through virtual controller input. This is useful only if the game supports local second-client testing or if a multiplayer session already works.

Not recommended for the next pass.

## Recommended architecture

### 1. CodeRED AI Controller

External Python controller.

Suggested file:

```text
tools/codered_trainer_ai_controller_v1.py
```

Responsibilities:
- read/write AI state
- accept commands
- maintain behavior mode
- log actions
- output a game-side action plan
- support menu-driven commands

State files:

```text
scratch/codered_trainer_ai_state.json
scratch/codered_trainer_ai_commands.jsonl
scratch/codered_trainer_ai_action_plan.json
logs/codered_trainer_ai_controller.log
```

### 2. CodeRED AI Menu

Simple batch menu.

Suggested file:

```text
CodeRED_Trainer_AI_Menu_v1.bat
```

Menu options:

```text
1. Start AI Controller
2. Spawn AI Guest
3. Follow Player
4. Guard Position
5. Defend Player
6. Attack Hostiles
7. Regroup / Warp Near Player
8. Mount Request
9. Dismount Request
10. Idle
11. Dismiss
12. Status
13. Open State JSON
14. Open Logs
15. Exit
```

### 3. Game-side trainer bridge

This depends on the game and trainer/mod API.

Possible bridge methods:
- a trainer hotkey triggers spawn, then writes/prints entity ID
- game script watches a JSON/INI command file
- trainer exposes named commands
- mod loader script exposes a native function interface
- memory/script bridge passes entity handle to CodeRED

Suggested file names:

```text
scripts/codered_trainer_ai_bridge.*
scripts/codered_ai_companion_tasks.*
```

The game-side bridge should consume:

```text
scratch/codered_trainer_ai_action_plan.json
```

Example action plan:

```json
{
  "version": 1,
  "active": true,
  "entity": {
    "label": "CodeRED_AI_01",
    "handle": null,
    "spawn_requested": true,
    "model": "companion_default"
  },
  "behavior": {
    "mode": "follow_defend",
    "target": "player",
    "follow_distance": 8.0,
    "warp_distance": 80.0,
    "attack_hostiles": true,
    "avoid_friendly_fire": true
  },
  "requests": [
    "ensure_spawned",
    "attach_to_player_group",
    "equip_basic_weapon",
    "follow_player",
    "defend_player"
  ]
}
```

## Behavior model

### AI states

```text
offline
spawn_requested
spawning
active
following
guarding
attacking
regrouping
dismissed
lost
dead
```

### Core behavior loop

```text
Every tick:
1. Check if AI exists.
2. If not and active, request spawn.
3. Check distance to player.
4. If too far, request regroup/warp.
5. Check combat state.
6. If hostiles near player, defend/attack.
7. If idle command active, stop combat/follow tasks.
8. Log state changes.
```

### Minimum viable behavior

The first playable proof only needs:
- spawn
- follow
- defend
- regroup
- dismiss
- status logging

Do not start with advanced personality, dialogue, vehicles, or multiplayer-like invites.

## Suggested next pass

### Pass T1 — Trainer AI scaffolding

Build:
- `tools/codered_trainer_ai_controller_v1.py`
- `CodeRED_Trainer_AI_Menu_v1.bat`
- `data/codered/trainer_ai_profile_v1.json`
- `docs/codered/trainer_ai_control_handoff_v1.md`

Features:
- menu commands
- JSON state
- JSON action plan
- command log
- no dependency on Xenia
- no dependency on a specific trainer yet

Proof:
- run controller
- send spawn/follow/guard/status commands
- verify state/action-plan JSON changes
- verify logs

### Pass T2 — Trainer bridge selection

Choose the real target:
- RDR PC
- GTA/RAGE-based game
- another local trainer-supported game
- existing trainer/mod menu with spawn function

Tasks:
- identify how trainer spawns entity
- identify whether scripts can access entity handle
- choose bridge format: JSON, INI, hotkey, native script, console command, or memory bridge
- do one visible spawn proof

### Pass T3 — Visible companion proof

Goal:
- trainer spawns actor
- CodeRED AI command sets `follow`
- actor follows/guards player
- status/log proves behavior

### Pass T4 — Behavior expansion

Add:
- combat target scoring
- guard area
- patrol around player
- mount/dismount
- revive/respawn
- companion personality profile
- command aliases

## Handoff prompt for next chat/pass

```text
Continue CodeRED from the Trainer AI Control handoff.

Hold off on Xenia for now.

Goal:
Build a script-controlled AI guest/companion that can control an actor spawned by a trainer or mod script, without needing Xenia multiplayer or Freeroam connection.

First pass:
Create the offline-safe trainer AI controller scaffold:
- tools/codered_trainer_ai_controller_v1.py
- CodeRED_Trainer_AI_Menu_v1.bat
- data/codered/trainer_ai_profile_v1.json
- docs/codered/trainer_ai_control_handoff_v1.md

The controller should:
- accept numbered commands from a menu
- write scratch/codered_trainer_ai_state.json
- write scratch/codered_trainer_ai_action_plan.json
- append scratch/codered_trainer_ai_commands.jsonl
- write logs/codered_trainer_ai_controller.log
- support commands: spawn, follow, guard, defend, attack, regroup, mount, dismount, idle, dismiss, status
- remain independent of Xenia and independent of a specific trainer for this first pass

Important:
Do not delete Xenia notes. Archive Xenia work as paused. Do not build anything for public online cheating or anti-cheat bypass. Keep this singleplayer/offline/private.
```

## Notes to preserve from Xenia phase

Keep these as paused research:
- `docs/codered/rdr_netplay_pass_l_v14_singleplayer_host.md`
- `docs/codered/rdr_netplay_profile.json`
- `docs/codered/rdr_private_host_contract.json`
- `logs/CodeRED_Xenia_RDR_Pass_L_v14_Changelog_2026-05-01.md`
- `logs/CodeRED_Xenia_RDR_Pass_K_v13_Changelog_2026-05-01.md`
- `logs/INDEX_CODERED.md`
- `Xenia Emulator Improvement Suggestions.txt`

Xenia may still be useful later, but it is not the shortest path to AI-controlled visible companions.
