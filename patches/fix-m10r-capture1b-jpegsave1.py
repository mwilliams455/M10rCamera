#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix-m10r-capture1b-jpegsave1.py <PhotonCamera-root>')

root = Path(sys.argv[1]).resolve()
if not (root / 'app').is_dir():
    raise SystemExit('CAPTURE1B JPEGSAVE1: not a PhotonCamera root')

# The supplied device log does not contain the failing M10-R shutter transaction
# itself. It ends after camera-session setup. The user-visible "image save error"
# nevertheless tells us the CAPTURE1B path reached JPEG publication and that
# publication reported false. Photon ImagePath.newImageFilePath() deliberately
# returns an extensionless path in DCIM/Camera. For CAPTURE1B we instead publish
# the JPEG beside the already proven-writable DNG, with an explicit .jpg suffix
# and identical capture stem. JPEG byte persistence is authoritative; EXIF is
# best effort and cannot turn an already-written photograph into a save failure.

gradle = root / 'app/build.gradle'
g = gradle.read_text()
if "versionName '0.97-m10rcapture1b'" in g:
    g = g.replace("versionName '0.97-m10rcapture1b'",
                  "versionName '0.97-m10rcapture1b-jpegsave1'", 1)
elif "versionName '0.97-m10rcapture1b-jpegsave1'" not in g:
    raise SystemExit('CAPTURE1B JPEGSAVE1 version anchor missing')
gradle.write_text(g)

saver = root / 'app/src/main/java/com/particlesdevs/photoncamera/processing/DefaultSaver.java'
s = saver.read_text()
old = '''            Path capture1Dng = ImagePath.newDNGFilePath();\n            Path capture1Jpeg = ImagePath.newImageFilePath();\n            ImageFrame capture1Frame = IMAGE_BUFFER.get(0);'''
new = '''            Path capture1Dng = ImagePath.newDNGFilePath();\n            String capture1DngName = capture1Dng.getFileName().toString();\n            String capture1Stem = capture1DngName.toLowerCase(java.util.Locale.US).endsWith(".dng")\n                    ? capture1DngName.substring(0, capture1DngName.length() - 4)\n                    : capture1DngName;\n            // JPEGSAVE1: same proven-writable directory + same stem + explicit MIME suffix.\n            Path capture1Jpeg = capture1Dng.resolveSibling(capture1Stem + ".jpg");\n            ImageFrame capture1Frame = IMAGE_BUFFER.get(0);'''
if new not in s:
    if s.count(old) != 1:
        raise SystemExit('CAPTURE1B JPEGSAVE1 path anchor missing/non-unique')
    s = s.replace(old, new, 1)

old_call = '''                    jpegSaved = ImageSaver.Util.saveBitmapAsJPG(\n                            capture1Jpeg, capture1b.bitmap, 95,\n                            ParseExif.parse(captureResult, captureRequest));'''
new_call = '''                    Log.d(TAG, "M10-R CAPTURE1B JPEGSAVE1 publishing JPEG: " + capture1Jpeg);\n                    jpegSaved = ImageSaver.Util.saveBitmapAsJPGM10R(\n                            capture1Jpeg, capture1b.bitmap, 95,\n                            ParseExif.parse(captureResult, captureRequest));'''
if new_call not in s:
    if s.count(old_call) != 1:
        raise SystemExit('CAPTURE1B JPEGSAVE1 save call anchor missing/non-unique')
    s = s.replace(old_call, new_call, 1)

needle = '                    capture1b.diagnostics.put("device1RenderBeforeDng", true);\n'
insert = needle + '''                    capture1b.diagnostics.put("jpegSavePolicy", "m10r_jpegsave1_same_dng_dir_explicit_jpg_best_effort_exif");\n                    capture1b.diagnostics.put("jpegParent", String.valueOf(capture1Jpeg.getParent()));\n'''
if insert not in s:
    if s.count(needle) != 1:
        raise SystemExit('CAPTURE1B JPEGSAVE1 diagnostic anchor missing/non-unique')
    s = s.replace(needle, insert, 1)
saver.write_text(s)

image_saver = root / 'app/src/main/java/com/particlesdevs/photoncamera/processing/ImageSaver.java'
i = image_saver.read_text()
anchor = '''        public static boolean saveBitmapAsJPG(Path fileToSave, Bitmap img, int jpgQuality, ParseExif.ExifData exifData) {\n            exifData.COMPRESSION = String.valueOf(jpgQuality);\n            try {\n                OutputStream outputStream = Files.newOutputStream(fileToSave);\n                img.compress(Bitmap.CompressFormat.JPEG, jpgQuality, outputStream);\n                outputStream.flush();\n                outputStream.close();\n                img.recycle();\n                ExifInterface inter = ParseExif.setAllAttributes(fileToSave.toFile(), exifData);\n                inter.saveAttributes();\n                return true;\n            } catch (IOException e) {\n                e.printStackTrace();\n                return false;\n            }\n        }\n'''
if anchor not in i:
    raise SystemExit('CAPTURE1B JPEGSAVE1 ImageSaver anchor missing')
