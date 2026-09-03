# M9 PROJECT HANDOFF v2.76
## M10-R CROSS-GENERATION EXPOSURE FINDINGS / VIRTUAL-BV NEXT

**Date:** 2026-09-03  
**Predecessor:** `M9_PROJECT_HANDOFF_v2_75_SCENEEXPOSURE1H_CAPTURE_RENDER_SPLIT.md`  
**Cross-project research source:** `mwilliams455/M10rCamera`  
**M10-R research baseline:** `research/M10R_EXPOSURE_ENGINE_v0_01.md`  
**M10-R exposure research commit:** `7ab0983b5106671a9830e34cfa634230ef04e9a7`

---

# 1. PURPOSE OF THIS HANDOFF

This handoff records an important change in the **direction of the M9 exposure investigation** based on independent reverse engineering of Leica M10-R firmware.

The M10-R work does **not** replace the M9 exposure model and does **not** justify copying M10-R constants or exposure behavior directly into M9Cam.

Instead, the M10-R firmware provides a newer Leica reference implementation that strongly confirms the exposure architecture already recovered from the M9 firmware:

- Leica exposure is fundamentally solved in an **APEX / EV domain**.
- Scene brightness is represented as **BV**.
- ISO is represented as **SV**.
- shutter is represented as **TV**.
- aperture is represented as **AV** where available.
- user exposure compensation is a separate `Override`-type term.
- meter calibration is separate from user exposure compensation.
- Auto ISO is a **constraint solver**, not a scene-brightening heuristic.
- the normal Leica exposure path is not fundamentally a backlight classifier that emits a fixed positive EV boost.

This matters because the current M9Cam LUMA2.4 feedback experiment is limited to a positive `0 ... +0.75 EV` recommendation. Field evidence has already shown that the desired correction is not inherently positive or fixed: some scenes may need positive correction, some approximately zero, and some negative correction.

The next M9 exposure experiment should therefore move from:

```text
"How backlit is this scene and how much positive EV should be added?"
```

toward:

```text
"What BV would an M9-like optical TTL meter have assigned to this scene?"
```

The signed difference between the Leica-like BV estimate and the Photon/phone exposure target can then determine whether the requested correction should be negative, zero, or positive.

---

# 2. M9 BASELINE THAT REMAINS AUTHORITATIVE

The existing M9 firmware investigation remains the authority for **M9 behavior**.

Previously recovered M9 exposure arithmetic:

```text
EvDiff = 5 + TV - SV - BV + Override
```

Nominal exposure:

```text
TV = BV + SV - 5 - Override
```

Auto ISO solve:

```text
SV_required = 5 + TV + Override - BV
```

Important M9 findings already established:

- exposure values use signed **Q8.8 EV units**;
- `1 EV = 256`;
- normal M9 BV comes from a **scalar TTL metering path** rather than RGB/WB scene rendering;
- the M9 uses discrete Leica sensitivity / SV states;
- Auto ISO begins from the Leica base behavior already recovered for the M9;
- `Slowest speed` / lens-dependent TV is an **ISO activation / preference threshold**, not an absolute permanent shutter floor;
- at ISO limits the shutter may move beyond that preference threshold;
- lens-dependent shutter behavior is approximately reciprocal-focal-length;
- normal M9 metering is not proven to be a global image histogram, RGB classifier, or highlight percentile algorithm.

These M9 findings are **not superseded** by the M10-R work.

---

# 3. CURRENT M9 IMPLEMENTATION CONTEXT

The preceding exposure work introduced a deliberate separation between the capture and render exposure investigations.

The post-v2.75 architecture includes the `CAPTURESPLIT1A` direction, with capture-meter and render-meter concepts separated so that a rendered-image brightness problem is not automatically assumed to be a capture-metering problem.

Subsequent render-meter investigation has produced encouraging outdoor evidence, including the `RENDERMETER1C` line of work.

This separation must remain intact.

