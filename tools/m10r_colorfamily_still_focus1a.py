#!/usr/bin/env python3
import json
from pathlib import Path

src=Path("research/generated/M10_FAMILY_B2Y_COLORFAMILYDIFF1A.json")
d=json.loads(src.read_text())
targets={"0x08","0x1a","0x16","0x0f","0x1c","0x1d","0x05","0x09"}
rows=[]
for x in d["records"]:
    if not x.get("m10r_specific_changed"): continue
    if x.get("record_id") not in targets: continue
    key=x.get("key")
    scope=x.get("scope")
    if not (scope in ("STILL","NO_KEY") or (key and "_B2YMODE:STILL" in key)): continue
    rows.append({
        "record_id":x.get("record_id"),
        "selector_names":x.get("selector_names"),
        "key":key,
        "scope":scope,
        "m10r":x["by_firmware"].get("M10R-30.22.23.34"),
        "m10":x["by_firmware"].get("M10-3.22.23.38"),
        "m10p":x["by_firmware"].get("M10P-4.22.23.34"),
    })
rows.sort(key=lambda x:(x["record_id"],x["key"] or ""))
out={"schema":"M10R_COLORFAMILY_STILL_FOCUS1A_V1","rows":rows}
Path("research/generated/M10R_COLORFAMILY_STILL_FOCUS1A.json").write_text(json.dumps(out,indent=2)+"\n")
for x in rows:
    print(f"{x['record_id']}|{','.join(x['selector_names'] or [])}|{x['key']}")
