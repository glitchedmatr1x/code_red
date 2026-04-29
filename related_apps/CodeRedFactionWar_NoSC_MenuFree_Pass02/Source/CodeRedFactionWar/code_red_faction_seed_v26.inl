// Code RED generated seed include v26
// Generated from extracted registries and resource donor anchors.
// Version marker for AI/workflow continuity: v26

namespace CodeRedFactionSeedV26
{
    struct SeedFaction
    {
        const char* engineFaction;
        const char* brandName;
        bool lawEnforcement;
        bool lawfulToAttack;
        int hostileRelationCount;
        int alliedRelationCount;
    };

    struct SeedNode
    {
        const char* nodeId;
        const char* displayName;
        const char* regionName;
        const char* defaultController;
        const char* neighborsCsv;
        const char* strategicTagsCsv;
        int basePressure;
        int baseHeat;
        float anchorX;
        float anchorY;
        float anchorZ;
        float anchorHeading;
        bool hasAnchor;
    };

    struct SeedMission
    {
        const char* missionId;
        const char* displayName;
        const char* description;
        const char* missionType;
    };

    static constexpr SeedFaction kSeedFactions[] = {
        {"USLawEnforcement", "US Marshals", true, false, 10, 2},
        {"CattleRustler", "Bollard / Walton", false, true, 16, 1},
        {"TreasureHunter", "Treasure Hunters", false, true, 17, 1},
        {"GenericCriminal", "Thieves' Landing Outlaws", false, true, 16, 1},
        {"MexicanBandito", "Banditos", false, true, 12, 4},
        {"PlayerNeutral", "Homesteaders", false, false, 0, 1},
        {"PlayerFriendly", "Ranch Allies", false, false, 0, 2},
        {"IndianRaider", "Dutch's Gang", false, true, 16, 1},
    };

    static constexpr SeedNode kSeedNodes[] = {
        {"armadillo", "Armadillo", "cholla_springs", "USLawEnforcement", "ridgewood_farm,twin_rocks,thieves_landing", "law_hub,civilian_pressure,transport_post", 55, 15, -2174.8779f, 16.2192f, 2612.1245f, -93.0f, true},
        {"ridgewood_farm", "Ridgewood Farm", "cholla_springs", "PlayerNeutral", "armadillo,twin_rocks,pikes_basin", "supply_node,civilian_defense", 55, 6, -3222.7070f, 16.2142f, 2700.2136f, 118.6f, true},
        {"twin_rocks", "Twin Rocks", "cholla_springs", "CattleRustler", "armadillo,ridgewood_farm,fort_mercer", "ambush_ground,outlaw_hideout", 70, 6, -2700.0f, 18.0f, 2800.0f, 115.0f, true},
        {"benedict_point", "Benedict Point", "gaptooth_ridge", "USLawEnforcement", "solomons_folly,gaptooth_breach,fort_mercer", "rail_node,checkpoint,transport_post", 55, 6, -3689.5247f, 8.0954f, 3456.2620f, 94.6f, true},
        {"gaptooth_breach", "Gaptooth Breach", "gaptooth_ridge", "TreasureHunter", "solomons_folly,benedict_point,tumbleweed", "mine_hideout,resource_node", 70, 6, -3925.0f, 12.0f, 3015.0f, 30.0f, true},
        {"rathskeller_fork", "Rathskeller Fork", "gaptooth_ridge", "PlayerNeutral", "plainview,tumbleweed", "border_crossing,transport_post", 45, 6, -3687.8213f, 41.7716f, 2147.8994f, -45.8f, true},
        {"solomons_folly", "Solomons Folly", "gaptooth_ridge", "CattleRustler", "pikes_basin,gaptooth_breach,benedict_point", "roadside_robbery,outlaw_hideout", 70, 6, -1850.0f, 40.0f, 2730.0f, 75.0f, true},
        {"tumbleweed", "Tumbleweed", "gaptooth_ridge", "PlayerNeutral", "gaptooth_breach,rathskeller_fork", "ghost_town,loot_zone", 55, 6, -3450.0f, 28.0f, 2850.0f, -20.0f, true},
        {"hennigans_ranch", "Hennigans Ranch", "hennigans_stead", "PlayerFriendly", "pikes_basin,thieves_landing,solomons_folly", "crossroads,escort_routes,transport_post", 55, 6, -785.9983f, 92.3670f, 2429.9731f, 51.8f, true},
        {"pikes_basin", "Pikes Basin", "hennigans_stead", "CattleRustler", "thieves_landing,hennigans_ranch,solomons_folly", "hideout,raid_origin", 70, 6, -250.0f, 82.0f, 2275.0f, 140.0f, true},
        {"thieves_landing", "Thieves Landing", "hennigans_stead", "GenericCriminal", "armadillo,pikes_basin,hennigans_ranch", "black_market,criminal_overlap,transport_post", 70, 6, 101.9139f, 73.1091f, 2322.7966f, -51.0f, true},
        {"fort_mercer", "Fort Mercer", "rio_bravo", "MexicanBandito", "twin_rocks,benedict_point,plainview", "fortified_outpost,war_anchor", 70, 6, -3400.0f, 34.0f, 3380.0f, -150.0f, true},
        {"plainview", "Plainview", "rio_bravo", "MexicanBandito", "fort_mercer,rathskeller_fork", "wilderness_outpost,transport_post", 60, 6, -3135.2666f, 43.3561f, 3717.7427f, -156.2f, true},
    };

    static constexpr SeedMission kSeedMissions[] = {
        {"defend_hideout", "Defend Hideout", "Hold the node against a raid wave.", "defense"},
        {"raid_road_convoy", "Raid Road Convoy", "Intercept transport crossing contested territory.", "raid"},
        {"law_sweep", "Law Sweep", "Marshals push through and clear outlaw pressure.", "law"},
        {"escort_prisoner", "Escort Prisoner", "Protect or intercept a prisoner transport.", "law"},
        {"retaliation_strike", "Retaliation Strike", "Counterattack after losing pressure in a node.", "raid"},
        {"fortify_node", "Fortify Node", "Move men and supplies into the current node.", "defense"},
        {"tax_settlement", "Tax Settlement", "Pressure a civilian node for supplies and fear.", "raid"},
        {"rescue_lieutenant", "Rescue Lieutenant", "Recover a captured faction officer.", "rescue"},
        {"escort_supply_wagon", "Escort Supply Wagon", "Run supplies between linked transport posts before rivals intercept them.", "escort"},
        {"frontier_patrol", "Frontier Patrol", "Ride the transport line and show your colors to steady local pressure.", "patrol"},
    };
}
