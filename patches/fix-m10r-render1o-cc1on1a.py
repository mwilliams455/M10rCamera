#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix-m10r-render1o-cc1on1a.py <PhotonCamera-root>')
root = Path(sys.argv[1]).resolve()
if not (root / 'app').is_dir():
    raise SystemExit('RENDER1O CC1ON1A: not a PhotonCamera root')

def rd(rel):
    p = root / rel
    if not p.exists():
        raise SystemExit('RENDER1O CC1ON1A missing: ' + rel)
    return p.read_text()

def wr(rel, text):
    (root / rel).write_text(text)

def one(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit('RENDER1O CC1ON1A anchor %s count=%d' % (label, n))
    return text.replace(old, new, 1)

# RENDER1O is a photographic convergence experiment on top of validated
# RENDER1N YBLEND1A. It changes ONE live photographic variable: restore the
# already-recovered DEFAULT_SRGB_CC1 matrix after the exact Yc inverse.
#
# Frozen: source calibration, WB/CA9, WORKING1A, YC2A, MEDIUM/DG,
# YBLEND1A, NATIVEOUT1A, EDGE0A, single RAW, HDR-off and JPEG quality.
# This does NOT claim YBLEND1A is the final firmware formula.

grad = 'app/build.gradle'
g = rd(grad)
g = one(
    g,
    "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1n-yblend1a-redtrace1b-cc1off1a-edge0a-nativeout1a-diag1c-saf1'",
    "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1o-cc1on1a-yblend1a-redtrace1b-edge0a-nativeout1a-diag1c-saf1'",
    'version')
wr(grad, g)

renderer = 'app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'
r = rd(renderer)

r = one(
    r,
    '            d.put("renderLook", "RENDER1N_YBLEND1A_REDTRACE1B_CC1OFF1A_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A");\n',
    '''            d.put("renderLook", "RENDER1O_CC1ON1A_YBLEND1A_REDTRACE1B_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A");
            d.put("photographicConvergenceExperiment", "CC1ON1A_RESTORE_AFTER_VALIDATED_YBLEND1A");
            d.put("cc1RestoreOnlyPhotographicVariable", true);
''',
    'render-identity')

r = one(r,
    '            d.put("cc1Experiment", "CC1OFF1A_PHOTOGRAPHIC_OUTPUT_BYPASS");\n',
    '            d.put("cc1Experiment", "CC1ON1A_PHOTOGRAPHIC_OUTPUT_RESTORE");\n',
    'cc1-experiment')
r = one(r,
    '            d.put("cc1AppliedToPhotographicPixels", false);\n',
    '            d.put("cc1AppliedToPhotographicPixels", true);\n',
    'cc1-applied')
r = one(r,
    '            d.put("cc1MatrixRetainedUnusedForPhotographicOutput", true);\n',
    '            d.put("cc1MatrixRetainedUnusedForPhotographicOutput", false);\n',
    'cc1-matrix-used')
r = one(r,
    '            d.put("cc1CounterfactualRedTraceRetained", true);\n',
    '            d.put("cc1RedTraceMatchesPhotographicOutput", true);\n',
    'cc1-redtrace-role')
r = one(r,
    '            d.put("cc1OffOnlyPhotographicVariable", true);\n',
    '            d.put("cc1On1ARestoresFinalColourOnly", true);\n',
    'cc1-only-variable')
r = one(r,
    '            d.put("cc1BypassInput", "post_Yc_exact_inverse_working_RGB");\n',
    '            d.put("cc1Input", "post_Yc_exact_inverse_working_RGB");\n',
    'cc1-input')
r = one(r,
    '            d.put("cc1BypassOutput", "post_Yc_working_RGB_direct_linear8");\n',
    '            d.put("cc1Output", "post_CC1_output_RGB_direct_linear8");\n',
    'cc1-output')
r = one(r,
    '            d.put("preSrgbStatisticsRole", "counterfactual_CC1_control_not_photographic_output");\n',
    '            d.put("preSrgbStatisticsRole", "actual_post_CC1_photographic_output");\n',
    'cc1-stats-role')

r = one(r,
    '        d.put("cc1Placement", "CC1OFF1A_bypassed_post_Yc_before_direct_8bit_output");\n',
    '        d.put("cc1Placement", "post_MEDIUM_DG_after_Yc_exact_inverse_before_direct_8bit_output");\n',
    'cc1-placement')
r = one(r,
    '            d.put("outputTransferExperiment", "NATIVEOUT1A_DIRECT_POST_YC_WORKING_LINEAR8_CC1OFF1A");\n',
    '            d.put("outputTransferExperiment", "NATIVEOUT1A_DIRECT_POST_CC1_LINEAR8");\n',
    'output-experiment')
r = one(r,
    '            d.put("outputTransferPlacement", "native_post_Yc_working_CC1_bypassed_direct_8bit_before_JPEG");\n',
    '            d.put("outputTransferPlacement", "native_post_CC1_direct_8bit_before_JPEG");\n',
    'output-placement')
r = one(r,
    '            d.put("netOutputTransfer", "post_Yc_working_linear_direct_8bit_CC1_bypassed");\n',
    '            d.put("netOutputTransfer", "post_CC1_linear_direct_8bit");\n',
    'net-output-transfer')
r = one(r,
    '            d.put("nativePixelOutputQuantizer", "linear8_post_Yc_working_CC1_bypassed");\n',
    '            d.put("nativePixelOutputQuantizer", "linear8_post_CC1");\n',
    'quantizer-metadata')
wr(renderer, r)

cpp = 'app/src/main/cpp/m10rRender.cpp'
c = rd(cpp)
old_cc1 = '''            const double outR = nr;
            const double outG = ng;
            const double outB = nb;
'''
new_cc1 = '''            // RENDER1O CC1ON1A: restore the already recovered output colour
            // transform after YBLEND1A + exact Yc inverse. No tone/chroma
            // arithmetic changes here; NATIVEOUT1A still quantizes directly.
            const double outR = outMat[0]*nr + outMat[1]*ng + outMat[2]*nb;
            const double outG = outMat[3]*nr + outMat[4]*ng + outMat[5]*nb;
            const double outB = outMat[6]*nr + outMat[7]*ng + outMat[8]*nb;
'''
c = one(c, old_cc1, new_cc1, 'native-cc1-restore')
wr(cpp, c)

G = rd(grad)
R = rd(renderer)
C = rd(cpp)

if "render1o-cc1on1a-yblend1a-redtrace1b-edge0a-nativeout1a-diag1c-saf1'" not in G:
    raise SystemExit('RENDER1O CC1ON1A build identity missing')

for needle in [
    'RENDER1O_CC1ON1A_YBLEND1A_REDTRACE1B_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A',
    'CC1ON1A_RESTORE_AFTER_VALIDATED_YBLEND1A',
    'cc1AppliedToPhotographicPixels", true',
    'cc1MatrixRetainedUnusedForPhotographicOutput", false',
    'cc1RedTraceMatchesPhotographicOutput", true',
    'cc1RestoreOnlyPhotographicVariable", true',
    'cc1On1ARestoresFinalColourOnly", true',
    'actual_post_CC1_photographic_output',
    'post_MEDIUM_DG_after_Yc_exact_inverse_before_direct_8bit_output',
    'NATIVEOUT1A_DIRECT_POST_CC1_LINEAR8',
    'native_post_CC1_direct_8bit_before_JPEG',
    'post_CC1_linear_direct_8bit',
    'linear8_post_CC1',
    'chromaReconstructionExperiment", "YBLEND1A"',
    'yBlend1ALumaArithmeticChanged", false',
    'yBlend1AMediumDgChanged", false',
    'yBlend1AFirmwareClaim", false',
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
        raise SystemExit('RENDER1O CC1ON1A renderer invariant missing: ' + needle)

for needle in [
    'const double mappedY = dy / static_cast<double>(DG_OUT_MAX);',
    'const double yRatio = y > 1.0e-12 ? mappedY / y : 0.0;',
    'const double yBlendChromaScale = y > 1.0e-12 ? 0.5 * (1.0 + yRatio) : 0.0;',
    'const double mappedCb = cb * yBlendChromaScale;',
    'const double mappedCr = cr * yBlendChromaScale;',
    'const double nr = 1.000000000000*mappedY - 0.001043337611*mappedCb + 1.401991725445*mappedCr;',
    'const double ng = 1.000000000000*mappedY - 0.345114690199*mappedCb - 0.714098755336*mappedCr;',
    'const double nb = 1.000000000000*mappedY + 1.770975790582*mappedCb - 0.000124867533*mappedCr;',
    'const double outR = outMat[0]*nr + outMat[1]*ng + outMat[2]*nb;',
    'const double outG = outMat[3]*nr + outMat[4]*ng + outMat[5]*nb;',
    'const double outB = outMat[6]*nr + outMat[7]*ng + outMat[8]*nb;',
    'linear8(outR)', 'linear8(outG)', 'linear8(outB)'
]:
    if needle not in C:
        raise SystemExit('RENDER1O CC1ON1A native invariant missing: ' + needle)

for forbidden in [
    'const double outR = nr;',
    'const double outG = ng;',
    'const double outB = nb;',
    'const double mappedCb = cb * yRatio;',
    'const double mappedCr = cr * yRatio;'
]:
    if forbidden in C:
        raise SystemExit('RENDER1O CC1ON1A forbidden old live path remains: ' + forbidden)

if 'nativeInverseSrgbTransfer(bitmap)' in R or 'nativeEdgePass(bitmap, edgeIso)' in R:
    raise SystemExit('RENDER1O CC1ON1A unexpectedly changed transfer/edge isolation')

print('M10-R RENDER1O CC1ON1A applied')
print(' - validated RENDER1N YBLEND1A luma/chroma path remains frozen')
print(' - DEFAULT_SRGB_CC1 restored after exact Yc inverse')
print(' - direct NATIVEOUT1A linear8 remains; no textbook sRGB OETF')
print(' - REDTRACE now describes actual CC1 photographic output')
print(' - EDGE0A, WB/CA9, WORKING1A, MEDIUM/DG, exposure, JPEG, single RAW and HDR-off frozen')
print(' - photographic convergence candidate; YBLEND1A is still not claimed as final firmware semantics')
