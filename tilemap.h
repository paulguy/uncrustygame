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
 * uncrustygame is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with uncrustygame.  If not, see <https://www.gnu.org/licenses/>.
 */

#ifndef _TILEMAP_H
#define _TILEMAP_H

#include <SDL.h>

#define TILEMAP_HFLIP_MASK (0x01)
#define TILEMAP_VFLIP_MASK (0x02)
#define TILEMAP_ROTATE_MASK (0x0C)
#define TILEMAP_ROTATE_NONE (0x00)
#define TILEMAP_ROTATE_90   (0x04)
#define TILEMAP_ROTATE_180  (0x08)
#define TILEMAP_ROTATE_270  (0x0C)

#define TILEMAP_BLENDMODE_BLEND (0)
#define TILEMAP_BLENDMODE_ADD   (1)
#define TILEMAP_BLENDMODE_MOD   (2)
#define TILEMAP_BLENDMODE_MUL   (3)
#define TILEMAP_BLENDMODE_SUB   (4)

/* comment that was here doesn't matter, this is just for creating colormod
 * values which are converted to what they should be internally */
#define TILEMAP_BSHIFT (24)
#define TILEMAP_BMASK (0xFF << TILEMAP_BSHIFT)
#define TILEMAP_GSHIFT (16)
#define TILEMAP_GMASK (0xFF << TILEMAP_GSHIFT)
#define TILEMAP_RSHIFT (8)
#define TILEMAP_RMASK (0xFF << TILEMAP_RSHIFT)
#define TILEMAP_ASHIFT (0)
#define TILEMAP_AMASK (0xFF << TILEMAP_ASHIFT)
#define TILEMAP_COLOR(CR, CG, CB, CA) (((CR) << TILEMAP_RSHIFT) | \
                                       ((CG) << TILEMAP_GSHIFT) | \
                                       ((CB) << TILEMAP_BSHIFT) | \
                                       ((CA) << TILEMAP_ASHIFT))
#define TILEMAP_COLOR_B(VAL) ((VAL & TILEMAP_BMASK) >> TILEMAP_BSHIFT)
#define TILEMAP_COLOR_G(VAL) ((VAL & TILEMAP_GMASK) >> TILEMAP_GSHIFT)
#define TILEMAP_COLOR_R(VAL) ((VAL & TILEMAP_RMASK) >> TILEMAP_RSHIFT)
#define TILEMAP_COLOR_A(VAL) ((VAL & TILEMAP_AMASK) >> TILEMAP_ASHIFT)

typedef struct LayerList_t LayerList;
typedef void (*layerlist_log_cb_t)(void *priv, const char *fmt, ...);

int tilemap_tileset_from_bmp(LayerList *ll,
                             const char *filename,
                             unsigned int tw,
                             unsigned int th);
int tilemap_blank_tileset(LayerList *ll,
                          unsigned int w,
                          unsigned int h,
                          Uint32 color,
                          unsigned int tw,
                          unsigned int th);

LayerList *layerlist_new(SDL_Renderer *renderer,
                         Uint32 format,
                         layerlist_log_cb_t log_cb,
                         void *log_priv);
void layerlist_free(LayerList *ll);

int tilemap_add_tileset(LayerList *ll,
                        SDL_Surface *surface,
                        unsigned int tw,
                        unsigned int th);
int tilemap_free_tileset(LayerList *ll, unsigned int index);

int tilemap_add_tilemap(LayerList *ll,
                        unsigned int w,
                        unsigned int h);
int tilemap_free_tilemap(LayerList *ll, unsigned int index);
int tilemap_set_tilemap_tileset(LayerList *ll,
                                unsigned int index,
                                unsigned int tileset);
int tilemap_set_tilemap_map(LayerList *ll,
                            unsigned int index,
                            unsigned int x,
                            unsigned int y,
                            unsigned int pitch,
                            unsigned int w,
                            unsigned int h,
                            const unsigned int *value,
                            unsigned int size);
int tilemap_set_tilemap_attr_flags(LayerList *ll,
                              unsigned int index,
                              unsigned int x,
                              unsigned int y,
                              unsigned int pitch,
                              unsigned int w,
                              unsigned int h,
                              const unsigned int *value,
                              unsigned int size);
int tilemap_set_tilemap_attr_colormod(LayerList *ll,
                                      unsigned int index,
                                      unsigned int x,
                                      unsigned int y,
                                      unsigned int pitch,
                                      unsigned int w,
                                      unsigned int h,
                                      const Uint32 *value,
                                      unsigned int size);
int tilemap_update_tilemap(LayerList *ll,
                           unsigned int index,
                           unsigned int x,
                           unsigned int y,
                           unsigned int w,
                           unsigned int h);

int tilemap_add_layer(LayerList *ll,
                      unsigned int tilemap);
int tilemap_free_layer(LayerList *ll,
                       unsigned int index);
int tilemap_set_layer_pos(LayerList *ll,
                          unsigned int index,
                          int x,
                          int y);
int tilemap_set_layer_window(LayerList *ll,
                             unsigned int index,
                             unsigned int w,
                             unsigned int h);
int tilemap_set_layer_scroll_pos(LayerList *ll,
                                 unsigned int index,
                                 unsigned int scroll_x,
                                 unsigned int scroll_y);
int tilemap_set_layer_scale(LayerList *ll,
                            unsigned int index,
                            double scale_x,
                            double scale_y);
int tilemap_set_layer_rotation_center(LayerList *ll,
                                      unsigned int index,
                                      int x,
                                      int y);
int tilemap_set_layer_rotation(LayerList *ll,
                               unsigned int index,
                               double angle);
int tilemap_set_layer_colormod(LayerList *ll,
                               unsigned int index,
                               Uint32 colormod);
int tilemap_set_layer_blendmode(LayerList *ll,
                                unsigned int index,
                                int blendMode);
void tilemap_set_default_render_target(LayerList *ll, SDL_Texture *tex);
int tilemap_set_target_tileset(LayerList *ll, int tileset);
int tilemap_draw_layer(LayerList *ll, unsigned int index);

#endif
