#include "MockInputBridge.h"

namespace codered {

void MockInputBridge::press(std::uint32_t vkCode) {
    pressed_.insert(vkCode);
    down_.insert(vkCode);
}

void MockInputBridge::hold(std::uint32_t vkCode) {
    down_.insert(vkCode);
}

void MockInputBridge::release(std::uint32_t vkCode) {
    down_.erase(vkCode);
}

void MockInputBridge::clearFrame() {
    pressed_.clear();
}

bool MockInputBridge::wasKeyPressed(std::uint32_t vkCode) {
    return pressed_.count(vkCode) != 0;
}

bool MockInputBridge::isKeyDown(std::uint32_t vkCode) {
    return down_.count(vkCode) != 0;
}

} // namespace codered