The new M10-R findings are primarily relevant to the **capture / metering / exposure-allocation side**.

They do not justify modifying:

- the frozen M9 photographic rendering;
- the M9 color pipeline;
- JPEG quality;
- DNG behavior;
- 12 MP output;
- primary render routing;
- native color behavior;
- render-meter calibration unless separate evidence demands it.

---

# 4. M10-R FIRMWARE RECONSTRUCTION STATUS

Firmware analyzed:

```text
M10-R-30.22.23.34-Customer.FW
```

The firmware packing has been solved sufficiently to recover the real Leica firmware image and inspect the actual exposure-control subsystem.

The decoded firmware contains:

- a MIPS/OpenWrt side;
- a separate Leica Camera Control subsystem using ARM/Thumb code;
- an AE library / controller containing the actual photographic exposure calculations.

The M10-R exposure research is being maintained independently in:

```text
mwilliams455/M10rCamera
```

This handoff copies only the findings relevant to M9 exposure architecture.

---

# 5. CROSS-GENERATION FINDING: SAME APEX COORDINATE SYSTEM

The M10-R independently uses:

```text
1 EV = 0x0100 = 256
```

for its principal exposure values.

That is the same Q8.8 EV scale independently recovered from the M9.

The newer M10-R AE library exposes the fuller exposure formulation:

```text
EV_target =
      BV
    + SV
    - Override
    - ExposureCorrection
    - per-SV correction
```

The selected exposure program then solves approximately:

```text
TV + AV ~= EV_target
```

with residual exposure error reported separately.

This is classical APEX-domain exposure arithmetic and strongly supports the idea that the M9 and M10-R are generations of a shared Leica exposure-engine philosophy.

---

# 6. AUTO ISO: IMPORTANT ARCHITECTURAL CLARIFICATION

The M10-R Auto ISO implementation is **not** the mechanism that decides whether a scene should be brighter or darker.

Conceptually:

```text
meter
  |
  v
BV
  |
  v
exposure target in APEX space
  |
  v
solve TV + AV
  |
  +--> constraints satisfied --> final exposure
  |
  +--> constraints hit
           |
           v
     move remaining EV into SV / ISO
```

Auto ISO therefore answers:

```text
"How can the requested exposure target be physically achieved?"
```

It does not answer:

```text
"Should this scene receive +0.75 EV because it is backlit?"
```

This closely matches the recovered M9 behavior where the lens-dependent slowest-shutter setting acts as an Auto-ISO activation threshold / preference rather than a universal scene correction.

---

# 7. M10-R METERING TOPOLOGY

The M10-R camera-control state keeps distinct brightness values for:

```text
TTL
EXT
EXT IR
BvCMOS
final BV
```

The normal traditional still/rangefinder path selects a TTL-derived BV.

Live-view / sensor-metered operation can use `BvCMOS`.

The firmware also includes a small source-change stability / hysteresis region of approximately:

```text
25 / 256 EV
~= 0.098 EV
```

and a separate final-BV coordinate / calibration offset of approximately:

```text
59 / 256 EV
~= 0.230 EV
```

These values are **M10-R implementation details** and must not be copied into M9Cam.

The important architectural result is separation:

```text
meter reading
!= meter calibration
!= meter source selection
!= user exposure compensation
!= Auto ISO
```

That separation is directly relevant to simplifying the current M9 exposure investigation.

---

# 8. M10-R MECHANICAL-LENS APERTURE ESTIMATION

The M10-R firmware explicitly maintains:

```text
selected AV
measured AV
```

For the traditional rangefinder path, the recovered measured-aperture estimator behaves structurally like:

```text
measured_AV ~= EXT_BV - TTL_BV + calibration
```

The estimate is then stabilized / quantized:

```text
meter difference
    |
    v
AV estimate
    |
    +--> approximately +/-0.25 EV hysteresis
    |
    +--> 0.5 EV quantization
    |
    +--> optional 22-entry aperture-table snap
    |
    +--> AV min/max clamp
```

