#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>

#include <algorithm>
#include <atomic>
#include <cctype>
#include <cmath>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

#include "main.h"
#include "natives.h"

namespace {

constexpr int kMaxWorldActors = 512;
constexpr DWORD kDebounceMs = 450;

HMODULE g_module = nullptr;
std::atomic<bool> g_ready{false};
std::atomic<bool> g_requestSnapshot{false};
std::atomic<bool> g_requestSquadAllies{false};
std::atomic<bool> g_requestResetSquad{false};
DWORD g_lastF6 = 0;
DWORD g_lastF7 = 0;
DWORD g_lastF8 = 0;

Layout g_layout = 0;
int g_squad = 0;

enum class F7Mode {
    SnapshotOnly,
    CreateSquadOnly,
    JoinPlayerOnly,
    JoinAlliesNoGoal,
    JoinAlliesFollowGoal
};

struct Config {
    bool enabled = true;
    int startupDelayMs = 15000;
    float radius = 45.0f;
    int maxActors = 256;
    F7Mode f7Mode = F7Mode::SnapshotOnly;
    bool includeSameFaction = true;
    bool includeFactionAllowlist = true;
    bool setSquadFactionToPlayerFaction = true;
    bool setActorCompanionFlag = false;
    bool addFollowGoal = true;
    bool clearGoalsBeforeFollowGoal = true;
    bool makeSquadEmptyBeforeJoin = true;
    bool joinPlayerFirst = true;
    std::vector<int> allyFactions{20};
};

Config g_config;

std::string trim(const std::string& value) {
    const char* whitespace = " \t\r\n";
    const auto start = value.find_first_not_of(whitespace);
    if (start == std::string::npos) {
        return "";
    }
    const auto end = value.find_last_not_of(whitespace);
    return value.substr(start, end - start + 1);
}

bool parseBool(const std::string& value, bool fallback) {
    std::string v = trim(value);
    std::transform(v.begin(), v.end(), v.begin(), [](unsigned char c) {
        return static_cast<char>(std::tolower(c));
    });
    if (v == "1" || v == "true" || v == "yes" || v == "on") {
        return true;
    }
    if (v == "0" || v == "false" || v == "no" || v == "off") {
        return false;
    }
    return fallback;
}

F7Mode parseF7Mode(const std::string& value, F7Mode fallback) {
    std::string v = trim(value);
    std::transform(v.begin(), v.end(), v.begin(), [](unsigned char c) {
        return static_cast<char>(std::tolower(c));
    });
    if (v == "snapshot_only" || v == "scan_only") {
        return F7Mode::SnapshotOnly;
    }
    if (v == "create_squad_only") {
        return F7Mode::CreateSquadOnly;
    }
    if (v == "join_player_only") {
        return F7Mode::JoinPlayerOnly;
    }
    if (v == "join_allies_no_goal") {
        return F7Mode::JoinAlliesNoGoal;
    }
    if (v == "join_allies_follow_goal" || v == "full") {
        return F7Mode::JoinAlliesFollowGoal;
    }
    return fallback;
}

const char* f7ModeName(F7Mode mode) {
    switch (mode) {
        case F7Mode::SnapshotOnly:
            return "snapshot_only";
        case F7Mode::CreateSquadOnly:
            return "create_squad_only";
        case F7Mode::JoinPlayerOnly:
            return "join_player_only";
        case F7Mode::JoinAlliesNoGoal:
            return "join_allies_no_goal";
        case F7Mode::JoinAlliesFollowGoal:
            return "join_allies_follow_goal";
    }
    return "unknown";
}

std::vector<int> parseIntList(const std::string& value) {
    std::vector<int> out;
    std::stringstream ss(value);
    std::string item;
    while (std::getline(ss, item, ',')) {
        item = trim(item);
        if (item.empty()) {
            continue;
        }
        char* end = nullptr;
        const long parsed = std::strtol(item.c_str(), &end, 10);
        if (end && *end == '\0') {
            out.push_back(static_cast<int>(parsed));
        }
    }
    return out;
}

bool ensureDirectory(const char* path) {
    if (CreateDirectoryA(path, nullptr) || GetLastError() == ERROR_ALREADY_EXISTS) {
        return true;
    }
    return false;
}

bool safeCreateDirectory(const char* path) {
    __try {
        return ensureDirectory(path);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

void logLine(const char* fmt, ...) {
    safeCreateDirectory("logs");

    SYSTEMTIME st{};
    GetLocalTime(&st);

    FILE* file = nullptr;
    fopen_s(&file, "logs\\codered_allied_squad_trainer.log", "a");
    if (!file) {
        return;
    }

    std::fprintf(
        file,
        "[%04u-%02u-%02u %02u:%02u:%02u.%03u] ",
        st.wYear,
        st.wMonth,
        st.wDay,
        st.wHour,
        st.wMinute,
        st.wSecond,
        st.wMilliseconds);

    va_list args;
    va_start(args, fmt);
    std::vfprintf(file, fmt, args);
    va_end(args);
    std::fprintf(file, "\n");
    std::fclose(file);
}

bool safeSquadIsValid(int squad, BOOL& valid, DWORD& exceptionCode) {
    exceptionCode = 0;
    valid = FALSE;
    __try {
        valid = squad ? SQUADS::SQUAD_IS_VALID(squad) : FALSE;
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        exceptionCode = GetExceptionCode();
        return false;
    }
}

bool safeCreateLayout(Layout& layout, DWORD& exceptionCode) {
    exceptionCode = 0;
    layout = 0;
    __try {
        layout = OBJECT::FIND_NAMED_LAYOUT("CodeRED_AlliedSquadTrainer");
        if (!layout) {
            layout = OBJECT::CREATE_LAYOUT("CodeRED_AlliedSquadTrainer");
        }
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        exceptionCode = GetExceptionCode();
        return false;
    }
}

bool safeCreateSquad(Layout layout, int& squad, DWORD& exceptionCode) {
    exceptionCode = 0;
    squad = 0;
    __try {
        squad = OBJECT::CREATE_SQUAD_IN_LAYOUT(layout, "CodeRED_AlliedSquad");
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        exceptionCode = GetExceptionCode();
        return false;
    }
}

bool safeSquadMakeEmpty(int squad, DWORD& exceptionCode) {
    exceptionCode = 0;
    __try {
        SQUADS::SQUAD_MAKE_EMPTY(squad);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        exceptionCode = GetExceptionCode();
        return false;
    }
}

bool safeSquadSetFaction(int squad, int faction, DWORD& exceptionCode) {
    exceptionCode = 0;
    __try {
        SQUADS::SQUAD_SET_FACTION(squad, faction);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        exceptionCode = GetExceptionCode();
        return false;
    }
}

bool safeSquadJoin(int squad, Actor actor, DWORD& exceptionCode) {
    exceptionCode = 0;
    __try {
        SQUADS::SQUAD_JOIN(squad, actor);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        exceptionCode = GetExceptionCode();
        return false;
    }
}

bool safeSquadGoalsClear(int squad, DWORD& exceptionCode) {
    exceptionCode = 0;
    __try {
        SQUADS::SQUAD_GOALS_CLEAR(squad);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        exceptionCode = GetExceptionCode();
        return false;
    }
}

bool safeSquadFollowGoal(int squad, Actor player, int& goal, DWORD& exceptionCode) {
    exceptionCode = 0;
    goal = 0;
    __try {
        goal = SQUADS::SQUAD_GOAL_ADD_FOLLOW_OBJECT_IN_FORMATION(squad, player, 0, 0, 0, 0);
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        exceptionCode = GetExceptionCode();
        return false;
    }
}

bool safeSquadGetSize(int squad, int& size, DWORD& exceptionCode) {
    exceptionCode = 0;
    size = 0;
    __try {
        size = squad ? SQUADS::SQUAD_GET_SIZE(squad) : 0;
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        exceptionCode = GetExceptionCode();
        return false;
    }
}

bool loadConfig() {
    g_config = Config{};
    ensureDirectory("data");
    ensureDirectory("data\\codered");

    std::ifstream in("data\\codered\\allied_squad_trainer.ini");
    if (!in) {
        logLine("load_config: default config used; data\\codered\\allied_squad_trainer.ini not found");
        return false;
    }

    std::string line;
    while (std::getline(in, line)) {
        const auto comment = line.find_first_of("#;");
        if (comment != std::string::npos) {
            line = line.substr(0, comment);
        }
        const auto eq = line.find('=');
        if (eq == std::string::npos) {
            continue;
        }
        const std::string key = trim(line.substr(0, eq));
        const std::string value = trim(line.substr(eq + 1));
        if (key == "enabled") {
            g_config.enabled = parseBool(value, g_config.enabled);
        } else if (key == "startup_delay_ms") {
            g_config.startupDelayMs = std::clamp(std::atoi(value.c_str()), 0, 60000);
        } else if (key == "radius") {
            g_config.radius = std::max(1.0f, std::strtof(value.c_str(), nullptr));
        } else if (key == "max_actors") {
            g_config.maxActors = std::clamp(std::atoi(value.c_str()), 1, kMaxWorldActors);
        } else if (key == "f7_mode") {
            g_config.f7Mode = parseF7Mode(value, g_config.f7Mode);
        } else if (key == "include_same_faction") {
            g_config.includeSameFaction = parseBool(value, g_config.includeSameFaction);
        } else if (key == "include_faction_allowlist") {
            g_config.includeFactionAllowlist = parseBool(value, g_config.includeFactionAllowlist);
        } else if (key == "ally_factions") {
            const auto parsed = parseIntList(value);
            if (!parsed.empty()) {
                g_config.allyFactions = parsed;
            }
        } else if (key == "set_squad_faction_to_player_faction") {
            g_config.setSquadFactionToPlayerFaction = parseBool(value, g_config.setSquadFactionToPlayerFaction);
        } else if (key == "set_actor_companion_flag") {
            g_config.setActorCompanionFlag = parseBool(value, g_config.setActorCompanionFlag);
        } else if (key == "add_follow_goal") {
            g_config.addFollowGoal = parseBool(value, g_config.addFollowGoal);
        } else if (key == "clear_goals_before_follow_goal") {
            g_config.clearGoalsBeforeFollowGoal = parseBool(value, g_config.clearGoalsBeforeFollowGoal);
        } else if (key == "make_squad_empty_before_join") {
            g_config.makeSquadEmptyBeforeJoin = parseBool(value, g_config.makeSquadEmptyBeforeJoin);
        } else if (key == "join_player_first") {
            g_config.joinPlayerFirst = parseBool(value, g_config.joinPlayerFirst);
        }
    }

    logLine(
        "load_config: enabled=%d startup_delay_ms=%d f7_mode=%s radius=%.2f max_actors=%d same_faction=%d allowlist=%d follow_goal=%d companion_flag=%d",
        g_config.enabled,
        g_config.startupDelayMs,
        f7ModeName(g_config.f7Mode),
        g_config.radius,
        g_config.maxActors,
        g_config.includeSameFaction,
        g_config.includeFactionAllowlist,
        g_config.addFollowGoal,
        g_config.setActorCompanionFlag);
    return true;
}

float distanceBetween(const Vector3& a, const Vector3& b) {
    const float dx = a.x - b.x;
    const float dy = a.y - b.y;
    const float dz = a.z - b.z;
    return std::sqrt(dx * dx + dy * dy + dz * dz);
}

bool isFactionAllowed(int actorFaction, int playerFaction) {
    if (g_config.includeSameFaction && actorFaction == playerFaction) {
        return true;
    }
    if (g_config.includeFactionAllowlist) {
        return std::find(g_config.allyFactions.begin(), g_config.allyFactions.end(), actorFaction) != g_config.allyFactions.end();
    }
    return false;
}

bool ensureSquad() {
    BOOL valid = FALSE;
    DWORD exceptionCode = 0;
    if (safeSquadIsValid(g_squad, valid, exceptionCode) && valid) {
        return true;
    }
    if (exceptionCode) {
        logLine("ensure_squad: existing_squad_valid_check_exception=0x%08lX", exceptionCode);
        g_squad = 0;
    }

    if (!g_layout) {
        logLine("ENTER ensure_squad.create_layout");
        if (!safeCreateLayout(g_layout, exceptionCode)) {
            logLine("EXIT ensure_squad.create_layout FAILED exception=0x%08lX", exceptionCode);
            return false;
        }
        logLine("EXIT ensure_squad.create_layout OK layout=%d", g_layout);
    }

    if (!g_layout) {
        logLine("ensure_squad: FAILED reason=no_layout");
        return false;
    }

    logLine("ENTER ensure_squad.create_squad layout=%d", g_layout);
    if (!safeCreateSquad(g_layout, g_squad, exceptionCode)) {
        logLine("EXIT ensure_squad.create_squad FAILED exception=0x%08lX", exceptionCode);
        return false;
    }
    valid = FALSE;
    if (!safeSquadIsValid(g_squad, valid, exceptionCode)) {
        logLine("ensure_squad: valid_check_exception=0x%08lX squad=%d", exceptionCode, g_squad);
        return false;
    }
    logLine("EXIT ensure_squad.create_squad OK squad=%d valid=%d", g_squad, valid);
    return g_squad && valid;
}

bool getPlayer(Actor& player, Vector3& playerPos, int& playerFaction) {
    player = ACTOR::GET_PLAYER_ACTOR(0);
    if (!player || !ENTITY::IS_ACTOR_VALID(player) || !HEALTH::IS_ACTOR_ALIVE(player)) {
        logLine("get_player: FAILED player=%d", player);
        return false;
    }
    ACTOR::GET_POSITION(player, &playerPos);
    playerFaction = FACTION::GET_ACTOR_FACTION(player);
    return true;
}

void snapshotActors() {
    logLine("ENTER snapshot");
    Actor player = 0;
    Vector3 playerPos{};
    int playerFaction = -1;
    if (!getPlayer(player, playerPos, playerFaction)) {
        logLine("EXIT snapshot FAILED reason=no_valid_player");
        return;
    }

    int actors[kMaxWorldActors]{};
    const int limit = std::clamp(g_config.maxActors, 1, kMaxWorldActors);
    const int count = worldGetAllActors(actors, limit);

    int valid = 0;
    int alive = 0;
    int inRadius = 0;
    int allied = 0;
    for (int i = 0; i < count && i < limit; ++i) {
        const Actor actor = actors[i];
        if (!actor || !ENTITY::IS_ACTOR_VALID(actor) || ACTOR::IS_ACTOR_LOCAL_PLAYER(actor)) {
            continue;
        }
        ++valid;
        if (!HEALTH::IS_ACTOR_ALIVE(actor)) {
            continue;
        }
        ++alive;
        Vector3 pos{};
        ACTOR::GET_POSITION(actor, &pos);
        const float distance = distanceBetween(playerPos, pos);
        if (distance > g_config.radius) {
            continue;
        }
        ++inRadius;
        const int faction = FACTION::GET_ACTOR_FACTION(actor);
        const bool allowed = isFactionAllowed(faction, playerFaction);
        if (allowed) {
            ++allied;
            logLine("snapshot_candidate: actor=%d faction=%d distance=%.2f", actor, faction, distance);
        }
    }

    logLine(
        "EXIT snapshot OK player=%d faction=%d pos=%.2f,%.2f,%.2f count=%d valid=%d alive=%d in_radius=%d allied=%d squad=%d",
        player,
        playerFaction,
        playerPos.x,
        playerPos.y,
        playerPos.z,
        count,
        valid,
        alive,
        inRadius,
        allied,
        g_squad);
}

void squadNearbyAllies() {
    logLine("ENTER squad_nearby_allies f7_mode=%s", f7ModeName(g_config.f7Mode));
    if (!g_config.enabled) {
        logLine("EXIT squad_nearby_allies SKIPPED reason=config_disabled");
        return;
    }

    if (g_config.f7Mode == F7Mode::SnapshotOnly) {
        snapshotActors();
        logLine("EXIT squad_nearby_allies OK mode=snapshot_only");
        return;
    }

    Actor player = 0;
    Vector3 playerPos{};
    int playerFaction = -1;
    if (!getPlayer(player, playerPos, playerFaction)) {
        logLine("EXIT squad_nearby_allies FAILED reason=no_valid_player");
        return;
    }

    if (!ensureSquad()) {
        logLine("EXIT squad_nearby_allies FAILED reason=no_valid_squad");
        return;
    }

    if (g_config.f7Mode == F7Mode::CreateSquadOnly) {
        logLine("EXIT squad_nearby_allies OK mode=create_squad_only squad=%d", g_squad);
        return;
    }

    DWORD exceptionCode = 0;

    if (g_config.makeSquadEmptyBeforeJoin) {
        logLine("ENTER squad_make_empty squad=%d", g_squad);
        if (!safeSquadMakeEmpty(g_squad, exceptionCode)) {
            logLine("EXIT squad_make_empty FAILED exception=0x%08lX", exceptionCode);
            return;
        }
        logLine("EXIT squad_make_empty OK squad=%d", g_squad);
    }

    if (g_config.setSquadFactionToPlayerFaction) {
        logLine("ENTER squad_set_faction squad=%d faction=%d", g_squad, playerFaction);
        if (!safeSquadSetFaction(g_squad, playerFaction, exceptionCode)) {
            logLine("EXIT squad_set_faction FAILED exception=0x%08lX", exceptionCode);
            return;
        }
        logLine("EXIT squad_set_faction OK squad=%d faction=%d", g_squad, playerFaction);
    }

    int joined = 0;
    if (g_config.joinPlayerFirst) {
        logLine("ENTER squad_join_player squad=%d player=%d", g_squad, player);
        if (!safeSquadJoin(g_squad, player, exceptionCode)) {
            logLine("EXIT squad_join_player FAILED exception=0x%08lX", exceptionCode);
            return;
        }
        ++joined;
        logLine("EXIT squad_join_player OK actor=%d", player);
    }

    if (g_config.f7Mode == F7Mode::JoinPlayerOnly) {
        logLine("EXIT squad_nearby_allies OK mode=join_player_only squad=%d joined=%d", g_squad, joined);
        return;
    }

    int actors[kMaxWorldActors]{};
    const int limit = std::clamp(g_config.maxActors, 1, kMaxWorldActors);
    const int count = worldGetAllActors(actors, limit);
    int scanned = 0;
    int candidates = 0;
    int skippedInvalid = 0;
    int skippedDead = 0;
    int skippedDistance = 0;
    int skippedFaction = 0;

    for (int i = 0; i < count && i < limit; ++i) {
        const Actor actor = actors[i];
        ++scanned;
        if (!actor || !ENTITY::IS_ACTOR_VALID(actor) || ACTOR::IS_ACTOR_LOCAL_PLAYER(actor)) {
            ++skippedInvalid;
            continue;
        }
        if (!HEALTH::IS_ACTOR_ALIVE(actor)) {
            ++skippedDead;
            continue;
        }

        Vector3 pos{};
        ACTOR::GET_POSITION(actor, &pos);
        const float distance = distanceBetween(playerPos, pos);
        if (distance > g_config.radius) {
            ++skippedDistance;
            continue;
        }

        const int faction = FACTION::GET_ACTOR_FACTION(actor);
        if (!isFactionAllowed(faction, playerFaction)) {
            ++skippedFaction;
            continue;
        }

        ++candidates;
        if (g_config.setActorCompanionFlag) {
            ENTITY::SET_ACTOR_IS_COMPANION(actor, TRUE);
        }
        logLine("ENTER squad_join_actor squad=%d actor=%d faction=%d distance=%.2f", g_squad, actor, faction, distance);
        if (!safeSquadJoin(g_squad, actor, exceptionCode)) {
            logLine("EXIT squad_join_actor FAILED exception=0x%08lX actor=%d", exceptionCode, actor);
            continue;
        }
        ++joined;
        logLine("EXIT squad_join_actor OK actor=%d faction=%d distance=%.2f", actor, faction, distance);
    }

    int followGoal = 0;
    if (g_config.f7Mode == F7Mode::JoinAlliesFollowGoal && g_config.addFollowGoal) {
        if (g_config.clearGoalsBeforeFollowGoal) {
            logLine("ENTER squad_goals_clear squad=%d", g_squad);
            if (!safeSquadGoalsClear(g_squad, exceptionCode)) {
                logLine("EXIT squad_goals_clear FAILED exception=0x%08lX", exceptionCode);
                return;
            }
            logLine("EXIT squad_goals_clear OK squad=%d", g_squad);
        }
        logLine("ENTER squad_follow_goal squad=%d player=%d", g_squad, player);
        if (!safeSquadFollowGoal(g_squad, player, followGoal, exceptionCode)) {
            logLine("EXIT squad_follow_goal FAILED exception=0x%08lX", exceptionCode);
            return;
        }
        logLine("EXIT squad_follow_goal OK goal=%d squad=%d player=%d", followGoal, g_squad, player);
    }

    int squadSize = 0;
    BOOL squadValid = FALSE;
    safeSquadGetSize(g_squad, squadSize, exceptionCode);
    safeSquadIsValid(g_squad, squadValid, exceptionCode);

    logLine(
        "EXIT squad_nearby_allies OK squad=%d squad_valid=%d squad_size=%d scanned=%d candidates=%d joined=%d skipped_invalid=%d skipped_dead=%d skipped_distance=%d skipped_faction=%d follow_goal=%d",
        g_squad,
        squadValid,
        squadSize,
        scanned,
        candidates,
        joined,
        skippedInvalid,
        skippedDead,
        skippedDistance,
        skippedFaction,
        followGoal);
}

void resetSquad() {
    logLine("ENTER reset_squad");
    BOOL valid = FALSE;
    DWORD exceptionCode = 0;
    if (!safeSquadIsValid(g_squad, valid, exceptionCode) || !valid) {
        logLine("EXIT reset_squad SKIPPED reason=no_valid_squad squad=%d", g_squad);
        return;
    }
    safeSquadGoalsClear(g_squad, exceptionCode);
    safeSquadMakeEmpty(g_squad, exceptionCode);
    int squadSize = 0;
    safeSquadGetSize(g_squad, squadSize, exceptionCode);
    logLine("EXIT reset_squad OK squad=%d size=%d", g_squad, squadSize);
}

bool shouldDebounce(DWORD& lastTick) {
    const DWORD now = GetTickCount();
    if (now - lastTick < kDebounceMs) {
        return true;
    }
    lastTick = now;
    return false;
}

void OnKeyboard(DWORD key, WORD, BYTE, BOOL isUp, BOOL, BOOL, BOOL) {
    if (isUp) {
        return;
    }
    if (!g_ready.load()) {
        return;
    }

    if (key == VK_F6) {
        if (!shouldDebounce(g_lastF6)) {
            g_requestSnapshot = true;
        }
    } else if (key == VK_F7) {
        if (!shouldDebounce(g_lastF7)) {
            g_requestSquadAllies = true;
        }
    } else if (key == VK_F8) {
        if (!shouldDebounce(g_lastF8)) {
            g_requestResetSquad = true;
        }
    }
}

void ScriptMain() {
    logLine("script_started");
    loadConfig();
    if (g_config.startupDelayMs > 0) {
        logLine("startup_delay_begin ms=%d", g_config.startupDelayMs);
        WAIT(static_cast<DWORD>(g_config.startupDelayMs));
        logLine("startup_delay_end");
    }
    g_ready = true;
    logLine("script_ready controls=F6_snapshot,F7_staged_squad,F8_reset");

    while (true) {
        if (g_requestSnapshot.exchange(false)) {
            loadConfig();
            snapshotActors();
        }
        if (g_requestSquadAllies.exchange(false)) {
            loadConfig();
            squadNearbyAllies();
        }
        if (g_requestResetSquad.exchange(false)) {
            resetSquad();
        }
        WAIT(50);
    }
}

} // namespace

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        g_module = module;
        DisableThreadLibraryCalls(module);
        scriptRegister(module, ScriptMain);
        keyboardHandlerRegister(OnKeyboard);
    } else if (reason == DLL_PROCESS_DETACH) {
        keyboardHandlerUnregister(OnKeyboard);
        scriptUnregister(module);
    }
    return TRUE;
}
