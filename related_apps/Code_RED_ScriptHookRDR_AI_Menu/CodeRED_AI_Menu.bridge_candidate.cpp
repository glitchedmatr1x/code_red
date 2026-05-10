// CodeRED_AI_Menu.cpp
// Conservative ScriptHookRDR in-game menu scaffold.
//
// Codex/build-ready note:
// This source resolves ScriptHookRDR exports dynamically with GetProcAddress instead
// of linking against a ScriptHookRDR import .lib. That keeps the first-pass build
// simple: cl.exe can produce a .asi DLL using only Windows SDK + the repo source.
//
// This pass draws an overlay, loads an editable NPC roster, writes action-plan JSON,
// and can spawn/follow/dismiss actors through ScriptHookRDR native exports.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <algorithm>
#include <cerrno>
#include <cctype>
#include <climits>
#include <cmath>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <fstream>
#include <sstream>
#include <string>
#include <type_traits>
#include <unordered_map>
#include <vector>

namespace codered {

using KeyboardHandler = void(*)(DWORD, WORD, BYTE, BOOL, BOOL, BOOL, BOOL);
using ScriptRegisterFn = void(*)(HMODULE, void(*)());
using ScriptUnregisterFn = void(*)(HMODULE);
using KeyboardHandlerRegisterFn = void(*)(KeyboardHandler);
using KeyboardHandlerUnregisterFn = void(*)(KeyboardHandler);
using ScriptWaitFn = void(*)(DWORD);
using DrawRectFn = void(*)(float, float, float, float, int, int, int, int, float);
using DrawTextFn = void(*)(float, float, const char*, int, int, int, int, int, float, int);
using NativeInitFn = void(*)(unsigned long long);
using NativePush64Fn = void(*)(unsigned long long);
using NativeCallFn = unsigned long long*(*)();
using WorldGetAllActorsFn = int(*)(int*, int);

// ScriptHookRDR font/justification ids from sdk/inc/enums.h.
constexpr int FONT_REDEMPTION = 2;
constexpr int JUSTIFY_LEFT = 0;
constexpr float PI = 3.14159265358979323846f;
constexpr int FACTION_PLAYER = 2;
constexpr int FACTION_US_LAW = 8;
constexpr int FACTION_MEXICAN_BANDITO = 12;
constexpr int FACTION_GENERIC_CRIMINAL = 13;
constexpr int FACTION_CATTLE_RUSTLER = 14;
constexpr int FACTION_INDIAN_RAIDER = 15;
constexpr int FACTION_MEXICAN_SOLDIER = 16;

using Actor = int;
using Layout = int;

struct Vector2 {
    float x;
    float y;
};

struct Vector3 {
    float x;
    float y;
    float z;
};

static HMODULE g_scriptHook = nullptr;
static ScriptRegisterFn g_scriptRegister = nullptr;
static ScriptUnregisterFn g_scriptUnregister = nullptr;
static KeyboardHandlerRegisterFn g_keyboardHandlerRegister = nullptr;
static KeyboardHandlerUnregisterFn g_keyboardHandlerUnregister = nullptr;
static ScriptWaitFn g_scriptWait = nullptr;
static DrawRectFn g_drawRect = nullptr;
static DrawTextFn g_drawText = nullptr;
static NativeInitFn g_nativeInit = nullptr;
static NativePush64Fn g_nativePush64 = nullptr;
static NativeCallFn g_nativeCall = nullptr;
static WorldGetAllActorsFn g_worldGetAllActors = nullptr;
static HMODULE g_module = nullptr;
static volatile LONG g_stopRequested = 0;
static volatile LONG g_registered = 0;
static volatile LONG g_nativeReady = 0;

static bool g_menuOpen = false;
static int g_menuIndex = 0;
static int g_npcIndex = 0;
static bool g_dirtyRoster = true;
static bool g_dirtyActorMap = true;
static bool g_dirtyActions = true;
static bool g_configLoaded = false;
static DWORD g_lastKeyMs = 0;
static Layout g_layout = 0;
static int g_spawnCounter = 0;
static bool g_actorEnumCacheValid = false;
static std::string g_actorEnumCacheRaw;
static int g_actorEnumCacheValue = 0;
static bool g_savedPlayerFaction = false;
static int g_originalPlayerFaction = FACTION_PLAYER;
static int g_playerSideFaction = FACTION_PLAYER;

static std::string g_rosterPath = "data/codered/npc_roster.txt";
static std::string g_actorEnumMapPath = "data/codered/actor_enum_map.csv";
static std::string g_actionsPath = "data/codered/ai_behavior_actions.csv";
static std::string g_actionPlanPath = "scratch/codered_ai_action_plan.json";
static std::string g_mpConnectRequestPath = "scratch/codered_mp_connect_request.json";
static std::string g_mpClientStatusPath = "scratch/codered_mp_client_status.json";
static std::string g_mpBridgeInputPath = "scratch/codered_mp_local_state.json";
static std::string g_mpBridgeWorldPath = "scratch/codered_mp_world_state.json";
static std::string g_mpClientPath = "codered-mp-client.exe";
static std::string g_mpServerHost = "127.0.0.1";
static int g_mpServerPort = 7777;
static std::string g_mpPlayerName = "rdr_asi";
static bool g_mpBareWorldEnabled = true;
static bool g_mpBareWorldDestroyActors = true;
static bool g_mpBareWorldPopulationSuppression = true;
static float g_mpBareWorldRadius = 280.0f;
static int g_mpBareWorldMaxDestroyPerTick = 32;
static int g_mpBareWorldTickMs = 400;
static std::string g_statePath = "scratch/codered_ai_state.json";
static std::string g_overrideRpfPath = "override";
static std::string g_patchStagePath = "game";
static std::string g_contentOverrideName = "content.rpf";
static std::string g_status = "CodeRED AI Menu ready";
static unsigned long long g_mpClientStatusWriteTime = 0;
static unsigned long long g_mpWorldStateWriteTime = 0;
static unsigned int g_mpLastNativeCallSeq = 0;
static bool g_mpLiteActive = false;
static bool g_mpLiteJoined = false;
static bool g_mpSpawnApplied = false;
static bool g_mpChatOpen = false;
static bool g_mpChatControlsSuppressed = false;
static std::string g_mpChatDraft;
static std::string g_mpPendingChat;
static int g_mpLocalPlayerId = -1;
static int g_mpLocalActorEnum = 837;
static unsigned int g_mpStateSeq = 0;
static unsigned int g_mpChatSeq = 0;
static DWORD g_mpPendingChatStartedMs = 0;
static DWORD g_mpLastLocalStateMs = 0;
static DWORD g_mpBareWorldLastTickMs = 0;
static DWORD g_mpBareWorldLastPopulationMs = 0;
static int g_mpBareWorldLastSeen = 0;
static int g_mpBareWorldLastProtected = 0;
static int g_mpBareWorldLastDestroyed = 0;
static int g_mpBareWorldTotalDestroyed = 0;
static bool g_mpNoClipActive = false;
static DWORD g_mpNoClipLastTickMs = 0;
static int g_mpNoClipSpeedIndex = 1;
static bool g_mpLocalGodMode = false;
static bool g_mpTransportPropsetPending = false;
static int g_mpTransportPropset = 0;
static int g_mpTransportPropsetAssetId = 0;
static DWORD g_mpTransportPropsetRequestedMs = 0;
static Vector3 g_mpTransportPropsetPosition = {};
static float g_mpTransportPropsetHeading = 0.0f;
static std::vector<std::string> g_mpChatLines;
static std::vector<std::string> g_mpNoticeLines;
static HWND g_gameWindow = nullptr;
static WNDPROC g_originalWndProc = nullptr;

struct MpRemoteActor {
    int playerId = -1;
    Actor actor = 0;
    int actorEnum = 837;
    Vector3 position = {};
    float heading = 0.0f;
    unsigned int sequence = 0;
    DWORD lastSeenMs = 0;
};

static std::vector<MpRemoteActor> g_mpRemoteActors;

static std::vector<std::string> g_roster;
static std::unordered_map<std::string, int> g_actorEnumMap;
static std::unordered_map<std::string, std::string> g_actionLabels;
static size_t g_actorEnumRowsLoaded = 0;
static std::vector<Actor> g_spawnedActors;
static std::vector<std::string> g_actions = {
    "spawn_selected_npc_request",
    "follow_player_request",
    "guard_position_request",
    "defend_player_request",
    "attack_nearest_hostile_request",
    "idle_spawned_request",
    "wander_spawned_request",
    "regroup_near_player_request",
    "make_spawned_lawmen_request",
    "side_lawman_immunity_request",
    "side_gang_immunity_request",
    "restore_player_faction_request",
    "mp_connect_localhost_request",
    "mp_toggle_bare_world_request",
    "mp_bare_world_purge_request",
    "mp_toggle_bare_world_suppression_request",
    "reload_override_rpf_request",
    "dismiss_ai_guest_request",
    "status_request"
};

static std::string logPath() {
    char exePath[MAX_PATH] = {};
    DWORD len = GetModuleFileNameA(nullptr, exePath, MAX_PATH);
    if (len == 0 || len >= MAX_PATH) {
        return "CodeRED_AI_Menu.log";
    }

    std::string path(exePath);
    size_t slash = path.find_last_of("\\/");
    if (slash == std::string::npos) {
        return "CodeRED_AI_Menu.log";
    }
    return path.substr(0, slash + 1) + "CodeRED_AI_Menu.log";
}

static std::string gameDirectory() {
    char exePath[MAX_PATH] = {};
    DWORD len = GetModuleFileNameA(nullptr, exePath, MAX_PATH);
    if (len == 0 || len >= MAX_PATH) {
        return ".";
    }

    std::string path(exePath);
    size_t slash = path.find_last_of("\\/");
    if (slash == std::string::npos) {
        return ".";
    }
    return path.substr(0, slash);
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
    snprintf(line, sizeof(line),
             "[%04u-%02u-%02u %02u:%02u:%02u] %s\r\n",
             now.wYear, now.wMonth, now.wDay, now.wHour, now.wMinute,
             now.wSecond, message);

    std::string path = logPath();
    HANDLE file = CreateFileA(path.c_str(), FILE_APPEND_DATA,
                              FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr,
                              OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }

    DWORD written = 0;
    WriteFile(file, line, static_cast<DWORD>(strlen(line)), &written, nullptr);
    CloseHandle(file);
}

static FARPROC resolveExport(const char* name, const char* decoratedName = nullptr) {
    if (!g_scriptHook) return nullptr;
    FARPROC proc = GetProcAddress(g_scriptHook, name);
    if (!proc && decoratedName) {
        proc = GetProcAddress(g_scriptHook, decoratedName);
    }
    return proc;
}

static void logMissingExport(const char* name, FARPROC proc) {
    if (!proc) {
        writeLog("Missing ScriptHookRDR export: %s", name);
    }
}

static bool resolveScriptHook(bool logMissingExports) {
    if (!g_scriptHook) {
        g_scriptHook = GetModuleHandleA("ScriptHookRDR.dll");
        if (!g_scriptHook) {
            g_scriptHook = LoadLibraryA("ScriptHookRDR.dll");
        }
    }
    if (!g_scriptHook) return false;

    FARPROC scriptRegisterProc =
        resolveExport("scriptRegister", "?scriptRegister@@YAXPEAUHINSTANCE__@@P6AXXZ@Z");
    FARPROC scriptUnregisterProc =
        resolveExport("scriptUnregister", "?scriptUnregister@@YAXPEAUHINSTANCE__@@@Z");
    FARPROC keyboardRegisterProc = resolveExport(
        "keyboardHandlerRegister", "?keyboardHandlerRegister@@YAXP6AXKGEHHHH@Z@Z");
    FARPROC keyboardUnregisterProc = resolveExport(
        "keyboardHandlerUnregister", "?keyboardHandlerUnregister@@YAXP6AXKGEHHHH@Z@Z");
    FARPROC scriptWaitProc = resolveExport("scriptWait", "?scriptWait@@YAXK@Z");
    FARPROC drawRectProc = resolveExport("drawRect", "?drawRect@@YAXMMMMHHHHM@Z");
    FARPROC drawTextProc =
        resolveExport("drawText", "?drawText@@YAXMMPEBDHHHHHMH@Z");
    FARPROC worldGetAllActorsProc =
        resolveExport("worldGetAllActors", "?worldGetAllActors@@YAHPEAHH@Z");

    if (logMissingExports) {
        logMissingExport("scriptRegister", scriptRegisterProc);
        logMissingExport("scriptUnregister", scriptUnregisterProc);
        logMissingExport("keyboardHandlerRegister", keyboardRegisterProc);
        logMissingExport("keyboardHandlerUnregister", keyboardUnregisterProc);
        logMissingExport("scriptWait", scriptWaitProc);
        logMissingExport("drawRect", drawRectProc);
        logMissingExport("drawText", drawTextProc);
    }

    g_scriptRegister = reinterpret_cast<ScriptRegisterFn>(scriptRegisterProc);
    g_scriptUnregister = reinterpret_cast<ScriptUnregisterFn>(scriptUnregisterProc);
    g_keyboardHandlerRegister = reinterpret_cast<KeyboardHandlerRegisterFn>(keyboardRegisterProc);
    g_keyboardHandlerUnregister = reinterpret_cast<KeyboardHandlerUnregisterFn>(keyboardUnregisterProc);
    g_scriptWait = reinterpret_cast<ScriptWaitFn>(scriptWaitProc);
    g_drawRect = reinterpret_cast<DrawRectFn>(drawRectProc);
    g_drawText = reinterpret_cast<DrawTextFn>(drawTextProc);
    g_worldGetAllActors = reinterpret_cast<WorldGetAllActorsFn>(worldGetAllActorsProc);

    return g_scriptRegister && g_scriptUnregister &&
           g_keyboardHandlerRegister && g_keyboardHandlerUnregister &&
           g_scriptWait && g_drawRect && g_drawText;
}

template <typename T>
static void nativePush(T value) {
    static_assert(sizeof(T) <= sizeof(unsigned long long),
                  "native argument must fit in 64 bits");
    unsigned long long value64 = 0;
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

// BEGIN CODERED_NATIVE_BRIDGE_SELECTED_WRAPPERS
// Generated candidate block. Do not hand-edit this section in-place.
// Re-run tools/codered_ai_menu_bridge_integration.py after regenerating native wrappers.
// Code RED selected native bridge prep
// Generated: 2026-05-03T09:08:32Z
// Profile: ai_trainer_core
// Include this below the existing nativeInvoke/nativePush helpers in CodeRED_AI_Menu.cpp.
// This file is bridge prep, not a blind auto-install patch.

namespace codered_native_bridge {

struct NativeBridgeSpec {
    const char* name;
    unsigned long long hash;
    const char* category;
    const char* return_type;
    int param_count;
};

static const NativeBridgeSpec kSelectedNatives[] = {
    {"GET_PLAYER_ACTOR", 0xE8CFDD53ULL, "actor", "Actor", 1},
    {"IS_ACTOR_VALID", 0xBA6C3E92ULL, "actor", "BOOL", 1},
    {"IS_ACTOR_ALIVE", 0x2F232639ULL, "actor", "BOOL", 1},
    {"FIND_NAMED_LAYOUT", 0x5699DE7EULL, "world", "Layout", 1},
    {"CREATE_LAYOUT", 0x6CA53214ULL, "world", "Layout", 1},
    {"CREATE_ACTOR_IN_LAYOUT", 0x8D67F397ULL, "actor", "Actor", 7},
    {"GET_POSITION", 0x99BD9D6FULL, "world", "void", 2},
    {"TELEPORT_ACTOR", 0x2D54B916ULL, "actor", "void", 5},
    {"SET_ACTOR_HEADING", 0xECE8520BULL, "actor", "void", 3},
    {"TASK_CLEAR", 0x16876A25ULL, "ai_task", "void", 1},
    {"TASK_STAND_STILL", 0x6F80965DULL, "ai_task", "void", 4},
    {"TASK_WANDER", 0x17BCA08EULL, "ai_task", "void", 2},
    {"TASK_FOLLOW_ACTOR", 0x12F0911AULL, "actor", "void", 2},
    {"TASK_KILL_CHAR", 0x1AE4B75BULL, "actor", "void", 2},
    {"AI_IS_HOSTILE_OR_ENEMY", 0x9AB964F4ULL, "ai_task", "int", 2},
    {"SET_ACTOR_FACTION", 0xCC63951AULL, "actor", "void", 2},
    {"GET_ACTOR_FACTION", 0x52E2A611ULL, "actor", "int", 1},
    {"GIVE_WEAPON_TO_ACTOR", 0x6AA0EAF2ULL, "actor", "void", 5},
    {"TASK_MOUNT", 0xB6131204ULL, "actor", "void", 6},
    {"TASK_DISMOUNT", 0x5DEF5C4AULL, "actor", "void", 2},
    {"GET_MOUNT", 0xDD31EC4EULL, "actor", "Mount", 1},
    {"GET_VEHICLE", 0xA0936EB6ULL, "vehicle", "Vehicle", 1},
    {"START_VEHICLE", 0xE4442AB2ULL, "vehicle", "void", 1},
    {"STOP_VEHICLE", 0xC2232D29ULL, "vehicle", "void", 1},
    {"TASK_VEHICLE_LEAVE", 0x6C1218A4ULL, "ai_task", "void", 1},
    {"RELEASE_LAYOUT_REF", 0xD9AC8830ULL, "world", "void", 1},
};

static Actor CR_NATIVE_GET_PLAYER_ACTOR(int player) { return nativeInvoke<Actor>(0xE8CFDD53ULL, player); }
static BOOL CR_NATIVE_IS_ACTOR_VALID(Actor actor) { return nativeInvoke<BOOL>(0xBA6C3E92ULL, actor); }
static BOOL CR_NATIVE_IS_ACTOR_ALIVE(Actor actor) { return nativeInvoke<BOOL>(0x2F232639ULL, actor); }
static Layout CR_NATIVE_FIND_NAMED_LAYOUT(const char* layoutName) { return nativeInvoke<Layout>(0x5699DE7EULL, layoutName); }
static Layout CR_NATIVE_CREATE_LAYOUT(const char* layoutName) { return nativeInvoke<Layout>(0x6CA53214ULL, layoutName); }
static Actor CR_NATIVE_CREATE_ACTOR_IN_LAYOUT(Layout layout, const char* layoutName, int actorEnum, Vector2 positionXY, float positionZ, Vector2 orientationXY, float orientationZ) { return nativeInvoke<Actor>(0x8D67F397ULL, layout, layoutName, actorEnum, positionXY, positionZ, orientationXY, orientationZ); }
static void CR_NATIVE_GET_POSITION(Actor actor, Vector3* position) { nativeInvoke<void>(0x99BD9D6FULL, actor, position); }
static void CR_NATIVE_TELEPORT_ACTOR(Actor actor, Vector3* coords, BOOL xAxis, BOOL yAxis, BOOL zAxis) { nativeInvoke<void>(0x2D54B916ULL, actor, coords, xAxis, yAxis, zAxis); }
static void CR_NATIVE_SET_ACTOR_HEADING(Actor actor, float heading, BOOL p2) { nativeInvoke<void>(0xECE8520BULL, actor, heading, p2); }
static void CR_NATIVE_TASK_CLEAR(Actor actor) { nativeInvoke<void>(0x16876A25ULL, actor); }
static void CR_NATIVE_TASK_STAND_STILL(Actor actor, float p1, int p2, int p3) { nativeInvoke<void>(0x6F80965DULL, actor, p1, p2, p3); }
static void CR_NATIVE_TASK_WANDER(int p0, int p1) { nativeInvoke<void>(0x17BCA08EULL, p0, p1); }
static void CR_NATIVE_TASK_FOLLOW_ACTOR(Actor actor, Actor followActor) { nativeInvoke<void>(0x12F0911AULL, actor, followActor); }
static void CR_NATIVE_TASK_KILL_CHAR(int p0, int p1) { nativeInvoke<void>(0x1AE4B75BULL, p0, p1); }
static int CR_NATIVE_AI_IS_HOSTILE_OR_ENEMY(int p0, int p1) { return nativeInvoke<int>(0x9AB964F4ULL, p0, p1); }
static void CR_NATIVE_SET_ACTOR_FACTION(Actor actor, int faction) { nativeInvoke<void>(0xCC63951AULL, actor, faction); }
static int CR_NATIVE_GET_ACTOR_FACTION(Actor actor) { return nativeInvoke<int>(0x52E2A611ULL, actor); }
static void CR_NATIVE_GIVE_WEAPON_TO_ACTOR(Actor actor, int weaponEnum, float ammoCount, BOOL p3, int p4) { nativeInvoke<void>(0x6AA0EAF2ULL, actor, weaponEnum, ammoCount, p3, p4); }
static void CR_NATIVE_TASK_MOUNT(int p0, int p1, int p2, int p3, int p4, int p5) { nativeInvoke<void>(0xB6131204ULL, p0, p1, p2, p3, p4, p5); }
static void CR_NATIVE_TASK_DISMOUNT(int p0, int p1) { nativeInvoke<void>(0x5DEF5C4AULL, p0, p1); }
static int CR_NATIVE_GET_MOUNT(Actor actor) { return nativeInvoke<int>(0xDD31EC4EULL, actor); }
static int CR_NATIVE_GET_VEHICLE(Actor actor) { return nativeInvoke<int>(0xA0936EB6ULL, actor); }
static void CR_NATIVE_START_VEHICLE(int vehicle) { nativeInvoke<void>(0xE4442AB2ULL, vehicle); }
static void CR_NATIVE_STOP_VEHICLE(int vehicle) { nativeInvoke<void>(0xC2232D29ULL, vehicle); }
static void CR_NATIVE_TASK_VEHICLE_LEAVE(int p0) { nativeInvoke<void>(0x6C1218A4ULL, p0); }
static void CR_NATIVE_RELEASE_LAYOUT_REF(Layout layout) { nativeInvoke<void>(0xD9AC8830ULL, layout); }

} // namespace codered_native_bridge
// END CODERED_NATIVE_BRIDGE_SELECTED_WRAPPERS

static bool nativeReady() {
    return InterlockedCompareExchange(&g_nativeReady, 0, 0) != 0 &&
           g_nativeInit && g_nativePush64 && g_nativeCall;
}

static bool resolveNativeBridge(bool logMissingExports) {
    if (!g_scriptHook) return false;

    FARPROC nativeInitProc = resolveExport("nativeInit", "?nativeInit@@YAX_K@Z");
    FARPROC nativePush64Proc = resolveExport("nativePush64", "?nativePush64@@YAX_K@Z");
    FARPROC nativeCallProc = resolveExport("nativeCall", "?nativeCall@@YAPEA_KXZ");

    if (logMissingExports) {
        logMissingExport("nativeInit", nativeInitProc);
        logMissingExport("nativePush64", nativePush64Proc);
        logMissingExport("nativeCall", nativeCallProc);
    }

    g_nativeInit = reinterpret_cast<NativeInitFn>(nativeInitProc);
    g_nativePush64 = reinterpret_cast<NativePush64Fn>(nativePush64Proc);
    g_nativeCall = reinterpret_cast<NativeCallFn>(nativeCallProc);

    const bool ready = g_nativeInit && g_nativePush64 && g_nativeCall;
    InterlockedExchange(&g_nativeReady, ready ? 1 : 0);
    return ready;
}

static void waitFrame(DWORD ms) {
    if (g_scriptWait) {
        g_scriptWait(ms);
    } else {
        Sleep(ms);
    }
}

static void drawRectSafe(float x, float y, float width, float height, int r, int g, int b, int a, float rounding) {
    if (g_drawRect) g_drawRect(x, y, width, height, r, g, b, a, rounding);
}

static void drawTextSafe(float x, float y, const char* text, int r, int g, int b, int a, int fontId, float fontSize, int justification) {
    if (g_drawText) g_drawText(x, y, text, r, g, b, a, fontId, fontSize, justification);
}

static std::string trim(const std::string& value) {
    size_t first = value.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) return "";
    size_t last = value.find_last_not_of(" \t\r\n");
    return value.substr(first, last - first + 1);
}

static std::string lowerCopy(const std::string& value) {
    std::string out = value;
    std::transform(out.begin(), out.end(), out.begin(),
                   [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    return out;
}

static bool parseConfigBool(const std::string& raw, bool fallback) {
    const std::string text = lowerCopy(trim(raw));
    if (text == "1" || text == "true" || text == "yes" ||
        text == "on" || text == "enabled") {
        return true;
    }
    if (text == "0" || text == "false" || text == "no" ||
        text == "off" || text == "disabled") {
        return false;
    }
    return fallback;
}

static int parseConfigInt(const std::string& raw, int fallback,
                          int minValue, int maxValue) {
    char* end = nullptr;
    const long parsed = std::strtol(raw.c_str(), &end, 10);
    if (end == raw.c_str() || *end != '\0') return fallback;
    if (parsed < minValue) return minValue;
    if (parsed > maxValue) return maxValue;
    return static_cast<int>(parsed);
}

static float parseConfigFloat(const std::string& raw, float fallback,
                              float minValue, float maxValue) {
    char* end = nullptr;
    const float parsed = static_cast<float>(std::strtod(raw.c_str(), &end));
    if (end == raw.c_str() || *end != '\0') return fallback;
    if (parsed < minValue) return minValue;
    if (parsed > maxValue) return maxValue;
    return parsed;
}

static std::string stripInlineComment(const std::string& value) {
    bool inQuotes = false;
    for (size_t i = 0; i < value.size(); ++i) {
        const char c = value[i];
        if (c == '"') {
            inQuotes = !inQuotes;
            continue;
        }
        if (!inQuotes && (c == '#' || c == ';')) {
            return value.substr(0, i);
        }
    }
    return value;
}

static std::vector<std::string> splitCsvLine(const std::string& line) {
    std::vector<std::string> fields;
    std::string current;
    bool inQuotes = false;

    for (size_t i = 0; i < line.size(); ++i) {
        const char c = line[i];
        if (c == '"') {
            if (inQuotes && i + 1 < line.size() && line[i + 1] == '"') {
                current.push_back('"');
                ++i;
            } else {
                inQuotes = !inQuotes;
            }
            continue;
        }
        if (!inQuotes && c == ',') {
            fields.push_back(trim(current));
            current.clear();
            continue;
        }
        current.push_back(c);
    }

    fields.push_back(trim(current));
    return fields;
}

static std::vector<std::string> splitAliases(const std::string& text) {
    std::vector<std::string> aliases;
    std::string current;
    for (char c : text) {
        if (c == '|' || c == ';') {
            std::string clean = trim(current);
            if (!clean.empty()) aliases.push_back(clean);
            current.clear();
        } else {
            current.push_back(c);
        }
    }
    std::string clean = trim(current);
    if (!clean.empty()) aliases.push_back(clean);
    return aliases;
}

static bool parseActorEnumToken(const std::string& raw, int& outValue) {
    std::string text = trim(raw);
    if (text.empty() || text == "?" || text == "null" || text == "NULL" ||
        text == "todo" || text == "TODO") {
        return false;
    }

    int base = 10;
    if (text.size() > 2 && text[0] == '0' &&
        (text[1] == 'x' || text[1] == 'X')) {
        base = 16;
    }

    errno = 0;
    char* end = nullptr;
    long long value = std::strtoll(text.c_str(), &end, base);
    if (errno != 0 || end == text.c_str() || !trim(end).empty()) {
        return false;
    }
    if (value <= 0 || value > INT_MAX) {
        return false;
    }

    outValue = static_cast<int>(value);
    return true;
}

static std::string jsonEscape(const std::string& value) {
    std::ostringstream out;
    for (char c : value) {
        switch (c) {
            case '\\': out << "\\\\"; break;
            case '"': out << "\\\""; break;
            case '\n': out << "\\n"; break;
            case '\r': out << "\\r"; break;
            case '\t': out << "\\t"; break;
            default: out << c; break;
        }
    }
    return out.str();
}

static std::string jsonStringValue(const std::string& json, const std::string& key) {
    const std::string needle = "\"" + key + "\"";
    size_t pos = json.find(needle);
    if (pos == std::string::npos) return "";
    pos = json.find(':', pos + needle.size());
    if (pos == std::string::npos) return "";
    pos = json.find('"', pos + 1);
    if (pos == std::string::npos) return "";

    std::string out;
    bool escaped = false;
    for (++pos; pos < json.size(); ++pos) {
        const char c = json[pos];
        if (escaped) {
            switch (c) {
                case 'n': out.push_back('\n'); break;
                case 'r': out.push_back('\r'); break;
                case 't': out.push_back('\t'); break;
                default: out.push_back(c); break;
            }
            escaped = false;
            continue;
        }
        if (c == '\\') {
            escaped = true;
            continue;
        }
        if (c == '"') break;
        out.push_back(c);
    }
    return out;
}

static bool jsonNumberValue(const std::string& json, const std::string& key, double& out) {
    const std::string needle = "\"" + key + "\"";
    size_t pos = json.find(needle);
    if (pos == std::string::npos) return false;
    pos = json.find(':', pos + needle.size());
    if (pos == std::string::npos) return false;
    ++pos;
    while (pos < json.size() && std::isspace(static_cast<unsigned char>(json[pos]))) ++pos;
    const size_t start = pos;
    while (pos < json.size()) {
        const char c = json[pos];
        if (!(std::isdigit(static_cast<unsigned char>(c)) || c == '-' || c == '+' ||
              c == '.' || c == 'e' || c == 'E')) {
            break;
        }
        ++pos;
    }
    if (pos == start) return false;
    char* end = nullptr;
    out = std::strtod(json.substr(start, pos - start).c_str(), &end);
    return end && *end == '\0';
}

static int jsonIntValue(const std::string& json, const std::string& key, int fallback = 0) {
    double value = 0.0;
    if (!jsonNumberValue(json, key, value)) return fallback;
    return static_cast<int>(value);
}

static float jsonFloatValue(const std::string& json, const std::string& key, float fallback = 0.0f) {
    double value = 0.0;
    if (!jsonNumberValue(json, key, value)) return fallback;
    return static_cast<float>(value);
}

static bool jsonBoolValue(const std::string& json, const std::string& key, bool fallback = false) {
    const std::string needle = "\"" + key + "\"";
    size_t pos = json.find(needle);
    if (pos == std::string::npos) return fallback;
    pos = json.find(':', pos + needle.size());
    if (pos == std::string::npos) return fallback;
    ++pos;
    while (pos < json.size() && std::isspace(static_cast<unsigned char>(json[pos]))) ++pos;
    if (json.compare(pos, 4, "true") == 0) return true;
    if (json.compare(pos, 5, "false") == 0) return false;
    return fallback;
}

static bool jsonReadStringAt(const std::string& json, size_t& pos, std::string& out) {
    if (pos >= json.size() || json[pos] != '"') return false;
    out.clear();
    bool escaped = false;
    for (++pos; pos < json.size(); ++pos) {
        const char c = json[pos];
        if (escaped) {
            switch (c) {
                case 'n': out.push_back('\n'); break;
                case 'r': out.push_back('\r'); break;
                case 't': out.push_back('\t'); break;
                default: out.push_back(c); break;
            }
            escaped = false;
            continue;
        }
        if (c == '\\') {
            escaped = true;
            continue;
        }
        if (c == '"') {
            ++pos;
            return true;
        }
        out.push_back(c);
    }
    return false;
}

static size_t jsonArrayEnd(const std::string& json, size_t arrayStart) {
    if (arrayStart >= json.size() || json[arrayStart] != '[') return std::string::npos;
    int depth = 0;
    bool inString = false;
    bool escaped = false;
    for (size_t pos = arrayStart; pos < json.size(); ++pos) {
        const char c = json[pos];
        if (inString) {
            if (escaped) {
                escaped = false;
            } else if (c == '\\') {
                escaped = true;
            } else if (c == '"') {
                inString = false;
            }
            continue;
        }
        if (c == '"') {
            inString = true;
        } else if (c == '[') {
            ++depth;
        } else if (c == ']') {
            --depth;
            if (depth == 0) return pos;
            if (depth < 0) return std::string::npos;
        }
    }
    return std::string::npos;
}

static std::vector<std::string> jsonStringArrayValue(const std::string& json, const std::string& key) {
    std::vector<std::string> values;
    const std::string needle = "\"" + key + "\"";
    size_t pos = json.find(needle);
    if (pos == std::string::npos) return values;
    pos = json.find('[', pos + needle.size());
    if (pos == std::string::npos) return values;
    const size_t end = jsonArrayEnd(json, pos);
    if (end == std::string::npos) return values;

    while (pos < end) {
        pos = json.find('"', pos + 1);
        if (pos == std::string::npos || pos >= end) break;
        std::string item;
        if (!jsonReadStringAt(json, pos, item)) break;
        values.push_back(item);
    }
    return values;
}

static bool jsonArrayKeyPresent(const std::string& json, const std::string& key) {
    const std::string needle = "\"" + key + "\"";
    size_t pos = json.find(needle);
    if (pos == std::string::npos) return false;
    pos = json.find(':', pos + needle.size());
    if (pos == std::string::npos) return false;
    ++pos;
    while (pos < json.size() && std::isspace(static_cast<unsigned char>(json[pos]))) ++pos;
    return pos < json.size() && json[pos] == '[';
}

static std::string readSmallTextFile(const std::string& path, size_t maxBytes = 32768) {
    std::ifstream file(path.c_str(), std::ios::binary);
    if (!file) return "";
    std::ostringstream out;
    char buffer[1024] = {};
    size_t total = 0;
    while (file && total < maxBytes) {
        const size_t remaining = maxBytes - total;
        const size_t want = remaining < sizeof(buffer) ? remaining : sizeof(buffer);
        file.read(buffer, static_cast<std::streamsize>(want));
        const std::streamsize got = file.gcount();
        if (got <= 0) break;
        out.write(buffer, got);
        total += static_cast<size_t>(got);
    }
    return out.str();
}

static std::string dirnameOf(const std::string& path) {
    const size_t slash = path.find_last_of("\\/");
    if (slash == std::string::npos) return "";
    return path.substr(0, slash);
}

static void createDirectoriesForPath(const std::string& path) {
    std::string current;
    for (size_t i = 0; i < path.size(); ++i) {
        char c = path[i];
        current.push_back(c);
        if (c != '\\' && c != '/') continue;
        if (current.size() <= 3 && current.size() >= 2 && current[1] == ':') continue;
        if (!current.empty()) CreateDirectoryA(current.c_str(), nullptr);
    }
    if (!path.empty()) CreateDirectoryA(path.c_str(), nullptr);
}

static void createParentDirs(const std::string& filePath) {
    const std::string dir = dirnameOf(filePath);
    if (!dir.empty()) createDirectoriesForPath(dir);
}

static std::string joinPath(const std::string& base, const std::string& leaf) {
    if (base.empty()) return leaf;
    const char tail = base[base.size() - 1];
    if (tail == '\\' || tail == '/') return base + leaf;
    return base + "\\" + leaf;
}

static bool isAbsolutePath(const std::string& path) {
    if (path.empty()) return false;
    if (path.size() >= 3 && std::isalpha(static_cast<unsigned char>(path[0])) &&
        path[1] == ':' && (path[2] == '\\' || path[2] == '/')) {
        return true;
    }
    return path[0] == '\\' || path[0] == '/';
}

static std::string gamePath(const std::string& path) {
    if (isAbsolutePath(path)) return path;
    return joinPath(gameDirectory(), path);
}

static bool fileExists(const std::string& path) {
    const DWORD attr = GetFileAttributesA(path.c_str());
    return attr != INVALID_FILE_ATTRIBUTES &&
           (attr & FILE_ATTRIBUTE_DIRECTORY) == 0;
}

static unsigned long long fileSizeBytes(const std::string& path) {
    WIN32_FILE_ATTRIBUTE_DATA data = {};
    if (!GetFileAttributesExA(path.c_str(), GetFileExInfoStandard, &data)) {
        return 0;
    }
    if ((data.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0) return 0;
    return (static_cast<unsigned long long>(data.nFileSizeHigh) << 32) |
           static_cast<unsigned long long>(data.nFileSizeLow);
}

static unsigned long long fileWriteTime(const std::string& path) {
    WIN32_FILE_ATTRIBUTE_DATA data = {};
    if (!GetFileAttributesExA(path.c_str(), GetFileExInfoStandard, &data)) {
        return 0;
    }
    return (static_cast<unsigned long long>(data.ftLastWriteTime.dwHighDateTime) << 32) |
           static_cast<unsigned long long>(data.ftLastWriteTime.dwLowDateTime);
}

static std::string enumHex(int actorEnum) {
    char buffer[32] = {};
    snprintf(buffer, sizeof(buffer), "0x%08X",
             static_cast<unsigned int>(actorEnum));
    return std::string(buffer);
}

static std::string displayRosterName(const std::string& raw) {
    std::string text = trim(stripInlineComment(raw));
    size_t best = std::string::npos;
    for (char marker : {'|', '=', ','}) {
        size_t pos = text.find(marker);
        if (pos != std::string::npos &&
            (best == std::string::npos || pos < best)) {
            best = pos;
        }
    }
    if (best != std::string::npos) {
        text = text.substr(0, best);
    }
    return trim(text);
}

static bool resolveInlineActorEnum(const std::string& raw, int& actorEnum) {
    std::string text = trim(stripInlineComment(raw));
    for (char marker : {'|', '=', ','}) {
        size_t pos = text.find(marker);
        if (pos != std::string::npos) {
            std::string rhs = trim(text.substr(pos + 1));
            if (parseActorEnumToken(rhs, actorEnum)) return true;
        }
    }
    return parseActorEnumToken(text, actorEnum);
}

static void loadConfig() {
    if (g_configLoaded) return;
    g_configLoaded = true;

    std::ifstream file("CodeRED_AI_Menu.ini");
    if (!file) return;

    std::string section;
    std::string line;
    while (std::getline(file, line)) {
        std::string clean = trim(stripInlineComment(line));
        if (clean.empty()) continue;
        if (clean.front() == '[' && clean.back() == ']') {
            section = lowerCopy(trim(clean.substr(1, clean.size() - 2)));
            continue;
        }
        if (section != "paths" && section != "mp") continue;

        size_t eq = clean.find('=');
        if (eq == std::string::npos) continue;
        std::string key = lowerCopy(trim(clean.substr(0, eq)));
        std::string value = trim(clean.substr(eq + 1));
        if (value.empty()) continue;

        if (section == "paths") {
            if (key == "roster") {
                g_rosterPath = value;
            } else if (key == "actor_enum_map" || key == "actor_map" ||
                       key == "enum_map") {
                g_actorEnumMapPath = value;
            } else if (key == "behavior_actions" || key == "actions" ||
                       key == "action_menu") {
                g_actionsPath = value;
            } else if (key == "action_plan") {
                g_actionPlanPath = value;
            } else if (key == "mp_connect_request" || key == "mp_connect_request_path") {
                g_mpConnectRequestPath = value;
            } else if (key == "mp_client_status" || key == "mp_client_status_path") {
                g_mpClientStatusPath = value;
            } else if (key == "mp_bridge_input" || key == "mp_bridge_in" ||
                       key == "mp_local_state") {
                g_mpBridgeInputPath = value;
            } else if (key == "mp_bridge_world" || key == "mp_bridge_out" ||
                       key == "mp_world_state") {
                g_mpBridgeWorldPath = value;
            } else if (key == "mp_client" || key == "mp_client_exe" ||
                       key == "mp_client_path") {
                g_mpClientPath = value;
            } else if (key == "state") {
                g_statePath = value;
            } else if (key == "override_rpf" || key == "override_rpf_dir" ||
                       key == "override_dir") {
                g_overrideRpfPath = value;
            } else if (key == "patch_stage" || key == "patch_stage_dir" ||
                       key == "rpf_patch_stage") {
                g_patchStagePath = value;
            } else if (key == "content_override" || key == "content_rpf" ||
                       key == "content_override_name") {
                g_contentOverrideName = value;
            }
        } else if (section == "mp") {
            if (key == "host" || key == "server" || key == "server_host") {
                g_mpServerHost = value;
            } else if (key == "port" || key == "server_port") {
                g_mpServerPort = parseConfigInt(value, g_mpServerPort, 1, 65535);
            } else if (key == "name" || key == "player_name") {
                g_mpPlayerName = value;
            } else if (key == "bare_world" || key == "bare_world_enabled") {
                g_mpBareWorldEnabled = parseConfigBool(value, g_mpBareWorldEnabled);
            } else if (key == "bare_world_destroy_actors" ||
                       key == "bare_world_cleanup") {
                g_mpBareWorldDestroyActors = parseConfigBool(value, g_mpBareWorldDestroyActors);
            } else if (key == "bare_world_population_suppression" ||
                       key == "population_suppression") {
                g_mpBareWorldPopulationSuppression = parseConfigBool(value, g_mpBareWorldPopulationSuppression);
            } else if (key == "bare_world_radius" || key == "cleanup_radius") {
                g_mpBareWorldRadius = parseConfigFloat(value, g_mpBareWorldRadius, 25.0f, 2000.0f);
            } else if (key == "bare_world_max_destroy_per_tick" ||
                       key == "cleanup_max_destroy_per_tick") {
                g_mpBareWorldMaxDestroyPerTick =
                    parseConfigInt(value, g_mpBareWorldMaxDestroyPerTick, 1, 128);
            } else if (key == "bare_world_tick_ms" || key == "cleanup_tick_ms") {
                g_mpBareWorldTickMs = parseConfigInt(value, g_mpBareWorldTickMs, 100, 5000);
            }
        }
    }

    writeLog("Config loaded: roster=%s actor_enum_map=%s actions=%s action_plan=%s mp_connect_request=%s mp_client_status=%s mp_bridge_in=%s mp_bridge_world=%s mp_client=%s mp_host=%s mp_port=%d mp_name=%s mp_bare_world=%d mp_bare_destroy=%d mp_bare_population=%d mp_bare_radius=%.1f mp_bare_max_destroy=%d mp_bare_tick_ms=%d state=%s override_rpf=%s patch_stage=%s content_override=%s",
             g_rosterPath.c_str(), g_actorEnumMapPath.c_str(),
             g_actionsPath.c_str(), g_actionPlanPath.c_str(),
             g_mpConnectRequestPath.c_str(), g_mpClientStatusPath.c_str(),
             g_mpBridgeInputPath.c_str(), g_mpBridgeWorldPath.c_str(),
             g_mpClientPath.c_str(), g_mpServerHost.c_str(), g_mpServerPort,
             g_mpPlayerName.c_str(),
             g_mpBareWorldEnabled ? 1 : 0,
             g_mpBareWorldDestroyActors ? 1 : 0,
             g_mpBareWorldPopulationSuppression ? 1 : 0,
             g_mpBareWorldRadius,
             g_mpBareWorldMaxDestroyPerTick,
             g_mpBareWorldTickMs,
             g_statePath.c_str(), g_overrideRpfPath.c_str(),
             g_patchStagePath.c_str(), g_contentOverrideName.c_str());
}

static void loadActorEnumMap() {
    loadConfig();
    g_actorEnumMap.clear();
    g_actorEnumRowsLoaded = 0;
    g_actorEnumCacheValid = false;

    std::ifstream file(g_actorEnumMapPath.c_str());
    if (!file) {
        g_dirtyActorMap = false;
        writeLog("Actor enum map not found: %s", g_actorEnumMapPath.c_str());
        return;
    }

    std::string line;
    while (std::getline(file, line)) {
        std::string clean = trim(stripInlineComment(line));
        if (clean.empty()) continue;

        const size_t firstComma = clean.find(',');
        if (firstComma != std::string::npos) {
            std::vector<std::string> fields = splitCsvLine(clean);
            if (fields.empty()) continue;
            if (fields.size() >= 2) {
                const std::string key0 = lowerCopy(fields[0]);
                const std::string key1 = lowerCopy(fields[1]);
                if ((key0 == "label" || key0 == "name" || key0 == "actor") &&
                    (key1 == "actor_enum" || key1 == "enum" ||
                     key1 == "value" || key1 == "actorenum")) {
                    continue;
                }
            }

            std::string label = trim(fields[0]);
            std::string enumText = fields.size() >= 2 ? fields[1] : "";
            int enumValue = 0;
            if (label.empty() || !parseActorEnumToken(enumText, enumValue)) {
                continue;
            }

            g_actorEnumMap[lowerCopy(label)] = enumValue;
            ++g_actorEnumRowsLoaded;

            if (fields.size() >= 5) {
                for (const std::string& alias : splitAliases(fields[4])) {
                    g_actorEnumMap[lowerCopy(alias)] = enumValue;
                }
            }
            continue;
        }

        const size_t inlineEq = clean.find('=');
        const size_t inlinePipe = clean.find('|');
        if (inlineEq != std::string::npos || inlinePipe != std::string::npos) {
            size_t pos = inlineEq;
            if (inlinePipe != std::string::npos &&
                (pos == std::string::npos || inlinePipe < pos)) {
                pos = inlinePipe;
            }
            std::string label = trim(clean.substr(0, pos));
            std::string enumText = trim(clean.substr(pos + 1));
            int enumValue = 0;
            if (!label.empty() && parseActorEnumToken(enumText, enumValue)) {
                g_actorEnumMap[lowerCopy(label)] = enumValue;
                ++g_actorEnumRowsLoaded;
            }
            continue;
        }
    }

    g_dirtyActorMap = false;
    writeLog("Actor enum map loaded: rows=%zu aliases=%zu path=%s",
             g_actorEnumRowsLoaded, g_actorEnumMap.size(),
             g_actorEnumMapPath.c_str());
}

static void ensureDefaultActions() {
    if (!g_actions.empty()) return;
    g_actions = {
        "spawn_selected_npc_request",
        "follow_player_request",
        "guard_position_request",
        "defend_player_request",
        "attack_nearest_hostile_request",
        "idle_spawned_request",
        "wander_spawned_request",
        "regroup_near_player_request",
        "make_spawned_lawmen_request",
        "side_lawman_immunity_request",
        "side_gang_immunity_request",
        "restore_player_faction_request",
        "mp_connect_localhost_request",
        "mp_toggle_bare_world_request",
        "mp_bare_world_purge_request",
        "mp_toggle_bare_world_suppression_request",
        "reload_override_rpf_request",
        "dismiss_ai_guest_request",
        "status_request"
    };
}

static bool csvEnabledValue(const std::string& value) {
    std::string clean = lowerCopy(trim(value));
    return clean.empty() || clean == "1" || clean == "true" || clean == "yes" ||
           clean == "on" || clean == "enabled";
}

static void loadActions() {
    loadConfig();
    std::vector<std::string> loaded;
    std::unordered_map<std::string, std::string> labels;

    std::ifstream file(g_actionsPath.c_str());
    if (!file) {
        g_dirtyActions = false;
        ensureDefaultActions();
        writeLog("Behavior action menu not found: %s", g_actionsPath.c_str());
        return;
    }

    std::string line;
    while (std::getline(file, line)) {
        std::string clean = trim(stripInlineComment(line));
        if (clean.empty()) continue;
        std::vector<std::string> fields = splitCsvLine(clean);
        if (fields.empty()) continue;

        std::string action = trim(fields[0]);
        if (action.empty()) continue;
        if (lowerCopy(action) == "action" || lowerCopy(action) == "id") continue;

        std::string enabled = fields.size() >= 4 ? fields[3] : "";
        if (!csvEnabledValue(enabled)) continue;

        loaded.push_back(action);
        if (fields.size() >= 2 && !trim(fields[1]).empty()) {
            labels[action] = trim(fields[1]);
        }
    }

    if (!loaded.empty()) {
        g_actions.swap(loaded);
        g_actionLabels.swap(labels);
    } else {
        ensureDefaultActions();
    }
    if (g_menuIndex < 0) g_menuIndex = 0;
    if (g_menuIndex >= static_cast<int>(g_actions.size())) g_menuIndex = 0;
    g_dirtyActions = false;
    writeLog("Behavior action menu loaded: count=%zu path=%s",
             g_actions.size(), g_actionsPath.c_str());
}

static void ensureDefaultRoster() {
    if (!g_roster.empty()) return;
    g_roster = {
        "amb_fh_farmer06",
        "amb_cowboy",
        "amb_worker",
        "gent_default",
        "gped_default",
        "player_bandito",
        "player_lawman",
        "player_marston",
        "law_sheriff",
        "misc_rancher",
        "com_companion",
        "crm_outlaw"
    };
}

static void loadRoster() {
    loadConfig();
    if (g_dirtyActorMap) loadActorEnumMap();

    g_roster.clear();
    std::ifstream file(g_rosterPath.c_str());
    std::string line;
    while (std::getline(file, line)) {
        std::string clean = trim(stripInlineComment(line));
        if (clean.empty()) continue;
        std::string label = displayRosterName(clean);
        if (label.empty()) continue;
        g_roster.push_back(clean);
    }
    ensureDefaultRoster();
    if (g_npcIndex < 0) g_npcIndex = 0;
    if (g_npcIndex >= static_cast<int>(g_roster.size())) g_npcIndex = 0;
    g_status = "Roster loaded: " + std::to_string(g_roster.size()) +
               " | enum rows: " + std::to_string(g_actorEnumRowsLoaded);
    g_dirtyRoster = false;
    writeLog("Roster loaded: count=%zu path=%s", g_roster.size(),
             g_rosterPath.c_str());
}

static std::string selectedNpcRaw() {
    ensureDefaultRoster();
    if (g_npcIndex < 0) g_npcIndex = 0;
    if (g_npcIndex >= static_cast<int>(g_roster.size())) g_npcIndex = 0;
    return g_roster[g_npcIndex];
}

static std::string selectedNpc() {
    return displayRosterName(selectedNpcRaw());
}

static std::string selectedAction() {
    ensureDefaultActions();
    if (g_menuIndex < 0) g_menuIndex = 0;
    if (g_menuIndex >= static_cast<int>(g_actions.size())) g_menuIndex = 0;
    return g_actions[g_menuIndex];
}

static void writeActionPlan();
static void pollMpClientStatus();

static std::string displayAction(const std::string& action) {
    auto found = g_actionLabels.find(action);
    if (found != g_actionLabels.end() && !found->second.empty()) {
        return found->second;
    }

    std::string text = action;
    const std::string suffix = "_request";
    if (text.size() > suffix.size() &&
        text.compare(text.size() - suffix.size(), suffix.size(), suffix) == 0) {
        text.erase(text.size() - suffix.size());
    }
    std::replace(text.begin(), text.end(), '_', ' ');
    return text;
}

static bool parseInteger(const std::string& text, int* value) {
    if (!value) return false;
    char* end = nullptr;
    long parsed = std::strtol(text.c_str(), &end, 0);
    if (end == text.c_str() || *end != '\0') return false;
    *value = static_cast<int>(parsed);
    return true;
}

static int actorEnumFromRosterLine(const std::string& line) {
    if (!nativeReady()) return 0;

    std::vector<std::string> candidates;
    candidates.push_back(displayRosterName(line));
    candidates.push_back(trim(stripInlineComment(line)));

    size_t delimiter = line.find('|');
    if (delimiter == std::string::npos) delimiter = line.find(',');
    if (delimiter == std::string::npos) delimiter = line.find('=');
    if (delimiter != std::string::npos) {
        candidates.push_back(trim(line.substr(0, delimiter)));
        candidates.push_back(trim(line.substr(delimiter + 1)));
    }

    for (const std::string& candidate : candidates) {
        if (candidate.empty()) continue;

        int numeric = 0;
        if (parseInteger(candidate, &numeric) && numeric > 0) {
            return numeric;
        }

        int actorEnum = nativeInvoke<int>(0xC739D1D2, candidate.c_str());
        if (actorEnum > 0) {
            return actorEnum;
        }
    }

    return 0;
}

static int selectedActorEnum() {
    if (g_dirtyActorMap) loadActorEnumMap();

    const std::string raw = selectedNpcRaw();
    if (g_actorEnumCacheValid && raw == g_actorEnumCacheRaw) {
        return g_actorEnumCacheValue;
    }

    int actorEnum = 0;
    if (resolveInlineActorEnum(raw, actorEnum)) {
        g_actorEnumCacheRaw = raw;
        g_actorEnumCacheValue = actorEnum;
        g_actorEnumCacheValid = true;
        return g_actorEnumCacheValue;
    }

    auto found = g_actorEnumMap.find(lowerCopy(selectedNpc()));
    if (found != g_actorEnumMap.end()) {
        g_actorEnumCacheRaw = raw;
        g_actorEnumCacheValue = found->second;
        g_actorEnumCacheValid = true;
        return g_actorEnumCacheValue;
    }

    // Preserve the current native bridge behavior for direct actor enum strings.
    g_actorEnumCacheRaw = raw;
    g_actorEnumCacheValue = actorEnumFromRosterLine(raw);
    g_actorEnumCacheValid = true;
    return g_actorEnumCacheValue;
}

static Layout ensureLayout() {
    if (!nativeReady()) return 0;
    if (g_layout > 0) return g_layout;

    g_layout = nativeInvoke<Layout>(0x5699DE7E, "CodeRED_AI_Menu_Layout");
    if (g_layout <= 0) {
        g_layout = nativeInvoke<Layout>(0x6CA53214, "CodeRED_AI_Menu_Layout");
    }
    return g_layout;
}

static void pruneSpawnedActors() {
    if (!nativeReady()) return;
    std::vector<Actor> alive;
    for (Actor actor : g_spawnedActors) {
        if (actor > 0 && nativeInvoke<BOOL>(0xBA6C3E92, actor)) {
            alive.push_back(actor);
        }
    }
    g_spawnedActors.swap(alive);
}

static Actor playerActor() {
    if (!nativeReady()) return 0;
    Actor player = nativeInvoke<Actor>(0xE8CFDD53, 0);
    if (player <= 0 || !nativeInvoke<BOOL>(0xBA6C3E92, player)) {
        return 0;
    }
    return player;
}

static bool isCodeRedSpawnedActor(Actor actor) {
    for (Actor spawned : g_spawnedActors) {
        if (spawned == actor) return true;
    }
    return false;
}

static float distanceSquared(const Vector3& a, const Vector3& b) {
    const float dx = a.x - b.x;
    const float dy = a.y - b.y;
    const float dz = a.z - b.z;
    return dx * dx + dy * dy + dz * dz;
}

static bool actorPosition(Actor actor, Vector3* out) {
    if (!out || actor <= 0 || !nativeReady()) return false;
    if (!nativeInvoke<BOOL>(0xBA6C3E92, actor)) return false;
    *out = {};
    nativeInvoke<void>(0x99BD9D6F, actor, out);
    return true;
}

static void mpLiteAddChatLine(const std::string& line) {
    if (line.empty()) return;
    g_mpNoticeLines.push_back(line);
    if (g_mpNoticeLines.size() > 16) {
        g_mpNoticeLines.erase(g_mpNoticeLines.begin(), g_mpNoticeLines.end() - 16);
    }
}

static void mpLiteRemoveNoticeLine(const std::string& line) {
    g_mpNoticeLines.erase(
        std::remove(g_mpNoticeLines.begin(), g_mpNoticeLines.end(), line),
        g_mpNoticeLines.end());
}

static std::string mpLiteClipText(const std::string& text, size_t maxChars) {
    if (text.size() <= maxChars) return text;
    if (maxChars <= 3) return text.substr(0, maxChars);
    return text.substr(0, maxChars - 3) + "...";
}

static void mpLiteTeleportActorWithHeading(Actor actor, const Vector3& target, float heading) {
    Vector2 targetXY = {target.x, target.y};
    nativeInvoke<void>(0xE4DE507CULL, actor, targetXY, target.z, heading, TRUE, TRUE, TRUE);
}

static MpRemoteActor* mpLiteRemoteById(int playerId) {
    for (MpRemoteActor& remote : g_mpRemoteActors) {
        if (remote.playerId == playerId) return &remote;
    }
    g_mpRemoteActors.push_back(MpRemoteActor{});
    g_mpRemoteActors.back().playerId = playerId;
    return &g_mpRemoteActors.back();
}

static bool mpLiteRemoteActorValid(const MpRemoteActor& remote) {
    return remote.actor > 0 && nativeReady() &&
           nativeInvoke<BOOL>(0xBA6C3E92, remote.actor);
}

static bool mpLiteSpawnRemoteActor(MpRemoteActor& remote) {
    if (!nativeReady()) return false;
    Layout layout = ensureLayout();
    if (layout <= 0) return false;

    Vector2 spawnXY = {remote.position.x, remote.position.y};
    Vector2 orientXY = {0.0f, 1.0f};
    std::ostringstream instanceName;
    instanceName << "codered_mp_remote_" << remote.playerId;

    Actor actor = nativeInvoke<Actor>(0x8D67F397, layout,
                                      instanceName.str().c_str(),
                                      remote.actorEnum,
                                      spawnXY,
                                      remote.position.z,
                                      orientXY,
                                      remote.heading);
    if (actor <= 0 || !nativeInvoke<BOOL>(0xBA6C3E92, actor)) {
        writeLog("MP remote spawn failed: playerid=%d enum=%d actor=%d",
                 remote.playerId, remote.actorEnum, actor);
        return false;
    }

    remote.actor = actor;
    nativeInvoke<void>(0x16876A25, remote.actor);
    nativeInvoke<void>(0x6F80965D, remote.actor, -1.0f, 0, 0);
    writeLog("MP remote spawned: playerid=%d enum=%d actor=%d",
             remote.playerId, remote.actorEnum, remote.actor);
    return true;
}

static void mpLiteApplyRemoteState(MpRemoteActor& remote) {
    if (!nativeReady()) return;
    if (!mpLiteRemoteActorValid(remote) && !mpLiteSpawnRemoteActor(remote)) {
        return;
    }
    Vector3 target = remote.position;
    mpLiteTeleportActorWithHeading(remote.actor, target, remote.heading);
}

static void mpLitePruneStaleRemotes() {
    if (!nativeReady()) return;
    const DWORD now = GetTickCount();
    std::vector<MpRemoteActor> kept;
    for (MpRemoteActor& remote : g_mpRemoteActors) {
        if (remote.lastSeenMs != 0 && now - remote.lastSeenMs > 5000) {
            if (mpLiteRemoteActorValid(remote)) {
                nativeInvoke<void>(0x8BD21869, remote.actor);
            }
            writeLog("MP remote removed as stale: playerid=%d actor=%d",
                     remote.playerId, remote.actor);
            continue;
        }
        kept.push_back(remote);
    }
    g_mpRemoteActors.swap(kept);
}

static bool mpBareWorldIsRemoteActor(Actor actor) {
    for (const MpRemoteActor& remote : g_mpRemoteActors) {
        if (remote.actor == actor) return true;
    }
    return false;
}

static bool mpBareWorldProtectActor(Actor actor, Actor player,
                                    Actor mount, Actor vehicle) {
    if (actor <= 0) return true;
    if (actor == player || actor == mount || actor == vehicle) return true;
    if (isCodeRedSpawnedActor(actor)) return true;
    if (mpBareWorldIsRemoteActor(actor)) return true;
    return false;
}

static void mpBareWorldApplyPopulationSuppression(bool force) {
    if (!g_mpBareWorldPopulationSuppression || !nativeReady()) return;

    const DWORD now = GetTickCount();
    if (!force && g_mpBareWorldLastPopulationMs != 0 &&
        now - g_mpBareWorldLastPopulationMs < 1500) {
        return;
    }
    g_mpBareWorldLastPopulationMs = now;

    nativeInvoke<void>(0x04EFC113ULL, 0);
}

static void mpBareWorldTick(bool force) {
    if (!nativeReady()) {
        if (force) g_status = "Bare world skipped: native bridge unavailable";
        return;
    }

    if (!g_mpBareWorldEnabled && !force) return;

    const DWORD now = GetTickCount();
    if (!force && g_mpBareWorldLastTickMs != 0 &&
        now - g_mpBareWorldLastTickMs < static_cast<DWORD>(g_mpBareWorldTickMs)) {
        mpBareWorldApplyPopulationSuppression(false);
        return;
    }
    g_mpBareWorldLastTickMs = now;

    mpBareWorldApplyPopulationSuppression(force);

    if (!g_mpBareWorldDestroyActors) {
        if (force) {
            g_status = "Bare world cleanup disabled";
            writeLog("Bare world cleanup skipped: destroy_actors disabled");
        }
        return;
    }

    if (!g_worldGetAllActors) {
        if (force) g_status = "Bare world skipped: worldGetAllActors missing";
        return;
    }

    Actor player = playerActor();
    Vector3 playerPos = {};
    if (player <= 0 || !actorPosition(player, &playerPos)) {
        if (force) g_status = "Bare world skipped: player actor not ready";
        return;
    }

    const Actor mount = nativeInvoke<Actor>(0xDD31EC4EULL, player);
    const Actor vehicle = nativeInvoke<Actor>(0xA0936EB6ULL, player);

    constexpr int MAX_ACTORS = 1024;
    int actors[MAX_ACTORS] = {};
    const int count = g_worldGetAllActors(actors, MAX_ACTORS);
    const float radiusSq = g_mpBareWorldRadius * g_mpBareWorldRadius;
    int seen = 0;
    int protectedCount = 0;
    int destroyed = 0;

    for (int i = 0; i < count && i < MAX_ACTORS; ++i) {
        const Actor candidate = actors[i];
        if (candidate <= 0) continue;
        if (!nativeInvoke<BOOL>(0xBA6C3E92ULL, candidate)) continue;
        ++seen;

        if (mpBareWorldProtectActor(candidate, player, mount, vehicle)) {
            ++protectedCount;
            continue;
        }

        Vector3 pos = {};
        if (!actorPosition(candidate, &pos)) continue;
        if (radiusSq > 0.0f && distanceSquared(playerPos, pos) > radiusSq) {
            continue;
        }

        nativeInvoke<void>(0x16876A25ULL, candidate);
        nativeInvoke<void>(0x8BD21869ULL, candidate);
        ++destroyed;
        if (destroyed >= g_mpBareWorldMaxDestroyPerTick) break;
    }

    g_mpBareWorldLastSeen = seen;
    g_mpBareWorldLastProtected = protectedCount;
    g_mpBareWorldLastDestroyed = destroyed;
    g_mpBareWorldTotalDestroyed += destroyed;

    if (destroyed > 0 || force) {
        writeLog("Bare world tick: seen=%d protected=%d destroyed=%d total=%d radius=%.1f population=%d",
                 seen, protectedCount, destroyed, g_mpBareWorldTotalDestroyed,
                 g_mpBareWorldRadius,
                 g_mpBareWorldPopulationSuppression ? 1 : 0);
    }
    if (force) {
        g_status = "Bare world purge: destroyed " + std::to_string(destroyed) +
                   " / seen " + std::to_string(seen);
    }
}

static void mpBareWorldToggle() {
    g_mpBareWorldEnabled = !g_mpBareWorldEnabled;
    g_mpBareWorldLastTickMs = 0;
    g_mpBareWorldLastPopulationMs = 0;
    if (g_mpBareWorldEnabled) {
        mpBareWorldTick(true);
    }
    g_status = std::string("Bare world ") +
               (g_mpBareWorldEnabled ? "enabled" : "disabled");
    writeLog("Bare world toggled: enabled=%d", g_mpBareWorldEnabled ? 1 : 0);
}

static void mpBareWorldPurgeNow() {
    g_mpBareWorldLastTickMs = 0;
    g_mpBareWorldLastPopulationMs = 0;
    mpBareWorldTick(true);
}

static void mpBareWorldTogglePopulationSuppression() {
    g_mpBareWorldPopulationSuppression = !g_mpBareWorldPopulationSuppression;
    g_mpBareWorldLastPopulationMs = 0;
    if (g_mpBareWorldPopulationSuppression) {
        mpBareWorldApplyPopulationSuppression(true);
    }
    g_status = std::string("Bare population suppression ") +
               (g_mpBareWorldPopulationSuppression ? "enabled" : "disabled");
    writeLog("Bare population suppression toggled: enabled=%d",
             g_mpBareWorldPopulationSuppression ? 1 : 0);
}

static bool mpLiteChatAcknowledgedByServer(const std::vector<std::string>& chatLines) {
    if (g_mpPendingChat.empty() || g_mpLocalPlayerId < 0) return false;
    const std::string expected = "[" + std::to_string(g_mpLocalPlayerId) + "] " + g_mpPendingChat;
    for (const std::string& line : chatLines) {
        if (line == expected) return true;
    }
    return false;
}

static void mpLiteWriteLocalState(bool force = false) {
    if (!g_mpLiteActive || !nativeReady()) return;
    const DWORD now = GetTickCount();
    if (!force && now - g_mpLastLocalStateMs < 100) return;
    g_mpLastLocalStateMs = now;

    if (!g_mpPendingChat.empty() && g_mpPendingChatStartedMs != 0 &&
        now - g_mpPendingChatStartedMs > 5000) {
        writeLog("MP chat send window expired: seq=%u text=%s",
                 g_mpChatSeq, g_mpPendingChat.c_str());
        g_mpPendingChat.clear();
        g_mpPendingChatStartedMs = 0;
    }

    Actor player = playerActor();
    Vector3 pos = {};
    if (player <= 0 || !actorPosition(player, &pos)) return;
    const float heading = nativeInvoke<float>(0x42DE39F0, player);

    const std::string path = gamePath(g_mpBridgeInputPath);
    createParentDirs(path);
    std::ofstream file(path.c_str(), std::ios::trunc);
    if (!file) return;

    file << "{\n";
    file << "  \"source\": \"CodeRED_AI_Menu\",\n";
    file << "  \"state_seq\": " << ++g_mpStateSeq << ",\n";
    file << "  \"chat_seq\": " << g_mpChatSeq << ",\n";
    file << "  \"chat\": \"" << jsonEscape(g_mpPendingChat) << "\",\n";
    file << "  \"x\": " << pos.x << ",\n";
    file << "  \"y\": " << pos.y << ",\n";
    file << "  \"z\": " << pos.z << ",\n";
    file << "  \"heading\": " << heading << ",\n";
    file << "  \"health\": 100,\n";
    file << "  \"flags\": 0,\n";
    file << "  \"actor_enum\": " << g_mpLocalActorEnum << ",\n";
    file << "  \"timestamp_ms\": " << static_cast<unsigned long>(now) << "\n";
    file << "}\n";
}

static bool mpLiteParsePlayerObject(const std::string& objectText, MpRemoteActor& remote) {
    const int playerId = jsonIntValue(objectText, "player_id", -1);
    if (playerId < 0 || playerId > 255) return false;
    remote.playerId = playerId;
    remote.position.x = jsonFloatValue(objectText, "x", remote.position.x);
    remote.position.y = jsonFloatValue(objectText, "y", remote.position.y);
    remote.position.z = jsonFloatValue(objectText, "z", remote.position.z);
    remote.heading = jsonFloatValue(objectText, "heading", remote.heading);
    remote.actorEnum = jsonIntValue(objectText, "actor_enum", remote.actorEnum);
    remote.sequence = static_cast<unsigned int>(jsonIntValue(objectText, "sequence", remote.sequence));
    remote.lastSeenMs = GetTickCount();
    return true;
}

static bool parseFloatCsv(const std::string& text, std::vector<float>& values) {
    values.clear();
    std::stringstream input(text);
    std::string item;
    while (std::getline(input, item, ',')) {
        item = trim(item);
        if (item.empty()) return false;
        char* end = nullptr;
        errno = 0;
        const float value = std::strtof(item.c_str(), &end);
        if (errno != 0 || end == item.c_str() || !trim(end).empty()) {
            return false;
        }
        values.push_back(value);
    }
    return !values.empty();
}

static bool parseFloatValue(const std::string& text, float* value) {
    if (!value) return false;
    char* end = nullptr;
    errno = 0;
    const float parsed = std::strtof(text.c_str(), &end);
    if (errno != 0 || end == text.c_str() || !trim(end).empty()) return false;
    *value = parsed;
    return true;
}

static void mpLiteApplyTeleportPayload(const std::string& payload) {
    if (!nativeReady()) return;
    std::vector<float> values;
    if (!parseFloatCsv(payload, values) || values.size() < 3) {
        g_status = "MP teleport failed: bad payload";
        writeLog("MP native teleport bad payload: %s", payload.c_str());
        return;
    }

    Actor player = playerActor();
    if (player <= 0) {
        g_status = "MP teleport failed: player not ready";
        return;
    }

    Vector3 target = {};
    target.x = values[0];
    target.y = values[1];
    target.z = values[2];
    const float heading = values.size() >= 4
        ? values[3]
        : nativeInvoke<float>(0x42DE39F0ULL, player);
    mpLiteTeleportActorWithHeading(player, target, heading);
    g_status = "MP teleported";
    writeLog("MP native teleport applied: pos=(%.3f, %.3f, %.3f) heading=%.3f",
             target.x, target.y, target.z, heading);
}

static void mpLiteApplyHealthPayload(const std::string& payload) {
    if (!nativeReady()) return;
    float health = 100.0f;
    const std::string text = trim(payload);
    if (!text.empty() && (!parseFloatValue(text, &health) || health <= 0.0f)) {
        g_status = "MP health failed: bad payload";
        writeLog("MP health bad payload: %s", payload.c_str());
        return;
    }

    Actor player = playerActor();
    if (player <= 0) return;
    nativeInvoke<void>(0x165BD4C5ULL, player, health);
    nativeInvoke<void>(0xFA090024ULL, player, health);
    g_status = "MP health set";
}

static void mpLiteApplyGodMode(bool enabled) {
    g_mpLocalGodMode = enabled;
    if (nativeReady()) {
        Actor player = playerActor();
        if (player > 0) {
            nativeInvoke<void>(0xE38EF526ULL, player, enabled ? TRUE : FALSE);
            nativeInvoke<void>(0x0D9A35F6ULL, player, enabled ? TRUE : FALSE);
        }
    }
    g_status = std::string("MP god mode ") + (enabled ? "enabled" : "disabled");
    mpLiteAddChatLine(g_status);
}

static void mpLiteApplyModelPayload(const std::string& payload) {
    int actorEnum = 0;
    if (!parseInteger(trim(payload), &actorEnum) || actorEnum <= 0 || actorEnum > 65535) {
        g_status = "MP model failed: bad actor enum";
        writeLog("MP model bad payload: %s", payload.c_str());
        return;
    }

    g_mpLocalActorEnum = actorEnum;
    if (!nativeReady()) {
        return;
    }

    Actor player = playerActor();
    Vector3 pos = {};
    if (player <= 0 || !actorPosition(player, &pos)) {
        g_status = "MP model sync updated";
        return;
    }

    Layout layout = ensureLayout();
    if (layout <= 0) {
        g_status = "MP model sync updated";
        return;
    }

    const float heading = nativeInvoke<float>(0x42DE39F0ULL, player);
    Vector2 spawnXY = {pos.x, pos.y};
    Vector2 orientXY = {0.0f, 1.0f};
    Actor respawned = nativeInvoke<Actor>(0x637E446BULL, layout, player,
                                          "codered_mp_player", actorEnum,
                                          spawnXY, pos.z, orientXY, heading, 0);
    if (respawned > 0 && nativeInvoke<BOOL>(0xBA6C3E92ULL, respawned)) {
        if (g_mpLocalGodMode) {
            nativeInvoke<void>(0xE38EF526ULL, respawned, TRUE);
            nativeInvoke<void>(0x0D9A35F6ULL, respawned, TRUE);
        }
        g_status = "MP model changed to " + std::to_string(actorEnum);
        writeLog("MP local player respawned with enum=%d actor=%d",
                 actorEnum, respawned);
    } else {
        g_status = "MP model sync updated";
        writeLog("MP local model respawn failed: enum=%d result=%d",
                 actorEnum, respawned);
    }
}

static void mpLiteSetNoClip(bool enabled) {
    g_mpNoClipActive = enabled;
    g_mpNoClipLastTickMs = GetTickCount();
    if (nativeReady()) {
        Actor player = playerActor();
        if (player > 0) {
            const BOOL frozen = nativeInvoke<BOOL>(0x9C12BD5AULL, player);
            if (enabled && !frozen) {
                nativeInvoke<void>(0x13E6B5EEULL, player, TRUE);
            } else if (!enabled && frozen) {
                nativeInvoke<void>(0x13E6B5EEULL, player, FALSE);
            }
        }
        if (enabled || !g_mpChatOpen) {
            nativeInvoke<void>(0xD17AFCD8ULL, -1, enabled ? FALSE : TRUE,
                               enabled ? 1 : 0, enabled ? TRUE : FALSE);
        }
    }
    g_status = std::string("MP noclip ") + (enabled ? "enabled" : "disabled");
    writeLog("MP noclip toggled: enabled=%d", enabled ? 1 : 0);
}

static float mpLiteNoClipSpeed() {
    static const float speeds[] = {10.0f, 50.0f, 100.0f, 300.0f};
    if (g_mpNoClipSpeedIndex < 0) g_mpNoClipSpeedIndex = 0;
    if (g_mpNoClipSpeedIndex >= static_cast<int>(sizeof(speeds) / sizeof(speeds[0]))) {
        g_mpNoClipSpeedIndex = static_cast<int>(sizeof(speeds) / sizeof(speeds[0])) - 1;
    }
    return speeds[g_mpNoClipSpeedIndex];
}

static Vector3 mpLiteHeadingVector(float heading, float correctionDegrees) {
    const float radians = (heading + correctionDegrees) * (PI / 180.0f);
    Vector3 out = {};
    out.x = -std::cos(radians);
    out.y = std::sin(radians);
    out.z = 0.0f;
    return out;
}

static void mpLiteNoClipTick() {
    if (!g_mpNoClipActive || !nativeReady()) return;
    if (g_mpChatOpen) return;

    if ((GetAsyncKeyState(VK_BACK) & 0x0001) != 0) {
        mpLiteSetNoClip(false);
        return;
    }
    if ((GetAsyncKeyState('Q') & 0x0001) != 0 && g_mpNoClipSpeedIndex > 0) {
        --g_mpNoClipSpeedIndex;
    }
    if ((GetAsyncKeyState('E') & 0x0001) != 0 && g_mpNoClipSpeedIndex < 3) {
        ++g_mpNoClipSpeedIndex;
    }

    Actor player = playerActor();
    Vector3 pos = {};
    if (player <= 0 || !actorPosition(player, &pos)) return;

    const DWORD now = GetTickCount();
    float dt = g_mpNoClipLastTickMs == 0 ? 0.016f :
        static_cast<float>(now - g_mpNoClipLastTickMs) / 1000.0f;
    g_mpNoClipLastTickMs = now;
    if (dt <= 0.0f) dt = 0.016f;
    if (dt > 0.1f) dt = 0.1f;

    float heading = nativeInvoke<float>(0x42DE39F0ULL, player);
    const int camera = nativeInvoke<int>(0x6B7677BFULL);
    if (camera > 0) {
        heading = nativeInvoke<float>(0x1C02D2F8ULL, camera);
    }

    float speed = mpLiteNoClipSpeed();
    if ((GetAsyncKeyState(VK_SHIFT) & 0x8000) != 0) {
        speed *= 2.0f;
    }
    const float delta = speed * dt;

    Vector3 move = {};
    const Vector3 forward = mpLiteHeadingVector(heading, 90.0f);
    const Vector3 right = mpLiteHeadingVector(heading, 180.0f);
    if ((GetAsyncKeyState('W') & 0x8000) != 0) {
        move.x += forward.x;
        move.y += forward.y;
    }
    if ((GetAsyncKeyState('S') & 0x8000) != 0) {
        move.x -= forward.x;
        move.y -= forward.y;
    }
    if ((GetAsyncKeyState('D') & 0x8000) != 0) {
        move.x += right.x;
        move.y += right.y;
    }
    if ((GetAsyncKeyState('A') & 0x8000) != 0) {
        move.x -= right.x;
        move.y -= right.y;
    }
    if ((GetAsyncKeyState(VK_SPACE) & 0x8000) != 0) {
        move.z += 1.0f;
    }
    if ((GetAsyncKeyState(VK_CONTROL) & 0x8000) != 0) {
        move.z -= 1.0f;
    }

    const float lengthSq = move.x * move.x + move.y * move.y + move.z * move.z;
    if (lengthSq > 0.0001f) {
        const float scale = delta / std::sqrt(lengthSq);
        pos.x += move.x * scale;
        pos.y += move.y * scale;
        pos.z += move.z * scale;
        mpLiteTeleportActorWithHeading(player, pos, heading);
    }
    nativeInvoke<void>(0xECE8520BULL, player, heading, TRUE);
}

static void mpLiteRequestTransportPropset(const std::string& payload) {
    std::vector<float> values;
    if (!parseFloatCsv(payload, values) || values.size() < 4) {
        g_status = "MP propset failed: bad payload";
        writeLog("MP propset bad payload: %s", payload.c_str());
        return;
    }
    g_mpTransportPropsetPosition = {values[0], values[1], values[2]};
    g_mpTransportPropsetHeading = values[3];
    g_mpTransportPropsetPending = true;
    g_mpTransportPropsetRequestedMs = GetTickCount();
    g_mpTransportPropsetAssetId = 0;
    g_status = "MP propset requested";
}

static void mpLiteTransportPropsetTick() {
    if (!g_mpTransportPropsetPending || !nativeReady()) return;

    if (g_mpTransportPropset > 0 &&
        nativeInvoke<BOOL>(0xD7E7187BULL, g_mpTransportPropset)) {
        g_mpTransportPropsetPending = false;
        return;
    }

    constexpr const char* kMpTransportRefGroup = "$/tune/refGroups/refgroups/mp_transport";
    constexpr int kAssetTypePropset = 7;
    nativeInvoke<int>(0x9AA02DA7ULL, kMpTransportRefGroup, kAssetTypePropset);
    if (g_mpTransportPropsetAssetId <= 0) {
        g_mpTransportPropsetAssetId =
            nativeInvoke<int>(0x6005B514ULL, kMpTransportRefGroup, kAssetTypePropset);
    }
    if (g_mpTransportPropsetAssetId <= 0) {
        return;
    }

    nativeInvoke<void>(0xEC1F14C8ULL, g_mpTransportPropsetAssetId);
    if (!nativeInvoke<BOOL>(0xF7D65903ULL, g_mpTransportPropsetAssetId)) {
        if (GetTickCount() - g_mpTransportPropsetRequestedMs > 10000) {
            g_mpTransportPropsetPending = false;
            g_status = "MP propset load timed out";
            writeLog("MP transport propset load timed out asset=%d",
                     g_mpTransportPropsetAssetId);
        }
        return;
    }

    Layout layout = nativeInvoke<Layout>(0x5699DE7EULL, "PlayerLayout");
    if (layout <= 0) {
        layout = ensureLayout();
    }
    if (layout <= 0) {
        return;
    }

    g_mpTransportPropset = nativeInvoke<int>(
        0x779267C3ULL, layout, "", kMpTransportRefGroup,
        g_mpTransportPropsetPosition.x, g_mpTransportPropsetPosition.y,
        g_mpTransportPropsetPosition.z, 0.0f, g_mpTransportPropsetHeading, 0.0f);
    nativeInvoke<void>(0x4A5E4C13ULL, g_mpTransportPropsetAssetId);
    g_mpTransportPropsetPending = false;

    if (g_mpTransportPropset > 0) {
        g_status = "MP Escalera propset spawned";
        writeLog("MP transport propset spawned: object=%d pos=(%.3f, %.3f, %.3f) heading=%.3f",
                 g_mpTransportPropset,
                 g_mpTransportPropsetPosition.x,
                 g_mpTransportPropsetPosition.y,
                 g_mpTransportPropsetPosition.z,
                 g_mpTransportPropsetHeading);
    } else {
        g_status = "MP propset create failed";
        writeLog("MP transport propset create failed");
    }
}

static void mpLiteApplyNativeCallRecord(const std::string& record) {
    const size_t split = record.find('|');
    if (split == std::string::npos || split == 0) return;

    char* end = nullptr;
    const unsigned long seq = std::strtoul(record.substr(0, split).c_str(), &end, 10);
    if (!end || *end != '\0' || seq == 0 || seq <= g_mpLastNativeCallSeq) {
        return;
    }
    g_mpLastNativeCallSeq = static_cast<unsigned int>(seq);

    std::string callText = record.substr(split + 1);
    std::string callName = callText;
    std::string payload;
    const size_t payloadSplit = callText.find(": ");
    if (payloadSplit != std::string::npos) {
        callName = callText.substr(0, payloadSplit);
        payload = callText.substr(payloadSplit + 2);
    }

    if (callName == "client_chat_echo") {
        return;
    }
    if (callName == "client_hello_world" || callName == "client_add_message") {
        mpLiteAddChatLine(payload);
        return;
    }
    if (callName == "client_teleport") {
        mpLiteApplyTeleportPayload(payload);
        return;
    }
    if (callName == "client_set_model") {
        mpLiteApplyModelPayload(payload);
        return;
    }
    if (callName == "client_kill_player") {
        Actor player = playerActor();
        if (player > 0) {
            nativeInvoke<void>(0x8B08ECA2ULL, player);
        }
        return;
    }
    if (callName == "client_set_health") {
        mpLiteApplyHealthPayload(payload);
        return;
    }
    if (callName == "client_god_toggle") {
        mpLiteApplyGodMode(!g_mpLocalGodMode);
        return;
    }
    if (callName == "client_noclip_toggle") {
        mpLiteSetNoClip(!g_mpNoClipActive);
        return;
    }
    if (callName == "client_spawn_transport_propset") {
        mpLiteRequestTransportPropset(payload);
        return;
    }

    g_status = "MP native unhandled: " + callName;
    writeLog("MP native call unhandled: %s payload=%s",
             callName.c_str(), payload.c_str());
}

static void mpLiteApplyWorldState() {
    if (!g_mpLiteActive) return;
    const std::string path = gamePath(g_mpBridgeWorldPath);
    const unsigned long long writeTime = fileWriteTime(path);
    if (writeTime == 0 || writeTime == g_mpWorldStateWriteTime) return;
    g_mpWorldStateWriteTime = writeTime;

    const std::string json = readSmallTextFile(path, 131072);
    if (json.empty()) return;

    const int playerId = jsonIntValue(json, "player_id", -1);
    if (playerId >= 0) {
        g_mpLocalPlayerId = playerId;
        g_mpLiteJoined = true;
    }
    g_mpLocalActorEnum = jsonIntValue(json, "spawn_actor_enum", g_mpLocalActorEnum);

    if (jsonBoolValue(json, "spawn_valid", false) && !g_mpSpawnApplied && nativeReady()) {
        Actor player = playerActor();
        if (player > 0) {
            Vector3 spawn = {};
            spawn.x = jsonFloatValue(json, "spawn_x", 0.0f);
            spawn.y = jsonFloatValue(json, "spawn_y", 0.0f);
            spawn.z = jsonFloatValue(json, "spawn_z", 0.0f);
            const float heading = jsonFloatValue(json, "spawn_heading", 0.0f);
            mpLiteTeleportActorWithHeading(player, spawn, heading);
            g_mpSpawnApplied = true;
            writeLog("MP local spawn applied: playerid=%d pos=(%.3f, %.3f, %.3f) heading=%.3f",
                     g_mpLocalPlayerId, spawn.x, spawn.y, spawn.z, heading);
        }
    }

    if (jsonArrayKeyPresent(json, "chat")) {
        const std::vector<std::string> chat = jsonStringArrayValue(json, "chat");
        if (mpLiteChatAcknowledgedByServer(chat)) {
            mpLiteRemoveNoticeLine("[you] " + g_mpPendingChat);
            g_mpPendingChat.clear();
            g_mpPendingChatStartedMs = 0;
            mpLiteWriteLocalState(true);
        }
        g_mpChatLines = chat;
        if (g_mpChatLines.size() > 16) {
            g_mpChatLines.erase(g_mpChatLines.begin(), g_mpChatLines.end() - 16);
        }
    }

    if (jsonArrayKeyPresent(json, "native_calls")) {
        const std::vector<std::string> nativeCalls = jsonStringArrayValue(json, "native_calls");
        for (const std::string& record : nativeCalls) {
            mpLiteApplyNativeCallRecord(record);
        }
    }

    const std::string playersNeedle = "\"players\"";
    size_t playersPos = json.find(playersNeedle);
    if (playersPos != std::string::npos) {
        size_t pos = json.find('[', playersPos + playersNeedle.size());
        const size_t end = pos == std::string::npos ? std::string::npos : jsonArrayEnd(json, pos);
        while (pos != std::string::npos && end != std::string::npos && pos < end) {
            const size_t objectStart = json.find('{', pos + 1);
            if (objectStart == std::string::npos || objectStart >= end) break;
            const size_t objectEnd = json.find('}', objectStart + 1);
            if (objectEnd == std::string::npos || objectEnd > end) break;
            const std::string objectText = json.substr(objectStart, objectEnd - objectStart + 1);

            MpRemoteActor parsed;
            if (mpLiteParsePlayerObject(objectText, parsed) &&
                parsed.playerId != g_mpLocalPlayerId) {
                MpRemoteActor* remote = mpLiteRemoteById(parsed.playerId);
                Actor existingActor = remote->actor;
                if (existingActor > 0 && remote->actorEnum != parsed.actorEnum &&
                    mpLiteRemoteActorValid(*remote)) {
                    nativeInvoke<void>(0x8BD21869ULL, existingActor);
                    existingActor = 0;
                    writeLog("MP remote respawn requested: playerid=%d enum %d -> %d",
                             parsed.playerId, remote->actorEnum, parsed.actorEnum);
                }
                *remote = parsed;
                remote->actor = existingActor;
                mpLiteApplyRemoteState(*remote);
            }
            pos = objectEnd + 1;
        }
    }

    mpLitePruneStaleRemotes();
}

static void mpLiteSendChat() {
    std::string text = trim(g_mpChatDraft);
    if (text.empty()) {
        g_mpChatDraft.clear();
        g_mpChatOpen = false;
        return;
    }
    if (text.size() > 96) text.resize(96);
    g_mpPendingChat = text;
    ++g_mpChatSeq;
    g_mpPendingChatStartedMs = GetTickCount();
    mpLiteAddChatLine("[you] " + text);
    g_mpChatDraft.clear();
    g_mpChatOpen = false;
    mpLiteWriteLocalState(true);
}

static char mpLiteCharFromKey(DWORD key) {
    const bool shift = (GetAsyncKeyState(VK_SHIFT) & 0x8000) != 0;
    if (key >= 'A' && key <= 'Z') {
        char c = static_cast<char>(key);
        return shift ? c : static_cast<char>(std::tolower(c));
    }
    if (key >= '0' && key <= '9') {
        if (!shift) return static_cast<char>(key);
        const char shifted[] = {')', '!', '@', '#', '$', '%', '^', '&', '*', '('};
        return shifted[key - '0'];
    }
    if (key == VK_SPACE) return ' ';
    if (key == VK_OEM_PERIOD) return shift ? '>' : '.';
    if (key == VK_OEM_COMMA) return shift ? '<' : ',';
    if (key == VK_OEM_MINUS) return shift ? '_' : '-';
    if (key == VK_OEM_PLUS) return shift ? '+' : '=';
    if (key == VK_OEM_2) return shift ? '?' : '/';
    if (key == VK_OEM_1) return shift ? ':' : ';';
    if (key == VK_OEM_7) return shift ? '"' : '\'';
    return 0;
}

static bool mpLiteHandleKey(DWORD key) {
    if (!g_mpLiteActive || g_menuOpen) return false;
    if (!g_mpChatOpen) {
        if (key == 'T') {
            g_mpChatOpen = true;
            g_mpChatDraft.clear();
            return true;
        }
        return false;
    }

    if (key == VK_RETURN) {
        mpLiteSendChat();
        return true;
    }
    if (key == VK_ESCAPE) {
        g_mpChatDraft.clear();
        g_mpChatOpen = false;
        return true;
    }
    if (key == VK_BACK) {
        if (!g_mpChatDraft.empty()) g_mpChatDraft.pop_back();
        return true;
    }
    const char c = mpLiteCharFromKey(key);
    if (c != 0 && g_mpChatDraft.size() < 96) {
        g_mpChatDraft.push_back(c);
        return true;
    }
    return true;
}

static void mpLiteDrawOverlay() {
    if (!g_mpLiteActive) return;

    constexpr float boxLeft = 0.020f;
    constexpr float boxTop = 0.030f;
    constexpr float boxWidth = 0.470f;
    constexpr float boxHeight = 0.235f;
    constexpr float textLeft = boxLeft + 0.010f;
    drawRectSafe(boxLeft + boxWidth * 0.5f, boxTop + boxHeight * 0.5f,
                 boxWidth, boxHeight, 5, 5, 8, 178, 0.010f);

    std::string title = "CodeRED MP Lite";
    if (g_mpLiteJoined) {
        title += " | player " + std::to_string(g_mpLocalPlayerId) +
                 " | remotes " + std::to_string(g_mpRemoteActors.size()) +
                 " | bare " + (g_mpBareWorldEnabled ? std::string("on") : std::string("off")) +
                 " | noclip " + (g_mpNoClipActive ? std::string("on") : std::string("off"));
    } else {
        title += " | joining";
    }
    drawTextSafe(textLeft, boxTop + 0.010f, mpLiteClipText(title, 74).c_str(),
                 255, 235, 235, 235, FONT_REDEMPTION, 0.018f, JUSTIFY_LEFT);
    drawTextSafe(textLeft, boxTop + 0.035f, "T chat | F8 menu",
                 220, 220, 220, 220, FONT_REDEMPTION, 0.014f, JUSTIFY_LEFT);
    std::string bareLine = "bare cleaned " +
                           std::to_string(g_mpBareWorldLastDestroyed) +
                           " last | " +
                           std::to_string(g_mpBareWorldTotalDestroyed) +
                           " total";
    drawTextSafe(textLeft, boxTop + 0.058f, bareLine.c_str(),
                 190, 205, 205, 210, FONT_REDEMPTION, 0.013f, JUSTIFY_LEFT);

    std::vector<std::string> lines = g_mpChatLines;
    lines.insert(lines.end(), g_mpNoticeLines.begin(), g_mpNoticeLines.end());
    if (lines.size() > 16) {
        lines.erase(lines.begin(), lines.end() - 16);
    }

    constexpr float lineHeight = 0.020f;
    const float chatTop = boxTop + 0.084f;
    const float inputY = boxTop + boxHeight - 0.030f;
    const float chatBottom = g_mpChatOpen ? inputY - 0.012f : boxTop + boxHeight - 0.024f;
    const int maxLines = std::max(0, static_cast<int>((chatBottom - chatTop) / lineHeight) + 1);
    const int visibleLines = std::min(static_cast<int>(lines.size()), maxLines);
    const int firstLine = static_cast<int>(lines.size()) - visibleLines;
    float y = chatBottom - static_cast<float>(visibleLines - 1) * lineHeight;
    for (int i = 0; i < visibleLines; ++i) {
        const std::string line = mpLiteClipText(lines[firstLine + i], 68);
        drawTextSafe(textLeft, y, line.c_str(), 235, 235, 235, 220,
                     FONT_REDEMPTION, 0.014f, JUSTIFY_LEFT);
        y += lineHeight;
    }
    if (g_mpChatOpen) {
        const std::string draft = mpLiteClipText("> " + g_mpChatDraft + "_", 70);
        drawTextSafe(textLeft, inputY, draft.c_str(), 255, 170, 170, 240,
                     FONT_REDEMPTION, 0.015f, JUSTIFY_LEFT);
    }
}

static void mpLiteApplyChatControlSuppression() {
    if (!nativeReady()) return;
    if (g_mpChatOpen) {
        nativeInvoke<void>(0xD17AFCD8ULL, -1, FALSE, 1, TRUE);
        nativeInvoke<void>(0x0959C27AULL, -1, TRUE);
        g_mpChatControlsSuppressed = true;
        return;
    }
    if (g_mpChatControlsSuppressed && !g_mpNoClipActive) {
        nativeInvoke<void>(0x0959C27AULL, -1, FALSE);
        nativeInvoke<void>(0xD17AFCD8ULL, -1, TRUE, 0, FALSE);
        g_mpChatControlsSuppressed = false;
    }
}

static void mpLiteTick() {
    if (!g_mpLiteActive) return;
    pollMpClientStatus();
    mpLiteApplyWorldState();
    mpLiteApplyChatControlSuppression();
    mpBareWorldTick(false);
    mpLiteTransportPropsetTick();
    mpLiteNoClipTick();
    mpLiteWriteLocalState(false);
}

static BOOL CALLBACK mpLiteFindGameWindow(HWND hwnd, LPARAM param) {
    DWORD processId = 0;
    GetWindowThreadProcessId(hwnd, &processId);
    if (processId != GetCurrentProcessId() || !IsWindowVisible(hwnd) ||
        GetWindow(hwnd, GW_OWNER) != nullptr) {
        return TRUE;
    }
    *reinterpret_cast<HWND*>(param) = hwnd;
    return FALSE;
}

static LRESULT CALLBACK mpLiteWndProc(HWND hwnd, UINT message, WPARAM wParam, LPARAM lParam) {
    if (g_mpLiteActive) {
        if ((message == WM_KEYDOWN || message == WM_SYSKEYDOWN) &&
            (g_mpChatOpen || (!g_menuOpen && static_cast<DWORD>(wParam) == 'T'))) {
            mpLiteHandleKey(static_cast<DWORD>(wParam));
            return 0;
        }
        if (g_mpChatOpen &&
            (message == WM_CHAR || message == WM_SYSCHAR ||
             message == WM_KEYUP || message == WM_SYSKEYUP)) {
            return 0;
        }
    }
    return CallWindowProc(g_originalWndProc, hwnd, message, wParam, lParam);
}

static void mpLiteInstallInputFilter() {
    if (g_originalWndProc != nullptr) return;
    HWND hwnd = nullptr;
    EnumWindows(mpLiteFindGameWindow, reinterpret_cast<LPARAM>(&hwnd));
    if (!hwnd) {
        writeLog("MP chat input filter: game window not found");
        return;
    }
    SetLastError(0);
    LONG_PTR previous = SetWindowLongPtr(hwnd, GWLP_WNDPROC,
                                         reinterpret_cast<LONG_PTR>(mpLiteWndProc));
    if (previous == 0 && GetLastError() != 0) {
        writeLog("MP chat input filter install failed: error=%lu", GetLastError());
        return;
    }
    g_gameWindow = hwnd;
    g_originalWndProc = reinterpret_cast<WNDPROC>(previous);
    writeLog("MP chat input filter installed");
}

static void mpLiteUninstallInputFilter() {
    if (!g_gameWindow || !g_originalWndProc) return;
    SetWindowLongPtr(g_gameWindow, GWLP_WNDPROC,
                     reinterpret_cast<LONG_PTR>(g_originalWndProc));
    g_gameWindow = nullptr;
    g_originalWndProc = nullptr;
}

static void mpLiteBegin() {
    g_mpLiteActive = true;
    g_mpLiteJoined = false;
    g_mpSpawnApplied = false;
    g_mpChatOpen = false;
    g_mpChatControlsSuppressed = false;
    g_mpChatDraft.clear();
    g_mpPendingChat.clear();
    g_mpLocalPlayerId = -1;
    g_mpStateSeq = 0;
    g_mpChatSeq = 0;
    g_mpPendingChatStartedMs = 0;
    g_mpLastLocalStateMs = 0;
    g_mpBareWorldLastTickMs = 0;
    g_mpBareWorldLastPopulationMs = 0;
    g_mpBareWorldLastSeen = 0;
    g_mpBareWorldLastProtected = 0;
    g_mpBareWorldLastDestroyed = 0;
    g_mpBareWorldTotalDestroyed = 0;
    g_mpLastNativeCallSeq = 0;
    g_mpWorldStateWriteTime = 0;
    g_mpNoClipActive = false;
    g_mpNoClipLastTickMs = 0;
    g_mpNoClipSpeedIndex = 1;
    g_mpLocalGodMode = false;
    g_mpTransportPropsetPending = false;
    g_mpTransportPropset = 0;
    g_mpTransportPropsetAssetId = 0;
    g_mpTransportPropsetRequestedMs = 0;
    g_mpTransportPropsetPosition = {};
    g_mpTransportPropsetHeading = 0.0f;
    g_mpRemoteActors.clear();
    g_mpChatLines.clear();
    g_mpNoticeLines.clear();
    mpLiteAddChatLine("MP Lite connecting...");
    mpLiteInstallInputFilter();
    writeLog("MP Lite bridge started: input=%s world=%s",
             g_mpBridgeInputPath.c_str(), g_mpBridgeWorldPath.c_str());
}

static void saveOriginalPlayerFaction(Actor player) {
    if (g_savedPlayerFaction || player <= 0 || !nativeReady()) return;
    g_originalPlayerFaction = nativeInvoke<int>(0x52E2A611, player);
    if (g_originalPlayerFaction <= 0) {
        g_originalPlayerFaction = FACTION_PLAYER;
    }
    g_savedPlayerFaction = true;
    writeLog("Saved original player faction: %d", g_originalPlayerFaction);
}

static void setPlayerFactionSide(int faction, const char* label) {
    Actor player = playerActor();
    if (player <= 0) {
        g_status = "Player actor not ready";
        writeLog("Faction side failed: player actor invalid label=%s", label);
        return;
    }
    saveOriginalPlayerFaction(player);
    nativeInvoke<void>(0xCC63951A, player, faction);
    g_playerSideFaction = faction;
    g_status = std::string("Player side: ") + label + " faction " +
               std::to_string(faction);
    writeLog("Player faction set: label=%s faction=%d", label, faction);
}

static void restorePlayerFaction() {
    Actor player = playerActor();
    if (player <= 0) {
        g_status = "Player actor not ready";
        return;
    }
    const int restoreFaction = g_savedPlayerFaction ? g_originalPlayerFaction : FACTION_PLAYER;
    nativeInvoke<void>(0xCC63951A, player, restoreFaction);
    g_playerSideFaction = restoreFaction;
    g_status = "Player faction restored: " + std::to_string(restoreFaction);
    writeLog("Player faction restored: faction=%d", restoreFaction);
}

static void configureSpawnedAsLawmen(bool followPlayer) {
    Actor player = playerActor();
    pruneSpawnedActors();
    if (g_spawnedActors.empty()) {
        g_status = "No spawned actors to set as lawmen";
        writeLog("Lawman configure skipped: no spawned actors");
        return;
    }

    for (Actor actor : g_spawnedActors) {
        nativeInvoke<void>(0xCC63951A, actor, FACTION_US_LAW);
        nativeInvoke<void>(0x4C94EB9E, actor, TRUE);
        if (followPlayer && player > 0) {
            nativeInvoke<void>(0x12F0911A, actor, player);
        }
    }
    g_status = "Spawned actors set to US law";
    writeLog("Configured %zu spawned actor(s) as US law", g_spawnedActors.size());
}

static Actor nearestHostileToPlayer(float maxDistance) {
    if (!nativeReady() || !g_worldGetAllActors) return 0;
    Actor player = playerActor();
    if (player <= 0) return 0;

    Vector3 playerPos = {};
    if (!actorPosition(player, &playerPos)) return 0;

    constexpr int MAX_ACTORS = 512;
    int actors[MAX_ACTORS] = {};
    const int count = g_worldGetAllActors(actors, MAX_ACTORS);
    const float maxDistanceSq = maxDistance * maxDistance;
    float bestDistanceSq = maxDistanceSq;
    Actor best = 0;

    for (int i = 0; i < count && i < MAX_ACTORS; ++i) {
        Actor candidate = actors[i];
        if (candidate <= 0 || candidate == player) continue;
        if (isCodeRedSpawnedActor(candidate)) continue;
        if (!nativeInvoke<BOOL>(0xBA6C3E92, candidate)) continue;

        const int hostileA = nativeInvoke<int>(0x9AB964F4, candidate, player);
        const int hostileB = nativeInvoke<int>(0x9AB964F4, player, candidate);
        if (!hostileA && !hostileB) continue;

        Vector3 pos = {};
        if (!actorPosition(candidate, &pos)) continue;
        const float distSq = distanceSquared(playerPos, pos);
        if (distSq < bestDistanceSq) {
            bestDistanceSq = distSq;
            best = candidate;
        }
    }

    return best;
}

static void attackNearestHostileWithSpawned() {
    pruneSpawnedActors();
    if (g_spawnedActors.empty()) {
        g_status = "No spawned actors";
        writeLog("Attack hostile skipped: no spawned actors");
        return;
    }

    Actor target = nearestHostileToPlayer(90.0f);
    if (target <= 0) {
        g_status = "No nearby hostile found";
        writeLog("Attack hostile skipped: no target");
        return;
    }

    for (Actor actor : g_spawnedActors) {
        nativeInvoke<void>(0x16876A25, actor);
        nativeInvoke<void>(0x1AE4B75B, actor, target);
    }
    g_status = "Attack target sent: " + std::to_string(target);
    writeLog("Attack hostile sent: target=%d actors=%zu", target,
             g_spawnedActors.size());
}

static bool spawnSelectedNpc() {
    if (!nativeReady()) {
        g_status = "Native bridge unavailable";
        writeLog("Spawn failed: native bridge unavailable");
        return false;
    }

    const std::string npc = selectedNpc();
    const int actorEnum = selectedActorEnum();
    if (actorEnum <= 0) {
        g_status = "No actor enum for: " + npc;
        writeLog("Spawn failed: selected label did not resolve to an actor enum: %s",
                 npc.c_str());
        return false;
    }

    Actor player = playerActor();
    if (player <= 0) {
        g_status = "Player actor not ready";
        writeLog("Spawn failed: player actor was not valid");
        return false;
    }

    Layout layout = ensureLayout();
    if (layout <= 0) {
        g_status = "Could not create layout";
        writeLog("Spawn failed: CodeRED layout could not be found or created");
        return false;
    }

    Vector3 playerPos = {};
    nativeInvoke<void>(0x99BD9D6F, player, &playerPos);
    float heading = nativeInvoke<float>(0x42DE39F0, player);
    const float radians = heading * (PI / 180.0f);
    Vector2 spawnXY = {
        playerPos.x + std::sin(radians) * 2.0f,
        playerPos.y + std::cos(radians) * 2.0f
    };
    Vector2 orientXY = {0.0f, 1.0f};

    std::ostringstream instanceName;
    instanceName << "codered_ai_guest_" << ++g_spawnCounter;

    Actor spawned = nativeInvoke<Actor>(0x8D67F397, layout,
                                        instanceName.str().c_str(),
                                        actorEnum, spawnXY, playerPos.z,
                                        orientXY, heading);
    if (spawned <= 0 || !nativeInvoke<BOOL>(0xBA6C3E92, spawned)) {
        g_status = "Spawn native returned invalid actor";
        writeLog("Spawn failed: CREATE_ACTOR_IN_LAYOUT returned actor=%d enum=%d model=%s",
                 spawned, actorEnum, npc.c_str());
        return false;
    }

    g_spawnedActors.push_back(spawned);
    nativeInvoke<void>(0xECE8520B, spawned, heading, TRUE);
    nativeInvoke<void>(0x4C94EB9E, spawned, TRUE);
    nativeInvoke<void>(0x12F0911A, spawned, player);

    g_status = "Spawned actor " + std::to_string(spawned) + " enum " +
               std::to_string(actorEnum);
    writeLog("Spawn succeeded: actor=%d enum=%d model=%s", spawned, actorEnum,
             npc.c_str());
    return true;
}

static void commandSpawnedActors(const std::string& action) {
    if (!nativeReady()) {
        g_status = "Native bridge unavailable";
        writeLog("Action failed: native bridge unavailable action=%s",
                 action.c_str());
        return;
    }

    pruneSpawnedActors();
    if (g_spawnedActors.empty()) {
        g_status = "No CodeRED spawned actors";
        writeLog("Action skipped: no spawned actors action=%s", action.c_str());
        return;
    }

    Actor player = playerActor();
    if (player <= 0) {
        g_status = "Player actor not ready";
        writeLog("Action failed: player actor invalid action=%s", action.c_str());
        return;
    }

    if (action == "follow_player_request" ||
        action == "defend_player_request") {
        for (Actor actor : g_spawnedActors) {
            nativeInvoke<void>(0x4C94EB9E, actor, TRUE);
            nativeInvoke<void>(0x12F0911A, actor, player);
        }
        g_status = "Follow/defend sent to " +
                   std::to_string(g_spawnedActors.size()) + " actor(s)";
        writeLog("Follow/defend task sent to %zu actor(s)",
                 g_spawnedActors.size());
        return;
    }

    if (action == "guard_position_request" ||
        action == "idle_spawned_request") {
        for (Actor actor : g_spawnedActors) {
            nativeInvoke<void>(0x16876A25, actor);
            nativeInvoke<void>(0x6F80965D, actor, -1.0f, 0, 0);
        }
        g_status = "Stand guard sent to " +
                   std::to_string(g_spawnedActors.size()) + " actor(s)";
        writeLog("Stand guard task sent to %zu actor(s)",
                 g_spawnedActors.size());
        return;
    }

    if (action == "wander_spawned_request") {
        for (Actor actor : g_spawnedActors) {
            nativeInvoke<void>(0x16876A25, actor);
            nativeInvoke<void>(0x17BCA08E, actor, 0);
        }
        g_status = "Wander sent to " +
                   std::to_string(g_spawnedActors.size()) + " actor(s)";
        writeLog("Wander task sent to %zu actor(s)", g_spawnedActors.size());
        return;
    }

    if (action == "regroup_near_player_request") {
        for (Actor actor : g_spawnedActors) {
            nativeInvoke<void>(0x3EB7590C, actor, player, 2.0f, 4.0f);
        }
        g_status = "Regroup sent to " +
                   std::to_string(g_spawnedActors.size()) + " actor(s)";
        writeLog("Regroup task sent to %zu actor(s)", g_spawnedActors.size());
        return;
    }

    if (action == "dismiss_ai_guest_request") {
        for (Actor actor : g_spawnedActors) {
            nativeInvoke<void>(0x8BD21869, actor);
        }
        const size_t count = g_spawnedActors.size();
        g_spawnedActors.clear();
        g_status = "Dismissed " + std::to_string(count) + " actor(s)";
        writeLog("Dismissed %zu spawned actor(s)", count);
        return;
    }

    if (action == "make_spawned_lawmen_request") {
        configureSpawnedAsLawmen(true);
        return;
    }

    if (action == "attack_nearest_hostile_request") {
        attackNearestHostileWithSpawned();
        return;
    }

    g_status = "Unsupported action: " + displayAction(action);
    writeLog("Unsupported behavior action: %s", action.c_str());
}

static bool scriptExists(const char* scriptPath) {
    if (!scriptPath || !scriptPath[0] || !nativeReady()) return false;
    return nativeInvoke<BOOL>(0xDEAB87AB, scriptPath) != 0;
}

static int launchScriptPath(const char* scriptPath) {
    if (!scriptPath || !scriptPath[0] || !nativeReady()) return 0;
    int handle = nativeInvoke<int>(0x85A30503, scriptPath, 0);
    if (handle <= 0) {
        handle = nativeInvoke<int>(0x3F166D0E, scriptPath, 4096);
    }
    return handle;
}

static int launchFirstExistingScript(const char* label, const char* const* paths, size_t count) {
    int checked = 0;
    for (size_t i = 0; i < count; ++i) {
        const char* path = paths[i];
        if (!path || !path[0]) continue;
        ++checked;
        const bool exists = scriptExists(path);
        writeLog("MP script probe: label=%s path=%s exists=%s",
                 label, path, exists ? "true" : "false");
        if (!exists) continue;

        const int handle = launchScriptPath(path);
        writeLog("MP script launch: label=%s path=%s handle=%d",
                 label, path, handle);
        if (handle > 0) {
            g_status = std::string("MP launch ") + label + " handle " +
                       std::to_string(handle);
            return handle;
        }
    }

    g_status = std::string("MP script not found: ") + label +
               " checked " + std::to_string(checked);
    return 0;
}

static void mpStatusProbe() {
    const BOOL wasLastResetForMp = nativeInvoke<BOOL>(0x3B004817);
    const BOOL simulateStartMp = nativeInvoke<BOOL>(0x9A73C2CD);
    const BOOL inSession = nativeInvoke<BOOL>(0x8CA54980);
    const BOOL isHost = nativeInvoke<BOOL>(0xCDAC0F0E);

    const char* const probes[] = {
        "multiplayer/freemode/freemode",
        "multiplayer/freemode/freemode.csc",
        "content/release/multiplayer/freemode/freemode.csc",
        "release/multiplayer/freemode/freemode.csc",
        "multiplayer/multiplayer_system_thread",
        "multiplayer/multiplayer_update_thread",
        "multiplayer/deathmatch/deathmatch",
        "multiplayer/ctf/ctf_base_game",
    };
    int found = 0;
    for (const char* path : probes) {
        if (scriptExists(path)) ++found;
    }

    g_status = "MP probe reset=" + std::to_string(wasLastResetForMp) +
               " sim=" + std::to_string(simulateStartMp) +
               " session=" + std::to_string(inSession) +
               " scripts=" + std::to_string(found);
    writeLog("MP status: wasLastResetForMP=%d simulateStartMP=%d inSession=%d isHost=%d scriptProbeFound=%d",
             wasLastResetForMp, simulateStartMp, inSession, isHost, found);
}

static std::string quoteCommandArg(const std::string& value) {
    std::string out = "\"";
    for (char c : value) {
        if (c == '"') out += '\\';
        out += c;
    }
    out += "\"";
    return out;
}

static void writeMpConnectRequest(const std::string& status) {
    createParentDirs(g_mpConnectRequestPath);

    std::ofstream file(g_mpConnectRequestPath.c_str(), std::ios::trunc);
    if (!file) {
        writeLog("MP localhost connect request write failed: path=%s",
                 g_mpConnectRequestPath.c_str());
        return;
    }

    std::time_t now = std::time(nullptr);
    file << "{\n";
    file << "  \"source\": \"CodeRED_AI_Menu\",\n";
    file << "  \"action\": \"mp_connect_localhost_request\",\n";
    file << "  \"transport\": \"slikenet\",\n";
    file << "  \"host\": \"127.0.0.1\",\n";
    file << "  \"port\": 7777,\n";
    file << "  \"client\": \"" << jsonEscape(g_mpClientPath) << "\",\n";
    file << "  \"client_status\": \"" << jsonEscape(g_mpClientStatusPath) << "\",\n";
    file << "  \"bridge_input\": \"" << jsonEscape(g_mpBridgeInputPath) << "\",\n";
    file << "  \"bridge_world\": \"" << jsonEscape(g_mpBridgeWorldPath) << "\",\n";
    file << "  \"status\": \"" << jsonEscape(status) << "\",\n";
    file << "  \"timestamp\": " << static_cast<long long>(now) << "\n";
    file << "}\n";
}

static void pollMpClientStatus() {
    if (g_mpClientStatusPath.empty()) {
        return;
    }

    const std::string statusPath = gamePath(g_mpClientStatusPath);
    const unsigned long long writeTime = fileWriteTime(statusPath);
    if (writeTime == 0 || writeTime == g_mpClientStatusWriteTime) {
        return;
    }
    g_mpClientStatusWriteTime = writeTime;

    const std::string json = readSmallTextFile(statusPath);
    if (json.empty()) {
        return;
    }

    const std::string state = jsonStringValue(json, "state");
    const std::string summary = jsonStringValue(json, "summary");
    const std::string nativeCall = jsonStringValue(json, "native_call");
    if (!nativeCall.empty()) {
        g_status = "MP native: " + nativeCall;
    } else if (!summary.empty()) {
        g_status = "MP " + summary;
    } else if (!state.empty()) {
        g_status = "MP client " + state;
    }
    writeLog("MP client status updated: state=%s summary=%s native_call=%s",
             state.c_str(), summary.c_str(), nativeCall.c_str());
}

static void mpConnectLocalhost() {
    const std::string gameDir = gameDirectory();
    const std::string clientPath = gamePath(g_mpClientPath);
    const std::string statusPath = gamePath(g_mpClientStatusPath);
    const std::string bridgeInputPath = gamePath(g_mpBridgeInputPath);
    const std::string bridgeWorldPath = gamePath(g_mpBridgeWorldPath);
    const std::string stdoutPath = gamePath("scratch/codered_mp_client_stdout.log");

    createParentDirs(statusPath);
    createParentDirs(bridgeInputPath);
    createParentDirs(bridgeWorldPath);
    createParentDirs(stdoutPath);

    const std::string cmdLine = quoteCommandArg(clientPath) +
        " --host " + quoteCommandArg(g_mpServerHost) +
        " --port " + std::to_string(g_mpServerPort) +
        " --name " + quoteCommandArg(g_mpPlayerName) +
        " --seconds 0 --status " +
        quoteCommandArg(statusPath) +
        " --bridge-in " + quoteCommandArg(bridgeInputPath) +
        " --bridge-out " + quoteCommandArg(bridgeWorldPath);

    std::vector<char> mutableCmd(cmdLine.begin(), cmdLine.end());
    mutableCmd.push_back('\0');

    STARTUPINFOA startupInfo = {};
    startupInfo.cb = sizeof(startupInfo);
    SECURITY_ATTRIBUTES securityAttributes = {};
    securityAttributes.nLength = sizeof(securityAttributes);
    securityAttributes.bInheritHandle = TRUE;
    HANDLE stdoutFile = CreateFileA(stdoutPath.c_str(), GENERIC_WRITE,
                                    FILE_SHARE_READ | FILE_SHARE_WRITE,
                                    &securityAttributes, CREATE_ALWAYS,
                                    FILE_ATTRIBUTE_NORMAL, nullptr);
    if (stdoutFile != INVALID_HANDLE_VALUE) {
        startupInfo.dwFlags |= STARTF_USESTDHANDLES;
        startupInfo.hStdOutput = stdoutFile;
        startupInfo.hStdError = stdoutFile;
        startupInfo.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
    }
    PROCESS_INFORMATION processInfo = {};

    DeleteFileA(statusPath.c_str());
    DeleteFileA(bridgeInputPath.c_str());
    DeleteFileA(bridgeWorldPath.c_str());
    g_mpClientStatusWriteTime = 0;
    g_mpWorldStateWriteTime = 0;

    const BOOL started = CreateProcessA(
        clientPath.c_str(),
        mutableCmd.data(),
        nullptr,
        nullptr,
        stdoutFile != INVALID_HANDLE_VALUE,
        CREATE_NO_WINDOW,
        nullptr,
        gameDir.c_str(),
        &startupInfo,
        &processInfo);

    if (stdoutFile != INVALID_HANDLE_VALUE) {
        CloseHandle(stdoutFile);
    }

    if (started) {
        CloseHandle(processInfo.hThread);
        CloseHandle(processInfo.hProcess);
        mpLiteBegin();
        mpLiteWriteLocalState(true);
        g_status = "MP connect " + g_mpServerHost + ":" + std::to_string(g_mpServerPort) + " started";
        writeMpConnectRequest("started");
        writeLog("MP connect started: cwd=%s command=%s stdout=%s",
                 gameDir.c_str(), cmdLine.c_str(), stdoutPath.c_str());
    } else {
        const DWORD err = GetLastError();
        g_status = "MP client start failed err=" + std::to_string(err);
        writeMpConnectRequest("start_failed");
        writeLog("MP connect failed: cwd=%s command=%s err=%lu",
                 gameDir.c_str(), cmdLine.c_str(), err);
    }
}

static void mpEnableMultiplayer() {
    const int result = nativeInvoke<int>(0x9180FF1C, TRUE);
    const BOOL inSession = nativeInvoke<BOOL>(0x8CA54980);
    const BOOL isHost = nativeInvoke<BOOL>(0xCDAC0F0E);
    g_status = "NET_ENABLE_MULTIPLAYER result=" + std::to_string(result) +
               " session=" + std::to_string(inSession);
    writeLog("MP enable: NET_ENABLE_MULTIPLAYER result=%d inSession=%d isHost=%d",
             result, inSession, isHost);
}

static void mpEnterNetworkingUi() {
    const char* const layers[] = {
        "networking",
        "net",
        "pausemenu",
        "pausemenu_networking",
        "content/ui/pausemenu/networking.sc.xml",
    };
    for (const char* layer : layers) {
        nativeInvoke<void>(0x594F2657, layer);
        writeLog("MP UI enter attempted: %s", layer);
    }
    g_status = "Requested MP/networking UI layers";
}

static void mpStartCoreThreads() {
    const char* const systemThread[] = {
        "multiplayer/multiplayer_system_thread",
        "multiplayer/multiplayer_system_thread.csc",
        "content/release/multiplayer/multiplayer_system_thread.csc",
        "release/multiplayer/multiplayer_system_thread.csc",
    };
    const char* const updateThread[] = {
        "multiplayer/multiplayer_update_thread",
        "multiplayer/multiplayer_update_thread.csc",
        "content/release/multiplayer/multiplayer_update_thread.csc",
        "release/multiplayer/multiplayer_update_thread.csc",
    };
    const int systemHandle = launchFirstExistingScript("mp_system_thread", systemThread, _countof(systemThread));
    const int updateHandle = launchFirstExistingScript("mp_update_thread", updateThread, _countof(updateThread));
    g_status = "MP threads sys=" + std::to_string(systemHandle) +
               " upd=" + std::to_string(updateHandle);
}

static void mpLaunchFreemode() {
    const char* const paths[] = {
        "multiplayer/freemode/freemode",
        "multiplayer/freemode/freemode.csc",
        "content/release/multiplayer/freemode/freemode.csc",
        "release/multiplayer/freemode/freemode.csc",
        "freemode",
    };
    launchFirstExistingScript("freemode", paths, _countof(paths));
}

static void mpLaunchDeathmatch() {
    const char* const paths[] = {
        "multiplayer/deathmatch/deathmatch",
        "multiplayer/deathmatch/deathmatch.csc",
        "content/release/multiplayer/deathmatch/deathmatch.csc",
        "release/multiplayer/deathmatch/deathmatch.csc",
        "deathmatch",
    };
    launchFirstExistingScript("deathmatch", paths, _countof(paths));
}

static void mpLaunchCtf() {
    const char* const paths[] = {
        "multiplayer/ctf/ctf_base_game",
        "multiplayer/ctf/ctf_base_game.csc",
        "content/release/multiplayer/ctf/ctf_base_game.csc",
        "release/multiplayer/ctf/ctf_base_game.csc",
        "ctf_base_game",
    };
    launchFirstExistingScript("ctf", paths, _countof(paths));
}

struct OverridePatchFile {
    std::string fileName;
    std::string sourcePath;
    std::string stagedPath;
    unsigned long long size;
};

static bool isPatchRpfName(const char* name) {
    if (!name) return false;
    std::string text = lowerCopy(name);
    if (text.size() < 10) return false;
    if (text.rfind("patch", 0) != 0) return false;
    if (text.compare(text.size() - 4, 4, ".rpf") != 0) return false;
    for (size_t i = 5; i + 4 < text.size(); ++i) {
        if (!std::isdigit(static_cast<unsigned char>(text[i]))) return false;
    }
    return true;
}

static int patchNumberFromName(const std::string& fileName) {
    std::string text = lowerCopy(fileName);
    if (text.rfind("patch", 0) != 0) return INT_MAX;
    const size_t dot = text.rfind(".rpf");
    if (dot == std::string::npos || dot <= 5) return INT_MAX;
    return std::atoi(text.substr(5, dot - 5).c_str());
}

static std::vector<OverridePatchFile> findOverridePatchFiles() {
    loadConfig();
    createDirectoriesForPath(g_overrideRpfPath);

    std::vector<OverridePatchFile> patches;
    WIN32_FIND_DATAA data = {};
    const std::string pattern = joinPath(g_overrideRpfPath, "patch*.rpf");
    HANDLE find = FindFirstFileA(pattern.c_str(), &data);
    if (find == INVALID_HANDLE_VALUE) return patches;

    do {
        if ((data.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0) continue;
        if (!isPatchRpfName(data.cFileName)) continue;

        OverridePatchFile patch = {};
        patch.fileName = data.cFileName;
        patch.sourcePath = joinPath(g_overrideRpfPath, patch.fileName);
        patch.stagedPath = joinPath(g_patchStagePath, patch.fileName);
        patch.size = (static_cast<unsigned long long>(data.nFileSizeHigh) << 32) |
                     static_cast<unsigned long long>(data.nFileSizeLow);
        patches.push_back(patch);
    } while (FindNextFileA(find, &data));
    FindClose(find);

    std::sort(patches.begin(), patches.end(),
              [](const OverridePatchFile& a, const OverridePatchFile& b) {
                  const int an = patchNumberFromName(a.fileName);
                  const int bn = patchNumberFromName(b.fileName);
                  if (an != bn) return an < bn;
                  return lowerCopy(a.fileName) < lowerCopy(b.fileName);
              });
    return patches;
}

static void writeRuntimeState(const std::string& phase,
                              const std::vector<OverridePatchFile>& patches,
                              const std::string& result) {
    createParentDirs(g_statePath);

    std::ofstream file(g_statePath.c_str(), std::ios::trunc);
    if (!file) {
        writeLog("Could not write state file: %s", g_statePath.c_str());
        return;
    }

    std::time_t now = std::time(nullptr);
    Actor player = playerActor();
    Vector3 playerPos = {};
    const bool hasPlayerPos = player > 0 && actorPosition(player, &playerPos);

    file << "{\n";
    file << "  \"source\": \"CodeRED_AI_Menu\",\n";
    file << "  \"phase\": \"" << jsonEscape(phase) << "\",\n";
    file << "  \"result\": \"" << jsonEscape(result) << "\",\n";
    file << "  \"timestamp\": " << static_cast<long long>(now) << ",\n";
    file << "  \"override_rpf_dir\": \"" << jsonEscape(g_overrideRpfPath) << "\",\n";
    file << "  \"patch_stage_dir\": \"" << jsonEscape(g_patchStagePath) << "\",\n";
    file << "  \"content_override\": \"" << jsonEscape(g_contentOverrideName) << "\",\n";
    file << "  \"player_actor\": " << player << ",\n";
    file << "  \"player_side_faction\": " << g_playerSideFaction << ",\n";
    if (hasPlayerPos) {
        file << "  \"player_position\": {\"x\": " << playerPos.x
             << ", \"y\": " << playerPos.y << ", \"z\": " << playerPos.z << "},\n";
    } else {
        file << "  \"player_position\": null,\n";
    }
    file << "  \"patches\": [\n";
    for (size_t i = 0; i < patches.size(); ++i) {
        const OverridePatchFile& patch = patches[i];
        file << "    {\"name\": \"" << jsonEscape(patch.fileName)
             << "\", \"source\": \"" << jsonEscape(patch.sourcePath)
             << "\", \"staged\": \"" << jsonEscape(patch.stagedPath)
             << "\", \"size\": " << patch.size << "}";
        if (i + 1 < patches.size()) file << ",";
        file << "\n";
    }
    file << "  ]\n";
    file << "}\n";
}

static bool applyContentOverride(std::string* appliedSource,
                                 std::string* failure) {
    const std::string contentSource =
        joinPath(g_overrideRpfPath, g_contentOverrideName);
    const std::string patch0Source = joinPath(g_overrideRpfPath, "patch0.rpf");
    const std::string target = joinPath(g_patchStagePath, "content.rpf");
    const std::string backup = target + ".codered_original_backup";

    std::string source;
    if (fileExists(contentSource)) {
        source = contentSource;
    } else if (fileExists(patch0Source)) {
        const unsigned long long patchSize = fileSizeBytes(patch0Source);
        const unsigned long long targetSize = fileSizeBytes(target);
        if (patchSize >= 8ULL * 1024ULL * 1024ULL &&
            (targetSize == 0 ||
             (patchSize * 10ULL >= targetSize * 7ULL &&
              patchSize * 10ULL <= targetSize * 13ULL))) {
            source = patch0Source;
        }
    }

    if (source.empty()) return false;

    createDirectoriesForPath(g_patchStagePath);
    const bool patch0IsContent =
        lowerCopy(source) == lowerCopy(patch0Source);
    const std::string stagedPatch0 = joinPath(g_patchStagePath, "patch0.rpf");
    const unsigned long long sourceSize = fileSizeBytes(source);
    const unsigned long long targetSize = fileSizeBytes(target);
    const unsigned long long sourceTime = fileWriteTime(source);
    const unsigned long long targetTime = fileWriteTime(target);
    if (sourceSize != 0 && sourceSize == targetSize && targetTime >= sourceTime) {
        if (patch0IsContent && fileExists(stagedPatch0)) {
            if (DeleteFileA(stagedPatch0.c_str())) {
                writeLog("Removed staged patch0 because patch0 is active content override: %s",
                         stagedPatch0.c_str());
            } else {
                writeLog("Could not remove staged patch0 while patch0 is active content override: %s err=%lu",
                         stagedPatch0.c_str(), GetLastError());
            }
        }
        if (appliedSource) *appliedSource = source;
        writeLog("Content RPF override already current: %s -> %s size=%llu",
                 source.c_str(), target.c_str(), sourceSize);
        return true;
    }

    if (!fileExists(backup) && fileExists(target)) {
        if (!CopyFileA(target.c_str(), backup.c_str(), TRUE)) {
            const DWORD err = GetLastError();
            if (failure) {
                *failure = "Content RPF backup failed err " + std::to_string(err);
            }
            writeLog("Content RPF backup failed: %s -> %s err=%lu",
                     target.c_str(), backup.c_str(), err);
            return false;
        }
        writeLog("Content RPF backup created: %s", backup.c_str());
    }

    if (!CopyFileA(source.c_str(), target.c_str(), FALSE)) {
        const DWORD err = GetLastError();
        if (failure) {
            if (err == ERROR_SHARING_VIOLATION || err == ERROR_LOCK_VIOLATION) {
                *failure = "Content RPF locked by game; restart to apply override";
            } else {
                *failure = "Content RPF override failed err " + std::to_string(err);
            }
        }
        writeLog("Content RPF override failed: %s -> %s err=%lu",
                 source.c_str(), target.c_str(), err);
        return false;
    }

    if (appliedSource) *appliedSource = source;
    if (patch0IsContent && fileExists(stagedPatch0)) {
        if (DeleteFileA(stagedPatch0.c_str())) {
            writeLog("Removed staged patch0 because patch0 is active content override: %s",
                     stagedPatch0.c_str());
        } else {
            writeLog("Could not remove staged patch0 while patch0 is active content override: %s err=%lu",
                     stagedPatch0.c_str(), GetLastError());
        }
    }
    writeLog("Content RPF override applied: %s -> %s size=%llu",
             source.c_str(), target.c_str(), fileSizeBytes(source));
    return true;
}

static void reloadOverrideRpf() {
    loadConfig();
    const std::vector<OverridePatchFile> patches = findOverridePatchFiles();
    writeRuntimeState("before_override_rpf_reload", patches, "snapshot");

    std::string contentSource;
    std::string contentFailure;
    const bool appliedContent = applyContentOverride(&contentSource, &contentFailure);
    if (!contentFailure.empty()) {
        g_status = contentFailure;
        writeRuntimeState("override_rpf_reload_failed", patches, g_status);
        return;
    }

    if (patches.empty() && !appliedContent) {
        g_status = "No override RPF files in " + g_overrideRpfPath;
        writeRuntimeState("override_rpf_reload_skipped", patches, "no_patch_files");
        writeLog("Override RPF reload skipped: no content.rpf or patchN.rpf files in %s",
                 g_overrideRpfPath.c_str());
        return;
    }
    for (size_t i = 0; i < patches.size(); ++i) {
        const int expected = static_cast<int>(i);
        const int actual = patchNumberFromName(patches[i].fileName);
        if (actual != expected) {
            g_status = "Override RPF names must start at patch0.rpf and be contiguous";
            writeRuntimeState("override_rpf_reload_failed", patches, "non_contiguous_patch_names");
            writeLog("Override RPF reload failed: expected patch%d.rpf but found %s",
                     expected, patches[i].fileName.c_str());
            return;
        }
    }

    createDirectoriesForPath(g_patchStagePath);
    size_t copied = 0;
    size_t skipped = 0;
    for (const OverridePatchFile& patch : patches) {
        if (appliedContent &&
            lowerCopy(patch.sourcePath) == lowerCopy(contentSource)) {
            ++skipped;
            writeLog("Override RPF patch stage skipped because it is the active content override: %s",
                     patch.sourcePath.c_str());
            continue;
        }
        if (CopyFileA(patch.sourcePath.c_str(), patch.stagedPath.c_str(), FALSE)) {
            ++copied;
            writeLog("Override RPF staged: %s -> %s size=%llu",
                     patch.sourcePath.c_str(), patch.stagedPath.c_str(), patch.size);
        } else {
            const DWORD err = GetLastError();
            g_status = "RPF stage failed: " + patch.fileName +
                       " err " + std::to_string(err);
            writeRuntimeState("override_rpf_reload_failed", patches, g_status);
            writeLog("Override RPF stage failed: %s -> %s err=%lu",
                     patch.sourcePath.c_str(), patch.stagedPath.c_str(), err);
            return;
        }
    }

    if (appliedContent) {
        g_status = "Applied content override";
        if (copied) {
            g_status += " and staged " + std::to_string(copied) + " patch RPF(s)";
        }
        if (skipped) {
            g_status += "; skipped active content patch";
        }
        g_status += "; restart required";
    } else {
        g_status = "Staged " + std::to_string(copied) +
                   " patch RPF(s); restart required";
    }
    writeRuntimeState("after_override_rpf_reload", patches, g_status);
    writeLog("Override RPF applied: content=%s source=%s patch_copied=%zu patch_skipped=%zu; live remount not called",
             appliedContent ? "true" : "false",
             appliedContent ? contentSource.c_str() : "",
             copied, skipped);
}

static void executeSelectedAction() {
    const std::string action = selectedAction();
    writeActionPlan();

    if (action == "mp_connect_localhost_request") {
        mpConnectLocalhost();
        return;
    }

    if (!resolveNativeBridge(false)) {
        g_status = "Queued JSON; native bridge unavailable";
        writeLog("Native bridge unavailable while executing action=%s",
                 action.c_str());
        return;
    }

    if (action == "spawn_selected_npc_request") {
        spawnSelectedNpc();
    } else if (action == "side_lawman_immunity_request") {
        setPlayerFactionSide(FACTION_US_LAW, "US lawman");
    } else if (action == "side_gang_immunity_request") {
        setPlayerFactionSide(FACTION_GENERIC_CRIMINAL, "generic criminal/gang");
    } else if (action == "restore_player_faction_request") {
        restorePlayerFaction();
    } else if (action == "mp_status_probe_request") {
        mpStatusProbe();
    } else if (action == "mp_enable_multiplayer_request") {
        mpEnableMultiplayer();
    } else if (action == "mp_enter_networking_ui_request") {
        mpEnterNetworkingUi();
    } else if (action == "mp_start_core_threads_request") {
        mpStartCoreThreads();
    } else if (action == "mp_launch_freemode_request") {
        mpLaunchFreemode();
    } else if (action == "mp_launch_deathmatch_request") {
        mpLaunchDeathmatch();
    } else if (action == "mp_launch_ctf_request") {
        mpLaunchCtf();
    } else if (action == "mp_toggle_bare_world_request") {
        mpBareWorldToggle();
    } else if (action == "mp_bare_world_purge_request") {
        mpBareWorldPurgeNow();
    } else if (action == "mp_toggle_bare_world_suppression_request") {
        mpBareWorldTogglePopulationSuppression();
    } else if (action == "reload_override_rpf_request") {
        reloadOverrideRpf();
    } else if (action == "status_request") {
        pruneSpawnedActors();
        const int actorEnum = selectedActorEnum();
        g_status = "Native OK | enum " + std::to_string(actorEnum) +
                   " | spawned " + std::to_string(g_spawnedActors.size()) +
                   " | bare " + (g_mpBareWorldEnabled ? "on" : "off") +
                   " total " + std::to_string(g_mpBareWorldTotalDestroyed);
        writeLog("Status: native=ready selected=%s enum=%d spawned=%zu worldGetAllActors=%s playerSideFaction=%d bare=%d bare_seen=%d bare_protected=%d bare_destroyed_last=%d bare_destroyed_total=%d",
                 selectedNpc().c_str(), actorEnum, g_spawnedActors.size(),
                 g_worldGetAllActors ? "ready" : "missing",
                 g_playerSideFaction,
                 g_mpBareWorldEnabled ? 1 : 0,
                 g_mpBareWorldLastSeen,
                 g_mpBareWorldLastProtected,
                 g_mpBareWorldLastDestroyed,
                 g_mpBareWorldTotalDestroyed);
    } else {
        commandSpawnedActors(action);
    }
}

static void writeActionPlan() {
    createParentDirs(g_actionPlanPath);

    std::ofstream file(g_actionPlanPath.c_str(), std::ios::trunc);
    if (!file) {
        g_status = "Could not write action plan";
        return;
    }

    std::time_t now = std::time(nullptr);
    const int actorEnum = selectedActorEnum();
    const bool actorEnumResolved = actorEnum > 0;

    file << "{\n";
    file << "  \"source\": \"CodeRED_AI_Menu\",\n";
    file << "  \"action\": \"" << jsonEscape(selectedAction()) << "\",\n";
    file << "  \"model\": \"" << jsonEscape(selectedNpc()) << "\",\n";
    file << "  \"actor_enum_resolved\": " << (actorEnumResolved ? "true" : "false") << ",\n";
    if (actorEnumResolved) {
        file << "  \"actor_enum\": " << actorEnum << ",\n";
        file << "  \"actor_enum_hex\": \"" << enumHex(actorEnum) << "\",\n";
    } else {
        file << "  \"actor_enum\": null,\n";
        file << "  \"actor_enum_hex\": null,\n";
    }
    file << "  \"spawned_actor_count\": " << g_spawnedActors.size() << ",\n";
    file << "  \"player_side_faction\": " << g_playerSideFaction << ",\n";
    file << "  \"override_rpf_dir\": \"" << jsonEscape(g_overrideRpfPath) << "\",\n";
    file << "  \"patch_stage_dir\": \"" << jsonEscape(g_patchStagePath) << "\",\n";
    file << "  \"mp_connect_request_path\": \"" << jsonEscape(g_mpConnectRequestPath) << "\",\n";
    file << "  \"mp_client_status_path\": \"" << jsonEscape(g_mpClientStatusPath) << "\",\n";
    file << "  \"mp_bridge_input_path\": \"" << jsonEscape(g_mpBridgeInputPath) << "\",\n";
    file << "  \"mp_bridge_world_path\": \"" << jsonEscape(g_mpBridgeWorldPath) << "\",\n";
    file << "  \"mp_client\": \"" << jsonEscape(g_mpClientPath) << "\",\n";
    file << "  \"state_path\": \"" << jsonEscape(g_statePath) << "\",\n";
    file << "  \"status\": \"queued\",\n";
    file << "  \"timestamp\": " << static_cast<long long>(now) << "\n";
    file << "}\n";

    const std::string action = selectedAction();
    const std::string npc = selectedNpc();
    if (actorEnumResolved) {
        g_status = "Queued: " + action + " / " + npc + " enum " +
                   std::to_string(actorEnum);
        writeLog("Action plan written: action=%s model=%s enum=%d",
                 action.c_str(), npc.c_str(), actorEnum);
    } else {
        g_status = "Queued unresolved: add enum for " + npc;
        writeLog("Action plan written unresolved: action=%s model=%s",
                 action.c_str(), npc.c_str());
    }
}

static bool throttleKey() {
    DWORD now = GetTickCount();
    if (now - g_lastKeyMs < 140) return true;
    g_lastKeyMs = now;
    return false;
}

static bool isMenuNavigationKey(DWORD key) {
    return key == VK_UP || key == VK_DOWN || key == VK_LEFT || key == VK_RIGHT ||
           key == VK_HOME || key == VK_END;
}

static void onKey(DWORD key, WORD repeats, BYTE scanCode, BOOL isExtended,
                  BOOL isWithAlt, BOOL wasDownBefore, BOOL isUpNow) {
    (void)repeats;
    (void)scanCode;
    (void)isExtended;
    (void)isWithAlt;

    if (isUpNow) return;
    const bool menuNavigationKey = isMenuNavigationKey(key);
    if (wasDownBefore && key != VK_RETURN && !(g_menuOpen && menuNavigationKey)) return;

    if (g_mpLiteActive && g_mpChatOpen) {
        mpLiteHandleKey(key);
        return;
    }

    if (key == VK_F8 || key == VK_INSERT) {
        if (throttleKey()) return;
        g_menuOpen = !g_menuOpen;
        if (g_menuOpen) {
            g_dirtyRoster = true;
            g_dirtyActorMap = true;
            g_dirtyActions = true;
        }
        writeLog("Menu toggled: open=%s key=0x%08lX",
                 g_menuOpen ? "true" : "false", key);
        return;
    }

    if (g_menuOpen) {
        if (!menuNavigationKey && throttleKey()) return;

        if (key == VK_BACK || key == VK_ESCAPE) {
            g_menuOpen = false;
            return;
        }

        if (key == VK_UP) {
            if (g_dirtyActions) loadActions();
            const int count = static_cast<int>(g_actions.size());
            if (count > 0) {
                g_menuIndex--;
                if (g_menuIndex < 0) g_menuIndex = count - 1;
            }
            return;
        }

        if (key == VK_DOWN) {
            if (g_dirtyActions) loadActions();
            const int count = static_cast<int>(g_actions.size());
            if (count > 0) {
                g_menuIndex++;
                if (g_menuIndex >= count) g_menuIndex = 0;
            }
            return;
        }

        if (key == VK_LEFT) {
            ensureDefaultRoster();
            const int count = static_cast<int>(g_roster.size());
            if (count > 0) {
                const bool fast = (GetAsyncKeyState(VK_SHIFT) & 0x8000) != 0;
                g_npcIndex -= fast ? 10 : 1;
                while (g_npcIndex < 0) g_npcIndex += count;
            }
            return;
        }

        if (key == VK_RIGHT) {
            ensureDefaultRoster();
            const int count = static_cast<int>(g_roster.size());
            if (count > 0) {
                const bool fast = (GetAsyncKeyState(VK_SHIFT) & 0x8000) != 0;
                g_npcIndex += fast ? 10 : 1;
                if (g_npcIndex >= count) g_npcIndex %= count;
            }
            return;
        }

        if (key == VK_HOME) {
            g_npcIndex = 0;
            return;
        }

        if (key == VK_END) {
            ensureDefaultRoster();
            if (!g_roster.empty()) {
                g_npcIndex = static_cast<int>(g_roster.size()) - 1;
            }
            return;
        }

        if (key == VK_RETURN) {
            executeSelectedAction();
            return;
        }

        if (key == VK_F5) {
            g_configLoaded = false;
            g_dirtyRoster = true;
            g_dirtyActorMap = true;
            g_dirtyActions = true;
            g_status = "Reload requested";
            writeLog("Manual reload requested");
            return;
        }
        return;
    }

    if (mpLiteHandleKey(key)) {
        return;
    }
}

static void drawLine(float x, float y, const std::string& text, int r = 235, int g = 235, int b = 235, float size = 0.018f) {
    drawTextSafe(x, y, text.c_str(), r, g, b, 255, FONT_REDEMPTION, size, JUSTIFY_LEFT);
}

static int crMinInt(int a, int b) { return a < b ? a : b; }
static int crMaxInt(int a, int b) { return a > b ? a : b; }
static float crMinFloat(float a, float b) { return a < b ? a : b; }
static float crMaxFloat(float a, float b) { return a > b ? a : b; }

static int listStartFor(int selected, int total, int visible) {
    if (total <= visible || visible <= 0) return 0;
    int start = selected - visible / 2;
    if (start < 0) start = 0;
    if (start > total - visible) start = total - visible;
    return start;
}

static void drawMenu() {
    if (!g_menuOpen) return;
    if (g_dirtyRoster) loadRoster();
    if (g_dirtyActorMap) loadActorEnumMap();
    if (g_dirtyActions) loadActions();
    pollMpClientStatus();

    const int totalActions = static_cast<int>(g_actions.size());
    const int totalRoster = static_cast<int>(g_roster.size());
    const int visibleActions = crMinInt(crMaxInt(totalActions, 1), 7);
    const int visibleRoster = crMinInt(crMaxInt(totalRoster, 1), 9);
    const int visibleRows = crMaxInt(visibleActions, visibleRoster);

    const float rowH = 0.026f;
    const float headerH = 0.120f;
    const float footerH = 0.070f;
    const float panelW = 0.520f;
    const float panelH = crMinFloat(0.780f, crMaxFloat(0.320f, headerH + footerH + rowH * static_cast<float>(visibleRows + 2)));
    const float x = 0.500f;
    const float y = 0.500f;
    const float left = x - panelW * 0.5f;
    const float top = y - panelH * 0.5f;

    drawRectSafe(x, y, panelW, panelH, 8, 8, 10, 205, 0.015f);
    drawRectSafe(x, top + 0.036f, panelW, 0.072f, 120, 0, 0, 220, 0.015f);
    drawRectSafe(x, top + panelH - 0.030f, panelW, 0.060f, 30, 0, 0, 190, 0.010f);

    drawTextSafe(left + 0.020f, top + 0.017f, "CodeRED AI Menu", 255, 235, 235, 255, FONT_REDEMPTION, 0.030f, JUSTIFY_LEFT);

    const std::string npc = selectedNpc();
    const int actorEnum = selectedActorEnum();
    std::string npcLine = "NPC: " + npc;
    std::string enumLine = "ENUM: " + std::to_string(actorEnum) + " / " + enumHex(actorEnum);
    drawTextSafe(left + 0.020f, top + 0.060f, npcLine.c_str(), 245, 245, 245, 245, FONT_REDEMPTION, 0.020f, JUSTIFY_LEFT);
    drawTextSafe(left + 0.020f, top + 0.085f, enumLine.c_str(), actorEnum > 0 ? 170 : 255, actorEnum > 0 ? 230 : 80, actorEnum > 0 ? 170 : 80, 245, FONT_REDEMPTION, 0.018f, JUSTIFY_LEFT);

    const float listTop = top + 0.130f;
    const float actionX = left + 0.025f;
    const float rosterX = left + panelW * 0.510f;
    const float colW = panelW * 0.455f;

    drawTextSafe(actionX, listTop - 0.030f, "Actions", 255, 80, 80, 255, FONT_REDEMPTION, 0.020f, JUSTIFY_LEFT);
    drawTextSafe(rosterX, listTop - 0.030f, "Roster", 255, 80, 80, 255, FONT_REDEMPTION, 0.020f, JUSTIFY_LEFT);

    const int actionStart = listStartFor(g_menuIndex, totalActions, visibleActions);
    for (int i = 0; i < visibleActions && actionStart + i < totalActions; ++i) {
        const int index = actionStart + i;
        const bool selected = index == g_menuIndex;
        const float rowY = listTop + rowH * static_cast<float>(i);
        if (selected) drawRectSafe(actionX + colW * 0.5f, rowY + 0.010f, colW, rowH, 95, 0, 0, 185, 0.006f);
        std::string label = (selected ? "> " : "  ") + displayAction(g_actions[index]);
        drawTextSafe(actionX + 0.005f, rowY, label.c_str(), selected ? 255 : 220, selected ? 245 : 210, selected ? 210 : 210, 255, FONT_REDEMPTION, 0.017f, JUSTIFY_LEFT);
    }

    const int rosterStart = listStartFor(g_npcIndex, totalRoster, visibleRoster);
    for (int i = 0; i < visibleRoster && rosterStart + i < totalRoster; ++i) {
        const int index = rosterStart + i;
        const bool selected = index == g_npcIndex;
        const float rowY = listTop + rowH * static_cast<float>(i);
        if (selected) drawRectSafe(rosterX + colW * 0.5f, rowY + 0.010f, colW, rowH, 70, 0, 0, 175, 0.006f);
        std::string label = (selected ? "> " : "  ") + displayRosterName(g_roster[index]);
        if (label.size() > 44) label = label.substr(0, 41) + "...";
        drawTextSafe(rosterX + 0.005f, rowY, label.c_str(), selected ? 255 : 220, selected ? 245 : 210, selected ? 210 : 210, 255, FONT_REDEMPTION, 0.017f, JUSTIFY_LEFT);
    }

    if (totalActions > visibleActions) {
        const int actionEnd = crMinInt(actionStart + visibleActions, totalActions);
        std::string hint = "actions " + std::to_string(actionStart + 1) + "-" + std::to_string(actionEnd) + " / " + std::to_string(totalActions);
        drawTextSafe(actionX + 0.005f, top + panelH - 0.050f, hint.c_str(), 190, 190, 190, 230, FONT_REDEMPTION, 0.015f, JUSTIFY_LEFT);
    }
    if (totalRoster > visibleRoster) {
        const int rosterEnd = crMinInt(rosterStart + visibleRoster, totalRoster);
        std::string hint = "roster " + std::to_string(rosterStart + 1) + "-" + std::to_string(rosterEnd) + " / " + std::to_string(totalRoster);
        drawTextSafe(rosterX + 0.005f, top + panelH - 0.050f, hint.c_str(), 190, 190, 190, 230, FONT_REDEMPTION, 0.015f, JUSTIFY_LEFT);
    }

    std::string footer = "F8 close | UP/DOWN action | LEFT/RIGHT roster | F5 reload files | ENTER run";
    drawTextSafe(left + 0.020f, top + panelH - 0.026f, footer.c_str(), 235, 235, 235, 235, FONT_REDEMPTION, 0.015f, JUSTIFY_LEFT);
    if (!g_status.empty()) {
        drawTextSafe(left + 0.020f, top + panelH - 0.005f, g_status.c_str(), 255, 140, 140, 235, FONT_REDEMPTION, 0.014f, JUSTIFY_LEFT);
    }
}
// CodeRED compact scrolling menu layout pass v2 no-std-minmax



static void mainLoop() {
    while (true) {
        mpLiteTick();
        mpLiteDrawOverlay();
        drawMenu();
        waitFrame(0);
    }
}

static DWORD WINAPI registrationThread(LPVOID param) {
    HMODULE module = reinterpret_cast<HMODULE>(param);
    writeLog("Registration worker started");
    loadConfig();

    const ULONGLONG deadline = GetTickCount64() + 30000;
    bool loggedDllMissing = false;
    bool loggedDllFound = false;
    bool loggedMissingExports = false;

    while (!InterlockedCompareExchange(&g_stopRequested, 0, 0) &&
           GetTickCount64() <= deadline) {
        const bool resolved = resolveScriptHook(!loggedMissingExports);

        if (!g_scriptHook) {
            if (!loggedDllMissing) {
                writeLog("ScriptHookRDR.dll not found yet");
                loggedDllMissing = true;
            }
        } else if (!loggedDllFound) {
            writeLog("ScriptHookRDR.dll found");
            loggedDllFound = true;
        }

        if (g_scriptHook && !resolved && !loggedMissingExports) {
            loggedMissingExports = true;
        }

        if (resolved) {
            if (resolveNativeBridge(true)) {
                writeLog("Native bridge ready");
            } else {
                writeLog("Native bridge unavailable; menu will still write action plans");
            }
            g_scriptRegister(module, codered::mainLoop);
            g_keyboardHandlerRegister(codered::onKey);
            InterlockedExchange(&g_registered, 1);
            writeLog("Registration succeeded");
            return 0;
        }

        Sleep(500);
    }

    if (InterlockedCompareExchange(&g_stopRequested, 0, 0)) {
        writeLog("Registration worker stopped before registration");
    } else {
        resolveScriptHook(true);
        writeLog("Registration failed: ScriptHookRDR exports were not ready within 30 seconds");
    }
    return 1;
}

} // namespace codered

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(module);
        codered::g_module = module;
        InterlockedExchange(&codered::g_stopRequested, 0);
        codered::writeLog("ASI attached");
        codered::loadConfig();
        {
            std::string source;
            std::string failure;
            if (codered::applyContentOverride(&source, &failure)) {
                codered::writeLog("Startup content override check complete: %s",
                                  source.c_str());
            } else if (!failure.empty()) {
                codered::writeLog("Startup content override check failed: %s",
                                  failure.c_str());
            }
        }
        HANDLE thread = CreateThread(nullptr, 0, codered::registrationThread,
                                     module, 0, nullptr);
        if (thread) {
            CloseHandle(thread);
        } else {
            codered::writeLog("Registration worker creation failed: %lu",
                              GetLastError());
        }
    } else if (reason == DLL_PROCESS_DETACH) {
        InterlockedExchange(&codered::g_stopRequested, 1);
        codered::writeLog("ASI detach requested");
        codered::mpLiteUninstallInputFilter();
        if (InterlockedCompareExchange(&codered::g_registered, 0, 0) &&
            codered::g_keyboardHandlerUnregister) {
            codered::g_keyboardHandlerUnregister(codered::onKey);
            codered::writeLog("Keyboard handler unregistered");
        }
        if (InterlockedCompareExchange(&codered::g_registered, 0, 0) &&
            codered::g_scriptUnregister) {
            codered::g_scriptUnregister(module);
            codered::writeLog("Script unregistered");
        }
        InterlockedExchange(&codered::g_registered, 0);
        codered::writeLog("ASI detached");
    }
    return TRUE;
}
