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

#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <math.h>
#include <SDL.h>

#include "tilemap.h"
#include "synth.h"

/* initial settings */
#define MAX_PROCESS_TIME (200)
#define WINDOW_TITLE    "UnCrustyGame Test"
#define WINDOW_WIDTH    (1280)
#define WINDOW_HEIGHT   (720)
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
#define ZZZ_AMP          (10)
#define ZZZ_CYCLE_SPEED  (M_PI * 2.0 / ACTOR_FPS / 3.0)
#define ZZZ_COLOR_BIAS   (64)
/* from bottom-left */
#define ZZZ_POS_X        (0.75)
#define ZZZ_POS_Y        (0.75)

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
#define SPIDER_SPAWN_MIN (10)
#define SPIDER_SPAWN_MAX (50)
#define SPIDER_SPAWN_TIME_MIN (20)
#define SPIDER_SPAWN_TIME_MAX (50)
#define SPIDER_VELOCITY  (2.0)
#define SPIDER_TURN_SPEED (M_PI * 2.0 / ACTOR_FPS * 1.8)
#define SPIDER_VALUE     (50)
#define MOUSE_SPAWN_MIN  (2)
#define MOUSE_SPAWN_MAX  (10)
#define MOUSE_SPAWN_TIME_MIN (100)
#define MOUSE_SPAWN_TIME_MAX (500)
#define MOUSE_VELOCITY   (4.0)
#define MOUSE_TURN_SPEED (M_PI * 2.0 / ACTOR_FPS * 1.3)
#define MOUSE_VALUE      (200)

#define TEST_SPRITESHEET   "cat.bmp"
#define TEST_SPRITE_WIDTH  (32)
#define TEST_SPRITE_HEIGHT (32)
const unsigned int TEST_SPRITESHEET_VALUES[] = {0, 1,
                                                2, 3,
                                                4, 5,
                                                6, 7,
                                                8, 9,
                                                10, 11,
                                                12, 13};
#define C_OPAQUE TILEMAP_COLOR(255, 255, 255, 255)
#define C_TRANSL TILEMAP_COLOR(255, 255, 255, ZZZ_TRANSLUCENCY)
const unsigned int TEST_SPRITESHEET_COLORMOD[] = {
    C_OPAQUE, C_TRANSL,
    C_OPAQUE, C_OPAQUE,
    C_OPAQUE, C_OPAQUE,
    C_OPAQUE, C_OPAQUE,
    C_OPAQUE, C_OPAQUE,
    C_OPAQUE, C_OPAQUE,
    C_OPAQUE, C_OPAQUE
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
#define TEST_GORE0   (12)
#define TEST_GORE1   (13)

#define ARRAY_COUNT(ARR) (sizeof(ARR) / sizeof((ARR[0])))
#define SCALE(VAL, SMIN, SMAX, DMIN, DMAX) \
    ((((VAL) - (SMIN)) / ((SMAX) - (SMIN)) * ((DMAX) - (DMIN))) + (DMIN))
#define SCALEINV(VAL, SMIN, SMAX, DMIN, DMAX) \
    ((DMAX) - (((VAL) - (SMIN)) / ((SMAX) - (SMIN)) * ((DMAX) - (DMIN))))
#define RANDRANGE(MIN, MAX) ((rand() % (MAX - MIN)) + MIN)

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
} Enemy;

typedef enum {
    SPAWN_NONE,
    SPAWN_ANTS,
    SPAWN_SPIDERS,
    SPAWN_MICE
} SpawnerType;

typedef struct {
    float catx, caty;
    unsigned int winwidth, winheight;
    Enemy enemy[MAX_ENEMIES];
} GameState;

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
    synth_free(as->s);
    free(as);
}

