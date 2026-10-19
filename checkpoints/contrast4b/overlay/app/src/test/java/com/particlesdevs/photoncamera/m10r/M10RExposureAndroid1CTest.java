package com.particlesdevs.photoncamera.m10r;
import android.media.Image;
import android.graphics.ImageFormat;
import android.graphics.Rect;
import java.nio.ByteBuffer;
import org.junit.Test;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;
public class M10RExposureAndroid1CTest {
    Image make(int w,int h,int stride,int limit){
        Image f=mock(Image.class);Image.Plane p=mock(Image.Plane.class);Rect r=new Rect();r.right=w;r.bottom=h;
        when(f.getFormat()).thenReturn(ImageFormat.RAW_SENSOR);when(f.getWidth()).thenReturn(w);when(f.getHeight()).thenReturn(h);
        when(f.getTimestamp()).thenReturn(100L);when(f.getCropRect()).thenReturn(r);when(f.getPlanes()).thenReturn(new Image.Plane[]{p});
        ByteBuffer b=ByteBuffer.allocate(limit+7);for(int i=0;i<b.capacity();i++)b.put(i,(byte)(i*13));b.position(7);
        when(p.getBuffer()).thenReturn(b);when(p.getRowStride()).thenReturn(stride);when(p.getPixelStride()).thenReturn(2);return f;
    }
    @Test public void paddedRowsCopyWithoutChangingBorrowedCursor(){
        for(int pad:new int[]{0,2,16,128}){
            int w=257,h=192,stride=w*2+pad;Image f=make(w,h,stride,stride*(h-1)+2*w);ByteBuffer b=f.getPlanes()[0].getBuffer();
            var owned=M10RExposureAndroid1C.copyAndClose(f,100);
            assertEquals(7,b.position());assertEquals(w*h*2,owned.bytes.capacity());
            for(int y=0;y<h;y++)for(int x=0;x<w*2;x++)assertEquals(b.get(7+y*stride+x),owned.bytes.get(y*w*2+x));
            verify(f,times(1)).close();
        }
    }
    @Test public void malformedInputsReleaseImage(){
        for(int kind=0;kind<6;kind++){
            Image f=make(256,192,512,512*192);
            if(kind==0)when(f.getTimestamp()).thenReturn(101L);
            if(kind==1)when(f.getFormat()).thenReturn(ImageFormat.JPEG);
            if(kind==2)when(f.getPlanes()[0].getPixelStride()).thenReturn(1);
            if(kind==3)when(f.getPlanes()[0].getRowStride()).thenReturn(510);
            if(kind==4)f.getCropRect().left=1;
            if(kind==5)f.getPlanes()[0].getBuffer().limit(100);
            assertThrows(IllegalArgumentException.class,()->M10RExposureAndroid1C.copyAndClose(f,100));verify(f,times(1)).close();
        }
    }
    @Test public void exceptionsWhileReadingStillReleaseImage(){
        Image f=make(256,192,512,512*192);when(f.getPlanes()[0].getBuffer()).thenThrow(new OutOfMemoryError("injected"));
        assertThrows(OutOfMemoryError.class,()->M10RExposureAndroid1C.copyAndClose(f,100));verify(f,times(1)).close();
    }
}
