# Minar-e-Pakistan at sunset, with a kite: two frames, 23 lines of code.
from PIL import Image

# 1. Canvas. Thought: "How small can it be and still read as the Minar?" A tower is tall and thin, so 32 x 48 pixels.
W, H = 32, 48

# 2. Palette. Thought: "Sunset over Iqbal Park." Five colours are enough. Pick them from a photo with any colour picker,
#    or borrow a ready-made set from lospec.com/palette-list. Physics: at sunset light crosses more air, and air scatters
#    blue away (Rayleigh scattering: shorter waves scatter far more), so the sky goes orange near the horizon.
SKY_TOP, SKY_LOW, MINAR, GRASS, KITE = (70, 40, 90), (240, 130, 60), (235, 230, 220), (40, 70, 40), (220, 30, 60)

def frame(kite_x):
    img = Image.new("RGB", (W, H))
    for y in range(H):
        for x in range(W):
            # 3. Sky. Thought: "Blend from purple at the top to orange at the horizon": mix = how far down we are.
            t = y / 40
            c = tuple(int(a + (b - a) * t) for a, b in zip(SKY_TOP, SKY_LOW))
            # 4. The Minar. Thought: "It is a tower that narrows as it rises": half-width shrinks linearly with height.
            half = (y - 4) / 12                               # grows by 1 pixel each side every 12 rows
            if 4 <= y < 40 and abs(x - 15.5) <= half + 0.5:
                c = MINAR
            if 36 <= y < 40 and abs(x - 15.5) <= 7:             # the raised platform it stands on
                c = MINAR
            if y >= 40:                                        # 5. Ground: the park's grass.
                c = GRASS
            img.putpixel((x, y), c)
    # 6. Kite. Thought: "Two frames are enough for motion if something swings." Move it two pixels between frames.
    PATANG = ((0, -2), (-1, -1), (0, -1), (1, -1), (-2, 0), (-1, 0), (0, 0), (1, 0), (2, 0), (-1, 1), (0, 1), (1, 1), (0, 2))
    for dx, dy in PATANG + ((0, 3), (1, 4), (0, 5)):              # a diamond, the patang, plus a wiggly tail
        img.putpixel((kite_x + dx, 10 + dy), KITE)
    return img.resize((W * 8, H * 8), Image.NEAREST)          # 7. Scale up without blurring, so pixels stay square.

frames = [frame(24), frame(26)]
frames[0].save("../out/tiny_minar.gif", save_all=True, append_images=frames[1:], duration=400, loop=0)
