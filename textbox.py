import array
import itertools
import display

MENU_DEFAULT_CURSOR = '>'

def wrap_text(text, w, h):
    lines = []
    spc = 0
    while spc < len(text) and len(lines) < h:
        remaining = w
        if len(text) - spc < remaining:
            remaining = len(text) - spc
        line = ""
        while spc < len(text) and remaining > 0:
            try:
                spc2 = text[spc:spc+remaining].index(' ')
            except ValueError:
                if spc + remaining + 1 < len(text) and text[spc+remaining] == ' ':
                    line = line + text[spc:spc+remaining]
                    spc += remaining + 1
                    break
                elif len(text) - spc <= remaining:
                    # if the tail end would fit within the width, just copy it
                    # in as-is and return
                    line = line + text[spc:len(text)]
                    spc = len(text)
                    break
                elif len(line) == 0:
                    # if the line wouldn't fit but it's at the beginning of a
                    # line anyway, just copy as much as possible
                    line = text[spc:spc+remaining]
                    spc += remaining
                    break
                else:
                    # otherwise, start a new line and try again
                    break
            # try not to add leading spaces to the beginning of a line
            if len(line) == 0:
                if text[spc+1] == ' ':
                    spc += 1
                    continue
            line = line + text[spc:spc+spc2 + 1]
            remaining -= spc2 + 1
            spc += spc2 + 1
        if line[len(line) - 1] == ' ':
            line = line[:-1]
        lines.append(line)

    return lines, spc

class TextBox():
    def __init__(self, w, h, vw, vh, ts, debug=False):
        if array.array('u').itemsize != 4:
            raise Exception("Unicode array item size must be 4 bytes wide.")
        self._debug = debug
        self._ts = ts
        self._w = int(w)
        self._h = int(h)
        self._vw = int(vw)
        self._vh = int(vh)
        self._noscroll = 0
        if self._w == self._vw:
            self._noscroll |= display.ScrollingTilemap.NOSCROLL_X
        if self._h == self._vh:
            self._noscroll |= display.ScrollingTilemap.NOSCROLL_Y
        self._tm = None
        if self._noscroll == display.ScrollingTilemap.NOSCROLL_X | display.ScrollingTilemap.NOSCROLL_Y:
            self._tm = ts.tilemap(self._w, self._h, "{}x{} Textbox Tilemap".format(self._w, self._h))

        self.clear()

        if isinstance(self._tm, array.array):
            self._l = self._stm.layer
        else:
            self._l = self._tm.layer("{}x{} Textbox Layer".format(self._w, self._h))

    @property
    def layer(self):
        return self._l

    def clear(self):
        # fill with spaces
        if isinstance(self._tm, array.array):
            self._tm = array.array('u', itertools.repeat(' ', self._w * self._h))
            self._stm = display.ScrollingTilemap(self._ts, self._tm, self._w, self._h, self._vw, self._vh, 8, 8, noscroll=self._noscroll)
        else:
            self._tm.map(0, 0, 0, self._w, self._h, array.array('u', itertools.repeat(' ', self._w)))
            self._tm.update(0, 0, 0, 0)

    def put_text(self, lines, x, y):
        x = int(x)
        y = int(y)
        w = self._w - x
        h = self._h - y
        for num, line in enumerate(lines):
            if y + num > h:
                if self._debug:
                    print("WARNING: Text box rows cut off {} > {}".format(len(lines), h))
                break
            if len(line) > w:
                if self._debug:
                    print("WARNING: Text box line cut off len(\"{}\") > {}".format(line, w))
                if isinstance(self._tm, array.array):
                    self._tm[(y+num)*self._w+x:(y+num)*self._w+x+w] = \
                        array.array('u', line[:w])
                    self._stm.updateregion(x, y+num, w, 1)
                else:
                    self._tm.map(x, y+num, 0, w, 1, array.array('u', line[:w]))
                    self._tm.update(x, y+num, w, 1)
            else:
                if isinstance(self._tm, array.array):
                    self._tm[(y+num)*self._w+x:(y+num)*self._w+x+len(line)] = \
                        array.array('u', line)
                    self._stm.updateregion(x, y+num, len(line), 1)
                else:
                    self._tm.map(x, y+num, 0, len(line), 1, array.array('u', line))
                    self._tm.update(x, y+num, len(line), 1)

    def put_char(self, char, x, y):
        if isinstance(self._tm, array.array):
            self._tm[y*self._w+x] = char
            self._stm.updateregion(x, y, 1, 1)
        else:
            self._tm.map(x, y, 0, 1, 1, array.array('u', char))
            self._tm.update(x, y, 1, 1)

    def scroll(self, x, y):
        if isinstance(self._tm, array.array):
            if x != 0 or y != 0:
                raise ValueError("Scroll in non-scrollable textbox to not 0, 0")
        else:
            self._stm.scroll(x, y)
            self._stm.update()

