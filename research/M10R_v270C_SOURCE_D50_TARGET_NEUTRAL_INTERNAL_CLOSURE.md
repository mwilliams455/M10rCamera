# M10-R v2.70C — Source D50 + target-neutral internal closure

Date: 2026-09-10
Status: RESEARCH-ONLY / NO PIXEL CHANGE / NO APK
Parent: `research/M10R_v270B_DEVICE_WB_GATE_NUMERIC_CLOSURE.md`

## Purpose

Use the Sept-10 device sidecar `IMG_20260910_071015_M10R_CAPTURE1B.json` to test one additional renderer-relevant discriminator before the visual JPEG gate:

> Are the recorded Xiaomi source neutral, source sensor->XYZ D50 transform, scene-white state and synthetic M10-R neutral internally inconsistent in a way that can already explain the warm-render concern?

This is a bounded arithmetic audit of the exact recorded state. It is not a claim that Xiaomi's AWB selected the physically correct scene illuminant.

---

## 1. Recorded state

```text
sourceSensorNeutral = [0.6025390625, 1.0, 0.3876953125]
sourceInterpolationFactor = 0.5780919564532268
sceneWhiteXY = [0.40806447946570246, 0.4329644967886003]
sceneCctKelvinLeicaLocus = 3747.056631039559
m10rSyntheticAsShotNeutral = [0.3520715101905391, 1.0, 0.4085187552669846]
m10rCa9Gains = [727, 256, 627]
```

Recorded source sensor->XYZ D50 matrix:

```text
[ 1.0538088083267212,   0.10974633693695068,  0.5661473274230957 ]
[ 0.3630470335483551,   0.7578125,             0.060453400015830994 ]
[-0.06457735598087311, -0.4513603448867798,   3.3922789096832275 ]
```

---

## 2. Source-neutral -> D50 closure

Apply the recorded source transform directly to the recorded sensor neutral:

```text
sourceSensorToXYZD50 * sourceSensorNeutral
= [0.96419997, 1.00000002, 0.82489991]
```

Normalize to Y=1:

```text
= [0.96419996, 1.00000000, 0.82489989]
```

Reference D50 from the renderer constant xy=(0.3457, 0.3585):

```text
D50 XYZ(Y=1) = [0.96429568, 1.00000000, 0.82510460]
```

Converted recorded result back to xy:

```text
x = 0.3457029178
y = 0.3585386164
```

Difference from renderer D50 xy:

```text
dx = +0.0000029178
dy = +0.0000386164
```

Normalized XYZ relative errors are approximately:

```text
X: -0.00993%
Y:  0.00000%
Z: -0.02481%
```

### Verdict

```text
SOURCE_SENSOR_NEUTRAL_TO_D50_INTERNAL_CLOSURE = STRONG
SOURCE_ADAPTER_GROSS_MATRIX_NEUTRAL_MISMATCH = REJECTED_FOR_THIS_FRAME
```

The recorded source transform maps its own recorded camera neutral essentially onto D50, as expected for the Camera2/Photon D50-adapted source transform. There is no gross matrix/neutral inconsistency here that would explain a large yellow cast by itself.

Important limitation: this proves internal consistency, not physical AWB correctness. If `CaptureResult.SENSOR_NEUTRAL_COLOR_POINT` itself selected the wrong real-scene illuminant, this closure would still hold because the D50 transform is constructed from that neutral.

---

## 3. Scene-white -> synthetic M10-R neutral closure

Recorded scene white:

```text
xy = [0.40806447946570246, 0.4329644967886003]
XYZ(Y=1) = [0.94248947, 1.00000000, 0.36716873]
```

For recorded Leica-locus CCT:

```text
T = 3747.056631039559 K
```

the renderer's reciprocal-temperature interpolation between the M10-R Standard-A and D65 profile matrices produces weight:

```text
g = (1/T - 1/6504) / (1/2856 - 1/6504)
  = 0.5760245082637195
```

The interpolated target matrix applied to scene-white XYZ yields raw target-camera neutral:

```text
[0.36636961, 1.04061136, 0.42510926]
```

Normalize green to 1:

```text
[0.35207151, 1.00000000, 0.40851876]
```

which reproduces the sidecar's:

```text
m10rSyntheticAsShotNeutral =
[0.3520715101905391, 1.0, 0.4085187552669846]
```

to displayed precision.

Together with v2.70B's exact integer reciprocal closure:

```text
round(256 / ASN) = [727, 256, 627]
```

this closes the current host-side chain numerically:

```text
recorded scene white
 -> reciprocal-temperature M10-R profile interpolation
 -> synthetic M10-R ASN
 -> reciprocal-Q8 CA9 gains
```

### Verdict

```text
TARGET_PROFILE_INTERPOLATION_INTERNAL_CLOSURE = PROVEN_FOR_RECORDED_STATE
SYNTHETIC_ASN_DERIVATION_INTERNAL_CLOSURE = PROVEN_FOR_RECORDED_STATE
CA9_GAIN_DERIVATION_INTERNAL_CLOSURE = PROVEN_FOR_RECORDED_STATE
```

---

## 4. Interpolation-factor observation

The Xiaomi source interpolation factor is:

```text
0.5780919564532268
```

The M10-R reciprocal-temperature profile weight derived independently from the recorded scene CCT is:

```text
0.5760245082637195
```

Difference:

```text
+0.0020674481895073
```

These factors belong to different camera characterization systems and are not required to be identical. Their close numerical agreement is therefore only a coherence observation, not proof of shared arithmetic.

Verdict:

```text
SOURCE_VS_TARGET_WARM_DAYLIGHT_POSITION = COHERENT_OBSERVATION_ONLY
```

---

## 5. What this eliminates and what it does not

For this frame, the device gate now rejects these simple implementation-fault explanations:

```text
- source-white clipping
- CA9 neutral-domain clipping
- synthetic ASN <-> CA9 reciprocal-Q8 mismatch
- gross source sensor-neutral <-> D50 transform inconsistency
- target-profile interpolation / synthetic-ASN arithmetic mismatch
```

Still OPEN:

```text
A. Was Xiaomi SENSOR_NEUTRAL_COLOR_POINT physically correct for this warm scene?
B. Does the matching JPEG still show the broad yellow/amber concern?
C. If B=yes while A is plausible, is a downstream ColorSpec/D50 -> rendered working-basis seam missing or mis-modeled?
```

The sidecar alone cannot answer A or B.

---

## 6. Gate state

```text
T2_NEUTRAL_CLIPPING = REJECTED_FOR_THIS_FRAME
T3_INTERNAL_WB_REPRESENTATION_MISMATCH = REJECTED_FOR_THIS_FRAME
SOURCE_ADAPTER_GROSS_INTERNAL_MISMATCH = REJECTED_FOR_THIS_FRAME
TARGET_SYNTHETIC_NEUTRAL_ARITHMETIC = CLOSED_FOR_RECORDED_STATE
T1_VS_T4 = WAITING_FOR_MATCHING_JPEG / EXACT-FRAME VISUAL CONFIRMATION
```

If the exact JPEG still shows the broad warm/yellow concern, proceed to T1 and design exactly one bounded ColorSpec/D50 -> fixed rendered working-basis A/B. If the JPEG does not reproduce the concern, classify T4 and freeze WB.

---

## 7. Project guardrail

```text
NEW APK = NO
NEW WB GAIN STAGE = NO
GENERIC B2Y TRACE = NO
Y_BLEND CHANGE = NO
TONE/DG CHANGE = NO
EDGE CHANGE = NO
```

The next useful evidence is photographic, not another unrestricted firmware excavation.
