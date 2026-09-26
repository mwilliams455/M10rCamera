#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path

def u32(b,o):
    return struct.unpack_from("<I",b,o)[0] if 0<=o<=len(b)-4 else None

def permutation_offsets(b,limit=0x10000):
    want=set(range(256));out=[]
    hi=min(limit,len(b)-256)
    # Leica table is aligned in the known M10-R container; scan 4-byte positions first.
    for o in range(0,hi+1,4):
        x=b[o:o+256]
        if len(set(x))==256 and set(x)==want:
            out.append(o)
    return out

def descriptor_tables(b,limit=0x10000):
    out=[];hi=min(limit,len(b)-8*16)
    for st in range(0,hi+1,4):
        rows=[];ok=True
        for i in range(8):
            e=st+i*16
            tag=u32(b,e);ro=u32(b,e+4);ps=u32(b,e+8);us=u32(b,e+12)
            if None in (tag,ro,ps,us) or ro==0 or ps==0 or us==0:
                ok=False;break
            # permit absolute or relative offsets; reject obviously impossible lengths
            if ps>len(b) or us>64*1024*1024:
                ok=False;break
            rows.append((tag,ro,ps,us))
        if not ok: continue
        # Known Leica codec rows have MB-scale uncompressed chunks and compressed sizes.
        if sum(1 for _,_,ps,us in rows if 0x10000<=ps<=32*1024*1024 and 0x10000<=us<=32*1024*1024)>=6:
            out.append((st,rows))
    return out[:100]

def ascii_runs(b,limit=0x2000,minlen=8):
    out=[];i=0;hi=min(limit,len(b))
    while i<hi:
        if 32<=b[i]<127:
            j=i
            while j<hi and 32<=b[j]<127:j+=1
            if j-i>=minlen:out.append((i,b[i:j].decode("ascii","replace")))
            i=j
        else:i+=1
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--item",action="append",required=True,help="LABEL|PATH")
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    result={"schema":"M10_FAMILY_FW_CONTAINER_PROBE1A_V1","items":{}}
    for spec in a.item:
        label,path=spec.split("|",1);b=Path(path).read_bytes()
        perms=permutation_offsets(b)
        tabs=descriptor_tables(b)
        result["items"][label]={
            "size":len(b),"sha256":hashlib.sha256(b).hexdigest(),
            "first_256_hex":b[:256].hex(),
            "u32_first_0x200":[{"off":hex(o),"value":hex(u32(b,o))} for o in range(0,min(0x200,len(b)-3),4)],
            "permutation_offsets":[hex(x) for x in perms],
            "descriptor_candidates":[{"start":hex(st),"rows":[[hex(x) for x in row] for row in rows]} for st,rows in tabs],
            "ascii_runs":[{"off":hex(o),"text":s} for o,s in ascii_runs(b)],
        }
        print(label,"size",len(b),"perm",[hex(x) for x in perms[:20]],"tables",[hex(x[0]) for x in tabs[:20]])
        for o,s in ascii_runs(b):
            print(label,"ASCII",hex(o),repr(s))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2)+"\n")
if __name__=="__main__":main()
