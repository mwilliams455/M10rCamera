# M10R PROJECT HANDOFF v0.07 — LVVideoSync / CA9 BV Stream Mapping Next

**Date:** 2026-09-04  
**Repository:** `mwilliams455/M10rCamera`  
**Active branch:** `m10r-metering-latch-trace`  
**Firmware:** `M10-R-30.22.23.34-Customer.FW`  
**Firmware SHA-256:** `ec8df72dc7d4c90332abb3cdbc07c6db837ffed802c1a9712b6f3d6e0edf6498`

## 1. Purpose of this handoff

This handoff captures the M10-R exposure/metering investigation after the v0.15 CTRL-side BvCMOS producer-boundary work and the subsequent cross-subsystem trace into the IMG/CA9 → ARM9 → CTRL live-view synchronization path.

The highest-value unresolved question is no longer whether CTRL has a distinct CMOS brightness-value path. That is established.

The next question is:

```text
Which CA9 AE BV product
    (Spot / Integral / MFM / AV-field)
feeds each CTRL live-view BV candidate,
and which one ultimately becomes BvCMOS under each runtime selector/state?
```

The immediate next investigation should therefore map the named CA9 BV outputs byte-for-byte into CTRL command `0x32` / `LVVideoSync`, then into the already-known 36-byte ring fields consumed by `0x0800F1C0`.

---

## 2. Do-not-regress conclusions from the traditional/rangefinder meter work

These conclusions remain valid unless hard contradictory evidence is found.

### Fresh traditional-meter acquisition

Fresh acquisition uses:

```text
measurement selector mask 1
```

Do **not** reinterpret selectors/detents `9 / 10 / 11` as fresh ambient ADC acquisition.

Those selectors belong to AE lock/recalculate/finalization behavior.

### Traditional ADC path

Recovered traditional meter behavior includes:

```text
ADC channel: ~6
sample count: ~10
average samples
apply body calibration
produce traditional Bv
```

The traditional path is independent of the upstream CMOS/CA9 AE record path described below.

### Final-Bv selector

The final source-selection logic remains in the region:

```text
0x0800D6A8 / 0x0800D6AC
```

with traditional-Bv eligibility rules already recovered in prior work.

---

## 3. v0.15 BvCMOS facts that are already proved

The AE state base is:

```text
0x2001A918
```

The BvCMOS signed halfword is:

```text
0x2001A918 + 0x16
```

This identity is **already proved**.

Do not reopen `+0x16` as an anonymous field merely because later traces inspect adjacent Bv state.

Exact accessors:

```text
BvCMOS setter: 0x08011D82
BvCMOS getter: 0x08011DA8
```

A firmware diagnostic string also exists:

```text
BvCMOS = %+05i
```

around the `0x0804A848` string region, reinforcing the recovered semantic name.

### Important correction to preserve

A later exploratory description temporarily referred to both `state +0x14` and `state +0x16` as unnamed states.

That phrasing must **not** supersede v0.15.

The correct current status is:

```text
state +0x16 = BvCMOS          PROVED
state +0x14 = adjacent BV-like state, semantic identity still open
```

---

## 4. CTRL-side BvCMOS producer path from v0.15

Main BvCMOS update routine:

```text
0x0800F228
```

Direct callers found:

```text
0x0800DC44
0x0800E000
```

The routine obtains a current 36-byte AE/CMOS record through:

```text
0x08001A78
```

from a 12-slot ring:

```text
ring base: 0x200190AC
record size: 0x24 bytes = 36 bytes
record count: 12
```

The selected ring index is obtained through:

```text
0x08007EC0
```

---

## 5. CTRL candidate-BV selector

Critical helper:

```text
0x0800F1C0
```

reads a runtime selector byte at:

```text
0x20000132
```

and chooses one of three halfwords from the current 36-byte record:

```text
selector 0 -> record +0x07
selector 1 -> record +0x05
selector 2 -> record +0x09
other      -> record +0x05
```

It then adds calibration `AV0` from calibration-record offset `+0x13`.

Working model:

```text
BvCMOS_candidate = selected_record_field + AV0
```

The semantic identity of the three record fields was not known at v0.15.

Do **not** assign Spot / Integral / MFM names to them until the new CA9 → CTRL field mapping is closed.

---

## 6. CTRL record-ingestion boundary

Handler:

```text
0x08003068 / 0x0800306C
```

copies an incoming larger structure into the 36-byte ring.

Relevant mapping:

```text
input +0x21 .. +0x30 -> ring +0x05 .. +0x14   (16 bytes)
input +0x31          -> ring +0x16            (16-bit)
input +0x33          -> ring +0x18            (16-bit)
input +0x35          -> ring +0x1A            (16-bit)
input +0x37          -> ring +0x1C            (32-bit)
```

