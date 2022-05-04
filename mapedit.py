#!/usr/bin/env python
from sdl2 import *
import crustygame as cg
import array
from sys import argv
import time
from dataclasses import dataclass
from traceback import print_tb
from enum import Enum
import json
import display
import textbox
import copy
import itertools
import math
import effects

#TODO:
# mouse support

# debugging options
# enable SDL render batching, no idea why you'd disable it
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
FULL_RENDERS = 2

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

class TileMapShrunk(Exception):
    pass

def put_centered_line(tb, line, y, mw):
    tb.put_text((line,), (mw - len(line)) / 2, y)

def make_tilemap(ll, vw, vh, mw, mh, curx, cury, ts,
                 tilemap, flags=None, colormod=None):
    if curx >= mw:
        curx = mw - 1
    if cury >= mh:
        cury = mh - 1
    stm = display.ScrollingTilemap(ll, ts, tilemap,
                                   vw * ts.width(), vh * ts.height(),
                                   mw, mh,
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
 
def cursor_dims(tw, th, twscale, thscale, fw, fh, fscale):
    curwidth = (tw * twscale) / (fw * fscale)
    if curwidth.is_integer():
        curwidth = int(curwidth) + 1
    else:
        curwidth = int(curwidth) + 2
    if curwidth < 2:
        curwidth = 2
    curheight = (th * thscale) / (fh * fscale)
    if curheight.is_integer():
        curheight = int(curheight) + 1
    else:
        curheight = int(curheight) + 2
    if curheight < 2:
        curheight = 2
    return curwidth, curheight

class Sidebar():
    SIDEBAR_COLOR=display.make_color(255, 255, 255, 96)

    def __init__(self, state, text, hpos=0):
        self._state = state
        self._vw, self._vh = self._state.window
        fw = self._state.font.ts.width()
        self._fh = self._state.font.ts.height()
        self._scale = self._state.font_scale
        fmw = int(self._vw / self._scale / fw)
        fmh = int(self._vh / self._scale / self._fh)
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
        self._sbtext = textbox.TextBox(self._state.ll,
                                       width * fw, height * self._fh,
                                       width, height,
                                       self._state.font)
        self._sbtext.put_text(helptext, 0, 0)
        self._hpos = int(self._fh * (1 + hpos))
        self._sbtext.layer.relative(self._sidebarl)
        self._textdl = display.DisplayList(self._state.ll)
        self._textdl.append(lambda: self._sbtext.layer.pos(fw + 1, self._hpos + 1))
        self._textdl.append(lambda: self._sbtext.internal.colormod(display.make_color(0, 0, 0, SDL_ALPHA_OPAQUE)))
        self._textdl.append(self._sbtext.draw)
        self._textdl.append(lambda: self._sbtext.layer.pos(fw, self._hpos))
        self._textdl.append(lambda: self._sbtext.internal.colormod(display.make_color(255, 255, 255, SDL_ALPHA_OPAQUE)))
        self._textdl.append(self._sbtext.draw)
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
            self._sidebarl.window(int(self._sbw / self._scale), int(self._vh / self._scale))
        else:
            self._dl.replace(self._textindex, None)
            self._sidebarl.window(int(self._sbw / self._scale), self._hpos)

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
        self._stm = display.ScrollingTilemap(self._state.ll,
                                             self._state.font.ts,
                                             self._tilemap,
                                             self._fvw * self._fw,
                                             self._fvh * self._fh,
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

    @property
    def internal(self):
        return self._stm.internal

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

    def draw(self):
        self._stm.draw()

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
        titletb = textbox.TextBox(self._state.ll,
                                  vw * fw, titleh * fh,
                                  vw, titleh,
                                  self._state.font)
        titletb.layer.scale(scale, scale)
        titletb.layer.pos(int(fw * scale), int(fh * scale))
        for num, line in enumerate(text):
            put_centered_line(titletb, line, num, vw - 2)
        self._dl.append(titletb.draw)
        message = titletb
        messageh = 0
        if self._message is not None:
            text, _, w, messageh = textbox.wrap_text(self._message, vw - 2, 5)
            message = textbox.TextBox(self._state.ll,
                                      w * fw, messageh * fh,
                                      w, messageh,
                                      self._state.font)
            message.put_text(text, 0, 0)
            message.layer.relative(titletb.layer)
            message.layer.pos(0, fh * (titleh + 1))
            self._dl.append(message.draw)
        self._menu = textbox.Menu(self._state.ll, self._state.font, vw - 2, vh - 3 - messageh - 1, None, rel=message.layer)
        for opt in self._options:
            self._menu.add_item(opt, onActivate=self._activate)
        self._menu.update()
        mlayer, self._cursorl = self._menu.layers
        mlayer.pos(0, fh * (messageh + 1))
        self._dl.append(self._menu.displaylist)
 
    def __init__(self, state, caller, title, options, message=None, default=0):
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
        vw, vh = self._state.window
        scale = self._state.font_scale
        fw = self._state.font.ts.width()
        fh = self._state.font.ts.height()
        if self._fmw != int(vw / scale / fw) or \
           self._fmh != int(vh / scale / fh):
            self._build_screen()

    def resize(self):
        self._build_screen()

    def _activate(self, priv, sel):
        self._return(sel)

    def _return(self, option):
        self._caller.set_option(option)
        self._state.active_screen(self._caller)

@dataclass
class TilemapDesc():
    name : str = "Untitled Tilemap"
    filename : str = FONT_FILENAME
    mapname : str = FONT_MAPNAME
    tw : int = FONT_WIDTH
    th : int = FONT_HEIGHT
    mw : int = 64
    mh : int = 64
    codec : str = None
    wscale : float = FONT_SCALE
    hscale : float = FONT_SCALE

class ProjectScreen():
    DEFAULT_BANNER="Project"

    def _set_banner(self, s):
        self._titletb.clear()
        put_centered_line(self._titletb, s, 0, self._fmw)

    def _add_editor(self, desc, tilemap=None, flags=None, colormod=None):
        self._editors.append(EditScreen(self._state, self, desc, tilemap, flags, colormod))
        if self._menu is not None:
            self._menu.insert_item(len(self._descs) - 1, desc.name, onActivate=self._open_tilemap)

    def _build_screen(self):
        self._vw, self._vh = self._state.window
        self._fw = self._state.font.ts.width()
        self._fh = self._state.font.ts.height()
        self._scale = self._state.font_scale
        self._fmw = int(self._vw / self._scale / self._fw)
        self._fmh = int(self._vh / self._scale / self._fh)
        self._titletb = textbox.TextBox(self._state.ll,
                                        self._fmw * self._fw, 1 * self._fh,
                                        self._fmw, 1,
                                        self._state.font)
        self._set_banner(ProjectScreen.DEFAULT_BANNER)
        self._titletb.layer.pos(int(self._fw * self._scale),
                                int(self._fh * self._scale))
        self._titletb.layer.scale(self._state.font_scale, self._state.font_scale)
        self._dl.replace(self._titleindex,
                         display.Renderable(self._titletb.draw,
                                            always=False))
        self._menu = textbox.Menu(self._state.ll, self._state.font, self._fmw - 2, self._fmh - 3, None, spacing=2, rel=self._titletb.layer)
        for desc in self._descs:
            self._menu.add_item(desc.name, onActivate=self._open_tilemap)
        self._menu.add_item("New Tilemap", onActivate=self._new_tilemap)
        self._menu.add_item("UI Scale", value=str(self._state.font_scale), maxlen=4, onEnter=self._set_scale)
        self._menu.add_item("Preview Manager", onActivate=self._open_layers)
        self._menu.add_item("Project Name", value=self._name, maxlen=255, onEnter=self._setname)
        self._menu.add_item("Save", onActivate=self._save)
        self._menu.update()
        mlayer, self._cursorl = self._menu.layers
        mlayer.pos(0, self._fh * 2)
        self._dl.replace(self._menuindex,
                         display.Renderable(self._menu.displaylist,
                                            always=False))
        # cursor would render twice during updates but whatever.
        self._dl.replace(self._cursorindex, self._cursorl)

    def _load(self):
        data = ""
        try:
            with open("{}.json".format(self._name), 'r') as infile:
                data = infile.read()
        except Exception as e:
            print(e)
            print_tb(e.__traceback__)
            self._set_error("Couldn't load project: {}".format(e))
            return
        savedata = json.loads(data)
        try:
            self._state.set_scale(savedata['ui_scale'])
        except KeyError:
            pass
        try:
            pscrollx, pscrolly = self._layers.scroll_pos
            self._layers.set_scroll(pscrollx, pscrolly)
        except KeyError:
            pass
        descs = list()
        try:
            descs = savedata['tilemaps']
        except KeyError:
            pass
        for desc in descs:
            newdesc = TilemapDesc()
            try:
                newdesc.name = desc['name']
            except KeyError:
                pass
            try:
                newdesc.filename = desc['gfx']
            except KeyError:
                pass
            try:
                newdesc.mapname = desc['unimap']
            except KeyError:
                pass
            try:
                newdesc.tw = desc['tile_width']
            except KeyError:
                pass
            try:
                newdesc.th = desc['tile_height']
            except KeyError:
                pass
            try:
                newdesc.mw = desc['map_width']
            except KeyError:
                pass
            try:
                newdesc.mh = desc['map_height']
            except KeyError:
                pass
            try:
                newdesc.wscale = desc['x_scale']
            except KeyError:
                pass
            try:
                newdesc.hscale = desc['y_scale']
            except KeyError:
                pass
            self._descs.append(newdesc)
        layers = list()
        newlayers = list()
        try:
            layers = savedata['layers']
        except KeyError:
            pass
        for layer in layers:
            newlayer = LayerDesc()
            try:
                newlayer.name = layer['name']
            except KeyError:
                pass
            try:
                newlayer.tilemap = layer['tilemap']
            except KeyError:
                pass
            try:
                newlayer.relative = layer['relative']
            except KeyError:
                pass
            try:
                newlayer.vw = layer['view_width']
            except KeyError:
                pass
            try:
                newlayer.vh = layer['view_height']
            except KeyError:
                pass
            try:
                newlayer.scalex = layer['x_scale']
            except KeyError:
                pass
            try:
                newlayer.scaley = layer['y_scale']
            except KeyError:
                pass
            mode = 'NONE'
            try:
                mode = layer['mode']
            except KeyError:
                pass
            if mode == 'POSITION':
                newlayer.mode = ScrollMode.POSITION
            elif mode == 'LAYER':
                newlayer.mode = ScrollMode.LAYER
            else:
                newlayer.mode = ScrollMode.NONE
            try:
                newlayer.posx = layer['x_pos']
            except KeyError:
                pass
            try:
                newlayer.posy = layer['y_pos']
            except KeyError:
                pass
            try:
                newlayer.scrollx = layer['x_scroll']
            except KeyError:
                pass
            try:
                newlayer.scrolly = layer['y_scroll']
            except KeyError:
                pass
            try:
                newlayer.colormod = layer['colormod']
            except KeyError:
                pass
            try:
                newlayer.blendmode = layer['blend_mode']
            except KeyError:
                pass
            newlayers.append(newlayer)
        for num, desc in enumerate(self._descs):
            tilemap = None
            try:
                with open("{} tilemap{}.bin".format(self._name, num), 'rb') as infile:
                    data = infile.read()
                tilemap = array.array('I', data)
            except Exception as e:
                print(e)
                print_tb(e.__traceback__)
                self._set_error("Couldn't load tilemap: {}".format(e))
            flags = None
            try:
                with open("{} flags{}.bin".format(self._name, num), 'rb') as infile:
                    data = infile.read()
                flags = array.array('I', data)
            except Exception as e:
                print(e)
                print_tb(e.__traceback__)
                self._set_error("Couldn't load flags: {}".format(e))
            colormod = None
            try:
                with open("{} colormod{}.bin".format(self._name, num), 'rb') as infile:
                    data = infile.read()
                colormod = array.array('I', data)
            except Exception as e:
                print(e)
                print_tb(e.__traceback__)
                self._set_error("Couldn't load colormod: {}".format(e))
            self._add_editor(desc, tilemap=tilemap, flags=flags, colormod=colormod)
        for layer in newlayers:
            self._layers.add_layer(layer)

    def __init__(self, state, name=None):
        self._state = state
        self._descs = list()
        self._editors = list()
        self._selected = 0
        self._quitting = False
        self._saving = False
        self._deleting = False
        self._moving = -1
        self._cursorrad = 0.0
        self._error = 0.0
        self._errortext = ''
        self._errorbox = None
        self._menu = None
        self._dl = display.DisplayList(self._state.ll)
        self._titleindex = self._dl.append(None)
        self._menuindex = self._dl.append(None)
        # cursor would render twice during updates but whatever.
        self._cursorindex = self._dl.append(None)
        self._errorindex = self._dl.append(None)
        self._layers = LayersScreen(self._state, self)
        if name is not None:
            self._name = name
        else:
            self._name = "Untitled Project"
        self._load()
        self._build_screen()

    def _set_error(self, text):
        print(text)
        self._errortext = text
        self._error = ERROR_TIME

    @property
    def dl(self):
        return self._dl

    def resize(self):
        vw, vh = self._state.window
        scale = self._state.font_scale
        fw = self._state.font.ts.width()
        fh = self._state.font.ts.height()
        if scale != self._scale or \
           self._fmw != int(vw / scale / fw) or \
           self._fmh != int(vh / scale / fh):
            self._build_screen()

    def _update_menu(self):
        self._menu.update()
        mlayer, _ = self._menu.layers
        mlayer.pos(0, self._fh * 2)

    def active(self):
        if self._quitting:
            self._state.stop()
        self.resize()
        if len(self._descs) > len(self._editors):
            # if menu was backed out of without saving, delete the desc
            del self._descs[-1]
        elif self._deleting:
            self._deleting = False
            del self._descs[self._selected]
            del self._editors[self._selected]
            self._menu.remove(self._selected)
            self._update_menu()
            self._layers.delete_tilemap(self._selected)
        elif self._moving >= 0:
            self._set_banner("Swap with?")
        elif self._saving:
            self._saving = False
            self._do_save()

    def set_option(self, sel):
        if sel != 0:
            self._quitting = False
            self._saving = False

    def input(self, event):
        if event.type == SDL_TEXTINPUT:
            self._menu.text_event(event)
        elif event.type == SDL_KEYDOWN:
            self._state.changed()
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
                if self._moving >= 0 and \
                   self._menu.selection >= len(self._descs):
                    self._set_error("Can't swap with a selection that isn't a tilemap, use ESCAPE to cancel move.")
                    return
                self._menu.activate_selection()
            elif event.key.keysym.sym == SDLK_ESCAPE:
                if not self._menu.cancel_entry():
                    if self._moving >= 0:
                        self._moving = -1
                        self._set_banner(ProjectScreen.DEFAULT_BANNER)
                    else:
                        self._quitting = True
                        prompt = PromptScreen(self._state, self, "Quit?", ("yes", "no"), message="Any unsaved changes will be lost, are you sure?", default=1)
                        self._state.active_screen(prompt)

    def update(self, time):
        if self._scale != self._state.font_scale:
            # set in motion rebuilding everything, and for the state to get the
            # new displaylist
            self._state.active_screen(self)
        if self._error > 0.0:
            if self._errorbox is None:
                if len(self._errortext) == 0:
                    self._errortext = "Unknown error"
                lines, _, w, h = textbox.wrap_text(self._errortext, self._fmw - 2, 10)
                self._errorbox = textbox.TextBox(self._state.ll,
                                                 w * self._fw, h * self._fh,
                                                 w, h,
                                                 self._state.font)
                self._errorbox.put_text(lines, 0, 0)
                self._errorbox.layer.relative(self._titletb.layer)
                self._errorbox.layer.pos(0, int((self._fmh - h - 2) * self._fh))
                self._dl.replace(self._errorindex, self._errorbox.draw)
            self._error -= time
        if self._error <= 0.0 and self._errorbox is not None:
            self._dl.replace(self._errorindex, None)
            self._errorbox = None
            self._errortext = ''

        self._cursorrad, color = update_cursor_effect(self._cursorrad, time)
        self._cursorl.colormod(color)

    def _open_settings(self, sel):
        self._selected = sel
        # make a copy so the original stays unmodified
        desc = copy.deepcopy(self._descs[sel])
        tilemapscreen = TilemapScreen(self._state, self, desc)
        self._state.active_screen(tilemapscreen)

    def _open_tilemap(self, priv, sel):
        if self._moving >= 0:
            if sel == self._moving:
                self._set_error("Can't swap with same tilemap, use ESCAPE to cancel move.")
                return
            moving = self._moving
            self._moving = -1
            desc1 = self._descs[sel]
            editor1 = self._editors[sel]
            desc2 = self._descs[moving]
            editor2 = self._editors[moving]
            self._descs[sel] = desc2
            self._editors[sel] = editor2
            self._descs[moving] = desc1
            self._editors[moving] = editor1
            self._menu.remove(sel)
            self._menu.insert_item(sel, desc2.name, onActivate=self._open_tilemap)
            self._menu.remove(moving)
            self._menu.insert_item(moving, desc1.name, onActivate=self._open_tilemap)
            self._update_menu()
            self._set_banner(ProjectScreen.DEFAULT_BANNER)
            self._layers.swap_tilemaps(sel, moving)
        else:
            try:
                self._open_settings(sel)
            except Exception as e:
                print(e)
                print_tb(e.__traceback__)
                if isinstance(e, cg.CrustyException):
                    self._set_error("Couldn't open tilemap: {}: {}".format(e, get_error()))
                else:
                    self._set_error("Couldn't open tilemap: {}".format(e))

    def _new_tilemap(self, priv, sel):
        self._descs.append(TilemapDesc())
        try:
            self._open_settings(len(self._descs) - 1)
        except Exception as e:
            print(e)
            print_tb(e.__traceback__)
            if isinstance(e, cg.CrustyException):
                self._set_error("Couldn't open tilemap: {}: {}".format(e, get_error()))
            else:
                self._set_error("Couldn't open tilemap: {}".format(e))
            # this could be -1 but keep it consistent in meaning with the call
            # to _open_settings() above.
            del self._descs[len(self._descs) - 1]

    def _set_scale(self, priv, sel, val):
        try:
            val = float(val)
        except ValueError:
            return None
        self._state.set_scale(val)
        if val < 1.0:
            return None
        return str(val)

    def apply(self, desc, force=False):
        if self._selected >= len(self._editors):
            self._add_editor(desc)
            self._update_menu()
        else:
            self._editors[self._selected].modify(desc, force)
            if desc.name != self._descs[self._selected].name:
                self._menu.remove(self._selected)
                self._menu.insert_item(self._selected, desc.name, onActivate=self._open_tilemap)
                self._update_menu()
        self._descs[self._selected] = desc

    def edit(self):
        self._state.active_screen(self._editors[self._selected])

    def set_wscale(self, scale):
        if self._selected >= len(self._editors):
            self._descs[self._selected].wscale = scale
        else:
            self._editors[self._selected].set_wscale(scale)
            self._descs[self._selected].wscale = self._editors[self._selected].wscale

    def set_hscale(self, scale):
        if self._selected >= len(self._editors):
            self._descs[self._selected].hscale = scale
        else:
            self._editors[self._selected].set_hscale(scale)
            self._descs[self._selected].hscale = self._editors[self._selected].hscale

    @property
    def wscale(self):
        return self._descs[self._selected].wscale

    @property
    def hscale(self):
        return self._descs[self._selected].hscale

    def delete(self):
        self._deleting = True

    def move(self):
        if self._selected >= len(self._editors):
            raise ValueError("Item not created yet, settings must be Applied at least once.")
        self._moving = self._selected

    def copy(self):
        if self._selected >= len(self._editors):
            raise ValueError("Item not created yet, settings must be Applied at least once.")
        desc = copy.deepcopy(self._descs[self._selected])
        self._add_editor(desc,
            tilemap=copy.copy(self._editors[self._selected].tilemap),
            flags=copy.copy(self._editors[self._selected].flags),
            colormod=copy.copy(self._editors[self._selected].colormod))

    def _open_layers(self, priv, sel):
        self._state.active_screen(self._layers)

    @property
    def descs(self):
        return self._descs

    @property
    def editors(self):
        return self._editors

    def _setname(self, priv, sel, val):
        name = val.lstrip().rstrip()
        if len(name) == 0:
            return None
        self._name = name
        return self._name

    def _get_filename(self):
        return "{}.json".format(self._name)

    def _save(self, priv, sel):
        flist = list()
        try:
            filename = self._get_filename()
            file = open(filename, "r")
            file.close()
            flist.append(filename)
        except OSError:
            pass
        for num in range(len(self._editors)):
            try:
                filename = "{} tilemap{}.bin".format(self._name, num)
                file = open(filename, 'r')
                file.close()
                flist.append(filename)
            except OSError:
                pass
            try:
                filename = "{} flags{}.bin".format(self._name, num)
                file = open(filename, 'r')
                file.close()
                flist.append(filename)
            except OSError:
                pass
            try:
                filename = "{} colormod{}.bin".format(self._name, num)
                file = open(filename, 'r')
                file.close()
                flist.append(filename)
            except OSError:
                pass
        if len(flist) == 0:
            self._do_save()
        else:
            self._saving = True
            liststr = "{}".format(flist[0])
            for name in flist[1:]:
                liststr = "{}, {}".format(liststr, name)
            prompt = PromptScreen(self._state, self, "Save?", ("yes", "no"), message="The following files exist and would be overwritten: {}".format(liststr), default=1)
            self._state.active_screen(prompt)

    def _do_save(self):
        savedata = {'ui_scale': self._state.font_scale}
        pscrollx, pscrolly = self._layers.scroll_pos
        savedata['preview_scroll_x'] = pscrollx
        savedata['preview_scroll_y'] = pscrolly
        tilemaps = list()
        for desc in self._descs:
            tilemaps.append({'name': desc.name,
                             'gfx': desc.filename,
                             'unimap': desc.mapname,
                             'tile_width': desc.tw,
                             'tile_height': desc.th,
                             'map_width': desc.mw,
                             'map_height': desc.mh,
                             'x_scale': desc.wscale,
                             'y_scale': desc.hscale})
        savedata['tilemaps'] = tilemaps
        layers = list()
        for layer in self._layers.layers:
            mode = 'NONE'
            if layer.mode == ScrollMode.POSITION:
                mode = 'POSITION'
            elif layer.mode == ScrollMode.LAYER:
                mode = 'LAYER'
            layers.append({'name': layer.name,
                           'tilemap': layer.tilemap,
                           'relative': layer.relative,
                           'view_width': layer.vw,
                           'view_height': layer.vh,
                           'x_scale': layer.scalex,
                           'y_scale': layer.scaley,
                           'mode': mode,
                           'x_pos': layer.posx,
                           'y_pos': layer.posy,
                           'x_scroll': layer.scrollx,
                           'y_scroll': layer.scrolly,
                           'colormod': layer.colormod,
                           'blend_mode': layer.blendmode})
        savedata['layers'] = layers
        with open("{}.json".format(self._name), 'w') as outfile:
            json.dump(savedata, outfile, indent=4)
        for num, editor in enumerate(self._editors):
            with open("{} tilemap{}.bin".format(self._name, num), 'wb') as outfile:
                editor.tilemap.tofile(outfile)
            with open("{} flags{}.bin".format(self._name, num), 'wb') as outfile:
                editor.flags.tofile(outfile)
            with open("{} colormod{}.bin".format(self._name, num), 'wb') as outfile:
                editor.colormod.tofile(outfile)

class TilemapScreen():
    def _build_screen(self):
        self._vw, self._vh = self._state.window
        self._fw = self._state.font.ts.width()
        self._fh = self._state.font.ts.height()
        self._scale = self._state.font_scale
        self._fmw = int(self._vw / self._scale / self._fw)
        self._fmh = int(self._vh / self._scale / self._fh)
        self._titletb = textbox.TextBox(self._state.ll,
                                        self._fmw * self._fw, 1 * self._fh,
                                        self._fmw, 1,
                                        self._state.font)
        put_centered_line(self._titletb, "Tilemap Settings", 0, self._fmw)
        self._titletb.layer.pos(int(self._fw * self._scale),
                                int(self._fh * self._scale))
        self._titletb.layer.scale(self._state.font_scale, self._state.font_scale)
        self._dl.replace(self._titletbindex, self._titletb.draw)
        self._menu = textbox.Menu(self._state.ll, self._state.font, self._fmw - 2, self._fmh - 3, None, spacing=2, rel=self._titletb.layer)
        self._menu.add_item("Apply and Edit", onActivate=self._edit)
        self._menu.add_item("Apply", onActivate=self._apply)
        self._menu.add_item("Name", value=self._tmdesc.name, maxlen=255, onEnter=self._setname)
        self._menu.add_item("Tileset", value=self._tmdesc.filename, maxlen=255, onEnter=self._setfilename)
        self._menu.add_item("Unicode Map", value=self._tmdesc.mapname, maxlen=255, onEnter=self._setmapname)
        self._menu.add_item("Tile Width", value=str(self._tmdesc.tw), maxlen=4, onEnter=self._settilewidth)
        self._menu.add_item("Tile Height", value=str(self._tmdesc.th), maxlen=4, onEnter=self._settileheight)
        self._menu.add_item("Map Width", value=str(self._tmdesc.mw), maxlen=4, onEnter=self._setmapwidth)
        self._menu.add_item("Map Height", value=str(self._tmdesc.mh), maxlen=4, onEnter=self._setmapheight)
        self._menu.add_item("View X Scale", value=str(self._caller.wscale), maxlen=5, onEnter=self._set_wscale)
        self._menu.add_item("View Y Scale", value=str(self._caller.hscale), maxlen=5, onEnter=self._set_hscale)
        self._menu.add_item("Move", onActivate=self._move)
        self._menu.add_item("Delete", onActivate=self._delete)
        self._menu.add_item("Copy", onActivate=self._copy)
        self._menu.update()
        mlayer, self._cursorl = self._menu.layers
        mlayer.pos(0, self._fh * 2)
        self._dl.replace(self._menuindex, self._menu.displaylist)

    def __init__(self, state, caller, tmdesc):
        self._state = state
        self._caller = caller
        self._tmdesc = tmdesc
        self._error = 0.0
        self._errortext = ''
        self._errorbox = None
        self._cursorrad = 0.0
        self._shrink = False
        self._editing = False
        self._deleting = False
        self._dl = display.DisplayList(self._state.ll)
        self._titletbindex = self._dl.append(None)
        self._menuindex = self._dl.append(None)
        self._errorindex = self._dl.append(None)
        self._build_screen()

    def _set_error(self, text):
        print(text)
        self._errortext = text
        self._error = ERROR_TIME

    @property
    def name(self):
        return self._name

    def resize(self):
        vw, vh = self._state.window
        scale = self._state.font_scale
        fw = self._state.font.ts.width()
        fh = self._state.font.ts.height()
        if self._fmw != int(vw / scale / fw) or \
           self._fmh != int(vh / scale / fh):
            self._build_screen()

    def active(self):
        self.resize()
        if self._shrink:
            self._shrink = False
            try:
                self._caller.apply(self._tmdesc, force=True)
            except Exception as e:
                print(e)
                print_tb(e.__traceback__)
                if isinstance(e, cg.CrustyException):
                    self._set_error("Couldn't save settings: {}: {}".format(e, get_error()))
                else:
                    self._set_error("Couldn't save settings: {}".format(e))
        elif self._deleting:
            self._caller.delete()
            self._state.active_screen(self._caller)

    @property
    def dl(self):
        return self._dl

    def input(self, event):
        if self._editing:
            self._editing = False
            self._caller.edit()
        elif event.type == SDL_TEXTINPUT:
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
                    self._state.active_screen(self._caller)

    def update(self, time):
        if self._error > 0.0:
            if self._errorbox is None:
                if len(self._errortext) == 0:
                    self._errortext = "Unknown error"
                lines, _, w, h = textbox.wrap_text(self._errortext, self._fmw - 2, 10)
                self._errorbox = textbox.TextBox(self._state.ll,
                                                 w * self._fw, h * self._fh,
                                                 w, h,
                                                 self._state.font)
                self._errorbox.put_text(lines, 0, 0)
                self._errorbox.layer.relative(self._titletb.layer)
                self._errorbox.layer.pos(0, int((self._fmh - h - 2) * self._fh))
                self._dl.replace(self._errorindex, self._errorbox.draw)
            self._error -= time
        if self._error <= 0.0 and self._errorbox is not None:
            self._dl.replace(self._errorindex, None)
            self._errorbox = None
            self._errortext = ''

        self._cursorrad, color = update_cursor_effect(self._cursorrad, time)
        self._cursorl.colormod(color)

    def _setname(self, priv, sel, val):
        name = val.lstrip().rstrip()
        if len(name) == 0:
            return None
        self._tmdesc.name = name
        return self._tmdesc.name

    def _setfilename(self, priv, sel, val):
        self._tmdesc.filename = val.lstrip().rstrip()
        return val

    def _settilewidth(self, priv, sel, val):
        try:
            val = int(val)
        except ValueError:
            return None
        if val < 1:
            return None
        self._tmdesc.tw = val
        return str(self._tmdesc.tw)

    def _settileheight(self, priv, sel, val):
        try:
            val = int(val)
        except ValueError:
            return None
        if val < 1:
            return None
        self._tmdesc.th = val
        return str(self._tmdesc.th)

    def _setmapwidth(self, priv, sel, val):
        try:
            val = int(val)
        except ValueError:
            return None
        if val < 1:
            return None
        self._tmdesc.mw = val
        return str(self._tmdesc.mw)

    def _setmapheight(self, priv, sel, val):
        try:
            val = int(val)
        except ValueError:
            return None
        if val < 1:
            return None
        self._tmdesc.mh = val
        return str(self._tmdesc.mh)

    def _setmapname(self, priv, sel, val):
        self._tmdesc.mapname = val.lstrip().rstrip()
        return val

    def _set_wscale(self, priv, sel, val):
        try:
            val = float(val)
        except ValueError:
            return None
        try:
            self._caller.set_wscale(val)
        except Exception as e:
            print(e)
            print_tb(e.__traceback__)
            if isinstance(e, cg.CrustyException):
                self._set_error("Couldn't set scale: {}: {}".format(e, get_error()))
            else:
                self._set_error("Couldn't set scale: {}".format(e))
            return None
        self._tmdesc.wscale = self._caller.wscale
        return str(self._caller.wscale)

    def _set_hscale(self, priv, sel, val):
        try:
            val = float(val)
        except ValueError:
            return None
        try:
            self._caller.set_hscale(val)
        except Exception as e:
            print(e)
            print_tb(e.__traceback__)
            if isinstance(e, cg.CrustyException):
                self._set_error("Couldn't set scale: {}: {}".format(e, get_error()))
            else:
                self._set_error("Couldn't set scale: {}".format(e))
            return None
        self._tmdesc.hscale = self._caller.hscale
        return str(self._caller.hscale)

    def set_option(self, sel):
        if self._deleting:
            if sel != 0:
                self._deleting = False
        else:
            if sel == 0:
                self._shrink = True
            else:
                # if canceled, don't proceed to edit
                self._editing = False

    def _apply(self, priv, sel):
        try:
            self._caller.apply(self._tmdesc)
        except TileMapShrunk:
            prompt = PromptScreen(self._state, self, "Continue?", ("yes", "no"), message="This operation will shrink the tilemap and lose any data that falls outside of the bottom and right edges, are you sure?", default=1)
            self._state.active_screen(prompt)
            return
        except Exception as e:
            print(e)
            print_tb(e.__traceback__)
            if isinstance(e, cg.CrustyException):
                self._set_error("Couldn't save settings: {}: {}".format(e, get_error()))
            else:
                self._set_error("Couldn't save settings: {}".format(e))
            self._editing = False
            return
        if self._editing:
            self._editing = False
            self._caller.edit()

    def _edit(self, priv, sel):
        self._editing = True
        self._apply(priv, sel)

    def _move(self, priv, sel):
        try:
            self._caller.move()
            self._state.active_screen(self._caller)
        except Exception as e:
            print(e)
            print_tb(e.__traceback__)
            if isinstance(e, cg.CrustyException):
                self._set_error("Couldn't move: {}: {}".format(e, get_error()))
            else:
                self._set_error("Couldn't move: {}".format(e))

    def _delete(self, priv, sel):
        self._deleting = True
        prompt = PromptScreen(self._state, self, "Continue?", ("yes", "no"), message="This operation will delete this tilemap and it cannot be reversed, are you sure?", default=1)
        self._state.active_screen(prompt)

    def _copy(self, priv, sel):
        try:
            self._caller.copy()
            self._state.active_screen(self._caller)
        except Exception as e:
            print(e)
            print_tb(e.__traceback__)
            if isinstance(e, cg.CrustyException):
                self._set_error("Couldn't copy: {}: {}".format(e, get_error()))
            else:
                self._set_error("Couldn't copy: {}".format(e))
        
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
                          self._tmdesc.mw, self._tmdesc.mh,
                          self._curx, self._cury)
        self._stm.scroll(xscroll * self._tmdesc.tw, yscroll * self._tmdesc.th)
        self._stm.update()
        self._cursorl.pos(int(x * self._tmdesc.tw - (self._fw / self._tmdesc.wscale * self._state.font_scale / 2)),
                          int(y * self._tmdesc.th - (self._fh / self._tmdesc.hscale * self._state.font_scale / 2)))
        self._statustext.put_text(("    ", "    "), 3, 1)
        self._statustext.put_text((str(self._curx), str(self._cury)), 3, 1)
        if self._border is not None:
            self._border.scroll(xscroll, yscroll)

    def _update_sidebar(self):
        self._sidebar.update(self._curpos,
                             self._curx * self._tmdesc.wscale * self._tmdesc.tw,
                             self._tmdesc.mw * self._tmdesc.tw * self._tmdesc.wscale)

    def _make_selectscreen(self):
        width = 0
        if self._selectscreen is not None:
            width = self._selectscreen.width
        self._selectscreen = TileSelectScreen(self._state, self, self._tsdesc, width=width)

    def _make_sidebar(self):
        scale = self._state.font_scale
        self._sidebar = Sidebar(self._state, "h - Toggle Sidebar\nESC - Quit\nArrows - Move\nSPACE - Place*\n  *=Fill Selection\nSHIFT+SPACE\n  Grab/Copy\nNumpad Plus\n  Increase Tile\nNumpad Minus\n  Decrease Tile\nc - Open Color Picker\nC - Grab/Copy Color\nCTRL+c - Place Color*\nv - Open Tile Picker\nV - Grab/Copy Tile\nCTRL+v - Place Tile*\nr - Cycle Rotation\nt - Toggle Horiz Flip\ny - Toggle Vert Flip\nB - Grab/Copy\n  Attributes\nCTRL+b\n  Place Attributes*\nq/a - Adjust Red\nw/s - Adjust Green\ne/d - Adjust Blue\nx/z - Adjust Alpha\nf - Top Left Select\ng - Bottom Right\n  Select\nu/U - Undo/Redo\np - Put Copy\ni - Insert Text\nCTRL+r - Reload\n  Tileset")
        pwidth = self._tmdesc.tw * scale / self._fw
        if pwidth.is_integer():
            pwidth = int(pwidth)
        else:
            pwidth = int(pwidth) + 1
        pheight = self._tmdesc.th * scale / self._fh
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
        self._statustext = textbox.TextBox(self._state.ll,
                                           self._sidebar.width - 2 * self._fw,
                                           h * self._fh,
                                           self._sidebar.width - 2, h,
                                           self._state.font)
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
        self._dl.replace(self._sidebarindex, self._sidebar.dl)
        self._dl.replace(self._statusindex, self._statustext.draw)

    def _set_tmdesc(self, tmdesc):
        if self._tmdesc is not None and \
           (self._tmdesc.filename != tmdesc.filename or \
            self._tmdesc.tw != tmdesc.tw or \
            self._tmdesc.th != tmdesc.th):
            self._state.remove_tileset(self._tsdesc)
            self._tmdesc = None
        if self._tmdesc is None:
            self._tsdesc = self._state.add_tileset(tmdesc.filename,
                                                   tmdesc.tw, tmdesc.th)
            self._make_selectscreen()
        self._tmdesc = tmdesc
        self._tileset = self._state.tileset_desc(self._tsdesc)
        self._tiles = self._tileset.tiles()
        codec = None
        if self._codec is not None:
            if self._tmdesc.mapname is not None:
                codec = textbox.load_tileset_codec(self._tmdesc.mapname,
                                                   maxval=self._tiles)
                textbox.unload_tileset_codec(self._codec)
            else:
                textbox.unload_tileset_codec(self._codec)
        self._codec = codec
        vw, vh = self._state.window
        self._vw = int(vw / self._tmdesc.wscale / self._tmdesc.tw)
        self._vh = int(vh / self._tmdesc.hscale / self._tmdesc.th)
        self._make_sidebar()

    def _make_stm(self):
        self._curx, self._cury, self._stm = \
            make_tilemap(self._state.ll,
                         self._vw, self._vh,
                         self._tmdesc.mw, self._tmdesc.mh,
                         0, 0,
                         self._tileset, self._tilemap,
                         flags=self._flags, colormod=self._colormod)
        self._stm.layer.scale(self._tmdesc.wscale, self._tmdesc.hscale)
        curwidth, curheight = cursor_dims(self._tmdesc.tw, self._tmdesc.th,
                                          self._tmdesc.wscale, self._tmdesc.hscale,
                                          self._fw, self._fh,
                                          self._state.font_scale)
        self._cursortm = self._state.font.ts.tilemap(curwidth, curheight, "MapEditor Cursor Tilemap")
        ctm = make_box(self._state.font.codec, curwidth, curheight)
        self._cursortm.map(0, 0, curwidth, curwidth, curheight, ctm)
        self._cursortm.update()
        self._cursorl = self._cursortm.layer("Map Editor Cursor Layer")
        self._cursorl.relative(self._stm.layer)
        self._cursorl.scale(1 / self._tmdesc.wscale * self._state.font_scale, 1 / self._tmdesc.hscale * self._state.font_scale)
        self._dl.replace(self._cursorindex, self._cursorl)
        if self._border is not None:
            self._border.relative(self._stm.layer)
        self._dl.replace(self._stmindex, self._stm.draw)
        self._update_cursor()

    def _make_border(self, x, y, w, h):
        vw = self._vw
        if vw > self._tmdesc.mw:
            vw = self._tmdesc.mw
        vh = self._vh
        if vh > self._tmdesc.mh:
            vh = self._tmdesc.mh
        self._border = BorderSelector(self._state, vw, vh,
                                      self._tmdesc.mw, self._tmdesc.mh,
                                      self._tmdesc.tw, self._tmdesc.th,
                                      x, y,
                                      x + w - 1, y + h - 1)
        _, _, x, y, _, _ = update_cursor(self._vw, self._vh,
                                         self._tmdesc.mw, self._tmdesc.mh,
                                         self._curx, self._cury)
        self._border.scroll(x, y)
        self._border.layer.relative(self._stm.layer)
        self._dl.replace(self._borderindex, self._border.draw)

    def set_wscale(self, scale):
        if scale < 1.0:
            raise ValueError("Scale too small.")
        if scale != self._tmdesc.wscale:
            self._tmdesc.wscale = scale
            vw, _ = self._state.window
            self._vw = int(vw / self._tmdesc.wscale / self._tmdesc.tw)
            self._make_stm()

    def set_hscale(self, scale):
        if scale < 1.0:
            raise ValueError("Scale too small.")
        if scale != self._tmdesc.hscale:
            self._tmdesc.hscale = scale
            _, vh = self._state.window
            self._vh = int(vh / self._tmdesc.hscale / self._tmdesc.th)
            self._make_stm()

    @property
    def wscale(self):
        return self._tmdesc.wscale

    @property
    def hscale(self):
        return self._tmdesc.hscale

    def _build_screen(self):
        vw, vh = self._state.window
        self._fw = self._state.font.ts.width()
        self._fh = self._state.font.ts.height()
        scale = self._state.font_scale
        self._fmw = int(vw / scale / self._fw)
        self._fmh = int(vh / scale / self._fh)
        self._vw = int(vw / self._tmdesc.wscale / self._tmdesc.tw)
        self._vh = int(vh / self._tmdesc.hscale / self._tmdesc.th)
        self._make_sidebar()
        self._make_stm()

    def __init__(self, state, caller, tmdesc, tilemap=None, flags=None, colormod=None):
        self._state = state
        self._caller = caller
        self._cursorrad = 0.0
        self._fxcolor = 0
        self._curx = 0
        self._cury = 0
        self._tile = 0
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
        self._codec = None
        self._tmdesc = None
        self._tsdesc = None
        self._fw = self._state.font.ts.width()
        self._fh = self._state.font.ts.height()
        self._dl = display.DisplayList(self._state.ll)
        self._stmindex = self._dl.append(None)
        self._cursorindex = self._dl.append(None)
        self._borderindex = self._dl.append(None)
        self._sidebarindex = self._dl.append(None)
        self._statusindex = self._dl.append(None)
        self._errorindex = self._dl.append(None)
        self._color = display.make_color(self._red, self._green, self._blue, self._alpha)
        self._attrib = display.make_attrib(self._hflip, self._vflip, self._rotate)
        self._set_tmdesc(tmdesc)
        if tilemap is None:
            self._tilemap = array.array('I', itertools.repeat(0, self._tmdesc.mw * self._tmdesc.mh))
        else:
            self._tilemap = tilemap
        if flags is None:
            self._flags = array.array('I', itertools.repeat(self._attrib, self._tmdesc.mw * self._tmdesc.mh))
        else:
            self._flags = flags
        if colormod is None:
            self._colormod = array.array('I', itertools.repeat(self._color, self._tmdesc.mw * self._tmdesc.mh))
        else:
            self._colormod = colormod
        self._errordl = display.DisplayList(self._state.ll)
        self._errordl.append(lambda: self._errorbox.layer.pos(self._fw + 1, self._errorh + 1))
        self._errordl.append(lambda: self._errorbox.layer.colormod(display.make_color(0, 0, 0, SDL_ALPHA_OPAQUE)))
        self._errordlindex1 = self._errordl.append(None)
        self._errordl.append(lambda: self._errorbox.layer.pos(self._fw, self._errorh))
        self._errordl.append(lambda: self._errorbox.layer.colormod(self._fxcolor))
        self._errordlindex2 = self._errordl.append(None)
        self._build_screen()

    def __del__(self):
        if self._codec is not None:
            textbox.unload_tileset_codec(self._codec)
        if self._tsdesc is not None:
            self._state.remove_tileset(self._tsdesc)

    def _set_error(self, text):
        print(text)
        self._errortext = text
        self._error = ERROR_TIME

    def resize(self):
        vw, vh = self._state.window
        scale = self._state.font_scale
        fw = self._state.font.ts.width()
        fh = self._state.font.ts.height()
        if self._fmw != int(vw / scale / fw) or \
           self._fmh != int(vh / scale / fh) or \
           self._vw != int(vw / self._tmdesc.wscale / self._tmdesc.tw) or \
           self._vh != int(vh / self._tmdesc.hscale / self._tmdesc.th):
            self._build_screen()
            if self._border is not None:
                x, y, w, h = self._border.get_selection()
                self._make_border(self._curx, self._cury, 1, 1)
    
    def active(self):
        self.resize()

    def _get_tilemap_rect(self, x, y, w, h):
        rect = array.array('I')
        for num in range(h):
            rect.extend(self._tilemap[(self._tmdesc.mw*(y+num))+x:(self._tmdesc.mw*(y+num))+x+w])
        return rect

    def _get_colormod_rect(self, x, y, w, h):
        rect = array.array('I')
        for num in range(h):
            rect.extend(self._colormod[(self._tmdesc.mw*(y+num))+x:(self._tmdesc.mw*(y+num))+x+w])
        return rect

    def _get_flags_rect(self, x, y, w, h):
        rect = array.array('I')
        for num in range(h):
            rect.extend(self._flags[(self._tmdesc.mw*(y+num))+x:(self._tmdesc.mw*(y+num))+x+w])
        return rect

    def _get_region(self, x, y, w, h):
        tilemap = self._get_tilemap_rect(x, y, w, h)
        colormod = self._get_colormod_rect(x, y, w, h)
        flags = self._get_flags_rect(x, y, w, h)
        return MapChange(x, y, w, h, tilemap, colormod, flags)

    def _store_region(self, x, y, w, h):
        orig = self._get_region(x, y, w, h)
        if self._undopos + 1 < len(self._undo):
            self._undo = self._undo[:self._undopos + 1]
        self._undo.append(orig)
        self._undopos += 1
        if self._undopos > EditScreen.MAX_UNDO:
            del self._undo[0]
            self._undopos = EditScreen.MAX_UNDO

    def _apply_change(self, change, store=True):
        if store:
            self._store_region(change.x, change.y, change.w, change.h)
        if change.tilemap is not None:
            for num in range(change.h):
                self._tilemap[(self._tmdesc.mw*(change.y+num))+change.x:(self._tmdesc.mw*(change.y+num))+change.x+change.w] = change.tilemap[change.w*num:(change.w*num)+change.w]
        if change.colormod is not None:
            for num in range(change.h):
                self._colormod[(self._tmdesc.mw*(change.y+num))+change.x:(self._tmdesc.mw*(change.y+num))+change.x+change.w] = change.colormod[change.w*num:(change.w*num)+change.w]
        if change.flags is not None:
            for num in range(change.h):
                self._flags[(self._tmdesc.mw*(change.y+num))+change.x:(self._tmdesc.mw*(change.y+num))+change.x+change.w] = change.flags[change.w*num:(change.w*num)+change.w]
        self._stm.updateregion(change.x, change.y, change.w+1, change.h+1)

    def _do_undo(self):
        if self._undopos >= 0:
            orig = self._get_region(self._undo[self._undopos].x,
                                    self._undo[self._undopos].y,
                                    self._undo[self._undopos].w,
                                    self._undo[self._undopos].h)
            self._apply_change(self._undo[self._undopos], store=False)
            self._undo[self._undopos] = orig
            self._undopos -= 1

    def _do_redo(self):
        if self._undopos + 1 < len(self._undo):
            orig = self._get_region(self._undo[self._undopos + 1].x,
                                    self._undo[self._undopos + 1].y,
                                    self._undo[self._undopos + 1].w,
                                    self._undo[self._undopos + 1].h)
            self._apply_change(self._undo[self._undopos + 1], store=False)
            self._undo[self._undopos + 1] = orig
            self._undopos += 1

    def _check_drawing(self):
        if self._drawing:
            if self._tilemap[self._cury * self._tmdesc.mw + self._curx] != self._tile or \
               self._colormod[self._cury * self._tmdesc.mw + self._curx] != self._color or \
               self._flags[self._cury * self._tmdesc.mw + self._curx] != self._attrib:
                self._store_region(self._curx, self._cury, 1, 1)
                self._tilemap[self._cury * self._tmdesc.mw + self._curx] = self._tile
                self._colormod[self._cury * self._tmdesc.mw + self._curx] = self._color
                self._flags[self._cury * self._tmdesc.mw + self._curx] = self._attrib
                self._stm.updateregion(self._curx, self._cury, 1, 1)
        else:
            if (self._puttile and self._tilemap[self._cury * self._tmdesc.mw + self._curx] != self._tile) or \
               (self._putcolor and self._colormod[self._cury * self._tmdesc.mw + self._curx] != self._color) or \
               (self._putattrib and self._flags[self._cury * self._tmdesc.mw + self._curx] != self._attrib):
                self._store_region(self._curx, self._cury, 1, 1)
                if self._puttile:
                    self._tilemap[self._cury * self._tmdesc.mw + self._curx] = self._tile
                if self._putcolor:
                    self._colormod[self._cury * self._tmdesc.mw + self._curx] = self._color
                if self._putattrib:
                    self._flags[self._cury * self._tmdesc.mw + self._curx] = self._attrib
                self._stm.updateregion(self._curx, self._cury, 1, 1)

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
        maxy = self._tmdesc.mh
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
            w = self._tmdesc.mw
            h = self._tmdesc.mh
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
            if self._curx > self._tmdesc.mw - 1:
                self._curx = self._tmdesc.mw - 1
        self._update_cursor()
        self._update_sidebar()
        self._check_drawing()

    def _return(self):
        maxy = self._tmdesc.mh
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
                self._tilemap[self._cury * self._tmdesc.mw + self._curx] = val
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
                            self._tile = self._tilemap[self._cury * self._tmdesc.mw + self._curx]
                            self._color = self._colormod[self._cury * self._tmdesc.mw + self._curx]
                            self._attrib = self._flags[self._cury * self._tmdesc.mw + self._curx]
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
                            self._store_region(x, y, w, h)
                            for num in range(h):
                                self._tilemap[self._tmdesc.mw*(y+num)+x:self._tmdesc.mw*(y+num)+x+w] = array.array('I', itertools.repeat(self._tile, w))
                                self._colormod[self._tmdesc.mw*(y+num)+x:self._tmdesc.mw*(y+num)+x+w] = array.array('I', itertools.repeat(self._color, w))
                                self._flags[self._tmdesc.mw*(y+num)+x:self._tmdesc.mw*(y+num)+x+w] = array.array('I', itertools.repeat(self._attrib, w))
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
                            self._tile = self._tilemap[self._cury * self._tmdesc.mw + self._curx]
                            self._update_tile()
                    elif event.key.keysym.mod & KMOD_CTRL != 0:
                        if self._border is not None:
                            x, y, w, h = self._border.get_selection()
                            self._store_region(x, y, w, h)
                            for num in range(h):
                                self._tilemap[self._tmdesc.mw*(y+num)+x:self._tmdesc.mw*(y+num)+x+w] = array.array('I', itertools.repeat(self._tile, w))
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
                            self._color = self._colormod[self._cury * self._tmdesc.mw + self._curx]
                            self._red, self._green, self._blue, self._alpha = display.unmake_color(self._color)
                            self._update_red()
                            self._update_green()
                            self._update_blue()
                            self._update_alpha()
                    elif event.key.keysym.mod & KMOD_CTRL != 0:
                        if self._border is not None:
                            x, y, w, h = self._border.get_selection()
                            self._store_region(x, y, w, h)
                            for num in range(h):
                                self._colormod[self._tmdesc.mw*(y+num)+x:self._tmdesc.mw*(y+num)+x+w] = array.array('I', itertools.repeat(self._color, w))
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
                            self._attrib = self._flags[self._cury * self._tmdesc.mw + self._curx]
                            self._hflip, self._vflip, self._rotate = display.unmake_attrib(self._attrib)
                            self._update_hflip()
                            self._update_vflip()
                            self._update_rotation()
                    elif event.key.keysym.mod & KMOD_CTRL != 0:
                        if self._border is not None:
                            x, y, w, h = self._border.get_selection()
                            self._store_region(x, y, w, h)
                            for num in range(h + 1):
                                self._flags[self._tmdesc.mw*(y+num)+x:self._tmdesc.mw*(y+num)+x+w] = array.array('I', itertools.repeat(self._attrib, w))
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
                            if self._codec is not None and \
                               self._tileset.tiles() < textbox.get_codec_max_map(self._codec):
                                raise ValueError("Tileset has insufficient tiles for tilemap codec.")
                        except Exception as e:
                            print(e)
                            print_tb(e.__traceback__)
                            if isinstance(e, cg.CrustyException):
                                self._set_error("Couldn't load tileset: {}: {}".format(e, get_error()))
                            else:
                                self._set_error("Couldn't load tileset: {}".format(e))
                            self._tileset = self._state.reload_tileset(self._tsdesc, tileset)
                            return
                        try:
                            self._make_stm()
                        except Exception as e:
                            print(e)
                            print_tb(e.__traceback__)
                            if isinstance(e, cg.CrustyException):
                                self._set_error("Couldn't make tilemap: {}: {}".format(e, get_error()))
                            else:
                                self._set_error("Couldn't make tilemap: {}".format(e))
                            self._tileset = self._state.reload_tileset(self._tsdesc, tileset)
                            self._make_stm()
                            return
                        self._tiles = self._tileset.tiles()
                        self._make_selectscreen()
                    else:
                        if self._rotate == cg.TILEMAP_ROTATE_NONE:
                            if self._tmdesc.tw == self._tmdesc.th:
                                self._rotate = cg.TILEMAP_ROTATE_90
                            else:
                                self._rotate = cg.TILEMAP_ROTATE_180
                        elif self._rotate == cg.TILEMAP_ROTATE_90:
                            self._rotate = cg.TILEMAP_ROTATE_180
                        elif self._rotate == cg.TILEMAP_ROTATE_180:
                            if self._tmdesc.tw == self._tmdesc.th:
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
                        self._dl.replace(self._statusindex, self._statustext.draw)
                        self._sidebar.show_text(False)
                        self._showsidebar = 1
                    elif self._showsidebar == 1:
                        self._sidebar.show_text(True)
                        self._showsidebar = 2
                    else:
                        self._dl.replace(self._sidebarindex, None)
                        self._dl.replace(self._statusindex, None)
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
                        self._state.active_screen(self._caller)
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
                self._errorbox = textbox.TextBox(self._state.ll,
                                                 w * self._fw, h * self._fh,
                                                 w, h,
                                                 self._state.font)
                self._errorbox.put_text(lines, 0, 0)
                self._errorbox.layer.relative(self._stm.layer)
                self._errorh = (self._fmh - h - 1) * self._fh
                self._errordl.replace(self._errordlindex1, self._errorbox.draw)
                self._errordl.replace(self._errordlindex2, self._errorbox.draw)
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
            self._border.internal.colormod(self._fxcolor)
        if self._errorbox is not None:
            self._errorbox.layer.colormod(self._fxcolor)

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

    def modify(self, desc, force):
        if desc.mw != self._tmdesc.mw or \
           desc.mh != self._tmdesc.mh:
            if (desc.mw < self._tmdesc.mw or \
                desc.mh < self._tmdesc.mh) and \
               not force:
                raise TileMapShrunk
            tilemap = array.array('I', itertools.repeat(self._tile, desc.mw * desc.mh))
            colormod = array.array('I', itertools.repeat(self._color, desc.mw * desc.mh))
            flags = array.array('I', itertools.repeat(self._attrib, desc.mw * desc.mh))
            if desc.mw < self._tmdesc.mw:
                for y in range(desc.mh):
                    tilemap[y*desc.mw:(y*desc.mw)+desc.mw] = self._tilemap[y*self._tmdesc.mw:(y*self._tmdesc.mw)+desc.mw]
                    colormod[y*desc.mw:(y*desc.mw)+desc.mw] = self._colormod[y*self._tmdesc.mw:(y*self._tmdesc.mw)+desc.mw]
                    flags[y*desc.mw:(y*desc.mw)+desc.mw] = self._flags[y*self._tmdesc.mw:(y*self._tmdesc.mw)+desc.mw]
            else:
                for y in range(desc.mh):
                    tilemap[y*desc.mw:(y*desc.mw)+self._tmdesc.mw] = self._tilemap[y*self._tmdesc.mw:(y*self._tmdesc.mw)+self._tmdesc.mw]
                    colormod[y*desc.mw:(y*desc.mw)+self._tmdesc.mw] = self._colormod[y*self._tmdesc.mw:(y*self._tmdesc.mw)+self._tmdesc.mw]
                    flags[y*desc.mw:(y*desc.mw)+self._tmdesc.mw] = self._flags[y*self._tmdesc.mw:(y*self._tmdesc.mw)+self._tmdesc.mw]
            self._tilemap = tilemap
            self._colormod = colormod
            self._flags = flags
        self._set_tmdesc(desc)
        self._make_stm()

    @property
    def tilemap(self):
        return self._tilemap

    @property
    def flags(self):
        return self._flags

    @property
    def colormod(self):
        return self._colormod

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
            make_tilemap(self._state.ll,
                         self._vw, self._vh,
                         self._mw, self._mh,
                         self._curx, self._cury,
                         self._tileset, tilemap,
                         colormod=colormod)
        if self._cury * self._mw + self._curx >= self._tiles:
            self._cury = self._tiles // self._mw - 1
        self._stm.layer.scale(self._scale, self._scale)
        self._dl.replace(self._tmindex, self._stm.draw)
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
        self._fmw = int(vw / self._scale / self._fw)
        self._fmh = int(vh / self._scale / self._fh)
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
        self._tileset = self._state.tileset_desc(ts)
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

    def resize(self):
        vw, vh = self._state.window
        scale = self._state.font_scale
        fw = self._state.font.ts.width()
        fh = self._state.font.ts.height()
        if self._fmw != int(vw / scale / fw) or \
           self._fmh != int(vh / scale / fh) or \
           self._vw != int(vw / scale / self._tw) or \
           self._vh != int(vh / scale / self._th):
            self._build_screen()

    def active(self):
        self.resize()

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

class ColorPickerScreen():
    def _build_screen(self):
        vw, vh = self._state.window
        scale = self._state.font_scale
        fw = self._state.font.ts.width()
        fh = self._state.font.ts.height()
        vw = int(vw / scale / fw)
        vh = int(vh / scale / fh)
        self._dl = display.DisplayList(self._state.ll)
        titletb = textbox.TextBox(self._state.ll,
                                  vw * fw, 1 * fh,
                                  vw, 1, self._state.font)
        titletb.layer.scale(scale, scale)
        titletb.layer.pos(int(fw * scale), int(fh * scale))
        put_centered_line(titletb, "Pick Color", 0, vw - 2)
        self._dl.append(titletb.draw)
        self._menu = textbox.Menu(self._state.ll, self._state.font, vw - 2, vw - 3, None, spacing=2, rel=titletb.layer)
        self._menu.add_item("Red", value=str(self._red), maxlen=3, onEnter=self.setred, onChange=self.changered)
        self._menu.add_item("Green", value=str(self._green), maxlen=3, onEnter=self.setgreen, onChange=self.changegreen)
        self._menu.add_item("Blue", value=str(self._blue), maxlen=3, onEnter=self.setblue, onChange=self.changeblue)
        self._menu.add_item("Alpha", value=str(self._alpha), maxlen=3, onEnter=self.setalpha, onChange=self.changealpha)
        self._menu.add_item("Accept", onActivate=self._accept)
        self._menu.update()
        mlayer, self._cursorl = self._menu.layers
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
                if not self._menu.cancel_entry():
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

class ScrollMode(Enum):
    NONE = 0
    LAYER = 1
    POSITION = 2

@dataclass
class LayerDesc():
    name : str = "Untitled Layer"
    tilemap : int = -1 
    relative : int = -1
    vw : int = 1
    vh : int = 1
    scalex : float = 1.0
    scaley : float = 1.0
    mode : ScrollMode = ScrollMode.NONE
    posx : int = 0
    posy : int = 0
    scrollx : int = 0
    scrolly : int = 0
    colormod : int = 2**32-1 # 0xFFFFFFFF opaque white
    blendmode : int = cg.TILEMAP_BLENDMODE_BLEND

class LayersScreen():
    DEFAULT_BANNER="Layers"

    def _set_banner(self, s):
        self._titletb.clear()
        put_centered_line(self._titletb, s, 0, self._fmw)

    def _build_screen(self):
        self._vw, self._vh = self._state.window
        self._fw = self._state.font.ts.width()
        self._fh = self._state.font.ts.height()
        self._scale = self._state.font_scale
        self._fmw = int(self._vw / self._scale / self._fw)
        self._fmh = int(self._vh / self._scale / self._fh)
        self._titletb = textbox.TextBox(self._state.ll,
                                        self._fmw * self._fw, 1 * self._fh,
                                        self._fmw, 1,
                                        self._state.font)
        self._set_banner(ProjectScreen.DEFAULT_BANNER)
        self._titletb.layer.pos(int(self._fw * self._scale),
                                int(self._fh * self._scale))
        self._titletb.layer.scale(self._state.font_scale, self._state.font_scale)
        self._dl = display.DisplayList(self._state.ll)
        self._dl.append(display.Renderable(self._titletb.draw,
                                           always=False))
        self._menu = textbox.Menu(self._state.ll, self._state.font, self._fmw - 2, self._fmh - 3, None, rel=self._titletb.layer)
        for desc in self._descs:
            self._menu.add_item(desc.name, onActivate=self._open_layer)
        self._menu.add_item("New Layer", onActivate=self._new_layer)
        self._menu.add_item("Show Preview", onActivate=self._show)
        self._menu.add_item("", value="Preview Screen Controls")
        self._menu.add_item("Arrows", value="Adjust Position")
        self._menu.add_item("r", value="Reset Position")
        self._menu.add_item("Escape", value="Return to this screen")
        self._menu.update()
        mlayer, self._cursorl = self._menu.layers
        mlayer.pos(0, self._fh * 2)
        self._dl.append(self._menu.displaylist)
        self._errorindex = self._dl.append(None)

    def __init__(self, state, caller):
        self._state = state
        self._caller = caller
        self._descs = list()
        self._selected = 0
        self._deleting = False
        self._moving = -1
        self._cursorrad = 0.0
        self._error = 0.0
        self._errortext = ''
        self._errorbox = None
        self._posx = 0
        self._posy = 0
        self._build_screen()

    def _set_error(self, text):
        print(text)
        self._errortext = text
        self._error = ERROR_TIME

    @property
    def dl(self):
        return self._dl

    def resize(self):
        vw, vh = self._state.window
        scale = self._state.font_scale
        fw = self._state.font.ts.width()
        fh = self._state.font.ts.height()
        if scale != self._scale or \
           self._fmw != int(vw / scale / fw) or \
           self._fmh != int(vh / scale / fh):
            self._build_screen()

    def _update_menu(self):
        self._menu.update()
        mlayer, _ = self._menu.layers
        mlayer.pos(0, self._fh * 2)

    def active(self):
        self.resize()
        if self._deleting:
            self._deleting = False
            del self._descs[self._selected]
            self._menu.remove(self._selected)
            self._update_menu()
        elif self._moving >= 0:
            self._set_banner("Swap with?")

    def input(self, event):
        if event.type == SDL_KEYDOWN:
            self._state.changed()
            self._error = 0.0
            if event.key.keysym.sym == SDLK_UP:
                self._menu.up()
            elif event.key.keysym.sym == SDLK_DOWN:
                self._menu.down()
            elif event.key.keysym.sym == SDLK_RETURN:
                if self._moving >= 0 and \
                   self._menu.selection >= len(self._descs):
                    self._set_error("Can't swap with a selection that isn't a layer, use ESCAPE to cancel move.")
                    return
                self._menu.activate_selection()
            elif event.key.keysym.sym == SDLK_ESCAPE:
                if not self._menu.cancel_entry():
                    if self._moving >= 0:
                        self._moving = -1
                        self._set_banner(ProjectScreen.DEFAULT_BANNER)
                    else:
                        self._state.active_screen(self._caller)

    def update(self, time):
        if self._error > 0.0:
            if self._errorbox is None:
                if len(self._errortext) == 0:
                    self._errortext = "Unknown error"
                lines, _, w, h = textbox.wrap_text(self._errortext, self._fmw - 2, 10)
                self._errorbox = textbox.TextBox(self._state.ll,
                                                 w * self._fw, h * self._fh, w, h,
                                                 self._state.font)
                self._errorbox.put_text(lines, 0, 0)
                self._errorbox.layer.relative(self._titletb.layer)
                self._errorbox.layer.pos(0, int((self._fmh - h - 2) * self._fh))
                self._dl.replace(self._errorindex, self._errorbox.draw)
            self._error -= time
        if self._error <= 0.0 and self._errorbox is not None:
            self._dl.replace(self._errorindex, None)
            self._errorbox = None
            self._errortext = ''

        self._cursorrad, color = update_cursor_effect(self._cursorrad, time)
        self._cursorl.colormod(color)

    def _open_settings(self, sel):
        self._selected = sel
        # make a copy so the original stays unmodified
        desc = copy.deepcopy(self._descs[sel])
        layerscreen = LayerScreen(self._state, self, desc)
        self._state.active_screen(layerscreen)

    def _open_layer(self, priv, sel):
        if self._moving >= 0:
            if sel == self._moving:
                self._set_error("Can't swap with same layer, use ESCAPE to cancel move.")
                return
            moving = self._moving
            self._moving = -1
            desc1 = self._descs[sel]
            desc2 = self._descs[moving]
            self._descs[sel] = desc2
            self._descs[moving] = desc1
            self._menu.remove(sel)
            self._menu.insert_item(sel, desc2.name, onActivate=self._open_layer)
            self._menu.remove(moving)
            self._menu.insert_item(moving, desc1.name, onActivate=self._open_layer)
            self._update_menu()
            self._set_banner(ProjectScreen.DEFAULT_BANNER)
        else:
            try:
                self._open_settings(sel)
            except Exception as e:
                print(e)
                print_tb(e.__traceback__)
                if isinstance(e, cg.CrustyException):
                    self._set_error("Couldn't open layer: {}: {}".format(e, get_error()))
                else:
                    self._set_error("Couldn't open layer: {}".format(e))

    def add_layer(self, desc):
        self._descs.append(desc)
        self._menu.insert_item(len(self._descs) - 1, self._descs[-1].name, onActivate=self._open_layer)
        self._update_menu()

    def _new_layer(self, priv, sel):
        self.add_layer(LayerDesc())
        self._open_settings(len(self._descs) - 1)

    def _show(self, priv, sel):
        try:
            preview = PreviewScreen(self._state, self, self._posx, self._posy)
            self._state.active_screen(preview)
        except Exception as e:
            print(e)
            print_tb(e.__traceback__)
            if isinstance(e, cg.CrustyException):
                self._set_error("Couldn't open preview: {}: {}".format(e, get_error()))
            else:
                self._set_error("Couldn't open preview: {}".format(e))

    def setpos(self, x, y):
        self._posx = x
        self._posy = y

    def apply(self, desc):
        if desc.name != self._descs[self._selected].name:
            self._menu.remove(self._selected)
            self._menu.insert_item(self._selected, desc.name, onActivate=self._open_layer)
            self._update_menu()
        self._descs[self._selected] = desc

    def delete(self):
        self._deleting = True

    def move(self):
        self._moving = self._selected

    @property
    def layers(self):
        return self._descs

    @property
    def tmdescs(self):
        return self._caller.descs

    @property
    def editors(self):
        return self._caller.editors

    @property
    def selected(self):
        return self._selected

    def delete_tilemap(self, tm):
        for desc in self._descs:
            if desc.tilemap == tm:
                desc.tilemap = -1

    def swap_tilemaps(self, tm1, tm2):
        for desc in self._descs:
            if desc.tilemap == tm1:
                desc.tilemap = tm2
            elif desc.tilemap == tm2:
                desc.tilemap = tm1

    @property
    def scroll_pos(self):
        return self._posx, self._posy

    def set_scroll(self, x, y):
        self._posx = x
        self._posy = y

class LayerScreenSelecting(Enum):
    NONE = 0
    TILEMAP = 1
    RELATIVE = 2

class LayerScreen():
    SCROLL_MODE_NONE="No Scrolling"
    SCROLL_MODE_LAYER="Layer Scrolling"
    SCROLL_MODE_POS="Position Scrolling"

    def get_scroll_mode(mode):
        if mode == ScrollMode.NONE:
            return LayerScreen.SCROLL_MODE_NONE
        elif mode == ScrollMode.LAYER:
            return LayerScreen.SCROLL_MODE_LAYER
        elif mode == ScrollMode.POSITION:
            return LayerScreen.SCROLL_MODE_POS
        return "Unknown"

    def get_blend_mode(mode):
        if mode == cg.TILEMAP_BLENDMODE_BLEND:
            return "Blend"
        elif mode == cg.TILEMAP_BLENDMODE_ADD:
            return "Add"
        elif mode == cg.TILEMAP_BLENDMODE_MOD:
            return "Modulate"
        elif mode == cg.TILEMAP_BLENDMODE_MUL:
            return "Multiply"
        elif mode == cg.TILEMAP_BLENDMODE_SUB:
            return "Subtract"
        return "Unknown"

    def _get_tmname(self):
        if self._ldesc.tilemap < 0:
            return "None"
        return self._caller.tmdescs[self._ldesc.tilemap].name

    def _get_tmdims(self):
        if self._ldesc.tilemap < 0:
            return 2<<31-1, 2<<31-1
        return (self._caller.tmdescs[self._ldesc.tilemap].mw *
                self._caller.tmdescs[self._ldesc.tilemap].tw), \
               (self._caller.tmdescs[self._ldesc.tilemap].mh *
                self._caller.tmdescs[self._ldesc.tilemap].th), \

    def _get_tmscale(self):
        if self._ldesc.tilemap < 0:
            return 1.0, 1.0
        return self._caller.tmdescs[self._ldesc.tilemap].hscale, \
               self._caller.tmdescs[self._ldesc.tilemap].wscale

    def _get_relname(self):
        if self._ldesc.relative < 0:
            return "None"
        return self._caller.layers[self._ldesc.relative].name

    def _build_screen(self):
        self._vw, self._vh = self._state.window
        self._fw = self._state.font.ts.width()
        self._fh = self._state.font.ts.height()
        self._scale = self._state.font_scale
        self._fmw = int(self._vw / self._scale / self._fw)
        self._fmh = int(self._vh / self._scale / self._fh)
        self._titletb = textbox.TextBox(self._state.ll,
                                        self._fmw * self._fw, 1 * self._fh,
                                        self._fmw, 1,
                                        self._state.font)
        put_centered_line(self._titletb, "Tilemap Settings", 0, self._fmw)
        self._titletb.layer.pos(int(self._fw * self._scale),
                                int(self._fh * self._scale))
        self._titletb.layer.scale(self._state.font_scale, self._state.font_scale)
        self._dl.replace(self._titletbindex, self._titletb.draw)
        self._menu = textbox.Menu(self._state.ll, self._state.font, self._fmw - 2, self._fmh - 3, None, spacing=2, rel=self._titletb.layer)
        self._menu.add_item("Apply", onActivate=self._apply)
        self._menu.add_item("Name", value=self._ldesc.name, maxlen=255, onEnter=self._setname)
        self._menu.add_item("Tilemap", value=self._get_tmname(), maxlen=255, onActivate=self._select_tilemap)
        self._menu.add_item("Relative", value=self._get_relname(), maxlen=255, onActivate=self._select_relative)
        self._menu.add_item("Width", value=str(self._ldesc.vw), maxlen=4, onEnter=self._setwidth)
        self._menu.add_item("Height", value=str(self._ldesc.vh), maxlen=4, onEnter=self._setheight)
        self._menu.add_item("X Scale", value=str(self._ldesc.scalex), maxlen=5, onEnter=self._set_scalex)
        self._menu.add_item("Y Scale", value=str(self._ldesc.scaley), maxlen=5, onEnter=self._set_scaley)
        self._menu.add_item("Mode", value=LayerScreen.get_scroll_mode(self._ldesc.mode), maxlen=32, onActivate=self._toggle_mode)
        self._menu.add_item(" None:", value="Layer position is never adjusted.")
        self._menu.add_item(" Layer:", value="Layer is scrolled.")
        self._menu.add_item(" Position:", value="Layer is moved.")
        self._menu.add_item("X Pos", value=str(self._ldesc.posx), maxlen=5, onEnter=self._set_posx)
        self._menu.add_item("Y Pos", value=str(self._ldesc.posy), maxlen=5, onEnter=self._set_posy)
        self._menu.add_item("X Scroll", value=str(self._ldesc.scrollx), maxlen=5, onEnter=self._set_scrollx)
        self._menu.add_item("Y Scroll", value=str(self._ldesc.scrolly), maxlen=5, onEnter=self._set_scrolly)
        self._menu.add_item("Colormod", onActivate=self._set_color)
        self._menu.add_item("Blend Mode", value=LayerScreen.get_blend_mode(self._ldesc.blendmode), maxlen=32, onActivate=self._toggle_blend_mode)
        self._menu.add_item("Move", onActivate=self._move)
        self._menu.add_item("Delete", onActivate=self._delete)
        self._menu.update()
        mlayer, self._cursorl = self._menu.layers
        mlayer.pos(0, self._fh * 2)
        self._dl.replace(self._menuindex, self._menu.displaylist)

    def __init__(self, state, caller, ldesc):
        self._state = state
        self._caller = caller
        self._ldesc = ldesc
        self._error = 0.0
        self._errortext = ''
        self._errorbox = None
        self._cursorrad = 0.0
        self._selecting = LayerScreenSelecting.NONE
        self._selection = 0
        self._dl = display.DisplayList(self._state.ll)
        self._titletbindex = self._dl.append(None)
        self._menuindex = self._dl.append(None)
        self._errorindex = self._dl.append(None)
        self._build_screen()

    def _set_error(self, text):
        print(text)
        self._errortext = text
        self._error = ERROR_TIME

    def resize(self):
        vw, vh = self._state.window
        scale = self._state.font_scale
        fw = self._state.font.ts.width()
        fh = self._state.font.ts.height()
        if self._fmw != int(vw / scale / fw) or \
           self._fmh != int(vh / scale / fh):
            self._build_screen()

    def active(self):
        self.resize()
        if self._selecting == LayerScreenSelecting.TILEMAP:
            if self._selection is not None:
                self._ldesc.tilemap = self._selection - 1
                self._ldesc.vw, self._ldesc.vh = self._get_tmdims()
                self._menu.update_value(4, str(self._ldesc.vw))
                self._menu.update_value(5, str(self._ldesc.vh))
                self._ldesc.scalex, self._ldesc.scaley = self._get_tmscale()
                self._menu.update_value(6, str(self._ldesc.scalex))
                self._menu.update_value(7, str(self._ldesc.scaley))
            else:
                self._ldesc.tilemap = -1
            self._menu.update_value(2, self._get_tmname())
        elif self._selecting == LayerScreenSelecting.RELATIVE:
            if self._selection is not None:
                if self._selection - 1 == self._caller.selected:
                    self._set_error("Layer can't be relative to self.")
                else:
                    self._ldesc.relative = self._selection - 1
            else:
                self._ldesc.tilemap = -1
            self._menu.update_value(3, self._get_relname())
        self._selecting = LayerScreenSelecting.NONE

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
                    self._state.active_screen(self._caller)

    def update(self, time):
        if self._error > 0.0:
            if self._errorbox is None:
                if len(self._errortext) == 0:
                    self._errortext = "Unknown error"
                lines, _, w, h = textbox.wrap_text(self._errortext, self._fmw - 2, 10)
                self._errorbox = textbox.TextBox(self._state.ll,
                                                 w * self._fw, h * self._fh,
                                                 w, h,
                                                 self._state.font)
                self._errorbox.put_text(lines, 0, 0)
                self._errorbox.layer.relative(self._titletb.layer)
                self._errorbox.layer.pos(0, int((self._fmh - h - 2) * self._fh))
                self._dl.replace(self._errorindex, self._errorbox.draw)
            self._error -= time
        if self._error <= 0.0 and self._errorbox is not None:
            self._dl.replace(self._errorindex, None)
            self._errorbox = None
            self._errortext = ''

        self._cursorrad, color = update_cursor_effect(self._cursorrad, time)
        self._cursorl.colormod(color)

    def _setname(self, priv, sel, val):
        self._ldesc.name = val.lstrip().rstrip()
        return self._ldesc.name

    def set_option(self, sel):
        self._selection = sel

    def _select_tilemap(self, priv, sel, val):
        tilemaps = [desc.name for desc in self._caller.tmdescs]
        tilemaps.insert(0, "None")
        promptscreen = PromptScreen(self._state, self, "Select Tilemap", tilemaps, default=self._ldesc.tilemap + 1)
        self._state.active_screen(promptscreen)
        self._selecting = LayerScreenSelecting.TILEMAP
        return None

    def _select_relative(self, priv, sel, val):
        layers = [desc.name for desc in self._caller.layers]
        # make sure the name in the menu reflects a name set but not applied
        layers[self._caller.selected] = self._ldesc.name
        layers.insert(0, "None")
        promptscreen = PromptScreen(self._state, self, "Select Layer", layers, default=self._ldesc.relative + 1)
        self._state.active_screen(promptscreen)
        self._selecting = LayerScreenSelecting.RELATIVE
        return None

    def _setwidth(self, priv, sel, val):
        try:
            val = int(val)
        except ValueError:
            return None
        pw, _ = self._get_tmdims()
        if val < 1 or val > pw:
            return None
        self._ldesc.vw = val
        return str(self._ldesc.vw)

    def _setheight(self, priv, sel, val):
        try:
            val = int(val)
        except ValueError:
            return None
        _, ph = self._get_tmdims()
        if val < 1 or val > ph:
            return None
        self._ldesc.vh = val
        return str(self._ldesc.vh)

    def _set_scalex(self, priv, sel, val):
        try:
            val = float(val)
        except ValueError:
            return None
        if val < 0.0:
            self._set_error("Scale must be positive.")
            return None
        self._ldesc.scalex = val
        return str(self._ldesc.scalex)

    def _set_scaley(self, priv, sel, val):
        try:
            val = float(val)
        except ValueError:
            return None
        if val < 0.0:
            self._set_error("Scale must be positive.")
            return None
        self._ldesc.scaley = val
        return str(self._ldesc.scaley)

    def _toggle_mode(self, priv, sel, val):
        if self._ldesc.mode == ScrollMode.NONE:
            self._ldesc.mode = ScrollMode.LAYER
        elif self._ldesc.mode == ScrollMode.LAYER:
            self._ldesc.mode = ScrollMode.POSITION
        else:
            self._ldesc.mode = ScrollMode.NONE
        return LayerScreen.get_scroll_mode(self._ldesc.mode)

    def _set_posx(self, priv, sel, val):
        try:
            val = int(val)
        except ValueError:
            return None
        self._ldesc.posx = val
        return str(self._ldesc.posx)

    def _set_posy(self, priv, sel, val):
        try:
            val = int(val)
        except ValueError:
            return None
        self._ldesc.posy = val
        return str(self._ldesc.posy)

    def _set_scrollx(self, priv, sel, val):
        try:
            val = int(val)
        except ValueError:
            return None
        self._ldesc.scrollx = val
        return str(self._ldesc.scrollx)

    def _set_scrolly(self, priv, sel, val):
        try:
            val = int(val)
        except ValueError:
            return None
        self._ldesc.scrolly = val
        return str(self._ldesc.scrolly)

    def _set_color(self, priv, sel):
        r, g, b, a = display.unmake_color(self._ldesc.colormod)
        colorpicker = ColorPickerScreen(self._state, self, r, g, b, a)
        self._state.active_screen(colorpicker)

    def set_color(self, r, g, b, a):
        self._ldesc.colormod = display.make_color(r, g, b, a)

    def _toggle_blend_mode(self, priv, sel, val):
        if self._ldesc.blendmode == cg.TILEMAP_BLENDMODE_BLEND:
            self._ldesc.blendmode = cg.TILEMAP_BLENDMODE_ADD
        elif self._ldesc.blendmode == cg.TILEMAP_BLENDMODE_ADD:
            self._ldesc.blendmode = cg.TILEMAP_BLENDMODE_MOD
        elif self._ldesc.blendmode == cg.TILEMAP_BLENDMODE_MOD:
            self._ldesc.blendmode = cg.TILEMAP_BLENDMODE_MUL
        elif self._ldesc.blendmode == cg.TILEMAP_BLENDMODE_MUL:
            self._ldesc.blendmode = cg.TILEMAP_BLENDMODE_SUB
        else:
            self._ldesc.blendmode = cg.TILEMAP_BLENDMODE_BLEND
        return LayerScreen.get_blend_mode(self._ldesc.blendmode)

    def _apply(self, priv, sel):
        self._caller.apply(self._ldesc)

    def _move(self, priv, sel):
        self._caller.move()
        self._state.active_screen(self._caller)

    def _delete(self, priv, sel):
        self._caller.delete()
        self._state.active_screen(self._caller)

class PreviewScreen():
    def _get_tileset(self, num):
        return self._state.tileset(self._tmdescs[num].filename,
                                   self._tmdescs[num].tw,
                                   self._tmdescs[num].th)

    def _set_all(self):
        for num, desc in enumerate(self._ldescs):
            if desc.mode == ScrollMode.LAYER:
                self._layers[num].scroll(desc.scrollx + int(self._posx),
                                         desc.scrolly + int(self._posy))
                self._layers[num].update()
            elif desc.mode == ScrollMode.POSITION:
                if desc.tilemap < 0:
                    self._layers[num].pos(desc.posx + int(self._posx),
                                          desc.posy + int(self._posy))
                else:
                    self._layers[num].layer.pos(desc.posx + int(self._posx),
                                                desc.posy + int(self._posy))
                    self._layers[num].update()

    def _build_screen(self):
        self._vw, self._vh = self._state.window
        self._layers = list()
        for desc in self._ldescs:
            if desc.tilemap < 0:
                l = cg.Layer(self._state.ll, None, "Preview Layer {}".format(desc.name))
                l.scale(desc.scalex, desc.scaley)
                l.pos(desc.posx, desc.posy)
                self._layers.append(l)
            else:
                vpw = desc.vw
                if vpw * desc.scalex > self._vw:
                    vpw = self._vw / desc.scalex + 1
                vph = desc.vh
                if desc.vh * desc.scaley > self._vh:
                    vph = self._vh / desc.scaley + 1
                stm = display.ScrollingTilemap(self._state.ll,
                    self._get_tileset(desc.tilemap),
                    self._maps[desc.tilemap][0],
                    vpw, vph,
                    self._tmdescs[desc.tilemap].mw,
                    self._tmdescs[desc.tilemap].mh,
                    flags=self._maps[desc.tilemap][1],
                    colormod=self._maps[desc.tilemap][2],
                    optimize=True)
                stm.scale(desc.scalex, desc.scaley)
                stm.layer.pos(desc.posx, desc.posy)
                stm.scroll(desc.scrollx, desc.scrolly)
                stm.internal.colormod(desc.colormod)
                stm.internal.blendmode(desc.blendmode)
                self._layers.append(stm)

        for num, desc in enumerate(self._ldescs):
            if desc.relative >= 0:
                if desc.mode != ScrollMode.LAYER:
                    if self._ldescs[desc.relative].mode == ScrollMode.LAYER:
                        self._layers[num].layer.relative(self._layers[desc.relative].maplayer)
                    else:
                        self._layers[num].layer.relative(self._layers[desc.relative].layer)
                else:
                    if self._ldescs[desc.relative].mode == ScrollMode.LAYER:
                        self._layers[num].maplayer.relative(self._layers[desc.relative].maplayer)
                    else:
                        self._layers[num].maplayer.relative(self._layers[desc.relative].layer)

        self._set_all()

        self._dl = display.DisplayList(self._state.ll)
        for layer in self._layers:
            self._dl.append(layer.draw)

    def __init__(self, state, caller, x, y):
        self._state = state
        self._caller = caller
        self._ldescs = caller.layers
        self._tmdescs = caller.tmdescs
        self._maps = [(editor.tilemap, editor.flags, editor.colormod) for editor in caller.editors]
        self._xspeed = 0.0
        self._yspeed = 0.0
        self._posx = x
        self._posy = y
        self._build_screen()

    def resize(self):
        vw, vh = self._state.window
        if self._vw != vw or self._vh != vh:
            self._build_screen()

    def active(self):
        self.resize()

    @property
    def dl(self):
        return self._dl

    def _movex(self, val):
        if val < 0:
            self._xspeed = -1.0
        elif val > 0:
            self._xspeed = 1.0
        else:
            self._xspeed = 0.0

    def _movey(self, val):
        if val < 0:
            self._yspeed = -1.0
        elif val > 0:
            self._yspeed = 1.0
        else:
            self._yspeed = 0.0

    def input(self, event):
        if event.type == SDL_KEYDOWN and event.key.repeat == 0:
            if event.key.keysym.sym == SDLK_UP:
                self._movey(-1)
            elif event.key.keysym.sym == SDLK_DOWN:
                self._movey(1)
            elif event.key.keysym.sym == SDLK_LEFT:
                self._movex(-1)
            elif event.key.keysym.sym == SDLK_RIGHT:
                self._movex(1)
            elif event.key.keysym.sym == SDLK_r:
                self._posx = 0
                self._posy = 0
                self._set_all()
            elif event.key.keysym.sym == SDLK_ESCAPE:
                self._caller.setpos(self._posx, self._posy)
                self._state.active_screen(self._caller)
        elif event.type == SDL_KEYUP:
            if event.key.keysym.sym == SDLK_UP:
                self._movey(0)
            elif event.key.keysym.sym == SDLK_DOWN:
                self._movey(0)
            elif event.key.keysym.sym == SDLK_LEFT:
                self._movex(0)
            elif event.key.keysym.sym == SDLK_RIGHT:
                self._movex(0)

    def update(self, time):
        if self._xspeed < 0:
            self._xspeed -= time
        elif self._xspeed > 0:
            self._xspeed += time
        if self._yspeed < 0:
            self._yspeed -= time
        elif self._yspeed > 0:
            self._yspeed += time
        if self._xspeed != 0 or self._yspeed != 0:
            self._posx += self._xspeed
            self._posy += self._yspeed
            self._set_all()


class MapeditState():
    RESIZE_COOLDOWN = 0.25

    def __init__(self, renderer, pixfmt, vw, vh, font_filename, font_mapname, font_width, font_height, font_scale):
        sdlfmt = SDL_AllocFormat(pixfmt)
        self._ll = cg.LayerList(renderer, pixfmt, log_cb_return, None)
        self._dl = display.DisplayList(self._ll)
        self._dl.append(display.make_color(0, 0, 0, SDL_ALPHA_OPAQUE))
        self._screen = None
        self._screenindex = self._dl.append(None)
        self._tilesets = {}
        self._tilesetrefs = {}
        self._tilemaps = {}
        self._running = True
        self._newscreen = False
        self._resizing = 0.0
        self._extratime = 0.0
        self._renders = FULL_RENDERS
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

    def set_scale(self, scale):
        if scale < 1.0:
            raise ValueError("Scale out of range.")
        self._font_scale = scale

    @property
    def font(self):
        return self._font

    def active_screen(self, screen):
        self._screen = screen
        self._screen.active()
        self._dl.replace(self._screenindex, self._screen.dl)
        self._newscreen = True
        self.changed()

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
                    self.changed()
            else:
                self._screen.update(time + self._extratime)
                if self._renders <= 0:
                    self._dl.draw(display.SCREEN, full=False)
                else:
                    self._dl.draw(display.SCREEN)
                    self._renders -= 1
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
            self._tilesetrefs[desc] += 1
        except KeyError:
            tileset = self._ll.tileset(filename, width, height, None)
            self._tilesets[desc] = tileset
            self._tilesetrefs[desc] = 1
        return desc

    def remove_tileset(self, desc):
        self._tilesetrefs[desc] -= 1
        if self._tilesetrefs[desc] == 0:
            del self._tilesets[desc]
            del self._tilesetrefs[desc]

    def reload_tileset(self, desc, tileset=None):
        if tileset is None:
            tileset = self._ll.tileset(desc.filename, desc.width, desc.height, None)
        else:
            if tileset.width() != desc.width or \
               tileset.height() != desc.height:
                raise ValueError("Replacement tileset width and height don't match description width and height.")
        self._tilesets[desc] = tileset
        return tileset

    def tileset_desc(self, desc):
        return self._tilesets[desc]

    def tileset(self, filename, width, height):
        return self._tilesets[TilesetDesc(filename, width, height)]

    def changed(self):
        self._renders = FULL_RENDERS


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
    if len(argv) > 1:
        project = ProjectScreen(state, argv[1])
    else:
        project = ProjectScreen(state)
    state.active_screen(project)

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
