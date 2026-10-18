package com.particlesdevs.photoncamera.m10r;

/** Short display-only grace for Camera2/SurfaceTexture callback ordering.
 * A held transform is never evidence of an exactly matched rendered frame.
 */
final class M10RPreviewContinuity1C {
    static final long GRACE_NS=120_000_000L;
    static final class Held {
        final M10RPreviewState1A.Observation observation;
        final M10RPreviewColour1A.Frame colour;
        final double scale;
        final long drawnNs;
        Held(M10RPreviewState1A.Observation o,M10RPreviewColour1A.Frame f,double s,long n) {
            observation=o;colour=f;scale=s;drawnNs=n;
        }
    }
    private Held last;
    void clear(){last=null;}
    void drawn(M10RPreviewState1A.Observation o,M10RPreviewColour1A.Frame f,double scale,long now) {
        if(o!=null&&f!=null&&f.ready&&f.matches(o)&&M10RPreviewState1A.current(o)
                &&Double.isFinite(scale)&&scale>0)last=new Held(o,f,scale,now);
    }
    Held held(long textureTimestamp,long now) {
        Held h=last;
        if(h==null)return null;
        if(!M10RPreviewState1A.current(h.observation)||now<h.drawnNs
                ||now-h.drawnNs>GRACE_NS||textureTimestamp<h.observation.timestamp
                ||textureTimestamp-h.observation.timestamp>GRACE_NS
                ||now<h.colour.observedNs||now-h.colour.observedNs>M10RPreviewColour1A.COLOUR_AGE_NS) {
            last=null;return null;
        }
        // Deliberately do not refresh drawnNs: consecutive misses cannot extend grace.
        return h;
    }
}
