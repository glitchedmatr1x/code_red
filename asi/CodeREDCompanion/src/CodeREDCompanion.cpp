// CodeREDCompanion.asi
// Pass 0.3 polling/id/whitelist proof layer for Code RED.
// This build is intentionally harmless: no hooks, no memory patches, no game writes.

#include <windows.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cwctype>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <string>
#include <thread>
#include <unordered_set>
#include <vector>

namespace {

constexpr const wchar_t* kPluginName = L"CodeREDCompanion";
constexpr const wchar_t* kPluginVersion = L"0.3.0-polling-id-whitelist-proof";
constexpr const wchar_t* kLogFolderName = L"CodeRED_ASI_Logs";
constexpr const wchar_t* kLogFileName = L"CodeREDCompanion_loader_proof.log";
constexpr const wchar_t* kStatusFileName = L"companion_status.json";
constexpr const wchar_t* kCommandFileRelativePath = L"data\\codered\\companion_commands.txt";
constexpr DWORD kInitialDelayMs = 250;
constexpr DWORD kPollIntervalMs = 3000;
constexpr std::size_t kMaxCommandsPerPoll = 32;
constexpr std::size_t kMaxLineChars = 512;

HMODULE g_module = nullptr;
std::atomic<bool> g_shutdown{false};

struct CommandResult {
    std::wstring raw;
    std::wstring command_id;
    bool explicit_id = false;
    bool skipped_duplicate = false;
    std::wstring verb;
    std::wstring args;
    std::wstring actor_candidate;
    bool actor_whitelisted = false;
    bool accepted = false;
    std::wstring action = L"noop";
    std::wstring reason;
};

struct RuntimeState {
    std::unordered_set<std::wstring> processed_command_ids;
    std::uint64_t poll_count = 0;
    std::uint64_t total_new_commands = 0;
    std::uint64_t total_skipped_duplicates = 0;
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

std::wstring FirstToken(const std::wstring& value) {
    const auto trimmed = Trim(value);
    const auto split = trimmed.find_first_of(L" \t");
    if (split == std::wstring::npos) {
        return trimmed;
    }
    return Trim(trimmed.substr(0, split));
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

std::uint64_t Fnv1a64(const std::wstring& value) {
    std::uint64_t hash = 14695981039346656037ull;
    for (const wchar_t ch : value) {
        const auto code = static_cast<std::uint32_t>(ch);
        hash ^= static_cast<std::uint8_t>(code & 0xffu);
        hash *= 1099511628211ull;
        hash ^= static_cast<std::uint8_t>((code >> 8u) & 0xffu);
        hash *= 1099511628211ull;
    }
    return hash;
}

std::wstring Hex64(std::uint64_t value) {
    std::wstringstream ss;
    ss << std::hex << std::setw(16) << std::setfill(L'0') << value;
    return ss.str();
}

std::wstring AutoCommandId(const std::wstring& body) {
    return L"auto_" + Hex64(Fnv1a64(body));
}

bool HasIdPrefix(const std::wstring& token) {
    const auto upper = ToUpper(token);
    return upper.rfind(L"ID=", 0) == 0 && token.size() > 3;
}

void ExtractCommandIdAndBody(const std::wstring& raw, std::wstring& commandId, bool& explicitId, std::wstring& body) {
    body = ClampLine(Trim(raw));
    explicitId = false;
    commandId = AutoCommandId(body);

    const auto split = body.find_first_of(L" \t");
    const auto first = split == std::wstring::npos ? body : body.substr(0, split);
    if (!HasIdPrefix(first)) {
        return;
    }

    explicitId = true;
    commandId = Trim(first.substr(3));
    if (commandId.empty()) {
        explicitId = false;
        commandId = AutoCommandId(body);
    }

    body = split == std::wstring::npos ? L"" : ClampLine(Trim(body.substr(split + 1)));
}

bool IsSafeProofCommand(const std::wstring& verb) {
    return verb == L"PING" || verb == L"STATUS" || verb == L"VERSION" || verb == L"HELP";
}

bool IsFutureCommand(const std::wstring& verb) {
    return verb == L"SPAWN_ACTOR" || verb == L"FOLLOW" || verb == L"GUARD" || verb == L"ATTACK" ||
           verb == L"DISMISS" || verb == L"MOUNT" || verb == L"WAYPOINT" || verb == L"TELEPORT" ||
           verb == L"SET_FORMATION";
}

bool IsWhitelistedActor(const std::wstring& actorName) {
    const auto actor = ToUpper(actorName);
    return actor == L"ACTOR_CAUCASIAN_ARMY_EASY01" || actor == L"AE_CAUCASIAN_ARMY_EASY01" ||
           actor == L"ACTOR_CAUCASIAN_MALE_TOWNFOLK02" || actor == L"ACTOR_RIDEABLE_ANIMAL_HORSE01" ||
           actor == L"ACTOR_RIDEABLE_ANIMAL_MEX_MULE01" || actor == L"ACTOR_VEHICLE_CAR01" ||
           actor == L"ACTOR_VEHICLE_TRUCK01" || actor == L"ACTOR_VEHICLE_STAGECOACH" ||
           actor == L"ACTOR_VEHICLE_WAGON02" || actor == L"ACTOR_VEHICLE_COACH01";
}

CommandResult ParseCommandLine(const std::wstring& rawLine, RuntimeState& state) {
    CommandResult result{};
    std::wstring body;
    result.raw = ClampLine(Trim(rawLine));
    ExtractCommandIdAndBody(result.raw, result.command_id, result.explicit_id, body);

    const auto split = body.find_first_of(L" \t");
    if (split == std::wstring::npos) {
        result.verb = ToUpper(body);
        result.args = L"";
    } else {
        result.verb = ToUpper(Trim(body.substr(0, split)));
        result.args = Trim(body.substr(split + 1));
    }

    result.actor_candidate = FirstToken(result.args);
    result.actor_whitelisted = !result.actor_candidate.empty() && IsWhitelistedActor(result.actor_candidate);

    if (result.command_id.empty()) {
        result.command_id = AutoCommandId(result.raw);
    }

    if (state.processed_command_ids.find(result.command_id) != state.processed_command_ids.end()) {
        result.skipped_duplicate = true;
        result.accepted = false;
        result.reason = L"duplicate_command_id_skipped";
        ++state.total_skipped_duplicates;
        return result;
    }

    state.processed_command_ids.insert(result.command_id);
    ++state.total_new_commands;

    if (result.verb.empty()) {
        result.accepted = false;
        result.reason = L"empty_command";
    } else if (IsSafeProofCommand(result.verb)) {
        result.accepted = true;
        if (result.verb == L"PING") {
            result.reason = L"pong";
        } else if (result.verb == L"STATUS") {
            result.reason = L"status_written";
        } else if (result.verb == L"VERSION") {
            result.reason = L"version_reported";
        } else {
            result.reason = L"safe_commands_ping_status_version_help";
        }
    } else if (IsFutureCommand(result.verb)) {
        result.accepted = false;
        result.reason = result.actor_whitelisted ? L"recognized_future_command_whitelisted_actor_but_disabled_in_pass_0_3"
                                                  : L"recognized_future_command_disabled_or_actor_not_whitelisted_in_pass_0_3";
    } else {
        result.accepted = false;
        result.reason = L"unknown_command";
    }

    return result;
}

std::vector<CommandResult> ReadCommands(RuntimeState& state, bool& commandFileFound, bool& commandLimitReached) {
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

        if (commands.size() >= kMaxCommandsPerPoll) {
            commandLimitReached = true;
            break;
        }
        commands.push_back(ParseCommandLine(trimmed, state));
    }

    return commands;
}

void WriteStatusJson(
    const RuntimeState& state,
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
    out << L"  \"poll_interval_ms\": " << kPollIntervalMs << L",\n";
    out << L"  \"poll_count\": " << state.poll_count << L",\n";
    out << L"  \"commands_seen_this_poll\": " << commands.size() << L",\n";
    out << L"  \"processed_command_id_count\": " << state.processed_command_ids.size() << L",\n";
    out << L"  \"total_new_commands\": " << state.total_new_commands << L",\n";
    out << L"  \"total_skipped_duplicates\": " << state.total_skipped_duplicates << L",\n";
    out << L"  \"safety\": {\n";
    out << L"    \"hooks_installed\": false,\n";
    out << L"    \"memory_patches_applied\": false,\n";
    out << L"    \"game_files_modified\": false,\n";
    out << L"    \"actor_spawning_enabled\": false,\n";
    out << L"    \"future_commands_blocked\": true,\n";
    out << L"    \"actor_whitelist_enforced\": true\n";
    out << L"  },\n";
    out << L"  \"actor_whitelist\": [\n";
    out << L"    \"ACTOR_CAUCASIAN_ARMY_Easy01\",\n";
    out << L"    \"AE_CAUCASIAN_ARMY_EASY01\",\n";
    out << L"    \"ACTOR_CAUCASIAN_MALE_TownFolk02\",\n";
    out << L"    \"ACTOR_RIDEABLE_ANIMAL_Horse01\",\n";
    out << L"    \"ACTOR_RIDEABLE_ANIMAL_MEX_Mule01\",\n";
    out << L"    \"ACTOR_VEHICLE_Car01\",\n";
    out << L"    \"ACTOR_VEHICLE_Truck01\",\n";
    out << L"    \"ACTOR_VEHICLE_Stagecoach\",\n";
    out << L"    \"ACTOR_VEHICLE_Wagon02\",\n";
    out << L"    \"ACTOR_VEHICLE_Coach01\"\n";
    out << L"  ],\n";
    out << L"  \"commands\": [\n";

    for (std::size_t i = 0; i < commands.size(); ++i) {
        const auto& command = commands[i];
        out << L"    {\n";
        out << L"      \"raw\": \"" << JsonEscape(command.raw) << L"\",\n";
        out << L"      \"command_id\": \"" << JsonEscape(command.command_id) << L"\",\n";
        out << L"      \"explicit_id\": " << JsonBool(command.explicit_id) << L",\n";
        out << L"      \"skipped_duplicate\": " << JsonBool(command.skipped_duplicate) << L",\n";
        out << L"      \"verb\": \"" << JsonEscape(command.verb) << L"\",\n";
        out << L"      \"args\": \"" << JsonEscape(command.args) << L"\",\n";
        out << L"      \"actor_candidate\": \"" << JsonEscape(command.actor_candidate) << L"\",\n";
        out << L"      \"actor_whitelisted\": " << JsonBool(command.actor_whitelisted) << L",\n";
        out << L"      \"accepted\": " << JsonBool(command.accepted) << L",\n";
        out << L"      \"action\": \"" << JsonEscape(command.action) << L"\",\n";
        out << L"      \"reason\": \"" << JsonEscape(command.reason) << L"\"\n";
        out << L"    }" << (i + 1 < commands.size() ? L"," : L"") << L"\n";
    }

    out << L"  ]\n";
    out << L"}\n";
}

void LogNewCommands(const std::vector<CommandResult>& commands) {
    for (const auto& command : commands) {
        if (command.skipped_duplicate) {
            continue;
        }
        AppendLogLine(L"Command " + command.command_id + L" verb=" + command.verb + L" accepted=" +
                      BoolText(command.accepted) + L" reason=" + command.reason);
    }
}

void PollingWorker() {
    std::this_thread::sleep_for(std::chrono::milliseconds(kInitialDelayMs));

    RuntimeState state{};
    const auto modulePath = GetModulePath(g_module);
    const auto processPath = GetProcessPath();

    AppendLogLine(std::wstring(kPluginName) + L" polling/id/whitelist proof started.");
    AppendLogLine(L"Version: " + std::wstring(kPluginVersion));
    AppendLogLine(L"Plugin path: " + modulePath.wstring());
    AppendLogLine(L"Host process: " + processPath.wstring());
    AppendLogLine(L"Command file: " + GetCommandPath().wstring());
    AppendLogLine(L"Poll interval ms: " + std::to_wstring(kPollIntervalMs));
    AppendLogLine(L"Hooks installed: false");
    AppendLogLine(L"Memory patches applied: false");
    AppendLogLine(L"Game files modified: false");
    AppendLogLine(L"Actor spawning enabled: false");

    while (!g_shutdown.load()) {
        ++state.poll_count;

        bool commandFileFound = false;
        bool commandLimitReached = false;
        const auto commands = ReadCommands(state, commandFileFound, commandLimitReached);

        WriteStatusJson(state, modulePath, processPath, commandFileFound, commandLimitReached, commands);
        LogNewCommands(commands);

        const DWORD sliceMs = 250;
        DWORD waited = 0;
        while (!g_shutdown.load() && waited < kPollIntervalMs) {
            Sleep(sliceMs);
            waited += sliceMs;
        }
    }

    AppendLogLine(std::wstring(kPluginName) + L" polling worker shutting down.");
}

DWORD WINAPI ThreadProc(LPVOID) {
    try {
        PollingWorker();
    } catch (...) {
        // Never allow proof diagnostics to destabilize the host process.
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
        g_shutdown.store(false);
        DisableThreadLibraryCalls(module);
        StartWorkerThread();
    } else if (reason == DLL_PROCESS_DETACH) {
        g_shutdown.store(true);
    }
    return TRUE;
}
