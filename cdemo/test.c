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
#include <string.h>
#include <limits.h>
#include <SDL.h>

#include "tilemap.h"
#include "synth.h"

#include "log_cb.h"
#include "text.h"
#include "extramath.h"
#include "testaudio.h"
#include "testgfx.h"

/* initial settings */
#define MAX_PROCESS_TIME (200)
#define WINDOW_TITLE    "UnCrustyGame Test"
#define WINDOW_WIDTH    (1024)
#define WINDOW_HEIGHT   (768)
#define WINDOW_FLAGS    (SDL_WINDOW_RESIZABLE)
#define RENDERER_FLAGS  (SDL_RENDERER_PRESENTVSYNC)
//#define RENDERER_FLAGS  (0)
#define SHOW_FPS
#define DEFAULT_RATE    (48000)
#define BG_R (47)
#define BG_G (17)
#define BG_B (49)
#define ACTOR_FPS      (60)
#define ACTOR_RATE     (MILLISECOND / ACTOR_FPS)
#define CAT_VELOCITY   (300.0)
#define CAT_TURN_SPEED (M_PI * 2.0 / ACTOR_FPS)
#define CAT_ANIM_DIV   (75)
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
#define SPAWNER_DEADZONE (0.1)
#define ANT_SPAWN_MIN    (20)
#define ANT_SPAWN_MAX    (100)
#define ANT_SPAWN_TIME_MIN (10)
#define ANT_SPAWN_TIME_MAX (30)
#define ANT_VELOCITY     (60.0)
#define ANT_TURN_SPEED   (M_PI * 2.0 / ACTOR_FPS * 2.0)
#define ANT_VALUE        (10)
#define ANT_EAT_TIME     (100)
#define SPIDER_SPAWN_MIN (10)
#define SPIDER_SPAWN_MAX (50)
#define SPIDER_SPAWN_TIME_MIN (20)
#define SPIDER_SPAWN_TIME_MAX (50)
#define SPIDER_VELOCITY  (120.0)
#define SPIDER_TURN_SPEED (M_PI * 2.0 / ACTOR_FPS * 1.8)
#define SPIDER_VALUE     (50)
#define SPIDER_EAT_TIME  (500)
#define MOUSE_SPAWN_MIN  (2)
#define MOUSE_SPAWN_MAX  (10)
#define MOUSE_SPAWN_TIME_MIN (100)
#define MOUSE_SPAWN_TIME_MAX (500)
#define MOUSE_VELOCITY   (240.0)
#define MOUSE_TURN_SPEED (M_PI * 2.0 / ACTOR_FPS * 1.3)
#define MOUSE_VALUE      (200)
#define MOUSE_EAT_TIME   (1000)

#define MAX_COLOR_BOX    (8)

#define TEST_SPRITESHEET   "cat.bmp"
#define TEST_SPRITE_DIM    (32)
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
#define C_ANTBLOOD TILEMAP_COLOR(37, 70, 0, 192)
#define C_SPIDERBLOOD TILEMAP_COLOR(0, 34, 72, 192)
#define C_HUD_SHADOW TILEMAP_COLOR(255, 255, 255, HUD_SHADOW_TRANSLUCENCY)
#define C_BGTILES TILEMAP_COLOR(255, 192, 128, 48)
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
/* sprite tilemap indices */
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

/* tileset indices */
#define TEST_MARBLE0 (14)
#define TEST_MARBLE1 (15)
#define TEST_MARBLE2 (16)
#define TEST_MARBLE3 (17)


#define FONT_WIDTH  (8)
#define FONT_HEIGHT (8)
#define HUD_SCALE   (2)
#define HUD_WIDTH   (WINDOW_WIDTH / (FONT_WIDTH * HUD_SCALE))
#define HUD_HEIGHT  (WINDOW_HEIGHT / (FONT_HEIGHT * HUD_SCALE))
#define SPRITE_SCALE    (2)
#define SCALED_SPRITE_DIM (TEST_SPRITE_DIM * SPRITE_SCALE)
#define WINDOW_TILE_WIDTH (WINDOW_WIDTH / SCALED_SPRITE_DIM)
#define WINDOW_TILE_HEIGHT (WINDOW_HEIGHT / SCALED_SPRITE_DIM)

