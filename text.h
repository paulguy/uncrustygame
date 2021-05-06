#include "tilemap.h"

void ascii_to_int(unsigned int *dst,
                  const char *src,
                  unsigned int len);
int print_to_tilemap(LayerList *ll,
                     unsigned int tilemap,
                     unsigned int x,
                     unsigned int y,
                     const char *text);
int printf_to_tilemap(LayerList *ll,
                      unsigned int tilemap,
                      unsigned int x,
                      unsigned int y,
                      const char *fmt,
                      ...);
int ascii_wrap_to_int(unsigned int *dst,
                      const char *src,
                      unsigned int srclen,
                      unsigned int dstwidth,
                      unsigned int *dstheight);
