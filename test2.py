from sdl2 import *
import crustygame as cg
import array
import time
import random
import math
from itertools import islice, count, repeat
import sequencer as seq
import audio
from traceback import print_tb
from sys import argv

DEFAULT_SEQ = "test3.crustysequence"
START = 40
SLICES = 2000

TWOPI = 2.0 * math.pi

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
    if rad >= 0 and rad < (math.pi * 2 / 6):
        rad = (rad * (1 / (math.pi * 2 / 6)) * (cmax - cmin)) + cmin
        return make_color(cmax, rad, cmin, 255)
    elif rad >= (math.pi * 2 / 6) and rad < (math.pi * 2 / 6 * 2):
        rad = cmax - ((rad - (math.pi * 2 / 6)) * (1 / (math.pi * 2 / 6)) * (cmax - cmin))
        return make_color(rad, cmax, cmin, 255)
    elif rad >= (math.pi * 2 / 6 * 2) and rad < (math.pi * 2 / 6 * 3):
        rad = ((rad - (math.pi * 2 / 6 * 2)) * (1 / (math.pi * 2 / 6)) * (cmax - cmin)) + cmin
        return make_color(cmin, cmax, rad, 255)
    elif rad >= (math.pi * 2 / 6 * 3) and rad < (math.pi * 2 / 6 * 4):
        rad = cmax - ((rad - (math.pi * 2 / 6 * 3)) * (1 / (math.pi * 2 / 6)) * (cmax - cmin))
        return make_color(cmin, rad, cmax, 255)
    elif rad >= (math.pi * 2 / 6 * 4) and rad < (math.pi * 2 / 6 * 5):
        rad = ((rad - (math.pi * 2 / 6 * 4)) * (1 / (math.pi * 2 / 6)) * (cmax - cmin)) + cmin
        return make_color(rad, cmin, cmax, 255)

    rad = cmax - ((rad - (math.pi * 2 / 6 * 5)) * (1 / (math.pi * 2 / 6)) * (cmax - cmin))
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
        val = math.sqrt(self._val * self._step)
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

def create_filter(freqs, amps, cycles, rate, filt=None):
    phase = list()
    step = list()
    maxval = list()
    length = 0.0
    for i in range(len(freqs)):
        phase.append(0.0)
        thislength = rate / freqs[i] * (cycles[i] - 0.25)
        step.append(TWOPI / (rate / freqs[i]))
        maxval.append(cycles[i] * TWOPI)
        if thislength > length:
            length = thislength
    length = int(length)

    if filt != None:
        if len(filt) < length:
            raise ValueError("Filter length less than length needed.")
    else:
        filt = array.array('f', repeat(0.0, length))

    for i in range(length):
        for j in range(len(freqs)):
            if phase[j] >= maxval[j]:
                continue
            else:
                filt[i] += math.cos(phase[j]) / \
                           (phase[j] / TWOPI + 1.0) * \
                           amps[j]
                phase[j] += step[j]

    return filt, length

def scale_filter(filt, start, count):
    allvals = 0.0
    for i in range(start, start + count):
        allvals += math.fabs(filt[i])

    for i in range(start, start + count):
        filt[i] /= allvals


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
    filt, flen = \
        create_filter((float(START),), (1.0,), (4,), rate)
    for i in range(1, SLICES - START):
        thisfilt = array.array('f', filt[(i-1)*flen:])
        create_filter((float(START + i) * 8.0,), (1.0,), (4,), rate, thisfilt)
        filt.extend(thisfilt)

    print(filt[(SLICES - START - 1)*flen])
    for i in range(SLICES - START):
        scale_filter(filt, i*flen, flen)
    print(filt[(SLICES - START - 1)*flen])

    #filt = array.array('f', (1.0, 0.0))
    #flen = 2
    #fscale = 1.0
    filt = aud.buffer(cg.SYNTH_TYPE_F32,
                      array.array('f', filt),
                      flen * (SLICES - START))

    aud.enabled(True)

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
                aud.del_sequence(seq)
                seq = None
            _, exc = aud.error
            print_tb(exc.__traceback__)
            print(exc)
            aud.enabled(True)

        if seq != None and seq.ended:
            aud.del_sequence(seq)
            seq = None
            print("Sequence ended")

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
                        aud.del_sequence(seq)
                        seq = None
                    macros = None
                    with open("macros.txt", 'r') as macrofile:
                        macrofile = audio.MacroReader(macrofile, trace=True)
                        try:
                            macros = audio.read_macros(macrofile)
                        except Exception as e:
                            print("Error reading macros from {} on line {}.".format(macrofile.name, macrofile.curline))
                            print_tb(e.__traceback__)
                            print(e)
                    if macros != None:
                        macros.extend((("FILTER_SIZE", (), str(flen)),
                                       ("FILTER_SLICES", (), str(SLICES - START))))
                        print(macros)
                        aud.enabled(False)
                        try:
                            with open(seqname, "r") as seqfile:
                                seq = audio.AudioSequencer(seqfile,
                                    [envslope, benddownslope, bendupslope, noise, filt],
                                    macros, trace=True)
                        except Exception as e:
                            aud.print_full_stats()
                            print_tb(e.__traceback__)
                            print(e)
                        if seq != None:
                            try:
                                aud.add_sequence(seq, enabled=True)
                            except Exception as e:
                                aud.print_full_stats()
                                print_tb(e.__traceback__)
                                print(e)
                                seq = None
                        aud.enabled(True)
                elif event.key.keysym.sym == SDLK_s:
                    if seq != None:
                        aud.del_sequence(seq)
                        seq = None
                elif event.key.keysym.sym == SDLK_r:
                    aud.enabled(True)
                elif event.key.keysym.sym == SDLK_n:
                    aud.enabled(False)
                elif event.key.keysym.sym == SDLK_i:
                    aud.print_full_stats()

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

        colorrad = colorrad + (math.pi * timetaken)
        if colorrad >= math.pi * 2:
            colorrad = colorrad - (math.pi * 2)
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
        aud.del_sequence(seq)

    SDL_DestroyRenderer(renderer)
    SDL_DestroyWindow(window)
    SDL_Quit()


if __name__ == "__main__":
    main()
