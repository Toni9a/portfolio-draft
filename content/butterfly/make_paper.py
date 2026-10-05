#!/usr/bin/env python3
"""Generate assets/paper-dark.webp: a tileable 512px dark paper texture (mottle, tooth, grain, fibres)."""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

rng = np.random.default_rng(11); N = 512

def fnoise(alpha):  # 1/f^alpha noise via FFT, so it tiles seamlessly
    F = np.fft.fft2(rng.standard_normal((N, N)))
    fx = np.fft.fftfreq(N)[:, None]; fy = np.fft.fftfreq(N)[None, :]
    f = np.sqrt(fx**2 + fy**2); f[0, 0] = 1
    n = np.real(np.fft.ifft2(F / f**alpha)); return (n - n.mean()) / n.std()

mott, grain, tooth = fnoise(1.3), fnoise(0.05), fnoise(0.6)
fib = Image.new('L', (N*3, N*3), 0); d = ImageDraw.Draw(fib)
for _ in range(700):
    x, y = rng.uniform(N, 2*N, 2); a = rng.uniform(0, np.pi); L = rng.uniform(6, 45); pts = []
    for _ in range(10):
        a += rng.normal(0, .2); x += np.cos(a)*L/10; y += np.sin(a)*L/10; pts.append((x, y))
    d.line(pts, fill=int(rng.uniform(50, 140)), width=1)
fa = np.asarray(fib.filter(ImageFilter.GaussianBlur(.45)), float) / 255
f = sum(fa[i*N:(i+1)*N, j*N:(j+1)*N] for i in range(3) for j in range(3))  # fold 3x3 so fibres wrap
base = np.array([31, 30, 27], float)
img = base + mott[..., None]*np.array([2.0, 1.9, 1.7]) + tooth[..., None]*1.6 + grain[..., None]*2.6 + f[..., None]*np.array([13, 12, 10])
out = Path(__file__).parent / 'assets' / 'paper-dark.webp'
Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(out, quality=92, method=6)
print('wrote', out.name, out.stat().st_size, 'bytes')
