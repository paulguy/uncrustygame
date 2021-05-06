#include "tilemap.h"
#include <SDL.h>

#include "extramath.h"

#define CBOX_MIN_TIME    (1000)
#define CBOX_MAX_TIME    (5000)

#define CBOX_TIME_RAND RANDRANGE(CBOX_MIN_TIME, CBOX_MAX_TIME)

typedef enum {
    DIR_LEFT,
    DIR_RIGHT,
    DIR_UP,
    DIR_DOWN
} Direction;

typedef struct {
    int tilemap;
    int layer;
    Uint32 bgColor;
    float x, y;
    int w, h;
    int shadowOffset;
    Direction dir;
    float speed;
} ColorBox;

int load_graphic(LayerList *ll,
                 const char *filename,
                 unsigned int tWidth, unsigned int tHeight,
                 int *tileset,
                 int *tilemap,
                 int *layer,
                 const unsigned int *values,
                 const unsigned int *colormod,
                 unsigned int tmWidth, unsigned int tmHeight,
                 float layerScale);
int create_sprite(LayerList *ll,
                  unsigned int spritemap,
                  unsigned int size,
                  unsigned int scale);
int select_sprite(LayerList *ll,
                  unsigned int layer,
                  unsigned int sprite,
                  unsigned int size);
int position_sprite(LayerList *ll,
                    unsigned int layer,
                    int x, int y,
                    unsigned int size);
int clear_tilemap(LayerList *ll,
                  unsigned int tilemap,
                  unsigned int w, unsigned int h);
int prepare_frame(LayerList *ll,
                  Uint8 r, Uint8 g, Uint8 b,
                  unsigned int bgLayer);
int draw_text_layer(LayerList *ll,
                    unsigned int layer,
                    int shadowOffset,
                    Uint32 shadowColor,
                    Uint32 textColor);
void fill_tilemap_with_pattern(unsigned int *values,
                               unsigned int vWidth, unsigned int vHeight,
                               const unsigned int *pattern,
                               unsigned int pWidth, unsigned int pHeight);
int create_color_box(LayerList *ll,
                     ColorBox *cbox,
                     int pTileset,
                     unsigned int pWidth, unsigned int pHeight,
                     const unsigned int *pattern,
                     unsigned int wWidth, unsigned int wHeight,
                     unsigned int tWidth, unsigned int tHeight,
                     unsigned int scale, unsigned int rate);
int free_color_box(LayerList *ll, ColorBox *cbox);
int update_color_boxes(LayerList *ll,
                       ColorBox *cbox, unsigned int count,
                       unsigned int wWidth, unsigned int wHeight,
                       unsigned int scale);
int draw_color_boxes(LayerList *ll,
                     ColorBox *cbox, unsigned int count,
                     unsigned int scale);
