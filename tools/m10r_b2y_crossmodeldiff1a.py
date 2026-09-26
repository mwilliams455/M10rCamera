#!/usr/bin/env python3
"""Record-by-record M10-family B2Y cross-model calibration diff.

This tool is intentionally calibration-only. It compares parsed B2Y records
between an M10-R baseline and M10 Monochrom firmware, aligns repeated record
IDs by occurrence ordinal with structural checks, maps IDs to the frozen
selector inventory, and prioritizes model-specific photographic controls.

It does not infer hardware arithmetic and does not modify renderer behavior.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from m10r_b2y_assets import parse_records

EXPECTED_LABELS = (
    "M10R-20.20.47.37",
    "M10M-2.12.8.0",
    "M10M-3.21.2.50",
)
BASELINE = EXPECTED_LABELS[0]

KNOWN_ASSET_IDS = {
    0x19: "tone_table",
    0x1C: "dg_main",
    0x1D: "dg_fl_anchors",
}
INVARIANT_CONTROLS = {
    0x0C: "yc_conversion",
    0x0D: "y_blend",
}


def sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def hexoff(v: int) -> str:
    return f"0x{v:x}"


def exact_occurrences(blob: bytes, needle: bytes, limit: int = 64) -> tuple[list[int], bool]:
    if not needle:
        return [], False
    out: list[int] = []
    pos = 0
    truncated = False
    while True:
        hit = blob.find(needle, pos)
        if hit < 0:
            break
        if len(out) >= limit:
            truncated = True
            break
        out.append(hit)
        pos = hit + 1
    return out, truncated


def parse_item_spec(spec: str) -> tuple[str, Path, str, str, str]:
    parts = spec.split("|", 4)
    if len(parts) != 5:
        raise ValueError(
            "--item must be LABEL|B2Y_PATH|FIRMWARE_SHA256|DECODED_SHA256|IDENTIFICATION"
        )
    label, path, fw_sha, dec_sha, ident = parts
    return label, Path(path), fw_sha, dec_sha, ident


def parse_inventory(path: Path) -> dict[int, list[dict[str, str]]]:
    out: dict[int, list[dict[str, str]]] = defaultdict(list)
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw.startswith("V094_MAP="):
            continue
        fields: dict[str, str] = {}
        for token in raw[len("V094_MAP=") :].split("|"):
            if "=" not in token:
                continue
            k, v = token.split("=", 1)
            fields[k] = v
        rid_text = fields.get("record", "UNKNOWN")
        if rid_text == "UNKNOWN":
            continue
        try:
            rid = int(rid_text, 0)
        except ValueError:
            continue
        item = {
            "name": fields.get("name", "UNKNOWN"),
            "func": fields.get("func", "UNKNOWN"),
            "lookup": fields.get("lookup", "UNKNOWN"),
            "setter": fields.get("setter", "UNKNOWN"),
            "pages": fields.get("pages", "NONE"),
            "offsets": fields.get("offsets", "NONE"),
        }
        if item not in out[rid]:
            out[rid].append(item)
    return dict(out)


def asset_identity(rid: int, ordinal: int) -> str | None:
    if rid == 0x19:
        if ordinal == 0:
            return "tone_low"
        if ordinal == 1:
            return "tone_medium"
        if ordinal == 2:
            return "tone_high"
        return f"tone_table_occurrence_{ordinal}"
    return KNOWN_ASSET_IDS.get(rid)


def priority_for(rid: int, selector_names: list[str], asset: str | None) -> tuple[str, str]:
    names = " ".join(selector_names).lower()
    if rid in INVARIANT_CONTROLS:
        return "CONTROL_INVARIANT", "Known invariant control; retain as a comparison control."
    if rid in (0x15, 0x06, 0x0A) or "colorcorrection" in names:
        return "P0_MODEL_COLOR", "Direct CC0/CC1 color-conversion candidate."
    if "output" in names or "color_conversion" in names:
        return "P0_OUTPUT_COLOR", "Named output/output-color conversion candidate."
    if rid in (0x18, 0x13, 0x16) or "color_dif" in names or "chroma" in names:
        return "P1_CHROMA_SHAPING", "Named chroma/color-difference filtering or suppression candidate."
    if rid in (0x19, 0x1C, 0x1D, 0x08, 0x09) or asset in (
        "tone_low",
        "tone_medium",
        "tone_high",
        "dg_main",
        "dg_fl_anchors",
    ) or "tone" in names or "gamma" in names:
        return "P1_TONE_DG", "Tone/differential-gamma candidate; keep separate from color-matrix hypotheses."
    return "P2_OTHER", "Changed B2Y control requiring semantic mapping before renderer use."


PRIORITY_ORDER = {
    "P0_MODEL_COLOR": 0,
    "P0_OUTPUT_COLOR": 1,
    "P1_CHROMA_SHAPING": 2,
    "P1_TONE_DG": 3,
    "P2_OTHER": 4,
    "CONTROL_INVARIANT": 9,
}


def load_item(
    label: str,
    path: Path,
    firmware_sha: str,
    decoded_sha: str,
    identification: str,
) -> dict:
    blob = path.read_bytes()
    records = parse_records(blob)
    ordinal_by_id: dict[int, int] = defaultdict(int)

    table_dup_groups: dict[tuple[int, int, str], list[int]] = defaultdict(list)
    raw_records: list[tuple[object, int, bytes, str]] = []
    for rec in records:
        ordinal = ordinal_by_id[rec.record_id]
        ordinal_by_id[rec.record_id] += 1
        payload = blob[rec.payload_offset : rec.payload_offset + rec.size]
        digest = sha256(payload)
        raw_records.append((rec, ordinal, payload, digest))
        table_dup_groups[(rec.record_id, rec.size, digest)].append(rec.index)

    rows = []
    for rec, ordinal, payload, digest in raw_records:
        occs, truncated = exact_occurrences(blob, payload)
        duplicate_indices = table_dup_groups[(rec.record_id, rec.size, digest)]
        rows.append(
            {
                "key": f"0x{rec.record_id:02x}#{ordinal}",
                "record_table_index": rec.index,
                "record_id": f"0x{rec.record_id:02x}",
                "record_id_int": rec.record_id,
                "occurrence_ordinal": ordinal,
                "relative_offset": hexoff(rec.rel_offset),
                "payload_offset": hexoff(rec.payload_offset),
                "payload_size": rec.size,
                "payload_sha256": digest,
                "table_exact_duplicate_indices": duplicate_indices,
                "table_exact_duplicate": len(duplicate_indices) > 1,
                "raw_exact_payload_occurrences": [hexoff(x) for x in occs],
                "raw_exact_payload_occurrences_truncated": truncated,
                "raw_exact_duplicate_outside_self": any(x != rec.payload_offset for x in occs),
            }
        )

    return {
        "label": label,
        "b2y_path": str(path),
        "b2y_sha256": sha256(blob),
        "firmware_sha256": firmware_sha,
        "decoded_sha256": decoded_sha,
        "b2y_identification": identification,
        "record_count": len(records),
        "record_id_counts": {
            f"0x{rid:02x}": n for rid, n in sorted(Counter(r.record_id for r in records).items())
        },
        "records": rows,
    }


def pair_status(base: dict | None, target: dict | None) -> str:
    if base is None and target is None:
        return "absent"
    if base is None:
        return "added"
    if target is None:
        return "missing"
    if (
        base["payload_size"] == target["payload_size"]
        and base["payload_sha256"] == target["payload_sha256"]
    ):
        return "exact_equal"
    return "changed"


def structural_checks(items: dict[str, dict]) -> dict[str, dict]:
    all_ids = sorted(
        {
            int(rid, 16)
            for item in items.values()
            for rid in item["record_id_counts"].keys()
        }
    )
    by_label_records = {
        label: defaultdict(list)
        for label in items
    }
    for label, item in items.items():
        for r in item["records"]:
            by_label_records[label][r["record_id_int"]].append(r)

    out = {}
    for rid in all_ids:
        counts = {
            label: len(by_label_records[label][rid])
            for label in items
        }
        sizes = {
            label: [r["payload_size"] for r in by_label_records[label][rid]]
            for label in items
        }
        count_equal = len(set(counts.values())) == 1
        size_vectors = {tuple(v) for v in sizes.values()}
        sizes_equal = len(size_vectors) == 1
        repeated = max(counts.values(), default=0) > 1
        out[f"0x{rid:02x}"] = {
            "counts": counts,
            "size_vectors": sizes,
            "count_equal_all": count_equal,
            "size_vector_equal_all": sizes_equal,
            "repeated_id": repeated,
            "ordinal_alignment_warning": (not count_equal) or (repeated and not sizes_equal),
        }
    return out


def build_report(result: dict) -> str:
    labels = result["labels"]
    lines = [
        "# M10-R B2Y CROSSMODEL-DIFF1A",
        "",
        "Record-by-record M10-R vs M10 Monochrom B2Y calibration diff.",
        "",
        "This pass is research-only. It does not alter the Android renderer, exposure, POSTYC1A, WB, tone, GAMUT1A, TONECAL1A, JPEG quality, or Y_BLEND k.",
        "",
        "## Provenance",
        "",
        "| Firmware | FW SHA256 | Decoded SHA256 | B2Y SHA256 | Records |",
        "|---|---|---|---|---:|",
    ]
    for label in labels:
        item = result["items"][label]
        lines.append(
            f"| {label} | `{item['firmware_sha256']}` | `{item['decoded_sha256']}` | "
            f"`{item['b2y_sha256']}` | {item['record_count']} |"
        )

    s = result["summary"]
    lines += [
        "",
        "## Summary",
        "",
        f"- Exact-equal aligned records: **{s['exact_equal']}**",
        f"- Changed aligned records: **{s['changed']}**",
        f"- Keys with one or more missing/added occurrences: **{s['missing_or_added']}**",
        f"- Structural alignment warnings: **{s['structural_alignment_warnings']}**",
        "",
        "## Invariant controls",
        "",
    ]
    for key in ("0x0c#0", "0x0d#0"):
        row = next(r for r in result["records"] if r["key"] == key)
        lines.append(
            f"- `{key}` **{row['asset_identity'] or row['selector_names'][0]}** — "
            f"`{row['all_status']}`; M10-R vs latest Monochrom: "
            f"`{row['comparisons']['M10R_vs_M10M_3.21.2.50']}`."
        )

    lines += [
        "",
        "## Highest-priority differing records",
        "",
        "| Priority | Key | Asset | Selector/name mapping | All-three | M10-R vs M10M 3.21.2.50 | Sizes |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in result["priority_differences"]:
        mapping = ", ".join(row["selector_names"]) or "UNKNOWN"
        sizes = ", ".join(
            f"{label}:{(row['by_firmware'][label] or {}).get('payload_size','-')}"
            for label in labels
        )
        lines.append(
            f"| {row['priority']} | `{row['key']}` | {row['asset_identity'] or '-'} | "
            f"{mapping} | {row['all_status']} | "
            f"{row['comparisons']['M10R_vs_M10M_3.21.2.50']} | {sizes} |"
        )

    warnings = [
        rid for rid, v in result["structural_checks"].items()
        if v["ordinal_alignment_warning"]
    ]
    lines += ["", "## Structural alignment checks", ""]
    if warnings:
        lines.append(
            "Occurrence-ordinal alignment needs manual review for: "
            + ", ".join(f"`{x}`" for x in warnings)
            + "."
        )
    else:
        lines.append(
            "No repeated-ID count/size-vector conflict was found; occurrence-ordinal alignment is structurally consistent across the three inputs."
        )

    lines += [
        "",
        "## Interpretation boundary",
        "",
        "- A changed calibration record is evidence of model/version-specific B2Y state, not proof of its pixel arithmetic.",
        "- CC0/CC1 or output-color differences have highest value for the remaining skin/color mismatch.",
        "- Tone/DG differences are retained as separate tone hypotheses rather than being used to explain color by default.",
        "- Y_BLEND and YC CONVERSION remain invariant controls and are not promoted as model-specific color knobs.",
        "- No renderer change should be made until a differing record's selector/driver/runtime stage is traced and an offline reproduction is supported.",
        "",
        "## Next unresolved work",
        "",
        "1. Trace the highest-priority changed CC/output/chroma records through selector -> setter/driver -> registers.",
        "2. Determine whether each changed payload is copied directly, transformed, or selected conditionally.",
        "3. For tone/DG changes, compare decoded tables independently from color-control hypotheses.",
        "4. Reproduce any recovered control offline on existing captures before creating another Android renderer candidate.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventory", type=Path, required=True)
    ap.add_argument("--item", action="append", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()

    specs = [parse_item_spec(x) for x in args.item]
    labels = [x[0] for x in specs]
    if tuple(labels) != EXPECTED_LABELS:
        raise SystemExit(f"expected ordered labels {EXPECTED_LABELS}, got {tuple(labels)}")

    selector_inventory = parse_inventory(args.inventory)
    items = {
        label: load_item(label, path, fw_sha, dec_sha, ident)
        for label, path, fw_sha, dec_sha, ident in specs
    }
    checks = structural_checks(items)

    rec_index = {
        label: {r["key"]: r for r in item["records"]}
        for label, item in items.items()
    }
    all_keys = sorted(
        {key for rows in rec_index.values() for key in rows},
        key=lambda k: (int(k.split("#")[0], 16), int(k.split("#")[1])),
    )

    records = []
    for key in all_keys:
        rid_text, ordinal_text = key.split("#")
        rid = int(rid_text, 16)
        ordinal = int(ordinal_text)
        by_fw = {label: rec_index[label].get(key) for label in labels}
        present = [x for x in by_fw.values() if x is not None]
        all_present = len(present) == len(labels)
        sigs = {(x["payload_size"], x["payload_sha256"]) for x in present}
        if all_present and len(sigs) == 1:
            all_status = "exact_equal"
        elif all_present:
            all_status = "changed"
        else:
            all_status = "missing_or_added"

        mappings = selector_inventory.get(rid, [])
        selector_names = sorted({m["name"] for m in mappings if m["name"] != "UNKNOWN"})
        asset = asset_identity(rid, ordinal)
        priority, rationale = priority_for(rid, selector_names, asset)
        rec = {
            "key": key,
            "record_id": rid_text,
            "record_id_int": rid,
            "occurrence_ordinal": ordinal,
            "asset_identity": asset,
            "selector_names": selector_names,
            "selector_mappings": mappings,
            "priority": priority,
            "priority_rationale": rationale,
            "structural_alignment": checks[rid_text],
            "by_firmware": by_fw,
            "all_status": all_status,
            "comparisons": {
                "M10R_vs_M10M_2.12.8.0": pair_status(
                    by_fw[BASELINE], by_fw["M10M-2.12.8.0"]
                ),
                "M10R_vs_M10M_3.21.2.50": pair_status(
                    by_fw[BASELINE], by_fw["M10M-3.21.2.50"]
                ),
                "M10M_2.12.8.0_vs_3.21.2.50": pair_status(
                    by_fw["M10M-2.12.8.0"], by_fw["M10M-3.21.2.50"]
                ),
            },
        }
        records.append(rec)

    by_key = {r["key"]: r for r in records}
    for control in ("0x0c#0", "0x0d#0"):
        if control not in by_key:
            raise RuntimeError(f"missing required invariant control {control}")
        if by_key[control]["all_status"] != "exact_equal":
            raise RuntimeError(
                f"invariant control {control} changed: {by_key[control]['comparisons']}"
            )

    priority_diffs = [r for r in records if r["all_status"] != "exact_equal"]
    priority_diffs.sort(
        key=lambda r: (
            PRIORITY_ORDER.get(r["priority"], 99),
            r["record_id_int"],
            r["occurrence_ordinal"],
        )
    )

    summary_counts = Counter(r["all_status"] for r in records)
    result = {
        "schema": "M10R_B2Y_CROSSMODEL_DIFF1A_V1",
        "labels": labels,
        "alignment_key": "(record_id, occurrence_ordinal)",
        "items": items,
        "structural_checks": checks,
        "records": records,
        "priority_differences": priority_diffs,
        "summary": {
            "aligned_key_count": len(records),
            "exact_equal": summary_counts["exact_equal"],
            "changed": summary_counts["changed"],
            "missing_or_added": summary_counts["missing_or_added"],
            "structural_alignment_warnings": sum(
                1 for x in checks.values() if x["ordinal_alignment_warning"]
            ),
            "invariant_controls_verified": ["0x0c#0", "0x0d#0"],
        },
        "guardrails": [
            "No renderer or photographic tuning is performed by this tool.",
            "Occurrence ordinal is used only with structural count/size checks.",
            "Changed payloads identify candidate model/version controls, not hardware arithmetic.",
            "Y_BLEND and YC CONVERSION are explicit invariant controls.",
        ],
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(build_report(result), encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))
    for row in priority_diffs[:20]:
        print(
            row["priority"],
            row["key"],
            row["asset_identity"] or ",".join(row["selector_names"]) or "UNKNOWN",
            row["all_status"],
            row["comparisons"]["M10R_vs_M10M_3.21.2.50"],
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
