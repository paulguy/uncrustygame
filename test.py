#!/usr/bin/env python3

import time
import array
from itertools import islice, count
from ctypes import *
from sdl2 import *
import pycrustygame as cg
import sequencer as seq
import audio

@cg.LOG_CB_RETURN_T
def log_cb_return(priv: py_object, string :c_char_p):
    print(string.decode("utf-8"), end='')

def clear_frame(ll, r, g, b):
    if SDL_SetRenderDrawColor(ll.renderer, r, g, b, SDL_ALPHA_OPAQUE) < 0:
        raise(Exception())
    if SDL_RenderClear(ll.renderer) < 0:
        raise(Exception())
    if SDL_SetRenderDrawColor(ll.renderer, 0, 0, 0, SDL_ALPHA_TRANSPARENT) < 0:
        raise(Exception())

# this is probably bad but whichever
def string_to_ints(string):
    array = list()

    for item in string:
        encoded = item.encode("utf-32")
        array.append(encoded[4] +
                     (encoded[5] * 0x100) +
                     (encoded[6] * 0x10000) +
                     (encoded[7] * 0x1000000))

    return(array)

def create_linear_slope(start, end, num):
    step = (end - start) / (num - 1)
    slope = array.array('f', islice(count(start, step), num))

    return(slope)
        

def main():
    SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO)
    window, renderer, pixfmt = cg.initialize_video("asdf", 640, 480, SDL_WINDOW_SHOWN, SDL_RENDERER_PRESENTVSYNC)
    red = cg.tilemap_color(255, 0, 0, 255)
    green = cg.tilemap_color(0, 255, 0, 255)
    blue = cg.tilemap_color(0, 0, 255, 255)

    ll = cg.Layerlist(renderer, pixfmt, log_cb_return, window)
    ts = ll.tileset_from_bmp("cdemo/font.bmp", 8, 8)
    tm = ll.tilemap(ts, 8, 8)
    tm.map(2, 2, 4, 4, 3, string_to_ints("tseta sisiht"))
    tm.attr_flags(2, 2, 0, 4, 3, (cg.TILEMAP_ROTATE_180, cg.TILEMAP_ROTATE_180, cg.TILEMAP_ROTATE_180, cg.TILEMAP_ROTATE_180))
    tm.attr_colormod(2, 2, 4, 4, 3, (red, green, blue, red, green, blue, red, green, blue, red, green, blue))
    tm.update(0, 0, 8, 8)
    l = ll.layer(tm)
    l.pos(200, 200)
    l.window(32, 24)
    l.scroll_pos(16, 16)
    l.scale(4.0, 4.0)
    l.rotation_center(32, 24)
    l.rotation(180)
    l.colormod(cg.tilemap_color(255, 255, 64, 192))
    l.blendmode(cg.TILEMAP_BLENDMODE_ADD) 

    aud = audio.AudioSystem(log_cb_return, None, 48000, 2)
    rate = aud.rate
    envslope = aud.buffer(cg.SYNTH_TYPE_F32,
                          cg.create_float_array(create_linear_slope(0.0, 1.0, rate)),
                          rate)
    seq = None
    with open("testseq2.txt", "r") as seqfile:
        seq = audio.AudioSequencer(seqfile, [envslope])
    aud.add_sequence(seq)
    aud.enabled(True)

    running = True
    playing = True
    lastTime = time.monotonic()
    while running:
        event = SDL_Event()

        while SDL_PollEvent(event):
            if event.type == SDL_QUIT:
                running = False
                break
            elif event.type == SDL_KEYDOWN:
                if event.key.keysym.sym == SDLK_q:
                    running = False
                elif event.key.keysym.sym == SDLK_s:
                    aud.sequence_enabled(seq, True)

        clear_frame(ll, 32, 128, 192)
        l.draw()
        aud.frame()

        thisTime = time.monotonic()
        if running and seq.ended:
            print("Sequence ended")
            running = False

        lastTime = thisTime
        SDL_RenderPresent(renderer)

    aud.enabled(False)
    aud.del_sequence(seq)
    SDL_DestroyRenderer(renderer)
    SDL_DestroyWindow(window)


if __name__ == "__main__":
    main()
