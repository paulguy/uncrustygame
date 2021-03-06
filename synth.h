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

#include "log_cb_helper.h"

/* Definitions */

/* try to determine a sane size which is roughly half a frame long at 60 FPS. 48000 / 120 = 400, nearest power of two is 512, user can set more fragments if they need */
#define SYNTH_DEFAULT_FRAGMENT_SIZE (512)

/* Synth stopped because the output buffer filled. */
#define SYNTH_STOPPED_OUTBUFFER    (0x01)
/* Synth stopped because the input buffer emptied */
#define SYNTH_STOPPED_INBUFFER     (0x02)
/* Synth stopped because the volume buffer reached the end */
#define SYNTH_STOPPED_VOLBUFFER    (0x04)
/* Synth stopped because the speed buffer reached the end */
#define SYNTH_STOPPED_SPEEDBUFFER  (0x08)
/* Synth stopped because the phase buffer reached the end */
#define SYNTH_STOPPED_PHASEBUFFER  (0x10)
/* Synth stopped because the slice buffer reached the end */
#define SYNTH_STOPPED_SLICEBUFFER  (0x20)
/* Synth stopped because the loop start buffer reached the end */
#define SYNTH_STOPPED_STARTBUFFER  (0x40)
/* Synth stopped because the loop length buffer reached the end */
#define SYNTH_STOPPED_LENGTHBUFFER (0x80)

/* most common formats */
typedef enum {
    SYNTH_TYPE_INVALID = 0,
    SYNTH_TYPE_U8 = 1,
    SYNTH_TYPE_S16 = 2,
    SYNTH_TYPE_F32 = 3,
    SYNTH_TYPE_F64 = 4
} SynthImportType;

/* synthesizer state:
 * STOPPED: not running
 * ENABLED: just started but hasn't generated any audio yet
 * RUNNING: started and has generated audio
 */
typedef enum {
    SYNTH_STOPPED = 0,
    SYNTH_ENABLED = 1,
    SYNTH_RUNNING = 2
} SynthState;

/* REPLACE: Replace buffer contents with output.
 * ADD: Add/mix output with buffer contents.
 */
typedef enum {
    SYNTH_OUTPUT_REPLACE = 0,
    SYNTH_OUTPUT_ADD = 1
} SynthOutputOperation;

/* CONSTANT: Use a constant value.
 * SOURCE: Use values sequentially from another buffer, possibly modified by a constant.
 */
typedef enum {
    SYNTH_AUTO_CONSTANT = 0,
    SYNTH_AUTO_SOURCE = 1
} SynthAutoMode;

/* ONCE: Play once then stop.
 * LOOP: Wrap play position by play bounds.
 * PHASE_SOURCE: Determine read position by values read from a buffer.
 */
typedef enum {
    SYNTH_MODE_ONCE = 0,
    SYNTH_MODE_LOOP = 1,
    SYNTH_MODE_PHASE_SOURCE = 2
} SynthPlayerMode;

/* the synth */
typedef struct Synth_s Synth;

/**/

/* Global Functions */

/*
 * The callback which you, the programmer, provide for the synth engine to
 * indicate it needs audio, in response to synth_frame() being called to try
 * to top up the audio buffers.  May be called several times per synth_frame()
 * call or not at all if the buffers are full.
 *
 * priv     A pointer you provided to synth_new
 * s        The relevant Synth structure which needs updating
 * return   number of samples written to output, negative to indicate to the
 *          engine there was some problem to indicate back to the synth_frame
 *          call.
 */
typedef int (*synth_frame_cb_t)(void *priv, Synth *s);

/*
 * Convert from an SDL_AudioFormat to a SynthImportType.  Not all formats
 * supported by SDL are supported by the synth engine so it can return
 * SYNTH_TYPE_INVALID if not.
 *
 * format   The SDL_AudioFormat to convert
 * return   The SynthImportType you can provide to synth_add_buffer
 */
SynthImportType synth_type_from_audioformat(SDL_AudioFormat format);
/*
 * Converts a SynthImportType to an SDL_AudioFormat.  Returns 0 if it's not a
 * valid SynthImportType (which should be an invalid/impossible
 * SDL_AudioFormat)
 *
 * type     The SynthImportType to convert
 * return   The SDL_AudioFormat
 */
SDL_AudioFormat synth_audioformat_from_type(SynthImportType type);
/*
 * Helper function to take a path to a WAV file and return a synth buffer
 * handle.  The sample rate from the WAV file is also returned.
 *
 * s        The Synth structure
 * filename A path to a WAV file to load.
 * rate     A pointer to an unsigned int that will be populated with the sample
 *          rate of the WAV file.
 * name     optional name or NULL to use the filename
 * return   0 on success, -1 on failure
 */
