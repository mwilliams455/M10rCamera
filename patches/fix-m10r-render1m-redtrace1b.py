#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix-m10r-render1m-redtrace1b.py <PhotonCamera-root>')
root = Path(sys.argv[1]).resolve()
if not (root / 'app').is_dir():
    raise SystemExit('RENDER1M REDTRACE1B: not a PhotonCamera root')

def rd(rel):
    p = root / rel
    if not p.exists():
        raise SystemExit('RENDER1M REDTRACE1B missing: ' + rel)
    return p.read_text()

def wr(rel, text):
    (root / rel).write_text(text)

def one(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit('RENDER1M REDTRACE1B anchor %s count=%d' % (label, n))
    return text.replace(old, new, 1)

# REDTRACE1B is diagnostics-only on top of RENDER1L CC1OFF1A.
#
# REDTRACE1A's global R>1 discriminator worked on a normally-lit portrait, but
# a strongly backlit portrait showed that near-white window pixels can dominate
# those counts. REDTRACE1B therefore stratifies the counterfactual CC1 effect by
# mapped luminance AND relative chroma. This isolates shadows/midtones from
# highlights and warm-chromatic samples from neutral controls.
#
# Photographic output is intentionally unchanged from RENDER1L:
#   ... MEDIUM/DG -> Yc exact inverse -> working RGB -> direct linear8 -> JPEG
# with CC1 bypassed only for the published pixels. The CC1 matrix is evaluated
# solely in the existing 1/64 diagnostic sampler.

grad = 'app/build.gradle'
g = rd(grad)
g = one(
    g,
    "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1l-cc1off1a-edge0a-nativeout1a-diag1c-saf1'",
    "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1m-redtrace1b-cc1off1a-edge0a-nativeout1a-diag1c-saf1'",
    'version')
wr(grad, g)

renderer = 'app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'
r = rd(renderer)

r = one(r,
        '            d.put("renderLook", "RENDER1L_CC1OFF1A_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A");\n',
        '''            d.put("renderLook", "RENDER1M_REDTRACE1B_CC1OFF1A_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A");\n            d.put("redTrace1BExperiment", "REDTRACE1B_LUMA_RELCHROMA_STRATIFIED_CC1_COUNTERFACTUAL");\n            d.put("redTrace1BPhotographicPixelsChanged", false);\n            d.put("redTrace1BReason", "prevent_highlight_window_pixels_from_masking_CC1_warm_midtone_behavior");\n            d.put("redTrace1BLumaBins", "shadow_[0,0.18);lowmid_[0.18,0.40);midhigh_[0.40,0.75);highlight_[0.75,+inf)");\n            d.put("redTrace1BWarmDefinition", "mappedY>0.03_and_mappedCr/mappedY>=0.04");\n            d.put("redTrace1BNeutralDefinition", "mappedY>0.03_and_abs(mappedCb/mappedY)<=0.02_and_abs(mappedCr/mappedY)<=0.02");\n''',
        'render-identity')

init_anchor = '''            final double[] redTraceExcursionSums = new double[12];\n'''
init_new = init_anchor + '''            // REDTRACE1B: 3 classes x 4 luminance bins = 12 subsets.\n            // Class 0=all, 1=warm relative chroma, 2=near-neutral relative chroma.\n            // count columns: 0=samples, 1=postYc R>1, 2=postCC1 R>1,\n            // 3=CC1-created R>1, 4=postCC1 red-only >1, 5=postCC1 B<0.\n            final long[][] redTrace1BCounts = new long[12][6];\n            // sum columns: mappedY, relCb, relCr, postYc RGB, postCC1 RGB,\n            // and CC1 delta RGB.\n            final double[][] redTrace1BSums = new double[12][12];\n'''
r = one(r, init_anchor, init_new, 'trace1b-init')

sample_anchor = '''                    toneDgStats.preSrgb.add(outR, outG, outB);\n'''
sample_new = '''                    // REDTRACE1B: classify by mapped luminance and relative\n                    // chroma so a clipped/near-white window cannot overwhelm\n                    // the portrait/midtone discriminator. Relative chroma is\n                    // stable under the current Yc policy because Cb/Cr and Y\n                    // are scaled by the same yRatio. Diagnostics only.\n                    final double relCb1B = Math.abs(mappedY) > 1.0e-9 ? mappedCb / mappedY : 0.0;\n                    final double relCr1B = Math.abs(mappedY) > 1.0e-9 ? mappedCr / mappedY : 0.0;\n                    final int yBin1B = mappedY < 0.18 ? 0 : (mappedY < 0.40 ? 1 : (mappedY < 0.75 ? 2 : 3));\n                    final boolean warm1B = mappedY > 0.03 && relCr1B >= 0.04;\n                    final boolean neutral1B = mappedY > 0.03 && Math.abs(relCb1B) <= 0.02 && Math.abs(relCr1B) <= 0.02;\n                    final double dR1B = outR - nr;\n                    final double dG1B = outG - ng;\n                    final double dB1B = outB - nb;\n                    for (int cls1B = 0; cls1B < 3; cls1B++) {\n                        if (cls1B == 1 && !warm1B) continue;\n                        if (cls1B == 2 && !neutral1B) continue;\n                        int idx1B = cls1B * 4 + yBin1B;\n                        long[] bc1B = redTrace1BCounts[idx1B];\n                        double[] bs1B = redTrace1BSums[idx1B];\n                        bc1B[0]++;\n                        if (nr > 1.0) bc1B[1]++;\n                        if (outR > 1.0) bc1B[2]++;\n                        if (outR > 1.0 && nr <= 1.0) bc1B[3]++;\n                        if (outR > 1.0 && outG <= 1.0 && outB <= 1.0) bc1B[4]++;\n                        if (outB < 0.0) bc1B[5]++;\n                        bs1B[0] += mappedY;\n                        bs1B[1] += relCb1B;\n                        bs1B[2] += relCr1B;\n                        bs1B[3] += nr;\n                        bs1B[4] += ng;\n                        bs1B[5] += nb;\n                        bs1B[6] += outR;\n                        bs1B[7] += outG;\n                        bs1B[8] += outB;\n                        bs1B[9] += dR1B;\n                        bs1B[10] += dG1B;\n                        bs1B[11] += dB1B;\n                    }\n                    toneDgStats.preSrgb.add(outR, outG, outB);\n'''
r = one(r, sample_anchor, sample_new, 'trace1b-sample')

json_anchor = '''            d.put("redTrace1A", redTrace);\n'''
json_new = json_anchor + '''            JSONObject redTrace1B = new JSONObject();\n            redTrace1B.put("sampleStride", 64);\n            redTrace1B.put("diagnosticOnly", true);\n            redTrace1B.put("photographicOutputStillCc1Bypassed", true);\n            redTrace1B.put("counterfactualCc1StillEvaluated", true);\n            redTrace1B.put("lumaBinEdges", "0.18,0.40,0.75");\n            redTrace1B.put("relativeChromaBasis", "mappedCb_over_mappedY_and_mappedCr_over_mappedY");\n            redTrace1B.put("warmThresholdRelCr", 0.04);\n            redTrace1B.put("neutralAbsRelCbCrThreshold", 0.02);\n            String[] rt1bClassNames = new String[]{"all", "warmRelCr", "neutralRelChroma"};\n            String[] rt1bBinNames = new String[]{"shadow", "lowMid", "midHigh", "highlight"};\n            for (int cls1B = 0; cls1B < 3; cls1B++) {\n                JSONObject classJson1B = new JSONObject();\n                for (int bin1B = 0; bin1B < 4; bin1B++) {\n                    int idx1B = cls1B * 4 + bin1B;\n                    long[] bc1B = redTrace1BCounts[idx1B];\n                    double[] bs1B = redTrace1BSums[idx1B];\n                    long n1B = bc1B[0];\n                    JSONObject binJson1B = new JSONObject();\n                    binJson1B.put("count", n1B);\n                    binJson1B.put("postYcRedAbove1Count", bc1B[1]);\n                    binJson1B.put("postCc1RedAbove1Count", bc1B[2]);\n                    binJson1B.put("cc1CreatedRedAbove1Count", bc1B[3]);\n                    binJson1B.put("postCc1RedOnlyAbove1Count", bc1B[4]);\n                    binJson1B.put("postCc1BlueBelow0Count", bc1B[5]);\n                    binJson1B.put("cc1CreatedRedAbove1FractionOfSubset", n1B > 0 ? bc1B[3] / (double)n1B : 0.0);\n                    if (n1B > 0) {\n                        binJson1B.put("meanMappedY", bs1B[0] / n1B);\n                        binJson1B.put("meanRelCb", bs1B[1] / n1B);\n                        binJson1B.put("meanRelCr", bs1B[2] / n1B);\n                        binJson1B.put("meanPostYcR", bs1B[3] / n1B);\n                        binJson1B.put("meanPostYcG", bs1B[4] / n1B);\n                        binJson1B.put("meanPostYcB", bs1B[5] / n1B);\n                        binJson1B.put("meanCounterfactualPostCc1R", bs1B[6] / n1B);\n                        binJson1B.put("meanCounterfactualPostCc1G", bs1B[7] / n1B);\n                        binJson1B.put("meanCounterfactualPostCc1B", bs1B[8] / n1B);\n                        binJson1B.put("meanCc1DeltaR", bs1B[9] / n1B);\n                        binJson1B.put("meanCc1DeltaG", bs1B[10] / n1B);\n                        binJson1B.put("meanCc1DeltaB", bs1B[11] / n1B);\n                    }\n                    classJson1B.put(rt1bBinNames[bin1B], binJson1B);\n                }\n                redTrace1B.put(rt1bClassNames[cls1B], classJson1B);\n            }\n            d.put("redTrace1B", redTrace1B);\n'''
r = one(r, json_anchor, json_new, 'trace1b-json')
wr(renderer, r)

# Hard proof that REDTRACE1B changes diagnostics only and preserves RENDER1L
# photographic output: CC1 stays bypassed in native code, direct linear8 stays
# live, and transfer/edge remain off.
G = rd(grad)
R = rd(renderer)
C = rd('app/src/main/cpp/m10rRender.cpp')

if "render1m-redtrace1b-cc1off1a-edge0a-nativeout1a-diag1c-saf1'" not in G:
    raise SystemExit('RENDER1M REDTRACE1B build identity missing')

for needle in [
    'RENDER1M_REDTRACE1B_CC1OFF1A_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A',
    'REDTRACE1B_LUMA_RELCHROMA_STRATIFIED_CC1_COUNTERFACTUAL',
    'redTrace1BPhotographicPixelsChanged", false',
    'prevent_highlight_window_pixels_from_masking_CC1_warm_midtone_behavior',
    'warmThresholdRelCr',
    'neutralAbsRelCbCrThreshold',
    'meanCc1DeltaR',
    'meanCc1DeltaG',
    'meanCc1DeltaB',
    'cc1AppliedToPhotographicPixels", false',
    'cc1CounterfactualRedTraceRetained", true',
    'CC1OFF1A_bypassed_post_Yc_before_direct_8bit_output',
    'NATIVEOUT1A_DIRECT_POST_YC_WORKING_LINEAR8_CC1OFF1A',
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
        raise SystemExit('RENDER1M REDTRACE1B renderer invariant missing: ' + needle)

for needle in [
    'const double outR = nr;',
    'const double outG = ng;',
    'const double outB = nb;',
    'linear8(outR)', 'linear8(outG)', 'linear8(outB)',
    'jdouble src[9], workingMat[9], outMat[9];',
    'env->GetDoubleArrayRegion(joutMat, 0, 9, outMat);'
]:
    if needle not in C:
        raise SystemExit('RENDER1M REDTRACE1B native invariant missing: ' + needle)

for needle in [
    'const double outR = outMat[0]*nr + outMat[1]*ng + outMat[2]*nb;',
    'const double outG = outMat[3]*nr + outMat[4]*ng + outMat[5]*nb;',
    'const double outB = outMat[6]*nr + outMat[7]*ng + outMat[8]*nb;'
]:
    if needle in C:
        raise SystemExit('RENDER1M REDTRACE1B unexpectedly restored native CC1: ' + needle)

# Java's matrix multiplication MUST still exist as counterfactual diagnostics.
for needle in [
    'double outR = workingToSrgb[0]*nr + workingToSrgb[1]*ng + workingToSrgb[2]*nb;',
    'double outG = workingToSrgb[3]*nr + workingToSrgb[4]*ng + workingToSrgb[5]*nb;',
    'double outB = workingToSrgb[6]*nr + workingToSrgb[7]*ng + workingToSrgb[8]*nb;'
]:
    if needle not in R:
        raise SystemExit('RENDER1M REDTRACE1B counterfactual CC1 diagnostic missing: ' + needle)

if 'nativeInverseSrgbTransfer(bitmap)' in R or 'nativeEdgePass(bitmap, edgeIso)' in R:
    raise SystemExit('RENDER1M REDTRACE1B unexpectedly re-enabled transfer/edge pass')

print('M10-R RENDER1M REDTRACE1B applied')
print(' - photographic pixels are byte-for-byte arithmetic-equivalent to RENDER1L CC1OFF1A')
print(' - counterfactual CC1 diagnostics split into 4 mapped-Y bins')
print(' - warm relative-Cr and near-neutral subsets are reported separately')
print(' - mean pre/post CC1 RGB and CC1 deltas are reported per subset')
print(' - highlight-window domination of global R>1 counts is explicitly separated')
print(' - no WB/CA9, matrix, WORKING1A, MEDIUM/DG, Yc, output, edge, exposure or JPEG change')
