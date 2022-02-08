from sdl2 import *
import crustygame
import array
import itertools
import display
import codecs

MENU_DEFAULT_CURSOR = '▶'

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

def tileset_encoder(table, obj, errors):
    out = array.array('I', itertools.repeat(0, len(obj)))
    for num, char in enumerate(obj):
        try:
            out[num] = table[char]
        except KeyError:
            pass

    return out.tobytes(), len(out)

def tileset_decoder(table, obj, errors):
    inp = array.array('I', bytes(obj))
    out = array.array('u', itertools.repeat(chr(0xfffd), len(inp)))
    for num, char in enumerate(inp):
        try:
            out[num] = table[char]
        except KeyError:
            if errors=='strict':
                raise ValueError("Tileset decode table has no conversion for tilenum {}.".format(char))

    return out.tounicode(), len(out)

def tileset_codec_search(sname, name, func):
    if sname == name:
        return func
    return None

def load_tileset_codec(f, name):
    enctable = {}
    dectable = {}

    for line in f:
        codepoint, tilenum = line.split(' ', maxsplit=1)
        try:
            tilenum, _ = tilenum.split(' ', maxsplit=1)
        except ValueError:
            pass
        endcodepoint = '0'
        try:
            codepoint, endcodepoint = codepoint.split('-', maxsplit=1)
        except ValueError:
            pass
        endcodepoint = int(endcodepoint, base=16)
        codepoint = int(codepoint, base=16)
        tilenum = int(tilenum)
        if endcodepoint == 0:
            if chr(codepoint) in enctable:
                raise ValueError("Duplicate char definition for {}.".format(hex(codepoint)))
            enctable[chr(codepoint)] = tilenum
            dectable[tilenum] = chr(codepoint)
        else:
            if endcodepoint <= codepoint:
                raise ValueError("End point before start point.")
            for num in range(endcodepoint - codepoint + 1):
                if chr(codepoint + num) in enctable:
                    raise ValueError("Duplicate char definition for {}.".format(hex(codepoint + num)))
                enctable[chr(codepoint + num)] = tilenum + num
                dectable[tilenum + num] = chr(codepoint + num)

    # EUGH!
    codecs.register(lambda s: tileset_codec_search(s, 'crusty_{}'.format(name), codecs.CodecInfo(encode=lambda o, e='strict': tileset_encoder(enctable, o, e), decode=lambda o, e='strict': tileset_decoder(dectable, o, e))))

class TextBox():
    def __init__(self, w, h, vw, vh, ts, codec, debug=False):
        if array.array('u').itemsize != 4:
            raise Exception("Unicode array item size must be 4 bytes wide.")
        self._debug = debug
        self._ts = ts
        self._codec = codec
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
        if self._noscroll == (display.ScrollingTilemap.NOSCROLL_X | display.ScrollingTilemap.NOSCROLL_Y):
            self._tm = self._ts.tilemap(self._w, self._h, "{}x{} Textbox Tilemap".format(self._w, self._h))

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
        if isinstance(self._tm, crustygame.Tilemap):
            self._tm.map(0, 0, 0, self._w, self._h, array.array('u', itertools.repeat(' ', self._w)))
            self._tm.update(0, 0, 0, 0)
        else:
            self._tm = array.array('I', itertools.repeat(ord(' '), self._w * self._h))
            self._stm = display.ScrollingTilemap(self._ts, self._tm, self._w, self._h, self._vw, self._vh, 8, 8, noscroll=self._noscroll)

    def put_text(self, lines, x, y):
        x = int(x)
        y = int(y)
        w = self._w - x
        h = self._h - y
        for num, line in enumerate(lines):
            if isinstance(line, str):
                line = array.array('I', line.encode(self._codec))
            if y + num > h:
                if self._debug:
                    print("WARNING: Text box rows cut off {} > {}".format(len(lines), h))
                break
            if len(line) > w:
                if self._debug:
                    print("WARNING: Text box line cut off len(\"{}\") > {}".format(line, w))
                if isinstance(self._tm, array.array):
                    self._tm[(y+num)*self._w+x:(y+num)*self._w+x+w] = \
                        line[:w]
                    self._stm.updateregion(x, y+num, w, 1)
                else:
                    self._tm.map(x, y+num, 0, w, 1, line[:w])
                    self._tm.update(x, y+num, w, 1)
            else:
                if isinstance(self._tm, array.array):
                    self._tm[(y+num)*self._w+x:(y+num)*self._w+x+len(line)] = \
                        line
                    self._stm.updateregion(x, y+num, len(line), 1)
                else:
                    self._tm.map(x, y+num, 0, len(line), 1, line)
                    self._tm.update(x, y+num, len(line), 1)

    def put_char(self, char, x, y):
        if isinstance(char, str):
            char = char.encode(self._codec)
        if isinstance(self._tm, array.array):
            self._tm[y*self._w+x] = char
            self._stm.updateregion(x, y, 1, 1)
        else:
            self._tm.map(x, y, 0, 1, 1, char)
            self._tm.update(x, y, 1, 1)

    def scroll(self, x, y):
        if isinstance(self._tm, crustygame.Tilemap):
            if x != 0 or y != 0:
                raise ValueError("Scroll in non-scrollable textbox to not 0, 0")
        else:
            self._stm.scroll(x, y)
            self._stm.update()

