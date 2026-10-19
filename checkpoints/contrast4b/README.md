# CONTRAST4B checkpoint

Android version **1.48-m10r-contrast4b-test**, version code **29007**.
The tested build requires **-Pm10rDetail3D=true**.

This checkpoint reconstructs the current 12 MP application over public
PhotonCamera commit 4ee108e169496f429c0afa0cc33e57bb6b2ec724. The overlay contains
each added or changed source, resource and test file. The manifest also records
removed upstream files and hashes every assembled file covered by the shared
snapshot policy.

The new photographic control is **Low / Standard / High contrast**. Standard
uses the existing firmware MEDIUM table. The same selected profile is carried
through still rendering, preview/exposure contexts and preview cache identity.
The exact table and scalar-operator checks have a narrower scope than complete
Leica hardware rendering parity; their reports retain that distinction.

## Verify the checkpoint

Use Python 3.12 or later:

~~~sh
python3 checkpoints/contrast4b/prepare_project.py --verify-only --require-apk-manifest
python3 checkpoints/contrast4b/wb_evidence/verify_bounded_wb4b.py
~~~

The first command checks all committed overlay and checkpoint evidence hashes.
It rejects a scaffold whose delivered-APK manifest is still pending. Read the
manifest's snapshotStatus and the recorded validation results before treating
a local work-in-progress snapshot as the delivered checkpoint.

## Assemble and build

Use JDK 17, Android SDK 36 and build tools 35.0.0. Supply the delivered
M10RCam_CONTRAST4B_TEST.apk to recover the exact 31 native libraries:

~~~sh
python3 checkpoints/contrast4b/prepare_project.py \
  --apk /path/to/M10RCam_CONTRAST4B_TEST.apk \
  --base-archive /path/to/photoncamera_4ee108e.tar.gz
cd checkpoints/contrast4b/PhotonCamera
chmod +x gradlew
./gradlew -Pm10rDetail3D=true :app:assembleDebug
~~~

The assembler checks the pinned upstream archive, each base file replaced or
removed, the complete assembled source inventory, the delivered APK digest and
every native library. Omit --base-archive to retrieve the pinned public archive.
Omit --apk for source inspection. A fresh --output directory can be supplied;
an existing output directory is never overwritten.

The native runtime follows the established checkpoint strategy: extract the
hash-verified payload from the delivered APK. It does not rebuild every upstream
native dependency. APK hashes bind a delivered artifact; the source reconstruction
does not promise a byte-identical signed APK across different local build tools.

Snapshot exclusions cover build state, unused ncnn static toolchain payloads,
native binaries, signing material, private photographs and full capture sidecars.
The hash-pinned upstream archive may contain its inherited public debug-signing
fixture and unused upstream tools; these are not committed in this checkpoint's
overlay or inventoried as application source.

## Exact contrast evidence

The table scripts write their validation results beside their fixtures. To keep
the committed evidence untouched, use a separate verification layout:

~~~sh
python3 checkpoints/contrast4b/prepare_project.py \
  --base-archive /path/to/photoncamera_4ee108e.tar.gz \
  --output /tmp/m10r-contrast4b-check/PhotonCamera
cp -R checkpoints/contrast4b/contrast_assets /tmp/m10r-contrast4b-check/contrast_assets
python3 /tmp/m10r-contrast4b-check/contrast_assets/generate_contrast_java.py --check
python3 /tmp/m10r-contrast4b-check/contrast_assets/verify_app_contrast4b.py
~~~

The small extracted table fixtures permit regeneration and verification without
shipping full firmware. The verifier checks the LOW/MEDIUM/HIGH payloads and the
unchanged differential-gamma payload, then evaluates all 20,480 supported integer
inputs per profile plus boundary inputs. LOW has unity tone gain; differential
gamma still applies. This check does not execute the settings UI, asynchronous
preview lifecycle or a physical phone.

The original extractor and frozen source reports are included for provenance.
The original full-firmware comparison script requires the separately identified
B2Y source section and baseline source recorded in its provenance file. The
portable application-table verifier above uses the committed small table fixtures.

The committed native-test resource contains **64 numeric sparse samples**, exact
input hashes and compressed table fixtures. It contains no photograph or full
capture sidecar. The optional prepare_native_probe_fixture4b.py --check generator
requires the original private DNG and sidecar locally under ../upload relative
to the checkpoint directory, together with the previously prepared host JNI
libraries under verification/shadow-build. Those inputs are excluded. The
committed resource is already available to the native test; regeneration is not
required to inspect or use the fixture. The samples do not claim full-RAW demosaic
or phone rendering parity.

## Bounded WB progress

The WB evidence preserves two source-linked IR/ExtBv observations from authentic
public Leica JPEG metadata and identifies both current target ColorMatrix
coefficient sets in the checksum-verified firmware baseline calibration record.
The JSON retains the exact inline descriptor bytes, coefficient words, hashes,
source references and version qualifications. It includes no full phone sidecar,
private RAW/JPEG, native binary or full firmware.

The portable WB verifier checks those bounded records and reconstructs the
132-byte calibration record in memory. It does not rerun original firmware or
recheck omitted original image files. Photographic WB authority remains at its
existing boundary; phone statistics scale, resident-bank/profile identity and
Android IR/ExtBv semantics remain separate calibration questions.

## Recorded build and release checks

The final build record and release review are under results. The actual JUnit
outputs comprise **95 tests in 15 suites**, with zero failures, errors or skipped
tests. Sixteen are the new contrast tests. A requested M10RWbSelector3YTest filter
matched no source class and did not execute; it is explicitly qualified in the
release review and is not counted as a passing WB test.

The release review binds the delivered APK identity, checks its public signing
certificate against the 4A baseline, records DETAIL3D=true, and verifies that all
31 native libraries and all 279 packaged assets match that baseline. The helper
under verification can repeat those checks with the specified APKs, SDK/JDK,
completed build record and JUnit outputs. It does not run Gradle or access a
private signing keystore.

Exported evidence uses relative or descriptive path labels. Original and
exported evidence hashes are preserved in results/evidence_exports.json; the
application overlay itself is copied byte for byte.

## Regenerate a frozen checkpoint

The generator is included under verification. Use an assembled, tested project,
the pinned upstream archive and the delivered APK, and write a fresh directory:

~~~sh
python3 checkpoints/contrast4b/verification/make_checkpoint4b.py \
  --project /path/to/frozen/PhotonCamera \
  --base-archive /path/to/photoncamera_4ee108e.tar.gz \
  --contrast-assets checkpoints/contrast4b/contrast_assets \
  --wb-evidence checkpoints/contrast4b/wb_evidence \
  --apk /path/to/M10RCam_CONTRAST4B_TEST.apk \
  --output /tmp/m10r-contrast4b-regenerated
~~~

The generator checks source stability during collection. It requires the expected
version identity, records the explicit DETAIL3D build property, and inventories
the native runtime only from the supplied APK. Optional --result-file and
--report-file arguments attach the final reviewable validation records. The
--verification-script option includes a portable Python review helper.

If --github-base-tree supplies a complete saved repository tree, the generator
also writes an upload plan outside the checkpoint. It compares exact Git blob
SHA1 values, provides tree entries with UTF-8 content or reusable blob identities,
and separates new binary payloads. It reports bytes and flags any new binary
larger than 1 MB. Generating this plan performs no GitHub write.
