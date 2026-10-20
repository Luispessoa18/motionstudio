/* Pacote SaaS / app / produto digital. */

/* ---------- CELULAR: telas de app que trocam entre cenas ---------- */
HEROES.celular = (u0, b) => {
  const ph = Math.min(b.h - 20, 700), pw = Math.round(ph * .49);
  const e = el('div', 'hc');
  const phone = el('div', 'hc-phone'); Object.assign(phone.style, { width: pw + 'px', height: ph + 'px', left: (b.w - pw) / 2 + 'px', top: (b.h - ph) / 2 + 'px' });
  const scr = el('div', 'hc-screen'); phone.appendChild(scr); phone.appendChild(el('div', 'hc-notch'));
  e.appendChild(phone);
  const brand = esc(BRAND.name || 'App');
  let curScr = null;
  const bar = `<div class="hc-status mn"><span>9:41</span><span>●●● ▮</span></div>`;
  const kinds = {
    inicio(u) {
      const tiles = (u.items && u.items.length ? u.items : [{ label: 'Resumo' }, { label: 'Tarefas' }, { label: 'Relatórios' }, { label: 'Ajustes' }]).slice(0, 4);
      return `${bar}<div class="hc-app">${esc(u.title || brand)}</div><div class="hc-hero">${esc(u.value || 'Olá!')}</div>${u.note ? `<div class="hc-sub">${esc(u.note)}</div>` : ''}
        <div class="hc-tiles">${tiles.map((x, i) => `<div class="hc-tile${i === 0 ? ' inv' : ''}"><b>${esc(x.label)}</b>${x.value ? `<span class="mn">${esc(x.value)}</span>` : ''}</div>`).join('')}</div>`;
    },
    lista(u) {
      const rows = (u.items && u.items.length ? u.items : [{ label: 'Item 1' }, { label: 'Item 2' }, { label: 'Item 3' }]).slice(0, 6);
      return `${bar}<div class="hc-app">${esc(u.title || brand)}</div><div class="hc-list">${rows.map((x, i) => `<div class="hc-row"><i class="${i === 0 ? 'inv' : ''}">${esc((x.label || '?').trim()[0] || '•')}</i><div><b>${esc(x.label)}</b>${x.sub ? `<small>${esc(x.sub)}</small>` : ''}</div>${x.value ? `<span class="mn">${esc(x.value)}</span>` : ''}</div>`).join('')}</div>`;
    },
    grafico(u) {
      const W = pw - 36, H = 170; let d = '', pts = [];
      for (let i = 0; i <= 16; i++) { const x = i / 16 * W, y = H - (H * .15 + H * .7 * (i / 16) ** 1.6 + Math.sin(i * 1.3) * 12); pts.push([x, y]); }
      d = 'M' + pts.map(p => p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' L');
      return `${bar}<div class="hc-app">${esc(u.title || brand)}</div><div class="k" style="margin-top:18px">${esc(u.label || 'Resultado')}</div><div class="hc-big mn">${esc(u.value || '')}</div>
        <svg class="hc-chart" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}"><path class="ar" d="${d} L${W} ${H} L0 ${H}Z" fill="${T.acc}" fill-opacity=".14"/><path class="ln" d="${d}" fill="none" stroke="${T.acc}" stroke-width="3" stroke-linejoin="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/></svg>
        <div class="hc-chips">${(u.items || []).slice(0, 3).map(x => `<span>${esc(x.label)}</span>`).join('')}</div>`;
    }
  };
  function screen(kind, u) { const s = el('div', 'hc-page', kinds[kind](u)); scr.appendChild(s); return s; }
  function animIn(tl, s, t, kind) {
    const kids = [...s.children];
    gsap.set(kids, { autoAlpha: 0, y: 18 });
    tl.to(kids, { autoAlpha: 1, y: 0, duration: .5, stagger: .08 }, t);
    const rows = s.querySelectorAll('.hc-row,.hc-tile');
    if (rows.length) { gsap.set(rows, { autoAlpha: 0, x: 24 }); tl.to(rows, { autoAlpha: 1, x: 0, duration: .45, stagger: .1 }, t + .3); }
    if (kind === 'grafico') {
      tl.to(s.querySelector('.ln'), { strokeDashoffset: 0, duration: 1.4, ease: 'power2.inOut' }, t + .4);
      gsap.set(s.querySelector('.ar'), { autoAlpha: 0 }); tl.to(s.querySelector('.ar'), { autoAlpha: 1, duration: .8 }, t + 1.2);
      const big = s.querySelector('.hc-big'); count(tl, big, parseNum(big.textContent), t + .3, 1.6);
    }
  }
  return { el: e, go(tl, state, t, d, u) {
    if (state === 'notificacao') {
      if (!curScr) { curScr = screen('inicio', u0); animIn(tl, curScr, t, 'inicio'); }
      const n = el('div', 'hc-notif', `<i class="inv">${brand[0] || '•'}</i><div><b>${esc(u.title || BRAND.name || 'Notificação')}</b><small>${esc(u.note || u.value || '')}</small></div>`);
      scr.appendChild(n);
      gsap.set(n, { yPercent: -160, autoAlpha: 0 });
      tl.to(n, { yPercent: 0, autoAlpha: 1, duration: .7, ease: 'back.out(1.6)' }, t + .3);
      tl.to(phone, { rotation: 2, duration: .06, yoyo: true, repeat: 5, ease: 'none' }, t + .35);
      return;
    }
    const kind = kinds[state] ? state : 'inicio';
    const s = screen(kind, u);
    if (curScr) {
      tl.to(curScr, { xPercent: -35, autoAlpha: 0, duration: .5, ease: 'power3.in' }, t);
      gsap.set(s, { xPercent: 100 });
      tl.to(s, { xPercent: 0, duration: .6, ease: 'expo.out' }, t + .35);
      animIn(tl, s, t + .45, kind);
    } else animIn(tl, s, t, kind);
    curScr = s;
  } };
};