Therefore the three candidate fields later consumed by `0x0800F1C0`:

```text
ring +0x05
ring +0x07
ring +0x09
```

originate directly from:

```text
incoming payload +0x21
incoming payload +0x23
incoming payload +0x25
```

This remains the strongest CTRL-side proof that the CMOS Bv candidates arrive already numerically computed from upstream.

---

## 7. New cross-subsystem finding: CA9 AE starter has two direct entry paths

The upstream AE starter under investigation is:

```text
0x420A2FB4
```

Two direct calls to that starter were located at:

```text
0x4216B8BA
0x4216B8FC
```

The two entry paths install different final callbacks.

Observed split:

```text
modes 0x0B .. 0x12 -> callback 0x42161FA1
general path       -> callback 0x42161AF1
```

with modes `0x06` and `0x1B` diverted elsewhere in the surrounding dispatch logic.

This is likely a meaningful AE workflow split, but do not yet label one branch "capture" and the other "live view" solely from the mode range.

---

## 8. CA9 completion callback exposes four named BV products

The callback around:

```text
0x42161FA0 / 0x42161FA1
```

reads four 16-bit BV results from the CA9 result object at:

```text
result +0x30
result +0x32
result +0x34
result +0x36
```

The recovered semantic order is:

```text
Spot BV
Integral BV
MFM BV
AV-field BV
```

The callback also copies the corresponding EV values.

This is the first strong upstream evidence giving semantic names to multiple BV products before they cross into CTRL.

---

## 9. ARM9 CtrlCPU handoff block

The callback serializes the four BV values and their corresponding EV values into a CtrlCPU state block rooted at:

```text
0x408F0EC0
```

The relevant destination area spans approximately:

```text
+0x2A .. +0x38
```

for the eight 16-bit BV/EV values.

A second ARM9 routine was found performing the same eight-value copy into the same state block.

That makes this structure a deliberate inter-subsystem AE handoff format rather than incidental scratch state.

### Important caution

Before assigning exact destination offsets to individual Spot / Integral / MFM / AV-field values in implementation notes, re-open the disassembly and preserve the exact store ordering instruction-by-instruction.

The fact that all four named BVs and their EV counterparts are copied is established; the final byte-for-byte semantic table should be treated as the next trace product.

---

## 10. Event handoff: 0x78000032

After the ARM9 callback copies the four BV/EV pairs, it posts:

```text
0x78000032
```

The same event is posted from a second IMG workflow path.

This event is therefore strongly associated with the AE/live-view synchronization handoff rather than a one-off callback artifact.

---

## 11. CTRL command 0x32 is now identified as LVVideoSync

CTRL dispatcher:

```text
0x08009DEE
```

explicitly matches:

```text
command 0x32
```

and routes it into the handler around:

```text
0x08009B30
```

The handler parses the command-`0x32` input through:

```text
0x0800306C
```

and emits a command-`0x32` response of:

```text
0x49 bytes = 73 bytes
```

A CTRL debug string identifies this command semantically as:

```text
LVVideoSync
```

Its diagnostic output includes fields such as:

```text
AV
SV
TV
Image ID
Max ISO
Max TV
live-view related flags
```

This establishes command `0x32` as the real live-view exposure synchronization packet, not a generic record transport.

---

## 12. Command-0x32 response Bv fields

Instruction-level response mapping recovered so far:

```text
response +0x1D = BV
response +0x1F = BV_IR
response +0x21 = BV_Ext
```

The final-BV getter used in this path was identified around:

```text
0x08011D04
```

Do not confuse this final `BV` state with `BvCMOS`.

Current conceptual separation:

```text
BvCMOS = CMOS/live-view brightness candidate after CTRL selection/calibration
BV     = final brightness value selected for exposure calculation / response
```

A nearby diagnostic family includes strings equivalent to:

```text
Bv
BvExt
BvCMOS
```

which is useful semantic reinforcement for the state model.

---

## 13. Final source-selection rule from v0.15 remains valid

The final selector uses two state predicates:

```text
0x080146F6 -> byte at 0x2001ADBB
0x08001A38 -> byte at 0x2001ADAE
```

Current CTRL-level rule:

```text
use_cmos =
    (byte[0x2001ADBB] != 0)
    ||
    (byte[0x2001ADAE] != 0)
```

When `use_cmos` is true, the selector reads:

```text
BvCMOS through 0x08011DA8
```

When false, it follows the traditional-Bv eligibility path.

