#pragma once
#include "m10rToneEncode3I.h"
#include <array>
#include <cstdint>

// Exact memoization of the existing post-quantization function. Collisions
// recompute TONECAL1A with the exact encoder; no interpolation or new quantization.
// Each worker owns its cache for one band. Alpha is independent of the RGB key.
namespace m10r_tonecache3i {
#ifndef M10R_TONECACHE3H_BITS
#define M10R_TONECACHE3H_BITS 14
#endif
class Cache {
    struct Entry { uint32_t key = 0, value = 0; };
    std::array<Entry, (1u << M10R_TONECACHE3H_BITS)> entries_{};
public:
    uint64_t hits = 0, misses = 0;
    static constexpr uint32_t bytes = (1u << M10R_TONECACHE3H_BITS) * sizeof(Entry);
    uint32_t apply(uint32_t argb) {
        const uint32_t rgb = argb & 0x00ffffffu;
        const uint32_t key = rgb | 0x01000000u; // nonzero validity tag
        const uint32_t slot = (rgb * 2654435761u) >> (32 - M10R_TONECACHE3H_BITS);
        Entry& entry = entries_[slot];
        if (entry.key == key) {
            ++hits;
            return (argb & 0xff000000u) | entry.value;
        }
        ++misses;
        const uint32_t result = m10r_toneencode3i::apply(argb);
        entry.key = key;
        entry.value = result & 0x00ffffffu;
        return result;
    }
};
}
