#include "extramath.h"
#include "tilemap.h"

#define CAT_OFFSCREEN_DIST_FACTOR (0.1)

/* i don't knwo what i'm doing */
float angle_from_xy(float x, float y) {
    if(x == 0.0) {
        if(y < 0.0) {
            return(M_PI);
        } else if(y >= 0.0) {
            return(0.0);
        }
    } else if(y == 0.0) {
        if(x < 0.0) {
            return(M_PI * 0.5);
        } else if(x > 0.0) {
            return(M_PI * 1.5);
        }
    } else if(x > 0.0 && y > 0.0) {
        if(x < y) {
            return((M_PI * 2.0) - atanf(x / y));
        } else {
            return((M_PI * 1.5) + atanf(y / x));
        }
    } else if(x < 0.0 && y > 0.0) {
        x = -x;
        if(x < y) {
            return(atanf(x / y));
        } else {
            return((M_PI * 0.5) - atanf(y / x));
        }
    } else if(x > 0.0 && y < 0.0) {
        y = -y;
        if(x < y) {
            return(M_PI + atanf(x / y));
        } else {
            return((M_PI * 1.5) - atanf(y / x));
        }
    }

    x = -x;
    y = -y;
    if(x < y) {
        return(M_PI - atanf(x / y));
    }
    return((M_PI * 0.5) + atanf(y / x));
}

float radian_to_degree(float radian) {
    return(radian / (M_PI * 2) * 360.0);
}

float velocity_from_xy(float x, float y) {
    return(sqrtf(powf(x, 2) + powf(y, 2)));
}

float distance(float x1, float y1, float x2, float y2) {
    if(x1 > x2) {
        if(y1 > y2) {
            return(velocity_from_xy(x1 - x2, y1 - y2));
        } else {
            return(velocity_from_xy(x1 - x2, y2 - y1));
        }
    }
    if(y1 > y2) {
        return(velocity_from_xy(x2 - x1, y1 - y2));
    }
    return(velocity_from_xy(x2 - x1, y2 - y1));
}

/* still have no idea */
void xy_from_angle(float *x, float *y, float angle) {
    *x = -sin(angle);
    *y = cos(angle);
}

