#!/usr/bin/env python3
from pathlib import Path
import base64, gzip, hashlib, sys

if len(sys.argv) != 3:
    raise SystemExit("usage: fix-m10r-capture1b-tonedg1a.py <PhotonCamera-root> <b2y-asset-dir>")
root = Path(sys.argv[1]).resolve()
assets = Path(sys.argv[2]).resolve()
if not (root/"app").is_dir() or not assets.is_dir():
    raise SystemExit("TONEDG1A: root/assets missing")

TONE_SHA="2fd6ca209f290c75aa96976b3d7692e55c41a55c0017a063aba9808da3b41a00"
DG_SHA="9e65de24d52271be0783f4e2728f20f482c0ba43b63159b75033b4a4fc75457d"
tone=(assets/"tone_medium_q15.u32le").read_bytes()
dg=(assets/"dg_expanded_u16le.bin").read_bytes()
if len(tone)!=40960 or hashlib.sha256(tone).hexdigest()!=TONE_SHA:
    raise SystemExit("TONEDG1A: MEDIUM asset validation failed")
if len(dg)!=65536 or hashlib.sha256(dg).hexdigest()!=DG_SHA:
    raise SystemExit("TONEDG1A: DG asset validation failed")

def rd(rel): return (root/rel).read_text()
def wr(rel,s):
    p=root/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(s)
def one(s,a,b,label):
    if s.count(a)!=1: raise SystemExit("TONEDG1A anchor "+label+" missing/ambiguous")
    return s.replace(a,b,1)

grad="app/build.gradle"
g=rd(grad)
g=one(g,"versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a'",
      "versionName '0.97-m10rcapture1b-rgborder1a-sourcecm1a-tonedg1a'","version")
wr(grad,g)

rel="app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java"
s=rd(rel)
if "TONEDG1A" in s: raise SystemExit("TONEDG1A already applied")
s=one(s,
 '"m10rcam.capture1b.nativecamera2_xyz_d50.m10r_c_promoted.v1";',
 '"m10rcam.capture1b.nativecamera2_xyz_d50.m10r_c_promoted.tonedg1a.v1";',"schema")

a='''        d.put("rawHeadroomRetained", false);
        d.put("ca9NeutralClipEnabled", true);
'''
b=a+'''        d.put("nonlinearRenderer", "TONEDG1A");
        d.put("nonlinearToneAsset", "MEDIUM");
        d.put("nonlinearOrder", "MEDIUM_THEN_DIFFERENTIAL_GAMMA");
        d.put("deKneeEnabled", false);
        d.put("interpolationGammaEnabled", false);
        d.put("toneAssetSha256", M10RToneDg1A.TONE_SHA256);
        d.put("differentialGammaExpandedSha256", M10RToneDg1A.DG_SHA256);
        d.put("b2yInputCoordinateMapping", "DIAGNOSTIC_linear_sRGB_0_1_to_14bit_0_16383_round_clamp");
        d.put("b2yLiveSignalNormalizationFrozen", false);
        d.put("toneArithmetic", "Q15_idx_x_shift1_truncate_rounding_not_hardware_frozen");
        d.put("nonlinearPlacement", "after_M10R_target_to_linear_sRGB_before_sRGB_OETF");
'''
s=one(s,a,b,"metadata")

a='''            long[] neutralClipCounts = new long[3];
            double inverseStorageScale = 1.0 / normalized.storageScale;
'''
b='''            long[] neutralClipCounts = new long[3];
            M10RToneDg1A.Diagnostics toneDgStats = new M10RToneDg1A.Diagnostics();
            double inverseStorageScale = 1.0 / normalized.storageScale;
'''
s=one(s,a,b,"stats-init")

a='''                    double lr = targetToSrgb[0]*tr + targetToSrgb[1]*tg + targetToSrgb[2]*tb;
                    double lg = targetToSrgb[3]*tr + targetToSrgb[4]*tg + targetToSrgb[5]*tb;
                    double lb = targetToSrgb[6]*tr + targetToSrgb[7]*tg + targetToSrgb[8]*tb;
                    argb[i] = 0xff000000 | (toSrgb8(lr) << 16) | (toSrgb8(lg) << 8) | toSrgb8(lb);
'''
b='''                    double lr = targetToSrgb[0]*tr + targetToSrgb[1]*tg + targetToSrgb[2]*tb;
                    double lg = targetToSrgb[3]*tr + targetToSrgb[4]*tg + targetToSrgb[5]*tb;
                    double lb = targetToSrgb[6]*tr + targetToSrgb[7]*tg + targetToSrgb[8]*tb;

                    toneDgStats.preTone.add(lr, lg, lb);
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
s=one(s,a,b,"render")

a='''            d.put("neutralDomainClipCounts", json(neutralClipCounts));
            d.put("sourceWhiteLevelClipCount", normalized.sourceWhiteClipCount);
