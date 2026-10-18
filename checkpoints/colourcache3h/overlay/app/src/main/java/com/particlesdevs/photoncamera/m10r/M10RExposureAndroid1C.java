package com.particlesdevs.photoncamera.m10r;

import android.graphics.ImageFormat;
import android.graphics.Rect;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CaptureResult;
import android.hardware.camera2.params.LensShadingMap;
import android.media.Image;
import java.nio.ByteBuffer;

/** Own a tight RAW16 copy, then release the camera Image BEFORE expensive reconstruction. */
public final class M10RExposureAndroid1C {
    private M10RExposureAndroid1C(){}
    public static final class Owned {
        final ByteBuffer bytes;final int width,height;final long timestamp;
        Owned(ByteBuffer b,int w,int h,long ts){bytes=b;width=w;height=h;timestamp=ts;}
    }
    public static Owned copyAndClose(Image image,long timestamp) {
        try{
            if(image==null||image.getFormat()!=ImageFormat.RAW_SENSOR||image.getTimestamp()!=timestamp)
                throw new IllegalArgumentException("exact RAW16 image required");
            int w=image.getWidth(),h=image.getHeight();long count=(long)w*h;
            if(w<64||h<64||w>8192||h>8192||count>67108864L)throw new IllegalArgumentException("RAW geometry");
            Rect crop=image.getCropRect();
            if(crop==null||crop.left!=0||crop.top!=0||crop.right!=w||crop.bottom!=h)
                throw new IllegalArgumentException("non-full RAW crop");
            if(image.getPlanes().length!=1)throw new IllegalArgumentException("RAW plane count");
            Image.Plane plane=image.getPlanes()[0];int stride=plane.getRowStride();
            if(plane.getPixelStride()!=2||stride<2*w)throw new IllegalArgumentException("RAW16 stride");
            ByteBuffer source=plane.getBuffer().duplicate();int origin=source.position();
            if((long)origin+(long)(h-1)*stride+2L*w>source.limit())throw new IllegalArgumentException("short RAW buffer");
            byte[] data=new byte[(int)(count*2)];
            for(int y=0;y<h;y++){source.position(origin+y*stride);source.get(data,y*w*2,w*2);}
            return new Owned(ByteBuffer.wrap(data),w,h,timestamp);
        }finally{if(image!=null)image.close();}
    }
    public static M10RExposureProbe1B.Output build(Owned image,CameraCharacteristics c,CaptureResult result,
            M10RExposureProbe1B.Binding binding,M10RExposureProbe1B.Clock clock,M10RExposureProbe1B.Cancelled cancelled)throws Exception{
        return build(image,c,result,binding,clock,cancelled,stage -> {});
    }
    public static M10RExposureProbe1B.Output build(Owned image,CameraCharacteristics c,CaptureResult result,
            M10RExposureProbe1B.Binding binding,M10RExposureProbe1B.Clock clock,M10RExposureProbe1B.Cancelled cancelled,
            M10RExposureProbe1B.Progress progress)throws Exception{
        progress.step("raw_metadata");
        Long ts=result.get(CaptureResult.SENSOR_TIMESTAMP);
        if(ts==null||ts!=image.timestamp||ts!=binding.imageTimestampNs)throw new IllegalArgumentException("RAW/result mismatch");
        Integer cfa=c.get(CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT);
        if(cfa==null||cfa<0||cfa>3)throw new IllegalArgumentException("physical CFA");
        double[] black=M10RNativeRenderer.exposureBlack1B(c,result);int white=M10RNativeRenderer.exposureWhite1B(c,result);
        LensShadingMap map=result.get(CaptureResult.STATISTICS_LENS_SHADING_CORRECTION_MAP);
        float[] gains=null;int cols=0,rows=0;
        if(map!=null&&map.getColumnCount()>=2&&map.getRowCount()>=2){cols=map.getColumnCount();rows=map.getRowCount();gains=new float[map.getGainFactorCount()];map.copyGainFactors(gains,0);}
        progress.step("colour_metadata");
        M10RExposureNative1B.Context context=M10RNativeRenderer.exposureContext1B(c,result,binding.cameraKey);
        progress.step("raw_normalization_native1e");
        M10RExposureRaw1B.Prepared raw=M10RExposureRaw1E.prepare(image.bytes,0,image.width*2,2,image.width,image.height,
                0,0,cfa,black,white,gains,cols,rows);
        // Independent diagnostic sink; its outputs never enter the exposure planner.
        try {
            raw.firmwareShadow2R=M10RFirmwareShadow2R.capture(image.bytes,image.width,image.height,
                    cfa,black,white,c,result,binding);
        } catch(RuntimeException|LinkageError|OutOfMemoryError diagnosticFailure) {
            // Also cover class initialization and allocation before capture's own handler.
            raw.firmwareShadow2R="{\"status\":\"DIAGNOSTIC_UNAVAILABLE\",\"controlsExposure\":false,\"calibrated\":false,\"errorType\":\"diagnostic_entry_failure\"}";
        }
        return M10RExposureProbe1B.produce(raw,result,context,binding,clock,cancelled,progress);
    }
}
