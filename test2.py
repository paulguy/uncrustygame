from sdl2 import *
import crustygame as cg
import array
import time
import random
import math

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

        print("Picked {} renderer".format(d[1].name.decode("utf-8")))
        break

    if renderer == None:
        SDL_DestroyWindow(window)
        raise RuntimeError("Couldn't initialze any SDL video device.")

    return window, renderer, pixfmt


def clear_frame(ll, r, g, b):
    if SDL_SetRenderDrawColor(ll.renderer, r, g, b, SDL_ALPHA_OPAQUE) < 0:
        raise(Exception())
    if SDL_RenderClear(ll.renderer) < 0:
        raise(Exception())
    if SDL_SetRenderDrawColor(ll.renderer, 0, 0, 0, SDL_ALPHA_TRANSPARENT) < 0:
        raise(Exception())

def make_color(r, g, b, a):
    return((int(r) << cg.TILEMAP_RSHIFT) |
           (int(g) << cg.TILEMAP_GSHIFT) |
           (int(b) << cg.TILEMAP_BSHIFT) |
           (int(a) << cg.TILEMAP_ASHIFT))

def color_from_rad(rad, cmin, cmax):
    if rad >= 0 and rad < (math.pi * 2 / 6):
        rad = (rad * (1 / (math.pi * 2 / 6)) * (cmax - cmin)) + cmin
        return make_color(cmax, rad, cmin, 255)
    elif rad >= (math.pi * 2 / 6) and rad < (math.pi * 2 / 6 * 2):
        rad = cmax - ((rad - (math.pi * 2 / 6)) * (1 / (math.pi * 2 / 6)) * (cmax - cmin))
        return make_color(rad, cmax, cmin, 255)
    elif rad >= (math.pi * 2 / 6 * 2) and rad < (math.pi * 2 / 6 * 3):
        rad = ((rad - (math.pi * 2 / 6 * 2)) * (1 / (math.pi * 2 / 6)) * (cmax - cmin)) + cmin
        return make_color(cmin, cmax, rad, 255)
    elif rad >= (math.pi * 2 / 6 * 3) and rad < (math.pi * 2 / 6 * 4):
        rad = cmax - ((rad - (math.pi * 2 / 6 * 3)) * (1 / (math.pi * 2 / 6)) * (cmax - cmin))
        return make_color(cmin, rad, cmax, 255)
    elif rad >= (math.pi * 2 / 6 * 4) and rad < (math.pi * 2 / 6 * 5):
        rad = ((rad - (math.pi * 2 / 6 * 4)) * (1 / (math.pi * 2 / 6)) * (cmax - cmin)) + cmin
        return make_color(rad, cmin, cmax, 255)

    rad = cmax - ((rad - (math.pi * 2 / 6 * 5)) * (1 / (math.pi * 2 / 6)) * (cmax - cmin))
    return make_color(cmax, cmin, rad, 255)

def log_cb_return(string, priv):
    print("tilemap.h output, ignore: {}".format(string), end='')

