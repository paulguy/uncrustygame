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

/* initial settings */
#define WINDOW_TITLE    "UnCrustyGame Test"
#define WINDOW_WIDTH    (1280)
#define WINDOW_HEIGHT   (720)
#define SPRITE_SCALE    (2.0)
#define BG_R (47)
#define BG_G (17)
#define BG_B (49)
#define CAT_FPS        (60)
#define CAT_RATE       (1000 / CAT_FPS)
#define CAT_VELOCITY   (5.0)
#define CAT_TURN_SPEED (M_PI * 2 / CAT_FPS)
#define CAT_ANIM_DIV   (6)
#define CAT_OFFSCREEN_DIST_FACTOR (0.1)
#define ZZZ_TRANSLUCENCY (128)
#define ZZZ_AMP          (10)
#define ZZZ_CYCLE_SPEED  (M_PI * 2 / CAT_FPS / 3)
#define ZZZ_COLOR_BIAS   (64)
/* from bottom-left */
#define ZZZ_POS_X        (0.75)
#define ZZZ_POS_Y        (0.75)

#define TEST_SPRITESHEET   "cat.bmp"
#define TEST_SPRITE_WIDTH  (32)
#define TEST_SPRITE_HEIGHT (32)
const unsigned int TEST_SPRITESHEET_VALUES[] = {0, 1,
                                                2, 3};
#define C_OPAQUE TILEMAP_COLOR(255, 255, 255, 255)
#define C_TRANSL TILEMAP_COLOR(255, 255, 255, ZZZ_TRANSLUCENCY)
const unsigned int TEST_SPRITESHEET_COLORMOD[] = {
    C_OPAQUE, C_TRANSL,
    C_OPAQUE, C_OPAQUE
};
#define TEST_RESTING_X (0)
#define TEST_RESTING_Y (0)
#define TEST_ZZZ_X     (1)
#define TEST_ZZZ_Y     (0)
#define TEST_ANIM0_X   (0)
#define TEST_ANIM0_Y   (1)
#define TEST_ANIM1_X   (1)
#define TEST_ANIM1_Y   (1)

#define ARRAY_COUNT(ARR) (sizeof(ARR) / sizeof((ARR[0])))
#define SCALE(VAL, SMIN, SMAX, DMIN, DMAX) \
    ((((VAL) - (SMIN)) / ((SMAX) - (SMIN)) * ((DMAX) - (DMIN))) + (DMIN))
#define SCALEINV(VAL, SMIN, SMAX, DMIN, DMAX) \
    ((DMAX) - (((VAL) - (SMIN)) / ((SMAX) - (SMIN)) * ((DMAX) - (DMIN))))

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
                            SDL_WINDOW_RESIZABLE);
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

double radian_to_degree(double radian) {
    return(radian / (M_PI * 2) * 360.0);
}

double velocity_from_xy(double x, double y) {
    return(sqrt(pow(x, 2) + pow(y, 2)));
}

/* still have no idea */
void xy_from_angle(double *x, double *y, double angle) {
    *x = -sin(angle);
    *y = cos(angle);
}

