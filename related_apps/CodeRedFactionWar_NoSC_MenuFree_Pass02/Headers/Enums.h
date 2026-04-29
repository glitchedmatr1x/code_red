#pragma once

// Virtual-key based input aliases for the prepared project.
constexpr int KEY_F7 = VK_F7;
constexpr int KEY_F8 = VK_F8;
constexpr int KEY_F9 = VK_F9;
constexpr int KEY_F10 = VK_F10;
constexpr int KEY_F11 = VK_F11;
constexpr int KEY_NUMPAD0 = VK_NUMPAD0;
constexpr int KEY_NUMPAD1 = VK_NUMPAD1;
constexpr int KEY_NUMPAD2 = VK_NUMPAD2;
constexpr int KEY_NUMPAD3 = VK_NUMPAD3;
constexpr int KEY_NUMPAD4 = VK_NUMPAD4;
constexpr int KEY_NUMPAD5 = VK_NUMPAD5;
constexpr int KEY_NUMPAD6 = VK_NUMPAD6;
constexpr int KEY_NUMPAD7 = VK_NUMPAD7;
constexpr int KEY_NUMPAD8 = VK_NUMPAD8;
constexpr int KEY_NUMPAD9 = VK_NUMPAD9;
constexpr int KEY_DIVIDE = VK_DIVIDE;
constexpr int KEY_DECIMAL = VK_DECIMAL;
constexpr int KEY_MULTIPLY = VK_MULTIPLY;
constexpr int KEY_SUBTRACT = VK_SUBTRACT;
constexpr int KEY_ADD = VK_ADD;

enum ActorModel : int
{
    ACTOR_CAUCASIAN_MALE_Farmer01 = 111,
    ACTOR_COMPANION_Marshal = 547,
    ACTOR_COMPANION_Outlaw = 548,
    ACTOR_COMPANION_MexicanHenchman = 556,
    ACTOR_COMPANION_NativeFriend = 562,
    ACTOR_COMPANION_NativeFriend_02 = 563,

    ACTOR_MISC_Deputy_Marshal01 = 588,
    ACTOR_MISC_Deputy_Marshal02 = 590,
    ACTOR_MISC_Deputy_Marshal03 = 592,
    ACTOR_MISC_TreasureHunter_Leader = 624,
    ACTOR_MISC_MineWorker = 625,
    ACTOR_MISC_Outlaw_01 = 659,
    ACTOR_MISC_BillsGang01 = 668,
    ACTOR_MISC_BillsGang02 = 670,
    ACTOR_MISC_BillsGang03 = 672,
    ACTOR_MISC_BillsGang04 = 673,
    ACTOR_MISC_BillsGang05 = 675,

    // Fallbacks chosen from the generic Mexican rebel gang table.
    ACTOR_MISC_RebelSoldier01 = 516,
    ACTOR_MISC_RebelSoldier02 = 517,
    ACTOR_MISC_RebelSoldier03 = 518,
    ACTOR_MISC_RebelSoldier05 = 752,
    ACTOR_MISC_RebelSoldier06 = 754,

    ACTOR_MISC_BanditRider01 = 756,
    ACTOR_MISC_BanditRider02 = 757,
    ACTOR_MISC_RanchHand01 = 768,
    ACTOR_MISC_RanchHand02 = 769,
};
