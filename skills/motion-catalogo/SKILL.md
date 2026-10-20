---
name: motion-catalogo
description: Catálogo dos movimentos que o runtime do Motion Studio sabe fazer (efeito de texto, base do texto, câmera, ênfase, ornamento, alinhamento, transição), com quando usar cada um.
---

# Catálogo de motion

Cada cena tem um objeto `motion`. Use só os valores abaixo.

## `text_fx`: como a headline entra

| Valor | O que acontece | Quando usar |
|---|---|---|
| `rise` | palavras sobem de uma máscara | neutro, mecanismo, qualquer cena calma |
| `blur` | palavras surgem do desfoque | elegante, luxo, bem-estar, mundo |
| `bars` | barras coloridas varrem cada linha e revelam o texto | tensão, manchete, alerta |
| `type` | máquina de escrever com cursor | dados, tecnologia, mensagens, "agora" |
| `split` | letras caem girando e se encaixam | jovem, divertido, queda (frases curtas) |
| `marker` | sobe e um marca-texto passa na palavra-chave | educação, explicação, destaque didático |
| `underline` | sublinhado se desenha na palavra-chave | prova, afirmação, clareza |
| `scale` | palavras chegam grandes e assentam com impacto | impacto, prova, número |
| `rotate` | palavras giram em 3D (eixo horizontal) e encaixam | mudança, virada, "vira" |
| `flip` | letras viram como placas (eixo vertical) | transformação, troca, antes/depois |
| `kinetic` | cada palavra aparece sozinha e gigante, depois a frase se monta | ritmo, frases de 2 a 5 palavras, abertura |
| `stack` | palavras empilham em tamanhos alternados e assentam | crescimento, "tudo junto", acúmulo |
| `wave` | letras sobem em onda | fluidez, conexão, natureza, água |
| `zoom` | o texto vem de trás atravessando a câmera | virada, revelação, velocidade |
| `slice` | o texto entra cortado ao meio e as metades se juntam | tensão, quebra, problema |

## `text_bg`: o que fica atrás do texto

`none` · `bar` (faixa sólida por linha na cor de destaque) · `block` (um bloco único atrás da headline) · `highlight` (faixa só atrás da palavra-chave) · `glass` (faixa de vidro escuro, ótima sobre foto) · `outline` (cantos finos em volta do texto).

## `camera`: movimento do conjunto da cena

`still` (parado) · `push_in` (aproxima devagar) · `pull_out` (afasta devagar) · `drift` (desliza de lado) · `tilt` (entra inclinado e endireita) · `spin_in` (a cena entra girando 90° e assenta: use pouco) · `shake` (treme no impacto: tensão) · `parallax` (texto e componente em velocidades diferentes).

## `emphasis`: gesto da palavra `*destacada*`

`none` · `pop` (pula e volta) · `spin` (dá uma volta inteira) · `circle` (um círculo desenhado à mão em volta) · `strike` (um risco passa por cima: "o jeito antigo") · `color_swap` (a cor muda de destaque para invertido) · `glow` (brilho pulsando) · `underline_draw` (traço grosso que se desenha embaixo).

## `ornament`: elemento extra (vários giram)

`none` · `spin_ring` (anel tracejado girando atrás da palavra-chave) · `orbit_dots` (pontos orbitando) · `rotating_badge` (selo circular com texto girando) · `corner_brackets` (cantoneiras que emolduram o texto) · `big_number_bg` (o número da cena gigante e vazado ao fundo) · `grid_sweep` (uma grade que varre o fundo).

## `align`

`left` · `center` · `right` (veja a skill `tipografia`).

## `transition`: como esta cena ENTRA (corte a partir da anterior)

`cut` · `fade` · `wipe` (painel colorido varre a tela) · `slide` (a nova cena desliza por cima) · `push` (a nova empurra a anterior para fora) · `zoom` (a câmera atravessa) · `iris` (círculo que abre) · `spin` (gira para fora e a nova entra girando) · `blinds` (faixas que fecham e abrem) · `flash` (clarão) · `glitch` (tremor digital) · `match` (a palavra-chave da cena anterior cresce até cobrir a tela e vira o fundo desta).

Detalhes de quando usar cada transição estão na skill `transicoes`.
