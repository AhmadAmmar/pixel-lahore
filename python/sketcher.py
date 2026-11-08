"""An urban sketcher draws Tollinton Market, step by step, with the thinking shown beside the paper.

The scene, camera, sun and colours are those of the guide's Tollinton chapter (tollinton.py), so every line the
sketcher draws is a true perspective line of the measured building. The video shows the order sketchers work in:
frame, eye level, vanishing points, the big box, roof and gable, cupolas, rhythm of posts and windows, the street,
light (shadows first), sky, and life.

    python sketcher.py PATH/TO/guides/pixel-animation/notebooks      writes ../out/sketcher.mp4 and sketcher_preview.gif
"""
import math, os, subprocess, sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

NB = Path(sys.argv[1]).resolve()
OUT = Path(__file__).resolve().parent.parent / "out"
OUT.mkdir(exist_ok=True)

# ---------------------------------------------------------------- the scene, from the guide's notebook
os.environ["MPLBACKEND"] = "Agg"
os.chdir(NB)
src = (NB / "tollinton.py").read_text(encoding="utf8").replace("plt.show()", "plt.close('all')")
scene = {}
exec(compile(src, "tollinton.py", "exec"), scene)
cam, FACES, GROUND, render, frames_traffic = scene["cam"], scene["FACES"], scene["GROUND"], scene["render"], scene["frames"]
H, ELEV, AZ, A, B = scene["H"], scene["ELEV"], scene["AZ"], scene["A"], scene["B"]
WP, HP = scene["WP"], scene["HP"]
n_market = scene["n_market"]

S = 3                                   # paper pixels per scene pixel
PW, PH = WP * S, HP * S                 # 768 x 432 drawing area
VW, VH = 1280, 720                      # video frame
FPS = 12
PAPER = np.array([246, 241, 229], np.uint8)
PENCIL, INK = np.array([150, 145, 140]), np.array([45, 40, 45])
rng = np.random.default_rng(5)
paper = np.clip(PAPER[None, None, :].astype(int) + rng.normal(0, 3, (PH, PW, 1)), 0, 255).astype(np.uint8)

target = np.asarray(render(cam, FACES, GROUND).convert("RGB").resize((PW, PH), Image.NEAREST))
pal_idx = np.asarray(render(cam, FACES, GROUND).resize((PW, PH), Image.NEAREST))

# ---------------------------------------------------------------- which face is visible where (an id buffer)
def visible_ids():
    img = Image.new("I", (PW, PH), -1); dr = ImageDraw.Draw(img)
    items = []
    for i, f in enumerate(FACES):
        if not f["two_sided"] and np.dot(f["n"], cam.eye - f["pts"].mean(0)) <= 0:
            continue
        uv, depth = cam.project(f["pts"])
        if uv is None:
            continue
        p = f["decal_of"]
        key = depth if p is None else cam.to_cam(FACES[p]["pts"])[:, 2].mean()
        items.append((-key, p is not None, i, uv * S))
    for _, _, i, uv in sorted(items, key=lambda x: (x[0], x[1])):
        dr.polygon([tuple(q) for q in uv], fill=i)
    return np.asarray(img), {i: uv for _, _, i, uv in items}

idbuf, uvs = visible_ids()

# ---------------------------------------------------------------- sort the market's faces into the sketcher's steps
eave, ridge, verandah = H["eave"], H["ridge"], H["verandah"]
def kind(i, f):
    z = f["pts"][:, 2]
    if i >= n_market:
        return "neighbours" if f["mat"].startswith("other") else "trees" if f["group"] == "tree" else None
    if f["mat"] == "window":
        return "windows"
    if f["mat"] == "cupola":
        return "cupolas"
    if f["mat"] == "railing" or (f["mat"] == "roof" and z.max() < verandah + 2.5):
        return "verandah"
    if f["mat"] == "roof" or (f["mat"] == "wall" and z.min() > eave):
        return "roof"
    if f["mat"] == "wall" and z.max() > eave + 1:
        return "gable"
    return "box"

GROUPS = {}
for i, f in enumerate(FACES):
    k = kind(i, f)
    if k and i in uvs:
        GROUPS.setdefault(k, []).append(i)

