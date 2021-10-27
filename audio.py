import array
import crustygame as cg
import sequencer as seq

#TODO: Add events to the silence channel type and make it operate in time with playback rather than as one shot.

CHANNEL_TYPE_SILENCE = "silence"
CHANNEL_TYPE_PLAYER = "player"
CHANNEL_TYPE_FILTER = "filter"

def _create_float_array(iterable):
    aType = c_float * len(iterable)
    a = aType()

    for item in enumerate(iterable):
        a[item[0]] = item[1]

    return(a)

_NOTES = "a bc d ef g "

class _EndOfFile(Exception):
    pass

class _MacroReaderIterator():
    def __init__(self, reader):
        self._reader = reader

    def __next__(self):
        try:
            return self._reader.readline()
        except _EndOfFile:
            raise StopIteration()

class MacroReader():
    """
    Gross probably slow crappy class for reading a file line by line with macro
    replacements, but it won't be dealing with large files.
    """

    def __init__(self, file, startLine=0, trace=False, macros=None):
        """
        Accepts a file or somethign with a readline() function as well as a
        list of macros which is a tuple of a name, list of argument names, and
        the replacement string.
        Replaces all instances of name arg0 arg1 arg2 ... with the replacement
        string and arg names in the replacement replaced with args
        """
        self._trace = trace
        self._file = file
        self._macros = list()
        self._line = None
        self._lines = startLine

        if macros != None:
            try:
                self._macros.extend(macros._macros)
            except AttributeError:
                self.add_macros(macros)

    def print_macros(self):
        print(self._macros)

    def add_macros(self, macros):
        if isinstance(macros[0], tuple):
            # try to find each macro arg in the macro body
            for macro in macros:
                for arg in macro[1]:
                    try:
                        macro[2].index(arg)
                    except ValueError:
                        raise ValueError("Macro {} has arg {} not found in body.".format(macro[0], arg))
            self._macros.extend(macros)
        else:
            # try to find each macro arg in the macro body
            for arg in macros[1]:
                try:
                    macros[2].index(arg)
                except ValueError:
                    raise ValueError("Macro {} has arg {} not found in body.".format(macros[0], arg))
            self._macros.append(macros)

    @property
    def curline(self):
        return self._lines

    @property
    def name(self):
        return self._file.name

    def readline(self):
        """
        Read a line with macros replaced.
        """
        if self._line == None:
            line = ""
            while True:
                newline = self._file.readline()
                if newline == "":
                    raise _EndOfFile()
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
                            index = line[index:].index(macro[0])
                        except ValueError:
                            # no macro found, just append the rest
                            newLine += line
                            break
                        changed = True
                        # append everything up to the macro name to be replaced
                        newLine += line[:index]
                        # results in args, remainder
                        args = line[index+len(macro[0]):].split(maxsplit=len(macro[1]))
                        # make a copy of the replacement string
                        replacement = str(macro[2])
                        # replace all instances of argument names with the provided
                        # values
                        for i in range(len(macro[1])):
                            replacement = replacement.replace(macro[1][i], args[i])
                        # append the replacement string
                        newLine += replacement + ' '
                        # if there's nothing left, break
                        if len(args) <= len(macro[1]):
                            break
                        # continue with the remainder
                        line = args[len(macro[1])]
                    line = newLine
                if not changed:
                    break
            self._line = line.splitlines()
        line = self._line[0]
        if len(self._line) == 1:
            self._line = None
        else:
            self._line = self._line[1:]
        if self._trace:
            print("-> {}".format(line))
        return line

    def __iter__(self):
        return _MacroReaderIterator(self)

def read_macro(line):
    macroline = line.split('=', maxsplit=1)
    lhs = macroline[0].split()
    macroname = lhs[0]
    macroargs = lhs[1:]

    return macroname, macroargs, macroline[1]

def read_macros(infile):
    macro = list()
    # read a list of macros, macros are formatted:
    # name arg0name arg1name ...=replacement
    # macro names are found in the file and replaced with replacement
    # and instances of argument names are replaced with the arguments
    # provided when the macro is used like:
    # name arg0 arg1 ...
    for line in infile:
        macro.append(read_macro(line.strip()))

    return macro

