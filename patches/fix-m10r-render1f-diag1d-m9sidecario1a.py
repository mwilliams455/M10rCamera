#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix-m10r-render1f-diag1d-m9sidecario1a.py <PhotonCamera-root>')
root = Path(sys.argv[1]).resolve()
if not (root/'app').is_dir():
    raise SystemExit('RENDER1F DIAG1D M9SIDECARIO1A: not a PhotonCamera root')

def rd(rel):
    p = root/rel
    if not p.exists(): raise SystemExit('RENDER1F DIAG1D missing: '+rel)
    return p.read_text()
def wr(rel,s):
    p = root/rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s)
def one(s,a,b,label):
    n=s.count(a)
    if n!=1: raise SystemExit('RENDER1F DIAG1D anchor %s count=%d'%(label,n))
    return s.replace(a,b,1)

# Diagnostics transport only. Port the M9 SIDECAR1A public-storage mechanism:
# direct filesystem stream first, then Photon SimpleStorageHelper/SAF fallback.
# This deliberately removes Files.createDirectories(parent) from the public sidecar
# path because that call can fail under scoped storage before fallback is attempted.
# Photographic rendering remains untouched.

grad='app/build.gradle'; g=rd(grad)
g=one(g,
      "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1f-yc2a-matrix1a-diag1c'",
      "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1f-yc2a-matrix1a-diag1d-m9sidecario1a'",
      'version')
wr(grad,g)

helper_rel='app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RDiagnosticSidecarIO.java'
if (root/helper_rel).exists():
    raise SystemExit('RENDER1F DIAG1D helper already exists; refuse ambiguous reapply')
helper=r'''package com.particlesdevs.photoncamera.m10r;

import android.os.Process;

import com.particlesdevs.photoncamera.util.Log;
import com.particlesdevs.photoncamera.util.SimpleStorageHelper;

import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * M10-R diagnostic sidecar transport ported from the proven M9 SIDECAR1A mechanism.
 * Diagnostic-only: no image/capture state is read or changed here.
 */
public final class M10RDiagnosticSidecarIO {
    public static final String SCHEMA = "m10r.sidecario.v1.m9port.directfirst.saffallback";
    private static final String TAG = "M10RDiagIO";

    private M10RDiagnosticSidecarIO() {}

    public static boolean persist(Path path, byte[] bytes, String role) {
        if (path == null || bytes == null) return false;
        final long startedNs = System.nanoTime();
        Throwable directError = null;
        try {
            Process.setThreadPriority(Process.THREAD_PRIORITY_BACKGROUND);
            try {
                // Match M9 SIDECAR1A: try the ordinary filesystem first.
                // Do NOT call Files.createDirectories() on the public parent here;
                // the JPEG/DNG parent already exists and scoped storage may reject it.
                try (OutputStream out = Files.newOutputStream(path)) {
                    out.write(bytes);
                    out.flush();
                }
                Log.d(TAG, "M10-R M9SIDECARIO1A saved mode=direct_filesystem role=" + role
                        + " path=" + path + " elapsedMs="
                        + ((System.nanoTime() - startedNs) / 1_000_000.0));
                return true;
            } catch (Throwable direct) {
                directError = direct;
            }

            // Exact M9 public-storage escape hatch: route through Photon's storage helper/SAF.
            OutputStream safOut = SimpleStorageHelper.openOutputStreamByAbsPath(path.toString());
            if (safOut == null) {
                Log.e(TAG, "M10-R M9SIDECARIO1A SAF stream unavailable; direct error="
                        + String.valueOf(directError) + " path=" + path);
                return false;
            }
            try (OutputStream out = safOut) {
                out.write(bytes);
                out.flush();
            }
            Log.d(TAG, "M10-R M9SIDECARIO1A saved mode=saf_fallback role=" + role
                    + " path=" + path + " elapsedMs="
                    + ((System.nanoTime() - startedNs) / 1_000_000.0));
            return true;
        } catch (Throwable t) {
            Log.e(TAG, "M10-R M9SIDECARIO1A persist failed role=" + role
                    + " path=" + path, t);
            return false;
        }
    }
}
'''
wr(helper_rel, helper)