def visible_strokes(ids):
    """Each face's outline, keeping only the pixels where that face (or its window) is what we see."""
    strokes = []
    for i in ids:
        uv = uvs[i]
        for p, q in zip(uv, np.roll(uv, -1, axis=0)):
            n = int(max(abs(q - p).max(), 1))
            pts = p + (q - p) * np.linspace(0, 1, n + 1)[:, None]
            xi, yi = pts[:, 0].round().astype(int), pts[:, 1].round().astype(int)
            ok = (xi >= 0) & (xi < PW) & (yi >= 0) & (yi < PH)
            seen = np.zeros(len(xi), bool)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    xx, yy = np.clip(xi + dx, 0, PW - 1), np.clip(yi + dy, 0, PH - 1)
                    seen |= idbuf[yy, xx] == i
            keep = ok & seen
            if keep.sum() > 2:
                strokes.append(np.c_[xi[keep], yi[keep]])
    return strokes

# ---------------------------------------------------------------- perspective guides
def vp(d):
    """Where all lines parallel to horizontal direction d meet: the image of a point infinitely far along d."""
    c = cam.to_cam(cam.eye + np.r_[d, 0] * 1e6)[0]
    if c[2] <= 0:
        c = cam.to_cam(cam.eye - np.r_[d, 0] * 1e6)[0]
    return np.array([WP / 2 + cam.focal * c[0] / c[2], HP / 2 - cam.focal * c[1] / c[2]]) * S

VP1, VP2 = vp(A), vp(B)
HORIZON = VP1[1]

def line_pts(p, q):
    n = int(max(abs(np.subtract(q, p)).max(), 1))
    pts = np.asarray(p) + (np.asarray(q) - np.asarray(p)) * np.linspace(0, 1, n + 1)[:, None]
    pts = pts[(pts[:, 0] >= 0) & (pts[:, 0] < PW) & (pts[:, 1] >= 0) & (pts[:, 1] < PH)]
    return pts.round().astype(int)

# ---------------------------------------------------------------- text panel
def font(size, bold=False):
    for name in (("arialbd.ttf" if bold else "arial.ttf"), ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()

F_TITLE, F_BODY, F_SMALL = font(26, True), font(19), font(14)

def wrap(text, f, width):
    words, lines, line = text.split(), [], ""
    for w in words:
        trial = (line + " " + w).strip()
        if f.getlength(trial) > width:
            lines.append(line); line = w
        else:
            line = trial
    return lines + [line]

# ---------------------------------------------------------------- the steps: (title, thinking, action)
STEPS = [
    ("Look, then frame", "Stand still and look first. I want the long yellow front and the stepped east gable together, "
     "so I stand across Mall Road, beyond the east end. The building goes in the lower middle, with room above for the cupolas.", "frame"),
    ("Eye level", f"I am on the top deck of a bus, 4.5 m up. The horizon is always at my eye level, so I draw it first. "
     "Everything above it I see from below; everything below it, from above.", "horizon"),
    ("Two vanishing points", "The hall's long walls are parallel, and so are its ends. Each set of parallel lines meets at its "
     "own point on the horizon: two-point perspective. One point is far off to the right, so I only hint at its lines.", "vps"),
    ("Block in the big box", "Before any detail, the mass: a box 73 m long and 12.5 m to the eaves. The near corner is the "
     "tallest vertical; every top edge runs to a vanishing point. The east end wall goes in with it, its stepped Dutch top "
     "and all. If the box is wrong, no detail will save it.", "box"),
    ("Roof and dormers", "The roof rises at about 35 degrees to a ridge set back 10 m, so it looks lower than it is; the "
     "gable's five steps already mark where it ends. Dormers sit along the slope like a row of tents.", "roof"),
    ("Cupolas", "Two green lanterns on the ridge, about 15 % in from each end. The far one is smaller and higher on the "
     "page: perspective, not a different size.", "cupolas"),
    ("Rhythm: posts and windows", "A post every 3.6 m, a window every 5.2 m. In perspective the spacing shrinks towards the "
     "vanishing point, so I do not count; I halve and halve again.", "rhythm"),
    ("The street", "Mall Road runs parallel to the hall, so its edges head for the same vanishing point. The kerb stones, "
     "yellow and black, are a quick dotted rhythm. Neighbours stay light, they are context.", "street"),
    ("Light: shadows first", "The sun is in the east-north-east, 30 degrees up, at 07:30 on a June morning. Walls turned away "
     "are darkest, so I lay those first, then the half tones.", "shade"),
    ("Light: the lit faces", "The east gable faces the sun most squarely, so it is the brightest thing on the page. I leave "
     "it for last and let it glow against the roof.", "lit"),
    ("Sky", "Deep blue above, paler towards the horizon: sunlight scattered by air, strongest in blue. I wash it in quickly "
     "around the cupolas.", "sky"),
    ("Life", "A street sketch needs people moving. Rickshaws keep to the left lane, cars and bikes to the right. "
     "Done: Tollinton Market, Mall Road, Lahore.", "life"),
]

# ---------------------------------------------------------------- drawing state and frame writer
canvas = paper.copy().astype(float)
layers = {"ink": np.zeros((PH, PW), bool), "pencil": np.zeros((PH, PW), bool)}
colour_mask = np.zeros((PH, PW), bool)
pen = np.array([PW * 0.6, PH * 0.6])
frames_out = []
ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{VW}x{VH}",
                       "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", str(OUT / "sketcher.mp4")],
                      stdin=subprocess.PIPE)
