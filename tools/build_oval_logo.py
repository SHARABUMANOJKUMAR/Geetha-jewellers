"""
Geetha Jewellers - the real OVAL logo, everywhere a logo appears
-----------------------------------------------------------------
    python tools/build_oval_logo.py

The client's mark is the pearl OVAL medallion with the gold GJS monogram and
peacock tail (the header logo, images/logo.webp, cut from reference A). The
intro used a round gold coin and the offer plates carried a generated "GJS"
mark, so this script rebuilds the medallion at high resolution and puts it
in every one of those places.

Inputs: images/logo.webp (the real lockup) and the plates as committed in
269e3ba (read with `git show`, so re-running never stacks edits).

Outputs (images/)
    gj-oval.webp/.png       the medallion alone, crisp, ~900 px tall
    gji-oval.webp/.png      the same with a warm glow, for the dark intro
    gji-gold.webp/.jpg      keyframe A with the coin replaced by the medallion
    offer-desktop/-mobile   generated "GJS / A LEGACY OF TRUST" replaced by
                            the real lockup (images/logo.webp)
    gjo-d / gjo-dm          the wall sign replaced by the medallion
    favicon.ico, favicon-32.png, apple-touch-icon.png
"""
from __future__ import annotations

import io
import os
import subprocess

import cv2
import numpy as np
from PIL import Image

import hd_upscale

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "images")
BASE = "269e3ba"   # the plates exactly as approved, before this pass
S = 4              # medallion scale over the header logo


def from_git(path):
    raw = subprocess.run(["git", "show", f"{BASE}:{path}"], cwd=ROOT, check=True, capture_output=True).stdout
    return Image.open(io.BytesIO(raw))


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def ellipse_field(h, w, cx, cy, ax, ay, ang):
    """normalised elliptical radius (1.0 on the ellipse) for every pixel"""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    t = np.deg2rad(ang)
    dx, dy = xx - cx, yy - cy
    u = dx * np.cos(t) + dy * np.sin(t)
    v = -dx * np.sin(t) + dy * np.cos(t)
    return np.hypot(u / ax, v / ay)