_BUILTIN_MACROS = (
    ("SYNTH_OUTPUT_REPLACE", (), str(cg.SYNTH_OUTPUT_REPLACE)),
    ("SYNTH_OUTPUT_ADD", (), str(cg.SYNTH_OUTPUT_ADD)),
    ("SYNTH_AUTO_CONSTANT", (), str(cg.SYNTH_AUTO_CONSTANT)),
    ("SYNTH_AUTO_SOURCE", (), str(cg.SYNTH_AUTO_SOURCE)),
    ("SYNTH_MODE_ONCE", (), str(cg.SYNTH_MODE_ONCE)),
    ("SYNTH_MODE_LOOP", (), str(cg.SYNTH_MODE_LOOP)),
    ("SYNTH_MODE_PHASE_SOURCE", (), str(cg.SYNTH_MODE_PHASE_SOURCE))
)

class AudioSequencer():
    def __init__(self, infile, buffer=None, extMacros=None, trace=False):
        """
        Create an audio sequence from a file.

        buffers is a list of external Buffer objects.
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
                    infile.add_macros(read_macro(line))
                elif linetype == 'tag':
                    tagline = line.split('=', maxsplit=1)
                    self._tag[tagline[0]] = tagline[1]
                elif linetype == 'buffer':
                    if line.lower() == 'external':
                        if not isinstance(buffer[extBuf], cg.Buffer):
                            raise Exception("Buffers must be external Buffers.")
                        # import an external buffer
                        self._buffer.append([buffer[extBuf], None, None, None])
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
                        self._buffer.append([item, None, None, None])
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
                        macrofile = MacroReader(macrofile, trace=True, macros=infile)
                        try:
                            macros = read_macros(macrofile)
                        except Exception as e:
                            print("Error reading macros from {} on line {}.".format(macrofile.name, macrofile.curline))
                            raise e
                        infile.add_macros(macros)
                else:
                    raise Exception("Invalid line type {}".format(linetype))
            if self._trace:
                infile.print_macros()
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
            # output buffer     0x10
            seqDesc.add_field(silenceDesc, seq.FIELD_TYPE_INT)
            # start pos         0x08
            seqDesc.add_field(silenceDesc, seq.FIELD_TYPE_INT)
            # run length        0x04
            seqDesc.add_field(silenceDesc, seq.FIELD_TYPE_INT)
            # stopped requested 0x02
            seqDesc.add_field(silenceDesc, seq.FIELD_TYPE_ROW, rowDesc=silenceDesc)
            # stopped outbuffer 0x01
            seqDesc.add_field(silenceDesc, seq.FIELD_TYPE_ROW, rowDesc=silenceDesc)
            playerDesc = seqDesc.add_row_description()
            # input buffer                      0x200000
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
            # input buffer pos                  0x100000
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_FLOAT)
            # output buffer                     0x080000
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
            # output buffer pos                 0x040000
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
            # output mode                       0x020000
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
            # volume                            0x010000
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_FLOAT)
            # volume source                     0x008000
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
            # volume mode                       0x004000
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
            # speed (frequency, /speed, note)   0x002000
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_STR)
            # speed source                      0x001000
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
            # speed mode                        0x000800
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
            # phase source                      0x000400
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
            # loop start                        0x000200
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
            # loop end                          0x000100
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
            # player mode                       0x000080
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
            # run length                        0x000040
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
            # stopped requested                 0x000020
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_ROW, rowDesc=playerDesc)
            # stopped outbuffer                 0x000010
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_ROW, rowDesc=playerDesc)
            # stopped inbuffer                  0x000008
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_ROW, rowDesc=playerDesc)
            # stopped volbuffer                 0x000004
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_ROW, rowDesc=playerDesc)
            # stopped speedbuffer               0x000002
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_ROW, rowDesc=playerDesc)
            # stopped phasebuffer               0x000001
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_ROW, rowDesc=playerDesc)
            filterDesc = seqDesc.add_row_description()
            # input buffer         0x100000
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
            # input buffer pos     0x080000
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
            # output buffer        0x040000
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
            # output buffer pos    0x020000
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
            # filter buffer        0x010000
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
            # filter buffer start  0x008000
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
            # filter buffer slices 0x004000
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
            # slice                0x002000
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
            # slice source         0x001000
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
            # filter mode          0x000800
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
            # output mode          0x000400
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
            # volume               0x000200
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_FLOAT)
            # volume source        0x000100
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
            # volume mode          0x000080
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
            # run length           0x000040
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
            # stopped requested    0x000020
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_ROW, rowDesc=filterDesc)
            # stopped outbuffer    0x000010
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_ROW, rowDesc=filterDesc)
            # stopped inbuffer     0x000008
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_ROW, rowDesc=filterDesc)
            # stopped volbuffer    0x000004
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_ROW, rowDesc=filterDesc)
            # stopped slicebuffer  0x000002
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_ROW, rowDesc=filterDesc)
            # initial size         0x000001 (only used for initialization)
            seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
            for channel in self._channel:
                if channel == CHANNEL_TYPE_SILENCE:
                    seqDesc.add_column(silenceDesc)
                elif channel == CHANNEL_TYPE_PLAYER:
                    seqDesc.add_column(playerDesc)
                elif channel == CHANNEL_TYPE_FILTER:
                    seqDesc.add_column(filterDesc)
            self._seq = seq.Sequencer(seqDesc, infile)
        except Exception as e:
            print("Exception on line {} in {}.".format(infile.curline, infile.name))
            raise e
        self._tune()
        self._loaded = False
        self._ended = False

    @property
    def ended(self):
        return self._ended

    def _tune(self):
        tuning = None
        try:
            tuning = self._tag['tuning'].split()
        except KeyError:
            self._tunes = [2 ** (x / 12) for x in range(12)]
            return

        if len(tuning) == 1:
            tuning = float(tuning[0])
            self._tunes = [tuning * (2 ** (x / 12)) for x in range(12)]
        elif len(tuning) == 12:
            self._tunes = [float(x) for x in tuning]
        else:
            raise Exception("'tuning' tag must be some detune or all 12 note detunings.")

    def _get_speed(self, speed, inrate, outrate):
        tune = 0.0
        # frequency
        try:
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

            tune = self._tunes[note] * (2 ** octave)

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

        return (outrate / inrate) * tune

    def _update_silence(self, silence, status):
        if status[0] != None:
            buf = status[0]
            if buf >= self._seqChannels:
                buf -= self._seqChannels
                buf += self._channels
            else:
                raise ValueError("Silence can't be applied to output channels")
            b = self._buffer[buf]
            silence[0] = b
        if status[1] != None:
            silence[1] = status[1] * silence[0][3]
        if status[2] != None:
            silence[2] = status[2] * silence[0][3]
        if status[3] != None:
            if status[3] == seq.EMPTY_ROW:
                silence[3] = None
            else:
                silence[3] = self._seq.get_row(status[3])
        if status[4] != None:
            if status[4] == seq.EMPTY_ROW:
                silence[4] = None
            else:
                silence[4] = self._seq.get_row(status[4])

    def _update_player(self, player, status):
        p = player[0]
        if status[0] != None:
            buf = status[0]
            if buf >= self._seqChannels:
                buf -= self._seqChannels
                buf += self._channels
            b = self._buffer[buf]
            player[8] = b
            p.input(b[2])
        if status[1] != None:
            pos = status[1]
            # make -1 be the real last sample
            if pos < 0:
                pos = (pos * player[8][3]) + (player[8][3] - 1)
            else:
                pos = pos * player[8][3]
            p.input_pos(pos)
        if status[2] != None:
            buf = status[2]
            if buf >= self._seqChannels:
                buf -= self._seqChannels
                buf += self._channels
            b = self._buffer[buf]
            player[9] = b
            p.output(b[2])
        if status[3] != None:
            pos = status[3]
            if pos < 0:
                pos = (pos * player[9][3]) + (player[9][3] - 1)
            else:
                pos = pos * player[9][3]
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
            b = self._buffer[buf]
            p.volume_source(b[2])
        if status[7] != None:
            p.volume_mode(status[7])
        if status[8] != None:
            p.speed(self._get_speed(status[8], player[8][1], player[9][1]))
        if status[9] != None:
            buf = status[9]
            if buf >= self._seqChannels:
                buf -= self._seqChannels
                buf += self._channels
            b = self._buffer[buf]
            p.speed_source(b[2])
        if status[10] != None:
            p.speed_mode(status[10])
        if status[11] != None:
            buf = status[11]
            if buf >= self._seqChannels:
                buf -= self._seqChannels
                buf += self._channels
            b = self._buffer[buf]
            p.phase_source(b[2])
        if status[12] != None:
            pos = status[12]
            if pos < 0:
                pos = (pos * player[8][3]) + (player[8][3] - 1)
            else:
                pos = pos * player[8][3]
            p.loop_start(pos)
        if status[13] != None:
            pos = status[13]
            if pos < 0:
                pos = (pos * player[8][3]) + (player[8][3] - 1)
            else:
                pos = pos * player[8][3]
            p.loop_end(pos)
        if status[14] != None:
            p.mode(status[14])
        if status[15] != None:
            player[1] = status[15] * player[9][3]
        if status[16] != None:
            if status[16] == seq.EMPTY_ROW:
                player[2] = None
            else:
                player[2] = self._seq.get_row(status[16])
        if status[17] != None:
            if status[17] == seq.EMPTY_ROW:
                player[3] = None
            else:
                player[3] = self._seq.get_row(status[17])
        if status[18] != None:
            if status[18] == seq.EMPTY_ROW:
                player[4] = None
            else:
                player[4] = self._seq.get_row(status[18])
        if status[19] != None:
            if status[19] == seq.EMPTY_ROW:
                player[5] = None
            else:
                player[5] = self._seq.get_row(status[19])
        if status[20] != None:
            if status[20] == seq.EMPTY_ROW:
                player[6] = None
            else:
                player[6] = self._seq.get_row(status[20])
        if status[21] != None:
            if status[21] == seq.EMPTY_ROW:
                player[7] = None
            else:
                player[7] = self._seq.get_row(status[21])

    def _update_filter(self, flt, status):
        f = flt[0]
        if status[0] != None:
            buf = status[0]
            if buf >= self._seqChannels:
                buf -= self._seqChannels
                buf += self._channels
            b = self._buffer[buf]
            flt[8] = b
            f.input(b[2])
        if status[1] != None:
            pos = status[1]
            if pos < 0:
                pos = (pos * flt[8][3]) + (flt[8][3] - 1)
            else:
                pos = pos * flt[8][3]
            f.input_pos(pos)
        if status[2] != None:
            buf = status[2]
            if buf >= self._seqChannels:
                buf -= self._seqChannels
                buf += self._channels
            b = self._buffer[buf]
            flt[7] = b
            f.output(b[2])
        if status[3] != None:
            pos = status[3]
            if pos < 0:
                pos = (pos * flt[7][3]) + (flt[7][3] - 1)
            else:
                pos = pos * flt[7][3]
            f.output_pos(pos)
        if status[4] != None:
            buf = status[4]
            if buf >= self._seqChannels:
                buf -= self._seqChannels
                buf += self._channels
            b = self._buffer[buf]
            f.filter(b[2])
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
            b = self._buffer[buf]
            f.slice_source(b[2])
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
            b = self._buffer[buf]
            f.volume_source(b[2])
        if status[13] != None:
            f.volume_mode(status[13])
        if status[14] != None:
            flt[1] = status[14] * flt[7][3]
        if status[15] != None:
            if status[15] == seq.EMPTY_ROW:
                flt[2] = None
            else:
                flt[2] = self._seq.get_row(status[15])
        if status[16] != None:
            if status[16] == seq.EMPTY_ROW:
                flt[3] = None
            else:
                flt[3] = self._seq.get_row(status[16])
        if status[17] != None:
            if status[17] == seq.EMPTY_ROW:
                flt[4] = None
            else:
                flt[4] = self._seq.get_row(status[17])
        if status[18] != None:
            if status[18] == seq.EMPTY_ROW:
                flt[5] = None
            else:
                flt[5] = self._seq.get_row(status[18])
        if status[19] != None:
            if status[19] == seq.EMPTY_ROW:
                flt[6] = None
            else:
                flt[6] = self._seq.get_row(status[19])

    def _load(self, s):
        if self._loaded:
            raise Exception("Already loaded")
        rate = s.rate()
        self._samplesms = int(rate / 1000)
        channels = s.channels()
        self._channels = len(channels)
        if self._channels < self._seqChannels:
            raise Exception("Not enough output channels to play sequence")
        newbuffer = [[None, rate, b, 0] for b in channels]
        newbuffer.extend(self._buffer)
        self._buffer = newbuffer
        for buffer in self._buffer:
            if buffer[0] == None:
                # nothing to do for output buffers
                pass
            elif isinstance(buffer[0], int):
                # silent buffer
                length = buffer[0] * self._samplesms
                buffer[2] = s.buffer(cg.SYNTH_TYPE_F32, None, length)
            elif isinstance(buffer[0], str):
                # filename
                b = s.buffer(buffer[0])
                buffer[2] = b
            elif isinstance(buffer[0], cg.Buffer):
                # external buffer
                buffer[2] = buffer[0]
            buffer[1] = buffer[2].rate()
            buffer[3] = int(buffer[1] / 1000)
        print(self._buffer)
        initial = self._seq.advance(0)[1]
        self._localChannels = list()
        for channel in enumerate(self._channel):
            try:
                if channel[1] == CHANNEL_TYPE_SILENCE:
                    buf = initial[channel[0]][0]
                    buf -= self._seqChannels
                    buf += self._channels
                    silence = [self._buffer[buf], 0, 0, None, None]
                    self._update_silence(silence, initial[channel[0]])
                    silence[2] = 0
                    self._localChannels.append(silence)
                elif channel[1] == CHANNEL_TYPE_PLAYER:
                    inbuf = initial[channel[0]][0]
                    inbuf -= self._seqChannels
                    inbuf += self._channels
                    b = self._buffer[inbuf][2]
                    player = [b.player(), 0, None, None, None, None, None, None, None, None, 0]
                    self._update_player(player, initial[channel[0]])
                    player[1] = 0
                    self._localChannels.append(player)
                elif channel[1] == CHANNEL_TYPE_FILTER:
                    filterbuf = initial[channel[0]][4]
                    filterbuf -= self._seqChannels
                    filterbuf += self._channels
                    b = self._buffer[filterbuf][2]
                    flt = [b.filter(initial[channel[0]][20]), 0, None, None, None, None, None, None, 0, 0]
                    self._update_filter(flt, initial[channel[0]])
                    flt[1] = 0
                    self._localChannels.append(flt)
            except Exception as e:
                print("Error when loading channel {}.".format(channel[0] + 1))
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
            buffer[2] = None
        self._loaded = False

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
        if player[9][0] == None and self._outpos < needed:
            player[0].output_pos(self._outpos)

    def _advance_filter_pos(self, filt, time, needed):
        if filt[7][0] == None and self._outpos < needed:
            filt[0].output_pos(self._outpos)

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
            if isinstance(channel[0], cg.Player):
                time = reqtime
                if line != None and line[i] != None:
                    if self._trace:
                        print(i, end=' ')
                        print(line[i])
                    self._update_player(channel, line[i])
                while time > 0:
                    get = time
                    if channel[1] < get:
                        get = channel[1]
                    got = channel[0].run(get)
                    if self._trace:
                        print("{} +{}".format(i, got))
                    if got == 0:
                        if lastgot == 0:
                            # heuristic to recover from a condition stuck in a
                            # loop that doesn't stop, might be heavy-handed but
                            # i guess we'll see
                            channel[1] = 0
                            break
                        changed = False
                        reason = channel[0].stop_reason()
                        if self._trace:
                            print("{} {} {}".format(i, channel[1], hex(reason)))
                            if channel[1] != 0 and reason == 0:
                                raise Exception("Synth returned no samples for n // 1000o reason.")
                        if channel[1] == 0:
                            if channel[2] != None:
                                upd = channel[2]
                                if self._trace:
                                    print(upd)
                                self._update_player(channel, upd)
                                changed = True
                        if reason & cg.SYNTH_STOPPED_OUTBUFFER:
                            if channel[3] != None:
                                upd = channel[3]
                                if self._trace:
                                    print(upd)
                                self._update_player(channel, upd)
                                changed = True
                        if reason & cg.SYNTH_STOPPED_INBUFFER:
                            if channel[4] != None:
                                upd = channel[4]
                                if self._trace:
                                    print(upd)
                                self._update_player(channel, upd)
                                changed = True
                        if reason & cg.SYNTH_STOPPED_VOLBUFFER:
                            if channel[5] != None:
                                upd = channel[5]
                                if self._trace:
                                    print(upd)
                                self._update_player(channel, upd)
                                changed = True
                        if reason & cg.SYNTH_STOPPED_SPEEDBUFFER:
                            if channel[6] != None:
                                upd = channel[6]
                                if self._trace:
                                    print(upd)
                                self._update_player(channel, upd)
                                changed = True
                        if reason & cg.SYNTH_STOPPED_PHASEBUFFER:
                            if channel[7] != None:
                                upd = channel[7]
                                if self._trace:
                                    print(upd)
                                self._update_player(channel, upd)
                                changed = True
                        if not changed:
                            channel[1] = 0
                            break
                    lastgot = got
                    time -= got
                    channel[1] -= got
                self._advance_player_pos(channel, time, needed)
            elif isinstance(channel[0], cg.Filter):
                time = reqtime
                if line != None and line[i] != None:
                    if self._trace:
                        print(i, end=' ')
                        print(line[i])
                    self._update_filter(channel, line[i])
                while time > 0:
                    get = time
                    if channel[1] < get:
                        get = channel[1]
                    got = channel[0].run(get)
                    if self._trace:
                        print("{} +{}".format(i, got))
                    if got == 0:
                        if lastgot == 0:
                            channel[1] = 0
                            break
                        changed = False
                        reason = channel[0].stop_reason()
                        if self._trace:
                            print("{} {} {}".format(i, channel[1], hex(reason)))
                            if channel[1] != 0 and reason == 0:
                                raise Exception("Synth returned no samples for no reason.")
                        if channel[1] == 0:
                            if channel[2] != None:
                                upd = channel[2]
                                if self._trace:
                                    print(upd)
                                self._update_filter(channel, upd)
                                changed = True
                        if reason & cg.SYNTH_STOPPED_OUTBUFFER:
                            if channel[3] != None:
                                upd = channel[3]
                                if self._trace:
                                    print(upd)
                                self._update_filter(channel, upd)
                                changed = True
                        if reason & cg.SYNTH_STOPPED_INBUFFER:
                            if channel[4] != None:
                                upd = channel[4]
                                if self._trace:
                                    print(upd)
                                self._update_filter(channel, upd)
                                changed = True
                        if reason & cg.SYNTH_STOPPED_VOLBUFFER:
                            if channel[5] != None:
                                upd = channel[5]
                                if self._trace:
                                    print(upd)
                                self._update_filter(channel, upd)
                                changed = True
                        if reason & cg.SYNTH_STOPPED_SLICEBUFFER:
                            if channel[6] != None:
                                upd = channel[6]
                                if self._trace:
                                    print(upd)
                                self._update_filter(channel, upd)
                                changed = True
                        if not changed:
                            channel[1] = 0
                            break
                    lastgot = got
                    time -= got
                    channel[1] -= got
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
                    if channel[2] < get:
                        get = channel[2]
                    remain = channel[0][2].size() - channel[1]
                    if get > remain:
                        get = remain
                    if remain > 0:
                        channel[0][2].silence(channel[1], get)
                    if self._trace:
                        print("{} +{}".format(i, get))
                    if get == 0:
                        if lastgot == 0:
                            channel[2] = 0
                            break
                        changed = False
                        if channel[2] == 0:
                            if channel[3] != None:
                                upd = channel[3]
                                if self._trace:
                                    print(upd)
                                self._update_silence(channel, upd)
                                changed = True
                        if remain == 0:
                            if channel[4] != None:
                                upd = channel[4]
                                if self._trace:
                                    print(upd)
                                self._update_silence(channel, upd)
                                changed = True
                        if not changed:
                            channel[2] = 0
                            break
                    lastgot = get
                    time -= get
                    channel[1] += get
                    channel[2] -= get
            i += 1

    def run(self, needed):
        if self._ended:
            return

        if needed == 0:
            try:
                _, line = self._seq.advance(0)
            except seq.SequenceEnded:
                self._ended = True
            self._run_channels(0, line)
        elif needed > 0:
            while needed > 0:
                get = min(needed, self._maxreq)
                try:
                    time, line = self._seq.advance(get)
                except seq.SequenceEnded:
                    self._ended = True
                    break
                self._run_channels(time * self._samplesms, line, needed * self._samplesms)
                needed -= time
        else:
            raise ValueError("needed must be a positive value")

    def get_tag(self, name):
        return self._tag[name]

    def _reset_output_positions(self):
        # reset output channel positions to 0
        for channel in self._localChannels:
            if isinstance(channel[0], cg.Player):
                if channel[9][0] == None:
                    channel[0].output_pos(0)
            elif isinstance(channel[0], cg.Filter):
                if channel[7][0] == None:
                    channel[0].output_pos(0)
        self._outpos = 0


def audio_system_frame(priv):
    return priv._frame_cb()

class AudioSystem():
    def __init__(self, log_cb_return, log_cb_priv, rate, channels, trace=False):
        self._s = cg.Synth(audio_system_frame, self,
                           log_cb_return, log_cb_priv,
                           rate, channels)
        self._sequences = list()
        self._samplesms = int(self._s.rate() / 1000)
        self._fragment_size = self._s.fragment_size()
        self._fragments = 0
        self._inc_fragments()
        self._error = None
        self._trace = trace

    def print_full_stats(self):
        self._s.print_full_stats()

    @property
    def error(self):
        error = self._error
        self._error = None
        e = self._exception
        self._e = None
        return error, e

    @property
    def rate(self):
        return self._s.rate()

    @property
    def channels(self):
        return self._s.channels()

    def buffer(self, audioType, data, size):
        return self._s.buffer(audioType, data, size)

    def _inc_fragments(self):
        self._s.enabled(0)
        self._fragments += 1
        self._s.fragments(self._fragments)

    def _frame_cb(self):
        try:
            if self._s.underrun():
                self._inc_fragments()
                self._s.enabled(True)
                # s.enabled() will eventually call this function again so when it
                # finally returns back to here, just return again
                return 0

            needed = int(self._s.needed() / self._samplesms)
            if self._trace and len(self._sequences) > 0:
                print("=== Audio Callback {} ===".format(needed))
            if needed > 0:
                for seq in self._sequences:
                    self._error = seq[0]
                    if not seq[1]:
                        continue
                    seq[0]._reset_output_positions()
                    seq[0].run(needed)
                self._error = None

            return needed * self._samplesms
        except Exception as e:
            # save it, otherwise raising it now confuses it.
            self._exception = e
            # make sure the error falls through.
            return -1

    def add_sequence(self, seq, enabled=False):
        seq._load(self._s)
        self._sequences.append([seq, enabled])

    def del_sequence(self, seq):
        for item in enumerate(self._sequences):
            if item[1][0] == seq:
                item[1][0]._unload()
                self._sequences.remove(item[1])
                return
        print("WARNING: Attempt to remove sequence not added.")

    def sequence_enabled(self, seq, enabled):
        for item in self._sequences:
            if item[0] == seq:
                item[1] = not not enabled
                return
        print("WARNING: Attempt to enable sequence not added.")

    def enabled(self, enabled):
        self._s.enabled(enabled)

    def open_wav(self, filename):
        self._s.open_wav(filename)

    def close_wav(self):
        self._s.close_wav()

    def frame(self):
        try:
            self._s.frame()
        except Exception as e:
            self._s.enabled(False)
            raise e
