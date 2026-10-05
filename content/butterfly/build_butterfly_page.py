#!/usr/bin/env python3
"""Build index-butterfly.html: the live index.html plus the Codex hydrangea
butterfly system (see ANIMATION-HANDOFF.md in the Codex butterfly study).

Local preview only. index.html and blog.html are never modified; this also writes
blog-butterfly.html (the blog with the same Ink / Paper / Kraft backgrounds). Re-run after editing
index.html:   python3 content/butterfly/build_butterfly_page.py
Then:         python3 -m http.server 8010   ->  http://localhost:8010/index-butterfly.html
"""
from pathlib import Path
import time
BUILD_STAMP = time.strftime("%H%M%S")

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "content" / "butterfly" / "src"   # pre-butterfly originals (index.html is generated once published)
SRC = SRC_DIR / "index.src.html" if (SRC_DIR / "index.src.html").exists() else ROOT / "index.html"
BLOG_SRC = SRC_DIR / "blog.src.html" if (SRC_DIR / "blog.src.html").exists() else ROOT / "blog.html"
OUT = ROOT / "index-butterfly.html"
ASSETS = "content/butterfly/assets"

CSS = r"""
    /* ══════════════════════════════════
       BUTTERFLY LAYER (local preview)
    ══════════════════════════════════ */
    .hero-right { position: relative; }
    .bf-art-wrap {
      position: relative;
      width: min(54vw, 86vh, 760px);
      aspect-ratio: 1;
      margin-right: -1.5vw;
      flex-shrink: 0;
    }
    .bf-art {
      display: block; width: 100%; height: 100%;
      /* cut-out PNG (black keyed to alpha), so the page and the butterflies behind it show through */
      user-select: none; pointer-events: none;
      opacity: 0; transform: scale(.985);
      transition: opacity 900ms ease, transform 1400ms cubic-bezier(.22,.72,.2,1);
    }
    .bf-art.ready { opacity: 1; transform: none; }

    /* cards are slightly see-through so a butterfly drifting behind one glows faintly through it */
    .project-card { background: rgba(3,3,3,.6); backdrop-filter: blur(3px); -webkit-backdrop-filter: blur(3px); }
    .project-card:hover { background: rgba(10,10,10,.82); }

    /* the flock sits BEHIND the page (z-index -1): cards and the hydrangea paint over it */
    .flock-layer {
      --butterfly-color: #5BB8FF;
      --sprite-filter: saturate(.55) brightness(.9);
      position: fixed; inset: 0; z-index: -1;
      pointer-events: none; overflow: visible;
      transition: opacity 700ms ease;
    }
    .flock-layer.away, body.modal-open .flock-layer { opacity: 0; }

    .flight {
      --size: 86px; --scale: 1; --angle: 0deg; --loop: 5.8s;
      position: absolute;
      left: var(--x); top: var(--y);
      width: var(--size); height: calc(var(--size) * .72);
      transform-origin: 50% 50%;
      offset-path: var(--path); offset-distance: 0%; offset-rotate: 0deg;
      animation: bf-follow-path var(--loop) linear var(--delay, 0s) infinite;
      color: var(--butterfly-color);
      filter: drop-shadow(0 0 2px color-mix(in srgb, currentColor 48%, transparent))
              drop-shadow(0 0 6px color-mix(in srgb, currentColor 24%, transparent));
      perspective: 340px;
      opacity: 1;
      transition: left 2.6s cubic-bezier(.3,.6,.2,1), top 2.6s cubic-bezier(.3,.6,.2,1),
                  opacity 1.4s ease, color 700ms ease, filter 700ms ease, width 600ms ease, height 600ms ease;
    }
    .flight.resting { opacity: 0; }
    .flock-layer.tracking .flight { transition: opacity 1.4s ease, color 700ms ease, filter 700ms ease; }
    .flock-layer.compact .flight { width: calc(var(--size) * .62); height: calc(var(--size) * .62 * .72); }

    .butterfly {
      position: absolute; inset: 0;
      transform-style: preserve-3d; transform-origin: 50% 52%;
      /* bank + glimmer: each butterfly surfaces out of the dark and sinks back on its own clock */
      animation:
        bf-bank var(--bank-loop, 4.8s) ease-in-out var(--bank-delay, 0s) infinite,
        bf-glimmer var(--glim, 11s) ease-in-out var(--glim-delay, 0s) infinite;
    }
    .wing-side {
      position: absolute; top: 0; width: 50%; height: 100%;
      transform-style: preserve-3d;
      background: url("ASSETS/butterfly-sprite.webp") no-repeat;
      background-size: 200% 100%;
      filter: var(--sprite-filter);
      transition: filter 700ms ease;
    }
    .wing-side.left  { left: 0;  transform-origin: 100% 52%; background-position: left center;
      animation: bf-flap-left  var(--flap, 760ms) cubic-bezier(.4,0,.6,1) var(--flap-delay, 0s) infinite alternate; }
    .wing-side.right { right: 0; transform-origin: 0 52%;    background-position: right center;
      animation: bf-flap-right var(--flap, 760ms) cubic-bezier(.4,0,.6,1) var(--flap-delay, 0s) infinite alternate; }

    @keyframes bf-flap-left  { from { transform: rotateY(12deg) rotateZ(-3deg); }  to { transform: rotateY(67deg) rotateZ(3deg); } }
    @keyframes bf-flap-right { from { transform: rotateY(-12deg) rotateZ(3deg); }  to { transform: rotateY(-67deg) rotateZ(-3deg); } }
    @keyframes bf-follow-path { from { offset-distance: 0%; } to { offset-distance: 100%; } }
    @keyframes bf-bank {
      0%, 100% { transform: rotateZ(var(--angle)) rotateX(0deg) scale(var(--scale)); }
      24% { transform: rotateZ(var(--bank-a, 14deg)) rotateX(5deg) scale(var(--scale)); }
      56% { transform: rotateZ(var(--bank-b, -12deg)) rotateX(-4deg) scale(var(--scale)); }
      79% { transform: rotateZ(var(--bank-c, 8deg)) rotateX(3deg) scale(var(--scale)); }
    }
    /* in the hero (--drift: 1) each butterfly surfaces from under the petals, small, and flies
       outwards as it fades; in the work sections (--drift: 0) it just glimmers in place */
    @keyframes bf-glimmer {
      0%   { opacity: 0;   translate: calc(var(--drift, 0) * 46px) calc(var(--drift, 0) * 10px); scale: calc(1 - var(--drift, 0) * .45); }
      20%  { opacity: 1; }
      60%  { opacity: .85; }
      80%  { opacity: 0;   translate: calc(var(--drift, 0) * -130px) calc(var(--drift, 0) * var(--rise, -40px)); scale: 1; }
      100% { opacity: 0;   translate: calc(var(--drift, 0) * -130px) calc(var(--drift, 0) * var(--rise, -40px)); scale: 1; }
    }
    .flock-layer.in-hero { --drift: 1; }

    /* ── paper background (toggle) ── */
    html.paper body {
      background-color: #1e1d1a;
      background-image:
        radial-gradient(ellipse 120% 90% at 50% 35%, transparent 50%, rgba(0,0,0,.5) 100%),
        url("ASSETS/paper-dark.webp");
      background-repeat: no-repeat, repeat;
      background-size: 100% 100%, 512px 512px;
      background-attachment: fixed, fixed;
    }
    html.paper .project-card { background: rgba(6,6,6,.66); }
    html.paper .project-card:hover { background: rgba(12,12,12,.85); }
    html.paper .projects-grid { box-shadow: 0 24px 70px rgba(0,0,0,.45); }
    html.paper .hat-section-header,
    html.paper .section-title { text-shadow: 0 1px 0 rgba(0,0,0,.35); }

    /* ── kraft background (toggle): cardboard + a sparse layer of pencil/chalk sketches ── */
    html.kraft body {
      background-color: #56402a;
      background-image:
        radial-gradient(ellipse 120% 90% at 50% 35%, transparent 45%, rgba(20,12,4,.55) 100%),
        url("content/butterfly/assets/sketches.webp"),
        url("content/butterfly/assets/kraft.webp");
      background-repeat: no-repeat, repeat, repeat;
      background-size: 100% 100%, 1600px 1600px, 1024px 1024px;
      background-attachment: fixed, scroll, fixed;   /* sketches scroll with the page, like doodles on the board */
    }
    html.kraft .project-card { background: rgba(14,10,6,.72); }
    html.kraft .project-card:hover { background: rgba(18,13,8,.88); }
    html.kraft .projects-grid { box-shadow: 0 26px 70px rgba(20,10,0,.5); border-color: rgba(0,0,0,.35); }
    /* lift the faint greys that sit directly on the board */
    html.kraft .hero-bio { color: rgba(255,248,236,.82); }
    html.kraft .hero-bio-muted { color: rgba(255,248,236,.55); }
    html.kraft .hnl-label { color: rgba(255,248,236,.72); }
    html.kraft .hnl-arrow { color: rgba(255,248,236,.4); }
    html.kraft .section-label, html.kraft .hat-section-desc { color: rgba(255,248,236,.6); }
    html.kraft .hat-section-header, html.kraft .section-title, html.kraft .hero-name { text-shadow: 0 1px 2px rgba(30,15,0,.45); }
    /* hat portraits are transparent cut-outs: drop the black box on paper/kraft, keep a soft shadow */
    html.kraft .hat-thumb, html.paper .hat-thumb { background: transparent; }
    html.kraft .hat-thumb img, html.paper .hat-thumb img { filter: drop-shadow(0 10px 14px rgba(20,10,0,.45)); }
    /* E / i / heart tiles: frosted card instead of a black square */
    html.kraft .dot-tile {
      background: rgba(255,240,215,.07);
      box-shadow: inset 0 0 0 1px rgba(255,240,215,.16), 0 10px 24px rgba(20,10,0,.28);
      backdrop-filter: blur(5px); -webkit-backdrop-filter: blur(5px);
    }
    html.kraft .dot-tile:hover { background: rgba(255,240,215,.14); }
    html.kraft .dot { opacity: .22; }
    html.kraft .dot.lit { opacity: .95; }
    html.kraft .about-photo img { box-shadow: 0 18px 40px rgba(20,10,0,.45); }

    /* hover labels on the E / i / heart tiles */
    .dot-tile { position: relative; }
    .dot-tile[data-label]::after {
      content: attr(data-label);
      position: absolute; top: calc(100% + 9px); left: 50%;
      transform: translate(-50%, 0); opacity: .55; pointer-events: none;
      padding: 0; white-space: nowrap; color: rgba(255,255,255,.9);
      font: 500 .6rem/1 'Space Grotesk', sans-serif; letter-spacing: .16em; text-transform: uppercase;
      transition: opacity .2s ease, transform .2s ease;
    }
    .dot-tile:hover::after, .dot-tile:focus-visible::after { opacity: 1; transform: translate(-50%, 2px); }
    html.kraft .dot-tile[data-label]::after { color: #fff8ec; opacity: .7; }
    .dot-tile:focus-visible { outline: 1px solid rgba(255,255,255,.5); outline-offset: 3px; }

    /* work tile = a live map of the five hats: one column per hat, filling as you scroll through it */
    .dot-tile.work-map .dot { animation: none !important; transition: opacity .35s ease, background-color .4s ease, transform .35s ease; }
    .dot-tile.work-map .dot.wm-off { opacity: .13; }
    .dot-tile.work-map .dot.wm-on { opacity: .95; }
    .dot-tile.work-map .dot.wm-now { opacity: 1; transform: scale(1.15); }
    .dot-tile.work-map.idle .dot { animation: wm-wave 2.6s ease-in-out infinite !important; animation-delay: calc(var(--c) * .14s + (6 - var(--r)) * .07s) !important; }
    @keyframes wm-wave { 0%, 100% { opacity: .13; } 40% { opacity: .9; } 70% { opacity: .13; } }
    .dot-tile.work-map:hover .dot.wm-off { opacity: .32; }

    /* heart / i tiles: crisper — off dots nearly gone, lit dots brighter with a soft glow, slower deeper pulse */
    .dot-tile[data-pattern="heart"] .dot:not(.lit), .dot-tile[data-pattern="i"] .dot:not(.lit) { opacity: .05; }
    .dot-tile[data-pattern="heart"] .dot.lit, .dot-tile[data-pattern="i"] .dot.lit {
      box-shadow: 0 0 6px color-mix(in srgb, var(--dot) 70%, transparent);
    }
    .dot-tile[data-pattern="heart"] .dot.lit.pulsing { animation: heart-beat 1.5s ease-in-out infinite; animation-delay: 0s !important; }  /* beats as one */
    @keyframes heart-beat { 0%, 100% { opacity: 1; transform: scale(1); } 12% { opacity: 1; transform: scale(1.18); } 24% { opacity: .75; transform: scale(1); } 36% { opacity: 1; transform: scale(1.12); } 60% { opacity: .7; } }
    .dot-tile[data-pattern="i"] .dot.lit.pulsing { animation: i-glow 2.4s ease-in-out infinite; }
    @keyframes i-glow { 0%, 100% { opacity: 1; } 50% { opacity: .6; } }
    html.kraft .dot-tile[data-pattern="heart"] .dot:not(.lit), html.kraft .dot-tile[data-pattern="i"] .dot:not(.lit) { opacity: .08; }

    /* case-study cards: plain cards with a badge and a link line */
    .case-card { position: relative; overflow: hidden; isolation: isolate; color: inherit; text-decoration: none; cursor: pointer; }
    .case-badge {
      display: inline-block; padding: .08rem .45rem; border-radius: 100px; margin-left: .15rem;
      border: 1px solid currentColor; font-size: .58rem; letter-spacing: .1em; opacity: .85;
    }
    .case-cta { font-size: .66rem; letter-spacing: .12em; text-transform: uppercase; opacity: .75; transition: opacity .2s, transform .2s; }
    .case-card:hover .case-cta { opacity: 1; transform: translateX(3px); }
    #contracting .case-badge, #contracting .case-cta { color: var(--hat-contracting); }
    #thinking .case-badge, #thinking .case-cta { color: var(--hat-thinking); }
    #artisting .case-badge, #artisting .case-cta { color: var(--hat-artisting); }
    #engineering .case-badge, #engineering .case-cta { color: var(--hat-engineering); }
    #marketing .case-badge, #marketing .case-cta { color: var(--hat-marketing); }

    /* left / right arrows beside the scroll dots, for people without a trackpad */
    .grid-scroll-indicator { align-items: center; }
    .gsi-arrow {
      width: 30px; height: 30px; border-radius: 50%; display: grid; place-items: center;
      border: 1px solid rgba(255,255,255,.18); background: rgba(3,3,3,.55); color: rgba(255,255,255,.75);
      font: 400 .95rem/1 'Space Grotesk', sans-serif; cursor: pointer; margin: 0 .5rem;
      transition: background .2s, color .2s, opacity .2s, border-color .2s;
    }
    .gsi-arrow:hover:not(:disabled) { background: rgba(255,255,255,.12); color: #fff; border-color: rgba(255,255,255,.4); }
    .gsi-arrow:disabled { opacity: .25; cursor: default; }
    .gsi-arrow:focus-visible { outline: 1px solid rgba(255,255,255,.6); outline-offset: 2px; }
    .gsi-dot { cursor: pointer; }
    html.kraft .gsi-arrow { background: rgba(14,10,6,.55); border-color: rgba(255,240,215,.25); color: rgba(255,248,236,.85); }

    /* interests: click a tag to see related projects and writing */
    .interest-tag.is-btn { cursor: pointer; font-family: inherit; font-size: .7rem; line-height: 1.4; background: transparent; color: rgba(255,255,255,.55); border: 1px solid rgba(255,255,255,.12); transition: border-color .2s, background .2s, color .2s; }
    .interest-tag.is-btn:hover { border-color: rgba(255,255,255,.35); color: #fff; }
    html.kraft .interest-tag.is-btn { color: rgba(255,248,236,.75); border-color: rgba(255,240,215,.25); }
    .interest-tag.is-btn[aria-pressed="true"] { border-color: var(--cyan); color: #fff; background: rgba(91,184,255,.12); }
    .interest-panel { margin-top: .9rem; padding: 1rem 1.1rem; border-radius: 12px; border: 1px solid rgba(255,255,255,.1); background: rgba(3,3,3,.55); backdrop-filter: blur(6px); }
    .interest-panel[hidden] { display: none; }
    .interest-panel .ip-head { font-size: .72rem; letter-spacing: .14em; text-transform: uppercase; color: rgba(255,255,255,.45); margin-bottom: .7rem; }
    .interest-panel .ip-head b { color: #fff; font-weight: 500; }
    .interest-panel .ip-label { display: block; font-size: .62rem; letter-spacing: .14em; text-transform: uppercase; color: rgba(255,255,255,.35); margin: .6rem 0 .35rem; }
    .interest-panel ul { list-style: none; display: grid; gap: .3rem; }
    .interest-panel a, .interest-panel button.ip-item { color: rgba(255,255,255,.82); font: inherit; font-size: .84rem; background: none; border: 0; padding: 0; text-align: left; cursor: pointer; }
    .interest-panel a:hover, .interest-panel button.ip-item:hover { color: var(--cyan); }
    .interest-panel .ip-hat { font-size: .62rem; letter-spacing: .08em; margin-left: .4rem; opacity: .7; }
    .interest-panel .ip-none { font-size: .8rem; color: rgba(255,255,255,.4); }
    html.kraft .interest-panel { background: rgba(14,10,6,.6); border-color: rgba(255,240,215,.18); }
    .project-card.ip-flash { animation: ip-flash 1.6s ease 1; }
    @keyframes ip-flash { 0%, 100% { box-shadow: inset 0 0 0 0 transparent; } 25%, 60% { box-shadow: inset 0 0 0 2px var(--cyan); } }

    /* about: how I work + quiet education */
    .how-i-work { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px; margin-top: 2.2rem; border: 1px solid var(--border); border-radius: 14px; overflow: hidden; background: var(--border); }
    .how-i-work > div { background: rgba(3,3,3,.6); padding: 1.1rem 1.1rem 1.2rem; }
    .how-i-work span { display: block; font-size: .62rem; letter-spacing: .16em; color: var(--cyan); margin-bottom: .55rem; }
    .how-i-work b { display: block; font-weight: 500; font-size: .88rem; line-height: 1.35; color: rgba(255,255,255,.9); margin-bottom: .45rem; }
    .about-bio .how-i-work p { font-size: .78rem; line-height: 1.55; color: rgba(255,255,255,.5); margin: 0; }
    html.kraft .how-i-work > div { background: rgba(14,10,6,.6); }
    html.kraft .about-bio p { color: rgba(255,248,236,.78); }
    html.kraft .about-bio .how-i-work p { color: rgba(255,248,236,.6); }
    .edu-quiet { opacity: .7; }
    @media (max-width: 760px) { .how-i-work { grid-template-columns: 1fr; } }

    /* why the hydrangea */
    .bf-story-grid { display: grid; grid-template-columns: minmax(220px, 340px) 1fr; gap: clamp(2rem, 5vw, 5rem); align-items: center; }
    .bf-story-art { width: 100%; height: auto; color: rgba(255,255,255,.55); }
    html.kraft .bf-story-art { color: rgba(255,244,226,.7); }
    .bf-story-text p { font-size: 1.02rem; line-height: 1.75; color: rgba(255,255,255,.62); max-width: 60ch; margin-bottom: 1.1rem; }
    .bf-story-text p:first-child { font-size: 1.22rem; line-height: 1.6; color: rgba(255,255,255,.88); }
    .bf-story-text .bf-story-note { font-size: .82rem; color: rgba(255,255,255,.38); margin-top: 1.6rem; }
    html.kraft .bf-story-text p { color: rgba(255,248,236,.78); }
    html.kraft .bf-story-text p:first-child { color: #fff8ec; }
    html.kraft .bf-story-text .bf-story-note { color: rgba(255,248,236,.55); }
    @media (max-width: 760px) { .bf-story-grid { grid-template-columns: 1fr; } .bf-story-art { max-width: 240px; } }

    /* active hat link in the hero */
    .hero-nav-link.is-active .hnl-label { color: rgba(255,255,255,.9); }
    .hero-nav-link:focus-visible { outline: 1px solid rgba(255,255,255,.5); outline-offset: 4px; border-radius: 4px; }

    .bf-controls {
      position: fixed; left: 16px; bottom: 16px; z-index: 300;
      display: flex; align-items: center; gap: 4px;
      padding: 4px 4px 4px 12px; border-radius: 100px;
      border: 1px solid rgba(255,255,255,.14); background: rgba(3,3,3,.75);
      backdrop-filter: blur(8px);
      font-family: 'Space Grotesk', sans-serif;
    }
    .bf-controls .bf-tag { font-size: .6rem; letter-spacing: .14em; text-transform: uppercase; color: rgba(255,255,255,.4); margin-right: 6px; }
    .bf-controls button {
      font: 500 .68rem/1 'Space Grotesk', sans-serif; letter-spacing: .06em;
      padding: 6px 11px; border-radius: 100px; border: 0; cursor: pointer;
      background: transparent; color: rgba(255,255,255,.5);
      transition: background .2s, color .2s;
    }
    .bf-controls button[aria-pressed="true"] { background: rgba(255,255,255,.12); color: #fff; }

    @media (prefers-reduced-motion: reduce) {
      .flight, .wing-side { animation-play-state: paused !important; }
      .butterfly { animation: none !important; opacity: .85; }
      .flight { transition: opacity 1.4s ease, color 700ms ease, filter 700ms ease !important; }
    }
""".replace("ASSETS", ASSETS)

