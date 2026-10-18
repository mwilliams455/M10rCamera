#include "m10rToneCache3H.h"
#include <chrono>
#include <iostream>
#include <vector>
#include <thread>
#include <stdexcept>
using Clock = std::chrono::steady_clock;
int main() {
    // Every possible RGB input; repeated lookups with different alpha verify
    // hit values, replacement collisions, and alpha preservation independently.
    m10r_tonecache3h::Cache cache;
    uint64_t checked = 0;
    auto start = Clock::now();
    for (uint32_t rgb=0; rgb<0x01000000u; ++rgb) {
        const uint32_t ref = m10r_tonecal1a::apply(0xff000000u | rgb) & 0x00ffffffu;
        const uint32_t a = (rgb * 37u) & 255u;
        const uint32_t input = (a<<24) | rgb;
        if (cache.apply(input) != ((a<<24)|ref)) return 1;
        const uint32_t input2 = ((255u-a)<<24) | rgb;
        if (cache.apply(input2) != (((255u-a)<<24)|ref)) return 2;
        checked += 2;
    }
    // Deliberately revisit colours after eviction and exercise independent workers.
    std::vector<std::thread> workers;
    std::array<uint64_t,4> failures{};
    for (int t=0;t<4;t++) workers.emplace_back([&,t] {
        m10r_tonecache3h::Cache local;
        uint32_t state=12345u+t;
        for (int i=0;i<250000;i++) {
            state=1664525u*state+1013904223u;
            if(local.apply(state)!=m10r_tonecal1a::apply(state)) failures[t]++;
        }
    });
    for(auto& thread:workers)thread.join();
    for(auto f:failures)if(f)return 3;
    std::cout << "{\"status\":\"PASS\",\"rgbInputsExhaustive\":16777216,\"alphaVariantComparisons\":" << checked
        << ",\"threadedRandomComparisons\":1000000,\"cacheBytesPerWorker\":" << cache.bytes
        << ",\"elapsedMs\":" << std::chrono::duration<double,std::milli>(Clock::now()-start).count() << "}\n";
}
