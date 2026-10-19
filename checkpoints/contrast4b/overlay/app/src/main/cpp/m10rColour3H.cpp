#include "m10rOutputGamut1A.h"
#include "m10rToneCal1A.h"
#include "m10rToneCache3H.h"
#include <chrono>
#include <array>
#include <jni.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <thread>
#include <vector>

namespace {
constexpr double ASN_SCALE = 256.0;
constexpr int INPUT_MAX = 0x3fff;
constexpr int TONE_ENTRIES = 10240;
constexpr int DG_INDEX_MAX = 0x7fff;
constexpr int DG_OUT_MAX = 0x3fff;
constexpr int THREADS = 4;

struct Counts {
    int64_t v[24] = {};
};

inline double ca9clip(double camera, int gain, Counts& c, int ch) {
    double balanced = camera * gain / ASN_SCALE;
    if (balanced > 1.0) { balanced = 1.0; c.v[ch]++; }
    if (balanced < 0.0) balanced = 0.0;
    return balanced * ASN_SCALE / gain;
}

inline int toneInput(double y, Counts& c) {
    if (!std::isfinite(y)) { c.v[5]++; return 0; }
    if (y < 0.0) { c.v[3]++; return 0; }
    if (y > 1.0) { c.v[4]++; return INPUT_MAX; }
    int q = static_cast<int>(std::floor(y * INPUT_MAX + 0.5));
    return std::max(0, std::min(INPUT_MAX, q));
}

inline int medium(int x, const jint* tone) {
    int xx = std::max(0, std::min(TONE_ENTRIES * 2 - 1, x));
    int64_t p = static_cast<int64_t>(xx) * static_cast<int64_t>(tone[xx >> 1]);
    return static_cast<int>(p >> 15);
}

inline int dg(int x, const jint* table, Counts& c) {
    int xx = x;
    if (xx < 0) { c.v[6]++; xx = 0; }
    else if (xx > DG_INDEX_MAX) { c.v[7]++; xx = DG_INDEX_MAX; }
    return table[xx];
}

inline int srgb8(double linear) {
    if (!std::isfinite(linear)) return 0;
    double c = std::max(0.0, std::min(1.0, linear));
    double e = c <= 0.0031308 ? 12.92*c : 1.055*std::pow(c, 1.0/2.4)-0.055;
    e = std::max(0.0, std::min(1.0, e));
    return static_cast<int>(std::floor(e * 255.0 + 0.5));
}

inline int linear8(double linear) {
    if (!std::isfinite(linear)) return 0;
    const double c = std::max(0.0, std::min(1.0, linear));
    return static_cast<int>(std::floor(c * 255.0 + 0.5));
}
}

