from sdl2 import *
import crustygame as cg
import array
import time
import random
from itertools import islice, count, repeat
import sequencer as seq
import audio
from traceback import print_tb
from sys import argv
import numpy
from scipy import signal
import display

DEFAULT_SEQ = "test3.crustysequence"
DEFAULT_WAV = "output.wav"

FILTER_TAPS = 1024
BASE_FREQ = 20
FILTERS_PER_DECADE = 100
DECADES = 3
SLICES = FILTERS_PER_DECADE * DECADES
MIN_TRANS_WIDTH = 80
TRANS_WIDTH_DIV = 500

WAVEFORM_HARMONICS = 8

def color_from_rad(rad, cmin, cmax):
    if rad >= 0 and rad < (numpy.pi * 2 / 6):
        rad = (rad * (1 / (numpy.pi * 2 / 6)) * (cmax - cmin)) + cmin
        return cmax, rad, cmin
    elif rad >= (numpy.pi * 2 / 6) and rad < (numpy.pi * 2 / 6 * 2):
        rad = cmax - ((rad - (numpy.pi * 2 / 6)) * (1 / (numpy.pi * 2 / 6)) * (cmax - cmin))
        return rad, cmax, cmin
    elif rad >= (numpy.pi * 2 / 6 * 2) and rad < (numpy.pi * 2 / 6 * 3):
        rad = ((rad - (numpy.pi * 2 / 6 * 2)) * (1 / (numpy.pi * 2 / 6)) * (cmax - cmin)) + cmin
        return cmin, cmax, rad
    elif rad >= (numpy.pi * 2 / 6 * 3) and rad < (numpy.pi * 2 / 6 * 4):
        rad = cmax - ((rad - (numpy.pi * 2 / 6 * 3)) * (1 / (numpy.pi * 2 / 6)) * (cmax - cmin))
        return cmin, rad, cmax
    elif rad >= (numpy.pi * 2 / 6 * 4) and rad < (numpy.pi * 2 / 6 * 5):
        rad = ((rad - (numpy.pi * 2 / 6 * 4)) * (1 / (numpy.pi * 2 / 6)) * (cmax - cmin)) + cmin
        return rad, cmin, cmax

    rad = cmax - ((rad - (numpy.pi * 2 / 6 * 5)) * (1 / (numpy.pi * 2 / 6)) * (cmax - cmin))
    return cmax, cmin, rad

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

def create_linear_slope(start, end, num):
    step = (end - start) / (num - 1)
    slope = array.array('f', islice(count(start, step), num))
    return(slope)

class LogSlope():
    def __init__(self, start, end, num):
        self._num = num
        self._start = start
        self._range = end - start
        self._val = 0
        self._step = 1.0 / num

    def __len__(self):
        return self._num

    def __iter__(self):
        return self

    def __next__(self):
        val = numpy.sqrt(self._val * self._step)
        if self._val == self._num:
            raise StopIteration()
        self._val += 1
        return self._start + (val * self._range)

def create_sqrt_slope(start, end, num):
    slope = array.array('f', LogSlope(start, end, num))
    return(slope)

class RandomNoise():
    def __init__(self, low, high, num):
        self._low = low
        self._high = high
        self._num = num
        self._val = 0

    def __len__(self):
        return self._num

    def __iter__(self):
        return self

    def __next__(self):
        self._val += 1
        if self._val > self._num:
            raise StopIteration()
        return random.uniform(self._low, self._high)

def create_random_noise(low, high, num):
    noise = array.array('f', RandomNoise(low, high, num))
    return(noise)

def make_filter(rate, lowpass):
    filt = None
#    fileexists = False

#    filename = "{}t{}b{}fd{}d{}mtw{}twd{}r.npy".format(FILTER_TAPS, BASE_FREQ, FILTERS_PER_DECADE, DECADES, MIN_TRANS_WIDTH, TRANS_WIDTH_DIV, rate)

