#include <jni.h>
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <new>
#include <stdexcept>
#include <thread>
#include <vector>

namespace {
void fail(JNIEnv* e,const char* type,const char* message) {
    if(e->ExceptionCheck())return;
    jclass c=e->FindClass(type);
    if(c){e->ThrowNew(c,message);e->DeleteLocalRef(c);}
}
struct Bytes {
    JNIEnv* e; jbyteArray a; jbyte* p;
    Bytes(JNIEnv* e,jbyteArray a):e(e),a(a),p(e->GetByteArrayElements(a,nullptr)){}
    ~Bytes(){if(p)e->ReleaseByteArrayElements(a,p,JNI_ABORT);}
};
struct Shorts {
    JNIEnv* e; jshortArray a; jshort* p;
    Shorts(JNIEnv* e,jshortArray a):e(e),a(a),p(e->GetShortArrayElements(a,nullptr)){}
    ~Shorts(){if(p)e->ReleaseShortArrayElements(a,p,0);}
};
struct Axis {int lo,hi,cell;double fraction;};
struct Counts {std::array<jlong,4> at{},above{},near{};};
constexpr int CHANNELS[4][4]={{0,1,2,3},{1,0,3,2},{1,3,0,2},{3,1,2,0}};
}

extern "C" JNIEXPORT void JNICALL
Java_com_particlesdevs_photoncamera_m10r_M10RExposureRaw1E_00024Native_prepare(
        JNIEnv* e,jclass,jbyteArray input,jint offset,jint stride,jint w,jint h,jint cfa,
        jdoubleArray blackArray,jint white,jfloatArray shadingArray,jint cols,jint rows,
        jdouble scale,jint workers,jshortArray output,jdoubleArray greenArray,
        jlongArray atArray,jlongArray aboveArray,jlongArray nearArray) {
    try {
        // Validate again at the JNI boundary, before any pointer arithmetic or worker launch.
        const int64_t pixels=int64_t(w)*h;
        if(!input||!blackArray||!output||!greenArray||!atArray||!aboveArray||!nearArray
                ||w<64||h<64||w>8192||h>8192||cfa<0||cfa>3||offset<0||stride<int64_t(w)*2
                ||white<2||white>65535||workers<1||workers>4
                ||int64_t(offset)+int64_t(h-1)*stride+int64_t(w)*2>e->GetArrayLength(input)
                ||e->GetArrayLength(blackArray)!=4||e->GetArrayLength(output)!=pixels
                ||e->GetArrayLength(greenArray)!=352||e->GetArrayLength(atArray)!=4
                ||e->GetArrayLength(aboveArray)!=4||e->GetArrayLength(nearArray)!=4)
            throw std::invalid_argument("native RAW preparation layout");
        std::array<double,4> black{},den{};
        e->GetDoubleArrayRegion(blackArray,0,4,black.data());if(e->ExceptionCheck())return;
        for(int p=0;p<4;p++) {
            if(!std::isfinite(black[p])||black[p]<0||black[p]>=white)
                throw std::invalid_argument("native black/white");
            den[p]=std::max(1.0,white-black[p]);
        }
        std::vector<float> shading;double maxGain=1.0;
        if(shadingArray) {
            if(cols<2||rows<2||cols>256||rows>256||e->GetArrayLength(shadingArray)!=int64_t(cols)*rows*4)
                throw std::invalid_argument("native shading shape");
            shading.resize(cols*rows*4);e->GetFloatArrayRegion(shadingArray,0,shading.size(),shading.data());
            if(e->ExceptionCheck())return;
            for(float v:shading) {
                if(!std::isfinite(v)||v<=0||v>64)throw std::invalid_argument("native shading values");
                if(v>maxGain)maxGain=v;
            }
        } else if(cols!=0||rows!=0)throw std::invalid_argument("native absent shading dimensions");
        if(!std::isfinite(scale)||scale!=1.0/maxGain)throw std::invalid_argument("native storage scale");
        std::vector<Axis> ax(w),ay(h);
        for(int x=0;x<w;x++) {
            double gx=shading.empty()?0:(x/double(w-1))*(cols-1);
            int lo=int(std::floor(gx));ax[x]={lo,std::min(cols-1,lo+1),std::min(21,int(int64_t(x)*22/w)),gx-lo};
        }
        for(int y=0;y<h;y++) {
            double gy=shading.empty()?0:(y/double(h-1))*(rows-1);
            int lo=int(std::floor(gy));ay[y]={lo,std::min(rows-1,lo+1),std::min(15,int(int64_t(y)*16/h)),gy-lo};
        }
        Bytes bytes(e,input);if(!bytes.p)return;
        Shorts normalized(e,output);if(!normalized.p)return;
        std::array<double,352> green{};std::array<jlong,352> count{};
        std::array<Counts,4> counters{};
        const auto work=[&](int worker) {
            // Whole meter-cell rows belong to one worker: per-cell accumulation order
            // stays identical to Java's y-major loop, with no floating-point reduction.
            int cellBegin=worker*16/workers,cellEnd=(worker+1)*16/workers;
            int begin=(cellBegin*h+15)/16,end=(cellEnd*h+15)/16;
            auto& sums=counters[worker];
            for(int y=begin;y<end;y++)for(int x=0;x<w;x++) {
                const int phase=((y&1)<<1)|(x&1),channel=CHANNELS[cfa][phase];
                const auto* p=reinterpret_cast<const uint8_t*>(bytes.p)+offset+int64_t(y)*stride+x*2;
                const int code=p[0]|(int(p[1])<<8);
                double unit=std::max(0.0,(code-black[phase])/den[phase]);
                if(code==white)sums.at[phase]++;
                if(code>white)sums.above[phase]++;
                if(unit>=.98)sums.near[phase]++;
                unit=std::min(1.0,unit);
                double gain=1;
                if(!shading.empty()) {
                    const Axis& xx=ax[x];const Axis& yy=ay[y];
                    const double fx=xx.fraction,fy=yy.fraction;
                    const double a=shading[(yy.lo*cols+xx.lo)*4+channel],b=shading[(yy.lo*cols+xx.hi)*4+channel];
                    const double d=shading[(yy.hi*cols+xx.lo)*4+channel],f=shading[(yy.hi*cols+xx.hi)*4+channel];
                    gain=std::max(1.0,(a*(1-fx)+b*fx)*(1-fy)+(d*(1-fx)+f*fx)*fy);
                }
                const double value=std::max(0.0,std::min(1.0,unit*gain*scale))*65535;
                const uint32_t integral=static_cast<uint32_t>(value);
                // Exact positive Java Math.round, including doubles just below a half.
                const uint16_t rounded=static_cast<uint16_t>(integral+(value-integral>=.5));
                normalized.p[int64_t(y)*w+x]=static_cast<jshort>(rounded);
                if((channel==1||channel==2)&&(x&7)<2&&(y&7)<2) {
                    int cell=ay[y].cell*22+ax[x].cell;green[cell]+=unit;count[cell]++;
                }
            }
        };
        std::vector<std::thread> threads;threads.reserve(workers-1);
        try {for(int t=1;t<workers;t++)threads.emplace_back(work,t);work(0);}
        catch(...) {for(auto& t:threads)if(t.joinable())t.join();throw;}
        for(auto& t:threads)t.join();
        for(int i=0;i<352;i++) {
            if(count[i]==0)throw std::invalid_argument("RAW too small for complete meter lattice");
            green[i]/=count[i];
        }
        std::array<jlong,4> at{},above{},near{};
        for(int t=0;t<workers;t++)for(int p=0;p<4;p++) {
            at[p]+=counters[t].at[p];above[p]+=counters[t].above[p];near[p]+=counters[t].near[p];
        }
        e->SetDoubleArrayRegion(greenArray,0,352,green.data());
        if(!e->ExceptionCheck())e->SetLongArrayRegion(atArray,0,4,at.data());
        if(!e->ExceptionCheck())e->SetLongArrayRegion(aboveArray,0,4,above.data());
        if(!e->ExceptionCheck())e->SetLongArrayRegion(nearArray,0,4,near.data());
    } catch(const std::bad_alloc&) {fail(e,"java/lang/OutOfMemoryError","native RAW preparation allocation");}
      catch(const std::invalid_argument& ex) {fail(e,"java/lang/IllegalArgumentException",ex.what());}
      catch(const std::exception& ex) {fail(e,"java/lang/IllegalStateException",ex.what());}
      catch(...) {fail(e,"java/lang/IllegalStateException","native RAW preparation failure");}
}
