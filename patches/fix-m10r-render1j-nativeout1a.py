#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix-m10r-render1j-nativeout1a.py <PhotonCamera-root>')
root = Path(sys.argv[1]).resolve()
if not (root / 'app').is_dir():
    raise SystemExit('RENDER1J NATIVEOUT1A: not a PhotonCamera root')

def rd(rel):
    p = root / rel
    if not p.exists():
        raise SystemExit('RENDER1J NATIVEOUT1A missing: ' + rel)
    return p.read_text()

def wr(rel, text):
    (root / rel).write_text(text)

def one(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit('RENDER1J NATIVEOUT1A anchor %s count=%d' % (label, n))
    return text.replace(old, new, 1)

# RENDER1J NATIVEOUT1A is the clean architectural follow-up to the successful
# TRANSFER1A density discriminator and the device-acceptable EDGE0A bypass.
# It removes the redundant OETF -> inverse-OETF round trip from the live path:
#
#   ... MEDIUM/DG -> Yc inverse -> CC1 -> direct 8-bit clamp/round -> JPEG
#
# EDGE remains OFF.  WB, CA9, source/target matrices, WORKING1A placement,
# MEDIUM/DG, Yc/LOOK1B, exposure, JPEG quality, single RAW and HDR-off behavior
# are frozen.  The old sRGB helper and inverse-transfer implementation remain
# resident only as non-executed research/control code, so the runtime change is
# tightly bounded and easy to audit.
#
# IMPORTANT: direct 8-bit publication is a photographic architecture test, not
# a claim that the exact M10-R output colour encoding has been proven.

grad = 'app/build.gradle'
g = rd(grad)
g = one(
    g,
    "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1i-edge0a-transfer1a-diag1c-saf1'",
    "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1j-edge0a-nativeout1a-diag1c-saf1'",
    'version')
wr(grad, g)

renderer = 'app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'
r = rd(renderer)

old_transfer = '''            long transferStartNs = System.nanoTime();\n            long transferPixels = nativeInverseSrgbTransfer(bitmap);\n            double transferElapsedMs = (System.nanoTime() - transferStartNs) / 1_000_000.0;\n            if (transferPixels < 0) {\n                throw new IllegalStateException("M10-R TRANSFER1A native inverse-sRGB failed code=" + transferPixels);\n            }\n            d.put("renderLook", "RENDER1I_EDGE0A_TRANSFER1A_WORKING1A_YC2A_MATRIX1A");\n            d.put("outputTransferExperiment", "TRANSFER1A_POST_EDGE_INVERSE_SRGB_CANCEL");\n            d.put("outputTransferPlacement", "post_EDGE0A_bypass_before_JPEG");\n            d.put("working1aNativeSrgbOetfRetainedForEdgeInvariant", true);\n            d.put("edgeInputDomainUnchangedFromWorking1A", true);\n            d.put("netOutputTransfer", "linear_coded_after_inverse_sRGB");\n            d.put("outputTransferQuantization", "8bit_sRGB_roundtrip_diagnostic");\n            d.put("outputTransferExactHardwareParityClaimed", false);\n            d.put("outputTransferPixels", transferPixels);\n            d.put("outputTransferElapsedMs", transferElapsedMs);\n'''
new_transfer = '''            // NATIVEOUT1A: no separate display-transfer pass.  The native\n            // pixel core now publishes post-CC1 values directly with 8-bit\n            // linear clamp/round.  EDGE0A remains bypassed.\n            long transferPixels = 0L;\n            double transferElapsedMs = 0.0;\n            d.put("renderLook", "RENDER1J_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A");\n            d.put("outputTransferExperiment", "NATIVEOUT1A_DIRECT_POST_CC1_LINEAR8");\n            d.put("outputTransferPlacement", "native_post_CC1_direct_8bit_before_JPEG");\n            d.put("working1aNativeSrgbOetfRetainedForEdgeInvariant", false);\n            d.put("edgeInputDomainUnchangedFromWorking1A", false);\n            d.put("edgeInputDomainNotApplicableDueEdge0A", true);\n            d.put("netOutputTransfer", "post_CC1_linear_direct_8bit");\n            d.put("outputTransferQuantization", "direct_8bit_linear_round_clamp");\n            d.put("outputTransferExactHardwareParityClaimed", false);\n            d.put("outputTransferPixels", transferPixels);\n            d.put("outputTransferElapsedMs", transferElapsedMs);\n            d.put("outputTransferSeparatePassExecuted", false);\n            d.put("textbookSrgbOetfApplied", false);\n            d.put("transfer1aInverseExecuted", false);\n            d.put("transferRoundTripRemoved", true);\n            d.put("nativePixelOutputQuantizer", "linear8_post_CC1");\n            d.put("inverseSrgbImplementationRetainedUnused", true);\n'''
r = one(r, old_transfer, new_transfer, 'remove-transfer-roundtrip')

r = one(r,
        '        d.put("cc1Placement", "post_MEDIUM_DG_before_sRGB_OETF");\n',
        '        d.put("cc1Placement", "post_MEDIUM_DG_before_direct_8bit_output");\n',
        'cc1-placement-metadata')
wr(renderer, r)

cpp = 'app/src/main/cpp/m10rRender.cpp'
c = rd(cpp)

srgb_helper = '''inline int srgb8(double linear) {\n    if (!std::isfinite(linear)) return 0;\n    double c = std::max(0.0, std::min(1.0, linear));\n    double e = c <= 0.0031308 ? 12.92*c : 1.055*std::pow(c, 1.0/2.4)-0.055;\n    e = std::max(0.0, std::min(1.0, e));\n    return static_cast<int>(std::floor(e * 255.0 + 0.5));\n}\n'''
linear_helper = srgb_helper + '''\ninline int linear8(double linear) {\n    if (!std::isfinite(linear)) return 0;\n    const double c = std::max(0.0, std::min(1.0, linear));\n    return static_cast<int>(std::floor(c * 255.0 + 0.5));\n}\n'''
c = one(c, srgb_helper, linear_helper, 'linear8-helper')

for ch in ['R', 'G', 'B']:
    c = one(c, 'srgb8(out%s)' % ch, 'linear8(out%s)' % ch, 'post-cc1-linear8-' + ch)
wr(cpp, c)

# Hard architectural checks.
G = rd(grad)
R = rd(renderer)
C = rd(cpp)

if "render1j-edge0a-nativeout1a-diag1c-saf1'" not in G:
    raise SystemExit('RENDER1J NATIVEOUT1A build identity missing')

for needle in [
    'RENDER1J_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A',
    'NATIVEOUT1A_DIRECT_POST_CC1_LINEAR8',
    'native_post_CC1_direct_8bit_before_JPEG',
    'post_CC1_linear_direct_8bit',
    'direct_8bit_linear_round_clamp',
    'outputTransferSeparatePassExecuted", false',
    'textbookSrgbOetfApplied", false',
    'transfer1aInverseExecuted", false',
    'transferRoundTripRemoved", true',
    'nativePixelOutputQuantizer", "linear8_post_CC1"',
    'inverseSrgbImplementationRetainedUnused", true',
    'edgePassEnabled", false',
    'edgeExperiment", "EDGE0A_BYPASS_ONLY"',
    'edgeCallExecuted", false',
    'edgeScaleTableApplied", false',
    'edgeHfRecordGainApplied", false',
    'workingBasisPlacementFix", "WORKING1A"',
    'nonlinearPlacement", "M10R_internal_working_RGB_between_CC0_CC1"',
    'cc1Placement", "post_MEDIUM_DG_before_direct_8bit_output"',
    'yc2aMatrixCorrectionApplied", true',
    'b2yYBlendApplied", false',
    'textureEnhancementBlockEnabled", false',
    'lowFrequencyEdgeApplied", false',
    'hdrEnabled", false',
    'sourceFrameCount", 1',
    'DIAG1C_SAF_ABSPATH'
]:
    if needle not in R:
        raise SystemExit('RENDER1J NATIVEOUT1A renderer invariant missing: ' + needle)

if 'nativeInverseSrgbTransfer(bitmap)' in R:
    raise SystemExit('RENDER1J NATIVEOUT1A isolation failed: inverse-sRGB runtime call remains')
if 'nativeEdgePass(bitmap, edgeIso)' in R:
    raise SystemExit('RENDER1J NATIVEOUT1A isolation failed: edge runtime call reappeared')

for needle in [
    'inline int srgb8(double linear)',
    'inline int linear8(double linear)',
    'linear8(outR)',
    'linear8(outG)',
    'linear8(outB)',
    'M10RNativeRenderer_nativeInverseSrgbTransfer',
    'M10RNativeRenderer_nativeEdgePass'
]:
    if needle not in C:
        raise SystemExit('RENDER1J NATIVEOUT1A native invariant missing: ' + needle)

for needle in ['srgb8(outR)', 'srgb8(outG)', 'srgb8(outB)']:
    if needle in C:
        raise SystemExit('RENDER1J NATIVEOUT1A old live OETF output remains: ' + needle)

# The retained inverse implementation must be unreachable from Java runtime;
# direct linear quantization is now the sole nativeProcessTile publication path.
pos_linear = C.index('linear8(outR)')
pos_inverse_impl = C.index('M10RNativeRenderer_nativeInverseSrgbTransfer')
if pos_linear < 0 or pos_inverse_impl < 0:
    raise SystemExit('RENDER1J NATIVEOUT1A native ordering audit failed')

print('M10-R RENDER1J NATIVEOUT1A applied')
print(' - EDGE0A remains bypassed')
print(' - nativeProcessTile publishes post-CC1 values with direct linear 8-bit clamp/round')
print(' - textbook sRGB OETF no longer executes for photographic output')
print(' - TRANSFER1A inverse-sRGB pass no longer executes')
print(' - old sRGB/inverse implementations retained only as unreachable research controls')
print(' - WORKING1A, MEDIUM/DG, Yc/LOOK1B, WB/CA9/matrices/exposure/JPEG/single-RAW/HDR-off frozen')
print(' - exact M10-R output encoding is NOT claimed')
