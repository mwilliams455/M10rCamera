#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix-m10r-render1a-stability1.py <PhotonCamera-root>')
root = Path(sys.argv[1]).resolve()
if not (root / 'app').is_dir():
    raise SystemExit('RENDER1A STABILITY1: not a PhotonCamera root')

def rd(rel):
    p = root / rel
    if not p.exists():
        raise SystemExit('RENDER1A STABILITY1 missing: ' + rel)
    return p.read_text()

def wr(rel, s):
    (root / rel).write_text(s)

def one(s, a, b, label):
    if s.count(a) != 1:
        raise SystemExit('RENDER1A STABILITY1 anchor %s missing/ambiguous count=%d' % (label, s.count(a)))
    return s.replace(a, b, 1)

# Build identity: this changes memory/ownership only, not the photographic policy.
grad = 'app/build.gradle'
g = rd(grad)
g = one(g,
        "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b'",
        "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability1'",
        'version')
wr(grad, g)

renderer = 'app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'
r = rd(renderer)

# RENDER1A originally held a full-frame 16UC3 OpenCV demosaic (~75 MiB), a
# normalized RAW array (~24 MiB), and an ARGB bitmap (~48 MiB) simultaneously.
# A 90/270 rotation then transiently created another full ARGB bitmap. On the
# Xiaomi 15 Ultra this can terminate the process in native/process memory without
# a Java exception reaching Photon's file logger. Keep the exact same OpenCV EA
# demosaic, but execute it in CFA-phase-preserving horizontal strips with a halo,
# and write directly into the final oriented bitmap.
old_setup = '''        Mat rawMat = null;\n        Mat bgr16 = null;\n        Bitmap bitmap = null;\n        try {\n            rawMat = new Mat(frame.height, frame.width, CvType.CV_16UC1);\n            rawMat.put(0, 0, normalized.data);\n            bgr16 = new Mat();\n            Imgproc.cvtColor(rawMat, bgr16, demosaicCode(cfa));\n            rawMat.release();\n            rawMat = null;\n\n            bitmap = Bitmap.createBitmap(frame.width, frame.height, Bitmap.Config.ARGB_8888);\n            final int blockRows = 64;\n'''
new_setup = '''        Mat tileRaw = null;\n        Mat tileBgr = null;\n        Bitmap bitmap = null;\n        try {\n            final int rotation = ((cameraRotation % 360) + 360) % 360;\n            final boolean quarterTurn = rotation == 90 || rotation == 270;\n            final int outputWidth = quarterTurn ? frame.height : frame.width;\n            final int outputHeight = quarterTurn ? frame.width : frame.height;\n            bitmap = Bitmap.createBitmap(outputWidth, outputHeight, Bitmap.Config.ARGB_8888);\n            final int blockRows = 128;\n            final int demosaicHaloRows = 4;\n'''
r = one(r, old_setup, new_setup, 'full-frame-demosaic-setup')

old_buffers = '''            short[] bgr = new short[Math.multiplyExact(frame.width * blockRows, 3)];\n            int[] argb = new int[frame.width * blockRows];\n'''
new_buffers = '''            short[] bgr = new short[Math.multiplyExact(frame.width * blockRows, 3)];\n            int[] argb = new int[frame.width * blockRows];\n            int[] oriented = new int[frame.width * blockRows];\n            short[] rawTileData = new short[Math.multiplyExact(frame.width, blockRows + 2*demosaicHaloRows + 2)];\n'''
r = one(r, old_buffers, new_buffers, 'strip-buffers')

old_loop = '''            for (int y0 = 0; y0 < frame.height; y0 += blockRows) {\n                int rows = Math.min(blockRows, frame.height - y0);\n                int shortCount = frame.width * rows * 3;\n                if (bgr.length < shortCount) bgr = new short[shortCount];\n                bgr16.get(y0, 0, bgr);\n                int pixels = frame.width * rows;\n'''
new_loop = '''            for (int y0 = 0; y0 < frame.height; y0 += blockRows) {\n                int rows = Math.min(blockRows, frame.height - y0);\n                int shortCount = frame.width * rows * 3;\n                if (bgr.length < shortCount) bgr = new short[shortCount];\n\n                // Keep tile row 0 on the same Bayer phase as full-frame row 0.\n                int srcY0 = Math.max(0, y0 - demosaicHaloRows);\n                if ((srcY0 & 1) != 0) srcY0--;\n                int srcY1 = Math.min(frame.height, y0 + rows + demosaicHaloRows);\n                if ((srcY1 & 1) != 0 && srcY1 < frame.height) srcY1++;\n                int tileRows = srcY1 - srcY0;\n                int tileSamples = Math.multiplyExact(frame.width, tileRows);\n                System.arraycopy(normalized.data, srcY0 * frame.width, rawTileData, 0, tileSamples);\n\n                tileRaw = new Mat(tileRows, frame.width, CvType.CV_16UC1);\n                tileRaw.put(0, 0, rawTileData);\n                tileBgr = new Mat();\n                Imgproc.cvtColor(tileRaw, tileBgr, demosaicCode(cfa));\n                tileRaw.release();\n                tileRaw = null;\n\n                int centralRow = y0 - srcY0;\n                tileBgr.get(centralRow, 0, bgr);\n                int pixels = frame.width * rows;\n'''
r = one(r, old_loop, new_loop, 'strip-loop')

