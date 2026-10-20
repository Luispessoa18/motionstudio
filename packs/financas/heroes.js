/* Pacote finanças / investimentos / crescimento. */

/* ---------- GRÁFICO: histórico → queda → virada → meta ---------- */
HEROES.grafico = (u0, b) => {
  const ORDER = ['historico', 'queda', 'virada', 'meta'];
  const MARK = { historico: .45, queda: .62, virada: 1, meta: 1 };
  const X0 = 20, X1 = b.w - 20, Y0 = 150, Y1 = b.h - 40;
  const e = el('div', 'hf');
  const N = 60, pts = [];
  for (let i = 0; i < N; i++) {
    const f = i / (N - 1);
    let v = f < .45 ? .35 + .25 * f / .45 + .05 * Math.sin(i * 1.7)
      : f < .62 ? .6 - .38 * (f - .45) / .17 + .03 * Math.sin(i * 2.3)
      : .22 + .7 * ((f - .62) / .38) ** 1.4 + .025 * Math.sin(i * 1.9);
    pts.push([X0 + f * (X1 - X0), Y1 - v * (Y1 - Y0)]);
  }
  const d = 'M' + pts.map(p => p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' L');
  const NS = 'http://www.w3.org/2000/svg', svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', `0 0 ${b.w} ${b.h}`); svg.setAttribute('width', b.w); svg.setAttribute('height', b.h);
  const cid = 'c' + Math.round(rnd() * 1e6);
  svg.innerHTML = `<defs><clipPath id="${cid}"><rect class="cr" x="0" y="0" width="0" height="${b.h}"/></clipPath></defs>` +
    [0, .25, .5, .75, 1].map(f => `<line class="gl" x1="${X0}" x2="${X1}" y1="${Y0 + f * (Y1 - Y0)}" y2="${Y0 + f * (Y1 - Y0)}" stroke="${T.fg}" stroke-opacity=".08"/>`).join('') +
    `<path d="${d} L${X1} ${Y1} L${X0} ${Y1}Z" fill="${T.acc}" fill-opacity=".13" clip-path="url(#${cid})"/>
     <path class="ln" d="${d}" fill="none" stroke="${T.acc}" stroke-width="4" stroke-linejoin="round"/>
     <line class="tg" x1="${X0}" x2="${X1}" y1="${Y0 - 10}" y2="${Y0 - 10}" stroke="${T.fg}" stroke-width="1.5" stroke-dasharray="8 8"/>`;
  const dot = el('div', 'hf-dot'), head = el('div', 'hf-head');
  e.append(svg, dot, head);
  const ln = svg.querySelector('.ln'), cr = svg.querySelector('.cr'), tg = svg.querySelector('.tg'), gl = [...svg.querySelectorAll('.gl')];
  const P = { p: 0 };
  let LEN = 0;
  gsap.set([dot, tg, ...gl], { autoAlpha: 0 });
  FRAME.push(() => {
    if (!LEN) return;
    ln.style.strokeDashoffset = LEN * (1 - P.p);
    const pt = ln.getPointAtLength(LEN * P.p);
    dot.style.left = pt.x + 'px'; dot.style.top = pt.y + 'px'; cr.setAttribute('width', pt.x);
  });
  let cur = -1;
  function header(tl, t, u) {
    if (!u.value && !u.title) return;
    const h = el('div', 'hf-h', `${u.title ? `<div class="k">${esc(u.title)}</div>` : ''}${u.value ? `<div class="hf-v mn">${esc(u.value)}</div>` : ''}`);
    const old = [...head.children]; head.appendChild(h);
    if (old.length) tl.to(old, { autoAlpha: 0, y: -20, duration: .35 }, t);
    gsap.set(h, { autoAlpha: 0, y: 20 }); tl.to(h, { autoAlpha: 1, y: 0, duration: .5 }, t + .2);
    if (u.value) count(tl, h.querySelector('.hf-v'), parseNum(u.value), t + .25, 1.5);
  }
  function tag(tl, t, frac, text) {
    if (!text) return;
    const i = Math.min(N - 1, Math.round(frac * (N - 1))), [x, y] = pts[i];
    const g = el('div', 'c-ftag c-card hf-tag', esc(text)); Object.assign(g.style, { left: x + 'px', top: y + 'px' }); e.appendChild(g);
    gsap.set(g, { autoAlpha: 0, xPercent: -50, yPercent: frac > .5 && frac < .7 ? 40 : -160 });
    tl.to(g, { autoAlpha: 1, duration: .45 }, t);
  }
  const steps = {
    historico(tl, t, d, u) {
      tl.to(gl, { autoAlpha: 1, duration: .6, stagger: .06 }, t);
      tl.to(dot, { autoAlpha: 1, duration: .3 }, t + .2);
      tl.to(P, { p: MARK.historico, duration: Math.max(1, d * .8), ease: 'power1.inOut' }, t + .2);
      header(tl, t, u); tag(tl, t + d * .7, .3, u.label);
    },
    queda(tl, t, d, u) { tl.to(P, { p: MARK.queda, duration: Math.max(.8, d * .6), ease: 'power2.in' }, t); header(tl, t, u); tag(tl, t + d * .5, .62, u.label); },
    virada(tl, t, d, u) { tl.to(P, { p: 1, duration: Math.max(1, d * .8), ease: 'power2.inOut' }, t); header(tl, t, u); tag(tl, t + .3, .62, u.label); },
    meta(tl, t, d, u) {
      if (P.p < 1) tl.to(P, { p: 1, duration: .8 }, t);
      tl.fromTo(tg, { autoAlpha: 0, scaleX: 0 }, { autoAlpha: 1, scaleX: 1, svgOrigin: `${X0} ${Y0}`, duration: .8, ease: 'expo.inOut', immediateRender: false }, t);
      tl.to(dot, { boxShadow: `0 0 0 16px ${T.accGlow}`, duration: .6, repeat: Math.max(1, Math.floor(d / .6)), yoyo: true }, t + .6);
      header(tl, t, u); tag(tl, t + .6, .97, u.label);
    }
  };
  return { el: e, layout() { LEN = ln.getTotalLength(); ln.style.strokeDasharray = LEN; ln.style.strokeDashoffset = LEN; }, go(tl, state, t, d, u) {
    let k = ORDER.indexOf(state); if (k < 0) k = Math.min(cur + 1, ORDER.length - 1);
    if (k <= cur) return;
    const n = k - cur, quick = Math.min(1.2, d * .35 / n); let tt = t;
    for (let j = cur + 1; j <= k; j++) { const last = j === k; steps[ORDER[j]](tl, tt, last ? Math.max(1, d - (tt - t)) : quick, last ? u : {}); if (!last) tt += quick; }
    cur = k;
  } };
};

