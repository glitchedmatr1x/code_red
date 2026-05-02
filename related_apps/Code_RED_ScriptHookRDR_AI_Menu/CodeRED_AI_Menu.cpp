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

// ScriptHookRDR font/justification ids from sdk/inc/enums.h.
constexpr int FONT_REDEMPTION = 2;
constexpr int JUSTIFY_LEFT = 0;
constexpr float PI = 3.14159265358979323846f;

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
static HMODULE g_module = nullptr;
static volatile LONG g_stopRequested = 0;
static volatile LONG g_registered = 0;
static volatile LONG g_nativeReady = 0;

static bool g_menuOpen = false;
static int g_menuIndex = 0;
static int g_npcIndex = 0;
static bool g_dirtyRoster = true;
static bool g_dirtyActorMap = true;
static bool g_configLoaded = false;
static DWORD g_lastKeyMs = 0;
static Layout g_layout = 0;
static int g_spawnCounter = 0;
static bool g_actorEnumCacheValid = false;
static std::string g_actorEnumCacheRaw;
static int g_actorEnumCacheValue = 0;

static std::string g_rosterPath = "data/codered/npc_roster.txt";
static std::string g_actorEnumMapPath = "data/codered/actor_enum_map.csv";
static std::string g_actionPlanPath = "scratch/codered_ai_action_plan.json";
static std::string g_status = "CodeRED AI Menu ready";

static std::vector<std::string> g_roster;
static std::unordered_map<std::string, int> g_actorEnumMap;
static size_t g_actorEnumRowsLoaded = 0;
static std::vector<Actor> g_spawnedActors;
static std::vector<std::string> g_actions = {
    "spawn_selected_npc_request",
    "follow_player_request",
    "guard_position_request",
    "defend_player_request",
    "attack_nearest_hostile_request",
    "regroup_near_player_request",
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
        if (section != "paths") continue;

        size_t eq = clean.find('=');
        if (eq == std::string::npos) continue;
        std::string key = lowerCopy(trim(clean.substr(0, eq)));
        std::string value = trim(clean.substr(eq + 1));
        if (value.empty()) continue;

        if (key == "roster") {
            g_rosterPath = value;
        } else if (key == "actor_enum_map" || key == "actor_map" ||
                   key == "enum_map") {
            g_actorEnumMapPath = value;
        } else if (key == "action_plan") {
            g_actionPlanPath = value;
        }
    }

    writeLog("Config loaded: roster=%s actor_enum_map=%s action_plan=%s",
             g_rosterPath.c_str(), g_actorEnumMapPath.c_str(),
             g_actionPlanPath.c_str());
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
    }

    g_dirtyActorMap = false;
    writeLog("Actor enum map loaded: rows=%zu aliases=%zu path=%s",
             g_actorEnumRowsLoaded, g_actorEnumMap.size(),
             g_actorEnumMapPath.c_str());
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
    if (g_menuIndex < 0) g_menuIndex = 0;
    if (g_menuIndex >= static_cast<int>(g_actions.size())) g_menuIndex = 0;
    return g_actions[g_menuIndex];
}

static void writeActionPlan();

static std::string displayAction(const std::string& action) {
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

    if (action == "guard_position_request") {
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

    if (action == "attack_nearest_hostile_request") {
        g_status = "Attack target scan not implemented yet";
        writeLog("Action not implemented yet: %s", action.c_str());
        return;
    }
}

static void executeSelectedAction() {
    const std::string action = selectedAction();
    writeActionPlan();

    if (!resolveNativeBridge(false)) {
        g_status = "Queued JSON; native bridge unavailable";
        writeLog("Native bridge unavailable while executing action=%s",
                 action.c_str());
        return;
    }

    if (action == "spawn_selected_npc_request") {
        spawnSelectedNpc();
    } else if (action == "status_request") {
        pruneSpawnedActors();
        const int actorEnum = selectedActorEnum();
        g_status = "Native OK | enum " + std::to_string(actorEnum) +
                   " | spawned " + std::to_string(g_spawnedActors.size());
        writeLog("Status: native=ready selected=%s enum=%d spawned=%zu",
                 selectedNpc().c_str(), actorEnum, g_spawnedActors.size());
    } else {
        commandSpawnedActors(action);
    }
}

static void writeActionPlan() {
    CreateDirectoryA("scratch", nullptr);

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

static void onKey(DWORD key, WORD repeats, BYTE scanCode, BOOL isExtended,
                  BOOL isWithAlt, BOOL wasDownBefore, BOOL isUpNow) {
    (void)repeats;
    (void)scanCode;
    (void)isExtended;
    (void)isWithAlt;

    if (isUpNow) return;
    if (wasDownBefore && key != VK_RETURN) return;

    if (key == VK_F8 || key == VK_INSERT) {
        if (throttleKey()) return;
        g_menuOpen = !g_menuOpen;
        if (g_menuOpen) {
            g_dirtyRoster = true;
            g_dirtyActorMap = true;
        }
        writeLog("Menu toggled: open=%s key=0x%08lX",
                 g_menuOpen ? "true" : "false", key);
        return;
    }

    if (!g_menuOpen) return;
    if (throttleKey()) return;

    if (key == VK_BACK || key == VK_ESCAPE) {
        g_menuOpen = false;
        return;
    }

    if (key == VK_UP) {
        g_menuIndex--;
        if (g_menuIndex < 0) g_menuIndex = static_cast<int>(g_actions.size()) - 1;
        return;
    }

    if (key == VK_DOWN) {
        g_menuIndex++;
        if (g_menuIndex >= static_cast<int>(g_actions.size())) g_menuIndex = 0;
        return;
    }

    if (key == VK_LEFT) {
        ensureDefaultRoster();
        g_npcIndex--;
        if (g_npcIndex < 0) g_npcIndex = static_cast<int>(g_roster.size()) - 1;
        return;
    }

    if (key == VK_RIGHT) {
        ensureDefaultRoster();
        g_npcIndex++;
        if (g_npcIndex >= static_cast<int>(g_roster.size())) g_npcIndex = 0;
        return;
    }

    if (key == VK_RETURN) {
        executeSelectedAction();
        return;
    }

    if (key == VK_F5) {
        g_dirtyRoster = true;
        g_dirtyActorMap = true;
        g_status = "Reload requested";
        writeLog("Manual reload requested");
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

    std::string footer = "F8/INSERT close | UP/DOWN action | LEFT/RIGHT roster | ENTER run | BACK/ESC close";
    drawTextSafe(left + 0.020f, top + panelH - 0.026f, footer.c_str(), 235, 235, 235, 235, FONT_REDEMPTION, 0.015f, JUSTIFY_LEFT);
    if (!g_status.empty()) {
        drawTextSafe(left + 0.020f, top + panelH - 0.005f, g_status.c_str(), 255, 140, 140, 235, FONT_REDEMPTION, 0.014f, JUSTIFY_LEFT);
    }
}
// CodeRED compact scrolling menu layout pass v2 no-std-minmax



static void mainLoop() {
    while (true) {
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
