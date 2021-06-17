import array
import pycrustygame as cg
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

_NOTES = "a bc d ef g "


class MacroReader():
    """
    Gross probably slow crappy class for reading a file line by line with macro
    replacements, but it won't be dealing with large files.
    """

    def __init__(self, file, macros):
        """
        Accepts a file or somethign with a readline() function as well as a
        list of macros which is a tuple of a name, list of argument names, and
        the replacement string.
        Replaces all instances of name arg0 arg1 arg2 ... with the replacement
        string and arg names in the replacement replaced with args
        """
        self._file = file
        self._macros = macros
        self._line = None

    def readline(self):
        """
        Read a line with macros replaced.
        """
        if self._line == None:
            line = ""
            while True:
                line += self._file.readline()
                line = line.split('#', maxsplit=1)
                line = line[0].strip()
                if len(line) > 0 and line[-1] == '\\':
                    line = line[:-1]
                    continue
                if len(line) > 0:
                    break
 
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
                    # append everything up to the macro name to be replaced
                    newLine += line[:index]
                    # results in name, args, remainder
                    args = line[index:].split(maxsplit=len(macro[1]) + 1)
                    # don't need the name
                    args = args[1:]
                    # make a copy of the replacement string
                    replacement = str(macro[2])
                    # replace all instances of argument names with the provided
                    # values
                    for i in range(len(macro[1])):
                        replacement.replace(macro[1][i], args[i])
                    # append the replacement string
                    newLine += replacement + ' '
                    # continue with the remainder
                    line = args[len(macro[1])]
                line = newLine
            self._line = line.splitlines()
        line = self._line[0]
        if len(self._line) == 1:
            self._line = None
        else:
            self._line = self._line[1:]
        return line


