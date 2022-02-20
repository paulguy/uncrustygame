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
# Toggleable GUI status/help panels
# Editor view scale option
# plane/project Save/Load
# Text tool using tilemap codec?
# Block copy/fill tool?
# Multiple layers?
# resizing tilemaps?
# Preview of multiple layers with independent scale/scroll speed/center?

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

def put_centered_line(tb, line, y, w):
    tb.put_text((line,), (w - len(line)) / 2, y)

def make_tilemap(w, h, tw, th, curx, cury, scale, ts,
                 tilemap, flags=None, colormod=None):
    vw = int(RES_WIDTH / scale) // tw
    if vw > w:
        vw = w
    vh = int(RES_HEIGHT / scale) // th
    if vh > h:
        vh = h
    if curx >= w:
        curx = w - 1
    if cury >= h:
        cury = h - 1
    stm = display.ScrollingTilemap(ts, tilemap,
                                   w, h, vw, vh, tw, th,
                                   flags=flags,
                                   colormod=colormod)
    return vw, vh, curx, cury, stm

def update_cursor(stm, cursorl, w, h, x, y, vw, vh, tw, th):
    xscroll = 0
    yscroll = 0
    halfw = vw // 2
    halfh = vh // 2
    if w != vw:
        if x > halfw:
            if x < w - halfw:
                xscroll = x - halfw
                x = halfx
            else:
                xscroll = w - vw
                x = x - (w - vw)
    if h != vh:
        if y > halfh:
            if y < h - halfh:
                yscroll = y - halfh
                y = halfh
            else:
                yscroll = h - vh
                y = y - (h - vh)
    stm.scroll(xscroll * tw, yscroll * th)
    stm.update()
    cursorl.pos(x * tw - TEXT_WIDTH, y * th - TEXT_HEIGHT)

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
        cursortm.update(0, 0, 0, 0)
        return cursortm

def update_cursor_effect(cursorrad, time, cursorl):
        cursorrad += math.pi * time
        cursorrad %= math.tau
        r, g, b = effects.color_from_rad(cursorrad, 0, 255)
        cursorl.colormod(display.make_color(r, g, b, SDL_ALPHA_OPAQUE))
        return(cursorrad)

class NewScreen():
    NAME='new'

    def __init__(self, state):
        self._state = state
        self._dl = display.DisplayList(self._state.ll)
        self._tw = TILES_WIDTH
        self._th = TILES_HEIGHT
        self._filename = TEXT_FILENAME
        self._tilewidth = TEXT_WIDTH
        self._tileheight = TEXT_HEIGHT
        self._mapwidth = 32
        self._mapheight = 32
        need_text(state)
        tstext = self._state.tileset('ts_text')
        self._tb = textbox.TextBox(self._tw, 1, self._tw, 1,
                                   tstext, 'crusty_text')
        put_centered_line(self._tb, "New Tilemap", 0, self._tw)
        self._tb.layer.pos(int(TEXT_SCALED_WIDTH), int(TEXT_SCALED_HEIGHT))
        self._tb.layer.scale(SCALE, SCALE)
        self._dl.append(self._tb.layer)
        self._menu = textbox.Menu(self._state.ll, tstext, 'crusty_text', TEXT_WIDTH, TEXT_HEIGHT, self._tw - 2, None, spacing=2)
        self._menu.add_item("Tileset", value=self._filename, maxlen=255, onEnter=self._setname)
        self._menu.add_item("Tile Width", value=str(self._tilewidth), maxlen=4, onEnter=self._settilewidth)
        self._menu.add_item("Tile Height", value=str(self._tileheight), maxlen=4, onEnter=self._settileheight)
        self._menu.add_item("Map Width", value=str(self._mapwidth), maxlen=4, onEnter=self._setmapwidth)
        self._menu.add_item("Map Height", value=str(self._mapheight), maxlen=4, onEnter=self._setmapheight)
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
                self._errorbox = textbox.TextBox(w, h, w, h, self._state.tileset('ts_text'), 'crusty_text')
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
        self._tilewidth = val
        return str(self._tilewidth)

    def _settileheight(self, priv, sel, val):
        try:
            val = int(val)
        except ValueError:
            return None
        if val < 1:
            return None
        self._tileheight = val
        return str(self._tileheight)

    def _setmapwidth(self, priv, sel, val):
        try:
            val = int(val)
        except ValueError:
            return None
        if val < 1:
            return None
        self._mapwidth = val
        return str(self._mapwidth)

    def _setmapheight(self, priv, sel, val):
        try:
            val = int(val)
        except ValueError:
            return None
        if val < 1:
            return None
        self._mapheight = val
        return str(self._mapheight)

    def _proceed(self, priv, sel):
        try:
            tileset = self._state.ll.tileset(self._filename, self._tilewidth, self._tileheight, None)
        except cg.CrustyException:
            self._error = ERROR_TIME
            return
        self._state.add_tileset(tileset, 'ts_tm0')
        try:
            editscreen = self._state.get_screen(EditScreen)
        except KeyError:
            self._state.add_screen(EditScreen)
            editscreen = self._state.get_screen(EditScreen)
        editscreen.tilemap('ts_tm0', self._mapwidth, self._mapheight,
                                     self._tilewidth, self._tileheight)
        self._state.active_screen(EditScreen)

