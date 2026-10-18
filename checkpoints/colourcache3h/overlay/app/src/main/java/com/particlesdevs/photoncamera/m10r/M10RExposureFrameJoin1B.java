package com.particlesdevs.photoncamera.m10r;

/**
 * Bounded request-owned RAW/result rendezvous, independent of callback arrival order.
 * This is NOT a "next RAW belongs to the meter" interceptor. The camera adapter must
 * provide the request's tag and capture-start timestamp, and must not pass unrelated
 * photographic images here. Returning false means ownership remains with the caller.
 */
public final class M10RExposureFrameJoin1B<F extends AutoCloseable,R> {
    public static final class Ticket {
        public final String cameraKey;public final long session,generation,issuedAtNs;
        Ticket(String camera,long session,long generation,long now){
            cameraKey=camera;this.session=session;this.generation=generation;issuedAtNs=now;
        }
    }
    public static final class Pair<F extends AutoCloseable,R> implements AutoCloseable {
        public final Ticket ticket;public final long timestampNs,observedAtNs;public final R result;
        private F frame;
        Pair(Ticket t,long ts,long observed,F frame,R r){ticket=t;timestampNs=ts;observedAtNs=observed;this.frame=frame;result=r;}
        public synchronized F frame(){if(frame==null)throw new IllegalStateException("closed frame");return frame;}
        @Override public synchronized void close(){F f=frame;frame=null;dispose(f);}
    }
    private String camera;private long session,generation;
    private Ticket pending;private long startedTs,imageTs,resultTs,observedNs;
    private F image;private R result;
    public synchronized void activate(String cameraKey,long session){
        if(cameraKey==null||cameraKey.isEmpty()||session<=this.session)throw new IllegalArgumentException("new session required");
        abandon();this.camera=cameraKey;this.session=session;
    }
    public synchronized Ticket begin(long now){
        if(camera==null||now<=0||pending!=null)return null;
        pending=new Ticket(camera,session,++generation,now);return pending;
    }
    private boolean live(Ticket t,long now){
        return t!=null&&t==pending&&camera!=null&&now>=t.issuedAtNs&&now-t.issuedAtNs<=M10RExposure1A.MAX_AGE_NS;
    }
    public synchronized boolean started(Ticket t,long ts,long now){
        if(!live(t,now)||ts<=0)return false;
        if(startedTs!=0&&startedTs!=ts){abandon();return false;}
        startedTs=ts;return true;
    }
    public synchronized boolean image(Ticket t,long ts,long now,F frame){
        if(!live(t,now)||frame==null||ts<=0)return false;
        if(image==frame)return true; // duplicate reference: do not release the still-owned lease.
        if(image!=null)return false;
        // If capture-start was delivered first, reject old/unrelated image timestamps immediately.
        if(startedTs!=0&&startedTs!=ts)return false;
        image=frame;imageTs=ts;observedNs=now;return true;
    }
    public synchronized boolean result(Ticket t,long ts,long now,R metadata){
        if(!live(t,now)||ts<=0||metadata==null||result!=null)return false;
        if(startedTs!=0&&startedTs!=ts)return false;
        result=metadata;resultTs=ts;return true;
    }
    public synchronized Pair<F,R> take(Ticket t,long now){
        if(!live(t,now)){if(t==pending)abandon();return null;}
        if(startedTs==0||image==null||result==null)return null;
        if(startedTs!=imageTs||imageTs!=resultTs){abandon();return null;}
        Pair<F,R> out=new Pair<>(pending,imageTs,observedNs,image,result);
        image=null;clear();return out;
    }
    public synchronized void expire(long now){if(pending!=null&&!live(pending,now))abandon();}
    public synchronized void cancel(Ticket t){if(t==pending)abandon();}
    public synchronized void closeSession(){abandon();camera=null;}
    private void abandon(){F old=image;image=null;clear();dispose(old);}
    private void clear(){pending=null;result=null;startedTs=imageTs=resultTs=observedNs=0;}
    private static void dispose(AutoCloseable f){if(f!=null)try{f.close();}catch(Exception ignored){}}
}
