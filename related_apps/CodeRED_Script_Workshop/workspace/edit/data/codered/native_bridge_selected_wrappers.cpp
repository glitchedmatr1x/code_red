// Code RED selected native bridge prep
// Generated: 2026-05-07T10:52:13Z
// Profile: ai_trainer_core
// Include this below the existing nativeInvoke/nativePush helpers in CodeRED_AI_Menu.cpp.
// This file is bridge prep, not a blind auto-install patch.

namespace codered_native_bridge {

struct NativeBridgeSpec {
    const char* name;
    unsigned long long hash;
    const char* category;
    const char* return_type;
    int param_count;
};

static const NativeBridgeSpec kSelectedNatives[] = {
    {"GET_PLAYER_ACTOR", 0xE8CFDD53ULL, "actor", "Actor", 1},
    {"IS_ACTOR_VALID", 0xBA6C3E92ULL, "actor", "BOOL", 1},
    {"IS_ACTOR_ALIVE", 0x2F232639ULL, "actor", "BOOL", 1},
    {"FIND_NAMED_LAYOUT", 0x5699DE7EULL, "world", "Layout", 1},
    {"CREATE_LAYOUT", 0x6CA53214ULL, "world", "Layout", 1},
    {"CREATE_ACTOR_IN_LAYOUT", 0x8D67F397ULL, "actor", "Actor", 7},
    {"GET_POSITION", 0x99BD9D6FULL, "world", "void", 2},
    {"TELEPORT_ACTOR", 0x2D54B916ULL, "actor", "void", 5},
    {"SET_ACTOR_HEADING", 0xECE8520BULL, "actor", "void", 3},
    {"TASK_CLEAR", 0x16876A25ULL, "ai_task", "void", 1},
    {"TASK_STAND_STILL", 0x6F80965DULL, "ai_task", "void", 4},
    {"TASK_WANDER", 0x17BCA08EULL, "ai_task", "void", 2},
    {"TASK_FOLLOW_ACTOR", 0x12F0911AULL, "actor", "void", 2},
    {"TASK_KILL_CHAR", 0x1AE4B75BULL, "actor", "void", 2},
    {"AI_IS_HOSTILE_OR_ENEMY", 0x9AB964F4ULL, "ai_task", "int", 2},
    {"SET_ACTOR_FACTION", 0xCC63951AULL, "actor", "void", 2},
    {"GET_ACTOR_FACTION", 0x52E2A611ULL, "actor", "int", 1},
    {"GIVE_WEAPON_TO_ACTOR", 0x6AA0EAF2ULL, "actor", "void", 5},
    {"TASK_MOUNT", 0xB6131204ULL, "actor", "void", 6},
    {"TASK_DISMOUNT", 0x5DEF5C4AULL, "actor", "void", 2},
    {"GET_MOUNT", 0xDD31EC4EULL, "actor", "Mount", 1},
    {"GET_VEHICLE", 0xA0936EB6ULL, "vehicle", "Vehicle", 1},
    {"START_VEHICLE", 0xE4442AB2ULL, "vehicle", "void", 1},
    {"STOP_VEHICLE", 0xC2232D29ULL, "vehicle", "void", 1},
    {"TASK_VEHICLE_LEAVE", 0x6C1218A4ULL, "ai_task", "void", 1},
    {"RELEASE_LAYOUT_REF", 0xD9AC8830ULL, "world", "void", 1},
};

static Actor CR_NATIVE_GET_PLAYER_ACTOR(int player) { return nativeInvoke<Actor>(0xE8CFDD53ULL, player); }
static BOOL CR_NATIVE_IS_ACTOR_VALID(Actor actor) { return nativeInvoke<BOOL>(0xBA6C3E92ULL, actor); }
static BOOL CR_NATIVE_IS_ACTOR_ALIVE(Actor actor) { return nativeInvoke<BOOL>(0x2F232639ULL, actor); }
static Layout CR_NATIVE_FIND_NAMED_LAYOUT(const char* layoutName) { return nativeInvoke<Layout>(0x5699DE7EULL, layoutName); }
static Layout CR_NATIVE_CREATE_LAYOUT(const char* layoutName) { return nativeInvoke<Layout>(0x6CA53214ULL, layoutName); }
static Actor CR_NATIVE_CREATE_ACTOR_IN_LAYOUT(Layout layout, const char* layoutName, int actorEnum, Vector2 positionXY, float positionZ, Vector2 orientationXY, float orientationZ) { return nativeInvoke<Actor>(0x8D67F397ULL, layout, layoutName, actorEnum, positionXY, positionZ, orientationXY, orientationZ); }
static void CR_NATIVE_GET_POSITION(Actor actor, Vector3* position) { nativeInvoke<void>(0x99BD9D6FULL, actor, position); }
static void CR_NATIVE_TELEPORT_ACTOR(Actor actor, Vector3* coords, BOOL xAxis, BOOL yAxis, BOOL zAxis) { nativeInvoke<void>(0x2D54B916ULL, actor, coords, xAxis, yAxis, zAxis); }
static void CR_NATIVE_SET_ACTOR_HEADING(Actor actor, float heading, BOOL p2) { nativeInvoke<void>(0xECE8520BULL, actor, heading, p2); }
static void CR_NATIVE_TASK_CLEAR(Actor actor) { nativeInvoke<void>(0x16876A25ULL, actor); }
static void CR_NATIVE_TASK_STAND_STILL(Actor actor, float p1, int p2, int p3) { nativeInvoke<void>(0x6F80965DULL, actor, p1, p2, p3); }
static void CR_NATIVE_TASK_WANDER(int p0, int p1) { nativeInvoke<void>(0x17BCA08EULL, p0, p1); }
static void CR_NATIVE_TASK_FOLLOW_ACTOR(Actor actor, Actor followActor) { nativeInvoke<void>(0x12F0911AULL, actor, followActor); }
static void CR_NATIVE_TASK_KILL_CHAR(int p0, int p1) { nativeInvoke<void>(0x1AE4B75BULL, p0, p1); }
static int CR_NATIVE_AI_IS_HOSTILE_OR_ENEMY(int p0, int p1) { return nativeInvoke<int>(0x9AB964F4ULL, p0, p1); }
static void CR_NATIVE_SET_ACTOR_FACTION(Actor actor, int faction) { nativeInvoke<void>(0xCC63951AULL, actor, faction); }
static int CR_NATIVE_GET_ACTOR_FACTION(Actor actor) { return nativeInvoke<int>(0x52E2A611ULL, actor); }
static void CR_NATIVE_GIVE_WEAPON_TO_ACTOR(Actor actor, int weaponEnum, float ammoCount, BOOL p3, int p4) { nativeInvoke<void>(0x6AA0EAF2ULL, actor, weaponEnum, ammoCount, p3, p4); }
static void CR_NATIVE_TASK_MOUNT(int p0, int p1, int p2, int p3, int p4, int p5) { nativeInvoke<void>(0xB6131204ULL, p0, p1, p2, p3, p4, p5); }
static void CR_NATIVE_TASK_DISMOUNT(int p0, int p1) { nativeInvoke<void>(0x5DEF5C4AULL, p0, p1); }
static int CR_NATIVE_GET_MOUNT(Actor actor) { return nativeInvoke<int>(0xDD31EC4EULL, actor); }
static int CR_NATIVE_GET_VEHICLE(Actor actor) { return nativeInvoke<int>(0xA0936EB6ULL, actor); }
static void CR_NATIVE_START_VEHICLE(int vehicle) { nativeInvoke<void>(0xE4442AB2ULL, vehicle); }
static void CR_NATIVE_STOP_VEHICLE(int vehicle) { nativeInvoke<void>(0xC2232D29ULL, vehicle); }
static void CR_NATIVE_TASK_VEHICLE_LEAVE(int p0) { nativeInvoke<void>(0x6C1218A4ULL, p0); }
static void CR_NATIVE_RELEASE_LAYOUT_REF(Layout layout) { nativeInvoke<void>(0xD9AC8830ULL, layout); }

} // namespace codered_native_bridge
