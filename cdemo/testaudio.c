#include <stdio.h>
#include <stdlib.h>

#include "testaudio.h"

#include "log_cb.h"
#include "extramath.h"

#define MAX_ACTIVE_PLAYERS (32)

struct ActivePlayer_s {
    int player;
    float volume;
    float panning;
    int token;
};

struct AudioState_s {
    Synth *s;
    int fragments;
    ActivePlayer player[MAX_ACTIVE_PLAYERS];
    int mixBuffer;
    int leftBuffer;
    int rightBuffer;
    int mixPlayer;
};

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

int audio_frame_cb(void *priv, Synth *s) {
    AudioState *as = (AudioState *)priv;
    unsigned int i;
    int playerRet;
    float volume;
    unsigned int needed = synth_get_samples_needed(s);

    /* check for underrun and enlarge the fragment size in the hopes of
     * settling on the minimum necessary number of fragments and avoid crackles
     */
    if(synth_has_underrun(s)) {
        /* disable the synth before doing fragment operations */
        if(synth_set_enabled(s, 0) < 0) {
            fprintf(stderr, "Failed to stop synth.\n");
            return(-1);
        }
        /* try to increase the fragments count by 1 */
        if(synth_set_fragments(s, as->fragments + 1) < 0) {
            fprintf(stderr, "Failed to set fragments, disabling.\n");
            return(-1);
        }
        as->fragments++;
        /* free the reference from the mix buffer */
        if(synth_free_player(s, as->mixPlayer) < 0) {
            fprintf(stderr, "Failed to free mix player.\n");
            return(-1);
        }
        /* free the buffers */
        if(synth_free_buffer(s, as->mixBuffer) < 0) {
            fprintf(stderr, "Failed to mix buffer.\n");
            return(-1);
        }
        if(synth_free_buffer(s, as->leftBuffer) < 0) {
            fprintf(stderr, "Failed to free left channel buffer.\n");
            return(-1);
        }
        if(synth_free_buffer(s, as->rightBuffer) < 0) {
            fprintf(stderr, "Failed to free right channel buffer.\n");
            return(-1);
        }
        /* remake them with the new fragment size */
        if(create_mix_buffers(as) < 0) {
            return(-1);
        }

        /* re-enable the synth.  I don't entirely remember how this works but
         * this function may be called again recursively so make sure nothing
         * else happens between this and returning. */
        if(synth_set_enabled(s, 1) < 0) {
            /* if it is recursive, allow the error to fall through, but don't
             * print something that might end up spammy */
            return(-1);
        }
        /* don't try to generate audio that'll just be crackles anyway */
        return(0);
    }

    /* clear channel mix buffers */
    if(synth_silence_buffer(s, as->leftBuffer, 0, needed) < 0) {
        fprintf(stderr, "Failed to silence left buffer.\n");
        return(-1);
    }
    if(synth_silence_buffer(s, as->rightBuffer, 0, needed) < 0) {
        fprintf(stderr, "Failed to silence right buffer.\n");
        return(-1);
    }

    for(i = 0; i < MAX_ACTIVE_PLAYERS; i++) {
        if(as->player[i].player >= 0) {
            /* clear mix buffer */
            if(synth_silence_buffer(s, as->mixBuffer, 0, needed) < 0) {
                fprintf(stderr, "Failed to silence mix buffer.\n");
                return(-1);
            }

            /* point active player to mix buffer, resets output pos to 0 */
            if(synth_set_player_output_buffer(s, as->player[i].player, as->mixBuffer) < 0) {
                fprintf(stderr, "failed to set active player to mix buffer.\n");
                return(-1);
            }
            playerRet = synth_run_player(s, as->player[i].player, needed);
            /* avoid external references to mix buffer */
            if(synth_set_player_output_buffer(s, as->player[i].player, 0) < 0) {
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
                if(synth_set_player_input_buffer(s, as->mixPlayer, as->mixBuffer) < 0) {
                    fprintf(stderr, "Failed to set mix player input to mix buffer.\n");
                    return(-1);
                }
                if(synth_set_player_output_buffer(s, as->mixPlayer, as->leftBuffer) < 0) {
                    fprintf(stderr, "Failed to set mix player output to left buffer.\n");
                    return(-1);
                }
                if(as->player[i].panning > 0) {
                    volume = as->player[i].volume * (1.0 - as->player[i].panning);
                } else {
                    volume = as->player[i].volume;
                }
                if(synth_set_player_volume(s, as->mixPlayer, volume) < 0) {
                    fprintf(stderr, "Failed to set mix player left volume.\n");
                    return(-1);
                }
                if(synth_run_player(s, as->mixPlayer, playerRet) < 0) {
                    fprintf(stderr, "Failed to run mix player for left channel.\n");
                    return(-1);
                }
                /* right channel, reset mix buffer player to 0 */
                if(synth_set_player_input_buffer_pos(s, as->mixPlayer, 0) < 0) {
                    fprintf(stderr, "Failed to reset center player output pos.\n");
                    return(-1);
                }
                if(synth_set_player_output_buffer(s, as->mixPlayer, as->rightBuffer) < 0) {
                    fprintf(stderr, "Failed to set mix player output to right buffer.\n");
                    return(-1);
                }
                if(as->player[i].panning < 0) {
                    volume = as->player[i].volume * (1.0 + as->player[i].panning);
                } else {
                    volume = as->player[i].volume;
                }
                if(synth_set_player_volume(s, as->mixPlayer, volume) < 0) {
                    fprintf(stderr, "Failed to set mix player right volume.\n");
                    return(-1);
                }
                if(synth_run_player(s, as->mixPlayer, playerRet) < 0) {
                    fprintf(stderr, "Failed to run mix player for right channel.\n");
                    return(-1);
                }
            }
        }
    }

    /* play out both channels */
    if(synth_set_player_input_buffer(s, as->mixPlayer, as->leftBuffer) < 0) {
        fprintf(stderr, "Failed to set mix player input to left buffer.\n");
        return(-1);
    }
    if(synth_set_player_output_buffer(s, as->mixPlayer, 0) < 0) {
        fprintf(stderr, "Failed to set mix player output to left channel.\n");
        return(-1);
    }
    if(synth_run_player(s, as->mixPlayer, needed) < 0) {
        fprintf(stderr, "Failed to output to left channel.\n");
        return(-1);
    }
    if(synth_set_player_input_buffer(s, as->mixPlayer, as->rightBuffer) < 0) {
        fprintf(stderr, "Failed to set mix player input right buffer.\n");
        return(-1);
    }
    if(synth_set_player_output_buffer(s, as->mixPlayer, 1) < 0) {
        fprintf(stderr, "Failed to set mix player output to right channel.\n");
        return(-1);
    }
    if(synth_run_player(s, as->mixPlayer, needed) < 0) {
        fprintf(stderr, "Failed to output to right channel.\n");
        return(-1);
    }

    return(needed);
}

AudioState *init_audio_state(unsigned int rate) {
    AudioState *as = malloc(sizeof(AudioState));
    unsigned int i;

    if(as == NULL) {
        fprintf(stderr, "Failed to allocate audio state.\n");
        return(NULL);
    }

    as->s = synth_new(audio_frame_cb,
                      as,
                      log_cb,
                      stderr,
                      rate,
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
