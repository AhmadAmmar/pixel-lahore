"""Pixel Lahore: a procedural 8-bit animation of Badshahi Masjid, written from first principles.

The picture is a 160 x 120 grid of palette indices (one byte per pixel, as on 8-bit machines).
Every part of the mosque is a function of a few numbers (a component), so the scene is data:
a list of components, mirrored about the centre line. Motion comes from simple physics:
the sun moves on a circle, pigeons follow three flocking rules, and a kite hangs on an
elastic string in a gusty wind, integrated with semi-implicit Euler steps.

    python pixel_lahore.py            still image and animated GIF in ../out/
"""
from dataclasses import dataclass, field
from pathlib import Path
import math

import numpy as np
from PIL import Image

W, H = 160, 120          # canvas size in pixels
GROUND = 104             # y of the ground line (y grows downwards, as on screen)
SCALE = 4                # each pixel becomes a 4 x 4 block in the saved image

# ---------------------------------------------------------------- palette
# Sixteen colours, chosen for Lahore: Mughal red sandstone, white marble, lawn and sky.
PALETTE = [
    (16, 20, 43),    # 0  night
    (29, 43, 83),    # 1  deep blue
    (94, 58, 110),   # 2  dusk purple
    (90, 150, 210),  # 3  day sky
    (170, 210, 235), # 4  pale sky
    (240, 140, 60),  # 5  sunset orange
    (255, 220, 110), # 6  sun yellow
    (240, 236, 225), # 7  white marble
    (190, 185, 175), # 8  marble in shade
    (170, 62, 45),   # 9  red sandstone
    (115, 38, 32),   # 10 sandstone in shade
    (40, 20, 22),    # 11 dark doorway
    (70, 120, 60),   # 12 lawn
    (40, 75, 40),    # 13 lawn in shade
    (200, 150, 110), # 14 brick path
    (12, 10, 14),    # 15 black
]
NIGHT = {9: 10, 7: 8, 12: 13, 14: 2, 8: 10, 10: 11}   # palette swap for a building at night

# 4 x 4 Bayer matrix: thresholds for ordered dithering between two colours
BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16

Y, X = np.mgrid[0:H, 0:W]   # the row and column number of every pixel


# ---------------------------------------------------------------- primitives
def new_canvas(colour=0):
    return np.full((H, W), colour, dtype=np.uint8)


def put_pixel(c, x, y, col):
    if 0 <= x < W and 0 <= y < H:
        c[int(y), int(x)] = col


def line(c, x0, y0, x1, y1, col):
    """Bresenham's line: step one pixel at a time, choosing the pixel nearest the true line."""
    x0, y0, x1, y1 = int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1))
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx + dy
    while True:
        put_pixel(c, x0, y0, col)
        if x0 == x1 and y0 == y1:
            return
        e2 = 2 * err
        if e2 >= dy:
            err += dy; x0 += sx
        if e2 <= dx:
            err += dx; y0 += sy


def fill(c, mask, col):
    c[mask] = col


def rect(x0, y0, x1, y1):
    """Mask of the pixels with x0 <= x < x1 and y0 <= y < y1."""
    return (X >= x0) & (X < x1) & (Y >= y0) & (Y < y1)


def disc(cx, cy, r):
    return (X - cx) ** 2 + (Y - cy) ** 2 <= r * r


def pointed_arch(cx, spring, bottom, w, k=0.5):
    """A two-centred (Mughal) arch: the intersection of two discs whose centres sit k*w/2 either side of cx.

    Each disc has radius w/2 + k*w/2, so it passes through the far springing point.
    k = 0 gives a round arch, k = 1 an equilateral pointed arch.
    """
    off = k * w / 2
    r = w / 2 + off
    top = disc(cx + off, spring, r) & disc(cx - off, spring, r) & (Y <= spring)
    return top | rect(cx - w / 2, spring, cx + w / 2, bottom)


