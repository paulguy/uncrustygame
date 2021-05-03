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

#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <math.h>
#include <stdarg.h>
#include <string.h>
#include <limits.h>
#include <SDL.h>

#include "tilemap.h"
#include "synth.h"

/* initial settings */
#define MAX_PROCESS_TIME (200)
#define WINDOW_TITLE    "UnCrustyGame Test"
#define WINDOW_WIDTH    (1024)
#define WINDOW_HEIGHT   (768)
#define DEFAULT_RATE    (48000)
#define SPRITE_SCALE    (2.0)
#define MAX_ACTIVE_PLAYERS (32)
#define BG_R (47)
#define BG_G (17)
#define BG_B (49)
#define ACTOR_FPS      (60)
#define ACTOR_RATE     (1000 / ACTOR_FPS)
#define CAT_VELOCITY   (5.0)
#define CAT_TURN_SPEED (M_PI * 2.0 / ACTOR_FPS)
#define CAT_ANIM_DIV   (6)
#define CAT_OFFSCREEN_DIST_FACTOR (0.1)
#define CAT_IDLE_MEOW    (2000) /* milliseconds */
#define CAT_PAN_FACTOR   (0.75)
#define ZZZ_TRANSLUCENCY (128)
#define ZZZ_AMP          (6)
#define ZZZ_CYCLE_SPEED  (M_PI * 2.0 / ACTOR_FPS / 3.0)
#define ZZZ_COLOR_BIAS   (64)
/* from bottom-left */
#define ZZZ_POS_X        (0.75)
#define ZZZ_POS_Y        (-0.5)
#define HUD_SHADOW_TRANSLUCENCY (192)

#define MAX_ENEMIES      (256)
#define MIN_SPAWNER_TIME (500)
#define MAX_SPAWNER_TIME (2000)
#define ANT_SPAWN_MIN    (20)
#define ANT_SPAWN_MAX    (100)
#define ANT_SPAWN_TIME_MIN (10)
#define ANT_SPAWN_TIME_MAX (30)
#define ANT_VELOCITY     (1.0)
#define ANT_TURN_SPEED   (M_PI * 2.0 / ACTOR_FPS * 2.0)
#define ANT_VALUE        (10)
#define ANT_EAT_TIME     (100)
#define SPIDER_SPAWN_MIN (10)
#define SPIDER_SPAWN_MAX (50)
#define SPIDER_SPAWN_TIME_MIN (20)
#define SPIDER_SPAWN_TIME_MAX (50)
#define SPIDER_VELOCITY  (2.0)
#define SPIDER_TURN_SPEED (M_PI * 2.0 / ACTOR_FPS * 1.8)
#define SPIDER_VALUE     (50)
#define SPIDER_EAT_TIME  (500)
#define MOUSE_SPAWN_MIN  (2)
#define MOUSE_SPAWN_MAX  (10)
#define MOUSE_SPAWN_TIME_MIN (100)
#define MOUSE_SPAWN_TIME_MAX (500)
#define MOUSE_VELOCITY   (4.0)
#define MOUSE_TURN_SPEED (M_PI * 2.0 / ACTOR_FPS * 1.3)
#define MOUSE_VALUE      (200)
#define MOUSE_EAT_TIME   (1000)

#define TEST_SPRITESHEET   "cat.bmp"
#define TEST_SPRITE_WIDTH  (32)
#define TEST_SPRITE_HEIGHT (32)
const unsigned int TEST_SPRITESHEET_VALUES[] = {0, 1,
                                                2, 3,
                                                4, 5,
                                                6, 7,
                                                8, 9,
                                                10, 11,
                                                12, 13,
                                                12, 12};
#define C_OPAQUE TILEMAP_COLOR(255, 255, 255, 255)
#define C_TRANSL TILEMAP_COLOR(255, 255, 255, ZZZ_TRANSLUCENCY)
#define C_MOUSEBLOOD TILEMAP_COLOR(145, 0, 0, 255)
#define C_ANTBLOOD TILEMAP_COLOR(37, 70, 0, 255)
#define C_SPIDERBLOOD TILEMAP_COLOR(0, 34, 72, 255)
#define C_HUD_SHADOW TILEMAP_COLOR(255, 255, 255, HUD_SHADOW_TRANSLUCENCY)
const unsigned int TEST_SPRITESHEET_COLORMOD[] = {
    C_OPAQUE, C_TRANSL,
    C_OPAQUE, C_OPAQUE,
    C_OPAQUE, C_OPAQUE,
    C_OPAQUE, C_OPAQUE,
    C_OPAQUE, C_OPAQUE,
    C_OPAQUE, C_OPAQUE,
    C_ANTBLOOD, C_OPAQUE,
    C_SPIDERBLOOD, C_MOUSEBLOOD
};
#define TEST_RESTING (0)
#define TEST_ZZZ     (1)
#define TEST_ANIM0   (2)
#define TEST_ANIM1   (3)
#define TEST_MOUSE0  (4)
#define TEST_MOUSE1  (5)
#define TEST_SPIDER0 (6)
#define TEST_SPIDER1 (7)
#define TEST_ANT0    (8)
#define TEST_ANT1    (9)
#define TEST_BIGHOLE (10)
#define TEST_SMHOLE  (11)
#define TEST_ANT_GORE   (12)
#define TEST_BONES   (13)
#define TEST_SPIDER_GORE   (14)
#define TEST_MOUSE_GORE   (15)

#define CAT_DISTANCE     (TEST_SPRITE_HEIGHT * SPRITE_SCALE / 2)

#define FONT_WIDTH  (8)
#define FONT_HEIGHT (8)
#define HUD_SCALE   (2)
#define HUD_WIDTH   (WINDOW_WIDTH / (FONT_WIDTH * HUD_SCALE))
#define HUD_HEIGHT  (WINDOW_HEIGHT / (FONT_HEIGHT * HUD_SCALE))

#define ARRAY_COUNT(ARR) (sizeof(ARR) / sizeof((ARR[0])))
#define SCALE(VAL, SMIN, SMAX, DMIN, DMAX) \
    ((((VAL) - (SMIN)) / ((SMAX) - (SMIN)) * ((DMAX) - (DMIN))) + (DMIN))
#define SCALEINV(VAL, SMIN, SMAX, DMIN, DMAX) \
    ((DMAX) - (((VAL) - (SMIN)) / ((SMAX) - (SMIN)) * ((DMAX) - (DMIN))))
#define RANDRANGE(MIN, MAX) ((rand() % (MAX - MIN)) + MIN)
#define CENTER(OUTERW, INNERW) (((OUTERW) - (INNERW)) / 2)

#define CATPAN(XPOS) ((float)((XPOS) - (WINDOW_WIDTH / 2.0)) / \
                      ((float)WINDOW_WIDTH / 2.0) * CAT_PAN_FACTOR)

typedef struct GameMode_s {
    int (*input)(void *priv, SDL_Event *event);
    struct GameMode_s* (*control)(void *priv);
    int (*draw)(void *priv);
    void *priv;
} GameMode;

typedef enum {
    CAT_RESTING,
    CAT_ANIM0,
    CAT_ANIM1
} CatState;

typedef struct {
    int player;
    float volume;
    float panning;
    int token;
} ActivePlayer;

typedef struct {
    Synth *s;
    int fragments;
    ActivePlayer player[MAX_ACTIVE_PLAYERS];
    int mixBuffer;
    int leftBuffer;
    int rightBuffer;
    int mixPlayer;
} AudioState;

typedef struct {
    int sprite;
    unsigned int anim;
    unsigned int animCounter;
    CatState state;
    float x, y;
    float angle;
    float maxSpeed;
    float maxAngle;
    int value;
    unsigned int eatTime;
    int deadSprite;
} Enemy;

typedef enum {
    SPAWN_NONE,
    SPAWN_ANTS,
    SPAWN_SPIDERS,
    SPAWN_MICE
} SpawnerType;

typedef struct {
    /* game modes */
    GameMode title;
    GameMode game;
    GameMode *nextMode;

    /* resources */
    SDL_Renderer *renderer;
    LayerList *ll;
    AudioState *as;
    int tilemap;
    int catlayer;
    int zzzlayer;
    SDL_Texture *goreTex;
    int goreSprite;
    int hudTilemap;
    int hud;
    int titleLayer;

    /* system state */
    int mousex, mousey;

    /* game state */
    CatState catState;
    int catAnim;
    float catAngle;
    int catIdleTime;
    float catx, caty;
    int eating;
    int score;
    int animCounter;
    float zzzcycle;
    SpawnerType spawner;
    int spawnerSprite;
    int spawnerTimer;
    unsigned int spawnerx;
    unsigned int spawnery;
    unsigned int spawnerCount;
    Enemy enemy[MAX_ENEMIES];

    /* player sound resources and state */
    int meow1, meow2, cat_activation, purr, meat, meat2;
    int catSound;
} GameState;

const char TEXT_SCORE[] = "Score: ";
#define TEXT_SCORE_X (0)
#define TEXT_SCORE_Y (0)

const char TEXT_START[] = "Press [ENTER] to start";
#define TEXT_START_X CENTER(HUD_WIDTH, sizeof(TEXT_START) - 1)
#define TEXT_START_Y (HUD_HEIGHT - 4)