class AudioSequencer():
    def __init__(self, infile, buffer=None):
        """
        Create an audio sequence from a file.

        buffers is a list of either float arrays or other external Buffer objects.
        """
        if infile.readline().strip() != "CrustyTracker":
            raise Exception("File isn't a CrustyTracker sequence.")
        line = infile.readline().split()
        self._version = int(line[0])
        self._seqChannels = int(line[1])
        if self._version != 1:
            raise Exception("Unsupported version: {}".format(version))
        while True:
            line = infile.readline().split('#', maxsplit=1)
            line = line[0]
            if len(line) != 0:
                break
        macros = int(line)
        macro = list()
        macro.append(("SYNTH_OUTPUT_REPLACE", (), str(cg.SYNTH_OUTPUT_REPLACE)))
        macro.append(("SYNTH_OUTPUT_ADD", (), str(cg.SYNTH_OUTPUT_ADD)))
        macro.append(("SYNTH_AUTO_CONSTANT", (), str(cg.SYNTH_AUTO_CONSTANT)))
        macro.append(("SYNTH_AUTO_SOURCE", (), str(cg.SYNTH_AUTO_SOURCE)))
        macro.append(("SYNTH_MODE_ONCE", (), str(cg.SYNTH_MODE_ONCE)))
        macro.append(("SYNTH_MODE_LOOP", (), str(cg.SYNTH_MODE_ONCE)))
        macro.append(("SYNTH_MODE_PHASE_SOURCE", (), str(cg.SYNTH_MODE_ONCE)))
        # read a list of macros, macros are formatted:
        # name arg0name arg1name ...=replacement
        # macro names are found in the file and replaced with replacement
        # and instances of argument names are replaced with the arguments
        # provided when the macro is used like:
        # name arg0 arg1 ...
        for i in range(macros):
            line = ""
            while True:
                line += infile.readline()
                line = line.split('#', maxsplit=1)
                line = line[0].strip()
                if len(line) > 0 and line[-1] == '\\':
                    continue
                if len(line) > 0:
                    break
            macroline = line[0].split('=', maxsplit=1)
            lhs = macroline[0].split()
            macroname = lhs[0]
            macroargs = lhs[1:]
            macro.append(macroname, macroargs, macroline[1])
        print(macro)
        infile = MacroReader(infile, macro)
        tags = int(infile.readline())
        self._tag = dict()
        for i in range(tags):
            tagline = line.split('=', maxsplit=1)
            self._tag[tagline[0]] = tagline[1]
        self._tune()
        line = infile.readline().split()
        buffers = int(line[0])
        self._inbufs = int(line[1])
        self._buffer = list()
        for i in range(buffers):
            bufferline = infile.readline().split(maxsplit=1)
            item = None
            # single value means the buffer will be provided
            try:
                # add the time in milliseconds of an empty buffer
                item = int(bufferline[0])
            except ValueError:
                # add the string to use as a filename later
                item = bufferline[0].strip()
            self._buffer.append([item, None, None])
        for i in range(self._inbufs):
            if isinstance(buffer[i], cg.Buffer):
                # import an external buffer
                item = buffer[i]
            elif isinstance(buffer[i], array.array) and \
                 buffer[i].typecode != 'f':
                # convert to a ctypes array so _load() can just pass it
                # along
                item = _create_float_array(buffer[i])
            else:
                raise Exception("Buffers must be float arrays or external Buffers.")
            self._buffer.append([item, 0, None])
        print(self._buffer)
        channels = int(infile.readline())
        self._channel = list()
        for i in range(channels):
            channel = infile.readline().strip().lower()
            if channel == CHANNEL_TYPE_SILENCE:
                self._channel.append(CHANNEL_TYPE_SILENCE)
            if channel == CHANNEL_TYPE_PLAYER:
                self._channel.append(CHANNEL_TYPE_PLAYER)
            elif channel == CHANNEL_TYPE_FILTER:
                self._channel.append(CHANNEL_TYPE_FILTER)
            else:
                raise Exception("Invalid channel type: {}".format(channel))
        print(self._channel)
        seqDesc = seq.SequenceDescription()
        silenceDesc = seqDesc.add_row_description()
        # output buffer 0x1
        seqDesc.add_field(silenceDesc, seq.FIELD_TYPE_INT)
        # start         0x2
        seqDesc.add_field(silenceDesc, seq.FIELD_TYPE_INT)
        # length        0x4
        seqDesc.add_field(silenceDesc, seq.FIELD_TYPE_INT)
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
        # input buffer
        seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
        # input buffer pos
        seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
        # output buffer
        seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
        # output buffer pos
        seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
        # filter buffer
        seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
        # filter buffer start
        seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
        # filter buffer slices
        seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
        # slice
        seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
        # slice source
        seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
        # filter mode
        seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
        # output mode
        seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
        # volume
        seqDesc.add_field(filterDesc, seq.FIELD_TYPE_FLOAT)
        # volume source
        seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
        # volume mode
        seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
        # run length
        seqDesc.add_field(filterDesc, seq.FIELD_TYPE_INT)
        # stopped requested
        seqDesc.add_field(filterDesc, seq.FIELD_TYPE_ROW, rowDesc=filterDesc)
        # stopped outbuffer
        seqDesc.add_field(filterDesc, seq.FIELD_TYPE_ROW, rowDesc=filterDesc)
        # stopped inbuffer
        seqDesc.add_field(filterDesc, seq.FIELD_TYPE_ROW, rowDesc=filterDesc)
        # stopped volbuffer
        seqDesc.add_field(filterDesc, seq.FIELD_TYPE_ROW, rowDesc=filterDesc)
        # stopped slicebuffer
        seqDesc.add_field(filterDesc, seq.FIELD_TYPE_ROW, rowDesc=filterDesc)
        for channel in self._channel:
            if channel == CHANNEL_TYPE_SILENCE:
                seqDesc.add_column(silenceDesc)
            elif channel == CHANNEL_TYPE_PLAYER:
                seqDesc.add_column(playerDesc)
            elif channel == CHANNEL_TYPE_FILTER:
                seqDesc.add_column(filterDesc)
        self._seq = seq.Sequencer(seqDesc, infile)
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
            note = _NOTES.index(speed[0].lower())
            octave = 4
            if len(speed) > 1:
                try:
                    octave = int(speed[1])
                except ValueError:
                    if len(speed) > 2:
                        try:
                            octave = int(speed[2])
                        except ValueError:
                            pass
                if speed[1] == '#':
                    note += 1;
                    if note == 12:
                        octave += 1
                        note = 0
                elif speed[1] == 'b':
                    note -= 1;
                    if note == -1:
                        octave -= 1
                        note = 11
            tune = self._tunes[note]
            if octave < 4:
                tune /= 5 - octave
            elif octave > 4:
                tune *= octave - 3

        return (outrate / inrate) * tune

    def _update_silence(self, silence, status):
        if status[0] != None:
            buf = status[0]
            if buf >= self._seqChannels:
                buf -= self._seqChannels
                buf += self._channels
            b = self._buffer[buf]
            silence[0] = b[2]
        if status[1] != None:
            silence[1] = status[1]
        if status[2] != None:
            silence[2] = status[2]

    def _update_player(self, player, status):
        p = player[0]
        if status[0] != None:
            buf = status[0]
            if buf >= self._seqChannels:
                buf -= self._seqChannels
                buf += self._channels
            b = self._buffer[buf]
            player[8] = b
            p.input_buffer(b[2])
        if status[1] != None:
            pos = status[1] * self._samplesms
            p.input_pos(pos)
        if status[2] != None:
            buf = status[2]
            if buf >= self._seqChannels:
                buf -= self._seqChannels
                buf += self._channels
            b = self._buffer[buf]
            player[9] = b
            p.output_buffer(b[2])
        if status[3] != None:
            pos = status[3] * self._samplesms
            player[10] = pos
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
            p.output_buffer(b[2])
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
            p.output_buffer(b[2])
        if status[10] != None:
            p.speed_mode(status[10])
        if status[11] != None:
            buf = status[11]
            if buf >= self._seqChannels:
                buf -= self._seqChannels
                buf += self._channels
            b = self._buffer[buf]
            p.output_buffer(b[2])
        if status[12] != None:
            p.loop_start(status[12])
        if status[13] != None:
            p.loop_end(status[13])
        if status[14] != None:
            p.mode(status[14])
        if status[15] != None:
            player[1] = status[15] * self._samplesms
        if status[16] != None:
            player[2] = status[16]
        if status[17] != None:
            player[3] = status[17]
        if status[18] != None:
            player[4] = status[18]
        if status[19] != None:
            player[5] = status[19]
        if status[20] != None:
            player[6] = status[20]
        if status[21] != None:
            player[7] = status[21]

    def _update_filter(self, flt, status):
        f = flt[0]
        if status[0] != None:
            buf = status[0]
            if buf >= self._seqChannels:
                buf -= self._seqChannels
                buf += self._channels
            b = self._buffer[buf]
            f.input_buffer(b[2])
        if status[1] != None:
            pos = status[1] * self._samplesms
            f.input_pos(pos)
        if status[2] != None:
            buf = status[2]
            if buf >= self._seqChannels:
                buf -= self._seqChannels
                buf += self._channels
            b = self._buffer[buf]
            flt[7] = b
            f.output_buffer(b[2])
        if status[3] != None:
            pos = status[3] * self._samplesms
            flt[8] = outpos
            f.output_pos(outpos)
        if status[4] != None:
            buf = status[4]
            if buf >= self._seqChannels:
                buf -= self._seqChannels
                buf += self._channels
            b = self._buffer[buf]
            f.filter_buffer(b[2])
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
            flt[1] = status[14] * self._samplesms
        if status[15] != None:
            flt[2] = status[15]
        if status[16] != None:
            flt[3] = status[16]
        if status[16] != None:
            flt[4] = status[17]
        if status[16] != None:
            flt[5] = status[18]
        if status[16] != None:
            flt[6] = status[19]

    def _load(self, s):
        if self._loaded:
            raise Exception("Already loaded")
        rate = s.rate
        self._samplesms = int(rate / 1000)
        self._channels = s.channels
        if self._channels < self._seqChannels:
            raise Exception("Not enough output channels to play sequence")
        newbuffer = [[None, rate, b] for b in s.output_buffers()]
        newbuffer.extend(self._buffer)
        self._buffer = newbuffer
        for buffer in self._buffer:
            if buffer[0] == None:
                # nothing to do for output buffers
                pass
            elif isinstance(buffer[0], int):
                # silent buffer
                length = buffer[0] * self._samplesms
                buffer[1] = rate
                buffer[2] = s.buffer(cg.SYNTH_TYPE_F32, None, length)
            elif isinstance(buffer[0], str):
                # filename
                b, r = s.buffer_from_wav(buffer[0])
                buffer[1] = r
                buffer[2] = b
            elif isinstance(buffer[0], cg.Buffer):
                buffer[1] = rate
                buffer[2] = buffer[0]
            else:
                # already a ctypes array
                b = s.buffer(cg.SYNTH_TYPE_F32, buffer[0], len(buffer[0]))
                buffer[1] = rate
                buffer[2] = b
        print(self._buffer)
        initial = self._seq.advance(0)[1]
        self._localChannels = list()
        for channel in enumerate(self._channel):
            if channel[1] == CHANNEL_TYPE_SILENCE:
                buf = initial[channel[0]][0]
                buf -= self._seqChannels
                buf += self._channels
                silence = [self._buffer[buf],
                           initial[channel[0]][1],
                           initial[channel[0]][2]]
                silence[2] = 0
                self._localChannels.append(silence)
            elif channel[1] == CHANNEL_TYPE_PLAYER:
                inbuf = initial[channel[0]][0]
                inbuf -= self._seqChannels
                inbuf += self._channels
                b = self._buffer[inbuf][2]
                player = [s.player(b), 0, None, None, None, None, None, None, None, None, 0]
                self._update_player(player, initial[channel[0]])
                player[1] = 0
                self._localChannels.append(player)
            elif channel[1] == CHANNEL_TYPE_FILTER:
                filterbuf = initial[channel[0]][4]
                filterbuf -= self._seqChannels
                filterbuf += self._channels
                b = self._buffer[filterbuf][2]
                flt = [s.filter(b, b.size), 0, None, None, None, None, None, None, 0]
                self._update_filter(flt, initial[channel[0]])
                flt[1] = 0
                self._localChannels.append(flt)
        init = None
        try:
            init = self._tag['init']
        except KeyError:
            pass
        if init != None:
            self._seq.set_pattern(init)
            self.run(-1)
        self._loaded = True
        s.print_full_stats()

    def _unload(self):
        if not self._loaded:
            raise Exception("Already not loaded")
        del self._localChannels
        self._buffer = self._buffer[self._channels:]
        for buffer in self._buffer:
            if not isinstance(buffer[0], cg.Buffer):
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
        self._ended = False

    def _run_channels(self, time, line):
        # for performance and simplicity reasons, this is evaluating whole
        # channels at a time.  Alternatively, it would look to each channel
        # for the next event then run all channels up to that event in repeat
        # but that could allow for things to be done in very slow ways which
        # result in a lot of very close together events.  I'm not looking to
        # make a full DAW, but rather a simple tracker, so don't do it that way
        i = 0
        for channel in self._localChannels:
            if isinstance(channel[0], cg.Player):
                if line != None and line[i] != None:
                    self._update_player(channel, line[i])
                while time > 0:
                    get = time
                    if channel[1] < get:
                        get = channel[1]
                    got = channel[0].run(get)
                    if got == 0:
                        reason = channel[0].stop_reason()
                        changed = False
                        if reason | cg.SYNTH_STOPPED_OUTBUFFER:
                            if channel[3] != None:
                                self._update_player(channel, channel[3])
                                changed = True
                        if reason | cg.SYNTH_STOPPED_INBUFFER:
                            if channel[4] != None:
                                self._update_player(channel, channel[4])
                                changed = True
                        if reason | cg.SYNTH_STOPPED_VOLBUFFER:
                            if channel[5] != None:
                                self._update_player(channel, channel[5])
                                changed = True
                        if reason | cg.SYNTH_STOPPED_SPEEDBUFFER:
                            if channel[6] != None:
                                self._update_player(channel, channel[6])
                                changed = True
                        if reason | cg.SYNTH_STOPPED_PHASEBUFFER:
                            if channel[7] != None:
                                self._update_player(channel, channel[7])
                                changed = True
                        if not changed:
                            if channel[1] == 0 and channel[2] != None:
                                self._update_player(channel, channel[2])
                            else:
                                channel[1] = 0
                                channel[10] += time
                                bufsize = channel[9][2].size
                                if channel[10] >= bufsize:
                                    channel[10] = bufsize
                                    channel[0].output_pos(bufsize - 1)
                                else:
                                    channel[0].output_pos(channel[10])
                                break
                    time -= got
                    channel[1] -= got
                    channel[10] += got
            elif isinstance(channel[0], cg.Filter):
                if line != None and line[i] != None:
                    self._update_filter(channel, line[i])
                while time > 0:
                    get = time
                    if channel[1] < get:
                        get = channel[1]
                    got = channel[0].run(get)
                    if got == 0:
                        reason = channel[0].stop_reason()
                        changed = False
                        if reason | cg.SYNTH_STOPPED_OUTBUFFER:
                            if channel[3] != None:
                                self._update_filter(channel, channel[3])
                                changed = True
                        if reason | cg.SYNTH_STOPPED_INBUFFER:
                            if channel[4] != None:
                                self._update_filter(channel, channel[4])
                                changed = True
                        if reason | cg.SYNTH_STOPPED_VOLBUFFER:
                            if channel[5] != None:
                                self._update_filter(channel, channel[5])
                                changed = True
                        if reason | cg.SYNTH_STOPPED_SLICEBUFFER:
                            if channel[6] != None:
                                self._update_filter(channel, channel[6])
                                changed = True
                        if not changed:
                            if channel[1] == 0 and channel[2] != None:
                                self._update_filter(channel, channel[2])
                            else:
                                channel[1] = 0
                                channel[8] += time
                                bufsize = channel[7][2].size
                                if channel[8] >= bufsize:
                                    channel[8] = bufsize
                                    channel[0].output_pos(bufsize - 1)
                                else:
                                    channel[0].output_pos(channel[8])
                                break
                    time -= got
                    channel[1] -= got
                    channel[8] += got
            else: # silence
                if line != None and line[i] != None:
                    self._update_silence(channel, line[i])
                    if channel[2] > 0:
                        channel[0].silence(channel[1], channel[2])
                        channel[2] = 0
            i += 1

    def run(self, needed):
        if self._ended:
            return

        if needed < 0:
            timepassed = 0
            while True:
                line = None
                time = 0
                try:
                    # try run for some absurd amount of time
                    time, line = self._seq.advance(2 ** 31)
                except seq.SequenceEnded:
                    break
                self._run_channels(time, line)
                timepassed += time
            return timepassed

        while needed > 0:
            try:
                time, line = self._seq.advance(int(needed / self._samplesms))
            except seq.SequenceEnded:
                self._ended = True
                break
            time *= self._samplesms
            self._run_channels(time, line)
            needed -= time
            if needed < self._samplesms:
                self._run_channels(needed, None)
                break

    def _reset_output_positions(self):
        for channel in self._localChannels:
            if isinstance(channel[0], cg.Player):
                # reset output channel positions to 0
                if channel[9][0] == None:
                    channel[0].output_pos(0)
                    channel[10] = 0
            elif isinstance(channel[0], cg.Filter):
                # reset output channel positions to 0
                if channel[9][0] == None:
                    channel[0].output_pos(0)
                    channel[7] = 0


