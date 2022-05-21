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

RES_WIDTH=640
RES_HEIGHT=480
VIEW_WIDTH=320
VIEW_HEIGHT=240
ERROR_TIME=10.0
FULL_RENDERS = 2

PLAYER_GFX = "gfx/face.bmp"
PLAYER_WIDTH=16
PLAYER_HEIGHT=16
PLAYER_MAXSPEED=15
PLAYER_JUMP_POWER=5
PLAYER_ACCEL=6
PLAYER_GRAVITY=3
#PLAYER_GRAVITY=0
PLAYER_BRAKING=3
PLAYER_MINSPEED=0.001
EDGE_FUDGE=0.01
EDGE_FUDGIER=EDGE_FUDGE/10

crustyerror = ''

@dataclass(frozen=True)
class TilesetDesc():
    filename : str
    width : int
    height : int

class PlayerState(Enum):
    AIR = 0,
    GROUND = 1

class NoHit(Exception):
    pass

def next_hit(x1, y1, x2, y2, tw, th):
    if x2 < x1:
        xdiff = x1 - (int(x1 / tw) * tw)
        # set to tw so when it hits and comes back to here, it'll continue
        # rather than get stuck
        if xdiff == 0:
            xdiff = tw
        if y2 < y1:
            ydiff = y1 - (int(y1 / th) * th)
            if ydiff == 0:
                ydiff = th
            if x1 - x2 < xdiff and y1 - y2 < ydiff:
                raise NoHit()
            slope = (x1 - x2) / (y1 - y2)
            if slope * ydiff > xdiff:
                return -xdiff, -((1 / slope) * xdiff)
            else:
                return -(slope * ydiff), -ydiff
        elif y2 > y1:
            ydiff = (int(y1 / th + 1) * th) - y1
            if ydiff == 0:
                ydiff = th
            if x1 - x2 < xdiff and y2 - y1 < ydiff:
                raise NoHit()
            slope = (x1 - x2) / (y2 - y1)
            if slope * ydiff > xdiff:
                return -xdiff, (1 / slope) * xdiff
            else:
                return -(slope * ydiff), ydiff
        else:
            if x1 - x2 < xdiff:
                raise NoHit()
            return -xdiff, 0
    if x2 > x1:
        xdiff = (int(x1 / tw + 1) * tw) - x1
        if xdiff == 0:
            xdiff = tw
        if y2 < y1:
            ydiff = y1 - (int(y1 / th) * th)
            if ydiff == 0:
                ydiff = th
            if x2 - x1 < xdiff and y1 - y2 < ydiff:
                raise NoHit()
            slope = (x2 - x1) / (y1 - y2)
            if slope * ydiff > xdiff:
                return xdiff, -((1 / slope) * xdiff)
            else:
                return slope * ydiff, -ydiff
        elif y2 > y1:
            ydiff = (int(y1 / th + 1) * th) - y1
            if ydiff == 0:
                ydiff = th
            if x2 - x1 < xdiff and y2 - y1 < ydiff:
                raise NoHit()
            slope = (x2 - x1) / (y2 - y1)
            if slope * ydiff > xdiff:
                return xdiff, (1 / slope) * xdiff
            else:
                return slope * ydiff, ydiff
        else:
            if x2 - x1 < xdiff:
                raise NoHit()
            return xdiff, 0
    else:
        if y2 < y1:
            ydiff = y1 - (int(y1 / th) * th)
            if ydiff == 0:
                ydiff = th
            if y1 - y2 < ydiff:
                raise NoHit()
            return 0, -ydiff
        elif y2 > y1:
            ydiff = (int(y1 / th + 1) * th) - y1
            if ydiff == 0:
                ydiff = th
            if y2 - y1 < ydiff:
                raise NoHit()
            return 0, ydiff
        else:
            raise NoHit()

def collision(x1, y1, x2, y2, tw, th):
    cx = 0
    cy = 0
    if x2 < x1:
        cx = (x1 % tw) - (x1 - x2)
        if cx > 0:
            cx = 0
    elif x2 > x1:
        cx = (x2 - x1) - (tw - (x1 % tw))
        if cx < 0:
            cx = 0
    if y2 < y1:
        cy = (y1 % th) - (y1 - y2)
        if cy > 0:
            cy = 0
    elif y2 > y1:
        cy = (y2 - y1) - (th - (y1 % th))
        if cy < 0:
            cy = 0
    return cx, cy

