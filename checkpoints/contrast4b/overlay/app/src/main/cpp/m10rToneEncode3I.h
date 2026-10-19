#pragma once
#include "m10rToneCal1A.h"
#include <cstring>
#include <limits>

// Preserve the original quantizer's transitions on this runtime. Bucket seeds
// only narrow the search; exact double thresholds decide the final output.
namespace m10r_toneencode3i {
inline double fromBits(uint64_t bits) {
    double value; std::memcpy(&value, &bits, sizeof(value)); return value;
}
struct Tables {
    std::array<double,255> threshold{};
    std::array<uint8_t,4096> seed{};
    bool valid = std::numeric_limits<double>::is_iec559 && sizeof(double)==8;
    Tables() {
        if (!valid) return;
        for (uint32_t code=1; code<=255; ++code) {
            uint64_t lo=0, hi=0x3ff0000000000000ULL;
            while (lo<hi) {
                const uint64_t mid=lo+(hi-lo)/2;
                if (m10r_tonecal1a::encode(fromBits(mid))>=code) hi=mid;
                else lo=mid+1;
            }
            threshold[code-1]=fromBits(lo);
            valid = valid && lo>0 && m10r_tonecal1a::encode(fromBits(lo-1))==code-1
                && m10r_tonecal1a::encode(fromBits(lo))==code
                && (code==1 || threshold[code-2]<threshold[code-1]);
        }
        for (size_t i=0;i<seed.size();++i)
            seed[i]=static_cast<uint8_t>(m10r_tonecal1a::encode(i/4096.0));
    }
};
inline const Tables& tables() { static const Tables t; return t; }
inline uint32_t encode(double x) {
    const auto& t=tables();
    if (!t.valid) return m10r_tonecal1a::encode(x);
    // Same ordering also preserves the reference NaN and infinity behavior.
    x=std::max(0.0,std::min(1.0,x));
    const uint32_t bucket=std::min(4095u,static_cast<uint32_t>(x*4096.0));
    uint32_t code=t.seed[bucket];
    while (code<255 && x>=t.threshold[code]) ++code;
    while (code>0 && x<t.threshold[code-1]) --code;
    return code;
}
using m10r_tonecal1a::linearTable;
using m10r_tonecal1a::labF;
using m10r_tonecal1a::invLabF;
using m10r_tonecal1a::correctedLightness;
inline uint32_t apply(uint32_t argb) {
    const uint32_t r=(argb>>16)&255u,g=(argb>>8)&255u,b=argb&255u;
    const auto& lut=linearTable();
    const double R=lut[r],G=lut[g],B=lut[b];
    const double Y=0.212671*R+0.715160*G+0.072169*B;
    const double fy=labF(Y),L=116.0*fy-16.0;
    const double delta=(correctedLightness(L)-L)/116.0;
    // Preserve exact black, white and achromatic equality; no neutral tint is introduced.
    if (r==g && g==b) {
        const uint32_t v=encode(invLabF(fy+delta));
        return (argb&0xff000000u)|(v<<16)|(v<<8)|v;
    }
    const double fx=labF((0.412453*R+0.357580*G+0.180423*B)/0.950456);
    const double fz=labF((0.019334*R+0.119193*G+0.950227*B)/1.088754);
    const double X1=0.950456*invLabF(fx+delta),Y1=invLabF(fy+delta),Z1=1.088754*invLabF(fz+delta);
    // Exact inverse (to the displayed precision) of the above RGB->XYZ matrix.
    const double rr=3.240481343200527*X1-1.537151516271318*Y1-0.498536326168887*Z1;
    const double gg=-0.969254949996569*X1+1.875990001489891*Y1+0.041555926558293*Z1;
    const double bb=0.055646639135177*X1-0.204041338366511*Y1+1.057311069645344*Z1;
    return (argb&0xff000000u)|(encode(rr)<<16)|(encode(gg)<<8)|encode(bb);
}
}
