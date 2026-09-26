#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from m10r_b2y_assets import parse_records,RECORD_HEADER_OFF,RECORD_STRIDE

RID=0x0d
def sha(b):return hashlib.sha256(b).hexdigest()
def u32(b,o):return struct.unpack_from("<I",b,o)[0]
def keystr(raw):return raw.split(b"\0",1)[0].decode("latin1","replace")
def spec(s):
    a=s.split("|",2)
    if len(a)!=3:raise ValueError("--item LABEL|B2Y|FW_SHA")
    return a[0],Path(a[1]),a[2]

def load(label,path,fwsha):
    data=path.read_bytes();recs=parse_records(data);out=[]
    for r in recs:
        if r.record_id!=RID:continue
        h=RECORD_HEADER_OFF+r.index*RECORD_STRIDE
        n=u32(data,h+0x0c)
        keys=[keystr(data[h+0x10+i*0x40:h+0x10+(i+1)*0x40]) for i in range(n)]
        p=data[r.payload_offset:r.payload_offset+r.size]
        words=[u32(p,o) for o in range(0,len(p)//4*4,4)]
        out.append({"table_index":r.index,"payload_offset":hex(r.payload_offset),"size":r.size,
                    "payload_sha256":sha(p),"payload_hex":p.hex(),"u32_words":words,"keys":keys})
    return {"label":label,"firmware_sha256":fwsha,"b2y_sha256":sha(data),"records_0x0d":out}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--item",action="append",required=True);ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    items=[load(*spec(x)) for x in a.item]
    normal=[0,32,0x3fff,0x3fff,0x3fff,0x3fff]
    result={"schema":"M10R_YBLEND_CROSSCOLOR1D_V1","record_id":"0x0d","normal_reference":normal,"items":items}
    for x in items:
        x["exact_normal_records"]=sum(1 for r in x["records_0x0d"] if r["u32_words"]==normal)
        x["distinct_payloads"]=sorted(set(r["payload_sha256"] for r in x["records_0x0d"]))
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+"\n")
    for x in items:
        print("\n",x["label"],"record0D",len(x["records_0x0d"]),"exact_normal",x["exact_normal_records"])
        for r in x["records_0x0d"]:
            print(" idx",r["table_index"],"size",r["size"],"words",r["u32_words"],"keys",r["keys"][:8])
if __name__=="__main__":main()
