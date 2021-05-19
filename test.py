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

# this is probably bad but whichever
def string_to_uint(string):
    array = list()

    for item in string:
        encoded = item.encode("utf-32")
        array.append(encoded[4] +
                     (encoded[5] * 0x100) +
                     (encoded[6] * 0x10000) +
                     (encoded[7] * 0x1000000))

    return(array)

def driver_key(info):
    info = info[1]
    # everything else is in between
    priority = 2
    if bytes(info.name) == b'metal' or \
       bytes(info.name) == b'direct3d11':
        # prefer platform-specific APIs
        priority = 0
    elif bytes(info.name).startswith(b'opengles'):
        # prefer opengl es over opengl because it has complete support for the
        # uncrustygame features
        priority = 1
    elif info.flags & SDL_RENDERER_SOFTWARE:
        # software will be very slow so don't prefer it, but it should display
        # _mostly_ OK
        priority = 9998

    found_32bit_alpha = 0
    for i in range(info.num_texture_formats):
        if SDL_BITSPERPIXEL(info.texture_formats[i]) == 32 and \
           SDL_ISPIXELFORMAT_ALPHA(info.texture_formats[i]):
               found_32bit_alpha = 1
               break

    if found_32bit_alpha == 0:
        # if something is missing the necessary formats, it's very unpreferable
        # because there's little to no chance anything will display properly
        priority = 9999

    return(priority)

def initialize_video(title, width, height, winflags, rendererflags):
    driver = list()
    pixfmt = SDL_PIXELFORMAT_UNKNOWN
    drivers = SDL_GetNumRenderDrivers()

    for i in range(drivers):
        d = SDL_RendererInfo()
        if SDL_GetRenderDriverInfo(i, d) < 0:
            raise Exception()
        driver.append((i, d))

    driver = sorted(driver, key=driver_key)

    window = SDL_CreateWindow(title.encode("utf-8"), SDL_WINDOWPOS_UNDEFINED, SDL_WINDOWPOS_UNDEFINED, width, height, winflags)
    if window == None:
        raise Exception()

    renderer = None
    for d in driver:
        renderer = SDL_CreateRenderer(window, d[0], rendererflags)
        # if initialization failed, continue down the priority list
        if renderer == None:
            continue

        pixfmt = SDL_PIXELFORMAT_UNKNOWN
        # find the most prefered format
        for i in range(d[1].num_texture_formats):
            if SDL_BITSPERPIXEL(d[1].texture_formats[i]) == 32 and \
               SDL_ISPIXELFORMAT_ALPHA(d[1].texture_formats[i]):
                pixfmt = d[1].texture_formats[i]
                break

        # otherwise, try to find something with the most color depth
        if pixfmt == SDL_PIXELFORMAT_UNKNOWN:
            maxbpp = 0
            for i in range(d[1].num_texture_formats):
                if SDL_BITSPERPIXEL(d[1].texture_formats[i]) > maxbpp:
                    maxbpp = SDL_BITSPERPIXEL(d[1].texture_formats[i])
                    pixfmt = d[1].texture_formats[i]

        break

    if renderer == None:
        SDL_DestroyWindow(window)
        raise Exception()

    return(window, renderer, pixfmt)


def main():
    window, renderer, pixfmt = initialize_video("asdf", 640, 480, SDL_WINDOW_SHOWN, SDL_RENDERER_PRESENTVSYNC)
    red = cg.tilemap_color(255, 0, 0, 255)
    green = cg.tilemap_color(0, 255, 0, 255)
    blue = cg.tilemap_color(0, 0, 255, 255)

    ll = cg.Layerlist(renderer, pixfmt, log_cb_return)
    ts = ll.tileset_from_bmp("cdemo/font.bmp", 8, 8)
    tm = ll.tilemap(ts, 8, 8)
    tm.map(2, 2, 4, 4, 3, string_to_uint("thisis atest"))
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

    SDL_DestroyRenderer(renderer)
    SDL_DestroyWindow(window)


if __name__ == "__main__":
    main()