# Five flights, timings and paths copied from the Codex study. hx/hy = home position as a
# fraction of the hydrangea artwork (its loose left edge). glim = fade-in/out cycle.
FLIGHTS = [
    dict(hx=.26, hy=.23, size=118, angle=-19, a=10, b=-28, c=-5, bl=5.3, bd=-1.2, loop=11.8, d=-2.1, flap=820, fd=0, glim=13, gd=-2, rise="-70px",
         path="M 0 0 C -36 -32 -92 -13 -84 33 C -76 76 2 72 34 29 C 58 -5 30 -35 0 0 Z"),
    dict(hx=.32, hy=.36, size=62, angle=7, a=24, b=-15, c=17, bl=4.4, bd=-2.4, loop=9.6, d=-1.3, flap=690, fd=-.2, glim=9.5, gd=-6, rise="-30px",
         path="M 0 0 C 18 -36 -14 -67 -51 -47 C -94 -24 -83 34 -34 55 C 16 76 51 28 0 0 Z"),
    dict(hx=.29, hy=.43, size=78, angle=16, a=-17, b=29, c=4, bl=5.0, bd=-.8, loop=12.4, d=-4, flap=740, fd=-.45, glim=11, gd=-1, rise="-10px",
         path="M 0 0 C -26 -44 -83 -41 -96 5 C -108 53 -45 88 6 65 C 52 43 48 -20 0 0 Z"),
    dict(hx=.325, hy=.51, size=54, angle=-9, a=18, b=-25, c=12, bl=4.1, bd=-1.9, loop=10.3, d=-.8, flap=640, fd=-.33, glim=8.5, gd=-4.5, rise="20px",
         path="M 0 0 C 8 -35 -33 -60 -68 -36 C -105 -11 -78 45 -27 63 C 25 81 58 25 0 0 Z"),
    dict(hx=.30, hy=.58, size=70, angle=20, a=-11, b=31, c=-19, bl=5.7, bd=-3, loop=13.2, d=-3.2, flap=780, fd=-.51, glim=12, gd=-8.5, rise="45px",
         path="M 0 0 C -22 -41 -72 -34 -91 10 C -110 59 -44 93 12 66 C 62 40 51 -22 0 0 Z"),
]

