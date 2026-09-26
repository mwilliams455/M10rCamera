#!/usr/bin/env python3
"""POSTYCNEUTRAL1A — preserve RENDER1T exact-neutral invariant on RENDER2C.

Single pixel-path change vs RENDER2C:
- COLORRECON still uses post-Yc reconstructed nr/ng/nb for every non-neutral pixel.
- When the original pre-tone working input is exactly achromatic (lr==lg==lb),
  feed lr/lg/lb to COLORRECON so its established neutral bypass remains exact.

No exposure, WB, source, MFM, YBLEND k, tone, CC1, GAMUT1A, TONECAL1A,
JPEG, DNG or capture changes.
"""
from pathlib import Path
import json,re,sys

def once(s,a,b):
    n=s.count(a)
    if n!=1:
        raise RuntimeError("Unique anchor required (%d): %s"%(n,a[:180]))
    return s.replace(a,b,1)

def patch_cpp(s):
    old='''            const unsigned colorFlags=m10r_colorrecon1a::apply(
                    nr,ng,nb,outMat,legacyOutR,legacyOutG,legacyOutB,
                    tone,dgt,outR,outG,outB,&skinTraceColor);
'''
    new='''            // POSTYCNEUTRAL1A: POSTYC1A keeps its recovered post-Yc
            // colour direction for non-neutral pixels, but the neutral decision
            // remains tied to the original pre-tone working RGB so numerical
            // Yc round-trip residue cannot defeat COLORRECON's exact-neutral bypass.
            const bool postYcNeutralPreserve=(lr==lg && lg==lb);
            const unsigned colorFlags=m10r_colorrecon1a::apply(
                    postYcNeutralPreserve?lr:nr,
                    postYcNeutralPreserve?lg:ng,
                    postYcNeutralPreserve?lb:nb,
                    outMat,legacyOutR,legacyOutG,legacyOutB,
                    tone,dgt,outR,outG,outB,&skinTraceColor);
'''
    return once(s,old,new)

def patch_java(s):
    edits={
      '"RENDER2C_COLORRECON1B_POSTYC1A_GAMUT1A_TONECAL1A_EDGE0A"':
        '"RENDER2E_COLORRECON1B_POSTYCNEUTRAL1A_GAMUT1A_TONECAL1A_EDGE0A"'
    }
    for a,b in edits.items():
        s=once(s,a,b)
    marker='            d.put("colorRecon1BPostYc1A", new JSONObject()'
    if marker not in s: raise RuntimeError("POSTYC1A diagnostic marker missing")
    diag='''            d.put("postYcNeutral1A", new JSONObject()
                    .put("enabled", true)
                    .put("onlyPhotographicVariableVsRender2C",
                            "exact_preTone_working_neutral_uses_original_COLORRECON_neutral_bypass")
                    .put("nonNeutralPostYcColourDirectionChanged", false)
                    .put("yBlendKChanged", false)
                    .put("cc1Changed", false)
                    .put("lightnessAnchorChanged", false)
                    .put("shoulderChanged", false)
                    .put("gamutMappingChanged", false)
                    .put("toneCalChanged", false)
                    .put("captureExposureChanged", false)
                    .put("whiteBalanceChanged", false)
                    .put("sourceProcessingChanged", false));
'''
    return s.replace(marker,diag+marker,1)

def main():
    if len(sys.argv)!=2:
        raise SystemExit("usage: fix-m10r-render2e-postycneutral1a.py <PhotonCamera-root>")
    root=Path(sys.argv[1]).resolve()
    cpp=root/"app/src/main/cpp/m10rRender.cpp"
    java=root/"app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java"
    gradle=root/"app/build.gradle"
    for p in (cpp,java,gradle):
        if not p.is_file(): raise RuntimeError("missing "+str(p))
    cb=cpp.read_text(); jb=java.read_text()
    if "COLORRECON1B POSTYC1A" not in cb or '"colorRecon1BPostYc1A"' not in jb:
        raise RuntimeError("RENDER2C baseline anchors missing")
    cpp.write_text(patch_cpp(cb))
    java.write_text(patch_java(jb))
    g=gradle.read_text()
    versions=re.findall(r'versionName\s+[\'"]([^\'"]+)[\'"]',g)
    if len(versions)!=1 or versions[0]!="0.97-m10r2c-postyc1a":
        raise RuntimeError("unexpected RENDER2C versionName: %r"%versions)
    version="0.97-m10r2e-postycneutral1a"
    gradle.write_text(g.replace(versions[0],version,1))
    proof={
      "schema":"RENDER2E_POSTYCNEUTRAL1A_PATCH_V1",
      "baseline":"RENDER2C_COLORRECON1B_POSTYC1A",
      "versionName":version,
      "photographicChange":"restore_exact_preTone_neutral_selector_for_COLORRECON_bypass",
      "nonNeutralPostYcPathChanged":False,
      "neutralInvariantRestored":True,
      "captureExposureChanged":False,
      "whiteBalanceChanged":False,
      "sourceProcessingChanged":False,
      "mfm1bChanged":False,
      "yBlendKChanged":False,
      "cc1Changed":False,
      "shoulderChanged":False,
      "gamutMappingChanged":False,
      "toneCalChanged":False,
      "deviceValidated":False,
      "productionPromoted":False
    }
    (root/"M10R_RENDER2E_POSTYCNEUTRAL1A_PROVENANCE.json").write_text(json.dumps(proof,indent=2)+"\n")
    print(json.dumps(proof,indent=2))

if __name__=="__main__": main()