old_store = '''                bitmap.setPixels(argb, 0, frame.width, 0, y0, frame.width, rows);\n            }\n'''
new_store = '''                tileBgr.release();\n                tileBgr = null;\n\n                // Write directly into final orientation: no second full-size bitmap.\n                if (rotation == 0) {\n                    bitmap.setPixels(argb, 0, frame.width, 0, y0, frame.width, rows);\n                } else if (rotation == 180) {\n                    for (int sy=0; sy<rows; sy++) {\n                        int dstRow = rows - 1 - sy;\n                        int so = sy * frame.width;\n                        int dst = dstRow * frame.width;\n                        for (int x=0; x<frame.width; x++) oriented[dst + (frame.width - 1 - x)] = argb[so + x];\n                    }\n                    bitmap.setPixels(oriented, 0, frame.width, 0, frame.height - y0 - rows, frame.width, rows);\n                } else if (rotation == 90) {\n                    int stripeX = frame.height - y0 - rows;\n                    for (int sy=0; sy<rows; sy++) {\n                        int localX = rows - 1 - sy;\n                        int so = sy * frame.width;\n                        for (int x=0; x<frame.width; x++) oriented[x * rows + localX] = argb[so + x];\n                    }\n                    bitmap.setPixels(oriented, 0, rows, stripeX, 0, rows, frame.width);\n                } else if (rotation == 270) {\n                    int stripeX = y0;\n                    for (int sy=0; sy<rows; sy++) {\n                        int so = sy * frame.width;\n                        for (int x=0; x<frame.width; x++) oriented[(frame.width - 1 - x) * rows + sy] = argb[so + x];\n                    }\n                    bitmap.setPixels(oriented, 0, rows, stripeX, 0, rows, frame.width);\n                } else {\n                    throw new IllegalStateException("unsupported camera rotation: " + rotation);\n                }\n            }\n'''
r = one(r, old_store, new_store, 'direct-oriented-store')

old_finish = '''            bgr16.release();\n            bgr16 = null;\n\n            int rotation = ((cameraRotation % 360) + 360) % 360;\n            if (rotation != 0) {\n                Matrix m = new Matrix();\n                m.postRotate(rotation);\n                Bitmap rotated = Bitmap.createBitmap(bitmap, 0, 0,\n                        bitmap.getWidth(), bitmap.getHeight(), m, true);\n                if (rotated != bitmap) bitmap.recycle();\n                bitmap = rotated;\n            }\n            d.put("cameraRotationDegrees", rotation);\n'''
new_finish = '''            d.put("renderStabilityFix", "STABILITY1_TILED_EA_DEMOSAIC_DIRECT_ORIENTATION");\n            d.put("demosaicTileRows", blockRows);\n            d.put("demosaicHaloRows", demosaicHaloRows);\n            d.put("fullFrameBgrMatAllocated", false);\n            d.put("secondRotationBitmapAllocated", false);\n            d.put("cameraRotationDegrees", rotation);\n'''
r = one(r, old_finish, new_finish, 'remove-full-bgr-and-rotation-copy')

old_finally = '''        } finally {\n            if (rawMat != null) rawMat.release();\n            if (bgr16 != null) bgr16.release();\n        }\n'''
new_finally = '''        } finally {\n            if (tileRaw != null) tileRaw.release();\n            if (tileBgr != null) tileBgr.release();\n        }\n'''
r = one(r, old_finally, new_finally, 'tile-finally')

# Persistent breadcrumb survives a native/process death and tells us which stage
# was last reached even when Photon's logger does not flush.
anchor = '''    public static void persistDiagnostics(Path dngPath, JSONObject diagnostics) {\n'''
helper = '''    public static void persistBreadcrumb(Path dngPath, String stage) {\n        if (dngPath == null || stage == null) return;\n        try {\n            String name = dngPath.getFileName().toString();\n            int dot = name.lastIndexOf('.');\n            String stem = dot > 0 ? name.substring(0, dot) : name;\n            Path sidecar = dngPath.resolveSibling(stem + "_M10R_STABILITY1.txt");\n            String line = System.currentTimeMillis() + " " + stage + "\\n";\n            Files.write(sidecar, line.getBytes(StandardCharsets.UTF_8),\n                    java.nio.file.StandardOpenOption.CREATE,\n                    java.nio.file.StandardOpenOption.APPEND);\n        } catch (Throwable ignored) {}\n    }\n\n''' + anchor
r = one(r, anchor, helper, 'breadcrumb-helper')
wr(renderer, r)

