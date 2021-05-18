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
 * This is the audio portion of the uncrustygame/libcrustygame library.  It
 * deals in managing audio buffers and player structures which handle outputting
 * those buffers to other buffers in memory or to the audio device, using SDL.
 * It should be fairly capable in being able to get basic audio effects and
 * playing out samples and music.
 *
 * The idea in how it's to be used is any audio that is to be played is loaded
 * in to its internal buffers, then a player is assigned for those buffers
 * which handles playback.  Many parameters can be modified to affect the way
 * the buffers are played back and other buffers can also be used to control
 * sample-by-sample how playback should be affected for many of the parameters.
 * the player may also output to other internal buffers so multiple stages of
 * effects can be performed and even buffers used to control parameters can be
 * generated in real time for a chain of players to make complex effects.
 * On initialization some number of buffers equal to the number of audio
 * channels will be available.  They can only be used for output, and their
 * size will vary based on how full the buffers are, and other factors.
 */
#ifndef _SYNTH_H
#define _SYNTH_H

#include <SDL.h>

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

typedef struct Synth_s Synth;

/*
 * The callback which you, the programmer, provide for the synth engine to
 * indicate it needs audio, in response to synth_frame() being called to try
 * to top up the audio buffers.  May be called several times per synth_frame()
 * call or not at all if the buffers are full.
 *
 * priv     A pointer you provided to synth_new
 * s        The relevant Synth structure which needs updating
 * return   0 if there were no issues, negative to indicate to the engine there
 *          was some problem to indicate back to the synth_frame call.
 */
typedef int (*synth_frame_cb_t)(void *priv, Synth *s);
/*
 * The callback you provide to handle any logging output, takes printf style
 * arguments.
 *
 * priv     A pointer provided to synth_new
 * fmt      the format string
 * ...      the arguments
 */
typedef void (*synth_log_cb_t)(void *priv, const char *fmt, ...);

/*
 * Convert from an SDL_AudioFormat to a SynthImportType.  Not all formats
 * supported by SDL are supported by the synth engine so it can indicate an
 * invalid format if not.
 *
 * format   The SDL_AudioFormat to convert
 * return   The SynthImportType you can provide to synth_add_buffer
 */
SynthImportType synth_type_from_audioformat(SDL_AudioFormat format);
/*
 * Helper function to take a path to a WAV file and return a synth buffer
 * handle.  The sample rate from the WAV file is also returned.
 *
 * s        The Synth structure
 * filename A path to a WAV file to load.
 * rate     A pointer to an unsigned int that will be populated with the sample
 *          rate of the WAV file.
 * return   0 on success, -1 on failure
 */
int synth_buffer_from_wav(Synth *s, const char *filename, unsigned int *rate);

/*
 * Output information about the provided Synth structure, all loaded buffers
 * and all players.  Outputs through the log callback provided associated with
 * the synth structure.
 *
 * s        The Synth structure 
 */
void synth_print_full_stats(Synth *s);
/*
 * Get the amount of samples necessary to top up the audio buffers.  Usually
 * useful during the audio callback.
 *
 * s        the Synth structure
 * return   number of samples needed
 */
unsigned int synth_get_samples_needed(Synth *s);
/*
 * Create a new synth structure.  The structure is "stopped" on creation.  The
 * specified format might not be what is gotten.
 *
 * synth_frame_cb   The callback which will be called when synth_get_rate is
 *                  called to request that more audio may be needed.
 * synth_frame_priv some pointer which you provide which will be passed in to
 *                  the synth_frame_cb calls.
 * synth_log_cb     Callback for logging.
 * synth_log_priv   Some pointer which you provide which will be passed on the
 *                  synth_log_cb calls.
 * rate             The prefered sample rate.
 * channels         The prefered channels count.
 * return           The new Synth structure.
 */
Synth *synth_new(synth_frame_cb_t synth_frame_cb,
                 void *synth_frame_priv,
                 synth_log_cb_t synth_log_cb,
                 void *synth_log_priv,
                 unsigned int rate,
                 unsigned int channels);
/*
 * Stop the synth, free any buffers created by it and close the associated
 * SDL_audio device.
 *
 * s        The Synth structure.
 */
