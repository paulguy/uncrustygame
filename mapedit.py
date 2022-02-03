from sdl2 import *
import crustygame as cg
import array
from sys import argv
import time
import display
import textbox

# debugging options
# enable SDL render batching, not very useful to disable but can be useful to
# see what if any difference it makes
RENDERBATCHING=True
# enable tracing of display list processing
TRACEVIDEO=False
# enable tracing of audio sequencer processing
TRACEAUDIO=True

RES_WIDTH=640
RES_HEIGHT=480
TEXT_FILENAME="cdemo/font.bmp"
TEXT_WIDTH=8
TEXT_HEIGHT=8


def need_text(state):
    try:
        state.tileset('ts_text')
    except KeyError:
        state.add_tileset(state.ll.tileset(TEXT_FILENAME, TEXT_WIDTH, TEXT_HEIGHT, None), 'ts_text')

def put_centered_line(tb, line, y, w):
    tb.put_text((line,), (w - len(line)) / 2, y)

class NewScreen():
    NAME='new'

    def __init__(self, state):
        self._state = state
        self._dl = display.DisplayList(self._state.ll)
        self._tw = RES_WIDTH / TEXT_WIDTH / 2
        self._th = RES_HEIGHT / TEXT_HEIGHT / 2
        need_text(state)
        self._tb = textbox.TextBox(state.ll,
                                   self._tw, self._th,
                                   self._tw, self._th,
                                   self._state.tileset('ts_text'))
        self._tb.layer.scale(2.0, 2.0)
        put_centered_line(self._tb, "New Tilemap", 1, self._tw)
        self._dl.append(self._tb.layer)

    @property
    def dl(self):
        return self._dl

    def input(self, event):
        pass

    def update(self, time):
        pass

class EditScreen():
    NAME='edit'

    def __init__(self, state):
        self._state = state

    def input(self, event, state):
        return self

    def update(self, time):
        pass

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
        if self._screendl == None:
            self._screendl = self._dl.append(self._screen.dl)
        else:
            self._dl.replace(self._screendl, self._screen.dl)
        self._newscreen = True

    def _common_input(self, event):
        if event.type == SDL_QUIT:
            self.stop()
        elif event.type == SDL_KEYDOWN:
            if event.key.keysym.sym == SDLK_q:
                self.stop()

    def input(self, event):
        self._common_input(event)
        if not self._running or self._newscreen:
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


def log_cb_return(priv, string):
    print(string, end='')

def do_main(window, renderer, pixfmt):
    event = SDL_Event()

    state = MapeditState(renderer, pixfmt)
    state.add_screen(NewScreen)
    state.add_screen(EditScreen)
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
    main()
