package com.particlesdevs.photoncamera.m10r;
import android.hardware.camera2.*;
import android.media.*;
import android.os.Handler;
import android.view.Surface;
import org.junit.Test;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
public class M10RExposureCamera1CTest {
    static class E implements M10RExposureCamera1C.Host {
        CameraCaptureSession session=mock(CameraCaptureSession.class);
        ImageReader reader=mock(ImageReader.class);Handler handler=mock(Handler.class);
        CameraCharacteristics chars=mock(CameraCharacteristics.class);
        CaptureRequest.Builder builder=mock(CaptureRequest.Builder.class);
        CaptureRequest request=mock(CaptureRequest.class);TotalCaptureResult result=mock(TotalCaptureResult.class);
        AtomicReference<Object> tag=new AtomicReference<>();CameraCaptureSession.CaptureCallback callback;
        M10RExposureCamera1C camera;M10RExposureCamera1C.Input input;List<Runnable> timers=new ArrayList<>();
        AtomicInteger ready=new AtomicInteger(),failed=new AtomicInteger(),worked=new AtomicInteger();
        volatile boolean valid=true;volatile String reason;CountDownLatch complete=new CountDownLatch(1);
        E()throws Exception{this(null);}
        E(M10RExposureCamera1C.Work work)throws Exception{
            when(reader.getSurface()).thenReturn(mock(Surface.class));
            doAnswer(i->{tag.set(i.getArgument(0));return null;}).when(builder).setTag(any());
            when(request.getTag()).thenAnswer(i->tag.get());when(builder.build()).thenReturn(request);
            when(handler.post(any())).thenAnswer(i->{((Runnable)i.getArgument(0)).run();return true;});
            when(handler.postDelayed(any(),anyLong())).thenAnswer(i->{timers.add(i.getArgument(0));return true;});
            when(session.capture(any(),any(),any())).thenAnswer(i->{callback=i.getArgument(1);return 9;});
            when(result.get(CaptureResult.SENSOR_TIMESTAMP)).thenReturn(100L);
            camera=new M10RExposureCamera1C(this,work!=null?work:(in,ts,observed,frame,r)->{
                assertEquals(100,ts);assertTrue(observed>0);assertSame(result,r);worked.incrementAndGet();frame.close();return null;
            });
            input=new M10RExposureCamera1C.Input(session,reader,chars,builder,handler,"camera","2","2",
                    new Object(),new Object(),"controls",1,0,0);
        }
        Image frame(){Image f=mock(Image.class);when(f.getTimestamp()).thenReturn(100L);return f;}
        public boolean current(M10RExposureCamera1C.Input i){return valid;}
        public void forward(ImageReader r,Image f){throw new AssertionError("unexpected forwarding");}
        public void ready(M10RExposureCamera1C.Input i,M10RExposureProbe1B.Output o,String why){ready.incrementAndGet();reason=why;complete.countDown();}
        public void failed(M10RExposureCamera1C.Input i,String why){failed.incrementAndGet();reason=why;complete.countDown();}
        void awaitDone()throws Exception{assertTrue(complete.await(3,TimeUnit.SECONDS));}
    }
    @Test public void actualCallbacksAllSixArrivalOrders()throws Exception{
        int[][] orders={{0,1,2},{0,2,1},{1,0,2},{1,2,0},{2,0,1},{2,1,0}};
        for(int[] order:orders){E e=new E();Image f=e.frame();assertTrue(e.camera.start(e.input));
            assertFalse(e.camera.start(e.input));
            for(int v:order){if(v==0)e.callback.onCaptureStarted(e.session,e.request,100,1);
                if(v==1)e.callback.onCaptureCompleted(e.session,e.request,e.result);
                if(v==2)assertTrue(e.camera.offer(e.reader,f));}
            e.awaitDone();assertEquals(1,e.worked.get());assertEquals(1,e.ready.get());assertEquals(0,e.failed.get());
            verify(f,times(1)).close();assertFalse(e.camera.busy());e.camera.close();
        }
    }
    @Test public void cancelledMeterDrainsWithoutWorkOrPhotograph()throws Exception{
        E e=new E();Image f=e.frame();assertTrue(e.camera.start(e.input));
        e.callback.onCaptureStarted(e.session,e.request,100,1);e.timers.get(0).run();e.awaitDone();
        assertEquals(1,e.failed.get());assertTrue(e.camera.busy());assertTrue(e.camera.offer(e.reader,f));
        e.callback.onCaptureCompleted(e.session,e.request,e.result);verify(f,times(1)).close();
        assertEquals(0,e.worked.get());assertEquals(0,e.ready.get());assertFalse(e.camera.busy());e.camera.close();
    }
    @Test public void changedControlsRejectNativeCompletion()throws Exception{
        E e=new E();Image f=e.frame();assertTrue(e.camera.start(e.input));e.valid=false;
        e.callback.onCaptureStarted(e.session,e.request,100,1);e.callback.onCaptureCompleted(e.session,e.request,e.result);
        assertTrue(e.camera.offer(e.reader,f));e.awaitDone();assertEquals(0,e.ready.get());assertEquals(1,e.failed.get());
        assertEquals("controls_or_camera_changed",e.reason);verify(f,times(1)).close();e.camera.close();
    }
    @Test public void retiredSessionCannotCompleteAnOldShot()throws Exception{
        E e=new E();Image f=e.frame();assertTrue(e.camera.start(e.input));assertTrue(e.camera.offer(e.reader,f));
        e.camera.close();e.callback.onCaptureStarted(e.session,e.request,100,1);e.callback.onCaptureCompleted(e.session,e.request,e.result);
        verify(f,times(1)).close();assertEquals(0,e.worked.get());assertEquals(0,e.ready.get());
    }
    @Test public void wrongSessionAndWrongRequestCannotBind()throws Exception{
        E e=new E();Image f=e.frame();assertTrue(e.camera.start(e.input));assertTrue(e.camera.offer(e.reader,f));
        e.callback.onCaptureStarted(mock(CameraCaptureSession.class),e.request,100,1);
        e.callback.onCaptureCompleted(e.session,mock(CaptureRequest.class),e.result);
        assertEquals(0,e.worked.get());assertTrue(e.camera.busy());e.camera.close();verify(f,times(1)).close();
    }
    @Test public void submittedRequestFailureUsesNoImagePath()throws Exception{
        E e=new E();assertTrue(e.camera.start(e.input));CaptureFailure failure=mock(CaptureFailure.class);
        when(failure.wasImageCaptured()).thenReturn(false);e.callback.onCaptureFailed(e.session,e.request,failure);
        e.awaitDone();assertEquals(1,e.failed.get());assertFalse(e.camera.busy());assertEquals(0,e.worked.get());
    }
    @Test public void failedProbeRetainsStageMessageStackAndStillCompletesFallback()throws Exception{
        E e=new E((in,ts,observed,frame,r)->{
            frame.close();in.trace.step("colour_metadata");
            throw new IllegalStateException("source scene-white solve invalid",new IllegalArgumentException("test cause"));
        });
        Image f=e.frame();assertTrue(e.camera.start(e.input));
        e.callback.onCaptureStarted(e.session,e.request,100,1);
        e.callback.onCaptureCompleted(e.session,e.request,e.result);
        assertTrue(e.camera.offer(e.reader,f));e.awaitDone();
        assertEquals(1,e.ready.get());assertEquals(0,e.failed.get());assertFalse(e.camera.busy());
        assertEquals("probe_unavailable_IllegalStateException",e.reason);verify(f,times(1)).close();
        org.json.JSONObject d=new org.json.JSONObject();assertTrue(e.input.trace.appendTo(d));
        org.json.JSONObject failure=d.getJSONObject("probeDiagnostics").getJSONObject("failure");
        assertEquals("colour_metadata",failure.getString("stage"));
        assertEquals("source scene-white solve invalid",failure.getString("message"));
        assertTrue(failure.getString("stackTrace").contains("test cause"));
        assertTrue(failure.getString("stackTrace").contains("M10RExposureCamera1CTest"));
        e.camera.close();
    }
    @Test public void physicalMetadataSelectionRejectsUnprovenLogicalIdentity(){
        TotalCaptureResult t=mock(TotalCaptureResult.class);CaptureResult p=mock(CaptureResult.class);
        when(t.getPhysicalCameraResults()).thenReturn(Map.of("2",p));assertSame(p,M10RExposureCamera1C.physicalAtApi(t,"2","0",28));
        when(t.getPhysicalCameraResults()).thenReturn(Map.of());
        when(t.get(CaptureResult.LOGICAL_MULTI_CAMERA_ACTIVE_PHYSICAL_ID)).thenReturn("2");assertSame(t,M10RExposureCamera1C.physicalAtApi(t,"2","0",28));
        when(t.get(CaptureResult.LOGICAL_MULTI_CAMERA_ACTIVE_PHYSICAL_ID)).thenReturn("3");assertThrows(IllegalArgumentException.class,()->M10RExposureCamera1C.physicalAtApi(t,"2","0",28));
        when(t.get(CaptureResult.LOGICAL_MULTI_CAMERA_ACTIVE_PHYSICAL_ID)).thenReturn(null);
        assertThrows(IllegalArgumentException.class,()->M10RExposureCamera1C.physicalAtApi(t,"2","0",28));
        assertSame(t,M10RExposureCamera1C.physicalAtApi(t,"2","2",27));
    }
}
