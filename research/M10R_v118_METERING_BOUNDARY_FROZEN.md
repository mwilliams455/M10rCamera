# M10-R v1.18 — METERING BOUNDARY FROZEN

Firmware: `M10-R-30.22.23.34-Customer.FW`  
SHA256: `ec8df72dc7d4c90332abb3cdbc07c6db837ffed802c1a9712b6f3d6e0edf6498`

Status: **FROZEN FOR IMPLEMENTATION**

This document closes the current M10-R metering reverse-engineering phase at the boundary needed to implement the metering path in the PhotonCamera-based application. It deliberately distinguishes the proven ABI/data-shape contract from one remaining unproven runtime pointer-equality detail.

---

## 1. Producer geometry is frozen: 22 × 16 = 352 AEAWB blocks

The Prepro AFAEAWB mode configuration exposes Leica-labelled fields:

- `AEAWB Block Numbers (horizontal)` = 22
- `AEAWB Block Numbers (vertical)` = 16

The same geometry is carried into the live Prepro window structure and programmed into hardware:

- `0x2000401C` = horizontal block count = 22
- `0x20004018` = vertical block count = 16

Therefore the producer-side metering/statistics grid is:

```text
22 columns × 16 rows = 352 cells
```

This is a firmware-semantic result, not a numerical guess.

References: v0.94–v1.04 research, especially `M10R_v100_aeawb_grid_geometry_FROZEN.md` and `M10R_v104_aeawb_mmio_grid_FROZEN.md`.

---

## 2. Prepro statistics payload begins at producer block root + 0x80

`drv_prepro_afaeawb_if_Config` uses its configured AFAEAWB memory root at `[config+4]`.

The function explicitly does:

```asm
420dacc8: ldr   r0, [r4, #4]     ; configured AFAEAWB root
420dacca: movs  r1, r0
420daccc: adds  r1, #0x80        ; root + 0x80
420dacce: movs  r0, #6           ; PW channel 6
420dacd0: bl    0x420e0850       ; drv_prepro_driver_pwch_setPWSA
```

`0x420E0850` is identified by Leica diagnostics as:

```text
drv_prepro_driver_pwch_setPWSA(channel %d)
```

and writes the address into the selected Prepro write-channel register bank.

Therefore:

```text
PW channel 6 output destination = AFAEAWB block root + 0x80
```

The root is itself structured state, not simply the raw payload: configuration also writes header/state data at the root (for example `strh ... [root]` at `0x420DACA4`).

---

## 3. CA9 receives a block-root pointer, not a raw-cell pointer

The CA9 parameter builder `0x420A3104` computes the workflow field:

```asm
420a3116: movs  r0, #0x85
420a3118: lsls  r0, r0, #3       ; 0x428
420a311a: adds  r0, r4, r0
420a311c: ldr   r0, [r0, #0x58]  ; workflow + 0x480
420a311e: ldr   r1, =0x43705A60
420a3120: str   r0, [r1]
```

Thus:

```text
workflow + 0x480 -> CA9 AE parameter block root pointer
```

The ARM CA9 AE module then dereferences that root as a structured statistics block. In the core configuration path around `0x4000084C..0x40000934`, it repeatedly reads header fields from the object pointed to by `[r4]`, then explicitly forms the payload pointer:

```asm
4000090c: ldr   r0, [r6]         ; statistics block root
40000914: add   r0, r0, #0x80    ; root + 0x80
4000091c: str   r0, [sp, #0x30]  ; payload pointer
```

Therefore the CA9 consumer contract is also:

```text
statistics block root
    +0x00 ... header / geometry / mode fields
    +0x80 ... statistics payload
```

This independently matches the Prepro PW-channel-6 producer layout.

---

## 4. Structural producer/consumer ABI is closed

The independently recovered producer and consumer agree on the same essential memory shape:

