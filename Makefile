OBJS   = log_cb_helper.o tilemap.o synth.o
TARGET = libcrustygame.so
CFLAGS = `pkg-config sdl2 --cflags` -D_GNU_SOURCE -fPIC -Wall -Wextra -Wno-unused-parameter -ggdb -Og
LDFLAGS = -shared `pkg-config sdl2 --libs` -lm

$(TARGET): $(OBJS)
	$(CC) $(LDFLAGS) -o $(TARGET) $(OBJS)

all: $(TARGET)

clean:
	rm -f $(TARGET) $(OBJS)

.PHONY: clean
