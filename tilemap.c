/*
 * Copyright 2020, 2021 paulguy <paulguy119@gmail.com>
 *
 * This file is part of uncrustygame.
 *
 * uncrustygame is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * crustygame is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with uncrustygame.  If not, see <https://www.gnu.org/licenses/>.
 */

#include <stdlib.h>

#include <SDL.h>

#include "tilemap.h"

#define FUDGE (0.0001)

#define LOG_PRINTF(LL, FMT, ...) \
    log_cb_helper((LL)->log_cb, (LL)->log_priv, \
    FMT, \
    ##__VA_ARGS__)

#define FLOAT_COMPARE(X, Y) ((X - FUDGE < Y) && (X + FUDGE > Y))

const SDL_Point ZEROZERO = {.x = 0, .y = 0};

const char *NONAME = "(unnamed)";

typedef struct {
    SDL_Texture *tex;
    unsigned int tw;
    unsigned int th;
    unsigned int maxx;
    unsigned int max;

    unsigned int refs; /* tilemaps referencing this tileset */

    char *name;
} Tileset;

typedef struct {
    int tileset;
    unsigned int w;
    unsigned int h;
    unsigned int *map;
    unsigned int *attr_flags;
    Uint32 *attr_colormod;
    SDL_Texture *tex; /* cached surface */
    SDL_Texture *tex2; /* surface for flipping between copies */

    unsigned int refs; /* layers referencing this tileset */

    char *name;
} Tilemap;

typedef struct {
    int tilemap;
    SDL_Texture *tex;
    int x;
    int y;
    int scroll_x;
    int scroll_y;
    unsigned int w;
    unsigned int h;
    unsigned int boundw;
    unsigned int boundh;
    double scale_x;
    double scale_y;
    SDL_Point center;
    double angle;
    Uint32 colormod;
    SDL_BlendMode blendMode;

    unsigned int refs;

    int rel;

    char *name;
} Layer;

typedef struct LayerList_t {
    SDL_Renderer *renderer;
    Uint32 format;
    SDL_Texture *defaultTex;
    log_cb_return_t log_cb;
    void *log_priv;
    
    Tileset *tileset;
    unsigned int tilesetsmem;

    Tilemap *tilemap;
    unsigned int tilemapsmem;

    Layer *layer;
    unsigned int layersmem;

    int blendWarned;
} LayerList;

static unsigned int find_power_of_two(unsigned int val) {
    unsigned int i;

    for(i = 1; i < val; i *= 2);

    return(i);
}

static double radian_to_degree(double radian) {
    return(radian / (M_PI * 2) * 360.0);
}

static double degree_to_radian(double degree) {
    return(degree * (M_PI * 2) / 360.0);
}

/* i don't knwo what i'm doing */
static double angle_from_xy(double x, double y) {
    if(x == 0.0) {
        if(y < 0.0) {
            return(M_PI);
        } else if(y >= 0.0) {
            return(0.0);
        }
    } else if(y == 0.0) {
        if(x < 0.0) {
            return(M_PI * 0.5);
        } else if(x > 0.0) {
            return(M_PI * 1.5);
        }
    } else if(x > 0.0 && y > 0.0) {
        if(x < y) {
            return((M_PI * 2.0) - atan(x / y));
        } else {
            return((M_PI * 1.5) + atan(y / x));
        }
    } else if(x < 0.0 && y > 0.0) {
        x = -x;
        if(x < y) {
            return(atan(x / y));
        } else {
            return((M_PI * 0.5) - atan(y / x));
        }
    } else if(x > 0.0 && y < 0.0) {
        y = -y;
        if(x < y) {
            return(M_PI + atan(x / y));
        } else {
            return((M_PI * 1.5) - atan(y / x));
        }
    }

    x = -x;
    y = -y;
    if(x < y) {
        return(M_PI - atan(x / y));
    }
    return((M_PI * 0.5) + atan(y / x));
}

/* still have no idea */
static void xy_from_angle(double *x, double *y, double angle) {
    *x = -sin(angle);
    *y = cos(angle);
}

static double distance(double x, double y) {
    return(sqrt(pow(fabs(x), 2) + powf(fabs(y), 2)));
}

int tilemap_tileset_from_bmp(LayerList *ll,
                             const char *filename,
                             unsigned int tw,
                             unsigned int th,
                             const char *name) {
    SDL_Surface *surface;
    int tileset;

    surface = SDL_LoadBMP(filename);
    if(surface == NULL) {
        LOG_PRINTF(ll, "Failed to load %s.\n", filename);
        return(-1);
    }

    tileset = tilemap_add_tileset(ll,
                                  surface,
                                  tw, th,
                                  name == NULL ? filename : name);
    SDL_FreeSurface(surface);
    return(tileset);
}

int tilemap_blank_tileset(LayerList *ll,
                          unsigned int w,
                          unsigned int h,
                          Uint32 color,
                          unsigned int tw,
                          unsigned int th,
                          const char *name) {
    SDL_Surface *surface;
    Uint32 rmask, gmask, bmask, amask;
    int bpp;
    int ret;

    if(name == NULL) {
        name = NONAME;
    }

    /* get the masks from the pixel format */
    if(SDL_PixelFormatEnumToMasks(ll->format, &bpp,
                                  &rmask, &gmask, &bmask, &amask) == SDL_FALSE) {
        LOG_PRINTF(ll, "%s: Failed to get format masks.\n", name);
        return(-1);
    }

    /* create the surface */
    surface = SDL_CreateRGBSurface(0, w, h, bpp,
                                   rmask, gmask, bmask, amask);
    if(surface == NULL) {
        LOG_PRINTF(ll, "%s: Failed to create surface.\n", name);
        return(-1);
    }

    /* fill it */
    if(SDL_FillRect(surface, NULL, color) < 0) {
        LOG_PRINTF(ll, "%s: Failed to fill surface with color.\n", name);
        return(-1);
    }

    /* create the tilemap, free the no longer needed surface and return */
    ret = tilemap_add_tileset(ll, surface, tw, th, name);
    SDL_FreeSurface(surface);
    return(ret);
}

static int debug_show_texture(LayerList *ll,
                              SDL_Texture *texture) {
    SDL_Rect src, dest;
    Uint32 format;
    int access;

    if(SDL_QueryTexture(texture,
                        &format,
                        &access,
                        &src.w,
                        &src.h) < 0) {
        LOG_PRINTF(ll, "Couldn't query texture.\n");
        return(-1);
    }
    src.x = 0; src.y = 0; dest.x = 0; dest.y = 0;
    dest.w = src.w * 2; dest.h = src.h * 2;

    if(SDL_SetRenderDrawColor(ll->renderer, 0, 0, 0, SDL_ALPHA_OPAQUE) < 0) {
        LOG_PRINTF(ll, "Couldn't set render color.\n");
        return(-1);
    }

    if(SDL_RenderClear(ll->renderer) < 0) {
        LOG_PRINTF(ll, "Couldn't clear screen.\n");
        return(-1);
    }

    if(SDL_SetRenderDrawColor(ll->renderer,
                              0, 0, 0,
                              SDL_ALPHA_TRANSPARENT) < 0) {
        LOG_PRINTF(ll, "Couldn't restore render color.\n");
        return(-1);
    }

    if(SDL_RenderCopy(ll->renderer, texture, &src, &dest) < 0) {
        LOG_PRINTF(ll, "Couldn't render texture.\n");
        return(-1);
    }
    SDL_RenderPresent(ll->renderer);

    return(0);
}

#define DEBUG_SHOW_TEXTURE(LL, TEXTURE) \
    if(debug_show_texture(LL, TEXTURE) < 0) { \
        LOG_PRINTF(LL, "Couldn't show texture.\n"); \
    }

LayerList *layerlist_new(SDL_Renderer *renderer,
                         Uint32 format,
                         log_cb_return_t log_cb,
                         void *log_priv) {
    LayerList *ll;

    ll = malloc(sizeof(LayerList));
    if(ll == NULL) {
        log_cb(log_priv, "Couldn't allocate memory for LayerList.\n");
        return(NULL);
    }

    ll->renderer = renderer;
    ll->format = format;
    /* NULL is the screen */
    ll->defaultTex = NULL;
    ll->log_cb = log_cb;
    ll->log_priv = log_priv;
    ll->tilesetsmem = 0;
    ll->tilemapsmem = 0;
    ll->layersmem = 0;
    ll->blendWarned = 0;

    return(ll);
}

void layerlist_free(LayerList *ll) {
    unsigned int i;

    if(ll->tilesetsmem > 0) {
        for(i = 0; i < ll->tilesetsmem; i++) {
            if(ll->tileset[i].tex != NULL) {
                SDL_DestroyTexture(ll->tileset[i].tex);
            }
        }
        free(ll->tileset);
    }

    if(ll->tilemapsmem > 0) {
        for(i = 0; i < ll->tilemapsmem; i++) {
            if(ll->tilemap[i].map != NULL) {
                free(ll->tilemap[i].map);
                if(ll->tilemap[i].attr_flags != NULL) {
                    free(ll->tilemap[i].attr_flags);
                }
                if(ll->tilemap[i].attr_colormod != NULL) {
                    free(ll->tilemap[i].attr_colormod);
                }
                if(ll->tilemap[i].tex != NULL) {
                    SDL_DestroyTexture(ll->tilemap[i].tex);
                }
            }
        }
        free(ll->tilemap);
    }

    if(ll->layersmem > 0) {
        free(ll->layer);
    }

    free(ll);
}

SDL_Renderer *layerlist_get_renderer(LayerList *ll) {
    return(ll->renderer);
}

void tilemap_set_default_render_target(LayerList *ll, SDL_Texture *tex) {
    ll->defaultTex = tex;
}

int tilemap_set_target_tileset(LayerList *ll, int tileset) {
    SDL_Texture *texture;

    if(tileset < 0) {
        texture = ll->defaultTex;
    } else if((unsigned int)tileset >= ll->tilesetsmem ||
              ll->tileset[tileset].tex == NULL) {
        LOG_PRINTF(ll, "Invalid tileset index.\n");
        return(-1);
    } else {
        texture = ll->tileset[tileset].tex;
    }

    if(SDL_SetRenderTarget(ll->renderer, texture) < 0) {
        LOG_PRINTF(ll, "%s: Failed to set render target: %s\n",
                       ll->tileset[tileset].name,
                       SDL_GetError());
        return(-1);
    }

    return(0);
}

static int init_tileset(LayerList *ll, Tileset *t,
                        SDL_Texture *tex,
                        unsigned int tw, unsigned int th,
                        unsigned int maxx, unsigned int maxy,
                        const char *name) {
    t->tex = tex;
    t->tw = tw;
    t->th = th;
    t->maxx = maxx;
    t->max = maxx * maxy;
    t->refs = 0;

    unsigned int namelen = strlen(name) + 1;
    t->name = malloc(namelen);
    if(t->name == NULL) {
        LOG_PRINTF(ll, "Failed to allocate memory for name for tileset %s.\n", name);
        return(-1);
    }
    strncpy(t->name, name, namelen);

    return(0);
}

int tilemap_add_tileset(LayerList *ll,
                        SDL_Surface *surface,
                        unsigned int tw,
                        unsigned int th,
                        const char *name) {
    Tileset *temp;
    SDL_Surface *surface2 = NULL;
    SDL_Texture *targetTexture;
    SDL_Texture *tex, *tex2;
    unsigned int i, j;
    unsigned int maxx, maxy;
    unsigned int texw, texh;
    SDL_Rect src, dest;
    unsigned int w = surface->w;
    unsigned int h = surface->h;

    if(name == NULL) {
        name = NONAME;
    }

    /* tiles should at least be 1x1 */
    if(tw == 0 || th == 0) {
        LOG_PRINTF(ll, "%s: Tile dimensions are 0.\n", name);
        return(-1);
    }

    /* check if there would be 0 tiles */
    if(tw > w || th > h) {
        LOG_PRINTF(ll, "%s: Tile dimensions greater than set.\n", name);
        return(-1);
    }

    maxx = w / tw;
    maxy = h / th;

    /* make sure the texture ends up being a power of two */
    texw = find_power_of_two(w);
    texh = find_power_of_two(h);
    if(w != texw || h != texh) {
        surface2 = SDL_CreateRGBSurface(0,
                                        texw,
                                        texh,
                                        32,
                                        surface->format->Rmask,
                                        surface->format->Gmask,
                                        surface->format->Bmask,
                                        surface->format->Amask);
        if(surface2 == NULL) {
            LOG_PRINTF(ll, "%s: Failed to create power of two surface.\n", name);
            return(-1);
        }
        src.x = 0; src.y = 0; src.w = surface->w; src.h = surface->h;
        dest.x = 0; dest.y = 0; dest.w = surface2->w; dest.h = surface2->h;
        if(SDL_BlitSurface(surface, &src, surface2, &dest) < 0) {
            LOG_PRINTF(ll, "%s: Failed to copy to power of two surface: %s.\n",
                           name, SDL_GetError());
            SDL_FreeSurface(surface2);
            return(-1);
        }
    } else {
        surface2 = surface;
    }

    /* create the texture */
    tex = SDL_CreateTextureFromSurface(ll->renderer, surface2);
    /* if it's not this function's surface, don't free it */
    if(surface != surface2) {
        SDL_FreeSurface(surface2);
    }
    if(tex == NULL) {
        LOG_PRINTF(ll, "%s: Failed to create texture from surface: %s.\n",
                       name, SDL_GetError());
        return(-1);
    }
    /* need to create a new texture to copy to because creating a texture from
     * a surface isn't a target texture */
    tex2 = SDL_CreateTexture(ll->renderer,
                             ll->format,
                             SDL_TEXTUREACCESS_STATIC |
                             SDL_TEXTUREACCESS_TARGET,
                             texw,
                             texh);
    if(tex2 == NULL) {
        LOG_PRINTF(ll, "%s: Failed to create texture: %s.\n",
                       name, SDL_GetError());
        SDL_DestroyTexture(tex);
        return(-1);
    }
    targetTexture = SDL_GetRenderTarget(ll->renderer);
    if(SDL_SetRenderTarget(ll->renderer, tex2) < 0) {
        LOG_PRINTF(ll, "%s: Failed to set render target to copy texture: %s.\n",
                       name, SDL_GetError());
        SDL_DestroyTexture(tex2);
        SDL_DestroyTexture(tex);
        return(-1);
    }
    if(SDL_SetTextureBlendMode(tex, SDL_BLENDMODE_NONE) < 0) {
        LOG_PRINTF(ll, "%s: Failed to set blend mode.\n", name);
        SDL_DestroyTexture(tex);
        return(-1);
    }
    if(SDL_RenderCopy(ll->renderer, tex, NULL, NULL) < 0) {
        LOG_PRINTF(ll, "%s: Failed to copy texture: %s.\n",
                       name, SDL_GetError());
        SDL_DestroyTexture(tex2);
        SDL_DestroyTexture(tex);
        return(-1);
    }
    if(SDL_SetRenderTarget(ll->renderer, targetTexture) < 0) {
        LOG_PRINTF(ll, "%s: Failed to set render target to screen: %s.\n",
                       name, SDL_GetError());
        SDL_DestroyTexture(tex2);
        SDL_DestroyTexture(tex);
        return(-1);
    }
    SDL_DestroyTexture(tex);
    tex = tex2;

    /* make values overwrite existing values */
    if(SDL_SetTextureBlendMode(tex, SDL_BLENDMODE_NONE) < 0) {
        LOG_PRINTF(ll, "%s: Failed to set blend mode.\n", name);
        SDL_DestroyTexture(tex);
        return(-1);
    }
 
    /* first loaded surface, so do some initial setup */
    if(ll->tilesetsmem == 0) {
        ll->tileset = malloc(sizeof(Tileset));
        if(ll->tileset == NULL) {
            LOG_PRINTF(ll, "%s: Failed to allocate tileset.\n", name);
            SDL_DestroyTexture(tex);
            return(-1);
        }
        ll->tilesetsmem = 1;
        if(init_tileset(ll, &(ll->tileset[0]), tex, tw, th, maxx, maxy, name) < 0) {
            return(-1);
        }
        return(0);
    }

    /* find first NULL surface and assign it */
    for(i = 0; i < ll->tilesetsmem; i++) {
        if(ll->tileset[i].tex == NULL) {
            if(init_tileset(ll, &(ll->tileset[i]), tex, tw, th, maxx, maxy, name) < 0) {
                return(-1);
            }
            return(i);
        }
    }

    /* expand buffer if there's no free slots */
    temp = realloc(ll->tileset,
            sizeof(Tileset) * ll->tilesetsmem * 2);
    if(temp == NULL) {
        LOG_PRINTF(ll, "%s: Failed to allocate tileset.\n", name);
        SDL_DestroyTexture(tex);
        return(-1);
    }
    ll->tileset = temp;
    unsigned int item = ll->tilesetsmem;
    ll->tilesetsmem *= 2;
    /* initialize empty excess surfaces as NULL */
    for(j = item; j < ll->tilesetsmem; j++) {
        ll->tileset[j].tex = NULL;
    }
    if(init_tileset(ll, &(ll->tileset[item]), tex, tw, th, maxx, maxy, name) < 0) {
        return(-1);
    }
 
    return(item);
}

static Tileset *get_tileset(LayerList *ll, unsigned int index) {
    if(index >= ll->tilesetsmem ||
       ll->tileset[index].tex == NULL) {
        LOG_PRINTF(ll, "Invalid tileset index: %u\n", index);
        return(NULL);
    }

    return(&(ll->tileset[index]));
}

static void add_tileset_ref(Tileset *ts) {
    ts->refs++;
}

static void free_tileset_ref(LayerList *ll, Tileset *ts) {
    if(ts->refs == 0) {
        LOG_PRINTF(ll, "WARNING: Attenpt to free reference to tileset %s with no references.\n", ts->name);
        return;
    }

    ts->refs--;
}

static void scan_tileset_refs(LayerList *ll, int index) {
    unsigned int i;

    LOG_PRINTF(ll, "Scanning for references...\n");
    for(i = 0; i < ll->tilemapsmem; i++) {
        if(ll->tilemap[i].map != NULL) {
            if(ll->tilemap[i].tileset == index) {
                LOG_PRINTF(ll, " %u %s\n", i, ll->tilemap[i].name);
            }
        }
    }
}

int tilemap_free_tileset(LayerList *ll, unsigned int index) {
    Tileset *ts = get_tileset(ll, index);
    if(ts == NULL) {
        return(-1);
    }
    if(ts->refs > 0) {
        LOG_PRINTF(ll, "%s: Tileset index referenced.\n", ts->name);
        scan_tileset_refs(ll, index);
        return(-1);
    }

    free(ts->name);
    SDL_DestroyTexture(ts->tex);
    ts->tex = NULL;

    return(0);
}

const char *tilemap_tileset_name(LayerList *ll, unsigned int index) {
    Tileset *ts = get_tileset(ll, index);
    if(ts == NULL) {
        return(NULL);
    }

    return(ts->name);
}

int tilemap_tileset_tiles(LayerList *ll, unsigned int index) {
    Tileset *ts = get_tileset(ll, index);
    if(ts == NULL) {
        return(-1);
    }

    return(ts->max);
}

int tilemap_tileset_tile_width(LayerList *ll, unsigned int index) {
    Tileset *ts = get_tileset(ll, index);
    if(ts == NULL) {
        return(-1);
    }

    return(ts->tw);
}

int tilemap_tileset_tile_height(LayerList *ll, unsigned int index) {
    Tileset *ts = get_tileset(ll, index);
    if(ts == NULL) {
        return(-1);
    }

    return(ts->th);
}

static int init_tilemap(LayerList *ll, Tilemap *t,
                        unsigned int tileset,
                        unsigned int w, unsigned int h,
                        const char *name) {
    t->map = malloc(sizeof(unsigned int) * w * h);
    if(t->map == NULL) {
        LOG_PRINTF(ll, "%s: Failed to allocate first tilemap map.\n", name);
        return(-1);
    }
    memset(t->map, 0, sizeof(unsigned int) * w * h);
    t->w = w;
    t->h = h;
    t->tileset = tileset;
    t->tex = NULL;
    t->tex2 = NULL;
    t->attr_flags = NULL;
    t->attr_colormod = NULL;
    t->refs = 0;

    unsigned int namelen = strlen(name) + 1;
    t->name = malloc(namelen);
    if(t->name == NULL) {
        LOG_PRINTF(ll, "%s: Failed to allocate memory for name for tilemap.\n", name);
        return(-1);
    }
    strncpy(t->name, name, namelen);

    return(0);
}

int tilemap_add_tilemap(LayerList *ll,
                        unsigned int tileset,
                        unsigned int w,
                        unsigned int h,
                        const char *name) {
    Tilemap *temp;
    unsigned int i, j;
    Tileset *ts = get_tileset(ll, tileset);
    if(ts == NULL) {
        return(-1);
    }

    if(name == NULL) {
        name = NONAME;
    }

    if(w == 0 || h == 0) {
        LOG_PRINTF(ll, "%s: Tilemap must have area.\n", name);
        return(-1);
    }

    /* first created tilemap, so do some initial setup */
    if(ll->tilemapsmem == 0) {
        ll->tilemap = malloc(sizeof(Tilemap));
        if(ll->tilemap == NULL) {
            LOG_PRINTF(ll, "%s: Failed to allocate first tilemap.\n", name);
            return(-1);
        }
        ll->tilemapsmem = 1;
        if(init_tilemap(ll, &(ll->tilemap[0]), tileset, w, h, name) < 0) {
            return(-1);
        }
        add_tileset_ref(ts);
        return(0);
    }

    /* find first NULL surface and assign it */
    for(i = 0; i < ll->tilemapsmem; i++) {
        if(ll->tilemap[i].map == NULL) {
            if(init_tilemap(ll, &(ll->tilemap[i]), tileset, w, h, name) < 0) {
                return(-1);
            }
            add_tileset_ref(ts);
            return(i);
        }
    }

    /* expand buffer if there's no free slots */
    temp = realloc(ll->tilemap,
            sizeof(Tilemap) * ll->tilemapsmem * 2);
    if(temp == NULL) {
        LOG_PRINTF(ll, "%s: Failed to expand tilemap space.\n", name);
        return(-1);
    }
    ll->tilemap = temp;
    unsigned int item = ll->tilemapsmem;
    ll->tilemapsmem *= 2;
    /* initialize empty excess surfaces as NULL */
    for(j = item; j < ll->tilemapsmem; j++) {
        ll->tilemap[j].map = NULL;
    }
 
    if(init_tilemap(ll, &(ll->tilemap[item]), tileset, w, h, name) < 0) {
        return(-1);
    }
    add_tileset_ref(ts);

    return(item);
}

static Tilemap *get_tilemap(LayerList *ll, unsigned int index) {
    if(index >= ll->tilemapsmem ||
       ll->tilemap[index].map == NULL) {
        LOG_PRINTF(ll, "Invalid tilemap index: %u\n", index);
        return(NULL);
    }

    return(&(ll->tilemap[index]));
}

static void add_tilemap_ref(Tilemap *tm) {
    tm->refs++;
}

static void free_tilemap_ref(LayerList *ll, Tilemap *tm) {
    if(tm->refs == 0) {
        LOG_PRINTF(ll, "%s: WARNING: Attenpt to free reference to tilemap with no references.\n", tm->name);
        return;
    }

    tm->refs--;
}

static void scan_tilemap_refs(LayerList *ll, int index) {
    unsigned int i;

    LOG_PRINTF(ll, "Scanning for references...\n");
    for(i = 0; i < ll->layersmem; i++) {
        if(ll->layer[i].tilemap == index) {
            LOG_PRINTF(ll, " %u %s\n", i, ll->layer[i].name);
        }
    }
}

int tilemap_free_tilemap(LayerList *ll, unsigned int index) {
    Tilemap *tm = get_tilemap(ll, index);
    if(tm == NULL) {
        return(-1);
    }
    if(tm->refs > 0) {
        LOG_PRINTF(ll, "%s: Tilemap index referenced.\n", tm->name);
        scan_tilemap_refs(ll, index);
        return(-1);
    }

    Tileset *ts = get_tileset(ll, tm->tileset);
    if(ts == NULL) {
        return(-1);
    }
    free_tileset_ref(ll, ts);

    free(tm->map);
    tm->map = NULL;
    /* free any attribute layers */
    if(tm->attr_flags != NULL) {
        free(tm->attr_flags);
        tm->attr_flags = NULL;
    }
    if(tm->attr_colormod != NULL) {
       free(tm->attr_colormod);
        tm->attr_colormod = NULL;
    }
    /* clear cached surfaces */
    if(tm->tex != NULL) {
        SDL_DestroyTexture(tm->tex);
        tm->tex = NULL;
    }
    if(tm->tex2 != NULL) {
        SDL_DestroyTexture(tm->tex2);
        tm->tex2 = NULL;
    }
    free(tm->name);

    return(0);
}

const char *tilemap_tilemap_name(LayerList *ll, unsigned int index) {
    Tilemap *tm = get_tilemap(ll, index);
    if(tm == NULL) {
        return(NULL);
    }

    return(tm->name);
}

int tilemap_set_tilemap_tileset(LayerList *ll,
                                unsigned int index,
                                unsigned int tileset) {
    Tilemap *tm = get_tilemap(ll, index);
    if(tm == NULL) {
        return(-1);
    }
    Tileset *oldts = get_tileset(ll, tm->tileset);
    if(oldts == NULL) {
        return(-1);
    }
    Tileset *newts = get_tileset(ll, tileset);
    if(newts == NULL) {
        return(-1);
    }

    /* free the old, invalid texture, because the tile size may have changed */
    if(tm->tex != NULL) {
        SDL_DestroyTexture(tm->tex);
        tm->tex = NULL;
    }

    free_tileset_ref(ll, oldts);
    add_tileset_ref(newts);
    tm->tileset = tileset;

    return(0);
}

int tilemap_set_tilemap_map(LayerList *ll,
                            unsigned int index,
                            unsigned int x,
                            unsigned int y,
                            int pitch,
                            int w,
                            int h,
                            const unsigned int *value,
                            unsigned int size) {
    unsigned int i;
    Tilemap *tm = get_tilemap(ll, index);
    if(tm == NULL) {
        return(-1);
    }

    /* Allow passing in 0s to be filled in for the whole map size, allow a
     * 0 pitch to be specified to copy the same row over each line */
    if(pitch < 0) {
        pitch = tm->w;
    }
    if(w <= 0) {
        w = tm->w;
    }
    if(h <= 0) {
        h = tm->h;
    }

    if(((((unsigned int)h - 1) * (unsigned int)pitch) +
        (unsigned int)w) > size) {
        LOG_PRINTF(ll, "%s: Buffer too small to hold tilemap.\n", tm->name);
        return(-1);
    }

    /* make sure start coordinate and end position don't go out of
     * range */
    if(x > tm->w || y > tm->h ||
       x + w > tm->w || y + h > tm->h) {
        LOG_PRINTF(ll, "%s: Position/size would expand outside of "
                       "tilemap. x:%d+%d>%d, y:%d+%d>%d\n",
                       tm->name, x, w, tm->w, y, h, tm->h);
        return(-1);
    }

    for(i = 0; i < (unsigned int)h; i++) {
        memcpy(&(tm->map[tm->w * (y + i) + x]),
               &(value[(pitch * i)]),
               sizeof(unsigned int) * w); 
    }

    return(0);
}

int tilemap_set_tilemap_attr_flags(LayerList *ll,
                                   unsigned int index,
                                   unsigned int x,
                                   unsigned int y,
                                   int pitch,
                                   int w,
                                   int h,
                                   const unsigned int *value,
                                   unsigned int size) {
    unsigned int i;
    Tilemap *tm = get_tilemap(ll, index);
    if(tm == NULL) {
        return(-1);
    }

    /* Allow passing in 0s to be filled in for the whole map size, allow a
     * 0 pitch to be specified to copy the same row over each line */
    if(pitch < 0) {
        pitch = tm->w;
    }
    if(w <= 0) {
        w = tm->w;
    }
    if(h <= 0) {
        h = tm->h;
    }

    if(((((unsigned int)h - 1) * (unsigned int)pitch) +
        (unsigned int)w) > size) {
        LOG_PRINTF(ll, "%s: Buffer too small to hold tilemap.\n", tm->name);
        return(-1);
    }

    /* make sure start coordinate and end position don't go out of
     * range */
    if(x > tm->w || y > tm->h ||
       x + w > tm->w || y + h > tm->h) {
        LOG_PRINTF(ll, "%s: Position/size would expand outside of "
                       "tilemap.\n", tm->name);
        return(-1);
    }
    
    /* allocate space for an attribute map if one doesn't exist */
    if(tm->attr_flags == NULL) {
        tm->attr_flags = malloc(sizeof(unsigned int) * tm->w * tm->h);
        if(tm->attr_flags == NULL) {
            LOG_PRINTF(ll, "%s: Failed to allocate tilemap attribute map.\n", tm->name);
            return(-1);
        }
        memset(tm->attr_flags, 0, sizeof(unsigned int) * tm->w * tm->h);
    }
 
    for(i = 0; i < (unsigned int)h; i++) {
        memcpy(&(tm->attr_flags[tm->w * (y + i) + x]),
               &(value[(pitch * i)]),
               sizeof(unsigned int) * w); 
    }

    return(0);
}

int tilemap_set_tilemap_attr_colormod(LayerList *ll,
                                      unsigned int index,
                                      unsigned int x,
                                      unsigned int y,
                                      int pitch,
                                      int w,
                                      int h,
                                      const Uint32 *value,
                                      unsigned int size) {
    unsigned int i;
    Tilemap *tm = get_tilemap(ll, index);
    if(tm == NULL) {
        return(-1);
    }

    /* Allow passing in 0s to be filled in for the whole map size, allow a
     * 0 pitch to be specified to copy the same row over each line */
    if(pitch < 0) {
        pitch = tm->w;
    }
    if(w <= 0) {
        w = tm->w;
    }
    if(h <= 0) {
        h = tm->h;
    }

    if(((((unsigned int)h - 1) * (unsigned int)pitch) +
        (unsigned int)w) > size) {
        LOG_PRINTF(ll, "%s: Buffer too small to hold tilemap.\n", tm->name);
        return(-1);
    }

    /* make sure start coordinate and end position don't go out of
     * range */
    if(x > tm->w || y > tm->h ||
       x + w > tm->w || y + h > tm->h) {
        LOG_PRINTF(ll, "%s: Position/size would expand outside of "
                       "tilemap.\n", tm->name);
        return(-1);
    }
    
    /* allocate space for an attribute map if one doesn't exist */
    if(tm->attr_colormod == NULL) {
        tm->attr_colormod =
            malloc(sizeof(unsigned int) * tm->w * tm->h);
        if(tm->attr_colormod == NULL) {
            LOG_PRINTF(ll, "%s: Failed to allocate tilemap attribute map.\n", tm->name);
            return(-1);
        }
        memset(tm->attr_colormod, 0,
               sizeof(unsigned int) * tm->w * tm->h);
    }
 
    for(i = 0; i < (unsigned int)h; i++) {
        memcpy(&(tm->attr_colormod[tm->w * (y + i) + x]),
               &(value[(pitch * i)]),
               sizeof(unsigned int) * w); 
    }

    return(0);
}

static SDL_Texture *make_texture(LayerList *ll,
                                 Tilemap *tm,
                                 Tileset *ts) {
    SDL_Texture *tex;
    unsigned int texw = find_power_of_two(tm->w * ts->tw);
    unsigned int texh = find_power_of_two(tm->h * ts->th);
    SDL_Texture *targetTexture = SDL_GetRenderTarget(ll->renderer);

    tex = SDL_CreateTexture(ll->renderer,
                            ll->format,
                            SDL_TEXTUREACCESS_STATIC |
                            SDL_TEXTUREACCESS_TARGET,
                            texw, texh);
    if(tex == NULL) {
        LOG_PRINTF(ll, "%s: Failed to create texture.\n", tm->name);
        return(NULL);
    }
    if(SDL_SetRenderTarget(ll->renderer, tex) < 0) {
        LOG_PRINTF(ll, "%s: Failed to set render target: %s.\n",
                       tm->name, SDL_GetError());
        SDL_DestroyTexture(tex);
        return(NULL);
    }
    if(SDL_RenderClear(ll->renderer) < 0) {
        LOG_PRINTF(ll, "%s: Failed to clear texture.\n", tm->name);
        if(SDL_SetRenderTarget(ll->renderer, targetTexture) < 0) {
            LOG_PRINTF(ll, "%s: Failed to restore render target: %s.\n",
                           tm->name, SDL_GetError());
            return(NULL);
        }
        SDL_DestroyTexture(tex);
        return(NULL);
    }

    return(tex);
}

int tilemap_copy_block(LayerList *ll,
                       unsigned int index,
                       unsigned int x,
                       unsigned int y,
                       unsigned int w,
                       unsigned int h,
                       unsigned int dx,
                       unsigned int dy,
                       unsigned int valid_outside_copy) {
    unsigned int i;
    SDL_Texture *targetTexture;
    SDL_Rect srcrect, dstrect;
#ifdef COPY_FIX
    SDL_Texture *temp;
#endif
    Tilemap *tm = get_tilemap(ll, index);
    if(tm == NULL) {
        return(-1);
    }
    Tileset *ts = get_tileset(ll, tm->tileset);
    if(ts == NULL) {
        return(-1);
    }

    if(x + w > tm->w || y + h > tm->h) {
        LOG_PRINTF(ll, "Source position/size beyond tilemap size.");
        return(-1);
    }

    if(dx + w > tm->w || dy + h > tm->h) {
        LOG_PRINTF(ll, "Destination position/size beyond tilemap size.");
        return(-1);
    }

    for(i = 0; i < (unsigned int)h; i++) {
        memmove(&(tm->map[tm->w * (dy + i) + dx]),
                &(tm->map[tm->w * ( y + i) +  x]),
                sizeof(unsigned int) * w); 
    }

    if(tm->tex != NULL) {
        x *= ts->tw; dx *= ts->tw; w *= ts->tw;
        y *= ts->th; dy *= ts->th; h *= ts->th;

        targetTexture = SDL_GetRenderTarget(ll->renderer);
        if(tm->tex2 == NULL) {
#ifdef COPY_FIX
            if(SDL_SetRenderDrawColor(ll->renderer,
                                      0, 0, 0,
                                      SDL_ALPHA_TRANSPARENT) < 0) {
                LOG_PRINTF(ll, "%s: Failed to set render draw color.\n", tm->name);
                return(-1);
            }

            tm->tex2 = make_texture(ll, tm, ts);
            if(tm->tex2 == NULL) {
                return(-1);
            }
#else
            tm->tex2 = tm->tex;
            if(SDL_SetRenderTarget(ll->renderer, tm->tex2) < 0) {
                LOG_PRINTF(ll, "%s: Failed to set render target: %s.\n",
                               tm->name, SDL_GetError());
                return(-1);
            }
#endif
        } else {
            if(SDL_SetRenderTarget(ll->renderer, tm->tex2) < 0) {
                LOG_PRINTF(ll, "%s: Failed to set render target: %s.\n",
                               tm->name, SDL_GetError());
                return(-1);
            }
        }

        if(SDL_SetTextureBlendMode(tm->tex, SDL_BLENDMODE_NONE) < 0) {
            LOG_PRINTF(ll, "%s: Failed to set blendmode.\n", tm->name);
            return(-1);
        }

#ifdef COPY_FIX
        if(valid_outside_copy != 0) {
            if(SDL_RenderCopy(ll->renderer,
                              tm->tex,
                              NULL,
                              NULL) < 0) {
                LOG_PRINTF(ll, "%s: Failed to render copy.\n", tm->name);
                return(-1);
            }
        }
#endif

        srcrect.x =  x; srcrect.y =  y; srcrect.w = w; srcrect.h = h;
        dstrect.x = dx, dstrect.y = dy; dstrect.w = w; dstrect.h = h;
        if(SDL_RenderCopy(ll->renderer,
                          tm->tex,
                          &srcrect,
                          &dstrect) < 0) {
            LOG_PRINTF(ll, "%s: Failed to render copy.\n", tm->name);
            return(-1);
        }

        if(SDL_SetRenderTarget(ll->renderer, targetTexture) < 0) {
            LOG_PRINTF(ll, "%s: Failed to restore render target: %s.\n",
                           tm->name, SDL_GetError());
            return(-1);
        }

#ifdef COPY_FIX
        temp = tm->tex;
        tm->tex = tm->tex2;
        tm->tex2 = temp;
#endif
    }

    return(0);
}

int tilemap_update_tilemap(LayerList *ll,
                           unsigned int index,
                           unsigned int x,
                           unsigned int y,
                           unsigned int w,
                           unsigned int h) {
    unsigned int i, j;
    SDL_Rect dest, src, finaldest;
    unsigned int attr;
    Uint32 colormod;
    double angle;
    SDL_RendererFlip flip;
    SDL_Texture *targetTexture;
    Tilemap *tm = get_tilemap(ll, index);
    if(tm == NULL) {
        return(-1);
    }
    Tileset *ts = get_tileset(ll, tm->tileset);
    if(ts == NULL) {
        return(-1);
    }

    /* Allow passing in 0s to be filled in for the whole map size */
    if(w == 0) {
        w = tm->w;
    }
    if(h == 0) {
        h = tm->h;
    }

    /* make sure the range specified is within the map */
    if(x > tm->w || x + w > tm->w ||
       y > tm->h || y + h > tm->h) {
        LOG_PRINTF(ll, "%s: Dimensions extend outside of tilemap.\n", tm->name);
        return(-1);
    }

    targetTexture = SDL_GetRenderTarget(ll->renderer);

    if(SDL_SetRenderDrawColor(ll->renderer,
                              0, 0, 0,
                              SDL_ALPHA_TRANSPARENT) < 0) {
        LOG_PRINTF(ll, "%s: Failed to set render draw color.\n", tm->name);
        return(-1);
    }

    /* create the surface if it doesn't exist */
    if(tm->tex == NULL) {
        /* texture will be made the render target */
        tm->tex = make_texture(ll, tm, ts);
        if(tm->tex == NULL) {
            return(-1);
        }
    } else {
        /* set it to be rendered to */
        if(SDL_SetRenderTarget(ll->renderer, tm->tex) < 0) {
            LOG_PRINTF(ll, "%s: Failed to set render target: %s.\n",
                           tm->name, SDL_GetError());
            return(-1);
        }

        dest.x = x * ts->tw; dest.y = y * ts->th;
        dest.w = w * ts->tw; dest.h = h * ts->th;
        if(SDL_RenderFillRect(ll->renderer, &dest) < 0) {
            LOG_PRINTF(ll, "%s: Failed to clear region.\n", tm->name);
            return(-1);
        }
    }

    /* blit each tile to the tilemap */
    src.w = ts->tw; src.h = ts->th; src.y = 0;
    dest.w = src.w; dest.h = src.h;
    dest.x = dest.w * x; dest.y = dest.h * y;
    for(j = y; j < y + h; j++) {
        dest.x = dest.w * x;
        for(i = x; i < x + w; i++) {
            src.x = tm->map[tm->w * j + i];
            /* check to see if index is within tileset */
            /* src.x can't be negative, because tm->map is unsigned,
             * silences a warning */
            if((unsigned int)(src.x) >= ts->max) {
                LOG_PRINTF(ll, "%s: Tilemap index beyond tileset %s: %u\n", tm->name, ts->name, src.x);
                return(-1);
            }
            /* calculate the source texture coords and render */
            src.y = src.x / ts->maxx;
            src.x %= ts->maxx;
            src.x *= ts->tw; src.y *= ts->th;
            if(tm->attr_colormod) {
                colormod = tm->attr_colormod[tm->w * j + i];
                if(SDL_SetTextureColorMod(ts->tex,
                        (colormod & TILEMAP_RMASK) >> TILEMAP_RSHIFT,
                        (colormod & TILEMAP_GMASK) >> TILEMAP_GSHIFT,
                        (colormod & TILEMAP_BMASK) >> TILEMAP_BSHIFT) < 0) {
                    LOG_PRINTF(ll, "%s: Failed to set tile colormod.\n", tm->name);
                    return(-1);
                }
                if(SDL_SetTextureAlphaMod(ts->tex,
                        (colormod & TILEMAP_AMASK) >> TILEMAP_ASHIFT) < 0) {
                    LOG_PRINTF(ll, "%s: Failed to set tile alphamod.\n", tm->name);
                    return(-1);
                }
            }
            if(tm->attr_flags &&
               tm->attr_flags[tm->w * j + i] != 0) {
                attr = tm->attr_flags[tm->w * j + i];
                memcpy(&finaldest, &dest, sizeof(SDL_Rect));
                flip = SDL_FLIP_NONE;
                if(attr & TILEMAP_HFLIP_MASK) {
                    flip |= SDL_FLIP_HORIZONTAL;
                }
                if(attr & TILEMAP_VFLIP_MASK) {
                    flip |= SDL_FLIP_VERTICAL;
                }
                if((attr & TILEMAP_ROTATE_MASK) == TILEMAP_ROTATE_NONE) {
                    angle = 0.0;
                } else if((attr & TILEMAP_ROTATE_MASK) == TILEMAP_ROTATE_90) {
                    if(ts->tw != ts->th) {
                        LOG_PRINTF(ll, "%s: Invalid rotation for rectangular "
                                       "tilemap.\n", tm->name);
                        return(-1);
                    }
                    angle = 90.0;
                    finaldest.x += ts->tw;
                } else if((attr & TILEMAP_ROTATE_MASK) == TILEMAP_ROTATE_180) {
                    angle = 180.0;
                    finaldest.x += ts->tw;
                    finaldest.y += ts->th;
                } else { /* TILEMAP_ROTATE_270 */
                     if(ts->tw != ts->th) {
                        LOG_PRINTF(ll, "%s: Invalid rotation for rectangular "
                                       "tilemap.\n", tm->name);
                        return(-1);
                    }
                    angle = 270.0;
                    finaldest.y += ts->th;
                }
                if(SDL_RenderCopyEx(ll->renderer,
                                    ts->tex,
                                    &src,
                                    &finaldest,
                                    angle,
                                    &ZEROZERO,
                                    flip) < 0) {
                    LOG_PRINTF(ll, "%s: Failed to render tile.\n", tm->name);
                    return(-1);
                }
            } else {
                if(SDL_RenderCopy(ll->renderer,
                                  ts->tex,
                                  &src,
                                  &dest) < 0) {
                    LOG_PRINTF(ll, "%s: Failed to render tile.\n", tm->name);
                    return(-1);
                }
            }
            if(tm->attr_colormod) {
                if(SDL_SetTextureColorMod(ts->tex, 255, 255, 255) < 0) {
                    LOG_PRINTF(ll, "%s: Failed to set tile colormod.\n", tm->name);
                    return(-1);
                }
                if(SDL_SetTextureAlphaMod(ts->tex, 255) < 0) {
                    LOG_PRINTF(ll, "%s: Failed to set tile alphamod.\n", tm->name);
                    return(-1);
                }
            }
            dest.x += dest.w;
        }
        dest.y += dest.h;
    }

    /* restore render target */
    if(SDL_SetRenderTarget(ll->renderer, targetTexture) < 0) {
        LOG_PRINTF(ll, "%s: Failed to restore render target.\n", tm->name);
        return(-1);
    }

    return(0);
}

static int init_layer(LayerList *ll,
                      Layer *l,
                      unsigned int w,
                      unsigned int h,
                      unsigned int tilemap,
                      SDL_Texture *tex,
                      const char *name) {
    l->x = 0;
    l->y = 0;
    l->w = w;
    l->h = h;
    l->boundw = w;
    l->boundh = h;
    l->scroll_x = 0;
    l->scroll_y = 0;
    l->scale_x = 1.0;
    l->scale_y = 1.0;
    l->center.x = 0;
    l->center.y = 0;
    l->angle = 0.0;
    l->colormod = TILEMAP_COLOR(255, 255, 255, 255);
    l->blendMode = SDL_BLENDMODE_BLEND;
    l->tilemap = tilemap;
    l->tex = tex;
    l->rel = -1;
    l->refs = 0;

    unsigned int namelen = strlen(name) + 1;
    l->name = malloc(namelen);
    if(l->name == NULL) {
        LOG_PRINTF(ll, "Failed to allocate memory for name for layer %s.\n", name);
        return(-1);
    }
    strncpy(l->name, name, namelen);

    return(0);
}

int tilemap_add_layer(LayerList *ll,
                      unsigned int tilemap,
                      SDL_Texture *tex,
                      const char *name) {
    Layer *temp;
    int junk;
    unsigned int i, j;
    int w, h;
    Tilemap *tm;
    Tileset *ts;
    if(tex == NULL) {
        tm = get_tilemap(ll, tilemap);
        if(tm == NULL) {
            return(-1);
        }
        ts = get_tileset(ll, tm->tileset);
        if(ts == NULL) {
            return(-1);
        }
        w = tm->w * ts->tw;
        h = tm->h * ts->th;
    } else {
        tm = NULL;
        ts = NULL;
        if(SDL_QueryTexture(tex, (Uint32 *)(&junk), &junk, &w, &h) < 0) {
            LOG_PRINTF(ll, "Failed to query texture dimensions.\n");
            return(-1);
        }
    }

    if(name == NULL) {
        name = NONAME;
    }

    /* first created layer, so do some initial setup */
    if(ll->layersmem == 0) {
        ll->layer = malloc(sizeof(Layer));
        if(ll->layer == NULL) {
            LOG_PRINTF(ll, "%s: Failed to allocate first layer.\n", name);
            return(-1);
        }
        ll->layersmem = 1;
        if(init_layer(ll, &(ll->layer[0]), w, h, tilemap, tex, name) < 0) {
            return(-1);
        }
        if(tm != NULL) {
            add_tilemap_ref(tm);
        }
        return(0);
    }

    /* find first NULL surface and assign it */
    for(i = 0; i < ll->layersmem; i++) {
        if(ll->layer[i].tilemap == -1 &&
           ll->layer[i].tex == NULL) {
            if(init_layer(ll, &(ll->layer[i]), w, h, tilemap, tex, name) < 0) {
                return(-1);
            }
            if(tm != NULL) {
                add_tilemap_ref(tm);
            }
            return(i);
        }
    }

    /* expand buffer if there's no free slots */
    temp = realloc(ll->layer,
            sizeof(Layer) * ll->layersmem * 2);
    if(temp == NULL) {
        LOG_PRINTF(ll, "%s: Failed to expand layer memory.\n", name);
        return(-1);
    }
    ll->layer = temp;
    unsigned int item = ll->layersmem;
    ll->layersmem *= 2;
    /* initialize empty excess surfaces as NULL */
    for(j = item; j < ll->layersmem; j++) {
        ll->layer[j].tilemap = -1;
        ll->layer[j].tex = NULL;
    }
 
    if(init_layer(ll, &(ll->layer[item]), w, h, tilemap, tex, name) < 0) {
        return(-1);
    }
    if(tm != NULL) {
        add_tilemap_ref(tm);
    }

    return(item);
}

static Layer *get_layer(LayerList *ll, unsigned int index) {
    if(index >= ll->layersmem ||
       (ll->layer[index].tilemap == -1 &&
        ll->layer[index].tex == NULL)) {
        LOG_PRINTF(ll, "Invalid layer index.\n");
        return(NULL);
    }

    return(&(ll->layer[index]));
}

static void add_layer_ref(Layer *l) {
    l->refs++;
}

static void free_layer_ref(LayerList *ll, Layer *l) {
    if(l->refs == 0) {
        LOG_PRINTF(ll, "%s: WARNING: Attenpt to free reference to layer with no references.\n", l->name);
        return;
    }

    l->refs--;
}

static void scan_layer_refs(LayerList *ll, int index) {
    unsigned int i;

    LOG_PRINTF(ll, "Scanning for references...\n");
    for(i = 0; i < ll->layersmem; i++) {
        if(ll->layer[i].rel == index) {
            LOG_PRINTF(ll, " %u %s\n", i, ll->layer[i].name);
        }
    }
}

int tilemap_free_layer(LayerList *ll, unsigned int index) {
    Layer *l = get_layer(ll, index);
    if(l == NULL) {
        return(-1);
    }
    if(l->refs > 0) {
        LOG_PRINTF(ll, "%s: Layer index referenced.\n", l->name);
        scan_layer_refs(ll, index);
        return(-1);
    }

    if(l->tilemap >= 0) {
        Tilemap *tm = get_tilemap(ll, l->tilemap);
        if(tm == NULL) {
            return(-1);
        }
        free_tilemap_ref(ll, tm);
    }

    free(l->name);
    l->tilemap = -1;
    l->tex = NULL;

    return(0);
}

const char *tilemap_layer_name(LayerList *ll, unsigned int index) {
    Layer *l = get_layer(ll, index);
    if(l == NULL) {
        return(NULL);
    }

    return(l->name);
}

int tilemap_set_layer_pos(LayerList *ll, unsigned int index, int x, int y) {
    Layer *l = get_layer(ll, index);
    if(l == NULL) {
        return(-1);
    }

    l->x = x;
    l->y = y;

    return(0);
}

int tilemap_set_layer_window(LayerList *ll,
                             unsigned int index,
                             unsigned int w,
                             unsigned int h) {
    Layer *l = get_layer(ll, index);
    if(l == NULL) {
        return(-1);
    }

    /* Allow passing in 0s to be reset to full size */
    if(w == 0) {
        w = l->boundw;
    }
    if(h == 0) {
        h = l->boundh;
    }

    if(l->scroll_x + w >= l->boundw * 2 ||
       l->scroll_y + h >= l->boundh * 2) {
        LOG_PRINTF(ll, "%s: Layer window out of range. (%u > %u) or (%u > %u)\n", l->name, w, l->boundw, h, l->boundh);
        return(-1);
    }
 
    l->w = w;
    l->h = h;

    return(0);
}

int tilemap_set_layer_scroll_pos(LayerList *ll,
                                 unsigned int index,
                                 unsigned int scroll_x,
                                 unsigned int scroll_y) {
    Layer *l = get_layer(ll, index);
    if(l == NULL) {
        return(-1);
    }

    if(scroll_x + l->w >= l->boundw * 2 ||
       scroll_y * l->h >= l->boundh * 2) {
        LOG_PRINTF(ll, "%s: Layer scroll pos out of range.\n", l->name);
        return(-1);
    }
 
    l->scroll_x = scroll_x;
    l->scroll_y = scroll_y;

    return(0);
}

int tilemap_set_layer_scale(LayerList *ll,
                            unsigned int index,
                            double scale_x,
                            double scale_y) {
    Layer *l = get_layer(ll, index);
    if(l == NULL) {
        return(-1);
    }

    /* SDL doesn't seem to allow negative rect coords and just clamps to 0 so
     * to avoid unexpected behavior, just throw a warning to the user. */
    if(scale_x < 0.0 || scale_y < 0.0) {
        LOG_PRINTF(ll, "%s: WARNING: Negative scale.\n", l->name);
    }

    l->scale_x = scale_x;
    l->scale_y = scale_y;

    return(0);
}

int tilemap_set_layer_rotation_center(LayerList *ll, unsigned int index, int x, int y) {
    Layer *l = get_layer(ll, index);
    if(l == NULL) {
        return(-1);
    }

    l->center.x = x;
    l->center.y = y;

    return(0);
}

int tilemap_set_layer_rotation(LayerList *ll, unsigned int index, double angle) {
    Layer *l = get_layer(ll, index);
    if(l == NULL) {
        return(-1);
    }

    /* SDL wants degrees but the math works best with radians */
    l->angle = degree_to_radian(angle);

    return(0);
}

int tilemap_set_layer_colormod(LayerList *ll, unsigned int index, Uint32 colormod) {
    Layer *l = get_layer(ll, index);
    if(l == NULL) {
        return(-1);
    }

    l->colormod = colormod;

    return(0);
}

int tilemap_set_layer_blendmode(LayerList *ll, unsigned int index, int blendMode) {
    Layer *l = get_layer(ll, index);
    if(l == NULL) {
        return(-1);
    }

    switch(blendMode) {
        case TILEMAP_BLENDMODE_BLEND:
            l->blendMode = SDL_BLENDMODE_BLEND;
            break;
        case TILEMAP_BLENDMODE_ADD:
            l->blendMode = SDL_BLENDMODE_ADD;
            break;
        case TILEMAP_BLENDMODE_MOD:
            l->blendMode = SDL_BLENDMODE_MOD;
            break;
        case TILEMAP_BLENDMODE_MUL:
            l->blendMode = SDL_BLENDMODE_MUL;
            break;
        case TILEMAP_BLENDMODE_SUB:
            l->blendMode =
                SDL_ComposeCustomBlendMode(SDL_BLENDFACTOR_SRC_ALPHA,
                                           SDL_BLENDFACTOR_ONE,
                                           SDL_BLENDOPERATION_REV_SUBTRACT,
                                           SDL_BLENDFACTOR_ZERO,
                                           SDL_BLENDFACTOR_ONE,
                                           SDL_BLENDOPERATION_ADD);
            break;
        default:
            LOG_PRINTF(ll, "%s: Invalid blend mode: %d\n", l->name, blendMode);
            return(-1);
    }

    return(0);
}

int tilemap_set_layer_relative(LayerList *ll, unsigned int index, int rel) {
    Layer *l = get_layer(ll, index);
    if(l == NULL) {
        return(-1);
    }
    Layer *rl = NULL;
    if(rel >= 0) {
        rl = get_layer(ll, (unsigned int)rel);
        if(rl == NULL) {
            return(-1);
        }
        add_layer_ref(rl);
    }

    Layer *next;
    for(next = rl; next != NULL; next = &(ll->layer[next->rel])) {
        if(l == next) {
            LOG_PRINTF(ll, "%s: layer %s would point to itself.", l->name, rl->name);
            return(-1);
        }
    }

    if(l->rel >= 0) {
        free_layer_ref(ll, get_layer(ll, l->rel));
    }

    l->rel = rel;

    return(0);
}

static void get_relative_pos(double *x, double *y,
                             double *angle,
                             double *scale_x, double *scale_y,
                             LayerList *ll, Layer *l) {
    *x = 0.0;
    *y = 0.0;
    *angle = 0.0;
    *scale_x = 1.0;
    *scale_y = 1.0;
    Layer *this = l;
    while(this->rel >= 0) {
        Layer *prev = get_layer(ll, this->rel);

        double cdist = distance(prev->center.x, prev->center.y);
        /* angle from center to corner */
        double cangle = angle_from_xy(-(prev->center.x),
                                      -(prev->center.y)); 
        cangle -= prev->angle;
        double relx, rely;
        xy_from_angle(&relx, &rely, cangle);
        relx *= cdist;
        rely *= cdist;
        relx -= prev->center.x;
        rely -= prev->center.y;
        double pdist = distance(this->x - prev->center.x,
                                this->y - prev->center.y);
        double pangle = angle_from_xy(this->x - prev->center.x,
                                      this->y - prev->center.y);
        pangle += prev->angle;
        double nextx, nexty;
        xy_from_angle(&nextx, &nexty, pangle);
        nextx *= pdist;
        nexty *= pdist;
        nextx += prev->center.x;
        nexty += prev->center.y;
        *x += relx + nextx;
        *y += rely + nexty;
        *angle += this->angle;
        *scale_x *= this->scale_x;
        *scale_y *= this->scale_y;
        *x *= prev->scale_x;
        *y *= prev->scale_y;

        this = prev;
    }

   *x += this->x;
   *y += this->y;
   *angle += this->angle;
   *scale_x *= this->scale_x;
   *scale_y *= this->scale_y;
}

int tilemap_draw_layer(LayerList *ll, unsigned int index) {
    SDL_Rect dest, src;
    unsigned int right, bottom;
    int overRight, overBottom;
    int remainRight, remainBottom;
    SDL_Texture *tex;
    double x, y, angle, scale_x, scale_y;
    Layer *l = get_layer(ll, index);
    if(l == NULL) {
        return(-1);
    }

    if(l->tex == NULL) {
        Tilemap *tm = get_tilemap(ll, l->tilemap);
        if(tm == NULL) {
            return(-1);
        }

        /* Make sure it's a layer with graphics */
        if(tm->tex == NULL) {
            LOG_PRINTF(ll, "%s: Layer without graphics: %d\n", l->name, index);
            return(-1);
        }

        tex = tm->tex;
    } else {
        tex = l->tex;
    }

    if(SDL_SetTextureColorMod(tex,
            (l->colormod & TILEMAP_RMASK) >> TILEMAP_RSHIFT,
            (l->colormod & TILEMAP_GMASK) >> TILEMAP_GSHIFT,
            (l->colormod & TILEMAP_BMASK) >> TILEMAP_BSHIFT) < 0) {
        LOG_PRINTF(ll, "%s: Failed to set layer colormod.\n", l->name);
        return(-1);
    }
    if(SDL_SetTextureAlphaMod(tex,
            (l->colormod & TILEMAP_AMASK) >> TILEMAP_ASHIFT) < 0) {
        LOG_PRINTF(ll, "%s: Failed to set tile alphamod.\n", l->name);
        return(-1);
    }

    if(SDL_SetTextureBlendMode(tex, l->blendMode) < 0) {
        if(ll->blendWarned == 0) {
            LOG_PRINTF(ll, "Failed to set layer blend mode, falling back to "
                           "SDL_BLENDMODE_BLEND, some things may appear "
                           "wrong. This warning will appear only once.\n");
            ll->blendWarned = 1;
        }
        SDL_SetTextureBlendMode(tex, SDL_BLENDMODE_BLEND);
    }
    right = l->scroll_x + l->w;
    bottom = l->scroll_y + l->h;
    overRight = right - l->boundw;
    overBottom = bottom - l->boundh;
    remainRight = l->w - overRight;
    remainBottom = l->h - overBottom;

    get_relative_pos(&x, &y, &angle, &scale_x, &scale_y, ll, l);
    /* SDL wants degrees */
    angle = radian_to_degree(angle);

    src.x = l->scroll_x;
    src.y = l->scroll_y;
    src.w = overRight > 0 ? remainRight : (int)(l->w);
    src.h = overBottom > 0 ? remainBottom : (int)(l->h);
    dest.x = x;
    dest.y = y;
    dest.w = src.w * scale_x;
    dest.h = src.h * scale_y;
    if(FLOAT_COMPARE(angle, 0.0)) {
        if(SDL_RenderCopy(ll->renderer, tex, &src, &dest) < 0) {
            LOG_PRINTF(ll, "%s: Failed to render layer.\n", l->name);
            return(-1);
        }
        if(overRight > 0) {
            src.x = 0;
            src.y = l->scroll_y;
            src.w = overRight;
            src.h = overBottom > 0 ? remainBottom : (int)(l->h);
            dest.x = x + (remainRight * scale_x);
            dest.y = y;
            dest.w = src.w * scale_x;
            dest.h = src.h * scale_y;
            if(SDL_RenderCopy(ll->renderer, tex, &src, &dest) < 0) {
                LOG_PRINTF(ll, "%s: Failed to render layer.\n", l->name);
                return(-1);
            }
        }
        if(overBottom > 0) {
            src.x = l->scroll_x;
            src.y = 0;
            src.w = overRight > 0 ? remainRight : (int)(l->w);
            src.h = overBottom;
            dest.x = x;
            dest.y = y + (remainBottom * scale_y);
            dest.w = src.w * scale_x;
            dest.h = src.h * scale_y;
            if(SDL_RenderCopy(ll->renderer, tex, &src, &dest) < 0) {
                LOG_PRINTF(ll, "%s: Failed to render layer.\n", l->name);
                return(-1);
            }
        }
        if(overRight > 0 && overBottom > 0) {
            src.x = 0;
            src.y = 0;
            src.w = overRight;
            src.h = overBottom;
            dest.x = x + (remainRight * scale_x);
            dest.y = y + (remainBottom * scale_y);
            dest.w = src.w * scale_x;
            dest.h = src.h * scale_y;
            if(SDL_RenderCopy(ll->renderer, tex, &src, &dest) < 0) {
                LOG_PRINTF(ll, "%s: Failed to render layer.\n", l->name);
                return(-1);
            }
        }
    } else {
        if(SDL_RenderCopyEx(ll->renderer, tex,
                            &src, &dest,
                            angle, &(l->center),
                            SDL_FLIP_NONE) < 0) {
            LOG_PRINTF(ll, "%s: Failed to render layer.\n", l->name);
            return(-1);
        }
    }

    return(0);
}
