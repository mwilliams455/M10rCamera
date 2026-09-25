import com.particlesdevs.photoncamera.m10r.M10RLiveMeterState;

public final class M10RLiveMeterStateHostTest {
    private static void near(double a,double b,double eps,String name){
        if(Math.abs(a-b)>eps) throw new AssertionError(name+" "+a+" vs "+b);
    }
    public static void main(String[] args){
        double[] grid=new double[352];
        for(int i=0;i<grid.length;i++) grid[i]=i/351.0;
        M10RLiveMeterState.publish(1L,10000000L,200,0.5,0.25,0.25,0.125,grid);
        M10RLiveMeterState.Snapshot s=M10RLiveMeterState.snapshot();
        if(!s.valid || s.generation!=1 || s.previewIso!=200) throw new AssertionError("basic");
        near(s.codeIntegralVsWholeEv,-1.0,1e-12,"code EV");
        near(s.linearIntegralVsWholeEv,-1.0,1e-12,"linear EV");
        if(s.linearGrid==null || s.linearGrid.length!=352) throw new AssertionError("grid");
        s.linearGrid[0]=9.0;
        if(M10RLiveMeterState.snapshot().linearGrid[0]==9.0) throw new AssertionError("copy");
        System.out.println("M10RLiveMeterStateHostTest PASS");
    }
}