def onion(cx, base, R, h):
    """Onion dome: half-width R(1-u)^0.7 (1+1.2u) at height fraction u, widest about a third of the way up."""
    u = (base - Y) / h
    hw = R * np.clip(1 - u, 0, 1) ** 0.7 * (1 + 1.2 * u) * (0.8 + 0.2 * np.clip(u / 0.15, 0, 1))  # pinched neck
    return (u >= 0) & (u <= 1) & (np.abs(X - cx + 0.5) <= hw)


# ---------------------------------------------------------------- components
@dataclass
class Dome:
    cx: float; base: float; R: float; h: float; drum: float = 6

    def draw(self, c):
        fill(c, rect(self.cx - self.R * 0.8, self.base, self.cx + self.R * 0.8, self.base + self.drum), 9)
        m = onion(self.cx, self.base, self.R, self.h)
        fill(c, m, 7)
        fill(c, m & (X > self.cx + self.R * 0.3), 8)               # light comes from the left
        top = self.base - self.h
        line(c, self.cx, top, self.cx, top - 5, 6)                 # gilded finial (kalash): a spire with a ball
        fill(c, disc(self.cx, top - 2, 1.2), 6)


@dataclass
class Minaret:
    x: float; top: float; w: float = 6; bottom: float = GROUND - 8; balconies: tuple = (0.3, 0.6)

    def draw(self, c):
        x0, x1 = self.x - self.w / 2, self.x + self.w / 2
        fill(c, rect(x0, self.top, x1, self.bottom), 9)
        fill(c, rect(x1 - 2, self.top, x1, self.bottom), 10)
        for yy in range(int(self.top) + 3, int(self.bottom), 6):   # white marble bands
            fill(c, rect(x0, yy, x1, yy + 1), 7)
        height = self.bottom - self.top
        for f in self.balconies:                                   # balconies stick out one pixel each side
            yy = self.top + f * height
            fill(c, rect(x0 - 1, yy, x1 + 1, yy + 2), 8)
        # chhatri: a little pavilion of four posts and a dome on top
        fill(c, rect(x0 - 1, self.top - 1, x1 + 1, self.top + 1), 8)
        for px in (x0, x1 - 1):
            fill(c, rect(px, self.top - 5, px + 1, self.top - 1), 7)
        fill(c, onion(self.x, self.top - 5, self.w / 2 + 0.5, 5), 7)
        line(c, self.x, self.top - 11, self.x, self.top - 13, 6)


@dataclass
class Arch:
    cx: float; spring: float; bottom: float; w: float; frame: float = 2; k: float = 0.5; inner: int = 11

    def draw(self, c):
        fill(c, pointed_arch(self.cx, self.spring, self.bottom, self.w + 2 * self.frame, self.k), 7)
        fill(c, pointed_arch(self.cx, self.spring, self.bottom, self.w, self.k), self.inner)


@dataclass
class Block:
    """A wall: a rectangle of sandstone with a row of merlons along the top."""
    x0: float; y0: float; x1: float; y1: float; merlons: bool = True

    def draw(self, c):
        fill(c, rect(self.x0, self.y0, self.x1, self.y1), 9)
        fill(c, rect(self.x0, self.y0, self.x1, self.y0 + 1), 7)
        if self.merlons:
            for xx in range(int(self.x0), int(self.x1), 3):
                fill(c, rect(xx, self.y0 - 2, xx + 2, self.y0), 9)


def mirror(comp):
    """The same component reflected about the centre line x = W/2."""
    d = dict(comp.__dict__)
    key = "cx" if "cx" in d else "x" if "x" in d else None
    if key:
        d[key] = W - d[key]
    else:
        d["x0"], d["x1"] = W - d["x1"], W - d["x0"]
    return type(comp)(**d)


