#!/usr/bin/env python3
"""RENDER2F WARMRED1B on top of RENDER2B/MFM1B/SKINTRACE1A.

Photographic change:
- exact RENDER1T/RENDER2B pixels remain unchanged unless WARMRED1B selects
  a stable warm highlight red-peak pixel;
- selected pixels use the public-reference-screened warm075_red085
  luminance-preserving opponent compression.

No change to capture exposure, MFM1B, source/WB/CA9, YBLEND k=0.35,
tone/DG, CC1 matrix, GAMUT1A, TONECAL1A, JPEG quality or DNG.
"""
from pathlib import Path
import json,re,shutil,sys

COUNT_APPLIED=194
COUNT_SCALE=195
COUNT_REDCODE=196
COUNT_MAPPEDY=197
COUNT_RELCR=198
SCALE=1000000.0

def once(s,a,b):
    n=s.count(a)
    if n!=1:
        raise RuntimeError("Unique anchor required (%d): %s"%(n,a[:180]))
    return s.replace(a,b,1)

def patch_cpp(s):
    if "SKINTRACE1A" not in s or "m10r_colorrecon1a::Trace skinTraceColor" not in s:
        raise RuntimeError("RENDER2B SKINTRACE1A C++ anchors missing")
    s=once(s,'#include "m10rColorRecon1A.h"',
              '#include "m10rColorRecon1A.h"\n#include "m10rWarmRed1B.h"')
    old='''            double outR,outG,outB;
            m10r_colorrecon1a::Trace skinTraceColor;
            const unsigned colorFlags=m10r_colorrecon1a::apply(
                    lr,lg,lb,outMat,legacyOutR,legacyOutG,legacyOutB,
                    tone,dgt,outR,outG,outB,&skinTraceColor);
'''
    new='''            double outR,outG,outB;
            m10r_colorrecon1a::Trace skinTraceColor;
            const unsigned colorFlags=m10r_colorrecon1a::apply(
                    lr,lg,lb,outMat,legacyOutR,legacyOutG,legacyOutB,
                    tone,dgt,outR,outG,outB,&skinTraceColor);

            // WARMRED1B: exact RENDER2B bypass unless the screened
            // warm075_red085 selector fires.
            m10r_warmred1b::Trace warmRedTrace;
            const bool warmRedApplied=m10r_warmred1b::apply(
                    lr,lg,lb,outMat,legacyOutR,legacyOutG,legacyOutB,
                    mappedY,mappedCr,outR,outG,outB,&warmRedTrace);
            if(warmRedApplied) {
                cnt.v[194]++;
                cnt.v[195]+=static_cast<int64_t>(std::llround(
                        warmRedTrace.opponentScale*1000000.0));
                cnt.v[196]+=static_cast<int64_t>(std::llround(
                        warmRedTrace.redCode*1000000.0));
                cnt.v[197]+=static_cast<int64_t>(std::llround(
                        warmRedTrace.mappedY*1000000.0));
                cnt.v[198]+=static_cast<int64_t>(std::llround(
                        warmRedTrace.relCr*1000000.0));
            }
'''
    return once(s,old,new)

