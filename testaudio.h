#include "synth.h"

typedef struct ActivePlayer_s ActivePlayer;
typedef struct AudioState_s AudioState;

int create_mix_buffers(AudioState *as);
int audio_frame_cb(void *priv);
AudioState *init_audio_state(unsigned int rate);
void free_audio_state(AudioState *as);
Synth *get_synth(AudioState *as);
int load_sound(Synth *s,
               const char *filename,
               int *buf,
               float dB);
int play_sound(AudioState *as, unsigned int player, float volume, float panning);
void stop_sound(AudioState *as, int token);
int update_volume(AudioState *as, int token, float volume);
int update_panning(AudioState *as, int token, float panning);
