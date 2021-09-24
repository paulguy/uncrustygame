import sdl2
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
    elif info.flags & sdl2.SDL_RENDERER_SOFTWARE:
        # software will be very slow so don't prefer it, but it should display
        # _mostly_ OK
        priority = 9998

    found_32bit_alpha = 0
    for i in range(info.num_texture_formats):
        if sdl2.SDL_BITSPERPIXEL(info.texture_formats[i]) == 32 and \
           sdl2.SDL_ISPIXELFORMAT_ALPHA(info.texture_formats[i]):
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
                     -> (sdl2.SDL_Window, sdl2.SDL_Renderer, int):
    """
    Initialize video in a way that as far as I can tell is the best, preferred 
    method to get the best functionality out of pycrustygame.

    title, width, height and winflags are simply passed on to SDL_CreateWindow
    rendererflags is passed on to SDL_CreateRenderer
    returns window, renderer and prefered pixel format or raises RuntimeError if
    no window or renderer could be created
    """
    driver = list()
    pixfmt = sdl2.SDL_PIXELFORMAT_UNKNOWN
    drivers = sdl2.SDL_GetNumRenderDrivers()

    for i in range(drivers):
        d = sdl2.SDL_RendererInfo()
        if sdl2.SDL_GetRenderDriverInfo(i, d) < 0:
            raise RuntimeError("Couldn't get video renderer info for {}".format(i))
        driver.append((i, d))

    driver = sorted(driver, key=_driver_key)

    window = sdl2.SDL_CreateWindow(title.encode("utf-8"), sdl2.SDL_WINDOWPOS_UNDEFINED, sdl2.SDL_WINDOWPOS_UNDEFINED, width, height, winflags)
    if window == None:
        raise RuntimeError("Couldn't create SDL window.")

    renderer = None
    for d in driver:
        renderer = sdl2.SDL_CreateRenderer(window, d[0], rendererflags)
        # if initialization failed, continue down the priority list
        if renderer == None:
            continue

        pixfmt = sdl2.SDL_PIXELFORMAT_UNKNOWN
        # find the most prefered format
        for i in range(d[1].num_texture_formats):
            if sdl2.SDL_BITSPERPIXEL(d[1].texture_formats[i]) == 32 and \
               sdl2.SDL_ISPIXELFORMAT_ALPHA(d[1].texture_formats[i]):
                pixfmt = d[1].texture_formats[i]
                break

        # otherwise, try to find something with the most color depth, although
        # it's pretty likely to just fail.
        if pixfmt == sdl2.SDL_PIXELFORMAT_UNKNOWN:
            maxbpp = 0
            for i in range(d[1].num_texture_formats):
                if sdl2.SDL_BITSPERPIXEL(d[1].texture_formats[i]) > maxbpp:
                    maxbpp = sdl2.SDL_BITSPERPIXEL(d[1].texture_formats[i])
                    pixfmt = d[1].texture_formats[i]

        break

    if renderer == None:
        sdl2.SDL_DestroyWindow(window)
        raise RuntimeError("Couldn't initialze any SDL video device.")

    return window, renderer, pixfmt


def log_cb_return(string, priv):
    print(priv)
    print(string, end='')

def main():
    sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO | sdl2.SDL_INIT_AUDIO)
    window, renderer, pixfmt = initialize_video("asdf", 640, 480, sdl2.SDL_WINDOW_SHOWN, sdl2.SDL_RENDERER_PRESENTVSYNC)
    print(type(renderer))
    print(sdl2.render.LP_SDL_Renderer)
    ll = cg.LayerList(renderer, pixfmt, log_cb_return, "test")

    ll.target_tileset(0)

    del ll
    sdl2.SDL_Quit()

if __name__ == "__main__":
    main()