renderer='app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'; r=rd(renderer)
old='''    public static boolean persistDiagnostics(Path anchorPath, JSONObject diagnostics) {\n        if (anchorPath == null || diagnostics == null) return false;\n        try {\n            Path parent = anchorPath.getParent();\n            if (parent == null) return false;\n            Files.createDirectories(parent);\n            String name = anchorPath.getFileName().toString();\n            int dot = name.lastIndexOf('.');\n            String stem = dot > 0 ? name.substring(0, dot) : name;\n            Path sidecar = parent.resolve(stem + "_M10R_CAPTURE1B.json");\n            diagnostics.put("diagnosticsWriter", "DIAG1C_DUAL_FILE_PLUS_LOG");\n            diagnostics.put("diagnosticsSidecarPath", sidecar.toString());\n            Files.write(sidecar, diagnostics.toString(2).getBytes(StandardCharsets.UTF_8));\n            return Files.exists(sidecar) && Files.size(sidecar) > 0L;\n        } catch (Throwable ignored) {\n            return false;\n        }\n    }'''
new='''    public static boolean persistDiagnostics(Path anchorPath, JSONObject diagnostics) {\n        if (anchorPath == null || diagnostics == null) return false;\n        try {\n            Path parent = anchorPath.getParent();\n            if (parent == null) return false;\n            String name = anchorPath.getFileName().toString();\n            int dot = name.lastIndexOf('.');\n            String stem = dot > 0 ? name.substring(0, dot) : name;\n            Path sidecar = parent.resolve(stem + "_M10R_CAPTURE1B.json");\n            diagnostics.put("diagnosticsWriter", "DIAG1D_M9SIDECARIO1A");\n            diagnostics.put("diagnosticsTransport", M10RDiagnosticSidecarIO.SCHEMA);\n            diagnostics.put("diagnosticsSidecarPath", sidecar.toString());\n            byte[] bytes = diagnostics.toString(2).getBytes(StandardCharsets.UTF_8);\n            return M10RDiagnosticSidecarIO.persist(sidecar, bytes, "m10r_capture1b");\n        } catch (Throwable ignored) {\n            return false;\n        }\n    }'''
r=one(r,old,new,'m9-sidecar-transport')
wr(renderer,r)

R=rd(renderer); D=rd('app/src/main/java/com/particlesdevs/photoncamera/processing/DefaultSaver.java'); G=rd(grad); H=rd(helper_rel)
for x in [
    'DIAG1D_M9SIDECARIO1A',
    'M10RDiagnosticSidecarIO.SCHEMA',
    'M10RDiagnosticSidecarIO.persist(sidecar, bytes, "m10r_capture1b")',
    'RENDER1F_YC2A_MATRIX1A',
    'edgeScaleTableApplied", true',
    'edgeHfRecordGainApplied", true',
    'hdrEnabled", false',
    'sourceFrameCount", 1',
]:
    if x not in R: raise SystemExit('RENDER1F DIAG1D renderer invariant missing: '+x)
for x in [
    'SimpleStorageHelper.openOutputStreamByAbsPath(path.toString())',
    'Files.newOutputStream(path)',
    'm10r.sidecario.v1.m9port.directfirst.saffallback',
    'saf_fallback',
]:
    if x not in H: raise SystemExit('RENDER1F DIAG1D helper invariant missing: '+x)
# Scope the writer guard to persistDiagnostics itself. M10RNativeRenderer contains
# other diagnostic/failure-sidecar Files.write calls that are intentionally untouched.
if old in R:
    raise SystemExit('RENDER1F DIAG1D old persistDiagnostics implementation remains')
if new not in R:
    raise SystemExit('RENDER1F DIAG1D new persistDiagnostics implementation missing')
for x in [
    'capture1Jpeg, capture1b.diagnostics',
    'M10-R DIAG1C PAYLOAD part=',
    'M10-R DIAG1C PAYLOAD END parts=',
]:
    if x not in D: raise SystemExit('RENDER1F DIAG1D log/raw fallback invariant missing: '+x)
if '-diag1d-m9sidecario1a' not in G:
    raise SystemExit('RENDER1F DIAG1D version marker missing')

print('M10-R RENDER1F DIAG1D M9SIDECARIO1A applied')
print(' - exact M9 SIDECAR1A transport principle ported: direct filesystem first, Photon SAF fallback second')
print(' - public Files.createDirectories gate removed from persistDiagnostics')
print(' - M10-R sidecar naming/payload retained')
print(' - DIAG1C complete-log fallback retained')
print(' - rendering, colour, tone, edge, exposure, JPEG quality, 12MP, single RAW and HDR-off unchanged')
