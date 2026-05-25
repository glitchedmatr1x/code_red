#pragma once
#include "HotkeyController.h"
#include <cstdint>
#include <set>

namespace codered {

class MockInputBridge : public IInputBridge {
public:
    void press(std::uint32_t vkCode);
    void hold(std::uint32_t vkCode);
    void release(std::uint32_t vkCode);
    void clearFrame();

    bool wasKeyPressed(std::uint32_t vkCode) override;
    bool isKeyDown(std::uint32_t vkCode) override;

private:
    std::set<std::uint32_t> pressed_;
    std::set<std::uint32_t> down_;
};

} // namespace codered
