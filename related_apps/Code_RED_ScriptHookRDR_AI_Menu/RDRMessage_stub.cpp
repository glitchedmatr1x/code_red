#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <cstdio>
#include <cstring>

static void appendLog(const char* commandLine) {
    char exePath[MAX_PATH] = {};
    DWORD len = GetModuleFileNameA(nullptr, exePath, MAX_PATH);
    if (len == 0 || len >= MAX_PATH) return;

    char* slash = std::strrchr(exePath, '\\');
    if (!slash) return;
    slash[1] = '\0';
    std::strcat(exePath, "RDRMessage_stub.log");

    HANDLE file = CreateFileA(exePath, FILE_APPEND_DATA,
                              FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr,
                              OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) return;

    SYSTEMTIME now = {};
    GetLocalTime(&now);
    char line[2048] = {};
    std::snprintf(line, sizeof(line),
                  "[%04u-%02u-%02u %02u:%02u:%02u] RDRMessage shim invoked: %s\r\n",
                  now.wYear, now.wMonth, now.wDay, now.wHour, now.wMinute,
                  now.wSecond, commandLine ? commandLine : "");
    DWORD written = 0;
    WriteFile(file, line, static_cast<DWORD>(std::strlen(line)), &written, nullptr);
    CloseHandle(file);
}

int WINAPI WinMain(HINSTANCE, HINSTANCE, LPSTR commandLine, int) {
    appendLog(commandLine);
    Sleep(120000);
    return 0;
}
