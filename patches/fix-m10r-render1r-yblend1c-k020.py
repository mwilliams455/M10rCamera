#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix-m10r-render1r-yblend1c-k020.py <PhotonCamera-root>')
root = Path(sys.argv[1]).resolve()
if not (root / 'app').is_dir():
    raise SystemExit('RENDER1R YBLEND1C K020: not a PhotonCamera root')

def rd(rel):
    p = root / rel
    if not p.exists():
        raise SystemExit('RENDER1R YBLEND1C K020 missing: ' + rel)
    return p.read_text()

def wr(rel, text):
    (root / rel).write_text(text)

def one(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit('RENDER1R YBLEND1C K020 anchor %s count=%d' % (label, n))
    return text.replace(old, new, 1)

# Controlled follow-up on device-validated RENDER1Q.
# Only live photographic variable: k=0.35 -> k=0.20 in
#   scale = 1 + k * (mappedY/inputY - 1)
# All luma/tone, matrices, output, edge, exposure and capture policy stay frozen.
# This remains a falsification probe, not a Leica firmware-formula claim.
#
# Diagnostic metadata is also corrected to reflect that CC1 is live in the
# photographic path since RENDER1O/RENDER1P; those bookkeeping edits do not
# affect pixels.

grad = 'app/build.gradle'
g = rd(grad)
g = one(
    g,
    "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1q-cc1map1a-yblend1b-k035-redtrace1b-edge0a-nativeout1a-diag1c-saf1'",
    "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1r-cc1map1a-yblend1c-k020-redtrace1b-edge0a-nativeout1a-diag1c-saf1'",
    'version')
wr(grad, g)

renderer = 'app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'
r = rd(renderer)

r = one(
    r,
    '            d.put("renderLook", "RENDER1Q_CC1MAP1A_YBLEND1B_K035_REDTRACE1B_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A");\n            d.put("yBlend1BProbeK", 0.35);\n            d.put("yBlend1BOnlyPhotographicVariable", true);\n',
    '            d.put("renderLook", "RENDER1R_CC1MAP1A_YBLEND1C_K020_REDTRACE1B_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A");\n            d.put("yBlend1CProbeK", 0.20);\n            d.put("yBlend1COnlyPhotographicVariable", true);\n',
    'render-identity')
r = one(
    r,
    '            d.put("photographicConvergenceExperiment", "YBLEND1B_K035_CONTROLLED_PROBE_AFTER_CC1MAP1A");\n',
    '            d.put("photographicConvergenceExperiment", "YBLEND1C_K020_CONTROLLED_PROBE_AFTER_CC1MAP1A");\n',
    'experiment')

r = one(r, '            d.put("chromaReconstructionExperiment", "YBLEND1B_K035");\n',
           '            d.put("chromaReconstructionExperiment", "YBLEND1C_K020");\n', 'chroma-experiment')
r = one(r, '            d.put("yBlend1BExperimentalApplied", true);\n',
           '            d.put("yBlend1CExperimentalApplied", true);\n', 'experimental')
r = one(r, '            d.put("yBlend1BFirmwareClaim", false);\n',
           '            d.put("yBlend1CFirmwareClaim", false);\n', 'firmware-claim')
r = one(r, '            d.put("yBlend1BK", 0.35);\n',
           '            d.put("yBlend1CK", 0.20);\n', 'k-meta')
r = one(r, '            d.put("yBlend1BInputY", "pre_MEDIUM_DG_Yc_Y");\n',
           '            d.put("yBlend1CInputY", "pre_MEDIUM_DG_Yc_Y");\n', 'input-y-meta')
r = one(r, '            d.put("yBlend1BMappedY", "unchanged_dy_over_DG_OUT_MAX");\n',
           '            d.put("yBlend1CMappedY", "unchanged_dy_over_DG_OUT_MAX");\n', 'mapped-y-meta')
r = one(r, '            d.put("yBlend1BPreviousScale", "YBLEND1A_k0p50");\n',
           '            d.put("yBlend1CPreviousScale", "YBLEND1B_k0p35");\n', 'previous-scale-meta')
r = one(r, '            d.put("yBlend1BNewChromaScale", "1_plus_0.35_times_(mappedY_over_inputY_minus_1)");\n',
           '            d.put("yBlend1CNewChromaScale", "1_plus_0.20_times_(mappedY_over_inputY_minus_1)");\n', 'new-scale-meta')
r = one(r, '            d.put("yBlend1BLumaArithmeticChanged", false);\n',
           '            d.put("yBlend1CLumaArithmeticChanged", false);\n', 'luma-meta')
r = one(r, '            d.put("yBlend1BMediumDgChanged", false);\n',
           '            d.put("yBlend1CMediumDgChanged", false);\n', 'medium-dg-meta')

r = one(r,
    'd.put("nonlinearApplicationMode", "M10R_Yc_Convert_map_Y_YBLEND1B_k035_chroma_exact_inverse");',
    'd.put("nonlinearApplicationMode", "M10R_Yc_Convert_map_Y_YBLEND1C_k020_chroma_exact_inverse");',
    'application-mode')
r = one(r,
    'd.put("b2yChromaPolicy", "YBLEND1B_k035_between_absolute_and_relative_chroma_then_exact_matrix_inverse");',
    'd.put("b2yChromaPolicy", "YBLEND1C_k020_between_absolute_and_relative_chroma_then_exact_matrix_inverse");',
    'chroma-policy')
r = one(r,
    'd.put("lumaGainStatisticSemantic", "mappedY_over_inputY_retained_as_diagnostic_full_relative_scale;_YBLEND1B_applies_k0p35_excess_gain_to_chroma_only");',
    'd.put("lumaGainStatisticSemantic", "mappedY_over_inputY_retained_as_diagnostic_full_relative_scale;_YBLEND1C_applies_k0p20_excess_gain_to_chroma_only");',
    'gain-semantic')

r = one(r,
    '                    // RENDER1Q YBLEND1B_K035: preserve the same mappedY and\n                    // zero-Y guard, but inherit only 35% of tone gain above unity.\n                    double yBlendChromaScale = (ycY > 1.0e-12) ? (1.0 + 0.35 * (yRatio - 1.0)) : 0.0;\n',
    '                    // RENDER1R YBLEND1C_K020: preserve the same mappedY and\n                    // zero-Y guard, but inherit only 20% of tone gain above unity.\n                    double yBlendChromaScale = (ycY > 1.0e-12) ? (1.0 + 0.20 * (yRatio - 1.0)) : 0.0;\n',
    'java-chroma-scale')
r = one(r,
    '            yBlend1A.put("appliedChromaScaleFormula", "1_plus_0.35_times_(mappedY_over_inputY_minus_1)");\n            yBlend1A.put("probeK", 0.35);\n',
    '            yBlend1A.put("appliedChromaScaleFormula", "1_plus_0.20_times_(mappedY_over_inputY_minus_1)");\n            yBlend1A.put("probeK", 0.20);\n',
    'diagnostic-formula')
r = one(r, '                        ybj.put("meanYBlend1BAppliedChromaScale", ybs[3] / yn);\n',
           '                        ybj.put("meanYBlend1CAppliedChromaScale", ybs[3] / yn);\n', 'diagnostic-field')
r = one(r, '            d.put("yBlend1B", yBlend1A);\n',
           '            d.put("yBlend1C", yBlend1A);\n', 'diagnostic-object-key')

# Correct stale REDTRACE1B bookkeeping from its original CC1OFF diagnostic era.
r = one(r,
    '            redTrace1B.put("photographicOutputStillCc1Bypassed", true);\n            redTrace1B.put("counterfactualCc1StillEvaluated", true);\n',
    '            redTrace1B.put("photographicOutputStillCc1Bypassed", false);\n            redTrace1B.put("counterfactualCc1StillEvaluated", false);\n            redTrace1B.put("postCc1StatisticsMatchPhotographicCc1", true);\n',
    'redtrace1b-live-cc1-meta')

# Correct stale REDTRACE1A matrix/equation labels. The sampled arithmetic has
# followed workingToSrgb since CC1MAP1A; only these strings were stale.
r = one(r,
    '            redTrace.put("cc1Matrix", "1.3895,-0.1693,-0.2202;-0.2288,1.2317,-0.0029;-0.0176,-0.0963,1.1139");\n            redTrace.put("cc1RedEquation", "outR=1.3895*postYcR-0.1693*postYcG-0.2202*postYcB");\n',
    '            redTrace.put("cc1Matrix", "2.0341,-0.7273,-0.3067;-0.2288,1.2317,-0.0029;-0.0086,-0.1533,1.1619");\n            redTrace.put("cc1RedEquation", "outR=2.0341*postYcR-0.7273*postYcG-0.3067*postYcB");\n',
    'redtrace1a-cc1-labels')
wr(renderer, r)

cpp = 'app/src/main/cpp/m10rRender.cpp'
c = rd(cpp)
c = one(c,
    '            // RENDER1Q YBLEND1B_K035 controlled probe. mappedY, Yc inverse,\n            // CC1MAP1A and direct output are frozen; only chroma gain changes.\n            const double yBlendChromaScale = y > 1.0e-12 ? 1.0 + 0.35 * (yRatio - 1.0) : 0.0;\n',
    '            // RENDER1R YBLEND1C_K020 controlled probe. mappedY, Yc inverse,\n            // CC1MAP1A and direct output are frozen; only chroma gain changes.\n            const double yBlendChromaScale = y > 1.0e-12 ? 1.0 + 0.20 * (yRatio - 1.0) : 0.0;\n',
    'native-chroma-scale')
wr(cpp, c)

G = rd(grad)
R = rd(renderer)
C = rd(cpp)

if "render1r-cc1map1a-yblend1c-k020-redtrace1b-edge0a-nativeout1a-diag1c-saf1'" not in G:
    raise SystemExit('RENDER1R build identity missing')
for needle in [
    'RENDER1R_CC1MAP1A_YBLEND1C_K020_REDTRACE1B_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A',
    'YBLEND1C_K020_CONTROLLED_PROBE_AFTER_CC1MAP1A',
    'chromaReconstructionExperiment", "YBLEND1C_K020',
    'yBlend1CFirmwareClaim", false',
    'yBlend1CK", 0.20',
    'yBlend1CLumaArithmeticChanged", false',
    'yBlend1CMediumDgChanged", false',
    'cc1MappingFix", "CC1MAP1A"',
    'cc1Ca9ModeIndex", 0',
    'cc1Semantic", "ProPhoto_RGB_to_sRGB"',
    'cc1AppliedToPhotographicPixels", true',
    'postCc1StatisticsMatchPhotographicCc1", true',
    'photographicOutputStillCc1Bypassed", false',
    'counterfactualCc1StillEvaluated", false',
    'cc1Matrix", "2.0341,-0.7273,-0.3067',
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
        raise SystemExit('RENDER1R renderer invariant missing: ' + needle)

for needle in [
    'const double mappedY = dy / static_cast<double>(DG_OUT_MAX);',
    'const double yRatio = y > 1.0e-12 ? mappedY / y : 0.0;',
    'const double yBlendChromaScale = y > 1.0e-12 ? 1.0 + 0.20 * (yRatio - 1.0) : 0.0;',
    'const double mappedCb = cb * yBlendChromaScale;',
    'const double mappedCr = cr * yBlendChromaScale;',
    'const double outR = outMat[0]*nr + outMat[1]*ng + outMat[2]*nb;',
    'const double outG = outMat[3]*nr + outMat[4]*ng + outMat[5]*nb;',
    'const double outB = outMat[6]*nr + outMat[7]*ng + outMat[8]*nb;',
    'linear8(outR)', 'linear8(outG)', 'linear8(outB)'
]:
    if needle not in C:
        raise SystemExit('RENDER1R native invariant missing: ' + needle)

for forbidden in [
    'const double yBlendChromaScale = y > 1.0e-12 ? 1.0 + 0.35 * (yRatio - 1.0) : 0.0;',
    'const double yBlendChromaScale = y > 1.0e-12 ? 0.5 * (1.0 + yRatio) : 0.0;',
    'const double mappedCb = cb * yRatio;',
    'const double mappedCr = cr * yRatio;'
]:
    if forbidden in C:
        raise SystemExit('RENDER1R forbidden old live path remains: ' + forbidden)

if 'nativeInverseSrgbTransfer(bitmap)' in R or 'nativeEdgePass(bitmap, edgeIso)' in R:
    raise SystemExit('RENDER1R unexpectedly changed transfer/edge isolation')

print('M10-R RENDER1R YBLEND1C K020 applied')
print(' - only live photographic change vs RENDER1Q: chroma excess-gain inheritance k 0.35 -> 0.20')
print(' - mappedY / MEDIUM / DG / CC1MAP1A / NATIVEOUT1A unchanged')
print(' - REDTRACE stale CC1OFF/mode1 labels corrected; diagnostic-only')
print(' - EDGE0A, WB/CA9, exposure, JPEG, single RAW and HDR-off frozen')
print(' - controlled falsification probe only; no firmware formula claim')
