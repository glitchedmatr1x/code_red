// CodeRED_DualGunLab.cpp
// ScriptHookRDR dual-pistol left-hand bypass lab.
//
// Goal:
//   Keep the normal right-hand weapon path native, then add a left-hand pistol
//   visual/fire layer through ScriptHook. The left-hand layer is intentionally
//   data-driven: it reads native hashes from CodeRED_DualGunLab.ini and refuses
//   to call unknown attach/fire natives.
//
// Controls:
//   F9  - toggle overlay
//   F10 - toggle DualGunLab enabled
//   F11 - request/test left-fire bypass
//   F12 - save current preset/state JSON
//   Numpad 4/6, 8/2, 7/9 - nudge XYZ offset
//   Numpad 1/3, 5/0, +/- - nudge pitch/yaw/roll

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <algorithm>
#include <cerrno>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <fstream>
#include <sstream>
#include <string>
#include <type_traits>
#include <vector>

namespace codered_dualgun {

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

using Actor = int;
using Layout = int;

struct Vector2 { float x; float y; };
struct Vector3 { float x; float y; float z; };

static HMODULE g_module = nullptr;
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
static volatile LONG g_stopRequested = 0;
static volatile LONG g_registered = 0;
static volatile LONG g_nativeReady = 0;

constexpr int FONT_REDEMPTION = 2;
constexpr int JUSTIFY_LEFT = 0;
constexpr float PI = 3.14159265358979323846f;

struct NativeConfig {
    // Proven from the current CodeRED AI menu.
    unsigned long long getPlayerActor = 0xE8CFDD53;
    unsigned long long isActorValid = 0xBA6C3E92;
    unsigned long long getPosition = 0x99BD9D6F;
    unsigned long long getHeading = 0x42DE39F0;