def flight_html(f):
    style = (f"--hx:{f['hx']};--hy:{f['hy']};--x:-200px;--y:-200px;--size:{f['size']}px;--angle:{f['angle']}deg;"
             f"--bank-a:{f['a']}deg;--bank-b:{f['b']}deg;--bank-c:{f['c']}deg;--bank-loop:{f['bl']}s;--bank-delay:{f['bd']}s;"
             f"--path:path('{f['path']}');--loop:{f['loop']}s;--delay:{f['d']}s;--flap:{f['flap']}ms;--flap-delay:{f['fd']}s;"
             f"--glim:{f['glim']}s;--glim-delay:{f['gd']}s;--rise:{f['rise']}")
    return (f'      <div class="flight" style="{style}">\n'
            '        <div class="butterfly"><div class="wing-side left"></div><div class="wing-side right"></div></div>\n'
            '      </div>')

HERO_ART = f"""<div class="bf-art-wrap">
      <img class="bf-art" src="{ASSETS}/hydrangea-cutout.webp" alt="A blue hydrangea whose edge petals turn into butterflies" onload="this.classList.add('ready')">
{chr(10).join(flight_html(f) for f in FLIGHTS)}
    </div>"""

JS = r"""
  // ══ BUTTERFLY LAYER (local preview; see content/butterfly/README.md) ══
  (() => {
    // ── background toggle: ink (black) / paper ──
    const root = document.documentElement;
    const store = { get: () => { try { return localStorage.getItem('bf-bg'); } catch { return null; } },
                    set: v => { try { localStorage.setItem('bf-bg', v); } catch {} } };
    const controls = document.createElement('div');
    controls.className = 'bf-controls';
    controls.innerHTML = '<span class="bf-tag">preview · local</span>' +
      '<button type="button" data-bg="ink">Ink</button><button type="button" data-bg="paper">Paper</button>' +
      '<button type="button" data-bg="kraft">Kraft</button>';
    document.body.appendChild(controls);
    const setBg = bg => {
      root.classList.toggle('paper', bg === 'paper');
      root.classList.toggle('kraft', bg === 'kraft');
      controls.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.bg === bg)));
      store.set(bg);
    };
    controls.addEventListener('click', e => { const b = e.target.closest('button'); if (b) setBg(b.dataset.bg); });
    setBg(['paper', 'kraft'].includes(store.get()) ? store.get() : 'ink');

    document.querySelectorAll('.dot-tile[tabindex]').forEach(t => t.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); t.click(); }
    }));

    // ── project grids: arrows + clickable dots (the dots row is built by index.html's own script) ──
    document.querySelectorAll('.projects-grid').forEach(grid => {
      const ind = grid.nextElementSibling;
      if (!ind || !ind.classList.contains('grid-scroll-indicator')) return;
      const step = () => grid.clientWidth / 3;                 // one card column
      const mk = (dir, label) => {
        const b = document.createElement('button');
        b.type = 'button'; b.className = 'gsi-arrow'; b.setAttribute('aria-label', label);
        b.textContent = dir < 0 ? '←' : '→';
        b.addEventListener('click', () => grid.scrollBy({ left: dir * step(), behavior: 'smooth' }));
        return b;
      };
      const prev = mk(-1, 'Previous projects'), next = mk(1, 'Next projects');
      ind.prepend(prev); ind.append(next);
      ind.querySelectorAll('.gsi-dot').forEach((d, i) =>
        d.addEventListener('click', () => grid.scrollTo({ left: i * step(), behavior: 'smooth' })));
      const update = () => {
        prev.disabled = grid.scrollLeft < 4;
        next.disabled = grid.scrollLeft + grid.clientWidth > grid.scrollWidth - 4;
      };
      grid.addEventListener('scroll', update, { passive: true });
      addEventListener('resize', update);
      update();
    });
    // case-study cards are links: don't let the project modal catch their clicks
    document.addEventListener('click', e => {
      if (e.target.closest && e.target.closest('.case-card')) e.stopPropagation();
    }, true);

    // ── interests: click a tag → related projects on this page + posts from the blog ──
    (() => {
      const label = [...document.querySelectorAll('.about-side .side-label')].find(l => l.textContent.trim() === 'Interests');
      const list = label && label.nextElementSibling;
      if (!list) return;
      const KEYS = {
        'Mobile apps': /\b(apps?|ios|android|iphone|swiftui|mobile|shortcuts?|testflight)\b/i,
        'Consumer hardware': /\b(hardware|devices?|dyson|foldables?|glasses|speaker|iphone|apple|camera|wearables?|3d print\w*|nfc)\b/i,
        'Electric vehicles': /\b(electric|evs?|scooter|vehicles?|autonomous|tesla|powertrain)\b/i,
        'Mixed reality': /\b(mixed reality|ar|vr|xr|vision pro|headsets?|smart glasses|meta glasses|digital twin|lidar)\b/i,
        'Half marathons': /\b(half[- ]?marathons?|marathons?|running(?!\s+(training|sessions|workshops|programmes|courses))|strava|halfmara|training plan)\b/i,
        'EdTech': /\b(edtech|tutor\w*|learning|education|flashcards?|workshops?|upskilling|students?)\b/i,
        'Film': /\b(films?|movies?|cinema|letterboxd|lyric\w*)\b/i,
        'Football': /\b(football|soccer)\b/i,
        'BSL': /\b(bsl|sign language|deaf)\b/i,
      };
      const BLOG_URL = 'https://dmlwcrbjetpgqacblvqp.supabase.co/rest/v1/published_posts';
      const BLOG_KEY = /*__BLOG_KEY__*/'';
      let postsP = null;
      const loadPosts = () => postsP || (postsP = fetch(BLOG_URL + '?select=slug,title,excerpt,body_md,topic_tags,published_at&published_at=lte.' +
          encodeURIComponent(new Date().toISOString()) + '&order=published_at.desc', { headers: { apikey: BLOG_KEY, Authorization: 'Bearer ' + BLOG_KEY } })
        .then(r => r.ok ? r.json() : []).catch(() => []));
      const esc = t => String(t || '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
      const plain = t => String(t || '').replace(/\*/g, '');

      const panel = document.createElement('div');
      panel.className = 'interest-panel'; panel.hidden = true; panel.setAttribute('aria-live', 'polite');
      list.after(panel);

      const cards = [...document.querySelectorAll('#work .project-card')];
      async function show(name, re) {
        const projects = cards.filter(c => re.test(c.textContent + ' ' + (c.dataset.note || ''))).slice(0, 7);
        panel.hidden = false;
        const projHtml = projects.length ? '<ul>' + projects.map((c, i) => {
          const t = esc(c.querySelector('.card-title')?.textContent);
          const hat = c.closest('.hat-section')?.id || '';
          return c.matches('a') ? `<li><a href="${c.getAttribute('href')}">${t}</a><span class="ip-hat">${hat} · case study</span></li>`
                                : `<li><button type="button" class="ip-item" data-i="${cards.indexOf(c)}">${t}</button><span class="ip-hat">${hat}</span></li>`;
        }).join('') + '</ul>' : '<p class="ip-none">Nothing built on this yet.</p>';
        const render = posts => {
          const hits = (posts || []).filter(p => re.test([p.title, p.excerpt, p.body_md, (p.topic_tags || []).join(' ')].join(' '))).slice(0, 4);
          const postHtml = hits.length ? '<ul>' + hits.map(p => `<li><a href="blog-butterfly.html#${encodeURIComponent(p.slug)}">${esc(plain(p.title))}</a></li>`).join('') + '</ul>'
                                       : (posts === null ? '<p class="ip-none">Loading…</p>' : '<p class="ip-none">Nothing written on this yet.</p>');
          panel.innerHTML = `<p class="ip-head">Related to <b>${esc(name)}</b></p><span class="ip-label">Built</span>${projHtml}<span class="ip-label">Written</span>${postHtml}`;
        };
        render(null);
        render(await loadPosts());
      }

      panel.addEventListener('click', e => {
        const b = e.target.closest('button.ip-item'); if (!b) return;
        const card = cards[+b.dataset.i];
        card.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'center' });
        card.classList.remove('ip-flash'); void card.offsetWidth; card.classList.add('ip-flash');
      });

      list.querySelectorAll('.interest-tag').forEach(tag => {
        const name = tag.textContent.trim(), re = KEYS[name];
        if (!re) return;
        const btn = document.createElement('button');
        btn.type = 'button'; btn.className = tag.className + ' is-btn'; btn.textContent = name; btn.setAttribute('aria-pressed', 'false');
        tag.replaceWith(btn);
        btn.addEventListener('click', () => {
          const on = btn.getAttribute('aria-pressed') !== 'true';
          list.querySelectorAll('.is-btn').forEach(b => b.setAttribute('aria-pressed', 'false'));
          if (!on) { panel.hidden = true; return; }
          btn.setAttribute('aria-pressed', 'true');
          show(name, re);
        });
      });
    })();

    // ── the work tile becomes a map of the page: 5 columns = 5 hats, each fills bottom-up as you scroll through it ──
    (() => {
      const tile = document.querySelector('.dot-tile[data-pattern="E"]');
      const order = ['contracting', 'thinking', 'artisting', 'engineering', 'marketing'];
      const secs = order.map(id => document.getElementById(id));
      if (!tile || secs.some(s => !s)) return;
      const colours = { contracting: '#A78BFA', thinking: '#C4956A', artisting: '#6EE7B7', engineering: '#5BB8FF', marketing: '#FBBF24' };
      const build = () => {
        const dots = [...tile.querySelectorAll('.dot')];
        if (dots.length !== 35) return null;
        tile.classList.add('work-map');
        dots.forEach((d, i) => {
          const r = Math.floor(i / 5), c = i % 5;
          d.classList.remove('lit', 'pulsing', 'hover-boost'); d.dataset.active = '0';
          d.style.background = colours[order[c]];
          d.style.setProperty('--c', c); d.style.setProperty('--r', r);
        });
        return dots;
      };
      let dots = build();
      if (!dots) return;
      const paint = () => {
        const mid = innerHeight * .5;
        const first = secs[0].getBoundingClientRect(), last = secs[4].getBoundingClientRect();
        const idle = first.top > mid || last.bottom < 0 && false;
        tile.classList.toggle('idle', first.top > mid);
        if (first.top > mid) { dots.forEach(d => d.classList.remove('wm-on', 'wm-off', 'wm-now')); return; }
        secs.forEach((sec, c) => {
          const r = sec.getBoundingClientRect();
          const p = Math.max(0, Math.min(1, (mid - r.top) / Math.max(1, r.height)));
          const filled = Math.round(p * 7);
          const current = r.top <= mid && r.bottom > mid;
          for (let row = 0; row < 7; row++) {
            const d = dots[row * 5 + c], on = (6 - row) < filled;
            d.classList.toggle('wm-on', on); d.classList.toggle('wm-off', !on);
            d.classList.toggle('wm-now', current && on && (6 - row) === filled - 1);
          }
        });
      };
      let raf;
      addEventListener('scroll', () => { if (!raf) raf = requestAnimationFrame(() => { raf = null; paint(); }); }, { passive: true });
      addEventListener('resize', paint);
      paint();
    })();

    const THEMES = {
      hero:        { color: '#5BB8FF', filter: 'saturate(.55) brightness(.9)' },
      engineering: { color: '#5BB8FF', filter: 'saturate(.55) brightness(.9)' },
      contracting: { color: '#A78BFA', filter: 'hue-rotate(52deg) saturate(.48) brightness(.86)' },
      thinking:    { color: '#C4956A', filter: 'hue-rotate(174deg) saturate(.38) brightness(.82)' },
      artisting:   { color: '#6EE7B7', filter: 'hue-rotate(-60deg) saturate(.38) brightness(.9)' },
      marketing:   { color: '#FBBF24', filter: 'hue-rotate(188deg) saturate(.5) brightness(.88)' },
    };
    // only two butterflies per hat section; which two varies so each section feels different
    const DUOS = { contracting: [1, 4], thinking: [2, 3], artisting: [4, 1], engineering: [3, 2], marketing: [1, 2] };

    const art = document.querySelector('.bf-art');
    const work = document.getElementById('work');
    const sections = [...document.querySelectorAll('.hat-section')];
    const links = [...document.querySelectorAll('.hero-nav-link[data-hat]')];
    const flights = [...document.querySelectorAll('.flight')];
    if (!art || !flights.length) return;

    const flock = document.createElement('div');
    flock.className = 'flock-layer';
    flock.setAttribute('aria-hidden', 'true');
    flights.forEach(f => flock.appendChild(f));
    document.body.appendChild(flock);

    let mode = 'hero';            // 'hero' | 'work' | 'away'
    let active = null;            // active .hat-section
    let duo = [];
    let buttonNavigation = false;
    let trackAfter = 0;           // hero: follow the art without easing once the return flight is done
    let followTimer, settleTimer, frame, driftTurn = 0;

    const setXY = (f, x, y) => { f.style.setProperty('--x', x + 'px'); f.style.setProperty('--y', y + 'px'); };
    const sizeOf = f => parseFloat(getComputedStyle(f).width) || 70;
    const shuffle = a => a.map(v => [Math.random(), v]).sort((p, q) => p[0] - q[0]).map(p => p[1]);

    function applyTheme(key) {
      const t = THEMES[key] || THEMES.hero;
      flock.style.setProperty('--butterfly-color', t.color);
      flock.style.setProperty('--sprite-filter', t.filter);
      links.forEach(l => l.classList.toggle('is-active', l.dataset.hat === key));
      links.forEach(l => l.setAttribute('aria-pressed', String(l.dataset.hat === key)));
    }

    function placeHome() {
      const r = art.getBoundingClientRect();
      flights.forEach(f => {
        const cs = getComputedStyle(f);
        setXY(f, r.left + r.width * parseFloat(cs.getPropertyValue('--hx')),
                 r.top + r.height * parseFloat(cs.getPropertyValue('--hy')));
      });
    }

    // a hat section can hold several grids (engineering has two): use the one nearest mid-screen
    function gridIn(section) {
      const grids = [...section.querySelectorAll('.projects-grid')];
      if (!grids.length) return null;
      const mid = innerHeight / 2;
      return grids.reduce((a, g) => {
        const r = g.getBoundingClientRect(), d = Math.abs(r.top + r.height / 2 - mid);
        return !a || d < a.d ? { g, d } : a;
      }, null).g;
    }

    function visibleCards(section) {
      const g = gridIn(section);
      if (!g) return [];
      const gr = g.getBoundingClientRect();
      return [...g.querySelectorAll('.project-card')].filter(c => {
        const r = c.getBoundingClientRect();
        return r.right > gr.left + 30 && r.left < gr.right - 30 && r.bottom > 140 && r.top < innerHeight - 80;
      });
    }

    // drift behind a card: somewhere around its middle, a little off-centre
    function behind(f, card) {
      const r = card.getBoundingClientRect(), s = sizeOf(f);
      const jx = (Math.random() - .5) * r.width * .45, jy = (Math.random() - .5) * r.height * .35;
      setXY(f, r.left + r.width / 2 - s / 2 + jx, r.top + r.height / 2 - s * .36 + jy);
      f._card = card;
    }

    function stageDuo(section) {
      duo = (DUOS[section.id] || [1, 3]).map(i => flights[i]);
      flights.forEach(f => f.classList.toggle('resting', !duo.includes(f)));
      const cards = shuffle(visibleCards(section));
      duo.forEach((f, i) => { if (cards.length) behind(f, cards[i % cards.length]); });
    }

    // after a scroll the cards have moved: follow them (or pick a new one if ours left the screen)
    function resettle() {
      if (mode !== 'work' || !active) return;
      const cards = visibleCards(active);
      if (!cards.length) return;
      duo.forEach(f => {
        const keep = cards.includes(f._card) ? f._card
          : shuffle(cards.filter(c => !duo.some(o => o !== f && o._card === c)))[0] || cards[0];
        behind(f, keep);
      });
    }

    // every so often one of the pair floats over to a different project
    setInterval(() => {
      if (mode !== 'work' || !active || document.hidden) return;
      const f = duo[driftTurn++ % duo.length];
      if (!f) return;
      const options = visibleCards(active).filter(c => !duo.some(o => o._card === c));
      if (options.length) behind(f, shuffle(options)[0]);
    }, 7000);

    // hovering a project: the nearer of the pair drifts behind it
    document.querySelectorAll('.hat-section .project-card').forEach(card => {
      card.addEventListener('mouseenter', () => {
        if (mode !== 'work' || !duo.length || duo.some(f => f._card === card)) return;
        const c = card.getBoundingClientRect(), cx = c.left + c.width / 2, cy = c.top + c.height / 2;
        const f = duo.reduce((a, b) => {
          const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
          return Math.hypot(ra.left - cx, ra.top - cy) <= Math.hypot(rb.left - cx, rb.top - cy) ? a : b;
        });
        behind(f, card);
      });
    });
    document.querySelectorAll('.projects-grid').forEach(g => g.addEventListener('scroll', () => {
      clearTimeout(settleTimer); settleTimer = setTimeout(resettle, 220);
    }, { passive: true }));

    function settleOn(section, delay = 140) {
      clearTimeout(followTimer);
      followTimer = setTimeout(() => stageDuo(section), delay);
    }

    function setMode(next) {
      if (next === mode) return;
      const prev = mode;
      mode = next;
      flock.classList.toggle('away', next === 'away');
      flock.classList.toggle('in-hero', next === 'hero');
      if (next === 'hero') {
        active = null; duo = [];
        flights.forEach(f => f.classList.remove('resting'));
        applyTheme('hero');
        flock.classList.remove('tracking');
        trackAfter = prev === 'hero' ? 0 : performance.now() + 2700;
      } else {
        flock.classList.remove('tracking');
      }
    }

    function sync() {
      frame = null;
      if (buttonNavigation) return;
      const mid = innerHeight * .5;

      if (scrollY < innerHeight * .35) {
        setMode('hero');
        if (performance.now() > trackAfter) flock.classList.add('tracking');
        placeHome();
        return;
      }

      const w = work.getBoundingClientRect();
      if (w.bottom < mid * .9) { setMode('away'); return; }

      setMode('work');
      const nearest = sections.reduce((best, s) => {
        const r = s.getBoundingClientRect();
        const d = Math.abs(r.top + r.height / 2 - mid);
        return !best || d < best.d ? { s, d } : best;
      }, null).s;

      if (nearest !== active) {
        active = nearest;
        applyTheme(nearest.id);
        settleOn(nearest, 160);
      } else {
        clearTimeout(settleTimer); settleTimer = setTimeout(resettle, 220);
      }
    }

    // hat links in the hero: theme first, then fly with the scroll
    links.forEach(link => {
      link.setAttribute('role', 'button');
      link.setAttribute('tabindex', '0');
      link.setAttribute('aria-pressed', 'false');
      link.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); link.click(); } });
      link.addEventListener('click', () => {
        const target = document.getElementById(link.dataset.hat);
        if (!target) return;
        buttonNavigation = true;
        mode = 'work';
        flock.classList.remove('tracking', 'away');
        active = target;
        applyTheme(target.id);
        settleOn(target, 900);
        setTimeout(() => { buttonNavigation = false; }, 920);
      });
    });

    addEventListener('scroll', () => { if (!frame) frame = requestAnimationFrame(sync); }, { passive: true });
    addEventListener('scrollend', () => { buttonNavigation = false; resettle(); });
    addEventListener('resize', () => {
      flock.classList.toggle('compact', innerWidth < 760);
      if (mode === 'hero') placeHome(); else resettle();
    });

    // hide the flock while a project modal is open
    const backdrop = document.getElementById('modal-backdrop');
    if (backdrop) new MutationObserver(() => {
      document.body.classList.toggle('modal-open', backdrop.classList.contains('open'));
    }).observe(backdrop, { attributes: true, attributeFilter: ['class'] });

    flock.classList.toggle('compact', innerWidth < 760);
    applyTheme('hero');
    flock.classList.add('tracking', 'in-hero');
    const start = () => { placeHome(); requestAnimationFrame(sync); if (window.bfOrbHide) bfOrbHide(); };
    if (art.complete) start(); else art.addEventListener('load', start);
  })();
"""


