# EXPOSURE1C integration checkpoint — 5 October 2026

This branch does not contain an exposure-enabled APK. The production/capture branch and existing AMaZE/color/tone code have not been changed.

## Completed in this continuation

- Recovered the September 30 UPSTREAM1A RAW16 overlay from the user's supplied Library recovery archive, locally only.
- Reconstructed Photon at 4ee108e169496f429c0afa0cc33e57bb6b2ec724 and applied that overlay locally. All 1,120 recorded baseline source-file SHA-256 values matched.
- Prepared two new local Java drafts: M10RExposureAndroid1C (copy a timestamp-matched RAW frame into owned memory before releasing the camera Image) and M10RExposureCamera1C (request-tagged shutter-time measurement, exact result/image association, cancellation, and guarded continuation).
- Compiled the drafts against minimal Android API stand-ins. This is only Java compilation, NOT Android compilation, integration validation, or a phone test. No callback test cases had been executed at this checkpoint.
- Built the unchanged public FIX1 parent on Actions solely to recover offline Android build prerequisites; run 37321071317 succeeded. This is NOT an exposure build.
- Split the prerequisite artifact into parts below the connector's 512 MiB download limit; run 37322776900. Only already-public source/toolchain inputs were used. The private September 30 overlay was not published.

## Execution interruption

After retrieving source archives and the two Android toolchain parts, every local container/Python execution attempt returned an infrastructure ClientError. The complete local app integration and Android build were therefore not executed. Do not infer that the recovered SDK is installed or that an exposure APK exists.

Last confirmed workspace:

- /mnt/data/m10r_exposure1c/PhotonCamera — reconstructed September 30 app, 1120 hashes checked, before exposure module installation.
- /mnt/data/m10r_exposure1c/baseline/RECONSTRUCTION_RECEIPT.json
- /mnt/data/m10r_exposure1c/M10R_EXPOSURE1B_20261005 — previous complete RAW/native exposure-probe package.
- /mnt/data/m10r_exposure1c/integration/src/com/particlesdevs/photoncamera/m10r/M10RExposureAndroid1C.java
- /mnt/data/m10r_exposure1c/integration/src/com/particlesdevs/photoncamera/m10r/M10RExposureCamera1C.java
- /mnt/data/m10r_exposure1c/integration/test_camera.py — minimal API compile harness, without callback test cases yet.
- /mnt/data/m10r_exposure1c/offline — source archives and expected prerequisite hashes.

Recovery artifact identifiers:

- M10R-E1C-SOURCES: 11350548498 (already downloaded as E1C_sources.zip).
- M10R-E1C-ANDROID-00: 11351166198 (already downloaded as E1C_android00.zip).
- M10R-E1C-ANDROID-01: 11350928137 (already downloaded as E1C_android01.zip).
- M10R-E1C-GRADLE-00: 11350153715 (not downloaded).
- M10R-E1C-GRADLE-01: 11350348565 (not downloaded).
- M10R-E1C-GRADLE-02: 11350568506 (not downloaded).

Before activation, review callback ownership including image-before-start, late images after timeout, controls/lens/session changes, duplicate events, out-of-memory during RAW copy, and forwarding ordinary RAW images without changing Photon's save/ZSL ownership. The draft is not yet a proven camera interceptor. Compile against the real Android SDK rather than relying on API stand-ins.

Next: restore execution, verify and unpack the remaining prerequisites, install the exact EXPOSURE1B modules on the verified UPSTREAM1A tree, finish the capture-controller and ISO/shutter freeze connections, add executable callback/ownership tests, then compile and inspect the APK. Keep the target native renderer and AMaZE FIX1 byte-identical. Do not publish the unpublished recovery overlay or private captures as a workaround.

The proposed first candidate uses one unsaved metering RAW before one photographic RAW, with no fusion/stacking. Its latency must be stated explicitly. It limits extra positive automatic assistance, not already-clipped sensor recovery or complete baseline-overexposure correction. The viewfinder's photographic transform is not changed by this step. No additional user photos are needed before integration/build.
