#!/usr/bin/env python3
"""Patch CodeRED_AI_Menu.cpp with a compact scrolling panel renderer.

Conservative behavior:
- replaces a brace-balanced `static void drawMenu()` when no compact pass exists
- replaces the older compact pass when present
- refuses when the expected source shape cannot be found

This version avoids std::min/std::max because Windows headers may define min/max
macros, producing C++ errors such as "illegal token on right side of '::'".
"""
from __future__ import annotations

import argparse
import shutil
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_SOURCE = Path("related_apps/Code_RED_ScriptHookRDR_AI_Menu/CodeRED_AI_Menu.cpp")
OLD_MARKER = "// CodeRED compact scrolling menu layout pass"
NEW_MARKER = "// CodeRED compact scrolling menu layout pass v2 no-std-minmax"

NEW_BLOCK = r'''static int crMinInt(int a, int b) { return a < b ? a : b; }
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
'''


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


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


def find_existing_compact_span(text: str) -> tuple[int, int] | None:
    marker_pos = text.find(OLD_MARKER)
    if marker_pos < 0:
        marker_pos = text.find(NEW_MARKER)
    if marker_pos < 0:
        return None
    start = text.rfind("static int crMinInt", 0, marker_pos)
    if start < 0:
        start = text.rfind("static int listStartFor", 0, marker_pos)
    if start < 0:
        return None
    marker = NEW_MARKER if text.find(NEW_MARKER, marker_pos, marker_pos + len(NEW_MARKER)) >= 0 else OLD_MARKER
    return start, marker_pos + len(marker)


def patch_source(path: Path, replace: bool) -> bool:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if NEW_MARKER in text and "std::min" not in text and "std::max" not in text:
        print("Compact scrolling layout v2 is already present.")
        return False

    span = find_existing_compact_span(text)
    if span:
        start, end = span
    else:
        span = find_function_span(text, "static void drawMenu()")
        if not span:
            raise RuntimeError("Could not find compact layout block or brace-balanced `static void drawMenu()`. Refusing to guess.")
        start, end = span

    patched = text[:start] + NEW_BLOCK + text[end:]
    if not replace:
        backup = path.with_suffix(path.suffix + ".bak_layout_" + utc_stamp())
        shutil.copy2(path, backup)
        print(f"Backup: {backup}")
    path.write_text(patched, encoding="utf-8", newline="")
    print(f"Patched compact scrolling layout v2: {path}")
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
