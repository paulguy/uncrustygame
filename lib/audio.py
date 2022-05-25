import array
import crustygame as cg
from dataclasses import dataclass
import lib.sequencer as seq
from py_expression_eval import Parser

CHANNEL_TYPE_SILENCE = "silence"
CHANNEL_TYPE_PLAYER = "player"
CHANNEL_TYPE_FILTER = "filter"

def _create_float_array(iterable):
    aType = c_float * len(iterable)
    a = aType()

    for item in enumerate(iterable):
        a[item[0]] = item[1]

    return(a)

_parser = Parser()

_NOTES = "c d ef g a b"

def get_speed(speed, tunes):
    tune = 0.0
    try:
        # frequency
        tune = float(speed)
    except ValueError:
        # note
        char = 0

        note = _NOTES.index(speed[char].lower())
        octave = 0

        if len(speed) > char + 1:
            if speed[char+1] == '#':
                char += 1
                note += 1
                if note == 12:
                    octave = 1
                    note = 0
            elif speed[char+1] == 'b':
                char += 1
                note -= 1
                if note == -1:
                    octave = -1
                    note = 11

        if len(speed) > char + 1:
            if speed[char+1].isdigit() or \
               speed[char+1] == '-' or \
               speed[char+1] == '+':
                curchar = char
                numlen = 0
                if speed[curchar+1].isdigit():
                    numlen += 1
                curchar += 1
                while len(speed) > curchar + 1:
                    if speed[curchar+1].isdigit():
                        numlen += 1;
                    else:
                        break
                    curchar += 1
                if numlen > 0:
                    octave = int(speed[char+1:curchar+1]) - 4 + octave
                    char = curchar
                else:
                    raise ValueError("Sign with no number.")

        tune = tunes[note] * (2 ** octave)

        if len(speed) > char + 1:
            if speed[char+1] == '*':
                char += 1
                if len(speed) > char + 1:
                    try:
                        detune = float(speed[char+1:])
                        tune = tune * (2 ** (detune / 12))
                    except ValueError:
                        pass
                else:
                    raise ValueError("'*' with no detune.")
            else:
                raise ValueError("Junk after speed/note value.")

    return tune

def eval_exprs(line):
    parens = 0
    pos = 0
    newline = ""
    while pos < len(line):
        if parens > 0:
            lidx = None
            ridx = None
            try:
                lidx = line[pos:].index('(')
            except ValueError:
                pass
            try:
                ridx = line[pos:].index(')')
            except ValueError:
                pass
            if lidx is None and ridx is None:
                break
            if lidx is not None:
                if ridx is None or lidx < ridx:
                    pos += lidx+1
                    parens += 1
            if ridx is not None:
                if lidx is None or ridx < lidx:
                    pos += ridx+1
                    parens -= 1
                    if parens == 0:
                        expr = line[sindex:pos]
                        result = str(float(_parser.parse(expr).evaluate({})))
                        newline += result
        else:
            try:
                sindex = line[pos:].index('(')
                sindex += pos
                newline += line[pos:sindex]
                pos = sindex+1
                parens = 1
            except ValueError as e:
                newline += line[pos:]
                break
    if parens > 0:
        raise ValueError("Unclosed parenthesis: {}".format(line[sindex:]))
    return newline

class _MacroReaderIterator():
    def __init__(self, reader):
        self._reader = reader

    def __next__(self):
        try:
            return self._reader.readline()
        except IOError:
            raise StopIteration()

class MacroReader():
    """
    Gross probably slow crappy class for reading a file line by line with macro
    replacements, but it won't be dealing with large files.
    """

    def __init__(self, file, startLine=0, trace=False, macros=None, macrofile=False):
        """
        Accepts a file or somethign with a readline() function as well as a
        list of macros which is a tuple of a name, list of argument names, and
        the replacement string.
        Replaces all instances of name arg0 arg1 arg2 ... with the replacement
        string and arg names in the replacement replaced with args
        """
        self._trace = trace
        self._file = file
        self._macros = dict()
        self._line = None
        self._lines = startLine
        self._tunes = None
        self._macrofile = macrofile

        if macros != None:
            self.add_macros(macros)

    def set_tunes(self, tunes):
        self._tunes = tunes

    @property
    def curline(self):
        """
        Return current line being processed.
        """
        return self._lines

    @property
    def name(self):
        """
        return filename
        """
        return self._file.name

    @property
    def macros(self):
        """
        Return the dict of this reader's macros.
        """
        return self._macros

    def add_macros(self, macros):
        """
        Add a single macro or a list of macros.

        A macro is a tuple or list of name, a tuple or list of argument names, and a
        string containing the replacement string that would contain the argument
        strings.
        """
        for macro in macros.keys():
            if macro in self._macros:
                print("WARNING: Macro {} would overwrite existing macro.".format(macro))
            # try to find each macro arg in the macro body
            for arg in macros[macro][0]:
                try:
                    macros[macro][1].index(arg)
                except ValueError:
                    raise ValueError("Macro {} has arg {} not found in body.".format(macro, arg))
            self._macros[macro] = macros[macro]

    def _replace_note_vals(self, line):
        if self._tunes is None:
            return line
        pos = 0
        newline = ""
        while pos < len(line):
            idx = None
            try:
                idx = line[pos:].index('$')
            except ValueError:
                pass
            if idx is not None:
                newline += line[pos:pos+idx]
                sidx = None
                try:
                    sidx = line[pos+idx:].index(' ')
                    sidx += pos+idx
                except ValueError:
                    pass
                speed = get_speed(line[pos+idx+1:sidx], self._tunes)
                newline += str(float(speed))
                if sidx is None:
                    break
                pos = sidx
            else:
                newline += line[pos:]
                break
        return newline

    def readline(self):
        """
        Read a line with macros replaced.
        """
        if self._line == None:
            line = ""
            while True:
                newline = self._file.readline()
                if newline == "":
                    raise IOError("End of file reached reading file.")
                self._lines += 1
                if self._trace:
                    print("{}: {}".format(self._lines, newline), end='')
                newline = newline.split(';', maxsplit=1)[0]
                newline = newline.strip()
                line += newline
                if len(line) > 0 and line[-1] == '\\':
                    line = line[:-1]
                    continue
                if len(line) > 0:
                    break

            while True:
                changed = False
                for macro in self._macros:
                    newLine = ""
                    while True:
                        index = 0
                        try:
                            # search for instance of macro name
                            index = line[index:].index(macro)
                        except ValueError:
                            # no macro found, just append the rest
                            newLine += line
                            break
                        changed = True
                        # append everything up to the macro name to be replaced
                        newLine += line[:index]
                        # results in args, remainder
                        args = line[index+len(macro):].split(maxsplit=len(self._macros[macro][0]))
                        # make a copy of the replacement string
                        replacement = str(self._macros[macro][1])
                        # replace all instances of argument names with the provided
                        # values
                        for num, macroarg in enumerate(self._macros[macro][0]):
                            try:
                                replacement = replacement.replace(macroarg, args[num])
                            except IndexError:
                                raise ValueError("Invalid arguments used for macro {} ({} != {})".format(macro, len(self._macros[macro][0]), len(args)))
                        # append the replacement string
                        newLine += replacement + ' '
                        # if there's nothing left, break
                        if len(args) <= len(self._macros[macro][0]):
                            break
                        # continue with the remainder
                        line = args[-1]
                    line = newLine
                if not changed:
                    break
            self._line = line.splitlines()
        line = self._line[0]
        if len(self._line) == 1:
            self._line = None
        else:
            self._line = self._line[1:]
        line = self._replace_note_vals(line)
        # don't evaluate expressions in macro definitions
        if not self._macrofile and \
           not line.lower().startswith("macro "):
            line = eval_exprs(line)
        if self._trace:
            print("-> {}".format(line))
        return line

    def __iter__(self):
        return _MacroReaderIterator(self)

