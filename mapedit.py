from sdl2 import *
import crustygame as cg
import array
from sys import argv
import time
import display
import textbox
import copy
import itertools

# debugging options
# enable SDL render batching, not very useful to disable but can be useful to
# see what if any difference it makes
# update: it actually makes a lot of difference
RENDERBATCHING=True
# enable tracing of display list processing
TRACEVIDEO=False
# enable tracing of audio sequencer processing
TRACEAUDIO=True

RES_WIDTH=640
RES_HEIGHT=480
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

class NewScreen():
    NAME='new'

    def __init__(self, state):
        self._state = state
        self._dl = display.DisplayList(self._state.ll)
        self._tw = TILES_WIDTH
        self._th = TILES_HEIGHT
        need_text(state)
        tstext = self._state.tileset('ts_text')
        self._tb = textbox.TextBox(self._tw, self._th,
                                   self._tw, self._th,
                                   tstext, 'crusty_text')
        self._tb.layer.scale(SCALE, SCALE)
        put_centered_line(self._tb, "New Tilemap", 1, self._tw)
        self._dl.append(self._tb.layer)
        self._menu = textbox.Menu(self._state.ll, tstext, 'crusty_text', 8, 8, 20, self, spacing=2)
        self._menu.add_item("Tileset", value='', maxlen=255, onEnter=NewScreen._setname)
        self._menu.add_item("Tile Width", value="8", maxlen=4, onEnter=NewScreen._settilewidth)
        self._menu.add_item("Tile Height", value="8", maxlen=4, onEnter=NewScreen._settileheight)
        self._menu.add_item("Map Width", value="32", maxlen=4, onEnter=NewScreen._setmapwidth)
        self._menu.add_item("Map Height", value="32", maxlen=4, onEnter=NewScreen._setmapheight)
        self._menu.add_item("Proceed", onActivate=NewScreen._proceed)
        self._menu.update()
        mlayer, _ = self._menu.layers
        mlayer.scale(SCALE, SCALE)
        mlayer.pos(int(TEXT_SCALED_WIDTH), int(TEXT_SCALED_HEIGHT * 3))
        self._dl.append(self._menu.displaylist)
        self._filename = ''
        self._tileset = None
        self._tilewidth = 8
        self._tileheight = 8
        self._mapwidth = 32
        self._mapheight = 32
        self._error = 0.0
        self._errorbox = None
        self._errorpos = self._dl.append(None)

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

    def _setname(self, sel, val):
        self._filename = val.lstrip().rstrip()
        return val

    def _settilewidth(self, sel, val):
        try:
            val = int(val)
        except ValueError:
            return None
        if val < 1:
            return None
        self._tilewidth = val
        return str(self._tilewidth)

    def _settileheight(self, sel, val):
        try:
            val = int(val)
        except ValueError:
            return None
        if val < 1:
            return None
        self._tileheight = val
        return str(self._tileheight)

    def _setmapwidth(self, sel, val):
        try:
            val = int(val)
        except ValueError:
            return None
        if val < 1:
            return None
        self._mapwidth = val
        return str(self._mapwidth)

    def _setmapheight(self, sel, val):
        try:
            val = int(val)
        except ValueError:
            return None
        if val < 1:
            return None
        self._mapheight = val
        return str(self._mapheight)

    def _proceed(self, sel):
        try:
            tileset = self._state.ll.tileset(self._filename, self._tilewidth, self._tileheight, None)
        except cg.CrustyException:
            self._error = ERROR_TIME
        self._state.add_tileset(tileset, 'ts_tm0')
        try:
            editscreen = self._state.get_screen('edit')
        except KeyError:
            self._state.add_screen(EditScreen)
            editscreen = self._state.get_screen('edit')
        editscreen.tilemap('ts_tm0', self._mapwidth, self._mapheight,
                                     self._tilewidth, self._tileheight)
        self._state.active_screen('edit')

class EditScreen():
    NAME='edit'

    def __init__(self, state):
        self._state = state
        need_text(state)
        self._tilemap = None

    @property
    def dl(self):
        return self._dl

    def active(self):
        if self._tilemap is None:
            raise Exception("Edit screen not fully set up.")

    def _update_cursor(self):
        xpos = self._curx
        ypos = self._cury
        xscroll = 0
        yscroll = 0
        halfx = self._vw // 2
        halfy = self._vh // 2
        if self._width != self._vw:
            if self._curx > halfx:
                if self._curx < self._width - halfx:
                    xscroll = self._curx - halfx
                    xpos = halfx
                else:
                    xscroll = self._width - self._vw
                    xpos = self._curx - (self._width - self._vw)
        if self._height != self._vh:
            if self._cury > halfy:
                if self._cury < self._height - halfy:
                    yscroll = self._cury - halfy
                    ypos = halfy
                else:
                    yscroll = self._height - self._vh
                    ypos = self._cury - (self._height - self._vh)
        self._stm.scroll(xscroll * self._twidth,
                         yscroll * self._theight)
        self._cursorl.pos((xpos - 1) * self._twidth,
                          (ypos - 1) * self._theight)

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
            elif event.key.keysym.sym == SDLK_ESCAPE:
                self._state.stop()

    def update(self, time):
        pass

    def tilemap(self, ts, w, h, tw, th):
        self._width = int(w)
        self._height = int(h)
        self._vw = TILES_WIDTH
        if self._vw > self._width:
            self._vw = self._width
        self._vh = TILES_HEIGHT
        if self._vh > self._height:
            self._vh = self._height
        self._twidth = int(tw)
        self._theight = int(th)
        self._curx = 0
        self._cury = 0
        self._dl = display.DisplayList(self._state.ll)
        self._tilemap = array.array('I', itertools.repeat(0, self._width * self._height))
        self._flags = copy.copy(self._tilemap)
        self._colormod = copy.copy(self._tilemap)
        self._stm = display.ScrollingTilemap(self._state.tileset(ts),
                                             self._tilemap,
                                             self._width, self._height,
                                             self._vw, self._vh,
                                             self._twidth, self._theight,
                                             flags=self._flags,
                                             colormod=self._colormod)
        self._stm.layer.scale(SCALE, SCALE)
        self._dl.append(self._stm.layer)
        tstext = self._state.tileset('ts_text')
        curwidth = int(self._twidth * SCALE / TEXT_SCALED_WIDTH)
        curheight = int(self._theight * SCALE / TEXT_SCALED_HEIGHT)
        self._cursortm = tstext.tilemap(curwidth + 2, curheight + 2, "Map Editor Cursor Tilemap")
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
        self._cursortm.map(0, 0, curwidth + 2, curwidth + 2, curheight + 2, tm.tounicode().encode('crusty_text'))
        self._cursortm.update(0, 0, 0, 0)
        self._cursorl = self._cursortm.layer("Map Editor Cursor Layer")
        self._cursorl.relative(self._stm.layer)
        self._update_cursor()
        self._dl.append(self._cursorl)


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
            name = screen.NAME
        except AttributeError:
            name = screen
        self._screen = self._screens[name]
        self._screen.active()
        if self._screendl == None:
            self._screendl = self._dl.append(self._screen.dl)
        else:
            self._dl.replace(self._screendl, self._screen.dl)
        self._newscreen = True

    def get_screen(self, name):
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
