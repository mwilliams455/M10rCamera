#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix-m10r-render1n-yblend1a.py <PhotonCamera-root>')
root = Path(sys.argv[1]).resolve()
if not (root / 'app').is_dir():
    raise SystemExit('RENDER1N YBLEND1A: not a PhotonCamera root')

def rd(rel):
    p = root / rel
    if not p.exists():
        raise SystemExit('RENDER1N YBLEND1A missing: ' + rel)
    return p.read_text()

def wr(rel, text):
    (root / rel).write_text(text)

def one(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit('RENDER1N YBLEND1A anchor %s count=%d' % (label, n))
    return text.replace(old, new, 1)

# Controlled falsification test on top of frozen RENDER1M REDTRACE1B.
#
# RENDER1M's live reconstruction is now pinned exactly:
#   yRatio  = mappedY / inputY
#   mappedCb = Cb * yRatio
#   mappedCr = Cr * yRatio
# so MEDIUM/DG's large Y expansion is inherited 100% by chroma.
#
# YBLEND1A keeps mappedY byte-for-byte on the same MEDIUM/DG path and changes
# ONLY the chroma carrier scale to the midpoint between the already-tested
# absolute-CbCr policy (scale=1) and RENDER1M relative-chroma policy
# (scale=yRatio):
#
#   chromaCarrierY = 0.5 * (inputY + mappedY)
#   chromaScale    = chromaCarrierY / inputY
#                  = 0.5 * (1 + mappedY/inputY)
#
# This is an experiment, NOT a claim that the decoded Leica Y_BLEND block uses
# this formula. The point is to test whether full inheritance of the tone gain
# is responsible for the warm/red inflation while leaving luminance untouched.

grad = 'app/build.gradle'
g = rd(grad)
g = one(
    g,
    "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1m-redtrace1b-cc1off1a-edge0a-nativeout1a-diag1c-saf1'",
    "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1n-yblend1a-redtrace1b-cc1off1a-edge0a-nativeout1a-diag1c-saf1'",
    'version')
wr(grad, g)

renderer = 'app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'
r = rd(renderer)

r = one(
    r,
    '            d.put("renderLook", "RENDER1M_REDTRACE1B_CC1OFF1A_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A");\n',
    '''            d.put("renderLook", "RENDER1N_YBLEND1A_REDTRACE1B_CC1OFF1A_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A");\n            d.put("chromaReconstructionExperiment", "YBLEND1A");\n            d.put("yBlend1AExperimentalApplied", true);\n            d.put("yBlend1AFirmwareClaim", false);\n            d.put("yBlend1AInputY", "pre_MEDIUM_DG_Yc_Y");\n            d.put("yBlend1AMappedY", "unchanged_dy_over_DG_OUT_MAX");\n            d.put("yBlend1AOldChromaScale", "mappedY_over_inputY");\n            d.put("yBlend1ANewChromaScale", "0.5_times_(1_plus_mappedY_over_inputY)");\n            d.put("yBlend1AChromaCarrierY", "0.5_times_(inputY_plus_mappedY)");\n            d.put("yBlend1ALumaArithmeticChanged", false);\n            d.put("yBlend1AMediumDgChanged", false);\n''',
    'render-identity')

r = one(
    r,
    'd.put("nonlinearApplicationMode", "M10R_Yc_Convert_map_Y_preserve_relative_chroma_exact_inverse");',
    'd.put("nonlinearApplicationMode", "M10R_Yc_Convert_map_Y_YBLEND1A_midpoint_chroma_exact_inverse");',
    'application-mode')
r = one(
    r,
    'd.put("b2yChromaPolicy", "preserve_Cb_over_Y_and_Cr_over_Y_through_MEDIUM_DG_then_exact_matrix_inverse");',
    'd.put("b2yChromaPolicy", "YBLEND1A_midpoint_between_absolute_and_relative_chroma_then_exact_matrix_inverse");',
    'chroma-policy')
r = one(
    r,
    'd.put("lumaGainStatisticSemantic", "mappedY_over_inputY_also_used_as_relative_chroma_scale");',
    'd.put("lumaGainStatisticSemantic", "mappedY_over_inputY_retained_as_diagnostic_old_scale;_YBLEND1A_applies_halfway_scale_to_chroma_only");',
    'gain-semantic')

# Java 1/64 diagnostic sampler: mirror the native photographic arithmetic.
old_java = '''                    double yRatio = (ycY > 1.0e-12) ? (mappedY / ycY) : 0.0;\n                    toneDgStats.lumaGain.add(yRatio);\n                    double mappedCb = ycCb * yRatio;\n                    double mappedCr = ycCr * yRatio;\n'''
new_java = '''                    double yRatio = (ycY > 1.0e-12) ? (mappedY / ycY) : 0.0;\n                    toneDgStats.lumaGain.add(yRatio);\n                    // RENDER1N YBLEND1A: mappedY is unchanged. Only the chroma\n                    // carrier scale moves halfway from absolute (1.0) to the\n                    // frozen RENDER1M relative scale (yRatio). Preserve the old\n                    // zero-Y guard so near-black behavior is not broadened.\n                    double yBlendChromaScale = (ycY > 1.0e-12) ? (0.5 * (1.0 + yRatio)) : 0.0;\n                    double mappedCb = ycCb * yBlendChromaScale;\n                    double mappedCr = ycCr * yBlendChromaScale;\n'''
r = one(r, old_java, new_java, 'java-chroma-scale')

init_anchor = '''            final double[][] redTrace1BSums = new double[12][12];\n'''
init_new = init_anchor + '''            // YBLEND1A proof sampler, same stride as REDTRACE1B.\n            // 3 classes x 4 mapped-Y bins. Class 0=all; 1=warm by INPUT Cr/Y;\n            // 2=near-neutral by INPUT Cb/Y and Cr/Y. Input-relative classes are\n            // invariant to the experiment, making RENDER1M/1N comparisons clean.\n            final long[][] yBlend1ACounts = new long[12][2];\n            // sum columns: inputY, mappedY, oldScale, appliedScale, originalCb,\n            // originalCr, reconstructedCb, reconstructedCr, postRecon R/G/B.\n            final double[][] yBlend1ASums = new double[12][11];\n'''
r = one(r, init_anchor, init_new, 'yblend-init')

sample_anchor = '''                    // REDTRACE1B: classify by mapped luminance and relative\n'''
sample_new = '''                    // YBLEND1A diagnostics classify warm/neutral on the PRE-MAP\n                    // Yc ratios, so membership does not move merely because this\n                    // experiment changed the chroma carrier scale.\n                    final double ybInputRelCb = Math.abs(ycY) > 1.0e-9 ? ycCb / ycY : 0.0;\n                    final double ybInputRelCr = Math.abs(ycY) > 1.0e-9 ? ycCr / ycY : 0.0;\n                    final int ybBin = mappedY < 0.18 ? 0 : (mappedY < 0.40 ? 1 : (mappedY < 0.75 ? 2 : 3));\n                    final boolean ybWarm = ycY > 0.03 && ybInputRelCr >= 0.04;\n                    final boolean ybNeutral = ycY > 0.03 && Math.abs(ybInputRelCb) <= 0.02 && Math.abs(ybInputRelCr) <= 0.02;\n                    for (int ybCls = 0; ybCls < 3; ybCls++) {\n                        if (ybCls == 1 && !ybWarm) continue;\n                        if (ybCls == 2 && !ybNeutral) continue;\n                        final int ybIdx = ybCls * 4 + ybBin;\n                        final long[] ybc = yBlend1ACounts[ybIdx];\n                        final double[] ybs = yBlend1ASums[ybIdx];\n                        ybc[0]++;\n                        if (yBlendChromaScale + 1.0e-12 < yRatio) ybc[1]++;\n                        ybs[0] += ycY;\n                        ybs[1] += mappedY;\n                        ybs[2] += yRatio;\n                        ybs[3] += yBlendChromaScale;\n                        ybs[4] += ycCb;\n                        ybs[5] += ycCr;\n                        ybs[6] += mappedCb;\n                        ybs[7] += mappedCr;\n                        ybs[8] += nr;\n                        ybs[9] += ng;\n                        ybs[10] += nb;\n                    }\n\n                    // REDTRACE1B: classify by mapped luminance and relative\n'''
r = one(r, sample_anchor, sample_new, 'yblend-sample')

json_anchor = '''            d.put("redTrace1B", redTrace1B);\n'''
json_new = json_anchor + '''            JSONObject yBlend1A = new JSONObject();\n            yBlend1A.put("sampleStride", 64);\n            yBlend1A.put("experimentalOnly", true);\n            yBlend1A.put("firmwareFormulaClaim", false);\n            yBlend1A.put("mappedYFormula", "dy_over_DG_OUT_MAX_UNCHANGED_FROM_RENDER1M");\n            yBlend1A.put("oldChromaScaleFormula", "mappedY_over_inputY");\n            yBlend1A.put("appliedChromaScaleFormula", "0.5_times_(1_plus_mappedY_over_inputY)");\n            yBlend1A.put("zeroYGuard", "scale_zero_when_inputY_le_1e-12");\n            yBlend1A.put("classificationBasis", "pre_map_input_Cb_over_Y_and_Cr_over_Y");\n            yBlend1A.put("lumaBinEdges", "0.18,0.40,0.75");\n            String[] ybClassNames = new String[]{"all", "warmInputRelCr", "neutralInputRelChroma"};\n            String[] ybBinNames = new String[]{"shadow", "lowMid", "midHigh", "highlight"};\n            for (int ybCls = 0; ybCls < 3; ybCls++) {\n                JSONObject ybClass = new JSONObject();\n                for (int ybBin = 0; ybBin < 4; ybBin++) {\n                    final int ybIdx = ybCls * 4 + ybBin;\n                    final long[] ybc = yBlend1ACounts[ybIdx];\n                    final double[] ybs = yBlend1ASums[ybIdx];\n                    final long yn = ybc[0];\n                    JSONObject ybj = new JSONObject();\n                    ybj.put("count", yn);\n                    ybj.put("chromaScaleReducedVsRender1MCount", ybc[1]);\n                    ybj.put("chromaScaleReducedVsRender1MFraction", yn > 0 ? ybc[1] / (double)yn : 0.0);\n                    if (yn > 0) {\n                        ybj.put("meanInputY", ybs[0] / yn);\n                        ybj.put("meanMappedY", ybs[1] / yn);\n                        ybj.put("meanRender1MChromaScale", ybs[2] / yn);\n                        ybj.put("meanYBlend1AAppliedChromaScale", ybs[3] / yn);\n                        ybj.put("meanOriginalCb", ybs[4] / yn);\n                        ybj.put("meanOriginalCr", ybs[5] / yn);\n                        ybj.put("meanReconstructedCb", ybs[6] / yn);\n                        ybj.put("meanReconstructedCr", ybs[7] / yn);\n                        ybj.put("meanPostReconR", ybs[8] / yn);\n                        ybj.put("meanPostReconG", ybs[9] / yn);\n                        ybj.put("meanPostReconB", ybs[10] / yn);\n                    }\n                    ybClass.put(ybBinNames[ybBin], ybj);\n                }\n                yBlend1A.put(ybClassNames[ybCls], ybClass);\n            }\n            d.put("yBlend1A", yBlend1A);\n'''
r = one(r, json_anchor, json_new, 'yblend-json')
wr(renderer, r)

# Native photographic path: alter only Cb/Cr scale; leave mappedY and inverse
# Y column untouched.
cpp = 'app/src/main/cpp/m10rRender.cpp'
c = rd(cpp)
old_cpp = '''            const double yRatio = y > 1.0e-12 ? mappedY / y : 0.0;\n            const double mappedCb = cb * yRatio;\n            const double mappedCr = cr * yRatio;\n'''
new_cpp = '''            const double yRatio = y > 1.0e-12 ? mappedY / y : 0.0;\n            // RENDER1N YBLEND1A controlled reconstruction experiment. mappedY\n            // remains exactly the frozen MEDIUM/DG output. Only Cb/Cr use the\n            // midpoint carrier between input Y and mapped Y.\n            const double yBlendChromaScale = y > 1.0e-12 ? 0.5 * (1.0 + yRatio) : 0.0;\n            const double mappedCb = cb * yBlendChromaScale;\n            const double mappedCr = cr * yBlendChromaScale;\n'''
c = one(c, old_cpp, new_cpp, 'native-chroma-scale')
wr(cpp, c)

# Hard gates: prove frozen luma/output architecture and the single intended
# photographic arithmetic change.
G = rd(grad)
R = rd(renderer)
C = rd(cpp)

for needle in [
    "render1n-yblend1a-redtrace1b-cc1off1a-edge0a-nativeout1a-diag1c-saf1'",
]:
    if needle not in G:
        raise SystemExit('RENDER1N YBLEND1A build identity missing: ' + needle)

for needle in [
    'RENDER1N_YBLEND1A_REDTRACE1B_CC1OFF1A_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A',
    'chromaReconstructionExperiment", "YBLEND1A',
    'yBlend1AExperimentalApplied", true',
    'yBlend1AFirmwareClaim", false',
    'yBlend1ALumaArithmeticChanged", false',
    'yBlend1AMediumDgChanged", false',
    'meanRender1MChromaScale',
    'meanYBlend1AAppliedChromaScale',
    'cc1AppliedToPhotographicPixels", false',
    'textbookSrgbOetfApplied", false',
    'transfer1aInverseExecuted", false',
    'edgePassEnabled", false',
    'edgeCallExecuted", false',
    'workingBasisPlacementFix", "WORKING1A"',
    'yc2aMatrixCorrectionApplied", true',
    'b2yYBlendApplied", false',
    'hdrEnabled", false',
    'sourceFrameCount", 1'
]:
    if needle not in R:
        raise SystemExit('RENDER1N YBLEND1A renderer invariant missing: ' + needle)

for needle in [
    'const double mappedY = dy / static_cast<double>(DG_OUT_MAX);',
    'const double yRatio = y > 1.0e-12 ? mappedY / y : 0.0;',
    'const double yBlendChromaScale = y > 1.0e-12 ? 0.5 * (1.0 + yRatio) : 0.0;',
    'const double mappedCb = cb * yBlendChromaScale;',
    'const double mappedCr = cr * yBlendChromaScale;',
    'const double nr = 1.000000000000*mappedY - 0.001043337611*mappedCb + 1.401991725445*mappedCr;',
    'const double ng = 1.000000000000*mappedY - 0.345114690199*mappedCb - 0.714098755336*mappedCr;',
    'const double nb = 1.000000000000*mappedY + 1.770975790582*mappedCb - 0.000124867533*mappedCr;',
    'const double outR = nr;',
    'const double outG = ng;',
    'const double outB = nb;',
    'linear8(outR)', 'linear8(outG)', 'linear8(outB)'
]:
    if needle not in C:
        raise SystemExit('RENDER1N YBLEND1A native invariant missing: ' + needle)

# Old full relative-chroma multiplication must be gone from both live native
# output and Java diagnostic mirror.
for needle in [
    'const double mappedCb = cb * yRatio;',
    'const double mappedCr = cr * yRatio;',
    'double mappedCb = ycCb * yRatio;',
    'double mappedCr = ycCr * yRatio;'
]:
    if needle in C or needle in R:
        raise SystemExit('RENDER1N old full relative-chroma scale remains: ' + needle)

# No transfer/edge/CC1 restoration.
if 'nativeInverseSrgbTransfer(bitmap)' in R or 'nativeEdgePass(bitmap, edgeIso)' in R:
    raise SystemExit('RENDER1N unexpectedly re-enabled transfer/edge')
for needle in [
    'const double outR = outMat[0]*nr + outMat[1]*ng + outMat[2]*nb;',
    'const double outG = outMat[3]*nr + outMat[4]*ng + outMat[5]*nb;',
    'const double outB = outMat[6]*nr + outMat[7]*ng + outMat[8]*nb;'
]:
    if needle in C:
        raise SystemExit('RENDER1N unexpectedly restored CC1 to photographic output: ' + needle)

print('M10-R RENDER1N YBLEND1A applied')
print(' - live RENDER1M reconstruction pinned: mappedCb/Cr = Cb/Cr * (mappedY/inputY)')
print(' - mappedY / MEDIUM / DG arithmetic unchanged')
print(' - chroma-only test scale = 0.5 * (1 + mappedY/inputY) for positive input Y')
print(' - exact YC2A inverse, CC1OFF1A, EDGE0A and NATIVEOUT1A retained')
print(' - diagnostic sidecar records old vs applied scale and input/mapped Y by luma/chroma class')
print(' - experimental only; no claim that Leica firmware Y_BLEND uses this midpoint formula')