void vprintf_cb(void *priv, const char *fmt, ...) {
    va_list ap;
    FILE *out = priv;

    va_start(ap, fmt);
    vfprintf(out, fmt, ap);
}

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
            for(j = 0; (unsigned int)j < driver.num_texture_formats; j++) {
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
            for(j = 0; (unsigned int)j < driver.num_texture_formats; j++) {
                if(SDL_BITSPERPIXEL(driver.texture_formats[j]) >= 24) {
                    namedfmt = driver.texture_formats[j];
                    nameddrv = i;
                    break;
                }
            }
        } else if((driver.flags & SDL_RENDERER_ACCELERATED) &&
                  (driver.flags & SDL_RENDERER_TARGETTEXTURE) &&
                  bestdrv == -1) {
            for(j = 0; (unsigned int)j < driver.num_texture_formats; j++) {
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
        for(j = 0; (unsigned int)j < driver.num_texture_formats; j++) {
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
            for(j = 0; (unsigned int)j < driver.num_texture_formats; j++) {
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

    /* might make some different?  dunno */
    setenv("SDL_HINT_RENDER_BATCHING", "1", 0);

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

void ascii_to_int(unsigned int *dst,
                  const char *src,
                  unsigned int len) {
    unsigned int i;

    for(i = 0; i < len; i++) {
        dst[i] = (unsigned int)(src[i]);
    }
}

int print_to_tilemap(LayerList *ll,
                     unsigned int tilemap,
                     unsigned int x,
                     unsigned int y,
                     unsigned int w,
                     const char *text) {
    unsigned int textLen = strlen(text);
    unsigned int h = textLen / w;
    if(textLen % w > 0) {
        h++;
    }
    unsigned int textTilemap[w * h];
    /* convert the char array to a tilemap */
    ascii_to_int(textTilemap,
                 text,
                 textLen);
    /* clear the rest, if there was a remainder */
    memset(&(textTilemap[textLen]),
           0,
           ((w * h) - textLen) * sizeof(unsigned int));
    /* apply it */
    if(tilemap_set_tilemap_map(ll, tilemap,
                               x, y,
                               w,
                               w, h,
                               textTilemap, w * h) < 0) {
        fprintf(stderr, "Failed to print to tilemap.\n");
        return(-1);
    }

    return(0);
}

int print_to_hud(GameState *gs,
                 const char *text,
                 unsigned int x,
                 unsigned int y) {
    int len = strlen(text);

    if(print_to_tilemap(gs->ll, gs->hudTilemap,
                        x, y,
                        len, text) < 0) {
        fprintf(stderr, "failed to print hud text.\n");
        return(-1);
    }
    if(tilemap_update_tilemap(gs->ll, gs->hudTilemap,
                              x, y,
                              len, 1) < 0) {
        fprintf(stderr, "Failed to update hud tilemap.\n");
        return(-1);
    }

    return(0);
}

int printf_to_tilemap(LayerList *ll,
                      unsigned int tilemap,
                      unsigned int x,
                      unsigned int y,
                      unsigned int w,
                      const char *fmt,
                      ...) {
    va_list ap;

    va_start(ap, fmt);
    unsigned int textLen = vsnprintf(NULL, 0, fmt, ap);
    va_end(ap);
    unsigned int h = textLen / w;
    if(textLen % w > 0) {
        h++;
    }
    /* just use the stack for simplicity */
    char text[textLen + 1];
    unsigned int textTilemap[w * h];

    va_start(ap, fmt);
    if(vsnprintf(text, textLen + 1, fmt, ap) < (int)textLen) {
        fprintf(stderr, "Failed to printf to text buf.\n");
        return(-1);
    }
    va_end(ap);

    /* convert the char array to a tilemap */
    ascii_to_int(textTilemap,
                 text,
                 textLen);
    /* clear the rest, if there was a remainder */
    memset(&(textTilemap[textLen]),
           0,
           ((w * h) - textLen) * sizeof(unsigned int));
    /* apply it */
    if(tilemap_set_tilemap_map(ll, tilemap,
                               x, y,
                               w,
                               w, h,
                               textTilemap, w * h) < 0) {
        fprintf(stderr, "Failed to printf to tilemap.\n");
        return(-1);
    }

    return(textLen);
}

int ascii_wrap_to_int(unsigned int *dst,
                      const char *src,
                      unsigned int srclen,
                      unsigned int dstwidth,
                      unsigned int *dstheight) {
    unsigned int temp;
    unsigned int i, x, y;
    unsigned int wordstart;
    unsigned int wordend;
    unsigned int wordlen;
    int stopCopying;

    if(dstheight == NULL) {
        temp = UINT_MAX;
        dstheight = &temp;
    }

    x = 0; y = 0;
    for(i = 0; i < srclen; i++) {
        /* find start of a word */
        stopCopying = 0;
        for(wordstart = i; wordstart < srclen; wordstart++) {
            if(stopCopying == 0 && src[wordstart] == ' ') {
                if(dst != NULL) {
                    dst[(y * dstwidth) + x] = ' ';
                }
                x++;
                /* at the end of a line, go to the next, but stop copying
                 * spaces */
                if(x == dstwidth) {
                    x = 0;
                    y++;
                    if(y == *dstheight) {
                        return(wordstart);
                    }
                    stopCopying = 1;
                }
            } else if(src[wordstart] == '\n') {
                x = 0;
                y++;
                if(y == *dstheight) {
                    return(wordstart);
                }
                stopCopying = 0;
            } else {
                break;
            }
        }

        if(wordstart == srclen) {
            break;
        }

        /* find end of word */
        for(wordend = wordstart; wordend < srclen; wordend++) {
            if(src[wordend] == ' ' || src[wordend] == '\n') {
                break;
            }
        }

        wordlen = wordend - wordstart;
        /* if the word wouldn't fit, start a new line */
        if(wordlen > dstwidth - x) {
            x = 0;
            y++;
            if(y == *dstheight) {
                return(wordstart);
            }
        }
        for(i = wordstart; i < wordend; i++) {
            if(x == dstwidth) {
                x = 0;
                y++;
                if(y == *dstheight) {
                    return(i);
                }
            }
            if(dst != NULL) {
                dst[(dstwidth * y) + x] = (unsigned int)(src[i]);
            }
            x++;
        }
    }

    *dstheight = y;
    return(srclen);
}


/* i don't knwo what i'm doing */
float angle_from_xy(float x, float y) {
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
            return((M_PI * 2.0) - atanf(x / y));
        } else {
            return((M_PI * 1.5) + atanf(y / x));
        }
    } else if(x < 0.0 && y > 0.0) {
        x = -x;
        if(x < y) {
            return(atanf(x / y));
        } else {
            return((M_PI * 0.5) - atanf(y / x));
        }
    } else if(x > 0.0 && y < 0.0) {
        y = -y;
        if(x < y) {
            return(M_PI + atanf(x / y));
        } else {
            return((M_PI * 1.5) - atanf(y / x));
        }
    }

    x = -x;
    y = -y;
    if(x < y) {
        return(M_PI - atanf(x / y));
    }
    return((M_PI * 0.5) + atanf(y / x));
}

float radian_to_degree(float radian) {
    return(radian / (M_PI * 2) * 360.0);
}

float velocity_from_xy(float x, float y) {
    return(sqrtf(powf(x, 2) + powf(y, 2)));
}

float distance(float x1, float y1, float x2, float y2) {
    if(x1 > x2) {
        if(y1 > y2) {
            return(velocity_from_xy(x1 - x2, y1 - y2));
        } else {
            return(velocity_from_xy(x1 - x2, y2 - y1));
        }
    }
    if(y1 > y2) {
        return(velocity_from_xy(x2 - x1, y1 - y2));
    }
    return(velocity_from_xy(x2 - x1, y2 - y1));
}

/* still have no idea */
void xy_from_angle(float *x, float *y, float angle) {
    *x = -sin(angle);
    *y = cos(angle);
}

unsigned int color_from_angle(float angle, unsigned int bias) {
    const float COLORDIV = ((M_PI * 2.0) / 6.0);

    if(angle >= 0.0 && angle < COLORDIV) {
        return(TILEMAP_COLOR(255,
                             bias,
                             (unsigned int)SCALEINV(angle,
                                                    0.0, COLORDIV,
                                                    (float)bias, 255.0),
                             255));
    } else if(angle >= COLORDIV &&
       angle < COLORDIV * 2.0) {
        return(TILEMAP_COLOR(255,
                             (unsigned int)SCALE(angle,
                                                 COLORDIV, COLORDIV * 2.0,
                                                 (float)bias, 255.0),
                             bias,
                             255));
    } else if(angle >= COLORDIV * 2.0 &&
       angle < COLORDIV * 3.0) {
        return(TILEMAP_COLOR((unsigned int)SCALEINV(angle,
                                                    COLORDIV * 2.0, COLORDIV * 3.0,
                                                    (float)bias, 255.0),
                             255,
                             bias,
                             255));
    } else if(angle >= COLORDIV * 3.0 &&
       angle < COLORDIV * 4.0) {
        return(TILEMAP_COLOR(bias,
                             255,
                             (unsigned int)SCALE(angle,
                                                 COLORDIV * 3.0, COLORDIV * 4.0,
                                                 (float)bias, 255.0),
                             255));
    } else if(angle >= COLORDIV * 4.0 &&
       angle < COLORDIV * 5.0) {
        return(TILEMAP_COLOR(bias,
                             (unsigned int)SCALEINV(angle,
                                                    COLORDIV * 4.0, COLORDIV * 5.0,
                                                    (float)bias, 255.0),
                             255,
                             255));
    }
    return(TILEMAP_COLOR((unsigned int)SCALE(angle,
                                             COLORDIV * 5.0, COLORDIV * 6.0,
                                             (float)bias, 255.0),
                         bias,
                         255,
                         255));
}

float volume_from_db(float db) {
    if(db < 0.0) {
        return(powf(10.0, db / 10.0));
    }
    return(1.0 / powf(10.0, -db / 10.0));
}

int create_mix_buffers(AudioState *as) {
    /* the import type is ignored when creating empty buffers. */
    as->mixBuffer = synth_add_buffer(as->s, SYNTH_TYPE_F32, NULL, synth_get_fragment_size(as->s) * as->fragments);
    if(as->mixBuffer < 0) {
        fprintf(stderr, "Failed to create mix buffer.\n");
        return(-1);
    }
    as->leftBuffer = synth_add_buffer(as->s, SYNTH_TYPE_F32, NULL, synth_get_fragment_size(as->s) * as->fragments);
    if(as->mixBuffer < 0) {
        fprintf(stderr, "Failed to create left buffer.\n");
        return(-1);
    }
    as->rightBuffer = synth_add_buffer(as->s, SYNTH_TYPE_F32, NULL, synth_get_fragment_size(as->s) * as->fragments);
    if(as->mixBuffer < 0) {
        fprintf(stderr, "Failed to create right buffer.\n");
        return(-1);
    }
    as->mixPlayer = synth_add_player(as->s, as->mixBuffer);
    if(as->mixPlayer < 0) {
        fprintf(stderr, "Failed to create mix player.\n");
        return(-1);
    }

    return(0);
}

int audio_frame_cb(void *priv) {
    AudioState *as = (AudioState *)priv;
    unsigned int i;
    int playerRet;
    float volume;
    unsigned int needed = synth_get_samples_needed(as->s);

    /* check for underrun and enlarge the fragment size in the hopes of
     * settling on the minimum necessary number of fragments and avoid crackles
     */
    if(synth_has_underrun(as->s)) {
        /* disable the synth before doing fragment operations */
        if(synth_set_enabled(as->s, 0) < 0) {
            fprintf(stderr, "Failed to stop synth.\n");
            return(-1);
        }
        /* try to increase the fragments count by 1 */
        if(synth_set_fragments(as->s, as->fragments + 1) < 0) {
            fprintf(stderr, "Failed to set fragments, disabling.\n");
            return(-1);
        }
        as->fragments++;
        /* free the reference from the mix buffer */
        if(synth_free_player(as->s, as->mixPlayer) < 0) {
            fprintf(stderr, "Failed to free mix player.\n");
            return(-1);
        }
        /* free the buffers */
        if(synth_free_buffer(as->s, as->mixBuffer) < 0) {
            fprintf(stderr, "Failed to mix buffer.\n");
            return(-1);
        }
        if(synth_free_buffer(as->s, as->leftBuffer) < 0) {
            fprintf(stderr, "Failed to left channel buffer.\n");
            return(-1);
        }
        if(synth_free_buffer(as->s, as->rightBuffer) < 0) {
            fprintf(stderr, "Failed to right channel buffer.\n");
            return(-1);
        }
        /* remake them with the new fragment size */
        if(create_mix_buffers(as) < 0) {
            return(-1);
        }

        /* re-enable the synth.  I don't entirely remember how this works but
         * this function may be called again recursively so make sure nothing
         * else happens between this and returning. */
        if(synth_set_enabled(as->s, 1) < 0) {
            /* if it is recursive, allow the error to fall through, but don't
             * print something that might end up spammy */
            return(-1);
        }
        /* don't try to generate audio that'll just be crackles anyway */
        return(0);
    }

    /* clear channel mix buffers */
    if(synth_silence_buffer(as->s, as->leftBuffer, 0, needed) < 0) {
        fprintf(stderr, "Failed to silence left buffer.\n");
        return(-1);
    }
    if(synth_silence_buffer(as->s, as->rightBuffer, 0, needed) < 0) {
        fprintf(stderr, "Failed to silence right buffer.\n");
        return(-1);
    }

    for(i = 0; i < MAX_ACTIVE_PLAYERS; i++) {
        if(as->player[i].player >= 0) {
            /* clear mix buffer */
            if(synth_silence_buffer(as->s, as->mixBuffer, 0, needed) < 0) {
                fprintf(stderr, "Failed to silence left buffer.\n");
                return(-1);
            }

            /* point active player to mix buffer */
            if(synth_set_player_output_buffer(as->s, as->player[i].player, as->mixBuffer) < 0) {
                fprintf(stderr, "failed to set active player to mix buffer.\n");
                return(-1);
            }
            /* reset the buffer output pos to 0 */
            if(synth_set_player_output_buffer_pos(as->s, as->player[i].player, 0) < 0) {
                fprintf(stderr, "Failed to set output buffer pos.\n");
                return(-1);
            }
            playerRet = synth_run_player(as->s, as->player[i].player, needed);
            /* avoid external references to mix buffer */
            if(synth_set_player_output_buffer(as->s, as->player[i].player, 0) < 0) {
                fprintf(stderr, "failed to set active player output to 0.\n");
                return(-1);
            }
            if(playerRet < 0) {
                fprintf(stderr, "Failed to play active player.\n");
                return(-1);
            } else if(playerRet == 0) {
                as->player[i].player = -1;
            } else {
                /* apply volume and panning */
                /* left channel */
                if(synth_set_player_input_buffer(as->s, as->mixPlayer, as->mixBuffer) < 0) {
                    fprintf(stderr, "Failed to set mix player input to mix buffer.\n");
                    return(-1);
                }
                if(synth_set_player_output_buffer(as->s, as->mixPlayer, as->leftBuffer) < 0) {
                    fprintf(stderr, "Failed to set mix player output to left buffer.\n");
                    return(-1);
                }
                if(as->player[i].panning > 0) {
                    volume = as->player[i].volume * (1.0 - as->player[i].panning);
                } else {
                    volume = as->player[i].volume;
                }
                if(synth_set_player_volume(as->s, as->mixPlayer, volume) < 0) {
                    fprintf(stderr, "Failed to set mix player left volume.\n");
                    return(-1);
                }
                if(synth_run_player(as->s, as->mixPlayer, needed) < 0) {
                    fprintf(stderr, "Failed to run mix player for left channel.\n");
                    return(-1);
                }
                /* right channel, reset mix buffer player to 0 */
                if(synth_set_player_input_buffer_pos(as->s, as->mixPlayer, 0) < 0) {
                    fprintf(stderr, "Failed to reset center player output pos.\n");
                    return(-1);
                }
                if(synth_set_player_output_buffer(as->s, as->mixPlayer, as->rightBuffer) < 0) {
                    fprintf(stderr, "Failed to set mix player output to right buffer.\n");
                    return(-1);
                }
                if(as->player[i].panning < 0) {
                    volume = as->player[i].volume * (1.0 + as->player[i].panning);
                } else {
                    volume = as->player[i].volume;
                }
                if(synth_set_player_volume(as->s, as->mixPlayer, volume) < 0) {
                    fprintf(stderr, "Failed to set mix player right volume.\n");
                    return(-1);
                }
                if(synth_run_player(as->s, as->mixPlayer, needed) < 0) {
                    fprintf(stderr, "Failed to run mix player for right channel.\n");
                    return(-1);
                }
            }
        }
    }

    /* play out both channels */
    if(synth_set_player_input_buffer(as->s, as->mixPlayer, as->leftBuffer) < 0) {
        fprintf(stderr, "Failed to set mix player input to left buffer.\n");
        return(-1);
    }
    if(synth_set_player_output_buffer(as->s, as->mixPlayer, 0) < 0) {
        fprintf(stderr, "Failed to set mix player output to left channel.\n");
        return(-1);
    }
    if(synth_run_player(as->s, as->mixPlayer, needed) < 0) {
        fprintf(stderr, "Failed to output to left channel.\n");
        return(-1);
    }
    if(synth_set_player_input_buffer(as->s, as->mixPlayer, as->rightBuffer) < 0) {
        fprintf(stderr, "Failed to set mix player input right buffer.\n");
        return(-1);
    }
    if(synth_set_player_output_buffer(as->s, as->mixPlayer, 1) < 0) {
        fprintf(stderr, "Failed to set mix player output to right channel.\n");
        return(-1);
    }
    if(synth_run_player(as->s, as->mixPlayer, needed) < 0) {
        fprintf(stderr, "Failed to output to right channel.\n");
        return(-1);
    }

    return(0);
}

AudioState *init_audio_state() {
    AudioState *as = malloc(sizeof(AudioState));
    unsigned int i;

    if(as == NULL) {
        fprintf(stderr, "Failed to allocate audio state.\n");
        return(NULL);
    }

    as->s = synth_new(audio_frame_cb,
                      as,
                      vprintf_cb,
                      stderr,
                      DEFAULT_RATE,
                      2);
    if(as->s == NULL) {
        fprintf(stderr, "Failed to create synth.\n");
        free(as);
        return(NULL);
    }
    if(synth_get_channels(as->s) < 2) {
        fprintf(stderr, "Mono output is unsupported.\n");
        synth_free(as->s);
        free(as);
        return(NULL);
    }

    /* set the initial fragments to 1, which will be expanded as needed */
    as->fragments = 1;
    /* clear the active synth players */
    for(i = 0; i < MAX_ACTIVE_PLAYERS; i++) {
        as->player[i].player = -1;
    }

    if(create_mix_buffers(as) < 0) {
        synth_free(as->s);
        free(as);
        return(NULL);
    }
    /* fragments need to be set so the output buffer will have been initialized */
    if(synth_set_fragments(as->s, 1) < 0) {
        fprintf(stderr, "Failed to set fragments.\n");
        synth_free(as->s);
        free(as);
        return(NULL);
    }

    return(as);
}

void free_audio_state(AudioState *as) {
    synth_free_player(as->s, as->mixPlayer);
    synth_free_buffer(as->s, as->leftBuffer);
    synth_free_buffer(as->s, as->rightBuffer);
    synth_free_buffer(as->s, as->mixBuffer);
    synth_free(as->s);
    free(as);
}

Synth *get_synth(AudioState *as) {
    return(as->s);
}

int load_sound(Synth *s,
               const char *filename,
               int *buf,
               float dB) {
    int player;
    unsigned int rate;

    *buf = synth_buffer_from_wav(s, filename, &rate);
    if(*buf < 0) {
        fprintf(stderr, "Failed to load wave.\n");
        return(-1);
    }
    player = synth_add_player(s, *buf);
    if(player < 0) {
        fprintf(stderr, "Failed to create wave player.\n");
        synth_free_buffer(s, *buf);
        *buf = -1;
        return(-1);
    }
    if(synth_set_player_speed(s, player, (float)rate / (float)synth_get_rate(s)) < 0) {
        fprintf(stderr, "Failed to set wave speed.\n");
        synth_free_player(s, player);
        synth_free_buffer(s, *buf);
        *buf = -1;
        return(-1);
    }
    if(synth_set_player_volume(s, player, volume_from_db(dB)) < 0) {
        fprintf(stderr, "Failed to set wave volume.\n");
        synth_free_player(s, player);
        synth_free_buffer(s, *buf);
        *buf = -1;
        return(-1);
    }

    return(player);
}

int play_sound(AudioState *as, unsigned int player, float volume, float panning) {
    unsigned int i;

    for(i = 0; i < MAX_ACTIVE_PLAYERS; i++) {
        if(as->player[i].player < 0) {
            break;
        }
    }
    if(i == MAX_ACTIVE_PLAYERS) {
        fprintf(stderr, "Max active players exceeded.\n");
        return(-1);
    }

    /* reset the buffer position to start */
    if(synth_set_player_input_buffer_pos(as->s, player, 0.0) < 0) {
        fprintf(stderr, "Failed to reset player input buffer pos.\n");
        return(-1);
    }

    as->player[i].player = player;
    as->player[i].volume = volume;
    as->player[i].panning = panning;
    as->player[i].token = rand();

    return(as->player[i].token);
}

void stop_sound(AudioState *as, int token) {
    unsigned int i;

    for(i = 0; i < MAX_ACTIVE_PLAYERS; i++) {
        if(as->player[i].player != -1 &&
           as->player[i].token == token) {
            break;
        }
    }
    if(i == MAX_ACTIVE_PLAYERS) {
        /* probably already stopped */
        return;
    }

    as->player[i].player = -1;
}

int update_volume(AudioState *as, int token, float volume) {
    unsigned int i;

    for(i = 0; i < MAX_ACTIVE_PLAYERS; i++) {
        if(as->player[i].player != -1 &&
           as->player[i].token == token) {
            break;
        }
    }
    if(i == MAX_ACTIVE_PLAYERS) {
        /* probably already stopped */
        return(-1);
    }

    as->player[i].volume = volume;

    return(0);
}

int update_panning(AudioState *as, int token, float panning) {
    unsigned int i;

    for(i = 0; i < MAX_ACTIVE_PLAYERS; i++) {
        if(as->player[i].player != -1 &&
           as->player[i].token == token) {
            break;
        }
    }
    if(i == MAX_ACTIVE_PLAYERS) {
        /* probably already stopped */
        return(-1);
    }

    as->player[i].panning = panning;

    return(0);
}

void play_cat_sound(GameState *gs, int player) {
    stop_sound(gs->as, gs->catSound);
    gs->catSound = play_sound(gs->as, player, 1.0, CATPAN(gs->catx));
}

int load_graphic(LayerList *ll,
                 const char *filename,
                 unsigned int tWidth,
                 unsigned int tHeight,
                 int *tileset,
                 int *tilemap,
                 const unsigned int *values,
                 const unsigned int *colormod,
                 unsigned int tmWidth,
                 unsigned int tmHeight) {
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

    return(0);
}

int create_sprite(GameState *gs) {
    int sprite;

    sprite = tilemap_add_layer(gs->ll, gs->tilemap);
    if(sprite < 0) {
        fprintf(stderr, "Failed to add layer for sprite.\n");
        return(-1);
    }

    /* make the tilemap window the size of a single sprite */
    if(tilemap_set_layer_window(gs->ll, sprite,
                                TEST_SPRITE_WIDTH,
                                TEST_SPRITE_HEIGHT) < 0) {
        fprintf(stderr, "Failed to set sprite window size.\n");
        return(-1);
    }
    /* make the rotation center in the center of the sprite so it rotates
     * about where it aims for the cursor */
    if(tilemap_set_layer_rotation_center(gs->ll, sprite,
                                         TEST_SPRITE_WIDTH / 2 * SPRITE_SCALE,
                                         TEST_SPRITE_HEIGHT / 2 * SPRITE_SCALE) < 0) {
        fprintf(stderr, "Failed to set sprite rotation center.\n");
        return(-1);
    }
    /* Makes the sprite more visible without me having to draw a larger sprite */
    if(tilemap_set_layer_scale(gs->ll, sprite,
                               SPRITE_SCALE, SPRITE_SCALE) < 0) {
        fprintf(stderr, "Failed to set sprite scale.\n");
        return(-1);
    }

    return(sprite);
}

int select_sprite(GameState *gs,
                  int layer,
                  int sprite) {
    if(tilemap_set_layer_scroll_pos(gs->ll, layer,
                                    sprite * TEST_SPRITE_WIDTH,
                                    0) < 0) {
        fprintf(stderr, "Failed to set layer scroll for sprite.\n");
        return(-1);
    }

    return(0);
}

int position_sprite(GameState *gs,
                    int layer,
                    int x,
                    int y) {
    /* position sprite based on center */
    if(tilemap_set_layer_pos(gs->ll, layer,
                             x - (TEST_SPRITE_WIDTH * SPRITE_SCALE / 2),
                             y - (TEST_SPRITE_HEIGHT * SPRITE_SCALE / 2)) < 0) {
        fprintf(stderr, "Failed to set sprite pos.\n");
        return(-1);
    }

    return(0);
}

int create_enemy(GameState *gs,
                 SpawnerType type,
                 float x,
                 float y,
                 float angle) {
    unsigned int i;

    for(i = 0; i < MAX_ENEMIES; i++) {
        if(gs->enemy[i].sprite < 0) {
            break;
        }
    }
    if(i == MAX_ENEMIES) {
        fprintf(stderr, "Max enemies exceeded.\n");
        return(-1);
    }

    switch(type) {
        case SPAWN_ANTS:
            gs->enemy[i].state = CAT_ANIM0;
            gs->enemy[i].anim = TEST_ANT0;
            gs->enemy[i].animCounter = 0;
            gs->enemy[i].maxSpeed = ANT_VELOCITY;
            gs->enemy[i].maxAngle = ANT_TURN_SPEED;
            gs->enemy[i].value = ANT_VALUE;
            gs->enemy[i].eatTime = ANT_EAT_TIME;
            gs->enemy[i].x = x;
            gs->enemy[i].y = y;
            gs->enemy[i].angle = angle;
            gs->enemy[i].deadSprite = TEST_ANT_GORE;
            break;
        case SPAWN_SPIDERS:
            gs->enemy[i].state = CAT_ANIM0;
            gs->enemy[i].anim = TEST_SPIDER0;
            gs->enemy[i].animCounter = 0;
            gs->enemy[i].maxSpeed = SPIDER_VELOCITY;
            gs->enemy[i].maxAngle = SPIDER_TURN_SPEED;
            gs->enemy[i].value = SPIDER_VALUE;
            gs->enemy[i].eatTime = SPIDER_EAT_TIME;
            gs->enemy[i].x = x;
            gs->enemy[i].y = y;
            gs->enemy[i].angle = angle;
            gs->enemy[i].deadSprite = TEST_SPIDER_GORE;
            break;
        case SPAWN_MICE:
            gs->enemy[i].state = CAT_ANIM0;
            gs->enemy[i].anim = TEST_MOUSE0;
            gs->enemy[i].animCounter = 0;
            gs->enemy[i].maxSpeed = MOUSE_VELOCITY;
            gs->enemy[i].maxAngle = MOUSE_TURN_SPEED;
            gs->enemy[i].value = MOUSE_VALUE;
            gs->enemy[i].eatTime = MOUSE_EAT_TIME;
            gs->enemy[i].x = x;
            gs->enemy[i].y = y;
            gs->enemy[i].angle = angle;
            gs->enemy[i].deadSprite = TEST_MOUSE_GORE;
            break;
        default:
            fprintf(stderr, "Invalid enemy spawn type.\n");
            return(-1);
    }

    gs->enemy[i].sprite = create_sprite(gs);
    if(gs->enemy[i].sprite < 0) {
        return(-1);
    }

    return(select_sprite(gs, gs->enemy[i].sprite, gs->enemy[i].anim));
}

float find_object_velocity(float curdist, float angle,
                           int x, int y,
                           int width, int height,
                           float velocity) {
    if(x < 0) {
        if(y < 0) {
            if(angle > M_PI * 1.5 && angle <= M_PI * 1.75) {
                float distance = sqrt(pow(-x, 2) + pow(-y, 2));
                return(SCALE(angle,
                             M_PI * 1.5, M_PI * 1.75,
                             0, distance * CAT_OFFSCREEN_DIST_FACTOR)
                       + velocity);
            } else if(angle > M_PI * 1.75 && angle <= M_PI * 2.0) {
                float distance = sqrt(pow(-x, 2) + pow(-y, 2));
                return(SCALEINV(angle,
                                M_PI * 1.75, M_PI * 2.0,
                                0, distance * CAT_OFFSCREEN_DIST_FACTOR)
                       + velocity);
            } else {
                return(velocity);
            }
        } else if(y > height) {
            if(angle > M_PI && angle <= M_PI * 1.25) {
                float distance = sqrt(pow(-x, 2) + pow(y - height, 2));
                return(SCALE(angle,
                             M_PI, M_PI * 1.25,
                             0, distance * CAT_OFFSCREEN_DIST_FACTOR)
                       + velocity);
            } else if(angle > M_PI * 1.25 && angle <= M_PI * 1.5) {
                float distance = sqrt(pow(-x, 2) + pow(y - height, 2));
                return(SCALEINV(angle,
                                M_PI * 1.25, M_PI * 1.5,
                                0, distance * CAT_OFFSCREEN_DIST_FACTOR)
                       + velocity);
            } else {
                return(velocity);
            }
        } else {
            if(angle > M_PI && angle <= M_PI * 1.5) {
                return(SCALE(angle,
                             M_PI, M_PI * 1.5,
                             0, -x * CAT_OFFSCREEN_DIST_FACTOR)
                       + velocity);
            } else if(angle > M_PI * 1.5 && angle <= M_PI * 2.0) {
                return(SCALEINV(angle,
                                M_PI * 1.5, M_PI * 2.0,
                                0, -x * CAT_OFFSCREEN_DIST_FACTOR)
                       + velocity);
            } else {
                return(velocity);
            }
        }
    } else if(x > width) { 
        if(y < 0) {
            if(angle > 0 && angle <= M_PI * 0.25) {
                float distance = sqrt(pow(x - width, 2) + pow(-y, 2));
                return(SCALE(angle,
                             0, M_PI * 0.25,
                             0, distance * CAT_OFFSCREEN_DIST_FACTOR)
                       + velocity);
            } else if(angle > M_PI * 0.25 && angle <= M_PI * 0.5) {
                float distance = sqrt(pow(x - width, 2) + pow(-y, 2));
                return(SCALEINV(angle,
                                M_PI * 0.25, M_PI * 0.5,
                                0, distance * CAT_OFFSCREEN_DIST_FACTOR)
                       + velocity);
            } else {
                return(velocity);
            }
        } else if(y > height) {
            if(angle > M_PI * 0.5 && angle <= M_PI * 0.75) {
                float distance = sqrt(pow(x - width, 2) + pow(y - height, 2));
                return(SCALE(angle,
                             M_PI * 0.5, M_PI * 0.75,
                             0, distance * CAT_OFFSCREEN_DIST_FACTOR)
                       + velocity);
            } else if(angle > M_PI * 0.75 && angle <= M_PI) {
                float distance = sqrt(pow(x - width, 2) + pow(y - height, 2));
                return(SCALEINV(angle,
                                M_PI * 0.75, M_PI,
                                0, distance * CAT_OFFSCREEN_DIST_FACTOR)
                       + velocity);
            } else {
                return(velocity);
            }
        } else {
            if(angle > 0 && angle <= M_PI * 0.5) {
                return(SCALE(angle,
                             0, M_PI * 0.5,
                             0, (x - width) * CAT_OFFSCREEN_DIST_FACTOR)
                       + velocity);
            } else if(angle > M_PI * 0.5 && angle <= M_PI) {
                return(SCALEINV(angle,
                                M_PI * 0.5, M_PI,
                                0, (x - width) * CAT_OFFSCREEN_DIST_FACTOR)
                       + velocity);
            } else {
                return(velocity);
            }
        }
    } else if(y < 0) {
        if(angle > 0 && angle <= M_PI * 0.5) {
            return(SCALEINV(angle,
                         0, M_PI * 0.5,
                         0, -y * CAT_OFFSCREEN_DIST_FACTOR)
                   + velocity);
        } else if(angle > M_PI * 1.5 && angle <= M_PI * 2.0) {
            return(SCALEINV(angle,
                            M_PI * 1.5, M_PI,
                            0, -y * CAT_OFFSCREEN_DIST_FACTOR)
                   + velocity);
        } else {
            return(velocity);
        }
    } else if(y > height) {
        if(angle > M_PI * 0.5 && angle <= M_PI) {
            return(SCALE(angle,
                         M_PI * 0.5, M_PI,
                         0, (y - height) * CAT_OFFSCREEN_DIST_FACTOR)
                   + velocity);
        } else if(angle > M_PI && angle <= M_PI * 1.5) {
            return(SCALEINV(angle,
                            M_PI, M_PI * 1.5,
                            0, (y - height) * CAT_OFFSCREEN_DIST_FACTOR)
                   + velocity);
        } else {
            return(velocity);
        }
    } else if(curdist > velocity) {
        return(velocity);
    }
    return(curdist);
}

void update_movement(float *thisx, float *thisy,
                     float targetx, float targety,
                     float maxVelocity,
                     unsigned int maxx, unsigned int maxy,
                     int *catIdleTime,
                     float *thisAngle, float maxAngle) {
    float motionx, motiony;
    float velocity;
    float angle, angleDiff;

    motionx = targetx - *thisx;
    motiony = targety - *thisy;
    velocity = velocity_from_xy(motionx, motiony);
    if(velocity >= 1.0) {
        if(catIdleTime != NULL) {
            *catIdleTime = 0;
        }

        angle = angle_from_xy(motionx, motiony);
        /* if not updating the cat, then updating an enemy, so actually move
         * _away_ from the target */
        if(catIdleTime == NULL) {
            angle += M_PI;
            if(angle >= M_PI * 2) {
                angle -= M_PI * 2;
            }
        }
        if(*thisAngle > M_PI && angle < *thisAngle - M_PI) {
            angle += M_PI * 2;
        } else if(*thisAngle < M_PI && angle > *thisAngle + M_PI) {
            angle -= M_PI * 2;
        }
        angleDiff = *thisAngle - angle;
        if(angleDiff > maxAngle) {
            angleDiff = maxAngle;
        } else if(angleDiff < -maxAngle) {
            angleDiff = -maxAngle;
        }
        *thisAngle -= angleDiff;
        if(*thisAngle < 0.0) {
            *thisAngle += M_PI * 2;
        } else if(*thisAngle >= M_PI * 2) {
            *thisAngle -= M_PI * 2;
        }
       
        velocity = find_object_velocity(velocity, *thisAngle,
                                        *thisx, *thisy,
                                        maxx, maxy,
                                        maxVelocity);
        xy_from_angle(&motionx, &motiony, *thisAngle);
        *thisx += motionx * velocity;
        *thisy += motiony * velocity;
    } else {
        if(catIdleTime != NULL) {
            *catIdleTime += ACTOR_RATE;
        }
    }
}

int clear_hud(GameState *gs) {
    unsigned int temp[HUD_WIDTH * HUD_HEIGHT];
    unsigned int i;

    for(i = 0; i < HUD_WIDTH * HUD_HEIGHT; i++) {
        temp[i] = ' ';
    }

    if(tilemap_set_tilemap_map(gs->ll, gs->hudTilemap,
                               0, 0,
                               HUD_WIDTH,
                               HUD_WIDTH, HUD_HEIGHT,
                               temp, HUD_WIDTH * HUD_HEIGHT) < 0) {
        fprintf(stderr, "Failed to set clear tilemap.\n");
        return(-1);
    }
    if(tilemap_update_tilemap(gs->ll, gs->hudTilemap,
                              0, 0,
                              HUD_WIDTH, HUD_HEIGHT) < 0) {
        fprintf(stderr, "Failed to clear hud tilemap.\n");
        return(-1);
    }

    return(0);
}

int print_score_to_hud(GameState *gs) {
    int scorelen;

    /* a potentially unbound operation, but the number should never be
     * long enough to extend past the tilemap bounds, and the tielmap
     * engine should error if that ends up the case */
    scorelen = printf_to_tilemap(gs->ll, gs->hudTilemap,
                                 TEXT_SCORE_X + (sizeof(TEXT_SCORE) - 1), TEXT_SCORE_Y,
                                 HUD_WIDTH - TEXT_SCORE_X - (sizeof(TEXT_SCORE) - 1),
                                 "%d", gs->score);
    if(scorelen < 0) {
        fprintf(stderr, "Failed to print score.\n");
        return(-1);
    }
    if(tilemap_update_tilemap(gs->ll, gs->hudTilemap,
                              TEXT_SCORE_X + (sizeof(TEXT_SCORE) - 1), TEXT_SCORE_Y,
                              scorelen, 1) < 0) {
        fprintf(stderr, "Failed to update hud tilemap.\n");
        return(-1);
    }

    return(0);
}

int process_enemies(GameState *gs) {
    unsigned int i;
    unsigned int gore;

    for(i = 0; i < MAX_ENEMIES; i++) {
        if(gs->enemy[i].sprite < 0) {
            continue;
        }

        if(gs->eating <= 0 &&
           distance(gs->catx, gs->caty,
                    gs->enemy[i].x, gs->enemy[i].y) < CAT_DISTANCE) {
            /* despawn eaten enemy */
            gs->enemy[i].sprite = -1;
            gs->eating = gs->enemy[i].eatTime;
            gs->score += gs->enemy[i].value;
            if(gs->score < 0) {
                gs->score = 0;
            }
            if(print_score_to_hud(gs) < 0) {
                return(-1);
            }

            /* render to gore texture */
            tilemap_set_default_render_target(gs->ll, gs->goreTex);
            if(tilemap_set_target_tileset(gs->ll, -1) < 0) {
                fprintf(stderr, "Failed to set target tileset.\n");
                return(-1);
            }

            if(position_sprite(gs, gs->goreSprite,
                               gs->enemy[i].x, gs->enemy[i].y) < 0) {
                return(-1);
            }
            if(tilemap_set_layer_rotation(gs->ll, gs->goreSprite,
                                          SCALE((double)rand(),
                                                0.0, (double)RAND_MAX,
                                                0.0, 360.0)) < 0) {
                fprintf(stderr, "Failed to set gore sprite rotation.\n");
                return(-1);
            }

            gore = (rand() % 3) + 1;
            if(gore & 1) {
                if(select_sprite(gs, gs->goreSprite,
                                 gs->enemy[i].deadSprite) < 0) {
                    return(-1);
                }
                if(tilemap_draw_layer(gs->ll, gs->goreSprite) < 0) {
                    fprintf(stderr, "Failed to draw gore sprite.\n");
                    return(-1);
                }
            }
            if(gore & 2) {
                if(select_sprite(gs, gs->goreSprite,
                                 TEST_BONES) < 0) {
                    return(-1);
                }
                if(tilemap_draw_layer(gs->ll, gs->goreSprite) < 0) {
                    fprintf(stderr, "Failed to draw bones sprite.\n");
                    return(-1);
                }
            }

            /* render to screen */
            tilemap_set_default_render_target(gs->ll, NULL);
            if(tilemap_set_target_tileset(gs->ll, -1) < 0) {
                fprintf(stderr, "Failed to set target tileset.\n");
                return(-1);
            }

            /* play the sound */
            if(rand() % 2 == 0) {
                play_cat_sound(gs, gs->meat);
            } else {
                play_cat_sound(gs, gs->meat2);
            }
            continue;
        } else {
            update_movement(&(gs->enemy[i].x), &(gs->enemy[i].y),
                            gs->catx, gs->caty,
                            gs->enemy[i].maxSpeed,
                            WINDOW_WIDTH, WINDOW_HEIGHT,
                            NULL,
                            &(gs->enemy[i].angle), gs->enemy[i].maxAngle);
            /* invalidate any enemies which have gone of screen */
            if(gs->enemy[i].x < -(TEST_SPRITE_WIDTH * SPRITE_SCALE / 2.0) ||
               gs->enemy[i].x > WINDOW_WIDTH + (TEST_SPRITE_WIDTH * SPRITE_SCALE / 2.0) ||
               gs->enemy[i].y < -(TEST_SPRITE_HEIGHT * SPRITE_SCALE / 2.0) ||
               gs->enemy[i].y > WINDOW_HEIGHT + (TEST_SPRITE_HEIGHT * SPRITE_SCALE / 2.0)) {
                gs->enemy[i].sprite = -1;
                continue;
            }
        }

        gs->enemy[i].animCounter++;
        if(gs->enemy[i].animCounter >= CAT_ANIM_DIV) {
            if(gs->enemy[i].state == CAT_ANIM0) {
                gs->enemy[i].state = CAT_ANIM1;
                gs->enemy[i].anim++;
            } else {
                gs->enemy[i].state = CAT_ANIM0;
                gs->enemy[i].anim--;
            }

            if(select_sprite(gs, gs->enemy[i].sprite, gs->enemy[i].anim) < 0) {
                return(-1);
            }
            gs->enemy[i].animCounter = 0;
        }

        if(position_sprite(gs, gs->enemy[i].sprite,
                           gs->enemy[i].x, gs->enemy[i].y) < 0) {
            return(-1);
        }
        if(tilemap_set_layer_rotation(gs->ll, gs->enemy[i].sprite,
                                      radian_to_degree(gs->enemy[i].angle)) < 0) {
            fprintf(stderr, "Failed to set enemy sprite rotation.\n");
            return(-1);
        }
    }

    return(0);
}

int draw_enemies(GameState *gs) {
    unsigned int i;

    for(i = 0; i < MAX_ENEMIES; i++) {
        if(gs->enemy[i].sprite < 0) {
            continue;
        }

        if(tilemap_draw_layer(gs->ll, gs->enemy[i].sprite) < 0) {
            return(-1);
        }
    }

    return(0);
}

void reset_state(GameState *gs) {
    unsigned int i;

    stop_sound(gs->as, gs->catSound);

    gs->catx = (WINDOW_WIDTH - TEST_SPRITE_WIDTH) / 2;
    gs->caty = (WINDOW_HEIGHT - TEST_SPRITE_HEIGHT) / 2;
    gs->catState = CAT_ANIM0;
    gs->catAnim = TEST_ANIM0;
    gs->catAngle = 0.0;
    gs->catIdleTime = 0;
    gs->eating = 0;
    gs->catSound = 0;
    gs->animCounter = 0;
    gs->zzzcycle = 0.0;
    gs->spawner = SPAWN_NONE;
    gs->spawnerTimer = RANDRANGE(MIN_SPAWNER_TIME, MAX_SPAWNER_TIME);
    gs->spawnerx = RANDRANGE(0, WINDOW_WIDTH);
    gs->spawnery = RANDRANGE(0, WINDOW_HEIGHT);
    gs->spawnerCount = 0;
    for(i = 0; i < MAX_ENEMIES; i++) {
        gs->enemy[i].sprite = -1;
    }
    gs->score = 0;
}

int update_cat(GameState *gs) {
    if(gs->catState != CAT_RESTING) {
        int lastCatIdleTime = gs->catIdleTime;
        update_movement(&(gs->catx), &(gs->caty),
                        gs->mousex, gs->mousey,
                        CAT_VELOCITY,
                        WINDOW_WIDTH, WINDOW_HEIGHT,
                        &(gs->catIdleTime),
                        &(gs->catAngle), CAT_TURN_SPEED);
        if(lastCatIdleTime - gs->catIdleTime >= CAT_IDLE_MEOW) {
            if(rand() % 2 == 1) {
                play_cat_sound(gs, gs->meow1);
            } else {
                play_cat_sound(gs, gs->meow2);
            }
        }
        if(position_sprite(gs, gs->catlayer,
                           gs->catx, gs->caty) < 0) {
            return(-1);
        }
        if(tilemap_set_layer_rotation(gs->ll, gs->catlayer,
                                      radian_to_degree(gs->catAngle)) < 0) {
            fprintf(stderr, "Failed to set layer rotation.\n");
            return(-1);
        }

        update_panning(gs->as, gs->catSound, CATPAN(gs->catx));

        gs->animCounter++;
        if(gs->animCounter >= CAT_ANIM_DIV) {
            if(gs->catState == CAT_ANIM0) {
                gs->catState = CAT_ANIM1;
                gs->catAnim++;
            } else {
                gs->catState = CAT_ANIM0;
                gs->catAnim--;
            }

            if(select_sprite(gs, gs->catlayer, gs->catAnim) < 0) {
                return(-1);
            }

            gs->animCounter = 0;
        }
    } else { /* CAT_RESTING */
        gs->zzzcycle += ZZZ_CYCLE_SPEED;
        if(gs->zzzcycle >= M_PI * 2) {
            gs->zzzcycle -= M_PI * 2;
        }

        if(position_sprite(gs, gs->zzzlayer,
                           gs->catx + (TEST_SPRITE_WIDTH * SPRITE_SCALE * ZZZ_POS_X),
                           gs->caty + (TEST_SPRITE_HEIGHT * SPRITE_SCALE * ZZZ_POS_Y) + 
                           ((sin(gs->zzzcycle) - 1.0) * ZZZ_AMP * SPRITE_SCALE)) < 0) {
            return(-1);
        }
        if(tilemap_set_layer_colormod(gs->ll, gs->zzzlayer,
                                      color_from_angle(gs->zzzcycle,
                                                       ZZZ_COLOR_BIAS)) < 0) {
            fprintf(stderr, "Failed to set ZZZ colormod.\n");
            return(-1);
        }
    }

    return(0);
}

int toggle_cat_mode(GameState *gs) {
    if(gs->catState == CAT_RESTING) {
        gs->catState = CAT_ANIM0;
        gs->catAnim = TEST_ANIM0;
        if(tilemap_free_layer(gs->ll, gs->zzzlayer) < 0) {
            fprintf(stderr, "Failed to free ZZZ layer.\n");
            return(-1);
        }

        play_cat_sound(gs, gs->cat_activation);
    } else {
        gs->catState = CAT_RESTING;
        if(select_sprite(gs, gs->catlayer, TEST_RESTING) < 0) {
            return(-1);
        }

        gs->zzzlayer = create_sprite(gs);
        if(gs->zzzlayer < 0) {
            return(-1);
        }
        if(select_sprite(gs, gs->zzzlayer, TEST_ZZZ) < 0) {
            return(-1);
        }
        
        play_cat_sound(gs, gs->purr);
    }

    return(0);
}

int prepare_frame(GameState *gs) {
    /* clear the display, otherwise it'll show flickery garbage */
    if(SDL_SetRenderDrawColor(gs->renderer,
                              0, 0, 0,
                              SDL_ALPHA_OPAQUE) < 0) {
        fprintf(stderr, "Failed to set render draw color.\n");
        return(-1);
    } 
    if(SDL_RenderClear(gs->renderer) < 0) {
        fprintf(stderr, "Failed to clear screen.\n");
        return(-1);
    }
    if(SDL_SetRenderDrawColor(gs->renderer,
                              BG_R, BG_G, BG_B,
                              SDL_ALPHA_OPAQUE) < 0) {
        fprintf(stderr, "Failed to set render draw color.\n");
        return(-1);
    } 
    if(SDL_RenderFillRect(gs->renderer, NULL) < 0) {
        fprintf(stderr, "Failed to fill background.\n");
        return(-1);
    }

    /* needs to be transparent so tilemap updates work */
    if(SDL_SetRenderDrawColor(gs->renderer,
                              0, 0, 0,
                              SDL_ALPHA_TRANSPARENT) < 0) {
        fprintf(stderr, "Failed to set render draw color.\n");
        return(-1);
    } 

    return(0);
}

int draw_cat(GameState *gs) {
    if(tilemap_draw_layer(gs->ll, gs->catlayer) < 0) {
        fprintf(stderr, "Failed to draw cat layer.\n");
        return(-1);
    }
    if(gs->catState == CAT_RESTING) {
        if(tilemap_draw_layer(gs->ll, gs->zzzlayer) < 0) {
            fprintf(stderr, "Failed to draw ZZZ layer.\n");
            return(-1);
        }
    }

    return(0);
}

int draw_hud(GameState *gs) {
    if(tilemap_set_layer_pos(gs->ll, gs->hud,
                             HUD_SCALE, HUD_SCALE) < 0) {
        fprintf(stderr, "Failed to set hud layer pos.\n");
        return(-1);
    }
    if(tilemap_set_layer_blendmode(gs->ll, gs->hud,
                                   TILEMAP_BLENDMODE_SUB) < 0) {
        fprintf(stderr, "Failed to set hud blend mode.\n");
        return(-1);
    }
    if(tilemap_set_layer_colormod(gs->ll, gs->hud,
                                  C_HUD_SHADOW) < 0) {
        fprintf(stderr, "Failed to set hud colormod.\n");
        return(-1);
    }
    if(tilemap_draw_layer(gs->ll, gs->hud) < 0) {
        fprintf(stderr, "Failed to draw hud layer.\n");
        return(-1);
    }
    if(tilemap_set_layer_pos(gs->ll, gs->hud, 0, 0) < 0) {
        fprintf(stderr, "Failed to set hud layer pos.\n");
        return(-1);
    }
    if(tilemap_set_layer_blendmode(gs->ll, gs->hud,
                                   TILEMAP_BLENDMODE_BLEND) < 0) {
        fprintf(stderr, "Failed to set hud blend mode.\n");
        return(-1);
    }
    if(tilemap_set_layer_colormod(gs->ll, gs->hud,
                                  C_OPAQUE) < 0) {
        fprintf(stderr, "Failed to set hud colormod.\n");
        return(-1);
    }
    if(tilemap_draw_layer(gs->ll, gs->hud) < 0) {
        fprintf(stderr, "Failed to draw hud layer.\n");
        return(-1);
    }

    return(0);
}

int game_setup(GameState *gs) {
    reset_state(gs);

    if(clear_hud(gs) < 0) {
        return(-1);
    }
    if(print_to_hud(gs, TEXT_SCORE, TEXT_SCORE_X, TEXT_SCORE_Y) < 0) {
        return(-1);
    }
    if(print_score_to_hud(gs) < 0) {
        return(-1);
    }

    return(0);
}

int title_input(void *priv, SDL_Event *event) {
    GameState *gs = (GameState *)priv;
    SDL_KeyboardEvent *key = (SDL_KeyboardEvent *)event;
    SDL_MouseMotionEvent *motion = (SDL_MouseMotionEvent *)event;
    SDL_MouseButtonEvent *click = (SDL_MouseButtonEvent *)event;

    switch(event->type) {
        case SDL_KEYDOWN:
            /* suppress repeat events */
            if(key->repeat) {
                break;
            }

            if(key->keysym.sym == SDLK_RETURN) {
                if(game_setup(gs) < 0) {
                    return(-1);
                }

                gs->nextMode = &(gs->game);
            }
            break;
        case SDL_MOUSEMOTION:
            gs->mousex = motion->x;
            gs->mousey = motion->y;
            break;
        case SDL_MOUSEBUTTONDOWN:
            if(click->button == 1) {
                if(toggle_cat_mode(gs) < 0) {
                    return(-1);
                }
            }
            break;
        default:
            break;
    }

    return(0);
}

GameMode* title_control(void *priv) {
    GameState *gs = (GameState *)priv;
    GameMode *next;

    if(update_cat(gs) < 0) {
        return(NULL);
    }

    if(gs->nextMode != NULL) {
        next = gs->nextMode;
        gs->nextMode = NULL;
        return(next);
    }

    return(&(gs->title));
}

int title_draw(void *priv) {
    GameState *gs = (GameState *)priv;

    if(draw_cat(gs) < 0) {
        return(-1);
    }

    if(tilemap_draw_layer(gs->ll, gs->titleLayer) < 0) {
        fprintf(stderr, "Failed to draw title layer.\n");
        return(-1);
    }

    if(draw_hud(gs) < 0) {
        return(-1);
    }

    return(0);
}

int game_input(void *priv, SDL_Event *event) {
    GameState *gs = (GameState *)priv;
    SDL_MouseMotionEvent *motion = (SDL_MouseMotionEvent *)event;
    SDL_MouseButtonEvent *click = (SDL_MouseButtonEvent *)event;

    switch(event->type) {
        case SDL_MOUSEMOTION:
            gs->mousex = motion->x;
            gs->mousey = motion->y;
            break;
        case SDL_MOUSEBUTTONDOWN:
            if(click->button == 1) {
                if(toggle_cat_mode(gs) < 0) {
                    return(-1);
                }
            }
            break;
        default:
            break;
    }

    return(0);
}

GameMode* game_control(void *priv) {
    GameState *gs = (GameState *)priv;

    if(gs->eating > 0) {
        gs->eating -= ACTOR_RATE;
    }

    if(update_cat(gs) < 0) {
        return(NULL);
    }

    switch(gs->spawner) {
        case SPAWN_ANTS:
            gs->spawnerTimer -= ACTOR_RATE;
            while(gs->spawnerTimer < 0) {
                if(gs->spawnerCount == 0) {
                    gs->spawnerTimer += RANDRANGE(MIN_SPAWNER_TIME, MAX_SPAWNER_TIME);
                    gs->spawner = SPAWN_NONE;
                    break;
                }

                gs->spawnerTimer += RANDRANGE(ANT_SPAWN_TIME_MIN, ANT_SPAWN_TIME_MAX);
                if(create_enemy(gs, SPAWN_ANTS,
                                gs->spawnerx, gs->spawnery,
                                SCALE((double)rand(),
                                      0.0, RAND_MAX,
                                      0.0, M_PI * 2.0)) < 0) {
                    return(NULL);
                }
                gs->spawnerCount--;
            }
            break;
        case SPAWN_SPIDERS:
            gs->spawnerTimer -= ACTOR_RATE;
            while(gs->spawnerTimer < 0) {
                if(gs->spawnerCount == 0) {
                    gs->spawnerTimer += RANDRANGE(MIN_SPAWNER_TIME, MAX_SPAWNER_TIME);
                    gs->spawner = SPAWN_NONE;
                    break;
                }

                gs->spawnerTimer += RANDRANGE(SPIDER_SPAWN_TIME_MIN, SPIDER_SPAWN_TIME_MAX);
                if(create_enemy(gs, SPAWN_SPIDERS,
                                gs->spawnerx, gs->spawnery,
                                SCALE((double)rand(),
                                      0.0, RAND_MAX,
                                      0.0, M_PI * 2.0)) < 0) {
                    return(NULL);
                }
                gs->spawnerCount--;
            }
            break;
        case SPAWN_MICE:
            gs->spawnerTimer -= ACTOR_RATE;
            while(gs->spawnerTimer < 0) {
                if(gs->spawnerCount == 0) {
                    gs->spawnerTimer += RANDRANGE(MIN_SPAWNER_TIME, MAX_SPAWNER_TIME);
                    gs->spawner = SPAWN_NONE;
                    break;
                }

                gs->spawnerTimer += RANDRANGE(MOUSE_SPAWN_TIME_MIN, MOUSE_SPAWN_TIME_MAX);
                if(create_enemy(gs, SPAWN_MICE,
                                gs->spawnerx, gs->spawnery,
                                SCALE((double)rand(),
                                      0.0, RAND_MAX,
                                      0.0, M_PI * 2.0)) < 0) {
                    return(NULL);
                }
                gs->spawnerCount--;
            }
            break;
        default:
            gs->spawnerTimer -= ACTOR_RATE;
            if(gs->spawnerTimer < 0) {
                gs->spawnerx = RANDRANGE(0, WINDOW_WIDTH);
                gs->spawnery = RANDRANGE(0, WINDOW_HEIGHT);
                if(select_sprite(gs, gs->spawnerSprite, TEST_BIGHOLE) < 0) {
                    return(NULL);
                }

                if(position_sprite(gs, gs->spawnerSprite,
                                   gs->spawnerx, gs->spawnery) < 0) {
                    return(NULL);
                }

                switch(rand() % 3) {
                    case 0:
                        gs->spawner = SPAWN_ANTS;
                        gs->spawnerCount = RANDRANGE(ANT_SPAWN_MIN, ANT_SPAWN_MAX);
                        gs->spawnerTimer += RANDRANGE(ANT_SPAWN_TIME_MIN, ANT_SPAWN_TIME_MAX);
                        break;
                    case 1:
                        gs->spawner = SPAWN_SPIDERS;
                        gs->spawnerCount = RANDRANGE(SPIDER_SPAWN_MIN, SPIDER_SPAWN_MAX);
                        gs->spawnerTimer += RANDRANGE(SPIDER_SPAWN_TIME_MIN, SPIDER_SPAWN_TIME_MAX);
                        break;
                    default:
                        gs->spawner = SPAWN_MICE;
                        gs->spawnerCount = RANDRANGE(MOUSE_SPAWN_MIN, MOUSE_SPAWN_MAX);
                        gs->spawnerTimer += RANDRANGE(MOUSE_SPAWN_TIME_MIN, MOUSE_SPAWN_TIME_MAX);
                }
            }
    }

    /* needs to be transparent since process enemies can draw to the gore
     * layer */
    if(SDL_SetRenderDrawColor(gs->renderer,
                              0, 0, 0,
                              SDL_ALPHA_TRANSPARENT) < 0) {
        fprintf(stderr, "Failed to set render draw color.\n");
        return(NULL);
    } 

    if(process_enemies(gs) < 0) {
        return(NULL);
    }

    return(&(gs->game));
}

int game_draw(void *priv) {
    GameState *gs = (GameState *)priv;

    /* draw the gore layer below eveyrthing */
    if(SDL_RenderCopy(gs->renderer, gs->goreTex, NULL, NULL) < 0) {
        fprintf(stderr, "Failed to copy gore layer.\n");
        return(-1);
    }

    if(gs->spawner != SPAWN_NONE) {
        if(tilemap_draw_layer(gs->ll, gs->spawnerSprite) < 0) {
            fprintf(stderr, "Failed to draw spawner.\n");
            return(-1);
        }
    }

    if(draw_enemies(gs) < 0) {
        return(-1);
    }

    if(draw_cat(gs) < 0) {
        return(-1);
    }

    /* draw the hud above everything */
    if(draw_hud(gs) < 0) {
        return(-1);
    }

    return(0);
}

int main(int argc, char **argv) {
    SDL_Window *win;
    Uint32 format;
    SDL_Event lastEvent;
    Synth *s;
    GameState gs;
    int fullscreen;
    int tileset = -1;
    int font = -1;
    int tsTitle = -1;
    int tmTitle = -1;
    Uint32 nextMotion = SDL_GetTicks() + ACTOR_RATE;
    int meow1_buf, meow2_buf, cat_activation_buf, purr_buf;
    int meat_buf, meat2_buf;
    GameMode *mode = &(gs.title);

    gs.game.input = game_input;
    gs.game.control = game_control;
    gs.game.draw = game_draw;
    gs.game.priv = &gs;
    gs.title.input = title_input;
    gs.title.control = title_control;
    gs.title.draw = title_draw;
    gs.title.priv = &gs;
    gs.nextMode = NULL;

    if(SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO) < 0) {
        fprintf(stderr, "Failed to initialize SDL: %s\n",
                SDL_GetError());
        exit(EXIT_FAILURE);
    }

    if(initialize_video(&win, &(gs.renderer), &format) < 0) {
        fprintf(stderr, "Failed to initialize video.\n");
        goto error_sdl;
    }

    /* fix the logical resolution (play field size, in this case) */
    if(SDL_RenderSetLogicalSize(gs.renderer,
                                WINDOW_WIDTH,
                                WINDOW_HEIGHT) < 0) {
        fprintf(stderr, "Failed to set render logical size.\n");
        goto error_video;
    }

    /* initialize the layerlist */
    gs.ll = layerlist_new(gs.renderer, format,
                          vprintf_cb, stderr);
    if(gs.ll == NULL) {
        fprintf(stderr, "Failed to create layerlist.\n");
        goto error_video;
    }

    /* initialize the audio */
    gs.as = init_audio_state();
    if(gs.as == NULL) {
        goto error_ll;
    }
    s = get_synth(gs.as);

    /* seed random */
    srand(time(NULL));

    /* init stuff */

    gs.goreTex = NULL;

    gs.tilemap = -1;
    if(load_graphic(gs.ll, TEST_SPRITESHEET,
                    TEST_SPRITE_WIDTH, TEST_SPRITE_HEIGHT,
                    &tileset, &(gs.tilemap),
                    TEST_SPRITESHEET_VALUES,
                    TEST_SPRITESHEET_COLORMOD,
                    ARRAY_COUNT(TEST_SPRITESHEET_VALUES), 1) < 0) {
        goto error_synth;
    }

    gs.catlayer = create_sprite(&gs);
    if(gs.catlayer < 0) {
        goto error_synth;
    }

    gs.spawnerSprite = create_sprite(&gs);
    if(gs.spawnerSprite < 0) {
        goto error_synth;
    }

    gs.hudTilemap = -1;
    if(load_graphic(gs.ll, "font.bmp",
                    8, 8,
                    &font, &(gs.hudTilemap),
                    NULL,
                    NULL,
                    HUD_WIDTH, HUD_HEIGHT) < 0) {
        goto error_synth;
    }
    gs.hud = tilemap_add_layer(gs.ll, gs.hudTilemap);
    if(gs.hud < 0) {
        fprintf(stderr, "Failed to create HUD layer.\n");
        goto error_synth;
    }
    if(tilemap_set_layer_scale(gs.ll, gs.hud, HUD_SCALE, HUD_SCALE) < 0) {
        fprintf(stderr, "Failed to set hud scale.\n");
        goto error_synth;
    }

    unsigned int titleTilemap = 0;
    if(load_graphic(gs.ll, "title.bmp",
                    256, 192,
                    &tsTitle, &tmTitle,
                    &titleTilemap,
                    NULL,
                    1, 1) < 0) {
        goto error_synth;
    }
    gs.titleLayer = tilemap_add_layer(gs.ll, tmTitle);
    if(gs.titleLayer < 0) {
        fprintf(stderr, "Failed to create title layer.\n");
        goto error_synth;
    }
    if(tilemap_set_layer_scale(gs.ll, gs.titleLayer,
                               SPRITE_SCALE, SPRITE_SCALE) < 0) {
        fprintf(stderr, "Failed to set title scale.\n");
        goto error_synth;
    }
    if(tilemap_set_layer_pos(gs.ll, gs.titleLayer,
                             CENTER(WINDOW_WIDTH, 256 * SPRITE_SCALE),
                             (WINDOW_HEIGHT - (192 * SPRITE_SCALE)) / 4) < 0) {
        fprintf(stderr, "Failed to set title pos.\n");
        goto error_synth;
    }

    /* create and clear the gore texture */
    gs.goreTex = SDL_CreateTexture(gs.renderer, format,
                                   SDL_TEXTUREACCESS_TARGET,
                                   WINDOW_WIDTH,
                                   WINDOW_HEIGHT);
    if(gs.goreTex == NULL) {
        fprintf(stderr, "Failed to create gore layer texture.\n");
        goto error_synth;
    }
    if(SDL_SetTextureBlendMode(gs.goreTex, SDL_BLENDMODE_BLEND) < 0) {
        fprintf(stderr, "Failed to set gore texture blend mode.\n");
        goto error_synth;
    }
    if(SDL_SetRenderTarget(gs.renderer, gs.goreTex) < 0) {
        fprintf(stderr, "Failed to set render target to gore texture.\n");
        goto error_synth;
    }
    if(SDL_SetRenderDrawColor(gs.renderer,
                              0, 0, 0,
                              SDL_ALPHA_TRANSPARENT) < 0) {
        fprintf(stderr, "Failed to set render draw color.\n");
        goto error_synth;
    } 
    if(SDL_RenderClear(gs.renderer) < 0) {
        fprintf(stderr, "Failed to clear gore texture.\n");
        goto error_synth;
    }
    /* restore screen rendering */
    if(SDL_SetRenderTarget(gs.renderer, NULL) < 0) {
        fprintf(stderr, "Failed to set render target to screen.\n");
        goto error_synth;
    }
    gs.goreSprite = create_sprite(&gs);
    if(gs.goreSprite < 0) {
        goto error_synth;
    }

    /* load the sound effects and create players for them, as they may
     * eventually each have different parameters for volume balance or
     * whatever else */
    gs.meow1 = load_sound(s, "meow1.wav", &meow1_buf, 0.0);
    if(gs.meow1 < 0) {
        goto error_synth;
    }
    gs.meow2 = load_sound(s, "meow2.wav", &meow2_buf, -3.0);
    if(gs.meow2 < 0) {
        goto error_synth;
    }
    gs.cat_activation = load_sound(s, "cat_activation.wav", &cat_activation_buf, -12.0);
    if(gs.cat_activation < 0) {
        goto error_synth;
    }
    gs.purr = load_sound(s, "purr.wav", &purr_buf, -2.0);
    if(gs.purr < 0) {
        goto error_synth;
    }
    if(synth_set_player_mode(s, gs.purr, SYNTH_MODE_LOOP) < 0) {
        fprintf(stderr, "Failed to set purr to looping.\n");
        goto error_synth;
    }
    gs.meat = load_sound(s, "meat.wav", &meat_buf, 0.0);
    if(gs.meat < 0) {
        goto error_synth;
    }
    gs.meat2 = load_sound(s, "meat2.wav", &meat2_buf, 0.0);
    if(gs.meat2 < 0) {
        goto error_synth;
    }

    if(synth_set_enabled(s, 1) < 0) {
        fprintf(stderr, "Failed to enable synth.\n");
        goto error_synth;
    }

    if(clear_hud(&gs) < 0) {
        goto error_synth;
    }
    if(print_to_hud(&gs, TEXT_START, TEXT_START_X, TEXT_START_Y) < 0) {
        goto error_synth;
    }

    reset_state(&gs);
    gs.mousex = gs.catx;
    gs.mousey = gs.caty;
    fullscreen = 0;

    /* ##### MAIN LOOP ##### */
    while(mode != NULL) {
        /* check mode since an event may end execution early */
        while(mode != NULL && SDL_PollEvent(&lastEvent)) {
            /* handle SDL_QUIT and some global hotkeys */
            if(lastEvent.type == SDL_QUIT) {
                mode = NULL;
                continue;
            } else if(lastEvent.type == SDL_KEYDOWN) {
                switch(((SDL_KeyboardEvent *)&lastEvent)->keysym.sym) {
                    case SDLK_q:
                        mode = NULL;
                        continue;
                    case SDLK_e:
                        /* simulate an error */
                        goto error_synth;
                    case SDLK_f:
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
                        continue;
                }
            }

            /* handle all other inputs */
            if(mode->input(mode->priv, &lastEvent) < 0) {
                goto error_synth;
            }
        }

        /* run the synth */
        if(mode != NULL && synth_frame(s) < 0) {
            fprintf(stderr, "Audio failed.\n");
            goto error_synth;
        }

        /* frame stuff, try to keep thisTick ahead of nextMotion, but if
         * things are just running really badly for some reason, just give up
         * if things get too far behind and maybe it'll eventually be able to
         * catch up.  It'll slow down but still be able to display something
         * and poll for events */
        Uint32 thisTick = SDL_GetTicks();
        Uint32 processTime = thisTick;
        while(mode != NULL &&
              thisTick >= nextMotion &&
              thisTick - processTime < MAX_PROCESS_TIME) {
            nextMotion += ACTOR_RATE;
            
            mode = mode->control(mode->priv);
            if(mode == NULL) {
                goto error_synth;
            }

            thisTick = SDL_GetTicks();
        }

        if(mode != NULL) {
            if(prepare_frame(&gs) < 0) {
                goto error_synth;
            }

            if(mode->draw(mode->priv) < 0) {
                goto error_synth;
            }
        }

        SDL_RenderPresent(gs.renderer);
    }

    /* test cleanup functions */
    synth_free_player(s, gs.meat);
    synth_free_buffer(s, meat_buf);
    synth_free_player(s, gs.meat2);
    synth_free_buffer(s, meat2_buf);
    synth_free_player(s, gs.purr);
    synth_free_buffer(s, purr_buf);
    synth_free_player(s, gs.cat_activation);
    synth_free_buffer(s, cat_activation_buf);
    synth_free_player(s, gs.meow1);
    synth_free_buffer(s, meow1_buf);
    synth_free_player(s, gs.meow2);
    synth_free_buffer(s, meow2_buf);
    free_audio_state(gs.as);

    tilemap_free_layer(gs.ll, gs.hud);
    tilemap_free_tilemap(gs.ll, gs.hudTilemap);
    tilemap_free_tileset(gs.ll, font);
    tilemap_free_layer(gs.ll, gs.goreSprite);
    tilemap_free_layer(gs.ll, gs.catlayer);
    tilemap_free_tilemap(gs.ll, gs.tilemap);
    tilemap_free_tileset(gs.ll, tileset);
    layerlist_free(gs.ll);

    SDL_DestroyWindow(win);
    SDL_Quit();

    exit(EXIT_SUCCESS);

    /* don't try to call any free methods other than the subsystems to test
     * behavior on exiting if that's left out */
error_synth:
    free_audio_state(gs.as);
    if(gs.goreTex != NULL) {
        SDL_DestroyTexture(gs.goreTex);
    }
error_ll:
    layerlist_free(gs.ll);
error_video:
    SDL_DestroyWindow(win);
error_sdl:
    SDL_Quit();

    exit(EXIT_FAILURE);
}
