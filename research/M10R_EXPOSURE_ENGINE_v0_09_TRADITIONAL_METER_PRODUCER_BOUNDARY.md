# M10-R Exposure Engine v0.09: Traditional-Meter Producer Boundary

## Outcome

The upstream traditional/rangefinder meter investigation has crossed the CTRL-local boundary.

The nine-byte `AE measure result` handler at `0x0800E1EC` has exactly one direct caller in CTRL-System: the communication dispatcher branch at `0x0801D88A`. The handler itself only validates/decodes the incoming packet and writes the already-computed meter-domain fields into CTRL exposure state; it does not derive traditional Bv from raw optical measurements.

The packet contract remains:

```text
+0x00  signed Tlog
+0x02  signed traditional/rangefinder Bv
+0x04  signed BvExt
+0x06  signed BV_IR
+0x08  status bit
```

## Handler behavior reverified

At `0x0800E1FA` the received size is compared with `9`. On a valid packet:

- `+0x02` is written through `0x08011D54` when the traditional-result acceptance flag is active;
- `+0x04` is written through `0x08011D18` when the relevant state gate allows it;
- `+0x06` is always written through `0x08011D36`;
- `+0x00` is written through `0x08011DB0`;
- `+0x08` contributes the status bit copied into CTRL state.

Thus the sender owns the numerical production of these values. CTRL is the consumer/state coordinator.

## Single CTRL dispatch entry

A direct-call scan of CTRL-System finds only:

```text
0x0801D88A -> BL 0x0800E1EC
```

At that branch the communication dispatcher passes:

```text
r0 = packet data pointer
r1 = packet size
```

to the AE-result handler.

The next required static step is to recover the selector/message identity that chooses this `0x0801D88A` branch, then match that identity to the sender in the non-CTRL firmware images.

## Cross-image vocabulary boundary

A checksum-verified scan of all extracted firmware sections found the exact CTRL diagnostics/field names only in `090_CTRL-System.bin`:

- `AE measure result`
- `Tlog`
- `BvExt`
- `BvCMOS`
- `BV_IR`

`092_IMG-System.bin` does contain exposure/light-meter control and status vocabulary, including:

```text
Light-Meter on (uint8)
Light-Meter x 256 (sint16)
SET - IMG_MPARAM_ID_LIGHTMETER
Lightmeter: %d
Lightmeter on: %d
```

and `099_IMG-CA9_System.bin` exposes a separate:

```text
CA9: AE MODULE: AE algorithm running ...
```

No second textual copy of the CTRL `AE measure result` field vocabulary was found in those images. A superficial `Tlog` substring hit in `100_IMG-SAM7.bin` belongs to test-interface `GetLog` strings and is not meter evidence.

## Interpretation boundary

This does **not** yet identify the physical producer CPU or prove the raw-to-Bv equation. It does establish that the CTRL handler receives a precomputed four-coordinate meter result rather than constructing traditional Bv at the point of receipt.

The IMG `Light-Meter x 256` parameter must also not yet be equated with the nine-byte packet's traditional Bv. It may be a UI/control/status coordinate, and its producer/consumer path needs explicit xref tracing before assigning photographic semantics.

Likewise the CA9 AE module is a strong candidate for the CMOS/live-view branch, but the string alone is insufficient to identify it as the traditional/rangefinder result producer.

## Next trace

1. Recover the communication-dispatch selector/message ID for the `0x0801D88A -> 0x0800E1EC` branch.
2. Search every non-CTRL image for the matching sender/packet constructor.
3. Identify which CPU owns the nine-byte result and the exact packet assembly order.
4. Trace backward from the sender's `+0x02` field to raw light-meter inputs and calibration/linearization.
5. Keep the traditional/rangefinder path separate from the CA9 CMOS/live-view AE path until the call graph proves convergence.

## Photographic significance

This is now the highest-value M10-R exposure target. Reconstructing the sender-side transformation into traditional Bv will reveal the part of the Leica exposure personality that cannot be reproduced by copying the downstream Tv/ISO allocator alone: meter scaling, calibration, filtering, brightness-dependent behavior, and any non-linear response before final-Bv selection.

## Research provenance

The trace was run against checksum-verified `M10-R-30.22.23.34-Customer.FW` on the temporary `m10r-metering-latch-trace` branch. Firmware binaries are not committed to the repository.
