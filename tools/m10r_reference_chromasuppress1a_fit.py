#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageOps
import rawpy

from m10r_reference_order_fit import alignment_search,metadata_status
from m10r_reference_transfer_rgb_fit import crop_to_reference,metrics

MODES=(
    "baseline",
    "cs_20000_30000","cs_20000_40000","cs_20000_50000",
    "cs_30000_40000","cs_30000_50000","cs_40000_50000",
)

def load(p:Path):
    with Image.open(p) as im:
        return np.asarray(im.convert("RGB"),dtype=np.uint8)

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--jpg",type=Path,required=True)
    ap.add_argument("--dng",type=Path,required=True)
    ap.add_argument("--prefix",type=Path,required=True)
    ap.add_argument("--sample",required=True)
    ap.add_argument("--metadata-json",type=Path)
    ap.add_argument("--render-log",type=Path)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()

    with Image.open(a.jpg) as im:
        jpg=np.asarray(ImageOps.exif_transpose(im).convert("RGB"),dtype=np.uint8)

    rendered={m:load(Path(str(a.prefix)+"_"+m+".ppm")) for m in MODES}
    if len({v.shape for v in rendered.values()})!=1:
        raise RuntimeError("candidate geometry mismatch")

    with rawpy.imread(str(a.dng)) as x:
        z=x.postprocess(use_camera_wb=True,no_auto_bright=True,gamma=(1,1),
                        output_bps=16,output_color=rawpy.ColorSpace.raw)
        white=float(x.white_level);flip=int(x.sizes.flip)
    proxy=z[...,1].astype(np.float32)*(white/65535.0);del z

    orient,scores=alignment_search(proxy,jpg)
    score,k,dx,dy=scores[0]
    rh,rw=orient.shape;jh,jw=jpg.shape[:2]
    cropped={n:crop_to_reference(v,k,dx,dy,rw,rh,jw,jh) for n,v in rendered.items()}
    h,w=next(iter(cropped.values())).shape[:2]
    ref=np.asarray(Image.fromarray(jpg).resize((w,h),Image.Resampling.LANCZOS),dtype=np.uint8)
    if h>12 and w>12:
        ref=ref[3:-3,3:-3]
        cropped={n:v[3:-3,3:-3] for n,v in cropped.items()}

    render_log=a.render_log.read_text(errors="replace") if a.render_log and a.render_log.exists() else ""
    out={
        "sample":a.sample,
        "metadata":metadata_status(a.metadata_json),
        "fit_freedom":"NONE; thresholds fixed to firmware values; csum normalization hypothesis fixed at (abs(Cb)+abs(Cr))*65536; RGB1G upstream fixed",
        "hypothesis":{
            "family":"Fujitsu-style low-chroma linear ramp; external architecture hypothesis, not Leica arithmetic proof",
            "csum_code":"(abs(Cb)+abs(Cr))*65536",
            "threshold_pairs":[[20000,30000],[20000,40000],[20000,50000],[30000,40000],[30000,50000],[40000,50000]],
            "gain":"0 below inner; 1 above outer; linear between",
            "placement":"exact recovered YC domain; after Y MEDIUM->DG value is computed, before mathematical YC inverse; Cb/Cr only",
        },
        "alignment":{
            "score":float(score),"rot90_k":int(k),"dx":int(dx),"dy":int(dy),
            "rawpy_flip":flip,"raw_oriented":[rw,rh],"jpeg":[jw,jh],
        },
        "render_log":render_log.strip(),
        "metrics":{n:metrics(v,ref) for n,v in cropped.items()},
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