@cg.SYNTH_FRAME_CB_T
def audio_system_frame(priv, s):
    return priv[1]._frame_cb()

class AudioSystem():
    def __init__(self, log_cb_return, log_cb_priv, rate, channels):
        self._s = cg.Synth(audio_system_frame, self,
                           log_cb_return, log_cb_priv,
                           rate, channels)
        self._sequences = list()
        self._samplesms = int(self._s.rate / 1000)
        self._fragment_size = self._s.fragment_size
        self._fragments = 0
        self._inc_fragments()

    def _inc_fragments(self):
        self._s.enabled(0)
        self._fragments += 1
        self._s.fragments(self._fragments)

    def _frame_cb(self):
        try:
            if self._s.underrun:
                self._inc_fragments()
                self._s.enabled(1)
                # s.enabled() will eventually call this function again so when it
                # finally returns back to here, just return again
                return 0
            needed = self._s.needed

            if needed > 0:
                self._reset_output_positions()
                for seq in self._sequences:
                    if not seq[1]:
                        continue
                    seq[0].run(needed)

            return 0
        except cg.CrustyException as e:
            # catch crusty exceptions since they'll have already printed error
            # output, then pass it down along the stack so the main loop can
            # try to do the right thing.
            # Let all other python errors fall through so their meaningful
            # messages can be properly displayed
            return -1

    def add_sequence(self, seq, enabled=False):
        seq._load(self._s)
        self._sequences.append([seq, enabled])

    def del_sequence(self, seq):
        for item in enumerate(self._sequences):
            if item[1][0] == seq:
                item[1][0]._unload()
                del self._sequences[item[0]]
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

    def frame(self):
        self._s.frame()

    def _reset_output_positions(self):
        for seq in self._sequences:
            if seq[1]:
                seq[0]._reset_output_positions()
