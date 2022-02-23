#!/usr/bin/env python
from sdl2 import *
import crustygame as cg
import array
from sys import argv
import time
import display
import textbox
import copy
import itertools
import math
import effects

#TODO:
# finish statusbar
# Editor view scale option
# Block copy/fill tool
# Text tool using tilemap codec
# Multiple layers
# Preview of multiple layers with independent scale/scroll speed/center
# plane/project Save/Load
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
TEXT_FILENAME="cdemo/font.bmp"
TEXT_MAP_FILENAME="font.txt"
TEXT_WIDTH=8
TEXT_HEIGHT=8
SCALE=2.0
ERROR_TIME=10.0

TEXT_SCALED_WIDTH=TEXT_WIDTH * SCALE
TEXT_SCALED_HEIGHT=TEXT_HEIGHT * SCALE
TILES_WIDTH=int(RES_WIDTH / TEXT_SCALED_WIDTH)
TILES_HEIGHT=int(RES_HEIGHT / TEXT_SCALED_HEIGHT)

crustyerror = ''

def need_text(state):
    try:
        state.tileset('ts_text')
    except KeyError:
        state.add_tileset(state.ll.tileset(TEXT_FILENAME, TEXT_WIDTH, TEXT_HEIGHT, None), 'ts_text')
        with open(TEXT_MAP_FILENAME, 'r') as f:
            textbox.load_tileset_codec(f, 'text')

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

def update_cursor(stm, cursorl, vw, vh, mw, mh, tw, th, x, y):
    xpos = -1
    ypos = -1
    xscroll = 0
    yscroll = 0
    halfw = vw // 2
    halfh = vh // 2
    if mw > vw:
        if x > halfw:
            if x <= mw - halfw:
                xscroll = x - halfw
                x = halfw
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
            if y <= mh - halfh:
                yscroll = y - halfh
                y = halfh
                ypos = 0
            else:
                yscroll = mh - vh
                y = y - (mh - vh)
                ypos = 1
    else:
        if y > halfh:
            xpos = 1
    stm.scroll(xscroll * tw, yscroll * th)
    stm.update()
    cursorl.pos(x * tw - TEXT_WIDTH, y * th - TEXT_HEIGHT)
    return xpos, ypos

def make_cursor(state, curwidth, curheight, name):
    need_text(state)
    tstext = state.tileset('ts_text')
    cursortm = tstext.tilemap(curwidth + 2, curheight + 2, name)
    tm = array.array('u', itertools.repeat(' ', (curwidth + 2) * (curheight + 2)))
    tm[0] = '+'
    for x in range(curwidth):
        tm[1 + x] = '-'
    tm[curwidth + 1] = '+'
    for y in range(curheight):
        tm[(y + 1) * (curwidth + 2)] = '|'
        tm[((y + 1) * (curwidth + 2)) + (curwidth + 1)] = '|'
    tm[(curheight + 1) * (curwidth + 2)] = '+'
    for x in range(curwidth):
        tm[((curheight + 1) * (curwidth + 2)) + x + 1] = '-'
    tm[((curheight + 1) * (curwidth + 2)) + curwidth + 1] = '+'
    cursortm.map(0, 0, curwidth + 2, curwidth + 2, curheight + 2, tm.tounicode().encode('crusty_text'))
    cursortm.update()
    return cursortm

def update_cursor_effect(cursorrad, time, cursorl):
    cursorrad += math.pi * time
    cursorrad %= math.tau
    r, g, b = effects.color_from_rad(cursorrad, 0, 255)
    cursorl.colormod(display.make_color(r, g, b, SDL_ALPHA_OPAQUE))
    return(cursorrad)

