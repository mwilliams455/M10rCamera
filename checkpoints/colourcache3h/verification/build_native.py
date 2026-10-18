from pathlib import Path
import os,subprocess,json,hashlib
R=Path(__file__).resolve().parents[1];src=R/'PhotonCamera/app/src/main/cpp'
ndk=Path(os.environ.get('M10R_NDK',R/'deps/android-ndk-r27c')).resolve();tc=ndk/'toolchains/llvm/prebuilt/linux-x86_64/bin'
rows=[]
for abi,target in [('arm64-v8a','aarch64-linux-android24'),('armeabi-v7a','armv7a-linux-androideabi24')]:
 dest=R/'PhotonCamera/app/src/main/jniLibs'/abi/'libm10rcolour3h.so'
 cmd=[str(tc/(target+'-clang++')),'-std=c++17','-O3','-ffp-contract=off','-fno-fast-math','-shared','-fPIC','-fvisibility=hidden','-static-libstdc++','-Wl,--exclude-libs,ALL','-Wl,-z,max-page-size=16384','-Wl,-z,common-page-size=16384','-Wl,--no-undefined',str(src/'m10rColour3H.cpp'),'-o',str(dest)]
 p=subprocess.run(cmd,capture_output=True,text=True);(R/'verification'/f'native_{abi}.log').write_text(p.stdout+p.stderr);p.check_returncode()
 subprocess.run([tc/'llvm-strip','--strip-unneeded',dest],check=True)
 readelf=subprocess.check_output([tc/'llvm-readelf','-h','-l','-d','--dyn-syms',dest],text=True)
 assert 'Java_com_particlesdevs_photoncamera_m10r_M10RColour3H_nativeProcessTile' in readelf
 assert 'libc++_shared.so' not in readelf
 assert all('0x4000' in x for x in readelf.splitlines() if x.lstrip().startswith('LOAD'))
 (R/'verification'/f'native_{abi}_elf.txt').write_text(readelf)
 rows.append({'abi':abi,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'bytes':dest.stat().st_size,'staticallyLinkedPrivateCxx':True,'elf16KiBAligned':True,'command':cmd})
(R/'results/NATIVE_BUILD3H.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))
