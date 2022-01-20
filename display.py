from ctypes import POINTER
from sdl2 import *
import crustygame as cg

SCREEN = object()

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

def make_color(r, g, b, a):
    return((int(r) << cg.TILEMAP_RSHIFT) |
           (int(g) << cg.TILEMAP_GSHIFT) |
           (int(b) << cg.TILEMAP_BSHIFT) |
           (int(a) << cg.TILEMAP_ASHIFT))

def unmake_color(color):
    return (int(color) & cg.TILEMAP_RMASK) >> cg.TILEMAP_RSHIFT, \
           (int(color) & cg.TILEMAP_GMASK) >> cg.TILEMAP_GSHIFT, \
           (int(color) & cg.TILEMAP_BMASK) >> cg.TILEMAP_BSHIFT, \
           (int(color) & cg.TILEMAP_AMASK) >> cg.TILEMAP_ASHIFT

def setdest(ll, dest):
    if isinstance(dest, cg.Tileset):
        ll.target_tileset(dest)
    elif isinstance(dest, POINTER(SDL_Texture)):
        ll.default_render_target(dest)
        ll.target_tileset(None)
    elif dest is SCREEN:
        ll.default_render_target(None)
        ll.target_tileset(None)
    # None should do nothing

def clear(ll, tex, r, g, b, a):
    if tex == SCREEN:
        realtex = None
    else:
        realtex = tex
    orig = SDL_GetRenderTarget(ll.renderer)
    if tex is not None and realtex != orig:
        if SDL_SetRenderTarget(ll.renderer, realtex) < 0:
            raise Exception("Failed to set render target")
    if SDL_SetRenderDrawColor(ll.renderer, r, g, b, a) < 0:
        raise Exception("Failed to set render draw color.")
    if SDL_RenderClear(ll.renderer) < 0:
        raise Exception("Failed to clear.")
    if tex is not None and realtex != orig:
        if SDL_SetRenderTarget(ll.renderer, orig) < 0:
            raise Exception("Failed to restore render target")

class DisplayList():
    def setdest(self, dest):
        if dest is not None and dest is not SCREEN and \
           not isinstance(dest, (POINTER(SDL_Texture), cg.Tileset)):
            raise TypeError("dest must be None or a SDL_Texture or Tileset")
        self._dest = dest

    def __init__(self, ll, dest):
        self._ll = ll
        self.setdest(dest)
        self._list = []
        self._ref = False

    def _checkitem(item):
        if isinstance(item, DisplayList):
            if item._ref == True:
                raise ValueError("DisplayList is already referenced")
            item._ref = True
        elif item is not None and \
           not isinstance(item, (cg.Layer, int)) and\
           not callable(item):
            raise TypeError("item must be DisplayList or Layer or int or None")

    def append(self, item):
        DisplayList._checkitem(item)
        self._list.append(item)
        return(len(self._list) - 1)

    def replace(self, num, item):
        if isinstance(self._list[num], DisplayList):
            self._list[num]._ref = False
        DisplayList._checkitem(item)
        self._list[num] = item

    def remove(self, num):
        if isinstance(self._list[num], DisplayList):
            self._list[num]._ref = False
        del self._list[num]

    def _setdest(self):
        setdest(self._ll, self._dest)

    def draw(self, restore, trace=False, depth=0):
        if restore != None and self._dest != restore:
            self._setdest()

        for item in self._list:
            if callable(item):
                if trace:
                    print('{:><{}}callable'.format('', depth))
                item()
            elif isinstance(item, DisplayList):
                if trace:
                    print('{:><{}}DisplayList'.format('', depth))
                item.draw(self._dest, trace, depth+1)
            elif isinstance(item, cg.Layer):
                if trace:
                    print('{:><{}}{}'.format('', depth, item.name()))
                item.draw()
            elif isinstance(item, int):
                r, g, b, a = unmake_color(item)
                if trace:
                    print('{:><{}}{} -> {} {} {} {}'.format('', depth, hex(item), r, g, b, a))
                clear(self._ll, None, r, g, b, a)

        if restore != None and self._dest != restore:
            setdest(self._ll, restore)