class Sidebar():
    SIDEBAR_COLOR=display.make_color(255, 255, 255, 96)

    def __init__(self, state, text, vw, vh, mw, tw):
        self._state = state
        self._vw = vw
        self._mw = mw
        self._tw = tw
        need_text(self._state)
        tstext = self._state.tileset('ts_text')
        self._dl = display.DisplayList(self._state.ll)
        helptext, _, width, height = textbox.wrap_text(text, self._vw, vh)
        self._sbwidth = width + 2
        sbtm = array.array('u', itertools.repeat('█', self._sbwidth * vh)).tounicode().encode('crusty_text')
        sidebartm = tstext.tilemap(self._sbwidth, vh, "Sidebar")
        sidebartm.map(0, 0, self._sbwidth, self._sbwidth, vh, sbtm)
        sidebartm.update()
        self._sidebarl = sidebartm.layer("Sidebar Layer")
        self._sidebarl.scale(SCALE, SCALE)
        self._sidebarl.colormod(Sidebar.SIDEBAR_COLOR)
        self._sidebarl.blendmode(cg.TILEMAP_BLENDMODE_SUB)
        self._sidebarl.pos(int((self._vw - self._sbwidth) * TEXT_SCALED_WIDTH), 0)
        self._dl.append(self._sidebarl)
        self._sbpos = 1
        self._sbtext = textbox.TextBox(width, height, width, height,
                                       tstext, 'crusty_text')
        self._sbtext.put_text(helptext, 0, 0)
        self._sbtext.layer.pos(TEXT_WIDTH, TEXT_HEIGHT)
        self._sbtext.layer.relative(self._sidebarl)
        self._dl.append(lambda: self._sbtext.layer.pos(TEXT_WIDTH + 1, TEXT_HEIGHT + 1))
        self._dl.append(lambda: self._sbtext.layer.colormod(display.make_color(0, 0, 0, SDL_ALPHA_OPAQUE)))
        self._dl.append(self._sbtext.layer)
        self._dl.append(lambda: self._sbtext.layer.pos(TEXT_WIDTH, TEXT_HEIGHT))
        self._dl.append(lambda: self._sbtext.layer.colormod(display.make_color(255, 255, 255, SDL_ALPHA_OPAQUE)))
        self._dl.append(self._sbtext.layer)

    @property
    def dl(self):
        return self._dl

    def update(self, curpos, curx, mw):
        if mw * self._tw * SCALE <= RES_WIDTH:
            if mw * self._tw * SCALE < RES_WIDTH - (self._sbwidth * TEXT_SCALED_WIDTH):
                self._sidebarl.pos(int((self._vw - self._sbwidth) * TEXT_SCALED_WIDTH), 0)
                self._sbpos = 1
            else:
                if self._sbpos == 1 and \
                   curx * self._tw * SCALE >= RES_WIDTH - (self._sbwidth * TEXT_SCALED_WIDTH):
                    self._sidebarl.pos(0, 0)
                    self._sbpos = -1
                elif self._sbpos == -1 and \
                     curx * self._tw * SCALE < self._sbwidth * TEXT_SCALED_WIDTH:
                    self._sidebarl.pos(int((self._vw - self._sbwidth) * TEXT_SCALED_WIDTH), 0)
                    self._sbpos = 1
        elif curpos != self._sbpos:
            if curpos < 0:
                self._sidebarl.pos(int((self._vw - self._sbwidth) * TEXT_SCALED_WIDTH), 0)
                self._sbpos = 1
            elif curpos > 0:
                self._sidebarl.pos(0, 0)
                self._sbpos = -1
            else:
                if self._sbpos < 0:
                    self._sidebarl.pos(int((self._vw - self._sbwidth) * TEXT_SCALED_WIDTH), 0)
                elif self._sbpos > 0:
                    self._sidebarl.pos(0, 0)
                self._sbpos = 0

