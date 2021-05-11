#include <stdio.h>

#include "testgfx.h"
#include "extramath.h"

#define CBOX_SHADOW_MIN  (1)
#define CBOX_SHADOW_MAX  (5)
#define CBOX_SHADOW_TRANSLUCENCY (128)
#define CBOX_MIN_COLOR   (0.1)
#define CBOX_MAX_COLOR   (0.4)
#define CBOX_MIN_DIM     (8)
#define CBOX_MAX_DIM     (480)
#define CBOX_MIN_AREA    (1000)
#define CBOX_MAX_AREA    (100000)
#define CBOX_MIN_SPEED   (16)
#define CBOX_MAX_SPEED   (80)
#define OPAQUE_COLOR_BOXES
#define CBOX_MIN_TIME    (1000)
#define CBOX_MAX_TIME    (5000)

#define CBOX_RAND_TIME RANDRANGE(CBOX_MIN_TIME, CBOX_MAX_TIME)

typedef enum {
    DIR_LEFT,
    DIR_RIGHT,
    DIR_UP,
    DIR_DOWN
} Direction;

typedef struct {
    int tilemap;
    int layer;
    Uint32 bgColor;
    float x, y;
    int w, h;
    int shadowOffset;
    Direction dir;
    float speed;
} ColorBoxItem;

typedef struct ColorBox_s {
    ColorBoxItem *cbox;
    unsigned int count;
    int wWidth, wHeight;
    int scale;
    unsigned int frameTime;
    LayerList *ll;
} ColorBox;

int load_graphic(LayerList *ll,
                 const char *filename,
                 unsigned int tWidth, unsigned int tHeight,
                 int *tileset,
                 int *tilemap,
                 int *layer,
                 const unsigned int *values,
                 const unsigned int *colormod,
                 unsigned int tmWidth, unsigned int tmHeight,
                 float layerScale) {
    /* load the graphic, if needed */
    if(*tileset < 0) {
        *tileset = tilemap_tileset_from_bmp(ll,
                                           filename,
                                           tWidth,
                                           tHeight);
        if(*tileset < 0) {
            fprintf(stderr, "Failed to load graphic.\n");
            return(-1);
        }
    }
    /* create the tilemap, if needed */
    if(*tilemap < 0) {
        *tilemap = tilemap_add_tilemap(ll, tmWidth, tmHeight);
        if(*tilemap < 0) {
            fprintf(stderr, "Failed to make tilemap.\n");
            return(-1);
        }
    }
    /* assign the tileset to the tilemap */
    if(tilemap_set_tilemap_tileset(ll, *tilemap, *tileset) < 0) {
        fprintf(stderr, "Failed to apply tileset to tilemap.\n");
        return(-1);
    }
    /* set up its map for the first time if needed */
    if(values != NULL) {
        if(tilemap_set_tilemap_map(ll, *tilemap, 
                                   0, 0, /* start x and y for destination rectangle */
                                   tmWidth, /* row width for source rectangle */
                                   tmWidth, tmHeight, /* size of rectangle */
                                   values, /* the values of the map rect */
                                   tmWidth * tmHeight /* number of values to expect */
                                   ) < 0) {
            fprintf(stderr, "Failed to set tilemap map.\n");
            return(-1);
        }
    }
    /* apply color modifications if needed, arguments are basically identical
     * to setting the tilemap map */
    if(colormod != NULL) {
        if(tilemap_set_tilemap_attr_colormod(ll, *tilemap,
                                             0, 0,
                                             tmWidth,
                                             tmWidth, tmHeight,
                                             colormod,
                                             tmWidth * tmHeight) < 0) {
            fprintf(stderr, "Failed to set tilemap colormod.\n");
            return(-1);
        }
    }
    /* update/"render out" the tilemap for the first time, if needed */
    if(values != NULL) {
        if(tilemap_update_tilemap(ll, *tilemap,
                                  0, 0, /* start rectangle to update */
                                  tmWidth, tmHeight /* update rectangle size */
                                  ) < 0) {
            fprintf(stderr, "Failed to update tilemap.\n");
            return(-1);
        }
    }
    /* create a layer if needed */
    if(*layer < 0) {
        *layer = tilemap_add_layer(ll, *tilemap);
        if(*layer < 0) {
            fprintf(stderr, "Failed to create layer.\n");
            return(-1);
        }

        /* don't modify a layer fed in as if it wasn't to be created */
        if(tilemap_set_layer_scale(ll, *layer, layerScale, layerScale) < 0) {
            fprintf(stderr, "Failed to set scale.\n");
            return(-1);
        }
    }

    return(0);
}

