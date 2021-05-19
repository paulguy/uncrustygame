#include <stdio.h>
#include <stdarg.h>

void log_cb(void *priv, const char *str) {
    FILE *out = priv;

    fprintf(out, str);
}
