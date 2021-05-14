#!/usr/bin/env python3

from ctypes import *
from sdl2 import *
import pycrustygame as cg

def main():
    window = SDL_Window()
    renderer = SDL_Renderer()

    ret = SDL_CreateWindowAndRenderer(640, 480, SDL_WINDOW_SHOWN,
                                      pointer(window), pointer(renderer))

    ll = cg.LayerList(renderer, SDL_PIXELFORMAT_RGBA32)

if __name__ == "__main__":
    main()
