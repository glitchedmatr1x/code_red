#include <pch.h>
// Code RED Faction War Plugin v26
// Version marker for AI/workflow continuity: v26
#include "code_red_factionwar_plugin_v26.h"

#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

#include "code_red_faction_seed_v26.inl"
#include "code_red_tune_profiles_v26.inl"

namespace
{
    using namespace CodeRedFactionSeedV26;
    using namespace CodeRedTuneProfilesV26;

    constexpr const char* kSavePath = "CodeRedFactionWar_NoSC_MenuFree.save";
    constexpr const char* kLogPath = "CodeRedFactionWar_NoSC_MenuFree.log";
    constexpr const char* kBindingsPath = "CodeRedFactionWar_NoSC_MenuFree_factions.ini";
    constexpr const char* kDiagnosticsPath = "CodeRedFactionWar_NoSC_MenuFree_diagnostics.txt";
    constexpr const char* kBulletinPath = "CodeRedFactionWar_NoSC_MenuFree_bulletin.txt";
    constexpr int kMaxControllerName = 64;
    constexpr int kMaxMissionText = 192;
    constexpr int kMaxToastText = 256;
    constexpr int kMaxSquadActors = 8;

    // No-SC / menu-free pass:
    // Keep the simulation running as an ambient world layer, but do not open
    // debug overlays, do not listen for trainer-style menu hotkeys, and do not
    // spam HUD toasts. State is still written to logs/diagnostics/bulletins.
    constexpr bool kMenuFreeWorldMode = true;
    constexpr bool kEnableDebugHotkeys = false;
    constexpr bool kEnableHudToasts = false;
    constexpr const char* kNoScModeMarker = "NoSC_MenuFree_Pass02";

    struct RuntimeNode
    {
        char nodeId[48]{};
        char displayName[64]{};
        char regionName[48]{};
        float anchorX = 0.0f;
        float anchorY = 0.0f;
        float anchorZ = 0.0f;
        float anchorHeading = 0.0f;
        bool hasAnchor = false;
        char controller[kMaxControllerName]{};
        char activeAssaultFaction[kMaxControllerName]{};
        char neighborsCsv[160]{};
        char strategicTagsCsv[160]{};
        char contextTag[48]{};
        char ambientSet[64]{};
        char civilianArchetype[64]{};
        char outlawArchetype[64]{};
        char lawArchetype[64]{};
        char missionFlavor[48]{};
        char travelFlavor[48]{};
        char abandonedToken[48]{};
        char returnToken[48]{};
        char localState[64]{};
        char trafficState[48]{};
        char populationProfile[64]{};
        char occupationState[48]{};
        char occupationFaction[kMaxControllerName]{};
        int occupationUntilDay = -1;
        int civilianWeight = 0;
        int outlawWeight = 0;
        int lawWeight = 0;
        int wagonWeight = 0;
        int pressure = 0;
        int heat = 0;
        int supply = 50;
        int fear = 20;
        int fortification = 0;
        bool contested = false;
        uint64_t nextAutoEventAllowedMs = 0;
        int lastTriggeredDay = -1;
        int dailyTriggerCount = 0;
        int activeStartHour = 0;
        int activeEndHour = 23;
        char roadControlState[48]{};
        int routePressure = 0;
        int escortNeed = 0;
    };

    struct MissionOffer
    {
        char missionId[48]{};
        char displayName[64]{};
        char description[kMaxMissionText]{};
        char sourceNodeId[48]{};
        char sourceFaction[kMaxControllerName]{};
        bool valid = false;
    };

    enum class PosseOrder
    {
        Follow = 0,
        Hold = 1,
        Wander = 2,
    };

    enum class SpawnedRole
    {
        Companion = 0,
        Rival = 1,
        Law = 2,
        TownAttacker = 3,
    };

    struct TownAssaultState
    {
        bool active = false;
        char nodeId[48]{};
        char attackerFaction[kMaxControllerName]{};
        char defenderFaction[kMaxControllerName]{};
        int waveIndex = 0;
        int maxWaves = 0;
        uint64_t nextWaveTickMs = 0;
        bool attackerNeighborReinforced = false;
        bool defenderNeighborReinforced = false;
    };

    struct RegionalShootoutState
    {
        bool active = false;
        char nodeId[48]{};
        char outlawFaction[kMaxControllerName]{};
        char lawFaction[kMaxControllerName]{};
        uint64_t resolveDeadlineMs = 0;
        bool outlawNeighborReinforced = false;
        bool lawNeighborReinforced = false;
    };

    enum class PendingConflictType
    {
        None = 0,
        TownAssault = 1,
        RegionalShootout = 2,
    };

    struct PendingConflictChain
    {
        bool active = false;
        PendingConflictType type = PendingConflictType::None;
        char nodeId[48]{};
        char sourceNodeId[48]{};
        char sourceFaction[kMaxControllerName]{};
        char targetFaction[kMaxControllerName]{};
        int executeDay = -1;
        int executeHour = -1;
        char reason[96]{};
    };

    struct RegionDirective
    {
        bool active = false;
        char regionName[48]{};
        char directiveName[48]{};
        char primaryNodeId[48]{};
        char sourceFaction[kMaxControllerName]{};
        int dayIssued = -1;
    };

    struct RegionPressureFront
    {
        bool active = false;
        char regionName[48]{};
        int lawPressure = 0;
        int outlawPressure = 0;
        char frontState[48]{};
        int lastSpilloverDay = -1;
        int lastSpilloverHour = -1;
    };

    struct RegionCadence
    {
        bool active = false;
        char regionName[48]{};
        int fatigue = 0;
        int recovery = 0;
        int momentum = 0;
        char cadenceState[48]{};
        int lastShiftDay = -1;
    };

    struct RegionLogistics
    {
        bool active = false;
        char regionName[48]{};
        int stock = 50;
        int convoyPressure = 0;
        int strain = 0;
        char supportState[48]{};
        int lastRefreshDay = -1;
    };

    struct RegionCivilianClimate
    {
        bool active = false;
        char regionName[48]{};
        int support = 0;
        int panic = 0;
        int repression = 0;
        int rumorTrust = 0;
        char climateState[48]{};
        int lastRefreshDay = -1;
    };

    struct RegionCampaignOutlook
    {
        bool active = false;
        char regionName[48]{};
        int lawControl = 0;
        int outlawControl = 0;
        int civilianTilt = 0;
        int strategicValue = 0;
        char campaignState[48]{};
        int lastRefreshDay = -1;
    };

    struct TheaterSummary
    {
        bool active = false;
        char theaterState[48]{};
        int lawLeaningRegions = 0;
        int outlawLeaningRegions = 0;
        int knifeEdgeRegions = 0;
        int playerMomentum = 0;
        int lastRefreshDay = -1;
    };

    struct SpawnedActorState
    {
        Actor actor = 0;
        Actor mountActor = 0;
        ActorModel model = static_cast<ActorModel>(0);
        bool active = false;
        bool companion = false;
        bool mounted = false;
        SpawnedRole role = SpawnedRole::Rival;
        char sourceFaction[kMaxControllerName]{};
    };

    struct FactionBinding
    {
        char engineFaction[kMaxControllerName]{};
        int factionId = -1;
    };

    struct RuntimeState
    {
        bool initialized = false;
        bool overlayOpen = false;
        bool simulationEnabled = true;
        bool membershipPreviewApplied = false;
        bool playerLeading = false;
        bool missionAccepted = false;
        bool saveDirty = false;
        int factionIndex = 0;
        int rankIndex = 0;
        int nodeIndex = 0;
        int rumorIndex = 0;
        int posseStrength = 0;
        int missionProgress = 0;
        int simulationStep = 0;
        int localPlayerFactionId = -1;
        int focusedFactionBindingId = -1;
        int gameDay = -1;
        int gameHour = -1;
        int lastDailyPrimeDay = -1;
        int directivesIssuedDay = -1;
        uint64_t nextRumorTickMs = 0;
        uint64_t nextWorldTickMs = 0;
        uint64_t nextAutosaveTickMs = 0;
        uint64_t nextCombatRetaskTickMs = 0;
        uint64_t nextRegionScanTickMs = 0;
        uint64_t nextNeighborPulseTickMs = 0;
        uint64_t nextDiagnosticsTickMs = 0;
        int runtimeHealthScore = 0;
        int unresolvedBindingCount = 0;
        int proxyAnchorCount = 0;
        int diagnosticsWrites = 0;
        int diagnosticsLastDay = -1;
        int bulletinLastDay = -1;
        bool diagnosticsDirty = false;
        char lastToast[kMaxToastText] = "Code RED Faction War v26 booted";
        MissionOffer activeMission{};
        PosseOrder posseOrder = PosseOrder::Follow;
        std::array<SpawnedActorState, kMaxSquadActors> spawnedActors{};
        std::array<FactionBinding, std::size(kSeedFactions)> factionBindings{};
        std::array<PendingConflictChain, 4> pendingChains{};
        std::array<RegionDirective, 4> regionDirectives{};
        std::array<RegionPressureFront, 4> regionFronts{};
        std::array<RegionCadence, 4> regionCadences{};
        std::array<RegionLogistics, 4> regionLogistics{};
        std::array<RegionCivilianClimate, 4> regionClimate{};
        std::array<RegionCampaignOutlook, 4> regionCampaigns{};
        TheaterSummary theaterSummary{};
        TownAssaultState townAssault{};
        RegionalShootoutState regionalShootout{};
        int activeFriendlyCount = 0;
        int activeEnemyCount = 0;
        int activeLawCount = 0;
        int activeTownAttackerCount = 0;
        char recentEvents[6][128]{};
        int recentEventCount = 0;
        int recentEventCursor = 0;
        char autoRegionNodeId[48]{};
        std::vector<RuntimeNode> nodes{};
    };


    RuntimeState gState{};

    void PushToast(const char* text);
    void LogLine(const char* text);
    int CountUnresolvedBindings();
    int CountProxyAnchors();
    int EvaluateRuntimeHealthScore();
    void WriteDiagnosticsReport(bool force);
    void MarkDiagnosticsDirty();
    void AppendRecentEvent(const char* text);
    const CodeRedTuneProfilesV26::TuneNodeProfile* FindTuneProfile(const char* nodeId);
    int FindNodeIndexById(const char* nodeId);
    int FindResolvedAnchorSourceIndex(const RuntimeNode& node);
    bool GetResolvedNodeAnchor(const RuntimeNode& node, Vector3* outPosition, float* outHeading, const char** outSourceNodeId = nullptr, bool* outUsedProxy = nullptr);
    int FindNearestAnchoredNodeIndex(float radius);
    bool RuntimeDegradedMode();
    void RefreshAutoRegionFocus();
    bool CurrentNodeSupportsRegionalShootout(const RuntimeNode& node);
    bool CurrentNodeSupportsTownAssault(const RuntimeNode& node);
    const char* DeterminePreferredAutoEvent(const RuntimeNode& node);
    const char* DescribeEntryConflictBias(const RuntimeNode& node);
    bool AutoEventWantsMountedOutlaws(const RuntimeNode& node);
    bool AutoEventWantsMountedLaw(const RuntimeNode& node);
    int DetermineAutoEventCooldownMs(const RuntimeNode& node, const char* preferredEvent, bool dailyPending);
    bool NodeSupportsAutoBattle(const RuntimeNode& node);
    int QueryGameDay();
    const char* DetermineLawFactionForNode(const RuntimeNode& node);
    const char* DetermineOutlawPressureFaction(const RuntimeNode& node);
    int QueryGameHour();
    bool HourInWindow(int hour, int startHour, int endHour);
    bool IsNodeActiveHour(const RuntimeNode& node, int hour);
    bool NodeNeedsDailyActivity(const RuntimeNode& node);
    void AssignNodeDailyProfile(RuntimeNode& node);
    int ComputeNodeHotness(const RuntimeNode& node);
    int FindRegionalHotNodeIndex(const char* regionName);
    void PrimeDailyFrontier();
    void RefreshGameClockState();
    void MarkNodeEventTriggered(RuntimeNode& node, const char* eventLabel);
    void StartRegionalShootoutEvent();
    void StartTownAssaultEvent();
    void TickRegionalShootout();
    void RefreshLocalState(RuntimeNode& node);
    const char* DetermineRoadControlState(const RuntimeNode& node);
    int ComputeRoutePressure(const RuntimeNode& node);
    int ComputeEscortNeed(const RuntimeNode& node);
    void RefreshRoadControl(RuntimeNode& node);
    void PropagateCorridorPressure();
    float DistanceSquared(const Vector3& a, const Vector3& b);
    void GenerateMissionFromCurrentState();
    bool IsPlayerNearNode(const RuntimeNode& node, float radius);
    RuntimeNode* FindNodeById(const char* nodeId);
    const CodeRedFactionSeedV26::SeedFaction* FindSeedFaction(const char* engineFaction);
    bool IsLawFactionName(const char* engineFaction);
    int FindNeighborNodeSupportingFaction(const RuntimeNode& battleNode, const char* faction, bool preferTransport, bool preferOutlaw);
    bool DispatchNeighborReinforcement(RuntimeNode& battleNode, const char* faction, SpawnedRole role, bool mounted, int count, bool preferTransport, bool preferOutlaw, const char* label);
    void ApplyRegionalBattleShock(RuntimeNode& centerNode, const char* winningFaction, const char* losingFaction, bool attackersWon);
    bool OccupationActive(const RuntimeNode& node);
    void ExpireOccupationStates();
    void ApplyOccupationOutcome(RuntimeNode& node, const char* winningFaction, bool attackersWon, const char* battleKind);
    void TickRegionalBackgroundPressure();
    void GenerateDailyRegionDirectives();
    const RegionDirective* FindDirectiveForRegion(const char* regionName);
    const RegionPressureFront* FindFrontForRegion(const char* regionName);
    RegionCadence* FindCadenceMutable(const char* regionName);
    const RegionCadence* FindCadenceForRegion(const char* regionName);
    void RefreshRegionCadences();
    const char* CadenceStateName(const RuntimeNode& node);
    int CadenceFatigueForNode(const RuntimeNode& node);
    int CadenceRecoveryForNode(const RuntimeNode& node);
    RegionLogistics* FindLogisticsMutable(const char* regionName);
    const RegionLogistics* FindLogisticsForRegion(const char* regionName);
    void RefreshRegionLogistics();
    const char* LogisticsStateName(const RuntimeNode& node);
    int LogisticsStockForNode(const RuntimeNode& node);
    int LogisticsConvoyForNode(const RuntimeNode& node);
    const char* LogisticsBattleProfile(const RuntimeNode& node);
    RegionCivilianClimate* FindClimateMutable(const char* regionName);
    const RegionCivilianClimate* FindClimateForRegion(const char* regionName);
    void RefreshRegionClimate();
    const char* ClimateStateName(const RuntimeNode& node);
    int ClimateSupportForNode(const RuntimeNode& node);
    int ClimatePanicForNode(const RuntimeNode& node);
    int ClimateRepressionForNode(const RuntimeNode& node);
    int ClimateRumorTrustForNode(const RuntimeNode& node);
    RegionCampaignOutlook* FindCampaignMutable(const char* regionName);
    const RegionCampaignOutlook* FindCampaignForRegion(const char* regionName);
    void RefreshRegionCampaign();
    void RefreshTheaterSummary();
    const char* CampaignStateName(const RuntimeNode& node);
    int CampaignLawControlForNode(const RuntimeNode& node);
    int CampaignOutlawControlForNode(const RuntimeNode& node);
    int CampaignCivilianTiltForNode(const RuntimeNode& node);
    const char* TheaterStateName();
    int TheaterPlayerMomentum();
    void WriteDailyBulletin();
    int ApplyLogisticsCountModifier(const RuntimeNode& node, int count, SpawnedRole role, bool mounted);
    bool LogisticsAllowsMounted(const RuntimeNode& node, SpawnedRole role);
    int LogisticsWaveDelayMs(const RuntimeNode& node);
    int LogisticsResolveDurationMs(const RuntimeNode& node);
    int CountActiveRegionFronts();
    const char* FrontStateName(const RuntimeNode& node);
    const char* DirectiveForNode(const RuntimeNode& node);
    void RefreshRegionFronts();
    void PropagateMultiFrontPressure();
    const char* AdjacentRegionsCsv(const char* regionName);
    const char* DirectiveDisplayName(const char* directiveName);
    int ComputeCivilianWeight(const RuntimeNode& node);
    int ComputeOutlawWeight(const RuntimeNode& node);
    int ComputeLawWeight(const RuntimeNode& node);
    int ComputeWagonWeight(const RuntimeNode& node);
    const char* DetermineTrafficState(const RuntimeNode& node);
    const char* DeterminePopulationProfile(const RuntimeNode& node);
    void RefreshNodeAtmosphere(RuntimeNode& node);
    int ScoreNeighborResponder(const RuntimeNode& battleNode, const RuntimeNode& sourceNode, const char* faction, bool preferTransport, bool preferOutlaw);
    int ComputeReinforcementCount(const RuntimeNode& battleNode, const RuntimeNode& sourceNode, SpawnedRole role, bool mounted, int requestedCount);
    void SpawnSquad(const char* sourceFaction, int requestedCount, SpawnedRole role, bool companionSquad, const RuntimeNode* nodeContext, bool mounted);
    const char* PendingConflictTypeName(PendingConflictType type);
    int CountPendingConflictChains();
    int FindConflictChainTargetIndex(const RuntimeNode& centerNode, const char* winningFaction, const char* losingFaction, bool attackersWon, PendingConflictType* outType);
    void ScheduleConflictChain(const RuntimeNode& centerNode, const char* winningFaction, const char* losingFaction, bool attackersWon);
    void TickPendingConflictChains();

    constexpr std::array<const char*, 4> kRanks = {
        "Outsider",
        "Associate",
        "Lieutenant",
        "Leader"
    };

    void CopyString(char* dst, std::size_t dstSize, const char* src)
    {
        if (!dst || dstSize == 0)
        {
            return;
        }
        if (!src)
        {
            dst[0] = '\0';
            return;
        }
        std::snprintf(dst, dstSize, "%s", src);
    }

    bool StringEquals(const char* a, const char* b)
    {
        if (!a || !b)
        {
            return false;
        }
        return std::strcmp(a, b) == 0;
    }

    bool ContainsCsvToken(const char* csv, const char* token)
    {
        if (!csv || !token || !csv[0] || !token[0])
        {
            return false;
        }

        std::string haystack = csv;
        std::string needle = token;
        std::stringstream ss(haystack);
        std::string item;
        while (std::getline(ss, item, ','))
        {
            if (item == needle)
            {
                return true;
            }
        }
        return false;
    }

    int ClampInt(int value, int low, int high)
    {
        if (value < low)
        {
            return low;
        }
        if (value > high)
        {
            return high;
        }
        return value;
    }

    int PositiveMod(int value, int mod)
    {
        const int r = value % mod;
        return r < 0 ? r + mod : r;
    }

    int QueryGameDay()
    {
        return GAMECLOCK::GET_DAY();
    }

    int QueryGameHour()
    {
        return GAMECLOCK::GET_HOUR();
    }

    bool HourInWindow(int hour, int startHour, int endHour)
    {
        if (startHour == endHour)
        {
            return true;
        }
        if (startHour < endHour)
        {
            return hour >= startHour && hour < endHour;
        }
        return hour >= startHour || hour < endHour;
    }

    bool NodeSupportsAutoBattle(const RuntimeNode& node)
    {
        return CurrentNodeSupportsTownAssault(node) || CurrentNodeSupportsRegionalShootout(node);
    }

    bool IsNodeActiveHour(const RuntimeNode& node, int hour)
    {
        if (hour < 0)
        {
            return true;
        }
        return HourInWindow(hour, node.activeStartHour, node.activeEndHour);
    }

    bool NodeNeedsDailyActivity(const RuntimeNode& node)
    {
        if (!(NodeSupportsAutoBattle(node) && gState.gameDay >= 0 && node.lastTriggeredDay != gState.gameDay))
        {
            return false;
        }
        const RegionCadence* cadence = FindCadenceForRegion(node.regionName);
        if (!cadence)
        {
            return true;
        }
        if (StringEquals(cadence->cadenceState, "spent") && node.dailyTriggerCount > 0)
        {
            return false;
        }
        if (StringEquals(cadence->cadenceState, "recovering") && node.dailyTriggerCount > 0)
        {
            return false;
        }
        return true;
    }

    void AssignNodeDailyProfile(RuntimeNode& node)
    {
        node.activeStartHour = 8;
        node.activeEndHour = 20;
        if (StringEquals(node.contextTag, "law_town"))
        {
            node.activeStartHour = 10;
            node.activeEndHour = 18;
        }
        else if (StringEquals(node.contextTag, "black_market"))
        {
            node.activeStartHour = 18;
            node.activeEndHour = 3;
        }
        else if (StringEquals(node.contextTag, "fort_war") || StringEquals(node.contextTag, "bandito_outpost"))
        {
            node.activeStartHour = 9;
            node.activeEndHour = 21;
        }
        else if (StringEquals(node.contextTag, "camp_hideout") || StringEquals(node.contextTag, "rustler_hideout"))
        {
            node.activeStartHour = 7;
            node.activeEndHour = 22;
        }
        else if (StringEquals(node.contextTag, "mine_hideout") || StringEquals(node.contextTag, "rail_checkpoint"))
        {
            node.activeStartHour = 8;
            node.activeEndHour = 18;
        }
        else if (StringEquals(node.contextTag, "roadside_robbery") || StringEquals(node.contextTag, "border_crossing") || StringEquals(node.contextTag, "escort_crossroads"))
        {
            node.activeStartHour = 6;
            node.activeEndHour = 20;
        }
        else if (StringEquals(node.contextTag, "ghost_town"))
        {
            node.activeStartHour = 19;
            node.activeEndHour = 4;
        }
    }

    int ComputeNodeHotness(const RuntimeNode& node)
    {
        int score = node.heat + node.pressure + node.fear / 2 + node.fortification / 3;
        if (node.contested)
        {
            score += 25;
        }
        if (OccupationActive(node))
        {
            score += IsLawFactionName(node.occupationFaction) ? 12 : 16;
        }
        if (NodeSupportsAutoBattle(node))
        {
            score += 10;
        }
        if (NodeNeedsDailyActivity(node))
        {
            score += 40;
        }
        const RegionDirective* directive = FindDirectiveForRegion(node.regionName);
        if (directive)
        {
            if (StringEquals(directive->primaryNodeId, node.nodeId))
            {
                score += 18;
            }
            if (StringEquals(directive->directiveName, "crackdown") && (StringEquals(node.contextTag, "law_town") || StringEquals(node.contextTag, "rail_checkpoint")))
            {
                score += 10;
            }
            else if (StringEquals(directive->directiveName, "smuggling") && (StringEquals(node.contextTag, "black_market") || ContainsCsvToken(node.strategicTagsCsv, "transport_post")))
            {
                score += 12;
            }
            else if (StringEquals(directive->directiveName, "raid") && (ContainsCsvToken(node.strategicTagsCsv, "outlaw_hideout") || ContainsCsvToken(node.strategicTagsCsv, "raid_origin") || StringEquals(node.contextTag, "camp_hideout") || StringEquals(node.contextTag, "rustler_hideout")))
            {
                score += 12;
            }
            else if (StringEquals(directive->directiveName, "fortify") && (ContainsCsvToken(node.strategicTagsCsv, "war_anchor") || StringEquals(node.contextTag, "fort_war")))
            {
                score += 12;
            }
            else if (StringEquals(directive->directiveName, "scavenge") && (StringEquals(node.contextTag, "ghost_town") || StringEquals(node.contextTag, "mine_hideout")))
            {
                score += 8;
            }
        }
        score += node.outlawWeight / 10;
        score += node.lawWeight / 12;
        score += node.wagonWeight / 14;
        if (node.civilianWeight >= 60 && !node.contested)
        {
            score += 4;
        }
        if (!IsNodeActiveHour(node, gState.gameHour))
        {
            score -= 10;
        }
        const RegionCadence* cadence = FindCadenceForRegion(node.regionName);
        if (cadence)
        {
            if (StringEquals(cadence->cadenceState, "surging")) score += 10;
            else if (StringEquals(cadence->cadenceState, "active")) score += 4;
            else if (StringEquals(cadence->cadenceState, "strained")) score -= 5;
            else if (StringEquals(cadence->cadenceState, "recovering")) score -= 10;
            else if (StringEquals(cadence->cadenceState, "spent")) score -= 14;
            else if (StringEquals(cadence->cadenceState, "quiet")) score -= 8;
        }
        const RegionLogistics* logistics = FindLogisticsForRegion(node.regionName);
        if (logistics)
        {
            score += (100 - logistics->stock) / 8;
            score += logistics->convoyPressure / 10;
            if (StringEquals(logistics->supportState, "starved")) score += 12;
            else if (StringEquals(logistics->supportState, "strained")) score += 8;
            else if (StringEquals(logistics->supportState, "convoys_hot")) score += 6;
            else if (StringEquals(logistics->supportState, "recovering")) score -= 6;
            if ((StringEquals(node.roadControlState, "smuggler_lane") || StringEquals(node.roadControlState, "wagon_route") || StringEquals(node.roadControlState, "supply_lane")) && logistics->convoyPressure > 45)
            {
                score += 8;
            }
        }
        const RegionCivilianClimate* climate = FindClimateForRegion(node.regionName);
        if (climate)
        {
            if (StringEquals(climate->climateState, "supportive"))
            {
                if (!IsLawFactionName(node.controller) || StringEquals(node.contextTag, "black_market") || ContainsCsvToken(node.strategicTagsCsv, "outlaw_hideout")) score += 10;
                if (node.wagonWeight >= 55) score += 4;
            }
            else if (StringEquals(climate->climateState, "talkative"))
            {
                if (IsLawFactionName(node.controller) || StringEquals(node.contextTag, "law_town") || StringEquals(node.contextTag, "rail_checkpoint")) score += 9;
                if (ContainsCsvToken(node.strategicTagsCsv, "transport_post")) score += 4;
            }
            else if (StringEquals(climate->climateState, "panicked"))
            {
                score += 5;
                if (StringEquals(node.contextTag, "law_town") || StringEquals(node.contextTag, "ghost_town")) score += 5;
            }
            else if (StringEquals(climate->climateState, "terrorized") || StringEquals(climate->climateState, "cowed"))
            {
                score += 4;
                if (IsLawFactionName(node.controller)) score += 6;
                else score -= 3;
            }
        }
        const RegionCampaignOutlook* campaign = FindCampaignForRegion(node.regionName);
        if (campaign)
        {
            if (StringEquals(campaign->campaignState, "knife_edge")) score += 8;
            else if (StringEquals(campaign->campaignState, "marshal_grip") && IsLawFactionName(node.controller)) score += 8;
            else if (StringEquals(campaign->campaignState, "outlaw_domain") && !IsLawFactionName(node.controller)) score += 10;
            else if (StringEquals(campaign->campaignState, "law_advancing") && IsLawFactionName(node.controller)) score += 5;
            else if (StringEquals(campaign->campaignState, "outlaw_ascending") && !IsLawFactionName(node.controller)) score += 6;
            else if (StringEquals(campaign->campaignState, "shattered")) score += 6;
        }
        return score;
    }

    int FindRegionalHotNodeIndex(const char* regionName)
    {
        int bestIndex = -1;
        int bestScore = -999999;
        for (int i = 0; i < static_cast<int>(gState.nodes.size()); ++i)
        {
            const RuntimeNode& node = gState.nodes[static_cast<std::size_t>(i)];
            if (!StringEquals(node.regionName, regionName))
            {
                continue;
            }
            const int score = ComputeNodeHotness(node);
            if (score > bestScore)
            {
                bestScore = score;
                bestIndex = i;
            }
        }
        return bestIndex;
    }

    void PrimeDailyFrontier()
    {
        if (gState.gameDay < 0 || gState.lastDailyPrimeDay == gState.gameDay)
        {
            return;
        }
        gState.lastDailyPrimeDay = gState.gameDay;
        for (RuntimeNode& node : gState.nodes)
        {
            node.dailyTriggerCount = 0;
            if (OccupationActive(node))
            {
                if (IsLawFactionName(node.occupationFaction))
                {
                    node.fortification = ClampInt(node.fortification + 3, 0, 100);
                    node.heat = ClampInt(node.heat + 2, 0, 100);
                    node.fear = ClampInt(node.fear + 2, 0, 100);
                }
                else
                {
                    node.pressure = ClampInt(node.pressure + 4, 0, 100);
                    node.heat = ClampInt(node.heat + 4, 0, 100);
                    node.fear = ClampInt(node.fear + 5, 0, 100);
                }
            }
            if (!NodeSupportsAutoBattle(node))
            {
                RefreshLocalState(node);
                RefreshNodeAtmosphere(node);
        RefreshRoadControl(node);
                continue;
            }
            if (StringEquals(node.contextTag, "law_town"))
            {
                node.heat = ClampInt(node.heat + 6, 0, 100);
                node.fear = ClampInt(node.fear + 4, 0, 100);
            }
            else if (StringEquals(node.contextTag, "black_market"))
            {
                node.heat = ClampInt(node.heat + 8, 0, 100);
                node.pressure = ClampInt(node.pressure + 6, 0, 100);
            }
            else if (StringEquals(node.contextTag, "fort_war") || StringEquals(node.contextTag, "bandito_outpost"))
            {
                node.pressure = ClampInt(node.pressure + 8, 0, 100);
                node.heat = ClampInt(node.heat + 7, 0, 100);
            }
            else if (StringEquals(node.contextTag, "camp_hideout") || StringEquals(node.contextTag, "rustler_hideout"))
            {
                node.pressure = ClampInt(node.pressure + 7, 0, 100);
                node.heat = ClampInt(node.heat + 5, 0, 100);
            }
            else if (StringEquals(node.contextTag, "mine_hideout") || StringEquals(node.contextTag, "rail_checkpoint"))
            {
                node.heat = ClampInt(node.heat + 5, 0, 100);
                node.pressure = ClampInt(node.pressure + 4, 0, 100);
            }
            else
            {
                node.heat = ClampInt(node.heat + 4, 0, 100);
                node.pressure = ClampInt(node.pressure + 4, 0, 100);
            }
            const RegionCadence* cadence = FindCadenceForRegion(node.regionName);
            if (cadence)
            {
                if (StringEquals(cadence->cadenceState, "recovering") || StringEquals(cadence->cadenceState, "spent"))
                {
                    node.heat = ClampInt(node.heat - 3, 0, 100);
                    node.pressure = ClampInt(node.pressure - 3, 0, 100);
                    node.fear = ClampInt(node.fear - 2, 0, 100);
                    node.supply = ClampInt(node.supply + 2, 0, 100);
                    node.nextAutoEventAllowedMs = GetTickCount64() + 14000;
                }
                else if (StringEquals(cadence->cadenceState, "surging"))
                {
                    node.heat = ClampInt(node.heat + 2, 0, 100);
                    node.pressure = ClampInt(node.pressure + 2, 0, 100);
                }
                else
                {
                    node.nextAutoEventAllowedMs = 0;
                }
            }
            else
            {
                node.nextAutoEventAllowedMs = 0;
            }
            const RegionLogistics* logistics = FindLogisticsForRegion(node.regionName);
            if (logistics)
            {
                if (StringEquals(logistics->supportState, "starved"))
                {
                    node.supply = ClampInt(node.supply - 6, 0, 100);
                    node.escortNeed = ClampInt(node.escortNeed + 4, 0, 100);
                    node.routePressure = ClampInt(node.routePressure + 4, 0, 100);
                }
                else if (StringEquals(logistics->supportState, "strained"))
                {
                    node.supply = ClampInt(node.supply - 3, 0, 100);
                    node.escortNeed = ClampInt(node.escortNeed + 2, 0, 100);
                }
                else if (StringEquals(logistics->supportState, "fortifying"))
                {
                    node.supply = ClampInt(node.supply + 2, 0, 100);
                    node.fortification = ClampInt(node.fortification + 2, 0, 100);
                }
                else if (StringEquals(logistics->supportState, "recovering"))
                {
                    node.supply = ClampInt(node.supply + 3, 0, 100);
                    node.routePressure = ClampInt(node.routePressure - 2, 0, 100);
                }
            }
            const RegionCivilianClimate* climate = FindClimateForRegion(node.regionName);
            if (climate)
            {
                if (StringEquals(climate->climateState, "supportive"))
                {
                    if (!IsLawFactionName(node.controller))
                    {
                        node.supply = ClampInt(node.supply + 2, 0, 100);
                        node.pressure = ClampInt(node.pressure + 2, 0, 100);
                    }
                    else
                    {
                        node.routePressure = ClampInt(node.routePressure + 1, 0, 100);
                    }
                }
                else if (StringEquals(climate->climateState, "talkative"))
                {
                    node.heat = ClampInt(node.heat + 2, 0, 100);
                    node.routePressure = ClampInt(node.routePressure + 2, 0, 100);
                }
                else if (StringEquals(climate->climateState, "panicked"))
                {
                    node.fear = ClampInt(node.fear + 3, 0, 100);
                    node.heat = ClampInt(node.heat + 2, 0, 100);
                }
                else if (StringEquals(climate->climateState, "terrorized") || StringEquals(climate->climateState, "cowed"))
                {
                    node.fear = ClampInt(node.fear + 4, 0, 100);
                    if (IsLawFactionName(node.controller))
                    {
                        node.fortification = ClampInt(node.fortification + 2, 0, 100);
                    }
                    else
                    {
                        node.civilianWeight = ClampInt(node.civilianWeight - 4, 0, 100);
                    }
                }
            }
            RefreshLocalState(node);
            RefreshNodeAtmosphere(node);
            RefreshRoadControl(node);
        }
        gState.saveDirty = true;
        char msg[160]{};
        std::snprintf(msg, sizeof(msg), "Frontier day %d stirred new gang movement", gState.gameDay);
        PushToast(msg);
        AppendRecentEvent(msg);
    }