EARLY_BG = """
  <script>try { var bg = localStorage.getItem('bf-bg'); if (bg === 'paper' || bg === 'kraft') document.documentElement.classList.add(bg); } catch (e) {}</script>"""

STORY_SVG = """<svg class="bf-story-art" viewBox="0 0 320 300" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <!-- construction lines -->
      <circle cx="112" cy="168" r="78" stroke-width=".8" stroke-dasharray="3 6" opacity=".55"/>
      <path d="M112 74v188M18 168h188" stroke-width=".8" stroke-dasharray="2 7" opacity=".45"/>
      <path d="M34 262h156M34 255v14M190 255v14M34 262l10-4M34 262l10 4M190 262l-10-4M190 262l-10 4" stroke-width=".9" opacity=".6"/>
      <!-- a hydrangea floret: four petals around a centre -->
      <path d="M112 166c-10-22-6-52 0-66 6 14 10 44 0 66Z" stroke-width="1.5"/>
      <path d="M112 170c10 22 6 52 0 66-6-14-10-44 0-66Z" stroke-width="1.5"/>
      <path d="M110 168c-22 10-52 6-66 0 14-6 44-10 66 0Z" stroke-width="1.5"/>
      <path d="M114 168c22-10 52-6 66 0-14 6-44 10-66 0Z" stroke-width="1.5"/>
      <path d="M112 128v30M112 178v30M72 168h30M122 168h30" stroke-width=".7" opacity=".6"/>
      <circle cx="112" cy="168" r="5" stroke-width="1.4"/>
      <!-- a butterfly leaving it -->
      <g transform="translate(246 70) rotate(-14)">
        <path d="M0 0C-8-26-40-40-52-28-60-16-40 4 0 4Z" stroke-width="1.4"/>
        <path d="M0 0C8-26 40-40 52-28 60-16 40 4 0 4Z" stroke-width="1.4"/>
        <path d="M0 4C-22 6-36 20-28 32-20 40-6 26 0 8Z" stroke-width="1.4"/>
        <path d="M0 4C22 6 36 20 28 32 20 40 6 26 0 8Z" stroke-width="1.4"/>
        <path d="M0-10V22M0-10l-8-14M0-10l8-14" stroke-width="1.6"/>
      </g>
      <path d="M178 140c18-14 30-30 46-46" stroke-width=".9" stroke-dasharray="2 6" opacity=".6"/>
    </svg>"""

