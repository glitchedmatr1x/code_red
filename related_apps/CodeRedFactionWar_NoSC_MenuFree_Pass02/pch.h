#ifndef PCH_H
#define PCH_H

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <array>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>
#include <type_traits>
#include <vector>

#include <RedHook.h>

#include "Headers/NativesCaller.h"
#include "Headers/MathUtil.h"
#include "Headers/Enums.h"
#include "Headers/Structs.h"
#include "Headers/Natives.h"
#include "Source/Application/Application.h"

namespace REDHOOK
{
    bool IS_KEY_PRESSED(int _VirtualKey);
    void ResetInputCache();
}

#endif
