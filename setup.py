from setuptools import setup, Extension

crustygame = Extension('crustygame',
                       include_dirs = ['/usr/include/SDL2'],
                       libraries = ['SDL2'],
                       sources = ['log_cb_helper.c', 'tilemap.c', 'synth.c', 'crustygamemodule.c'],
                       extra_compile_args = ['-W', '-Wall', '-Wextra', '-Wno-unused-parameter', '-DCOPY_FIX'])

setup (name = 'crustygame',
       version = '1.0',
       description = 'CrustyGame',
       ext_modules = [crustygame],
       install_requires = ['PySDL2', 'py_expression_eval == 0.3.14'])