void synth_free(Synth *s);
/*
 * Get the sample rate the audio device was initialized with, may be different
 * from what was requested.
 *
 * s        The Synth structure.
 * return   device sample rate
 */
unsigned int synth_get_rate(Synth *s);
/*
 * Get the channel count the audio device was initialized with, may be different
 * from what was requested.  Channel order should be the same as SDL_audio, and
 * it might end up being some "surround" mode, in which case there will be
 * many initial output buffers.  Note that surround/multichannel output beyond
 * stereo hasn't been tested and might not work at all.
 *
 * s        the Synth structure
 * return   the channel count
 */
unsigned int synth_get_channels(Synth *s);
/*
 * Get the fragment size the audio device was initialized with.  Can be useful
 * in calculating, for example, how many fragments there will be in 1 frame of
 * video, or to determine how much latency a certain amount of fragments will
 * add.
 * See: synth_set_fragments
 *
 * s        the Synth structure
 * return   fragment size in samples.
 */
unsigned int synth_get_fragment_size(Synth *s);
/*
 * Returns non-zero if there was an underrun resulting from the buffers being
 * depleted before a synth_frame was called and fulfilled.  At this point there
 * will probably have been pops and/or crackles or some other disruption of
 * audio and that either some external process has held things up or the rest
 * of your program is running slowly/lagging behind or that the fragment count
 * is simply too low.
 *
 * s        the Synth structure
 * return   0 if no underrun has occurred, non-zero if it has
 */
int synth_has_underrun(Synth *s);
/*
 * Set the enabled state of the synth, 0 to stop the synth and non-zero to start
 * it.  On the first call, the frame callback will be called to fill the buffers
 * up completely, so this should be called only when things are set up and ready
 * to start generating audio.
 *
 * s        the Synth structure
 * enabled  0 to stop, non-zero to start
 * return   0 on success, -1 on failure, including frame callback failures
 */
int synth_set_enabled(Synth *s, int enabled);
/*
 * Indicate that it's a good time for the frame callback to be run.  May result
 * in the frame callback being called once or many times or not at all.
 *
 * s        the Synth structure
 * return   0 on success, -1 on failure, including frame callback failures
 */
int synth_frame(Synth *s);
/*
 * Set the number of fragments that should be buffered internally.  Higher
 * values will add more latency but will buy more time between synth_frame
 * calls.  This must be called at least once before starting and can't be called
 * while the engine is running, it must be stopped first.
 * See: synth_get_fragment_size
 *
 * s            the Synth structure
 * fragments    the size of the internal buffer, in fragments
 * return       0 on success, -1 on failure
 */
int synth_set_fragments(Synth *s,
                        unsigned int fragments);
/*
 * Add a new buffer, given type, data and a size, in samples.  NULL can be given
 * as data to create a "silent" buffer which can be output to.  Everything is
 * internally converted to 32 bit float format, with integer formats scaled
 * from -1.0 to +1.0, then output to whatever is appropriate for the audio
 * device.  All buffers are mono by nature.  Stereo effects would be achieved
 * by writing to the individual output buffers.
 *
 * s        the Synth structure
 * type     The data format in "data"
 * data     the data
 * size     the size of the data in samples
 * return   the buffer handle or -1 on failure
 */
int synth_add_buffer(Synth *s,
                     SynthImportType type,
                     void *data,
                     unsigned int size);
/*
 * Free a buffer and its memory.
 *
 * s        the Synth structure
 * index    the buffer handle index
 * return   0 on success, -1 on failure
 */
int synth_free_buffer(Synth *s, unsigned int index);
/*
 * Silence a buffer which contains audio.
 *
 * s        The Synth structure
 * index    The buffer index to silence
 * start    The start sample to silence
 * length   The length of the range to silence in samples
 * return   0 on success, -1 on failure
 */
int synth_silence_buffer(Synth *s,
                         unsigned int index,
                         unsigned int start,
                         unsigned int length);
/*
 * Create a player.  These control all the input and output of buffers and how
 * they will be played back.
 *
 * s        The Synth structure
 * inBuffer The initial input buffer for the new player
 * return   the new player handle or -1 on failure
 */
