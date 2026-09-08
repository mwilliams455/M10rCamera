#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix-m10r-render1f-diag1a.py <PhotonCamera-root>')
root = Path(sys.argv[1]).resolve()
if not (root/'app').is_dir():
    raise SystemExit('RENDER1F DIAG1A: not a PhotonCamera root')

def rd(rel):
    p=root/rel
    if not p.exists(): raise SystemExit('RENDER1F DIAG1A missing: '+rel)
    return p.read_text()
def wr(rel,s): (root/rel).write_text(s)
def one(s,a,b,label):
    n=s.count(a)
    if n!=1: raise SystemExit('RENDER1F DIAG1A anchor %s count=%d'%(label,n))
    return s.replace(a,b,1)

# Diagnostics-only patch. Do not touch any image-processing arithmetic.
grad='app/build.gradle'; g=rd(grad)
g=one(g,
      "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1f-yc2a-matrix1a'",
      "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1f-yc2a-matrix1a-diag1a'",
      'version')
wr(grad,g)

renderer='app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'; r=rd(renderer)
old='''    public static void persistDiagnostics(Path dngPath, JSONObject diagnostics) {\n        if (dngPath == null || diagnostics == null) return;\n        try {\n            String name = dngPath.getFileName().toString();\n            int dot = name.lastIndexOf('.');\n            String stem = dot > 0 ? name.substring(0, dot) : name;\n            Path sidecar = dngPath.resolveSibling(stem + "_M10R_CAPTURE1B.json");\n            Files.write(sidecar,\n                    diagnostics.toString(2).getBytes(StandardCharsets.UTF_8));\n        } catch (Throwable ignored) {}\n    }'''
new='''    public static boolean persistDiagnostics(Path anchorPath, JSONObject diagnostics) {\n        if (anchorPath == null || diagnostics == null) return false;\n        try {\n            Path parent = anchorPath.getParent();\n            if (parent == null) return false;\n            Files.createDirectories(parent);\n            String name = anchorPath.getFileName().toString();\n            int dot = name.lastIndexOf('.');\n            String stem = dot > 0 ? name.substring(0, dot) : name;\n            Path sidecar = parent.resolve(stem + "_M10R_CAPTURE1B.json");\n            diagnostics.put("diagnosticsWriter", "DIAG1A_JPEG_SIBLING");\n            diagnostics.put("diagnosticsSidecarPath", sidecar.toString());\n            Files.write(sidecar, diagnostics.toString(2).getBytes(StandardCharsets.UTF_8));\n            return Files.exists(sidecar) && Files.size(sidecar) > 0L;\n        } catch (Throwable ignored) {\n            return false;\n        }\n    }'''
r=one(r,old,new,'persist-method')
wr(renderer,r)

default='app/src/main/java/com/particlesdevs/photoncamera/processing/DefaultSaver.java'; d=rd(default)
d=one(d,
      'M10RNativeRenderer.persistDiagnostics(capture1Dng, capture1b.diagnostics);',
      'M10RNativeRenderer.persistDiagnostics(capture1Jpeg, capture1b.diagnostics);',
      'jpeg-sibling-call')
wr(default,d)

R=rd(renderer); D=rd(default); G=rd(grad)
required_r=[
    'public static boolean persistDiagnostics(Path anchorPath, JSONObject diagnostics)',
    'Files.createDirectories(parent);',
    'DIAG1A_JPEG_SIBLING',
    'diagnosticsSidecarPath',
    'Files.exists(sidecar) && Files.size(sidecar) > 0L',
    'RENDER1F_YC2A_MATRIX1A',
    'M10R_Yc_Convert_Y_Q12_1224_2403_469',
    'edgeScaleTableApplied", true',
    'edgeHfRecordGainApplied", true',
    'hdrEnabled", false',
    'sourceFrameCount", 1',
]
for x in required_r:
    if x not in R: raise SystemExit('RENDER1F DIAG1A renderer invariant missing: '+x)
if 'persistDiagnostics(capture1Jpeg, capture1b.diagnostics)' not in D:
    raise SystemExit('RENDER1F DIAG1A JPEG-sidecar call missing')
if 'persistDiagnostics(capture1Dng, capture1b.diagnostics)' in D:
    raise SystemExit('RENDER1F DIAG1A old RAW-sidecar call remains')
if '-diag1a' not in G:
    raise SystemExit('RENDER1F DIAG1A version marker missing')
print('M10-R RENDER1F DIAG1A applied')
print(' - diagnostics JSON now targets the JPEG sibling directory (DCIM/Camera)')
print(' - writer verifies non-empty file and no longer silently reports success')
print(' - image rendering, edge arithmetic, YC2A matrix, JPEG quality, single-RAW and HDR-off are unchanged')