/* ---------- CARTEIRA: rosca de composição → destaque → total ---------- */
HEROES.carteira = (u0, b) => {
  const ORDER = ['composicao', 'destaque', 'total'];
  const r = Math.min(b.w * .27, b.h * .34), cx = b.w * .32, cy = b.h * .5, SW = 46, C = 2 * Math.PI * r;
  const e = el('div', 'hw');
  const NS = 'http://www.w3.org/2000/svg', svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', `0 0 ${b.w} ${b.h}`); svg.setAttribute('width', b.w); svg.setAttribute('height', b.h);
  svg.innerHTML = `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${T.fg}" stroke-opacity=".06" stroke-width="${SW}"/>`;
  const center = el('div', 'hw-c'); Object.assign(center.style, { left: cx + 'px', top: cy + 'px' });
  const legend = el('div', 'hw-leg'); Object.assign(legend.style, { left: cx + r + SW + 50 + 'px' });
  e.append(svg, center, legend);
  let cur = -1, segs = [], rows = [];
  const steps = {
    composicao(tl, t, d, u) {
      const items = (u.items && u.items.length ? u.items : [{ label: 'Renda fixa', value: '45%' }, { label: 'Ações', value: '30%' }, { label: 'Exterior', value: '15%' }, { label: 'Caixa', value: '10%' }]).slice(0, 6);
      const pc = items.map(it => { const p = parseNum(it.value); return p ? p.num : 100 / items.length; });
      const tot = pc.reduce((a, x) => a + x, 0) || 1;
      let acc = 0;
      items.forEach((it, i) => {
        const len = pc[i] / tot * C, gap = 4;
        const col = i === 0 ? T.acc : T.fg, op = i === 0 ? 1 : [.75, .5, .32, .2, .12][i - 1] || .12;
        const c = document.createElementNS(NS, 'circle');
        Object.entries({ cx, cy, r, fill: 'none', stroke: col, 'stroke-opacity': op, 'stroke-width': SW, 'stroke-dasharray': `${Math.max(1, len - gap)} ${C}`, transform: `rotate(${-90 + acc / C * 360} ${cx} ${cy})` }).forEach(([k, v]) => c.setAttribute(k, v));
        c._len = Math.max(1, len - gap); c.style.strokeDashoffset = c._len; svg.appendChild(c); segs.push(c); acc += len;
        const row = el('div', 'hw-row', `<i style="background:${col};opacity:${op}"></i><span>${esc(it.label)}</span><b class="mn">${esc(it.value || Math.round(pc[i]) + '%')}</b>`);
        legend.appendChild(row); rows.push(row);
      });
      center.innerHTML = `${u.label ? `<div class="k">${esc(u.label)}</div>` : ''}<div class="hw-v mn">${esc(u.value || '')}</div>`;
      gsap.set(rows, { autoAlpha: 0, x: 20 }); gsap.set(center, { autoAlpha: 0 });
      const st = Math.min(.35, d * .5 / segs.length);
      segs.forEach((c, i) => tl.to(c, { strokeDashoffset: 0, duration: .7, ease: 'power2.out' }, t + i * st));
      tl.to(rows, { autoAlpha: 1, x: 0, duration: .45, stagger: st }, t + .2);
      tl.to(center, { autoAlpha: 1, duration: .5 }, t + .4);
      if (u.value) count(tl, center.querySelector('.hw-v'), parseNum(u.value), t + .4, 1.6);
    },
    destaque(tl, t, d, u) {
      const i = Number.isInteger(u.highlight) && u.highlight < segs.length ? u.highlight : 0;
      tl.to(segs.filter((_, j) => j !== i), { opacity: .25, duration: .5 }, t);
      tl.to(rows.filter((_, j) => j !== i), { opacity: .35, duration: .5 }, t);
      tl.to(segs[i], { attr: { 'stroke-width': SW + 18 }, duration: .6, ease: 'back.out(2)' }, t + .1);
      tl.to(rows[i], { x: 12, duration: .5 }, t + .1);
      if (u.note || u.value) {
        const n = el('div', 'c-ftag inv hw-note', esc(u.note || u.value)); legend.appendChild(n);
        gsap.set(n, { autoAlpha: 0, y: 10 }); tl.to(n, { autoAlpha: 1, y: 0, duration: .5 }, t + .5);
      }
    },
    total(tl, t, d, u) {
      tl.to(segs, { opacity: 1, attr: { 'stroke-width': SW }, duration: .6 }, t);
      tl.to(rows, { opacity: 1, x: 0, duration: .5 }, t);
      if (u.value) {
        const h = el('div', '', `${u.label ? `<div class="k">${esc(u.label)}</div>` : ''}<div class="hw-v mn">${esc(u.value)}</div>`);
        tl.to(center.children, { autoAlpha: 0, duration: .3 }, t);
        center.appendChild(h); gsap.set(h, { autoAlpha: 0 }); tl.to(h, { autoAlpha: 1, duration: .4 }, t + .3);
        count(tl, h.querySelector('.hw-v'), parseNum(u.value), t + .3, 1.6);
      }
      tl.fromTo(svg, { filter: 'drop-shadow(0 0 0px rgba(0,0,0,0))' }, { filter: `drop-shadow(0 0 22px ${T.accGlow})`, duration: .6, yoyo: true, repeat: 1, immediateRender: false }, t + .4);
    }
  };
  return { el: e, go(tl, state, t, d, u) {
    let k = ORDER.indexOf(state); if (k < 0) k = Math.min(cur + 1, ORDER.length - 1);
    if (k <= cur) return;
    const n = k - cur, quick = Math.min(1.2, d * .35 / n); let tt = t;
    for (let j = cur + 1; j <= k; j++) { const last = j === k; steps[ORDER[j]](tl, tt, last ? Math.max(1, d - (tt - t)) : quick, j === k || j === 0 ? u : {}); if (!last) tt += quick; }
    cur = k;
  } };
};
