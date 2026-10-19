package com.particlesdevs.photoncamera.m10r;

import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.params.ColorSpaceTransform;
import android.hardware.camera2.params.RggbChannelVector;
import android.os.Build;

import com.particlesdevs.photoncamera.capture.CaptureController;
import com.particlesdevs.photoncamera.circularbarlib.console.ManualModeConsoleImpl;
import com.particlesdevs.photoncamera.circularbarlib.control.ManualParamModel;
import com.particlesdevs.photoncamera.circularbarlib.control.models.WbModel;
import com.particlesdevs.photoncamera.circularbarlib.model.KnobModel;
import com.particlesdevs.photoncamera.control.SpotWhiteBalanceHelper;
import com.particlesdevs.photoncamera.manual.ParamController;
import com.particlesdevs.photoncamera.manual.WhiteBalanceRequest3O;
import com.particlesdevs.photoncamera.processing.parameters.ColorTemperatureConverter;
import com.particlesdevs.photoncamera.util.Log;

import java.lang.reflect.Field;
import java.util.HashMap;
import java.util.Map;

import org.junit.AfterClass;
import org.junit.BeforeClass;
import org.junit.Test;
import org.mockito.MockedStatic;

import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

/** Actual observable/control path; hardware and calibration outputs are test doubles. */
public class M10RWhiteBalanceControls3OTest {
    private static int oldSdk;

    @BeforeClass public static void keys() throws Exception {
        M10RCaptureMeterReference1ITest.keys();
        oldSdk = Build.VERSION.SDK_INT;
        sdk(30);
    }

    @AfterClass public static void restore() throws Exception {
        sdk(oldSdk);
        M10RCaptureMeterReference1ITest.restoreKeys();
    }

    private static void sdk(int value) throws Exception {
        Field f = Build.VERSION.class.getField("SDK_INT");
        Object unsafe = M10RCaptureMeterReference1ITest.unsafe;
        Class<?> type = M10RCaptureMeterReference1ITest.unsafeClass;
        Object base = type.getMethod("staticFieldBase", Field.class).invoke(unsafe, f);
        long offset = (Long) type.getMethod("staticFieldOffset", Field.class).invoke(unsafe, f);
        type.getMethod("putIntVolatile", Object.class, long.class, int.class).invoke(unsafe, base, offset, value);
    }

    private static void field(Object target, String name, Object value) throws Exception {
        Field f = target.getClass().getDeclaredField(name);
        f.setAccessible(true);
        f.set(target, value);
    }

    private static final class Request {
        final CaptureRequest.Builder builder = mock(CaptureRequest.Builder.class);
        final Map<Object, Object> logical = new HashMap<>();
        final Map<Object, Object> physical = new HashMap<>();
        Request() {
            doAnswer(i -> { logical.put(i.getArgument(0), i.getArgument(1)); return null; })
                    .when(builder).set(any(), any());
            doAnswer(i -> {
                assertEquals("2", i.getArgument(2));
                physical.put(i.getArgument(0), i.getArgument(1)); return builder;
            }).when(builder).setPhysicalCameraKey(any(), any(), anyString());
            when(builder.get(any())).thenAnswer(i -> logical.get(i.getArgument(0)));
        }
        void manual(RggbChannelVector gains, ColorSpaceTransform transform) {
            for (Map<Object, Object> keys : new Map[]{logical, physical}) {
                assertEquals(CaptureRequest.CONTROL_AWB_MODE_OFF, keys.get(CaptureRequest.CONTROL_AWB_MODE));
                assertEquals(CaptureRequest.COLOR_CORRECTION_MODE_TRANSFORM_MATRIX,
                        keys.get(CaptureRequest.COLOR_CORRECTION_MODE));
                assertSame(gains, keys.get(CaptureRequest.COLOR_CORRECTION_GAINS));
                assertSame(transform, keys.get(CaptureRequest.COLOR_CORRECTION_TRANSFORM));
            }
        }
        void auto() {
            for (Map<Object, Object> keys : new Map[]{logical, physical}) {
                assertEquals(CaptureRequest.CONTROL_AWB_MODE_AUTO, keys.get(CaptureRequest.CONTROL_AWB_MODE));
                assertEquals(CaptureRequest.COLOR_CORRECTION_MODE_FAST,
                        keys.get(CaptureRequest.COLOR_CORRECTION_MODE));
            }
        }
    }