class Menu():
    _INITIAL_DL_ITEMS = 2

    def __init__(self, ll, ts, codec, tw, th, valuelen, priv):
        self._ll = ll
        self._ts = ts
        self._codec = codec
        self._tw = int(tw)
        self._th = int(th)
        self._valuelen = int(valuelen)
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
        self._longestlabel = 0
        self._curvalue = None
        self._curpos = 0

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

    def add_item(self, label, value=None, maxlen=None, onEnter=None, onActivate=None):
        if self._curvalue is not None:
            raise Exception("Editing the menu while text editing is unsupported.")
        if onEnter != None and onActivate != None:
            raise ValueError("Only one of onEnter and onActivate must be defined")
        if value is not None:
            value = array.array('I', value.encode(self._codec))
            if maxlen is None:
                maxlen = len(value)
            else:
                if maxlen < len(value):
                    raise ValueError("Maximum value length is less than initial value length.")

        label = array.array('I', label.encode(self._codec))
        self._entries.append([label, value, maxlen, onEnter, onActivate])
        self._valtbs.append(None)
        self._updated = False

    def remove(self, item):
        if self._curvalue is not None:
            raise Exception("Editing the menu while text editing is unsupported.")
        del self._entries[item]
        del self._valtbs[item]
        if self._dl != None:
            self._dl.remove(Menu._INITIAL_DL_ITEMS + item, None)
        self._updated = False

    def _update_cursor(self):
        if self._curvalue is not None:
            self._cursorl.rotation(-90)
            pos = self._curpos
            halflen = self._valuelen // 2
            if self._curpos > halflen:
                if self._curpos < len(self._curvalue) - halflen:
                    self._valtbs[self._selection].scroll((self._curpos - halflen) * self._tw, 0)
                    pos = halflen
                else:
                    self._valtbs[self._selection].scroll((len(self._curvalue) - self._valuelen) * self._tw, 0)
                    pos = self._curpos - (len(self._curvalue) - self._valuelen)
            else:
                self._valtbs[self._selection].scroll(0, 0)
            self._cursorl.pos((1 + self._longestlabel + 1 + pos) * self._tw,
                              (self._selection + 2) * self._th)
        else:
            self._cursorl.rotation(0)
            self._cursorl.pos(0, self._selection * self._th)

    def update(self):
        if self._curvalue is not None:
            raise Exception("Editing the menu while text editing is unsupported.")
        self._longestlabel = 0
        for entry in self._entries:
            if len(entry[0]) > self._longestlabel:
                self._longestlabel = len(entry[0])

        w = self._longestlabel
        h = len(self._entries)
        if w != self._w or h != self._h:
            self._w = w
            self._h = h
            self._tb = TextBox(1 + self._w, self._h, 1 + self._w, self._h, self._ts, self._codec)
            self._cursortm = self._ts.tilemap(1, 1, "{} Item Menu Cursor Tilemap".format(len(self._entries)))
            self._cursortm.map(0, 0, 0, 1, 1, array.array('I', MENU_DEFAULT_CURSOR.encode(self._codec)))
            self._cursortm.update(0, 0, 0, 0)
            self._cursorl = self._cursortm.layer("{} Item Menu Cursor Layer".format(len(self._entries)))
            self._cursorl.relative(self._tb.layer)
            self._dl = display.DisplayList(self._ll, None)
            self._dl.append(self._tb.layer)
            self._dl.append(self._cursorl)
        else:
            self._tb.clear()

        if self._selection >= len(self._entries):
            self._selection = len(self._entries) - 1

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
                self._valtbs[num] = TextBox(entry[2], 1, width, 1, self._ts, self._codec)
                self._valtbs[num].put_text((entry[1],), 0, 0)
                self._valtbs[num].layer.relative(self._tb.layer)
                self._valtbs[num].layer.pos((1 + self._longestlabel + 1) * self._tw, num * self._th)
                self._dl.append(self._valtbs[num].layer)
            else:
                self._dl.append(None)
        self._updated = True

    def move_selection(self, movement):
        if self._curvalue is not None:
            raise Exception("Moving the selection while text editing is unsupported.")
        if not self._updated:
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

    def up(self):
        if self._curvalue is None:
            self.move_selection(-1)

    def down(self):
        if self._curvalue is None:
            self.move_selection(1)

    def left(self):
        if self._curvalue is not None:
            if self._curpos > 0:
                self._curpos -= 1
                self._update_cursor()

    def right(self):
        if self._curvalue is not None:
            if self._curpos < len(self._curvalue):
                self._curpos += 1
                self._update_cursor()

    def _update_value(self):
        self._valtbs[self._selection].put_text((self._curvalue[self._curpos:],), self._curpos, 0)

    def backspace(self):
        if self._curvalue is not None:
            if self._curpos > 0:
                self._curvalue[self._curpos-1:-1] = self._curvalue[self._curpos:]
                self._curvalue[-1] = ord(' ')
                self._curpos -= 1
                self._update_value()
                self._update_cursor()

    def delete(self):
        if self._curvalue is not None:
            if self._curpos + 1 < len(self._curvalue):
                self._curvalue[self._curpos:-1] = self._curvalue[self._curpos+1:]
                self._curvalue[-1] = ord(' ')
                self._update_value()

    def activate_selection(self):
        if not self._updated:
            raise Exception("Menu must be updated to process movement.")

        if self._curvalue is not None:
            val = self._entries[self._selection][3](self._priv, self._selection, self._curvalue.tobytes().decode(self._codec))
            self._curvalue = array.array('I', val.encode(self._codec))
            self._curpos = 0
            self._update_value()
            self._update_cursor()
            self._entries[self._selection][1] = self._curvalue
            self._curvalue = None
            self._update_cursor()
        elif self._entries[self._selection][4] is not None:
            val = self._entries[self._selection][4](self._selection, self._priv)
        elif self._entries[self._selection][3] is not None:
            self._curvalue = self._entries[self._selection][1]
            self._curvalue.extend(array.array('I', itertools.repeat(ord(' '), self._entries[self._selection][2] - len(self._entries[self._selection][1]))))
            self._curpos = 0
            self._update_cursor()

    def text_event(self, event):
        if not self._updated:
            raise Exception("Menu must be updated to process movement.")
        if self._curvalue is not None:
            if self._curpos < len(self._curvalue):
                char = event.text.text.decode('utf-8')
                self._curvalue[self._curpos+1:] = self._curvalue[self._curpos:-1]
                self._curvalue[self._curpos:self._curpos+1] = array.array('I', char.encode(self._codec))
                self._update_value()
                self._curpos += 1
                self._update_cursor()