```text
PREPRO PRODUCER
AFAEAWB block root
    |
    +-- header/state at root
    |
    +-- payload at root + 0x80
            ^
            |
        PW channel 6 writes here

                     [caller / module boundary]

CA9 CONSUMER
workflow + 0x480
    |
    +-- statistics block root
            |
            +-- header fields at root
            +-- payload consumed from root + 0x80
```

Combined with the frozen 22 × 16 geometry, the metering-input ABI required for implementation is therefore:

```text
M10R_AE_STATS_BLOCK
    root/header
    payload_offset = 0x80
    grid_width      = 22
    grid_height     = 16
    cell_count      = 352
```

The exact per-cell payload encoding remains governed by the already recovered CA9 statistic/quantity/evaluator paths (v0.73–v0.83b); this boundary document does not redefine those algorithms.

---

## 5. `workflow+0x480` is caller-owned at the CA9 API boundary

`0x420A2FB4` is identified by Leica diagnostics as `ca9_StartImageProcessing`.

The function:

1. accepts the workflow object as its first argument;
2. saves it to `0x408187EC`;
3. calls `0x420A3104`, which immediately consumes `workflow+0x480`.

Prior targeted traces found:

- no direct internal caller of `0x420A2FB4`;
- no useful static function-pointer registration for `0x420A2FB4/5`;
- no in-module writer to `workflow+0x480` in the CA9/workflow or Prepro regions.

A later broad v1.17 whole-image constructor scan was cancelled by the Actions runner before producing a result; it adds no contradictory evidence.

The correct implementation interpretation is therefore:

> `workflow+0x480` is an input field owned/populated on the external side of the `ca9_StartImageProcessing` API boundary. CA9 consumes the block supplied there; CA9 does not construct that field internally.

This is enough to freeze the ABI even though the dynamically linked/higher-level caller that physically assigns the field has not been recovered.

---

## 6. Physical pointer equality is deliberately NOT frozen

Do **not** claim the following as proven firmware identity:

```text
workflow+0x480 == exact Prepro runtime allocation root
```

The structural evidence strongly supports that relationship because both sides independently use the same root-plus-0x80 payload contract, but an explicit cross-module assignment/copy instruction has not been recovered.

Also do **not** substitute:

```text
workflow+0x480 = base+0x80
```

because `base+0x80` is the **payload**, while CA9 expects the **block root** and adds `+0x80` itself.

`base+0x14080` remains a separate/companion structured AFAEAWB block seen in Prepro state. It must not be promoted to the primary CA9 root without new evidence.

---

## 7. Implementation contract for the PhotonCamera M10-R path

For a software implementation we do not need to emulate Leica's Prepro MMIO/PW-channel machinery. The required boundary is:

```text
camera frame / luma source
        |
        v
construct M10-R 22×16 statistics
        |
        v
populate M10R_AE_STATS_BLOCK
  - header/geometry/mode fields
  - payload begins at logical +0x80 boundary
        |
        v
run recovered CA9 metering evaluator
        |
        v
Bv / EV result
        |
        v
M10-R exposure solver (Tv / Sv / Av / AE-lock policy)
```

The implementation may represent the structure idiomatically rather than forcing a literal packed 0x80-byte C header, provided the recovered semantics and algorithms are preserved. A byte-faithful packed representation can still be retained in the oracle/tests for parity validation.

---

## 8. Metering phase stop condition

For purposes of building the camera application, the M10-R metering boundary is now considered **closed**.

Further reverse engineering of the dynamic caller that assigns `workflow+0x480` is optional and should only be resumed if implementation testing reveals a missing semantic field or a disagreement with firmware results.

The next major research track should be **M10-R colour science**, split into:

1. sensor / camera colour transforms and calibration matrices;
2. white-balance / tint / illuminant interpolation;
3. tone / highlight / black-level rendering;
4. Leica JPEG look tables and hue/saturation shaping;
5. separation of DNG/RAW colour calibration from JPEG rendering.

Target implementation remains the same PhotonCamera branch family used by the M9 project, with an independent M10-R photographic route.