class NewScreen():
    NAME='new'

    def __init__(self, state):
        self._state = state
        self._dl = display.DisplayList(self._state.ll)
        self._vw = TILES_WIDTH
        self._vh = TILES_HEIGHT
        self._mw = 32
        self._mh = 32
        self._tw = TEXT_WIDTH
        self._th = TEXT_HEIGHT
        self._filename = TEXT_FILENAME
        need_text(self._state)
        tstext = self._state.tileset('ts_text')
        self._tb = textbox.TextBox(self._vw, 1, self._vw, 1,
                                   tstext, 'crusty_text')
        put_centered_line(self._tb, "New Tilemap", 0, self._vw)
        self._tb.layer.pos(int(TEXT_SCALED_WIDTH), int(TEXT_SCALED_HEIGHT))
        self._tb.layer.scale(SCALE, SCALE)
        self._dl.append(self._tb.layer)
        self._menu = textbox.Menu(self._state.ll, tstext, 'crusty_text', self._vw - 2, None, spacing=2)
        self._menu.add_item("Tileset", value=self._filename, maxlen=255, onEnter=self._setname)
        self._menu.add_item("Tile Width", value=str(self._tw), maxlen=4, onEnter=self._settilewidth)
        self._menu.add_item("Tile Height", value=str(self._th), maxlen=4, onEnter=self._settileheight)
        self._menu.add_item("Map Width", value=str(self._mw), maxlen=4, onEnter=self._setmapwidth)
        self._menu.add_item("Map Height", value=str(self._mh), maxlen=4, onEnter=self._setmapheight)
        self._menu.add_item("Proceed", onActivate=self._proceed)
        self._menu.update()
        mlayer, self._cursorl = self._menu.layers
        mlayer.scale(SCALE, SCALE)
        mlayer.pos(int(TEXT_SCALED_WIDTH), int(TEXT_SCALED_HEIGHT * 3))
        self._dl.append(self._menu.displaylist)
        self._tileset = None
        self._error = 0.0
        self._errorbox = None
        self._errorpos = self._dl.append(None)
        self._cursorrad = 0.0

    def active(self):
        pass

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
                error = get_error()
                if len(error) == 0:
                    error = "Unknown error"
                lines, _, w, h = textbox.wrap_text(error, TILES_WIDTH - 2, 10)
                self._errorbox = textbox.TextBox(w, h, w, h,
                                                 self._state.tileset('ts_text'), 'crusty_text')
                self._errorbox.put_text(lines, 0, 0)
                self._errorbox.layer.pos(int(TEXT_SCALED_WIDTH), int((TILES_HEIGHT - h - 1) * TEXT_SCALED_HEIGHT))
                self._errorbox.layer.scale(SCALE, SCALE)
                self._dl.replace(self._errorpos, self._errorbox.layer)
            self._error -= time
        if self._error <= 0.0 and self._errorbox is not None:
            self._dl.replace(self._errorpos, None)
            self._errorbox = None

        self._cursorrad = update_cursor_effect(self._cursorrad, time, self._cursorl)

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

    def _proceed(self, priv, sel):
        try:
            tileset = self._state.ll.tileset(self._filename, self._tw, self._th, None)
        except cg.CrustyException:
            self._error = ERROR_TIME
            return
        self._state.add_tileset(tileset, 'ts_tm0')
        try:
            editscreen = self._state.get_screen(EditScreen)
        except KeyError:
            self._state.add_screen(EditScreen)
            editscreen = self._state.get_screen(EditScreen)
        editscreen.tilemap('ts_tm0', self._vw, self._vh,
                                     self._mw, self._mh)
        self._state.active_screen(EditScreen)

