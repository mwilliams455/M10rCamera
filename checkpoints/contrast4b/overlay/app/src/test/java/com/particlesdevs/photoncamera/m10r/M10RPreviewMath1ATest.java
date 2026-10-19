package com.particlesdevs.photoncamera.m10r;
import org.junit.Test;
import static org.junit.Assert.*;
public class M10RPreviewMath1ATest {
    @Test public void requestedCurvesInvertWithinFloatingPointPrecision(){
        for(int n:new int[]{16,32,64}){
            float[] c=M10RPreviewMath1A.srgbCurve(n);assertTrue(M10RPreviewMath1A.validCurve(c));
            for(int i=0;i<=4096;i++){
                double x=i/4096.0;
                assertEquals(x,M10RPreviewMath1A.invertCurve(c,M10RPreviewMath1A.curveOutput(c,x)),1e-6);
            }
        }
    }
    @Test public void linearOrFlatReportedCurveCannotMasqueradeAsRequestedSrgb(){
        float[] c=M10RPreviewMath1A.srgbCurve(64);
        assertTrue(M10RPreviewMath1A.curveOutputError(c,new float[]{0,0,1,1})>3.0/255);
        assertFalse(M10RPreviewMath1A.validCurve(new float[]{0,0,.5f,0,1,1}));
    }
    @Test public void inverseMatrixReallyReversesCrossChannelColourCorrection(){
        double[] a={1.3,-.2,-.1,-.1,1.2,-.1,.03,-.13,1.1};double[] b=M10RPreviewMath1A.inverse(a);
        for(int y=0;y<3;y++)for(int x=0;x<3;x++){
            double v=0;for(int k=0;k<3;k++)v+=a[y*3+k]*b[k*3+x];assertEquals(y==x?1:0,v,1e-12);
        }
        assertThrows(IllegalArgumentException.class,()->M10RPreviewMath1A.inverse(new double[9]));
    }
    @Test public void cubeCoordinatesRoundTripThroughAtlasAndSensorUnits(){
        short[] cube=M10RPreviewColour1A.cube();assertEquals(33*33*33*3,cube.length);
        for(int g=0;g<33;g++)for(int b=0;b<33;b++)for(int r=0;r<33;r++){
            int p=((g*33+b)*33+r)*3;
            assertEquals(M10RPreviewColour1A.unshape(r/32.0),(cube[p]&65535)*4.0/65535,4.0/65535);
            assertEquals(M10RPreviewColour1A.unshape(g/32.0),(cube[p+1]&65535)*4.0/65535,4.0/65535);
            assertEquals(M10RPreviewColour1A.unshape(b/32.0),(cube[p+2]&65535)*4.0/65535,4.0/65535);
        }
    }
}
