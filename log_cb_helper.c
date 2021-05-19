#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>

#include "log_cb_helper.h"

void log_cb_helper(log_cb_return_t ret, void *priv,
                   const char *fmt, ...) {
    va_list ap;
    unsigned int len, got;
    char *str;

    va_start(ap, fmt);
    len = vsnprintf(NULL, 0, fmt, ap);
    va_end(ap);

    str = malloc(len + 1);
    if(str == NULL) {
        ret(priv, "Failed to allocate memory for log string.\n");
        return;
    }

    va_start(ap, fmt);
    got = vsnprintf(str, len + 1, fmt, ap);
    va_end(ap);
    if(got < len) {
        free(str);
        ret(priv, "Failed to create log string.\n");
        return;
    }

    ret(priv, str);

    free(str);

    return;
}