state = dict(step=0, frame=0, overlay=None)


def compose(live=None):
    img = paper.astype(float).copy()
    img[colour_mask] = target[colour_mask] * 0.92 + paper[colour_mask] * 0.08
    if live is not None:
        img = live.astype(float)
    img[layers["pencil"]] = img[layers["pencil"]] * 0.55 + PENCIL * 0.45
    img[layers["ink"]] = INK
    pic = Image.fromarray(img.astype(np.uint8))
    if state["overlay"] is not None:
        pic = Image.alpha_composite(pic.convert("RGBA"), state["overlay"]).convert("RGB")
    frame = Image.new("RGB", (VW, VH), (32, 30, 36))
    frame.paste(pic, (32, 96))
    d = ImageDraw.Draw(frame)
    # the sketcher's hand: a pencil tip
    x, y = pen + [32, 96]
    d.polygon([(x, y), (x + 10, y - 26), (x + 20, y - 22)], fill=(230, 190, 60), outline=(60, 50, 40))
    d.line([(x, y), (x + 4, y - 9)], fill=(40, 40, 40), width=3)
    n, (title, text, _) = state["step"], STEPS[state["step"]]
    d.text((32, 30), "Sketching Tollinton Market, Mall Road, Lahore", font=F_TITLE, fill=(240, 235, 225))
    d.text((830, 96), f"Step {n + 1} of {len(STEPS)}", font=F_SMALL, fill=(200, 190, 170))
    d.text((830, 120), title, font=F_TITLE, fill=(250, 210, 120))
    yy = 165
    for ln in wrap(text, F_BODY, 420):
        d.text((830, yy), ln, font=F_BODY, fill=(235, 232, 225)); yy += 27
    for k in range(len(STEPS)):
        d.rectangle([32 + k * 64, 548, 32 + k * 64 + 58, 554], fill=(250, 210, 120) if k <= n else (80, 78, 85))
    d.text((32, 572), "Perspective, proportions, light and colours from the guide's Tollinton chapter: footprint from "
           "OpenStreetMap (ODbL), heights and colours measured", font=F_SMALL, fill=(170, 165, 160))
    d.text((32, 592), "from a photo by Shahzaib Damn Cruze (CC BY-SA 4.0), sun position for 21 June 07:30. "
           "ahmadammar.github.io/teaching/pixel-animation", font=F_SMALL, fill=(170, 165, 160))
    return frame


def emit(n=1, live=None):
    fr = compose(live)
    raw = np.asarray(fr).tobytes()
    for _ in range(n):
        ff.stdin.write(raw)
        if state["frame"] % 3 == 0:
            frames_out.append(fr.resize((640, 360)))
        state["frame"] += 1


def draw_strokes(strokes, layer, seconds, jitter=0.6):
    """Animate a pen along the strokes, finishing them in about `seconds`."""
    total = sum(len(s) for s in strokes) or 1
    per_frame = max(1, int(total / (seconds * FPS)))
    done = 0
    for s in strokes:
        s = s + rng.normal(0, jitter, s.shape).round().astype(int) * (layer == "pencil")
        s[:, 0] = np.clip(s[:, 0], 0, PW - 1); s[:, 1] = np.clip(s[:, 1], 0, PH - 1)
        for j in range(0, len(s), per_frame):
            chunk = s[j:j + per_frame]
            layers[layer][chunk[:, 1], chunk[:, 0]] = True
            pen[:] = chunk[-1]
            done += len(chunk)
            emit()


def wash(mask, seconds, direction="lr"):
    """Reveal the colour under `mask` with a brush sweeping across the page."""
    n = int(seconds * FPS)
    coord = np.mgrid[0:PH, 0:PW][1 if direction == "lr" else 0]
    span = PW if direction == "lr" else PH
    for k in range(1, n + 1):
        edge = span * k / n
        colour_mask[mask & (coord < edge)] = True
        pen[:] = [edge if direction == "lr" else PW * 0.5, PH * 0.5 if direction == "lr" else edge]
        pen[:] = np.clip(pen, 0, [PW - 1, PH - 1])
        emit()


