#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix-m10r-render1c-edge1a.py <PhotonCamera-root>')
root=Path(sys.argv[1]).resolve()
if not (root/'app').is_dir(): raise SystemExit('RENDER1C EDGE1A: not a PhotonCamera root')

def rd(rel):
    p=root/rel
    if not p.exists(): raise SystemExit('RENDER1C EDGE1A missing: '+rel)
    return p.read_text()
def wr(rel,s):
    p=root/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(s)
def one(s,a,b,label):
    n=s.count(a)
    if n!=1: raise SystemExit('RENDER1C EDGE1A anchor %s count=%d'%(label,n))
    return s.replace(a,b,1)

# RENDER1C EDGE1A is a deliberately bounded photographic experiment on top of
# the user-approved LOOK1B/YC1B baseline. The firmware-derived facts used here:
#   STILL_SHARPNESS:MEDIUM high-frequency 5x5 symmetry coefficients
#       center=316, near-axis=-46, near-diagonal=-4,
#       far-axis=-20, off-axis(2,1)=-3, far-corner=-3
#   weighted 5x5 sum is exactly zero (high-pass)
#   field immediately before coefficients = 8 (tested as Q8/shift candidate)
#   following base-ISO control values include 450, 1001 ...
#   EDGE_SYNTHESIS STILL ISO selector = 5400 (ISO100/160), 4096 (200..640),
#                                     3700 (>=800)
# Exact hardware arithmetic/placement is NOT claimed. Dedicated TEXTURE
# ENHANCEMENT is intentionally not enabled because its calibration enable=0.

grad='app/build.gradle'
g=rd(grad)
g=one(g,
      "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b'",
      "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1c-edge1a'",
      'version')
wr(grad,g)

renderer='app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'
r=rd(renderer)
# Add a Bitmap-native spatial pass alongside the already-loaded dngCreator core.
decl='''    private static native void nativeProcessTile(\n            short[] rgb16, int pixels, double inverseStorageScale,\n            double[] srcToTargetCamera, int[] ca9, double[] targetToSrgb,\n            int[] toneTable, int[] dgTable, int[] argbOut, long[] exactCounts);\n'''
decl_new=decl+'''    private static native long nativeEdgePass(Bitmap bitmap, int iso);\n'''
r=one(r,decl,decl_new,'edge-native-declaration')

# Apply after final oriented LOOK1B bitmap formation. This keeps the user-approved
# colour/tone math frozen and makes the spatial experiment easy to remove/compare.
anchor='''            d.put("outputWidth", bitmap.getWidth());\n            d.put("outputHeight", bitmap.getHeight());\n            d.put("status", "success");\n'''
insert='''            Integer edgeIsoObj = captureResult.get(CaptureResult.SENSOR_SENSITIVITY);\n            int edgeIso = edgeIsoObj != null && edgeIsoObj > 0 ? edgeIsoObj : 100;\n            long edgeStartNs = System.nanoTime();\n            long edgeAffectedPixels = nativeEdgePass(bitmap, edgeIso);\n            double edgeElapsedMs = (System.nanoTime() - edgeStartNs) / 1_000_000.0;\n            d.put("renderLook", "RENDER1C_EDGE1A");\n            d.put("edgePassEnabled", true);\n            d.put("edgeSource", "M10R_B2Y_STILL_SHARPNESS_MEDIUM_HIGH_FREQ_PLUS_EDGE_SYNTHESIS_ISO_GAIN");\n            d.put("edgeKernelGeometry", "5x5_D4_symmetric_zero_DC");\n            d.put("edgeKernelOrbitCoefficients", "316,-46,-4,-20,-3,-3");\n            d.put("edgeKernelWeightedSum", 0);\n            d.put("edgeKernelShiftCandidate", 8);\n            d.put("edgeCoringCandidate", 450);\n            d.put("edgeLimitCandidate", 1001);\n            d.put("edgeIso", edgeIso);\n            d.put("edgeSynthesisGainQ12", edgeIso <= 160 ? 5400 : (edgeIso <= 640 ? 4096 : 3700));\n            d.put("edgeAffectedPixels", edgeAffectedPixels);\n            d.put("edgeElapsedMs", edgeElapsedMs);\n            d.put("edgeArithmeticExactFirmwareParityClaimed", false);\n            d.put("edgePlacement", "post_LOOK1B_sRGB_decode_linear_Y_reencode_EXPERIMENTAL");\n            d.put("textureEnhancementBlockEnabled", false);\n            d.put("textureEnhancementReason", "firmware_calibration_enable_field_is_zero");\n            d.put("lowFrequencyEdgeApplied", false);\n            d.put("lowFrequencyEdgeReason", "combination_scaling_not_yet_constrained_enough");\n            d.put("outputWidth", bitmap.getWidth());\n            d.put("outputHeight", bitmap.getHeight());\n            d.put("status", "success");\n'''
r=one(r,anchor,insert,'edge-call')
wr(renderer,r)

