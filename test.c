/*
 * Copyright 2020 paulguy <paulguy119@gmail.com>
 *
 * This file is part of crustygame.
 *
 * crustygame is free software: you can redistribute it and/or modify
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
 * along with crustygame.  If not, see <https://www.gnu.org/licenses/>.
 */

#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <limits.h>
#include <time.h>
#include <math.h>
#include <SDL.h>

#include "tilemap.h"
#include "synth.h"

#define ARRAY_COUNT(ARR) (sizeof(ARR) / sizeof((ARR[0])))
/* initial settings */
#define WINDOW_TITLE    "UnCrustyGame Test"
#define WINDOW_WIDTH    (640)
#define WINDOW_HEIGHT   (480)
#define CAT_RATE        (33)
#define CAT_VELOCITY    (7)
#define CAT_ANIM_DIV    (3)
#define BG_R (47)
#define BG_G (17)
#define BG_B (49)
#define SPRITE_SCALE (2.0)

#define TEST_SPRITESHEET   "cat.bmp"
#define TEST_SPRITE_WIDTH  (32)
#define TEST_SPRITE_HEIGHT (32)
const unsigned int TEST_SPRITESHEET_VALUES[] = {0, 1,
                                                2, 3};
#define TEST_RESTING_X (0)
#define TEST_RESTING_Y (0)
#define TEST_ANIM0_X   (0)
#define TEST_ANIM0_Y   (1)
#define TEST_ANIM1_X   (1)
#define TEST_ANIM1_Y   (1)

typedef enum {
    CAT_RESTING,
    CAT_ANIM0,
    CAT_ANIM1
} CatState;

