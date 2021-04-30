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

#ifndef _SYNTH_H
#define _SYNTH_H

typedef int (*synth_frame_cb_t)(void *priv);
typedef void (*synth_log_cb_t)(void *priv, const char *fmt, ...);

/* most common formats */
typedef enum {
    SYNTH_TYPE_INVALID,
    SYNTH_TYPE_U8,
    SYNTH_TYPE_S16,
    SYNTH_TYPE_F32,
    SYNTH_TYPE_F64
} SynthImportType;

typedef enum {
    SYNTH_STOPPED,
    SYNTH_ENABLED,
    SYNTH_RUNNING
} SynthState;

typedef enum {
    SYNTH_OUTPUT_REPLACE,
    SYNTH_OUTPUT_ADD
} SynthOutputOperation;

typedef enum {
    SYNTH_VOLUME_CONSTANT,
    SYNTH_VOLUME_SOURCE
} SynthVolumeMode;

typedef enum {
    SYNTH_SPEED_CONSTANT,
    SYNTH_SPEED_SOURCE
} SynthSpeedMode;

typedef enum {
    SYNTH_MODE_ONCE,
    SYNTH_MODE_LOOP,
    SYNTH_MODE_PINGPONG,
    SYNTH_MODE_PHASE_SOURCE
} SynthPlayerMode;

typedef struct Synth_t Synth;

SynthImportType synth_type_from_audioformat(SDL_AudioFormat format);
int synth_buffer_from_wav(Synth *s, const char *filename, unsigned int *rate);

void synth_print_full_stats(Synth *s);
unsigned int synth_get_samples_needed(Synth *s);
Synth *synth_new(synth_frame_cb_t synth_frame_cb,
                 void *synth_frame_priv,
                 synth_log_cb_t synth_log_cb,
                 void *synth_log_priv,
                 unsigned int rate,
                 unsigned int channels);
void synth_free(Synth *s);
unsigned int synth_get_rate(Synth *s);
unsigned int synth_get_channels(Synth *s);
unsigned int synth_get_fragment_size(Synth *s);
int synth_has_underrun(Synth *s);
int synth_set_enabled(Synth *s, int enabled);
int synth_frame(Synth *s);
int synth_set_fragments(Synth *s,
                        unsigned int fragments);
int synth_add_buffer(Synth *s,
                     SynthImportType type,
                     void *data,
                     unsigned int size);
int synth_free_buffer(Synth *s, unsigned int index);
int synth_add_player(Synth *s, unsigned int inBuffer);
int synth_silence_buffer(Synth *s,
                         unsigned int index,
                         unsigned int start,
                         unsigned int end);
int synth_free_player(Synth *s, unsigned int index);
int synth_set_player_input_buffer(Synth *s,
                                  unsigned int index,
                                  unsigned int inBuffer);
int synth_set_player_input_buffer_pos(Synth *s,
                                      unsigned int index,
                                      float inPos);
int synth_set_player_output_buffer(Synth *s,
                                   unsigned int index,
                                   unsigned int outBuffer);
int synth_set_player_output_buffer_pos(Synth *s,
                                       unsigned int index,
                                       unsigned int outPos);
int synth_set_player_output_mode(Synth *s,
                                 unsigned int index,
                                 SynthOutputOperation outOp);
int synth_set_player_volume_mode(Synth *s,
                                 unsigned int index,
                                 SynthVolumeMode volMode);
int synth_set_player_volume(Synth *s,
                            unsigned int index,
                            float volume);
int synth_set_player_volume_source(Synth *s,
                                   unsigned int index,
                                   unsigned int volBuffer);
int synth_set_player_mode(Synth *s,
                          unsigned int index,
                          SynthPlayerMode mode);
int synth_set_player_loop_start(Synth *s,
                                unsigned int index,
                                unsigned int loopStart);
int synth_set_player_loop_end(Synth *s,
                              unsigned int index,
                              unsigned int loopEnd);
int synth_set_player_phase_source(Synth *s,
                                   unsigned int index,
                                   unsigned int phaseBuffer);
int synth_set_player_speed_mode(Synth *s,
                                unsigned int index,
                                SynthSpeedMode speedMode);
int synth_set_player_speed(Synth *s,
                           unsigned int index,
                           float speed);
int synth_set_player_speed_source(Synth *s,
                                  unsigned int index,
                                  unsigned int speedBuffer);
int synth_run_player(Synth *s,
                     unsigned int index,
                     unsigned int reqSamples);

#endif
