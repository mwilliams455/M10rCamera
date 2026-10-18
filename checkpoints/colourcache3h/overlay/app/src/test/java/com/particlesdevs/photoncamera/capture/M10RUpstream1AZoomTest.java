package com.particlesdevs.photoncamera.capture;

import org.junit.Test;
import java.util.Arrays;
import static org.junit.Assert.*;

/** Integration contract: no preview crop while the custom still path uses full RAW. */
public class M10RUpstream1AZoomTest {
    private ZoomController fullSensor() {
        ZoomController zoom = new ZoomController();
        zoom.setDigitalCropEnabled(false);
        zoom.setLenses(Arrays.asList(
                new ZoomController.LensEntry("uw", .6f, 3f),
                new ZoomController.LensEntry("main", 1f, 8f),
                new ZoomController.LensEntry("tele", 3.1f, 3f)));
        zoom.setActiveLens("main");
        return zoom;
    }

    @Test public void fractionalZoomDoesNotCropOrMislabelMainLens() {
        ZoomController zoom = fullSensor();
        assertNull(zoom.setTargetZoom(1.8f, .2f, .8f));
        assertEquals(1f, zoom.getZoomRatio(), 0f);
        assertEquals(1f, zoom.getDigitalZoom(), 0f);
        assertFalse(zoom.isZoomed());
    }

    @Test public void physicalLensSwitchesRemainAvailableAndUncropped() {
        ZoomController zoom = fullSensor();
        assertEquals("tele", zoom.setTargetZoom(3.1f, .5f, .5f));
        zoom.setActiveLens("tele");
        assertEquals(3.1f, zoom.getZoomRatio(), 0f);
        assertEquals(3.1f, zoom.getMaxZoom(), 0f);
        assertFalse(zoom.isZoomed());
        assertEquals("uw", zoom.setTargetZoom(.6f, .5f, .5f));
        zoom.setActiveLens("uw");
        assertEquals(.6f, zoom.getZoomRatio(), 0f);
        assertFalse(zoom.isZoomed());
    }

    @Test public void lockedLensCannotCreateDigitalCrop() {
        ZoomController zoom = fullSensor();
        zoom.setLensSwitchLocked(true);
        assertNull(zoom.setTargetZoom(8f, .5f, .5f, false));
        assertEquals("main", zoom.getActiveLensId());
        assertEquals(1f, zoom.getZoomRatio(), 0f);
        assertEquals(1f, zoom.getMaxZoom(), 0f);
        assertFalse(zoom.isZoomed());
    }
}
