# COLOURCACHE3H checkpoint

Current Android checkpoint: **1.39-m10r-colourcache3h-test**, version code **28901**.

The `overlay/` directory contains every changed or added source, resource and test
file relative to PhotonCamera commit `4ee108e169496f429c0afa0cc33e57bb6b2ec724`.
The manifest verifies all 1,178 assembled source/resource files. Historical app
experiments elsewhere in this repository are not this checkpoint's build input.

## Assemble and build

Use Python 3.12+, JDK 17, Android SDK 36 and build tools 35.0.0. Supply the delivered
`M10RCam_COLOURCACHE3H_TEST.apk` to recover the exact native payload used in testing:

```sh
python3 checkpoints/colourcache3h/prepare_project.py --apk /path/to/M10RCam_COLOURCACHE3H_TEST.apk
cd checkpoints/colourcache3h/PhotonCamera
chmod +x gradlew
./gradlew -Pm10rDetail3D=true :app:assembleDebug
```

The script checks the APK, upstream archive, source files and all 27 native-library
hashes. `--base-archive /path/to/base.tar.gz` supports an already downloaded pinned
base. Omit `--apk` for source inspection only. It will not overwrite an existing
output directory. No private photographs, full phone sidecars, APKs, build caches
or large upstream native dependency archives are committed here.

The exact prebuilt parent native libraries are intentionally retained. This is the
same build strategy as the delivered checkpoint; it does not rebuild every native
dependency. The new isolated colour library can be rebuilt for both ARM ABIs:

```sh
M10R_NDK=/path/to/android-ndk-r27c python3 checkpoints/colourcache3h/verification/build_native.py
```

The complete source-and-evidence ZIP delivered alongside the APK also contains
the full RAW replay fixtures, host test infrastructure and recorded unit-test
reports. See `REPORT.txt` for those reproduction commands and evidence limits.

## Included changes

- M10-R PHOTO/MOTION routing, one photographic RAW, no fusion/HDR.
- Current source calibration, exposure/preview work and saturation diagnostics.
- DETAIL3D experimental sharpening, disabled by default in source builds and
  enabled by the explicit flag used for the delivered test APK.
- RENDERPROFILE3E stage timing and RENDERPERF3F lens-shading/diagnostic optimization.
- NATIVENORM3G photographic native normalization with the previous Java fallback.
- COLOURCACHE3H exact RGB-key tone-calibration caching, bounded per worker/band,
  with native timing and cache statistics and the previous colour path as fallback.

`-Pm10rToneCache3H=false` selects the 3G colour control.
`-Pm10rNativeNormalize3G=false` selects the 3F Java normalization control.

## Validation status

The delivered build passed 337 JVM tests in 54 suites. Cache verification covered
all 16,777,216 RGB inputs with alpha variations and one million additional threaded
random cases. Old/new JNI output matched for 37,748,736 replay pixels and all
counter slots; production Java dispatch and fallback checks also passed.

NATIVENORM3G was validated in a PHOTO phone capture. COLOURCACHE3H has host and
build validation, but **phone validation remains pending**. MOTION still needs a
phone capture. The 15–21% colour-stage improvement is a host observation, not a
phone performance claim. No exact Leica hardware rendering parity is claimed.

The PR workflow verifies overlay hashes and runs the exhaustive native cache
test. It does not claim to rerun the Android suite or private RAW replays.