int create_sprite(LayerList *ll,
                  unsigned int spritemap,
                  unsigned int size,
                  unsigned int scale) {
    int sprite;

    sprite = tilemap_add_layer(ll, spritemap);
    if(sprite < 0) {
        fprintf(stderr, "Failed to add layer for sprite.\n");
        return(-1);
    }

    /* make the tilemap window the size of a single sprite */
    if(tilemap_set_layer_window(ll, sprite, size, size) < 0) {
        fprintf(stderr, "Failed to set sprite window size.\n");
        return(-1);
    }
    /* make the rotation center in the center of the sprite so it rotates
     * about where it aims for the cursor */
    if(tilemap_set_layer_rotation_center(ll, sprite,
                                         size / 2 * scale, size / 2 * scale) < 0) {
        fprintf(stderr, "Failed to set sprite rotation center.\n");
        return(-1);
    }
    /* Makes the sprite more visible without me having to draw a larger sprite */
    if(tilemap_set_layer_scale(ll, sprite, scale, scale) < 0) {
        fprintf(stderr, "Failed to set sprite scale.\n");
        return(-1);
    }

    return(sprite);
}

int select_sprite(LayerList *ll,
                  unsigned int layer,
                  unsigned int sprite,
                  unsigned int size) {
    if(tilemap_set_layer_scroll_pos(ll, layer,
                                    sprite * size,
                                    0) < 0) {
        fprintf(stderr, "Failed to set layer scroll for sprite.\n");
        return(-1);
    }

    return(0);
}

int position_sprite(LayerList *ll,
                    unsigned int layer,
                    int x, int y,
                    unsigned int size) {
    /* position sprite based on center */
    if(tilemap_set_layer_pos(ll, layer,
                             x - (size / 2), y - (size / 2)) < 0) {
        fprintf(stderr, "Failed to set sprite pos.\n");
        return(-1);
    }

    return(0);
}

int clear_tilemap(LayerList *ll,
                  unsigned int tilemap,
                  unsigned int w, unsigned int h) {
    unsigned int temp[w * h];
    unsigned int i;

    for(i = 0; i < w * h; i++) {
        temp[i] = ' ';
    }

    if(tilemap_set_tilemap_map(ll, tilemap,
                               0, 0,
                               w,
                               w, h,
                               temp, w * h) < 0) {
        fprintf(stderr, "Failed to set clear tilemap.\n");
        return(-1);
    }
    if(tilemap_update_tilemap(ll, tilemap,
                              0, 0,
                              w, h) < 0) {
        fprintf(stderr, "Failed to clear tilemap.\n");
        return(-1);
    }

    return(0);
}

int box_fill(SDL_Renderer *renderer, SDL_Rect *rect,
             Uint8 r, Uint8 g, Uint8 b, Uint8 a) {
    if(SDL_SetRenderDrawColor(renderer,
                              r, g, b, a) < 0) {
        fprintf(stderr, "Failed to set render draw color.\n");
        return(-1);
    } 
    if(SDL_RenderFillRect(renderer, rect) < 0) {
        fprintf(stderr, "Failed to fill rect.\n");
        return(-1);
    }
    /* needs to be transparent so tilemap updates work */
    if(SDL_SetRenderDrawColor(renderer,
                              0, 0, 0,
                              SDL_ALPHA_TRANSPARENT) < 0) {
        fprintf(stderr, "Failed to set render draw color.\n");
        return(-1);
    } 

    return(0);
}

int prepare_frame(LayerList *ll,
                  Uint8 r, Uint8 g, Uint8 b,
                  unsigned int bgLayer) {
    SDL_Renderer *renderer = layerlist_get_renderer(ll);

    /* clear the display, otherwise it'll show flickery garbage */
    if(SDL_SetRenderDrawColor(renderer,
                              0, 0, 0,
                              SDL_ALPHA_OPAQUE) < 0) {
        fprintf(stderr, "Failed to set render draw color.\n");
        return(-1);
    } 
    if(SDL_RenderClear(renderer) < 0) {
        fprintf(stderr, "Failed to clear screen.\n");
        return(-1);
    }
    if(box_fill(renderer, NULL, r, g, b, SDL_ALPHA_OPAQUE) < 0) {
        return(-1);
    }
    if(tilemap_draw_layer(ll, bgLayer) < 0) {
        fprintf(stderr, "Failed to draw background layer.\n");
        return(-1);
    }

    return(0);
}