def read_macro(line):
    """
    Read one macro args ...=contents and return name, args and macro contents
    """
    macroline = line.split('=', maxsplit=1)
    lhs = macroline[0].split()
    macroname = lhs[0]
    macroargs = lhs[1:]

    return macroname, macroargs, macroline[1]

def read_macros(infile):
    """
    read a list of macros from a file, macros are formatted:
    name arg0name arg1name ...=replacement
    macro names are found in the file and replaced with replacement
    and instances of argument names are replaced with the arguments
    provided when the macro is used like:
    name arg0 arg1 ...
    Returna dict of keys read.
    """
    macros = dict()
    for line in infile:
        name, args, line = read_macro(line.strip())
        macros[name] = (args, line)

    return macros

_BUILTIN_MACROS = {
    "SYNTH_OUTPUT_REPLACE": ((), str(cg.SYNTH_OUTPUT_REPLACE)),
    "SYNTH_OUTPUT_ADD": ((), str(cg.SYNTH_OUTPUT_ADD)),
    "SYNTH_AUTO_CONSTANT": ((), str(cg.SYNTH_AUTO_CONSTANT)),
    "SYNTH_AUTO_SOURCE": ((), str(cg.SYNTH_AUTO_SOURCE)),
    "SYNTH_MODE_ONCE": ((), str(cg.SYNTH_MODE_ONCE)),
    "SYNTH_MODE_LOOP": ((), str(cg.SYNTH_MODE_LOOP)),
    "SYNTH_MODE_PHASE_SOURCE": ((), str(cg.SYNTH_MODE_PHASE_SOURCE))
}

@dataclass
class BufferDesc():
    desc : object
    rate : int = 0
    buffer : object = None
    samplesms : float = 0.0

@dataclass
class SilenceState():
    outBuffer : cg.Buffer
    reqTime : int = 0
    outPos : int = 0
    reqTimeEvent : object = None
    outBufEvent : object = None

@dataclass
class PlayerState():
    player : cg.Player
    reqTime : int = 0
    reqTimeEvent : object = None
    outBufEvent : object = None
    inBufEvent : object = None
    volBufEvent : object = None
    speedBufEvent : object = None
    phaseBufEvent : object = None
    startBufEvent : object = None
    lengthBufEvent : object = None
    inBuf : cg.Buffer = None
    outBuf : cg.Buffer = None

@dataclass
class FilterState():
    flt : cg.Filter
    reqTime : int = 0
    reqTimeEvent : object = None
    outBufEvent : object = None
    inBufEvent : object = None
    volBufEvent : object = None
    sliceBufEvent : object = None
    inBuf : cg.Buffer = None
    outBuf : cg.Buffer = None

