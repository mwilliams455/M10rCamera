#!/usr/bin/env python3
from pathlib import Path
import sys
if len(sys.argv)!=2: raise SystemExit('usage: fix-m10r-capture1b-compile1.py <PhotonCamera-root>')
p=Path(sys.argv[1]).resolve()/'app/src/main/java/com/particlesdevs/photoncamera/m10r/M10RNativeRenderer.java'
if not p.exists(): raise SystemExit('CAPTURE1B COMPILE1 renderer missing')
s=p.read_text()
old='''        } catch (Throwable t) {\n            if (bitmap != null && !bitmap.isRecycled()) bitmap.recycle();\n            throw t;\n        } finally {'''
new='''        } catch (Throwable t) {\n            if (bitmap != null && !bitmap.isRecycled()) bitmap.recycle();\n            if (t instanceof Exception) throw (Exception)t;\n            throw new RuntimeException(t);\n        } finally {'''
if s.count(old)!=1: raise SystemExit('CAPTURE1B COMPILE1 rethrow anchor missing/non-unique')
p.write_text(s.replace(old,new,1))
print('CAPTURE1B COMPILE1 applied: Throwable converted to declared Exception/RuntimeException boundary')