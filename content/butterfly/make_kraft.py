#!/usr/bin/env python3
"""Generate the Kraft background: assets/kraft.webp (512px tileable cardboard) and
assets/sketches.webp (1600px tileable transparent layer of pencil + chalk doodles).
Deterministic (fixed seeds); re-run to regenerate."""
from pathlib import Path
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).parent / "assets"

# ── cardboard ────────────────────────────────────────────────────────────
def kraft():
    rng = np.random.default_rng(21); N = 1024
    def fnoise(alpha, stretch=1.0):
        F = np.fft.fft2(rng.standard_normal((N, N)))
        fx = np.fft.fftfreq(N)[:, None] * stretch; fy = np.fft.fftfreq(N)[None, :]
        f = np.sqrt(fx**2 + fy**2); f[0, 0] = 1
        n = np.real(np.fft.ifft2(F / f**alpha)); return (n - n.mean()) / n.std()
    mott, grain, streak = fnoise(1.3), fnoise(0.05), fnoise(1.0, stretch=6)  # streaks run with the grain
    fib = Image.new("L", (N * 3, N * 3), 128); d = ImageDraw.Draw(fib)
    for _ in range(5200):
        x, y = rng.uniform(N, 2 * N, 2); a = rng.normal(0, .5); L = rng.uniform(4, 30); pts = []
        for _ in range(8):
            a += rng.normal(0, .25); x += math.cos(a) * L / 8; y += math.sin(a) * L / 8; pts.append((x, y))
        d.line(pts, fill=int(rng.choice([rng.uniform(70, 110), rng.uniform(150, 200)])), width=1)
    for _ in range(1800):  # specks
        x, y = rng.uniform(N, 2 * N, 2); r = rng.uniform(.4, 1.3)
        d.ellipse([x - r, y - r, x + r, y + r], fill=int(rng.uniform(40, 90)))
    fa = (np.asarray(fib.filter(ImageFilter.GaussianBlur(.5)), float) - 128) / 128
    f = sum(fa[i*N:(i+1)*N, j*N:(j+1)*N] for i in range(3) for j in range(3))
    base = np.array([86, 64, 42], float)
    img = (base + mott[..., None] * np.array([5, 4, 3]) + streak[..., None] * np.array([3, 2.4, 1.6])
           + grain[..., None] * 2.4 + f[..., None] * np.array([14, 11, 8]))
    flute = np.sin(np.arange(N) / N * 2 * math.pi * 64)[None, :, None]   # faint corrugation, 16px pitch
    img = img + flute * np.array([1.6, 1.3, .9])
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(OUT / "kraft.webp", quality=90, method=6)

# ── sketches ─────────────────────────────────────────────────────────────
T, S = 1600, 2          # tile size, supersample
rng = np.random.default_rng(5)
canvas = Image.new("RGBA", (T * S, T * S), (0, 0, 0, 0))
draw = ImageDraw.Draw(canvas)
PENCIL = (26, 16, 8, 150)
CHALK = (245, 232, 205, 85)

def wobble(pts, amt=1.2):
    return [(x + rng.normal(0, amt), y + rng.normal(0, amt)) for x, y in pts]

def stroke(pts, col, w=1.6, passes=2, closed=False):
    if closed: pts = pts + [pts[0]]
    for p in range(passes):
        q = wobble(pts, 1.0 + p * .6)
        for dx in (-T, 0, T):          # draw wrapped copies so the tile is seamless
            for dy in (-T, 0, T):
                draw.line([((x + dx) * S, (y + dy) * S) for x, y in q], fill=col, width=int(w * S), joint="curve")

def curve(fn, n=80):
    return [fn(i / (n - 1)) for i in range(n)]

def circle(cx, cy, r, col, a0=0, a1=2 * math.pi, n=70):
    stroke(curve(lambda t: (cx + r * math.cos(a0 + (a1 - a0) * t), cy + r * math.sin(a0 + (a1 - a0) * t)), n), col)

def butterfly(cx, cy, s, col, rot):
    c, sn = math.cos(rot), math.sin(rot)
    tr = lambda x, y: (cx + (x * c - y * sn) * s, cy + (x * sn + y * c) * s)
    lobe = lambda a0, a1, R, side: [tr(side * R * math.sin(math.pi * t) * math.cos(a0 + (a1 - a0) * t),
                                       R * math.sin(math.pi * t) * math.sin(a0 + (a1 - a0) * t)) for t in np.linspace(0, 1, 40)]
    for side in (-1, 1):
        stroke(lobe(math.radians(-85), math.radians(-5), 1.0, side), col)    # forewing
        stroke(lobe(math.radians(8), math.radians(75), .68, side), col)      # hindwing
        stroke([tr(side * .05, -.1), tr(side * .55, -.5)], col, w=.9, passes=1)  # a vein
    stroke([tr(0, -.18), tr(0, .5)], col, w=2.4)
    stroke([tr(0, -.18), tr(-.2, -.55)], col, w=1.0); stroke([tr(0, -.18), tr(.2, -.55)], col, w=1.0)