    void RefreshGameClockState()
    {
        gState.gameDay = QueryGameDay();
        gState.gameHour = QueryGameHour();
        ExpireOccupationStates();
        PrimeDailyFrontier();
        RefreshRegionLogistics();
        RefreshRegionClimate();
        RefreshRegionCampaign();
        RefreshTheaterSummary();
        GenerateDailyRegionDirectives();
        RefreshRegionLogistics();
        RefreshRegionClimate();
        RefreshRegionCampaign();
        RefreshTheaterSummary();
        WriteDailyBulletin();
    }

    const char* DirectiveDisplayName(const char* directiveName)
    {
        if (!directiveName || !directiveName[0])
        {
            return "None";
        }
        if (StringEquals(directiveName, "crackdown")) return "Crackdown";
        if (StringEquals(directiveName, "smuggling")) return "Smuggling Window";
        if (StringEquals(directiveName, "raid")) return "Raid Muster";
        if (StringEquals(directiveName, "scavenge")) return "Scavenger Rush";
        if (StringEquals(directiveName, "fortify")) return "Fortify March";
        return directiveName;
    }

    int ComputeCivilianWeight(const RuntimeNode& node)
    {
        int weight = 30;
        if (StringEquals(node.contextTag, "law_town")) weight = 72;
        else if (StringEquals(node.contextTag, "black_market")) weight = 48;
        else if (StringEquals(node.contextTag, "rail_checkpoint")) weight = 34;
        else if (StringEquals(node.contextTag, "escort_crossroads") || StringEquals(node.contextTag, "border_crossing")) weight = 40;
        else if (StringEquals(node.contextTag, "ghost_town")) weight = 8;
        else if (StringEquals(node.contextTag, "mine_hideout")) weight = 16;
        else if (StringEquals(node.contextTag, "camp_hideout") || StringEquals(node.contextTag, "rustler_hideout")) weight = 12;
        else if (StringEquals(node.contextTag, "fort_war")) weight = 14;

        const char* directive = DirectiveForNode(node);
        if (StringEquals(directive, "crackdown")) weight -= 12;
        else if (StringEquals(directive, "smuggling")) weight -= 8;
        else if (StringEquals(directive, "raid")) weight -= 16;
        else if (StringEquals(directive, "fortify")) weight -= 10;
        else if (StringEquals(directive, "scavenge")) weight += 4;

        if (node.contested) weight -= 18;
        if (OccupationActive(node))
        {
            if (IsLawFactionName(node.occupationFaction)) weight -= 18;
            else weight -= 24;
        }
        const RegionLogistics* logistics = FindLogisticsForRegion(node.regionName);
        if (logistics)
        {
            if (StringEquals(logistics->supportState, "starved")) weight -= 14;
            else if (StringEquals(logistics->supportState, "strained")) weight -= 8;
            else if (StringEquals(logistics->supportState, "convoys_hot")) weight -= 4;
            else if (StringEquals(logistics->supportState, "searched")) weight -= 10;
        }
        if (!IsNodeActiveHour(node, gState.gameHour)) weight -= 10;
        return ClampInt(weight, 0, 100);
    }

    int ComputeOutlawWeight(const RuntimeNode& node)
    {
        int weight = IsLawFactionName(node.controller) ? 18 : 42;
        if (StringEquals(node.contextTag, "black_market")) weight += 18;
        else if (StringEquals(node.contextTag, "camp_hideout") || StringEquals(node.contextTag, "rustler_hideout")) weight += 22;
        else if (StringEquals(node.contextTag, "mine_hideout")) weight += 16;
        else if (StringEquals(node.contextTag, "fort_war") || StringEquals(node.contextTag, "bandito_outpost")) weight += 20;
        else if (StringEquals(node.contextTag, "law_town")) weight -= 8;

        const char* directive = DirectiveForNode(node);
        if (StringEquals(directive, "crackdown")) weight += 10;
        else if (StringEquals(directive, "smuggling")) weight += 18;
        else if (StringEquals(directive, "raid")) weight += 24;
        else if (StringEquals(directive, "fortify")) weight += 8;
        else if (StringEquals(directive, "scavenge")) weight += 12;

        if (node.contested) weight += 14;
        if (OccupationActive(node))
        {
            weight += IsLawFactionName(node.occupationFaction) ? -8 : 18;
        }
        const RegionLogistics* logistics = FindLogisticsForRegion(node.regionName);
        if (logistics)
        {
            if (StringEquals(logistics->supportState, "starved")) weight += 10;
            else if (StringEquals(logistics->supportState, "convoys_hot")) weight += 8;
            else if (StringEquals(logistics->supportState, "fortifying")) weight -= 6;
            else if (StringEquals(logistics->supportState, "searched")) weight -= 6;
        }
        if (!IsNodeActiveHour(node, gState.gameHour)) weight -= 6;
        return ClampInt(weight, 0, 100);
    }

    int ComputeLawWeight(const RuntimeNode& node)
    {
        int weight = IsLawFactionName(node.controller) ? 44 : 18;
        if (StringEquals(node.contextTag, "law_town")) weight += 24;
        else if (StringEquals(node.contextTag, "rail_checkpoint") || StringEquals(node.contextTag, "border_crossing")) weight += 18;
        else if (StringEquals(node.contextTag, "fort_war")) weight += 12;
        else if (StringEquals(node.contextTag, "black_market")) weight += 6;
        else if (StringEquals(node.contextTag, "ghost_town")) weight -= 8;

        const char* directive = DirectiveForNode(node);
        if (StringEquals(directive, "crackdown")) weight += 26;
        else if (StringEquals(directive, "smuggling")) weight += 12;
        else if (StringEquals(directive, "raid")) weight -= 6;
        else if (StringEquals(directive, "fortify")) weight += 18;
        else if (StringEquals(directive, "scavenge")) weight -= 10;

        if (node.contested) weight += 10;
        if (OccupationActive(node))
        {
            weight += IsLawFactionName(node.occupationFaction) ? 18 : -10;
        }
        const RegionLogistics* logistics = FindLogisticsForRegion(node.regionName);
        if (logistics)
        {
            if (StringEquals(logistics->supportState, "fortifying")) weight += 12;
            else if (StringEquals(logistics->supportState, "searched")) weight += 10;
            else if (StringEquals(logistics->supportState, "starved")) weight -= 10;
            else if (StringEquals(logistics->supportState, "convoys_hot")) weight += 6;
        }
        if (!IsNodeActiveHour(node, gState.gameHour)) weight -= 4;
        return ClampInt(weight, 0, 100);
    }

    int ComputeWagonWeight(const RuntimeNode& node)
    {
        int weight = 16;
        if (ContainsCsvToken(node.strategicTagsCsv, "transport_post") || StringEquals(node.contextTag, "escort_crossroads") || StringEquals(node.contextTag, "border_crossing")) weight += 28;
        if (StringEquals(node.contextTag, "black_market")) weight += 22;
        if (StringEquals(node.contextTag, "law_town")) weight += 12;
        if (StringEquals(node.contextTag, "ghost_town") || StringEquals(node.contextTag, "camp_hideout")) weight -= 10;

        const char* directive = DirectiveForNode(node);
        if (StringEquals(directive, "crackdown")) weight += 14;
        else if (StringEquals(directive, "smuggling")) weight += 30;
        else if (StringEquals(directive, "raid")) weight += 10;
        else if (StringEquals(directive, "fortify")) weight += 18;
        else if (StringEquals(directive, "scavenge")) weight -= 8;

        if (node.contested) weight -= 8;
        if (OccupationActive(node))
        {
            weight += IsLawFactionName(node.occupationFaction) ? 6 : -6;
        }
        const RegionLogistics* logistics = FindLogisticsForRegion(node.regionName);
        if (logistics)
        {
            if (StringEquals(logistics->supportState, "convoys_hot")) weight += 16;
            else if (StringEquals(logistics->supportState, "fortifying")) weight += 10;
            else if (StringEquals(logistics->supportState, "starved")) weight -= 10;
        }
        if (!IsNodeActiveHour(node, gState.gameHour)) weight -= 6;
        return ClampInt(weight, 0, 100);
    }

    const char* DetermineTrafficState(const RuntimeNode& node)
    {
        if (node.contested)
        {
            return node.wagonWeight >= 55 ? "wagon_breakdown" : "gun_smoke_roads";
        }
        const RegionLogistics* logistics = FindLogisticsForRegion(node.regionName);
        if (logistics)
        {
            if (StringEquals(logistics->supportState, "starved")) return "thin_supply_trails";
            if (StringEquals(logistics->supportState, "convoys_hot")) return node.wagonWeight >= 70 ? "relief_convoys" : "escort_columns";
            if (StringEquals(logistics->supportState, "fortifying")) return "fortified_supply_lines";
            if (StringEquals(logistics->supportState, "searched")) return "searched_roads";
            if (StringEquals(logistics->supportState, "recovering")) return "slow_restock";
        }
        const char* directive = DirectiveForNode(node);
        if (StringEquals(directive, "crackdown"))
        {
            return node.lawWeight >= 70 ? "marshal_checkpoint_lines" : "road_searches";
        }
        if (StringEquals(directive, "smuggling"))
        {
            return node.wagonWeight >= 70 ? "smuggler_wagon_flow" : "quiet_cargo_runs";
        }
        if (StringEquals(directive, "raid"))
        {
            return node.outlawWeight >= 70 ? "raider_horse_columns" : "scout_riders";
        }
        if (StringEquals(directive, "fortify"))
        {
            return node.wagonWeight >= 55 ? "supply_column" : "garrison_shifts";
        }
        if (StringEquals(directive, "scavenge"))
        {
            return "salvage_trickles";
        }
        return node.travelFlavor[0] ? node.travelFlavor : "frontier_drift";
    }

    const char* DeterminePopulationProfile(const RuntimeNode& node)
    {
        if (node.contested)
        {
            if (node.lawWeight >= node.outlawWeight) return "lawline_vs_raiders";
            return "raiders_overrunning_civilians";
        }
        const RegionCivilianClimate* climate = FindClimateForRegion(node.regionName);
        if (climate)
        {
            if (StringEquals(climate->climateState, "terrorized") || StringEquals(climate->climateState, "cowed")) return "cowed_civilians";
            if (StringEquals(climate->climateState, "panicked")) return "fleeing_settlers";
            if (StringEquals(climate->climateState, "talkative") && (IsLawFactionName(node.controller) || StringEquals(node.contextTag, "law_town") || StringEquals(node.contextTag, "rail_checkpoint"))) return "informants_and_deputies";
            if (StringEquals(climate->climateState, "supportive") && !IsLawFactionName(node.controller)) return "sympathizers_and_fences";
            if (StringEquals(climate->climateState, "suspicious")) return "closed_doors";
        }
        const RegionLogistics* logistics = FindLogisticsForRegion(node.regionName);
        if (logistics)
        {
            if (StringEquals(logistics->supportState, "starved")) return "lean_raiders";
            if (StringEquals(logistics->supportState, "convoys_hot")) return "convoy_guards";
            if (StringEquals(logistics->supportState, "fortifying")) return "fortified_garrison";
            if (StringEquals(logistics->supportState, "searched")) return "search_parties";
            if (StringEquals(logistics->supportState, "recovering")) return "restocking_frontier";
        }
        const char* directive = DirectiveForNode(node);
        if (StringEquals(directive, "crackdown")) return node.lawWeight >= 70 ? "marshal_heavy" : "deputy_watch";
        if (StringEquals(directive, "smuggling")) return node.wagonWeight >= 70 ? "smuggler_wagons" : "quiet_black_market";
        if (StringEquals(directive, "raid")) return node.outlawWeight >= 68 ? "gang_muster" : "trail_scouts";
        if (StringEquals(directive, "fortify")) return node.lawWeight >= 60 ? "garrison_build_up" : "fortified_frontier";
        if (StringEquals(directive, "scavenge")) return "scavengers_and_miners";
        if (node.civilianWeight >= 60) return "settlers_and_traders";
        if (node.outlawWeight >= 60) return "outlaw_pressure";
        if (node.lawWeight >= 60) return "law_watch";
        return "mixed_frontier";
    }

    void RefreshNodeAtmosphere(RuntimeNode& node)
    {
        node.civilianWeight = ComputeCivilianWeight(node);
        node.outlawWeight = ComputeOutlawWeight(node);
        node.lawWeight = ComputeLawWeight(node);
        node.wagonWeight = ComputeWagonWeight(node);
        CopyString(node.trafficState, sizeof(node.trafficState), DetermineTrafficState(node));
        CopyString(node.populationProfile, sizeof(node.populationProfile), DeterminePopulationProfile(node));
    }

    int ScoreNeighborResponder(const RuntimeNode& battleNode, const RuntimeNode& sourceNode, const char* faction, bool preferTransport, bool preferOutlaw)
    {
        int score = sourceNode.supply + sourceNode.fortification + sourceNode.pressure / 2 - sourceNode.fear / 3;
        if (StringEquals(sourceNode.regionName, battleNode.regionName))
        {
            score += 10;
        }
        if (sourceNode.hasAnchor)
        {
            score += 3;
        }

        const char* directive = DirectiveForNode(battleNode);
        const bool factionIsLaw = IsLawFactionName(faction);
        if (preferTransport && ContainsCsvToken(sourceNode.strategicTagsCsv, "transport_post"))
        {
            score += 16;
        }
        if (preferOutlaw && (ContainsCsvToken(sourceNode.strategicTagsCsv, "outlaw_hideout") || ContainsCsvToken(sourceNode.strategicTagsCsv, "raid_origin") || ContainsCsvToken(sourceNode.strategicTagsCsv, "war_anchor")))
        {
            score += 18;
        }

        if (StringEquals(directive, "crackdown"))
        {
            if (factionIsLaw)
            {
                if (StringEquals(sourceNode.contextTag, "law_town") || StringEquals(sourceNode.contextTag, "rail_checkpoint") || ContainsCsvToken(sourceNode.strategicTagsCsv, "transport_post"))
                {
                    score += 24;
                }
                score += sourceNode.lawWeight / 3;
                score += sourceNode.fortification / 2;
                score += sourceNode.wagonWeight / 4;
            }
            else
            {
                if (ContainsCsvToken(sourceNode.strategicTagsCsv, "outlaw_hideout") || ContainsCsvToken(sourceNode.strategicTagsCsv, "raid_origin") || StringEquals(sourceNode.contextTag, "camp_hideout") || StringEquals(sourceNode.contextTag, "rustler_hideout"))
                {
                    score += 12;
                }
                score += sourceNode.outlawWeight / 3;
            }
        }
        else if (StringEquals(directive, "smuggling"))
        {
            if (factionIsLaw)
            {
                if (StringEquals(sourceNode.contextTag, "rail_checkpoint") || StringEquals(sourceNode.contextTag, "border_crossing") || StringEquals(sourceNode.contextTag, "law_town"))
                {
                    score += 20;
                }
                score += sourceNode.lawWeight / 4;
                score += sourceNode.wagonWeight / 3;
            }
            else
            {
                if (StringEquals(sourceNode.contextTag, "black_market") || ContainsCsvToken(sourceNode.strategicTagsCsv, "transport_post") || ContainsCsvToken(sourceNode.strategicTagsCsv, "outlaw_hideout"))
                {
                    score += 22;
                }
                score += sourceNode.wagonWeight / 2;
                score += sourceNode.outlawWeight / 3;
                score += sourceNode.supply / 3;
            }
        }
        else if (StringEquals(directive, "raid"))
        {
            if (factionIsLaw)
            {
                if (StringEquals(sourceNode.contextTag, "law_town") || StringEquals(sourceNode.contextTag, "fort_war") || ContainsCsvToken(sourceNode.strategicTagsCsv, "law_hub"))
                {
                    score += 18;
                }
                score += sourceNode.lawWeight / 3;
            }
            else
            {
                if (StringEquals(sourceNode.contextTag, "camp_hideout") || StringEquals(sourceNode.contextTag, "rustler_hideout") || ContainsCsvToken(sourceNode.strategicTagsCsv, "raid_origin") || ContainsCsvToken(sourceNode.strategicTagsCsv, "war_anchor"))
                {
                    score += 24;
                }
                score += sourceNode.outlawWeight / 2;
                score += sourceNode.pressure / 3;
            }
        }
        else if (StringEquals(directive, "fortify"))
        {
            if (factionIsLaw)
            {
                if (StringEquals(sourceNode.contextTag, "fort_war") || ContainsCsvToken(sourceNode.strategicTagsCsv, "war_anchor") || ContainsCsvToken(sourceNode.strategicTagsCsv, "transport_post"))
                {
                    score += 24;
                }
                score += sourceNode.fortification / 2;
                score += sourceNode.wagonWeight / 3;
            }
            else
            {
                if (StringEquals(sourceNode.contextTag, "bandito_outpost") || ContainsCsvToken(sourceNode.strategicTagsCsv, "war_anchor") || ContainsCsvToken(sourceNode.strategicTagsCsv, "outlaw_hideout"))
                {
                    score += 16;
                }
                score += sourceNode.outlawWeight / 3;
            }
        }
        else if (StringEquals(directive, "scavenge"))
        {
            if (StringEquals(sourceNode.contextTag, "ghost_town") || StringEquals(sourceNode.contextTag, "mine_hideout"))
            {
                score += 18;
            }
            score += sourceNode.outlawWeight / 4;
            score += sourceNode.civilianWeight / 5;
        }

        if (StringEquals(sourceNode.populationProfile, "marshal_heavy") || StringEquals(sourceNode.populationProfile, "deputy_watch"))
        {
            score += factionIsLaw ? 10 : -4;
        }
        else if (StringEquals(sourceNode.populationProfile, "smuggler_wagons") || StringEquals(sourceNode.populationProfile, "quiet_black_market"))
        {
            score += !factionIsLaw ? 8 : 6;
        }
        else if (StringEquals(sourceNode.populationProfile, "gang_muster") || StringEquals(sourceNode.populationProfile, "trail_scouts"))
        {
            score += !factionIsLaw ? 10 : -2;
        }
        else if (StringEquals(sourceNode.populationProfile, "garrison_build_up") || StringEquals(sourceNode.populationProfile, "fortified_frontier"))
        {
            score += factionIsLaw ? 10 : 3;
        }
        else if (StringEquals(sourceNode.populationProfile, "scavengers_and_miners"))
        {
            score += 4;
        }

        if (StringEquals(sourceNode.trafficState, "marshal_checkpoint_lines") || StringEquals(sourceNode.trafficState, "road_searches"))
        {
            score += factionIsLaw ? 8 : -3;
        }
        else if (StringEquals(sourceNode.trafficState, "smuggler_wagon_flow") || StringEquals(sourceNode.trafficState, "quiet_cargo_runs"))
        {
            score += !factionIsLaw ? 8 : 5;
        }
        else if (StringEquals(sourceNode.trafficState, "raider_horse_columns") || StringEquals(sourceNode.trafficState, "scout_riders"))
        {
            score += !factionIsLaw ? 10 : 0;
        }
        else if (StringEquals(sourceNode.trafficState, "supply_column") || StringEquals(sourceNode.trafficState, "garrison_shifts"))
        {
            score += factionIsLaw ? 8 : 2;
        }

        const RegionLogistics* sourceLogistics = FindLogisticsForRegion(sourceNode.regionName);
        if (sourceLogistics)
        {
            if (StringEquals(sourceLogistics->supportState, "starved")) score -= 12;
            else if (StringEquals(sourceLogistics->supportState, "strained")) score -= 6;
            else if (StringEquals(sourceLogistics->supportState, "convoys_hot")) score += preferTransport ? 12 : 4;
            else if (StringEquals(sourceLogistics->supportState, "fortifying")) score += factionIsLaw ? 14 : -4;
            else if (StringEquals(sourceLogistics->supportState, "searched")) score += factionIsLaw ? 10 : -6;
        }
        if (!IsNodeActiveHour(sourceNode, gState.gameHour))
        {
            score -= 8;
        }
        return score;
    }

    int ComputeReinforcementCount(const RuntimeNode& battleNode, const RuntimeNode& sourceNode, SpawnedRole role, bool mounted, int requestedCount)
    {
        int count = requestedCount;
        const char* directive = DirectiveForNode(battleNode);
        if (StringEquals(directive, "crackdown") && role == SpawnedRole::Law)
        {
            ++count;
            if (sourceNode.lawWeight >= 70) ++count;
        }
        else if (StringEquals(directive, "smuggling"))
        {
            if (role == SpawnedRole::Rival || role == SpawnedRole::TownAttacker)
            {
                ++count;
                if (sourceNode.wagonWeight >= 70) ++count;
            }
            else if (role == SpawnedRole::Law && sourceNode.wagonWeight >= 65)
            {
                ++count;
            }
        }
        else if (StringEquals(directive, "raid"))
        {
            if (role == SpawnedRole::Rival || role == SpawnedRole::TownAttacker)
            {
                ++count;
                if (mounted) ++count;
            }
        }
        else if (StringEquals(directive, "fortify"))
        {
            if (role == SpawnedRole::Law)
            {
                ++count;
                if (sourceNode.fortification >= 55) ++count;
            }
        }
        else if (StringEquals(directive, "scavenge"))
        {
            count = ClampInt(count - 1, 1, 6);
        }

        if (sourceNode.populationProfile[0] && (StringEquals(sourceNode.populationProfile, "gang_muster") || StringEquals(sourceNode.populationProfile, "marshal_heavy") || StringEquals(sourceNode.populationProfile, "garrison_build_up")))
        {
            ++count;
        }
        count = ApplyLogisticsCountModifier(sourceNode, count, role, mounted);
        return ClampInt(count, 1, 8);
    }

    const RegionDirective* FindDirectiveForRegion(const char* regionName)
    {
        for (const RegionDirective& directive : gState.regionDirectives)
        {
            if (directive.active && StringEquals(directive.regionName, regionName))
            {
                return &directive;
            }
        }
        return nullptr;
    }

    const RegionPressureFront* FindFrontForRegion(const char* regionName)
    {
        for (const RegionPressureFront& front : gState.regionFronts)
        {
            if (front.active && StringEquals(front.regionName, regionName))
            {
                return &front;
            }
        }
        return nullptr;
    }


    RegionCadence* FindCadenceMutable(const char* regionName)
    {
        for (RegionCadence& cadence : gState.regionCadences)
        {
            if (cadence.active && StringEquals(cadence.regionName, regionName))
            {
                return &cadence;
            }
        }
        return nullptr;
    }

    const RegionCadence* FindCadenceForRegion(const char* regionName)
    {
        for (const RegionCadence& cadence : gState.regionCadences)
        {
            if (cadence.active && StringEquals(cadence.regionName, regionName))
            {
                return &cadence;
            }
        }
        return nullptr;
    }

    int CountActiveRegionFronts()
    {
        int count = 0;
        for (const RegionPressureFront& front : gState.regionFronts)
        {
            if (front.active && !StringEquals(front.frontState, "calm"))
            {
                ++count;
            }
        }
        return count;
    }

    const char* AdjacentRegionsCsv(const char* regionName)
    {
        if (StringEquals(regionName, "cholla_springs")) return "hennigans_stead,gaptooth_ridge";
        if (StringEquals(regionName, "gaptooth_ridge")) return "cholla_springs,rio_bravo";
        if (StringEquals(regionName, "hennigans_stead")) return "cholla_springs,rio_bravo";
        if (StringEquals(regionName, "rio_bravo")) return "gaptooth_ridge,hennigans_stead";
        return "";
    }

    void RefreshRegionFronts()
    {
        for (RegionPressureFront& front : gState.regionFronts)
        {
            front.active = false;
            front.lawPressure = 0;
            front.outlawPressure = 0;
            CopyString(front.frontState, sizeof(front.frontState), "calm");
        }

        int slot = 0;
        for (const RegionDirective& directive : gState.regionDirectives)
        {
            if (!directive.active || slot >= static_cast<int>(gState.regionFronts.size()))
            {
                continue;
            }
            RegionPressureFront front{};
            front.active = true;
            CopyString(front.regionName, sizeof(front.regionName), directive.regionName);
            const char* frontState = "calm";
            for (const RuntimeNode& node : gState.nodes)
            {
                if (!StringEquals(node.regionName, directive.regionName))
                {
                    continue;
                }
                int law = node.lawWeight + (IsLawFactionName(node.controller) ? (node.pressure / 2 + node.fortification / 2 + 6) : 0);
                int outlaw = node.outlawWeight + (!IsLawFactionName(node.controller) ? (node.heat / 2 + node.pressure / 2 + 6) : 0);
                if (node.contested)
                {
                    law += 10;
                    outlaw += 10;
                }
                if (gState.townAssault.active && StringEquals(gState.townAssault.nodeId, node.nodeId))
                {
                    law += 14;
                    outlaw += 18;
                }
                if (gState.regionalShootout.active && StringEquals(gState.regionalShootout.nodeId, node.nodeId))
                {
                    law += 12;
                    outlaw += 12;
                }
                front.lawPressure += law;
                front.outlawPressure += outlaw;
            }
            const int total = front.lawPressure + front.outlawPressure;
            const int diff = std::abs(front.lawPressure - front.outlawPressure);
            if (total < 130)
            {
                frontState = "calm";
            }
            else if (diff <= 24)
            {
                frontState = total >= 190 ? "two_front" : "tense";
            }
            else if (front.lawPressure > front.outlawPressure)
            {
                frontState = front.lawPressure >= 105 ? "law_surge" : "law_edge";
            }
            else
            {
                frontState = front.outlawPressure >= 105 ? "outlaw_push" : "outlaw_edge";
            }
            CopyString(front.frontState, sizeof(front.frontState), frontState);
            gState.regionFronts[static_cast<std::size_t>(slot++)] = front;
        }
    }

    void RefreshRegionCadences()
    {
        for (RegionCadence& cadence : gState.regionCadences)
        {
            cadence = RegionCadence{};
        }
        const char* regions[] = { "cholla_springs", "gaptooth_ridge", "hennigans_stead", "rio_bravo" };
        int slot = 0;
        for (const char* region : regions)
        {
            if (slot >= static_cast<int>(gState.regionCadences.size()))
            {
                break;
            }
            RegionCadence cadence{};
            cadence.active = true;
            CopyString(cadence.regionName, sizeof(cadence.regionName), region);
            const RegionPressureFront* front = FindFrontForRegion(region);
            const RegionDirective* directive = FindDirectiveForRegion(region);
            int contestedCount = 0;
            int occupationCount = 0;
            int routeLoad = 0;
            for (const RuntimeNode& node : gState.nodes)
            {
                if (!StringEquals(node.regionName, region))
                {
                    continue;
                }
                if (node.contested)
                {
                    ++contestedCount;
                    cadence.fatigue += 16;
                }
                if (OccupationActive(node))
                {
                    ++occupationCount;
                    cadence.fatigue += 8;
                }
                routeLoad += node.routePressure / 8;
                cadence.recovery += node.civilianWeight / 10;
                if (node.supply >= 60)
                {
                    cadence.recovery += 2;
                }
                if (node.fortification >= 55)
                {
                    cadence.recovery += 2;
                }
            }
            cadence.fatigue += routeLoad;
            cadence.recovery = ClampInt(cadence.recovery - contestedCount * 3 - occupationCount * 2, 0, 100);
            if (front)
            {
                cadence.momentum += std::abs(front->lawPressure - front->outlawPressure) / 10;
                if (StringEquals(front->frontState, "law_surge") || StringEquals(front->frontState, "outlaw_push"))
                {
                    cadence.fatigue += 10;
                    cadence.momentum += 8;
                }
                else if (StringEquals(front->frontState, "two_front"))
                {
                    cadence.fatigue += 14;
                    cadence.momentum += 6;
                }
                else if (StringEquals(front->frontState, "tense"))
                {
                    cadence.fatigue += 6;
                    cadence.momentum += 3;
                }
            }
            if (directive)
            {
                if (StringEquals(directive->directiveName, "raid") || StringEquals(directive->directiveName, "crackdown"))
                {
                    cadence.fatigue += 8;
                    cadence.momentum += 6;
                }
                else if (StringEquals(directive->directiveName, "fortify"))
                {
                    cadence.recovery += 8;
                }
                else if (StringEquals(directive->directiveName, "scavenge"))
                {
                    cadence.recovery += 5;
                }
            }
            if (gState.townAssault.active)
            {
                RuntimeNode* node = FindNodeById(gState.townAssault.nodeId);
                if (node && StringEquals(node->regionName, region))
                {
                    cadence.fatigue += 18;
                    cadence.momentum += 10;
                }
            }
            if (gState.regionalShootout.active)
            {
                RuntimeNode* node = FindNodeById(gState.regionalShootout.nodeId);
                if (node && StringEquals(node->regionName, region))
                {
                    cadence.fatigue += 12;
                    cadence.momentum += 7;
                }
            }
            cadence.fatigue = ClampInt(cadence.fatigue, 0, 100);
            cadence.recovery = ClampInt(cadence.recovery, 0, 100);
            cadence.momentum = ClampInt(cadence.momentum, 0, 100);
            const char* state = "active";
            if (cadence.fatigue >= 82 && cadence.recovery < 28)
            {
                state = "spent";
            }
            else if (cadence.fatigue >= 64)
            {
                state = "strained";
            }
            else if (cadence.recovery >= 56 && cadence.fatigue <= 34)
            {
                state = "recovering";
            }
            else if (cadence.momentum >= 18 && cadence.fatigue <= 72)
            {
                state = "surging";
            }
            else if ((!front || StringEquals(front->frontState, "calm")) && cadence.fatigue <= 22)
            {
                state = "quiet";
            }
            CopyString(cadence.cadenceState, sizeof(cadence.cadenceState), state);
            cadence.lastShiftDay = gState.gameDay;
            gState.regionCadences[static_cast<std::size_t>(slot++)] = cadence;
        }
    }

    const char* CadenceStateName(const RuntimeNode& node)
    {
        const RegionCadence* cadence = FindCadenceForRegion(node.regionName);
        return cadence ? cadence->cadenceState : "active";
    }

    int CadenceFatigueForNode(const RuntimeNode& node)
    {
        const RegionCadence* cadence = FindCadenceForRegion(node.regionName);
        return cadence ? cadence->fatigue : 0;
    }

    int CadenceRecoveryForNode(const RuntimeNode& node)
    {
        const RegionCadence* cadence = FindCadenceForRegion(node.regionName);
        return cadence ? cadence->recovery : 0;
    }

    RegionLogistics* FindLogisticsMutable(const char* regionName)
    {
        for (RegionLogistics& logistics : gState.regionLogistics)
        {
            if (logistics.active && StringEquals(logistics.regionName, regionName))
            {
                return &logistics;
            }
        }
        return nullptr;
    }

    const RegionLogistics* FindLogisticsForRegion(const char* regionName)
    {
        for (const RegionLogistics& logistics : gState.regionLogistics)
        {
            if (logistics.active && StringEquals(logistics.regionName, regionName))
            {
                return &logistics;
            }
        }
        return nullptr;
    }