int synth_buffer_from_wav(Synth *s,
                          const char *filename,
                          unsigned int *rate,
                          const char *name);

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
 * If opendev is 0, don't try to open an audio device, just output to a WAV
 * file or purely buffers consumed by the client application.
 * In this case, it doesn't need to be started (doing so is a no-op, with a
 * warning) and synth_frame will instead return the amount of samples written,
 * or 0 if none could be written, and still -1 on error.
 * Some method of determining completion will have to be determined by the
 * library user.
 * The filename may be NULL to simply run the synth with no output, to be used
 * by the internal buffers methods.  synth_frame shouldn't be called in this
 * case and instead synth_consume_samples should be used to advance things.
 *
 * filename         Filename to output to as WAV or NULL to not open a file.
 * opendev          Whether an audio output device should be opened at all.
 * devname          A device name provided by SDL_GetAudioDeviceName() or NULL
 *                  to let SDL make the decision.
 * synth_frame_cb   The callback which will be called when synth_get_rate is
 *                  called to request that more audio may be needed.
 * synth_frame_priv some pointer which you provide which will be passed in to
 *                  the synth_frame_cb calls.
 * synth_log_cb     Callback for logging.
 * synth_log_priv   Some pointer which you provide which will be passed on the
 *                  synth_log_cb calls.
 * rate             The prefered sample rate.
 * channels         The prefered channels count.
 * fragsize         Some fragment size, see SYNTH_DEFAULT_FRAGMENT_SIZE.
 * format           the format, supported formats are:
 *                  SYNTH_TYPE_U8
 *                  SYNTH_TYPE_S16
 *                  SYNTH_TYPE_F32
 * return           The new Synth structure.
 */
Synth *synth_new(const char *filename,
                 int opendev,
                 const char *devname,
                 synth_frame_cb_t synth_frame_cb,
                 void *synth_frame_priv,
                 log_cb_return_t log_cb,
                 void *log_priv,
                 unsigned int rate,
                 unsigned int channels,
                 unsigned int fragsize,
                 SynthImportType format);
/*
 * Stop the synth, free any buffers created by it and close the associated
 * SDL_audio device.
 *
 * s        The Synth structure.
 * return   void
 */
void synth_free(Synth *s);
/*
 * Open a WAV file for output on a currently running synthesizer, for recording
 * the output to a file as it's output.
 * s        the Synth structure
 * filename the file to open
 * return   0 on success, -1 on error
 */
int synth_open_wav(Synth *s, const char *filename);
/*
 * Close an open WAV file.  When done, synth_free() should be called, though.
 * s        the Synth structure
 * return   0 on successn -1 on error (although the file will likely have been
 *          closed, but the header might be incomplete.)
 */
int synth_close_wav(Synth *s);
/*
 * Write data to a wav file.  This is used when there is no SDL audio output.
 * synth_frame should be called first and its return value should be passed to
 * this function's samples argumet.
 *
 * d        the Synth structure
 * samples  the number of samples to write
 * return   0 on success, -1 on error, and the file will be closed
 */
int synth_write_wav(Synth *s, unsigned int samples);
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
 * Set the enabled state of the output, 0 to stop the output and non-zero to
 * start it.  Nothing happens other than some internal state being set up.
 * The next call to synth_frame will try to request buffers filled, then start
 * the audio output.
 * This doesn't do anything if there's no device being output to.
 *
 * s        the Synth structure
 * enabled  0 to stop, non-zero to start
 * return   0 on success, -1 on failure, including frame callback failures
 */
int synth_set_enabled(Synth *s, int enabled);
/*
 * Indicate that it's a good time for the frame callback to be run to fill up
 * the buffers.
 *
 * s        the Synth structure
 * return   negative on failure, including frame callback failures
 *          >=0 to indicate amount of samples output
 */
int synth_frame(Synth *s);
/*
 * Invalidate the output buffers.  Data in them already will not be played.
 * Probably best to do this when it's not enabled.  It will lock the audio
 * device while messing with buffer state so it should be safe, though.
 *
 * s        the Synth structure
 * return   void
 */
void synth_invalidate_buffers(Synth *s);
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
 * Get the number of samples available in the output buffers.
 *
 * s        the Synth structure
 * return   the number of samples available
 */
unsigned int synth_samples_available(Synth *s);
/*
 * Mark a certain amount of buffered audio as used/processed and that memory
 * can now be used for more data.
 *
 * s        the Synth structure
 * consumed the amount to mark as consumed
 * return   void
 */
