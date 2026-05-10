#if defined _codered_mp_included
    #endinput
#endif
#define _codered_mp_included

#define MAX_PLAYERS (32)

native print(const string[]);
native SetGameModeText(const text[]);
native SendClientNativeCall(playerid, const callName[], const payload[]);

forward OnGameModeInit();
forward OnGameModeExit();
forward OnPlayerConnect(playerid);
forward OnPlayerDisconnect(playerid);
forward OnPlayerText(playerid, text[]);