float find_object_velocity(float curdist, float angle,
                           int x, int y,
                           int width, int height,
                           float velocity, unsigned int rate) {
    velocity = velocity * rate / MILLISECOND;
    if(x < 0) {
        if(y < 0) {
            if(angle > M_PI * 1.5 && angle <= M_PI * 1.75) {
                float distance = sqrt(pow(-x, 2) + pow(-y, 2));
                return(SCALE(angle,
                             M_PI * 1.5, M_PI * 1.75,
                             0, distance * CAT_OFFSCREEN_DIST_FACTOR)
                       + velocity);
            } else if(angle > M_PI * 1.75 && angle <= M_PI * 2.0) {
                float distance = sqrt(pow(-x, 2) + pow(-y, 2));
                return(SCALEINV(angle,
                                M_PI * 1.75, M_PI * 2.0,
                                0, distance * CAT_OFFSCREEN_DIST_FACTOR)
                       + velocity);
            } else {
                return(velocity);
            }
        } else if(y > height) {
            if(angle > M_PI && angle <= M_PI * 1.25) {
                float distance = sqrt(pow(-x, 2) + pow(y - height, 2));
                return(SCALE(angle,
                             M_PI, M_PI * 1.25,
                             0, distance * CAT_OFFSCREEN_DIST_FACTOR)
                       + velocity);
            } else if(angle > M_PI * 1.25 && angle <= M_PI * 1.5) {
                float distance = sqrt(pow(-x, 2) + pow(y - height, 2));
                return(SCALEINV(angle,
                                M_PI * 1.25, M_PI * 1.5,
                                0, distance * CAT_OFFSCREEN_DIST_FACTOR)
                       + velocity);
            } else {
                return(velocity);
            }
        } else {
            if(angle > M_PI && angle <= M_PI * 1.5) {
                return(SCALE(angle,
                             M_PI, M_PI * 1.5,
                             0, -x * CAT_OFFSCREEN_DIST_FACTOR)
                       + velocity);
            } else if(angle > M_PI * 1.5 && angle <= M_PI * 2.0) {
                return(SCALEINV(angle,
                                M_PI * 1.5, M_PI * 2.0,
                                0, -x * CAT_OFFSCREEN_DIST_FACTOR)
                       + velocity);
            } else {
                return(velocity);
            }
        }
    } else if(x > width) { 
        if(y < 0) {
            if(angle > 0 && angle <= M_PI * 0.25) {
                float distance = sqrt(pow(x - width, 2) + pow(-y, 2));
                return(SCALE(angle,
                             0, M_PI * 0.25,
                             0, distance * CAT_OFFSCREEN_DIST_FACTOR)
                       + velocity);
            } else if(angle > M_PI * 0.25 && angle <= M_PI * 0.5) {
                float distance = sqrt(pow(x - width, 2) + pow(-y, 2));
                return(SCALEINV(angle,
                                M_PI * 0.25, M_PI * 0.5,
                                0, distance * CAT_OFFSCREEN_DIST_FACTOR)
                       + velocity);
            } else {
                return(velocity);
            }
        } else if(y > height) {
            if(angle > M_PI * 0.5 && angle <= M_PI * 0.75) {
                float distance = sqrt(pow(x - width, 2) + pow(y - height, 2));
                return(SCALE(angle,
                             M_PI * 0.5, M_PI * 0.75,
                             0, distance * CAT_OFFSCREEN_DIST_FACTOR)
                       + velocity);
            } else if(angle > M_PI * 0.75 && angle <= M_PI) {
                float distance = sqrt(pow(x - width, 2) + pow(y - height, 2));
                return(SCALEINV(angle,
                                M_PI * 0.75, M_PI,
                                0, distance * CAT_OFFSCREEN_DIST_FACTOR)
                       + velocity);
            } else {
                return(velocity);
            }
        } else {
            if(angle > 0 && angle <= M_PI * 0.5) {
                return(SCALE(angle,
                             0, M_PI * 0.5,
                             0, (x - width) * CAT_OFFSCREEN_DIST_FACTOR)
                       + velocity);
            } else if(angle > M_PI * 0.5 && angle <= M_PI) {
                return(SCALEINV(angle,
                                M_PI * 0.5, M_PI,
                                0, (x - width) * CAT_OFFSCREEN_DIST_FACTOR)
                       + velocity);
            } else {
                return(velocity);
            }
        }
    } else if(y < 0) {
        if(angle > 0 && angle <= M_PI * 0.5) {
            return(SCALEINV(angle,
                         0, M_PI * 0.5,
                         0, -y * CAT_OFFSCREEN_DIST_FACTOR)
                   + velocity);
        } else if(angle > M_PI * 1.5 && angle <= M_PI * 2.0) {
            return(SCALEINV(angle,
                            M_PI * 1.5, M_PI,
                            0, -y * CAT_OFFSCREEN_DIST_FACTOR)
                   + velocity);
        } else {
            return(velocity);
        }
    } else if(y > height) {
        if(angle > M_PI * 0.5 && angle <= M_PI) {
            return(SCALE(angle,
                         M_PI * 0.5, M_PI,
                         0, (y - height) * CAT_OFFSCREEN_DIST_FACTOR)
                   + velocity);
        } else if(angle > M_PI && angle <= M_PI * 1.5) {
            return(SCALEINV(angle,
                            M_PI, M_PI * 1.5,
                            0, (y - height) * CAT_OFFSCREEN_DIST_FACTOR)
                   + velocity);
        } else {
            return(velocity);
        }
    } else if(curdist > velocity) {
        return(velocity);
    }
    return(curdist);
}

Uint32 color_from_angle(float angle,
                        unsigned int min,
                        unsigned int max) {
    const float COLORDIV = ((M_PI * 2.0) / 6.0);

    if(angle >= 0.0 && angle < COLORDIV) {
        return(TILEMAP_COLOR(max,
                             min,
                             (unsigned int)SCALEINV(angle,
                                                    0.0, COLORDIV,
                                                    (float)min, (float)max),
                             255));
    } else if(angle >= COLORDIV &&
       angle < COLORDIV * 2.0) {
        return(TILEMAP_COLOR(max,
                             (unsigned int)SCALE(angle,
                                                 COLORDIV, COLORDIV * 2.0,
                                                 (float)min, (float)max),
                             min,
                             255));
    } else if(angle >= COLORDIV * 2.0 &&
       angle < COLORDIV * 3.0) {
        return(TILEMAP_COLOR((unsigned int)SCALEINV(angle,
                                                    COLORDIV * 2.0, COLORDIV * 3.0,
                                                    (float)min, (float)max),
                             max,
                             min,
                             255));
    } else if(angle >= COLORDIV * 3.0 &&
       angle < COLORDIV * 4.0) {
        return(TILEMAP_COLOR(min,
                             max,
                             (unsigned int)SCALE(angle,
                                                 COLORDIV * 3.0, COLORDIV * 4.0,
                                                 (float)min, (float)max),
                             255));
    } else if(angle >= COLORDIV * 4.0 &&
       angle < COLORDIV * 5.0) {
        return(TILEMAP_COLOR(min,
                             (unsigned int)SCALEINV(angle,
                                                    COLORDIV * 4.0, COLORDIV * 5.0,
                                                    (float)min, (float)max),
                             max,
                             255));
    }
    return(TILEMAP_COLOR((unsigned int)SCALE(angle,
                                             COLORDIV * 5.0, COLORDIV * 6.0,
                                             (float)min, (float)max),
                         min,
                         max,
                         255));
}

float volume_from_db(float db) {
    if(db < 0.0) {
        return(powf(10.0, db / 10.0));
    }
    return(1.0 / powf(10.0, -db / 10.0));
}
