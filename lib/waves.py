import array
import numpy
from scipy import signal
import random

FILTER_TAPS = 1024
BASE_FREQ = 20
FILTERS_PER_DECADE = 100
DECADES = 3
SLICES = FILTERS_PER_DECADE * DECADES
MIN_TRANS_WIDTH = BASE_FREQ * 2
TRANS_WIDTH_DIV = 10

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
                    print("{} {}".format(mul, transwidth))
                    pos = (dec * FILTERS_PER_DECADE * FILTER_TAPS) + (i * FILTER_TAPS)
#                    filt[pos:pos + FILTER_TAPS] = \
#                        signal.remez(FILTER_TAPS,
#                                     [0, freq, freq + transwidth, rate / 2],
#                                     [1, 0], fs=rate)
                    if lowpass:
                        filt[pos:pos + FILTER_TAPS] = \
                             signal.firwin(FILTER_TAPS, freq,
                                           width=transwidth,
                                           pass_zero=lowpass, fs=rate)
                    else:
                        filt[pos:pos + FILTER_TAPS] = \
                             signal.firwin(FILTER_TAPS, (freq, rate/2-1),
                                           width=transwidth,
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


