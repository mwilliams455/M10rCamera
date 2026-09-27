#include <jni.h>
#include <memory>
#include <new>
#include "session.h"
using m10r_amaze1a::Session;
namespace {
void report(JNIEnv* env,const char* type,const char* text) {
    if(env->ExceptionCheck()) return;
    jclass klass=env->FindClass(type);
    if(klass){env->ThrowNew(klass,text);env->DeleteLocalRef(klass);}
}
Session* ptr(jlong h) { return reinterpret_cast<Session*>(static_cast<intptr_t>(h)); }
}
extern "C" JNIEXPORT jlong JNICALL
Java_com_particlesdevs_photoncamera_m10r_M10RAmaze1A_nativeOpen(
 JNIEnv* env,jclass,jshortArray raw,jint w,jint h,jint cfa,jdouble scale,jdouble nr,jdouble nb,jint workers) {
 try {
    if(!raw || w<64 || h<64 || w>8192 || h>8192 || env->GetArrayLength(raw)!=int64_t(w)*h)
        throw std::invalid_argument("AMAZE1A RAW array shape");
    auto s=std::make_unique<Session>(w,h,cfa,scale,nr,nb,workers);
    std::vector<jshort> row(w);
    for(int y=0;y<h;++y) {
        env->GetShortArrayRegion(raw,y*w,w,row.data());
        if(env->ExceptionCheck()) return 0;
        s->loadRow(y,reinterpret_cast<const uint16_t*>(row.data()));
    }
    return static_cast<jlong>(reinterpret_cast<intptr_t>(s.release()));
 }catch(const std::bad_alloc&) { report(env,"java/lang/OutOfMemoryError","AMAZE1A source allocation"); }
 catch(const std::invalid_argument& e) {report(env,"java/lang/IllegalArgumentException",e.what());}
 catch(const std::exception& e) {report(env,"java/lang/IllegalStateException",e.what());}
 catch(...) {report(env,"java/lang/IllegalStateException","AMAZE1A unknown native open failure");}
 return 0;
}
extern "C" JNIEXPORT void JNICALL
Java_com_particlesdevs_photoncamera_m10r_M10RAmaze1A_nativeReadBand(
 JNIEnv* env,jclass,jlong handle,jint top,jint rows,jshortArray rgb) {
 try {
    Session* s=ptr(handle);
    if(!s || !rgb || rows<1 || rows>s->height || env->GetArrayLength(rgb)<int64_t(s->width)*rows*3)
        throw std::invalid_argument("AMAZE1A output array shape or closed session");
    s->process(top,rows);
    const int count=(s->width-2*m10r_amaze1a::Border)*3;
    std::vector<uint16_t> row(count);
    for(int y=std::max(top,m10r_amaze1a::Border); y<std::min(top+rows,s->height-m10r_amaze1a::Border); ++y) {
        s->interiorRow(y,row.data());
        // Only the interior is overwritten. The existing EA border stays exact.
        env->SetShortArrayRegion(rgb,((y-top)*s->width+m10r_amaze1a::Border)*3,count,
                reinterpret_cast<const jshort*>(row.data()));
        if(env->ExceptionCheck()) return;
    }
 }catch(const std::bad_alloc&) {report(env,"java/lang/OutOfMemoryError","AMAZE1A band allocation");}
 catch(const std::invalid_argument& e) {report(env,"java/lang/IllegalArgumentException",e.what());}
 catch(const std::exception& e) {report(env,"java/lang/IllegalStateException",e.what());}
 catch(...) {report(env,"java/lang/IllegalStateException","AMAZE1A unknown native band failure");}
}
extern "C" JNIEXPORT void JNICALL
Java_com_particlesdevs_photoncamera_m10r_M10RAmaze1A_nativeClose(JNIEnv*,jclass,jlong handle) {
 delete ptr(handle);
}