'''
b=a+'''            d.put("toneDg1aSignalStatistics", toneDgStats.json());
'''
s=one(s,a,b,"diagnostics")
wr(rel,s)

def chunks(raw):
    enc=base64.b64encode(gzip.compress(raw,compresslevel=9,mtime=0)).decode()
    return [enc[i:i+8000] for i in range(0,len(enc),8000)]
def lit(cs): return ",\n".join('        "'+x+'"' for x in cs)

helper = r'''package com.particlesdevs.photoncamera.m10r;

import android.util.Base64;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.zip.GZIPInputStream;

final class M10RToneDg1A {
    static final String TONE_SHA256="__TONE_SHA__";
    static final String DG_SHA256="__DG_SHA__";
    static final int INPUT_MAX=0x3fff, TONE_ENTRIES=10240, DG_ENTRIES=32768, DG_INDEX_MAX=0x7fff, DG_OUT_MAX=0x3fff;
    private static final int BINS=2048;
    private static final String[] TONE_B64={
__TONE__
    };
    private static final String[] DG_B64={
__DG__
    };
    private static final int[] TONE=decode32(TONE_B64,TONE_ENTRIES);
    private static final int[] DGT=decode16(DG_B64,DG_ENTRIES);
    private M10RToneDg1A(){}

    static int toInput(double v, Diagnostics d, int ch) {
        if (!Double.isFinite(v)) { d.inputNonFinite[ch]++; return 0; }
        if (v < 0.0) { d.inputLow[ch]++; return 0; }
        if (v > 1.0) { d.inputHigh[ch]++; return INPUT_MAX; }
        return clamp((int)Math.round(v*INPUT_MAX),0,INPUT_MAX);
    }
    static int medium(int x) {
        int xx=clamp(x,0,TONE_ENTRIES*2-1);
        return (int)(((long)xx*(long)TONE[xx>>1])>>15);
    }
    static int dg(int x, Diagnostics d, int ch) {
        int xx=x;
        if (xx<0) { d.dgLow[ch]++; xx=0; }
        else if (xx>DG_INDEX_MAX) { d.dgHigh[ch]++; xx=DG_INDEX_MAX; }
        return DGT[xx];
    }

