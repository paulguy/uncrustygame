#include <stdarg.h>
#include <limits.h>

#include "text.h"

void ascii_to_int(unsigned int *dst,
                  const char *src,
                  unsigned int len) {
    unsigned int i;

    for(i = 0; i < len; i++) {
        dst[i] = (unsigned int)(src[i]);
    }
}

int print_to_tilemap(LayerList *ll,
                     unsigned int tilemap,
                     unsigned int x,
                     unsigned int y,
                     const char *text) {
    unsigned int len = strlen(text);
    unsigned int textTilemap[len];

    /* convert the char array to a tilemap */
    ascii_to_int(textTilemap, text, len);
    /* apply it */
    if(tilemap_set_tilemap_map(ll, tilemap,
                               x, y,
                               len,
                               len, 1,
                               textTilemap, len) < 0) {
        fprintf(stderr, "Failed to print to tilemap.\n");
        return(-1);
    }
    if(tilemap_update_tilemap(ll, tilemap,
                              x, y,
                              len, 1) < 0) {
        fprintf(stderr, "Failed to update hud tilemap.\n");
        return(-1);
    }

    return(0);
}

int printf_to_tilemap(LayerList *ll,
                      unsigned int tilemap,
                      unsigned int x,
                      unsigned int y,
                      const char *fmt,
                      ...) {
    va_list ap;

    va_start(ap, fmt);
    int len = vsnprintf(NULL, 0, fmt, ap);
    va_end(ap);
    if(len < 0) {
        fprintf(stderr, "Failed to get string length.\n");
        return(-1);
    }
    /* just use the stack for simplicity */
    char text[len + 1];
    unsigned int textTilemap[len];

    va_start(ap, fmt);
    if(vsnprintf(text, len + 1, fmt, ap) < len) {
        fprintf(stderr, "Failed to printf to text buf.\n");
        return(-1);
    }
    va_end(ap);

    /* convert the char array to a tilemap */
    ascii_to_int(textTilemap, text, len);
    /* apply it */
    if(tilemap_set_tilemap_map(ll, tilemap,
                               x, y,
                               len,
                               len, 1,
                               textTilemap, len) < 0) {
        fprintf(stderr, "Failed to printf to tilemap.\n");
        return(-1);
    }
    if(tilemap_update_tilemap(ll, tilemap,
                              x, y,
                              len, 1) < 0) {
        fprintf(stderr, "Failed to update hud tilemap.\n");
        return(-1);
    }

    return(len);
}

int ascii_wrap_to_int(unsigned int *dst,
                      const char *src,
                      unsigned int srclen,
                      unsigned int dstwidth,
                      unsigned int *dstheight) {
    unsigned int temp;
    unsigned int i, x, y;
    unsigned int wordstart;
    unsigned int wordend;
    unsigned int wordlen;
    int stopCopying;

    if(dstheight == NULL) {
        temp = UINT_MAX;
        dstheight = &temp;
    }

    x = 0; y = 0;
    for(i = 0; i < srclen; i++) {
        /* find start of a word */
        stopCopying = 0;
        for(wordstart = i; wordstart < srclen; wordstart++) {
            if(stopCopying == 0 && src[wordstart] == ' ') {
                if(dst != NULL) {
                    dst[(y * dstwidth) + x] = ' ';
                }
                x++;
                /* at the end of a line, go to the next, but stop copying
                 * spaces */
                if(x == dstwidth) {
                    x = 0;
                    y++;
                    if(y == *dstheight) {
                        return(wordstart);
                    }
                    stopCopying = 1;
                }
            } else if(src[wordstart] == '\n') {
                x = 0;
                y++;
                if(y == *dstheight) {
                    return(wordstart);
                }
                stopCopying = 0;
            } else {
                break;
            }
        }

        if(wordstart == srclen) {
            break;
        }

        /* find end of word */
        for(wordend = wordstart; wordend < srclen; wordend++) {
            if(src[wordend] == ' ' || src[wordend] == '\n') {
                break;
            }
        }

        wordlen = wordend - wordstart;
        /* if the word wouldn't fit, start a new line */
        if(wordlen > dstwidth - x) {
            x = 0;
            y++;
            if(y == *dstheight) {
                return(wordstart);
            }
        }
        for(i = wordstart; i < wordend; i++) {
            if(x == dstwidth) {
                x = 0;
                y++;
                if(y == *dstheight) {
                    return(i);
                }
            }
            if(dst != NULL) {
                dst[(dstwidth * y) + x] = (unsigned int)(src[i]);
            }
            x++;
        }
    }

    *dstheight = y;
    return(srclen);
}
