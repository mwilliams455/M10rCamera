#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix-m10r-render1p-cc1map1a.py <PhotonCamera-root>')
root = Path(sys.argv[1]).resolve()
if not (root / 'app').is_dir():
    raise SystemExit('RENDER1P CC1MAP1A: not a PhotonCamera root')

def rd(rel):
    p = root / rel
    if not p.exists():
        raise SystemExit('RENDER1P CC1MAP1A missing: ' + rel)
    return p.read_text()

def wr(rel, text):
    (root / rel).write_text(text)

def one(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit('RENDER1P CC1MAP1A anchor %s count=%d' % (label, n))
    return text.replace(old, new, 1)

# RENDER1P changes exactly one photographic variable on top of RENDER1O:
# correct DEFAULT_SRGB_CC1 from constructor row/mode 1 to factory STILL
# CA9 mode 0. Firmware + standard-space closure identifies the field1 CC1 rows:
#   mode 0 = ProPhoto RGB -> sRGB
#   mode 1 = ProPhoto RGB -> Adobe RGB
#   mode 2 = ProPhoto RGB -> ECI RGB
# RENDER1O used mode 1 because v2.30 initially inferred semantics from the
# companion field2 getter. No Y_BLEND, MEDIUM/DG, WB/CA9, exposure, source
# calibration, output quantizer, JPEG quality, edge, transfer or HDR changes.

grad = 'app/build.gradle'
g = rd(grad)
g = one(
    g,
    "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1o-cc1on1a-yblend1a-redtrace1b-edge0a-nativeout1a-diag1c-saf1'",
    "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1p-cc1map1a-yblend1a-redtrace1b-edge0a-nativeout1a-diag1c-saf1'",
    'version')
wr(grad, g)

renderer = 'app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'
r = rd(renderer)
old_m = '''    private static final double[] DEFAULT_SRGB_CC1 = {\n            1.3895, -0.1693, -0.2202,\n           -0.2288,  1.2317, -0.0029,\n           -0.0176, -0.0963,  1.1139\n    };\n'''
new_m = '''    // CC1MAP1A: factory STILL sRGB maps to CA9 mode 0. The recovered\n    // field1 matrix is ProPhoto RGB -> sRGB (max standard-matrix error <5e-5).\n    private static final double[] DEFAULT_SRGB_CC1 = {\n            2.0341, -0.7273, -0.3067,\n           -0.2288,  1.2317, -0.0029,\n           -0.0086, -0.1533,  1.1619\n    };\n'''
r = one(r, old_m, new_m, 'default-srgb-cc1-mode0')

r = one(
    r,
    '            d.put("renderLook", "RENDER1O_CC1ON1A_YBLEND1A_REDTRACE1B_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A");\n',
    '''            d.put("renderLook", "RENDER1P_CC1MAP1A_YBLEND1A_REDTRACE1B_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A");
            d.put("cc1MappingFix", "CC1MAP1A");
            d.put("cc1FactoryStillColorSpace", "sRGB");
            d.put("cc1Ca9ModeIndex", 0);
            d.put("cc1Semantic", "ProPhoto_RGB_to_sRGB");
            d.put("cc1Mode1PriorMislabel", "ProPhoto_RGB_to_AdobeRGB");
            d.put("cc1MappingFirmwareEvidence", "v231_factory_sRGB_to_CA9_mode0_plus_v230_field1_standard_matrix_closure");
''',
    'render-identity')
r = one(
    r,
    '            d.put("photographicConvergenceExperiment", "CC1ON1A_RESTORE_AFTER_VALIDATED_YBLEND1A");\n',
    '            d.put("photographicConvergenceExperiment", "CC1MAP1A_EXACT_FACTORY_SRGB_ROW");\n',
    'experiment')
wr(renderer, r)

G = rd(grad); R = rd(renderer)
if "render1p-cc1map1a-yblend1a-redtrace1b-edge0a-nativeout1a-diag1c-saf1'" not in G:
    raise SystemExit('RENDER1P CC1MAP1A version identity missing')
for needle in [
    '2.0341, -0.7273, -0.3067',
    '-0.0086, -0.1533,  1.1619',
    'RENDER1P_CC1MAP1A_YBLEND1A_REDTRACE1B_NATIVEOUT1A_EDGE0A_WORKING1A_YC2A_MATRIX1A',
    'cc1MappingFix", "CC1MAP1A"',
    'cc1FactoryStillColorSpace", "sRGB"',
    'cc1Ca9ModeIndex", 0',
    'cc1Semantic", "ProPhoto_RGB_to_sRGB"',
    'CC1MAP1A_EXACT_FACTORY_SRGB_ROW',
    'cc1AppliedToPhotographicPixels", true',
    'cc1RestoreOnlyPhotographicVariable", true',
    'workingBasisPlacementFix", "WORKING1A"',
    'yc2aMatrixCorrectionApplied", true',
    'textbookSrgbOetfApplied", false',
    'edgePassEnabled", false',
    'hdrEnabled", false',
    'sourceFrameCount", 1'
]:
    if needle not in R:
        raise SystemExit('RENDER1P CC1MAP1A invariant missing: ' + needle)
if '1.3895, -0.1693, -0.2202' in R:
    raise SystemExit('RENDER1P CC1MAP1A old mode-1/Adobe output CC1 still present')

print('M10-R RENDER1P CC1MAP1A applied')
print(' - one photographic change: DEFAULT_SRGB_CC1 mode 1 -> mode 0')
print(' - mode 0 identified as ProPhoto RGB -> sRGB from exact standard-space closure')
print(' - mode 1 identified as ProPhoto RGB -> Adobe RGB; prior DEFAULT_SRGB label was wrong')
print(' - RENDER1O YBLEND1A, MEDIUM/DG, WB/CA9, exposure, NATIVEOUT1A, EDGE0A, JPEG and HDR-off frozen')