void synth_consume_samples(Synth *s, unsigned int consumed);

/**/

/* Buffer Functions */

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
 * name     optional name or NULL
 * return   the buffer handle or -1 on failure
 */
int synth_add_buffer(Synth *s,
                     SynthImportType type,
                     void *data,
                     unsigned int size,
                     const char *name);
/*
 * Free a buffer and its memory.
 *
 * s        the Synth structure
 * index    the buffer handle index
 * return   0 on success, -1 on failure
 */
int synth_free_buffer(Synth *s, unsigned int index);
/*
 * Get the size in samples of a buffer.
 *
 * s        the Synth structure
 * index    the buffer handle index
 * return   size in samples or -1 on failure
 */
int synth_buffer_get_size(Synth *s, unsigned int index);
/*
 * Get the pointer to the internal buffer data.  This can either be a normal
 * buffer or an output buffer.  Behavior differs a fair bit between the two:
 * Normal buffers will just return the fixed size and pointer to the beginning
 * of the buffer, and their reference count will be increased.
 * Output buffers have no reference counts but may be internally "split" since
 * it's a ring buffer, so to get the full output buffer, this must be called
 * twice, which the first, second, both or neither may return 0 length and a
 * NULL pointer for buf.
 *
 * s        the Synth structure
 * index    the buffer handle index
 * buf      a pointer to a pointer which will be assigned to the pointer to
 *          the buffer.
 * return   size in samples or -1 on failure
 */
int synth_get_internal_buffer(Synth *s, unsigned int index, float **buf);
/*
 * Release the reference to the inernal buffer data.  The buffer data shouldn't
 * be used after this until a new reference is acquired.  Output buffers must
 * be released before audio playback will continue.
 *
 * s        the Synth structure
 * index    the buffer handle index
 * return   0 on success or -1 on failure
 */
int synth_release_buffer(Synth *s, unsigned int index);
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

/**/

/* Player Functions */

/*
 * Create a player.  These control all the input and output of buffers and how
 * they will be played back.
 *
 * s        The Synth structure
 * inBuffer The initial input buffer for the new player
 * name     optional name or NULL
 * return   the new player handle or -1 on failure
 */
int synth_add_player(Synth *s,
                     unsigned int inBuffer,
                     const char *name);
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
 * Negative positions indicate a position from the end.
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
 * integer.  Negative positions indicate a position from the end.
 *
 * s        the Synth structure
 * index    the player index to update
 * outPos   the position to start output from
 * return   0 on success, -1 on failure
 */
int synth_set_player_output_buffer_pos(Synth *s,
                                       unsigned int index,
                                       int outPos);
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
                                 SynthAutoMode volMode);
/*
 * Set the constant player volume.  0.0 to mute, 1.0 for original volume,
 * greater values to amplify, lesser values to make it quieter, negative values
 * to invert, if you really want to.
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
 * Set loop start, or phase source start position.  A negative value indicates
 * an offset from the end.
 * See: synth_set_player_mode
 *
 * s            the Synth structure
 * index        the player index to update
 * loopStart    the starting sample to loop from
 * return       0 on success, -1 on failure
 */
int synth_set_player_loop_start(Synth *s,
                                unsigned int index,
                                int loopStart);
/*
 * Set loop length, or phase source 1.0 value.  A negative value indicates the
 * buffer's end
 * See: synth_set_player_mode
 *
 * s            the Synth structure
 * index        the player index to update
 * loopLength   the length to loop
 * return       0 on success, -1 on failure
 */
int synth_set_player_loop_length(Synth *s,
                                 unsigned int index,
                                 unsigned int loopLength);
/*
 * Set the source buffer for start position automation.
 * See: synth_set_player_volume_source
 *
 * s            the Synth structure
 * index        the player index to update
 * startBuffer  the source buffer
 * return       0 on success, -1 on failure
 */
int synth_set_player_start_source(Synth *s,
                                  unsigned int index,
                                  unsigned int startBuffer);
/*
 * Set the number of discrete values to fall on.
 * See: synth_set_player_start_granularity
 *
 * s            the Synth structure
 * index        the player index to update
 * startValues  the number of values
 * return       0 on success, -1 on failure
 */
int synth_set_player_start_values(Synth *s,
                                  unsigned int index,
                                  unsigned int startValues);
/*
 * Set the positional granularity or distance between values.
 * See: synth_set_player_start_granularity
 *
 * s                    the Synth structure
 * index                the player index to update
 * startGranularity     the distance between values
 * return               0 on success, -1 on failure
 */
int synth_set_player_start_granularity(Synth *s,
                                       unsigned int index,
                                       unsigned int startGranularity);
