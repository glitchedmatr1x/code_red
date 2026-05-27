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
    bool postSpawnActionsEnabled = false;
    bool giveWeaponEnabled = true;
    bool clearWeaponsEnabled = true;
    DWORD startupDelayMs = 15000;
    DWORD commandPollMs = 200;
    DWORD heartbeatMs = 5000;
    int companionActorEnum = 369;
    int fallbackActorEnum = 111;
    int friendlyFaction = 0;
    int neutralFaction = 0;
    int hostileFaction = 0;
    int basicWeaponEnum = 4;
    float basicWeaponAmmo = 60.0f;
    float spawnDistance = 3.0f;
    float spawnHeightOffset = 0.0f;
    float spawnHeadingOffset = 0.0f;
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
static Actor g_companion = 0;
static Vector3 g_companionPos = {};
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
        else if (key == "post_spawn_actions_enabled") g_config.postSpawnActionsEnabled = parseBool(value, g_config.postSpawnActionsEnabled);
        else if (key == "give_weapon_enabled") g_config.giveWeaponEnabled = parseBool(value, g_config.giveWeaponEnabled);
        else if (key == "clear_weapons_enabled") g_config.clearWeaponsEnabled = parseBool(value, g_config.clearWeaponsEnabled);
        else if (key == "startup_delay_ms") g_config.startupDelayMs = static_cast<DWORD>(std::max(0, std::atoi(value.c_str())));
        else if (key == "command_poll_ms") g_config.commandPollMs = static_cast<DWORD>(std::max(100, std::atoi(value.c_str())));
        else if (key == "heartbeat_ms") g_config.heartbeatMs = static_cast<DWORD>(std::max(1000, std::atoi(value.c_str())));
        else if (key == "companion_actor_enum") g_config.companionActorEnum = std::atoi(value.c_str());
        else if (key == "fallback_actor_enum") g_config.fallbackActorEnum = std::atoi(value.c_str());
        else if (key == "friendly_faction") g_config.friendlyFaction = std::atoi(value.c_str());
        else if (key == "neutral_faction") g_config.neutralFaction = std::atoi(value.c_str());
        else if (key == "hostile_faction") g_config.hostileFaction = std::atoi(value.c_str());
        else if (key == "basic_weapon_enum") g_config.basicWeaponEnum = std::atoi(value.c_str());
        else if (key == "basic_weapon_ammo") g_config.basicWeaponAmmo = static_cast<float>(std::atof(value.c_str()));
        else if (key == "spawn_distance") g_config.spawnDistance = static_cast<float>(std::max(1.0, std::atof(value.c_str())));
        else if (key == "spawn_height_offset") g_config.spawnHeightOffset = static_cast<float>(std::atof(value.c_str()));
        else if (key == "spawn_z_offset") g_config.spawnHeightOffset = static_cast<float>(std::atof(value.c_str()));
        else if (key == "spawn_heading_offset") g_config.spawnHeadingOffset = static_cast<float>(std::atof(value.c_str()));
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

