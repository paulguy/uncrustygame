#!/usr/bin/env python3

import copy
from traceback import print_tb
from sys import argv
import time
import array
import random
from math import sqrt, pi, cos, fabs
from itertools import islice, count, repeat
from ctypes import *
from sdl2 import *
import pycrustygame as cg
import sequencer as seq
import audio

DEFAULT_SEQ = "testseq2.txt"
START = 40
SLICES = 2000

TWOPI = 2.0 * pi

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

class LogSlope():
    def __init__(self, start, end, num):
        self._num = num
        self._start = start
        self._range = end - start
        self._val = 0
        self._step = 1.0 / num

    def __len__(self):
        return self._num

    def __iter__(self):
        return self

    def __next__(self):
        val = sqrt(self._val * self._step)
        if self._val == self._num:
            raise StopIteration()
        self._val += 1
        return self._start + (val * self._range)

def create_sqrt_slope(start, end, num):
    slope = array.array('f', LogSlope(start, end, num))
    return(slope)

class RandomNoise():
    def __init__(self, low, high, num):
        self._low = low
        self._high = high
        self._num = num
        self._val = 0

    def __len__(self):
        return self._num

    def __iter__(self):
        return self

    def __next__(self):
        self._val += 1
        if self._val > self._num:
            raise StopIteration()
        return random.uniform(self._low, self._high)

def create_random_noise(low, high, num):
    noise = array.array('f', RandomNoise(low, high, num))
    return(noise)

def create_filter(freqs, amps, cycles, rate, filt=None):
    phase = list()
    step = list()
    maxval = list()
    length = 0.0
    for i in range(len(freqs)):
        phase.append(0.0)
        thislength = rate / freqs[i] * (cycles[i] - 0.25)
        step.append(TWOPI / (rate / freqs[i]))
        maxval.append(cycles[i] * TWOPI)
        if thislength > length:
            length = thislength
    length = int(length)

    if filt != None:
        if len(filt) < length:
            raise ValueError("Filter length less than length needed.")
    else:
        filt = array.array('f', repeat(0.0, length))

    for i in range(length):
        for j in range(len(freqs)):
            if phase[j] >= maxval[j]:
                continue
            else:
                filt[i] += cos(phase[j]) / \
                           (phase[j] / TWOPI + 1.0) * \
                           amps[j]
                phase[j] += step[j]

    return filt, length

def scale_filter(filt, start, count):
    allvals = 0.0
    for i in range(start, start + count):
        allvals += fabs(filt[i])

    for i in range(start, start + count):
        filt[i] /= allvals

def main():
    try:
        seqname = argv[1]
    except IndexError:
        seqname = DEFAULT_SEQ

    random.seed()
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
                          cg.create_float_array(create_sqrt_slope(0.0, 1.0, rate)),
                          rate)
    benddownslope = aud.buffer(cg.SYNTH_TYPE_F32,
                               cg.create_float_array(create_sqrt_slope(1.0, 0.5, rate)),
                               rate)
    bendupslope = aud.buffer(cg.SYNTH_TYPE_F32,
                             cg.create_float_array(create_sqrt_slope(1.0, 2.0, rate)),
                             rate)
    noise = aud.buffer(cg.SYNTH_TYPE_F32,
                       cg.create_float_array(create_random_noise(-1.0, 1.0, rate)),
                       rate)
    filt, flen = \
        create_filter((float(START),), (1.0,), (4,), rate)
    for i in range(1, SLICES - START):
        thisfilt = array.array('f', filt[(i-1)*flen:])
        create_filter((float(START + i) * 8.0,), (1.0,), (4,), rate, thisfilt)
        filt.extend(thisfilt)

    print(filt[(SLICES - START - 1)*flen])
    for i in range(SLICES - START):
        scale_filter(filt, i*flen, flen)
    print(filt[(SLICES - START - 1)*flen])

    #filt = array.array('f', (1.0, 0.0))
    #flen = 2
    #fscale = 1.0
    filt = aud.buffer(cg.SYNTH_TYPE_F32,
                      cg.create_float_array(filt),
                      flen * (SLICES - START))

    aud.enabled(True)

    seq = None
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
                elif event.key.keysym.sym == SDLK_p:
                    if seq != None:
                        aud.del_sequence(seq)
                        seq = None
                    macros = None
                    with open("macros.txt", 'r') as macrofile:
                        macrofile = audio.MacroReader(macrofile)
                        try:
                            macros = audio.read_macros(macrofile)
                        except Exception as e:
                            print("Error reading macros from {} on line {}.".format(macrofile.name, macrofile.curline))
                            print_tb(e.__traceback__)
                            print(e)
                    if macros != None:
                        macros.extend((("FILTER_SIZE", (), str(flen)),
                                       ("FILTER_SLICES", (), str(SLICES - START))))
                        print(macros)
                        aud.enabled(False)
                        try:
                            with open(seqname, "r") as seqfile:
                                seq = audio.AudioSequencer(seqfile,
                                    [envslope, benddownslope, bendupslope, noise, filt],
                                    macros, trace=True)
                        except Exception as e:
                            aud.print_full_stats()
                            print_tb(e.__traceback__)
                            print(e)
                        if seq != None:
                            try:
                                aud.add_sequence(seq, enabled=True)
                            except Exception as e:
                                aud.print_full_stats()
                                print_tb(e.__traceback__)
                                print(e)
                                seq = None
                        aud.enabled(True)
                elif event.key.keysym.sym == SDLK_s:
                    if seq != None:
                        aud.del_sequence(seq)
                        seq = None
                elif event.key.keysym.sym == SDLK_r:
                    aud.enabled(True)
                elif event.key.keysym.sym == SDLK_n:
                    aud.enabled(False)
                elif event.key.keysym.sym == SDLK_i:
                    aud.print_full_stats()

        clear_frame(ll, 32, 128, 192)
        l.draw()
        try:
            aud.frame()
        except Exception as e:
            print("Sequence raised error")
            aud.print_full_stats()
            aud.del_sequence(seq)
            seq = None
            _, exc = aud.error
            print_tb(exc.__traceback__)
            print(exc)
            aud.enabled(True)

        thisTime = time.monotonic()
        if seq != None and seq.ended:
            aud.del_sequence(seq)
            seq = None
            print("Sequence ended")

        lastTime = thisTime
        SDL_RenderPresent(renderer)

    aud.enabled(False)
    if seq != None:
        aud.del_sequence(seq)
    SDL_DestroyRenderer(renderer)
    SDL_DestroyWindow(window)


if __name__ == "__main__":
    main()