/*
 * Mode for loop start position automation.
 * See: synth_set_player_mode
 *      synth_set_player_length_mode
 *
 * s            the Synth structure
 * index        the player index to update
 * startMode    the loop start mode
 * return       0 on success, -1 on failure
 */
int synth_set_player_start_mode(Synth *s,
                                unsigned int index,
                                SynthAutoMode startMode);
/*
 * Set the source buffer for length automation.
 * See: synth_set_player_volume_source
 *
 * s            the Synth structure
 * index        the player index to update
 * startBuffer  the source buffer
 * return       0 on success, -1 on failure
 */
int synth_set_player_length_source(Synth *s,
                                   unsigned int index,
                                   unsigned int lengthBuffer);
/*
 * Set the number of discrete values to fall on.
 * See: synth_set_player_length_granularity
 *
 * s                the Synth structure
 * index            the player index to update
 * lengthValues     the number of values
 * return           0 on success, -1 on failure
 */
int synth_set_player_length_values(Synth *s,
                                   unsigned int index,
                                   unsigned int lengthValues);
/*
 * Set the positional granularity or distance between values.
 * See: synth_set_player_length_granularity
 *
 * s                    the Synth structure
 * index                the player index to update
 * lengthGranularity    the distance between values
 * return               0 on success, -1 on failure
 */
int synth_set_player_length_granularity(Synth *s,
                                        unsigned int index,
                                        unsigned int lengthGranularity);
/*
 * Mode for loop length automation.
 * See: synth_set_player_mode
 *      synth_set_player_start_mode
 *
 * s            the Synth structure
 * index        the player index to update
 * startMode    the loop start mode
 * return       0 on success, -1 on failure
 */
int synth_set_player_length_mode(Synth *s,
                                 unsigned int index,
                                 SynthAutoMode lengthMode);
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
 * See: synth_set_player_speed
 *      synth_set_player_volume_mode
 *
 * s            the Synth structure
 * index        the player index to update
 * speedMode    the speed mode
 * return       0 on success, -1 on failure
 */
int synth_set_player_speed_mode(Synth *s,
                                unsigned int index,
                                SynthAutoMode speedMode);
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
/*
 * Determine criteria for why the player stopped.
 * See: SYNTH_STOPPED_*
 *
 * s            the Synth structure
 * index        the player index
 * return       A bitfield of reasons.
 */
int synth_player_stopped_reason(Synth *syn, unsigned int index);

/**/

/* Filter Functions */

/*
 * Create a new filter.
 *
 * s        the Synth structure
 * inBuffer the buffer to apply a filter to
 * size     the size of the filter (cannot be changed)
 * name     optional name or NULL
 * return   the new filter handle or -1 on failure;
 */
int synth_add_filter(Synth *s,
                     unsigned int inBuffer,
                     unsigned int size,
                     const char *name);
/*
 * Free the filter, and any of its memory, see buffer/player for memory
 * management notes.
 * See synth_free_buffer, synth_free_player
 *
 * s        the Synth structure
 * index    the filter handle index to free
 * return   0 on success, -1 on failure
 */
int synth_free_filter(Synth *s, unsigned int index);
/*
 * Reset the filter accumulation state, so if it's started to be used on
 * another buffer, it won't have weird discontinuity from previous processed content.
 *
 * s        the Synth structure
 * index    the filter to reset
 * return   0 on success, -1 on failure
 */
int synth_reset_filter(Synth *s, unsigned int index);
/*
 * Set the buffer to apply a filter to.
 *
 * s        the Synth structure
 * index    the filter to update
 * inBuffer the input buffer index
 * return   0 on success, -1 on failure
 */
int synth_set_filter_input_buffer(Synth *s,
                                  unsigned int index,
                                  unsigned int inBuffer);
/*
 * Sets the starting position on processing the input buffer.
 *
 * s        the Synth structure
 * index    the filter to update
 * inPos    the position in the buffer, in samples
 * return   0 on success, -1 on failure
 */
int synth_set_filter_input_buffer_pos(Synth *s,
                                      unsigned int index,
                                      int inPos);
/*
 * Set the buffer containing the filter kernel(s) this filter should use.
 *
 * s            the Synth structure
 * index        the filter to update
 * filterBuffer the index of the buffer containing filter kernels
 * return       0 on success, -1 on failure
 */
int synth_set_filter_buffer(Synth *s,
                            unsigned int index,
                            unsigned int filterBuffer);
/*
 * Set the position in the buffer where kernel(s) should start to be referenced
 * from.
 *
 * s        the Synth structure
 * index    the filter to update
 * startPos the sample where the filter(s) start
 * return   0 on success, -1 on failure
 */
