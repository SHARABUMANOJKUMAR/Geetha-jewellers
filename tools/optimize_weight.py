"""
Geetha Jewellers - page-weight pass (the "small lag" fix)
----------------------------------------------------------
    python tools/optimize_weight.py

The page was pulling ~30 MB of images: plates kept at WebP q92-95 after the
2x HD pass, two full-size PNG backgrounds and PNG product cutouts that had no
WebP at all, and hero displays far taller than they are ever drawn. Decoding
all of that while scrolling is what reads as lag.

What it does (only to files the page actually loads):
  * every WebP the page loads is re-encoded at q84 (alpha q90) from its
    lossless PNG master when one exists, else from itself - kept only when
    that saves at least 15 %; dimensions are untouched, so every layout,
    mask and coordinate stays exactly as approved
  * the hero displays (+ their glint masks) are capped at 1600 px tall:
    they are drawn at most 58svh, i.e. < 1300 device px even on a 2x phone
  * PNG-only images (necklace / men's-chains backgrounds, chain cutouts,
    glint masks) get a WebP sibling; index.html / the scripts point at it

Run after any tools/build_*_assets.py or tools/hd_upscale.py rebuild.
"""
from __future__ import annotations

import io
import os
import re
import subprocess

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "269e3ba"   # the approved originals: every WebP is encoded from these, never from
                   # its own previous output, so re-running never stacks compression
Q, QA, MIN_SAVING = 84, 90, 0.15
HERO = ["necklace", "ring", "earrings", "bangles", "pendant-set"]
HERO_MAX_H = 1600
# brand marks stay at full quality; plates written by build_oval_logo.py are
# already encoded there (from their own originals)
KEEP = ("logo", "gj-oval", "gj-lockup", "gji-oval", "gji-gold", "offer-desktop", "offer-mobile",
        "gjo-d", "gjo-dm", "gja-scene")
# PNG files referenced directly (no WebP twin yet) -> converted in place
PNG_ONLY = (["images/new-necklace-bg.png", "images/men-chains/men-chain-bg.png"]
            + [f"images/men-chains/chain{i}.png" for i in range(1, 6)]
            + [f"images/{h}-glints.png" for h in HERO])


def encode(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    if im.mode in ("RGBA", "LA", "P") and im.convert("RGBA").getchannel("A").getextrema()[0] < 255:
        im.convert("RGBA").save(buf, "WEBP", quality=Q, alpha_quality=QA, method=6)
    else:
        im.convert("RGB").save(buf, "WEBP", quality=Q, method=6)
    return buf.getvalue()


def cap(im: Image.Image, max_h: int) -> Image.Image:
    if im.height <= max_h:
        return im
    return im.resize((round(im.width * max_h / im.height), max_h), Image.LANCZOS)


def loaded_webps():
    text = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    for f in ("js/stage.js", "js/men-chains.js", "js/sections.js"):
        text += open(os.path.join(ROOT, f), encoding="utf-8").read()
    for f in os.listdir(os.path.join(ROOT, "css")):
        text += open(os.path.join(ROOT, "css", f), encoding="utf-8").read()
    return sorted(set(re.findall(r"images/[\w./-]+?\.webp", text)))


def main():
    before = after = 0
    # 1) PNG-only images get a WebP twin
    for png in PNG_ONLY:
        src = os.path.join(ROOT, png)
        im = Image.open(src)
        im.load()
        stem = os.path.splitext(os.path.basename(png))[0].replace("-glints", "")
        if stem in HERO:
            im = cap(im, HERO_MAX_H)
        data = encode(im)
        out = src[:-4] + ".webp"
        open(out, "wb").write(data)
        before += os.path.getsize(src)
        after += len(data)
        print(f"  {os.path.getsize(src) // 1024:5d} -> {len(data) // 1024:4d} KB  {png[:-4]}.webp (new)")

    # 2) every WebP the page loads
    for rel in loaded_webps():
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            continue
        stem = os.path.splitext(os.path.basename(rel))[0]
        if stem.startswith(KEEP):
            continue
        # the approved original of this WebP (or the file itself if it is new)
        original = subprocess.run(["git", "show", f"{BASE}:{rel}"], cwd=ROOT, capture_output=True).stdout \
            or open(path, "rb").read()
        master = path[:-5] + ".png"
        im = Image.open(master if os.path.exists(master) else io.BytesIO(original))
        im.load()
        if stem in HERO:
            im = cap(im, HERO_MAX_H)
        data = encode(im)
        if stem not in HERO and len(data) > len(original) * (1 - MIN_SAVING):
            data = original                     # not worth it: keep the original bytes
        open(path, "wb").write(data)
        before += len(original)
        after += len(data)
        if data is not original:
            print(f"  {len(original) // 1024:5d} -> {len(data) // 1024:4d} KB  {rel}")
    print(f"total {before / 1048576:.1f} MB -> {after / 1048576:.1f} MB")


if __name__ == "__main__":
    main()