#define CAT_DISTANCE     (SCALED_SPRITE_DIM / 2)

#define ARRAY_COUNT(ARR) (sizeof(ARR) / sizeof((ARR[0])))

#define CATPAN(XPOS) ((float)((XPOS) - (WINDOW_WIDTH / 2.0)) / \
                      ((float)WINDOW_WIDTH / 2.0) * CAT_PAN_FACTOR)
#define SPAWNERMIN(LENGTH) ((float)LENGTH * SPAWNER_DEADZONE)
#define SPAWNERMAX(LENGTH) ((float)LENGTH * (1.0 - SPAWNER_DEADZONE))
#define SPAWNERRAND(LENGTH) RANDRANGE((int)SPAWNERMIN(LENGTH), (int)SPAWNERMAX(LENGTH))

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
    /* resources */
    LayerList *ll;
    AudioState *as;
    int tileset;
    int tilemap;
    int catlayer;
    int zzzlayer;
    SDL_Texture *goreTex;
    int goreSprite;
    int hudTilemap;
    int hud;
    int titleLayer;
    int lBackground;

    /* system state */
    GameMode *nextMode;
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

const unsigned int BG_PATTERN[] = {TEST_MARBLE0, TEST_MARBLE1,
                                   TEST_MARBLE2, TEST_MARBLE3};
#define BG_PATTERN_WIDTH  (2)
#define BG_PATTERN_HEIGHT (2)

const char TEXT_SCORE[] = "Score: ";
#define TEXT_SCORE_X (0)
#define TEXT_SCORE_Y (0)

const char TEXT_START[] = "Press [ENTER] to start";
#define TEXT_START_X CENTER(HUD_WIDTH, sizeof(TEXT_START) - 1)
#define TEXT_START_Y (HUD_HEIGHT - 6)

const char TEXT_FPS[] = "FPS: ";
#define TEXT_FPS_X (0)
#define TEXT_FPS_Y (HUD_HEIGHT - 1)

GameState gs;
GameMode* generic_control(void *priv);
int title_input(void *priv, SDL_Event *event);
int title_draw(void *priv);
int game_input(void *priv, SDL_Event *event);
GameMode* game_control(void *priv);
int game_draw(void *priv);

GameMode title = {
    .input = title_input,
    .control = generic_control,
    .draw = title_draw,
    .priv = &gs
};
GameMode game = {
    .input = game_input,
    .control = game_control,
    .draw = game_draw,
    .priv = &gs
};

int initialize_video(SDL_Window **win,
                     SDL_Renderer **renderer,
                     Uint32 *format,
                     Uint32 initialWidth,
                     Uint32 initialHeight,
                     const char *initialTitle,
                     Uint32 winFlags,
                     Uint32 rendererFlags) {
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
    *win = SDL_CreateWindow(initialTitle,
                            SDL_WINDOWPOS_UNDEFINED,
                            SDL_WINDOWPOS_UNDEFINED,
                            initialWidth,
                            initialHeight,
                            winFlags);
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

    *renderer = SDL_CreateRenderer(*win, selectdrv, rendererFlags);
    if(*renderer == NULL) {
        fprintf(stderr, "Failed to create SDL renderer.\n");
        goto error;
    }

    /* Draw operations with alpha need this set */
    if(SDL_SetRenderDrawBlendMode(*renderer, SDL_BLENDMODE_BLEND) < 0) {
        fprintf(stderr, "Failed to set render draw mode to blend.\n");
        SDL_DestroyRenderer(*renderer);
        goto error;
    }

    return(0);

error:
    SDL_DestroyWindow(*win);

    return(-1);
}

