#include <math.h>
#include <SDL.h>

#define MILLISECOND (1000)
#define NANOSECOND  (1000000000)

#define SCALE(VAL, SMIN, SMAX, DMIN, DMAX) \
    ((((VAL) - (SMIN)) / ((SMAX) - (SMIN)) * ((DMAX) - (DMIN))) + (DMIN))
#define SCALEINV(VAL, SMIN, SMAX, DMIN, DMAX) \
    ((DMAX) - (((VAL) - (SMIN)) / ((SMAX) - (SMIN)) * ((DMAX) - (DMIN))))
#define RANDRANGE(MIN, MAX) ((rand() % (MAX - MIN)) + MIN)
#define CENTER(OUTERW, INNERW) (((OUTERW) - (INNERW)) / 2)

float angle_from_xy(float x, float y);
float radian_to_degree(float radian);
float velocity_from_xy(float x, float y);
float distance(float x1, float y1, float x2, float y2);
void xy_from_angle(float *x, float *y, float angle);
float find_object_velocity(float curdist, float angle,
                           int x, int y,
                           int width, int height,
                           float velocity, unsigned int rate);
Uint32 color_from_angle(float angle,
                        unsigned int min,
                        unsigned int max);
float volume_from_db(float db);
