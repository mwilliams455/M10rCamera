#include <jni.h>
// Per-context order: metering selects legacy, experimental preview opts in.
extern "C" JNIEXPORT void JNICALL
Java_com_particlesdevs_photoncamera_m10r_M10RNativeRenderer_nativeProcessTile(
        JNIEnv*, jclass, jshortArray, jint, jdouble, jdoubleArray, jintArray,
        jdoubleArray, jdoubleArray, jintArray, jintArray, jintArray, jlongArray, jboolean);
extern "C" JNIEXPORT void JNICALL
Java_com_particlesdevs_photoncamera_m10r_M10RExposureNative1B_nativeRender(
        JNIEnv* e, jclass c, jshortArray rgb, jint n, jdouble scale,
        jdoubleArray src, jintArray ca9, jdoubleArray work, jdoubleArray output,
        jintArray tone, jintArray dg, jintArray pixels, jlongArray counts, jboolean cc1BeforeDg) {
    Java_com_particlesdevs_photoncamera_m10r_M10RNativeRenderer_nativeProcessTile(
            e,c,rgb,n,scale,src,ca9,work,output,tone,dg,pixels,counts,cc1BeforeDg);
}
