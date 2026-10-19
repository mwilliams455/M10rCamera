package com.particlesdevs.photoncamera.m10r;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

/** Read-only RAW white-candidate probe. No returned proposal has render authority.
 * Experimental limits bound the deviation from the camera's reported neutral;
 * they are not Leica firmware constants or proof that a material is neutral.
 */
public final class M10RWhiteBalanceProbe1D {
    public static final String REVISION="M10R_WBPROBE1D_BOUNDED_RAW_CANDIDATES";
    public static final int COLS=32,ROWS=24;
    private static final double LOG2=Math.log(2);
    private M10RWhiteBalanceProbe1D() {}

    public static Result inspect(short[] raw,int width,int height,int cfa,double storageScale,double[] neutral) {
        return inspect(raw,width,height,cfa,storageScale,neutral,.40,.65);
    }

    // Parameterized only for offline sensitivity checks; production uses defaults.
    static Result inspect(short[] raw,int width,int height,int cfa,double scale,double[] neutral,
                          double maxBlueShiftEv,double brightnessQuantile) {
        if(raw==null||width<64||height<48||(long)width*height!=raw.length||(width&1)!=0||(height&1)!=0
                ||cfa<0||cfa>3||!finitePositive(scale)||scale>1||neutral==null||neutral.length!=3
                ||!finitePositive(neutral[0])||!finitePositive(neutral[1])||!finitePositive(neutral[2])
                ||!finitePositive(maxBlueShiftEv)||maxBlueShiftEv>.5||maxBlueShiftEv<.10
                ||!Double.isFinite(brightnessQuantile)||brightnessQuantile<0||brightnessQuantile>1)
            return Result.empty("invalid_input");
        double nr=neutral[0]/neutral[1],nb=neutral[2]/neutral[1];
        if(!finitePositive(nr)||!finitePositive(nb))return Result.empty("invalid_neutral");
        int[] red={0,1,2,3},blue={3,2,1,0};
        List<Tile> valid=new ArrayList<>();
        double[] lr=new double[16],lb=new double[16],greens=new double[16],quad=new double[4];
        for(int ty=0;ty<ROWS;ty++)for(int tx=0;tx<COLS;tx++) {
            int n=0;
            for(int iy=0;iy<4;iy++)for(int ix=0;ix<4;ix++) {
                int y=((int)((ty+(iy+.5)/4)*height/ROWS))&~1;
                int x=((int)((tx+(ix+.5)/4)*width/COLS))&~1;
                quad[0]=(raw[y*width+x]&65535)/65535.0/scale;
                quad[1]=(raw[y*width+x+1]&65535)/65535.0/scale;
                quad[2]=(raw[(y+1)*width+x]&65535)/65535.0/scale;
                quad[3]=(raw[(y+1)*width+x+1]&65535)/65535.0/scale;
                double lo=Double.POSITIVE_INFINITY,hi=0,g1=0,g2=0;
                int ng=0;
                for(int k=0;k<4;k++) {
                    lo=Math.min(lo,quad[k]);hi=Math.max(hi,quad[k]);
                    if(k!=red[cfa]&&k!=blue[cfa]){if(ng++==0)g1=quad[k];else g2=quad[k];}
                }
                double g=(g1+g2)*.5;
                // Low-signal, clipped/shading-amplified, and edge-inconsistent quads cannot vote.
                if(!(lo>.005&&hi<.85&&Math.abs(g1-g2)/g<.15))continue;
                lr[n]=Math.log((quad[red[cfa]]/g)/nr)/LOG2;
                lb[n]=Math.log((quad[blue[cfa]]/g)/nb)/LOG2;
                greens[n++]=g;
            }
            if(n<12)continue;
            double r=median(lr,n),b=median(lb,n),mr=mad(lr,n,r),mb=mad(lb,n,b);
            if(Math.max(mr,mb)>.06)continue;
            valid.add(new Tile(tx,ty,r,b,median(greens,n),mr,mb));
        }
        if(valid.size()<6)return new Result("insufficient_valid_tiles",valid,Collections.emptyList(),Collections.emptyList(),null,0,0);
        double[] brightness=new double[valid.size()];
        for(int i=0;i<brightness.length;i++)brightness[i]=valid.get(i).green;
        Arrays.sort(brightness);
        double pos=brightnessQuantile*(brightness.length-1);int lo=(int)pos,hi=Math.min(lo+1,brightness.length-1);
        double threshold=brightness[lo]+(brightness[hi]-brightness[lo])*(pos-lo);
        List<Tile> candidates=new ArrayList<>();
        for(Tile t:valid)if(t.green>=threshold&&t.r>=-.10&&t.r<=.25&&t.b>=-maxBlueShiftEv&&t.b<=-.10)candidates.add(t);
        if(candidates.size()<6)return new Result("insufficient_candidates",valid,candidates,Collections.emptyList(),null,threshold,0);
        List<Tile> best=Collections.emptyList();
        for(Tile center:candidates) {
            List<Tile> near=near(candidates,center.r,center.b);
            if(near.size()>best.size())best=near;
        }
        double[] center=center(best);
        List<Tile> selected=near(candidates,center[0],center[1]);
        if(selected.size()<6)return new Result("insufficient_consensus",valid,candidates,selected,null,threshold,0);
        center=center(selected);
        // A distinct, similarly supported mode makes the scene ambiguous.
        List<Tile> remaining=new ArrayList<>(candidates);remaining.removeAll(selected);
        int competing=0;
        for(Tile t:remaining)competing=Math.max(competing,near(remaining,t.r,t.b).size());
        if(competing>=Math.max(3,(selected.size()+1)/2))
            return new Result("competing_neutral_modes",valid,candidates,selected,null,threshold,competing);
        int minX=COLS,maxX=-1,minY=ROWS,maxY=-1;
        for(Tile t:selected){minX=Math.min(minX,t.x);maxX=Math.max(maxX,t.x);minY=Math.min(minY,t.y);maxY=Math.max(maxY,t.y);}
        if(minX==maxX||minY==maxY)return new Result("insufficient_spatial_support",valid,candidates,selected,null,threshold,competing);
        double[] proposal={nr*Math.pow(2,center[0]),1,nb*Math.pow(2,center[1])};
        return new Result("raw_candidate_consensus_unverified_material",valid,candidates,selected,proposal,threshold,competing);
    }

