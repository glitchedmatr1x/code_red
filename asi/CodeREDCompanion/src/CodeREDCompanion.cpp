// CodeREDCompanion.asi
// Pass 0.1 loader-proof plugin for Code RED.
// This build is intentionally harmless: no hooks, no memory patches, no game writes.

#include <windows.h>

#include <chrono>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <string>
#include <thread>

namespace {

constexpr const wchar_t* kPluginName = L"CodeREDCompanion";
constexpr const wchar_t* kPluginVersion = L"0.1.0-loader-proof";
constexpr const wchar_t* kLogFolderName = L"CodeRED_ASI_Logs";
constexpr const wchar_t* kLogFileName = L"CodeREDCompanion_loader_proof.log";

HMODULE g_module = nullptr;

std::wstring NowStamp() {
    SYSTEMTIME st{};
    GetLocalTime(&st);

    std::wstringstream ss;
    ss << std::setfill(L'0')
       << st.wYear << L"-" << std::setw(2) << st.wMonth << L"-" << std::setw(2) << st.wDay
       << L" " << std::setw(2) << st.wHour << L":" << std::setw(2) << st.wMinute
       << L":" << std::setw(2) << st.wSecond << L"." << std::setw(3) << st.wMilliseconds;
    return ss.str();
}

std::filesystem::path GetModulePath(HMODULE module) {
    wchar_t buffer[MAX_PATH]{};
    const DWORD len = GetModuleFileNameW(module, buffer, MAX_PATH);
    if (len == 0 || len >= MAX_PATH) {
        return {};
    }
    return std::filesystem::path(buffer);
}

std::filesystem::path GetProcessPath() {
    wchar_t buffer[MAX_PATH]{};
    const DWORD len = GetModuleFileNameW(nullptr, buffer, MAX_PATH);
    if (len == 0 || len >= MAX_PATH) {
        return {};
    }
    return std::filesystem::path(buffer);
}

std::filesystem::path GetLogPath() {
    const auto processPath = GetProcessPath();
    auto base = processPath.parent_path();
    if (base.empty()) {
        base = std::filesystem::current_path();
    }

    auto logDir = base / kLogFolderName;
    std::error_code ec;
    std::filesystem::create_directories(logDir, ec);
    return logDir / kLogFileName;
}

void AppendLogLine(const std::wstring& line) {
    const auto logPath = GetLogPath();
    std::wofstream out(logPath, std::ios::app);
    if (!out) {
        return;
    }
    out << L"[" << NowStamp() << L"] " << line << L"\n";
}

std::wstring BoolText(bool value) {
    return value ? L"true" : L"false";
}

void LoaderProofWorker() {
    // DllMain stays lightweight. This worker only writes proof logs after load.
    std::this_thread::sleep_for(std::chrono::milliseconds(250));

    const auto modulePath = GetModulePath(g_module);
    const auto processPath = GetProcessPath();

    AppendLogLine(std::wstring(kPluginName) + L" loader proof started.");
    AppendLogLine(L"Version: " + std::wstring(kPluginVersion));
    AppendLogLine(L"Plugin path: " + modulePath.wstring());
    AppendLogLine(L"Host process: " + processPath.wstring());
    AppendLogLine(L"Hooks installed: false");
    AppendLogLine(L"Memory patches applied: false");
    AppendLogLine(L"Game files modified: false");
    AppendLogLine(L"Loader proof complete: " + BoolText(true));
}

DWORD WINAPI ThreadProc(LPVOID) {
    try {
        LoaderProofWorker();
    } catch (...) {
        // Never allow loader-proof diagnostics to destabilize the host process.
    }
    return 0;
}

void StartWorkerThread() {
    HANDLE thread = CreateThread(nullptr, 0, ThreadProc, nullptr, 0, nullptr);
    if (thread != nullptr) {
        CloseHandle(thread);
    }
}

}  // namespace

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        g_module = module;
        DisableThreadLibraryCalls(module);
        StartWorkerThread();
    }
    return TRUE;
}
