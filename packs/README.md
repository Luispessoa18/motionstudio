# Como criar um pacote de domínio

Um pacote é uma pasta em `packs/<id>/` com quatro arquivos:

```
packs/meu-setor/
├── pack.json        descrição para a IA (heróis, estados, metáforas, tom)
├── heroes.js        código dos heróis
├── heroes.css       estilos dos heróis
└── examples/*.json  1 ou 2 roteiros-exemplo bem feitos
```

O servidor carrega tudo ao iniciar. Reinicie depois de mudar um pacote.

## pack.json

```json
{
  "id": "meu-setor",
  "name": "Meu setor",
  "description": "Para que tipo de negócio serve.",
  "keywords": ["palavras", "que", "aparecem", "no", "pitch"],
  "font": "grotesk",
  "particles": "dash",
  "heroes": {
    "nome": {
      "desc": "O que o herói é e quando usar.",
      "states": { "estado1": "o que acontece", "estado2": "o que acontece" },
      "fields": "quais campos do ui cada estado usa"
    }
  },
  "metaphors": ["boas escolhas visuais neste setor"],
  "notes": "tom de voz e o que evitar"
}
```

A ordem dos estados em `states` é a ordem da história. A detecção automática soma quantas vezes cada palavra de `keywords` aparece no pitch; o pacote precisa de pelo menos 2 ocorrências para ganhar do `geral`.

## heroes.js

O arquivo é injetado dentro do runtime, então tem acesso direto a `el`, `esc`, `gsap`, `T` (tema), `PORT` (vertical?), `count`, `parseNum`, `FRAME`, `rnd`, `clamp` e `BRAND`.

```js
HEROES.nome = (u0, box) => {          // u0 = ui da primeira cena; box = {w, h} da área do herói
  const e = el('div', 'meu-heroi');   // monte o DOM aqui
  let cur = -1;
  const ORDER = ['estado1', 'estado2'];
  const steps = {
    estado1(tl, t, d, u) { /* gsap.set nos estados iniciais + tl.to(...) a partir de t, durante d */ },
    estado2(tl, t, d, u) { /* ... */ }
  };
  return {
    el: e,
    layout() { /* opcional: medir elementos depois que estão na tela */ },
    go(tl, state, t, d, u) {          // chamado uma vez por cena
      let k = ORDER.indexOf(state); if (k < 0) k = Math.min(cur + 1, ORDER.length - 1);
      if (k <= cur) return;
      // se a cena pulou estados, rode os anteriores rápido antes
      const quick = Math.min(.9, d * .3 / (k - cur)); let tt = t;
      for (let j = cur + 1; j <= k; j++) { const last = j === k; steps[ORDER[j]](tl, tt, last ? d - (tt - t) : quick, u); if (!last) tt += quick; }
      cur = k;
    }
  };
};
```

Regras que evitam bugs:

- Use sempre referências diretas a elementos, nunca seletores globais como `'.classe'` (o echo trail clona elementos e um seletor pegaria os clones).
- Animações contínuas (câmera 3D, progresso de linha) devem ser escritas numa função adicionada a `FRAME`, não em `onUpdate`. Assim o render de MP4, que pula direto para cada quadro, desenha certo.
- Use `immediateRender: false` em `tl.fromTo` e defina estados iniciais com `gsap.set` na hora de montar.
- Cores via `T.acc`, `T.fg`, `T.bg`, `T.accGlow` ou variáveis CSS (`var(--acc)`), para o herói funcionar com qualquer marca.

## Exemplos

Os exemplos são o que mais melhora um modelo pequeno. Escreva 1 ou 2 roteiros completos que seguem a skill (`skills/roteiro/SKILL.md`): tensão antes da solução, headlines curtas, herói em cenas seguidas com estados em ordem. A IA aprende o ritmo com eles.
