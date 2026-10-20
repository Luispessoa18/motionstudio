---
name: tipografia
description: Regras de tipografia para motion legível. Use ao decidir tamanho, peso, alinhamento e se o texto precisa de barra ou bloco atrás.
---

# Tipografia em motion: grande, forte e sempre legível

Quem assiste vê a frase por 3 a 5 segundos, muitas vezes no celular e sem som. Se precisa forçar a vista, a cena falhou.

## 1. Tamanho

- A headline é o maior elemento da cena. Ela nunca fica pequena para "caber": se não cabe, a frase está longa demais.
- 3 a 7 palavras. Uma frase de 4 palavras fica gigante; uma de 12 vira texto corrido.
- A palavra `*destacada*` é uma só e carrega o sentido.

## 2. Contraste: quando colocar algo ATRÁS do texto (`text_bg`)

Use uma base atrás do texto sempre que o fundo competir com a letra:

| Situação | Use |
|---|---|
| Foto em tela cheia com muitos detalhes ou clara | `glass` (faixa de vidro escuro) ou `bar` |
| Fundo claro + cor de destaque clara | `bar` (faixa sólida na cor de destaque, texto em tinta contrastante) |
| Cena de tensão, alerta, manchete | `bar` ou `block` (cara de manchete, estilo Reels) |
| Frase de impacto com uma palavra-chave | `highlight` (faixa só atrás da palavra) |
| Cena editorial, luxo, calma | `none` ou `outline` (cantos finos), se o fundo for liso |

`bar` e `block` são fortes: no máximo em 1 de cada 3 cenas, para não virar padrão.

## 3. Peso e família

- Fundo claro pede peso firme (semibold ou mais). Letra fina sobre fundo claro some.
- Serifadas (elegant, luxury) só em headline grande; legendas vão na fonte sem serifa.
- Caixa alta só em selos (eyebrow) e palavras de impacto (big_word), nunca em frases inteiras.

## 4. Alinhamento (`align`)

- `left`: padrão de leitura, cenas com componente ao lado.
- `center`: impacto, frase sozinha, final de bloco, vertical sem componente.
- `right`: raro; só para quebrar o padrão numa cena de contraste ("antes" à esquerda, "depois" à direita).

## 5. Quebra de linha

- A palavra destacada fica no fim da frase ou sozinha na linha: é onde o olho para.
- Evite deixar uma palavra curta sozinha na última linha ("de", "e").

## 6. Movimento e leitura

- O texto precisa estar parado e completo por pelo menos 1,5s antes da cena sair.
- Efeitos letra a letra (`split`, `flip`, `wave`, `type`) só em frases curtas (até 5 palavras).
- `kinetic` mostra palavra por palavra: só para frases de 2 a 5 palavras com ritmo.
