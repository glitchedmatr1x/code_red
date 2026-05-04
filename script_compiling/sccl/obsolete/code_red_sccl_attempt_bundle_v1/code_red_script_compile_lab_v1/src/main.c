/*
   Code RED Compiled Script Menu v1
   Source-first compile proof target for the Script Workshop / SC-CL lane.

   This is the first real menu-shaped script, upgraded from the tiny vehicle
   probe. It is intentionally conservative:
   - no archive installation
   - no compiled-output promotion
   - no unproven native calls beyond the current proof header
   - function-key navigation only

   Controls:
   F5 = show menu / next section
   F6 = next option
   F7 = execute selected option
   F8 = hide menu
*/

#include "../include/types.h"
#include "../include/constants.h"
#include "../include/intrinsics.h"
#include "../include/natives.h"
#include "../include/RDR/natives32.h"
#include "../include/RDR/consts32.h"

#define CR_SECTION_VEHICLES 0
#define CR_SECTION_PLAYER   1
#define CR_SECTION_DEBUG    2
#define CR_SECTION_COUNT    3

#define CR_VEHICLE_CAR      0
#define CR_VEHICLE_TRUCK    1
#define CR_VEHICLE_DELETE   2
#define CR_VEHICLE_TUNE     3
#define CR_VEHICLE_COUNT    4

#define CR_PLAYER_ENTER     0
#define CR_PLAYER_CLEAR     1
#define CR_PLAYER_COUNT     2

#define CR_DEBUG_STATUS     0
#define CR_DEBUG_KEYS       1
#define CR_DEBUG_COUNT      2

static Layout g_codeRedLayout = 0;
static Actor g_player = 0;
static Actor g_vehicle = 0;
static int g_selectedVehicle = ACTOR_VEHICLE_Car01;
static float g_speedCap = 18.0f;
static int g_menuVisible = 1;
static int g_section = CR_SECTION_VEHICLES;
static int g_option = 0;
static int g_lastSpawnOk = 0;
static int g_spawnCount = 0;
static int g_lastF5 = 0;
static int g_lastF6 = 0;
static int g_lastF7 = 0;
static int g_lastF8 = 0;

