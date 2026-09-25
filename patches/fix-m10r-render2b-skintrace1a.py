#!/usr/bin/env python3
"""SKINTRACE1A diagnostic-only warm-mid colour stage trace on top of RENDER2A/MFM1B.

No photographic intent changes:
- capture exposure/MFM1B unchanged;
- source/WB/CA9 unchanged;
- RENDER1T COLORRECON1A/GAMUT1A/TONECAL1A arithmetic unchanged;
- no new correction is applied.

The diagnostic follows warm-chroma samples through:
mapped Yc -> linear CC1 -> COLORRECON1A anchor/gain/shoulder ->
pre-GAMUT encoded output -> post-GAMUT output.

It deliberately uses colour-space proxy classes, not face/person detection.
"""
from pathlib import Path
import hashlib,json,re,sys

BASE_CPP_SHA="880ce125413bdf1e0f56fbbdcc56591ba91e794f9b5281488f63353dca724637"
BASE_COLOR_HEADER_MARKER="Empirical COLORRECON1A. This is not recovered Leica Y BLEND arithmetic."

COUNT_LEN=208
TRACE_BASE=32
TRACE_METRICS=27
WARM_BIN_BASES=[32,59,86,113]
WARM_MID_BASE=140
NEUTRAL_MID_BASE=167

def sha_bytes(b): return hashlib.sha256(b).hexdigest()
def sha_text(s): return hashlib.sha256(s.encode()).hexdigest()

def once(s,a,b):
    n=s.count(a)
    if n!=1:
        raise RuntimeError("Unique anchor required (%d): %s" % (n,a[:180]))
    return s.replace(a,b,1)

def patch_color_header(s):
    if sha_text(s)!=BASE_COLOR_HEADER_SHA:
        raise RuntimeError("Refusing unknown m10rColorRecon1A.h")
    s=once(s,
'''namespace m10r_colorrecon1a {
inline double decode(double x) {
''',
'''namespace m10r_colorrecon1a {
struct Trace {
    bool valid=false;
    double cc1R=0.0,cc1G=0.0,cc1B=0.0;
    double lum=0.0,peak=0.0,anchor=0.0,requested=0.0;
    double saturation=0.0,width=0.0,knee=0.0;
    double requestedPeak=0.0,peakCode=0.0,ceiling=0.0,gain=0.0;
    double finalLinearR=0.0,finalLinearG=0.0,finalLinearB=0.0;
};
inline double decode(double x) {
''')
    s=once(s,
'''                      const int* tone,const int* table,
                      double& r,double& g,double& b) {
''',
'''                      const int* tone,const int* table,
                      double& r,double& g,double& b,
                      Trace* trace=nullptr) {
''')
    s=once(s,
'''    const double lum=0.2126*cr+0.7152*cg+0.0722*cb;
    const double peak=std::max(cr,std::max(cg,cb));
''',
'''    const double lum=0.2126*cr+0.7152*cg+0.0722*cb;
    const double peak=std::max(cr,std::max(cg,cb));
    if(trace) {
        trace->cc1R=cr; trace->cc1G=cg; trace->cc1B=cb;
        trace->lum=lum; trace->peak=peak;
    }
''')
    s=once(s,
'''    const double ceiling=decode(peakCode)/positivePeak;
    const double gain=std::min(requested,ceiling);
    r=encode(cr*gain);g=encode(cg*gain);b=encode(cb*gain);
''',
'''    const double ceiling=decode(peakCode)/positivePeak;
    const double gain=std::min(requested,ceiling);
    const double finalLinearR=cr*gain;
    const double finalLinearG=cg*gain;
    const double finalLinearB=cb*gain;
    if(trace) {
        trace->valid=true;
        trace->anchor=anchor;
        trace->requested=requested;
        trace->saturation=saturation;
        trace->width=width;
        trace->knee=knee;
        trace->requestedPeak=requestedPeak;
        trace->peakCode=peakCode;
        trace->ceiling=ceiling;
        trace->gain=gain;
        trace->finalLinearR=finalLinearR;
        trace->finalLinearG=finalLinearG;
        trace->finalLinearB=finalLinearB;
    }
    r=encode(finalLinearR);g=encode(finalLinearG);b=encode(finalLinearB);
''')
    return s

