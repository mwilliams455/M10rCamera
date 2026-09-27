#!/usr/bin/env python3
"""Host tests of actual SOURCEPROXY1C Java, using small typed Camera2 stand-ins.
These are synthetic metadata/array tests, not Android camera device validation.
CI separately compiles the complete APK against the real Android SDK.
"""
from pathlib import Path
import json
import subprocess
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
STUBS = {
'android/graphics/Rect.java': '''package android.graphics; public class Rect {
public int left,top,right,bottom; public Rect(int l,int t,int r,int b){left=l;top=t;right=r;bottom=b;}
public int width(){return right-left;} public int height(){return bottom-top;}}''',
'android/util/Size.java': '''package android.util; public class Size { int w,h; public Size(int w,int h){this.w=w;this.h=h;}
public int getWidth(){return w;} public int getHeight(){return h;}}''',
'android/util/SizeF.java': '''package android.util; public class SizeF { float w,h; public SizeF(float w,float h){this.w=w;this.h=h;}
public float getWidth(){return w;} public float getHeight(){return h;}}''',
'android/util/Rational.java': '''package android.util; public class Rational { int n,d; public Rational(int n,int d){this.n=n;this.d=d;}
public int getNumerator(){return n;} public int getDenominator(){return d;}}''',
'android/hardware/camera2/params/BlackLevelPattern.java': '''package android.hardware.camera2.params;
public class BlackLevelPattern {int[] v; public BlackLevelPattern(int[] v){this.v=v;} public int getOffsetForIndex(int c,int r){return v[r*2+c];}}''',
'android/hardware/camera2/params/ColorSpaceTransform.java': '''package android.hardware.camera2.params; import android.util.Rational;
public class ColorSpaceTransform {Rational[] v; public ColorSpaceTransform(Rational[] v){this.v=v;} public Rational getElement(int c,int r){return v[r*3+c];}}''',
}
KEYS = {
'android.graphics.Rect': ['SENSOR_INFO_ACTIVE_ARRAY_SIZE','SENSOR_INFO_PRE_CORRECTION_ACTIVE_ARRAY_SIZE'],
'android.util.Size': ['SENSOR_INFO_PIXEL_ARRAY_SIZE'],
'android.util.SizeF': ['SENSOR_INFO_PHYSICAL_SIZE'],
'Integer': ['SENSOR_INFO_COLOR_FILTER_ARRANGEMENT','SENSOR_INFO_WHITE_LEVEL','SENSOR_REFERENCE_ILLUMINANT1'],
'Byte': ['SENSOR_REFERENCE_ILLUMINANT2'],
'float[]': ['LENS_INFO_AVAILABLE_FOCAL_LENGTHS','LENS_INFO_AVAILABLE_APERTURES'],
'android.hardware.camera2.params.BlackLevelPattern': ['SENSOR_BLACK_LEVEL_PATTERN'],
'android.hardware.camera2.params.ColorSpaceTransform': ['SENSOR_COLOR_TRANSFORM1','SENSOR_COLOR_TRANSFORM2','SENSOR_FORWARD_MATRIX1','SENSOR_FORWARD_MATRIX2','SENSOR_CALIBRATION_TRANSFORM1','SENSOR_CALIBRATION_TRANSFORM2'],
}
STUBS['android/hardware/camera2/CameraCharacteristics.java'] = '''package android.hardware.camera2;
import java.util.HashMap; import java.util.Map; public class CameraCharacteristics {
public static class Key<T> {} private final Map<Key<?>,Object> data=new HashMap<>();
@SuppressWarnings("unchecked") public <T>T get(Key<T> k){return (T)data.get(k);}
public <T>void put(Key<T> k,T v){data.put(k,v);}
''' + '\n'.join('public static final Key<%s> %s=new Key<>();' % (t,k) for t,ks in KEYS.items() for k in ks) + '\n}'
HOST = r'''package com.particlesdevs.photoncamera.m10r;
import android.hardware.camera2.CameraCharacteristics;
import static android.hardware.camera2.CameraCharacteristics.*;
import android.hardware.camera2.params.*; import android.graphics.Rect;
import android.util.*; import java.util.*;
public class SourceProxy1CHostTest {
    static int tests=0;
    static void ok(boolean v,String name){if(!v)throw new AssertionError(name);tests++;}
    static M10RMfm1DSourceProxy.Profile p(CameraCharacteristics c){return M10RMfm1DSourceProxy.resolve(c,25.1,2.6);}
    static ColorSpaceTransform matrix(int numerator,int denominator){
        Rational[] a=new Rational[9]; for(int n=0;n<9;n++)a[n]=new Rational(n%4==0?numerator:0,denominator);
        return new ColorSpaceTransform(a);
    }
    static CameraCharacteristics camera(boolean a){
        CameraCharacteristics c=new CameraCharacteristics();
        int w=a?4096:4080;
        c.put(SENSOR_INFO_ACTIVE_ARRAY_SIZE,new Rect(0,0,w,3072));
        c.put(SENSOR_INFO_PRE_CORRECTION_ACTIVE_ARRAY_SIZE,new Rect(0,0,w,3072));
        c.put(SENSOR_INFO_PIXEL_ARRAY_SIZE,new Size(w,3072));
        c.put(SENSOR_INFO_PHYSICAL_SIZE,new SizeF(a?13.1072f:9.1392f,6.881f));
        c.put(SENSOR_INFO_COLOR_FILTER_ARRANGEMENT,0);c.put(SENSOR_INFO_WHITE_LEVEL,1023);
        c.put(SENSOR_REFERENCE_ILLUMINANT1,21);c.put(SENSOR_REFERENCE_ILLUMINANT2,(byte)17);
        c.put(LENS_INFO_AVAILABLE_FOCAL_LENGTHS,new float[]{a?8.72f:25.1f});
        c.put(LENS_INFO_AVAILABLE_APERTURES,new float[]{a?1.63f:2.6f});
        c.put(SENSOR_BLACK_LEVEL_PATTERN,new BlackLevelPattern(new int[]{64,64,64,64}));
        c.put(SENSOR_COLOR_TRANSFORM1,matrix(1,1));c.put(SENSOR_FORWARD_MATRIX1,matrix(1,1));
        return c;
    }
    public static void main(String[] args){
        CameraCharacteristics a=camera(true), b=camera(false); String id=p(b).fingerprint;
        ok(p(a).exponent==1.90,"seed A preserved"); ok(p(b).exponent==1.0,"seed B preserved");
        ok(p(a).calibrationStatus.equals("inherited_pair_seed_provisional"),"not falsely full calibrated");
        ok(p(b).fingerprint.length()==64,"full SHA256");
        for(double focal:new double[]{1,25.1,200,Double.NaN})for(double aperture:new double[]{1.2,2.6,16,Double.NaN}){
            var x=M10RMfm1DSourceProxy.resolve(b,focal,aperture);
            ok(x.fingerprint.equals(id)&&x.exponent==1.0,"current optics do not affect identity or calibration");
        }
        var telemetry=M10RMfm1DSourceProxy.resolve(b,50,8);
        ok(telemetry.physicalFocalMm==50&&telemetry.aperture==8,"current optics remain telemetry");
        CameraCharacteristics v=camera(false);
        v.put(LENS_INFO_AVAILABLE_APERTURES,new float[]{1.8f,2.6f,4});
        v.put(LENS_INFO_AVAILABLE_FOCAL_LENGTHS,new float[]{10,25.1f,50});
        String variable=p(v).fingerprint;
        ok(!variable.equals(id)&&p(v).calibrationStatus.equals("uncalibrated_identity_fallback"),"no singleton alias for variable optics");
        ok(M10RMfm1DSourceProxy.resolve(v,10,1.8).fingerprint.equals(M10RMfm1DSourceProxy.resolve(v,50,4).fingerprint),"variable optical state stable");
        v.put(LENS_INFO_AVAILABLE_APERTURES,new float[]{4,2.6f,1.8f,2.6f});
        v.put(LENS_INFO_AVAILABLE_FOCAL_LENGTHS,new float[]{50,25.1f,10,10});
        ok(variable.equals(p(v).fingerprint),"array order and duplicate independence");
        var immutable=v.get(LENS_INFO_AVAILABLE_FOCAL_LENGTHS).clone();p(v);
        ok(Arrays.equals(immutable,v.get(LENS_INFO_AVAILABLE_FOCAL_LENGTHS)),"metadata arrays not modified");
        b.put(SENSOR_COLOR_TRANSFORM1,matrix(2,2));ok(id.equals(p(b).fingerprint),"equivalent rational canonicalization");
        b.put(SENSOR_COLOR_TRANSFORM1,matrix(-3,-3));ok(id.equals(p(b).fingerprint),"negative denominator canonicalization");
        b.put(SENSOR_COLOR_TRANSFORM1,matrix(2,1));ok(!id.equals(p(b).fingerprint),"color matrix alters identity");
        b=camera(false);b.put(SENSOR_FORWARD_MATRIX1,matrix(2,1));ok(!id.equals(p(b).fingerprint),"forward matrix alters identity");
        b=camera(false);b.put(SENSOR_CALIBRATION_TRANSFORM1,matrix(1,1));ok(!id.equals(p(b).fingerprint),"calibration matrix alters identity");
        b=camera(false);b.put(SENSOR_INFO_PHYSICAL_SIZE,new SizeF(9.1392f,7.0f));ok(!id.equals(p(b).fingerprint),"sensor height alters identity");
        b=camera(false);b.put(SENSOR_BLACK_LEVEL_PATTERN,new BlackLevelPattern(new int[]{65,64,64,64}));ok(!id.equals(p(b).fingerprint),"black level alters identity");
        b=camera(false);b.put(SENSOR_INFO_WHITE_LEVEL,4095);ok(!id.equals(p(b).fingerprint)&&p(b).calibrationStatus.equals("uncalibrated_identity_fallback"),"white level new uncalibrated source");
        b=camera(false);b.put(SENSOR_INFO_COLOR_FILTER_ARRANGEMENT,1);ok(!id.equals(p(b).fingerprint)&&p(b).exponent==1.0,"different CFA new source");
        b=camera(false);b.put(SENSOR_INFO_ACTIVE_ARRAY_SIZE,new Rect(2,0,4082,3072));ok(!id.equals(p(b).fingerprint)&&p(b).calibrationStatus.equals("uncalibrated_identity_fallback"),"origin change no inherited alias");
        b=camera(false);b.put(LENS_INFO_AVAILABLE_FOCAL_LENGTHS,null);
        ok(p(b).calibrationStatus.equals("uncalibrated_identity_fallback"),"missing optics not replaced by current focal");
        b=camera(false);b.put(LENS_INFO_AVAILABLE_APERTURES,new float[]{Float.NaN,2.6f});
        ok(p(b).calibrationStatus.equals("uncalibrated_identity_fallback"),"invalid optics no inherited alias");
        b=camera(false);b.put(LENS_INFO_AVAILABLE_APERTURES,new float[0]);ok(p(b).exponent==1.0,"empty optics safe fallback");
        ok(p(null).fingerprint.equals(p(null).fingerprint)&&p(null).exponent==1.0,"null metadata deterministic fallback");
        b=camera(false);b.put(SENSOR_REFERENCE_ILLUMINANT2,(byte)255);ok(p(b).referenceIlluminant2==255,"illuminant2 unsigned byte");
        b=camera(false);Locale save=Locale.getDefault();Locale.setDefault(Locale.FRANCE);
        ok(id.equals(p(b).fingerprint),"locale independence");Locale.setDefault(save);
        b.put(LENS_INFO_AVAILABLE_FOCAL_LENGTHS,new float[]{25.100002f});ok(id.equals(p(b).fingerprint),"floating representation tolerance");
        b.put(LENS_INFO_AVAILABLE_FOCAL_LENGTHS,new float[]{25.102f});ok(!id.equals(p(b).fingerprint),"real metadata change detected");
        ok(M10RMfm1DSourceProxy.transform(null,p(a))==null,"null grid");
        Random random=new Random(1234); double[] grid=new double[100000];
        for(int i=0;i<grid.length;i++)grid[i]=random.nextDouble()*1.2;
        grid[0]=Double.NaN;grid[1]=Double.POSITIVE_INFINITY;grid[2]=-1;grid[3]=0;grid[4]=1;
        double[] saved=grid.clone();
        for(var profile:new M10RMfm1DSourceProxy.Profile[]{p(a),p(camera(false))}){
            double[] actual=M10RMfm1DSourceProxy.transform(grid,profile);
            for(int i=0;i<grid.length;i++){
                double x=grid[i];double expected=!Double.isFinite(x)||x<0?Double.NaN:Math.pow(Math.max(0,Math.min(1,x)),profile.exponent);
                if(Double.doubleToLongBits(actual[i])!=Double.doubleToLongBits(expected))throw new AssertionError("transform parity index "+i);
            }
            ok(true,"100000 sample bit-exact old transform reference");
            ok(actual!=grid&&Arrays.equals(grid,saved),"grid copied and input unchanged");
        }
        System.out.println("{\"passedAssertions\":"+tests+",\"transformSamplesCompared\":200000,\"androidDeviceTested\":false}");
    }
}
'''

def main():
    with tempfile.TemporaryDirectory(prefix='sourceproxy1c_') as tmp:
        tmp=Path(tmp)
        files=dict(STUBS)
        java_rel='com/particlesdevs/photoncamera/m10r/'
        files[java_rel+'M10RMfm1DSourceProxy.java']=(ROOT/'android/sourceproxy1c/M10RMfm1DSourceProxy.java').read_text()
        files[java_rel+'SourceProxy1CHostTest.java']=HOST
        for name,text in files.items():
            p=tmp/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
        subprocess.run(['javac','--release','17','-d',str(tmp/'classes')]+[str(tmp/n) for n in files],check=True,timeout=60)
        result=subprocess.run(['java','-cp',str(tmp/'classes'),'com.particlesdevs.photoncamera.m10r.SourceProxy1CHostTest'],check=True,text=True,capture_output=True,timeout=60)
        data=json.loads(result.stdout)
        print(json.dumps(data,indent=2))
        if len(sys.argv)>1:Path(sys.argv[1]).write_text(json.dumps(data,indent=2)+'\n')

if __name__=='__main__':main()