def gear(cx, cy, r, col, teeth=12):
    pts = []
    for i in range(teeth * 4):
        a = i / (teeth * 4) * 2 * math.pi
        rr = r * (1.18 if (i % 4) in (1, 2) else 1.0)
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    stroke(pts, col, closed=True); circle(cx, cy, r * .35, col)

def cube(x, y, s, col):
    o = s * .45
    f = [(x, y), (x + s, y), (x + s, y + s), (x, y + s)]
    b = [(px + o, py - o) for px, py in f]
    stroke(f, col, closed=True); stroke(b, col, closed=True)
    for p, q in zip(f, b): stroke([p, q], col, w=1.2)

def dimension(x, y, L, col):
    stroke([(x, y), (x + L, y)], col, w=1.2)
    for px in (x, x + L):
        stroke([(px, y - 9), (px, y + 9)], col, w=1.2)
    for px, d in ((x, 1), (x + L, -1)):
        stroke([(px + d * 12, y - 5), (px, y), (px + d * 12, y + 5)], col, w=1.2)
    scribble(x + L / 2 - 18, y - 16, 36, col, lines=1, h=0)

def flower(cx, cy, r, col):
    for k in range(4):
        a = k * math.pi / 2 + rng.uniform(-.2, .2)
        stroke(curve(lambda t: (cx + math.cos(a) * r * math.sin(t * math.pi) * 1.0 + math.cos(a + math.pi / 2) * r * .45 * math.sin(2 * t * math.pi) * 0,
                                cy + math.sin(a) * r * math.sin(t * math.pi)) , 20), col)
        pa = [(cx + r * math.cos(a + d) * (1 - abs(d) * 1.2), cy + r * math.sin(a + d) * (1 - abs(d) * 1.2)) for d in np.linspace(-.6, .6, 14)]
        stroke([(cx, cy)] + pa + [(cx, cy)], col, w=1.3)
    circle(cx, cy, r * .12, col)

def scribble(x, y, w, col, lines=3, h=16):
    for i in range(lines):
        lw = w * rng.uniform(.6, 1)
        stroke(curve(lambda t: (x + t * lw, y + i * h + math.sin(t * lw / 4) * 2.2 + rng.normal(0, .4)), 50), col, w=1.1, passes=1)

def arrow(x, y, dx, dy, col):
    pts = curve(lambda t: (x + dx * t, y + dy * t + math.sin(t * math.pi) * -abs(dx) * .18))
    stroke(pts, col, w=1.3)
    (ex, ey), (px, py) = pts[-1], pts[-6]
    a = math.atan2(ey - py, ex - px)
    for s in (2.6, -2.6):
        stroke([(ex + 14 * math.cos(a + s), ey + 14 * math.sin(a + s)), (ex, ey)], col, w=1.3)

def wireframe(x, y, w, h, col):
    stroke([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], col, closed=True)
    stroke([(x, y + 22), (x + w, y + 22)], col, w=1.1)
    for i in range(3):
        bx = x + 14 + i * (w - 28) / 3
        stroke([(bx, y + 40), (bx + (w - 60) / 3, y + 40), (bx + (w - 60) / 3, y + h - 16), (bx, y + h - 16)], col, w=1.1, closed=True)

def hatch(x, y, w, h, col):
    for i in range(int(w / 7)):
        stroke([(x + i * 7, y + h), (x + i * 7 + h * .5, y)], col, w=1, passes=1)

# a sparse composition: one motif per cell of a jittered 4x4 grid, mixed pencil and chalk
motifs = [
    lambda x, y, c: butterfly(x, y, rng.uniform(60, 95), c, rng.uniform(-.5, .5)),
    lambda x, y, c: gear(x, y, rng.uniform(38, 60), c),
    lambda x, y, c: cube(x - 50, y - 40, rng.uniform(70, 100), c),
    lambda x, y, c: dimension(x - 90, y, rng.uniform(150, 220), c),
    lambda x, y, c: flower(x, y, rng.uniform(30, 48), c),
    lambda x, y, c: scribble(x - 80, y - 20, 160, c, lines=rng.integers(2, 5)),
    lambda x, y, c: arrow(x - 70, y + 20, rng.uniform(110, 170), rng.uniform(-60, 40), c),
    lambda x, y, c: wireframe(x - 90, y - 60, 180, 120, c),
    lambda x, y, c: (circle(x, y, rng.uniform(40, 70), c, 0, 2 * math.pi * .93), scribble(x + 70, y - 10, 90, c, 2)),
    lambda x, y, c: hatch(x - 60, y - 25, 120, 50, c),
]
order = rng.permutation(np.tile(np.arange(len(motifs)), 2))
k = 0
for gy in range(4):
    for gx in range(4):
        cx = (gx + .5) * T / 4 + rng.uniform(-90, 90)
        cy = (gy + .5) * T / 4 + rng.uniform(-90, 90)
        col = CHALK if rng.random() < .4 else PENCIL
        motifs[order[k % len(order)]](cx, cy, col); k += 1

def sketches():
    img = canvas.resize((T, T), Image.LANCZOS)
    img.save(OUT / "sketches.webp", quality=85, method=6)

if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    kraft(); sketches()
    for n in ("kraft.webp", "sketches.webp"):
        print("wrote", n, (OUT / n).stat().st_size, "bytes")
