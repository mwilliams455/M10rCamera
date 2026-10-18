package com.particlesdevs.photoncamera.m10r;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.Map;

/** Request-owned RAW routing. Unrelated frames are forwarded, never used as a probe.
 * Cancelled requests retain a drain ticket until their image is accounted for.
 * A timeout cannot turn a late measurement RAW into a photographic RAW.
 */
public final class M10RExposureGate1C<F extends AutoCloseable,R> {
    public interface Events<F extends AutoCloseable,R> {
        void forward(Object reader,F frame);
        void matched(Ticket ticket,long timestamp,long observed,F frame,R result);
        void failure(Ticket ticket,String reason);
    }
    public static final class Ticket {
        public final Object reader; public final long id;
        private Ticket(Object reader,long id){this.reader=reader;this.id=id;}
    }
    private static final class Frame<F>{final F value;final long observed;Frame(F f,long n){value=f;observed=n;}}
    private final Events<F,R> events;
    private Ticket ticket; private long generation,started,resultTs;
    private R result; private boolean cancelled,reported;
    private final LinkedHashMap<Long,Frame<F>> held=new LinkedHashMap<>();
    public M10RExposureGate1C(Events<F,R> events){if(events==null)throw new IllegalArgumentException();this.events=events;}
    public synchronized Ticket begin(Object reader){
        if(reader==null||ticket!=null)return null;
        ticket=new Ticket(reader,++generation);return ticket;
    }
    public synchronized boolean busy(){return ticket!=null;}
    public synchronized boolean owns(Ticket t){return t!=null&&t==ticket;}
    public void started(Ticket t,long timestamp){
        ArrayList<Runnable> a=new ArrayList<>();
        synchronized(this){
            if(t!=ticket)return;
            if(timestamp<=0||(started!=0&&started!=timestamp)){fail(a,"conflicting_capture_start");}
            else{started=timestamp;reconcile(a);}
        }run(a);
    }
    public void result(Ticket t,long timestamp,R r){
        ArrayList<Runnable> a=new ArrayList<>();
        synchronized(this){
            if(t!=ticket)return;
            if(timestamp<=0||r==null||(result!=null&&resultTs!=timestamp))fail(a,"conflicting_capture_result");
            else{resultTs=timestamp;result=r;reconcile(a);}
        }run(a);
    }
    /** true transfers ownership; false leaves it with caller. */
    public boolean image(Object reader,long timestamp,long observed,F frame){
        ArrayList<Runnable> a=new ArrayList<>();
        synchronized(this){
            if(ticket==null||reader!=ticket.reader||frame==null)return false;
            if(started!=0&&timestamp!=started)return false;
            Frame<F> old=held.get(timestamp);
            if(old!=null){if(old.value!=frame)a.add(()->dispose(frame));}
            else if(timestamp<=0||held.size()>=2){
                // Cannot safely classify another RAW before capture-start. Retain no more
                // camera buffers; abort the attempt, never continue into the saver.
                a.add(()->dispose(frame));fail(a,"ambiguous_raw_overflow_reopen_camera");
            }else held.put(timestamp,new Frame<>(frame,observed));
            reconcile(a);
        }run(a);return true;
    }
    public void cancel(Ticket t,String reason,boolean noImageWillArrive){
        ArrayList<Runnable> a=new ArrayList<>();
        synchronized(this){
            if(t!=ticket)return;
            fail(a,reason);
            if(noImageWillArrive && (started!=0 || held.isEmpty())){
                // A frame already delivered for the cancelled request is not a photograph,
                // even when a contradictory failure callback says no image was captured.
                Ticket owner=ticket;
                for(Map.Entry<Long,Frame<F>> e:held.entrySet()){
                    F f=e.getValue().value;
                    if(e.getKey()==started)a.add(()->dispose(f));
                    else a.add(()->events.forward(owner.reader,f));
                }
                held.clear();clear();
            }else reconcile(a);
        }run(a);
    }
    /** Session retirement closes every lease still owned by this gate exactly once. */
    public void close(){
        ArrayList<Runnable> a=new ArrayList<>();
        synchronized(this){
            if(ticket!=null)fail(a,"camera_session_closed");
            for(Frame<F> f:held.values())a.add(()->dispose(f.value));
            held.clear();clear();
        }run(a);
    }
    private void reconcile(ArrayList<Runnable>a){
        if(ticket==null||started==0)return;
        Ticket t=ticket;
        for(Map.Entry<Long,Frame<F>> e:new ArrayList<>(held.entrySet()))if(e.getKey()!=started){
            F f=e.getValue().value;held.remove(e.getKey());a.add(()->events.forward(t.reader,f));
        }
        if(result!=null&&resultTs!=started)fail(a,"image_result_timestamp_mismatch");
        Frame<F> f=held.get(started);
        if(f==null)return;
        if(cancelled){held.remove(started);a.add(()->dispose(f.value));clear();return;}
        if(result==null)return;
        long ts=started;R r=result;held.remove(ts);clear();
        a.add(()->events.matched(t,ts,f.observed,f.value,r));
    }
    private void fail(ArrayList<Runnable>a,String reason){
        cancelled=true;if(!reported){reported=true;Ticket t=ticket;a.add(()->events.failure(t,reason));}
    }
    private void forwardHeld(ArrayList<Runnable>a){
        Ticket t=ticket;for(Frame<F> f:held.values())a.add(()->events.forward(t.reader,f.value));held.clear();
    }
    private void clear(){ticket=null;started=resultTs=0;result=null;cancelled=reported=false;}
    private static void run(ArrayList<Runnable>a){for(Runnable r:a)r.run();}
    private static void dispose(AutoCloseable f){try{f.close();}catch(Exception ignored){}}
}
