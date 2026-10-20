# Motion Studio

Gera motions de lançamento em HTML (e MP4) a partir de um pitch, um logo e imagens de referência, usando uma IA local via Ollama.

A IA só escreve o **roteiro em JSON** (headlines, legendas e qual componente de UI ilustra cada cena). Toda a animação fica num runtime fixo e testado (`runtime/motion.js`). Por isso um modelo de 7B a 14B dá conta: escrever copy e escolher componente é fácil; programar animação, não.

## O que ele faz

- Interface web para anexar logo, imagens de referência e o pitch.
- Recorta o fundo do logo, deixa legível sobre fundo escuro (texto preto vira branco) e detecta a cor de destaque.
- Descreve o estilo das referências com um modelo de visão local (opcional) e permite usar as imagens dentro das cenas.
- Formato 16:9 (1920×1080) ou 9:16 (1080×1920), trocável depois de gerar, sem chamar a IA de novo.
- Duração automática ou fixa (15 a 90s).
- Editor do roteiro em JSON para ajustar textos e componentes na mão.
- Exporta HTML autocontido e MP4 (H.264), renderizado quadro a quadro em paralelo.

## Requisitos

- Python 3.10+
- [Ollama](https://ollama.com) rodando localmente
- ffmpeg: vem junto pelo pacote `imageio-ffmpeg` (se houver um ffmpeg no PATH, ele é usado)
- Internet só para as fontes do Google Fonts (sem internet, cai para fontes do sistema)

## Instalação

```bash
cd motion-studio
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium     # use "playwright install --with-deps chromium" se faltar biblioteca no Linux

ollama pull qwen2.5:14b         # roteirista (recomendado). Com pouca VRAM: qwen2.5:7b
ollama pull qwen2.5vl:7b        # opcional: lê as imagens de referência
```

## Rodar

```bash
./run.sh          # Linux/macOS
run.bat           # Windows (cria o .venv e instala tudo na primeira vez)
# ou: uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Abra http://localhost:8000.

Para testar sem IA (usa `examples/demo.story.json`):

```bash
MOTION_LLM=mock ./run.sh
```

## Variáveis de ambiente

| Variável | Padrão | Para quê |
|---|---|---|
| `OLLAMA_URL` | `http://localhost:11434` | Endereço do Ollama |
| `MOTION_MODEL` | `qwen2.5:14b` | Modelo que escreve o roteiro |
| `VISION_MODEL` | `qwen2.5vl:7b` | Modelo de visão; deixe vazio para desligar |
| `MOTION_LLM` | `ollama` | `mock` para rodar sem IA |
| `MOTION_NUM_CTX` | `12288` | Contexto do modelo |
| `MOTION_TWO_STAGE` | `1` | `0` desliga o plano de direção |
| `MOTION_SCENE_DIRECTOR` | `per_scene` | Diretor de cena: `per_scene` (uma chamada por cena), `batch` (uma chamada para todas) ou `off` (só o sorteio pela semente) |
| `MOTION_RENDER_WORKERS` | metade dos núcleos (máx. 4) | Processos de render em paralelo |
| `CHROMIUM_PATH` | — | Usar um Chromium específico no render |
| `MOTION_PROJECTS_DIR` | `./projects` | Onde ficam os projetos |
| `ELEVENLABS_API_KEY` | — | Liga a narração (também pela tela Configurações) |
| `ELEVENLABS_VOICE_ID` | primeira voz da conta | Voz padrão |
| `ELEVENLABS_MODEL` | `eleven_multilingual_v2` | Modelo de voz |
| `TTS_ENGINE` | `auto` | Motor de voz padrão: `auto` (ElevenLabs se houver chave, senão KittenTTS), `kitten` ou `elevenlabs` |
| `KITTEN_MODEL` | `KittenML/kitten-tts-2` | Modelo da KittenTTS (o único com português e clonagem) |
| `KITTEN_PYTHON` | procura sozinho | Python onde o `kittenml` está instalado (se não for o do app) |
| `KITTEN_VOICE` | `Portuguese` | Voz nativa padrão da KittenTTS |
| `KITTEN_PRESET` | `stable` | `stable` ou `expressive` |
| `MOTION_VOICES_DIR` | `./voices` | Onde ficam as vozes clonadas |
| `PEXELS_API_KEY` / `PIXABAY_API_KEY` | — | Fotos de banco no componente `image` |
| `MOTION_SFX_DIR` / `MOTION_MUSIC_DIR` | `./sfx`, `./music` | Bibliotecas de efeitos e músicas |

## Projetos, áudio e exportação

- **Projetos:** cada projeto fica salvo em `projects/<id>` e é atualizado a cada alteração. O botão *Projetos* lista, reabre, apaga, exporta (.zip) e importa projetos. O endereço `/#<id>` reabre direto.
- **Exportar:** MP4 (H.264 + AAC) ou WebM (VP9 + Opus), com a trilha de áudio.
- **Narração (ElevenLabs):** com a narração ligada, a IA escreve `narration` em cada cena e `outro_narration` no fim. A fala complementa a tela (contexto, consequência, exemplo) em vez de ler a headline, e cada cena dura pelo menos o tempo da fala. As falas ficam em cache: só textos alterados gastam créditos de novo.
- **Narração local (KittenTTS):** com o pacote `kittenml` instalado (`pip install kittenml`, em qualquer Python da máquina; o app procura sozinho), a narração roda no seu computador, sem chave. São 47 vozes nativas, entre elas `Portuguese`, que fala português. A primeira vez baixa o modelo (~1 GB). Em CPU a síntese é lenta, ~15 a 20s para cada segundo de fala, mas cada fala fica em cache e só textos alterados são gerados de novo. O modelo roda num processo separado (`app/kitten_worker.py`, log em `kitten.log`) que fica carregado entre as falas.
- **Voz clonada:** em *Configurações → Vozes clonadas*, grave pelo navegador (lendo o texto que aparece na tela) ou envie um arquivo de 10 a 30s de uma pessoa só. Com a transcrição do que é falado, a semelhança é bem maior (na gravação pelo navegador ela já vem pronta). A voz entra na lista de narração do projeto. Use só vozes de quem autorizou.
- **Efeitos sonoros:** arquivos de `sfx/` entram nos momentos das animações (intro do logo, troca de cena, entrada dos componentes, palavra de impacto, logo final). O papel de cada arquivo vem do nome: `intro`/`cue`/`tone`, `whoosh`/`swoosh`, `impact`/`hit`/`boom`, `pop`/`click`/`tick`. Para forçar, comece o nome do arquivo com o papel (ex. `impact-grave.mp3`).
- **Música:** arquivos de `music/`. Entra com fade, faz loop se for curta e abaixa sozinha enquanto o locutor fala (ducking).
- **Fotos e ícones:** com chave do Pexels ou do Pixabay, a IA pode pedir fotos reais (`"ui": {"type": "image", "stock": "server room"}`); você também pode escrever `stock` no JSON do roteiro. Itens de `cards`, `checklist` e `flow` aceitam `"icon"` com um nome Lucide (ex. `shield-check`), baixado do Iconify sem chave.

## Como funciona

```
pitch + logo + referências
        │
        ├─ brand.py   → logo.png transparente, cor de destaque
        ├─ packs.py   → escolhe o pacote de domínio pelo pitch
        ├─ llm.py     → (visão) descrição do estilo das referências
        │             → (texto) plano de direção, depois roteiro JSON
        │               (skills + pacote + exemplos no prompt, saída forçada por JSON Schema)
        │             → (texto) diretor de cena: 3 ideias de motion por cena, uma chamada por cena
        ├─ seeds.py   → receita do filme e semente de cada cena; sorteio, anti-repetição
        ├─ story.py   → limpa o roteiro, corrige tipos, calcula o tempo de cada cena
        ├─ builder.py → HTML único com runtime + GSAP + logo + imagens embutidos
        └─ render.py  → Playwright avança a timeline quadro a quadro → ffmpeg → MP4
```

Se o modelo devolver JSON inválido, o sistema mostra o erro para ele e pede correção (até 3 tentativas). Mesmo com JSON válido, `story.py` normaliza tudo: corta textos longos, descarta componentes sem dados e infere o tipo quando ele vem errado.

## Pacotes de domínio

Cada pacote traz **heróis**: objetos visuais que atravessam várias cenas seguidas, mudando de estado. É isso que dá cara de filme ao motion, em vez de uma sequência de cartões.

| Pacote | Heróis e estados |
|---|---|
| Imobiliário | `lote` (planta → iso → recuos → prédio → VGV), `mapa` (cidade → pin → raio → pontos de interesse) |
| Segurança / Cripto | `guarda` (fluxo → barreiras → bloqueio ou aprovado → registro on-chain), `radar` (varredura → ameaças → neutralizado) |
| SaaS / App | `celular` (início, lista, gráfico, notificação), `painel` (vazio → KPIs → gráfico → destaque) |
| Finanças | `grafico` (histórico → queda → virada → meta), `carteira` (composição → destaque → total) |
| Geral | só os componentes básicos |

O pacote é detectado pelas palavras do pitch ou escolhido na interface. Cada um tem roteiros-exemplo em `packs/<id>/examples/`, que entram no prompt como referência de ritmo e escolha visual. Para criar um pacote novo, veja `packs/README.md`.

## Skills (guias da IA)

Os guias ficam em `skills/<nome>/SKILL.md` e entram no prompt de cada etapa (todos têm o cabeçalho no formato de skill do Claude, então também servem para outras IAs):

| Skill | Etapa | O que ensina |
|---|---|---|
| `roteiro` | plano e roteiro | arco (mundo, tensão, virada, mecanismo, prova, impacto), batidas, headlines curtas, visual que prova a frase |
| `variacao` | plano e roteiro | como usar o ângulo e a receita da semente para que duas versões não saiam iguais |
| `direcao-cena` | diretor de cena | ler o verbo e a energia da frase, coreografia em camadas, o que gira, 3 ideias diferentes por cena |
| `tipografia` | diretor de cena | texto grande, quando pôr barra/bloco/vidro atrás do texto, peso e contraste por fundo |
| `motion-catalogo` | diretor de cena | todos os efeitos que o runtime sabe fazer, com quando usar cada um |
| `transicoes` | diretor de cena | gramática de transição entre cenas (energia → corte) |

A geração acontece em três etapas:

1. **Plano de direção:** a IA divide o pitch em batidas e escolhe o visual de cada uma. O plano aparece na interface.
2. **Roteiro:** com o plano, os exemplos do pacote e o checklist da skill, ela escreve o JSON final (com a `funcao` de cada cena).
3. **Diretor de cena:** para cada cena, uma chamada própria com o contexto do filme, a cena anterior e a próxima, a receita da semente e 3 "sementes de ideia". A IA escreve a `direction` e propõe 3 ideias de motion (`ideas`), escolhendo uma (`pick`). Se a chamada falhar, a cena recebe um motion sorteado pela semente.

Desligue a primeira etapa com `MOTION_TWO_STAGE=0` e use `MOTION_SCENE_DIRECTOR=batch` se quiser mais velocidade.

## Sementes e motion por cena

- **Semente do projeto** → **receita visual** do filme (Editorial calmo, Kinetic bold, Tech glitch, Revista/colagem, Cinemático, Pop jovem, Suíço minimal, Luxo respirado, Manchete, Orgânico fluido) + **ângulo criativo** (16 formas de contar a história). A receita é filtrada pelo contexto: categoria, estilo das referências e fonte (luxo nunca recebe glitch, tremida ou letras pulando).
- **Semente de cada cena**, derivada da do projeto: mudar uma cena não mexe nas outras. A mesma semente sempre gera o mesmo resultado.
- **Interface:** campo *Semente* (marque *manter* para reaproveitar), **Novo roteiro** (outro texto e outra receita), **Novo motion** (mesmo texto, a IA dirige cada cena de novo) e o painel **Motion por cena**: selects para cada campo, as 3 ideias como botões, 🎲 *Sortear esta cena* (sem IA, instantâneo) e *Repensar com a IA* (3 ideias novas só para aquela cena).
- **Anti-repetição:** cenas vizinhas não repetem efeito de texto, câmera nem transição; barra/bloco atrás do texto no máximo 1 a cada 3 cenas; elementos girando em no máximo metade das cenas; no máximo 2 transições fortes seguidas.

Cada cena tem um objeto `motion`:

| Campo | Valores |
|---|---|
| `text_fx` | rise, bars, blur, type, split, marker, underline, scale, rotate, flip, kinetic, stack, wave, zoom, slice |
| `text_bg` | none, bar (faixa por linha), block, highlight (só a palavra-chave), glass, outline |
| `camera` | still, push_in, pull_out, drift, tilt, spin_in, shake, parallax |
| `emphasis` | none, pop, spin, circle (desenhado à mão), strike, color_swap, glow, underline_draw |
| `ornament` | none, spin_ring, orbit_dots, rotating_badge, corner_brackets, big_number_bg, grid_sweep |
| `align` | left, center, right |
| `transition` | cut, fade, wipe, slide, push, zoom, iris, spin, blinds, flash, glitch, match |

Os efeitos sonoros seguem a transição (whoosh em wipe/push/spin, impacto em flash/zoom/match/glitch).

## Componentes disponíveis

| Tipo | Uso |
|---|---|
| `counter` | Número grande que conta do zero, com barra dividida opcional |
| `cards` | 2 a 5 cartões de dados (valores numéricos animam sozinhos) |
| `bars` | Barras horizontais de comparação |
| `chat` | Conversa de agente/app, com mensagem destacada |
| `flow` | Nós ligados com uma pílula que viaja até o nó principal |
| `checklist` | Lista com checks desenhados e selo opcional |
| `steps` | Painel com etapas mostradas uma por vez (linhas com `!` viram alerta) |
| `table` | Tabela antes/depois (células com `!` ganham destaque) |
| `verdict` | Bloco de resultado ("BLOQUEADO", "APROVADO") com selo |
| `feed` | Lista de eventos rolando cada vez mais rápido |
| `image` | Imagem de referência num mockup de navegador ou celular |
| `big_word` | Tela invertida com uma palavra gigante montada em facetas |
| `none` | Só a headline, em tela cheia |
| `hero` | Herói do pacote (`hero` + `state`) |

Abertura (logo montado em facetas) e fechamento (logo + tagline + CTA) entram automaticamente.

Na headline, `*palavra*` pinta a palavra com a cor de destaque (e é nela que entram a ênfase e os ornamentos).

## Adicionar um componente novo

1. Em `runtime/motion.js`, crie `C.meuTipo = (u, box) => ({ el, layout?, anim(tl, t, d) })`.
   - `el` deve nascer no **estado final** (é isso que o echo trail clona).
   - `layout()` (opcional) roda depois que o elemento está na tela, para medir e posicionar.
   - `anim()` define os estados iniciais com `gsap.set` e agenda as animações na timeline `tl`, começando em `t` e com duração `d`.
2. Estilos em `runtime/motion.css`, usando as variáveis `--bg`, `--fg`, `--acc`, `--accInk`, `--card`, `--line`, `--muted`.
3. Em `app/story.py`, adicione o tipo em `UI_TYPES`, os campos no `STORY_SCHEMA` e a limpeza em `normalize_ui`.
4. Em `app/llm.py`, descreva o componente no `CATALOG` para a IA saber quando usar.

## Logo e cores da marca

Ao criar o projeto, o logo passa por três etapas:

- **Contraste com o fundo preto.** O Motion Studio mede os pixels e a IA de visão dá um palpite. Logo com texto preto: as partes pretas viram brancas. Logo cujas cores escuras são a identidade (azul-marinho, vinho): ele aparece sobre um fundo claro na abertura e no fecho, e com um selo claro no canto. Dá para trocar em "Logo sobre o fundo preto".
- **SVG.** Logos chapados (até 5 cores sólidas) são vetorizados com o `vtracer`, o que libera o efeito "Desenhar o traço".
- **Paleta.** 3 cores de referência, tiradas do logo e das artes enviadas. Elas aparecem nos efeitos de logo e nas partículas.

Efeitos de entrada do logo: `draw`, `blur`, `wipe`, `slices`, `glitch`, `pixel`, `iris`, `shatter`, `impact`. A IA escolhe um para a abertura e outro para o fecho, de acordo com a marca. Você pode fixar os dois na tela.

## Fundo, decoração, fotos e ilustrações

- **Fundo do vídeo**: escuro, claro ou cor da marca. No automático, logos feitos para papel (texto preto, azul-marinho) e artes claras levam a fundo claro; a IA de visão opina nos casos em dúvida. O logo se adapta: no fundo claro, partes brancas viram escuras.
- **Decoração animada** (`deco`): manchas de luz, formas geométricas, anéis, feixes diagonais ou ondas, nas cores da marca, mudando a cada cena.
- **Fotos de fundo** (`photo` na cena): uma referência enviada ou uma busca no Pexels/Pixabay, em tela cheia com zoom lento.
- **Ilustrações** (`sticker` na cena): figurinhas coloridas (Fluent Emoji / Noto via Iconify, sem chave).
- **Stories (9:16)**: headline e componente formam um bloco só, e o componente ocupa a altura que sobra.

## Estilo visual e legibilidade

- **Premium** (padrão): moldura fina em degradê com um brilho que percorre a borda, grade de pontos no canto, cartões de vidro, selo (`eyebrow`) acima da headline, headline com pesos mistos e palavra-chave em degradê, divisor com ✦ e linha curva no fecho. **Clean**: o visual mais seco.
- Fontes: além das anteriores, `luxury` (Cormorant Garamond) e `soft` (Montserrat). Headlines serifadas usam uma fonte sem serifa no texto de apoio.
- Vertical: componentes com zoom de 1,55× (nenhum texto abaixo de ~22px na tela de 1080) e legenda de 40px.
- **Legibilidade garantida:** a headline nunca fica abaixo de 72px (84px no vertical); se não couber, o entrelinha aperta em vez de a letra encolher. Serifadas de olho pequeno ganham escala extra. O destaque e o texto de apoio passam por uma checagem de contraste (WCAG) contra o fundo e são escurecidos ou clareados até ficarem legíveis. No fundo claro, o peso fino da headline mista sobe para 500. Sobre foto em tela cheia o texto sempre ganha vidro ou faixa sólida, e a palavra destacada usa uma versão clara da cor da marca.

## Onboarding, fotos e estilo

- **+ Novo motion** abre o passo a passo: categoria → marca → conteúdo (perguntas da categoria) → fotos → estilo → formato → revisão.
- **Fotos para usar no vídeo** (`assets`): a IA de visão identifica cada uma (fachada, lazer, interior, planta…), com título e descrição editáveis. O roteiro usa essas fotos como protagonistas, com layouts `full`, `split`, `card`, `kenburns` ou numa `gallery`.
- **Referências de estilo** (`refs`): não aparecem no vídeo. A IA lê o estilo (resumo, paleta, fundo, skin, fonte, decoração, animação de texto) e o roteiro segue essa direção de arte.
- **Categorias** (`packs/*/pack.json`): cada uma traz perguntas, as fotos que vale a pena pedir, dicas de busca de fotos e o estilo padrão. Para criar uma nova, copie uma pasta e edite o `pack.json`.
- **Semente**: cada projeto tem uma `seed`. "Novo roteiro" sorteia outra semente, o que muda o ângulo criativo, os efeitos de logo e texto e a decoração.
- **Saída maior da IA**: `MOTION_MAX_TOKENS` (padrão 16000). Cada cena traz um campo `direction` com o plano detalhado.
- **Ícones**: coleção Solar duotone (Iconify), em selos com borda e brilho.

## Dicas

- O pitch é a matéria-prima: a IA é instruída a não inventar números. Se quiser uma estatística na tela, ela precisa estar no texto.
- Notas de estilo curtas ajudam ("minimalista P&B", "imobiliário premium").
- Logo em PNG transparente dá o melhor recorte. JPG com fundo liso também funciona.
- O render de 60s em 1080p a 30 fps são 1.800 quadros. Numa máquina com 8 núcleos leva poucos minutos; aumente `MOTION_RENDER_WORKERS` se tiver CPU sobrando.
- Modelos `qwen3` também podem ser usados via `MOTION_MODEL`, mas o padrão testado é `qwen2.5`.

## Licenças

GSAP está em `runtime/vendor` (licença gratuita da GreenSock/Webflow, inclusive para uso comercial). As fontes vêm do Google Fonts (licença OFL).
