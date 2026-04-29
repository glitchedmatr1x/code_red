
// Code RED tune profile include v26
// Derived from tune_d11generic.rpf string scan.
// Version marker for AI/workflow continuity: v07

namespace CodeRedTuneProfilesV26
{
    struct TuneNodeProfile
    {
        const char* nodeId;
        const char* contextTag;
        const char* ambientSet;
        const char* civilianArchetype;
        const char* outlawArchetype;
        const char* lawArchetype;
        const char* missionFlavor;
        const char* travelFlavor;
        const char* abandonedToken;
        const char* returnToken;
    };

    static constexpr TuneNodeProfile kTuneNodeProfiles[] = {
        {"armadillo", "law_town", "smic_armadillo", "AE_Caucasian_Male_TownFolk02", "AE_MISC_Outlaw_01", "AE_Law_Caucasian_TownPosse_Easy01", "law_bounty", "tutorial_road_to_armadillo", "", ""},
        {"ridgewood_farm", "ranch_homestead", "smic_p_gen_campfire04", "AE_Caucasian_Male_Rancher01", "AE_Caucasian_GenericCriminal_Easy01", "AE_Law_Caucasian_Sheriff_Medium01", "wagon_escort", "wagon_choose_ride", "", ""},
        {"twin_rocks", "rustler_hideout", "smic_p_gen_campfire04", "AE_Caucasian_Male_Traveler01", "AE_Gang_CATTLERUSTLER_Medium01", "AE_Law_Caucasian_TownPosse_Easy02", "camp_assault", "horse_matchspeed_wagon", "", "Outlaw_return"},
        {"benedict_point", "rail_checkpoint", "smic_p_gen_campfire04", "AE_Caucasian_Male_RailroadStaff01", "AE_Caucasian_GenericCriminal_Medium01", "AE_Law_Caucasian_USMarshal_Hard01", "wagon_convoy", "wagon_choose_ride", "", ""},
        {"gaptooth_breach", "mine_hideout", "smic_p_gen_campfire04", "AE_Caucasian_Male_MineWorker01", "AE_Gang_CRAZYMINER_Medium01", "AE_Law_Caucasian_USMarshal_Hard02", "treasure_map", "item_treasure_map", "GaptoothBreach_abandoned", "GaptoothBreach_return"},
        {"rathskeller_fork", "border_crossing", "smic_p_gen_campfire04", "AE_Caucasian_Male_Traveler02", "AE_Caucasian_GenericCriminal_Easy02", "AE_Law_Caucasian_TownPosse_Easy03", "border_escort", "wagon_nap_obj", "", ""},
        {"solomons_folly", "roadside_robbery", "smic_p_gen_campfire04", "AE_Caucasian_Male_Traveler05", "AE_Gang_CATTLERUSTLER_Hard01", "AE_Law_Caucasian_USMarshal_Hard03", "road_robbery", "Steal_Wagon", "Outlaw_abandoned", "Outlaw_return"},
        {"tumbleweed", "ghost_town", "smic_p_gen_campfire04", "AE_Caucasian_Old_Male_Beggar01", "AE_MISC_Outlaw_01", "AE_Law_Caucasian_Sheriff_Medium02", "ghost_town", "GhostTown_Help1", "", ""},
        {"hennigans_ranch", "escort_crossroads", "smic_p_gen_campfire04", "AE_Caucasian_Male_Rancher01", "AE_Caucasian_GenericCriminal_Easy03", "AE_Law_Caucasian_Sheriff_Medium03", "escort_route", "proc_escort_first_help", "", ""},
        {"pikes_basin", "camp_hideout", "smic_pikesBasin", "AE_Caucasian_Male_Traveler06", "AE_Gang_CATTLERUSTLER_Medium02", "AE_Law_Caucasian_USMarshal_Hard04", "camp_raiders", "sit_camp", "Outlaw_abandoned", "Outlaw_return"},
        {"thieves_landing", "black_market", "smic_p_gen_lamp02bnternGlass05thievesding", "AE_Caucasian_Male_DocksWorker01", "AE_Black_GenericCriminal_Medium01", "AE_Law_Caucasian_TownPosse_Easy04", "wagon_theft", "Steal_Wagon", "", ""},
        {"fort_mercer", "fort_war", "smic_p_gen_campfire04", "AE_Hispanic_Male_Laborer01", "AE_Gang_BANDITO_Hard01", "AE_Caucasian_Army_Hard01", "bandito_assault", "out_bandito_hint1", "", ""},
        {"plainview", "bandito_outpost", "smic_p_gen_campfire04", "AE_Hispanic_Male_Traveler01", "AE_Gang_BANDITO_Medium01", "AE_Caucasian_Army_Medium01", "bandito_patrol", "out_bandito_hint2", "", ""},
    };
}
