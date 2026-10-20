/* Motion Studio runtime
 * Lê window.MOTION_SPEC (gerado pelo backend) e monta a timeline GSAP.
 * Regra de ouro: o DOM de cada componente nasce no estado FINAL; as animações partem de estados iniciais
 * definidos depois. Assim os clones do echo trail sempre mostram o visual correto.
 */
(function () {
  'use strict';
  const S = window.MOTION_SPEC;
  const W = S.format.w, H = S.format.h, PORT = H > W;
  const RENDER = new URLSearchParams(location.search).has('render');
  const T = S.theme;
  const rs = document.documentElement.style;
  Object.entries({ '--bg': T.bg, '--fg': T.fg, '--muted': T.muted, '--card': T.card, '--line': T.line, '--acc': T.acc,
    '--accInk': T.accInk, '--fd': `'${T.fontDisplay}'`, '--fm': `'${T.fontMono}'`, '--fb': `'${T.fontBody || T.fontDisplay}'`, '--fw': T.weight, '--stretch': T.stretch })
    .forEach(([k, v]) => rs.setProperty(k, v));
  rs.setProperty('--plateInk', T.plateInk || '#141416');
  rs.setProperty('--accPh', T.accPh || T.acc);
  rs.setProperty('--fwl', T.weightLight || 400);

  const stage = document.getElementById('stage');
  stage.style.width = W + 'px'; stage.style.height = H + 'px';
  stage.style.setProperty('--logo', `url(${S.brand.logo})`);
  function fit() { const s = Math.min(innerWidth / W, innerHeight / H); stage.style.transform = `translate(-50%,-50%) scale(${s})`; }
  fit(); addEventListener('resize', fit);

  const L = PORT ? {
    hl: { x: 90, y: 230, w: 900, h: 740, justify: 'flex-end', size: 112, maxH: 560 },
    hlFull: { x: 90, y: 300, w: 900, h: 1300, justify: 'center', size: 140, maxH: 1000 },
    slot: { x: 90, y: 1030, w: 900, h: 700 },
    corner: { x: 90, y: 90, w: 300, h: 100 },
    logo: { cx: 540, cy: 760, w: 880, h: 560 },
    prog: { x: 90, y: 1830, w: 900 }
  } : {
    hl: { x: 120, y: 0, w: 780, h: 1080, justify: 'center', size: 112, maxH: 660 },
    hlFull: { x: 160, y: 0, w: 1600, h: 1080, justify: 'center', size: 150, maxH: 720 },
    slot: { x: 960, y: 170, w: 840, h: 740 },
    corner: { x: 110, y: 54, w: 250, h: 92 },
    logo: { cx: 960, cy: 450, w: 1100, h: 470 },
    prog: { x: 120, y: 1020, w: 1680 }
  };

  /* ---------- utilidades ---------- */
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
  // gerador com semente: o filme usa a semente do projeto; cada cena troca para a sua (mudar uma cena não mexe nas outras)
  const mkRnd = s0 => { let s = (Math.abs(Math.floor(s0)) % 2147483646) || 11; return () => (s = (s * 16807) % 2147483647, (s - 1) / 2147483646); };
  let rnd = mkRnd(S.seed);
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  function wordsHTML(s) {
    let on = false;
    return String(s || '').split(/\s+/).filter(Boolean).map(w => {
      let a = on;
      if (w.startsWith('*')) { a = true; on = true; w = w.slice(1); }
      const end = w.match(/\*([.,!?;:…"')\]]*)$/);  // aceita "palavra*." além de "palavra.*"
      if (end) { w = w.slice(0, end.index) + end[1]; on = false; }
      w = w.replace(/\*/g, '');
      return `<span class="w"><span class="wi${a ? ' acc' : ''}">${esc(w)}</span></span>`;
    }).join(' ');
  }
  function parseNum(s) {
    s = String(s ?? '').trim();
    const m = s.match(/^((?:R\$|US\$|\$|€|£)?\s*)(-?\d{1,3}(?:\.\d{3})+|-?\d+)(,\d+)?(\s*(?:%|x|[a-zA-Zµ²³]{1,4}))?$/);
    if (!m) return null;
    const dec = m[3] ? m[3].length - 1 : 0;
    const num = parseFloat(m[2].replace(/\./g, '') + (m[3] ? '.' + m[3].slice(1) : ''));
    return { num, dec, pre: m[1] || '', suf: m[4] || '', group: m[2].includes('.') || Math.abs(num) >= 10000 };
  }
  const fmtNum = (v, p) => p.pre + v.toLocaleString('pt-BR', { minimumFractionDigits: p.dec, maximumFractionDigits: p.dec, useGrouping: p.group }) + p.suf;
  const counters = [];
  function count(tl, node, p, at, dur, from = 0) {
    if (!p) return;
    const o = { v: from }; counters.push({ node, o, p, last: null });
    tl.to(o, { v: p.num, duration: dur, ease: 'expo.out' }, at);
  }
  function updCounters() { for (const c of counters) { const t = fmtNum(c.o.v, c.p); if (t !== c.last) { c.node.textContent = t; c.last = t; } } }
  const FRAME = [];  // funções chamadas a cada quadro (e em cada seek do render)
  function frame() { updCounters(); for (const f of FRAME) f(); }
  // a headline encolhe até um mínimo legível (theme.minFont); se ainda não couber, aperta o entrelinha em vez de ficar miúda
  function fitText(node, maxH, start, min = T.minFont || 64) {
    min = Math.round(min * (T.fontScale || 1));
    let s = Math.max(Math.round(start * (T.fontScale || 1)), min); node.style.fontSize = s + 'px';
    while (node.scrollHeight > maxH && s > min) { s -= 4; node.style.fontSize = s + 'px'; }
    if (node.scrollHeight > maxH) node.style.lineHeight = '.94';
    return s;
  }
  function fitWidth(node, maxW, min = 30) { let s = parseFloat(getComputedStyle(node).fontSize); while (node.scrollWidth > maxW && s > min) { s -= 3; node.style.fontSize = s + 'px'; } }
  function fitBox(w, h, mw, mh) { const s = Math.min(mw / w, mh / h); return { w: w * s, h: h * s }; }
  let uid = 0;
  function stampSVG(text) {
    const id = 'stp' + (uid++);
    const t = (String(text).toUpperCase() + ' • ').repeat(2);
    return el('div', 'c-stamp', `<svg viewBox="0 0 200 200" width="100%" height="100%"><defs><path id="${id}" d="M100,100 m-72,0 a72,72 0 1,1 144,0 a72,72 0 1,1 -144,0"/></defs><circle cx="100" cy="100" r="96" fill="${T.bg}" stroke="${T.acc}" stroke-width="3"/><circle cx="100" cy="100" r="86" fill="none" stroke="${T.acc}" stroke-width="1"/><g class="ring"><text font-family="${T.fontMono}, monospace" font-size="14" font-weight="800" letter-spacing="2.5" fill="${T.fg}"><textPath href="#${id}" textLength="440">${esc(t)}</textPath></text></g><path d="M78 102l15 15 30-32" fill="none" stroke="${T.acc}" stroke-width="7" stroke-linecap="square"/></svg>`);
  }

  /* ---------- echo trail ---------- */
  function cloneFor(e) {
    const c = e.cloneNode(true); c.removeAttribute('id');
    c.style.transform = ''; c.style.opacity = ''; c.style.visibility = ''; c.style.filter = '';
    c.querySelectorAll('[id]').forEach(x => x.removeAttribute('id'));
    return c;
  }
  const OPS = [.38, .22, .12];
  function echo(tl, e, from, to, at, n = 3, gap = .055) {
    const fA = { ...from }; delete fA.autoAlpha;
    for (let i = n; i >= 1; i--) {
      const c = cloneFor(e); c.classList.add('echo'); e.parentNode.insertBefore(c, e); gsap.set(c, { autoAlpha: 0 });
      tl.set(c, { autoAlpha: OPS[i - 1] }, at + i * gap);
      tl.fromTo(c, fA, { ...to, autoAlpha: 0, immediateRender: false }, at + i * gap);
    }
    tl.fromTo(e, from, { ...to, immediateRender: false }, at);
    if (from.autoAlpha === 0) gsap.set(e, { autoAlpha: 0 });
  }

  /* ---------- facetas ---------- */
  function shards(container, cols, rows, make) {
    const P = [];
    for (let r = 0; r <= rows; r++) { P.push([]); for (let c = 0; c <= cols; c++) {
      let x = c / cols * 100, y = r / rows * 100;
      if (c > 0 && c < cols) x += (rnd() - .5) * (60 / cols);
      if (r > 0 && r < rows) y += (rnd() - .5) * (60 / rows);
      P[r].push([x, y]);
    } }
    const out = [];
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
      const a = P[r][c], b = P[r][c + 1], d = P[r + 1][c], e = P[r + 1][c + 1];
      const tris = (r + c) % 2 ? [[a, b, e], [a, e, d]] : [[a, b, d], [b, e, d]];
      tris.forEach(t => {
        const s = make();
        s.style.clipPath = `polygon(${t.map(p => p[0].toFixed(2) + '% ' + p[1].toFixed(2) + '%').join(',')})`;
        s._cx = (t[0][0] + t[1][0] + t[2][0]) / 3; s._cy = (t[0][1] + t[1][1] + t[2][1]) / 3;
        container.insertBefore(s, container.firstChild); out.push(s);
      });
    }
    out.forEach(s => { const a = rnd() * Math.PI * 2, d = 500 + rnd() * 700; s._fx = Math.cos(a) * d; s._fy = Math.sin(a) * d * .7; s._fr = (rnd() - .5) * 240; });
    return out;
  }
  const scatter = (arr, k = 1) => ({ x: i => arr[i]._fx * k, y: i => arr[i]._fy * k, rotation: i => arr[i]._fr, scale: .4, autoAlpha: 0 });

  /* ---------- componentes ---------- */
  const C = {};
  const ICONS = S.icons || {};
  const ico = name => (name && ICONS[name]) ? `<span class="ico" aria-hidden="true">${ICONS[name]}</span>` : '';

  C.counter = (u, b) => {
    const e = el('div', 'c-col');
    const val = String(u.value || '');
    const fs = clamp(Math.floor(b.w / (Math.max(val.length, 4) * .62)), 44, 120);
    e.innerHTML = `${u.label ? `<div class="k">${esc(u.label)}</div>` : ''}<div class="c-big mn" style="font-size:${fs}px">${esc(val)}</div>`;
    const segs = [];
    if (u.segments && u.segments.length) {
      const bar = el('div', 'c-split'); let used = 0;
      u.segments.forEach((s, i) => {
        const p = s.pct != null ? s.pct : Math.max(0, 100 - used); used += p;
        const d = el('div', 'c-seg' + (i === 0 ? ' inv' : ''), `<span>${esc(s.label)}</span>`);
        d.style.flex = `${Math.max(p, 6)} 1 0`; bar.appendChild(d); segs.push(d);
      });
      e.appendChild(bar);
    }
    if (u.note) e.appendChild(el('div', 'c-note', esc(u.note)));
    return { el: e, layout() { fitWidth(e.querySelector('.c-big'), b.w); }, anim(tl, t, d) {
      count(tl, e.querySelector('.c-big'), parseNum(val), t, Math.min(2.4, d * .5));
      if (segs.length) { gsap.set(segs, { scaleX: 0 }); tl.to(segs, { scaleX: 1, duration: .8, ease: 'expo.inOut', stagger: .22 }, t + Math.min(1, d * .25)); }
      const n = e.querySelector('.c-note'); if (n) { gsap.set(n, { autoAlpha: 0 }); tl.to(n, { autoAlpha: 1, duration: .6 }, t + Math.min(1.6, d * .4)); }
    } };
  };

  C.cards = (u, b) => {
    const items = (u.items || []).slice(0, 5); const n = Math.max(items.length, 1);
    const e = el('div', 'c-col c-cards');
    const h = Math.min(150, (b.h - 14 * (n - 1)) / n);
    const vfs = Math.min(n <= 3 ? 54 : 44, h * .42);
    const rows = items.map(it => {
      const r = el('div', 'c-card c-item'); r.style.height = h + 'px';
      r.innerHTML = `<div class="k">${ico(it.icon)}${esc(it.label)}</div><div class="c-val mn" style="font-size:${vfs}px">${esc(it.value)}</div>${it.sub ? `<div class="c-sub">${esc(it.sub)}</div>` : ''}`;
      e.appendChild(r); return r;
    });
    const scan = el('div', 'c-scan'); e.appendChild(scan);
    return { el: e, anim(tl, t, d) {
      gsap.set(rows, { autoAlpha: 0, x: 50 });
      tl.to(rows, { autoAlpha: 1, x: 0, duration: .7, stagger: .12 }, t);
      rows.forEach((r, i) => count(tl, r.querySelector('.c-val'), parseNum(items[i].value), t + .15 + i * .12, 1.4));
      if (!rows.length) return;
      const top = rows[0].offsetTop, span = rows[rows.length - 1].offsetTop + rows[rows.length - 1].offsetHeight - top;
      scan.style.top = top + 'px';
      const st = t + Math.min(1.6, d * .35), sd = Math.min(1.2, d * .3);
      tl.set(scan, { autoAlpha: 1, y: 0 }, st);
      tl.to(scan, { y: span, duration: sd, ease: 'power1.inOut' }, st);
      tl.to(scan, { autoAlpha: 0, duration: .2 }, st + sd);
      rows.forEach((r, i) => tl.to(r, { borderColor: T.acc, duration: .15, yoyo: true, repeat: 1, ease: 'power1.inOut' }, st + sd * (r.offsetTop - top + r.offsetHeight / 2) / span - .1));
    } };
  };

  C.chat = (u) => {
    const e = el('div', 'c-card c-chat');
    e.innerHTML = `<div class="c-head"><span class="c-live"></span>${esc(u.title || 'Agente de IA')}</div><div class="c-msgs"></div>`;
    const box = e.querySelector('.c-msgs');
    const msgs = (u.messages || []).slice(0, 6).map(m => {
      const role = ['user', 'agent', 'external'].includes(m.role) ? m.role : 'agent';
      const d = el('div', 'c-msg c-' + role);
      const lab = role === 'external' ? `<span class="c-src">${esc(m.label || 'Conteúdo externo')}</span>` : '';
      d.innerHTML = lab + (m.highlight ? `<span class="c-hi">${esc(m.text)}</span>` : esc(m.text));
      box.appendChild(d); return d;
    });
    let note = null; if (u.note) { note = el('div', 'c-tag inv', esc(u.note)); e.appendChild(note); }
    return { el: e, anim(tl, t, d) {
      const step = Math.min(.7, (d * .55) / Math.max(msgs.length, 1));
      gsap.set(msgs, { autoAlpha: 0, y: 16 });
      msgs.forEach((m, i) => {
        tl.to(m, { autoAlpha: 1, y: 0, duration: .5 }, t + i * step);
        const hi = m.querySelector('.c-hi');
        if (hi) { gsap.set(hi, { backgroundSize: '0% 100%', color: T.fg }); tl.to(hi, { backgroundSize: '100% 100%', color: T.accInk, duration: .7, ease: 'expo.inOut' }, t + i * step + .55); }
      });
      if (note) { gsap.set(note, { autoAlpha: 0 }); const nt = t + msgs.length * step + .5; tl.to(note, { autoAlpha: 1, duration: .3 }, nt); tl.to(note, { opacity: .3, duration: .3, yoyo: true, repeat: 3, ease: 'power1.inOut' }, nt + .4); }
    } };
  };

  C.flow = (u, b) => {
    const nodes = (u.nodes || []).slice(0, 4); const n = Math.max(nodes.length, 2);
    const hiI = Number.isInteger(u.highlight) && u.highlight >= 0 && u.highlight < n ? u.highlight : n - 1;
    const gap = PORT ? 40 : 56, nw = Math.min(260, (b.w - gap * (n - 1)) / n), nh = 170;
    const x0 = (b.w - (nw * n + gap * (n - 1))) / 2, y0 = (b.h - nh) / 2 + 30;
    const e = el('div', 'c-flow');
    const nd = nodes.map((x, i) => {
      const d = el('div', 'c-node' + (i === hiI ? ' hi' : ''), `${ico(x.icon)}<b>${esc(x.title)}</b>${x.sub ? `<small>${esc(x.sub)}</small>` : ''}`);
      Object.assign(d.style, { left: x0 + i * (nw + gap) + 'px', top: y0 + 'px', width: nw + 'px', height: nh + 'px' });
      e.appendChild(d); return d;
    });
    const lines = [];
    for (let i = 0; i < n - 1; i++) { const l = el('div', 'c-link'); Object.assign(l.style, { left: x0 + (i + 1) * nw + i * gap + 'px', top: y0 + nh / 2 + 'px', width: gap + 'px' }); e.appendChild(l); lines.push(l); }
    let pill = null;
    if (u.label) { pill = el('div', 'c-pill inv mn', esc(u.label)); e.appendChild(pill); }
    let pv = null;
    return { el: e, layout() {
      if (!pill) return;
      const pw = pill.offsetWidth, ph = pill.offsetHeight;
      const cx = i => x0 + i * (nw + gap) + nw / 2 - pw / 2;
      const fy = y0 + nh - ph - 14, sy = y0 - ph - 18;
      pill.style.left = cx(hiI) + 'px'; pill.style.top = fy + 'px';
      pv = { dx: cx(0) - cx(hiI), dy: sy - fy };
    }, anim(tl, t) {
      gsap.set(nd, { autoAlpha: 0, y: 30 });
      tl.to(nd, { autoAlpha: 1, y: 0, duration: .7, stagger: .15 }, t);
      gsap.set(lines, { scaleX: 0 });
      tl.to(lines, { scaleX: 1, duration: .6, stagger: .2, ease: 'expo.inOut' }, t + .4);
      if (pill && pv) {
        gsap.set(pill, { x: pv.dx, y: pv.dy, autoAlpha: 0, scale: .6 });
        tl.to(pill, { autoAlpha: 1, scale: 1, duration: .4 }, t + .9);
        tl.to(pill, { x: 0, duration: 1.1, ease: 'expo.inOut' }, t + 1.3);
        tl.to(pill, { y: 0, duration: .5, ease: 'expo.inOut' }, t + 2.4);
      }
      tl.fromTo(nd[hiI], { boxShadow: '0 0 0px rgba(0,0,0,0)' }, { boxShadow: `0 0 44px ${T.accGlow}`, duration: .6, immediateRender: false }, t + 2.5);
    } };
  };

  C.checklist = (u) => {
    const wrap = el('div', 'c-center');
    const e = el('div', 'c-card c-check'); wrap.appendChild(e);
    e.innerHTML = (u.title ? `<div class="c-ttl">${esc(u.title)}</div>` : '') + (u.items || []).slice(0, 6).map(it =>
      `<div class="c-ci"><svg viewBox="0 0 26 26"><circle cx="13" cy="13" r="12"/><path d="M8 13.5l3.4 3.4L18.5 10"/></svg>${ico(it.icon)}<span>${esc(it.label)}</span></div>`).join('');
    let st = null; if (u.stamp) { st = stampSVG(u.stamp); e.appendChild(st); }
    return { el: wrap, anim(tl, t, d) {
      const rows = [...e.querySelectorAll('.c-ci')], step = Math.min(.4, d * .5 / Math.max(rows.length, 1));
      gsap.set(rows, { autoAlpha: 0, x: -16 });
      tl.to(rows, { autoAlpha: 1, x: 0, duration: .5, stagger: step }, t);
      const ps = rows.map(r => r.querySelector('path'));
      gsap.set(ps, { strokeDashoffset: 30 });
      tl.to(ps, { strokeDashoffset: 0, duration: .45, stagger: step, ease: 'power2.out' }, t + .25);
      if (st) {
        const at = t + rows.length * step + .4;
        gsap.set(st, { autoAlpha: 0, scale: 0, rotation: -90 });
        tl.to(st, { autoAlpha: 1, scale: 1, rotation: -8, duration: .9, ease: 'back.out(1.6)' }, at);
        tl.fromTo(st.querySelector('.ring'), { rotation: 0 }, { rotation: 120, svgOrigin: '100 100', duration: Math.max(1, d - (at - t)), ease: 'none', immediateRender: false }, at);
      }
    } };
  };

  C.steps = (u) => {
    const steps = (u.steps || []).slice(0, 5); const n = Math.max(steps.length, 1);
    const e = el('div', 'c-card c-steps');
    const bar = el('div', 'c-prog4'); bar.style.gridTemplateColumns = `repeat(${n},1fr)`;
    bar.innerHTML = steps.map(() => '<div><i></i></div>').join(''); e.appendChild(bar);
    const panes = steps.map((s, i) => {
      const p = el('div', 'c-pane' + (i < n - 1 ? ' off' : ''));
      p.innerHTML = `<div class="c-ph"><b>${i + 1}. ${esc(s.title)}</b>${s.detail ? `<span>${esc(s.detail)}</span>` : ''}</div><div class="c-lines mn">${(s.lines || []).slice(0, 6).map(l => {
        const f = /^!/.test(l); return `<div class="c-ln${f ? ' flag' : ''}">${esc(f ? l.slice(1).trim() : l)}</div>`; }).join('')}</div>`;
      e.appendChild(p); return p;
    });
    return { el: e, anim(tl, t, d) {
      const per = d / n, segs = [...bar.querySelectorAll('i')];
      gsap.set(segs, { scaleX: 0 }); gsap.set(panes, { autoAlpha: 0 });
      panes.forEach((p, i) => {
        const ti = t + i * per;
        tl.to(segs[i], { scaleX: 1, duration: .7, ease: 'expo.inOut' }, ti + .1);
        tl.set(p, { autoAlpha: 1 }, ti);
        tl.fromTo(p, { clipPath: 'polygon(0% 0%,0% 0%,-25% 100%,-25% 100%)' }, { clipPath: 'polygon(0% 0%,125% 0%,100% 100%,-25% 100%)', duration: .65, ease: 'expo.inOut', immediateRender: false }, ti);
        const lns = [...p.querySelectorAll('.c-ln')];
        gsap.set(lns, { autoAlpha: 0, x: 24 });
        tl.to(lns, { autoAlpha: 1, x: 0, duration: .4, stagger: Math.min(.14, per * .3 / Math.max(lns.length, 1)) }, ti + .4);
        p.querySelectorAll('.c-ln.flag').forEach(f => {
          gsap.set(f, { backgroundColor: 'rgba(0,0,0,0)', color: T.fg });
          tl.to(f, { backgroundColor: T.acc, color: T.accInk, duration: .25, ease: 'none' }, ti + per * .55);
        });
        if (i < n - 1) tl.to(p, { x: -60, autoAlpha: 0, filter: 'blur(6px)', duration: .35, ease: 'power3.in' }, ti + per - .35);
      });
    } };
  };

  C.table = (u) => {
    const cols = (u.columns || []).slice(0, 4), rows = (u.rows || []).slice(0, 6);
    const wrap = el('div', 'c-center'), e = el('div', 'c-card c-table'); wrap.appendChild(e);
    e.innerHTML = `${u.title ? `<div class="c-ttl" style="font-size:26px">${esc(u.title)}</div>` : ''}<table class="mn"><tr>${cols.map(c => `<th>${esc(c)}</th>`).join('')}</tr>${rows.map(r =>
      `<tr>${cols.map((_, j) => { const v = String(r[j] ?? ''); const f = v.startsWith('!'); return `<td class="${f ? 'flag' : ''}">${esc(f ? v.slice(1).trim() : v)}</td>`; }).join('')}</tr>`).join('')}</table>`;
    return { el: wrap, anim(tl, t, d) {
      const trs = [...e.querySelectorAll('tr')].slice(1);
      gsap.set(trs, { autoAlpha: 0, x: 24 });
      tl.to(trs, { autoAlpha: 1, x: 0, duration: .45, stagger: Math.min(.18, d * .4 / Math.max(trs.length, 1)) }, t);
      const fl = [...e.querySelectorAll('td.flag')];
      if (fl.length) { gsap.set(fl, { color: T.fg }); tl.to(fl, { color: T.acc, duration: .3, stagger: .12 }, t + Math.min(1.6, d * .45)); }
    } };
  };

  C.verdict = (u, b) => {
    const wrap = el('div', 'c-center'), e = el('div', 'c-card c-verdict'); wrap.appendChild(e);
    const st = String(u.status || 'VEREDITO');
    const fs = clamp(Math.floor((b.w - 90) / (st.length * .66)), 48, 120);
    e.innerHTML = `<div class="c-vblk inv" style="font-size:${fs}px">${esc(st)}</div><div class="c-vbody">${u.reason ? `<div class="c-vreason">${esc(u.reason)}</div>` : ''}<div class="c-vrows mn">${(u.items || []).slice(0, 4).map(it =>
      `<div class="c-vr"><span>${esc(it.label)}</span><span>${esc(it.value)}</span></div>`).join('')}</div></div>`;
    let sp = null; if (u.stamp) { sp = stampSVG(u.stamp); e.appendChild(sp); }
    return { el: wrap, layout() { const blk = e.querySelector('.c-vblk'); fitWidth(blk, blk.clientWidth - 40); }, anim(tl, t, d) {
      const blk = e.querySelector('.c-vblk');
      gsap.set(blk, { scaleX: 0 }); tl.to(blk, { scaleX: 1, duration: .7, ease: 'expo.inOut' }, t + .1);
      const r = e.querySelector('.c-vreason'); if (r) { gsap.set(r, { autoAlpha: 0, y: 16 }); tl.to(r, { autoAlpha: 1, y: 0, duration: .6 }, t + .7); }
      const vr = [...e.querySelectorAll('.c-vr')]; gsap.set(vr, { autoAlpha: 0, x: 20 });
      tl.to(vr, { autoAlpha: 1, x: 0, duration: .45, stagger: .15 }, t + 1.1);
      if (sp) {
        const at = t + Math.min(2.4, d * .5);
        gsap.set(sp, { autoAlpha: 0, scale: 2.2, rotation: -30 });
        tl.to(sp, { autoAlpha: 1, scale: 1, rotation: -12, duration: .35, ease: 'power4.in' }, at);
        tl.to(e, { x: '+=8', duration: .05, yoyo: true, repeat: 5, ease: 'none' }, at + .35);
      }
    } };
  };

  C.feed = (u, b) => {
    const lines = (u.lines || []).slice(0, 16), RH = 56;
    const e = el('div', 'c-card c-feed');
    e.innerHTML = `<div class="c-head"><span class="c-live"></span>${esc(u.title || 'Agente de IA')}${u.label ? `<span class="c-pl">${esc(u.label)}</span>` : ''}</div><div class="c-fw"><div class="c-fl mn"></div></div>`;
    const fl = e.querySelector('.c-fl');
    const rows = lines.map((l, i) => {
      const [a, s] = String(l).split(/\s*\|\s*/);
      const r = el('div', 'c-fr', `<span class="t">14:32:${String(10 + i * 3).padStart(2, '0')}.${String(100 + (i * 137) % 900)}</span><span>${esc(a)}</span><span class="st">${esc(s || u.note || 'executado')}</span>`);
      r.style.top = i * RH + 'px'; fl.appendChild(r); return r;
    });
    const viewH = b.h - 92 - 24, max = Math.max(0, lines.length * RH - viewH);
    fl.style.top = -max + 'px';
    return { el: e, anim(tl, t, d) {
      gsap.set(rows, { autoAlpha: 0 });
      tl.to(rows, { autoAlpha: 1, duration: .25, stagger: Math.min(.18, d * .7 / Math.max(rows.length, 1)) }, t);
      tl.fromTo(fl, { y: max }, { y: 0, duration: d * .8, ease: 'power2.in', immediateRender: false }, t + .2);
      gsap.set(fl, { y: max });
    } };
  };

  C.bars = (u) => {
    const items = (u.items || []).slice(0, 4);
    const ps = items.map(it => parseNum(it.value));
    const max = Math.max(1, ...ps.map(p => p ? p.num : 0));
    const e = el('div', 'c-col c-bars');
    const fills = items.map((it, i) => {
      const p = ps[i]; const pct = p ? (p.suf.trim() === '%' ? p.num : p.num / max * 100) : 60;
      const row = el('div', '', `<div class="c-bl"><span>${esc(it.label)}</span><b class="mn">${esc(it.value)}</b></div><div class="c-bt"><i class="${i === 0 ? 'a' : ''}" style="width:${clamp(pct, 2, 100)}%"></i></div>${it.sub ? `<div class="c-bs">${esc(it.sub)}</div>` : ''}`);
      e.appendChild(row); return row;
    });
    if (u.note) e.appendChild(el('div', 'c-note', esc(u.note)));
    return { el: e, anim(tl, t) {
      gsap.set(fills, { autoAlpha: 0, y: 16 });
      tl.to(fills, { autoAlpha: 1, y: 0, duration: .5, stagger: .25 }, t);
      fills.forEach((r, i) => {
        const f = r.querySelector('i'); gsap.set(f, { scaleX: 0 });
        tl.to(f, { scaleX: 1, duration: 1, ease: 'expo.inOut' }, t + .2 + i * .25);
        count(tl, r.querySelector('b'), ps[i], t + .2 + i * .25, 1.2);
      });
      const n = e.querySelector('.c-note'); if (n) { gsap.set(n, { autoAlpha: 0 }); tl.to(n, { autoAlpha: 1, duration: .6 }, t + 1.4); }
    } };
  };

  C.gallery = (u, b) => {
    const items = (u.items || []).filter(it => S.refs && S.refs[it.image]).slice(0, 4);
    const wrap = el('div', 'c-gal');
    const ar = 4 / 3; let fw = b.w * .86, fh = fw / ar;
    if (fh > b.h * .8) { fh = b.h * .8; fw = fh * ar; }
    const frames = items.map((it, k) => {
      const f = el('div', 'c-galf');
      Object.assign(f.style, { width: fw + 'px', height: fh + 'px', left: (b.w - fw) / 2 + 'px', top: (b.h - fh) / 2 + 'px' });
      f.innerHTML = `<i style="background-image:url(${S.refs[it.image].src})"></i>` + (it.label ? `<span class="phc-tag"><em>✦</em>${esc(it.label)}</span>` : '');
      wrap.appendChild(f); return f;
    });
    const rot = k => (k % 2 ? 3.5 : -3);
    return { el: wrap, anim(tl, t, d) {
      const step = Math.max(1.2, (d - .4) / Math.max(1, frames.length));
      frames.forEach((f, k) => {
        gsap.set(f, { autoAlpha: 0, xPercent: 70, rotation: 14, scale: .9 });
        const tt = t + k * step;
        tl.to(f, { autoAlpha: 1, xPercent: 0, rotation: rot(k), scale: 1, duration: .9, ease: 'expo.out' }, tt);
        tl.fromTo(f.firstChild, { scale: 1.15 }, { scale: 1, duration: step + 1, ease: 'none', immediateRender: false }, tt);
        frames.slice(0, k).forEach((p, j) => tl.to(p, { scale: .9 - (k - j) * .03, yPercent: -(k - j) * 5, rotation: rot(j) * 1.6, filter: 'brightness(.7)', duration: .8, ease: 'expo.out' }, tt));
      });
    } };
  };

  C.image = (u, b) => {
    const key = (S.refs[u.image] ? u.image : Object.keys(S.refs)[0]);
    if (!key) return null;
    const ref = S.refs[key], ar = ref.ar || 1.6;
    const phone = ar < .8, chrome = phone ? 0 : 38;
    const box = fitBox(ar, 1, b.w - 40, b.h - 60 - chrome);
    const wrap = el('div', 'c-center');
    const f = el('div', 'c-frame ' + (phone ? 'phone' : 'web'));
    Object.assign(f.style, { width: box.w + 'px', height: box.h + chrome + 'px' });
    f.innerHTML = (phone ? '' : '<div class="c-chrome"><i></i><i></i><i></i></div>') + `<div class="c-img" style="top:${chrome}px;background-image:url(${ref.src})"></div>`;
    wrap.appendChild(f);
    const pos = [['-24px', null, '18%', null], [null, '-24px', null, '16%'], ['-24px', null, null, '30%']];
    const tags = (u.items || []).slice(0, 3).map((it, i) => {
      const tg = el('div', 'c-ftag ' + (i === 0 ? 'inv' : 'c-card'), esc(it.label));
      const [l, r, tp, bt] = pos[i];
      Object.assign(tg.style, { left: l ?? 'auto', right: r ?? 'auto', top: tp ?? 'auto', bottom: bt ?? 'auto' });
      f.appendChild(tg); f.style.overflow = 'visible'; return tg;
    });
    f.querySelector('.c-img').style.borderRadius = phone ? '34px' : '0 0 11px 11px';
    return { el: wrap, anim(tl, t, d) {
      tl.fromTo(f.querySelector('.c-img'), { scale: 1.14 }, { scale: 1, duration: d + .8, ease: 'power1.out', immediateRender: false }, t - .4);
      gsap.set(tags, { autoAlpha: 0, scale: .7 });
      tl.to(tags, { autoAlpha: 1, scale: 1, duration: .5, ease: 'back.out(2)', stagger: .3 }, t + .8);
    } };
  };

  /* ---------- heróis (pacotes de domínio) ----------
   * Um herói é um objeto visual que atravessa várias cenas seguidas, mudando de estado.
   * HEROES.nome = (u, box) => ({ el, layout?(), go(tl, state, t, d, u) })
   */
  const HEROES = {};
  const BRAND = S.brand;
/*@@PACKS@@*/

  /* ---------- montagem ---------- */
  const tl = gsap.timeline({ paused: true, defaults: { ease: 'expo.out' } });
  const anchor = document.getElementById('anchor');
  const tex = el('div', 'tex ' + (T.texture || 'dots')); stage.insertBefore(tex, stage.firstChild);
  gsap.set(tex, { autoAlpha: 0 });
  tl.to(tex, { autoAlpha: 1, duration: 2, ease: 'power1.out' }, 0);
  /* ---------- vida no fundo: decoração animada, fotos e ilustrações ----------
   * Tudo fica atrás do texto (z-index baixo) e anda na timeline, então o render quadro a quadro é igual ao preview. */
  const PALD = T.decoPalette || T.palette || [T.acc, T.fg, T.muted];
  const LIGHT = T.mode === 'light';
  stage.classList.add('mode-' + (T.mode || 'dark'), 'skin-' + (T.skin || 'clean'), PORT ? 'port' : 'land');
  const decoL = el('div', 'deco'); stage.insertBefore(decoL, tex.nextSibling);
  const SC = S.scenes;
  const sceneStarts = SC.map(s => s.at);
  const rpos = (mx = .12) => ({ x: (rnd() < .5 ? rnd() * mx : 1 - rnd() * mx) * W, y: (.08 + rnd() * .84) * H });
  // posição na moldura da tela (faixas de cima, de baixo e laterais finas), longe do texto
  const edge = () => {
    const k = rnd(), sx = PORT ? .06 : .045;
    if (k < .35) return { x: (.05 + rnd() * .9) * W, y: (.02 + rnd() * (PORT ? .06 : .09)) * H };
    if (k < .6) return { x: (.05 + rnd() * .9) * W, y: (PORT ? .935 : .9) * H + rnd() * .03 * H };
    return { x: (rnd() < .5 ? rnd() * sx : 1 - rnd() * sx) * W, y: (.1 + rnd() * .8) * H };
  };
  const DECO = {
    // manchas de luz com as cores da marca que passeiam a cada cena
    orbs() {
      const n = 3, sz = Math.max(W, H) * .7;
      const orbs = Array.from({ length: n }, (_, i) => {
        const o = el('div', 'orb');
        Object.assign(o.style, { width: sz + 'px', height: sz + 'px', margin: -sz / 2 + 'px 0 0 ' + -sz / 2 + 'px',
          background: `radial-gradient(circle, ${PALD[i % PALD.length]} 0%, transparent 62%)` });
        decoL.appendChild(o); return o;
      });
      gsap.set(orbs, { x: () => rpos(.3).x, y: () => rpos().y, autoAlpha: 0, scale: .8 });
      tl.to(orbs, { autoAlpha: LIGHT ? .28 : .34, duration: 2, stagger: .3, ease: 'power1.out' }, .2);
      sceneStarts.forEach((t, k) => orbs.forEach((o, i) => {
        const p = rpos(.35);
        tl.to(o, { x: p.x, y: p.y, scale: .7 + rnd() * .6, duration: Math.max(2, (SC[k].dur || 4) * .9), ease: 'sine.inOut' }, t - .3);
      }));
    },
    // formas geométricas (círculo, quadrado, cruz, triângulo, zigue-zague) que dançam entre as cenas
    shapes() {
      const kinds = [
        c => `<circle cx="50" cy="50" r="40" fill="none" stroke="${c}" stroke-width="8"/>`,
        c => `<circle cx="50" cy="50" r="30" fill="${c}"/>`,
        c => `<rect x="18" y="18" width="64" height="64" rx="6" fill="none" stroke="${c}" stroke-width="8"/>`,
        c => `<path d="M50 14v72M14 50h72" stroke="${c}" stroke-width="12" stroke-linecap="round"/>`,
        c => `<path d="M50 12L90 84H10z" fill="none" stroke="${c}" stroke-width="8" stroke-linejoin="round"/>`,
        c => `<path d="M8 62l14-20 14 20 14-20 14 20 14-20 14 20" fill="none" stroke="${c}" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>`,
      ];
      const n = PORT ? 9 : 11;
      const sh = Array.from({ length: n }, (_, i) => {
        const s = el('div', 'shp', `<svg viewBox="0 0 100 100" width="100%" height="100%">${kinds[i % kinds.length](PALD[i % PALD.length])}</svg>`);
        const z = 34 + rnd() * 56; Object.assign(s.style, { width: z + 'px', height: z + 'px', margin: -z / 2 + 'px 0 0 ' + -z / 2 + 'px' });
        s.style.opacity = .75; decoL.appendChild(s); return s;
      });
      gsap.set(sh, { x: i => (sh[i]._p = edge()).x, y: i => sh[i]._p.y, scale: 0, rotation: () => rnd() * 360 });
      tl.to(sh, { scale: 1, duration: .8, ease: 'back.out(2)', stagger: { each: .06, from: 'random' } }, .4);
      sceneStarts.forEach(t => sh.forEach(s => {
        const p = edge();
        tl.to(s, { x: p.x, y: p.y, rotation: '+=' + (90 + rnd() * 180), duration: 1.3, ease: 'expo.inOut' }, t - .35 + rnd() * .2);
      }));
      tl.to(sh, { y: '-=40', duration: S.duration, ease: 'none' }, 0);
    },
    // anéis tracejados gigantes que giram devagar, trocando de canto a cada cena
    rings() {
      const corners = [[0, 0], [1, 0], [1, 1], [0, 1]];
      const rs2 = [0, 1].map(i => {
        const z = Math.max(W, H) * (i ? .55 : .8);
        const r = el('div', 'rng', `<svg viewBox="0 0 200 200" width="100%" height="100%"><circle cx="100" cy="100" r="96" fill="none" stroke="${PALD[i]}" stroke-width="${i ? 1.2 : .8}" stroke-dasharray="${i ? '2 6' : '30 10 4 10'}"/><circle cx="100" cy="100" r="80" fill="none" stroke="${PALD[(i + 1) % 3]}" stroke-width=".6"/></svg>`);
        Object.assign(r.style, { width: z + 'px', height: z + 'px', margin: -z / 2 + 'px 0 0 ' + -z / 2 + 'px' });
        decoL.appendChild(r); return r;
      });
      gsap.set(rs2, { x: i => corners[i * 2][0] * W, y: i => corners[i * 2][1] * H, autoAlpha: 0, scale: .6 });
      tl.to(rs2, { autoAlpha: LIGHT ? .4 : .3, scale: 1, duration: 1.6, ease: 'expo.out', stagger: .2 }, .3);
      tl.to(rs2, { rotation: i => (i ? -1 : 1) * 25 * S.duration, duration: S.duration, ease: 'none' }, 0);
      sceneStarts.forEach((t, k) => rs2.forEach((r, i) => {
        const c = corners[(k + 1 + i * 2) % 4];
        tl.to(r, { x: c[0] * W, y: c[1] * H, duration: 1.6, ease: 'expo.inOut' }, t - .4);
      }));
    },
    // feixes diagonais que cruzam a tela na troca de cena
    lines() {
      const n = 5, len = Math.hypot(W, H) * 1.2;
      const ls = Array.from({ length: n }, (_, i) => {
        const l = el('div', 'dln'); Object.assign(l.style, { width: len + 'px', height: (i % 2 ? 2 : 6) + 'px', background: PALD[i % PALD.length],
          left: (W - len) / 2 + 'px', top: H / 2 + 'px' });
        decoL.appendChild(l); return l;
      });
      gsap.set(ls, { rotation: -32, y: i => (i - 2) * 46, xPercent: -110 });
      sceneStarts.forEach(t => {
        tl.set(ls, { xPercent: -110 }, t - .6);
        tl.to(ls, { xPercent: 110, duration: .9, ease: 'expo.inOut', stagger: .04 }, t - .6);
      });
      // duas linhas finas fixas que respiram no canto
      const fixed = [0, 1].map(i => { const f = el('div', 'dln'); Object.assign(f.style, { width: len * .5 + 'px', height: '1.5px', background: PALD[i + 1] || PALD[0],
        left: (i ? W * .55 : -len * .1) + 'px', top: (i ? H * .88 : H * .12) + 'px', opacity: .5 }); decoL.appendChild(f); return f; });
      gsap.set(fixed, { rotation: -32, scaleX: 0, transformOrigin: '0 50%' });
      tl.to(fixed, { scaleX: 1, duration: 1.5, ease: 'expo.out', stagger: .2 }, .5);
    },
    // ondas que correm no rodapé
    waves() {
      const hh = H * (PORT ? .2 : .26), w2 = W * 2;
      const wave = (amp, ph) => { let d = `M0 ${hh}`; for (let x = 0; x <= w2; x += 40) d += ` L${x} ${hh * .5 + Math.sin(x / W * Math.PI * 4 + ph) * amp}`; return d + ` L${w2} ${hh} Z`; };
      const box = el('div', 'wvs', `<svg width="${w2}" height="${hh}" viewBox="0 0 ${w2} ${hh}">${[0, 1, 2].map(i =>
        `<path d="${wave(hh * (.18 + i * .07), i * 1.7)}" fill="${PALD[i % PALD.length]}" opacity="${[.22, .16, .12][i]}"/>`).join('')}</svg>`);
      Object.assign(box.style, { top: H - hh + 'px', height: hh + 'px', width: w2 + 'px' });
      decoL.appendChild(box);
      const ps = box.querySelectorAll('path');
      gsap.set(box, { yPercent: 100 });
      tl.to(box, { yPercent: 0, duration: 1.6, ease: 'expo.out' }, .3);
      ps.forEach((p, i) => tl.to(p, { x: -W, duration: S.duration / (1 + i * .5), ease: 'none', repeat: Math.ceil(1 + i * .5) - 1 }, 0));
    },
    none() {},
  };
  (DECO[T.deco] || DECO.none)();
  // estilo premium: moldura fina em degradê que se desenha, um brilho que percorre a borda e uma grade de pontos no canto
  const PREMIUM = T.skin === 'premium';
  if (PREMIUM) {
    const m = PORT ? 26 : 22, r = PORT ? 30 : 24;
    const fr = el('div', 'frm', `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><defs><linearGradient id="frg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="${PALD[0]}" stop-opacity=".95"/><stop offset=".35" stop-color="${T.fg}" stop-opacity=".14"/>
      <stop offset=".7" stop-color="${T.fg}" stop-opacity=".14"/><stop offset="1" stop-color="${PALD[1] || PALD[0]}" stop-opacity=".9"/></linearGradient></defs>
      <rect x="${m}" y="${m}" width="${W - 2 * m}" height="${H - 2 * m}" rx="${r}" fill="none" stroke="url(#frg)" stroke-width="1.6"/></svg>`);
    stage.appendChild(fr);
    const rect = fr.querySelector('rect'), len = rect.getTotalLength();
    gsap.set(rect, { strokeDasharray: len, strokeDashoffset: len });
    tl.to(rect, { strokeDashoffset: 0, duration: 2.4, ease: 'power2.inOut' }, .1);
    const glow = el('div', 'frm-glow'); glow.style.setProperty('--c', PALD[0]); fr.appendChild(glow);
    const go = { p: 0 };
    gsap.set(glow, { autoAlpha: 0 });
    tl.to(glow, { autoAlpha: 1, duration: .6 }, 2.2);
    tl.to(go, { p: Math.max(1, Math.round(S.duration / 14)), duration: S.duration, ease: 'none' }, 0);
    FRAME.push(() => { const pt = rect.getPointAtLength((go.p % 1) * len); glow.style.transform = `translate(${pt.x}px,${pt.y}px)`; });
    const dg = el('div', 'dgrid'); Object.assign(dg.style, { right: m + 26 + 'px', top: m + 26 + 'px' });
    for (let i = 0; i < 36; i++) dg.appendChild(el('i'));
    fr.appendChild(dg);
    gsap.set(dg.children, { scale: 0 });
    tl.to(dg.children, { scale: 1, duration: .5, ease: 'back.out(3)', stagger: { each: .02, grid: [6, 6], from: 'end' } }, 1.2);
  }
  // a decoração some no fecho para o logo respirar
  tl.to(decoL, { autoAlpha: .35, duration: .8 }, S.outro.at);

  // foto de fundo de uma cena (referência enviada ou banco de imagens), com zoom lento
  function scenePhoto(sc, t0, t1, strong) {
    const ref = S.refs && S.refs[sc.photo]; if (!ref) return;
    const ph = el('div', 'ph'); ph.innerHTML = `<i style="background-image:url(${ref.src})"></i>`;
    stage.insertBefore(ph, decoL.nextSibling);
    const img = ph.firstChild;
    gsap.set(ph, { autoAlpha: 0 });
    tl.to(ph, { autoAlpha: 1, duration: .7, ease: 'power2.out' }, t0 - .25);
    tl.fromTo(img, strong ? { scale: 1.38, xPercent: -4, yPercent: 3 } : { scale: 1.16, xPercent: -2 },
      { scale: strong ? 1.04 : 1.02, xPercent: strong ? 3 : 2, yPercent: 0, duration: t1 - t0 + .6, ease: strong ? 'power1.out' : 'none', immediateRender: false }, t0 - .25);
    tl.to(ph, { autoAlpha: 0, duration: .5, ease: 'power2.in' }, t1 - .45);
  }
  // ilustração colorida (estilo figurinha) que entra girando e flutua
  function sceneSticker(sc, t0, t1, at) {
    const svg = S.stickers && S.stickers[sc.sticker]; if (!svg) return;
    const z = PORT ? 250 : 230;
    const s = el('div', 'stk', svg);
    Object.assign(s.style, { width: z + 'px', height: z + 'px', left: at.x - z / 2 + 'px', top: at.y - z / 2 + 'px' });
    stage.insertBefore(s, anchor);
    gsap.set(s, { scale: 0, rotation: -25, autoAlpha: 0 });
    tl.to(s, { scale: 1, rotation: 0, autoAlpha: 1, duration: .9, ease: 'back.out(1.8)' }, t0 + .5);
    tl.to(s, { y: -18, rotation: 6, duration: Math.max(1, (t1 - t0 - 1.6) / 2), ease: 'sine.inOut', yoyo: true, repeat: 1 }, t0 + 1.3);
    tl.to(s, { scale: .4, autoAlpha: 0, rotation: 20, duration: .4, ease: 'power3.in' }, t1 - .5);
  }
  // área útil no vertical (abaixo do logo do canto, acima da barra de progresso)
  const PB = { top: 230, bottom: 1780, gap: 60 };
  function contentBox(root, maxH) {  // altura real do conteúdo dentro do slot (antes das animações)
    const sc = stage.getBoundingClientRect().height / H, r0 = root.getBoundingClientRect();
    let t = Infinity, b = -Infinity;
    root.querySelectorAll('*').forEach(e => {
      const r = e.getBoundingClientRect(); if (r.width < 2 || r.height < 2 || r.height / sc > maxH * .95) return;  // ignora contêineres do tamanho do slot
      t = Math.min(t, r.top); b = Math.max(b, r.bottom);
    });
    if (t === Infinity) return { top: 0, bottom: maxH };
    return { top: clamp((t - r0.top) / sc, 0, maxH), bottom: clamp((b - r0.top) / sc, 0, maxH) };
  }

  // logo
  const PAL = T.palette || [T.acc, T.fg, T.muted];
  PAL.forEach((c, i) => rs.setProperty('--p' + (i + 1), c));
  const PLATE = S.brand.plate;  // logo com cores escuras da marca: aparece sobre fundo claro
  if (PLATE) rs.setProperty('--plate', PLATE);
  const lb = fitBox(S.brand.logoW, S.brand.logoH, L.logo.w, L.logo.h);
  function makeLogo() {
    const n = el('div', 'logo' + (PLATE ? ' plated' : ''));
    Object.assign(n.style, { left: L.logo.cx - lb.w / 2 + 'px', top: L.logo.cy - lb.h / 2 + 'px', width: lb.w + 'px', height: lb.h + 'px' });
    n.appendChild(el('div', 'lart'));
    return n;
  }

  /* Efeitos de entrada do logo. Cada um recebe o nó do logo (com .lart no estado final), cria as camadas
   * temporárias, esconde a arte e devolve o instante em que o logo está completo. No fim a arte original
   * volta sozinha, então o logo final é sempre nítido e sem emendas. */
  const layer = (n, cls) => n.appendChild(el('div', cls));
  const artOf = n => n.querySelector('.lart');
  function sweep(tl, n, t) {
    const s = layer(n, 'shine');
    tl.fromTo(s, { backgroundPosition: '120% 0' }, { backgroundPosition: '-20% 0', duration: 1, ease: 'power2.inOut', immediateRender: false }, t);
  }
  function burst(tl, t, k = 1) {
    const f = el('div', 'flash'); Object.assign(f.style, { left: L.logo.cx - 400 + 'px', top: L.logo.cy - 400 + 'px' }); stage.appendChild(f);
    tl.set(f, { autoAlpha: .9 * k, scale: .3 }, t);
    tl.to(f, { autoAlpha: 0, scale: 1.6, duration: 1.1, ease: 'power2.out' }, t);
  }
  function ring(n, color, size) {
    const r = layer(n, 'lring'); const d = size || Math.max(lb.w, lb.h) * 1.1;
    Object.assign(r.style, { width: d + 'px', height: d + 'px', margin: -d / 2 + 'px 0 0 ' + -d / 2 + 'px', borderColor: color });
    return r;
  }
  function converge(tl, t) {  // partículas que voam até o logo
    const fx = el('div', 'fx'); stage.appendChild(fx);
    const parts = [];
    for (let i = 0; i < 46; i++) {
      const p = el('span', T.particles === 'bits' ? 'bit mn' : 'pk', T.particles === 'bits' ? (rnd() > .5 ? '1' : '0') : null);
      const a = rnd() * Math.PI * 2, d = 700 + rnd() * 500, ox = L.logo.cx + Math.cos(a) * d, oy = L.logo.cy + Math.sin(a) * d * .6;
      p.style.left = ox + 'px'; p.style.top = oy + 'px';
      if (T.particles !== 'bits') p.style.background = PAL[i % 3];
      p._tx = L.logo.cx - lb.w / 2 + rnd() * lb.w - ox; p._ty = L.logo.cy - lb.h / 2 + rnd() * lb.h - oy; p._r = rnd() * 180;
      fx.appendChild(p); parts.push(p);
    }
    gsap.set(parts, { autoAlpha: 0, rotation: i => T.particles === 'bits' ? 0 : parts[i]._r });
    tl.to(parts, { autoAlpha: 1, duration: .2, stagger: { each: .01, from: 'random' } }, t);
    tl.to(parts, { x: i => parts[i]._tx, y: i => parts[i]._ty, duration: 1.5, ease: 'expo.inOut', stagger: { each: .012, from: 'random' } }, t + .05);
    tl.to(parts, { autoAlpha: 0, scale: .3, duration: .3, stagger: { each: .008, from: 'random' } }, t + 1.6);
  }
  const REVEAL = {
    // foco: nasce desfocado e esticado, com um brilho que se apaga
    blur(tl, n, t) {
      const a = artOf(n), g = layer(n, 'lglow');
      gsap.set(a, { autoAlpha: 0, scale: 1.3, scaleX: 1.45, filter: 'blur(40px)' });
      gsap.set(g, { autoAlpha: 0 });
      tl.to(g, { autoAlpha: .9, duration: .5, ease: 'power2.out' }, t);
      tl.to(g, { autoAlpha: 0, scale: 1.15, duration: 1.2, ease: 'power2.inOut' }, t + .6);
      tl.to(a, { autoAlpha: 1, scale: 1, scaleX: 1, filter: 'blur(0px)', duration: 1.7, ease: 'expo.out' }, t);
      tl.set(a, { filter: 'none' }, t + 1.75);
      sweep(tl, n, t + 1.3);
      return t + 1.9;
    },
    // traço: o contorno se desenha e depois a cor preenche (precisa do logo em SVG)
    draw(tl, n, t) {
      if (!S.brand.svg) return REVEAL.wipe(tl, n, t);
      const a = artOf(n), box = layer(n, 'lsvg');
      box.innerHTML = S.brand.svg;
      const svg = box.querySelector('svg');
      svg.setAttribute('preserveAspectRatio', 'none');
      const vb = svg.viewBox.baseVal, sw = 3.4 * (vb.width / lb.w);
      const paths = [...svg.querySelectorAll('path')];
      const xs = paths.map(p => {
        try { const b = p.getBBox(), m = p.transform.baseVal.consolidate(); return (b.x + (m ? m.matrix.e : 0)) / vb.width; } catch (e) { return rnd(); }
      });
      paths.forEach(p => {
        const len = p.getTotalLength() || 1;
        Object.assign(p.style, { stroke: PLATE ? p.getAttribute('fill') : PAL[0], strokeWidth: sw, strokeLinejoin: 'round',
          strokeDasharray: len, strokeDashoffset: len, fillOpacity: 0 });
      });
      gsap.set(a, { autoAlpha: 0 });
      const dl = i => clamp(xs[i], 0, 1) * .7;
      tl.to(paths, { strokeDashoffset: 0, duration: 1.2, ease: 'power2.inOut', stagger: i => dl(i) }, t);
      tl.to(paths, { fillOpacity: 1, duration: .6, ease: 'power1.out', stagger: i => dl(i) * .6 }, t + 1.05);
      tl.to(paths, { strokeOpacity: 0, duration: .5, ease: 'power1.in' }, t + 1.75);
      tl.set(a, { autoAlpha: 1 }, t + 2.25); tl.set(box, { autoAlpha: 0 }, t + 2.25);
      return t + 2.25;
    },
    // blocos com as cores da paleta passam e deixam o logo
    wipe(tl, n, t) {
      const a = artOf(n), b2 = layer(n, 'lblock'), b1 = layer(n, 'lblock');
      b1.style.background = PAL[0]; b2.style.background = PAL[1];
      gsap.set([b1, b2], { scaleX: 0, transformOrigin: '0% 50%' });
      gsap.set(a, { autoAlpha: 0, x: -40 });
      tl.to(b2, { scaleX: 1, duration: .55, ease: 'expo.inOut' }, t);
      tl.to(b1, { scaleX: 1, duration: .55, ease: 'expo.inOut' }, t + .1);
      tl.set([b1, b2], { transformOrigin: '100% 50%' }, t + .66);
      tl.set(a, { autoAlpha: 1 }, t + .66);
      tl.to(a, { x: 0, duration: 1, ease: 'expo.out' }, t + .66);
      tl.to(b1, { scaleX: 0, duration: .6, ease: 'expo.inOut' }, t + .68);
      tl.to(b2, { scaleX: 0, duration: .6, ease: 'expo.inOut' }, t + .78);
      sweep(tl, n, t + 1.3);
      return t + 1.8;
    },
    // fatias horizontais entram de lados alternados
    slices(tl, n, t) {
      const a = artOf(n), N = clamp(Math.round(lb.h / 40), 5, 10), sl = [];
      for (let i = 0; i < N; i++) {
        const d = layer(n, 'lslice');
        d.style.clipPath = `inset(${Math.max(0, i / N * 100 - .4)}% 0 ${Math.max(0, 100 - (i + 1) / N * 100 - .4)}% 0)`;
        sl.push(d);
      }
      gsap.set(a, { autoAlpha: 0 });
      gsap.set(sl, { x: i => (i % 2 ? 1 : -1) * lb.w * .7, skewX: i => (i % 2 ? -18 : 18), autoAlpha: 0 });
      tl.to(sl, { x: 0, skewX: 0, autoAlpha: 1, duration: 1.1, ease: 'expo.out', stagger: { each: .06, from: 'center' } }, t);
      tl.set(a, { autoAlpha: 1 }, t + 1.55); tl.set(sl, { autoAlpha: 0 }, t + 1.55);
      sweep(tl, n, t + 1.3);
      return t + 1.7;
    },
    // falha digital: cópias coloridas tremem até o logo estabilizar
    glitch(tl, n, t) {
      const a = artOf(n), r = layer(n, 'lmask'), b = layer(n, 'lmask');
      r.style.background = PAL[1]; b.style.background = PAL[2];
      gsap.set([a, r, b], { autoAlpha: 0 });
      const steps = 16, dt = .05, cut = () => `inset(${(rnd() * 70).toFixed(1)}% 0 ${(rnd() * 25).toFixed(1)}% 0)`;
      for (let k = 0; k < steps; k++) {
        const tt = t + k * dt, calm = k / steps;
        tl.set(r, { autoAlpha: rnd() > .25 ? .85 : 0, x: (rnd() - .5) * 70 * (1 - calm), clipPath: cut() }, tt);
        tl.set(b, { autoAlpha: rnd() > .3 ? .85 : 0, x: (rnd() - .5) * 70 * (1 - calm), clipPath: cut() }, tt);
        tl.set(a, { autoAlpha: calm > .35 && rnd() > .3 ? 1 : 0, x: (rnd() - .5) * 26 * (1 - calm), skewX: (rnd() - .5) * 12 * (1 - calm) }, tt);
      }
      const te = t + steps * dt;
      tl.set(a, { autoAlpha: 1, x: 0, skewX: 0 }, te); tl.set([r, b], { autoAlpha: 0 }, te);
      tl.set(r, { autoAlpha: .8, x: 16, clipPath: 'inset(42% 0 44% 0)' }, te + .5); tl.set(r, { autoAlpha: 0 }, te + .56);
      tl.set(a, { x: -6 }, te + .5); tl.set(a, { x: 0 }, te + .56);
      return te + .6;
    },
    // mosaico: quadradinhos surgem em ordem aleatória
    pixel(tl, n, t) {
      const a = artOf(n), grid = layer(n, 'lgrid'), cell = Math.max(lb.w, lb.h) / 26, cells = [];
      for (let y = 0; y < lb.h; y += cell) for (let x = 0; x < lb.w; x += cell) {
        const d = el('i');
        Object.assign(d.style, { left: x + 'px', top: y + 'px', width: cell + .6 + 'px', height: cell + .6 + 'px',
          backgroundSize: `${lb.w}px ${lb.h}px`, backgroundPosition: `${-x}px ${-y}px` });
        grid.appendChild(d); cells.push(d);
      }
      gsap.set(a, { autoAlpha: 0 }); gsap.set(cells, { autoAlpha: 0, scale: 0 });
      tl.to(cells, { autoAlpha: 1, scale: 1, duration: .35, ease: 'back.out(2.2)', stagger: { each: 1.1 / cells.length, from: 'random' } }, t);
      tl.set(a, { autoAlpha: 1 }, t + 1.5); tl.set(grid, { autoAlpha: 0 }, t + 1.5);
      burst(tl, t + 1.45, .6);
      sweep(tl, n, t + 1.5);
      return t + 1.9;
    },
    // íris: abre em círculo a partir do centro, com anéis da paleta
    iris(tl, n, t) {
      const a = artOf(n), r1 = ring(n, PAL[0]), r2 = ring(n, PAL[1]);
      gsap.set(a, { clipPath: 'circle(0% at 50% 50%)' }); gsap.set([r1, r2], { scale: 0, autoAlpha: 1 });
      tl.to(r1, { scale: 1.25, duration: 1.2, ease: 'expo.out' }, t);
      tl.to(r2, { scale: 1.5, duration: 1.3, ease: 'expo.out' }, t + .12);
      tl.to([r1, r2], { autoAlpha: 0, duration: .6, stagger: .1 }, t + .7);
      tl.to(a, { clipPath: 'circle(75% at 50% 50%)', duration: 1.3, ease: 'expo.inOut' }, t + .1);
      tl.set(a, { clipPath: 'none' }, t + 1.45);
      sweep(tl, n, t + 1.3);
      return t + 1.75;
    },
    // estilhaços se juntam, com partículas
    shatter(tl, n, t) {
      const a = artOf(n);
      const sh = shards(n, clamp(Math.round(lb.w / 110), 4, 12), clamp(Math.round(lb.h / 110), 3, 8), () => el('div', 'shard'));
      sh.forEach(s => s._dl = (s._cx / 100) * .6 + rnd() * .35);
      gsap.set(a, { autoAlpha: 0 }); gsap.set(sh, scatter(sh));
      tl.to(sh, { x: 0, y: 0, rotation: 0, scale: 1, autoAlpha: 1, duration: 1.4, ease: 'expo.out', stagger: i => sh[i]._dl }, t);
      const te = t + 2.35;
      tl.set(a, { autoAlpha: 1 }, te); tl.set(sh, { autoAlpha: 0 }, te);
      converge(tl, t + .1);
      burst(tl, t + 1.7);
      sweep(tl, n, te - .4);
      return te;
    },
    // impacto: cai como um carimbo, com tremida e onda de choque
    impact(tl, n, t) {
      const a = artOf(n), r = ring(n, PAL[0]);
      gsap.set(a, { autoAlpha: 0, scale: 2.6, filter: 'blur(14px)' }); gsap.set(r, { scale: .5, autoAlpha: 0 });
      tl.to(a, { autoAlpha: 1, scale: 1, filter: 'blur(0px)', duration: .42, ease: 'power4.in' }, t + .3);
      tl.set(a, { filter: 'none' }, t + .73);
      tl.fromTo(a, { x: -16, y: 8 }, { x: 0, y: 0, duration: .6, ease: 'elastic.out(1,.3)', immediateRender: false }, t + .72);
      tl.set(r, { autoAlpha: 1 }, t + .72);
      tl.to(r, { scale: 1.9, autoAlpha: 0, duration: .9, ease: 'expo.out' }, t + .72);
      burst(tl, t + .72);
      sweep(tl, n, t + 1);
      return t + 1.5;
    },
  };
  const RV = S.brand.reveal || { intro: 'blur', outro: 'wipe' };
  const reveal = (name, n, t) => (REVEAL[name] || REVEAL.blur)(tl, n, t);

  const logo = makeLogo();
  stage.insertBefore(logo, anchor.nextSibling);
  const cs = Math.min(L.corner.w / lb.w, L.corner.h / lb.h);
  const dx = L.corner.x + lb.w * cs / 2 - L.logo.cx, dy = L.corner.y + lb.h * cs / 2 - L.logo.cy;
  const ID = S.intro.dur, OA = S.outro.at;
  // echos primeiro (os clones copiam o logo completo), depois o efeito de entrada esconde as camadas
  echo(tl, logo, { x: 0, y: 0, scale: 1 }, { x: dx, y: dy, scale: cs, duration: .85, ease: 'expo.inOut' }, ID - .85);
  echo(tl, logo, { x: dx, y: dy, scale: cs, autoAlpha: 1 }, { y: dy - 26, autoAlpha: 0, duration: .45, ease: 'power2.in' }, OA);
  if (PLATE) {
    const pl = el('div', 'plate'); stage.insertBefore(pl, logo);
    const px = ((L.corner.x + lb.w * cs / 2) / W * 100).toFixed(1), py = ((L.corner.y + lb.h * cs / 2) / H * 100).toFixed(1);
    const cy = (L.logo.cy / H * 100).toFixed(1);
    tl.fromTo(pl, { clipPath: `circle(150% at 50% ${cy}%)` }, { clipPath: `circle(0% at ${px}% ${py}%)`, duration: .85, ease: 'expo.inOut', immediateRender: false }, ID - .85);
  }
  reveal(RV.intro, logo, .2);

  // cenas
  function bigWord(sc) {
    const u = sc.ui, t0 = sc.at, t1 = sc.at + sc.dur;
    const word = String(u.word || 'NÃO');
    const fs = Math.min(PORT ? 420 : 520, Math.floor(W * .86 / (word.length * .62)));
    const ov = el('div', 'bw-bg'); stage.insertBefore(ov, anchor);
    const pre = el('div', 'bw-pre', wordsHTML(u.pre || sc.headline || ''));
    const preFs = PORT ? 64 : 72;
    pre.style.fontSize = preFs + 'px';
    const wrap = el('div', 'bw-word'); const wh = fs * 1.15;
    const cy = H / 2 + (PORT ? 40 : 60);
    Object.assign(wrap.style, { top: cy - wh / 2 + 'px', height: wh + 'px' });
    pre.style.top = (cy - wh / 2 - preFs * 1.6) + 'px';
    stage.insertBefore(pre, anchor); stage.insertBefore(wrap, anchor);
    const solid = el('div', 'bw-t'); solid.textContent = word; solid.style.fontSize = fs + 'px'; wrap.appendChild(solid);
    const probe = el('span', '', esc(word)); probe.style.cssText = 'display:inline-block;white-space:nowrap'; solid.textContent = ''; solid.appendChild(probe);
    let fs2 = fs; while (probe.offsetWidth > W * .82 && fs2 > 60) { fs2 -= 8; solid.style.fontSize = fs2 + 'px'; }
    solid.textContent = word;
    const sh = shards(wrap, 7, 3, () => { const d = el('div', 'bw-t'); d.textContent = word; d.style.fontSize = fs2 + 'px'; return d; });
    gsap.set(solid, { autoAlpha: 0 });
    gsap.set(sh, { ...scatter(sh), scale: 1 });
    gsap.set(ov, { autoAlpha: 0 });
    tl.set(ov, { autoAlpha: 1 }, t0 - .15);
    tl.fromTo(ov, { clipPath: 'polygon(0% 0%,0% 0%,-30% 100%,-30% 100%)' }, { clipPath: 'polygon(0% 0%,130% 0%,100% 100%,-30% 100%)', duration: .55, ease: 'expo.inOut', immediateRender: false }, t0 - .15);
    const wis = pre.querySelectorAll('.wi'); gsap.set(wis, { yPercent: 150 });
    tl.to(wis, { yPercent: 0, duration: .8, stagger: .08 }, t0 + .25);
    tl.to(sh, { x: 0, y: 0, rotation: 0, autoAlpha: 1, duration: 1.1, ease: 'expo.out', stagger: { each: .015, from: 'random' } }, t0 + .7);
    tl.to(solid, { autoAlpha: 1, duration: .3, ease: 'none' }, t0 + 2.2);
    tl.to(wrap, { scale: 1.04, duration: Math.max(.5, sc.dur - 3.2), ease: 'none' }, t0 + 1.9);
    tl.set(solid, { autoAlpha: 0 }, t1 - 1.1);
    tl.to(sh, { x: i => sh[i]._fx * 1.4, y: i => sh[i]._fy * 1.4, rotation: i => -sh[i]._fr, autoAlpha: 0, duration: .8, ease: 'expo.in', stagger: { each: .01, from: 'center' } }, t1 - 1.1);
    tl.to(wis, { yPercent: -150, duration: .45, ease: 'power3.in', stagger: .04 }, t1 - 1.1);
    tl.to(ov, { clipPath: 'polygon(130% 0%,130% 0%,100% 100%,100% 100%)', duration: .6, ease: 'expo.inOut' }, t1 - .75);
  }

  /* ---------- entrada da headline: vários estilos de animação de texto ----------
   * Todos partem do DOM final (palavras .w > .wi) e criam só camadas temporárias, então o eco de saída
   * (clonado antes) continua mostrando o texto limpo. */
  const TFX = ['rise', 'bars', 'blur', 'type', 'split', 'marker', 'underline', 'scale', 'rotate', 'flip', 'kinetic', 'stack', 'wave', 'zoom', 'slice'];
  const SNAPPY = T.ease === 'snappy', DK = SNAPPY ? .82 : 1.15;  // personalidade da receita: cortes secos ou respirados
  function splitChars(h2) {  // quebra cada palavra em letras, levando o destaque (.acc) para cada letra
    const out = [];
    h2.querySelectorAll('.wi').forEach(wi => {
      const acc = wi.classList.contains('acc'); wi.classList.remove('acc');
      const txt = wi.textContent; wi.textContent = '';
      [...txt].forEach(c => { const s = el('span', 'ch' + (acc ? ' acc' : ''), esc(c)); wi.appendChild(s); out.push(s); });
    });
    return out;
  }
  function lines(h2) {  // agrupa as palavras por linha (posição vertical) para efeitos por linha
    const ws = [...h2.querySelectorAll('.w')], ls = [];
    ws.forEach(w => { const top = w.offsetTop; let l = ls.find(x => Math.abs(x.top - top) < 6); if (!l) ls.push(l = { top, ws: [] }); l.ws.push(w); });
    return ls.map(l => { const a = l.ws[0], b = l.ws[l.ws.length - 1];
      return { ws: l.ws, x: a.offsetLeft, y: l.top, w: b.offsetLeft + b.offsetWidth - a.offsetLeft, h: Math.max(...l.ws.map(w => w.offsetHeight)) }; });
  }
  const accWords = h2 => { const a = [...h2.querySelectorAll('.w')].filter(w => w.querySelector('.acc')); return a.length ? a : [...h2.querySelectorAll('.w')].slice(-1); };
  function textIn(h2, fx, t, cam) {
    const wis = h2.querySelectorAll('.wi');
    const ws = [...h2.querySelectorAll('.w')];
    if (fx === 'rotate') {  // palavras giram em 3D no eixo horizontal e encaixam
      h2.classList.add('fx-free');
      ws.forEach(w => { w.style.perspective = '700px'; });
      gsap.set(wis, { autoAlpha: 0, rotationX: -100, transformOrigin: '50% 50% -.4em' });
      tl.to(wis, { autoAlpha: 1, rotationX: 0, duration: .85 * DK, stagger: .08, ease: 'back.out(1.5)' }, t);
    } else if (fx === 'flip') {  // letras viram como placas
      h2.classList.add('fx-free');
      const ch = splitChars(h2);
      h2.querySelectorAll('.wi').forEach(wi => { wi.style.perspective = '600px'; });
      gsap.set(ch, { autoAlpha: 0, rotationY: -95, transformOrigin: '50% 50%' });
      tl.to(ch, { autoAlpha: 1, rotationY: 0, duration: .6 * DK, stagger: Math.min(.035, 1.2 / ch.length), ease: 'back.out(1.6)' }, t);
    } else if (fx === 'kinetic' && cam) {  // cada palavra sozinha e gigante no centro, depois a frase se monta
      const n = ws.length, step = (SNAPPY ? .3 : .38);
      ws.forEach((w, i) => {
        const txt = w.textContent, acc = !!w.querySelector('.acc');
        const fs = Math.min(PORT ? 300 : 340, Math.floor(W * .82 / Math.max(3, txt.length * .6)));
        const k = el('div', 'kin' + (acc ? ' acc' : ''), esc(txt)); k.style.fontSize = fs + 'px';
        cam.appendChild(k);
        gsap.set(k, { autoAlpha: 0 });
        const tt = t + i * step;
        tl.fromTo(k, { autoAlpha: 1, scale: 1.35 }, { scale: 1, duration: step, ease: 'power3.out', immediateRender: false }, tt);
        tl.set(k, { autoAlpha: 0 }, tt + step);
      });
      h2.classList.add('fx-free');
      gsap.set(wis, { autoAlpha: 0, scale: 1.5 });
      tl.to(wis, { autoAlpha: 1, scale: 1, duration: .5, stagger: .03, ease: 'expo.out' }, t + n * step);
    } else if (fx === 'stack') {  // palavras chegam em tamanhos alternados e se empilham no lugar
      h2.classList.add('fx-free');
      gsap.set(wis, { autoAlpha: 0, y: i => (i % 2 ? 1 : -1) * 70, scale: i => (i % 2 ? .55 : 1.6), transformOrigin: '0% 60%' });
      tl.to(wis, { autoAlpha: 1, y: 0, scale: 1, duration: .75 * DK, stagger: .1, ease: 'expo.out' }, t);
    } else if (fx === 'wave') {  // letras sobem em onda e ondulam uma vez
      h2.classList.add('fx-free');
      const ch = splitChars(h2);
      const each = Math.min(.035, 1.3 / ch.length);
      gsap.set(ch, { autoAlpha: 0, yPercent: 110 });
      tl.to(ch, { autoAlpha: 1, yPercent: 0, duration: .7 * DK, stagger: each, ease: 'sine.out' }, t);
      tl.to(ch, { yPercent: -14, duration: .28, yoyo: true, repeat: 1, stagger: each, ease: 'sine.inOut' }, t + .7 + ch.length * each);
    } else if (fx === 'zoom') {  // o texto vem de trás, atravessando a câmera
      h2.classList.add('fx-free');
      gsap.set(wis, { autoAlpha: 0, scale: 3.2, filter: 'blur(12px)', transformOrigin: '50% 55%' });
      tl.to(wis, { autoAlpha: 1, scale: 1, filter: 'blur(0px)', duration: .9 * DK, stagger: .06, ease: 'expo.out' }, t);
      tl.set(wis, { filter: 'none' }, t + 1 * DK + wis.length * .06);
    } else if (fx === 'slice') {  // cada palavra cortada ao meio: as metades entram de lados opostos
      h2.classList.add('fx-free');
      const tops = [], bots = [];
      ws.forEach(w => {
        const wi = w.querySelector('.wi'), b = wi.cloneNode(true);
        w.style.position = 'relative'; b.classList.add('wi2'); w.appendChild(b);
        wi.style.clipPath = 'inset(0 0 50% 0)'; b.style.clipPath = 'inset(50% 0 0 0)';
        tops.push(wi); bots.push(b);
      });
      gsap.set(tops, { autoAlpha: 0, x: -90 }); gsap.set(bots, { autoAlpha: 0, x: 90 });
      tl.to(tops, { autoAlpha: 1, x: 0, duration: .55 * DK, stagger: .05, ease: 'expo.out' }, t);
      tl.to(bots, { autoAlpha: 1, x: 0, duration: .55 * DK, stagger: .05, ease: 'expo.out' }, t + .06);
      const te = t + .7 * DK + ws.length * .05;
      tl.set(tops, { clipPath: 'inset(0 0 0% 0)' }, te); tl.set(bots, { autoAlpha: 0 }, te);
    } else if (fx === 'blur') {
      h2.classList.add('fx-free');
      gsap.set(wis, { autoAlpha: 0, filter: 'blur(16px)', y: 24, scale: 1.06 });
      tl.to(wis, { autoAlpha: 1, filter: 'blur(0px)', y: 0, scale: 1, duration: 1.1, stagger: .09, ease: 'power3.out' }, t);
      tl.set(wis, { filter: 'none' }, t + 1.2 + wis.length * .09);
    } else if (fx === 'scale') {
      h2.classList.add('fx-free');
      gsap.set(wis, { autoAlpha: 0, scale: 1.9, transformOrigin: '50% 70%' });
      tl.to(wis, { autoAlpha: 1, scale: 1, duration: .55, stagger: .08, ease: 'back.out(1.7)' }, t);
    } else if (fx === 'split') {
      h2.classList.add('fx-free');
      const ch = splitChars(h2);
      gsap.set(ch, { autoAlpha: 0, yPercent: -140, rotation: () => (rnd() - .5) * 70 });
      tl.to(ch, { autoAlpha: 1, yPercent: 0, rotation: 0, duration: .7, stagger: Math.min(.03, 1.1 / ch.length), ease: 'back.out(2)' }, t);
    } else if (fx === 'type') {
      h2.classList.add('fx-free');
      const ch = splitChars(h2), caret = el('span', 'caret');
      h2.appendChild(caret);
      const step = Math.min(.045, 1.6 / ch.length);
      gsap.set(ch, { autoAlpha: 0 });
      tl.to(ch, { autoAlpha: 1, duration: .01, stagger: step, ease: 'none' }, t);
      const te = t + ch.length * step;
      gsap.set(caret, { autoAlpha: 0 });
      tl.set(caret, { autoAlpha: 1 }, t);
      for (let k = 0; k < 4; k++) { tl.set(caret, { autoAlpha: 0 }, te + k * .5 + .25); tl.set(caret, { autoAlpha: 1 }, te + k * .5 + .5); }
      tl.set(caret, { autoAlpha: 0 }, te + 2.1);
    } else if (fx === 'bars') {
      h2.classList.add('fx-free');
      gsap.set(wis, { autoAlpha: 0 });
      lines(h2).forEach((l, i) => {
        const b = el('i', 'tbar'); Object.assign(b.style, { left: l.x - 8 + 'px', top: l.y + 'px', width: l.w + 16 + 'px', height: l.h + 'px', background: PALD[i % PALD.length] });
        h2.appendChild(b);
        const tt = t + i * .13;
        gsap.set(b, { scaleX: 0, transformOrigin: '0% 50%' });
        tl.to(b, { scaleX: 1, duration: .42, ease: 'expo.inOut' }, tt);
        tl.set(l.ws.map(w => w.querySelector('.wi')), { autoAlpha: 1 }, tt + .42);
        tl.set(b, { transformOrigin: '100% 50%' }, tt + .42);
        tl.to(b, { scaleX: 0, duration: .45, ease: 'expo.inOut' }, tt + .44);
      });
    } else {  // rise (padrão), marker e underline partem da subida por máscara
      gsap.set(wis, { yPercent: 150 });
      tl.to(wis, { yPercent: 0, duration: .9, stagger: .07 }, t);
      if (fx === 'marker' || fx === 'underline') {
        accWords(h2).forEach((w, i) => {
          const m = el('i', fx === 'marker' ? 'tmark' : 'tline');
          const r = { x: w.offsetLeft, y: w.offsetTop, w: w.offsetWidth, h: w.offsetHeight };
          if (fx === 'marker') Object.assign(m.style, { left: r.x - 6 + 'px', top: r.y + r.h * .52 + 'px', width: r.w + 12 + 'px', height: r.h * .36 + 'px' });
          else Object.assign(m.style, { left: r.x + 'px', top: r.y + r.h * .9 + 'px', width: r.w + 'px' });
          h2.insertBefore(m, h2.firstChild);
          gsap.set(m, { scaleX: 0, transformOrigin: '0% 50%' });
          tl.to(m, { scaleX: 1, duration: .7, ease: 'expo.inOut' }, t + .7 + i * .15);
        });
      }
    }
  }
  const pickFx = (sc, i) => TFX.includes(sc.text_fx) ? sc.text_fx : (T.textFx && TFX.includes(T.textFx) && rnd() < .5 ? T.textFx : TFX[Math.floor(rnd() * TFX.length)]);

  /* ---------- acabamento da cena: base do texto, ênfase, ornamentos, câmera ----------
   * Tudo é criado no estado final e escondido com gsap.set; as animações ficam na timeline (render = preview). */
  let DRESS = [];  // elementos extras da cena atual (somem junto com o texto)
  function posIn(e, root) {  // posição de e dentro de root, somando offsets (ignora transforms de animação)
    let x = 0, y = 0;
    for (let n = e; n && n !== root; n = n.offsetParent) { x += n.offsetLeft; y += n.offsetTop; }
    return { x, y };
  }
  const fsOf = h2 => parseFloat(h2.style.fontSize) || parseFloat(getComputedStyle(h2).fontSize) || 100;
  function swapWord(w, h2, at, cls) {  // cópia da palavra em outra cor, revelada por cima (não mexe no texto original)
    // classes próprias: a cópia não pode ser pega pelos efeitos de texto (que procuram .w/.wi)
    const c = el('span', 'tsw ' + cls, `<span class="twi">${esc(w.textContent)}</span>`);
    Object.assign(c.style, { left: w.offsetLeft + 'px', top: w.offsetTop + 'px', width: w.offsetWidth + 'px', height: w.offsetHeight + 'px' });
    h2.appendChild(c);
    gsap.set(c, { clipPath: 'inset(0% 100% 0% 0%)' });
    tl.to(c, { clipPath: 'inset(0% 0% 0% 0%)', duration: .5 * DK, ease: 'expo.inOut' }, at);
    return c;
  }
  function textBg(kind, h2, t) {
    if (!kind || kind === 'none' || kind === 'glass') return;
    const ls = lines(h2); if (!ls.length) return;
    const pad = fsOf(h2) * .16;
    if (kind === 'bar') {  // faixa sólida por linha, texto em tinta contrastante (estilo Reels)
      h2.classList.add('on-bar');
      ls.forEach((l, i) => {
        const b = el('i', 'tbg'); Object.assign(b.style, { left: l.x - pad + 'px', top: l.y + l.h * .06 + 'px', width: l.w + pad * 2 + 'px', height: l.h * .9 + 'px' });
        h2.insertBefore(b, h2.firstChild);
        gsap.set(b, { scaleX: 0, transformOrigin: '0% 50%' });
        tl.to(b, { scaleX: 1, duration: .5 * DK, ease: 'expo.inOut' }, t - .35 + i * .09);
      });
    } else if (kind === 'block') {  // um bloco único atrás da headline
      h2.classList.add('on-bar');
      const x0 = Math.min(...ls.map(l => l.x)), x1 = Math.max(...ls.map(l => l.x + l.w));
      const y0 = ls[0].y, y1 = ls[ls.length - 1].y + ls[ls.length - 1].h;
      const b = el('i', 'tbg blk'); Object.assign(b.style, { left: x0 - pad * 1.8 + 'px', top: y0 - pad * .8 + 'px', width: x1 - x0 + pad * 3.6 + 'px', height: y1 - y0 + pad * 1.6 + 'px' });
      h2.insertBefore(b, h2.firstChild);
      gsap.set(b, { clipPath: 'inset(0% 100% 0% 0%)' });
      tl.to(b, { clipPath: 'inset(0% 0% 0% 0%)', duration: .6 * DK, ease: 'expo.inOut' }, t - .4);
    } else if (kind === 'highlight') {  // faixa sólida só na palavra-chave
      accWords(h2).forEach((w, i) => swapWord(w, h2, t + .55 + i * .12, 'tsw-acc'));
    } else if (kind === 'outline') {  // contorno fino com cantos arredondados em volta do texto
      const x0 = Math.min(...ls.map(l => l.x)), x1 = Math.max(...ls.map(l => l.x + l.w));
      const y0 = ls[0].y, y1 = ls[ls.length - 1].y + ls[ls.length - 1].h;
      const o = el('i', 'tbg-ol'); Object.assign(o.style, { left: x0 - pad * 2 + 'px', top: y0 - pad * 1.2 + 'px', width: x1 - x0 + pad * 4 + 'px', height: y1 - y0 + pad * 2.4 + 'px' });
      h2.insertBefore(o, h2.firstChild);
      gsap.set(o, { autoAlpha: 0, scale: 1.08 });
      tl.to(o, { autoAlpha: 1, scale: 1, duration: .9 * DK, ease: 'expo.out' }, t + .3);
    }
  }
  function glassBand(hl, box, t0, t1) {  // faixa de vidro atrás do texto, do tamanho do conteúdo
    const h0 = hl.style.height; hl.style.height = 'auto'; const ch = hl.offsetHeight; hl.style.height = h0;
    const top = parseFloat(hl.style.top) + (box.justify === 'center' ? (parseFloat(h0) - ch) / 2 : 0);
    const g = el('div', 'gband'); Object.assign(g.style, { left: box.x - 46 + 'px', top: top - 40 + 'px', width: box.w + 92 + 'px', height: ch + 80 + 'px' });
    hl.parentNode.insertBefore(g, hl);
    gsap.set(g, { autoAlpha: 0, scale: .96 });
    tl.to(g, { autoAlpha: 1, scale: 1, duration: .7, ease: 'expo.out' }, t0 - .15);
    tl.to(g, { autoAlpha: 0, duration: .45, ease: 'power2.in' }, t1 - .5);
    return g;
  }
  function emphasize(kind, h2, te) {
    if (!kind || kind === 'none' || !h2.querySelector('.acc')) return;
    const ws = accWords(h2), wis = ws.map(w => w.querySelector('.wi'));
    const fs = fsOf(h2), onBar = h2.classList.contains('on-bar');
    tl.set(ws, { overflow: 'visible' }, te - .02);
    if (kind === 'pop') tl.to(wis, { scale: 1.2, duration: .2, yoyo: true, repeat: 1, ease: 'power2.out', stagger: .08 }, te);
    else if (kind === 'spin') { gsap.set(wis, { transformOrigin: '50% 55%' }); tl.to(wis, { rotation: '+=360', duration: .9, ease: 'back.inOut(1.3)', stagger: .1 }, te); }
    else if (kind === 'glow') {
      tl.to(wis, { filter: `drop-shadow(0 0 ${Math.round(fs * .22)}px ${T.accGlow || T.acc})`, duration: .55, yoyo: true, repeat: 3, ease: 'sine.inOut' }, te);
      tl.set(wis, { filter: 'none' }, te + 2.25);
    } else if (kind === 'color_swap') ws.forEach((w, i) => swapWord(w, h2, te + i * .1, 'tsw-inv'));
    else ws.forEach((w, i) => {
      const r = { x: w.offsetLeft, y: w.offsetTop, w: w.offsetWidth, h: w.offsetHeight }, at = te + i * .12;
      if (kind === 'circle') {  // círculo desenhado à mão em volta da palavra
        const px = fs * .32, W2 = r.w + px * 2, H2 = r.h + px * 1.1;
        const c = el('div', 'tem-c' + (onBar ? ' ink' : ''), `<svg width="${W2}" height="${H2}" viewBox="0 0 ${W2} ${H2}" overflow="visible"><path pathLength="1" d="M${W2 * .56} ${H2 * .04} C ${W2 * 1.04} ${H2 * .02}, ${W2 * 1.02} ${H2 * .98}, ${W2 * .5} ${H2 * .97} C ${-W2 * .04} ${H2 * .96}, ${-W2 * .02} ${H2 * .06}, ${W2 * .62} ${H2 * .1}" fill="none" stroke-width="${Math.max(4, fs * .045)}" stroke-linecap="round"/></svg>`);
        Object.assign(c.style, { left: r.x - px + 'px', top: r.y - px * .55 + 'px' });
        h2.appendChild(c);
        const p = c.querySelector('path'); gsap.set(p, { strokeDasharray: 1, strokeDashoffset: 1 });
        tl.to(p, { strokeDashoffset: 0, duration: .75, ease: 'power2.inOut' }, at);
      } else if (kind === 'strike' || kind === 'underline_draw') {
        const s = el('i', kind === 'strike' ? 'tem-s' : 'tline');
        const sh = Math.max(6, fs * .09);
        if (kind === 'strike') Object.assign(s.style, { left: r.x - fs * .06 + 'px', top: r.y + r.h * .54 - sh / 2 + 'px', width: r.w + fs * .12 + 'px', height: sh + 'px' });
        else Object.assign(s.style, { left: r.x + 'px', top: r.y + r.h * .88 + 'px', width: r.w + 'px', height: Math.max(8, fs * .11) + 'px' });
        if (onBar) s.classList.add('ink');
        h2.appendChild(s);
        gsap.set(s, { scaleX: 0, transformOrigin: '0% 50%' });
        tl.to(s, { scaleX: 1, duration: .5, ease: 'expo.inOut' }, at);
      }
    });
  }
  function focal(h2, cam) {  // ponto focal da cena: a palavra destacada (ou o centro da headline)
    const w = accWords(h2)[0] || h2, p = posIn(w, cam);
    return { x: p.x + w.offsetWidth / 2, y: p.y + w.offsetHeight / 2, w: w.offsetWidth, h: w.offsetHeight };
  }
  function ornament(kind, sc, idx, hl, h2, cam, slot, t0, t1) {
    if (!kind || kind === 'none') return;
    const f = focal(h2, cam), d = t1 - t0;
    const add = (e, x, y, z) => { Object.assign(e.style, { left: x - z / 2 + 'px', top: y - z / 2 + 'px', width: z + 'px', height: z + 'px' }); cam.insertBefore(e, cam.firstChild); DRESS.push(e); return e; };
    if (kind === 'spin_ring') {  // anel tracejado girando atrás da palavra-chave
      const z = clamp(Math.max(f.w, f.h) * 1.6, 180, PORT ? 760 : 680);
      const r = add(el('div', 'orn-ring', `<svg viewBox="0 0 200 200" width="100%" height="100%"><circle cx="100" cy="100" r="96" fill="none" stroke="${PALD[0]}" stroke-width="1.6" stroke-dasharray="14 9 3 9"/><circle cx="100" cy="100" r="82" fill="none" stroke="${PALD[1] || PALD[0]}" stroke-width=".8" stroke-dasharray="2 5"/></svg>`), f.x, f.y, z);
      gsap.set(r, { scale: 0, rotation: -120, autoAlpha: 0 });
      tl.to(r, { scale: 1, rotation: 0, autoAlpha: .9, duration: 1.1 * DK, ease: 'expo.out' }, t0 + .25);
      tl.to(r, { rotation: '+=' + (60 + 40 * d), duration: d, ease: 'none' }, t0 + 1.2);
    } else if (kind === 'orbit_dots') {  // pontos orbitando a palavra-chave numa elipse
      const R = clamp(f.w * .7, 120, 520), o = add(el('div', 'orn-orb'), f.x, f.y, R * 2);
      const spin = el('div', 'orn-orb-in'); o.appendChild(spin);
      for (let k = 0; k < 5; k++) { const dot = el('i'); const a = k / 5 * Math.PI * 2, z = 10 + (k % 3) * 6;
        Object.assign(dot.style, { left: R + Math.cos(a) * R - z / 2 + 'px', top: R + Math.sin(a) * R - z / 2 + 'px', width: z + 'px', height: z + 'px', background: PALD[k % PALD.length] }); spin.appendChild(dot); }
      gsap.set(o, { scaleY: .34, rotation: -10, autoAlpha: 0 });
      tl.to(o, { autoAlpha: 1, duration: .6 }, t0 + .4);
      tl.fromTo(spin, { rotation: 0 }, { rotation: 360 * Math.max(1, Math.round(d / 3)), duration: d, ease: 'none', immediateRender: false }, t0 + .4);
    } else if (kind === 'rotating_badge') {  // selo circular com texto girando
      const z = PORT ? 210 : 180;
      let x, y;
      if (slot) { x = parseFloat(slot.style.left) + parseFloat(slot.style.width) - z * .35; y = parseFloat(slot.style.top) + z * .3; }
      else { const ls = lines(h2), p = posIn(h2, cam); x = p.x + Math.max(...ls.map(l => l.x + l.w)) + z * .45; y = p.y + ls[0].y - z * .15;
        x = clamp(x, z, W - z * .7); y = clamp(y, z * .7, H - z); }
      const b = add(stampSVG(sc.eyebrow || BRAND.name || 'novo'), x, y, z); b.classList.add('orn-badge');
      gsap.set(b, { scale: 0, rotation: -200 });
      tl.to(b, { scale: 1, rotation: 0, duration: .9, ease: 'back.out(1.6)' }, t0 + .7);
      tl.to(b, { rotation: '+=' + 50 * d, duration: d, ease: 'none' }, t0 + 1.6);
    } else if (kind === 'corner_brackets') {  // cantoneiras que emolduram a headline
      const ls = lines(h2), p = posIn(h2, cam), pad = fsOf(h2) * .38;
      const x0 = p.x + Math.min(...ls.map(l => l.x)) - pad, x1 = p.x + Math.max(...ls.map(l => l.x + l.w)) + pad;
      const y0 = p.y + ls[0].y - pad * .7, y1 = p.y + ls[ls.length - 1].y + ls[ls.length - 1].h + pad * .7;
      [[x0, y0, 'tl'], [x1, y0, 'tr'], [x1, y1, 'br'], [x0, y1, 'bl']].forEach(([x, y, c], k) => {
        const e = el('i', 'orn-br ' + c); Object.assign(e.style, { left: x + 'px', top: y + 'px' }); cam.appendChild(e); DRESS.push(e);
        gsap.set(e, { autoAlpha: 0, x: (c[1] === 'l' ? -1 : 1) * 40, y: (c[0] === 't' ? -1 : 1) * 40 });
        tl.to(e, { autoAlpha: 1, x: 0, y: 0, duration: .8 * DK, ease: 'expo.out' }, t0 + .35 + k * .05);
      });
    } else if (kind === 'big_number_bg' && !slot) {  // número da cena gigante e vazado ao fundo
      const n = el('div', 'orn-num', String(idx + 1).padStart(2, '0'));
      n.style.fontSize = (PORT ? W * .62 : H * .78) + 'px';
      Object.assign(n.style, PORT ? { right: '4%', bottom: '8%' } : { right: '3%', bottom: '-10%' });
      cam.insertBefore(n, cam.firstChild); DRESS.push(n);
      gsap.set(n, { autoAlpha: 0, yPercent: 18 });
      tl.to(n, { autoAlpha: 1, yPercent: 0, duration: 1.2 * DK, ease: 'expo.out' }, t0);
      tl.to(n, { yPercent: -6, duration: d, ease: 'none' }, t0 + 1.2);
    } else if (kind === 'grid_sweep') {  // faixa de grade que varre o fundo
      const g = el('div', 'orn-grid'); Object.assign(g.style, { width: W * .42 + 'px', height: H + 'px' });
      cam.insertBefore(g, cam.firstChild); DRESS.push(g);
      tl.fromTo(g, { x: -W * .45 }, { x: W * 1.05, duration: Math.max(2.2, d * .85), ease: 'power1.inOut', immediateRender: false }, t0);
    }
  }
  function camera(kind, cam, hl, slot, t0, t1, f) {
    if (!kind || kind === 'still') return;
    const d = t1 - t0, dir = rnd() < .5 ? -1 : 1;
    gsap.set(cam, { transformOrigin: `${f.x}px ${f.y}px` });
    if (kind === 'push_in') tl.fromTo(cam, { scale: 1 }, { scale: 1.07, duration: d + .3, ease: 'none', immediateRender: false }, t0 - .1);
    else if (kind === 'pull_out') tl.fromTo(cam, { scale: 1.13 }, { scale: 1, duration: d, ease: 'power2.out', immediateRender: false }, t0 - .1);
    else if (kind === 'drift') tl.fromTo(cam, PORT ? { y: 34 * dir } : { x: 40 * dir }, { x: 0, y: 0, ...(PORT ? { y: -34 * dir } : { x: -40 * dir }), duration: d + .3, ease: 'none', immediateRender: false }, t0 - .1);
    else if (kind === 'tilt') tl.fromTo(cam, { rotation: 4 * dir, scale: 1.05 }, { rotation: 0, scale: 1, duration: 1.4 * DK, ease: 'expo.out', immediateRender: false }, t0 - .05);
    else if (kind === 'spin_in') tl.fromTo(cam, { rotation: 90 * dir, scale: .6 }, { rotation: 0, scale: 1, duration: 1.05 * DK, ease: 'back.out(1.15)', immediateRender: false }, t0 - .05);
    else if (kind === 'shake') {
      const ts = t0 + .55;
      for (let k = 0; k < 8; k++) { const a = 1 - k / 8; tl.to(cam, { x: (rnd() - .5) * 34 * a, y: (rnd() - .5) * 20 * a, rotation: (rnd() - .5) * 1.6 * a, duration: .045, ease: 'none' }, ts + k * .045); }
      tl.to(cam, { x: 0, y: 0, rotation: 0, duration: .15, ease: 'power2.out' }, ts + .37);
    } else if (kind === 'parallax') {
      tl.fromTo(hl, { xPercent: 2 }, { xPercent: -2, duration: d, ease: 'none', immediateRender: false }, t0);
      if (slot) tl.fromTo(slot, { xPercent: -3 }, { xPercent: 3, duration: d, ease: 'none', immediateRender: false }, t0);
    }
  }

  /* ---------- transições entre cenas ----------
   * TRANS[nome](cenaAnterior | null, cenaNova, instante do corte). Camadas de cobertura ficam acima das cenas e abaixo do logo. */
  function cover(cls, bg) { const c = el('div', 'trc ' + (cls || '')); if (bg) c.style.background = bg; stage.insertBefore(c, anchor.nextSibling); gsap.set(c, { autoAlpha: 0 }); return c; }
  const hideAt = (o, tb) => { if (o) tl.set(o, { autoAlpha: 0 }, tb); };
  const TRANS = {
    cut(o, n, tb) { hideAt(o, tb); },
    fade() {},  // a saída com eco da cena anterior já faz o fade
    wipe(o, n, tb) {
      const c = cover('', PALD[0]); const k = .42 * DK;
      tl.set(c, { autoAlpha: 1 }, tb - k);
      tl.fromTo(c, { scaleX: 0, transformOrigin: '0% 50%' }, { scaleX: 1, duration: k, ease: 'expo.in', immediateRender: false }, tb - k);
      hideAt(o, tb);
      tl.set(c, { transformOrigin: '100% 50%' }, tb);
      tl.to(c, { scaleX: 0, duration: .5 * DK, ease: 'expo.out' }, tb + .02);
    },
    slide(o, n, tb) {
      tl.fromTo(n, PORT ? { y: H } : { x: W }, { x: 0, y: 0, duration: .75 * DK, ease: 'expo.out', immediateRender: false }, tb - .1);
      if (o) tl.to(o, { ...(PORT ? { y: -H * .2 } : { x: -W * .2 }), autoAlpha: 0, duration: .55 * DK, ease: 'power3.in' }, tb - .2);
    },
    push(o, n, tb) {
      const k = .62 * DK;
      tl.fromTo(n, PORT ? { y: H } : { x: W }, { x: 0, y: 0, duration: k, ease: 'expo.inOut', immediateRender: false }, tb - k * .55);
      if (o) { tl.to(o, { ...(PORT ? { y: -H } : { x: -W }), duration: k, ease: 'expo.inOut' }, tb - k * .55); hideAt(o, tb + k * .5); }
    },
    zoom(o, n, tb) {
      if (o) tl.to(o, { scale: 2.3, autoAlpha: 0, duration: .4 * DK, ease: 'power2.in' }, tb - .35);
      tl.fromTo(n, { scale: .55, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: .75 * DK, ease: 'expo.out', immediateRender: false }, tb - .05);
    },
    iris(o, n, tb) {
      if (o) tl.to(o, { autoAlpha: 0, duration: .4, ease: 'power2.in' }, tb - .25);
      tl.fromTo(n, { clipPath: 'circle(0% at 50% 50%)' }, { clipPath: 'circle(75% at 50% 50%)', duration: .85 * DK, ease: 'expo.inOut', immediateRender: false }, tb - .1);
      tl.set(n, { clipPath: 'none' }, tb + .8 * DK);
      const z = Math.hypot(W, H), ring = cover('trc-ring');
      Object.assign(ring.style, { width: z + 'px', height: z + 'px', left: (W - z) / 2 + 'px', top: (H - z) / 2 + 'px', borderColor: PALD[0] });
      tl.fromTo(ring, { scale: 0, autoAlpha: 1 }, { scale: 1, autoAlpha: 0, duration: .95 * DK, ease: 'expo.out', immediateRender: false }, tb - .1);
    },
    spin(o, n, tb) {
      const dir = rnd() < .5 ? -1 : 1;
      if (o) tl.to(o, { rotation: -70 * dir, scale: .5, autoAlpha: 0, duration: .42 * DK, ease: 'power3.in', transformOrigin: '50% 50%' }, tb - .38);
      tl.fromTo(n, { rotation: 70 * dir, scale: .5, autoAlpha: 0, transformOrigin: '50% 50%' }, { rotation: 0, scale: 1, autoAlpha: 1, duration: .8 * DK, ease: 'back.out(1.25)', immediateRender: false }, tb - .02);
    },
    blinds(o, n, tb) {
      const N = PORT ? 9 : 7, k = .4 * DK, wrap = cover('trc-bl');
      for (let j = 0; j < N; j++) { const s = el('i'); Object.assign(s.style, { top: j / N * 100 + '%', height: 100 / N + 0.2 + '%', background: j % 2 ? T.fg : PALD[0] }); wrap.appendChild(s); }
      const ss = wrap.children;
      tl.set(wrap, { autoAlpha: 1 }, tb - k - .2);
      tl.fromTo(ss, { scaleY: 0, transformOrigin: '50% 0%' }, { scaleY: 1, duration: k, stagger: .025, ease: 'expo.in', immediateRender: false }, tb - k - .15);
      hideAt(o, tb);
      tl.set(ss, { transformOrigin: '50% 100%' }, tb);
      tl.to(ss, { scaleY: 0, duration: k, stagger: .025, ease: 'expo.out' }, tb + .02);
      tl.set(wrap, { autoAlpha: 0 }, tb + k + .3);
    },
    flash(o, n, tb) {
      const c = cover('', LIGHT ? PALD[0] : '#FFFFFF');
      tl.to(c, { autoAlpha: LIGHT ? .9 : 1, duration: .12, ease: 'power2.in' }, tb - .12);
      hideAt(o, tb);
      tl.to(c, { autoAlpha: 0, duration: .55, ease: 'power2.out' }, tb);
      tl.fromTo(n, { scale: 1.08 }, { scale: 1, duration: .7, ease: 'expo.out', immediateRender: false }, tb);
    },
    glitch(o, n, tb) {
      const jit = (e, from, to) => { for (let k = 0; k < 6; k++) tl.set(e, { x: (rnd() - .5) * 60, skewX: (rnd() - .5) * 18 }, from + (to - from) * k / 6); tl.set(e, { x: 0, skewX: 0 }, to); };
      if (o) { jit(o, tb - .3, tb); hideAt(o, tb); }
      jit(n, tb, tb + .3);
      const c = cover('trc-gl');
      for (let k = 0; k < 7; k++) { const b = el('i'); Object.assign(b.style, { top: rnd() * 92 + '%', height: 1 + rnd() * 7 + '%', left: rnd() * 30 + '%', width: 40 + rnd() * 60 + '%', background: PALD[k % PALD.length] }); c.appendChild(b); }
      for (let k = 0; k < 6; k++) tl.set(c, { autoAlpha: k % 2 ? 0 : .85, x: (rnd() - .5) * 80 }, tb - .25 + k * .08);
      tl.set(c, { autoAlpha: 0 }, tb + .25);
    },
    match(o, n, tb) {  // a palavra-chave da cena anterior cresce até cobrir a tela
      const w = o && o.querySelector('.hl .acc');
      if (!w) return TRANS.zoom(o, n, tb);
      const ww = w.closest('.w') || w, p = posIn(ww, stage);
      const c = cover('trc-m', PALD[0]);
      Object.assign(c.style, { left: p.x + 'px', top: p.y + 'px', width: ww.offsetWidth + 'px', height: ww.offsetHeight + 'px' });
      const k = .5 * DK;
      tl.set(c, { autoAlpha: 1 }, tb - k);
      tl.fromTo(c, { left: p.x, top: p.y, width: ww.offsetWidth, height: ww.offsetHeight, borderRadius: 12 },
        { left: 0, top: 0, width: W, height: H, borderRadius: 0, duration: k, ease: 'expo.in', immediateRender: false }, tb - k);
      hideAt(o, tb);
      tl.to(c, { autoAlpha: 0, duration: .5, ease: 'power2.out' }, tb + .05);
      tl.fromTo(n, { scale: 1.1 }, { scale: 1, duration: .8, ease: 'expo.out', immediateRender: false }, tb);
    },
  };

  /* ---------- fotos em layouts: metade da tela com corte diagonal, cartão emoldurado, faixa de vidro ---------- */
  function photoSplit(sc, t0, t1) {
    const ref = S.refs && S.refs[sc.photo]; if (!ref) return;
    const ph = el('div', 'phs'); ph.innerHTML = `<i style="background-image:url(${ref.src})"></i><b></b>`;
    if (PORT) Object.assign(ph.style, { left: 0, top: 0, width: W + 'px', height: H * .5 + 'px', clipPath: 'polygon(0 0,100% 0,100% 82%,0 100%)' });
    else Object.assign(ph.style, { left: W * .46 + 'px', top: 0, width: W * .54 + 'px', height: H + 'px', clipPath: 'polygon(14% 0,100% 0,100% 100%,0 100%)' });
    stage.insertBefore(ph, decoL.nextSibling);
    const edge = ph.querySelector('b');
    const from = PORT ? 'polygon(0 0,100% 0,100% 0,0 0)' : 'polygon(100% 0,100% 0,100% 100%,100% 100%)';
    const to = ph.style.clipPath;
    gsap.set(ph, { clipPath: from });
    tl.to(ph, { clipPath: to, duration: .9, ease: 'expo.inOut' }, t0 - .2);
    tl.fromTo(ph.firstChild, { scale: 1.2 }, { scale: 1.04, duration: t1 - t0 + .4, ease: 'none', immediateRender: false }, t0 - .2);
    tl.to(ph, { clipPath: from, duration: .6, ease: 'expo.in' }, t1 - .6);
  }
  function photoCard(sc, t0, t1, box) {
    const ref = S.refs && S.refs[sc.photo]; if (!ref) return null;
    let w = box.w, h = w / (ref.ar || 1.5);
    if (h > box.h) { h = box.h; w = h * (ref.ar || 1.5); }
    const c = el('div', 'phc');
    Object.assign(c.style, { left: box.x + (box.w - w) / 2 + 'px', top: box.y + (box.h - h) / 2 + 'px', width: w + 'px', height: h + 'px' });
    c.innerHTML = `<i style="background-image:url(${ref.src})"></i>` + (ref.titulo ? `<span class="phc-tag"><em>✦</em>${esc(ref.titulo)}</span>` : '');
    stage.insertBefore(c, anchor);
    const tag = c.querySelector('.phc-tag');
    gsap.set(c, { autoAlpha: 0, y: 60, rotation: PORT ? 0 : 2.5, scale: .94 });
    tl.to(c, { autoAlpha: 1, y: 0, rotation: 0, scale: 1, duration: 1, ease: 'expo.out' }, t0 + .2);
    tl.fromTo(c.firstChild, { scale: 1.15 }, { scale: 1, duration: t1 - t0, ease: 'none', immediateRender: false }, t0 + .2);
    if (tag) { gsap.set(tag, { autoAlpha: 0, x: -20 }); tl.to(tag, { autoAlpha: 1, x: 0, duration: .6, ease: 'back.out(2)' }, t0 + .9); }
    tl.to(c, { autoAlpha: 0, y: -40, duration: .45, ease: 'power3.in' }, t1 - .5);
    return { top: parseFloat(c.style.top), h };
  }

  const K = PORT ? 1.55 : 1;  // no vertical a UI ganha zoom: texto de componente nunca fica abaixo de ~26px na tela de 1080
  function makeSlot(child, before, h = L.slot.h) {
    const slot = el('div', 'slot');
    Object.assign(slot.style, { left: L.slot.x + 'px', top: L.slot.y + 'px', width: L.slot.w + 'px', height: h + 'px' });
    const inner = el('div', 'slot-in');
    Object.assign(inner.style, { position: 'absolute', left: 0, top: 0, width: L.slot.w / K + 'px', height: h / K + 'px', transform: `scale(${K})`, transformOrigin: '0 0' });
    inner.appendChild(child); slot.appendChild(inner); before.parentNode.insertBefore(slot, before);
    return slot;
  }
  let hInst = null, hSlot = null;
  const isHeroUI = x => x && x.type === 'hero' && HEROES[x.hero];
  const filmRnd = rnd, scnOf = [];
  S.scenes.forEach((sc, i) => {
    const u = sc.ui || { type: 'none' };
    rnd = mkRnd(sc.seed || (S.seed + i * 7919));  // cada cena com a própria semente
    if (u.type === 'big_word') { bigWord(sc); return; }
    const t0 = sc.at, t1 = sc.at + sc.dur;
    const m = sc.motion || {};
    DRESS = [];
    // cena = transição (scn) > câmera (cam) > conteúdo; assim os movimentos não brigam entre si
    const scn = el('div', 'scn'), cam = el('div', 'cam'); scn.appendChild(cam); stage.insertBefore(scn, anchor);
    const nextSc = S.scenes[i + 1];
    const outTr = nextSc && (nextSc.ui || {}).type !== 'big_word' ? (nextSc.motion || {}).transition : null;
    const echoOut = !outTr || outTr === 'fade' || !TRANS[outTr];  // saída com eco só quando a próxima não traz transição própria
    let comp = null;
    const hero = isHeroUI(u);
    // layout da foto: split/card só quando a cena não tem componente (senão vira foto de fundo)
    let phL = sc.photo && S.refs && S.refs[sc.photo] ? (sc.layout || 'full') : null;
    if ((phL === 'split' || phL === 'card') && (hero || (u.type !== 'none' && C[u.type]))) phL = 'full';
    if (phL === 'full' || phL === 'kenburns') scenePhoto(sc, t0, t1, phL === 'kenburns');
    if (phL === 'split') photoSplit(sc, t0, t1);
    const prevU = i > 0 ? S.scenes[i - 1].ui : null, nextU = S.scenes[i + 1] ? S.scenes[i + 1].ui : null;
    const contPrev = hero && isHeroUI(prevU) && prevU.hero === u.hero;
    const contNext = hero && isHeroUI(nextU) && nextU.hero === u.hero;
    const wantComp = !hero && u.type !== 'none' && C[u.type];
    let box = (wantComp || hero || phL === 'card') ? L.hl : L.hlFull;
    if (phL === 'split') box = PORT ? { x: 90, y: H * .53, w: 900, h: H * .36, justify: 'flex-start', size: 100, maxH: 560 }
      : { x: 120, y: 0, w: W * .4, h: H, justify: 'center', size: 96, maxH: 640 };
    const hl = el('div', 'hl' + (phL === 'full' || phL === 'kenburns' ? ' onphoto' : ''));
    Object.assign(hl.style, { left: box.x + 'px', top: box.y + 'px', width: box.w + 'px', height: box.h + 'px', justifyContent: box.justify });
    const hasAcc = /\*/.test(sc.headline || '');
    hl.innerHTML = (sc.eyebrow ? `<div class="eyb"><i>✦</i><span>${esc(sc.eyebrow)}</span></div>` : '')
      + `<h2${hasAcc ? ' class="mix"' : ''}>${wordsHTML(sc.headline)}</h2>`
      + (sc.caption && PREMIUM ? '<div class="orn"><b></b><i>✦</i><b></b></div>' : '')
      + (sc.caption ? `<p class="cap">${esc(sc.caption)}</p>` : '');
    if (m.align === 'center' || m.align === 'right') hl.classList.add('al-' + m.align);
    cam.appendChild(hl);
    fitText(hl.querySelector('h2'), box.maxH, box.size);
    // no vertical, headline e componente formam um bloco só, centrado na área útil (sem buraco entre logo e texto)
    const hH = PORT ? (() => { const h0 = hl.style.height; hl.style.height = 'auto'; const v = hl.offsetHeight; hl.style.height = h0; return v; })() : 0;
    const stackHl = top => Object.assign(hl.style, { top: top + 'px', height: hH + 'px', justifyContent: 'flex-start' });
    // no vertical o componente ganha toda a altura que sobra abaixo da headline
    const slotH = PORT ? clamp(PB.bottom - PB.top - hH - PB.gap, L.slot.h, 1080) : L.slot.h;
    if (phL === 'card') {  // foto emoldurada no lugar do componente
      const cbox = PORT ? { x: L.slot.x, y: 0, w: L.slot.w, h: Math.min(slotH, 900) } : { x: L.slot.x, y: L.slot.y, w: L.slot.w, h: L.slot.h };
      if (PORT) {
        const ar = S.refs[sc.photo].ar || 1.5, ch = Math.min(cbox.h, cbox.w / ar);
        const top = PB.top + Math.max(0, (PB.bottom - PB.top - hH - PB.gap - ch) * .45);
        stackHl(top); cbox.y = top + hH + PB.gap; cbox.h = ch;
      }
      photoCard(sc, t0, t1, cbox);
    }
    if (wantComp) comp = C[u.type](u, { w: L.slot.w / K, h: slotH / K });
    let slot = null;
    if (comp) {
      slot = makeSlot(comp.el, hl, slotH);
      if (comp.layout) comp.layout();
      if (PORT) {
        const cb = contentBox(slot, slotH), cH = cb.bottom - cb.top;
        const top = PB.top + Math.max(0, (PB.bottom - PB.top - hH - PB.gap - cH) * .45);
        stackHl(top);
        slot.style.top = top + hH + PB.gap - cb.top + 'px';
      }
    }
    if (hero) {
      const ent = PORT ? { y: 90, autoAlpha: 0 } : { x: 110, autoAlpha: 0 };
      if (!contPrev) {
        const hh = PORT ? slotH - 60 : L.slot.h;  // folga para headlines mais longas nas cenas seguintes do herói
        hInst = HEROES[u.hero](u, { w: L.slot.w / K, h: hh / K });
        hSlot = makeSlot(hInst.el, scn, hh);  // o herói fica fora da cena: atravessa as cenas seguintes
        if (hInst.layout) hInst.layout();
        if (PORT) hSlot.style.top = PB.top + Math.max(0, (PB.bottom - PB.top - hH - PB.gap - hh) * .45) + hH + PB.gap + 'px';
        gsap.set(hSlot, { autoAlpha: 0 });
        tl.fromTo(hSlot, ent, { x: 0, y: 0, autoAlpha: 1, duration: .8, immediateRender: false }, t0 + .15);
      }
      if (PORT) stackHl(Math.max(PB.top, parseFloat(hSlot.style.top) - PB.gap - hH));
      hInst.go(tl, u.state, t0 + .45, Math.max(1.5, sc.dur - 1.1), u);
      if (!contNext) tl.to(hSlot, { autoAlpha: 0, scale: .96, filter: 'blur(8px)', duration: .5, ease: 'power3.in' }, t1 - .55);
    }
    if (sc.sticker) {
      const sl = slot || (hero ? hSlot : null);
      let at;
      if (sl) at = { x: parseFloat(sl.style.left) + parseFloat(sl.style.width) - 70, y: parseFloat(sl.style.top) + 40 };
      else if (PORT) at = { x: W / 2, y: box.y + (box.h - hH) / 2 - 170 };
      else at = { x: W - 250, y: 240 };
      sceneSticker(sc, t0, t1, at);
    }
    // echos de saída (capturam o visual final antes dos estados iniciais)
    if (echoOut) echo(tl, hl, { y: 0, autoAlpha: 1, filter: 'blur(0px)' }, { y: -90, autoAlpha: 0, filter: 'blur(10px)', duration: .5, ease: 'power3.in' }, t1 - .5);
    if (slot) {
      if (echoOut) echo(tl, slot, { x: 0, y: 0, autoAlpha: 1 }, PORT ? { y: -70, autoAlpha: 0, duration: .45, ease: 'power3.in' } : { x: -120, autoAlpha: 0, duration: .45, ease: 'power3.in' }, t1 - .55);
      gsap.set(slot, { autoAlpha: 0 });
      tl.fromTo(slot, PORT ? { y: 90, autoAlpha: 0 } : { x: 110, autoAlpha: 0 }, { x: 0, y: 0, autoAlpha: 1, duration: .8, immediateRender: false }, t0 + .15);
    }
    const eyb = hl.querySelector('.eyb');
    if (eyb) { gsap.set(eyb, { autoAlpha: 0, y: 18 }); tl.to(eyb, { autoAlpha: 1, y: 0, duration: .7, ease: 'expo.out' }, t0 - .1); }
    const orn = hl.querySelector('.orn');
    if (orn) {
      gsap.set(orn.querySelectorAll('b'), { scaleX: 0 }); gsap.set(orn.querySelector('i'), { scale: 0, rotation: -90 });
      tl.to(orn.querySelectorAll('b'), { scaleX: 1, duration: .9, ease: 'expo.out' }, t0 + .35);
      tl.to(orn.querySelector('i'), { scale: 1, rotation: 0, duration: .6, ease: 'back.out(3)' }, t0 + .3);
    }
    // base do texto: sobre foto o texto sempre ganha vidro ou faixa (legibilidade antes de estética)
    const h2 = hl.querySelector('h2');
    let fx = TFX.includes(m.text_fx) ? m.text_fx : pickFx(sc, i);
    let bg = m.text_bg || 'none';
    if (phL === 'kenburns') { glassBand(hl, box, t0, t1); if (bg === 'glass') bg = 'none'; }
    else if (phL === 'full' && !['bar', 'block', 'glass'].includes(bg)) bg = 'glass';
    if (bg === 'glass') glassBand(hl, box, t0, t1);
    if (bg === 'bar' && fx === 'bars') fx = 'rise';
    if (fx === 'kinetic' && (slot || hero || phL === 'card')) fx = 'stack';  // a palavra gigante cobriria o componente
    const nW = h2.querySelectorAll('.w').length;
    const tText = fx === 'kinetic' ? t0 + nW * (SNAPPY ? .3 : .38) : t0;  // quando a frase montada aparece
    textIn(h2, fx, t0, cam);
    textBg(bg, h2, tText);  // mede depois do textIn: quebrar em letras muda um pouco a largura das palavras
    const f = focal(h2, cam);
    ornament(m.ornament, sc, i, hl, h2, cam, slot, t0, t1);
    emphasize(m.emphasis, h2, tText + (fx === 'kinetic' ? .7 : 1.05 * DK));
    camera(m.camera, cam, hl, slot, t0, t1, f);
    const cap = hl.querySelector('.cap');
    if (cap) { gsap.set(cap, { autoAlpha: 0, y: 24 }); tl.to(cap, { autoAlpha: 1, y: 0, duration: .8 }, tText + .45); }
    if (comp && comp.anim) comp.anim(tl, t0 + .45, Math.max(1.5, sc.dur - 1.1));
    if (echoOut && DRESS.length) tl.to(DRESS, { autoAlpha: 0, scale: .9, duration: .45, ease: 'power3.in' }, t1 - .5);
    // transição de entrada desta cena (a anterior já sabe que não deve sair com eco)
    scnOf[i] = scn;
    if (m.transition && TRANS[m.transition]) TRANS[m.transition](scnOf[i - 1] || null, scn, t0);
  });
  rnd = filmRnd;

  // fundo claro + cena com foto escura: o logo do canto fica branco enquanto a foto está na tela
  if (T.mode === 'light' && !PLATE) {
    const onPh = sc => sc.photo && S.refs && S.refs[sc.photo] && sc.ui && sc.ui.type !== 'big_word' && (sc.layout || 'full') !== 'card'
      && !(sc.layout === 'split' && !PORT);
    let run = null;
    const flush = () => { if (!run) return; tl.to(logo, { filter: 'brightness(0) invert(1)', duration: .4 }, run[0] - .25); tl.to(logo, { filter: 'brightness(1) invert(0)', duration: .4 }, run[1] - .45); run = null; };
    S.scenes.forEach(sc => { if (onPh(sc)) { if (run && sc.at - run[1] < .5) run[1] = sc.at + sc.dur; else { flush(); run = [sc.at, sc.at + sc.dur]; } } else flush(); });
    flush();
  }

  // final: o logo entra com outro efeito, num elemento próprio (não disputa a timeline com o logo do canto)
  if (PLATE) {
    const pl2 = el('div', 'plate'); stage.appendChild(pl2);
    const cy = (L.logo.cy / H * 100).toFixed(1);
    gsap.set(pl2, { clipPath: `circle(0% at 50% ${cy}%)` });
    tl.to(pl2, { clipPath: `circle(150% at 50% ${cy}%)`, duration: .9, ease: 'expo.inOut' }, OA + .1);
  }
  const logo2 = makeLogo(); stage.appendChild(logo2);
  gsap.set(logo2, { autoAlpha: 0 }); tl.set(logo2, { autoAlpha: 1 }, OA + .5);
  reveal(RV.outro, logo2, OA + .5);
  const tagY = L.logo.cy + lb.h / 2 + (PORT ? 80 : 60);
  if (PREMIUM) {  // linha curva em degradê que cruza a base no fecho
    const y0 = H * (PORT ? .84 : .8);
    const sw = el('div', 'swoosh', `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><defs><linearGradient id="swg" x1="0" x2="1">
      <stop offset="0" stop-color="${PALD[0]}" stop-opacity="0"/><stop offset=".5" stop-color="${PALD[0]}"/><stop offset="1" stop-color="${PALD[1] || PALD[0]}" stop-opacity="0"/></linearGradient></defs>
      <path d="M${-W * .05} ${y0 + H * .08} C ${W * .3} ${y0 - H * .1}, ${W * .62} ${y0 + H * .12}, ${W * 1.05} ${y0 - H * .04}" fill="none" stroke="url(#swg)" stroke-width="2"/></svg>`);
    stage.appendChild(sw);
    const path = sw.querySelector('path'), pl = path.getTotalLength();
    gsap.set(path, { strokeDasharray: pl, strokeDashoffset: pl });
    tl.to(path, { strokeDashoffset: 0, duration: 1.8, ease: 'power2.inOut' }, OA + 1.4);
  }
  if (S.brand.tagline) {
    const tg = el('div', 'tag' + (PLATE ? ' onplate' : ''), wordsHTML(S.brand.tagline)); tg.style.top = tagY + 'px'; tg.style.fontSize = (PORT ? 52 : 44) + 'px';
    stage.appendChild(tg);
    const w = tg.querySelectorAll('.wi'); gsap.set(w, { yPercent: 150 });
    tl.to(w, { yPercent: 0, duration: .8, stagger: .06 }, OA + 2.5);
  }
  if (S.brand.cta) {
    const c = el('div', 'cta' + (PLATE ? ' onplate' : ''), `<div><span class="arr inv"><svg width="22" height="22" viewBox="0 0 24 24"><path d="M5 12h13M13 6l6 6-6 6" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg></span>${esc(S.brand.cta)}</div>`);
    c.style.top = tagY + (PORT ? 190 : 130) + 'px'; stage.appendChild(c);
    echo(tl, c, { y: 34, autoAlpha: 0 }, { y: 0, autoAlpha: 1, duration: .75 }, OA + 3.1);
  }
  if (S.progress) {
    const pg = el('div', 'prog', '<i></i>'); Object.assign(pg.style, { left: L.prog.x + 'px', top: L.prog.y + 'px', width: L.prog.w + 'px' }); stage.appendChild(pg);
    tl.fromTo(pg.querySelector('i'), { scaleX: 0 }, { scaleX: 1, duration: S.duration, ease: 'none', immediateRender: false }, 0);
  }
  tl.set({}, {}, S.duration);

  gsap.ticker.add(frame);
  window.__motion = {
    duration: S.duration, tl, ready: true,
    seek(t) { tl.pause(); tl.seek(t, false); frame(); },
    play() { tl.play(); }
  };
  if (!RENDER) {
    const btn = document.getElementById('replay');
    // Trilha (narração + efeitos + música): segue o relógio da timeline e corrige desvios.
    const au = S.audio ? new Audio(S.audio) : null;
    let snd = null;
    const playAudio = () => {
      if (!au) return;
      au.currentTime = tl.time();
      const p = au.play();
      if (p) p.catch(() => {  // navegador bloqueou som sem clique: pausa e pede um clique
        tl.pause();
        if (!snd) {
          snd = el('button', '', 'Tocar com som'); snd.id = 'sound'; snd.type = 'button'; document.body.appendChild(snd);
          snd.addEventListener('click', () => { snd.classList.remove('show'); tl.restart(); playAudio(); });
        }
        snd.classList.add('show');
      });
    };
    if (au) gsap.ticker.add(() => {
      if (!tl.paused() && !au.paused && Math.abs(au.currentTime - tl.time()) > .15) au.currentTime = tl.time();
    });
    const play = () => { tl.play(); playAudio(); };
    const pause = () => { tl.pause(); if (au) au.pause(); };
    tl.eventCallback('onComplete', () => { btn.classList.add('show'); if (au) au.pause(); });
    btn.addEventListener('click', () => { btn.classList.remove('show'); tl.restart(); playAudio(); });
    addEventListener('keydown', e => { if (e.code === 'Space') { e.preventDefault(); tl.paused() ? play() : pause(); } });
    setTimeout(play, 300);
  }
})();