STORY = f"""<!-- ══════ WHY THE HYDRANGEA (butterfly preview) ══════ -->
<section id="why-hydrangea" style="border-top:1px solid var(--border)">
  <div class="section">
    <p class="section-label">About the flower</p>
    <h2 class="section-title">Why a hydrangea, and why butterflies</h2>
    <div class="bf-story-grid">
      {STORY_SVG}
      <div class="bf-story-text">
        <p>I like hydrangeas. One flower head is really hundreds of small florets, each repeating the same simple four-petal pattern, packed into a dome that reads as a single shape from across a garden. It's very good engineering that also happens to be beautiful.</p>
        <p>Butterflies are the same idea in motion: a light frame, wings that fold flat, and colour that often comes from the structure of the scales rather than from pigment. The function and the design aren't a trade-off; they're the same decision. That's the standard I try to hold my own work to, which is why the flower on this page turns into butterflies.</p>
        <p class="bf-story-note">The pencil marks behind the page are nods to my old engineering sketches: gears, boxes, dimension lines and the odd butterfly.</p>
      </div>
    </div>
  </div>
</section>"""

# ── blog preview: same three backgrounds on the editorial blog ───────────
BLOG_OUT = ROOT / "blog-butterfly.html"
BLOG_CSS = r"""
    /* ══ background options (local preview, shared with index-butterfly.html) ══ */
    html.paper body {
      background-color: #1e1d1a;
      background-image: radial-gradient(ellipse 120% 90% at 50% 30%, transparent 50%, rgba(0,0,0,.5) 100%), url("ASSETS/paper-dark.webp");
      background-repeat: no-repeat, repeat; background-size: 100% 100%, 512px 512px; background-attachment: fixed, fixed;
    }
    html.kraft { --paper-dim: #ddd4c4; --line: rgba(255,240,215,.2); }
    html.kraft body {
      background-color: #56402a;
      background-image: radial-gradient(ellipse 120% 90% at 50% 30%, transparent 45%, rgba(20,12,4,.55) 100%), url("ASSETS/kraft.webp");
      background-repeat: no-repeat, repeat; background-size: 100% 100%, 1024px 1024px; background-attachment: fixed, fixed;
    }
    /* sketches only in the margins, so the reading column stays clean */
    html.kraft body::after {
      content: ""; position: fixed; inset: 0; z-index: -1; pointer-events: none;
      background: url("ASSETS/sketches.webp") 0 0 / 1600px 1600px repeat;
      -webkit-mask-image: linear-gradient(90deg, #000 0, #000 13%, transparent 28%, transparent 72%, #000 87%, #000 100%);
              mask-image: linear-gradient(90deg, #000 0, #000 13%, transparent 28%, transparent 72%, #000 87%, #000 100%);
    }
    html.kraft .voice-note { background: rgba(14,10,6,.72); }
    html.kraft .field input, html.kraft .field textarea { background: rgba(14,10,6,.35); }
    html.kraft h1, html.kraft h2 { text-shadow: 0 1px 2px rgba(30,15,0,.4); }

    .bf-controls {
      position: fixed; left: 16px; bottom: 16px; z-index: 300;
      display: flex; align-items: center; gap: 4px;
      padding: 4px 4px 4px 12px; border-radius: 100px;
      border: 1px solid rgba(255,255,255,.14); background: rgba(3,3,3,.75);
      backdrop-filter: blur(8px); font-family: var(--sans);
    }
    .bf-controls .bf-tag { font-size: .6rem; letter-spacing: .14em; text-transform: uppercase; color: rgba(255,255,255,.4); margin-right: 6px; }
    .bf-controls button { font: 500 .68rem/1 var(--sans); letter-spacing: .06em; padding: 6px 11px; border-radius: 100px; border: 0; cursor: pointer; background: transparent; color: rgba(255,255,255,.5); }
    .bf-controls button[aria-pressed="true"] { background: rgba(255,255,255,.12); color: #fff; }
""".replace("ASSETS", ASSETS)

