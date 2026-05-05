/*
   Code RED Camp Car Probe v1
   Runtime proof target for adding a car near camp without replacing the camp.

   Purpose:
   - Stand near/inside the player camp.
   - Press F5 to spawn ACTOR_VEHICLE_Car01 a few meters beside the player.
   - Press F6 to put the player in the spawned car.
   - Press F7 to re-apply vehicle tuning.
   - Press F8 to delete the spawned probe car.

   Boundary:
   - This is a runtime proof only.
   - It does not install into game archives.
   - It does not replace camp templates, props, or placement files.
*/

#include "types.h"
#include "constants.h"
#include "intrinsics.h"
#include "natives.h"
#include "RDR/natives32.h"
#include "RDR/consts32.h"

static Layout g_campCarLayout = 0;
static Actor g_player = 0;
static Actor g_campCar = 0;
static int g_spawnCount = 0;
static int g_lastSpawnOk = 0;
static int g_lastF5 = 0;
static int g_lastF6 = 0;
static int g_lastF7 = 0;
static int g_lastF8 = 0;
static float g_speedCap = 16.0f;

static void CR_Print(const char* text)
{
    _CLEAR_PRINTS();
    _PRINT_SUBTITLE(text, 3000.0f, true, 1, 0, 0, 0, 0);
}

static int CR_KeyPressedOnce(int key, int* previous)
{
    int now = _IS_KEY_PRESSED(key);
    int fired = 0;
    if (now && !(*previous))
    {
        fired = 1;
    }
    *previous = now;
    return fired;
}

static void CR_ZeroVector(vector3* value)
{
    value->x = 0.0f;
    value->y = 0.0f;
    value->z = 0.0f;
}

static void CR_EnsureLayout(void)
{
    if (!_IS_LAYOUT_VALID(g_campCarLayout))
    {
        g_campCarLayout = CREATE_LAYOUT("CodeREDCampCarProbeV1");
    }
}

static void CR_TuneCar(Actor vehicle)
{
    if (!IS_ACTOR_VALID(vehicle))
    {
        CR_Print("CODE RED CAMP CAR > Tune failed: invalid car");
        return;
    }
    if (!IS_ACTOR_VEHICLE(vehicle))
    {
        CR_Print("CODE RED CAMP CAR > Tune failed: not vehicle");
        return;
    }

    ENABLE_VEHICLE_SEAT(vehicle, 0, 1);
    SET_VEHICLE_ALLOWED_TO_DRIVE(vehicle, 1);
    SET_VEHICLE_ENGINE_RUNNING(vehicle, 1);
    VEHICLE_SET_HANDBRAKE(vehicle, 0);
    SET_ACTOR_MAX_SPEED(vehicle, g_speedCap);
    SET_ACTOR_MAX_SPEED_ABSOLUTE(vehicle, g_speedCap);
    SET_ACTOR_SPEED(vehicle, 0.0f);
    START_VEHICLE(vehicle);
    CR_Print("CODE RED CAMP CAR > Tune applied");
}

static void CR_DeleteCampCar(void)
{
    Actor existing = FIND_ACTOR_IN_LAYOUT(g_campCarLayout, "CodeREDCampCar01");
    if (IS_ACTOR_VALID(existing))
    {
        DESTROY_ACTOR(existing);
        CR_Print("CODE RED CAMP CAR > Deleted probe car");
    }
    else if (IS_ACTOR_VALID(g_campCar))
    {
        DESTROY_ACTOR(g_campCar);
        CR_Print("CODE RED CAMP CAR > Deleted last car");
    }
    else
    {
        CR_Print("CODE RED CAMP CAR > No probe car to delete");
    }

    g_campCar = 0;
    g_lastSpawnOk = 0;
}

static void CR_PutPlayerInCar(void)
{
    g_player = GET_PLAYER_ACTOR(0);
    if (IS_ACTOR_VALID(g_player) && IS_ACTOR_VALID(g_campCar))
    {
        SET_ACTOR_IN_VEHICLE(g_player, g_campCar, 0);
        CR_Print("CODE RED CAMP CAR > Player entered car");
    }
    else
    {
        CR_Print("CODE RED CAMP CAR > Need player and car");
    }
}

static void CR_SpawnCampCar(void)
{
    vector3 spawnPos;
    vector3 spawnRot;

    CR_EnsureLayout();
    CR_DeleteCampCar();

    CR_ZeroVector(&spawnPos);
    CR_ZeroVector(&spawnRot);

    g_player = GET_PLAYER_ACTOR(0);
    if (IS_ACTOR_VALID(g_player))
    {
        GET_POSITION(g_player, &spawnPos);
        spawnPos.x = spawnPos.x + 4.0f;
        spawnPos.y = spawnPos.y + 2.0f;
    }

    STREAMING_REQUEST_ACTOR(ACTOR_VEHICLE_Car01, 1, 1);
    g_campCar = CREATE_ACTOR_IN_LAYOUT(g_campCarLayout, "CodeREDCampCar01", ACTOR_VEHICLE_Car01, spawnPos, spawnRot);

    if (IS_ACTOR_VALID(g_campCar))
    {
        g_spawnCount = g_spawnCount + 1;
        g_lastSpawnOk = 1;
        CR_TuneCar(g_campCar);
        CR_Print("CODE RED CAMP CAR > Car01 spawned near camp/player");
    }
    else
    {
        g_lastSpawnOk = 0;
        CR_Print("CODE RED CAMP CAR > Spawn failed");
    }
}

static void CR_ShowStatus(void)
{
    if (g_lastSpawnOk)
    {
        CR_Print("CODE RED CAMP CAR > Ready: F5 spawn / F6 enter / F7 tune / F8 delete");
    }
    else
    {
        CR_Print("CODE RED CAMP CAR > Stand at camp. F5 spawns Car01 nearby.");
    }
}

static void CR_HandleInput(void)
{
    if (CR_KeyPressedOnce(KEY_F5, &g_lastF5))
    {
        CR_SpawnCampCar();
    }
    if (CR_KeyPressedOnce(KEY_F6, &g_lastF6))
    {
        CR_PutPlayerInCar();
    }
    if (CR_KeyPressedOnce(KEY_F7, &g_lastF7))
    {
        CR_TuneCar(g_campCar);
    }
    if (CR_KeyPressedOnce(KEY_F8, &g_lastF8))
    {
        CR_DeleteCampCar();
    }
}

void main(void)
{
    ADD_PERSISTENT_SCRIPT(_GET_ID_OF_THIS_SCRIPT());
    CR_EnsureLayout();
    CR_ShowStatus();

    while (true)
    {
        CR_HandleInput();
        WAIT(0);
    }
}
