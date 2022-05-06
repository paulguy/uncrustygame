import math
import random

def color_from_rad(rad, cmin, cmax):
    if rad >= 0 and rad < (math.tau / 6):
        rad = (rad * (1 / (math.tau / 6)) * (cmax - cmin)) + cmin
        return cmax, rad, cmin
    elif rad >= (math.tau / 6) and rad < (math.tau / 6 * 2):
        rad = cmax - ((rad - (math.tau / 6)) * (1 / (math.tau / 6)) * (cmax - cmin))
        return rad, cmax, cmin
    elif rad >= (math.tau / 6 * 2) and rad < (math.tau / 6 * 3):
        rad = ((rad - (math.tau / 6 * 2)) * (1 / (math.tau / 6)) * (cmax - cmin)) + cmin
        return cmin, cmax, rad
    elif rad >= (math.tau / 6 * 3) and rad < (math.tau / 6 * 4):
        rad = cmax - ((rad - (math.tau / 6 * 3)) * (1 / (math.tau / 6)) * (cmax - cmin))
        return cmin, rad, cmax
    elif rad >= (math.tau / 6 * 4) and rad < (math.tau / 6 * 5):
        rad = ((rad - (math.tau / 6 * 4)) * (1 / (math.tau / 6)) * (cmax - cmin)) + cmin
        return rad, cmin, cmax

    rad = cmax - ((rad - (math.tau / 6 * 5)) * (1 / (math.tau / 6)) * (cmax - cmin))
    return cmax, cmin, rad

class BouncingPoint():
    def __init__(self, minx, miny, maxx, maxy, maxspeed, minspeed=0, x=0, y=0):
        self._minx = minx
        self._maxx = maxx
        self._miny = miny
        self._maxy = maxy
        self._minspeed = minspeed
        self._maxspeed = maxspeed
        self._x = x
        self._y = y
        self._xspeed = self._val()
        self._yspeed = self._val()

    def _val(self):
        return random.uniform(self._minspeed, self._maxspeed)

    @property
    def point(self):
        return self._x, self._y

    def update(self, timetaken):
        bounced = False

        self._x += self._xspeed * timetaken
        if self._x > self._maxx:
            self._xspeed = -self._val()
            if self._yspeed > 0.0:
                self._yspeed = self._val()
            else:
                self._yspeed = -self._val()
            self._x = self._maxx
            bounced = True
        elif self._x < self._minx:
            self._xspeed = self._val()
            if self._yspeed > 0.0:
                self._yspeed = self._val()
            else:
                self._yspeed = -self._val()
            self._x = self._minx
            bounced = True

        self._y += self._yspeed * timetaken
        if self._y > self._maxy:
            self._yspeed = -self._val()
            if self._xspeed > 0.0:
                self._xspeed = self._val()
            else:
                self._xspeed = -self._val()
            self._y = self._maxy
            bounced = True
        elif self._y < self._miny:
            self._yspeed = self._val()
            if self._xspeed > 0.0:
                self._xspeed = self._val()
            else:
                self._xspeed = -self._val()
            self._y = self._miny
            bounced = True

        while self._xspeed == 0.0 and self._yspeed == 0.0:
            self._xspeed = -self._val()
            self._yspeed = -self._val()

        return bounced
