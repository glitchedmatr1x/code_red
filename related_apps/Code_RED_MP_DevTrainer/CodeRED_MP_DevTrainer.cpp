// Code RED MP Dev Trainer
// Local/offline ScriptHookRDR diagnostics for restored multiplayer paths.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <string>

namespace codered_mp_dev {

using KeyboardHandler = void(*)(DWORD, WORD, BYTE, BOOL, BOOL, BOOL, BOOL);
using ScriptRegisterFn = void(*)(HMODULE, void(*)());
using ScriptUnregisterFn = void(*)(HMODULE);
using KeyboardHandlerRegisterFn = void(*)(KeyboardHandler);
using KeyboardHandlerUnregisterFn = void(*)(KeyboardHandler);
using ScriptWaitFn = void(*)(DWORD);
using WorldGetAllActorsFn = int(*)(int*, int);

static HMODULE g_module = nullptr;
static HMODULE g_scriptHook = nullptr;
static ScriptRegisterFn g_scriptRegister = nullptr;
static ScriptUnregisterFn g_scriptUnregister = nullptr;
static KeyboardHandlerRegisterFn g_keyboardRegister = nullptr;
static KeyboardHandlerUnregisterFn g_keyboardUnregister = nullptr;
static ScriptWaitFn g_scriptWait = nullptr;
static WorldGetAllActorsFn g_worldGetAllActors = nullptr;
static volatile LONG g_stopRequested = 0;
static volatile LONG g_registered = 0;
static DWORD g_lastKeyMs = 0;

struct Config {
    char gameWish[96];
    char catacombsWorld[128];
    char catacombsProps[128];
    char teleportCatacombs[128];
    char teleportBlackwater[128];
    bool enableLanRoute;
    bool tryTriggerLoad;
    bool tryStartGameWish;
};

static Config g_config = {};

static std::string exeDir() {
    char exePath[MAX_PATH] = {};
    DWORD len = GetModuleFileNameA(nullptr, exePath, MAX_PATH);
    if (!len || len >= MAX_PATH) return ".\\";
    std::string path(exePath);
    size_t slash = path.find_last_of("\\/");
    return slash == std::string::npos ? ".\\" : path.substr(0, slash + 1);
}

static std::string logPath() {
    std::string logs = exeDir() + "logs";
    CreateDirectoryA(logs.c_str(), nullptr);
    return logs + "\\codered_mp_dev_trainer.log";
}

static std::string configPath() {
    return exeDir() + "data\\codered\\mp_dev_trainer.ini";
}

static void writeLog(const char* format, ...) {
    char message[1024] = {};
    va_list args;
    va_start(args, format);
    vsnprintf_s(message, sizeof(message), _TRUNCATE, format, args);
    va_end(args);
    SYSTEMTIME now = {};
    GetLocalTime(&now);
    char line[1280] = {};
    snprintf(line, sizeof(line), "[%04u-%02u-%02u %02u:%02u:%02u] %s\r\n",
             now.wYear, now.wMonth, now.wDay, now.wHour, now.wMinute, now.wSecond, message);
    HANDLE file = CreateFileA(logPath().c_str(), FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE,
                              nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) return;
    DWORD written = 0;
    WriteFile(file, line, static_cast<DWORD>(strlen(line)), &written, nullptr);
    CloseHandle(file);
}

static bool readBool(const char* section, const char* key, bool fallback) {
    return GetPrivateProfileIntA(section, key, fallback ? 1 : 0, configPath().c_str()) != 0;
}

static void readText(const char* section, const char* key, const char* fallback, char* out, DWORD outSize) {
    GetPrivateProfileStringA(section, key, fallback, out, outSize, configPath().c_str());
}

static void loadConfig() {
    readText("mp", "game_wish", "MULTI_FREE_ROAM", g_config.gameWish, sizeof(g_config.gameWish));
    g_config.enableLanRoute = readBool("mp", "enable_lan_route", true);
    g_config.tryTriggerLoad = readBool("mp", "try_trigger_load", false);
    g_config.tryStartGameWish = readBool("mp", "try_start_game_wish", false);
    readText("sectors", "catacombs_world", "dlc_beh_catacombs01x", g_config.catacombsWorld, sizeof(g_config.catacombsWorld));
    readText("sectors", "catacombs_props", "dlc_beh_catacombs01props01x", g_config.catacombsProps, sizeof(g_config.catacombsProps));
    readText("teleports", "catacombs", "0,0,0", g_config.teleportCatacombs, sizeof(g_config.teleportCatacombs));
    readText("teleports", "blackwater_mp", "0,0,0", g_config.teleportBlackwater, sizeof(g_config.teleportBlackwater));
    writeLog("Config loaded: game_wish=%s lan=%d trigger=%d start=%d catacombs=%s props=%s",
             g_config.gameWish, g_config.enableLanRoute, g_config.tryTriggerLoad, g_config.tryStartGameWish,
             g_config.catacombsWorld, g_config.catacombsProps);
}

static FARPROC resolveExport(const char* name, const char* decorated = nullptr) {
    if (!g_scriptHook) return nullptr;
    FARPROC proc = GetProcAddress(g_scriptHook, name);
    if (!proc && decorated) proc = GetProcAddress(g_scriptHook, decorated);
    return proc;
}

static void missing(const char* name, FARPROC proc, bool logMissing) {
    if (logMissing && !proc) writeLog("Missing ScriptHookRDR export: %s", name);
}

static bool resolveScriptHook(bool logMissing) {
    if (!g_scriptHook) {
        g_scriptHook = GetModuleHandleA("ScriptHookRDR.dll");
        if (!g_scriptHook) g_scriptHook = LoadLibraryA("ScriptHookRDR.dll");
    }
    if (!g_scriptHook) return false;
    FARPROC scriptRegister = resolveExport("scriptRegister", "?scriptRegister@@YAXPEAUHINSTANCE__@@P6AXXZ@Z");
    FARPROC scriptUnregister = resolveExport("scriptUnregister", "?scriptUnregister@@YAXPEAUHINSTANCE__@@@Z");
    FARPROC keyRegister = resolveExport("keyboardHandlerRegister", "?keyboardHandlerRegister@@YAXP6AXKGEHHHH@Z@Z");
    FARPROC keyUnregister = resolveExport("keyboardHandlerUnregister", "?keyboardHandlerUnregister@@YAXP6AXKGEHHHH@Z@Z");
    FARPROC scriptWait = resolveExport("scriptWait", "?scriptWait@@YAXK@Z");
    FARPROC allActors = resolveExport("worldGetAllActors", "?worldGetAllActors@@YAHPEAHH@Z");
    missing("scriptRegister", scriptRegister, logMissing);
    missing("scriptUnregister", scriptUnregister, logMissing);
    missing("keyboardHandlerRegister", keyRegister, logMissing);
    missing("keyboardHandlerUnregister", keyUnregister, logMissing);
    missing("scriptWait", scriptWait, logMissing);
    g_scriptRegister = reinterpret_cast<ScriptRegisterFn>(scriptRegister);
    g_scriptUnregister = reinterpret_cast<ScriptUnregisterFn>(scriptUnregister);
    g_keyboardRegister = reinterpret_cast<KeyboardHandlerRegisterFn>(keyRegister);
    g_keyboardUnregister = reinterpret_cast<KeyboardHandlerUnregisterFn>(keyUnregister);
    g_scriptWait = reinterpret_cast<ScriptWaitFn>(scriptWait);
    g_worldGetAllActors = reinterpret_cast<WorldGetAllActorsFn>(allActors);
    return g_scriptRegister && g_scriptUnregister && g_keyboardRegister && g_keyboardUnregister && g_scriptWait;
}

static bool throttleKey() {
    DWORD now = GetTickCount();
    if (now - g_lastKeyMs < 150) return true;
    g_lastKeyMs = now;
    return false;
}

static void logSkipped(const char* key, const char* action, const char* reason) {
    writeLog("%s attempted: action=%s status=skipped reason=%s", key, action, reason);
}

static void dumpState(const char* key) {
    int actors[512] = {};
    int actorCount = g_worldGetAllActors ? g_worldGetAllActors(actors, 512) : -1;
    writeLog("%s state: registered=%ld hook=%p worldGetAllActors=%s actor_count=%d game_wish=%s lan=%d trigger=%d start=%d",
             key, InterlockedCompareExchange(&g_registered, 0, 0), g_scriptHook,
             g_worldGetAllActors ? "resolved" : "unresolved", actorCount, g_config.gameWish,
             g_config.enableLanRoute, g_config.tryTriggerLoad, g_config.tryStartGameWish);
}

static void onKey(DWORD key, WORD repeats, BYTE scanCode, BOOL extended, BOOL alt, BOOL wasDown, BOOL upNow) {
    (void)repeats;
    (void)scanCode;
    (void)extended;
    (void)alt;
    if (upNow || wasDown || throttleKey()) return;
    if (key == VK_F5) {
        loadConfig();
        writeLog("F5 attempted: action=reload_config status=ok");
    } else if (key == VK_F6) {
        dumpState("F6");
    } else if (key == VK_F7) {
        logSkipped("F7", "open_local_lan_route", "no safe runtime UI route native mapped; use Pass5 XML route");
    } else if (key == VK_F8) {
        logSkipped("F8", "set_game_wish", "NetMachine route is SCXML-owned; no safe ScriptHook native mapped");
    } else if (key == VK_F9) {
        logSkipped("F9", "trigger_multiplayer_load", g_config.tryTriggerLoad ? "trigger native unresolved" : "disabled_by_config");
    } else if (key == VK_F10) {
        logSkipped("F10", "start_game_wish", g_config.tryStartGameWish ? "start native unresolved" : "disabled_by_config");
    } else if (key == VK_F11) {
        writeLog("F11 attempted: action=toggle_catacombs_sectors world=%s props=%s status=skipped reason=sector native unresolved",
                 g_config.catacombsWorld, g_config.catacombsProps);
    } else if (key == VK_F12) {
        logSkipped("F12", "toggle_mp_blackwater_freeroam_sectors", "sector list/native mapping pending");
    } else if (key == VK_NUMPAD1) {
        writeLog("NUM1 attempted: action=teleport_catacombs target=%s status=skipped reason=teleport native unresolved",
                 g_config.teleportCatacombs);
    } else if (key == VK_NUMPAD2) {
        writeLog("NUM2 attempted: action=teleport_blackwater_mp target=%s status=skipped reason=teleport native unresolved",
                 g_config.teleportBlackwater);
    } else if (key == VK_NUMPAD3) {
        dumpState("NUM3");
    }
}

static void mainLoop() {
    while (!InterlockedCompareExchange(&g_stopRequested, 0, 0)) {
        if (g_scriptWait) g_scriptWait(0);
        else Sleep(0);
    }
}

static DWORD WINAPI registrationThread(LPVOID param) {
    HMODULE module = reinterpret_cast<HMODULE>(param);
    writeLog("Registration worker started");
    loadConfig();
    ULONGLONG deadline = GetTickCount64() + 30000;
    bool loggedMissingDll = false;
    bool loggedFoundDll = false;
    bool loggedExports = false;
    while (!InterlockedCompareExchange(&g_stopRequested, 0, 0) && GetTickCount64() <= deadline) {
        bool ready = resolveScriptHook(!loggedExports);
        if (!g_scriptHook && !loggedMissingDll) {
            writeLog("ScriptHookRDR.dll not found yet");
            loggedMissingDll = true;
        } else if (g_scriptHook && !loggedFoundDll) {
            writeLog("ScriptHookRDR.dll found");
            loggedFoundDll = true;
        }
        if (g_scriptHook && !ready) loggedExports = true;
        if (ready) {
            g_scriptRegister(module, mainLoop);
            g_keyboardRegister(onKey);
            InterlockedExchange(&g_registered, 1);
            writeLog("Registration succeeded; hotkeys F5-F12 and NUM1-NUM3 active");
            return 0;
        }
        Sleep(500);
    }
    resolveScriptHook(true);
    writeLog("Registration failed: required ScriptHookRDR exports unavailable after 30 seconds");
    return 1;
}

} // namespace codered_mp_dev

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID) {
    using namespace codered_mp_dev;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(module);
        g_module = module;
        InterlockedExchange(&g_stopRequested, 0);
        writeLog("ASI attached");
        HANDLE thread = CreateThread(nullptr, 0, registrationThread, module, 0, nullptr);
        if (thread) CloseHandle(thread);
        else writeLog("Registration worker creation failed: %lu", GetLastError());
    } else if (reason == DLL_PROCESS_DETACH) {
        InterlockedExchange(&g_stopRequested, 1);
        writeLog("ASI detach requested");
        if (InterlockedCompareExchange(&g_registered, 0, 0) && g_keyboardUnregister) {
            g_keyboardUnregister(onKey);
            writeLog("Keyboard handler unregistered");
        }
        if (InterlockedCompareExchange(&g_registered, 0, 0) && g_scriptUnregister) {
            g_scriptUnregister(module);
            writeLog("Script unregistered");
        }
        InterlockedExchange(&g_registered, 0);
        writeLog("ASI detached");
    }
    return TRUE;
}