int initialize_video(SDL_Window **win,
                     SDL_Renderer **renderer,
                     Uint32 *format) {
    int drivers;
    int nameddrv, bestdrv, softdrv, selectdrv;
    int selectfmt;
    Uint32 namedfmt, bestfmt, softfmt;
    int i, j;
    SDL_RendererInfo driver;

    /* SDL/Windows/Render initialization stuff */
    /* try to determine what driver to use based on available
     * features and prioritize an accelerated driver then fall back to
     * the software driver */
    drivers = SDL_GetNumRenderDrivers();
    fprintf(stderr, "Video Drivers: %d\n", drivers);

    nameddrv = -1;
    namedfmt = SDL_PIXELFORMAT_UNKNOWN;
    bestdrv = -1;
    bestfmt = SDL_PIXELFORMAT_UNKNOWN;
    softdrv = -1;
    softfmt = SDL_PIXELFORMAT_UNKNOWN;
    for(i = 0; i < drivers; i++) {
        if(SDL_GetRenderDriverInfo(i, &driver) < 0) {
            fprintf(stderr, "Couldn't get driver info for index %d.\n",
                    i);
            continue;
        }

        fprintf(stderr, "Driver %d: %s", i, driver.name);
        if((driver.flags & SDL_RENDERER_SOFTWARE) &&
           softdrv == -1) {
            for(j = 0; j < driver.num_texture_formats; j++) {
                if(SDL_BITSPERPIXEL(driver.texture_formats[j]) >= 24) {
                    softfmt = driver.texture_formats[j];
                    softdrv = i;
                    break;
                }
            }
        } else if((strcmp(driver.name, "direct3d11") == 0 ||
                  strncmp(driver.name, "opengles", 8) == 0 ||
                  strcmp(driver.name, "metal") == 0) &&
                  nameddrv == -1) {
            /* prefer direct3d 11 or opengles or metal for better blend mode support */
            for(j = 0; j < driver.num_texture_formats; j++) {
                if(SDL_BITSPERPIXEL(driver.texture_formats[j]) >= 24) {
                    namedfmt = driver.texture_formats[j];
                    nameddrv = i;
                    break;
                }
            }
        } else if((driver.flags & SDL_RENDERER_ACCELERATED) &&
                  (driver.flags & SDL_RENDERER_TARGETTEXTURE) &&
                  bestdrv == -1) {
            for(j = 0; j < driver.num_texture_formats; j++) {
                if(SDL_BITSPERPIXEL(driver.texture_formats[j]) >= 24) {
                    bestfmt = driver.texture_formats[j];
                    bestdrv = i;
                    break;
                }
            }
        }
        fprintf(stderr, "\n");
        fprintf(stderr, "Flags: (%08X) ", driver.flags);
        if(driver.flags & SDL_RENDERER_SOFTWARE)
            fprintf(stderr, "SOFTWARE ");
        if(driver.flags & SDL_RENDERER_ACCELERATED)
            fprintf(stderr, "ACCELERATED ");
        if(driver.flags & SDL_RENDERER_PRESENTVSYNC)
            fprintf(stderr, "PRESENTVSYNC ");
        if(driver.flags & SDL_RENDERER_TARGETTEXTURE)
            fprintf(stderr, "TARGETTEXTURE ");
        fprintf(stderr, "\n");
        fprintf(stderr, "Formats: ");
        for(j = 0; j < driver.num_texture_formats; j++) {
            fprintf(stderr, "(%08X) %s ",
                    driver.texture_formats[j],
                    SDL_GetPixelFormatName(driver.texture_formats[j]));
        }
        fprintf(stderr, "\n");
        fprintf(stderr, "Max Texture Size: %d x %d\n",
                driver.max_texture_width,
                driver.max_texture_height);
    }

    if(nameddrv != -1) {
        bestfmt = namedfmt;
        bestdrv = nameddrv;
    }

    /* create the window then try to create a renderer for it */
    *win = SDL_CreateWindow(WINDOW_TITLE,
                            SDL_WINDOWPOS_UNDEFINED,
                            SDL_WINDOWPOS_UNDEFINED,
                            WINDOW_WIDTH,
                            WINDOW_HEIGHT,
                            0);
    if(*win == NULL) {
        fprintf(stderr, "Failed to create SDL window.\n");
        goto error;
    }
 
    if(bestdrv < 0) {
        if(softdrv < 0) {
            fprintf(stderr, "No accelerated or software driver found? "
                            "Trying index 0...\n");
            if(SDL_GetRenderDriverInfo(0, &driver) < 0) {
                fprintf(stderr, "Couldn't get driver info for index "
                                "0.\n");
                goto error;
            }
            selectfmt = SDL_PIXELFORMAT_UNKNOWN;
            for(j = 0; j < driver.num_texture_formats; j++) {
                if(SDL_BITSPERPIXEL(driver.texture_formats[j]) >= 24) {
                    selectfmt = driver.texture_formats[j];
                    break;
                }
            }
            if(selectfmt == SDL_PIXELFORMAT_UNKNOWN) {
                fprintf(stderr, "Coulnd't find true color pixel "
                                "format.\n");
                goto error;
            }

            *format = selectfmt;
            selectdrv = 0;
        } else {
            fprintf(stderr, "No accelerated driver found, falling "
                            "back to software (%d).\n", softdrv);
            *format = softfmt;
            selectdrv = softdrv;
        }
    } else {
        fprintf(stderr, "Selecting driver %d.\n",
                        bestdrv);
        *format = bestfmt;
        selectdrv = bestdrv;
    }

    *renderer = SDL_CreateRenderer(*win, selectdrv, SDL_RENDERER_PRESENTVSYNC);
    if(*renderer == NULL) {
        fprintf(stderr, "Failed to create SDL renderer.\n");
        goto error;
    }

    return(0);

error:
    SDL_DestroyWindow(*win);

    return(-1);
}

int tileset_from_bmp(LayerList *ll,
                     const char *filename,
                     unsigned int tw,
                     unsigned int th) {
    SDL_Surface *surface;
    int tileset;

    surface = SDL_LoadBMP(filename);
    if(surface == NULL) {
        fprintf(stderr, "Failed to load %s.\n", filename);
        return(-1);
    }
    if(SDL_LockSurface(surface) < 0) {
        fprintf(stderr, "Failed to lock surface.\n");
        SDL_FreeSurface(surface);
        return(-1);
    }

    tileset = tilemap_add_tileset(ll,
                                  surface,
                                  tw, th);
    SDL_FreeSurface(surface);
    return(tileset);
}

