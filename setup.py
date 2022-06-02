import sys
import os
import subprocess
from setuptools import setup, Extension

cflags = ['-W', '-Wall', '-Wextra', '-Wno-unused-parameter', '-DCOPY_FIX']
ldflags = []

def pkg_config(name, defcflags, defldflags):
    print("Getting CFLAGS for {}... ".format(name), end='')
    pkgcflags = None
    try:
        pkgcflags = subprocess.run(
            ('pkg-config', '--cflags', name),
            capture_output=True, check=True)
        pkgcflags = pkgcflags.stdout.split()
        for num, val in enumerate(pkgcflags):
            pkgcflags[num] = val.decode('utf-8')
        print("Got {}".format(pkgcflags))
    except subprocess.CalledProcessError as e:
        print("Failed to get {} CFLAGS, using {}. error: {}".format(name, defcflags, e))
        pkgcflags = defcflags

    print("Getting LDFLAGS for {}... ".format(name), end='')
    pkgldflags = None
    try:
        pkgldflags = subprocess.run(
            ('pkg-config', '--libs', name),
            capture_output=True, check=True)
        pkgldflags = pkgldflags.stdout.split()
        for num, val in enumerate(pkgldflags):
            pkgldflags[num] = val.decode('utf-8')
        print("Got {}".format(pkgldflags))
    except subprocess.CalledProcessError as e:
        print("Failed to get {} LDFLAGS, using {}. error: {}".format(name, defldflags, e))
        pkgldflags = defldflags

    return pkgcflags, pkgldflags

compile_args = []
link_args = []

pkgcflags = None
pkgldflags = None
if os.uname().sysname == 'Darwin':
    pkgcflags, pkgldflags = pkg_config('sdl2', 
        ("-I/Library/Frameworks/SDL2.framework/Headers",),
        ("-F", "/Library/Frameworks", "-framework", "SDL2"))
else:
    pkgcflags, pkgldflags = pkg_config('sdl2',
        ("-I/usr/include/SDL2",),
        ('-lSDL2',))
compile_args.extend(pkgcflags)
link_args.extend(pkgldflags)

compile_args.extend(cflags)
link_args.extend(ldflags)

crustygame = Extension('crustygame',
                       sources = ['log_cb_helper.c', 'tilemap.c', 'synth.c', 'crustygamemodule.c'],
                       extra_compile_args = compile_args,
                       extra_link_args = link_args)

setup (name = 'crustygame',
       version = '1.0',
       description = 'CrustyGame',
       ext_modules = [crustygame],
       install_requires = ['PySDL2',
                           'py_expression_eval == 0.3.14'])
