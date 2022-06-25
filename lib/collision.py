from enum import Enum

class _NoHit(Exception):
    pass

class SpriteEdge(Enum):
    TopLeft = 0,
    Top = 1,
    TopRight = 2,
    Right = 3,
    BottomRight = 4,
    Bottom = 5,
    BottomLeft = 6,
    Left = 7

def _solid_hit(x, y, dx, dy, tw, th, t):
    if dx < 0.0:
        # set to tw so when it hits and comes back to here, it'll continue
        # rather than get stuck
        if x == 0.0:
            x = tw
        xdiff = -x
        if dy < 0.0:
            if y == 0.0:
                y = th
            ydiff = -y
            if dx > xdiff and dy > ydiff:
                return t, dx, dy
            slope = dy / dx
            if slope * xdiff < ydiff:
                return t, (1.0 / slope) * ydiff, ydiff
            else:
                return t, xdiff, slope * xdiff
        elif dy > 0.0:
            ydiff = th - y
            if dx > xdiff and dy < ydiff:
                return t, dx, dy
            slope = dy / dx
            if slope * xdiff > ydiff:
                return t, (1.0 / slope) * ydiff, ydiff
            else:
                return t, xdiff, slope * xdiff
        else:
            if dx > xdiff:
                return t, dx, 0.0
            return t, xdiff, 0.0
    if dx > 0.0:
        xdiff = tw - x
        if dy < 0.0:
            if y == 0.0:
                y = th
            ydiff = -y
            if dx < xdiff and dy > ydiff:
                return t, dx, dy
            slope = dy / dx
            if slope * xdiff < ydiff:
                return t, (1.0 / slope) * ydiff, ydiff
            else:
                return t, xdiff, slope * xdiff
        elif dy > 0.0:
            ydiff = th - y
            if dx < xdiff and dy < ydiff:
                return t, dx, dy
            slope = dy / dx
            if slope * xdiff > ydiff:
                return t, (1.0 / slope) * ydiff, ydiff
            else:
                return t, xdiff, slope * xdiff
        else:
            if dx < xdiff:
                return t, dx, 0.0
            return t, xdiff, 0.0
    else:
        if dy < 0.0:
            if y == 0.0:
                y = th
            ydiff = -y
            if dy > ydiff:
                return t, 0.0, dy
            return t, 0.0, ydiff
        elif dy > 0.0:
            ydiff = th - y
            if dy < ydiff:
                return t, 0.0, dy
            return t, 0.0, ydiff
        else:
            raise _NoHit()

