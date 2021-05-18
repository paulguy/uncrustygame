#!/usr/bin/env python3

from ctypes import *
from sdl2 import *
import pycrustygame as cg

# making this thing work in some useful way has been CBT so just yeah
@cg.LOG_CB_RETURN_T
def log_cb_return(string :c_char_p):
    print(string.decode("utf-8"))

def clear_frame(ll, r, g, b):
    if SDL_SetRenderDrawColor(ll.renderer, r, g, b, SDL_ALPHA_OPAQUE) < 0:
        raise(Exception())
    if SDL_RenderClear(ll.renderer) < 0:
        raise(Exception())
    if SDL_SetRenderDrawColor(ll.renderer, 0, 0, 0, SDL_ALPHA_TRANSPARENT) < 0:
        raise(Exception())

def main():
    # TODO: Write actual window/renderer initialization stuff
    window = SDL_CreateWindow(b"asdf", SDL_WINDOWPOS_UNDEFINED, SDL_WINDOWPOS_UNDEFINED, 640, 480, SDL_WINDOW_SHOWN)
    renderer = SDL_CreateRenderer(window, 1, 0);

    ll = cg.Layerlist(renderer, SDL_PIXELFORMAT_ARGB32, log_cb_return)
    ts = ll.tileset_from_bmp("cdemo/font.bmp", 8, 8)
    tm = ll.tilemap(ts, 8, 8)
    tm.map(2, 2, 4, 4, 3, "thisis atest")
    tm.update(0, 0, 8, 8)
    l = ll.layer(tm)

    running = 1
    while running:
        event = SDL_Event()

        while SDL_PollEvent(event):
            if event.type == SDL_QUIT:
                running = 0
                break

        clear_frame(ll, 32, 128, 192)
        l.draw()
        SDL_RenderPresent(renderer)

if __name__ == "__main__":
    main()