    const char* LogisticsStateName(const RuntimeNode& node)
    {
        const RegionLogistics* logistics = FindLogisticsForRegion(node.regionName);
        return logistics ? logistics->supportState : "steady";
    }

    int LogisticsStockForNode(const RuntimeNode& node)
    {
        const RegionLogistics* logistics = FindLogisticsForRegion(node.regionName);
        return logistics ? logistics->stock : 50;
    }

    int LogisticsConvoyForNode(const RuntimeNode& node)
    {
        const RegionLogistics* logistics = FindLogisticsForRegion(node.regionName);
        return logistics ? logistics->convoyPressure : 0;
    }

    const char* LogisticsBattleProfile(const RuntimeNode& node)
    {
        const RegionLogistics* logistics = FindLogisticsForRegion(node.regionName);
        if (!logistics)
        {
            return "steady_front";
        }
        if (StringEquals(logistics->supportState, "starved")) return "lean_front";
        if (StringEquals(logistics->supportState, "strained")) return "strained_front";
        if (StringEquals(logistics->supportState, "convoys_hot")) return "convoy_front";
        if (StringEquals(logistics->supportState, "fortifying")) return "fortified_front";
        if (StringEquals(logistics->supportState, "searched")) return "searched_front";
        if (StringEquals(logistics->supportState, "recovering")) return "reforming_front";
        return "steady_front";
    }

    int ApplyLogisticsCountModifier(const RuntimeNode& node, int count, SpawnedRole role, bool mounted)
    {
        const RegionLogistics* logistics = FindLogisticsForRegion(node.regionName);
        if (!logistics)
        {
            return ClampInt(count, 1, 8);
        }

        if (StringEquals(logistics->supportState, "starved"))
        {
            count -= mounted ? 2 : 1;
            if (role == SpawnedRole::Law)
            {
                --count;
            }
        }
        else if (StringEquals(logistics->supportState, "strained"))
        {
            --count;
        }
        else if (StringEquals(logistics->supportState, "convoys_hot"))
        {
            if (role != SpawnedRole::Companion)
            {
                ++count;
            }
            if (mounted)
            {
                ++count;
            }
        }
        else if (StringEquals(logistics->supportState, "fortifying"))
        {
            if (role == SpawnedRole::Law)
            {
                count += 2;
            }
            else if (role == SpawnedRole::Rival || role == SpawnedRole::TownAttacker)
            {
                --count;
            }
        }
        else if (StringEquals(logistics->supportState, "searched"))
        {
            if (role == SpawnedRole::Law)
            {
                ++count;
            }
            else if (role != SpawnedRole::Companion)
            {
                --count;
            }
        }
        else if (StringEquals(logistics->supportState, "recovering"))
        {
            --count;
        }

        if (logistics->stock < 30 && mounted)
        {
            --count;
        }
        if (logistics->convoyPressure > 65 && role != SpawnedRole::Companion)
        {
            ++count;
        }
        return ClampInt(count, 1, 8);
    }

    bool LogisticsAllowsMounted(const RuntimeNode& node, SpawnedRole role)
    {
        const RegionLogistics* logistics = FindLogisticsForRegion(node.regionName);
        if (!logistics)
        {
            return true;
        }
        if (logistics->stock < 25 && role != SpawnedRole::Companion)
        {
            return false;
        }
        if (StringEquals(logistics->supportState, "starved") && role != SpawnedRole::Companion)
        {
            return false;
        }
        if (StringEquals(logistics->supportState, "recovering") && role == SpawnedRole::Law)
        {
            return false;
        }
        return true;
    }

    int LogisticsWaveDelayMs(const RuntimeNode& node)
    {
        const RegionLogistics* logistics = FindLogisticsForRegion(node.regionName);
        int delay = 12000;
        if (!logistics)
        {
            return delay;
        }
        if (StringEquals(logistics->supportState, "starved")) delay += 5000;
        else if (StringEquals(logistics->supportState, "strained")) delay += 2500;
        else if (StringEquals(logistics->supportState, "convoys_hot")) delay -= 2500;
        else if (StringEquals(logistics->supportState, "fortifying")) delay -= 3000;
        else if (StringEquals(logistics->supportState, "searched")) delay -= 1500;
        else if (StringEquals(logistics->supportState, "recovering")) delay += 1500;
        return ClampInt(delay, 7000, 20000);
    }

    int LogisticsResolveDurationMs(const RuntimeNode& node)
    {
        const RegionLogistics* logistics = FindLogisticsForRegion(node.regionName);
        int duration = 20000;
        if (!logistics)
        {
            return duration;
        }
        if (StringEquals(logistics->supportState, "starved")) duration -= 4000;
        else if (StringEquals(logistics->supportState, "convoys_hot")) duration += 3000;
        else if (StringEquals(logistics->supportState, "fortifying")) duration += 5000;
        else if (StringEquals(logistics->supportState, "searched")) duration += 2500;
        return ClampInt(duration, 12000, 35000);
    }

    void RefreshRegionLogistics()
    {
        const char* regions[] = { "cholla_springs", "gaptooth_ridge", "hennigans_stead", "rio_bravo" };
        int slot = 0;
        for (const char* region : regions)
        {
            if (slot >= static_cast<int>(gState.regionLogistics.size()))
            {
                break;
            }

            int supplySum = 0;
            int escortSum = 0;
            int routeSum = 0;
            int outlawBias = 0;
            int lawBias = 0;
            int nodeCount = 0;
            for (const RuntimeNode& node : gState.nodes)
            {
                if (!StringEquals(node.regionName, region))
                {
                    continue;
                }
                ++nodeCount;
                supplySum += node.supply;
                escortSum += node.escortNeed;
                routeSum += node.routePressure;
                outlawBias += node.outlawWeight;
                lawBias += node.lawWeight;
            }
            if (nodeCount <= 0)
            {
                continue;
            }

            RegionLogistics logistics{};
            logistics.active = true;
            CopyString(logistics.regionName, sizeof(logistics.regionName), region);
            logistics.stock = ClampInt(supplySum / nodeCount + lawBias / 20 - outlawBias / 24, 0, 100);
            logistics.convoyPressure = ClampInt(routeSum / nodeCount + escortSum / 2, 0, 100);
            logistics.strain = ClampInt((100 - logistics.stock) / 2 + logistics.convoyPressure / 2 + escortSum / 3, 0, 100);
            logistics.lastRefreshDay = gState.gameDay;

            const RegionDirective* directive = FindDirectiveForRegion(region);
            const RegionCadence* cadence = FindCadenceForRegion(region);
            if (logistics.stock < 30)
            {
                CopyString(logistics.supportState, sizeof(logistics.supportState), "starved");
            }
            else if (logistics.strain > 70)
            {
                CopyString(logistics.supportState, sizeof(logistics.supportState), "strained");
            }
            else if (directive && StringEquals(directive->directiveName, "smuggling"))
            {
                CopyString(logistics.supportState, sizeof(logistics.supportState), "convoys_hot");
            }
            else if (directive && StringEquals(directive->directiveName, "fortify"))
            {
                CopyString(logistics.supportState, sizeof(logistics.supportState), "fortifying");
            }
            else if (directive && StringEquals(directive->directiveName, "crackdown"))
            {
                CopyString(logistics.supportState, sizeof(logistics.supportState), "searched");
            }
            else if (cadence && (StringEquals(cadence->cadenceState, "recovering") || StringEquals(cadence->cadenceState, "quiet")))
            {
                CopyString(logistics.supportState, sizeof(logistics.supportState), "recovering");
            }
            else
            {
                CopyString(logistics.supportState, sizeof(logistics.supportState), "steady");
            }

            gState.regionLogistics[static_cast<std::size_t>(slot++)] = logistics;
        }
    }

    RegionCivilianClimate* FindClimateMutable(const char* regionName)
    {
        for (RegionCivilianClimate& climate : gState.regionClimate)
        {
            if (climate.active && StringEquals(climate.regionName, regionName))
            {
                return &climate;
            }
        }
        return nullptr;
    }

    const RegionCivilianClimate* FindClimateForRegion(const char* regionName)
    {
        for (const RegionCivilianClimate& climate : gState.regionClimate)
        {
            if (climate.active && StringEquals(climate.regionName, regionName))
            {
                return &climate;
            }
        }
        return nullptr;
    }

    const char* ClimateStateName(const RuntimeNode& node)
    {
        const RegionCivilianClimate* climate = FindClimateForRegion(node.regionName);
        return climate ? climate->climateState : "uncertain";
    }

    int ClimateSupportForNode(const RuntimeNode& node)
    {
        const RegionCivilianClimate* climate = FindClimateForRegion(node.regionName);
        return climate ? climate->support : 0;
    }

    int ClimatePanicForNode(const RuntimeNode& node)
    {
        const RegionCivilianClimate* climate = FindClimateForRegion(node.regionName);
        return climate ? climate->panic : 0;
    }

    int ClimateRepressionForNode(const RuntimeNode& node)
    {
        const RegionCivilianClimate* climate = FindClimateForRegion(node.regionName);
        return climate ? climate->repression : 0;
    }

    int ClimateRumorTrustForNode(const RuntimeNode& node)
    {
        const RegionCivilianClimate* climate = FindClimateForRegion(node.regionName);
        return climate ? climate->rumorTrust : 0;
    }

    void RefreshRegionClimate()
    {
        const char* regions[] = { "cholla_springs", "gaptooth_ridge", "hennigans_stead", "rio_bravo" };
        int slot = 0;
        for (const char* region : regions)
        {
            if (slot >= static_cast<int>(gState.regionClimate.size()))
            {
                break;
            }

            int civilianSum = 0;
            int fearSum = 0;
            int wagonSum = 0;
            int contestedCount = 0;
            int lawControlledCount = 0;
            int outlawControlledCount = 0;
            int occupationCount = 0;
            int nodeCount = 0;
            for (const RuntimeNode& node : gState.nodes)
            {
                if (!StringEquals(node.regionName, region))
                {
                    continue;
                }
                ++nodeCount;
                civilianSum += node.civilianWeight;
                fearSum += node.fear;
                wagonSum += node.wagonWeight;
                if (node.contested) ++contestedCount;
                if (IsLawFactionName(node.controller)) ++lawControlledCount;
                else ++outlawControlledCount;
                if (OccupationActive(node)) ++occupationCount;
            }
            if (nodeCount <= 0)
            {
                continue;
            }

            const RegionDirective* directive = FindDirectiveForRegion(region);
            const RegionPressureFront* front = FindFrontForRegion(region);
            const RegionLogistics* logistics = FindLogisticsForRegion(region);

            RegionCivilianClimate climate{};
            climate.active = true;
            CopyString(climate.regionName, sizeof(climate.regionName), region);
            const int civilianAvg = civilianSum / nodeCount;
            const int fearAvg = fearSum / nodeCount;
            const int wagonAvg = wagonSum / nodeCount;

            climate.support = ClampInt(civilianAvg - fearAvg / 3 + outlawControlledCount * 5 - lawControlledCount * 3, 0, 100);
            climate.panic = ClampInt(fearAvg + contestedCount * 12 + occupationCount * 4, 0, 100);
            climate.repression = ClampInt(lawControlledCount * 14 + (directive && StringEquals(directive->directiveName, "crackdown") ? 18 : 0) + (logistics && StringEquals(logistics->supportState, "searched") ? 16 : 0) + (front && (StringEquals(front->frontState, "law_surge") || StringEquals(front->frontState, "law_edge")) ? 10 : 0), 0, 100);
            climate.rumorTrust = ClampInt(civilianAvg + wagonAvg / 3 + climate.support / 4 - climate.repression / 2 - climate.panic / 3, 0, 100);

            const char* state = "uncertain";
            if (climate.panic >= 74 && climate.repression >= 60) state = "terrorized";
            else if (climate.repression >= 66) state = "cowed";
            else if (climate.panic >= 66) state = "panicked";
            else if (climate.support >= 62 && climate.rumorTrust >= 50) state = "supportive";
            else if (climate.rumorTrust >= 62) state = "talkative";
            else if (climate.repression >= 45 && climate.support <= 32) state = "suspicious";
            CopyString(climate.climateState, sizeof(climate.climateState), state);
            climate.lastRefreshDay = gState.gameDay;
            gState.regionClimate[static_cast<std::size_t>(slot++)] = climate;
        }
    }

    RegionCampaignOutlook* FindCampaignMutable(const char* regionName)
    {
        for (RegionCampaignOutlook& campaign : gState.regionCampaigns)
        {
            if (campaign.active && StringEquals(campaign.regionName, regionName))
            {
                return &campaign;
            }
        }
        return nullptr;
    }

    const RegionCampaignOutlook* FindCampaignForRegion(const char* regionName)
    {
        for (const RegionCampaignOutlook& campaign : gState.regionCampaigns)
        {
            if (campaign.active && StringEquals(campaign.regionName, regionName))
            {
                return &campaign;
            }
        }
        return nullptr;
    }

    const char* CampaignStateName(const RuntimeNode& node)
    {
        const RegionCampaignOutlook* campaign = FindCampaignForRegion(node.regionName);
        return campaign ? campaign->campaignState : "balanced";
    }

    int CampaignLawControlForNode(const RuntimeNode& node)
    {
        const RegionCampaignOutlook* campaign = FindCampaignForRegion(node.regionName);
        return campaign ? campaign->lawControl : 0;
    }

    int CampaignOutlawControlForNode(const RuntimeNode& node)
    {
        const RegionCampaignOutlook* campaign = FindCampaignForRegion(node.regionName);
        return campaign ? campaign->outlawControl : 0;
    }

    int CampaignCivilianTiltForNode(const RuntimeNode& node)
    {
        const RegionCampaignOutlook* campaign = FindCampaignForRegion(node.regionName);
        return campaign ? campaign->civilianTilt : 0;
    }

    const char* TheaterStateName()
    {
        return gState.theaterSummary.active ? gState.theaterSummary.theaterState : "balanced_war";
    }

    int TheaterPlayerMomentum()
    {
        return gState.theaterSummary.active ? gState.theaterSummary.playerMomentum : 0;
    }

    void RefreshRegionCampaign()
    {
        const char* regions[] = { "cholla_springs", "gaptooth_ridge", "hennigans_stead", "rio_bravo" };
        int slot = 0;
        for (const char* region : regions)
        {
            if (slot >= static_cast<int>(gState.regionCampaigns.size()))
            {
                break;
            }

            int lawNodes = 0;
            int outlawNodes = 0;
            int contestedNodes = 0;
            int strategicSum = 0;
            int nodeCount = 0;
            for (const RuntimeNode& node : gState.nodes)
            {
                if (!StringEquals(node.regionName, region))
                {
                    continue;
                }
                ++nodeCount;
                strategicSum += node.pressure + node.heat + node.routePressure + node.fortification;
                if (node.contested) ++contestedNodes;
                if (IsLawFactionName(node.controller)) ++lawNodes;
                else ++outlawNodes;
            }
            if (nodeCount <= 0)
            {
                continue;
            }

            const RegionPressureFront* front = FindFrontForRegion(region);
            const RegionLogistics* logistics = FindLogisticsForRegion(region);
            const RegionCivilianClimate* climate = FindClimateForRegion(region);
            const RegionCadence* cadence = FindCadenceForRegion(region);

            RegionCampaignOutlook campaign{};
            campaign.active = true;
            CopyString(campaign.regionName, sizeof(campaign.regionName), region);
            campaign.lawControl = ClampInt(lawNodes * 18 + (front ? front->lawPressure / 2 : 0) + (climate ? climate->repression / 4 : 0) + (logistics && StringEquals(logistics->supportState, "fortifying") ? 8 : 0), 0, 100);
            campaign.outlawControl = ClampInt(outlawNodes * 18 + (front ? front->outlawPressure / 2 : 0) + (climate ? climate->support / 5 : 0) + (logistics && (StringEquals(logistics->supportState, "starved") || StringEquals(logistics->supportState, "convoys_hot")) ? 8 : 0), 0, 100);
            campaign.civilianTilt = ClampInt((climate ? climate->support - climate->repression / 2 - climate->panic / 3 : 0) + 50, 0, 100);
            campaign.strategicValue = ClampInt(strategicSum / nodeCount, 0, 100);

            const int diff = campaign.lawControl - campaign.outlawControl;
            const char* state = "balanced";
            if (std::abs(diff) <= 10 || contestedNodes >= 2) state = "knife_edge";
            else if (diff >= 36) state = "marshal_grip";
            else if (diff >= 16) state = "law_advancing";
            else if (diff <= -36) state = "outlaw_domain";
            else if (diff <= -16) state = "outlaw_ascending";
            else if (campaign.civilianTilt >= 64) state = "simmering_support";
            else if (climate && (StringEquals(climate->climateState, "terrorized") || StringEquals(climate->climateState, "panicked"))) state = "shattered";
            else if (cadence && (StringEquals(cadence->cadenceState, "recovering") || StringEquals(cadence->cadenceState, "spent"))) state = "reforming";
            CopyString(campaign.campaignState, sizeof(campaign.campaignState), state);
            campaign.lastRefreshDay = gState.gameDay;
            gState.regionCampaigns[static_cast<std::size_t>(slot++)] = campaign;
        }
        for (; slot < static_cast<int>(gState.regionCampaigns.size()); ++slot)
        {
            gState.regionCampaigns[static_cast<std::size_t>(slot)] = RegionCampaignOutlook{};
        }
    }

    void RefreshTheaterSummary()
    {
        TheaterSummary summary{};
        summary.active = true;
        summary.lastRefreshDay = gState.gameDay;
        for (const RegionCampaignOutlook& campaign : gState.regionCampaigns)
        {
            if (!campaign.active)
            {
                continue;
            }
            if (StringEquals(campaign.campaignState, "marshal_grip") || StringEquals(campaign.campaignState, "law_advancing")) ++summary.lawLeaningRegions;
            else if (StringEquals(campaign.campaignState, "outlaw_domain") || StringEquals(campaign.campaignState, "outlaw_ascending")) ++summary.outlawLeaningRegions;
            if (StringEquals(campaign.campaignState, "knife_edge")) ++summary.knifeEdgeRegions;
        }
        const int delta = summary.lawLeaningRegions - summary.outlawLeaningRegions;
        const bool playerLaw = kSeedFactions[static_cast<std::size_t>(ClampInt(gState.factionIndex, 0, static_cast<int>(std::size(kSeedFactions)) - 1))].lawEnforcement;
        summary.playerMomentum = playerLaw ? delta : -delta;
        const char* state = "balanced_war";
        if (summary.knifeEdgeRegions >= 2) state = "knife_edge_frontier";
        else if (delta >= 3) state = "law_theater_edge";
        else if (delta <= -3) state = "outlaw_theater_edge";
        else if (summary.lawLeaningRegions > 0 && summary.outlawLeaningRegions > 0) state = "fractured_frontier";
        CopyString(summary.theaterState, sizeof(summary.theaterState), state);
        gState.theaterSummary = summary;
    }

    void WriteDailyBulletin()
    {
        if (gState.gameDay < 0 || gState.bulletinLastDay == gState.gameDay)
        {
            return;
        }
        std::ofstream out(kBulletinPath, std::ios::trunc);
        if (!out)
        {
            return;
        }
        out << "CODE RED FACTION WAR V26 DAILY BULLETIN\n";
        out << "DAY=" << gState.gameDay << "\n";
        out << "THEATER=" << TheaterStateName() << "|MOMENTUM=" << TheaterPlayerMomentum() << "\n\n";
        for (const RegionCampaignOutlook& campaign : gState.regionCampaigns)
        {
            if (!campaign.active) continue;
            const RegionLogistics* logistics = FindLogisticsForRegion(campaign.regionName);
            const RegionCivilianClimate* climate = FindClimateForRegion(campaign.regionName);
            const RegionCadence* cadence = FindCadenceForRegion(campaign.regionName);
            out << "[" << campaign.regionName << "]\n";
            out << "campaign=" << campaign.campaignState << " law=" << campaign.lawControl << " outlaw=" << campaign.outlawControl << " civilian_tilt=" << campaign.civilianTilt << " strategic=" << campaign.strategicValue << "\n";
            if (logistics) out << "logistics=" << logistics->supportState << " stock=" << logistics->stock << " convoy=" << logistics->convoyPressure << " strain=" << logistics->strain << "\n";
            if (climate) out << "climate=" << climate->climateState << " support=" << climate->support << " panic=" << climate->panic << " repression=" << climate->repression << " rumor=" << climate->rumorTrust << "\n";
            if (cadence) out << "cadence=" << cadence->cadenceState << " fatigue=" << cadence->fatigue << " recovery=" << cadence->recovery << " momentum=" << cadence->momentum << "\n";
            out << "\n";
        }
        gState.bulletinLastDay = gState.gameDay;
    }

    const char* FrontStateName(const RuntimeNode& node)
    {
        const RegionPressureFront* front = FindFrontForRegion(node.regionName);
        return front ? front->frontState : "calm";
    }

    bool OccupationActive(const RuntimeNode& node)
    {
        return node.occupationState[0] && (node.occupationUntilDay < 0 || gState.gameDay <= node.occupationUntilDay);
    }

    void ExpireOccupationStates()
    {
        if (gState.gameDay < 0)
        {
            return;
        }
        for (RuntimeNode& node : gState.nodes)
        {
            if (!node.occupationState[0] || node.occupationUntilDay < 0 || gState.gameDay <= node.occupationUntilDay)
            {
                continue;
            }
            char msg[192]{};
            std::snprintf(msg, sizeof(msg), "%s settled after %s", node.displayName, node.occupationState);
            AppendRecentEvent(msg);
            CopyString(node.occupationState, sizeof(node.occupationState), "");
            CopyString(node.occupationFaction, sizeof(node.occupationFaction), "");
            node.occupationUntilDay = -1;
            node.fear = ClampInt(node.fear - 6, 0, 100);
            node.heat = ClampInt(node.heat - 4, 0, 100);
            node.pressure = ClampInt(node.pressure - 3, 0, 100);
            RefreshLocalState(node);
            gState.saveDirty = true;
        }
    }

    void ApplyOccupationOutcome(RuntimeNode& node, const char* winningFaction, bool attackersWon, const char* battleKind)
    {
        if (!winningFaction || !winningFaction[0])
        {
            return;
        }
        const bool lawVictory = IsLawFactionName(winningFaction);
        const bool townLike = StringEquals(node.contextTag, "law_town") || StringEquals(node.contextTag, "rail_checkpoint") || ContainsCsvToken(node.strategicTagsCsv, "transport_post");
        const bool marketLike = StringEquals(node.contextTag, "black_market");
        const bool fortLike = StringEquals(node.contextTag, "fort_war") || ContainsCsvToken(node.strategicTagsCsv, "war_anchor");
        const bool hideoutLike = StringEquals(node.contextTag, "camp_hideout") || StringEquals(node.contextTag, "rustler_hideout") || ContainsCsvToken(node.strategicTagsCsv, "outlaw_hideout");

        const char* state = "shaken_frontier";
        int durationDays = 1;
        if (lawVictory)
        {
            if (townLike)
            {
                state = "marshal_lockdown";
            }
            else if (marketLike)
            {
                state = "law_sweep";
            }
            else if (fortLike)
            {
                state = "garrison_retake";
                durationDays = 2;
            }
            else
            {
                state = "deputy_sweep";
            }
            node.fortification = ClampInt(node.fortification + (fortLike ? 12 : 8), 0, 100);
            node.fear = ClampInt(node.fear + 4, 0, 100);
            node.heat = ClampInt(node.heat + 3, 0, 100);
            node.supply = ClampInt(node.supply + 4, 0, 100);
        }
        else
        {
            if (townLike)
            {
                state = "gang_occupation";
                durationDays = 2;
            }
            else if (marketLike)
            {
                state = "smuggler_hold";
            }
            else if (fortLike)
            {
                state = "fortified_outlaw_hold";
                durationDays = 2;
            }
            else if (hideoutLike)
            {
                state = "raider_muster";
            }
            else
            {
                state = "outlaw_pressure_hold";
            }
            node.fear = ClampInt(node.fear + 10, 0, 100);
            node.heat = ClampInt(node.heat + 8, 0, 100);
            node.pressure = ClampInt(node.pressure + 6, 0, 100);
            node.supply = ClampInt(node.supply - 4, 0, 100);
        }
        (void)attackersWon;
        CopyString(node.occupationState, sizeof(node.occupationState), state);
        CopyString(node.occupationFaction, sizeof(node.occupationFaction), winningFaction);
        node.occupationUntilDay = gState.gameDay >= 0 ? gState.gameDay + durationDays : durationDays;
        RefreshLocalState(node);

        char msg[224]{};
        std::snprintf(msg, sizeof(msg), "%s after %s at %s", state, battleKind ? battleKind : "battle", node.displayName);
        AppendRecentEvent(msg);
        PushToast(msg);
        if (RegionCadence* cadence = FindCadenceMutable(node.regionName))
        {
            cadence->fatigue = ClampInt(cadence->fatigue + 10, 0, 100);
            cadence->recovery = ClampInt(cadence->recovery - 4, 0, 100);
            cadence->momentum = ClampInt(cadence->momentum + (lawVictory ? 4 : 6), 0, 100);
        }
        gState.saveDirty = true;
    }

    void PropagateMultiFrontPressure()
    {
        if (gState.gameDay < 0 || gState.gameHour < 0)
        {
            return;
        }
        for (RegionPressureFront& front : gState.regionFronts)
        {
            if (!front.active || StringEquals(front.frontState, "calm") || StringEquals(front.frontState, "tense"))
            {
                continue;
            }
            if (front.lastSpilloverDay == gState.gameDay && front.lastSpilloverHour == gState.gameHour)
            {
                continue;
            }
            const int sourceHotIndex = FindRegionalHotNodeIndex(front.regionName);
            if (sourceHotIndex < 0)
            {
                continue;
            }
            RuntimeNode& sourceNode = gState.nodes[static_cast<std::size_t>(sourceHotIndex)];
            std::stringstream targets(AdjacentRegionsCsv(front.regionName));
            std::string regionItem;
            int bestTargetIndex = -1;
            int bestTargetScore = -999999;
            PendingConflictType bestType = PendingConflictType::None;
            bool lawDominant = front.lawPressure >= front.outlawPressure;
            while (std::getline(targets, regionItem, ','))
            {
                int targetIndex = FindRegionalHotNodeIndex(regionItem.c_str());
                if (targetIndex < 0)
                {
                    continue;
                }
                RuntimeNode& targetNode = gState.nodes[static_cast<std::size_t>(targetIndex)];
                if (targetNode.contested)
                {
                    continue;
                }
                int score = ComputeNodeHotness(targetNode);
                if (lawDominant)
                {
                    if (!CurrentNodeSupportsRegionalShootout(targetNode))
                    {
                        continue;
                    }
                    if (!IsLawFactionName(targetNode.controller)) score += 18;
                    if (StringEquals(DirectiveForNode(targetNode), "crackdown")) score += 10;
                }
                else
                {
                    if (!(CurrentNodeSupportsTownAssault(targetNode) || CurrentNodeSupportsRegionalShootout(targetNode)))
                    {
                        continue;
                    }
                    if (CurrentNodeSupportsTownAssault(targetNode)) score += 14;
                    if (StringEquals(DirectiveForNode(targetNode), "raid")) score += 10;
                }
                if (score > bestTargetScore)
                {
                    bestTargetScore = score;
                    bestTargetIndex = targetIndex;
                    bestType = lawDominant ? PendingConflictType::RegionalShootout : (CurrentNodeSupportsTownAssault(targetNode) ? PendingConflictType::TownAssault : PendingConflictType::RegionalShootout);
                }
            }
            if (bestTargetIndex < 0 || bestType == PendingConflictType::None)
            {
                continue;
            }
            RuntimeNode& targetNode = gState.nodes[static_cast<std::size_t>(bestTargetIndex)];
            bool alreadyQueued = false;
            for (const PendingConflictChain& chain : gState.pendingChains)
            {
                if (chain.active && StringEquals(chain.nodeId, targetNode.nodeId))
                {
                    alreadyQueued = true;
                    break;
                }
            }
            if (alreadyQueued)
            {
                continue;
            }
            for (PendingConflictChain& chain : gState.pendingChains)
            {
                if (chain.active)
                {
                    continue;
                }
                chain.active = true;
                chain.type = bestType;
                CopyString(chain.nodeId, sizeof(chain.nodeId), targetNode.nodeId);
                CopyString(chain.sourceNodeId, sizeof(chain.sourceNodeId), sourceNode.nodeId);
                const char* sourceFaction = lawDominant ? DetermineLawFactionForNode(sourceNode) : DetermineOutlawPressureFaction(sourceNode);
                const char* targetFaction = lawDominant ? DetermineOutlawPressureFaction(targetNode) : DetermineLawFactionForNode(targetNode);
                CopyString(chain.sourceFaction, sizeof(chain.sourceFaction), sourceFaction);
                CopyString(chain.targetFaction, sizeof(chain.targetFaction), targetFaction);
                int delayHours = StringEquals(front.frontState, "two_front") ? 1 : 2;
                chain.executeDay = gState.gameDay;
                chain.executeHour = gState.gameHour + delayHours;
                while (chain.executeHour >= 24)
                {
                    chain.executeHour -= 24;
                    ++chain.executeDay;
                }
                std::snprintf(chain.reason, sizeof(chain.reason), "Front spillover from %s", sourceNode.displayName);

                targetNode.heat = ClampInt(targetNode.heat + 9, 0, 100);
                targetNode.pressure = ClampInt(targetNode.pressure + 8, 0, 100);
                targetNode.fear = ClampInt(targetNode.fear + 5, 0, 100);
                targetNode.nextAutoEventAllowedMs = 0;
                RefreshLocalState(targetNode);

                char msg[192]{};
                std::snprintf(msg, sizeof(msg), "%s front pushed from %s into %s", front.frontState, sourceNode.displayName, targetNode.displayName);
                AppendRecentEvent(msg);
                PushToast(msg);
                gState.saveDirty = true;
                front.lastSpilloverDay = gState.gameDay;
                front.lastSpilloverHour = gState.gameHour;
                break;
            }
        }
    }

    const char* DirectiveForNode(const RuntimeNode& node)
    {
        const RegionDirective* directive = FindDirectiveForRegion(node.regionName);
        return directive ? directive->directiveName : "";
    }

    void GenerateDailyRegionDirectives()
    {
        if (gState.gameDay < 0 || gState.directivesIssuedDay == gState.gameDay)
        {
            return;
        }
        gState.directivesIssuedDay = gState.gameDay;
        for (RegionDirective& directive : gState.regionDirectives)
        {
            directive = RegionDirective{};
        }

        const char* regions[] = { "cholla_springs", "gaptooth_ridge", "hennigans_stead", "rio_bravo" };
        int slot = 0;
        for (const char* region : regions)
        {
            int hotIndex = FindRegionalHotNodeIndex(region);
            if (hotIndex < 0 || slot >= static_cast<int>(gState.regionDirectives.size()))
            {
                continue;
            }
            RuntimeNode& node = gState.nodes[static_cast<std::size_t>(hotIndex)];
            RegionDirective directive{};
            directive.active = true;
            CopyString(directive.regionName, sizeof(directive.regionName), region);
            CopyString(directive.primaryNodeId, sizeof(directive.primaryNodeId), node.nodeId);
            CopyString(directive.sourceFaction, sizeof(directive.sourceFaction), node.controller);
            directive.dayIssued = gState.gameDay;

            if (StringEquals(node.contextTag, "law_town") || StringEquals(node.contextTag, "rail_checkpoint"))
            {
                CopyString(directive.directiveName, sizeof(directive.directiveName), "crackdown");
            }
            else if (StringEquals(node.contextTag, "black_market") || ContainsCsvToken(node.strategicTagsCsv, "transport_post"))
            {
                CopyString(directive.directiveName, sizeof(directive.directiveName), "smuggling");
            }
            else if (StringEquals(node.contextTag, "ghost_town") || StringEquals(node.contextTag, "mine_hideout"))
            {
                CopyString(directive.directiveName, sizeof(directive.directiveName), "scavenge");
            }
            else if (StringEquals(node.contextTag, "fort_war") || ContainsCsvToken(node.strategicTagsCsv, "war_anchor"))
            {
                CopyString(directive.directiveName, sizeof(directive.directiveName), "fortify");
            }
            else
            {
                CopyString(directive.directiveName, sizeof(directive.directiveName), "raid");
            }
            const RegionCadence* cadence = FindCadenceForRegion(region);
            if (cadence)
            {
                if (StringEquals(cadence->cadenceState, "recovering") || StringEquals(cadence->cadenceState, "spent"))
                {
                    if (StringEquals(directive.directiveName, "raid"))
                    {
                        CopyString(directive.directiveName, sizeof(directive.directiveName), "fortify");
                    }
                    else if (StringEquals(directive.directiveName, "crackdown"))
                    {
                        CopyString(directive.directiveName, sizeof(directive.directiveName), "fortify");
                    }
                }
                else if (StringEquals(cadence->cadenceState, "surging"))
                {
                    if (ContainsCsvToken(node.strategicTagsCsv, "outlaw_hideout") || ContainsCsvToken(node.strategicTagsCsv, "raid_origin") || StringEquals(node.contextTag, "camp_hideout") || StringEquals(node.contextTag, "rustler_hideout"))
                    {
                        CopyString(directive.directiveName, sizeof(directive.directiveName), "raid");
                    }
                    else if (StringEquals(node.contextTag, "law_town") || StringEquals(node.contextTag, "rail_checkpoint"))
                    {
                        CopyString(directive.directiveName, sizeof(directive.directiveName), "crackdown");
                    }
                }
            }
            const RegionLogistics* logistics = FindLogisticsForRegion(region);
            if (logistics)
            {
                if (logistics->stock < 28)
                {
                    if (StringEquals(directive.directiveName, "raid"))
                    {
                        CopyString(directive.directiveName, sizeof(directive.directiveName), "smuggling");
                    }
                    else
                    {
                        CopyString(directive.directiveName, sizeof(directive.directiveName), "fortify");
                    }
                }
                else if (logistics->convoyPressure > 60 && !StringEquals(directive.directiveName, "crackdown"))
                {
                    CopyString(directive.directiveName, sizeof(directive.directiveName), "smuggling");
                }
            }
            gState.regionDirectives[static_cast<std::size_t>(slot++)] = directive;

            char msg[192]{};
            std::snprintf(msg, sizeof(msg), "%s directive: %s around %s", region, DirectiveDisplayName(directive.directiveName), node.displayName);
            AppendRecentEvent(msg);
        }
        RefreshRegionFronts();
        RefreshRegionCadences();
        RefreshRegionClimate();
        RefreshRegionCampaign();
        RefreshTheaterSummary();
    }

