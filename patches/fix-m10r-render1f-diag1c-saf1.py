#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix-m10r-render1f-diag1c-saf1.py <PhotonCamera-root>')
root = Path(sys.argv[1]).resolve()
if not (root/'app').is_dir():
    raise SystemExit('RENDER1F DIAG1C SAF1: not a PhotonCamera root')

def rd(rel):
    p=root/rel
    if not p.exists(): raise SystemExit('RENDER1F DIAG1C SAF1 missing: '+rel)
    return p.read_text()
def wr(rel,s): (root/rel).write_text(s)
def one(s,a,b,label):
    n=s.count(a)
    if n!=1: raise SystemExit('RENDER1F DIAG1C SAF1 anchor %s count=%d'%(label,n))
    return s.replace(a,b,1)

# Diagnostics-only storage fix.
# DIAG1A used java.nio Files.write() for a .json in public DCIM storage. The
# exact Photon baseline already documents that Android 11+ FUSE/MediaProvider
# can reject non-image file types there and provides SimpleStorageHelper's SAF
# writer specifically for JSON/text/CSV. Use that existing path first.
# No image-processing arithmetic is changed.

grad='app/build.gradle'; g=rd(grad)
g=one(g,
      "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1f-yc2a-matrix1a-diag1a'",
      "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1f-yc2a-matrix1a-diag1c-saf1'",
      'version')
wr(grad,g)

renderer='app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'; r=rd(renderer)
old='''    public static boolean persistDiagnostics(Path anchorPath, JSONObject diagnostics) {\n        if (anchorPath == null || diagnostics == null) return false;\n        try {\n            Path parent = anchorPath.getParent();\n            if (parent == null) return false;\n            Files.createDirectories(parent);\n            String name = anchorPath.getFileName().toString();\n            int dot = name.lastIndexOf('.');\n            String stem = dot > 0 ? name.substring(0, dot) : name;\n            Path sidecar = parent.resolve(stem + "_M10R_CAPTURE1B.json");\n            diagnostics.put("diagnosticsWriter", "DIAG1A_JPEG_SIBLING");\n            diagnostics.put("diagnosticsSidecarPath", sidecar.toString());\n            Files.write(sidecar, diagnostics.toString(2).getBytes(StandardCharsets.UTF_8));\n            return Files.exists(sidecar) && Files.size(sidecar) > 0L;\n        } catch (Throwable ignored) {\n            return false;\n        }\n    }'''
new='''    public static boolean persistDiagnostics(Path anchorPath, JSONObject diagnostics) {\n        if (anchorPath == null || diagnostics == null) return false;\n        Path sidecar = null;\n        try {\n            Path parent = anchorPath.getParent();\n            if (parent == null) return false;\n            String name = anchorPath.getFileName().toString();\n            int dot = name.lastIndexOf('.');\n            String stem = dot > 0 ? name.substring(0, dot) : name;\n            sidecar = parent.resolve(stem + "_M10R_CAPTURE1B.json");\n            diagnostics.put("diagnosticsSidecarPath", sidecar.toString());\n\n            java.io.OutputStream safOut =\n                    com.particlesdevs.photoncamera.util.SimpleStorageHelper\n                            .openOutputStreamByAbsPath(sidecar.toString());\n            if (safOut != null) {\n                diagnostics.put("diagnosticsWriter", "DIAG1C_SAF_ABSPATH");\n                byte[] payload = diagnostics.toString(2).getBytes(StandardCharsets.UTF_8);\n                try (java.io.OutputStream out = safOut) {\n                    out.write(payload);\n                    out.flush();\n                }\n                android.util.Log.d("M10RNativeRenderer",\n                        "M10-R DIAG1C SAF JSON saved bytes=" + payload.length + " path=" + sidecar);\n                return payload.length > 0;\n            }\n\n            diagnostics.put("diagnosticsWriter", "DIAG1C_DIRECT_FALLBACK");\n            byte[] payload = diagnostics.toString(2).getBytes(StandardCharsets.UTF_8);\n            Files.createDirectories(parent);\n            try (java.io.OutputStream out = Files.newOutputStream(sidecar)) {\n                out.write(payload);\n                out.flush();\n            }\n            boolean ok = Files.exists(sidecar) && Files.size(sidecar) > 0L;\n            android.util.Log.d("M10RNativeRenderer",\n                    "M10-R DIAG1C direct JSON saved=" + ok + " path=" + sidecar);\n            return ok;\n        } catch (Throwable error) {\n            android.util.Log.e("M10RNativeRenderer",\n                    "M10-R DIAG1C JSON WRITE FAILED path=" + sidecar + " "\n                            + android.util.Log.getStackTraceString(error));\n            android.util.Log.e("M10RNativeRenderer",\n                    "M10-R DIAG1C JSON PAYLOAD=" + diagnostics.toString());\n            return false;\n        }\n    }'''
r=one(r,old,new,'saf-writer')
wr(renderer,r)

default='app/src/main/java/com/particlesdevs/photoncamera/processing/DefaultSaver.java'; d=rd(default)
old_call='''M10RNativeRenderer.persistDiagnostics(capture1Jpeg, capture1b.diagnostics);'''
new_call='''boolean diagSaved = M10RNativeRenderer.persistDiagnostics(\n                                capture1Jpeg, capture1b.diagnostics);\n                        Log.d(TAG, "M10-R DIAG1C JSON saved=" + diagSaved\n                                + " siblingOf=" + capture1Jpeg);\n                        if (!diagSaved) {\n                            Log.e(TAG, "M10-R DIAG1C JSON WRITE FAILED; see M10RNativeRenderer log payload");\n                        }'''
d=one(d,old_call,new_call,'checked-call')
wr(default,d)

R=rd(renderer); D=rd(default); G=rd(grad)
for x in [
    'DIAG1C_SAF_ABSPATH',
    'openOutputStreamByAbsPath(sidecar.toString())',
    'DIAG1C_DIRECT_FALLBACK',
    'M10-R DIAG1C JSON WRITE FAILED path=',
    'RENDER1F_YC2A_MATRIX1A',
    'edgeScaleTableApplied", true',
    'edgeHfRecordGainApplied", true',
    'hdrEnabled", false',
    'sourceFrameCount", 1',
]:
    if x not in R: raise SystemExit('RENDER1F DIAG1C SAF1 renderer invariant missing: '+x)
for x in [
    'boolean diagSaved = M10RNativeRenderer.persistDiagnostics(',
    'M10-R DIAG1C JSON saved=',
    'M10-R DIAG1C JSON WRITE FAILED;',
]:
    if x not in D: raise SystemExit('RENDER1F DIAG1C SAF1 saver invariant missing: '+x)
if 'diagnostics.put("diagnosticsWriter", "DIAG1A_JPEG_SIBLING")' in R:
    raise SystemExit('RENDER1F DIAG1C SAF1 stale DIAG1A writer identity remains')
if '-diag1c-saf1' not in G:
    raise SystemExit('RENDER1F DIAG1C SAF1 version marker missing')

print('M10-R RENDER1F DIAG1C SAF1 applied')
print(' - JSON writer now uses Photon SimpleStorageHelper SAF absolute-path writer first')
print(' - direct Files.newOutputStream remains only as fallback')
print(' - diagnostics save result is checked and logged; failure payload is retained in log')
print(' - JSON remains paired by capture stem with the rendered JPEG/DNG in PhotonCamera/Raw')
print(' - rendering, colour, tone, edge, exposure, JPEG quality, 12MP and HDR-off are unchanged')
