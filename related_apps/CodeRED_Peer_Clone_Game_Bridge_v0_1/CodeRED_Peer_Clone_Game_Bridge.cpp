// Code RED Peer Clone Red Dead In-Game Clone Bridge v0.1
//
// ASI-side bridge for an already-running singleplayer session. It only reads and
// writes JSON bridge files and optionally spawns one human actor clone. It does
// not edit RPFs, restore official multiplayer, spawn vehicles, or touch content.rpf.

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

namespace codered_peer_clone_bridge {

using KeyboardHandler = void(*)(DWORD, WORD, BYTE, BOOL, BOOL, BOOL, BOOL);
using ScriptRegisterFn = void(*)(HMODULE, void(*)());
using ScriptUnregisterFn = void(*)(HMODULE);
using KeyboardHandlerRegisterFn = void(*)(KeyboardHandler);
using KeyboardHandlerUnregisterFn = void(*)(KeyboardHandler);
using ScriptWaitFn = void(*)(DWORD);
using NativeInitFn = void(*)(unsigned long long);
using NativePush64Fn = void(*)(unsigned long long);
using NativeCallFn = unsigned long long*(*)();

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

struct RemotePlayer {
    bool valid = false;
    std::string clientId;
    std::string name;
    float x = 0.0f;
    float y = 0.0f;
    float z = 0.0f;
    float heading = 0.0f;
    float health = 100.0f;
    long long pulseId = 0;
};

struct Config {
    std::string mode = "log-only";
    std::string bridgeDir = "bridge";
    std::string runtimeDir = "runtime";
    std::string localStatePath = "bridge/local_player_state.json";
    std::string remoteStatePath = "bridge/remote_players_state.json";
    std::string statusPath = "bridge/bridge_status.json";
    std::string jsonlPath = "runtime/codered_peer_clone_game_bridge.jsonl";
    int cloneActorEnum = 369; // ACTOR_CAUCASIAN_ARMY_Easy01, human seed enum.
    float spawnDistance = 2.5f;
    float positionScale = 0.05f;
    float interpolation = 0.35f;
    DWORD tickMs = 100;
    DWORD startupDelayMs = 30000;
    bool allowSpawn = false;
    bool relativeRemoteCoordinates = true;
};

static HMODULE g_module = nullptr;
static HMODULE g_scriptHook = nullptr;
static ScriptRegisterFn g_scriptRegister = nullptr;
static ScriptUnregisterFn g_scriptUnregister = nullptr;
static KeyboardHandlerRegisterFn g_keyboardHandlerRegister = nullptr;
static KeyboardHandlerUnregisterFn g_keyboardHandlerUnregister = nullptr;
static ScriptWaitFn g_scriptWait = nullptr;
static NativeInitFn g_nativeInit = nullptr;
static NativePush64Fn g_nativePush64 = nullptr;
static NativeCallFn g_nativeCall = nullptr;
static volatile LONG g_stopRequested = 0;
static volatile LONG g_registered = 0;
static Config g_config;
static std::string g_rootDir;
static bool g_configLoaded = false;
static bool g_nativeReady = false;
static bool g_killSwitch = false;
static bool g_noSpawnFallback = false;
static std::string g_lastError;
static Layout g_layout = 0;
static Actor g_clone = 0;
static int g_spawnCounter = 0;
static Vector3 g_clonePos = {};
static DWORD g_lastReadTick = 0;
static DWORD g_lastStatusTick = 0;
static ULONGLONG g_scriptStartTick = 0;

static constexpr float PI = 3.14159265358979323846f;

static std::string replaceSlashes(std::string value) {
    std::replace(value.begin(), value.end(), '/', '\\');
    return value;
}

static std::string trim(const std::string& value) {
    size_t start = 0;
    while (start < value.size() && std::isspace(static_cast<unsigned char>(value[start]))) {
        ++start;
    }
    size_t end = value.size();
    while (end > start && std::isspace(static_cast<unsigned char>(value[end - 1]))) {
        --end;
    }
    return value.substr(start, end - start);
}

static std::string moduleDir() {
    char path[MAX_PATH] = {};
    DWORD len = GetModuleFileNameA(g_module, path, MAX_PATH);
    if (len == 0 || len >= MAX_PATH) {
        len = GetModuleFileNameA(nullptr, path, MAX_PATH);
    }
    std::string result(path);
    size_t slash = result.find_last_of("\\/");
    if (slash == std::string::npos) {
        return ".";
    }
    return result.substr(0, slash);
}

static bool isAbsolutePath(const std::string& path) {
    if (path.size() >= 3 && std::isalpha(static_cast<unsigned char>(path[0])) &&
        path[1] == ':' && (path[2] == '\\' || path[2] == '/')) {
        return true;
    }
    return path.size() >= 2 && path[0] == '\\' && path[1] == '\\';
}

static std::string pathJoin(const std::string& left, const std::string& right) {
    if (right.empty()) return left;
    if (isAbsolutePath(right)) return replaceSlashes(right);
    if (left.empty()) return replaceSlashes(right);
    const char last = left[left.size() - 1];
    if (last == '\\' || last == '/') {
        return replaceSlashes(left + right);
    }
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
    } else if (normalized.size() >= 2 && normalized[0] == '\\' && normalized[1] == '\\') {
        size_t server = normalized.find('\\', 2);
        size_t share = server == std::string::npos ? std::string::npos : normalized.find('\\', server + 1);
        if (share != std::string::npos) {
            partial = normalized.substr(0, share);
            start = share + 1;
        }
    }
    for (size_t i = start; i <= normalized.size(); ++i) {
        if (i == normalized.size() || normalized[i] == '\\') {
            std::string current = partial.empty() ? normalized.substr(0, i) : partial + normalized.substr(start - 1, i - start + 1);
            if (!current.empty() && current[current.size() - 1] != ':') {
                CreateDirectoryA(current.c_str(), nullptr);
            }
        }
    }
}