class EditScreen():
    NAME='edit'

    def __init__(self, state):
        self._state = state
        self._tilemap = None
        self._cursorrad = 0.0
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
        self._showsidebar = True

    @property
    def dl(self):
        return self._dl

    def set_tile(self, tile):
        self._tile = tile

    def active(self):
        if self._tilemap is None:
            raise Exception("Edit screen not fully set up.")
        if self._quitting:
            self._state.stop()

    def _update_cursor(self):
        self._curpos, _ = update_cursor(self._stm, self._cursorl,
                                        self._vw, self._vh,
                                        self._mw, self._mh,
                                        self._tw, self._th,
                                        self._curx, self._cury)

    def _make_tilemap(self):
        self._curx, self._cury, self._stm = \
            make_tilemap(self._vw, self._vh,
                         self._mw, self._mh,
                         0, 0,
                         self._tileset, self._tilemap,
                         flags=self._flags, colormod=self._colormod)

    def _update_sidebar(self):
        self._sidebar.update(self._curpos, self._curx, self._mw)

    def tilemap(self, ts, vw, vh, mw, mh):
        self._tileset = self._state.tileset(ts)
        self._tiles = self._tileset.tiles()
        self._vw = int(vw)
        self._vh = int(vh)
        self._mw = int(mw)
        self._mh = int(mh)
        self._tw = self._tileset.width()
        self._th = self._tileset.height()
        need_text(self._state)
        tstext = self._state.tileset('ts_text')
        self._color = display.make_color(self._red, self._green, self._blue, self._alpha)
        self._attrib = display.make_attrib(self._hflip, self._vflip, self._rotate)
        self._dl = display.DisplayList(self._state.ll)
        self._tilemap = array.array('I', itertools.repeat(0, self._mw * self._mh))
        self._flags = array.array('I', itertools.repeat(self._attrib, self._mw * self._mh))
        self._colormod = array.array('I', itertools.repeat(self._color, self._mw * self._mh))
        self._make_tilemap()
        self._stm.layer.scale(SCALE, SCALE)
        self._dl.append(self._stm.layer)
        curwidth = int(self._tw * SCALE / TEXT_SCALED_WIDTH)
        curheight = int(self._th * SCALE / TEXT_SCALED_HEIGHT)
        self._cursortm = make_cursor(self._state, curwidth, curheight, "MapEditor Cursor Tilemap")
        self._cursorl = self._cursortm.layer("Map Editor Cursor Layer")
        self._cursorl.relative(self._stm.layer)
        self._update_cursor()
        self._dl.append(self._cursorl)
        self._state.add_screen(TileSelectScreen)
        selectscreen = self._state.get_screen(TileSelectScreen)
        selectscreen.tileset(ts, self._vw, self._vh)
        self._sidebar = Sidebar(self._state, "Tile:\n\n\nR:    G:    B:\nVF:  HF:  R:\nh - Toggle Sidebar\nESC - Quit\nArrows - Move\nSPACE - Place\nSHIFT+SPACE - Grab\nNumpad Plus\n  Increase Tile\nNumpad Minus\n  Decrease Tile\nc - Open Color Picker\nSHIFT+c - Grab Color\nCTRL+c - Place Color\nv - Open Tile Picker\nSHIFT+v - Grab Tile\nCTRL+v - Place Tile\nr - Cycle Rotation\nt - Toggle Horiz Flip\ny - Toggle Vert Flip\nSHIFT+b\n  Grab Attributes\nCTRL+b\n  Place Attributes\nq/a - Adjust Red\nw/s - Adjust Green\ne/d - Adjust Blue\nx/z - Adjust Alpha", self._vw, self._vh, self._mw, self._tw)
        self._sidebarindex = self._dl.append(self._sidebar.dl)

    def _check_drawing(self):
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

    def input(self, event):
        if event.type == SDL_KEYDOWN:
            if event.key.keysym.sym == SDLK_UP:
                if self._cury > 0:
                    self._cury -= 1
                    self._update_cursor()
                    self._check_drawing()
            elif event.key.keysym.sym == SDLK_DOWN:
                if self._cury < self._mh - 1:
                    self._cury += 1
                    self._update_cursor()
                    self._check_drawing()
            elif event.key.keysym.sym == SDLK_LEFT:
                if self._curx > 0:
                    self._curx -= 1
                    self._update_cursor()
                    self._update_sidebar()
                    self._check_drawing()
            elif event.key.keysym.sym == SDLK_RIGHT:
                if self._curx < self._mw - 1:
                    self._curx += 1
                    self._update_cursor()
                    self._update_sidebar()
                    self._check_drawing()
            elif event.key.keysym.sym == SDLK_SPACE:
                if event.key.keysym.mod & KMOD_SHIFT != 0:
                    self._tile = self._tilemap[self._cury * self._mw + self._curx]
                    self._color = self._colormod[self._cury * self._mw + self._curx]
                    self._attrib = self._flags[self._cury * self._mw + self._curx]
                else:
                    self._drawing = True
                    self._check_drawing()
            elif event.key.keysym.sym == SDLK_KP_PLUS:
                val = self._tilemap[self._cury * self._mw + self._curx] + 1
                if val < self._tiles:
                    self._tilemap[self._cury * self._mw + self._curx] = val
                    self._stm.updateregion(self._curx, self._cury, 1, 1)
            elif event.key.keysym.sym == SDLK_KP_MINUS:
                val = self._tilemap[self._cury * self._mw + self._curx] - 1
                if val >= 0:
                    self._tilemap[self._cury * self._mw + self._curx] = val
                    self._stm.updateregion(self._curx, self._cury, 1, 1)
            elif event.key.keysym.sym == SDLK_v:
                if event.key.keysym.mod & KMOD_SHIFT != 0:
                    self._tile = self._tilemap[self._cury * self._mw + self._curx]
                elif event.key.keysym.mod & KMOD_CTRL != 0:
                    self._puttile = True
                    self._check_drawing()
                else:
                    self._state.active_screen(TileSelectScreen)
            elif event.key.keysym.sym == SDLK_c:
                if event.key.keysym.mod & KMOD_SHIFT != 0:
                    self._color = self._colormod[self._cury * self._mw + self._curx]
                    self._red, self._green, self._blue, self._alpha = display.unmake_color(self._color)
                elif event.key.keysym.mod & KMOD_CTRL != 0:
                    self._putcolor = True
                    self._check_drawing()
                else:
                    colorpicker = ColorPickerScreen(self._state, self, self._vw, self._red, self._green, self._blue, self._alpha)
                    self._state.active_screen(colorpicker)
            elif event.key.keysym.sym == SDLK_b:
                if event.key.keysym.mod & KMOD_SHIFT != 0:
                    self._attrib = self._flags[self._cury * self._mw + self._curx]
                    self._hflip, self._vflip, self._rotate = display.unmake_attrib(self._attrib)
                elif event.key.keysym.mod & KMOD_CTRL != 0:
                    self._putattrib = True
                    self._check_drawing()
            elif event.key.keysym.sym == SDLK_t:
                if self._hflip == 0:
                    self._hflip = cg.TILEMAP_HFLIP_MASK
                else:
                    self._hflip = 0
                self._attrib = display.make_attrib(self._hflip, self._vflip, self._rotate)
            elif event.key.keysym.sym == SDLK_y:
                if self._vflip == 0:
                    self._vflip = cg.TILEMAP_VFLIP_MASK
                else:
                    self._vflip = 0
                self._attrib = display.make_attrib(self._hflip, self._vflip, self._rotate)
            elif event.key.keysym.sym == SDLK_r:
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
            elif event.key.keysym.sym == SDLK_q:
                if self._red < 255:
                    self._red += 1
                    self._color = display.make_color(self._red, self._green, self._blue, self._alpha)
            elif event.key.keysym.sym == SDLK_a:
                if self._red > 0:
                    self._red -= 1
                    self._color = display.make_color(self._red, self._green, self._blue, self._alpha)
            elif event.key.keysym.sym == SDLK_w:
                if self._green < 255:
                    self._green += 1
                    self._color = display.make_color(self._red, self._green, self._blue, self._alpha)
            elif event.key.keysym.sym == SDLK_s:
                if self._green > 0:
                    self._green -= 1
                    self._color = display.make_color(self._red, self._green, self._blue, self._alpha)
            elif event.key.keysym.sym == SDLK_e:
                if self._blue < 255:
                    self._blue += 1
                    self._color = display.make_color(self._red, self._green, self._blue, self._alpha)
            elif event.key.keysym.sym == SDLK_d:
                if self._blue > 0:
                    self._blue -= 1
                    self._color = display.make_color(self._red, self._green, self._blue, self._alpha)
            elif event.key.keysym.sym == SDLK_x:
                if self._alpha < 255:
                    self._alpha += 1
                    self._color = display.make_color(self._red, self._green, self._blue, self._alpha)
            elif event.key.keysym.sym == SDLK_z:
                if self._alpha > 0:
                    self._alpha -= 1
                    self._color = display.make_color(self._red, self._green, self._blue, self._alpha)
            elif event.key.keysym.sym == SDLK_ESCAPE:
                prompt = PromptScreen(self._state, self, "Quit?", "Any unsaved changes will be lost, are you sure?", ("yes", "no"), default=1)
                self._state.active_screen(prompt)
            elif event.key.keysym.sym == SDLK_h:
                if self._showsidebar:
                    self._dl.replace(self._sidebarindex, None)
                    self._showsidebar = False
                else:
                    self._dl.replace(self._sidebarindex, self._sidebar.dl)
                    self._showsidebar = True
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
        self._cursorrad = update_cursor_effect(self._cursorrad, time, self._cursorl)

    def set_option(self, sel):
        if sel == 0:
            self._quitting = True

    def set_color(self, red, green, blue, alpha):
        self._red = red
        self._green = green
        self._blue = blue
        self._alpha = alpha
        self._color = display.make_color(self._red, self._green, self._blue, self._alpha)