/* ---------- PAINEL: dashboard vazio → KPIs → gráfico → destaque ---------- */
HEROES.painel = (u0, b) => {
  const ORDER = ['vazio', 'kpis', 'grafico', 'destaque'];
  const e = el('div', 'c-card hp');
  e.innerHTML = `<div class="hp-top"><i></i><i></i><i></i><b>${esc(u0.title || (BRAND.name ? BRAND.name + ' · Painel' : 'Painel'))}</b></div>
    <div class="hp-side">${'<i></i>'.repeat(5)}</div><div class="hp-main"><div class="hp-kpis">${'<div class="hp-k sk"></div>'.repeat(3)}</div><div class="hp-chart"></div></div>`;
  const chartBox = e.querySelector('.hp-chart'), kpiBox = e.querySelector('.hp-kpis');
  let cur = -1, CW = 0, CH = 0, peak = null, line = null, area = null;
  const steps = {
    vazio(tl, t, d) {
      const sk = [...e.querySelectorAll('.sk')];
      tl.fromTo(sk, { backgroundPosition: '200% 0' }, { backgroundPosition: '-200% 0', duration: 1.4, repeat: Math.max(0, Math.floor(d / 1.4)), ease: 'none', immediateRender: false }, t);
      gsap.set(chartBox, { opacity: .4 });
    },
    kpis(tl, t, d, u) {
      const items = (u.items && u.items.length ? u.items : [{ label: 'Usuários', value: '12.480' }, { label: 'Receita', value: 'R$ 84 mil' }, { label: 'Retenção', value: '92%' }]).slice(0, 3);
      const ks = items.map((it, i) => { const k = el('div', 'hp-k hp-kv' + (i === 0 ? ' hi' : ''), `<div class="k">${esc(it.label)}</div><div class="v mn">${esc(it.value || '')}</div>${it.sub ? `<small>${esc(it.sub)}</small>` : ''}`); kpiBox.appendChild(k); return k; });
      gsap.set(ks, { autoAlpha: 0, y: 14 });
      tl.to(ks, { autoAlpha: 1, y: 0, duration: .5, stagger: .15 }, t);
      tl.to(e.querySelectorAll('.sk'), { autoAlpha: 0, duration: .3 }, t + .3);
      ks.forEach((k, i) => count(tl, k.querySelector('.v'), parseNum(items[i].value), t + .1 + i * .15, 1.5));
      tl.to(chartBox, { opacity: 1, duration: .4 }, t + .5);
      tl.to(line, { strokeDashoffset: 0, duration: Math.min(2.2, d * .6), ease: 'power2.inOut' }, t + .7);
    },
    grafico(tl, t, d, u) {
      tl.to(chartBox, { opacity: 1, duration: .3 }, t);
      tl.to(line, { strokeDashoffset: 0, duration: Math.min(2, d * .6), ease: 'power2.inOut' }, t + .2);
      tl.fromTo(area, { autoAlpha: 0 }, { autoAlpha: 1, duration: .8, immediateRender: false }, t + Math.min(1.4, d * .5));
      if (u.label) { const lb = el('div', 'k hp-cl', esc(u.label)); chartBox.appendChild(lb); gsap.set(lb, { autoAlpha: 0 }); tl.to(lb, { autoAlpha: 1, duration: .5 }, t + .2); }
    },
    destaque(tl, t, d, u) {
      const tg = el('div', 'c-ftag inv hp-tag', esc(u.note || u.label || u.value || 'Recorde'));
      Object.assign(tg.style, { left: peak[0] + 'px', top: peak[1] + 'px' }); chartBox.appendChild(tg);
      const dot = el('div', 'hp-dot'); Object.assign(dot.style, { left: peak[0] + 'px', top: peak[1] + 'px' }); chartBox.appendChild(dot);
      gsap.set([tg, dot], { autoAlpha: 0 });
      tl.fromTo(dot, { scale: 0 }, { autoAlpha: 1, scale: 1, duration: .4, ease: 'back.out(3)', immediateRender: false }, t);
      tl.fromTo(tg, { scale: .6, xPercent: -50, yPercent: -150 }, { autoAlpha: 1, scale: 1, duration: .5, ease: 'back.out(2)', immediateRender: false }, t + .2);
      tl.to(dot, { boxShadow: `0 0 0 18px ${T.accGlow}`, duration: .6, repeat: Math.max(1, Math.floor(d / .6)), yoyo: true }, t + .5);
    }
  };
  return { el: e, layout() {
    CW = chartBox.clientWidth; CH = chartBox.clientHeight;
    const pts = []; for (let i = 0; i <= 24; i++) { const x = i / 24 * CW, y = CH - 20 - (CH - 60) * (.12 + .78 * (i / 24) ** 1.8 + .06 * Math.sin(i * 1.1)); pts.push([x, y]); }
    peak = pts.reduce((a, p) => p[1] < a[1] ? p : a, pts[0]);
    const d = 'M' + pts.map(p => p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' L');
    const NS = 'http://www.w3.org/2000/svg', svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('viewBox', `0 0 ${CW} ${CH}`); svg.setAttribute('width', CW); svg.setAttribute('height', CH);
    svg.innerHTML = [.25, .5, .75].map(f => `<line x1="0" x2="${CW}" y1="${CH * f}" y2="${CH * f}" stroke="${T.fg}" stroke-opacity=".08"/>`).join('') +
      `<path class="ar" d="${d} L${CW} ${CH} L0 ${CH}Z" fill="${T.acc}" fill-opacity=".14"/><path class="ln" d="${d}" fill="none" stroke="${T.acc}" stroke-width="3" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/>`;
    chartBox.appendChild(svg); line = svg.querySelector('.ln'); area = svg.querySelector('.ar'); gsap.set(area, { autoAlpha: 0 });
  }, go(tl, state, t, d, u) {
    let k = ORDER.indexOf(state); if (k < 0) k = Math.min(cur + 1, ORDER.length - 1);
    if (k <= cur) return;
    const n = k - cur, quick = Math.min(.9, d * .3 / n); let tt = t;
    for (let j = cur + 1; j <= k; j++) { const last = j === k; steps[ORDER[j]](tl, tt, last ? Math.max(1, d - (tt - t)) : quick, u); if (!last) tt += quick; }
    cur = k;
  } };
};