def main():
    SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO)
    window, renderer, pixfmt = initialize_video("asdf", 640, 480, SDL_WINDOW_SHOWN, SDL_RENDERER_PRESENTVSYNC | SDL_RENDERER_TARGETTEXTURE)
    sdlfmt = SDL_AllocFormat(pixfmt)
    sdl_red = SDL_MapRGBA(sdlfmt, 255, 0, 0, 255)
    sdl_green = SDL_MapRGBA(sdlfmt, 0, 255, 0, 255)
    sdl_blue = SDL_MapRGBA(sdlfmt, 0, 0, 255, 255)
    red = make_color(255, 31, 31, 255)
    green = make_color(31, 255, 31, 255)
    blue = make_color(127, 127, 255, 255)
    transparent_rg = SDL_MapRGBA(sdlfmt, 255, 255, 63, 191)
    ll = cg.LayerList(renderer, pixfmt, log_cb_return, None)

    if ll.renderer != renderer:
        print("Got different renderer back from layerlist")

    ts1 = cg.Tileset(ll, 32, 32, sdl_blue, 16, 16)
    ts2 = cg.Tileset(ll, "cdemo/font.bmp", 8, 8)
    surface = SDL_CreateRGBSurfaceWithFormat(0, 64, 64, 32, pixfmt)
    ts3 = cg.Tileset(ll, surface, 64, 64)
    SDL_FreeSurface(surface)

    try:
        ll.target_tileset(window)
        print("set_target_tileset didn't raise TypeError as expected")
    except TypeError:
        pass

    try:
        ll.target_tileset(0)
        print("set_target_tileset didn't raise TypeError as expected")
    except TypeError:
        pass

    ll.target_tileset(ts1);
    ll.target_tileset(ts2);
    ll.target_tileset(ts3);
    ll.target_tileset(None);

    try:
        ll.default_render_target(window)
        print("set_default_render_target didn't raise TypeError as expected")
    except TypeError:
        pass

    tm1 = cg.Tilemap(ll, ts1, 4, 4)
    tm1.tileset(ts2)
    SDL_RenderPresent(renderer)

    del tm1
    del ts3
    del ts2
    del ts1

    ts1 = ll.Tileset("cdemo/font.bmp", 8, 8)
    tm1 = ll.Tilemap(ts1, 8, 8)
    tm1.map(2, 2, 5, 5, 2, array.array('u', "oediV DVD "))
    tm1.attr_flags(2, 2, 0, 5, 2, array.array('I', (cg.TILEMAP_ROTATE_180, cg.TILEMAP_ROTATE_180, cg.TILEMAP_ROTATE_180, cg.TILEMAP_ROTATE_180, cg.TILEMAP_ROTATE_180)))
    tm1.attr_colormod(2, 2, 4, 5, 2, array.array('I', (red, green, blue, red, green, blue, red, green, blue, red)))
    tm1.update(0, 0, 8, 8)
    l1 = cg.Layer(ll, tm1);
    l1.window(40, 16)
    l1.scroll_pos(16, 16)
    l1.rotation_center(20, 8)
    l1.rotation(180)
    l1.colormod(transparent_rg)
    l1.blendmode(cg.TILEMAP_BLENDMODE_ADD)
    ts2 = ll.Tileset(64, 64, sdl_blue, 64, 64)
    tm2 = ts2.Tilemap(1, 1)
    l2 = tm2.Layer()
    l2.scale(4.0, 4.0)

    random.seed(None)

    x = 0.0
    y = 0.0
    x2 = -20.0
    y2 = -8.0
    xspeed = random.uniform(0.0, 480.0)
    yspeed = random.uniform(0.0, 480.0)
    x2speed = random.uniform(0.0, 64.0)
    y2speed = random.uniform(0.0, 64.0)
    blendmode = cg.TILEMAP_BLENDMODE_ADD
    colorrad = 0.0

    running = True
    lastTime = time.monotonic()
    while running:
        event = SDL_Event()

        while SDL_PollEvent(event):
            if event.type == SDL_QUIT or event.type == SDL_KEYDOWN:
                running = False

        thisTime = time.monotonic()
        timetaken = thisTime - lastTime
        x = x + (xspeed * timetaken)
        if x > (640 - (64 * 4.0)):
            xspeed = random.uniform(-480.0, 0.0)
            if yspeed > 0.0:
                yspeed = random.uniform(0.0, 480.0)
            else:
                yspeed = random.uniform(-480.0, 0.0)
            x = 640 - (64 * 4.0)
        elif x < 0:
            xspeed = random.uniform(0.0, 480.0)
            if yspeed > 0.0:
                yspeed = random.uniform(0.0, 480.0)
            else:
                yspeed = random.uniform(-480.0, 0.0)
            x = 0

        y = y + (yspeed * timetaken)
        if y > (480 - (64 * 4.0)):
            y = 480 - (64 * 4.0)
            yspeed = random.uniform(-480.0, 0.0)
            if xspeed > 0.0:
                xspeed = random.uniform(0.0, 480.0)
            else:
                xspeed = random.uniform(-480.0, 0.0)
            y = 480 - (64 * 4.0)
        elif y < 0:
            yspeed = random.uniform(0.0, 480.0)
            if xspeed > 0.0:
                xspeed = random.uniform(0.0, 480.0)
            else:
                xspeed = random.uniform(-480.0, 0.0)
            y = 0

        x2 = x2 + (x2speed * timetaken)
        if x2 > 64 - 20:
            x2speed = random.uniform(-64.0, 0.0)
            if y2speed > 0.0:
                y2speed = random.uniform(0.0, 64.0)
            else:
                y2speed = random.uniform(-64.0, 0.0)
            x2 = 64 - 20
            if blendmode == cg.TILEMAP_BLENDMODE_ADD:
                blendmode = cg.TILEMAP_BLENDMODE_SUB
            else:
                blendmode = cg.TILEMAP_BLENDMODE_ADD
            l1.blendmode(blendmode)
        elif x2 < -20:
            x2speed = random.uniform(0.0, 64.0)
            if y2speed > 0.0:
                y2speed = random.uniform(0.0, 64.0)
            else:
                y2speed = random.uniform(-64.0, 0.0)
            x2 = -20
            if blendmode == cg.TILEMAP_BLENDMODE_ADD:
                blendmode = cg.TILEMAP_BLENDMODE_SUB
            else:
                blendmode = cg.TILEMAP_BLENDMODE_ADD
            l1.blendmode(blendmode)

        y2 = y2 + (y2speed * timetaken)
        if y2 > 64 - 8:
            y2speed = random.uniform(-64.0, 0.0)
            if x2speed > 0.0:
                x2speed = random.uniform(0.0, 64.0)
            else:
                x2speed = random.uniform(-64.0, 0.0)
            y2 = 64 - 8
            if blendmode == cg.TILEMAP_BLENDMODE_ADD:
                blendmode = cg.TILEMAP_BLENDMODE_SUB
            else:
                blendmode = cg.TILEMAP_BLENDMODE_ADD
            l1.blendmode(blendmode)
        elif y2 < -8:
            y2speed = random.uniform(0.0, 64.0)
            if x2speed > 0.0:
                x2speed = random.uniform(0.0, 64.0)
            else:
                x2speed = random.uniform(-64.0, 0.0)
            y2 = -8
            if blendmode == cg.TILEMAP_BLENDMODE_ADD:
                blendmode = cg.TILEMAP_BLENDMODE_SUB
            else:
                blendmode = cg.TILEMAP_BLENDMODE_ADD
            l1.blendmode(blendmode)

        if xspeed == 0.0 and yspeed == 0.0:
            xspeed = random.uniform(-480.0, 480.0)
            yspeed = random.uniform(-480.0, 480.0)

        if x2speed == 0.0 and y2speed == 0.0:
            x2speed = random.uniform(-64.0, 64.0)
            y2speed = random.uniform(-64.0, 64.0)

        colorrad = colorrad + (math.pi * timetaken)
        if colorrad >= math.pi * 2:
            colorrad = colorrad - (math.pi * 2)
        l1.colormod(color_from_rad(colorrad, 0, 255))

        clear_frame(ll, 32, 128, 192)
        l1.pos(int(x2), int(y2))
        l2.pos(int(x), int(y))
        ll.target_tileset(ts2)
        l1.draw()
        ll.target_tileset(None)
        tm2.update(0, 0, 1, 1)
        l2.draw()
        SDL_RenderPresent(renderer)

        lastTime = thisTime
 
    SDL_DestroyRenderer(renderer)
    SDL_DestroyWindow(window)
    SDL_Quit()

    print("If no other errors other than those said to ignore, then tests passed.")

if __name__ == "__main__":
    main()
