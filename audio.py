import array
import crustygame as cg
import sequencer as seq

CHANNEL_TYPE_SILENCE = "silence"
CHANNEL_TYPE_PLAYER = "player"
CHANNEL_TYPE_FILTER = "filter"

def _create_float_array(iterable):
    aType = c_float * len(iterable)
    a = aType()

    for item in enumerate(iterable):
        a[item[0]] = item[1]

    return(a)

_NOTES = "c d ef g a b"

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
                for macro_b in self._macros:
                    if macro[0] in macro_b[0]:
                        raise ValueError("Macro {} would be aliased by macro {}.".format(macro_b[0], macro[0]))
                    elif macro_b[0] in macro[0]:
                        raise ValueError("Macro {} would be aliased by macro {}.".format(macro[0], macro_b[0]))
                for arg in macro[1]:
                    try:
                        macro[2].index(arg)
                    except ValueError:
                        raise ValueError("Macro {} has arg {} not found in body.".format(macro[0], arg))
            self._macros.extend(macros)
        else:
            for macro_b in self._macros:
                if macros[0] in macro_b[0]:
                    raise ValueError("Macro {} would be aliased by macro {}.".format(macro_b[0], macros[0]))
                elif macro_b[0] in macros[0]:
                    raise ValueError("Macro {} would be aliased by macro {}.".format(macros[0], macro_b[0]))
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
                            try:
                                replacement = replacement.replace(macro[1][i], args[i])
                            except IndexError:
                                raise ValueError("Invalid arguments used for macro {} ({} != {})".format(macro[0], len(macro[1]), len(args)))
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
                        macrofile = MacroReader(macrofile, trace=trace, macros=infile)
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
        self._tune()
        self._loaded = False
        self._ended = False

    @property
    def ended(self):
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
        # 0  output buffer
        # 1  start position
        # 2  requested time
        # 3  row ID for requested time met behavior
        # 4  row ID for output buffer filled behavior
        # status arguments are the order in which they appear
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
            silence[0] = b
        if status[1] != None:
            silence[1] = int(status[1] * silence[0][3])
        if status[2] != None:
            silence[2] = int(status[2] * silence[0][3])
        if status[3] != None:
            if status[3] < 0:
                silence[3] = None
            else:
                silence[3] = self._seq.get_row(status[3])
        if status[4] != None:
            if status[4] < 0:
                silence[4] = None
            else:
                silence[4] = self._seq.get_row(status[4])

    def _update_player(self, player, status):
        # 0  the underlying Player object
        # 1  requested time
        # 2  row ID for requested time met behavior
        # 3  row ID for output buffer filled behavior
        # 4  row ID for input buffer exhausted behavior
        # 5  row ID for volume buffer exhausted behavior
        # 6  row ID for speed buffer exhausted behavior
        # 7  row ID for phase buffer exhausted behavior
        # 8  input Buffer object
        # 9  output Buffer object
        p = player[0]
        if status[0] != None:
            buf = status[0]
            if buf >= self._seqChannels:
                buf -= self._seqChannels
                buf += self._channels
            try:
                b = self._buffer[buf]
            except IndexError:
                raise IndexError("Invalid buffer number {}.".format(buf))
            player[10] = b
            p.input(b[2])
        if status[1] != None:
            pos = status[1]
            # make -1.0 be the real last sample
            # input buffer position is natively float, so don't convert to int
            if pos < 0.0:
                pos = (pos * player[10][3]) + (player[10][3] - 1.0)
            else:
                pos = pos * player[10][3]
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
            player[11] = b
            p.output(b[2])
        if status[3] != None:
            pos = status[3]
            if pos < 0:
                pos = int((pos * player[11][3]) + (player[11][3] - 1))
            else:
                pos = int(pos * player[11][3])
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
            p.volume_source(b[2])
        if status[7] != None:
            p.volume_mode(status[7])
        if status[8] != None:
            p.speed(self._get_speed(status[8], player[10][1], player[11][1]))
        if status[9] != None:
            buf = status[9]
            if buf >= self._seqChannels:
                buf -= self._seqChannels
                buf += self._channels
            try:
                b = self._buffer[buf]
            except IndexError:
                raise IndexError("Invalid buffer number {}.".format(buf))
            p.speed_source(b[2])
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
            p.phase_source(b[2])
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
            p.start_source(b[2])
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
            p.length_source(b[2])
        if status[20] != None:
            p.length_values(status[20])
        if status[21] != None:
            p.length_granularity(status[21])
        if status[22] != None:
            p.length_mode(status[22])
        if status[23] != None:
            player[1] = int(status[23] * player[11][3])
        if status[24] != None:
            if status[24] < 0:
                player[2] = None
            else:
                player[2] = self._seq.get_row(status[24])
        if status[25] != None:
            if status[25] < 0:
                player[3] = None
            else:
                player[3] = self._seq.get_row(status[25])
        if status[26] != None:
            if status[26] < 0:
                player[4] = None
            else:
                player[4] = self._seq.get_row(status[26])
        if status[27] != None:
            if status[27] < 0:
                player[5] = None
            else:
                player[5] = self._seq.get_row(status[27])
        if status[28] != None:
            if status[28] < 0:
                player[6] = None
            else:
                player[6] = self._seq.get_row(status[28])
        if status[29] != None:
            if status[29] < 0:
                player[7] = None
            else:
                player[7] = self._seq.get_row(status[29])
        if status[30] != None:
            if status[30] < 0:
                player[8] = None
            else:
                player[8] = self._seq.get_row(status[30])
        if status[31] != None:
            if status[31] < 0:
                player[9] = None
            else:
                player[9] = self._seq.get_row(status[31])

    def _update_filter(self, flt, status):
        # 0  the underlying Filter object
        # 1  requested time
        # 2  row ID for requested time met behavior
        # 3  row ID for output buffer filled behavior
        # 4  row ID for input buffer exhausted behavior
        # 5  row ID for volume buffer exhausted behavior
        # 6  row ID for slice buffer exhausted behavior
        # 7  output Buffer object (yes, these are inverted from Player...)
        # 8  input Buffer object
        f = flt[0]
        if status[0] != None:
            buf = status[0]
            if buf >= self._seqChannels:
                buf -= self._seqChannels
                buf += self._channels
            try:
                b = self._buffer[buf]
            except IndexError:
                raise IndexError("Invalid buffer number {}.".format(buf))
            flt[8] = b
            f.input(b[2])
        if status[1] != None:
            pos = status[1]
            if pos < 0:
                pos = int((pos * flt[8][3]) + (flt[8][3] - 1))
            else:
                pos = int(pos * flt[8][3])
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
            flt[7] = b
            f.output(b[2])
        if status[3] != None:
            pos = status[3]
            if pos < 0:
                pos = int((pos * flt[7][3]) + (flt[7][3] - 1))
            else:
                pos = int(pos * flt[7][3])
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
            try:
                b = self._buffer[buf]
            except IndexError:
                raise IndexError("Invalid buffer number {}.".format(buf))
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
            try:
                b = self._buffer[buf]
            except IndexError:
                raise IndexError("Invalid buffer number {}.".format(buf))
            f.volume_source(b[2])
        if status[13] != None:
            f.volume_mode(status[13])
        if status[14] != None:
            flt[1] = int(status[14] * flt[7][3])
        if status[15] != None:
            if status[15] < 0:
                flt[2] = None
            else:
                flt[2] = self._seq.get_row(status[15])
        if status[16] != None:
            if status[16] < 0:
                flt[3] = None
            else:
                flt[3] = self._seq.get_row(status[16])
        if status[17] != None:
            if status[17] < 0:
                flt[4] = None
            else:
                flt[4] = self._seq.get_row(status[17])
        if status[18] != None:
            if status[18] < 0:
                flt[5] = None
            else:
                flt[5] = self._seq.get_row(status[18])
        if status[19] != None:
            if status[19] < 0:
                flt[6] = None
            else:
                flt[6] = self._seq.get_row(status[19])

    def _load(self, s):
        if self._loaded:
            raise Exception("Already loaded")
        rate = s.rate()
        self._samplesms = rate / 1000
        channels = s.channels()
        self._channels = len(channels)
        if self._channels < self._seqChannels:
            raise Exception("Not enough output channels to play sequence")
        # 0  None for output buffer
        #    int for a length of empty buffer in milliseconds
        #    str for loading a WAV from a file
        #    Buffer for taking an external buffer
        # 1  sample rate for the buffer, pretty much only meaningful for WAV
        #    used for calculating real play speed by a letter note
        #    files imported that way, otherwise it's the synth rate
        # 2  the Buffer object
        # 3  the samples per millisecond calculated from the rate
        #    used for calculating times in samples for time/position arguments
        newbuffer = [[None, rate, b, 0] for b in channels]
        newbuffer.extend(self._buffer)
        self._buffer = newbuffer
        for buffer in enumerate(self._buffer):
            num = buffer[0]
            buffer = buffer[1]
            if buffer[0] == None:
                # nothing to do for output buffers
                pass
            elif isinstance(buffer[0], int):
                # silent buffer
                length = int(buffer[0] * self._samplesms)
                buffer[2] = s.buffer(cg.SYNTH_TYPE_F32, None, length, "silence {}".format(num))
            elif isinstance(buffer[0], str):
                # filename
                b = s.buffer(buffer[0], None)
                buffer[2] = b
            elif isinstance(buffer[0], cg.Buffer):
                # external buffer
                buffer[2] = buffer[0]
            buffer[1] = buffer[2].rate()
            buffer[3] = buffer[1] / 1000
        if self._trace:
            print(self._buffer)
        initial = self._seq.advance(0)[1]
        self._localChannels = list()
        for channel in enumerate(self._channel):
            if self._trace:
                print(initial[channel[0]])
            # channel list positions are detailed in their respective _update_*
            # functions
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
                    player = [b.player("Player {}".format(channel[0])), 0, None, None, None, None, None, None, None, None, None, None, 0]
                    self._update_player(player, initial[channel[0]])
                    player[1] = 0
                    self._localChannels.append(player)
                elif channel[1] == CHANNEL_TYPE_FILTER:
                    filterbuf = initial[channel[0]][4]
                    filterbuf -= self._seqChannels
                    filterbuf += self._channels
                    b = self._buffer[filterbuf][2]
                    flt = [b.filter(initial[channel[0]][20], "Filter {}".format(channel[0])), 0, None, None, None, None, None, None, 0, 0]
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

    def internal(self, bufnum):
        if not self._loaded:
            raise Exception("sequence not loaded, so buffers don't exist.")

        return self._buffer[bufnum][2].internal()

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
        if player[11][0] == None and self._outpos < needed:
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
                                raise Exception("Synth returned no samples for no reason.")
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
                        if reason & cg.SYNTH_STOPPED_STARTBUFFER:
                            if channel[8] != None:
                                upd = channel[8]
                                if self._trace:
                                    print(upd)
                                self._update_player(channel, upd)
                                changed = True
                        if reason & cg.SYNTH_STOPPED_LENGTHBUFFER:
                            if channel[9] != None:
                                upd = channel[9]
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
                        if remain == 0:
                            print("{} {} 0x1".format(i, channel[2]))
                        else:
                            print("{} {} 0x0".format(i, channel[2]))
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
        return self._tag[name]

    def _reset_output_positions(self):
        # reset output channel positions to 0
        for channel in self._localChannels:
            if isinstance(channel[0], cg.Player):
                if channel[11][0] == None:
                    channel[0].output_pos(0)
            elif isinstance(channel[0], cg.Filter):
                if channel[7][0] == None:
                    channel[0].output_pos(0)
        self._outpos = 0


def audio_system_frame(priv):
    return priv._frame_cb()

class AudioSystem():
    def __init__(self, log_cb_return, log_cb_priv, rate, channels,
                 fragsize=cg.SYNTH_DEFAULT_FRAGMENT_SIZE,
                 audformat=cg.SYNTH_TYPE_F32,
                 filename=None, opendev=True, devname=None, trace=False):
        self._s = cg.Synth(filename, opendev, devname,
                           audio_system_frame, self,
                           log_cb_return, log_cb_priv,
                           rate, channels, fragsize, audformat)
        self._sequences = list()
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

    def buffer(self, audioType, data, size, name):
        return self._s.buffer(audioType, data, size, name)

    def _inc_fragments(self):
        self._s.enabled(False)
        self._fragments += 1
        self._s.fragments(self._fragments)

    def _frame_cb(self):
        try:
            if self._s.underrun():
                self._inc_fragments()
                self._s.enabled(True)

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
            return(self._s.frame())
        except Exception as e:
            self._s.enabled(False)
            raise e
