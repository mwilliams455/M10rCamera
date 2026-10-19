package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.CaptureResult;
import com.particlesdevs.photoncamera.BuildConfig;
import org.json.JSONObject;

/**
 * One sensor RAW -> unchanged AMaZE FIX1 -> sparse RGB -> the unchanged native M10-R renderer.
 * No OEM preview inversion, luma-to-RGB synthesis, JPEG gain, HDR or recovered highlight claim.
 * A candidate is an exposure projection of one reconstruction, not a newly captured RAW.
 */
public final class M10RExposureProbe1B {
    public static final String REVISION="M10R_E1B_RAW_AMAZE_SPARSE_NATIVE_COLOUR";
    public static final int WIDTH=176, HEIGHT=128, BORDER=16;
    private M10RExposureProbe1B() {}
    public interface Clock { long nowNs(); }
    public interface Cancelled { boolean get(); }
    public interface Progress { void step(String stage); }
    public static final class Binding {
        public final String cameraKey;
        public final long session,generation,imageTimestampNs,observedAtNs,referenceExposureNs;
        public final int referenceIso;
        public final M10RMetering1U.Config metering;
        public final M10RContrast4B.Level contrast4B;
        public final double referenceUserEv,referenceAutoEv,requestedUserEv;
        public Binding(String cameraKey,long session,long generation,long imageTimestampNs,
                long observedAtNs,long exposure,int iso,double referenceUserEv,double referenceAutoEv,double requestedUserEv) {
            this(cameraKey,session,generation,imageTimestampNs,observedAtNs,exposure,iso,referenceUserEv,referenceAutoEv,requestedUserEv,null);
        }
        public Binding(String cameraKey,long session,long generation,long imageTimestampNs,
                long observedAtNs,long exposure,int iso,double referenceUserEv,double referenceAutoEv,double requestedUserEv,
                M10RMetering1U.Config metering) {
            this(cameraKey,session,generation,imageTimestampNs,observedAtNs,exposure,iso,referenceUserEv,
                    referenceAutoEv,requestedUserEv,metering,M10RContrast4B.Level.STANDARD);
        }
        public Binding(String cameraKey,long session,long generation,long imageTimestampNs,
                long observedAtNs,long exposure,int iso,double referenceUserEv,double referenceAutoEv,double requestedUserEv,
                M10RMetering1U.Config metering,M10RContrast4B.Level contrast) {
            this.metering=metering;
            contrast4B=M10RContrast4B.normalized(contrast);
            if(cameraKey==null||cameraKey.isEmpty()||session<=0||generation<=0||imageTimestampNs<=0
                    ||observedAtNs<=0||exposure<=0||iso<=0||!ev(referenceUserEv)||!ev(referenceAutoEv)||!ev(requestedUserEv))
                throw new IllegalArgumentException("exact immutable frame binding required");
            this.cameraKey=cameraKey;this.session=session;this.generation=generation;
            this.imageTimestampNs=imageTimestampNs;this.observedAtNs=observedAtNs;
            this.referenceExposureNs=exposure;this.referenceIso=iso;
            this.referenceUserEv=referenceUserEv;this.referenceAutoEv=referenceAutoEv;this.requestedUserEv=requestedUserEv;
        }
    }
    public static final class Output {
        public final M10RExposure1A.Probe probe;
        private final short[] sampledRgb;
        private final int[][] candidates;
        private final long[] atWhite, aboveWhite, nearWhite;
        private final M10RHighlightGuard1A.Stats[] positiveStats,baselineStats;
        private final M10RSceneExposure1M.Stats[] positiveSceneStats,baselineSceneStats;
        public final long reconstructionNs, colourNs;
        public final String firmwareShadow2R;
        Output(M10RExposure1A.Probe p,short[] sample,int[][] argb,M10RExposureRaw1B.Prepared raw,long reconstruct,long colour,
                M10RHighlightGuard1A.Stats[] positiveStats,M10RHighlightGuard1A.Stats[] baselineStats){
            this(p,sample,argb,raw,reconstruct,colour,positiveStats,baselineStats,null,null);
        }
        Output(M10RExposure1A.Probe p,short[] sample,int[][] argb,M10RExposureRaw1B.Prepared raw,long reconstruct,long colour,
                M10RHighlightGuard1A.Stats[] positiveStats,M10RHighlightGuard1A.Stats[] baselineStats,
                M10RSceneExposure1M.Stats[] positiveSceneStats,M10RSceneExposure1M.Stats[] baselineSceneStats){
            this.positiveSceneStats=positiveSceneStats==null?null:positiveSceneStats.clone();
            this.baselineSceneStats=baselineSceneStats==null?null:baselineSceneStats.clone();
            probe=p;sampledRgb=sample;candidates=argb;reconstructionNs=reconstruct;colourNs=colour;
            firmwareShadow2R=raw.firmwareShadow2R;
            atWhite=raw.atWhiteByCfaPhase();aboveWhite=raw.aboveWhiteByCfaPhase();nearWhite=raw.nearWhiteByCfaPhase();
            this.positiveStats=positiveStats.clone();this.baselineStats=baselineStats.clone();
        }
        public M10RSceneExposure1M.Stats[] positiveSceneStats(){return positiveSceneStats==null?null:positiveSceneStats.clone();}
        public M10RSceneExposure1M.Stats[] baselineSceneStats(){return baselineSceneStats==null?null:baselineSceneStats.clone();}
        public short[] sampledRgbCopy(){return sampledRgb.clone();}
        public int[] candidateCopy(int step){return candidates[step].clone();}
        public long[] atWhiteByCfaPhase(){return atWhite.clone();}
        public long[] aboveWhiteByCfaPhase(){return aboveWhite.clone();}
        public long[] nearWhiteByCfaPhase(){return nearWhite.clone();}
        public M10RHighlightGuard1A.Stats[] positiveStats(){return positiveStats.clone();}
        public M10RHighlightGuard1A.Stats[] baselineStats(){return baselineStats.clone();}
    }
    public static Output produce(M10RExposureRaw1B.Prepared raw,CaptureResult result,
            M10RExposureNative1B.Context context,Binding binding,Clock clock,Cancelled cancelled) throws Exception {
        return produce(raw,result,context,binding,clock,cancelled,stage -> {});
    }
    public static Output produce(M10RExposureRaw1B.Prepared raw,CaptureResult result,
            M10RExposureNative1B.Context context,Binding binding,Clock clock,Cancelled cancelled,
            Progress progress) throws Exception {
        progress.step("binding_validation");
        if(raw==null||result==null||context==null||binding==null||clock==null||cancelled==null)
            throw new IllegalArgumentException("missing frame input");
        Long ts=result.get(CaptureResult.SENSOR_TIMESTAMP), exposure=result.get(CaptureResult.SENSOR_EXPOSURE_TIME);
        Integer iso=result.get(CaptureResult.SENSOR_SENSITIVITY);
        if(ts==null||ts!=binding.imageTimestampNs||exposure==null||exposure!=binding.referenceExposureNs
                ||iso==null||iso!=binding.referenceIso||context.frameTimestampNs!=ts
                ||!context.cameraKey.equals(binding.cameraKey))
            throw new IllegalArgumentException("RAW/result/colour/exposure binding mismatch");
        if(raw.width<WIDTH+2*BORDER||raw.height<HEIGHT+2*BORDER)
            throw new IllegalArgumentException("probe grid requires complete AMaZE interior");
        progress.step("freshness_before_amaze");
        check(binding,clock,cancelled);
        int[] xs=new int[WIDTH],ys=new int[HEIGHT];
        for(int x=0;x<WIDTH;x++)xs[x]=BORDER+(int)((x+.5)*(raw.width-2*BORDER)/WIDTH);
        for(int y=0;y<HEIGHT;y++)ys[y]=BORDER+(int)((y+.5)*(raw.height-2*BORDER)/HEIGHT);
        short[] samples=new short[WIDTH*HEIGHT*3];
        long start=clock.nowNs();int sampleRow=0;
        progress.step("amaze_initialization");
        try(M10RAmaze1A amaze=M10RAmaze1A.open(raw.normalized,raw.width,raw.height,raw.cfa,
                raw.storageScale,result,context.sourceWhite,new JSONObject())) {
            progress.step("amaze_reconstruction");
            short[] band=new short[raw.width*Math.min(256,raw.height)*3];
            for(int top=0;top<raw.height;top+=256){
                check(binding,clock,cancelled);
                int rows=Math.min(256,raw.height-top);amaze.readBand(top,rows,band);
                while(sampleRow<HEIGHT&&ys[sampleRow]<top+rows){
                    int y=ys[sampleRow];
                    for(int x=0;x<WIDTH;x++)System.arraycopy(band,((y-top)*raw.width+xs[x])*3,
                            samples,(sampleRow*WIDTH+x)*3,3);
                    sampleRow++;
                }
            }
        }
        long reconstructed=clock.nowNs();
        progress.step("sample_validation");
        if(sampleRow!=HEIGHT)throw new IllegalStateException("incomplete RAW probe sampling");
        // MFM sees intent-removed RAW green; colour guards are relative to the USER's
        // chosen EV. Testing only neutral candidates would miss clipping at user +EV.
        double reference=binding.referenceUserEv+binding.referenceAutoEv;
        M10RMetering1U.Measurement measurement=binding.metering==null?null:
                M10RMetering1U.measure(raw.meterGreen1U,raw.width,raw.height,binding.metering);
        int[] fields=measurement==null?null:measurement.fields();
        int count=M10RExposureRange1H.POSITIVE_CANDIDATES;
        int[][] argb=new int[count][];M10RHighlightGuard1A.Stats[] stats=new M10RHighlightGuard1A.Stats[count];
        M10RSceneExposure1M.Stats[] scene=BuildConfig.M10R_METER_RENDERER1M?new M10RSceneExposure1M.Stats[count]:null;
        M10RSceneExposure1M.Stats[] lowerScene=BuildConfig.M10R_METER_RENDERER1M?new M10RSceneExposure1M.Stats[3]:null;
        for(int i=0;i<count;i++){
            progress.step("native_colour_candidate_"+i);
            check(binding,clock,cancelled);
            double inverseScale=Math.pow(2,binding.requestedUserEv+i*.25-reference)/raw.storageScale;
            argb[i]=context.render(samples,inverseScale);
            progress.step("candidate_validation_"+i);
            stats[i]=M10RHighlightGuard1A.measureArgb(argb[i],WIDTH,HEIGHT,fields);
            if(scene!=null)scene[i]=M10RSceneExposure1M.measure(argb[i],WIDTH,HEIGHT);
        }
        // E1F: independent neutral-user evidence prevents the safeguard from
        // chasing/cancelling the user's explicit EV. Reuse the neutral candidate
        // at user EV zero; otherwise render it through the exact same native path.
        M10RHighlightGuard1A.Stats[] baselineStats=new M10RHighlightGuard1A.Stats[3];
        for(int i=0;i<3;i++) {
            progress.step("baseline_colour_candidate_"+i);
            check(binding,clock,cancelled);
            if(i==0&&binding.requestedUserEv==0){
                baselineStats[i]=stats[0];if(lowerScene!=null)lowerScene[i]=scene[0];
            }
            else {
                double scale=Math.pow(2,-i*M10RHighlightGuard1A.STEP_EV-reference)/raw.storageScale;
                int[] pixels=context.render(samples,scale);
                baselineStats[i]=M10RHighlightGuard1A.measureArgb(pixels,WIDTH,HEIGHT,fields);
                if(lowerScene!=null)lowerScene[i]=M10RSceneExposure1M.measure(pixels,WIDTH,HEIGHT);
            }
        }
        progress.step("probe_publication");
        long completed=clock.nowNs();check(binding,clock,cancelled);
        M10RExposure1A.Probe p=new M10RExposure1A.Probe(binding.cameraKey,binding.session,binding.generation,
                context.revision,binding.imageTimestampNs,ts,binding.observedAtNs,completed,
                exposure,iso,binding.referenceUserEv,binding.referenceAutoEv,
                M10RExposure1A.ProbeDomain.M10R_RENDERED_USER_EV_REFERENCE,raw.neutralGreen(reference),stats,
                M10RHighlightGuard1A.noSubject(count),binding.requestedUserEv,baselineStats,measurement);
        return new Output(p,samples,argb,raw,reconstructed-start,completed-reconstructed,stats,baselineStats,scene,lowerScene);
    }
    private static boolean ev(double v){return Double.isFinite(v)&&Math.abs(v)<=32;}
    private static void check(Binding b,Clock clock,Cancelled cancelled){
        long now=clock.nowNs();
        if(cancelled.get())throw new IllegalStateException("probe cancelled");
        if(now<b.observedAtNs||now-b.observedAtNs>M10RExposure1A.MAX_AGE_NS)
            throw new IllegalStateException("probe expired while processing");
    }
}