When a valid estimate is unavailable the firmware can fall back to:

```text
AV = 4 EV = f/4
```

This is useful for understanding why the M10-R can run a complete:

```text
BV + SV = TV + AV
```

style model despite a mechanically controlled M lens.

It also provides a possible explanation for why the recovered M9 equation appears more reduced: the older camera's calibrated TTL BV path may absorb more of the lens/aperture effect rather than exposing AV as a separately reconstructed state.

This is a **research hypothesis**, not yet a proven M9 implementation detail.

---

# 9. CURRENT M9CAM LUMA2.4 LIMITATION

The present M9Cam live-feedback path is approximately:

```text
preview luma / spatial statistics
        |
        v
backlight-starvation score
        |
        v
recommendation 0 ... +0.75 EV
        |
        v
multiply Photon target exposure energy by 2^EV
```

The implementation therefore only knows how to request **more** exposure.

Current feedback logic also deliberately contains multiple scene classifiers / guards:

- dark body;
- bright population;
- body/highlight separation;
- center-body protection;
- catastrophic underexposure;
- spatial foreground starvation;
- landscape/high-contrast protection.

These have been useful for investigation and should remain available as diagnostics.

However, the cross-generation Leica evidence suggests they should **not automatically become the final M9 metering architecture**.

A real meter model should naturally be capable of producing:

```text
negative correction
zero correction
positive correction
```

from the same underlying scene-brightness model.

---

# 10. NEW PRIMARY M9 EXPOSURE HYPOTHESIS

The next question should be:

```text
What BV would an M9-like TTL meter report for the current scene?
```

rather than:

```text
Does this scene match a known backlight failure pattern?
```

Conceptual architecture:

```text
phone / Photon scene
        |
        +-----------------------------+
        |                             |
        v                             v
Photon exposure target        M9 virtual TTL meter
                                      |
                                      v
                                virtual raw meter
                                      |
                                      v
                              M9-like BV calibration
                                      |
                                      v
                                 virtual M9 BV
        |                             |
        +----------- compare ---------+
                      |
                      v
               signed meter delta EV
                      |
                      v
             exact M9 APEX controller
                      |
                      +--> TV preference
                      +--> lens threshold
                      +--> discrete SV / ISO
                      +--> physical allocation
```

This gives the signed correction naturally.

Example interpretation:

```text
virtual Leica meter says Photon is 0.72 EV too dark
=> signedMeterDeltaEv ~= +0.72 EV

virtual Leica meter says Photon is 0.43 EV too bright
=> signedMeterDeltaEv ~= -0.43 EV

difference ~= 0.05 EV
=> effectively no correction
```

No fixed `+0.75 EV` assumption is required.

---

# 11. NEXT M9 EXPERIMENT: `M9VirtualBv`

## 11.1 First implementation MUST be diagnostic-only

Do **not** replace or mutate the current exposure controller in the first build.

Add a parallel diagnostic model tentatively named:

```text
M9VirtualBv
```

Suggested schema:

```text
m9cam.virtualbv.v1
```

Its purpose is to estimate an M9-like BV and compare the implied signed exposure error against:

- Photon current exposure decision;
- existing LUMA2.4 recommendation;
- field-observed desired exposure;
- capture-meter diagnostics;
- render-meter diagnostics.

The first version should collect evidence only.

---

## 11.2 Suggested diagnostic pipeline

```text
linear / minimally transformed preview-meter proxy
        |
        v
M9-like scalar centre-weighted reading
        |
        v
temporal stabilization / averaging
        |
        v
virtual raw-meter value
        |
        v
raw-meter -> M9 BV calibration
        |
        v
Q8.8 virtual BV
        |
        v
exact recovered M9 APEX solve
        |
        v
predicted TV / SV
```

Do not assume the existing global preview histogram should directly become BV.

