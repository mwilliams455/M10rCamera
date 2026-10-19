#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>

// Empirical, opt-in output-colour guard. Not a recovered Leica firmware stage
// and not an illuminant estimator. The caller decides whether it is enabled.
namespace m10r_tungsten3j {
constexpr double MAX_REDUCTION = 0.12;
inline double smooth(double lo, double hi, double x) {
    const double t = std::max(0.0, std::min(1.0, (x - lo) / (hi - lo)));
    return t * t * (3.0 - 2.0 * t);
}
inline uint32_t apply(uint32_t argb) {
    // Camera output is opaque. Leave other alpha values untouched: no changes
    // to premultiplied colours or transparent pixels in other callers.
    if ((argb >> 24) != 255u) return argb;
    const double r = (argb >> 16) & 255u, g = (argb >> 8) & 255u, b = argb & 255u;
    if (b >= r || b >= g) return argb; // blue/cyan/magenta and neutral bypass
    const double high = std::max(r, g), delta = high - b;
    if (high <= 0.0 || delta / high <= 0.06) return argb;
    // Hue in sixth-turns: red=0, yellow=1, green=2. Smooth edges prevent
    // a hard colour boundary. Red, green, cyan, blue and magenta are excluded.
    const double hue = r >= g ? (g - b) / delta : 2.0 + (b - r) / delta;
    if (hue <= 0.12 || hue >= 1.35) return argb;
    const double y = .2126*r + .7152*g + .0722*b; // encoded RGB luma, not linear luminance
    const double weight = smooth(.12, .35, hue) * (1.0 - smooth(1.05, 1.35, hue))
            * smooth(.06, .20, delta / high)
            * smooth(20.0, 60.0, y) * (1.0 - smooth(210.0, 250.0, y));
    const double amount = MAX_REDUCTION * weight;
    if (amount <= 0.0) return argb;
    // A convex blend toward equal-luma grey: preserves encoded luma before
    // rounding and cannot create a new channel extreme or recover lost detail.
    const auto channel = [=](double c) { return uint32_t(std::floor(c + amount*(y-c) + .5)); };
    return (argb & 0xff000000u) | (channel(r) << 16) | (channel(g) << 8) | channel(b);
}
// Shared Android/host row routine, including real RGBA byte order and stride.
// Padding and non-opaque pixels are never modified.
inline int64_t applyRgba(uint8_t* bytes, uint32_t width, uint32_t height, uint32_t stride) {
    if (!bytes || !width || !height || uint64_t(stride) < uint64_t(width)*4u) return -1;
    int64_t changed = 0;
    for (uint32_t row=0; row<height; ++row) {
        uint8_t* p = bytes + size_t(row)*stride;
        for (uint32_t col=0; col<width; ++col, p+=4) {
            const uint32_t before = (uint32_t(p[3])<<24) | (uint32_t(p[0])<<16) | (uint32_t(p[1])<<8) | p[2];
            const uint32_t after = apply(before);
            if (after != before) { p[0]=uint8_t(after>>16); p[1]=uint8_t(after>>8); p[2]=uint8_t(after); ++changed; }
        }
    }
    return changed;
}
}
