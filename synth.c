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

#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <SDL.h>

#include "synth.h"

#define DEFAULT_RATE (48000)

#define LOG_PRINTF(SYNTH, FMT, ...) \
    log_cb_helper((SYNTH)->log_cb, (SYNTH)->log_priv, \
    FMT, \
    ##__VA_ARGS__)

#define MIN(X, Y) (((X) < (Y)) ? (X) : (Y))

typedef struct {
    float *idxbuf;

    float *data;
    unsigned int size;
    unsigned int ref;

    /* for getting both parts of an output channel buffer */
    int getPart;

    char *name;
} SynthBuffer;

typedef struct {
    unsigned int inUse;

    unsigned int inBuffer;
    unsigned int outBuffer;

    float inPos;
    unsigned int outPos;

    SynthOutputOperation outOp;

    SynthAutoMode volMode;
    float volume;
    unsigned int volBuffer;
    unsigned int volPos;

    SynthPlayerMode mode;
    unsigned int loopStart;
    unsigned int loopEnd;
    unsigned int phaseBuffer;
    unsigned int phasePos;

    SynthAutoMode speedMode;
    float speed;
    unsigned int speedBuffer;
    unsigned int speedPos;

    char *name;
} SynthPlayer;

typedef struct {
    unsigned int size;
    float *accum;
    unsigned int accumPos;

    unsigned int inBuffer;
    unsigned int inPos;

    unsigned int filterBuffer;
    unsigned int startPos;
    unsigned int slices;
    SynthAutoMode mode;
    unsigned int sliceBuffer;
    unsigned int slice;
    unsigned int slicePos;

    unsigned int outBuffer;
    unsigned int outPos;
    SynthOutputOperation outOp;

    SynthAutoMode volMode;
    float vol;
    unsigned int volBuffer;
    unsigned int volPos;

    char *name;
} SynthFilter;

struct Synth_s {
    SDL_AudioDeviceID audiodev;
    unsigned int rate;
    unsigned int fragmentsize;
    unsigned int fragments;
    unsigned int channels;
    SynthBuffer *channelbuffer;
    unsigned long reffedchannels;
    unsigned int readcursor;
    unsigned int writecursor;
    unsigned int bufferfilled;
    unsigned int buffersize;
    int underrun;
    SynthState state;
    SDL_AudioCVT converter;
    Uint8 silence;

    synth_frame_cb_t synth_frame_cb;
    void *synth_frame_priv;

    SDL_AudioCVT U8toF32;
    SDL_AudioCVT S16toF32;

    SynthBuffer *buffer;
    unsigned int buffersmem;

    SynthPlayer *player;
    unsigned int playersmem;

    SynthFilter *filter;
    unsigned int filtersmem;

    FILE *out;
    SynthImportType format;
    unsigned int written;
    Uint8 *outbuf;

    log_cb_return_t log_cb;
    void *log_priv;
};

static const char *NONAME = "(unnamed)";
static const char *CHANNEL_PREFIX = "Channel";

SynthImportType synth_type_from_audioformat(SDL_AudioFormat format) {
    switch(format) {
        case AUDIO_U8:
            return(SYNTH_TYPE_U8);
            break;
        case AUDIO_S16SYS:
            return(SYNTH_TYPE_S16);
            break;
        case AUDIO_F32SYS:
            return(SYNTH_TYPE_F32);
            break;
        default:
            break;
    }
    return(SYNTH_TYPE_INVALID);
}

SDL_AudioFormat synth_audioformat_from_type(SynthImportType type) {
    switch(type) {
        case SYNTH_TYPE_U8:
            return(AUDIO_U8);
            break;
        case SYNTH_TYPE_S16:
            return(AUDIO_S16SYS);
            break;
        case SYNTH_TYPE_F32:
            return(AUDIO_F32SYS);
            break;
        default:
            break;
    }
    /* 0 should indicate a sample bit size of 0 which is probably
     * impossible */
    return(0);
}

int synth_buffer_from_wav(Synth *s,
                          const char *filename,
                          unsigned int *rate,
                          const char *name) {
    SDL_AudioSpec spec;
    Uint8 *audiobuf;
    Uint32 len;
    SynthImportType type;
    int sb;

    if(name == NULL) {
        name = filename;
    }

    if(SDL_LoadWAV(filename, &spec, &audiobuf, &len) == NULL) {
        LOG_PRINTF(s, "%s: Failed to load WAV file.\n", name);
        return(-1);
    }

    if(spec.channels != 1) {
        LOG_PRINTF(s, "%s: Buffers are mono.\n", name);
        SDL_FreeWAV(audiobuf);
        return(-1);
    }

    type = synth_type_from_audioformat(spec.format);
    if(type == SYNTH_TYPE_INVALID) {
        LOG_PRINTF(s, "%s: Unsupported format.\n", name);
        SDL_FreeWAV(audiobuf);
        return(-1);
    }

    len = len / (SDL_AUDIO_BITSIZE(spec.format) / 8);

    sb = synth_add_buffer(s, type, audiobuf, len, name);
    if(rate != NULL) {
        *rate = spec.freq;
    }
    SDL_FreeWAV(audiobuf);

    return(sb);
}

#define PRINT_BUFFER_STATS(BUF) \
    if((BUF).data != NULL) { \
        LOG_PRINTF(s, " Name: %s\n", (BUF).name); \
    } \
    LOG_PRINTF(s, " Size: %u\n", (BUF).size); \
    LOG_PRINTF(s, " Refcount: %u\n", (BUF).ref);

#define PRINT_OUTPUT_OPERATION(OUTOP) \
    LOG_PRINTF(s, " Output Operation: "); \
    switch((OUTOP)) { \
        case SYNTH_OUTPUT_REPLACE: \
            LOG_PRINTF(s, "Replace\n"); \
            break; \
        case SYNTH_OUTPUT_ADD: \
            LOG_PRINTF(s, "Add/Mix\n"); \
            break; \
        default: \
            LOG_PRINTF(s, "Invalid\n");\
    }

#define PRINT_AUTO_MODE(AUTOMODE) \
    switch((AUTOMODE)) { \
        case SYNTH_AUTO_CONSTANT: \
            LOG_PRINTF(s, "Constant\n"); \
            break; \
        case SYNTH_AUTO_SOURCE: \
            LOG_PRINTF(s, "Source/Modulate\n"); \
            break; \
        default: \
            LOG_PRINTF(s, "Invalid\n"); \
    }

#define PRINT_PLAYER_STATS(PLR) \
    LOG_PRINTF(s, " In Use: "); \
    if((PLR).inUse) { \
        LOG_PRINTF(s, "Yes\n"); \
        LOG_PRINTF(s, "Name: %s\n", (PLR).name); \
    } else { \
        LOG_PRINTF(s, "No\n"); \
    } \
    LOG_PRINTF(s, " Input Buffer: %u\n", (PLR).inBuffer); \
    LOG_PRINTF(s, " Output Buffer: %u\n", (PLR).outBuffer); \
    LOG_PRINTF(s, " Input Buffer Pos: %f\n", (PLR).inPos); \
    LOG_PRINTF(s, " Output Buffer Pos: %u\n", (PLR).outPos); \
    PRINT_OUTPUT_OPERATION((PLR).outOp) \
    LOG_PRINTF(s, " Volume Mode: "); \
    PRINT_AUTO_MODE((PLR).volMode) \
    LOG_PRINTF(s, " Volume: %f\n", (PLR).volume); \
    LOG_PRINTF(s, " Volume Source Buffer: %u\n", (PLR).volBuffer); \
    LOG_PRINTF(s, " Volume Source Buffer Pos: %u\n", (PLR).volPos); \
    LOG_PRINTF(s, " Player Mode: "); \
    switch((PLR).mode) { \
        case SYNTH_MODE_ONCE: \
            LOG_PRINTF(s, "Play Once\n"); \
            break; \
        case SYNTH_MODE_LOOP: \
            LOG_PRINTF(s, "Loop\n"); \
            break; \
        case SYNTH_MODE_PHASE_SOURCE: \
            LOG_PRINTF(s, "Source/Modulate\n"); \
            break; \
        default: \
            LOG_PRINTF(s, "Invalid\n"); \
    } \
    LOG_PRINTF(s, " Loop Start: %u\n", (PLR).loopStart); \
    LOG_PRINTF(s, " Loop End: %u\n", (PLR).loopEnd); \
    LOG_PRINTF(s, " Phase Source Buffer: %u\n", (PLR).phaseBuffer); \
    LOG_PRINTF(s, " Phase Source Buffer Pos: %u\n", (PLR).phasePos); \
    LOG_PRINTF(s, " Speed Mode: "); \
    PRINT_AUTO_MODE((PLR).speedMode) \
    LOG_PRINTF(s, " Speed: %f\n", (PLR).speed); \
    LOG_PRINTF(s, " Speed Source Buffer: %u\n", (PLR).speedBuffer); \
    LOG_PRINTF(s, " Speed Source Buffer Pos: %u\n", (PLR).speedPos);

#define PRINT_FILTER_STATS(FLT) \
    if((FLT).accum != NULL) { \
        LOG_PRINTF(s, " Name: %s\n", (FLT).name); \
    } \
    LOG_PRINTF(s, " Size: %u\n", (FLT).size); \
    LOG_PRINTF(s, " Accumulator Position: %u\n", (FLT).accumPos); \
    LOG_PRINTF(s, " Input Buffer: %u\n", (FLT).inBuffer); \
    LOG_PRINTF(s, " Input Buffer Position: %u\n", (FLT).inPos); \
    LOG_PRINTF(s, " Filter Buffer: %u\n", (FLT).filterBuffer); \
    LOG_PRINTF(s, " Filter Start Position: %u\n", (FLT).startPos); \
    LOG_PRINTF(s, " Filter Slices: %u\n", (FLT).slices); \
    LOG_PRINTF(s, " Filter Mode: "); \
    PRINT_AUTO_MODE((FLT).mode) \
    LOG_PRINTF(s, " Slice Buffer: %u\n", (FLT).sliceBuffer); \
    LOG_PRINTF(s, " Slice: %u\n", (FLT).slice); \
    LOG_PRINTF(s, " Slice Buffer Position: %u\n", (FLT).slicePos); \
    LOG_PRINTF(s, " Output Buffer: %u\n", (FLT).outBuffer); \
    LOG_PRINTF(s, " Output Buffer Position: %u\n", (FLT).outPos); \
    PRINT_OUTPUT_OPERATION((FLT).outOp) \
    LOG_PRINTF(s, " Volume Mode: "); \
    PRINT_AUTO_MODE((FLT).volMode) \
    LOG_PRINTF(s, " Volume: %f\n", (FLT).vol); \
    LOG_PRINTF(s, " Volume Buffer: %u\n", (FLT).volBuffer); \
    LOG_PRINTF(s, " Volume Buffer Position: %u\n", (FLT).volPos);

void synth_print_full_stats(Synth *s) {
    unsigned int i;

    if(s->log_cb == NULL) {
        return;
    }

    LOG_PRINTF(s, "SDL audio device ID: %u\n", s->audiodev);
    LOG_PRINTF(s, "Audio rate: %u\n", s->rate);
    LOG_PRINTF(s, "Channels: %u\n", s->channels);
    for(i = 0; i < s->channels; i++) {
        LOG_PRINTF(s, "Channel %u Buffer Size: %u\n", i, s->channelbuffer[i].size);
    }
    LOG_PRINTF(s, "Read Cursor Pos: %u\n", s->readcursor);
    LOG_PRINTF(s, "Write Cursor Pos: %u\n", s->writecursor);
    LOG_PRINTF(s, "Buffer Filled: %u\n", s->bufferfilled);
    LOG_PRINTF(s, "Buffer Total Size: %u\n", s->buffersize);
    LOG_PRINTF(s, "Has Underrun Since Last Reset: ");
    if(s->underrun) {
        LOG_PRINTF(s, "Yes\n");
    } else {
        LOG_PRINTF(s, "No\n");
    }
    LOG_PRINTF(s, "Synth State: ");
    switch(s->state) {
        case SYNTH_STOPPED:
            LOG_PRINTF(s, "Stopped\n");
            break;
        case SYNTH_ENABLED:
            LOG_PRINTF(s, "Enabled/Pending\n");
            break;
        case SYNTH_RUNNING:
            LOG_PRINTF(s, "Running\n");
            break;
        default:
            LOG_PRINTF(s, "Invalid\n");
    }
    LOG_PRINTF(s, "Buffers Memory: %u\n", s->buffersmem);
    for(i = 0; i < s->buffersmem; i++) {
        if(s->buffer[i].data != NULL) {
            LOG_PRINTF(s, "Buffer %u (%u):\n", i, i + s->channels);
            PRINT_BUFFER_STATS(s->buffer[i]);
        }
    }
    LOG_PRINTF(s, "Players Memory: %u\n", s->playersmem);
    for(i = 0; i < s->playersmem; i++) {
        if(s->player[i].inUse != 0) {
            LOG_PRINTF(s, "Player %u:\n", i);
            PRINT_PLAYER_STATS(s->player[i]);
        }
    }
    LOG_PRINTF(s, "Filters Memory: %u\n", s->filtersmem);
    for(i = 0; i < s->filtersmem; i++) {
        if(s->filter[i].accum != NULL) {
            LOG_PRINTF(s, "Filter %u:\n", i);
            PRINT_FILTER_STATS(s->filter[i]);
        }
    }
}

#undef PRINT_FILTER_STATS
#undef PRINT_PLAYER_STATS
#undef PRINT_AUTO_MODE
#undef PRINT_OUTPUT_OPERATION
#undef PRINT_BUFFER_STATS

unsigned int synth_get_samples_needed(Synth *s) {
    if(s->readcursor == s->writecursor) {
        if(s->bufferfilled == s->buffersize) {
            return(0);
        } else {
            return(s->buffersize);
        }
    } else if(s->writecursor < s->readcursor) {
        return(s->readcursor - s->writecursor);
    } else { /* s->writecursor > s->readcursor */
        return(s->buffersize - s->writecursor + s->readcursor);
    }
}

static void add_samples(Synth *s, unsigned int added) {
    s->writecursor += added;
    if(s->writecursor >= s->buffersize) {
        s->writecursor -= s->buffersize;
    }
    s->bufferfilled += added;
}

unsigned int synth_samples_available(Synth *s) {
    if(s->readcursor == s->writecursor) {
        if(s->bufferfilled == s->buffersize) {
            return(s->buffersize);
        } else {
            return(0);
        }
    } else if(s->readcursor < s->writecursor) {
        return(s->writecursor - s->readcursor);
    } else { /* s->readcursor > s->writecursor */
        return(s->buffersize - s->readcursor);
    }
}

void synth_consume_samples(Synth *s, unsigned int consumed) {
    s->readcursor += consumed;
    if(s->readcursor == s->buffersize) {
        s->readcursor = 0;
    }
    s->bufferfilled -= consumed;
}

/* big ugly, overcomplicated function, but hopefully it isolates most of the
 * complexity in one place. */
static void do_synth_audio_cb(Synth *s, Uint8 *stream, unsigned int todo) {
    unsigned int i, j;

    if(s->channels == 1) {
        Uint8 *mono = (Uint8 *)&(s->channelbuffer[0].data[s->readcursor]);

        /* convert in-place, because it can only be shrunken from 32 bits to
         * 16 bits, or just left as-is as 32 bits. */
        s->converter.len = todo * sizeof(float);
        s->converter.buf = mono;
        /* ignore return value because the documentation indicates the only
         * fail state is that buf is NULL, which it won't be. */
        SDL_ConvertAudio(&(s->converter));

        /* copy what has been converted */
        memcpy(stream, mono,
               todo * SDL_AUDIO_BITSIZE(s->converter.dst_format) / 8);

        /* clear the source buffer with silence */
        memset(mono, s->silence, todo * sizeof(float));
    } else if(s->channels == 2) { /* hopefully faster stereo code path */
        Uint8 *left = (Uint8 *)&(s->channelbuffer[0].data[s->readcursor]);
        Uint8 *right = (Uint8 *)&(s->channelbuffer[1].data[s->readcursor]);
        /* much like mono, just do it to both channels and zipper them in to
         * the output */
        s->converter.len = todo * sizeof(float);
        s->converter.buf = left;
        SDL_ConvertAudio(&(s->converter));
        s->converter.buf = right;
        SDL_ConvertAudio(&(s->converter));

        /* this is probably slow */
        if(SDL_AUDIO_BITSIZE(s->converter.dst_format) == 32) {
            Sint32 *left32 = (Sint32 *)left;
            Sint32 *right32 = (Sint32 *)right;
            for(i = 0; i < todo; i++) {
                ((Sint32 *)stream)[i * 2]     = left32[i];
                ((Sint32 *)stream)[i * 2 + 1] = right32[i];
            }
        } else if(SDL_AUDIO_BITSIZE(s->converter.dst_format) == 16) {
            Sint16 *left16 = (Sint16 *)left;
            Sint16 *right16 = (Sint16 *)right;
            for(i = 0; i < todo; i++) {
                ((Sint16 *)stream)[i * 2] =     left16[i];
                ((Sint16 *)stream)[i * 2 + 1] = right16[i];
            }
        } else { /* 8, very unlikely */
            for(i = 0; i < todo; i++) {
                stream[i * 2] =     left[i];
                stream[i * 2 + 1] = right[i];
            }
        }

        memset(left, s->silence, todo * sizeof(float));
        memset(right, s->silence, todo * sizeof(float));
    } else { /* unlikely case it's multichannel surround ... */
        /* much like stereo, but use a loop because i don't feel like making
         * a bunch of unrolled versions of this unless surround sound becomes
         * something frequently used with this.. */
        Uint8 *bufs[s->channels];

        s->converter.len = todo * sizeof(float);
        for(i = 0; i < s->channels; i++) {
            bufs[i] = (Uint8 *)&(s->channelbuffer[i].data[s->readcursor]);
            s->converter.buf = bufs[i];
            SDL_ConvertAudio(&(s->converter));
        }
        /* this is probably very slow, and very untested */
        if(SDL_AUDIO_BITSIZE(s->converter.dst_format) == 32) {
            for(i = 0; i < s->channels; i++) {
                Sint32 *buf = (Sint32 *)bufs[i];
                for(j = 0; j < todo; j++) {
                    ((Sint32 *)stream)[j * s->channels + i] = buf[j];
                }
            }
        } else if(SDL_AUDIO_BITSIZE(s->converter.dst_format) == 16) {
            for(i = 0; i < s->channels; i++) {
                Sint16 *buf = (Sint16 *)bufs[i];
                for(j = 0; j < todo; j++) {
                    ((Sint16 *)stream)[j * s->channels + i] = buf[j];
                }
            }
        } else { /* 8 */
            for(i = 0; i < s->channels; i++) {
                for(j = 0; j < todo; j++) {
                    stream[j * s->channels + i] = bufs[i][j];
                }
            }
        }

        for(i = 0; i < s->channels; i++) {
            memset(bufs[i], s->silence, todo * sizeof(float));
        }
    }

    if(s->out != NULL) {
        unsigned int towrite;
        switch(SDL_AUDIO_BITSIZE(s->converter.dst_format)) {
            case 32:
                towrite = todo * s->channels * sizeof(float);
                break;
            case 16:
                towrite = todo * s->channels * sizeof(int16_t);
                break;
            default:
                towrite = todo * s->channels * sizeof(uint8_t);
        }

        if(fwrite(stream, towrite, 1, s->out) < 1) {
            fclose(s->out);
            s->out = NULL;
        }
        s->written += towrite;
    }

    synth_consume_samples(s, todo);
}

static void synth_audio_cb(void *userdata, Uint8 *stream, int len) {
    Synth *s = (Synth *)userdata;
    unsigned int available = synth_samples_available(s);
    unsigned int todo;
    /* get number of samples */
    unsigned int samsize = (SDL_AUDIO_BITSIZE(s->converter.dst_format) / 8) * s->channels;
    unsigned int length = len / samsize;

    if(available == 0) {
        s->underrun = 1;
        return;
    }

    todo = MIN(length, available);
    do_synth_audio_cb(s, stream, todo);
    length -= todo;

    if(length > 0) {
        stream = &(stream[todo * samsize]);
        available = synth_samples_available(s);
        todo = MIN(length, available);
        do_synth_audio_cb(s, stream, todo);
        length -= todo;

        if(length > 0) {
            /* SDL audio requested more, but there is no more,
             * underrun. */
            s->underrun = 1;
        }
    }
}

static int audiodev_is_open(Synth *s) {
    if(s->audiodev >= 2) {
        return(1);
    }

    return(0);
}

static void lock_audiodev(Synth *s) {
    if(audiodev_is_open(s)) {
        SDL_LockAudioDevice(s->audiodev);
    }
}

static void unlock_audiodev(Synth *s) {
    if(audiodev_is_open(s)) {
        SDL_UnlockAudioDevice(s->audiodev);
    }
}

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
                 SynthImportType format) {
    SDL_AudioSpec desired, obtained;
    Synth *s;

    s = malloc(sizeof(Synth));
    if(s == NULL) {
        log_cb(log_priv, "Failed to allocate synth.\n");
        return(NULL);
    }

    s->log_cb = log_cb;
    s->log_priv = log_priv;
    s->audiodev = 0;

    desired.format = synth_audioformat_from_type(format);
    if(desired.format == 0) {
        LOG_PRINTF(s, "Invalid SynthImportType.\n");
        goto error;
    }

    desired.freq = rate;
    /* Stereo should be fine for most things but technically surround is
     * supported and in theory this should create additional audio sinks for
     * all the surround channels.  Untested. */
    desired.channels = channels;
    desired.samples = fragsize;
    desired.callback = synth_audio_cb;
    desired.userdata = s;
    if(opendev) {
        s->audiodev = SDL_OpenAudioDevice(devname,
                                          0,
                                          &desired,
                                          &obtained,
                                          SDL_AUDIO_ALLOW_ANY_CHANGE);
        if(!audiodev_is_open(s)) {
            LOG_PRINTF(s, "Failed to open SDL audio: %s.\n", SDL_GetError());
            goto error;
        }
    } else {
        memcpy(&obtained, &desired, sizeof(SDL_AudioSpec));
    }

    /* probably impossible, but there are cases where at least one output
     * buffer is assumed, so I guess make it clear that there must be at least
     * 1. */
    if(obtained.channels < 1) {
        LOG_PRINTF(s, "No channels?\n");
        goto error;
    }

    switch(SDL_AUDIO_BITSIZE(obtained.format)) {
        case 32:
            if(!SDL_AUDIO_ISFLOAT(obtained.format)) {
                LOG_PRINTF(s, "32 bit integer output format isn't supported.\n");
                goto error;
            }
            s->format = SYNTH_TYPE_F32;
            break;
        case 16:
            s->format = SYNTH_TYPE_S16;
            break;
        case 8:
            s->format = SYNTH_TYPE_U8;
            break;
        default:
            LOG_PRINTF(s, "Unsupported format size: %d.\n",
                            SDL_AUDIO_BITSIZE(obtained.format));
            goto error;
    }

    /* just use the obtained spec for frequency but try to convert the format.
     * Specify mono because the buffers are separate until the end. */
    if(SDL_BuildAudioCVT(&(s->converter),
                         desired.format,  1, obtained.freq,
                         obtained.format, 1, obtained.freq) < 0) {
        LOG_PRINTF(s, "Can't create audio output converter.\n");
        goto error;
    }

    /* create converters now for allowing import later */
    if(SDL_BuildAudioCVT(&(s->U8toF32),
                         AUDIO_U8,    1, obtained.freq,
                         AUDIO_F32SYS, 1, obtained.freq) < 0) {
        LOG_PRINTF(s, "Failed to build U8 import converter.\n");
        goto error;
    }
    if(SDL_BuildAudioCVT(&(s->S16toF32),
                         AUDIO_S16SYS, 1, obtained.freq,
                         AUDIO_F32SYS, 1, obtained.freq) < 0) {
        LOG_PRINTF(s, "Failed to build S16 import converter.\n");
        goto error;
    }

    if(filename != NULL) {
        if(synth_open_wav(s, filename) < 0) {
            goto error;
        }
    }

    s->out = NULL;
    s->outbuf = NULL;
    s->rate = obtained.freq;
    s->fragmentsize = obtained.samples;
    s->fragments = 0;
    s->channels = obtained.channels;
    s->silence = obtained.silence;
    /* Won't know what size to allocate to them until the user has set a number of fragments */
    s->channelbuffer = NULL;
    s->reffedchannels = 0;
    s->buffer = NULL;
    s->buffersmem = 0;
    s->player = NULL;
    s->playersmem = 0;
    s->filter = NULL;
    s->filtersmem = 0;
    s->underrun = 0;
    s->state = SYNTH_STOPPED;
    s->synth_frame_cb = synth_frame_cb;
    s->synth_frame_priv = synth_frame_priv;

    return(s);
error:
    if(audiodev_is_open(s)) {
        SDL_CloseAudioDevice(s->audiodev);
    }

    free(s);

    return(NULL);
}

