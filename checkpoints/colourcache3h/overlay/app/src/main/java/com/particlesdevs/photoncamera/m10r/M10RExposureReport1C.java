package com.particlesdevs.photoncamera.m10r;
/** Immutable request tag; the saved sidecar receives THIS shot's selection, not global mutable state. */
public final class M10RExposureReport1C {
    public final String json;
    public M10RExposureReport1C(org.json.JSONObject value){if(value==null)throw new IllegalArgumentException();json=value.toString();}
}
