// Arithmetic support for statically translated M10-R metering functions.
// No instruction decoder, executable firmware, or dynamic code execution.
#pragma once
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <limits>
#include <stdexcept>
#include <vector>

namespace m10r {
constexpr uint32_t ram = 0x50000000u;
constexpr uint32_t work = ram + 0x100u;
constexpr uint32_t regions = ram + 0x400u;
constexpr uint32_t stack = ram + 0x1f00u;
constexpr uint32_t table_address = 0x400138bcu;
extern const uint8_t tables[113];

inline int32_t signed32(uint32_t x) {
    return x < 0x80000000u ? int32_t(x) : int32_t(int64_t(x) - 0x100000000ll);
}
inline int32_t signed16(uint32_t x) {
    x &= 65535u;
    return x < 32768u ? int32_t(x) : int32_t(x) - 65536;
}
inline uint32_t asr(uint32_t x, unsigned n) {
    if (!n) return x;
    if (n >= 32) return (x >> 31) ? 0xffffffffu : 0u;
    return (x >> n) | ((x >> 31) ? (0xffffffffu << (32-n)) : 0u);
}
inline uint32_t lsr(uint32_t x, unsigned n) { return n < 32 ? x >> n : 0u; }
inline uint32_t lsl(uint32_t x, unsigned n) { return n < 32 ? x << n : 0u; }
inline uint32_t to_u32(double x) {
    if (std::isnan(x) || x <= 0) return 0;
    if (x >= 4294967295.0) return 0xffffffffu;
    return uint32_t(x);
}
inline uint32_t to_s32(double x) {
    if (std::isnan(x)) return 0;
    if (x >= 2147483647.0) return 0x7fffffffu;
    if (x <= -2147483648.0) return 0x80000000u;
    return uint32_t(int32_t(x));
}

struct State {
    std::array<uint32_t,16> r{};
    std::array<uint64_t,32> d{};
    std::array<uint8_t,8192> memory{};
    bool n=false, z=false, c=false, v=false;
    uint32_t budget=200000;
    bool tracing=false;
    std::vector<uint32_t> trace;
    void hit(uint32_t address) {
        if (!budget--) throw std::runtime_error("instruction budget");
        if (tracing) trace.push_back(address);
    }
    void nz(uint32_t x) { n=bool(x>>31); z=(x==0); }
    uint32_t add(uint32_t a, uint32_t b, bool flags=false, uint32_t carry=0) {
        const uint64_t sum=uint64_t(a)+b+carry;
        const uint32_t out=uint32_t(sum);
        if (flags) { nz(out); c=bool(sum>>32); v=bool((~(a^b)&(a^out))>>31); }
        return out;
    }
    uint32_t sub(uint32_t a, uint32_t b, bool flags=false) {
        const uint32_t out=a-b;
        if (flags) { nz(out); c=a>=b; v=bool(((a^b)&(a^out))>>31); }
        return out;
    }
    uint32_t logical(uint32_t x, bool carry) { nz(x); c=carry; return x; }
    uint32_t read(uint32_t address, unsigned size) const {
        if (address>=table_address && uint64_t(address)+size<=table_address+113) {
            uint32_t out=0;
            for (unsigned i=0;i<size;i++) out|=uint32_t(tables[address-table_address+i])<<(8*i);
            return out;
        }
        if (address<ram || uint64_t(address)+size>ram+memory.size())
            throw std::runtime_error("read outside bounded scratch");
        uint32_t out=0;
        for (unsigned i=0;i<size;i++) out|=uint32_t(memory[address-ram+i])<<(8*i);
        return out;
    }
    void write(uint32_t address, uint32_t value, unsigned size) {
        if (address<ram || uint64_t(address)+size>ram+memory.size())
            throw std::runtime_error("write outside bounded scratch");
        for (unsigned i=0;i<size;i++) memory[address-ram+i]=uint8_t(value>>(8*i));
    }
    uint32_t single(unsigned i) const { return uint32_t(d[i/2]>>((i%2)*32)); }
    void single(unsigned i,uint32_t x) {
        unsigned shift=(i%2)*32;
        d[i/2]=(d[i/2]&~(uint64_t(0xffffffffu)<<shift)) | (uint64_t(x)<<shift);
    }
    double number(unsigned i) const { double x; std::memcpy(&x,&d[i],8); return x; }
    void number(unsigned i,double x) { std::memcpy(&d[i],&x,8); }
};
static_assert(sizeof(double)==8 && std::numeric_limits<double>::is_iec559,
              "IEEE binary64 is required");
void block_mean(State&);
void confidence_ramp(State&);
void quantized_line(State&);
void feature_engine(State&);
void aggregate_engine(State&);
void signed_division(State&);
} // namespace m10r
