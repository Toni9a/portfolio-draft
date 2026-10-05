#!/usr/bin/env python3
"""Turn the local previews into the live pages.

    python3 content/butterfly/build_butterfly_page.py   # rebuild the previews
    python3 content/butterfly/publish.py               # write index.html + blog.html from them

Edits to the homepage/blog content go into content/butterfly/src/*.src.html (the originals),
never into index.html / blog.html, which are generated from here on.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def common(html):
    html = re.sub(r'(?<![/\w])content/butterfly/assets/', '/content/butterfly/assets/', html)
    html = re.sub(r'<span class="bf-tag">preview · [^<]*</span>', '', html)
    html = html.replace('\n  <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">', '', 1)
    return html


def index():
    html = (ROOT / "index-butterfly.html").read_text(encoding="utf-8")
    html = common(html)
    html = html.replace("<title>Toni Esan · butterfly preview</title>", "<title>Toni Esan</title>", 1)
    html = html.replace("bfGo('blog-butterfly.html', 'Opening the blog')", "bfGo('/blog', 'Opening the blog')")
    html = html.replace('href="blog-butterfly.html#${encodeURIComponent(p.slug)}"', 'href="/blog/${encodeURIComponent(p.slug)}"')
    html = re.sub(r'href="work\.html#([\w-]+)"', r'href="/work/\1"', html)
    assert "blog-butterfly" not in html and "work.html#" not in html, "local link left in index"
    (ROOT / "index.html").write_text(html, encoding="utf-8")
    print("wrote index.html", len(html))


def blog():
    html = (ROOT / "blog-butterfly.html").read_text(encoding="utf-8")
    html = common(html)
    html = html.replace('<a class="home-link" href="index-butterfly.html">', '<a class="home-link" href="/">', 1)
    assert "href=\"index-butterfly" not in html, "local link left in blog"
    (ROOT / "blog.html").write_text(html, encoding="utf-8")
    print("wrote blog.html", len(html))


if __name__ == "__main__":
    index(); blog()