int draw_text_layer(LayerList *ll,
                    unsigned int layer,
                    int shadowOffset,
                    Uint32 shadowColor,
                    Uint32 textColor) {
    if(tilemap_set_layer_pos(ll, layer,
                             shadowOffset, shadowOffset) < 0) {
        fprintf(stderr, "Failed to set text shadow pos.\n");
        return(-1);
    }
    if(tilemap_set_layer_blendmode(ll, layer,
                                   TILEMAP_BLENDMODE_SUB) < 0) {
        fprintf(stderr, "Failed to set text shadow blend mode.\n");
        return(-1);
    }
    if(tilemap_set_layer_colormod(ll, layer,
                                  shadowColor) < 0) {
        fprintf(stderr, "Failed to set text shadow colormod.\n");
        return(-1);
    }
    if(tilemap_draw_layer(ll, layer) < 0) {
        fprintf(stderr, "Failed to draw text shadow.\n");
        return(-1);
    }
    if(tilemap_set_layer_pos(ll, layer, 0, 0) < 0) {
        fprintf(stderr, "Failed to set text layer pos.\n");
        return(-1);
    }
    if(tilemap_set_layer_blendmode(ll, layer,
                                   TILEMAP_BLENDMODE_BLEND) < 0) {
        fprintf(stderr, "Failed to set text layer blend mode.\n");
        return(-1);
    }
    if(tilemap_set_layer_colormod(ll, layer,
                                  textColor) < 0) {
        fprintf(stderr, "Failed to set text layer colormod.\n");
        return(-1);
    }
    if(tilemap_draw_layer(ll, layer) < 0) {
        fprintf(stderr, "Failed to draw text layer.\n");
        return(-1);
    }

    return(0);
}

void fill_tilemap_with_pattern(unsigned int *values,
                               unsigned int vWidth, unsigned int vHeight,
                               const unsigned int *pattern,
                               unsigned int pWidth, unsigned int pHeight) {
    unsigned int x, y;

    for(y = 0; y < vHeight; y++) {
        for(x = 0; x < vWidth; x++) {
            values[y * vWidth + x] = 
                pattern[(y % pHeight) * pWidth + (x % pWidth)];
        }
    }
}

ColorBox *init_color_boxes(LayerList *ll, unsigned int count,
                           unsigned int wWidth, unsigned int wHeight,
                           unsigned int scale, unsigned int frameTime) {
    ColorBox *cboxes;
    unsigned int i;

    cboxes = malloc(sizeof(ColorBox));
    if(cboxes == NULL) {
        return(NULL);
    }
    cboxes->cbox = malloc(sizeof(ColorBoxItem) * count);
    if(cboxes->cbox == NULL) {
        free(cboxes);
        return(NULL);
    }

    cboxes->count = count;
    cboxes->wWidth = wWidth;
    cboxes->wHeight = wHeight;
    cboxes->scale = scale;
    cboxes->frameTime = frameTime;
    cboxes->ll = ll;

    for(i = 0; i < count; i++) {
        cboxes->cbox[i].tilemap = -1;
    }

    return(cboxes);
}

void free_color_boxes(ColorBox *cboxes) {
    unsigned int i;

    for(i = 0; i < cboxes->count; i++) {
        if(cboxes->cbox[i].tilemap == -1) {
            continue;
        }
        tilemap_free_layer(cboxes->ll, cboxes->cbox[i].layer);
        tilemap_free_tilemap(cboxes->ll, cboxes->cbox[i].tilemap);
    }

    free(cboxes->cbox);
    free(cboxes);
}

#define MAKE_COLOR_BOX_COLOR \
    color_from_angle(SCALE((double)rand(), \
                           0.0, RAND_MAX, \
                           0.0, M_PI * 2.0), \
                           0, RANDRANGE((int)(CBOX_MIN_COLOR * 255.0), \
                                        (int)(CBOX_MAX_COLOR * 255.0)))
