import array
import itertools
import display

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
    def __init__(self, ll, w, h, vw, vh, ts, debug=False):
        if array.array('u').itemsize != 4:
            raise Exception("Unicode array item size must be 4 bytes wide.")
        self._debug = debug
        self._w = int(w)
        self._h = int(h)
        noscroll = 0
        if self._w == vw:
            noscroll |= display.ScrollingTilemap.NOSCROLL_X
        if self._h == vh:
            noscroll |= display.ScrollingTilemap.NOSCROLL_Y
        # fill with spaces
        if noscroll == display.ScrollingTilemap.NOSCROLL_X | display.ScrollingTilemap.NOSCROLL_Y:
            self._tm = ts.tilemap(self._w, self._h, "{}x{} Textbox Tilemap".format(self._w, self._h))
            self._tm.map(0, 0, 0, self._w, self._h, array.array('u', itertools.repeat(' ', self._w)))
            self._tm.update(0, 0, 0, 0)
            self._l = self._tm.layer("{}x{} Textbox Layer".format(self._w, self._h))
        else:
            self._tm = array.array('u', itertools.repeat(' ', self._w * self._h))
            self._stm = display.ScrollingTilemap(ts, self._tm, self._w, self._h, vw, vh, 8, 8, noscroll=noscroll)

    @property
    def layer(self):
        try:
            return self._l
        except AttributeError:
            return self._stm.layer

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
