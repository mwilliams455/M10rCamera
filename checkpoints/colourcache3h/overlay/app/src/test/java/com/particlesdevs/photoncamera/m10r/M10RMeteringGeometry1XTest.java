package com.particlesdevs.photoncamera.m10r;

import org.junit.Test;
import static org.junit.Assert.*;

public class M10RMeteringGeometry1XTest {
    @Test public void boundariesAndAreasMatchOriginalWrapperRois() {
        // Original 25 evaluator calls: Integral, then four rows of these ROIs.
        int[] columns={0,0,0,0,1,1,1,1,2,2,2,3,3,3,4,4,4,4,5,5,5,5};
        int[] counts=new int[24];
        for(int r=0;r<16;r++)for(int c=0;c<22;c++) {
            int field=M10RMeteringGeometry1X.fieldForCell(r*22+c);
            assertEquals((r/4)*6+columns[c],field);counts[field]++;
        }
        assertArrayEquals(new int[]{16,16,12,12,16,16,16,16,12,12,16,16,
                16,16,12,12,16,16,16,16,12,12,16,16},counts);
    }
    @Test public void unevenSparseDensityDoesNotChangeCellAreaWeight() {
        int w=4032,h=3024;double[] green=new double[176*128];
        var cfg=new M10RMetering1U.Config(M10RMetering1U.Mode.MULTI_FIELD,.137,.173,.863,.827,.5,.5);
        // One bright cell in field 0: its expected contribution is 1/16,
        // independent of how many sparse sample points landed in that cell.
        for(int y=0;y<128;y++)for(int x=0;x<176;x++) {
            double px=M10RMetering1U.sampleCoordinate(x,176,w)+.5;
            double py=M10RMetering1U.sampleCoordinate(y,128,h)+.5;
            green[y*176+x]=px>=cfg.left*w&&px<(cfg.left+(cfg.right-cfg.left)/22)*w
                    &&py>=cfg.top*h&&py<(cfg.top+(cfg.bottom-cfg.top)/16)*h?1:0;
        }
        var m=M10RMetering1U.measure(green,w,h,cfg);
        assertEquals(1,m.cells()[0],0);assertEquals(1.0/16,m.regions()[0],0);
        for(int i=1;i<24;i++)assertEquals(0,m.regions()[i],0);
    }
    @Test public void invalidAndMutableInputsCannotCorruptGeometry() {
        assertThrows(IllegalArgumentException.class,()->M10RMeteringGeometry1X.fieldForCell(-1));
        assertThrows(IllegalArgumentException.class,()->M10RMeteringGeometry1X.fieldForCell(352));
        assertThrows(IllegalArgumentException.class,()->M10RMeteringGeometry1X.regionMeans(new double[351]));
        double[] bad=new double[352];bad[100]=Double.NaN;
        assertThrows(IllegalArgumentException.class,()->M10RMeteringGeometry1X.regionMeans(bad));
        M10RMeteringGeometry1X.columnStarts()[0]=99;M10RMeteringGeometry1X.columnWidths()[0]=99;
        assertEquals(0,M10RMeteringGeometry1X.fieldForCell(0));
        assertEquals(4,M10RMeteringGeometry1X.columnWidths()[0]);
    }
    @Test public void sidecarCarriesGeometryAndExplicitCalibrationBoundary()throws Exception {
        var cfg=M10RLiveView1UTest.config(M10RMetering1U.Mode.MULTI_FIELD);
        var m=M10RLiveView1UTest.measure(M10RLiveView1UTest.split(),cfg);
        var p=M10RExposure1A.prepare(M10RLiveView1UTest.probe(m,0,0,0,false),M10RLiveView1UTest.request(cfg,0));
        var j=M10RMeteringEvidence1U.build(p);
        assertEquals(352,j.getJSONArray("rawCells16x22").length());
        assertEquals("[4,4,3,3,4,4]",j.getJSONArray("regionColumnWidths").toString());
        assertFalse(j.getBoolean("firmwareStatisticsEngineControlsExposure"));
        assertFalse(j.getBoolean("absoluteFirmwareCalibrationEstablished"));
    }
}
