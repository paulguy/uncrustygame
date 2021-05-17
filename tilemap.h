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

/*
 * This is the tilemap library component of uncrustygame/libcrustygame.so, it is
 * the entire graphics system unique to uncrustygame, separated out and fixed up
 * from the previous crustygame project.  It's built upon the SDL_render API so
 * it's not quite the most efficient thing that could be used, I'm sure it could
 * be ported to using pure OpenGL or Vulkan or something but it's just a bit of
 * silly fun and not meant to be super practical or to really make very complex
 * graphics that would call for greater efficiency.  One can still interact with
 * things directly through the SDL_render API or OpenGL (or whatever API it ends
 * up being backed by I imagine..) as it's pretty non-intrusive and just holds
 * texture resources but doesn't otherwise interact with the underlying API in
 * any major way.
 *
 * The theory to how it is to be used is that one creates/loads in tilesets
 * from SDL_Surfaces (helpers are provided for creating blank tilesets if one
 * wants to create a new tileset from existing tilemaps/layers, as well as using
 * SDL's built in function for loading BMPs.).  The reason for this is it's a
 * slower process to update a texture pixel by pixel, so the idea would be that
 * you create fully prepared textures ahead of time as surfaces and pass them on
 * to the graphics API.
 *
 * Once there are tilesets, tilemaps can be created and have a tileset assigned
 * to them.  Tiles are laid out on a grid in the tilemap, optionally using
 * various attributes that allow to easily reuse tiles that just need to be
 * recolored or flipped or rotated in the cardinal directions.  Once all the
 * parameters are entered or any time they're changed, the tilemap needs to be
 * updated.  For the sake of preventing updating the entire tilemap especially
 * if it's a very large tilemap, a rectangular region can be selected to be
 * updated rather then the entire thing updated on every attribute or map
 * change.  Multiple tilemaps can be assigned to the same tileset.
 *
 * Tilemaps can't be displayed on their own though, they are just backed by a
 * texture, ultimately, in memory.  A layer needs to be created for the tilemap
 * as a view in to the tilemap to place on screen.  There are many parameters
 * which a layer can have which defines this view and how it's rendered to the
 * window or target tileset.
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
/*
 * Defined type of function for a logging callback for the layerlist context
 * which will accept whatever pointer to whatever you pass when initializing
 * the thing.  Otherwise, it's expected to take printf style format strings
 * so you'll probably want to use something like vsnprintf or something.
 *
 * priv     the void pointer you passed in on initialization
 * fmt      the format string
 * ...      the format string parameters
 */
typedef void (*layerlist_log_cb_t)(void *priv, const char *fmt, ...);

/*
 * Accept a path to a BMP file and use SDL_LoadBMP to load the BMP file which
 * at this time conveniently loads in the RGBA-format BMP files exported by the
 * GIMP, then returns a tileset.
 * See: tilemap_add_tileset
 *
 * ll       the LayerList context
 * filename the path to the BMP file
 * tw, th   dimensions of tiles
 * return   the tileset handle or -1 on failuer
 */
int tilemap_tileset_from_bmp(LayerList *ll,
                             const char *filename,
                             unsigned int tw,
                             unsigned int th);
/*
 * Create a new blank tileset filled with some color.
 * See: tilemap_add_tileset
 *
 * ll       the LayerList context
 * w, h     the entire tileset dimensions
 * color    the color the tileset will be initialized to, use something like
 *          SDL_MapRGBA or something
 * tw, th   dimensions of tiles
 * return   the tileset handle or -1 on failure
 */
int tilemap_blank_tileset(LayerList *ll,
                          unsigned int w,
                          unsigned int h,
                          Uint32 color,
                          unsigned int tw,
                          unsigned int th);

/*
 * Create a new LayerList context.
 *
 * renderer     the SDL_Renderer which the context is to use
 * format       a prefered format for the SDL_Renderer
 * log_cb       a callback you (the programmer using this library) provide to
 *              handle logging output from the library.
 * log_priv     handed off to log_cb as priv that can contain whatever you may
 *              find useful
 * return       the created LayerList or -1 on failure
 */
LayerList *layerlist_new(SDL_Renderer *renderer,
                         Uint32 format,
                         layerlist_log_cb_t log_cb,
                         void *log_priv);
/*
 * Free a layerlist and any associated memory/resources.  You shouldn't have to
 * free anything yourself on quit, and if you do it's a bug you should probably
 * report so it can be fixed.
 *
 * ll       the LayerList to free
 */
void layerlist_free(LayerList *ll);
/*
 * Get the renderer back from the LayerList, mostly a convenience function to
 * not have to hold on to it/pass it along to other functions that might make
 * direct SDL_render API calls.
 *
 * ll       the LayerList to get the SDL_Renderer from
 * return   the SDL_Renderer
 */
SDL_Renderer *layerlist_get_renderer(LayerList *ll);

/*
 * Add a tileset given an SDL_Surface.
 *
 * ll       the LayerList
 * surface  the SDL_Surface to transfer to the tileset.
 * tw, th   the tile dimensions
 * return   the tileset handle or -1 on failure
 */
