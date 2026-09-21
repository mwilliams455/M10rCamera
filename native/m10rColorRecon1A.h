#pragma once
// Empirical COLORRECON1A. This is not recovered Leica Y BLEND arithmetic.
// Reconstruct colour from the pre-tone working RGB, transformed by CC1 in
// linear light. Retain S's floating output lightness as an anchor; constrain
// the gain with a continuous saturation-dependent highlight shoulder.
// Width 0.30 is an empirical engineering choice, not firmware-derived.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include "m10rOutputGamut1A.h"
namespace m10r_colorrecon1a {
inline double decode(double x) {
    return x<=0.04045 ? x/12.92 : std::pow((x+0.055)/1.055,2.4);
}
inline double encode(double x) {
    return x<=0.0031308 ? 12.92*x : 1.055*std::pow(x,1.0/2.4)-0.055;
}
// Flags: bit0 peak limited; bit1 nonfinite fallback; bit2 peak input >1.
inline unsigned apply(double lr,double lg,double lb,const double* matrix,
                      double oldR,double oldG,double oldB,
                      const int* tone,const int* table,
                      double& r,double& g,double& b) {
    double ar=oldR,ag=oldG,ab=oldB;
    m10r_outputgamut1a::apply(ar,ag,ab);
    const double cr=matrix[0]*lr+matrix[1]*lg+matrix[2]*lb;
    const double cg=matrix[3]*lr+matrix[4]*lg+matrix[5]*lb;
    const double cb=matrix[6]*lr+matrix[7]*lg+matrix[8]*lb;
    const double lum=0.2126*cr+0.7152*cg+0.0722*cb;
    const double peak=std::max(cr,std::max(cg,cb));
    if(!std::isfinite(oldR)||!std::isfinite(oldG)||!std::isfinite(oldB)||!std::isfinite(cr)||!std::isfinite(cg)||!std::isfinite(cb)||!std::isfinite(lum)) {
        r=ar;g=ag;b=ab;return 2;
    }
    // Exact achromatic working input retains the established S neutral curve.
    if(lr==lg && lg==lb) {r=ar;g=ag;b=ab;return peak>1.0?4u:0u;}
    const double anchor=0.2126*decode(ar)+0.7152*decode(ag)+0.0722*decode(ab);
    const double requested=anchor/std::max(1.0e-12,lum);
    const double positivePeak=std::max(1.0e-12,peak);
    const double saturation=std::max(0.0,std::min(1.0,
            (positivePeak-std::min(cr,std::min(cg,cb)))/positivePeak));
    const double width=0.30*saturation;
    const double knee=1.0-width;
    const double requestedPeak=encode(std::max(0.0,positivePeak*requested));
    double peakCode=requestedPeak;
    if(requestedPeak>knee) {
        const double above=requestedPeak-knee;
        peakCode=knee+width*above/std::max(1.0e-12,above+width);
    }
    const double ceiling=decode(peakCode)/positivePeak;
    const double gain=std::min(requested,ceiling);
    r=encode(cr*gain);g=encode(cg*gain);b=encode(cb*gain);
    if(!std::isfinite(r)||!std::isfinite(g)||!std::isfinite(b)) {r=ar;g=ag;b=ab;return 2;}
    return (ceiling<requested?1u:0u)|(peak>1.0?4u:0u);
}
}