    private static final class Fixture implements AutoCloseable {
        final MockedStatic<SpotWhiteBalanceHelper> measured = mockStatic(SpotWhiteBalanceHelper.class);
        final MockedStatic<ColorTemperatureConverter> converter = mockStatic(ColorTemperatureConverter.class);
        final MockedStatic<Log> log = mockStatic(Log.class);
        final CameraCharacteristics previous = CaptureController.mCameraCharacteristics;
        final CameraCharacteristics a = mock(CameraCharacteristics.class), b = mock(CameraCharacteristics.class);
        final RggbChannelVector gains = mock(RggbChannelVector.class);
        final ColorSpaceTransform transform = mock(ColorSpaceTransform.class);
        final CaptureController controller = mock(CaptureController.class);
        final Request preview = new Request();
        final ParamController param = new ParamController(controller);
        final ManualModeConsoleImpl console = (ManualModeConsoleImpl) ManualModeConsoleImpl.newInstance();
        final ManualParamModel model = console.getManualParamModel();
        final WbModel wheel = mock(WbModel.class);
        int wheelResetNotifications;

        Fixture() throws Exception {
            CaptureController.mCameraCharacteristics = a;
            controller.mPreviewRequestBuilder = preview.builder;
            when(controller.getWhiteBalancePhysicalId3O()).thenReturn("2");
            converter.when(() -> ColorTemperatureConverter.kelvinToRggb(anyInt(), any())).thenReturn(gains);
            converter.when(() -> ColorTemperatureConverter.createColorTransform(anyInt(), any())).thenReturn(transform);
            console.addParamObserver(param);
            console.setPreserveManualWb(false);
            field(console, "wbModel", wheel);
            field(console, "selectedModel", wheel);
            // A real reset of the wheel would notify the model and clear WB.
            doAnswer(i -> { model.setCurrentWbValue(0); return null; }).when(wheel).resetModel();
            console.getKnobModel().setManualModel(wheel);
            // ViewObserver/Binding reset the still-attached primary KnobView
            // even after the console clears selectedModel on its first close.
            console.getKnobModel().addObserver((observable, changed) -> {
                KnobModel knob = (KnobModel) observable;
                if (changed == KnobModel.KnobModelFields.RESET && knob.isKnobResetCalled()) {
                    wheelResetNotifications++;
                    if (knob.getManualModel() == wheel) wheel.resetModel();
                }
            });
        }

        @Override public void close() {
            CaptureController.mCameraCharacteristics = previous;
            log.close(); converter.close(); measured.close();
        }
    }

    @Test public void sliderRepeatedCloseAndReopenRetainKelvinWithLensPreservationDisabled() throws Exception {
        try (Fixture f = new Fixture()) {
            f.model.setCurrentWbValue(3500);
            f.console.getManualModeModel().setWbText("3500K");
            f.preview.manual(f.gains, f.transform);
            f.model.setCurrentISOValue(400);
            f.console.retractAllKnobs();
            f.console.setPanelVisibility(false);
            f.param.setupPreview();
            f.console.setPanelVisibility(true);
            assertSame(f.wheel, f.console.getKnobModel().getManualModel());
            // No knob selection between reopening and the second close.
            f.console.retractAllKnobs();
            f.console.setPanelVisibility(false);
            f.console.setPanelVisibility(true);
            assertEquals(3500, f.model.getCurrentWbValue(), 0);
            assertEquals(3500, f.param.WB);
            assertFalse(f.param.isSpotWb);
            assertEquals("3500K", f.console.getManualModeModel().getWbText());
            assertEquals(ManualParamModel.ISO_AUTO, f.model.getCurrentISOValue(), 0);
            f.preview.manual(f.gains, f.transform);
            assertEquals(0, f.wheelResetNotifications);
            verify(f.wheel, never()).resetModel();
        }
    }

    @Test public void explicitAutoAndResetStillReleaseLogicalAndPhysicalManualWb() throws Exception {
        try (Fixture f = new Fixture()) {
            f.model.setCurrentWbValue(3500);
            f.model.setCurrentWbValue(ManualParamModel.WB_AUTO);
            f.preview.auto(); assertEquals(0, f.param.WB);
            f.model.setCurrentWbValue(7000);
            f.console.resetAllValues();
            f.preview.auto(); assertEquals(0, f.param.WB);
            assertEquals(0, f.model.getCurrentWbValue(), 0);
        }
    }