cpp='app/src/main/cpp/m10rRender.cpp'
c=rd(cpp)
# Android Bitmap NDK API for in-place pass without a second full ARGB bitmap.
c=one(c,'#include <jni.h>\n','#include <jni.h>\n#include <android/bitmap.h>\n','bitmap-header')

native=r'''

extern "C" JNIEXPORT jlong JNICALL
Java_com_particlesdevs_photoncamera_m10r_M10RNativeRenderer_nativeEdgePass(
        JNIEnv* env, jclass, jobject bitmap, jint iso) {
    if (!bitmap) return 0;
    AndroidBitmapInfo info{};
    if (AndroidBitmap_getInfo(env, bitmap, &info) != ANDROID_BITMAP_RESULT_SUCCESS) return -1;
    if (info.format != ANDROID_BITMAP_FORMAT_RGBA_8888 || info.width < 5 || info.height < 5) return -2;

    void* rawPixels = nullptr;
    if (AndroidBitmap_lockPixels(env, bitmap, &rawPixels) != ANDROID_BITMAP_RESULT_SUCCESS || !rawPixels) return -3;

    const int w = static_cast<int>(info.width);
    const int h = static_cast<int>(info.height);
    const int stride = static_cast<int>(info.stride);
    auto* base = static_cast<uint8_t*>(rawPixels);

    // Full uint16 luma plane (~24 MiB at 12.6 MP) avoids a second ARGB bitmap
    // and guarantees the convolution never reads already-sharpened neighbors.
    std::vector<uint16_t> y14(static_cast<size_t>(w) * static_cast<size_t>(h));

    double decode[256];
    for (int i=0;i<256;i++) {
        const double e = i / 255.0;
        decode[i] = e <= 0.04045 ? e / 12.92 : std::pow((e + 0.055) / 1.055, 2.4);
    }

    auto fillLuma = [&](int y0, int y1) {
        for (int y=y0; y<y1; ++y) {
            uint8_t* row = base + static_cast<size_t>(y) * stride;
            for (int x=0; x<w; ++x) {
                const uint8_t* p = row + x*4;
                const double r = decode[p[0]], g = decode[p[1]], b = decode[p[2]];
                double yy = (1224.0*r + 2404.0*g + 467.0*b) / 4096.0;
                yy = std::max(0.0, std::min(1.0, yy));
                y14[static_cast<size_t>(y)*w+x] = static_cast<uint16_t>(std::floor(yy*16383.0 + 0.5));
            }
        }
    };
    {
        const int nt=4;
        std::vector<std::thread> ts;
        for (int t=0;t<nt;t++) {
            int a=h*t/nt, b=h*(t+1)/nt;
            ts.emplace_back(fillLuma,a,b);
        }
        for (auto& t:ts) t.join();
    }

    // Six D4-symmetry orbits recovered from STILL_SHARPNESS:MEDIUM HF record.
    // Layout:
    //  k o b o k
    //  o d a d o
    //  b a c a b
    //  o d a d o
    //  k o b o k
    constexpr int kc=316, ka=-46, kd=-4, kb=-20, ko=-3, kk=-3;
    constexpr double q8=256.0;
    constexpr double core=450.0;
    constexpr double limit=1001.0;
    const double synthGain = iso <= 160 ? (5400.0/4096.0) : (iso <= 640 ? 1.0 : (3700.0/4096.0));

    auto enc8 = [](double linear)->uint8_t {
        double v=std::max(0.0,std::min(1.0,linear));
        double e=v<=0.0031308 ? 12.92*v : 1.055*std::pow(v,1.0/2.4)-0.055;
        int q=static_cast<int>(std::floor(std::max(0.0,std::min(1.0,e))*255.0+0.5));
        return static_cast<uint8_t>(std::max(0,std::min(255,q)));
    };

    std::vector<int64_t> affected(4,0);
    auto sharpen = [&](int tid, int y0, int y1) {
        y0=std::max(2,y0); y1=std::min(h-2,y1);
        int64_t local=0;
        for (int y=y0; y<y1; ++y) {
            uint8_t* row=base+static_cast<size_t>(y)*stride;
            for (int x=2; x<w-2; ++x) {
                auto Y=[&](int dx,int dy)->int64_t{return y14[static_cast<size_t>(y+dy)*w+(x+dx)];};
                int64_t sum=0;
                sum += kc*Y(0,0);
                sum += ka*(Y(-1,0)+Y(1,0)+Y(0,-1)+Y(0,1));
                sum += kd*(Y(-1,-1)+Y(1,-1)+Y(-1,1)+Y(1,1));
                sum += kb*(Y(-2,0)+Y(2,0)+Y(0,-2)+Y(0,2));
                sum += ko*(Y(-2,-1)+Y(-2,1)+Y(2,-1)+Y(2,1)+Y(-1,-2)+Y(1,-2)+Y(-1,2)+Y(1,2));
                sum += kk*(Y(-2,-2)+Y(2,-2)+Y(-2,2)+Y(2,2));
                double hp=sum/q8;
                double mag=std::abs(hp);
                if (mag<=core) continue;
                double shaped=std::min(mag,limit)-core;
                if (shaped<=0.0) continue;
                double delta=(hp<0.0?-shaped:shaped)*synthGain;
                const double oldY=Y(0,0);
                if (oldY<=1.0) continue;
                double newY=std::max(0.0,std::min(16383.0,oldY+delta));
                if (std::abs(newY-oldY)<0.5) continue;
                double ratio=newY/oldY;
                uint8_t* p=row+x*4;
                p[0]=enc8(decode[p[0]]*ratio);
                p[1]=enc8(decode[p[1]]*ratio);
                p[2]=enc8(decode[p[2]]*ratio);
                local++;
            }
        }
        affected[tid]=local;
    };
    {
        const int nt=4;
        std::vector<std::thread> ts;
        for (int t=0;t<nt;t++) {
            int a=h*t/nt, b=h*(t+1)/nt;
            ts.emplace_back(sharpen,t,a,b);
        }
        for (auto& t:ts) t.join();
    }

    AndroidBitmap_unlockPixels(env, bitmap);
    int64_t total=0; for (auto v:affected) total+=v;
    return static_cast<jlong>(total);
}
'''
if 'M10RNativeRenderer_nativeEdgePass' in c:
    raise SystemExit('RENDER1C EDGE1A native edge pass already exists')
