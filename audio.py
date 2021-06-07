import array
import pycrustygame as cg
import sequencer as seq

_DEFAULT_TUNING = 440

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

    def __init__(file, macros):
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
            line = self._file.readline()
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
                    newLine += replacement
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
    def __init__(self, infile, buffers=None):
        """
        Create an audio sequence from a file.

        buffers is a list of either float arrays or other external Buffer objects.
        """
        if infile.readline() != "CrustyTracker":
            raise Exception("File isn't a CrustyTracker sequence.")
        self._version = int(infile.readline())
        if self._version != 1:
            raise Exception("Unsupported version: {}".format(version))
        macros = int(infile.readline())
        self._macro = list()
        # read a list of macros, macros are formatted:
        # name arg0name arg1name ...=replacement
        # macro names are found in the file and replaced with replacement
        # and instances of argument names are replaced with the arguments
        # provided when the macro is used like:
        # name arg0 arg1 ...
        for i in range(macros):
            line = infile.readline().split('#', maxsplit=1)
            if len(line[0]) == 0:
                continue
            macroline = line[0].split('=', maxsplit=1)
            lhs = macroline[0].split()
            macroname = lhs[0]
            macroargs = lhs[1:]
            self._macro.append(macroname, macroargs, macroline[1])
        infile = MacroReader(infile, macros)
        tags = int(infile.readline())
        self._tag = dict()
        for i in range(tags):
            line = infile.readline().split('#', maxsplit=1)
            if len(line[0]) == 0:
                continue
            tagline = line.split('=', maxsplit=1)
            self._tag[tagline[0]] = tagline[1]
        self._tune()
        buffers = int(infile.readline())
        self._buffer = list()
        # populated on _load(), None when unloaded, map sequence's buffers
        # to crustygame synth's buffers
        self._bufferInfo = None
        inbuf = 0
        for i in range(buffers):
            line = infile.readline().split('#', maxsplit=1)
            if len(line[0]) == 0:
                continue
            bufferline = line.split(maxsplit=1)
            # line is either a filename and middle A frequency or
            # a length in milliseconds and middle A frequency or
            # just a middle A frequency for a buffer to be provided
            item = None
            freq = None
            rate = None
            freq = int(bufferline[0])
            # allow starting the second arg with a # to explicitly indicate a
            # comment
            if len(bufferline) > 1 and bufferline[1][0] != '#':
                # single value means the buffer will be provided
                try:
                    # add the time in milliseconds of an empty buffer
                    item = int(bufferline[1].split('#', maxsplit=1)[0])
                except ValueError:
                    # add the string to use as a filename later
                    item = bufferline[1].split('#', maxsplit=1)[0].strip()
            else:
                rate = buffers[inbuf][1]
                if isinstance(buffer[inbuf], seq.Buffer):
                    # import an external buffer
                    item = buffers[inbuf][0]
                elif isinstance(buffer[inbuf], array.array) and \
                     buffer[inbuf].typecode != 'f':
                    # convert to a ctypes array so _load() can just pass it
                    # along
                    item = _create_float_array(buffers[inbuf][0])
                    inbuf += 1
                else:
                    raise Exception("Buffers must be float arrays or external Buffers.")
            self._buffer.append((item, rate, freq))
        channels = int(infile.readline())
        self._channel = list()
        for i in range(channels):
            channel = infile.readline().split('#', maxsplit=1).strip().lower()
            if channel == CHANNEL_TYPE_SILENCE:
                self._channel.append(CHANNEL_TYPE_SILENCE)
            if channel == CHANNEL_TYPE_PLAYER:
                self._channel.append(CHANNEL_TYPE_PLAYER)
            elif channel == CHANNEL_TYPE_FILTER:
                self._channel.append(CHANNEL_TYPE_FILTER)
            else:
                raise Exception("Invalid channel type: {}".format(channel))
        seqDesc = seq.SequenceDescription()
        silenceDesc = seqDesc.add_row_description()
        # output buffer
        seqDesc.add_field(silenceDesc, seq.FIELD_TYPE_INT)
        # start
        seqDesc.add_field(silenceDesc, seq.FIELD_TYPE_INT)
        # length
        seqDesc.add_field(silenceDesc, seq.FIELD_TYPE_INT)
        playerDesc = seqDesc.add_row_description()
        # input buffer
        seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
        # input buffer pos
        seqDesc.add_field(playerDesc, seq.FIELD_TYPE_FLOAT)
        # output buffer
        seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
        # output buffer pos
        seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
        # output mode
        seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
        # volume
        seqDesc.add_field(playerDesc, seq.FIELD_TYPE_FLOAT)
        # volume source
        seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
        # volume mode
        seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
        # speed (frequency, /speed, note)
        seqDesc.add_field(playerDesc, seq.FIELD_TYPE_STR)
        # speed source
        seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
        # speed mode
        seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
        # phase source
        seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
        # loop start
        seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
        # loop end
        seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
        # player mode
        seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
        # run length
        seqDesc.add_field(playerDesc, seq.FIELD_TYPE_INT)
        # stopped requested
        seqDesc.add_field(playerDesc, seq.FIELD_TYPE_ROW, rowDesc=playerDesc)
        # stopped outbuffer
        seqDesc.add_field(playerDesc, seq.FIELD_TYPE_ROW, rowDesc=playerDesc)
        # stopped inbuffer
        seqDesc.add_field(playerDesc, seq.FIELD_TYPE_ROW, rowDesc=playerDesc)
        # stopped volbuffer
        seqDesc.add_field(playerDesc, seq.FIELD_TYPE_ROW, rowDesc=playerDesc)
        # stopped speedbuffer
        seqDesc.add_field(playerDesc, seq.FIELD_TYPE_ROW, rowDesc=playerDesc)
        # stopped phasebuffer
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

    def __del__(self):
        self._unload()

    def _tune(self):
        tuning = None
        try:
            tuning = self._tag['tuning'].split()
        except KeyError:
            self._freqs = [_DEFAULT_TUNING * (2 ** (x / 12)) for x in range(12)]
            return

        if len(tuning) == 1:
            tuning = float(tuning[0])
            self._freqs = [tuning * (2 ** (x / 12)) for x in range(12)]
        elif len(tuning) == 12:
            self._freqs = [float(x) for x in tuning]
        else:
            raise Exception("'tuning' tag must be middle A or all 12 middle octave notes.")

    def _get_speed(self, speed, tuning, inrate, outrate):
        # literal speed
        if speed[0] == '/':
            return float(speed[1:])
        freq = 0
        # frequency
        try:
            freq = float(speed)
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
            freq = self._freqs[note]
            if octave < 4:
                freq /= 5 - octave
            elif octave > 4:
                freq *= octave - 3

        return (freq / tuning) * (outrate / inrate)

    def update_buffer(self, index, item, rate):
        if isinstance(item, seq.Buffer):
            # import an external buffer
            self._buffer[index] = item
            self._bufferRates[index] = rate
            if self._bufferMaps != None:
                del self._bufferMaps[index]
                self._bufferMaps[index] = item
        elif isinstance(buffer[inbuf], array.array) and \
             buffer[inbuf].typecode != 'f':
            # convert to a ctypes array so _load() can just pass it
            # along
            self._buffer[index] = _create_float_array(buffers[inbuf])
            self._bufferRates[index] = rate
            if self._bufferMaps != None:
                del self._bufferMaps[index]
                self._bufferMaps[index] = item
        else:
            raise Exception("Buffers must be float arrays.")

    def _update_silence(self, silence, status):
        if status[0] != None:
            b = self._bufferInfo[status[0]][0]
            silence[0] = b
        if status[1] != None:
            silence[1] = status[1]
        if status[2] != None:
            silence[2] = status[2]

    def _update_player(self, player, status):
        p = player[0]
        if status[0] != None:
            b = self._bufferInfo[status[0]][0]
            p.input_buffer(b)
        if status[1] != None:
            p.input_pos(status[1])
        if status[2] != None:
            b = self._bufferInfo[status[2]][0]
            p.output_buffer(b)
        if status[3] != None:
            p.output_pos(status[3])
        if status[4] != None:
            p.output_mode(status[4])
        if status[5] != None:
            p.volume(status[5])
        if status[6] != None:
            b = self._bufferInfo[status[6]][0]
            p.output_buffer(b)
        if status[7] != None:
            p.volume_mode(status[7])
        if status[8] != None:
            p.speed(status[8])
        if status[9] != None:
            b = self._bufferInfo[status[9]][0]
            p.output_buffer(b)
        if status[10] != None:
            p.speed_mode(status[10])
        if status[11] != None:
            b = self._bufferInfo[status[11]][0]
            p.output_buffer(b)
        if status[12] != None:
            p.loop_start(status[12])
        if status[13] != None:
            p.loop_end(status[13])
        if status[14] != None:
            p.player_mode(status[14])
        if status[15] != None:
            player[1] = status[15]
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
            b = self._bufferInfo[status[0]][0]
            f.input_buffer(b)
        if status[1] != None:
            f.input_pos(status[1])
        if status[2] != None:
            b = self._bufferInfo[status[2]][0]
            f.output_buffer(b)
        if status[3] != None:
            f.output_pos(status[3])
        if status[4] != None:
            b = self._bufferInfo[status[4]][0]
            f.filter_buffer(b)
        if status[5] != None:
            f.filter_start(status[5])
        if status[6] != None:
            f.slices(status[6])
        if status[7] != None:
            f.slice(status[7])
        if status[8] != None:
            b = self._bufferInfo[status[8]][0]
            f.slice_source(b)
        if status[9] != None:
            f.mode(status[9])
        if status[10] != None:
            f.output_mode(status[10])
        if status[11] != None:
            f.volume(status[11])
        if status[12] != None:
            b = self._bufferInfo[status[12]][0]
            f.volume_source(b)
        if status[13] != None:
            f.volume_mode(status[13])
        if status[14] != None:
            flt[1] = status[14]
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
        self._rate = s.rate
        self._channels = s.channels
        self._bufferInfo = [(b, self._rate) for b in s.output_buffers()]
        self._localBuffers = list()
        for buffer in self._buffer:
            if isinstance(buffer[0], int):
                # silent buffer
                length = self._rate * buffer[0] / 1000
                b = s.buffer(seq.SYNTH_TYPE_F32, None, length)
                self._bufferInfo.append((b, self._rate))
                self._localBuffers.append(b)
            elif isinstance(buffer[0], str):
                # filename
                b, r = s.buffer_from_wav(buffer[0])
                self._bufferInfo.append((b, r))
                self._localBuffers.append(b)
            elif isinstance(buffer[0], seq.Buffer):
                # external buffer
                self._bufferInfo.append((buffer[0], buffer[1]))
            else:
                # already a ctypes array
                b = s.buffer(seq.SYNTH_TYPE_F32, buffer[0], len(buffer[0]))
                self._bufferInfo.append((b, buffer[1]))
                self._localBuffers.append(b)
        initial = self._seq.advance(0)
        self._localChannels = list()
        for channel in enumerate(self._channel):
            if channel[1] == CHANNEL_TYPE_SILENCE:
                silence = [self._bufferInfo[initial[channel[0]][0]],
                           initial[channel[0]][1],
                           initial[channel[0]][2]]
                silence[2] = 0
                self._localChannels.append(silence)
            elif channel[1] == CHANNEL_TYPE_PLAYER:
                b = self._bufferInfo[initial[channel[0]][0]][0]
                player = [s.player(b), 0, None, None, None, None, None, None]
                self._update_player(player, initial[channel[0]])
                player[1] = 0
                self._localChannels.append(player)
            elif channel[1] == CHANNEL_TYPE_FILTER:
                b = self._bufferInfo[initial[channel[0]][4]][0]
                flt = [s.filter(b, b.size), 0, None, None, None, None, None]
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

    def _unload(self, s):
        self._bufferInfo = None
        # delete channels and filters which may refer to buffers first.
        if isinstance(channel[0], (cg.Player, cg.Filter)):
            del channel[0]
        self._localChannels = None
        for buffer in self._localBuffers:
            del buffer
        self._localBuffers = None 

    def reset(self):
        """
        Reset everything, frees all buffers and reloads them fresh, so they're
        in a known state.
        """
        self._unload()
        self._seq.reset()
        self._load()

    def fast_reset(self):
        """
        Faster reset that just resets the sequence, and should have no
        consequences if the buffers haven't been touched.
        """
        self._seq.reset()

    def _run_channels(self, line, time):
        # for performance and simplicity reasons, this is evaluating whole
        # channels at a time.  Alternatively, it would look to each channel
        # for the next event then run all channels up to that event in repeat
        # but that could allow for things to be done in very slow ways which
        # result in a lot of very close together events.  I'm not looking to
        # make a full DAW, but rather a simple tracker, so don't do it that way
        for channel in enumerate(self._localChannels):
            if isinstance(channel[1][0], cg.Player):
                p = channel[1][0]
                if line != None:
                    self._update_player(channel[1], line[channel[0]])
                while time > 0:
                    curtime = time
                    if channel[1][1] < curtime:
                        curtime = channel[1][1]
                        channel[1][1] = 0
                        time -= curtime
                    else:
                        channel[1][1] -= curtime
                        time -= channel[1][1]
                    while curtime > 0:
                        got = p.run(curtime)
                        if got < curtime:
                            reason = p.stop_reason()
                            if reason | cg.SYNTH_STOPPED_OUTBUFFER:
                                self._update_player(channel[1], channel[1][3])
                            if reason | cg.SYNTH_STOPPED_INBUFFER:
                                self._update_player(channel[1], channel[1][4])
                            if reason | cg.SYNTH_STOPPED_VOLBUFFER:
                                self._update_player(channel[1], channel[1][5])
                            if reason | cg.SYNTH_STOPPED_SPEEDBUFFER:
                                self._update_player(channel[1], channel[1][6])
                            if reason | cg.SYNTH_STOPPED_PHASEBUFFER:
                                self._update_player(channel[1], channel[1][7])
                            curtime -= got
                    if channel[1][1] == 0:
                        self._update_player(channel[1], channel[1][2])
            if isinstance(channel[1][0], cg.Filter):
                f = channel[1][0]
                if line != None:
                    self._update_filter(channel[1], line[channel[0]])
                while time > 0:
                    curtime = time
                    if channel[1][1] < curtime:
                        curtime = channel[1][1]
                        channel[1][1] = 0
                        time -= curtime
                    else:
                        channel[1][1] -= curtime
                        time -= channel[1][1]
                    while curtime > 0:
                        got = p.run(curtime)
                        if got < curtime:
                            reason = f.stop_reason()
                            if reason | cg.SYNTH_STOPPED_OUTBUFFER:
                                self._update_filter(channel[1], channel[1][3])
                            if reason | cg.SYNTH_STOPPED_INBUFFER:
                                self._update_filter(channel[1], channel[1][4])
                            if reason | cg.SYNTH_STOPPED_VOLBUFFER:
                                self._update_filter(channel[1], channel[1][5])
                            if reason | cg.SYNTH_STOPPED_SLICEBUFFER:
                                self._update_filter(channel[1], channel[1][6])
                    if channel[1][1] == 0:
                        self._update_filter(channel[1], channel[1][2])
            else: # silence
                self._update_silence(channel[1], line[channel[0]])
                if channel[1][2] > 0:
                    channel[1][0].silence(channel[1][1], channel[1][2])
                    channel[1][2] = 0

    def run(self, needed):
        if needed < 0:
            timepassed = 0
            while True:
                line = None
                time = 0
                try:
                    # try run for some absurd amount of time
                    line, time = self._seq.advance(2 ** 31)
                except seq.SequenceEnded:
                    break
                self._run_channels(line, time)
                timepassed += time
            return timepassed

        remain = needed
        while remain > 0:
            try:
                line, time = self._seq.advance(remain)
            except seq.SequenceEnded:
                break
            self._run_channels(line, time)
            remain -= time

        return needed - remain


