# M10-R v2.70D — T1 closed; WORKING1A placement A/B built

Date: 2026-09-10
Status: DEVICE-GROUNDED / ONE BOUNDED PIXEL A/B

## 1. Device gate is now T1

The matching current-chat pair is:

- JPEG: `IMG_20260910_071015.jpg`
- diagnostics: `IMG_20260910_071015_M10R_CAPTURE1B.json`

The JPEG visibly retains the broad warm/yellow/amber concern in the tungsten/mixed indoor scene.

The sidecar simultaneously reports:

```text
sourceWhiteLevelClipCount = 0
neutralDomainClipCounts = [0,0,0]
m10rSyntheticAsShotNeutral = [0.3520715101905391,1,0.4085187552669846]
m10rCa9Gains = [727,256,627]
```

and the recovered reciprocal relation closes exactly after integer rounding:

```text
round(256 / synthetic_ASN) = [727,256,627]
```

Therefore:

```text
T1 = CONFIRMED
T2 = REJECTED_FOR_THIS_FRAME
T3 = REJECTED_FOR_THIS_FRAME
```

No guessed WB gain or CA9 clipping change is justified.

## 2. Structural mismatch selected for the bounded A/B

Frozen v2.32 architecture establishes:

```text
camera / scene-dependent entrance
 -> CC0
 -> fixed Leica internal working RGB
 -> tone / nonlinear stages
 -> CC1
 -> selected output RGB
```

The RENDER1F Android implementation instead precomposed the fixed internal-basis transform and `DEFAULT_SRGB_CC1` into one `targetToSrgb` matrix before MEDIUM/DG/Yc processing.

Because MEDIUM/DG is nonlinear, moving CC1 across that operation is not algebraically neutral.

For the exact firmware YC2A luma row:

```text
L = [1224,2403,469] / 4096
  = [0.298828125,0.586669921875,0.114501953125]
```

and the unchanged default sRGB CC1:

```text
[ 1.3895 -0.1693 -0.2202]
[-0.2288  1.2317 -0.0029]
[-0.0176 -0.0963  1.1139]
```

the old pre-nonlinear placement gives effective working-RGB luma weights approximately:

```text
[0.27897637,0.66098320,0.06004043]
```

instead of the firmware Y row. Delta:

```text
[-0.01985176,+0.07431328,-0.05446152]
```

This is a measurable scene-dependent discriminator, especially under warm spectra.

## 3. WORKING1A implementation

A/B branch:

```text
m10r-render1g-working1a-build
```

Base:

```text
m10r-render1f-diag1c-saf1-build @ 45314cd8f43a0c7ddfb739faf385100dc4bfbf87
```

Candidate workflow head:

```text
d54e64bc129c54c4d835df4e289b3b0a07750120
```

Only stage placement changes:

```text
source -> target camera -> CA9
 -> PCS_TO_INTERNAL / Leica internal working RGB
 -> exact YC2A Yc transform
 -> unchanged MEDIUM -> DG
 -> unchanged relative-chroma reconstruction
 -> unchanged DEFAULT_SRGB_CC1
 -> sRGB OETF
 -> unchanged edge stage
```

The JNI path now receives separate `targetToWorking` and `workingToSrgb` matrices. Sampled diagnostics were changed to observe the same preTone working domain and post-CC1 preSrgb domain as the native pixel path.

## 4. Frozen invariants

Unchanged:

```text
single RAW
HDR OFF
Xiaomi SOURCECM1A source model
scene-white / target profile construction
CA9 Q8 gains and clamp behavior
YC2A matrix = 1224,2403,469;-691,-1357,2048;2048,-1715,-333
MEDIUM tone asset
DG asset
LOOK1B relative-chroma policy
tone/DG coordinate arithmetic
SCALE1A / EDGE / HF gain behavior
Y_BLEND OFF
LF OFF
TEXTURE OFF
JPEG quality
12 MP output
DIAG1C SAF persistence
```

No coefficient was tuned from the JPEG.

## 5. Build result

Actions run:

```text
34453946900
```

Result:

```text
SUCCESS
```

Artifact:

```text
M10RCam-RENDER1G-WORKING1A-DIAG1C-SAF1-debug-apk
artifact id = 10142777422
sha256 = 2507cbd6177a1901ff916bd1ab6596e9a8bfe8afb2bdcc58c96783f63410cccb
```

Workflow hard guards proved the RENDER1F reconstruction first, rejected the old collapsed pre-tone CC1 expression, verified the new post-MEDIUM/DG CC1 expression, and preserved HDR-off / YC2A / edge / DIAG1C invariants.

## 6. Device test protocol

Do not promote WORKING1A yet.

Install WORKING1A and reproduce the same or closely matched tungsten/mixed-light scene. Preserve JPEG + `_M10R_CAPTURE1B.json`.

Judge against frozen RENDER1F/DIAG1C on:

1. broad yellow/amber bias in neutrals/skin/furnishings;
2. brightness/midtone change caused by the corrected nonlinear coordinate domain;
3. saturation and colour separation;
4. highlight channel behavior;
5. diagnostics: `preTone`, `preSrgb`, clipping counts, render identity.

Decision:

```text
WORKING1A materially improves T1 without new regressions -> promote placement architecture
WORKING1A changes tone but leaves amber residual -> keep placement if globally better; AWB selector remains separate OPEN gap
WORKING1A regresses colour/tone -> reject candidate; do not compensate with subjective WB
```

## 7. Current verdict

```text
T1_DEVICE_GATE = CLOSED_CONFIRMED
GENERIC_B2Y_TRACE = STILL_DEFERRED
AWB_SCENE_SELECTOR = OPEN
WORKING1A_STRUCTURAL_BASIS = FIRMWARE_GROUNDED
WORKING1A_BUILD = GREEN
WORKING1A_PHOTOGRAPHIC_PROMOTION = NOT_YET
NEXT_GATE = ONE_MATCHED_DEVICE_A/B
```