unsigned int color_from_angle(double angle, unsigned int bias) {
    const double COLORDIV = ((M_PI * 2.0) / 6.0);

    if(angle >= 0.0 && angle < COLORDIV) {
        return(TILEMAP_COLOR(255,
                             bias,
                             (unsigned int)SCALEINV(angle,
                                                    0.0, COLORDIV,
                                                    (double)bias, 255.0),
                             255));
    } else if(angle >= COLORDIV &&
       angle < COLORDIV * 2.0) {
        return(TILEMAP_COLOR(255,
                             (unsigned int)SCALE(angle,
                                                 COLORDIV, COLORDIV * 2.0,
                                                 (double)bias, 255.0),
                             bias,
                             255));
    } else if(angle >= COLORDIV * 2.0 &&
       angle < COLORDIV * 3.0) {
        return(TILEMAP_COLOR((unsigned int)SCALEINV(angle,
                                                    COLORDIV * 2.0, COLORDIV * 3.0,
                                                    (double)bias, 255.0),
                             255,
                             bias,
                             255));
    } else if(angle >= COLORDIV * 3.0 &&
       angle < COLORDIV * 4.0) {
        return(TILEMAP_COLOR(bias,
                             255,
                             (unsigned int)SCALE(angle,
                                                 COLORDIV * 3.0, COLORDIV * 4.0,
                                                 (double)bias, 255.0),
                             255));
    } else if(angle >= COLORDIV * 4.0 &&
       angle < COLORDIV * 5.0) {
        return(TILEMAP_COLOR(bias,
                             (unsigned int)SCALEINV(angle,
                                                    COLORDIV * 4.0, COLORDIV * 5.0,
                                                    (double)bias, 255.0),
                             255,
                             255));
    }
    return(TILEMAP_COLOR((unsigned int)SCALE(angle,
                                             COLORDIV * 5.0, COLORDIV * 6.0,
                                             (double)bias, 255.0),
                         bias,
                         255,
                         255));
}