int synth_add_player(Synth *s, unsigned int inBuffer);
/*
 * Free a player.  Doesn't free any buffers and doesn't necessarily free any
 * memory.  In fact, players are kept in an internal array that only grows
 * logarithmically as needed, so lots and lots of players will only grow that,
 * while freeing them won't shrink it.  The structure isn't particularly huge
 * or anything but it's maybe something to consider to avoid memory leaks.
 * Player structures in the array are reused, though when they've been freed.
 *
 * s        The Synth structure
 * index    the player index to free
 * return   0 on success, -1 on failure
 */
int synth_free_player(Synth *s, unsigned int index);
/*
 * Set the input buffer handle for the player.  Only buffers created can be
 * input buffers, not the final output buffer handles, as their contents and
 * size is unpredictable.
 *
 * s        The Synth structure
 * index    the player index to update
 * inBuffer the buffer to apply to the player as input
 * return   0 on success, -1 on failure
 */
int synth_set_player_input_buffer(Synth *s,
                                  unsigned int index,
                                  unsigned int inBuffer);
/*
 * Set the position in samples that the input buffer should start playing from.
 *
 * s        the Synth structure
 * index    the player index to update
 * inPos    the position to start playing at.  Internally this value is a
 *          floating point value so fractional position information is retained
 *          for non-integer playback speeds
 * return   0 on success, -1 on failure
 */
int synth_set_player_input_buffer_pos(Synth *s,
                                      unsigned int index,
                                      float inPos);
/*
 * Set a buffer to output to, either a buffer which has been created or to a
 * final output buffer.
 *
 * s            the Synth structure
 * index        the played index to update
 * outBuffer    the buffer which the player should output to
 * return       0 on success, -1 on failure
 */
int synth_set_player_output_buffer(Synth *s,
                                   unsigned int index,
                                   unsigned int outBuffer);
/*
 * Set the output buffer position.  In the case of final output buffers, this
 * is relative to the position which needs to be filled from, and the length
 * being the amount of samples needed, otherwise it's just the whole output
 * buffer.  Since buffers are always filled sample by sample, this value is an
 * integer.
 *
 * s        the Synth structure
 * index    the player index to update
 * outPos   the position to start output from
 * return   0 on success, -1 on failure
 */
int synth_set_player_output_buffer_pos(Synth *s,
                                       unsigned int index,
                                       unsigned int outPos);
/*
 * Set the output mode or operation for the player.
 * REPLACE: just replace the value in the buffer with the result of the
 *          player's output
 * ADD: add(mix) the player's output with the buffer's value, there is no
 *      protection from clipping but internally, buffers are 32 bit float so
 *      values swinging larger than -1.0 to +1.0 can be compressed down,
 *      otherwise, I have no idea what it would sound like when SDL passes it
 *      on to the audio device.
 *
 * s        the Synth structure
 * index    the player index to update
 * outOp    the output mode/operation
 * return   0 on success, -1 on failure
 */
int synth_set_player_output_mode(Synth *s,
                                 unsigned int index,
                                 SynthOutputOperation outOp);
/*
 * Set the volume mode.
 * CONSTANT: Simply multiply each output sample by the constant set volume.
 * SOURCE: Multiply each output sample by the values from a buffer.  Each
 *         sample output by the player is multiplied by the samples in the
 *         buffer in sequence, as well as the constant volume.
 *         Can be used for envelopes or amplitude modulation effects if you're
 *         extra hopeful things work properly.
 * See: player_set_player_volume, player_set_player_volume_source
 *
 * s        the Synth structure
 * index    the player index to update
 * volMode  the volume mode
 * return   0 on success, -1 on failure
 */
int synth_set_player_volume_mode(Synth *s,
                                 unsigned int index,
                                 SynthVolumeMode volMode);
/*
 * Set the constant player volume.
 * See: synth_set_player_volume_mode
 *
 * s        the Synth structure
 * index    the player index to update
 * volume   the value to multiply the channel output by.  1.0 for no change
 * return   0 on success, -1 on failure
 */
int synth_set_player_volume(Synth *s,
                            unsigned int index,
                            float volume);
