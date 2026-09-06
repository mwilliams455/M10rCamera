# RENDER_PARITY1A — genuine M10-R DNG factorial evidence (2026-09-06)

## Scope

This note records measurements from five user-supplied genuine Leica M10-R DNGs. It is evidence for the controlled RENDER_PARITY1A 2x2 experiment only. It does **not** claim that either candidate mechanism is final Leica firmware parity.

Authoritative matrix:

- A = RAW headroom OFF, CA9 neutral-domain clip OFF
- B = RAW headroom ON, CA9 neutral-domain clip OFF
- C = RAW headroom OFF, CA9 neutral-domain clip ON
- D = RAW headroom ON, CA9 neutral-domain clip ON

Everything else remains frozen: CFA interpretation, DNG black/white metadata, bilinear diagnostic demosaic, AsShotNeutral/CA9 gain recovery, NeutralToXY/ColorSpec and final display conversion.

## Common DNG structure

All five files identify as LEICA M10-R and contain a 7872x5208 CFA image (40,997,376 samples), Compression=7 lossless JPEG, DNG WhiteLevel=15000, BlackLevel=0 and CFA GBRG. The embedded SOF3 stream is 14-bit, predictor 1, point transform 0, encoded as 3936x5208 with two 1x1 components; `DngRawDecoder` expands the two interleaved components back to the 7872-sample Bayer row.

## Fixture identities and raw headroom

| File | SHA-256 | CA9 gains from AsShotNeutral | CFA samples >15000 | Fraction >15000 |
|---|---|---:|---:|---:|
| 7233386414.dng | b03ab4fdc8a5ce2ab6341721712950e546e97cb7e68776d7e4315ba1de6d5126 | [851,256,387] | 127 | 0.0003098% |
| 2534813740.dng | 2b0aee07897923ae161eb04cf4b38f3c385916f86ba42ede7b57e65da806fadd | [819,256,394] | 1,223,536 | 2.9844251% |
| 2513472276.dng | 27c17364fc10c264055a7cf32139ca60d4c5ce95e90e51f1c815d363ff3bbbd8 | [851,256,387] | 541,142 | 1.3199430% |
| 7976840085.dng | c8526e5f2466c2004db431ddf55a16dcaeb30f45e745b94375066ead390c5c75 | [851,256,397] | 935,801 | 2.2825875% |
| 9406796331.dng | c68b74514002ecc07deeb53d85e39d98a855b0af504621112d2767605724e5bd | [840,256,387] | 483,817 | 1.1801170% |

Four of the five reach the 14-bit maximum 16383. `7233386414.dng` is the useful near-zero-headroom control; `2534813740.dng` is the strongest headroom fixture in this set.

### Correction to an earlier exploratory count

An earlier scratch decode understated the high tail and incorrectly nominated `7976840085` as the strongest fixture and `9406796331` as the control. That result is superseded. The table above was recomputed after matching the repository `LosslessJpegDecoder` predictor/component semantics and checking the DNG strip metadata.

## Exact candidate equations used

RAW normalization follows the repository code:

- headroom OFF: `clamp01((sample - black) / (white - black))`
- headroom ON: `max(0, (sample - black) / (white - black))`

Recovered CA9 saturation follows the repository code exactly for each camera channel `c`:

`balanced = camera[c] * gain[c] / 256`

If `balanced > 1`, clamp it to 1, then return to camera domain with `balanced * 256 / gain[c]`.

The resulting camera-domain clip thresholds in these fixtures are therefore approximately R=0.301–0.313, G=1.0 and B=0.645–0.661. This is important: the CA9 candidate is not intrinsically restricted to samples above DNG WhiteLevel; it can alter red/blue camera-domain values well below 1.0.

## Factorial measurements at the diagnostic renderer's 1600-max-dimension sampling

For 7872x5208 input the existing renderer uses source stride 5, producing 1575x1042 = 1,641,150 diagnostic pixels. `changed pixels` below means at least one camera-domain channel differs between the pair before the unchanged ColorSpec transform.

| File | A→B headroom changed | A→C CA9 changed | B→D CA9 changed | C→D headroom with CA9 changed |
|---|---:|---:|---:|---:|
| 7233386414 | 16 (0.000975%) | 46 (0.002803%) | 46 (0.002803%) | 10 (0.000609%) |
| 2534813740 | 74,371 (4.5316%) | 86,009 (5.2408%) | 86,009 (5.2408%) | 2,112 (0.12869%) |
| 2513472276 | 32,847 (2.0015%) | 33,562 (2.0450%) | 33,745 (2.0562%) | 2,930 (0.17853%) |
| 7976840085 | 74,140 (4.5176%) | 98,497 (6.0017%) | 98,764 (6.0180%) | 3,261 (0.19870%) |
| 9406796331 | 35,147 (2.1416%) | 48,477 (2.9538%) | 48,812 (2.9743%) | 1,998 (0.12174%) |

## Interpretation

1. **RAW headroom is real and scene-dependent.** In four highlight-rich fixtures, preserving values above WhiteLevel changes roughly 2.0–4.5% of diagnostic pixels before ColorSpec. The near-zero-headroom control is essentially unchanged.
2. **The CA9 neutral-domain clip is also a strong independent intervention.** In the four highlight-rich fixtures it changes roughly 2.0–6.0% of diagnostic pixels. Because the recovered red/blue thresholds are below 1.0, this candidate is not a pure `>WhiteLevel` highlight guard.
3. **CA9 removes most of the effect of retained RAW headroom.** C→D falls to only about 0.12–0.20% changed pixels in the four strong fixtures, compared with about 2.0–4.5% for A→B. The mechanisms therefore interact strongly rather than behaving as two fully independent additive corrections.
4. This interaction is mechanically expected: values retained above 1.0 by B are frequently clipped again when D enters the CA9 gain domain. Some residual difference survives, principally through bilinear green interpolation around saturated CFA sites.
5. These measurements establish causal significance, **not photographic correctness**. A paired in-camera Leica JPEG (or stronger firmware stage-order evidence) is still needed to choose which cell best represents M10-R rendering rather than merely which cell changes the data.

## Development consequence

Keep WBCLIP/F82F parked. Continue RENDER_PARITY1A with the explicit canonical A/B/C/D matrix. Do not blend the two candidate mechanisms into a production renderer yet. The strongest next photographic test is to compare the four rendered cells from `2534813740.dng` and `7976840085.dng` against genuine paired Leica JPEGs if available, with `7233386414.dng` retained as the negative/control fixture.