void synth_free(Synth *s) {
    unsigned int i;

    if(audiodev_is_open(s)) {
        SDL_LockAudioDevice(s->audiodev);
        SDL_CloseAudioDevice(s->audiodev);
    }

    if(s->channelbuffer != NULL) {
        for(i = 0; i < s->channels; i++) {
            if(s->channelbuffer[i].data != NULL) {
                free(s->channelbuffer[i].data);
            }
            if(s->channelbuffer[i].name != NULL) {
                free(s->channelbuffer[i].name);
            }
        }
        free(s->channelbuffer);
    }

    if(s->buffer != NULL) {
        free(s->buffer);
    }

    if(s->player != NULL) {
        free(s->player);
    }

    if(s->filter != NULL) {
        free(s->filter);
    }

    if(s->out != NULL) {
        synth_close_wav(s);
    }

    if(s->outbuf != NULL) {
        free(s->outbuf);
    }

    free(s);
}

static int allocate_outbuf(Synth *s) {
    unsigned int formatbytes;

    if(s->fragments == 0) {
        LOG_PRINTF(s, "Fragments must be set first.\n");
        fclose(s->out);
        s->out = NULL;
        return(-1);
    }

    switch(s->format) {
        case SYNTH_TYPE_U8:
            formatbytes = sizeof(uint8_t);
            break;
        case SYNTH_TYPE_S16:
            formatbytes = sizeof(int16_t);
            break;
        case SYNTH_TYPE_F32:
            formatbytes = sizeof(float);
            break;
        default:
            LOG_PRINTF(s, "Unsupported WAV output format.\n");
            return(-1);
    }

    s->outbuf = malloc(s->channels * formatbytes * s->fragments * s->fragmentsize);
    if(s->outbuf == NULL) {
        LOG_PRINTF(s, "Failed to allocate file output buffer.\n");
        fclose(s->out);
        s->out = NULL;
        return(-1);
    }

    return(0);
}