class Menu():
    _INITIAL_DL_ITEMS = 2

    def __init__(self, ts, tw, th, valuelen, priv):
        self._ts = ts
        self._tw = tw
        self._th = th
        self._valuelen = valuelen
        self._priv = priv
        self._entries = []
        self._selection = 0
        self._tb = None
        self._valtbs = []
        self._cursortm = None
        self._cursorl = None
        self._dl = None
        self._w = None
        self._h = None
        self._updated = False

    @property
    def layers(self):
        return self._tb.layer, self._cursorl

    @property
    def displaylist(self):
        return self._dl

    @property
    def dimensions(self):
        return (1 + self._w + 1 + self._valuelen) * self._tw, \
               self._h * self._th

    @property
    def selection(self):
        return self._selection

    def add_option(self, label, value=None, maxlen=None, onEnter=None, onActivate=None):
        if onEnter != None and onActivate != None:
            raise ValueError("Only one of onEnter and onActivate must be defined")
        if value is not None:
            if maxlen is None:
                maxlen = len(value)
            else:
                if maxlen < len(value):
                    raise ValueError("Maximum value length is less than initial value length.")

        self._entries.append((label, value, maxlen, onEnter, onActivate))
        self._valtbs.append(None)
        self._updated = False

    def remove(self, item):
        del self._entries[item]
        del self._valtbs[item]
        if self._dl != None:
            self._dl.remove(Menu._INITIAL_DL_ITEMS + item, None)
        self._updated = False

    def _update_cursor(self):
        self._cursorl.pos(-self._tw, self._selection * self._th)

    def update(self):
        longestlabel = 0
        for entry in self._entries:
            if len(entry[0]) > longestlabel:
                longestlabel = len(entry[0])

        w = longestlabel
        h = len(entries)
        if w != self._w or h != self._h:
            self._w = w
            self._h = h
            self._tb = TextBox(1 + self._w, self._h, 1 + self._w, self._h, self._ts)
            self._cursortm = ts.tilemap(1, 1, "{} Item Menu Cursor Tilemap".format(len(entries)))
            self._cursortm.map(0, 0, 0, 1, 1, array.array('u', MENU_DEFAULT_CURSOR))
            self._cursorl = self._cursortm.layer("{} Item Menu Cursor Layer".format(len(entries)))
            self._cursorl.relative(self._tb.layer)
            self._dl = display.DisplayList(None)
            self._dl.append(self._tb.layer)
            self._dl.append(self._cursorl)
        else:
            self._tb.clear()

        if self._selection >= len(entries):
            self._selection = len(entries) - 1

        self._update_cursor()

        try:
            while True:
                self._dl.remove(Menu._INITIAL_DL_ITEMS)
        except IndexError:
            pass

        for num, entry in enumerate(self._entries):
            self._tb.put_text((entry[0],), 1, num)
            self._valtbs[num] = None
            if entry[1] is not None:
                width = entry[2]
                if width > self._valuelen:
                    width = self._valuelen
                self._valtbs[num] = TextBox(entry[2], 1, width, 1, self._ts)
                self._valtbs[num].layer.relative(self._tb.layer)
                self._valtbs[num].layer.pos((1 + longestlabel + 1) * self._tw, num * self._th)
                self._dl.append(self._valtbs[num].layer)
            else:
                self._dl.append(None)
        self._updated = True

    def move_selection(self, movement):
        if self._updated == False:
            raise Exception("Menu must be updated to process movement.")
        newval = self._selection + movement
        if newval < 0:
            newval = 0
        if newval >= len(self._entries):
            newval = len(self._entries) - 1
        if newval == self._selection:
            return
        self._selection = newval
        self._update_cursor()

    def activate_selection(self):
        pass
