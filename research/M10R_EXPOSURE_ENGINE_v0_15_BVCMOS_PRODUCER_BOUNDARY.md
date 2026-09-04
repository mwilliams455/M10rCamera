# M10-R Exposure Engine v0.15 — BvCMOS Producer Boundary and Live-View Source Selection

**Date:** 2026-09-04

**Branch:** `m10r-metering-latch-trace`

## Purpose

Continue from v0.14 by tracing AE state `+0x16` (`BvCMOS`), identifying its CTRL-side setter/getter, the record used to produce it, and the exact final-Bv source predicate visible in CTRL.

This note does **not** claim the pixel/statistical algorithm inside the upstream IMG/CA9 AE subsystem has been recovered. It closes the CTRL-side boundary sufficiently to show that BvCMOS is not produced by the traditional ADC meter path.

---

## 1. Exact BvCMOS accessors

AE state base remains:

```text
0x2001A918
```

BvCMOS is the signed halfword at:

```text
0x2001A918 + 0x16
```

Recovered accessors:

```text
BvCMOS setter: 0x08011D82
BvCMOS getter: 0x08011DA8
```

The getter is a direct signed-halfword load from `+0x16`.

Direct setter callers found:

```text
0x0800DF30
0x0800F906
0x0800F94A
0x0800F964
```

The `0x0800DF30` path is a fallback/initialization-like path that reads traditional Bv through `0x08011D7A` and copies it into BvCMOS under a state flag. It should not be mistaken for the normal CMOS producer.

---

## 2. Main CTRL-side BvCMOS update

Main update routine:

```text
0x0800F228
```

Direct callers:

```text
0x0800DC44
0x0800E000
```

The `0x0800DC44` wrapper passes `1` into `0x0800F228`.

When this update is running in the record-consuming path, it allocates a 36-byte local structure and calls:

```text
0x08001A78
```

which copies one 36-byte record out of a ring/table rooted at:

```text
0x200190AC
```

The ring contains 12 records of 36 bytes each.

The selected ring index is obtained through:

```text
0x08007EC0
```

The record copy uses the generic copy helper:

```text
0x0801D044
```

After record acquisition, `0x0800F228` performs calibration/post-processing and eventually calls the BvCMOS setter.

---

## 3. Bv candidate selector at 0x0800F1C0

Helper:

```text
0x0800F1C0
```

reads a signed runtime selector byte and chooses one of three 16-bit fields from the 36-byte record:

```text
selector 0 -> record +0x07
selector 1 -> record +0x05
selector 2 -> record +0x09
other      -> record +0x05
```

It then reads factory `AV0` from calibration record offset `+0x13` and returns approximately:

```text
BvCMOS_candidate = selected_record_field + AV0
```

in the same signed fixed-point exposure coordinate used elsewhere in the exposure engine.

Important implication:

**CTRL receives multiple already-computed CMOS AE/Bv-like candidate values and selects among them. It does not derive those values directly from pixels in `0x0800F1C0`.**

The exact semantic identity of the three candidate fields remains unresolved. Do not label them as spot/center/multi-field or any named metering mode until proved.

---

## 4. Record producer boundary inside CTRL

The ring at `0x200190AC` is populated by a larger state/AE record handler beginning at:

```text
0x08003068
```

Its only direct caller found in this trace is:

```text
0x08009B3E
```

inside command-layer wrapper:

```text
0x08009B2C
```

The handler writes a selected 36-byte ring slot. Relevant source-to-ring copies include:

```text
input +0x21 .. +0x30  -> ring +0x05 .. +0x14   (16 bytes)
input +0x31            -> ring +0x16            (16-bit)
input +0x33            -> ring +0x18            (16-bit)
input +0x35            -> ring +0x1A            (16-bit)
input +0x37            -> ring +0x1C            (32-bit)
```

Therefore the three values consumed later by `0x0800F1C0`:

```text
ring +0x05
ring +0x07
ring +0x09
```

all come directly from the upstream structure beginning at:

```text
input +0x21
```

This is the strongest current boundary result:

