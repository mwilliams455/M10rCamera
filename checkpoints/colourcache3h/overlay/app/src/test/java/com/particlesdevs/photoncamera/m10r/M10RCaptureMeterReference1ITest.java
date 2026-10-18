package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.*;
import android.media.ImageReader;
import android.os.Handler;
import android.util.Range;
import android.util.SizeF;
import com.particlesdevs.photoncamera.api.*;
import com.particlesdevs.photoncamera.app.PhotonCamera;
import com.particlesdevs.photoncamera.capture.CaptureController;
import com.particlesdevs.photoncamera.manual.ParamController;
import java.lang.reflect.*;
import java.util.*;
import org.junit.*;
import org.mockito.MockedStatic;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/** Real controller admission/completion, with hardware/native work replaced by test fixtures. */
public class M10RCaptureMeterReference1ITest {
    static final Map<Field,Object> originals=new LinkedHashMap<>();
    static Object unsafe;static Class<?> unsafeClass;
    @BeforeClass public static void keys() throws Exception {
        unsafeClass=Class.forName("sun.misc.Unsafe");Field f=unsafeClass.getDeclaredField("theUnsafe");f.setAccessible(true);unsafe=f.get(null);
        for(Class<?> owner:new Class<?>[]{CaptureResult.class,CaptureRequest.class,CameraCharacteristics.class})
            for(Field key:owner.getFields())if(Modifier.isStatic(key.getModifiers())&&key.getType().getSimpleName().equals("Key")){
                originals.put(key,key.get(null));put(key,mock(key.getType()));
            }
    }
    static void put(Field f,Object value) throws Exception {
        Object base=unsafeClass.getMethod("staticFieldBase",Field.class).invoke(unsafe,f);
        long offset=(Long)unsafeClass.getMethod("staticFieldOffset",Field.class).invoke(unsafe,f);
        unsafeClass.getMethod("putObjectVolatile",Object.class,long.class,Object.class).invoke(unsafe,base,offset,value);
    }
    @AfterClass public static void restoreKeys() throws Exception { for(var e:originals.entrySet())put(e.getKey(),e.getValue()); }
    @After public void clear() { M10RPreviewState1A.clear(null);CaptureController.isProcessing=false; }
    static class Fixture implements AutoCloseable {
        final MockedStatic<PhotonCamera> app=mockStatic(PhotonCamera.class);
        final MockedStatic<com.particlesdevs.photoncamera.settings.PreferenceKeys> prefs=mockStatic(com.particlesdevs.photoncamera.settings.PreferenceKeys.class);
        final boolean historical;
        final MockedStatic<VendorTagUtils> vendor=mockStatic(VendorTagUtils.class);
        final CaptureController controller=mock(CaptureController.class,CALLS_REAL_METHODS);
        final CameraCharacteristics chars=mock(CameraCharacteristics.class),oldChars=CaptureController.mCameraCharacteristics;
        final CameraDevice device=mock(CameraDevice.class);
        final CameraCaptureSession session=mock(CameraCaptureSession.class);
        final ImageReader reader=mock(ImageReader.class);
        final CaptureRequest.Builder preview=mock(CaptureRequest.Builder.class),meter=mock(CaptureRequest.Builder.class);
        final CaptureRequest request=mock(CaptureRequest.class);
        final CaptureResult result=mock(CaptureResult.class);
        final M10RExposureCamera1C exposure=mock(M10RExposureCamera1C.class);
        final CameraEventsListener events=mock(CameraEventsListener.class);
        final M10RCaptureLifecycle1G gate=new M10RCaptureLifecycle1G();
        M10RExposureCamera1C.Input admitted;
        final String controls;
        Fixture(int ev) throws Exception {this(ev,false);}
        Fixture(int ev,int mode) throws Exception {this(ev,false,mode);}
        Fixture(int ev,boolean historical) throws Exception {this(ev,historical,1);}
        Fixture(int ev,boolean historical,int mode) throws Exception {
            this.historical=historical;
            prefs.when(com.particlesdevs.photoncamera.settings.PreferenceKeys::getAeMeteringStd).thenReturn(mode);
            set("m10rSpot1U",new double[]{.5,.5});
            android.graphics.Rect active=mock(android.graphics.Rect.class);
            active.right=4096;active.bottom=3072;
            when(active.width()).thenReturn(4096);when(active.height()).thenReturn(3072);
            when(chars.get(CameraCharacteristics.SENSOR_INFO_ACTIVE_ARRAY_SIZE)).thenReturn(active);
            android.util.Size pixels=mock(android.util.Size.class);
            when(pixels.getWidth()).thenReturn(4096);when(pixels.getHeight()).thenReturn(3072);
            when(chars.get(CameraCharacteristics.SENSOR_INFO_PIXEL_ARRAY_SIZE)).thenReturn(pixels);
            Settings settings=mock(Settings.class);settings.selectedMode=CameraMode.PHOTO;settings.mCameraID="2";
            app.when(PhotonCamera::getSettings).thenReturn(settings);CaptureController.mCameraCharacteristics=chars;
            when(device.getId()).thenReturn("2");when(device.createCaptureRequest(CameraDevice.TEMPLATE_STILL_CAPTURE)).thenReturn(meter);
            when(device.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW)).thenReturn(meter);
            when(reader.getWidth()).thenReturn(4096);when(reader.getHeight()).thenReturn(3072);
            when(chars.get(CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT)).thenReturn(0);
            var unit=mock(android.util.Rational.class);when(unit.doubleValue()).thenReturn(1.0/3);
            when(chars.get(CameraCharacteristics.CONTROL_AE_COMPENSATION_STEP)).thenReturn(unit);
            when(preview.get(CaptureRequest.CONTROL_AE_MODE)).thenReturn(CaptureRequest.CONTROL_AE_MODE_ON);
            when(preview.get(CaptureRequest.CONTROL_AE_EXPOSURE_COMPENSATION)).thenReturn(ev);
            when(preview.get(CaptureRequest.FLASH_MODE)).thenReturn(CaptureRequest.FLASH_MODE_OFF);
            when(request.get(CaptureRequest.CONTROL_AE_MODE)).thenReturn(CaptureRequest.CONTROL_AE_MODE_ON);
            when(request.get(CaptureRequest.CONTROL_AE_EXPOSURE_COMPENSATION)).thenReturn(ev);
            when(request.get(CaptureRequest.FLASH_MODE)).thenReturn(CaptureRequest.FLASH_MODE_OFF);
            when(preview.build()).thenReturn(request);when(request.getKeys()).thenReturn(Collections.emptyList());
            when(result.get(CaptureResult.SENSOR_TIMESTAMP)).thenReturn(123L);
            when(result.get(CaptureResult.SENSOR_EXPOSURE_TIME)).thenReturn(40_000_000L);
            when(result.get(CaptureResult.SENSOR_SENSITIVITY)).thenReturn(125);
            when(result.get(CaptureResult.LENS_APERTURE)).thenReturn(1.8f);
            when(result.get(CaptureResult.LENS_FOCAL_LENGTH)).thenReturn(8.8f);
            SizeF size=mock(SizeF.class);when(size.getWidth()).thenReturn(13.2f);when(chars.get(CameraCharacteristics.SENSOR_INFO_PHYSICAL_SIZE)).thenReturn(size);
            Range<Long> times=mock(Range.class);when(times.getLower()).thenReturn(1000L);when(times.getUpper()).thenReturn(1_000_000_000L);
            Range<Integer> isos=mock(Range.class);when(isos.getLower()).thenReturn(50);when(isos.getUpper()).thenReturn(12800);
            when(chars.get(CameraCharacteristics.SENSOR_INFO_EXPOSURE_TIME_RANGE)).thenReturn(times);
            when(chars.get(CameraCharacteristics.SENSOR_INFO_SENSITIVITY_RANGE)).thenReturn(isos);
            set("mCameraDevice",device);set("mCaptureSession",session);set("mImageReaderRaw",reader);
            set("mPreviewRequestBuilder",preview);set("mBackgroundHandler",mock(Handler.class));
            set("paramController",mock(ParamController.class));set("physicalID","2");set("logicalID","2");
            set("cameraEventsListener",events);set("m10rShot1G",gate);set("m10rExposure1C",exposure);set("isCameraResumed",true);
            doNothing().when(controller).applyZoom(any(CaptureRequest.Builder.class),anyBoolean());
            doNothing().when(controller).unlockFocus();doReturn(false).when(controller).isVideoMode();
            when(exposure.start(any())).thenAnswer(i->{admitted=i.getArgument(0);return true;});
            controls=(String)call("m10rControls1C",new Class<?>[0]);
            var o=M10RPreviewMetadata1E.observe(session,"2:4096x3072:0",controls,chars,result,request,System.nanoTime(),ev/3.0,
                    M10RPreviewMetadata1E.requestMatchesCurrentControls(request,preview));
            M10RPreviewState1A.observe(o);gate.begin();
        }
        void set(String name,Object value)throws Exception{M10RCaptureAdmission1GTest.field(controller,name,value);}
        Object call(String name,Class<?>[] types,Object...args)throws Exception{
            Method m=CaptureController.class.getDeclaredMethod(name,types);m.setAccessible(true);return m.invoke(controller,args);
        }
        void start(boolean background)throws Exception{
            call("m10rStartProbe1A",new Class<?>[]{boolean.class},background);
            if(historical&&admitted!=null){
                // Explicit old-policy replay. New production admission is verified separately.
                var a=admitted;
                admitted=new M10RExposureCamera1C.Input(a.session,a.reader,a.characteristics,a.builder,a.handler,a.cameraKey,
                        a.physicalId,a.deviceId,a.device,a.previewBuilder,a.controlsKey,a.id,a.referenceUserEv,a.userEv,a.requestEvMeterSeed);
                set("m10rPendingInput1C",admitted);if(background)set("m10rBackgroundInput1A",admitted);
            }
        }
        void finish(M10RExposureProbe1B.Output output)throws Exception{call("m10rFinishProbe1C",new Class<?>[]{M10RExposureCamera1C.Input.class,M10RExposureProbe1B.Output.class,String.class},admitted,output,"test_probe");}
        public void close(){CaptureController.mCameraCharacteristics=oldChars;vendor.close();app.close();prefs.close();M10RPreviewState1A.clear(null);}
    }
    @Test public void foregroundMeterStartsWithFreshSensorValuesDespiteMissingResultEv() throws Exception {
        try(Fixture f=new Fixture(0)) {
            f.start(false);assertNotNull(f.admitted);assertTrue(f.admitted.requestEvMeterSeed);
            verify(f.meter).set(CaptureRequest.SENSOR_EXPOSURE_TIME,40_000_000L);
            verify(f.meter).set(CaptureRequest.SENSOR_SENSITIVITY,125);
            verify(f.meter).set(CaptureRequest.CONTROL_AE_MODE,CaptureRequest.CONTROL_AE_MODE_OFF);
            verifyNoInteractions(f.events);assertTrue(f.gate.preparing());
        }
    }
    @Test public void nonzeroEvIsBoundOnceFromMatchedSubmittedRequest() throws Exception {
        try(Fixture f=new Fixture(-3)) {
            f.start(false);assertNotNull(f.admitted);
            assertEquals(-1,f.admitted.referenceUserEv,1e-12);assertEquals(-1,f.admitted.userEv,1e-12);
            assertTrue(f.admitted.requestEvMeterSeed);verifyNoInteractions(f.events);
        }
    }
    @Test public void requestSeedAloneCannotFallBackToAnUnmeasuredPhotograph() throws Exception {
        try(Fixture f=new Fixture(0)) {
            f.start(false);assertNotNull(f.admitted);f.finish(null);
            assertFalse(f.gate.busy());verify(f.events).onProcessingError(contains("no fresh safe exposure selection"));
            verify(f.device,times(1)).createCaptureRequest(anyInt());
        }
    }
    @Test public void completedRawProbeCanPublishPlanWhilePreviewStillOmitsEvEcho() throws Exception {
        for(int steps:new int[]{0,-3,3})try(Fixture f=new Fixture(steps)) {
            f.start(true);assertNotNull(f.admitted);long now=System.nanoTime();
            double[] grid=new double[352];Arrays.fill(grid,.12);
            var positive=M10RExposureRange1HTest.stats(7);var baseline=M10RExposureRange1HTest.stats(3);
            var probe=new M10RExposure1A.Probe(f.admitted.cameraKey,f.admitted.id,1,M10RExposureRenderer1M.expectedRevision(com.particlesdevs.photoncamera.BuildConfig.M10R_METER_RENDERER1M,
                com.particlesdevs.photoncamera.BuildConfig.M10R_RENDERED_COLOR1A,com.particlesdevs.photoncamera.BuildConfig.M10R_COLOR_ORDER1A),
                    123,123,now,now,40_000_000L,125,steps/3.0,0,M10RExposure1A.ProbeDomain.M10R_RENDERED_USER_EV_REFERENCE,
                    grid,positive,M10RHighlightGuard1A.noSubject(7),steps/3.0,baseline,
                    M10RMetering1U.measure(M10RLiveView1UTest.flat(.12),4096,3072,f.admitted.metering));
            var prepared=mock(M10RExposureRaw1B.Prepared.class);
            when(prepared.atWhiteByCfaPhase()).thenReturn(new long[4]);when(prepared.aboveWhiteByCfaPhase()).thenReturn(new long[4]);
            when(prepared.nearWhiteByCfaPhase()).thenReturn(new long[4]);
            var output=new M10RExposureProbe1B.Output(probe,new short[3],new int[7][],prepared,1,1,positive,baseline);
            f.finish(output);var plan=M10RPreviewState1A.plan();assertNotNull(plan);assertTrue(plan.selection.apply);
            assertEquals(steps/3.0,plan.selection.plan.totalIntentEv,1e-12);
            assertEquals(0,plan.selection.plan.deltaFromReferenceEv,1e-12);
            var report=new org.json.JSONObject(plan.report.json);
            assertEquals("matched_request_EV",report.getString("meterReferenceEvSource"));
            assertTrue(report.getBoolean("requestEvSeedRequiresRawOrReportedReference"));verifyNoInteractions(f.events);
            assertEquals(0,M10RPreviewState1A.display().planId);
        }
    }
    @Test public void freshReportedFallbackSurvivesNewerRequestOnlyPreviewFrames() throws Exception {
        try(Fixture f=new Fixture(0);var selection=mockStatic(M10RExposureCapture1B.class,CALLS_REAL_METHODS)) {
            CaptureResult reported=mock(CaptureResult.class);
            when(reported.get(CaptureResult.SENSOR_TIMESTAMP)).thenReturn(122L);
            when(reported.get(CaptureResult.SENSOR_EXPOSURE_TIME)).thenReturn(30_000_000L);
            when(reported.get(CaptureResult.SENSOR_SENSITIVITY)).thenReturn(200);
            long observed=System.nanoTime()-100_000_000L;
            var complete=new M10RPreviewState1A.Observation(f.session,"2:4096x3072:0",f.controls,f.chars,reported,observed,0,0,true);
            M10RPreviewState1A.observe(complete);f.start(true);assertTrue(f.admitted.requestEvMeterSeed);f.finish(null);
            selection.verify(()->M10RExposureCapture1B.select(isNull(),any(),argThat(ref->ref!=null
                    &&ref.observedNs==observed&&ref.exposureNs==30_000_000L&&ref.iso==200),any()));
            verifyNoInteractions(f.events);
        }
    }
}