    void MarkNodeEventTriggered(RuntimeNode& node, const char* eventLabel)
    {
        node.lastTriggeredDay = gState.gameDay;
        ++node.dailyTriggerCount;
        if (RegionCadence* cadence = FindCadenceMutable(node.regionName))
        {
            cadence->fatigue = ClampInt(cadence->fatigue + 12, 0, 100);
            cadence->recovery = ClampInt(cadence->recovery - 8, 0, 100);
            cadence->momentum = ClampInt(cadence->momentum + 5, 0, 100);
            if (StringEquals(cadence->cadenceState, "recovering") || StringEquals(cadence->cadenceState, "quiet"))
            {
                CopyString(cadence->cadenceState, sizeof(cadence->cadenceState), "active");
            }
        }
        char msg[192]{};
        std::snprintf(msg, sizeof(msg), "%s at %s on frontier day %d", eventLabel, node.displayName, gState.gameDay);
        LogLine(msg);
    }


    const char* PendingConflictTypeName(PendingConflictType type)
    {
        switch (type)
        {
        case PendingConflictType::TownAssault:
            return "TownAssault";
        case PendingConflictType::RegionalShootout:
            return "RegionalShootout";
        default:
            return "None";
        }
    }

    int CountPendingConflictChains()
    {
        int count = 0;
        for (const PendingConflictChain& chain : gState.pendingChains)
        {
            if (chain.active)
            {
                ++count;
            }
        }
        return count;
    }

    int FindConflictChainTargetIndex(const RuntimeNode& centerNode, const char* winningFaction, const char* losingFaction, bool attackersWon, PendingConflictType* outType)
    {
        if (outType)
        {
            *outType = PendingConflictType::None;
        }
        const bool winnerIsLaw = IsLawFactionName(winningFaction);
        std::stringstream ss(centerNode.neighborsCsv);
        std::string item;
        int bestIndex = -1;
        int bestScore = -999999;
        PendingConflictType bestType = PendingConflictType::None;
        while (std::getline(ss, item, ','))
        {
            RuntimeNode* node = FindNodeById(item.c_str());
            if (!node || node->contested)
            {
                continue;
            }
            int score = node->heat + node->pressure + node->fear / 2 + node->supply / 4 + node->fortification / 5;
            const char* directive = DirectiveForNode(*node);
            PendingConflictType candidateType = PendingConflictType::None;
            if (winnerIsLaw)
            {
                const bool supportsCrackdown = StringEquals(node->controller, losingFaction) || (!IsLawFactionName(node->controller) && (ContainsCsvToken(node->strategicTagsCsv, "outlaw_hideout") || ContainsCsvToken(node->strategicTagsCsv, "raid_origin") || ContainsCsvToken(node->strategicTagsCsv, "black_market") || ContainsCsvToken(node->strategicTagsCsv, "roadside_robbery") || ContainsCsvToken(node->strategicTagsCsv, "war_anchor")));
                if (!supportsCrackdown)
                {
                    continue;
                }
                candidateType = CurrentNodeSupportsRegionalShootout(*node) ? PendingConflictType::RegionalShootout : PendingConflictType::None;
                if (ContainsCsvToken(node->strategicTagsCsv, "outlaw_hideout") || ContainsCsvToken(node->strategicTagsCsv, "raid_origin"))
                {
                    score += 18;
                }
                if (ContainsCsvToken(node->strategicTagsCsv, "black_market"))
                {
                    score += 10;
                }
                if (StringEquals(directive, "crackdown")) score += 12;
                if (StringEquals(directive, "smuggling") && (StringEquals(node->contextTag, "black_market") || ContainsCsvToken(node->strategicTagsCsv, "transport_post"))) score += 10;
            }
            else
            {
                const bool supportsReprisal = IsLawFactionName(node->controller) || StringEquals(node->controller, losingFaction) || ContainsCsvToken(node->strategicTagsCsv, "transport_post") || ContainsCsvToken(node->strategicTagsCsv, "law_hub") || ContainsCsvToken(node->strategicTagsCsv, "civilian_pressure") || StringEquals(node->contextTag, "law_town");
                if (!supportsReprisal)
                {
                    continue;
                }
                candidateType = CurrentNodeSupportsTownAssault(*node) ? PendingConflictType::TownAssault : (CurrentNodeSupportsRegionalShootout(*node) ? PendingConflictType::RegionalShootout : PendingConflictType::None);
                if (candidateType == PendingConflictType::TownAssault)
                {
                    score += 18;
                }
                if (ContainsCsvToken(node->strategicTagsCsv, "transport_post") || StringEquals(node->contextTag, "law_town"))
                {
                    score += 12;
                }
                if (attackersWon)
                {
                    score += 6;
                }
                if (StringEquals(directive, "raid")) score += 12;
                if (StringEquals(directive, "fortify") && (StringEquals(node->contextTag, "fort_war") || ContainsCsvToken(node->strategicTagsCsv, "war_anchor"))) score += 12;
            }
            if (candidateType == PendingConflictType::None)
            {
                continue;
            }
            if (StringEquals(node->regionName, centerNode.regionName))
            {
                score += 8;
            }
            if (score > bestScore)
            {
                bestScore = score;
                bestIndex = FindNodeIndexById(node->nodeId);
                bestType = candidateType;
            }
        }
        if (outType)
        {
            *outType = bestType;
        }
        return bestIndex;
    }

    void ScheduleConflictChain(const RuntimeNode& centerNode, const char* winningFaction, const char* losingFaction, bool attackersWon)
    {
        if (CountPendingConflictChains() >= static_cast<int>(gState.pendingChains.size()))
        {
            return;
        }
        PendingConflictType type = PendingConflictType::None;
        const int idx = FindConflictChainTargetIndex(centerNode, winningFaction, losingFaction, attackersWon, &type);
        if (idx < 0 || type == PendingConflictType::None)
        {
            return;
        }
        RuntimeNode& target = gState.nodes[static_cast<std::size_t>(idx)];
        for (const PendingConflictChain& chain : gState.pendingChains)
        {
            if (chain.active && StringEquals(chain.nodeId, target.nodeId))
            {
                return;
            }
        }
        for (PendingConflictChain& chain : gState.pendingChains)
        {
            if (chain.active)
            {
                continue;
            }
            int delayHours = StringEquals(target.regionName, centerNode.regionName) ? 2 : 4;
            const char* targetDirective = DirectiveForNode(target);
            if (StringEquals(targetDirective, "raid") || StringEquals(targetDirective, "crackdown"))
            {
                delayHours = StringEquals(target.regionName, centerNode.regionName) ? 1 : 3;
            }
            else if (StringEquals(targetDirective, "fortify"))
            {
                delayHours += 1;
            }
            int executeDay = gState.gameDay;
            int executeHour = gState.gameHour >= 0 ? gState.gameHour + delayHours : delayHours;
            while (executeHour >= 24)
            {
                executeHour -= 24;
                ++executeDay;
            }
            chain.active = true;
            chain.type = type;
            CopyString(chain.nodeId, sizeof(chain.nodeId), target.nodeId);
            CopyString(chain.sourceNodeId, sizeof(chain.sourceNodeId), centerNode.nodeId);
            CopyString(chain.sourceFaction, sizeof(chain.sourceFaction), winningFaction);
            CopyString(chain.targetFaction, sizeof(chain.targetFaction), losingFaction);
            const bool winnerIsLaw = IsLawFactionName(winningFaction);
            std::snprintf(chain.reason, sizeof(chain.reason), "%s from %s", winnerIsLaw ? "Crackdown" : "Reprisal", centerNode.displayName);
            chain.executeDay = executeDay;
            chain.executeHour = executeHour;

            target.heat = ClampInt(target.heat + 8, 0, 100);
            target.pressure = ClampInt(target.pressure + 6, 0, 100);
            target.fear = ClampInt(target.fear + 5, 0, 100);
            target.nextAutoEventAllowedMs = 0;
            RefreshLocalState(target);

            char msg[192]{};
            std::snprintf(msg, sizeof(msg), "%s chain set: %s -> %s by hour %d", PendingConflictTypeName(type), centerNode.displayName, target.displayName, executeHour);
            AppendRecentEvent(msg);
            PushToast(msg);
            gState.saveDirty = true;
            break;
        }
    }

    void TickPendingConflictChains()
    {
        if (gState.townAssault.active || gState.regionalShootout.active)
        {
            return;
        }
        for (PendingConflictChain& chain : gState.pendingChains)
        {
            if (!chain.active)
            {
                continue;
            }
            if (gState.gameDay < 0 || gState.gameHour < 0)
            {
                continue;
            }
            if (gState.gameDay < chain.executeDay || (gState.gameDay == chain.executeDay && gState.gameHour < chain.executeHour))
            {
                continue;
            }
            RuntimeNode* node = FindNodeById(chain.nodeId);
            if (!node)
            {
                chain = PendingConflictChain{};
                continue;
            }
            const bool playerNear = IsPlayerNearNode(*node, 240.0f);
            node->heat = ClampInt(node->heat + 10, 0, 100);
            node->pressure = ClampInt(node->pressure + 8, 0, 100);
            node->fear = ClampInt(node->fear + 6, 0, 100);
            CopyString(node->activeAssaultFaction, sizeof(node->activeAssaultFaction), chain.sourceFaction);
            node->contested = true;
            RefreshLocalState(*node);
            char msg[192]{};
            if (playerNear)
            {
                gState.nodeIndex = FindNodeIndexById(node->nodeId);
                std::snprintf(msg, sizeof(msg), "Conflict chain reached %s near the player", node->displayName);
                AppendRecentEvent(msg);
                PushToast(msg);
                if (chain.type == PendingConflictType::TownAssault && CurrentNodeSupportsTownAssault(*node))
                {
                    StartTownAssaultEvent();
                }
                else if (CurrentNodeSupportsRegionalShootout(*node))
                {
                    StartRegionalShootoutEvent();
                }
            }
            else
            {
                std::snprintf(msg, sizeof(msg), "Conflict chain spread off-screen to %s", node->displayName);
                AppendRecentEvent(msg);
                PushToast(msg);
            }
            chain = PendingConflictChain{};
            gState.saveDirty = true;
            break;
        }
    }

    int FindNodeIndexById(const char* nodeId)
    {
        for (int i = 0; i < static_cast<int>(gState.nodes.size()); ++i)
        {
            if (StringEquals(gState.nodes[static_cast<std::size_t>(i)].nodeId, nodeId))
            {
                return i;
            }
        }
        return -1;
    }

    int FindNeighborNodeSupportingFaction(const RuntimeNode& battleNode, const char* faction, bool preferTransport, bool preferOutlaw)
    {
        if (!battleNode.neighborsCsv[0] || !faction || !faction[0])
        {
            return -1;
        }
        std::stringstream ss(battleNode.neighborsCsv);
        std::string item;
        int bestIndex = -1;
        int bestScore = -999999;
        while (std::getline(ss, item, ','))
        {
            const int idx = FindNodeIndexById(item.c_str());
            if (idx < 0)
            {
                continue;
            }
            RuntimeNode& node = gState.nodes[static_cast<std::size_t>(idx)];
            if (node.contested)
            {
                continue;
            }
            const bool sameFaction = StringEquals(node.controller, faction);
            const bool lawMatch = IsLawFactionName(faction) && IsLawFactionName(node.controller);
            if (!sameFaction && !lawMatch)
            {
                continue;
            }
            int score = ScoreNeighborResponder(battleNode, node, faction, preferTransport, preferOutlaw);
            if (score > bestScore)
            {
                bestScore = score;
                bestIndex = idx;
            }
        }
        return bestIndex;
    }

    bool DispatchNeighborReinforcement(RuntimeNode& battleNode, const char* faction, SpawnedRole role, bool mounted, int count, bool preferTransport, bool preferOutlaw, const char* label)
    {
        if (RuntimeDegradedMode() && (gState.activeEnemyCount + gState.activeLawCount + gState.activeTownAttackerCount) >= 8)
        {
            return false;
        }
        const int idx = FindNeighborNodeSupportingFaction(battleNode, faction, preferTransport, preferOutlaw);
        if (idx < 0)
        {
            return false;
        }
        RuntimeNode& source = gState.nodes[static_cast<std::size_t>(idx)];
        const int finalCount = ComputeReinforcementCount(battleNode, source, role, mounted, count);
        source.supply = ClampInt(source.supply - (6 + finalCount * 2), 0, 100);
        source.fortification = ClampInt(source.fortification - (mounted ? 3 : 2), 0, 100);
        source.pressure = ClampInt(source.pressure + 6 + finalCount, 0, 100);
        source.heat = ClampInt(source.heat + 5 + finalCount, 0, 100);
        source.nextAutoEventAllowedMs = GetTickCount64() + 18000;
        RefreshLocalState(source);
        SpawnSquad(faction, finalCount, role, false, &battleNode, mounted);
        char msg[224]{};
        std::snprintf(msg, sizeof(msg), "%s from %s reinforced %s (%d riders)", label, source.displayName, battleNode.displayName, finalCount);
        PushToast(msg);
        AppendRecentEvent(msg);
        gState.saveDirty = true;
        return true;
    }


    int FindResolvedAnchorSourceIndex(const RuntimeNode& node)
    {
        if (node.hasAnchor)
        {
            return FindNodeIndexById(node.nodeId);
        }

        int bestNeighbor = -1;
        int bestNeighborScore = -999999;
        if (node.neighborsCsv[0])
        {
            std::stringstream ss(node.neighborsCsv);
            std::string item;
            while (std::getline(ss, item, ','))
            {
                const int idx = FindNodeIndexById(item.c_str());
                if (idx < 0)
                {
                    continue;
                }
                const RuntimeNode& candidate = gState.nodes[static_cast<std::size_t>(idx)];
                if (!candidate.hasAnchor)
                {
                    continue;
                }
                int score = 30;
                if (StringEquals(candidate.regionName, node.regionName)) score += 25;
                if (StringEquals(candidate.contextTag, node.contextTag)) score += 20;
                if (candidate.strategicTagsCsv[0] && node.strategicTagsCsv[0])
                {
                    if (ContainsCsvToken(candidate.strategicTagsCsv, "transport_post") && ContainsCsvToken(node.strategicTagsCsv, "transport_post")) score += 12;
                    if (ContainsCsvToken(candidate.strategicTagsCsv, "war_anchor") && ContainsCsvToken(node.strategicTagsCsv, "war_anchor")) score += 12;
                    if (ContainsCsvToken(candidate.strategicTagsCsv, "outlaw_hideout") && ContainsCsvToken(node.strategicTagsCsv, "outlaw_hideout")) score += 12;
                }
                if (score > bestNeighborScore)
                {
                    bestNeighborScore = score;
                    bestNeighbor = idx;
                }
            }
        }
        if (bestNeighbor >= 0)
        {
            return bestNeighbor;
        }

        int bestIndex = -1;
        int bestScore = -999999;
        for (int i = 0; i < static_cast<int>(gState.nodes.size()); ++i)
        {
            const RuntimeNode& candidate = gState.nodes[static_cast<std::size_t>(i)];
            if (!candidate.hasAnchor)
            {
                continue;
            }
            int score = 0;
            if (StringEquals(candidate.regionName, node.regionName)) score += 40;
            if (StringEquals(candidate.contextTag, node.contextTag)) score += 16;
            if (candidate.strategicTagsCsv[0] && node.strategicTagsCsv[0])
            {
                if (ContainsCsvToken(candidate.strategicTagsCsv, "transport_post") && ContainsCsvToken(node.strategicTagsCsv, "transport_post")) score += 10;
                if (ContainsCsvToken(candidate.strategicTagsCsv, "war_anchor") && ContainsCsvToken(node.strategicTagsCsv, "war_anchor")) score += 10;
                if (ContainsCsvToken(candidate.strategicTagsCsv, "black_market") && ContainsCsvToken(node.strategicTagsCsv, "black_market")) score += 8;
                if (ContainsCsvToken(candidate.strategicTagsCsv, "outlaw_hideout") && ContainsCsvToken(node.strategicTagsCsv, "outlaw_hideout")) score += 8;
            }
            if (score > bestScore)
            {
                bestScore = score;
                bestIndex = i;
            }
        }
        return bestIndex;
    }

    bool GetResolvedNodeAnchor(const RuntimeNode& node, Vector3* outPosition, float* outHeading, const char** outSourceNodeId, bool* outUsedProxy)
    {
        if (node.hasAnchor)
        {
            if (outPosition) *outPosition = Vector3(node.anchorX, node.anchorY, node.anchorZ);
            if (outHeading) *outHeading = node.anchorHeading;
            if (outSourceNodeId) *outSourceNodeId = node.nodeId;
            if (outUsedProxy) *outUsedProxy = false;
            return true;
        }

        const int sourceIdx = FindResolvedAnchorSourceIndex(node);
        if (sourceIdx < 0)
        {
            if (outUsedProxy) *outUsedProxy = false;
            return false;
        }
        const RuntimeNode& source = gState.nodes[static_cast<std::size_t>(sourceIdx)];
        if (!source.hasAnchor)
        {
            if (outUsedProxy) *outUsedProxy = false;
            return false;
        }
        if (outPosition) *outPosition = Vector3(source.anchorX, source.anchorY, source.anchorZ);
        if (outHeading) *outHeading = source.anchorHeading;
        if (outSourceNodeId) *outSourceNodeId = source.nodeId;
        if (outUsedProxy) *outUsedProxy = !StringEquals(source.nodeId, node.nodeId);
        return true;
    }

    bool RuntimeDegradedMode()
    {
        return gState.runtimeHealthScore > 0 && (gState.runtimeHealthScore < 72 || gState.unresolvedBindingCount >= 5 || gState.proxyAnchorCount >= 6);
    }

    int FindNearestAnchoredNodeIndex(float radius)
    {
        Actor localPlayerActor = ACTOR::GET_PLAYER_ACTOR(-1);
        if (!ACTOR::IS_ACTOR_VALID(localPlayerActor))
        {
            return -1;
        }
        const Vector3 playerPos = ACTOR::GET_POSITION(localPlayerActor);
        const float maxDistSq = radius * radius;
        float bestDistSq = maxDistSq;
        int bestIndex = -1;
        for (int i = 0; i < static_cast<int>(gState.nodes.size()); ++i)
        {
            const RuntimeNode& node = gState.nodes[static_cast<std::size_t>(i)];
            if (!node.hasAnchor)
            {
                continue;
            }
            const Vector3 nodePos(node.anchorX, node.anchorY, node.anchorZ);
            const float distSq = DistanceSquared(playerPos, nodePos);
            if (distSq <= bestDistSq)
            {
                bestDistSq = distSq;
                bestIndex = i;
            }
        }
        return bestIndex;
    }

    const CodeRedFactionSeedV26::SeedFaction& CurrentFaction()
    {
        return kSeedFactions[static_cast<std::size_t>(gState.factionIndex)];
    }

    RuntimeNode& CurrentNodeMutable()
    {
        return gState.nodes[static_cast<std::size_t>(gState.nodeIndex)];
    }

    const RuntimeNode& CurrentNode()
    {
        return gState.nodes[static_cast<std::size_t>(gState.nodeIndex)];
    }

    int BindingIndexForEngineFaction(const char* engineFaction)
    {
        for (int i = 0; i < static_cast<int>(gState.factionBindings.size()); ++i)
        {
            if (StringEquals(gState.factionBindings[static_cast<std::size_t>(i)].engineFaction, engineFaction))
            {
                return i;
            }
        }
        return -1;
    }

    int GetFactionBindingId(const char* engineFaction)
    {
        const int idx = BindingIndexForEngineFaction(engineFaction);
        return idx >= 0 ? gState.factionBindings[static_cast<std::size_t>(idx)].factionId : -1;
    }

    bool IsLawFactionName(const char* engineFaction)
    {
        const SeedFaction* seed = FindSeedFaction(engineFaction);
        return seed ? seed->lawEnforcement : false;
    }

    void WriteBindingsTemplate()
    {
        std::ofstream out(kBindingsPath, std::ios::trunc);
        if (!out)
        {
            return;
        }
        out << "# Code RED faction binding template v26\n";
        out << "# Fill in live faction IDs as you discover them. Leave -1 for unresolved IDs.\n";
        out << "# Menu-free pass: live faction sampling hotkeys are disabled. Fill IDs manually from logs/research if needed.\n";
        for (const CodeRedFactionSeedV26::SeedFaction& seed : kSeedFactions)
        {
            out << seed.engineFaction << "=-1\n";
        }
    }

    void LoadBindingsTemplate()
    {
        for (std::size_t i = 0; i < std::size(kSeedFactions); ++i)
        {
            CopyString(gState.factionBindings[i].engineFaction, sizeof(gState.factionBindings[i].engineFaction), kSeedFactions[i].engineFaction);
            gState.factionBindings[i].factionId = -1;
        }

        std::ifstream in(kBindingsPath);
        if (!in)
        {
            WriteBindingsTemplate();
            return;
        }

        std::string line;
        while (std::getline(in, line))
        {
            if (line.empty() || line[0] == '#')
            {
                continue;
            }
            const std::size_t eq = line.find('=');
            if (eq == std::string::npos)
            {
                continue;
            }
            std::string key = line.substr(0, eq);
            std::string value = line.substr(eq + 1);
            const int idx = BindingIndexForEngineFaction(key.c_str());
            if (idx >= 0)
            {
                gState.factionBindings[static_cast<std::size_t>(idx)].factionId = std::atoi(value.c_str());
            }
        }
    }

    void CaptureLiveFactionSnapshot()
    {
        Actor localPlayerActor = ACTOR::GET_PLAYER_ACTOR(-1);
        if (!ACTOR::IS_ACTOR_VALID(localPlayerActor))
        {
            PushToast("Faction snapshot failed: local player actor is not valid");
            return;
        }
        gState.localPlayerFactionId = UNSORTED::GET_ACTOR_FACTION(localPlayerActor);
        gState.focusedFactionBindingId = GetFactionBindingId(CurrentFaction().engineFaction);

        char msg[224]{};
        std::snprintf(msg, sizeof(msg), "Player faction id=%d | focused binding %s=%d",
            gState.localPlayerFactionId, CurrentFaction().engineFaction, gState.focusedFactionBindingId);
        PushToast(msg);
    }


    const char* PosseOrderName(PosseOrder order)
    {
        switch (order)
        {
        case PosseOrder::Follow:
            return "Follow";
        case PosseOrder::Hold:
            return "Hold";
        case PosseOrder::Wander:
            return "Wander";
        default:
            return "Unknown";
        }
    }

    const char* SpawnedRoleName(SpawnedRole role)
    {
        switch (role)
        {
        case SpawnedRole::Companion: return "Companion";
        case SpawnedRole::Rival: return "Rival";
        case SpawnedRole::Law: return "Law";
        case SpawnedRole::TownAttacker: return "TownAttacker";
        default: return "Unknown";
        }
    }

    bool CurrentNodeSupportsTownAssault(const RuntimeNode& node)
    {
        return StringEquals(node.contextTag, "law_town") ||
               StringEquals(node.contextTag, "black_market") ||
               StringEquals(node.contextTag, "fort_war");
    }

    const char* DeterminePreferredAutoEvent(const RuntimeNode& node)
    {
        const RegionLogistics* logistics = FindLogisticsForRegion(node.regionName);
        if (logistics)
        {
            if (StringEquals(logistics->supportState, "convoys_hot") && CurrentNodeSupportsRegionalShootout(node))
            {
                return "regional_shootout";
            }
            if (StringEquals(logistics->supportState, "fortifying") && CurrentNodeSupportsTownAssault(node) && node.heat < 60)
            {
                return CurrentNodeSupportsRegionalShootout(node) ? "regional_shootout" : "town_assault";
            }
            if (StringEquals(logistics->supportState, "starved") && CurrentNodeSupportsRegionalShootout(node) && !CurrentNodeSupportsTownAssault(node))
            {
                return "regional_shootout";
            }
        }
        if (node.roadControlState[0])
        {
            if (StringEquals(node.roadControlState, "marshal_roadblock") ||
                StringEquals(node.roadControlState, "law_patrol_lane") ||
                StringEquals(node.roadControlState, "garrison_corridor"))
            {
                return CurrentNodeSupportsRegionalShootout(node) ? "regional_shootout" : (CurrentNodeSupportsTownAssault(node) ? "town_assault" : "none");
            }
            if (StringEquals(node.roadControlState, "smuggler_lane") ||
                StringEquals(node.roadControlState, "cargo_cutthrough") ||
                StringEquals(node.roadControlState, "wagon_route") ||
                StringEquals(node.roadControlState, "supply_lane"))
            {
                return CurrentNodeSupportsRegionalShootout(node) ? "regional_shootout" : (CurrentNodeSupportsTownAssault(node) ? "town_assault" : "none");
            }
            if (StringEquals(node.roadControlState, "raider_corridor") ||
                StringEquals(node.roadControlState, "scout_watchtrail") ||
                StringEquals(node.roadControlState, "outlaw_watchtrail"))
            {
                return CurrentNodeSupportsTownAssault(node) ? "town_assault" : (CurrentNodeSupportsRegionalShootout(node) ? "regional_shootout" : "none");
            }
        }

        const char* directive = DirectiveForNode(node);
        if (directive[0])
        {
            if (StringEquals(directive, "crackdown"))
            {
                return CurrentNodeSupportsRegionalShootout(node) ? "regional_shootout" : (CurrentNodeSupportsTownAssault(node) ? "town_assault" : "none");
            }
            if (StringEquals(directive, "smuggling"))
            {
                return CurrentNodeSupportsRegionalShootout(node) ? "regional_shootout" : (CurrentNodeSupportsTownAssault(node) ? "town_assault" : "none");
            }
            if (StringEquals(directive, "raid"))
            {
                return CurrentNodeSupportsTownAssault(node) ? "town_assault" : (CurrentNodeSupportsRegionalShootout(node) ? "regional_shootout" : "none");
            }
        }

        if (CurrentNodeSupportsTownAssault(node)) return "town_assault";
        if (CurrentNodeSupportsRegionalShootout(node)) return "regional_shootout";
        return "none";
    }

    const char* DescribeEntryConflictBias(const RuntimeNode& node)
    {
        if (node.roadControlState[0])
        {
            if (StringEquals(node.roadControlState, "marshal_roadblock")) return "Marshal Roadblock";
            if (StringEquals(node.roadControlState, "law_patrol_lane")) return "Patrol Sweep";
            if (StringEquals(node.roadControlState, "garrison_corridor")) return "Garrison Push";
            if (StringEquals(node.roadControlState, "smuggler_lane")) return "Smuggler Intercept";
            if (StringEquals(node.roadControlState, "cargo_cutthrough")) return "Cargo Cutthrough";
            if (StringEquals(node.roadControlState, "wagon_route")) return "Wagon Pressure";
            if (StringEquals(node.roadControlState, "supply_lane")) return "Supply Escort";
            if (StringEquals(node.roadControlState, "raider_corridor")) return "Mounted Raider Push";
            if (StringEquals(node.roadControlState, "scout_watchtrail") || StringEquals(node.roadControlState, "outlaw_watchtrail")) return "Scout Ambush";
            if (StringEquals(node.roadControlState, "salvage_track")) return "Salvage Tension";
        }

        const RegionLogistics* logistics = FindLogisticsForRegion(node.regionName);
        if (logistics)
        {
            if (StringEquals(logistics->supportState, "starved")) return "Starved Front";
            if (StringEquals(logistics->supportState, "convoys_hot")) return "Convoy Intercept";
            if (StringEquals(logistics->supportState, "fortifying")) return "Fortified Hold";
            if (StringEquals(logistics->supportState, "searched")) return "Search Sweep";
            if (StringEquals(logistics->supportState, "recovering")) return "Recovery Patrol";
        }

        const char* directive = DirectiveForNode(node);
        if (directive[0])
        {
            if (StringEquals(directive, "crackdown")) return "Crackdown Sweep";
            if (StringEquals(directive, "smuggling")) return "Smuggling Window";
            if (StringEquals(directive, "raid")) return "Raid Muster";
            if (StringEquals(directive, "fortify")) return "Fortified Response";
            if (StringEquals(directive, "scavenge")) return "Scavenger Trouble";
        }

        return CurrentNodeSupportsTownAssault(node) ? "Town Assault" : (CurrentNodeSupportsRegionalShootout(node) ? "Regional Shootout" : "Frontier Pressure");
    }

    bool AutoEventWantsMountedOutlaws(const RuntimeNode& node)
    {
        const bool wants = StringEquals(node.roadControlState, "raider_corridor") ||
               StringEquals(node.roadControlState, "scout_watchtrail") ||
               StringEquals(node.roadControlState, "outlaw_watchtrail") ||
               StringEquals(DirectiveForNode(node), "raid") ||
               StringEquals(node.populationProfile, "gang_muster") ||
               StringEquals(LogisticsBattleProfile(node), "convoy_front");
        return wants && LogisticsAllowsMounted(node, SpawnedRole::Rival);
    }

    bool AutoEventWantsMountedLaw(const RuntimeNode& node)
    {
        const bool wants = StringEquals(node.roadControlState, "law_patrol_lane") ||
               StringEquals(node.roadControlState, "garrison_corridor") ||
               StringEquals(node.roadControlState, "marshal_roadblock") ||
               StringEquals(DirectiveForNode(node), "crackdown") ||
               StringEquals(DirectiveForNode(node), "fortify") ||
               StringEquals(node.populationProfile, "marshal_heavy") ||
               StringEquals(node.populationProfile, "garrison_build_up") ||
               StringEquals(LogisticsBattleProfile(node), "fortified_front");
        return wants && LogisticsAllowsMounted(node, SpawnedRole::Law);
    }