static const char RIFF[] = {'R', 'I', 'F', 'F'};
static const int32_t RIFF_INIT_SIZE = 0;
static const unsigned int RIFF_HEADER_PCM_SIZE = 36;
static const unsigned int RIFF_HEADER_FLOAT_SIZE = 50;
static const unsigned int RIFF_SIZE_POS = 4;
static const char WAVE[] = {'W', 'A', 'V', 'E'};
static const char WAVE_fmt[] = {'f', 'm', 't', ' '};
static const uint32_t WAVE_fmt_PCM_LEN = 16;
static const uint32_t WAVE_fmt_FLOAT_LEN = 18;
static const uint16_t WAVE_PCM_TYPE = 1;
static const uint16_t WAVE_FLOAT_TYPE = 3;
static const uint16_t WAVE_FLOAT_EXTENSION_LEN = 0;
static const char WAVE_fact[] = {'f', 'a', 'c', 't'};
static const uint32_t WAVE_fact_LEN = 4;
static const unsigned int WAVE_fact_SIZE_POS = 46;
static const char WAVE_data[] = {'d', 'a', 't', 'a'};
static const unsigned int WAVE_data_SIZE_PCM_POS = 40;
static const unsigned int WAVE_data_SIZE_FLOAT_POS = 54;

#define WAVE_WRITE_FIELD(NAME) \
    if(fwrite((NAME), sizeof(NAME), 1, out) < 1) { \
        LOG_PRINTF(s, "Failed to write field "#NAME".\n"); \
        goto error; \
    }

#define WAVE_WRITE_FIELD_PTR(NAME) \
    if(fwrite(&(NAME), sizeof(NAME), 1, out) < 1) { \
        LOG_PRINTF(s, "Failed to write field "#NAME".\n"); \
        goto error; \
    }

int synth_open_wav(Synth *s, const char *filename) {
    uint16_t formatbits;
    uint16_t bytespersample;
    uint32_t bytespersecond;
    int formatbytes;
    uint16_t channels;
    FILE *out;

    if(s->out != NULL) {
        LOG_PRINTF(s, "Synth already has a wav file open\n");
        return(-1);
    }

    switch(s->format) {
        case SYNTH_TYPE_U8:
            formatbytes = sizeof(uint8_t);
            break;
        case SYNTH_TYPE_S16:
            formatbytes = sizeof(int16_t);
            break;
        case SYNTH_TYPE_F32:
            formatbytes = sizeof(float);
            break;
        default:
            LOG_PRINTF(s, "Unsupported WAV output format.\n");
            return(-1);
    }
    formatbits = formatbytes * 8;
    bytespersample = formatbytes * s->channels;
    bytespersecond = bytespersample * s->rate;
    channels = s->channels;

    out = fopen(filename, "wb");
    if(out == NULL) {
        LOG_PRINTF(s, "Failed to open %s for writing.\n", filename);
        return(-1);
    }

    WAVE_WRITE_FIELD(RIFF)
    WAVE_WRITE_FIELD_PTR(RIFF_INIT_SIZE)
    WAVE_WRITE_FIELD(WAVE)
    WAVE_WRITE_FIELD(WAVE_fmt)
    if(s->format == SYNTH_TYPE_F32) {
        WAVE_WRITE_FIELD_PTR(WAVE_fmt_FLOAT_LEN)
        WAVE_WRITE_FIELD_PTR(WAVE_FLOAT_TYPE)
    } else {
        WAVE_WRITE_FIELD_PTR(WAVE_fmt_PCM_LEN)
        WAVE_WRITE_FIELD_PTR(WAVE_PCM_TYPE)
    }
    WAVE_WRITE_FIELD_PTR(channels)
    WAVE_WRITE_FIELD_PTR(s->rate)
    WAVE_WRITE_FIELD_PTR(bytespersecond)
    WAVE_WRITE_FIELD_PTR(bytespersample)
    WAVE_WRITE_FIELD_PTR(formatbits)
    if(s->format == SYNTH_TYPE_F32) {
        WAVE_WRITE_FIELD_PTR(WAVE_FLOAT_EXTENSION_LEN);
        WAVE_WRITE_FIELD(WAVE_fact);
        WAVE_WRITE_FIELD_PTR(WAVE_fact_LEN);
        WAVE_WRITE_FIELD_PTR(RIFF_INIT_SIZE);
    }
    WAVE_WRITE_FIELD(WAVE_data);
    WAVE_WRITE_FIELD_PTR(RIFF_INIT_SIZE);

    if(!audiodev_is_open(s)) {
        if(allocate_outbuf(s) < 0) {
            return(-1);
        }
    }

    s->written = 0;
    s->out = out;

    return(0);

error:
    fclose(out);
    out = NULL;

    return(-1);
}

#define WAVE_SEEK_POS(POS) \
    if(fseek(out, POS, SEEK_SET) < 0) { \
        LOG_PRINTF(s, "Failed to seek to field NAME.\n"); \
        goto error; \
    }

int synth_close_wav(Synth *s) {
    uint32_t riffsize;
    FILE *out = s->out;

    /* lock the audio device to make sure nothing's fighting to write to the
     * file */
    lock_audiodev(s);

    WAVE_SEEK_POS(RIFF_SIZE_POS)

    if(s->format == SYNTH_TYPE_F32) {
        riffsize = RIFF_HEADER_FLOAT_SIZE + s->written;
    } else {
        riffsize = RIFF_HEADER_PCM_SIZE + s->written;
    }
    WAVE_WRITE_FIELD_PTR(riffsize);

    if(s->format == SYNTH_TYPE_F32) {
        WAVE_SEEK_POS(WAVE_fact_SIZE_POS)
        WAVE_WRITE_FIELD_PTR(s->written)
        WAVE_SEEK_POS(WAVE_data_SIZE_FLOAT_POS)
        WAVE_WRITE_FIELD_PTR(s->written)
    } else {
        WAVE_SEEK_POS(WAVE_data_SIZE_PCM_POS)
        WAVE_WRITE_FIELD_PTR(s->written)
    }

    if(!audiodev_is_open(s)) {
        free(s->outbuf);
        s->outbuf = NULL;
    }
    fclose(s->out);
    s->out = NULL;

    unlock_audiodev(s);

    return(0);
error:
    if(!audiodev_is_open(s)) {
        free(s->outbuf);
        s->outbuf = NULL;
    }

    fclose(s->out);
    s->out = NULL;

    unlock_audiodev(s);

    return(-1);
}

#undef WAVE_SEEK_POS
#undef WAVE_WRITE_FIELD_PTR
#undef WAVE_WRITE_FIELD

int synth_write_wav(Synth *s, unsigned int samples) {
    do_synth_audio_cb(s, s->outbuf, samples);
    /* file will be closed on error */
    if(s->out == NULL) {
        return(-1);
    }

    return(0);
}

unsigned int synth_get_rate(Synth *s) {
    return(s->rate);
}

unsigned int synth_get_channels(Synth *s) {
    return(s->channels);
}

unsigned int synth_get_fragment_size(Synth *s) {
    return(s->fragmentsize);
}

int synth_has_underrun(Synth *s) {
    if(s->underrun == 0) {
        return(0);
    }

    s->underrun = 0;
    return(1);
}

int synth_set_enabled(Synth *s, int enabled) {
    if(!audiodev_is_open(s)) {
        LOG_PRINTF(s, "Audio doesn't need to be enabled for wave output only mode.\n");
        return(0);
    }

    if(enabled == 0) {
        SDL_PauseAudioDevice(s->audiodev, 1);
        s->state = SYNTH_STOPPED;
    } else {
        if(s->channelbuffer == NULL) {
            LOG_PRINTF(s, "Audio buffers haven't been set up.  Set fragment "
                          "count first.\n");
            return(-1);
        }

        /* signal to enable */
        s->state = SYNTH_ENABLED;
    }

    return(0);
}

int synth_frame(Synth *s) {
    unsigned int needed;
    /* if needed is 0, got should be 0 */
    int got = 0;

    if(!audiodev_is_open(s)) {
        if(s->outbuf == NULL) {
            LOG_PRINTF(s, "Set a number of fragments first.\n");
            return(-1);
        }

        got = s->synth_frame_cb(s->synth_frame_priv, s);
        if(got < 0) {
            return(got);
        }
        add_samples(s, got);
    } else {
        needed = synth_get_samples_needed(s);
        if(needed > 0) {
            lock_audiodev(s);
            got = s->synth_frame_cb(s->synth_frame_priv, s);
            if(got < 0) {
                unlock_audiodev(s);
                return(got);
            }
            add_samples(s, got);
            unlock_audiodev(s);
        }

        if(s->state == SYNTH_ENABLED) {
            SDL_PauseAudioDevice(s->audiodev, 0);
            s->state = SYNTH_RUNNING;
        }
    }

    return(got);
}

void synth_invalidate_buffers(Synth *s) {
    lock_audiodev(s);

    s->bufferfilled = 0;
    s->readcursor = 0;
    s->writecursor = 0;
    s->underrun = 0;

    unlock_audiodev(s);
}

int synth_set_fragments(Synth *s, unsigned int fragments) {
    int i;

    if(fragments == 0) {
        return(-1);
    }
    
    if(s->state != SYNTH_STOPPED) {
        LOG_PRINTF(s, "Synth must be stopped before changing fragment size.\n");
        return(-1);
    }

    /* true on on subsequent setups */
    if(s->channelbuffer != NULL) {
        if(s->fragments != fragments) {
            for(i = 0; (unsigned int)i < s->channels; i++) {
                free(s->channelbuffer[i].data);
                free(s->channelbuffer[i].name);
            }
            free(s->channelbuffer);
            s->channelbuffer = NULL;
        } else {
            /* nothing to do */
            return(0);
        }
    }

    /* true on first and subsequent setups */
    if(s->channelbuffer == NULL) {
        s->channelbuffer = malloc(sizeof(SynthBuffer) * s->channels);
        if(s->channelbuffer == NULL) {
            LOG_PRINTF(s, "Failed to allocate channel buffers.\n");
            goto error;
        }
        for(i = 0; (unsigned int)i < s->channels; i++) {
            s->channelbuffer[i].data = NULL;
            s->channelbuffer[i].name = NULL;
        }
    }

    s->fragments = fragments;
    s->buffersize = s->fragmentsize * fragments;
    for(i = 0; (unsigned int)i < s->channels; i++) {
        s->channelbuffer[i].size = s->buffersize;
        s->channelbuffer[i].data =
            malloc(sizeof(float) * s->buffersize);
        if(s->channelbuffer[i].data == NULL) {
            LOG_PRINTF(s, "Failed to allocate channel buffer memory.\n");
            goto error;
        }
        memset(s->channelbuffer[i].data, 0, sizeof(float) * s->buffersize);

        s->channelbuffer[i].name = malloc(strlen(CHANNEL_PREFIX) + 4 + 1);
        if(s->channelbuffer[i].name == NULL) {
            LOG_PRINTF(s, "Failed to allocate memory for channel name.\n");
            goto error;
        }
        snprintf(s->channelbuffer[i].name, strlen(CHANNEL_PREFIX) + 4 + 1, "%s%04u", CHANNEL_PREFIX, i);
    }

    if(s->outbuf != NULL) {
        free(s->outbuf);
        s->outbuf = NULL;
    }

    if(!audiodev_is_open(s)) {
        if(allocate_outbuf(s) < 0) {
            goto error;
        }
    }

    synth_invalidate_buffers(s);

    return(0);

error:
    for(i = 0; i < (int)s->channels; i++) {
        if(s->channelbuffer[i].data != NULL) {
            free(s->channelbuffer[i].data);
        }
        if(s->channelbuffer[i].name != NULL) {
            free(s->channelbuffer[i].name);
        }
    }
    free(s->channelbuffer);
    s->channelbuffer = NULL;
    /* can't be enabled */
    s->fragments = 0;

    return(-1);
}

static int init_buffer(Synth *s,
                       SynthBuffer *b,
                       SynthImportType type,
                       void *data,
                       unsigned int size,
                       const char *name) {
    unsigned int i;

    b->size = size;
    b->data = malloc(size * sizeof(float));
    if(b->data == NULL) {
        LOG_PRINTF(s, "%s: Failed to allocate buffer data memory.\n", name);
        return(-1);
    }
    if(data != NULL) {
        if(type == SYNTH_TYPE_U8) {
            memcpy(b->data, data, size * sizeof(Uint8));
            s->U8toF32.buf = (Uint8 *)b->data;
            s->U8toF32.len = size;
            SDL_ConvertAudio(&(s->U8toF32));
        } else if(type == SYNTH_TYPE_S16) {
            memcpy(b->data, data, size * sizeof(Sint16));
            s->S16toF32.buf = (Uint8 *)b->data;
            s->S16toF32.len = size * sizeof(Sint16);
            SDL_ConvertAudio(&(s->S16toF32));
        } else if(type == SYNTH_TYPE_F32) {
            memcpy(b->data, data, size * sizeof(float));
        } else { /* F64 */
            /* SDL has no conversion facilities to accept F64, so just do
             * a cast of each value in a loop and hope it goes OK. */
            for(i = 0; i < size; i++) {
                b->data[i] = (float)(((double *)data)[i]);
            }
        }
    } else {
        memset(b->data, 0, size * sizeof(float));
    }
    b->ref = 0;
    b->getPart = 0;

    unsigned int namelen = strlen(name) + 1;
    b->name = malloc(namelen);
    if(b->name == NULL) {
        LOG_PRINTF(s, "Failed to allocate memory for name for buffer %s.\n", name);
    }
    strncpy(b->name, name, namelen);

    b->idxbuf = malloc(size * sizeof(float));
    if(b->idxbuf == NULL) {
        LOG_PRINTF(s, "%s: Couldn't allocate index buffer.\n", name);
        free(b->data);
        return(-1);
    }

    return(0);
}

#define BUFFER_INPUT_ONLY (1)
static int is_valid_buffer(Synth *s, unsigned int index, int input) {
    if(index < s->channels) {
        if(input) {
            LOG_PRINTF(s, "Output buffer cannot be used as input.\n");
            return(0);
        } else {
            return(1);
        }
    }

    index -= s->channels;
    if(index > s->buffersmem ||
       s->buffer[index].data == NULL) {
        LOG_PRINTF(s, "Invalid buffer index.\n");
        return(0);
    }

    return(1);
}

static void *get_buffer_data(Synth *s, unsigned int index) {
    if(index < s->channels) {
        return(&(s->channelbuffer[index].data[s->writecursor]));
    }

    return(s->buffer[index - s->channels].data);
}

static unsigned int get_buffer_size(Synth *s, unsigned int index) {
    if(index < s->channels) {
        return(synth_get_samples_needed(s));
    }

    return(s->buffer[index - s->channels].size);
}

static const char *get_buffer_name(Synth *s, unsigned int index) {
    if(index < s->channels) {
        return(s->channelbuffer[index].name);
    }

    return(s->buffer[index - s->channels].name);
}

static float *get_buffer_idxbuf(Synth *s, unsigned int index) {
    if(index < s->channels) {
        return(NULL);
    }

    return(s->buffer[index - s->channels].idxbuf);
}

static void add_buffer_ref(Synth *s, unsigned int index) {
    if(index >= s->channels) {
        s->buffer[index - s->channels].ref++;
    }
}

static void free_buffer_ref(Synth *s, unsigned int index) {
    if(index >= s->channels) {
        if(s->buffer[index - s->channels].ref == 0) {
            LOG_PRINTF(s, "%s: WARNING: Attenpt to free reference to buffer with no references.\n", s->buffer[index - s->channels].name);
            return;
        }
        s->buffer[index - s->channels].ref--;
    }
}

static unsigned int get_buffer_ref(Synth *s, unsigned int index) {
    if(index < s->channels) {
        return(0);
    }

    return(s->buffer[index - s->channels].ref);
}

int synth_add_buffer(Synth *s,
                     SynthImportType type,
                     void *data,
                     unsigned int size,
                     const char *name) {
    unsigned int i, j;
    SynthBuffer *temp;

    if(name == NULL) {
        name = NONAME;
    }

    switch(type) {
        case SYNTH_TYPE_U8:
        case SYNTH_TYPE_S16:
        case SYNTH_TYPE_F32:
        case SYNTH_TYPE_F64:
            break;
        default:
            LOG_PRINTF(s, "%s: Invalid buffer type.\n", name);
            return(-1);
    }

    /* so loop start and loop end can have valid values. */
    if(size < 2) {
        LOG_PRINTF(s, "%s: Buffer size too small, must be at least 2 samples long.\n", name);
        return(-1);
    }

    /* first loaded buffer, so do some initial setup */
    if(s->buffersmem == 0) {
        s->buffer = malloc(sizeof(SynthBuffer));
        if(s->buffer == NULL) {
            LOG_PRINTF(s, "%s: Failed to allocate buffers memory.\n", name);
            return(-1);
        }
        s->buffersmem = 1;

        if(init_buffer(s, &(s->buffer[0]), type, data, size, name) < 0) {
            return(-1);
        }

        return(s->channels);
    }

    /* find first NULL buffer and assign it */
    for(i = 0; i < s->buffersmem; i++) {
        if(s->buffer[i].data == NULL) {
            if(init_buffer(s, &(s->buffer[i]), type, data, size, name) < 0) {
                return(-1);
            }

            return(s->channels + i);
        }
    }

    /* expand buffer if there's no free slots */
    temp = realloc(s->buffer,
                   sizeof(SynthBuffer) * s->buffersmem * 2);
    if(temp == NULL) {
        LOG_PRINTF(s, "%s: Failed to allocate buffers memory.\n", name);
        return(-1);
    }
    s->buffer = temp;
    unsigned int item = s->buffersmem;
    s->buffersmem *= 2;
    /* initialize empty excess buffers as empty */
    for(j = item; j < s->buffersmem; j++) {
        s->buffer[j].data = NULL;
    }

    if(init_buffer(s, &(s->buffer[item]), type, data, size, name) < 0) {
        return(-1);
    }

    return(s->channels + item);
}

int synth_free_buffer(Synth *s, unsigned int index) {
    if(!is_valid_buffer(s, index, BUFFER_INPUT_ONLY)) {
        return(-1);
    }
    if(get_buffer_ref(s, index) != 0) {
        LOG_PRINTF(s, "%s: Buffer still referenced.\n", get_buffer_name(s, index));
        return(-1);
    }
    free(s->buffer[index - s->channels].data);
    free(s->buffer[index - s->channels].idxbuf);
    free(s->buffer[index - s->channels].name);
    s->buffer[index - s->channels].data = NULL;

    return(0);
}

int synth_buffer_get_size(Synth *s, unsigned int index) {
    if(!is_valid_buffer(s, index, 0)) {
        return(-1);
    }

    return(get_buffer_size(s, index));
}

int synth_get_internal_buffer(Synth *s, unsigned int index, float **buf) {
    SynthBuffer *b;

    if(index < s->channels) {
        if(!(s->reffedchannels) && audiodev_is_open(s)) {
            SDL_LockAudioDevice(s->audiodev);
        }
        s->reffedchannels &= 1 << index;
        b = &(s->channelbuffer[index]);
        if(b->getPart == 0) {
            b->getPart = 1;
            if(s->readcursor == s->writecursor) {
                if(s->bufferfilled == s->buffersize) {
                    *buf = &(b->data[s->readcursor]);
                    return(s->buffersize - s->readcursor);
                } else {
                    *buf = NULL;
                    return(0);
                }
            } else if(s->readcursor < s->writecursor) {
                *buf = &(b->data[s->readcursor]);
                return(s->writecursor - s->readcursor);
            } /* s->readcursor > s->writecursor */
            *buf = &(b->data[s->readcursor]);
            return(s->buffersize - s->readcursor);
        }

        b->getPart = 0;
        if(s->readcursor == s->writecursor) {
            if(s->bufferfilled == s->buffersize) {
                *buf = b->data;
                return(s->writecursor);
            } else {
                *buf = NULL;
                return(0);
            }
        } else if(s->readcursor < s->writecursor) {
            *buf = NULL;
            return(0);
        } /* s->readcursor > s->writecursor */
        *buf = b->data;
        return(s->writecursor);
    }

    index -= s->channels;
    if(index > s->buffersmem ||
       s->buffer[index].data == NULL) {
        LOG_PRINTF(s, "Invalid buffer index.\n");
        *buf = NULL;
        return(-1);
    }

    add_buffer_ref(s, index);
    *buf = get_buffer_data(s, index);
    return(get_buffer_size(s, index));
}

int synth_release_buffer(Synth *s, unsigned int index) {
    if(index < s->channels) {
        s->reffedchannels &= ~(1 << index);
        if(!(s->reffedchannels) && audiodev_is_open(s)) {
            SDL_UnlockAudioDevice(s->audiodev);
        }
        return(0);
    }

    index -= s->channels;
    if(index > s->buffersmem ||
       s->buffer[index].data == NULL) {
        LOG_PRINTF(s, "Invalid buffer index.\n");
        return(-1);
    }

    free_buffer_ref(s, index);
    return(0);
}

int synth_silence_buffer(Synth *s,
                         unsigned int index,
                         unsigned int start,
                         unsigned int length) {
    float *o;
    unsigned int os;

    if(!is_valid_buffer(s, index, 0)) {
        return(-1);
    }
    o = get_buffer_data(s, index);
    os = get_buffer_size(s, index);

    if(start >= os ||
       start + length > os) {
        LOG_PRINTF(s, "%s: Bound(s) out of buffer range. %u + %u > %u\n", get_buffer_name(s, index), start, length, os);
        return(-1);
    }
    o = &(o[start]);
    /* always deals with float buffers, whether it's output or otherwise */
    memset(o, 0, length * sizeof(float));

    return(0);
}

static int init_player(Synth *s,
                        SynthPlayer *p,
                        unsigned int inBuffer,
                        const char *name) {
    p->inUse = 1;
    p->inBuffer = inBuffer;
    add_buffer_ref(s, inBuffer);
    p->outBuffer = 0; /* A 0th buffer will have to exist at least */
    p->inPos = 0.0;
    p->outPos = 0;
    p->outOp = SYNTH_OUTPUT_ADD;
    p->volMode = SYNTH_AUTO_CONSTANT;
    p->volume = 1.0;
    p->volBuffer = inBuffer; /* 0 is output only, so this is the only sane
                                default here.  It won't do anything weird.
                                */
    add_buffer_ref(s, inBuffer);
    p->volPos = 0;
    p->mode = SYNTH_MODE_ONCE;
    p->loopStart = 0;
    p->loopEnd = get_buffer_size(s, inBuffer) - 1;
    p->phaseBuffer = inBuffer; /* this would have some weird effect, but
                                  at least it won't fail? */
    add_buffer_ref(s, inBuffer);
    p->phasePos = 0;
    p->speedMode = SYNTH_AUTO_CONSTANT;
    p->speed = 1.0;
    p->speedBuffer = inBuffer; /* same */
    add_buffer_ref(s, inBuffer);
    p->speedPos = 0;

    unsigned int namelen = strlen(name) + 1;
    p->name = malloc(namelen);
    if(p->name == NULL) {
        LOG_PRINTF(s, "Failed to allocate memory for name for buffer %s.\n", name);
        return(-1);
    }
    strncpy(p->name, name, namelen);

    return(0);
}

static SynthPlayer *get_player(Synth *s, unsigned int index) {
    if(index > s->playersmem ||
       s->player[index].inUse == 0) {
        LOG_PRINTF(s, "Invalid player index %u.\n", index);
        return(NULL);
    }

    return(&(s->player[index]));
}

int synth_add_player(Synth *s,
                     unsigned int inBuffer,
                     const char *name) {
    unsigned int i, j;
    SynthPlayer *temp;

    if(name == NULL) {
        name = NONAME;
    }

    if(!is_valid_buffer(s, inBuffer, BUFFER_INPUT_ONLY)) {
        return(-1);
    }

    /* first loaded buffer, so do some initial setup */
    if(s->playersmem == 0) {
        s->player = malloc(sizeof(SynthPlayer));
        if(s->player == NULL) {
            LOG_PRINTF(s, "%s: Failed to allocate buffers memory.\n", name);
            return(-1);
        }
        s->playersmem = 1;

       if(init_player(s, &(s->player[0]), inBuffer, name) < 0) {
           return(-1);
       }
        return(0);
    }

    /* find first NULL buffer and assign it */
    for(i = 0; i < s->playersmem; i++) {
        if(s->player[i].inUse == 0) {
            if(init_player(s, &(s->player[i]), inBuffer, name) < 0) {
                return(-1);
            }
            return(i);
        }
    }

    /* expand buffer if there's no free slots */
    temp = realloc(s->player,
                   sizeof(SynthPlayer) * s->playersmem * 2);
    if(temp == NULL) {
        LOG_PRINTF(s, "%s: Failed to allocate buffers memory.\n", name);
        return(-1);
    }
    s->player = temp;
    unsigned int item = s->playersmem;
    s->playersmem *= 2;
    /* initialize empty excess buffers as empty */
    for(j = item; j < s->playersmem; j++) {
        s->player[j].inUse = 0;
    }

    if(init_player(s, &(s->player[item]), inBuffer, name) < 0) {
        return(-1);
    }
    return(item);
}

int synth_free_player(Synth *s, unsigned int index) {
    SynthPlayer *p = get_player(s, index);
    if(p == NULL) {
        return(-1);
    }
    free_buffer_ref(s, p->outBuffer);
    free_buffer_ref(s, p->inBuffer);
    free_buffer_ref(s, p->volBuffer);
    free_buffer_ref(s, p->phaseBuffer);
    free_buffer_ref(s, p->speedBuffer);
    free(p->name);
    p->inUse = 0;

    return(0);
}

int synth_set_player_input_buffer(Synth *s,
                                  unsigned int index,
                                  unsigned int inBuffer) {
    SynthPlayer *p = get_player(s, index);
    if(p == NULL) {
        return(-1);
    }
    if(p->inBuffer != inBuffer) {
        if(!is_valid_buffer(s, inBuffer, BUFFER_INPUT_ONLY)) {
            return(-1);
        }
        free_buffer_ref(s, p->inBuffer);
        p->inBuffer = inBuffer;
        add_buffer_ref(s, inBuffer);
    }
    p->inPos = 0.0;
    p->loopStart = 0;
    p->loopEnd = get_buffer_size(s, inBuffer) - 1;

    return(0);
}

int synth_set_player_input_buffer_pos(Synth *s,
                                      unsigned int index,
                                      float inPos) {
    SynthPlayer *p = get_player(s, index);
    if(p == NULL) {
        return(-1);
    }
    unsigned int bufsize = get_buffer_size(s, p->inBuffer);
    if(inPos < 0.0) {
        inPos = (float)bufsize + inPos;
    }
    if(inPos < 0.0 || (unsigned int)inPos >= bufsize) {
        LOG_PRINTF(s, "%s: Input position out of buffer bounds.\n", p->name);
        return(-1);
    }
    p->inPos = inPos;

    return(0);
}

int synth_set_player_output_buffer(Synth *s,
                                   unsigned int index,
                                   unsigned int outBuffer) {
    SynthPlayer *p = get_player(s, index);
    if(p == NULL) {
        return(-1);
    }
    if(p->outBuffer != outBuffer) {
        if(!is_valid_buffer(s, outBuffer, 0)) {
            return(-1);
        }
        free_buffer_ref(s, p->outBuffer);
        p->outBuffer = outBuffer;
        add_buffer_ref(s, outBuffer);
    }
    p->outPos = 0;

    return(0);
}

int synth_set_player_output_buffer_pos(Synth *s,
                                       unsigned int index,
                                       int outPos) {
    SynthPlayer *p = get_player(s, index);
    if(p == NULL) {
        return(-1);
    }
    unsigned int bufsize = get_buffer_size(s, p->outBuffer);
    if(outPos < 0) {
        outPos = bufsize + outPos;
    }
    /* if bufsize == 0, that means it's an output buffer which is full, allow
     * setting the output position to 0 in this case, because it's a reasonable
     * thing to want to do at runtime, and it's hopefully impossible to create
     * an issue doing this since a full buffer won't be overfilled anyway.
     * Normal buffers can't have a bufsize of 0. */
    if(outPos < 0 || ((unsigned int)outPos >= bufsize && bufsize > 0 && outPos > 0)) {
        LOG_PRINTF(s, "%s: Player %u output position past end of buffer (%u > %u).\n", p->name, index, outPos, bufsize);
        return(-1);
    }
    p->outPos = outPos;

    return(0);
}

int synth_set_player_output_mode(Synth *s,
                                 unsigned int index,
                                 SynthOutputOperation outOp) {
    SynthPlayer *p = get_player(s, index);
    if(p == NULL) {
        return(-1);
    }

    switch(outOp) {
        case SYNTH_OUTPUT_REPLACE:
        case SYNTH_OUTPUT_ADD:
            break;
        default:
            LOG_PRINTF(s, "%s: Invalid player output mode.\n", p->name);
            return(-1);
    }
    p->outOp = outOp;

    return(0);
}

int synth_set_player_volume_mode(Synth *s,
                                 unsigned int index,
                                 SynthAutoMode volMode) {
    SynthPlayer *p = get_player(s, index);
    if(p == NULL) {
        return(-1);
    }

    switch(volMode) {
        case SYNTH_AUTO_CONSTANT:
        case SYNTH_AUTO_SOURCE:
            break;
        default:
            LOG_PRINTF(s, "%s: Invalid player volume mode.\n", p->name);
            return(-1);
    }
    p->volMode = volMode;

    return(0);
}

int synth_set_player_volume(Synth *s,
                            unsigned int index,
                            float volume) {
    SynthPlayer *p = get_player(s, index);
    if(p == NULL) {
        return(-1);
    }
    p->volume = volume;

    return(0);
}

int synth_set_player_volume_source(Synth *s,
                                   unsigned int index,
                                   unsigned int volBuffer) {
    SynthPlayer *p = get_player(s, index);
    if(p == NULL) {
        return(-1);
    }
    if(p->volBuffer != volBuffer) {
        if(!is_valid_buffer(s, volBuffer, BUFFER_INPUT_ONLY)) {
            return(-1);
        }
        free_buffer_ref(s, p->volBuffer);
        p->volBuffer = volBuffer;
        add_buffer_ref(s, volBuffer);
    }
    p->volPos = 0;

    return(0);
}

int synth_set_player_mode(Synth *s,
                          unsigned int index,
                          SynthPlayerMode mode) {
    SynthPlayer *p = get_player(s, index);
    if(p == NULL) {
        return(-1);
    }

    switch(mode) {
        case SYNTH_MODE_ONCE:
        case SYNTH_MODE_LOOP:
        case SYNTH_MODE_PHASE_SOURCE:
            break;
        default:
            LOG_PRINTF(s, "%s: Invalid player output mode.\n", p->name);
            return(-1);
    }
    p->mode = mode;

    return(0);
}

int synth_set_player_loop_start(Synth *s,
                                unsigned int index,
                                int loopStart) {
    SynthPlayer *p = get_player(s, index);
    if(p == NULL) {
        return(-1);
    }
    if(loopStart < 0) {
        loopStart = get_buffer_size(s, p->inBuffer) + loopStart;
    }
    if(loopStart < 0 ||
       loopStart >= (int)get_buffer_size(s, p->inBuffer)) {
        LOG_PRINTF(s, "%s: Player loop start out of buffer range.\n", p->name);
        return(-1);
    }
    if((unsigned int)loopStart > p->loopEnd) {
        LOG_PRINTF(s, "%s: Loop start must be before loop end.\n", p->name);
        return(-1);
    }
    p->loopStart = loopStart;

    return(0);
}

int synth_set_player_loop_end(Synth *s,
                              unsigned int index,
                              int loopEnd) {
    SynthPlayer *p = get_player(s, index);
    if(p == NULL) {
        return(-1);
    }
    if(loopEnd < 0) {
        loopEnd = get_buffer_size(s, p->inBuffer) + loopEnd;
    }
    if(loopEnd < 0 ||
       loopEnd >= (int)get_buffer_size(s, p->inBuffer)) {
        LOG_PRINTF(s, "%s: Player loop end out of buffer range.\n", p->name);
        return(-1);
    }
    if((unsigned int)loopEnd < p->loopStart) {
        LOG_PRINTF(s, "%s: Loop end must be after loop start.\n", p->name);
        return(-1);
    }
    p->loopEnd = loopEnd;

    return(0);
}

int synth_set_player_phase_source(Synth *s,
                                   unsigned int index,
                                   unsigned int phaseBuffer) {
    SynthPlayer *p = get_player(s, index);
    if(p == NULL) {
        return(-1);
    }
    if(p->phaseBuffer != phaseBuffer) {
        if(!is_valid_buffer(s, phaseBuffer, BUFFER_INPUT_ONLY)) {
            return(-1);
        }
        free_buffer_ref(s, p->phaseBuffer);
        p->phaseBuffer = phaseBuffer;
        add_buffer_ref(s, phaseBuffer);
    }
    p->phasePos = 0;

    return(0);
}

int synth_set_player_speed_mode(Synth *s,
                                unsigned int index,
                                SynthAutoMode speedMode) {
    SynthPlayer *p = get_player(s, index);
    if(p == NULL) {
        return(-1);
    }

    switch(speedMode) {
        case SYNTH_AUTO_CONSTANT:
        case SYNTH_AUTO_SOURCE:
            break;
        default:
            LOG_PRINTF(s, "%s: Invalid player speed mode.\n", p->name);
            return(-1);
    }
    p->speedMode = speedMode;

    return(0);
}

int synth_set_player_speed(Synth *s,
                           unsigned int index,
                           float speed) {
    SynthPlayer *p = get_player(s, index);
    if(p == NULL) {
        return(-1);
    }
    if(speed == -0.0) {
        speed = 0.0;
    }
    p->speed = speed;

    return(0);
}

int synth_set_player_speed_source(Synth *s,
                                  unsigned int index,
                                  unsigned int speedBuffer) {
    SynthPlayer *p = get_player(s, index);
    if(p == NULL) {
        return(-1);
    }
    if(p->speedBuffer != speedBuffer) {
        if(!is_valid_buffer(s, speedBuffer, BUFFER_INPUT_ONLY)) {
            return(-1);
        }
        free_buffer_ref(s, p->speedBuffer);
        p->speedBuffer = speedBuffer;
        add_buffer_ref(s, speedBuffer);
    }
    p->speedPos = 0;

    return(0);
}

static unsigned int do_synth_run_player(Synth *syn, SynthPlayer *pl,
                                        float *o, int outPos,
                                        unsigned int todo) {
    unsigned int samples;
    unsigned int t;
    float vol = pl->volume;
    float *i = get_buffer_data(syn, pl->inBuffer);
    float *idx = get_buffer_idxbuf(syn, pl->inBuffer);

    /* TODO actual player logic */
    if(pl->mode == SYNTH_MODE_ONCE &&
       pl->speedMode == SYNTH_AUTO_CONSTANT) {
        float inPos = pl->inPos;
        float speed = pl->speed;
        int inSize = get_buffer_size(syn, pl->inBuffer);
        for(t = 0; t < todo && (int)inPos >= 0 && (int)inPos < inSize; t++) {
            idx[t] = i[(int)inPos];
            inPos += speed;
        }
        todo = t;
        pl->inPos = inPos;
    } else if(pl->mode == SYNTH_MODE_ONCE &&
              pl->speedMode == SYNTH_AUTO_SOURCE) {
        float *s = get_buffer_data(syn, pl->speedBuffer);
        float inPos = pl->inPos;
        int speedPos = pl->speedPos;
        float speed = pl->speed;
        todo = MIN(todo, get_buffer_size(syn, pl->speedBuffer) - speedPos);
        int inSize = get_buffer_size(syn, pl->inBuffer);
        for(t = 0; t < todo && (int)inPos >= 0 && (int)inPos < inSize; t++) {
            idx[t] = i[(int)inPos];
            inPos += speed * powf(2, s[speedPos + t]);
        }
        todo = t;
        pl->inPos = inPos;
        speedPos += t;
    } else if(pl->mode == SYNTH_MODE_LOOP &&
              pl->speedMode == SYNTH_AUTO_CONSTANT) {
        float inPos = pl->inPos - pl->loopStart;
        i = &(i[pl->loopStart]);
        float speed = pl->speed;
        float loopLen = pl->loopEnd - pl->loopStart + 1;
        for(samples = 0; samples < todo; samples++) {
            if(inPos > loopLen) {
                inPos = fmodf(inPos, loopLen);
            } else if(inPos < 0) {
                inPos = fmodf(inPos, loopLen) + loopLen;
            }
            idx[samples] = i[(int)inPos];
            inPos += speed;
        }
        pl->inPos = pl->loopStart + inPos;
    } else if(pl->mode == SYNTH_MODE_LOOP &&
              pl->speedMode == SYNTH_AUTO_SOURCE) {
        float *s = get_buffer_data(syn, pl->speedBuffer);
        float inPos = pl->inPos - pl->loopStart;
        i = &(i[pl->loopStart]);
        int speedPos = pl->speedPos;
        float speed = pl->speed;
        todo = MIN(todo, get_buffer_size(syn, pl->speedBuffer) - speedPos);
        float loopLen = pl->loopEnd - pl->loopStart + 1;
        for(samples = 0; samples < todo; samples++) {
            if(inPos > loopLen) {
                inPos = fmodf(inPos, loopLen);
            } else if(inPos < 0) {
                inPos = fmodf(inPos, loopLen) + loopLen;
            }
            idx[samples] = i[(int)inPos];
            inPos += speed * powf(2, s[speedPos]);
            speedPos++;
        }
        pl->inPos = inPos + pl->loopStart;
        pl->speedPos = speedPos;
    } else if(pl->mode == SYNTH_MODE_PHASE_SOURCE) {
        float *p = get_buffer_data(syn, pl->phaseBuffer);
        int phasePos = pl->phasePos;
        float loopLen = pl->loopEnd - pl->loopStart + 1;
        todo = MIN(todo, get_buffer_size(syn, pl->phaseBuffer) - phasePos);
        for(samples = 0; samples < todo; samples++) {
            idx[samples] =
                i[(int)fmodf(fabsf(p[phasePos] * loopLen), loopLen)
                  + pl->loopStart];
            phasePos++;
        }
        pl->phasePos = phasePos;
    }

    if(pl->volMode == SYNTH_AUTO_CONSTANT &&
       pl->outOp == SYNTH_OUTPUT_REPLACE) {
        for(samples = 0; samples < todo; samples++) {
            o[outPos] = idx[samples] * vol;
            outPos++;
        }
    } else if(pl->volMode == SYNTH_AUTO_CONSTANT &&
              pl->outOp == SYNTH_OUTPUT_ADD) {
        for(samples = 0; samples < todo; samples++) {
            o[outPos] += idx[samples] * vol;
            outPos++;
        }
    } else if(pl->volMode == SYNTH_AUTO_SOURCE) {
        float *v = get_buffer_data(syn, pl->volBuffer);
        int volPos = pl->volPos;
        todo = MIN(todo, get_buffer_size(syn, pl->volBuffer) - volPos);
        if(pl->outOp == SYNTH_OUTPUT_REPLACE) {
            for(samples = 0; samples < todo; samples++) {
                o[outPos] = idx[samples] * v[volPos] * vol;
                outPos++;
                volPos++;
            }
        } else if(pl->outOp == SYNTH_OUTPUT_ADD) {
            for(samples = 0; samples < todo; samples++) {
                o[outPos] += idx[samples] * v[volPos] * vol;
                outPos++;
                volPos++;
            }
        }
        pl->volPos = volPos;
    }

    return(todo);
}

int synth_run_player(Synth *s,
                     unsigned int index,
                     unsigned int reqSamples) {
    int samples;
    int todo;

    SynthPlayer *p = get_player(s, index);
    if(p == NULL) {
        return(-1);
    }

    float *o = get_buffer_data(s, p->outBuffer);

    unsigned int outPos = p->outPos;

    /* Try to get the entire task done in 1 call */
    /* if it's an ouptut buffer, try to fill it as much as possible */
    if(p->outBuffer < s->channels) {
        todo = MIN(reqSamples,
                   get_buffer_size(s, p->outBuffer) - outPos);

        if((unsigned int)s->writecursor + outPos >= s->buffersize) {
            /* if it starts past the end, figure out where to start from the
             * beginning */
            unsigned int temp = s->writecursor;
            s->writecursor = 0;
            o = get_buffer_data(s, p->outBuffer);
            s->writecursor = temp;

            samples = do_synth_run_player(s, p, o, s->writecursor + outPos - s->buffersize, todo);
        } else if((unsigned int)s->writecursor + outPos + todo >= s->buffersize) {
            /* if it would go past the end, split it in to 2 calls */
            samples = do_synth_run_player(s, p, o, outPos,
                                          s->buffersize - s->writecursor - outPos);
            todo -= samples;
            /* if there's more to do, try updating the pointer and trying
             * again. */
            if(todo > 0) {
                /* store it temporarily so when it's properly updated later,
                 * it'll be correct */
                unsigned int temp = s->writecursor;
                s->writecursor = 0;
                o = get_buffer_data(s, p->outBuffer);
                s->writecursor = temp;

                samples += do_synth_run_player(s, p, o, 0, todo);
            }
        } else {
            samples = do_synth_run_player(s, p, o, outPos, todo);
        }
    } else {
        todo = MIN(reqSamples,
                   get_buffer_size(s, p->outBuffer) - outPos);

        samples = do_synth_run_player(s, p, o, outPos, todo);
    }
    p->outPos = outPos + samples;

    return(samples);
}

int synth_player_stopped_reason(Synth *syn,
                                unsigned int index) {
    int reason = 0;
    SynthPlayer *pl = get_player(syn, index);
    if(pl == NULL) {
        return(-1);
    }

    if(pl->outPos >= get_buffer_size(syn, pl->outBuffer)) {
        reason |= SYNTH_STOPPED_OUTBUFFER;
    }

    if(pl->mode == SYNTH_MODE_ONCE &&
       pl->speedMode == SYNTH_AUTO_CONSTANT) {
        if(((int)(pl->inPos) < 0) ||
           ((unsigned int)(pl->inPos) >= get_buffer_size(syn, pl->inBuffer))) {
            reason |= SYNTH_STOPPED_INBUFFER;
        }
        if(pl->volMode == SYNTH_AUTO_SOURCE) {
            if(pl->volPos >= get_buffer_size(syn, pl->volBuffer)) {
                reason |= SYNTH_STOPPED_VOLBUFFER;
            }
        }
    } else if(pl->mode == SYNTH_MODE_ONCE &&
              pl->speedMode == SYNTH_AUTO_SOURCE) {
        if(((int)(pl->inPos) < 0) ||
           ((unsigned int)(pl->inPos) >= get_buffer_size(syn, pl->inBuffer))) {
            reason |= SYNTH_STOPPED_INBUFFER;
        }
        if(pl->speedPos >= get_buffer_size(syn, pl->speedBuffer)) {
            reason |= SYNTH_STOPPED_SPEEDBUFFER;
        }
        if(pl->volMode == SYNTH_AUTO_SOURCE) {
            if(pl->volPos >= get_buffer_size(syn, pl->volBuffer)) {
                reason |= SYNTH_STOPPED_VOLBUFFER;
            }
        }
    } else if(pl->mode == SYNTH_MODE_LOOP &&
              pl->speedMode == SYNTH_AUTO_CONSTANT) {
        if(pl->volMode == SYNTH_AUTO_SOURCE) {
            if(pl->volPos >= get_buffer_size(syn, pl->volBuffer)) {
                reason |= SYNTH_STOPPED_VOLBUFFER;
            }
        }
    } else if(pl->mode == SYNTH_MODE_LOOP &&
              pl->speedMode == SYNTH_AUTO_SOURCE) {
        if(pl->speedPos >= get_buffer_size(syn, pl->speedBuffer)) {
            reason |= SYNTH_STOPPED_SPEEDBUFFER;
        }
        if(pl->volMode == SYNTH_AUTO_SOURCE) {
            if(pl->volPos >= get_buffer_size(syn, pl->volBuffer)) {
                reason |= SYNTH_STOPPED_VOLBUFFER;
            }
        }
    } else if(pl->mode == SYNTH_MODE_PHASE_SOURCE) {
        if(pl->phasePos >= get_buffer_size(syn, pl->phaseBuffer)) {
            reason |= SYNTH_STOPPED_PHASEBUFFER;
        }
        if(pl->volMode == SYNTH_AUTO_SOURCE) {
            if(pl->volPos >= get_buffer_size(syn, pl->volBuffer)) {
                reason |= SYNTH_STOPPED_VOLBUFFER;
            }
        }
    }

    return(reason);
}

static int init_filter(Synth *s,
                       SynthFilter *f,
                       unsigned int filterBuffer,
                       unsigned int size,
                       const char *name) {
    f->accum = malloc(sizeof(float) * size);
    if(f->accum == NULL) {
        LOG_PRINTF(s, "%s: Failed to allocate filter accumulation buffer.\n", name);
        return(-1);
    }
    f->size = size;
    f->accumPos = 0;
    f->inBuffer = filterBuffer;
    add_buffer_ref(s, filterBuffer);
    f->inPos = 0;
    f->filterBuffer = filterBuffer;
    add_buffer_ref(s, filterBuffer);
    f->startPos = 0;
    f->slices = 1;
    f->mode = SYNTH_AUTO_CONSTANT;
    f->slice = 0;
    f->sliceBuffer = filterBuffer;
    add_buffer_ref(s, filterBuffer);
    f->slicePos = 0;
    f->outBuffer = 0;
    f->outPos = 0;
    f->outOp = SYNTH_OUTPUT_ADD;
    f->volMode = SYNTH_AUTO_CONSTANT;
    f->vol = 1.0;
    f->volBuffer = filterBuffer;
    add_buffer_ref(s, filterBuffer);
    f->volPos = 0;

    unsigned int namelen = strlen(name) + 1;
    f->name = malloc(namelen);
    if(f->name == NULL) {
        LOG_PRINTF(s, "Failed to allocate memory for name for buffer %s.\n", name);
        return(-1);
    }
    strncpy(f->name, name, namelen);

    return(0);
}

static SynthFilter *get_filter(Synth *s, unsigned int index) {
    if(index > s->filtersmem ||
       s->filter[index].accum == NULL) {
        LOG_PRINTF(s, "Invalid filter index %u.\n", index);
        return(NULL);
    }

    return(&(s->filter[index]));
}

int synth_add_filter(Synth *s,
                     unsigned int filterBuffer,
                     unsigned int size,
                     const char *name) {
    unsigned int i, j;
    SynthFilter *temp;

    if(name == NULL) {
        name = NONAME;
    }

    if(!is_valid_buffer(s, filterBuffer, BUFFER_INPUT_ONLY)) {
        return(-1);
    }

    if(size == 0) {
        size = get_buffer_size(s, filterBuffer);
    }

    if(get_buffer_size(s, filterBuffer) < size) {
        LOG_PRINTF(s, "%s: Input buffer isn't large enough for filter size.", name);
        return(-1);
    }

    /* first loaded buffer, so do some initial setup */
    if(s->filtersmem == 0) {
        s->filter = malloc(sizeof(SynthFilter));
        if(s->filter == NULL) {
            LOG_PRINTF(s, "%s: Failed to allocate filters memory.\n", name);
            return(-1);
        }
        s->filtersmem = 1;

        if(init_filter(s, &(s->filter[0]), filterBuffer, size, name) < 0) {
            return(-1);
        }
        synth_reset_filter(s, 0);
        return(0);
    }

    /* find first NULL buffer and assign it */
    for(i = 0; i < s->filtersmem; i++) {
        if(s->filter[i].accum == NULL) {
            if(init_filter(s, &(s->filter[i]), filterBuffer, size, name) < 0) {
                return(-1);
            }
            synth_reset_filter(s, i);
            return(i);
        }
    }

    /* expand buffer if there's no free slots */
    temp = realloc(s->filter,
                   sizeof(SynthFilter) * s->filtersmem * 2);
    if(temp == NULL) {
        LOG_PRINTF(s, "%s: Failed to allocate filters memory.\n", name);
        return(-1);
    }
    s->filter = temp;
    unsigned int item = s->filtersmem;
    s->filtersmem *= 2;
    /* initialize empty excess buffers as empty */
    for(j = item; j < s->filtersmem; j++) {
        s->filter[j].accum = NULL;
    }

    if(init_filter(s, &(s->filter[item]), filterBuffer, size, name) < 0) {
        return(-1);
    }
    synth_reset_filter(s, item);
    return(i);
}

int synth_free_filter(Synth *s, unsigned int index) {
    SynthFilter *f = get_filter(s, index);
    if(f == NULL) {
        return(-1);
    }

    free_buffer_ref(s, f->inBuffer);
    free_buffer_ref(s, f->filterBuffer);
    free_buffer_ref(s, f->sliceBuffer);
    free_buffer_ref(s, f->outBuffer);
    free_buffer_ref(s, f->volBuffer);
    free(f->name);
    free(f->accum);
    f->accum = NULL;

    return(0);
}

int synth_reset_filter(Synth *s, unsigned int index) {
    SynthFilter *f = get_filter(s, index);
    if(f == NULL) {
        return(-1);
    }

    memset(f->accum, 0, sizeof(float) * f->size);

    return(0);
}

int synth_set_filter_input_buffer(Synth *s,
                                  unsigned int index,
                                  unsigned int inBuffer) {
    SynthFilter *f = get_filter(s, index);
    if(f == NULL) {
        return(-1);
    }
    if(f->inBuffer != inBuffer) {
        if(!is_valid_buffer(s, inBuffer, BUFFER_INPUT_ONLY)) {
            return(-1);
        }
        free_buffer_ref(s, f->inBuffer);
        f->inBuffer = inBuffer;
        add_buffer_ref(s, inBuffer);
    }
    f->inPos = 0;

    return(0);
}

int synth_set_filter_input_buffer_pos(Synth *s,
                                      unsigned int index,
                                      int inPos) {
    SynthFilter *f = get_filter(s, index);
    if(f == NULL) {
        return(-1);
    }
    unsigned int bufsize = get_buffer_size(s, f->inBuffer);
    if(inPos < 0) {
        inPos = bufsize + inPos;
    }
    if(inPos < 0 || (unsigned int)inPos >= bufsize) {
        LOG_PRINTF(s, "%s: Input position out of buffer bounds.\n", f->name);
        return(-1);
    }
    f->inPos = inPos;

    return(0);
}

int synth_set_filter_buffer(Synth *s,
                            unsigned int index,
                            unsigned int filterBuffer) {
    SynthFilter *f = get_filter(s, index);
    if(f == NULL) {
        return(-1);
    }
    if(f->filterBuffer != filterBuffer) {
        if(!is_valid_buffer(s, filterBuffer, BUFFER_INPUT_ONLY)) {
            return(-1);
        }
        free_buffer_ref(s, f->filterBuffer);
        f->filterBuffer = filterBuffer;
        add_buffer_ref(s, filterBuffer);
    }
    f->startPos = 0;
    f->slices = 1;
    f->slice = 0;

    return(0);
}

int synth_set_filter_buffer_start(Synth *s,
                                  unsigned int index,
                                  int startPos) {
    SynthFilter *f = get_filter(s, index);
    if(f == NULL) {
        return(-1);
    }
    unsigned int bufsize = get_buffer_size(s, f->filterBuffer);
    if(startPos < 0) {
        startPos = bufsize + startPos;
    }
    if(startPos < 0 ||
       (unsigned int)startPos + (f->size * f->slices) > bufsize) {
        LOG_PRINTF(s, "%s: Buffer start would make slices exceed buffer size.\n", f->name);
        return(-1);
    }
    f->startPos = startPos;

    return(0);
}

int synth_set_filter_slices(Synth *s,
                            unsigned int index,
                            unsigned int slices) {
    SynthFilter *f = get_filter(s, index);
    if(f == NULL) {
        return(-1);
    }
    unsigned int bufsize = get_buffer_size(s, f->filterBuffer);
    unsigned int neededsize = f->startPos + (f->size * slices);
    if(neededsize > bufsize) {
        LOG_PRINTF(s, "%s: Slices count would exceed buffer size (%u + (%u * %u) = %u > %u.\n", f->name,
                   f->startPos, f->size, slices, neededsize, bufsize);
        return(-1);
    }
    f->slices = slices;
    f->slice = 0;

    return(0);
}

int synth_set_filter_mode(Synth *s,
                          unsigned int index,
                          SynthAutoMode mode) {
    SynthFilter *f = get_filter(s, index);
    if(f == NULL) {
        return(-1);
    }

    switch(mode) {
        case SYNTH_AUTO_CONSTANT:
        case SYNTH_AUTO_SOURCE:
            break;
        default:
            LOG_PRINTF(s, "%s: Invalid filter mode.\n", f->name);
            return(-1);
    }
    f->mode = mode;

    return(0);
}

int synth_set_filter_slice(Synth *s,
                           unsigned int index,
                           int slice) {
    SynthFilter *f = get_filter(s, index);
    if(f == NULL) {
        return(-1);
    }
    if(slice < 0) {
        slice = f->slices + slice;
    }
    if(slice < 0 || (unsigned int)slice >= f->slices) {
        LOG_PRINTF(s, "%s: Slice is greater than configured slices.\n", f->name);
        return(-1);
    }
    f->slice = slice;

    return(0);
}

int synth_set_filter_slice_source(Synth *s,
                                  unsigned int index,
                                  unsigned int sliceBuffer) {
    SynthFilter *f = get_filter(s, index);
    if(f == NULL) {
        return(-1);
    }
    if(f->sliceBuffer != sliceBuffer) {
        if(!is_valid_buffer(s, sliceBuffer, BUFFER_INPUT_ONLY)) {
            return(-1);
        }
        free_buffer_ref(s, f->sliceBuffer);
        f->sliceBuffer = sliceBuffer;
        add_buffer_ref(s, sliceBuffer);
    }
    f->slicePos = 0;

    return(0);
}

int synth_set_filter_output_buffer(Synth *s,
                                   unsigned int index,
                                   unsigned int outBuffer) {
    SynthFilter *f = get_filter(s, index);
    if(f == NULL) {
        return(-1);
    }
    if(f->outBuffer != outBuffer) {
        if(!is_valid_buffer(s, outBuffer, 0)) {
            return(-1);
        }
        free_buffer_ref(s, f->outBuffer);
        f->outBuffer = outBuffer;
        add_buffer_ref(s, outBuffer);
    }
    f->outPos = 0;

    return(0);
}

int synth_set_filter_output_buffer_pos(Synth *s,
                                       unsigned int index,
                                       int outPos) {
    SynthFilter *f = get_filter(s, index);
    if(f == NULL) {
        return(-1);
    }
    unsigned int bufsize = get_buffer_size(s, f->outBuffer);
    if(outPos < 0) {
        outPos = bufsize + outPos;
    }
    /* see note in synth_set_player_output_buffer_pos */
    if(outPos < 0 || ((unsigned int)outPos >= bufsize && bufsize > 0 && outPos > 0)) {
        LOG_PRINTF(s, "%s: Filter %u output position past end of buffer (%u > %u).\n", f->name, index, outPos, bufsize);
        return(-1);
    }
    f->outPos = outPos;

    return(0);
}

int synth_set_filter_output_mode(Synth *s,
                                 unsigned int index,
                                 SynthOutputOperation outOp) {
    SynthFilter *f = get_filter(s, index);
    if(f == NULL) {
        return(-1);
    }

    switch(outOp) {
        case SYNTH_OUTPUT_REPLACE:
        case SYNTH_OUTPUT_ADD:
            break;
        default:
            LOG_PRINTF(s, "%s: Invalid filter output mode.\n", f->name);
            return(-1);
    }
    f->outOp = outOp;

    return(0);
}

int synth_set_filter_volume_mode(Synth *s,
                                 unsigned int index,
                                 SynthAutoMode volMode) {
    SynthFilter *f = get_filter(s, index);
    if(f == NULL) {
        return(-1);
    }

    switch(volMode) {
        case SYNTH_AUTO_CONSTANT:
        case SYNTH_AUTO_SOURCE:
            break;
        default:
            LOG_PRINTF(s, "%s: Invalid volume mode.\n", f->name);
            return(-1);
    }
    f->volMode = volMode;

    return(0);
}

int synth_set_filter_volume(Synth *s,
                            unsigned int index,
                            float vol) {
    SynthFilter *f = get_filter(s, index);
    if(f == NULL) {
        return(-1);
    }
    f->vol = vol;

    return(0);
}

int synth_set_filter_volume_source(Synth *s,
                                   unsigned int index,
                                   unsigned int volBuffer) {
    SynthFilter *f = get_filter(s, index);
    if(f == NULL) {
        return(-1);
    }
    if(f->volBuffer != volBuffer) {
        if(!is_valid_buffer(s, volBuffer, BUFFER_INPUT_ONLY)) {
            return(-1);
        }
        free_buffer_ref(s, f->volBuffer);
        f->volBuffer = volBuffer;
        add_buffer_ref(s, volBuffer);
    }
    f->volPos = 0;

    return(0);
}

static unsigned int do_synth_run_filter(Synth *syn, SynthFilter *flt,
                                        float *o, int outPos,
                                        int todo) {
    unsigned int j;
    /* silence a warning */
    int samples = 0;

    float *i = get_buffer_data(syn, flt->inBuffer);
    i = &(i[flt->inPos]);
    o = &(o[outPos]);

    todo = MIN((unsigned int)todo, get_buffer_size(syn, flt->inBuffer) - flt->inPos);
    if(flt->mode == SYNTH_AUTO_CONSTANT) {
        /* get pointer to the specifically selected filter slice */
        float *f = get_buffer_data(syn, flt->filterBuffer);
        f = &(f[flt->startPos + (flt->slice * flt->size)]);
        if(flt->volMode == SYNTH_AUTO_CONSTANT) {
            if(flt->outOp == SYNTH_OUTPUT_REPLACE) {
                for(samples = 0; samples < todo; samples++) {
                    unsigned int pos = 0;
                    /* update the first half of the accumulation buffer */
                    for(j = flt->accumPos; j < flt->size; j++) {
                        flt->accum[j] += i[samples] * f[pos];
                        pos++;
                    }
                    /* second half */
                    for(j = 0; j < flt->accumPos; j++) {
                        flt->accum[j] += i[samples] * f[pos];
                        pos++;
                    }
                    /* apply the accumulated value to the output */
                    o[samples] = flt->accum[flt->accumPos] * flt->vol;
                    /* clear the fetched value */
                    flt->accum[flt->accumPos] = 0.0;
                    /* advance the acumulator start and do wrapping */
                    flt->accumPos = (flt->accumPos + 1) % flt->size;
                }
            } else if(flt->outOp == SYNTH_OUTPUT_ADD) {
                for(samples = 0; samples < todo; samples++) {
                    unsigned int pos = 0;
                    for(j = flt->accumPos; j < flt->size; j++) {
                        flt->accum[j] += i[samples] * f[pos];
                        pos++;
                    }
                    for(j = 0; j < flt->accumPos; j++) {
                        flt->accum[j] += i[samples] * f[pos];
                        pos++;
                    }
                    o[samples] += flt->accum[flt->accumPos] * flt->vol;
                    flt->accum[flt->accumPos] = 0.0;
                    flt->accumPos = (flt->accumPos + 1) % flt->size;
                }
            }
        } else if(flt->volMode == SYNTH_AUTO_SOURCE) {
            float *v = get_buffer_data(syn, flt->volBuffer);
            v = &(v[flt->volPos]);
            todo = MIN((unsigned int)todo, get_buffer_size(syn, flt->volBuffer) - flt->volPos);
            if(flt->outOp == SYNTH_OUTPUT_REPLACE) {
                for(samples = 0; samples < todo; samples++) {
                    unsigned int pos = 0;
                    for(j = flt->accumPos; j < flt->size; j++) {
                        flt->accum[j] += i[samples] * f[pos];
                        pos++;
                    }
                    for(j = 0; j < flt->accumPos; j++) {
                        flt->accum[j] += i[samples] * f[pos];
                        pos++;
                    }
                    /* apply the volume from the volume buffer */
                    o[samples] = flt->accum[flt->accumPos] *
                                 v[samples] * flt->vol;
                    flt->accum[flt->accumPos] = 0.0;
                    flt->accumPos = (flt->accumPos + 1) % flt->size;
                }
            } else if(flt->outOp == SYNTH_OUTPUT_ADD) {
                for(samples = 0; samples < todo; samples++) {
                    unsigned int pos = 0;
                    for(j = flt->accumPos; j < flt->size; j++) {
                        flt->accum[j] += i[samples] * f[pos];
                        pos++;
                    }
                    for(j = 0; j < flt->accumPos; j++) {
                        flt->accum[j] += i[samples] * f[pos];
                        pos++;
                    }
                    o[samples] += flt->accum[flt->accumPos] *
                                  v[samples] * flt->vol;
                    flt->accum[flt->accumPos] = 0.0;
                    flt->accumPos = (flt->accumPos + 1) % flt->size;
                }
            }
            flt->volPos += samples;
        }
    } else if(flt->mode == SYNTH_AUTO_SOURCE) {
        float *s = get_buffer_data(syn, flt->sliceBuffer);
        s = &(s[flt->slicePos]);
        todo = MIN((unsigned int)todo, get_buffer_size(syn, flt->sliceBuffer) - flt->slicePos);
        float *f = get_buffer_data(syn, flt->filterBuffer);
        float *fs;
        unsigned int slices = flt->slices - flt->slice;
        unsigned int startPos = flt->startPos + (flt->slice * flt->size);
        if(flt->volMode == SYNTH_AUTO_CONSTANT) {
            if(flt->outOp == SYNTH_OUTPUT_REPLACE) {
                for(samples = 0; samples < todo; samples++) {
                    fs = &(f[startPos +
                             (((int)(s[samples] * slices)) % slices * flt->size)]);
                    unsigned int pos = 0;
                    for(j = flt->accumPos; j < flt->size; j++) {
                        flt->accum[j] += i[samples] * fs[pos];
                        pos++;
                    }
                    for(j = 0; j < flt->accumPos; j++) {
                        flt->accum[j] += i[samples] * fs[pos];
                        pos++;
                    }
                    o[samples] = flt->accum[flt->accumPos] * flt->vol;
                    flt->accum[flt->accumPos] = 0.0;
                    flt->accumPos = (flt->accumPos + 1) % flt->size;
                }
            } else if(flt->outOp == SYNTH_OUTPUT_ADD) {
                for(samples = 0; samples < todo; samples++) {
                    fs = &(f[startPos +
                             (((int)(s[samples] * slices)) % slices * flt->size)]);
                    unsigned int pos = 0;
                    for(j = flt->accumPos; j < flt->size; j++) {
                        flt->accum[j] += i[samples] * fs[pos];
                        pos++;
                    }
                    for(j = 0; j < flt->accumPos; j++) {
                        flt->accum[j] += i[samples] * fs[pos];
                        pos++;
                    }
                    o[samples] += flt->accum[flt->accumPos] * flt->vol;
                    flt->accum[flt->accumPos] = 0.0;
                    flt->accumPos = (flt->accumPos + 1) % flt->size;
                }
            }
        } else if(flt->volMode == SYNTH_AUTO_SOURCE) {
            float *v = get_buffer_data(syn, flt->volBuffer);
            v = &(v[flt->volPos]);
            todo = MIN((unsigned int)todo, get_buffer_size(syn, flt->volBuffer) - flt->volPos);
            if(flt->outOp == SYNTH_OUTPUT_REPLACE) {
                for(samples = 0; samples < todo; samples++) {
                    fs = &(f[startPos +
                             (((int)(s[samples] * slices)) % slices * flt->size)]);
                    unsigned int pos = 0;
                    for(j = flt->accumPos; j < flt->size; j++) {
                        flt->accum[j] += i[samples] * fs[pos];
                        pos++;
                    }
                    for(j = 0; j < flt->accumPos; j++) {
                        flt->accum[j] += i[samples] * fs[pos];
                        pos++;
                    }
                    o[samples] = flt->accum[flt->accumPos] *
                                 v[samples] * flt->vol;
                    flt->accum[flt->accumPos] = 0.0;
                    flt->accumPos = (flt->accumPos + 1) % flt->size;
                }
            } else if(flt->outOp == SYNTH_OUTPUT_ADD) {
                for(samples = 0; samples < todo; samples++) {
                    fs = &(f[startPos +
                             (((int)(s[samples] * slices)) % slices * flt->size)]);
                    unsigned int pos = 0;
                    for(j = flt->accumPos; j < flt->size; j++) {
                        flt->accum[j] += i[samples] * fs[pos];
                        pos++;
                    }
                    for(j = 0; j < flt->accumPos; j++) {
                        flt->accum[j] += i[samples] * fs[pos];
                        pos++;
                    }
                    o[samples] += flt->accum[flt->accumPos] *
                                  v[samples] * flt->vol;
                    flt->accum[flt->accumPos] = 0.0;
                    flt->accumPos = (flt->accumPos + 1) % flt->size;
                }
            }
            flt->volPos += samples;
        }
        flt->slicePos += samples;
    }
    flt->inPos += samples;

    return(samples);
}

int synth_run_filter(Synth *s,
                     unsigned int index,
                     unsigned int reqSamples) {
    int samples;
    int todo;

    SynthFilter *f = get_filter(s, index);
    if(f == NULL) {
        return(-1);
    }

    float *o = get_buffer_data(s, f->outBuffer);

    unsigned int outPos = f->outPos;

    /* Try to get the entire task done in 1 call */
    /* if it's an ouptut buffer, try to fill it as much as possible */
    if(f->outBuffer < s->channels) {
        todo = MIN(reqSamples,
                   get_buffer_size(s, f->outBuffer) - (int)outPos);

        if((unsigned int)s->writecursor + outPos >= s->buffersize) {
            /* if it starts past the end, figure out where to start from the
             * beginning */
            unsigned int temp = s->writecursor;
            s->writecursor = 0;
            o = get_buffer_data(s, f->outBuffer);
            s->writecursor = temp;

            samples = do_synth_run_filter(s, f, o, s->writecursor + outPos - s->buffersize, todo);
        } else if((unsigned int)s->writecursor + outPos + todo >= s->buffersize) {
            /* if it would go past the end, split it in to 2 calls */
            samples = do_synth_run_filter(s, f, o, outPos,
                                          s->buffersize - s->writecursor - outPos);
            todo -= samples;
            /* if there's more to do, try updating the pointer and trying
             * again. */
            if(todo > 0) {
                /* store it temporarily so when it's properly updated later,
                 * it'll be correct */
                unsigned int temp = s->writecursor;
                s->writecursor = 0;
                o = get_buffer_data(s, f->outBuffer);
                s->writecursor = temp;

                samples += do_synth_run_filter(s, f, o, 0, todo);
            }
        } else {
            samples = do_synth_run_filter(s, f, o, outPos, todo);
        }
    } else {
        todo = MIN(reqSamples,
                   get_buffer_size(s, f->outBuffer) - (int)outPos);

        samples = do_synth_run_filter(s, f, o, outPos, todo);
    }
    f->outPos = outPos + samples;

    return(samples);
}

int synth_filter_stopped_reason(Synth *syn, unsigned int index) {
    int reason = 0;
    SynthFilter *flt = get_filter(syn, index);
    if(flt == NULL) {
        return(-1);
    }

    if(get_buffer_size(syn, flt->outBuffer) - flt->outPos == 0) {
        reason |= SYNTH_STOPPED_OUTBUFFER;
    }
    if(get_buffer_size(syn, flt->inBuffer) - flt->inPos == 0) {
        reason |= SYNTH_STOPPED_INBUFFER;
    }

    if(flt->mode == SYNTH_AUTO_CONSTANT) {
        if(flt->volMode == SYNTH_AUTO_SOURCE) {
            if(get_buffer_size(syn, flt->volBuffer) - flt->volPos == 0) {
                reason |= SYNTH_STOPPED_VOLBUFFER;
            }
        }
    } else if(flt->mode == SYNTH_AUTO_SOURCE) {
        if(get_buffer_size(syn, flt->sliceBuffer) - flt->slicePos == 0) {
            reason |= SYNTH_STOPPED_SLICEBUFFER;
        }
        if(flt->volMode == SYNTH_AUTO_SOURCE) {
            if(get_buffer_size(syn, flt->volBuffer) - flt->volPos == 0) {
                reason |= SYNTH_STOPPED_VOLBUFFER;
            }
        }
    }

    return(reason);
}
