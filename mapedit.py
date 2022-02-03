from sdl2 import *
import crustygame as cg
import array
from itertools import repeat
from sys import argv
import display

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

# this is probably bad but whichever
def string_to_ints(string):
    array = list()

    for item in string:
        encoded = item.encode("utf-32")
        array.append(encoded[4] +
                     (encoded[5] * 0x100) +
                     (encoded[6] * 0x10000) +
                     (encoded[7] * 0x1000000))

    return(array)

def log_cb_return(priv, string):
    print(string, end='')

def common_input(event):
    if event.type == SDL_QUIT:
        return False
    elif event.type == SDL_KEYDOWN:
        if event.key.keysym.sym == SDLK_q:
            return False

def need_text(state):
    if 'ts_text' not in state:
        state['ts_text'] = state['ll'].tileset("cdemo/font.bmp", 8, 8, None)

class NewScreen():
    def __init__(self, state):
        self._state = state
        need_text(state)
        ll = self._state['ll']


    def input(self, event, state):
        return self

    def draw(self, time):
        pass

class EditScreen():
    def __init__(self, state):
        self._state = state

    def input(self, event, state):
        return self

    def draw(self, time):
        pass

def do_main(window, renderer, pixfmt):
    event = SDL_Event()
    sdlfmt = SDL_AllocFormat(pixfmt)
    ll = cg.LayerList(renderer, pixfmt, log_cb_return, None)


    state = {}
    state['ll'] = ll
    state['screens'] = []
    state['screens']['new'] = NewScreen(state)
    state['screens']['edit'] = EditScreen(state)
    screen = state['screens']['new']
    nextscreen = state['screens']['new']
    running = True
    lastTime = time.monotonic()
    while running:
        thisTime = time.monotonic()
        timetaken = thisTime - lastTime

        while SDL_PollEvent(event):
            running = common_input(event)
            if running == False:
                break
            # consume buffered events before transitioning to next screen
            # but still process quit events
            if nextscreen is screen:
                nextscreen = screen.input(event, state)

        if running:
            screen.draw(timetaken)

            SDL_RenderPresent(renderer)

            if nextscreen == None:
                running = False
            else:
                screen = nextscreen

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