def patch_java(s):
    if '"skinTrace1A"' not in s or 'final long[] nativeExactCounts = new long[208];' not in s:
        raise RuntimeError("RENDER2B Java anchors missing")
    s=once(s,
      '"RENDER1T_COLORRECON1A_GAMUT1A_TONECAL1A_EDGE0A"',
      '"RENDER2F_WARMRED1B_MFM1B_RENDER1T_GAMUT1A_TONECAL1A_EDGE0A"')
    marker='            d.put("skinTrace1A", new JSONObject()'
    diag='''            final long warmRedAppliedPixels=nativeExactCounts[194];
            d.put("warmRed1B", new JSONObject()
                    .put("enabled", true)
                    .put("empiricalNotFirmware", true)
                    .put("candidate", "warm075_red085")
                    .put("baseline", "RENDER2B_MFM1B_RENDER1T")
                    .put("selector",
                            "mappedY_ge_0p75_relCr_ge_0p04_red_peak_requested_red_code_gt_0p85")
                    .put("nonSelectedPixelPolicy", "exact_RENDER2B")
                    .put("selectedOperation",
                            "linear_lightness_anchor_opponent_scale_then_existing_GAMUT1A_TONECAL1A")
                    .put("appliedPixels", warmRedAppliedPixels)
                    .put("appliedFraction",
                            warmRedAppliedPixels/(double)((long)frame.width*frame.height))
                    .put("meanOpponentScale",
                            warmRedAppliedPixels>0 ? nativeExactCounts[195]/1000000.0/warmRedAppliedPixels : 1.0)
                    .put("meanRequestedRedCode",
                            warmRedAppliedPixels>0 ? nativeExactCounts[196]/1000000.0/warmRedAppliedPixels : 0.0)
                    .put("meanMappedY",
                            warmRedAppliedPixels>0 ? nativeExactCounts[197]/1000000.0/warmRedAppliedPixels : 0.0)
                    .put("meanRelCr",
                            warmRedAppliedPixels>0 ? nativeExactCounts[198]/1000000.0/warmRedAppliedPixels : 0.0)
                    .put("captureExposureChanged", false)
                    .put("mfm1bChanged", false)
                    .put("whiteBalanceChanged", false)
                    .put("sourceProcessingChanged", false)
                    .put("yBlendKChanged", false)
                    .put("cc1Changed", false)
                    .put("gamutMappingChanged", false)
                    .put("toneCalChanged", false)
                    .put("privatePhotoFixtureCommitted", false)
                    .put("deviceValidated", false)
                    .put("productionPromoted", false));
'''
    return s.replace(marker,diag+marker,1)

def main():
    if len(sys.argv)!=2:
        raise SystemExit("usage: fix-m10r-render2f-warmred1b.py <PhotonCamera-root>")
    root=Path(sys.argv[1]).resolve()
    repo=Path(__file__).resolve().parents[1]
    cpp=root/"app/src/main/cpp/m10rRender.cpp"
    hdr=root/"app/src/main/cpp/m10rWarmRed1B.h"
    java=root/"app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java"
    gradle=root/"app/build.gradle"
    for p in (cpp,java,gradle):
        if not p.is_file(): raise RuntimeError("missing "+str(p))
    cpp_before=cpp.read_text(); java_before=java.read_text()
    cpp.write_text(patch_cpp(cpp_before))
    java.write_text(patch_java(java_before))
    shutil.copy2(repo/"native/m10rWarmRed1B.h",hdr)

    g=gradle.read_text()
    versions=re.findall(r'versionName\s+[\'"]([^\'"]+)[\'"]',g)
    if len(versions)!=1 or versions[0]!="0.97-m10r2b-skintrace1a":
        raise RuntimeError("unexpected RENDER2B versionName: %r"%versions)
    version="0.97-m10r2f-warmred1b"
    gradle.write_text(g.replace(versions[0],version,1))

    proof={
      "schema":"RENDER2F_WARMRED1B_PATCH_V1",
      "baseline":"RENDER2B_SKINTRACE1A_on_RENDER2A_MFM1B_on_RENDER1T",
      "versionName":version,
      "screenedCandidate":"warm075_red085",
      "screenBranch":"m10r-warmred1b-screen",
      "screenStatus":"PASS_WARMRED1B_SCREEN",
      "selector":"mappedY>=0.75 && relCr>=0.04 && redPeak && requestedRedCode>0.85",
      "nonSelectedPixelPolicy":"exact_RENDER2B",
      "selectedOperation":"luminance_preserving_opponent_compression",
      "captureExposureChanged":False,
      "mfm1bChanged":False,
      "whiteBalanceChanged":False,
      "sourceProcessingChanged":False,
      "yBlendKChanged":False,
      "cc1Changed":False,
      "gamutMappingChanged":False,
      "toneCalChanged":False,
      "jpegQualityChanged":False,
      "dngChanged":False,
      "privatePhotoFixtureCommitted":False,
      "deviceValidated":False,
      "productionPromoted":False
    }
    (root/"M10R_RENDER2F_WARMRED1B_PROVENANCE.json").write_text(json.dumps(proof,indent=2)+"\n")
    print(json.dumps(proof,indent=2))

if __name__=="__main__":
    main()
