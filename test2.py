from sdl2 import *
import crustygame as cg

def _driver_key(info):
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

    return priority


def initialize_video(title :str,
                     width :int, height :int,
                     winflags :int, rendererflags :int) \
                     -> (SDL_Window, SDL_Renderer, int):
    """
    Initialize video in a way that as far as I can tell is the best, preferred 
    method to get the best functionality out of pycrustygame.

    title, width, height and winflags are simply passed on to SDL_CreateWindow
    rendererflags is passed on to SDL_CreateRenderer
    returns window, renderer and prefered pixel format or raises RuntimeError if
    no window or renderer could be created
    """
    driver = list()
    pixfmt = SDL_PIXELFORMAT_UNKNOWN
    drivers = SDL_GetNumRenderDrivers()

    for i in range(drivers):
        d = SDL_RendererInfo()
        if SDL_GetRenderDriverInfo(i, d) < 0:
            raise RuntimeError("Couldn't get video renderer info for {}".format(i))
        driver.append((i, d))

    driver = sorted(driver, key=_driver_key)

    window = SDL_CreateWindow(title.encode("utf-8"), SDL_WINDOWPOS_UNDEFINED, SDL_WINDOWPOS_UNDEFINED, width, height, winflags)
    if window == None:
        raise RuntimeError("Couldn't create SDL window.")

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

        # otherwise, try to find something with the most color depth, although
        # it's pretty likely to just fail.
        if pixfmt == SDL_PIXELFORMAT_UNKNOWN:
            maxbpp = 0
            for i in range(d[1].num_texture_formats):
                if SDL_BITSPERPIXEL(d[1].texture_formats[i]) > maxbpp:
                    maxbpp = SDL_BITSPERPIXEL(d[1].texture_formats[i])
                    pixfmt = d[1].texture_formats[i]

        break

    if renderer == None:
        SDL_DestroyWindow(window)
        raise RuntimeError("Couldn't initialze any SDL video device.")

    return window, renderer, pixfmt


def log_cb_return(string, priv):
    print("tilemap.h output, ignore: {}".format(string), end='')

def main():
    SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO)
    window, renderer, pixfmt = initialize_video("asdf", 640, 480, SDL_WINDOW_SHOWN, SDL_RENDERER_PRESENTVSYNC)
    ll = cg.LayerList(renderer, pixfmt, log_cb_return, None)

    try:
        ll.set_target_tileset(window)
        print("set_target_tileset didn't raise TypeError as expected")
    except TypeError:
        pass

    try:
        ll.set_target_tileset(0)
        print("set_target_tileset didn't raise CrustyException as expected")
    except cg.CrustyException:
        pass

    try:
        ll.set_default_render_target(window)
        print("set_default_render_target didn't raise TypeError as expected")
    except TypeError:
        pass

    if ll.renderer != renderer:
        print("Got different renderer back from layerlist")

    SDL_Quit()

    print("If no other errors other than those said to ignore, then tests passed.")

if __name__ == "__main__":
    main()