    int DetermineAutoEventCooldownMs(const RuntimeNode& node, const char* preferredEvent, bool dailyPending)
    {
        int cooldown = dailyPending ? 18000 : 42000;
        if (StringEquals(preferredEvent, "town_assault"))
        {
            cooldown += 4000;
        }
        if (StringEquals(node.roadControlState, "raider_corridor") || StringEquals(DirectiveForNode(node), "raid"))
        {
            cooldown -= 5000;
        }
        if (StringEquals(node.roadControlState, "marshal_roadblock") || StringEquals(DirectiveForNode(node), "crackdown"))
        {
            cooldown -= 2500;
        }
        if (StringEquals(node.roadControlState, "garrison_corridor") || StringEquals(DirectiveForNode(node), "fortify"))
        {
            cooldown += 2500;
        }
        const RegionLogistics* logistics = FindLogisticsForRegion(node.regionName);
        if (logistics)
        {
            if (StringEquals(logistics->supportState, "convoys_hot")) cooldown -= 2500;
            else if (StringEquals(logistics->supportState, "fortifying")) cooldown += 3000;
            else if (StringEquals(logistics->supportState, "starved")) cooldown += 2000;
        }
        const RegionCadence* cadence = FindCadenceForRegion(node.regionName);
        if (cadence)
        {
            if (StringEquals(cadence->cadenceState, "surging")) cooldown -= 5000;
            else if (StringEquals(cadence->cadenceState, "active")) cooldown -= 1500;
            else if (StringEquals(cadence->cadenceState, "recovering")) cooldown += 9000;
            else if (StringEquals(cadence->cadenceState, "spent")) cooldown += 14000;
            else if (StringEquals(cadence->cadenceState, "quiet")) cooldown += 5000;
        }
        return ClampInt(cooldown, 12000, 85000);
    }

    void RecountSpawnedActors()
    {
        gState.activeFriendlyCount = 0;
        gState.activeEnemyCount = 0;
        gState.activeLawCount = 0;
        gState.activeTownAttackerCount = 0;
        for (SpawnedActorState& spawned : gState.spawnedActors)
        {
            if (spawned.active && !ACTOR::IS_ACTOR_VALID(spawned.actor))
            {
                spawned = SpawnedActorState{};
            }
            if (!spawned.active)
            {
                continue;
            }
            switch (spawned.role)
            {
            case SpawnedRole::Companion:
                ++gState.activeFriendlyCount;
                break;
            case SpawnedRole::Law:
                ++gState.activeLawCount;
                ++gState.activeEnemyCount;
                break;
            case SpawnedRole::TownAttacker:
                ++gState.activeTownAttackerCount;
                ++gState.activeEnemyCount;
                break;
            case SpawnedRole::Rival:
                ++gState.activeEnemyCount;
                break;
            }
        }
    }

    int CountActiveRole(SpawnedRole role)
    {
        int count = 0;
        for (const SpawnedActorState& spawned : gState.spawnedActors)
        {
            if (spawned.active && spawned.role == role && ACTOR::IS_ACTOR_VALID(spawned.actor))
            {
                ++count;
            }
        }
        return count;
    }

    int FindFreeSpawnSlot()
    {
        for (int i = 0; i < static_cast<int>(gState.spawnedActors.size()); ++i)
        {
            if (!gState.spawnedActors[static_cast<std::size_t>(i)].active)
            {
                return i;
            }
        }
        return -1;
    }

    Vector3 ComputeSpawnOrbit(const Vector3& origin, float headingDegrees, float radius, int slotIndex, float extraAngleDegrees)
    {
        const float angleDegrees = headingDegrees + extraAngleDegrees + static_cast<float>(slotIndex) * 28.0f;
        const float angleRadians = angleDegrees * 3.1415926535f / 180.0f;
        return Vector3(origin.x + std::cos(angleRadians) * radius,
                       origin.y + std::sin(angleRadians) * radius,
                       origin.z);
    }

    float DistanceSquared(const Vector3& a, const Vector3& b)
    {
        const float dx = a.x - b.x;
        const float dy = a.y - b.y;
        const float dz = a.z - b.z;
        return dx * dx + dy * dy + dz * dz;
    }

    bool RequestActorModelLoaded(ActorModel model)
    {
        STREAM::STREAMING_REQUEST_ACTOR(model, true, false);
        const uint64_t startTick = GetTickCount64();
        while (!STREAM::STREAMING_IS_ACTOR_LOADED(model, -1) && GetTickCount64() < startTick + 1500)
        {
            ScriptWait(0);
        }
        return STREAM::STREAMING_IS_ACTOR_LOADED(model, -1);
    }

    Actor SpawnActorAt(Layout layout, ActorModel model, const Vector3& position, float headingDegrees)
    {
        if (!RequestActorModelLoaded(model))
        {
            return 0;
        }
        Vector2 pos2(position.x, position.y);
        Vector2 rot2(0.0f, headingDegrees);
        Actor actor = ACTOR::CREATE_ACTOR_IN_LAYOUT(layout, "", model, pos2, position.z, rot2, 0.0f);
        if (ACTOR::IS_ACTOR_VALID(actor))
        {
            ACTOR::SET_ACTOR_HEADING(actor, headingDegrees, false);
        }
        return actor;
    }

    Actor SpawnHorseForActor(Layout layout, Actor rider, const Vector3& riderPos, float headingDegrees, int horseIndex)
    {
        const ActorModel horseModel = static_cast<ActorModel>(976 + (horseIndex % 24));
        Vector3 horsePos = riderPos;
        horsePos.x += 1.5f;
        horsePos.y += 1.0f;
        Actor horse = SpawnActorAt(layout, horseModel, horsePos, headingDegrees);
        if (ACTOR::IS_ACTOR_VALID(horse))
        {
            UNSORTED::ACTOR_MOUNT_ACTOR(rider, horse);
        }
        return horse;
    }

    ActorModel SelectModelForFaction(const char* engineFaction, bool leader, int index)
    {
        if (StringEquals(engineFaction, "USLawEnforcement"))
        {
            static constexpr ActorModel kLaw[] = {
                ACTOR_COMPANION_Marshal,
                ACTOR_MISC_Deputy_Marshal01,
                ACTOR_MISC_Deputy_Marshal02,
                ACTOR_MISC_Deputy_Marshal03,
            };
            return leader ? kLaw[0] : kLaw[1 + (index % 3)];
        }
        if (StringEquals(engineFaction, "MexicanLawEnforcement"))
        {
            static constexpr ActorModel kMexLaw[] = {
                ACTOR_MISC_RebelSoldier01,
                ACTOR_MISC_RebelSoldier02,
                ACTOR_MISC_RebelSoldier03,
            };
            return kMexLaw[index % 3];
        }
        if (StringEquals(engineFaction, "CattleRustler"))
        {
            static constexpr ActorModel kRustlers[] = {
                ACTOR_MISC_BillsGang01,
                ACTOR_MISC_BillsGang02,
                ACTOR_MISC_BillsGang03,
                ACTOR_MISC_BillsGang04,
                ACTOR_MISC_BillsGang05,
            };
            return kRustlers[index % 5];
        }
        if (StringEquals(engineFaction, "TreasureHunter"))
        {
            static constexpr ActorModel kHunters[] = {
                ACTOR_MISC_TreasureHunter_Leader,
                ACTOR_MISC_MineWorker,
                ACTOR_MISC_Outlaw_01,
            };
            return leader ? kHunters[0] : kHunters[1 + (index % 2)];
        }
        if (StringEquals(engineFaction, "MexicanBandito"))
        {
            static constexpr ActorModel kBanditos[] = {
                ACTOR_COMPANION_MexicanHenchman,
                ACTOR_MISC_RebelSoldier05,
                ACTOR_MISC_RebelSoldier06,
            };
            return leader ? kBanditos[0] : kBanditos[1 + (index % 2)];
        }
        if (StringEquals(engineFaction, "IndianRaider"))
        {
            static constexpr ActorModel kRaiders[] = {
                ACTOR_COMPANION_NativeFriend,
                ACTOR_COMPANION_NativeFriend_02,
                ACTOR_MISC_BanditRider01,
            };
            return kRaiders[index % 3];
        }
        if (StringEquals(engineFaction, "PlayerFriendly") || StringEquals(engineFaction, "PlayerNeutral"))
        {
            static constexpr ActorModel kSettlers[] = {
                ACTOR_MISC_RanchHand01,
                ACTOR_MISC_RanchHand02,
                ACTOR_CAUCASIAN_MALE_Farmer01,
            };
            return kSettlers[index % 3];
        }

        static constexpr ActorModel kCriminals[] = {
            ACTOR_COMPANION_Outlaw,
            ACTOR_MISC_Outlaw_01,
            ACTOR_MISC_BanditRider01,
            ACTOR_MISC_BanditRider02,
        };
        return leader ? kCriminals[0] : kCriminals[1 + (index % 3)];
    }

    void LogLine(const char* text)
    {
        std::ofstream out(kLogPath, std::ios::app);
        if (!out)
        {
            return;
        }
        out << text << "\n";
    }

    int CountUnresolvedBindings()
    {
        int count = 0;
        for (const FactionBinding& binding : gState.factionBindings)
        {
            if (binding.engineFaction[0] && binding.factionId < 0)
            {
                ++count;
            }
        }
        return count;
    }

    int CountProxyAnchors()
    {
        int count = 0;
        for (const RuntimeNode& node : gState.nodes)
        {
            bool usedProxy = false;
            if (!GetResolvedNodeAnchor(node, nullptr, nullptr, nullptr, &usedProxy) || usedProxy)
            {
                ++count;
            }
        }
        return count;
    }

    int EvaluateRuntimeHealthScore()
    {
        int score = 100;
        const int unresolved = CountUnresolvedBindings();
        const int proxyAnchors = CountProxyAnchors();
        score -= unresolved * 3;
        score -= proxyAnchors;
        if (gState.nodes.empty())
        {
            score -= 30;
        }
        if (!gState.simulationEnabled)
        {
            score -= 10;
        }
        return ClampInt(score, 0, 100);
    }

    void WriteDiagnosticsReport(bool force)
    {
        const uint64_t now = GetTickCount64();
        if (!force && !gState.diagnosticsDirty && now < gState.nextDiagnosticsTickMs)
        {
            return;
        }

        gState.unresolvedBindingCount = CountUnresolvedBindings();
        gState.proxyAnchorCount = CountProxyAnchors();
        gState.runtimeHealthScore = EvaluateRuntimeHealthScore();

        std::ofstream out(kDiagnosticsPath, std::ios::trunc);
        if (!out)
        {
            gState.nextDiagnosticsTickMs = now + 15000;
            return;
        }

        out << "Code RED Faction War v26 Diagnostics\n";
        out << "health=" << gState.runtimeHealthScore << "\n";
        out << "unresolved_bindings=" << gState.unresolvedBindingCount << "\n";
        out << "proxy_anchors=" << gState.proxyAnchorCount << "\n";
        out << "active_fronts=" << CountActiveRegionFronts() << "\n";
        out << "pending_chains=" << CountPendingConflictChains() << "\n";
        out << "game_day=" << gState.gameDay << "\n";
        out << "game_hour=" << gState.gameHour << "\n\n";
        out << "[bindings]\n";
        for (const FactionBinding& binding : gState.factionBindings)
        {
            out << binding.engineFaction << '=' << binding.factionId << "\n";
        }
        out << "\n[hot_nodes]\n";
        for (const RuntimeNode& node : gState.nodes)
        {
            out << node.nodeId << '|' << node.displayName << '|' << node.regionName << '|' << node.controller << '|'
                << ComputeNodeHotness(node) << '|' << node.roadControlState << '|'
                << LogisticsStateName(node) << '|' << LogisticsBattleProfile(node) << '|'
                << (OccupationActive(node) ? node.occupationState : "none") << "\n";
        }
        out << "\n[fronts]\n";
        for (const RegionPressureFront& front : gState.regionFronts)
        {
            if (!front.active)
            {
                continue;
            }
            out << front.regionName << '|' << front.frontState << '|' << front.lawPressure << '|' << front.outlawPressure << "\n";
        }
        out << "\n[logistics]\n";
        for (const RegionLogistics& logistics : gState.regionLogistics)
        {
            if (!logistics.active)
            {
                continue;
            }
            out << logistics.regionName << '|' << logistics.supportState << '|' << logistics.stock << '|' << logistics.convoyPressure << '|' << logistics.strain << "\n";
        }
        out << "\n[climate]\n";
        for (const RegionCivilianClimate& climate : gState.regionClimate)
        {
            if (!climate.active)
            {
                continue;
            }
            out << climate.regionName << '|' << climate.climateState << '|' << climate.support << '|' << climate.panic << '|' << climate.repression << '|' << climate.rumorTrust << "\n";
        }

        gState.diagnosticsDirty = false;
        gState.diagnosticsWrites += 1;
        gState.diagnosticsLastDay = gState.gameDay;
        gState.nextDiagnosticsTickMs = now + 15000;
    }

    void MarkDiagnosticsDirty()
    {
        gState.diagnosticsDirty = true;
    }

    void AppendRecentEvent(const char* text)
    {
        if (!text || !text[0])
        {
            return;
        }
        CopyString(gState.recentEvents[gState.recentEventCursor], sizeof(gState.recentEvents[gState.recentEventCursor]), text);
        gState.recentEventCursor = (gState.recentEventCursor + 1) % 6;
        if (gState.recentEventCount < 6)
        {
            ++gState.recentEventCount;
        }
    }

    void BuildRecentEventsBlock(char* outText, std::size_t outSize)
    {
        if (!outText || outSize == 0)
        {
            return;
        }
        outText[0] = '\0';
        if (gState.recentEventCount <= 0)
        {
            std::snprintf(outText, outSize, "No frontier events recorded yet.");
            return;
        }

        std::size_t used = 0;
        for (int i = 0; i < gState.recentEventCount; ++i)
        {
            const int idx = (gState.recentEventCursor - 1 - i + 6) % 6;
            const char* entry = gState.recentEvents[idx];
            if (!entry[0])
            {
                continue;
            }
            int written = std::snprintf(outText + used, outSize - used, "%s%s", used ? "\n- " : "- ", entry);
            if (written < 0)
            {
                break;
            }
            used += static_cast<std::size_t>(written);
            if (used >= outSize)
            {
                outText[outSize - 1] = '\0';
                break;
            }
        }
    }

    void PushToast(const char* text)
    {
        CopyString(gState.lastToast, sizeof(gState.lastToast), text);
        AppendRecentEvent(text);
        LogLine(text);
        MarkDiagnosticsDirty();
        if (kEnableHudToasts)
        {
            HUD::PRINT_SMALL_B(text, 0.75f, true, 0, 0, 0, 0);
        }
    }

    void BindActorFactionIfKnown(Actor actor, const char* engineFaction)
    {
        if (!ACTOR::IS_ACTOR_VALID(actor))
        {
            return;
        }
        const int factionId = GetFactionBindingId(engineFaction);
        if (factionId < 0)
        {
            char msg[192]{};
            std::snprintf(msg, sizeof(msg), "Unresolved faction binding for %s during actor bind", engineFaction ? engineFaction : "unknown");
            LogLine(msg);
            MarkDiagnosticsDirty();
            return;
        }
        UNSORTED::SET_ACTOR_FACTION(actor, factionId);
    }

    void ClearSpawnedActor(SpawnedActorState& spawned, bool destroyActor)
    {
        if (spawned.active)
        {
            if (destroyActor && ACTOR::IS_ACTOR_VALID(spawned.actor))
            {
                ACTOR::DESTROY_ACTOR(spawned.actor);
            }
            if (destroyActor && ACTOR::IS_ACTOR_VALID(spawned.mountActor))
            {
                ACTOR::DESTROY_ACTOR(spawned.mountActor);
            }
        }
        spawned = SpawnedActorState{};
    }

    void DespawnAllSpawnedActors(bool pushToast)
    {
        for (SpawnedActorState& spawned : gState.spawnedActors)
        {
            ClearSpawnedActor(spawned, true);
        }
        RecountSpawnedActors();
        gState.townAssault = TownAssaultState{};
        if (pushToast)
        {
            PushToast("Cleared all spawned faction-war squads");
        }
    }

    void DespawnBattleActors(bool pushToast)
    {
        for (SpawnedActorState& spawned : gState.spawnedActors)
        {
            if (spawned.active && spawned.role != SpawnedRole::Companion)
            {
                ClearSpawnedActor(spawned, true);
            }
        }
        RecountSpawnedActors();
        gState.townAssault = TownAssaultState{};
        if (pushToast)
        {
            PushToast("Cleared active battle squads");
        }
    }

    void ApplyCurrentPosseOrder()
    {
        Actor localPlayerActor = ACTOR::GET_PLAYER_ACTOR(-1);
        if (!ACTOR::IS_ACTOR_VALID(localPlayerActor))
        {
            return;
        }

        for (SpawnedActorState& spawned : gState.spawnedActors)
        {
            if (!spawned.active || spawned.role != SpawnedRole::Companion || !ACTOR::IS_ACTOR_VALID(spawned.actor))
            {
                continue;
            }

            TASKS::TASK_CLEAR(spawned.actor);
            switch (gState.posseOrder)
            {
            case PosseOrder::Follow:
                TASKS::TASK_FOLLOW_ACTOR(spawned.actor, localPlayerActor);
                break;
            case PosseOrder::Hold:
                TASKS::TASK_STAND_STILL(spawned.actor, 60, 0, 0);
                break;
            case PosseOrder::Wander:
                TASKS::TASK_WANDER(spawned.actor, 0);
                break;
            }
        }
    }

    Actor FindBestCombatTargetFor(const SpawnedActorState& self)
    {
        if (!ACTOR::IS_ACTOR_VALID(self.actor))
        {
            return 0;
        }
        const Vector3 selfPos = ACTOR::GET_POSITION(self.actor);
        float bestDist = 1.0e30f;
        Actor bestActor = 0;
        for (const SpawnedActorState& other : gState.spawnedActors)
        {
            if (!other.active || !ACTOR::IS_ACTOR_VALID(other.actor) || other.actor == self.actor)
            {
                continue;
            }
            bool enemy = false;
            if (self.role == SpawnedRole::Law)
            {
                enemy = other.role == SpawnedRole::TownAttacker || other.role == SpawnedRole::Rival;
            }
            else if (self.role == SpawnedRole::TownAttacker)
            {
                enemy = other.role == SpawnedRole::Law;
            }
            else if (self.role == SpawnedRole::Rival)
            {
                enemy = other.role == SpawnedRole::Law;
            }
            if (!enemy)
            {
                continue;
            }
            const float dist = DistanceSquared(selfPos, ACTOR::GET_POSITION(other.actor));
            if (dist < bestDist)
            {
                bestDist = dist;
                bestActor = other.actor;
            }
        }
        if (!ACTOR::IS_ACTOR_VALID(bestActor) && self.role == SpawnedRole::Rival)
        {
            Actor localPlayerActor = ACTOR::GET_PLAYER_ACTOR(-1);
            if (ACTOR::IS_ACTOR_VALID(localPlayerActor))
            {
                bestActor = localPlayerActor;
            }
        }
        return bestActor;
    }

    void RetaskDynamicCombat(bool force = false)
    {
        const uint64_t now = GetTickCount64();
        if (!force && now < gState.nextCombatRetaskTickMs)
        {
            return;
        }
        for (SpawnedActorState& spawned : gState.spawnedActors)
        {
            if (!spawned.active || !ACTOR::IS_ACTOR_VALID(spawned.actor) || spawned.role == SpawnedRole::Companion)
            {
                continue;
            }
            Actor target = FindBestCombatTargetFor(spawned);
            if (ACTOR::IS_ACTOR_VALID(target))
            {
                TASKS::TASK_CLEAR(spawned.actor);
                TASKS::TASK_KILL_CHAR(spawned.actor, target);
                UNSORTED::MEMORY_ATTACK_ON_SIGHT(spawned.actor, true);
            }
        }
        gState.nextCombatRetaskTickMs = now + 2500;
    }

    const char* DetermineRivalFaction()
    {
        const RuntimeNode& node = CurrentNode();
        if (node.activeAssaultFaction[0] && !StringEquals(node.activeAssaultFaction, CurrentFaction().engineFaction))
        {
            return node.activeAssaultFaction;
        }
        if (StringEquals(node.contextTag, "mine_hideout"))
        {
            return "TreasureHunter";
        }
        if (StringEquals(node.contextTag, "fort_war") || StringEquals(node.contextTag, "bandito_outpost"))
        {
            return "MexicanBandito";
        }
        if (StringEquals(node.contextTag, "law_town") || StringEquals(node.contextTag, "rail_checkpoint"))
        {
            return "USLawEnforcement";
        }
        if (StringEquals(node.contextTag, "black_market"))
        {
            return "GenericCriminal";
        }
        if (StringEquals(node.contextTag, "rustler_hideout") || StringEquals(node.contextTag, "camp_hideout") || StringEquals(node.contextTag, "roadside_robbery"))
        {
            return "CattleRustler";
        }
        if (!StringEquals(node.controller, CurrentFaction().engineFaction))
        {
            return node.controller;
        }
        return CurrentFaction().lawEnforcement ? "CattleRustler" : "USLawEnforcement";
    }

    const char* DetermineLawFactionForNode(const RuntimeNode& node)
    {
        return StringEquals(node.regionName, "Nuevo Paraiso") ? "MexicanLawEnforcement" : "USLawEnforcement";
    }

    const char* DetermineOutlawPressureFaction(const RuntimeNode& node)
    {
        if (!CurrentFaction().lawEnforcement)
        {
            return CurrentFaction().engineFaction;
        }
        if (!StringEquals(node.controller, "USLawEnforcement") && !StringEquals(node.controller, "MexicanLawEnforcement") && !StringEquals(node.controller, "PlayerNeutral") && !StringEquals(node.controller, "PlayerFriendly"))
        {
            return node.controller;
        }
        if (StringEquals(node.contextTag, "fort_war") || StringEquals(node.contextTag, "bandito_outpost"))
        {
            return "MexicanBandito";
        }
        if (StringEquals(node.contextTag, "mine_hideout"))
        {
            return "TreasureHunter";
        }
        if (StringEquals(node.contextTag, "black_market"))
        {
            return "GenericCriminal";
        }
        if (StringEquals(node.contextTag, "camp_hideout") || StringEquals(node.contextTag, "rustler_hideout") || StringEquals(node.contextTag, "roadside_robbery"))
        {
            return "CattleRustler";
        }
        if (StringEquals(node.regionName, "rio_bravo"))
        {
            return "MexicanBandito";
        }
        return "CattleRustler";
    }

    const char* DetermineTownAssaultFaction(const RuntimeNode& node)
    {
        return DetermineOutlawPressureFaction(node);
    }

    bool CurrentNodeSupportsRegionalShootout(const RuntimeNode& node)
    {
        return StringEquals(node.contextTag, "camp_hideout")
            || StringEquals(node.contextTag, "rustler_hideout")
            || StringEquals(node.contextTag, "mine_hideout")
            || StringEquals(node.contextTag, "black_market")
            || StringEquals(node.contextTag, "roadside_robbery")
            || StringEquals(node.contextTag, "rail_checkpoint")
            || ContainsCsvToken(node.strategicTagsCsv, "outlaw_hideout")
            || ContainsCsvToken(node.strategicTagsCsv, "black_market");
    }

    bool IsPlayerNearNode(const RuntimeNode& node, float radius)
    {
        Actor localPlayerActor = ACTOR::GET_PLAYER_ACTOR(-1);
        if (!ACTOR::IS_ACTOR_VALID(localPlayerActor))
        {
            return false;
        }
        Vector3 nodePos{};
        if (!GetResolvedNodeAnchor(node, &nodePos, nullptr, nullptr, nullptr))
        {
            return true;
        }
        const Vector3 playerPos = ACTOR::GET_POSITION(localPlayerActor);
        return DistanceSquared(playerPos, nodePos) <= radius * radius;
    }

    void RefreshAutoRegionFocus()
    {
        const uint64_t now = GetTickCount64();
        if (now < gState.nextRegionScanTickMs)
        {
            return;
        }
        gState.nextRegionScanTickMs = now + 1500;

        const int nearestIndex = FindNearestAnchoredNodeIndex(220.0f);
        if (nearestIndex < 0 || nearestIndex >= static_cast<int>(gState.nodes.size()))
        {
            return;
        }
        RuntimeNode& nearest = gState.nodes[static_cast<std::size_t>(nearestIndex)];
        const int regionalHotIndex = FindRegionalHotNodeIndex(nearest.regionName);
        const int focusIndex = regionalHotIndex >= 0 ? regionalHotIndex : nearestIndex;
        RuntimeNode& focusNode = gState.nodes[static_cast<std::size_t>(focusIndex)];
        if (!StringEquals(gState.autoRegionNodeId, focusNode.nodeId))
        {
            CopyString(gState.autoRegionNodeId, sizeof(gState.autoRegionNodeId), focusNode.nodeId);
            gState.nodeIndex = focusIndex;
            char msg[256]{};
            std::snprintf(msg, sizeof(msg), "Entered %s region envelope / hotspot %s", nearest.displayName, focusNode.displayName);
            PushToast(msg);
            if (!gState.activeMission.valid && NodeSupportsAutoBattle(focusNode))
            {
                GenerateMissionFromCurrentState();
            }
        }
    }

    void SpawnSquad(const char* sourceFaction, int requestedCount, SpawnedRole role, bool companionSquad, const RuntimeNode* nodeContext = nullptr, bool mounted = false)
    {
        Actor localPlayerActor = ACTOR::GET_PLAYER_ACTOR(-1);
        if (!ACTOR::IS_ACTOR_VALID(localPlayerActor))
        {
            PushToast("Spawn skipped: local player actor is not valid");
            return;
        }

        RecountSpawnedActors();
        const int available = static_cast<int>(gState.spawnedActors.size()) - (gState.activeFriendlyCount + gState.activeEnemyCount);
        int count = ClampInt(requestedCount, 0, available);
        if (RuntimeDegradedMode() && !companionSquad && count > 2)
        {
            count -= 1;
        }
        if (count <= 0)
        {
            PushToast("Spawn skipped: no free squad slots remain");
            return;
        }

        Layout layout = OBJECT::FIND_NAMED_LAYOUT("PlayerLayout");
        const RuntimeNode* battleNode = nodeContext ? nodeContext : &CurrentNode();
        Vector3 center = ACTOR::GET_POSITION(localPlayerActor);
        float baseHeading = ACTOR::GET_HEADING(localPlayerActor);
        if (battleNode && role != SpawnedRole::Companion)
        {
            Vector3 resolvedPos{};
            float resolvedHeading = baseHeading;
            if (GetResolvedNodeAnchor(*battleNode, &resolvedPos, &resolvedHeading, nullptr, nullptr))
            {
                center = resolvedPos;
                baseHeading = resolvedHeading;
            }
        }

        const float radius = companionSquad ? 5.0f : (role == SpawnedRole::TownAttacker ? 42.0f : (role == SpawnedRole::Law ? 14.0f : 12.0f));
        const float extraAngle = companionSquad ? -70.0f : (role == SpawnedRole::TownAttacker ? 180.0f : (role == SpawnedRole::Law ? 0.0f : 110.0f));

        int spawnedCount = 0;
        for (int i = 0; i < count; ++i)
        {
            const int slot = FindFreeSpawnSlot();
            if (slot < 0)
            {
                break;
            }

            const bool leader = (i == 0);
            const ActorModel model = SelectModelForFaction(sourceFaction, leader, i);
            Vector3 spawnPos = ComputeSpawnOrbit(center, baseHeading, radius, i, extraAngle);
            float actorHeading = baseHeading;
            if (role == SpawnedRole::TownAttacker && battleNode && battleNode->hasAnchor)
            {
                actorHeading = battleNode->anchorHeading + 180.0f;
            }
            Actor spawnedActor = SpawnActorAt(layout, model, spawnPos, actorHeading);
            if (!ACTOR::IS_ACTOR_VALID(spawnedActor))
            {
                continue;
            }

            SpawnedActorState& slotRef = gState.spawnedActors[static_cast<std::size_t>(slot)];
            slotRef.actor = spawnedActor;
            slotRef.model = model;
            slotRef.active = true;
            slotRef.companion = companionSquad;
            slotRef.role = companionSquad ? SpawnedRole::Companion : role;
            slotRef.mounted = false;
            CopyString(slotRef.sourceFaction, sizeof(slotRef.sourceFaction), sourceFaction);
            BindActorFactionIfKnown(spawnedActor, sourceFaction);

            if (companionSquad)
            {
                UNSORTED::SET_ACTOR_IS_COMPANION(spawnedActor, true);
                TASKS::TASK_FOLLOW_ACTOR(spawnedActor, localPlayerActor);
            }
            else if (mounted)
            {
                slotRef.mountActor = SpawnHorseForActor(layout, spawnedActor, spawnPos, actorHeading, i);
                slotRef.mounted = ACTOR::IS_ACTOR_VALID(slotRef.mountActor);
            }
            else if (role == SpawnedRole::Rival)
            {
                TASKS::TASK_KILL_CHAR(spawnedActor, localPlayerActor);
            }
            ++spawnedCount;
        }

        RecountSpawnedActors();
        gState.saveDirty = true;
        if (companionSquad)
        {
            ApplyCurrentPosseOrder();
        }
        else
        {
            RetaskDynamicCombat(true);
        }

        char msg[224]{};
        std::snprintf(msg, sizeof(msg), "%s squad spawned: %d from %s%s", SpawnedRoleName(companionSquad ? SpawnedRole::Companion : role), spawnedCount, sourceFaction, mounted ? " (mounted)" : "");
        PushToast(msg);
    }

    void SpawnAllyPosse()
    {
        if (gState.rankIndex <= 0)
        {
            PushToast("Outsider rank cannot summon a faction posse yet");
            return;
        }
        const RuntimeNode& node = CurrentNode();
        int count = gState.playerLeading ? 3 : 2;
        if (StringEquals(node.contextTag, "fort_war") || StringEquals(node.contextTag, "law_town"))
        {
            ++count;
        }
        if (ContainsCsvToken(node.strategicTagsCsv, "transport_post"))
        {
            ++count;
        }
        if ((CurrentFaction().lawEnforcement && node.lawWeight >= 65) || (!CurrentFaction().lawEnforcement && node.outlawWeight >= 65))
        {
            ++count;
        }
        SpawnSquad(CurrentFaction().engineFaction, ClampInt(count, 2, 5), SpawnedRole::Companion, true, nullptr, false);
    }

    void SpawnRivalRaid()
    {
        const RuntimeNode& node = CurrentNode();
        int count = node.contested ? 4 : 3;
        if (StringEquals(node.contextTag, "fort_war") || StringEquals(node.contextTag, "camp_hideout"))
        {
            ++count;
        }
        SpawnSquad(DetermineRivalFaction(), ClampInt(count, 3, 5), SpawnedRole::Rival, false, &node, false);
    }

    void StartRegionalShootoutEvent()
    {
        RuntimeNode& node = CurrentNodeMutable();
        if (!CurrentNodeSupportsRegionalShootout(node))
        {
            PushToast("Current node does not support a regional law shootout profile");
            return;
        }
        if (gState.townAssault.active || gState.regionalShootout.active)
        {
            PushToast("Another regional battle is already active");
            return;
        }

        DespawnBattleActors(false);
        const char* outlawFaction = DetermineOutlawPressureFaction(node);
        const char* lawFaction = DetermineLawFactionForNode(node);
        CopyString(gState.regionalShootout.nodeId, sizeof(gState.regionalShootout.nodeId), node.nodeId);
        CopyString(gState.regionalShootout.outlawFaction, sizeof(gState.regionalShootout.outlawFaction), outlawFaction);
        CopyString(gState.regionalShootout.lawFaction, sizeof(gState.regionalShootout.lawFaction), lawFaction);
        gState.regionalShootout.active = true;
        gState.regionalShootout.resolveDeadlineMs = GetTickCount64() + LogisticsResolveDurationMs(node);

        CopyString(node.activeAssaultFaction, sizeof(node.activeAssaultFaction), outlawFaction);
        node.contested = true;
        MarkNodeEventTriggered(node, "Regional shootout");
        node.heat = ClampInt(node.heat + 12, 0, 100);
        node.fear = ClampInt(node.fear + 9, 0, 100);
        node.pressure = ClampInt(node.pressure + 8, 0, 100);
        RefreshLocalState(node);

        int outlawCount = StringEquals(node.contextTag, "black_market") ? 4 : 3;
        int lawCount = StringEquals(node.contextTag, "rail_checkpoint") ? 3 : 2;
        if (node.outlawWeight >= 65) ++outlawCount;
        if (node.lawWeight >= 65) ++lawCount;
        if (node.wagonWeight >= 70 && StringEquals(DirectiveForNode(node), "smuggling")) ++outlawCount;
        if (StringEquals(DirectiveForNode(node), "crackdown")) ++lawCount;
        if (StringEquals(DirectiveForNode(node), "raid")) ++outlawCount;
        if (StringEquals(node.populationProfile, "marshal_heavy")) ++lawCount;
        if (StringEquals(node.populationProfile, "gang_muster")) ++outlawCount;
        if (StringEquals(node.roadControlState, "marshal_roadblock") || StringEquals(node.roadControlState, "law_patrol_lane")) { lawCount += 2; ++outlawCount; }
        if (StringEquals(node.roadControlState, "garrison_corridor")) { lawCount += 2; }
        if (StringEquals(node.roadControlState, "smuggler_lane") || StringEquals(node.roadControlState, "cargo_cutthrough") || StringEquals(node.roadControlState, "wagon_route")) { ++outlawCount; ++lawCount; }
        if (StringEquals(node.roadControlState, "raider_corridor") || StringEquals(node.roadControlState, "scout_watchtrail") || StringEquals(node.roadControlState, "outlaw_watchtrail")) { outlawCount += 2; }
        if (RuntimeDegradedMode())
        {
            outlawCount = ClampInt(outlawCount - 1, 2, 6);
            lawCount = ClampInt(lawCount - 1, 1, 6);
        }
        const bool mountedOutlaws = AutoEventWantsMountedOutlaws(node) && !RuntimeDegradedMode() && LogisticsAllowsMounted(node, SpawnedRole::Rival);
        const bool mountedLaw = AutoEventWantsMountedLaw(node) && !RuntimeDegradedMode() && LogisticsAllowsMounted(node, SpawnedRole::Law) && (StringEquals(node.contextTag, "rail_checkpoint") || StringEquals(node.roadControlState, "law_patrol_lane") || StringEquals(LogisticsBattleProfile(node), "fortified_front"));
        outlawCount = ApplyLogisticsCountModifier(node, outlawCount, SpawnedRole::Rival, mountedOutlaws);
        lawCount = ApplyLogisticsCountModifier(node, lawCount, SpawnedRole::Law, mountedLaw);
        SpawnSquad(outlawFaction, outlawCount, SpawnedRole::Rival, false, &node, mountedOutlaws);
        SpawnSquad(lawFaction, lawCount, SpawnedRole::Law, false, &node, mountedLaw);
        RetaskDynamicCombat(true);
        char msg[224]{};
        std::snprintf(msg, sizeof(msg), "Regional shootout started: %s", DescribeEntryConflictBias(node));
        PushToast(msg);
    }

