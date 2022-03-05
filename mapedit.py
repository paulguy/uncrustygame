#!/usr/bin/env python
from sdl2 import *
import crustygame as cg
import array
from sys import argv
import time
from dataclasses import dataclass
from traceback import print_tb
import display
import textbox
import copy
import itertools
import math
import effects

#TODO:
# options for text/UI scale
# Editor view scale option
# Multiple layers
# Preview of multiple layers with independent scale/scroll speed/center
# layer/project Save/Load
# resizing tilemaps?
# mouse support?

# debugging options
# enable SDL render batching, not very useful to disable but can be useful to
# see what if any difference it makes
# update: it actually makes a lot of difference
RENDERBATCHING=True
# enable tracing of display list processing
TRACEVIDEO=False

RES_WIDTH=1024
RES_HEIGHT=768
FONT_FILENAME="cdemo/font.bmp"
FONT_MAPNAME="font.txt"
FONT_WIDTH=8
FONT_HEIGHT=8
FONT_SCALE=2.0
ERROR_TIME=10.0

crustyerror = ''

@dataclass(frozen=True)
class TilesetDesc():
    filename : str
    width : int
    height : int

@dataclass
class MapChange():
    x : int
    y : int
    w : int
    h : int
    tilemap : array.array = None
    colormod : array.array = None
    flags : array.array = None

def put_centered_line(tb, line, y, mw):
    tb.put_text((line,), (mw - len(line)) / 2, y)

def make_tilemap(vw, vh, mw, mh, curx, cury, ts,
                 tilemap, flags=None, colormod=None):
    if vw > mw:
        vw = mw
    if vh > mh:
        vh = mh
    if curx >= mw:
        curx = mw - 1
    if cury >= mh:
        cury = mh - 1
    stm = display.ScrollingTilemap(ts, tilemap,
                                   vw, vh, mw, mh,
                                   flags=flags,
                                   colormod=colormod)
    return curx, cury, stm

def update_cursor(vw, vh, mw, mh, x, y):
    xpos = -1
    ypos = -1
    xscroll = 0
    yscroll = 0
    halfw = vw // 2
    halfh = vh // 2
    if mw > vw:
        if x > halfw:
            if x < mw - halfw:
                xscroll = x - halfw - (vw % 2)
                x = halfw + (vw % 2)
                xpos = 0
            else:
                xscroll = mw - vw
                x = x - (mw - vw)
                xpos = 1
    else:
        if x > halfw:
            xpos = 1
    if mh > vh:
        if y > halfh:
            if y < mh - halfh:
                yscroll = y - halfh - (vh % 2)
                y = halfh + (vh % 2)
                ypos = 0
            else:
                yscroll = mh - vh
                y = y - (mh - vh)
                ypos = 1
    else:
        if y > halfh:
            xpos = 1
    return xpos, ypos, xscroll, yscroll, x, y

def make_box(codec, width, height, mw=None, tm=None, offset=0, corner='+', hedge='-', vedge='|'):
    corner = array.array('I', corner.encode(codec))[0]
    hedge = array.array('I', hedge.encode(codec))[0]
    vedge = array.array('I', vedge.encode(codec))[0]
    if tm is None:
        tm = array.array('I', itertools.repeat(array.array('I', ' '.encode(codec))[0], width * height))
    if mw is None:
        mw = width
    tm[offset] = corner
    for x in range(width - 2):
        tm[offset + 1 + x] = hedge
    tm[offset + width - 1] = corner
    for y in range(height - 2):
        tm[offset + ((y + 1) * mw)] = vedge
        tm[offset + (((y + 1) * mw) + width - 1)] = vedge
    tm[offset + ((height - 1) * mw)] = corner
    for x in range(width - 2):
        tm[offset + (((height - 1) * mw) + x + 1)] = hedge
    tm[offset + (((height - 1) * mw) + width - 1)] = corner
    return tm

def update_cursor_effect(cursorrad, time):
    cursorrad += math.pi * time
    cursorrad %= math.tau
    r, g, b = effects.color_from_rad(cursorrad, 0, 255)
    color = display.make_color(r, g, b, SDL_ALPHA_OPAQUE)
    return(cursorrad, color)

