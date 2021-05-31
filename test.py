#!/usr/bin/env python3

import time
import array
from ctypes import *
from sdl2 import *
import pycrustygame as cg
import sequencer as seq

# making this thing work in some useful way has been CBT so just yeah
@cg.LOG_CB_RETURN_T
def log_cb_return(priv: py_object, string :c_char_p):
    print(string.decode("utf-8"))

def clear_frame(ll, r, g, b):
    if SDL_SetRenderDrawColor(ll.renderer, r, g, b, SDL_ALPHA_OPAQUE) < 0:
        raise(Exception())
    if SDL_RenderClear(ll.renderer) < 0:
        raise(Exception())
    if SDL_SetRenderDrawColor(ll.renderer, 0, 0, 0, SDL_ALPHA_TRANSPARENT) < 0:
        raise(Exception())

# this is probably bad but whichever
def string_to_ints(string):
    array = list()

    for item in string:
        encoded = item.encode("utf-32")
        array.append(encoded[4] +
                     (encoded[5] * 0x100) +
                     (encoded[6] * 0x10000) +
                     (encoded[7] * 0x1000000))

    return(array)

CHANNEL_TYPE_SILENCE = "silence"
CHANNEL_TYPE_PLAYER = "player"
CHANNEL_TYPE_FILTER = "filter"

def _create_float_array(iterable):
    aType = c_float * len(iterable)
    a = aType()

    for item in enumerate(iterable):
        a[item[0]] = item[1]

    return(a)

class AudioSequencer():
    def __init__(self, filename, buffers = None):
        self._looping = False
        with open(filename, "r") as infile:
            if infile.readline() != "CrustyTracker":
                raise Exception("File isn't a CrustyTracker sequence.")
            self._version = int(infile.readline())
            if self._version != 1:
                raise Exception("Unsupported version: {}".format(version))
            tags = int(infile.readline())
            self._tag = dict()
            for i in range(tags):
                tagline = infile.readline().split('=', maxsplit=1)
                self._tag[tagline[0]] = tagline[1]
            buffers = int(infile.readline())
            self._buffer = list()
            # first buffer is output
            self._buffer.append(None)
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
                    if not isinstance(buffer[inbuf], array.array) or \
                       buffer[inbuf].typecode != 'f':
                        raise Exception("Buffers must be float arrays.")
                    # convert to a ctypes array so _load() can just pass it
                    # along
                    item = _create_float_array(buffers[inbuf])
                    inbuf += 1
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
            # balance (only for output)
            seqDesc.add_field(playerDesc, seq.FIELD_TYPE_FLOAT)
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

    def _load(self, s):
        self._bufferMaps = list()
        for buffer in self._buffer:
            if buffer == None:
                # output
                self._bufferMaps.append(None)
            elif isinstance(buffer[0], int):
                # silent buffer
                length = s.rate * buffer[0] / 1000
                self._bufferMaps.append(s.buffer(seq.SYNTH_TYPE_F32, None, length))
            elif isinstance(buffer[0], str):
                # filename
                self._bufferMaps.append(s.buffer_from_wav(buffer[0]))
            else:
                # already a ctypes array
                self._bufferMaps.append(buffer[0])

    def _unload(self, s):
        for buffer in self._bufferMaps:
            if buffer == None:
                continue
            else:
                del buffer
        self._bufferMaps = None

    def reset(self):
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
    def __init__(self):
        self._s = Synth(audio_system_frame, self,
                        log_cb_return, None)
        self._rate = self._s.rate
        self._channels = self._s.channels
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


def main():
    window, renderer, pixfmt = cg.initialize_video("asdf", 640, 480, SDL_WINDOW_SHOWN, SDL_RENDERER_PRESENTVSYNC)
    red = cg.tilemap_color(255, 0, 0, 255)
    green = cg.tilemap_color(0, 255, 0, 255)
    blue = cg.tilemap_color(0, 0, 255, 255)

    ll = cg.Layerlist(renderer, pixfmt, log_cb_return, window)
    ts = ll.tileset_from_bmp("cdemo/font.bmp", 8, 8)
    tm = ll.tilemap(ts, 8, 8)
    tm.map(2, 2, 4, 4, 3, string_to_ints("tseta sisiht"))
    tm.attr_flags(2, 2, 0, 4, 3, (cg.TILEMAP_ROTATE_180, cg.TILEMAP_ROTATE_180, cg.TILEMAP_ROTATE_180, cg.TILEMAP_ROTATE_180))
    tm.attr_colormod(2, 2, 4, 4, 3, (red, green, blue, red, green, blue, red, green, blue, red, green, blue))
    tm.update(0, 0, 8, 8)
    l = ll.layer(tm)
    l.pos(200, 200)
    l.window(32, 24)
    l.scroll_pos(16, 16)
    l.scale(4.0, 4.0)
    l.rotation_center(32, 24)
    l.rotation(180)
    l.colormod(cg.tilemap_color(255, 255, 64, 192))
    l.blendmode(cg.TILEMAP_BLENDMODE_ADD) 

    seqdesc = seq.SequenceDescription()
    rowdesc = seqdesc.add_row_description()
    seqdesc.add_field(rowdesc, seq.FIELD_TYPE_INT)
    seqdesc.add_field(rowdesc, seq.FIELD_TYPE_INT)
    seqdesc.add_field(rowdesc, seq.FIELD_TYPE_FLOAT)
    seqdesc.add_field(rowdesc, seq.FIELD_TYPE_HEX)
    seqdesc.add_field(rowdesc, seq.FIELD_TYPE_STR)
    seqdesc.add_column(rowdesc)
    rowdesc2 = seqdesc.add_row_description()
    seqdesc.add_field(rowdesc2, seq.FIELD_TYPE_INT)
    seqdesc.add_field(rowdesc2, seq.FIELD_TYPE_FLOAT)
    seqdesc.add_field(rowdesc2, seq.FIELD_TYPE_ROW, rowDesc=rowdesc)
    seqdesc.add_column(rowdesc2)
    with open("testseq.txt", "r") as seqfile:
        sequence = seq.Sequencer(seqdesc, seqfile)
    sequence.write_file()

    running = 1
    lastTime = time.monotonic()
    while running:
        event = SDL_Event()

        while SDL_PollEvent(event):
            if event.type == SDL_QUIT:
                running = 0
                break

        clear_frame(ll, 32, 128, 192)
        l.draw()

        thisTime = time.monotonic()
        try:
            timeMS = int((thisTime - lastTime) * 1000)
            while timeMS > 0:
                seqTime, seqLine = sequence.advance(timeMS)
                print(timeMS, end=' ')
                print(seqTime, end=' ')
                print(repr(seqLine))
                timeMS -= seqTime
        except seq.SequenceEnded as e:
            sequence.reset()

        lastTime = thisTime
        SDL_RenderPresent(renderer)

    SDL_DestroyRenderer(renderer)
    SDL_DestroyWindow(window)


if __name__ == "__main__":
    main()