BLOG_JS = r"""
  <script>
  (() => {
    const root = document.documentElement;
    const store = { get: () => { try { return localStorage.getItem('bf-bg'); } catch { return null; } },
                    set: v => { try { localStorage.setItem('bf-bg', v); } catch {} } };
    const c = document.createElement('div');
    c.className = 'bf-controls';
    c.innerHTML = '<span class="bf-tag">preview · local</span><button type="button" data-bg="ink">Ink</button>' +
      '<button type="button" data-bg="paper">Paper</button><button type="button" data-bg="kraft">Kraft</button>';
    document.body.appendChild(c);
    const setBg = bg => {
      root.classList.toggle('paper', bg === 'paper'); root.classList.toggle('kraft', bg === 'kraft');
      c.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.bg === bg)));
      store.set(bg);
    };
    c.addEventListener('click', e => { const b = e.target.closest('button'); if (b) setBg(b.dataset.bg); });
    setBg(['paper', 'kraft'].includes(store.get()) ? store.get() : 'ink');
  })();
  </script>
"""


def build_blog():
    src = BLOG_SRC
    html = src.read_text(encoding="utf-8")
    i = html.index("</style>")
    html = html[:i] + BLOG_CSS + "  " + html[i:]
    html = html.replace('<a class="home-link" href="/">', '<a class="home-link" href="index-butterfly.html">', 1)
    k = html.rindex("</body>")
    html = html[:k] + BLOG_JS + html[k:]
    for ext in (".webp",):
        html = html.replace(ext + '")', ext + '?v=' + BUILD_STAMP + '")')
    html = html.replace("preview · local", "preview · build " + BUILD_STAMP, 1)
    html = html.replace("<head>", '<head>\n  <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">' + EARLY_BG, 1)
    html = add_orb(html, 'Loading the blog')
    k = html.rindex("</body>")
    html = html[:k] + """
  <script>
  (() => {  // hide the orb once the skeleton has been replaced by real content
    const main = document.getElementById('top');
    const done = () => !main || !main.querySelector('.skeleton');
    if (done()) return window.bfOrbHide && bfOrbHide();
    new MutationObserver((m, o) => { if (done()) { o.disconnect(); window.bfOrbHide && bfOrbHide(); } })
      .observe(main, { childList: true, subtree: true });
  })();
  </script>
""" + html[k:]
    BLOG_OUT.write_text(html, encoding="utf-8")
    print(f"wrote {BLOG_OUT.relative_to(ROOT)} ({len(html):,} bytes)")


