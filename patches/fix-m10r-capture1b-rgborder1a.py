#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix-m10r-capture1b-rgborder1a.py <PhotonCamera-root>')

root = Path(sys.argv[1]).resolve()
if not (root / 'app').is_dir():
    raise SystemExit('CAPTURE1B RGBORDER1A: not a PhotonCamera root')

renderer = root / 'app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'
if not renderer.exists():
    raise SystemExit('CAPTURE1B RGBORDER1A: generated renderer missing')

r = renderer.read_text()

# OpenCV's Bayer *2BGR_EA aliases used by this renderer produce the camera
# channels in RGB memory order for these CFA conversions (the same convention
# consumed by the proven M9 renderer/native core). CAPTURE1B incorrectly read
# channel 0 as blue and channel 2 as red, effectively swapping R/B after a
# correct demosaic. Fix only that handoff; source matrices, target matrices,
# CA9, CFA selection, shading and all other rendering stages remain unchanged.
old = '''                    double sb = (bgr[i * 3] & 0xffff) / 65535.0 * inverseStorageScale;\n                    double sg = (bgr[i * 3 + 1] & 0xffff) / 65535.0 * inverseStorageScale;\n                    double sr = (bgr[i * 3 + 2] & 0xffff) / 65535.0 * inverseStorageScale;\n\n                    double tr = srcToTargetCamera[0]*sr + srcToTargetCamera[1]*sg + srcToTargetCamera[2]*sb;'''
new = '''                    // RGBORDER1A: OpenCV EA Bayer output is consumed in the same RGB\n                    // channel order as the proven M9 path. Do not reverse R/B here.\n                    double sr = (bgr[i * 3] & 0xffff) / 65535.0 * inverseStorageScale;\n                    double sg = (bgr[i * 3 + 1] & 0xffff) / 65535.0 * inverseStorageScale;\n                    double sb = (bgr[i * 3 + 2] & 0xffff) / 65535.0 * inverseStorageScale;\n\n                    double tr = srcToTargetCamera[0]*sr + srcToTargetCamera[1]*sg + srcToTargetCamera[2]*sb;'''
if new not in r:
    if r.count(old) != 1:
        raise SystemExit('CAPTURE1B RGBORDER1A channel-order anchor missing/non-unique')
    r = r.replace(old, new, 1)

anchor = '''        d.put("fourBayerPatternsSupported", true);\n'''
insert = anchor + '''        d.put("demosaicOutputChannelOrder", "RGB");\n        d.put("demosaicChannelOrderFix", "RGBORDER1A");\n        d.put("postDemosaicRedBlueSwapApplied", false);\n'''
if 'demosaicChannelOrderFix", "RGBORDER1A"' not in r:
    if r.count(anchor) != 1:
        raise SystemExit('CAPTURE1B RGBORDER1A diagnostic anchor missing/non-unique')
    r = r.replace(anchor, insert, 1)

renderer.write_text(r)

# Hard invariants: require corrected channel reads and forbid the old R/B reversal.
r = renderer.read_text()
required = [
    'double sr = (bgr[i * 3] & 0xffff) / 65535.0 * inverseStorageScale;',
    'double sg = (bgr[i * 3 + 1] & 0xffff) / 65535.0 * inverseStorageScale;',
    'double sb = (bgr[i * 3 + 2] & 0xffff) / 65535.0 * inverseStorageScale;',
    'demosaicOutputChannelOrder", "RGB"',
    'demosaicChannelOrderFix", "RGBORDER1A"',
    'postDemosaicRedBlueSwapApplied", false',
    'sourceColorMatrixRowNormalizationApplied", false',
    'sourceForwardMatrixNormalizationApplied", true',
    'ca9NeutralClipEnabled", true',
]
for needle in required:
    if needle not in r:
        raise SystemExit('CAPTURE1B RGBORDER1A verify missing: ' + needle)

for forbidden in [
    'double sb = (bgr[i * 3] & 0xffff) / 65535.0 * inverseStorageScale;\n                    double sg = (bgr[i * 3 + 1] & 0xffff) / 65535.0 * inverseStorageScale;\n                    double sr = (bgr[i * 3 + 2] & 0xffff) / 65535.0 * inverseStorageScale;',
]:
    if forbidden in r:
        raise SystemExit('CAPTURE1B RGBORDER1A old R/B reversal still present')

print('M10-R CAPTURE1B RGBORDER1A applied')
print(' - OpenCV demosaic output now consumed as R,G,B')
print(' - erroneous post-demosaic red/blue reversal removed')
print(' - Bayer/CFA selection unchanged')
print(' - Camera2 source matrices unchanged for this test')
print(' - M10-R target transform and CA9 unchanged')
print(' - single-frame/no-HDR route unchanged')
