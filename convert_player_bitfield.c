#include <stdlib.h>
#include <stdio.h>

const unsigned int CONVERSIONS[] = {
    0x000001, 0x00000004,
    0x000002, 0x00000008,
    0x000004, 0x00000010,
    0x000008, 0x00000020,
    0x000010, 0x00000040,
    0x000020, 0x00000080,
    0x000040, 0x00000100,
    0x000080, 0x00020000,
    0x000100, 0x00040000,
    0x000200, 0x00080000,
    0x000400, 0x00100000,
    0x000800, 0x00200000,
    0x001000, 0x00400000,
    0x002000, 0x00800000,
    0x004000, 0x01000000,
    0x008000, 0x02000000,
    0x010000, 0x04000000,
    0x020000, 0x08000000,
    0x040000, 0x10000000,
    0x080000, 0x20000000,
    0x100000, 0x40000000,
    0x200000, 0x80000000
};

#define VALID_BITS (0x3FFFFF)

int main(int argc, char **argv) {
    unsigned int bitfield;
    unsigned int bitfield2 = 0;
    unsigned int i;

    if(argc < 2) {
        fprintf(stderr, "USAGE: %s <hex>\n", argv[0]);
        exit(EXIT_FAILURE);
    }

    if(sscanf(argv[1], "%x", &bitfield) < 1) {
        fprintf(stderr, "Failed to read hex.\n");
        exit(EXIT_FAILURE);
    }

    if(bitfield & ~VALID_BITS) {
        fprintf(stderr, "Unknown bits set %x.\n", bitfield & ~VALID_BITS);
        exit(EXIT_FAILURE);
    }

    for(i = 0; i < sizeof(CONVERSIONS) / sizeof(unsigned int); i += 2){
        if(bitfield & CONVERSIONS[i]) {
            bitfield2 |= CONVERSIONS[i+1];
        }
    }

    printf("%x\n", bitfield2);

    exit(EXIT_SUCCESS);
}