class AudioSequencer():
    def __init__(self, infile, buffer=None, extMacros=None, trace=False):
        """
        Create an audio sequence from a file.

        infile     a file object to read the sequence from
        buffer     an iterator of external Buffer objects.
        extMacros  an iterator of some sort containing tuples of name, a tuple or argument names, and the macro 
        trace      output a lot of status data
        """
        self._trace = trace
        infile = MacroReader(infile, trace=trace)
        if infile.readline().strip() != "CrustyTracker":
            raise Exception("File isn't a CrustyTracker sequence.")
        line = infile.readline().split()
        self._version = int(line[0])
        if self._version != 2:
            raise Exception("Unsupported version: {}".format(self._version))
        self._seqChannels = int(line[1])

        infile.add_macros(_BUILTIN_MACROS)

        if extMacros:
            infile.add_macros(extMacros)

        self._tag = dict()
        self._buffer = list()
        self._channel = list()
        extBuf = 0
        try:
            while True:
                line = infile.readline()
                if line.lower() == 'sequence':
                    break
                linetype, line = line.split(maxsplit=1)
                linetype = linetype.lower()
                if linetype == 'macro':
                    macroname, macroargs, macroline = read_macro(line)
                    infile.add_macros({macroname: (macroargs, macroline)})
                elif linetype == 'tag':
                    tagline = line.split('=', maxsplit=1)
                    self._tag[tagline[0]] = tagline[1]
                    if tagline[0] == 'tuning':
                        self._tune()
                        infile.set_tunes(self._tunes)
                elif linetype == 'buffer':
                    if line.lower() == 'external':
                        if not isinstance(buffer[extBuf], cg.Buffer):
                            raise Exception("Buffers must be external Buffers.")
                        # import an external buffer
                        self._buffer.append(BufferDesc(buffer[extBuf]))
                        extBuf += 1
                    else:
                        bufferline = line.split(maxsplit=1)
                        item = None
                        # single value means the buffer will be provided
                        try:
                            # add the time in milliseconds of an empty buffer
                            item = int(bufferline[0])
                        except ValueError:
                            # add the string to use as a filename later
                            item = bufferline[0].strip()
                        self._buffer.append(BufferDesc(item))
                elif linetype == 'channel':
                    line = line.strip().lower()
                    if line == CHANNEL_TYPE_SILENCE:
                        self._channel.append(CHANNEL_TYPE_SILENCE)
                    elif line == CHANNEL_TYPE_PLAYER:
                        self._channel.append(CHANNEL_TYPE_PLAYER)
                    elif line == CHANNEL_TYPE_FILTER:
                        self._channel.append(CHANNEL_TYPE_FILTER)
                    else:
                        raise Exception("Invalid channel type: {}".format(channel))
                elif linetype == 'include':
                    with open(line, 'r') as macrofile:
                        macrofile = MacroReader(macrofile, trace=trace, macros=infile.macros, macrofile=True)
                        try:
                            macros = read_macros(macrofile)
                        except Exception as e:
                            print("Error reading macros from {} on line {}.".format(macrofile.name, macrofile.curline))
                            raise e
                        infile.add_macros(macros)
                else:
                    raise Exception("Invalid line type {}".format(linetype))
            self._tune()
            infile.set_tunes(self._tunes)
            if self._trace:
                print(infile.macros)
                print(self._tag)
                print(self._buffer)
                print(self._channel)
            self._maxreq = 2 ** 31
            try:
                self._maxreq = int(self._tag['max-request'])
            except KeyError:
                pass
            seqDesc = seq.SequenceDescription()
            silenceDesc = seqDesc.add_row_description()
            # 0  output buffer     0x10
            seqDesc.add_field(silenceDesc, seq.FIELD_TYPE_INT)
            # 1  start pos         0x08
            seqDesc.add_field(silenceDesc, seq.FIELD_TYPE_FLOAT)
            # 2  run length        0x04
            seqDesc.add_field(silenceDesc, seq.FIELD_TYPE_FLOAT)
            # 3  stopped requested 0x02
            seqDesc.add_field(silenceDesc, seq.FIELD_TYPE_ROW, rowDesc=silenceDesc)
            # 4  stopped outbuffer 0x01
            seqDesc.add_field(silenceDesc, seq.FIELD_TYPE_ROW, rowDesc=silenceDesc)
            playerDesc = seqDesc.add_row_description()
            # 0   input buffer                     0x80000000
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
            # 1   input buffer pos                 0x40000000
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_FLOAT)
            # 2   output buffer                    0x20000000
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
            # 3   output buffer pos                0x10000000
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_FLOAT)
            # 4   output mode                      0x08000000
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
            # 5   volume                           0x04000000
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_FLOAT)
            # 6   volume source                    0x02000000
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
            # 7   volume mode                      0x01000000
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
            # 8   speed (frequency, /speed, note)  0x00800000
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_STR)
            # 9   speed source                     0x00400000
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
            # 10  speed mode                       0x00200000
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
            # 11  phase source                     0x00100000
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
            # 12  loop length                      0x00080000
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
            # 13  loop start                       0x00040000
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
            # 14  player mode                      0x00020000
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
            # 15  start source                     0x00010000
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
            # 16  start values                     0x00008000
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
            # 17  start granularity                0x00004000
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
            # 18  start mode                       0x00002000
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
            # 19  length source                    0x00001000
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
            # 20  length values                    0x00000800
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
            # 21  length granularity               0x00000400
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
            # 22  length mode                      0x00000200
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
            # 23  run length                       0x00000100
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_FLOAT)
            # 24  stopped requested                0x00000080 (reason 0)
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_ROW, rowDesc=playerDesc)
            # 25  stopped outbuffer                0x00000040 (reason 01)
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_ROW, rowDesc=playerDesc)
            # 26  stopped inbuffer                 0x00000020 (reason 02)
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_ROW, rowDesc=playerDesc)
            # 27  stopped volbuffer                0x00000010 (reason 04)
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_ROW, rowDesc=playerDesc)
            # 28  stopped speedbuffer              0x00000008 (reason 08)
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_ROW, rowDesc=playerDesc)
            # 29  stopped phasebuffer              0x00000004 (reason 10)
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_ROW, rowDesc=playerDesc)
            # 30  stopped startbuffer              0x00000002 (reason 40)
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_ROW, rowDesc=playerDesc)
            # 31  stopped lengthbuffer             0x00000001 (reason 80)
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_ROW, rowDesc=playerDesc)
            filterDesc = seqDesc.add_row_description()
            # 0   input buffer         0x100000
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
            # 1   input buffer pos     0x080000
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_FLOAT)
            # 2   output buffer        0x040000
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
            # 3   output buffer pos    0x020000
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_FLOAT)
            # 4   filter buffer        0x010000
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
            # 5   filter buffer start  0x008000
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
            # 6   filter buffer slices 0x004000
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
            # 7   slice                0x002000
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
            # 8   slice source         0x001000
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
            # 9   filter mode          0x000800
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
            # 10  output mode          0x000400
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
            # 11  volume               0x000200
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_FLOAT)
            # 12  volume source        0x000100
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
            # 13  volume mode          0x000080
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
            # 14  run length           0x000040
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_FLOAT)
            # 15  stopped requested    0x000020 (reason 0)
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_ROW, rowDesc=filterDesc)
            # 16  stopped outbuffer    0x000010 (reason 01)
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_ROW, rowDesc=filterDesc)
            # 17  stopped inbuffer     0x000008 (reason 02)
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_ROW, rowDesc=filterDesc)
            # 18  stopped volbuffer    0x000004 (reason 04)
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_ROW, rowDesc=filterDesc)
            # 19  stopped slicebuffer  0x000002 (reason 20)
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_ROW, rowDesc=filterDesc)
            # 20  initial size         0x000001 (only used for initialization)
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
            for channel in self._channel:
                if channel == CHANNEL_TYPE_SILENCE:
                    seqDesc.add_column(silenceDesc)
                elif channel == CHANNEL_TYPE_PLAYER:
                    seqDesc.add_column(playerDesc)
                elif channel == CHANNEL_TYPE_FILTER:
                    seqDesc.add_column(filterDesc)
            self._seq = seq.Sequencer(seqDesc, infile, trace=trace)
        except Exception as e:
            print("Exception on line {} in {}.".format(infile.curline, infile.name))
            raise e
        self._loaded = False
        self._ended = False

    @property
    def ended(self):
        """
        Determine whether sequence has reached ended state
        """
        return self._ended

    def _rearrange_tunings(orig):
        for i in range(3, 12):
            orig[i] /= 2.0
        tunes = (orig[3], orig[4], orig[5], orig[6], orig[7], orig[8], orig[9], orig[10], orig[11], orig[0], orig[1], orig[2])
        return tunes

    def _tune(self):
        tuning = None
        try:
            tuning = self._tag['tuning'].split()
        except KeyError:
            tunes = [2 ** (x / 12) for x in range(12)]
            self._tunes = AudioSequencer._rearrange_tunings(tunes)
            return

        if len(tuning) == 1:
            tuning = float(tuning[0])
            tunes = [tuning * (2 ** (x / 12)) for x in range(12)]
            self._tunes = AudioSequencer._rearrange_tunings(tunes)
        elif len(tuning) == 12:
            self._tunes = [float(x) for x in tuning]
        else:
            raise ValueError("'tuning' tag must be some detune or all 12 note detunings.")

    def _update_silence(self, silence, status):
        if status[0] != None:
            buf = status[0]
            if buf >= self._seqChannels:
                buf -= self._seqChannels
                buf += self._channels
            else:
                raise ValueError("Silence can't be applied to output channels")
            try:
                b = self._buffer[buf]
            except IndexError:
                raise IndexError("Invalid buffer number {}.".format(buf))
            silence.outBuf = b
        if status[1] != None:
            silence.outPos = int(status[1] * silence.outBuf.samplesms)
        if status[2] != None:
            silence.reqTime = int(status[2] * silence.outBuf.samplesms)
        if status[3] != None:
            if status[3] < 0:
                silence.reqTimeEvent = None
            else:
                silence.reqTimeEvent = self._seq.get_row(status[3])
        if status[4] != None:
            if status[4] < 0:
                silence.outBufEvent = None
            else:
                silence.outBufEvent = self._seq.get_row(status[4])

    def _update_player(self, player, status):
        p = player.player
        if status[0] != None:
            buf = status[0]
            if buf >= self._seqChannels:
                buf -= self._seqChannels
                buf += self._channels
            try:
                b = self._buffer[buf]
            except IndexError:
                raise IndexError("Invalid buffer number {}.".format(buf))
            player.inBuf = b
            p.input(b.buffer)
        if status[1] != None:
            pos = status[1]
            # make -1.0 be the real last sample
            # input buffer position is natively float, so don't convert to int
            if pos < 0.0:
                pos = (pos * player.inBuf.samplesms) + (player.inBuf.samplesms - 1.0)
            else:
                pos = pos * player.inBuf.samplesms
            p.input_pos(pos)
        if status[2] != None:
            buf = status[2]
            if buf >= self._seqChannels:
                buf -= self._seqChannels
                buf += self._channels
            try:
                b = self._buffer[buf]
            except IndexError:
                raise IndexError("Invalid buffer number {}.".format(buf))
            player.outBuf = b
            p.output(b.buffer)
        if status[3] != None:
            pos = status[3]
            if pos < 0:
                pos = int((pos * player.outBuf.samplesms) + (player.outBuf.samplesms - 1))
            else:
                pos = int(pos * player.outBuf.samplesms)
            p.output_pos(pos)
        if status[4] != None:
            p.output_mode(status[4])
        if status[5] != None:
            p.volume(status[5])
        if status[6] != None:
            buf = status[6]
            if buf >= self._seqChannels:
                buf -= self._seqChannels
                buf += self._channels
            try:
                b = self._buffer[buf]
            except IndexError:
                raise IndexError("Invalid buffer number {}.".format(buf))
            p.volume_source(b.buffer)
        if status[7] != None:
            p.volume_mode(status[7])
        if status[8] != None:
            p.speed((player.outBuf.rate / player.inBuf.rate) * get_speed(status[8], self._tunes))
        if status[9] != None:
            buf = status[9]
            if buf >= self._seqChannels:
                buf -= self._seqChannels
                buf += self._channels
            try:
                b = self._buffer[buf]
            except IndexError:
                raise IndexError("Invalid buffer number {}.".format(buf))
            p.speed_source(b.buffer)
        if status[10] != None:
            p.speed_mode(status[10])
        if status[11] != None:
            buf = status[11]
            if buf >= self._seqChannels:
                buf -= self._seqChannels
                buf += self._channels
            try:
                b = self._buffer[buf]
            except IndexError:
                raise IndexError("Invalid buffer number {}.".format(buf))
            p.phase_source(b.buffer)
        if status[12] != None:
            # loop pointers should be relative to the sample to be most useful
            p.loop_length(status[12])
        if status[13] != None:
            p.loop_start(status[13])
        if status[14] != None:
            p.mode(status[14])
        if status[15] != None:
            buf = status[15]
            if buf >= self._seqChannels:
                buf -= self._seqChannels
                buf += self._channels
            try:
                b = self._buffer[buf]
            except IndexError:
                raise IndexError("Invalid buffer number {}.".format(buf))
            p.start_source(b.buffer)
        if status[16] != None:
            p.start_values(status[16])
        if status[17] != None:
            p.start_granularity(status[17])
        if status[18] != None:
            p.start_mode(status[18])
        if status[19] != None:
            buf = status[19]
            if buf >= self._seqChannels:
                buf -= self._seqChannels
                buf += self._channels
            try:
                b = self._buffer[buf]
            except IndexError:
                raise IndexError("Invalid buffer number {}.".format(buf))
            p.length_source(b.buffer)
        if status[20] != None:
            p.length_values(status[20])
        if status[21] != None:
            p.length_granularity(status[21])
        if status[22] != None:
            p.length_mode(status[22])
        if status[23] != None:
            player.reqTime = int(status[23] * player.outBuf.samplesms)
        if status[24] != None:
            if status[24] < 0:
                player.reqTimeEvent = None
            else:
                player.reqTimeEvent = self._seq.get_row(status[24])
        if status[25] != None:
            if status[25] < 0:
                player.outBufEvent = None
            else:
                player.outBufEvent = self._seq.get_row(status[25])
        if status[26] != None:
            if status[26] < 0:
                player.inBufEvent = None
            else:
                player.inBufEvent = self._seq.get_row(status[26])
        if status[27] != None:
            if status[27] < 0:
                player.volBufEvent = None
            else:
                player.volBufEvent = self._seq.get_row(status[27])
        if status[28] != None:
            if status[28] < 0:
                player.speedBufEvent = None
            else:
                player.speedBufEvent = self._seq.get_row(status[28])
        if status[29] != None:
            if status[29] < 0:
                player.phaseBufEvent = None
            else:
                player.phaseBufEvent = self._seq.get_row(status[29])
        if status[30] != None:
            if status[30] < 0:
                player.startBufEvent = None
            else:
                player.startBufEvent = self._seq.get_row(status[30])
        if status[31] != None:
            if status[31] < 0:
                player.lengthBufEvent = None
            else:
                player.lengthBufEvent = self._seq.get_row(status[31])

    def _update_filter(self, flt, status):
        f = flt.flt
        if status[0] != None:
            buf = status[0]
            if buf >= self._seqChannels:
                buf -= self._seqChannels
                buf += self._channels
            try:
                b = self._buffer[buf]
            except IndexError:
                raise IndexError("Invalid buffer number {}.".format(buf))
            flt.inBuf = b
            f.input(b.buffer)
        if status[1] != None:
            pos = status[1]
            if pos < 0:
                pos = int((pos * flt.inBuf.samplesms) + (flt.inBuf.samplesms - 1))
            else:
                pos = int(pos * flt.inBuf.samplesms)
            f.input_pos(pos)
        if status[2] != None:
            buf = status[2]
            if buf >= self._seqChannels:
                buf -= self._seqChannels
                buf += self._channels
            try:
                b = self._buffer[buf]
            except IndexError:
                raise IndexError("Invalid buffer number {}.".format(buf))
            flt.outBuf = b
            f.output(b.buffer)
        if status[3] != None:
            pos = status[3]
            if pos < 0:
                pos = int((pos * flt.outBuf.samplesms) + (flt.outBuf.samplesms - 1))
            else:
                pos = int(pos * flt.outBuf.samplesms)
            f.output_pos(pos)
        if status[4] != None:
            buf = status[4]
            if buf >= self._seqChannels:
                buf -= self._seqChannels
                buf += self._channels
            try:
                b = self._buffer[buf]
            except IndexError:
                raise IndexError("Invalid buffer number {}.".format(buf))
            f.filter(b.buffer)
        if status[5] != None:
            f.filter_start(status[5])
        if status[6] != None:
            f.slices(status[6])
        if status[7] != None:
            f.slice(status[7])
        if status[8] != None:
            buf = status[8]
            if buf >= self._seqChannels:
                buf -= self._seqChannels
                buf += self._channels
            try:
                b = self._buffer[buf]
            except IndexError:
                raise IndexError("Invalid buffer number {}.".format(buf))
            f.slice_source(b.buffer)
        if status[9] != None:
            f.mode(status[9])
        if status[10] != None:
            f.output_mode(status[10])
        if status[11] != None:
            f.volume(status[11])
        if status[12] != None:
            buf = status[12]
            if buf >= self._seqChannels:
                buf -= self._seqChannels
                buf += self._channels
            try:
                b = self._buffer[buf]
            except IndexError:
                raise IndexError("Invalid buffer number {}.".format(buf))
            f.volume_source(b.buffer)
        if status[13] != None:
            f.volume_mode(status[13])
        if status[14] != None:
            flt.reqTime = int(status[14] * flt.outBuf.samplesms)
        if status[15] != None:
            if status[15] < 0:
                flt.reqTimeEvent = None
            else:
                flt.reqTimeEvent = self._seq.get_row(status[15])
        if status[16] != None:
            if status[16] < 0:
                flt.outBufEvent = None
            else:
                flt.outBufEvent = self._seq.get_row(status[16])
        if status[17] != None:
            if status[17] < 0:
                flt.inBufEvent = None
            else:
                flt.inBufEvent = self._seq.get_row(status[17])
        if status[18] != None:
            if status[18] < 0:
                flt.volBufEvent = None
            else:
                flt.volBufEvent = self._seq.get_row(status[18])
        if status[19] != None:
            if status[19] < 0:
                flt.sliceBufEvent = None
            else:
                flt.sliceBufEvent = self._seq.get_row(status[19])

    def _load(self, s):
        if self._loaded:
            raise Exception("Already loaded")
        self._samplesms = s.rate() / 1000.0
        channels = s.channels()
        self._channels = len(channels)
        if self._channels < self._seqChannels:
            raise Exception("Not enough output channels to play sequence")
        newbuffer = [BufferDesc(None, 0, b, 0) for b in channels]
        newbuffer.extend(self._buffer)
        self._buffer = newbuffer
        for num, buffer in enumerate(self._buffer):
            if buffer.desc == None:
                # nothing to do for output buffers
                pass
            elif isinstance(buffer.desc, int):
                # silent buffer
                length = int(buffer.desc * self._samplesms)
                buffer.buffer = s.buffer(cg.SYNTH_TYPE_F32, None, length, "Silence {}".format(num))
            elif isinstance(buffer.desc, str):
                # filename
                b = s.buffer(buffer.desc, None)
                buffer.buffer = b
            elif isinstance(buffer.desc, cg.Buffer):
                # external buffer
                buffer.buffer = buffer.desc
            buffer.rate = buffer.buffer.rate()
            buffer.samplesms = buffer.rate / 1000.0
        if self._trace:
            print(self._buffer)
        initial = self._seq.advance(0)[1]
        self._localChannels = list()
        for num, channel in enumerate(self._channel):
            if self._trace:
                print(initial[num])
            # channel list positions are detailed in their respective _update_*
            # functions
            try:
                if channel == CHANNEL_TYPE_SILENCE:
                    buf = initial[num][0]
                    buf -= self._seqChannels
                    buf += self._channels
                    silence = SilenceState(self._buffer[buf])
                    self._update_silence(silence, initial[num])
                    silence.reqTime = 0
                    self._localChannels.append(silence)
                elif channel == CHANNEL_TYPE_PLAYER:
                    inbuf = initial[num][0]
                    inbuf -= self._seqChannels
                    inbuf += self._channels
                    b = self._buffer[inbuf].buffer
                    player = PlayerState(b.player("Player {}".format(num)))
                    self._update_player(player, initial[num])
                    player.reqTime = 0
                    self._localChannels.append(player)
                elif channel == CHANNEL_TYPE_FILTER:
                    filterbuf = initial[num][4]
                    filterbuf -= self._seqChannels
                    filterbuf += self._channels
                    b = self._buffer[filterbuf].buffer
                    flt = FilterState(b.filter(initial[num][20], "Filter {}".format(num)))
                    self._update_filter(flt, initial[num])
                    flt.reqTime = 0
                    self._localChannels.append(flt)
            except Exception as e:
                print("Error when loading channel {}.".format(num + 1))
                raise e
        if self._trace:
            print(self._localChannels)
        self._loaded = True
        self._outpos = 0
        if self._trace:
            s.print_full_stats()

    def _unload(self):
        if not self._loaded:
            raise Exception("Already not loaded")
        del self._localChannels
        self._buffer = self._buffer[self._channels:]
        for buffer in self._buffer:
            buffer.buffer = None
        self._loaded = False

    def internal(self, bufnum):
        """
        Get a pybuffer representation of a buffer from one of this sequence's buffers.
        """
        if not self._loaded:
            raise Exception("sequence not loaded, so buffers don't exist.")

        return self._buffer[bufnum].buffer.internal()

    def reset(self):
        """
        Reset everything, frees all buffers and reloads them fresh, so they're
        in a known state.
        """
        self._unload()
        self._seq.reset()
        self._load()
        self._ended = False

    def fast_reset(self):
        """
        Faster reset that just resets the sequence, and should have no
        consequences if the buffers haven't been touched.
        """
        self._seq.reset()
        self._outpos = 0
        self._ended = False

    def _advance_player_pos(self, player, time, needed):
        if player.outBuf.desc == None and self._outpos < needed:
            player.player.output_pos(self._outpos)

    def _advance_filter_pos(self, flt, time, needed):
        if flt.outBuf.desc == None and self._outpos < needed:
            flt.flt.output_pos(self._outpos)

    def _run_channels(self, reqtime, line, needed):
        if self._trace:
            print("=== run_channels === {}".format(reqtime))
        self._outpos += reqtime
        # for performance and simplicity reasons, this is evaluating whole
        # channels at a time.  Alternatively, it would look to each channel
        # for the next event then run all channels up to that event in repeat
        # but that could allow for things to be done in very slow ways which
        # result in a lot of very close together events.  I'm not looking to
        # make a full DAW, but rather a simple tracker, so don't do it that way
        i = 0
        for channel in self._localChannels:
            lastgot = -1
            if isinstance(channel, PlayerState):
                time = reqtime
                if line != None and line[i] != None:
                    if self._trace:
                        print(i, end=' ')
                        print(line[i])
                    self._update_player(channel, line[i])
                while time > 0:
                    get = time
                    if channel.reqTime < get:
                        get = channel.reqTime
                    got = channel.player.run(get)
                    if self._trace:
                        print("{} +{}".format(i, got))
                    if got == 0:
                        if lastgot == 0:
                            # heuristic to recover from a condition stuck in a
                            # loop that doesn't stop, might be heavy-handed but
                            # i guess we'll see
                            channel.reqTime = 0
                            break
                        changed = False
                        reason = channel.player.stop_reason()
                        if self._trace:
                            print("{} {} {}".format(i, channel.reqTime, hex(reason)))
                            if channel.reqTime != 0 and reason == 0:
                                raise Exception("Synth returned no samples for no reason.")
                        if channel.reqTime == 0:
                            if channel.reqTimeEvent != None:
                                upd = channel.reqTimeEvent
                                if self._trace:
                                    print(upd)
                                self._update_player(channel, upd)
                                changed = True
                        if reason & cg.SYNTH_STOPPED_OUTBUFFER:
                            if channel.outBufEvent != None:
                                upd = channel.outBufEvent
                                if self._trace:
                                    print(upd)
                                self._update_player(channel, upd)
                                changed = True
                        if reason & cg.SYNTH_STOPPED_INBUFFER:
                            if channel.inBufEvent != None:
                                upd = channel.inBufEvent
                                if self._trace:
                                    print(upd)
                                self._update_player(channel, upd)
                                changed = True
                        if reason & cg.SYNTH_STOPPED_VOLBUFFER:
                            if channel.volBufEvent != None:
                                upd = channel.volBufEvent
                                if self._trace:
                                    print(upd)
                                self._update_player(channel, upd)
                                changed = True
                        if reason & cg.SYNTH_STOPPED_SPEEDBUFFER:
                            if channel.speedBufEvent != None:
                                upd = channel.speedBufEvent
                                if self._trace:
                                    print(upd)
                                self._update_player(channel, upd)
                                changed = True
                        if reason & cg.SYNTH_STOPPED_PHASEBUFFER:
                            if channel.phaseBufEvent != None:
                                upd = channel.phaseBufEvent
                                if self._trace:
                                    print(upd)
                                self._update_player(channel, upd)
                                changed = True
                        if reason & cg.SYNTH_STOPPED_STARTBUFFER:
                            if channel.startBufEvent != None:
                                upd = channel.startBufEvent
                                if self._trace:
                                    print(upd)
                                self._update_player(channel, upd)
                                changed = True
                        if reason & cg.SYNTH_STOPPED_LENGTHBUFFER:
                            if channel.lengthBufEvent != None:
                                upd = channel.lengthBufEvent
                                if self._trace:
                                    print(upd)
                                self._update_player(channel, upd)
                                changed = True
                        if not changed:
                            channel.reqTime = 0
                            break
                    lastgot = got
                    time -= got
                    channel.reqTime -= got
                self._advance_player_pos(channel, time, needed)
            elif isinstance(channel, FilterState):
                time = reqtime
                if line != None and line[i] != None:
                    if self._trace:
                        print(i, end=' ')
                        print(line[i])
                    self._update_filter(channel, line[i])
                while time > 0:
                    get = time
                    if channel.reqTime < get:
                        get = channel.reqTime
                    got = channel.flt.run(get)
                    if self._trace:
                        print("{} +{}".format(i, got))
                    if got == 0:
                        if lastgot == 0:
                            channel.reqTime = 0
                            break
                        changed = False
                        reason = channel.flt.stop_reason()
                        if self._trace:
                            print("{} {} {}".format(i, channel.reqTime, hex(reason)))
                            if channel.reqTime != 0 and reason == 0:
                                raise Exception("Synth returned no samples for no reason.")
                        if channel.reqTime == 0:
                            if channel.reqTimeEvent != None:
                                upd = channel.reqTimeEvent
                                if self._trace:
                                    print(upd)
                                self._update_filter(channel, upd)
                                changed = True
                        if reason & cg.SYNTH_STOPPED_OUTBUFFER:
                            if channel.outBufEvent != None:
                                upd = channel.outBufEvent
                                if self._trace:
                                    print(upd)
                                self._update_filter(channel, upd)
                                changed = True
                        if reason & cg.SYNTH_STOPPED_INBUFFER:
                            if channel.inBufEvent != None:
                                upd = channel.inBufEvent
                                if self._trace:
                                    print(upd)
                                self._update_filter(channel, upd)
                                changed = True
                        if reason & cg.SYNTH_STOPPED_VOLBUFFER:
                            if channel.volBufEvent != None:
                                upd = channel.volBufEvent
                                if self._trace:
                                    print(upd)
                                self._update_filter(channel, upd)
                                changed = True
                        if reason & cg.SYNTH_STOPPED_SLICEBUFFER:
                            if channel.sliceBufEvent != None:
                                upd = channel.sliceBufEvent
                                if self._trace:
                                    print(upd)
                                self._update_filter(channel, upd)
                                changed = True
                        if not changed:
                            channel.reqTime = 0
                            break
                    lastgot = got
                    time -= got
                    channel.reqTime -= got
                self._advance_filter_pos(channel, time, needed)
            else: # silence
                time = reqtime
                if line != None and line[i] != None:
                    if self._trace:
                        print(i, end=' ')
                        print(line[i])
                    self._update_silence(channel, line[i])
                # simulate in-time synth functionality
                while time > 0:
                    get = time
                    if channel.reqTime < get:
                        get = channel.reqTime
                    remain = channel.buffer.buffer.size() - channel.outPos
                    if get > remain:
                        get = remain
                    if remain > 0:
                        channel.buffer.buffer.silence(channel.outPos, get)
                    if self._trace:
                        print("{} +{}".format(i, get))
                    if get == 0:
                        if lastgot == 0:
                            channel.reqTime = 0
                            break
                        changed = False
                        if remain == 0:
                            print("{} {} 0x1".format(i, channel.reqTime))
                        else:
                            print("{} {} 0x0".format(i, channel.reqTime))
                        if channel.reqTime == 0:
                            if channel.reqTimeEvent != None:
                                upd = channel.reqTimeEvent
                                if self._trace:
                                    print(upd)
                                self._update_silence(channel, upd)
                                changed = True
                        if remain == 0:
                            if channel.outBufEvent != None:
                                upd = channel.outBufEvent
                                if self._trace:
                                    print(upd)
                                self._update_silence(channel, upd)
                                changed = True
                        if not changed:
                            channel.reqTime = 0
                            break
                    lastgot = get
                    time -= get
                    channel.outPos += get
                    channel.reqTime -= get
            i += 1

    def run(self, needed):
        """
        Run the sequence for needed samples.
        """
        if self._ended:
            return

        if needed <= 0:
            raise ValueError("needed must be a positive, nonzero value")

        origneeded = needed
        while needed > self._samplesms:
            get = min(needed, int(self._maxreq * self._samplesms))
            try:
                time, line = self._seq.advance(int(get / self._samplesms))
            except seq.SequenceEnded:
                self._ended = True
                break
            time = int(time * self._samplesms)
            self._run_channels(time, line, needed)
            needed -= time

        return origneeded - needed

    def get_tag(self, name):
        """
        Get a tag declared in the sequence file.
        """
        return self._tag[name]

    def _reset_output_positions(self):
        # reset output channel positions to 0
        for channel in self._localChannels:
            if isinstance(channel, PlayerState):
                if channel.outBuf.desc == None:
                    channel.player.output_pos(0)
            elif isinstance(channel, FilterState):
                if channel.outBuf.desc == None:
                    channel.player.output_pos(0)
        self._outpos = 0


