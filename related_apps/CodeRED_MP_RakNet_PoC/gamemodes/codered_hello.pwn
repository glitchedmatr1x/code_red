#include <codered_mp>

enum E_LOCATION
{
    locName[24],
    Float:locX,
    Float:locY,
    Float:locZ,
    Float:locHeading
}

new g_locations[][E_LOCATION] =
{
    {"agave viejo", -1545.03, 3913.46, 15.03, 0.0},
    {"armadillo", -2175.62, 2613.50, 16.31, 0.0},
    {"beecher's hope", -83.45, 1374.10, 117.68, 0.0},
    {"benedict point", -3686.96, 3493.24, 8.62, 0.0},
    {"blackwater", 711.18, 1252.763, 78.31, 0.0},
    {"casa madrugada", -788.78, 3729.81, 13.04, 0.0},
    {"chuparosa", -2714.70, 4251.90, 32.37, 0.0},
    {"cochinay", -739.29, 784.69, 179.10, 0.0},
    {"coot's chapel", -1793.48, 2836.85, 23.78, 0.0},
    {"el matadero", -455.44, 3926.91, 20.84, 0.0},
    {"el presidio", -698.10, 3323.25, 63.25, 0.0},
    {"escalera", -4265.4355, 4475.8091, 19.1414, 31.9},
    {"fort mercer", -2622.53, 3390.51, 68.08, 0.0},
    {"gaptooth breach", -4461.66, 3310.42, 7.78, 0.0},
    {"lake don julio", -1955.07, 3255.67, 24.82, 0.0},
    {"las hermanas", -1700.31, 4242.14, 8.08, 0.0},
    {"manzanita post", -428.16, 1615.59, 151.34, 0.0},
    {"mcfarlane's ranch", -887.08, 2420.53, 90.19, 0.0},
    {"nosalida", -4701.72, 3958.90, 3.04, 0.0},
    {"pacific union camp", -273.95, 2113.30, 84.31, 0.0},
    {"plainview", -3126.40, 3724.13, 43.57, 0.0},
    {"rathskeller fork", -3661.76, 2124.70, 42.23, 0.0},
    {"ridgewood farm", -3275.14, 2719.86, 15.89, 0.0},
    {"serendipity's wreck", 325.34, 1939.81, 74.29, 0.0},
    {"thieve's landing", 111.55, 2318.82, 73.29, 0.0},
    {"tumbleweed", -4007.25, 2935.45, 28.46, 0.0},
    {"tesoro azul", -3288.00, 4547.00, 38.20, 0.0},
    {"torquemada", 376.66, 3459.57, 76.30, 0.0},
    {"twin rocks", -2425.06, 2138.93, 25.00, 0.0}
};

main()
{
    print("Code RED Pawn VM main()");
}

stock SendPlayerMessage(playerid, const message[])
{
    SendClientNativeCall(playerid, "client_add_message", message);
    return 1;
}

stock SendTeleport(playerid, Float:x, Float:y, Float:z, Float:heading)
{
    SendClientTeleport(playerid, x, y, z, heading);
    return 1;
}

stock SplitCommand(const text[], command[], commandSize, args[], argsSize)
{
    new len = strlen(text);
    new i = 1;
    new ci = 0;

    while (i < len && text[i] != ' ' && ci < commandSize - 1)
    {
        command[ci++] = text[i++];
    }
    command[ci] = 0;

    while (i < len && text[i] == ' ')
    {
        i++;
    }

    new ai = 0;
    while (i < len && ai < argsSize - 1)
    {
        args[ai++] = text[i++];
    }
    args[ai] = 0;
    return ci > 0;
}

stock FindLocationIndex(const name[])
{
    for (new i = 0; i < sizeof(g_locations); i++)
    {
        if (strcmp(g_locations[i][locName], name, true) == 0)
        {
            return i;
        }
    }
    return -1;
}

stock SendTeleportList(playerid)
{
    SendPlayerMessage(playerid, "Use /tp <location>. Escalera is the default MP spawn.");
    SendPlayerMessage(playerid, "Locations: escalera, armadillo, blackwater, chuparosa");
    SendPlayerMessage(playerid, "Locations: fort mercer, tumbleweed, benedict point");
    SendPlayerMessage(playerid, "Locations: mcfarlane's ranch, beecher's hope");
    SendPlayerMessage(playerid, "Locations: plainview, tesoro azul, thieve's landing");
    SendPlayerMessage(playerid, "Locations: coot's chapel, el presidio, torquemada");
    return 1;
}

