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

def _driver_key(info):
    info = info[1]
    # everything else is in between
    priority = 2
    if bytes(info.name) == b'metal' or \
       bytes(info.name) == b'direct3d11':
        # prefer platform-specific APIs
        priority = 0
    elif bytes(info.name).startswith(b'opengles'):
        # prefer opengl es over opengl because it has complete support for the
        # uncrustygame features
        priority = 1
    elif info.flags & SDL_RENDERER_SOFTWARE:
        # software will be very slow so don't prefer it, but it should display
        # _mostly_ OK
        priority = 9998

    found_32bit_alpha = 0
    for i in range(info.num_texture_formats):
        if SDL_BITSPERPIXEL(info.texture_formats[i]) == 32 and \
           SDL_ISPIXELFORMAT_ALPHA(info.texture_formats[i]):
               found_32bit_alpha = 1
               break

    if found_32bit_alpha == 0:
        # if something is missing the necessary formats, it's very unpreferable
        # because there's little to no chance anything will display properly
        priority = 9999

    return priority

def initialize_video(title :str,
                     width :int, height :int,
                     winflags :int, rendererflags :int) \
                     -> (SDL_Window, SDL_Renderer, int):
    """
    Initialize video in a way that as far as I can tell is the best, preferred 
    method to get the best functionality out of pycrustygame.

    title, width, height and winflags are simply passed on to SDL_CreateWindow
    rendererflags is passed on to SDL_CreateRenderer
    returns window, renderer and prefered pixel format or raises RuntimeError if
    no window or renderer could be created
    """
    driver = list()
    pixfmt = SDL_PIXELFORMAT_UNKNOWN
    drivers = SDL_GetNumRenderDrivers()

    for i in range(drivers):
        d = SDL_RendererInfo()
        if SDL_GetRenderDriverInfo(i, d) < 0:
            raise RuntimeError("Couldn't get video renderer info for {}".format(i))
        driver.append((i, d))

    driver = sorted(driver, key=_driver_key)

    window = SDL_CreateWindow(title.encode("utf-8"), SDL_WINDOWPOS_UNDEFINED, SDL_WINDOWPOS_UNDEFINED, width, height, winflags)
    if window == None:
        raise RuntimeError("Couldn't create SDL window.")

    renderer = None
    for d in driver:
        renderer = SDL_CreateRenderer(window, d[0], rendererflags)
        # if initialization failed, continue down the priority list
        if renderer == None:
            continue

        pixfmt = SDL_PIXELFORMAT_UNKNOWN
        # find the most prefered format
        for i in range(d[1].num_texture_formats):
            if SDL_BITSPERPIXEL(d[1].texture_formats[i]) == 32 and \
               SDL_ISPIXELFORMAT_ALPHA(d[1].texture_formats[i]):
                pixfmt = d[1].texture_formats[i]
                break

        # otherwise, try to find something with the most color depth, although
        # it's pretty likely to just fail.
        if pixfmt == SDL_PIXELFORMAT_UNKNOWN:
            maxbpp = 0
            for i in range(d[1].num_texture_formats):
                if SDL_BITSPERPIXEL(d[1].texture_formats[i]) > maxbpp:
                    maxbpp = SDL_BITSPERPIXEL(d[1].texture_formats[i])
                    pixfmt = d[1].texture_formats[i]

        print("Picked {} renderer".format(d[1].name.decode("utf-8")))
        break

    if renderer == None:
        SDL_DestroyWindow(window)
        raise RuntimeError("Couldn't initialze any SDL video device.")

    return window, renderer, pixfmt


def clear_frame(ll, r, g, b):
    if SDL_SetRenderDrawColor(ll.renderer, r, g, b, SDL_ALPHA_OPAQUE) < 0:
        raise(Exception())
    if SDL_RenderClear(ll.renderer) < 0:
        raise(Exception())
    if SDL_SetRenderDrawColor(ll.renderer, 0, 0, 0, SDL_ALPHA_TRANSPARENT) < 0:
        raise(Exception())

def make_color(r, g, b, a):
    return((int(r) << cg.TILEMAP_RSHIFT) |
           (int(g) << cg.TILEMAP_GSHIFT) |
           (int(b) << cg.TILEMAP_BSHIFT) |
           (int(a) << cg.TILEMAP_ASHIFT))

