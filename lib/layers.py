import crustygame as cg
import json
import array
from dataclasses import dataclass
from enum import Enum
import lib.display as display

FONT_FILENAME="gfx/font.bmp"
FONT_MAPNAME="gfx/font.txt"
FONT_WIDTH=8
FONT_HEIGHT=8
FONT_SCALE=2.0

@dataclass
class TilemapDesc():
    name : str = "Untitled Tilemap"
    filename : str = FONT_FILENAME
    mapname : str = FONT_MAPNAME
    tw : int = FONT_WIDTH
    th : int = FONT_HEIGHT
    mw : int = 64
    mh : int = 64
    codec : str = None
    wscale : float = FONT_SCALE
    hscale : float = FONT_SCALE

class ScrollMode(Enum):
    NONE = 0
    LAYER = 1
    POSITION = 2

@dataclass
class LayerDesc():
    name : str = "Untitled Layer"
    tilemap : int = -1 
    relative : int = -1
    vw : int = 1
    vh : int = 1
    scalex : float = 1.0
    scaley : float = 1.0
    mode : ScrollMode = ScrollMode.NONE
    posx : int = 0
    posy : int = 0
    scrollx : int = 0
    scrolly : int = 0
    colormod : int = 2**32-1 # 0xFFFFFFFF opaque white
    blendmode : int = cg.TILEMAP_BLENDMODE_BLEND

def load_map(name):
    data = ""
    with open("{}.json".format(name), 'r') as infile:
        data = infile.read()
    savedata = json.loads(data)
    descs = list()
    try:
        descs = savedata['tilemaps']
        del savedata['tilemaps']
    except KeyError:
        pass
    newdescs = list()
    for desc in descs:
        newdesc = TilemapDesc()
        try:
            newdesc.name = desc['name']
            del desc['name']
        except KeyError:
            pass
        try:
            newdesc.filename = desc['gfx']
            del desc['gfx']
        except KeyError:
            pass
        try:
            newdesc.mapname = desc['unimap']
            del desc['unimap']
        except KeyError:
            pass
        try:
            newdesc.tw = desc['tile_width']
            del desc['tile_width']
        except KeyError:
            pass
        try:
            newdesc.th = desc['tile_height']
            del desc['tile_height']
        except KeyError:
            pass
        try:
            newdesc.mw = desc['map_width']
            del desc['map_width']
        except KeyError:
            pass
        try:
            newdesc.mh = desc['map_height']
            del desc['map_height']
        except KeyError:
            pass
        try:
            newdesc.wscale = desc['x_scale']
            del desc['x_scale']
        except KeyError:
            pass
        try:
            newdesc.hscale = desc['y_scale']
            del desc['y_scale']
        except KeyError:
            pass
        newdescs.append(newdesc)
    layers = list()
    newlayers = list()
    try:
        layers = savedata['layers']
        del savedata['layers']
    except KeyError:
        pass
    for layer in layers:
        newlayer = LayerDesc()
        try:
            newlayer.name = layer['name']
            del layer['name']
        except KeyError:
            pass
        try:
            newlayer.tilemap = layer['tilemap']
            del layer['tilemap']
        except KeyError:
            pass
        try:
            newlayer.relative = layer['relative']
            del layer['relative']
        except KeyError:
            pass
        try:
            newlayer.vw = layer['view_width']
            del layer['view_width']
        except KeyError:
            pass
        try:
            newlayer.vh = layer['view_height']
            del layer['view_height']
        except KeyError:
            pass
        try:
            newlayer.scalex = layer['x_scale']
            del layer['x_scale']
        except KeyError:
            pass
        try:
            newlayer.scaley = layer['y_scale']
            del layer['y_scale']
        except KeyError:
            pass
        mode = 'NONE'
        try:
            mode = layer['mode']
            del layer['mode']
        except KeyError:
            pass
        if mode == 'POSITION':
            newlayer.mode = ScrollMode.POSITION
        elif mode == 'LAYER':
            newlayer.mode = ScrollMode.LAYER
        else:
            newlayer.mode = ScrollMode.NONE
        try:
            newlayer.posx = layer['x_pos']
            del layer['x_pos']
        except KeyError:
            pass
        try:
            newlayer.posy = layer['y_pos']
            del layer['y_pos']
        except KeyError:
            pass
        try:
            newlayer.scrollx = layer['x_scroll']
            del layer['x_scroll']
        except KeyError:
            pass
        try:
            newlayer.scrolly = layer['y_scroll']
            del layer['y_scroll']
        except KeyError:
            pass
        try:
            newlayer.colormod = layer['colormod']
            del layer['colormod']
        except KeyError:
            pass
        try:
            newlayer.blendmode = layer['blend_mode']
            del layer['blend_mode']
        except KeyError:
            pass
        newlayers.append(newlayer)
    maps = list()
    for num, desc in enumerate(newdescs):
        tilemap = None
        try:
            with open("{} tilemap{}.bin".format(name, num), 'rb') as infile:
                data = infile.read()
            tilemap = array.array('I', data)
        except:
            pass
        flags = None
        try:
            with open("{} flags{}.bin".format(name, num), 'rb') as infile:
                data = infile.read()
            flags = array.array('I', data)
        except:
            pass
        colormod = None
        try:
            with open("{} colormod{}.bin".format(name, num), 'rb') as infile:
                data = infile.read()
            colormod = array.array('I', data)
        except:
            pass
        maps.append((tilemap, flags, colormod))

    return savedata, newdescs, maps, newlayers, descs, layers

