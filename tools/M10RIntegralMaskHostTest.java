import com.particlesdevs.photoncamera.m10r.M10RIntegralMask;

public final class M10RIntegralMaskHostTest {
    public static void main(String[] args) {
        int[] w=M10RIntegralMask.copyWeights();
        if(w.length!=352) throw new AssertionError("length");
        int sum=0, nonzero=0, max=0;
        for(int v:w){sum+=v;if(v!=0)nonzero++;if(v>max)max=v;}
        if(sum!=14160) throw new AssertionError("sum "+sum);
        if(nonzero!=312) throw new AssertionError("nonzero "+nonzero);
        if(max!=100) throw new AssertionError("max "+max);
        for(int r=0;r<M10RIntegralMask.ROWS;r++) for(int c=0;c<M10RIntegralMask.COLS;c++) {
            int a=M10RIntegralMask.weight(r,c);
            int b=M10RIntegralMask.weight(M10RIntegralMask.ROWS-1-r,M10RIntegralMask.COLS-1-c);
            if(a!=b) throw new AssertionError("symmetry "+r+","+c);
        }
        System.out.println("M10RIntegralMaskHostTest PASS");
    }
}
