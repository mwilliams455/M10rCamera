#!/usr/bin/env python3
"""Verify the M10-R ambient-light calibration flag and AE-lock path."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct


CTRL_BASE = 0x08000000
CTRL_PREFIX = 4
IMG_CODE_BASE = 0x42000000
IMG_DATA_BASE = 0x40000000
IMG_PREFIX = 4


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def ctrl_offset(address: int) -> int:
    return CTRL_PREFIX + address - CTRL_BASE


def img_offset(address: int) -> int:
    """Map an IMG code/string VA to its raw image offset."""
    return IMG_PREFIX + address - IMG_CODE_BASE


def img_data_offset(address: int) -> int:
    """Map an IMG initialized-data VA to its raw image offset."""
    return IMG_PREFIX + address - IMG_DATA_BASE


def cstring(data: bytes, offset: int) -> str:
    end = data.find(b"\0", offset)
    if end < 0:
        raise ValueError(f"unterminated string at file offset 0x{offset:x}")
    return data[offset:end].decode("ascii")


def require_prefix(data: bytes, offset: int, expected_hex: str, label: str) -> str:
    expected = bytes.fromhex(expected_hex)
    actual = data[offset : offset + len(expected)]
    if actual != expected:
        raise ValueError(
            f"{label} signature mismatch: {actual.hex()} != {expected.hex()}"
        )
    return actual.hex()


def extract(ctrl_path: Path, img_path: Path) -> dict[str, object]:
    ctrl = ctrl_path.read_bytes()
    img = img_path.read_bytes()

    if u32(img, 0) != 0x12345678:
        raise ValueError("expected IMG-System 0x12345678 prefix marker")

    ambient_text_va = 0x08046AF0
    ctrl_lock_text_va = 0x08049DD0
    ctrl_help_va = 0x080411ED
    ext_lock_va = 0x421C26FC
    ext_unlock_va = 0x421C270C
    control_name_va = 0x421C7790
    state_enabled_va = 0x421CAAC0
    state_disabled_va = 0x421CAAD8
    release_name_va = 0x4283F5FC
    mapper_error_va = 0x421395F4

    strings = {
        "ambient_light_missing": cstring(ctrl, ctrl_offset(ambient_text_va)),
        "ctrl_lock_received": cstring(ctrl, ctrl_offset(ctrl_lock_text_va)),
        "ctrl_simulator_help": cstring(ctrl, ctrl_offset(ctrl_help_va)),
        "img_event_lock": cstring(img, img_offset(ext_lock_va)),
        "img_event_unlock": cstring(img, img_offset(ext_unlock_va)),
        "img_control": cstring(img, img_offset(control_name_va)),
        "img_state_enabled": cstring(img, img_offset(state_enabled_va)),
        "img_state_disabled": cstring(img, img_offset(state_disabled_va)),
        "img_release_key": cstring(img, img_offset(release_name_va)),
        "img_mapper_error": cstring(img, img_offset(mapper_error_va)),
    }

    expected_strings = {
        "ambient_light_missing": "\t\t - Ambient light not calibrated\r\n",
        "ctrl_lock_received": "AE lock %i received\r\n",
        "ctrl_simulator_help":
            "<AELock X> Simulate AE lock (0 - unlock, 1 - lock).\r\n",
        "img_event_lock": "EXT_AE_LOCK",
        "img_event_unlock": "EXT_AE_UNLOCK",
        "img_control": "AE_LOCK_CONTROL",
        "img_state_enabled": "ae_lock_enabled",
        "img_state_disabled": "ae_lock_disabled",
        "img_release_key": "K_Release",
        "img_mapper_error":
            " string not found: _string = %d, _option = %d",
    }
    if strings != expected_strings:
        raise ValueError("one or more AE-lock/calibration evidence strings changed")

    lock_callback_literal_va = 0x421CAABC
    unlock_callback_literal_va = 0x421CAAD4
    lock_callback = u32(img, img_offset(lock_callback_literal_va))
    unlock_callback = u32(img, img_offset(unlock_callback_literal_va))
    if (lock_callback, unlock_callback) != (0x421BD5D5, 0x421BD5E5):
        raise ValueError("unexpected IMG AE-lock state callback pointers")

    signatures = {
        "ctrl_receiver": require_prefix(
            ctrl,
            ctrl_offset(0x0800248E),
            "10b504002278dff8841b002006f021fd20780bf0bafc02200bf0d0fb10bd",
            "CTRL AE-lock receiver",
        ),
        "ctrl_message_bit_injection": require_prefix(
            ctrl,
            ctrl_offset(0x0800DA62),
            "dff8a40a00789df8251060f341018df82510",
            "CTRL AE-lock message-bit injection",
        ),
        "ctrl_bv_update_gate": require_prefix(
            ctrl,
            ctrl_offset(0x0802049C),
            "94f82500c0f34000c0b2002818d194f82500c0f38000c0b2002802d0e069",
            "CTRL cached-Bv update gate",
        ),
        "img_lock_sender": require_prefix(
            img,
            img_offset(0x420AB2F8),
            "30b5c3b003ac0234002512206946888101202070002000900300032203a901901220",
            "IMG lock sender",
        ),
        "img_unlock_sender": require_prefix(
            img,
            img_offset(0x420AB326),
            "30b5c3b003ac023400251220694688810020207000900300032203a901901220",
            "IMG unlock sender",
        ),
        "img_release_translator": require_prefix(
            img,
            img_offset(0x42186734),
            "38b504000d006c48c06e01280ad820016a49401880682b00220069a1",
            "IMG physical-key translator",
        ),
        "img_enum_mapper": require_prefix(
            img,
            img_offset(0x42134D50),
            "70b504000d00902c03d003dc902c02d202e0f2e326e1",
            "IMG enum/string mapper",
        ),
        "img_enum_mapper_ae_cases": require_prefix(
            img,
            img_offset(0x42135388),
            "2900ae2004f004f940e72900af2004f0fff83be7",
            "IMG enum mapper AE cases",
        ),
    }

    # The physical-key descriptor is a 28-byte record. Record 13 is K_Release.
    key_table_va = 0x427F8EC4
    release_record_va = key_table_va + 13 * 28
    release_record = img[img_offset(release_record_va) : img_offset(release_record_va) + 28]
    release_name_ptr = u32(release_record, 0x0C)
    release_kind = release_record[0x10]
    release_events = struct.unpack_from("<4H", release_record, 0x12)
    if release_name_ptr != release_name_va or release_kind != 1:
        raise ValueError("unexpected IMG K_Release descriptor")
    if release_events != (0xD5, 0xD6, 0xD7, 0xD8):
        raise ValueError("unexpected IMG K_Release event sequence")

    # Global external-event actions are 16-byte records in initialized data.
    ext_lock_action = struct.unpack_from(
        "<4I", img, img_data_offset(0x4096945C)
    )
    ext_unlock_action = struct.unpack_from(
        "<4I", img, img_data_offset(0x4096946C)
    )
    if ext_lock_action != (0, 0xAE, 0, 0x421BE68D):
        raise ValueError("unexpected EXT_AE_LOCK action record")
    if ext_unlock_action != (0, 0xAF, 0, 0x421BE69B):
        raise ValueError("unexpected EXT_AE_UNLOCK action record")

    ctrl_lock_global = u32(ctrl, ctrl_offset(0x0800E508))
    cached_bv_global = u32(ctrl, ctrl_offset(0x08021130))
    if ctrl_lock_global != 0x2001AD6E:
        raise ValueError("unexpected CTRL AE-lock byte address")
    if cached_bv_global != 0x2000012A:
        raise ValueError("unexpected cached calculation-Bv address")

    return {
        "files": {
            "ctrl": {
                "path": str(ctrl_path),
                "size": len(ctrl),
                "sha256": hashlib.sha256(ctrl).hexdigest(),
            },
            "img": {
                "path": str(img_path),
                "size": len(img),
                "sha256": hashlib.sha256(img).hexdigest(),
            },
        },
        "mapping": {
            "ctrl": "VA = 0x08000000 + file_offset - 4",
            "img_code": "VA = 0x42000000 + file_offset - 4",
            "img_initialized_data": "VA = 0x40000000 + file_offset - 4",
            "img_prefix_marker": "0x12345678",
        },
        "ambient_light_calibration": {
            "persisted_structure_va": "0x2001a77c",
            "validity_flags_offset": "0x79",
            "ambient_light_valid_mask": "0x01",
            "missing_diagnostic_va": f"0x{ambient_text_va:08x}",
            "missing_diagnostic": strings["ambient_light_missing"],
        },
        "ae_lock": {
            "img_events": {
                "lock": {"id": "0xae", "name": strings["img_event_lock"]},
                "unlock": {"id": "0xaf", "name": strings["img_event_unlock"]},
            },
            "img_state_machine": strings["img_control"],
            "img_states": [strings["img_state_enabled"], strings["img_state_disabled"]],
            "img_callbacks": {
                "lock_thumb": f"0x{lock_callback:08x}",
                "unlock_thumb": f"0x{unlock_callback:08x}",
            },
            "physical_release": {
                "key_table_va": f"0x{key_table_va:08x}",
                "record_index": 13,
                "record_va": f"0x{release_record_va:08x}",
                "name": strings["img_release_key"],
                "raw_state_to_event": {
                    "1": {"id": "0xd6", "name": "K_Release_1"},
                    "3": {"id": "0xd7", "name": "K_Release_2"},
                    "2": {"id": "0xd5", "name": "K_Release_0"},
                },
                "unused_by_this_path": {"id": "0xd8", "name": "K_Release_3"},
                "translator_va": "0x42186734",
            },
            "external_actions": {
                "lock_record": [f"0x{x:08x}" for x in ext_lock_action],
                "unlock_record": [f"0x{x:08x}" for x in ext_unlock_action],
                "classification": (
                    "EXT_AE_LOCK/UNLOCK are independent external actions; "
                    "they are not emitted by the physical-key translator"
                ),
            },
            "negative_result": {
                "enum_mapper_va": "0x42134d50",
                "lookup_va": "0x42139598",
                "error_text": strings["img_mapper_error"],
                "classification": (
                    "the 0xAE/0xAF cases at 0x42135388/0x42135392 "
                    "perform a value lookup and return; they do not post events"
                ),
            },
            "ipc": {
                "command_id": "0x12",
                "packet_size": 3,
                "lock_payload": 1,
                "unlock_payload": 0,
                "ctrl_receiver_va": "0x0800248e",
                "ctrl_dispatch_case_va": "0x080097d2",
            },
            "ctrl_lock_byte_va": f"0x{ctrl_lock_global:08x}",
            "ctrl_message_field": "exposure-input +0x25 bit 1",
            "exposure_calculator_va": "0x080203b4",
            "cached_calculation_bv_va": f"0x{cached_bv_global:08x}",
            "update_rule": (
                "lock=0 refreshes cached calculation Bv from input +0x06; "
                "lock=1 skips that write and reuses the prior cached Bv"
            ),
        },
        "strings": strings,
        "signatures": signatures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ctrl_system", type=Path)
    parser.add_argument("img_system", type=Path)
    args = parser.parse_args()
    print(json.dumps(extract(args.ctrl_system, args.img_system), indent=2))


if __name__ == "__main__":
    main()
