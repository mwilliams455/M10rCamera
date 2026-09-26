#!/usr/bin/env python3
"""RENDER2G YA_TOPOLOGY1A live candidate on top of frozen RENDER2A/MFM1B.

Photographic change vs RENDER2A:
- remove empirical COLORRECON1A from the live photographic path;
- remove empirical YBLEND1B k=0.35 chroma scaling;
- use the public-reference-validated YA_TOPOLOGY1A nonlinear core:
    working RGB
    -> TCYC-derived MEDIUM tone common gain
    -> recovered DG independently on R/G/B
    -> frozen factory-sRGB CC1
    -> unchanged GAMUT1A
    -> unchanged TONECAL1A.

Capture/exposure/MFM1B, source/WB/CA9, demosaic, JPEG quality, single RAW and
HDR-off policy are unchanged.

The native output is required to be byte-for-byte source-identical to the
candidate C++ validated in GitHub Actions run 36244571736.
"""
from pathlib import Path
import hashlib,json,re,sys

RENDER1T_CPP_SHA="880ce125413bdf1e0f56fbbdcc56591ba91e794f9b5281488f63353dca724637"
RENDER1S_CPP_SHA="af0d5fb85b5df55a00b7765f58ca96d5484900333e552c1591f99e5cb31f3895"
VALIDATED_CPP_SHA="3f7b696cdf33e29348d7c0532f658c11819f9b8e54772b55753e357fb6018985"
VALIDATION_RUN_ID="36244571736"
VALIDATION_COMMIT="6852a749a9882d65083c81366d98d84a27b94a2c"

OLD_TOPOLOGY='''            // LOOK1A YC1A: exact firmware Yc_Convert 3x3 coefficients, Q12.
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

NEW_TOPOLOGY='''            // YA_TOPOLOGY1A: firmware-shaped nonlinear sandwich.
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

COLOR_BLOCK='''            // The legacy reconstruction supplies only the S lightness anchor.
            // Actual colour is reconstructed from pre-tone working RGB.
            double outR,outG,outB;
            const unsigned colorFlags=m10r_colorrecon1a::apply(
                    lr,lg,lb,outMat,legacyOutR,legacyOutG,legacyOutB,
                    tone,dgt,outR,outG,outB);
            cnt.v[24]++;
            cnt.v[25]+=(colorFlags&1u)!=0;
            cnt.v[26]+=(colorFlags&2u)!=0;
            cnt.v[27]+=(colorFlags&4u)!=0;
            double gamutR=outR, gamutG=outG, gamutB=outB;'''

def sha_text(s): return hashlib.sha256(s.encode()).hexdigest()

def once(s,a,b,label):
    n=s.count(a)
    if n!=1:
        raise RuntimeError("%s anchor count=%d" % (label,n))
    return s.replace(a,b,1)

def reverse_colorrecon_to_render1s(s):
    if sha_text(s)!=RENDER1T_CPP_SHA:
        raise RuntimeError("Unexpected RENDER1T native source: "+sha_text(s))
    s=once(s,'#include "m10rColorRecon1A.h"\n#include "m10rOutputGamut1A.h"',
             '#include "m10rOutputGamut1A.h"',"include")
    for old,new,label in [
        ('int64_t v[32] = {};','int64_t v[24] = {};',"counts"),
        ('jlong existing[32] = {};','jlong existing[24] = {};',"existing"),
        ('std::min(32,static_cast<int>','std::min(24,static_cast<int>',"returned-counts"),
        ('const double legacyOutR =','const double outR =',"outR"),
        ('const double legacyOutG =','const double outG =',"outG"),
        ('const double legacyOutB =','const double outB =',"outB"),
    ]:
        s=once(s,old,new,label)
    s=once(s,COLOR_BLOCK,'            double gamutR=outR, gamutG=outG, gamutB=outB;',"colorrecon-block")
    got=sha_text(s)
    if got!=RENDER1S_CPP_SHA:
        raise RuntimeError("Failed exact RENDER1S recovery: "+got)
    return s

def patch_cpp(render1t):
    s=reverse_colorrecon_to_render1s(render1t)
    s=once(s,OLD_TOPOLOGY,NEW_TOPOLOGY,"YA-topology")
    got=sha_text(s)
    if got!=VALIDATED_CPP_SHA:
        raise RuntimeError("Candidate does not match validated native source: "+got)
    return s

