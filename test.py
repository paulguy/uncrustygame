#!/usr/bin/env python3

from ctypes import *
from sdl2 import *
import pycrustygame as cg

# making this thing work in some useful way has been CBT so just yeah
@cg.LOG_CB_RETURN_T
def log_cb_return(string :c_char_p):
    print(string.decode("utf-8"))

def main():
    window = SDL_CreateWindow(b"asdf", SDL_WINDOWPOS_UNDEFINED, SDL_WINDOWPOS_UNDEFINED, 640, 480, SDL_WINDOW_SHOWN)
    renderer = SDL_CreateRenderer(window, 1, 0);

    ll = cg.Layerlist(renderer, SDL_PIXELFORMAT_ARGB32, log_cb_return)
    ts = ll.new_blank_tileset(512, 512, 0, 32, 32)
    ts2 = ll.new_tileset_from_bmp("cdemo/font.bmp", 8, 8)
    tm = ll.new_tilemap(ts, 8, 8)
    tm2 = ll.new_tilemap(ts2, 16, 16)
    l = ll.new_layer(tm)
    l2 = ll.new_layer(tm)
    l3 = ll.new_layer(tm2)

if __name__ == "__main__":
    main()