def _box_hit(x, y, dx, dy, tw, th, edge, xb, yb, t1, t2, t3, t4):
    rx = dx
    ry = dy
    o1 = t1
    o2 = t2
    o3 = t3
    o4 = t4
    # assure the leading edge detects the collision with the part of the box
    # which isn't necessarily in the way of the ray, this assumes the sprite is
    # the tile size or larger!
    # pass None for no change, and just cast the ray.
    if edge == SpriteEdge.Bottom or edge == SpriteEdge.Top:
        t1 = o1 or o2
        t2 = t1
        t3 = o3 or o4
        t4 = t3
    elif edge == SpriteEdge.Left or edge == SpriteEdge.Right:
        t1 = o1 or o3
        t3 = t1
        t2 = o2 or o4
        t4 = t2
    elif edge == SpriteEdge.TopLeft:
        # i know this is a bit redundant but it makes what its doing a little
        # more obvious, which is, combining the rows and columns of the topleft
        # quadrant together
        t1 = (o1 or o2) or (o1 or o3)
        t2 = o2 or o4
        t3 = o3 or o4
    elif edge == SpriteEdge.TopRight:
        t2 = (o1 or o2) or (o2 or o4)
        t1 = o1 or o3
        t4 = o3 or o4
    elif edge == SpriteEdge.BottomLeft:
        t3 = (o1 or o3) or (o3 or o4)
        t1 = o1 or o2
        t4 = o2 or o4
    elif edge == SpriteEdge.BottomRight:
        t4 = (o2 or o4) or (o3 or o4)
        t2 = o1 or o2
        t3 = o1 or o3
    if dx < 0.0:
        # set to tw so when it hits and comes back to here, it'll continue
        # rather than get stuck
        if x == 0.0:
            x = tw
        xdiff = -x
        if dy < 0.0:
            if y == 0.0:
                y = th
            ydiff = -y
            slope = dy / dx
            if x < xb:
                if y < yb: # top left
                    if dx < xdiff or dy < ydiff:
                        if slope * xdiff < ydiff:
                            rx = (1.0 / slope) * ydiff
                            ry = ydiff
                        else:
                            rx = xdiff
                            ty = slope * xdiff
                else: # bottom left
                    if dx < xdiff or y + dy < yb:
                        if y + (slope * xdiff) < yb:
                            ry = by - y
                            rx = (1.0 / slope) * ry
                        else:
                            rx = xdiff
                            ry = slope * xdiff
            else:
                if y < yb: # top right
                    if x + dx < xb or dy < ydiff:
                        if slope * (xb - x) < ydiff:
                            rx = (1.0 / slope) * ydiff
                            ry = ydiff
                        else:
                            rx = xb - x
                            ry = slope * rx
                else: # bottom right
                    if x + dx < xb or y + dy < yb:
                        if y + (slope * (xb - x)) < yb:
                            ry = yb - y
                            rx = (1.0 / slope) * ry
                        else:
                            rx = xb - x
                            ry = slope * rx
        elif dy > 0.0:
            ydiff = th - y
            slope = dy / dx
            if x < xb:
                if y < yb:
                    if dx < xdiff or y + dy > yb:
                        if slope * xdiff > yb:
                            ry = yb - y
                            rx = (1.0 / slope) * ry
                        else:
                            rx = xdiff
                            ty = slope * xdiff
                else:
                    if dx < xdiff or dy > ydiff:
                        if slope * xdiff > ydiff:
                            rx = (1.0 / slope) * ydiff
                            ry = ydiff
                        else:
                            rx = xdiff
                            ry = slope * xdiff
            else:
                if y < yb:
                    if x + dx < xb or y + dy > yb:
                        if slope * (xb - x) > yb:
                            ry = yb - y
                            rx = (1.0 / slope) * ry
                        else:
                            rx = xb - x
                            ry = slope * rx
                else:
                    if x + dx < xb or dy > ydiff:
                        if slope * (xb - x) > ydiff:
                            rx = (1.0 / slope) * ydiff
                            ry = ydiff
                        else:
                            rx = xb - x
                            ry = slope * rx
        else:
            if x < xb:
                if dx < xdiff:
                    rx = xdiff
            else:
                if x + dx < xb:
                    rx = xb - x
    if dx > 0.0:
        xdiff = tw - x
        if dy < 0.0:
            if y == 0.0:
                y = th
            ydiff = -y
            if x < xb:
                if y < yb:
                    if x + dx > xb or dy < ydiff:
                        if slope * xb - x < ydiff:
                            rx = (1.0 / slope) * ydiff
                            ry = ydiff
                        else:
                            rx = xb - x
                            ty = slope * rx
                else:
                    if x + dx > xb or y + dy < yb:
                        if y + (slope * (xb - x)) < yb:
                            ry = by - y
                            rx = (1.0 / slope) * ry
                        else:
                            rx = xb - x
                            ry = slope * rx
            else:
                if y < yb:
                    if dx > xdiff or dy < ydiff:
                        if slope * xdiff < ydiff:
                            rx = (1.0 / slope) * ydiff
                            ry = ydiff
                        else:
                            rx = xdiff
                            ry = slope * xdiff
                else:
                    if dx > xdiff or y + dy < yb:
                        if y + (slope * xdiff) < yb:
                            ry = yb - y
                            rx = (1.0 / slope) * ry
                        else:
                            rx = xdiff
                            ry = slope * xdiff
        elif dy > 0.0:
            ydiff = th - y
            # TODO
        else:
            if dx < xdiff:
                return t, dx, dy
            return t, xdiff, 0.0
    else:
        if dy < 0.0:
            if y == 0.0:
                y = th
            ydiff = -y
            if dy > ydiff:
                return t, dx, dy
            return t, 0.0, ydiff
        elif dy > 0.0:
            ydiff = th - y
            if dy < ydiff:
                return t, dx, dy
            return t, 0.0, ydiff
        else:
            raise _NoHit()
    if x < xb:
        if y < yb:
            return t1, rx, ry
        else:
            return t2, rx, ry
    else:
        if y < yb:
            return t3, rx, ry
        else:
            return t4, rx, ry

