  <script>
  /* ── Connecting orb: page loader + page-to-page transition (local preview) ──
     Points on a slowly turning sphere, joined to their near neighbours; a few
     sparks run along the links. Drawn on a canvas, coloured by --orb. */
  (() => {
    const LABEL = window.__BF_ORB_LABEL || 'Loading';
    const root = document.documentElement;
    const css = `
      .bf-orb-veil { position: fixed; inset: 0; z-index: 2000; display: grid; place-items: center; align-content: center; gap: 18px;
        background: rgba(3,3,3,.94); color: var(--orb, var(--dot, #5BB8FF)); opacity: 1; transition: opacity .45s ease, visibility 0s linear 0s;
        -webkit-backdrop-filter: blur(10px); backdrop-filter: blur(10px); }
      html.paper .bf-orb-veil { background: rgba(26,25,22,.95); }
      html.kraft .bf-orb-veil { background: rgba(62,46,30,.96); --orb: #fff1d8; }
      .bf-orb-veil.gone { opacity: 0; visibility: hidden; pointer-events: none; transition: opacity .55s ease, visibility 0s linear .55s; }
      .bf-orb-veil canvas { width: 132px; height: 132px; }
      .bf-orb-veil .bf-orb-label { font: 500 .62rem/1 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .22em; text-transform: uppercase; opacity: .7; color: #fff; }
      html.kraft .bf-orb-veil .bf-orb-label { color: #fff8ec; }
      @media (prefers-reduced-motion: reduce) { .bf-orb-veil, .bf-orb-veil.gone { transition: none; } }
    `;
    const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);

    const veil = document.createElement('div');
    veil.className = 'bf-orb-veil'; veil.setAttribute('role', 'status'); veil.setAttribute('aria-live', 'polite');
    veil.innerHTML = '<canvas width="264" height="264" aria-hidden="true"></canvas><span class="bf-orb-label"></span>';
    const label = veil.querySelector('.bf-orb-label');
    label.textContent = LABEL;
    (document.body || root).appendChild(veil);

    // sphere points (Fibonacci) and their links
    const N = 64, pts = [];
    for (let i = 0; i < N; i++) {
      const y = 1 - (i / (N - 1)) * 2, r = Math.sqrt(1 - y * y), t = i * 2.399963;
      pts.push([Math.cos(t) * r, y, Math.sin(t) * r]);
    }
    const links = [];
    for (let i = 0; i < N; i++) for (let j = i + 1; j < N; j++) {
      const d = Math.hypot(pts[i][0] - pts[j][0], pts[i][1] - pts[j][1], pts[i][2] - pts[j][2]);
      if (d < .52) links.push([i, j]);
    }
    const sparks = Array.from({ length: 7 }, () => ({ l: Math.random() * links.length | 0, t: Math.random() }));

    const cv = veil.querySelector('canvas'), cx = cv.getContext('2d');
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
    let running = true, t0 = performance.now();
    function drawConnect(t) {
      const col = getComputedStyle(veil).color;
      const W = cv.width, R = W * .36, C = W / 2;
      const ay = t * .55, ax = .42 + Math.sin(t * .4) * .12, breathe = 1 + Math.sin(t * 1.6) * .035;
      const cy = Math.cos(ay), sy = Math.sin(ay), cxr = Math.cos(ax), sxr = Math.sin(ax);
      const P = pts.map(([x, y, z]) => {
        const x1 = x * cy + z * sy, z1 = -x * sy + z * cy;
        const y2 = y * cxr - z1 * sxr, z2 = y * sxr + z1 * cxr;
        return [C + x1 * R * breathe, C + y2 * R * breathe, z2];
      });
      cx.clearRect(0, 0, W, W);
      cx.strokeStyle = col; cx.fillStyle = col; cx.lineWidth = 1.1;
      for (const [i, j] of links) {
        const z = (P[i][2] + P[j][2]) / 2;
        cx.globalAlpha = .06 + (z + 1) * .16;
        cx.beginPath(); cx.moveTo(P[i][0], P[i][1]); cx.lineTo(P[j][0], P[j][1]); cx.stroke();
      }
      for (const p of P) {
        const k = (p[2] + 1) / 2;
        cx.globalAlpha = .25 + k * .75;
        cx.beginPath(); cx.arc(p[0], p[1], 1.6 + k * 3, 0, 7); cx.fill();
      }
      for (const s of sparks) {            // little pulses travelling along the links
        s.t += .022;
        if (s.t >= 1) { s.t = 0; s.l = Math.random() * links.length | 0; }
        const [i, j] = links[s.l], a = P[i], b = P[j];
        const x = a[0] + (b[0] - a[0]) * s.t, y = a[1] + (b[1] - a[1]) * s.t, z = a[2] + (b[2] - a[2]) * s.t;
        cx.globalAlpha = .5 + (z + 1) * .25;
        cx.beginPath(); cx.arc(x, y, 3.2, 0, 7); cx.fill();
      }
    }

    // "composing": a tilted ring of vertical strokes whose heights swell in a travelling wave
    const M = 84;
    function drawCompose(t) {
      const col = getComputedStyle(veil).color;
      const W = cv.width, C = W / 2, R = W * .34;
      const ay = t * .7, tilt = .55 + Math.sin(t * .5) * .08;
      const ct = Math.cos(tilt), stl = Math.sin(tilt);
      cx.clearRect(0, 0, W, W);
      cx.strokeStyle = col; cx.lineCap = 'round';
      const cols = [];
      for (let k = 0; k < M; k++) {
        const th = k / M * Math.PI * 2 + ay;
        const x = Math.cos(th), z = Math.sin(th);
        const h = .16 + .14 * (0.5 + 0.5 * Math.sin(k / M * Math.PI * 6 - t * 2.4));   // band height
        const top = [x, -h, z], bot = [x, h, z];
        const proj = ([px, py, pz]) => { const y2 = py * ct - pz * stl, z2 = py * stl + pz * ct; return [C + px * R, C + y2 * R, z2]; };
        cols.push([proj(top), proj(bot)]);
      }
      cols.sort((p, q) => (p[0][2] + p[1][2]) - (q[0][2] + q[1][2]));          // back to front
      for (const [a, b] of cols) {
        const k = ((a[2] + b[2]) / 2 + 1) / 2;
        cx.globalAlpha = .12 + k * .85;
        cx.lineWidth = 1.2 + k * 2.2;
        cx.beginPath(); cx.moveTo(a[0], a[1]); cx.lineTo(b[0], b[1]); cx.stroke();
      }
    }

    let mode = 'compose';   // loading = composing ring, transitions = connecting orb
    function frame(now) {
      if (!running) return;
      const t = (now - t0) / 1000;
      (mode === 'compose' ? drawCompose : drawConnect)(t);
      cx.globalAlpha = 1;
      if (!reduce) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);

    const shownAt = performance.now();
    let hidden = false;
    window.bfOrbHide = () => {
      if (hidden) return; hidden = true;
      const wait = Math.max(0, 650 - (performance.now() - shownAt));   // never just flash
      setTimeout(() => { veil.classList.add('gone'); setTimeout(() => { running = false; }, 700); }, wait);
    };
    setTimeout(window.bfOrbHide, 4500);                                 // safety net

    // leaving: fade the orb in, then go
    window.bfGo = (href, text) => {
      mode = 'connect';
      label.textContent = text || 'Loading';
      const was = running; hidden = false; running = true;
      veil.classList.remove('gone'); if (!was) requestAnimationFrame(frame);
      setTimeout(() => { location.href = href; }, reduce ? 0 : 420);
    };
    const labelFor = u => /^\/blog(-butterfly)?(\.html)?(\/|$)/.test(u.pathname) ? 'Opening the blog'
      : /^\/work(\.html)?(\/|$)/.test(u.pathname) ? 'Opening the case study'
      : /^\/(index(-butterfly)?(\.html)?)?$/.test(u.pathname) ? 'Back to the homepage' : null;
    document.addEventListener('click', e => {
      const a = e.target.closest && e.target.closest('a[href]');
      if (!a || e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey || a.target === '_blank') return;
      const url = new URL(a.getAttribute('href'), location.href);
      if (url.origin !== location.origin) return;
      const text = labelFor(url);
      if (!text || (url.pathname === location.pathname && url.hash)) return;
      e.preventDefault(); bfGo(url.href, text);
    });
    // back/forward cache: never come back to a covered page
    addEventListener('pageshow', e => { if (e.persisted) { veil.classList.add('gone'); running = false; } });
  })();
  </script>
