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
import copy
import itertools
import math
import lib.display as display
import lib.textbox as textbox
import lib.effects as effects
import lib.layers as layers

# debugging options
# enable SDL render batching, no idea why you'd disable it
RENDERBATCHING=True
# enable tracing of display list processing
TRACEVIDEO=False

RES_WIDTH=1024
RES_HEIGHT=768
ERROR_TIME=10.0
FULL_RENDERS = 2

crustyerror = ''

@dataclass(frozen=True)
class TilesetDesc():
    filename : str
    width : int
    height : int

class MapScreen():
    def _build_screen(self):
        self._vw, self._vh = self._state.window
        if self._view is None:
            self._view = layers.MapView(self._state,
                                        self._descs, self._maps, self._layers,
                                        self._vw, self._vh)
        else:
            self._view.resize(self._vw, self._vh)
        self._dl.replace(self._viewindex, self._view.dl)

    def __init__(self, state, name):
        self._state = state
        _, self._descs, self._maps, self._layers = layers.load_map(name)
        self._view = None
        self._xspeed = 0.0
        self._yspeed = 0.0
        self._posx = 0
        self._posy = 0
        self._dl = display.DisplayList(self._state.ll)
        self._viewindex = self._dl.append(None)
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
                self._view.scroll(0, 0)
            elif event.key.keysym.sym == SDLK_ESCAPE:
                self._state.stop()
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
            self._view.scroll(self._posx, self._posy)


class GameState():
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
            self._resizing = GameState.RESIZE_COOLDOWN

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
    state = GameState(renderer, pixfmt, rect.w, rect.h,
                      layers.FONT_FILENAME, layers.FONT_MAPNAME,
                      layers.FONT_WIDTH, layers.FONT_HEIGHT,
                      layers.FONT_SCALE)
    mapscreen = MapScreen(state, "maps/Example")
    state.active_screen(mapscreen)

    while state.running:
        state.frame()
        SDL_RenderPresent(renderer)

def main():
    SDL_Init(SDL_INIT_VIDEO)
    window, renderer, pixfmt = display.initialize_video("Game", RES_WIDTH, RES_HEIGHT, SDL_WINDOW_SHOWN | SDL_WINDOW_RESIZABLE, SDL_RENDERER_PRESENTVSYNC | SDL_RENDERER_TARGETTEXTURE, batching=RENDERBATCHING)

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