The virtual meter should attempt to approximate the **behavior of the M9's scalar optical TTL meter**, even though the Xiaomi hardware is using a camera sensor rather than a physical M9 metering photodiode.

---

# 12. REQUIRED `M9VirtualBv` TELEMETRY

At minimum log:

```text
schema
valid
reason

meterProxyRaw
meterProxyTemporal
meterProxyFramesUsed

virtualBvQ8_8
virtualBvEv

photonEquivalentBvEv
signedMeterDeltaEv

m9OverrideQ8_8

m9SelectedSvQ8_8
m9SelectedIso
m9TvBaseQ8_8
m9TvBaseEv
m9TvThresholdQ8_8
m9TvThresholdEv

autoIsoWouldActivate
autoIsoLowerBoundHit
autoIsoUpperBoundHit

predictedM9SvQ8_8
predictedM9SvEv
predictedM9Iso

predictedM9TvQ8_8
predictedM9TvEv
predictedM9ShutterSeconds

luma24WouldApply
luma24RecommendedEv
luma24AppliedEv

actualTargetIso
actualTargetExposureNs
actualCaptureIso
actualCaptureExposureNs
```

Also retain enough capture/render split data to answer:

```text
Was the source capture wrong?
or
Was capture reasonable and the rendered image merely too dark/bright?
```

That distinction remains essential.

---

# 13. DO NOT CLAMP THE FIRST DIAGNOSTIC TO A POSITIVE RANGE

The first diagnostic implementation should log the **raw signed BV difference**.

Do not initially force it into:

```text
0 ... +0.75 EV
```

and do not prematurely define:

```text
-1 EV ... +1 EV
```

as the final production bounds either.

We need to learn the real distribution first.

Production limits can be introduced only after validation.

The diagnostic may separately emit a proposed bounded value for analysis, but the unbounded/raw signed measurement must remain available.

---

# 14. VALIDATION STRATEGY

Use the existing exposure corpus first.

The known test set already contains:

- indoor backlit failures;
- outdoor backlit scenes;
- high-contrast negative controls;
- bright outdoor controls;
- darker indoor scenes;
- scenes manually improved with positive EV;
- scenes where a positive correction would be inappropriate;
- recent capture/render split examples.

For every replay / new test, compare:

```text
field-observed desired direction
        vs
LUMA2.4 signed capability (currently positive-only)
        vs
M9VirtualBv signedMeterDeltaEv
```

The first success criterion is **direction**, not perfect magnitude.

We should first ask:

```text
Does the model correctly decide:
negative / neutral / positive?
```

Then:

```text
Does magnitude track the photographic need?
```

Only after that should it drive the real capture allocator.

---

# 15. PROMOTION GATE

`M9VirtualBv` should remain diagnostic until it demonstrates all of the following:

1. Positive cases are correctly predicted as positive.
2. Known negative controls remain near zero or negative where appropriate.
3. It does not systematically brighten ordinary daylight scenes.
4. It does not systematically darken ordinary indoor scenes.
5. Backlit failures receive the correct correction direction.
6. Signed magnitude correlates with the amount of manual correction that improves the photograph.
7. ISO behavior remains explainable through the recovered M9 Auto-ISO model.
8. Capture-vs-render diagnostics still agree on where the brightness error originates.
9. No changes are required to the frozen M9 renderer to make the meter appear correct.
10. The model can be expressed with a reasonably simple Leica-like metering/calibration model rather than an ever-growing list of scene exceptions.

If these conditions hold, a later build can feed a **bounded signed meter correction** into the existing Photon allocation seam.

---

# 16. IMPORTANT IMPLEMENTATION PRINCIPLE

The target architecture should eventually separate:

```text
METER
  |
  v
BV

USER EV COMPENSATION
  |
  v
Override

M9 APEX CONTROLLER
  |
  v
TV / SV solution

MOTION POLICY
  |
  v
physical shutter preference adjustment

PHONE / PHOTON ALLOCATOR
  |
  v
actual exposure time + ISO
```

