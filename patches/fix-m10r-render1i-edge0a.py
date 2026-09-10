#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix-m10r-render1i-edge0a.py <PhotonCamera-root>')
root = Path(sys.argv[1]).resolve()
if not (root / 'app').is_dir():
    raise SystemExit('RENDER1I EDGE0A: not a PhotonCamera root')

def rd(rel):
    p = root / rel
    if not p.exists():
        raise SystemExit('RENDER1I EDGE0A missing: ' + rel)
    return p.read_text()

def wr(rel, text):
    (root / rel).write_text(text)

def one(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit('RENDER1I EDGE0A anchor %s count=%d' % (label, n))
    return text.replace(old, new, 1)

# RENDER1I EDGE0A is the next one-variable photographic A/B on top of the
# positive TRANSFER1A control. It changes only whether the provisional EDGE1A
# spatial pass is executed. The native edge implementation, firmware-derived
# coefficients/tables, WORKING1A topology, upstream textbook sRGB OETF, and the
# post-edge-site TRANSFER1A inverse-sRGB diagnostic remain resident and frozen.
#
# This deliberately preserves the same quantized OETF -> inverse-OETF output
# path as RENDER1H so a device comparison answers one question only:
#   does the current domain-provisional EDGE1A improve the photograph enough to
#   justify keeping it while its native Leica B2Y/YC domain remains unresolved?
#
# If EDGE0A is photographically neutral/positive, the next clean architecture
# can remove BOTH the standalone OETF and diagnostic inverse pass together,
# rather than retaining a suspect transfer merely to service EDGE1A.

grad = 'app/build.gradle'
g = rd(grad)
g = one(
    g,
    "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1h-transfer1a-diag1c-saf1'",
    "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1i-edge0a-transfer1a-diag1c-saf1'",
    'version')
wr(grad, g)

renderer = 'app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'
r = rd(renderer)

# Skip only the edge call. Leave declaration + native implementation present so
# no arithmetic/table code is changed as part of this discriminator.
old_edge_call = '''            long edgeStartNs = System.nanoTime();\n            long edgeAffectedPixels = nativeEdgePass(bitmap, edgeIso);\n            double edgeElapsedMs = (System.nanoTime() - edgeStartNs) / 1_000_000.0;\n'''
new_edge_call = '''            // EDGE0A: bounded bypass. Keep the native EDGE1A implementation\n            // resident, but do not execute it on the photographic bitmap.\n            long edgeAffectedPixels = 0L;\n            double edgeElapsedMs = 0.0;\n'''
r = one(r, old_edge_call, new_edge_call, 'edge-call-bypass')

r = one(r,
        '            d.put("renderLook", "RENDER1H_TRANSFER1A_WORKING1A_YC2A_MATRIX1A");\n',
        '            d.put("renderLook", "RENDER1I_EDGE0A_TRANSFER1A_WORKING1A_YC2A_MATRIX1A");\n',
        'render-look')
r = one(r,
        '            d.put("outputTransferPlacement", "post_EDGE1A_before_JPEG");\n',
        '            d.put("outputTransferPlacement", "post_EDGE0A_bypass_before_JPEG");\n',
        'transfer-placement')
r = one(r,
        '            d.put("edgePassEnabled", true);\n',
        '''            d.put("edgePassEnabled", false);\n            d.put("edgeExperiment", "EDGE0A_BYPASS_ONLY");\n            d.put("edgeCallExecuted", false);\n            d.put("edgeNativeImplementationRetained", true);\n            d.put("edgeBypassReason", "domain_provisional_isolation_before_clean_native_output");\n            d.put("edge0aOnlyPhotographicVariable", true);\n            d.put("oetfRetainedForTransferControl", true);\n            d.put("transfer1aInverseRetainedForControl", true);\n''',
        'edge-enabled')

# These inherited fields described operations performed inside the edge call.
# Mark them false rather than leaving diagnostics that imply execution.
r = one(r,
        '            d.put("edgeScaleTableApplied", true);\n',
        '            d.put("edgeScaleTableApplied", false);\n',
        'edge-scale-applied')
r = one(r,
        '            d.put("edgeHfRecordGainApplied", true);\n',
        '            d.put("edgeHfRecordGainApplied", false);\n',
        'edge-hf-gain-applied')
wr(renderer, r)

# Hard isolation checks: EDGE1A code must still exist, its Java call must not;
# TRANSFER1A and the WORKING1A/OETF controls must remain exactly available.
G = rd(grad)
R = rd(renderer)
C = rd('app/src/main/cpp/m10rRender.cpp')

if "render1i-edge0a-transfer1a-diag1c-saf1'" not in G:
    raise SystemExit('RENDER1I EDGE0A build identity missing')

for needle in [
    'RENDER1I_EDGE0A_TRANSFER1A_WORKING1A_YC2A_MATRIX1A',
    'TRANSFER1A_POST_EDGE_INVERSE_SRGB_CANCEL',
    'post_EDGE0A_bypass_before_JPEG',
    'edgePassEnabled", false',
    'edgeExperiment", "EDGE0A_BYPASS_ONLY"',
    'edgeCallExecuted", false',
    'edgeNativeImplementationRetained", true',
    'edge0aOnlyPhotographicVariable", true',
    'oetfRetainedForTransferControl", true',
    'transfer1aInverseRetainedForControl", true',
    'edgeScaleTableApplied", false',
    'edgeHfRecordGainApplied", false',
    'nativeInverseSrgbTransfer(bitmap)',
    'workingBasisPlacementFix", "WORKING1A"',
    'nonlinearPlacement", "M10R_internal_working_RGB_between_CC0_CC1"',
    'cc1Placement", "post_MEDIUM_DG_before_sRGB_OETF"',
    'yc2aMatrixCorrectionApplied", true',
    'b2yYBlendApplied", false',
    'textureEnhancementBlockEnabled", false',
    'lowFrequencyEdgeApplied", false',
    'hdrEnabled", false',
    'sourceFrameCount", 1',
    'DIAG1C_SAF_ABSPATH'
]:
    if needle not in R:
        raise SystemExit('RENDER1I EDGE0A renderer invariant missing: ' + needle)

if 'nativeEdgePass(bitmap, edgeIso)' in R:
    raise SystemExit('RENDER1I EDGE0A isolation failed: native edge call still executes')

for needle in [
    'private static native long nativeEdgePass(Bitmap bitmap, int iso);',
    'private static native long nativeInverseSrgbTransfer(Bitmap bitmap);'
]:
    if needle not in R:
        raise SystemExit('RENDER1I EDGE0A resident Java native declaration missing: ' + needle)

for needle in [
    'M10RNativeRenderer_nativeEdgePass',
    'constexpr int kc=316, ka=-46, kd=-4, kb=-20, ko=-3, kk=-3',
    '*synthGain*edgeScale*hfRecordGain',
    'M10RNativeRenderer_nativeInverseSrgbTransfer',
    'std::pow((encoded + 0.055) / 1.055, 2.4)',
    'srgb8(outR)',
    'srgb8(outG)',
    'srgb8(outB)'
]:
    if needle not in C:
        raise SystemExit('RENDER1I EDGE0A native invariant missing: ' + needle)

# The inverse transfer must still occur before success/JPEG publication. The
# removed edge call must not reappear between bitmap creation and that transfer.
pos_transfer = R.index('long transferPixels = nativeInverseSrgbTransfer(bitmap);')
pos_status = R.index('d.put("status", "success");', pos_transfer)
if not (pos_transfer < pos_status):
    raise SystemExit('RENDER1I EDGE0A transfer ordering invariant failed')

print('M10-R RENDER1I EDGE0A applied')
print(' - ONLY photographic change: nativeEdgePass call bypassed')
print(' - EDGE1A native implementation/coefficient/table code retained but unused')
print(' - WORKING1A + MEDIUM/DG + LOOK1B + CC1 frozen')
print(' - upstream textbook sRGB OETF retained for TRANSFER1A control parity')
print(' - TRANSFER1A inverse-sRGB diagnostic retained unchanged')
print(' - single RAW, HDR-off, exposure, WB, matrices, 12MP and JPEG quality frozen')
