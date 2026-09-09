#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix-m10r-render1f-diag1c.py <PhotonCamera-root>')
root = Path(sys.argv[1]).resolve()
if not (root/'app').is_dir():
    raise SystemExit('RENDER1F DIAG1C: not a PhotonCamera root')

def rd(rel):
    p=root/rel
    if not p.exists(): raise SystemExit('RENDER1F DIAG1C missing: '+rel)
    return p.read_text()
def wr(rel,s): (root/rel).write_text(s)
def one(s,a,b,label):
    n=s.count(a)
    if n!=1: raise SystemExit('RENDER1F DIAG1C anchor %s count=%d'%(label,n))
    return s.replace(a,b,1)

# Diagnostics-only follow-up after DIAG1B field test produced no user-visible JSON.
# Keep all photographic arithmetic frozen. Make diagnostics impossible to lose by:
#  1) still attempting the explicit DCIM/Camera sidecar,
#  2) also writing a second copy beside the proven-writable JPEGSAVE1 JPEG in Raw,
#  3) ALWAYS emitting the complete JSON payload to the Photon log in <=3000-char chunks.

grad='app/build.gradle'; g=rd(grad)
g=one(g,
      "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1f-yc2a-matrix1a-diag1b'",
      "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b-stability3-native1-look1b-yc1b-render1f-yc2a-matrix1a-diag1c'",
      'version')
wr(grad,g)

default='app/src/main/java/com/particlesdevs/photoncamera/processing/DefaultSaver.java'; d=rd(default)
old='''                    boolean diagSaved = M10RNativeRenderer.persistDiagnostics(\n                            diagAnchor, capture1b.diagnostics);\n                    Log.d(TAG, "M10-R DIAG1B JSON saved=" + diagSaved + " anchor=" + diagAnchor);\n                    if (!diagSaved) {\n                        Log.e(TAG, "M10-R DIAG1B JSON WRITE FAILED; payload="\n                                + capture1b.diagnostics.toString());\n                    }'''
new='''                    boolean diagSaved = M10RNativeRenderer.persistDiagnostics(\n                            diagAnchor, capture1b.diagnostics);\n                    // DIAG1C: also persist beside the JPEGSAVE1 JPEG in the already-proven\n                    // writable PhotonCamera/Raw directory. This is a second copy only.\n                    boolean rawDiagSaved = M10RNativeRenderer.persistDiagnostics(\n                            capture1Jpeg, capture1b.diagnostics);\n                    Log.d(TAG, "M10-R DIAG1C JSON publicSaved=" + diagSaved\n                            + " rawSaved=" + rawDiagSaved\n                            + " publicAnchor=" + diagAnchor\n                            + " rawAnchor=" + capture1Jpeg);\n\n                    // Always log the complete payload, whether either file write succeeds or not.\n                    // Chunk below Android/logcat practical line limits so the payload is recoverable.\n                    String diagPayload = capture1b.diagnostics.toString();\n                    final int diagChunk = 3000;\n                    int diagPart = 0;\n                    for (int off = 0; off < diagPayload.length(); off += diagChunk) {\n                        int end = Math.min(diagPayload.length(), off + diagChunk);\n                        Log.d(TAG, "M10-R DIAG1C PAYLOAD part=" + diagPart + " "\n                                + diagPayload.substring(off, end));\n                        diagPart++;\n                    }\n                    Log.d(TAG, "M10-R DIAG1C PAYLOAD END parts=" + diagPart\n                            + " chars=" + diagPayload.length());'''
d=one(d,old,new,'always-log-payload')
wr(default,d)

renderer='app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'; r=rd(renderer)
r=one(r,
      'diagnostics.put("diagnosticsWriter", "DIAG1B_DCIM_CAMERA_EXPLICIT");',
      'diagnostics.put("diagnosticsWriter", "DIAG1C_DUAL_FILE_PLUS_LOG");',
      'writer-id')
wr(renderer,r)

R=rd(renderer); D=rd(default); G=rd(grad)
for x in [
    'DIAG1C_DUAL_FILE_PLUS_LOG',
    'RENDER1F_YC2A_MATRIX1A',
    'edgeScaleTableApplied", true',
    'edgeHfRecordGainApplied", true',
    'hdrEnabled", false',
    'sourceFrameCount", 1',
]:
    if x not in R: raise SystemExit('RENDER1F DIAG1C renderer invariant missing: '+x)
for x in [
    'rawDiagSaved = M10RNativeRenderer.persistDiagnostics(',
    'capture1Jpeg, capture1b.diagnostics',
    'M10-R DIAG1C JSON publicSaved=',
    'M10-R DIAG1C PAYLOAD part=',
    'M10-R DIAG1C PAYLOAD END parts=',
    'final int diagChunk = 3000',
]:
    if x not in D: raise SystemExit('RENDER1F DIAG1C saver invariant missing: '+x)
if '-diag1c' not in G:
    raise SystemExit('RENDER1F DIAG1C version marker missing')

print('M10-R RENDER1F DIAG1C applied')
print(' - photographic rendering remains byte-for-byte intended to match DIAG1B/RENDER1F')
print(' - JSON attempted in DCIM/Camera and beside JPEG in PhotonCamera/Raw')
print(' - complete JSON always emitted to Photon log in 3000-char chunks')
print(' - single RAW, HDR-off, 12MP, JPEG quality, colour/tone/edge/exposure unchanged')
