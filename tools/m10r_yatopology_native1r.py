#!/usr/bin/env python3
"""Native full-chain validation of YA_TOPOLOGY1A on public Leica M10-R pairs.

Candidate:
  working RGB
  -> TCYC-derived MEDIUM tone gain applied uniformly to RGB
  -> recovered DG curve independently on R/G/B
  -> recovered CC1
  -> unchanged RENDER1S GAMUT1A + TONECAL1A

No Yc chroma scaling, no main-line Yb substitution, no COLORRECON shoulder.
"""
from pathlib import Path
import argparse,hashlib,json,statistics
import numpy as np
from PIL import Image
import m10r_colorrecon1a_validate as v
import m10r_photoaudit_measure1a as a
import m10r_tonecal1a_validate as t

OLD='''            // LOOK1A YC1A: exact firmware Yc_Convert 3x3 coefficients, Q12.
            const double y  = (1224.0*lr + 2403.0*lg + 469.0*lb) / 4096.0;
            const double cb = (-691.0*lr - 1357.0*lg + 2048.0*lb) / 4096.0;
            const double cr = (2048.0*lr - 1715.0*lg - 333.0*lb) / 4096.0;
            const int xy = toneInput(y, cnt);
            const int my = medium(xy, tone);
            const int dy = dg(my, dgt, cnt);
            const double mappedY = dy / static_cast<double>(DG_OUT_MAX);

            // LOOK1B YC1B: until Y_BLEND is decoded, preserve chroma relative
            // to Y rather than freezing absolute Cb/Cr. LOOK1A demonstrated
            // that absolute preservation strongly desaturates when tone raises Y.
            const double yRatio = y > 1.0e-12 ? mappedY / y : 0.0;
            // RENDER1N YBLEND1A controlled reconstruction experiment. mappedY
            // remains exactly the frozen MEDIUM/DG output. Only Cb/Cr use the
            // midpoint carrier between input Y and mapped Y.
            // RENDER1Q YBLEND1B_K035 controlled probe. mappedY, Yc inverse,
            // CC1MAP1A and direct output are frozen; only chroma gain changes.
            const double yBlendChromaScale = y > 1.0e-12 ? 1.0 + 0.35 * (yRatio - 1.0) : 0.0;
            const double mappedCb = cb * yBlendChromaScale;
            const double mappedCr = cr * yBlendChromaScale;
            const double nr = 1.000000000000*mappedY - 0.001043337611*mappedCb + 1.401991725445*mappedCr;
            const double ng = 1.000000000000*mappedY - 0.345114690199*mappedCb - 0.714098755336*mappedCr;
            const double nb = 1.000000000000*mappedY + 1.770975790582*mappedCb - 0.000124867533*mappedCr;
'''
NEW='''            // YA_TOPOLOGY1A: firmware-shaped nonlinear sandwich.
            // M10-R tone descriptor: RGB tone enabled, Yb tone disabled,
            // TCYC = {1024,2661,410}/4096. MAINBLEND1N reference evidence
            // strongly favors Ya (post-RGB nonlinear luminance) for main output.
            const double ytc = (1024.0*lr + 2661.0*lg + 410.0*lb) / 4096.0;
            const int xy = toneInput(ytc, cnt);
            const int my = medium(xy, tone);
            const double toneY = my / static_cast<double>(INPUT_MAX);
            const double toneGain = ytc > 1.0e-12 ? toneY / ytc : 0.0;

            const double toneR = lr * toneGain;
            const double toneG = lg * toneGain;
            const double toneB = lb * toneGain;

            // DG common-table candidate applied independently to RGB components.
            // This is the topology supported by TOPOLOGY1K/MAINBLEND1N;
            // exact ASIC table-bank routing remains a separate proof boundary.
            const int xr = toneInput(toneR, cnt);
            const int xg = toneInput(toneG, cnt);
            const int xb = toneInput(toneB, cnt);
            const int dr = dg(xr, dgt, cnt);
            const int dgG = dg(xg, dgt, cnt);
            const int db = dg(xb, dgt, cnt);
            const double nr = dr / static_cast<double>(DG_OUT_MAX);
            const double ng = dgG / static_cast<double>(DG_OUT_MAX);
            const double nb = db / static_cast<double>(DG_OUT_MAX);
'''