    @Test public void measuredEchoAndPanelCloseKeepExactGainsTintAndKelvin() throws Exception {
        try (Fixture f = new Fixture()) {
            f.param.setSpotWB(3524, "G+1.2", f.gains, f.transform);
            f.model.setCurrentWbValue(3500); // The helper's rounded knob echo.
            f.console.retractAllKnobs();
            f.console.setPanelVisibility(false);
            f.param.setupPreview();
            assertEquals(3524, f.param.WB);
            assertTrue(f.param.isSpotWb);
            assertEquals("G+1.2", f.param.spotTintStr);
            assertSame(f.gains, f.param.spotGains);
            f.preview.manual(f.gains, f.transform);
            f.measured.verifyNoInteractions();
            f.model.setCurrentWbValue(4000);
            assertFalse(f.param.isSpotWb);
            assertNull(f.param.spotGains);
            f.measured.verify(SpotWhiteBalanceHelper::cancelPendingMeasurement);
        }
    }

    @Test public void completedRemeasureReplacesWhiteWhenBothMeasurementsEchoSameKnobKelvin() throws Exception {
        try (Fixture f = new Fixture()) {
            RggbChannelVector gainsA = mock(RggbChannelVector.class);
            RggbChannelVector gainsB = mock(RggbChannelVector.class);
            ColorSpaceTransform transformA = mock(ColorSpaceTransform.class);
            ColorSpaceTransform transformB = mock(ColorSpaceTransform.class);
            when(gainsA.getRed()).thenReturn(2.75f);
            when(gainsA.getGreenEven()).thenReturn(1.0f);
            when(gainsA.getGreenOdd()).thenReturn(1.0f);
            when(gainsA.getBlue()).thenReturn(2.125f);
            when(gainsB.getRed()).thenReturn(1.875f);
            when(gainsB.getGreenEven()).thenReturn(1.0f);
            when(gainsB.getGreenOdd()).thenReturn(1.0f);
            when(gainsB.getBlue()).thenReturn(3.5f);
            when(f.wheel.getKnobInfoList()).thenReturn(java.util.Collections.emptyList());

            f.param.setSpotWB(3524, "G+1.2", gainsA, transformA);
            f.console.setManualWbValue(3500);
            WhiteBalanceRequest3O first = f.param.snapshotWhiteBalance3O(f.a);
            assertEquals(3524, first.kelvin);
            assertTrue(first.measured);
            f.preview.manual(gainsA, transformA);

            // The second completed measurement has the same rounded knob echo,
            // but its exact Kelvin, tint, gains and transform must replace A.
            f.param.setSpotWB(3481, "M+0.8", gainsB, transformB);
            f.console.setManualWbValue(3500);
            f.console.retractAllKnobs();
            f.console.setPanelVisibility(false);
            f.param.setupPreview();
            WhiteBalanceRequest3O second = f.param.snapshotWhiteBalance3O(f.a);

            assertEquals(3500, f.model.getCurrentWbValue(), 0);
            assertEquals(3481, f.param.WB);
            assertTrue(f.param.isSpotWb);
            assertEquals("M+0.8", f.param.spotTintStr);
            assertSame(gainsB, f.param.spotGains);
            assertSame(transformB, f.param.spotTransform);
            assertEquals(3481, second.kelvin);
            assertTrue(second.measured);
            assertSame(f.a, second.characteristics);
            assertSame(gainsB, second.gains);
            assertSame(transformB, second.transform);
            assertNotEquals(first.controlKey, second.controlKey);
            f.preview.manual(gainsB, transformB);
            Request still = new Request();
            second.apply(still.builder, "2");
            still.manual(gainsB, transformB);

            // An already frozen A request stays A; the current request is B.
            assertEquals(3524, first.kelvin);
            assertSame(gainsA, first.gains);
            assertSame(transformA, first.transform);
            f.measured.verifyNoInteractions();
            f.converter.verifyNoInteractions();
        }
    }

