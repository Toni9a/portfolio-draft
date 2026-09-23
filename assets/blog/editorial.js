/* editorial.js
 * One renderer for blog posts, shared by blog.html (the public page) and the
 * admin editor's preview (which loads blog.html?preview=1 in an iframe and
 * posts the draft into it). Whatever the preview shows is what gets published.
 *
 * ── Editorial markdown ─────────────────────────────────────────────────────
 * body_md stays plain markdown so sync_posts.py / tag_posts.py / the Telegram
 * query bot can keep reading it. A handful of conventions add the layout:
 *
 *   > Opening note text            first blockquote before any heading
 *                                  = the paper "quick take" note
 *   ## [THE SOURCE] Heading        a numbered section; the [LABEL] is optional
 *   >> A line Toni said            the pull quote (one per post)
 *   [[cutout:<post_media id>]]     a collage cutout beside the next passage
 *   [[image:<post_media id>]]      an ordinary inline photo
 *   [[voice:<inbox id>]]           the original recording: always shown, collapsed,
 *                                  just under the opening note (1x/1.5x/2x)
 *
 * Title: *words* in the title are set in italic blue, e.g.
 *   Why GEO Will Rely on *Human Influencers*
 *
 * Posts written before these conventions (no ## headings) still render: the
 * whole body becomes one unnumbered section.
 * ─────────────────────────────────────────────────────────────────────────── */
