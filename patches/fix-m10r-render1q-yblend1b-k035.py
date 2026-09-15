#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix-m10r-render1q-yblend1b-k035.py <PhotonCamera-root>')
root = Path(sys.argv[1]).resolve()
if not (root / 'app').is_dir():
    raise SystemExit('RENDER1Q YBLEND1B K035: not a PhotonCamera root')

def rd(rel):
    p = root / rel
    if not p.exists():
        raise SystemExit('RENDER1Q YBLEND1B K035 missing: ' + rel)
    return p.read_text()

def wr(rel, text):
    (root / rel).write_text(text)

def one(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit('RENDER1Q YBLEND1B K035 anchor %s count=%d' % (label, n))
    return text.replace(old, new, 1)

# Controlled one-variable photographic probe on top of frozen RENDER1P.
#
# RENDER1P validated the corrected factory sRGB CC1 mapping. This probe leaves
# that mapping and every other photographic stage frozen, and changes ONLY the
# Yc chroma carrier interpolation coefficient:
#
#   r       = mappedY / inputY
#   scale_k = 1 + k * (r - 1)
#
# RENDER1P / YBLEND1A used k=0.50.
# RENDER1Q / YBLEND1B_K035 uses k=0.35.
#
# This is a falsification experiment, NOT a claim that Leica firmware uses
# k=0.35 or even a constant-k model.

grad = 'app/build.gradle'
g = rd(grad)
g = one(
    g,
    "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1p-cc1map1a-yblend1a-redtrace1b-edge0a-nativeout1a-diag1c-saf1'",
    "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1q-cc1map1a-yblend1b-k035-redtrace1b-edge0a-nativeout1a-diag1c-saf1'",
    'version')
wr(grad, g)

renderer = 'app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'
r = rd(renderer)

r = one(
    r,
    '            d.put("renderLook", "RENDER1P_CC1MAP1A_YBLEND1A_REDTRACE1B_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A");\n',
    '''            d.put("renderLook", "RENDER1Q_CC1MAP1A_YBLEND1B_K035_REDTRACE1B_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A");
            d.put("yBlend1BProbeK", 0.35);
            d.put("yBlend1BOnlyPhotographicVariable", true);
''',
    'render-identity')

r = one(
    r,
    '            d.put("photographicConvergenceExperiment", "CC1MAP1A_EXACT_FACTORY_SRGB_ROW");\n',
    '            d.put("photographicConvergenceExperiment", "YBLEND1B_K035_CONTROLLED_PROBE_AFTER_CC1MAP1A");\n',
    'experiment')

old_meta = '''            d.put("chromaReconstructionExperiment", "YBLEND1A");
            d.put("yBlend1AExperimentalApplied", true);
            d.put("yBlend1AFirmwareClaim", false);
            d.put("yBlend1AInputY", "pre_MEDIUM_DG_Yc_Y");
            d.put("yBlend1AMappedY", "unchanged_dy_over_DG_OUT_MAX");
            d.put("yBlend1AOldChromaScale", "mappedY_over_inputY");
            d.put("yBlend1ANewChromaScale", "0.5_times_(1_plus_mappedY_over_inputY)");
            d.put("yBlend1AChromaCarrierY", "0.5_times_(inputY_plus_mappedY)");
            d.put("yBlend1ALumaArithmeticChanged", false);
            d.put("yBlend1AMediumDgChanged", false);
'''
new_meta = '''            d.put("chromaReconstructionExperiment", "YBLEND1B_K035");
            d.put("yBlend1BExperimentalApplied", true);
            d.put("yBlend1BFirmwareClaim", false);
            d.put("yBlend1BK", 0.35);
            d.put("yBlend1BInputY", "pre_MEDIUM_DG_Yc_Y");
            d.put("yBlend1BMappedY", "unchanged_dy_over_DG_OUT_MAX");
            d.put("yBlend1BPreviousScale", "YBLEND1A_k0p50");
            d.put("yBlend1BNewChromaScale", "1_plus_0.35_times_(mappedY_over_inputY_minus_1)");
            d.put("yBlend1BLumaArithmeticChanged", false);
            d.put("yBlend1BMediumDgChanged", false);
'''
r = one(r, old_meta, new_meta, 'experiment-metadata')

r = one(
    r,
    'd.put("nonlinearApplicationMode", "M10R_Yc_Convert_map_Y_YBLEND1A_midpoint_chroma_exact_inverse");',
    'd.put("nonlinearApplicationMode", "M10R_Yc_Convert_map_Y_YBLEND1B_k035_chroma_exact_inverse");',
    'application-mode')
r = one(
    r,
    'd.put("b2yChromaPolicy", "YBLEND1A_midpoint_between_absolute_and_relative_chroma_then_exact_matrix_inverse");',
    'd.put("b2yChromaPolicy", "YBLEND1B_k035_between_absolute_and_relative_chroma_then_exact_matrix_inverse");',
    'chroma-policy')
r = one(
    r,
    'd.put("lumaGainStatisticSemantic", "mappedY_over_inputY_retained_as_diagnostic_old_scale;_YBLEND1A_applies_halfway_scale_to_chroma_only");',
    'd.put("lumaGainStatisticSemantic", "mappedY_over_inputY_retained_as_diagnostic_full_relative_scale;_YBLEND1B_applies_k0p35_excess_gain_to_chroma_only");',
    'gain-semantic')

old_java = '                    double yBlendChromaScale = (ycY > 1.0e-12) ? (0.5 * (1.0 + yRatio)) : 0.0;\n'
new_java = '''                    // RENDER1Q YBLEND1B_K035: preserve the same mappedY and
                    // zero-Y guard, but inherit only 35% of tone gain above unity.
                    double yBlendChromaScale = (ycY > 1.0e-12) ? (1.0 + 0.35 * (yRatio - 1.0)) : 0.0;
'''
r = one(r, old_java, new_java, 'java-chroma-scale')

r = one(
    r,
    '            yBlend1A.put("appliedChromaScaleFormula", "0.5_times_(1_plus_mappedY_over_inputY)");\n',
    '            yBlend1A.put("appliedChromaScaleFormula", "1_plus_0.35_times_(mappedY_over_inputY_minus_1)");\n            yBlend1A.put("probeK", 0.35);\n',
    'diagnostic-formula')
r = one(
    r,
    '                        ybj.put("meanYBlend1AAppliedChromaScale", ybs[3] / yn);\n',
    '                        ybj.put("meanYBlend1BAppliedChromaScale", ybs[3] / yn);\n',
    'diagnostic-field')
r = one(
    r,
    '            d.put("yBlend1A", yBlend1A);\n',
    '            d.put("yBlend1B", yBlend1A);\n',
    'diagnostic-object-key')

wr(renderer, r)

cpp = 'app/src/main/cpp/m10rRender.cpp'
c = rd(cpp)
old_cpp = '            const double yBlendChromaScale = y > 1.0e-12 ? 0.5 * (1.0 + yRatio) : 0.0;\n'
new_cpp = '''            // RENDER1Q YBLEND1B_K035 controlled probe. mappedY, Yc inverse,
            // CC1MAP1A and direct output are frozen; only chroma gain changes.
            const double yBlendChromaScale = y > 1.0e-12 ? 1.0 + 0.35 * (yRatio - 1.0) : 0.0;
'''
c = one(c, old_cpp, new_cpp, 'native-chroma-scale')
wr(cpp, c)

G = rd(grad)
R = rd(renderer)
C = rd(cpp)

if "render1q-cc1map1a-yblend1b-k035-redtrace1b-edge0a-nativeout1a-diag1c-saf1'" not in G:
    raise SystemExit('RENDER1Q build identity missing')

for needle in [
    'RENDER1Q_CC1MAP1A_YBLEND1B_K035_REDTRACE1B_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A',
    'YBLEND1B_K035_CONTROLLED_PROBE_AFTER_CC1MAP1A',
    'chromaReconstructionExperiment", "YBLEND1B_K035',
    'yBlend1BFirmwareClaim", false',
    'yBlend1BK", 0.35',
    'yBlend1BLumaArithmeticChanged", false',
    'yBlend1BMediumDgChanged", false',
    'cc1MappingFix", "CC1MAP1A"',
    'cc1FactoryStillColorSpace", "sRGB"',
    'cc1Ca9ModeIndex", 0',
    'cc1Semantic", "ProPhoto_RGB_to_sRGB"',
    'cc1AppliedToPhotographicPixels", true',
    'actual_post_CC1_photographic_output',
    'textbookSrgbOetfApplied", false',
    'transfer1aInverseExecuted", false',
    'edgePassEnabled", false',
    'edgeCallExecuted", false',
    'workingBasisPlacementFix", "WORKING1A"',
    'yc2aMatrixCorrectionApplied", true',
    'hdrEnabled", false',
    'sourceFrameCount", 1'
]:
    if needle not in R:
        raise SystemExit('RENDER1Q renderer invariant missing: ' + needle)

for needle in [
    'const double mappedY = dy / static_cast<double>(DG_OUT_MAX);',
    'const double yRatio = y > 1.0e-12 ? mappedY / y : 0.0;',
    'const double yBlendChromaScale = y > 1.0e-12 ? 1.0 + 0.35 * (yRatio - 1.0) : 0.0;',
    'const double mappedCb = cb * yBlendChromaScale;',
    'const double mappedCr = cr * yBlendChromaScale;',
    'const double outR = outMat[0]*nr + outMat[1]*ng + outMat[2]*nb;',
    'const double outG = outMat[3]*nr + outMat[4]*ng + outMat[5]*nb;',
    'const double outB = outMat[6]*nr + outMat[7]*ng + outMat[8]*nb;',
    'linear8(outR)', 'linear8(outG)', 'linear8(outB)'
]:
    if needle not in C:
        raise SystemExit('RENDER1Q native invariant missing: ' + needle)

for forbidden in [
    'const double yBlendChromaScale = y > 1.0e-12 ? 0.5 * (1.0 + yRatio) : 0.0;',
    'const double mappedCb = cb * yRatio;',
    'const double mappedCr = cr * yRatio;'
]:
    if forbidden in C:
        raise SystemExit('RENDER1Q forbidden old live path remains: ' + forbidden)

for needle in [
    '2.0341, -0.7273, -0.3067',
    '-0.2288,  1.2317, -0.0029',
    '-0.0086, -0.1533,  1.1619'
]:
    if needle not in R:
        raise SystemExit('RENDER1Q CC1MAP1A matrix invariant missing: ' + needle)

if '1.3895, -0.1693, -0.2202' in R:
    raise SystemExit('RENDER1Q old mode-1/Adobe CC1 unexpectedly present')
if 'nativeInverseSrgbTransfer(bitmap)' in R or 'nativeEdgePass(bitmap, edgeIso)' in R:
    raise SystemExit('RENDER1Q unexpectedly changed transfer/edge isolation')

print('M10-R RENDER1Q YBLEND1B K035 applied')
print(' - only live photographic change vs RENDER1P: chroma excess-gain inheritance k 0.50 -> 0.35')
print(' - mappedY / MEDIUM / DG unchanged')
print(' - CC1MAP1A exact factory sRGB row frozen')
print(' - NATIVEOUT1A direct linear8, EDGE0A, WB/CA9, exposure, JPEG, single RAW and HDR-off frozen')
print(' - controlled falsification probe only; no firmware formula claim')