    @Test public void frozenRequestWinsOverConflictingLogicalAndPhysicalTunables() throws Exception {
        try (Fixture f = new Fixture()) {
            f.model.setCurrentWbValue(3500);
            WhiteBalanceRequest3O frozen = f.param.snapshotWhiteBalance3O(f.a);
            RggbChannelVector laterGains = mock(RggbChannelVector.class);
            ColorSpaceTransform laterTransform = mock(ColorSpaceTransform.class);
            f.converter.when(() -> ColorTemperatureConverter.kelvinToRggb(7000, f.b)).thenReturn(laterGains);
            f.converter.when(() -> ColorTemperatureConverter.createColorTransform(7000, f.b)).thenReturn(laterTransform);
            CaptureController.mCameraCharacteristics = f.b;
            f.model.setCurrentWbValue(7000);
            Request still = new Request();
            for (Map<Object, Object> keys : new Map[]{still.logical, still.physical}) {
                keys.put(CaptureRequest.CONTROL_AWB_MODE, CaptureRequest.CONTROL_AWB_MODE_AUTO);
                keys.put(CaptureRequest.COLOR_CORRECTION_MODE, CaptureRequest.COLOR_CORRECTION_MODE_FAST);
                keys.put(CaptureRequest.COLOR_CORRECTION_GAINS, laterGains);
                keys.put(CaptureRequest.COLOR_CORRECTION_TRANSFORM, laterTransform);
            }
            frozen.apply(still.builder, "2");
            still.manual(f.gains, f.transform);
            assertEquals(3500, frozen.kelvin);
            assertSame(f.a, frozen.characteristics);
            assertEquals(7000, f.param.WB);
        }
    }

    @Test public void autoSnapshotDoesNotRewriteTemplateOrTunableDefaults() throws Exception {
        try (Fixture f = new Fixture()) {
            WhiteBalanceRequest3O automatic = f.param.snapshotWhiteBalance3O(f.a);
            Request request = new Request();
            automatic.apply(request.builder, "2");
            assertFalse(automatic.isManual());
            verify(request.builder, never()).set(any(), any());
            verify(request.builder, never()).setPhysicalCameraKey(any(), any(), anyString());
            f.converter.verifyNoInteractions();
        }
    }

    @Test public void unsupportedPhysicalKeyDoesNotDropLogicalWbOrOtherPhysicalKeys() throws Exception {
        try (Fixture f = new Fixture()) {
            f.model.setCurrentWbValue(3500);
            Request request = new Request();
            doThrow(new IllegalArgumentException("unsupported physical key"))
                    .when(request.builder).setPhysicalCameraKey(eq(CaptureRequest.CONTROL_AWB_MODE), any(), eq("2"));
            f.param.snapshotWhiteBalance3O(f.a).apply(request.builder, "2");
            assertEquals(CaptureRequest.CONTROL_AWB_MODE_OFF, request.logical.get(CaptureRequest.CONTROL_AWB_MODE));
            assertSame(f.gains, request.logical.get(CaptureRequest.COLOR_CORRECTION_GAINS));
            assertSame(f.transform, request.logical.get(CaptureRequest.COLOR_CORRECTION_TRANSFORM));
            assertSame(f.gains, request.physical.get(CaptureRequest.COLOR_CORRECTION_GAINS));
            assertSame(f.transform, request.physical.get(CaptureRequest.COLOR_CORRECTION_TRANSFORM));
        }
    }

    @Test public void pairedKelvinConversionKeepsCapturedCharacteristicsIfGlobalChanges() throws Exception {
        try (Fixture f = new Fixture()) {
            f.converter.when(() -> ColorTemperatureConverter.kelvinToRggb(3500, f.a)).thenAnswer(i -> {
                CaptureController.mCameraCharacteristics = f.b;
                return f.gains;
            });
            f.model.setCurrentWbValue(3500);
            f.converter.verify(() -> ColorTemperatureConverter.createColorTransform(3500, f.a));
            f.converter.verify(() -> ColorTemperatureConverter.createColorTransform(3500, f.b), never());
            f.preview.manual(f.gains, f.transform);
        }
    }

    @Test public void measuredSnapshotCannotReuseAnotherSensorsGains() throws Exception {
        try (Fixture f = new Fixture()) {
            RggbChannelVector measured = mock(RggbChannelVector.class);
            ColorSpaceTransform measuredTransform = mock(ColorSpaceTransform.class);
            f.param.setSpotWB(3524, "G+1.2", measured, measuredTransform);
            WhiteBalanceRequest3O held = f.param.snapshotWhiteBalance3O(f.a);
            WhiteBalanceRequest3O otherSensor = f.param.snapshotWhiteBalance3O(f.b);
            assertTrue(held.measured); assertSame(measured, held.gains);
            assertFalse(otherSensor.measured); assertSame(f.gains, otherSensor.gains);
            assertSame(f.b, otherSensor.characteristics);
            f.param.onCameraChanged();
            assertEquals(3524, f.param.WB); // Existing lens policy then decides whether the UI restores Kelvin.
            assertFalse(f.param.isSpotWb); assertNull(f.param.spotGains);
            assertSame(measured, held.gains);
            assertSame(measuredTransform, held.transform);
            assertTrue(held.measured);
        }
    }
}
