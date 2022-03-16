from ctypes import POINTER
from sdl2 import *
import crustygame as cg
from dataclasses import dataclass

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

def make_attrib(hflip, vflip, rotate):
    return hflip | vflip | rotate

def unmake_attrib(attrib):
    return attrib & cg.TILEMAP_HFLIP_MASK, \
           attrib & cg.TILEMAP_VFLIP_MASK, \
           attrib & cg.TILEMAP_ROTATE_MASK

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

def fill(ll, tex, r, g, b, a, x, y, w, h):
    rect = SDL_Rect(x, y, w, h)
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
    if SDL_RenderFillColor(ll.renderer, rect) < 0:
        raise Exception("Failed to fill.")
    if tex is not None and realtex != orig:
        if SDL_SetRenderTarget(ll.renderer, orig) < 0:
            raise Exception("Failed to restore render target")

@dataclass
class RenderZone():
    window : SDL_Point = None
    scroll : SDL_Point = None
    pos : SDL_Point = None
    scale : SDL_FPoint = None
    rotation_center : SDL_FPoint = None
    rotation : float = None
    colormod : int = None
    blendmode : int = None

@dataclass
class Renderable():
    obj : ('DisplayList', cg.Layer, int, None)
    always : bool = True
    zone : list = None

class DisplayList():
    def setdest(self, dest):
        if dest is not None and dest is not SCREEN and \
           not isinstance(dest, (POINTER(SDL_Texture), cg.Tileset)):
            raise TypeError("dest must be None or a SDL_Texture or Tileset")
        self._dest = dest

    def __init__(self, ll, dest=None):
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
           not isinstance(item, (Renderable, cg.Layer, int)) and \
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

    def draw(self, restore, trace=False, depth=0, full=True):
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
            elif isinstance(item, Renderable):
                if item.always:
                    if trace:
                        print('{:><{}}Renderable (always)'.format('', depth))
                else:
                    if trace:
                        print('{:><{}}Renderable (not always)'.format('', depth))
                    if not full:
                        continue
                if callable(item.obj):
                    item.obj()
                elif isinstance(item.obj, cg.Layer):
                    if item.zone is not None:
                        for zone in item.zone:
                            if zone.window is not None:
                                item.obj.window(zone.window.x, zone.window.y)
                            if zone.scroll is not None:
                                item.obj.window(zone.scroll.x, zone.scroll.y)
                            if zone.pos is not None:
                                item.obj.pos(zone.pos.x, zone.pos.y)
                            if zone.scale is not None:
                                item.obj.scale(zone.scale.x, zone.scale.y)
                            if zone.rotation_center is not None:
                                item.obj.rotation_center(zone.rotation_center.x, zone.rotation_center.y)
                            if zone.rotation is not None:
                                item.obj.rotation(zone.rotation)
                            if zone.colormod is not None:
                                item.obj.colormod(zone.colormod)
                            if zone.blendmode is not None:
                                item.obj.blendmode(zone.blendmode)
                            item.obj.draw()
                    else:
                        item.obj.draw()
                elif isinstance(item.obj, int):
                    r, g, b, a = unmake_color(item.obj)
                    if item.zone is not None:
                        for zone in item.zone:
                            fill(self._ll, None, r, g, b, a,
                                 item.zone.pos.x, item.zone.pos.y,
                                 item.zone.window.x, item.zone.window.y)
                    else:
                        clear(self._ll, None, r, g, b, a)
                elif isinstance(item.obj, DisplayList):
                    if self._dest == None:
                        item.obj.draw(restore, trace, depth+1)
                    else:
                        item.obj.draw(self._dest, trace, depth+1)

        if self._dest != restore:
            if trace:
                DisplayList._print_dest(restore, "Restoring", depth)
            setdest(self._ll, restore)

