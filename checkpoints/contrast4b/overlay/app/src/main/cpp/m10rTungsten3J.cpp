#include <jni.h>
#include <android/bitmap.h>
#include "m10rTungsten3J.h"

extern "C" JNIEXPORT jlong JNICALL
Java_com_particlesdevs_photoncamera_m10r_M10RTungsten3J_00024Native_apply(JNIEnv* env, jclass, jobject bitmap) {
    AndroidBitmapInfo info{};
    if (!bitmap || AndroidBitmap_getInfo(env, bitmap, &info) != ANDROID_BITMAP_RESULT_SUCCESS) return -1;
    if (info.format != ANDROID_BITMAP_FORMAT_RGBA_8888 || !info.width || !info.height
            || uint64_t(info.stride) < uint64_t(info.width)*4u) return -2;
    void* data = nullptr;
    if (AndroidBitmap_lockPixels(env, bitmap, &data) != ANDROID_BITMAP_RESULT_SUCCESS) return -3;
    const int64_t changed = m10r_tungsten3j::applyRgba(static_cast<uint8_t*>(data), info.width, info.height, info.stride);
    if (AndroidBitmap_unlockPixels(env, bitmap) != ANDROID_BITMAP_RESULT_SUCCESS) return -4;
    return changed;
}
