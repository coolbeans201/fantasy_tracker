#!/usr/bin/env python3
"""Print Python environment details (run before pip install)."""

import platform
import struct
import sys

print("executable:", sys.executable)
print("version:", sys.version)
print("platform:", platform.platform())
print("machine:", platform.machine())
print("bitness:", struct.calcsize("P") * 8, "bit")
print("PyPI tag (approx):", f"cp{sys.version_info.major}{sys.version_info.minor}-cp{sys.version_info.major}{sys.version_info.minor}")

if struct.calcsize("P") == 4:
    print("\nWARNING: 32-bit Python — pandas wheels may be unavailable. Use 64-bit Python.")
if sys.version_info >= (3, 14):
    print("\nNOTE: Python 3.14 needs pandas>=2.3.3 (wheels). Use: pip install \"pandas>=2.3.3,<3\"")
elif sys.version_info < (3, 12):
    print("\nWARNING: Fantasy Tracker requires Python 3.12+")
