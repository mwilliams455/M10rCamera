package com.particlesdevs.photoncamera.m10r;

import java.nio.ByteBuffer;

/** Fast probe preparation; exact E1B normalization, CFA counters and green meter lattice. */
public final class M10RExposureRaw1E {
    public static final String REVISION="M10R_EXPOSURE1E_EXACT_NATIVE_RAW_PREPARATION";
    private M10RExposureRaw1E() {}
    private static final class Native {
        static { System.loadLibrary("m10rexposureprep"); }
        static native void prepare(byte[] bytes,int offset,int stride,int width,int height,int cfa,
                double[] black,int white,float[] shading,int cols,int rows,double scale,int workers,
                short[] normalized,double[] green,long[] at,long[] above,long[] near);
    }
    public static M10RExposureRaw1B.Prepared prepare(ByteBuffer data,int offset,int rowStride,int pixelStride,
            int width,int height,int originX,int originY,int cfa,double[] black,int white,
            float[] shading,int cols,int rows) {
        return prepare(data,offset,rowStride,pixelStride,width,height,originX,originY,cfa,black,white,
                shading,cols,rows,4);
    }
    static M10RExposureRaw1B.Prepared prepare(ByteBuffer data,int offset,int rowStride,int pixelStride,
            int width,int height,int originX,int originY,int cfa,double[] black,int white,
            float[] shading,int cols,int rows,int workers) {
        if(data==null || width<64 || height<64 || width>8192 || height>8192 || cfa<0 || cfa>3
                || originX!=0 || originY!=0 || pixelStride!=2 || rowStride<(long)width*2 || offset<0
                || (long)offset+(long)(height-1)*rowStride+(long)width*2>data.limit()
                || black==null || black.length!=4 || white<2 || white>65535 || workers<1 || workers>4)
            throw new IllegalArgumentException("full-origin valid RAW16 layout required");
        black=black.clone();
        for(double v:black) if(!Double.isFinite(v)||v<0||v>=white)throw new IllegalArgumentException("black/white");
        if(shading!=null) {
            if(cols<2||rows<2||cols>256||rows>256||shading.length!=(long)cols*rows*4)
                throw new IllegalArgumentException("shading shape");
            shading=shading.clone();
            for(float v:shading)if(!Float.isFinite(v)||v<=0||v>64)throw new IllegalArgumentException("shading values");
        } else if(cols!=0||rows!=0)throw new IllegalArgumentException("absent shading dimensions");
        double max=1;
        if(shading!=null)for(float g:shading)if(g>max)max=g;
        double scale=1/max;
        short[] normalized=new short[Math.multiplyExact(width,height)];
        double[] green=new double[352];
        long[] at=new long[4],above=new long[4],near=new long[4];
        byte[] bytes;
        int nativeOffset,nativeStride;
        if(data.hasArray()) {
            // The live coordinator owns this array and has already closed the camera Image.
            bytes=data.array();nativeOffset=Math.addExact(data.arrayOffset(),offset);nativeStride=rowStride;
        } else {
            // Support read-only/direct callers without changing their cursor, byte order or limits.
            bytes=new byte[Math.multiplyExact(normalized.length,2)];
            ByteBuffer source=data.duplicate();
            for(int y=0;y<height;y++){source.position(offset+y*rowStride);source.get(bytes,y*width*2,width*2);}
            nativeOffset=0;nativeStride=width*2;
        }
        Native.prepare(bytes,nativeOffset,nativeStride,width,height,cfa,black,white,shading,cols,rows,
                scale,workers,normalized,green,at,above,near);
        var prepared=new M10RExposureRaw1B.Prepared(normalized,green,at,above,near,width,height,cfa,scale);
        prepared.meterGreen1U=M10RMetering1U.sampleGreen(ByteBuffer.wrap(bytes),nativeOffset,nativeStride,width,height,cfa,black,white);
        return prepared;
    }
}
