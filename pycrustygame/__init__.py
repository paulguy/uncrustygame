from ctypes import *
from sdl2 import *

_LOG_CB_RETURN_T = CFUNCTYPE(None, c_char_p)

_cg = None
# try to find libcrustygame.so in a few places
try:
    _cg = CDLL("libcrustygame.so")
except OSError as e:
    try:
        _cg = CDLL("./libcrustygame.so")
    except OSError as e:
        _cg = CDLL("../libcrustygame.so")

def _set_types(func,
               restype,
               argtypes :list):
    func.restype = restype
    func.argtypes = argtypes

_set_types(_cg.log_cb_helper, c_int, [_LOG_CB_RETURN_T, c_char_p])
_set_types(_cg.tilemap_tileset_from_bmp, c_int, [c_void_p, c_char_p, c_uint, c_uint])
_set_types(_cg.tilemap_blank_tileset, c_int, [c_void_p, c_uint, c_uint, c_uint, c_uint, c_uint])
_set_types(_cg.layerlist_new, c_void_p, [c_void_p, c_uint, c_void_p, c_void_p])
_set_types(_cg.layerlist_free, None, [c_void_p])
_set_types(_cg.layerlist_get_renderer, c_void_p, [c_void_p])
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
_set_types(_cg.tilemap_set_default_render_target, None, [c_void_p, c_void_p])
_set_types(_cg.tilemap_set_target_tileset, c_int, [c_void_p, c_int])
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

# just something simple for now
@_LOG_CB_RETURN_T
def _log_cb_return(string: str):
    print(string.decode("utf-8"))

class LayerList():
    def __init__(self,
                 renderer: SDL_Renderer,
                 texfmt: c_uint):
        self._ll = _cg.layerlist_new(renderer.value,
                                     texfmt,
                                     _cg.log_cb_helper,
                                     _log_cb_return)

    def __del__(self):
        _cg.layerlist_free(self._ll)
