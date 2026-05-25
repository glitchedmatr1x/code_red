#include "SoulStealerModule.h"
#include "MockNativeBridge.h"
#include <iostream>
#include <stdexcept>

using namespace codered;

static void require(bool value, const char* msg) {
    if (!value) throw std::runtime_error(msg);
}

static void fallback_test() {
    MockNativeBridge bridge;
    SoulStealerConfig cfg;
    cfg.targetMode = TargetMode::ReticleFirst;
    cfg.possessionMode = PossessionMode::PreferRealSwap;
    cfg.hideOriginalTargetOnFallback = false;
    SoulStealerModule soul(bridge, cfg);

    soul.arm();
    require(soul.captureBestTarget(), "fallback capture failed");
    require(soul.state() == SoulStealerModule::State::Possessing, "not possessing after fallback");
    require(soul.possessionStatus() == PossessionStatus::FallbackModelTeleport, "wrong fallback status");
    require(bridge.actors[bridge.player].model == 0x222, "player model did not become target model");
    require(bridge.actors[2].frozen, "target actor not frozen in fallback");
    soul.cancel();
    require(soul.state() == SoulStealerModule::State::Idle, "not idle after cancel");
    require(!bridge.actors[2].frozen, "target actor still frozen after cancel");
}

static void real_swap_test() {
    MockNativeBridge bridge;
    bridge.allowRealSwap = true;
    SoulStealerConfig cfg;
    cfg.targetMode = TargetMode::ReticleFirst;
    cfg.possessionMode = PossessionMode::PreferRealSwap;
    SoulStealerModule soul(bridge, cfg);

    soul.arm();
    require(soul.captureBestTarget(), "real swap capture failed");
    require(soul.possessionStatus() == PossessionStatus::RealSwap, "wrong real swap status");
    require(bridge.player == 2, "mock player handle did not swap");
    soul.cancel();
}

static void animal_filter_test() {
    MockNativeBridge bridge;
    bridge.reticleTarget = 4;
    SoulStealerConfig cfg;
    cfg.targetMode = TargetMode::ReticleFirst;
    cfg.allowAnimals = false;
    SoulStealerModule soul(bridge, cfg);
    soul.arm();
    // Reticle horse should be rejected, but nearest forward NPC should still be captured.
    require(soul.captureBestTarget(), "animal-filter fallback target failed");
    require(soul.targetActor() == 2, "expected fallback to NPC after animal rejection");
}

int main() {
    try {
        fallback_test();
        real_swap_test();
        animal_filter_test();
    } catch (const std::exception& e) {
        std::cerr << "mock test failed: " << e.what() << "\n";
        return 1;
    }
    std::cout << "all Soul Stealer Pass 2 mock tests passed\n";
    return 0;
}