c += native
wr(cpp,c)

cmake='app/src/main/cpp/CMakeLists.txt'
cm=rd(cmake)
link='''target_link_libraries(${CMAKE_PROJECT_NAME} PRIVATE\n        log\n        dl\n)\n'''
link_new='''target_link_libraries(${CMAKE_PROJECT_NAME} PRIVATE\n        log\n        dl\n        jnigraphics\n)\n'''
cm=one(cm,link,link_new,'jnigraphics-link')
wr(cmake,cm)

R=rd(renderer); C=rd(cpp); CM=rd(cmake)
for m in [
    'LOOK1B_YC1B','RENDER1C_EDGE1A','edgeKernelOrbitCoefficients", "316,-46,-4,-20,-3,-3"',
    'edgeKernelWeightedSum", 0','edgeArithmeticExactFirmwareParityClaimed", false',
    'textureEnhancementBlockEnabled", false','lowFrequencyEdgeApplied", false',
    'hdrEnabled", false','sourceFrameCount", 1','STABILITY3_NATIVE1_FOUR_THREAD_PIXEL_CORE']:
    if m not in R: raise SystemExit('RENDER1C EDGE1A renderer invariant missing: '+m)
for m in ['AndroidBitmap_lockPixels','constexpr int kc=316, ka=-46, kd=-4, kb=-20, ko=-3, kk=-3',
          '5400.0/4096.0','3700.0/4096.0','constexpr double core=450.0','constexpr double limit=1001.0']:
    if m not in C: raise SystemExit('RENDER1C EDGE1A native invariant missing: '+m)
if 'jnigraphics' not in CM: raise SystemExit('RENDER1C EDGE1A jnigraphics link missing')
print('M10-R RENDER1C EDGE1A applied')
print(' - LOOK1B/YC1B colour and tone frozen')
print(' - firmware-derived STILL_SHARPNESS:MEDIUM HF 5x5 zero-DC kernel added')
print(' - firmware EDGE_SYNTHESIS ISO gain map applied')
print(' - Q8/coring/limit combination explicitly marked experimental')
print(' - dedicated TEXTURE ENHANCEMENT remains OFF because firmware calibration disables it')
print(' - LF edge deferred until combination scaling is better proven')
print(' - 12 MP, JPEG quality, single-frame and HDR-disabled policy unchanged')