class TileSelectScreen():
    NAME='tileselect'

    def __init__(self, state):
        self._state = state
        self._stm = None
        self._cursorrad = 0.0

    @property
    def dl(self):
        return self._dl

    def active(self):
        if self._stm is None:
            raise Exception("Edit screen not fully set up.")

    def _update_cursor(self):
        self._curpos, _ = update_cursor(self._stm, self._cursorl,
                                        self._vw, self._vh,
                                        self._mw, self._mh,
                                        self._tw, self._th,
                                        self._curx, self._cury)

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
        self._sidebar.update(self._curpos, self._curx, self._mw)

    def tileset(self, ts, vw, vh):
        self._tileset = self._state.tileset(ts)
        self._tiles = self._tileset.tiles()
        self._scale = 2.0
        side = math.sqrt(self._tiles)
        if side.is_integer():
            side = int(side)
        else:
            side = int(side) + 1
        self._vw = int(vw)
        self._vh = int(vh)
        self._mw = side
        self._mh = side
        self._tw = self._tileset.width()
        self._th = self._tileset.height()
        self._dl = display.DisplayList(self._state.ll)
        curwidth = int(self._tw * SCALE / TEXT_SCALED_WIDTH)
        curheight = int(self._th * SCALE / TEXT_SCALED_HEIGHT)
        self._cursortm = make_cursor(self._state, curwidth, curheight, "Tile Select Cursor Tilemap")
        self._cursorl = self._cursortm.layer("Tile Select Cursor Layer")
        self._tmindex = self._dl.append(None)
        self._dl.append(self._cursorl)
        self._curx = 0
        self._cury = 0
        self._make_tilemap()
        self._sidebar = Sidebar(self._state, "ESC - Cancel Selection\nArrows - Move\nEnter - Select\nq/w - Adjust Width\na/z - Adjust Height", self._vw, self._vh, self._mw, self._tw)
        self._dl.append(self._sidebar.dl)

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
            elif event.key.keysym.sym == SDLK_q:
                if self._mh + 1 < self._tiles:
                    self._mh += 1
                    self._mw = self._tiles // self._mh
                    if self._tiles % self._mh > 0:
                        self._mw += 1
                    self._make_tilemap()
            elif event.key.keysym.sym == SDLK_z:
                if self._mw - 1 > 0:
                    self._mw -= 1
                    self._mh = self._tiles // self._mw
                    if self._tiles % self._mw > 0:
                        self._mh += 1
                    self._make_tilemap()
            elif event.key.keysym.sym == SDLK_x:
                if self._mw + 1 < self._tiles:
                    self._mw += 1
                    self._mh = self._tiles // self._mw
                    if self._tiles % self._mw > 0:
                        self._mh += 1
                    self._make_tilemap()
            elif event.key.keysym.sym == SDLK_RETURN:
                editscreen = self._state.get_screen(EditScreen)
                editscreen.set_tile(self._cury * self._mw + self._curx)
                self._state.active_screen(EditScreen)
            elif event.key.keysym.sym == SDLK_ESCAPE:
                self._state.active_screen(EditScreen)

    def update(self, time):
        self._cursorrad = update_cursor_effect(self._cursorrad, time, self._cursorl)

