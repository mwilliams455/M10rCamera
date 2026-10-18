package com.particlesdevs.photoncamera.m10r;

/** GL-thread presentation only. Never changes an E1H selection or a camera request. */
final class M10RPreviewExposure1D {
    static final double EV_PER_SECOND=3.0;
    // A capture pause must not accumulate a large catch-up step on the first live frame.
    static final long MAX_STEP_NS=50_000_000L;
    private M10RPreviewState1A.Observation identity;
    private long at;
    private double ev;
    void clear(){identity=null;at=0;}
    double update(M10RPreviewState1A.Observation o,double targetScale,long now) {
        if(o==null||!Double.isFinite(targetScale)||targetScale<=0)
            throw new IllegalArgumentException("finite positive preview scale required");
        double target=Math.log(targetScale)/Math.log(2);
        if(identity==null||identity.owner!=o.owner||!identity.key.equals(o.key)
                ||!identity.controls.equals(o.controls)||now<at)ev=target;
        else {
            double step=EV_PER_SECOND*Math.min(now-at,MAX_STEP_NS)/1e9;
            ev+=Math.max(-step,Math.min(step,target-ev));
        }
        identity=o;at=now;return Math.pow(2,ev);
    }
    static boolean settled(double actual,double target){
        return Double.isFinite(actual)&&Double.isFinite(target)&&actual>0&&target>0
                &&Math.abs(Math.log(actual/target)/Math.log(2))<1e-6;
    }
}
