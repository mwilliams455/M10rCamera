# M10-R v2.67 — WB ColorSpec D50 / B2Y closure

Date: 2026-09-09

## Scope

This is a research-only checkpoint. It does not modify the Android renderer or any frozen photographic stage.

Keep frozen:

- `m10r-capture1b`
- `RENDER1F / YC2A / MATRIX1A / DIAG1A`
- MEDIUM / DG
- SCALE1A / EDGE1A / GAIN1A
- Y_BLEND OFF
- LF OFF
- TEXTURE OFF
- HDR OFF

The purpose of this note is to refine the WB-B/reference-basis hypothesis from handoff v2.66.

---

## 1. New high-confidence architectural comparison

Recovered M10-R CA9 ColorSpec behavior already includes:

- `NeutralToXY`
- `SetWhiteXY`
- `MapWhiteMatrix`
- `FindXYZtoCamera`
- reciprocal-temperature interpolation between dual illuminant color matrices
- Bradford-type chromatic adaptation
- a D50-like fallback white near `(0.3457, 0.3585)`

A comparison against the public Adobe DNG SDK `dng_color_spec` topology shows an unusually close structural match.

The DNG SDK sequence is conceptually:

```text
camera neutral
-> NeutralToXY
   - initialize at D50
   - FindXYZtoCamera(current xy)
   - invert XYZ->camera
   - map neutral back to XYZ/xy
   - iterate to convergence
-> SetWhiteXY(scene xy)
   - FindXYZtoCamera(scene xy)
   - cameraWhite = colorMatrix(scene) * XYZ(scene white)
   - normalize cameraWhite
   - PCStoCamera = colorMatrix(scene) * MapWhiteMatrix(D50, scene white)
   - if no ForwardMatrix: CameraToPCS = inverse(PCStoCamera)
```

The recovered M10-R firmware follows the same distinctive ingredients and ordering closely enough that the leading interpretation of `MapWhiteMatrix` should now be:

```text
D50 PCS white -> selected scene white
```

followed by inversion in the camera->PCS construction where appropriate.

### Status

This is not proof that Leica literally compiled the Adobe DNG SDK source unchanged.

It is strong structural evidence that M10-R `MapWhiteMatrix` is a DNG-ColorSpec-style PCS adaptation operation, not by itself a hidden Standard-A camera-reference bridge.

---

## 2. Correction to the v2.66 reference-basis hypothesis

The v2.66 M11 cross-map correctly identified a high-value question:

```text
Does M10-R normalize scene white into a fixed/reference basis before fixed rendering matrices?
```

The new comparison narrows the answer.

For the CA9 ColorSpec layer itself, the current leading topology is:

```text
selected scene white
-> reciprocal-T interpolated M10-R ColorMatrix
-> Bradford D50 PCS <-> scene-white adaptation
-> M10-R camera <-> D50 PCS transform
```

Therefore do NOT implement `MapWhiteMatrix` as:

```text
inverse(T_standard_A) * T_scene
```

or copy the M11 Standard-A-like bridge.

M11 H1 remains useful as a family-level structural clue that downstream Leica matrices may consume a normalized basis, but M10-R CA9 `MapWhiteMatrix` now points specifically toward PCS/D50 normalization.

A separate downstream fixed Leica working/reference basis may still exist after CameraToPCS. That is a different question and must be proven from M10-R consumers such as rendered CC0/CC1/B2Y, not inferred from `MapWhiteMatrix` alone.

---

## 3. Exact numerical closure: AsShotNeutral and B2Y Q8 gains

For the genuine M10-R DNG sample previously inspected:

```text
AsShotNeutral =
[0.3672883788, 1.0, 0.5791855204]
```

The recovered B2Y direct-WB Q8 values are:

```text
[R, G1, G2, B] = [697, 256, 256, 442]
```

The relationship is numerically exact to the displayed DNG precision:

```text
256 / 697 = 0.367288378766...
256 / 256 = 1.0
256 / 442 = 0.579185520362...
```

Therefore:

```text
AsShotNeutral ~= [256/R_gain_q8, 256/G_gain_q8, 256/B_gain_q8]
```

and conversely:

```text
B2Y direct WB gain ~= round(256 / AsShotNeutral)
```

This is stronger than the earlier statement that the values merely looked related.

---

## 4. Join with v1.32 callback evidence

The previously frozen `ca9_cm_ColorManagementFinished` callback exports three doubles at:

```text
source +0xB8 : R high-level gain/white value
source +0xC0 : G high-level gain/white value
source +0xC8 : B high-level gain/white value
```

