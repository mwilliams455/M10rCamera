#pragma once
// RENDER1R TONECAL1A. Empirical post-output lightness calibration, NOT firmware Y BLEND.
// Fit: Photography Blog M10-R scenes 01/03/05 neutral patches only, equal scene weights.
// Post-quantization by design: the input is the unchanged RENDER1Q 8-bit publication.
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
namespace m10r_tonecal1a {
constexpr double B0=-3.229545380578171;
constexpr double B1=-0.25128474545011054;
constexpr double B2=-0.17860038493017244;
inline double correctedLightness(double L) {
    const double t=std::max(0.0,std::min(1.0,L/100.0));
    return L+4.0*t*(1.0-t)*(B0+B1*(2.0*t-1.0)+B2*(6.0*t*t-6.0*t+1.0));
}
inline const std::array<double,256>& linearTable() {
    static const std::array<double,256> table=[] {
        std::array<double,256> t{};
        for (int i=0;i<256;++i) { const double x=i/255.0;
            t[i]=x<=0.04045 ? x/12.92 : std::pow((x+0.055)/1.055,2.4); }
        return t;
    }();
    return table;
}
inline double labF(double x) {
    return x>216.0/24389.0 ? std::cbrt(x) : (24389.0/27.0*x+16.0)/116.0;
}
inline double invLabF(double x) {
    return x>6.0/29.0 ? x*x*x : (116.0*x-16.0)/(24389.0/27.0);
}
inline uint32_t encode(double x) {
    x=std::max(0.0,std::min(1.0,x));
    const double v=x<=0.0031308 ? 12.92*x : 1.055*std::pow(x,1.0/2.4)-0.055;
    return static_cast<uint32_t>(std::max(0.0,std::min(255.0,std::floor(v*255.0+0.5))));
}
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