def color_from_rad(rad, cmin, cmax):
    if rad >= 0 and rad < (numpy.pi * 2 / 6):
        rad = (rad * (1 / (numpy.pi * 2 / 6)) * (cmax - cmin)) + cmin
        return make_color(cmax, rad, cmin, 255)
    elif rad >= (numpy.pi * 2 / 6) and rad < (numpy.pi * 2 / 6 * 2):
        rad = cmax - ((rad - (numpy.pi * 2 / 6)) * (1 / (numpy.pi * 2 / 6)) * (cmax - cmin))
        return make_color(rad, cmax, cmin, 255)
    elif rad >= (numpy.pi * 2 / 6 * 2) and rad < (numpy.pi * 2 / 6 * 3):
        rad = ((rad - (numpy.pi * 2 / 6 * 2)) * (1 / (numpy.pi * 2 / 6)) * (cmax - cmin)) + cmin
        return make_color(cmin, cmax, rad, 255)
    elif rad >= (numpy.pi * 2 / 6 * 3) and rad < (numpy.pi * 2 / 6 * 4):
        rad = cmax - ((rad - (numpy.pi * 2 / 6 * 3)) * (1 / (numpy.pi * 2 / 6)) * (cmax - cmin))
        return make_color(cmin, rad, cmax, 255)
    elif rad >= (numpy.pi * 2 / 6 * 4) and rad < (numpy.pi * 2 / 6 * 5):
        rad = ((rad - (numpy.pi * 2 / 6 * 4)) * (1 / (numpy.pi * 2 / 6)) * (cmax - cmin)) + cmin
        return make_color(rad, cmin, cmax, 255)

    rad = cmax - ((rad - (numpy.pi * 2 / 6 * 5)) * (1 / (numpy.pi * 2 / 6)) * (cmax - cmin))
    return make_color(cmax, cmin, rad, 255)

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

