#define _native __attribute((native))
#define l ;

extern _native void WAIT(int ms) l
extern _native int LAUNCH_NEW_SCRIPT(const char* scriptPath, int stackSize) l
extern _native void STREAMING_REQUEST_SCRIPT(int scriptHash) l
extern _native int STREAMING_IS_SCRIPT_LOADED(int scriptHash) l
extern _native int STRING_TO_HASH(const char* text) l

static void request_and_launch(const char* scriptPath)
{
    int scriptHash = STRING_TO_HASH(scriptPath);
    int i = 0;

    STREAMING_REQUEST_SCRIPT(scriptHash);
    while (i < 240 && !STREAMING_IS_SCRIPT_LOADED(scriptHash))
    {
        WAIT(0);
        i++;
    }

    LAUNCH_NEW_SCRIPT(scriptPath, 4096);
}

void main()
{
    WAIT(3000);
    request_and_launch("content/release64/multiplayer/mp_idle");
    request_and_launch("content/release64/multiplayer/multiplayer_system_thread");
    request_and_launch("content/release64/multiplayer/multiplayer_update_thread");
    request_and_launch("content/release64/multiplayer/freemode/freemode");

    while (1)
    {
        WAIT(0);
    }
}
