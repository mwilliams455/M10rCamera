#pragma once
// WARMRED1B — bounded empirical warm-highlight red-peak treatment.
//
// This is NOT recovered Leica firmware arithmetic.
// It is the public-reference-screened warm075_red085 candidate:
//   mappedY >= 0.75
//   mappedCr/mappedY >= 0.04
//   pre-tone CC1 colour direction is red-peak
//   requested red sRGB code > 0.85
//
// Non-selected pixels are untouched by the caller. Selected pixels preserve
// the established RENDER1T linear lightness anchor exactly and scale only the
// opponent vector around that neutral anchor.
#include <algorithm>
#include <cmath>
#include "m10rColorRecon1A.h"
#include "m10rOutputGamut1A.h"

namespace m10r_warmred1b {

constexpr double MIN_MAPPED_Y = 0.75;
constexpr double MIN_REL_CR = 0.04;
constexpr double RED_KNEE = 0.85;
constexpr double RED_WIDTH = 1.0 - RED_KNEE;
constexpr double MIN_LUM = 1.0e-6;
constexpr double MIN_RED_OPPONENT = 1.0e-9;

struct Trace {
    bool applied=false;
    double mappedY=0.0;
    double relCr=0.0;
    double anchor=0.0;
    double requested=0.0;
    double redCode=0.0;
    double targetRedLinear=0.0;
    double opponentScale=1.0;
    double lumaError=0.0;
};

inline bool apply(double lr,double lg,double lb,const double* matrix,
                  double oldR,double oldG,double oldB,
                  double mappedY,double mappedCr,
                  double& r,double& g,double& b,
                  Trace* trace=nullptr) {
    if(!(mappedY>=MIN_MAPPED_Y) || !std::isfinite(mappedY) ||
       !std::isfinite(mappedCr) || !(std::abs(mappedY)>1.0e-12)) {
        return false;
    }
    const double relCr=mappedCr/mappedY;
    if(!(relCr>=MIN_REL_CR) || !std::isfinite(relCr)) return false;

    // Preserve COLORRECON1A's exact neutral invariant.
    if(lr==lg && lg==lb) return false;

    const double cr=matrix[0]*lr+matrix[1]*lg+matrix[2]*lb;
    const double cg=matrix[3]*lr+matrix[4]*lg+matrix[5]*lb;
    const double cb=matrix[6]*lr+matrix[7]*lg+matrix[8]*lb;
    if(!std::isfinite(cr)||!std::isfinite(cg)||!std::isfinite(cb)) return false;
    if(!(cr>=cg && cr>=cb)) return false;

    double ar=oldR,ag=oldG,ab=oldB;
    m10r_outputgamut1a::apply(ar,ag,ab);
    if(!std::isfinite(ar)||!std::isfinite(ag)||!std::isfinite(ab)) return false;

    const double anchor=
            0.2126*m10r_colorrecon1a::decode(ar)+
            0.7152*m10r_colorrecon1a::decode(ag)+
            0.0722*m10r_colorrecon1a::decode(ab);
    const double lum=0.2126*cr+0.7152*cg+0.0722*cb;
    if(!std::isfinite(anchor)||!std::isfinite(lum)||!(lum>MIN_LUM)) return false;

    const double requested=anchor/lum;
    const double rr=cr*requested;
    const double gg=cg*requested;
    const double bb=cb*requested;
    if(!std::isfinite(rr)||!std::isfinite(gg)||!std::isfinite(bb)) return false;

    const double redCode=m10r_colorrecon1a::encode(std::max(0.0,rr));
    if(!std::isfinite(redCode)||!(redCode>RED_KNEE)) return false;

    const double above=redCode-RED_KNEE;
    const double soft=RED_KNEE+
            RED_WIDTH*above/std::max(1.0e-12,above+RED_WIDTH);
    const double targetRed=m10r_colorrecon1a::decode(soft);
    const double dr=rr-anchor;
    if(!std::isfinite(targetRed)||!(dr>MIN_RED_OPPONENT)) return false;

    const double scale=std::max(0.0,std::min(1.0,(targetRed-anchor)/dr));
    const double orr=anchor+scale*(rr-anchor);
    const double ogg=anchor+scale*(gg-anchor);
    const double obb=anchor+scale*(bb-anchor);
    if(!std::isfinite(orr)||!std::isfinite(ogg)||!std::isfinite(obb)) return false;

    const double encodedR=m10r_colorrecon1a::encode(orr);
    const double encodedG=m10r_colorrecon1a::encode(ogg);
    const double encodedB=m10r_colorrecon1a::encode(obb);
    if(!std::isfinite(encodedR)||!std::isfinite(encodedG)||!std::isfinite(encodedB)) return false;

    r=encodedR; g=encodedG; b=encodedB;

    if(trace) {
        trace->applied=true;
        trace->mappedY=mappedY;
        trace->relCr=relCr;
        trace->anchor=anchor;
        trace->requested=requested;
        trace->redCode=redCode;
        trace->targetRedLinear=targetRed;
        trace->opponentScale=scale;
        trace->lumaError=(0.2126*orr+0.7152*ogg+0.0722*obb)-anchor;
    }
    return true;
}

} // namespace m10r_warmred1b