class EditScreen():
    NAME='edit'

    def __init__(self, state):
        self._state = state
        self._tilemap = None
        self._cursorrad = 0.0
        self._tile = 0
        self._quitting = False
        self._red = 255
        self._green = 255
        self._blue = 255
        self._alpha = SDL_ALPHA_OPAQUE
        self._hflip = 0
        self._vflip = 0
        self._rotate = cg.TILEMAP_ROTATE_NONE

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
        update_cursor(self._stm, self._cursorl,
                      self._width, self._height,
                      self._curx, self._cury,
                      self._vw, self._vh,
                      self._twidth, self._theight)

    def _make_tilemap(self):
        self._vw, self._vh, self._curx, self._cury, self._stm = \
            make_tilemap(self._width, self._height,
                         self._twidth, self._theight,
                         0, 0,
                         SCALE, self._tileset,
                         self._tilemap, flags=self._flags,
                         colormod=self._colormod)

    def tilemap(self, ts, w, h, tw, th):
        self._tileset = self._state.tileset(ts)
        self._tiles = self._tileset.tiles()
        self._width = int(w)
        self._height = int(h)
        self._twidth = int(tw)
        self._theight = int(th)
        self._color = display.make_color(self._red, self._green, self._blue, self._alpha)
        self._attrib = display.make_attrib(self._hflip, self._vflip, self._rotate)
        self._dl = display.DisplayList(self._state.ll)
        self._tilemap = array.array('I', itertools.repeat(0, self._width * self._height))
        self._flags = array.array('I', itertools.repeat(self._attrib, self._width * self._height))
        self._colormod = array.array('I', itertools.repeat(self._color, self._width * self._height))
        self._make_tilemap()
        self._stm.layer.scale(SCALE, SCALE)
        self._dl.append(self._stm.layer)
        curwidth = int(self._twidth * SCALE / TEXT_SCALED_WIDTH)
        curheight = int(self._theight * SCALE / TEXT_SCALED_HEIGHT)
        self._cursortm = make_cursor(self._state, curwidth, curheight, "MapEditor Cursor Tilemap")
        self._cursorl = self._cursortm.layer("Map Editor Cursor Layer")
        self._cursorl.relative(self._stm.layer)
        self._update_cursor()
        self._dl.append(self._cursorl)
        self._state.add_screen(TileSelectScreen)
        selectscreen = self._state.get_screen(TileSelectScreen)
        selectscreen.tileset(ts, self._twidth, self._theight)

    def input(self, event):
        if event.type == SDL_KEYDOWN:
            if event.key.keysym.sym == SDLK_UP:
                if self._cury > 0:
                    self._cury -= 1
                    self._update_cursor()
            elif event.key.keysym.sym == SDLK_DOWN:
                if self._cury < self._height - 1:
                    self._cury += 1
                    self._update_cursor()
            elif event.key.keysym.sym == SDLK_LEFT:
                if self._curx > 0:
                    self._curx -= 1
                    self._update_cursor()
            elif event.key.keysym.sym == SDLK_RIGHT:
                if self._curx < self._width - 1:
                    self._curx += 1
                    self._update_cursor()
            elif event.key.keysym.sym == SDLK_SPACE:
                    self._tilemap[self._cury * self._width + self._curx] = self._tile
                    self._colormod[self._cury * self._width + self._curx] = self._color
                    self._flags[self._cury * self._width + self._curx] = self._attrib
                    self._stm.updateregion(self._curx, self._cury, 1, 1)
            elif event.key.keysym.sym == SDLK_KP_PLUS:
                val = self._tilemap[self._cury * self._width + self._curx] + 1
                if val < self._tiles:
                    self._tilemap[self._cury * self._width + self._curx] = val
                    self._stm.updateregion(self._curx, self._cury, 1, 1)
            elif event.key.keysym.sym == SDLK_KP_MINUS:
                val = self._tilemap[self._cury * self._width + self._curx] - 1
                if val >= 0:
                    self._tilemap[self._cury * self._width + self._curx] = val
                    self._stm.updateregion(self._curx, self._cury, 1, 1)
            elif event.key.keysym.sym == SDLK_v:
                if event.key.keysym.mod & KMOD_SHIFT != 0:
                    self._tile = self._tilemap[self._cury * self._width + self._curx]
                elif event.key.keysym.mod & KMOD_CTRL != 0:
                    self._tilemap[self._cury * self._width + self._curx] = self._tile
                    self._stm.updateregion(self._curx, self._cury, 1, 1)
                else:
                    self._state.active_screen(TileSelectScreen)
            elif event.key.keysym.sym == SDLK_c:
                if event.key.keysym.mod & KMOD_SHIFT != 0:
                    self._color = self._colormod[self._cury * self._width + self._curx]
                    self._red, self._green, self._blue, self._alpha = display.unmake_color(self._color)
                elif event.key.keysym.mod & KMOD_CTRL != 0:
                    self._colormod[self._cury * self._width + self._curx] = self._color
                    self._stm.updateregion(self._curx, self._cury, 1, 1)
                else:
                    colorpicker = ColorPickerScreen(self._state, self, self._red, self._green, self._blue, self._alpha)
                    self._state.active_screen(colorpicker)
            elif event.key.keysym.sym == SDLK_b:
                if event.key.keysym.mod & KMOD_SHIFT != 0:
                    self._attrib = self._flags[self._cury * self._width + self._curx]
                    self._hflip, self._vflip, self._rotate = display.unmake_attrib(self._attrib)
                elif event.key.keysym.mod & KMOD_CTRL != 0:
                    self._flags[self._cury * self._width + self._curx] = self._attrib
                    self._stm.updateregion(self._curx, self._cury, 1, 1)
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
                    self._rotate = cg.TILEMAP_ROTATE_90
                elif self._rotate == cg.TILEMAP_ROTATE_90:
                    self._rotate = cg.TILEMAP_ROTATE_180
                elif self._rotate == cg.TILEMAP_ROTATE_180:
                    self._rotate = cg.TILEMAP_ROTATE_270
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
        update_cursor(self._stm, self._cursorl,
                      self._width, self._height,
                      self._curx, self._cury,
                      self._vw, self._vh,
                      self._twidth, self._theight)

    def _make_tilemap(self):
        self._cursorl.relative(None)
        self._dl.replace(self._tmindex, None)
        tilemap = array.array('I', range(self._tiles))
        remainder = (self._width * self._height) - self._tiles
        tilemap.extend(array.array('I', itertools.repeat(0, remainder)))
        colormod = array.array('I', itertools.repeat(display.make_color(255, 255, 255, SDL_ALPHA_OPAQUE), self._tiles))
        colormod.extend(array.array('I', itertools.repeat(0, remainder)))
        self._vw, self._vh, self._curx, self._cury, self._stm = \
            make_tilemap(self._width, self._height,
                         self._twidth, self._theight,
                         self._curx, self._cury,
                         SCALE, self._tileset, tilemap,
                         colormod=colormod)
        if self._cury * self._width + self._curx >= self._tiles:
            self._cury = self._tiles // self._width - 1
        self._stm.layer.scale(self._scale, self._scale)
        self._dl.replace(self._tmindex, self._stm.layer)
        self._cursorl.relative(self._stm.layer)
        self._update_cursor()

    def tileset(self, ts, tw, th):
        self._tileset = self._state.tileset(ts)
        self._tiles = self._tileset.tiles()
        self._scale = 2.0
        side = math.sqrt(self._tiles)
        if side.is_integer():
            side = int(side)
        else:
            side = int(side) + 1
        self._width = side
        self._height = side
        self._twidth = int(tw)
        self._theight = int(th)
        self._dl = display.DisplayList(self._state.ll)
        curwidth = int(self._twidth * SCALE / TEXT_SCALED_WIDTH)
        curheight = int(self._theight * SCALE / TEXT_SCALED_HEIGHT)
        self._cursortm = make_cursor(self._state, curwidth, curheight, "Tile Select Cursor Tilemap")
        self._cursorl = self._cursortm.layer("Tile Select Cursor Layer")
        self._tmindex = self._dl.append(None)
        self._dl.append(self._cursorl)
        self._curx = 0
        self._cury = 0
        self._make_tilemap()

    def input(self, event):
        if event.type == SDL_KEYDOWN:
            if event.key.keysym.sym == SDLK_UP:
                if self._cury > 0:
                    self._cury -= 1
                    self._update_cursor()
            elif event.key.keysym.sym == SDLK_DOWN:
                if (self._cury + 1) * self._width + self._curx < self._tiles:
                    self._cury += 1
                    self._update_cursor()
            elif event.key.keysym.sym == SDLK_LEFT:
                if self._curx > 0:
                    self._curx -= 1
                    self._update_cursor()
            elif event.key.keysym.sym == SDLK_RIGHT:
                if self._curx + 1 < self._width and \
                   self._cury * self._width + (self._curx + 1) < self._tiles:
                    self._curx += 1
                    self._update_cursor()
            elif event.key.keysym.sym == SDLK_a:
                if self._height - 1 > 0:
                    self._height -= 1
                    self._width = self._tiles // self._height
                    if self._tiles % self._height > 0:
                        self._width += 1
                    self._make_tilemap()
            elif event.key.keysym.sym == SDLK_q:
                if self._height + 1 < self._tiles:
                    self._height += 1
                    self._width = self._tiles // self._height
                    if self._tiles % self._height > 0:
                        self._width += 1
                    self._make_tilemap()
            elif event.key.keysym.sym == SDLK_z:
                if self._width - 1 > 0:
                    self._width -= 1
                    self._height = self._tiles // self._width
                    if self._tiles % self._width > 0:
                        self._height += 1
                    self._make_tilemap()
            elif event.key.keysym.sym == SDLK_x:
                if self._width + 1 < self._tiles:
                    self._width += 1
                    self._height = self._tiles // self._width
                    if self._tiles % self._width > 0:
                        self._height += 1
                    self._make_tilemap()
            elif event.key.keysym.sym == SDLK_RETURN:
                editscreen = self._state.get_screen(EditScreen)
                editscreen.set_tile(self._cury * self._width + self._curx)
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
        self._tw = TILES_WIDTH
        self._th = TILES_HEIGHT
        self._dl = display.DisplayList(self._state.ll)
        pos = 1
        need_text(state)
        tstext = self._state.tileset('ts_text')
        text, _, w, h = textbox.wrap_text(title, self._tw - 2, 2)
        self._title = textbox.TextBox(self._tw, h, self._tw, h, tstext, 'crusty_text')
        self._title.layer.scale(SCALE, SCALE)
        self._title.layer.pos(int(TEXT_SCALED_WIDTH), int(pos * TEXT_SCALED_HEIGHT))
        for num, line in enumerate(text):
            put_centered_line(self._title, line, num, self._tw - 2)
        self._dl.append(self._title.layer)
        pos += h + 1
        text, _, w, h = textbox.wrap_text(message, self._tw - 2, 5)
        self._message = textbox.TextBox(w, h, w, h, tstext, 'crusty_text')
        self._message.put_text(text, 0, 0)
        self._message.layer.scale(SCALE, SCALE)
        self._message.layer.pos(int(TEXT_SCALED_WIDTH), int(pos * TEXT_SCALED_HEIGHT))
        self._dl.append(self._message.layer)
        pos += h + 1
        self._menu = textbox.Menu(self._state.ll, tstext, 'crusty_text', TEXT_WIDTH, TEXT_HEIGHT, self._tw - 2, None)
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

    def __init__(self, state, caller, red=0, green=0, blue=0, alpha=SDL_ALPHA_OPAQUE):
        self._state = state
        self._caller = caller
        self._red = red
        self._green = green
        self._blue = blue
        self._alpha = alpha
        self._tw = TILES_WIDTH
        self._th = TILES_HEIGHT
        self._dl = display.DisplayList(self._state.ll)
        need_text(state)
        tstext = self._state.tileset('ts_text')
        self._title = textbox.TextBox(self._tw, 1, self._tw, 1, tstext, 'crusty_text')
        self._title.layer.scale(SCALE, SCALE)
        self._title.layer.pos(int(TEXT_SCALED_WIDTH), int(TEXT_SCALED_HEIGHT))
        put_centered_line(self._title, "Pick Color", 0, self._tw - 2)
        self._dl.append(self._title.layer)
        self._menu = textbox.Menu(self._state.ll, tstext, 'crusty_text', TEXT_WIDTH, TEXT_HEIGHT, self._tw - 2, None, spacing=2)
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
        cbtm = array.array('u', itertools.repeat('█', 56)).tounicode().encode('crusty_text')
        bgcm = array.array('I', itertools.repeat(display.make_color(85, 85, 85, SDL_ALPHA_OPAQUE), 56))
        bgcm[1::2] = array.array('I', itertools.repeat(display.make_color(170, 170, 170, SDL_ALPHA_OPAQUE), 28))
        self._colorbg = display.ScrollingTilemap(tstext, cbtm, 7, 8, 7, 8, TEXT_WIDTH, TEXT_HEIGHT, colormod=bgcm)
        self._colorbg.layer.pos(int(TEXT_SCALED_WIDTH * 15), int(TEXT_SCALED_WIDTH * 3))
        self._dl.append(self._colorbg.layer)
        self._colorblock = display.ScrollingTilemap(tstext, cbtm, 7, 8, 7, 8, TEXT_WIDTH, TEXT_HEIGHT)
        self._colorblock.layer.pos(int(TEXT_SCALED_WIDTH * 15), int(TEXT_SCALED_WIDTH * 3))
        self._update_color()
        self._dl.append(self._colorblock.layer)
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
        self._colorblock.layer.colormod(display.make_color(self._red, self._green, self._blue, self._alpha))

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