    void StartTownAssaultEvent()
    {
        RuntimeNode& node = CurrentNodeMutable();
        if (!CurrentNodeSupportsTownAssault(node))
        {
            PushToast("Current node does not support a town assault profile");
            return;
        }
        if (gState.townAssault.active && StringEquals(gState.townAssault.nodeId, node.nodeId))
        {
            PushToast("Town assault already active at this node");
            return;
        }

        DespawnBattleActors(false);
        const char* attackerFaction = DetermineTownAssaultFaction(node);
        const char* defenderFaction = DetermineLawFactionForNode(node);
        CopyString(gState.townAssault.nodeId, sizeof(gState.townAssault.nodeId), node.nodeId);
        CopyString(gState.townAssault.attackerFaction, sizeof(gState.townAssault.attackerFaction), attackerFaction);
        CopyString(gState.townAssault.defenderFaction, sizeof(gState.townAssault.defenderFaction), defenderFaction);
        gState.townAssault.active = true;
        gState.townAssault.waveIndex = 1;
        gState.townAssault.maxWaves = StringEquals(node.contextTag, "fort_war") ? 3 : 2;
        if (StringEquals(DirectiveForNode(node), "raid")) ++gState.townAssault.maxWaves;
        if (StringEquals(DirectiveForNode(node), "fortify") && StringEquals(node.contextTag, "fort_war")) ++gState.townAssault.maxWaves;
        gState.townAssault.nextWaveTickMs = GetTickCount64() + LogisticsWaveDelayMs(node);

        CopyString(node.activeAssaultFaction, sizeof(node.activeAssaultFaction), attackerFaction);
        node.contested = true;
        MarkNodeEventTriggered(node, "Town assault");
        node.heat = ClampInt(node.heat + 20, 0, 100);
        node.fear = ClampInt(node.fear + 18, 0, 100);
        node.pressure = ClampInt(node.pressure + 10, 0, 100);
        RefreshLocalState(node);

        int attackerCount = StringEquals(node.contextTag, "fort_war") ? 4 : 3;
        int lawCount = StringEquals(node.contextTag, "law_town") ? 3 : 2;
        if (node.outlawWeight >= 70) ++attackerCount;
        if (node.lawWeight >= 70) ++lawCount;
        if (node.wagonWeight >= 70 && StringEquals(DirectiveForNode(node), "fortify")) ++lawCount;
        if (StringEquals(DirectiveForNode(node), "raid")) ++attackerCount;
        if (StringEquals(DirectiveForNode(node), "crackdown")) ++lawCount;
        if (StringEquals(node.populationProfile, "gang_muster")) ++attackerCount;
        if (StringEquals(node.populationProfile, "marshal_heavy") || StringEquals(node.populationProfile, "garrison_build_up")) ++lawCount;
        if (StringEquals(node.roadControlState, "raider_corridor") || StringEquals(node.roadControlState, "scout_watchtrail") || StringEquals(node.roadControlState, "outlaw_watchtrail")) { attackerCount += 2; ++gState.townAssault.maxWaves; }
        if (StringEquals(node.roadControlState, "marshal_roadblock") || StringEquals(node.roadControlState, "law_patrol_lane")) { lawCount += 2; }
        if (StringEquals(node.roadControlState, "garrison_corridor")) { lawCount += 2; }
        if (StringEquals(node.roadControlState, "smuggler_lane") || StringEquals(node.roadControlState, "cargo_cutthrough") || StringEquals(node.roadControlState, "wagon_route")) { ++attackerCount; ++lawCount; }
        if (RuntimeDegradedMode())
        {
            attackerCount = ClampInt(attackerCount - 1, 2, 7);
            lawCount = ClampInt(lawCount - 1, 1, 6);
            gState.townAssault.maxWaves = ClampInt(gState.townAssault.maxWaves - 1, 1, 4);
        }
        const bool mountedAttackers = !RuntimeDegradedMode() && LogisticsAllowsMounted(node, SpawnedRole::TownAttacker);
        const bool mountedLaw = !RuntimeDegradedMode() && AutoEventWantsMountedLaw(node) && LogisticsAllowsMounted(node, SpawnedRole::Law) && (StringEquals(node.contextTag, "fort_war") || StringEquals(LogisticsBattleProfile(node), "fortified_front"));
        attackerCount = ApplyLogisticsCountModifier(node, attackerCount, SpawnedRole::TownAttacker, mountedAttackers);
        lawCount = ApplyLogisticsCountModifier(node, lawCount, SpawnedRole::Law, mountedLaw);
        SpawnSquad(attackerFaction, attackerCount, SpawnedRole::TownAttacker, false, &node, mountedAttackers);
        SpawnSquad(defenderFaction, lawCount, SpawnedRole::Law, false, &node, mountedLaw);
        RetaskDynamicCombat(true);
        char msg[224]{};
        std::snprintf(msg, sizeof(msg), "Town assault started: %s", DescribeEntryConflictBias(node));
        PushToast(msg);
    }

    void ResolveTownAssault(bool attackersWon)
    {
        RuntimeNode* node = FindNodeById(gState.townAssault.nodeId);
        if (node)
        {
            if (attackersWon)
            {
                CopyString(node->controller, sizeof(node->controller), gState.townAssault.attackerFaction);
                node->pressure = ClampInt(node->pressure + 18, 0, 100);
                node->fear = ClampInt(node->fear + 14, 0, 100);
                node->heat = ClampInt(node->heat + 10, 0, 100);
                node->supply = ClampInt(node->supply - 8, 0, 100);
            }
            else
            {
                CopyString(node->controller, sizeof(node->controller), gState.townAssault.defenderFaction);
                node->pressure = ClampInt(node->pressure - 14, 0, 100);
                node->fear = ClampInt(node->fear - 8, 0, 100);
                node->heat = ClampInt(node->heat + 6, 0, 100);
                node->fortification = ClampInt(node->fortification + 10, 0, 100);
            }
            node->contested = false;
            CopyString(node->activeAssaultFaction, sizeof(node->activeAssaultFaction), "");
            node->nextAutoEventAllowedMs = GetTickCount64() + 50000;
            ApplyOccupationOutcome(*node, attackersWon ? gState.townAssault.attackerFaction : gState.townAssault.defenderFaction, attackersWon, "town_assault");
            RefreshLocalState(*node);
        }
        if (node)
        {
            ApplyRegionalBattleShock(*node, attackersWon ? gState.townAssault.attackerFaction : gState.townAssault.defenderFaction, attackersWon ? gState.townAssault.defenderFaction : gState.townAssault.attackerFaction, attackersWon);
            ScheduleConflictChain(*node, attackersWon ? gState.townAssault.attackerFaction : gState.townAssault.defenderFaction, attackersWon ? gState.townAssault.defenderFaction : gState.townAssault.attackerFaction, attackersWon);
        }
        DespawnBattleActors(false);
        gState.townAssault = TownAssaultState{};
        gState.saveDirty = true;
        PushToast(attackersWon ? "Town assault resolved: the gang overran the node" : "Town assault resolved: the law held the town");
    }

    void ResolveRegionalShootout(bool lawWon)
    {
        RuntimeNode* node = FindNodeById(gState.regionalShootout.nodeId);
        if (node)
        {
            if (lawWon)
            {
                node->heat = ClampInt(node->heat + 8, 0, 100);
                node->pressure = ClampInt(node->pressure - 8, 0, 100);
                node->fear = ClampInt(node->fear - 4, 0, 100);
                node->fortification = ClampInt(node->fortification + 6, 0, 100);
            }
            else
            {
                CopyString(node->controller, sizeof(node->controller), gState.regionalShootout.outlawFaction);
                node->heat = ClampInt(node->heat + 10, 0, 100);
                node->pressure = ClampInt(node->pressure + 12, 0, 100);
                node->fear = ClampInt(node->fear + 8, 0, 100);
                node->supply = ClampInt(node->supply - 6, 0, 100);
            }
            node->contested = false;
            CopyString(node->activeAssaultFaction, sizeof(node->activeAssaultFaction), "");
            node->nextAutoEventAllowedMs = GetTickCount64() + 45000;
            ApplyOccupationOutcome(*node, lawWon ? gState.regionalShootout.lawFaction : gState.regionalShootout.outlawFaction, !lawWon, "regional_shootout");
            RefreshLocalState(*node);
        }
        if (node)
        {
            ApplyRegionalBattleShock(*node, lawWon ? gState.regionalShootout.lawFaction : gState.regionalShootout.outlawFaction, lawWon ? gState.regionalShootout.outlawFaction : gState.regionalShootout.lawFaction, !lawWon);
            ScheduleConflictChain(*node, lawWon ? gState.regionalShootout.lawFaction : gState.regionalShootout.outlawFaction, lawWon ? gState.regionalShootout.outlawFaction : gState.regionalShootout.lawFaction, !lawWon);
        }
        DespawnBattleActors(false);
        gState.regionalShootout = RegionalShootoutState{};
        gState.saveDirty = true;
        PushToast(lawWon ? "Regional shootout resolved: lawmen broke the gang pressure" : "Regional shootout resolved: the gang drove off the law response");
    }

    void ApplyRegionalBattleShock(RuntimeNode& centerNode, const char* winningFaction, const char* losingFaction, bool attackersWon)
    {
        std::stringstream ss(centerNode.neighborsCsv);
        std::string item;
        while (std::getline(ss, item, ','))
        {
            RuntimeNode* node = FindNodeById(item.c_str());
            if (!node)
            {
                continue;
            }
            if (StringEquals(node->controller, winningFaction) || (IsLawFactionName(winningFaction) && IsLawFactionName(node->controller)))
            {
                node->pressure = ClampInt(node->pressure + (attackersWon ? 8 : 4), 0, 100);
                node->supply = ClampInt(node->supply + 4, 0, 100);
                node->fear = ClampInt(node->fear + (attackersWon ? 3 : -2), 0, 100);
            }
            if (StringEquals(node->controller, losingFaction) || (IsLawFactionName(losingFaction) && IsLawFactionName(node->controller)))
            {
                node->pressure = ClampInt(node->pressure - 6, 0, 100);
                node->supply = ClampInt(node->supply - 6, 0, 100);
                node->heat = ClampInt(node->heat + 6, 0, 100);
            }
            if (StringEquals(node->controller, "PlayerNeutral") || StringEquals(node->controller, "PlayerFriendly"))
            {
                node->fear = ClampInt(node->fear + 5, 0, 100);
                node->heat = ClampInt(node->heat + 4, 0, 100);
            }
            RefreshLocalState(*node);
        }
    }

    void TickRegionalShootout()
    {
        if (!gState.regionalShootout.active)
        {
            return;
        }
        RecountSpawnedActors();
        RetaskDynamicCombat();
        RuntimeNode* node = FindNodeById(gState.regionalShootout.nodeId);
        const uint64_t now = GetTickCount64();
        if (node)
        {
            if (gState.activeEnemyCount <= 1 && !gState.regionalShootout.outlawNeighborReinforced)
            {
                gState.regionalShootout.outlawNeighborReinforced = DispatchNeighborReinforcement(*node, gState.regionalShootout.outlawFaction, SpawnedRole::Rival, false, 2, false, true, "Outlaw reinforcements");
            }
            if (gState.activeLawCount <= 1 && !gState.regionalShootout.lawNeighborReinforced)
            {
                gState.regionalShootout.lawNeighborReinforced = DispatchNeighborReinforcement(*node, gState.regionalShootout.lawFaction, SpawnedRole::Law, false, 2, true, false, "Law reinforcements");
            }
        }
        if ((gState.activeEnemyCount <= 0 && gState.activeLawCount > 0) || (now >= gState.regionalShootout.resolveDeadlineMs && gState.activeLawCount >= gState.activeEnemyCount))
        {
            ResolveRegionalShootout(true);
        }
        else if ((gState.activeLawCount <= 0 && gState.activeEnemyCount > 0) || (now >= gState.regionalShootout.resolveDeadlineMs && gState.activeEnemyCount > gState.activeLawCount))
        {
            ResolveRegionalShootout(false);
        }
    }

    void TickTownAssault()
    {
        if (!gState.townAssault.active)
        {
            return;
        }
        RuntimeNode* node = FindNodeById(gState.townAssault.nodeId);
        if (!node)
        {
            gState.townAssault = TownAssaultState{};
            return;
        }

        RecountSpawnedActors();
        RetaskDynamicCombat();
        const uint64_t now = GetTickCount64();
        if (gState.activeTownAttackerCount <= 1 && !gState.townAssault.attackerNeighborReinforced)
        {
            gState.townAssault.attackerNeighborReinforced = DispatchNeighborReinforcement(*node, gState.townAssault.attackerFaction, SpawnedRole::TownAttacker, true, 2, false, true, "Mounted outlaw reinforcements");
        }
        if (gState.activeLawCount <= 1 && !gState.townAssault.defenderNeighborReinforced)
        {
            gState.townAssault.defenderNeighborReinforced = DispatchNeighborReinforcement(*node, gState.townAssault.defenderFaction, SpawnedRole::Law, false, 2, true, false, "Regional law reinforcements");
        }
        if (now >= gState.townAssault.nextWaveTickMs && gState.townAssault.waveIndex < gState.townAssault.maxWaves)
        {
            int extraAttackers = 2 + gState.townAssault.waveIndex;
            int extraLaw = gState.activeLawCount <= 1 ? 2 : 1;
            if (StringEquals(DirectiveForNode(*node), "raid")) ++extraAttackers;
            if (StringEquals(DirectiveForNode(*node), "crackdown") || StringEquals(DirectiveForNode(*node), "fortify")) ++extraLaw;
            const bool waveMountedAttackers = LogisticsAllowsMounted(*node, SpawnedRole::TownAttacker);
            const bool waveMountedLaw = LogisticsAllowsMounted(*node, SpawnedRole::Law) && StringEquals(LogisticsBattleProfile(*node), "fortified_front");
            extraAttackers = ApplyLogisticsCountModifier(*node, extraAttackers, SpawnedRole::TownAttacker, waveMountedAttackers);
            extraLaw = ApplyLogisticsCountModifier(*node, extraLaw, SpawnedRole::Law, waveMountedLaw);
            SpawnSquad(gState.townAssault.attackerFaction, extraAttackers, SpawnedRole::TownAttacker, false, node, waveMountedAttackers);
            SpawnSquad(gState.townAssault.defenderFaction, extraLaw, SpawnedRole::Law, false, node, waveMountedLaw);
            ++gState.townAssault.waveIndex;
            gState.townAssault.nextWaveTickMs = now + LogisticsWaveDelayMs(*node);
            PushToast("Another mounted gang wave hit the town and drew more lawmen into the fight");
        }

        if (gState.townAssault.waveIndex >= gState.townAssault.maxWaves)
        {
            if (gState.activeTownAttackerCount <= 0 && gState.activeLawCount > 0)
            {
                ResolveTownAssault(false);
            }
            else if (gState.activeLawCount <= 0 && gState.activeTownAttackerCount > 0)
            {
                ResolveTownAssault(true);
            }
        }
    }

    void CyclePosseOrder()
    {
        const int next = (static_cast<int>(gState.posseOrder) + 1) % 3;
        gState.posseOrder = static_cast<PosseOrder>(next);
        ApplyCurrentPosseOrder();
        gState.saveDirty = true;
        char msg[160]{};
        std::snprintf(msg, sizeof(msg), "Posse order changed to %s", PosseOrderName(gState.posseOrder));
        PushToast(msg);
    }

    void BootSeeds()
    {
        gState.nodes.clear();
        gState.nodes.reserve(std::size(kSeedNodes));
        for (const SeedNode& seed : kSeedNodes)
        {
            RuntimeNode node{};
            CopyString(node.nodeId, sizeof(node.nodeId), seed.nodeId);
            CopyString(node.displayName, sizeof(node.displayName), seed.displayName);
            CopyString(node.regionName, sizeof(node.regionName), seed.regionName);
            node.anchorX = seed.anchorX;
            node.anchorY = seed.anchorY;
            node.anchorZ = seed.anchorZ;
            node.anchorHeading = seed.anchorHeading;
            node.hasAnchor = seed.hasAnchor;
            CopyString(node.controller, sizeof(node.controller), seed.defaultController);
            CopyString(node.activeAssaultFaction, sizeof(node.activeAssaultFaction), "");
            CopyString(node.neighborsCsv, sizeof(node.neighborsCsv), seed.neighborsCsv);
            CopyString(node.strategicTagsCsv, sizeof(node.strategicTagsCsv), seed.strategicTagsCsv);
            node.pressure = seed.basePressure;
            node.heat = seed.baseHeat;
            node.supply = ContainsCsvToken(seed.strategicTagsCsv, "supply_node") || ContainsCsvToken(seed.strategicTagsCsv, "transport_post") ? 70 : 50;
            node.fear = ContainsCsvToken(seed.strategicTagsCsv, "civilian_pressure") ? 35 : 18;
            node.fortification = ContainsCsvToken(seed.strategicTagsCsv, "outlaw_hideout") || ContainsCsvToken(seed.strategicTagsCsv, "fortified_outpost") ? 20 : 5;
            node.contested = false;
            if (const TuneNodeProfile* profile = FindTuneProfile(seed.nodeId))
            {
                CopyString(node.contextTag, sizeof(node.contextTag), profile->contextTag);
                CopyString(node.ambientSet, sizeof(node.ambientSet), profile->ambientSet);
                CopyString(node.civilianArchetype, sizeof(node.civilianArchetype), profile->civilianArchetype);
                CopyString(node.outlawArchetype, sizeof(node.outlawArchetype), profile->outlawArchetype);
                CopyString(node.lawArchetype, sizeof(node.lawArchetype), profile->lawArchetype);
                CopyString(node.missionFlavor, sizeof(node.missionFlavor), profile->missionFlavor);
                CopyString(node.travelFlavor, sizeof(node.travelFlavor), profile->travelFlavor);
                CopyString(node.abandonedToken, sizeof(node.abandonedToken), profile->abandonedToken);
                CopyString(node.returnToken, sizeof(node.returnToken), profile->returnToken);
            }
            AssignNodeDailyProfile(node);
            RefreshLocalState(node);
            gState.nodes.push_back(node);
        }
    }

    const CodeRedFactionSeedV26::SeedFaction* FindSeedFaction(const char* engineFaction)
    {
        for (const CodeRedFactionSeedV26::SeedFaction& seed : kSeedFactions)
        {
            if (StringEquals(seed.engineFaction, engineFaction))
            {
                return &seed;
            }
        }
        return nullptr;
    }

    RuntimeNode* FindNodeById(const char* nodeId)
    {
        for (RuntimeNode& node : gState.nodes)
        {
            if (StringEquals(node.nodeId, nodeId))
            {
                return &node;
            }
        }
        return nullptr;
    }

    const CodeRedTuneProfilesV26::TuneNodeProfile* FindTuneProfile(const char* nodeId)
    {
        for (const CodeRedTuneProfilesV26::TuneNodeProfile& profile : kTuneNodeProfiles)
        {
            if (StringEquals(profile.nodeId, nodeId))
            {
                return &profile;
            }
        }
        return nullptr;
    }

    const char* DetermineRoadControlState(const RuntimeNode& node)
    {
        if (OccupationActive(node))
        {
            if (IsLawFactionName(node.occupationFaction))
            {
                if (StringEquals(node.contextTag, "law_town") || ContainsCsvToken(node.strategicTagsCsv, "transport_post"))
                {
                    return "marshal_roadblock";
                }
                if (StringEquals(node.contextTag, "fort_war") || ContainsCsvToken(node.strategicTagsCsv, "war_anchor"))
                {
                    return "garrison_corridor";
                }
                return "law_patrol_lane";
            }
            if (StringEquals(node.contextTag, "black_market"))
            {
                return "smuggler_lane";
            }
            if (StringEquals(node.contextTag, "camp_hideout") || StringEquals(node.contextTag, "rustler_hideout") || ContainsCsvToken(node.strategicTagsCsv, "raid_origin"))
            {
                return "raider_corridor";
            }
            return "outlaw_watchtrail";
        }

        const char* directive = DirectiveForNode(node);
        if (directive[0] && StringEquals(directive, "crackdown"))
        {
            if (StringEquals(node.contextTag, "law_town") || ContainsCsvToken(node.strategicTagsCsv, "transport_post"))
            {
                return "marshal_roadblock";
            }
            return "law_patrol_lane";
        }
        if (directive[0] && StringEquals(directive, "smuggling"))
        {
            if (node.wagonWeight >= 60 || StringEquals(node.contextTag, "black_market"))
            {
                return "smuggler_lane";
            }
            return "cargo_cutthrough";
        }
        if (directive[0] && StringEquals(directive, "raid"))
        {
            if (StringEquals(node.contextTag, "camp_hideout") || StringEquals(node.contextTag, "rustler_hideout") || ContainsCsvToken(node.strategicTagsCsv, "raid_origin"))
            {
                return "raider_corridor";
            }
            return "scout_watchtrail";
        }
        if (directive[0] && StringEquals(directive, "fortify"))
        {
            return (StringEquals(node.contextTag, "fort_war") || ContainsCsvToken(node.strategicTagsCsv, "war_anchor")) ? "garrison_corridor" : "supply_lane";
        }
        if (directive[0] && StringEquals(directive, "scavenge"))
        {
            return (StringEquals(node.contextTag, "ghost_town") || StringEquals(node.contextTag, "mine_hideout")) ? "salvage_track" : "dust_track";
        }
        if (node.wagonWeight >= 65)
        {
            return "wagon_route";
        }
        if (node.lawWeight >= 65 && IsLawFactionName(node.controller))
        {
            return "law_patrol_lane";
        }
        if (node.outlawWeight >= 65 && !IsLawFactionName(node.controller))
        {
            return "outlaw_watchtrail";
        }
        return "frontier_open";
    }

    int ComputeRoutePressure(const RuntimeNode& node)
    {
        int value = (node.pressure + node.heat + node.wagonWeight) / 3;
        if (OccupationActive(node)) value += 8;
        if (node.contested) value += 10;
        const char* road = DetermineRoadControlState(node);
        if (StringEquals(road, "marshal_roadblock") || StringEquals(road, "raider_corridor")) value += 10;
        else if (StringEquals(road, "smuggler_lane") || StringEquals(road, "garrison_corridor")) value += 6;
        return ClampInt(value, 0, 100);
    }

    int ComputeEscortNeed(const RuntimeNode& node)
    {
        int value = (node.wagonWeight + node.fear + node.supply) / 3;
        const char* road = DetermineRoadControlState(node);
        if (StringEquals(road, "smuggler_lane") || StringEquals(road, "wagon_route") || StringEquals(road, "supply_lane") || StringEquals(road, "garrison_corridor"))
        {
            value += 12;
        }
        if (ContainsCsvToken(node.strategicTagsCsv, "transport_post"))
        {
            value += 8;
        }
        return ClampInt(value, 0, 100);
    }

    void RefreshRoadControl(RuntimeNode& node)
    {
        CopyString(node.roadControlState, sizeof(node.roadControlState), DetermineRoadControlState(node));
        node.routePressure = ComputeRoutePressure(node);
        node.escortNeed = ComputeEscortNeed(node);
    }

    void PropagateCorridorPressure()
    {
        for (RuntimeNode& source : gState.nodes)
        {
            if (!source.neighborsCsv[0])
            {
                continue;
            }
            const int routePush = source.routePressure / 12;
            const int escortPush = source.escortNeed / 18;
            if (routePush <= 0 && escortPush <= 0)
            {
                continue;
            }

            std::stringstream ss(source.neighborsCsv);
            std::string item;
            while (std::getline(ss, item, ','))
            {
                RuntimeNode* neighbor = FindNodeById(item.c_str());
                if (!neighbor)
                {
                    continue;
                }
                int pressureDelta = 0;
                int heatDelta = 0;
                int supplyDelta = 0;
                int fearDelta = 0;

                if (StringEquals(source.roadControlState, "marshal_roadblock") || StringEquals(source.roadControlState, "law_patrol_lane") || StringEquals(source.roadControlState, "garrison_corridor"))
                {
                    pressureDelta += routePush;
                    fearDelta += 1;
                    if (!IsLawFactionName(neighbor->controller))
                    {
                        heatDelta += 1;
                    }
                }
                else if (StringEquals(source.roadControlState, "raider_corridor") || StringEquals(source.roadControlState, "outlaw_watchtrail") || StringEquals(source.roadControlState, "scout_watchtrail"))
                {
                    heatDelta += routePush;
                    pressureDelta += routePush / 2;
                    fearDelta += 1;
                }
                else if (StringEquals(source.roadControlState, "smuggler_lane") || StringEquals(source.roadControlState, "cargo_cutthrough") || StringEquals(source.roadControlState, "wagon_route") || StringEquals(source.roadControlState, "supply_lane"))
                {
                    supplyDelta += escortPush;
                    pressureDelta += escortPush / 2;
                }
                else if (StringEquals(source.roadControlState, "salvage_track"))
                {
                    fearDelta += 1;
                    heatDelta += routePush / 2;
                }

                if (pressureDelta || heatDelta || supplyDelta || fearDelta)
                {
                    neighbor->pressure = ClampInt(neighbor->pressure + pressureDelta, 0, 100);
                    neighbor->heat = ClampInt(neighbor->heat + heatDelta, 0, 100);
                    neighbor->supply = ClampInt(neighbor->supply + supplyDelta, 0, 100);
                    neighbor->fear = ClampInt(neighbor->fear + fearDelta, 0, 100);
                    RefreshLocalState(*neighbor);
                }
            }
        }
    }

    void RefreshLocalState(RuntimeNode& node)
    {
        RefreshNodeAtmosphere(node);
        const char* directive = DirectiveForNode(node);
        if (node.contested)
        {
            if (directive[0] && StringEquals(directive, "crackdown") && StringEquals(node.contextTag, "law_town"))
            {
                CopyString(node.localState, sizeof(node.localState), "law_lockdown");
                return;
            }
            if (directive[0] && StringEquals(directive, "raid"))
            {
                CopyString(node.localState, sizeof(node.localState), "raid_frontier_hot");
                return;
            }
            if (node.contextTag[0])
            {
                std::snprintf(node.localState, sizeof(node.localState), "%s contested", node.contextTag);
            }
            else
            {
                CopyString(node.localState, sizeof(node.localState), "contested frontier node");
            }
            return;
        }
        if (OccupationActive(node))
        {
            CopyString(node.localState, sizeof(node.localState), node.occupationState);
            return;
        }
        if (node.abandonedToken[0] && node.supply <= 25)
        {
            CopyString(node.localState, sizeof(node.localState), node.abandonedToken);
            return;
        }
        if (node.returnToken[0] && node.supply >= 55 && node.heat <= 45)
        {
            CopyString(node.localState, sizeof(node.localState), node.returnToken);
            return;
        }
        if (directive[0] && StringEquals(directive, "smuggling") && (StringEquals(node.contextTag, "black_market") || ContainsCsvToken(node.strategicTagsCsv, "transport_post")))
        {
            CopyString(node.localState, sizeof(node.localState), node.wagonWeight >= 70 ? "wagon_nap_obj" : "cargo_watch");
            return;
        }
        if (directive[0] && StringEquals(directive, "fortify") && (StringEquals(node.contextTag, "fort_war") || ContainsCsvToken(node.strategicTagsCsv, "war_anchor")))
        {
            CopyString(node.localState, sizeof(node.localState), node.lawWeight >= 60 ? "fortified_muster" : "supply_column");
            return;
        }
        if (directive[0] && StringEquals(directive, "scavenge") && StringEquals(node.contextTag, "ghost_town"))
        {
            CopyString(node.localState, sizeof(node.localState), "GhostTown_Help1");
            return;
        }
        if (StringEquals(node.contextTag, "law_town"))
        {
            CopyString(node.localState, sizeof(node.localState), node.heat >= 55 ? "law_bounty_amount" : "law_local_watch");
            return;
        }
        if (StringEquals(node.contextTag, "ghost_town"))
        {
            CopyString(node.localState, sizeof(node.localState), "GhostTown_Help1");
            return;
        }
        if (StringEquals(node.contextTag, "mine_hideout"))
        {
            CopyString(node.localState, sizeof(node.localState), node.supply <= 35 ? "item_treasure_map" : "mine_watch");
            return;
        }
        if (StringEquals(node.contextTag, "camp_hideout") || StringEquals(node.contextTag, "rustler_hideout"))
        {
            CopyString(node.localState, sizeof(node.localState), node.heat >= 50 ? "sit_camp_q" : "sit_camp");
            return;
        }
        if (StringEquals(node.contextTag, "black_market"))
        {
            CopyString(node.localState, sizeof(node.localState), node.heat >= 50 ? "wagon_nap_help" : "black_market_open");
            return;
        }
        if (node.travelFlavor[0] && node.wagonWeight >= 45)
        {
            CopyString(node.localState, sizeof(node.localState), node.travelFlavor);
            return;
        }
        CopyString(node.localState, sizeof(node.localState), node.trafficState[0] ? node.trafficState : (node.contextTag[0] ? node.contextTag : "frontier_idle"));
    }

    const RuntimeNode* FindNeighborNode(const RuntimeNode& source, int offset)
    {
        std::stringstream ss(source.neighborsCsv);
        std::string item;
        int index = 0;
        while (std::getline(ss, item, ','))
        {
            if (index == offset)
            {
                return FindNodeById(item.c_str());
            }
            ++index;
        }
        return nullptr;
    }

    int FactionAggression(const char* engineFaction)
    {
        const CodeRedFactionSeedV26::SeedFaction* seed = FindSeedFaction(engineFaction);
        if (!seed)
        {
            return 10;
        }

        int score = 8 + seed->hostileRelationCount / 2;
        if (seed->lawEnforcement)
        {
            score -= 2;
        }
        if (StringEquals(engineFaction, "MexicanBandito") || StringEquals(engineFaction, "CattleRustler") || StringEquals(engineFaction, "IndianRaider"))
        {
            score += 4;
        }
        return ClampInt(score, 6, 20);
    }

    int FactionDiscipline(const char* engineFaction)
    {
        const CodeRedFactionSeedV26::SeedFaction* seed = FindSeedFaction(engineFaction);
        if (!seed)
        {
            return 10;
        }
        int score = 7 + seed->alliedRelationCount / 2;
        if (seed->lawEnforcement)
        {
            score += 6;
        }
        return ClampInt(score, 8, 20);
    }

