# M10-R PROJECT HANDOFF v0.02
## EXPOSURE ENGINE: TV-ISO / 1-F / SV TABLE / FINAL-BV / AE ORACLE NEXT

**Date:** 2026-09-03  
**Repository:** `mwilliams455/M10rCamera`  
**Firmware:** `M10-R-30.22.23.34-Customer.FW`  
**Predecessor research:** `research/M10R_EXPOSURE_ENGINE_v0_01.md`  
**Cross-project M9 handoff:** `research/M9_PROJECT_HANDOFF_v2_76_M10R_EXPOSURE_CROSSGEN_VIRTUAL_BV_NEXT.md`

---

# 1. PURPOSE

This handoff records the current Leica M10-R exposure-engine reconstruction milestone and defines the next research / implementation boundary.

The project is still in **research-first mode**.

The current objective is not yet to reproduce the M10-R rendering pipeline. The immediate goal is to reconstruct the M10-R exposure and metering architecture sufficiently well to:

1. build an executable Leica AE oracle;
2. validate the oracle independently of Photon;
3. then integrate that oracle into PhotonCamera in diagnostic-only form;
4. move M10-R development in parallel with the M9 project while sharing only platform infrastructure, not camera-specific photographic policy.

The M10-R work is also proving useful as a newer Leica reference for unresolved M9 exposure questions.

---

# 2. REPOSITORY STATE

Current M10-R repository:

```text
mwilliams455/M10rCamera
```

Important committed research/tooling already present:

```text
research/M10R_EXPOSURE_ENGINE_v0_01.md
research/M9_PROJECT_HANDOFF_v2_76_M10R_EXPOSURE_CROSSGEN_VIRTUAL_BV_NEXT.md
tools/m10r_unpack.py
tools/m10r_sections.py
research/M10R_EXPOSURE_ENGINE_v0_02_CTRL_SYSTEM_AND_PHOTON_BOUNDARY.md
```

The firmware unpacking path is now reproducible from the original Leica `.FW`.

---

# 3. FIRMWARE UNPACKING STATUS

The Leica M10-R firmware wrapper has been solved sufficiently to deterministically recover the real decoded firmware image.

The unpacked image contains 102 Leica firmware sections.

The section descriptor size is:

```text
0x248 bytes
= 584 bytes
```

This explains the earlier repeating 584-byte structure observed in the decoded image.

The exposure / camera-control work is concentrated in:

```text
Section: CTRL-System
Image base: 0x08000000
Size: ~312,648 bytes
Architecture: ARM / Thumb
```

This section contains the Leica Camera Control AE / metering code and is the primary target for the continuing exposure reverse engineering.

---

# 4. CORE EXPOSURE DOMAIN

The M10-R uses signed Q8.8 APEX units:

```text
1 EV = 0x0100 = 256
```

The recovered AE defaults are now confirmed from actual initialization instructions:

```text
SV:
  min  = 5 EV
  max  = 12 EV
  step = 1 EV default before table snapping

TV:
  min  = -7 EV
  max  = 12 EV

AV:
  min  = 0 EV
  max  = 12 EV
  step = 1 EV default before table snapping
```

Equivalent photographic interpretations:

```text
SV 5  ~= ISO 100
SV 12 ~= ISO 12,800

TV -7 = 128 s
TV 12 ~= 1/4096 s
```

The AE engine then applies discrete tables and limits on top of this continuous EV-domain arithmetic.

---

# 5. CENTRAL AE MODEL

The current recovered M10-R AE target is structurally:

```text
EV_target =
      BV
    + SV
    - Override
    - ExposureCorrection
    - per-SV correction
```

The selected exposure mode then attempts to satisfy:

```text
TV + AV ~= EV_target
```

Auto ISO is not itself a brightness / scene-correction mechanism.

It is a **constraint solver** that absorbs unresolved exposure into SV / ISO after TV / AV mode constraints are applied.

This is important for both M10-R implementation and the M9 cross-generation comparison.