    // These must be resolved from the ScriptHookRDR SDK/natives before live use.
    // The lab will not call them while set to 0.
    unsigned long long createObjectOrProp = 0;
    unsigned long long deleteObjectOrProp = 0;
    unsigned long long attachObjectToActorLocator = 0;
    unsigned long long detachObject = 0;
    unsigned long long fireProjectileOrBullet = 0;
    unsigned long long damageActor = 0;
    unsigned long long raycastOrGetAimHit = 0;
};

struct LabConfig {
    bool autoEnable = false;
    std::string attachLocator = "smic_player_default_hand_1_rm";
    std::string fallbackLocator = "smic_player_default_hand_1";
    std::string leftPropModel = "pistol_left_hand_prop_candidate";
    float offset[3] = { 0.030f, 0.018f, -0.055f };
    float eulers[3] = { -6.0f, 0.0f, 88.0f };
    float muzzleOffset[3] = { 0.0f, 0.030f, -0.100f };
    float nudgeStep = 0.005f;
    bool useSimulatedFire = true;
    bool visualAttachRequiredForFire = false;
};

struct LabState {
    bool overlay = true;
    bool enabled = false;
    bool leftVisualAttached = false;
    int leftProp = 0;
    int fireCounter = 0;
    DWORD lastKeyMs = 0;
    std::string status = "DualGunLab ready";
};

static NativeConfig g_natives;
static LabConfig g_config;
static LabState g_state;

static std::string exeDir() {
    char exePath[MAX_PATH] = {};
    DWORD len = GetModuleFileNameA(nullptr, exePath, MAX_PATH);
    if (len == 0 || len >= MAX_PATH) return ".";
    std::string path(exePath);
    size_t slash = path.find_last_of("\\/");
    if (slash == std::string::npos) return ".";
    return path.substr(0, slash);
}

static std::string pathBesideExe(const char* name) {
    return exeDir() + "\\" + name;
}

static void ensureScratchDir() {
    CreateDirectoryA(pathBesideExe("scratch").c_str(), nullptr);
}

static void writeLog(const char* format, ...) {
    char message[1600] = {};
    va_list args;
    va_start(args, format);
    vsnprintf_s(message, sizeof(message), _TRUNCATE, format, args);
    va_end(args);

    SYSTEMTIME now = {};
    GetLocalTime(&now);
    char line[2048] = {};
    snprintf(line, sizeof(line), "[%04u-%02u-%02u %02u:%02u:%02u] %s\r\n",
        now.wYear, now.wMonth, now.wDay, now.wHour, now.wMinute, now.wSecond, message);

    std::string path = pathBesideExe("CodeRED_DualGunLab.log");
    HANDLE file = CreateFileA(path.c_str(), FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE,
                              nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) return;
    DWORD written = 0;
    WriteFile(file, line, static_cast<DWORD>(strlen(line)), &written, nullptr);
    CloseHandle(file);
}

static std::string trim(const std::string& s) {
    size_t a = s.find_first_not_of(" \t\r\n");
    if (a == std::string::npos) return "";
    size_t b = s.find_last_not_of(" \t\r\n");
    return s.substr(a, b - a + 1);
}

static std::string lowerCopy(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(), [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    return s;
}

static std::string stripComment(const std::string& s) {
    bool q = false;
    for (size_t i = 0; i < s.size(); ++i) {
        if (s[i] == '"') q = !q;
        if (!q && (s[i] == '#' || s[i] == ';')) return s.substr(0, i);
    }
    return s;
}

static bool parseBool(const std::string& value, bool def) {
    std::string v = lowerCopy(trim(value));
    if (v == "1" || v == "true" || v == "yes" || v == "on") return true;
    if (v == "0" || v == "false" || v == "no" || v == "off") return false;
    return def;
}

static unsigned long long parseHash(const std::string& value, unsigned long long def = 0) {
    std::string text = trim(value);
    if (text.empty()) return def;
    errno = 0;
    char* end = nullptr;
    unsigned long long out = std::strtoull(text.c_str(), &end, 0);
    if (errno != 0 || end == text.c_str()) return def;
    return out;
}

static float parseFloat(const std::string& value, float def) {
    std::string text = trim(value);
    if (text.empty()) return def;
    errno = 0;
    char* end = nullptr;
    float out = std::strtof(text.c_str(), &end);
    if (errno != 0 || end == text.c_str()) return def;
    return out;
}

static void loadConfig() {
    std::ifstream file(pathBesideExe("CodeRED_DualGunLab.ini"));
    if (!file) {
        writeLog("No CodeRED_DualGunLab.ini found; using safe defaults.");
        return;
    }
    std::string section;
    std::string line;
    while (std::getline(file, line)) {
        std::string clean = trim(stripComment(line));
        if (clean.empty()) continue;
        if (clean.front() == '[' && clean.back() == ']') {
            section = lowerCopy(trim(clean.substr(1, clean.size() - 2)));
            continue;
        }
        size_t eq = clean.find('=');
        if (eq == std::string::npos) continue;
        std::string key = lowerCopy(trim(clean.substr(0, eq)));
        std::string value = trim(clean.substr(eq + 1));

        if (section == "natives") {
            if (key == "getplayeractor") g_natives.getPlayerActor = parseHash(value, g_natives.getPlayerActor);
            else if (key == "isactorvalid") g_natives.isActorValid = parseHash(value, g_natives.isActorValid);
            else if (key == "getposition") g_natives.getPosition = parseHash(value, g_natives.getPosition);
            else if (key == "getheading") g_natives.getHeading = parseHash(value, g_natives.getHeading);
            else if (key == "createobjectorprop") g_natives.createObjectOrProp = parseHash(value);
            else if (key == "deleteobjectorprop") g_natives.deleteObjectOrProp = parseHash(value);
            else if (key == "attachobjecttoactorlocator") g_natives.attachObjectToActorLocator = parseHash(value);
            else if (key == "detachobject") g_natives.detachObject = parseHash(value);
            else if (key == "fireprojectileorbullet") g_natives.fireProjectileOrBullet = parseHash(value);
            else if (key == "damageactor") g_natives.damageActor = parseHash(value);
            else if (key == "raycastorgetaimhit") g_natives.raycastOrGetAimHit = parseHash(value);
        } else if (section == "dualgun") {
            if (key == "autoenable") g_config.autoEnable = parseBool(value, g_config.autoEnable);
            else if (key == "attachlocator") g_config.attachLocator = value;
            else if (key == "fallbacklocator") g_config.fallbackLocator = value;
            else if (key == "leftpropmodel") g_config.leftPropModel = value;
            else if (key == "offsetx") g_config.offset[0] = parseFloat(value, g_config.offset[0]);
            else if (key == "offsety") g_config.offset[1] = parseFloat(value, g_config.offset[1]);
            else if (key == "offsetz") g_config.offset[2] = parseFloat(value, g_config.offset[2]);
            else if (key == "pitch") g_config.eulers[0] = parseFloat(value, g_config.eulers[0]);
            else if (key == "yaw") g_config.eulers[1] = parseFloat(value, g_config.eulers[1]);
            else if (key == "roll") g_config.eulers[2] = parseFloat(value, g_config.eulers[2]);
            else if (key == "muzzlex") g_config.muzzleOffset[0] = parseFloat(value, g_config.muzzleOffset[0]);
            else if (key == "muzzley") g_config.muzzleOffset[1] = parseFloat(value, g_config.muzzleOffset[1]);
            else if (key == "muzzlez") g_config.muzzleOffset[2] = parseFloat(value, g_config.muzzleOffset[2]);
            else if (key == "nudgestep") g_config.nudgeStep = parseFloat(value, g_config.nudgeStep);
            else if (key == "usesimulatedfire") g_config.useSimulatedFire = parseBool(value, g_config.useSimulatedFire);
            else if (key == "visualattachrequiredfordire") g_config.visualAttachRequiredForFire = parseBool(value, g_config.visualAttachRequiredForFire);
            else if (key == "visualattachrequiredfire") g_config.visualAttachRequiredForFire = parseBool(value, g_config.visualAttachRequiredForFire);
        }
    }
    g_state.enabled = g_config.autoEnable;
    writeLog("Config loaded: locator=%s fallback=%s prop=%s attachHash=0x%llX fireHash=0x%llX",
        g_config.attachLocator.c_str(), g_config.fallbackLocator.c_str(), g_config.leftPropModel.c_str(),
        g_natives.attachObjectToActorLocator, g_natives.fireProjectileOrBullet);
}

static FARPROC resolveExport(const char* name, const char* decorated = nullptr) {
    if (!g_scriptHook) return nullptr;
    FARPROC proc = GetProcAddress(g_scriptHook, name);
    if (!proc && decorated) proc = GetProcAddress(g_scriptHook, decorated);
    return proc;
}

static bool resolveScriptHook() {
    if (!g_scriptHook) {
        g_scriptHook = GetModuleHandleA("ScriptHookRDR.dll");
        if (!g_scriptHook) g_scriptHook = LoadLibraryA("ScriptHookRDR.dll");
    }
    if (!g_scriptHook) return false;

    g_scriptRegister = reinterpret_cast<ScriptRegisterFn>(resolveExport("scriptRegister", "?scriptRegister@@YAXPEAUHINSTANCE__@@P6AXXZ@Z"));
    g_scriptUnregister = reinterpret_cast<ScriptUnregisterFn>(resolveExport("scriptUnregister", "?scriptUnregister@@YAXPEAUHINSTANCE__@@@Z"));
    g_keyboardHandlerRegister = reinterpret_cast<KeyboardHandlerRegisterFn>(resolveExport("keyboardHandlerRegister", "?keyboardHandlerRegister@@YAXP6AXKGEHHHH@Z@Z"));
    g_keyboardHandlerUnregister = reinterpret_cast<KeyboardHandlerUnregisterFn>(resolveExport("keyboardHandlerUnregister", "?keyboardHandlerUnregister@@YAXP6AXKGEHHHH@Z@Z"));
    g_scriptWait = reinterpret_cast<ScriptWaitFn>(resolveExport("scriptWait", "?scriptWait@@YAXK@Z"));
    g_drawRect = reinterpret_cast<DrawRectFn>(resolveExport("drawRect", "?drawRect@@YAXMMMMHHHHM@Z"));
    g_drawText = reinterpret_cast<DrawTextFn>(resolveExport("drawText", "?drawText@@YAXMMPEBDHHHHHMH@Z"));
    g_nativeInit = reinterpret_cast<NativeInitFn>(resolveExport("nativeInit", "?nativeInit@@YAX_K@Z"));
    g_nativePush64 = reinterpret_cast<NativePush64Fn>(resolveExport("nativePush64", "?nativePush64@@YAX_K@Z"));
    g_nativeCall = reinterpret_cast<NativeCallFn>(resolveExport("nativeCall", "?nativeCall@@YAPEA_KXZ"));

    const bool coreReady = g_scriptRegister && g_scriptUnregister && g_keyboardHandlerRegister &&
                           g_keyboardHandlerUnregister && g_scriptWait;
    const bool nativeReady = g_nativeInit && g_nativePush64 && g_nativeCall;
    InterlockedExchange(&g_nativeReady, nativeReady ? 1 : 0);
    return coreReady;
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

static bool nativeReady() {
    return InterlockedCompareExchange(&g_nativeReady, 0, 0) != 0 && g_nativeInit && g_nativePush64 && g_nativeCall;
}

static void waitFrame(DWORD ms) {
    if (g_scriptWait) g_scriptWait(ms); else Sleep(ms);
}

static void drawRectSafe(float x, float y, float w, float h, int r, int g, int b, int a) {
    if (g_drawRect) g_drawRect(x, y, w, h, r, g, b, a, 0.0f);
}

static void drawTextSafe(float x, float y, const char* text, int r, int g, int b, int a, float size = 0.28f) {
    if (g_drawText) g_drawText(x, y, text, r, g, b, a, FONT_REDEMPTION, size, JUSTIFY_LEFT);
}

static Actor playerActor() {
    if (!nativeReady() || !g_natives.getPlayerActor || !g_natives.isActorValid) return 0;
    Actor player = nativeInvoke<Actor>(g_natives.getPlayerActor, 0);
    if (player <= 0 || !nativeInvoke<BOOL>(g_natives.isActorValid, player)) return 0;
    return player;
}

static Vector3 playerPosition(Actor player) {
    Vector3 pos = {};
    if (nativeReady() && player > 0 && g_natives.getPosition) {
        nativeInvoke<void>(g_natives.getPosition, player, &pos);
    }
    return pos;
}

static float playerHeading(Actor player) {
    if (nativeReady() && player > 0 && g_natives.getHeading) return nativeInvoke<float>(g_natives.getHeading, player);
    return 0.0f;
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

static void saveStateJson(const char* reason) {
    ensureScratchDir();
    Actor p = playerActor();
    Vector3 pos = playerPosition(p);
    float heading = playerHeading(p);

    std::ostringstream js;
    js << "{\n";
    js << "  \"schema\": \"codered.dualgunlab.runtime_state.v1\",\n";
    js << "  \"reason\": \"" << jsonEscape(reason ? reason : "state") << "\",\n";
    js << "  \"enabled\": " << (g_state.enabled ? "true" : "false") << ",\n";
    js << "  \"left_visual_attached\": " << (g_state.leftVisualAttached ? "true" : "false") << ",\n";
    js << "  \"left_prop_handle\": " << g_state.leftProp << ",\n";
    js << "  \"fire_counter\": " << g_state.fireCounter << ",\n";
    js << "  \"attach_locator\": \"" << jsonEscape(g_config.attachLocator) << "\",\n";
    js << "  \"fallback_locator\": \"" << jsonEscape(g_config.fallbackLocator) << "\",\n";
    js << "  \"left_prop_model\": \"" << jsonEscape(g_config.leftPropModel) << "\",\n";
    js << "  \"offset\": [" << g_config.offset[0] << ", " << g_config.offset[1] << ", " << g_config.offset[2] << "],\n";
    js << "  \"eulers\": [" << g_config.eulers[0] << ", " << g_config.eulers[1] << ", " << g_config.eulers[2] << "],\n";
    js << "  \"muzzle_offset\": [" << g_config.muzzleOffset[0] << ", " << g_config.muzzleOffset[1] << ", " << g_config.muzzleOffset[2] << "],\n";
    js << "  \"player\": {\"handle\": " << p << ", \"x\": " << pos.x << ", \"y\": " << pos.y << ", \"z\": " << pos.z << ", \"heading\": " << heading << "},\n";
    js << "  \"natives_configured\": {\n";
    js << "    \"create_object_or_prop\": " << (g_natives.createObjectOrProp ? "true" : "false") << ",\n";
    js << "    \"attach_object_to_actor_locator\": " << (g_natives.attachObjectToActorLocator ? "true" : "false") << ",\n";
    js << "    \"fire_projectile_or_bullet\": " << (g_natives.fireProjectileOrBullet ? "true" : "false") << ",\n";
    js << "    \"damage_actor\": " << (g_natives.damageActor ? "true" : "false") << "\n";
    js << "  },\n";
    js << "  \"status\": \"" << jsonEscape(g_state.status) << "\"\n";
    js << "}\n";

    std::ofstream out(pathBesideExe("scratch\\codered_dualgunlab_state.json"));
    out << js.str();
    writeLog("State saved: %s", reason ? reason : "state");
}

static bool ensureLeftVisual() {
    if (!nativeReady()) {
        g_state.status = "Native bridge not ready";
        writeLog("DualGun attach skipped: native bridge not ready");
        return false;
    }
    Actor player = playerActor();
    if (player <= 0) {
        g_state.status = "Player actor not ready";
        writeLog("DualGun attach skipped: player actor invalid");
        return false;
    }
    if (!g_natives.createObjectOrProp || !g_natives.attachObjectToActorLocator) {
        g_state.status = "Attach natives not configured; using left-fire bypass only";
        writeLog("Attach skipped: createObjectOrProp=0x%llX attachObjectToActorLocator=0x%llX",
            g_natives.createObjectOrProp, g_natives.attachObjectToActorLocator);
        saveStateJson("attach_native_missing");
        return false;
    }

    // Intentionally not called until the exact ScriptHookRDR native signatures are confirmed.
    // When confirmed, wire createObjectOrProp and attachObjectToActorLocator here.
    // This prevents the enum-style crash loop that happened with unverified actor spawns.
    g_state.status = "Attach natives configured, but signature gate is still locked";
    writeLog("Attach signature gate locked. Fill the confirmed signatures before live attach.");
    saveStateJson("attach_signature_gate_locked");
    return false;
}

static void detachLeftVisual() {
    if (!g_state.leftVisualAttached) return;
    if (nativeReady() && g_natives.detachObject && g_state.leftProp > 0) {
        // Signature gate: leave disabled until confirmed.
    }
    g_state.leftVisualAttached = false;
    g_state.leftProp = 0;
    g_state.status = "Left pistol visual detached";
    writeLog("Left visual detached");
    saveStateJson("detach_left_visual");
}

static bool leftFireBypass() {
    if (!g_state.enabled) {
        g_state.status = "DualGunLab disabled";
        return false;
    }
    if (g_config.visualAttachRequiredForFire && !g_state.leftVisualAttached) {
        g_state.status = "Left visual required before fire";
        return false;
    }
    Actor player = playerActor();
    if (player <= 0) {
        g_state.status = "Player actor not ready";
        return false;
    }
    Vector3 pos = playerPosition(player);
    float heading = playerHeading(player);
    float rad = heading * (PI / 180.0f);
    Vector3 muzzle = {
        pos.x + std::sin(rad) * 0.50f + g_config.muzzleOffset[0],
        pos.y + std::cos(rad) * 0.50f + g_config.muzzleOffset[1],
        pos.z + 1.35f + g_config.muzzleOffset[2]
    };
    Vector3 target = {
        muzzle.x + std::sin(rad) * 90.0f,
        muzzle.y + std::cos(rad) * 90.0f,
        muzzle.z
    };

    ++g_state.fireCounter;

    if (nativeReady() && g_config.useSimulatedFire && g_natives.fireProjectileOrBullet) {
        // Signature gate: leave disabled until the SDK native signature is confirmed.
        g_state.status = "Left fire native configured; signature gate locked";
        writeLog("Left fire signature gate locked. muzzle=(%.3f %.3f %.3f) target=(%.3f %.3f %.3f)",
                 muzzle.x, muzzle.y, muzzle.z, target.x, target.y, target.z);
    } else {
        g_state.status = "Left fire bypass logged; configure projectile/raycast native for damage";
        writeLog("Left fire bypass pulse #%d muzzle=(%.3f %.3f %.3f) target=(%.3f %.3f %.3f)",
                 g_state.fireCounter, muzzle.x, muzzle.y, muzzle.z, target.x, target.y, target.z);
    }
    saveStateJson("left_fire_bypass");
    return true;
}

static void toggleEnabled() {
    g_state.enabled = !g_state.enabled;
    if (g_state.enabled) {
        g_state.status = "DualGunLab enabled: right hand native, left hand bypass armed";
        ensureLeftVisual();
    } else {
        detachLeftVisual();
        g_state.status = "DualGunLab disabled";
    }
    writeLog("DualGunLab enabled=%d", g_state.enabled ? 1 : 0);
    saveStateJson("toggle_enabled");
}

static void nudge(float* v, float delta, const char* label) {
    *v += delta;
    char status[256] = {};
    snprintf(status, sizeof(status), "Nudged %s by %.4f", label, delta);
    g_state.status = status;
    saveStateJson("nudge_offset");
}

static bool canAcceptKey() {
    DWORD now = GetTickCount();
    if (now - g_state.lastKeyMs < 120) return false;
    g_state.lastKeyMs = now;
    return true;
}

static void keyboardHandler(DWORD key, WORD, BYTE, BOOL, BOOL, BOOL, BOOL up) {
    if (up || !canAcceptKey()) return;
    switch (key) {
        case VK_F9: g_state.overlay = !g_state.overlay; saveStateJson("toggle_overlay"); break;
        case VK_F10: toggleEnabled(); break;
        case VK_F11: leftFireBypass(); break;
        case VK_F12: saveStateJson("manual_save"); break;
        case VK_NUMPAD4: nudge(&g_config.offset[0], -g_config.nudgeStep, "offsetX"); break;
        case VK_NUMPAD6: nudge(&g_config.offset[0],  g_config.nudgeStep, "offsetX"); break;
        case VK_NUMPAD2: nudge(&g_config.offset[1], -g_config.nudgeStep, "offsetY"); break;
        case VK_NUMPAD8: nudge(&g_config.offset[1],  g_config.nudgeStep, "offsetY"); break;
        case VK_NUMPAD7: nudge(&g_config.offset[2], -g_config.nudgeStep, "offsetZ"); break;
        case VK_NUMPAD9: nudge(&g_config.offset[2],  g_config.nudgeStep, "offsetZ"); break;
        case VK_NUMPAD1: nudge(&g_config.eulers[0], -1.0f, "pitch"); break;
        case VK_NUMPAD3: nudge(&g_config.eulers[0],  1.0f, "pitch"); break;
        case VK_NUMPAD5: nudge(&g_config.eulers[1], -1.0f, "yaw"); break;
        case VK_NUMPAD0: nudge(&g_config.eulers[1],  1.0f, "yaw"); break;
        case VK_SUBTRACT: nudge(&g_config.eulers[2], -1.0f, "roll"); break;
        case VK_ADD: nudge(&g_config.eulers[2],  1.0f, "roll"); break;
        default: break;
    }
}

static void drawOverlay() {
    if (!g_state.overlay || !g_drawText) return;
    drawRectSafe(0.50f, 0.115f, 0.54f, 0.155f, 10, 0, 0, 150);
    drawTextSafe(0.245f, 0.050f, "CodeRED DualGunLab - Left Hand Bypass", 255, 55, 55, 255, 0.31f);
    char line[512] = {};
    snprintf(line, sizeof(line), "F10 enabled=%s | visual=%s | F11 left fire | locator=%s",
             g_state.enabled ? "YES" : "NO", g_state.leftVisualAttached ? "ATTACHED" : "BYPASS", g_config.attachLocator.c_str());
    drawTextSafe(0.245f, 0.078f, line, 255, 255, 255, 235);
    snprintf(line, sizeof(line), "offset %.3f %.3f %.3f | rot %.1f %.1f %.1f | shots %d",
             g_config.offset[0], g_config.offset[1], g_config.offset[2],
             g_config.eulers[0], g_config.eulers[1], g_config.eulers[2], g_state.fireCounter);
    drawTextSafe(0.245f, 0.102f, line, 230, 230, 230, 235);
    drawTextSafe(0.245f, 0.126f, g_state.status.c_str(), 255, 210, 120, 235);
}

static void scriptMain() {
    writeLog("DualGunLab script thread started");
    saveStateJson("startup");
    while (InterlockedCompareExchange(&g_stopRequested, 0, 0) == 0) {
        drawOverlay();
        waitFrame(0);
    }
    detachLeftVisual();
    saveStateJson("shutdown");
    writeLog("DualGunLab script thread stopped");
}

static void onAttach() {
    loadConfig();
    if (!resolveScriptHook()) {
        writeLog("ScriptHookRDR exports were not ready at attach time");
        return;
    }
    if (InterlockedExchange(&g_registered, 1) == 0) {
        g_keyboardHandlerRegister(keyboardHandler);
        g_scriptRegister(g_module, scriptMain);
        writeLog("DualGunLab registered with ScriptHookRDR");
    }
}

static void onDetach() {
    InterlockedExchange(&g_stopRequested, 1);
    if (InterlockedExchange(&g_registered, 0) != 0) {
        if (g_scriptUnregister) g_scriptUnregister(g_module);
        if (g_keyboardHandlerUnregister) g_keyboardHandlerUnregister(keyboardHandler);
    }
    writeLog("DualGunLab detached");
}

} // namespace codered_dualgun

BOOL APIENTRY DllMain(HMODULE hModule, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        codered_dualgun::g_module = hModule;
        DisableThreadLibraryCalls(hModule);
        codered_dualgun::onAttach();
    } else if (reason == DLL_PROCESS_DETACH) {
        codered_dualgun::onDetach();
    }
    return TRUE;
}
