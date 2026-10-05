    /* Case studies. Data: /content/work/index.json + /content/work/<slug>.md.
       Rendered with the blog's editorial renderer so the pages match the blog. */
    const E = window.Editorial;
    const main = document.getElementById('top');
    const params = new URLSearchParams(location.search);
    const root = document.documentElement;
    const updateProgress = () => {
      const scrollable = root.scrollHeight - innerHeight;
      root.style.setProperty('--read', `${scrollable > 0 ? Math.min(100, Math.max(0, scrollY / scrollable * 100)) : 0}%`);
    };
    addEventListener('scroll', updateProgress, { passive: true });
    addEventListener('resize', updateProgress);

    const onPlainServer = !/toniesan\.com$|vercel\.app$/.test(location.hostname);
    const caseHref = (slug) => (onPlainServer ? `/work.html#${encodeURIComponent(slug)}` : `/work/${encodeURIComponent(slug)}`);
    const indexHref = () => (onPlainServer ? '/work.html' : '/work');
    function slugFromLocation() {
      const m = location.pathname.match(/^\/work\/([^/]+)\/?$/);
      if (m && m[1] !== 'index.html') return decodeURIComponent(m[1]);
      if (params.get('p')) return params.get('p');
      if (location.hash.length > 1 && location.hash !== '#top') return decodeURIComponent(location.hash.slice(1));
      return null;
    }

    let items = null;
    const bodies = {};
    async function loadItems() {
      if (items) return items;
      const r = await fetch('/content/work/index.json', { cache: 'no-store' });
      if (!r.ok) throw new Error('index.json ' + r.status);
      items = (await r.json()).items.sort((a, b) => a.order - b.order);
      return items;
    }
    async function loadBody(slug) {
      if (bodies[slug] != null) return bodies[slug];
      const r = await fetch(`/content/work/${encodeURIComponent(slug)}.md`, { cache: 'no-store' });
      bodies[slug] = r.ok ? await r.text() : '';
      return bodies[slug];
    }
    const monthYear = (iso) => new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', { month: 'long', year: 'numeric' });
    const minutes = (md) => Math.max(1, Math.round(E.wordCount(md) / 200));

    function setFooter(item) {
      document.getElementById('footer-date').textContent = item ? E.fmtSlash(item.date) : '';
      document.getElementById('footer-filed').textContent = item ? `Case study · ${item.kind}` : 'Case studies';
    }

    /* The shared renderer knows images; videos and "asset to come" boxes are swapped in after. */
    function finishMedia(item) {
      main.querySelectorAll('[data-media-id]').forEach((fig) => {
        const m = item.media[fig.dataset.mediaId];
        if (!m) return;
        if (m.kind === 'video') {
          fig.classList.add('work-video');
          fig.innerHTML = `<video src="${E.esc(m.url)}" ${m.poster ? `poster="${E.esc(m.poster)}"` : ''} autoplay muted loop playsinline controls preload="metadata" aria-label="${E.esc(m.alt || '')}"></video>${m.caption ? `<figcaption>${E.esc(m.caption)}</figcaption>` : ''}`;
        } else if (m.kind === 'placeholder') {
          fig.classList.add('work-placeholder');
          fig.innerHTML = `<div class="ph"><span class="ph-k">Asset to add</span>${E.esc(m.caption || '')}</div>`;
        }
      });
    }

    async function showCase(slug, { push = false } = {}) {
      const all = await loadItems();
      const item = all.find((i) => i.slug === slug);
      if (!item) { showIndex({ note: 'That case study could not be found.' }); return; }
      const body = await loadBody(slug);
      if (push) history.pushState({ slug }, '', caseHref(slug));
      const post = { title: item.title, excerpt: item.excerpt, body_md: body, topic_tags: item.tags, captured_on: item.date };
      const media = {};
      Object.entries(item.media || {}).forEach(([id, m]) => { media[id] = { url: m.url || '', alt: m.alt || '', caption: m.caption || '', placement: m.placement }; });
      main.innerHTML = E.articleHtml(post, { media });
      main.querySelector('.issue-line').textContent = `${item.kind} · ${monthYear(item.date)}`;
      main.querySelector('.margin-note').innerHTML = `<strong>CASE STUDY</strong>${E.esc(item.stage)}<br><br>Approx. ${minutes(body)} min read.`;
      finishMedia(item);
      document.title = `${E.plainTitle(item.title)} | Toni Esan`;
      setFooter(item);
      renderMore(item);
      scrollTo({ top: 0 });
      updateProgress();
    }

    async function showIndex({ push = false, note = '' } = {}) {
      if (push) history.pushState({}, '', indexHref());
      document.title = 'Work | Toni Esan';
      let all = [];
      try { all = await loadItems(); } catch (err) { console.error(err); note = 'The case studies could not load.'; }
      main.innerHTML = `
        <header class="index-header">
          <div class="issue-line">Toni Esan · Work</div>
          <h1>Case <em>studies</em></h1>
          <p class="deck">Client workflows, training and personal builds. What the problem was, what I did, and what it shows.</p>
        </header>
        ${note ? `<p class="empty-state">${E.esc(note)}</p>` : ''}
        <ol class="post-list">${all.map((it, i) => {
          const thumb = Object.values(it.media || {}).find((m) => m.kind === 'image');
          return `<li class="post-row">
            <a class="post-link" href="${caseHref(it.slug)}" data-slug="${E.esc(it.slug)}">
              <span class="post-no">${String(i + 1).padStart(2, '0')}</span>
              <span>
                <div class="post-meta">${E.esc(it.kind)} · ${E.esc(it.stage)}</div>
                <h2 class="post-title">${E.titleHtml(it.title)}</h2>
                <p class="post-deck">${E.esc(it.excerpt)}</p>
              </span>
              <span class="post-thumb work-thumb" aria-hidden="true">${thumb ? `<img src="${E.esc(thumb.url)}" alt="">` : ''}</span>
            </a>
          </li>`;
        }).join('')}</ol>`;
      setFooter(null);
      renderMore(null);
      updateProgress();
    }

    function renderMore(item) {
      const others = (items || []).filter((i) => !item || i.slug !== item.slug).slice(0, 3)
        .map((i) => ({ title: E.plainTitle(i.title), note: `${i.kind} · ${i.stage}`, url: caseHref(i.slug), slug: i.slug }));
      const links = [
        ...(item ? others : []),
        ...(item ? [{ title: 'All case studies', note: 'Every project, in one list', url: indexHref(), nav: true }] : []),
        { title: 'The portfolio', note: 'Projects across engineering, AI, design and more', url: '/' },
        { title: 'The blog', note: 'Voice notes, shaped into essays', url: onPlainServer ? '/blog.html' : '/blog' },
      ];
      document.getElementById('more-list').innerHTML = links.map((it, i) => `
        <li><a href="${E.esc(it.url)}" ${it.slug ? `data-slug="${E.esc(it.slug)}"` : ''} ${it.nav ? 'data-nav="index"' : ''}>
          <span class="n">${String(i + 1).padStart(2, '0')}</span>
          <span class="t">${E.esc(it.title)}${it.note ? `<small>${E.esc(it.note)}</small>` : ''}</span>
          <span class="arrow" aria-hidden="true">↗</span></a></li>`).join('');
    }

    function route() { const slug = slugFromLocation(); return slug ? showCase(slug) : showIndex(); }
    document.addEventListener('click', (e) => {
      const a = e.target.closest('a');
      if (a && a.hasAttribute('data-top')) { e.preventDefault(); scrollTo({ top: 0, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' }); return; }
      if (!a || e.metaKey || e.ctrlKey || e.shiftKey) return;
      if (a.dataset.slug) { e.preventDefault(); showCase(a.dataset.slug, { push: true }); }
      else if (a.dataset.nav === 'index') { e.preventDefault(); showIndex({ push: true }); scrollTo({ top: 0 }); }
    });
    addEventListener('popstate', route);
    addEventListener('hashchange', () => { if (onPlainServer) route(); });
    route();

    const fl = document.createElement('script');
    fl.src = '/assets/blog/flower.js?v=20260923c';
    document.body.appendChild(fl);
