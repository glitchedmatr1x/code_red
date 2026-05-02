#!/usr/bin/env python3
"""Patch CodeRED_AI_Menu.cpp with a compact scrolling panel renderer.

This is intentionally surgical. It only replaces `static void drawMenu()` when that
function is present and brace-balanced. If the source layout has changed, it refuses
rather than guessing.
"""
from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path

DEFAULT_SOURCE = Path("related_apps/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.cpp")
MARKER = "// CodeRED compact scrolling menu layout pass"

NEW_DRAW_MENU = r'''static int listStartFor(int selected, int total, int visible) {
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
    const int visibleActions = std::min(std::max(totalActions, 1), 7);
    const int visibleRoster = std::min(std::max(totalRoster, 1), 9);
    const int visibleRows = std::max(visibleActions, visibleRoster);

    const float rowH = 0.026f;
    const float headerH = 0.120f;
    const float footerH = 0.070f;
    const float panelW = 0.520f;
    const float panelH = std::min(0.780f, std::max(0.320f, headerH + footerH + rowH * static_cast<float>(visibleRows + 2)));
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
        std::string hint = "actions " + std::to_string(actionStart + 1) + "-" + std::to_string(std::min(actionStart + visibleActions, totalActions)) + " / " + std::to_string(totalActions);
        drawTextSafe(actionX + 0.005f, top + panelH - 0.050f, hint.c_str(), 190, 190, 190, 230, FONT_REDEMPTION, 0.015f, JUSTIFY_LEFT);
    }
    if (totalRoster > visibleRoster) {
        std::string hint = "roster " + std::to_string(rosterStart + 1) + "-" + std::to_string(std::min(rosterStart + visibleRoster, totalRoster)) + " / " + std::to_string(totalRoster);
        drawTextSafe(rosterX + 0.005f, top + panelH - 0.050f, hint.c_str(), 190, 190, 190, 230, FONT_REDEMPTION, 0.015f, JUSTIFY_LEFT);
    }

    std::string footer = "F8/INSERT close | UP/DOWN action | LEFT/RIGHT roster | ENTER run | BACK/ESC close";
    drawTextSafe(left + 0.020f, top + panelH - 0.026f, footer.c_str(), 235, 235, 235, 235, FONT_REDEMPTION, 0.015f, JUSTIFY_LEFT);
    if (!g_status.empty()) {
        drawTextSafe(left + 0.020f, top + panelH - 0.005f, g_status.c_str(), 255, 140, 140, 235, FONT_REDEMPTION, 0.014f, JUSTIFY_LEFT);
    }
}
// CodeRED compact scrolling menu layout pass
'''


def find_function_span(text: str, signature: str) -> tuple[int, int] | None:
    start = text.find(signature)
    if start < 0:
        return None
    brace = text.find("{", start)
    if brace < 0:
        return None
    depth = 0
    for i in range(brace, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return start, i + 1
    return None


def patch_source(path: Path, replace: bool) -> bool:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if MARKER in text:
        print("Compact scrolling layout is already present.")
        return False
    span = find_function_span(text, "static void drawMenu()")
    if not span:
        raise RuntimeError("Could not find brace-balanced `static void drawMenu()` in source. Refusing to guess.")
    start, end = span
    patched = text[:start] + NEW_DRAW_MENU + text[end:]
    if not replace:
        backup = path.with_suffix(path.suffix + ".bak_layout_" + datetime.utcnow().strftime("%Y%m%d_%H%M%S"))
        shutil.copy2(path, backup)
        print(f"Backup: {backup}")
    path.write_text(patched, encoding="utf-8", newline="")
    print(f"Patched compact scrolling layout: {path}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch CodeRED_AI_Menu.cpp with compact scrolling menu layout.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--replace", action="store_true", help="Do not create a timestamp backup before patching.")
    args = parser.parse_args()
    if not args.source.exists():
        raise SystemExit(f"Source not found: {args.source}")
    patch_source(args.source, replace=args.replace)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
