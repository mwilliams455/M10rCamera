# M10-R contrast integration: assets and 4A source observations

## Delivered assets

The three still profiles are firmware enum 1 LOW, 2 MEDIUM, 3 HIGH. MEDIUM is the recovered factory default and is the existing app table; the user-facing label is Standard. Values 4, 5 and 6 select VIDEOLOW, VIDEOMEDIUM and VIDEOHIGH, not intermediate still levels.

Each table contains 10,240 little-endian uint32 Q15 gains (40,960 bytes). Both firmware banks have identical active payloads for each profile. The second bank is not a second sequential tone operation.

| Profile | SHA-256 |
| --- | --- |
| LOW | 136b69127e73cc43c28c0aa7b511f1f3e9b29be139f4d491422f2eb574a49fb0 |
| MEDIUM | 2fd6ca209f290c75aa96976b3d7692e55c41a55c0017a063aba9808da3b41a00 |
| HIGH | 0a764cf29d35cd4a4eb7f816e5d128bccaef81b4d5eca991d9b80ab207bd0101 |

The extracted MEDIUM and expanded differential-gamma table are byte-for-byte identical to the embedded tables in the restored 4A M10RToneDg1A.java. LOW is unity at the tone-gain stage; the unchanged differential-gamma stage still runs.

Source B2Y section SHA-256: ea935a8006ea3b0a765660bd1d89f6a52c9f60508ee5ba76650005d80372335b. The exact extractor and five copied frozen reports match immutable repository commit f93072b7d588e14329704a73ba64874cc16f0cf3. Source URLs, payload locations and hashes are in provenance.json and verification.json.

## Generated app class

Only this new app file was written by the asset subtask:

app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RContrastTables4B.java

It exposes package-private static int[] low() and high(), with lazy holders through M10RToneDg1A.decode32. It also exposes LOW_SHA256 and HIGH_SHA256. MEDIUM stays in M10RToneDg1A and is not duplicated. Callers and native renderers must treat returned arrays as read-only.

Compression uses gzip level 9 with mtime 0, no filename, and OS byte 255. LOW compresses to 77 bytes; HIGH to 8,039 bytes. Repeated generation produces identical Java source.

## 4A integration points observed before the main integration

- M10RNativeRenderer freezes nativeToneTable once before the row-band loop (line 385). That array already reaches the active 3I path, the 3H fallback, and the inherited native fallback. No JNI signature change is needed.
- M10RExposureNative1B.Context.render separately requests the existing MEDIUM table (line 62). Store the selected profile in the immutable Context and retain it across withRenderedColor copies so preview and exposure probes use the same choice as still rendering.
- M10RPreviewColour1A.Frame.matches matches owner, camera key, submitted controls and white-balance key (lines 138–140). Profile changes need equivalent cache identity/generation protection, including asynchronous build publication. Otherwise a still-valid old Standard preview LUT can be reused after switching to Low or High.
- M10RNativeRenderer toneAssetSha256 (line 291) and the Java counterfactual tone operator (line 495) also need the selected profile, so diagnostic output remains consistent with the actual native table.
- Native 3I's tone-calibration cache is private per worker per band and keyed by exact RGB24 after the tone/gamma/colour stages. It therefore does not require a new persistent contrast key. The already-frozen per-band LUT parameter is sufficient.
- Photon’s global getContrastValue / KEY_CONTRAST_SEEKBAR is a generic floating-point multiplier. It has no recovered mapping to these three firmware choices. A dedicated three-state setting avoids silently treating a generic 0–3 scalar as the firmware enum.

These are observations of the restored baseline, not a claim that the main integration is still missing them.

## Verification and curve interpretation

Run from any directory:

    python contrast_assets/generate_contrast_java.py --check
    python contrast_assets/verify_app_contrast4b.py

The post-edit validator permits normal changes to M10RToneDg1A source while requiring its embedded MEDIUM and DG bytes to keep their 4A hashes. It independently checks LOW/HIGH against frozen hashes and extracted bytes, evaluates all 20,480 integer inputs per profile plus four extreme boundary inputs, and verifies monotonicity and zero DG input clamping. The settings default and asynchronous lifecycle are application integration gates, not executed by the asset validator.

tone_curve_samples.csv contains representative points. tone_curve_full_domain.csv contains all 20,480 input rows. Both evaluate the existing scalar model:

    xx = clamp(x, 0, 20479)
    tone = (xx * table[xx >> 1]) >> 15
    scalar_output = dg[clamp(tone, 0, 32767)]

The current app normalizes/clamps tone input to 0–16,383. Inputs above 16,383 are retained in the comparison to check the complete LUT domain, not to claim the app exposes extra RAW headroom.

| Input x | Approximate fraction of 16,383 | LOW scalar tone → DG | MEDIUM scalar tone → DG | HIGH scalar tone → DG |
| --- | --- | --- | --- | --- |
| 164 | 1% | 1606 | 1006 | 840 |
| 819 | 5% | 5247 | 4670 | 3730 |
| 1638 | 10% | 7915 | 8001 | 8089 |
| 2949 | 18% | 10691 | 11036 | 11363 |
| 4096 | 25% | 12182 | 12344 | 12523 |
| 8192 | 50% | 14423 | 14477 | 14535 |
| 12287 | 75% | 15640 | 15693 | 15733 |
| 16383 | 100% | 16383 | 16383 | 16383 |

HIGH produces lower deep-shadow values and higher values through much of the middle range in this scalar model; black and white endpoints remain shared. All three complete curves are nondecreasing. The comparison excludes source/working/output colour matrices, common-luma RGB reconstruction, output gamut, empirical ToneCal and detail. It does not predict a complete final JPEG or establish exact Leica ASIC normalization, rounding or routing.