# ── case studies on the homepage: cards that open work.html#slug ─────────
# hat -> (mode, slugs). "after-first" = after the first card in that hat's grid,
# "start" = at the front of the grid. The Full Week replaces the Healthcoach card.
CASE_PLACEMENT = {
    "contracting": ("after-first", ["thorne-hale", "lending-assistant", "charity-toolkit"]),
    "thinking":    ("start",       ["grandma-tv", "automation-collection"]),
    "artisting":   ("start",       ["pacetune"]),
}
CASE_REPLACE = {"Healthcoach + Halfmara": "the-full-week", "Cornerstore": "cornerstore"}
CASE_THUMB = {  # which image sits behind each card
    "thorne-hale": "th-quotes", "lending-assistant": "la-dashboard", "charity-toolkit": "km-timetable",
    "grandma-tv": "gt-mode", "automation-collection": "ff-results", "the-full-week": "fw-phone",
    "pacetune": "pt-messages",
}

def _div_end(html, start):
    depth, j = 0, start
    while True:
        o = html.find("<div", j); c = html.find("</div>", j)
        if o != -1 and o < c:
            depth += 1; j = o + 4
        else:
            depth -= 1; j = c + 6
            if depth == 0:
                return j

def case_card(item):
    import html as h
    title = item["title"].replace("*", "")
    media = item.get("media", {})
    img = media.get(CASE_THUMB.get(item["slug"], ""), {}).get("url", "")
    if not img:
        img = next((m["url"] for m in media.values() if m.get("kind") == "image"), "")
    tags = "".join(f'<span class="tag">{h.escape(t)}</span>' for t in item.get("tags", [])[:3])
    year = item.get("date", "")[:4]
    style = ""  # no screenshot behind the card (removed at Toni's request)
    return (f'<a class="project-card case-card" href="work.html#{item["slug"]}"{style}>\n'
            f'          <p class="card-period">{year} · <span class="case-badge">Case study</span></p>\n'
            f'          <h3 class="card-title">{h.escape(title)}</h3>\n'
            f'          <p class="card-desc">{h.escape(item.get("excerpt", ""))}</p>\n'
            f'          <p class="card-metric">{h.escape(item.get("stage", ""))}</p>\n'
            f'          <div class="card-tags">{tags}</div>\n'
            f'          <span class="case-cta">Read the case study →</span>\n'
            f'        </a>')

def add_case_studies(html):
    import json
    idx = ROOT / "content" / "work" / "index.json"
    if not idx.exists():
        return html
    items = {it["slug"]: it for it in json.loads(idx.read_text(encoding="utf-8"))["items"]}
    for old_title, slug in CASE_REPLACE.items():
        t = html.find(f'<h3 class="card-title">{old_title}</h3>')
        if t != -1 and slug in items:
            s = html.rfind('<div class="project-card"', 0, t)
            html = html[:s] + case_card(items[slug]) + html[_div_end(html, s):]
    for hat, (mode, slugs) in CASE_PLACEMENT.items():
        sec = html.find(f'class="hat-section" id="{hat}"')
        g = html.find('<div class="projects-grid">', sec)
        if sec == -1 or g == -1:
            continue
        cards = "\n        ".join(case_card(items[s]) for s in slugs if s in items)
        if mode == "start":
            at = g + len('<div class="projects-grid">')
        else:
            first = html.find('<div class="project-card"', g)
            at = _div_end(html, first)
        html = html[:at] + "\n        " + cards + html[at:]
    return html

ORB_JS = (Path(__file__).parent / "orb.js").read_text(encoding="utf-8")

def add_orb(html, label):
    """Loader/transition veil, injected straight after <body> so it covers the page from the first paint."""
    i = html.index("<body")
    j = html.index(">", i) + 1
    return html[:j] + f"\n  <script>window.__BF_ORB_LABEL = {label!r};</script>\n" + ORB_JS + html[j:]

