#include <jni.h>
#include <cstring>
#include <new>
#include "m10r_statistics.h"
#include "selftest_fixture.hpp"

// The fixture contains original-firmware replay bytes, not outputs calculated
// by this bridge. Run it on the phone before evaluating uncalibrated phone data.
extern "C" JNIEXPORT jboolean JNICALL
Java_com_particlesdevs_photoncamera_m10r_M10RFirmwareShadow2R_nativeSelfTest(JNIEnv*,jclass) {
    try {
    static_assert(sizeof(M10RGridInput)==sizeof(selftest_input));
    static_assert(sizeof(M10RGridOutput)==sizeof(selftest_output));
    M10RGridInput in{};M10RGridOutput out{};
    std::memcpy(&in,selftest_input,sizeof(in));
    return m10r_meter_grid(&in,&out)==0 &&
        std::memcmp(&out,selftest_output,sizeof(out))==0 ? JNI_TRUE:JNI_FALSE;
    } catch (...) { return JNI_FALSE; }
}
extern "C" JNIEXPORT jintArray JNICALL
Java_com_particlesdevs_photoncamera_m10r_M10RFirmwareShadow2R_nativeEvaluate(
        JNIEnv* env,jclass,jlongArray cells,jint sv,jint tv) {
    try {
    if(!cells||env->GetArrayLength(cells)!=352||sv< -32768||sv>32767||tv< -32768||tv>32767) {
        env->ThrowNew(env->FindClass("java/lang/IllegalArgumentException"),"firmware shadow input");return nullptr;
    }
    jlong y[352];env->GetLongArrayRegion(cells,0,352,y);if(env->ExceptionCheck())return nullptr;
    M10RGridInput in{};in.step_a=2;in.step_b=2;in.av_q8=0;in.sv_q8=sv;in.tv_q8=tv;
    // Fpos=0 is the original unknown sentinel. No phone diopter binding is inferred.
    in.fpos=0;
    for(unsigned i=0;i<352;i++) {
        if(y[i]<0||uint64_t(y[i])>UINT32_MAX) {
            env->ThrowNew(env->FindClass("java/lang/IllegalArgumentException"),"firmware shadow Y range");return nullptr;
        }
        in.y_sums[i]=uint32_t(y[i]);
    }
    // Four tilt hypotheses; no undocumented Android-to-Leica rotation binding.
    constexpr unsigned stride=229;jint packed[4*stride]{};
    for(unsigned t=0;t<4;t++) {
        in.tilt=t;M10RGridOutput out{};unsigned p=t*stride;
        packed[p++]=m10r_meter_grid(&in,&out);
        auto add=[&](const M10RYResult& r) {
            packed[p++]=r.status;packed[p++]=r.ev_q8;packed[p++]=r.bv_q8;
            packed[p++]=jint(r.normalized_y);packed[p++]=jint(r.normalized_reference);
        };
        add(out.integral);for(const auto& r:out.regions)add(r);
        packed[p++]=out.mfm_status;packed[p++]=out.mfm_bv_q8;packed[p++]=out.mfm_ev_q8;
        for(unsigned i=0;i<100;i++) {
            uint32_t w;std::memcpy(&w,out.aggregate.work+i*4,4);std::memcpy(&packed[p++],&w,4);
        }
    }
    jintArray result=env->NewIntArray(4*stride);
    if(result)env->SetIntArrayRegion(result,0,4*stride,packed);
    return result;
    } catch (const std::bad_alloc&) {
        env->ThrowNew(env->FindClass("java/lang/OutOfMemoryError"),"firmware shadow allocation");return nullptr;
    } catch (...) {
        env->ThrowNew(env->FindClass("java/lang/IllegalStateException"),"firmware shadow native failure");return nullptr;
    }
}
