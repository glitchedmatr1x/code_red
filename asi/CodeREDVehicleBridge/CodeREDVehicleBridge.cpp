// Code RED Vehicle Bridge ASI scaffold
// Research-only starter: add ScriptHookRDR includes/libs locally.

#include <windows.h>
#include <fstream>
#include <string>

static HMODULE g_module = nullptr;

static void Log(const std::string& line)
{
    std::ofstream f("CodeREDVehicleBridge.log", std::ios::app);
    f << line << "\n";
}

static DWORD WINAPI MainThread(LPVOID)
{
    Log("Code RED Vehicle Bridge loaded.");
    Log("TODO: attach ScriptHookRDR native-call layer here after WSC research maps vehicle activation.");

    // Suggested first experiment once native wrappers are available:
    // - resolve player position
    // - create/spawn car01x/truck01x through the same native family seen in playercar/vehicle_generator
    // - register/activate vehicle brain/seat/controls
    // - log failures rather than crashing the game

    while (true)
    {
        if (GetAsyncKeyState(VK_F7) & 1)
        {
            Log("F7 pressed: placeholder vehicle activation test hook.");
        }
        if (GetAsyncKeyState(VK_END) & 1)
        {
            Log("END pressed: unloading worker loop.");
            break;
        }
        Sleep(50);
    }
    FreeLibraryAndExitThread(g_module, 0);
    return 0;
}

BOOL APIENTRY DllMain(HMODULE hModule, DWORD reason, LPVOID)
{
    if (reason == DLL_PROCESS_ATTACH)
    {
        g_module = hModule;
        DisableThreadLibraryCalls(hModule);
        CreateThread(nullptr, 0, MainThread, nullptr, 0, nullptr);
    }
    return TRUE;
}
