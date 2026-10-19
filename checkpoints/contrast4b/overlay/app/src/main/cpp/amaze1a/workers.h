// PREVIEW1B: independent bounded workers, without a second OpenMP runtime.
#pragma once
#include <exception>
#include <mutex>
#include <stdexcept>
#include <thread>
#include <vector>

namespace m10r_amaze1a {
template<class Work>
void runWorkers(int count, Work work) {
    if (count < 1 || count > 8) throw std::invalid_argument("AMaZE worker count");
    std::vector<std::thread> threads;
    threads.reserve(count - 1);
    std::exception_ptr failure;
    std::mutex failureMutex;
    // Joining during unwinding also covers a failure to create a later worker.
    struct Join {
        std::vector<std::thread>& threads;
        ~Join() { for (auto& thread : threads) if (thread.joinable()) thread.join(); }
    } join{threads};
    auto guarded = [&] {
        try { work(); }
        catch (...) {
            std::lock_guard<std::mutex> lock(failureMutex);
            if (!failure) failure = std::current_exception();
        }
    };
    for (int i = 1; i < count; ++i) threads.emplace_back(guarded);
    guarded();
    for (auto& thread : threads) thread.join();
    if (failure) std::rethrow_exception(failure);
}
}
