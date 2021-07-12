from ctypes import c_char_p, c_int, c_uint, c_void_p, c_float, c_double, py_object, CFUNCTYPE, POINTER, CDLL, pointer
from sdl2 import SDL_RendererInfo, SDL_Renderer, SDL_Window, SDL_Surface, SDL_Texture, SDL_PIXELFORMAT_UNKNOWN, SDL_RENDERER_SOFTWARE, SDL_WINDOWPOS_UNDEFINED, SDL_BITSPERPIXEL, SDL_ISPIXELFORMAT_ALPHA, SDL_GetNumRenderDrivers, SDL_GetRenderDriverInfo, SDL_CreateWindow, SDL_CreateRenderer

LOG_CB_RETURN_T = CFUNCTYPE(None, py_object, c_char_p)

_cg = None
# try to find libcrustygame.so in a few places
try:
    _cg = CDLL("libcrustygame.so")
except OSError as e:
    try:
        _cg = CDLL("./libcrustygame.so")
    except OSError as e:
        _cg = CDLL("../libcrustygame.so")

# tilemap.h definitions
TILEMAP_HFLIP_MASK  = 0x01
TILEMAP_VFLIP_MASK  = 0x02
TILEMAP_ROTATE_MASK = 0x0C
TILEMAP_ROTATE_NONE = 0x00
TILEMAP_ROTATE_90   = 0x04
TILEMAP_ROTATE_180  = 0x08
TILEMAP_ROTATE_270  = 0x0C

TILEMAP_BLENDMODE_BLEND = 0
TILEMAP_BLENDMODE_ADD   = 1
TILEMAP_BLENDMODE_MOD   = 2
TILEMAP_BLENDMODE_MUL   = 3
TILEMAP_BLENDMODE_SUB   = 4

# these values are just for passing colormod values/buffers, they don't indicate
# any sort of best or native format or anything
TILEMAP_BSHIFT = 24
TILEMAP_GSHIFT = 16
TILEMAP_RSHIFT = 8
TILEMAP_ASHIFT = 0
TILEMAP_BMASK = 0xFF000000
TILEMAP_GMASK = 0x00FF0000
TILEMAP_RMASK = 0x0000FF00
TILEMAP_AMASK = 0x000000FF

# tilemap.h miscellaneous functions/macros
def tilemap_color(r :int, g :int, b :int, a :int) -> int:
    """
    Used for creating an integer for the tileset/layer colormod values.
    """
    return (r << TILEMAP_RSHIFT) | \
           (g << TILEMAP_GSHIFT) | \
           (b << TILEMAP_BSHIFT) | \
           (a << TILEMAP_ASHIFT)
def tilemap_color_r(val :int) -> int:
    """
    Extract red from a colormod value.
    """
    return (val & TILEMAP_RMASK) >> TILEMAP_RSHIFT
def tilemap_color_g(val :int) -> int:
    """
    Extract green from a colormod value.
    """
    return (val & TILEMAP_GMASK) >> TILEMAP_GSHIFT
def tilemap_color_b(val :int) -> int:
    """
    Extract blue from a colormod value.
    """
    return (val & TILEMAP_BMASK) >> TILEMAP_BSHIFT
def tilemap_color_a(val :int) -> int:
    """
    Extract alpha from a colormod value.
    """
    return (val & TILEMAP_AMASK) >> TILEMAP_ASHIFT

def _set_types(func, restype, argtypes :list):
    func.restype = restype
    func.argtypes = argtypes

# synth.h definitions
SYNTH_TYPE_INVALID = 0
SYNTH_TYPE_U8 = 1
SYNTH_TYPE_S16 = 2
SYNTH_TYPE_F32 = 3
SYNTH_TYPE_F64 = 4

SYNTH_STOPPED = 0
SYNTH_ENABLED = 1
SYNTH_RUNNING = 2

SYNTH_OUTPUT_REPLACE = 0
SYNTH_OUTPUT_ADD = 1

SYNTH_AUTO_CONSTANT = 0
SYNTH_AUTO_SOURCE = 1

SYNTH_MODE_ONCE = 0
SYNTH_MODE_LOOP = 1
SYNTH_MODE_PHASE_SOURCE = 2

