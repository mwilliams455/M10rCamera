package com.particlesdevs.photoncamera.m10r;
import org.junit.Test;
import static org.junit.Assert.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
public class M10RExposureGate1CTest {
    static class F implements AutoCloseable {AtomicInteger closes=new AtomicInteger();public void close(){assertEquals(1,closes.incrementAndGet());}}
    static class Env implements M10RExposureGate1C.Events<F,String>{
        Object reader=new Object();int matched,failed;List<F> forwarded=new ArrayList<>();F result;
        M10RExposureGate1C<F,String> gate=new M10RExposureGate1C<>(this);
        public void forward(Object r,F f){assertSame(reader,r);forwarded.add(f);}
        public void failure(M10RExposureGate1C.Ticket t,String s){failed++;}
        public void matched(M10RExposureGate1C.Ticket t,long ts,long obs,F f,String s){
            assertEquals(100,ts);assertEquals(99,obs);assertEquals("result",s);result=f;matched++;
        }
    }
    @Test public void everyArrivalOrderTransfersExactlyOneFrame(){
        int[][] orders={{0,1,2},{0,2,1},{1,0,2},{1,2,0},{2,0,1},{2,1,0}};
        for(int[] order:orders){Env e=new Env();F f=new F();var t=e.gate.begin(e.reader);
            for(int event:order){if(event==0)e.gate.started(t,100);if(event==1)e.gate.result(t,100,"result");if(event==2)assertTrue(e.gate.image(e.reader,100,99,f));}
            assertEquals(1,e.matched);assertEquals(0,e.failed);assertEquals(0,f.closes.get());assertSame(f,e.result);assertFalse(e.gate.busy());
            e.gate.close();assertEquals(0,f.closes.get());f.close();
        }
    }
    @Test public void unrelatedSourceAndTimestampRemainPhotographic(){
        Env e=new Env();var t=e.gate.begin(e.reader);F alien=new F();
        assertFalse(e.gate.image(new Object(),100,99,alien));assertEquals(0,alien.closes.get());
        F early=new F();assertTrue(e.gate.image(e.reader,90,89,early));e.gate.started(t,100);
        assertEquals(List.of(early),e.forwarded);assertEquals(0,early.closes.get());
        F late=new F();assertFalse(e.gate.image(e.reader,101,102,late));assertEquals(0,late.closes.get());
        e.gate.close();alien.close();early.close();late.close();
    }
    @Test public void timeoutDoesNotConvertLateMeterIntoPhotograph(){
        for(boolean beforeStart:new boolean[]{false,true}){
            Env e=new Env();var t=e.gate.begin(e.reader);F f=new F();
            if(!beforeStart)e.gate.started(t,100);
            e.gate.cancel(t,"timeout",false);assertTrue(e.gate.busy());assertNull(e.gate.begin(e.reader));
            assertTrue(e.gate.image(e.reader,100,99,f));
            if(beforeStart)e.gate.started(t,100);
            e.gate.result(t,100,"result");assertEquals(1,e.failed);assertEquals(0,e.matched);assertEquals(1,f.closes.get());assertFalse(e.gate.busy());assertTrue(e.forwarded.isEmpty());
        }
    }
    @Test public void contradictingFailureCannotForwardMeterImage(){
        Env e=new Env();var t=e.gate.begin(e.reader);F f=new F();e.gate.started(t,100);e.gate.image(e.reader,100,99,f);
        e.gate.cancel(t,"not captured",true);assertEquals(1,f.closes.get());assertTrue(e.forwarded.isEmpty());assertFalse(e.gate.busy());
        e=new Env();t=e.gate.begin(e.reader);f=new F();e.gate.image(e.reader,100,99,f);e.gate.cancel(t,"unknown before start",true);
        assertTrue(e.gate.busy());assertTrue(e.forwarded.isEmpty());e.gate.started(t,100);assertEquals(1,f.closes.get());
    }
    @Test public void mismatchDuplicateAndSessionRetirement(){
        Env e=new Env();var t=e.gate.begin(e.reader);F f=new F(),duplicate=new F();
        e.gate.image(e.reader,100,99,f);e.gate.image(e.reader,100,99,f);e.gate.image(e.reader,100,99,duplicate);
        assertEquals(1,duplicate.closes.get());e.gate.started(t,100);e.gate.result(t,101,"bad");
        assertEquals(1,f.closes.get());assertEquals(1,e.failed);assertEquals(0,e.matched);
        var next=e.gate.begin(e.reader);F newFrame=new F();e.gate.image(e.reader,100,99,newFrame);
        e.gate.result(t,100,"old");assertEquals(0,e.matched);e.gate.close();e.gate.close();assertEquals(1,newFrame.closes.get());
    }
    @Test public void overflowIsBoundedAndCannotReachSaver(){
        Env e=new Env();var t=e.gate.begin(e.reader);F a=new F(),b=new F(),c=new F();
        e.gate.image(e.reader,98,97,a);e.gate.image(e.reader,99,98,b);e.gate.image(e.reader,100,99,c);
        assertEquals(1,c.closes.get());assertEquals(1,e.failed);assertTrue(e.gate.busy());
        e.gate.close();assertEquals(1,a.closes.get());assertEquals(1,b.closes.get());assertTrue(e.forwarded.isEmpty());
    }
    @Test public void concurrentStartResultImageAndCloseDoNotDoubleOwn()throws Exception{
        ExecutorService pool=Executors.newFixedThreadPool(4);
        try{for(int n=0;n<200;n++){
            Env e=new Env();var t=e.gate.begin(e.reader);F f=new F();CountDownLatch start=new CountDownLatch(1);
            Future<?> a=pool.submit(()->{await(start);e.gate.started(t,100);});
            Future<?> b=pool.submit(()->{await(start);e.gate.result(t,100,"result");});
            Future<?> c=pool.submit(()->{await(start);if(!e.gate.image(e.reader,100,99,f))f.close();});
            Future<?> d=pool.submit(()->{await(start);e.gate.close();});start.countDown();a.get();b.get();c.get();d.get();
            assertTrue(e.matched<=1);if(e.matched==1){assertEquals(0,f.closes.get());f.close();}else assertEquals(1,f.closes.get());
        }}finally{pool.shutdownNow();}
    }
    static void await(CountDownLatch c){try{c.await();}catch(InterruptedException e){throw new AssertionError(e);}}
}
