typedef void (*log_cb_return_t)(void *priv, const char *str);

void log_cb_helper(log_cb_return_t ret, void *priv,
                   const char *fmt, ...);