def patch_cpp(s):
    if sha_text(s)!=BASE_CPP_SHA:
        raise RuntimeError("Refusing unknown RENDER1T native source")

    s=once(s,'int64_t v[32] = {};',f'int64_t v[{COUNT_LEN}] = {{}};')
    s=once(s,'jlong existing[32] = {};',f'jlong existing[{COUNT_LEN}] = {{}};')
    s=once(s,'std::min(32,static_cast<int>',f'std::min({COUNT_LEN},static_cast<int>')

    # Diagnostic integer-scaled accumulation helpers. 1e6 is enough precision
    # while leaving enormous int64 headroom even for full-frame sampling.
    counts_anchor='''inline double ca9clip(double camera, int gain, Counts& c, int ch) {
'''
    counts_helper=f'''constexpr int SKINTRACE_STRIDE = 64;
constexpr int SKINTRACE_METRICS = {TRACE_METRICS};
constexpr double SKINTRACE_SCALE = 1000000.0;

inline void skinTraceAcc(Counts& c,int base,int slot,double value) {{
    if(!std::isfinite(value)) return;
    const double scaled=value*SKINTRACE_SCALE;
    if(scaled > static_cast<double>(INT64_MAX) || scaled < static_cast<double>(INT64_MIN)) return;
    c.v[base+slot] += static_cast<int64_t>(std::llround(scaled));
}}
inline void skinTraceBin(Counts& c,int base,
                         double inputY,double mappedY,double relCb,double relCr,
                         const m10r_colorrecon1a::Trace& t,unsigned flags,
                         double outR,double outG,double outB,
                         double gamutR,double gamutG,double gamutB) {{
    c.v[base+0]++;
    c.v[base+1] += (flags&1u)!=0;
    c.v[base+2] += (flags&4u)!=0;
    skinTraceAcc(c,base,3,inputY);
    skinTraceAcc(c,base,4,mappedY);
    skinTraceAcc(c,base,5,relCb);
    skinTraceAcc(c,base,6,relCr);
    skinTraceAcc(c,base,7,t.cc1R);
    skinTraceAcc(c,base,8,t.cc1G);
    skinTraceAcc(c,base,9,t.cc1B);
    skinTraceAcc(c,base,10,t.anchor);
    skinTraceAcc(c,base,11,t.requested);
    skinTraceAcc(c,base,12,t.saturation);
    skinTraceAcc(c,base,13,t.width);
    skinTraceAcc(c,base,14,t.gain);
    skinTraceAcc(c,base,15,t.finalLinearR);
    skinTraceAcc(c,base,16,t.finalLinearG);
    skinTraceAcc(c,base,17,t.finalLinearB);
    skinTraceAcc(c,base,18,outR);
    skinTraceAcc(c,base,19,outG);
    skinTraceAcc(c,base,20,outB);
    skinTraceAcc(c,base,21,gamutR);
    skinTraceAcc(c,base,22,gamutG);
    skinTraceAcc(c,base,23,gamutB);
    skinTraceAcc(c,base,24,m10r_colorrecon1a::decode(gamutR));
    skinTraceAcc(c,base,25,m10r_colorrecon1a::decode(gamutG));
    skinTraceAcc(c,base,26,m10r_colorrecon1a::decode(gamutB));
}}

'''+counts_anchor
    s=once(s,counts_anchor,counts_helper)

    old_call='''            double outR,outG,outB;
            const unsigned colorFlags=m10r_colorrecon1a::apply(
                    lr,lg,lb,outMat,legacyOutR,legacyOutG,legacyOutB,
                    tone,dgt,outR,outG,outB);
'''
    new_call='''            double outR,outG,outB;
            m10r_colorrecon1a::Trace skinTraceColor;
            const unsigned colorFlags=m10r_colorrecon1a::apply(
                    lr,lg,lb,outMat,legacyOutR,legacyOutG,legacyOutB,
                    tone,dgt,outR,outG,outB,&skinTraceColor);
'''
    s=once(s,old_call,new_call)

    old_gamut='''            const int gamutStatus=m10r_outputgamut1a::apply(gamutR,gamutG,gamutB);
            cnt.v[8]++;
'''
    new_gamut=f'''            const int gamutStatus=m10r_outputgamut1a::apply(gamutR,gamutG,gamutB);

            // SKINTRACE1A: diagnostic-only warm/neutral colour-space proxies.
            // Classification reuses the already established mapped Yc relative
            // chroma diagnostic domain; no face/person detection is performed.
            if((i % SKINTRACE_STRIDE)==0 && skinTraceColor.valid && mappedY>0.03) {{
                const double relCb=mappedCb/mappedY;
                const double relCr=mappedCr/mappedY;
                if(std::isfinite(relCb) && std::isfinite(relCr)) {{
                    if(relCr>=0.04) {{
                        const int warmBin = mappedY<0.18 ? 0 : (mappedY<0.40 ? 1 : (mappedY<0.75 ? 2 : 3));
                        static const int warmBases[4]={{{','.join(map(str,WARM_BIN_BASES))}}};
                        skinTraceBin(cnt,warmBases[warmBin],y,mappedY,relCb,relCr,
                                     skinTraceColor,colorFlags,outR,outG,outB,gamutR,gamutG,gamutB);
                    }}
                    const bool warmMidProxy = mappedY>=0.18 && mappedY<0.75
                            && relCr>=0.04 && relCr<=0.20
                            && relCb>=-0.18 && relCb<=0.03;
                    if(warmMidProxy) {{
                        skinTraceBin(cnt,{WARM_MID_BASE},y,mappedY,relCb,relCr,
                                     skinTraceColor,colorFlags,outR,outG,outB,gamutR,gamutG,gamutB);
                    }}
                    const bool neutralMid = mappedY>=0.18 && mappedY<0.75
                            && std::abs(relCb)<=0.02 && std::abs(relCr)<=0.02;
                    if(neutralMid) {{
                        skinTraceBin(cnt,{NEUTRAL_MID_BASE},y,mappedY,relCb,relCr,
                                     skinTraceColor,colorFlags,outR,outG,outB,gamutR,gamutG,gamutB);
                    }}
                }}
            }}

            cnt.v[8]++;
'''
    s=once(s,old_gamut,new_gamut)
    return s