```text
upstream IMG/AE-side structure
        ↓
CTRL handler 0x08003068
        ↓
12 × 36-byte ring at 0x200190AC
        ↓
0x08001A78 copies current record
        ↓
0x0800F228 calibrates/post-processes
        ↓
0x0800F1C0 selects one of three Bv-like fields + AV0
        ↓
0x08011D82 stores BvCMOS
```

The precise upstream CPU/module that computes `input +0x21/+0x23/+0x25` is still to be proved by following the command/message owner into IMG-System / CA9.

---

## 5. Final-Bv source predicate is now explicit

The final selector remains:

```text
0x0800D6A8
```

The CMOS branch is selected when either of two state helpers is nonzero:

```text
0x080146F6 -> byte at 0x2001ADBB
0x08001A38 -> byte at 0x2001ADAE
```

Current CTRL-level rule:

```text
use_cmos = (state_0x2001ADBB != 0) || (state_0x2001ADAE != 0)
```

When `use_cmos` is true, the selector obtains BvCMOS through `0x08011DA8`.

When the predicate is false, the traditional-Bv eligibility path remains subject to the already-recovered ambient-calibration validity and negative-Bv-delay rules.

Do **not** yet rename either byte to a specific user-facing state such as `live_view_enabled`. Their exact owners and transition meanings still need to be recovered.

---

## 6. Important nuance: selector 5 is still invoked on the CMOS branch

The final-Bv selector invokes measurement selector 5 before reading BvCMOS as well as in the traditional path.

This does **not** prove selector 5 computes BvCMOS. The producer trace above proves the BvCMOS values are supplied through the separate 36-byte record path.

For now, model selector 5 as part of the synchronous AE/measurement transaction surrounding final-Bv selection, while keeping the numerical traditional-ADC producer and the numerical CMOS-record producer separate.

---

## 7. Relationship to CA9 AE clue

Firmware still contains the CA9 string:

```text
CA9: AE MODULE: AE algorithm running (AE parameter pointer 0x%08X)
```

The new CTRL record boundary makes the CA9/IMG AE subsystem a stronger candidate for the upstream numerical producer, but the relationship is **not yet proven**.

Do not state that CA9 computes BvCMOS until the message/record path is traced across the subsystem boundary.

---

## 8. Implementation consequence

The host oracle can now separate the two source models more confidently:

```text
traditional meter:
    phone/rangefinder-like luminance estimator
    -> M10-R traditional Bv

CMOS/live-view meter:
    separate sensor-frame/statistics estimator
    -> multiple CMOS Bv candidates if needed
    -> runtime candidate selection
    -> AV0 reference adjustment
    -> BvCMOS

final source selector:
    if CMOS-state predicate:
        use BvCMOS
    else:
        use traditional-Bv eligibility policy
```

Do not share the traditional ADC calibration function with the CMOS path unless a later trace proves common calibration math.

---

## 9. What is closed by v0.15

Closed enough for implementation/research continuity:

- exact BvCMOS state offset;
- exact BvCMOS setter/getter;
- main CTRL BvCMOS update routine;
- 36-byte current-record fetch;
- 12-slot record ring base and record size;
- three candidate Bv-like fields selected by runtime mode;
- AV0 addition before BvCMOS storage;
- upstream record-to-ring copy boundary;
- exact two-byte OR predicate used by final-Bv selector to choose the CMOS source.

Still open:

- semantic names of the three Bv candidate fields;
- exact meaning/writers of state bytes `0x2001ADBB` and `0x2001ADAE`;
- upstream IMG/CA9 command/message owner that supplies the AE record;
- raw image statistic / spatial weighting / metering-mode algorithm producing the three candidates;
- live-view update cadence;
- exact entry/exit transitions and AE-lock behavior if source mode changes while already locked.

---

## 10. Recommended next trace

Highest-value next sequence:

```text
0x08009B2C command-layer owner
    -> enumerate callers / command dispatch identity
    -> trace message source across CTRL/IMG boundary
    -> locate producer of source record fields +0x21/+0x23/+0x25
```

In parallel:

```text
0x2001ADBB writers
0x2001ADAE writers
    -> identify exact mode/state transitions
    -> prove which one is live view and what the second condition represents
```

Only after that should the CA9 AE-module string be tied to BvCMOS by name.
