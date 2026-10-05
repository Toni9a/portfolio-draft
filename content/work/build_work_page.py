"""Builds work.html (case-study pages) from the blog template (content/butterfly/src/blog.src.html).

Reuses the blog's editorial styles, header, footer and renderer
(assets/blog/editorial.js), and swaps the data layer for local files in
content/work/ (index.json + one markdown file per case study). No Supabase
calls: nothing here reads or writes the database.

Run from the repo root:  python3 content/work/build_work_page.py
Re-run it after editing blog.html so the styles stay in step.
"""
import re
from pathlib import Path

root = Path(__file__).resolve().parents[2]
_frozen = root / "content" / "butterfly" / "src" / "blog.src.html"   # blog.html is generated now
src = (_frozen if _frozen.exists() else root / "blog.html").read_text()
script = (Path(__file__).parent / "work_page.js").read_text()
extra_css = (Path(__file__).parent / "work_page.css").read_text()

def cut(s, start_pat, end_tag):
    """Remove from the first match of start_pat to the matching end_tag (first after it)."""
    i = s.find(start_pat)
    assert i >= 0, start_pat
    j = s.find(end_tag, i)
    assert j >= 0, end_tag
    return s[:i] + s[j + len(end_tag):]

out = src
out = out.replace("<title>Blog | Toni Esan</title>", "<title>Work | Toni Esan</title>")
out = re.sub(r'<meta name="description" content="[^"]*">',
             '<meta name="description" content="Toni Esan: case studies of client work and personal builds.">', out)
out = re.sub(r'\n\s*<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>', "", out)
out = out.replace('<a class="brand" href="/blog" data-nav="index">TONI ESAN / BLOG</a>',
                  '<a class="brand" href="/work" data-nav="index">TONI ESAN / WORK</a>')
out = out.replace('<span class="header-note">Voice notes, shaped into essays</span>',
                  '<span class="header-note">Case studies</span>')
# Reader zone: keep "Also check this out" + socials, drop comments and the mailing list.
out = cut(out, '<section class="thoughts"', "</section>\n\n    <div")
out = out.replace('<section class="reader-zone" aria-label="Keep in touch">\n    ',
                  '<section class="reader-zone" aria-label="Keep in touch">\n    <div')
out = cut(out, '<section class="newsletter"', "</section>")
out = out.replace('<span id="footer-filed">Field notes</span>', '<span id="footer-filed">Case studies</span>')
# Swap the page script (the one that starts with the Supabase constants).
start = out.find("<script>\n    const SUPABASE_URL")
assert start >= 0, "page script not found"
end = out.find("</script>", start) + len("</script>")
out = out[:start] + "<script>\n" + script + "\n  </script>" + out[end:]
out, n = re.subn(r'</style>(\s*<script src="https://cdn.jsdelivr.net/npm/marked)', lambda m: extra_css + "\n  </style>" + m.group(1), out, count=1)
assert n == 1, "could not add work_page.css"

assert "SUPABASE_URL" not in out and "createClient" not in out, "Supabase client left in work.html"
(root / "work.html").write_text(out)
print("wrote", root / "work.html", len(out), "bytes")