Do not collapse these into one scoring function.

In particular:

- `M9VirtualBv` should determine scene brightness;
- the recovered M9 APEX equation should determine requested exposure;
- Auto ISO should allocate exposure between shutter and sensitivity;
- motion policy should constrain shutter behavior for phone usability;
- render metering should remain a separate concern.

---

# 17. RELATIONSHIP TO CURRENT MOTION POLICY

The current `M9ModernExposurePolicy` works downstream by shortening Photon shutter caps based on subject motion while respecting analog ISO headroom.

That policy is conceptually compatible with the new architecture **if it remains downstream of the Leica-like scene target**.

The intended order is:

```text
virtual M9 meter
    |
    v
BV target
    |
    v
M9 APEX exposure request
    |
    v
M9 Auto-ISO / shutter preference
    |
    v
phone motion constraint
    |
    v
Photon physical allocation
```

Motion should not redefine BV.

BV should not be inferred from motion.

---

# 18. RELATIONSHIP TO LUMA2.4

Do not delete LUMA2.4.

It remains valuable as:

- a diagnostic backlight label;
- a known-scene regression oracle;
- a source of spatial measurements;
- a comparison baseline against the new virtual meter;
- a possible source of meter-proxy features during research.

But its final role should be determined by evidence.

Possible final outcomes include:

```text
A. Virtual BV replaces LUMA2.4 exposure feedback completely.

B. Virtual BV is primary; LUMA2.4 becomes diagnostic-only.

C. Virtual BV is primary; a very small LUMA-derived guard handles a proven phone-specific failure that a physical M9 meter never had to face.
```

Do not choose among these yet.

---

# 19. WHAT MUST NOT BE COPIED FROM M10-R INTO M9

Do not directly import M10-R:

- BV calibration constant `59/256 EV`;
- source-change hysteresis `25/256 EV`;
- AV hysteresis;
- 0.5-EV AV quantization;
- M10-R aperture table;
- M10-R SV limits;
- M10-R TV limits;
- M10-R Auto-ISO defaults;
- M10-R metering source policy;
- M10-R exposure-correction constants;
- M10-R program-line behavior.

These are evidence about **architecture**, not M9 calibration values.

The M9 firmware and M9 photographic behavior remain the target.

---

# 20. M10-R PARALLEL RESEARCH — CONTINUE IN `M10rCamera`

The M10-R project should continue defining the newer Leica implementation without blocking M9 work.

Highest-value remaining M10-R exposure targets:

1. reconstruct the exact production `TV ISO` calculation;
2. recover the full `1/f TV` derivation and focal-length mapping;
3. determine the exact numerical role of `EXT IR`;
4. recover the 22-entry measured-aperture AV table;
5. trace the exact TTL / EXT raw-meter calibration functions;
6. determine whether highlight information modifies BV upstream;
7. recover temporal filtering / averaging of the meter inputs;
8. map AE-lock semantics precisely;
9. recover per-SV correction table values and purpose;
10. distinguish service/debug exposure inputs from production still-capture inputs.

Each result should be evaluated in two columns:

```text
M10-R implementation fact
M9 relevance / no-relevance
```

This prevents newer-camera policy from accidentally becoming the M9 target.

---

# 21. CROSS-PROJECT WORKING MODEL

The two projects can now proceed in parallel:

## M9Camera

Primary goal:

```text
replicate M9 behavior
```

Immediate exposure task:

```text
diagnostic M9VirtualBv
```

Then validate against real M9-like photographic behavior and existing M9Cam field evidence.

## M10rCamera

Primary goal:

```text
reconstruct M10-R behavior independently
```

Immediate exposure task:

```text
finish exact metering + AE constraint reconstruction
```

Secondary value:

```text
use later Leica architecture to clarify ambiguous concepts in M9,
without treating M10-R values as M9 values.
```

