package com.particlesdevs.photoncamera.m10r;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

/** Diagnostic scene placement, measured on existing photographic colour candidates.
 * Inspired by M9's neutral-reference global/centre/4x6 evidence. No M9 brightness
 * target, classifier, fixed bias or exposure decision is copied here.
 */
public final class M10RSceneExposure1M {
    public static final String REVISION="M10R_SCENE1M_RENDERED_PLACEMENT_EVIDENCE";
    private M10RSceneExposure1M() {}
    public static final class Stats {
        public final int median,q25,q90,centerMedian,centerQ25,centerWeightedMedian;
        private final int[] fieldMedian,fieldQ25;
        private Stats(int[] global,int[] center,int[] weighted,int[][] fields) {
            median=quantile(global,.5);q25=quantile(global,.25);q90=quantile(global,.9);
            centerMedian=quantile(center,.5);centerQ25=quantile(center,.25);
            centerWeightedMedian=quantile(weighted,.5);fieldMedian=new int[24];fieldQ25=new int[24];
            for(int f=0;f<24;f++){fieldMedian[f]=quantile(fields[f],.5);fieldQ25[f]=quantile(fields[f],.25);}
        }
        public int fieldMedian(int f){return fieldMedian[f];}
        public int fieldQ25(int f){return fieldQ25[f];}
        JSONObject json(double ev)throws JSONException {
            JSONObject d=new JSONObject().put("relativeEv",ev).put("globalMedianCode",median)
                    .put("globalQ25Code",q25).put("globalQ90Code",q90)
                    .put("centerMedianCode",centerMedian).put("centerQ25Code",centerQ25)
                    .put("centerWeightedMedianCode",centerWeightedMedian);
            JSONArray m=new JSONArray(),q=new JSONArray();
            for(int f=0;f<24;f++){m.put(fieldMedian[f]);q.put(fieldQ25[f]);}
            return d.put("fieldMedianCode",m).put("fieldQ25Code",q);
        }
    }
    public static Stats measure(int[] pixels,int width,int height) {
        if(pixels==null||width<6||height<4||width>8192||height>8192||pixels.length!=(long)width*height)
            throw new IllegalArgumentException("complete rendered scene probe");
        int[] g=new int[256],c=new int[256],weighted=new int[256];int[][] fields=new int[24][256];
        for(int y=0;y<height;y++)for(int x=0;x<width;x++) {
            int p=pixels[y*width+x];if((p>>>24)!=255)throw new IllegalArgumentException("opaque probe required");
            int l=(77*((p>>>16)&255)+150*((p>>>8)&255)+29*(p&255)+128)>>8;
            boolean center=x>=width/4&&x<3*width/4&&y>=height/4&&y<3*height/4;
            g[l]++;weighted[l]+=center?3:1;if(center)c[l]++;
            fields[(y*4/height)*6+x*6/width][l]++;
        }
        return new Stats(g,c,weighted,fields);
    }
    private static int quantile(int[] h,double fraction) {
        int n=0;for(int x:h)n+=x;int need=Math.max(1,(int)Math.ceil(n*fraction)),sum=0;
        for(int i=0;i<256;i++){sum+=h[i];if(sum>=need)return i;}return 0;
    }
    static JSONObject describe(M10RExposureProbe1B.Output output)throws JSONException {
        Stats[] positive=output.positiveSceneStats(),baseline=output.baselineSceneStats();
        boolean available=positive!=null&&baseline!=null;
        JSONObject d=new JSONObject().put("revision",REVISION).put("available",available)
                .put("diagnosticOnly",true).put("changesExposure",false)
                .put("rendererRevision",output.probe.rendererRevision)
                .put("candidateUserEv",output.probe.candidateUserEv).put("baselineUserEv",0)
                .put("coordinates","sensor_4x6_no_semantic_subject_detection")
                .put("centerWeight",3).put("codeLuma","integer_77R_150G_29B_over_256")
                .put("additionalRawFrames",0).put("additionalColourPasses",0);
        if(available){
            JSONArray p=new JSONArray(),b=new JSONArray();
            for(int i=0;i<positive.length;i++)p.put(positive[i].json(i*.25));
            for(int i=0;i<baseline.length;i++)b.put(baseline[i].json(-i*.25));
            d.put("positiveCandidates",p).put("baselineCandidates",b);
        }
        return d;
    }
}
