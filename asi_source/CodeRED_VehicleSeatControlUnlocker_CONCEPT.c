/*
Code RED Vehicle Seat/Control Unlocker - runtime test concept

This is source/reference for the ASI lane, not a ready-made compiled binary.
Build it inside the same ScriptHookRDR/native environment used by your trainer.

Starting point is the proven trainer chain:
  SET_VEHICLE_ALLOWED_TO_DRIVE(vehicle, true);
  ENABLE_VEHICLE_SEAT(vehicle, 0, true);
  SET_ACTOR_AUTO_TRANSITION_TO_DRIVER_SEAT(player, true);
  SET_ACTOR_IN_VEHICLE(player, vehicle, 0);
  START_VEHICLE(vehicle);
  SET_VEHICLE_ENGINE_RUNNING(vehicle, true);

Code RED runtime test behavior:
  F7: toggle seat unlock loop for nearest 1193/1194 vehicle
  F8: try driver seat handoff
  F9: passenger/gunner lane; keep NPC driver if present
  F10: disable unlock loop

Important:
  - Whitelist 1193 Truck01 and 1194 Car01 first.
  - Reapply seat enable every tick/half-second because WSCs may disable seats again.
  - Do not globally unlock every wagon until the whitelist path is proven.
*/

#include <stdint.h>
#include <stdbool.h>

// Pseudocode placeholders.
// Replace these with the actual types/helpers from your ScriptHook/Trainer SDK.
typedef int Actor;
typedef struct { float x, y, z; } vector3;

extern Actor self;

// Native calls expected from the RDR trainer/native layer.
extern int GET_ACTOR_ENUM(Actor actor);
extern int GET_NUM_AVAILABLE_SEATS(Actor vehicle);
extern void ENABLE_VEHICLE_SEAT(Actor vehicle, int seat, bool enabled);
extern void SET_VEHICLE_ALLOWED_TO_DRIVE(Actor vehicle, bool enabled);
extern void START_VEHICLE(Actor vehicle);
extern void SET_VEHICLE_ENGINE_RUNNING(Actor vehicle, bool running);
extern void SET_VEHICLE_EJECTION_ENABLED(Actor vehicle, bool enabled);
extern void SET_ACTOR_AUTO_TRANSITION_TO_DRIVER_SEAT(Actor actor, int enabled);
extern void SET_ACTOR_IN_VEHICLE(Actor actor, Actor vehicle, int seat);

// TODO: implement using existing trainer pool/entity scan helpers.
Actor CodeRED_FindNearestTargetVehicle(void);

static bool CodeRED_IsTargetVehicle(Actor vehicle)
{
    int ae = GET_ACTOR_ENUM(vehicle);
    return ae == 1193 || ae == 1194; // Truck01 / Car01
}

static void CodeRED_EnableAllSeatsAndControls(Actor vehicle)
{
    if (!CodeRED_IsTargetVehicle(vehicle)) return;

    SET_VEHICLE_ALLOWED_TO_DRIVE(vehicle, true);
    SET_VEHICLE_EJECTION_ENABLED(vehicle, false);

    int seats = GET_NUM_AVAILABLE_SEATS(vehicle);
    if (seats < 0) seats = 0;
    if (seats > 32) seats = 32;

    for (int seat = 0; seat < seats; ++seat)
    {
        ENABLE_VEHICLE_SEAT(vehicle, seat, true);
    }

    START_VEHICLE(vehicle);
    SET_VEHICLE_ENGINE_RUNNING(vehicle, true);
}

static void CodeRED_TryDriverSeat(Actor vehicle)
{
    if (!CodeRED_IsTargetVehicle(vehicle)) return;

    CodeRED_EnableAllSeatsAndControls(vehicle);
    SET_ACTOR_AUTO_TRANSITION_TO_DRIVER_SEAT(self, 1);
    SET_ACTOR_IN_VEHICLE(self, vehicle, 0);
}

static void CodeRED_TryPassengerSeat(Actor vehicle)
{
    if (!CodeRED_IsTargetVehicle(vehicle)) return;

    CodeRED_EnableAllSeatsAndControls(vehicle);

    // First safe guess: seat 1.
    // Later tests can cycle 1..N and log which seats work.
    SET_ACTOR_AUTO_TRANSITION_TO_DRIVER_SEAT(self, 0);
    SET_ACTOR_IN_VEHICLE(self, vehicle, 1);
}
