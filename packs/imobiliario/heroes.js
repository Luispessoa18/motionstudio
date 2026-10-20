/* Pacote imobiliário. Fragmento injetado dentro do runtime: tem acesso a el, esc, gsap, T, PORT, count, parseNum, FRAME, HEROES, rnd, clamp. */

/* ---------- LOTE: terreno em planta → isometria → recuos → prédio → VGV ---------- */
HEROES.lote = (u0, b) => {
  const ORDER = ['planta', 'iso', 'recuos', 'predio', 'vgv'];
  const s = Math.min(1, (b.w * .58) / 560);
  const PW = 560 * s, PH = 380 * s;
  const cx = b.w * .38, cy = b.h * .56;
  const e = el('div', 'hl-lote');
  const sc3 = el('div', 'hl-3d'); sc3.style.perspectiveOrigin = `${cx}px ${cy - 80}px`;
  const plane = el('div', 'hl-plane');
  Object.assign(plane.style, { left: cx - PW / 2 + 'px', top: cy - PH / 2 + 'px', width: PW + 'px', height: PH + 'px' });
  sc3.appendChild(plane); e.appendChild(sc3);
  const px = v => v * s + 'px';
  const blocks = [];
  [-300, -70, 160, 390, 620].forEach(x => [-250, -50, 150, 480].forEach(y => {
    if (x < 590 && x + 180 > -30 && y < 480 && y + 150 > -30) return;
    const k = el('div', 'hl-blk'); Object.assign(k.style, { left: px(x), top: px(y), width: px(180), height: px(150) });
    plane.appendChild(k); blocks.push(k);
  }));
  const road = el('div', 'hl-road'); Object.assign(road.style, { left: px(-300), top: px(425), width: px(1160) }); plane.appendChild(road);
  const street = el('div', 'hl-street', esc(u0.label || 'AV. PRINCIPAL')); Object.assign(street.style, { left: px(100), top: px(438), fontSize: Math.max(11, 16 * s) + 'px' }); plane.appendChild(street);
  const gid = 'g' + Math.round(rnd() * 1e6);
  const svgNS = 'http://www.w3.org/2000/svg';
  const lot = document.createElementNS(svgNS, 'svg');
  lot.setAttribute('viewBox', '0 0 560 380'); lot.setAttribute('width', PW); lot.setAttribute('height', PH);
  lot.setAttribute('class', 'hl-lotsvg');
  let trees = '';
  [[40, 40], [70, 330], [30, 200], [100, 60], [470, 50], [520, 120], [500, 330], [440, 345], [520, 230], [60, 120], [110, 320], [300, 335], [230, 345]].forEach(([x, y], i) =>
    trees += `<circle cx="${x}" cy="${y}" r="${8 + (i % 3) * 3}" fill="${T.fg}" fill-opacity=".07" stroke="${T.fg}" stroke-opacity=".22"/>`);
  lot.innerHTML = `<defs><filter id="${gid}" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>
    <rect class="lf" width="560" height="380" fill="${T.acc}" fill-opacity=".07"/><g class="tr">${trees}</g>
    <g class="rc"><rect class="rr" x="18" y="18" width="524" height="282" fill="none" stroke="${T.fg}" stroke-opacity=".55" stroke-width="1.5" stroke-dasharray="8 8"/>
    <text x="280" y="350" text-anchor="middle" fill="${T.muted}" font-size="15" letter-spacing="2" font-family="${T.fontMono}">recuo frontal</text></g>
    <path class="lp" d="M2 2H558V378H2Z" fill="none" stroke="${T.acc}" stroke-width="3.5" filter="url(#${gid})" stroke-dasharray="1864" stroke-dashoffset="1864"/>`;
  plane.appendChild(lot);
  const lp = lot.querySelector('.lp'), lf = lot.querySelector('.lf'), tr = lot.querySelector('.tr'), rc = lot.querySelector('.rc'), rr = lot.querySelector('.rr');
  const nslabs = [];
  [[-280, -30, 7], [640, -30, 10], [180, -230, 5], [-280, 500, 4]].forEach(([x, y, n]) => {
    for (let i = 0; i <= n; i++) { const k = el('div', 'hl-nslab'); Object.assign(k.style, { left: px(x), top: px(y), width: px(140), height: px(110) }); k._z = i * 24 * s; plane.appendChild(k); nslabs.push(k); }
  });
  const call = el('div', 'hl-call'); e.appendChild(call);
  const badge = el('div', 'hl-badge', `<div class="k">Pavimentos</div><div class="v mn">0</div>`); e.appendChild(badge);
  const cam = { rx: 0, rz: 0, s: .8, y: 0 };
  FRAME.push(() => { plane.style.transform = `translateY(${cam.y}px) scale(${cam.s}) rotateX(${cam.rx}deg) rotateZ(${cam.rz}deg)`; });
  gsap.set(blocks, { autoAlpha: 0 }); gsap.set([lf, tr, rc, street, badge], { autoAlpha: 0 }); gsap.set(nslabs, { autoAlpha: 0, z: 0 });
  let cur = -1, slabs = [], calls = [];

  const steps = {
    planta(tl, t, d) {
      tl.fromTo(cam, { s: .78 }, { s: .92, duration: Math.min(3.6, d + .6), ease: 'power2.out', immediateRender: false }, t);
      tl.to(blocks, { autoAlpha: 1, duration: .5, stagger: { each: .02, from: 'random' } }, t);
      tl.to(lp, { strokeDashoffset: 0, duration: Math.min(1.3, d * .55), ease: 'power3.inOut' }, t + .15);
      tl.to([lf, tr], { autoAlpha: 1, duration: .6 }, t + Math.min(1.3, d * .55));
      tl.fromTo(street, { autoAlpha: 0, x: -30 }, { autoAlpha: 1, x: 0, duration: .8, immediateRender: false }, t + .4);
    },
    iso(tl, t, d) { tl.to(cam, { rx: 57, rz: -38, y: 40 * s, duration: Math.min(1.25, d), ease: 'expo.inOut' }, t); },
    recuos(tl, t, d, u) {
      tl.to(rc, { autoAlpha: 1, duration: .6 }, t);
      tl.fromTo(rr, { strokeDashoffset: 64 }, { strokeDashoffset: 0, duration: d + 3, ease: 'none', immediateRender: false }, t);
      const items = (u.items || []).slice(0, 4);
      calls = items.map(it => {
        const c = el('div', 'c-card c-item hl-ci', `<div class="k">${esc(it.label)}</div><div class="c-val mn">${esc(it.value)}</div>${it.sub ? `<div class="c-sub">${esc(it.sub)}</div>` : ''}`);
        call.appendChild(c); return c;
      });
      gsap.set(calls, { autoAlpha: 0, x: 60 });
      tl.to(calls, { autoAlpha: 1, x: 0, duration: .7, stagger: .14 }, t + .2);
      calls.forEach((c, i) => count(tl, c.querySelector('.c-val'), parseNum(items[i].value), t + .3 + i * .14, 1.3));
    },
    predio(tl, t, d, u) {
      const pn = parseNum(u.value);
      const n = clamp(pn ? Math.round(pn.num) : 12, 2, 40);
      const fh = Math.min(26, 330 / n) * s;
      for (let i = 0; i <= n; i++) {
        const k = el('div', 'hl-slab' + (i === n ? ' roof' : '')); Object.assign(k.style, { left: px(150), top: px(80), width: px(260), height: px(200) });
        k._z = i * fh; plane.appendChild(k); slabs.push(k);
      }
      gsap.set(slabs, { autoAlpha: 0, z: 0 });
      const per = Math.min(.16, (d * .6) / n);
      tl.to(slabs, { z: i => slabs[i]._z, autoAlpha: 1, duration: .5, ease: 'power2.out', stagger: per }, t);
      tl.to(nslabs, { z: i => nslabs[i]._z, autoAlpha: 1, duration: .6, ease: 'power2.out', stagger: .03 }, t);
      tl.to(cam, { rz: '-=9', s: '+=.05', duration: d + .6, ease: 'none' }, t);
      if (u.label || pn) badge.querySelector('.k').textContent = u.label && !pn ? u.label : 'Pavimentos';
      tl.fromTo(badge, { autoAlpha: 0, y: -16 }, { autoAlpha: 1, y: 0, duration: .5, immediateRender: false }, t);
      count(tl, badge.querySelector('.v'), { num: n, dec: 0, pre: '', suf: '', group: false }, t, n * per + .4, 0);
    },
    vgv(tl, t, d, u) {
      tl.to(calls, { autoAlpha: 0, x: 40, duration: .4, stagger: .05, ease: 'power2.in' }, t);
      tl.to(slabs, { backgroundColor: T.accGlow.replace(/[\d.]+\)$/, '0.17)'), duration: .8, stagger: .03 }, t + .2);
      const card = el('div', 'c-card hl-vgv', `<div class="k">${esc(u.label || 'VGV estimado')}</div><div class="hl-vv mn">${esc(u.value || '')}</div>${u.note ? `<div class="c-sub">${esc(u.note)}</div>` : ''}`);
      e.appendChild(card);
      gsap.set(card, { autoAlpha: 0, y: 40 });
      tl.to(card, { autoAlpha: 1, y: 0, duration: .8 }, t + .35);
      count(tl, card.querySelector('.hl-vv'), parseNum(u.value), t + .5, Math.min(2.2, d * .6));
      tl.to(cam, { s: '-=.06', y: '-=20', duration: d, ease: 'power1.inOut' }, t);
    }
  };
  return { el: e, go(tl, state, t, d, u) {
    let k = ORDER.indexOf(state); if (k < 0) k = Math.min(cur + 1, ORDER.length - 1);
    if (k <= cur) { tl.to(cam, { rz: '-=6', duration: d, ease: 'none' }, t); return; }
    const n = k - cur, quick = Math.min(.9, d * .3 / n);
    let tt = t;
    for (let j = cur + 1; j <= k; j++) { const last = j === k; steps[ORDER[j]](tl, tt, last ? Math.max(1, d - (tt - t)) : quick, u); if (!last) tt += quick; }
    cur = k;
  } };
};