and remaps each with:

```text
round(256.0 / value)
```

The exact genuine-DNG closure above strongly suggests that these high-level doubles are in the same normalized camera-white / neutral representation used for DNG `AsShotNeutral`, while the reciprocal Q8 values are the hardware-friendly direct-WB gains.

### Important wording discipline

Until the producer of `+0xB8/+0xC0/+0xC8` is traced instruction-by-instruction, do not rename those doubles universally as `AsShotNeutral` fields.

The currently justified statement is:

> The callback high-level white/gain values, genuine DNG AsShotNeutral, and B2Y Q8 direct gains are linked by an exact reciprocal-256 relationship in the inspected M10-R sample.

---

## 5. Updated WB-B working model

The strongest current M10-R-specific model is now:

```text
selected camera neutral / scene white
-> NeutralToXY
-> reciprocal-temperature CM interpolation
-> SetWhiteXY
-> cameraWhite / neutral representation
-> Bradford D50 PCS <-> scene-white mapping
-> camera <-> D50 PCS transform

and, through a hardware-realization path:

cameraWhite / neutral
-> reciprocal * 256
-> B2Y direct R/G/G/B Q8 WB gains
```

This does NOT yet prove whether the B2Y gain application occurs before, after, or as the physical realization of the exact camera->PCS matrix operation in the rendered pixel path.

Do not apply both software WB and Q8 gains in a future renderer merely because both representations exist. Their ownership/order must be traced first or the result could double-apply white balance.

---

## 6. Consequence for the current Android renderer

The current renderer path:

```text
Xiaomi RAW
-> Xiaomi source adapter
-> XYZ D50
-> synthetic M10-R scene target camera basis
-> CA9 neutral clip
-> inverse target/output transform
-> downstream render
```

still deserves scrutiny because its target-camera entry and later inversion can cancel scene-dependent behavior.

However the next replacement candidate should NOT yet be called a `Standard-A reference-basis bridge`.

The evidence-backed candidate to test first is a faithful M10-R ColorSpec/D50 bridge whose algebra is explicitly compared with the current route:

```text
Xiaomi scene-referred XYZ D50
-> M10-R scene ColorMatrix / selected white construction
-> exact M10-R camera-white / headroom behavior where required
-> M10-R D50 PCS normalization
-> proven downstream M10-R rendering basis
```

The remaining missing seam is the consumer that turns the CA9/D50 result into the fixed rendered CC0/B2Y input basis.

---

## 7. Next static tasks

Priority order:

1. Trace the exact two white operands at the M10-R `MapWhiteMatrix` call and confirm operand order against the D50->scene interpretation.
2. Trace production of callback doubles `+0xB8/+0xC0/+0xC8` back into `SetWhiteXY` / camera-white state.
3. Trace the reciprocal-256 result forward to the proven B2Y Q8 registers.
4. Determine whether those B2Y gains are the physical realization of WB already represented by ColorSpec, or an additional stage with different data ownership.
5. Trace the `CameraToPCS`/equivalent result forward to rendered CC0/CC1 and identify the fixed downstream working basis.
6. Only then build a controlled WB-B A/B.
7. Separately continue WB-A by tracing the producer of the selected camera neutral/xy for Auto WB.

---

## 8. Empirical gate remains unchanged

Before a pixel change, use the existing DIAG1A build for one controlled tungsten capture and preserve JPEG + matching JSON.

Priority fields remain:

```text
sourceSensorNeutral
sourceInterpolationFactor
sourceSensorToXYZD50
sourceWhiteLevelClipCount
neutralDomainClipCounts
m10rCa9Gains
sceneWhiteX
sceneWhiteY
sceneCctKelvinLeicaLocus
m10rSyntheticAsShotNeutral
```

If `neutralDomainClipCounts` are zero/negligible, CA9 clipping remains unable to explain a broad yellow/amber midtone cast.

---

## 9. Current verdict

```text
WB_B_MAPWHITE_D50_PCS_LEADING
ASN_B2Y_Q8_RECIPROCAL256_EXACT_SAMPLE_CLOSURE
FIXED_STANDARD_A_CAMERA_BASIS_NOT_PROVEN_FOR_M10R_CA9
NO_RENDERER_CHANGE_YET
```

The M11 cross-project result remains valuable, but the M10-R firmware now supports a more specific interpretation: its CA9 white-domain machinery is strongly consistent with DNG-style D50 PCS normalization, and the high-level camera-white/neutral representation is numerically tied to B2Y Q8 direct-WB gains by the exact reciprocal-256 relationship.