---

# 22. FROZEN M9 QUALITY / FUNCTIONAL INVARIANTS

Exposure investigation must not regress the established camera behavior.

Preserve:

- 12 MP output;
- JPEG + DNG workflow;
- high-quality JPEG output;
- current frozen M9 photographic rendering;
- M9 primary render path;
- current color / tone behavior unless separately authorized;
- capture/render exposure separation;
- native-processing performance work already validated;
- diagnostics and timing telemetry needed for continued investigation.

Do **not** trade visible image quality for exposure or performance convenience.

---

# 23. RECOMMENDED NEXT BUILD

Recommended next M9 exposure build:

```text
VIRTUALBV1A
```

Characteristics:

```text
diagnostic-only
no exposure mutation
no renderer change
no JPEG-quality change
no DNG change
no current LUMA2.4 removal
no current motion-policy removal
```

Add:

```text
M9VirtualBv
m9cam.virtualbv.v1
signedMeterDeltaEv
predicted M9 TV/SV/ISO
comparison against LUMA2.4
comparison against Photon target
```

The purpose of `VIRTUALBV1A` is not to "fix exposure."

Its purpose is to determine whether a Leica-like BV abstraction can explain the field evidence **better and more symmetrically** than the current positive-only backlight-feedback model.

---

# 24. DECISION AFTER `VIRTUALBV1A`

After enough paired scenes:

### If virtual BV predicts the correct sign and useful magnitude

Proceed to:

```text
VIRTUALBV1B
```

with a carefully bounded **signed** live-feedback experiment.

### If virtual BV gets direction right but magnitude wrong

Keep the architecture and calibrate:

```text
raw meter -> BV
```

rather than returning to scene-specific EV constants.

### If virtual BV fails systematically

Use the M10-R meter reconstruction and the known M9 firmware path to determine whether:

- meter weighting is wrong;
- temporal averaging is wrong;
- raw-to-BV calibration is wrong;
- the preview proxy is not representative of the M9 TTL sensor;
- a missing lens/aperture term needs to be modeled.

Do not immediately add another special-case backlight branch.

---

# 25. CURRENT CONCLUSION

The M10-R firmware investigation has materially changed the interpretation of the M9 exposure problem.

The most important cross-generation conclusion is:

> Leica appears to meter a scene into a calibrated BV coordinate, then solve exposure in APEX space under shutter / aperture / ISO constraints. The camera does not fundamentally begin by classifying a scene as "backlit" and applying a fixed positive compensation.

For M9Cam, the next promising direction is therefore:

```text
virtual M9 TTL meter
        ->
virtual BV
        ->
exact M9 APEX solve
        ->
signed exposure difference
        ->
Photon physical allocation
```

rather than:

```text
backlight classifier
        ->
positive-only EV boost
```

This should be investigated **diagnostically first** and only promoted after field validation.

---

# 26. NEXT ACTIONS

## M9 project

1. Add `M9VirtualBv` diagnostic-only.
2. Preserve current LUMA2.4 for comparison.
3. Log raw signed meter delta.
4. Re-run existing positive and negative exposure examples.
5. Compare correction direction before tuning magnitude.
6. Keep capture and render exposure diagnostics separate.
7. Do not modify frozen renderer or JPEG quality.

## M10-R project

1. Continue exposure-engine reverse engineering in `M10rCamera`.
2. Finish TTL/EXT/EXT-IR metering math.
3. Finish TV-ISO / 1-f / AV-table reconstruction.
4. Record every cross-generation finding with explicit M9 relevance.
5. Do not block M9 diagnostic implementation while M10-R research continues.

---

**HANDOFF STATUS:** READY  
**M9 NEXT:** `VIRTUALBV1A` diagnostic-only  
**M10-R NEXT:** continue exact metering / AE reconstruction  
**CORE RULE:** architecture may transfer; camera-specific constants do not.
