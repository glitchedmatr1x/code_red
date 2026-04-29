#include "pch.h"

namespace
{
    std::array<bool, 256> gWasDown{};
}

bool REDHOOK::IS_KEY_PRESSED(int _VirtualKey)
{
    if (_VirtualKey < 0 || _VirtualKey >= static_cast<int>(gWasDown.size()))
    {
        return false;
    }

    const bool isDown = (GetAsyncKeyState(_VirtualKey) & 0x8000) != 0;
    const bool pressed = isDown && !gWasDown[static_cast<std::size_t>(_VirtualKey)];
    gWasDown[static_cast<std::size_t>(_VirtualKey)] = isDown;
    return pressed;
}

void REDHOOK::ResetInputCache()
{
    gWasDown.fill(false);
}
