#!/usr/bin/env python
from sdl2 import *
import crustygame as cg
import array
from sys import argv
import time
from dataclasses import dataclass
from traceback import print_tb
from enum import Enum, IntEnum
import json
import copy
import itertools
import math
import lib.display as display
import lib.textbox as textbox
import lib.effects as effects
import lib.layers as layers
from lib.collision import SpriteEdge, first_hit

#TODO:
# Allow player to stand on a slope tip
# more player movement (following slopes, avoiding bonking on slopes)
# loading in and displaying multiple maps in the right spots
#  and unloading oldest off screen maps after a certain pool size is reached
# player transitioning properly between maps and colliding on both maps
# camera blocking
# actors (and all their interactions with the environment around them)
# jump-through platforms
# water physics

# debugging options
# enable SDL render batching, no idea why you'd disable it
RENDERBATCHING=True
# enable tracing of display list processing
TRACEVIDEO=False

RES_WIDTH=800
RES_HEIGHT=600
VIEW_WIDTH=400
VIEW_HEIGHT=300
ERROR_TIME=10.0
DEFAULT_MAP="maps/Example"

PLAYER_GFX = "gfx/face.bmp"
PLAYER_WIDTH=16
PLAYER_HEIGHT=16
PLAYER_MAXSPEED=6
PLAYER_JUMP_POWER=5
PLAYER_ACCEL=20
PLAYER_AIR_ACCEL=10
PLAYER_GRAVITY=5
PLAYER_MAX_FALLSPEED=20
PLAYER_BRAKING=12
PLAYER_AIR_BRAKING=2
PLAYER_MINSPEED=0.001
EDGE_FUDGE=0.01
EDGE_FUDGIER=EDGE_FUDGE/10

crustyerror = ''

@dataclass(frozen=True)
class TilesetDesc():
    filename : str
    width : int
    height : int

class PlayerState(IntEnum):
    AIR = 0,
    GROUND = 1

class GameInputMode(Enum):
    NORMAL = 0,
    RECORD = 1,
    RECORDPAUSE = 2,
    PLAY = 3,
    PLAYSTOP = 4