def make_checkerboard(font, width, height):
    tm = array.array('u', itertools.repeat('█', width)).tounicode().encode(font.codec)
    cm = array.array('I', itertools.repeat(display.make_color(85, 85, 85, SDL_ALPHA_OPAQUE), height - 1 + width))
    cm[1::2] = array.array('I', itertools.repeat(display.make_color(170, 170, 170, SDL_ALPHA_OPAQUE), (height - 1 + width) // 2))
    cbtm = font.ts.tilemap(width, height, "{}x{} Checkerboard".format(width, height))
    cbtm.map(0, 0, 0, width, height, tm)
    cbtm.attr_colormod(0, 0, 1, width, height, cm)
    cbtm.update()
    cbl = cbtm.layer("{}x{} Checkerboard Layer".format(width, height))
    return cbl
 
class Sidebar():
    SIDEBAR_COLOR=display.make_color(255, 255, 255, 96)

    def __init__(self, state, text, hpos=0):
        self._state = state
        self._vw, vh = self._state.window
        fw = self._state.font.ts.width()
        self._fh = self._state.font.ts.height()
        self._scale = self._state.font_scale
        fmw = int(self._vw / self._scale / fw)
        fmh = int(vh / self._scale / self._fh)
        self._dl = display.DisplayList(self._state.ll)
        helptext, _, width, height = textbox.wrap_text(text, fmw // 2 - 2, fmh)
        sbw = width + 2
        self._sbw = int(sbw * fw * self._scale)
        sbtm = array.array('u', itertools.repeat('█', sbw)).tounicode().encode(self._state.font.codec)
        sidebartm = self._state.font.ts.tilemap(sbw, fmh, "Sidebar")
        sidebartm.map(0, 0, 0, sbw, fmh, sbtm)
        sidebartm.update()
        self._sidebarl = sidebartm.layer("Sidebar Layer")
        self._sidebarl.scale(self._scale, self._scale)
        self._sidebarl.colormod(Sidebar.SIDEBAR_COLOR)
        self._sidebarl.blendmode(cg.TILEMAP_BLENDMODE_SUB)
        self._sidebarl.pos(int(self._vw - self._sbw), 0)
        self._dl.append(self._sidebarl)
        self._sbpos = 1
        self._sbtext = textbox.TextBox(width, height, width, height,
                                       self._state.font)
        self._sbtext.put_text(helptext, 0, 0)
        self._hpos = int(self._fh * (1 + hpos))
        self._sbtext.layer.relative(self._sidebarl)
        self._textdl = display.DisplayList(self._state.ll)
        self._textdl.append(lambda: self._sbtext.layer.pos(fw + 1, self._hpos + 1))
        self._textdl.append(lambda: self._sbtext.layer.colormod(display.make_color(0, 0, 0, SDL_ALPHA_OPAQUE)))
        self._textdl.append(self._sbtext.layer)
        self._textdl.append(lambda: self._sbtext.layer.pos(fw, self._hpos))
        self._textdl.append(lambda: self._sbtext.layer.colormod(display.make_color(255, 255, 255, SDL_ALPHA_OPAQUE)))
        self._textdl.append(self._sbtext.layer)
        self._textindex = self._dl.append(self._textdl)

    @property
    def dl(self):
        return self._dl

    @property
    def layer(self):
        return self._sidebarl

    @property
    def width(self):
        return self._sbw

    def set_hpos(self, hpos):
        self._hpos = int(self._fh * (1 + hpos))

    def show_text(self, show):
        if show:
            self._dl.replace(self._textindex, self._textdl)
            self._sidebarl.window(self._sbw, self._vh)
        else:
            self._dl.replace(self._textindex, None)
            self._sidebarl.window(self._sbw, self._hpos)

    def update(self, curpos, curx, mw):
        if mw <= self._vw:
            if mw < self._vw - self._sbw:
                self._sidebarl.pos(self._vw - self._sbw, 0)
                self._sbpos = 1
            else:
                if self._sbpos == 1 and \
                   curx >= self._vw - self._sbw:
                    self._sidebarl.pos(0, 0)
                    self._sbpos = -1
                elif self._sbpos == -1 and \
                     curx < self._sbw:
                    self._sidebarl.pos(self._vw - self._sbw, 0)
                    self._sbpos = 1
        elif curpos != self._sbpos:
            if curpos < 0:
                self._sidebarl.pos(self._vw - self._sbw, 0)
                self._sbpos = 1
            elif curpos > 0:
                self._sidebarl.pos(0, 0)
                self._sbpos = -1
            else:
                if self._sbpos < 0:
                    self._sidebarl.pos(self._vw - self._sbw, 0)
                elif self._sbpos > 0:
                    self._sidebarl.pos(0, 0)
                self._sbpos = 0

class BorderSelector():
    def __init__(self, state, vw, vh, mw, mh, tw, th, tlx, tly, brx, bry):
        self._mw = int(mw)
        self._mh = int(mh)
        self._tlx = int(tlx)
        self._tly = int(tly)
        self._brx = int(brx)
        self._bry = int(bry)
        if self._tlx < 0 or self._tlx >= self._mw or \
           self._tly < 0 or self._tly >= self._mh or \
           self._brx < 0 or self._brx >= self._mw or \
           self._bry < 0 or self._bry >= self._mh:
            raise ValueError("Coordinate out of range.")
        self._state = state
        self._vw = int(vw)
        self._vh = int(vh)
        self._tw = int(tw)
        self._th = int(th)
        self._fw = self._state.font.ts.width()
        self._fh = self._state.font.ts.height()
        self._fvw = self._vw * self._tw // self._fw
        if self._vw * self._tw % self._fw > 0:
            self._fvw += 1
        self._fvh = self._vh * self._th // self._fh
        if self._vh * self._th % self._fh > 0:
            self._fvh += 1
        self._fmw = self._mw * self._tw // self._fw
        if self._mw * self._mw % self._mw > 0:
            self._fmw += 1
        self._fmh = self._mh * self._th // self._fh
        if self._mh * self._mh % self._mh > 0:
            self._fmh += 1
        space = array.array('I', ' '.encode(self._state.font.codec))[0]
        self._tilemap = array.array('I', itertools.repeat(space, self._fmw * self._fmh))
        self._stm = display.ScrollingTilemap(self._state.font.ts,
                                             self._tilemap,
                                             self._fvw, self._fvh,
                                             self._fmw, self._fmh)
        x, y, w, h = self._get_dims()
        make_box(self._state.font.codec, w, h, mw=self._fmw, tm=self._tilemap, offset=(self._fmw * y) + x)
        self._stm.updateregion(0, 0, self._fmw, self._fmh)
        self._apply_box(x, y, w, h)
        self._newtlx = self._tlx
        self._newtly = self._tly
        self._newbrx = self._brx
        self._newbry = self._bry

    @property
    def layer(self):
        return self._stm.layer

    def scroll(self, x, y):
        self._stm.scroll(x * self._tw, y * self._th)
        self._stm.update()

    def get_selection(self):
        return self._tlx, self._tly, \
               self._brx - self._tlx + 1, \
               self._bry - self._tly + 1

    def _get_dims(self):
        w = (self._brx - self._tlx + 1) * self._tw / self._fw
        if w.is_integer():
            w = int(w)
        else:
            w = int(w) + 1
        h = (self._bry - self._tly + 1) * self._th / self._fh
        if h.is_integer():
            h = int(h)
        else:
            h = int(h) + 1
        return self._tlx * self._tw // self._fw, \
               self._tly * self._th // self._fh, \
               w, h

    def _apply_box(self, x, y, w, h):
        self._stm.updateregion(x, y, w, 1)
        self._stm.updateregion(x, y + h - 1, w, 1)
        self._stm.updateregion(x, y, 1, h)
        self._stm.updateregion(x + w - 1, y, 1, h)

    def _update_box(self):
        x, y, w, h = self._get_dims()
        make_box(self._state.font.codec, w, h, mw=self._fmw, tm=self._tilemap, offset=(self._fmw * y) + x, corner=' ', vedge=' ', hedge=' ')
        self._apply_box(x, y, w, h)
        self._tlx = self._newtlx
        self._tly = self._newtly
        self._brx = self._newbrx
        self._bry = self._newbry
        x, y, w, h = self._get_dims()
        make_box(self._state.font.codec, w, h, mw=self._fmw, tm=self._tilemap, offset=(self._fmw * y) + x)
        self._apply_box(x, y, w, h)

    def set_top_left(self, x, y):
        x = int(x)
        y = int(y)
        if x < 0 or x >= self._mw or \
           y < 0 or y >= self._mh:
            raise ValueError("Top-left coordinate out of range.")
        if x > self._brx:
            self._newtlx = self._brx
            self._newbrx = x
        else:
            self._newtlx = x
        if y > self._bry:
            self._newtly = self._bry
            self._newbry = y
        else:
            self._newtly = y
        self._update_box()
        
    def set_bottom_right(self, x, y):
        x = int(x)
        y = int(y)
        if x < 0 or x >= self._mw or \
           y < 0 or y >= self._mh:
            raise ValueError("Bottom-right coordinate out of range.")
        if x < self._tlx:
            self._newbrx = self._tlx
            self._newtlx = x
        else:
            self._newbrx = x
        if y < self._tly:
            self._newbry = self._tly
            self._newtly = y
        else:
            self._newbry = y
        self._update_box()

class ProjectScreen():
    def __init__(self, state):
        self._state = state
        self._layers = list()
        self._fw = self._state.font.ts.width()
        self._fh = self._state.font.ts.height()
        self._vw, self._vh = self._state.window
        self._fmw = int(self._vw / self._state.scale / self._vw)
        self._fmh = int(self._vh / self._state.scale / self._vh)
        self._titletb = textbox.TextBox(self._fmw, 1, self._fmw, 1,
                                        self._state.font)
        put_centered_line(self._titletb, "Project Layers", 0, self._fmw)
        self._tb.layer.pos(int(TEXT_SCALED_WIDTH), int(TEXT_SCALED_HEIGHT))
        self._tb.layer.scale(SCALE, SCALE)
        self._dl.append(self._tb.layer)
        self._menu = textbox.Menu(self._state.ll, self._state.font, self._vw - 2, None)
        self._menu.add_item("Add Layer", onActivate=self._add_layer)
        self._menu.update()
        mlayer, self._cursorl = self._menu.layers
        mlayer.scale(SCALE, SCALE)
        mlayer.pos(int(TEXT_SCALED_WIDTH), int(TEXT_SCALED_HEIGHT * 3))

class NewScreen():
    def _build_screen(self):
        self._vw, self._vh = self._state.window
        self._fw = self._state.font.ts.width()
        self._fh = self._state.font.ts.height()
        self._scale = self._state.font_scale
        self._fmw = int(self._vw / self._scale / self._fw)
        self._fmh = int(self._vh / self._scale / self._fh)
        self._titletb = textbox.TextBox(self._fmw, 1,
                                        self._fmw, 1,
                                        self._state.font)
        put_centered_line(self._titletb, "New Tilemap", 0, self._fmw)
        self._titletb.layer.pos(int(self._fw * self._scale),
                                int(self._fh * self._scale))
        self._titletb.layer.scale(self._state.font_scale, self._state.font_scale)
        self._dl.replace(self._titletbindex, self._titletb.layer)
        self._menu = textbox.Menu(self._state.ll, self._state.font, self._fmw - 2, self._fmh - 3, None, spacing=2)
        self._menu.add_item("Tileset", value=self._filename, maxlen=255, onEnter=self._setname)
        self._menu.add_item("Tile Width", value=str(self._tw), maxlen=4, onEnter=self._settilewidth)
        self._menu.add_item("Tile Height", value=str(self._th), maxlen=4, onEnter=self._settileheight)
        self._menu.add_item("Map Width", value=str(self._mw), maxlen=4, onEnter=self._setmapwidth)
        self._menu.add_item("Map Height", value=str(self._mh), maxlen=4, onEnter=self._setmapheight)
        self._menu.add_item("Unicode Map", value=self._unimap, maxlen=255, onEnter=self._setunimap)
        self._menu.add_item("Proceed", onActivate=self._proceed)
        self._menu.update()
        mlayer, self._cursorl = self._menu.layers
        mlayer.pos(0, self._th * 2)
        mlayer.relative(self._titletb.layer)
        self._dl.replace(self._menuindex, self._menu.displaylist)

    def __init__(self, state):
        self._state = state
        self._filename = FONT_FILENAME
        self._tw = FONT_WIDTH
        self._th = FONT_HEIGHT
        self._mw = 64
        self._mh = 64
        self._unimap = FONT_MAPNAME
        self._error = 0.0
        self._errortext = ''
        self._errorbox = None
        self._cursorrad = 0.0
        self._dl = display.DisplayList(self._state.ll)
        self._titletbindex = self._dl.append(None)
        self._menuindex = self._dl.append(None)
        self._errorindex = self._dl.append(None)
        self._build_screen()

    def active(self):
        vw, vh = self._state.window
        if self._vw != int(vw / self._scale / self._tw) or \
           self._vh != int(vh / self._scale / self._th):
            self._build_screen()

    @property
    def dl(self):
        return self._dl

    def input(self, event):
        if event.type == SDL_TEXTINPUT:
            self._menu.text_event(event)
        elif event.type == SDL_KEYDOWN:
            self._error = 0.0
            if event.key.keysym.sym == SDLK_UP:
                self._menu.up()
            elif event.key.keysym.sym == SDLK_DOWN:
                self._menu.down()
            elif event.key.keysym.sym == SDLK_LEFT:
                self._menu.left()
            elif event.key.keysym.sym == SDLK_RIGHT:
                self._menu.right()
            elif event.key.keysym.sym == SDLK_BACKSPACE:
                self._menu.backspace()
            elif event.key.keysym.sym == SDLK_DELETE:
                self._menu.delete()
            elif event.key.keysym.sym == SDLK_RETURN:
                self._menu.activate_selection()
            elif event.key.keysym.sym == SDLK_ESCAPE:
                if not self._menu.cancel_entry():
                    self._state.stop()

    def update(self, time):
        if self._error > 0.0:
            if self._errorbox is None:
                if len(self._errortext) == 0:
                    self._errortext = "Unknown error"
                lines, _, w, h = textbox.wrap_text(self._errortext, self._fmw - 2, 10)
                self._errorbox = textbox.TextBox(w, h, w, h,
                                                 self._state.font)
                self._errorbox.put_text(lines, 0, 0)
                self._errorbox.layer.relative(self._titletb.layer)
                self._errorbox.layer.pos(0, int((self._fmh - h - 2) * self._fh))
                self._dl.replace(self._errorindex, self._errorbox.layer)
            self._error -= time
        if self._error <= 0.0 and self._errorbox is not None:
            self._dl.replace(self._errorindex, None)
            self._errorbox = None
            self._errortext = ''

        self._cursorrad, color = update_cursor_effect(self._cursorrad, time)
        self._cursorl.colormod(color)

    def resize(self):
        self._build_screen()

    def _setname(self, priv, sel, val):
        self._filename = val.lstrip().rstrip()
        return val

    def _settilewidth(self, priv, sel, val):
        try:
            val = int(val)
        except ValueError:
            return None
        if val < 1:
            return None
        self._tw = val
        return str(self._tw)

    def _settileheight(self, priv, sel, val):
        try:
            val = int(val)
        except ValueError:
            return None
        if val < 1:
            return None
        self._th = val
        return str(self._th)

    def _setmapwidth(self, priv, sel, val):
        try:
            val = int(val)
        except ValueError:
            return None
        if val < 1:
            return None
        self._mw = val
        return str(self._mw)

    def _setmapheight(self, priv, sel, val):
        try:
            val = int(val)
        except ValueError:
            return None
        if val < 1:
            return None
        self._mh = val
        return str(self._mh)

    def _setunimap(self, priv, sel, val):
        self._unimap = val.lstrip().rstrip()
        return val

    def _set_error(self, text):
        self._errortext = text
        self._error = ERROR_TIME

    def _proceed(self, priv, sel):
        unimap = None
        if len(self._unimap) > 0:
            unimap = self._unimap
        try:
            self._editscreen = EditScreen(self._state,
                                          self._filename, unimap,
                                          self._mw, self._mh,
                                          self._tw, self._th)
        except Exception as e:
            if isinstance(e, cg.CrustyException):
                self._set_error("Couldn't load tileset: {}: {}".format(e, get_error()))
            else:
                self._set_error("Couldn't load tileset: {}".format(e))
            print(e)
            print_tb(e.__traceback__)
            return
        self._state.active_screen(self._editscreen)

class EditScreen():
    MAX_UNDO=100

    @property
    def dl(self):
        return self._dl

    def _update_tile(self):
        self._statustext.put_text(("    ",), 6, 0)
        self._statustext.put_text((str(self._tile),), 6, 0)
        self._tiletm.map(0, 0, 0, 1, 1, array.array('I', (self._tile,)))
        self._tiletm.update()

    def _update_red(self):
        self._statustext.put_text(("   ",), 14, 0)
        self._statustext.put_text((str(self._red),), 14, 0)
        self._tilel.colormod(self._color)

    def _update_green(self):
        self._statustext.put_text(("   ",), 14, 1)
        self._statustext.put_text((str(self._green),), 14, 1)
        self._tilel.colormod(self._color)

    def _update_blue(self):
        self._statustext.put_text(("   ",), 14, 2)
        self._statustext.put_text((str(self._blue),), 14, 2)
        self._tilel.colormod(self._color)

    def _update_alpha(self):
        self._statustext.put_text(("   ",), 14, 3)
        self._statustext.put_text((str(self._alpha),), 14, 3)
        self._tilel.colormod(self._color)

    def _update_vflip(self):
        if self._vflip:
            self._statustext.put_text("Y", 4, 4)
        else:
            self._statustext.put_text("N", 4, 4)
        self._tiletm.attr_flags(0, 0, 0, 1, 1, array.array('I', (self._attrib,)))
        self._tiletm.update()

    def _update_hflip(self):
        if self._hflip:
            self._statustext.put_text("Y", 10, 4)
        else:
            self._statustext.put_text("N", 10, 4)
        self._tiletm.attr_flags(0, 0, 0, 1, 1, array.array('I', (self._attrib,)))
        self._tiletm.update()

    def _update_rotation(self):
        if self._rotate == cg.TILEMAP_ROTATE_NONE:
            self._statustext.put_text(("0°  ",), 3, 3)
        elif self._rotate == cg.TILEMAP_ROTATE_90:
            self._statustext.put_text(("90° ",), 3, 3)
        elif self._rotate == cg.TILEMAP_ROTATE_180:
            self._statustext.put_text(("180°",), 3, 3)
        else:
            self._statustext.put_text(("270°",), 3, 3)
        self._tiletm.attr_flags(0, 0, 0, 1, 1, array.array('I', (self._attrib,)))
        self._tiletm.update()

    def set_tile(self, tile):
        self._tile = tile
        self._update_tile()

    def _update_cursor(self):
        self._curpos, _, xscroll, yscroll, x, y = \
            update_cursor(self._vw, self._vh,
                          self._mw, self._mh,
                          self._curx, self._cury)
        self._stm.scroll(xscroll * self._tw, yscroll * self._th)
        self._stm.update()
        self._cursorl.pos(x * self._tw - self._fw, y * self._th - self._fw)
        self._statustext.put_text(("    ", "    "), 3, 1)
        self._statustext.put_text((str(self._curx), str(self._cury)), 3, 1)
        if self._border is not None:
            self._border.scroll(xscroll, yscroll)

    def _update_sidebar(self):
        self._sidebar.update(self._curpos,
                             self._curx * self._scale * self._tw,
                             self._mw * self._tw * self._scale)

    def _make_stm(self):
        self._curx, self._cury, self._stm = \
            make_tilemap(self._vw, self._vh,
                         self._mw, self._mh,
                         0, 0,
                         self._tileset, self._tilemap,
                         flags=self._flags, colormod=self._colormod)
        self._stm.layer.scale(self._scale, self._scale)
        self._cursorl.relative(self._stm.layer)
        self._dl.replace(self._stmindex, self._stm.layer)
        self._update_cursor()

    def _make_selectscreen(self):
        width = 0
        if self._selectscreen is not None:
            width = self._selectscreen.width
        self._selectscreen = TileSelectScreen(self._state, self, self._tsdesc, width=width)

    def _build_screen(self):
        vw, vh = self._state.window
        self._vw = int(vw / self._scale / self._tw)
        self._vh = int(vh / self._scale / self._th)
        self._fw = self._state.font.ts.width()
        self._fh = self._state.font.ts.height()
        scale = self._state.font_scale
        self._fmw = int(vw / scale / self._fw)
        self._fmh = int(vh / scale / self._fh)
        self._sidebar = Sidebar(self._state, "h - Toggle Sidebar\nESC - Quit\nArrows - Move\nSPACE - Place*\n  *=Fill Selection\nSHIFT+SPACE\n  Grab/Copy\nNumpad Plus\n  Increase Tile\nNumpad Minus\n  Decrease Tile\nc - Open Color Picker\nC - Grab/Copy Color\nCTRL+c - Place Color*\nv - Open Tile Picker\nV - Grab/Copy Tile\nCTRL+v - Place Tile*\nr - Cycle Rotation\nt - Toggle Horiz Flip\ny - Toggle Vert Flip\nB - Grab/Copy\n  Attributes\nCTRL+b\n  Place Attributes*\nq/a - Adjust Red\nw/s - Adjust Green\ne/d - Adjust Blue\nx/z - Adjust Alpha\nf - Top Left Select\ng - Bottom Right\n  Select\nu/U - Undo/Redo\np - Put Copy\ni - Insert Text\nCTRL+r - Reload\n  Tileset")
        pwidth = self._tw * scale / self._fw
        if pwidth.is_integer():
            pwidth = int(pwidth)
        else:
            pwidth = int(pwidth) + 1
        pheight = self._th * scale / self._fh
        if pheight.is_integer():
            pheight = int(pheight)
        else:
            pheight = int(pheight) + 1
        tstart = pheight / scale
        if tstart.is_integer():
            tstart = int(tstart)
        else:
            tstart = int(tstart) + 1
        tstart += 1
        tilebgl = make_checkerboard(self._state.font, pwidth, pheight)
        tilebgl.pos(self._fw, self._fh)
        tilebgl.scale(1 / scale, 1 / scale)
        tilebgl.relative(self._sidebar.layer)
        self._sidebar.dl.append(tilebgl)
        self._tiletm = self._tileset.tilemap(1, 1, "Preview")
        self._tiletm.update()
        self._tilel = self._tiletm.layer("Preview Layer")
        self._tilel.scale(scale, scale)
        self._tilel.relative(tilebgl)
        self._sidebar.dl.append(self._tilel)
        lines, _, _, h = textbox.wrap_text("Tile:      R:    \nX:         G:    \nY:         B:    \nR:         A:\nVF:   HF:  ", self._sidebar.width - 2, self._vh)
        self._sidebar.set_hpos(tstart + h)
        self._statustext = textbox.TextBox(self._sidebar.width - 2, h, self._sidebar.width - 2, h, self._state.font)
        self._statustext.put_text(lines, 0, 0)
        self._statustext.layer.pos(self._fw, self._fh * (1 + tstart))
        self._statustext.layer.relative(self._sidebar.layer)
        self._update_tile()
        self._update_red()
        self._update_green()
        self._update_blue()
        self._update_alpha()
        self._update_hflip()
        self._update_vflip()
        self._update_rotation()
        self._sidebar.dl.append(self._statustext.layer)
        curwidth = int((self._tw * self._scale) / (self._fw * scale)) + 2
        curheight = int((self._th * self._scale) / (self._fh * scale)) + 2
        self._cursortm = self._state.font.ts.tilemap(curwidth, curheight, "MapEditor Cursor Tilemap")
        ctm = make_box(self._state.font.codec, curwidth, curheight)
        self._cursortm.map(0, 0, curwidth, curwidth, curheight, ctm)
        self._cursortm.update()
        self._cursorl = self._cursortm.layer("Map Editor Cursor Layer")
        self._make_stm()
        self._dl.replace(self._cursorindex, self._cursorl)
        self._dl.replace(self._sidebarindex, self._sidebar.dl)
        self._make_selectscreen()

    def __init__(self, state, filename, unimap, mw, mh, tw, th):
        self._state = state
        self._scale = self._state.font_scale
        self._mw = int(mw)
        self._mh = int(mh)
        self._tw = int(tw)
        self._th = int(th)
        self._cursorrad = 0.0
        self._fxcolor = 0
        self._curx = 0
        self._cury = 0
        self._tile = 0
        self._quitting = False
        self._red = 255
        self._green = 255
        self._blue = 255
        self._alpha = SDL_ALPHA_OPAQUE
        self._hflip = 0
        self._vflip = 0
        self._rotate = cg.TILEMAP_ROTATE_NONE
        self._drawing = False
        self._puttile = False
        self._putcolor = False
        self._putattrib = False
        self._showsidebar = 2
        self._border = None
        self._clipboard = None
        self._undo = list()
        self._undopos = -1
        self._typing = False
        self._selectscreen = None
        self._errortext = ''
        self._error = 0.0
        self._errorbox = None
        self._errorh = 0
        self._tsdesc = self._state.add_tileset(filename, self._tw, self._th)
        self._tileset = self._state.tileset(self._tsdesc)
        self._tiles = self._tileset.tiles()
        self._codec = None
        if unimap is not None:
            self._codec = textbox.load_tileset_codec(unimap, maxval=self._tiles)
        self._color = display.make_color(self._red, self._green, self._blue, self._alpha)
        self._attrib = display.make_attrib(self._hflip, self._vflip, self._rotate)
        self._tilemap = array.array('I', itertools.repeat(0, self._mw * self._mh))
        self._flags = array.array('I', itertools.repeat(self._attrib, self._mw * self._mh))
        self._colormod = array.array('I', itertools.repeat(self._color, self._mw * self._mh))
        self._errordl = display.DisplayList(self._state.ll)
        self._errordl.append(lambda: self._errorbox.layer.pos(self._fw + 1, self._errorh + 1))
        self._errordl.append(lambda: self._errorbox.layer.colormod(display.make_color(0, 0, 0, SDL_ALPHA_OPAQUE)))
        self._errordlindex1 = self._errordl.append(None)
        self._errordl.append(lambda: self._errorbox.layer.pos(self._fw, self._errorh))
        self._errordl.append(lambda: self._errorbox.layer.colormod(self._fxcolor))
        self._errordlindex2 = self._errordl.append(None)
        self._dl = display.DisplayList(self._state.ll)
        self._stmindex = self._dl.append(None)
        self._cursorindex = self._dl.append(None)
        self._borderindex = self._dl.append(None)
        self._sidebarindex = self._dl.append(None)
        self._errorindex = self._dl.append(None)
        self._build_screen()

    def _set_error(self, text):
        self._errortext = text
        self._error = ERROR_TIME

    def active(self):
        if self._quitting:
            self._state.stop()
        vw, vh = self._state.window
        if self._vw != int(vw / self._scale / self._tw) or \
           self._vh != int(vh / self._scale / self._th):
            self._build_screen()

    def _get_tilemap_rect(self, x, y, w, h):
        rect = array.array('I')
        for num in range(h):
            rect.extend(self._tilemap[(self._mw*(y+num))+x:(self._mw*(y+num))+x+w])
        return rect

    def _get_colormod_rect(self, x, y, w, h):
        rect = array.array('I')
        for num in range(h):
            rect.extend(self._colormod[(self._mw*(y+num))+x:(self._mw*(y+num))+x+w])
        return rect

    def _get_flags_rect(self, x, y, w, h):
        rect = array.array('I')
        for num in range(h):
            rect.extend(self._flags[(self._mw*(y+num))+x:(self._mw*(y+num))+x+w])
        return rect

    def _get_region(self, x, y, w, h):
        tilemap = self._get_tilemap_rect(x, y, w, h)
        colormod = self._get_colormod_rect(x, y, w, h)
        flags = self._get_flags_rect(x, y, w, h)
        return MapChange(x, y, w, h, tilemap, colormod, flags)

    def _save_region(self, x, y, w, h):
        orig = self._get_region(x, y, w, h)
        if self._undopos + 1 < len(self._undo):
            self._undo = self._undo[:self._undopos + 1]
        self._undo.append(orig)
        self._undopos += 1
        if self._undopos > EditScreen.MAX_UNDO:
            del self._undo[0]
            self._undopos = EditScreen.MAX_UNDO

    def _apply_change(self, change, save=True):
        if save:
            self._save_region(change.x, change.y, change.w, change.h)
        if change.tilemap is not None:
            for num in range(change.h):
                self._tilemap[(self._mw*(change.y+num))+change.x:(self._mw*(change.y+num))+change.x+change.w] = change.tilemap[change.w*num:(change.w*num)+change.w]
        if change.colormod is not None:
            for num in range(change.h):
                self._colormod[(self._mw*(change.y+num))+change.x:(self._mw*(change.y+num))+change.x+change.w] = change.colormod[change.w*num:(change.w*num)+change.w]
        if change.flags is not None:
            for num in range(change.h):
                self._flags[(self._mw*(change.y+num))+change.x:(self._mw*(change.y+num))+change.x+change.w] = change.flags[change.w*num:(change.w*num)+change.w]
        self._stm.updateregion(change.x, change.y, change.w+1, change.h+1)

    def _do_undo(self):
        if self._undopos >= 0:
            orig = self._get_region(self._undo[self._undopos].x,
                                    self._undo[self._undopos].y,
                                    self._undo[self._undopos].w,
                                    self._undo[self._undopos].h)
            self._apply_change(self._undo[self._undopos], save=False)
            self._undo[self._undopos] = orig
            self._undopos -= 1

    def _do_redo(self):
        if self._undopos + 1 < len(self._undo):
            orig = self._get_region(self._undo[self._undopos + 1].x,
                                    self._undo[self._undopos + 1].y,
                                    self._undo[self._undopos + 1].w,
                                    self._undo[self._undopos + 1].h)
            self._apply_change(self._undo[self._undopos + 1], save=False)
            self._undo[self._undopos + 1] = orig
            self._undopos += 1

    def _check_drawing(self):
        if self._drawing or self._puttile or self._putcolor or self._putattrib:
            self._save_region(self._curx, self._cury, 1, 1)
        if self._drawing:
            self._tilemap[self._cury * self._mw + self._curx] = self._tile
            self._colormod[self._cury * self._mw + self._curx] = self._color
            self._flags[self._cury * self._mw + self._curx] = self._attrib
        else:
            if self._puttile:
                self._tilemap[self._cury * self._mw + self._curx] = self._tile
            if self._putcolor:
                self._colormod[self._cury * self._mw + self._curx] = self._color
            if self._putattrib:
                self._flags[self._cury * self._mw + self._curx] = self._attrib
        if self._drawing or self._puttile or self._putcolor or self._putattrib:
            self._stm.updateregion(self._curx, self._cury, 1, 1)

    def _make_border(self, x, y, w, h):
        vw = self._vw
        if vw > self._mw:
            vw = self._mw
        vh = self._vh
        if vh > self._mh:
            vh = self._mh
        self._border = BorderSelector(self._state, vw, vh,
                                      self._mw, self._mh,
                                      self._tw, self._th,
                                      x, y,
                                      x + w - 1, y + h - 1)
        _, _, x, y, _, _ = update_cursor(self._vw, self._vh,
                                         self._mw, self._mh,
                                         self._curx, self._cury)
        self._border.scroll(x, y)
        self._border.layer.relative(self._stm.layer)
        self._dl.replace(self._borderindex, self._border.layer)

    def _up(self):
        miny = 0
        if self._typing and self._border is not None:
            _, miny, _, _ = self._border.get_selection()
        self._cury -= 1
        if self._cury < miny:
            self._cury = miny
        self._update_cursor()
        self._check_drawing()

    def _down(self):
        maxy = self._mh
        if self._typing and self._border is not None:
            _, y, _, h = self._border.get_selection()
            maxy = y + h
        self._cury += 1
        if self._cury > maxy - 1:
            self._cury = maxy - 1
        self._update_cursor()
        self._check_drawing()

    def _left(self):
        minx = 0
        if self._typing and self._border is not None:
            minx, _, _, _ = self._border.get_selection()
        self._curx -= 1
        if self._curx < minx:
            self._curx = minx
        self._update_cursor()
        self._update_sidebar()
        self._check_drawing()

    def _right(self):
        if self._typing:
            x = 0
            y = 0
            w = self._mw
            h = self._mh
            if self._border is not None:
                x, y, w, h = self._border.get_selection()
            maxx = x + w
            self._curx += 1
            if self._curx > maxx - 1:
                maxy = y + h
                self._cury += 1
                if self._cury > maxy - 1:
                    self._curx = maxx - 1
                    self._cury = maxy - 1
                else:
                    self._curx = x
        else:
            self._curx += 1
            if self._curx > self._mh - 1:
                self._curx = self._mh - 1
        self._update_cursor()
        self._update_sidebar()
        self._check_drawing()

    def _return(self):
        maxy = self._mh
        x = 0
        if self._border is not None:
            x, y, _, h = self._border.get_selection()
            maxy = y + h
        self._cury += 1
        if self._cury > maxy - 1:
            self._cury = maxy - 1
        self._curx = x
        self._update_cursor()
        self._check_drawing()

    def input(self, event):
        if self._typing:
            if event.type == SDL_TEXTINPUT:
                # bytes to unicode
                val = event.text.text.decode('utf-8')
                # unicode to bytes
                val = val.encode(self._codec)
                # bytes to int
                val = array.array('I', val)[0]
                self._tilemap[self._cury * self._mw + self._curx] = val
                self._right()
            elif event.type == SDL_KEYDOWN:
                if event.key.keysym.sym == SDLK_UP:
                    self._up()
                elif event.key.keysym.sym == SDLK_DOWN:
                    self._down()
                elif event.key.keysym.sym == SDLK_LEFT or \
                     event.key.keysym.sym == SDLK_BACKSPACE:
                    self._left()
                elif event.key.keysym.sym == SDLK_RIGHT:
                    self._right()
                elif event.key.keysym.sym == SDLK_RETURN:
                    self._return()
                elif event.key.keysym.sym == SDLK_ESCAPE:
                    self._typing = False
        else:
            if event.type == SDL_KEYDOWN:
                self._error = 0.0
                if event.key.keysym.sym == SDLK_UP:
                    self._up()
                elif event.key.keysym.sym == SDLK_DOWN:
                    self._down()
                elif event.key.keysym.sym == SDLK_LEFT:
                    self._left()
                elif event.key.keysym.sym == SDLK_RIGHT:
                    self._right()
                elif event.key.keysym.sym == SDLK_SPACE:
                    if event.key.keysym.mod & KMOD_SHIFT != 0:
                        if self._border is not None:
                            x, y, w, h = self._border.get_selection()
                            self._clipboard = MapChange(x, y, w, h,
                                tilemap=self._get_tilemap_rect(x, y, w, h),
                                colormod=self._get_colormod_rect(x, y, w, h),
                                flags=self._get_flags_rect(x, y, w, h))
                        else:
                            self._tile = self._tilemap[self._cury * self._mw + self._curx]
                            self._color = self._colormod[self._cury * self._mw + self._curx]
                            self._attrib = self._flags[self._cury * self._mw + self._curx]
                            self._update_tile()
                            self._update_red()
                            self._update_green()
                            self._update_blue()
                            self._update_alpha()
                            self._update_hflip()
                            self._update_vflip()
                            self._update_rotation()
                    else:
                        if self._border is not None:
                            x, y, w, h = self._border.get_selection()
                            self._save_region(x, y, w, h)
                            for num in range(h):
                                self._tilemap[self._mw*(y+num)+x:self._mw*(y+num)+x+w] = array.array('I', itertools.repeat(self._tile, w))
                                self._colormod[self._mw*(y+num)+x:self._mw*(y+num)+x+w] = array.array('I', itertools.repeat(self._color, w))
                                self._flags[self._mw*(y+num)+x:self._mw*(y+num)+x+w] = array.array('I', itertools.repeat(self._attrib, w))
                            self._stm.updateregion(x, y, w, h)
                        else:
                            self._drawing = True
                            self._check_drawing()
                elif event.key.keysym.sym == SDLK_KP_PLUS:
                    if self._tile + 1 < self._tiles:
                        self._tile += 1
                        self._update_tile()
                elif event.key.keysym.sym == SDLK_KP_MINUS:
                    if self._tile > 0:
                        self._tile -= 1
                        self._update_tile()
                elif event.key.keysym.sym == SDLK_v:
                    if event.key.keysym.mod & KMOD_SHIFT != 0:
                        if self._border is not None:
                            x, y, w, h = self._border.get_selection()
                            if self._clipboard is not None and \
                               x == self._clipboard.x and \
                               y == self._clipboard.y and \
                               w == self._clipboard.w and \
                               h == self._clipboard.h:
                                self._clipboard.tilemap = self._get_tilemap_rect(x, y, w, h)
                            else:
                                self._clipboard = MapChange(x, y, w, h, tilemap=self._get_tilemap_rect(x, y, w, h))
                        else:
                            self._tile = self._tilemap[self._cury * self._mw + self._curx]
                            self._update_tile()
                    elif event.key.keysym.mod & KMOD_CTRL != 0:
                        if self._border is not None:
                            x, y, w, h = self._border.get_selection()
                            self._save_region(x, y, w, h)
                            for num in range(h):
                                self._tilemap[self._mw*(y+num)+x:self._mw*(y+num)+x+w] = array.array('I', itertools.repeat(self._tile, w))
                            self._stm.updateregion(x, y, w, h)
                        else:
                            self._puttile = True
                            self._check_drawing()
                    else:
                        self._state.active_screen(self._selectscreen)
                elif event.key.keysym.sym == SDLK_c:
                    if event.key.keysym.mod & KMOD_SHIFT != 0:
                        if self._border is not None:
                            x, y, w, h = self._border.get_selection()
                            if self._clipboard is not None and \
                               x == self._clipboard.x and \
                               y == self._clipboard.y and \
                               w == self._clipboard.w and \
                               h == self._clipboard.h:
                                self._clipboard.colormod = self._get_colormod_rect(x, y, w, h)
                            else:
                                self._clipboard = MapChange(x, y, w, h, colormod=self._get_colormod_rect(x, y, w, h))
                        else:
                            self._color = self._colormod[self._cury * self._mw + self._curx]
                            self._red, self._green, self._blue, self._alpha = display.unmake_color(self._color)
                            self._update_red()
                            self._update_green()
                            self._update_blue()
                            self._update_alpha()
                    elif event.key.keysym.mod & KMOD_CTRL != 0:
                        if self._border is not None:
                            x, y, w, h = self._border.get_selection()
                            self._save_region(x, y, w, h)
                            for num in range(h):
                                self._colormod[self._mw*(y+num)+x:self._mw*(y+num)+x+w] = array.array('I', itertools.repeat(self._color, w))
                            self._stm.updateregion(x, y, w, h)
                        else:
                            self._putcolor = True
                            self._check_drawing()
                    else:
                        colorpicker = ColorPickerScreen(self._state, self, self._red, self._green, self._blue, self._alpha)
                        self._state.active_screen(colorpicker)
                elif event.key.keysym.sym == SDLK_b:
                    if event.key.keysym.mod & KMOD_SHIFT != 0:
                        if self._border is not None:
                            x, y, w, h = self._border.get_selection()
                            if self._clipboard is not None and \
                               x == self._clipboard.x and \
                               y == self._clipboard.y and \
                               w == self._clipboard.w and \
                               h == self._clipboard.h:
                                self._clipboard.flags = self._get_flags_rect(x, y, w, h)
                            else:
                                self._clipboard = MapChange(x, y, w, h, flags=self._get_flags_rect(x, y, w, h))
                        else:
                            self._attrib = self._flags[self._cury * self._mw + self._curx]
                            self._hflip, self._vflip, self._rotate = display.unmake_attrib(self._attrib)
                            self._update_hflip()
                            self._update_vflip()
                            self._update_rotation()
                    elif event.key.keysym.mod & KMOD_CTRL != 0:
                        if self._border is not None:
                            x, y, w, h = self._border.get_selection()
                            self._save_region(x, y, w, h)
                            for num in range(h + 1):
                                self._flags[self._mw*(y+num)+x:self._mw*(y+num)+x+w] = array.array('I', itertools.repeat(self._attrib, w))
                            self._stm.updateregion(x, y, w, h)
                        else:
                            self._putattrib = True
                            self._check_drawing()
                elif event.key.keysym.sym == SDLK_t:
                    if self._hflip == 0:
                        self._hflip = cg.TILEMAP_HFLIP_MASK
                    else:
                        self._hflip = 0
                    self._attrib = display.make_attrib(self._hflip, self._vflip, self._rotate)
                    self._update_hflip()
                elif event.key.keysym.sym == SDLK_y:
                    if self._vflip == 0:
                        self._vflip = cg.TILEMAP_VFLIP_MASK
                    else:
                        self._vflip = 0
                    self._attrib = display.make_attrib(self._hflip, self._vflip, self._rotate)
                    self._update_vflip()
                elif event.key.keysym.sym == SDLK_r:
                    if event.key.keysym.mod & KMOD_CTRL != 0:
                        tileset = self._tileset
                        try:
                            self._tileset = self._state.reload_tileset(self._tsdesc)
                            if self._tileset.tiles() < textbox.get_codec_max_map(self._codec):
                                raise ValueError("Tileset has insufficient tiles for tilemap codec.")
                        except Exception as e:
                            if isinstance(e, cg.CrustyException):
                                self._set_error("Couldn't load tileset: {}: {}".format(e, get_error()))
                            else:
                                self._set_error("Couldn't load tileset: {}".format(e))
                            self._tileset = self._state.reload_tileset(self._tsdesc, tileset)
                            print(e)
                            print_tb(e.__traceback__)
                            return
                        try:
                            self._make_stm()
                        except Exception as e:
                            if isinstance(e, cg.CrustyException):
                                self._set_error("Couldn't make tilemap: {}: {}".format(e, get_error()))
                            else:
                                self._set_error("Couldn't make tilemap: {}".format(e))
                            self._tileset = self._state.reload_tileset(self._tsdesc, tileset)
                            self._make_stm()
                            print(e)
                            print_tb(e.__traceback__)
                            return
                        self._make_selectscreen()
                    else:
                        if self._rotate == cg.TILEMAP_ROTATE_NONE:
                            if self._tw == self._th:
                                self._rotate = cg.TILEMAP_ROTATE_90
                            else:
                                self._rotate = cg.TILEMAP_ROTATE_180
                        elif self._rotate == cg.TILEMAP_ROTATE_90:
                            self._rotate = cg.TILEMAP_ROTATE_180
                        elif self._rotate == cg.TILEMAP_ROTATE_180:
                            if self._tw == self._th:
                                self._rotate = cg.TILEMAP_ROTATE_270
                            else:
                                self._rotate = cg.TILEMAP_ROTATE_NONE
                        else:
                            self._rotate = cg.TILEMAP_ROTATE_NONE
                        self._attrib = display.make_attrib(self._hflip, self._vflip, self._rotate)
                        self._update_rotation()
                elif event.key.keysym.sym == SDLK_q:
                    if self._red < 255:
                        self._red += 1
                        self._color = display.make_color(self._red, self._green, self._blue, self._alpha)
                        self._update_red()
                elif event.key.keysym.sym == SDLK_a:
                    if self._red > 0:
                        self._red -= 1
                        self._color = display.make_color(self._red, self._green, self._blue, self._alpha)
                        self._update_red()
                elif event.key.keysym.sym == SDLK_w:
                    if self._green < 255:
                        self._green += 1
                        self._color = display.make_color(self._red, self._green, self._blue, self._alpha)
                        self._update_green()
                elif event.key.keysym.sym == SDLK_s:
                    if self._green > 0:
                        self._green -= 1
                        self._color = display.make_color(self._red, self._green, self._blue, self._alpha)
                        self._update_green()
                elif event.key.keysym.sym == SDLK_e:
                    if self._blue < 255:
                        self._blue += 1
                        self._color = display.make_color(self._red, self._green, self._blue, self._alpha)
                        self._update_blue()
                elif event.key.keysym.sym == SDLK_d:
                    if self._blue > 0:
                        self._blue -= 1
                        self._color = display.make_color(self._red, self._green, self._blue, self._alpha)
                        self._update_blue()
                elif event.key.keysym.sym == SDLK_x:
                    if self._alpha < 255:
                        self._alpha += 1
                        self._color = display.make_color(self._red, self._green, self._blue, self._alpha)
                        self._update_alpha()
                elif event.key.keysym.sym == SDLK_z:
                    if self._alpha > 0:
                        self._alpha -= 1
                        self._color = display.make_color(self._red, self._green, self._blue, self._alpha)
                        self._update_alpha()
                elif event.key.keysym.sym == SDLK_h:
                    if self._showsidebar == 0:
                        self._dl.replace(self._sidebarindex, self._sidebar.dl)
                        self._sidebar.show_text(False)
                        self._showsidebar = 1
                    elif self._showsidebar == 1:
                        self._sidebar.show_text(True)
                        self._showsidebar = 2
                    else:
                        self._dl.replace(self._sidebarindex, None)
                        self._showsidebar = 0
                elif event.key.keysym.sym == SDLK_f:
                    if self._border is None:
                        self._make_border(self._curx, self._cury, 1, 1)
                    else:
                        self._border.set_top_left(self._curx, self._cury)
                elif event.key.keysym.sym == SDLK_g:
                    if self._border is None:
                        self._make_border(self._curx, self._cury, 1, 1)
                    else:
                        self._border.set_bottom_right(self._curx, self._cury)
                elif event.key.keysym.sym == SDLK_ESCAPE:
                    if self._border is None:
                        prompt = PromptScreen(self._state, self, "Quit?", "Any unsaved changes will be lost, are you sure?", ("yes", "no"), default=1)
                        self._state.active_screen(prompt)
                    else:
                        self._dl.replace(self._borderindex, None)
                        self._border = None
                elif event.key.keysym.sym == SDLK_p:
                    x = self._clipboard.x
                    y = self._clipboard.y
                    self._clipboard.x = self._curx
                    self._clipboard.y = self._cury
                    self._apply_change(self._clipboard)
                    self._clipboard.x = x
                    self._clipboard.y = y
                elif event.key.keysym.sym == SDLK_u:
                    if event.key.keysym.mod & KMOD_SHIFT != 0:
                        self._do_redo()
                    else:
                        self._do_undo()
                elif event.key.keysym.sym == SDLK_i:
                    if self._codec is not None:
                        self._typing = True
            elif event.type == SDL_KEYUP:
                if event.key.keysym.sym == SDLK_SPACE:
                    self._drawing = False
                elif event.key.keysym.sym == SDLK_c:
                    self._putcolor = False
                elif event.key.keysym.sym == SDLK_v:
                    self._puttile = False
                elif event.key.keysym.sym == SDLK_b:
                    self._putattrib = False

    def update(self, time):
        if self._error > 0.0:
            if self._errorbox is None:
                if len(self._errortext) == 0:
                    self._errortext = "Unknown error"
                lines, _, w, h = textbox.wrap_text(self._errortext, self._fmw - 2, 10)
                self._errorbox = textbox.TextBox(w, h, w, h,
                                                 self._state.font)
                self._errorbox.put_text(lines, 0, 0)
                self._errorbox.layer.relative(self._stm.layer)
                self._errorh = (self._fmh - h - 1) * self._fh
                self._errordl.replace(self._errordlindex1, self._errorbox.layer)
                self._errordl.replace(self._errordlindex2, self._errorbox.layer)
                self._dl.replace(self._errorindex, self._errordl)
            self._error -= time
        if self._error <= 0.0 and self._errorbox is not None:
            self._dl.replace(self._errorindex, None)
            self._errordl.replace(self._errordlindex1, None)
            self._errordl.replace(self._errordlindex2, None)
            self._errorbox = None
            self._errortext = ''

        self._cursorrad, self._fxcolor = update_cursor_effect(self._cursorrad, time)
        self._cursorl.colormod(self._fxcolor)
        if self._border is not None:
            self._border.layer.colormod(self._fxcolor)
        if self._errorbox is not None:
            self._errorbox.layer.colormod(self._fxcolor)

    def resize(self):
        self._build_screen()
        if self._border is None:
            x, y, w, h = self._border.get_selection()
            self._make_border(self._curx, self._cury, 1, 1)

    def set_option(self, sel):
        if sel == 0:
            self._quitting = True

    def set_color(self, red, green, blue, alpha):
        self._red = red
        self._green = green
        self._blue = blue
        self._alpha = alpha
        self._color = display.make_color(self._red, self._green, self._blue, self._alpha)
        self._update_red()
        self._update_green()
        self._update_blue()
        self._update_alpha()

class TileSelectScreen():
    def _update_cursor(self):
        self._curpos, _, xscroll, yscroll, x, y = \
            update_cursor(self._vw, self._vh,
                          self._mw, self._mh,
                          self._curx, self._cury)
        self._stm.scroll(xscroll * self._tw, yscroll * self._th)
        self._stm.update()
        self._cursorl.pos(x * self._tw - self._fw, y * self._th - self._fh)

    def _make_tilemap(self):
        self._cursorl.relative(None)
        self._dl.replace(self._tmindex, None)
        tilemap = array.array('I', range(self._tiles))
        remainder = (self._mw * self._mh) - self._tiles
        tilemap.extend(array.array('I', itertools.repeat(0, remainder)))
        colormod = array.array('I', itertools.repeat(display.make_color(255, 255, 255, SDL_ALPHA_OPAQUE), self._tiles))
        colormod.extend(array.array('I', itertools.repeat(0, remainder)))
        self._curx, self._cury, self._stm = \
            make_tilemap(self._vw, self._vh,
                         self._mw, self._mh,
                         self._curx, self._cury,
                         self._tileset, tilemap,
                         colormod=colormod)
        if self._cury * self._mw + self._curx >= self._tiles:
            self._cury = self._tiles // self._mw - 1
        self._stm.layer.scale(self._scale, self._scale)
        self._dl.replace(self._tmindex, self._stm.layer)
        self._cursorl.relative(self._stm.layer)
        self._update_cursor()

    def _update_sidebar(self):
        self._sidebar.update(self._curpos,
                             self._curx * self._scale * self._tw,
                             self._mw * self._tw * self._scale)

    def _build_screen(self):
        vw, vh = self._state.window
        self._scale = self._state.font_scale
        self._vw = int(vw / self._scale / self._tw)
        self._vh = int(vh / self._scale / self._th)
        self._fw = self._state.font.ts.width()
        self._fh = self._state.font.ts.height()
        self._dl = display.DisplayList(self._state.ll)
        curwidth = int(self._tw / self._fw) + 2
        curheight = int(self._th / self._fh) + 2
        cursortm = self._state.font.ts.tilemap(curwidth, curheight, "Tile Select Cursor Tilemap")
        ctm = make_box(self._state.font.codec, curwidth, curheight)
        cursortm.map(0, 0, curwidth, curwidth, curheight, ctm)
        cursortm.update()
        self._cursorl = cursortm.layer("Tile Select Cursor Layer")
        self._tmindex = self._dl.append(None)
        self._dl.append(self._cursorl)
        self._make_tilemap()
        self._sidebar = Sidebar(self._state, "ESC - Cancel Selection\nArrows - Move\nEnter - Select\nq/w - Adjust Width\na/z - Adjust Height")
        self._dl.append(self._sidebar.dl)

    def __init__(self, state, editscreen, ts, width=0):
        self._state = state
        self._cursorrad = 0.0
        self._editscreen = editscreen
        self._curx = 0
        self._cury = 0
        self._tileset = self._state.tileset(ts)
        self._tiles = self._tileset.tiles()
        if width == 0 and width < self._tiles:
            side = math.sqrt(self._tiles)
            if side.is_integer():
                side = int(side)
            else:
                side = int(side) + 1
            self._mw = side
            self._mh = side
        else:
            self._mw = int(width)
            self._mh = self._tiles // self._mw
            if self._mw * self._mh < self._tiles:
                self._mh += 1
        self._tw = self._tileset.width()
        self._th = self._tileset.height()
        self._build_screen()

    @property
    def width(self):
        return self._mw

    @property
    def dl(self):
        return self._dl

    def active(self):
        vw, vh = self._state.window
        if self._vw != int(vw / self._scale / self._tw) or \
           self._vh != int(vh / self._scale / self._th):
            self._build_screen()

    def input(self, event):
        if event.type == SDL_KEYDOWN:
            if event.key.keysym.sym == SDLK_UP:
                if self._cury > 0:
                    self._cury -= 1
                    self._update_cursor()
            elif event.key.keysym.sym == SDLK_DOWN:
                if (self._cury + 1) * self._mw + self._curx < self._tiles:
                    self._cury += 1
                    self._update_cursor()
            elif event.key.keysym.sym == SDLK_LEFT:
                if self._curx > 0:
                    self._curx -= 1
                    self._update_cursor()
                    self._update_sidebar()
            elif event.key.keysym.sym == SDLK_RIGHT:
                if self._curx + 1 < self._mw and \
                   self._cury * self._mw + (self._curx + 1) < self._tiles:
                    self._curx += 1
                    self._update_cursor()
                    self._update_sidebar()
            elif event.key.keysym.sym == SDLK_a:
                if self._mh - 1 > 0:
                    self._mh -= 1
                    self._mw = self._tiles // self._mh
                    if self._tiles % self._mh > 0:
                        self._mw += 1
                    self._make_tilemap()
                    self._update_sidebar()
            elif event.key.keysym.sym == SDLK_q:
                if self._mh + 1 < self._tiles:
                    self._mh += 1
                    self._mw = self._tiles // self._mh
                    if self._tiles % self._mh > 0:
                        self._mw += 1
                    self._make_tilemap()
                    self._update_sidebar()
            elif event.key.keysym.sym == SDLK_z:
                if self._mw - 1 > 0:
                    self._mw -= 1
                    self._mh = self._tiles // self._mw
                    if self._tiles % self._mw > 0:
                        self._mh += 1
                    self._make_tilemap()
                    self._update_sidebar()
            elif event.key.keysym.sym == SDLK_x:
                if self._mw + 1 < self._tiles:
                    self._mw += 1
                    self._mh = self._tiles // self._mw
                    if self._tiles % self._mw > 0:
                        self._mh += 1
                    self._make_tilemap()
                    self._update_sidebar()
            elif event.key.keysym.sym == SDLK_RETURN:
                self._editscreen.set_tile(self._cury * self._mw + self._curx)
                self._state.active_screen(self._editscreen)
            elif event.key.keysym.sym == SDLK_ESCAPE:
                self._state.active_screen(self._editscreen)

    def update(self, time):
        self._cursorrad, color = update_cursor_effect(self._cursorrad, time)
        self._cursorl.colormod(color)

    def resize(self):
        self._build_screen()

class PromptScreen():
    def _build_screen(self):
        vw, vh = self._state.window
        scale = self._state.font_scale
        fw = self._state.font.ts.width()
        fh = self._state.font.ts.height()
        vw = int(vw / scale / fw)
        vh = int(vh / scale / fh)
        self._dl = display.DisplayList(self._state.ll)
        text, _, w, titleh = textbox.wrap_text(self._title, vw - 2, 2)
        titletb = textbox.TextBox(vw, titleh, vw, titleh,
                                  self._state.font)
        titletb.layer.scale(scale, scale)
        titletb.layer.pos(int(fw * scale), int(fh * scale))
        for num, line in enumerate(text):
            put_centered_line(titletb, line, num, vw - 2)
        self._dl.append(titletb.layer)
        text, _, w, messageh = textbox.wrap_text(self._message, vw - 2, 5)
        message = textbox.TextBox(w, messageh, w, messageh,
                                  self._state.font)
        message.put_text(text, 0, 0)
        message.layer.relative(titletb.layer)
        message.layer.pos(0, fh * (titleh + 1))
        self._dl.append(message.layer)
        self._menu = textbox.Menu(self._state.ll, self._state.font, vw - 2, vh - 3, None)
        for opt in self._options:
            self._menu.add_item(opt, onActivate=self._activate)
        self._menu.update()
        mlayer, self._cursorl = self._menu.layers
        mlayer.relative(message.layer)
        mlayer.pos(0, fh * (messageh + 1))
        self._dl.append(self._menu.displaylist)
 
    def __init__(self, state, caller, title, message, options, default=0):
        self._cursorrad = 0.0
        self._state = state
        self._caller = caller
        self._title = title
        self._message = message
        self._options = options
        self._build_screen()
        self._menu.move_selection(default)

    @property
    def dl(self):
        return self._dl

    def active(self):
        # On demand screens that destroy when done don't need to rebuild
        pass

    def input(self, event):
        if event.type == SDL_KEYDOWN:
            if event.key.keysym.sym == SDLK_UP:
                self._menu.up()
            elif event.key.keysym.sym == SDLK_DOWN:
                self._menu.down()
            elif event.key.keysym.sym == SDLK_RETURN:
                self._menu.activate_selection()
            elif event.key.keysym.sym == SDLK_ESCAPE:
                self._return(None)

    def update(self, time):
        self._cursorrad, color = update_cursor_effect(self._cursorrad, time)
        self._cursorl.colormod(color)

    def resize(self):
        self._build_screen()

    def _activate(self, priv, sel):
        self._return(sel)

    def _return(self, option):
        self._caller.set_option(option)
        self._state.active_screen(self._caller)

class ColorPickerScreen():
    def _build_screen(self):
        vw, vh = self._state.window
        scale = self._state.font_scale
        fw = self._state.font.ts.width()
        fh = self._state.font.ts.height()
        vw = int(vw / scale / fw)
        vh = int(vh / scale / fh)
        self._dl = display.DisplayList(self._state.ll)
        titletb = textbox.TextBox(vw, 1, vw, 1, self._state.font)
        titletb.layer.scale(scale, scale)
        titletb.layer.pos(int(fw * scale), int(fh * scale))
        put_centered_line(titletb, "Pick Color", 0, vw - 2)
        self._dl.append(titletb.layer)
        self._menu = textbox.Menu(self._state.ll, self._state.font, vw - 2, vw - 3, None, spacing=2)
        self._menu.add_item("Red", value=str(self._red), maxlen=3, onEnter=self.setred, onChange=self.changered)
        self._menu.add_item("Green", value=str(self._green), maxlen=3, onEnter=self.setgreen, onChange=self.changegreen)
        self._menu.add_item("Blue", value=str(self._blue), maxlen=3, onEnter=self.setblue, onChange=self.changeblue)
        self._menu.add_item("Alpha", value=str(self._alpha), maxlen=3, onEnter=self.setalpha, onChange=self.changealpha)
        self._menu.add_item("Accept", onActivate=self._accept)
        self._menu.update()
        mlayer, self._cursorl = self._menu.layers
        mlayer.relative(titletb.layer)
        mlayer.pos(0, fh * 2)
        self._dl.append(self._menu.displaylist)
        colorbgl = make_checkerboard(self._state.font, 8, 8)
        colorbgl.relative(titletb.layer)
        colorbgl.scale(1 / scale, 1 / scale)
        colorbgl.pos(fw * 14, fh * 2)
        self._dl.append(colorbgl)
        cbtm = array.array('u', itertools.repeat('█', 64)).tounicode().encode(self._state.font.codec)
        colortm = self._state.font.ts.tilemap(8, 8, "Color Picker Color")
        colortm.map(0, 0, 8, 8, 8, cbtm)
        colortm.update()
        self._colorl = colortm.layer("Color Picker Color Layer")
        self._colorl.relative(colorbgl)
        self._update_color()
        self._dl.append(self._colorl)

    def __init__(self, state, caller, red=0, green=0, blue=0, alpha=SDL_ALPHA_OPAQUE):
        self._state = state
        self._caller = caller
        self._red = red
        self._green = green
        self._blue = blue
        self._alpha = alpha
        self._cursorrad = 0.0
        self._build_screen()
 
    @property
    def dl(self):
        return self._dl

    def active(self):
        # On demand screens that destroy when done don't need to rebuild
        pass

    def input(self, event):
        if event.type == SDL_TEXTINPUT:
            self._menu.text_event(event)
        elif event.type == SDL_KEYDOWN:
            if event.key.keysym.sym == SDLK_UP:
                self._menu.up()
            elif event.key.keysym.sym == SDLK_DOWN:
                self._menu.down()
            elif event.key.keysym.sym == SDLK_LEFT:
                self._menu.left()
            elif event.key.keysym.sym == SDLK_RIGHT:
                self._menu.right()
            elif event.key.keysym.sym == SDLK_BACKSPACE:
                self._menu.backspace()
            elif event.key.keysym.sym == SDLK_DELETE:
                self._menu.delete()
            elif event.key.keysym.sym == SDLK_RETURN:
                self._menu.activate_selection()
            elif event.key.keysym.sym == SDLK_ESCAPE:
                self._state.active_screen(self._caller)

    def update(self, time):
        self._cursorrad, color = update_cursor_effect(self._cursorrad, time)
        self._cursorl.colormod(color)

    def resize(self):
        self._build_screen()

    def _update_color(self):
        self._colorl.colormod(display.make_color(self._red, self._green, self._blue, self._alpha))

    def setred(self, priv, sel, val):
        try:
            val = int(val)
        except ValueError:
            return None
        if val < 0 or val > 255:
            return None
        self._red = val
        self._update_color()
        return str(self._red)

    def changered(self, priv, sel, change, val):
        val = int(val)
        val += change
        if val < 0 or val > 255:
            return None
        self._red = val
        self._update_color()
        return str(self._red)

    def setgreen(self, priv, sel, val):
        try:
            val = int(val)
        except ValueError:
            return None
        if val < 0 or val > 255:
            return None
        self._green = val
        self._update_color()
        return str(self._green)

    def changegreen(self, priv, sel, change, val):
        val = int(val)
        val += change
        if val < 0 or val > 255:
            return None
        self._green = val
        self._update_color()
        return str(self._green)

    def setblue(self, priv, sel, val):
        try:
            val = int(val)
        except ValueError:
            return None
        if val < 0 or val > 255:
            return None
        self._blue = val
        self._update_color()
        return str(self._blue)

    def changeblue(self, priv, sel, change, val):
        val = int(val)
        val += change
        if val < 0 or val > 255:
            return None
        self._blue = val
        self._update_color()
        return str(self._blue)

    def setalpha(self, priv, sel, val):
        try:
            val = int(val)
        except ValueError:
            return None
        if val < 0 or val > 255:
            return None
        self._alpha = val
        self._update_color()
        return str(self._alpha)

    def changealpha(self, priv, sel, change, val):
        val = int(val)
        val += change
        if val < 0 or val > 255:
            return None
        self._alpha = val
        self._update_color()
        return str(self._alpha)

    def _accept(self, priv, sel):
        self._caller.set_color(self._red, self._green, self._blue, self._alpha)
        self._state.active_screen(self._caller)


class MapeditState():
    RESIZE_COOLDOWN = 0.25

    def __init__(self, renderer, pixfmt, vw, vh, font_filename, font_mapname, font_width, font_height, font_scale):
        sdlfmt = SDL_AllocFormat(pixfmt)
        self._ll = cg.LayerList(renderer, pixfmt, log_cb_return, None)
        self._dl = display.DisplayList(self._ll)
        self._dl.append(display.make_color(0, 0, 0, SDL_ALPHA_OPAQUE))
        self._screen = None
        self._screenindex = None
        self._tilesets = {}
        self._tilemaps = {}
        self._running = True
        self._newscreen = False
        self._resizing = 0.0
        self._extratime = 0.0
        self._vw = int(vw)
        self._vh = int(vh)
        self._font_scale = font_scale
        ts = self._ll.tileset(font_filename, font_width, font_height, "font")
        codec = textbox.load_tileset_codec(font_mapname, ts.tiles())
        self._font = textbox.Font(ts, codec)
        self._lastTime = time.monotonic()

    @property
    def running(self):
        return self._running

    def stop(self):
        self._running = False

    @property
    def ll(self):
        return self._ll

    @property
    def window(self):
        return self._vw, self._vh

    @property
    def font_scale(self):
        return self._font_scale

    @property
    def font(self):
        return self._font

    def active_screen(self, screen):
        self._screen = screen
        self._screen.active()
        if self._screenindex == None:
            self._screenindex = self._dl.append(self._screen.dl)
        else:
            self._dl.replace(self._screenindex, self._screen.dl)
        self._newscreen = True

    def _common_input(self, event):
        if event.type == SDL_QUIT:
            self.stop()
        elif event.type == SDL_WINDOWEVENT and \
             event.window.event == SDL_WINDOWEVENT_RESIZED:
            self._vw = event.window.data1
            self._vh = event.window.data2
            self._resizing = MapeditState.RESIZE_COOLDOWN

    def _input(self, event):
        self._common_input(event)
        if self._running and not self._newscreen and self._resizing <= 0.0:
            self._screen.input(event)

    def _update(self, time):
        if self._running:
            if self._resizing > 0.0:
                self._extratime += time
                display.clear(self._ll, None, 0, 0, 0, SDL_ALPHA_OPAQUE)
                self._resizing -= time
                if self._resizing <= 0.0:
                    self._screen.resize()
                    # the displaylist may have changed
                    self._dl.replace(self._screenindex, self._screen.dl)
            else:
                self._screen.update(time + self._extratime)
                self._dl.draw(display.SCREEN)
                self._extratime = 0.0
        self._newscreen = False

    def frame(self):
        event = SDL_Event()
        thisTime = time.monotonic()
        timetaken = thisTime - self._lastTime

        while SDL_PollEvent(event):
            self._input(event)

        self._update(timetaken)

        self._lastTime = thisTime

    def add_tileset(self, filename, width, height):
        desc = TilesetDesc(filename, width, height)
        try:
            tileset = self._tilesets[desc]
        except KeyError:
            tileset = self._ll.tileset(filename, width, height, None)
            self._tilesets[desc] = tileset
        return desc

    def reload_tileset(self, desc, tileset=None):
        if tileset is None:
            tileset = self._ll.tileset(desc.filename, desc.width, desc.height, None)
        else:
            if tileset.width() != desc.width or \
               tileset.height() != desc.height:
                raise ValueError("Replacement tileset width and height don't match description width and height.")
        self._tilesets[desc] = tileset
        return tileset

    def tileset(self, name):
        return self._tilesets[name]

    def add_tilemap(self, tm, name):
        self._tilemaps[name] = tm


def log_cb_return(priv, string):
    global crustyerror
    crustyerror += string

def get_error():
    global crustyerror
    error = copy.copy(crustyerror)
    crustyerror = ''
    return error

def get_viewport(renderer):
    rect = SDL_Rect()
    SDL_RenderGetViewport(renderer, rect)
    return rect

def do_main(window, renderer, pixfmt):
    rect = get_viewport(renderer)
    state = MapeditState(renderer, pixfmt, rect.w, rect.h, FONT_FILENAME, FONT_MAPNAME, FONT_WIDTH, FONT_HEIGHT, FONT_SCALE)
    newscreen = NewScreen(state)
    state.active_screen(newscreen)

    while state.running:
        state.frame()
        SDL_RenderPresent(renderer)

def main():
    SDL_Init(SDL_INIT_VIDEO)
    window, renderer, pixfmt = display.initialize_video("Map Editor", RES_WIDTH, RES_HEIGHT, SDL_WINDOW_SHOWN | SDL_WINDOW_RESIZABLE, SDL_RENDERER_PRESENTVSYNC | SDL_RENDERER_TARGETTEXTURE, batching=RENDERBATCHING)

    try:
        do_main(window, renderer, pixfmt)
    except cg.CrustyException as e:
        print(crustyerror)
        raise e

    SDL_DestroyRenderer(renderer)
    SDL_DestroyWindow(window)
    SDL_Quit()

if __name__ == "__main__":
    main()
