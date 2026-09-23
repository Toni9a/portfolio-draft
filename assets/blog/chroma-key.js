/* chroma-key.js
 * Turns a Gemini cutout rendered on a flat chroma-green ground into a real
 * transparent PNG. Gemini image models do not return alpha, and SITE-HANDOFF
 * rules out hiding a rectangle with a CSS blend mode, so this does the job
 * properly on a canvas before the file is uploaded.
 *
 *   const { blob, width, height, coverage } = await chromaKey(dataUrl);
 *
 * 1. Estimates the background colour from the image border (median), so a
 *    slightly-off green (or any flat colour) still works.
 * 2. Flood-fills from the border through pixels close to that colour, so a
 *    colour that also appears inside the subject is only removed where it is
 *    connected to the outside. Isolated pockets of near-exact background
 *    colour (e.g. inside a film reel) are removed too.
 * 3. Feathers the edge: pixels next to the removed area get partial alpha by
 *    colour distance, and green spill is pulled out of them.
 * 4. Crops to the subject with a little padding and caps the long side.
 */
(function (global) {
  function median(arr) { const s = arr.slice().sort((a, b) => a - b); return s[s.length >> 1]; }

  async function loadImage(src) {
    const img = new Image();
    img.decoding = 'async';
    img.src = src;
    await img.decode();
    return img;
  }

  async function chromaKey(src, opts = {}) {
    const HARD = opts.hard ?? 70;      // below this distance: background
    const SOFT = opts.soft ?? 150;     // edge ramp up to this distance
    const POCKET = opts.pocket ?? 38;  // enclosed pixels this close are background too
    const MAX_SIDE = opts.maxSide ?? 1400;
    const PAD = opts.pad ?? 0.04;

    const img = await loadImage(src);
    const w = img.naturalWidth, h = img.naturalHeight;
    const c = document.createElement('canvas');
    c.width = w; c.height = h;
    const ctx = c.getContext('2d', { willReadFrequently: true });
    ctx.drawImage(img, 0, 0);
    const im = ctx.getImageData(0, 0, w, h);
    const d = im.data;

    // 1. background colour from the border
    const rs = [], gs = [], bs = [];
    const sample = (x, y) => { const k = (y * w + x) * 4; rs.push(d[k]); gs.push(d[k + 1]); bs.push(d[k + 2]); };
    for (let x = 0; x < w; x += 2) { sample(x, 0); sample(x, 1); sample(x, h - 1); sample(x, h - 2); }
    for (let y = 0; y < h; y += 2) { sample(0, y); sample(1, y); sample(w - 1, y); sample(w - 2, y); }
    const bg = [median(rs), median(gs), median(bs)];
    const dist = new Float32Array(w * h);
    for (let i = 0, k = 0; i < w * h; i++, k += 4) {
      const dr = d[k] - bg[0], dg = d[k + 1] - bg[1], db = d[k + 2] - bg[2];
      dist[i] = Math.sqrt(dr * dr + dg * dg + db * db);
    }

    // 2. flood fill from the border
    const bgMask = new Uint8Array(w * h);
    const stack = new Int32Array(w * h);
    let sp = 0;
    const push = (i) => { if (!bgMask[i] && dist[i] < HARD) { bgMask[i] = 1; stack[sp++] = i; } };
    for (let x = 0; x < w; x++) { push(x); push((h - 1) * w + x); }
    for (let y = 0; y < h; y++) { push(y * w); push(y * w + w - 1); }
    while (sp) {
      const i = stack[--sp], x = i % w, y = (i / w) | 0;
      if (x > 0) push(i - 1);
      if (x < w - 1) push(i + 1);
      if (y > 0) push(i - w);
      if (y < h - 1) push(i + w);
    }
    for (let i = 0; i < w * h; i++) if (dist[i] < POCKET) bgMask[i] = 1;

    // 3. alpha + edge feather + despill
    const isGreenBg = bg[1] > bg[0] + 40 && bg[1] > bg[2] + 40;
    for (let i = 0, k = 0; i < w * h; i++, k += 4) {
      if (bgMask[i]) { d[k + 3] = 0; continue; }
      const x = i % w, y = (i / w) | 0;
      const nearBg = (x > 0 && bgMask[i - 1]) || (x < w - 1 && bgMask[i + 1]) ||
        (y > 0 && bgMask[i - w]) || (y < h - 1 && bgMask[i + w]) ||
        (x > 1 && bgMask[i - 2]) || (x < w - 2 && bgMask[i + 2]) ||
        (y > 1 && bgMask[i - 2 * w]) || (y < h - 2 && bgMask[i + 2 * w]);
      if (nearBg && dist[i] < SOFT) {
        d[k + 3] = Math.round(255 * Math.max(0, Math.min(1, (dist[i] - HARD) / (SOFT - HARD))));
      }
      if (isGreenBg && (nearBg || d[k + 1] > Math.max(d[k], d[k + 2]) + 30)) {
        const cap = Math.max(d[k], d[k + 2]);
        if (d[k + 1] > cap) d[k + 1] = cap;
      }
    }
    ctx.putImageData(im, 0, 0);

    // 4. crop to subject
    let x0 = w, y0 = h, x1 = -1, y1 = -1, kept = 0;
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      if (d[(y * w + x) * 4 + 3] > 8) { kept++; if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
    }
    if (x1 < 0) throw new Error('Nothing left after removing the background.');
    const pad = Math.round(Math.max(x1 - x0, y1 - y0) * PAD);
    x0 = Math.max(0, x0 - pad); y0 = Math.max(0, y0 - pad);
    x1 = Math.min(w - 1, x1 + pad); y1 = Math.min(h - 1, y1 + pad);
    const cw = x1 - x0 + 1, ch = y1 - y0 + 1;
    const scale = Math.min(1, MAX_SIDE / Math.max(cw, ch));
    const out = document.createElement('canvas');
    out.width = Math.round(cw * scale); out.height = Math.round(ch * scale);
    const octx = out.getContext('2d');
    octx.imageSmoothingQuality = 'high';
    octx.drawImage(c, x0, y0, cw, ch, 0, 0, out.width, out.height);
    const blob = await new Promise((res) => out.toBlob(res, 'image/png'));
    return {
      blob,
      dataUrl: out.toDataURL('image/png'),
      width: out.width,
      height: out.height,
      background: bg,
      coverage: kept / (w * h), // share of the frame that is subject
    };
  }

  global.chromaKey = chromaKey;
})(window);
