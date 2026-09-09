#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix-m10r-render1f-diag1b.py <PhotonCamera-root>')
root = Path(sys.argv[1]).resolve()
if not (root/'app').is_dir():
    raise SystemExit('RENDER1F DIAG1B: not a PhotonCamera root')

def rd(rel):
    p=root/rel
    if not p.exists(): raise SystemExit('RENDER1F DIAG1B missing: '+rel)
    return p.read_text()
def wr(rel,s): (root/rel).write_text(s)
def one(s,a,b,label):
    n=s.count(a)
    if n!=1: raise SystemExit('RENDER1F DIAG1B anchor %s count=%d'%(label,n))
    return s.replace(a,b,1)

# Diagnostics-only follow-up. DIAG1A anchored the writer on capture1Jpeg, but
# JPEGSAVE1 deliberately places that JPEG beside the DNG in PhotonCamera/Raw.
# Therefore DIAG1A never actually moved the JSON to DCIM/Camera as intended.
# DIAG1B supplies an explicit DCIM/Camera anchor and logs the writer result.
# If the sidecar still cannot be written, the complete JSON payload is emitted
# into the Photon log so the photographic diagnostic cannot be lost silently.

grad='app/build.gradle'; g=rd(grad)
g=one(g,
      "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1f-yc2a-matrix1a-diag1a'",
      "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1f-yc2a-matrix1a-diag1b'",
      'version')
wr(grad,g)

default='app/src/main/java/com/particlesdevs/photoncamera/processing/DefaultSaver.java'; d=rd(default)
old='''                    if (capture1b != null) {\n                        M10RNativeRenderer.persistDiagnostics(capture1Jpeg, capture1b.diagnostics);\n                    }'''
new='''                    if (capture1b != null) {\n                        // DIAG1B: JPEGSAVE1 puts capture1Jpeg in PhotonCamera/Raw, so\n                        // construct the intended public DCIM/Camera anchor explicitly.\n                        Path diagAnchor = java.nio.file.Paths.get(\n                                com.particlesdevs.photoncamera.util.FileManager.sDCIM_CAMERA.getAbsolutePath(),\n                                capture1Stem + ".jpg");\n                        capture1b.diagnostics.put("diagnosticsIntent",\n                                "DIAG1B_DCIM_CAMERA_EXPLICIT_WITH_LOG_FALLBACK");\n                        boolean diagSaved = M10RNativeRenderer.persistDiagnostics(\n                                diagAnchor, capture1b.diagnostics);\n                        Log.d(TAG, "M10-R DIAG1B JSON saved=" + diagSaved\n                                + " anchor=" + diagAnchor);\n                        if (!diagSaved) {\n                            Log.e(TAG, "M10-R DIAG1B JSON WRITE FAILED; payload="\n                                    + capture1b.diagnostics.toString());\n                        }\n                    }'''
d=one(d,old,new,'explicit-dcim-anchor')
wr(default,d)

# Update the renderer's writer identity only; persistence arithmetic is unchanged.
renderer='app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'; r=rd(renderer)
r=one(r,
      'diagnostics.put("diagnosticsWriter", "DIAG1A_JPEG_SIBLING");',
      'diagnostics.put("diagnosticsWriter", "DIAG1B_DCIM_CAMERA_EXPLICIT");',
      'writer-id')
wr(renderer,r)

R=rd(renderer); D=rd(default); G=rd(grad)
for x in [
    'DIAG1B_DCIM_CAMERA_EXPLICIT',
    'Files.createDirectories(parent);',
    'Files.exists(sidecar) && Files.size(sidecar) > 0L',
    'RENDER1F_YC2A_MATRIX1A',
    'edgeScaleTableApplied", true',
    'edgeHfRecordGainApplied", true',
    'hdrEnabled", false',
    'sourceFrameCount", 1',
]:
    if x not in R: raise SystemExit('RENDER1F DIAG1B renderer invariant missing: '+x)
for x in [
    'FileManager.sDCIM_CAMERA.getAbsolutePath()',
    'DIAG1B_DCIM_CAMERA_EXPLICIT_WITH_LOG_FALLBACK',
    'M10-R DIAG1B JSON saved=',
    'M10-R DIAG1B JSON WRITE FAILED; payload=',
    'persistDiagnostics(diagAnchor, capture1b.diagnostics)',
]:
    if x not in D: raise SystemExit('RENDER1F DIAG1B saver invariant missing: '+x)
if 'persistDiagnostics(capture1Jpeg, capture1b.diagnostics)' in D:
    raise SystemExit('RENDER1F DIAG1B old JPEGSAVE1/raw anchor remains')
if '-diag1b' not in G:
    raise SystemExit('RENDER1F DIAG1B version marker missing')

print('M10-R RENDER1F DIAG1B applied')
print(' - fixes DIAG1A path assumption: JPEGSAVE1 JPEG is in PhotonCamera/Raw')
print(' - JSON now explicitly targets DCIM/Camera using the same capture stem')
print(' - sidecar success/failure is logged')
print(' - on write failure, complete diagnostic JSON is emitted to Photon log')
print(' - rendering, colour, tone, edge, exposure, JPEG quality, 12MP and HDR-off are unchanged')
