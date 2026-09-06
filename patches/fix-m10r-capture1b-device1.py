#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix-m10r-capture1b-device1.py <PhotonCamera-root>')

root = Path(sys.argv[1]).resolve()
if not (root / 'app').is_dir():
    raise SystemExit('CAPTURE1B DEVICE1: not a PhotonCamera root')

# 1) Port the device-validated M9 DNGGAINMAPFIX1A exactly: Photon passes Android
# Rect top/left/bottom/right into a JNI x/y API.  The corrected call is
# left/top/right/bottom.  This changes only DNG GainMap geometry.
dng = root / 'app/src/main/java/com/particlesdevs/photoncamera/processing/DngCreator.java'
s = dng.read_text()
old = '''        setGainMap(parameters.gainMap,\n                   parameters.sensorPix.top,\n                   parameters.sensorPix.left,\n                   parameters.sensorPix.bottom,\n                   parameters.sensorPix.right,\n                   parameters.mapSize.x,\n                   parameters.mapSize.y);'''
new = '''        // M10R CAPTURE1B DEVICE1 / DNGGAINMAPFIX1A: native setGainMap uses x/y ordering.\n        // Android Rect is top/left/bottom/right, so pass left/top/right/bottom.\n        setGainMap(parameters.gainMap,\n                   parameters.sensorPix.left,\n                   parameters.sensorPix.top,\n                   parameters.sensorPix.right,\n                   parameters.sensorPix.bottom,\n                   parameters.mapSize.x,\n                   parameters.mapSize.y);'''
if new not in s:
    if s.count(old) != 1:
        raise SystemExit('CAPTURE1B DEVICE1 DNG GainMap anchor missing/non-unique')
    s = s.replace(old, new, 1)
dng.write_text(s)

# 2) Use the same OpenCV Android version already proven on-device by the current
# M9 project.  CAPTURE1B originally used 4.10.0; M9 uses 4.13.0 on this phone.
gradle = root / 'app/build.gradle'
g = gradle.read_text()
if "implementation 'org.opencv:opencv:4.10.0'" in g:
    g = g.replace("implementation 'org.opencv:opencv:4.10.0'",
                  "implementation 'org.opencv:opencv:4.13.0'", 1)
elif "implementation 'org.opencv:opencv:4.13.0'" not in g:
    raise SystemExit('CAPTURE1B DEVICE1 OpenCV dependency anchor missing')
gradle.write_text(g)

renderer = root / 'app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'
r = renderer.read_text()
r = r.replace('d.put("openCvAndroidAar", "org.opencv:opencv:4.10.0");',
              'd.put("openCvAndroidAar", "org.opencv:opencv:4.13.0");')

# Add a failure sidecar that exists even when render() fails before returning Result.
anchor = '''    public static void persistDiagnostics(Path dngPath, JSONObject diagnostics) {\n        if (dngPath == null || diagnostics == null) return;\n'''
if anchor not in r:
    raise SystemExit('CAPTURE1B DEVICE1 diagnostics anchor missing')
if 'persistFailureDiagnostics(Path dngPath' not in r:
    insert_at = r.index('    private static SourceModel buildSourceModel(')
    helper = r'''    public static void persistFailureDiagnostics(Path dngPath, Throwable error,
                                                 ImageFrame frame,
                                                 CameraCharacteristics characteristics) {
        try {
            JSONObject d = new JSONObject();
            d.put("schema", SCHEMA);
            d.put("status", "renderer_failed_before_result");
            d.put("errorClass", error != null ? error.getClass().getName() : "unknown");
            d.put("error", error != null ? String.valueOf(error.getMessage()) : "unknown");
            d.put("openCvAndroidAar", "org.opencv:opencv:4.13.0");
            d.put("captureMode", "single_frame_raw");
            d.put("hdrEnabled", false);
            d.put("stackingEnabled", false);
            if (frame != null) {
                d.put("width", frame.width);
                d.put("height", frame.height);
                d.put("rawBufferCapacity", frame.buffer != null ? frame.buffer.capacity() : -1);
            }
            if (characteristics != null) {
                Integer cfa = characteristics.get(CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT);
                d.put("cfaPatternCode", cfa != null ? cfa : -1);
                if (cfa != null && cfa >= 0 && cfa <= 3) d.put("cfaPatternName", cfaName(cfa));
            }
            persistDiagnostics(dngPath, d);
        } catch (Throwable ignored) {}
    }

'''
    r = r[:insert_at] + helper + r[insert_at:]
renderer.write_text(r)

