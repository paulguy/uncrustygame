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
    def __init__(self, infile, buffers=None, looping=False):
        """
        Create an audio sequence from a file.
        """
        self._looping = looping
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
            macroline = infile.readline().split('=', maxsplit=1)
            lhs = macroline[0].split()
            macroname = lhs[0]
            macroargs = lhs[1:]
            self._macro.append(macroname, macroargs, macroline[1])
        infile = MacroReader(infile, macros)
        tags = int(infile.readline())
        self._tag = dict()
        for i in range(tags):
            tagline = infile.readline().split('=', maxsplit=1)
            self._tag[tagline[0]] = tagline[1]
        buffers = int(infile.readline())
        self._buffer = list()
        # populated on _load(), None when unloaded, map sequence's buffers
        # to crustygame synth's buffers
        self._bufferMaps = None
        inbuf = 0
        for i in range(buffers):
            bufferline = infile.readline().rsplit(maxsplit=1)
            # line is either a filename and middle A frequency or
            # a length in milliseconds and middle A frequency
            item = None
            # single value means the buffer will be provided
            if len(bufferline) > 1:
                try:
                    # add the time in milliseconds of an empty buffer
                    item = int(bufferline[0])
                except ValueError:
                    # add the string to use as a filename later
                    item = bufferline[0]
            else:
                if isinstance(buffer[inbuf], seq.Buffer):
                    # import an external buffer
                    item = buffer[inbuf]
                elif isinstance(buffer[inbuf], array.array) and \
                     buffer[inbuf].typecode != 'f':
                    # convert to a ctypes array so _load() can just pass it
                    # along
                    item = _create_float_array(buffers[inbuf])
                    inbuf += 1
                else:
                    raise Exception("Buffers must be float arrays or external Buffers.")
            self._buffer.append((item, int(bufferline[1])))
        channels = int(infile.readline())
        self._channel = list()
        for i in range(channels):
            channel = infile.readline().lower()
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
        # speed
        seqDesc.add_field(playerDesc, seq.FIELD_TYPE_FLOAT)
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
        filterDesc = seqDesc.add_row_description()
        # TODO: filter rows
        for channel in self._channel:
            if channel == CHANNEL_TYPE_SILENCE:
                seqDesc.add_column(silenceDesc)
            elif channel == CHANNEL_TYPE_PLAYER:
                seqDesc.add_column(playerDesc)
            elif channel == CHANNEL_TYPE_FILTER:
                seqDesc.add_column(filterDesc)
        self._seq = seq.Sequencer(seqDesc, infile)

    def update_buffer(self, index, item):
        if isinstance(item, seq.Buffer):
            # import an external buffer
            self._buffer[index] = item
            if self._bufferMaps != None:
                del self._bufferMaps[index]
                self._bufferMaps[index] = item
        elif not isinstance(buffer[inbuf], array.array) or \
           buffer[inbuf].typecode != 'f':
            raise Exception("Buffers must be float arrays.")
        else:
            # convert to a ctypes array so _load() can just pass it
            # along
            self._buffer[index] = _create_float_array(buffers[inbuf])
            if self._bufferMaps != None:
                del self._bufferMaps[index]
                self._bufferMaps[index] = item

    def _load(self, s):
        self._rate = s.rate
        self._channels = s.channels
        self._bufferMaps = [b for b in self.s.get_channel_buffers()]
        for buffer in self._buffer:
            if isinstance(buffer[0], int):
                # silent buffer
                length = s.rate * buffer[0] / 1000
                self._bufferMaps.append(s.buffer(seq.SYNTH_TYPE_F32, None, length))
            elif isinstance(buffer[0], str):
                # filename
                self._bufferMaps.append(s.buffer_from_wav(buffer[0]))
            elif isinstance(buffer[0], seq.Buffer):
                # external buffer
                self._bufferMaps.append(buffer[0])
            else:
                # already a ctypes array
                self._bufferMaps.append(s.buffer(seq.SYNTH_TYPE_F32, buffer[0], len(buffer[0])))

    def _unload(self, s):
        for buffer in self._bufferMaps:
            if buffer == None:
                continue
            else:
                del buffer
        self._bufferMaps = None

    def reset(self):
        """
        Reset everything, frees all buffers and reloads them fresh, so they're
        in a known state.
        """
        self._unload()
        self._load()
        self._seq.reset()

    def fast_reset(self):
        """
        Faster reset that just resets the sequence, and should have no
        consequences if the buffers haven't been touched.
        """
        self._seq.reset()

    def looping(self):
        self._looping = True

    def not_looping(self):
        self._looping = False

    def run(self, needed):
        pass


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
                seq.run(needed)

            return 0
        except CrustyException as e:
            # catch crusty exceptions since they'll have already printed error
            # output, then pass it down along the stack so the main loop can
            # try to do the right thing.
            # Let all other python errors fall through so their meaningful
            # messages can be properly displayed
            return -1

    def add_sequence(self, seq):
        seq._load(self._s)
        self._sequences.append(seq)
        self._s.enabled(1)

    def del_sequence(self, seq):
        try:
            self._sequences.remove(seq)
            seq._unload(self._s)
        except ValueError as e:
            print("WARNING: Attempt to remove nonexistent sequence.")

    def frame(self):
        self._s.frame()
