package com.particlesdevs.photoncamera.m10r;

/** Domain math only: no camera-ID fits, scene residuals or exposure feedback. */
public final class M10RPreviewMath1A {
    private M10RPreviewMath1A() {}
    public static double decode(double v) {
        return v <= .04045 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4);
    }
    public static float[] srgbCurve(int points) {
        int n = Math.max(2, Math.min(64, points));
        float[] c = new float[2*n];
        // Uniform input knots support index-addressed HAL LUTs as well as Camera2 curves.
        for (int i=0;i<n;i++) {
            double x=(double)i/(n-1);
            c[2*i]=(float)x;
            c[2*i+1]=(float)(x<=.0031308?12.92*x:1.055*Math.pow(x,1/2.4)-.055);
        }
        return c;
    }
    /** Maximum vertical error between two piecewise-linear curves, at their union of knots. */
    public static double curveOutputError(float[] requested, float[] reported) {
        if (!validCurve(requested) || !validCurve(reported)) return Double.POSITIVE_INFINITY;
        double error=0;
        for (float[] knots:new float[][]{requested,reported}) for (int i=0;i<knots.length;i+=2)
            error=Math.max(error,Math.abs(curveOutput(requested,knots[i])-curveOutput(reported,knots[i])));
        return error;
    }
    public static double curveOutput(float[] c,double x) {
        if (x<=0) return 0; if (x>=1) return 1;
        for (int i=2;i<c.length;i+=2) if (x<=c[i])
            return c[i-1]+(c[i+1]-c[i-1])*(x-c[i-2])/(c[i]-c[i-2]);
        return 1;
    }
    public static boolean validCurve(float[] c) {
        if (c==null || c.length<4 || (c.length&1)!=0) return false;
        if (Math.abs(c[0])>1e-6 || Math.abs(c[1])>1e-6
                || Math.abs(c[c.length-2]-1)>1e-6 || Math.abs(c[c.length-1]-1)>1e-6) return false;
        for (int i=0;i<c.length;i++) if (!Float.isFinite(c[i]) || c[i]<0 || c[i]>1) return false;
        for (int i=2;i<c.length;i+=2) if (c[i]<=c[i-2] || c[i+1]<=c[i-1]) return false;
        return true;
    }
    public static double invertCurve(float[] c, double y) {
        if (y<=0) return 0; if (y>=1) return 1;
        for (int i=2;i<c.length;i+=2) if (y<=c[i+1])
            return c[i-2]+(c[i]-c[i-2])*(y-c[i-1])/(c[i+1]-c[i-1]);
        return 1;
    }
    /** Two RGBA8 rows hold high/low bytes of linear RGB; decode texels before interpolating. */
    public static byte[] inverseTexture(float[][] curves) {
        byte[] b=new byte[1024*2*4];
        for (int c=0;c<3;c++) {
            if (!validCurve(curves[c])) throw new IllegalArgumentException("noninvertible_tonemap_curve");
            for (int i=0;i<1024;i++) {
                int q=(int)Math.round(65535*invertCurve(curves[c],i/1023.0));
                b[4*i+c]=(byte)(q>>>8); b[4096+4*i+c]=(byte)q;
            }
        }
        return b;
    }
    public static double[] inverse(double[] a) {
        if (a==null || a.length!=9) throw new IllegalArgumentException("missing_matrix");
        for (double v:a) if (!Double.isFinite(v)) throw new IllegalArgumentException("invalid_matrix");
        double d=a[0]*(a[4]*a[8]-a[5]*a[7])-a[1]*(a[3]*a[8]-a[5]*a[6])+a[2]*(a[3]*a[7]-a[4]*a[6]);
        if (Math.abs(d)<1e-5) throw new IllegalArgumentException("singular_camera_transform");
        double[] b={a[4]*a[8]-a[5]*a[7],a[2]*a[7]-a[1]*a[8],a[1]*a[5]-a[2]*a[4],
            a[5]*a[6]-a[3]*a[8],a[0]*a[8]-a[2]*a[6],a[2]*a[3]-a[0]*a[5],
            a[3]*a[7]-a[4]*a[6],a[1]*a[6]-a[0]*a[7],a[0]*a[4]-a[1]*a[3]};
        for (int i=0;i<9;i++) { b[i]/=d; if (Math.abs(b[i])>32) throw new IllegalArgumentException("ill_conditioned_camera_transform"); }
        return b;
    }
    public static float[] columnMajor(double[] a) {
        float[] b=new float[9];
        for (int y=0;y<3;y++) for (int x=0;x<3;x++) {
            if (!Double.isFinite(a[y*3+x])) throw new IllegalArgumentException("invalid_colour_context");
            b[x*3+y]=(float)a[y*3+x];
        }
        return b;
    }
}