SYNTH_STOPPED_OUTBUFFER = 0x01
SYNTH_STOPPED_INBUFFER = 0x02
SYNTH_STOPPED_VOLBUFFER = 0x04
SYNTH_STOPPED_SPEEDBUFFER = 0x08
SYNTH_STOPPED_PHASEBUFFER = 0x10
SYNTH_STOPPED_SLICEBUFFER = 0x20

SYNTH_FRAME_CB_T = CFUNCTYPE(c_int, py_object, c_void_p)

# tilemap.h funcs
_set_types(_cg.tilemap_tileset_from_bmp, c_int, [c_void_p, c_char_p, c_uint, c_uint])
_set_types(_cg.tilemap_blank_tileset, c_int, [c_void_p, c_uint, c_uint, c_uint, c_uint, c_uint])
_set_types(_cg.layerlist_new, c_void_p, [c_void_p, c_uint, LOG_CB_RETURN_T, py_object])
_set_types(_cg.layerlist_free, None, [c_void_p])
_set_types(_cg.layerlist_get_renderer, POINTER(SDL_Renderer), [c_void_p])
_set_types(_cg.tilemap_set_default_render_target, None, [c_void_p, c_void_p])
_set_types(_cg.tilemap_set_target_tileset, c_int, [c_void_p, c_int])
_set_types(_cg.tilemap_add_tileset, c_int, [c_void_p, c_void_p, c_uint, c_uint])
_set_types(_cg.tilemap_free_tileset, c_int, [c_void_p, c_uint])
_set_types(_cg.tilemap_add_tilemap, c_int, [c_void_p, c_uint, c_uint])
_set_types(_cg.tilemap_free_tilemap, c_int, [c_void_p, c_uint])
_set_types(_cg.tilemap_set_tilemap_tileset, c_int, [c_void_p, c_uint, c_uint])
_set_types(_cg.tilemap_set_tilemap_map, c_int, [c_void_p, c_uint, c_uint, c_uint, c_uint, c_uint, c_uint, c_void_p, c_uint])
_set_types(_cg.tilemap_set_tilemap_attr_flags, c_int, [c_void_p, c_uint, c_uint, c_uint, c_uint, c_uint, c_uint, c_void_p, c_uint])
_set_types(_cg.tilemap_set_tilemap_attr_colormod, c_int, [c_void_p, c_uint, c_uint, c_uint, c_uint, c_uint, c_uint, c_void_p, c_uint])
_set_types(_cg.tilemap_update_tilemap, c_int, [c_void_p, c_uint, c_uint, c_uint, c_uint, c_uint])
_set_types(_cg.tilemap_add_layer, c_int, [c_void_p, c_uint])
_set_types(_cg.tilemap_free_layer, c_int, [c_void_p, c_uint])
_set_types(_cg.tilemap_set_layer_pos, c_int, [c_void_p, c_uint, c_int, c_int])
_set_types(_cg.tilemap_set_layer_window, c_int, [c_void_p, c_uint, c_uint, c_uint])
_set_types(_cg.tilemap_set_layer_scroll_pos, c_int, [c_void_p, c_uint, c_uint, c_uint])
_set_types(_cg.tilemap_set_layer_scale, c_int, [c_void_p, c_uint, c_double, c_double])
_set_types(_cg.tilemap_set_layer_rotation_center, c_int, [c_void_p, c_uint, c_int, c_int])
_set_types(_cg.tilemap_set_layer_rotation, c_int, [c_void_p, c_uint, c_double])
_set_types(_cg.tilemap_set_layer_colormod, c_int, [c_void_p, c_uint, c_uint])
_set_types(_cg.tilemap_set_layer_blendmode, c_int, [c_void_p, c_uint, c_int])
_set_types(_cg.tilemap_draw_layer, c_int, [c_void_p, c_uint])