    void MakeMission(const char* missionId, const char* displayName, const char* description, const RuntimeNode& node, const char* sourceFaction)
    {
        CopyString(gState.activeMission.missionId, sizeof(gState.activeMission.missionId), missionId);
        CopyString(gState.activeMission.displayName, sizeof(gState.activeMission.displayName), displayName);
        CopyString(gState.activeMission.description, sizeof(gState.activeMission.description), description);
        CopyString(gState.activeMission.sourceNodeId, sizeof(gState.activeMission.sourceNodeId), node.nodeId);
        CopyString(gState.activeMission.sourceFaction, sizeof(gState.activeMission.sourceFaction), sourceFaction);
        gState.activeMission.valid = true;
    }

    void GenerateMissionFromCurrentState()
    {
        const RuntimeNode& node = CurrentNode();
        const CodeRedFactionSeedV26::SeedFaction& faction = CurrentFaction();
        const char* directive = DirectiveForNode(node);
        const char* campaignState = CampaignStateName(node);

        if (StringEquals(campaignState, "knife_edge"))
        {
            MakeMission(faction.lawEnforcement ? "fortify_node" : "retaliation_strike", faction.lawEnforcement ? "Hold the Knife Edge" : "Break the Knife Edge", faction.lawEnforcement ? "This region is hanging by a thread. Hold the line, steady the roads, and keep the gangs from flipping the balance today." : "This region is ready to tip. Push the pressure, hit the weak point, and break the frontier balance in your favor.", node, faction.engineFaction);
        }
        else if (StringEquals(campaignState, "marshal_grip") && !faction.lawEnforcement)
        {
            MakeMission("raid_road_convoy", "Smash the Clampdown", "The marshals are taking a hard grip on this region. Break the clampdown, hit the road net, and keep the frontier from going quiet.", node, faction.engineFaction);
        }
        else if (StringEquals(campaignState, "outlaw_domain") && faction.lawEnforcement)
        {
            MakeMission("law_sweep", "Retake the Frontier", "This region is slipping into outlaw rule. Sweep the hot nodes, break their holds, and pull the territory back under law pressure.", node, faction.engineFaction);
        }
        else if (StringEquals(campaignState, "shattered"))
        {
            MakeMission(faction.lawEnforcement ? "frontier_patrol" : "tax_settlement", faction.lawEnforcement ? "Stabilize the Region" : "Exploit the Collapse", faction.lawEnforcement ? "The civilians are breaking under pressure. Lock the worst lanes down and stabilize the region before panic turns into open war." : "The region is cracking. Exploit the fear, seize what you can, and turn collapse into control.", node, faction.engineFaction);
        }
        else if (node.contested)
        {
            if (StringEquals(node.controller, faction.engineFaction))
            {
                MakeMission("defend_hideout", "Defend Hideout", "Your men are under pressure. Break the assault and hold the node.", node, faction.engineFaction);
            }
            else
            {
                MakeMission("retaliation_strike", "Retaliation Strike", "A contested node is wavering. Push hard and take the ground before reinforcements arrive.", node, faction.engineFaction);
            }
        }
        else if (StringEquals(LogisticsStateName(node), "starved"))
        {
            MakeMission(faction.lawEnforcement ? "escort_supply_wagon" : "raid_road_convoy", faction.lawEnforcement ? "Relief Convoy" : "Seize Relief Convoy", faction.lawEnforcement ? "This region is running lean. Ride the relief convoy through the dangerous lanes before the gangs strip it bare." : "The region is starving and the relief wagons are exposed. Hit the lane, seize the cargo, and turn hunger into pressure.", node, faction.engineFaction);
        }
        else if (StringEquals(LogisticsStateName(node), "convoys_hot"))
        {
            MakeMission(faction.lawEnforcement ? "escort_supply_wagon" : "raid_road_convoy", faction.lawEnforcement ? "Cover Hot Convoys" : "Hit the Hot Lane", faction.lawEnforcement ? "Traffic is thick and every wagon matters. Cover the convoy corridor and keep the smugglers from flipping the road." : "The lane is burning with cargo and escorts. Pick the right stretch of road, hit the wagons, and vanish with the goods.", node, faction.engineFaction);
        }
        else if (StringEquals(LogisticsStateName(node), "fortifying"))
        {
            MakeMission(faction.lawEnforcement ? "fortify_node" : "retaliation_strike", faction.lawEnforcement ? "Hold the Fortified Line" : "Break the Fortified Line", faction.lawEnforcement ? "This region is locking down with supply and men. Hold the line and make the next assault pay for every yard." : "The enemy is hardening this region with supplies and garrisons. Break the fortified line before the frontier closes on you.", node, faction.engineFaction);
        }
        else if (node.roadControlState[0] && StringEquals(node.roadControlState, "marshal_roadblock"))
        {
            MakeMission(faction.lawEnforcement ? "frontier_patrol" : "raid_road_convoy", faction.lawEnforcement ? "Hold the Roadblock" : "Break the Roadblock", faction.lawEnforcement ? "This corridor is under marshal control. Hold the stop, search riders, and keep gang traffic off the line." : "The marshals locked the road down. Break the checkpoint, scatter the law, and reopen the frontier lane.", node, faction.engineFaction);
        }
        else if (node.roadControlState[0] && StringEquals(node.roadControlState, "smuggler_lane"))
        {
            MakeMission(faction.lawEnforcement ? "escort_supply_wagon" : "escort_supply_wagon", faction.lawEnforcement ? "Seize the Smuggling Lane" : "Run the Smuggling Lane", faction.lawEnforcement ? "The black-market corridor is active. Catch the cargo on the road before it reaches the next post." : "The lane is open and the wagons are moving. Ride escort, keep the cargo alive, and hold the route until nightfall.", node, faction.engineFaction);
        }
        else if (node.roadControlState[0] && StringEquals(node.roadControlState, "raider_corridor"))
        {
            MakeMission("retaliation_strike", faction.lawEnforcement ? "Break the Raider Corridor" : "Ride the Raider Corridor", faction.lawEnforcement ? "Mounted raiders are owning this route. Cut the corridor apart before they can hit the next town." : "This trail is hot with riders. Muster hard, run the corridor, and hit the next target before the law can react.", node, faction.engineFaction);
        }
        else if (directive[0] && StringEquals(directive, "crackdown"))
        {
            if (faction.lawEnforcement)
            {
                MakeMission("law_sweep", "Regional Crackdown", "Marshal pressure is rising across this region. Sweep the hot road and break the outlaw build-up before sunset.", node, faction.engineFaction);
            }
            else
            {
                MakeMission("raid_road_convoy", "Break the Crackdown", "Law posts are tightening the roads. Hit the patrol line and break the region-wide crackdown before it closes.", node, faction.engineFaction);
            }
        }
        else if (directive[0] && StringEquals(directive, "smuggling"))
        {
            if (faction.lawEnforcement)
            {
                MakeMission("escort_supply_wagon", "Intercept Smuggling Run", "A smuggling window opened on the transport line. Lock the crossing down and seize the wagons before they vanish.", node, faction.engineFaction);
            }
            else
            {
                MakeMission("escort_supply_wagon", "Smuggling Run", "The region is moving cargo under cover. Ride the wagon line, protect the crew, and keep the black market fed.", node, faction.engineFaction);
            }
        }
        else if (directive[0] && StringEquals(directive, "raid"))
        {
            MakeMission("retaliation_strike", "Raid Muster", "This region is rallying raiders. Hit first, burn their staging point, and keep the frontier answering to your colors.", node, faction.engineFaction);
        }
        else if (directive[0] && StringEquals(directive, "fortify"))
        {
            MakeMission("fortify_node", "Fortify March", "The war anchor is drawing men and supplies. Secure the strongpoint before the next same-day strike lands.", node, faction.engineFaction);
        }
        else if (directive[0] && StringEquals(directive, "scavenge"))
        {
            MakeMission("frontier_patrol", "Scavenger Rush", "Word is spreading through the dust. Sweep the salvage zone, secure the cache, and leave with the region afraid to return.", node, faction.engineFaction);
        }
        else if (StringEquals(node.missionFlavor, "law_bounty"))
        {
            MakeMission("law_sweep", "Marshal Crackdown", "Bounty pressure is rising in town. Hit the law response before it hardens into a full posse sweep.", node, faction.engineFaction);
        }
        else if (StringEquals(node.missionFlavor, "wagon_convoy") || StringEquals(node.missionFlavor, "escort_route") || StringEquals(node.missionFlavor, "border_escort"))
        {
            MakeMission("escort_supply_wagon", "Escort Supply Wagon", "The transport line is open. Move men and cargo between nearby posts before rivals intercept the run.", node, faction.engineFaction);
        }
        else if (StringEquals(node.missionFlavor, "wagon_theft") || StringEquals(node.missionFlavor, "road_robbery"))
        {
            MakeMission("raid_road_convoy", "Wagon Theft", "This route is ripe for a grab. Hit the convoy fast and vanish before deputies lock the road.", node, faction.engineFaction);
        }
        else if (StringEquals(node.missionFlavor, "camp_assault") || StringEquals(node.missionFlavor, "camp_raiders"))
        {
            MakeMission("defend_hideout", "Camp Assault", "Campfires and sentries are live here. Either hold the hideout or break the rival camp before dawn.", node, faction.engineFaction);
        }
        else if (StringEquals(node.missionFlavor, "treasure_map"))
        {
            MakeMission("rescue_lieutenant", "Treasure Cache Sweep", "The mine country is unstable. Secure the map trail, clear the crazy miners, and walk the prize back alive.", node, faction.engineFaction);
        }
        else if (StringEquals(node.missionFlavor, "ghost_town"))
        {
            MakeMission("frontier_patrol", "Ghost Town Sweep", "The ghost town is drawing scavengers and drifters. Sweep it, collect rumors, and leave with the streets answering to you.", node, faction.engineFaction);
        }
        else if (StringEquals(node.missionFlavor, "bandito_assault") || StringEquals(node.missionFlavor, "bandito_patrol"))
        {
            MakeMission("retaliation_strike", "Bandito Assault", "The border outpost is active. Ride in hard, break the defenders, and flip the flag before the army reacts.", node, faction.engineFaction);
        }
        else if (StringEquals(node.controller, faction.engineFaction))
        {
            if (node.supply < 45)
            {
                MakeMission("fortify_node", "Fortify Node", "Supplies are thinning. Move wagons and guards into the node to stabilize control.", node, faction.engineFaction);
            }
            else
            {
                MakeMission("escort_prisoner", "Escort Prisoner", "Move a captured rival through controlled territory before a rescue attempt lands.", node, faction.engineFaction);
            }
        }
        else if (FindSeedFaction(node.controller) && FindSeedFaction(node.controller)->lawEnforcement)
        {
            MakeMission("raid_road_convoy", "Raid Road Convoy", "Law pressure is hardening. Hit the route before the sweep locks the region down.", node, faction.engineFaction);
        }
        else if (ContainsCsvToken(node.strategicTagsCsv, "civilian_pressure"))
        {
            MakeMission("tax_settlement", "Tax Settlement", "Lean on the civilians and convert fear into supplies and rumor control.", node, faction.engineFaction);
        }
        else
        {
            MakeMission("rescue_lieutenant", "Rescue Lieutenant", "A trusted officer is missing near this node. Recover them before the trail goes cold.", node, faction.engineFaction);
        }

        gState.missionAccepted = false;
        gState.missionProgress = 0;
        PushToast("Generated a directive-weighted faction-war mission offer");
    }

    void BuildRumorForNode(const RuntimeNode& node, char* outText, std::size_t outSize)
    {
        const CodeRedFactionSeedV26::SeedFaction* owner = FindSeedFaction(node.controller);
        const char* ownerName = owner ? owner->brandName : node.controller;
        const char* campaignState = CampaignStateName(node);

        if (node.contested)
        {
            std::snprintf(outText, outSize, "Rumor: %s is hot. %s are fighting over %s while %s hangs in the air.", node.displayName, ownerName, node.contextTag[0] ? node.contextTag : "the ground", node.localState[0] ? node.localState : "camp smoke");
            return;
        }
        if (StringEquals(node.contextTag, "law_town"))
        {
            std::snprintf(outText, outSize, "Rumor: %s is running under %s. Locals talk about %s and watch the road.", node.displayName, ownerName, node.localState[0] ? node.localState : "law pressure");
            return;
        }
        if (StringEquals(node.contextTag, "mine_hideout"))
        {
            std::snprintf(outText, outSize, "Rumor: %s is restless. Men whisper about %s and the maps changing hands.", node.displayName, node.localState[0] ? node.localState : "treasure signs");
            return;
        }
        if (StringEquals(node.contextTag, "ghost_town"))
        {
            std::snprintf(outText, outSize, "Rumor: %s feels dead until nightfall. Scavengers keep circling back for %s.", node.displayName, node.localState[0] ? node.localState : "ghost town scraps");
            return;
        }
        if (ContainsCsvToken(node.strategicTagsCsv, "transport_post"))
        {
            std::snprintf(outText, outSize, "Rumor: %s still answers to %s. Wagons keep moving and the line smells like %s.", node.displayName, ownerName, node.travelFlavor[0] ? node.travelFlavor : "escort trouble");
            return;
        }
        std::snprintf(outText, outSize, "Rumor: %s still answers to %s. The region reads as %s and the camp signs point to %s.", node.displayName, ownerName, campaignState, node.localState[0] ? node.localState : "frontier idling");
    }

    void TriggerRumorTick()
    {
        if (gState.nodes.empty())
        {
            return;
        }
        const RuntimeNode& node = gState.nodes[static_cast<std::size_t>(gState.rumorIndex % static_cast<int>(gState.nodes.size()))];
        char rumor[192]{};
        BuildRumorForNode(node, rumor, sizeof(rumor));
        if (kEnableHudToasts)
        {
            HUD::PRINT_SMALL_B(rumor, 2.0f, true, 0, 0, 0, 0);
        }
        gState.rumorIndex = (gState.rumorIndex + 1) % static_cast<int>(gState.nodes.size());
        gState.nextRumorTickMs = GetTickCount64() + 10000;
    }

    void SaveStateToDisk()
    {
        std::ofstream out(kSavePath, std::ios::trunc);
        if (!out)
        {
            PushToast("Save failed: could not write faction-war save file");
            return;
        }

        out << "VERSION=26\n";
        out << "FACTION_INDEX=" << gState.factionIndex << "\n";
        out << "RANK_INDEX=" << gState.rankIndex << "\n";
        out << "NODE_INDEX=" << gState.nodeIndex << "\n";
        out << "SIMULATION=" << (gState.simulationEnabled ? 1 : 0) << "\n";
        out << "PLAYER_LEADING=" << (gState.playerLeading ? 1 : 0) << "\n";
        out << "POSSE_STRENGTH=" << gState.posseStrength << "\n";
        for (const RuntimeNode& node : gState.nodes)
        {
            out << "NODE="
                << node.nodeId << '|'
                << node.controller << '|'
                << node.activeAssaultFaction << '|'
                << node.pressure << '|'
                << node.heat << '|'
                << node.supply << '|'
                << node.fear << '|'
                << node.fortification << '|'
                << (node.contested ? 1 : 0) << '|'
                << node.lastTriggeredDay << '|'
                << node.dailyTriggerCount << '|'
                << node.activeStartHour << '|'
                << node.activeEndHour << '|'
                << node.occupationState << '|'
                << node.occupationFaction << '|'
                << node.occupationUntilDay << '|'
                << node.roadControlState << '|'
                << node.routePressure << '|'
                << node.escortNeed
                << '\n';
        }
        for (const PendingConflictChain& chain : gState.pendingChains)
        {
            if (!chain.active)
            {
                continue;
            }
            out << "CHAIN="
                << static_cast<int>(chain.type) << '|'
                << chain.nodeId << '|'
                << chain.sourceNodeId << '|'
                << chain.sourceFaction << '|'
                << chain.targetFaction << '|'
                << chain.executeDay << '|'
                << chain.executeHour << '|'
                << chain.reason
                << '\n';
        }
        for (const RegionPressureFront& front : gState.regionFronts)
        {
            if (!front.active)
            {
                continue;
            }
            out << "FRONT="
                << front.regionName << '|'
                << front.lawPressure << '|'
                << front.outlawPressure << '|'
                << front.frontState << '|'
                << front.lastSpilloverDay << '|'
                << front.lastSpilloverHour
                << '\n';
        }
        for (const RegionCadence& cadence : gState.regionCadences)
        {
            if (!cadence.active)
            {
                continue;
            }
            out << "CADENCE="
                << cadence.regionName << '|'
                << cadence.fatigue << '|'
                << cadence.recovery << '|'
                << cadence.momentum << '|'
                << cadence.cadenceState << '|'
                << cadence.lastShiftDay
                << '\n';
        }
        for (const RegionLogistics& logistics : gState.regionLogistics)
        {
            if (!logistics.active)
            {
                continue;
            }
            out << "LOGISTICS="
                << logistics.regionName << '|'
                << logistics.stock << '|'
                << logistics.convoyPressure << '|'
                << logistics.strain << '|'
                << logistics.supportState << '|'
                << logistics.lastRefreshDay
                << '\n';
        }
        for (const RegionCivilianClimate& climate : gState.regionClimate)
        {
            if (!climate.active)
            {
                continue;
            }
            out << "CLIMATE="
                << climate.regionName << '|'
                << climate.support << '|'
                << climate.panic << '|'
                << climate.repression << '|'
                << climate.rumorTrust << '|'
                << climate.climateState << '|'
                << climate.lastRefreshDay
                << '\n';
        }
        for (const RegionCampaignOutlook& campaign : gState.regionCampaigns)
        {
            if (!campaign.active)
            {
                continue;
            }
            out << "CAMPAIGN="
                << campaign.regionName << '|'
                << campaign.lawControl << '|'
                << campaign.outlawControl << '|'
                << campaign.civilianTilt << '|'
                << campaign.strategicValue << '|'
                << campaign.campaignState << '|'
                << campaign.lastRefreshDay
                << '\n';
        }
        if (gState.theaterSummary.active)
        {
            out << "THEATER="
                << gState.theaterSummary.theaterState << '|'
                << gState.theaterSummary.lawLeaningRegions << '|'
                << gState.theaterSummary.outlawLeaningRegions << '|'
                << gState.theaterSummary.knifeEdgeRegions << '|'
                << gState.theaterSummary.playerMomentum << '|'
                << gState.theaterSummary.lastRefreshDay
                << '\n';
        }

        gState.saveDirty = false;
        MarkDiagnosticsDirty();
        WriteDiagnosticsReport(true);
        PushToast("Faction-war state saved to disk");
    }

    void LoadStateFromDisk()
    {
        std::ifstream in(kSavePath);
        if (!in)
        {
            PushToast("Load skipped: no faction-war save file yet");
            return;
        }

        BootSeeds();

        std::string line;
        while (std::getline(in, line))
        {
            if (line.rfind("FACTION_INDEX=", 0) == 0)
            {
                gState.factionIndex = ClampInt(std::atoi(line.c_str() + 14), 0, static_cast<int>(std::size(kSeedFactions)) - 1);
            }
            else if (line.rfind("RANK_INDEX=", 0) == 0)
            {
                gState.rankIndex = ClampInt(std::atoi(line.c_str() + 11), 0, static_cast<int>(kRanks.size()) - 1);
            }
            else if (line.rfind("NODE_INDEX=", 0) == 0)
            {
                gState.nodeIndex = ClampInt(std::atoi(line.c_str() + 11), 0, static_cast<int>(gState.nodes.size()) - 1);
            }
            else if (line.rfind("SIMULATION=", 0) == 0)
            {
                gState.simulationEnabled = std::atoi(line.c_str() + 11) != 0;
            }
            else if (line.rfind("PLAYER_LEADING=", 0) == 0)
            {
                gState.playerLeading = std::atoi(line.c_str() + 15) != 0;
            }
            else if (line.rfind("POSSE_STRENGTH=", 0) == 0)
            {
                gState.posseStrength = ClampInt(std::atoi(line.c_str() + 15), 0, 8);
            }
            else if (line.rfind("NODE=", 0) == 0)
            {
                std::stringstream ss(line.substr(5));
                std::string parts[19];
                for (int i = 0; i < 19 && std::getline(ss, parts[i], "|"[0]); ++i) {}
                RuntimeNode* node = FindNodeById(parts[0].c_str());
                if (node)
                {
                    CopyString(node->controller, sizeof(node->controller), parts[1].c_str());
                    CopyString(node->activeAssaultFaction, sizeof(node->activeAssaultFaction), parts[2].c_str());
                    node->pressure = ClampInt(std::atoi(parts[3].c_str()), 0, 100);
                    node->heat = ClampInt(std::atoi(parts[4].c_str()), 0, 100);
                    node->supply = ClampInt(std::atoi(parts[5].c_str()), 0, 100);
                    node->fear = ClampInt(std::atoi(parts[6].c_str()), 0, 100);
                    node->fortification = ClampInt(std::atoi(parts[7].c_str()), 0, 100);
                    node->contested = std::atoi(parts[8].c_str()) != 0;
                    if (!parts[9].empty()) node->lastTriggeredDay = std::atoi(parts[9].c_str());
                    if (!parts[10].empty()) node->dailyTriggerCount = std::atoi(parts[10].c_str());
                    if (!parts[11].empty()) node->activeStartHour = std::atoi(parts[11].c_str());
                    if (!parts[12].empty()) node->activeEndHour = std::atoi(parts[12].c_str());
                    if (!parts[13].empty()) CopyString(node->occupationState, sizeof(node->occupationState), parts[13].c_str());
                    if (!parts[14].empty()) CopyString(node->occupationFaction, sizeof(node->occupationFaction), parts[14].c_str());
                    if (!parts[15].empty()) node->occupationUntilDay = std::atoi(parts[15].c_str());
                    if (!parts[16].empty()) CopyString(node->roadControlState, sizeof(node->roadControlState), parts[16].c_str());
                    if (!parts[17].empty()) node->routePressure = std::atoi(parts[17].c_str());
                    if (!parts[18].empty()) node->escortNeed = std::atoi(parts[18].c_str());
                    RefreshLocalState(*node);
                }
            }
            else if (line.rfind("CHAIN=", 0) == 0)
            {
                std::stringstream ss(line.substr(6));
                std::string parts[8];
                for (int i = 0; i < 8 && std::getline(ss, parts[i], "|"[0]); ++i) {}
                for (PendingConflictChain& chain : gState.pendingChains)
                {
                    if (chain.active)
                    {
                        continue;
                    }
                    chain.active = true;
                    chain.type = static_cast<PendingConflictType>(std::atoi(parts[0].c_str()));
                    CopyString(chain.nodeId, sizeof(chain.nodeId), parts[1].c_str());
                    CopyString(chain.sourceNodeId, sizeof(chain.sourceNodeId), parts[2].c_str());
                    CopyString(chain.sourceFaction, sizeof(chain.sourceFaction), parts[3].c_str());
                    CopyString(chain.targetFaction, sizeof(chain.targetFaction), parts[4].c_str());
                    chain.executeDay = std::atoi(parts[5].c_str());
                    chain.executeHour = std::atoi(parts[6].c_str());
                    CopyString(chain.reason, sizeof(chain.reason), parts[7].c_str());
                    break;
                }
            }
            else if (line.rfind("FRONT=", 0) == 0)
            {
                std::stringstream ss(line.substr(6));
                std::string parts[6];
                for (int i = 0; i < 6 && std::getline(ss, parts[i], "|"[0]); ++i) {}
                for (RegionPressureFront& front : gState.regionFronts)
                {
                    if (front.active)
                    {
                        continue;
                    }
                    front.active = true;
                    CopyString(front.regionName, sizeof(front.regionName), parts[0].c_str());
                    front.lawPressure = std::atoi(parts[1].c_str());
                    front.outlawPressure = std::atoi(parts[2].c_str());
                    CopyString(front.frontState, sizeof(front.frontState), parts[3].c_str());
                    front.lastSpilloverDay = std::atoi(parts[4].c_str());
                    front.lastSpilloverHour = std::atoi(parts[5].c_str());
                    break;
                }
            }
            else if (line.rfind("CADENCE=", 0) == 0)
            {
                std::stringstream ss(line.substr(8));
                std::string parts[6];
                for (int i = 0; i < 6 && std::getline(ss, parts[i], "|"[0]); ++i) {}
                for (RegionCadence& cadence : gState.regionCadences)
                {
                    if (cadence.active)
                    {
                        continue;
                    }
                    cadence.active = true;
                    CopyString(cadence.regionName, sizeof(cadence.regionName), parts[0].c_str());
                    cadence.fatigue = std::atoi(parts[1].c_str());
                    cadence.recovery = std::atoi(parts[2].c_str());
                    cadence.momentum = std::atoi(parts[3].c_str());
                    CopyString(cadence.cadenceState, sizeof(cadence.cadenceState), parts[4].c_str());
                    cadence.lastShiftDay = std::atoi(parts[5].c_str());
                    break;
                }
            }
            else if (line.rfind("LOGISTICS=", 0) == 0)
            {
                std::stringstream ss(line.substr(10));
                std::string parts[6];
                for (int i = 0; i < 6 && std::getline(ss, parts[i], "|"[0]); ++i) {}
                for (RegionLogistics& logistics : gState.regionLogistics)
                {
                    if (logistics.active)
                    {
                        continue;
                    }
                    logistics.active = true;
                    CopyString(logistics.regionName, sizeof(logistics.regionName), parts[0].c_str());
                    logistics.stock = std::atoi(parts[1].c_str());
                    logistics.convoyPressure = std::atoi(parts[2].c_str());
                    logistics.strain = std::atoi(parts[3].c_str());
                    CopyString(logistics.supportState, sizeof(logistics.supportState), parts[4].c_str());
                    logistics.lastRefreshDay = std::atoi(parts[5].c_str());
                    break;
                }
            }
            else if (line.rfind("CLIMATE=", 0) == 0)
            {
                std::stringstream ss(line.substr(8));
                std::string parts[7];
                for (int i = 0; i < 7 && std::getline(ss, parts[i], "|"[0]); ++i) {}
                for (RegionCivilianClimate& climate : gState.regionClimate)
                {
                    if (climate.active)
                    {
                        continue;
                    }
                    climate.active = true;
                    CopyString(climate.regionName, sizeof(climate.regionName), parts[0].c_str());
                    climate.support = std::atoi(parts[1].c_str());
                    climate.panic = std::atoi(parts[2].c_str());
                    climate.repression = std::atoi(parts[3].c_str());
                    climate.rumorTrust = std::atoi(parts[4].c_str());
                    CopyString(climate.climateState, sizeof(climate.climateState), parts[5].c_str());
                    climate.lastRefreshDay = std::atoi(parts[6].c_str());
                    break;
                }
            }
            else if (line.rfind("CAMPAIGN=", 0) == 0)
            {
                std::stringstream ss(line.substr(9));
                std::string parts[7];
                for (int i = 0; i < 7 && std::getline(ss, parts[i], "|"[0]); ++i) {}
                for (RegionCampaignOutlook& campaign : gState.regionCampaigns)
                {
                    if (campaign.active)
                    {
                        continue;
                    }
                    campaign.active = true;
                    CopyString(campaign.regionName, sizeof(campaign.regionName), parts[0].c_str());
                    campaign.lawControl = std::atoi(parts[1].c_str());
                    campaign.outlawControl = std::atoi(parts[2].c_str());
                    campaign.civilianTilt = std::atoi(parts[3].c_str());
                    campaign.strategicValue = std::atoi(parts[4].c_str());
                    CopyString(campaign.campaignState, sizeof(campaign.campaignState), parts[5].c_str());
                    campaign.lastRefreshDay = std::atoi(parts[6].c_str());
                    break;
                }
            }
            else if (line.rfind("THEATER=", 0) == 0)
            {
                std::stringstream ss(line.substr(8));
                std::string parts[6];
                for (int i = 0; i < 6 && std::getline(ss, parts[i], "|"[0]); ++i) {}
                gState.theaterSummary.active = true;
                CopyString(gState.theaterSummary.theaterState, sizeof(gState.theaterSummary.theaterState), parts[0].c_str());
                gState.theaterSummary.lawLeaningRegions = std::atoi(parts[1].c_str());
                gState.theaterSummary.outlawLeaningRegions = std::atoi(parts[2].c_str());
                gState.theaterSummary.knifeEdgeRegions = std::atoi(parts[3].c_str());
                gState.theaterSummary.playerMomentum = std::atoi(parts[4].c_str());
                gState.theaterSummary.lastRefreshDay = std::atoi(parts[5].c_str());
            }
        }

        RefreshRegionFronts();
        RefreshRegionLogistics();
        RefreshRegionClimate();
        RefreshRegionCampaign();
        RefreshTheaterSummary();
        for (RuntimeNode& node : gState.nodes)
        {
            RefreshLocalState(node);
        }

        gState.saveDirty = false;
        MarkDiagnosticsDirty();
        WriteDiagnosticsReport(true);
        PushToast("Faction-war state loaded from disk");
    }

    void AdvanceFaction()
    {
        gState.factionIndex = (gState.factionIndex + 1) % static_cast<int>(std::size(kSeedFactions));
        gState.saveDirty = true;
        PushToast("Faction focus changed");
    }

    void AdvanceRank()
    {
        gState.rankIndex = (gState.rankIndex + 1) % static_cast<int>(kRanks.size());
        gState.playerLeading = gState.rankIndex >= 2;
        gState.saveDirty = true;
        PushToast("Player rank changed");
    }

    void AdvanceNode()
    {
        gState.nodeIndex = (gState.nodeIndex + 1) % static_cast<int>(gState.nodes.size());
        PushToast("Territory node changed");
    }

    void ToggleLeadershipMode()
    {
        gState.playerLeading = !gState.playerLeading;
        gState.saveDirty = true;
        PushToast(gState.playerLeading ? "Player switched to leader posture" : "Player switched to follower posture");
    }

    void ApplyMembershipPreview()
    {
        Actor localPlayerActor = ACTOR::GET_PLAYER_ACTOR(-1);
        if (!ACTOR::IS_ACTOR_VALID(localPlayerActor))
        {
            PushToast("Membership bind failed: local player actor is not valid");
            return;
        }

        gState.focusedFactionBindingId = GetFactionBindingId(CurrentFaction().engineFaction);
        if (gState.focusedFactionBindingId >= 0)
        {
            UNSORTED::SET_ACTOR_FACTION(localPlayerActor, gState.focusedFactionBindingId);
            gState.localPlayerFactionId = UNSORTED::GET_ACTOR_FACTION(localPlayerActor);
            gState.membershipPreviewApplied = true;
            gState.saveDirty = true;
            PushToast("Focused faction was applied to the local player actor");
            return;
        }

        gState.membershipPreviewApplied = true;
        gState.saveDirty = true;
        PushToast("No faction ID binding yet for the focused faction; sample live IDs and fill the bindings template");
    }

    void ClaimNodeForFocusedFaction()
    {
        RuntimeNode& node = CurrentNodeMutable();
        CopyString(node.controller, sizeof(node.controller), CurrentFaction().engineFaction);
        CopyString(node.activeAssaultFaction, sizeof(node.activeAssaultFaction), "");
        node.pressure = ClampInt(node.pressure + 18, 0, 100);
        node.heat = ClampInt(node.heat + 10, 0, 100);
        node.supply = ClampInt(node.supply + 8, 0, 100);
        node.contested = false;
        RefreshLocalState(node);
        gState.saveDirty = true;
        PushToast("Node controller reassigned inside persistent faction-war state");
    }

    void StartRaidPreview()
    {
        RuntimeNode& node = CurrentNodeMutable();
        CopyString(node.activeAssaultFaction, sizeof(node.activeAssaultFaction), CurrentFaction().engineFaction);
        node.contested = true;
        node.pressure = ClampInt(node.pressure + 10, 0, 100);
        node.heat = ClampInt(node.heat + 8, 0, 100);
        node.fear = ClampInt(node.fear + 6, 0, 100);
        RefreshLocalState(node);
        gState.saveDirty = true;
        PushToast("Raid seeded into node simulation state");
    }

    void StartDefensePreview()
    {
        RuntimeNode& node = CurrentNodeMutable();
        if (!node.contested)
        {
            CopyString(node.activeAssaultFaction, sizeof(node.activeAssaultFaction), CurrentFaction().engineFaction);
            node.contested = true;
        }
        node.fortification = ClampInt(node.fortification + 12, 0, 100);
        node.supply = ClampInt(node.supply + 5, 0, 100);
        node.heat = ClampInt(node.heat + 4, 0, 100);
        RefreshLocalState(node);
        gState.saveDirty = true;
        PushToast("Defense posture strengthened for current node");
    }