#    try:
#        filt = numpy.load(filename, allow_pickle=False)
#        fileexists = True
#        print("Filters loaded from file.")
#    except IOError as e:
#        pass

    if filt is None:
        try:
            filt = numpy.zeros(SLICES * FILTER_TAPS, numpy.float32)
            maxval = DECADES * FILTERS_PER_DECADE
            for dec in range(DECADES):
                for i in range(FILTERS_PER_DECADE):
                    mul = (10 ** dec) + (((10 ** (dec + 1)) - (10 ** dec)) ** (i / FILTERS_PER_DECADE)) - 1.0
                    freq = BASE_FREQ * mul
                    transwidth = (((mul - 1) / TRANS_WIDTH_DIV) + 1) * MIN_TRANS_WIDTH
                    pos = (dec * FILTERS_PER_DECADE * FILTER_TAPS) + (i * FILTER_TAPS)
#                    filt[pos:pos + FILTER_TAPS] = \
#                        signal.remez(FILTER_TAPS,
#                                     [0, freq, freq + transwidth, rate / 2],
#                                     [1, 0], fs=rate)
                    if lowpass:
                        filt[pos:pos + FILTER_TAPS] = \
                             signal.firwin(FILTER_TAPS, freq,
                                           pass_zero=lowpass, fs=rate)
                    else:
                        filt[pos:pos + FILTER_TAPS] = \
                             signal.firwin(FILTER_TAPS, (freq, rate/2-1),
                                           pass_zero=lowpass, fs=rate)
                    print("{} / {}".format(dec * FILTERS_PER_DECADE + i + 1, maxval), end='\r')
        except Exception as e:
            raise e
        finally:
            print()

#    if not fileexists:
#        print("Saving filter to file...")
#        try:
#            numpy.save(filename, filt, allow_pickle=False)
#        except IOError:
#            print("Saving failed.")

    return(filt)

class WaveGen():
    def __init__(self, rate):
        self._rate = rate
        self._harmonics = {}

    def gen(self, harmonics):
        wave = numpy.zeros(self._rate, dtype=numpy.float32)

        for h in harmonics:
            # try to cache results for reuse
            if h[0] not in self._harmonics:
                maxpt = numpy.pi * 2 * h[0]
                points = numpy.arange(0, maxpt, maxpt / self._rate)
                self._harmonics[h[0]] = numpy.sin(points, dtype=numpy.float32)

            split = int(self._rate * h[2])
            remain = self._rate - split
            wave[:split] += self._harmonics[h[0]][remain:] * h[1]
            wave[split:] += self._harmonics[h[0]][:remain] * h[1]

        return wave

    def sine(self, freq):
        return(self.gen(((freq, 1.0, 0.0),)))

    # information for these was found at:
    # <https://pages.uoregon.edu/emi/9.php>
    # but it's well-known stuff.
    def square(self, harmonics, freq):
        # odd harmonics
        # each 1/harmonic in amplitude
        # all in phase
        return self.gen(zip([x * freq for x in range(1, harmonics * 2 + 1, 2)],
                            [1 / x for x in range(1, harmonics * 2 + 1, 2)],
                            [0 for x in range(harmonics)]))

    def triangle(self, harmonics, freq):
        # odd harmonics
        # each 1/(harmonic ** 2) in amplitude
        # every other harmonic is out of phase
        return self.gen(zip([x * freq for x in range(1, harmonics * 2 + 1, 2)],
                            [1 / (x ** 2) for x in range(1, harmonics * 2 + 1, 2)],
                            [(x % 2) * 0.5 for x in range(harmonics)]))

    def sawtooth(self, harmonics, freq):
        # all harmonics
        # each 1/harmonic in amplitude
        # odd harmonics are 180 deg out of phase
        return self.gen(zip([x * freq for x in range(1, harmonics + 1)],
                            [1 / x for x in range(1, harmonics + 1)],
                            [(x % 2) * 0.5 for x in range(harmonics)]))