def make_filter(rate):
    filt = None
    fileexists = False

    filename = "{}t{}b{}fd{}d{}mtw{}twd{}r.npy".format(FILTER_TAPS, BASE_FREQ, FILTERS_PER_DECADE, DECADES, MIN_TRANS_WIDTH, TRANS_WIDTH_DIV, rate)

    try:
        filt = numpy.load(filename, allow_pickle=False)
        fileexists = True
        print("Filters loaded from file.")
    except IOError as e:
        pass

    if filt is None:
        print("Generating filters...")
        try:
            filt = numpy.zeros(SLICES * FILTER_TAPS // 2, numpy.float32)
            maxval = DECADES * FILTERS_PER_DECADE
            for dec in range(DECADES):
                for i in range(FILTERS_PER_DECADE):
                    mul = (10 ** dec) + (((10 ** (dec + 1)) - (10 ** dec)) ** (i / FILTERS_PER_DECADE)) - 1.0
                    freq = BASE_FREQ * mul
                    transwidth = (((mul - 1) / TRANS_WIDTH_DIV) + 1) * MIN_TRANS_WIDTH
                    pos = (dec * FILTERS_PER_DECADE * FILTER_TAPS // 2) + (i * FILTER_TAPS // 2)
                    filt[pos:pos + (FILTER_TAPS // 2)] = \
                        signal.remez(FILTER_TAPS,
                                     [0, freq, freq + transwidth, rate / 2],
                                     [1, 0], fs=rate)[FILTER_TAPS//2:]
                    print("{} / {}".format(dec * FILTERS_PER_DECADE + i + 1, maxval), end='\r')
        except Exception as e:
            raise e
        finally:
            print()

    if not fileexists:
        print("Saving filter to file...")
        try:
            numpy.save(filename, filt, allow_pickle=False)
        except IOError:
            print("Saving failed.")

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
                          rate)
    benddownslope = aud.buffer(cg.SYNTH_TYPE_F32,
                               array.array('f', create_sqrt_slope(1.0, 0.5, rate)),
                               rate)
    bendupslope = aud.buffer(cg.SYNTH_TYPE_F32,
                             array.array('f', create_sqrt_slope(1.0, 2.0, rate)),
                             rate)
    noise = aud.buffer(cg.SYNTH_TYPE_F32,
                       array.array('f', create_random_noise(-1.0, 1.0, rate)),
                       rate)

    filt = make_filter(rate)
    filt = aud.buffer(cg.SYNTH_TYPE_F32, filt, len(filt))

    wave = WaveGen(rate)
    sine = aud.buffer(cg.SYNTH_TYPE_F32, wave.sine(440), rate)
    square = aud.buffer(cg.SYNTH_TYPE_F32, wave.square(harmonics, 440), rate)
    triangle = aud.buffer(cg.SYNTH_TYPE_F32, wave.triangle(harmonics, 440), rate)
    saw = aud.buffer(cg.SYNTH_TYPE_F32, wave.sawtooth(harmonics, 440), rate)

    return envslope, benddownslope, bendupslope, noise, filt, sine, square, triangle, saw


def log_cb_return(priv, string):
    print(string, end='')

def main():
    try:
        seqname = argv[1]
    except IndexError:
        seqname = DEFAULT_SEQ

    SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO)
    window, renderer, pixfmt = initialize_video("asdf", 640, 480, SDL_WINDOW_SHOWN, SDL_RENDERER_PRESENTVSYNC | SDL_RENDERER_TARGETTEXTURE)
    sdlfmt = SDL_AllocFormat(pixfmt)
    sdl_red = SDL_MapRGBA(sdlfmt, 255, 0, 0, 255)
    sdl_green = SDL_MapRGBA(sdlfmt, 0, 255, 0, 255)
    sdl_blue = SDL_MapRGBA(sdlfmt, 0, 0, 255, 255)
    red = make_color(255, 31, 31, 255)
    green = make_color(31, 255, 31, 255)
    blue = make_color(127, 127, 255, 255)
    transparent_rg = SDL_MapRGBA(sdlfmt, 255, 255, 63, 191)
    ll = cg.LayerList(renderer, pixfmt, log_cb_return, None)

    if ll.renderer != renderer:
        print("Got different renderer back from layerlist")

    ts1 = cg.Tileset(ll, 32, 32, sdl_blue, 16, 16)
    ts2 = cg.Tileset(ll, "cdemo/font.bmp", 8, 8)
    surface = SDL_CreateRGBSurfaceWithFormat(0, 64, 64, 32, pixfmt)
    ts3 = cg.Tileset(ll, surface, 64, 64)
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

    tm1 = cg.Tilemap(ll, ts1, 4, 4)
    tm1.tileset(ts2)
    SDL_RenderPresent(renderer)

    del tm1
    del ts3
    del ts2
    del ts1

    ts1 = ll.Tileset("cdemo/font.bmp", 8, 8)
    tm1 = ll.Tilemap(ts1, 8, 8)
    tm1.map(2, 2, 5, 5, 2, array.array('u', "oediV DVD "))
    tm1.attr_flags(2, 2, 0, 5, 2, array.array('I', (cg.TILEMAP_ROTATE_180, cg.TILEMAP_ROTATE_180, cg.TILEMAP_ROTATE_180, cg.TILEMAP_ROTATE_180, cg.TILEMAP_ROTATE_180)))
    tm1.attr_colormod(2, 2, 4, 5, 2, array.array('I', (red, green, blue, red, green, blue, red, green, blue, red)))
    tm1.update(0, 0, 8, 8)
    l1 = cg.Layer(ll, tm1);
    l1.window(40, 16)
    l1.scroll_pos(16, 16)
    l1.rotation_center(20, 8)
    l1.rotation(180)
    l1.colormod(transparent_rg)
    l1.blendmode(cg.TILEMAP_BLENDMODE_ADD)
    ts2 = ll.Tileset(64, 64, sdl_blue, 64, 64)
    tm2 = ts2.Tilemap(1, 1)
    l2 = tm2.Layer()
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

    aud = audio.AudioSystem(log_cb_return, None, 48000, 2, True)
    audbuffers = load_audio(aud, WAVEFORM_HARMONICS)
    aud.enabled(True)

    wavout = False
    seq = None
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
                seq = None
            _, exc = aud.error
            print_tb(exc.__traceback__)
            print(exc)
            aud.enabled(True)

        if seq != None:
            for s in seq:
                if s.ended:
                    aud.del_sequence(s)
                    seq.remove(s)
                    print("Sequence ended")
            if len(seq) == 0:
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
                        seq = None
                    macros = (("FILTER_SIZE", (), str(FILTER_TAPS//2)),
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
                elif event.key.keysym.sym == SDLK_s:
                    if seq != None:
                        for s in seq:
                            aud.del_sequence(s)
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
        l1.colormod(color_from_rad(colorrad, 0, 255))

        clear_frame(ll, 32, 128, 192)
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
        seq = None

    SDL_DestroyRenderer(renderer)
    SDL_DestroyWindow(window)
    SDL_Quit()


if __name__ == "__main__":
    main()