/* ---------- MAPA: cidade → pin → raio de alcance → pontos de interesse ---------- */
HEROES.mapa = (u0, b) => {
  const ORDER = ['cidade', 'pin', 'raio', 'pois'];
  const W2 = b.w, H2 = b.h, cx = W2 * .46, cy = H2 * .5, R = Math.min(W2, H2) * .42;
  const e = el('div', 'hm-map');
  const NS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(NS, 'svg'); svg.setAttribute('viewBox', `0 0 ${W2} ${H2}`); svg.setAttribute('width', W2); svg.setAttribute('height', H2);
  let lines = '', lens = [];
  const L = (x1, y1, x2, y2, w, op) => { lens.push(Math.hypot(x2 - x1, y2 - y1)); lines += `<line class="st" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${T.fg}" stroke-opacity="${op}" stroke-width="${w}"/>`; };
  for (let y = 30; y < H2; y += 74) L(-20, y + (rnd() - .5) * 20, W2 + 20, y + (rnd() - .5) * 40, 1.2, .16);
  for (let x = 30; x < W2; x += 92) L(x + (rnd() - .5) * 20, -20, x + (rnd() - .5) * 50, H2 + 20, 1.2, .16);
  L(-20, H2 * .85, W2 + 20, H2 * .1, 5, .22); L(W2 * .1, -20, W2 * .7, H2 + 20, 4, .2);
  const rings = [.34, .64, .94].map(f => `<circle class="rg" cx="${cx}" cy="${cy}" r="${R * f}" fill="none" stroke="${T.acc}" stroke-opacity=".7" stroke-width="1.5" stroke-dasharray="6 8"/>`).join('');
  svg.innerHTML = `<g class="zm"><path class="wt" d="M -20 ${H2 * .25} C ${W2 * .3} ${H2 * .05}, ${W2 * .45} ${H2 * .55}, ${W2 + 20} ${H2 * .4}" fill="none" stroke="${T.fg}" stroke-opacity=".07" stroke-width="26"/>${lines}${rings}<g class="lk"></g><g class="pois"></g>
    <circle class="pu" cx="${cx}" cy="${cy}" r="20" fill="${T.acc}" fill-opacity=".35"/>
    <g transform="translate(${cx} ${cy})"><g class="pin"><path d="M0 0 C -14 -18 -22 -30 -22 -42 A22 22 0 1 1 22 -42 C22 -30 14 -18 0 0Z" fill="${T.acc}"/><circle cx="0" cy="-42" r="8" fill="${T.bg}"/></g></g></g>`;
  e.appendChild(svg);
  const zm = svg.querySelector('.zm'), sts = [...svg.querySelectorAll('.st')], wt = svg.querySelector('.wt');
  const pin = svg.querySelector('.pin'), pu = svg.querySelector('.pu'), rgs = [...svg.querySelectorAll('.rg')];
  sts.forEach((l, i) => { l.style.strokeDasharray = lens[i]; l.style.strokeDashoffset = lens[i]; });
  const tag = el('div', 'c-ftag inv hm-tag', esc(u0.label || u0.title || 'Seu terreno')); Object.assign(tag.style, { right: W2 - cx + 30 + 'px', top: cy - 120 + 'px' }); e.appendChild(tag);
  const rlab = el('div', 'hm-rlab mn'); Object.assign(rlab.style, { left: cx + R * .66 + 'px', top: cy - R * .72 + 'px' }); e.appendChild(rlab);
  gsap.set([wt, pin, pu, tag, rlab, ...rgs], { autoAlpha: 0 });
  let cur = -1;
  const steps = {
    cidade(tl, t, d) {
      tl.fromTo(zm, { scale: 1.2 }, { scale: 1, svgOrigin: `${cx} ${cy}`, duration: d + 4, ease: 'power2.out', immediateRender: false }, t);
      tl.to(wt, { autoAlpha: 1, duration: 1 }, t);
      tl.to(sts, { strokeDashoffset: 0, duration: 1.1, ease: 'power2.out', stagger: { each: Math.min(.03, d * .4 / sts.length), from: 'random' } }, t);
    },
    pin(tl, t, d, u) {
      if (u.label) tag.textContent = u.label;
      tl.fromTo(pin, { y: -160, autoAlpha: 0 }, { y: 0, autoAlpha: 1, duration: .9, ease: 'bounce.out', immediateRender: false }, t);
      tl.fromTo(tag, { autoAlpha: 0, scale: .7 }, { autoAlpha: 1, scale: 1, duration: .5, ease: 'back.out(2)', immediateRender: false }, t + .7);
      const reps = Math.max(1, Math.floor((d + 4) / 1.3));
      tl.fromTo(pu, { scale: .3, autoAlpha: .8 }, { scale: 3, autoAlpha: 0, svgOrigin: `${cx} ${cy}`, duration: 1.3, repeat: reps, ease: 'power1.out', immediateRender: false }, t + .8);
    },
    raio(tl, t, d, u) {
      rlab.textContent = u.value || '';
      tl.fromTo(rgs, { scale: 0, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, svgOrigin: `${cx} ${cy}`, duration: .9, stagger: .25, immediateRender: false }, t);
      if (u.value) tl.fromTo(rlab, { autoAlpha: 0, y: 10 }, { autoAlpha: 1, y: 0, duration: .5, immediateRender: false }, t + .8);
    },
    pois(tl, t, d, u) {
      const items = (u.items || []).slice(0, 6), n = items.length || 1;
      const pg = svg.querySelector('.pois'), lk = svg.querySelector('.lk');
      const ds = [], ls = [], tg = [];
      items.forEach((it, i) => {
        const a = -Math.PI / 2 + i * (Math.PI * 2 / n) + .9, r = R * (i % 2 ? .78 : .55);
        const x = cx + Math.cos(a) * r, y = cy + Math.sin(a) * r * .85;
        const ln = document.createElementNS(NS, 'line');
        Object.entries({ x1: cx, y1: cy, x2: x, y2: y, stroke: T.fg, 'stroke-opacity': .35, 'stroke-dasharray': '4 6' }).forEach(([k, v]) => ln.setAttribute(k, v)); lk.appendChild(ln); ls.push(ln);
        const dt = document.createElementNS(NS, 'circle');
        Object.entries({ cx: x, cy: y, r: 7, fill: T.fg }).forEach(([k, v]) => dt.setAttribute(k, v)); pg.appendChild(dt); ds.push(dt);
        const lb = el('div', 'c-ftag c-card hm-poi', `${esc(it.label)}${it.value ? ` <span class="mn">${esc(it.value)}</span>` : ''}`);
        Object.assign(lb.style, { left: x + 12 + 'px', top: y - 18 + 'px' }); e.appendChild(lb); tg.push(lb);
      });
      gsap.set([...ds, ...ls, ...tg], { autoAlpha: 0 });
      const st = Math.min(.3, d * .5 / n);
      tl.to(ls, { autoAlpha: 1, duration: .4, stagger: st }, t);
      tl.fromTo(ds, { scale: 0 }, { scale: 1, autoAlpha: 1, transformOrigin: '50% 50%', duration: .45, ease: 'back.out(3)', stagger: st, immediateRender: false }, t + .1);
      tl.fromTo(tg, { x: -10 }, { x: 0, autoAlpha: 1, duration: .45, stagger: st, immediateRender: false }, t + .2);
    }
  };
  return { el: e, go(tl, state, t, d, u) {
    let k = ORDER.indexOf(state); if (k < 0) k = Math.min(cur + 1, ORDER.length - 1);
    if (k <= cur) return;
    const n = k - cur, quick = Math.min(.9, d * .3 / n); let tt = t;
    for (let j = cur + 1; j <= k; j++) { const last = j === k; steps[ORDER[j]](tl, tt, last ? Math.max(1, d - (tt - t)) : quick, u); if (!last) tt += quick; }
    cur = k;
  } };
};