stock SendHelp(playerid)
{
    SendPlayerMessage(playerid, "Commands: /help /tplist /tp /tpid /model /heal /god /killme /noclip /propset");
    SendPlayerMessage(playerid, "/tp escalera uses the RDRMP mptransport Escalera marker.");
    SendPlayerMessage(playerid, "/model <enum> syncs your actor enum to remote clients.");
    return 1;
}

stock HandleCommand(playerid, const text[])
{
    new command[24];
    new args[96];
    if (!SplitCommand(text, command, sizeof(command), args, sizeof(args)))
    {
        return 0;
    }

    if (strcmp(command, "help", true) == 0)
    {
        SendHelp(playerid);
        return 0;
    }

    if (strcmp(command, "tplist", true) == 0)
    {
        SendTeleportList(playerid);
        return 0;
    }

    if (strcmp(command, "tp", true) == 0)
    {
        new location = FindLocationIndex(args);
        if (location < 0)
        {
            SendPlayerMessage(playerid, "Invalid location. Use /tplist.");
            return 0;
        }

        SendTeleport(playerid,
                     g_locations[location][locX],
                     g_locations[location][locY],
                     g_locations[location][locZ],
                     g_locations[location][locHeading]);

        SendPlayerMessage(playerid, "Teleporting.");
        return 0;
    }

    if (strcmp(command, "tpid", true) == 0)
    {
        if (!args[0])
        {
            SendPlayerMessage(playerid, "Usage: /tpid <playerid>");
            return 0;
        }

        new target = strval(args);
        if (target == playerid)
        {
            SendPlayerMessage(playerid, "You cannot teleport to yourself.");
            return 0;
        }
        if (target < 0 || target >= MAX_PLAYERS || !IsPlayerConnected(target))
        {
            SendPlayerMessage(playerid, "Player is not connected.");
            return 0;
        }

        new Float:x, Float:y, Float:z, Float:heading;
        if (!GetPlayerPosition(target, x, y, z))
        {
            SendPlayerMessage(playerid, "Could not read target position.");
            return 0;
        }
        if (!GetPlayerHeading(target, heading))
        {
            heading = 0.0;
        }
        SendTeleport(playerid, x, y, z, heading);

        SendPlayerMessage(playerid, "Teleporting to player.");
        return 0;
    }

    if (strcmp(command, "model", true) == 0)
    {
        if (!args[0])
        {
            SendPlayerMessage(playerid, "Usage: /model <actor enum>");
            return 0;
        }

        new actorEnum = strval(args);
        if (actorEnum <= 0 || actorEnum > 65535)
        {
            SendPlayerMessage(playerid, "Invalid actor enum.");
            return 0;
        }

        SetPlayerActorEnum(playerid, actorEnum);
        SendClientNativeCallInt(playerid, "client_set_model", actorEnum);
        SendPlayerMessage(playerid, "Actor enum changed.");
        return 0;
    }

    if (strcmp(command, "killme", true) == 0)
    {
        SendClientNativeCall(playerid, "client_kill_player", "");
        return 0;
    }

    if (strcmp(command, "heal", true) == 0)
    {
        SendClientNativeCall(playerid, "client_set_health", "100");
        SendPlayerMessage(playerid, "Health restored.");
        return 0;
    }

    if (strcmp(command, "god", true) == 0)
    {
        SendClientNativeCall(playerid, "client_god_toggle", "");
        return 0;
    }

    if (strcmp(command, "noclip", true) == 0)
    {
        SendClientNativeCall(playerid, "client_noclip_toggle", "");
        return 0;
    }

    if (strcmp(command, "propset", true) == 0)
    {
        SendClientNativeCall(playerid, "client_spawn_transport_propset", "-4279.0459,4471.1343,18.3635,56.0467");
        SendPlayerMessage(playerid, "Requested Escalera mp_transport propset.");
        return 0;
    }

    if (strcmp(command, "time", true) == 0 || strcmp(command, "weather", true) == 0 ||
        strcmp(command, "kick", true) == 0)
    {
        SendPlayerMessage(playerid, "This RDRMP command is staged but not wired yet.");
        return 0;
    }

    SendPlayerMessage(playerid, "Unknown command. Use /help.");
    return 0;
}

public OnGameModeInit()
{
    SetGameModeText("Code RED MP Initial Freeroam");
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
    SendPlayerMessage(playerid, "Welcome to Code RED MP. Use /help.");
    SendClientNativeCall(playerid, "client_spawn_transport_propset", "-4279.0459,4471.1343,18.3635,56.0467");
    return 1;
}

public OnPlayerDisconnect(playerid)
{
    print("Pawn OnPlayerDisconnect");
    return 1;
}

public OnPlayerText(playerid, text[])
{
    if (text[0] == '/')
    {
        return HandleCommand(playerid, text);
    }

    SendClientNativeCall(playerid, "client_chat_echo", text);
    return 1;
}
