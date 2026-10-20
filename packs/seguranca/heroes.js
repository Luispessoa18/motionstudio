/* Pacote segurança / fintech / cripto. */

/* ---------- GUARDA: transação atravessando barreiras até o veredito ---------- */
HEROES.guarda = (u0, b) => {
  const ORDER = ['fluxo', 'barreiras', 'bloqueio', 'aprovado', 'registro'];
  const y = b.h * .42, NW = 124, NH = 130;
  const e = el('div', 'hg');
  const agent = el('div', 'hg-node', `<b>${esc(u0.title || 'Agente')}</b><small>origem</small>`);
  const chain = el('div', 'hg-node', `<b>Blockchain</b><small>destino</small>`);
  Object.assign(agent.style, { left: 0, top: y - NH / 2 + 'px', width: NW + 'px', height: NH + 'px' });
  Object.assign(chain.style, { left: b.w - NW + 'px', top: y - NH / 2 + 'px', width: NW + 'px', height: NH + 'px' });
  const track = el('div', 'hg-track'); Object.assign(track.style, { left: NW + 'px', width: b.w - 2 * NW + 'px', top: y + 'px' });
  const pill = el('div', 'hg-pill inv mn', esc(u0.label || 'tx 0x4be1…a0f3'));
  e.append(track, agent, chain, pill);
  gsap.set([agent, chain, pill], { autoAlpha: 0 }); gsap.set(track, { scaleX: 0 });
  let gates = [], pw = 0, ph = 0, reasonEl = null;
  const px0 = () => NW + 14;
  const steps = {
    fluxo(tl, t, d) {
      pw = pill.offsetWidth; ph = pill.offsetHeight;
      Object.assign(pill.style, { left: px0() + 'px', top: y - ph / 2 + 'px' });
      tl.fromTo([agent, chain], { autoAlpha: 0, y: 24 }, { autoAlpha: 1, y: 0, duration: .7, stagger: .15, immediateRender: false }, t);
      tl.to(track, { scaleX: 1, duration: .9, ease: 'expo.inOut' }, t + .3);
      tl.fromTo(pill, { autoAlpha: 0, scale: .5 }, { autoAlpha: 1, scale: 1, duration: .45, ease: 'back.out(2)', immediateRender: false }, t + .9);
      tl.to(pill, { x: 30, duration: Math.max(.6, d - 1.4), ease: 'power1.inOut' }, t + 1.3);
    },
    barreiras(tl, t, d, u) {
      const names = (u.items && u.items.length ? u.items.map(i => i.label) : ['Reputação', 'Prompt Guard', 'IA de intenção', 'Simulação']).slice(0, 5);
      const n = names.length, x0 = NW + 30, span = b.w - 2 * NW - 60;
      gates = names.map((nm, i) => {
        const flag = /^!/.test(nm);
        const gx = x0 + span * (i + .5) / n;
        const g = el('div', 'hg-gate', `<i></i><span class="hg-ic"></span><em>${esc(nm.replace(/^!\s*/, ''))}</em>`);
        Object.assign(g.style, { left: gx + 'px', top: y + 'px' }); g._x = gx; g._flag = flag;
        // pouco espaço (vertical): rótulos alternam acima e abaixo da barreira, com o dobro da largura
        const tight = span / n < 120, em = g.querySelector('em'), lw = Math.min(170, (tight ? 2 : 1) * span / n - 8);
        Object.assign(em.style, { width: lw + 'px', left: -lw / 2 + 'px' });
        if (tight && i % 2) em.classList.add('up');
        e.insertBefore(g, pill); return g;
      });
      gsap.set(gates, { autoAlpha: 0, scaleY: 0 });
      tl.to(gates, { autoAlpha: 1, scaleY: 1, duration: .5, stagger: .12, ease: 'expo.out' }, t);
      let tt = t + .4 + n * .12;
      const per = Math.max(.5, Math.min(1.1, (d - (tt - t) - .2) / n));
      for (const g of gates) {
        const tx = g._x - px0() - pw / 2;
        tl.to(pill, { x: tx, duration: per * .55, ease: 'power2.inOut' }, tt);
        tl.fromTo(g.querySelector('i'), { backgroundColor: T.fg }, { backgroundColor: T.acc, boxShadow: `0 0 24px ${T.accGlow}`, duration: .15, immediateRender: false }, tt + per * .5);
        const ic = g.querySelector('.hg-ic');
        ic.textContent = g._flag ? '!' : '✓';
        if (g._flag) ic.classList.add('inv');
        tl.fromTo(ic, { autoAlpha: 0, scale: .4 }, { autoAlpha: 1, scale: 1, duration: .3, ease: 'back.out(3)', immediateRender: false }, tt + per * .6);
        tt += per;
        if (g._flag) break;
        tl.to(g.querySelector('i'), { backgroundColor: T.fg, boxShadow: '0 0 0px rgba(0,0,0,0)', duration: .3 }, tt);
      }
      gsap.set(gates.map(g => g.querySelector('.hg-ic')), { autoAlpha: 0 });
    },
    bloqueio(tl, t, d, u) {
      const st = el('div', 'hg-stamp inv', esc(u.status || 'BLOQUEADO'));
      Object.assign(st.style, { left: b.w / 2 + 'px', top: y - 230 + 'px' }); e.appendChild(st);
      gsap.set(st, { autoAlpha: 0, xPercent: -50 });
      tl.fromTo(st, { scale: 2, rotation: -10 }, { autoAlpha: 1, scale: 1, rotation: -4, duration: .35, ease: 'power4.in', immediateRender: false }, t + .1);
      tl.to(pill, { x: '+=10', duration: .05, yoyo: true, repeat: 7, ease: 'none' }, t + .45);
      tl.to([chain, track], { opacity: .25, duration: .6 }, t + .5);
      if (u.reason || u.note) {
        const r = el('div', 'hg-reason', esc(u.reason || u.note)); Object.assign(r.style, { top: y + 200 + 'px' }); e.appendChild(r); reasonEl = r;
        gsap.set(r, { autoAlpha: 0 }); tl.to(r, { autoAlpha: 1, duration: .6 }, t + .8);
      }
    },
    aprovado(tl, t, d, u) {
      const tx = b.w - NW - px0() - pw - 14;
      tl.to(pill, { x: tx, duration: .9, ease: 'expo.inOut' }, t);
      tl.to(chain, { borderColor: T.acc, boxShadow: `0 0 44px ${T.accGlow}`, duration: .4 }, t + .8);
      const st = el('div', 'hg-stamp inv', esc(u.status || 'APROVADO'));
      Object.assign(st.style, { left: b.w / 2 + 'px', top: y - 230 + 'px' }); e.appendChild(st);
      gsap.set(st, { autoAlpha: 0, xPercent: -50 });
      tl.fromTo(st, { scale: .6 }, { autoAlpha: 1, scale: 1, duration: .5, ease: 'back.out(2)', immediateRender: false }, t + 1);
    },
    registro(tl, t, d, u) {
      if (reasonEl) tl.to(reasonEl, { autoAlpha: 0, duration: .3 }, t);
      const row = el('div', 'hg-chain'); Object.assign(row.style, { top: y + 190 + 'px' }); e.appendChild(row);
      const blocks = [3, 2, 1].map(k => el('div', 'hg-blk mn', `#${String(21483902 - k).replace(/\B(?=(\d{3})+(?!\d))/g, '.')}`));
      const last = el('div', 'hg-blk hg-new inv mn', `${esc(u.value || '0x9c1e…44b7')}<small>${esc(u.label || 'veredito registrado')}</small>`);
      blocks.forEach(k => row.appendChild(k)); row.appendChild(last);
      gsap.set([...blocks, last], { autoAlpha: 0 });
      tl.to(blocks, { autoAlpha: 1, duration: .4, stagger: .12 }, t);
      tl.fromTo(last, { x: 80, autoAlpha: 0 }, { x: 0, autoAlpha: 1, duration: .7, ease: 'expo.out', immediateRender: false }, t + .5);
      tl.fromTo(last, { boxShadow: '0 0 0px rgba(0,0,0,0)' }, { boxShadow: `0 0 40px ${T.accGlow}`, duration: .5, yoyo: true, repeat: 1, immediateRender: false }, t + 1.2);
    }
  };
  const done = new Set();
  return { el: e, go(tl, state, t, d, u) {
    if (!steps[state]) state = ['fluxo', 'barreiras', 'bloqueio', 'registro'].find(x => !done.has(x)) || 'registro';
    const path = ORDER.slice(0, ORDER.indexOf(state)).filter(p => (p === 'fluxo' || p === 'barreiras') && !done.has(p));
    if (!done.has(state)) path.push(state);
    if (!path.length) return;
    const quick = Math.min(1.6, d * .4 / Math.max(1, path.length - 1));
    let tt = t;
    path.forEach((p, i) => { const last = i === path.length - 1; steps[p](tl, tt, last ? Math.max(1, d - (tt - t)) : quick, u); if (!last) tt += quick; done.add(p); });
  } };
};

