[app]
title = Drone / PVO
package.name = dronepvo
package.domain = org.dronepvo

source.dir = .
source.include_exts = py

version = 0.1.0
requirements = python3,pygame

orientation = landscape
fullscreen = 1

android.permissions =
android.api = 33
android.minapi = 21
android.archs = arm64-v8a, armeabi-v7a

[buildozer]
log_level = 2
warn_on_root = 1
