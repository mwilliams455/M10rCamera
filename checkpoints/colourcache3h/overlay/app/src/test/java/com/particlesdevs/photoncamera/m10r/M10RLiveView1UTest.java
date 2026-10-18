package com.particlesdevs.photoncamera.m10r;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.Arrays;
import org.junit.Test;
import static org.junit.Assert.*;

public class M10RLiveView1UTest {
    static final int W=176,H=128;
    static final long NOW=1_100_000_000L;
    static double[] flat(double v){double[] a=new double[W*H];Arrays.fill(a,v);return a;}
    static M10RMetering1U.Config config(M10RMetering1U.Mode mode){return new M10RMetering1U.Config(mode);}
    static M10RMetering1U.Measurement measure(double[] g,M10RMetering1U.Config c){return M10RMetering1U.measure(g,4096,3072,c);}
    static double[] split(){double[] a=flat(.04);for(int y=0;y<H;y++)for(int x=W/2;x<W;x++)a[y*W+x]=.32;return a;}
    static M10RHighlightGuard1A.Stats stats(int q,double clip){
        int[] qs=new int[24];Arrays.fill(qs,q);double[] c=new double[24];Arrays.fill(c,clip);
        return new M10RHighlightGuard1A.Stats(0,clip,qs,new double[24],c);
    }
    static M10RExposure1A.Probe probe(M10RMetering1U.Measurement m,double user,double refUser,double refAuto,boolean clipping){
        M10RHighlightGuard1A.Stats[] s=new M10RHighlightGuard1A.Stats[7];
        for(int i=0;i<7;i++)s[i]=stats(100,clipping&&i>0?.5:0);
        var b=new M10RHighlightGuard1A.Stats[]{stats(100,0),stats(95,0),stats(90,0)};
        return new M10RExposure1A.Probe("cam",1,1,"renderer",123,123,NOW-100_000_000,NOW-10_000_000,
                10_000_000,200,refUser,refAuto,M10RExposure1A.ProbeDomain.M10R_RENDERED_USER_EV_REFERENCE,
                m.cells(),s,M10RHighlightGuard1A.noSubject(7),user,b,m);
    }
    static M10RExposure1A.Request request(M10RMetering1U.Config c,double user){
        return new M10RExposure1A.Request("cam",1,"renderer",NOW,user,1.8,28,100,50000,true,c);
    }
    @Test public void uniformFieldHasNoSpatialBiasInAnyMode(){
        for(var mode:M10RMetering1U.Mode.values())for(double grey:new double[]{0,.001,.18,.9,1}) {
            var c=config(mode);var m=measure(flat(grey),c);
            assertEquals(grey,m.mean,1e-12);assertEquals(grey,m.integral,1e-12);assertEquals(grey,m.spot,1e-12);
            var p=M10RExposure1A.prepare(probe(m,0,0,0,false),request(c,0));
            assertTrue(p.ready());assertEquals(0,p.appliedAutoEv,1e-10);assertNull(p.multiField);
        }
    }
    @Test public void centreWeightsRespondInBothDirections(){
        double[] dark=flat(.4),bright=flat(.04);
        for(int y=H/4;y<3*H/4;y++)for(int x=W/4;x<3*W/4;x++){dark[y*W+x]=.04;bright[y*W+x]=.4;}
        var c=config(M10RMetering1U.Mode.CENTRE_WEIGHTED);
        assertTrue(measure(dark,c).spatialEv>.2);assertTrue(measure(bright,c).spatialEv<-.2);
        assertEquals(14160,Arrays.stream(M10RIntegralMask.copyWeights()).sum());
    }
    @Test public void movingSpotSelectsDarkOrBrightPartOfSameFrame(){
        var left=new M10RMetering1U.Config(M10RMetering1U.Mode.SPOT,0,0,1,1,.2,.5);
        var right=new M10RMetering1U.Config(M10RMetering1U.Mode.SPOT,0,0,1,1,.8,.5);
        var a=measure(split(),left);var b=measure(split(),right);
        assertEquals(.04,a.spot,1e-12);assertEquals(.32,b.spot,1e-12);
        assertTrue(a.spatialEv>1);assertTrue(b.spatialEv<-.5);
    }
    @Test public void edgeSpotIsKeptInsideCrop(){
        for(double x:new double[]{0,1})for(double y:new double[]{0,1}) {
            var c=new M10RMetering1U.Config(M10RMetering1U.Mode.SPOT,0,0,1,1,x,y);
            assertEquals(.2,measure(flat(.2),c).spot,1e-12);
        }
    }
    @Test public void relativeMeterDoesNotInventAbsolutePhoneRawGreyTarget(){
        for(var mode:new M10RMetering1U.Mode[]{M10RMetering1U.Mode.CENTRE_WEIGHTED,M10RMetering1U.Mode.SPOT}) {
            var c=new M10RMetering1U.Config(mode,0,0,1,1,.2,.5);
            double[] g=split();double expected=measure(g,c).spatialEv;
            for(int i=0;i<g.length;i++)g[i]/=16;
            assertEquals(expected,measure(g,c).spatialEv,1e-10);
        }
    }
    @Test public void rawAndRenderedRegionsUseSamePhysicalBoundaries(){
        for(int[] size:new int[][]{{4096,3072},{4080,3060},{8064,6048},{4032,3024}}) {
            double[] green=new double[W*H];int[] argb=new int[green.length];
            for(int y=0;y<H;y++)for(int x=0;x<W;x++) {
                double u=(M10RMetering1U.sampleCoordinate(x,W,size[0])+.5-16)/(size[0]-32);
                double v=(M10RMetering1U.sampleCoordinate(y,H,size[1])+.5-16)/(size[1]-32);
                int col=(int)(u*22);
                int f=(int)(v*4)*6+(col<4?0:col<8?1:col<11?2:col<14?3:col<18?4:5),code=20+8*f;
                green[y*W+x]=(f+1)/25.0;argb[y*W+x]=0xff000000|code*0x010101;
            }
            var m=M10RMetering1U.measure(green,size[0],size[1],config(M10RMetering1U.Mode.MULTI_FIELD));
            var s=M10RHighlightGuard1A.measureArgb(argb,W,H,m.fields());
            for(int f=0;f<24;f++){assertEquals((f+1)/25.0,m.regions()[f],1e-12);assertEquals(20+8*f,s.q90(f));}
        }
    }
    @Test public void cropExcludesOutsideLightFromBothMeasurements(){
        var c=new M10RMetering1U.Config(M10RMetering1U.Mode.SPOT,0,0,.49,1,.5,.5);
        var m=measure(split(),c);assertEquals(.04,m.mean,1e-12);assertEquals(0,m.spatialEv,1e-10);
        int[] argb=new int[W*H];
        for(int y=0;y<H;y++)for(int x=0;x<W;x++)argb[y*W+x]=x<W/2?0xff646464:0xffffffff;
        var s=M10RHighlightGuard1A.measureArgb(argb,W,H,m.fields());
        assertEquals(0,s.clipped,0);assertEquals(0,s.bright,0);
    }
    @Test public void sparseSamplingHonorsCfaBlackLevelsStrideAndBufferCursor(){
        int w=256,h=192,stride=w*2+16,offset=8;
        for(int cfa=0;cfa<4;cfa++) {
            ByteBuffer b=ByteBuffer.allocate(offset+stride*h).order(ByteOrder.LITTLE_ENDIAN);
            double[] black={40,60,80,100};
            for(int y=0;y<h;y++)for(int x=0;x<w;x++) {
                int p=(y%2)*2+x%2;boolean g=M10RExposureRaw1B.GAIN_CHANNELS[cfa][p]==1||M10RExposureRaw1B.GAIN_CHANNELS[cfa][p]==2;
                b.putShort(offset+y*stride+x*2,(short)(g?black[p]+(1060-black[p])*.5:1060));
            }
            b.position(3);b.order(ByteOrder.BIG_ENDIAN);
            double[] samples=M10RMetering1U.sampleGreen(b.asReadOnlyBuffer(),offset,stride,w,h,cfa,black,1060);
            assertEquals(3,b.position());assertEquals(ByteOrder.BIG_ENDIAN,b.order());
            for(double g:samples)assertEquals(.5,g,1e-12);
        }
    }
    @Test public void incompleteOrInvalidGeometryCannotAuthorizeModePlan(){
        assertThrows(IllegalArgumentException.class,()->measure(flat(.2),new M10RMetering1U.Config(M10RMetering1U.Mode.SPOT,.49,.49,.51,.51,.5,.5)));
        double[] bad=flat(.2);bad[12]=Double.NaN;
        assertThrows(IllegalArgumentException.class,()->measure(bad,config(M10RMetering1U.Mode.SPOT)));
        assertThrows(IllegalArgumentException.class,()->new M10RMetering1U.Config(M10RMetering1U.Mode.SPOT,0,0,1,1,Double.NaN,.5));
    }
    @Test public void measurementsOwnTheirArrays(){
        double[] green=flat(.2);var m=measure(green,config(M10RMetering1U.Mode.SPOT));Arrays.fill(green,1);
        m.cells()[0]=1;m.regions()[0]=1;m.fields()[0]=-1;
        assertEquals(.2,m.cells()[0],1e-12);assertEquals(.2,m.regions()[0],1e-12);assertTrue(m.fields()[0]>=0);
    }
    @Test public void modeSpotAndCropChangesRejectOldRawProbe(){
        var c=config(M10RMetering1U.Mode.SPOT);var p=probe(measure(split(),c),0,0,0,false);
        for(var other:new M10RMetering1U.Config[]{config(M10RMetering1U.Mode.MULTI_FIELD),
                new M10RMetering1U.Config(M10RMetering1U.Mode.SPOT,0,0,1,1,.2,.5),
                new M10RMetering1U.Config(M10RMetering1U.Mode.SPOT,.1,.1,.9,.9,.5,.5),null})
            assertEquals(M10RExposure1A.Status.METERING_MISMATCH,M10RExposure1A.prepare(p,request(other,0)).status);
    }
    @Test public void explicitEvIsAddedExactlyOnceAfterModeMeasurement(){
        var c=new M10RMetering1U.Config(M10RMetering1U.Mode.SPOT,0,0,1,1,.2,.5);var m=measure(split(),c);
        for(double user:new double[]{-1.25,0,.75}) {
            var p=M10RExposure1A.prepare(probe(m,user,.5,.25,false),request(c,user));
            assertTrue(p.ready());assertEquals(m.spatialEv,p.appliedAutoEv,0);
            assertEquals(user+m.spatialEv-.75,p.deltaFromReferenceEv,1e-12);
        }
    }
    @Test public void spotIntentIsNotVetoedByBrightBackground(){
        var c=new M10RMetering1U.Config(M10RMetering1U.Mode.SPOT,0,0,1,1,.2,.5);var m=measure(split(),c);
        var p=M10RExposure1A.prepare(probe(m,0,0,0,true),request(c,0));
        assertTrue(p.ready());assertEquals(0,p.highlight.maxPositiveEv,0);assertTrue(p.appliedAutoEv>1);
        assertNull(p.multiField);assertEquals(m.spatialEv,p.appliedAutoEv,0);
    }
    @Test public void previewScaleAndStillAllocationUseSameModeDecision()throws Exception {
        var c=new M10RMetering1U.Config(M10RMetering1U.Mode.SPOT,0,0,1,1,.2,.5);var m=measure(split(),c);
        var selection=M10RExposureCapture1B.select(probe(m,0,0,0,false),request(c,0),null,
                new M10RExposureCapture1B.Limits(1000,1_000_000_000,50,50000));
        assertTrue(selection.apply);assertFalse(selection.fallback);
        Object owner=new Object();var pp=new M10RPreviewPlan1A(1,owner,"cam",c.key(),NOW-100_000_000,NOW-1_000_000,
                10_000_000,200,selection,new M10RExposureReport1C(new org.json.JSONObject()));
        assertEquals((double)selection.exposureNs*selection.iso/(10_000_000.0*200),pp.previewScale(10_000_000,200),1e-12);
        assertTrue(pp.captureEligible(owner,"cam",c.key(),NOW,10_000_000,200,1,NOW));
        assertFalse(pp.captureEligible(owner,"cam",config(M10RMetering1U.Mode.MULTI_FIELD).key(),NOW,10_000_000,200,1,NOW));
        assertFalse(pp.captureEligible(new Object(),"cam",c.key(),NOW,10_000_000,200,1,NOW));
    }
    @Test public void evidenceLabelsResearchAndAdapterBoundaries()throws Exception {
        var c=config(M10RMetering1U.Mode.MULTI_FIELD);var m=measure(split(),c);
        var p=M10RExposure1A.prepare(probe(m,0,0,0,false),request(c,0));var d=M10RMeteringEvidence1U.build(p);
        assertFalse(d.getBoolean("sceneSpecificForegroundOverridesEnabled"));assertFalse(d.getBoolean("absoluteFirmwareCalibrationEstablished"));
        assertEquals(1,d.getInt("photographicRawFrames"));assertFalse(d.getBoolean("frameFusion"));
    }
    @Test public void legacyAutoAndAverageResolveToMultiField(){
        assertEquals(M10RMetering1U.Mode.MULTI_FIELD,M10RMetering1U.mode(-1));
        assertEquals(M10RMetering1U.Mode.MULTI_FIELD,M10RMetering1U.mode(1));
        assertEquals(M10RMetering1U.Mode.CENTRE_WEIGHTED,M10RMetering1U.mode(0));
        assertEquals(M10RMetering1U.Mode.SPOT,M10RMetering1U.mode(2));
    }
}