double find_cat_velocity(double curdist, double angle, int catx, int caty, int winwidth, int winheight) {
    if(catx < 0) {
        if(caty < 0) {
            if(angle > M_PI * 1.5 && angle <= M_PI * 1.75) {
                double distance = sqrt(pow(-catx, 2) + pow(-caty, 2));
                return(SCALE(angle,
                             M_PI * 1.5, M_PI * 1.75,
                             0, distance * CAT_OFFSCREEN_DIST_FACTOR)
                       + CAT_VELOCITY);
            } else if(angle > M_PI * 1.75 && angle <= M_PI * 2.0) {
                double distance = sqrt(pow(-catx, 2) + pow(-caty, 2));
                return(SCALEINV(angle,
                                M_PI * 1.75, M_PI * 2.0,
                                0, distance * CAT_OFFSCREEN_DIST_FACTOR)
                       + CAT_VELOCITY);
            } else {
                return(CAT_VELOCITY);
            }
        } else if(caty > winheight) {
            if(angle > M_PI && angle <= M_PI * 1.25) {
                double distance = sqrt(pow(-catx, 2) + pow(caty - winheight, 2));
                return(SCALE(angle,
                             M_PI, M_PI * 1.25,
                             0, distance * CAT_OFFSCREEN_DIST_FACTOR)
                       + CAT_VELOCITY);
            } else if(angle > M_PI * 1.25 && angle <= M_PI * 1.5) {
                double distance = sqrt(pow(-catx, 2) + pow(caty - winheight, 2));
                return(SCALEINV(angle,
                                M_PI * 1.25, M_PI * 1.5,
                                0, distance * CAT_OFFSCREEN_DIST_FACTOR)
                       + CAT_VELOCITY);
            } else {
                return(CAT_VELOCITY);
            }
        } else {
            if(angle > M_PI && angle <= M_PI * 1.5) {
                return(SCALE(angle,
                             M_PI, M_PI * 1.5,
                             0, -catx * CAT_OFFSCREEN_DIST_FACTOR)
                       + CAT_VELOCITY);
            } else if(angle > M_PI * 1.5 && angle <= M_PI * 2.0) {
                return(SCALEINV(angle,
                                M_PI * 1.5, M_PI * 2.0,
                                0, -catx * CAT_OFFSCREEN_DIST_FACTOR)
                       + CAT_VELOCITY);
            } else {
                return(CAT_VELOCITY);
            }
        }
    } else if(catx > winwidth) { 
        if(caty < 0) {
            if(angle > 0 && angle <= M_PI * 0.25) {
                double distance = sqrt(pow(catx - winwidth, 2) + pow(-caty, 2));
                return(SCALE(angle,
                             0, M_PI * 0.25,
                             0, distance * CAT_OFFSCREEN_DIST_FACTOR)
                       + CAT_VELOCITY);
            } else if(angle > M_PI * 0.25 && angle <= M_PI * 0.5) {
                double distance = sqrt(pow(catx - winwidth, 2) + pow(-caty, 2));
                return(SCALEINV(angle,
                                M_PI * 0.25, M_PI * 0.5,
                                0, distance * CAT_OFFSCREEN_DIST_FACTOR)
                       + CAT_VELOCITY);
            } else {
                return(CAT_VELOCITY);
            }
        } else if(caty > winheight) {
            if(angle > M_PI * 0.5 && angle <= M_PI * 0.75) {
                double distance = sqrt(pow(catx - winwidth, 2) + pow(caty - winheight, 2));
                return(SCALE(angle,
                             M_PI * 0.5, M_PI * 0.75,
                             0, distance * CAT_OFFSCREEN_DIST_FACTOR)
                       + CAT_VELOCITY);
            } else if(angle > M_PI * 0.75 && angle <= M_PI) {
                double distance = sqrt(pow(catx - winwidth, 2) + pow(caty - winheight, 2));
                return(SCALEINV(angle,
                                M_PI * 0.75, M_PI,
                                0, distance * CAT_OFFSCREEN_DIST_FACTOR)
                       + CAT_VELOCITY);
            } else {
                return(CAT_VELOCITY);
            }
        } else {
            if(angle > 0 && angle <= M_PI * 0.5) {
                return(SCALE(angle,
                             0, M_PI * 0.5,
                             0, (catx - winwidth) * CAT_OFFSCREEN_DIST_FACTOR)
                       + CAT_VELOCITY);
            } else if(angle > M_PI * 0.5 && angle <= M_PI) {
                return(SCALEINV(angle,
                                M_PI * 0.5, M_PI,
                                0, (catx - winwidth) * CAT_OFFSCREEN_DIST_FACTOR)
                       + CAT_VELOCITY);
            } else {
                return(CAT_VELOCITY);
            }
        }
    } else if(caty < 0) {
        if(angle > 0 && angle <= M_PI * 0.5) {
            return(SCALEINV(angle,
                         0, M_PI * 0.5,
                         0, -caty * CAT_OFFSCREEN_DIST_FACTOR)
                   + CAT_VELOCITY);
        } else if(angle > M_PI * 1.5 && angle <= M_PI * 2.0) {
            return(SCALEINV(angle,
                            M_PI * 1.5, M_PI,
                            0, -caty * CAT_OFFSCREEN_DIST_FACTOR)
                   + CAT_VELOCITY);
        } else {
            return(CAT_VELOCITY);
        }
    } else if(caty > winheight) {
        if(angle > M_PI * 0.5 && angle <= M_PI) {
            return(SCALE(angle,
                         M_PI * 0.5, M_PI,
                         0, (caty - winheight) * CAT_OFFSCREEN_DIST_FACTOR)
                   + CAT_VELOCITY);
        } else if(angle > M_PI && angle <= M_PI * 1.5) {
            return(SCALEINV(angle,
                            M_PI, M_PI * 1.5,
                            0, (caty - winheight) * CAT_OFFSCREEN_DIST_FACTOR)
                   + CAT_VELOCITY);
        } else {
            return(CAT_VELOCITY);
        }
    } else if(curdist > CAT_VELOCITY) {
        return(CAT_VELOCITY);
    }
    return(curdist);
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
    double catx = mousex;
    double caty = mousey;
    Uint32 nextMotion = SDL_GetTicks() + CAT_RATE;
    CatState catState = CAT_ANIM0;
    int animCounter = 0;
    double catAngle = 0.0;
    int zzzlayer;
    double zzzcycle = 0.0;
    int fullscreen = 0;
    int winwidth = WINDOW_WIDTH;
    int winheight = WINDOW_HEIGHT;

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
    /* create the tilemap */
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
    /* apply color modifications, arguments are basically identical to setting
     * the tilemap map */
    if(tilemap_set_tilemap_attr_colormod(ll, tilemap,
                                         0, 0,
                                         2,
                                         2, 2,
                                         TEST_SPRITESHEET_COLORMOD,
                                         ARRAY_COUNT(TEST_SPRITESHEET_COLORMOD)
                                        ) < 0) {
        fprintf(stderr, "Failed to set tilemap colormod.\n");
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
    /* make the tilemap window the size of a single sprite */
    if(tilemap_set_layer_window(ll, catlayer,
                                TEST_SPRITE_WIDTH,
                                TEST_SPRITE_HEIGHT) < 0) {
        fprintf(stderr, "Failed to set layer window.\n");
        goto error_synth;
    }
    /* make the rotation center in the center of the sprite so it rotates
     * about where it aims for the cursor */
    if(tilemap_set_layer_rotation_center(ll, catlayer,
                                         TEST_SPRITE_WIDTH / 2 * SPRITE_SCALE,
                                         TEST_SPRITE_HEIGHT / 2 * SPRITE_SCALE) < 0) {
        fprintf(stderr, "Failed to set layer rotation center.\n");
        goto error_synth;
    }
    /* Makes the sprite more visible without me having to draw a larger sprite */
    if(tilemap_set_layer_scale(ll, catlayer, SPRITE_SCALE, SPRITE_SCALE) < 0) {
        fprintf(stderr, "Failed to set layer scale.\n");
        goto error_synth;
    }

    /* ##### MAIN LOOP ##### */
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
                SDL_MouseButtonEvent *click;
                SDL_WindowEvent *winEv;
                case SDL_QUIT:
                    running = 0;
                    continue;
                case SDL_KEYDOWN:
                    key = (SDL_KeyboardEvent *)&lastEvent;
                    /* suppress repeat events */
                    if(key->repeat) {
                        continue;
                    }

                    if(key->keysym.sym == SDLK_q) {
                        running = 0;
                    } else if(key->keysym.sym == SDLK_e) {
                        /* simulate an error, which will only only free the
                         * whole layerlist, testing possible memory leaks */ 
                        goto error_synth;
                    } else if(key->keysym.sym == SDLK_f) {
                        if(fullscreen) {
                            if(SDL_SetWindowFullscreen(win, 0) < 0) {
                                fprintf(stderr, "Failed to make window windowed.\n");
                            } else {
                                fullscreen = !fullscreen;
                            }
                        } else {
                            if(SDL_SetWindowFullscreen(win, SDL_WINDOW_FULLSCREEN_DESKTOP) < 0) {
                                fprintf(stderr, "Failed to make window full screen.\n");
                            } else {
                                fullscreen = !fullscreen;
                            }
                        }
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
                    click = (SDL_MouseButtonEvent *)&lastEvent;
                    if(click->button == 1) {
                        if(catState == CAT_RESTING) {
                            catState = CAT_ANIM0;
                            if(tilemap_free_layer(ll, zzzlayer) < 0) {
                                fprintf(stderr, "Failed to free ZZZ layer.\n");
                                goto error_synth;
                            }
                        } else {
                            catState = CAT_RESTING;
                            if(tilemap_set_layer_scroll_pos(ll, catlayer,
                                                            TEST_RESTING_X * TEST_SPRITE_WIDTH,
                                                            TEST_RESTING_Y * TEST_SPRITE_HEIGHT) < 0) {
                                fprintf(stderr, "Failed to set layer scroll pos.\n");
                                goto error_synth;
                            }

                            zzzlayer = tilemap_add_layer(ll, tilemap);
                            if(zzzlayer < 0) {
                                fprintf(stderr, "Failed to create ZZZ layer.\n");
                                goto error_synth;
                            }
                            if(tilemap_set_layer_window(ll, zzzlayer,
                                                        TEST_SPRITE_WIDTH,
                                                        TEST_SPRITE_HEIGHT) < 0) {
                                fprintf(stderr, "Failed to set layer window.\n");
                                goto error_synth;
                            }
                            if(tilemap_set_layer_scale(ll, zzzlayer,
                                                       SPRITE_SCALE,
                                                       SPRITE_SCALE) < 0) {
                                fprintf(stderr, "Failed to set layer scale.\n");
                                goto error_synth;
                            }
                            if(tilemap_set_layer_scroll_pos(ll, zzzlayer,
                                                            TEST_ZZZ_X * TEST_SPRITE_WIDTH,
                                                            TEST_ZZZ_Y * TEST_SPRITE_HEIGHT) < 0) {
                                fprintf(stderr, "Failed to set layer scroll pos.\n");
                                goto error_synth;
                            }
                        }
                    } else if(click->button == 3) {
                        catx = mousex;
                        caty = mousey;
                    }
                    break;
                case SDL_MOUSEBUTTONUP:
                    break;
                case SDL_WINDOWEVENT:
                    winEv = (SDL_WindowEvent *)&lastEvent;
                    if(winEv->event == SDL_WINDOWEVENT_SIZE_CHANGED) {
                        winwidth = winEv->data1;
                        winheight = winEv->data2;
                    }
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
                double motionx = mousex - catx - (TEST_SPRITE_WIDTH / 2 * SPRITE_SCALE);
                double motiony = mousey - caty - (TEST_SPRITE_HEIGHT / 2 * SPRITE_SCALE);
                double velocity = velocity_from_xy(motionx, motiony);
                if(velocity >= 1.0) {
                    double angle = angle_from_xy(motionx, motiony);
                    double angleDiff;
                    if(catAngle > M_PI && angle < catAngle - M_PI) {
                        angle += M_PI * 2;
                    } else if(catAngle < M_PI && angle > catAngle + M_PI) {
                        angle -= M_PI * 2;
                    }
                    angleDiff = catAngle - angle;
                    if(angleDiff > CAT_TURN_SPEED) {
                        angleDiff = CAT_TURN_SPEED;
                    } else if(angleDiff < -CAT_TURN_SPEED) {
                        angleDiff = -CAT_TURN_SPEED;
                    }
                    catAngle -= angleDiff;
                    if(catAngle < 0.0) {
                        catAngle += M_PI * 2;
                    } else if(catAngle >= M_PI * 2) {
                        catAngle -= M_PI * 2;
                    }
                    if(tilemap_set_layer_rotation(ll, catlayer,
                                                  radian_to_degree(catAngle)) < 0) {
                        fprintf(stderr, "Failed to set layer rotation.\n");
                        goto error_synth;
                    }
                    
                    velocity = find_cat_velocity(velocity, catAngle,
                                                 catx, caty,
                                                 winwidth, winheight);
                    xy_from_angle(&motionx, &motiony, catAngle);
                    catx += motionx * velocity;
                    caty += motiony * velocity;
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
            } else { /* CAT_RESTING */
                if(tilemap_set_layer_pos(ll, zzzlayer,
                                     catx + (TEST_SPRITE_WIDTH * SPRITE_SCALE * ZZZ_POS_X),
                                     caty - (TEST_SPRITE_HEIGHT * SPRITE_SCALE * ZZZ_POS_Y) + 
                                     (sin(zzzcycle) * ZZZ_AMP)) < 0) {
                    fprintf(stderr, "Failed to set ZZZ position.\n");
                    goto error_synth;
                }
                if(tilemap_set_layer_colormod(ll, zzzlayer,
                                              color_from_angle(zzzcycle,
                                                               ZZZ_COLOR_BIAS)) < 0) {
                    fprintf(stderr, "Failed to set ZZZ colormod.\n");
                    goto error_synth;
                }

                zzzcycle += ZZZ_CYCLE_SPEED;
                if(zzzcycle >= M_PI * 2) {
                    zzzcycle -= M_PI * 2;
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
        if(catState == CAT_RESTING) {
            if(tilemap_draw_layer(ll, zzzlayer) < 0) {
                fprintf(stderr, "Failed to draw ZZZ layer.\n");
                goto error_synth;
            }
        }

        SDL_RenderPresent(renderer);
    }

    synth_free(s);

    /* test cleanup functions */
    tilemap_free_layer(ll, catlayer);
    tilemap_free_tilemap(ll, tilemap);
    tilemap_free_tileset(ll, tileset);
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
