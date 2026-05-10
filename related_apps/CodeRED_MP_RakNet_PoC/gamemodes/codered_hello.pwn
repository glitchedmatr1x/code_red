#include <codered_mp>

main()
{
    print("Code RED Pawn VM main()");
}

public OnGameModeInit()
{
    SetGameModeText("Code RED Pawn PoC");
    print("Code RED Pawn gamemode loaded");
    return 1;
}

public OnGameModeExit()
{
    print("Code RED Pawn gamemode exit");
    return 1;
}

public OnPlayerConnect(playerid)
{
    print("Pawn OnPlayerConnect");
    SendClientNativeCall(playerid, "client_hello_world", "Hello from Code RED Pawn gamemode");
    return 1;
}

public OnPlayerDisconnect(playerid)
{
    print("Pawn OnPlayerDisconnect");
    return 1;
}

public OnPlayerText(playerid, text[])
{
    SendClientNativeCall(playerid, "client_chat_echo", text);
    return 1;
}
