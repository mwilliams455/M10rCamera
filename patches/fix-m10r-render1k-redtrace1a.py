#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix-m10r-render1k-redtrace1a.py <PhotonCamera-root>')
root = Path(sys.argv[1]).resolve()
if not (root / 'app').is_dir():
    raise SystemExit('RENDER1K REDTRACE1A: not a PhotonCamera root')

def rd(rel):
    p = root / rel
    if not p.exists():
        raise SystemExit('RENDER1K REDTRACE1A missing: ' + rel)
    return p.read_text()

def wr(rel, text):
    (root / rel).write_text(text)

def one(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit('RENDER1K REDTRACE1A anchor %s count=%d' % (label, n))
    return text.replace(old, new, 1)

# REDTRACE1A is diagnostics-only on top of RENDER1J NATIVEOUT1A.
# The device sample that triggered this trace showed a strong red-only excursion:
# post-CC1 sampled R exceeds 1.0 while G/B do not.  This patch measures where
# that excursion appears without touching any photographic pixel arithmetic.
#
# Trace points (1/64 sampled diagnostic path already present):
#   working RGB before Yc -> Y/Cb/Cr -> mapped Y + relative chroma ->
#   exact Yc inverse (postYcWorking) -> CC1 output (postCC1 / existing preSrgb)
#
# The key discriminator is whether R > 1.0 already exists after Yc inverse or
# is newly created by CC1.  We also record the mapped chroma statistics for the
# red-excursion subset.  No gamut fix is applied in this build.

grad = 'app/build.gradle'
g = rd(grad)
g = one(
    g,
    "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1j-edge0a-nativeout1a-diag1c-saf1'",
    "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1k-redtrace1a-edge0a-nativeout1a-diag1c-saf1'",
    'version')
wr(grad, g)

renderer = 'app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'
r = rd(renderer)

r = one(r,
        '            d.put("renderLook", "RENDER1J_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A");\n',
        '''            d.put("renderLook", "RENDER1K_REDTRACE1A_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A");\n            d.put("redTraceExperiment", "REDTRACE1A_YC_INVERSE_VS_CC1_EXCURSION");\n            d.put("redTracePhotographicPixelsChanged", false);\n            d.put("redTraceSamplingStride", 64);\n            d.put("redTracePurpose", "locate_red_above_one_before_or_after_CC1_without_colour_tuning");\n''',
        'render-identity')

init_anchor = '''            final long[] sampledNeutralClipScratch = new long[3];\n'''
init_new = init_anchor + '''            // REDTRACE1A sampled counters.  Arrays are final so the existing\n            // tile loop can mutate them without adding any output-path state.\n            // counts: 0=samples, 1..3=postYc RGB >1, 4..6=postCC1 RGB >1,\n            // 7=CC1-created R>1, 8=R>1 already postYc and still >1 postCC1,\n            // 9=postCC1 red-only >1, 10=postCC1 B<0, 11=postYc B<0.\n            final long[] redTraceCounts = new long[12];\n            // For samples where postCC1 R>1: mappedY,Cb,Cr,yRatio, postYc RGB,\n            // postCC1 RGB, input Cb, input Cr.\n            final double[] redTraceExcursionSums = new double[12];\n'''
r = one(r, init_anchor, init_new, 'trace-init')

sample_anchor = '''                    double outR = workingToSrgb[0]*nr + workingToSrgb[1]*ng + workingToSrgb[2]*nb;\n                    double outG = workingToSrgb[3]*nr + workingToSrgb[4]*ng + workingToSrgb[5]*nb;\n                    double outB = workingToSrgb[6]*nr + workingToSrgb[7]*ng + workingToSrgb[8]*nb;\n                    toneDgStats.preSrgb.add(outR, outG, outB);\n'''
sample_new = '''                    double outR = workingToSrgb[0]*nr + workingToSrgb[1]*ng + workingToSrgb[2]*nb;\n                    double outG = workingToSrgb[3]*nr + workingToSrgb[4]*ng + workingToSrgb[5]*nb;\n                    double outB = workingToSrgb[6]*nr + workingToSrgb[7]*ng + workingToSrgb[8]*nb;\n\n                    // REDTRACE1A: diagnostics only.  The native output pixels are\n                    // already formed above by nativeProcessTile; none of these\n                    // counters feed back into rendering.\n                    redTraceCounts[0]++;\n                    if (nr > 1.0) redTraceCounts[1]++;\n                    if (ng > 1.0) redTraceCounts[2]++;\n                    if (nb > 1.0) redTraceCounts[3]++;\n                    if (outR > 1.0) redTraceCounts[4]++;\n                    if (outG > 1.0) redTraceCounts[5]++;\n                    if (outB > 1.0) redTraceCounts[6]++;\n                    if (outR > 1.0 && nr <= 1.0) redTraceCounts[7]++;\n                    if (outR > 1.0 && nr > 1.0) redTraceCounts[8]++;\n                    if (outR > 1.0 && outG <= 1.0 && outB <= 1.0) redTraceCounts[9]++;\n                    if (outB < 0.0) redTraceCounts[10]++;\n                    if (nb < 0.0) redTraceCounts[11]++;\n                    if (outR > 1.0) {\n                        redTraceExcursionSums[0] += mappedY;\n                        redTraceExcursionSums[1] += mappedCb;\n                        redTraceExcursionSums[2] += mappedCr;\n                        redTraceExcursionSums[3] += yRatio;\n                        redTraceExcursionSums[4] += nr;\n                        redTraceExcursionSums[5] += ng;\n                        redTraceExcursionSums[6] += nb;\n                        redTraceExcursionSums[7] += outR;\n                        redTraceExcursionSums[8] += outG;\n                        redTraceExcursionSums[9] += outB;\n                        redTraceExcursionSums[10] += ycCb;\n                        redTraceExcursionSums[11] += ycCr;\n                    }\n                    toneDgStats.preSrgb.add(outR, outG, outB);\n'''
r = one(r, sample_anchor, sample_new, 'sample-trace')

json_anchor = '''            d.put("toneDg1aSignalStatistics", toneDgStats.json());\n'''
json_new = json_anchor + '''            JSONObject redTrace = new JSONObject();\n            long rtN = redTraceCounts[0];\n            long rtR = redTraceCounts[4];\n            redTrace.put("sampleCount", rtN);\n            redTrace.put("postYcWorkingAbove1RGB", json(new long[]{redTraceCounts[1], redTraceCounts[2], redTraceCounts[3]}));\n            redTrace.put("postCc1Above1RGB", json(new long[]{redTraceCounts[4], redTraceCounts[5], redTraceCounts[6]}));\n            redTrace.put("cc1CreatedRedAbove1Count", redTraceCounts[7]);\n            redTrace.put("redAlreadyAbove1PostYcAndStillAbovePostCc1Count", redTraceCounts[8]);\n            redTrace.put("postCc1RedOnlyAbove1Count", redTraceCounts[9]);\n            redTrace.put("postCc1BlueBelow0Count", redTraceCounts[10]);\n            redTrace.put("postYcBlueBelow0Count", redTraceCounts[11]);\n            redTrace.put("postCc1RedAbove1Fraction", rtN > 0 ? redTraceCounts[4] / (double)rtN : 0.0);\n            redTrace.put("cc1CreatedShareOfPostCc1RedAbove1", rtR > 0 ? redTraceCounts[7] / (double)rtR : 0.0);\n            redTrace.put("redOnlyShareOfPostCc1RedAbove1", rtR > 0 ? redTraceCounts[9] / (double)rtR : 0.0);\n            redTrace.put("cc1Matrix", "1.3895,-0.1693,-0.2202;-0.2288,1.2317,-0.0029;-0.0176,-0.0963,1.1139");\n            redTrace.put("cc1RedEquation", "outR=1.3895*postYcR-0.1693*postYcG-0.2202*postYcB");\n            JSONObject exc = new JSONObject();\n            exc.put("count", rtR);\n            if (rtR > 0) {\n                exc.put("meanMappedY", redTraceExcursionSums[0] / rtR);\n                exc.put("meanMappedCb", redTraceExcursionSums[1] / rtR);\n                exc.put("meanMappedCr", redTraceExcursionSums[2] / rtR);\n                exc.put("meanYRatio", redTraceExcursionSums[3] / rtR);\n                exc.put("meanPostYcR", redTraceExcursionSums[4] / rtR);\n                exc.put("meanPostYcG", redTraceExcursionSums[5] / rtR);\n                exc.put("meanPostYcB", redTraceExcursionSums[6] / rtR);\n                exc.put("meanPostCc1R", redTraceExcursionSums[7] / rtR);\n                exc.put("meanPostCc1G", redTraceExcursionSums[8] / rtR);\n                exc.put("meanPostCc1B", redTraceExcursionSums[9] / rtR);\n                exc.put("meanInputCb", redTraceExcursionSums[10] / rtR);\n                exc.put("meanInputCr", redTraceExcursionSums[11] / rtR);\n            }\n            redTrace.put("redExcursionSubset", exc);\n            redTrace.put("diagnosticOnly", true);\n            d.put("redTrace1A", redTrace);\n'''
r = one(r, json_anchor, json_new, 'trace-json')
wr(renderer, r)

# Hard proof that REDTRACE1A did not alter photographic output arithmetic.
R = rd(renderer)
C = rd('app/src/main/cpp/m10rRender.cpp')
G = rd(grad)
if "render1k-redtrace1a-edge0a-nativeout1a-diag1c-saf1'" not in G:
    raise SystemExit('RENDER1K REDTRACE1A build identity missing')
for needle in [
    'RENDER1K_REDTRACE1A_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A',
    'REDTRACE1A_YC_INVERSE_VS_CC1_EXCURSION',
    'redTracePhotographicPixelsChanged", false',
    'cc1CreatedRedAbove1Count',
    'postCc1RedOnlyAbove1Count',
    'redExcursionSubset',
    'NATIVEOUT1A_DIRECT_POST_CC1_LINEAR8',
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
        raise SystemExit('RENDER1K REDTRACE1A renderer invariant missing: ' + needle)
for needle in [
    'linear8(outR)', 'linear8(outG)', 'linear8(outB)',
    'const double yRatio = y > 1.0e-12 ? mappedY / y : 0.0;',
    'const double mappedCb = cb * yRatio;',
    'const double mappedCr = cr * yRatio;',
    'const double outR = outMat[0]*nr + outMat[1]*ng + outMat[2]*nb;'
]:
    if needle not in C:
        raise SystemExit('RENDER1K REDTRACE1A native invariant missing: ' + needle)
if 'nativeInverseSrgbTransfer(bitmap)' in R or 'nativeEdgePass(bitmap, edgeIso)' in R:
    raise SystemExit('RENDER1K REDTRACE1A unexpectedly re-enabled transfer/edge pass')

print('M10-R RENDER1K REDTRACE1A applied')
print(' - diagnostic-only trace around Yc inverse and CC1')
print(' - counts whether post-CC1 red excursions are created by CC1 vs already present post-Yc')
print(' - records mapped chroma means for the red-excursion subset')
print(' - NATIVEOUT1A, EDGE0A, WB/CA9, matrices, MEDIUM/DG, Yc, exposure and JPEG pixels unchanged')
