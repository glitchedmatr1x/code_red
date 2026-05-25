#include "RuntimeLogger.h"
#include <chrono>
#include <iomanip>
#include <sstream>

namespace codered {

RuntimeLogger::RuntimeLogger(std::size_t maxEntries) : maxEntries_(maxEntries) {}

bool RuntimeLogger::openFile(const std::string& path) {
    file_.open(path, std::ios::out | std::ios::app);
    return file_.good();
}

static std::string timestamp() {
    using clock = std::chrono::system_clock;
    auto now = clock::now();
    auto tt = clock::to_time_t(now);
    std::tm tm{};
#if defined(_WIN32)
    localtime_s(&tm, &tt);
#else
    localtime_r(&tt, &tm);
#endif
    std::ostringstream oss;
    oss << std::put_time(&tm, "%Y-%m-%d %H:%M:%S");
    return oss.str();
}

void RuntimeLogger::log(const std::string& line) {
    std::string out = "[" + timestamp() + "] " + line;
    entries_.push_back(out);
    while (entries_.size() > maxEntries_) entries_.pop_front();
    if (file_.is_open()) {
        file_ << out << "\n";
        file_.flush();
    }
}

std::vector<std::string> RuntimeLogger::recent() const {
    return std::vector<std::string>(entries_.begin(), entries_.end());
}

std::string RuntimeLogger::joinedRecent(const char* sep) const {
    std::ostringstream oss;
    for (std::size_t i = 0; i < entries_.size(); ++i) {
        if (i) oss << sep;
        oss << entries_[i];
    }
    return oss.str();
}

} // namespace codered
