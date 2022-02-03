import array

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
            print(line)
        if line[len(line) - 1] == ' ':
            line = line[:-1]
        lines.append(line)

    return lines

class TextBox():
    def __init__(self, w, h, vw, vh, ts):
        self._w = int(w)
        self._h = int(h)
        # fill with spaces
        self._tm = array.array('L', itertools.repeat(32, self._w * self._h))
        self._stm = display.ScrollingTilemap(ts, self._tm, self._w, self._h, vw, vh, 8, 8)

    @property
    def layer(self):
        return self._stm.layer

    def put_text(self, text, x, y, w=0, h=0):
        if w == 0:
            w = self._w - x
        if h == 0:
            h = self._h - y