# some highschool math I haven't done in a while and never fully grasped...
# y = ax + b
# y - b = ax
# x = (y - b)/a

# ax + b = cx + d
# ax + b - cx = d
# ax - cx = d - b
# (a - c)*x = d - b
# x = (d - b) / (a - c)

# a: player's slope
# a = dy / dx
# b: player's bias
# b = y
# c: slope's slope
# c = a
# d: slope's bias, advanced to the player's position
# d = b + (a * x)

# rotate
# y = ax + b -> x = (1/a)y - (1/a)b

# ix = ((b + (a * x)) - y) / ((dy / dx) - a)
# iy = ((dy / dx) * ix) + y

def _slope_hit(x, y, dx, dy, tw, th, edge, a, b, t1, t2):
    print("{} {} {} {}".format(x, y, dx, dy))
    rx = dx
    ry = dy
    # if the leading edge of the sprite is towards the "point" of a slope,
    # treat the collision as a rectangle rather than a slope so the corner
    # aligning with the top of the slope won't pass by the slope
    """
    if a > 0:
        if edge == SpriteEdge.TopLeft or \
           edge == SpriteEdge.Top or \
           edge == SpriteEdge.Left or \
           edge == SpriteEdge.BottomRight or \
           edge == SpriteEdge.Bottom or \
           edge == SpriteEdge.Right:
            if a > th / tw:
                return _box_hit(x, y, dx, dy, tw, th, edge,
                                (th - b) / a, 0.5,
                                t2, t1, t2, t1)
            else:
                return _box_hit(x, y, dx, dy, tw, th, edge,
                                0.5, (tw * a) + b,
                                t1, t1, t2, t2)
    else: # a <= 0:
        if edge == SpriteEdge.TopRight or \
           edge == SpriteEdge.Top or \
           edge == SpriteEdge.Right or \
           edge == SpriteEdge.BottomLeft or \
           edge == SpriteEdge.Bottom or \
           edge == SpriteEdge.Left:
            if a < -th / tw:
                return _box_hit(x, y, dx, dy, tw, th, edge,
                                b / a, 0.5,
                                t2, t1, t2, t1)
            else:
                return _box_hit(x, y, dx, dy, tw, th, edge,
                                0.5, b,
                                t1, t1, t2, t2)
                            """
    if dx < 0.0:
        # set to tw so when it hits and comes back to here, it'll continue
        # rather than get stuck
        if x == 0.0:
            x = tw
        xdiff = -x
        if dy < 0.0:
            if y == 0.0:
                y = th
            ydiff = -y
            slope = dy / dx
            try:
                # calculate intersection between movement and slope
                ix = ((b + (a * x)) - y) / (slope - a)
                iy = slope * ix
                # check to see if the intersection is within the tile and also
                # whether it's within the movement.
                if ix > dx and ix < 0 and \
                   iy > dy and iy < 0:
                    rx = ix
                    ry = iy
            except ZeroDivisionError:
                # paralell lines
                pass
            # if the computed movement falls out of bounds, calculate the
            # movement that would reach the edge of the bounds
            if rx < xdiff or ry < ydiff:
                hit = slope * xdiff
                if hit < 0:
                    rx = (1.0 / slope) * ydiff
                    ry = ydiff
                else:
                    rx = xdiff
                    ry = hit
        elif dy > 0.0:
            ydiff = th - y
            slope = dy / dx
            try:
                ix = ((b + (a * x)) - y) / (slope - a)
                iy = slope * ix
                if ix > dx and ix < 0 and \
                   iy > 0  and iy < dy:
                    rx = ix
                    ry = iy
            except ZeroDivisionError:
                pass
            if rx < xdiff or ry > ydiff:
                hit = slope * xdiff
                if hit > ydiff:
                    rx = (1.0 / slope) * ydiff
                    ry = ydiff
                else:
                    rx = xdiff
                    ry = hit
        else:
            try:
                # calculate the value of X when crossing a line at Y
                ix = ((y - b) / a) - x
                # determine is the Y crossing happened at an X value within the
                # movement
                if ix > dx and ix < 0:
                    rx = ix
            except ZeroDivisionError:
                pass
            if rx < xdiff:
                rx = xdiff
    elif dx > 0.0:
        xdiff = tw - x
        if dy < 0.0:
            if y == 0.0:
                y = th
            ydiff = -y
            slope = dy / dx
            try:
                ix = ((b + (a * x)) - y) / (slope - a)
                iy = slope * ix
                if ix > 0  and ix < dx and \
                   iy > dy and iy < 0:
                    rx = ix
                    ry = iy
            except ZeroDivisionError:
                pass
            if rx > xdiff or ry < ydiff:
                hit = slope * xdiff
                if hit < 0:
                    rx = (1.0 / slope) * ydiff
                    ry = ydiff
                else:
                    rx = xdiff
                    ry = hit
        elif dy > 0.0:
            ydiff = th - y
            slope = dy / dx
            try:
                ix = ((b + (a * x)) - y) / (slope - a)
                iy = slope * ix
                if ix > 0 and ix < dx and \
                   iy > 0 and iy < dy:
                    rx = ix
                    ry = iy
            except ZeroDivisionError:
                pass
            if rx > xdiff or ry > ydiff:
                hit = slope * xdiff
                if hit > ydiff:
                    rx = (1.0 / slope) * ydiff
                    ry = ydiff
                else:
                    rx = xdiff
                    ry = hit
        else:
            try:
                ix = abs((y - b) / a) - x
                if ix > 0 and ix < dx:
                    rx = ix
            except ZeroDivisionError:
                pass
            if rx > xdiff:
                rx = xdiff
    else:
        if dy < 0.0:
            if y == 0.0:
                y = th
            ydiff = -y
            iy = (a * x + b) - y
            if iy > dy and iy < 0:
                ry = iy
            if ry < ydiff:
                ry = ydiff
        elif dy > 0.0:
            ydiff = th - y
            iy = (a * x + b) - y
            if iy > 0 and iy < dy:
                ry = iy
            if ry > ydiff:
                ry = ydiff
        else:
            raise _NoHit()
        """
        This might be overkill and it seems to work otherwise and i'm not sure
        what this was originally solving
    if y > a * x + b:
        if y + ry < a * (x + rx) + b:
            return t1, rx, ry
        else:
            return t2, rx, ry
    else:
        if y + ry <= a * (x + rx) + b:
            return t1, rx, ry
        else:
            return t2, rx, ry
       """ 
    if y > a * x + b:
        return t2, rx, ry
    else:
        return t1, rx, ry