def load_audio(aud, harmonics):
    rate = aud.rate
    envslope = aud.buffer(cg.SYNTH_TYPE_F32,
                          array.array('f', create_sqrt_slope(0.0, 1.0, rate)),
                          rate, "EnvSlope")
    benddownslope = aud.buffer(cg.SYNTH_TYPE_F32,
                               array.array('f', create_sqrt_slope(1.0, 0.5, rate)),
                               rate, "BendDownSlope")
    bendupslope = aud.buffer(cg.SYNTH_TYPE_F32,
                             array.array('f', create_sqrt_slope(1.0, 2.0, rate)),
                             rate, "BendUpSlope")
    noise = aud.buffer(cg.SYNTH_TYPE_F32,
                       array.array('f', create_random_noise(-1.0, 1.0, rate)),
                       rate, "Noise")

    print("Generating filters...")
    filt = make_filter(rate, lowpass=True)
    lpfilt = aud.buffer(cg.SYNTH_TYPE_F32, filt, len(filt), "Lowpass Filters")
    filt = make_filter(rate, lowpass=False)
    hpfilt = aud.buffer(cg.SYNTH_TYPE_F32, filt, len(filt), "Highpass Filters")

    wave = WaveGen(rate)
    sine = aud.buffer(cg.SYNTH_TYPE_F32, wave.sine(440), rate, "Sine")
    square = aud.buffer(cg.SYNTH_TYPE_F32, wave.square(harmonics, 440), rate, "Square")
    triangle = aud.buffer(cg.SYNTH_TYPE_F32, wave.triangle(harmonics, 440), rate, "Triangle")
    saw = aud.buffer(cg.SYNTH_TYPE_F32, wave.sawtooth(harmonics, 440), rate, "Saw")

    return envslope, benddownslope, bendupslope, noise, lpfilt, hpfilt, sine, square, triangle, saw

class Scope():
    def __init__(self, renderer, seq, num, pixfmt, w, h):
        self._renderer = renderer
        self._seq = seq
        self._num = num
        self._w = w
        self._h = h
        self._array = numpy.zeros(shape=w * 2, dtype=numpy.float32)
        self._array[:w*2:2] = numpy.arange(0, w)
        self._tex = SDL_CreateTexture(renderer, pixfmt, SDL_TEXTUREACCESS_STATIC | SDL_TEXTUREACCESS_TARGET, w, h)
        if SDL_SetTextureBlendMode(self._tex, SDL_BLENDMODE_BLEND) < 0:
            raise Exception("Couldn't set scope texture blend mode.")

    @property
    def texture(self):
        return self._tex

    def _get_buffers(self):
        # keep this as short as possible so the audio device is unlocked as
        # soon as possible
        first = numpy.copy(self._seq.internal(self._num))
        second = numpy.copy(self._seq.internal(self._num))

        return first, second

    def update(self):
        first, second = self._get_buffers()

        if len(first) < self._w and len(first) != 0:
            pos = len(first) * 2 + 1
            self._array[1:pos:2] = first
            if len(second) != 0:
                if len(first) + len(second) < self._w:
                    pos2 = pos + len(first) * 2
                    self._array[pos:pos2:2] = second
                    self._array[pos2::2].fill(0)
                else:
                    self._array[pos::2] = second[:self._w - len(first)]
        else:
            if len(first) != 0:
                self._array[1:self._w*2:2] = first[:self._w]

        self._array[1::2] *= self._h / 2
        self._array[1::2] += self._h / 2

        origtarget = SDL_GetRenderTarget(self._renderer)
        if SDL_SetRenderTarget(self._renderer, self._tex) < 0:
            raise Exception("Failed to set render target")
        if SDL_SetRenderDrawColor(self._renderer, 0, 0, 0, SDL_ALPHA_TRANSPARENT) < 0:
            raise Exception()
        if SDL_RenderClear(self._renderer) < 0:
            raise Exception()
        if SDL_SetRenderDrawColor(self._renderer, 255, 255, 255, SDL_ALPHA_OPAQUE) < 0:
            raise Exception()
        # call crustygame version
        cg.SDL_RenderDrawLinesF(self._renderer, self._array)
        if SDL_SetRenderTarget(self._renderer, origtarget) < 0:
            raise Exception("Failed to restore render target")


def log_cb_return(priv, string):
    print(string, end='')