class MapScreen():
    def _first_hit(self, x, y, dx, dy, val, edge):
        return first_hit(x, y, dx, dy, self._tw, self._th, val, edge,
                         self._solids[1][0], self._solids[0].mw)

    def _collision_left(self):
        h, x, y = self._first_hit(self._playerx,
                                  self._playery,
                                  -self._tw, 0,
                                  False, SpriteEdge.TopLeft)
        if h and x > -EDGE_FUDGE:
            return True
        h, x, y = self._first_hit(self._playerx,
                                  self._playery + PLAYER_HEIGHT,
                                  -self._tw, 0,
                                  False, SpriteEdge.BottomLeft)
        if h and x > -EDGE_FUDGE:
            return True
        return False

    def _collision_right(self):
        h, x, y = self._first_hit(self._playerx + PLAYER_WIDTH,
                                  self._playery,
                                  self._tw, 0,
                                  False, SpriteEdge.TopRight)
        if h and x < EDGE_FUDGE:
            return True
        h, x, y = self._first_hit(self._playerx + PLAYER_WIDTH,
                                  self._playery + PLAYER_HEIGHT,
                                  self._tw, 0,
                                  False, SpriteEdge.BottomRight)
        if h and x < EDGE_FUDGE:
            return True
        return False

    def _collision_up(self):
        h, x, y = self._first_hit(self._playerx,
                                  self._playery,
                                  0, -self._th,
                                  False, SpriteEdge.TopLeft)
        if h and y > -EDGE_FUDGE:
            return True
        h, x, y = self._first_hit(self._playerx + PLAYER_WIDTH,
                                  self._playery,
                                  0, -self._th,
                                  False, SpriteEdge.TopRight)
        if h and y > -EDGE_FUDGE:
            return True
        return False

    def _collision_down(self):
        h, x, y = self._first_hit(self._playerx,
                                  self._playery + PLAYER_HEIGHT,
                                  0, self._th,
                                  False, SpriteEdge.BottomLeft)
        if h and y < EDGE_FUDGE:
            return True
        h, x, y = self._first_hit(self._playerx + PLAYER_WIDTH,
                                  self._playery + PLAYER_HEIGHT,
                                  0, self._th,
                                  False, SpriteEdge.BottomRight)
        if h and y < EDGE_FUDGE:
            return True
        return False

    def _move_player(self):
        dx = self._pspeedx
        dy = self._pspeedy
        movedx = 0
        movedy = 0
        while dx != 0 or dy != 0:
            dx2 = dx
            dy2 = dy
            x = self._playerx + dx
            y = self._playery + dy
            if self._pstate == PlayerState.AIR:
                if dx2 > 0:
                    if dy2 > 0:
                        ht, xt, yt = \
                            self._first_hit(self._playerx + PLAYER_WIDTH,
                                            self._playery,
                                            dx2, dy2,
                                            False,
                                            SpriteEdge.TopRight)
                        hc, xc, yc = \
                            self._first_hit(self._playerx + PLAYER_WIDTH,
                                            self._playery + PLAYER_HEIGHT,
                                            dx2, dy2,
                                            False,
                                            SpriteEdge.BottomRight)
                        hb, xb, yb = \
                            self._first_hit(self._playerx,
                                            self._playery + PLAYER_HEIGHT,
                                            dx2, dy2,
                                            False,
                                            SpriteEdge.BottomLeft)
                        if hb and xb < dx2:
                            if yb > EDGE_FUDGE:
                                dy2 = yb - EDGE_FUDGIER
                            elif self._collision_down():
                                dy2 = 0
                                self._pstate = PlayerState.GROUND
                        if ht and yt < dy2:
                            if xt > EDGE_FUDGE:
                                dx2 = xt - EDGE_FUDGIER
                            elif self._collision_right():
                                dx2 = 0
                                dx = 0
                        if hc:
                            if xc < dx2:
                                if xc > EDGE_FUDGE:
                                    dx2 = xc - EDGE_FUDGIER
                                elif self._collision_right():
                                    dx2 = 0
                                    dx = 0
                            if yc < dy2:
                                if yc > EDGE_FUDGE:
                                    dy2 = yc - EDGE_FUDGIER
                                elif self._collision_down():
                                    dy2 = 0
                                    self._pstate = PlayerState.GROUND
                    elif dy2 < 0:
                        ht, xt, yt = \
                            self._first_hit(self._playerx, self._playery,
                                            dx2, dy2,
                                            False,
                                            SpriteEdge.TopLeft)
                        hc, xc, yc = \
                            self._first_hit(self._playerx + PLAYER_WIDTH,
                                            self._playery,
                                            dx2, dy2,
                                            False,
                                            SpriteEdge.TopRight)
                        hb, xb, yb = \
                            self._first_hit(self._playerx + PLAYER_WIDTH,
                                            self._playery + PLAYER_HEIGHT,
                                            dx2, dy2,
                                            False,
                                            SpriteEdge.BottomRight)
                        if hb and xb < dx2:
                            if xb > EDGE_FUDGE:
                                dx2 = xb - EDGE_FUDGIER
                            elif self._collision_right():
                                dx2 = 0
                                dx = 0
                        # greater is less negative
                        if ht and yt > dy2:
                            if yt < -EDGE_FUDGE:
                                dy2 = yt + EDGE_FUDGIER
                            elif self._collision_up():
                                dy2 = 0
                                dy = 0
                        if hc:
                            if xc < dx2:
                                if xc > EDGE_FUDGE:
                                    dx2 = xc - EDGE_FUDGIER
                                elif self._collision_right():
                                    dx2 = 0
                                    dx = 0
                            if yc > dy2:
                                if yc < -EDGE_FUDGE:
                                    dy2 = yc + EDGE_FUDGIER
                                elif self._collision_up():
                                    dy2 = 0
                                    dy = 0
                    else:
                        ht, xt, yt = \
                            self._first_hit(self._playerx + PLAYER_WIDTH,
                                            self._playery,
                                            dx2, 0,
                                            False,
                                            SpriteEdge.TopRight)
                        hb, xb, yb = \
                            self._first_hit(self._playerx + PLAYER_WIDTH,
                                            self._playery + PLAYER_HEIGHT,
                                            dx2, 0,
                                            False,
                                            SpriteEdge.BottomRight)
                        if ht and xt < dx:
                            if xt > EDGE_FUDGE:
                                dx2 = xt - EDGE_FUDGIER
                            else:
                                dx2 = 0
                                dx = 0
                        if hb and xb < dx:
                            if xb > EDGE_FUDGE:
                                dx2 = xb - EDGE_FUDGIER
                            else:
                                dx2 = 0
                                dx = 0
                elif dx2 < 0:
                    if dy2 > 0:
                        ht, xt, yt = \
                            self._first_hit(self._playerx, self._playery,
                                            dx2, dy2,
                                            False,
                                            SpriteEdge.TopLeft)
                        hc, xc, yc = \
                            self._first_hit(self._playerx,
                                            self._playery + PLAYER_HEIGHT,
                                            dx2, dy2,
                                            False,
                                            SpriteEdge.BottomLeft)
                        hb, xb, yb = \
                            self._first_hit(self._playerx + PLAYER_WIDTH,
                                            self._playery + PLAYER_HEIGHT,
                                            dx2, dy2,
                                            False,
                                            SpriteEdge.BottomRight)
                        if ht and xt > dx2:
                            if xt < -EDGE_FUDGE:
                                dx2 = xt + EDGE_FUDGIER
                            elif self._collision_left():
                                dx2 = 0
                                dx = 0
                        if hb and yb < dy2:
                            if yb > EDGE_FUDGE:
                                dy2 = yb - EDGE_FUDGIER
                            elif self._collision_down():
                                dy2 = 0
                                self._pstate = PlayerState.GROUND
                        if hc:
                            if xc > dx2:
                                if xc < -EDGE_FUDGE:
                                    dx2 = xc + EDGE_FUDGIER
                                elif self._collision_left():
                                    dx2 = 0
                                    dx = 0
                            if yc < dy2:
                                if yc > EDGE_FUDGE:
                                    dy2 = yc - EDGE_FUDGIER
                                elif self._collision_down():
                                    dy2 = 0
                                    self._pstate = PlayerState.GROUND
                    elif dy2 < 0:
                        ht, xt, yt = \
                            self._first_hit(self._playerx + PLAYER_WIDTH,
                                            self._playery,
                                            dx2, dy2,
                                            False,
                                            SpriteEdge.TopRight)
                        hc, xc, yc = \
                            self._first_hit(self._playerx, self._playery,
                                            dx2, dy2,
                                            False,
                                            SpriteEdge.TopLeft)
                        hb, xb, yb = \
                            self._first_hit(self._playerx,
                                            self._playery + PLAYER_HEIGHT,
                                            dx2, dy2,
                                            False,
                                            SpriteEdge.BottomLeft)
                        if hb and xb > dx2:
                            if xb < -EDGE_FUDGE:
                                dx2 = xb + EDGE_FUDGIER
                            elif self._collision_left():
                                dx2 = 0
                                dx = 0
                        if ht and yt > dy2:
                            if yt < -EDGE_FUDGE:
                                dy2 = yt + EDGE_FUDGIER
                            elif self._collision_up():
                                dy2 = 0
                                dy = 0
                        if hc:
                            if xc > dx2:
                                if xc < -EDGE_FUDGE:
                                    dx2 = xc + EDGE_FUDGIER
                                elif self._collision_left():
                                    dx2 = 0
                                    dx = 0
                            if yc > dy2:
                                if yc < -EDGE_FUDGE:
                                    dy2 = yc + EDGE_FUDGIER
                                elif self._collision_up():
                                    dy2 = 0
                                    dy = 0
                    else:
                        ht, xt, yt = \
                            self._first_hit(self._playerx, self._playery,
                                            dx2, 0,
                                            False,
                                            SpriteEdge.TopLeft)
                        hb, xb, yb = \
                            self._first_hit(self._playerx,
                                            self._playery + PLAYER_HEIGHT,
                                            dx2, 0,
                                            False,
                                            SpriteEdge.BottomLeft)
                        if ht and xt > dx2:
                            if xt < -EDGE_FUDGE:
                                dx2 = xt + EDGE_FUDGIER
                            else:
                                dx2 = 0
                                dx = 0
                        if hb and xb > dx2:
                            if xb < -EDGE_FUDGE:
                                dx2 = xb + EDGE_FUDGIER
                            else:
                                dx2 = 0
                                dx = 0
                else:
                    if dy2 > 0:
                        hl, xl, yl = \
                            self._first_hit(self._playerx,
                                            self._playery + PLAYER_HEIGHT,
                                            0, dy2,
                                            False,
                                            SpriteEdge.BottomLeft)
                        hr, xr, yr = \
                            self._first_hit(self._playerx + PLAYER_WIDTH,
                                            self._playery + PLAYER_HEIGHT,
                                            0, dy2,
                                            False,
                                            SpriteEdge.BottomRight)
                        if hl and yl < dy2:
                            if yl > EDGE_FUDGE:
                                dy2 = yl - EDGE_FUDGIER
                            else:
                                dy2 = 0
                                self._pstate = PlayerState.GROUND
                        if hr and yr < dy2:
                            if yr > EDGE_FUDGE:
                                dy2 = yr - EDGE_FUDGIER
                            else:
                                dy2 = 0
                                self._pstate = PlayerState.GROUND
                    elif dy2 < 0:
                        hl, xl, yl = \
                            self._first_hit(self._playerx, self._playery,
                                            0, dy2,
                                            False,
                                            SpriteEdge.TopLeft)
                        hr, xr, yr = \
                            self._first_hit(self._playerx + PLAYER_WIDTH,
                                            self._playery,
                                            0, dy2,
                                            False,
                                            SpriteEdge.TopRight)
                        if hl and yl > dy2:
                            if yl < -EDGE_FUDGE:
                                dy2 = yl + EDGE_FUDGIER
                            else:
                                dy2 = 0
                                dy = 0
                        if hr and yr > dy2:
                            if yr < -EDGE_FUDGE:
                                dy2 = yr + EDGE_FUDGIER
                            else:
                                dy2 = 0
                                dy = 0
            elif self._pstate == PlayerState.GROUND:
                if not self._collision_down():
                    self._pspeedy = 0.0
                    self._pstate = PlayerState.AIR
                    continue
                dy = 0
                dy2 = 0
                if dx < 0:
                    ht, xt, yt = \
                        self._first_hit(self._playerx,
                                        self._playery,
                                        dx2, 0,
                                        False,
                                        SpriteEdge.TopLeft)
                    hb, xb, yb = \
                        self._first_hit(self._playerx,
                                        self._playery + PLAYER_HEIGHT,
                                        dx2, 0,
                                        False,
                                        SpriteEdge.BottomLeft)
                    if ht and xt > dx:
                        if xt < -EDGE_FUDGE:
                            dx2 = xt + EDGE_FUDGIER
                        else:
                            dx2 = 0
                            dx = 0
                    if hb and xb > dx:
                        if xb < -EDGE_FUDGE:
                            dx2 = xb + EDGE_FUDGIER
                        else:
                            dx2 = 0
                            dx = 0
                elif dx > 0:
                    ht, xt, yt = \
                        self._first_hit(self._playerx + PLAYER_WIDTH,
                                        self._playery,
                                        dx2, 0,
                                        False,
                                        SpriteEdge.TopRight)
                    hb, xb, yb = \
                        self._first_hit(self._playerx + PLAYER_WIDTH,
                                        self._playery + PLAYER_HEIGHT,
                                        dx2, 0,
                                        False,
                                        SpriteEdge.BottomRight)
                    if ht and xt < dx:
                        if xt > EDGE_FUDGE:
                            dx2 = xt - EDGE_FUDGIER
                        else:
                            dx2 = 0
                            dx = 0
                    if hb and xb < dx:
                        if xb > EDGE_FUDGE:
                            dx2 = xb - EDGE_FUDGIER
                        else:
                            dx2 = 0
                            dx = 0
            else:
                raise ValueError("Invalid player state: {}".format(self._pstate))

            self._playerx += dx2
            self._playery += dy2
            movedx += dx2
            movedy += dy2
            dx -= dx2
            if (self._pspeedx < 0 and dx >= -EDGE_FUDGE) or \
               (self._pspeedx > 0 and dx <= EDGE_FUDGE):
                dx = 0
            dy -= dy2
            if (self._pspeedy < 0 and dy >= -EDGE_FUDGE) or \
               (self._pspeedy > 0 and dy <= EDGE_FUDGE):
                dy = 0

        if (self._pspeedx < 0 and movedx >= -EDGE_FUDGE) or \
           (self._pspeedx > 0 and movedx <= EDGE_FUDGE):
            self._pspeedx = 0.0
        if (self._pspeedy < 0 and movedy >= -EDGE_FUDGE) or \
           (self._pspeedy > 0 and movedy <= EDGE_FUDGE):
            self._pspeedy = 0.0

    def _update_scroll(self):
        self._view.scroll(round(self._playerx - self._centerx),
                          round(self._playery - self._centery))
        self._playerl.pos(round(self._centerx), round(self._centery))

    def _read_demo_line(self):
        try:
            self._nexttime, self._nextpdirx, self._nextpdiry = \
                self._demofile.readline().split()
        except ValueError:
            self._demofile.close()
            self._demofile = None
            self._mode = GameInputMode.NORMAL
            return
        self._nexttime = float(self._nexttime)
        self._nextpdirx = int(self._nextpdirx)
        self._nextpdiry = int(self._nextpdiry)

    def _build_screen(self):
        self._vw, self._vh = self._state.window
        self._centerx = (self._vw - PLAYER_WIDTH) / 2
        self._centery = (self._vh - PLAYER_HEIGHT) / 2
        if self._view is None:
            self._view = layers.MapView(self._state,
                                        self._descs, self._maps, self._layers,
                                        self._vw, self._vh)
            self._playerl.relative(self._view.layer)
        else:
            self._view.resize(self._vw, self._vh)
        self._update_scroll()
        self._dl.replace(self._viewindex, self._view.dl)
        self._tb = textbox.TextBox(self._state.ll,
                                   32 * self._state.font.ts.width(),
                                   6 * self._state.font.ts.height(),
                                   32, 6, self._state.font)
        self._tb.internal.colormod(display.make_color(255, 255, 255, 96))
        self._dl.replace(self._tbindex, self._tb.draw)

    def _get_demo_filename(self):
        return "{}.demo".format(self._demoname)

    def __init__(self, state, name, mode=GameInputMode.NORMAL, demoname=None):
        self._state = state
        self._curtime = 0.0
        self._mode = mode
        self._playstop = False
        self._pause = False
        self._mapname = name
        self._demoname = demoname
        self._demofile = None
        if self._mode == GameInputMode.PLAYSTOP:
            self._playstop = True
            self._mode = GameInputMode.PLAY
        elif self._mode == GameInputMode.RECORD:
            # start from the beginning, avoid saving maps from a recording
            # from the beginning.
            self._demofile = open(self._get_demo_filename(), 'w')
        elif self._mode == GameInputMode.RECORDPAUSE:
            self._pause = True
            self._mode = GameInputMode.RECORD
        if self._mode == GameInputMode.PLAY:
            if self._demoname is None:
                self._demoname = self._mapname
            self._demofile = open(self._get_demo_filename(), 'r')
            self._lasttime = 0
            self._step = False
            self._read_demo_line()
        settings, self._descs, self._maps, self._layers, _, _ = layers.load_map(self._mapname)
        self._solids = None
        # get the params tilemap out
        for num, desc in enumerate(self._descs):
            if desc.name == 'solids':
                self._solids = (self._descs[num], self._maps[num])
                del self._descs[num]
                del self._maps[num]
                # take out layers which display this tilemap
                # also repoint layers offset by this removed tilemap
                for num2, layer in enumerate(self._layers):
                    if layer.tilemap == num:
                        del self._layers[num2]
                        # remove references to this removed layer
                        # also repoint indexes offset by this removed layer
                        for layer in self._layers:
                            if layer.relative == num2:
                                layer.relative = -1
                            elif layer.relative > num2:
                                layer.relative -= 1
                    elif layer.tilemap > num:
                        layer.tilemap -= 1
                break
        if self._solids is None:
            raise ValueError("No 'solids' map found.")
        self._tw = self._solids[0].tw
        self._th = self._solids[0].th
        for layer in self._layers:
            layer.scalex = 1.0
            layer.scaley = 1.0
        playerdesc = self._state.add_tileset(PLAYER_GFX,
                                             PLAYER_WIDTH, PLAYER_HEIGHT)
        playerts = self._state.tileset_desc(playerdesc)
        playertm = playerts.tilemap(1, 1, "Player Tilemap")
        playertm.map(0, 0, 1, 1, 1, array.array('I', (0,)))
        playertm.update()
        self._playerl = playertm.layer("Player Layer")
        # maybe have some global state container later i guess.
        try:
            self._pdirx = int(settings['player_dir_x'])
        except KeyError:
            self._pdirx = 0
        try:
            self._pdiry = int(settings['player_dir_y'])
        except KeyError:
            self._pdiry = 0
        try:
            self._pstate = PlayerState(int(settings['player_state']))
        except KeyError:
            self._pstate = PlayerState.AIR
        try:
            self._pspeedx = float(settings['player_speed_x'])
        except KeyError:
            self._pspeedx = 0.0
        try:
            self._pspeedy = float(settings['player_speed_y'])
        except KeyError:
            self._pspeedy = 0.0
        self._playerx = float(settings['player_x'])
        self._playery = float(settings['player_y'])
        self._move_player()
        self._dl = display.DisplayList(self._state.ll)
        self._viewindex = self._dl.append(None)
        self._dl.append(self._playerl)
        self._tbindex = self._dl.append(None)
        self._view = None
        self._build_screen()

    def active(self):
        pass

    @property
    def dl(self):
        return self._dl

    def input(self, event):
        if self._mode == GameInputMode.PLAY:
            if event.type == SDL_KEYDOWN:
                if event.key.keysym.sym == SDLK_ESCAPE:
                    self._demofile.close()
                    self._state.stop()
                elif event.key.keysym.sym == SDLK_PERIOD:
                    self._pause = True
                    self._step = True
                elif event.key.keysym.sym == SDLK_SPACE:
                    self._pause = not self._pause
        else:
            if event.type == SDL_KEYDOWN and event.key.repeat == 0:
                if event.key.keysym.sym == SDLK_LEFT:
                    self._pdirx = -1
                elif event.key.keysym.sym == SDLK_RIGHT:
                    self._pdirx = 1
                elif event.key.keysym.sym == SDLK_SPACE:
                    self._pdiry = -1
                elif event.key.keysym.sym == SDLK_ESCAPE:
                    if self._demofile is not None:
                        self._demofile.close()
                    self._state.stop()
            elif event.type == SDL_KEYUP:
                if event.key.keysym.sym == SDLK_LEFT:
                    if self._pdirx < 0:
                        self._pdirx = 0
                elif event.key.keysym.sym == SDLK_RIGHT:
                    if self._pdirx > 0:
                        self._pdirx = 0
        if self._mode == GameInputMode.RECORD:
            if event.type == SDL_KEYDOWN and event.key.repeat == 0:
                if event.key.keysym.sym == SDLK_r:
                    if not self._pause:
                        self._pause = True
                        self._demofile.close()
                        self._demofile = None
                    else:
                        self._pause = False

    def _do_movement(self, time):
        if self._mode == GameInputMode.PLAY:
            print("--- {} {}".format(time, self._state.frameTime))

        accel = PLAYER_ACCEL
        braking = PLAYER_BRAKING
        if self._pstate == PlayerState.AIR:
            accel = PLAYER_AIR_ACCEL
            braking = PLAYER_AIR_BRAKING
        if self._pdirx < 0:
            if self._pspeedx > 0.0:
                self._pspeedx /= braking
            else:
                self._pspeedx -= time * \
                    ((PLAYER_MAXSPEED + self._pspeedx) / PLAYER_MAXSPEED) * \
                    accel
        elif self._pdirx > 0:
            if self._pspeedx < 0.0:
                self._pspeedx /= braking
            else:
                self._pspeedx += time * \
                    ((PLAYER_MAXSPEED - self._pspeedx) / PLAYER_MAXSPEED) * \
                    accel
        else:
            self._pspeedx /= braking
        if abs(self._pspeedx) < PLAYER_MINSPEED:
            self._pspeedx = 0.0
        if self._pdiry < 0:
            if self._pstate == PlayerState.GROUND:
                self._pstate = PlayerState.AIR
                self._pspeedy = -PLAYER_JUMP_POWER
            self._pdiry = 0
        if self._pstate == PlayerState.AIR:
            self._pspeedy += time * \
                ((PLAYER_MAX_FALLSPEED - self._pspeedy) / PLAYER_MAX_FALLSPEED) * \
                PLAYER_GRAVITY
        if abs(self._pspeedy) < PLAYER_MINSPEED:
            self._pspeedy = 0.0
        self._move_player()
        self._update_scroll()

        status, _, _, _ = textbox.wrap_text("FT:  {:.3}\nCPU: {:.3}\nPX:  {:.3}\nPY:  {:.3}\nPSX: {:.3}\nPSY: {:.3}".format(time, self._state.frameTime, self._playerx, self._playery, self._pspeedx, self._pspeedy), 32, 6)
        self._tb.clear(0, 0, 32, 6)
        self._tb.put_text(status)

    def _play_step(self, time):
        time = self._nexttime - self._lasttime
        self._lasttime = self._nexttime
        self._pdirx = self._nextpdirx
        self._pdiry = self._nextpdiry
        self._do_movement(time)
        self._read_demo_line()
        if self._mode == GameInputMode.NORMAL:
            if self._playstop:
                self._state.stop()
            return False
        return True

    def update(self, time):
        if self._mode == GameInputMode.RECORD:
            if not self._pause:
                if self._demofile is None:
                    self._demofile = open(self._get_demo_filename(), 'w')
                    settings = dict()
                    settings['player_dir_x'] = self._pdirx
                    settings['player_dir_y'] = self._pdiry
                    settings['player_state'] = self._pstate.value
                    settings['player_speed_x'] = self._pspeedx
                    settings['player_speed_y'] = self._pspeedy
                    settings['player_x'] = self._playerx
                    settings['player_y'] = self._playery
                    descs = self._descs.copy()
                    descs.append(self._solids[0])
                    maps = self._maps.copy()
                    maps.append(self._solids[1])
                    layers.save_map(self._demoname, settings,
                                    descs, maps, self._layers,
                                    None, None)
                    self._curtime = 0.0
                self._curtime += time
                self._demofile.write("{} {} {}\n".format(self._curtime,
                                                         self._pdirx,
                                                         self._pdiry))
        elif self._mode == GameInputMode.PLAY:
            if self._pause:
                if self._step == True:
                    self._step = False
                    self._play_step(time)
                    self._curtime = self._lasttime
            else:
                self._curtime += time
                while self._curtime >= self._nexttime:
                    if not self._play_step(time):
                        break
            return
        else:
            self._curtime += time

        self._do_movement(time)