Do not yet rename either state byte to a user-facing mode such as `live_view_enabled`.

One writer to `0x2001ADAE` was previously found around:

```text
0x08002F4C
```

Further transition tracing remains required.

---

## 14. Current best architecture

The current evidence supports this architecture:

```text
IMAGE SENSOR / IMG AE
        │
        ▼
CA9 AE algorithm
        │
        ├─ Spot BV
        ├─ Integral BV
        ├─ MFM BV
        └─ AV-field BV
        │
        ▼
CA9 completion callback
0x42161FA0
        │
        ▼
ARM9 CtrlCPU state
0x408F0EC0
(BV + EV handoff values)
        │
        ▼
event 0x78000032
        │
        ▼
CTRL command 0x32
LVVideoSync
        │
        ▼
0x0800306C
incoming fields +0x21...
        │
        ▼
12 × 36-byte ring
0x200190AC
        │
        ▼
0x0800F1C0
choose record +0x05/+0x07/+0x09
        │
        + AV0
        ▼
0x0800F228
        │
        ▼
0x08011D82
BvCMOS = AE state +0x16
        │
        ▼
0x0800D6A8 / 0x0800D6AC
final source selection
        │
        ▼
final BV
```

### What is hard evidence vs. what is still a seam

Hard evidence now establishes all major blocks above individually.

The remaining item to prove byte-for-byte is the exact serialization mapping between:

```text
CA9/ARM9 named BV outputs
```

and:

```text
CTRL command-0x32 input +0x21/+0x23/+0x25/...
```

Until that is closed, do not state that a particular CTRL candidate offset is definitively Spot, Integral, MFM, or AV-field.

---

## 15. Strongest new implication

The M10-R does not appear to have a single undifferentiated "CMOS meter value" arriving in CTRL.

Instead, the upstream AE system exposes several already-computed BV products:

```text
Spot
Integral
MFM
AV-field
```

and CTRL later selects among multiple candidate fields before storing BvCMOS.

This matters for eventual app replication.

A faithful M10-R exposure oracle may need:

```text
sensor statistics
    -> several spatially distinct BV estimators
    -> Leica runtime candidate selection
    -> AV0/reference adjustment
    -> BvCMOS
    -> final source selector
```

rather than one generic live-view average-luminance number.

Do not implement four named estimators yet; first close the field mapping and selector semantics.

---

## 16. Runtime selector still open

The byte controlling `0x0800F1C0` is:

```text
0x20000132
```

Known behavior:

```text
0 -> record +0x07
1 -> record +0x05
2 -> record +0x09
default -> record +0x05
```

Now that CA9 exposes named BV outputs, tracing writers/readers of `0x20000132` has become much higher value.

The goal is to establish an evidence-backed equation such as:

```text
selector 0 -> <named CA9 BV product>
selector 1 -> <named CA9 BV product>
selector 2 -> <named CA9 BV product>
```

Do not map selector numbers to metering-mode names from intuition.

---

## 17. Highest-priority next trace

### Track A — close the named CA9 BV → CTRL field map

Start from:

```text
0x42161FA0
0x408F0EC0
event 0x78000032
```

Recover the exact packet builder / message transport that produces CTRL command `0x32`.

Then map:

```text
Spot BV
Integral BV
MFM BV
AV-field BV
```

onto exact command-`0x32` input offsets.

Specifically resolve:

```text
input +0x21
input +0x23
input +0x25
input +0x27   (if the fourth value continues contiguously)
```

without assuming the fourth offset until disassembly proves it.

Once this is done, the existing CTRL ring mapping immediately gives semantic identities to:

```text
ring +0x05
ring +0x07
ring +0x09
...
```

### Track B — trace runtime selector 0x20000132

Enumerate:

```text
all readers
all writers
caller context
mode/state transitions
```

for:

```text
0x20000132
```

Then correlate selector values `0/1/2` with the now-named CA9 BV products.

This is probably the shortest route to identifying Leica's actual live-view metering-mode choice.

### Track C — finish source-state semantics

Continue writer tracing for:

```text
0x2001ADBB
0x2001ADAE
```

Goal:

```text
prove which state corresponds to normal live view,
identify the second CMOS-forcing condition,
trace entry/exit transitions,
test AE-lock behavior if the source changes while locked.
```

---

## 18. Secondary next trace: final BV / adjacent state +0x14

`AE state +0x16` is BvCMOS and is closed.

The adjacent state:

```text
AE state +0x14
```

remains semantically unresolved and is involved in nearby final-BV logic.

Trace:

```text
getter(s)
setter(s)
callers
diagnostic-string xrefs
relationship to final BV
```

