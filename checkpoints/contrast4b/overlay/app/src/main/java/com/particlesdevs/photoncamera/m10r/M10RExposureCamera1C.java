package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.*;
import android.media.Image;
import android.media.ImageReader;
import android.os.Build;
import android.os.Handler;
import java.util.concurrent.*;

/** One unsaved request-tagged RAW measurement before a single photographic RAW.
 * No HDR, no saved-probe frame and no asynchronous change to an already frozen shot.
 */
public final class M10RExposureCamera1C {
    public static final String REVISION="M10R_EXPOSURE1C_REQUEST_OWNED_RAW_HIGHLIGHTS";
    public interface Host {
        boolean current(Input in);
        void forward(ImageReader reader,Image image);
        void ready(Input in,M10RExposureProbe1B.Output output,String reason);
        void failed(Input in,String reason);
    }
    public static final class Input {
        public final CameraCaptureSession session;public final ImageReader reader;
        public final CameraCharacteristics characteristics;public final CaptureRequest.Builder builder;
        public final Handler handler;public final String cameraKey,physicalId,deviceId,controlsKey;
        public final Object device,previewBuilder;
        public final long id; public final double referenceUserEv,userEv;
        public final boolean requestEvMeterSeed;
        public final M10RMetering1U.Config metering;
        public final M10RContrast4B.Level contrast4B;
        public final long previewGeneration4B;
        public final M10RExposureTrace1D trace = new M10RExposureTrace1D();
        public Input(CameraCaptureSession session,ImageReader reader,CameraCharacteristics c,
                CaptureRequest.Builder b,Handler handler,String key,String physical,String deviceId,
                Object device,Object previewBuilder,String controls,long id,double referenceUserEv,double userEv){
            this(session,reader,c,b,handler,key,physical,deviceId,device,previewBuilder,controls,id,referenceUserEv,userEv,false);
        }
        public Input(CameraCaptureSession session,ImageReader reader,CameraCharacteristics c,
                CaptureRequest.Builder b,Handler handler,String key,String physical,String deviceId,
                Object device,Object previewBuilder,String controls,long id,double referenceUserEv,double userEv,
                boolean requestEvMeterSeed){
            this(session,reader,c,b,handler,key,physical,deviceId,device,previewBuilder,controls,id,referenceUserEv,userEv,requestEvMeterSeed,null);
        }
        public Input(CameraCaptureSession session,ImageReader reader,CameraCharacteristics c,
                CaptureRequest.Builder b,Handler handler,String key,String physical,String deviceId,
                Object device,Object previewBuilder,String controls,long id,double referenceUserEv,double userEv,
                boolean requestEvMeterSeed,M10RMetering1U.Config metering){
            this(session,reader,c,b,handler,key,physical,deviceId,device,previewBuilder,controls,id,
                    referenceUserEv,userEv,requestEvMeterSeed,metering,M10RContrast4B.Level.STANDARD);
        }
        public Input(CameraCaptureSession session,ImageReader reader,CameraCharacteristics c,
                CaptureRequest.Builder b,Handler handler,String key,String physical,String deviceId,
                Object device,Object previewBuilder,String controls,long id,double referenceUserEv,double userEv,
                boolean requestEvMeterSeed,M10RMetering1U.Config metering,M10RContrast4B.Level contrast){
            this.metering=metering;
            contrast4B=M10RContrast4B.normalized(contrast);
            previewGeneration4B=M10RPreviewState1A.currentGeneration4B();
            this.session=session;this.reader=reader;characteristics=c;builder=b;this.handler=handler;
            cameraKey=key;physicalId=physical;this.deviceId=deviceId;this.device=device;
            this.previewBuilder=previewBuilder;controlsKey=controls;this.id=id;
            this.referenceUserEv=referenceUserEv;this.userEv=userEv;
            this.requestEvMeterSeed=requestEvMeterSeed;
        }
    }
    interface Work {
        M10RExposureProbe1B.Output run(Input in,long ts,long observed,Image frame,CaptureResult result) throws Exception;
    }
    private final Host host;
    private final Work testWork;
    private final ThreadPoolExecutor worker=new ThreadPoolExecutor(0,1,30,TimeUnit.SECONDS,
            new SynchronousQueue<>(),r->{Thread t=new Thread(r,"M10RExposureProbe");t.setDaemon(true);return t;});
    private final M10RExposureGate1C<Image,CaptureResult> gate;
    private volatile Input active;
    private volatile M10RExposureGate1C.Ticket ticket;
    private volatile boolean cancelled;
    public M10RExposureCamera1C(Host host){this(host,null);}
    M10RExposureCamera1C(Host host,Work testWork){
        if(host==null)throw new IllegalArgumentException("host required");
        this.host=host;this.testWork=testWork;
        gate=new M10RExposureGate1C<>(new M10RExposureGate1C.Events<Image,CaptureResult>(){
            public void forward(Object r,Image f){host.forward((ImageReader)r,f);}
            public void failure(M10RExposureGate1C.Ticket t,String why){
                Input in=active;if(in==null||ticket!=t)return;
                cancelled=true;active=null;in.handler.post(()->host.failed(in,why));
            }
            public void matched(M10RExposureGate1C.Ticket t,long timestamp,long observed,Image frame,CaptureResult result){
                Input in=active;
                if(in==null||ticket!=t||cancelled){frame.close();return;}
                try{worker.execute(()->process(in,t,timestamp,observed,frame,result));}
                catch(RejectedExecutionException e){frame.close();finish(in,null,"probe_worker_busy");}
            }
        });
    }
    public boolean busy(){return active!=null||gate.busy();}
    public boolean offer(ImageReader reader,Image image){return gate.image(reader,image.getTimestamp(),System.nanoTime(),image);}
    public synchronized boolean start(Input in){
        if(in==null||busy()||!host.current(in))return false;
        M10RExposureGate1C.Ticket t=gate.begin(in.reader);if(t==null)return false;
        active=in;ticket=t;cancelled=false;
        try{
            in.builder.setTag(t);
            CaptureRequest request=in.builder.build();
            in.session.capture(request,new CameraCaptureSession.CaptureCallback(){
                private boolean ours(CameraCaptureSession s,CaptureRequest r){return s==in.session&&r.getTag()==t;}
                @Override public void onCaptureStarted(CameraCaptureSession s,CaptureRequest r,long ts,long fn){
                    if(ours(s,r))gate.started(t,ts);
                }
                @Override public void onCaptureCompleted(CameraCaptureSession s,CaptureRequest r,TotalCaptureResult total){
                    if(!ours(s,r))return;
                    try{
                        CaptureResult result=physical(total,in.physicalId,in.deviceId);
                        Long ts=result.get(CaptureResult.SENSOR_TIMESTAMP);
                        if(ts==null)throw new IllegalArgumentException("missing_sensor_timestamp");
                        gate.result(t,ts,result);
                    }catch(Exception e){diagnose(in,"raw_association",e);gate.cancel(t,"probe_metadata_rejected",false);}
                }
                @Override public void onCaptureFailed(CameraCaptureSession s,CaptureRequest r,CaptureFailure f){
                    if(ours(s,r))gate.cancel(t,"meter_capture_failed",!f.wasImageCaptured());
                }
                @Override public void onCaptureBufferLost(CameraCaptureSession s,CaptureRequest r,android.view.Surface target,long fn){
                    if(ours(s,r)&&target==in.reader.getSurface())gate.cancel(t,"meter_raw_buffer_lost",true);
                }
                @Override public void onCaptureSequenceAborted(CameraCaptureSession s,int sequenceId){
                    if(s==in.session)gate.cancel(t,"meter_sequence_aborted",false);
                }
            },in.handler);
            in.handler.postDelayed(()->{
                if(active==in&&gate.owns(t))gate.cancel(t,"meter_acquisition_timeout_reopen_if_not_drained",false);
            },1800L);
            return true;
        }catch(Exception e){diagnose(in,"request_submission",e);gate.cancel(t,"meter_request_rejected",true);return true;}
    }
    public static CaptureResult physical(TotalCaptureResult total,String physicalId,String deviceId){
        return physicalAtApi(total,physicalId,deviceId,Build.VERSION.SDK_INT);
    }
    static CaptureResult physicalAtApi(TotalCaptureResult total,String physicalId,String deviceId,int api){
        if(total==null||physicalId==null||deviceId==null)throw new IllegalArgumentException("source identity required");
        if(api>=28){
            CaptureResult p=total.getPhysicalCameraResults().get(physicalId);
            if(p!=null)return p;
            String active=total.get(CaptureResult.LOGICAL_MULTI_CAMERA_ACTIVE_PHYSICAL_ID);
            if(active!=null&&!active.equals(physicalId))throw new IllegalArgumentException("wrong physical source");
            if(active==null&&!deviceId.equals(physicalId))
                throw new IllegalArgumentException("logical source identity unproven");
        }else if(!deviceId.equals(physicalId))throw new IllegalArgumentException("physical source unavailable");
        return total;
    }
    private void process(Input in,M10RExposureGate1C.Ticket t,long ts,long observed,Image frame,CaptureResult result){
        M10RExposureProbe1B.Output output=null;String reason="ready";
        in.trace.observed(observed);
        in.trace.step("raw_copy");
        try{
            if(testWork!=null){
                // Test transport only: normal constructor always uses the actual RAW/native path.
                output=testWork.run(in,ts,observed,frame,result);
                in.trace.complete();finish(in,output,"ready");return;
            }
            M10RExposureAndroid1C.Owned copy=M10RExposureAndroid1C.copyAndClose(frame,ts);
            if(active!=in||cancelled)throw new IllegalStateException("probe_cancelled");
            in.trace.step("exposure_metadata");
            Long ns=result.get(CaptureResult.SENSOR_EXPOSURE_TIME);Integer iso=result.get(CaptureResult.SENSOR_SENSITIVITY);
            if(ns==null||iso==null)throw new IllegalArgumentException("exact exposure metadata unavailable");
            M10RExposureProbe1B.Binding b=new M10RExposureProbe1B.Binding(in.cameraKey,in.id,t.id,ts,observed,
                    ns,iso,in.referenceUserEv,0,in.userEv,in.metering,in.contrast4B);
            output=M10RExposureAndroid1C.build(copy,in.characteristics,result,b,System::nanoTime,
                    ()->active!=in||cancelled,in.trace);
        }catch(Exception|LinkageError|OutOfMemoryError e){
            reason="probe_unavailable_"+e.getClass().getSimpleName();diagnose(in,null,e);
        }
        in.trace.complete();
        finish(in,output,reason);
    }
    private static void diagnose(Input in,String stage,Throwable error){
        if(stage!=null)in.trace.step(stage);
        in.trace.failure(error);
        try{android.util.Log.e("M10RExposure","Probe request="+in.id+" source="+in.cameraKey
                +" stage="+in.trace.stage(),error);}
        catch(RuntimeException|LinkageError|OutOfMemoryError ignored){}
    }
    private void finish(Input in,M10RExposureProbe1B.Output output,String reason){
        boolean posted=in.handler.post(()->{
            synchronized(this){if(active!=in||cancelled)return;active=null;ticket=null;}
            if(host.current(in))host.ready(in,output,reason);else host.failed(in,"controls_or_camera_changed");
        });
        if(!posted)synchronized(this){if(active==in){active=null;ticket=null;cancelled=true;}}
    }
    /** Called before old session/reader destruction; running work sees cancellation. */
    public synchronized void close(){cancelled=true;gate.close();active=null;ticket=null;}
}
