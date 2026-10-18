package com.particlesdevs.photoncamera.m10r;

/** Geometry from CA9 0x40000e98..0x40001330. No phone brightness calibration. */
public final class M10RMeteringGeometry1X {
    public static final String REVISION="CA9_16x22_REGIONS_4_4_3_3_4_4";
    private static final int[] STARTS={0,4,8,11,14,18};
    private static final int[] WIDTHS={4,4,3,3,4,4};
    private M10RMeteringGeometry1X() {}
    public static int[] columnStarts(){return STARTS.clone();}
    public static int[] columnWidths(){return WIDTHS.clone();}
    public static int fieldForCell(int cell) {
        if(cell<0||cell>=352)throw new IllegalArgumentException("meter cell");
        int col=cell%22,fieldCol=5;
        while(fieldCol>0&&col<STARTS[fieldCol])fieldCol--;
        return (cell/22/4)*6+fieldCol;
    }
    /** Linear phone diagnostic means. Every complete cell has equal area;
     * sparse sample density must not give individual cells more influence.
     * Firmware's uint32 Y truncation and Q8 conversion are separate operations.
     */
    public static double[] regionMeans(double[] cells) {
        if(cells==null||cells.length!=352)throw new IllegalArgumentException("16x22 cells required");
        double[] out=new double[24];
        for(int i=0;i<352;i++) {
            double value=cells[i];
            if(!Double.isFinite(value)||value<0||value>1)throw new IllegalArgumentException("normalized RAW cell");
            out[fieldForCell(i)]+=value;
        }
        for(int i=0;i<24;i++)out[i]/=4*WIDTHS[i%6];
        return out;
    }
}
