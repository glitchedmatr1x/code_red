// Code RED Peer Companion Link Pass 1
//
// Safe single-player companion command bridge. This ASI does not touch
// content.rpf, RDR.exe, official multiplayer, GameSpy, WSC, or SCXML.

#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>
#include <type_traits>

namespace codered_peer_companion {

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

using Actor = int;
using Layout = int;
using Squad = int;

struct Vector2 {
    float x;
    float y;
};

struct Vector3 {
    float x;
    float y;
    float z;
};

struct Config {
    bool peerLinkEnabled = false;
    bool peerControlEnabled = false;
    bool aiCompanionEnabled = true;
    bool spawnOnStartup = false;
    bool companionSpawnEnabled = true;
    bool companionSyncEnabled = false;
    bool externalCommandEnabled = false;
    bool heartbeatEnabled = true;
    bool debugLogging = true;
    bool overlayEnabled = true;
    bool taskNativesEnabled = false;
    bool postSpawnPositionNativeEnabled = false;
    bool teleportCommandEnabled = false;
    bool spawnUseXZGroundPlane = true;
    bool giveWeaponEnabled = true;
    bool clearWeaponsEnabled = true;
    bool companionControllerEnabled = true;
    bool spawn638Enabled = true;
    bool streamingRequestEnabled = true;
    bool adoptTargetActorEnabled = false;
    bool nearestScanEnabled = false;
    bool setCompanionFactionEnabled = true;
    bool setCompanionFlagEnabled = false;
    bool taskPriorityEnabled = false;
    bool squadRouteEnabled = false;
    bool fallbackFollowEnabled = true;
    bool allowAnyTarget = false;
    bool debugAdoptOnly = false;
    DWORD startupDelayMs = 15000;
    DWORD commandPollMs = 200;
    DWORD heartbeatMs = 5000;
    int companionActorEnum = 111;
    int spawnActorEnum = 638;
    int adoptActorEnum = 638;
    int companionFaction = 20;
    int companionFollowPriority = 1;
    int friendlyFaction = 0;
    int neutralFaction = 0;
    int hostileFaction = 0;
    int basicWeaponEnum = 4;
    float basicWeaponAmmo = 60.0f;
    float spawnDistance = 2.5f;
    float spawnZOffset = 0.35f;
    float adoptRadius = 8.0f;
    std::string logPath = "logs\\codered_peer_companion.log";
    std::string statusPath = "data\\codered\\link\\host_status.json";
    std::string commandInboxPath = "data\\codered\\link\\peer_command_inbox.json";
    std::string commandArchivePath = "data\\codered\\link\\peer_command_last_consumed.json";
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
static CRITICAL_SECTION g_logLock;
static bool g_logLockReady = false;
static Config g_config;
static std::string g_rootDir;
static bool g_configLoaded = false;
static bool g_nativeReady = false;
static Layout g_layout = 0;
static Squad g_squad = 0;
static Actor g_companion = 0;
static Vector3 g_companionPos = {};
static bool g_companionOwnedByCode = false;
static bool g_companionAdopted638 = false;
static int g_spawnCounter = 0;
static bool g_aiMode = true;
static bool g_peerMode = false;
static bool g_peerConnected = false;
static std::string g_lastCommandId;
static std::string g_lastCommand = "none";
static std::string g_lastError;
static std::string g_overlayLine = "CodeRED Peer Companion: loading";
static DWORD g_overlayFlashUntil = 0;
static ULONGLONG g_startTick = 0;
static DWORD g_lastCommandPollTick = 0;
static DWORD g_lastHeartbeatTick = 0;
static DWORD g_lastStatusTick = 0;
static DWORD g_lastHotkeyTick[256] = {};

static constexpr float PI = 3.14159265358979323846f;

static std::string trim(const std::string& value) {
    size_t start = 0;
    while (start < value.size() && std::isspace(static_cast<unsigned char>(value[start]))) ++start;
    size_t end = value.size();
    while (end > start && std::isspace(static_cast<unsigned char>(value[end - 1]))) --end;
    return value.substr(start, end - start);
}

static std::string lower(std::string value) {
    std::transform(value.begin(), value.end(), value.begin(),
                   [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    return value;
}

static std::string replaceSlashes(std::string value) {
    std::replace(value.begin(), value.end(), '/', '\\');
    return value;
}

static std::string moduleDir() {
    char path[MAX_PATH] = {};
    DWORD len = GetModuleFileNameA(g_module, path, MAX_PATH);
    if (len == 0 || len >= MAX_PATH) len = GetModuleFileNameA(nullptr, path, MAX_PATH);
    std::string result(path);
    size_t slash = result.find_last_of("\\/");
    return slash == std::string::npos ? "." : result.substr(0, slash);
}

static bool isAbsolutePath(const std::string& path) {
    return (path.size() >= 3 && std::isalpha(static_cast<unsigned char>(path[0])) &&
            path[1] == ':' && (path[2] == '\\' || path[2] == '/')) ||
           (path.size() >= 2 && path[0] == '\\' && path[1] == '\\');
}

static std::string pathJoin(const std::string& left, const std::string& right) {
    if (right.empty()) return left;
    if (isAbsolutePath(right)) return replaceSlashes(right);
    if (left.empty()) return replaceSlashes(right);
    char last = left[left.size() - 1];
    if (last == '\\' || last == '/') return replaceSlashes(left + right);
    return replaceSlashes(left + "\\" + right);
}

static std::string rootPath(const std::string& path) {
    return pathJoin(g_rootDir, path);
}

static void ensureDir(const std::string& dir) {
    if (dir.empty()) return;
    std::string normalized = replaceSlashes(dir);
    std::string partial;
    size_t start = 0;
    if (normalized.size() >= 3 && normalized[1] == ':') {
        partial = normalized.substr(0, 3);
        start = 3;
    }
    for (size_t i = start; i <= normalized.size(); ++i) {
        if (i == normalized.size() || normalized[i] == '\\') {
            std::string current = partial.empty()
                ? normalized.substr(0, i)
                : partial + normalized.substr(start - 1, i - start + 1);
            if (!current.empty() && current[current.size() - 1] != ':') {
                CreateDirectoryA(current.c_str(), nullptr);
            }
        }
    }
}

static void ensureParentDir(const std::string& path) {
    size_t slash = path.find_last_of("\\/");
    if (slash != std::string::npos) ensureDir(path.substr(0, slash));
}

static bool readText(const std::string& path, std::string* out) {
    std::ifstream file(path, std::ios::binary);
    if (!file) return false;
    std::ostringstream buffer;
    buffer << file.rdbuf();
    *out = buffer.str();
    return true;
}

static bool writeText(const std::string& path, const std::string& text) {
    ensureParentDir(path);
    std::ofstream file(path, std::ios::binary | std::ios::trunc);
    if (!file) return false;
    file << text;
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
            default:
                if (static_cast<unsigned char>(c) < 0x20) out << "?";
                else out << c;
                break;
        }
    }
    return out.str();
}

static long long nowMs() {
    FILETIME ft = {};
    GetSystemTimeAsFileTime(&ft);
    ULARGE_INTEGER uli = {};
    uli.LowPart = ft.dwLowDateTime;
    uli.HighPart = ft.dwHighDateTime;
    return static_cast<long long>((uli.QuadPart - 116444736000000000ULL) / 10000ULL);
}

static void logLine(const std::string& line) {
    if (!g_logLockReady) return;
    EnterCriticalSection(&g_logLock);
    const std::string path = rootPath(g_config.logPath);
    ensureParentDir(path);
    std::ofstream file(path, std::ios::binary | std::ios::app);
    if (file) file << nowMs() << " " << line << "\n";
    LeaveCriticalSection(&g_logLock);
}

static void logEnter(const char* stage) {
    if (g_config.debugLogging) logLine(std::string("ENTER ") + stage);
}

static void logExit(const char* stage, const char* result = "OK") {
    if (g_config.debugLogging) logLine(std::string("EXIT ") + stage + " " + result);
}

static void setOverlay(const std::string& line, DWORD flashMs = 3500) {
    g_overlayLine = line;
    g_overlayFlashUntil = GetTickCount() + flashMs;
}

static bool parseBool(const std::string& value, bool fallback) {
    std::string v = lower(trim(value));
    if (v == "1" || v == "true" || v == "yes" || v == "on") return true;
    if (v == "0" || v == "false" || v == "no" || v == "off") return false;
    return fallback;
}

static void loadConfig() {
    if (g_configLoaded) return;
    g_configLoaded = true;
    g_rootDir = moduleDir();
    ensureDir(rootPath("logs"));
    ensureDir(rootPath("data\\codered\\link"));

    const std::string cfgPath = rootPath("data\\codered\\peer_companion.ini");
    std::string text;
    if (!readText(cfgPath, &text)) {
        logLine("load_config defaulted reason=missing_ini path=" + cfgPath);
        return;
    }
    std::istringstream lines(text);
    std::string line;
    while (std::getline(lines, line)) {
        line = trim(line);
        if (line.empty() || line[0] == '#' || line[0] == ';' || line[0] == '[') continue;
        size_t eq = line.find('=');
        if (eq == std::string::npos) continue;
        std::string key = trim(line.substr(0, eq));
        std::string value = trim(line.substr(eq + 1));
        if (key == "peer_link_enabled") g_config.peerLinkEnabled = parseBool(value, g_config.peerLinkEnabled);
        else if (key == "peer_control_enabled") g_config.peerControlEnabled = parseBool(value, g_config.peerControlEnabled);
        else if (key == "ai_companion_enabled") g_config.aiCompanionEnabled = parseBool(value, g_config.aiCompanionEnabled);
        else if (key == "spawn_on_startup") g_config.spawnOnStartup = parseBool(value, g_config.spawnOnStartup);
        else if (key == "companion_spawn_enabled") g_config.companionSpawnEnabled = parseBool(value, g_config.companionSpawnEnabled);
        else if (key == "companion_sync_enabled") g_config.companionSyncEnabled = parseBool(value, g_config.companionSyncEnabled);
        else if (key == "external_command_enabled") g_config.externalCommandEnabled = parseBool(value, g_config.externalCommandEnabled);
        else if (key == "heartbeat_enabled") g_config.heartbeatEnabled = parseBool(value, g_config.heartbeatEnabled);
        else if (key == "debug_logging") g_config.debugLogging = parseBool(value, g_config.debugLogging);
        else if (key == "overlay_enabled") g_config.overlayEnabled = parseBool(value, g_config.overlayEnabled);
        else if (key == "task_natives_enabled") g_config.taskNativesEnabled = parseBool(value, g_config.taskNativesEnabled);
        else if (key == "post_spawn_position_native_enabled") g_config.postSpawnPositionNativeEnabled = parseBool(value, g_config.postSpawnPositionNativeEnabled);
        else if (key == "teleport_command_enabled") g_config.teleportCommandEnabled = parseBool(value, g_config.teleportCommandEnabled);
        else if (key == "spawn_use_xz_ground_plane") g_config.spawnUseXZGroundPlane = parseBool(value, g_config.spawnUseXZGroundPlane);
        else if (key == "give_weapon_enabled") g_config.giveWeaponEnabled = parseBool(value, g_config.giveWeaponEnabled);
        else if (key == "clear_weapons_enabled") g_config.clearWeaponsEnabled = parseBool(value, g_config.clearWeaponsEnabled);
        else if (key == "companion_controller_enabled") g_config.companionControllerEnabled = parseBool(value, g_config.companionControllerEnabled);
        else if (key == "enable_spawn_638") g_config.spawn638Enabled = parseBool(value, g_config.spawn638Enabled);
        else if (key == "enable_streaming_request") g_config.streamingRequestEnabled = parseBool(value, g_config.streamingRequestEnabled);
        else if (key == "adopt_target_actor_enabled") g_config.adoptTargetActorEnabled = parseBool(value, g_config.adoptTargetActorEnabled);
        else if (key == "enable_target_adopt") g_config.adoptTargetActorEnabled = parseBool(value, g_config.adoptTargetActorEnabled);
        else if (key == "enable_nearest_scan") g_config.nearestScanEnabled = parseBool(value, g_config.nearestScanEnabled);
        else if (key == "set_companion_faction_enabled") g_config.setCompanionFactionEnabled = parseBool(value, g_config.setCompanionFactionEnabled);
        else if (key == "set_companion_flag_enabled") g_config.setCompanionFlagEnabled = parseBool(value, g_config.setCompanionFlagEnabled);
        else if (key == "task_priority_enabled") g_config.taskPriorityEnabled = parseBool(value, g_config.taskPriorityEnabled);
        else if (key == "squad_route_enabled") g_config.squadRouteEnabled = parseBool(value, g_config.squadRouteEnabled);
        else if (key == "fallback_follow_enabled") g_config.fallbackFollowEnabled = parseBool(value, g_config.fallbackFollowEnabled);
        else if (key == "enable_set_faction") g_config.setCompanionFactionEnabled = parseBool(value, g_config.setCompanionFactionEnabled);
        else if (key == "enable_set_companion") g_config.setCompanionFlagEnabled = parseBool(value, g_config.setCompanionFlagEnabled);
        else if (key == "enable_task_follow") g_config.fallbackFollowEnabled = parseBool(value, g_config.fallbackFollowEnabled);
        else if (key == "enable_task_priority") g_config.taskPriorityEnabled = parseBool(value, g_config.taskPriorityEnabled);
        else if (key == "enable_squad_route") g_config.squadRouteEnabled = parseBool(value, g_config.squadRouteEnabled);
        else if (key == "allow_any_target") g_config.allowAnyTarget = parseBool(value, g_config.allowAnyTarget);
        else if (key == "debug_adopt_only") g_config.debugAdoptOnly = parseBool(value, g_config.debugAdoptOnly);
        else if (key == "startup_delay_ms") g_config.startupDelayMs = static_cast<DWORD>(std::max(0, std::atoi(value.c_str())));
        else if (key == "command_poll_ms") g_config.commandPollMs = static_cast<DWORD>(std::max(100, std::atoi(value.c_str())));
        else if (key == "heartbeat_ms") g_config.heartbeatMs = static_cast<DWORD>(std::max(1000, std::atoi(value.c_str())));
        else if (key == "companion_actor_enum") g_config.companionActorEnum = std::atoi(value.c_str());
        else if (key == "spawn_actor_enum") {
            g_config.spawnActorEnum = std::atoi(value.c_str());
            g_config.companionActorEnum = g_config.spawnActorEnum;
        }
        else if (key == "adopt_actor_enum") g_config.adoptActorEnum = std::atoi(value.c_str());
        else if (key == "companion_faction") g_config.companionFaction = std::atoi(value.c_str());
        else if (key == "companion_follow_priority") g_config.companionFollowPriority = std::atoi(value.c_str());
        else if (key == "friendly_faction") g_config.friendlyFaction = std::atoi(value.c_str());
        else if (key == "neutral_faction") g_config.neutralFaction = std::atoi(value.c_str());
        else if (key == "hostile_faction") g_config.hostileFaction = std::atoi(value.c_str());
        else if (key == "basic_weapon_enum") g_config.basicWeaponEnum = std::atoi(value.c_str());
        else if (key == "basic_weapon_ammo") g_config.basicWeaponAmmo = static_cast<float>(std::atof(value.c_str()));
        else if (key == "spawn_distance") g_config.spawnDistance = static_cast<float>(std::max(1.0, std::atof(value.c_str())));
        else if (key == "spawn_z_offset") g_config.spawnZOffset = static_cast<float>(std::atof(value.c_str()));
        else if (key == "adopt_radius") g_config.adoptRadius = static_cast<float>(std::max(1.0, std::atof(value.c_str())));
        else if (key == "log_path") g_config.logPath = value;
        else if (key == "status_path") g_config.statusPath = value;
        else if (key == "command_inbox_path") g_config.commandInboxPath = value;
        else if (key == "command_archive_path") g_config.commandArchivePath = value;
    }
    g_aiMode = g_config.aiCompanionEnabled;
    g_peerMode = g_config.peerControlEnabled;
    logLine("load_config path=" + cfgPath);
}

static FARPROC resolveExport(const char* plain, const char* decorated) {
    if (!g_scriptHook) return nullptr;
    FARPROC proc = GetProcAddress(g_scriptHook, plain);
    if (!proc && decorated) proc = GetProcAddress(g_scriptHook, decorated);
    return proc;
}

static bool resolveScriptHook() {
    if (!g_scriptHook) {
        g_scriptHook = GetModuleHandleA("ScriptHookRDR.dll");
        if (!g_scriptHook) g_scriptHook = LoadLibraryA("ScriptHookRDR.dll");
    }
    if (!g_scriptHook) {
        g_lastError = "ScriptHookRDR.dll not found";
        return false;
    }
    g_scriptRegister = reinterpret_cast<ScriptRegisterFn>(
        resolveExport("scriptRegister", "?scriptRegister@@YAXPEAUHINSTANCE__@@P6AXXZ@Z"));
    g_scriptUnregister = reinterpret_cast<ScriptUnregisterFn>(
        resolveExport("scriptUnregister", "?scriptUnregister@@YAXPEAUHINSTANCE__@@@Z"));
    g_keyboardRegister = reinterpret_cast<KeyboardHandlerRegisterFn>(
        resolveExport("keyboardHandlerRegister", "?keyboardHandlerRegister@@YAXP6AXKGEHHHH@Z@Z"));
    g_keyboardUnregister = reinterpret_cast<KeyboardHandlerUnregisterFn>(
        resolveExport("keyboardHandlerUnregister", "?keyboardHandlerUnregister@@YAXP6AXKGEHHHH@Z@Z"));
    g_scriptWait = reinterpret_cast<ScriptWaitFn>(
        resolveExport("scriptWait", "?scriptWait@@YAXK@Z"));
    g_nativeInit = reinterpret_cast<NativeInitFn>(
        resolveExport("nativeInit", "?nativeInit@@YAX_K@Z"));
    g_nativePush64 = reinterpret_cast<NativePush64Fn>(
        resolveExport("nativePush64", "?nativePush64@@YAX_K@Z"));
    g_nativeCall = reinterpret_cast<NativeCallFn>(
        resolveExport("nativeCall", "?nativeCall@@YAPEA_KXZ"));
    g_drawText = reinterpret_cast<DrawTextFn>(
        resolveExport("drawText", "?drawText@@YAXMMPEBDHHHHHMH@Z"));

    g_nativeReady = g_scriptRegister && g_scriptUnregister && g_keyboardRegister &&
                    g_keyboardUnregister && g_scriptWait && g_nativeInit &&
                    g_nativePush64 && g_nativeCall;
    if (!g_nativeReady) g_lastError = "ScriptHookRDR exports missing";
    return g_nativeReady;
}

template <typename T>
static void nativePush(T value) {
    static_assert(sizeof(T) <= sizeof(unsigned long long), "native argument must fit in 64 bits");
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

static void waitFrame(DWORD ms) {
    if (g_scriptWait) g_scriptWait(ms);
    else Sleep(ms);
}

static bool actorValid(Actor actor) {
    return g_nativeReady && actor > 0 && nativeInvoke<BOOL>(0xBA6C3E92ULL, actor) != 0;
}

static bool actorAlive(Actor actor) {
    return actorValid(actor) && nativeInvoke<BOOL>(0x2F232639ULL, actor) != 0;
}

static bool actorPosition(Actor actor, Vector3* out) {
    if (!actorValid(actor) || !out) return false;
    nativeInvoke<void>(0x99BD9D6FULL, actor, out);
    return true;
}

static int actorEnum(Actor actor) {
    if (!actorValid(actor)) return -1;
    return nativeInvoke<int>(0x0B28E9ECULL, actor);
}

static int actorFaction(Actor actor) {
    if (!actorValid(actor)) return -1;
    return nativeInvoke<int>(0x52E2A611ULL, actor);
}

static float distance3(const Vector3& a, const Vector3& b) {
    const float dx = a.x - b.x;
    const float dy = a.y - b.y;
    const float dz = a.z - b.z;
    return std::sqrt(dx * dx + dy * dy + dz * dz);
}

static bool nativeNoThrowGetTargetActor(Actor* out, DWORD* exceptionCode) {
    if (out) *out = 0;
    if (exceptionCode) *exceptionCode = 0;
    Actor target = 0;
    DWORD code = 0;
    __try {
        target = nativeInvoke<Actor>(0x0EF7427BULL);
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        code = GetExceptionCode();
    }
    if (exceptionCode) *exceptionCode = code;
    if (code != 0) return false;
    if (out) *out = target;
    return true;
}

static bool nativeNoThrowVoidActor(unsigned long long hash, Actor actor, DWORD* exceptionCode) {
    if (exceptionCode) *exceptionCode = 0;
    DWORD code = 0;
    __try {
        nativeInvoke<void>(hash, actor);
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        code = GetExceptionCode();
    }
    if (exceptionCode) *exceptionCode = code;
    return code == 0;
}

static bool nativeNoThrowVoidActorInt(unsigned long long hash, Actor actor, int value, DWORD* exceptionCode) {
    if (exceptionCode) *exceptionCode = 0;
    DWORD code = 0;
    __try {
        nativeInvoke<void>(hash, actor, value);
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        code = GetExceptionCode();
    }
    if (exceptionCode) *exceptionCode = code;
    return code == 0;
}

static bool nativeNoThrowVoidActorBool(unsigned long long hash, Actor actor, BOOL value, DWORD* exceptionCode) {
    if (exceptionCode) *exceptionCode = 0;
    DWORD code = 0;
    __try {
        nativeInvoke<void>(hash, actor, value);
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        code = GetExceptionCode();
    }
    if (exceptionCode) *exceptionCode = code;
    return code == 0;
}

static bool nativeNoThrowTaskFollow(Actor actor, Actor followActor, DWORD* exceptionCode) {
    if (exceptionCode) *exceptionCode = 0;
    DWORD code = 0;
    __try {
        nativeInvoke<void>(0x12F0911AULL, actor, followActor);
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        code = GetExceptionCode();
    }
    if (exceptionCode) *exceptionCode = code;
    return code == 0;
}

static bool nativeNoThrowStreamingRequestActor(int actorEnum, DWORD* exceptionCode) {
    if (exceptionCode) *exceptionCode = 0;
    DWORD code = 0;
    __try {
        nativeInvoke<void>(0xB0A79FEEULL, actorEnum, TRUE, FALSE);
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        code = GetExceptionCode();
    }
    if (exceptionCode) *exceptionCode = code;
    return code == 0;
}

static bool nativeNoThrowStreamingIsActorLoaded(int actorEnum, BOOL* loaded, DWORD* exceptionCode) {
    if (loaded) *loaded = FALSE;
    if (exceptionCode) *exceptionCode = 0;
    DWORD code = 0;
    BOOL result = FALSE;
    __try {
        result = nativeInvoke<BOOL>(0x7DF72579ULL, actorEnum, 0);
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        code = GetExceptionCode();
    }
    if (exceptionCode) *exceptionCode = code;
    if (code != 0) return false;
    if (loaded) *loaded = result;
    return true;
}

static bool nativeNoThrowStreamingEvictActor(int actorEnum, DWORD* exceptionCode) {
    if (exceptionCode) *exceptionCode = 0;
    DWORD code = 0;
    __try {
        nativeInvoke<void>(0x6661CF89ULL, actorEnum, 0);
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        code = GetExceptionCode();
    }
    if (exceptionCode) *exceptionCode = code;
    return code == 0;
}

static bool nativeNoThrowCreateActorInLayout(Layout layout, const char* name, int actorEnum,
                                             Vector2 spawnPlane, float spawnHeight,
                                             Vector2 orientPlane, float heading,
                                             Actor* out, DWORD* exceptionCode) {
    if (out) *out = 0;
    if (exceptionCode) *exceptionCode = 0;
    DWORD code = 0;
    Actor actor = 0;
    __try {
        actor = nativeInvoke<Actor>(0x8D67F397ULL, layout, name, actorEnum,
                                    spawnPlane, spawnHeight, orientPlane, heading);
    } __except(EXCEPTION_EXECUTE_HANDLER) {
        code = GetExceptionCode();
    }
    if (exceptionCode) *exceptionCode = code;
    if (code != 0) return false;
    if (out) *out = actor;
    return true;
}

static bool safeGetTargetActor(Actor* out) {
    if (!out) return false;
    *out = 0;
    logEnter("stage_a_get_target_actor");
    if (!g_config.adoptTargetActorEnabled) {
        logExit("stage_a_get_target_actor", "SKIPPED adopt_target_actor_enabled=false");
        return false;
    }
    logLine("stage_a target native call reached GET_TARGET_ACTOR hash=0x0EF7427B");
    DWORD exceptionCode = 0;
    Actor target = 0;
    nativeNoThrowGetTargetActor(&target, &exceptionCode);
    if (exceptionCode != 0) {
        std::ostringstream line;
        line << "stage_a_get_target_actor exception=0x" << std::hex << exceptionCode;
        logLine(line.str());
        logExit("stage_a_get_target_actor", "FAILED reason=native_exception");
        return false;
    }
    *out = target;
    logLine("stage_a target_actor_handle=" + std::to_string(target));
    if (!actorValid(target)) {
        logLine("[PeerCompanion] F8 adopt failed: no valid targeted actor.");
        logExit("stage_a_get_target_actor", "FAILED reason=invalid_target_actor");
        return false;
    }
    logExit("stage_a_get_target_actor");
    return true;
}

static bool safeClearTask(Actor actor, const char* stage) {
    logEnter(stage);
    if (!actorValid(actor)) {
        logExit(stage, "FAILED reason=invalid_actor");
        return false;
    }
    DWORD exceptionCode = 0;
    nativeNoThrowVoidActor(0x16876A25ULL, actor, &exceptionCode);
    if (exceptionCode != 0) {
        std::ostringstream line;
        line << stage << " exception=0x" << std::hex << exceptionCode;
        logLine(line.str());
        logExit(stage, "FAILED reason=native_exception");
        return false;
    }
    logExit(stage);
    return true;
}

static bool safeSetActorFaction(Actor actor, int faction) {
    logEnter("stage_c_set_actor_faction");
    if (!g_config.setCompanionFactionEnabled) {
        logExit("stage_c_set_actor_faction", "SKIPPED enable_set_faction=false");
        return false;
    }
    if (!actorValid(actor)) {
        logExit("stage_c_set_actor_faction", "FAILED reason=invalid_actor");
        return false;
    }
    logLine("stage_c SET_ACTOR_FACTION call reached actor=" + std::to_string(actor) +
            " faction=" + std::to_string(faction));
    DWORD exceptionCode = 0;
    nativeNoThrowVoidActorInt(0xCC63951AULL, actor, faction, &exceptionCode);
    if (exceptionCode != 0) {
        std::ostringstream line;
        line << "stage_c_set_actor_faction exception=0x" << std::hex << exceptionCode;
        logLine(line.str());
        logExit("stage_c_set_actor_faction", "FAILED reason=native_exception");
        return false;
    }
    logExit("stage_c_set_actor_faction");
    return true;
}

static bool safeSetActorIsCompanion(Actor actor, BOOL enabled) {
    logEnter("stage_c_set_actor_is_companion");
    if (!g_config.setCompanionFlagEnabled) {
        logExit("stage_c_set_actor_is_companion", "SKIPPED enable_set_companion=false");
        return false;
    }
    if (!actorValid(actor)) {
        logExit("stage_c_set_actor_is_companion", "FAILED reason=invalid_actor");
        return false;
    }
    logLine(std::string("stage_c SET_ACTOR_IS_COMPANION call reached enabled=") +
            (enabled ? "true" : "false"));
    DWORD exceptionCode = 0;
    nativeNoThrowVoidActorBool(0x4C94EB9EULL, actor, enabled, &exceptionCode);
    if (exceptionCode != 0) {
        std::ostringstream line;
        line << "stage_c_set_actor_is_companion exception=0x" << std::hex << exceptionCode;
        logLine(line.str());
        logExit("stage_c_set_actor_is_companion", "FAILED reason=native_exception");
        return false;
    }
    logExit("stage_c_set_actor_is_companion");
    return true;
}

static bool safeTaskFollowActor(Actor actor, Actor followActor) {
    logEnter("stage_d_task_follow_actor");
    if (!g_config.fallbackFollowEnabled) {
        logExit("stage_d_task_follow_actor", "SKIPPED enable_task_follow=false");
        return false;
    }
    if (!actorValid(actor) || !actorValid(followActor)) {
        logExit("stage_d_task_follow_actor", "FAILED reason=invalid_actor");
        return false;
    }
    logLine("stage_d TASK_FOLLOW_ACTOR call reached actor=" + std::to_string(actor) +
            " follow_actor=" + std::to_string(followActor));
    DWORD exceptionCode = 0;
    nativeNoThrowTaskFollow(actor, followActor, &exceptionCode);
    if (exceptionCode != 0) {
        std::ostringstream line;
        line << "stage_d_task_follow_actor exception=0x" << std::hex << exceptionCode;
        logLine(line.str());
        logExit("stage_d_task_follow_actor", "FAILED reason=native_exception");
        return false;
    }
    logExit("stage_d_task_follow_actor");
    return true;
}

static Actor playerActor(Vector3* pos, float* heading, float* health) {
    logEnter("resolve_player_actor");
    if (!g_nativeReady) {
        logExit("resolve_player_actor", "FAILED reason=native_not_ready");
        return 0;
    }
    Actor player = nativeInvoke<Actor>(0xE8CFDD53ULL, 0);
    if (!actorValid(player)) {
        logExit("resolve_player_actor", "FAILED reason=invalid_player");
        return 0;
    }
    if (pos) nativeInvoke<void>(0x99BD9D6FULL, player, pos);
    if (heading) *heading = nativeInvoke<float>(0x42DE39F0ULL, player);
    if (health) *health = nativeInvoke<float>(0xF246F15DULL, player);
    logExit("resolve_player_actor");
    return player;
}

static bool companionValid() {
    logEnter("validate_companion");
    bool ok = actorValid(g_companion);
    logExit("validate_companion", ok ? "OK" : "FAILED reason=invalid_companion");
    return ok;
}

static Layout companionLayout() {
    if (g_layout > 0) return g_layout;
    g_layout = nativeInvoke<Layout>(0x5699DE7EULL, "CodeREDPeerCompanion");
    if (g_layout <= 0) g_layout = nativeInvoke<Layout>(0x6CA53214ULL, "CodeREDPeerCompanion");
    return g_layout;
}

static void writeStatus(const char* phase) {
    Vector3 pos = {};
    float heading = 0.0f;
    float health = 0.0f;
    Actor player = 0;
    const bool startupReady = g_startTick != 0 && (GetTickCount64() - g_startTick) >= g_config.startupDelayMs;
    if (g_nativeReady && startupReady) player = playerActor(&pos, &heading, &health);
    bool validCompanion = g_nativeReady && startupReady && actorValid(g_companion);
    std::ostringstream out;
    out << "{\n"
        << "  \"version\": 1,\n"
        << "  \"source\": \"CodeRED_PeerCompanion\",\n"
        << "  \"timestamp_ms\": " << nowMs() << ",\n"
        << "  \"phase\": \"" << jsonEscape(phase) << "\",\n"
        << "  \"native_ready\": " << (g_nativeReady ? "true" : "false") << ",\n"
        << "  \"player_actor_valid\": " << (player > 0 ? "true" : "false") << ",\n"
        << "  \"player_actor\": " << player << ",\n"
        << "  \"x\": " << pos.x << ",\n"
        << "  \"y\": " << pos.y << ",\n"
        << "  \"z\": " << pos.z << ",\n"
        << "  \"heading\": " << heading << ",\n"
        << "  \"health\": " << health << ",\n"
        << "  \"companion_actor_valid\": " << (validCompanion ? "true" : "false") << ",\n"
        << "  \"companion_actor\": " << g_companion << ",\n"
        << "  \"ai_companion_enabled\": " << (g_aiMode ? "true" : "false") << ",\n"
        << "  \"peer_control_enabled\": " << (g_peerMode ? "true" : "false") << ",\n"
        << "  \"peer_link_enabled\": " << (g_peerConnected ? "true" : "false") << ",\n"
        << "  \"last_command\": \"" << jsonEscape(g_lastCommand) << "\",\n"
        << "  \"last_error\": \"" << jsonEscape(g_lastError) << "\"\n"
        << "}\n";
    writeText(rootPath(g_config.statusPath), out.str());
}


static Vector3 companionPointNearPlayer(const Vector3& playerPos, float heading, float distance, float heightOffset) {
    // Observed RDR PC actor coordinates from logs look like X/Z = ground plane and Y = height.
    // The older build used X/Y as ground plane. That can place the actor at the wrong spot.
    // This helper keeps the clone close to the player's reported coordinate system.
    float rad = heading * (PI / 180.0f);
    if (g_config.spawnUseXZGroundPlane) {
        return Vector3{
            playerPos.x + std::sin(rad) * distance,
            playerPos.y + heightOffset,
            playerPos.z + std::cos(rad) * distance
        };
    }
    return Vector3{
        playerPos.x + std::sin(rad) * distance,
        playerPos.y + std::cos(rad) * distance,
        playerPos.z + heightOffset
    };
}

static void logPlayerAndSpawnPoint(const char* stage, const Vector3& playerPos, float heading, const Vector3& dest) {
    std::ostringstream line;
    line << stage
         << " player_xyz=" << playerPos.x << "," << playerPos.y << "," << playerPos.z
         << " heading=" << heading
         << " spawn_xyz=" << dest.x << "," << dest.y << "," << dest.z
         << " distance=" << g_config.spawnDistance
         << " height_offset=" << g_config.spawnZOffset
         << " xz_ground_plane=" << (g_config.spawnUseXZGroundPlane ? "true" : "false");
    logLine(line.str());
}

static bool applyCompanion638State(Actor player, const char* source);

static bool requestActorLoaded(int actorEnum, DWORD timeoutMs) {
    logEnter("spawn_stage_streaming_request_actor");
    if (!g_config.streamingRequestEnabled) {
        logExit("spawn_stage_streaming_request_actor", "SKIPPED enable_streaming_request=false");
        return true;
    }
    DWORD exceptionCode = 0;
    logLine("spawn_stage STREAMING_REQUEST_ACTOR call reached enum=" + std::to_string(actorEnum));
    if (!nativeNoThrowStreamingRequestActor(actorEnum, &exceptionCode)) {
        std::ostringstream line;
        line << "spawn_stage_streaming_request_actor exception=0x" << std::hex << exceptionCode;
        logLine(line.str());
        logExit("spawn_stage_streaming_request_actor", "FAILED reason=native_exception");
        return false;
    }

    const DWORD start = GetTickCount();
    while (GetTickCount() - start < timeoutMs) {
        BOOL loaded = FALSE;
        exceptionCode = 0;
        if (!nativeNoThrowStreamingIsActorLoaded(actorEnum, &loaded, &exceptionCode)) {
            std::ostringstream line;
            line << "spawn_stage_streaming_is_actor_loaded exception=0x" << std::hex << exceptionCode;
            logLine(line.str());
            logExit("spawn_stage_streaming_request_actor", "FAILED reason=is_loaded_exception");
            return false;
        }
        if (loaded) {
            logExit("spawn_stage_streaming_request_actor", "OK loaded");
            return true;
        }
        waitFrame(50);
    }

    logExit("spawn_stage_streaming_request_actor", "FAILED reason=timeout");
    return false;
}

static bool spawnCompanionNearPlayer() {
    logEnter("spawn_companion");
    logLine("[PeerCompanion] F7 spawn/adopt requested");
    if (!g_config.companionSpawnEnabled) {
        g_lastError = "companion_spawn_enabled=false";
        logExit("spawn_companion", "FAILED reason=config_disabled");
        return false;
    }
    if (!g_config.spawn638Enabled) {
        g_lastError = "enable_spawn_638=false";
        logExit("spawn_companion", "FAILED reason=enable_spawn_638_false");
        return false;
    }
    const int actorEnumToSpawn = g_config.spawnActorEnum;
    if (actorEnumToSpawn >= 1177 && actorEnumToSpawn <= 1202) {
        g_lastError = "vehicle actor enum blocked for Pass 1";
        logExit("spawn_companion", "FAILED reason=vehicle_enum_blocked");
        return false;
    }
    Vector3 playerPos = {};
    float heading = 0.0f;
    Actor player = playerActor(&playerPos, &heading, nullptr);
    if (!actorValid(player)) {
        g_lastError = "player unavailable";
        logExit("spawn_companion", "FAILED reason=player_unavailable");
        return false;
    }
    if (companionValid()) {
        bool ok = applyCompanion638State(player, "F7_existing_companion");
        logExit("spawn_companion", ok ? "OK already_spawned_regrouped" : "FAILED already_spawned_regroup_failed");
        return ok;
    }
    Layout layout = companionLayout();
    if (layout <= 0) {
        g_lastError = "layout unavailable";
        logExit("spawn_companion", "FAILED reason=layout_unavailable");
        return false;
    }
    if (!requestActorLoaded(actorEnumToSpawn, 3000)) {
        g_lastError = "STREAMING_REQUEST_ACTOR failed or timed out";
        setOverlay("Spawn 638 failed: actor streaming timeout");
        logExit("spawn_companion", "FAILED reason=streaming_timeout");
        return false;
    }
    Vector3 dest = companionPointNearPlayer(playerPos, heading, g_config.spawnDistance, g_config.spawnZOffset);
    logPlayerAndSpawnPoint("spawn_point", playerPos, heading, dest);

    // CREATE_ACTOR_IN_LAYOUT is kept as the only required placement native.
    // The previous visibility nudge/teleport path could crash, so post-spawn position writes
    // are disabled by default and must be explicitly enabled in the INI.
    Vector2 spawnPlane = g_config.spawnUseXZGroundPlane
        ? Vector2{dest.x, dest.z}
        : Vector2{dest.x, dest.y};
    const float spawnHeight = g_config.spawnUseXZGroundPlane ? dest.y : dest.z;
    Vector2 orientPlane = {0.0f, 1.0f};
    std::ostringstream name;
    name << "codered_peer_companion_" << ++g_spawnCounter;
    Actor actor = 0;
    DWORD createException = 0;
    logLine("spawn_stage CREATE_ACTOR_IN_LAYOUT call reached enum=" + std::to_string(actorEnumToSpawn));
    nativeNoThrowCreateActorInLayout(layout, name.str().c_str(), actorEnumToSpawn,
                                     spawnPlane, spawnHeight, orientPlane, heading,
                                     &actor, &createException);
    if (createException != 0) {
        std::ostringstream line;
        line << "spawn_stage_create_actor exception=0x" << std::hex << createException;
        logLine(line.str());
        g_lastError = "CREATE_ACTOR_IN_LAYOUT native exception";
        logExit("spawn_companion", "FAILED reason=create_actor_exception");
        return false;
    }
    logLine("spawn_stage create_actor_return=" + std::to_string(actor));
    if (!actorValid(actor)) {
        g_lastError = "CREATE_ACTOR_IN_LAYOUT returned invalid actor";
        logExit("spawn_companion", "FAILED reason=create_actor_invalid");
        return false;
    }
    g_companion = actor;
    g_companionOwnedByCode = true;
    g_companionAdopted638 = false;
    g_companionPos = dest;
    if (g_config.postSpawnPositionNativeEnabled) {
        nativeInvoke<void>(0x2D54B916ULL, g_companion, &g_companionPos, TRUE, TRUE, TRUE);
        logLine("post_spawn_position_native called");
    } else {
        logLine("post_spawn_position_native skipped: disabled_by_config");
    }
    nativeInvoke<void>(0xECE8520BULL, g_companion, heading, TRUE);
    if (g_config.taskNativesEnabled) {
        nativeInvoke<void>(0x16876A25ULL, g_companion);
    }
    if (g_aiMode && g_config.taskNativesEnabled) {
        nativeInvoke<void>(0x12F0911AULL, g_companion, player);
    } else if (g_config.taskNativesEnabled) {
        nativeInvoke<void>(0x6F80965DULL, g_companion, -1.0f, 0, 0);
    }
    std::ostringstream ok;
    ok << "OK actor=" << g_companion << " enum=" << actorEnumToSpawn
       << " x=" << g_companionPos.x << " y=" << g_companionPos.y << " z=" << g_companionPos.z
       << " note=create_actor_only_near_player_no_teleport_default";
    setOverlay("Spawned companion actor=" + std::to_string(g_companion) +
               " enum=" + std::to_string(actorEnumToSpawn));
    logLine(ok.str());

    bool adopted = applyCompanion638State(player, "F7_spawned_actor_638");
    logExit("spawn_companion", adopted ? "OK spawned_and_adopted" : "OK spawned_follow_failed");
    return adopted;
}

static void despawnCompanion(const char* reason) {
    logEnter("despawn_companion");
    if (actorValid(g_companion)) {
        safeClearTask(g_companion, "release_task_clear");
        if (g_config.setCompanionFlagEnabled) {
            safeSetActorIsCompanion(g_companion, FALSE);
        }
        if (g_companionOwnedByCode) {
            nativeInvoke<void>(0x8BD21869ULL, g_companion);
            logLine("despawn destroyed CodeRED-owned spawned companion");
        } else {
            logLine("despawn skipped destroy for adopted retail actor");
        }
    }
    g_companion = 0;
    g_squad = 0;
    g_companionOwnedByCode = false;
    g_companionAdopted638 = false;
    setOverlay("Companion despawned");
    logLine(std::string("despawn reason=") + reason);
    logExit("despawn_companion");
}

static bool ensureCompanionForCommand() {
    if (companionValid()) return true;
    return spawnCompanionNearPlayer();
}

static void setIdle() {
    logEnter("set_idle");
    if (companionValid() && g_config.taskNativesEnabled) {
        nativeInvoke<void>(0x16876A25ULL, g_companion);
        nativeInvoke<void>(0x6F80965DULL, g_companion, -1.0f, 0, 0);
        setOverlay("Companion idle");
        logExit("set_idle");
    } else if (companionValid()) {
        setOverlay("Idle requested; task natives disabled");
        logExit("set_idle", "SKIPPED task_natives_disabled");
    } else {
        logExit("set_idle", "FAILED reason=invalid_companion");
    }
}

static void setFollowPlayer() {
    logEnter("set_follow_player");
    Vector3 pos = {};
    float heading = 0.0f;
    Actor player = playerActor(&pos, &heading, nullptr);
    if (actorValid(player) && ensureCompanionForCommand() && g_config.taskNativesEnabled) {
        nativeInvoke<void>(0x16876A25ULL, g_companion);
        nativeInvoke<void>(0x12F0911AULL, g_companion, player);
        setOverlay("Companion following player");
        logExit("set_follow_player");
    } else if (actorValid(player) && companionValid()) {
        setOverlay("Follow requested; task natives disabled");
        logExit("set_follow_player", "SKIPPED task_natives_disabled");
    } else {
        logExit("set_follow_player", "FAILED reason=missing_player_or_companion");
    }
}

static bool applyTaskPriority(const char* stage) {
    logEnter(stage);
    if (!g_config.taskPriorityEnabled) {
        logExit(stage, "SKIPPED task_priority_enabled=false");
        return false;
    }
    if (!actorValid(g_companion)) {
        logExit(stage, "FAILED reason=invalid_companion");
        return false;
    }
    nativeInvoke<void>(0x3A95A656ULL, g_companion, g_config.companionFollowPriority);
    std::ostringstream line;
    line << stage << " priority=" << g_config.companionFollowPriority;
    logLine(line.str());
    logExit(stage);
    return true;
}

static bool trySquadFollowRoute(Actor player) {
    logEnter("companion_squad_route");
    if (!g_config.squadRouteEnabled) {
        logExit("companion_squad_route", "SKIPPED squad_route_enabled=false");
        return false;
    }
    if (!actorValid(player) || !actorValid(g_companion)) {
        logExit("companion_squad_route", "FAILED reason=missing_player_or_companion");
        return false;
    }
    Layout layout = companionLayout();
    if (layout <= 0) {
        logExit("companion_squad_route", "FAILED reason=layout_unavailable");
        return false;
    }
    if (g_squad <= 0) {
        g_squad = nativeInvoke<Squad>(0xF7277A0FULL, layout, "CodeREDCompanion638Squad");
    }
    if (g_squad <= 0) {
        logExit("companion_squad_route", "FAILED reason=create_squad_failed");
        return false;
    }

    // The SDK exposes SQUAD_JOIN and SQUAD_GOAL_ADD_FOLLOW_OBJECT_IN_FORMATION
    // with Any parameters. This route is compiled but config-gated because the
    // exact argument semantics still need runtime proof.
    nativeInvoke<void>(0xB14302C8ULL, g_squad, player);
    nativeInvoke<void>(0xB14302C8ULL, g_squad, g_companion);
    int followGoal = nativeInvoke<int>(0x1AC03C80ULL, g_squad, player, 0, 0, 0, 0);

    std::ostringstream line;
    line << "squad_route squad=" << g_squad
         << " player=" << player
         << " companion=" << g_companion
         << " follow_goal=" << followGoal
         << " note=Any-argument native route explicitly enabled";
    logLine(line.str());
    logExit("companion_squad_route", followGoal != 0 ? "OK" : "FAILED reason=follow_goal_zero");
    return followGoal != 0;
}

static bool fallbackFollowActor(Actor player) {
    logEnter("companion_fallback_follow");
    if (!g_config.fallbackFollowEnabled) {
        logExit("companion_fallback_follow", "SKIPPED fallback_follow_enabled=false");
        return false;
    }
    if (!actorValid(player) || !actorValid(g_companion)) {
        logExit("companion_fallback_follow", "FAILED reason=missing_player_or_companion");
        return false;
    }
    safeClearTask(g_companion, "stage_d_task_clear_before_follow");
    if (!safeTaskFollowActor(g_companion, player)) {
        logExit("companion_fallback_follow", "FAILED reason=task_follow_failed");
        return false;
    }
    applyTaskPriority("companion_fallback_priority");
    setOverlay("Companion 638 following player");
    logExit("companion_fallback_follow");
    return true;
}

static bool applyCompanion638State(Actor player, const char* source) {
    logEnter("companion_apply_state");
    if (!actorValid(player) || !actorValid(g_companion)) {
        logExit("companion_apply_state", "FAILED reason=missing_player_or_companion");
        return false;
    }
    int enumValue = actorEnum(g_companion);
    int factionBefore = actorFaction(g_companion);
    std::ostringstream start;
    start << "companion_apply_state source=" << source
          << " actor=" << g_companion
          << " enum=" << enumValue
          << " faction_before=" << factionBefore;
    logLine(start.str());

    if (g_config.debugAdoptOnly) {
        logLine("debug_adopt_only=true; stopping after Stage B adopt-handle");
        logExit("companion_apply_state", "OK debug_adopt_only");
        return true;
    }

    safeSetActorFaction(g_companion, g_config.companionFaction);
    safeSetActorIsCompanion(g_companion, TRUE);

    int factionAfter = actorFaction(g_companion);
    std::ostringstream after;
    after << "companion_apply_state faction_after=" << factionAfter
          << " companion_flag_requested=" << (g_config.setCompanionFlagEnabled ? "true" : "false");
    logLine(after.str());

    bool squadOk = trySquadFollowRoute(player);
    bool followOk = squadOk ? true : fallbackFollowActor(player);
    logLine(std::string("companion_apply_state squad_route_used=") +
            (squadOk ? "true" : "false") +
            " fallback_used=" + (!squadOk && followOk ? "true" : "false"));
    logExit("companion_apply_state", followOk ? "OK" : "FAILED reason=no_follow_route");
    return followOk;
}

static bool adoptActor638(Actor candidate, Actor player, const Vector3& playerPos, const char* source) {
    logEnter("adopt_actor_638");
    if (!actorAlive(candidate)) {
        logExit("adopt_actor_638", "FAILED reason=invalid_or_dead_candidate");
        return false;
    }
    if (candidate == player) {
        logExit("adopt_actor_638", "FAILED reason=candidate_is_player");
        return false;
    }
    int enumValue = actorEnum(candidate);
    Vector3 candidatePos = {};
    actorPosition(candidate, &candidatePos);
    float dist = distance3(playerPos, candidatePos);
    std::ostringstream seen;
    seen << "adopt_candidate source=" << source
         << " actor=" << candidate
         << " enum=" << enumValue
         << " distance=" << dist
         << " xyz=" << candidatePos.x << "," << candidatePos.y << "," << candidatePos.z;
    logLine(seen.str());

    if (!g_config.allowAnyTarget && enumValue != g_config.adoptActorEnum) {
        logExit("adopt_actor_638", "FAILED reason=wrong_actor_enum");
        return false;
    }
    if (dist > g_config.adoptRadius) {
        logExit("adopt_actor_638", "FAILED reason=candidate_out_of_radius");
        return false;
    }

    g_companion = candidate;
    g_companionPos = candidatePos;
    g_companionOwnedByCode = false;
    g_companionAdopted638 = true;
    bool ok = applyCompanion638State(player, source);
    setOverlay(ok ? "Adopted actor 638 companion" : "Actor 638 adoption failed");
    logExit("adopt_actor_638", ok ? "OK" : "FAILED reason=apply_state_failed");
    return ok;
}

static bool adoptNearest638AndFollow() {
    logEnter("adopt_nearest_638");
    logLine("[PeerCompanion] F8 nearest adopt skipped: no safe actor iterator available; use F7 spawn/adopt.");
    setOverlay("F8 nearest adopt skipped; use F7 spawn/adopt");
    logExit("adopt_nearest_638", "SKIPPED no_safe_actor_iterator");
    return false;
#if 0
    if (!g_config.companionControllerEnabled) {
        logExit("adopt_nearest_638", "FAILED reason=companion_controller_enabled=false");
        return false;
    }
    Vector3 playerPos = {};
    float heading = 0.0f;
    Actor player = playerActor(&playerPos, &heading, nullptr);
    if (!actorValid(player)) {
        logExit("adopt_nearest_638", "FAILED reason=player_unavailable");
        return false;
    }
    if (actorValid(g_companion) && actorEnum(g_companion) == g_config.adoptActorEnum) {
        logLine("adopt_nearest_638 reusing existing companion handle");
        bool ok = applyCompanion638State(player, "existing_handle");
        logExit("adopt_nearest_638", ok ? "OK existing_handle" : "FAILED reason=existing_handle_apply_failed");
        return ok;
    }
    if (g_config.adoptTargetActorEnabled) {
        Actor target = 0;
        if (!safeGetTargetActor(&target)) {
            g_lastError = "F8 adopt failed: no valid targeted actor";
            logExit("adopt_nearest_638", "FAILED reason=no_valid_targeted_actor");
            setOverlay("F8 adopt failed: no valid targeted actor");
            return false;
        }
        if (adoptActor638(target, player, playerPos, "GET_TARGET_ACTOR")) {
            logExit("adopt_nearest_638", "OK target_actor");
            return true;
        }
    } else {
        logLine("GET_TARGET_ACTOR adoption skipped adopt_target_actor_enabled=false");
    }
    g_lastError = "No safe global actor iterator is wired; target a nearby actor 638 and press F8";
    logLine("adopt_nearest_638 nearest_scan_status=unsupported_no_safe_global_actor_iterator");
    logExit("adopt_nearest_638", "FAILED reason=no_candidate");
    setOverlay("No actor 638 adopted; target Jack/son near player and press F8");
    return false;
#endif
}

static void guardWaitCompanion638() {
    logEnter("guard_wait_638");
    if (!actorValid(g_companion)) {
        logExit("guard_wait_638", "FAILED reason=invalid_companion");
        return;
    }
    safeClearTask(g_companion, "guard_wait_task_clear");
    applyTaskPriority("guard_wait_priority");
    setOverlay("Companion 638 waiting/guarding current spot");
    logExit("guard_wait_638");
}

static void regroupCompanion638() {
    logEnter("regroup_follow_638");
    Vector3 pos = {};
    float heading = 0.0f;
    Actor player = playerActor(&pos, &heading, nullptr);
    if (actorValid(player) && actorValid(g_companion)) {
        applyCompanion638State(player, "regroup_hotkey");
        logExit("regroup_follow_638");
    } else {
        logExit("regroup_follow_638", "FAILED reason=missing_player_or_companion");
    }
}

static void drawOverlay() {
    if (!g_config.overlayEnabled || !g_drawText) return;
    const bool companion = g_nativeReady && actorValid(g_companion);
    std::ostringstream line;
    line << "CodeRED Companion 638 | F7 spawn/adopt F9 wait F10 regroup Backspace release | "
         << (companion ? "COMPANION OK" : "NO COMPANION")
         << " | enum638 " << (g_companionAdopted638 ? "ADOPTED" : "not adopted")
         << " | PEER " << (g_peerMode ? "ON" : "OFF");
    g_drawText(0.030f, 0.080f, line.str().c_str(), 255, 50, 50, 235, 0, 0.018f, 0);
    if (!g_overlayLine.empty()) {
        const bool flash = static_cast<int>(g_overlayFlashUntil - GetTickCount()) > 0;
        g_drawText(0.030f, 0.105f, g_overlayLine.c_str(),
                   flash ? 255 : 220, flash ? 235 : 220, flash ? 140 : 220,
                   235, 0, 0.016f, 0);
    }
}

static void teleportCompanionToPlayer() {
    logEnter("teleport_companion");
    if (!g_config.teleportCommandEnabled) {
        setOverlay("Teleport command disabled for crash isolation");
        logExit("teleport_companion", "SKIPPED disabled_by_config");
        return;
    }
    Vector3 pos = {};
    float heading = 0.0f;
    Actor player = playerActor(&pos, &heading, nullptr);
    if (actorValid(player) && ensureCompanionForCommand()) {
        Vector3 dest = companionPointNearPlayer(pos, heading, g_config.spawnDistance, g_config.spawnZOffset);
        logPlayerAndSpawnPoint("teleport_point", pos, heading, dest);
        nativeInvoke<void>(0x2D54B916ULL, g_companion, &dest, TRUE, TRUE, TRUE);
        nativeInvoke<void>(0xECE8520BULL, g_companion, heading, TRUE);
        g_companionPos = dest;
        setOverlay("Companion teleported near player");
        logExit("teleport_companion");
    } else {
        logExit("teleport_companion", "FAILED reason=missing_player_or_companion");
    }
}

static void setFaction(const char* stage, int faction) {
    logEnter(stage);
    if (ensureCompanionForCommand()) {
        nativeInvoke<void>(0xCC63951AULL, g_companion, faction);
        setOverlay(std::string("Companion faction command: ") + stage);
        logExit(stage);
    } else {
        logExit(stage, "FAILED reason=invalid_companion");
    }
}

static void setInvincible(bool enabled) {
    logEnter(enabled ? "set_invincible_true" : "set_invincible_false");
    if (ensureCompanionForCommand()) {
        nativeInvoke<void>(0xE38EF526ULL, g_companion, enabled ? TRUE : FALSE);
        setOverlay(enabled ? "Companion invincible ON" : "Companion invincible OFF");
        logExit(enabled ? "set_invincible_true" : "set_invincible_false");
    } else {
        logExit(enabled ? "set_invincible_true" : "set_invincible_false", "FAILED reason=invalid_companion");
    }
}

static void giveBasicWeapon() {
    logEnter("give_basic_weapon");
    if (!g_config.giveWeaponEnabled) {
        logExit("give_basic_weapon", "FAILED reason=config_disabled");
        return;
    }
    if (ensureCompanionForCommand()) {
        nativeInvoke<void>(0x6AA0EAF2ULL, g_companion, g_config.basicWeaponEnum,
                           g_config.basicWeaponAmmo, TRUE, 0);
        nativeInvoke<void>(0x8F4B473DULL, g_companion, g_config.basicWeaponEnum, 0);
        setOverlay("Companion given basic weapon");
        logExit("give_basic_weapon");
    } else {
        logExit("give_basic_weapon", "FAILED reason=invalid_companion");
    }
}

static void clearWeapons() {
    logEnter("clear_weapons");
    if (!g_config.clearWeaponsEnabled) {
        logExit("clear_weapons", "FAILED reason=config_disabled");
        return;
    }
    if (companionValid()) {
        nativeInvoke<void>(0xD695F857ULL, g_companion);
        setOverlay("Companion weapons cleared");
        logExit("clear_weapons");
    } else {
        logExit("clear_weapons", "FAILED reason=invalid_companion");
    }
}

static std::string jsonStringValue(const std::string& text, const char* key) {
    std::string needle = std::string("\"") + key + "\"";
    size_t p = text.find(needle);
    if (p == std::string::npos) return "";
    p = text.find(':', p + needle.size());
    if (p == std::string::npos) return "";
    p = text.find('"', p + 1);
    if (p == std::string::npos) return "";
    size_t e = text.find('"', p + 1);
    if (e == std::string::npos) return "";
    return text.substr(p + 1, e - p - 1);
}

static void archiveCommand(const std::string& text) {
    writeText(rootPath(g_config.commandArchivePath), text);
}

static void executeCommand(const std::string& command) {
    logEnter("execute_peer_command");
    g_lastCommand = command;
    if (command == "spawn_companion") spawnCompanionNearPlayer();
    else if (command == "adopt_638" || command == "adopt_follow_638") adoptNearest638AndFollow();
    else if (command == "despawn_companion") despawnCompanion("peer_command");
    else if (command == "release_638") despawnCompanion("peer_command_release_638");
    else if (command == "follow_player") setFollowPlayer();
    else if (command == "regroup_638") regroupCompanion638();
    else if (command == "guard_wait_638") guardWaitCompanion638();
    else if (command == "idle") setIdle();
    else if (command == "friendly") setFaction("set_friendly", g_config.friendlyFaction);
    else if (command == "neutral") setFaction("set_relationship", g_config.neutralFaction);
    else if (command == "hostile") setFaction("set_hostile", g_config.hostileFaction);
    else if (command == "guard_player") {
        giveBasicWeapon();
        setFollowPlayer();
    } else if (command == "stop_combat") {
        setIdle();
    } else if (command == "teleport_to_player") teleportCompanionToPlayer();
    else if (command == "set_invincible_true") setInvincible(true);
    else if (command == "set_invincible_false") setInvincible(false);
    else if (command == "give_basic_weapon") giveBasicWeapon();
    else if (command == "clear_weapons") clearWeapons();
    else logLine("unknown_command ignored command=" + command);
    logExit("execute_peer_command");
}

static void pollPeerCommand() {
    if (!g_peerMode || !g_config.externalCommandEnabled) return;
    logEnter("read_peer_command");
    std::string text;
    if (!readText(rootPath(g_config.commandInboxPath), &text) || trim(text).empty()) {
        logExit("read_peer_command", "OK empty");
        return;
    }
    logExit("read_peer_command");
    logEnter("parse_peer_command");
    std::string command = jsonStringValue(text, "command");
    std::string commandId = jsonStringValue(text, "command_id");
    if (commandId.empty()) commandId = jsonStringValue(text, "time_ms");
    if (command.empty()) {
        logExit("parse_peer_command", "FAILED reason=missing_command");
        return;
    }
    if (!commandId.empty() && commandId == g_lastCommandId) {
        logExit("parse_peer_command", "OK duplicate_ignored");
        return;
    }
    g_lastCommandId = commandId;
    archiveCommand(text);
    logExit("parse_peer_command");
    executeCommand(command);
}

static void snapshot() {
    logEnter("snapshot");
    Vector3 pos = {};
    float heading = 0.0f;
    float health = 0.0f;
    Actor player = playerActor(&pos, &heading, &health);
    const bool compOk = actorValid(g_companion);
    Vector3 compPos = {};
    if (compOk) nativeInvoke<void>(0x99BD9D6FULL, g_companion, &compPos);
    int compEnum = compOk ? actorEnum(g_companion) : -1;
    int compFaction = compOk ? actorFaction(g_companion) : -1;
    std::ostringstream line;
    line << "snapshot player_valid=" << (actorValid(player) ? "true" : "false")
         << " player=" << player
         << " player_xyz=" << pos.x << "," << pos.y << "," << pos.z
         << " heading=" << heading
         << " health=" << health
         << " companion_valid=" << (compOk ? "true" : "false")
         << " companion=" << g_companion
         << " companion_enum=" << compEnum
         << " companion_faction=" << compFaction
         << " companion_owned_by_code=" << (g_companionOwnedByCode ? "true" : "false")
         << " companion_adopted_638=" << (g_companionAdopted638 ? "true" : "false")
         << " companion_xyz=" << compPos.x << "," << compPos.y << "," << compPos.z
         << " ai_mode=" << (g_aiMode ? "true" : "false")
         << " peer_mode=" << (g_peerMode ? "true" : "false");
    logLine(line.str());
    writeStatus("snapshot");
    logExit("snapshot");
}

static void tick() {
    const DWORD now = GetTickCount();
    if (g_config.heartbeatEnabled && now - g_lastHeartbeatTick >= g_config.heartbeatMs) {
        g_lastHeartbeatTick = now;
        logEnter("heartbeat");
        logLine("heartbeat uptime_ms=" + std::to_string(GetTickCount64() - g_startTick) +
                " peer_mode=" + (g_peerMode ? std::string("true") : std::string("false")) +
                " ai_mode=" + (g_aiMode ? std::string("true") : std::string("false")));
        logExit("heartbeat");
    }
    if ((GetTickCount64() - g_startTick) < g_config.startupDelayMs) {
        if (now - g_lastStatusTick >= 1000) {
            g_lastStatusTick = now;
            writeStatus("startup_delay");
        }
        return;
    }
    if (now - g_lastStatusTick >= g_config.heartbeatMs) {
        g_lastStatusTick = now;
        writeStatus("heartbeat");
    }
    if (now - g_lastCommandPollTick >= g_config.commandPollMs) {
        g_lastCommandPollTick = now;
        pollPeerCommand();
    }
}

static void keyboardHandler(DWORD key, WORD, BYTE, BOOL, BOOL, BOOL, BOOL) {
    DWORD now = GetTickCount();
    if (key < 256) {
        if (now - g_lastHotkeyTick[key] < 400) return;
        g_lastHotkeyTick[key] = now;
    }
    const ULONGLONG elapsed = GetTickCount64() - g_startTick;
    if (elapsed < g_config.startupDelayMs && key != VK_F12) {
        logLine("hotkey_blocked startup_delay key=" + std::to_string(key));
        return;
    }
    if (key == VK_F6) {
        snapshot();
        setOverlay("Snapshot logged");
    } else if (key == VK_F7) {
        spawnCompanionNearPlayer();
        writeStatus("spawn_638_adopt_hotkey");
    } else if (key == VK_F8) {
        logLine("[PeerCompanion] F8 key detected: nearest adopt requested");
        adoptNearest638AndFollow();
        writeStatus("nearest_adopt_638_hotkey");
    } else if (key == VK_F9) {
        guardWaitCompanion638();
        writeStatus("guard_wait_638_hotkey");
    } else if (key == VK_F10) {
        regroupCompanion638();
        writeStatus("regroup_638_hotkey");
    } else if (key == VK_F11) {
        g_peerMode = !g_peerMode;
        g_config.externalCommandEnabled = g_peerMode;
        logLine(std::string("peer_control_toggled enabled=") + (g_peerMode ? "true" : "false"));
        setOverlay(std::string("Peer control ") + (g_peerMode ? "ON" : "OFF"));
        writeStatus("peer_control_toggled");
    } else if (key == VK_F12) {
        logLine("help F6=snapshot F7=spawn/adopt actor638 F8=nearest-skip F9=guard/wait F10=regroup/follow F11=peer-control Backspace=release F12=help");
        setOverlay("F7 spawn/adopt 638 | F9 wait | F10 regroup | Backspace release");
        writeStatus("help");
    } else if (key == VK_BACK) {
        despawnCompanion("backspace");
        writeStatus("backspace_cleanup");
    }
}

static void mainScript() {
    loadConfig();
    g_startTick = GetTickCount64();
    logLine("asi_script_started startup_delay_ms=" + std::to_string(g_config.startupDelayMs));
    writeStatus("script_started");

    while (InterlockedCompareExchange(&g_stopRequested, 0, 0) == 0) {
        if (!g_nativeReady && !resolveScriptHook()) {
            writeStatus("waiting_for_scripthook");
            waitFrame(1000);
            continue;
        }
        tick();
        drawOverlay();
        waitFrame(25);
    }
    despawnCompanion("shutdown");
    writeStatus("shutdown");
    logLine("asi_script_stopped");
}

static DWORD WINAPI registrationThread(void*) {
    loadConfig();
    logLine("ASI attached");
    for (int i = 0; i < 120 && !resolveScriptHook(); ++i) {
        logLine("ScriptHookRDR.dll not found or exports missing; retry=" + std::to_string(i));
        Sleep(1000);
    }
    if (!g_nativeReady) {
        logLine("registration_failed reason=scripthook_exports_unavailable");
        return 0;
    }
    if (InterlockedCompareExchange(&g_registered, 1, 0) == 0) {
        g_scriptRegister(g_module, mainScript);
        g_keyboardRegister(keyboardHandler);
        logLine("registration_success");
        writeStatus("registered");
    }
    return 0;
}

} // namespace codered_peer_companion

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID) {
    using namespace codered_peer_companion;
    if (reason == DLL_PROCESS_ATTACH) {
        g_module = module;
        InitializeCriticalSection(&g_logLock);
        g_logLockReady = true;
        DisableThreadLibraryCalls(module);
        HANDLE thread = CreateThread(nullptr, 0, registrationThread, nullptr, 0, nullptr);
        if (thread) CloseHandle(thread);
    } else if (reason == DLL_PROCESS_DETACH) {
        InterlockedExchange(&g_stopRequested, 1);
        if (g_registered && g_keyboardUnregister) g_keyboardUnregister(keyboardHandler);
        if (g_registered && g_scriptUnregister) g_scriptUnregister(g_module);
        if (g_logLockReady) {
            DeleteCriticalSection(&g_logLock);
            g_logLockReady = false;
        }
    }
    return TRUE;
}
