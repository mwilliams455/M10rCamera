package com.particlesdevs.photoncamera.m10r;
import android.graphics.ImageFormat;
import android.media.Image;
import android.media.ImageReader;
import com.particlesdevs.photoncamera.processing.*;
import org.junit.Test;
import org.mockito.MockedStatic;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;
public class M10RExposureOwnedSaver1CTest {
    @Test public void ownedImageIsNotReacquiredAndSurplusIsClosed(){
        ImageSaver saver=mock(ImageSaver.class,CALLS_REAL_METHODS);SaverImplementation implementation=mock(SaverImplementation.class);
        saver.implementation=implementation;saver.setFrameCount(1);saver.newBurst=true;
        ImageReader reader=mock(ImageReader.class);when(reader.getImageFormat()).thenReturn(ImageFormat.RAW_SENSOR);
        Image first=mock(Image.class),surplus=mock(Image.class);when(first.getFormat()).thenReturn(ImageFormat.RAW_SENSOR);
        try(MockedStatic<ImageSaverSelector> selector=mockStatic(ImageSaverSelector.class)){
            selector.when(()->ImageSaverSelector.getImageSaver(ImageFormat.RAW_SENSOR,implementation)).thenReturn(implementation);
            saver.initOwnedRaw1C(reader,first);verify(implementation,times(1)).addImage(first);verify(first,never()).close();
            assertEquals(1,implementation.frameCount);assertTrue(implementation.newBurst);
            saver.initOwnedRaw1C(reader,surplus);verify(surplus,times(1)).close();verify(implementation,never()).addImage(surplus);
            verify(reader,never()).acquireNextImage();verify(reader,never()).acquireLatestImage();
        }
    }
}