class GameState():
    RESIZE_COOLDOWN = 0.25

    def _set_size(self):
        if SDL_RenderSetLogicalSize(self._renderer, self._vw, self._vh) < 0:
            raise Exception("SDL_RenderSetLogicalSize: {}".format(SDL_GetError()))

    def __init__(self, renderer, pixfmt, vw, vh, font_filename, font_mapname, font_width, font_height, font_scale):
        self._renderer = renderer
        self._vw = int(vw)
        self._vh = int(vh)
        self._set_size()
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
        self._frameTime = 0.0
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

    @property
    def frameTime(self):
        return self._frameTime

    def active_screen(self, screen):
        self._screen = screen
        self._screen.active()
        self._dl.replace(self._screenindex, self._screen.dl)
        self._newscreen = True

    def _common_input(self, event):
        if event.type == SDL_QUIT:
            self.stop()
        elif event.type == SDL_WINDOWEVENT and \
             event.window.event == SDL_WINDOWEVENT_RESIZED:
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
            else:
                self._screen.update(time + self._extratime)
                self._dl.draw(display.SCREEN, full=False)
                self._extratime = 0.0
        self._newscreen = False

    def frame(self):
        event = SDL_Event()
        thisTime = time.monotonic()
        timetaken = thisTime - self._lastTime

        while SDL_PollEvent(event):
            self._input(event)

        self._update(timetaken)
        self._frameTime = time.monotonic() - thisTime

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


