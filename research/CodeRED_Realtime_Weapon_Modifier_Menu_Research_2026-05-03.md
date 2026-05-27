# Code RED Realtime Weapon Modifier Menu Research — 2026-05-03

## Question

Can Code RED make realtime modifiers with the menu for things like weapons?

## Answer

Yes. The right path is the ScriptHook / AI Trainer menu lane, using verified runtime native/wrapper calls.

Do not try to edit `tune_d11generic.rpf` while the game is running. Tune/RPF work belongs in the archive patch lane and may be loaded/cached by the game.

## Existing local source clue

The uploaded Code RED source includes:

```text
research/menu resources/natives.h
```

That file includes weapon wrapper leads such as:

```text
GIVE_WEAPON_TO_ACTOR
ACTOR_PUT_WEAPON_IN_HAND
ACTOR_HAS_WEAPON
DELETE_WEAPON_FROM_ACTOR
GET_WEAPON_IN_HAND
ACTOR_SET_WEAPON_AMMO
ACTOR_ADD_WEAPON_AMMO
ACTOR_GET_WEAPON_AMMO
GET_AMMOENUM_FOR_WEAPONENUM
ACTOR_ADD_INV_AMMO
SET_WEAPON_GOLD
GET_WEAPON_GOLD
```

This means the next pass should be runtime proof, not guessed names.

## Files added

```text
docs/script_workflow/REALTIME_WEAPON_MODIFIERS.md
docs/script_workflow/native_registry/candidate_weapon_runtime_natives.csv
```

## Safe first feature set

```text
Weapon Modifiers
  Player Weapon
    Show current weapon
    Give selected weapon
    Equip selected weapon
    Refill ammo
    Set ammo amount
    Toggle gold weapon

  Companion Weapon
    Give selected weapon to spawned companion
    Equip companion weapon
    Refill companion ammo
```

## Runtime proof order

1. Add menu page that only logs selected option.
2. Prove `GET_WEAPON_IN_HAND(player)`.
3. Prove `ACTOR_HAS_WEAPON(player, weaponEnum)`.
4. Prove `GIVE_WEAPON_TO_ACTOR(player, weaponEnum, ammoCount, ...)` with one safe weapon enum.
5. Prove `ACTOR_PUT_WEAPON_IN_HAND(player, weaponEnum, ...)`.
6. Prove `ACTOR_ADD_WEAPON_AMMO` or `ACTOR_SET_WEAPON_AMMO`.
7. Add companion weapon commands only after player weapon proof passes.
8. Keep damage/spread/fire-rate controls experimental until exact behavior is proven.

## Experimental later

```text
SET_GLOBAL_ACTOR_WEAPON_BIAS
AI_SET_WEAPON_MAX_RANGE / MIN_RANGE / DESIRED_RANGE
SET_FACTION_TO_FACTION_DAMAGE_SCALE_FACTOR
SET_PHOSPHORUS_AMMO_ACTIVE
FIRE_SET_GUNS_BLAZING_ACTIVE
_DLC_SHOTGUN_SPREAD_OVERRIDE
```

These should not be added to the real menu until reset behavior and runtime safety are proven.