def tone_mask(level, mats=None):
    """Pixels of the target picture whose palette tone is `level` (0 shade, 1 half, 2 lit)."""
    t = (pal_idx.astype(int) - 3) % 3
    m = (pal_idx >= 3) & (t == level)
    return m


# ---------------------------------------------------------------- perform
for n, (_, _, action) in enumerate(STEPS):
    state["step"] = n
    if action == "frame":
        ov = Image.new("RGBA", (PW, PH)); od = ImageDraw.Draw(ov)
        for k in range(1, 16):
            state["overlay"] = Image.new("RGBA", (PW, PH))
            ImageDraw.Draw(state["overlay"]).rectangle([PW * 0.08, PH * 0.3, PW * 0.92, PH * 0.82], outline=(200, 80, 60, int(255 * min(1, k / 8))), width=3)
            emit()
        emit(FPS * 3)
        state["overlay"] = None
    elif action == "horizon":
        draw_strokes([line_pts((0, HORIZON), (PW - 1, HORIZON))], "pencil", 2.0, jitter=0.3); emit(FPS * 3)
    elif action == "vps":
        anchors = [(x, y) for x in (0, PW * 0.25, PW * 0.5, PW * 0.75, PW - 1) for y in (PH * 0.2, PH * 0.95)]
        strokes = [line_pts(a, VP1) for a in anchors[::2]] + [line_pts(a, VP2) for a in anchors[1::3]]
        draw_strokes([s for s in strokes if len(s) > 3], "pencil", 3.5); emit(FPS * 3)
    elif action == "box":
        draw_strokes(visible_strokes(GROUPS.get("box", []) + GROUPS.get("gable", [])), "ink", 6.0); emit(FPS * 2)
    elif action == "roof":
        draw_strokes(visible_strokes(GROUPS.get("roof", [])), "ink", 6.0); emit(FPS * 2)
    elif action == "cupolas":
        draw_strokes(visible_strokes(GROUPS.get("cupolas", [])), "ink", 4.0); emit(FPS * 2)
    elif action == "rhythm":
        draw_strokes(visible_strokes(GROUPS.get("verandah", []) + GROUPS.get("windows", [])), "ink", 7.0); emit(FPS * 2)
    elif action == "street":
        road_strokes = []
        for pts, mat in GROUND:
            if mat in ("kerb yellow", "kerb dark"):
                uv, _ = cam.project(np.array(pts))
                if uv is not None and mat == "kerb dark":
                    road_strokes.append(np.clip((uv * S).mean(0).round().astype(int)[None], 0, [PW - 1, PH - 1]))
        draw_strokes(road_strokes[::2], "ink", 2.5, jitter=0)
        draw_strokes(visible_strokes(GROUPS.get("neighbours", []) + GROUPS.get("trees", [])), "pencil", 4.0); emit(FPS * 2)
    elif action == "shade":
        ground_like = pal_idx < 3
        wash(tone_mask(0) & ~ground_like, 3.0); wash(tone_mask(1) & ~ground_like, 4.0); emit(FPS * 2)
    elif action == "lit":
        wash(tone_mask(2), 3.0); emit(FPS * 3)
    elif action == "sky":
        wash(pal_idx < 3, 3.0, direction="tb"); emit(FPS * 2)
    elif action == "life":
        for rep in range(3):
            for fr in frames_traffic:
                live = np.asarray(fr.convert("RGB").resize((PW, PH), Image.NEAREST)).astype(float)
                live = live * 0.92 + paper * 0.08
                emit(1, live=live)
        state["overlay"] = Image.new("RGBA", (PW, PH))
        ImageDraw.Draw(state["overlay"]).text((PW - 230, PH - 34), "Tollinton Mkt, Lahore  21.vi", font=font(18), fill=(60, 50, 60, 255))
        emit(FPS * 4, live=live)

ff.stdin.close(); ff.wait()
frames_out[0].save(OUT / "sketcher_preview.gif", save_all=True, append_images=frames_out[1:], duration=int(3000 / FPS), loop=0)
secs = state["frame"] / FPS
print(f"{state['frame']} frames, {secs:.0f} s at {FPS} fps -> {OUT / 'sketcher.mp4'} "
      f"({(OUT / 'sketcher.mp4').stat().st_size / 1e6:.1f} MB); preview GIF {(OUT / 'sketcher_preview.gif').stat().st_size / 1e6:.1f} MB")
print("strokes per step:", {k: len(v) for k, v in GROUPS.items()}, f"VP1 {VP1.round()}, VP2 {VP2.round()}, horizon y {HORIZON:.0f}")
