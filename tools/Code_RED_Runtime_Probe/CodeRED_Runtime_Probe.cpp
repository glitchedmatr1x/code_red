// Code RED Runtime Probe
// Manual-only ScriptHookRDR runtime diagnostics for SP sector/UI experiments.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <string>

namespace codered_runtime_probe {

using KeyboardHandler = void(*)(DWORD, WORD, BYTE, BOOL, BOOL, BOOL, BOOL);
using ScriptRegisterFn = void(*)(HMODULE, void(*)());
using ScriptUnregisterFn = void(*)(HMODULE);
using KeyboardHandlerRegisterFn = void(*)(KeyboardHandler);
using KeyboardHandlerUnregisterFn = void(*)(KeyboardHandler);
using ScriptWaitFn = void(*)(DWORD);
using NativeInitFn = void(*)(unsigned long long);
using NativePush64Fn = void(*)(unsigned long long);
using NativeCallFn = unsigned long long*(*)();
using DrawTextFn = void(*)(float, float, const char*, int, int, int, int, int, float, int);

struct Vector3 {
    float x;
    float y;
    float z;
};

struct Config {
    bool enableUiEvents;
    bool enableSectorProbe;
    bool enableMpEvents;
    bool enableScriptLaunchProbe;
    bool drawOverlay;
    int startupDelayMs;
    char singleSector[64];
    char tesSector0[64];
    char tesSector1[64];
    char tesSector2[64];
    char tesSector3[64];
    char uiTestEvent[96];
};

static HMODULE g_module = nullptr;
static HMODULE g_scriptHook = nullptr;
static ScriptRegisterFn g_scriptRegister = nullptr;
static ScriptUnregisterFn g_scriptUnregister = nullptr;
static KeyboardHandlerRegisterFn g_keyboardRegister = nullptr;
static KeyboardHandlerUnregisterFn g_keyboardUnregister = nullptr;
static ScriptWaitFn g_scriptWait = nullptr;
static NativeInitFn g_nativeInit = nullptr;
static NativePush64Fn g_nativePush64 = nullptr;
static NativeCallFn g_nativeCall = nullptr;
static DrawTextFn g_drawText = nullptr;

static volatile LONG g_stopRequested = 0;
static volatile LONG g_registered = 0;
static DWORD g_attachTick = 0;
static DWORD g_lastKeyMs = 0;
static DWORD g_helpUntilTick = 0;
static Config g_config = {};

static std::string exeDir() {
    char exePath[MAX_PATH] = {};
    DWORD len = GetModuleFileNameA(nullptr, exePath, MAX_PATH);
    if (!len || len >= MAX_PATH) return ".\\";
    std::string path(exePath);
    size_t slash = path.find_last_of("\\/");
    return slash == std::string::npos ? ".\\" : path.substr(0, slash + 1);
}

static void ensureDataDirs() {
    std::string data = exeDir() + "data";
    std::string codered = data + "\\codered";
    CreateDirectoryA(data.c_str(), nullptr);
    CreateDirectoryA(codered.c_str(), nullptr);
}

static std::string logPath() {
    ensureDataDirs();
    return exeDir() + "data\\codered\\runtime_probe.log";
}

static std::string configPath() {
    ensureDataDirs();
    return exeDir() + "data\\codered\\runtime_probe.ini";
}

static void writeLog(const char* format, ...) {
    char message[2048] = {};
    va_list args;
    va_start(args, format);
    vsnprintf_s(message, sizeof(message), _TRUNCATE, format, args);
    va_end(args);

    SYSTEMTIME now = {};
    GetLocalTime(&now);
    char line[2300] = {};
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

static int readInt(const char* section, const char* key, int fallback) {
    return GetPrivateProfileIntA(section, key, fallback, configPath().c_str());
}

static void readText(const char* section, const char* key, const char* fallback, char* out, DWORD outSize) {
    GetPrivateProfileStringA(section, key, fallback, out, outSize, configPath().c_str());
}

static void loadConfig() {
    g_config.enableUiEvents = readBool("runtime_probe", "enable_ui_events", false);
    g_config.enableSectorProbe = readBool("runtime_probe", "enable_sector_probe", true);
    g_config.enableMpEvents = readBool("runtime_probe", "enable_mp_events", false);
    g_config.enableScriptLaunchProbe = readBool("runtime_probe", "enable_script_launch_probe", false);
    g_config.drawOverlay = readBool("runtime_probe", "draw_overlay", false);
    g_config.startupDelayMs = readInt("runtime_probe", "startup_delay_ms", 15000);
    readText("sectors", "single_sector", "mp_tes_coop01ax", g_config.singleSector, sizeof(g_config.singleSector));
    readText("sectors", "tes_0", "mp_tes_coop01ax", g_config.tesSector0, sizeof(g_config.tesSector0));
    readText("sectors", "tes_1", "mp_tes_coop01bx", g_config.tesSector1, sizeof(g_config.tesSector1));
    readText("sectors", "tes_2", "mp_tes_coop01cx", g_config.tesSector2, sizeof(g_config.tesSector2));
    readText("sectors", "tes_3", "mp_tes_coop02x", g_config.tesSector3, sizeof(g_config.tesSector3));
    readText("ui", "harmless_test_event", "CodeRED_RuntimeProbe_Test", g_config.uiTestEvent, sizeof(g_config.uiTestEvent));
    writeLog("config loaded ui=%d sector=%d mp=%d script_launch=%d startup_delay_ms=%d overlay=%d single=%s group=%s,%s,%s,%s ui_event=%s",
             g_config.enableUiEvents, g_config.enableSectorProbe, g_config.enableMpEvents,
             g_config.enableScriptLaunchProbe, g_config.startupDelayMs, g_config.drawOverlay,
             g_config.singleSector, g_config.tesSector0, g_config.tesSector1,
             g_config.tesSector2, g_config.tesSector3, g_config.uiTestEvent);
}

static FARPROC resolveExport(const char* name, const char* decorated = nullptr) {
    if (!g_scriptHook) return nullptr;
    FARPROC proc = GetProcAddress(g_scriptHook, name);
    if (!proc && decorated) proc = GetProcAddress(g_scriptHook, decorated);
    return proc;
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
    FARPROC nativeInit = resolveExport("nativeInit", "?nativeInit@@YAX_K@Z");
    FARPROC nativePush64 = resolveExport("nativePush64", "?nativePush64@@YAX_K@Z");
    FARPROC nativeCall = resolveExport("nativeCall", "?nativeCall@@YAPEA_KXZ");
    FARPROC drawText = resolveExport("drawText", "?drawText@@YAXMMPEBDHHHHHMH@Z");

    if (logMissing) {
        if (!scriptRegister) writeLog("missing export scriptRegister");
        if (!scriptUnregister) writeLog("missing export scriptUnregister");
        if (!keyRegister) writeLog("missing export keyboardHandlerRegister");
        if (!keyUnregister) writeLog("missing export keyboardHandlerUnregister");
        if (!scriptWait) writeLog("missing export scriptWait");
        if (!nativeInit) writeLog("missing export nativeInit");
        if (!nativePush64) writeLog("missing export nativePush64");
        if (!nativeCall) writeLog("missing export nativeCall");
        if (!drawText) writeLog("optional export drawText unavailable");
    }

    g_scriptRegister = reinterpret_cast<ScriptRegisterFn>(scriptRegister);
    g_scriptUnregister = reinterpret_cast<ScriptUnregisterFn>(scriptUnregister);
    g_keyboardRegister = reinterpret_cast<KeyboardHandlerRegisterFn>(keyRegister);
    g_keyboardUnregister = reinterpret_cast<KeyboardHandlerUnregisterFn>(keyUnregister);
    g_scriptWait = reinterpret_cast<ScriptWaitFn>(scriptWait);
    g_nativeInit = reinterpret_cast<NativeInitFn>(nativeInit);
    g_nativePush64 = reinterpret_cast<NativePush64Fn>(nativePush64);
    g_nativeCall = reinterpret_cast<NativeCallFn>(nativeCall);
    g_drawText = reinterpret_cast<DrawTextFn>(drawText);

    return g_scriptRegister && g_scriptUnregister && g_keyboardRegister && g_keyboardUnregister && g_scriptWait;
}

static bool nativeReady() {
    return g_nativeInit && g_nativePush64 && g_nativeCall;
}

template <typename T>
static void nativePush(T value) {
    unsigned long long value64 = 0;
    static_assert(sizeof(T) <= sizeof(value64), "native argument too large");
    std::memcpy(&value64, &value, sizeof(T));
    g_nativePush64(value64);
}

template <typename R, typename... Args>
static R nativeInvoke(unsigned long long hash, Args... args) {
    g_nativeInit(hash);
    (nativePush(args), ...);
    unsigned long long* result = g_nativeCall();
    if constexpr (std::is_same_v<R, void>) {
        (void)result;
        return;
    } else {
        return *reinterpret_cast<R*>(result);
    }
}

static bool waitGate(const char* action) {
    DWORD now = GetTickCount();
    DWORD elapsed = now - g_attachTick;
    if (elapsed < static_cast<DWORD>(g_config.startupDelayMs)) {
        writeLog("%s skipped: startup delay active elapsed_ms=%lu required_ms=%d",
                 action, elapsed, g_config.startupDelayMs);
        return false;
    }
    return true;
}

static unsigned int joaat(const char* text) {
    unsigned int hash = 0;
    for (const unsigned char* p = reinterpret_cast<const unsigned char*>(text); *p; ++p) {
        unsigned char c = *p;
        if (c >= 'A' && c <= 'Z') c = static_cast<unsigned char>(c + 32);
        hash += c;
        hash += (hash << 10);
        hash ^= (hash >> 6);
    }
    hash += (hash << 3);
    hash ^= (hash >> 11);
    hash += (hash << 15);
    return hash;
}

static bool tryGetPlayerActor(int* outActor) {
    if (!nativeReady()) {
        writeLog("resolve_player_actor skipped: native bridge unavailable");
        return false;
    }
    __try {
        *outActor = nativeInvoke<int>(0xE8CFDD53ULL, 0);
        writeLog("resolve_player_actor OK actor=%d", *outActor);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        writeLog("resolve_player_actor EXCEPTION code=0x%08lx", GetExceptionCode());
        return false;
    }
}

static bool tryGetActorPosition(int actor, Vector3* outPos) {
    if (!nativeReady()) {
        writeLog("read_player_position skipped: native bridge unavailable");
        return false;
    }
    __try {
        nativeInvoke<void>(0x99BD9D6FULL, actor, outPos);
        writeLog("read_player_position OK actor=%d x=%.3f y=%.3f z=%.3f", actor, outPos->x, outPos->y, outPos->z);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        writeLog("read_player_position EXCEPTION actor=%d code=0x%08lx", actor, GetExceptionCode());
        return false;
    }
}

static bool tryGetActorHeading(int actor, float* outHeading) {
    if (!nativeReady()) {
        writeLog("read_player_heading skipped: native bridge unavailable");
        return false;
    }
    __try {
        *outHeading = nativeInvoke<float>(0x42DE39F0ULL, actor);
        writeLog("read_player_heading OK actor=%d heading=%.3f", actor, *outHeading);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        writeLog("read_player_heading EXCEPTION actor=%d code=0x%08lx", actor, GetExceptionCode());
        return false;
    }
}

static bool tryIsWorldLoaded(BOOL* outLoaded) {
    if (!nativeReady()) {
        writeLog("loaded_world_status skipped: native bridge unavailable");
        return false;
    }
    __try {
        *outLoaded = nativeInvoke<BOOL>(0x87B74064ULL);
        writeLog("loaded_world_status OK loaded=%d", *outLoaded);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        writeLog("loaded_world_status EXCEPTION code=0x%08lx", GetExceptionCode());
        return false;
    }
}

static bool tryUiEvent(const char* eventName) {
    if (!g_config.enableUiEvents) {
        writeLog("ui_event skipped: disabled_by_config event=%s", eventName);
        return false;
    }
    if (!nativeReady()) {
        writeLog("ui_event skipped: native bridge unavailable event=%s", eventName);
        return false;
    }
    unsigned int eventHash = joaat(eventName);
    __try {
        nativeInvoke<void>(0xB58825F5ULL, eventHash);
        writeLog("ui_event OK event=%s joaat=0x%08X", eventName, eventHash);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        writeLog("ui_event EXCEPTION event=%s code=0x%08lx", eventName, GetExceptionCode());
        return false;
    }
}

static bool tryEnableSector(const char* sectorName) {
    if (!g_config.enableSectorProbe) {
        writeLog("enable_child_sector skipped: disabled_by_config sector=%s", sectorName);
        return false;
    }
    if (!nativeReady()) {
        writeLog("enable_child_sector skipped: native bridge unavailable sector=%s", sectorName);
        return false;
    }
    __try {
        nativeInvoke<void>(0x7ECE15BEULL, sectorName);
        writeLog("enable_child_sector OK sector=%s", sectorName);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        writeLog("enable_child_sector EXCEPTION sector=%s code=0x%08lx", sectorName, GetExceptionCode());
        return false;
    }
}

static bool tryDisableSector(const char* sectorName) {
    if (!g_config.enableSectorProbe) {
        writeLog("disable_child_sector skipped: disabled_by_config sector=%s", sectorName);
        return false;
    }
    if (!nativeReady()) {
        writeLog("disable_child_sector skipped: native bridge unavailable sector=%s", sectorName);
        return false;
    }
    __try {
        nativeInvoke<void>(0x9E1AE585ULL, sectorName);
        writeLog("disable_child_sector OK sector=%s", sectorName);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        writeLog("disable_child_sector EXCEPTION sector=%s code=0x%08lx", sectorName, GetExceptionCode());
        return false;
    }
}

static void snapshot() {
    writeLog("snapshot BEGIN");
    int actor = 0;
    Vector3 pos = {};
    float heading = 0.0f;
    BOOL worldLoaded = FALSE;

    bool actorOk = tryGetPlayerActor(&actor);
    bool posOk = actorOk ? tryGetActorPosition(actor, &pos) : false;
    bool headingOk = actorOk ? tryGetActorHeading(actor, &heading) : false;
    bool worldOk = tryIsWorldLoaded(&worldLoaded);

    writeLog("snapshot state player_actor=%s:%d coords=%s:%.3f,%.3f,%.3f heading=%s:%.3f world_loaded=%s:%d",
             actorOk ? "ok" : "unavailable", actor,
             posOk ? "ok" : "unavailable", pos.x, pos.y, pos.z,
             headingOk ? "ok" : "unavailable", heading,
             worldOk ? "ok" : "unavailable", worldLoaded);
    writeLog("snapshot current_region_sector=unavailable save_load_state=unavailable session_network_state=unavailable script_count=unavailable");
    writeLog("snapshot END");
}

static void logHelp() {
    writeLog("help F6=snapshot F7=harmless UI event test F8=enable %s F9=disable %s F10=enable TES group F11=disable TES group F12=help",
             g_config.singleSector, g_config.singleSector);
    writeLog("config gates ui=%d sector=%d mp=%d script_launch=%d; MP/script launch actions are intentionally not implemented in this probe",
             g_config.enableUiEvents, g_config.enableSectorProbe, g_config.enableMpEvents, g_config.enableScriptLaunchProbe);
    g_helpUntilTick = GetTickCount() + 8000;
}

static bool throttleKey() {
    DWORD now = GetTickCount();
    if (now - g_lastKeyMs < 180) return true;
    g_lastKeyMs = now;
    return false;
}

static void onKey(DWORD key, WORD repeats, BYTE scanCode, BOOL extended, BOOL alt, BOOL wasDown, BOOL upNow) {
    (void)repeats;
    (void)scanCode;
    (void)extended;
    (void)alt;
    if (upNow || wasDown || throttleKey()) return;

    if (key == VK_F6) {
        writeLog("F6 pressed: state snapshot requested");
        if (waitGate("F6 snapshot")) snapshot();
    } else if (key == VK_F7) {
        writeLog("F7 pressed: harmless UI/log test requested");
        if (waitGate("F7 ui_event")) tryUiEvent(g_config.uiTestEvent);
    } else if (key == VK_F8) {
        writeLog("F8 pressed: enable one TES sector requested sector=%s", g_config.singleSector);
        if (waitGate("F8 enable_single_sector")) {
            writeLog("F8 before enable sector=%s", g_config.singleSector);
            tryEnableSector(g_config.singleSector);
            writeLog("F8 after enable sector=%s", g_config.singleSector);
        }
    } else if (key == VK_F9) {
        writeLog("F9 pressed: disable one TES sector requested sector=%s", g_config.singleSector);
        if (waitGate("F9 disable_single_sector")) {
            writeLog("F9 before disable sector=%s", g_config.singleSector);
            tryDisableSector(g_config.singleSector);
            writeLog("F9 after disable sector=%s", g_config.singleSector);
        }
    } else if (key == VK_F10) {
        writeLog("F10 pressed: enable TES sector group requested");
        if (waitGate("F10 enable_tes_group")) {
            const char* sectors[] = {g_config.tesSector0, g_config.tesSector1, g_config.tesSector2, g_config.tesSector3};
            for (const char* sector : sectors) {
                writeLog("F10 before enable sector=%s", sector);
                tryEnableSector(sector);
                writeLog("F10 after enable sector=%s", sector);
            }
        }
    } else if (key == VK_F11) {
        writeLog("F11 pressed: disable TES sector group requested");
        if (waitGate("F11 disable_tes_group")) {
            const char* sectors[] = {g_config.tesSector0, g_config.tesSector1, g_config.tesSector2, g_config.tesSector3};
            for (const char* sector : sectors) {
                writeLog("F11 before disable sector=%s", sector);
                tryDisableSector(sector);
                writeLog("F11 after disable sector=%s", sector);
            }
        }
    } else if (key == VK_F12) {
        writeLog("F12 pressed: help requested");
        logHelp();
    }
}

static void drawHelpIfRequested() {
    if (!g_config.drawOverlay || !g_drawText) return;
    DWORD now = GetTickCount();
    if (now > g_helpUntilTick) return;
    g_drawText(0.020f, 0.080f, "CodeRED Runtime Probe", 255, 80, 80, 230, 0, 0.020f, 0);
    g_drawText(0.020f, 0.105f, "F6 snapshot | F8/F9 one TES sector | F10/F11 TES group", 235, 235, 235, 220, 0, 0.016f, 0);
    g_drawText(0.020f, 0.128f, "F7 UI test is config-gated. No MP launch actions are present.", 235, 210, 160, 220, 0, 0.015f, 0);
}

static void mainLoop() {
    while (!InterlockedCompareExchange(&g_stopRequested, 0, 0)) {
        drawHelpIfRequested();
        if (g_scriptWait) g_scriptWait(0);
        else Sleep(0);
    }
}

static DWORD WINAPI registrationThread(LPVOID param) {
    HMODULE module = reinterpret_cast<HMODULE>(param);
    writeLog("registration worker started");
    loadConfig();
    ULONGLONG deadline = GetTickCount64() + 30000;
    bool loggedMissingDll = false;
    bool loggedExports = false;

    while (!InterlockedCompareExchange(&g_stopRequested, 0, 0) && GetTickCount64() <= deadline) {
        bool ready = resolveScriptHook(!loggedExports);
        if (!g_scriptHook && !loggedMissingDll) {
            writeLog("ScriptHookRDR.dll not found yet");
            loggedMissingDll = true;
        }
        if (g_scriptHook && !loggedExports) {
            writeLog("ScriptHookRDR.dll found");
            loggedExports = true;
            resolveScriptHook(true);
        }
        if (ready) {
            g_scriptRegister(module, mainLoop);
            g_keyboardRegister(onKey);
            InterlockedExchange(&g_registered, 1);
            writeLog("registration succeeded; manual hotkeys active after startup_delay_ms=%d", g_config.startupDelayMs);
            writeLog("native bridge status: %s", nativeReady() ? "ready" : "unavailable");
            return 0;
        }
        Sleep(500);
    }
    resolveScriptHook(true);
    writeLog("registration failed: required ScriptHookRDR exports unavailable after 30 seconds");
    return 1;
}

} // namespace codered_runtime_probe

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID) {
    using namespace codered_runtime_probe;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(module);
        g_module = module;
        g_attachTick = GetTickCount();
        InterlockedExchange(&g_stopRequested, 0);
        writeLog("ASI attached: CodeRED Runtime Probe");
        HANDLE thread = CreateThread(nullptr, 0, registrationThread, module, 0, nullptr);
        if (thread) CloseHandle(thread);
        else writeLog("registration worker creation failed: %lu", GetLastError());
    } else if (reason == DLL_PROCESS_DETACH) {
        InterlockedExchange(&g_stopRequested, 1);
        writeLog("ASI detach requested");
        if (InterlockedCompareExchange(&g_registered, 0, 0) && g_keyboardUnregister) {
            g_keyboardUnregister(onKey);
            writeLog("keyboard handler unregistered");
        }
        if (InterlockedCompareExchange(&g_registered, 0, 0) && g_scriptUnregister) {
            g_scriptUnregister(module);
            writeLog("script unregistered");
        }
        InterlockedExchange(&g_registered, 0);
        writeLog("ASI detached");
    }
    return TRUE;
}