    void EmergencyResetNodeState()
    {
        RuntimeNode& node = CurrentNodeMutable();
        const SeedNode& seed = kSeedNodes[static_cast<std::size_t>(gState.nodeIndex)];
        CopyString(node.controller, sizeof(node.controller), seed.defaultController);
        CopyString(node.activeAssaultFaction, sizeof(node.activeAssaultFaction), "");
        node.pressure = seed.basePressure;
        node.heat = seed.baseHeat;
        node.supply = ContainsCsvToken(seed.strategicTagsCsv, "supply_node") || ContainsCsvToken(seed.strategicTagsCsv, "transport_post") ? 70 : 50;
        node.fear = ContainsCsvToken(seed.strategicTagsCsv, "civilian_pressure") ? 35 : 20;
        node.fortification = ContainsCsvToken(seed.strategicTagsCsv, "outlaw_hideout") ? 20 : 5;
        node.contested = false;
        RefreshLocalState(node);
        gState.saveDirty = true;
        PushToast("Current node was reset to its seeded state");
    }

    void StageTravelPreview()
    {
        const RuntimeNode& node = CurrentNode();
        Actor localPlayerActor = ACTOR::GET_PLAYER_ACTOR(-1);
        if (!ACTOR::IS_ACTOR_VALID(localPlayerActor))
        {
            PushToast("Travel failed: local player actor is not valid");
            return;
        }
        if (node.hasAnchor)
        {
            Vector3 pos(node.anchorX, node.anchorY, node.anchorZ);
            ACTOR::TELEPORT_ACTOR(localPlayerActor, &pos, false, false, false);
            ACTOR::SET_ACTOR_HEADING(localPlayerActor, node.anchorHeading, false);
            char msg[192]{};
            std::snprintf(msg, sizeof(msg), "Traveled to %s using seeded node anchor", node.displayName);
            PushToast(msg);
            return;
        }
        char msg[192]{};
        std::snprintf(msg, sizeof(msg), "Current node still has no travel anchor: %s", node.displayName);
        PushToast(msg);
    }

    void AcceptOrCompleteMission()
    {
        if (!gState.activeMission.valid)
        {
            CaptureLiveFactionSnapshot();
            return;
        }

        RuntimeNode& node = CurrentNodeMutable();
        RegionCivilianClimate* climate = FindClimateMutable(node.regionName);
        if (!gState.missionAccepted)
        {
            gState.missionAccepted = true;
            gState.missionProgress = 5;
            gState.saveDirty = true;
            PushToast("Mission accepted into the active faction-war state");
            return;
        }

        gState.missionAccepted = false;
        gState.missionProgress = 100;
        if (StringEquals(gState.activeMission.missionId, "defend_hideout") || StringEquals(gState.activeMission.missionId, "fortify_node"))
        {
            node.fortification = ClampInt(node.fortification + 18, 0, 100);
            node.supply = ClampInt(node.supply + 12, 0, 100);
            node.pressure = ClampInt(node.pressure - 10, 0, 100);
            node.contested = false;
            CopyString(node.activeAssaultFaction, sizeof(node.activeAssaultFaction), "");
        }
        else if (StringEquals(gState.activeMission.missionId, "raid_road_convoy") || StringEquals(gState.activeMission.missionId, "retaliation_strike") || StringEquals(gState.activeMission.missionId, "tax_settlement"))
        {
            node.heat = ClampInt(node.heat + 12, 0, 100);
            node.pressure = ClampInt(node.pressure + 16, 0, 100);
            node.fear = ClampInt(node.fear + 10, 0, 100);
            if (node.pressure >= 90)
            {
                CopyString(node.controller, sizeof(node.controller), CurrentFaction().engineFaction);
            }
        }
        else
        {
            node.supply = ClampInt(node.supply + 8, 0, 100);
            node.heat = ClampInt(node.heat + 4, 0, 100);
        }
        if (climate)
        {
            if (StringEquals(gState.activeMission.missionId, "escort_supply_wagon") || StringEquals(gState.activeMission.missionId, "fortify_node"))
            {
                climate->support = ClampInt(climate->support + 8, 0, 100);
                climate->panic = ClampInt(climate->panic - 6, 0, 100);
                climate->rumorTrust = ClampInt(climate->rumorTrust + 4, 0, 100);
            }
            else if (StringEquals(gState.activeMission.missionId, "tax_settlement") || StringEquals(gState.activeMission.missionId, "retaliation_strike") || StringEquals(gState.activeMission.missionId, "raid_road_convoy"))
            {
                climate->panic = ClampInt(climate->panic + 8, 0, 100);
                if (CurrentFaction().lawEnforcement)
                {
                    climate->repression = ClampInt(climate->repression + 7, 0, 100);
                    climate->support = ClampInt(climate->support - 4, 0, 100);
                }
                else
                {
                    climate->support = ClampInt(climate->support + 3, 0, 100);
                    climate->rumorTrust = ClampInt(climate->rumorTrust - 6, 0, 100);
                }
            }
            else if (StringEquals(gState.activeMission.missionId, "frontier_patrol"))
            {
                if (CurrentFaction().lawEnforcement)
                {
                    climate->panic = ClampInt(climate->panic - 4, 0, 100);
                    climate->repression = ClampInt(climate->repression + 2, 0, 100);
                }
                else
                {
                    climate->panic = ClampInt(climate->panic + 4, 0, 100);
                    climate->support = ClampInt(climate->support + 2, 0, 100);
                }
            }
            RefreshRegionClimate();
        RefreshRegionCampaign();
        RefreshTheaterSummary();
        }
        RefreshLocalState(node);
        gState.saveDirty = true;
        PushToast("Mission completed and folded into territory state");
    }

    void ToggleSimulation()
    {
        gState.simulationEnabled = !gState.simulationEnabled;
        gState.saveDirty = true;
        PushToast(gState.simulationEnabled ? "Faction-war simulation enabled" : "Faction-war simulation paused");
    }

    void TickWorldSimulation()
    {
        RefreshGameClockState();
        ++gState.simulationStep;
        const CodeRedFactionSeedV26::SeedFaction& focused = CurrentFaction();

        if (gState.missionAccepted && gState.activeMission.valid)
        {
            gState.missionProgress = ClampInt(gState.missionProgress + (gState.playerLeading ? 9 : 6), 0, 100);
            if (gState.missionProgress == 100)
            {
                PushToast("Mission objective is ready to turn in automatically once you stay in the hot zone long enough");
            }
        }

        for (RuntimeNode& node : gState.nodes)
        {
            const bool controllerIsLaw = FindSeedFaction(node.controller) && FindSeedFaction(node.controller)->lawEnforcement;
            if (node.contested)
            {
                int assault = FactionAggression(node.activeAssaultFaction[0] ? node.activeAssaultFaction : focused.engineFaction);
                int defense = FactionDiscipline(node.controller) + node.fortification / 8 + node.supply / 20;
                const char* battleProfile = LogisticsBattleProfile(node);
                if (StringEquals(battleProfile, "lean_front"))
                {
                    assault += 1;
                    defense -= 2;
                }
                else if (StringEquals(battleProfile, "convoy_front"))
                {
                    assault += 1;
                    defense += 1;
                }
                else if (StringEquals(battleProfile, "fortified_front"))
                {
                    defense += 4;
                }
                else if (StringEquals(battleProfile, "searched_front"))
                {
                    defense += 3;
                }
                const int delta = assault - defense + PositiveMod(gState.simulationStep + node.pressure, 5) - 2;

                node.pressure = ClampInt(node.pressure + delta, 0, 100);
                node.heat = ClampInt(node.heat + 5, 0, 100);
                node.supply = ClampInt(node.supply - 2, 0, 100);
                node.fear = ClampInt(node.fear + 3, 0, 100);

                if (node.pressure >= 100 && node.activeAssaultFaction[0])
                {
                    CopyString(node.controller, sizeof(node.controller), node.activeAssaultFaction);
                    CopyString(node.activeAssaultFaction, sizeof(node.activeAssaultFaction), "");
                    node.contested = false;
                    node.pressure = 62;
                    node.fortification = ClampInt(node.fortification / 2, 0, 100);
                    ApplyOccupationOutcome(node, node.controller, true, "frontline_capture");
                    char msg[192]{};
                    std::snprintf(msg, sizeof(msg), "%s fell to %s", node.displayName, node.controller);
                    PushToast(msg);
                }
                else if (node.pressure <= 10)
                {
                    CopyString(node.activeAssaultFaction, sizeof(node.activeAssaultFaction), "");
                    node.contested = false;
                    node.pressure = 24;
                    ApplyOccupationOutcome(node, node.controller, false, "frontline_defense");
                    char msg[192]{};
                    std::snprintf(msg, sizeof(msg), "Defense held at %s", node.displayName);
                    PushToast(msg);
                }
            }
            else
            {
                node.heat = ClampInt(node.heat + (controllerIsLaw ? -2 : 1) + (node.outlawWeight >= 65 && !controllerIsLaw ? 1 : 0), 0, 100);
                node.supply = ClampInt(node.supply + (controllerIsLaw ? 2 : 1) + (node.wagonWeight >= 65 ? 1 : 0), 0, 100);
                node.fear = ClampInt(node.fear + (controllerIsLaw ? -1 : 1) - (node.civilianWeight >= 60 ? 1 : 0), 0, 100);
                node.pressure = ClampInt(node.pressure + (controllerIsLaw ? -1 : 1) + (node.lawWeight >= 65 && controllerIsLaw ? -1 : 0), 0, 100);

                if (!controllerIsLaw && (node.heat >= 72 || node.outlawWeight >= 70) && PositiveMod(gState.simulationStep + node.fear, 3) == 0)
                {
                    const RuntimeNode* neighbor = FindNeighborNode(node, PositiveMod(gState.simulationStep, 2));
                    if (neighbor)
                    {
                        CopyString(node.activeAssaultFaction, sizeof(node.activeAssaultFaction), node.controller);
                        node.contested = true;
                        PushToast(ContainsCsvToken(node.strategicTagsCsv, "transport_post")
                            ? "A transport artery tipped into active conflict"
                            : "A frontier node tipped into active conflict");
                    }
                }
            }
            RefreshLocalState(node);
        }

        if (gState.missionAccepted && gState.missionProgress >= 100)
        {
            AcceptOrCompleteMission();
        }

        RuntimeNode& currentNode = CurrentNodeMutable();
        if (IsPlayerNearNode(currentNode, 160.0f) && GetTickCount64() >= currentNode.nextAutoEventAllowedMs)
        {
            const bool nodeLawControlled = FindSeedFaction(currentNode.controller) && FindSeedFaction(currentNode.controller)->lawEnforcement;
            const bool dailyPending = NodeNeedsDailyActivity(currentNode);
            const bool activeHour = IsNodeActiveHour(currentNode, gState.gameHour);
            const char* preferredEvent = DeterminePreferredAutoEvent(currentNode);
            const int eventCooldownMs = DetermineAutoEventCooldownMs(currentNode, preferredEvent, dailyPending);
            const bool wantsTown = StringEquals(preferredEvent, "town_assault") && CurrentNodeSupportsTownAssault(currentNode);
            const bool wantsShootout = StringEquals(preferredEvent, "regional_shootout") && CurrentNodeSupportsRegionalShootout(currentNode);
            const char* logisticsState = LogisticsStateName(currentNode);
            const bool convoyHot = StringEquals(logisticsState, "convoys_hot");
            const bool fortifying = StringEquals(logisticsState, "fortifying");
            const bool starved = StringEquals(logisticsState, "starved");
            if (!gState.townAssault.active && !gState.regionalShootout.active && wantsTown)
            {
                if ((dailyPending && activeHour) ||
                    currentNode.routePressure >= (fortifying ? 60 : 52) ||
                    currentNode.escortNeed >= (fortifying ? 56 : 48) ||
                    (nodeLawControlled && currentNode.heat >= (fortifying ? 40 : 34)) ||
                    (!nodeLawControlled && currentNode.heat >= (starved ? 46 : 42)) ||
                    StringEquals(currentNode.roadControlState, "raider_corridor"))
                {
                    currentNode.nextAutoEventAllowedMs = GetTickCount64() + eventCooldownMs;
                    StartTownAssaultEvent();
                }
            }
            else if (!gState.townAssault.active && !gState.regionalShootout.active && wantsShootout)
            {
                if ((dailyPending && activeHour) ||
                    currentNode.routePressure >= (convoyHot ? 34 : 40) ||
                    currentNode.escortNeed >= (convoyHot ? 34 : 42) ||
                    currentNode.heat >= (fortifying ? 34 : 28) ||
                    currentNode.pressure >= (starved ? 62 : 68) ||
                    currentNode.contested ||
                    StringEquals(currentNode.roadControlState, "marshal_roadblock") ||
                    StringEquals(currentNode.roadControlState, "smuggler_lane") ||
                    convoyHot)
                {
                    currentNode.nextAutoEventAllowedMs = GetTickCount64() + eventCooldownMs;
                    StartRegionalShootoutEvent();
                }
            }
        }

        TickTownAssault();
        TickRegionalShootout();
        TickRegionalBackgroundPressure();
        TickPendingConflictChains();
        RefreshRegionFronts();
        RefreshRegionCadences();
        RefreshRegionClimate();
        RefreshRegionCampaign();
        RefreshTheaterSummary();
        WriteDiagnosticsReport(false);

        gState.nextWorldTickMs = GetTickCount64() + 4000;
        gState.saveDirty = true;
    }

    void TickRegionalBackgroundPressure()
    {
        const uint64_t now = GetTickCount64();
        if (now < gState.nextNeighborPulseTickMs)
        {
            return;
        }
        gState.nextNeighborPulseTickMs = now + 9000;
        if (gState.townAssault.active || gState.regionalShootout.active)
        {
            RuntimeNode* center = FindNodeById(gState.townAssault.active ? gState.townAssault.nodeId : gState.regionalShootout.nodeId);
            if (center)
            {
                std::stringstream ss(center->neighborsCsv);
                std::string item;
                while (std::getline(ss, item, ','))
                {
                    RuntimeNode* node = FindNodeById(item.c_str());
                    if (!node)
                    {
                        continue;
                    }
                    node->heat = ClampInt(node->heat + 2, 0, 100);
                    node->fear = ClampInt(node->fear + 2, 0, 100);
                    if (StringEquals(node->controller, center->controller))
                    {
                        node->pressure = ClampInt(node->pressure + 2, 0, 100);
                    }
                    RefreshLocalState(*node);
                }
                gState.saveDirty = true;
            }
        }

        for (const RegionDirective& directive : gState.regionDirectives)
        {
            if (!directive.active)
            {
                continue;
            }
            for (RuntimeNode& node : gState.nodes)
            {
                if (!StringEquals(node.regionName, directive.regionName))
                {
                    continue;
                }
                if (StringEquals(directive.directiveName, "crackdown"))
                {
                    if (IsLawFactionName(node.controller))
                    {
                        node.fortification = ClampInt(node.fortification + 1, 0, 100);
                        node.heat = ClampInt(node.heat + 1, 0, 100);
                    }
                    else
                    {
                        node.fear = ClampInt(node.fear + 1, 0, 100);
                        node.heat = ClampInt(node.heat + 2, 0, 100);
                    }
                }
                else if (StringEquals(directive.directiveName, "smuggling"))
                {
                    if (ContainsCsvToken(node.strategicTagsCsv, "transport_post") || StringEquals(node.contextTag, "black_market"))
                    {
                        node.supply = ClampInt(node.supply + 2, 0, 100);
                        node.pressure = ClampInt(node.pressure + 2, 0, 100);
                    }
                }
                else if (StringEquals(directive.directiveName, "raid"))
                {
                    if (ContainsCsvToken(node.strategicTagsCsv, "outlaw_hideout") || ContainsCsvToken(node.strategicTagsCsv, "raid_origin") || StringEquals(node.contextTag, "camp_hideout") || StringEquals(node.contextTag, "rustler_hideout"))
                    {
                        node.heat = ClampInt(node.heat + 2, 0, 100);
                        node.pressure = ClampInt(node.pressure + 2, 0, 100);
                    }
                }
                else if (StringEquals(directive.directiveName, "fortify"))
                {
                    if (ContainsCsvToken(node.strategicTagsCsv, "war_anchor") || StringEquals(node.contextTag, "fort_war"))
                    {
                        node.fortification = ClampInt(node.fortification + 2, 0, 100);
                        node.supply = ClampInt(node.supply + 1, 0, 100);
                    }
                }
                else if (StringEquals(directive.directiveName, "scavenge"))
                {
                    if (StringEquals(node.contextTag, "ghost_town") || StringEquals(node.contextTag, "mine_hideout"))
                    {
                        node.fear = ClampInt(node.fear + 1, 0, 100);
                        node.heat = ClampInt(node.heat + 1, 0, 100);
                    }
                }
                if (OccupationActive(node))
                {
                    if (IsLawFactionName(node.occupationFaction))
                    {
                        node.fortification = ClampInt(node.fortification + 1, 0, 100);
                        node.fear = ClampInt(node.fear + 1, 0, 100);
                    }
                    else
                    {
                        node.heat = ClampInt(node.heat + 1, 0, 100);
                        node.pressure = ClampInt(node.pressure + 1, 0, 100);
                        node.fear = ClampInt(node.fear + 1, 0, 100);
                    }
                }
                if (node.wagonWeight >= 65)
                {
                    node.supply = ClampInt(node.supply + 1, 0, 100);
                }
                if (node.outlawWeight >= 65 && !IsLawFactionName(node.controller))
                {
                    node.heat = ClampInt(node.heat + 1, 0, 100);
                    node.pressure = ClampInt(node.pressure + 1, 0, 100);
                }
                const RegionCadence* cadence = FindCadenceForRegion(node.regionName);
                if (cadence)
                {
                    if (StringEquals(cadence->cadenceState, "surging"))
                    {
                        node.heat = ClampInt(node.heat + 1, 0, 100);
                        node.pressure = ClampInt(node.pressure + 1, 0, 100);
                    }
                    else if (StringEquals(cadence->cadenceState, "recovering") || StringEquals(cadence->cadenceState, "spent"))
                    {
                        node.heat = ClampInt(node.heat - 1, 0, 100);
                        node.pressure = ClampInt(node.pressure - 1, 0, 100);
                        node.supply = ClampInt(node.supply + 1, 0, 100);
                    }
                }
                if (node.lawWeight >= 65 && IsLawFactionName(node.controller))
                {
                    node.fortification = ClampInt(node.fortification + 1, 0, 100);
                }
                if (node.civilianWeight >= 60 && !node.contested)
                {
                    node.fear = ClampInt(node.fear - 1, 0, 100);
                }
                RefreshLocalState(node);
            }
        }
        RefreshRegionFronts();
        PropagateCorridorPressure();
        PropagateMultiFrontPressure();
        gState.saveDirty = true;
    }

    void AutosaveIfNeeded()
    {
        if (!gState.saveDirty)
        {
            return;
        }

        const uint64_t now = GetTickCount64();
        if (now >= gState.nextAutosaveTickMs)
        {
            SaveStateToDisk();
            gState.nextAutosaveTickMs = now + 15000;
        }
    }



    void RenderOverlay()
    {
        const RuntimeNode& node = CurrentNode();
        const CodeRedFactionSeedV26::SeedFaction& faction = CurrentFaction();
        const char* anchorSource = "None";
        bool usedProxyAnchor = false;
        GetResolvedNodeAnchor(node, nullptr, nullptr, &anchorSource, &usedProxyAnchor);
        char buffer[4096]{};
        char recentBlock[1024]{};
        BuildRecentEventsBlock(recentBlock, sizeof(recentBlock));
        std::snprintf(
            buffer,
            sizeof(buffer),
            "<red>Code RED Faction War v26</red>\\n"
            "Faction Focus: <green>%s</green> (%s)  Binding: <green>%d</green>  PlayerFaction: <green>%d</green>\\n"
            "Health: <green>%d</green>  Stability: <green>%s</green>  Unresolved Bindings: <green>%d</green>  Proxy Anchors: <green>%d</green>  Diagnostics Writes: <green>%d</green>\\n"
            "Rank: <green>%s</green>   Command Posture: <green>%s</green>   Posse Order: <green>%s</green>\\n"
            "Friendly Squad: <green>%d</green>   Rival/Law: <green>%d</green>   Law: <green>%d</green>   Town Attackers: <green>%d</green>\\n"
            "Game Day: <green>%d</green>   Hour: <green>%d</green>   Daily Triggers: <green>%d</green>   Active Hours: <green>%02d-%02d</green>\\n"
            "Save Dirty: <green>%s</green>   Simulation: <green>%s</green>   Town Assault: <green>%s</green>   Shootout: <green>%s</green>   Chains: <green>%d</green>   Fronts: <green>%d</green>\\n"
            "Cadence: <green>%s</green>  Fatigue: <green>%d</green>  Recovery: <green>%d</green>  Logistics: <green>%s</green>  Battle: <green>%s</green>  Stock: <green>%d</green>  Convoys: <green>%d</green>\n"
            "Campaign: <green>%s</green>  LawCtrl: <green>%d</green>  OutlawCtrl: <green>%d</green>  CivilianTilt: <green>%d</green>  Theater: <green>%s</green>  Momentum: <green>%d</green>\n"
            "Climate: <green>%s</green>  Support: <green>%d</green>  Panic: <green>%d</green>  Repression: <green>%d</green>  Rumor: <green>%d</green>\n"
            "Reinforce / Town A:<green>%s</green> D:<green>%s</green>   Shootout O:<green>%s</green> L:<green>%s</green>\n"
            "Node: <green>%s</green> [%s]  Context: <green>%s</green>  Auto Region: <green>%s</green>  Directive: <green>%s</green>   Front: <green>%s</green>\\n"
            "Anchor Source: <green>%s</green>  Anchor Mode: <green>%s</green>\\n"
            "Controller: <green>%s</green>   Active Assault: <green>%s</green>\\n"
            "Occupation: <green>%s</green>  Holder: <green>%s</green>  Until Day: <green>%d</green>\\n"
            "Pressure: <green>%d</green>  Heat: <green>%d</green>  Supply: <green>%d</green>  Fear: <green>%d</green>  Fortify: <green>%d</green>\\n"
            "Contested: <green>%s</green>   State: <green>%s</green>   Traffic: <green>%s</green>\\n"
            "Road: <green>%s</green>  Route Pressure: <green>%d</green>  Escort Need: <green>%d</green>  Entry Bias: <green>%s</green>\\n"
            "Population: <green>%s</green>   C:<green>%d</green> O:<green>%d</green> L:<green>%d</green> W:<green>%d</green>\\n"
            "Ambient: <green>%s</green>  Civilian: <green>%s</green>\\n"
            "Outlaw: <green>%s</green>  Law: <green>%s</green>  Travel: <green>%s</green>\\n"
            "Tags: <green>%s</green>\\n"
            "Neighbors: <green>%s</green>\\n"
            "Mission: <green>%s</green>  Accepted: <green>%s</green>  Progress: <green>%d%%%%</green>\\n"
            "%s\\n\\n"
            "Recent Frontier Events:\\n%s\\n\\n"
            "[F7] Overlay  [F8] Faction  [F9] Rank  [F10] Node\\n"
            "[F11] Leader/Follower  Region visits auto-trigger node activity\\n"
            "[NUMPAD0] Live faction sample  [MULTIPLY] Save  [SUBTRACT] Load  [ADD] Reset Node\\n\\n"
            "Last: %s",
            faction.brandName,
            faction.engineFaction,
            gState.focusedFactionBindingId,
            gState.localPlayerFactionId,
            gState.runtimeHealthScore,
            RuntimeDegradedMode() ? "Fallback" : "Direct",
            gState.unresolvedBindingCount,
            gState.proxyAnchorCount,
            gState.diagnosticsWrites,
            kRanks[static_cast<std::size_t>(gState.rankIndex)],
            gState.playerLeading ? "Leader" : "Follower",
            PosseOrderName(gState.posseOrder),
            gState.activeFriendlyCount,
            gState.activeEnemyCount,
            gState.activeLawCount,
            gState.activeTownAttackerCount,
            gState.gameDay,
            gState.gameHour,
            node.dailyTriggerCount,
            node.activeStartHour,
            node.activeEndHour,
            gState.saveDirty ? "Yes" : "No",
            gState.simulationEnabled ? "Active" : "Paused",
            gState.townAssault.active ? "Active" : "Idle",
            gState.regionalShootout.active ? "Active" : "Idle",
            CountPendingConflictChains(),
            CountActiveRegionFronts(),
            CadenceStateName(node),
            CadenceFatigueForNode(node),
            CadenceRecoveryForNode(node),
            LogisticsStateName(node),
            LogisticsBattleProfile(node),
            LogisticsStockForNode(node),
            LogisticsConvoyForNode(node),
            CampaignStateName(node),
            CampaignLawControlForNode(node),
            CampaignOutlawControlForNode(node),
            CampaignCivilianTiltForNode(node),
            TheaterStateName(),
            TheaterPlayerMomentum(),
            ClimateStateName(node),
            ClimateSupportForNode(node),
            ClimatePanicForNode(node),
            ClimateRepressionForNode(node),
            ClimateRumorTrustForNode(node),
            gState.townAssault.attackerNeighborReinforced ? "Yes" : "No",
            gState.townAssault.defenderNeighborReinforced ? "Yes" : "No",
            gState.regionalShootout.outlawNeighborReinforced ? "Yes" : "No",
            gState.regionalShootout.lawNeighborReinforced ? "Yes" : "No",
            node.displayName,
            node.regionName,
            node.contextTag[0] ? node.contextTag : "frontier",
            gState.autoRegionNodeId[0] ? gState.autoRegionNodeId : "None",
            DirectiveDisplayName(DirectiveForNode(node)),
            FrontStateName(node),
            anchorSource,
            usedProxyAnchor ? "Proxy" : "Direct",
            node.controller,
            node.activeAssaultFaction[0] ? node.activeAssaultFaction : "None",
            OccupationActive(node) ? node.occupationState : "None",
            OccupationActive(node) ? node.occupationFaction : "None",
            OccupationActive(node) ? node.occupationUntilDay : -1,
            node.pressure,
            node.heat,
            node.supply,
            node.fear,
            node.fortification,
            node.contested ? "Yes" : "No",
            node.localState[0] ? node.localState : "None",
            node.trafficState[0] ? node.trafficState : "None",
            node.roadControlState[0] ? node.roadControlState : "None",
            node.routePressure,
            node.escortNeed,
            DescribeEntryConflictBias(node),
            node.populationProfile[0] ? node.populationProfile : "None",
            node.civilianWeight,
            node.outlawWeight,
            node.lawWeight,
            node.wagonWeight,
            node.ambientSet[0] ? node.ambientSet : "None",
            node.civilianArchetype[0] ? node.civilianArchetype : "None",
            node.outlawArchetype[0] ? node.outlawArchetype : "None",
            node.lawArchetype[0] ? node.lawArchetype : "None",
            node.travelFlavor[0] ? node.travelFlavor : "None",
            node.strategicTagsCsv[0] ? node.strategicTagsCsv : "None",
            node.neighborsCsv[0] ? node.neighborsCsv : "None",
            gState.activeMission.valid ? gState.activeMission.displayName : "None",
            gState.missionAccepted ? "Yes" : "No",
            gState.missionProgress,
            gState.activeMission.valid ? gState.activeMission.description : "Generate a mission from the current war state.",
            recentBlock,
            gState.lastToast);
        HUD::PRINT_HELP_B(buffer, 0.25f, true, 1, 0, 0, 0, 0);
    }

}

void CodeRedFactionWarV26::Initialize()
{
    if (gState.initialized)
    {
        return;
    }

    gState = RuntimeState{};
    BootSeeds();
    LoadBindingsTemplate();
    gState.initialized = true;
    gState.nextRumorTickMs = GetTickCount64() + 7000;
    gState.nextWorldTickMs = GetTickCount64() + 4000;
    gState.nextAutosaveTickMs = GetTickCount64() + 15000;
    gState.nextDiagnosticsTickMs = GetTickCount64() + 5000;
    RefreshGameClockState();
    LoadStateFromDisk();
    gState.overlayOpen = false;
    gState.simulationEnabled = true;
    PushToast("Code RED Faction War No-SC menu-free world layer initialized - WorldResourceBridge Pass02");
}

void CodeRedFactionWarV26::Update()
{
    if (!gState.initialized)
    {
        CodeRedFactionWarV26::Initialize();
    }

    RefreshAutoRegionFocus();

    if (!kMenuFreeWorldMode && kEnableDebugHotkeys)
    {
        if (REDHOOK::IS_KEY_PRESSED(KEY_F7))
        {
            gState.overlayOpen = !gState.overlayOpen;
            PushToast(gState.overlayOpen ? "Faction War overlay opened" : "Faction War overlay closed");
        }
        if (REDHOOK::IS_KEY_PRESSED(KEY_F8))
        {
            AdvanceFaction();
        }
        if (REDHOOK::IS_KEY_PRESSED(KEY_F9))
        {
            AdvanceRank();
        }
        if (REDHOOK::IS_KEY_PRESSED(KEY_F10))
        {
            AdvanceNode();
        }
        if (REDHOOK::IS_KEY_PRESSED(KEY_F11))
        {
            ToggleLeadershipMode();
        }
        if (REDHOOK::IS_KEY_PRESSED(KEY_NUMPAD1))
        {
            ApplyMembershipPreview();
        }
        if (REDHOOK::IS_KEY_PRESSED(KEY_NUMPAD2))
        {
            ClaimNodeForFocusedFaction();
        }
        if (REDHOOK::IS_KEY_PRESSED(KEY_NUMPAD3))
        {
            StartRaidPreview();
        }
        if (REDHOOK::IS_KEY_PRESSED(KEY_NUMPAD4))
        {
            StartDefensePreview();
        }
        if (REDHOOK::IS_KEY_PRESSED(KEY_NUMPAD5))
        {
            SpawnAllyPosse();
        }
        if (REDHOOK::IS_KEY_PRESSED(KEY_NUMPAD6))
        {
            if (CurrentNodeSupportsTownAssault(CurrentNode()))
            {
                StartTownAssaultEvent();
            }
            else
            {
                SpawnRivalRaid();
            }
        }
        if (REDHOOK::IS_KEY_PRESSED(KEY_NUMPAD7))
        {
            CyclePosseOrder();
        }
        if (REDHOOK::IS_KEY_PRESSED(KEY_NUMPAD8))
        {
            GenerateMissionFromCurrentState();
        }
        if (REDHOOK::IS_KEY_PRESSED(KEY_NUMPAD9))
        {
            ToggleSimulation();
        }
        if (REDHOOK::IS_KEY_PRESSED(KEY_NUMPAD0))
        {
            AcceptOrCompleteMission();
        }
        if (REDHOOK::IS_KEY_PRESSED(KEY_DIVIDE))
        {
            StageTravelPreview();
        }
        if (REDHOOK::IS_KEY_PRESSED(KEY_DECIMAL))
        {
            DespawnAllSpawnedActors(true);
        }
        if (REDHOOK::IS_KEY_PRESSED(KEY_MULTIPLY))
        {
            SaveStateToDisk();
        }
        if (REDHOOK::IS_KEY_PRESSED(KEY_SUBTRACT))
        {
            LoadStateFromDisk();
        }
        if (REDHOOK::IS_KEY_PRESSED(KEY_ADD))
        {
            EmergencyResetNodeState();
        }
    }

    RecountSpawnedActors();
    gState.posseStrength = gState.activeFriendlyCount;

    const uint64_t now = GetTickCount64();
    if (gState.simulationEnabled && now >= gState.nextWorldTickMs)
    {
        TickWorldSimulation();
    }
    if (now >= gState.nextRumorTickMs)
    {
        TriggerRumorTick();
    }
    AutosaveIfNeeded();

    if (!kMenuFreeWorldMode && gState.overlayOpen)
    {
        RenderOverlay();
    }
}

void CodeRedFactionWarV26::Shutdown()
{
    if (!gState.initialized)
    {
        return;
    }

    if (gState.saveDirty)
    {
        SaveStateToDisk();
    }

    DespawnAllSpawnedActors(false);
    gState.overlayOpen = false;
    gState.initialized = false;
    LogLine("Code RED Faction War No-SC menu-free world layer shutdown");
}
