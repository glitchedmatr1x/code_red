#include <pch.h>
#include "../CodeRedFactionWar/code_red_factionwar_plugin_v26.h"

void Application::Initialize(HMODULE _Module)
{
    ScriptRegister(_Module, []
    {
        while (true)
        {
            CodeRedFactionWarV26::Update();
            ScriptWait(0);
        }
    });
}

void Application::Shutdown(HMODULE _Module)
{
    CodeRedFactionWarV26::Shutdown();
    REDHOOK::ResetInputCache();
    ScriptUnregister(_Module);
}
