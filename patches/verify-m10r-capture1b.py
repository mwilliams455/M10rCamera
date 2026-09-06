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
image_saver=text('app/src/main/java/com/particlesdevs/photoncamera/processing/ImageSaver.java')

required = {
    'gradle': ["applicationId 'com.m10rproject.m10rcam.photon'", "versionName '0.97-m10rcapture1b-jpegsave1'",
               "implementation 'org.opencv:opencv:4.13.0'"],
    'frames': ['CameraMode.PHOTO', 'frameCount = 1', 'throwCount = 0', 'return 1;'],
    'saver': ['M10RNativeRenderer.render(', 'ImageSaver.Util.saveSingleRaw(', 'ImageSaver.Util.saveBitmapAsJPGM10R(',
              'capture1Dng.resolveSibling(capture1Stem + ".jpg")', 'capture1Frame.close()',
              'DNG remains unconditional and uses the same untouched single RAW frame',
              'persistFailureDiagnostics(', 'device1RenderBeforeDng',
              'm10r_jpegsave1_same_dng_dir_explicit_jpg_best_effort_exif'],
    'image_saver': ['public static boolean saveBitmapAsJPGM10R(', 'Files.createDirectories(parent)',
                    'JPEG encoder/write produced no bytes',
                    'EXIF finalisation failed but JPEG bytes are preserved',
                    'M10-R JPEGSAVE1 JPEG saved bytes='],
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
    hay={'gradle':gradle,'frames':frames,'saver':saver,'image_saver':image_saver,
         'renderer':renderer,'dng':dng}[name]
    for n in needles:
        if n not in hay: raise SystemExit('CAPTURE1B verify %s missing %r' % (name,n))

correct_gainmap = '''        setGainMap(parameters.gainMap,\n                   parameters.sensorPix.left,\n                   parameters.sensorPix.top,\n                   parameters.sensorPix.right,\n                   parameters.sensorPix.bottom,\n                   parameters.mapSize.x,\n                   parameters.mapSize.y);'''
wrong_gainmap = '''        setGainMap(parameters.gainMap,\n                   parameters.sensorPix.top,\n                   parameters.sensorPix.left,\n                   parameters.sensorPix.bottom,\n                   parameters.sensorPix.right,\n                   parameters.mapSize.x,\n                   parameters.mapSize.y);'''
if correct_gainmap not in dng or wrong_gainmap in dng:
    raise SystemExit('CAPTURE1B DNG GainMap x/y geometry regression')

pos_render=saver.find('capture1b = M10RNativeRenderer.render(')
pos_jpeg=saver.find('jpegSaved = ImageSaver.Util.saveBitmapAsJPGM10R(', pos_render)
pos_dng=saver.find('dngSaved = ImageSaver.Util.saveSingleRaw(', pos_render)
pos_return=saver.find('            return;\n        }', pos_render)
pos_hdr=saver.find('        hdrxProcessor.configure(', pos_render)
if min(pos_render,pos_jpeg,pos_dng,pos_return,pos_hdr) < 0:
    raise SystemExit('CAPTURE1B DEVICE1 route markers missing')
if not (pos_render < pos_jpeg < pos_dng < pos_return < pos_hdr):
    raise SystemExit('CAPTURE1B DEVICE1 route order invalid: expected render/JPEG -> DNG -> return -> legacy HDR')

pos_render_try=saver.rfind('                try {', 0, pos_render)
pos_render_catch=saver.find('                } catch (Throwable renderError)', pos_render)
if min(pos_render_try,pos_render_catch) < 0 or not (pos_render_try < pos_render < pos_render_catch < pos_dng):
    raise SystemExit('CAPTURE1B DEVICE1 DNG is not preserved after render failure')

# Restrict this check to the CAPTURE1B early-return route. Legacy Photon code below
# the return still uses ImagePath.newImageFilePath(), but CAPTURE1B never reaches it.
cap_block_start=saver.find('// M10R CAPTURE1B:')
cap_block_end=saver.find('            return;\n        }', cap_block_start)
if cap_block_start < 0 or cap_block_end < 0:
    raise SystemExit('CAPTURE1B JPEGSAVE1 route bounds missing')
cap_block=saver[cap_block_start:cap_block_end]
if 'ImagePath.newImageFilePath()' in cap_block:
    raise SystemExit('CAPTURE1B JPEGSAVE1 regressed to extensionless ImagePath.newImageFilePath()')
if 'capture1Dng.resolveSibling(capture1Stem + ".jpg")' not in cap_block:
    raise SystemExit('CAPTURE1B JPEGSAVE1 same-stem sibling path missing')

for forbidden in ['Cobalt_', 'm9_r35_calibration', 'ProfileHueSatMap', 'HdrxProcessor']:
    if forbidden in renderer:
        raise SystemExit('CAPTURE1B renderer forbidden dependency: '+forbidden)
if 'photonPostPipelineUsed", false' not in renderer:
    raise SystemExit('CAPTURE1B PostPipeline false diagnostic missing')

print('M10-R CAPTURE1B JPEGSAVE1 verification PASS')
print(' - build identity 0.97-m10rcapture1b-jpegsave1 enforced')
print(' - pinned single-frame CAPTURE1 semantics retained')
print(' - JPEG renders before DNG to bound peak memory')
print(' - JPEG uses same proven-writable DNG directory and explicit .jpg suffix')
print(' - JPEG byte persistence is authoritative; EXIF is best effort')
print(' - DNG remains unconditional after renderer failure')
print(' - M9-validated GainMap x/y geometry fix enforced')
print(' - OpenCV Android 4.13.0 enforced')
print(' - pre-Result renderer failures produce a diagnostic sidecar')
print(' - no HDR/stacking/Photon post pipeline on normal PHOTO route')
print(' - no Cobalt source profile dependency')
print(' - all four Bayer CFA layouts represented in source adapter')
print(' - ColorMatrix convention correction enforced')
print(' - promoted C boundary enforced: headroom OFF / CA9 clip ON')
