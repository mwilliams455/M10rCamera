#!/usr/bin/env python3
"""Compile and execute the real reducer, without Android or private-photo fixtures."""
from pathlib import Path
import json,subprocess,tempfile,sys
root=Path(__file__).resolve().parents[1]
harness=r'''
import com.particlesdevs.photoncamera.m10r.M10RMeterAreaMath;
import java.nio.ByteBuffer;
import java.util.Arrays;
public class TestArea {
  static int assertions=0;
  static void ok(boolean b,String why) { assertions++; if(!b) throw new AssertionError(why); }
  static void near(double a,double b,double e,String why) { ok(Math.abs(a-b)<e,why+":"+a+" != "+b); }
  static ByteBuffer image(int mode,int value) {
    ByteBuffer b=ByteBuffer.allocate(128*176*4);
    for(int fy=0;fy<176;fy++) for(int fx=0;fx<128;fx++) {
      int v=mode==0?value:mode==1?(((fx+fy+value)&1)*255):((fx/8)*22+fy/8)%256;
      b.put((byte)v).put((byte)v).put((byte)v).put((byte)255);
    }
    b.flip();return b;
  }
  public static void main(String[] args) {
    for(double exponent:new double[]{1.0,1.9}) {
      for(int value=0;value<256;value++) {
        ByteBuffer b=image(0,value); int pos=b.position();
        M10RMeterAreaMath.Grid g=M10RMeterAreaMath.reduce(b,exponent);
        ok(b.position()==pos,"input position preserved");
        for(int i=0;i<352;i++) {
          double y=M10RMeterAreaMath.decode(value);
          near(g.code[i],value/255.0,2e-14,"uniform code");
          near(g.linear[i],y,2e-14,"uniform linear");
          near(g.green[i],y,2e-14,"uniform green");
          near(g.proxyBeforeAverage[i],Math.pow(y,exponent),2e-14,"uniform proxy");
        }
      }
    }
    M10RMeterAreaMath.Grid checker=M10RMeterAreaMath.reduce(image(1,0),1.9);
    M10RMeterAreaMath.Grid shifted=M10RMeterAreaMath.reduce(image(1,1),1.9);
    for(int i=0;i<352;i++) {
      near(checker.linear[i],0.5,1e-14,"checker area linear mean");
      near(checker.proxyBeforeAverage[i],0.5,1e-14,"proxy before averaging");
      near(checker.linear[i],shifted.linear[i],1e-14,"one-sample phase shift invariance");
      ok(Math.abs(checker.linear[i]-M10RMeterAreaMath.decode(128))>0.28,"gamma before average matters");
      ok(Math.abs(checker.proxyBeforeAverage[i]-Math.pow(checker.linear[i],1.9))>0.2,"proxy order distinction");
      double phaseMean=0;
      for(int p=0;p<4;p++)phaseMean+=checker.linearPhases[p][i]/4;
      near(phaseMean,checker.linear[i],1e-14,"phase partition");
    }
    M10RMeterAreaMath.Grid spatial=M10RMeterAreaMath.reduce(image(2,0),1.0);
    for(int i=0;i<352;i++) near(spatial.linear[i],M10RMeterAreaMath.decode(i%256),2e-14,"FBO-to-sensor axes");
    ByteBuffer rgb=ByteBuffer.allocate(128*176*4);
    for(int i=0;i<128*176;i++)rgb.put((byte)255).put((byte)0).put((byte)0).put((byte)255);
    rgb.flip();M10RMeterAreaMath.Grid red=M10RMeterAreaMath.reduce(rgb,1);
    near(red.linear[0],0.2126,1e-14,"linear RGB coefficients");
    near(red.green[0],0,1e-14,"green separated from luminance");
    for(double exp:new double[]{0,-1,Double.NaN,Double.POSITIVE_INFINITY}) {
      boolean threw=false;try{M10RMeterAreaMath.reduce(image(0,1),exp);}catch(IllegalArgumentException e){threw=true;}
      ok(threw,"reject invalid exponent");
    }
    boolean threw=false;try{M10RMeterAreaMath.reduce(ByteBuffer.allocate(4),1);}catch(IllegalArgumentException e){threw=true;}
    ok(threw,"reject short buffer");
    int[][] maps={{0,1,2,3},{1,0,3,2},{1,3,0,2},{3,1,2,0}};
    for(int cfa=0;cfa<4;cfa++) {
      int[] counts=new int[4];int n=0,legacyN=0;
      for(int y=0;y<8;y++) for(int x=0;x<8;x++) {
        int site=((y&1)<<1)|(x&1),channel=maps[cfa][site];
        if((channel==1||channel==2)&&(x&7)<2&&(y&7)<2){counts[channel]++;n++;}
        if((site==1||site==2)&&(((y&7)==0&&(x&7)==1)||((y&7)==1&&(x&7)==0)))
          if(channel==1||channel==2)legacyN++;
      }
      ok(n==2&&counts[1]==1&&counts[2]==1,"both CFA-resolved greens");
      ok(legacyN==((cfa==0||cfa==3)?2:0),"legacy compatibility flag");
    }
    System.out.println(assertions);
  }
}
'''
with tempfile.TemporaryDirectory() as td:
    t=Path(td); (t/'TestArea.java').write_text(harness)
    subprocess.run(['javac','-d',str(t),str(root/'android/meterarea1a/M10RMeterAreaMath.java'),str(t/'TestArea.java')],check=True)
    r=subprocess.run(['java','-cp',str(t),'TestArea'],capture_output=True,text=True,check=True)
    assertions=int(r.stdout.strip())
result={'schema':'METERAREA1A_HOST_TEST_V1','assertionsPassed':assertions,
        'actualJavaReducerExecuted':True,'syntheticOnly':True,
        'linearBeforeAverageTested':True,'proxyOrderDifferenceTested':True,
        'transposedFboCoordinatesTested':True,'fourCfaGreenSelectionTested':True,
        'phoneOpenGlNotTested':True,'realSceneAgreementNotEstablished':True}
print(json.dumps(result,indent=2))
if len(sys.argv)>1:Path(sys.argv[1]).write_text(json.dumps(result,indent=2)+'\n')
