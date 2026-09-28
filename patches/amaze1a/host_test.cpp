#include "session.h"
#include <iostream>
#include <random>
#include <thread>
#include <future>
#include <limits>
using namespace m10r_amaze1a;
static int checks=0, cases=0;
void check(bool ok,const char* label){if(!ok)throw std::runtime_error(label);++checks;}
std::vector<uint16_t> render(const std::vector<uint16_t>& raw,int w,int h,int cfa,double scale,double nr,double nb,int band,int workers) {
    Session s(w,h,cfa,scale,nr,nb,workers,band);
    for(int y=0;y<h;++y)s.loadRow(y,raw.data()+size_t(y)*w);
    std::vector<uint16_t> out(size_t(w)*h*3,12345), row((w-32)*3);
    for(int top=0;top<h;top+=band) {
        int rows=std::min(band,h-top);s.process(top,rows);
        for(int y=std::max(top,16);y<std::min(top+rows,h-16);++y) {
            s.interiorRow(y,row.data());
            std::copy(row.begin(),row.end(),out.begin()+(size_t(y)*w+16)*3);
        }
    }
    return out;
}
int main(int argc,char**) {
 try {
    std::mt19937 rng(0x10a2e);
    const int sizes[][2]={{64,64},{257,301},{386,530}};
    const double neutrals[][2]={{1.,1.},{.4,1.5},{1.7,.2}};
    for(int cfa=0;cfa<4;++cfa)for(const auto& dim:sizes)for(const auto& n:neutrals)for(int kind=0;kind<3;++kind) {
        const int w=dim[0],h=dim[1];
        std::vector<uint16_t> raw(size_t(w)*h);
        Session lattice(w,h,cfa,.5,n[0],n[1],1);
        for(int y=0;y<h;++y)for(int x=0;x<w;++x) {
            const int ch=lattice.channel(y,x);
            const int rgb[3]={16000,24000,32000};
            raw[size_t(y)*w+x]=kind==0?rgb[ch]:kind==1?((x*3+y*5)%31<15?62000:2000):uint16_t(rng());
        }
        auto full=render(raw,w,h,cfa,.5,n[0],n[1],h,1);
        auto b128=render(raw,w,h,cfa,.5,n[0],n[1],128,1);
        auto b256=render(raw,w,h,cfa,.5,n[0],n[1],256,1);
        auto parallel=render(raw,w,h,cfa,.5,n[0],n[1],256,4);
        check(full==b128,"full/128 band parity");
        check(full==b256,"full/256 band parity");
        check(full==parallel,"one/four worker parity");
        bool samples=true,borders=true,flat=true;
        for(int y=0;y<h;++y)for(int x=0;x<w;++x) {
            if(x<16 || y<16 || x>=w-16 || y>=h-16) {
                for(int ch=0;ch<3;++ch)borders &= full[(size_t(y)*w+x)*3+ch]==12345;
            } else {
                samples &= full[(size_t(y)*w+x)*3+lattice.channel(y,x)]==raw[size_t(y)*w+x];
                if(kind==0)for(int ch=0;ch<3;++ch)flat &= std::abs(int(full[(size_t(y)*w+x)*3+ch])-(16000+8000*ch))<=1;
            }
        }
        check(samples,"measured CFA samples retained");
        check(borders,"EA border untouched");
        if(kind==0)check(flat,"flat channel order/colour retained within one code");
        ++cases;
    }
    // TAIL1A: the old suite's nonconstant frames ended 18 or 45 rows after
    // a tile boundary. Sweep every short remainder with nonconstant input.
    // Full-frame reconstruction is the oracle; compare within each backend.
    int shortTailCases=0;
    for(int cfa=0;cfa<4;++cfa)for(int tail=1;tail<=20;++tail) {
        const int w=192,h=256+tail;
        std::vector<uint16_t> raw(size_t(w)*h);
        for(auto& v:raw)v=uint16_t(rng());
        auto full=render(raw,w,h,cfa,.5,.4,1.5,h,1);
        check(full==render(raw,w,h,cfa,.5,.4,1.5,128,1),"short tail full/128 parity");
        check(full==render(raw,w,h,cfa,.5,.4,1.5,256,1),"short tail full/256 parity");
        check(full==render(raw,w,h,cfa,.5,.4,1.5,256,4),"short tail worker parity");
        Session lattice(w,h,cfa,.5,.4,1.5,1);
        bool samples=true,borders=true;
        for(int y=0;y<h;++y)for(int x=0;x<w;++x) {
            if(x<16 || y<16 || x>=w-16 || y>=h-16) {
                for(int ch=0;ch<3;++ch)borders &= full[(size_t(y)*w+x)*3+ch]==12345;
            } else {
                samples &= full[(size_t(y)*w+x)*3+lattice.channel(y,x)]==raw[size_t(y)*w+x];
            }
        }
        check(samples,"short tail measured CFA samples retained");
        check(borders,"short tail EA border untouched");
        ++shortTailCases;++cases;
    }
    for(double scale:{1.0,.5,.25,1./64})for(const auto& n:neutrals) {
        Session s(64,64,0,scale,n[0],n[1],1);
        check(std::abs(1.0/s.initGain-scale/s.headroom)<1e-15,"clip coordinate relation");
    }
    auto invalid=[&](auto fn){bool caught=false;try{fn();}catch(const std::invalid_argument&){caught=true;}check(caught,"invalid input rejected");};
    invalid([]{Session s(63,64,0,1,1,1,1);});
    invalid([]{Session s(64,64,4,1,1,1,1);});
    invalid([]{Session s(64,64,0,0,1,1,1);});
    invalid([]{Session s(64,64,0,1,.01,1,1);});
    invalid([]{Session s(64,64,0,1,1,1,0);});
    invalid([]{Session s(64,64,0,1,1,1,1);s.process(0,64);});
    invalid([]{Session s(64,64,0,1,1,1,1);std::vector<uint16_t> a(64);s.loadRow(1,a.data());});
    invalid([]{Session s(64,512,0,1,1,1,1);std::vector<uint16_t> a(64);for(int y=0;y<512;++y)s.loadRow(y,a.data());s.process(0,129);});
    // Repeated/independent sessions: verifies native host ownership, not phone capture lifecycle.
    std::vector<uint16_t> repeated(129*257,12000);
    auto expected=render(repeated,129,257,2,1,1,1,256,1);
    for(int i=0;i<24;++i)check(render(repeated,129,257,2,1,1,1,256,4)==expected,"repeated session parity");
    auto a=std::async(std::launch::async,[&]{return render(repeated,129,257,2,1,1,1,256,1);});
    auto b=std::async(std::launch::async,[&]{return render(repeated,129,257,2,1,1,1,256,4);});
    check(a.get()==expected && b.get()==expected,"concurrent session independence");
    if(argc>1) {
        std::vector<uint16_t> large(4096*3072,20000);
        auto out=render(large,4096,3072,0,.5,.7,.4,256,4);
        check(out[(size_t(1000)*4096+1000)*3]==20000,"12MP smoke");
    }
    std::cout<<"{\"status\":\"pass\",\"cases\":"<<cases<<",\"assertions\":"<<checks<<",\"shortTailCases\":"<<shortTailCases<<",\"actualAmazeExecuted\":true,\"realRawReplay\":false,\"deviceValidated\":false}"<<std::endl;
    return 0;
 }catch(const std::exception& e){std::cerr<<"FAILED after "<<checks<<" checks / "<<cases<<" cases: "<<e.what()<<std::endl;return 1;}
}
