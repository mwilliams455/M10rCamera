#!/usr/bin/env python3
"""Compile the real pinned AMaZE, test band parity/safety and exercise actual JNI."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,shutil
HERE=Path(__file__).resolve().parent
from prepare_upstream import prepare
STUBS={
'android/util/Rational.java':'''package android.util;
public class Rational extends Number {
 private final double v; public Rational(int a,int b){v=(double)a/b;}
 public double doubleValue(){return v;} public float floatValue(){return(float)v;}
 public int intValue(){return(int)v;} public long longValue(){return(long)v;}
}
''',
'android/hardware/camera2/CaptureResult.java':'''package android.hardware.camera2;
import android.util.Rational;
public class CaptureResult {
 public static class Key<T>{}
 public static final Key<Rational[]> SENSOR_NEUTRAL_COLOR_POINT=new Key<>();
 @SuppressWarnings("unchecked") public <T> T get(Key<T> key){return (T)new Rational[]{new Rational(2,5),new Rational(1,1),new Rational(3,2)};}
}
''',
'org/json/JSONObject.java':'''package org.json;
public class JSONObject {public JSONObject put(String k,Object v)throws Exception{return this;}}
''',
'JniTest.java':'''import com.particlesdevs.photoncamera.m10r.M10RAmaze1A;
import android.hardware.camera2.CaptureResult;
import org.json.JSONObject;
import java.util.Arrays;
public class JniTest {
 public static void main(String[] args)throws Exception{
  int checks=0;short[] raw=new short[257*301];Arrays.fill(raw,(short)14000);
  for(int iteration=0;iteration<24;iteration++){
   short[] rgb=new short[257*256*3];Arrays.fill(rgb,(short)12345);
   M10RAmaze1A s=M10RAmaze1A.open(raw,257,301,0,.5,new CaptureResult(),new JSONObject());
   s.readBand(0,256,rgb);
   if(rgb[0]!=12345 || (rgb[(100*257+100)*3]&0xffff)!=14000)throw new AssertionError("JNI border/interior");checks++;
   s.readBand(256,45,rgb);s.close();s.close();checks++;
   try{s.readBand(0,256,rgb);throw new AssertionError("closed accepted");}catch(IllegalStateException expected){checks++;}
  }
  try{M10RAmaze1A.open(null,257,301,0,.5,new CaptureResult(),new JSONObject());throw new AssertionError("null raw accepted");}catch(IllegalArgumentException expected){checks++;}
  System.out.println("{\\"status\\":\\"pass\\",\\"jniAssertions\\":"+checks+",\\"phoneValidated\\":false}");
 }
}
'''}
def main():
 upstream=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve();out.mkdir(parents=True,exist_ok=True)
 provenance=json.loads((upstream/'PROVENANCE.json').read_text())
 for name,digest in provenance['files'].items():
  assert hashlib.sha256((upstream/name).read_bytes()).hexdigest()==digest,name
 assert hashlib.sha256((upstream/'amaze.cc').read_bytes()).hexdigest()=='a43f01c7ffe70efdf92dec473d5a785658c11756365d78df617d7a4c28117f1e'
 def run(args,file=None):
  result=subprocess.run([str(x) for x in args],cwd=out,text=True,capture_output=True,timeout=180,env=dict(os.environ,OMP_WAIT_POLICY="PASSIVE"))
  if file:(out/file).write_text(result.stdout+result.stderr)
  if result.returncode:raise RuntimeError('command failed: '+repr(args)+'\n'+result.stdout+result.stderr)
  print(result.stdout,end='',flush=True);return result
 common=[os.environ.get('CXX','g++'),'-std=c++17','-fopenmp','-ffp-contract=off','-I',upstream/'include']
 compiled=out/'compiled_upstream'
 proof=prepare(upstream,compiled)
 (out/'UPSTREAM_FIX1_RESULTS.json').write_text(json.dumps(proof,indent=2)+'\n')
 sources=[compiled/'amaze_m10r_fix1.cc',compiled/'border.cc']
 run(common+['-O2',HERE/'host_test.cpp']+sources+['-o',out/'host_test'])
 run([out/'host_test','full'],'HOST_TEST_RESULTS.json')
 run(common+['-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer',HERE/'host_test.cpp']+sources+['-o',out/'host_test_asan'])
 run([out/'host_test_asan'],'HOST_SANITIZER_RESULTS.json')
 # Android ARM builds use the non-SSE implementation. Test that branch too;
 # compare full/banded/worker outputs within it, not across SIMD variants.
 run(common+['-U__SSE2__','-O2',HERE/'host_test.cpp']+sources+['-o',out/'host_test_scalar'])
 run([out/'host_test_scalar','full'],'HOST_SCALAR_RESULTS.json')
 run(common+['-U__SSE2__','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer',HERE/'host_test.cpp']+sources+['-o',out/'host_test_scalar_asan'])
 run([out/'host_test_scalar_asan'],'HOST_SCALAR_SANITIZER_RESULTS.json')
 jdk=Path(shutil.which('javac')).resolve().parents[1]
 run(common+['-O2','-fPIC','-shared','-I',jdk/'include','-I',jdk/'include/linux',HERE/'jni.cpp']+sources+['-o',out/'libm10ramaze.so'])
 java=[]
 for name,content in STUBS.items():
  dest=out/'jni-test'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(content);java.append(dest)
 classes=out/'classes';classes.mkdir(exist_ok=True)
 run(['javac','-d',classes,HERE/'M10RAmaze1A.java']+java)
 run(['java','-Xcheck:jni','-Djava.library.path='+str(out),'-cp',classes,'JniTest'],'JNI_HOST_RESULTS.json')
if __name__=='__main__':main()