int create_color_box(ColorBox *cboxes, int pTileset,
                     unsigned int pWidth, unsigned int pHeight,
                     const unsigned int *pattern,
                     unsigned int tWidth, unsigned int tHeight) {
    unsigned int i;
    ColorBoxItem *cbox;

    for(i = 0; i < cboxes->count; i++) {
        if(cboxes->cbox[i].tilemap == -1) {
            break;
        }
    }
    /* if there's no open slots, just do nothing and let it go around */
    if(i == cboxes->count) {
        return(CBOX_RAND_TIME);
    }
    cbox = &(cboxes->cbox[i]);

    cbox->shadowOffset = RANDRANGE(CBOX_SHADOW_MIN, CBOX_SHADOW_MAX) * cboxes->scale;
    cbox->speed = (float)RANDRANGE(CBOX_MIN_SPEED, CBOX_MAX_SPEED) * cboxes->scale * cboxes->frameTime / MILLISECOND;
    cbox->w = RANDRANGE(CBOX_MIN_DIM, CBOX_MAX_DIM) / cboxes->scale;
    cbox->h = RANDRANGE(CBOX_MIN_DIM, CBOX_MAX_DIM) / cboxes->scale;
    /* if the area is too big or small, prefer rectangles to squares */
    if(cbox->w * cbox->h > CBOX_MAX_AREA) {
        if(cbox->w > cbox->h) {
            cbox->h = CBOX_MAX_AREA / cbox->w;
        } else {
            cbox->w = CBOX_MAX_AREA / cbox->h;
        }
    } else if(cbox->w * cbox->h < CBOX_MIN_AREA) {
        if(cbox->w > cbox->h) {
            cbox->w = CBOX_MIN_AREA / cbox->h;
        } else {
            cbox->h = CBOX_MIN_AREA / cbox->w;
        }
    }
    /* prefer to go along the strip's length */
    if(cbox->w < cbox->h) {
        cbox->x = RANDRANGE(0, cboxes->wWidth - cbox->w * cboxes->scale);
        if(rand() % 2 == 0) {
            cbox->dir = DIR_DOWN;
            cbox->y = -(cbox[i].h) * cboxes->scale - cbox->shadowOffset;
        } else {
            cbox->dir = DIR_UP;
            cbox->y = cboxes->wHeight;
        }
    } else {
        cbox->y = RANDRANGE(0, cboxes->wHeight - cbox->h * cboxes->scale);
        if(rand() % 2 == 0) {
            cbox->dir = DIR_LEFT;
            cbox->x = cboxes->wWidth;
        } else {
            cbox->dir = DIR_RIGHT;
            cbox->x = -(cbox->w) * cboxes->scale - cbox->shadowOffset;
        }
    }

    cbox->bgColor = MAKE_COLOR_BOX_COLOR;
    Uint32 fgColor = MAKE_COLOR_BOX_COLOR;
    unsigned int cboxTileWidth = cbox->w / tWidth;
    if(cbox->w % tWidth > 0) {
        cboxTileWidth++;
    }
    unsigned int cboxTileHeight = cbox->h / tHeight;
    if(cbox->h % tHeight > 0) {
        cboxTileHeight++;
    }
    unsigned int cboxTilemap[cboxTileWidth * cboxTileHeight];
    fill_tilemap_with_pattern(cboxTilemap,
                              cboxTileWidth, cboxTileHeight,
                              pattern,
                              pWidth, pHeight);
    /* tilemap is already -1 */
    cbox->layer = -1;
    if(load_graphic(cboxes->ll, NULL,
                    tWidth, tHeight,
                    &pTileset, &(cbox->tilemap), &(cbox->layer),
                    cboxTilemap,
                    NULL,
                    cboxTileWidth, cboxTileHeight,
                    cboxes->scale) < 0) {
        return(-1);
    }
    if(tilemap_set_layer_blendmode(cboxes->ll, cbox->layer,
                                   TILEMAP_BLENDMODE_ADD) < 0) {
        fprintf(stderr, "Failed to set colorbox blend mode.\n");
        return(-1);
    }
    if(tilemap_set_layer_colormod(cboxes->ll, cbox->layer,
                                  fgColor) < 0) {
        fprintf(stderr, "Failed to set colorbox colormod.\n");
        return(-1);
    }
    if(tilemap_set_layer_window(cboxes->ll, cbox->layer,
                                cbox->w, cbox->h) < 0) {
        fprintf(stderr, "Failed to set colorbox window.\n");
        return(-1);
    }
    unsigned int xscroll = 0;
    unsigned int yscroll = 0;
    if(cbox->w % tWidth > 0) {
        xscroll = RANDRANGE(0, (cboxTileWidth * tWidth) - cbox->w);
    }
    if(cbox->h % tHeight > 0) {
        yscroll = RANDRANGE(0, (cboxTileHeight * tHeight) - cbox->h);
    }
    if(tilemap_set_layer_scroll_pos(cboxes->ll, cbox->layer,
                                    xscroll, yscroll) < 0) {
        fprintf(stderr, "Failed to set colorbox scroll.\n");
        return(-1);
    }

    return(CBOX_RAND_TIME);
}
#undef MAKE_COLOR_BOX_COLOR