@cg.SYNTH_FRAME_CB_T
def audio_system_frame(s, priv):
    return(priv.value._frame_cb())

class AudioSystem():
    def __init__(self, log_cb_return, log_cb_priv):
        self._s = Synth(audio_system_frame, self,
                        log_cb_return, log_cb_priv)
        self._fragment_size = self._s.fragment_size
        self._fragments = 0
        self._inc_fragments()
        self._sequences = list()

    def __del__(self):
        for seq in self._sequences:
            seq._unload(self._s)

    def _inc_fragments(self):
        self._s.enabled(0)
        self._fragments += 1
        self._s.fragments(self._fragments)

    def _frame_cb(self):
        try:
            if self._s.underrun:
                self._s.inc_fragments()
                self._s.enabled(1)
                # s.enabled() will eventually call this function again so when it
                # finally returns back to here, just return again
                return 0
            needed = self._s.needed

            for seq in self._sequences:
                if not seq[1]:
                    continue
                gotzero = 0
                while needed > 0:
                    got = seq[0].run(needed)
                    if got < needed:
                        seq[3] += 1
                        if seq[2]:
                            if got == 0:
                                if gotzero == 1:
                                    print("WARNING: looping sequence returned 0 consecutively")
                                    break
                                gotzero = 1
                            else:
                                gotzero = 0
                            seq[0].fast_reset()
                            needed -= got
                        else:
                            break

            return 0
        except CrustyException as e:
            # catch crusty exceptions since they'll have already printed error
            # output, then pass it down along the stack so the main loop can
            # try to do the right thing.
            # Let all other python errors fall through so their meaningful
            # messages can be properly displayed
            return -1

    def add_sequence(self, seq, enabled=True, looping=False):
        seq._load(self._s)
        self._sequences.append([seq, enabled, looping, 0])

    def del_sequence(self, seq):
        try:
            self._sequences.remove(seq)
            seq._unload(self._s)
        except ValueError as e:
            print("WARNING: Attempt to remove nonexistent sequence.")

    def sequence_enabled(self, seq, enabled):
        index = self._sequences.index(seq)
        if enabled:
            self._sequences[index][1] = True
        else:
            self._sequences[index][1] = False

    def enabled(self, enabled):
        self._s.enabled(enabled)

    def frame(self):
        for seq in self._sequences:
            seq[3] = 0
        self._s.frame()

    def ended(self, seq):
        index = self._sequences.index(seq)
        return self._sequences[index][2]