int tilemap_add_tileset(LayerList *ll,
                        SDL_Surface *surface,
                        unsigned int tw,
                        unsigned int th);
/*
 * Free a tileset and any resources.
 * NOTE: there's a logarithmically growing array of structures which is grown
 *       as needed as tilesets are added, on free, any other memory or
 *       resources pointed to by the structure are freed but the structures
 *       themselves aren't freed, and on adding, they are linearly searched
 *       through to find the first free one.  This shouldn't be any concern but
 *       just for the sake of being up-front about things, I guess.
 *
 * ll       the LayerList
 * index    the tileset handle index
 * return   0 on success, -1 on failure
 */
int tilemap_free_tileset(LayerList *ll, unsigned int index);

/*
 * Add a tilemap.
 *
 * ll       the LayerList
 * w, h     the tilemap dimensions in tiles
 * return   the tilemap handle or -1 on failure
 */
int tilemap_add_tilemap(LayerList *ll,
                        unsigned int w,
                        unsigned int h);
/*
 * Free a tilemap and any resources.
 * See: tilemap_free_tileset NOTE
 *
 * ll       the LayerList
 * return   0 on success, -1 on failure
 */
int tilemap_free_tilemap(LayerList *ll, unsigned int index);
/*
 * Set a tileset which will be used for rendering out the tilemap.  This needs
 * to be done at least once before the tilemap can be updated.
 *
 * ll       the LayerList
 * index    the tilemap handle
 * tileset  the tileset handle to apply to the tilemap
 */
int tilemap_set_tilemap_tileset(LayerList *ll,
                                unsigned int index,
                                unsigned int tileset);
/*
 * Update a rectangle section of the tilemap.
 *
 * ll       the LayerList
 * index    the tilemap handle to update
 * x, y     the top-left corner of the rectangle to update
 * pitch    the width of the array of values to update with
 * w, h     the dimensions of the rectangle to update
 * value    the array containing the values to update with
 * size     the total size of the array, as a sanity check
 * return   0 on success, -1 on failure
 */
int tilemap_set_tilemap_map(LayerList *ll,
                            unsigned int index,
                            unsigned int x,
                            unsigned int y,
                            unsigned int pitch,
                            unsigned int w,
                            unsigned int h,
                            const unsigned int *value,
                            unsigned int size);
/*
 * Add/update attribute flags to a tilemap.  Non-squared tiles can only be
 * rotated 180 degrees.
 * See: TILEMAP_.FLIP_MASK, TILEMAP_ROTATE_.*
 * NOTE: For a slight optimization, a tilemap without an attribute map will
 *       never try to apply attributes which might make some difference to
 *       performance.
 *
 * ll       the LayerList
 * index    the tilemap to add or update attribute flags with
 * x, y     the top-left corner of the rectangle to update
 * pitch    the width of the array of values to update with
 * w, h     the dimensions of the rectangle to update
 * value    the array containing the values to update with
 * size     the total size of the array, as a sanity check
 * return   0 on success, -1 on failure
 */
int tilemap_set_tilemap_attr_flags(LayerList *ll,
                                   unsigned int index,
                                   unsigned int x,
                                   unsigned int y,
                                   unsigned int pitch,
                                   unsigned int w,
                                   unsigned int h,
                                   const unsigned int *value,
                                   unsigned int size);
/*
 * Add/update colormod values for a tilemap.  The way colormod works is, think
 * like the range of colors is scaled from 0.0 to 1.0 and multiplies by the
 * color value of the pixel, so for example if you have a pixel on the tilemap
 * which is RGB: 255, 255, 255 (full white), and the colormod for the tile which
 * the pixel is on is something like, 63, 127, 255, those values would be scaled
 * to roughly 0.25, 0.5 and 1.0, which will make the original pixel of
 * 255, 255, 255 take on close to those values.  This is scaled to the alpha of
 * the colormod value, where tha range of the alpha is scaled from 0.0 to 1.0.
 * See: tilemap_set_tilemap_attr_flags NOTE
 *
 * ll       the LayerList
 * index    the tilemap to add/update
 * x, y     the top-left corner of the rectangle to update
 * pitch    the width of the array of values to update with
 * w, h     the dimensions of the rectangle to update
 * value    the array containing the values to update with
 * size     the total size of the array, as a sanity check
 * return   0 on success, -1 on failure     
 */
int tilemap_set_tilemap_attr_colormod(LayerList *ll,
                                      unsigned int index,
                                      unsigned int x,
                                      unsigned int y,
                                      unsigned int pitch,
                                      unsigned int w,
                                      unsigned int h,
                                      const Uint32 *value,
                                      unsigned int size);
/*
 * Update a region of the tilemap.  This is necessary to perform on any update
 * to the tilemap or pointed-to tileset, otherwise it won't appear any
 * different, or may just error.
 * 
 * ll       the LayerList
 * index    the tilemap to update
 * x, y     the top-left corner of the rectangle to update, in tiles
 * w, h     the dimensions of the rectangle to update, in tiles
 * return   0 on success, -1 on failure
 */
