#include "MockInputBridge.h"
#include "MockNativeBridge.h"
#include "SoulStealerRuntime.h"
#include <cassert>
#include <iostream>

using namespace codered;

static void testRuntimeFallbackFlow() {
    MockNativeBridge native;
    MockInputBridge input;
    SoulStealerConfig cfg;
    cfg.possessionMode = PossessionMode::ForceFallbackModelTeleport;
    cfg.targetMode = TargetMode::NearestRadius;
    cfg.debugLogging = true;

    SoulStealerRuntime runtime(native, input, cfg);

    input.press(cfg.toggleHotkeyVk);
    runtime.tick();
    input.clearFrame();
    assert(runtime.module().state() == SoulStealerModule::State::Armed);

    input.press(cfg.captureHotkeyVk);
    runtime.tick();
    input.clearFrame();
    assert(runtime.module().state() == SoulStealerModule::State::Possessing);
    assert(runtime.module().possessionStatus() == PossessionStatus::FallbackModelTeleport);

    input.press(cfg.cancelHotkeyVk);
    runtime.tick();
    input.clearFrame();
    assert(runtime.module().state() == SoulStealerModule::State::Idle);
}

static void testRuntimeProbeDebug() {
    MockNativeBridge native;
    MockInputBridge input;
    SoulStealerConfig cfg;
    cfg.possessionMode = PossessionMode::ProbeOnly;
    cfg.targetMode = TargetMode::NearestRadius;

    SoulStealerRuntime runtime(native, input, cfg);
    input.press(cfg.toggleHotkeyVk);
    runtime.tick();
    input.clearFrame();
    input.press(cfg.captureHotkeyVk);
    runtime.tick();
    input.clearFrame();
    assert(runtime.module().state() == SoulStealerModule::State::ProbeOnly);

    input.press(0x78); // F9 debug dump
    runtime.tick();
    input.clearFrame();
    assert(!runtime.logger().recent().empty());

    input.press(cfg.cancelHotkeyVk);
    runtime.tick();
    input.clearFrame();
    assert(runtime.module().state() == SoulStealerModule::State::Idle);
}

int main() {
    testRuntimeFallbackFlow();
    testRuntimeProbeDebug();
    std::cout << "Soul Stealer Pass 3 runtime tests passed\n";
    return 0;
}
