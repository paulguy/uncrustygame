#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>

#include "log_cb_helper.h"

int log_cb_helper(log_cb_return_t ret,
                  const char *fmt, ...) {
    va_list ap;
    unsigned int len, got;
    char *str;

    va_start(ap, fmt);
    len = vsnprintf(NULL, 0, fmt, ap);
    va_end(ap);

    str = malloc(len + 1);
    if(str == NULL) {
        return(-1);
    }

    va_start(ap, fmt);
    got = vsnprintf(str, len + 1, fmt, ap);
    va_end(ap);
    if(got < len) {
        free(str);
        return(-1);
    }

    ret(str);

    free(str);

    return(0);
}
