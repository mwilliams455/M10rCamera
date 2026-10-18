#include "m10r_statistics.h"
#include "translation_runtime.hpp"
#include "statistics_tables.hpp"

namespace {
double number(uint64_t bits) { double x; std::memcpy(&x,&bits,8); return x; }
bool fits16(int32_t x) { return x>=-32768 && x<=32767; }
// 0x40012a4a, coefficients read in descending order, non-fused VMLA.
template<size_t N> double polynomial(double x,const uint64_t (&bits)[N]) {
    double result=number(bits[N-1]);
    for(size_t i=N-1;i>0;--i) result=number(bits[i-1])+result*x;
    return result;
}
M10RYResult evaluate(const M10RGridInput& in,unsigned row,unsigned col,
                     unsigned height,unsigned width,bool integral) {
    // 0x40000178: MUL wraps, ASR is signed, conversion at 0x240 is unsigned.
    const uint32_t normalizer=m10r::asr(in.step_a*in.step_b,2);
    uint64_t sum_y=0,sum_ref=0;double sum_weight=0;
    for(unsigned r=row;r<row+height;++r) for(unsigned c=col;c<col+width;++c) {
        const unsigned i=r*22+c;
        const double w=double(integral?integral_weights[i]:100u)/100.0;
        sum_weight+=w;
        // Both per-cell conversions truncate/saturate before accumulation.
        sum_y+=m10r::to_u32((double(in.y_sums[i])*w)/double(normalizer));
        sum_ref+=m10r::to_u32(524.0*w);
    }
    const uint32_t y=m10r::to_u32(double(sum_y)/sum_weight);
    const uint32_t ref=m10r::to_u32(double(sum_ref)/sum_weight);
    // The supported fixed masks and nonempty ROIs cannot have zero reference.
    const int32_t ev=y?m10r::signed16(m10r::to_s32(
        (m10r_statistics_log(double(y)/double(ref))/m10r_statistics_log(2.0))*256.0)):-2586;
    const int32_t bv=m10r::signed16(uint32_t(ev+in.tv_q8+in.av_q8-in.sv_q8+0x11a));
    return {y?0:-12,ev,bv,y,ref};
}
}

extern "C" double m10r_statistics_log(double x) {
    if(!std::isnormal(x)||x<=0) return std::numeric_limits<double>::quiet_NaN();
    // Original positive-normal path at 0x4001276c..0x400128de.
    uint64_t bits;std::memcpy(&bits,&x,8);
    uint32_t hi=uint32_t(bits>>32),mantissa=hi&0xfffffu;
    const uint32_t carry=(mantissa+0x95f64u)&0x100000u;
    const int32_t k=int32_t(hi>>20)-0x3ff+int32_t(carry>>20);
    hi=(carry^0x3ff00000u)|mantissa;
    const double f=number((uint64_t(hi)<<32)|(bits&0xffffffffu))-1.0;
    const double ln_hi=number(0x3fe62e42fee00000ull);
    const double ln_lo=number(0x3dea39ef35793c76ull);
    if(((mantissa+2u)&0xfffffu)<3u) {
        if(f==0.0) return k?double(k)*ln_hi+double(k)*ln_lo:0.0;
        double d=(f*f)*(0.5-f*number(0x3fd5555555555555ull));
        if(k==0) return f-d;
        d=d-double(k)*ln_lo;d=d-f;
        return double(k)*ln_hi-d;
    }
    const double s=f/(f+2.0),z=s*s,w=z*z;
    static constexpr uint64_t even[]={0x3fd999999997fa04ull,0x3fcc71c51d8e78afull,0x3fc39a09d078c69full};
    static constexpr uint64_t odd[]={0x3fe5555555555593ull,0x3fd2492494229359ull,0x3fc7466496cb03deull,0x3fc2f112df3e5244ull};
    const double t=polynomial(w,even)*w;
    double d1=polynomial(w,odd)*z+t;
    const int32_t branch=m10r::signed32((mantissa-0x6147au)|(0x6b851u-mantissa));
    if(branch>0) {
        double d0=(f*0.5)*f;d1=d0+d1;
        if(k==0) {d0=d0-s*d1;return f-d0;}
        d1=d1*s;d1=d1+double(k)*ln_lo;
        d0=d0-d1;d0=d0-f;return double(k)*ln_hi-d0;
    }
    if(k==0) return f-s*(f-d1);
    double d0=(f-d1)*s;d0=d0-double(k)*ln_lo;d0=d0-f;
    return double(k)*ln_hi-d0;
}

extern "C" int m10r_meter_grid(const M10RGridInput* in,M10RGridOutput* out) {
    if(!in||!out||!in->step_a||in->step_a>65535||!in->step_b||in->step_b>65535||
       in->step_a*in->step_b<4||!fits16(in->sv_q8)||!fits16(in->tv_q8)||
       !fits16(in->av_q8)||in->fpos>65535||in->tilt>3) return -1;
    M10RGridOutput result{};
    result.integral=evaluate(*in,0,0,16,22,true);
    M10RMeterInput meter{};
    meter.baseline_q8=m10r::signed16(uint32_t(result.integral.bv_q8+in->av_q8));
    meter.sub_av_q8=in->av_q8;meter.sub_tv_q8=in->tv_q8;meter.add_sv_q8=in->sv_q8;
    meter.fpos=in->fpos;meter.tilt=in->tilt;
    for(unsigned r=0;r<4;++r) for(unsigned c=0;c<6;++c) {
        const unsigned i=r*6+c;
        result.regions[i]=evaluate(*in,r*4,region_starts[c],4,region_widths[c],false);
        meter.regions_q8[i]=result.regions[i].bv_q8;
        if(result.regions[i].status) result.mfm_status=-12;
    }
    if(m10r_meter(&meter,&result.aggregate)!=0) return -2;
    result.mfm_bv_q8=m10r::signed16(uint32_t(result.aggregate.result_q8-in->av_q8));
    // Wrapper EV intentionally differs from the generic evaluator's EV.
    result.mfm_ev_q8=m10r::signed16(uint32_t(result.mfm_bv_q8+in->sv_q8-in->tv_q8));
    *out=result;return 0;
}
extern "C" uint32_t m10r_workflow_fpos(int32_t source) {
    if(source==0x7fffffff) return 0;
    const uint32_t narrowed=uint32_t(source/100)&65535u;
    return narrowed?narrowed:1;
}
extern "C" uint32_t m10r_workflow_tilt(int32_t angle) {
    // Original uses uint32 wrapping ADD/CMP, with all other angles -> 0.
    const uint32_t value=uint32_t(angle)+90u;
    return value==0?1:value==180?2:value==270?3:0;
}