def badshahi():
    """The front of Badshahi Masjid (1673) as a list of components, back to front, left half mirrored."""
    left = [
        Minaret(x=14, top=24, w=7, balconies=(0.25, 0.5, 0.75)),   # corner minaret of the courtyard
        Dome(cx=46, base=52, R=9, h=16),
        Block(30, 60, 66, GROUND - 8),
        Minaret(x=30, top=44, w=4, balconies=(0.4,)),
        Arch(cx=40, spring=76, bottom=GROUND - 8, w=6),
        Arch(cx=54, spring=76, bottom=GROUND - 8, w=6),
    ]
    centre = [
        Dome(cx=80, base=38, R=13, h=22),
        Block(64, 42, 96, GROUND - 8),                               # the great iwan (portal)
        Arch(cx=80, spring=62, bottom=GROUND - 8, w=20, frame=3),
        Arch(cx=80, spring=70, bottom=GROUND - 8, w=10, frame=1, inner=10),
    ]
    comps = []
    for comp in left:
        comps += [comp, mirror(comp)]
    return comps[:4] + centre[:1] + comps[4:] + centre[1:]           # side domes and centre dome behind the walls


# ---------------------------------------------------------------- sky, sun and light
def sun_position(phase):
    """The sun moves on a circle centred below the ground; phase 0 is sunrise, 0.5 sunset."""
    a = 2 * math.pi * phase
    return 80 - 84 * math.cos(a), GROUND - 84 * math.sin(a), math.sin(a)


def sky(c, elevation, stars_seed=7):
    if elevation > 0.25:   top, bottom = 3, 4
    elif elevation > 0:    top, bottom = 2, 5
    elif elevation > -0.2: top, bottom = 0, 2
    else:                  top, bottom = 0, 1
    t = Y / GROUND                                            # 0 at the top of the sky, 1 at the horizon
    use_bottom = t > BAYER[Y % 4, X % 4]                      # ordered dithering
    c[:] = np.where(use_bottom, bottom, top)
    if elevation < 0:                                         # fixed stars, from a seeded generator
        rng = np.random.default_rng(stars_seed)
        for x, y in zip(rng.integers(0, W, 40), rng.integers(0, 60, 40)):
            c[y, x] = 7


def ground(c):
    fill(c, rect(0, GROUND - 8, W, GROUND), 14)                  # the plinth and steps
    fill(c, rect(0, GROUND - 8, W, GROUND - 7), 7)
    fill(c, (Y >= GROUND), 12)
    fill(c, (Y >= GROUND) & ((X - 80) ** 2 * 0.02 < (Y - GROUND + 2)), 14)   # path widening towards us


def night_swap(c, region):
    out = c.copy()
    for a, b in NIGHT.items():
        out[region & (c == a)] = b
    return out


# ---------------------------------------------------------------- physics
@dataclass
class Kite:
    """A point mass on an elastic string. Forces: gravity, string tension (Hooke's law), drag towards the wind."""
    anchor: tuple = (4.0, GROUND - 2.0)
    pos: np.ndarray = field(default_factory=lambda: np.array([40.0, 40.0]))
    vel: np.ndarray = field(default_factory=lambda: np.zeros(2))
    m: float = 1.0; g: float = 20.0; k: float = 6.0; L0: float = 90.0; drag: float = 1.5

    def wind(self, t):
        return np.array([10 + 4 * math.sin(0.7 * t) + 2 * math.sin(2.3 * t), -30 - 3 * math.sin(1.3 * t)])

    def forces(self, t):
        d = self.pos - np.array(self.anchor)
        L = np.linalg.norm(d)
        tension = -self.k * max(L - self.L0, 0) * d / L        # a string pulls but never pushes
        gravity = np.array([0.0, self.m * self.g])             # +y is down on screen
        air = self.drag * (self.wind(t) - self.vel)
        return gravity + tension + air

    def step(self, t, dt):
        self.vel += self.forces(t) / self.m * dt               # semi-implicit Euler: velocity first,
        self.pos += self.vel * dt                              # then position with the new velocity

    def draw(self, c):
        line(c, *self.anchor, *self.pos, 15)
        x, y = self.pos
        diamond = (np.abs(X - x) / 3 + np.abs(Y - y) / 4) <= 1
        fill(c, diamond, 5); fill(c, diamond & (X > x), 6)
        for i in range(1, 6):                                    # tail ripples behind
            put_pixel(c, x - 1 - i * 0.4, y + 3 + i + math.sin(i + x) * 0.8, 9)


