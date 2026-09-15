#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys
import tempfile

if len(sys.argv) != 2:
    raise SystemExit('usage: run-m10r-yblend-diag1a-currentbaseline.py <PhotonCamera-root>')

repo = Path(__file__).resolve().parent.parent
src_path = repo / 'patches' / 'fix-m10r-yblend-diag1a.py'
if not src_path.is_file():
    raise SystemExit('YBLEND DIAG1A BASELINEFIX1: missing original DIAG1A patch')

src = src_path.read_text()

# RENDER1F YC2A MATRIX1A already promoted the exact B2Y record-0x0C matrix
# (1224,2403,469 / -691,-1357,2048 / 2048,-1715,-333) into both Java and
# native rendering. The original DIAG1A patch was authored against the older
# YC1A assumption 1224,2404,467, so its output-neutrality gates are stale.
# Correct only those baseline/provenance assumptions here. The diagnostic
# instrumentation itself is otherwise left byte-for-byte unchanged.
replacements = [
    (
        "# IMPORTANT: the live renderer's YC1A Y row is 1224,2404,467. The newly\n# recovered TRUE Y_BLEND record 0x0C Y row is 1224,2403,469. Cb/Cr rows are\n# identical. DIAG1A therefore measures the true record-0x0C coordinates in the\n# existing 1/64 Java diagnostic sampler but deliberately does NOT replace YC1A\n# and does not touch m10rRender.cpp. This keeps photographic pixels frozen.",
        "# IMPORTANT: RENDER1F YC2A MATRIX1A already promoted the recovered TRUE\n# Y_BLEND record-0x0C matrix into the live Java/native renderer. DIAG1A therefore\n# measures that exact coordinate system in the existing 1/64 Java diagnostic\n# sampler and deliberately does NOT alter m10rRender.cpp. Photographic pixels\n# remain frozen at the current RENDER1Q baseline."
    ),
    (
        "                    // record-0x0C matrix beside the frozen live YC1A matrix.\n                    // YC1A stays untouched: live Y row = 1224,2404,467; true\n                    // Y_BLEND row = 1224,2403,469. Cb/Cr rows are identical.",
        "                    // record-0x0C matrix beside the frozen live YC2A matrix.\n                    // RENDER1F already made the live matrix coefficient-identical\n                    // to record 0x0C; this diagnostic only observes its coordinates."
    ),
    (
        'yBlendDiag1A.put("liveYc1AMatrixQ12", "1224,2404,467;-691,-1357,2048;2048,-1715,-333");',
        'yBlendDiag1A.put("liveYc1AMatrixQ12", "1224,2403,469;-691,-1357,2048;2048,-1715,-333");'
    ),
    (
        'yBlendDiag1A.put("trueMinusLiveYRowQ12", "0,-1,+2");',
        'yBlendDiag1A.put("trueMinusLiveYRowQ12", "0,0,0");'
    ),
    (
        "'liveYc1AMatrixQ12\", \"1224,2404,467;-691,-1357,2048;2048,-1715,-333',",
        "'liveYc1AMatrixQ12\", \"1224,2403,469;-691,-1357,2048;2048,-1715,-333',"
    ),
    (
        "'trueMinusLiveYRowQ12\", \"0,-1,+2',",
        "'trueMinusLiveYRowQ12\", \"0,0,0',"
    ),
    (
        "'const double y  = (1224.0*lr + 2404.0*lg + 467.0*lb) / 4096.0;',",
        "'const double y  = (1224.0*lr + 2403.0*lg + 469.0*lb) / 4096.0;',"
    ),
    (
        "# Prove the true record matrix exists only in Java diagnostics; it must not have\n# silently replaced live native YC1A.\nif '(1224.0*lr + 2403.0*lg + 469.0*lb) / 4096.0' in C:\n    raise SystemExit('YBLEND DIAG1A changed native Y matrix; diagnostic must be output-neutral')",
        "# Prove DIAG1A did not regress the already-promoted exact YC2A matrix.\nif '(1224.0*lr + 2404.0*lg + 467.0*lb) / 4096.0' in C:\n    raise SystemExit('YBLEND DIAG1A regressed native Y matrix to legacy YC1A coefficients')"
    ),
    (
        "print(' - live YC1A 1224/2404/467 matrix preserved; true Y_BLEND 1224/2403/469 measured separately')",
        "print(' - live YC2A matrix already equals true record0C 1224/2403/469; DIAG1A observes it without changing pixels')"
    ),
]

for old, new in replacements:
    count = src.count(old)
    if count != 1:
        raise SystemExit(f'YBLEND DIAG1A BASELINEFIX1 replacement count={count}: {old[:80]}')
    src = src.replace(old, new, 1)

# The actual coordinate delta is now expected to be exactly zero because ycY
# and ybdY use the same coefficients after RENDER1F. Keep the field in the JSON
# as a useful runtime identity check rather than deleting diagnostic plumbing.
if '1224,2404,467' in src:
    raise SystemExit('YBLEND DIAG1A BASELINEFIX1: stale 1224/2404/467 assumption remains')
if '1224,2403,469' not in src or 'trueMinusLiveYRowQ12", "0,0,0' not in src:
    raise SystemExit('YBLEND DIAG1A BASELINEFIX1: corrected matrix identity missing')

with tempfile.TemporaryDirectory(prefix='m10r-yblenddiag1a-') as td:
    patched = Path(td) / 'fix-m10r-yblend-diag1a-currentbaseline.py'
    patched.write_text(src)
    subprocess.run([sys.executable, str(patched), sys.argv[1]], check=True)

print('M10-R YBLEND DIAG1A BASELINEFIX1 applied')
print(' - historical DIAG1A instrumentation retained')
print(' - stale YC1A 1224/2404/467 baseline assumption corrected to current YC2A 1224/2403/469')
print(' - native renderer remains untouched by DIAG1A')