JAVA_HELPERS=f'''    private static final double SKINTRACE1A_SCALE = 1000000.0;
    private static final int SKINTRACE1A_METRICS = {TRACE_METRICS};

    private static double skinTrace1AMean(long[] counts, int base, int slot) {{
        long n=counts[base];
        if(n<=0L) return Double.NaN;
        return counts[base+slot]/SKINTRACE1A_SCALE/n;
    }}

    private static JSONObject skinTrace1ABin(long[] counts, int base, String name) throws Exception {{
        final long n=counts[base];
        JSONObject o=new JSONObject()
                .put("name", name)
                .put("sampleCount", n)
                .put("peakLimitedCount", counts[base+1])
                .put("linearPeakAboveOneCount", counts[base+2]);
        if(n<=0L) return o.put("valid", false);
        return o.put("valid", true)
                .put("meanInputY", skinTrace1AMean(counts,base,3))
                .put("meanMappedY", skinTrace1AMean(counts,base,4))
                .put("meanRelCb", skinTrace1AMean(counts,base,5))
                .put("meanRelCr", skinTrace1AMean(counts,base,6))
                .put("meanLinearCc1R", skinTrace1AMean(counts,base,7))
                .put("meanLinearCc1G", skinTrace1AMean(counts,base,8))
                .put("meanLinearCc1B", skinTrace1AMean(counts,base,9))
                .put("meanLightnessAnchorLinearY", skinTrace1AMean(counts,base,10))
                .put("meanRequestedCommonGain", skinTrace1AMean(counts,base,11))
                .put("meanSaturation", skinTrace1AMean(counts,base,12))
                .put("meanShoulderWidth", skinTrace1AMean(counts,base,13))
                .put("meanAppliedCommonGain", skinTrace1AMean(counts,base,14))
                .put("meanColorReconLinearR", skinTrace1AMean(counts,base,15))
                .put("meanColorReconLinearG", skinTrace1AMean(counts,base,16))
                .put("meanColorReconLinearB", skinTrace1AMean(counts,base,17))
                .put("meanPreGamutEncodedR", skinTrace1AMean(counts,base,18))
                .put("meanPreGamutEncodedG", skinTrace1AMean(counts,base,19))
                .put("meanPreGamutEncodedB", skinTrace1AMean(counts,base,20))
                .put("meanPostGamutEncodedR", skinTrace1AMean(counts,base,21))
                .put("meanPostGamutEncodedG", skinTrace1AMean(counts,base,22))
                .put("meanPostGamutEncodedB", skinTrace1AMean(counts,base,23))
                .put("meanPostGamutLinearR", skinTrace1AMean(counts,base,24))
                .put("meanPostGamutLinearG", skinTrace1AMean(counts,base,25))
                .put("meanPostGamutLinearB", skinTrace1AMean(counts,base,26));
    }}

'''

