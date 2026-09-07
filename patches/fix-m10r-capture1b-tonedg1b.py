#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: fix-m10r-capture1b-tonedg1b.py <PhotonCamera-root>")
root = Path(sys.argv[1]).resolve()
if not (root / "app").is_dir():
    raise SystemExit("TONEDG1B: not a PhotonCamera root")


def rd(rel):
    p = root / rel
    if not p.exists():
        raise SystemExit("TONEDG1B missing expected file: " + rel)
    return p.read_text()


def wr(rel, s):
    (root / rel).write_text(s)


def one(s, a, b, label):
    if s.count(a) != 1:
        raise SystemExit("TONEDG1B anchor " + label + " missing/ambiguous")
    return s.replace(a, b, 1)


grad = "app/build.gradle"
g = rd(grad)
g = one(
    g,
    "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1a'",
    "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1b'",
    "version",
)
wr(grad, g)

renderer = "app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java"
s = rd(renderer)
s = one(
    s,
    '"m10rcam.capture1b.nativecamera2_xyz_d50.m10r_c_promoted.tonedg1a.v1";',
    '"m10rcam.capture1b.nativecamera2_xyz_d50.m10r_c_promoted.tonedg1b.v1";',
    "schema",
)
s = one(s, 'd.put("nonlinearRenderer", "TONEDG1A");', 'd.put("nonlinearRenderer", "TONEDG1B");', "renderer-id")
meta_anchor = '        d.put("nonlinearPlacement", "after_M10R_target_to_linear_sRGB_before_sRGB_OETF");\n'
meta_extra = meta_anchor + '''        d.put("nonlinearApplicationMode", "luma_gain_preserve_linear_rgb_ratios");
        d.put("nonlinearLumaProxy", "linear_sRGB_Rec709_0.2126_0.7152_0.0722_DIAGNOSTIC");
        d.put("nonlinearChromaticityPreservationIntent", true);
        d.put("nonlinearPerChannelCurveApplied", false);
'''
s = one(s, meta_anchor, meta_extra, "metadata")

old = '''                    toneDgStats.preTone.add(lr, lg, lb);
                    int xr = M10RToneDg1A.toInput(lr, toneDgStats, 0);
                    int xg = M10RToneDg1A.toInput(lg, toneDgStats, 1);
                    int xb = M10RToneDg1A.toInput(lb, toneDgStats, 2);
                    toneDgStats.toneInput.add(xr, xg, xb);
                    int mr = M10RToneDg1A.medium(xr);
                    int mg = M10RToneDg1A.medium(xg);
                    int mb = M10RToneDg1A.medium(xb);
                    toneDgStats.postTone.add(mr, mg, mb);
                    int dr = M10RToneDg1A.dg(mr, toneDgStats, 0);
                    int ddg = M10RToneDg1A.dg(mg, toneDgStats, 1);
                    int db = M10RToneDg1A.dg(mb, toneDgStats, 2);
                    toneDgStats.postDg.add(dr, ddg, db);
                    double nr = dr / (double)M10RToneDg1A.DG_OUT_MAX;
                    double ng = ddg / (double)M10RToneDg1A.DG_OUT_MAX;
                    double nb = db / (double)M10RToneDg1A.DG_OUT_MAX;
                    toneDgStats.preSrgb.add(nr, ng, nb);
                    argb[i] = 0xff000000 | (toSrgb8(nr) << 16) | (toSrgb8(ng) << 8) | toSrgb8(nb);
'''
new = '''                    toneDgStats.preTone.add(lr, lg, lb);
                    double linearY = 0.2126*lr + 0.7152*lg + 0.0722*lb;
                    int xy = M10RToneDg1A.toInputLuma(linearY, toneDgStats);
                    toneDgStats.toneInput.add(xy, xy, xy);
                    int my = M10RToneDg1A.medium(xy);
                    toneDgStats.postTone.add(my, my, my);
                    int dy = M10RToneDg1A.dgLuma(my, toneDgStats);
                    toneDgStats.postDg.add(dy, dy, dy);
                    double mappedY = dy / (double)M10RToneDg1A.DG_OUT_MAX;
                    double gain = (linearY > 1.0e-12) ? (mappedY / linearY) : 0.0;
                    toneDgStats.lumaGain.add(gain);
                    double nr = lr * gain;
                    double ng = lg * gain;
                    double nb = lb * gain;
                    toneDgStats.preSrgb.add(nr, ng, nb);
                    argb[i] = 0xff000000 | (toSrgb8(nr) << 16) | (toSrgb8(ng) << 8) | toSrgb8(nb);
'''
s = one(s, old, new, "render")
wr(renderer, s)

