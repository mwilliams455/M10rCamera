#!/usr/bin/env python3
"""Verify M10-R first-detent AE-lock ordering across IMG/BSTM and CTRL."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

from m10r_ae_lock_inspect import ctrl_offset, img_offset, require_prefix


def u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def thumb_bl_target(data: bytes, offset: int, instruction_va: int) -> int:
    """Decode a Thumb-2 BL immediate at *offset* and return its target VA."""
    h1 = u16(data, offset)
    h2 = u16(data, offset + 2)
    if (h1 & 0xF800) != 0xF000 or (h2 & 0xD000) != 0xD000:
        raise ValueError(f"not a Thumb BL at 0x{instruction_va:08x}")
    s = (h1 >> 10) & 1
    imm10 = h1 & 0x03FF
    j1 = (h2 >> 13) & 1
    j2 = (h2 >> 11) & 1
    imm11 = h2 & 0x07FF
    i1 = (~(j1 ^ s)) & 1
    i2 = (~(j2 ^ s)) & 1
    imm25 = (s << 24) | (i1 << 23) | (i2 << 22) | (imm10 << 12) | (imm11 << 1)
    if s:
        imm25 -= 1 << 25
    return (instruction_va + 4 + imm25) & 0xFFFFFFFF


def expect_ctrl_bl(ctrl: bytes, va: int, target: int, label: str) -> str:
    actual = thumb_bl_target(ctrl, ctrl_offset(va), va)
    if actual != target:
        raise ValueError(f"{label}: BL target 0x{actual:08x} != 0x{target:08x}")
    return f"0x{actual:08x}"


def expect_img_bl(img: bytes, va: int, target: int, label: str) -> str:
    actual = thumb_bl_target(img, img_offset(va), va)
    if actual != target:
        raise ValueError(f"{label}: BL target 0x{actual:08x} != 0x{target:08x}")
    return f"0x{actual:08x}"


def extract(ctrl_path: Path, img_path: Path) -> dict[str, object]:
    ctrl = ctrl_path.read_bytes()
    img = img_path.read_bytes()

    # Receiver-local ordering: store lock first, then post update mask 2.
    require_prefix(
        ctrl,
        ctrl_offset(0x0800248E),
        "10b504002278dff8841b002006f021fd20780bf0bafc02200bf0d0fb10bd",
        "CTRL AE-lock receiver ordering",
    )
    setter = expect_ctrl_bl(ctrl, 0x080024A0, 0x0800DE18, "AE-lock state setter")
    update = expect_ctrl_bl(ctrl, 0x080024A6, 0x0800DC4A, "AE-lock update post")

    # The update helper checks the exposure event facility and posts the caller's
    # bitmask to the exposure-control task selected from its task descriptor.
    require_prefix(
        ctrl,
        ctrl_offset(0x0800DC4A),
        "10b5040003f0f3fa002806d02100dff8b408c0790ff062f905e02200dff8ac180120fbf738f910bd",
        "CTRL exposure update-event helper",
    )
    ready = expect_ctrl_bl(ctrl, 0x0800DC4E, 0x08011238, "exposure event-ready getter")
    event_send = expect_ctrl_bl(ctrl, 0x0800DC5E, 0x0801CF26, "exposure task event post")

    # Event bit 1 (mask 2) is extracted by the exposure-control event loop.  If
    # its normal eligibility check passes, that branch invokes the input builder.
    require_prefix(
        ctrl,
        ctrl_offset(0x0800DD42),
        "9df80000c0f34000c0b2002810d0",
        "CTRL exposure event bit-1 consumer",
    )
    eligibility = expect_ctrl_bl(ctrl, 0x0800DD50, 0x08001A38, "event-2 eligibility check")
    builder = expect_ctrl_bl(ctrl, 0x0800DD58, 0x0800D91C, "event-2 exposure builder")

    # The builder snapshots the global lock byte into exposure input +0x25 bit 1
    # and is the sole direct caller of the calculator in the recovered graph.
    require_prefix(
        ctrl,
        ctrl_offset(0x0800DA62),
        "dff8a40a00789df8251060f341018df82510",
        "CTRL lock-bit snapshot into exposure input",
    )
    calculator = expect_ctrl_bl(ctrl, 0x0800DB78, 0x080203B4, "exposure calculator call")
    require_prefix(
        ctrl,
        ctrl_offset(0x0802049C),
        "94f82500c0f34000c0b2002818d194f82500c0f38000c0b2002802d0e069",
        "CTRL cached-Bv refresh gate",
    )

    # BSTM is child-first: the parent dispatcher invokes the child wrapper before
    # evaluating its own transition table; the wrapper recursively dispatches.
    child = expect_img_bl(img, 0x420A2768, 0x420A2840, "BSTM child dispatch")
    recursive = expect_img_bl(img, 0x420A2852, 0x420A274C, "BSTM recursive dispatcher")

    # The external exposure-start action is a useful independent ordering probe:
    # it synthesizes K_Release_1 first and only then enters exposure preparation.
    require_prefix(
        img,
        img_offset(0x421BE6EC),
        "70b504000d00d620fef778f900f0a0fd012070bd",
        "IMG external exposure-start ordering",
    )
    event_producer = expect_img_bl(img, 0x421BE6F4, 0x421BC9E8, "K_Release_1 event producer")
    exposure_prep = expect_img_bl(img, 0x421BE6F8, 0x421BF23C, "exposure-start preparation")

    return {
        "files": {
            "ctrl_sha256": hashlib.sha256(ctrl).hexdigest(),
            "img_sha256": hashlib.sha256(img).hexdigest(),
        },
        "ctrl_lock_to_calculator": {
            "receiver_va": "0x0800248e",
            "ordered_calls": [
                {"call_va": "0x080024a0", "target": setter, "meaning": "commit AE-lock byte"},
                {"call_va": "0x080024a6", "target": update, "meaning": "post update mask 2"},
            ],
            "event_post": {
                "ready_getter": ready,
                "per_task_event_sender": event_send,
                "mask": "0x02",
            },
            "event_consumer": {
                "bit": 1,
                "eligibility_check": eligibility,
                "builder": builder,
            },
            "builder": {
                "va": "0x0800d91c",
                "lock_snapshot_va": "0x0800da62",
                "lock_destination": "exposure-input +0x25 bit 1",
                "calculator_call_va": "0x0800db78",
                "calculator": calculator,
            },
            "closed_order": (
                "CTRL command receiver commits the lock byte before posting event mask 2; "
                "the exposure-control event-2 branch invokes the builder, which snapshots "
                "that lock state before directly calling the calculator"
            ),
        },
        "img_ordering": {
            "bstm": {
                "dispatcher": "0x420a274c",
                "child_call": child,
                "recursive_call": recursive,
                "classification": "nested BSTM state machines are dispatched before the current state's transitions",
            },
            "external_exposure_start": {
                "action_va": "0x421be6ec",
                "first_call": event_producer,
                "event": {"id": "0xd6", "name": "K_Release_1"},
                "second_call": exposure_prep,
                "classification": "K_Release_1 is emitted before the later exposure-preparation call",
            },
        },
        "latch_boundary": {
            "lock_triggered_pass_can_refresh_cached_bv": False,
            "reason": (
                "the lock-triggered event-2 calculation snapshots AE_lock=1, and the calculator's "
                "lock gate suppresses refresh of cached calculation Bv"
            ),
            "remaining_race": (
                "a previously-started unlocked builder/calculator pass could have snapshotted "
                "AE_lock=0 before the receiver commits lock and could complete across the task boundary; "
                "static evidence here does not yet prove mutual exclusion or task-priority ordering"
            ),
            "oracle_status": (
                "stateful first-detent lock remains confirmed; exact identity of the final Bv sample "
                "relative to the physical detent remains provisional"
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ctrl_system", type=Path)
    parser.add_argument("img_system", type=Path)
    args = parser.parse_args()
    print(json.dumps(extract(args.ctrl_system, args.img_system), indent=2))


if __name__ == "__main__":
    main()