def patch_java(s):
    s=once(s,'final long[] nativeExactCounts = new long[32];',f'final long[] nativeExactCounts = new long[{COUNT_LEN}];')

    helper_anchor='    private static SourceModel buildSourceModel('
    s=once(s,helper_anchor,JAVA_HELPERS+helper_anchor)

    marker='            d.put("outputGamut1A", new JSONObject()'
    diag=f'''            JSONArray skinWarmBins=new JSONArray()
                    .put(skinTrace1ABin(nativeExactCounts,{WARM_BIN_BASES[0]},"shadow"))
                    .put(skinTrace1ABin(nativeExactCounts,{WARM_BIN_BASES[1]},"lowMid"))
                    .put(skinTrace1ABin(nativeExactCounts,{WARM_BIN_BASES[2]},"midHigh"))
                    .put(skinTrace1ABin(nativeExactCounts,{WARM_BIN_BASES[3]},"highlight"));
            d.put("skinTrace1A", new JSONObject()
                    .put("enabled", true)
                    .put("diagnosticOnly", true)
                    .put("photographicPixelsChanged", false)
                    .put("captureExposureChanged", false)
                    .put("whiteBalanceChanged", false)
                    .put("mfm1bChanged", false)
                    .put("classificationUsesFaceDetection", false)
                    .put("sampleStride", 64)
                    .put("classificationDomain", "mapped_Yc_relative_chroma")
                    .put("warmRelCrDefinition", "mappedY_gt_0p03_and_relCr_ge_0p04")
                    .put("warmMidProxyDefinition",
                            "mappedY_0p18_to_0p75_relCr_0p04_to_0p20_relCb_minus0p18_to_0p03")
                    .put("neutralMidDefinition",
                            "mappedY_0p18_to_0p75_absRelCb_le_0p02_absRelCr_le_0p02")
                    .put("traceStages",
                            "mappedYc,linear_CC1,COLORRECON1A_anchor_gain_shoulder,pre_GAMUT_encoded,post_GAMUT_encoded_and_linearized")
                    .put("warmRelCrBins", skinWarmBins)
                    .put("warmMidProxy", skinTrace1ABin(nativeExactCounts,{WARM_MID_BASE},"warmMidProxy"))
                    .put("neutralMidControl", skinTrace1ABin(nativeExactCounts,{NEUTRAL_MID_BASE},"neutralMidControl"))
                    .put("toneCal1AIncludedInTrace", false)
                    .put("toneCal1AReason",
                            "TONECAL1A_is_post_quantization_Lab_lightness_correction_with_ab_held_constant")
                    .put("exactFirmwareSkinModelClaimed", false));
'''+marker
    s=once(s,marker,diag)
    return s

def main():
    if len(sys.argv)!=2:
        raise SystemExit("usage: fix-m10r-render2b-skintrace1a.py <PhotonCamera-root>")
    root=Path(sys.argv[1]).resolve()

    cpp=root/"app/src/main/cpp/m10rRender.cpp"
    header=root/"app/src/main/cpp/m10rColorRecon1A.h"
    java=root/"app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java"
    gradle=root/"app/build.gradle"
    for p in [cpp,header,java,gradle]:
        if not p.is_file(): raise RuntimeError("missing "+str(p))

    cpp_before=cpp.read_text()
    header_before=header.read_text()
    java_before=java.read_text()
    if sha_text(cpp_before)!=BASE_CPP_SHA:
        raise RuntimeError("unexpected MFM1B renderer C++ baseline")
    if sha_text(header_before)!=BASE_COLOR_HEADER_SHA:
        raise RuntimeError("unexpected COLORRECON1A header baseline")

    cpp_after=patch_cpp(cpp_before)
    header_after=patch_color_header(header_before)
    java_after=patch_java(java_before)

    cpp.write_text(cpp_after)
    header.write_text(header_after)
    java.write_text(java_after)

    g=gradle.read_text()
    versions=re.findall(r'versionName\s+[\'\"]([^\'\"]+)[\'\"]',g)
    if len(versions)!=1 or versions[0]!="0.97-m10r2a-mfm1b":
        raise RuntimeError("unexpected MFM1B versionName: %r" % versions)
    version="0.97-m10r2b-skintrace1a"
    gradle.write_text(g.replace(versions[0],version,1))

    proof={
        "schema":"RENDER2B_SKINTRACE1A_PATCH_V1",
        "baseline":"RENDER2A_MFM1B_on_RENDER1T",
        "versionName":version,
        "diagnosticOnly":True,
        "photographicIntentChanged":False,
        "captureExposureChanged":False,
        "mfm1bChanged":False,
        "whiteBalanceChanged":False,
        "sourceProcessingChanged":False,
        "toneAssetsChanged":False,
        "colorReconCoefficientsChanged":False,
        "gamutMappingChanged":False,
        "toneCalChanged":False,
        "faceDetectionUsed":False,
        "sampleStride":64,
        "countsLength":COUNT_LEN,
        "warmBins":"mappedY_shadow_lowMid_midHigh_highlight_relCr>=0.04",
        "warmMidProxy":"mappedY_0.18_0.75_relCr_0.04_0.20_relCb_-0.18_0.03",
        "neutralControl":"mappedY_0.18_0.75_absRelCbCr<=0.02",
        "privatePhotoFixtureCommitted":False,
        "privateValidationDataCommitted":False,
        "deviceValidated":False,
        "productionPromoted":False
    }
    (root/"M10R_RENDER2B_SKINTRACE1A_PROVENANCE.json").write_text(json.dumps(proof,indent=2)+"\n")
    print(json.dumps(proof,indent=2))

if __name__=="__main__":
    main()
