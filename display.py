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
                     winflags :int, rendererflags :int,
                     batching=True) \
                     -> (SDL_Window, SDL_Renderer, int):
    """
    Initialize video in a way that as far as I can tell is the best, preferred 
    method to get the best functionality out of pycrustygame.

    title, width, height and winflags are simply passed on to SDL_CreateWindow
    rendererflags is passed on to SDL_CreateRenderer
    returns window, renderer and prefered pixel format or raises RuntimeError if
    no window or renderer could be created
    """
    if batching:
        # According to documentation, setting the render backend explicitly
        # will disable batching by default, so reenable it if it's requested
        # specifically.
        if SDL_SetHint(SDL_HINT_RENDER_BATCHING, b'1') != SDL_TRUE:
            print("WARNING: Failed to set SDL_HINT_RENDER_BATCHING.")

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
           not isinstance(item, (cg.Layer, int)) and \
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

    def _print_dest(dest, pfx, depth):
        if dest is None:
            print('{:><{}}{}: No Change'.format('', depth, pfx))
        elif dest is SCREEN:
            print('{:><{}}{}: Screen'.format('', depth, pfx))
        elif isinstance(dest, POINTER(SDL_Texture)):
            print('{:><{}}{}: SDL_Texture'.format('', depth, pfx))
        elif isinstance(dest, cg.Tileset):
            print('{:><{}}{}: {}'.format('', depth, pfx, dest.name()))

    def draw(self, restore, trace=False, depth=0):
        if trace:
            DisplayList._print_dest(self._dest, 'Destination', depth)

        if self._dest != restore:
            self._setdest()

        for item in self._list:
            if callable(item):
                if trace:
                    print('{:><{}}callable'.format('', depth))
                item()
            elif isinstance(item, DisplayList):
                if trace:
                    print('{:><{}}DisplayList'.format('', depth))
                if self._dest == None:
                    item.draw(restore, trace, depth+1)
                else:
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

        if self._dest != restore:
            if trace:
                DisplayList._print_dest(restore, "Restoring", depth)
            setdest(self._ll, restore)

class ScrollingTilemap():
    NOSCROLL_X = 1 << 0
    NOSCROLL_Y = 1 << 1

    def __init__(self, tileset, tilemap, linewidth, width, height, twidth, theight, startx = 0, starty = 0, noscroll = 0, flags=None, colormod=None):
        if noscroll & (ScrollingTilemap.NOSCROLL_X | \
                       ScrollingTilemap.NOSCROLL_Y):
            raise ValueError("Scrolling must be allowed in some direction.")
        self._tilemap = tilemap
        self._flags = flags
        self._colormod = colormod
        self._linewidth = linewidth
        self._twidth = twidth
        self._theight = theight
        self._tmw = int(width / twidth)
        if width % twidth > 0:
            self._tmw += 1
        if not noscroll & ScrollingTilemap.NOSCROLL_X:
            self._tmw += 1
        self._tmh = int(height / theight)
        if height % theight > 0:
            self._tmh += 1
        if not noscroll & ScrollingTilemap.NOSCROLL_Y:
            self._tmh += 1
        self._tm = tileset.tilemap(self._tmw, self._tmh, "Scrolling Tilemap {}".format(tileset.name()))
        # don't bother sanity checking the buffer, just try to update it which
        # should do all the sanity checking. :p
        self._setmap(startx, starty)
        self._l = self._tm.layer("Scrolling Layer {}".format(tileset.name()))
        self._l.window(width, height)
        self._x = startx
        self._y = starty
        self._newx = startx
        self._newy = starty

    @property
    def layer(self):
        return self._l

    def _setmap(self, x, y, tmx=0, tmy=0, w=0, h=0):
        self._tm.map(tmx, tmy, self._linewidth, w, h, self._tilemap[y * self._linewidth + x:])
        if self._flags is not None:
            self._tm.attr_flags(tmx, tmy, self._linewidth, w, h, self._flags[y * self._linewidth + x:])
        if self._colormod is not None:
            self._tm.attr_colormod(tmx, tmy, self._linewidth, w, h, self._colormod[y * self._linewidth + x:])
        self._tm.update(tmx, tmy, w, h)

    def scroll(self, x, y):
        self._newx = x
        self._newy = y

    def update(self):
        if int(self._x / self._twidth)  != int(self._newx / self._twidth) or \
           int(self._y / self._theight) != int(self._newy / self._theight):
            self._setmap(int(self._newx / self._twidth), \
                        int(self._newy / self._theight))
        self._l.scroll_pos(int(self._newx % self._twidth), \
                           int(self._newy % self._theight))
        self._x = self._newx
        self._y = self._newy

    def updateregion(self, x, y, w, h):
        tmx = x
        tmy = y
        if tmx < self._x:
            if tmx + w > self._x + self._tmw:
                tmx = 0
                w = self._tmw
            elif tmx + w > self._x:
                tmx = 0
                w = (tmx + w) - self._x
            else:
                return
        else:
            if tmx >= self._x + self._tmw:
                return
            else:
                tmx = tmx - self._x
                w = (self._x + self._tmw) - (tmx + w)
        if tmy < self._y:
            if tmy + h > self._y + self._tmh:
                tmy = 0
                h = self._tmh
            elif tmy + h > self._y:
                tmy = 0
                h = (tmy + h) - self._y
            else:
                return
        else:
            if tmy >= self._y + self._tmh:
                return
            else:
                tmy = tmy - self._y
                h = (self._y + self._tmh) - (tmy + h)
        self._setmap(x, y, tmx, tmy, w, h)
