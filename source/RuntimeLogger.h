#pragma once
#include <deque>
#include <fstream>
#include <string>
#include <vector>

namespace codered {

class RuntimeLogger {
public:
    explicit RuntimeLogger(std::size_t maxEntries = 128);
    bool openFile(const std::string& path);
    void log(const std::string& line);
    std::vector<std::string> recent() const;
    std::string joinedRecent(const char* sep = "\n") const;

private:
    std::size_t maxEntries_ = 128;
    std::deque<std::string> entries_;
    std::ofstream file_;
};

} // namespace codered
