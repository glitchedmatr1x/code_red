// CodeREDCompanion.asi
// Pass 0.2 command/status proof layer for Code RED.
// This build is intentionally harmless: no hooks, no memory patches, no game writes.

#include <windows.h>

#include <algorithm>
#include <chrono>
#include <cwctype>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

namespace {

constexpr const wchar_t* kPluginName = L"CodeREDCompanion";
constexpr const wchar_t* kPluginVersion = L"0.2.0-command-status-proof";
constexpr const wchar_t* kLogFolderName = L"CodeRED_ASI_Logs";
constexpr const wchar_t* kLogFileName = L"CodeREDCompanion_loader_proof.log";
constexpr const wchar_t* kStatusFileName = L"companion_status.json";
constexpr const wchar_t* kCommandFileRelativePath = L"data\\codered\\companion_commands.txt";
constexpr std::size_t kMaxCommands = 32;
constexpr std::size_t kMaxLineChars = 512;

HMODULE g_module = nullptr;

struct CommandResult {
    std::wstring raw;
    std::wstring verb;
    std::wstring args;
    bool accepted = false;
    std::wstring action = L"noop";
    std::wstring reason;
};

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

std::filesystem::path GetProcessFolder() {
    const auto processPath = GetProcessPath();
    if (!processPath.parent_path().empty()) {
        return processPath.parent_path();
    }
    return std::filesystem::current_path();
}

std::filesystem::path GetLogDir() {
    auto logDir = GetProcessFolder() / kLogFolderName;
    std::error_code ec;
    std::filesystem::create_directories(logDir, ec);
    return logDir;
}

std::filesystem::path GetLogPath() {
    return GetLogDir() / kLogFileName;
}

std::filesystem::path GetStatusPath() {
    return GetLogDir() / kStatusFileName;
}

std::filesystem::path GetCommandPath() {
    return GetProcessFolder() / kCommandFileRelativePath;
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

std::wstring JsonBool(bool value) {
    return value ? L"true" : L"false";
}

std::wstring Trim(const std::wstring& value) {
    const auto begin = std::find_if_not(value.begin(), value.end(), [](wchar_t ch) {
        return std::iswspace(ch) != 0;
    });
    const auto end = std::find_if_not(value.rbegin(), value.rend(), [](wchar_t ch) {
        return std::iswspace(ch) != 0;
    }).base();

    if (begin >= end) {
        return L"";
    }
    return std::wstring(begin, end);
}

std::wstring ToUpper(std::wstring value) {
    std::transform(value.begin(), value.end(), value.begin(), [](wchar_t ch) {
        return static_cast<wchar_t>(std::towupper(ch));
    });
    return value;
}

std::wstring ClampLine(std::wstring line) {
    if (line.size() > kMaxLineChars) {
        line.resize(kMaxLineChars);
    }
    return line;
}

std::wstring JsonEscape(const std::wstring& value) {
    std::wstringstream ss;
    for (const wchar_t ch : value) {
        switch (ch) {
            case L'\\':
                ss << L"\\\\";
                break;
            case L'\"':
                ss << L"\\\"";
                break;
            case L'\b':
                ss << L"\\b";
                break;
            case L'\f':
                ss << L"\\f";
                break;
            case L'\n':
                ss << L"\\n";
                break;
            case L'\r':
                ss << L"\\r";
                break;
            case L'\t':
                ss << L"\\t";
                break;
            default:
                if (ch < 0x20) {
                    ss << L"\\u" << std::hex << std::setw(4) << std::setfill(L'0') << static_cast<int>(ch)
                       << std::dec << std::setfill(L' ');
                } else {
                    ss << ch;
                }
                break;
        }
    }
    return ss.str();
}

bool IsFutureCommand(const std::wstring& verb) {
    return verb == L"SPAWN_ACTOR" || verb == L"FOLLOW" || verb == L"GUARD" || verb == L"ATTACK" ||
           verb == L"DISMISS" || verb == L"MOUNT" || verb == L"WAYPOINT" || verb == L"TELEPORT" ||
           verb == L"SET_FORMATION";
}

CommandResult ParseCommandLine(const std::wstring& rawLine) {
    CommandResult result{};
    result.raw = ClampLine(Trim(rawLine));

    const auto split = result.raw.find_first_of(L" \t");
    if (split == std::wstring::npos) {
        result.verb = ToUpper(result.raw);
        result.args = L"";
    } else {
        result.verb = ToUpper(Trim(result.raw.substr(0, split)));
        result.args = Trim(result.raw.substr(split + 1));
    }

    if (result.verb.empty()) {
        result.accepted = false;
        result.reason = L"empty_command";
    } else if (result.verb == L"PING") {
        result.accepted = true;
        result.reason = L"pong";
    } else if (result.verb == L"STATUS") {
        result.accepted = true;
        result.reason = L"status_written";
    } else if (result.verb == L"VERSION") {
        result.accepted = true;
        result.reason = L"version_reported";
    } else if (result.verb == L"HELP") {
        result.accepted = true;
        result.reason = L"safe_commands_ping_status_version_help";
    } else if (IsFutureCommand(result.verb)) {
        result.accepted = false;
        result.reason = L"recognized_future_command_disabled_in_pass_0_2";
    } else {
        result.accepted = false;
        result.reason = L"unknown_command";
    }

    return result;
}

std::vector<CommandResult> ReadCommands(bool& commandFileFound, bool& commandLimitReached) {
    commandFileFound = false;
    commandLimitReached = false;

    std::vector<CommandResult> commands;
    const auto commandPath = GetCommandPath();

    std::wifstream in(commandPath);
    if (!in) {
        return commands;
    }

    commandFileFound = true;
    std::wstring line;
    while (std::getline(in, line)) {
        auto trimmed = Trim(line);
        if (trimmed.empty() || trimmed[0] == L'#' || trimmed[0] == L';') {
            continue;
        }

        if (commands.size() >= kMaxCommands) {
            commandLimitReached = true;
            break;
        }
        commands.push_back(ParseCommandLine(trimmed));
    }

    return commands;
}

void WriteStatusJson(
    const std::filesystem::path& modulePath,
    const std::filesystem::path& processPath,
    bool commandFileFound,
    bool commandLimitReached,
    const std::vector<CommandResult>& commands) {
    const auto statusPath = GetStatusPath();
    std::wofstream out(statusPath, std::ios::trunc);
    if (!out) {
        AppendLogLine(L"Could not write companion_status.json");
        return;
    }

    out << L"{\n";
    out << L"  \"plugin_name\": \"" << JsonEscape(kPluginName) << L"\",\n";
    out << L"  \"plugin_version\": \"" << JsonEscape(kPluginVersion) << L"\",\n";
    out << L"  \"timestamp\": \"" << JsonEscape(NowStamp()) << L"\",\n";
    out << L"  \"host_process\": \"" << JsonEscape(processPath.wstring()) << L"\",\n";
    out << L"  \"plugin_path\": \"" << JsonEscape(modulePath.wstring()) << L"\",\n";
    out << L"  \"command_file\": \"" << JsonEscape(GetCommandPath().wstring()) << L"\",\n";
    out << L"  \"command_file_found\": " << JsonBool(commandFileFound) << L",\n";
    out << L"  \"command_limit_reached\": " << JsonBool(commandLimitReached) << L",\n";
    out << L"  \"command_count\": " << commands.size() << L",\n";
    out << L"  \"safety\": {\n";
    out << L"    \"hooks_installed\": false,\n";
    out << L"    \"memory_patches_applied\": false,\n";
    out << L"    \"game_files_modified\": false,\n";
    out << L"    \"actor_spawning_enabled\": false,\n";
    out << L"    \"future_commands_blocked\": true\n";
    out << L"  },\n";
    out << L"  \"commands\": [\n";

    for (std::size_t i = 0; i < commands.size(); ++i) {
        const auto& command = commands[i];
        out << L"    {\n";
        out << L"      \"raw\": \"" << JsonEscape(command.raw) << L"\",\n";
        out << L"      \"verb\": \"" << JsonEscape(command.verb) << L"\",\n";
        out << L"      \"args\": \"" << JsonEscape(command.args) << L"\",\n";
        out << L"      \"accepted\": " << JsonBool(command.accepted) << L",\n";
        out << L"      \"action\": \"" << JsonEscape(command.action) << L"\",\n";
        out << L"      \"reason\": \"" << JsonEscape(command.reason) << L"\"\n";
        out << L"    }" << (i + 1 < commands.size() ? L"," : L"") << L"\n";
    }

    out << L"  ]\n";
    out << L"}\n";
}

void LoaderProofWorker() {
    // DllMain stays lightweight. This worker only writes proof logs/status after load.
    std::this_thread::sleep_for(std::chrono::milliseconds(250));

    const auto modulePath = GetModulePath(g_module);
    const auto processPath = GetProcessPath();

    bool commandFileFound = false;
    bool commandLimitReached = false;
    const auto commands = ReadCommands(commandFileFound, commandLimitReached);

    WriteStatusJson(modulePath, processPath, commandFileFound, commandLimitReached, commands);

    AppendLogLine(std::wstring(kPluginName) + L" command/status proof started.");
    AppendLogLine(L"Version: " + std::wstring(kPluginVersion));
    AppendLogLine(L"Plugin path: " + modulePath.wstring());
    AppendLogLine(L"Host process: " + processPath.wstring());
    AppendLogLine(L"Command file: " + GetCommandPath().wstring());
    AppendLogLine(L"Command file found: " + BoolText(commandFileFound));
    AppendLogLine(L"Command count: " + std::to_wstring(commands.size()));
    AppendLogLine(L"Command limit reached: " + BoolText(commandLimitReached));
    AppendLogLine(L"Hooks installed: false");
    AppendLogLine(L"Memory patches applied: false");
    AppendLogLine(L"Game files modified: false");
    AppendLogLine(L"Actor spawning enabled: false");
    AppendLogLine(L"Command/status proof complete: " + BoolText(true));
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