def log_cb_return(priv, string):
    global crustyerror
    crustyerror += string

def get_error():
    global crustyerror
    error = copy.copy(crustyerror)
    crustyerror = ''
    return error

def do_main(window, renderer, pixfmt):
    state = GameState(renderer, pixfmt, VIEW_WIDTH, VIEW_HEIGHT,
                      layers.FONT_FILENAME, layers.FONT_MAPNAME,
                      layers.FONT_WIDTH, layers.FONT_HEIGHT,
                      layers.FONT_SCALE)
    mode = GameInputMode.NORMAL
    mapfile = DEFAULT_MAP
    demofile = None
    try:
        if len(argv) == 2:
            mapfile = argv[1]
        elif len(argv) >= 3:
            demofile = argv[2]
            if argv[1] == 'record':
                mapfile = argv[3]
                mode = GameInputMode.RECORD
            elif argv[1] == 'recordpause':
                mapfile = argv[3]
                mode = GameInputMode.RECORDPAUSE
            elif argv[1] == 'play':
                mapfile = demofile
                if len(argv) > 3:
                    mapfile = argv[3]
                mode = GameInputMode.PLAY
            elif argv[1] == 'playstop':
                mapfile = demofile
                if len(argv) > 3:
                    mapfile = argv[3]
                mode = GameInputMode.PLAYSTOP
            else:
                raise ValueError("Invalid mode {}".format(argv[1]))
    except IndexError:
        raise ValueError("Record modes need a demo file name and a map file name.")

    mapscreen = MapScreen(state, mapfile, mode, demofile)
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
