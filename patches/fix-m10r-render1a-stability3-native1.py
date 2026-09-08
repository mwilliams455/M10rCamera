#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix-m10r-render1a-stability3-native1.py <PhotonCamera-root>')
root = Path(sys.argv[1]).resolve()
if not (root / 'app').is_dir():
    raise SystemExit('RENDER1A STABILITY3 NATIVE1: not a PhotonCamera root')

def rd(rel):
    p = root / rel
    if not p.exists():
        raise SystemExit('RENDER1A STABILITY3 NATIVE1 missing: ' + rel)
    return p.read_text()

def wr(rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)

def one(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit('RENDER1A STABILITY3 NATIVE1 anchor %s count=%d' % (label, n))
    return text.replace(old, new, 1)

# Speed-only overlay: move the 12.6 MP colour/CA9/MEDIUM/DG/sRGB pixel loop
# into the existing Photon dngCreator native library. Demosaic, matrices, tone
# assets, exposure, JPEG quality and no-HDR policy remain unchanged.
grad = 'app/build.gradle'
g = rd(grad)
g = one(g,
        "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability2'",
        "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1'",
        'version')
wr(grad, g)

helper_rel = 'app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RToneDg1A.java'
h = rd(helper_rel)
anchor = '    static int medium(int x) {\n'
extra = '''    static int toInputLumaNoStats(double v) {\n        if (!Double.isFinite(v) || v < 0.0) return 0;\n        if (v > 1.0) return INPUT_MAX;\n        return clamp((int)Math.round(v*INPUT_MAX),0,INPUT_MAX);\n    }\n    static int dgLumaNoStats(int x) {\n        int xx=clamp(x,0,DG_INDEX_MAX);\n        return DGT[xx];\n    }\n    static int[] nativeToneTable() { return TONE; }\n    static int[] nativeDgTable() { return DGT; }\n\n''' + anchor
if 'nativeToneTable()' not in h:
    h = one(h, anchor, extra, 'tone-accessors')
wr(helper_rel, h)

renderer_rel = 'app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'
r = rd(renderer_rel)
class_anchor = 'public final class M10RNativeRenderer {\n'
class_extra = class_anchor + '''    static { System.loadLibrary("dngCreator"); }\n    private static native void nativeProcessTile(\n            short[] rgb16, int pixels, double inverseStorageScale,\n            double[] srcToTargetCamera, int[] ca9, double[] targetToSrgb,\n            int[] toneTable, int[] dgTable, int[] argbOut, long[] exactCounts);\n\n'''
if 'nativeProcessTile(' not in r:
    r = one(r, class_anchor, class_extra, 'native-declaration')

init_anchor = '''            long[] neutralClipCounts = new long[3];\n            M10RToneDg1A.Diagnostics toneDgStats = new M10RToneDg1A.Diagnostics();\n            double inverseStorageScale = 1.0 / normalized.storageScale;\n'''
init_new = '''            long[] neutralClipCounts = new long[3];\n            M10RToneDg1A.Diagnostics toneDgStats = new M10RToneDg1A.Diagnostics();\n            double inverseStorageScale = 1.0 / normalized.storageScale;\n            final int[] nativeToneTable = M10RToneDg1A.nativeToneTable();\n            final int[] nativeDgTable = M10RToneDg1A.nativeDgTable();\n            final long[] nativeExactCounts = new long[8];\n            final long[] sampledNeutralClipScratch = new long[3];\n'''
r = one(r, init_anchor, init_new, 'native-init')

start_marker = '                int pixels = frame.width * rows;\n                for (int i = 0; i < pixels; i++) {\n'
start = r.find(start_marker)
if start < 0 or r.find(start_marker, start + 1) >= 0:
    raise SystemExit('RENDER1A STABILITY3 NATIVE1 pixel-loop start missing/ambiguous')
loop_start = start + len('                int pixels = frame.width * rows;\n')
end_marker = '                tileBgr.release();\n'
end = r.find(end_marker, loop_start)
if end < 0:
    raise SystemExit('RENDER1A STABILITY3 NATIVE1 pixel-loop end missing')
old_loop = r[loop_start:end]
for required in ['sampleDiagnostics', 'M10RToneDg1A.medium(xy)', 'argb[i] = 0xff000000']:
    if required not in old_loop:
        raise SystemExit('RENDER1A STABILITY3 NATIVE1 expected STABILITY2 loop missing ' + required)

new_loop = '''                nativeProcessTile(\n                        bgr, pixels, inverseStorageScale,\n                        srcToTargetCamera, ca9, targetToSrgb,\n                        nativeToneTable, nativeDgTable, argb, nativeExactCounts);\n\n                // Preserve the research distributions at the exact STABILITY2 1/64\n                // sampling phase without making Java form any output pixels.\n                for (int i = 0; i < pixels; i += 64) {\n                    double sr = (bgr[i * 3] & 0xffff) / 65535.0 * inverseStorageScale;\n                    double sg = (bgr[i * 3 + 1] & 0xffff) / 65535.0 * inverseStorageScale;\n                    double sb = (bgr[i * 3 + 2] & 0xffff) / 65535.0 * inverseStorageScale;\n                    double tr = srcToTargetCamera[0]*sr + srcToTargetCamera[1]*sg + srcToTargetCamera[2]*sb;\n                    double tg = srcToTargetCamera[3]*sr + srcToTargetCamera[4]*sg + srcToTargetCamera[5]*sb;\n                    double tb = srcToTargetCamera[6]*sr + srcToTargetCamera[7]*sg + srcToTargetCamera[8]*sb;\n                    tr = ca9Clip(tr, ca9[0], sampledNeutralClipScratch, 0);\n                    tg = ca9Clip(tg, ca9[1], sampledNeutralClipScratch, 1);\n                    tb = ca9Clip(tb, ca9[2], sampledNeutralClipScratch, 2);\n                    double lr = targetToSrgb[0]*tr + targetToSrgb[1]*tg + targetToSrgb[2]*tb;\n                    double lg = targetToSrgb[3]*tr + targetToSrgb[4]*tg + targetToSrgb[5]*tb;\n                    double lb = targetToSrgb[6]*tr + targetToSrgb[7]*tg + targetToSrgb[8]*tb;\n                    toneDgStats.preTone.add(lr, lg, lb);\n                    double linearY = 0.2126*lr + 0.7152*lg + 0.0722*lb;\n                    int xy = M10RToneDg1A.toInputLumaNoStats(linearY);\n                    toneDgStats.toneInput.add(xy, xy, xy);\n                    int my = M10RToneDg1A.medium(xy);\n                    toneDgStats.postTone.add(my, my, my);\n                    int dy = M10RToneDg1A.dgLumaNoStats(my);\n                    toneDgStats.postDg.add(dy, dy, dy);\n                    double mappedY = dy / (double)M10RToneDg1A.DG_OUT_MAX;\n                    double gain = (linearY > 1.0e-12) ? (mappedY / linearY) : 0.0;\n                    toneDgStats.lumaGain.add(gain);\n                    toneDgStats.preSrgb.add(lr*gain, lg*gain, lb*gain);\n                }\n'''
r = r[:loop_start] + new_loop + r[end:]

count_anchor = '''            d.put("neutralDomainClipCounts", json(neutralClipCounts));\n            d.put("sourceWhiteLevelClipCount", normalized.sourceWhiteClipCount);\n'''
count_new = '''            neutralClipCounts[0] = nativeExactCounts[0];\n            neutralClipCounts[1] = nativeExactCounts[1];\n            neutralClipCounts[2] = nativeExactCounts[2];\n            toneDgStats.lumaInputLow = nativeExactCounts[3];\n            toneDgStats.lumaInputHigh = nativeExactCounts[4];\n            toneDgStats.lumaInputNonFinite = nativeExactCounts[5];\n            toneDgStats.lumaDgLow = nativeExactCounts[6];\n            toneDgStats.lumaDgHigh = nativeExactCounts[7];\n            d.put("neutralDomainClipCounts", json(neutralClipCounts));\n            d.put("sourceWhiteLevelClipCount", normalized.sourceWhiteClipCount);\n'''
r = one(r, count_anchor, count_new, 'native-exact-counts')

meta_old = '''            d.put("renderStabilityFix", "STABILITY2_TILED_EA_DEMOSAIC_SAMPLED_DIAGNOSTICS");\n            d.put("diagnosticSamplingStride", 64);\n'''
meta_new = '''            d.put("renderStabilityFix", "STABILITY3_NATIVE1_FOUR_THREAD_PIXEL_CORE");\n            d.put("nativePixelCore", true);\n            d.put("nativePixelCoreThreads", 4);\n            d.put("nativePixelCoreLibrary", "dngCreator/m10rRender.cpp");\n            d.put("diagnosticSamplingStride", 64);\n'''
r = one(r, meta_old, meta_new, 'native-metadata')
wr(renderer_rel, r)

# Add the native source to Photon's existing dngCreator library. This avoids a
# second shared-library packaging path and leaves dngCreator.cpp itself untouched.
cmake_rel = 'app/src/main/cpp/CMakeLists.txt'
c = rd(cmake_rel)
old_cmake = '''add_library(${CMAKE_PROJECT_NAME} SHARED\n    ${SRC_DIR}/dngCreator.cpp\n)\n'''
new_cmake = '''add_library(${CMAKE_PROJECT_NAME} SHARED\n    ${SRC_DIR}/dngCreator.cpp\n    ${SRC_DIR}/m10rRender.cpp\n)\nset_source_files_properties(${SRC_DIR}/m10rRender.cpp PROPERTIES\n    COMPILE_FLAGS "-O3 -ffp-contract=off"\n)\n'''
c = one(c, old_cmake, new_cmake, 'cmake-source')
wr(cmake_rel, c)

cpp = r'''#include <jni.h>
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
    int64_t v[8] = {0,0,0,0,0,0,0,0};
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
}

extern "C" JNIEXPORT void JNICALL
Java_com_particlesdevs_photoncamera_m10r_M10RNativeRenderer_nativeProcessTile(
        JNIEnv* env, jclass,
        jshortArray jrgb, jint pixels, jdouble inverseStorageScale,
        jdoubleArray jsrc, jintArray jca9, jdoubleArray joutMat,
        jintArray jtone, jintArray jdg, jintArray jargb, jlongArray jcounts) {
    if (!jrgb || !jsrc || !jca9 || !joutMat || !jtone || !jdg || !jargb || !jcounts || pixels <= 0) return;
    if (env->GetArrayLength(jsrc) < 9 || env->GetArrayLength(joutMat) < 9 ||
        env->GetArrayLength(jca9) < 3 || env->GetArrayLength(jtone) < TONE_ENTRIES ||
        env->GetArrayLength(jdg) <= DG_INDEX_MAX || env->GetArrayLength(jargb) < pixels ||
        env->GetArrayLength(jrgb) < pixels * 3 || env->GetArrayLength(jcounts) < 8) return;

    jdouble src[9], outMat[9];
    jint ca9[3];
    jlong existing[8];
    env->GetDoubleArrayRegion(jsrc, 0, 9, src);
    env->GetDoubleArrayRegion(joutMat, 0, 9, outMat);
    env->GetIntArrayRegion(jca9, 0, 3, ca9);
    env->GetLongArrayRegion(jcounts, 0, 8, existing);

    jint* tone = env->GetIntArrayElements(jtone, nullptr);
    jint* dgt = env->GetIntArrayElements(jdg, nullptr);
    auto* rgb = static_cast<jshort*>(env->GetPrimitiveArrayCritical(jrgb, nullptr));
    auto* argb = static_cast<jint*>(env->GetPrimitiveArrayCritical(jargb, nullptr));
    if (!tone || !dgt || !rgb || !argb) {
        if (argb) env->ReleasePrimitiveArrayCritical(jargb, argb, 0);
        if (rgb) env->ReleasePrimitiveArrayCritical(jrgb, rgb, JNI_ABORT);
        if (dgt) env->ReleaseIntArrayElements(jdg, dgt, JNI_ABORT);
        if (tone) env->ReleaseIntArrayElements(jtone, tone, JNI_ABORT);
        return;
    }

    const int nthreads = std::max(1, std::min(THREADS, pixels / 32768));
    std::vector<Counts> local(static_cast<size_t>(nthreads));
    std::vector<std::thread> workers;
    workers.reserve(static_cast<size_t>(nthreads));

    auto work = [&](int tid, int begin, int end) {
        Counts& cnt = local[static_cast<size_t>(tid)];
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

            const double lr = outMat[0]*tr + outMat[1]*tg + outMat[2]*tb;
            const double lg = outMat[3]*tr + outMat[4]*tg + outMat[5]*tb;
            const double lb = outMat[6]*tr + outMat[7]*tg + outMat[8]*tb;
            const double y = 0.2126*lr + 0.7152*lg + 0.0722*lb;
            const int xy = toneInput(y, cnt);
            const int my = medium(xy, tone);
            const int dy = dg(my, dgt, cnt);
            const double mappedY = dy / static_cast<double>(DG_OUT_MAX);
            const double gain = y > 1.0e-12 ? mappedY / y : 0.0;
            const double nr = lr * gain;
            const double ng = lg * gain;
            const double nb = lb * gain;
            argb[i] = static_cast<jint>(0xff000000u |
                    (static_cast<uint32_t>(srgb8(nr)) << 16) |
                    (static_cast<uint32_t>(srgb8(ng)) << 8) |
                    static_cast<uint32_t>(srgb8(nb)));
        }
    };

    int begin = 0;
    for (int t = 0; t < nthreads; ++t) {
        int end = (t == nthreads - 1) ? pixels : static_cast<int>((static_cast<int64_t>(pixels) * (t + 1)) / nthreads);
        workers.emplace_back(work, t, begin, end);
        begin = end;
    }
    for (auto& th : workers) th.join();

    env->ReleasePrimitiveArrayCritical(jargb, argb, 0);
    env->ReleasePrimitiveArrayCritical(jrgb, rgb, JNI_ABORT);
    env->ReleaseIntArrayElements(jdg, dgt, JNI_ABORT);
    env->ReleaseIntArrayElements(jtone, tone, JNI_ABORT);

    for (const Counts& c : local) for (int k=0;k<8;k++) existing[k] += static_cast<jlong>(c.v[k]);
    env->SetLongArrayRegion(jcounts, 0, 8, existing);
}
'''
wr('app/src/main/cpp/m10rRender.cpp', cpp)

# Hard checks.
R = rd(renderer_rel); H = rd(helper_rel); C = rd(cmake_rel); CPP = rd('app/src/main/cpp/m10rRender.cpp')
for marker in [
    'STABILITY3_NATIVE1_FOUR_THREAD_PIXEL_CORE',
    'nativePixelCoreThreads", 4',
    'private static native void nativeProcessTile(',
    'nativeProcessTile(',
    'nonlinearOrder", "MEDIUM_THEN_DIFFERENTIAL_GAMMA"',
    'nonlinearApplicationMode", "luma_gain_preserve_linear_rgb_ratios"',
    'hdrEnabled", false', 'sourceFrameCount", 1',
    'final int blockRows = 256', 'diagnosticSamplingStride", 64',
]:
    if marker not in R: raise SystemExit('RENDER1A STABILITY3 NATIVE1 renderer invariant missing: '+marker)
for marker in ['nativeToneTable()', 'nativeDgTable()', 'toInputLumaNoStats', 'dgLumaNoStats']:
    if marker not in H: raise SystemExit('RENDER1A STABILITY3 NATIVE1 helper invariant missing: '+marker)
for marker in ['${SRC_DIR}/m10rRender.cpp', '-O3 -ffp-contract=off']:
    if marker not in C: raise SystemExit('RENDER1A STABILITY3 NATIVE1 CMake invariant missing: '+marker)
for marker in ['M10RNativeRenderer_nativeProcessTile', 'constexpr int THREADS = 4', 'std::pow', 'MEDIUM']:
    if marker == 'MEDIUM': continue
    if marker not in CPP: raise SystemExit('RENDER1A STABILITY3 NATIVE1 native core invariant missing: '+marker)
if 'for (int i = 0; i < pixels; i++) {' in R:
    raise SystemExit('RENDER1A STABILITY3 NATIVE1 full Java pixel loop still present')

print('M10-R RENDER1A STABILITY3 NATIVE1 applied')
print(' - 12 MP output pixel formation moved from Java to 4-thread C++')
print(' - existing OpenCV EA tiled demosaic unchanged')
print(' - exact CA9/tone-input/DG clip counters retained by native core')
print(' - STABILITY2 1/64 research distributions retained as sparse Java diagnostics')
print(' - colour matrices, MEDIUM/DG assets/order, sRGB transfer and JPEG quality unchanged')
print(' - single-frame capture and HDR-disabled policy unchanged')
