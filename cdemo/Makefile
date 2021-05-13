OBJS   = vprintf_cb.o testgfx.o testaudio.o extramath.o text.o test.o
TARGET = test
CFLAGS = `pkg-config sdl2 --cflags` -I.. -D_GNU_SOURCE -Wall -Wextra -Wno-unused-parameter -ggdb -Og
LDFLAGS = `pkg-config sdl2 --libs` -lm -L.. -lcrustygame

$(TARGET): $(OBJS)
	$(CC) $(LDFLAGS) -o $(TARGET) $(OBJS)

all: $(TARGET)

clean:
	rm -f $(TARGET) $(OBJS)

.PHONY: clean