class MapScreen():
    def _param(self, x, y):
        try:
            return self._params[1][0][int(y) * self._params[0].mw + int(x)]
        except IndexError as e:
            raise IndexError("Out of bounds: {} {}".format(x, y))

    def _first_hit(self, x, y, dx, dy, cur):
        nx = 0
        ny = 0
        while True:
            try:
                hx, hy = next_hit(x + nx, y + ny,
                                  x + dx, y + dy,
                                  self._tw, self._th)
                nx += hx
                ny += hy
                px = int((x + nx) / self._tw)
                if dx < 0 and (x + nx) % self._tw == 0:
                    px -= 1
                py = int((y + ny) / self._th)
                if dy < 0 and (y + ny) % self._th == 0:
                    py -= 1
                try:
                    hit = self._param(px, py)
                except IndexError as e:
                    print("{} {} {} {}".format(x, y, dx, dy))
                    print("{} {} {} {}".format(nx, ny, hx, hy))
                    raise e
                if hit != cur:
                    return hit, nx, ny
            except NoHit:
                break
        return None, dx, dy 

    def _collision_left(self):
        h, x, y = self._first_hit(self._playerx,
                                  self._playery,
                                  -self._tw, 0,
                                  0)
        if h is not None and x > -EDGE_FUDGE:
            return True
        h, x, y = self._first_hit(self._playerx,
                                  self._playery + PLAYER_HEIGHT,
                                  -self._tw, 0,
                                  0)
        if h is not None and x > -EDGE_FUDGE:
            return True
        return False

    def _collision_right(self):
        h, x, y = self._first_hit(self._playerx + PLAYER_WIDTH,
                                  self._playery,
                                  self._tw, 0,
                                  0)
        if h is not None and x < EDGE_FUDGE:
            return True
        h, x, y = self._first_hit(self._playerx + PLAYER_WIDTH,
                                  self._playery + PLAYER_HEIGHT,
                                  self._tw, 0,
                                  0)
        if h is not None and x < EDGE_FUDGE:
            return True
        return False

    def _collision_up(self):
        h, x, y = self._first_hit(self._playerx,
                                  self._playery,
                                  0, -self._th,
                                  0)
        if h is not None and y > -EDGE_FUDGE:
            return True
        h, x, y = self._first_hit(self._playerx + PLAYER_WIDTH,
                                  self._playery,
                                  0, -self._th,
                                  0)
        if h is not None and y > -EDGE_FUDGE:
            return True
        return False

    def _collision_down(self):
        h, x, y = self._first_hit(self._playerx,
                                  self._playery + PLAYER_HEIGHT,
                                  0, self._th,
                                  0)
        if h is not None and y < EDGE_FUDGE:
            return True
        h, x, y = self._first_hit(self._playerx + PLAYER_WIDTH,
                                  self._playery + PLAYER_HEIGHT,
                                  0, self._th,
                                  0)
        if h is not None and y < EDGE_FUDGE:
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
                        ht, xt, yt = self._first_hit(self._playerx + PLAYER_WIDTH,
                                                     self._playery,
                                                     dx2, dy2,
                                                     0)
                        hc, xc, yc = self._first_hit(self._playerx + PLAYER_WIDTH,
                                                     self._playery + PLAYER_HEIGHT,
                                                     dx2, dy2,
                                                     0)
                        hb, xb, yb = self._first_hit(self._playerx,
                                                     self._playery + PLAYER_HEIGHT,
                                                     dx2, dy2,
                                                     0)
                        if hb is not None and xb < dx2:
                            if xb > EDGE_FUDGE:
                                dx2 = xb - EDGE_FUDGIER
                            elif self._collision_right():
                                dx2 = 0
                                dx = 0
                        if ht is not None and yt < dy2:
                            if yt > EDGE_FUDGE:
                                dy2 = yt - EDGE_FUDGIER
                            elif self._collision_down():
                                dy2 = 0
                                self._pstate = PlayerState.GROUND
                        if hc is not None:
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
                        ht, xt, yt = self._first_hit(self._playerx, self._playery,
                                                     dx2, dy2,
                                                     0)
                        hc, xc, yc = self._first_hit(self._playerx + PLAYER_WIDTH,
                                                     self._playery,
                                                     dx2, dy2,
                                                     0)
                        hb, xb, yb = self._first_hit(self._playerx + PLAYER_WIDTH,
                                                     self._playery + PLAYER_HEIGHT,
                                                     dx2, dy2,
                                                     0)
                        if hb is not None and xb < dx2:
                            if xb > EDGE_FUDGE:
                                dx2 = xb - EDGE_FUDGIER
                            elif self._collision_right():
                                dx2 = 0
                                dx = 0
                        # greater is less negative
                        if ht is not None and yt > dy2:
                            if yt < -EDGE_FUDGE:
                                dy2 = yt + EDGE_FUDGIER
                            elif self._collision_up():
                                dy2 = 0
                                dy = 0
                        if hc is not None:
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
                        ht, xt, yt = self._first_hit(self._playerx + PLAYER_WIDTH,
                                                     self._playery,
                                                     dx2, 0,
                                                     0)
                        hb, xb, yb = self._first_hit(self._playerx + PLAYER_WIDTH,
                                                     self._playery + PLAYER_HEIGHT,
                                                     dx2, 0,
                                                     0)
                        if ht is not None and xt < dx:
                            if xt > EDGE_FUDGE:
                                dx2 = xt - EDGE_FUDGIER
                            else:
                                dx2 = 0
                                dx = 0
                        if hb is not None and xb < dx:
                            if xb > EDGE_FUDGE:
                                dx2 = xb - EDGE_FUDGIER
                            else:
                                dx2 = 0
                                dx = 0
                elif dx2 < 0:
                    if dy2 > 0:
                        ht, xt, yt = self._first_hit(self._playerx, self._playery,
                                                     dx2, dy2,
                                                     0)
                        hc, xc, yc = self._first_hit(self._playerx,
                                                     self._playery + PLAYER_HEIGHT,
                                                     dx2, dy2,
                                                     0)
                        hb, xb, yb = self._first_hit(self._playerx + PLAYER_WIDTH,
                                                     self._playery + PLAYER_HEIGHT,
                                                     dx2, dy2,
                                                     0)
                        if ht is not None and xt > dx2:
                            if xt < -EDGE_FUDGE:
                                dx2 = xt + EDGE_FUDGIER
                            elif self._collision_left():
                                dx2 = 0
                                dx = 0
                        if hb is not None and yb < dy2:
                            if yb > EDGE_FUDGE:
                                dy2 = yb - EDGE_FUDGIER
                            elif self._collision_down():
                                dy2 = 0
                                self._pstate = PlayerState.GROUND
                        if hc is not None:
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
                        ht, xt, yt = self._first_hit(self._playerx + PLAYER_WIDTH,
                                                     self._playery,
                                                     dx2, dy2,
                                                     0)
                        hc, xc, yc = self._first_hit(self._playerx, self._playery,
                                                     dx2, dy2,
                                                     0)
                        hb, xb, yb = self._first_hit(self._playerx,
                                                     self._playery + PLAYER_HEIGHT,
                                                     dx2, dy2,
                                                     0)
                        if hb is not None and xb > dx2:
                            if xb < -EDGE_FUDGE:
                                dx2 = xb + EDGE_FUDGIER
                            elif self._collision_left():
                                dx2 = 0
                                dx = 0
                        if ht is not None and yt > dy2:
                            if yt < -EDGE_FUDGE:
                                dy2 = yt + EDGE_FUDGIER
                            elif self._collision_up():
                                dy2 = 0
                                dy = 0
                        if hc is not None:
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
                        ht, xt, yt = self._first_hit(self._playerx, self._playery,
                                                     dx2, 0,
                                                     0)
                        hb, xb, yb = self._first_hit(self._playerx,
                                                     self._playery + PLAYER_HEIGHT,
                                                     dx2, 0,
                                                     0)
                        if ht is not None and xt > dx2:
                            if xt < -EDGE_FUDGE:
                                dx2 = xt + EDGE_FUDGIER
                            else:
                                dx2 = 0
                                dx = 0
                        if hb is not None and xb > dx2:
                            if xb < -EDGE_FUDGE:
                                dx2 = xb + EDGE_FUDGIER
                            else:
                                dx2 = 0
                                dx = 0
                else:
                    if dy2 > 0:
                        hl, xl, yl = self._first_hit(self._playerx,
                                                     self._playery + PLAYER_HEIGHT,
                                                     0, dy2,
                                                     0)
                        hr, xr, yr = self._first_hit(self._playerx + PLAYER_WIDTH,
                                                     self._playery + PLAYER_HEIGHT,
                                                     0, dy2,
                                                     0)
                        if hl is not None and yl < dy2:
                            if yl > EDGE_FUDGE:
                                dy2 = yl - EDGE_FUDGIER
                            else:
                                dy2 = 0
                                self._pstate = PlayerState.GROUND
                        if hr is not None and yr < dy2:
                            if yr > EDGE_FUDGE:
                                dy2 = yr - EDGE_FUDGIER
                            else:
                                dy2 = 0
                                self._pstate = PlayerState.GROUND
                    elif dy2 < 0:
                        hl, xl, yl = self._first_hit(self._playerx, self._playery,
                                                     0, dy2,
                                                     0)
                        hr, xr, yr = self._first_hit(self._playerx + PLAYER_WIDTH,
                                                     self._playery,
                                                     0, dy2,
                                                     0)
                        if hl is not None and yl > dy2:
                            if yl < -EDGE_FUDGE:
                                dy2 = yl + EDGE_FUDGIER
                            else:
                                dy2 = 0
                                dy = 0
                        if hr is not None and yr > dy2:
                            if yr < -EDGE_FUDGE:
                                dy2 = yr + EDGE_FUDGIER
                            else:
                                dy2 = 0
                                dy = 0
            elif self._pstate == PlayerState.GROUND:
                hl, xl, yl = self._first_hit(self._playerx,
                                             self._playery + PLAYER_HEIGHT,
                                             0, EDGE_FUDGE,
                                             0)
                hr, xr, yr = self._first_hit(self._playerx + PLAYER_WIDTH,
                                             self._playery + PLAYER_HEIGHT,
                                             0, EDGE_FUDGE,
                                             0)
                if hl is None and hr is None:
                    self._pspeedy = 0
                    self._pstate = PlayerState.AIR
                    continue
                dy = 0
                dy2 = 0
                if dx < 0:
                    ht, xt, yt = self._first_hit(self._playerx,
                                                 self._playery,
                                                 dx2, 0,
                                                 0)
                    hb, xb, yb = self._first_hit(self._playerx,
                                                 self._playery + PLAYER_HEIGHT,
                                                 dx2, 0,
                                                 0)
                    if ht is not None and xt > dx:
                        if xt < -EDGE_FUDGE:
                            dx2 = xt + EDGE_FUDGIER
                        else:
                            dx2 = 0
                            dx = 0
                    if hb is not None and xb > dx:
                        if xb < -EDGE_FUDGE:
                            dx2 = xb + EDGE_FUDGIER
                        else:
                            dx2 = 0
                            dx = 0
                elif dx > 0:
                    ht, xt, yt = self._first_hit(self._playerx + PLAYER_WIDTH,
                                                 self._playery,
                                                 dx2, 0,
                                                 0)
                    hb, xb, yb = self._first_hit(self._playerx + PLAYER_WIDTH,
                                                 self._playery + PLAYER_HEIGHT,
                                                 dx2, 0,
                                                 0)
                    if ht is not None and xt < dx:
                        if xt > EDGE_FUDGE:
                            dx2 = xt - EDGE_FUDGIER
                        else:
                            dx2 = 0
                            dx = 0
                    if hb is not None and xb < dx:
                        if xb > EDGE_FUDGE:
                            dx2 = xb - EDGE_FUDGIER
                        else:
                            dx2 = 0
                            dx = 0

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
            self._pspeedx = 0
        if (self._pspeedy < 0 and movedy >= -EDGE_FUDGE) or \
           (self._pspeedy > 0 and movedy <= EDGE_FUDGE):
            self._pspeedy = 0

    def _update_scroll(self):
        self._view.scroll(round(self._playerx - self._centerx),
                          round(self._playery - self._centery))
        self._playerl.pos(round(self._centerx), round(self._centery))

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
                                   4 * self._state.font.ts.height(),
                                   32, 4, self._state.font)
        self._tb.internal.colormod(display.make_color(255, 255, 255, 96))
        self._dl.replace(self._tbindex, self._tb.draw)

    def __init__(self, state, name):
        self._state = state
        settings, self._descs, self._maps, self._layers, _, _ = layers.load_map(name)
        self._params = None
        # get the params tilemap out
        for num, desc in enumerate(self._descs):
            if desc.name == 'params':
                self._params = (self._descs[num], self._maps[num])
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
        if self._params is None:
            raise ValueError("No 'params' map found.")
        self._tw = self._params[0].tw
        self._th = self._params[0].th
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
        self._view = None
        self._pdirx = 0.0
        self._pdiry = 1.0
        self._pstate = PlayerState.AIR
        self._pspeedx = 0.0
        self._pspeedy = 0.0
        self._playerx = settings['player_x']
        self._playery = settings['player_y']
        self._move_player()
        self._dl = display.DisplayList(self._state.ll)
        self._viewindex = self._dl.append(None)
        self._dl.append(self._playerl)
        self._tbindex = self._dl.append(None)
        self._build_screen()

    def active(self):
        pass

    @property
    def dl(self):
        return self._dl

    def input(self, event):
        if event.type == SDL_KEYDOWN and event.key.repeat == 0:
            if event.key.keysym.sym == SDLK_LEFT:
                self._pdirx = -1
            elif event.key.keysym.sym == SDLK_RIGHT:
                self._pdirx = 1
            elif event.key.keysym.sym == SDLK_SPACE:
                self._pdiry = -1
            elif event.key.keysym.sym == SDLK_ESCAPE:
                self._state.stop()
        elif event.type == SDL_KEYUP:
            if event.key.keysym.sym == SDLK_LEFT:
                if self._pdirx < 0:
                    self._pdirx = 0
            elif event.key.keysym.sym == SDLK_RIGHT:
                if self._pdirx > 0:
                    self._pdirx = 0

    def update(self, time):
        # TODO: Macro recording/playback for testing/demos
        if self._pdirx < 0:
            if not self._collision_left():
                self._pspeedx -= time * \
                    ((PLAYER_MAXSPEED - self._pspeedx) / PLAYER_MAXSPEED) * \
                    PLAYER_ACCEL
        elif self._pdirx > 0:
            if not self._collision_right():
                self._pspeedx += time * \
                    ((PLAYER_MAXSPEED - self._pspeedx) / PLAYER_MAXSPEED) * \
                    PLAYER_ACCEL
        else:
            self._pspeedx /= PLAYER_BRAKING
        if abs(self._pspeedx) < PLAYER_MINSPEED:
            self._pspeedx = 0
        if self._pdiry < 0:
            if self._pstate == PlayerState.GROUND:
                self._pstate = PlayerState.AIR
                self._pspeedy = -PLAYER_JUMP_POWER
            self._pdiry = 0
        if self._pstate == PlayerState.AIR:
            self._pspeedy += time * \
                ((PLAYER_MAXSPEED - self._pspeedy) / PLAYER_MAXSPEED) * \
                PLAYER_GRAVITY
        if abs(self._pspeedy) < PLAYER_MINSPEED:
            self._pspeedy = 0
        self._move_player()
        self._update_scroll()

        status, _, _, _ = textbox.wrap_text("{}\n{}\n{}\n{}".format(self._playerx, self._playery, self._pspeedx, self._pspeedy), 32, 4)
        self._tb.clear(0, 0, 32, 4)
        self._tb.put_text(status)


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
        self._renders = FULL_RENDERS
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

def do_main(window, renderer, pixfmt):
    state = GameState(renderer, pixfmt, VIEW_WIDTH, VIEW_HEIGHT,
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