/*
 * Set the player volume source.  Must be a created buffer.  The position which
 * is read from starts at 0 and is read sequentially forward until its end.
 * Each call resets the position to 0.
 * See: synth_set_player_volume_mode
 *
 * s            the Synth structure
 * index        the player index to update
 * volBuffer    the buffer index
 * return       0 on success, -1 on failure
 */
int synth_set_player_volume_source(Synth *s,
                                   unsigned int index,
                                   unsigned int volBuffer);
/*
 * Set the playback mode for the player.
 * ONCE: Play the sample once then stop once the end is reached.
 * LOOP: Continuously play the sample until the loop end is reached then
 *       continue back to the loop start indefinitely.
 * PINGPONG: Play forward until loop end, then play backwards until loop start
 *           then repeat indefinitely
 * PHASE_SOURCE: Read phase source from a buffer, where 0.0 represents the loop
 *               start position of the input buffer and 1.0 represents the loop
 *               end position.  This overrides any speed settings.
 *               I guess this can be used for like frequency modulation effects
 *               or something, I'm not entirely sure how that works but I just
 *               figured someone might want to mess around with something weird
 *               like this.
 * See: synth_set_player_loop_start
 *      synth_set_player_loop_end
 *      synth_set_player_phase_source
 *
 * s        the Synth structure
 * index    the player index to update
 * mode     the playback mode
 * return   0 on success, -1 on failure
 */
int synth_set_player_mode(Synth *s,
                          unsigned int index,
                          SynthPlayerMode mode);
/*
 * Set loop start, or phase source start position.
 * See: synth_set_player_mode
 *
 * s            the Synth structure
 * index        the player index to update
 * loopStart    the starting sample to loop from
 * return       0 on success, -1 on failure
 */
int synth_set_player_loop_start(Synth *s,
                                unsigned int index,
                                unsigned int loopStart);
/*
 * Set loop end, or phase source end position.
 * See: synth_set_player_mode
 *
 * s        the Synth structure
 * index    the player index to update
 * loopEnd  the ending sample to loop to
 * return   0 on success, -1 on failure
 */
int synth_set_player_loop_end(Synth *s,
                              unsigned int index,
                              unsigned int loopEnd);
/*
 * Set the buffer to read phase source samples from, similar rules as volume
 * source, except instead of multiplying the output by each sample, input buffer
 * samples will be referenced based on the loop start and end range given source
 * buffer samples from 0.0 to +1.0.
 *
 * s            the Synth structure
 * index        the player index to update
 * phaseBuffer  the buffer to get phase source samples from
 * return       0 on success, -1 on failure
 */
int synth_set_player_phase_source(Synth *s,
                                   unsigned int index,
                                   unsigned int phaseBuffer);
/*
 * Set the player's speed mode.  Same rules as volume mode, just affects the
 * rate at which input buffer samples are advanced.
 * See: synth_set_player_speed_mode
 *      synth_set_player_speed
 *      synth_set_player_volume_mode
 *
 * s            the Synth structure
 * index        the player index to update
 * speedMode    the speed mode
 * return       0 on success, -1 on failure
 */
int synth_set_player_speed_mode(Synth *s,
                                unsigned int index,
                                SynthSpeedMode speedMode);
/*
 * Sets the constant player speed.
 * See: synth_set_player_speed_mode
 *
 * s        the Synth structure
 * index    the player index to update
 * speed    the constant player speed
 * return   0 on success, -1 on failure
 */
int synth_set_player_speed(Synth *s,
                           unsigned int index,
                           float speed);
/*
 * Sets the source for playback speed.
 * See: synth_set_player_speed_mode
 *
 * s            the Synth structure
 * index        the player index to update
 * speedBuffer  the buffer to use for speed samples
 * return       0 on success, -1 on failure
 */
int synth_set_player_speed_source(Synth *s,
                                  unsigned int index,
                                  unsigned int speedBuffer);
/*
 * Actually run the player, given all the criteria given for some number of
 * samples or until some source is depleted.
 *
 * s            the Synth structure
 * index        the player index to run
 * reqSamples   the number of samples desired
 * return       the number of samples generated before something ran out, or -1 on failure
 */
int synth_run_player(Synth *s,
                     unsigned int index,
                     unsigned int reqSamples);

#endif
