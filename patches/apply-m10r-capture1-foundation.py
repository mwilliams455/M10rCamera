#!/usr/bin/env python3
from pathlib import Path
import re, sys

if len(sys.argv) != 2:
    raise SystemExit("usage: apply-m10r-capture1-foundation.py <PhotonCamera-root>")

root = Path(sys.argv[1]).resolve()
if not (root / "app").is_dir():
    raise SystemExit(f"not a PhotonCamera root: {root}")

def read(rel):
    p = root / rel
    if not p.exists():
        raise SystemExit(f"CAPTURE1 missing upstream file: {rel}")
    return p.read_text()

def write(rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)

# CAPTURE1 deliberately reuses the exact Photon baseline already proven by the
# current M9 project.  This first milestone changes capture plumbing only:
# one physical RAW frame, untouched DNG, no HDR merge and no Photon PostPipeline.
# M10-R rendering is integrated in the next seam after this capture foundation
# is proven on all four Xiaomi 15 Ultra rear physical cameras.

gradle_rel = "app/build.gradle"
g = read(gradle_rel)
g = re.sub(r"applicationId\s+'com\.particlesdevs\.photoncamera'",
           "applicationId 'com.m10rproject.m10rcam.photon'", g, count=1)
g = re.sub(r"versionName\s+'0\.97(?:-[^']*)?'",
           "versionName '0.97-m10rcapture1'", g, count=1)
g = g.replace(
    'outputFileName = "PhotonCamera-${versionName}${versionBuild}-${variant.name}.apk"',
    'outputFileName = "M10RCam-Photon-${versionName}${versionBuild}-${variant.name}.apk"')
for required in [
    "applicationId 'com.m10rproject.m10rcam.photon'",
    "versionName '0.97-m10rcapture1'",
    'outputFileName = "M10RCam-Photon-${versionName}${versionBuild}-${variant.name}.apk"',
]:
    if required not in g:
        raise SystemExit(f"CAPTURE1 build identity patch failed: {required}")
write(gradle_rel, g)

for rel in [
    "app/src/main/res/values/strings.xml",
    "app/src/main/res/values-ko-rKR/strings.xml",
]:
    p = root / rel
    if not p.exists():
        continue
    s = p.read_text()
    s2 = re.sub(r'<string name="app_name" translatable="false">[^<]*</string>',
                '<string name="app_name" translatable="false">M10RCam Capture1</string>',
                s, count=1)
    if s2 == s:
        raise SystemExit(f"CAPTURE1 app_name anchor missing in {rel}")
    p.write_text(s2)

# Normal PHOTO mode is a true single-frame route.  This is the explicit guard
# against HDR/stacking: no second RAW frame is requested for CAPTURE1.
frames_rel = "app/src/main/java/com/particlesdevs/photoncamera/processing/parameters/FrameNumberSelector.java"
f = read(frames_rel)
anchor = "    public static int getFrames() {\n"
insert = (
    "    public static int getFrames() {\n"
    "        // M10R CAPTURE1: one physical exposure only; HDR/stacking is intentionally bypassed.\n"
    "        if (PhotonCamera.getSettings().selectedMode == CameraMode.PHOTO) {\n"
    "            frameCount = 1;\n"
    "            throwCount = 0;\n"
    "            return 1;\n"
    "        }\n"
)
if "M10R CAPTURE1: one physical exposure only" not in f:
    if anchor not in f:
        raise SystemExit("CAPTURE1 FrameNumberSelector anchor missing")
    f = f.replace(anchor, insert, 1)
write(frames_rel, f)

# Stop normal PHOTO processing immediately after saving the untouched RAW frame.
# This intentionally does not invoke HdrxProcessor or Photon's PostPipeline.
saver_rel = "app/src/main/java/com/particlesdevs/photoncamera/processing/DefaultSaver.java"
s = read(saver_rel)
anchor = '        Log.d(TAG,"Size:"+IMAGE_BUFFER.size());\n'
block = '''        Log.d(TAG,"Size:"+IMAGE_BUFFER.size());
        // M10R CAPTURE1: one untouched RAW DNG, then stop before Hdrx/PostPipeline.
        if (PhotonCamera.getSettings().selectedMode == com.particlesdevs.photoncamera.api.CameraMode.PHOTO) {
            Path capture1Dng = ImagePath.newDNGFilePath();
            ImageFrame capture1Frame = IMAGE_BUFFER.get(0);
            boolean capture1Saved = false;
            try {
                capture1Saved = ImageSaver.Util.saveSingleRaw(
                        capture1Dng, capture1Frame, characteristics, captureResult, cameraRotation);
                processingEventsListener.notifyImageSavedStatus(capture1Saved, capture1Dng);
                processingEventsListener.onProcessingFinished(
                        capture1Saved
                                ? "M10-R CAPTURE1: single RAW DNG saved"
                                : "M10-R CAPTURE1: RAW save failed");
            } finally {
                capture1Frame.close();
                IMAGE_BUFFER.clear();
                bufferLock = false;
            }
            return;
        }
'''
if "M10R CAPTURE1: one untouched RAW DNG" not in s:
    if anchor not in s:
        raise SystemExit("CAPTURE1 DefaultSaver anchor missing")
    s = s.replace(anchor, block, 1)
write(saver_rel, s)

# Fail the patch if any of the capture invariants disappeared.
checks = {
    gradle_rel: ["com.m10rproject.m10rcam.photon", "0.97-m10rcapture1", "M10RCam-Photon-"],
    frames_rel: ["frameCount = 1", "throwCount = 0", "return 1"],
    saver_rel: ["saveSingleRaw", "capture1Frame.close()", "return;", "M10-R CAPTURE1"],
}
for rel, needles in checks.items():
    text = read(rel)
    for needle in needles:
        if needle not in text:
            raise SystemExit(f"CAPTURE1 verify failed: {needle!r} missing from {rel}")

print("M10-R CAPTURE1 Photon foundation applied")
print(" - one normal PHOTO RAW frame")
print(" - untouched DNG save")
print(" - Hdrx/PostPipeline bypassed")
print(" - M10-R renderer not yet wired in this milestone")
