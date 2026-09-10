#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix-m10r-render1l-cc1off1a.py <PhotonCamera-root>')
root = Path(sys.argv[1]).resolve()
if not (root / 'app').is_dir():
    raise SystemExit('RENDER1L CC1OFF1A: not a PhotonCamera root')

def rd(rel):
    p = root / rel
    if not p.exists():
        raise SystemExit('RENDER1L CC1OFF1A missing: ' + rel)
    return p.read_text()

def wr(rel, text):
    (root / rel).write_text(text)

def one(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit('RENDER1L CC1OFF1A anchor %s count=%d' % (label, n))
    return text.replace(old, new, 1)

# CC1OFF1A is a one-variable photographic positive control following REDTRACE1A.
# Device REDTRACE1A showed that CC1 creates the large majority of sampled red
# excursions while preserving the neutral axis.  This build therefore bypasses
# CC1 ONLY for photographic pixel publication:
#
#   ... MEDIUM/DG -> Yc exact inverse -> working RGB -> direct linear8 -> JPEG
#
# The CC1 matrix and REDTRACE1A counterfactual calculations remain resident and
# diagnostic-only.  This is NOT a proposal to remove CC1 from the final M10-R
# architecture; it is the cleanest device A/B to prove whether CC1 semantics,
# domain, or downstream gamut handling are responsible for the visible warm/red
# expansion.  RAW/source calibration, WB/CA9, working basis, MEDIUM/DG, Yc,
# NATIVEOUT1A, EDGE0A, exposure, JPEG quality, single RAW and HDR-off are frozen.

grad = 'app/build.gradle'
g = rd(grad)
g = one(
    g,
    "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1k-redtrace1a-edge0a-nativeout1a-diag1c-saf1'",
    "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1l-cc1off1a-edge0a-nativeout1a-diag1c-saf1'",
    'version')
wr(grad, g)

renderer = 'app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'
r = rd(renderer)

r = one(r,
        '            d.put("renderLook", "RENDER1K_REDTRACE1A_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A");\n',
        '''            d.put("renderLook", "RENDER1L_CC1OFF1A_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A");\n            d.put("cc1Experiment", "CC1OFF1A_PHOTOGRAPHIC_OUTPUT_BYPASS");\n            d.put("cc1AppliedToPhotographicPixels", false);\n            d.put("cc1MatrixRetainedUnusedForPhotographicOutput", true);\n            d.put("cc1CounterfactualRedTraceRetained", true);\n            d.put("cc1OffOnlyPhotographicVariable", true);\n            d.put("cc1BypassInput", "post_Yc_exact_inverse_working_RGB");\n            d.put("cc1BypassOutput", "post_Yc_working_RGB_direct_linear8");\n            d.put("preSrgbStatisticsRole", "counterfactual_CC1_control_not_photographic_output");\n''',
        'render-identity')

r = one(r,
        '        d.put("cc1Placement", "post_MEDIUM_DG_before_direct_8bit_output");\n',
        '        d.put("cc1Placement", "CC1OFF1A_bypassed_post_Yc_before_direct_8bit_output");\n',
        'cc1-placement')

r = one(r,
        '            d.put("outputTransferExperiment", "NATIVEOUT1A_DIRECT_POST_CC1_LINEAR8");\n',
        '            d.put("outputTransferExperiment", "NATIVEOUT1A_DIRECT_POST_YC_WORKING_LINEAR8_CC1OFF1A");\n',
        'output-experiment')
r = one(r,
        '            d.put("outputTransferPlacement", "native_post_CC1_direct_8bit_before_JPEG");\n',
        '            d.put("outputTransferPlacement", "native_post_Yc_working_CC1_bypassed_direct_8bit_before_JPEG");\n',
        'output-placement')
r = one(r,
        '            d.put("netOutputTransfer", "post_CC1_linear_direct_8bit");\n',
        '            d.put("netOutputTransfer", "post_Yc_working_linear_direct_8bit_CC1_bypassed");\n',
        'net-output-transfer')
r = one(r,
        '            d.put("nativePixelOutputQuantizer", "linear8_post_CC1");\n',
        '            d.put("nativePixelOutputQuantizer", "linear8_post_Yc_working_CC1_bypassed");\n',
        'quantizer-metadata')
wr(renderer, r)

cpp = 'app/src/main/cpp/m10rRender.cpp'
c = rd(cpp)

old_cc1 = '''            const double outR = outMat[0]*nr + outMat[1]*ng + outMat[2]*nb;\n            const double outG = outMat[3]*nr + outMat[4]*ng + outMat[5]*nb;\n            const double outB = outMat[6]*nr + outMat[7]*ng + outMat[8]*nb;\n'''
new_cc1 = '''            // CC1OFF1A positive control: bypass DEFAULT_SRGB_CC1 only for\n            // photographic publication.  outMat stays loaded for reproducible\n            // provenance/control work; no other pixel arithmetic is changed.\n            const double outR = nr;\n            const double outG = ng;\n            const double outB = nb;\n'''
c = one(c, old_cc1, new_cc1, 'native-cc1-output-bypass')
wr(cpp, c)

# Hard isolation checks.
G = rd(grad)
R = rd(renderer)
C = rd(cpp)

if "render1l-cc1off1a-edge0a-nativeout1a-diag1c-saf1'" not in G:
    raise SystemExit('RENDER1L CC1OFF1A build identity missing')

for needle in [
    'RENDER1L_CC1OFF1A_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A',
    'CC1OFF1A_PHOTOGRAPHIC_OUTPUT_BYPASS',
    'cc1AppliedToPhotographicPixels", false',
    'cc1MatrixRetainedUnusedForPhotographicOutput", true',
    'cc1CounterfactualRedTraceRetained", true',
    'cc1OffOnlyPhotographicVariable", true',
    'post_Yc_exact_inverse_working_RGB',
    'counterfactual_CC1_control_not_photographic_output',
    'CC1OFF1A_bypassed_post_Yc_before_direct_8bit_output',
    'NATIVEOUT1A_DIRECT_POST_YC_WORKING_LINEAR8_CC1OFF1A',
    'native_post_Yc_working_CC1_bypassed_direct_8bit_before_JPEG',
    'post_Yc_working_linear_direct_8bit_CC1_bypassed',
    'linear8_post_Yc_working_CC1_bypassed',
    'redTracePhotographicPixelsChanged", false',
    'REDTRACE1A_YC_INVERSE_VS_CC1_EXCURSION',
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
        raise SystemExit('RENDER1L CC1OFF1A renderer invariant missing: ' + needle)

for needle in [
    'const double outR = nr;',
    'const double outG = ng;',
    'const double outB = nb;',
    'linear8(outR)', 'linear8(outG)', 'linear8(outB)',
    'jdouble src[9], workingMat[9], outMat[9];',
    'env->GetDoubleArrayRegion(joutMat, 0, 9, outMat);',
    'const double mappedCb = cb * yRatio;',
    'const double mappedCr = cr * yRatio;'
]:
    if needle not in C:
        raise SystemExit('RENDER1L CC1OFF1A native invariant missing: ' + needle)

for needle in [
    'const double outR = outMat[0]*nr + outMat[1]*ng + outMat[2]*nb;',
    'const double outG = outMat[3]*nr + outMat[4]*ng + outMat[5]*nb;',
    'const double outB = outMat[6]*nr + outMat[7]*ng + outMat[8]*nb;'
]:
    if needle in C:
        raise SystemExit('RENDER1L CC1OFF1A live native CC1 multiplication remains: ' + needle)

# Java sampled REDTRACE intentionally retains the matrix multiplication as a
# counterfactual control.  It must remain diagnostic-only and must not feed JNI
# pixel output.
for needle in [
    'double outR = workingToSrgb[0]*nr + workingToSrgb[1]*ng + workingToSrgb[2]*nb;',
    'double outG = workingToSrgb[3]*nr + workingToSrgb[4]*ng + workingToSrgb[5]*nb;',
    'double outB = workingToSrgb[6]*nr + workingToSrgb[7]*ng + workingToSrgb[8]*nb;'
]:
    if needle not in R:
        raise SystemExit('RENDER1L CC1OFF1A counterfactual CC1 diagnostic missing: ' + needle)

if 'nativeInverseSrgbTransfer(bitmap)' in R or 'nativeEdgePass(bitmap, edgeIso)' in R:
    raise SystemExit('RENDER1L CC1OFF1A unexpectedly re-enabled transfer/edge pass')

print('M10-R RENDER1L CC1OFF1A applied')
print(' - photographic output bypasses CC1 only: post-Yc working RGB -> linear8')
print(' - CC1 matrix retained; sampled REDTRACE keeps counterfactual CC1 diagnostics')
print(' - NATIVEOUT1A and EDGE0A remain active')
print(' - WB/CA9, matrices, WORKING1A, MEDIUM/DG, Yc, exposure, JPEG, single RAW and HDR-off frozen')
print(' - diagnostic positive control only; final M10-R architecture is NOT claimed')
