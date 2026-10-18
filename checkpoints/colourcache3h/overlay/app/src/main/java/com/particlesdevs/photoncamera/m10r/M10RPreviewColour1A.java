package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.CaptureResult;
import android.hardware.camera2.params.ColorSpaceTransform;
import android.hardware.camera2.params.RggbChannelVector;
import android.hardware.camera2.params.TonemapCurve;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.SynchronousQueue;
import java.util.concurrent.TimeUnit;

/** Controlled ISP preview reconstruction plus an LUT sampled from the actual M10-R renderer.
 * ISP clipping, demosaic, shading and LUT interpolation prevent pixel-exact RAW reproduction.
 */
public final class M10RPreviewColour1A {
    public static final int SIZE=33;
    public static final long COLOUR_AGE_NS=1_000_000_000L;
    private static final AtomicBoolean busy=new AtomicBoolean();
    private static final ThreadPoolExecutor worker=new ThreadPoolExecutor(0,1,30,TimeUnit.SECONDS,
            new SynchronousQueue<>(),r->{Thread t=new Thread(r,"M10RPreviewColour");t.setDaemon(true);return t;});
    private static volatile Frame latest;
    private static volatile Frame failure;
    private static volatile long attemptedAt;
    private M10RPreviewColour1A() {}
    public static void configure(CaptureRequest.Builder b,CameraCharacteristics c) {
        if(c==null)return;
        int[] modes=c.get(CameraCharacteristics.TONEMAP_AVAILABLE_TONE_MAP_MODES);
        Integer n=c.get(CameraCharacteristics.TONEMAP_MAX_CURVE_POINTS);
        if(modes==null||n==null||n<16)return;
        for(int m:modes)if(m==CaptureRequest.TONEMAP_MODE_CONTRAST_CURVE) {
            float[] curve=M10RPreviewMath1A.srgbCurve(n);
            b.set(CaptureRequest.TONEMAP_MODE,CaptureRequest.TONEMAP_MODE_CONTRAST_CURVE);
            b.set(CaptureRequest.TONEMAP_CURVE,new TonemapCurve(curve,curve,curve));return;
        }
    }
    public static Frame request(M10RPreviewState1A.Observation o,long now) {
        return request(o,now,worker,M10RPreviewColour1A::build);
    }
    // Deterministic worker dispatch for lifecycle regression tests; production
    // always uses the single bounded colour worker above.
    interface Builder { Frame build(M10RPreviewState1A.Observation o) throws Exception; }
    static Frame request(M10RPreviewState1A.Observation o,long now,java.util.concurrent.Executor executor,Builder builder) {
        if(o==null)return null;
        Frame f=latest;
        boolean same=f!=null&&f.matches(o);
        // A missing AE compensation echo does not invalidate independently
        // reported colour metadata. Fresh physical measurements with matching
        // submitted controls may refresh the display; build() still validates
        // the reported curve, matrix, gains and boost. This grants no capture authority.
        if(o.meterEvidence&&M10RPreviewState1A.current(o)&&now>=o.observedNs
                &&now-o.observedNs<=250_000_000L
                &&(!same||now-attemptedAt>=250_000_000L)&&busy.compareAndSet(false,true)) {
            attemptedAt=now;
            try {executor.execute(()->{
                Frame built;
                try {built=builder.build(o);}
                catch(Exception|LinkageError|OutOfMemoryError e){built=Frame.failure(o,e.getMessage());}
                if(M10RPreviewState1A.current(o)) {
                    if(built.ready)latest=built;
                    else failure=built;
                }
                busy.set(false);
            });}catch(java.util.concurrent.RejectedExecutionException e){busy.set(false);}
        }
        return available(f,failure,o,now);
    }
    static Frame available(Frame good,Frame failed,M10RPreviewState1A.Observation o,long now) {
        // A transient failed refresh must not evict a still-valid colour transform.
        if(good!=null&&good.ready&&good.matches(o)&&now>=good.observedNs
                &&now-good.observedNs<=COLOUR_AGE_NS)return good;
        return failed!=null&&failed.matches(o)?failed:null;
    }
    static Frame build(M10RPreviewState1A.Observation o)throws Exception {
        return build(o,x->M10RNativeRenderer.previewContext1A(x.characteristics,x.result,x.key));
    }
    interface NativeContext { M10RExposureNative1B.Context create(M10RPreviewState1A.Observation o) throws Exception; }
    static Frame build(M10RPreviewState1A.Observation o,NativeContext factory)throws Exception {
        CaptureResult r=o.result;
        Integer mode=r.get(CaptureResult.TONEMAP_MODE),max=o.characteristics.get(CameraCharacteristics.TONEMAP_MAX_CURVE_POINTS);
        TonemapCurve curve=r.get(CaptureResult.TONEMAP_CURVE);
        ColorSpaceTransform ccm=r.get(CaptureResult.COLOR_CORRECTION_TRANSFORM);
        RggbChannelVector wb=r.get(CaptureResult.COLOR_CORRECTION_GAINS);
        Integer boost=r.get(CaptureResult.CONTROL_POST_RAW_SENSITIVITY_BOOST);
        if(mode==null||mode!=CaptureRequest.TONEMAP_MODE_CONTRAST_CURVE||max==null||max<16
                ||curve==null||ccm==null||wb==null||boost==null||boost<=0)
            throw new IllegalArgumentException("incomplete_controlled_preview_metadata");
        if(Math.abs(wb.getGreenEven()-wb.getGreenOdd())>.01f)
            throw new IllegalArgumentException("unequal_green_gains");
        float[] requested=M10RPreviewMath1A.srgbCurve(max);
        float[][] curves=new float[3][];
        for(int c=0;c<3;c++) {
            curves[c]=new float[2*curve.getPointCount(c)];curve.copyColorCurve(c,curves[c],0);
            if(M10RPreviewMath1A.curveOutputError(requested,curves[c])>3.0/255)
                throw new IllegalArgumentException("reported_preview_curve_disagrees");
        }
        double[] matrix=new double[9];
        for(int y=0;y<3;y++)for(int x=0;x<3;x++)matrix[y*3+x]=ccm.getElement(x,y).doubleValue();
        double[] undo=M10RPreviewMath1A.inverse(matrix);
        double[] gains={wb.getRed(),(wb.getGreenEven()+wb.getGreenOdd())*.5,wb.getBlue()};
        for(int y=0;y<3;y++) {
            if(!Double.isFinite(gains[y])||gains[y]<=0)throw new IllegalArgumentException("invalid_WB");
            for(int x=0;x<3;x++)undo[y*3+x]/=gains[y]*(boost/100.0);
        }
        M10RExposureNative1B.Context context=factory.create(o);
        int[] argb=context.render(cube(),4.0);
        byte[] pixels=new byte[argb.length*4];
        for(int i=0;i<argb.length;i++) {
            pixels[4*i]=(byte)(argb[i]>>>16);pixels[4*i+1]=(byte)(argb[i]>>>8);
            pixels[4*i+2]=(byte)argb[i];pixels[4*i+3]=(byte)255;
        }
        return new Frame(o,true,"native_M10R_LUT_approximate_ISP_source",pixels,
                M10RPreviewMath1A.inverseTexture(curves),M10RPreviewMath1A.columnMajor(undo));
    }
    public static double unshape(double value){return (Math.pow(61,value)-1)/15;}
    public static short[] cube() {
        short[] cube=new short[SIZE*SIZE*SIZE*3];int i=0;
        // Texture atlas: R within each B slice, G along rows.
        for(int g=0;g<SIZE;g++)for(int b=0;b<SIZE;b++)for(int r=0;r<SIZE;r++) {
            cube[i++]=(short)Math.round(65535*unshape(r/(double)(SIZE-1))/4);
            cube[i++]=(short)Math.round(65535*unshape(g/(double)(SIZE-1))/4);
            cube[i++]=(short)Math.round(65535*unshape(b/(double)(SIZE-1))/4);
        }
        return cube;
    }
    public static final class Frame {
        public final Object owner;public final String key,controls,reason;
        public final long observedNs;public final boolean ready;
        final byte[] pixels,inverse;final float[] undo;
        Frame(M10RPreviewState1A.Observation o,boolean ready,String reason,byte[] pixels,byte[] inverse,float[] undo) {
            owner=o.owner;key=o.key;controls=o.controls;observedNs=o.observedNs;this.ready=ready;
            this.reason=reason;this.pixels=pixels;this.inverse=inverse;this.undo=undo;
        }
        static Frame failure(M10RPreviewState1A.Observation o,String why){return new Frame(o,false,why,null,null,null);}
        boolean matches(M10RPreviewState1A.Observation o) {
            return o!=null&&owner==o.owner&&key.equals(o.key)&&controls.equals(o.controls);
        }
    }
}