---

# 6. AE STATE / DIAGNOSTIC TOPOLOGY

The M10-R controller distinctly tracks:

```text
TTL
EXT
BV_IR
BvCMOS

Bv
BvExt

Av
AvMan
AvAdj

Tv
TvMan

Sv
SvMan

Ev
dEv

f
```

This is strong evidence that Leica separates:

```text
meter measurement
meter calibration
meter-source selection
manual/user states
AE target solving
Auto ISO
final solved exposure
```

rather than collapsing these into one scene classifier or one EV correction.

---

# 7. FINAL BV STORAGE / CALIBRATION SEAM

The final-BV storage path is now instruction-level confirmed.

One setter performs:

```text
stored_BV = incoming_BV - 59
```

in Q8.8 counts.

The paired getter restores:

```text
returned_BV = stored_BV + 59
```

Thus:

```text
59 / 256 EV
= 0.23046875 EV
```

is a coordinate / calibration seam around the stored BV value.

It is **not** user exposure compensation.

Do not treat it as a universal +0.23 EV photographic bias.

---

# 8. FINAL BV STABILITY / HYSTERESIS

The production final-BV selector also compares a newly selected source against the previous final BV with an approximately:

```text
25 / 256 EV
= 0.09765625 EV
```

deadband / stability band.

Conceptually:

```text
new selected BV
       |
       v
compare against previous final BV
       |
       +--> inside ~0.10 EV band --> retain previous state
       |
       +--> outside band --> update final BV
```

This is another internal meter-stability mechanism.

It is separate from:

```text
user Override
Auto ISO
exposure compensation
```

---

# 9. METER SOURCES

The current state map confirms the controller retains separate meter values:

```text
EXT
BV_IR
BvCMOS
traditional / TTL-derived path
final BV
```

Known state identities include:

```text
state +0x10 = EXT / BvExt
state +0x12 = BV_IR
state +0x16 = BvCMOS
```

The remaining traditional meter state at:

```text
state +0x14
```

is the alternate source used by the final-BV selector when the CMOS-derived path is not selected.

All current evidence indicates this is the traditional TTL-derived BV path, but this label should not be considered permanently frozen until its producer is traced instruction-by-instruction.

This is the next meter-state closure target.

---

# 10. `Tlog` / `Tlm20` FALSE LEAD RESOLVED

Earlier diagnostics included:

```text
Tlog
Tlm20
```

These initially looked like possible additional metering variables.

That interpretation is now rejected.

`Tlm20` is produced by a hardware/environmental sensor-control path adjacent to firmware diagnostics for:

```text
S-5851A temperature sensor
Hall-sensor subsystem
```

and is filtered with its own approximately ±50-unit stability behavior.

Therefore:

```text
Tlog / Tlm20
```

must not be included in the core photographic BV / AE model unless later evidence explicitly reconnects them.

This simplifies the exposure topology.

---

# 11. EXTERNAL-METER CALIBRATION IS PIECEWISE

The external-light calibration layer carries anchor corrections at approximately:

```text
BV -2
BV  0
BV  3
BV 10
```

with separate slopes between:

```text
-2 -> 0
 0 -> 3
 3 -> 10
```

This is important architecturally.

Leica is not relying on one global raw-meter → BV offset in this path.

Instead, the meter can use a brightness-dependent calibration function.

Do not copy these breakpoints into M9 or Photon blindly.

The important lesson is:

```text
raw meter -> calibrated BV
```

may be nonlinear / piecewise.

---

# 12. MECHANICAL-LENS APERTURE ESTIMATION

The M10-R controller explicitly maintains:

```text
selected AV
measured AV
```

For the traditional M-lens path the measured aperture behaves structurally like:

```text
measured_AV ~= EXT_BV - TTL_BV + calibration
```

followed by approximately:

```text
±0.25 EV hysteresis
0.5 EV quantization
optional AV table snap
AV limit clamp
```

When valid estimation is unavailable, a fallback of:

```text
AV = 4 EV
= f/4
```

can be used.

This is a hardware-specific Leica mechanism for a mechanically controlled M lens.

For a future Xiaomi / Photon implementation we should not need to emulate this optical trick because the phone's aperture is known directly.

---

# 13. PRODUCTION ISO ↔ SV TABLE RECOVERED

The firmware contains an explicit ISO↔SV table rather than using only a runtime logarithmic formula.

Examples:

```text
ISO 100   -> SV 5.000 EV
ISO 125   -> SV 5.332 EV
ISO 160   -> SV 5.680 EV
ISO 200   -> SV 6.000 EV

ISO 400   -> SV 7.000 EV
ISO 800   -> SV 8.000 EV
ISO 1600  -> SV 9.000 EV
ISO 3200  -> SV 10.000 EV
ISO 6400  -> SV 11.000 EV
ISO 12500 -> SV 12.000 EV
```

The internal table spans a much broader engineering / service domain, approximately:

```text
ISO 3 ... ISO 400,000
```

over 52 states.

Not every state should be assumed to be a user-selectable photographic M10-R ISO.

The important result is that the exact Leica Q8.8 conversion lattice is available for an executable oracle.

---

# 14. `1/f TV` IS PROVEN FROM FOCAL LENGTH

The firmware reads actual active-lens focal length in **millimetres**.

The same source is used in Leica's own diagnostic message containing:

```text
focal length (%i mm, AV min %i, AV max %i)
```

The `1/f TV` helper therefore operates on actual focal length, not an inferred arbitrary denominator.

The conversion behaves approximately as:

```text
TV_1/f = log2(focal_length_mm)
```

with Q8.8 output rounded to approximately 0.5-EV shutter steps.

Examples:

```text
16 mm  -> TV 4.0  -> 1/16 s
~23 mm -> TV 4.5
32 mm  -> TV 5.0  -> 1/32 s
~45 mm -> TV 5.5
64 mm  -> TV 6.0  -> 1/64 s
~91 mm -> TV 6.5
128 mm -> TV 7.0  -> 1/128 s
```

A zero / unavailable input has a fallback equivalent to approximately:

```text
TV 6
= 1/64 s
```

---

# 15. AUTO-ISO MAXIMUM-EXPOSURE-TIME MODES RESOLVED

The firmware itself names the four focal-length-relative Auto-ISO shutter modes:

```text
1/f
1/2f
1/3f
1/4f
```

These are stored symbolically and resolved whenever focal-length context changes.

The resulting Auto-ISO boundary is approximately:

```text
1/f  -> TV_1/f

1/2f -> TV_1/f + 1.0 EV

1/3f -> TV_1/f + 1.5 EV

1/4f -> TV_1/f + 2.0 EV
```

Leica therefore approximates `1/3f` using a +1.5 EV offset rather than an exact `log2(3)` value.

An absolute TV choice can bypass the focal-length-relative conversion.

---

# 16. `TV ISO` POLICY NOW UNDERSTOOD

The production Auto-ISO settings block resolves the symbolic user choice to an absolute Q8.8 TV boundary.

That resulting value is supplied to the AE engine as:

```text
TV ISO
```

Conceptually:

```text
active focal length
       |
       v
TV_1/f
       |
       +--> 1/f
       +--> 1/2f
       +--> 1/3f
       +--> 1/4f
       +--> absolute TV
       |
       v
resolved TV ISO
       |
       v
AE solver
       |
       v
shutter / ISO allocation
```

In aperture-priority operation, `TV ISO` acts as the shutter preference / Auto-ISO activation boundary.

When the requested exposure would require a shutter beyond that preference, unresolved EV begins moving into SV / ISO, subject to the configured SV limits.

This is highly relevant to the older M9 `Slowest speed` architecture.

---

# 17. CROSS-GENERATION M9 RELEVANCE

The M10-R is independently confirming the same general Leica exposure philosophy previously reconstructed from the M9:

```text
meter
   ->
BV
   ->
APEX equation
   ->
TV / AV / SV constraint solve
   ->
physical exposure
```

The important shared concepts are:

```text
Q8.8 EV domain
BV as core scene coordinate
Override as separate user compensation
discrete SV states
lens / focal-length shutter preference
Auto ISO as residual / constraint allocation
```

The camera-specific calibration constants remain separate.

Do not import M10-R:

```text
59/256 BV storage offset
25/256 deadband
piecewise EXT calibration anchors
M10-R SV limits
M10-R AV behavior
M10-R TV limits
M10-R 1/f UI policy
```

directly into M9Camera.

Use them only as evidence about Leica architecture.

---

# 18. FUTURE PHOTON IMPLEMENTATION ARCHITECTURE

PhotonCamera remains the recommended shared platform.

The correct long-term structure is:

```text
                 Photon shared platform
                         |
             +-----------+-----------+
             |                       |
             v                       v
       M9 personality          M10-R personality
             |                       |
       M9 meter                M10-R meter
       M9 AE                   M10-R AE
       M9 Auto ISO             M10-R Auto ISO
       M9 renderer             M10-R renderer
```

Shared infrastructure may include:

```text
Camera2 capture
image ownership
queueing
JPEG save
DNG save
metadata
native infrastructure
timing diagnostics
device / lens discovery
```

Do not make M10-R a branch of the M9 photographic personality.

---

# 19. PHONE-SPECIFIC AV ADAPTATION

The real M10-R must estimate the mechanical lens aperture.

The Xiaomi phone does not.

For a Photon M10-R profile:

```text
phone aperture
     |
     v
known fixed AV
```

can be supplied directly to the reconstructed AE model.

Thus the future M10-R Photon exposure architecture can be:

```text
phone meter proxy
       |
       v
M10-R-like calibrated BV
       |
       +--> known phone AV
       +--> Override
       +--> focal-length policy
       |
       v
M10-R AE oracle
       |
       +--> TV
       +--> SV
       |
       v
Camera2 exposure time + ISO
```

This reproduces Leica policy without unnecessarily emulating the Leica mechanical-aperture sensing hardware.

---

# 20. NEXT RESEARCH TARGETS

Before freezing the first production-style AE oracle, continue with:

## 20.1 Traditional meter source closure

Trace the producer of:

```text
state +0x14
```

and confirm definitively whether it is the traditional TTL-derived BV state.

## 20.2 Exact final-BV source selector

Freeze the operating-mode conditions that choose between:

```text
traditional / TTL-derived BV
and
BvCMOS
```

including AE-lock and state-transition behavior.

## 20.3 Exact A-mode Auto-ISO helper

Recover the actual instruction sequence that:

```text
takes EV target
applies AV
applies TV ISO
moves residual into SV
snaps/clamps SV
returns final TV/SV/dEV
```

This should become the first executable Leica AE oracle path.

## 20.4 Production SV subset

Determine which entries of the 52-state engineering ISO table are actually valid in normal M10-R still photography and how user Auto-ISO min/max settings constrain them.

## 20.5 Per-SV correction

Recover the 52 signed per-SV correction values and determine whether they represent:

```text
meter calibration
sensitivity calibration
sensor gain correction
AE linearization
```

or another purpose.

---

# 21. EXECUTABLE ORACLE MILESTONE

The next major milestone should be an offline program tentatively called:

```text
m10r_ae_oracle
```

Initial inputs:

```text
program
BV Q8.8
AV Q8.8
SV Q8.8 / ISO state
Override Q8.8
TV ISO Q8.8
1/f TV Q8.8
Auto ISO enabled
SV min
SV max
TV min
TV max
```

Initial outputs:

```text
TV Q8.8
SV Q8.8
ISO
shutter seconds
dEV
constraint reason
Auto-ISO activation
SV lower-bound hit
SV upper-bound hit
TV boundary hit
```

The oracle must first match known firmware behavior outside Photon.

Only then should it be embedded into the app.

