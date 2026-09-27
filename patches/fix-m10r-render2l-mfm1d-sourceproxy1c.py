#!/usr/bin/env python3
"""Apply SOURCEPROXY1C stable metadata identity to reconstructed RENDER2K.

Identity robustness only: no new inferred preview transfer, scene thresholds,
exposure allocator, RAW/CFA path or target photographic rendering arithmetic.
Historical fixed-optics seeds are retained through an explicit provisional,
static-singleton alias. They are NOT validated full-signature calibrations.
No user photographs, diagnostic grids or private fixtures are shipped here.
"""
from pathlib import Path
import hashlib
import json
import re
import sys

CPP_SHA = '3f7b696cdf33e29348d7c0532f658c11819f9b8e54772b55753e357fb6018985'
VERSION = '0.97-m10r2l-mfm1d-sourceproxy1c'
JAVA_REL = Path('app/src/main/java/com/particlesdevs/photoncamera')

def once(s, old, new):
    if s.count(old) != 1:
        raise RuntimeError('Expected one anchor: ' + old[:120])
    return s.replace(old, new, 1)

def patch_renderer(s):
    s = once(s, 'MFM1D_SOURCEPROXY1B_GENERIC_FINGERPRINT',
             'MFM1D_SOURCEPROXY1C_STABLE_FINGERPRINT')
    s = once(s, 'generic_Camera2_RAW_characteristics_fingerprint_not_brand_model_lens_name',
             'static_CameraCharacteristics_signature_not_current_optical_state_not_hardware_serial')
    anchor = '                .put("sourceProxyCalibrationEvidenceId", sourceProxy.calibrationEvidenceId)\n'
    s = once(s, anchor, anchor + '''                .put("sourceProxyFingerprintVersion", M10RMfm1DSourceProxy.IDENTITY_VERSION)
                .put("sourceProxyCurrentOpticalStateInFingerprint", false)
                .put("sourceProxyCurrentFocalApertureTelemetryOnly", true)
                .put("sourceProxyFingerprintIncludesStaticMatrices", true)
                .put("sourceProxyFingerprintUsesAvailableOptics", true)
                .put("sourceProxyFullSignatureCalibrationValidated", false)
                .put("sourceProxyAutomaticLearningEnabled", false)
                .put("sourceProxyIdentityImpliesTransferParity", false)
''')
    # Missing/invalid state must not make JSON reject non-finite telemetry.
    for field in ['sensorWidthMm', 'physicalFocalMm', 'aperture']:
        pattern = re.compile(r'(\.put\("sourceProxy[^"\n]+", )sourceProxy\.' + field + r'\)')
        s, count = pattern.subn(r'\1(Double.isFinite(sourceProxy.' + field +
                               ') ? sourceProxy.' + field + ' : JSONObject.NULL))', s)
        if count != 1:
            raise RuntimeError('Expected one finite telemetry field: ' + field)
    return s

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def frozen_files(root):
    files = []
    for sub in ['app/src/main/cpp', 'app/src/main/assets']:
        files.extend(p for p in (root / sub).rglob('*') if p.is_file())
    for rel in ['m10r/M10RMfm1B.java', 'm10r/M10RIntegralMask.java',
                'm10r/M10RMfm1DSourceState.java', 'm10r/M10RAe1BPolicy.java',
                'processing/parameters/IsoExpoSelector.java',
                'processing/DefaultSaver.java', 'processing/ImageSaver.java']:
        p = root / JAVA_REL / rel
        if not p.is_file():
            raise RuntimeError('Missing frozen file: ' + str(p))
        files.append(p)
    return {str(p.relative_to(root)): sha(p) for p in sorted(set(files))}

def main():
    if len(sys.argv) != 2:
        raise SystemExit('usage: fix-m10r-render2l-mfm1d-sourceproxy1c.py <PhotonCamera>')
    root = Path(sys.argv[1]).resolve()
    repo = Path(__file__).resolve().parents[1]
    cpp = root / 'app/src/main/cpp/m10rRender.cpp'
    if sha(cpp) != CPP_SHA:
        raise RuntimeError('Unexpected RENDER2G native source')
    before = frozen_files(root)
    renderer = root / JAVA_REL / 'm10r/M10RNativeRenderer.java'
    proxy = root / JAVA_REL / 'm10r/M10RMfm1DSourceProxy.java'
    gradle = root / 'app/build.gradle'
    new_renderer = patch_renderer(renderer.read_text())
    new_gradle = once(gradle.read_text(), '0.97-m10r2k-mfm1d-sourceproxy1b', VERSION)
    new_proxy = (repo / 'android/sourceproxy1c/M10RMfm1DSourceProxy.java').read_text()
    # Compare complete transform method text: no changed pixel/meter math hidden here.
    def transform(s):
        return s[s.index('    public static double[] transform('):s.index('\n    private static', s.index('    public static double[] transform('))].rstrip()
    if transform(proxy.read_text()) != transform(new_proxy):
        raise RuntimeError('SOURCEPROXY1C must not change transform arithmetic')
    for forbidden in ['Build.MODEL', 'Build.MANUFACTURER', 'CaptureResult',
                      'XIAOMI', 'Xiaomi', 'SUPERTELE', 'MAIN24']:
        if forbidden in new_proxy:
            raise RuntimeError('Forbidden identity dependency: ' + forbidden)
    # Prepare all mutations before writing, so failed anchors leave no partial patch.
    proxy.write_text(new_proxy)
    renderer.write_text(new_renderer)
    gradle.write_text(new_gradle)
    after = frozen_files(root)
    if after != before or sha(cpp) != CPP_SHA:
        raise RuntimeError('Frozen source/target path changed')
    proof = {
        'schema': 'RENDER2L_SOURCEPROXY1C_V1',
        'versionName': VERSION,
        'baseline': 'RENDER2K_SOURCEPROXY1B',
        'rendererNativeSha256': CPP_SHA,
        'sourceProxyJavaSha256': sha(proxy),
        'frozenFilesChecked': len(before),
        'frozenFilesManifestSha256': hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest(),
        'frozenFilesUnchanged': True,
        'sharedMeterAndAllocatorUnchanged': True,
        'port1aAndDngSaverUnchanged': True,
        'sameInputRendererCodeUnchanged': True,
        'sameRawPixelReplayPerformed': False,
        'currentFocalApertureInIdentity': False,
        'identityUsesSortedAvailableOptics': True,
        'identityIncludesStaticColorForwardCalibrationMatrices': True,
        'fullSha256Identity': True,
        'legacySeedsFixedOpticsOnly': True,
        'legacySeedsProvisionalNotFullSignatureValidated': True,
        'unknownSourceExponent': 1.0,
        'unknownIdentityIsNotTransferParityClaim': True,
        'automaticLearningEnabled': False,
        'hdrEnabled': False,
        'privateFixturesCommitted': False,
        'deviceValidated': False,
        'productionPromoted': False,
    }
    (root / 'M10R_RENDER2L_SOURCEPROXY1C_PROVENANCE.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps(proof, indent=2))

if __name__ == '__main__':
    main()