def _audio_system_frame(priv):
    return priv._frame_cb()

class AudioSystem():
    def __init__(self, log_cb_return, log_cb_priv, rate, channels,
                 fragsize=cg.SYNTH_DEFAULT_FRAGMENT_SIZE,
                 audformat=cg.SYNTH_TYPE_F32,
                 filename=None, opendev=True, devname=None, trace=False):
        """
        Make a new AudioSystem.

        log_cb_return  A callable which would be called when the underlying system would log.
        log_cb_priv    Something passed in to the log callback.
        rate           The desired sample rate
        channels       The desired number of channels
        fragsize       The optional desired fragment size
        audformat      The optional desired audio format
        filename       The optional output WAV file
        opendev        False to not open an audio device
        devname        The optional SDL audio device name
        trace          True to output a lot of realtime status info
        """
        self._s = cg.Synth(filename, opendev, devname,
                           _audio_system_frame, self,
                           log_cb_return, log_cb_priv,
                           rate, channels, fragsize, audformat)
        self._histo = [0]
        self._sequences = list()
        self._fragment_size = self._s.fragment_size()
        self._fragments = 0
        self._inc_fragments()
        self._error = None
        self._trace = trace
        self._lastunderrun = -1

    def print_latency(self):
        print("Latency Histogram")
        print("frag  samples  ms  count")
        for num, val in enumerate(self._histo):
            print("{}  {}  {:.03}  {}".format(num,
                                              num*self._fragment_size,
                                              num*self._fragment_size/self._s.rate()*1000.0,
                                              val),
                  end='')
            if num == self._fragments:
                print(' *')
            else:
                print()

    def print_full_stats(self):
        """
        Print a lot of status info.
        """
        self._s.print_full_stats()

    @property
    def error(self):
        """
        If frame() throws an exception, get the exception which caused it to throw originally, then clear the error state.
        returns a tuple containing the sequence which caused the error and the Exception object
        """
        error = self._error
        self._error = None
        e = self._exception
        self._e = None
        return error, e

    @property
    def rate(self):
        """
        Get the rate the synth is running at.
        """
        return self._s.rate()

    @property
    def channels(self):
        """
        Get the number of channels the synth is outputting.
        """
        return self._s.channels()

    def buffer(self, audioType, data, size, name=None):
        """
        Create a global buffer not bound directly to a sequence.

        audioType  The audio format of the data
        data       A buffer object containing the data
        size       How much of the buffer object to use
        name       An optional name for the buffer
        """
        return self._s.buffer(audioType, data, size, name)

    def _set_fragments(self):
        self._s.enabled(False)
        self._s.fragments(self._fragments)

    def _inc_fragments(self):
        self._fragments += 1
        if len(self._histo) < self._fragments + 1:
            self._histo.append(0)
        self._lastunderrun = 0
        self._set_fragments()

    def _frame_cb(self):
        try:
            if self._s.underrun():
                self._inc_fragments()
                self._s.enabled(True)
            else:
                self._histo[self._fragments] += 1
                if self._lastunderrun > -1:
                    self._lastunderrun += self._s.needed()
                    # try to return to the most stable latency in case of
                    # hitches
                    if self._lastunderrun >= self._s.rate():
                        maxval = sorted(self._histo)[-1]
                        val = self._histo.index(maxval)
                        if val != self._fragments:
                            self._fragments = val
                            self._set_fragments()
                            self._s.enabled(True)
                        self._lastunderrun = -1

            needed = self._s.needed()

            if self._trace and len(self._sequences) > 0:
                print("=== Audio Callback {} ===".format(needed))
            if needed > 0:
                for seq in self._sequences:
                    self._error = seq[0]
                    if not seq[1]:
                        continue
                    seq[0]._reset_output_positions()
                    got = seq[0].run(needed)
                    # a biiiiiit hacky but now that we're dealing with floating
                    # point stuff, but the sequencer still runs in terms of
                    # whole milliseconds (might change later?), bits of
                    # rounding error need to be lopped off so all sequences can
                    # run in lockstep
                    if not seq[0].ended:
                        needed = got
                self._error = None

            return needed
        except Exception as e:
            # save it, otherwise raising it now confuses it.
            self._exception = e
            # make sure the error falls through.
            return -1

    def add_sequence(self, seq, enabled=False):
        """
        Add a sequence.

        enabled  True to have the sequence enabled (playing) immediately
        """
        seq._load(self._s)
        self._sequences.append([seq, enabled])

    def del_sequence(self, seq):
        """
        Delete a sequence.
        """
        for item in enumerate(self._sequences):
            if item[1][0] == seq:
                item[1][0]._unload()
                self._sequences.remove(item[1])
                return
        print("WARNING: Attempt to remove sequence not added.")

    def sequence_enabled(self, seq, enabled):
        """
        Set enabled state (start/stop playing) for a sequence.
        """
        for item in self._sequences:
            if item[0] == seq:
                item[1] = not not enabled
                return
        print("WARNING: Attempt to enable sequence not added.")

    def enabled(self, enabled):
        """
        Set enabled state (start/stop playing) for the whole synth.
        """
        self._s.enabled(enabled)

    def open_wav(self, filename):
        """
        Open a WAV file for logging output.
        """
        self._s.open_wav(filename)

    def close_wav(self):
        """
        Close/finalize WAV file.
        """
        self._s.close_wav()

    def frame(self):
        """
        Indicate to the synth it's OK to request to fill buffers.
        """
        try:
            return(self._s.frame())
        except Exception as e:
            self._s.enabled(False)
            raise e
