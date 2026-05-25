// Code RED Soul Stealer Pass 2 integration skeleton.
// This file is intentionally not compiled in the sandbox. It documents exactly
// where Codex should wire the module into the local Windows ASI / ScriptHook RDR project.

#include "../source/SoulStealerModule.h"

// TODO: include the real Code RED native invoker / ScriptHook headers here.
// #include "ScriptHookRDR.h"
// #include "NativeInvoker.h"

namespace codered_integration_todo {

class RdrNativeBridge final : public codered::INativeBridge {
public:
    codered::ActorHandle getPlayerActor() override {
        // TODO: return GET_PLAYER_ACTOR(0) or Code RED's known player actor wrapper.
        return 0;
    }
    bool isActorValid(codered::ActorHandle actor) override {
        // TODO: IS_ACTOR_VALID(actor)
        return actor != 0;
    }
    bool isActorAlive(codered::ActorHandle actor) override {
        // TODO: IS_ACTOR_ALIVE(actor)
        return actor != 0;
    }
    bool isActorPlayer(codered::ActorHandle actor) override {
        // TODO: compare with getPlayerActor(), or use player flag/native if available.
        return actor == getPlayerActor();
    }
    bool isActorAnimal(codered::ActorHandle actor) override {
        // TODO: species/model filter. Default false until native is identified.
        (void)actor;
        return false;
    }
    bool isActorMissionCritical(codered::ActorHandle actor) override {
        // TODO: inspect DECOR/mission flags if available. Default false for first proof.
        (void)actor;
        return false;
    }
    codered::Vec3 getActorPos(codered::ActorHandle actor) override {
        // TODO: GET_ACTOR_POSITION(actor, &vec)
        (void)actor;
        return {};
    }
    float getActorHeading(codered::ActorHandle actor) override {
        // TODO: GET_ACTOR_HEADING(actor)
        (void)actor;
        return 0.0f;
    }
    std::uint32_t getActorModel(codered::ActorHandle actor) override {
        // TODO: GET_ACTORENUM / GET_ACTOR_ENUM / model hash wrapper if present.
        (void)actor;
        return 0;
    }
    std::string getActorModelName(codered::ActorHandle actor) override {
        // TODO: optional enum-to-name mapping from Code RED actor enum CSV.
        (void)actor;
        return {};
    }
    std::vector<codered::ActorHandle> getAllActors() override {
        // TODO: use Code RED's actor iterator if one exists.
        // Fallback: scan nearby actors from object pools if available.
        return {};
    }
    codered::ActorHandle getActorUnderReticle() override {
        // TODO: identify native equivalent, or return 0 and rely on nearest-forward selection.
        return 0;
    }
    codered::ActorHandle getLastActorDamagedByPlayer() override {
        // TODO: hook damage event or known script event; return 0 until wired.
        return 0;
    }
    void clearActorTasksImmediately(codered::ActorHandle actor) override {
        // TODO: TASK_CLEAR_IMMEDIATELY(actor) or closest native.
        (void)actor;
    }
    bool setPlayerControl(bool enabled) override {
        // TODO: SET_PLAYER_CONTROL(0, enabled, ...) or Code RED wrapper.
        (void)enabled;
        return true;
    }
    bool swapPlayerToActor(codered::ActorHandle actor) override {
        // TODO: highest priority research target.
        // Old trainer string map had SwapPlayerToActorR / SetPlayerControlR.
        // Return false until a real PC native/wrapper is proven.
        (void)actor;
        return false;
    }
    bool setPlayerModel(std::uint32_t model) override {
        // TODO: SET_PLAYER_MODEL / SetPlayerModel8 equivalent.
        (void)model;
        return false;
    }
    bool setActorPos(codered::ActorHandle actor, codered::Vec3 pos) override {
        // TODO: SET_ACTOR_POSITION(actor, pos)
        (void)actor; (void)pos;
        return false;
    }
    bool setActorHeading(codered::ActorHandle actor, float heading) override {
        // TODO: SET_ACTOR_HEADING(actor, heading)
        (void)actor; (void)heading;
        return false;
    }
    bool setActorInvincible(codered::ActorHandle actor, bool enabled) override {
        // TODO: SET_ACTOR_INVINCIBLE / health guard if available. Return true if unsupported but nonfatal.
        (void)actor; (void)enabled;
        return true;
    }
    bool setActorFrozen(codered::ActorHandle actor, bool enabled) override {
        // TODO: freeze task/move or clear AI loop if no native exists. Return true if unsupported but nonfatal.
        (void)actor; (void)enabled;
        return true;
    }
    bool setActorVisible(codered::ActorHandle actor, bool visible) override {
        // TODO: SET_ACTOR_VISIBLE if available. Return true if unsupported but nonfatal.
        (void)actor; (void)visible;
        return true;
    }
    void showMessage(const std::string& text) override {
        // TODO: print HUD message / subtitle / trainer menu status.
        (void)text;
    }
    void log(const std::string& text) override {
        // TODO: append to Code_RED/logs/soul_stealer.log.
        (void)text;
    }
};

// Example plugin-level state.
static RdrNativeBridge g_bridge;
static codered::SoulStealerConfig g_config;
static codered::SoulStealerModule g_soul(g_bridge, g_config);

void OnPluginTick() {
    // TODO: wire real key state helpers.
    // if (IsKeyJustPressed(g_config.toggleHotkeyVk)) g_soul.toggleArmed();
    // if (IsKeyJustPressed(g_config.captureHotkeyVk)) g_soul.captureBestTarget();
    // if (IsKeyJustPressed(g_config.cancelHotkeyVk)) g_soul.cancel();
    g_soul.tick();
}

} // namespace codered_integration_todo
