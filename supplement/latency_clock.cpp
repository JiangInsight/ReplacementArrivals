
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <numeric>
#include <vector>

int main() {
    using Clock = std::chrono::steady_clock;
    constexpr int samples = 1000000;
    std::vector<std::int64_t> ns(samples);
    for (auto& interval : ns) {
        const auto start = Clock::now();
        const auto end = Clock::now();
        interval = std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();
    }
    std::sort(ns.begin(), ns.end());
    const auto zeros = std::upper_bound(ns.begin(), ns.end(), 0);
    std::cout << "{\"n\":" << samples << ",\"zero\":" << (zeros - ns.begin())
              << ",\"min_positive_ns\":" << (zeros == ns.end() ? 0 : *zeros)
              << ",\"median_ns\":" << ns[samples / 2] << ",\"p99_ns\":" << ns[samples * 99 / 100]
              << ",\"mean_ns\":" << std::accumulate(ns.begin(), ns.end(), 0.0) / samples
              << ",\"max_ns\":" << ns.back() << "}\n";
}