def patch_topology(s):
    if s.count(OLD)!=1:
        raise RuntimeError("YA_TOPOLOGY1A nonlinear anchor count=%d"%s.count(OLD))
    out=s.replace(OLD,NEW,1)
    if "0.35 * (yRatio - 1.0)" in out:
        raise RuntimeError("empirical k path remained")
    return out

def sha_text(s): return hashlib.sha256(s.encode()).hexdigest()

def mean(rows,variant,key,group="all"):
    return float(np.mean([r[variant][group][key] for r in rows]))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("inputs",type=Path);ap.add_argument("out",type=Path)
    args=ap.parse_args();inp=args.inputs.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    repo=Path(__file__).resolve().parents[1]

    q=(inp/"source/m10rRender.cpp").read_text()
    r=v.load("rp",repo/"patches/fix-m10r-render1r-tonecal1a.py").patch_cpp(q)
    s=v.load("sp",repo/"patches/fix-m10r-render1s-gamut1a.py").patch_cpp(r)
    tcpp=v.load("tp",repo/"patches/fix-m10r-render1t-colorrecon1a.py").patch_cpp(s)
    cand=patch_topology(s)

    S=v.compile_native(repo,out,s,"host_s")
    T=v.compile_native(repo,out,tcpp,"host_t")
    C=v.compile_native(repo,out,cand,"host_c")

    js=(inp/"source/M10RNativeRenderer.java").read_text()
    dst=a.constant(js,"DEFAULT_SRGB_CC1").reshape(3,3)
    tone=np.fromfile(inp/"assets/tone_medium_q15.u32le",dtype="<u4").astype(np.int32)
    dg=np.fromfile(inp/"assets/dg_expanded_u16le.bin",dtype="<u2").astype(np.int32)
    eye=np.eye(3)

    result={
      "schema":"M10R_YA_TOPOLOGY_NATIVE1R_V1",
      "status":"RUNNING",
      "source_commit":__import__("os").environ.get("GITHUB_SHA"),
      "cpp_sha256":{"render1s":sha_text(s),"render1t":sha_text(tcpp),"candidate":sha_text(cand)},
      "candidate":{
        "tone_luma":"TCYC_Q12_1024_2661_410",
        "tone_application":"common_gain_preserve_working_RGB_ratios",
        "dg_application":"same_recovered_curve_independently_R_G_B",
        "main_y":"Ya_post_RGB_nonlinear",
        "yb_mainline_contribution":0,
        "empirical_chroma_k":None,
        "colorrecon":False,
        "gamut1a":"unchanged",
        "tonecal1a":"unchanged",
        "cc1":"unchanged_factory_sRGB",
      },
      "splits":{"development":["01","03","05"],"historical":["02","04","06"],"fresh_holdout":["07","08","09","10"]},
      "cases":{}
    }

    for sid in [f"{i:02d}" for i in range(1,11)]:
        sample,ref,ca,work,wy,meta=v.data(sid,inp,js)
        scene={"metadata":meta,"whiteY":wy,"conditions":{}}
        for mode,scale in [("target_native",1.0),("white_normalized_control",1.0/wy)]:
            src=eye*scale
            simg,sc,_,_=v.native(S,sample,src,ca,work,dst,tone,dg)
            timg,tc,_,_=v.native(T,sample,src,ca,work,dst,tone,dg)
            cimg,cc,_,_=v.native(C,sample,src,ca,work,dst,tone,dg)
            if mode=="target_native":
                al=t.align(simg,ref);scene["alignment"]=al
            rows={}
            rp=None;patches=None
            for name,img,cnt in [("render1s",simg,sc),("render1t",timg,tc),("candidate",cimg,cc)]:
                aa,rr=t.view(img,ref,al);pa,pr,npats=a.patch_values(aa,rr)
                if rp is None: rp=pr;patches=npats
                else: assert np.array_equal(rp,pr) and patches==npats
                rows[name]={"all":a.groups(pa,pr)["all"],"neutral":a.groups(pa,pr)["neutral"],"patches":npats,"counts":cnt.tolist()}
                if mode=="target_native" and sid in ("02","04","06","07","08","09","10"):
                    Image.fromarray(aa).save(out/f"{sid}_{name}.jpg",quality=94)
            scene["conditions"][mode]=rows
            print(sid,mode,
                  "S",round(rows["render1s"]["all"]["DE76_mean"],4),
                  "T",round(rows["render1t"]["all"]["DE76_mean"],4),
                  "C",round(rows["candidate"]["all"]["DE76_mean"],4),
                  "C_ab",round(rows["candidate"]["all"]["ab_error_mean"],4),
                  "C_L",round(rows["candidate"]["all"]["L_mae"],4),flush=True)
        result["cases"][sid]=scene
        (out/"results.json").write_text(json.dumps(result,indent=2)+"\n")

    summary={}
    for split,ids in result["splits"].items():
        summary[split]={}
        for mode in ("target_native","white_normalized_control"):
            rr=[result["cases"][sid]["conditions"][mode] for sid in ids]
            m={}
            for var in ("render1s","render1t","candidate"):
                m[var]={
                    "L_mae":mean(rr,var,"L_mae"),
                    "ab_error":mean(rr,var,"ab_error_mean"),
                    "DE76":mean(rr,var,"DE76_mean"),
                    "neutral_L_mae":mean(rr,var,"L_mae","neutral"),
                }
            m["candidate_vs_render1s"]={
                "L_delta":m["candidate"]["L_mae"]-m["render1s"]["L_mae"],
                "ab_ratio":m["candidate"]["ab_error"]/m["render1s"]["ab_error"],
                "DE_ratio":m["candidate"]["DE76"]/m["render1s"]["DE76"],
            }
            m["candidate_vs_render1t"]={
                "L_delta":m["candidate"]["L_mae"]-m["render1t"]["L_mae"],
                "ab_ratio":m["candidate"]["ab_error"]/m["render1t"]["ab_error"],
                "DE_ratio":m["candidate"]["DE76"]/m["render1t"]["DE76"],
            }
            summary[split][mode]=m
    result["summary"]=summary
    result["status"]="PASS_YA_TOPOLOGY_NATIVE1R_EXECUTION"
    (out/"results.json").write_text(json.dumps(result,indent=2)+"\n")

    lines=["# M10-R YA_TOPOLOGY NATIVE1R","",
      "Full native-chain public reference test. Candidate changes only the nonlinear working-RGB path; RENDER1S CC1, GAMUT1A and TONECAL1A are frozen.","",
      "## Fresh holdout 07–10 / target native",""]
    m=summary["fresh_holdout"]["target_native"]
    lines += [
      f"- RENDER1S: L={m['render1s']['L_mae']:.3f}, ab={m['render1s']['ab_error']:.3f}, DE={m['render1s']['DE76']:.3f}",
      f"- RENDER1T: L={m['render1t']['L_mae']:.3f}, ab={m['render1t']['ab_error']:.3f}, DE={m['render1t']['DE76']:.3f}",
      f"- YA_TOPOLOGY: L={m['candidate']['L_mae']:.3f}, ab={m['candidate']['ab_error']:.3f}, DE={m['candidate']['DE76']:.3f}",
      f"- Candidate vs RENDER1S: {m['candidate_vs_render1s']}",
      f"- Candidate vs RENDER1T: {m['candidate_vs_render1t']}",
      "",
      "No APK is authorized by this execution alone. Exact M10-R DG bank semantics remain an evidence boundary."
    ]
    (out/"REPORT.md").write_text("\n".join(lines)+"\n")
    print(json.dumps(summary,indent=2))

if __name__=="__main__": main()