extern "C" JNIEXPORT jboolean JNICALL
Java_com_particlesdevs_photoncamera_m10r_M10RColour3H_nativeProcessTile(
        JNIEnv* env, jclass,
        jshortArray jrgb, jint pixels, jdouble inverseStorageScale,
        jdoubleArray jsrc, jintArray jca9, jdoubleArray jworkingMat,
        jdoubleArray joutMat, jintArray jtone, jintArray jdg,
        jintArray jargb, jlongArray jcounts, jboolean cc1BeforeDg,
        jboolean cacheEnabled, jlongArray jperf) {
    using Clock = std::chrono::steady_clock;
    const auto started = Clock::now();
    if (!jperf || env->GetArrayLength(jperf) < 10) return JNI_FALSE;
    if (!jrgb || !jsrc || !jca9 || !jworkingMat || !joutMat || !jtone || !jdg || !jargb || !jcounts || pixels <= 0) return JNI_FALSE;
    if (env->GetArrayLength(jsrc) < 9 || env->GetArrayLength(jworkingMat) < 9 || env->GetArrayLength(joutMat) < 9 ||
        env->GetArrayLength(jca9) < 3 || env->GetArrayLength(jtone) < TONE_ENTRIES ||
        env->GetArrayLength(jdg) <= DG_INDEX_MAX || env->GetArrayLength(jargb) < pixels ||
        env->GetArrayLength(jrgb) < pixels * 3 || env->GetArrayLength(jcounts) < 8) return JNI_FALSE;

    jdouble src[9], workingMat[9], outMat[9];
    jint ca9[3];
    jlong existing[24] = {};
    const int returnedCounts=std::min(24,static_cast<int>(env->GetArrayLength(jcounts)));
    env->GetDoubleArrayRegion(jsrc, 0, 9, src);
    env->GetDoubleArrayRegion(jworkingMat, 0, 9, workingMat);
    env->GetDoubleArrayRegion(joutMat, 0, 9, outMat);
    env->GetIntArrayRegion(jca9, 0, 3, ca9);
    env->GetLongArrayRegion(jcounts, 0, returnedCounts, existing);

    jint* tone = env->GetIntArrayElements(jtone, nullptr);
    jint* dgt = env->GetIntArrayElements(jdg, nullptr);
    auto* rgb = static_cast<jshort*>(env->GetPrimitiveArrayCritical(jrgb, nullptr));
    auto* argb = static_cast<jint*>(env->GetPrimitiveArrayCritical(jargb, nullptr));
    if (!tone || !dgt || !rgb || !argb) {
        if (argb) env->ReleasePrimitiveArrayCritical(jargb, argb, 0);
        if (rgb) env->ReleasePrimitiveArrayCritical(jrgb, rgb, JNI_ABORT);
        if (dgt) env->ReleaseIntArrayElements(jdg, dgt, JNI_ABORT);
        if (tone) env->ReleaseIntArrayElements(jtone, tone, JNI_ABORT);
        return JNI_FALSE;
    }

    const int nthreads = std::max(1, std::min(THREADS, pixels / 32768));
    std::vector<Counts> local(static_cast<size_t>(nthreads));
    std::vector<std::thread> workers;
    workers.reserve(static_cast<size_t>(nthreads));

    std::vector<std::array<int64_t,2>> cacheCounts(static_cast<size_t>(nthreads));
    auto work = [&](int tid, int begin, int end) {
        Counts& cnt = local[static_cast<size_t>(tid)];
        m10r_tonecache3h::Cache toneCache;
        for (int i = begin; i < end; ++i) {
            const int o = i * 3;
            const double sr = static_cast<uint16_t>(rgb[o]) / 65535.0 * inverseStorageScale;
            const double sg = static_cast<uint16_t>(rgb[o+1]) / 65535.0 * inverseStorageScale;
            const double sb = static_cast<uint16_t>(rgb[o+2]) / 65535.0 * inverseStorageScale;

            double tr = src[0]*sr + src[1]*sg + src[2]*sb;
            double tg = src[3]*sr + src[4]*sg + src[5]*sb;
            double tb = src[6]*sr + src[7]*sg + src[8]*sb;
            tr = ca9clip(tr, ca9[0], cnt, 0);
            tg = ca9clip(tg, ca9[1], cnt, 1);
            tb = ca9clip(tb, ca9[2], cnt, 2);

            // WORKING1A: nonlinear B2Y input is Leica internal working RGB.
            const double lr = workingMat[0]*tr + workingMat[1]*tg + workingMat[2]*tb;
            const double lg = workingMat[3]*tr + workingMat[4]*tg + workingMat[5]*tb;
            const double lb = workingMat[6]*tr + workingMat[7]*tg + workingMat[8]*tb;

            // YA_TOPOLOGY1A: firmware-shaped nonlinear sandwich.
            // M10-R tone descriptor: RGB tone enabled, Yb tone disabled,
            // TCYC = {1024,2661,410}/4096. MAINBLEND1N reference evidence
            // strongly favors Ya (post-RGB nonlinear luminance) for main output.
            const double ytc = (1024.0*lr + 2661.0*lg + 410.0*lb) / 4096.0;
            const int xy = toneInput(ytc, cnt);
            const int my = medium(xy, tone);
            const double toneY = my / static_cast<double>(INPUT_MAX);
            const double toneGain = ytc > 1.0e-12 ? toneY / ytc : 0.0;

            const double toneR = lr * toneGain;
            const double toneG = lg * toneGain;
            const double toneB = lb * toneGain;

            // DG common-table candidate applied independently to RGB components.
            // This is the topology supported by TOPOLOGY1K/MAINBLEND1N;
            // exact ASIC table-bank routing remains a separate proof boundary.
            const int xr = cc1BeforeDg ? toneInput(outMat[0]*toneR + outMat[1]*toneG + outMat[2]*toneB, cnt) : toneInput(toneR, cnt);
            const int xg = cc1BeforeDg ? toneInput(outMat[3]*toneR + outMat[4]*toneG + outMat[5]*toneB, cnt) : toneInput(toneG, cnt);
            const int xb = cc1BeforeDg ? toneInput(outMat[6]*toneR + outMat[7]*toneG + outMat[8]*toneB, cnt) : toneInput(toneB, cnt);
            const int dr = dg(xr, dgt, cnt);
            const int dgG = dg(xg, dgt, cnt);
            const int db = dg(xb, dgt, cnt);
            const double nr = dr / static_cast<double>(DG_OUT_MAX);
            const double ng = dgG / static_cast<double>(DG_OUT_MAX);
            const double nb = db / static_cast<double>(DG_OUT_MAX);
            // COLORORDER1A: frozen photographic hypothesis, not an ASIC routing proof.
            // False preserves accepted/metering arithmetic; true moves only CC1 before DG.
            const double outR = cc1BeforeDg ? nr : outMat[0]*nr + outMat[1]*ng + outMat[2]*nb;
            const double outG = cc1BeforeDg ? ng : outMat[3]*nr + outMat[4]*ng + outMat[5]*nb;
            const double outB = cc1BeforeDg ? nb : outMat[6]*nr + outMat[7]*ng + outMat[8]*nb;
            double gamutR=outR, gamutG=outG, gamutB=outB;
            const int gamutStatus=m10r_outputgamut1a::apply(gamutR,gamutG,gamutB);
            cnt.v[8]++;
            cnt.v[9+gamutStatus]++;
            cnt.v[12]+=(outR<0.0); cnt.v[13]+=(outG<0.0); cnt.v[14]+=(outB<0.0);
            cnt.v[15]+=(outR>1.0); cnt.v[16]+=(outG>1.0); cnt.v[17]+=(outB>1.0);
            cnt.v[18]+=(gamutR<0.0); cnt.v[19]+=(gamutG<0.0); cnt.v[20]+=(gamutB<0.0);
            cnt.v[21]+=(gamutR>1.0); cnt.v[22]+=(gamutG>1.0); cnt.v[23]+=(gamutB>1.0);
            argb[i] = static_cast<jint>(0xff000000u |
                    (static_cast<uint32_t>(linear8(gamutR)) << 16) |
                    (static_cast<uint32_t>(linear8(gamutG)) << 8) |
                    static_cast<uint32_t>(linear8(gamutB)));
            argb[i] = static_cast<jint>((cacheEnabled ? toneCache.apply(static_cast<uint32_t>(argb[i])) : m10r_tonecal1a::apply(static_cast<uint32_t>(argb[i]))));
        }
        cacheCounts[tid] = {static_cast<int64_t>(toneCache.hits), static_cast<int64_t>(toneCache.misses)};
    };

    const auto setupDone = Clock::now();
    int begin = 0;
    for (int t = 0; t < nthreads; ++t) {
        int end = (t == nthreads - 1) ? pixels : static_cast<int>((static_cast<int64_t>(pixels) * (t + 1)) / nthreads);
        workers.emplace_back(work, t, begin, end);
        begin = end;
    }
    for (auto& th : workers) th.join();
    const auto workersDone = Clock::now();

    env->ReleasePrimitiveArrayCritical(jargb, argb, 0);
    env->ReleasePrimitiveArrayCritical(jrgb, rgb, JNI_ABORT);
    env->ReleaseIntArrayElements(jdg, dgt, JNI_ABORT);
    env->ReleaseIntArrayElements(jtone, tone, JNI_ABORT);

    for (const Counts& c : local) for (int k=0;k<returnedCounts;k++) existing[k] += static_cast<jlong>(c.v[k]);
    env->SetLongArrayRegion(jcounts, 0, returnedCounts, existing);
    const auto finished = Clock::now();
    auto ns = [](Clock::duration duration) { return static_cast<jlong>(std::chrono::duration_cast<std::chrono::nanoseconds>(duration).count()); };
    jlong perf[10] = {ns(finished-started), ns(setupDone-started), ns(workersDone-setupDone),
        ns(finished-workersDone), 0, 0, nthreads, m10r_tonecache3h::Cache::bytes, pixels, cacheEnabled ? 1 : 0};
    for (const auto& counts : cacheCounts) { perf[4] += counts[0]; perf[5] += counts[1]; }
    env->SetLongArrayRegion(jperf, 0, 10, perf);
    return JNI_TRUE;
}