class ScrollingTilemap():
    NOSCROLL_X = 1 << 0
    NOSCROLL_Y = 1 << 1

    def __init__(self, ll, tileset, tilemap, vw, vh, mw, mh, flags=None, colormod=None, optimize=False, debug=False):
        noscroll = 0
        if vw == mw:
            noscroll |= ScrollingTilemap.NOSCROLL_X
        if vh == mh:
            noscroll |= ScrollingTilemap.NOSCROLL_Y
        if debug and \
           (noscroll & (ScrollingTilemap.NOSCROLL_X | \
                        ScrollingTilemap.NOSCROLL_Y)) == \
           (ScrollingTilemap.NOSCROLL_X |
            ScrollingTilemap.NOSCROLL_Y):
            print("WARNING: No scroll in either direction, suggest using a normal tilemap.")
        self._tilemap = tilemap
        self._tw = tileset.width()
        self._th = tileset.height()
        self._flags = flags
        self._colormod = colormod
        self._optimize = optimize
        self._mw = int(mw)
        self._mh = int(mh)
        self._vw = int(vw)
        self._vh = int(vh)
        self._vmw = self._vw
        self._vmh = self._vh
        if not noscroll & ScrollingTilemap.NOSCROLL_X:
            self._vmw += 1
        if not noscroll & ScrollingTilemap.NOSCROLL_Y:
            self._vmh += 1
        self._tm = tileset.tilemap(self._vmw, self._vmh, "{}x{} Scrolling Tilemap {}".format(self._vmw, self._vmh, tileset.name()))
        self._l = self._tm.layer("{}x{} Scrolling Layer {}".format(self._vw, self._vh, tileset.name()))
        self._ref = cg.Layer(ll, None, "{}x{} Scrolling Relative Layer {}".format(self._vw, self._vh, tileset.name()))
        self._l.relative(self._ref)
        self.scroll(0, 0)
        self._vmx = self._newx
        self._vmy = self._newy
        # don't bother sanity checking the buffer, just try to update it which
        # should do all the sanity checking. :p
        self.update(force=True)
        self._l.window(self._vw * self._tw, self._vh * self._th)

    @property
    def layer(self):
        return self._ref

    def optimize(self, val):
        self._optimize = not not val

    def scroll(self, x, y):
        self._newx = int(x)
        self._newy = int(y)

    def _setmap(self, x, y, vmx=0, vmy=0, w=0, h=0):
        self._tm.map(vmx, vmy, self._mw, w, h, self._tilemap[y * self._mw + x:])
        if self._flags is not None:
            self._tm.attr_flags(vmx, vmy, self._mw, w, h, self._flags[y * self._mw + x:])
        if self._colormod is not None:
            self._tm.attr_colormod(vmx, vmy, self._mw, w, h, self._colormod[y * self._mw + x:])
        self._tm.update(vmx, vmy, w, h)

    def update(self, force=False):
        if self._newx + (self._vw * self._tw) <= 0 or \
           self._newx > self._mw * self._tw - 1 or \
           self._newy + (self._vh * self._th) <= 0 or \
           self._newy > self._mh * self._th - 1:
            self._draw = False
            return
        else:
            self._draw = True
        nx = self._newx // self._tw
        ny = self._newy // self._th
        ox = self._vmx
        oy = self._vmy
        if nx < 0:
            nx = 0
        if ny < 0:
            ny = 0
        if nx + self._vmw > self._mw:
            nx = self._mw - self._vmw
        if ny + self._vmh > self._mh:
            ny = self._mh - self._vmh
        if nx + self._vmw < ox or nx >= ox + self._vmw or \
           ny + self._vmh < oy or ny >= oy + self._vmh or \
           not self._optimize or force:
            # no overlap or optimization disabled, redraw the whole thing
            self._setmap(nx, ny)
            self._vmx = nx
            self._vmy = ny
        else:
            if nx < ox:
                rw = ox - nx
                w  = self._vmw - rw
                if ny < oy:
                    # push to bottom right
                    rh = oy - ny
                    h  = self._vmh - rh
                    self._tm.copy(0, 0, w, h, rw, rh, False)
                    self._setmap(nx, ny,      0,  0, self._vmw, rh)
                    self._setmap(nx, ny + rh, 0, rh, rw,        h)
                    self._vmy = ny
                elif ny > oy:
                    # push to top right
                    rh = ny - oy
                    h  = self._vmh - rh
                    self._tm.copy(0, rh, w, h, rw, 0, False)
                    self._setmap(nx, ny,     0, 0, rw,        h)
                    self._setmap(nx, ny + h, 0, h, self._vmw, rh)
                    self._vmy = ny
                else:
                    # push to right
                    self._tm.copy(0, 0, w, self._vmh, rw, 0, False)
                    self._setmap(nx, ny, 0, 0, rw, self._vmh)
                self._vmx = nx
            elif nx > ox:
                rw = nx - ox
                w  = self._vmw - rw
                if ny < oy:
                    # push to bottom left
                    rh = oy - ny
                    h  = self._vmh - rh
                    self._tm.copy(rw, 0, w, h, 0, rh, False)
                    self._setmap(nx,     ny,      0, 0,  self._vmw, rh)
                    self._setmap(nx + w, ny + rh, w, rh, rw,        h)
                    self._vmy = ny
                elif ny > oy:
                    # push to top left
                    rh = ny - oy
                    h  = self._vmh - rh
                    self._tm.copy(rw, rh, w, h, 0, 0, False)
                    self._setmap(nx + w, ny,     w, 0, rw,        h)
                    self._setmap(nx,     ny + h, 0, h, self._vmw, rh)
                    self._vmy = ny
                else:
                    # push to left
                    self._tm.copy(rw, 0, w, self._vmh, 0, 0, False)
                    self._setmap(nx + w, ny, w, 0, rw, self._vmh)
                self._vmx = nx
            else:
                if ny < oy:
                    # push to bottom
                    rh = oy - ny
                    h  = self._vmh - rh
                    self._tm.copy(0, 0, self._vmw, h, 0, rh, False)
                    self._setmap(nx, ny, 0, 0, self._vmw, rh)
                    self._vmy = ny
                elif ny > oy:
                    # push to top
                    rh = ny - oy
                    h  = self._vmh - rh
                    self._tm.copy(0, rh, self._vmw, h, 0, 0, False)
                    self._setmap(nx, ny + h, 0, h, self._vmw, rh)
                    self._vmy = ny
                else:
                    # nothing to do
                    pass 
        # allow to safely set parameters in any order
        self._l.scroll_pos(0, 0)
        if self._newx < 0:
            if self._newy < 0:
                # push to bottom right
                self._l.pos(-self._newx, -self._newy)
                self._l.window(self._vw * self._tw + self._newx,
                               self._vh * self._th + self._newy)
                self._l.scroll_pos(0, 0)
            elif self._newy + (self._vmh * self._th) > self._mh * self._th:
                # push to top right
                vh = self._mh * self._th - self._newy
                self._l.pos(-self._newx, 0)
                self._l.window(self._vw * self._tw + self._newx, vh)
                self._l.scroll_pos(0, self._vmh * self._th - vh)
            else:
                # push to right
                self._l.pos(-self._newx, 0)
                self._l.window(self._vw * self._tw + self._newx,
                               self._vh * self._th)
                self._l.scroll_pos(0, self._newy - (ny * self._th))
        elif self._newx + (self._vmw * self._tw) > self._mw * self._tw:
            if self._newy < 0:
                # push to bottom left
                vw = self._mw * self._tw - self._newx
                self._l.pos(0, -self._newy)
                self._l.window(vw, self._vh * self._th + self._newy)
                self._l.scroll_pos(self._vmw * self._tw - vw, 0)
            elif self._newy + (self._vmh * self._th) > self._mh * self._th:
                # push to top left
                vw = self._mw * self._tw - self._newx
                vh = self._mh * self._th - self._newy
                self._l.pos(0, 0)
                self._l.window(vw, vh)
                self._l.scroll_pos(self._vmw * self._tw - vw,
                                   self._vmh * self._th - vh)
            else:
                # push to left
                vw = self._mw * self._tw - self._newx
                self._l.pos(0, 0)
                self._l.window(vw, self._vh * self._th)
                self._l.scroll_pos(self._vmw * self._tw - vw,
                                   self._newy - (ny * self._th))
        else:
            if self._newy < 0:
                # push to bottom
                self._l.pos(0, -self._newy)
                self._l.window(self._vw * self._tw,
                               self._vh * self._th + self._newy)
                self._l.scroll_pos(self._newx - (nx * self._tw), 0)
            elif self._newy + (self._vmh * self._th) > self._mh * self._th:
                # push to top
                vh = self._mh * self._th - self._newy
                self._l.pos(0, 0)
                self._l.window(self._vw * self._tw, vh)
                self._l.scroll_pos(self._newx - (nx * self._tw),
                                   self._vmh * self._th - vh)
            else:
                # view all
                self._l.pos(0, 0)
                self._l.window(self._vw * self._tw,
                               self._vh * self._th)
                self._l.scroll_pos(self._newx - (nx * self._tw),
                                   self._newy - (ny * self._th))

    def updateregion(self, x, y, w, h):
        vmx = 0
        vmy = 0
        if x < self._vmx:
            if x + w > self._vmx + self._vmw:
                w = self._vmw
                x = self._vmx
                vmx = 0
            elif x + w > self._vmx:
                w = (x + w) - self._vmx
                x = self._vmx
                vmx = 0
            else:
                return
        else: # x >= self._vmx
            if x >= self._vmx + self._vmw:
                return
            else: # x < self._vmx + self._vmw
                vmx = x - self._vmx
                if vmx + w > self._vmw:
                    w = self._vmw - vmx
        if y < self._vmy:
            if y + h > self._vmy + self._vmh:
                h = self._vmh
                y = self._vmy
                vmy = 0
            elif y + h > self._vmy:
                h = (y + h) - self._vmy
                y = self._vmy
                vmy = 0
            else:
                return
        else: # y >= self._vmy
            if y >= self._vmy + self._vmh:
                return
            else: # y < self._vmy + self._vmh
                vmy = y - self._vmy
                if vmy + h > self._vmh:
                    h = self._vmh - vmy
        self._setmap(x, y, vmx, vmy, w, h)

    def draw(self):
        if self._draw:
            self._l.draw()