class PromptScreen():
    NAME='prompt'

    def __init__(self, state, caller, title, message, options, default=0):
        self._state = state
        self._caller = caller
        self._default = default
        self._vw = TILES_WIDTH
        self._vh = TILES_HEIGHT
        self._dl = display.DisplayList(self._state.ll)
        pos = 1
        need_text(self._state)
        tstext = self._state.tileset('ts_text')
        text, _, w, h = textbox.wrap_text(title, self._vw - 2, 2)
        self._title = textbox.TextBox(self._vw, h, self._vw, h,
                                      tstext, 'crusty_text')
        self._title.layer.scale(SCALE, SCALE)
        self._title.layer.pos(int(TEXT_SCALED_WIDTH), int(pos * TEXT_SCALED_HEIGHT))
        for num, line in enumerate(text):
            put_centered_line(self._title, line, num, self._vw - 2)
        self._dl.append(self._title.layer)
        pos += h + 1
        text, _, w, h = textbox.wrap_text(message, self._vw - 2, 5)
        self._message = textbox.TextBox(w, h, w, h,
                                        tstext, 'crusty_text')
        self._message.put_text(text, 0, 0)
        self._message.layer.scale(SCALE, SCALE)
        self._message.layer.pos(int(TEXT_SCALED_WIDTH), int(pos * TEXT_SCALED_HEIGHT))
        self._dl.append(self._message.layer)
        pos += h + 1
        self._menu = textbox.Menu(self._state.ll, tstext, 'crusty_text', self._vw - 2, None)
        for opt in options:
            self._menu.add_item(opt, onActivate=self._activate)
        self._menu.update()
        self._menu.move_selection(default)
        mlayer, self._cursorl = self._menu.layers
        mlayer.scale(SCALE, SCALE)
        mlayer.pos(int(TEXT_SCALED_WIDTH), int(TEXT_SCALED_HEIGHT * pos))
        self._dl.append(self._menu.displaylist)
        self._cursorrad = 0.0
 
    @property
    def dl(self):
        return self._dl

    def active(self):
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
        self._cursorrad = update_cursor_effect(self._cursorrad, time, self._cursorl)

    def _activate(self, priv, sel):
        self._return(sel)

    def _return(self, option):
        self._caller.set_option(option)
        self._state.active_screen(self._caller)

