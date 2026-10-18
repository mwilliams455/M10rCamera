package com.particlesdevs.photoncamera.m10r;

import java.util.Arrays;

/** Renderer-independent regional geometry, with masks supplied by the renderer.
 * A foreground proxy, not semantic subject/sky recognition or Leica firmware parity.
 * Four-neighbour connectivity is evaluated in sensor coordinates, without an up direction.
 */
public final class MultiFieldScene1G {
    private static final int ALL = (1 << 24) - 1;
    private MultiFieldScene1G() {}

    public static final class Scene {
        public final boolean qualified, splitBackground, midtoneBridge;
        public final int midtoneBridgeMask;
        public final int foregroundMask, backgroundMask, backgroundComponents;
        public final double separationEv;
        public final String reason;
        private Scene(boolean qualified,int foreground,int background,double separation,String reason) {
            this(qualified,foreground,background,separation,reason,false,background==0?0:1);
        }
        private Scene(boolean qualified,int foreground,int background,double separation,String reason,
                boolean split,int components) {
            this(qualified,foreground,background,separation,reason,split,components,0);
        }
        private Scene(boolean qualified,int foreground,int background,double separation,String reason,
                boolean split,int components,int bridges) {
            this.qualified=qualified;foregroundMask=foreground;backgroundMask=background;
            separationEv=separation;this.reason=reason;splitBackground=split;backgroundComponents=components;
            midtoneBridgeMask=bridges;midtoneBridge=bridges!=0;
        }
    }

    public static Scene evaluate(double[] rawRegions,int darkMask,int brightMask) {
        return evaluate(rawRegions,darkMask,brightMask,0);
    }
    public static Scene evaluate(double[] rawRegions,int darkMask,int brightMask,int midtoneMask) {
        if(rawRegions==null||rawRegions.length!=24||(darkMask&brightMask)!=0
                ||((darkMask|brightMask)&midtoneMask)!=0
                ||((darkMask|brightMask|midtoneMask)&~ALL)!=0)return fail("invalid_regions");
        for(double v:rawRegions)if(!Double.isFinite(v)||v<0)return fail("invalid_regions");
        int foreground=largestComponent(darkMask),background=largestComponent(brightMask);
        // Keep a broad connected foreground. SPLITBG1P also admits multiple
        // substantial bright components touching the frame edge; single-field
        // lights and interior bright patches cannot accumulate into a background.
        if(Integer.bitCount(foreground)<6||Integer.bitCount(foreground)>18)
            return fail("insufficient_coherent_regions");
        boolean split=false;int groups=1;
        if(Integer.bitCount(background)<4) {
            int remaining=brightMask; background=0;groups=0;
            while(remaining!=0) {
                int component=component(remaining);remaining&=~component;
                if(Integer.bitCount(component)>=2&&touchesBoundary(component)) {
                    background|=component;groups++;
                }
            }
            if(groups<2||Integer.bitCount(background)<4)return fail("insufficient_coherent_regions");
            split=true;
        }
        int inner=0,boundary=0,contactMask=0;
        for(int f=0;f<24;f++) {
            int y=f/6,x=f%6;
            if((foreground&(1<<f))!=0) {
                if(y>0&&y<3&&x>0&&x<5)inner++;
                if((neighbours(f)&background)!=0)contactMask|=1<<f;
            }
            if((background&(1<<f))!=0&&(y==0||y==3||x==0||x==5))boundary++;
        }
        int contacts=Integer.bitCount(contactMask),bridges=0;
        if(inner<2||boundary<3)return fail("foreground_background_geometry_weak");
        if(contacts<2) {
            // MIDGAP1S: a single connected background may meet a broad dark
            // foreground through one intermediate field. Require an existing
            // direct contact plus two distinct bridges supporting at least two
            // additional foreground fields. Never grow either target mask or
            // chain intermediate fields. Every bridge needs increasing RAW
            // brightness from foreground through the bridge to background.
            int supported=0;
            if(!split&&contacts==1)for(int f=0;f<24;f++)if((midtoneMask&(1<<f))!=0) {
                int nearForeground=neighbours(f)&foreground&~contactMask;
                int nearBackground=neighbours(f)&background,local=0;
                for(int a=0;a<24;a++)if((nearForeground&(1<<a))!=0)
                    for(int b=0;b<24;b++)if((nearBackground&(1<<b))!=0
                            &&rawRegions[a]<rawRegions[f]&&rawRegions[f]<rawRegions[b])local|=1<<a;
                if(local!=0){bridges|=1<<f;supported|=local;}
            }
            if(Integer.bitCount(bridges)<2||Integer.bitCount(supported)<2)
                return fail("foreground_background_geometry_weak");
        }
        double dark=median(rawRegions,foreground),bright=median(rawRegions,background);
        if(dark<=0||bright<=0)return fail("no_measurable_foreground");
        double separation=Math.log(bright/dark)/Math.log(2);
        if(split) {
            // Every accepted bright group must support the RAW separation. A
            // single extreme patch cannot authorize the rest of the background.
            int remaining=background;
            while(remaining!=0) {
                int component=component(remaining);remaining&=~component;
                double groupBright=median(rawRegions,component);
                if(groupBright<=0)return fail("no_measurable_background");
                separation=Math.min(separation,Math.log(groupBright/dark)/Math.log(2));
            }
        }
        return new Scene(separation>=2.0,foreground,background,separation,
                separation>=2.0?(bridges!=0?"midtone_bridge_foreground_proxy":
                        split?"split_bright_background_proxy":"broad_backlit_foreground_proxy")
                        :"insufficient_raw_separation",split,groups,bridges);
    }
    private static Scene fail(String reason){return new Scene(false,0,0,0,reason);}
    private static double median(double[] values,int mask) {
        double[] a=new double[Integer.bitCount(mask)];int n=0;
        for(int f=0;f<24;f++)if((mask&(1<<f))!=0)a[n++]=values[f];
        Arrays.sort(a);return (a[(n-1)/2]+a[n/2])*.5;
    }
    private static int largestComponent(int mask) {
        int best=0;
        while(mask!=0) {
            int component=component(mask);
            mask&=~component;
            if(Integer.bitCount(component)>Integer.bitCount(best))best=component;
        }
        return best;
    }
    private static int component(int mask) {
        int component=Integer.lowestOneBit(mask),previous;
        do {
            previous=component;
            for(int f=0;f<24;f++)if((component&(1<<f))!=0)component|=neighbours(f)&mask;
        }while(component!=previous);
        return component;
    }
    private static boolean touchesBoundary(int mask) {
        for(int f=0;f<24;f++)if((mask&(1<<f))!=0&&(f/6==0||f/6==3||f%6==0||f%6==5))return true;
        return false;
    }
    private static int neighbours(int f) {
        int y=f/6,x=f%6,mask=0;
        if(y>0)mask|=1<<(f-6);if(y<3)mask|=1<<(f+6);
        if(x>0)mask|=1<<(f-1);if(x<5)mask|=1<<(f+1);
        return mask;
    }
}
