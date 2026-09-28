// M10R AMAZE1A: source reconstruction only. No target look, NR or chroma filter.
#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <vector>
#include <omp.h>
#include "librtprocess.h"

namespace m10r_amaze1a {
constexpr int Border = 16;
constexpr int BandRows = 256;
class Session {
public:
    const int width, height, cfa, workers, capacityRows;
    const double storageScale, nr, nb, headroom, initGain;
    std::vector<float> input;
    std::vector<float*> inRows, rRows, gRows, bRows;
    std::vector<float> red, green, blue;
    int nextRow = 0, loadedRows = 0;
    Session(int w, int h, int pattern, double s, double redNeutral,
            double blueNeutral, int threads, int capacity = BandRows)
      : width(w), height(h), cfa(pattern), workers(threads), capacityRows(capacity),
        storageScale(s), nr(redNeutral), nb(blueNeutral),
        headroom(std::max({1.0, 1.0/redNeutral, 1.0/blueNeutral})),
        initGain(headroom/s) {
        if (w<64 || h<64 || w>8192 || h>8192 || pattern<0 || pattern>3 ||
            threads<1 || threads>8 || capacity<1 || capacity>h+BandRows ||
            !std::isfinite(s) || s<1.0/64 || s>1.0 ||
            !std::isfinite(nr) || !std::isfinite(nb) ||
            nr<0.0625 || nb<0.0625 || nr>16 || nb>16)
            throw std::invalid_argument("AMAZE1A invalid dimensions/CFA/neutral/storage scale");
        const size_t count=size_t(w)*size_t(h);
        input.resize(count);
        inRows.resize(h); rRows.resize(h,nullptr); gRows.resize(h,nullptr); bRows.resize(h,nullptr);
        // Up to 15 extra scratch rows carry a penultimate band to the physical
        // image bottom. Only the originally requested rows are emitted.
        const size_t band=size_t(w)*std::min(h,capacity+Border);
        red.resize(band); green.resize(band); blue.resize(band);
        for(int y=0;y<h;++y) inRows[y]=input.data()+size_t(y)*w;
    }
    Session(const Session&) = delete;
    Session& operator=(const Session&) = delete;
    int channel(int y,int x) const {
        static constexpr int pattern[4][2][2]={{{0,1},{1,2}},{{1,0},{2,1}},{{1,2},{0,1}},{{2,1},{1,0}}};
        return pattern[cfa][y&1][x&1];
    }
    double neutral(int ch) const {return ch==0?nr:ch==2?nb:1.0;}
    void loadRow(int y,const uint16_t* raw) {
        if(!raw || y!=loadedRows || y>=height) throw std::invalid_argument("AMAZE1A nonsequential source row");
        for(int x=0;x<width;++x) inRows[y][x]=float(double(raw[x])/(neutral(channel(y,x))*headroom));
        ++loadedRows;
    }
    void process(int top,int rows) {
        if(loadedRows!=height || top!=nextRow || top<0 || top%128!=0 || rows<1 ||
            rows>capacityRows || rows>height-top || (top+rows!=height && rows%128!=0))
            throw std::invalid_argument("AMAZE1A invalid band/global tile alignment");
        std::fill(rRows.begin(),rRows.end(),nullptr);
        std::fill(gRows.begin(),gRows.end(),nullptr);
        std::fill(bRows.begin(),bRows.end(),nullptr);
        std::fill(red.begin(),red.end(),0.0f);
        std::fill(green.begin(),green.end(),0.0f);
        std::fill(blue.begin(),blue.end(),0.0f);
        // TAIL1A: when fewer than Border rows remain, upstream's window-end
        // reflection must use the physical bottom, not this band's early end.
        // Keep the global 128-row tile lattice and the logical output schedule.
        const int tail=height-top-rows;
        const int renderRows=rows+((tail>0 && tail<Border)?tail:0);
        for(int y=top;y<top+renderRows;++y) {
            rRows[y]=red.data()+size_t(y-top)*width;
            gRows[y]=green.data()+size_t(y-top)*width;
            bRows[y]=blue.data()+size_t(y-top)*width;
        }
        const unsigned patterns[4][2][2]={{{0,1},{1,2}},{{1,0},{2,1}},{{1,2},{0,1}},{{2,1},{1,0}}};
        struct Threads {
            int previous;
            explicit Threads(int n):previous(omp_get_max_threads()){omp_set_num_threads(n);}
            ~Threads(){omp_set_num_threads(previous);}
        } threads(workers);
        // rawStored = sourceCorrected * storageScale * 65535.
        // Neutral-balanced unit-one -> storageScale/headroom. AMaZE defines
        // clip_pt=1/initGain, so M10-R must pass headroom/storageScale.
        const rpError rc=amaze_demosaic(width,height,0,top,width,renderRows,
                inRows.data(),rRows.data(),gRows.data(),bRows.data(),patterns[cfa],
                [](double){return false;},initGain,Border,65535.f,65535.f,2,false);
        if(rc!=RP_NO_ERROR) throw std::runtime_error("AMAZE1A upstream failure "+std::to_string(int(rc)));
        nextRow=top+rows;
    }
    void interiorRow(int y,uint16_t* rgb) const {
        if(!rgb || y<Border || y>=height-Border || y>=nextRow || !rRows[y])
            throw std::invalid_argument("AMAZE1A invalid output row");
        for(int x=Border;x<width-Border;++x) {
            const double values[3]={rRows[y][x],gRows[y][x],bRows[y][x]};
            for(int ch=0;ch<3;++ch) {
                const double value=values[ch]*headroom*neutral(ch);
                if(!std::isfinite(value)) throw std::runtime_error("AMAZE1A nonfinite reconstruction");
                rgb[3*(x-Border)+ch]=uint16_t(std::llround(std::clamp(value,0.0,65535.0)));
            }
        }
    }
};
}