@dataclass
class Flock:
    """Pigeons following Reynolds' three rules: keep apart, match heading, stay together."""
    n: int = 14; seed: int = 3

    def __post_init__(self):
        rng = np.random.default_rng(self.seed)
        self.p = rng.uniform([20, 10], [140, 40], (self.n, 2))
        self.v = rng.normal(0, 8, (self.n, 2)) + [12, 0]

    def step(self, dt):
        d = self.p[:, None, :] - self.p[None, :, :]
        dist = np.linalg.norm(d, axis=2) + np.eye(self.n) * 1e9
        near = dist < 25
        cnt = near.sum(1, keepdims=True).clip(1)
        cohesion = (near[..., None] * -d).sum(1) / cnt * 0.6
        alignment = ((near @ self.v) / cnt - self.v) * 0.5
        separation = ((dist < 5)[..., None] * d / dist[..., None] ** 2).sum(1) * 60
        home = (np.array([80, 25]) - self.p) * 0.4            # stay over the mosque
        self.v += (cohesion + alignment + separation + home) * dt
        speed = np.linalg.norm(self.v, axis=1, keepdims=True)
        self.v *= np.clip(speed, 8, 22) / speed                # pigeons have a cruising speed
        self.p += self.v * dt

    def draw(self, c, frame):
        for i, (x, y) in enumerate(self.p):
            up = (frame + i) % 4 < 2                            # a two-frame wing flap
            dy = -1 if up else 1
            put_pixel(c, x, y, 15); put_pixel(c, x - 1, y + dy, 15); put_pixel(c, x + 1, y + dy, 15)


# ---------------------------------------------------------------- scene and film
def render(phase=0.2, kite=None, flock=None, frame=0):
    c = new_canvas()
    sx, sy, elev = sun_position(phase)
    sky(c, elev)
    if elev > -0.05:
        fill(c, disc(sx, sy, 6), 6)
    else:
        mx, my, _ = sun_position(phase + 0.5)                   # the moon is opposite the sun
        fill(c, disc(mx, my, 4), 7); fill(c, disc(mx + 2, my - 1, 3.5), 0 if elev < -0.2 else 2)
    ground(c)
    building = c.copy()
    for comp in badshahi():
        comp.draw(building)
    changed = building != c
    if elev < 0:
        building = night_swap(building, changed | (Y >= GROUND - 8))
    c = building
    if flock is not None:
        flock.draw(c, frame)
    if kite is not None:
        kite.draw(c)
    return c


def save_png(c, path):
    img = Image.fromarray(c, "P")
    img.putpalette([v for rgb in PALETTE for v in rgb])
    img.resize((W * SCALE, H * SCALE), Image.NEAREST).save(path)


def film(n=240, fps=20, substeps=4, path="day.gif"):
    kite, flock, frames = Kite(), Flock(), []
    dt = 1 / fps
    for f in range(n):
        t = f * dt
        for s in range(substeps):
            kite.step(t + s * dt / substeps, dt / substeps)
        flock.step(dt)
        c = render(phase=-0.05 + 1.1 * f / n, kite=kite, flock=flock, frame=f)
        img = Image.fromarray(c, "P"); img.putpalette([v for rgb in PALETTE for v in rgb])
        frames.append(img.resize((W * SCALE, H * SCALE), Image.NEAREST))
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=int(1000 / fps), loop=0, optimize=False)
    return kite, flock


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "out"
    out.mkdir(exist_ok=True)
    save_png(render(phase=0.22), out / "badshahi_day.png")
    save_png(render(phase=0.62), out / "badshahi_night.png")
    film(path=out / "badshahi_day.gif")
    print("wrote", *sorted(p.name for p in out.iterdir()))
