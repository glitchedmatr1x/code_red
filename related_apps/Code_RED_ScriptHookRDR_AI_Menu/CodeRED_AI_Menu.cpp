// CodeRED_AI_Menu.cpp
// Conservative ScriptHookRDR in-game menu scaffold.
// This pass draws an overlay, loads an editable NPC roster, and writes action-plan JSON.
// It does not spawn actors or call risky native behavior functions yet.

#include <windows.h>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <algorithm>
#include <ctime>

#include "../../ScriptHookRDR/sdk/inc/main.h"
#include "../../ScriptHookRDR/sdk/inc/enums.h"

namespace codered {

static bool g_menuOpen = false;
static int g_menuIndex = 0;
static int g_npcIndex = 0;
static bool g_dirtyRoster = true;
static DWORD g_lastKeyMs = 0;

static std::string g_rosterPath = "data/codered/npc_roster.txt";
static std::string g_actionPlanPath = "scratch/codered_ai_action_plan.json";
static std::string g_status = "CodeRED AI Menu ready";

static std::vector<std::string> g_roster;
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

static std::string trim(const std::string& value) {
    size_t first = value.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) return "";
    size_t last = value.find_last_not_of(" \t\r\n");
    return value.substr(first, last - first + 1);
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
    g_roster.clear();
    std::ifstream file(g_rosterPath.c_str());
    std::string line;
    while (std::getline(file, line)) {
        std::string clean = trim(line);
        if (clean.empty()) continue;
        if (clean[0] == '#') continue;
        g_roster.push_back(clean);
    }
    ensureDefaultRoster();
    if (g_npcIndex < 0) g_npcIndex = 0;
    if (g_npcIndex >= static_cast<int>(g_roster.size())) g_npcIndex = 0;
    g_status = "Roster loaded: " + std::to_string(g_roster.size()) + " NPC models";
    g_dirtyRoster = false;
}

static std::string selectedNpc() {
    ensureDefaultRoster();
    if (g_npcIndex < 0) g_npcIndex = 0;
    if (g_npcIndex >= static_cast<int>(g_roster.size())) g_npcIndex = 0;
    return g_roster[g_npcIndex];
}

static std::string selectedAction() {
    if (g_menuIndex < 0) g_menuIndex = 0;
    if (g_menuIndex >= static_cast<int>(g_actions.size())) g_menuIndex = 0;
    return g_actions[g_menuIndex];
}

static void writeActionPlan() {
    std::ofstream file(g_actionPlanPath.c_str(), std::ios::trunc);
    if (!file) {
        g_status = "Could not write action plan";
        return;
    }

    std::time_t now = std::time(nullptr);
    file << "{\n";
    file << "  \"source\": \"CodeRED_AI_Menu\",\n";
    file << "  \"action\": \"" << jsonEscape(selectedAction()) << "\",\n";
    file << "  \"model\": \"" << jsonEscape(selectedNpc()) << "\",\n";
    file << "  \"status\": \"queued\",\n";
    file << "  \"timestamp\": " << static_cast<long long>(now) << "\n";
    file << "}\n";

    g_status = "Queued: " + selectedAction() + " / " + selectedNpc();
}

static bool throttleKey() {
    DWORD now = GetTickCount();
    if (now - g_lastKeyMs < 140) return true;
    g_lastKeyMs = now;
    return false;
}

static void onKey(DWORD key, WORD, BYTE, BOOL isDown, BOOL, BOOL, BOOL) {
    if (!isDown) return;

    if (key == VK_F8 || key == VK_INSERT) {
        if (throttleKey()) return;
        g_menuOpen = !g_menuOpen;
        if (g_menuOpen) g_dirtyRoster = true;
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
        g_npcIndex--;
        if (g_npcIndex < 0) g_npcIndex = static_cast<int>(g_roster.size()) - 1;
        return;
    }

    if (key == VK_RIGHT) {
        g_npcIndex++;
        if (g_npcIndex >= static_cast<int>(g_roster.size())) g_npcIndex = 0;
        return;
    }

    if (key == VK_RETURN) {
        writeActionPlan();
        return;
    }

    if (key == VK_F5) {
        g_dirtyRoster = true;
        return;
    }
}

static void drawLine(float x, float y, const std::string& text, int r = 235, int g = 235, int b = 235, float size = 0.35f) {
    drawText(x, y, text.c_str(), r, g, b, 255, FontID::Redemption, size, TextJustification::Left);
}

static void drawMenu() {
    if (!g_menuOpen) {
        drawText(0.015f, 0.955f, "CodeRED AI Bridge: F8", 210, 60, 60, 180, FontID::Redemption, 0.26f, TextJustification::Left);
        return;
    }

    if (g_dirtyRoster) loadRoster();

    drawRect(0.25f, 0.40f, 0.46f, 0.60f, 8, 8, 8, 205, 0.01f);
    drawRect(0.25f, 0.105f, 0.46f, 0.055f, 95, 0, 0, 220, 0.01f);

    drawLine(0.035f, 0.078f, "CodeRED AI Menu", 255, 70, 70, 0.42f);
    drawLine(0.035f, 0.135f, "NPC: " + selectedNpc(), 255, 230, 190, 0.32f);
    drawLine(0.035f, 0.170f, "LEFT/RIGHT switch NPC  |  F5 reload roster", 190, 190, 190, 0.25f);

    float y = 0.225f;
    for (int i = 0; i < static_cast<int>(g_actions.size()); ++i) {
        const bool selected = (i == g_menuIndex);
        std::string prefix = selected ? "> " : "  ";
        int r = selected ? 255 : 220;
        int g = selected ? 80 : 220;
        int b = selected ? 80 : 220;
        drawLine(0.055f, y, prefix + g_actions[i], r, g, b, 0.30f);
        y += 0.038f;
    }

    drawLine(0.035f, 0.565f, "ENTER queue action  |  BACK/ESC close", 190, 190, 190, 0.25f);
    drawLine(0.035f, 0.602f, g_status, 255, 210, 120, 0.25f);
}

static void mainLoop() {
    while (true) {
        drawMenu();
        WAIT(0);
    }
}

} // namespace codered

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(module);
        scriptRegister(module, codered::mainLoop);
        keyboardHandlerRegister(codered::onKey);
    } else if (reason == DLL_PROCESS_DETACH) {
        keyboardHandlerUnregister(codered::onKey);
        scriptUnregister(module);
    }
    return TRUE;
}