class ColorPickerScreen():
    NAME='colorpicker'

    def __init__(self, state, caller, vw, red=0, green=0, blue=0, alpha=SDL_ALPHA_OPAQUE):
        self._state = state
        self._caller = caller
        self._red = red
        self._green = green
        self._blue = blue
        self._alpha = alpha
        self._dl = display.DisplayList(self._state.ll)
        need_text(self._state)
        tstext = self._state.tileset('ts_text')
        self._title = textbox.TextBox(vw, 1, vw, 1,
                                      tstext, 'crusty_text')
        self._title.layer.scale(SCALE, SCALE)
        self._title.layer.pos(int(TEXT_SCALED_WIDTH), int(TEXT_SCALED_HEIGHT))
        put_centered_line(self._title, "Pick Color", 0, vw - 2)
        self._dl.append(self._title.layer)
        self._menu = textbox.Menu(self._state.ll, tstext, 'crusty_text', vw - 2, None, spacing=2)
        self._menu.add_item("Red", value=str(self._red), maxlen=3, onEnter=self.setred, onChange=self.changered)
        self._menu.add_item("Green", value=str(self._green), maxlen=3, onEnter=self.setgreen, onChange=self.changegreen)
        self._menu.add_item("Blue", value=str(self._blue), maxlen=3, onEnter=self.setblue, onChange=self.changeblue)
        self._menu.add_item("Alpha", value=str(self._alpha), maxlen=3, onEnter=self.setalpha, onChange=self.changealpha)
        self._menu.add_item("Accept", onActivate=self._accept)
        self._menu.update()
        mlayer, self._cursorl = self._menu.layers
        mlayer.scale(SCALE, SCALE)
        mlayer.pos(int(TEXT_SCALED_WIDTH), int(TEXT_SCALED_HEIGHT * 3))
        self._dl.append(self._menu.displaylist)
        cbtm = array.array('u', itertools.repeat('█', 64)).tounicode().encode('crusty_text')
        bgcm = array.array('I', itertools.repeat(display.make_color(85, 85, 85, SDL_ALPHA_OPAQUE), 72))
        bgcm[1::2] = array.array('I', itertools.repeat(display.make_color(170, 170, 170, SDL_ALPHA_OPAQUE), 36))
        colorbgtm = tstext.tilemap(8, 8, "Color Picker Checker BG")
        colorbgtm.map(0, 0, 8, 8, 8, cbtm)
        colorbgtm.attr_colormod(0, 0, 9, 8, 8, bgcm)
        colorbgtm.update()
        colorbgl = colorbgtm.layer("Color Picker Checker BG Layer")
        colorbgl.pos(int(TEXT_SCALED_WIDTH * 15), int(TEXT_SCALED_WIDTH * 3))
        self._dl.append(colorbgl)
        colortm = tstext.tilemap(8, 8, "Color Picker Color")
        colortm.map(0, 0, 8, 8, 8, cbtm)
        colortm.update()
        self._colorl = colortm.layer("Color Picker Color Layer")
        self._colorl.pos(int(TEXT_SCALED_WIDTH * 15), int(TEXT_SCALED_WIDTH * 3))
        self._update_color()
        self._dl.append(self._colorl)
        self._cursorrad = 0.0
 
    @property
    def dl(self):
        return self._dl

    def active(self):
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
        self._cursorrad = update_cursor_effect(self._cursorrad, time, self._cursorl)

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
    def __init__(self, renderer, pixfmt):
        self._renderer = renderer
        sdlfmt = SDL_AllocFormat(pixfmt)
        self._ll = cg.LayerList(renderer, pixfmt, log_cb_return, None)
        self._dl = display.DisplayList(self._ll)
        self._dl.append(display.make_color(0, 0, 0, SDL_ALPHA_OPAQUE))
        self._screen = None
        self._screendl = None
        self._screens = {}
        self._tilesets = {}
        self._tilemaps = {}
        self._running = True
        self._newscreen = False

    @property
    def running(self):
        return self._running

    def stop(self):
        self._running = False

    @property
    def ll(self):
        return self._ll

    def add_screen(self, screen, name=None):
        if name is None:
            name = screen.NAME
        self._screens[name] = screen(self)

    def active_screen(self, screen):
        try:
            if isinstance(screen, type):
                # lookup by type
                self._screen = self._screens[screen.NAME]
            else:
                # assign a screen object directly
                self._screen = screen
        except AttributeError:
            # lookup by name/key
            self._screen = self._screens[screen]
        self._screen.active()
        if self._screendl == None:
            self._screendl = self._dl.append(self._screen.dl)
        else:
            self._dl.replace(self._screendl, self._screen.dl)
        self._newscreen = True

    def get_screen(self, screen):
        name = screen
        try:
            name = screen.NAME
        except AttributeError:
            pass
        return self._screens[name]

    def _common_input(self, event):
        if event.type == SDL_QUIT:
            self.stop()

    def input(self, event):
        self._common_input(event)
        if self._running and not self._newscreen:
            self._screen.input(event)

    def update(self, time):
        if self._running:
            self._screen.update(time)
            self._dl.draw(display.SCREEN)
            SDL_RenderPresent(self._renderer)
        self._newscreen = False

    def add_tileset(self, ts, name):
        self._tilesets[name] = ts

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

def do_main(window, renderer, pixfmt):
    event = SDL_Event()

    state = MapeditState(renderer, pixfmt)
    state.add_screen(NewScreen)
    state.active_screen(NewScreen)
    lastTime = time.monotonic()
    while state.running:
        thisTime = time.monotonic()
        timetaken = thisTime - lastTime

        while SDL_PollEvent(event):
            state.input(event)

        state.update(timetaken)

        lastTime = thisTime

def main():
    SDL_Init(SDL_INIT_VIDEO)
    window, renderer, pixfmt = display.initialize_video("Map Editor", RES_WIDTH, RES_HEIGHT, SDL_WINDOW_SHOWN, SDL_RENDERER_PRESENTVSYNC | SDL_RENDERER_TARGETTEXTURE, batching=RENDERBATCHING)

    do_main(window, renderer, pixfmt)

    SDL_DestroyRenderer(renderer)
    SDL_DestroyWindow(window)
    SDL_Quit()


if __name__ == "__main__":
    try:
        main()
    except cg.CrustyException as e:
        print(crustyerror)
        raise e
