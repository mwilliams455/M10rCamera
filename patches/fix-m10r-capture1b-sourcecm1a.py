#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix-m10r-capture1b-sourcecm1a.py <PhotonCamera-root>')

root = Path(sys.argv[1]).resolve()
if not (root / 'app').is_dir():
    raise SystemExit('CAPTURE1B SOURCECM1A: not a PhotonCamera root')

renderer = root / 'app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'
gradle = root / 'app/build.gradle'
if not renderer.exists() or not gradle.exists():
    raise SystemExit('CAPTURE1B SOURCECM1A: generated renderer/build.gradle missing')

r = renderer.read_text()
g = gradle.read_text()

# SOURCECM1A: Camera2 ColorSpaceTransform storage must be converted into the same
# matrix representation used by Photon Converter math. The working M9 source
# calibration path and Photon Parameters.ReCalcColor() both use
# Converter.convertColorspaceTransform(). CAPTURE1B previously used copyElements()
# directly, then passed those arrays into Converter.findDngInterpolationFactor()
# and calculateCameraToXYZD50Transform(), mixing conventions.
#
# This changes representation only. DNG ColorMatrix remains XYZ->reference-camera
# and is NOT ForwardMatrix-normalized. ForwardMatrix normalization remains exactly
# as in CAPTURE1B SOURCECAL2A.
old = '''    private static float[] transform(ColorSpaceTransform t) {\n        if (t == null) return null;\n        Rational[] r=new Rational[9];\n        t.copyElements(r,0);\n        float[] out=new float[9];\n        for(int i=0;i<9;i++) out[i]=r[i].floatValue();\n        return out;\n    }'''
new = '''    private static float[] transform(ColorSpaceTransform t) {\n        if (t == null) return null;\n        float[] out = new float[9];\n        // SOURCECM1A: match Photon/M9 matrix representation exactly.\n        Converter.convertColorspaceTransform(t, out);\n        return out;\n    }'''
if new not in r:
    if r.count(old) != 1:
        raise SystemExit('CAPTURE1B SOURCECM1A transform anchor missing/non-unique')
    r = r.replace(old, new, 1)

anchor = '        d.put("sourceModel", "Camera2_dual_illuminant_native_XYZ_D50");\n'
insert = anchor + '''        d.put("sourceMatrixConventionFix", "SOURCECM1A");\n        d.put("sourceCamera2TransformConversion", "Photon_Converter.convertColorspaceTransform");\n        d.put("sourceCamera2RawCopyElementsUsed", false);\n'''
if 'sourceMatrixConventionFix", "SOURCECM1A"' not in r:
    if r.count(anchor) != 1:
        raise SystemExit('CAPTURE1B SOURCECM1A diagnostic anchor missing/non-unique')
    r = r.replace(anchor, insert, 1)

# Distinguish the corrected build on-device.
old_version = "versionName '0.97-m10rcapture1b-jpegsave1'"
new_version = "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a'"
if new_version not in g:
    if g.count(old_version) != 1:
        raise SystemExit('CAPTURE1B SOURCECM1A version anchor missing/non-unique')
    g = g.replace(old_version, new_version, 1)

renderer.write_text(r)
gradle.write_text(g)

# Hard invariants.
r = renderer.read_text()
g = gradle.read_text()
required = [
    'Converter.convertColorspaceTransform(t, out);',
    'sourceMatrixConventionFix", "SOURCECM1A"',
    'sourceCamera2TransformConversion", "Photon_Converter.convertColorspaceTransform"',
    'sourceCamera2RawCopyElementsUsed", false',
    'sourceColorMatrixConvention", "DNG_XYZ_to_reference_camera_unmodified"',
    'sourceColorMatrixRowNormalizationApplied", false',
    'sourceForwardMatrixNormalizationApplied", true',
    'demosaicChannelOrderFix", "RGBORDER1A"',
    'postDemosaicRedBlueSwapApplied", false',
]
for needle in required:
    if needle not in r:
        raise SystemExit('CAPTURE1B SOURCECM1A verify missing: ' + needle)
if 't.copyElements(r,0);' in r:
    raise SystemExit('CAPTURE1B SOURCECM1A raw Camera2 copyElements convention remains')
if new_version not in g:
    raise SystemExit('CAPTURE1B SOURCECM1A build identity missing')

print('M10-R CAPTURE1B SOURCECM1A applied')
print(' - Camera2 ColorSpaceTransform conversion now matches Photon/M9')
print(' - DNG ColorMatrix remains unnormalized XYZ->reference-camera')
print(' - ForwardMatrix normalization retained')
print(' - RGBORDER1A retained')
print(' - CA9 / target M10-R / CFA / shading unchanged')
print(' - nonlinear MEDIUM/DG finishing remains intentionally unchanged for isolation')
print(' - single-frame/no-HDR route unchanged')
