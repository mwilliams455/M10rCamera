#pragma once
#include <algorithm>
#include <cmath>

// Empirical output safety candidate, NOT recovered Leica ISP arithmetic.
// Input is the existing post-CC1 direct-output coordinate, not asserted linear light.
// Preserve clipped-baseline code-luma and unbounded RGB opponent direction.
// This is NOT perceptual-hue or CIELAB-lightness preservation.
namespace m10r_outputgamut1a {
inline double bounded(double x) {
    if (!std::isfinite(x)) return 0.0; // matches legacy linear8 nonfinite policy
    return std::max(0.0, std::min(1.0, x));
}
inline double luma(double r, double g, double b) {
    return 0.2126*r + 0.7152*g + 0.0722*b;
}
// Returns 0=exact in-gamut bypass; 1=finite gamut projection; 2=nonfinite fallback.
inline int apply(double& r, double& g, double& b) {
    if (!std::isfinite(r) || !std::isfinite(g) || !std::isfinite(b)) {
        r=bounded(r); g=bounded(g); b=bounded(b); return 2;
    }
    if (r>=0.0 && r<=1.0 && g>=0.0 && g<=1.0 && b>=0.0 && b<=1.0) return 0;
    const double anchor=bounded(luma(bounded(r),bounded(g),bounded(b)));
    // Normalize before centering so even extreme finite input cannot overflow.
    const double magnitude=std::max(1.0,std::max(std::abs(r),std::max(std::abs(g),std::abs(b))));
    const double nr=r/magnitude, ng=g/magnitude, nb=b/magnitude;
    const double y=luma(nr,ng,nb);
    const double d[3]={nr-y,ng-y,nb-y};
    double scale=magnitude;
    for (double v:d) {
        if (v>0.0) scale=std::min(scale,(1.0-anchor)/v);
        else if (v<0.0) scale=std::min(scale,-anchor/v);
    }
    scale=std::max(0.0,scale);
    r=bounded(anchor+scale*d[0]);
    g=bounded(anchor+scale*d[1]);
    b=bounded(anchor+scale*d[2]);
    return 1;
}
} // namespace m10r_outputgamut1a