if 'saveBitmapAsJPGM10R(' not in i:
    helper = anchor + '''\n        /**\n         * CAPTURE1B JPEGSAVE1 publication primitive. JPEG byte persistence is the\n         * success criterion; EXIF finalisation is best effort and cannot turn a\n         * valid JPEG into a user-visible save failure.\n         */\n        public static boolean saveBitmapAsJPGM10R(Path fileToSave, Bitmap img, int jpgQuality, ParseExif.ExifData exifData) {\n            if (fileToSave == null || img == null) {\n                Log.e(TAG, "M10-R JPEGSAVE1 invalid JPEG arguments");\n                return false;\n            }\n            boolean bytesSaved = false;\n            try {\n                Path parent = fileToSave.getParent();\n                if (parent != null) Files.createDirectories(parent);\n                try (OutputStream outputStream = Files.newOutputStream(fileToSave)) {\n                    bytesSaved = img.compress(Bitmap.CompressFormat.JPEG, jpgQuality, outputStream);\n                    outputStream.flush();\n                }\n                if (!bytesSaved || !Files.exists(fileToSave) || Files.size(fileToSave) <= 0L) {\n                    Log.e(TAG, "M10-R JPEGSAVE1 JPEG encoder/write produced no bytes: " + fileToSave);\n                    return false;\n                }\n                if (exifData != null) {\n                    try {\n                        exifData.COMPRESSION = String.valueOf(jpgQuality);\n                        ExifInterface inter = ParseExif.setAllAttributes(fileToSave.toFile(), exifData);\n                        inter.saveAttributes();\n                    } catch (Exception exifError) {\n                        Log.e(TAG, "M10-R JPEGSAVE1 EXIF finalisation failed but JPEG bytes are preserved: "\n                                + Log.getStackTraceString(exifError));\n                    }\n                }\n                Log.d(TAG, "M10-R JPEGSAVE1 JPEG saved bytes=" + Files.size(fileToSave)\n                        + " path=" + fileToSave);\n                return true;\n            } catch (Exception saveError) {\n                Log.e(TAG, "M10-R JPEGSAVE1 JPEG byte save failed path=" + fileToSave + " "\n                        + Log.getStackTraceString(saveError));\n                return false;\n            } finally {\n                try {\n                    if (!img.isRecycled()) img.recycle();\n                } catch (Throwable ignored) {}\n            }\n        }\n'''
    i = i.replace(anchor, helper, 1)
image_saver.write_text(i)

# Hard verification.
g = gradle.read_text()
s = saver.read_text()
i = image_saver.read_text()
if "versionName '0.97-m10rcapture1b-jpegsave1'" not in g:
    raise SystemExit('CAPTURE1B JPEGSAVE1 build identity missing')
for needle in [
    'capture1Dng.resolveSibling(capture1Stem + ".jpg")',
    'saveBitmapAsJPGM10R(',
    'm10r_jpegsave1_same_dng_dir_explicit_jpg_best_effort_exif',
    'M10-R CAPTURE1B JPEGSAVE1 publishing JPEG:'
]:
    if needle not in s:
        raise SystemExit('CAPTURE1B JPEGSAVE1 verify DefaultSaver missing: ' + needle)
for needle in [
    'public static boolean saveBitmapAsJPGM10R(',
    'Files.createDirectories(parent)',
    'JPEG byte persistence is the',
    'EXIF finalisation failed but JPEG bytes are preserved',
    'JPEG encoder/write produced no bytes',
    'M10-R JPEGSAVE1 JPEG saved bytes=',
    'catch (Exception exifError)',
    'catch (Exception saveError)'
]:
    if needle not in i:
        raise SystemExit('CAPTURE1B JPEGSAVE1 verify ImageSaver missing: ' + needle)

print('M10-R CAPTURE1B JPEGSAVE1 applied')
print(' - build identity: 0.97-m10rcapture1b-jpegsave1')
print(' - JPEG path now reuses proven-writable DNG directory')
print(' - JPEG gets identical capture stem and explicit .jpg extension')
print(' - JPEG byte persistence is authoritative success')
print(' - EXIF failure is logged but no longer discards a valid photograph')
print(' - Java logging exception types are compile-safe')
print(' - exact byte-save failures are now logged for the next device run')
print(' - DNGGAINMAPFIX1A and single-frame/no-HDR route remain unchanged')
