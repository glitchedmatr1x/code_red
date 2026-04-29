#include <pch.h>
#include "Source/CodeRedFactionWar/code_red_factionwar_plugin_v26.h"

BOOL APIENTRY DllMain(HMODULE hModule, DWORD reason, LPVOID)
{
    switch (reason)
    {
    case DLL_PROCESS_ATTACH:
        Application::Initialize(hModule);
        break;
    case DLL_PROCESS_DETACH:
        Application::Shutdown(hModule);
        break;
    default:
        break;
    }
    return TRUE;
}