(function (global) {
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const md = (s) => (global.marked ? global.marked.parse(s || '') : `<p>${esc(s)}</p>`);

  function titleHtml(title) {
    return esc(title || 'Untitled').replace(/\*([^*]+)\*/g, '<em>$1</em>');
  }
  function plainTitle(title) { return String(title || '').replace(/\*/g, ''); }

  function fmtLong(iso) {
    if (!iso) return '';
    const d = new Date(String(iso).length === 10 ? iso + 'T12:00:00' : iso);
    return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
  }
  function fmtSlash(iso) {
    if (!iso) return '';
    const d = new Date(String(iso).length === 10 ? iso + 'T12:00:00' : iso);
    const p = (n) => String(n).padStart(2, '0');
    return `${p(d.getDate())} / ${p(d.getMonth() + 1)} / ${d.getFullYear()}`;
  }
  const pad2 = (n) => String(n).padStart(2, '0');

  function domainOf(url) {
    try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return url; }
  }

  function stripTokens(s) { return String(s || '').replace(/\[\[[a-z]+:[^\]]+\]\]/g, ''); }
  function wordCount(s) { return stripTokens(s).replace(/[#>*_\[\]()`]/g, ' ').split(/\s+/).filter(Boolean).length; }

  /* Parse body_md into { lead, sections: [{label, heading, blocks: [...]}] }.
     A block is {type:'md', text} | {type:'pull', text} | {type:'cutout'|'image'|'voice', id}. */
  function parse(bodyMd) {
    const lines = String(bodyMd || '').replace(/\r\n/g, '\n').split('\n');
    const out = { lead: '', sections: [] };
    let cur = null;
    let buf = [];
    let seenHeading = false;
    let leadDone = false;

    const ensure = () => { if (!cur) { cur = { label: '', heading: '', blocks: [] }; out.sections.push(cur); } return cur; };
    const flush = () => {
      const text = buf.join('\n').trim();
      buf = [];
      if (text) ensure().blocks.push({ type: 'md', text });
    };

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const trimmed = line.trim();

      // Opening note: the first blockquote before any heading or other text.
      if (!leadDone && !seenHeading && /^>(?!>)/.test(trimmed) && !buf.join('').trim() && !out.sections.length) {
        const q = [];
        while (i < lines.length && /^>(?!>)/.test(lines[i].trim())) { q.push(lines[i].trim().replace(/^>\s?/, '')); i++; }
        i--;
        out.lead = q.join(' ').trim();
        leadDone = true;
        continue;
      }
      if (trimmed) leadDone = true;

      const h = trimmed.match(/^##\s+(?:\[([^\]]+)\]\s*)?(.*)$/);
      if (h && !/^###/.test(trimmed)) {
        flush();
        seenHeading = true;
        cur = { label: (h[1] || '').trim(), heading: (h[2] || '').trim(), blocks: [] };
        out.sections.push(cur);
        continue;
      }
      const pq = trimmed.match(/^>>\s?(.*)$/);
      if (pq) {
        flush();
        const q = [pq[1]];
        while (i + 1 < lines.length && /^>>/.test(lines[i + 1].trim())) { i++; q.push(lines[i].trim().replace(/^>>\s?/, '')); }
        ensure().blocks.push({ type: 'pull', text: q.join(' ').trim() });
        continue;
      }
      const tok = trimmed.match(/^\[\[(cutout|image|voice):([A-Za-z0-9-]+)\]\]$/);
      if (tok) {
        flush();
        ensure().blocks.push({ type: tok[1], id: tok[2] });
        continue;
      }
      buf.push(line);
    }
    flush();
    return out;
  }

  /* ctx: { media: {id: {url, alt, placement}}, voice: {id: url}, fieldNo, preview } */
  function articleHtml(post, ctx = {}) {
    const media = ctx.media || {};
    const voice = ctx.voice || {};
    const doc = parse(post.body_md);
    const date = post.captured_on || post.published_at || post.updated_at || post.created_at;
    const tags = (post.topic_tags || []).filter(Boolean);
    const words = wordCount(post.body_md);
    const minutes = Math.max(1, Math.round(words / 200));
    const fromVoice = !!doc.lead || /\[\[voice:/.test(post.body_md || '') || ctx.fromVoice;
    let cutoutSide = 0;
    let firstPara = true;
    let sectionNo = 0;

    const blockHtml = (b) => {
      if (b.type === 'md') {
        let html = md(b.text);
        if (firstPara) {
          const swapped = html.replace(/^<p>/, '<p class="drop">');
          if (swapped !== html) firstPara = false;
          html = swapped;
        }
        return html;
      }
      if (b.type === 'pull') return `<blockquote class="pull-quote">${esc(b.text)}</blockquote>`;
      if (b.type === 'voice') return voiceHtml(b.id, voice[b.id]);
      const m = media[b.id];
      if (!m) return ctx.preview ? `<div class="media-missing">${esc(b.type)} ${esc(b.id.slice(0, 8))} not found</div>` : '';
      if (b.type === 'image') {
        return `<figure class="inline-figure"><img src="${esc(m.url)}" alt="${esc(m.alt || '')}" loading="lazy">${m.caption ? `<figcaption>${esc(m.caption)}</figcaption>` : ''}</figure>`;
      }
      // cutout
      let side = m.placement;
      if (!side || side === 'lead') side = side === 'lead' ? 'lead' : (cutoutSide++ % 2 ? 'left' : 'right');
      return `<div class="cutout-anchor cutout-${side}"><img class="cutout" src="${esc(m.url)}" alt="${esc(m.alt || '')}" decoding="async"></div>`;
    };

    const voiceBlocks = [];
    doc.sections.forEach((s) => { s.blocks = s.blocks.filter((b) => (b.type === 'voice' ? (voiceBlocks.push(b), false) : true)); });
    const voiceTop = voiceBlocks.map(blockHtml).join('\n');

    const sectionsHtml = doc.sections.filter((s) => s.heading || s.blocks.length).map((s) => {
      const numbered = !!s.heading;
      if (numbered) sectionNo++;
      const label = numbered ? `${pad2(sectionNo)}${s.label ? ' / ' + esc(s.label.toUpperCase()) : ''}` : '';
      return `<section class="section">
        ${numbered ? `<span class="section-number">${label}</span><h2>${esc(s.heading)}</h2>` : ''}
        ${s.blocks.map(blockHtml).join('\n')}
      </section>`;
    }).join('\n');

    const sources = (post.source_urls || []).filter(Boolean);
    const labels = post.source_labels || {};
    const sourcesHtml = sources.length ? `
      <section class="sources" aria-labelledby="sources-title">
        <h2 id="sources-title">Sources &amp; sparks</h2>
        ${sources.map((u, i) => `
          <a class="source-card" href="${esc(u)}" target="_blank" rel="noreferrer">
            <span class="source-index">${pad2(i + 1)}</span>
            <span class="source-title">${esc(labels[u] || domainOf(u))}<span class="source-domain">${esc(domainOf(u))}</span></span>
            <span class="source-arrow" aria-hidden="true">↗</span>
          </a>`).join('')}
      </section>` : '';

    return `
      <header class="article-header">
        <div class="issue-line">${esc(fmtLong(date))}${ctx.fieldNo ? ` · Field note ${pad2(ctx.fieldNo)}` : ctx.preview ? ' · Draft' : ''}</div>
        <h1>${titleHtml(post.title)}</h1>
        ${post.excerpt ? `<p class="deck">${esc(post.excerpt)}</p>` : ''}
        ${tags.length ? `<div class="tags" aria-label="Article topics">${tags.map((t) => `<span>${esc(t)}</span>`).join('')}</div>` : ''}
      </header>
      <div class="article-grid">
        <aside class="margin-note">
          <strong>${fromVoice ? 'VOICE NOTE → EDITED' : 'FIELD NOTE'}</strong>
          ${fromVoice ? 'Original thought,<br>cleaner rhythm.<br><br>' : ''}
          Approx. ${minutes} min read.
        </aside>
        <article class="article-body">
          ${doc.lead ? `<p class="lead-note">${esc(doc.lead)}</p>` : ''}
          ${voiceTop}
          ${sectionsHtml}
          ${sourcesHtml}
        </article>
      </div>`;
  }

  /* A voice note is a collapsed strip: readers choose to open and play it.
     Speed buttons are wired up by wireVoiceNotes() on the page. */
  function voiceHtml(id, url) {
    return `<details class="voice-note" data-voice-id="${esc(id)}">
      <summary>
        <span class="vn-icon" aria-hidden="true"></span>
        <span class="vn-label">Listen <b>·</b> the original voice note</span>
        <span class="vn-time"></span>
        <span class="vn-toggle" aria-hidden="true"></span>
      </summary>
      <div class="vn-body">
        <audio controls preload="metadata"${url ? ` src="${esc(url)}"` : ''}></audio>
        <div class="vn-speeds" role="group" aria-label="Playback speed">
          <button type="button" data-rate="1" aria-pressed="true">1×</button>
          <button type="button" data-rate="1.5" aria-pressed="false">1.5×</button>
          <button type="button" data-rate="2" aria-pressed="false">2×</button>
        </div>
      </div>
    </details>`;
  }

  // Speed buttons + duration label. Safe to call repeatedly (delegated once).
  function wireVoiceNotes(doc) {
    doc = doc || document;
    if (doc.__voiceWired) return;
    doc.__voiceWired = true;
    const fmt = (t) => (isFinite(t) && t > 0 ? `${Math.floor(t / 60)}:${String(Math.round(t % 60)).padStart(2, '0')}` : '');
    doc.addEventListener('click', (e) => {
      const btn = e.target.closest('.vn-speeds button');
      if (!btn) return;
      const note = btn.closest('.voice-note');
      const audio = note.querySelector('audio');
      audio.playbackRate = Number(btn.dataset.rate);
      note.querySelectorAll('.vn-speeds button').forEach((b) => b.setAttribute('aria-pressed', String(b === btn)));
    });
    doc.addEventListener('loadedmetadata', (e) => {
      if (e.target.tagName !== 'AUDIO') return;
      const note = e.target.closest('.voice-note');
      if (note) note.querySelector('.vn-time').textContent = fmt(e.target.duration);
    }, true);
    doc.addEventListener('ratechange', (e) => {
      if (e.target.tagName !== 'AUDIO') return;
      const note = e.target.closest('.voice-note');
      if (!note) return;
      note.querySelectorAll('.vn-speeds button').forEach((b) => b.setAttribute('aria-pressed', String(Number(b.dataset.rate) === e.target.playbackRate)));
    }, true);
  }

  function footerMeta(post) {
    const date = post ? (post.captured_on || post.published_at || post.updated_at) : new Date().toISOString();
    const tags = post ? (post.topic_tags || []).slice(0, 3) : [];
    return { date: fmtSlash(date), filed: tags.length ? 'Filed under: ' + tags.join(' / ') : 'Field notes' };
  }

  function voiceIds(bodyMd) {
    return [...new Set([...String(bodyMd || '').matchAll(/\[\[voice:([A-Za-z0-9-]+)\]\]/g)].map((m) => m[1]))];
  }
  function mediaIds(bodyMd) {
    return [...new Set([...String(bodyMd || '').matchAll(/\[\[(?:cutout|image):([A-Za-z0-9-]+)\]\]/g)].map((m) => m[1]))];
  }

  // House rules, shared with the admin editor's checks.
  function findDashes(text) {
    const out = [];
    String(text || '').split('\n').forEach((line, i) => { if (/[—–]/.test(line)) out.push({ line: i + 1, text: line.trim().slice(0, 120) }); });
    return out;
  }

  global.Editorial = {
    parse, articleHtml, footerMeta, titleHtml, plainTitle, fmtLong, fmtSlash,
    voiceIds, mediaIds, wordCount, stripTokens, findDashes, esc, domainOf, voiceHtml, wireVoiceNotes,
  };
})(window);
