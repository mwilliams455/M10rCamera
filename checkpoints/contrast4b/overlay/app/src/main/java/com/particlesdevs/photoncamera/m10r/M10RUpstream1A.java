package com.particlesdevs.photoncamera.m10r;

/** Photon compatibility boundary for the custom full-sensor M10-R renderer. */
public final class M10RUpstream1A {
    private M10RUpstream1A() {}
    public static final String REVISION = "M10RUPSTREAM1A_RAW16";
    public static final String PHOTON_COMMIT = "4ee108e169496f429c0afa0cc33e57bb6b2ec724";
    public static boolean isM10rBuild() { return true; }
}