saver = 'app/src/main/java/com/particlesdevs/photoncamera/processing/DefaultSaver.java'
s = rd(saver)
render_call = '''                    capture1b = M10RNativeRenderer.render(\n                            capture1Frame, characteristics, captureResult, captureRequest, cameraRotation);\n'''
render_call_new = '''                    M10RNativeRenderer.persistBreadcrumb(capture1Dng, "before_render");\n                    capture1b = M10RNativeRenderer.render(\n                            capture1Frame, characteristics, captureResult, captureRequest, cameraRotation);\n                    M10RNativeRenderer.persistBreadcrumb(capture1Dng, "after_render");\n'''
s = one(s, render_call, render_call_new, 'saver-render-breadcrumb')

jpeg_anchor = '''                    capture1b.diagnostics.put("jpegSaved", jpegSaved);\n                    processingEventsListener.notifyImageSavedStatus(jpegSaved, capture1Jpeg);\n'''
jpeg_new = '''                    capture1b.diagnostics.put("jpegSaved", jpegSaved);\n                    M10RNativeRenderer.persistBreadcrumb(capture1Dng, jpegSaved ? "after_jpeg_saved" : "after_jpeg_failed");\n                    processingEventsListener.notifyImageSavedStatus(jpegSaved, capture1Jpeg);\n'''
s = one(s, jpeg_anchor, jpeg_new, 'saver-jpeg-breadcrumb')

dng_call = '''                dngSaved = ImageSaver.Util.saveSingleRaw(\n                        capture1Dng, capture1Frame, characteristics, captureResult, cameraRotation);\n                processingEventsListener.notifyImageSavedStatus(dngSaved, capture1Dng);\n'''
dng_new = '''                M10RNativeRenderer.persistBreadcrumb(capture1Dng, "before_dng_save");\n                dngSaved = ImageSaver.Util.saveSingleRaw(\n                        capture1Dng, capture1Frame, characteristics, captureResult, cameraRotation);\n                M10RNativeRenderer.persistBreadcrumb(capture1Dng, dngSaved ? "after_dng_saved" : "after_dng_failed");\n                processingEventsListener.notifyImageSavedStatus(dngSaved, capture1Dng);\n'''
s = one(s, dng_call, dng_new, 'saver-dng-breadcrumb')

finally_anchor = '''            } finally {\n                capture1Frame.close();\n                IMAGE_BUFFER.clear();\n                bufferLock = false;\n            }\n'''
finally_new = '''            } finally {\n                M10RNativeRenderer.persistBreadcrumb(capture1Dng, "capture_finally_release");\n                capture1Frame.close();\n                IMAGE_BUFFER.clear();\n                bufferLock = false;\n            }\n'''
s = one(s, finally_anchor, finally_new, 'saver-finally-breadcrumb')
wr(saver, s)

# Hard invariants: photographic route is frozen; only memory topology changes.
R = rd(renderer)
S = rd(saver)
for marker in [
    'nonlinearRenderer", "TONEDG1B"',
    'nonlinearOrder", "MEDIUM_THEN_DIFFERENTIAL_GAMMA"',
    'nonlinearApplicationMode", "luma_gain_preserve_linear_rgb_ratios"',
    'hdrEnabled", false',
    'sourceFrameCount", 1',
    'STABILITY1_TILED_EA_DEMOSAIC_DIRECT_ORIENTATION',
    'fullFrameBgrMatAllocated", false',
    'secondRotationBitmapAllocated", false',
    'persistBreadcrumb(Path dngPath, String stage)',
]:
    if marker not in R:
        raise SystemExit('RENDER1A STABILITY1 renderer invariant missing: ' + marker)
for forbidden in [
    'new Mat(frame.height, frame.width, CvType.CV_16UC1)',
    'Bitmap rotated = Bitmap.createBitmap(bitmap',
    'bgr16 = new Mat()',
]:
    if forbidden in R:
        raise SystemExit('RENDER1A STABILITY1 peak-memory regression still present: ' + forbidden)
for marker in ['before_render', 'after_render', 'after_jpeg_saved', 'before_dng_save', 'capture_finally_release']:
    if marker not in S:
        raise SystemExit('RENDER1A STABILITY1 saver breadcrumb missing: ' + marker)

print('M10-R RENDER1A STABILITY1 applied')
print(' - full-frame 16UC3 BGR Mat removed')
print(' - OpenCV EA demosaic retained in CFA-phase-preserving 128-row strips with 4-row halo')
print(' - final orientation written directly; second full bitmap removed')
print(' - persistent per-capture breadcrumbs added for native/process-death diagnosis')
print(' - tone, colour, exposure, single-frame and no-HDR policies unchanged')
