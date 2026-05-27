#if defined _codered_mp_included
    #endinput
#endif
#define _codered_mp_included

#pragma rational Float

#define MAX_PLAYERS (32)

native strlen(const string[]);
native strcmp(const string1[], const string2[], bool:ignorecase = false, length = -1);
native strval(const string[]);

native print(const string[]);
native SetGameModeText(const text[]);
native SendClientNativeCall(playerid, const callName[], const payload[]);
native SendClientNativeCallInt(playerid, const callName[], value);
native SendClientTeleport(playerid, Float:x, Float:y, Float:z, Float:heading);
native IsPlayerConnected(playerid);
native GetPlayerPosition(playerid, &Float:x, &Float:y, &Float:z);
native GetPlayerHeading(playerid, &Float:heading);
native SetPlayerActorEnum(playerid, actorEnum);

forward OnGameModeInit();
forward OnGameModeExit();
forward OnPlayerConnect(playerid);
forward OnPlayerDisconnect(playerid);
forward OnPlayerText(playerid, text[]);
