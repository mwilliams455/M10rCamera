#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix-m10r-capture1b-opencv1.py <PhotonCamera-root>')

root = Path(sys.argv[1]).resolve()
if not (root / 'app').is_dir():
    raise SystemExit('CAPTURE1B OPENCV1: not a PhotonCamera root')

gradle = root / 'app/build.gradle'
renderer = root / 'app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'
if not gradle.exists() or not renderer.exists():
    raise SystemExit('CAPTURE1B OPENCV1 requires generated CAPTURE1B renderer and app/build.gradle')

g = gradle.read_text()
dep = "    implementation 'org.opencv:opencv:4.10.0'\n"
if "org.opencv:opencv:" not in g:
    anchor = "    implementation fileTree(dir: 'libs', include: ['*.jar'])\n"
    if g.count(anchor) != 1:
        raise SystemExit('CAPTURE1B OPENCV1 dependency anchor missing/non-unique')
    g = g.replace(anchor, anchor + dep, 1)
elif "implementation 'org.opencv:opencv:4.10.0'" not in g:
    raise SystemExit('CAPTURE1B OPENCV1 found a conflicting OpenCV dependency')
gradle.write_text(g)

s = renderer.read_text()
import_anchor = 'import org.json.JSONObject;\n'
if 'import org.opencv.android.OpenCVLoader;' not in s:
    if s.count(import_anchor) != 1:
        raise SystemExit('CAPTURE1B OPENCV1 import anchor missing/non-unique')
    s = s.replace(import_anchor,
                  import_anchor + 'import org.opencv.android.OpenCVLoader;\n', 1)

field_anchor = '    private M10RNativeRenderer() {}\n'
field_block = '''    private static volatile boolean OPEN_CV_READY = false;\n\n    private static synchronized void ensureOpenCv() {\n        if (OPEN_CV_READY) return;\n        if (!OpenCVLoader.initDebug()) {\n            throw new IllegalStateException("OpenCV Android initialization failed");\n        }\n        OPEN_CV_READY = true;\n    }\n\n    private M10RNativeRenderer() {}\n'''
if 'private static synchronized void ensureOpenCv()' not in s:
    if s.count(field_anchor) != 1:
        raise SystemExit('CAPTURE1B OPENCV1 class field anchor missing/non-unique')
    s = s.replace(field_anchor, field_block, 1)

render_anchor = '''        BayerFrame normalized = normalizeBayer(\n                frame.buffer, frame.width, frame.height, cfa, black, white, map, d);\n\n        Mat rawMat = null;\n'''
render_block = '''        BayerFrame normalized = normalizeBayer(\n                frame.buffer, frame.width, frame.height, cfa, black, white, map, d);\n\n        // Official OpenCV Android AAR from Maven Central supplies the Java API and\n        // arm64-v8a/armeabi-v7a native runtime used only for deterministic EA demosaic.\n        ensureOpenCv();\n        d.put("openCvAndroidAar", "org.opencv:opencv:4.10.0");\n        d.put("openCvPurpose", "single_frame_Bayer_EA_demosaic_only");\n\n        Mat rawMat = null;\n'''
if 'd.put("openCvAndroidAar"' not in s:
    if s.count(render_anchor) != 1:
        raise SystemExit('CAPTURE1B OPENCV1 render anchor missing/non-unique')
    s = s.replace(render_anchor, render_block, 1)

for required in [
    "implementation 'org.opencv:opencv:4.10.0'",
    'import org.opencv.android.OpenCVLoader;',
    'private static synchronized void ensureOpenCv()',
    'OpenCVLoader.initDebug()',
    'openCvPurpose", "single_frame_Bayer_EA_demosaic_only',
]:
    target = g if required.startswith('implementation') else s
    if required not in target:
        raise SystemExit('CAPTURE1B OPENCV1 verify failed: ' + required)

renderer.write_text(s)
print('M10-R CAPTURE1B OPENCV1 applied')
print(' - official OpenCV Android 4.10.0 AAR added from Maven Central')
print(' - Java org.opencv API now present at compile time')
print(' - packaged native OpenCV runtime initialized before EA demosaic')
print(' - OpenCV is used for single-frame Bayer demosaic only; no HDR/PostPipeline enabled')