int tilemap_update_tilemap(LayerList *ll,
                           unsigned int index,
                           unsigned int x,
                           unsigned int y,
                           unsigned int w,
                           unsigned int h);

/*
 * Add a layer.
 *
 * ll       the LayerList
 * tilemap  the tilemap which the layer will display.
 * return   the layer handle or -1 on failure
 */
int tilemap_add_layer(LayerList *ll,
                      unsigned int tilemap);
/*
 * Free a layer.
 * See: tilemap_free_tileset NOTE
 *
 * ll       the LayerList
 * index    the layer to free
 * return   0 on success, -1 on failure
 */
int tilemap_free_layer(LayerList *ll,
                       unsigned int index);
/*
 * Set the on-screen position to draw the layer to.
 *
 * ll       the LayerList
 * index    the layer to update
 * x, y     the position the layer is to be drawn to
 * return   0 on success, -1 on failure
 */
int tilemap_set_layer_pos(LayerList *ll,
                          unsigned int index,
                          int x,
                          int y);
/*
 * Set the window size of the view in to the tilemap to show.
 *
 * ll       the LayerList
 * index    the layer to update
 * w, h     the size of the window
 * return   0 on success, -1 on failure
 */
int tilemap_set_layer_window(LayerList *ll,
                             unsigned int index,
                             unsigned int w,
                             unsigned int h);
/*
 * Set the scroll position (top-left corner) of the tilemap to show.
 *
 * ll                   the LayerList
 * index                the layer to update
 * scroll_x, scroll_y   the corner of the tilemap to show
 * return               0 on success, -1 on failure
 */
int tilemap_set_layer_scroll_pos(LayerList *ll,
                                 unsigned int index,
                                 unsigned int scroll_x,
                                 unsigned int scroll_y);
/*
 * Set the scale of the layer.
 * NOTE: The dimensions of the layer will be the layer's window size multiplied
 *       by this scale factor when drawn to the screen.
 *
 * ll               the LayerList
 * index            the layer to update
 * scale_x, scale_y the scales of each dimension
 * return           0 on success, -1 on failure
 */
int tilemap_set_layer_scale(LayerList *ll,
                            unsigned int index,
                            double scale_x,
                            double scale_y);
/*
 * Set the point around which the layer is rotated.
 *
 * ll       the LayerList
 * index    the layer to update
 * x, y     the center of rotation relative to the top-left corner
 * return   0 on success, -1 on failure
 */
int tilemap_set_layer_rotation_center(LayerList *ll,
                                      unsigned int index,
                                      int x,
                                      int y);
/*
 * Set the rotation of the layer, in degrees.
 *
 * ll       the LayerList
 * index    the layer to update
 * angle    the angle in degrees it should be rotated
 * return   0 on success, -1 on failure
 */
int tilemap_set_layer_rotation(LayerList *ll,
                               unsigned int index,
                               double angle);
/*
 * Set the layer's colormod.
 * See: tilemap_set_tilemap_attr_colormod
 *
 * ll       the LayerList
 * index    the layer to update
 * colormod the color modulation value
 * return   0 on success, -1 on failure
 */
int tilemap_set_layer_colormod(LayerList *ll,
                               unsigned int index,
                               Uint32 colormod);
/*
 * Set the layer blendmode.
 *
 * BLEND: add -alpha of the underlying color with +alpha of the layer color
 * ADD: add +alpha of the layer color to the underlying color
 * MOD: See: tilemap_set_tilemap_attr_colormod
 * MUL: I'm just really not sure, I would guess the same as ADD and SUB but the
 *      value is multiplied?
 * SUB: subtract +alpha of the layer color from the underlying color
 *
 * ll           the LayerList
 * index        the layer to update
 * blendMode    See: TILEMAP_BLENDMODE_.*
 * return       0 on success, -1 on failure
 */
int tilemap_set_layer_blendmode(LayerList *ll,
                                unsigned int index,
                                int blendMode);
/*
 * Set the default texture to render to.  Isn't applied immediately, though.
 * See: tilemap_set_target_tileset
 *
 * ll       the LayerList
 * tex      the SDL_Texture to render to or NULL for the screen
 */
void tilemap_set_default_render_target(LayerList *ll, SDL_Texture *tex);
/*
 * Set the tileset to render to or the default render target if less than 0.
 *
 * ll       the LayerList
 * tileset  the tileset which should be rendered to.  Important to kniow is that
 *          any tilemaps which refer to this tileset need to be updated before
 *          changes are applied.
 * return   0 on success, -1 on failure
 */
int tilemap_set_target_tileset(LayerList *ll, int tileset);
/*
 * Finally, draw a layer to the screen or render target.
 *
 * ll       the LayerList
 * index    the layer index
 * return   0 on success, -1 on failure
 */
int tilemap_draw_layer(LayerList *ll, unsigned int index);

#endif