# 3) Lower peak memory and match the proven M9 ownership order: render/publish the
# JPEG first, then write the DNG from the same untouched RAW frame.  DNG save is
# still unconditional even when rendering fails.  CAPTURE1B previously created a
# full uncompressed DNG before allocating the full-resolution OpenCV/Bitmap render.
saver = root / 'app/src/main/java/com/particlesdevs/photoncamera/processing/DefaultSaver.java'
d = saver.read_text()
old_block = '''            try {\n                // DNG publication is unconditional for CAPTURE1B; Photon HDR/PostPipeline remains bypassed.\n                dngSaved = ImageSaver.Util.saveSingleRaw(\n                        capture1Dng, capture1Frame, characteristics, captureResult, cameraRotation);\n                processingEventsListener.notifyImageSavedStatus(dngSaved, capture1Dng);\n                try {\n                    capture1b = M10RNativeRenderer.render(\n                            capture1Frame, characteristics, captureResult, captureRequest, cameraRotation);\n                    capture1b.diagnostics.put("dngSaved", dngSaved);\n                    capture1b.diagnostics.put("dngPath", capture1Dng.toString());\n                    capture1b.diagnostics.put("jpegPath", capture1Jpeg.toString());\n                    jpegSaved = ImageSaver.Util.saveBitmapAsJPG(\n                            capture1Jpeg, capture1b.bitmap, 95,\n                            ParseExif.parse(captureResult, captureRequest));\n                    capture1b.diagnostics.put("jpegSaved", jpegSaved);\n                    processingEventsListener.notifyImageSavedStatus(jpegSaved, capture1Jpeg);\n                } catch (Throwable renderError) {\n                    Log.e(TAG, "M10-R CAPTURE1B renderer failed; DNG preserved", renderError);\n                    if (capture1b != null) {\n                        try { capture1b.diagnostics.put("rendererError", renderError.toString()); } catch (Throwable ignored) {}\n                    }\n                } finally {\n                    if (capture1b != null) {\n                        M10RNativeRenderer.persistDiagnostics(capture1Dng, capture1b.diagnostics);\n                    }\n                }\n                processingEventsListener.onProcessingFinished(\n'''
new_block = '''            try {\n                // DEVICE1: render first to avoid overlapping DNG-creation memory with the\n                // full-resolution OpenCV/Bitmap render. The RAW bytes are read-only here.\n                try {\n                    capture1b = M10RNativeRenderer.render(\n                            capture1Frame, characteristics, captureResult, captureRequest, cameraRotation);\n                    capture1b.diagnostics.put("dngPath", capture1Dng.toString());\n                    capture1b.diagnostics.put("jpegPath", capture1Jpeg.toString());\n                    capture1b.diagnostics.put("device1RenderBeforeDng", true);\n                    jpegSaved = ImageSaver.Util.saveBitmapAsJPG(\n                            capture1Jpeg, capture1b.bitmap, 95,\n                            ParseExif.parse(captureResult, captureRequest));\n                    capture1b.diagnostics.put("jpegSaved", jpegSaved);\n                    processingEventsListener.notifyImageSavedStatus(jpegSaved, capture1Jpeg);\n                } catch (Throwable renderError) {\n                    Log.e(TAG, "M10-R CAPTURE1B DEVICE1 renderer failed; DNG will still be saved", renderError);\n                    if (capture1b != null) {\n                        try { capture1b.diagnostics.put("rendererError", renderError.toString()); } catch (Throwable ignored) {}\n                    } else {\n                        M10RNativeRenderer.persistFailureDiagnostics(\n                                capture1Dng, renderError, capture1Frame, characteristics);\n                    }\n                }\n\n                // DNG remains unconditional and uses the same untouched single RAW frame.\n                dngSaved = ImageSaver.Util.saveSingleRaw(\n                        capture1Dng, capture1Frame, characteristics, captureResult, cameraRotation);\n                processingEventsListener.notifyImageSavedStatus(dngSaved, capture1Dng);\n                if (capture1b != null) {\n                    capture1b.diagnostics.put("dngSaved", dngSaved);\n                    M10RNativeRenderer.persistDiagnostics(capture1Dng, capture1b.diagnostics);\n                }\n                processingEventsListener.onProcessingFinished(\n'''
if new_block not in d:
    if d.count(old_block) != 1:
        raise SystemExit('CAPTURE1B DEVICE1 saver order anchor missing/non-unique')
    d = d.replace(old_block, new_block, 1)
saver.write_text(d)

# Hard invariants.
checks = {
    dng: ['parameters.sensorPix.left', 'parameters.sensorPix.top',
          'parameters.sensorPix.right', 'parameters.sensorPix.bottom', 'DNGGAINMAPFIX1A'],
    gradle: ["implementation 'org.opencv:opencv:4.13.0'"],
    renderer: ['org.opencv:opencv:4.13.0', 'persistFailureDiagnostics(Path dngPath'],
    saver: ['device1RenderBeforeDng', 'persistFailureDiagnostics(',
            'DNG remains unconditional and uses the same untouched single RAW frame']
}
for path, needles in checks.items():
    text = path.read_text()
    for needle in needles:
        if needle not in text:
            raise SystemExit('CAPTURE1B DEVICE1 verify failed: %s missing from %s' % (needle, path))

print('M10-R CAPTURE1B DEVICE1 applied')
print(' - M9-validated DNG GainMap x/y geometry fix ported')
print(' - OpenCV Android updated to M9-proven 4.13.0')
print(' - JPEG render moved before DNG creation to lower peak memory')
print(' - DNG remains unconditional from the same single RAW frame')
print(' - render-failure sidecar now survives pre-Result exceptions')
print(' - no HDR, stacking, Photon PostPipeline, or Cobalt runtime dependency enabled')