void play_cat_sound(GameState *gs, int player) {
    stop_sound(gs->as, gs->catSound);
    gs->catSound = play_sound(gs->as, player, 1.0, CATPAN(gs->catx));
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

    gs->enemy[i].sprite = create_sprite(gs->ll, gs->tilemap,
                                        TEST_SPRITE_DIM, SPRITE_SCALE,
                                        "enemy");
    if(gs->enemy[i].sprite < 0) {
        return(-1);
    }

    return(select_sprite(gs->ll, gs->enemy[i].sprite,
                         gs->enemy[i].anim, TEST_SPRITE_DIM));
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
                                        maxVelocity, ACTOR_RATE);
        xy_from_angle(&motionx, &motiony, *thisAngle);
        *thisx += motionx * velocity;
        *thisy += motiony * velocity;
    } else {
        if(catIdleTime != NULL) {
            *catIdleTime += ACTOR_RATE;
        }
    }
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
            if(tilemap_free_layer(gs->ll, gs->enemy[i].sprite) < 0) {
                fprintf(stderr, "Failed to free sprite.\n");
                return(-1);
            }
            gs->enemy[i].sprite = -1;
            gs->eating = gs->enemy[i].eatTime;
            gs->score += gs->enemy[i].value;
            if(gs->score < 0) {
                gs->score = 0;
            }
            if(printf_to_tilemap(gs->ll, gs->hudTilemap,
                                    TEXT_SCORE_X + (sizeof(TEXT_SCORE) - 1), TEXT_SCORE_Y,
                                    "%d", gs->score) < 0) {
                fprintf(stderr, "Failed to print score.\n");
                return(-1);
            }

            /* render to gore texture */
            tilemap_set_default_render_target(gs->ll, gs->goreTex);
            if(tilemap_set_target_tileset(gs->ll, -1) < 0) {
                fprintf(stderr, "Failed to set target tileset.\n");
                return(-1);
            }

            if(position_sprite(gs->ll, gs->goreSprite,
                               gs->enemy[i].x, gs->enemy[i].y,
                               SCALED_SPRITE_DIM) < 0) {
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
                if(select_sprite(gs->ll, gs->goreSprite,
                                 gs->enemy[i].deadSprite,
                                 TEST_SPRITE_DIM) < 0) {
                    return(-1);
                }
                if(tilemap_draw_layer(gs->ll, gs->goreSprite) < 0) {
                    fprintf(stderr, "Failed to draw gore sprite.\n");
                    return(-1);
                }
            }
            if(gore & 2) {
                if(select_sprite(gs->ll, gs->goreSprite,
                                 TEST_BONES, TEST_SPRITE_DIM) < 0) {
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
            if(gs->enemy[i].x < -(SCALED_SPRITE_DIM / 2.0) ||
               gs->enemy[i].x > WINDOW_WIDTH + (SCALED_SPRITE_DIM / 2.0) ||
               gs->enemy[i].y < -(SCALED_SPRITE_DIM / 2.0) ||
               gs->enemy[i].y > WINDOW_HEIGHT + (SCALED_SPRITE_DIM / 2.0)) {
                if(tilemap_free_layer(gs->ll, gs->enemy[i].sprite) < 0) {
                    fprintf(stderr, "Failed to free sprite.\n");
                    return(-1);
                }
                gs->enemy[i].sprite = -1;
                continue;
            }
        }

        gs->enemy[i].animCounter += ACTOR_RATE;
        if(gs->enemy[i].animCounter >= CAT_ANIM_DIV) {
            if(gs->enemy[i].state == CAT_ANIM0) {
                gs->enemy[i].state = CAT_ANIM1;
                gs->enemy[i].anim++;
            } else {
                gs->enemy[i].state = CAT_ANIM0;
                gs->enemy[i].anim--;
            }

            if(select_sprite(gs->ll, gs->enemy[i].sprite,
                             gs->enemy[i].anim, TEST_SPRITE_DIM) < 0) {
                return(-1);
            }
            gs->enemy[i].animCounter -= CAT_ANIM_DIV;
        }

        if(position_sprite(gs->ll, gs->enemy[i].sprite,
                           gs->enemy[i].x, gs->enemy[i].y,
                           SCALED_SPRITE_DIM) < 0) {
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

void init_sprite_list(GameState *gs) {
    unsigned int i;

    for(i = 0; i < MAX_ENEMIES; i++) {
        gs->enemy[i].sprite = -1;
    }
}

void free_sprites(GameState *gs) {
    unsigned int i;

    for(i = 0; i < MAX_ENEMIES; i++) {
        if(gs->enemy[i].sprite >= 0) {
            if(tilemap_free_layer(gs->ll, gs->enemy[i].sprite) < 0) {
                fprintf(stderr, "Failed to free sprite.\n");
            }
            gs->enemy[i].sprite = -1;
        }
    }
}

void reset_state(GameState *gs) {
    stop_sound(gs->as, gs->catSound);
    free_sprites(gs);

    gs->catx = (WINDOW_WIDTH - SCALED_SPRITE_DIM) / 2;
    gs->caty = (WINDOW_HEIGHT - SCALED_SPRITE_DIM) / 2;
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
    gs->spawnerx = SPAWNERRAND(WINDOW_WIDTH);
    gs->spawnery = SPAWNERRAND(WINDOW_HEIGHT);
    gs->spawnerCount = 0;
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
        if(position_sprite(gs->ll, gs->catlayer,
                           gs->catx, gs->caty,
                           SCALED_SPRITE_DIM) < 0) {
            return(-1);
        }
        if(tilemap_set_layer_rotation(gs->ll, gs->catlayer,
                                      radian_to_degree(gs->catAngle)) < 0) {
            fprintf(stderr, "Failed to set layer rotation.\n");
            return(-1);
        }

        update_panning(gs->as, gs->catSound, CATPAN(gs->catx));

        gs->animCounter += ACTOR_RATE;
        if(gs->animCounter >= CAT_ANIM_DIV) {
            if(gs->catState == CAT_ANIM0) {
                gs->catState = CAT_ANIM1;
                gs->catAnim++;
            } else {
                gs->catState = CAT_ANIM0;
                gs->catAnim--;
            }

            if(select_sprite(gs->ll, gs->catlayer,
                             gs->catAnim, TEST_SPRITE_DIM) < 0) {
                return(-1);
            }

            gs->animCounter -= CAT_ANIM_DIV;
        }
    } else { /* CAT_RESTING */
        gs->zzzcycle += ZZZ_CYCLE_SPEED;
        if(gs->zzzcycle >= M_PI * 2) {
            gs->zzzcycle -= M_PI * 2;
        }

        if(position_sprite(gs->ll, gs->zzzlayer,
                           gs->catx + SCALED_SPRITE_DIM * ZZZ_POS_X,
                           gs->caty + SCALED_SPRITE_DIM * ZZZ_POS_Y + 
                           ((sin(gs->zzzcycle) - 1.0) * ZZZ_AMP * SPRITE_SCALE),
                           SCALED_SPRITE_DIM) < 0) {
            return(-1);
        }
        if(tilemap_set_layer_colormod(gs->ll, gs->zzzlayer,
                                      color_from_angle(gs->zzzcycle,
                                                       ZZZ_COLOR_BIAS,
                                                       255)) < 0) {
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
        if(select_sprite(gs->ll, gs->catlayer,
                         TEST_RESTING, TEST_SPRITE_DIM) < 0) {
            return(-1);
        }

        gs->zzzlayer = create_sprite(gs->ll, gs->tilemap,
                                     TEST_SPRITE_DIM, SPRITE_SCALE,
                                     "zzzlayer");
        if(gs->zzzlayer < 0) {
            return(-1);
        }
        if(select_sprite(gs->ll, gs->zzzlayer,
                         TEST_ZZZ, TEST_SPRITE_DIM) < 0) {
            return(-1);
        }
        
        play_cat_sound(gs, gs->purr);
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

int game_setup(GameState *gs) {
    reset_state(gs);

    if(clear_tilemap(gs->ll, gs->hudTilemap,
                     HUD_WIDTH, HUD_HEIGHT) < 0) {
        return(-1);
    }
    if(print_to_tilemap(gs->ll, gs->hudTilemap,
                        TEXT_SCORE_X, TEXT_SCORE_Y,
                        TEXT_SCORE) < 0) {
        return(-1);
    }
    if(printf_to_tilemap(gs->ll, gs->hudTilemap,
                            TEXT_SCORE_X + (sizeof(TEXT_SCORE) - 1), TEXT_SCORE_Y,
                            "%d", gs->score) < 0) {
        fprintf(stderr, "Failed to print score.\n");
        return(-1);
    }
#ifdef SHOW_FPS
    if(print_to_tilemap(gs->ll, gs->hudTilemap,
                        TEXT_FPS_X, TEXT_FPS_Y,
                        TEXT_FPS) < 0) {
        return(-1);
    }
#endif

    return(0);
}

/* for when no extra control other than passing on the next mode fromt he input
 * function was set */
GameMode* generic_control(void *priv) {
    GameState *gs = (GameState *)priv;

    return(gs->nextMode);
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

                gs->nextMode = &game;
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

int title_draw(void *priv) {
    GameState *gs = (GameState *)priv;

    if(tilemap_draw_layer(gs->ll, gs->titleLayer) < 0) {
        fprintf(stderr, "Failed to draw title layer.\n");
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
                gs->spawnerx = SPAWNERRAND(WINDOW_WIDTH);
                gs->spawnery = SPAWNERRAND(WINDOW_HEIGHT);
                if(select_sprite(gs->ll, gs->spawnerSprite,
                                 TEST_BIGHOLE, TEST_SPRITE_DIM) < 0) {
                    return(NULL);
                }

                if(position_sprite(gs->ll, gs->spawnerSprite,
                                   gs->spawnerx, gs->spawnery,
                                   SCALED_SPRITE_DIM) < 0) {
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

    if(process_enemies(gs) < 0) {
        return(NULL);
    }

    return(&game);
}

int game_draw(void *priv) {
    GameState *gs = (GameState *)priv;

    if(gs->spawner != SPAWN_NONE) {
        if(tilemap_draw_layer(gs->ll, gs->spawnerSprite) < 0) {
            fprintf(stderr, "Failed to draw spawner.\n");
            return(-1);
        }
    }

    if(draw_enemies(gs) < 0) {
        return(-1);
    }

    return(0);
}

int main(int argc, char **argv) {
    SDL_Window *win;
    SDL_Renderer *renderer;
    Uint32 format;
#ifdef SHOW_FPS
    struct timespec thisTime;
    struct timespec lastTime;
#endif
    SDL_Event lastEvent;
    Synth *s;
    int fullscreen;
    int font = -1;
    int tsTitle = -1;
    int tmTitle = -1;
    int tmBackground = -1;
    Uint32 nextMotion = SDL_GetTicks() + ACTOR_RATE;
    int meow1_buf, meow2_buf, cat_activation_buf, purr_buf;
    int meat_buf, meat2_buf;
    GameMode *mode;
    int nextColorBox;
    ColorBox *cbox = NULL;

    /* just a non-negative value to pass as pointer to load_graphic tomake it
     * simply not create a new layer itself, nor modify any layer properties. */
    int NOLAYER = 0;

    if(SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO) < 0) {
        fprintf(stderr, "Failed to initialize SDL: %s\n",
                SDL_GetError());
        exit(EXIT_FAILURE);
    }

    if(initialize_video(&win, &renderer, &format,
                        WINDOW_WIDTH, WINDOW_HEIGHT,
                        WINDOW_TITLE, WINDOW_FLAGS, RENDERER_FLAGS) < 0) {
        fprintf(stderr, "Failed to initialize video.\n");
        goto error_sdl;
    }

    /* fix the logical resolution (play field size, in this case) */
    if(SDL_RenderSetLogicalSize(renderer,
                                WINDOW_WIDTH,
                                WINDOW_HEIGHT) < 0) {
        fprintf(stderr, "Failed to set render logical size.\n");
        goto error_video;
    }

    /* initialize the layerlist */
    gs.ll = layerlist_new(renderer, format,
                          log_cb, stderr);
    if(gs.ll == NULL) {
        fprintf(stderr, "Failed to create layerlist.\n");
        goto error_video;
    }

    /* initialize the audio */
    gs.as = init_audio_state(DEFAULT_RATE);
    if(gs.as == NULL) {
        goto error_ll;
    }
    s = get_synth(gs.as);

    /* seed random */
    srand(time(NULL));

    /* init stuff */

    gs.goreTex = NULL;

    gs.tileset = -1;
    gs.tilemap = -1;
    if(load_graphic(gs.ll, TEST_SPRITESHEET,
                    TEST_SPRITE_DIM, TEST_SPRITE_DIM,
                    &(gs.tileset), &(gs.tilemap), &NOLAYER,
                    TEST_SPRITESHEET_VALUES,
                    TEST_SPRITESHEET_COLORMOD,
                    ARRAY_COUNT(TEST_SPRITESHEET_VALUES), 1,
                    1.0, "spritesheet") < 0) {
        goto error_synth;
    }

    gs.catlayer = create_sprite(gs.ll, gs.tilemap,
                                TEST_SPRITE_DIM, SPRITE_SCALE,
                                "catlayer");
    if(gs.catlayer < 0) {
        goto error_synth;
    }

    gs.spawnerSprite = create_sprite(gs.ll, gs.tilemap,
                                     TEST_SPRITE_DIM, SPRITE_SCALE,
                                     "spawnerSprite");
    if(gs.spawnerSprite < 0) {
        goto error_synth;
    }

    gs.hudTilemap = -1;
    gs.hud = -1;
    if(load_graphic(gs.ll, "font.bmp",
                    8, 8,
                    &font, &(gs.hudTilemap), &(gs.hud),
                    NULL,
                    NULL,
                    HUD_WIDTH, HUD_HEIGHT,
                    HUD_SCALE, "font") < 0) {
        goto error_synth;
    }

    unsigned int titleTilemap = 0;
    gs.titleLayer = -1;
    if(load_graphic(gs.ll, "title.bmp",
                    256, 192,
                    &tsTitle, &tmTitle, &(gs.titleLayer),
                    &titleTilemap,
                    NULL,
                    1, 1,
                    SPRITE_SCALE, "title") < 0) {
        goto error_synth;
    }
    if(tilemap_set_layer_pos(gs.ll, gs.titleLayer,
                             CENTER(WINDOW_WIDTH, 256 * SPRITE_SCALE),
                             (WINDOW_HEIGHT - (192 * SPRITE_SCALE)) / 4) < 0) {
        fprintf(stderr, "Failed to set title pos.\n");
        goto error_synth;
    }

    /* create background tilemap */
    unsigned int bgTilemap[WINDOW_TILE_WIDTH * WINDOW_TILE_HEIGHT];
    fill_tilemap_with_pattern(bgTilemap,
                              WINDOW_TILE_WIDTH, WINDOW_TILE_HEIGHT,
                              BG_PATTERN,
                              BG_PATTERN_WIDTH, BG_PATTERN_HEIGHT);
    gs.lBackground = -1;
    if(load_graphic(gs.ll, NULL,
                    TEST_SPRITE_DIM, TEST_SPRITE_DIM,
                    &(gs.tileset), &tmBackground, &(gs.lBackground),
                    bgTilemap,
                    NULL,
                    WINDOW_TILE_WIDTH, WINDOW_TILE_HEIGHT,
                    SPRITE_SCALE, "background") < 0) {
        goto error_synth;
    }
    if(tilemap_set_layer_blendmode(gs.ll, gs.lBackground,
                                   TILEMAP_BLENDMODE_ADD) < 0) {
        fprintf(stderr, "Failed to set background blend mode.\n");
        goto error_synth;
    }
    if(tilemap_set_layer_colormod(gs.ll, gs.lBackground,
                                  C_BGTILES) < 0) {
        fprintf(stderr, "Failed to set background colormod.\n");
        goto error_synth;
    }

    /* create and clear the gore texture */
    gs.goreTex = SDL_CreateTexture(renderer, format,
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
    if(SDL_SetRenderTarget(renderer, gs.goreTex) < 0) {
        fprintf(stderr, "Failed to set render target to gore texture.\n");
        goto error_synth;
    }
    if(SDL_SetRenderDrawColor(renderer,
                              0, 0, 0,
                              SDL_ALPHA_TRANSPARENT) < 0) {
        fprintf(stderr, "Failed to set render draw color.\n");
        goto error_synth;
    } 
    if(SDL_RenderClear(renderer) < 0) {
        fprintf(stderr, "Failed to clear gore texture.\n");
        goto error_synth;
    }
    /* restore screen rendering */
    if(SDL_SetRenderTarget(renderer, NULL) < 0) {
        fprintf(stderr, "Failed to set render target to screen.\n");
        goto error_synth;
    }
    gs.goreSprite = create_sprite(gs.ll, gs.tilemap,
                                  TEST_SPRITE_DIM, SPRITE_SCALE,
                                  "goreSprite");
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

    if(clear_tilemap(gs.ll, gs.hudTilemap,
                     HUD_WIDTH, HUD_HEIGHT) < 0) {
        goto error_synth;
    }
    if(print_to_tilemap(gs.ll, gs.hudTilemap,
                        TEXT_START_X, TEXT_START_Y,
                        TEXT_START) < 0) {
        goto error_synth;
    }
#ifdef SHOW_FPS
    if(print_to_tilemap(gs.ll, gs.hudTilemap,
                        TEXT_FPS_X, TEXT_FPS_Y,
                        TEXT_FPS) < 0) {
        goto error_synth;
    }
    if(clock_gettime(CLOCK_MONOTONIC, &lastTime) < 0) {
        fprintf(stderr, "clock_gettime returned error.\n");
        goto error_synth;
    }
#endif

    init_sprite_list(&gs);
    reset_state(&gs);
    cbox = init_color_boxes(gs.ll, MAX_COLOR_BOX,
                            WINDOW_WIDTH, WINDOW_HEIGHT,
                            SPRITE_SCALE, ACTOR_RATE);
    if(cbox == NULL) {
        goto error_synth;
    }
    /* make sure the mouse position is set to _something_ sensical.  Just make
     * it think the mouse is positioned where the cat is so it starts idle
     * until a mouse motion event comes in. */
    gs.mousex = gs.catx;
    gs.mousey = gs.caty;
    fullscreen = 0;
    nextColorBox = 0;

    /* ##### MAIN LOOP ##### */
    gs.nextMode = &title;
    mode = &title;
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

            /* always update the cat */
            if(update_cat(&gs) < 0) {
                goto error_synth;
            }

            mode = mode->control(mode->priv);
            if(mode == NULL) {
                goto error_synth;
            }

            nextColorBox -= ACTOR_RATE;
            if(nextColorBox <= 0) {
                int cboxret = create_color_box(cbox, gs.tileset,
                                               BG_PATTERN_WIDTH, BG_PATTERN_HEIGHT,
                                               BG_PATTERN,
                                               TEST_SPRITE_DIM, TEST_SPRITE_DIM);
                if(cboxret < 0) {
                    goto error_synth;
                }

                nextColorBox += cboxret;
            }

            if(update_color_boxes(cbox) < 0) {
                goto error_synth;
            }

            thisTick = SDL_GetTicks();
        }

#ifdef SHOW_FPS
        if(clock_gettime(CLOCK_MONOTONIC, &thisTime) < 0) {
            fprintf(stderr, "clock_gettime returned error.\n");
            goto error_synth;
        }

        unsigned int nanoseconds;
        if(thisTime.tv_sec > lastTime.tv_sec) {
            nanoseconds = NANOSECOND - lastTime.tv_nsec;
            nanoseconds += thisTime.tv_nsec;
            nanoseconds += (thisTime.tv_sec - lastTime.tv_sec - 1) * NANOSECOND;
        } else {
            nanoseconds = thisTime.tv_nsec - lastTime.tv_nsec;
        }
        /* put a bunch of spaces to make sure different lengths of numbers clear
         * properly */
        if(printf_to_tilemap(gs.ll, gs.hudTilemap,
                                TEXT_FPS_X + (sizeof(TEXT_FPS) - 1), TEXT_FPS_Y,
                                "%.1f       ", (float)NANOSECOND / nanoseconds) < 0) {
            fprintf(stderr, "Failed to print fps.\n");
            return(-1);
        }

        lastTime.tv_sec = thisTime.tv_sec;
        lastTime.tv_nsec = thisTime.tv_nsec;
#endif

        if(mode != NULL) {
            /* always draw the background, boxes and gore layer */
            if(prepare_frame(gs.ll,
                             BG_R, BG_G, BG_B,
                             gs.lBackground) < 0) {
                goto error_synth;
            }

            if(draw_color_boxes(cbox) < 0) {
                goto error_synth;
            }

            if(SDL_RenderCopy(renderer, gs.goreTex, NULL, NULL) < 0) {
                fprintf(stderr, "Failed to copy gore layer.\n");
                return(-1);
            }

            if(mode->draw(mode->priv) < 0) {
                goto error_synth;
            }

            /* always draw the cat */
            if(draw_cat(&gs) < 0) {
                goto error_synth;
            }

            /* draw the hud above everything */
            if(draw_text_layer(gs.ll, gs.hud, HUD_SCALE, C_HUD_SHADOW, C_OPAQUE) < 0) {
                goto error_synth;
            }
        }

        SDL_RenderPresent(renderer);
    }

    free_sprites(&gs);

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

    free_color_boxes(cbox);

    tilemap_free_layer(gs.ll, gs.titleLayer);
    tilemap_free_tilemap(gs.ll, tmTitle);
    tilemap_free_tileset(gs.ll, tsTitle);
    tilemap_free_layer(gs.ll, gs.hud);
    tilemap_free_tilemap(gs.ll, gs.hudTilemap);
    tilemap_free_tileset(gs.ll, font);
    tilemap_free_layer(gs.ll, gs.lBackground);
    tilemap_free_tilemap(gs.ll, tmBackground);
    tilemap_free_layer(gs.ll, gs.goreSprite);
    tilemap_free_layer(gs.ll, gs.spawnerSprite);
    tilemap_free_layer(gs.ll, gs.catlayer);
    tilemap_free_tilemap(gs.ll, gs.tilemap);
    tilemap_free_tileset(gs.ll, gs.tileset);
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
    if(cbox != NULL) {
        free(cbox);
    }
error_ll:
    layerlist_free(gs.ll);
error_video:
    SDL_DestroyWindow(win);
error_sdl:
    SDL_Quit();

    exit(EXIT_FAILURE);
}