def do_main(window, renderer, pixfmt):
    try:
        seqname = argv[1]
    except IndexError:
        seqname = DEFAULT_SEQ

    sdlfmt = SDL_AllocFormat(pixfmt)
    sdl_red = SDL_MapRGBA(sdlfmt, 255, 0, 0, 255)
    sdl_green = SDL_MapRGBA(sdlfmt, 0, 255, 0, 255)
    sdl_blue = SDL_MapRGBA(sdlfmt, 0, 0, 255, 255)
    red = display.make_color(255, 31, 31, 255)
    green = display.make_color(31, 255, 31, 255)
    blue = display.make_color(127, 127, 255, 255)
    transparent_rg = SDL_MapRGBA(sdlfmt, 255, 255, 63, 191)
    ll = cg.LayerList(renderer, pixfmt, log_cb_return, None)

    if ll.renderer != renderer:
        print("Got different renderer back from layerlist")

    ts1 = cg.Tileset(ll, 32, 32, sdl_blue, 16, 16, "Blue")
    ts2 = cg.Tileset(ll, "cdemo/font.bmp", 8, 8, None)
    surface = SDL_CreateRGBSurfaceWithFormat(0, 64, 64, 32, pixfmt)
    ts3 = cg.Tileset(ll, surface, 64, 64, "Square")
    SDL_FreeSurface(surface)

    try:
        ll.target_tileset(window)
        print("set_target_tileset didn't raise TypeError as expected")
    except TypeError:
        pass

    try:
        ll.target_tileset(0)
        print("set_target_tileset didn't raise TypeError as expected")
    except TypeError:
        pass

    ll.target_tileset(ts1);
    ll.target_tileset(ts2);
    ll.target_tileset(ts3);
    ll.target_tileset(None);

    try:
        ll.default_render_target(window)
        print("set_default_render_target didn't raise TypeError as expected")
    except TypeError:
        pass

    tm1 = cg.Tilemap(ll, ts1, 4, 4, "Test 2")
    tm1.tileset(ts2, "Test 2")
    SDL_RenderPresent(renderer)

    del tm1
    del ts3
    del ts2
    del ts1

    ts1 = ll.tileset("cdemo/font.bmp", 8, 8, None)
    tm1 = ll.tilemap(ts1, 8, 8, "DVD Video")
    tm1.map(2, 2, 5, 5, 2, array.array('u', "oediV DVD "))
    tm1.attr_flags(2, 2, 0, 5, 2, array.array('I', (cg.TILEMAP_ROTATE_180, cg.TILEMAP_ROTATE_180, cg.TILEMAP_ROTATE_180, cg.TILEMAP_ROTATE_180, cg.TILEMAP_ROTATE_180)))
    tm1.attr_colormod(2, 2, 4, 5, 2, array.array('I', (red, green, blue, red, green, blue, red, green, blue, red)))
    tm1.update(0, 0, 8, 8)
    l1 = cg.Layer(ll, tm1, "DVD Video");
    l1.window(40, 16)
    l1.scroll_pos(16, 16)
    l1.rotation_center(20, 8)
    l1.rotation(180)
    l1.colormod(transparent_rg)
    l1.blendmode(cg.TILEMAP_BLENDMODE_ADD)
    ts2 = ll.tileset(64, 64, sdl_blue, 64, 64, "Blue Box")
    tm2 = ts2.tilemap(1, 1, "Blue Box")
    l2 = tm2.layer("Blue Box")
    l2.scale(4.0, 4.0)

    random.seed(None)

    x = 0.0
    y = 0.0
    x2 = -20.0
    y2 = -8.0
    xspeed = random.uniform(0.0, 480.0)
    yspeed = random.uniform(0.0, 480.0)
    x2speed = random.uniform(0.0, 64.0)
    y2speed = random.uniform(0.0, 64.0)
    blendmode = cg.TILEMAP_BLENDMODE_ADD
    colorrad = 0.0
    colorrad2 = 0.25

    osc1 = SDL_CreateTexture(renderer, pixfmt, SDL_TEXTUREACCESS_STATIC | SDL_TEXTUREACCESS_TARGET, 320, 240)
    display.clear(ll, osc1, 0, 0, 0, SDL_ALPHA_OPAQUE)
    osc1l = cg.Layer(ll, osc1, "OSC 1 Layer")
    osc1l.pos(-20, -20)
    osc1l.scale((320 + (20 * 2)) / 320, (240 + (20 * 2)) / 240)
    osc1l.rotation(5)
    osc1l.rotation_center(160, 120)
    osc2 = SDL_CreateTexture(renderer, pixfmt, SDL_TEXTUREACCESS_STATIC | SDL_TEXTUREACCESS_TARGET, 320, 240)
    display.clear(ll, osc2, 0, 0, 0, SDL_ALPHA_OPAQUE)
    osc2l = cg.Layer(ll, osc2, "OSC 2 Layer")

    scene = display.DisplayList(ll, display.SCREEN)
    osc1dl = display.DisplayList(ll, osc2)
    osc1dl.append(osc1l)
    osc2dl = display.DisplayList(ll, osc1)
    osc2dl.append(osc2l)
    scopelid = osc2dl.append(None)
    scoperid = osc2dl.append(None)
    scene.append(display.make_color(32, 128, 192, SDL_ALPHA_OPAQUE))
    scene.append(lambda: osc2l.scale(1.0, 1.0))
    scene.append(osc1dl)
    scene.append(osc2dl)
    scene.append(lambda: osc2l.scale(2.0, 2.0))
    scene.append(osc2l)

    #aud = audio.AudioSystem(log_cb_return, None, 48000, 2, trace=True)
    aud = audio.AudioSystem(log_cb_return, None, 48000, 2, trace=False)
    audbuffers = load_audio(aud, WAVEFORM_HARMONICS)
    aud.enabled(True)

    wavout = False
    seq = None
    scopell = None
    scoperl = None
    scopel = None
    scoper = None
    running = True
    playing = True
    lastTime = time.monotonic()
    while running:
        thisTime = time.monotonic()
        timetaken = thisTime - lastTime

        try:
            aud.frame()
        except Exception as e:
            print("Sequence raised error")
            aud.print_full_stats()
            if seq != None:
                for s in seq:
                    aud.del_sequence(s)
                osc2dl.replace(scopelid, None)
                osc2dl.replace(scoperid, None)
                scopell = None
                scoperl = None
                scopel = None
                scoper = None
                seq = None
            _, exc = aud.error
            print_tb(exc.__traceback__)
            print(exc)
            aud.enabled(True)

        if scopel != None:
            # possible race condition between this and aud.frame() but it'll
            # just result in missed samples, no big deal
            scopel.update()
            scoper.update()

        if seq != None:
            for s in seq:
                if s.ended:
                    aud.del_sequence(s)
                    seq.remove(s)
                    print("Sequence ended")
            if len(seq) == 0:
                osc2dl.replace(scopelid, None)
                osc2dl.replace(scoperid, None)
                scopell = None
                scoperl = None
                scopel = None
                scoper = None
                seq = None

        event = SDL_Event()

        while SDL_PollEvent(event):
            if event.type == SDL_QUIT:
                running = False
                break
            elif event.type == SDL_KEYDOWN:
                if event.key.keysym.sym == SDLK_q:
                    running = False
                elif event.key.keysym.sym == SDLK_p:
                    if seq != None:
                        for s in seq:
                            aud.del_sequence(s)
                        scopell = None
                        scoperl = None
                        scopel = None
                        scoper = None
                        seq = None
                    macros = (("FILTER_SIZE", (), str(FILTER_TAPS)),
                              ("FILTER_SLICES", (), str(SLICES)))
                    # load first sequence
                    seq = []
                    try:
                        with open(seqname, "r") as seqfile:
                            seq.append(audio.AudioSequencer(seqfile,
                                       audbuffers, macros, trace=True))
                    except Exception as e:
                        aud.print_full_stats()
                        print_tb(e.__traceback__)
                        print(e)
                        seq = None
                    # if it didn't fail, try to see if there are more parts
                    if seq != None:
                        parts = ()
                        try:
                            parts = seq[0].get_tag('part-files').split(';')
                        except KeyError:
                            pass
                        if len(parts) > 0:
                            # try loading all the parts
                            for part in parts:
                                try:
                                    with open(part, "r") as seqfile:
                                        seq.append(audio.AudioSequencer(seqfile,
                                                   [envslope, benddownslope, bendupslope, noise, filt],
                                                   macros, trace=True))
                                except Exception as e:
                                    aud.print_full_stats()
                                    print_tb(e.__traceback__)
                                    print(e) 
                                    seq = None
                                    break
                    # if loading all the parts succeeds, try adding them
                    # all to the audio context
                    if seq != None:
                        for s in seq:
                            try:
                                aud.add_sequence(s, enabled=True)
                            except Exception as e:
                                print("Adding sequences failed, ignore warnings about attempt to remove.")
                                for s in seq:
                                    aud.del_sequence(s)
                                aud.print_full_stats()
                                print_tb(e.__traceback__)
                                print(e)
                                seq = None
                                break
                    if seq != None:
                        scopel = Scope(renderer, seq[0], 0, pixfmt, 320, 120)
                        scopell = cg.Layer(ll, scopel.texture, "Scope L Layer")
                        scopell.pos(0, 30)
                        osc2dl.replace(scopelid, scopell)
                        scoper = Scope(renderer, seq[0], 1, pixfmt, 320, 120)
                        scoperl = cg.Layer(ll, scoper.texture, "Scope R Layer")
                        scoperl.pos(0, 90)
                        osc2dl.replace(scoperid, scoperl)

                elif event.key.keysym.sym == SDLK_s:
                    if seq != None:
                        for s in seq:
                            aud.del_sequence(s)
                        osc2dl.replace(scopelid, None)
                        osc2dl.replace(scoperid, None)
                        scopell = None
                        scoperl = None
                        scopel = None
                        scoper = None
                        seq = None
                elif event.key.keysym.sym == SDLK_r:
                    aud.enabled(True)
                elif event.key.keysym.sym == SDLK_n:
                    aud.enabled(False)
                elif event.key.keysym.sym == SDLK_i:
                    aud.print_full_stats()
                elif event.key.keysym.sym == SDLK_w:
                    if wavout:
                        aud.close_wav()
                        wavout = False
                    else:
                        aud.open_wav("output.wav")
                        wavout = True

        x = x + (xspeed * timetaken)
        if x > (640 - (64 * 4.0)):
            xspeed = random.uniform(-480.0, 0.0)
            if yspeed > 0.0:
                yspeed = random.uniform(0.0, 480.0)
            else:
                yspeed = random.uniform(-480.0, 0.0)
            x = 640 - (64 * 4.0)
        elif x < 0:
            xspeed = random.uniform(0.0, 480.0)
            if yspeed > 0.0:
                yspeed = random.uniform(0.0, 480.0)
            else:
                yspeed = random.uniform(-480.0, 0.0)
            x = 0

        y = y + (yspeed * timetaken)
        if y > (480 - (64 * 4.0)):
            y = 480 - (64 * 4.0)
            yspeed = random.uniform(-480.0, 0.0)
            if xspeed > 0.0:
                xspeed = random.uniform(0.0, 480.0)
            else:
                xspeed = random.uniform(-480.0, 0.0)
            y = 480 - (64 * 4.0)
        elif y < 0:
            yspeed = random.uniform(0.0, 480.0)
            if xspeed > 0.0:
                xspeed = random.uniform(0.0, 480.0)
            else:
                xspeed = random.uniform(-480.0, 0.0)
            y = 0

        x2 = x2 + (x2speed * timetaken)
        if x2 > 64 - 20:
            x2speed = random.uniform(-64.0, 0.0)
            if y2speed > 0.0:
                y2speed = random.uniform(0.0, 64.0)
            else:
                y2speed = random.uniform(-64.0, 0.0)
            x2 = 64 - 20
            if blendmode == cg.TILEMAP_BLENDMODE_ADD:
                blendmode = cg.TILEMAP_BLENDMODE_SUB
            else:
                blendmode = cg.TILEMAP_BLENDMODE_ADD
            l1.blendmode(blendmode)
        elif x2 < -20:
            x2speed = random.uniform(0.0, 64.0)
            if y2speed > 0.0:
                y2speed = random.uniform(0.0, 64.0)
            else:
                y2speed = random.uniform(-64.0, 0.0)
            x2 = -20
            if blendmode == cg.TILEMAP_BLENDMODE_ADD:
                blendmode = cg.TILEMAP_BLENDMODE_SUB
            else:
                blendmode = cg.TILEMAP_BLENDMODE_ADD
            l1.blendmode(blendmode)

        y2 = y2 + (y2speed * timetaken)
        if y2 > 64 - 8:
            y2speed = random.uniform(-64.0, 0.0)
            if x2speed > 0.0:
                x2speed = random.uniform(0.0, 64.0)
            else:
                x2speed = random.uniform(-64.0, 0.0)
            y2 = 64 - 8
            if blendmode == cg.TILEMAP_BLENDMODE_ADD:
                blendmode = cg.TILEMAP_BLENDMODE_SUB
            else:
                blendmode = cg.TILEMAP_BLENDMODE_ADD
            l1.blendmode(blendmode)
        elif y2 < -8:
            y2speed = random.uniform(0.0, 64.0)
            if x2speed > 0.0:
                x2speed = random.uniform(0.0, 64.0)
            else:
                x2speed = random.uniform(-64.0, 0.0)
            y2 = -8
            if blendmode == cg.TILEMAP_BLENDMODE_ADD:
                blendmode = cg.TILEMAP_BLENDMODE_SUB
            else:
                blendmode = cg.TILEMAP_BLENDMODE_ADD
            l1.blendmode(blendmode)

        if xspeed == 0.0 and yspeed == 0.0:
            xspeed = random.uniform(-480.0, 480.0)
            yspeed = random.uniform(-480.0, 480.0)

        if x2speed == 0.0 and y2speed == 0.0:
            x2speed = random.uniform(-64.0, 64.0)
            y2speed = random.uniform(-64.0, 64.0)

        colorrad = colorrad + (numpy.pi * timetaken)
        if colorrad >= numpy.pi * 2:
            colorrad = colorrad - (numpy.pi * 2)
        colorrad2 = colorrad2 + (numpy.pi * timetaken)
        if colorrad2 >= numpy.pi * 2:
            colorrad2 = colorrad2 - (numpy.pi * 2)
        modr, modg, modb = color_from_rad(colorrad, 0, 255)
        l1.colormod(display.make_color(modr, modg, modb, 255))

        if scopell != None:
            modr, modg, modb = color_from_rad(colorrad, 0, 250)
            scopell.colormod(display.make_color(modr, modg, modb, SDL_ALPHA_OPAQUE))
            modr, modg, modb = color_from_rad(colorrad2, 0, 250)
            scoperl.colormod(display.make_color(modr, modg, modb, SDL_ALPHA_OPAQUE))

        scene.draw(display.SCREEN)

        l1.pos(int(x2), int(y2))
        l2.pos(int(x), int(y))
        ll.target_tileset(ts2)
        l1.draw()
        ll.target_tileset(None)
        tm2.update(0, 0, 1, 1)
        l2.draw()
        SDL_RenderPresent(renderer)

        lastTime = thisTime

    aud.enabled(False)
    if seq != None:
        for s in seq:
            aud.del_sequence(s)
        osc2dl.replace(scopelid, None)
        osc2dl.replace(scoperid, None)
        scopell = None
        scoperl = None
        scopel= None
        scoper= None
        seq = None

def main():
    SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO)
    window, renderer, pixfmt = display.initialize_video("asdf", 640, 480, SDL_WINDOW_SHOWN, SDL_RENDERER_PRESENTVSYNC | SDL_RENDERER_TARGETTEXTURE)

    do_main(window, renderer, pixfmt)

    SDL_DestroyRenderer(renderer)
    SDL_DestroyWindow(window)
    SDL_Quit()


if __name__ == "__main__":
    main()