def gold_shade(mask, light=(-0.55, -0.8, 1.0), relief=5.0):
    """render a crisp coverage mask as polished, bevelled gold (RGB 0..1)"""
    h, w = mask.shape
    height = cv2.GaussianBlur(mask, (0, 0), relief)
    gy, gx = np.gradient(height)
    n = np.dstack([-gx * 26, -gy * 26, np.ones_like(mask)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    lv = np.array(light, np.float32)
    lv /= np.linalg.norm(lv)
    lam = np.clip((n * lv).sum(axis=2), 0, 1)
    spec = lam ** 18
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    top = np.array([0.98, 0.85, 0.52], np.float32)
    mid = np.array([0.84, 0.60, 0.22], np.float32)
    low = np.array([0.55, 0.34, 0.09], np.float32)
    base = np.where((yy < 0.5)[..., None], top + (mid - top) * (yy / 0.5)[..., None],
                    mid + (low - mid) * ((yy - 0.5) / 0.5)[..., None])
    base = np.broadcast_to(base, (h, w, 3))
    col = base * (0.55 + 0.75 * lam[..., None]) + spec[..., None] * np.array([1.0, 0.95, 0.8], np.float32) * 0.55
    return np.clip(col, 0, 1)


# ------------------------------------------------------------------ the medallion
def build_medallion():
    print("medallion:")
    lg = np.array(Image.open(os.path.join(OUT, "logo.webp")).convert("RGBA")).astype(np.float32) / 255
    rgb, al = lg[..., :3], lg[..., 3]
    # rim ellipse fitted to the header logo's gold ring
    cx, cy, aw, ah, ang = 212.11, 108.76, 133.82 / 2, 148.91 / 2, 3.82
    pad = 6
    x0, y0 = int(cx - aw - pad), int(cy - ah - pad)
    x1, y1 = int(cx + aw + pad) + 1, int(cy + ah + pad) + 1
    y0 = max(0, y0)
    sub = (np.clip(rgb[y0:y1, x0:x1], 0, 1) * 255 + 0.5).astype(np.uint8)
    h, w = sub.shape[:2]
    lcx, lcy = cx - x0, cy - y0

    # the real pixels, super-resolved (FSRCNN 2x, as every plate on the site),
    # then taken to S with Lanczos and a light unsharp - faithful, not re-drawn
    up = hd_upscale.sr2x(sub)
    H, W = h * S, w * S
    col = np.asarray(hd_upscale.sharpen(Image.fromarray(up).resize((W, H), Image.LANCZOS))).astype(np.float32) / 255

    # only the outline is re-drawn: a crisp polished-gold rim exactly over the
    # fitted ring, so the oval reads clean at any size
    R = ellipse_field(H, W, lcx * S, lcy * S, aw * S, ah * S, ang)
    px = 1.0 / (ah * S)                    # one pixel in normalised radius
    rim_w, out = 0.026, 0.01
    rim = smoothstep(1 - rim_w - px, 1 - rim_w + px, R) * (1 - smoothstep(1 + out - px, 1 + out + px, R))
    alpha = 1 - smoothstep(1 + out - px, 1 + out + px, R)
    gold_r = gold_shade(rim, light=(-0.4, -1.0, 0.9), relief=S * 0.5)
    col = col * (1 - rim[..., None]) + gold_r * rim[..., None]
    rgba = np.dstack([col, alpha])
    # trim to the ellipse
    ys, xs = np.nonzero(alpha > 0.01)
    rgba = rgba[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    im = Image.fromarray((np.clip(rgba, 0, 1) * 255).astype(np.uint8), "RGBA")
    im.save(os.path.join(OUT, "gj-oval.png"), optimize=True)
    im.save(os.path.join(OUT, "gj-oval.webp"), "WEBP", quality=90, alpha_quality=95, method=6)
    print(f"  gj-oval     {im.size[0]}x{im.size[1]}")
    return im


def rgba_f(im):
    return np.asarray(im.convert("RGBA")).astype(np.float32) / 255


def paste(dst, src, cx, cy):
    """alpha-composite float RGBA `src` centred at (cx, cy) onto float RGB `dst`"""
    h, w = src.shape[:2]
    x0, y0 = int(round(cx - w / 2)), int(round(cy - h / 2))
    a = src[..., 3:4]
    dst[y0:y0 + h, x0:x0 + w] = dst[y0:y0 + h, x0:x0 + w] * (1 - a) + src[..., :3] * a
    return dst


def shadow_layer(alpha, blur, opacity, dx=0, dy=0, colour=(0.12, 0.07, 0.02), grow=1.0):
    """a soft cast shadow / glow of `alpha`, on a canvas `grow`x larger"""
    h, w = alpha.shape
    H, W = int(h * grow), int(w * grow)
    a = np.zeros((H, W), np.float32)
    oy, ox = (H - h) // 2 + dy, (W - w) // 2 + dx
    a[oy:oy + h, ox:ox + w] = alpha
    a = cv2.GaussianBlur(a, (0, 0), blur) * opacity
    return np.dstack([np.broadcast_to(np.array(colour, np.float32), (H, W, 3)), a])


def scaled(im, height):
    w = round(im.width * height / im.height)
    return im.resize((w, height), Image.LANCZOS)


def fill_hole(rgb, mask, radius=9, scale=4):
    """melt a hole from its surroundings: inpaint at low resolution (smooth,
    no smears), lifted back to full size, then feathered into the plate"""
    h, w = mask.shape
    small = cv2.resize(rgb, (w // scale, h // scale), interpolation=cv2.INTER_AREA)
    msmall = cv2.resize(mask, (w // scale, h // scale), interpolation=cv2.INTER_AREA)
    filled = cv2.inpaint(small, (msmall > 8).astype(np.uint8) * 255, radius, cv2.INPAINT_TELEA)
    filled = cv2.GaussianBlur(cv2.resize(filled, (w, h), interpolation=cv2.INTER_CUBIC), (0, 0), scale * 0.8)
    m = cv2.GaussianBlur(mask.astype(np.float32) / 255, (0, 0), scale)[..., None]
    out = rgb.astype(np.float32) * (1 - m) + filled.astype(np.float32) * m
    # a whisper of grain so the melted patch matches the plate's texture
    grain = np.random.default_rng(7).normal(0, 1.4, out.shape).astype(np.float32)
    return np.clip(out + grain * m, 0, 255).astype(np.uint8)


def ink_mask(rgb, box, thresh=16, sigma=14, dilate=9):
    """pixels in `box` that stand out from the smooth plate around them"""
    x0, y0, x1, y1 = box
    f = rgb.astype(np.float32)
    bg = cv2.GaussianBlur(f, (0, 0), sigma)
    dev = np.abs(f - bg).max(axis=2)
    m = np.zeros(rgb.shape[:2], np.uint8)
    m[y0:y1, x0:x1] = (dev[y0:y1, x0:x1] > thresh).astype(np.uint8) * 255
    m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate, dilate)))
    # close it into one patch so nothing of the old mark survives inside
    return cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (41, 41)))


def save_plate(arr, name, q=86, jpg=True):
    im = Image.fromarray(arr)
    im.save(os.path.join(OUT, f"{name}.webp"), "WEBP", quality=q, method=6)
    if jpg:
        im.save(os.path.join(OUT, f"{name}.jpg"), "JPEG", quality=88, optimize=True, progressive=True)
    print(f"  {name:14s} {im.size[0]}x{im.size[1]}")


# ------------------------------------------------------------------ the intro
def build_intro(oval):
    print("intro:")
    # lockup emblem: the medallion in a warm glow for the dark colonnade
    o = rgba_f(oval)
    glow = shadow_layer(o[..., 3], blur=oval.height * 0.07, opacity=0.75, colour=(1.0, 0.82, 0.5), grow=1.36)
    H, W = glow.shape[:2]
    canvas = np.zeros((H, W, 4), np.float32)
    canvas[..., :3] = glow[..., :3]
    canvas[..., 3] = glow[..., 3]
    y0, x0 = (H - o.shape[0]) // 2, (W - o.shape[1]) // 2
    a = o[..., 3:4]
    region = canvas[y0:y0 + o.shape[0], x0:x0 + o.shape[1]]
    out_a = a + region[..., 3:4] * (1 - a)
    region[..., :3] = (o[..., :3] * a + region[..., :3] * region[..., 3:4] * (1 - a)) / np.maximum(out_a, 1e-4)
    region[..., 3:4] = out_a
    im = Image.fromarray((np.clip(canvas, 0, 1) * 255).astype(np.uint8), "RGBA")
    im.save(os.path.join(OUT, "gji-oval.png"), optimize=True)
    im.save(os.path.join(OUT, "gji-oval.webp"), "WEBP", quality=88, alpha_quality=92, method=6)
    print(f"  gji-oval       {im.size[0]}x{im.size[1]}")

    # keyframe A: the round coin embossed on the gold bar becomes the medallion
    plate = np.asarray(from_git("images/gji-gold.webp").convert("RGB")).copy()
    g = cv2.cvtColor(plate, cv2.COLOR_RGB2GRAY)
    small = cv2.resize(g, (g.shape[1] // 4, g.shape[0] // 4))
    c = cv2.HoughCircles(cv2.GaussianBlur(small, (0, 0), 2), cv2.HOUGH_GRADIENT, 1.2, 400,
                         param1=80, param2=40, minRadius=60, maxRadius=110)
    ccx, ccy, cr = (c[0][0] * 4).tolist()
    print(f"  coin at ({ccx:.0f},{ccy:.0f}) r={cr:.0f}")
    med_h = int(cr * 2 * 1.1)
    med = rgba_f(scaled(oval, med_h))
    f = plate.astype(np.float32) / 255
    # seated into the bar: a dark contact shadow, then a warm halo of light
    sh = shadow_layer(med[..., 3], blur=med_h * 0.03, opacity=0.85, dy=int(med_h * 0.018), grow=1.25)
    f = paste(f, sh, ccx, ccy - cr * 0.07)
    f = paste(f, med, ccx, ccy - cr * 0.07)
    save_plate((np.clip(f, 0, 1) * 255 + 0.5).astype(np.uint8), "gji-gold", q=84, jpg=False)


def clean_lockup(oval):
    """the header lockup without its white halo: the crisp medallion seated
    over the real GEETHA JEWELLERS / SINCE 1998 wordmark (gold pixels only)"""
    lg = rgba_f(Image.open(os.path.join(OUT, "logo.webp")))
    h, w = lg.shape[:2]
    rgb, al = lg[..., :3], lg[..., 3]
    warm = np.clip((rgb[..., 0] - rgb[..., 2] - 0.06) / 0.16, 0, 1)
    rows = (np.arange(h) >= 189).astype(np.float32)[:, None]
    canvas = np.zeros((h + 8, w, 4), np.float32)
    canvas[8:, :, :3] = rgb
    canvas[8:, :, 3] = al * warm * rows
    med = rgba_f(scaled(oval, 152))
    canvas[..., :3] *= canvas[..., 3:4]                      # premultiply
    sh = shadow_layer(med[..., 3], blur=5, opacity=0.22, dy=3, grow=1.2)
    for layer in (sh, med):
        lh, lw = layer.shape[:2]
        y0, x0 = int(round(108.76 + 8 - lh / 2)), int(round(212.11 - lw / 2))
        a = layer[..., 3:4]
        reg = canvas[y0:y0 + lh, x0:x0 + lw]
        reg[..., :3] = layer[..., :3] * a + reg[..., :3] * (1 - a)
        reg[..., 3:4] = a + reg[..., 3:4] * (1 - a)
    canvas[..., :3] /= np.maximum(canvas[..., 3:4], 1e-4)
    im = Image.fromarray((np.clip(canvas, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA")
    return im.crop(im.getchannel("A").getbbox())


# ------------------------------------------------------------------ offer plates
def build_offer(oval):
    print("offer:")
    logo = clean_lockup(oval)
    logo.save(os.path.join(OUT, "gj-lockup.png"), optimize=True)
    logo.save(os.path.join(OUT, "gj-lockup.webp"), "WEBP", quality=90, alpha_quality=95, method=6)
    print(f"  gj-lockup      {logo.size[0]}x{logo.size[1]}")
    jobs = [
        # name, box around the generated mark + tagline, logo width, logo centre
        ("offer-desktop", (60, 85, 300, 365), 300, (170, 228)),
        ("offer-mobile", (300, 35, 640, 236), 300, (470, 138)),
    ]
    for name, box, lw, (cx, cy) in jobs:
        plate = np.asarray(from_git(f"images/{name}.jpg").convert("RGB")).copy()
        m = ink_mask(plate, box)
        plate = fill_hole(plate, m)
        f = plate.astype(np.float32) / 255
        lg = rgba_f(logo.resize((lw, round(logo.height * lw / logo.width)), Image.LANCZOS))
        f = paste(f, lg, cx, cy)
        save_plate((np.clip(f, 0, 1) * 255 + 0.5).astype(np.uint8), name, q=86)


# ------------------------------------------------------------------ wall sign
def build_wall_sign(oval):
    print("wall sign:")
    jobs = [
        # name, box around the generated wall sign, medallion height, centre
        ("gjo-d", (1520, 80, 1745, 310), 184, (1632, 184)),
        ("gjo-dm", (600, 150, 925, 455), 290, (763, 304)),
    ]
    for name, box, mh, (cx, cy) in jobs:
        plate = np.asarray(from_git(f"images/{name}.jpg").convert("RGB")).copy()
        m = ink_mask(plate, box, thresh=12)
        plate = fill_hole(plate, m)
        f = plate.astype(np.float32) / 255
        med = rgba_f(scaled(oval, mh))
        # mounted proud of the marble, lit from the upper left like the old sign
        sh = shadow_layer(med[..., 3], blur=mh * 0.035, opacity=0.42, dx=int(mh * 0.035), dy=int(mh * 0.05), grow=1.3)
        f = paste(f, sh, cx, cy)
        f = paste(f, med, cx, cy)
        save_plate((np.clip(f, 0, 1) * 255 + 0.5).astype(np.uint8), name, q=86)


# ------------------------------------------------------------------ icons
def build_icons(oval):
    print("icons:")
    def square(size, pad):
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        med = scaled(oval, size - 2 * pad)
        canvas.alpha_composite(med, ((size - med.width) // 2, pad))
        return canvas
    square(180, 8).save(os.path.join(OUT, "apple-touch-icon.png"), optimize=True)
    square(32, 0).save(os.path.join(OUT, "favicon-32.png"), optimize=True)
    big = square(256, 0)
    big.save(os.path.join(ROOT, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)])
    print("  favicon.ico, favicon-32.png, apple-touch-icon.png")


# ------------------------------------------------------------------ app section
def build_app(oval):
    print("app:")
    # the phone's home screen: generated mark above GEETHA JEWELLERS -> medallion,
    # tilted with the phone (its wordmark rises ~6.6 deg to the right)
    scene = from_git("images/gja-scene.png").convert("RGBA")
    rgb = np.asarray(scene.convert("RGB")).copy()
    al = np.asarray(scene.getchannel("A"))
    box = (585, 378, 692, 500)
    m = ink_mask(rgb, box, thresh=14, dilate=7)
    rgb = fill_hole(rgb, m, radius=5, scale=2)
    f = rgb.astype(np.float32) / 255
    med = scaled(oval, 108).rotate(6.6, resample=Image.BICUBIC, expand=True)
    f = paste(f, rgba_f(med), 636, 440)
    out = Image.fromarray(np.dstack([(np.clip(f, 0, 1) * 255 + 0.5).astype(np.uint8), al]), "RGBA")
    out.save(os.path.join(OUT, "gja-scene.png"), optimize=True)
    out.save(os.path.join(OUT, "gja-scene.webp"), "WEBP", quality=86, alpha_quality=90, method=6)
    print(f"  gja-scene      {out.size[0]}x{out.size[1]}")

    # the (decorative) QR card's centre mark
    qr = np.asarray(from_git("images/gja-qr.png").convert("RGB")).astype(np.float32) / 255
    qr[70:127, 77:134] = 1.0
    qr = paste(qr, rgba_f(scaled(oval, 50)), 105.5, 98)
    Image.fromarray((np.clip(qr, 0, 1) * 255 + 0.5).astype(np.uint8)).save(os.path.join(OUT, "gja-qr.png"), optimize=True)
    print("  gja-qr         216x216")


# ------------------------------------------------------------------ men's bracelets
def build_bracelets():
    """three bracelet renders carried a generated "GJS" stamp on one link -
    lifted out, leaving the plain brushed-gold plate"""
    print("bracelets:")
    for name, box in [("gjbr-b3", (284, 374, 339, 436)), ("gjbr-b4", (278, 326, 322, 380)),
                      ("gjbr-b5", (350, 434, 394, 478))]:
        src = from_git(f"images/{name}.png").convert("RGBA")
        rgb = np.asarray(src.convert("RGB")).copy()
        al = np.asarray(src.getchannel("A"))
        m = ink_mask(rgb, box, thresh=7, sigma=5, dilate=5)
        x0, y0, x1, y1 = box
        keep = np.zeros_like(m)
        keep[y0 - 4:y1 + 4, x0 - 4:x1 + 4] = 255
        m = cv2.bitwise_and(m, keep)
        rgb = cv2.inpaint(rgb, m, 6, cv2.INPAINT_TELEA)
        out = Image.fromarray(np.dstack([rgb, al]), "RGBA")
        out.save(os.path.join(OUT, f"{name}.png"), optimize=True)
        out.save(os.path.join(OUT, f"{name}.webp"), "WEBP", quality=84, alpha_quality=90, method=6)
        print(f"  {name}")


if __name__ == "__main__":
    import sys
    oval = build_medallion()
    steps = sys.argv[1:] or ["intro", "offer", "wall", "icons", "app", "bracelets"]
    if "intro" in steps: build_intro(oval)
    if "offer" in steps: build_offer(oval)
    if "wall" in steps: build_wall_sign(oval)
    if "icons" in steps: build_icons(oval)
    if "app" in steps: build_app(oval)
    if "bracelets" in steps: build_bracelets()
