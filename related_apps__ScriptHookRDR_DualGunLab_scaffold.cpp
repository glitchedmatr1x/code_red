// CodeRED DualGunLab ScriptHook scaffold (not a compiled patch yet)
//
// Purpose:
// - Add a lab mode to CodeRED_AI_Menu.cpp after the attachment-data scan.
// - Use runtime attach/nudge/debug before any WFT/WEDT mutation.
// - Keep right-hand weapon native.
// - Attach left-hand pistol prop to a candidate locator and simulate left fire with raycast/damage.
//
// Required proof before compile integration:
// 1) Confirm native name/hash for attaching actor/prop to locator/bone.
// 2) Confirm native name/hash for spawning weapon/prop model safely.
// 3) Confirm raycast native or fallback projectile/damage native.
// 4) Confirm prop cleanup on dismiss/reload.
//
// Suggested menu actions:
// - dualgun_attach_left_prop_request
// - dualgun_nudge_offset_request
// - dualgun_save_offset_preset_request
// - dualgun_left_fire_test_request
// - dualgun_debug_draw_request
//
// Data source:
// reports/wft_wedt_attachment_lab/script_hook_dualgun_attachment_plan.json

struct DualGunLabState {
    bool enabled = false;
    int leftPropActor = 0;
    float offset[3] = {0.0f, 0.0f, 0.0f};
    float eulers[3] = {0.0f, 0.0f, 0.0f};
    const char* attachLocator = "smic_player_default_hand_1_rm";
    const char* fallbackAttachLocator = "smic_player_default_hand_1";
};

// Pseudocode only:
// 1. Ensure player actor is valid.
// 2. Spawn or request a pistol prop/fragment candidate.
// 3. Attach prop to attachLocator with offset/eulers.
// 4. Draw muzzle/locator debug.
// 5. On left trigger: fire raycast from left prop muzzle/camera-aligned fallback.
// 6. On dismiss/reload: delete prop and clear state.