helper = "app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RToneDg1A.java"
h = rd(helper)
insert_anchor = '''    static int medium(int x) {
'''
insert = '''    static int toInputLuma(double v, Diagnostics d) {
        if (!Double.isFinite(v)) { d.lumaInputNonFinite++; return 0; }
        if (v < 0.0) { d.lumaInputLow++; return 0; }
        if (v > 1.0) { d.lumaInputHigh++; return INPUT_MAX; }
        return clamp((int)Math.round(v*INPUT_MAX),0,INPUT_MAX);
    }
    static int dgLuma(int x, Diagnostics d) {
        int xx=x;
        if (xx<0) { d.lumaDgLow++; xx=0; }
        else if (xx>DG_INDEX_MAX) { d.lumaDgHigh++; xx=DG_INDEX_MAX; }
        return DGT[xx];
    }

''' + insert_anchor
h = one(h, insert_anchor, insert, "helper-luma-functions")
old_fields = '''        final Stage preSrgb=new Stage("linear",0,1);
        final long[] inputLow=new long[3],inputHigh=new long[3],inputNonFinite=new long[3],dgLow=new long[3],dgHigh=new long[3];
'''
new_fields = '''        final Stage preSrgb=new Stage("linear",0,1);
        final ScalarStat lumaGain=new ScalarStat();
        final long[] inputLow=new long[3],inputHigh=new long[3],inputNonFinite=new long[3],dgLow=new long[3],dgHigh=new long[3];
        long lumaInputLow,lumaInputHigh,lumaInputNonFinite,lumaDgLow,lumaDgHigh;
'''
h = one(h, old_fields, new_fields, "helper-fields")
old_json = '''            o.put("differentialGammaIndexClipHighRGB",arr(dgHigh));
            o.put("percentileHistogramBins",BINS);
'''
new_json = '''            o.put("differentialGammaIndexClipHighRGB",arr(dgHigh));
            o.put("lumaToneInputClipLow",lumaInputLow);
            o.put("lumaToneInputClipHigh",lumaInputHigh);
            o.put("lumaToneInputNonFinite",lumaInputNonFinite);
            o.put("lumaDifferentialGammaIndexClipLow",lumaDgLow);
            o.put("lumaDifferentialGammaIndexClipHigh",lumaDgHigh);
            o.put("lumaGain",lumaGain.json());
            o.put("percentileHistogramBins",BINS);
'''
h = one(h, old_json, new_json, "helper-json")
stat_anchor = '''    static final class Stat {
'''
scalar = '''    static final class ScalarStat {
        long n,nf; double min=Double.POSITIVE_INFINITY,max=Double.NEGATIVE_INFINITY,sum;
        void add(double v){if(!Double.isFinite(v)){nf++;return;}n++;min=Math.min(min,v);max=Math.max(max,v);sum+=v;}
        JSONObject json() throws Exception {JSONObject o=new JSONObject();o.put("count",n);o.put("min",n==0?JSONObject.NULL:min);o.put("mean",n==0?JSONObject.NULL:sum/n);o.put("max",n==0?JSONObject.NULL:max);o.put("nonFinite",nf);return o;}
    }
''' + stat_anchor
h = one(h, stat_anchor, scalar, "helper-scalar-stat")
wr(helper, h)

out = rd(renderer)
for marker in [
    'demosaicChannelOrderFix", "RGBORDER1A"',
    'sourceMatrixConventionFix", "SOURCECM1A"',
    'nonlinearRenderer", "TONEDG1B"',
    'nonlinearApplicationMode", "luma_gain_preserve_linear_rgb_ratios"',
    'nonlinearPerChannelCurveApplied", false',
    'hdrEnabled", false',
    'sourceFrameCount", 1',
]:
    if marker not in out:
        raise SystemExit("TONEDG1B invariant missing " + marker)
if "t.copyElements(r,0);" in out:
    raise SystemExit("TONEDG1B copyElements regression")
print("TONEDG1B applied; MEDIUM->DG now maps luma and preserves linear RGB ratios")