# synth.h funcs
_set_types(_cg.synth_type_from_audioformat, c_int, [c_int])
_set_types(_cg.synth_buffer_from_wav, c_int, [c_void_p, c_char_p, POINTER(c_uint)])
_set_types(_cg.synth_print_full_stats, None, [c_void_p])
_set_types(_cg.synth_get_samples_needed, c_uint, [c_void_p])
_set_types(_cg.synth_new, c_void_p, [SYNTH_FRAME_CB_T, py_object, LOG_CB_RETURN_T, py_object, c_uint, c_uint])
_set_types(_cg.synth_free, None, [c_void_p])
_set_types(_cg.synth_get_rate, c_uint, [c_void_p])
_set_types(_cg.synth_get_channels, c_uint, [c_void_p])
_set_types(_cg.synth_get_fragment_size, c_uint, [c_void_p])
_set_types(_cg.synth_has_underrun, c_int, [c_void_p])
_set_types(_cg.synth_set_enabled, c_int, [c_void_p, c_int])
_set_types(_cg.synth_frame, c_int, [c_void_p])
_set_types(_cg.synth_set_fragments, c_int, [c_void_p, c_uint])
_set_types(_cg.synth_add_buffer, c_int, [c_void_p, c_int, c_void_p, c_uint])
_set_types(_cg.synth_free_buffer, c_int, [c_void_p, c_uint])
_set_types(_cg.synth_buffer_get_size, c_int, [c_void_p, c_uint])
_set_types(_cg.synth_silence_buffer, c_int, [c_void_p, c_uint, c_uint, c_uint])
_set_types(_cg.synth_add_player, c_int, [c_void_p, c_uint])
_set_types(_cg.synth_free_player, c_int, [c_void_p, c_uint])
_set_types(_cg.synth_set_player_input_buffer, c_int, [c_void_p, c_uint, c_uint])
_set_types(_cg.synth_set_player_input_buffer_pos, c_int, [c_void_p, c_uint, c_float])
_set_types(_cg.synth_set_player_output_buffer, c_int, [c_void_p, c_uint, c_uint])
_set_types(_cg.synth_set_player_output_buffer_pos, c_int, [c_void_p, c_uint, c_int])
_set_types(_cg.synth_set_player_output_mode, c_int, [c_void_p, c_uint, c_int])
_set_types(_cg.synth_set_player_volume_mode, c_int, [c_void_p, c_uint, c_int])
_set_types(_cg.synth_set_player_volume, c_int, [c_void_p, c_uint, c_float])
_set_types(_cg.synth_set_player_volume_source, c_int, [c_void_p, c_uint, c_uint])
_set_types(_cg.synth_set_player_mode, c_int, [c_void_p, c_uint, c_int])
_set_types(_cg.synth_set_player_loop_start, c_int, [c_void_p, c_uint, c_uint])
_set_types(_cg.synth_set_player_loop_end, c_int, [c_void_p, c_uint, c_uint])
_set_types(_cg.synth_set_player_phase_source, c_int, [c_void_p, c_uint, c_uint])
_set_types(_cg.synth_set_player_speed_mode, c_int, [c_void_p, c_uint, c_int])
_set_types(_cg.synth_set_player_speed, c_int, [c_void_p, c_uint, c_float])
_set_types(_cg.synth_set_player_speed_source, c_int, [c_void_p, c_uint, c_uint])
_set_types(_cg.synth_run_player, c_int, [c_void_p, c_uint, c_uint])
_set_types(_cg.synth_player_stopped_reason, c_int, [c_void_p, c_uint])

_set_types(_cg.synth_add_filter, c_int, [c_void_p, c_uint, c_uint])
_set_types(_cg.synth_free_filter, c_int, [c_void_p, c_uint])
_set_types(_cg.synth_set_filter_input_buffer, c_int, [c_void_p, c_uint, c_uint])
_set_types(_cg.synth_set_filter_input_buffer_pos, c_int, [c_void_p, c_uint, c_uint])
_set_types(_cg.synth_set_filter_buffer, c_int, [c_void_p, c_uint, c_uint])
_set_types(_cg.synth_set_filter_buffer_start, c_int, [c_void_p, c_uint, c_uint])
_set_types(_cg.synth_set_filter_slices, c_int, [c_void_p, c_uint, c_uint])
_set_types(_cg.synth_set_filter_mode, c_int, [c_void_p, c_uint, c_int])
_set_types(_cg.synth_set_filter_slice, c_int, [c_void_p, c_uint, c_uint])
_set_types(_cg.synth_set_filter_slice_source, c_int, [c_void_p, c_uint, c_uint])
_set_types(_cg.synth_set_filter_output_buffer, c_int, [c_void_p, c_uint, c_uint])
_set_types(_cg.synth_set_filter_output_buffer_pos, c_int, [c_void_p, c_uint, c_uint])
_set_types(_cg.synth_set_filter_output_mode, c_int, [c_void_p, c_uint, c_int])
_set_types(_cg.synth_set_filter_volume_mode, c_int, [c_void_p, c_uint, c_int])
_set_types(_cg.synth_set_filter_volume, c_int, [c_void_p, c_uint, c_float])
_set_types(_cg.synth_set_filter_volume_source, c_int, [c_void_p, c_uint, c_uint])
_set_types(_cg.synth_run_filter, c_int, [c_void_p, c_uint, c_uint])
_set_types(_cg.synth_filter_stopped_reason, c_int, [c_void_p, c_uint])