static void CR_Print(const char* text)
{
    _CLEAR_PRINTS();
    _PRINT_SUBTITLE(text, 3000, 1, 1, 1);
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

static void CR_EnsureLayout(void)
{
    if (!_IS_LAYOUT_VALID(g_codeRedLayout))
    {
        g_codeRedLayout = CREATE_LAYOUT("CodeREDCompiledMenuV1");
    }
}

static void CR_SetVehicleModel(int actorModel)
{
    g_selectedVehicle = actorModel;
    if (actorModel == ACTOR_VEHICLE_Truck01)
    {
        CR_Print("CODE RED MENU > VEHICLES > Truck01 selected");
    }
    else
    {
        CR_Print("CODE RED MENU > VEHICLES > Car01 selected");
    }
}

static void CR_DestroyVehicle(void)
{
    Actor existing = FIND_ACTOR_IN_LAYOUT(g_codeRedLayout, "CodeREDMenuVehicle");
    if (IS_ACTOR_VALID(existing))
    {
        DESTROY_ACTOR(existing);
        CR_Print("CODE RED MENU > VEHICLES > Vehicle deleted");
    }
    else if (IS_ACTOR_VALID(g_vehicle))
    {
        DESTROY_ACTOR(g_vehicle);
        CR_Print("CODE RED MENU > VEHICLES > Last vehicle deleted");
    }
    else
    {
        CR_Print("CODE RED MENU > VEHICLES > No vehicle to delete");
    }
    g_vehicle = 0;
    g_lastSpawnOk = 0;
}

static void CR_ApplyTune(Actor vehicle)
{
    if (!IS_ACTOR_VALID(vehicle))
    {
        CR_Print("CODE RED MENU > VEHICLES > Tune failed: invalid actor");
        return;
    }
    if (!IS_ACTOR_VEHICLE(vehicle))
    {
        CR_Print("CODE RED MENU > VEHICLES > Tune failed: not a vehicle");
        return;
    }

    ENABLE_VEHICLE_SEAT(vehicle, 0, 1);
    SET_VEHICLE_ALLOWED_TO_DRIVE(vehicle, 1);
    SET_VEHICLE_ENGINE_RUNNING(vehicle, 1);
    VEHICLE_SET_HANDBRAKE(vehicle, 0);
    SET_ACTOR_MAX_SPEED(vehicle, g_speedCap);
    SET_ACTOR_MAX_SPEED_ABSOLUTE(vehicle, g_speedCap);
    SET_ACTOR_SPEED(vehicle, g_speedCap);
    START_VEHICLE(vehicle);
    CR_Print("CODE RED MENU > VEHICLES > Tune applied");
}

static void CR_PutPlayerInVehicle(void)
{
    g_player = GET_PLAYER_ACTOR(0);
    if (IS_ACTOR_VALID(g_player) && IS_ACTOR_VALID(g_vehicle))
    {
        SET_ACTOR_IN_VEHICLE(g_player, g_vehicle, 0);
        CR_Print("CODE RED MENU > PLAYER > Entered vehicle");
    }
    else
    {
        CR_Print("CODE RED MENU > PLAYER > Need player and vehicle");
    }
}

static void CR_SpawnVehicle(int actorModel)
{
    CR_EnsureLayout();
    CR_DestroyVehicle();

    g_player = GET_PLAYER_ACTOR(0);
    STREAMING_REQUEST_ACTOR(actorModel, 1, 1);
    g_vehicle = CREATE_ACTOR_IN_LAYOUT(g_codeRedLayout, "CodeREDMenuVehicle", actorModel, 0.0f, 0.0f, 0.0f, 0.0f);

    if (IS_ACTOR_VALID(g_vehicle))
    {
        g_lastSpawnOk = 1;
        g_spawnCount = g_spawnCount + 1;
        CR_ApplyTune(g_vehicle);
        if (IS_ACTOR_VALID(g_player))
        {
            SET_ACTOR_IN_VEHICLE(g_player, g_vehicle, 0);
        }
        if (actorModel == ACTOR_VEHICLE_Truck01)
        {
            CR_Print("CODE RED MENU > VEHICLES > Truck01 spawned");
        }
        else
        {
            CR_Print("CODE RED MENU > VEHICLES > Car01 spawned");
        }
    }
    else
    {
        g_lastSpawnOk = 0;
        CR_Print("CODE RED MENU > VEHICLES > Spawn failed");
    }
}

static int CR_SectionOptionCount(void)
{
    if (g_section == CR_SECTION_PLAYER)
    {
        return CR_PLAYER_COUNT;
    }
    if (g_section == CR_SECTION_DEBUG)
    {
        return CR_DEBUG_COUNT;
    }
    return CR_VEHICLE_COUNT;
}

static void CR_ResetOption(void)
{
    int count = CR_SectionOptionCount();
    if (g_option >= count)
    {
        g_option = 0;
    }
    if (g_option < 0)
    {
        g_option = 0;
    }
}

static void CR_ShowMenu(void)
{
    if (!g_menuVisible)
    {
        return;
    }

    CR_ResetOption();

    if (g_section == CR_SECTION_VEHICLES)
    {
        if (g_option == CR_VEHICLE_CAR)
        {
            CR_Print("CODE RED MENU > VEHICLES [F7] Spawn Car01");
        }
        else if (g_option == CR_VEHICLE_TRUCK)
        {
            CR_Print("CODE RED MENU > VEHICLES [F7] Spawn Truck01");
        }
        else if (g_option == CR_VEHICLE_DELETE)
        {
            CR_Print("CODE RED MENU > VEHICLES [F7] Delete vehicle");
        }
        else
        {
            CR_Print("CODE RED MENU > VEHICLES [F7] Apply tune");
        }
    }
    else if (g_section == CR_SECTION_PLAYER)
    {
        if (g_option == CR_PLAYER_ENTER)
        {
            CR_Print("CODE RED MENU > PLAYER [F7] Put player in vehicle");
        }
        else
        {
            CR_Print("CODE RED MENU > PLAYER [F7] Clear prints");
        }
    }
    else
    {
        if (g_option == CR_DEBUG_STATUS)
        {
            if (g_lastSpawnOk)
            {
                CR_Print("CODE RED MENU > DEBUG > Last spawn OK");
            }
            else
            {
                CR_Print("CODE RED MENU > DEBUG > No successful spawn yet");
            }
        }
        else
        {
            CR_Print("CODE RED MENU > DEBUG > F5 section / F6 option / F7 run / F8 hide");
        }
    }
}

static void CR_NextSection(void)
{
    g_menuVisible = 1;
    g_section = g_section + 1;
    if (g_section >= CR_SECTION_COUNT)
    {
        g_section = 0;
    }
    g_option = 0;
    CR_ShowMenu();
}

static void CR_NextOption(void)
{
    g_menuVisible = 1;
    g_option = g_option + 1;
    if (g_option >= CR_SectionOptionCount())
    {
        g_option = 0;
    }
    CR_ShowMenu();
}

static void CR_ExecuteVehicleOption(void)
{
    if (g_option == CR_VEHICLE_CAR)
    {
        CR_SetVehicleModel(ACTOR_VEHICLE_Car01);
        CR_SpawnVehicle(ACTOR_VEHICLE_Car01);
    }
    else if (g_option == CR_VEHICLE_TRUCK)
    {
        CR_SetVehicleModel(ACTOR_VEHICLE_Truck01);
        CR_SpawnVehicle(ACTOR_VEHICLE_Truck01);
    }
    else if (g_option == CR_VEHICLE_DELETE)
    {
        CR_DestroyVehicle();
    }
    else
    {
        CR_ApplyTune(g_vehicle);
    }
}

static void CR_ExecutePlayerOption(void)
{
    if (g_option == CR_PLAYER_ENTER)
    {
        CR_PutPlayerInVehicle();
    }
    else
    {
        _CLEAR_PRINTS();
    }
}

static void CR_ExecuteDebugOption(void)
{
    if (g_option == CR_DEBUG_STATUS)
    {
        if (g_lastSpawnOk)
        {
            CR_Print("CODE RED MENU > DEBUG > Spawn status OK");
        }
        else
        {
            CR_Print("CODE RED MENU > DEBUG > Spawn status waiting");
        }
    }
    else
    {
        CR_Print("CODE RED MENU > DEBUG > F5 section / F6 option / F7 run / F8 hide");
    }
}

static void CR_ExecuteOption(void)
{
    g_menuVisible = 1;
    CR_ResetOption();
    if (g_section == CR_SECTION_PLAYER)
    {
        CR_ExecutePlayerOption();
    }
    else if (g_section == CR_SECTION_DEBUG)
    {
        CR_ExecuteDebugOption();
    }
    else
    {
        CR_ExecuteVehicleOption();
    }
}

static void CR_HandleInput(void)
{
    if (CR_KeyPressedOnce(KEY_F5, &g_lastF5))
    {
        CR_NextSection();
    }
    if (CR_KeyPressedOnce(KEY_F6, &g_lastF6))
    {
        CR_NextOption();
    }
    if (CR_KeyPressedOnce(KEY_F7, &g_lastF7))
    {
        CR_ExecuteOption();
    }
    if (CR_KeyPressedOnce(KEY_F8, &g_lastF8))
    {
        g_menuVisible = 0;
        CR_Print("CODE RED MENU > Hidden. Press F5 to show.");
    }
}

void main(void)
{
    ADD_PERSISTENT_SCRIPT(_GET_ID_OF_THIS_SCRIPT());
    CR_EnsureLayout();
    CR_Print("CODE RED MENU v1 ready: F5 section / F6 option / F7 run / F8 hide");

    while (true)
    {
        CR_HandleInput();
        WAIT(0);
    }
}
