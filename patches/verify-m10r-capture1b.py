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
dng=text('app/src/main/java/com/particlesdevs/photoncamera/processing/DngCreator.java')

required = {
    'gradle': ["applicationId 'com.m10rproject.m10rcam.photon'", "versionName '0.97-m10rcapture1b'",
               "implementation 'org.opencv:opencv:4.13.0'"],
    'frames': ['CameraMode.PHOTO', 'frameCount = 1', 'throwCount = 0', 'return 1;'],
    'saver': ['M10RNativeRenderer.render(', 'ImageSaver.Util.saveSingleRaw(', 'ImageSaver.Util.saveBitmapAsJPG(',
              'capture1Frame.close()', 'DNG remains unconditional and uses the same untouched single RAW frame',
              'persistFailureDiagnostics(', 'device1RenderBeforeDng'],
    'renderer': ['sourceFrameCount", 1', 'hdrEnabled", false', 'stackingEnabled", false',
                 'photonPostPipelineUsed", false', 'cobaltRuntimeDependency", false',
                 'sourceColorMatrixRowNormalizationApplied", false',
                 'sourceForwardMatrixNormalizationApplied", true',
                 'fourBayerPatternsSupported", true', 'case 0: return new int[]{0,1,2,3}',
                 'case 1: return new int[]{1,0,3,2}', 'case 2: return new int[]{1,3,0,2}',
                 'case 3: return new int[]{3,1,2,0}', 'COLOR_BayerGR2BGR_EA',
                 'rawHeadroomRetained", false', 'ca9NeutralClipEnabled", true',
                 'Math.rint(ASN_SCALE / asn[i])', 'org.opencv:opencv:4.13.0',
                 'persistFailureDiagnostics(Path dngPath'],
    'dng': ['DNGGAINMAPFIX1A', 'parameters.sensorPix.left', 'parameters.sensorPix.top',
            'parameters.sensorPix.right', 'parameters.sensorPix.bottom']
}
for name, needles in required.items():
    hay={'gradle':gradle,'frames':frames,'saver':saver,'renderer':renderer,'dng':dng}[name]
    for n in needles:
        if n not in hay: raise SystemExit('CAPTURE1B verify %s missing %r' % (name,n))

# The DNG JNI ABI is xmin/ymin/xmax/ymax.  Guard exact argument order so the
# horizontal GainMap seam fixed on-device in the M9 project cannot regress here.
correct_gainmap = '''        setGainMap(parameters.gainMap,\n                   parameters.sensorPix.left,\n                   parameters.sensorPix.top,\n                   parameters.sensorPix.right,\n                   parameters.sensorPix.bottom,\n                   parameters.mapSize.x,\n                   parameters.mapSize.y);'''
wrong_gainmap = '''        setGainMap(parameters.gainMap,\n                   parameters.sensorPix.top,\n                   parameters.sensorPix.left,\n                   parameters.sensorPix.bottom,\n                   parameters.sensorPix.right,\n                   parameters.mapSize.x,\n                   parameters.mapSize.y);'''
if correct_gainmap not in dng or wrong_gainmap in dng:
    raise SystemExit('CAPTURE1B DNG GainMap x/y geometry regression')

# DEVICE1 deliberately renders/publishes the JPEG before constructing the DNG.
# That keeps the full DNG creation buffers from overlapping the full OpenCV/Bitmap
# render while preserving the same untouched RAW for both outputs.
pos_render=saver.find('capture1b = M10RNativeRenderer.render(')
pos_jpeg=saver.find('jpegSaved = ImageSaver.Util.saveBitmapAsJPG(', pos_render)
pos_dng=saver.find('dngSaved = ImageSaver.Util.saveSingleRaw(', pos_render)
pos_return=saver.find('            return;\n        }', pos_render)
pos_hdr=saver.find('        hdrxProcessor.configure(', pos_render)
if min(pos_render,pos_jpeg,pos_dng,pos_return,pos_hdr) < 0:
    raise SystemExit('CAPTURE1B DEVICE1 route markers missing')
if not (pos_render < pos_jpeg < pos_dng < pos_return < pos_hdr):
    raise SystemExit('CAPTURE1B DEVICE1 route order invalid: expected render/JPEG -> DNG -> return -> legacy HDR')

# DNG must remain outside the render try/catch so a JPEG renderer exception cannot
# suppress RAW publication.
pos_render_try=saver.rfind('                try {', 0, pos_render)
pos_render_catch=saver.find('                } catch (Throwable renderError)', pos_render)
if min(pos_render_try,pos_render_catch) < 0 or not (pos_render_try < pos_render < pos_render_catch < pos_dng):
    raise SystemExit('CAPTURE1B DEVICE1 DNG is not preserved after render failure')

# Prevent accidental reintroduction of Cobalt/profile LUT naming in the integration renderer.
for forbidden in ['Cobalt_', 'm9_r35_calibration', 'ProfileHueSatMap', 'HdrxProcessor']:
    if forbidden in renderer:
        raise SystemExit('CAPTURE1B renderer forbidden dependency: '+forbidden)
if 'photonPostPipelineUsed", false' not in renderer:
    raise SystemExit('CAPTURE1B PostPipeline false diagnostic missing')

print('M10-R CAPTURE1B DEVICE1 verification PASS')
print(' - pinned single-frame CAPTURE1 semantics retained')
print(' - JPEG renders before DNG to bound peak memory')
print(' - DNG remains unconditional after renderer failure')
print(' - M9-validated GainMap x/y geometry fix enforced')
print(' - OpenCV Android 4.13.0 enforced')
print(' - pre-Result renderer failures produce a diagnostic sidecar')
print(' - no HDR/stacking/Photon post pipeline on normal PHOTO route')
print(' - no Cobalt source profile dependency')
print(' - all four Bayer CFA layouts represented in source adapter')
print(' - ColorMatrix convention correction enforced')
print(' - promoted C boundary enforced: headroom OFF / CA9 clip ON')