/* ---------- RADAR: varredura → ameaças → neutralizado ---------- */
HEROES.radar = (u0, b) => {
  const ORDER = ['varredura', 'ameacas', 'neutralizado'];
  const R = Math.min(b.w * .44, b.h * .44), cx = b.w * .5, cy = b.h * .5;
  const e = el('div', 'hr');
  const NS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(NS, 'svg'); svg.setAttribute('viewBox', `0 0 ${b.w} ${b.h}`); svg.setAttribute('width', b.w); svg.setAttribute('height', b.h);
  svg.innerHTML = [1, .74, .48, .22].map(f => `<circle class="rr" cx="${cx}" cy="${cy}" r="${R * f}" fill="none" stroke="${T.fg}" stroke-opacity=".22"/>`).join('') +
    `<line class="rr" x1="${cx - R}" y1="${cy}" x2="${cx + R}" y2="${cy}" stroke="${T.fg}" stroke-opacity=".14"/><line class="rr" x1="${cx}" y1="${cy - R}" x2="${cx}" y2="${cy + R}" stroke="${T.fg}" stroke-opacity=".14"/>`;
  const sweep = el('div', 'hr-sweep'); Object.assign(sweep.style, { left: cx - R + 'px', top: cy - R + 'px', width: 2 * R + 'px', height: 2 * R + 'px' });
  const core = el('div', 'hr-core'); Object.assign(core.style, { left: cx + 'px', top: cy + 'px' });
  e.append(svg, sweep, core);
  const rr = [...svg.querySelectorAll('.rr')];
  gsap.set(rr, { autoAlpha: 0 }); gsap.set(sweep, { autoAlpha: 0 });
  let cur = -1, dots = [];
  const spin = (tl, t, d, k = 1) => tl.to(sweep, { rotation: `+=${360 * Math.max(1, Math.round(d / 2.2 * k))}`, duration: d + .6, ease: 'none' }, t);
  const steps = {
    varredura(tl, t, d) {
      tl.fromTo(rr, { scale: .2 }, { scale: 1, autoAlpha: 1, svgOrigin: `${cx} ${cy}`, duration: .9, stagger: .08, immediateRender: false }, t);
      tl.to(sweep, { autoAlpha: 1, duration: .6 }, t + .4);
      spin(tl, t + .4, d);
    },
    ameacas(tl, t, d, u) {
      spin(tl, t, d);
      const items = (u.items && u.items.length ? u.items : [{ label: 'Contrato malicioso' }, { label: 'Prompt injetado' }, { label: 'Endereço sinalizado' }]).slice(0, 5);
      dots = items.map((it, i) => {
        const a = -2.2 + i * (Math.PI * 2 / items.length), r = R * (.4 + .45 * ((i * 37) % 10) / 10);
        const d0 = el('div', 'hr-dot', `<span class="c-ftag c-card">${esc(it.label)}</span>`);
        Object.assign(d0.style, { left: cx + Math.cos(a) * r + 'px', top: cy + Math.sin(a) * r + 'px' });
        if (Math.cos(a) < 0) d0.classList.add('l');
        e.appendChild(d0); return d0;
      });
      gsap.set(dots, { autoAlpha: 0, scale: 0 });
      tl.to(dots, { autoAlpha: 1, scale: 1, duration: .4, ease: 'back.out(3)', stagger: Math.min(.45, d * .6 / dots.length) }, t + .2);
    },
    neutralizado(tl, t, d, u) {
      spin(tl, t, d, .5);
      dots.forEach(x => x.classList.add('done'));
      tl.to(dots, { opacity: .35, duration: .4, stagger: .1 }, t + .2);
      tl.to(dots.map(x => x.querySelector('span')), { textDecoration: 'line-through', duration: .01, stagger: .1 }, t + .2);
      const badge = el('div', 'hr-badge inv', esc(u.status || 'PROTEGIDO')); Object.assign(badge.style, { left: cx + 'px', top: cy + 'px' }); e.appendChild(badge);
      gsap.set(badge, { autoAlpha: 0, xPercent: -50, yPercent: -50, scale: .5 });
      tl.to(badge, { autoAlpha: 1, scale: 1, duration: .6, ease: 'back.out(2)' }, t + .7);
      tl.to(rr, { stroke: T.acc, duration: .3, stagger: .05, yoyo: true, repeat: 1 }, t + .7);
    }
  };
  return { el: e, go(tl, state, t, d, u) {
    let k = ORDER.indexOf(state); if (k < 0) k = Math.min(cur + 1, ORDER.length - 1);
    if (k <= cur) { spin(tl, t, d); return; }
    const n = k - cur, quick = Math.min(1, d * .3 / n); let tt = t;
    for (let j = cur + 1; j <= k; j++) { const last = j === k; steps[ORDER[j]](tl, tt, last ? Math.max(1, d - (tt - t)) : quick, u); if (!last) tt += quick; }
    cur = k;
  } };
};
