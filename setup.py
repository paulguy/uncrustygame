from distutils.core import setup, Extension

crustygame = Extension('crustygame',
                       include_dirs = ['/usr/include/SDL2'],
                       libraries = ['SDL2'],
                       sources = ['log_cb_helper.c', 'tilemap.c', 'synth.c', 'crustygamemodule.c'])

setup (name = 'crustygame',
       version = '1.0',
       description = 'CrustyGame',
       ext_modules = [crustygame])