static int free_color_box(ColorBox *cboxes, unsigned int i) {
    if(tilemap_free_layer(cboxes->ll, cboxes->cbox[i].layer) < 0) {
        fprintf(stderr, "Failed to free colorbox layer.\n");
        return(-1);
    }
    if(tilemap_free_tilemap(cboxes->ll, cboxes->cbox[i].tilemap) < 0) {
        fprintf(stderr, "Failed to free colorbox tilemap.\n");
        return(-1);
    }
    cboxes->cbox[i].tilemap = -1;

    return(0);
}

int update_color_boxes(ColorBox *cboxes) {
    unsigned int i;
    ColorBoxItem *cbox;

    for(i = 0; i < cboxes->count; i++) {
        if(cboxes->cbox[i].tilemap == -1) {
            continue;
        }
        cbox = &(cboxes->cbox[i]);

        switch(cbox->dir) {
            case DIR_LEFT:
                cbox->x -= cbox->speed;
                if(cbox->x <= -(cbox->w) * cboxes->scale - cbox->shadowOffset) {
                    if(free_color_box(cboxes, i) < 0) {
                        return(-1);
                    }
                    continue;
                }
                break;
            case DIR_RIGHT:
                cbox->x += cbox->speed;
                if(cbox->x >= cboxes->wWidth) {
                    if(free_color_box(cboxes, i) < 0) {
                        return(-1);
                    }
                    continue;
                }
                break;
            case DIR_UP:
                cbox->y -= cbox->speed;
                if(cbox->y <= -(cbox->h) * cboxes->scale - cbox->shadowOffset) {
                    if(free_color_box(cboxes, i) < 0) {
                        return(-1);
                    }
                    continue;
                }
                break;
            default: /* DIR_DOWN */
                cbox->y += cbox->speed;
                if(cbox->y >= cboxes->wHeight) {
                    if(free_color_box(cboxes, i) < 0) {
                        return(-1);
                    }
                    continue;
                }
                break;
        }
    }

    return(0);
}

int draw_color_boxes(ColorBox *cboxes) {
    unsigned int i;
    ColorBoxItem *cbox;
    SDL_Renderer *renderer = layerlist_get_renderer(cboxes->ll);

    for(i = 0; i < cboxes->count; i++) {
        if(cboxes->cbox[i].tilemap == -1) {
            continue;
        }
        cbox = &(cboxes->cbox[i]);

#ifdef OPAQUE_COLOR_BOXES
        SDL_Rect rect;

        rect.w = cbox->w * cboxes->scale;
        rect.h = cbox->h * cboxes->scale;
        rect.x = cbox->x + cbox->shadowOffset;
        rect.y = cbox->y + cbox->shadowOffset;
        if(box_fill(renderer, &rect, 0, 0, 0, CBOX_SHADOW_TRANSLUCENCY) < 0) {
            return(-1);
        }

        rect.x = cbox->x;
        rect.y = cbox->y;
        if(box_fill(renderer, &rect, TILEMAP_COLOR_R(cbox->bgColor),
                                     TILEMAP_COLOR_G(cbox->bgColor),
                                     TILEMAP_COLOR_B(cbox->bgColor),
                                     SDL_ALPHA_OPAQUE) < 0) {
            return(-1);
        }
#endif

        if(tilemap_set_layer_pos(cboxes->ll, cbox->layer,
                                 cbox->x, cbox->y) < 0) {
            fprintf(stderr, "Failed to set color box pos.\n");
            return(-1);
        }
        if(tilemap_draw_layer(cboxes->ll, cbox->layer) < 0) {
            fprintf(stderr, "Failed to draw color box layer.\n");
            return(-1);
        }
    }

    return(0);
}
