#!/usr/bin/env python3

import time
from ctypes import *
from sdl2 import *
import pycrustygame as cg
import sequencer as seq
import audio

@cg.LOG_CB_RETURN_T
def log_cb_return(priv: py_object, string :c_char_p):
    print(string.decode("utf-8"))

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


def main():
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

    seqdesc = seq.SequenceDescription()
    rowdesc = seqdesc.add_row_description()
    seqdesc.add_field(rowdesc, seq.FIELD_TYPE_INT)
    seqdesc.add_field(rowdesc, seq.FIELD_TYPE_INT)
    seqdesc.add_field(rowdesc, seq.FIELD_TYPE_FLOAT)
    seqdesc.add_field(rowdesc, seq.FIELD_TYPE_HEX)
    seqdesc.add_field(rowdesc, seq.FIELD_TYPE_STR)
    seqdesc.add_column(rowdesc)
    rowdesc2 = seqdesc.add_row_description()
    seqdesc.add_field(rowdesc2, seq.FIELD_TYPE_INT)
    seqdesc.add_field(rowdesc2, seq.FIELD_TYPE_FLOAT)
    seqdesc.add_field(rowdesc2, seq.FIELD_TYPE_ROW, rowDesc=rowdesc)
    seqdesc.add_column(rowdesc2)
    with open("testseq.txt", "r") as seqfile:
        sequence = seq.Sequencer(seqdesc, seqfile)
    sequence.write_file()

    running = 1
    lastTime = time.monotonic()
    while running:
        event = SDL_Event()

        while SDL_PollEvent(event):
            if event.type == SDL_QUIT:
                running = 0
                break

        clear_frame(ll, 32, 128, 192)
        l.draw()

        thisTime = time.monotonic()
        try:
            timeMS = int((thisTime - lastTime) * 1000)
            while timeMS > 0:
                seqTime, seqLine = sequence.advance(timeMS)
                print(timeMS, end=' ')
                print(seqTime, end=' ')
                print(repr(seqLine))
                timeMS -= seqTime
        except seq.SequenceEnded as e:
            sequence.reset()

        lastTime = thisTime
        SDL_RenderPresent(renderer)

    SDL_DestroyRenderer(renderer)
    SDL_DestroyWindow(window)


if __name__ == "__main__":
    main()