class MapView():
    def _get_tileset(self, num):
        desc = self._state.add_tileset(self._tmdescs[num].filename,
                                       self._tmdescs[num].tw,
                                       self._tmdescs[num].th)
        return self._state.tileset_desc(desc)

    def _set_all(self):
        for num, desc in enumerate(self._ldescs):
            if desc.mode == ScrollMode.LAYER:
                if desc.tilemap < 0:
                    self._layers[num].pos(-(desc.posx + int(self._posx)),
                                          -(desc.posy + int(self._posy)))
                else:
                    self._layers[num].scroll((desc.scrollx + int(self._posx)) / desc.scalex,
                                             (desc.scrolly + int(self._posy)) / desc.scaley)
                    self._layers[num].update()
            elif desc.mode == ScrollMode.POSITION:
                if desc.tilemap < 0:
                    self._layers[num].pos(desc.posx + int(self._posx),
                                          desc.posy + int(self._posy))
                else:
                    self._layers[num].layer.pos(desc.posx + int(self._posx),
                                                desc.posy + int(self._posy))
                    self._layers[num].update()

    def _build_screen(self):
        self._layers = list()
        for desc in self._ldescs:
            if desc.tilemap < 0:
                l = cg.Layer(self._state.ll, None, "Preview Layer {}".format(desc.name))
                l.scale(desc.scalex, desc.scaley)
                if desc.mode == ScrollMode.LAYER:
                    l.pos(-desc.posx, -desc.posy)
                else:
                    l.pos(desc.posx, desc.posy)
                self._layers.append(l)
            else:
                vpw = desc.vw
                if vpw * desc.scalex > self._vw:
                    vpw = self._vw / desc.scalex + 1
                vph = desc.vh
                if desc.vh * desc.scaley > self._vh:
                    vph = self._vh / desc.scaley + 1
                stm = display.ScrollingTilemap(self._state.ll,
                    self._get_tileset(desc.tilemap),
                    self._maps[desc.tilemap][0],
                    vpw, vph,
                    self._tmdescs[desc.tilemap].mw,
                    self._tmdescs[desc.tilemap].mh,
                    flags=self._maps[desc.tilemap][1],
                    colormod=self._maps[desc.tilemap][2],
                    optimize=True)
                stm.scale(desc.scalex, desc.scaley)
                stm.layer.pos(desc.posx, desc.posy)
                stm.scroll(desc.scrollx, desc.scrolly)
                stm.internal.colormod(desc.colormod)
                stm.internal.blendmode(desc.blendmode)
                self._layers.append(stm)

        for num, desc in enumerate(self._ldescs):
            if desc.relative >= 0:
                layer = self._layers[num]
                if desc.tilemap >= 0:
                    layer = layer.layer

                rlayer = self._layers[desc.relative]
                if self._ldescs[desc.relative].tilemap >= 0:
                    if self._ldescs[desc.relative].mode == ScrollMode.LAYER:
                        rlayer = rlayer.layer
                    else:
                        rlayer = rlayer.maplayer

                layer.relative(rlayer)

        self._set_all()

        self._dl = display.DisplayList(self._state.ll)
        for layer in self._layers:
            self._dl.append(layer.draw)

    def __init__(self, state, tmdescs, maps, layers, vw, vh, x=0, y=0):
        self._state = state
        self._tmdescs = tmdescs
        self._maps = maps
        self._ldescs = layers
        self._vw = int(vw)
        self._vh = int(vh)
        self._posx = x
        self._posy = y
        self._build_screen()

    def resize(self, vw, vh):
        vw, vh = self._state.window
        if self._vw != vw or self._vh != vh:
            self._build_screen()

    @property
    def dl(self):
        return self._dl

    def scroll(self, x, y):
        self._posx = x
        self._posy = y
        self._set_all()

    @property
    def layer(self):
        """
        Return the first layer for use of relative placement of sprites on top
        of this map.
        
        Which means that the first layer should be the correct relative
        position and scale that sprites would be placed to.
        """
        layer = self._layers[0]
        if self._ldescs[0].tilemap >= 0:
            if self._ldescs[0].mode == ScrollMode.LAYER:
                layer = layer.layer
            else:
                layer = layer.maplayer

        return layer