    static final class Diagnostics {
        final Stage preTone=new Stage("linear",0,1);
        final Stage toneInput=new Stage("14bit_coordinate",0,INPUT_MAX);
        final Stage postTone=new Stage("tone_coordinate",0,DG_INDEX_MAX);
        final Stage postDg=new Stage("dg_output",0,DG_OUT_MAX);
        final Stage preSrgb=new Stage("linear",0,1);
        final long[] inputLow=new long[3],inputHigh=new long[3],inputNonFinite=new long[3],dgLow=new long[3],dgHigh=new long[3];
        JSONObject json() throws Exception {
            JSONObject o=new JSONObject();
            o.put("preTone",preTone.json());
            o.put("toneInputCoordinate",toneInput.json());
            o.put("postMediumTone",postTone.json());
            o.put("postDifferentialGamma",postDg.json());
            o.put("preSrgb",preSrgb.json());
            o.put("toneInputCoordinateClipLowRGB",arr(inputLow));
            o.put("toneInputCoordinateClipHighRGB",arr(inputHigh));
            o.put("toneInputCoordinateNonFiniteRGB",arr(inputNonFinite));
            o.put("differentialGammaIndexClipLowRGB",arr(dgLow));
            o.put("differentialGammaIndexClipHighRGB",arr(dgHigh));
            o.put("percentileHistogramBins",BINS);
            o.put("percentilesApproximateFromFixedHistogram",true);
            return o;
        }
    }
    static final class Stage {
        final String unit; final double lo,hi; final Stat[] s;
        Stage(String u,double l,double h){unit=u;lo=l;hi=h;s=new Stat[]{new Stat(l,h),new Stat(l,h),new Stat(l,h),new Stat(l,h)};}
        void add(double r,double g,double b){s[0].add(r);s[1].add(g);s[2].add(b);s[3].add(.2126*r+.7152*g+.0722*b);}
        JSONObject json() throws Exception {
            JSONObject o=new JSONObject();o.put("unit",unit);o.put("expectedLow",lo);o.put("expectedHigh",hi);
            o.put("R",s[0].json());o.put("G",s[1].json());o.put("B",s[2].json());o.put("luma709Proxy",s[3].json());return o;
        }
    }
    static final class Stat {
        final double lo,hi; final long[] h=new long[BINS]; long n,below,above,nf; double min=Double.POSITIVE_INFINITY,max=Double.NEGATIVE_INFINITY,sum;
        Stat(double l,double u){lo=l;hi=u;}
        void add(double v){
            if(!Double.isFinite(v)){nf++;return;} n++;min=Math.min(min,v);max=Math.max(max,v);sum+=v;
            if(v<lo)below++;if(v>hi)above++;
            double q=Math.max(0,Math.min(1,(v-lo)/Math.max(1e-30,hi-lo)));int i=Math.min(BINS-1,(int)Math.floor(q*BINS));h[i]++;
        }
        JSONObject json() throws Exception {
            JSONObject o=new JSONObject();o.put("count",n);o.put("min",n==0?JSONObject.NULL:min);o.put("median",pct(.5));
            o.put("mean",n==0?JSONObject.NULL:sum/n);o.put("p90",pct(.9));o.put("p99",pct(.99));o.put("max",n==0?JSONObject.NULL:max);
            o.put("belowExpected",below);o.put("aboveExpected",above);o.put("nonFinite",nf);return o;
        }
        Object pct(double p){
            if(n==0)return JSONObject.NULL;long target=Math.max(1L,(long)Math.ceil(p*n)),a=0;
            for(int i=0;i<h.length;i++){a+=h[i];if(a>=target)return lo+((i+.5)/h.length)*(hi-lo);}return hi;
        }
    }
    static int[] decode32(String[] c,int n){byte[] r=inflate(c);if(r.length!=n*4)throw new IllegalStateException("TONEDG1A tone bytes");ByteBuffer b=ByteBuffer.wrap(r).order(ByteOrder.LITTLE_ENDIAN);int[] o=new int[n];for(int i=0;i<n;i++)o[i]=b.getInt();return o;}
    static int[] decode16(String[] c,int n){byte[] r=inflate(c);if(r.length!=n*2)throw new IllegalStateException("TONEDG1A dg bytes");ByteBuffer b=ByteBuffer.wrap(r).order(ByteOrder.LITTLE_ENDIAN);int[] o=new int[n];for(int i=0;i<n;i++)o[i]=b.getShort()&0xffff;return o;}
    static byte[] inflate(String[] c){
        try{StringBuilder s=new StringBuilder();for(String x:c)s.append(x);byte[] z=Base64.decode(s.toString(),Base64.NO_WRAP);
            GZIPInputStream in=new GZIPInputStream(new ByteArrayInputStream(z));ByteArrayOutputStream o=new ByteArrayOutputStream();byte[] b=new byte[8192];int n;
            while((n=in.read(b))!=-1)o.write(b,0,n);in.close();return o.toByteArray();}catch(Exception e){throw new IllegalStateException("TONEDG1A asset inflate",e);}
    }
    static JSONArray arr(long[] x){JSONArray a=new JSONArray();for(long v:x)a.put(v);return a;}
    static int clamp(int v,int l,int h){return v<l?l:(v>h?h:v);}
}
'''
helper=helper.replace("__TONE_SHA__",TONE_SHA).replace("__DG_SHA__",DG_SHA).replace("__TONE__",lit(chunks(tone))).replace("__DG__",lit(chunks(dg)))
wr("app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RToneDg1A.java",helper)

out=rd(rel)
for marker in ['demosaicChannelOrderFix", "RGBORDER1A"','sourceMatrixConventionFix", "SOURCECM1A"','nonlinearRenderer", "TONEDG1A"','toneDg1aSignalStatistics']:
    if marker not in out: raise SystemExit("TONEDG1A invariant missing "+marker)
if "t.copyElements(r,0);" in out: raise SystemExit("TONEDG1A copyElements regression")
print("TONEDG1A applied; exact assets validated; diagnostic 14-bit input mapping active")
