package com.particlesdevs.photoncamera.m10r;
/** Immutable request tag; the saved sidecar receives THIS shot's selection, not global mutable state. */
public final class M10RExposureReport1C {
    public final String json;
    public final M10RRawBinding4A.CameraContext rawContext4A;
    public final M10RContrast4B.Level contrast4B;
    public M10RExposureReport1C(org.json.JSONObject value){this(value,M10RContrast4B.Level.STANDARD);}
    public M10RExposureReport1C(org.json.JSONObject value,M10RContrast4B.Level contrast){
        if(value==null)throw new IllegalArgumentException();
        json=value.toString();rawContext4A=null;contrast4B=M10RContrast4B.normalized(contrast);
    }
    private M10RExposureReport1C(String json,M10RRawBinding4A.CameraContext context,M10RContrast4B.Level contrast){
        this.json=json;this.rawContext4A=context;this.contrast4B=contrast;
    }
    /** Retain the exact exposure payload while binding this request's RAW source. */
    public M10RExposureReport1C withRawContext4A(M10RRawBinding4A.CameraContext context){
        return new M10RExposureReport1C(json,context,contrast4B);
    }
}