    private static List<Tile> near(List<Tile> tiles,double r,double b) {
        List<Tile> out=new ArrayList<>();
        for(Tile t:tiles)if(Math.max(Math.abs(t.r-r),Math.abs(t.b-b))<=.10)out.add(t);
        return out;
    }
    private static double[] center(List<Tile> tiles) {
        double[] r=new double[tiles.size()],b=new double[tiles.size()];
        for(int i=0;i<r.length;i++){r[i]=tiles.get(i).r;b[i]=tiles.get(i).b;}
        return new double[]{median(r,r.length),median(b,b.length)};
    }
    private static boolean finitePositive(double x){return Double.isFinite(x)&&x>0;}
    private static double median(double[] values,int n){double[] a=Arrays.copyOf(values,n);Arrays.sort(a);return n%2==1?a[n/2]:(a[n/2-1]+a[n/2])*.5;}
    private static double mad(double[] values,int n,double median){double[] a=new double[n];for(int i=0;i<n;i++)a[i]=Math.abs(values[i]-median);return median(a,n);}

    public static final class Tile {
        public final int x,y;
        public final double r,b,green,madR,madB;
        Tile(int x,int y,double r,double b,double green,double mr,double mb){this.x=x;this.y=y;this.r=r;this.b=b;this.green=green;madR=mr;madB=mb;}
    }
    public static final class Result {
        public final String reason;
        public final List<Tile> valid,candidates,selected;
        public final double[] proposedNeutral;
        public final double brightnessThreshold;
        public final int competingSupport;
        Result(String why,List<Tile> valid,List<Tile> candidates,List<Tile> selected,double[] neutral,double threshold,int competing) {
            reason=why;this.valid=Collections.unmodifiableList(new ArrayList<>(valid));this.candidates=Collections.unmodifiableList(new ArrayList<>(candidates));this.selected=Collections.unmodifiableList(new ArrayList<>(selected));
            proposedNeutral=neutral==null?null:neutral.clone();brightnessThreshold=threshold;competingSupport=competing;
        }
        public boolean hasProposal(){return proposedNeutral!=null;}
        static Result empty(String reason){return new Result(reason,Collections.emptyList(),Collections.emptyList(),Collections.emptyList(),null,0,0);}
    }
}
