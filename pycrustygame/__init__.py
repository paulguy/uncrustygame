from ctypes import *
from sdl2 import *

LOG_CB_RETURN_T = CFUNCTYPE(None, c_char_p)

_cg = None
# try to find libcrustygame.so in a few places
try:
    _cg = CDLL("libcrustygame.so")
except OSError as e:
    try:
        _cg = CDLL("./libcrustygame.so")
    except OSError as e:
        _cg = CDLL("../libcrustygame.so")

def _set_types(func, restype, argtypes :list):
    func.restype = restype
    func.argtypes = argtypes

_set_types(_cg.log_cb_helper, c_int, [LOG_CB_RETURN_T, c_char_p])
_set_types(_cg.tilemap_tileset_from_bmp, c_int, [c_void_p, c_char_p, c_uint, c_uint])
_set_types(_cg.tilemap_blank_tileset, c_int, [c_void_p, c_uint, c_uint, c_uint, c_uint, c_uint])
_set_types(_cg.layerlist_new, c_void_p, [c_void_p, c_uint, c_void_p, c_void_p])
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

def tilemap_color(r, g, b, a):
    return((r << TILEMAP_RSHIFT) |
           (g << TILEMAP_GSHIFT) |
           (b << TILEMAP_BSHIFT) |
           (a << TILEMAP_ASHIFT))
def tilemap_color_r(val):
    return((val & TILEMAP_RMASK) >> TILEMAP_RSHIFT)
def tilemap_color_g(val):
    return((val & TILEMAP_GMASK) >> TILEMAP_GSHIFT)
def tilemap_color_b(val):
    return((val & TILEMAP_BMASK) >> TILEMAP_BSHIFT)
def tilemap_color_a(val):
    return((val & TILEMAP_AMASK) >> TILEMAP_ASHIFT)

class CrustyException(Exception):
    pass


# not sure if it matters but it might or whether it'll even prevent any issues
# but try to hold references to things in dependent objects just so the internal
# "free" functions are maybe called in a sane order during garbage collection?
class Layerlist():
    def __init__(self,
                 renderer: SDL_Renderer,
                 texfmt,
                 printfunc: LOG_CB_RETURN_T):
        self._ll = _cg.layerlist_new(renderer,
                                     texfmt,
                                     _cg.log_cb_helper,
                                     printfunc)

    def __del__(self):
        _cg.layerlist_free(self._ll)

    @property
    def renderer(self):
        return(_cg.layerlist_get_renderer(self._ll))

    def tileset(self, surface :SDL_Surface, tw, th):
        return(Tileset(self, surface, tw, th))

    def blank_tileset(self, w, h, color, tw, th):
        return(Tileset(self, w, h, color, tw, th))

    def tileset_from_bmp(self, filename, tw, th):
        return(Tileset(self, filename, tw, th))

    # not sure why i allow for tilemaps without an assigned tileset but whichever
    def tilemap(self, tileset, w, h):
        tilemap = Tilemap(self, w, h)
        tilemap.tileset(tileset)
        return(tilemap)

    def layer(self, tilemap):
        return(Layer(self, tilemap))

    def default_render_target(self, texture):
        _cg.tilemap_set_default_render_target(self._ll, texture)

    def target_tileset(self, tileset):
        if _cg.tilemap_set_target_tileset(self._ll, tileset) < 0:
            raise(CrustyException())


class Tileset():
    def __init__(self, ll :Layerlist, *args):
        self._ll = ll
        if isinstance(args[0], SDL_Surface):
            self._ts = _cg.tilemap_new_tileset(ll._ll, args[0], args[1], args[2])
        elif isinstance(args[0], int):
            self._ts = _cg.tilemap_blank_tileset(ll._ll, args[0], args[1], args[2], args[3], args[4])
        elif isinstance(args[0], str):
            self._ts = _cg.tilemap_tileset_from_bmp(ll._ll, args[0].encode("utf-8"), args[1], args[2])
        else:
            raise(TypeError())
        if self._ts < 0:
            raise(CrustyException())

    def __del__(self):
        if _cg.tilemap_free_tileset(self._ll._ll, self) < 0:
            raise(CrustyException())

    def __int__(self):
        return(self._ts)


class Tilemap():
    def __init__(self, ll :Layerlist, w, h):
        self._ll = ll
        self._tm = _cg.tilemap_add_tilemap(ll._ll, w, h)
        if self._tm < 0:
            raise(CrustyException())

    def __del__(self):
        if _cg.tilemap_free_tilemap(self._ll._ll, self) < 0:
            raise(CrustyException())

    def __int__(self):
        return(self._tm)

    def tileset(self, tileset :Tileset):
        self._ts = tileset
        if _cg.tilemap_set_tilemap_tileset(self._ll._ll, self, tileset._ts) < 0:
            raise(CrustyException())

    def map(self, x, y, pitch, w, h, values):
        if _cg.tilemap_set_tilemap_map(self._ll._ll, self, x, y, pitch, w, h, values, len(values)) < 0:
            raise(CrustyException())

    def attr_flags(self, x, y, pitch, w, h, values):
        if _cg.tilemap_set_tilemap_attr_flags(self._ll._ll, self, x, y, pitch, values, len(values)) < 0:
            raise(CrustyException())

    def attr_colormod(self, x, y, pitch, w, h, values):
        if _cg.tilemap_set_tilemap_attr_colormod(self._ll._ll, self, x, y, pitch, values, len(values)) < 0:
            raise(CrustyException())

    def update(self, x, y, w, h):
        if _cg.tilemap_update_tilemap(self._ll._ll, self, x, y, w, h) < 0:
            raise(CrustyException())


class Layer():
    def __init__(self, ll :Layerlist, tilemap :Tilemap):
        self._ll = ll
        self._tm = tilemap
        self._l = _cg.tilemap_add_layer(ll._ll, tilemap)
        if self._l < 0:
            raise(CrustyException())

    def __del__(self):
        if _cg.tilemap_free_layer(self._ll._ll, self):
            raise(CrustyException())

    def __int__(self):
        return(self._l)

    def pos(self, x, y):
        if _cg.tilemap_set_layer_pos(self._ll._ll, self, x, y) < 0:
            raise(CrustyException())

    def window(self, w, h):
        if _cg.tilemap_set_layer_window(self._ll._ll, self, w, h) < 0:
            raise(CrustyException())

    def scale(self, scale_x, scale_y):
        if _cg.tilemap_set_layer_scale(self._ll._ll, self, scale_x, scale_y) < 0:
            raise(CrustyException())

    def rotation_center(self, x, y):
        if _cg.tilemap_set_layer_rotation_center(self._ll._ll, self, x, y) < 0:
            raise(CrustyException())

    def rotation(self, angle):
        if _cg.tilemap_set_layer_rotation(self._ll._ll, self, angle) < 0:
            raise(CrustyException())

    def colormod(self, colormod):
        if _cg.tilemap_set_layer_colormod(self._ll._ll, self, colormod) < 0:
            raise(CrustyException())

    def blendmode(self, blendMode):
        if _cg.tilemap_set_layer_blendmode(self._ll._ll, self, blendMode) < 0:
            raise(CrustyException())

    def draw(self):
        if _cg.tilemap_draw_layer(self._ll._ll, self) < 0:
            raise(CrustyException())