---

# 22. PHOTON DEVELOPMENT GATE

Once the executable AE oracle is stable enough, create the first M10-R Photon implementation.

Recommended sequence:

```text
M10R-PHOTON0A
```

Purpose:

```text
establish clean M10-R Photon capture / save / diagnostics infrastructure
```

No M10-R rendering claim yet.

Then:

```text
M10R-AE1A
```

Purpose:

```text
run reconstructed M10-R AE in diagnostic-only mode
```

Suggested telemetry:

```text
m10rVirtualBv
m10rAv
m10rOverride

m10rTvIso
m10rOneOverFTv

predictedTv
predictedSv
predictedIso
predictedShutterSeconds
predictedDEv

autoIsoActivated
constraintReason

actualPhotonTv
actualPhotonIso
actualPhotonExposureTime
```

`M10R-AE1A` should **not mutate the real exposure** initially.

It should compare Leica-predicted exposure against Photon / Camera2 behavior.

---

# 23. RELATIONSHIP TO M9 PARALLEL DEVELOPMENT

Parallel work should proceed as:

```text
M9
  ->
M9VirtualBv diagnostic
  ->
validate virtual M9 TTL/BV behavior
  ->
signed exposure correction

M10-R
  ->
finish meter / AE reconstruction
  ->
offline AE oracle
  ->
M10R-AE1A diagnostic

               |
               v

      shared Photon platform
```

M10-R findings can clarify M9 architecture.

M9 findings can provide practical information about Photon integration.

Neither project's camera-specific photographic constants should silently leak into the other.

---

# 24. QUALITY / PLATFORM PRINCIPLES

When M10-R reaches Photon development:

Preserve the same general engineering discipline established in the M9 project:

- avoid unnecessary JPEG quality loss;
- separate capture policy from rendering policy;
- maintain diagnostic visibility;
- do not optimize by silently changing photographic output;
- keep DNG behavior explicit;
- keep camera-specific metering independent from rendering;
- use native acceleration only after behavior is validated;
- prefer reproducible parity/oracle tests before performance changes.

The M10-R target should ultimately be its own photographic personality, not “M9 with different color.”

---

# 25. CURRENT CONCLUSION

The M10-R exposure investigation is now beyond general architectural inference.

Several production behaviors are directly reconstructed:

```text
Q8.8 APEX domain
exact ISO/SV lattice
final-BV coordinate offset
final-BV stability deadband
piecewise meter calibration
focal-length-derived 1/f TV
1/f / 1/2f / 1/3f / 1/4f Auto-ISO modes
resolved TV ISO boundary
separation of meter / Override / Auto ISO
```

The remaining work is focused and tractable.

The best next objective is:

```text
complete traditional BV source
        +
freeze A-mode Auto-ISO helper
        +
build executable AE oracle
```

After that, M10-R should be ready to enter PhotonCamera in a diagnostic-only AE phase while the M9 project continues independently.

---

# 26. NEXT ACTIONS

## M10-R research

1. Trace and definitively label `state +0x14`.
2. Freeze final-BV source-selection logic.
3. Recover exact A-mode Auto-ISO constraint helper.
4. Determine production still-photo SV subset.
5. Recover per-SV correction table.
6. Build offline `m10r_ae_oracle`.

## Photon preparation

1. Do not yet copy M9 code as the M10-R personality.
2. Identify only the reusable Photon platform seams.
3. Plan `M10R-PHOTON0A`.
4. Plan diagnostic-only `M10R-AE1A`.
5. Keep rendering work separate until exposure/capture behavior is validated.

---

**HANDOFF STATUS:** READY  
**RESEARCH NEXT:** traditional BV source + exact A-mode Auto-ISO helper  
**IMPLEMENTATION GATE:** executable offline AE oracle  
**PHOTON NEXT AFTER GATE:** `M10R-PHOTON0A` then diagnostic `M10R-AE1A`  
**CORE RULE:** share platform architecture, not M9 photographic assumptions.