/* i don't knwo what i'm doing */
double angle_from_xy(double x, double y) {
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
            return((M_PI * 2.0) - tan(x / y));
        } else {
            return((M_PI * 1.5) + tan(y / x));
        }
    } else if(x < 0.0 && y > 0.0) {
        x = -x;
        if(x < y) {
            return(tan(x / y));
        } else {
            return((M_PI * 0.5) - tan(y / x));
        }
    } else if(x > 0.0 && y < 0.0) {
        y = -y;
        if(x < y) {
            return(M_PI + tan(x / y));
        } else {
            return((M_PI * 1.5) - tan(y / x));
        }
    }

    x = -x;
    y = -y;
    if(x < y) {
        return(M_PI - tan(x / y));
    }
    return((M_PI * 0.5) + tan(y / x));
}

double radian_to_degree(double radian) {
    return(radian / (M_PI * 2) * 360.0);
}

void vprintf_cb(void *priv, const char *fmt, ...) {
    va_list ap;
    FILE *out = priv;

    va_start(ap, fmt);
    vfprintf(out, fmt, ap);
}

int audio_frame_cb(void *priv) {
    return(0);
}

int main(int argc, char **argv) {
    Uint32 format;
    SDL_Window *win;
    SDL_Renderer *renderer;
    SDL_Event lastEvent;
    LayerList *ll;
    Synth *s;
    int running;
    int mouseCaptured = 0;
    unsigned int mouseReleaseCombo = 0;
    int tileset;
    int tilemap;
    int catlayer;
    int mousex = (WINDOW_WIDTH - TEST_SPRITE_WIDTH) / 2;
    int mousey = (WINDOW_HEIGHT - TEST_SPRITE_HEIGHT) / 2;
    int catx = mousex;
    int caty = mousey;
    Uint32 nextMotion = SDL_GetTicks() + CAT_RATE;
    CatState catState = CAT_ANIM0;
    int animCounter = 0;

    if(SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO) < 0) {
        fprintf(stderr, "Failed to initialize SDL: %s\n",
                SDL_GetError());
        exit(EXIT_FAILURE);
    }

    if(initialize_video(&win,
                        &renderer,
                        &format) < 0) {
        fprintf(stderr, "Failed to initialize video.\n");
        goto error_sdl;
    }

    /* initialize the layerlist */
    ll = layerlist_new(renderer,
                       format,
                       vprintf_cb,
                       stderr);
    if(ll == NULL) {
        fprintf(stderr, "Failed to create layerlist.\n");
        goto error_video;
    }

    /* initialize the audio */
    s = synth_new(audio_frame_cb,
                  NULL,
                  vprintf_cb,
                  stderr);
    if(s == NULL) {
        fprintf(stderr, "Failed to create synth.\n");
        goto error_ll;
    }

    /* seed random */
    srand(time(NULL));

    /* init stuff */

    /* load the spritesheet */
    tileset = tileset_from_bmp(ll,
                               TEST_SPRITESHEET,
                               TEST_SPRITE_WIDTH,
                               TEST_SPRITE_HEIGHT);
    if(tileset < 0) {
        fprintf(stderr, "Failed to load spritesheet.\n");
        goto error_synth;
    }
    /* create a single tile map (sprite) */
    tilemap = tilemap_add_tilemap(ll, 2, 2);
    if(tilemap < 0) {
        fprintf(stderr, "Failed to make tilemap.\n");
        goto error_synth;
    }
    /* assign the spritesheet to the sprite */
    if(tilemap_set_tilemap_tileset(ll, tilemap, tileset) < 0) {
        fprintf(stderr, "Failed to apply tileset to tilemap.\n");
        goto error_synth;
    }
    /* set up its map for the first time (not likely necessary in this case
     * since it's probably already 0, but for demonstration purposes) */
    if(tilemap_set_tilemap_map(ll, tilemap, 
                               0, 0, /* start x and y for destination rectangle */
                               2, /* row width for source rectangle */
                               2, 2, /* size of rectangle */
                               TEST_SPRITESHEET_VALUES, /* the values of the
                                                           map rect */
                               ARRAY_COUNT(TEST_SPRITESHEET_VALUES)
                               /* number of values to expect */
                               ) < 0) {
        fprintf(stderr, "Failed to set tilemap map.\n");
        goto error_synth;
    }
    /* update/"render out" the tilemap for the first time */
    if(tilemap_update_tilemap(ll, tilemap,
                              0, 0, /* start rectangle to update */
                              2, 2) /* update rectangle size */ < 0) {
        fprintf(stderr, "Failed to update tilemap.\n");
        goto error_synth;
    }
    /* add the tilemap to a layer */
    catlayer = tilemap_add_layer(ll, tilemap);
    if(catlayer < 0) {
        fprintf(stderr, "Failed to create cat layer.\n");
        goto error_synth;
    }
    if(tilemap_set_layer_window(ll, catlayer,
                                TEST_SPRITE_WIDTH,
                                TEST_SPRITE_HEIGHT) < 0) {
        fprintf(stderr, "Failed to set layer window.\n");
        goto error_synth;
    }
    if(tilemap_set_layer_scroll_pos(ll, catlayer,
                                    TEST_ANIM0_X * TEST_SPRITE_WIDTH,
                                    TEST_ANIM0_Y * TEST_SPRITE_HEIGHT) < 0) {
        fprintf(stderr, "Failed to set layer scroll pos.\n");
        goto error_synth;
    }
    if(tilemap_set_layer_rotation_center(ll, catlayer,
                                         TEST_SPRITE_WIDTH / 2 * SPRITE_SCALE,
                                         TEST_SPRITE_HEIGHT / 2 * SPRITE_SCALE) < 0) {
        fprintf(stderr, "Failed to set layer rotation center.\n");
        goto error_synth;
    }
    tilemap_set_layer_scale(ll, catlayer, SPRITE_SCALE, SPRITE_SCALE);

    running = 1;
    while(running) {
        /* clear the display, otherwise it'll show flickery garbage */
        if(SDL_SetRenderDrawColor(renderer,
                                  BG_R, BG_G, BG_B,
                                  SDL_ALPHA_OPAQUE) < 0) {
            fprintf(stderr, "Failed to set render draw color.\n");
            goto error_synth;
        } 
        if(SDL_RenderClear(renderer) < 0) {
            fprintf(stderr, "Failed to clear screen.\n");
            goto error_synth;
        }

        /* needs to be transparent so tilemap updates work */
        if(SDL_SetRenderDrawColor(renderer,
                                  0, 0, 0,
                                  SDL_ALPHA_TRANSPARENT) < 0) {
            fprintf(stderr, "Failed to set render draw color.\n");
            goto error_synth;
        } 

        /* check running since an event may end execution early */
        while(running && SDL_PollEvent(&lastEvent)) {
            /* allow the user to press CTRL+F10 (like DOSBOX) to uncapture a
             * captured mouse, and also enforce disallowing recapture until
             * reallowed by pressing the same combo again. */
            if(lastEvent.type == SDL_KEYDOWN) {
                if(((SDL_KeyboardEvent *)&lastEvent)->keysym.sym ==
                   SDLK_LCTRL) {
                    mouseReleaseCombo |= 1;
                } else if(((SDL_KeyboardEvent *)&lastEvent)->keysym.sym ==
                   SDLK_F10) {
                    mouseReleaseCombo |= 2;
                }

                if(mouseReleaseCombo == 3) {
                    if(mouseCaptured < 0) {
                        mouseCaptured = 0;
                    } else {
                        if(SDL_SetRelativeMouseMode(0) < 0) {
                            fprintf(stderr, "Failed to clear relative mouse mode.\n");
                            return(-1);
                        }
                        mouseCaptured = -1;
                    }
                    mouseReleaseCombo = 0;
                }
            } else if(lastEvent.type == SDL_KEYUP) {
                if(((SDL_KeyboardEvent *)&lastEvent)->keysym.sym ==
                   SDLK_LCTRL) {
                    mouseReleaseCombo &= ~1;
                } else if(((SDL_KeyboardEvent *)&lastEvent)->keysym.sym ==
                   SDLK_F10) {
                    mouseReleaseCombo &= ~2;
                }
            }

            /* handle inputs */
            switch(lastEvent.type) {
                SDL_KeyboardEvent *key;
                SDL_MouseMotionEvent *motion;
                case SDL_QUIT:
                    running = 0;
                    continue;
                case SDL_KEYDOWN:
                    key = (SDL_KeyboardEvent *)&lastEvent;
                    /* suppress repeat events */
                    if(key->repeat) {
                        continue;
                    }
                    break;
                case SDL_KEYUP:
                    key = (SDL_KeyboardEvent *)&lastEvent;
                    if(key->repeat) {
                        continue;
                    }
                    break;
                case SDL_MOUSEMOTION:
                    motion = (SDL_MouseMotionEvent *)&lastEvent;
                    mousex = motion->x;
                    mousey = motion->y;
                    break;
                case SDL_MOUSEBUTTONDOWN:
                    if(catState == CAT_RESTING) {
                        catState = CAT_ANIM0;
                    } else {
                        catState = CAT_RESTING;
                        if(tilemap_set_layer_scroll_pos(ll, catlayer,
                                                        TEST_RESTING_X * TEST_SPRITE_WIDTH,
                                                        TEST_RESTING_Y * TEST_SPRITE_HEIGHT) < 0) {
                            fprintf(stderr, "Failed to set layer scroll pos.\n");
                            goto error_synth;
                        }
                    }
                    break;
                case SDL_MOUSEBUTTONUP:
                    break;
                default:
                    break;
            }
        }

        /* run the synth */
        if(synth_frame(s) < 0) {
            fprintf(stderr, "Audio failed.\n");
            goto error_synth;
        }

        /* frame stuff */
        Uint32 thisTick = SDL_GetTicks();
        if(thisTick >= nextMotion) {
            nextMotion += CAT_RATE;
            if(catState != CAT_RESTING) {
                int motionx = mousex - catx - (TEST_SPRITE_WIDTH / 2 * SPRITE_SCALE);
                int motiony = mousey - caty - (TEST_SPRITE_HEIGHT / 2 * SPRITE_SCALE);
                if(tilemap_set_layer_rotation(ll, catlayer,
                                              radian_to_degree(angle_from_xy(motionx, motiony))) < 0) {
                    fprintf(stderr, "Failed to set layer rotation.\n");
                    goto error_synth;
                }
                
                if(motionx < -CAT_VELOCITY) {
                    catx -= CAT_VELOCITY;
                } else if(motionx > CAT_VELOCITY) {
                    catx += CAT_VELOCITY;
                } else {
                    catx += motionx;
                }
                if(motiony < -CAT_VELOCITY) {
                    caty -= CAT_VELOCITY;
                } else if(motiony > CAT_VELOCITY) {
                    caty += CAT_VELOCITY;
                } else {
                    caty += motiony;
                }
                if(catState == CAT_ANIM0) {
                    animCounter++;
                    if(animCounter >= CAT_ANIM_DIV) {
                        catState = CAT_ANIM1;
                        animCounter = 0;
                        if(tilemap_set_layer_scroll_pos(ll, catlayer,
                                                        TEST_ANIM1_X * TEST_SPRITE_WIDTH,
                                                        TEST_ANIM1_Y * TEST_SPRITE_HEIGHT) < 0) {
                            fprintf(stderr, "Failed to set layer scroll pos.\n");
                            goto error_synth;
                        }
                    }
                } else {
                    animCounter++;
                    if(animCounter >= CAT_ANIM_DIV) {
                        catState = CAT_ANIM0;
                        animCounter = 0;
                        if(tilemap_set_layer_scroll_pos(ll, catlayer,
                                                        TEST_ANIM0_X * TEST_SPRITE_WIDTH,
                                                        TEST_ANIM0_Y * TEST_SPRITE_HEIGHT) < 0) {
                            fprintf(stderr, "Failed to set layer scroll pos.\n");
                            goto error_synth;
                        }
                    }
                }
            }
        }

        if(tilemap_set_layer_pos(ll, catlayer,
                                 catx, caty) < 0) {
            fprintf(stderr, "Failed to set cat position.\n");
            goto error_synth;
        }
        if(tilemap_draw_layer(ll, catlayer) < 0) {
            fprintf(stderr, "Failed to draw cat layer.\n");
            goto error_synth;
        }

        SDL_RenderPresent(renderer);
    }

    synth_free(s);
    layerlist_free(ll);

    SDL_DestroyWindow(win);
    SDL_Quit();

    exit(EXIT_SUCCESS);

error_synth:
    synth_free(s);
error_ll:
    layerlist_free(ll);
error_video:
    SDL_DestroyWindow(win);
error_sdl:
    SDL_Quit();
}
