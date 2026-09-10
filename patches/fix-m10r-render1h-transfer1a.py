#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix-m10r-render1h-transfer1a.py <PhotonCamera-root>')
root = Path(sys.argv[1]).resolve()
if not (root / 'app').is_dir():
    raise SystemExit('RENDER1H TRANSFER1A: not a PhotonCamera root')

def rd(rel):
    p = root / rel
    if not p.exists():
        raise SystemExit('RENDER1H TRANSFER1A missing: ' + rel)
    return p.read_text()

def wr(rel, text):
    (root / rel).write_text(text)

def one(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit('RENDER1H TRANSFER1A anchor %s count=%d' % (label, n))
    return text.replace(old, new, 1)

# TRANSFER1A is a single-variable device discriminator on top of WORKING1A.
# Device diagnostics show that MEDIUM/DG already expand low/mid scalar values
# strongly before the renderer applies the textbook sRGB OETF. Firmware research
# freezes differential gamma itself as a live 14-bit scalar transfer function,
# while interpolation gamma is disabled in default STILL. What is still open is
# whether the software renderer should add a separate display OETF after B2Y.
#
# IMPORTANT ISOLATION DETAIL:
# EDGE1A currently receives the sRGB-coded WORKING1A bitmap, decodes it to linear
# for its Y-domain operation, then re-encodes affected pixels. Removing the OETF
# inside nativeProcessTile would therefore silently change EDGE1A's input domain.
# This diagnostic instead leaves nativeProcessTile and EDGE1A byte-for-byte
# untouched, then applies one full-frame inverse-sRGB transform after EDGE1A and
# before JPEG publication. Thus the only delivered-image variable is final
# transfer coding. The 8-bit OETF -> inverse-OETF round trip is quantized and is
# explicitly NOT claimed to be exact M10-R hardware parity.

grad = 'app/build.gradle'
g = rd(grad)
g = one(
    g,
    "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1g-working1a-diag1c-saf1'",
    "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1h-transfer1a-diag1c-saf1'",
    'version')
wr(grad, g)

renderer = 'app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'
r = rd(renderer)

edge_decl = '    private static native long nativeEdgePass(Bitmap bitmap, int iso);\n'
transfer_decl = edge_decl + '    private static native long nativeInverseSrgbTransfer(Bitmap bitmap);\n'
r = one(r, edge_decl, transfer_decl, 'native-transfer-declaration')

old_call = '''            long edgeAffectedPixels = nativeEdgePass(bitmap, edgeIso);\n            double edgeElapsedMs = (System.nanoTime() - edgeStartNs) / 1_000_000.0;\n            d.put("renderLook", "RENDER1G_WORKING1A_YC2A_MATRIX1A");\n'''
new_call = '''            long edgeAffectedPixels = nativeEdgePass(bitmap, edgeIso);\n            double edgeElapsedMs = (System.nanoTime() - edgeStartNs) / 1_000_000.0;\n\n            // TRANSFER1A: preserve the entire WORKING1A + EDGE1A path, then\n            // cancel only the final textbook sRGB coding before JPEG save.\n            long transferStartNs = System.nanoTime();\n            long transferPixels = nativeInverseSrgbTransfer(bitmap);\n            double transferElapsedMs = (System.nanoTime() - transferStartNs) / 1_000_000.0;\n            if (transferPixels < 0) {\n                throw new IllegalStateException("M10-R TRANSFER1A native inverse-sRGB failed code=" + transferPixels);\n            }\n            d.put("renderLook", "RENDER1H_TRANSFER1A_WORKING1A_YC2A_MATRIX1A");\n            d.put("outputTransferExperiment", "TRANSFER1A_POST_EDGE_INVERSE_SRGB_CANCEL");\n            d.put("outputTransferPlacement", "post_EDGE1A_before_JPEG");\n            d.put("working1aNativeSrgbOetfRetainedForEdgeInvariant", true);\n            d.put("edgeInputDomainUnchangedFromWorking1A", true);\n            d.put("netOutputTransfer", "linear_coded_after_inverse_sRGB");\n            d.put("outputTransferQuantization", "8bit_sRGB_roundtrip_diagnostic");\n            d.put("outputTransferExactHardwareParityClaimed", false);\n            d.put("outputTransferPixels", transferPixels);\n            d.put("outputTransferElapsedMs", transferElapsedMs);\n'''
r = one(r, old_call, new_call, 'post-edge-transfer-call')
wr(renderer, r)

cpp = 'app/src/main/cpp/m10rRender.cpp'
c = rd(cpp)
if 'M10RNativeRenderer_nativeInverseSrgbTransfer' in c:
    raise SystemExit('RENDER1H TRANSFER1A native inverse transfer already exists')

native = r'''

// RENDER1H TRANSFER1A diagnostic only.
// Input is the already-formed WORKING1A bitmap AFTER the frozen EDGE1A path.
// Every channel is decoded with the exact inverse of the textbook sRGB OETF
// used by the current renderer/edge implementation, then re-quantized to 8-bit.
// Alpha and geometry are unchanged. This intentionally tests final transfer
// ownership without altering the input domain seen by EDGE1A.
extern "C" JNIEXPORT jlong JNICALL
Java_com_particlesdevs_photoncamera_m10r_M10RNativeRenderer_nativeInverseSrgbTransfer(
        JNIEnv* env, jclass, jobject bitmap) {
    if (!bitmap) return -10;
    AndroidBitmapInfo info{};
    if (AndroidBitmap_getInfo(env, bitmap, &info) != ANDROID_BITMAP_RESULT_SUCCESS) return -11;
    if (info.format != ANDROID_BITMAP_FORMAT_RGBA_8888 || info.width == 0 || info.height == 0) return -12;

    uint8_t inverseSrgb[256];
    for (int i = 0; i < 256; ++i) {
        const double encoded = i / 255.0;
        const double linear = encoded <= 0.04045
                ? encoded / 12.92
                : std::pow((encoded + 0.055) / 1.055, 2.4);
        const int q = static_cast<int>(std::floor(
                std::max(0.0, std::min(1.0, linear)) * 255.0 + 0.5));
        inverseSrgb[i] = static_cast<uint8_t>(std::max(0, std::min(255, q)));
    }

    void* rawPixels = nullptr;
    if (AndroidBitmap_lockPixels(env, bitmap, &rawPixels) != ANDROID_BITMAP_RESULT_SUCCESS || !rawPixels) return -13;

    const int w = static_cast<int>(info.width);
    const int h = static_cast<int>(info.height);
    const int stride = static_cast<int>(info.stride);
    auto* base = static_cast<uint8_t*>(rawPixels);

    auto convertRows = [&](int y0, int y1) {
        for (int y = y0; y < y1; ++y) {
            uint8_t* row = base + static_cast<size_t>(y) * stride;
            for (int x = 0; x < w; ++x) {
                uint8_t* p = row + x * 4;
                p[0] = inverseSrgb[p[0]];
                p[1] = inverseSrgb[p[1]];
                p[2] = inverseSrgb[p[2]];
            }
        }
    };

    {
        constexpr int nt = 4;
        std::vector<std::thread> threads;
        threads.reserve(nt);
        for (int t = 0; t < nt; ++t) {
            const int y0 = h * t / nt;
            const int y1 = h * (t + 1) / nt;
            threads.emplace_back(convertRows, y0, y1);
        }
        for (auto& thread : threads) thread.join();
    }

    AndroidBitmap_unlockPixels(env, bitmap);
    return static_cast<jlong>(static_cast<int64_t>(w) * static_cast<int64_t>(h));
}
'''
c += native
wr(cpp, c)

# Hard isolation checks. These deliberately ensure the pre-existing OETF and
# EDGE1A implementation remain present; TRANSFER1A must not become an upstream
# renderer rewrite by accident.
G = rd(grad)
R = rd(renderer)
C = rd(cpp)
if "render1h-transfer1a-diag1c-saf1'" not in G:
    raise SystemExit('RENDER1H TRANSFER1A build identity missing')
for needle in [
    'RENDER1H_TRANSFER1A_WORKING1A_YC2A_MATRIX1A',
    'TRANSFER1A_POST_EDGE_INVERSE_SRGB_CANCEL',
    'post_EDGE1A_before_JPEG',
    'working1aNativeSrgbOetfRetainedForEdgeInvariant", true',
    'edgeInputDomainUnchangedFromWorking1A", true',
    'linear_coded_after_inverse_sRGB',
    '8bit_sRGB_roundtrip_diagnostic',
    'outputTransferExactHardwareParityClaimed", false',
    'nativeInverseSrgbTransfer(bitmap)',
    'RENDER1G_WORKING1A_YC2A_MATRIX1A'  # old identity survives only in patch history? see below
]:
    if needle == 'RENDER1G_WORKING1A_YC2A_MATRIX1A':
        continue
    if needle not in R:
        raise SystemExit('RENDER1H TRANSFER1A renderer invariant missing: ' + needle)

for needle in [
    'M10RNativeRenderer_nativeInverseSrgbTransfer',
    'encoded <= 0.04045',
    'encoded / 12.92',
    'std::pow((encoded + 0.055) / 1.055, 2.4)',
    'p[0] = inverseSrgb[p[0]];',
    'p[1] = inverseSrgb[p[1]];',
    'p[2] = inverseSrgb[p[2]];',
    'M10RNativeRenderer_nativeEdgePass',
    'double e=v<=0.0031308 ? 12.92*v : 1.055*std::pow(v,1.0/2.4)-0.055;',
    'srgb8(outR)',
    'srgb8(outG)',
    'srgb8(outB)'
]:
    if needle not in C:
        raise SystemExit('RENDER1H TRANSFER1A native invariant missing: ' + needle)

# Ordering check in the Java renderer: edge must run before transfer, and the
# transfer must run before the Result is returned to DefaultSaver/JPEG output.
pos_edge = R.index('long edgeAffectedPixels = nativeEdgePass(bitmap, edgeIso);')
pos_transfer = R.index('long transferPixels = nativeInverseSrgbTransfer(bitmap);')
pos_status = R.index('d.put("status", "success");', pos_transfer)
if not (pos_edge < pos_transfer < pos_status):
    raise SystemExit('RENDER1H TRANSFER1A ordering invariant failed')

print('M10-R RENDER1H TRANSFER1A applied')
print(' - WORKING1A native sRGB OETF retained unchanged')
print(' - EDGE1A input domain and decode/re-encode behavior retained unchanged')
print(' - one inverse-sRGB full-frame pass added only after EDGE1A')
print(' - net JPEG coding is linear-coded for diagnostic A/B')
print(' - 8-bit OETF/inverse-OETF quantization explicitly acknowledged')
print(' - no WB, matrix, MEDIUM, DG, Yc, edge, exposure, HDR, RAW-count, or JPEG-quality change')
