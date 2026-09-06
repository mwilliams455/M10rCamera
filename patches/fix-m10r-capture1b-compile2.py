#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix-m10r-capture1b-compile2.py <PhotonCamera-root>')

root = Path(sys.argv[1]).resolve()
renderer = root / 'app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'
if not renderer.exists():
    raise SystemExit('CAPTURE1B COMPILE2 requires generated M10RNativeRenderer.java')

s = renderer.read_text()
old = '''        Integer ref2Obj = c.get(CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT2);\n        if (ref1Obj == null) throw new IllegalStateException("source illuminant1 missing");\n        int ref1 = ref1Obj;\n        int ref2 = ref2Obj != null ? ref2Obj : ref1;\n'''
new = '''        Byte ref2Obj = c.get(CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT2);\n        if (ref1Obj == null) throw new IllegalStateException("source illuminant1 missing");\n        int ref1 = ref1Obj;\n        int ref2 = ref2Obj != null ? (ref2Obj & 0xff) : ref1;\n'''

if old not in s:
    if 'Byte ref2Obj = c.get(CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT2);' in s:
        print('CAPTURE1B COMPILE2 already applied')
        raise SystemExit(0)
    raise SystemExit('CAPTURE1B COMPILE2 illuminant2 anchor missing')

s = s.replace(old, new, 1)

for required in [
    'Byte ref2Obj = c.get(CameraCharacteristics.SENSOR_REFERENCE_ILLUMINANT2);',
    'int ref2 = ref2Obj != null ? (ref2Obj & 0xff) : ref1;',
]:
    if required not in s:
        raise SystemExit('CAPTURE1B COMPILE2 verify failed: ' + required)

renderer.write_text(s)
print('M10-R CAPTURE1B COMPILE2 applied')
print(' - SENSOR_REFERENCE_ILLUMINANT2 uses Android Camera2 Byte key type')
print(' - unsigned byte converted to int for DNG illuminant handling')
