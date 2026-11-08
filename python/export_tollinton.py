"""Export Tollinton Market: a detailed final picture (PNG, JPG, GIF) and a GIF of the notebook's steps.

The scene is the guide's tollinton.py, run again with a canvas twice as large (512 x 288) for more detail.

    python export_tollinton.py PATH/TO/guides/pixel-animation/notebooks
"""
import os, sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

NB = Path(sys.argv[1]).resolve()
OUT = Path(__file__).resolve().parent.parent / "out" / "tollinton"
OUT.mkdir(parents=True, exist_ok=True)
os.environ["MPLBACKEND"] = "Agg"
os.chdir(NB)

src = (NB / "tollinton.py").read_text(encoding="utf8").replace("plt.show()", "plt.close('all')")
src = src.replace("WP, HP = 256, 144", "WP, HP = 512, 288")          # twice the detail, same camera and light
scene = {}
exec(compile(src, "tollinton.py", "exec"), scene)
render, cam, FACES, GROUND, frames = scene["render"], scene["cam"], scene["FACES"], scene["GROUND"], scene["frames"]

still = render(cam, FACES, GROUND)                                    # palette image, 512 x 288
big = still.resize((still.width * 3, still.height * 3), Image.NEAREST)
big.save(OUT / "tollinton_final.png")
big.convert("RGB").save(OUT / "tollinton_final.jpg", quality=95, subsampling=0)
big.save(OUT / "tollinton_final.gif")
small = [f.convert("RGB").resize((f.width * 2, f.height * 2), Image.NEAREST) for f in frames]
small[0].save(OUT / "tollinton_traffic_detailed.gif", save_all=True, append_images=small[1:], duration=100, loop=0)

# A GIF of the notebook's steps, from the figures the guide's build saved
fig = NB.parent / "fig"
steps = [("1. OpenStreetMap: outline and streets", "nb_tollinton_01.png"),
         ("2. Heights measured on a photograph", "nb_tollinton_02.png"),
         ("3. Colours measured with k-means", "nb_tollinton_03.png"),
         ("4. The sun's path over Lahore", "nb_tollinton_04.png"),
         ("5. A 3D model from the footprint", "nb_tollinton_05.png"),
         ("6. Rendered: light, shadow, perspective", "nb_tollinton_06.png"),
         ("7. Traffic: the Intelligent Driver Model", "nb_tollinton_07.png")]
try:
    font = ImageFont.truetype("arialbd.ttf", 28)
except OSError:
    font = ImageFont.load_default()
cards = []
for title, name in steps:
    if not (fig / name).exists():
        continue
    im = Image.open(fig / name).convert("RGB")
    im.thumbnail((1100, 560))
    card = Image.new("RGB", (1152, 640), (250, 248, 242))
    card.paste(im, ((1152 - im.width) // 2, 70))
    ImageDraw.Draw(card).text((30, 18), title, font=font, fill=(40, 40, 50))
    cards.append(card)
final = big.convert("RGB").resize((1152, 648)).crop((0, 4, 1152, 644))
ImageDraw.Draw(final).text((30, 18), "8. The final picture", font=font, fill=(255, 255, 255))
cards.append(final)
cards[0].save(OUT / "tollinton_steps.gif", save_all=True, append_images=cards[1:], duration=2500, loop=0)
for f in sorted(OUT.iterdir()):
    print(f"{f.name:32s} {f.stat().st_size / 1e3:7.0f} kB")
