package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.CaptureResult;
import android.util.Rational;
import org.json.JSONObject;

/** RENDER2N: AMaZE interior with unchanged EA border, source/target separation. */
public final class M10RAmaze1A implements AutoCloseable {
    public static final String REVISION = "RENDER2N_AMAZE1A_SOURCE_ONLY_FIX1";
    static { System.loadLibrary("m10ramaze"); }
    private long handle;
    private static native long nativeOpen(short[] raw,int w,int h,int cfa,double scale,double nr,double nb,int workers);
    private static native void nativeReadBand(long handle,int top,int rows,short[] rgb);
    private static native void nativeClose(long handle);
    private M10RAmaze1A(long handle) { this.handle=handle; }

    public static M10RAmaze1A open(short[] raw,int width,int height,int cfa,
            double scale,CaptureResult result,JSONObject d) throws Exception {
        Rational[] neutral=result.get(CaptureResult.SENSOR_NEUTRAL_COLOR_POINT);
        if(neutral==null || neutral.length<3 || neutral[0]==null || neutral[1]==null || neutral[2]==null)
            throw new IllegalArgumentException("AMAZE1A source neutral unavailable");
        double g=neutral[1].doubleValue();
        double nr=neutral[0].doubleValue()/g, nb=neutral[2].doubleValue()/g;
        if(!Double.isFinite(g) || g<=0 || !Double.isFinite(nr) || !Double.isFinite(nb))
            throw new IllegalArgumentException("AMAZE1A invalid source neutral");
        final int workers=4;
        final double headroom=Math.max(1.0,Math.max(1.0/nr,1.0/nb));
        // Write diagnostics before native allocation: no pointer can leak on JSON failure.
        d.put("sourceReconstructionRevision",REVISION);
        d.put("sourceReconstructionAlgorithm","AMaZE_interior_16px_existing_OpenCV_EA_border");
        d.put("amazeSourceNeutralR",nr); d.put("amazeSourceNeutralB",nb);
        d.put("amazeStorageScale",scale); d.put("amazeHeadroom",headroom);
        d.put("amazeInitGain",headroom/scale);
        d.put("amazeClipReference","source_corrected_neutral_unit_one_not_sensor_clip_mask");
        d.put("amazeWorkers",workers); d.put("amazeOutputBandRows",256);
        d.put("amazeFullFrameRgbAllocated",false);
        d.put("amazeRawNoiseCorrectionEnabled",false);
        d.put("amazeDirectionalChromaEnabled",false);
        d.put("amazeGlobalMagentaSuppressionEnabled",false);
        d.put("amazeNativeInputPlaneBytes",4L*width*height);
        d.put("amazeBorderPixels",16);
        d.put("amazeShortTailReflectionRevision","TAIL1A_PHYSICAL_BOTTOM");
        d.put("amazeExtraScratchRows",16);
        d.put("amazeTileScratchRevision","SCRATCH1A_ZERO_EACH_TILE");
        d.put("openCvPurpose","unchanged_EA_border_reference_AMaZE_replaces_interior");
        long pointer=nativeOpen(raw,width,height,cfa,scale,nr,nb,workers);
        if(pointer==0) throw new IllegalStateException("AMAZE1A native open returned null");
        try { return new M10RAmaze1A(pointer); }
        catch(Throwable error) { nativeClose(pointer); throw error; }
    }
    public synchronized void readBand(int top,int rows,short[] rgb) {
        if(handle==0) throw new IllegalStateException("AMAZE1A session closed");
        nativeReadBand(handle,top,rows,rgb);
    }
    @Override public synchronized void close() {
        long pointer=handle; handle=0;
        if(pointer!=0) nativeClose(pointer);
    }
}
