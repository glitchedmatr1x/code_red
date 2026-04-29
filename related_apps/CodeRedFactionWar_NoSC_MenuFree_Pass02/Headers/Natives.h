#pragma once

using Player = int;
using Actor = int;
using Vehicle = int;
using Object = int;
using Train = int;
using Pickup = int;
using Blip = int;
using Camera = int;
using Controller = int;
using Layout = int;
using Iterator = int;
using IterationSet = int;
using GUIWindow = int;
using FireHandle = int;
using Volume = int;

using Hash = uint32_t;
using Time = uint32_t;

namespace ACTOR
{
    static Actor CREATE_ACTOR_IN_LAYOUT(Layout _Layout, const char* _Name, int _ActorEnum, Vector2 _PositionXY, float _PositionZ, Vector2 _RotationXY, float _UnkFloat)
    {
        return Invoke<0x8D67F397, Actor>(_Layout, _Name, _ActorEnum, _PositionXY, _PositionZ, _RotationXY, _UnkFloat);
    }

    static void DESTROY_ACTOR(Actor _Actor)
    {
        Invoke<0x8BD21869, void>(_Actor);
    }

    static Vector3 GET_POSITION(Actor _Actor)
    {
        Vector3 position;
        Invoke<0x99BD9D6F, void>(_Actor, &position);
        return position;
    }

    static float GET_HEADING(Actor _Actor)
    {
        return Invoke<0x42DE39F0, float>(_Actor);
    }

    static void SET_ACTOR_HEADING(Actor _Actor, float _Heading, bool _UnkFlag)
    {
        Invoke<0xECE8520B, void>(_Actor, _Heading, _UnkFlag);
    }

    static Actor GET_PLAYER_ACTOR(int _PlayerId)
    {
        return Invoke<0xE8CFDD53, Actor>(_PlayerId);
    }

    static bool IS_ACTOR_VALID(Actor _Actor)
    {
        return Invoke<0xBA6C3E92, bool>(_Actor);
    }

    static void TELEPORT_ACTOR(Actor _Actor, const Vector3* _Position, bool _UnkFlag0, bool _UnkFlag1, bool _UnkFlag2)
    {
        Invoke<0x2D54B916, void>(_Actor, _Position, _UnkFlag0, _UnkFlag1, _UnkFlag2);
    }
}

namespace GAMECLOCK
{
    static int GET_DAY() { return Invoke<0x63D13FB0, int>(); }
    static int GET_HOUR() { return Invoke<0x2765C37E, int>(); }
}

namespace HUD
{
    static void PRINT_HELP_B(const char* _Text, float _Duration, bool _Permanent, int _A, int _B, int _C, int _D, int _E)
    {
        Invoke<0xE42A8278, void>(_Text, _Duration, _Permanent, _A, _B, _C, _D, _E);
    }

    static void PRINT_SMALL_B(const char* _Text, float _Duration, bool _Permanent, int _A, int _B, int _C, int _D)
    {
        Invoke<0x04A38C60, void>(_Text, _Duration, _Permanent, _A, _B, _C, _D);
    }
}

namespace OBJECT
{
    static Layout FIND_NAMED_LAYOUT(const char* _Name)
    {
        return Invoke<0x5699DE7E, Layout>(_Name);
    }
}

namespace STREAM
{
    static void STREAMING_REQUEST_ACTOR(int _ActorEnum, bool _HighPriority, bool _Unknown)
    {
        Invoke<0xB0A79FEE, void>(_ActorEnum, _HighPriority, _Unknown);
    }

    static bool STREAMING_IS_ACTOR_LOADED(int _ActorEnum, int _Unknown)
    {
        return Invoke<0x7DF72579, bool>(_ActorEnum, _Unknown);
    }
}

namespace TASKS
{
    static void TASK_CLEAR(Actor _Actor) { Invoke<0x16876A25, void>(_Actor); }
    static void TASK_FOLLOW_ACTOR(Actor _Actor, Actor _Target) { Invoke<0x12F0911A, void>(_Actor, _Target); }
    static void TASK_KILL_CHAR(Actor _Actor, Actor _Target) { Invoke<0x1AE4B75B, void>(_Actor, _Target); }
    static void TASK_STAND_STILL(Actor _Actor, int _TimeMs, int _A, int _B) { Invoke<0x6F80965D, void>(_Actor, _TimeMs, _A, _B); }
    static void TASK_WANDER(Actor _Actor, int _Style) { Invoke<0x17BCA08E, void>(_Actor, _Style); }
}

namespace UNSORTED
{
    static int GET_ACTOR_FACTION(Actor _Actor) { return Invoke<0x52E2A611, int>(_Actor); }
    static void SET_ACTOR_FACTION(Actor _Actor, int _FactionId) { Invoke<0xCC63951A, void>(_Actor, _FactionId); }
    static void SET_ACTOR_IS_COMPANION(Actor _Actor, bool _Value) { Invoke<0x4C94EB9E, void>(_Actor, _Value); }
    static void ACTOR_MOUNT_ACTOR(Actor _Rider, Actor _Mount) { Invoke<0xC28242F4, void>(_Rider, _Mount); }
    static void MEMORY_ATTACK_ON_SIGHT(Actor _Actor, bool _Value) { Invoke<0x5A83A1EA, void>(_Actor, _Value); }
}