TILE_CALLS = [
    lambda x, y, dx, dy, tw, th, edge: \
        _solid_hit(x, y, dx, dy, tw, th, False),
    lambda x, y, dx, dy, tw, th, edge: \
        _solid_hit(x, y, dx, dy, tw, th, True),
    # start basic slopes
    lambda x, y, dx, dy, tw, th, edge: \
        _slope_hit(x, y, dx, dy, tw, th, edge,
                   -1, th, False, True),
    lambda x, y, dx, dy, tw, th, edge: \
        _slope_hit(x, y, dx, dy, tw, th, edge,
                   1, 0, False, True),
    lambda x, y, dx, dy, tw, th, edge: \
        _slope_hit(x, y, dx, dy, tw, th, edge,
                   -1, th, True, False),
    lambda x, y, dx, dy, tw, th, edge: \
        _slope_hit(x, y, dx, dy, tw, th, edge,
                   1, 0, True, False),
    lambda x, y, dx, dy, tw, th, edge: \
        _slope_hit(x, y, dx, dy, tw, th, edge,
                   -0.5, th, False, True),
    lambda x, y, dx, dy, tw, th, edge: \
        _slope_hit(x, y, dx, dy, tw, th, edge,
                   -0.5, th / 2, False, True),
    lambda x, y, dx, dy, tw, th, edge: \
        _slope_hit(x, y, dx, dy, tw, th, edge,
                   0.5, 0, False, True),
    lambda x, y, dx, dy, tw, th, edge: \
        _slope_hit(x, y, dx, dy, tw, th, edge,
                   0.5, th / 2, False, True),
    lambda x, y, dx, dy, tw, th, edge: \
        _slope_hit(x, y, dx, dy, tw, th, edge,
                   -0.5, th, True, False),
    lambda x, y, dx, dy, tw, th, edge: \
        _slope_hit(x, y, dx, dy, tw, th, edge,
                   -0.5, th / 2, True, False),
    lambda x, y, dx, dy, tw, th, edge: \
        _slope_hit(x, y, dx, dy, tw, th, edge,
                   0.5, 0, True, False),
    lambda x, y, dx, dy, tw, th, edge: \
        _slope_hit(x, y, dx, dy, tw, th, edge,
                   0.5, th / 2, True, False),
    lambda x, y, dx, dy, tw, th, edge: \
        _slope_hit(x, y, dx, dy, tw, th, edge,
                   -2, th, False, True),
    lambda x, y, dx, dy, tw, th, edge: \
        _slope_hit(x, y, dx, dy, tw, th, edge,
                   -2, th * 2, False, True),
    lambda x, y, dx, dy, tw, th, edge: \
        _slope_hit(x, y, dx, dy, tw, th, edge,
                   2, 0, False, True),
    lambda x, y, dx, dy, tw, th, edge: \
        _slope_hit(x, y, dx, dy, tw, th, edge,
                   2, -th, False, True),
    lambda x, y, dx, dy, tw, th, edge: \
        _slope_hit(x, y, dx, dy, tw, th, edge,
                   -2, th, True, False),
    lambda x, y, dx, dy, tw, th, edge: \
        _slope_hit(x, y, dx, dy, tw, th, edge,
                   -2, th * 2, True, False),
    lambda x, y, dx, dy, tw, th, edge: \
        _slope_hit(x, y, dx, dy, tw, th, edge,
                   2, 0, True, False),
    lambda x, y, dx, dy, tw, th, edge: \
        _slope_hit(x, y, dx, dy, tw, th, edge,
                   2, -th, True, False),
    # start basic partial blocks
    lambda x, y, dx, dy, tw, th, edge: \
        _box_hit(x, y, dx, dy, tw, th, edge,
                 0.5, 0.5, True, False, True, False),
    lambda x, y, dx, dy, tw, th, edge: \
        _box_hit(x, y, dx, dy, tw, th, edge,
                 0.5, 0.5, False, True, False, True),
    lambda x, y, dx, dy, tw, th, edge: \
        _box_hit(x, y, dx, dy, tw, th, edge,
                 0.5, 0.5, True, True, False, False),
    lambda x, y, dx, dy, tw, th, edge: \
        _box_hit(x, y, dx, dy, tw, th, edge,
                 0.5, 0.5, False, False, True, True),
    lambda x, y, dx, dy, tw, th, edge: \
        _box_hit(x, y, dx, dy, tw, th, edge,
                 0.5, 0.5, True, False, False, False),
    lambda x, y, dx, dy, tw, th, edge: \
        _box_hit(x, y, dx, dy, tw, th, edge,
                 0.5, 0.5, False, True, False, False),
    lambda x, y, dx, dy, tw, th, edge: \
        _box_hit(x, y, dx, dy, tw, th, edge,
                 0.5, 0.5, False, False, True, False),
    lambda x, y, dx, dy, tw, th, edge: \
        _box_hit(x, y, dx, dy, tw, th, edge,
                 0.5, 0.5, False, False, False, True),
]

def first_hit(x, y, dx, dy, tw, th, val, edge, buffer, bw):
    print(" {} {} {} {}".format(x, y, dx, dy))
    nx = 0
    ny = 0
    try:
        curtile = buffer[int(y / th) * bw + int(x / tw)]
    except IndexError:
        raise IndexError("Out of bounds: {} {}", int(y / th), int(x / tw))
    while True:
        try:
            hit, hx, hy = TILE_CALLS[curtile]((x + nx) % tw,
                                              (y + ny) % th,
                                              dx - nx, dy - ny,
                                              tw, th, edge)
            print("{} {} {}".format(hit, hx, hy))
            if hit != val:
                return hit, nx, ny
            nx += hx
            ny += hy
            px = int((x + nx) / tw)
            if dx < 0 and (x + nx) % tw == 0:
                px -= 1
            py = int((y + ny) / th)
            if dy < 0 and (y + ny) % th == 0:
                py -= 1
            try:
                curtile = buffer[py * bw + px]
            except IndexError:
                raise IndexError("Out of bounds: {} {}", px, py)
        except _NoHit:
            break
    # don't modify dx or dy to avoid rounding errors
    return val, dx, dy