without disturbing the proven `+0x16 = BvCMOS` identity.

Also useful firmware strings include:

```text
Update BV value for calculation.
BV value for calculation (0x%04X | %i | %f |).
```

These may provide a direct semantic xref into the final calculation path.

---

## 19. Selector-5 caution

The final-BV selector still invokes:

```text
measurement selector 5 via 0x080184D8
```

before reading BvCMOS.

Do **not** reinterpret selector 5 as the numerical CMOS meter producer.

The numerical CMOS BV values have a separately proven upstream record path.

For now:

```text
selector 5 = shared synchronous AE/measurement transaction plumbing
```

unless later evidence proves a more specific role.

---

## 20. CA9 attribution status

The earlier firmware clue:

```text
CA9: AE MODULE: AE algorithm running (AE parameter pointer 0x%08X)
```

is now materially reinforced by the newly recovered CA9 result structure and named BV outputs.

It is now reasonable to say:

```text
CA9 AE produces named BV result products in this traced path.
```

However, the actual raw image-statistic / spatial weighting formulas used to produce:

```text
Spot
Integral
MFM
AV-field
```

are still not recovered.

Do not claim their pixel-level algorithms are known.

---

## 21. Research artifacts / repo state

Important existing research note:

```text
research/M10R_EXPOSURE_ENGINE_v0_15_BVCMOS_PRODUCER_BOUNDARY.md
```

Commit that introduced it:

```text
ae4a4f4e74fe13dd3efe16ab80f4d9d2bcaf2fa8
```

Earlier v0.15 research-only workflows include:

```text
.github/workflows/m10r-v015-bvcmos-xrefs.yml
.github/workflows/m10r-v015-bvcmos-producer.yml
.github/workflows/m10r-v015-bvcmos-boundary.yml
.github/workflows/m10r-v015-bvcmos-ring-state.yml
.github/workflows/m10r-v015-cmos-receiver-owner.yml
```

These are research scaffolding and should not be promoted wholesale to `main`.

Known v0.15 workflow runs/artifacts from the previous handoff:

```text
33840855571  m10r-v015-bvcmos-xrefs
33840964151  m10r-v015-bvcmos-producer
33841052400  m10r-v015-bvcmos-boundary
33841204959  m10r-v015-bvcmos-ring-state
33841285579  m10r-v015-cmos-receiver-owner
```

---

## 22. Research rigor / wording constraints

Preserve these distinctions in the next session:

### Proven

- traditional meter fresh acquisition is selector mask 1;
- selectors 9/10/11 are not fresh ambient ADC sampling;
- traditional ADC and CMOS AE numerical producers are separate;
- BvCMOS is `0x2001A918 +0x16`;
- BvCMOS getter/setter are `0x08011DA8 / 0x08011D82`;
- CTRL receives multiple already-computed CMOS BV-like values;
- CTRL command `0x32` is `LVVideoSync`;
- CA9 result structure exposes named Spot / Integral / MFM / AV-field BV products;
- command `0x32` reaches the CTRL record-ingestion path;
- final source selector uses the two-state OR predicate and can select BvCMOS.

### Strong but not yet byte-for-byte closed

- the CA9 BV products are the upstream semantic source of the CTRL ring candidate fields;
- event `0x78000032` is the ARM9-side trigger for the same live-view synchronization flow.

### Still open

- exact CA9 named-BV to command-`0x32` offset table;
- exact named identity of CTRL ring `+0x05/+0x07/+0x09`;
- semantic meaning of runtime selector `0x20000132`;
- pixel/statistical formulas for Spot / Integral / MFM / AV-field;
- exact meaning of `0x2001ADBB` and `0x2001ADAE`;
- adjacent AE state `+0x14`;
- live-view cadence and AE-lock transition behavior.

---

## 23. Recommended first action in the next session

Do not restart from the traditional meter.

Do not spend another pass proving that `+0x16` is BvCMOS.

Start here:

```text
CA9 callback 0x42161FA0
    ↓
ARM9 state 0x408F0EC0
    ↓
event 0x78000032
    ↓
find exact command-0x32 packet serializer
    ↓
map named BV products to CTRL payload offsets
    ↓
reuse existing 0x0800306C mapping
    ↓
assign semantic identities to ring candidates
    ↓
trace 0x20000132
```

Success criterion for the next research note:

```text
Spot / Integral / MFM / AV-field
        ↓ exact byte offsets
LVVideoSync command 0x32
        ↓
ring fields
        ↓
selector 0/1/2
        ↓
BvCMOS
```

Once that table is proved, the M10-R live-view metering architecture will be substantially more implementation-ready.