# ── About section rewrite (Toni, 2026-10-05: less Cranfield, more "I solve problems by building") ──
ABOUT_TITLE = "I solve problems by building things"
ABOUT_BIO = """<div class="about-bio">
          <p>I'm <strong>Toni Esan</strong>, based in London. I like problem solving, and the way I solve problems is by <strong>building the thing</strong>. I've done that in mechanical engineering, in software, and in product design, where I still sketch and model in 3D.</p>
          <p>Now I use <strong>AI to bring all of that together</strong>. At <strong>Leveret AI</strong>, a dental AI startup, I built the annotation site dentists actually used to label X-rays, and tested our voice notes with dentists through background noise and different accents. Through <strong>Avalon Insights</strong> I build AI workflows and run training for construction firms, lenders, charities and trade bodies. And I build a lot of my own tools, from a 3D digital twin of a corner shop to a training plan that lives on my lock screen.</p>
          <p>Before that I worked in industry: logistics deployment at GXO, IT at LiviaSoft, and autonomous vehicles since 2019. I've also grown social accounts past half a million followers.</p>
          <p>I like learning new things, and I like teaching them just as much. That's a big part of why so much of my work is helping people use AI well, not just building it for them.</p>
          <p>What I'm into: cars and anything automotive, from autonomous vehicles to logging every fill-up of my old Polo. I'm nearly always in the middle of a side project, building with Codex, Claude and Gemini, and this site is slowly being built out of a second brain of my bookmarks and voice notes. I'm training for a half marathon (PaceTune came out of wanting to know which song was playing on each split), I watch a lot of films, I follow football, and I sign BSL and speak some Spanish and Yoruba.</p>
          <div class="how-i-work">
            <div><span>01</span><b>Make it easy for the person using it</b><p>Dentists weren't going to sign up to Roboflow, so I built them a mobile annotation site instead.</p></div>
            <div><span>02</span><b>Keep a person in the loop where it matters</b><p>Drafts, emails and credit papers wait for the owner's approval before anything goes out.</p></div>
            <div><span>03</span><b>Test it where it will be used</b><p>On the real TV, in the real shop, with real accents and background noise.</p></div>
          </div>
        </div>"""

# the published paper (Toni, 2026-10-05). Code: https://github.com/Toni9a/VisualGazebo
GDP_LINK = "https://www.researchgate.net/publication/400702068_Generative_Street-View_using_Satellite_Images_with_Hallucination_Reduction_via_Semantic_Constraining"

FLOWER_START = '<div class="flower-card">'


def main():
    html = SRC.read_text(encoding="utf-8")

    # 1. CSS: append to the first <style> block
    i = html.index("</style>")
    html = html[:i] + CSS + "  " + html[i:]

    # 2. Hero: swap the rotated flower card for the transition artwork + flights
    s = html.index(FLOWER_START)
    depth, j = 0, s
    while True:  # find the matching closing </div>
        o = html.find("<div", j)
        c = html.find("</div>", j)
        if o != -1 and o < c:
            depth += 1; j = o + 4
        else:
            depth -= 1; j = c + 6
            if depth == 0:
                break
    html = html[:s] + HERO_ART + html[j:]

    # 2b. hat portraits: contracting was a JPG with black baked in; use the cut-out
    html = html.replace('src="assetsforsite/Contracting_hat_purple.jpg"', f'src="{ASSETS}/Contracting_hat_purple_cutout.webp"')

    # 2c. nav tiles: hover labels + keyboard access; heart goes to the blog preview
    # nav order: work · blog (heart, middle) · about (i, beside Resumé). Dot-matrix tiles stay;
    # each gets a small word underneath, and the work tile becomes a live map of the hats (JS below).
    mid  = """<div class="dot-tile" data-pattern="i" onclick="navTo('about')"></div>"""
    right = """<div class="dot-tile" data-pattern="heart" onclick="window.location.href='blog.html'"></div>"""
    if mid in html and right in html:
        html = html.replace(mid, "@@MID@@").replace(right, mid).replace("@@MID@@", right)
    for pat, label in (("E", "work"), ("i", "about"), ("heart", "blog")):
        html = html.replace(f'class="dot-tile" data-pattern="{pat}"',
                            f'class="dot-tile" data-pattern="{pat}" data-label="{label}" aria-label="{label}" role="link" tabindex="0"')
    html = html.replace("window.location.href='blog.html'", "bfGo('blog-butterfly.html', 'Opening the blog')")
    html = add_orb(html, 'Toni Esan')


    # 2c2. case studies from content/work/index.json, as cards in the right hats
    html = add_case_studies(html)

    # 2c3. the "Blog / Coming soon" box in About goes: the blog exists now
    b = html.find('<p class="side-label" style="margin-bottom:0.75rem">Blog</p>')
    if b != -1:
        start = html.rfind('<div style="margin-top:3rem;">', 0, b)
        html = html[:start] + html[_div_end(html, start):]

    # 2c4. interests become buttons; the panel reads published posts with the blog's public anon key
    import re as _re
    blog_src = BLOG_SRC.read_text(encoding="utf-8")
    m = _re.search(r"SUPABASE_ANON_KEY = '([^']+)'", blog_src)
    blog_key = m.group(1) if m else ""

    # 2c5. About: new title and bio, education demoted to one quiet line at the bottom of the sidebar
    html = html.replace('<h2 class="section-title">Mechanical engineer turned AI builder</h2>',
                        f'<h2 class="section-title">{ABOUT_TITLE}</h2>', 1)
    a = html.find('<div class="about-bio">')
    if a != -1:
        html = html[:a] + ABOUT_BIO + html[_div_end(html, a):]
    e = html.find('<p class="side-label">Education</p>')
    if e != -1:
        es = html.rfind('<div>', 0, e); ee = _div_end(html, es)
        edu = html[es:ee]
        html = html[:es] + html[ee:]
        side = html.find('<div class="about-side">')
        side_end = _div_end(html, side) - len('</div>')
        html = html[:side_end] + '  <div class="edu-quiet">' + edu.replace('<div>', '<div>', 1) + '</div>\n      ' + html[side_end:]
    html = html.replace('<span class="hero-bio-muted">MSc Applied AI, Cranfield &middot; Technical Officer, Leveret AI.</span>',
                        '<span class="hero-bio-muted">Mechanical engineering, software and product design, joined up with AI.</span>', 1)

    # 2c6. hero bio: builder + learner/educator
    html = html.replace('Building things that bridge disciplines and solve real problems with taste.',
                        'I build things that bridge disciplines, and I love learning new things and teaching them.', 1)
    html = html.replace('joined up with AI.</span>', 'joined up with AI. Builder and educator.</span>', 1)
    # 2c7. the Cranfield GDP card is really the Neural Gazetteer (Toni was project lead; published research)
    g = html.find('<h3 class="card-title">Cranfield GDP: Generative Prompt Pipeline</h3>')
    if g != -1:
        cs = html.rfind('<div class="project-card"', 0, g); ce = _div_end(html, cs)
        html = html[:cs] + f"""<div class="project-card"
       data-note="I led our Cranfield Group Design Project: a neural gazetteer that describes, and pictures, places that maps barely label."
       data-link="{GDP_LINK}">
          <p class="card-period">2024–2025 · Project lead</p>
          <h3 class="card-title">Neural Gazetteer (Cranfield GDP)</h3>
          <p class="card-desc">Give it a latitude and longitude and it builds a rich description and a street-level picture of the place, even where maps have few labels. Reverse geocoding and Places data, GPT-4o narratives, then Stable Diffusion with ControlNet to synthesise street views from satellite imagery. Published as <em>Generative Street-View using Satellite Images with Hallucination Reduction via Semantic Constraining</em>.</p>
          <p class="card-metric">Project lead · published paper</p>
          <div class="card-tags"><span class="tag">Geospatial</span><span class="tag">Diffusion</span><span class="tag">LLMs</span></div>
        </div>""" + html[ce:]

    # 2d. "why the hydrangea" section, just above the footer
    f = html.index("<footer")
    # html = html[:f] + STORY + "\n" + html[f:]   # removed 2026-10-05 (Toni: "for now")

    # 3. JS: before the last </script>
    k = html.rindex("</script>")
    html = html[:k] + JS + html[k:]

    # cache-bust: browsers (Safari especially) keep old copies from python's http.server
    for ext in (".webp",):
        html = html.replace(ext + '"', ext + '?v=' + BUILD_STAMP + '"').replace(ext + '")', ext + '?v=' + BUILD_STAMP + '")')
    html = html.replace("preview · local", "preview · build " + BUILD_STAMP, 1)
    html = html.replace("<head>", '<head>\n  <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">' + EARLY_BG, 1)
    html = html.replace("<title>Toni Esan</title>", "<title>Toni Esan · butterfly preview</title>", 1)
    html = html.replace("/*__BLOG_KEY__*/''", "'" + blog_key + "'")  # public anon key, same as blog.html
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(html):,} bytes)")
    build_blog()


if __name__ == "__main__":
    main()