def patch_java(s):
    # RENDER2A only changes MFM capture logic; its render diagnostics are inherited
    # from RENDER1T. Replace misleading photographic-path labels without touching
    # source/WB/exposure/capture code.
    old='d.put("renderLook", "RENDER1T_COLORRECON1A_GAMUT1A_TONECAL1A_EDGE0A");'
    new='d.put("renderLook", "RENDER2G_YATOPOLOGY1A_GAMUT1A_TONECAL1A_MFM1B_EDGE0A");'
    s=once(s,old,new,"renderLook")
    if 'd.put("chromaReconstructionExperiment", "COLORRECON1A");' in s:
        s=s.replace('d.put("chromaReconstructionExperiment", "COLORRECON1A");',
                    'd.put("chromaReconstructionExperiment", "YA_TOPOLOGY1A");',1)
    if 'd.put("textbookSrgbOetfApplied", true);' in s:
        s=s.replace('d.put("textbookSrgbOetfApplied", true);',
                    'd.put("textbookSrgbOetfApplied", false);',1)
    if 'd.put("yBlend1BPhotographicRole", "counterfactual_lightness_anchor_only");' in s:
        s=s.replace('d.put("yBlend1BPhotographicRole", "counterfactual_lightness_anchor_only");',
                    'd.put("yBlend1BPhotographicRole", "removed_from_YA_TOPOLOGY1A_photographic_path");',1)

    start=s.find('            d.put("colorRecon1A", new JSONObject()')
    end=s.find('            d.put("outputGamut1A", new JSONObject()',start)
    if start<0 or end<0:
        raise RuntimeError("COLORRECON1A diagnostic block not found")
    replacement='''            d.put("colorRecon1A", new JSONObject()
                    .put("enabled", false)
                    .put("bypassedBy", "YA_TOPOLOGY1A")
                    .put("reason", "public_reference_native_validation_preferred_firmware_shaped_RGB_topology")
                    .put("validationRunId", "36244571736"));
            d.put("yaTopology1A", new JSONObject()
                    .put("enabled", true)
                    .put("publicReferenceValidated", true)
                    .put("validationRunId", "36244571736")
                    .put("validationCommit", "6852a749a9882d65083c81366d98d84a27b94a2c")
                    .put("toneLuma", "TCYC_Q12_1024_2661_410")
                    .put("toneApplication", "common_gain_preserve_working_RGB_ratios")
                    .put("differentialGammaApplication", "same_recovered_curve_independently_R_G_B")
                    .put("mainLuminance", "Ya_post_RGB_nonlinear")
                    .put("mainlineYbContribution", 0.0)
                    .put("empiricalChromaKApplied", false)
                    .put("exactAsicGammaBankRoutingClaimed", false)
                    .put("gamut1AChanged", false)
                    .put("toneCal1AChanged", false)
                    .put("mfm1bChanged", false)
                    .put("captureExposureChanged", false)
                    .put("whiteBalanceChanged", false)
                    .put("sourceProcessingChanged", false));
'''
    s=s[:start]+replacement+s[end:]

    # Keep legacy 32-long Java array ABI safe; native candidate writes only first 24.
    # Explicitly mark the reserved tail so diagnostics cannot be mistaken for live
    # COLORRECON counters.
    marker='            d.put("outputGamut1A", new JSONObject()'
    if marker not in s:
        raise RuntimeError("outputGamut1A marker missing after diagnostic rewrite")
    s=s.replace(marker,
'''            d.put("nativeExactCountsFirst24Semantic",
                    "legacy8_plus_GAMUT1A_8_to_23;_24_to_31_reserved_zero_in_YA_TOPOLOGY1A");
'''+marker,1)
    return s

def main():
    if len(sys.argv)!=2:
        raise SystemExit("usage: fix-m10r-render2g-yatopology1a-live.py <PhotonCamera-root>")
    root=Path(sys.argv[1]).resolve()
    cpp=root/"app/src/main/cpp/m10rRender.cpp"
    java=root/"app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java"
    gradle=root/"app/build.gradle"
    for p in (cpp,java,gradle):
        if not p.is_file(): raise RuntimeError("missing "+str(p))

    before=cpp.read_text()
    after=patch_cpp(before)
    cpp.write_text(after)

    js=java.read_text()
    if '"m10rMfm1B"' not in js or "M10RMfm1B" not in js:
        raise RuntimeError("RENDER2A/MFM1B Java baseline missing")
    java.write_text(patch_java(js))

    g=gradle.read_text()
    versions=re.findall(r'versionName\s+[\'"]([^\'"]+)[\'"]',g)
    if len(versions)!=1 or versions[0]!="0.97-m10r2a-mfm1b":
        raise RuntimeError("unexpected RENDER2A versionName: %r"%versions)
    version="0.97-m10r2g-yatopology1a"
    gradle.write_text(g.replace(versions[0],version,1))

    proof={
      "schema":"RENDER2G_YATOPOLOGY1A_LIVE_PATCH_V1",
      "baseline":"RENDER2A_MFM1B_on_RENDER1T",
      "versionName":version,
      "baselineCppSha256":RENDER1T_CPP_SHA,
      "recoveredRender1sCppSha256":RENDER1S_CPP_SHA,
      "candidateCppSha256":VALIDATED_CPP_SHA,
      "publicReferenceValidationRunId":VALIDATION_RUN_ID,
      "publicReferenceValidationCommit":VALIDATION_COMMIT,
      "freshHoldout07to10":{
        "render1s":{"L_mae":0.2867915787,"ab_error":4.5488179506,"DE76":4.5730922858},
        "render1t":{"L_mae":0.3332802879,"ab_error":2.0804842854,"DE76":2.1321113123},
        "yaTopology":{"L_mae":0.2645223106,"ab_error":1.2864271885,"DE76":1.3337094181}
      },
      "photographicChange":"replace_empirical_YBLEND_k035_plus_COLORRECON1A_with_YA_TOPOLOGY1A",
      "toneLuma":"TCYC_Q12_1024_2661_410",
      "toneApplication":"common_gain_preserve_working_RGB_ratios",
      "dgApplication":"same_recovered_curve_independently_R_G_B",
      "mainLuminance":"Ya_post_RGB_nonlinear",
      "mainlineYbContribution":0.0,
      "empiricalChromaKApplied":False,
      "colorRecon1AApplied":False,
      "gamut1AChanged":False,
      "toneCal1AChanged":False,
      "mfm1bChanged":False,
      "captureExposureChanged":False,
      "whiteBalanceChanged":False,
      "sourceProcessingChanged":False,
      "demosaicChanged":False,
      "jpegQualityChanged":False,
      "hdrEnabled":False,
      "singleRaw":True,
      "exactAsicGammaBankRoutingClaimed":False,
      "deviceValidated":False,
      "productionPromoted":False
    }
    (root/"M10R_RENDER2G_YATOPOLOGY1A_PROVENANCE.json").write_text(json.dumps(proof,indent=2)+"\n")
    print(json.dumps(proof,indent=2))

if __name__=="__main__":
    main()