class CrustyException(Exception):
    pass


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
    returns window, renderer and prefered pixel format or raises CrustyException if
    no window or renderer could be created
    """
    driver = list()
    pixfmt = SDL_PIXELFORMAT_UNKNOWN
    drivers = SDL_GetNumRenderDrivers()

    for i in range(drivers):
        d = SDL_RendererInfo()
        if SDL_GetRenderDriverInfo(i, d) < 0:
            raise CrustyException("Couldn't get video renderer info for {}".format(i))
        driver.append((i, d))

    driver = sorted(driver, key=_driver_key)

    window = SDL_CreateWindow(title.encode("utf-8"), SDL_WINDOWPOS_UNDEFINED, SDL_WINDOWPOS_UNDEFINED, width, height, winflags)
    if window == None:
        raise CrustyException("Couldn't create SDL window.")

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

        break

    if renderer == None:
        SDL_DestroyWindow(window)
        raise CrustyException("Couldn't initialze any SDL video device.")

    return window, renderer, pixfmt


def create_uint_array(iterable):
    arrayType = c_uint * len(iterable)
    array = arrayType()

    for item in enumerate(iterable):
        array[item[0]] = item[1]

    return array

def create_float_array(iterable):
    arrayType = c_float * len(iterable)
    array = arrayType()

    for item in enumerate(iterable):
        array[item[0]] = item[1]

    return array

# not sure if it matters but it might or whether it'll even prevent any issues
# but try to hold references to things in dependent objects just so the internal
# "free" functions are maybe called in a sane order during garbage collection?
class Layerlist():
    """
    See tileset.h for details on using this library.
    """
    def __init__(self,
                 renderer: SDL_Renderer,
                 texfmt :int,
                 printfunc: LOG_CB_RETURN_T,
                 printpriv):
        self._ll = _cg.layerlist_new(renderer,
                                     texfmt,
                                     printfunc,
                                     py_object(printpriv))
        if self._ll == None:
            raise CrustyException("Couldn't initialize LayerList.")

    def __del__(self):
        _cg.layerlist_free(self._ll)

    @property
    def renderer(self) -> SDL_Renderer:
        return _cg.layerlist_get_renderer(self._ll)

    def tileset(self, surface :SDL_Surface, tw :int, th :int):
        return Tileset(self, surface, tw, th)

    def blank_tileset(self,
                      w :int, h :int,
                      color :int,
                      tw :int, th :int):
        return Tileset(self, w, h, color, tw, th)

    def tileset_from_bmp(self, filename :str, tw :int, th :int):
        return Tileset(self, filename, tw, th)

    # not sure why i allow for tilemaps without an assigned tileset but whichever
    def tilemap(self, tileset :int, w :int, h :int):
        tilemap = Tilemap(self, w, h)
        tilemap.tileset(tileset)
        return tilemap

    def layer(self, tilemap :int):
        return Layer(self, tilemap)

    def default_render_target(self, texture :SDL_Texture):
        _cg.tilemap_set_default_render_target(self._ll, texture)

    def target_tileset(self, tileset :int):
        if _cg.tilemap_set_target_tileset(self._ll, tileset) < 0:
            raise CrustyException("Couldn't set target tileset.")


class Tileset():
    """
    See tileset.h for details on using this library.
    """
    def __init__(self, ll :Layerlist, *args):
        self._ll = ll
        if isinstance(args[0], SDL_Surface):
            self._ts = _cg.tilemap_new_tileset(ll._ll, args[0], args[1], args[2])
        elif isinstance(args[0], int):
            self._ts = _cg.tilemap_blank_tileset(ll._ll, args[0], args[1], args[2], args[3], args[4])
        elif isinstance(args[0], str):
            self._ts = _cg.tilemap_tileset_from_bmp(ll._ll, args[0].encode("utf-8"), args[1], args[2])
        else:
            raise TypeError()
        if self._ts < 0:
            raise CrustyException("Couldn't create a tileset.")

    def __del__(self):
        if _cg.tilemap_free_tileset(self._ll._ll, self) < 0:
            raise CrustyException()

    def __int__(self):
        return self._ts


class Tilemap():
    """
    See tileset.h for details on using this library.
    """
    def __init__(self, ll :Layerlist, w, h):
        self._ll = ll
        self._tm = _cg.tilemap_add_tilemap(ll._ll, w, h)
        if self._tm < 0:
            raise CrustyException()

    def __del__(self):
        if _cg.tilemap_free_tilemap(self._ll._ll, self) < 0:
            raise CrustyException()

    def __int__(self):
        return self._tm

    def tileset(self, tileset :Tileset):
        self._ts = tileset
        if _cg.tilemap_set_tilemap_tileset(self._ll._ll, self, tileset._ts) < 0:
            raise CrustyException()

    def map(self,
            x :int, y :int,
            pitch :int, w :int, h :int,
            values :int):
        if _cg.tilemap_set_tilemap_map(self._ll._ll, self, x, y, pitch, w, h, create_uint_array(values), len(values)) < 0:
            raise CrustyException()

    def attr_flags(self,
                   x :int, y :int,
                   pitch :int, w :int, h :int,
                   values :c_void_p):
        if _cg.tilemap_set_tilemap_attr_flags(self._ll._ll, self, x, y, pitch, w, h, create_uint_array(values), len(values)) < 0:
            raise CrustyException()

    def attr_colormod(self,
                      x :int, y :int,
                      pitch :int, w :int, h: int,
                      values :c_void_p):
        if _cg.tilemap_set_tilemap_attr_colormod(self._ll._ll, self, x, y, pitch, w, h, create_uint_array(values), len(values)) < 0:
            raise CrustyException()

    def update(self, x :int, y :int, w :int, h :int):
        if _cg.tilemap_update_tilemap(self._ll._ll, self, x, y, w, h) < 0:
            raise CrustyException()


class Layer():
    """
    See tileset.h for details on using this library.
    """
    def __init__(self, ll :Layerlist, tilemap :Tilemap):
        self._ll = ll
        self._tm = tilemap
        self._l = _cg.tilemap_add_layer(ll._ll, tilemap)
        if self._l < 0:
            raise CrustyException()

    def __del__(self):
        if _cg.tilemap_free_layer(self._ll._ll, self):
            raise CrustyException()

    def __int__(self):
        return self._l

    def pos(self, x :int, y :int):
        if _cg.tilemap_set_layer_pos(self._ll._ll, self, x, y) < 0:
            raise CrustyException()

    def window(self, w :int, h :int):
        if _cg.tilemap_set_layer_window(self._ll._ll, self, w, h) < 0:
            raise CrustyException()
    
    def scroll_pos(self, scroll_x :int, scroll_y :int):
        if _cg.tilemap_set_layer_scroll_pos(self._ll._ll, self, scroll_x, scroll_y) < 0:
            raise CrustyException()

    def scale(self, scale_x :float, scale_y :float):
        if _cg.tilemap_set_layer_scale(self._ll._ll, self, scale_x, scale_y) < 0:
            raise CrustyException()

    def rotation_center(self, x :int, y :int):
        if _cg.tilemap_set_layer_rotation_center(self._ll._ll, self, x, y) < 0:
            raise CrustyException()

    def rotation(self, angle :float):
        if _cg.tilemap_set_layer_rotation(self._ll._ll, self, angle) < 0:
            raise CrustyException()

    def colormod(self, colormod :int):
        if _cg.tilemap_set_layer_colormod(self._ll._ll, self, colormod) < 0:
            raise CrustyException()

    def blendmode(self, blendMode :int):
        if _cg.tilemap_set_layer_blendmode(self._ll._ll, self, blendMode) < 0:
            raise CrustyException()

    def draw(self):
        if _cg.tilemap_draw_layer(self._ll._ll, self) < 0:
            raise CrustyException()


class Synth():
    """
    See synth.h for details on using this library.
    """
    def __init__(self,
                framefunc :SYNTH_FRAME_CB_T,
                framepriv,
                printfunc :LOG_CB_RETURN_T,
                printpriv,
                rate :int,
                channels :int):
        self._priv = (self, framepriv)
        self._s = _cg.synth_new(framefunc, py_object(self._priv),
                                printfunc, py_object(printpriv),
                                rate, channels)
        if self._s == None:
            raise CrustyException("Couldn't initialize synthesizer.")
        self._outputBuffers = [Buffer(self, i) for i in range(self.channels)]

    def __del__(self):
        _cg.synth_free(self._s)

    def print_full_stats(self):
        _cg.synth_print_full_stats(self._s)

    def output_buffers(self):
        return self._outputBuffers

    def buffer(self, dataType :int, data :c_void_p, size :int):
        if data != None and size > len(data):
            raise CrustyException("Buffer size larger than data buffer ({} > {}).".format(size, len(data)))
        return Buffer(self, dataType, data, size)

    def buffer_from_wav(self, filename :str):
        rate = c_uint()
        return Buffer(self, filename, pointer(rate)), rate.value

    def player(self, buffer :'Buffer'):
        return Player(self, buffer)

    def filter(self, buffer :'Buffer', size :int):
        return Filter(self, buffer, size)

    @property
    def rate(self):
        return _cg.synth_get_rate(self._s)

    @property
    def channels(self):
        return _cg.synth_get_channels(self._s)

    @property
    def fragment_size(self):
        return _cg.synth_get_fragment_size(self._s)

    @property
    def underrun(self):
        if _cg.synth_has_underrun(self._s) == 0:
            return False
        return True

    def fragments(self, fragments :int):
        if _cg.synth_set_fragments(self._s, fragments) < 0:
            raise CrustyException()

    @property
    def needed(self):
        return _cg.synth_get_samples_needed(self._s)

    def enabled(self, enabled :int):
        if _cg.synth_set_enabled(self._s, enabled) < 0:
            raise CrustyException()

    def frame(self):
        if _cg.synth_frame(self._s) < 0:
            raise CrustyException()


class Buffer():
    """
    See synth.h for details on using this library.
    """
    def __init__(self, *args):
        self._s = args[0]
        self._b = -1
        self._output = False
        if len(args) == 2:
            # channel output buffers
            self._b = args[1]
            self._output = True
        elif isinstance(args[1], int):
            self._b = _cg.synth_add_buffer(self._s._s, args[1], args[2], args[3])
        elif isinstance(args[1], str):
            self._b = _cg.synth_buffer_from_wav(self._s._s, c_char_p(args[1].encode('utf-8')), args[2])
        else:
            raise TypeError()

        if self._b < 0:
            raise CrustyException("Couldn't create buffer.")

    def __del__(self):
        if not self._output:
            _cg.synth_free_buffer(self._s._s, self)

    def __int__(self):
        return self._b

    @property
    def size(self):
        size = _cg.synth_buffer_get_size(self._s._s, self)
        if size < 0:
            raise CrustyException()
        return size

    def silence(self, start :int, length :int):
        if _cg.synth_silence_buffer(self._s._s, self, start, length) < 0:
            raise CrustyException()


class Player():
    """
    See synth.h for details on using this library.
    """
    def __init__(self, synth :Synth, buffer :Buffer):
        self._ib = buffer
        self._vb = buffer
        self._pb = buffer
        self._sb = buffer
        self._s = synth
        self._p = _cg.synth_add_player(self._s._s, buffer)

        if self._p < 0:
            raise CrustyException()

    def __del__(self):
        _cg.synth_free_player(self._s._s, self)

    def __int__(self):
        return self._p

    def input_buffer(self, buffer :Buffer):
        if _cg.synth_set_player_input_buffer(self._s._s, self, buffer) < 0:
            raise CrustyException()
        self._ib = buffer

    def input_pos(self, pos :float):
        if _cg.synth_set_player_input_buffer_pos(self._s._s, self, pos) < 0:
            raise CrustyException()

    def output_buffer(self, buffer :Buffer):
        if _cg.synth_set_player_output_buffer(self._s._s, self, buffer) < 0:
            raise CrustyException()
        self._ob = buffer

    def output_pos(self, pos :int):
        if _cg.synth_set_player_output_buffer_pos(self._s._s, self, pos) < 0:
            raise CrustyException()

    def output_mode(self, mode :int):
        if _cg.synth_set_player_output_mode(self._s._s, self, mode) < 0:
            raise CrustyException()

    def volume_mode(self, mode :int):
        if _cg.synth_set_player_volume_mode(self._s._s, self, mode) < 0:
            raise CrustyException()

    def volume(self, volume :float):
        if _cg.synth_set_player_volume(self._s._s, self, volume) < 0:
            raise CrustyException()

    def volume_source(self, source :Buffer):
        if _cg.synth_set_player_volume_source(self._s._s, self, source) < 0:
            raise CrustyException()
        self._vb = source

    def mode(self, mode :int):
        if _cg.synth_set_player_mode(self._s._s, self, mode) < 0:
            raise CrustyException()

    def loop_start(self, loopStart :int):
        if _cg.synth_set_player_loop_start(self._s._s, self, loopStart) < 0:
            raise CrustyException()

    def loop_end(self, loopEnd :int):
        if _cg.synth_set_player_loop_end(self._s._s, self, loopEnd) < 0:
            raise CrustyException()

    def phase_source(self, source :Buffer):
        if _cg.synth_set_player_phase_source(self._s._s, self, source) < 0:
            raise CrustyException()
        self._pb = source

    def speed_mode(self, mode :int):
        if _cg.synth_set_player_speed_mode(self._s._s, self, mode) < 0:
            raise CrustyException()

    def speed(self, speed :float):
        if _cg.synth_set_player_speed(self._s._s, self, speed) < 0:
            raise CrustyException()

    def speed_source(self, source :Buffer):
        if _cg.synth_set_player_speed_source(self._s._s, self, source) < 0:
            raise CrustyException()
        self._sb = source

    def run(self, requested :int):
        ret = _cg.synth_run_player(self._s._s, self, requested)
        if ret < 0:
            raise CrustyException()
        return ret

    def stop_reason(self):
        ret = _cg.synth_player_stopped_reason(self._s._s, self)
        if ret < 0:
            raise CrustyException()
        return ret


class Filter():
    def __init__(self, synth :Synth, buffer :Buffer, size :int):
        self._s = synth
        self._b = buffer
        self._f = _cg.synth_add_filter(self._s._s, buffer, size)
        if self._f == None:
            raise CrustyException()

    def __del__(self):
        _cg.synth_free_filter(self._s._s, self)

    def __int__(self):
        return self._f

    def input_buffer(self, buffer :Buffer):
        print(int(self))
        if _cg.synth_set_filter_input_buffer(self._s._s, self, buffer) < 0:
            raise CrustyException()

    def input_pos(self, pos :int):
        if _cg.synth_set_filter_input_buffer_pos(self._s._s, self, pos) < 0:
            raise CrustyException()

    def filter_buffer(self, buffer :Buffer):
        if _cg.synth_set_filter_buffer(self._s._s, self, buffer) < 0:
            raise CrustyException()

    def filter_start(self, start :int):
        if _cg.synth_set_filter_buffer_start(self._s._s, self, start) < 0:
            raise CrustyException()

    def slices(self, slices :int):
        if _cg.synth_set_filter_slices(self._s._s, self, slices) < 0:
            raise CrustyException()

    def mode(self, mode :int):
        if _cg.synth_set_filter_mode(self._s._s, self, mode) < 0:
            raise CrustyException()

    def slice(self, sliceval :int):
        if _cg.synth_set_filter_slice(self._s._s, self, sliceval) < 0:
            raise CrustyException()

    def slice_source(self, buffer :Buffer):
        if _cg.synth_set_filter_slice_source(self._s._s, self, buffer) < 0:
            raise CrustyException()

    def output_buffer(self, buffer :Buffer):
        if _cg.synth_set_filter_output_buffer(self._s._s, self, buffer) < 0:
            raise CrustyException()

    def output_pos(self, pos :int):
        if _cg.synth_set_filter_output_buffer_pos(self._s._s, self, pos) < 0:
            raise CrustyException()

    def output_mode(self, mode :int):
        if _cg.synth_set_filter_output_mode(self._s._s, self, mode) < 0:
            raise CrustyException()

    def volume_mode(self, mode :int):
        if _cg.synth_set_filter_volume_mode(self._s._s, self, mode) < 0:
            raise CrustyException()

    def volume(self, vol :float):
        if _cg.synth_set_filter_volume(self._s._s, self, vol) < 0:
            raise CrustyException()

    def volume_source(self, source :Buffer):
        if _cg.synth_set_filter_volume_source(self._s._s, self, source) < 0:
            raise CrustyException()

    def run(self, requested :int):
        ret = _cg.synth_run_filter(self._s._s, self, requested)
        if ret < 0:
            raise CrustyException()
        return ret

    def stop_reason(self):
        ret = _cg.synth_filter_stopped_reason(self._s._s, self)
        if ret < 0:
            raise CrustyException()
        return ret
