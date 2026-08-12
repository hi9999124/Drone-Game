[app]
title = Drone / PVO
package.name = dronepvo
package.domain = org.dronepvo

source.dir = .
source.include_exts = py

version = 0.1.0
# python3 pinned to 3.10: pygame's own C source (src_c/_sdl2/sdl2.c) includes
# CPython's internal longintrepr.h, which moved to Include/cpython/ in Python
# 3.11. python-for-android's pygame recipe predates that move, so building
# against an unpinned (3.11+) hostpython fails with "longintrepr.h file not
# found". 3.10.x still has the header at the old path.
# hostpython3 pinned alongside python3: p4a builds hostpython3 (used to run
# build scripts during cross-compilation) as its own separate recipe, and
# recent p4a versions no longer auto-sync it to the python3 recipe's pinned
# version -- left unpinned, it resolves against whatever python3 the runner
# image ships (observed: 3.14.2), which trips p4a's own "python3 must match
# hostpython3" sanity check before the build ever gets to compiling anything.
requirements = python3==3.10.14,hostpython3==3.10.14,pygame

orientation = landscape
fullscreen = 1

android.permissions =
android.api = 33
android.minapi = 21
android.archs = arm64-v8a, armeabi-v7a

[buildozer]
log_level = 2
warn_on_root = 1
