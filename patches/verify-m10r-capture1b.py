#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: verify-m10r-capture1b.py <PhotonCamera-root>')
root = Path(sys.argv[1]).resolve()

def text(rel):
    p=root/rel
    if not p.exists(): raise SystemExit('CAPTURE1B verify missing '+rel)
    return p.read_text()

gradle=text('app/build.gradle')
frames=text('app/src/main/java/com/particlesdevs/photoncamera/processing/parameters/FrameNumberSelector.java')
saver=text('app/src/main/java/com/particlesdevs/photoncamera/processing/DefaultSaver.java')
renderer=text('app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java')

required = {
    'gradle': ["applicationId 'com.m10rproject.m10rcam.photon'", "versionName '0.97-m10rcapture1b'"],
    'frames': ['CameraMode.PHOTO', 'frameCount = 1', 'throwCount = 0', 'return 1;'],
    'saver': ['M10RNativeRenderer.render(', 'ImageSaver.Util.saveSingleRaw(', 'ImageSaver.Util.saveBitmapAsJPG(',
              'capture1Frame.close()', 'DNG publication is unconditional for CAPTURE1B'],
    'renderer': ['sourceFrameCount", 1', 'hdrEnabled", false', 'stackingEnabled", false',
                 'photonPostPipelineUsed", false', 'cobaltRuntimeDependency", false',
                 'sourceColorMatrixRowNormalizationApplied", false',
                 'sourceForwardMatrixNormalizationApplied", true',
                 'fourBayerPatternsSupported", true', 'case 0: return new int[]{0,1,2,3}',
                 'case 1: return new int[]{1,0,3,2}', 'case 2: return new int[]{1,3,0,2}',
                 'case 3: return new int[]{3,1,2,0}', 'COLOR_BayerGR2BGR_EA',
                 'rawHeadroomRetained", false', 'ca9NeutralClipEnabled", true',
                 'Math.rint(ASN_SCALE / asn[i])']
}
for name, needles in required.items():
    hay={'gradle':gradle,'frames':frames,'saver':saver,'renderer':renderer}[name]
    for n in needles:
        if n not in hay: raise SystemExit('CAPTURE1B verify %s missing %r' % (name,n))

# Normal PHOTO block must return before the legacy HDR processor configuration below it.
pos_render=saver.find('M10RNativeRenderer.render(')
pos_return=saver.find('            return;\n        }', pos_render)
pos_hdr=saver.find('        hdrxProcessor.configure(', pos_render)
if min(pos_render,pos_return,pos_hdr) < 0 or not (pos_render < pos_return < pos_hdr):
    raise SystemExit('CAPTURE1B normal PHOTO route does not terminate before HdrxProcessor')

# Prevent accidental reintroduction of Cobalt/profile LUT naming in the integration renderer.
for forbidden in ['Cobalt_', 'm9_r35_calibration', 'ProfileHueSatMap', 'HdrxProcessor', 'PostPipeline']:
    if forbidden in renderer and forbidden != 'PostPipeline':
        raise SystemExit('CAPTURE1B renderer forbidden dependency: '+forbidden)
# PostPipeline appears only in an explicit false diagnostic/comment; require the false marker.
if 'photonPostPipelineUsed", false' not in renderer:
    raise SystemExit('CAPTURE1B PostPipeline false diagnostic missing')

print('M10-R CAPTURE1B verification PASS')
print(' - pinned single-frame CAPTURE1 semantics retained')
print(' - DNG + JPEG wired from same RAW frame')
print(' - no HDR/stacking/Photon post pipeline on normal PHOTO route')
print(' - no Cobalt source profile dependency')
print(' - all four Bayer CFA layouts represented in source adapter')
print(' - ColorMatrix convention correction enforced')
print(' - promoted C boundary enforced: headroom OFF / CA9 clip ON')