Synth *get_synth(AudioState *as) {
    return(as->s);
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

int create_enemy(GameState *gs,
                 SpawnerType type,
                 float x,
                 float y,
                 float angle) {
    unsigned int i;

    for(i = 0; i < MAX_ENEMIES; i++) {
        if(gs->enemy[i].sprite >= 0) {
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
            gs->enemy[i].anim = ANT_ANIM0;
            gs->enemy[i].animCounter = 0;
            gs->enemy[i].maxSpeed = ANT_VELOCITY;
            gs->enemy[i].maxAngle = ANT_TURN_SPEED;
            gs->enemy[i].x = x;
            gs->enemy[i].y = y;
            gs->enemy[i].angle = angle;
            break;
        case SPAWN_SPIDERS:
            gs->enemy[i].state = CAT_ANIM0;
            gs->enemy[i].anim = SPIDER_ANIM0;
            gs->enemy[i].animCounter = 0;
            gs->enemy[i].maxSpeed = SPIDER_VELOCITY;
            gs->enemy[i].maxAngle = SPIDER_TURN_SPEED;
            gs->enemy[i].x = x;
            gs->enemy[i].y = y;
            gs->enemy[i].angle = angle;
            break;
        case SPAWN_MICE:
            gs->enemy[i].state = CAT_ANIM0;
            gs->enemy[i].anim = MOUSE_ANIM0;
            gs->enemy[i].animCounter = 0;
            gs->enemy[i].maxSpeed = MOUSE_VELOCITY;
            gs->enemy[i].maxAngle = MOUSE_TURN_SPEED;
            gs->enemy[i].x = x;
            gs->enemy[i].y = y;
            gs->enemy[i].angle = angle;
            break;
        default:
            fprintf(stderr, "Invalid enemy spawn type.\n");
            return(-1);
    }

    gs->enemy[i].sprite = tilemap_add_layer(gs->ll, gs->tilemap);
    if(gs->enemy[i].sprite < 0) {
        fprintf(stderr, "Failed to add layer for enemy.\n");
        return(-1);
    }
    if(tilemap_set_layer_scroll_pos(gs->ll, gs->enemy[i].sprite,
                                    gs->enemy[i].anim * TEST_SPRITE_WIDTH,
                                    0) < 0) {
        fprintf(stderr, "Failed to set layer scroll for enemy.\n");
        return(-1);
    }
    if(tilemap_set_layer_window(gs->ll, gs->enemy[i].sprite,
                                TEST_SPRITE_WIDTH,
                                TEST_SPRITE_HEIGHT) < 0) {
        fprintf(stderr, "Failed to set enemy window size.\n");
        return(-1);
    }
    if(tilemap_set_layer_rotation_center(gs->ll, gs->enemy[i].sprite,
                                         TEST_SPRITE_WIDTH / 2 * SPRITE_SCALE,
                                         TEST_SPRITE_HEIGHT / 2 * SPRITE_SCALE) < 0) {
        fprintf(stderr, "Failed to set enemy rotation center.\n");
        return(-1);
    }
    if(tilemap_set_layer_scale(gs->ll, gs->enemy[i].sprite,
                               SPRITE_SCALE, SPRITE_SCALE) < 0) {
        fprintf(stderr, "Failed to set enemy sprite scame.\n");
        return(-1);
    }

    return(0);
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
                     float *catIdleTime,
                     float *thisAngle, float maxAngle) {
    float motionx, motiony;
    float velocity;
    float angle, angleDiff;

    motionx = targetx - *thisx - (TEST_SPRITE_WIDTH / 2 * SPRITE_SCALE);
    motiony = targety - *thisy - (TEST_SPRITE_HEIGHT / 2 * SPRITE_SCALE);
    velocity = velocity_from_xy(motionx, motiony);
    if(velocity >= 1.0) {
        if(catIdleTime != NULL) {
            *catIdleTime = 0;
        }

        angle = angle_from_xy(motionx, motiony);
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
        /* if not updating the cat, then updating an enemy, so actually move
         * _away_ from the target */
        if(catIdleTime == NULL) {
            *thisAngle += M_PI;
        }
        if(*thisAngle < 0.0) {
            *thisAngle += M_PI * 2;
        } else if(*thisAngle >= M_PI * 2) {
            *thisAngle -= M_PI * 2;
        }
       
        velocity = find_object_velocity(velocity, thisAngle,
                                        thisx, thisy,
                                        maxx, maxy,
                                        maxVelocity);
        xy_from_angle(&motionx, &motiony, thisAngle);
        *thisx += motionx * velocity;
        *thisy += motiony * velocity;
    } else {
        if(catIdleTime != NULL) {
            *catIdleTime += ACTOR_RATE;
        }
    }
}

void process_enemies(GameState *gs) {
    unsigned int i;

    for(i = 0; i < MAX_ENEMIES; i++) {
        if(gs->enemy[i].sprite < 0) {
            continue;
        }

        update_movement(&(gs->enemy[i].x), &(gs->enemy[i].y),
                        gs->catx, gs.caty,
                        gs->enemy[i].maxSpeed,
                        gs->winwidth, gs->winheight,
                        NULL,
                        &(gs->enemy[i].angle), gs->enemy[i].maxAngle);
        /* invalidate any enemies which have gone of screen */
        if(gs->enemy[i].x < -(TEST_SPRITE_WIDTH * SPRITE_SCALE) ||
           gs->enemy[i].x > gs->winwidth + (TEST_SPRITE_WIDTH * SPRITE_SCALE) ||
           gs->enemy[i].y < -(TEST_SPRITE_HEIGHT * SPRITE_SCALE) ||
           gs->enemy[i].y > gs->winheight + (TEST_SPRITE_HEIGHT * SPRITE_SCALE)) {
            gs->enemy[i].sprite = -1;
            continue;
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

            if(tilemap_set_layer_scroll_pos(gs->ll, gs->enemy[i].sprite,
                                            gs->enemy[i].anim * TEST_SPRITE_WIDTH,
                                            0) < 0) {
                return(-1);
            }
            gs->enemy[i].animCounter = 0;
        }

        if(tilemap_set_layer_pos(gs->ll, gs->enemy[i].sprite,
                                 gs->catx, gs->caty) < 0) {
            return(-1);
        }
        if(tilemap_set_layer_rotation(gs->ll, gs->enemy[i].sprite,
                                      radian_to_degree(gs->enemy[i].angle)) < 0) {
            return(-1);
        }
    }
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

int main(int argc, char **argv) {
    Uint32 format;
    SDL_Window *win;
    SDL_Renderer *renderer;
    SDL_Event lastEvent;
    Synth *s;
    AudioState *audioState;
    GameState gs;
    int running;
    int mouseCaptured = 0;
    unsigned int mouseReleaseCombo = 0;
    int tileset;
    int catlayer;
    int mousex = (WINDOW_WIDTH - TEST_SPRITE_WIDTH) / 2;
    int mousey = (WINDOW_HEIGHT - TEST_SPRITE_HEIGHT) / 2;
    Uint32 nextMotion = SDL_GetTicks() + ACTOR_RATE;
    CatState catState = CAT_ANIM0;
    int animCounter = 0;
    int catAnim = TEST_ANIM0;
    double catAngle = 0.0;
    int zzzlayer = -1;
    double zzzcycle = 0.0;
    int fullscreen = 0;
    int meow1_buf, meow2_buf, cat_activation_buf, purr_buf;
    int meow1, meow2, cat_activation, purr;
    unsigned int catIdleTime = 0;
    int catSound = 0;
    float catPan = 0.0;
    SpawnerType spawner;
    unsigned int spawnerTimer = RANDRANGE(MIN_SPAWNER_TIME, MAX_SPAWNER_TIME);
    int spawnerx, spawnery;
    int spawnCount;

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
    gs.ll = layerlist_new(renderer,
                       format,
                       vprintf_cb,
                       stderr);
    if(gs.ll == NULL) {
        fprintf(stderr, "Failed to create layerlist.\n");
        goto error_video;
    }

    /* initialize the audio */
    audioState = init_audio_state();
    if(audioState == NULL) {
        goto error_ll;
    }
    s = get_synth(audioState);

    /* seed random */
    srand(time(NULL));

    /* init stuff */

    /* load the spritesheet */
    tileset = tilemap_tileset_from_bmp(gs.ll,
                                       TEST_SPRITESHEET,
                                       TEST_SPRITE_WIDTH,
                                       TEST_SPRITE_HEIGHT);
    if(tileset < 0) {
        fprintf(stderr, "Failed to load spritesheet.\n");
        goto error_synth;
    }
    /* create the tilemap */
    gs.tilemap = tilemap_add_tilemap(gs.ll, ARRAY_COUNT(TEST_SPRITESHEET_VALUES), 1);
    if(gs.tilemap < 0) {
        fprintf(stderr, "Failed to make tilemap.\n");
        goto error_synth;
    }
    /* assign the spritesheet to the sprite */
    if(tilemap_set_tilemap_tileset(gs.ll, gs.tilemap, tileset) < 0) {
        fprintf(stderr, "Failed to apply tileset to tilemap.\n");
        goto error_synth;
    }
    /* set up its map for the first time (not likely necessary in this case
     * since it's probably already 0, but for demonstration purposes) */
    if(tilemap_set_tilemap_map(gs.ll, gs.tilemap, 
                               0, 0, /* start x and y for destination rectangle */
                               ARRAY_COUNT(TEST_SPRITESHEET_VALUES), /* row width for source rectangle */
                               ARRAY_COUNT(TEST_SPRITESHEET_VALUES), 1, /* size of rectangle */
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
    if(tilemap_set_tilemap_attr_colormod(gs.ll, gs.tilemap,
                                         0, 0,
                                         ARRAY_COUNT(TEST_SPRITESHEET_VALUES),
                                         ARRAY_COUNT(TEST_SPRITESHEET_VALUES), 1,
                                         TEST_SPRITESHEET_COLORMOD,
                                         ARRAY_COUNT(TEST_SPRITESHEET_COLORMOD)
                                        ) < 0) {
        fprintf(stderr, "Failed to set tilemap colormod.\n");
        goto error_synth;
    }
    /* update/"render out" the tilemap for the first time */
    if(tilemap_update_tilemap(gs.ll, gs.tilemap,
                              0, 0, /* start rectangle to update */
                              ARRAY_COUNT(TEST_SPRITESHEET_VALUES), 1) /* update rectangle size */ < 0) {
        fprintf(stderr, "Failed to update tilemap.\n");
        goto error_synth;
    }
    /* add the tilemap to a layer */
    catlayer = tilemap_add_layer(gs.ll, gs.tilemap);
    if(catlayer < 0) {
        fprintf(stderr, "Failed to create cat layer.\n");
        goto error_synth;
    }
    /* make the tilemap window the size of a single sprite */
    if(tilemap_set_layer_window(gs.ll, catlayer,
                                TEST_SPRITE_WIDTH,
                                TEST_SPRITE_HEIGHT) < 0) {
        fprintf(stderr, "Failed to set layer window.\n");
        goto error_synth;
    }
    /* make the rotation center in the center of the sprite so it rotates
     * about where it aims for the cursor */
    if(tilemap_set_layer_rotation_center(gs.ll, catlayer,
                                         TEST_SPRITE_WIDTH / 2 * SPRITE_SCALE,
                                         TEST_SPRITE_HEIGHT / 2 * SPRITE_SCALE) < 0) {
        fprintf(stderr, "Failed to set layer rotation center.\n");
        goto error_synth;
    }
    /* Makes the sprite more visible without me having to draw a larger sprite */
    if(tilemap_set_layer_scale(gs.ll, catlayer, SPRITE_SCALE, SPRITE_SCALE) < 0) {
        fprintf(stderr, "Failed to set layer scale.\n");
        goto error_synth;
    }

    /* load the sound effects and create players for them, as they may
     * eventually each have different parameters for volume balance or
     * whatever else */
    meow1_buf = synth_buffer_from_wav(s, "meow1.wav");
    if(meow1_buf < 0) {
        fprintf(stderr, "Failed to load meow1.wav.\n");
        goto error_synth;
    }
    meow1 = synth_add_player(s, meow1_buf);
    if(meow1 < 0) {
        fprintf(stderr, "Failed to create meow1 player.\n");
        goto error_synth;
    }
    if(synth_set_player_speed(s, meow1, 8000.0 / (float)synth_get_rate(s)) < 0) {
        fprintf(stderr, "Failed to set meow1 speed.\n");
        goto error_synth;
    }
    meow2_buf = synth_buffer_from_wav(s, "meow2.wav");
    if(meow2_buf < 0) {
        fprintf(stderr, "Failed to load meow2.wav.\n");
        goto error_synth;
    }
    meow2 = synth_add_player(s, meow2_buf);
    if(meow2 < 0) {
        fprintf(stderr, "Failed to create meow2 player.\n");
        goto error_synth;
    }
    if(synth_set_player_speed(s, meow2, 8000.0 / (float)synth_get_rate(s)) < 0) {
        fprintf(stderr, "Failed to set meow2 speed.\n");
        goto error_synth;
    }
    if(synth_set_player_volume(s, meow2, volume_from_db(-3)) < 0) {
        fprintf(stderr, "Failed to set meow2 volume.\n");
        goto error_synth;
    }
    cat_activation_buf = synth_buffer_from_wav(s, "cat_activation.wav");
    if(cat_activation_buf < 0) {
        fprintf(stderr, "Failed to load cat_activation.wav.\n");
        goto error_synth;
    }
    cat_activation = synth_add_player(s, cat_activation_buf);
    if(cat_activation < 0) {
        fprintf(stderr, "Failed to create cat_activation player.\n");
        goto error_synth;
    }
    if(synth_set_player_speed(s, cat_activation, 8000.0 / (float)synth_get_rate(s)) < 0) {
        fprintf(stderr, "Failed to set cat_activation speed.\n");
        goto error_synth;
    }
    if(synth_set_player_volume(s, cat_activation, volume_from_db(-12)) < 0) {
        fprintf(stderr, "failed to set cat_activation volume.\n");
        goto error_synth;
    }
    purr_buf = synth_buffer_from_wav(s, "purr.wav");
    if(purr_buf < 0) {
        fprintf(stderr, "Failed to load purr.wav.\n");
        goto error_synth;
    }
    purr = synth_add_player(s, purr_buf);
    if(purr < 0) {
        fprintf(stderr, "Failed to create purr player.\n");
        goto error_synth;
    }
    if(synth_set_player_speed(s, purr, 8000.0 / (float)synth_get_rate(s)) < 0) {
        fprintf(stderr, "Failed to set purr speed.\n");
        goto error_synth;
    }
    if(synth_set_player_volume(s, purr, volume_from_db(-2)) < 0) {
        fprintf(stderr, "failed to set purr volume.\n");
        goto error_synth;
    }
    if(synth_set_player_mode(s, purr, SYNTH_MODE_LOOP) < 0) {
        fprintf(stderr, "Failed to set purr to looping.\n");
        goto error_synth;
    }

    if(synth_set_enabled(s, 1) < 0) {
        fprintf(stderr, "Failed to enable synth.\n");
        goto error_synth;
    }

    gs.catx = mousex;
    gs.caty = mousey;
    gs.winwidth = WINDOW_WIDTH;
    gs.winheight = WINDOW_HEIGHT;
    for(i = 0; i < MAX_ENEMIES; i++) {
        gs.enemy[sprite] = -1;
    }

    spawneType = SPAWN_NONE;

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
                    } else if(key->keysym.sym == SDLK_1) {
                        stop_sound(audioState, catSound);
                        catSound = play_sound(audioState, meow1, 1.0, catPan);
                    } else if(key->keysym.sym == SDLK_2) {
                        stop_sound(audioState, catSound);
                        catSound = play_sound(audioState, meow2, 1.0, catPan);
                    } else if(key->keysym.sym == SDLK_3) {
                        stop_sound(audioState, catSound);
                        catSound = play_sound(audioState, cat_activation, 1.0, catPan);
                    } else if(key->keysym.sym == SDLK_4) {
                        stop_sound(audioState, catSound);
                        catSound = play_sound(audioState, purr, 1.0, catPan);
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
                            if(tilemap_free_layer(gs.ll, zzzlayer) < 0) {
                                fprintf(stderr, "Failed to free ZZZ layer.\n");
                                goto error_synth;
                            }

                            stop_sound(audioState, catSound);
                            catSound = play_sound(audioState, cat_activation, 1.0, catPan);
                        } else {
                            catState = CAT_RESTING;
                            if(tilemap_set_layer_scroll_pos(gs.ll, catlayer,
                                                            TEST_RESTING * TEST_SPRITE_WIDTH,
                                                            0) < 0) {
                                fprintf(stderr, "Failed to set layer scroll pos.\n");
                                goto error_synth;
                            }

                            zzzlayer = tilemap_add_layer(gs.ll, gs.tilemap);
                            if(zzzlayer < 0) {
                                fprintf(stderr, "Failed to create ZZZ layer.\n");
                                goto error_synth;
                            }
                            if(tilemap_set_layer_window(gs.ll, zzzlayer,
                                                        TEST_SPRITE_WIDTH,
                                                        TEST_SPRITE_HEIGHT) < 0) {
                                fprintf(stderr, "Failed to set layer window.\n");
                                goto error_synth;
                            }
                            if(tilemap_set_layer_scale(gs.ll, zzzlayer,
                                                       SPRITE_SCALE,
                                                       SPRITE_SCALE) < 0) {
                                fprintf(stderr, "Failed to set layer scale.\n");
                                goto error_synth;
                            }
                            if(tilemap_set_layer_scroll_pos(gs.ll, zzzlayer,
                                                            TEST_ZZZ * TEST_SPRITE_WIDTH,
                                                            0) < 0) {
                                fprintf(stderr, "Failed to set layer scroll pos.\n");
                                goto error_synth;
                            }
                            
                            stop_sound(audioState, catSound);
                            catSound = play_sound(audioState, purr, 1.0, catPan);
                        }
                    } else if(click->button == 3) {
                        gs.catx = mousex;
                        gs.caty = mousey;
                        catPan = (float)(gs.catx - (gs.winwidth / 2)) /
                                 ((float)gs.winwidth / 2) * CAT_PAN_FACTOR;
                    }
                    break;
                case SDL_MOUSEBUTTONUP:
                    break;
                case SDL_WINDOWEVENT:
                    winEv = (SDL_WindowEvent *)&lastEvent;
                    if(winEv->event == SDL_WINDOWEVENT_SIZE_CHANGED) {
                        gs.winwidth = winEv->data1;
                        gs.winheight = winEv->data2;
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

        /* frame stuff, try to keep thisTick ahead of nextMotion, but if
         * things are just running really badly for some reason, just give up
         * if things get too far behind and maybe it'll eventually be able to
         * catch up.  It'll slow down but still be able to display something
         * and poll for events */
        Uint32 thisTick = SDL_GetTicks();
        processTime = thisTick;
        while(thisTick >= nextMotion &&
              thisTick - processTime < MAX_PROCESS_TIME) {
            nextMotion += ACTOR_RATE;

            if(catState != CAT_RESTING) {
                float lastCatIdleTime = catIdleTime;
                update_movement(&(gs.catx), &(gs.caty),
                                mousex, mousey,
                                CAT_VELOCITY,
                                gs.winwidth, gs.winheight,
                                &catIdleTime,
                                &catAngle, CAT_TURN_SPEED);
                if(lastCatIdleTime - catIdleTime >= CAT_IDLE_MEOW) {
                    if(rand() % 2 == 1) {
                        stop_sound(audioState, catSound);
                        catSound = play_sound(audioState, meow1, 1.0, catPan);
                    } else {
                        stop_sound(audioState, catSound);
                        catSound = play_sound(audioState, meow2, 1.0, catPan);
                    }
                }
                if(tilemap_set_layer_pos(gs.ll, catlayer,
                                         gs.catx, gs.caty) < 0) {
                    fprintf(stderr, "Failed to set cat position.\n");
                    goto error_synth;
                }
                if(tilemap_set_layer_rotation(gs.ll, catlayer,
                                              radian_to_degree(catAngle)) < 0) {
                    fprintf(stderr, "Failed to set layer rotation.\n");
                    return(-1);
                }

                update_panning(audioState, catSound, catPan);

                animCounter++;
                if(animCounter >= CAT_ANIM_DIV) {
                    if(catState == CAT_ANIM0) {
                        catState = CAT_ANIM1;
                        catAnim++;
                    } else {
                        catState = CAT_ANIM0;
                        catAnim--;
                    }

                    if(tilemap_set_layer_scroll_pos(gs.ll, catlayer,
                                                    catAnim * TEST_SPRITE_WIDTH,
                                                    0) < 0) {
                        fprintf(stderr, "Failed to set layer scroll pos.\n");
                        goto error_synth;
                    }

                    animCounter = 0;
                }
            } else { /* CAT_RESTING */
                zzzcycle += ZZZ_CYCLE_SPEED;
                if(zzzcycle >= M_PI * 2) {
                    zzzcycle -= M_PI * 2;
                }

                if(tilemap_set_layer_pos(gs.ll, zzzlayer,
                                         gs.catx + (TEST_SPRITE_WIDTH * SPRITE_SCALE * ZZZ_POS_X),
                                         gs.caty - (TEST_SPRITE_HEIGHT * SPRITE_SCALE * ZZZ_POS_Y) + 
                                         (sin(zzzcycle) * ZZZ_AMP)) < 0) {
                    fprintf(stderr, "Failed to set ZZZ position.\n");
                    goto error_synth;
                }
                if(tilemap_set_layer_colormod(gs.ll, zzzlayer,
                                              color_from_angle(zzzcycle,
                                                               ZZZ_COLOR_BIAS)) < 0) {
                    fprintf(stderr, "Failed to set ZZZ colormod.\n");
                    goto error_synth;
                }
            }

            process_enemies(&gs);

            switch(spawner) {
                case SPAWN_ANTS:
                    spawnerTimer -= ACTOR_RATE;
                    while(spawnerTimer < 0) {
                        if(spawnerCount == 0) {
                            spawnerTimer += RANDRANGE(MIN_SPAWNER_TIME, MAX_SPAWNER_TIME);
                            spawner = SPAWN_NONE;
                            break;
                        }

                        spawnerTimer += RANDRANGE(ANT_SPAWN_TIME_MIN, ANT_SPAWN_TIME_MAX);
                        if(create_enemy(&gs, SPAWN_ANTS,
                                        RANDRANGE(0, gs.winwidth),
                                        RANDRANGE(0, gs.winheight),
                                        SCALE((double)rand(),
                                              0.0, RAND_MAX,
                                              0.0, M_PI * 2.0)) < 0) {
                            goto error_synth;
                        }
                        spawnerCount--;
                    }
                    break;
                case SPAWN_SPIDERS:
                    spawnerTimer -= ACTOR_RATE;
                    while(spawnerTimer < 0) {
                        if(spawnerCount == 0) {
                            spawnerTimer += RANDRANGE(MIN_SPAWNER_TIME, MAX_SPAWNER_TIME);
                            spawner = SPAWN_NONE;
                            break;
                        }

                        spawnerTimer += RANDRANGE(SPIDER_SPAWN_TIME_MIN, SPIDER_SPAWN_TIME_MAX);
                        if(create_enemy(&gs, SPAWN_SPIDERS,
                                        RANDRANGE(0, gs.winwidth),
                                        RANDRANGE(0, gs.winheight),
                                        SCALE((double)rand(),
                                              0.0, RAND_MAX,
                                              0.0, M_PI * 2.0)) < 0) {
                            goto error_synth;
                        }
                        spawnerCount--;
                    }
                    break;
                case SPAWN_MICE:
                    spawnerTimer -= ACTOR_RATE;
                    while(spawnerTimer < 0) {
                        if(spawnerCount == 0) {
                            spawnerTimer += RANDRANGE(MIN_SPAWNER_TIME, MAX_SPAWNER_TIME);
                            spawner = SPAWN_NONE;
                            break;
                        }

                        spawnerTimer += RANDRANGE(MOUSE_SPAWN_TIME_MIN, MOUSE_SPAWN_TIME_MAX);
                        if(create_enemy(&gs, SPAWN_MICE,
                                        RANDRANGE(0, gs.winwidth),
                                        RANDRANGE(0, gs.winheight),
                                        SCALE((double)rand(),
                                              0.0, RAND_MAX,
                                              0.0, M_PI * 2.0)) < 0) {
                            goto error_synth;
                        }
                        spawnerCount--;
                    }
                    break;
                default:
                    spawnerTimer -= ACTOR_RATE;
                    if(spawnerTimer < 0) {
                        gs.spawnerx = rand() % gs.winwidth;
                        gs.spawnery = rand() % gs.winheight;
                        switch(rand() % 3) {
                            case 0:
                                spawner = SPAWN_ANTS;
                                spawnerCount = RAND_RANGE(ANT_SPAWN_MIN, ANT_SPAWN_MAX);
                                spawnerTimer += RANDRANGE(ANT_SPAWN_TIME_MIN, ANT_SPAWN_TIME_MAX);
                                break;
                            case 1:
                                spawner = SPAWN_SPIDERS;
                                spawnerCount = RAND_RANGE(SPIDER_SPAWN_MIN, SPIDER_SPAWN_MAX);
                                spawnerTimer += RANDRANGE(SPIDER_SPAWN_TIME_MIN, SPIDER_SPAWN_TIME_MAX);
                                break;
                            default:
                                spawner = SPAWN_MICE;
                                spawnerCount = RAND_RANGE(MOUSE_SPAWN_MIN, MOUSE_SPAWN_MAX);
                                spawnerTimer += RANDRANGE(MOUSE_SPAWN_TIME_MIN, MOUSE_SPAWN_TIME_MAX);
                        }
                    }
            }

            thisTick = SDL_GetTicks();
        }

        draw_enemies(&gs);
        if(tilemap_draw_layer(gs.ll, catlayer) < 0) {
            fprintf(stderr, "Failed to draw cat layer.\n");
            goto error_synth;
        }
        if(catState == CAT_RESTING) {
            if(tilemap_draw_layer(gs.ll, zzzlayer) < 0) {
                fprintf(stderr, "Failed to draw ZZZ layer.\n");
                goto error_synth;
            }
        }

        SDL_RenderPresent(renderer);
    }

    free_audio_state(audioState);

    /* test cleanup functions */
    tilemap_free_layer(gs.ll, catlayer);
    tilemap_free_tilemap(gs.ll, gs.tilemap);
    tilemap_free_tileset(gs.ll, tileset);
    layerlist_free(gs.ll);

    SDL_DestroyWindow(win);
    SDL_Quit();

    exit(EXIT_SUCCESS);

error_synth:
    free_audio_state(audioState);
error_ll:
    layerlist_free(gs.ll);
error_video:
    SDL_DestroyWindow(win);
error_sdl:
    SDL_Quit();
}
