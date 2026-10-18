#include "m10r_metering.h"
#include "translation_runtime.hpp"
#include <algorithm>
#include <utility>

namespace {
thread_local bool trace_enabled=false;
thread_local std::vector<uint32_t> last_trace;
bool fits16(int32_t x) { return x>=-32768 && x<=32767; }
void init(m10r::State& s) {
    s.r[13]=m10r::stack;
    s.r[14]=0;
    s.tracing=trace_enabled;
    last_trace.clear();
}
void capture(m10r::State& s) { if (s.tracing) last_trace=std::move(s.trace); }
}

extern "C" int m10r_meter(const M10RMeterInput* in, M10RMeterOutput* out) {
    if (!in || !out || !fits16(in->baseline_q8) || !fits16(in->offset_q8) ||
        !fits16(in->sub_av_q8) || !fits16(in->sub_tv_q8) || !fits16(in->add_sv_q8) ||
        in->fpos>65535u || in->tilt>3u) return -1;
    for (auto value:in->regions_q8) if (!fits16(value)) return -1;
    m10r::State s; init(s);
    try {
        for (unsigned i=0;i<24;i++) s.write(m10r::regions+2*i,uint32_t(in->regions_q8[i]),2);
        s.write(m10r::work+0x16c,in->fpos,2);
        s.write(m10r::work+0x18d,in->tilt,1);
        s.r[0]=uint32_t(in->baseline_q8);s.r[1]=m10r::regions;
        s.r[2]=uint32_t(in->offset_q8);s.r[3]=uint32_t(in->sub_av_q8);
        s.write(m10r::stack,uint32_t(in->sub_tv_q8),4);
        s.write(m10r::stack+4,uint32_t(in->add_sv_q8),4);
        s.write(m10r::stack+8,m10r::work,4);
        m10r::aggregate_engine(s);
        M10RMeterOutput result{};
        result.result_q8=m10r::signed32(s.r[0]);
        std::memcpy(result.work,s.memory.data()+m10r::work-m10r::ram,400);
        *out=result; capture(s); return 0;
    } catch (...) { capture(s); return -2; }
}

extern "C" int m10r_features(const uint8_t* in, uint8_t* out) {
    if (!in || !out) return -1;
    for (unsigned i=0x173;i<0x180;i++) if (in[i]>1) return -1;
    if (in[0x18d]>3) return -1;
    m10r::State s; init(s);
    try {
        std::memcpy(s.memory.data()+m10r::work-m10r::ram,in,400);
        s.r[0]=m10r::work+0x173;s.r[1]=m10r::work;
        m10r::feature_engine(s);
        std::memcpy(out,s.memory.data()+m10r::work-m10r::ram,400);
        capture(s); return 0;
    } catch (...) { capture(s); return -2; }
}

extern "C" void m10r_trace_enable(int enabled) { trace_enabled=enabled!=0; }
extern "C" size_t m10r_trace_copy(uint32_t* addresses,size_t capacity) {
    if (addresses) std::copy_n(last_trace.data(),std::min(capacity,last_trace.size()),addresses);
    return last_trace.size();
}