static std::string vectorString(const Vector3& pos) {
    std::ostringstream out;
    out << pos.x << "," << pos.y << "," << pos.z;
    return out.str();
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

static bool spawnCompanionNearPlayer() {
    logEnter("spawn_companion");
    if (!g_config.companionSpawnEnabled) {
        g_lastError = "companion_spawn_enabled=false";
        logExit("spawn_companion", "FAILED reason=config_disabled");
        return false;
    }
    if (g_config.companionActorEnum >= 1177 && g_config.companionActorEnum <= 1202) {
        g_lastError = "vehicle actor enum blocked for Pass 1";
        logExit("spawn_companion", "FAILED reason=vehicle_enum_blocked");
        return false;
    }
    if (companionValid()) {
        logExit("spawn_companion", "OK already_spawned");
        return true;
    }
    Vector3 playerPos = {};
    float heading = 0.0f;
    Actor player = playerActor(&playerPos, &heading, nullptr);
    const bool playerValid = actorValid(player);
    logLine(std::string("player_valid=") + (playerValid ? "true" : "false"));
    logLine("player_xyz=" + vectorString(playerPos));
    logLine("heading=" + std::to_string(heading));
    if (!playerValid) {
        g_lastError = "player unavailable";
        logExit("spawn_companion", "FAILED reason=player_unavailable");
        return false;
    }
    Layout layout = companionLayout();
    if (layout <= 0) {
        g_lastError = "layout unavailable";
        logExit("spawn_companion", "FAILED reason=layout_unavailable");
        return false;
    }
    float rad = heading * (PI / 180.0f);
    Vector2 spawnXY = {
        playerPos.x + std::sin(rad) * g_config.spawnDistance,
        playerPos.y + std::cos(rad) * g_config.spawnDistance
    };
    const float spawnZ = playerPos.z + g_config.spawnHeightOffset;
    const float spawnHeading = heading + g_config.spawnHeadingOffset;
    Vector2 orientXY = {0.0f, 1.0f};
    std::ostringstream name;
    name << "codered_peer_companion_" << ++g_spawnCounter;

    auto createActor = [&](int actorEnum, const char* methodName) -> Actor {
        logLine("spawn_xyz=" + vectorString({spawnXY.x, spawnXY.y, spawnZ}));
        logLine("actor_enum=" + std::to_string(actorEnum));
        logLine(std::string("using_spawn_method=") + methodName);
        Actor created = nativeInvoke<Actor>(0x8D67F397ULL, layout, name.str().c_str(),
                                            actorEnum, spawnXY, spawnZ,
                                            orientXY, spawnHeading);
        logLine("create_actor_return=" + std::to_string(created));
        logLine(std::string("is_actor_valid_after_create=") + (actorValid(created) ? "true" : "false"));
        return created;
    };

    Actor actor = createActor(g_config.companionActorEnum, "CodeRED_AI_Menu::spawnSelectedNpc");
    int usedActorEnum = g_config.companionActorEnum;
    if (!actorValid(actor) && g_config.fallbackActorEnum > 0 &&
        g_config.fallbackActorEnum != g_config.companionActorEnum) {
        std::ostringstream fallbackName;
        fallbackName << "codered_peer_companion_fallback_" << g_spawnCounter;
        name.str("");
        name.clear();
        name << fallbackName.str();
        logLine("primary_spawn_failed_trying_fallback_actor_enum=" + std::to_string(g_config.fallbackActorEnum));
        actor = createActor(g_config.fallbackActorEnum, "CodeRED_AI_Menu::spawnSelectedNpc:fallback");
        usedActorEnum = g_config.fallbackActorEnum;
    }

    if (!actorValid(actor)) {
        g_lastError = "CREATE_ACTOR_IN_LAYOUT returned invalid actor";
        logExit("spawn_companion", "FAILED reason=create_actor_invalid");
        return false;
    }
    g_companion = actor;
    g_companionPos = {spawnXY.x, spawnXY.y, spawnZ};
    if (g_config.postSpawnActionsEnabled) {
        nativeInvoke<void>(0xECE8520BULL, g_companion, spawnHeading, TRUE);
    }
    std::ostringstream ok;
    ok << "OK actor=" << g_companion << " enum=" << usedActorEnum
       << " x=" << g_companionPos.x << " y=" << g_companionPos.y << " z=" << g_companionPos.z;
    setOverlay("Spawned companion actor=" + std::to_string(g_companion) +
               " enum=" + std::to_string(usedActorEnum));
    logExit("spawn_companion", ok.str().c_str());
    return true;
}

static void despawnCompanion(const char* reason) {
    logEnter("despawn_companion");
    if (actorValid(g_companion)) {
        nativeInvoke<void>(0x16876A25ULL, g_companion);
        nativeInvoke<void>(0x8BD21869ULL, g_companion);
    }
    g_companion = 0;
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

static void drawOverlay() {
    if (!g_config.overlayEnabled || !g_drawText) return;
    const bool companion = g_nativeReady && actorValid(g_companion);
    std::ostringstream line;
    line << "CodeRED Peer Companion | F8 spawn F9 despawn F10 AI F11 peer | "
         << (companion ? "COMPANION OK" : "NO COMPANION")
         << " | AI " << (g_aiMode ? "ON" : "OFF")
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
    Vector3 pos = {};
    float heading = 0.0f;
    Actor player = playerActor(&pos, &heading, nullptr);
    if (actorValid(player) && ensureCompanionForCommand()) {
        float rad = heading * (PI / 180.0f);
        Vector3 dest = {
            pos.x + std::sin(rad) * 2.5f,
            pos.y + std::cos(rad) * 2.5f,
            pos.z
        };
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
    else if (command == "despawn_companion") despawnCompanion("peer_command");
    else if (command == "follow_player") setFollowPlayer();
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
    std::ostringstream line;
    line << "snapshot player_valid=" << (actorValid(player) ? "true" : "false")
         << " player=" << player
         << " x=" << pos.x << " y=" << pos.y << " z=" << pos.z
         << " heading=" << heading
         << " health=" << health
         << " companion_valid=" << (actorValid(g_companion) ? "true" : "false")
         << " companion=" << g_companion
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

static void keyboardHandler(DWORD key, WORD, BYTE, BOOL, BOOL, BOOL wasDown, BOOL upNow) {
    if (upNow || wasDown) return;
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
        g_peerConnected = !g_peerConnected;
        logLine(std::string("peer_link_toggled enabled=") + (g_peerConnected ? "true" : "false"));
        setOverlay(std::string("Peer link ") + (g_peerConnected ? "ON" : "OFF"));
        writeStatus("peer_link_toggled");
    } else if (key == VK_F8) {
        spawnCompanionNearPlayer();
        writeStatus("spawn_hotkey");
    } else if (key == VK_F9) {
        despawnCompanion("hotkey");
        writeStatus("despawn_hotkey");
    } else if (key == VK_F10) {
        g_aiMode = !g_aiMode;
        logLine(std::string("ai_companion_toggled enabled=") + (g_aiMode ? "true" : "false"));
        if (g_aiMode && actorValid(g_companion)) setFollowPlayer();
        else if (actorValid(g_companion)) setIdle();
        else setOverlay(std::string("AI mode ") + (g_aiMode ? "ON" : "OFF"));
        writeStatus("ai_toggled");
    } else if (key == VK_F11) {
        g_peerMode = !g_peerMode;
        g_config.externalCommandEnabled = g_peerMode;
        logLine(std::string("peer_control_toggled enabled=") + (g_peerMode ? "true" : "false"));
        setOverlay(std::string("Peer control ") + (g_peerMode ? "ON" : "OFF"));
        writeStatus("peer_control_toggled");
    } else if (key == VK_F12) {
        logLine("help F6=snapshot F7=peer-link F8=spawn F9=despawn F10=AI F11=peer-control F12=help");
        setOverlay("F6 snapshot | F8 spawn | F9 despawn | F10 AI | F11 peer");
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