int synth_set_filter_buffer_start(Synth *s,
                                  unsigned int index,
                                  int startPos);
/*
 * Set the number of consecutive filter kernels starting from the start
 * position which are in the filter buffer.
 *
 * s        the Synth structure
 * index    the filter to update
 * slices   the number of slices
 * return   0 on success, -1 on failure
 */
int synth_set_filter_slices(Synth *s,
                            unsigned int index,
                            unsigned int slices);
/*
 * Set whether the filter slice is a constant value (CONSTANT) or whether a
 * buffer should be read to determine which slice should be used per input
 * sample (SOURCE).
 *
 * s        the Synth structure
 * index    the filter to update
 * mode     the filter mode
 * return   0 on success, -1 on failure
 */
int synth_set_filter_mode(Synth *s,
                          unsigned int index,
                          SynthAutoMode mode);
/*
 * Set the filter slice value to use either in constant mode or the first slice
 * in slice buffer source mode.
 *
 * s        the Synth structure
 * index    the filter to update
 * slice    the slice index
 * return   0 on success, -1 on failure
 */
int synth_set_filter_slice(Synth *s,
                           unsigned int index,
                           int slice);
/*
 * Provide the source buffer for slices, valid values are 0.0 to 1.0,
 * everything else will just wrap between those values.  0.0 will be the Nth
 * filter past startPos and 1.0 will be the last numbered filter slice, and
 * values in between will be which is linearly nearest.  Where N is the first
 * slice value.
 * See: synth_set_filter_slice
 *
 * s            the Synth structure
 * indxx        the filter to update
 * sliceBuffer  The buffer containing the continuous slice selections
 * return       0 on success, -1 on failure
 */
int synth_set_filter_slice_source(Synth *s,
                                  unsigned int index,
                                  unsigned int sliceBuffer);
/*
 * Set the buffer to be output to.
 *
 * s            theSynth structure
 * index        the filter to update
 * outBuffer    the buffer to output to
 * return       0 on success, -1 on failure
 */
int synth_set_filter_output_buffer(Synth *s,
                                   unsigned int index,
                                   unsigned int outBuffer);
/*
 * Set the buffer output position.
 *
 * s        the Synth structure
 * index    the filter to update
 * outPos   the position of the output buffer to output to
 * return   0 on success, -1 on failure
 */
int synth_set_filter_output_buffer_pos(Synth *s,
                                       unsigned int index,
                                       int outPos);
/*
 * Set the filter's output mode.  Either overwrite values in the output buffer
 * (REPLACE) or add/mix them together (ADD).
 *
 * s        the Synth structure
 * index    the filter to update
 * outOp    the output operation
 * return   0 on success, -1 onf ailure
 */
int synth_set_filter_output_mode(Synth *s,
                                 unsigned int index,
                                 SynthOutputOperation outOp);
/*
 * Set the filter's volume mode.  Either a constant value (CONSTANT) or from a
 * source buffer (SOURCE) with the constant value applied.
 *
 * s        the Synth structure
 * index    the filter to update
 * volMode  the volume mode
 * return   0 on success, -1 on failure
 */
int synth_set_filter_volume_mode(Synth *s,
                                 unsigned int index,
                                 SynthAutoMode volMode);
/*
 * Set the filter's output volume.
 * See: synth_set_player_volume
 *
 * s        the Synth structure
 * index    the filter to update
 * vol      the volume
 * return   0 on success, -1 on failure
 */
int synth_set_filter_volume(Synth *s,
                            unsigned int index,
                            float vol);
/*
 * Set the source buffer for the filter output volume.
 *
 * s            the Synth structure
 * index        the filter to update
 * volBuffer    the volume buffer index
 * return       0 on success, -1 on failure
 */
int synth_set_filter_volume_source(Synth *s,
                                   unsigned int index,
                                   unsigned int volBuffer);
/*
 * Run the filter for a certain number of samples.
 *
 * s            the Synth structure
 * index        the filter index to run
 * reqSamples   the number of samples to try to run
 * return       the number of samples which could run or -1 on error
 */
int synth_run_filter(Synth *s,
                     unsigned int index,
                     unsigned int reqSamples);
/*
 * Get the reason why the filter stopped running.
 * See: SYNTH_STOPPED_*
 *
 * syn          the Synth structure
 * index        the index of the filter
 * requested    number of samples requested
 * returned     number of samples returned
 * return       the reason or -1 on failure
 */
int synth_filter_stopped_reason(Synth *syn, unsigned int index);

#endif