static void ensureParentDir(const std::string& path) {
    size_t slash = path.find_last_of("\\/");
    if (slash != std::string::npos) {
        ensureDir(path.substr(0, slash));
    }
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

static long long nowMs() {
    FILETIME ft = {};
    GetSystemTimeAsFileTime(&ft);
    ULARGE_INTEGER uli = {};
    uli.LowPart = ft.dwLowDateTime;
    uli.HighPart = ft.dwHighDateTime;
    return static_cast<long long>((uli.QuadPart - 116444736000000000ULL) / 10000ULL);
}

static std::string jsonEscape(const std::string& value) {
    std::string out;
    out.reserve(value.size() + 8);
    for (char ch : value) {
        switch (ch) {
            case '\\': out += "\\\\"; break;
            case '"': out += "\\\""; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default:
                if (static_cast<unsigned char>(ch) < 0x20) {
                    char buf[8] = {};
                    std::snprintf(buf, sizeof(buf), "\\u%04x", static_cast<unsigned char>(ch));
                    out += buf;
                } else {
                    out += ch;
                }
        }
    }
    return out;
}

static void appendJsonl(const std::string& event, const std::string& details) {
    const std::string path = rootPath(g_config.jsonlPath);
    ensureParentDir(path);
    std::ofstream file(path, std::ios::binary | std::ios::app);
    if (!file) return;
    file << "{\"schema\":\"codered.peer_clone.game_bridge.event.v1\","
         << "\"updated_ms\":" << nowMs()
         << ",\"mode\":\"" << jsonEscape(g_config.mode) << "\""
         << ",\"event\":\"" << jsonEscape(event) << "\"";
    if (!details.empty()) {
        file << "," << details;
    }
    file << "}\n";
}

static FARPROC resolveExport(const char* name, const char* decoratedName = nullptr) {
    if (!g_scriptHook) return nullptr;
    FARPROC proc = GetProcAddress(g_scriptHook, name);
    if (!proc && decoratedName) {
        proc = GetProcAddress(g_scriptHook, decoratedName);
    }
    return proc;
}

static bool resolveScriptHook() {
    if (!g_scriptHook) {
        g_scriptHook = GetModuleHandleA("ScriptHookRDR.dll");
        if (!g_scriptHook) {
            g_scriptHook = LoadLibraryA("ScriptHookRDR.dll");
        }
    }
    if (!g_scriptHook) {
        g_lastError = "ScriptHookRDR.dll not loaded";
        return false;
    }

    g_scriptRegister = reinterpret_cast<ScriptRegisterFn>(
        resolveExport("scriptRegister", "?scriptRegister@@YAXPEAUHINSTANCE__@@P6AXXZ@Z"));
    g_scriptUnregister = reinterpret_cast<ScriptUnregisterFn>(
        resolveExport("scriptUnregister", "?scriptUnregister@@YAXPEAUHINSTANCE__@@@Z"));
    g_keyboardHandlerRegister = reinterpret_cast<KeyboardHandlerRegisterFn>(
        resolveExport("keyboardHandlerRegister", "?keyboardHandlerRegister@@YAXP6AXKGEHHHH@Z@Z"));
    g_keyboardHandlerUnregister = reinterpret_cast<KeyboardHandlerUnregisterFn>(
        resolveExport("keyboardHandlerUnregister", "?keyboardHandlerUnregister@@YAXP6AXKGEHHHH@Z@Z"));
    g_scriptWait = reinterpret_cast<ScriptWaitFn>(
        resolveExport("scriptWait", "?scriptWait@@YAXK@Z"));
    g_nativeInit = reinterpret_cast<NativeInitFn>(
        resolveExport("nativeInit", "?nativeInit@@YAX_K@Z"));
    g_nativePush64 = reinterpret_cast<NativePush64Fn>(
        resolveExport("nativePush64", "?nativePush64@@YAX_K@Z"));
    g_nativeCall = reinterpret_cast<NativeCallFn>(
        resolveExport("nativeCall", "?nativeCall@@YAPEA_KXZ"));

    g_nativeReady = g_scriptRegister && g_scriptUnregister &&
                    g_keyboardHandlerRegister && g_keyboardHandlerUnregister &&
                    g_scriptWait && g_nativeInit && g_nativePush64 && g_nativeCall;
    if (!g_nativeReady) {
        g_lastError = "ScriptHookRDR exports missing";
    }
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
    if (g_scriptWait) {
        g_scriptWait(ms);
    } else {
        Sleep(ms);
    }
}

static bool parseBool(const std::string& value, bool fallback) {
    std::string v = value;
    std::transform(v.begin(), v.end(), v.begin(), [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    if (v == "1" || v == "true" || v == "yes" || v == "on") return true;
    if (v == "0" || v == "false" || v == "no" || v == "off") return false;
    return fallback;
}

static void loadConfig() {
    if (g_configLoaded) return;
    g_configLoaded = true;
    g_rootDir = moduleDir();

    const std::string cfgPath = rootPath("CodeRED_Peer_Clone_Game_Bridge.ini");
    std::string text;
    if (!readText(cfgPath, &text)) {
        ensureDir(rootPath(g_config.bridgeDir));
        ensureDir(rootPath(g_config.runtimeDir));
        appendJsonl("config_defaulted", "\"reason\":\"ini_not_found\"");
        return;
    }

    std::istringstream lines(text);
    std::string line;
    while (std::getline(lines, line)) {
        line = trim(line);
        if (line.empty() || line[0] == '#' || line[0] == ';') continue;
        size_t eq = line.find('=');
        if (eq == std::string::npos) continue;
        const std::string key = trim(line.substr(0, eq));
        const std::string value = trim(line.substr(eq + 1));
        if (key == "mode") g_config.mode = value;
        else if (key == "bridge_dir") g_config.bridgeDir = value;
        else if (key == "runtime_dir") g_config.runtimeDir = value;
        else if (key == "local_player_state") g_config.localStatePath = value;
        else if (key == "remote_players_state") g_config.remoteStatePath = value;
        else if (key == "bridge_status") g_config.statusPath = value;
        else if (key == "jsonl_log") g_config.jsonlPath = value;
        else if (key == "clone_actor_enum") g_config.cloneActorEnum = std::atoi(value.c_str());
        else if (key == "spawn_distance") g_config.spawnDistance = static_cast<float>(std::atof(value.c_str()));
        else if (key == "position_scale") g_config.positionScale = static_cast<float>(std::atof(value.c_str()));
        else if (key == "interpolation") g_config.interpolation = std::max(0.01f, std::min(1.0f, static_cast<float>(std::atof(value.c_str()))));
        else if (key == "tick_ms") g_config.tickMs = static_cast<DWORD>(std::max(25, std::atoi(value.c_str())));
        else if (key == "startup_delay_ms") g_config.startupDelayMs = static_cast<DWORD>(std::max(0, std::atoi(value.c_str())));
        else if (key == "allow_spawn") g_config.allowSpawn = parseBool(value, g_config.allowSpawn);
        else if (key == "relative_remote_coordinates") g_config.relativeRemoteCoordinates = parseBool(value, g_config.relativeRemoteCoordinates);
    }

    ensureDir(rootPath(g_config.bridgeDir));
    ensureDir(rootPath(g_config.runtimeDir));
    appendJsonl("config_loaded", "\"config_path\":\"" + jsonEscape(cfgPath) + "\"");
}

static bool extractNumber(const std::string& text, size_t objectStart, size_t objectEnd, const char* key, float* out) {
    const std::string needle = std::string("\"") + key + "\"";
    size_t pos = text.find(needle, objectStart);
    if (pos == std::string::npos || pos >= objectEnd) return false;
    pos = text.find(':', pos + needle.size());
    if (pos == std::string::npos || pos >= objectEnd) return false;
    ++pos;
    while (pos < objectEnd && std::isspace(static_cast<unsigned char>(text[pos]))) ++pos;
    char* end = nullptr;
    const double value = std::strtod(text.c_str() + pos, &end);
    if (end == text.c_str() + pos) return false;
    *out = static_cast<float>(value);
    return true;
}

static bool extractInt64(const std::string& text, size_t objectStart, size_t objectEnd, const char* key, long long* out) {
    float value = 0.0f;
    if (!extractNumber(text, objectStart, objectEnd, key, &value)) return false;
    *out = static_cast<long long>(value);
    return true;
}

static bool extractString(const std::string& text, size_t objectStart, size_t objectEnd, const char* key, std::string* out) {
    const std::string needle = std::string("\"") + key + "\"";
    size_t pos = text.find(needle, objectStart);
    if (pos == std::string::npos || pos >= objectEnd) return false;
    pos = text.find(':', pos + needle.size());
    if (pos == std::string::npos || pos >= objectEnd) return false;
    pos = text.find('"', pos + 1);
    if (pos == std::string::npos || pos >= objectEnd) return false;
    ++pos;
    std::string value;
    while (pos < objectEnd && pos < text.size()) {
        const char ch = text[pos++];
        if (ch == '"') {
            *out = value;
            return true;
        }
        if (ch == '\\' && pos < objectEnd) {
            const char esc = text[pos++];
            if (esc == 'n') value += '\n';
            else if (esc == 'r') value += '\r';
            else if (esc == 't') value += '\t';
            else value += esc;
        } else {
            value += ch;
        }
    }
    return false;
}

static size_t matchingBrace(const std::string& text, size_t openPos) {
    int depth = 0;
    bool inString = false;
    bool escaped = false;
    for (size_t i = openPos; i < text.size(); ++i) {
        const char ch = text[i];
        if (inString) {
            if (escaped) escaped = false;
            else if (ch == '\\') escaped = true;
            else if (ch == '"') inString = false;
            continue;
        }
        if (ch == '"') inString = true;
        else if (ch == '{') ++depth;
        else if (ch == '}') {
            --depth;
            if (depth == 0) return i;
        }
    }
    return std::string::npos;
}

static bool readRemotePlayer(RemotePlayer* remote, int* remoteCount) {
    std::string text;
    *remoteCount = 0;
    if (!readText(rootPath(g_config.remoteStatePath), &text)) {
        g_lastError = "remote_players_state.json missing";
        return false;
    }

    size_t players = text.find("\"players\"");
    if (players == std::string::npos) {
        g_lastError = "remote_players_state.json has no players object";
        return false;
    }
    size_t containerOpen = text.find('{', players);
    if (containerOpen == std::string::npos) return false;
    size_t containerEnd = matchingBrace(text, containerOpen);
    if (containerEnd == std::string::npos) return false;

    size_t firstObject = text.find('{', containerOpen + 1);
    if (firstObject == std::string::npos || firstObject >= containerEnd) {
        g_lastError = "remote players empty";
        return false;
    }
    size_t objectEnd = matchingBrace(text, firstObject);
    if (objectEnd == std::string::npos || objectEnd > containerEnd) return false;

    *remoteCount = 1;
    remote->valid = true;
    extractString(text, firstObject, objectEnd, "client_id", &remote->clientId);
    if (remote->clientId.empty()) {
        size_t quote1 = text.rfind('"', firstObject - 1);
        size_t quote0 = quote1 == std::string::npos ? std::string::npos : text.rfind('"', quote1 - 1);
        if (quote0 != std::string::npos && quote1 != std::string::npos && quote0 < quote1) {
            remote->clientId = text.substr(quote0 + 1, quote1 - quote0 - 1);
        }
    }
    extractString(text, firstObject, objectEnd, "name", &remote->name);
    extractNumber(text, firstObject, objectEnd, "x", &remote->x);
    extractNumber(text, firstObject, objectEnd, "y", &remote->y);
    extractNumber(text, firstObject, objectEnd, "z", &remote->z);
    extractNumber(text, firstObject, objectEnd, "heading", &remote->heading);
    extractNumber(text, firstObject, objectEnd, "health", &remote->health);
    extractInt64(text, firstObject, objectEnd, "pulse_id", &remote->pulseId);
    return true;
}

static Actor getPlayer(Vector3* pos, float* heading) {
    Actor player = nativeInvoke<Actor>(0xE8CFDD53ULL, 0);
    if (player <= 0 || !nativeInvoke<BOOL>(0xBA6C3E92ULL, player)) {
        return 0;
    }
    nativeInvoke<void>(0x99BD9D6FULL, player, pos);
    *heading = nativeInvoke<float>(0x42DE39F0ULL, player);
    return player;
}

static void writeLocalPlayerState(const Vector3& pos, float heading) {
    std::ostringstream out;
    out << "{\n"
        << "  \"schema\": \"codered.bridge.local_player.v1\",\n"
        << "  \"source\": \"CodeRED_Peer_Clone_Game_Bridge_v0_1\",\n"
        << "  \"updated_ms\": " << nowMs() << ",\n"
        << "  \"x\": " << pos.x << ",\n"
        << "  \"y\": " << pos.y << ",\n"
        << "  \"z\": " << pos.z << ",\n"
        << "  \"heading\": " << heading << ",\n"
        << "  \"health\": 100,\n"
        << "  \"action\": \"in_game_bridge\"\n"
        << "}\n";
    writeText(rootPath(g_config.localStatePath), out.str());
}

static void writeStatus(const char* phase, int remoteCount) {
    std::ostringstream out;
    out << "{\n"
        << "  \"schema\": \"codered.bridge.status.v1\",\n"
        << "  \"source\": \"CodeRED_Peer_Clone_Game_Bridge_v0_1\",\n"
        << "  \"updated_ms\": " << nowMs() << ",\n"
        << "  \"phase\": \"" << jsonEscape(phase) << "\",\n"
        << "  \"mode\": \"" << jsonEscape(g_config.mode) << "\",\n"
        << "  \"remote_count\": " << remoteCount << ",\n"
        << "  \"native_ready\": " << (g_nativeReady ? "true" : "false") << ",\n"
        << "  \"kill_switch\": " << (g_killSwitch ? "true" : "false") << ",\n"
        << "  \"spawned\": " << ((g_clone > 0) ? "true" : "false") << ",\n"
        << "  \"allow_spawn\": " << (g_config.allowSpawn ? "true" : "false") << ",\n"
        << "  \"startup_delay_ms\": " << g_config.startupDelayMs << ",\n"
        << "  \"clone_actor\": " << g_clone << ",\n"
        << "  \"clone_actor_enum\": " << g_config.cloneActorEnum << ",\n"
        << "  \"no_spawn_fallback\": " << (g_noSpawnFallback ? "true" : "false") << ",\n"
        << "  \"last_error\": \"" << jsonEscape(g_lastError) << "\",\n"
        << "  \"cleanup_hotkey\": \"F12\",\n"
        << "  \"kill_switch_hotkey\": \"F11\"\n"
        << "}\n";
    writeText(rootPath(g_config.statusPath), out.str());
}

static Layout bridgeLayout() {
    if (g_layout > 0) return g_layout;
    g_layout = nativeInvoke<Layout>(0x5699DE7EULL, "CodeREDPeerCloneBridge");
    if (g_layout <= 0) {
        g_layout = nativeInvoke<Layout>(0x6CA53214ULL, "CodeREDPeerCloneBridge");
    }
    return g_layout;
}

static bool cloneValid() {
    return g_clone > 0 && nativeInvoke<BOOL>(0xBA6C3E92ULL, g_clone) != 0;
}

static void cleanupClone(const char* reason) {
    if (cloneValid()) {
        nativeInvoke<void>(0x16876A25ULL, g_clone);
        nativeInvoke<void>(0x8BD21869ULL, g_clone);
        appendJsonl("cleanup_clone", "\"reason\":\"" + jsonEscape(reason) + "\",\"actor\":" + std::to_string(g_clone));
    }
    g_clone = 0;
    g_noSpawnFallback = false;
}

static bool spawnCloneNearPlayer(const Vector3& playerPos, float playerHeading) {
    if (g_noSpawnFallback) return false;
    if (cloneValid()) return true;
    if (g_config.cloneActorEnum >= 1177 && g_config.cloneActorEnum <= 1202) {
        g_lastError = "vehicle actor enum blocked";
        g_noSpawnFallback = true;
        appendJsonl("spawn_blocked_vehicle_enum", "\"actor_enum\":" + std::to_string(g_config.cloneActorEnum));
        return false;
    }

    Layout layout = bridgeLayout();
    if (layout <= 0) {
        g_lastError = "could not create bridge layout";
        g_noSpawnFallback = true;
        return false;
    }

    const float radians = playerHeading * (PI / 180.0f);
    Vector2 spawnXY = {
        playerPos.x + std::sin(radians) * g_config.spawnDistance,
        playerPos.y + std::cos(radians) * g_config.spawnDistance
    };
    Vector2 orientXY = {0.0f, 1.0f};
    std::ostringstream name;
    name << "codered_peer_clone_" << ++g_spawnCounter;

    Actor spawned = nativeInvoke<Actor>(0x8D67F397ULL, layout, name.str().c_str(),
                                        g_config.cloneActorEnum, spawnXY, playerPos.z,
                                        orientXY, playerHeading);
    if (spawned <= 0 || !nativeInvoke<BOOL>(0xBA6C3E92ULL, spawned)) {
        g_lastError = "CREATE_ACTOR_IN_LAYOUT returned invalid actor";
        g_noSpawnFallback = true;
        appendJsonl("spawn_failed", "\"actor_enum\":" + std::to_string(g_config.cloneActorEnum));
        return false;
    }

    g_clone = spawned;
    g_clonePos = {spawnXY.x, spawnXY.y, playerPos.z};
    nativeInvoke<void>(0xECE8520BULL, g_clone, playerHeading, TRUE);
    nativeInvoke<void>(0x16876A25ULL, g_clone);
    nativeInvoke<void>(0x6F80965DULL, g_clone, -1.0f, 0, 0);
    appendJsonl("spawned_clone", "\"actor\":" + std::to_string(g_clone) +
                                 ",\"actor_enum\":" + std::to_string(g_config.cloneActorEnum));
    return true;
}

static Vector3 targetFromRemote(const Vector3& playerPos, const RemotePlayer& remote) {
    if (!g_config.relativeRemoteCoordinates) {
        return {remote.x, remote.y, remote.z};
    }
    return {
        playerPos.x + remote.x * g_config.positionScale,
        playerPos.y + remote.y * g_config.positionScale,
        playerPos.z + remote.z * g_config.positionScale
    };
}

static void moveCloneToward(const Vector3& target, float heading) {
    if (!cloneValid()) return;
    g_clonePos.x += (target.x - g_clonePos.x) * g_config.interpolation;
    g_clonePos.y += (target.y - g_clonePos.y) * g_config.interpolation;
    g_clonePos.z += (target.z - g_clonePos.z) * g_config.interpolation;
    nativeInvoke<void>(0x2D54B916ULL, g_clone, &g_clonePos, TRUE, TRUE, TRUE);
    nativeInvoke<void>(0xECE8520BULL, g_clone, heading, TRUE);
}

static void tickBridge() {
    if (g_killSwitch) {
        writeStatus("kill_switch", 0);
        return;
    }

    const ULONGLONG elapsed = GetTickCount64() - g_scriptStartTick;
    if (elapsed < g_config.startupDelayMs) {
        writeStatus("startup_delay", 0);
        return;
    }

    Vector3 playerPos = {};
    float playerHeading = 0.0f;
    Actor player = getPlayer(&playerPos, &playerHeading);
    if (player <= 0) {
        g_lastError = "local player actor unavailable";
        writeStatus("waiting_for_player", 0);
        return;
    }
    writeLocalPlayerState(playerPos, playerHeading);

    RemotePlayer remote = {};
    int remoteCount = 0;
    const bool hasRemote = readRemotePlayer(&remote, &remoteCount);

    if (g_config.mode == "log-only") {
        if (hasRemote) {
            appendJsonl("remote_seen_log_only",
                        "\"client_id\":\"" + jsonEscape(remote.clientId) + "\",\"x\":" + std::to_string(remote.x) +
                        ",\"y\":" + std::to_string(remote.y) + ",\"z\":" + std::to_string(remote.z));
        }
        writeStatus("log_only", remoteCount);
        return;
    }

    if ((g_config.mode == "spawn-test" || g_config.mode == "move-test") && !g_config.allowSpawn) {
        g_lastError = "spawn blocked by config: set allow_spawn=true after launch is stable";
        writeStatus("spawn_blocked_by_config", remoteCount);
        return;
    }

    if (g_config.mode == "spawn-test" || g_config.mode == "move-test") {
        spawnCloneNearPlayer(playerPos, playerHeading);
    }

    if (g_config.mode == "move-test" && hasRemote && cloneValid()) {
        const Vector3 target = targetFromRemote(playerPos, remote);
        moveCloneToward(target, remote.heading);
        appendJsonl("clone_move",
                    "\"client_id\":\"" + jsonEscape(remote.clientId) + "\",\"actor\":" + std::to_string(g_clone) +
                    ",\"target_x\":" + std::to_string(target.x) +
                    ",\"target_y\":" + std::to_string(target.y) +
                    ",\"target_z\":" + std::to_string(target.z));
    }

    writeStatus(g_config.mode.c_str(), remoteCount);
}

static void keyboardHandler(DWORD key, WORD, BYTE, BOOL, BOOL, BOOL, BOOL) {
    if (key == VK_F11) {
        g_killSwitch = !g_killSwitch;
        if (g_killSwitch) cleanupClone("kill_switch");
        appendJsonl("kill_switch_toggled", std::string("\"enabled\":") + (g_killSwitch ? "true" : "false"));
    } else if (key == VK_F12) {
        cleanupClone("hotkey");
        writeStatus("cleanup_hotkey", 0);
    }
}

static void mainScript() {
    loadConfig();
    g_scriptStartTick = GetTickCount64();
    appendJsonl("asi_script_started", "");

    while (InterlockedCompareExchange(&g_stopRequested, 0, 0) == 0) {
        if (!g_nativeReady && !resolveScriptHook()) {
            writeStatus("waiting_for_scripthook", 0);
            waitFrame(1000);
            continue;
        }
        const DWORD now = GetTickCount();
        if (now - g_lastReadTick >= g_config.tickMs) {
            g_lastReadTick = now;
            tickBridge();
        } else if (now - g_lastStatusTick >= 1000) {
            g_lastStatusTick = now;
            writeStatus("heartbeat", 0);
        }
        waitFrame(25);
    }

    cleanupClone("shutdown");
    writeStatus("shutdown", 0);
    appendJsonl("asi_script_stopped", "");
}

static DWORD WINAPI registrationThread(void*) {
    loadConfig();
    for (int i = 0; i < 120 && !resolveScriptHook(); ++i) {
        writeStatus("waiting_for_scripthook", 0);
        Sleep(1000);
    }
    if (!g_nativeReady) {
        appendJsonl("registration_failed", "\"reason\":\"scripthook_exports_unavailable\"");
        return 0;
    }

    if (InterlockedCompareExchange(&g_registered, 1, 0) == 0) {
        g_scriptRegister(g_module, mainScript);
        g_keyboardHandlerRegister(keyboardHandler);
        appendJsonl("registered", "");
        writeStatus("registered", 0);
    }
    return 0;
}

} // namespace codered_peer_clone_bridge

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID) {
    using namespace codered_peer_clone_bridge;
    if (reason == DLL_PROCESS_ATTACH) {
        g_module = module;
        DisableThreadLibraryCalls(module);
        HANDLE thread = CreateThread(nullptr, 0, registrationThread, nullptr, 0, nullptr);
        if (thread) CloseHandle(thread);
    } else if (reason == DLL_PROCESS_DETACH) {
        InterlockedExchange(&g_stopRequested, 1);
        if (g_registered && g_scriptUnregister) {
            g_scriptUnregister(g_module);
        }
        if (g_registered && g_keyboardHandlerUnregister) {
            g_keyboardHandlerUnregister(keyboardHandler);
        }
    }
    return TRUE;
}
