"""Conversa com Ollama ou um provedor OpenAI-compatible (como 9router)."""
import base64
import json
import re
import logging

import httpx

from . import config, seeds
from .packs import load_packs, pack_prompt, skill_text
from .story import UI_TYPES, story_schema

log = logging.getLogger("motion.llm")


class LLMError(RuntimeError):
    pass


CATALOG = """
Componentes de UI disponíveis (campo "ui.type") e os campos que cada um usa:
- "counter": número grande que conta do zero. Campos: label, value (texto com o número, ex. "US$ 3.400.000.000", "1.250,00 m²", "92%"), note, segments (opcional, até 3 partes de uma barra: [{"label","pct"}]).
- "cards": 2 a 5 cartões de dados empilhados. Campos: items [{"label","value","sub"}]. Valores numéricos contam sozinhos.
- "bars": 2 a 4 barras horizontais de comparação. Campos: items [{"label","value","sub"}], note.
- "chat": janela de conversa de um agente/app. Campos: title, messages [{"role":"user|agent|external","text","highlight":true/false}], note (selo curto como "IRREVERSÍVEL"). Use highlight para destacar a mensagem crítica.
- "flow": 2 a 4 nós ligados (arquitetura, processo). Campos: nodes [{"title","sub"}], highlight (índice do nó principal), label (pílula que viaja até o nó, ex. "tx 0x4be1…a0f3").
- "checklist": lista com checks animados. Campos: title, items [{"label"}], stamp (texto curto de selo, opcional).
- "steps": painel com 2 a 5 etapas mostradas uma por vez. Campos: steps [{"title","detail","lines":[...]}]. Comece uma linha com "!" para destacá-la como alerta.
- "table": tabela antes/depois ou comparação. Campos: title, columns (2 a 4), rows (listas de textos). Comece uma célula com "!" para destacá-la.
- "verdict": resultado final em bloco grande. Campos: status (1-2 palavras, ex. "BLOQUEADO", "APROVADO"), reason, items [{"label","value"}], stamp.
- "feed": lista de eventos rolando cada vez mais rápido. Campos: title, label (pílula, ex. "Autônomo"), lines (6 a 14 textos curtos; use "ação | status" para duas colunas).
- "image": mostra uma imagem de referência num mockup. Campos: image (chave, ex. "ref1"), items [{"label"}] como etiquetas flutuantes.
- "gallery": baralho de 2 a 4 FOTOS do catálogo que entram uma depois da outra, cada uma com etiqueta. Campos: items [{"image": "img4", "label": "Casa 3 suítes"}]. Ótimo para mostrar várias fachadas, ambientes ou produtos numa cena só e aproveitar todas as fotos do cliente.
- "big_word": tela invertida com UMA palavra gigante (momento de impacto). Campos: word (curta!), pre (frase pequena acima). Use no máximo uma vez.
- "none": só a headline, em tela cheia.
- "hero": objeto do pacote de domínio que atravessa várias cenas (veja a lista de heróis abaixo). Campos: hero, state e os campos do herói.
"""

RULES = """Responda SOMENTE com JSON válido, em português do Brasil.
O logo e a tagline entram sozinhos no fim do vídeo; não crie cena para eles.
"font": grotesk (tech neutro), geometric (moderno), wide (robusto), clean (corporativo), tech (futurista), elegant (serifada editorial), luxury (serifada clássica: alto padrão, patrimônio, joias), soft (geométrica fina: bem-estar, natureza, residencial).
"skin": "premium" (moldura fina com brilho, cartões de vidro, selo acima da headline, headline com pesos mistos e degradê: ótimo para imobiliário, finanças, marcas de valor) ou "clean" (mais seco e técnico: dev tools, segurança, B2B duro). Na dúvida, "premium".
"particles": "bits" para tecnologia/segurança/cripto, "dash" para os demais.
"logo_intro" e "logo_outro": efeito de entrada do logo na abertura e no fecho (seção 7 do guia). Escolha dois DIFERENTES, que combinem com a marca.
"tagline": se o usuário não deu, escreva uma de até 8 palavras."""


NARRATION_RULES = """NARRAÇÃO (locução em off): cada cena tem "narration", o texto que o locutor fala enquanto a cena está na tela.
- NÃO leia a headline nem a caption. A tela mostra a frase de efeito; a voz entrega o que a tela não diz: contexto, consequência, um exemplo concreto, o "por quê".
- Não repita números, nomes ou palavras-chave que já estão na tela: diga o que eles significam ou o que causam. Nunca comece a fala lendo o número que está na tela (o espectador já está vendo).
- Exemplo (de outro setor, só para entender a ideia). Headline "Obras atrasam 8 meses em média." -> narration ruim: "As obras atrasam oito meses em média." narration boa: "Cada mês parado é aluguel pago, juros correndo e um cliente perdendo a paciência."
- As falas formam UM texto contínuo de locutor do começo ao fim, com ligação entre as cenas ("E é aí que...", "Agora imagine...").
- Frases curtas, fáceis de falar, tom de locutor de lançamento: confiante, sem exagero. Sem emojis, sem markdown, sem asteriscos.
- Escreva números e siglas como se falam ("três vírgula quatro bilhões", "dois mil e vinte e cinco").
- Tamanho: cerca de {words} palavras por cena (o locutor fala ~2,5 palavras por segundo e a cena dura o tempo da fala). Cenas big_word podem ter só 3 a 8 palavras ou ficar sem narração, para o impacto respirar.
- "outro_narration": 5 a 14 palavras ditas sobre o logo final; pode dizer o nome da marca e a chamada."""

STOCK_RULES = """FOTOS DE BANCO: o componente "image" pode usar uma foto real buscada no Pexels/Pixabay. Para isso preencha "stock" com 2 a 5 palavras de busca EM INGLÊS, descrevendo uma cena fotografável (ex. "construction site aerial", "woman using phone night", "server room"). Use quando uma foto concreta provar a headline melhor que uma interface; no máximo 2 por vídeo."""

VISUAL_RULES = """VIDA NA TELA (o vídeo não pode ficar seco, com fundo vazio):
- "deco" (no topo do JSON): decoração animada do fundo nas cores da marca. "orbs" (manchas de luz suaves: elegante, premium, saúde), "shapes" (formas geométricas que dançam: jovem, criativo, educação, varejo), "rings" (anéis tracejados girando: tech, finanças, institucional), "lines" (feixes diagonais na troca de cena: dinâmico, esporte, logística), "waves" (ondas no rodapé: água, bem-estar, fluidez), "none" (só quando o pitch pede sobriedade total).
- "photo" (em uma cena): uma foto real na cena. {photo_src}
  FOTOS DO CLIENTE (chaves img1, img2...) SÃO AS PROTAGONISTAS: use TODAS as que fizerem sentido, cada uma numa cena diferente, casando a foto com a frase (fachada na cena da casa, piscina na cena do lazer). Fotos de banco só para o que o cliente não mandou (paisagem da região, estilo de vida, contexto do problema), buscando com a cidade/região citada no briefing quando houver.
  "layout" (na cena com photo) define como a foto aparece: "full" (tela cheia atrás do texto, com degradê), "split" (foto ocupa metade da tela com corte diagonal e o texto na outra metade), "card" (foto numa moldura arredondada com borda fina e etiquetas flutuantes, ao lado/abaixo do texto), "kenburns" (tela cheia com zoom forte e o texto numa faixa de vidro). Varie os layouts ao longo do vídeo. Fotos marcadas como "melhor num cartão" pedem "card". Layouts "split" e "card" exigem ui.type "none" (a foto ocupa o lugar do componente); com componente, use "full" ou "kenburns". Se sobrarem fotos do cliente sem cena, junte-as numa cena "gallery".
- "eyebrow" (em uma cena): selo curto de 2 a 4 palavras que aparece numa pílula acima da headline e diz o TEMA da cena, não repete a headline (ex. "Bem-estar e conforto", "Natureza e sustentabilidade", "O problema", "Como funciona", "Resultado"). Use na maioria das cenas (menos big_word); o sistema mostra em maiúsculas espaçadas.
- "text_fx" (opcional): sugestão de como a headline entra (rise, bars, blur, type, split, marker, underline, scale, rotate, flip, kinetic, stack, wave, zoom, slice). O motion completo de cada cena (efeito de texto, barra atrás do texto, câmera, rotações, transição) é decidido depois, cena a cena, por um diretor; capriche na "direction" e na "funcao".
- "sticker" (em uma cena): ilustração colorida estilo figurinha que entra girando e flutua perto do componente. Escreva UMA palavra ou expressão curta EM INGLÊS de um objeto ou emoji concreto (ex. "house", "key", "handshake", "rocket", "money bag", "chart increasing", "shield", "light bulb", "trophy"). Use em 1 a 3 cenas quando o tom permitir (marcas jovens, varejo, educação, apps). Marcas sofisticadas/luxo/jurídicas: prefira "photo" e evite stickers."""

ICON_RULES = """ÍCONES: em "cards", "checklist" e "flow", cada item ou nó pode ter "icon": o nome em inglês, kebab-case, de um ícone da coleção Solar (duotone, desenhados com dois tons; o sistema os coloca em selos com borda e brilho). Ex.: "home-smile", "shield-check", "wallet-money", "buildings-2", "swimming", "tree", "sun", "key", "map-point", "users-group-rounded", "chart-2", "bolt", "heart", "cup-hot", "case", "calendar". Use em quase todos os itens de cards/checklist/flow; seja consistente dentro da cena."""

DIRECTION_RULES = """DIREÇÃO DETALHADA (obrigatório em toda cena): "direction" é um parágrafo de 3 a 5 frases, como um diretor de motion descrevendo o plano para o animador: o que aparece primeiro, como cada elemento entra e se move, onde fica a foto e como ela é tratada, que detalhe de design dá acabamento (moldura, etiqueta, selo, ornamento), qual é o ritmo e como a cena sai. Seja concreto e visual, usando os elementos reais da cena (headline, componente, foto, ícones). Escreva a direção ANTES de decidir o texto final da cena e mantenha tudo coerente com ela.
"funcao" (obrigatório em toda cena): a função da batida no arco: "mundo", "tensao", "virada", "mecanismo", "prova" ou "impacto". Ela define o ritmo do motion da cena."""


def _system(pack_id: str, extras: dict | None = None) -> str:
    extras = extras or {}
    parts = ["Você é roteirista e diretor de motion design de vídeos curtos de lançamento. Siga este guia à risca:",
             skill_text("roteiro", "variacao"), "COMPONENTES BÁSICOS (ui.type):" + CATALOG, pack_prompt(pack_id), RULES, ICON_RULES, DIRECTION_RULES]
    src = []
    if extras.get("refs"):
        src.append(f"Use a chave de uma foto disponível ({', '.join(extras['refs'])}; veja o catálogo de imagens no briefing)")
    if extras.get("stock"):
        src.append("ou escreva 2 a 5 palavras de busca EM INGLÊS de uma cena fotografável (ex. \"rio de janeiro leblon aerial\", \"luxury apartment living room\") para buscar no banco de fotos")
    if src:
        parts.append(VISUAL_RULES.replace("{photo_src}", " ".join(src) + "."))
    else:
        parts.append(VISUAL_RULES.replace("{photo_src}", "(Sem fotos disponíveis neste projeto: NÃO use \"photo\".)"))
    if extras.get("stock"):
        parts.append(STOCK_RULES)
    if extras.get("narration"):
        parts.append(NARRATION_RULES.replace("{words}", str(extras.get("words") or "14 a 24")))
    return "\n\n".join(parts)


PLAN_SCHEMA = {"type": "object", "properties": {
    "arco": {"type": "string"},
    "conceito_visual": {"type": "string"},
    "batidas": {"type": "array", "items": {"type": "object", "properties": {
        "funcao": {"type": "string", "enum": ["mundo", "tensao", "virada", "mecanismo", "prova", "impacto"]},
        "ideia": {"type": "string"}, "visual": {"type": "string"}, "foto": {"type": "string"},
        "plano": {"type": "string"}}, "required": ["funcao", "ideia", "visual"]}}},
    "required": ["arco", "batidas"]}

EXAMPLE = {
    "font": "grotesk", "particles": "dash", "tagline": "Sua frase final aqui.",
    "scenes": [
        {"headline": "Planilhas não escalam.", "caption": "Times perdem horas consolidando dados à mão.",
         "ui": {"type": "counter", "label": "Horas perdidas por mês", "value": "120 h", "note": "Média informada no pitch."}},
        {"headline": "Tudo num só painel.", "caption": "",
         "ui": {"type": "flow", "nodes": [{"title": "Fontes", "sub": "ERP e CRM"}, {"title": "Produto", "sub": "consolida"},
                                           {"title": "Painel", "sub": "decisão"}], "highlight": 1, "label": "sync"}},
    ],
}


def _brief_text(brief: dict, ref_desc: str, ref_keys: list, n_scenes: int) -> str:
    parts = [f"Marca: {brief.get('name') or '(sem nome)'}"]
    if brief.get("tagline"):
        parts.append(f"Tagline já definida: {brief['tagline']}")
    if brief.get("style"):
        parts.append(f"Notas de estilo do usuário: {brief['style']}")
    if ref_desc:
        parts.append(f"Descrição das imagens de referência: {ref_desc}")
    if brief.get("answers"):
        parts.append("Briefing do cliente (respostas do onboarding):\n" + "\n".join(f"- {a}" for a in brief["answers"]))
    if brief.get("assets"):
        parts.append("CATÁLOGO DE IMAGENS (chave: o que a foto mostra). Use as fotos do cliente como protagonistas, uma por cena:\n"
                     + "\n".join(f"- {a}" for a in brief["assets"]))
    elif ref_keys:
        parts.append(f"Imagens disponíveis: {', '.join(ref_keys)}")
    sb = brief.get("style_brief") or {}
    if sb.get("resumo"):
        bits = [f"DIREÇÃO DE ARTE pedida pelo cliente (das referências de design dele; o motion deve seguir este estilo): {sb['resumo']}"]
        if sb.get("elements"):
            bits.append("Elementos que aparecem nas referências: " + ", ".join(sb["elements"]))
        sug = {k: sb.get(k) for k in ("font", "skin", "deco", "text_fx") if sb.get(k)}
        if sug:
            bits.append("Sugestões da análise: " + ", ".join(f"{k}={v}" for k, v in sug.items()) + " (prefira estas, a menos que a cena peça outra coisa)")
        parts.append("\n".join(bits))
    if brief.get("photo_hint"):
        parts.append(f"Fotos de banco que costumam funcionar nesta categoria: {brief['photo_hint']}")
    if brief.get("angle"):
        parts.append(f"ÂNGULO CRIATIVO desta versão (variação #{brief.get('seed')}): {brief['angle']} Faça escolhas diferentes do óbvio.")
    if brief.get("dna"):
        parts.append(seeds.dna_prompt(brief["dna"]))
    if brief.get("logo"):
        parts.append(f"Logo da marca: {brief['logo']}")
    parts.append(f"Quantidade de cenas desejada: {n_scenes} (pode variar 1 para mais ou para menos).")
    parts.append("Pitch:\n" + brief.get("pitch", "").strip())
    return "\n\n".join(parts)


def _examples(pack_id: str) -> str:
    exs = load_packs()[pack_id].get("examples", [])[:2] or [EXAMPLE]
    return "\n\n".join(f"Exemplo {i + 1} de roteiro BEM FEITO neste estilo (aprenda o ritmo, a escolha de visuais e a continuidade dos heróis; NÃO copie o conteúdo):\n"
                         + json.dumps(e, ensure_ascii=False) for i, e in enumerate(exs))


def _is_reasoning_model(model: str) -> bool:
    """Modelos agentic/thinking frequentemente rejeitam temperature e JSON Schema."""
    name = model.lower()
    markers = ("agentic", "thinking", "reasoning", "codex", "o1", "o3", "o4", "gpt-5")
    return any(marker in name for marker in markers)


def _base_model(model: str) -> str:
    """kr/claude-sonnet-4.5-thinking-agentic -> kr/claude-sonnet-4.5"""
    for suffix in ("-thinking-agentic", "-agentic", "-thinking"):
        if model.endswith(suffix):
            return model[: -len(suffix)]
    return model


def _openai_messages(messages: list) -> list:
    """Converte o formato multimodal do Ollama para o formato OpenAI."""
    converted = []
    for message in messages:
        item = {"role": message["role"], "content": message.get("content", "")}
        images = message.get("images", [])
        if images:
            content = [{"type": "text", "text": str(item["content"])}]
            content += [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{data}"}}
                        for data in images]
            item["content"] = content
        converted.append(item)
    return converted


def _response_text(data: dict) -> str:
    """Aceita texto simples, blocos multimodais e respostas com reasoning separado."""
    choices = data.get("choices") or []
    choice = choices[0] if choices else {}
    message = choice.get("message") or {}
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") in ("text", "output_text"):
                parts.append(str(block.get("text") or block.get("content") or ""))
        if "".join(parts).strip():
            return "".join(parts)
    # Alguns gateways devolvem o resultado final fora de content.
    for value in (message.get("output_text"), choice.get("text"), data.get("output_text")):
        if isinstance(value, str) and value.strip():
            return value
    raise LLMError("O modelo respondeu sem conteúdo final (apenas raciocínio ou tool calls).")


async def _openai_chat(model: str, messages: list, fmt=None, temperature=0.5, seed: int | None = None) -> str:
    if not config.NINEROUTER_API_KEY:
        raise LLMError("Configure NINEROUTER_API_KEY para usar o 9router.")
    reasoning = _is_reasoning_model(model)
    payload = {"model": model, "messages": _openai_messages(messages), "stream": False, "max_tokens": config.MAX_TOKENS}
    if reasoning:
        payload["reasoning_effort"] = config.REASONING_EFFORT
    else:
        payload["temperature"] = temperature
        if fmt is not None:
            payload["response_format"] = {"type": "json_object"}
        if seed is not None:
            payload["seed"] = seed
    headers = {"Authorization": f"Bearer {config.NINEROUTER_API_KEY}"}
    try:
        async with httpx.AsyncClient(timeout=config.LLM_TIMEOUT) as c:
            r = await c.post(f"{config.NINEROUTER_URL}/chat/completions", json=payload, headers=headers)
            # Nem todo upstream aceita response_format/reasoning_effort; recue sem gastar outra
            # tentativa de roteiro quando o gateway rejeitar apenas esse parâmetro.
            if r.status_code == 400 and ("response_format" in payload or "reasoning_effort" in payload or "max_tokens" in payload):
                payload.pop("response_format", None)
                payload.pop("seed", None)
                payload.pop("reasoning_effort", None)
                payload.pop("max_tokens", None)
                r = await c.post(f"{config.NINEROUTER_URL}/chat/completions", json=payload, headers=headers)
            # O upstream kiro rejeita as variantes -thinking/-agentic (REQUEST_BODY_INVALID);
            # recue para o modelo base da mesma família.
            base = _base_model(model)
            if r.status_code == 400 and base != model:
                log.warning("Modelo %s rejeitado pelo 9router; usando %s.", model, base)
                payload["model"] = base
                payload["temperature"] = temperature
                r = await c.post(f"{config.NINEROUTER_URL}/chat/completions", json=payload, headers=headers)
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        raise LLMError(f"Não consegui falar com o 9router em {config.NINEROUTER_URL}.") from e
    if r.status_code >= 400:
        detail = r.text[:500]
        raise LLMError(f"9router respondeu {r.status_code}: {detail}")
    try:
        return _response_text(r.json())
    except (ValueError, KeyError) as e:
        raise LLMError("O 9router devolveu uma resposta inválida.") from e


async def _chat(model: str, messages: list, fmt=None, temperature=0.5, seed: int | None = None) -> str:
    """seed: com a mesma semente o modelo tende a repetir a resposta (variação reproduzível)."""
    if config.LLM_BACKEND in ("9router", "openai"):
        return await _openai_chat(model, messages, fmt, temperature, seed)
    payload = {"model": model, "messages": messages, "stream": False,
               "options": {"temperature": temperature, "num_ctx": config.NUM_CTX, "num_predict": config.MAX_TOKENS}}
    if seed is not None:
        payload["options"]["seed"] = seed
    if fmt is not None:
        payload["format"] = fmt
    try:
        async with httpx.AsyncClient(timeout=config.LLM_TIMEOUT) as c:
            r = await c.post(f"{config.OLLAMA_URL}/api/chat", json=payload)
    except httpx.ConnectError as e:
        raise LLMError(f"Não consegui falar com o Ollama em {config.OLLAMA_URL}. Ele está rodando? (ollama serve)") from e
    if r.status_code == 404:
        raise LLMError(f"O modelo '{model}' não está instalado. Rode: ollama pull {model}")
    if r.status_code >= 400:
        raise LLMError(f"Ollama respondeu {r.status_code}: {r.text[:300]}")
    return r.json().get("message", {}).get("content", "")


async def list_models() -> tuple[list[str], bool]:
    """Lista modelos disponíveis sem expor credenciais ao cliente web."""
    if config.LLM_BACKEND == "mock":
        return [], True
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            if config.LLM_BACKEND in ("9router", "openai"):
                if not config.NINEROUTER_API_KEY:
                    return [], False
                r = await c.get(f"{config.NINEROUTER_URL}/models",
                                headers={"Authorization": f"Bearer {config.NINEROUTER_API_KEY}"})
                r.raise_for_status()
                models = [m.get("id") for m in r.json().get("data", []) if m.get("id")]
            else:
                r = await c.get(f"{config.OLLAMA_URL}/api/tags")
                r.raise_for_status()
                models = [m.get("name") for m in r.json().get("models", []) if m.get("name")]
        return sorted(set(models), key=str.lower), True
    except Exception as e:
        log.warning("Não foi possível listar modelos: %s", e)
        return [], False


_STOP = set("a o as os um uma de da do das dos e é em no na nos nas por para com que se sua seu mais já não ao à".split())


def _words(text: str) -> set[str]:
    import re
    return {w for w in re.findall(r"\w+", (text or "").lower().replace("*", "")) if len(w) > 2 and w not in _STOP}


def _echoing_scenes(data: dict) -> list[int]:
    """Cenas (1-based) cuja narração reaproveita metade ou mais das palavras da headline."""
    bad = []
    for i, sc in enumerate(data.get("scenes") or [], start=1):
        head, narr = _words(sc.get("headline")), _words(sc.get("narration"))
        if len(head) >= 2 and narr and len(head & narr) / len(head) >= 0.5:
            bad.append(i)
    return bad


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):]
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


ASSET_TYPES = ["fachada", "lazer", "piscina", "interior", "planta", "vista", "paisagem", "pessoas", "produto",
               "tela_app", "equipe", "comida", "ambiente", "detalhe", "mapa", "logo", "outro"]

ASSETS_PROMPT = """Estas são as FOTOS que o cliente quer que apareçam num vídeo de motion design{cat}. Para cada imagem, na ordem, diga o que ela mostra.
Responda SOMENTE com JSON: {{"imagens": [{{"tipo": "<um de: {tipos}>", "titulo": "2 a 4 palavras em português (ex. Fachada principal, Piscina aquecida, Sala integrada)", "descricao": "uma frase concreta do que aparece, com materiais, luz e clima", "uso": "fundo" | "cartao" | "ambos", "destaque": "o elemento mais forte da foto em 2 a 5 palavras"}}]}}
"uso": "fundo" para fotos amplas e bonitas que aguentam texto por cima; "cartao" para prints de tela, plantas, detalhes ou fotos com muita informação; "ambos" quando servem para os dois."""


async def analyze_assets(images: list[bytes], category: str = "") -> list[dict]:
    """IA de visão identifica cada foto enviada (fachada, lazer, interior...). Falhas devolvem lista vazia."""
    if not images or not config.VISION_MODEL or config.LLM_BACKEND == "mock":
        return []
    out = []
    for i in range(0, len(images), 6):  # lotes de 6 para não estourar o limite de imagens por chamada
        batch = images[i:i + 6]
        msg = {"role": "user", "content": ASSETS_PROMPT.format(cat=f" da categoria {category}" if category else "",
                                                               tipos=", ".join(ASSET_TYPES)),
               "images": [base64.b64encode(b).decode() for b in batch]}
        try:
            data = _parse_json(await _chat(config.VISION_MODEL, [msg], fmt={"type": "object"}, temperature=0.2))
            items = data.get("imagens") or []
        except Exception as e:
            log.warning("Análise das fotos falhou: %s", e)
            items = []
        for k in range(len(batch)):
            it = items[k] if k < len(items) and isinstance(items[k], dict) else {}
            tipo = str(it.get("tipo") or "outro").strip().lower()
            out.append({"tipo": tipo if tipo in ASSET_TYPES else "outro",
                        "titulo": str(it.get("titulo") or "").strip()[:40],
                        "descricao": str(it.get("descricao") or "").strip()[:240],
                        "uso": it.get("uso") if it.get("uso") in ("fundo", "cartao", "ambos") else "ambos",
                        "destaque": str(it.get("destaque") or "").strip()[:60]})
    return out


STYLE_PROMPT = """Estas imagens são REFERÊNCIAS DE DESIGN: o cliente quer que o motion siga este estilo (não o conteúdo). Analise como um diretor de arte.
Responda SOMENTE com JSON:
{"resumo": "60 a 110 palavras descrevendo o estilo para um motion designer: composição, hierarquia tipográfica (pesos, caixa alta, espaçamento), tratamento das fotos (degradês, sobreposições), bordas, cartões, ícones, ornamentos, clima",
 "paleta": ["#RRGGBB", "#RRGGBB", "#RRGGBB"],
 "fundo": "escuro" | "claro" | "cor_da_marca",
 "skin": "premium" | "clean",
 "fonte": "<uma de: grotesk, geometric, wide, clean, tech, elegant, luxury, soft>",
 "deco": "<uma de: orbs, shapes, rings, lines, waves, none>",
 "texto": "<uma de: rise, bars, blur, type, split, marker, underline, scale>",
 "elementos": ["moldura fina", "cartões de vidro", "selo/pílula", "degradê no texto", "ícones em caixa", "ornamentos", "grade de pontos", "linha curva", "foto em tela cheia", "foto recortada", "fundo liso", ...]  // só o que aparece
}"""


async def analyze_style(images: list[bytes]) -> dict:
    """IA de visão lê as referências de estilo como um brief de direção de arte. Falhas devolvem {}."""
    if not images or not config.VISION_MODEL or config.LLM_BACKEND == "mock":
        return {}
    msg = {"role": "user", "content": STYLE_PROMPT, "images": [base64.b64encode(b).decode() for b in images[:5]]}
    try:
        d = _parse_json(await _chat(config.VISION_MODEL, [msg], fmt={"type": "object"}, temperature=0.2))
    except Exception as e:
        log.warning("Análise das referências de estilo falhou: %s", e)
        return {}
    pick = lambda v, ok: v if v in ok else None
    return {"resumo": str(d.get("resumo") or "").strip()[:900],
            "palette": [c.upper() for c in d.get("paleta") or [] if isinstance(c, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", c.strip())][:3],
            "theme": {"escuro": "dark", "claro": "light", "cor_da_marca": "brand"}.get(str(d.get("fundo") or "")),
            "skin": pick(d.get("skin"), ("premium", "clean")),
            "font": pick(d.get("fonte"), tuple(config.FONTS)),
            "deco": pick(d.get("deco"), ("orbs", "shapes", "rings", "lines", "waves", "none")),
            "text_fx": pick(d.get("texto"), tuple(seeds.TEXT_FX)),
            "elements": [str(x)[:40] for x in (d.get("elementos") or []) if isinstance(x, str)][:12]}


BRAND_PROMPT = """A primeira imagem é um LOGO, mostrado sobre fundo cinza só para você enxergar partes claras e escuras. As outras (se houver) são artes de referência da marca.
Por padrão o vídeo tem FUNDO PRETO (mas pode ser claro ou da cor da marca, veja "fundo_video"). Responda SOMENTE com JSON:
{"simples": true/false,  // true se o logo é chapado (poucas cores sólidas, sem foto, sem degradê complexo) e pode virar SVG
 "ajuste": "nenhum" | "inverter" | "fundo_claro",
   // nenhum: já é legível sobre preto
   // inverter: há texto/partes pretas ou cinza-escuras que podem virar brancas sem descaracterizar a marca
   // fundo_claro: as cores escuras fazem parte da identidade (ex. azul-marinho, vinho); melhor mostrar o logo sobre um fundo claro
 "paleta": ["#RRGGBB", "#RRGGBB", "#RRGGBB"],  // as 3 cores de referência da marca (logo primeiro, depois as artes), boas como destaque sobre preto; nada de preto puro
 "revelacao": "<um destes: draw, blur, wipe, slices, glitch, pixel, iris, shatter, impact>",  // efeito de entrada do logo que combina com o desenho e o clima da marca
 "fundo_video": "escuro" | "claro" | "cor_da_marca"  // fundo do vídeo inteiro que combina com a marca: logo pensado para papel branco e marcas leves/limpas pedem "claro"; marcas tech/noturnas "escuro"; marcas com cor forte e confiante "cor_da_marca"
}"""


async def analyze_brand(logo_jpg: bytes, refs: list[bytes]) -> dict | None:
    """IA de visão olha o logo (e as artes): é simples? precisa inverter ou de fundo claro? quais as 3 cores? Falhas são ignoradas."""
    if not config.VISION_MODEL or config.LLM_BACKEND == "mock":
        return None
    msg = {"role": "user", "content": BRAND_PROMPT,
           "images": [base64.b64encode(b).decode() for b in [logo_jpg] + refs[:3]]}
    try:
        data = _parse_json(await _chat(config.VISION_MODEL, [msg], fmt={"type": "object"}, temperature=0.2))
    except Exception as e:
        log.warning("Análise do logo pela IA de visão falhou: %s", e)
        return None
    fix = {"nenhum": "none", "inverter": "invert", "fundo_claro": "plate"}.get(str(data.get("ajuste", "")).strip())
    pal = [c.upper() for c in data.get("paleta") or [] if isinstance(c, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", c.strip())]
    return {"simple": data.get("simples") if isinstance(data.get("simples"), bool) else None, "fix": fix,
            "palette": pal[:3], "reveal": str(data.get("revelacao") or "").strip().lower() or None,
            "theme": {"escuro": "dark", "claro": "light", "cor_da_marca": "brand"}.get(str(data.get("fundo_video", "")).strip())}


async def plan_story(brief: dict, ref_desc: str, ref_keys: list, n_scenes: int, pack_id: str, model: str,
                     extras: dict | None = None) -> dict | None:
    """Etapa 1: o diretor quebra o pitch em batidas e escolhe o visual de cada uma."""
    msgs = [{"role": "system", "content": _system(pack_id, extras)},
            {"role": "user", "content": _brief_text(brief, ref_desc, ref_keys, n_scenes) + "\n\n"
             "ETAPA 1 (plano). Faça só o plano de direção, seguindo as seções 1 e 2 do guia. Em \"arco\", escreva o arco em uma frase. "
             "Em \"conceito_visual\", descreva em 2 a 3 frases a linguagem visual do filme inteiro (como as fotos, cores, molduras e tipografia vão conversar). "
             "Para cada batida: funcao, a ideia em poucas palavras, o visual escolhido (o nome de um componente básico, ex. \"counter\", "
             "ou \"heroi:estado\", ex. \"lote:predio\"), \"foto\" (chave da foto do catálogo ou busca em inglês, ou vazio) e \"plano\" "
             "(2 frases: o que se vê e como se move). Heróis em batidas seguidas, estados em ordem."}]
    try:
        plan = _parse_json(await _chat(model, msgs, fmt=PLAN_SCHEMA, temperature=0.7, seed=brief.get("seed")))
        return plan if plan.get("batidas") else None
    except Exception as e:
        log.warning("Plano falhou, seguindo direto para o roteiro: %s", e)
        return None


async def write_story(brief: dict, ref_desc: str, ref_keys: list, n_scenes: int, pack_id: str = "geral", model: str | None = None,
                      extras: dict | None = None) -> dict:
    """extras: {"narration": bool, "words": "12 a 18", "stock": bool} liga as seções extras do prompt."""
    if config.LLM_BACKEND == "mock":
        exs = load_packs().get(pack_id, {}).get("examples")
        return exs[0] if exs else json.loads((config.EXAMPLES_DIR / "demo.story.json").read_text(encoding="utf-8"))
    model = model or config.MOTION_MODEL
    plan = await plan_story(brief, ref_desc, ref_keys, n_scenes, pack_id, model, extras) if config.TWO_STAGE else None
    ask = _brief_text(brief, ref_desc, ref_keys, n_scenes) + "\n\n" + _examples(pack_id)
    if plan:
        ask += "\n\nPLANO DE DIREÇÃO aprovado (siga a ordem e os visuais; pode ajustar se algum visual não couber):\n" + json.dumps(plan, ensure_ascii=False)
    ask += ("\n\nAgora escreva o ROTEIRO FINAL em JSON. Antes de responder, confira o checklist da seção 6 do guia. "
            "Marque a \"funcao\" de cada cena (use a do plano, se houver).")
    if (extras or {}).get("narration"):
        ask += " Inclua \"narration\" em cada cena e \"outro_narration\"; confira que nenhuma fala repete a headline."
    messages = [{"role": "system", "content": _system(pack_id, extras)}, {"role": "user", "content": ask}]
    schema = story_schema(pack_id)
    last_err = None
    for attempt in range(3):
        text = await _chat(model, messages, fmt=schema, temperature=0.6 if attempt == 0 else 0.3,
                           seed=seeds.derive(brief.get("seed") or 0, "story", attempt))
        try:
            data = _parse_json(text)
            if not data.get("scenes"):
                raise ValueError("lista de cenas vazia")
            bad = [s.get("ui", {}).get("type") for s in data["scenes"] if s.get("ui", {}).get("type") not in UI_TYPES]
            if bad:
                raise ValueError(f"tipos de UI inválidos: {bad}")
            echo = _echoing_scenes(data) if (extras or {}).get("narration") and attempt < 2 else []
            if echo:
                raise ValueError(f"a narração das cenas {echo} repete palavras da headline; reescreva essas falas "
                                 "dizendo o que a tela NÃO diz (consequência, contexto, exemplo)")
            if plan:
                data["_plan"] = plan
            return data
        except Exception as e:
            last_err = e
            log.warning("Tentativa %d de roteiro falhou: %s", attempt + 1, e)
            messages += [{"role": "assistant", "content": text[:4000]},
                         {"role": "user", "content": f"O JSON tem um problema: {e}. Corrija e responda só com o JSON completo."}]
    raise LLMError(f"O modelo não gerou um roteiro válido após 3 tentativas ({last_err}).")


# ---------- etapa 3: diretor de cena ----------

_MOTION_PROPS = {"nome": {"type": "string"}} | {f: {"type": "string", "enum": vals} for f, vals in seeds.MOTION_FIELDS.items()}
_MOTION_OBJ = {"type": "object", "properties": _MOTION_PROPS, "required": ["nome", "text_fx", "camera", "transition"]}
SCENE_MOTION_SCHEMA = {"type": "object", "properties": {
    "direction": {"type": "string"},
    "ideas": {"type": "array", "items": _MOTION_OBJ},
    "pick": {"type": "integer"}}, "required": ["direction", "ideas", "pick"]}
BATCH_MOTION_SCHEMA = {"type": "object", "properties": {
    "scenes": {"type": "array", "items": SCENE_MOTION_SCHEMA}}, "required": ["scenes"]}

_DIRECTOR_SYSTEM = None


def _director_system() -> str:
    global _DIRECTOR_SYSTEM
    if _DIRECTOR_SYSTEM is None:
        _DIRECTOR_SYSTEM = ("Você é diretor de motion design. Recebe UMA cena de um vídeo curto de lançamento e decide como ela "
                            "se move, seguindo estes guias:\n\n"
                            + skill_text("direcao-cena", "tipografia", "motion-catalogo", "transicoes")
                            + "\n\nResponda SOMENTE com JSON válido, em português do Brasil.")
    return _DIRECTOR_SYSTEM


_UI_DESC = {"none": "nenhum: só a headline, grande na tela", "big_word": "palavra gigante", "hero": "objeto do pacote (herói)"}


def _scene_card(sc: dict, label: str) -> str:
    ui = sc.get("ui") or {}
    comp = _UI_DESC.get(ui.get("type"), ui.get("type") or "nenhum")
    if ui.get("type") == "hero":
        comp = f"herói {ui.get('hero')} no estado {ui.get('state')}"
    bits = [f"{label} (função: {sc.get('funcao') or 'não marcada'})", f'- headline: "{sc.get("headline", "")}"']
    if sc.get("caption"):
        bits.append(f'- legenda: "{sc["caption"]}"')
    bits.append(f"- componente: {comp}")
    if sc.get("photo"):
        bits.append(f"- foto: sim, layout {sc.get('layout') or 'full'}")
    if sc.get("direction"):
        bits.append(f"- ideia do roteirista: {sc['direction']}")
    return "\n".join(bits)


def _motion_line(m: dict) -> str:
    return ", ".join(f"{k}={m[k]}" for k in ("text_fx", "text_bg", "camera", "emphasis", "ornament", "transition") if m.get(k))


def _film_header(brief: dict, plan: dict | None, dna: dict, theme_mode: str, fmt: str) -> str:
    bg = {"light": "claro", "brand": "cor da marca (escuro)"}.get(theme_mode, "escuro")
    parts = [f"FILME: marca {brief.get('name') or '(sem nome)'}. Formato {'vertical 9:16' if fmt == 'portrait' else 'horizontal 16:9'}. Fundo do vídeo: {bg}."]
    if plan:
        if plan.get("arco"):
            parts.append(f"Arco: {plan['arco']}")
        if plan.get("conceito_visual"):
            parts.append(f"Conceito visual: {plan['conceito_visual']}")
    if (brief.get("style_brief") or {}).get("resumo"):
        parts.append("Direção de arte do cliente: " + brief["style_brief"]["resumo"][:400])
    parts.append(seeds.dna_prompt(dna))
    return "\n".join(parts)


async def direct_scenes(scenes: list, brief: dict, plan: dict | None, dna: dict, project_seed: int, model: str | None = None,
                        theme_mode: str = "dark", fmt: str = "landscape", only: int | None = None) -> None:
    """Etapa 3: pensa o motion de cada cena (3 ideias + escolha), uma chamada por cena, em ordem.
    Cada cena vê o que a anterior escolheu. Falhas caem no sorteio pela semente. only: dirige só essa cena."""
    model = model or config.MOTION_MODEL
    light = theme_mode == "light"
    mode = "off" if config.LLM_BACKEND == "mock" else config.SCENE_DIRECTOR
    idx = [i for i in range(len(scenes)) if (only is None or i == only)]
    header = _film_header(brief, plan, dna, theme_mode, fmt)

    def seed_of(i):
        return seeds.scene_seed(project_seed, i, 0) if only is None else seeds.derive(project_seed, "redirect", i, scenes[i].get("reroll") or 0)

    def settle(i, ideas, pick, direction=None):
        sc = scenes[i]
        ctx = seeds.scene_ctx(scenes, i, light=light)
        sc["ideas"] = [seeds.harmonize(seeds.fill(m, dna, seeds.derive(seed_of(i), "fill", k), ctx), ctx) for k, m in enumerate(ideas)]
        sc["pick"] = pick if 0 <= pick < len(sc["ideas"]) else 0
        sc["reroll"] = 0
        sc["seed"] = seed_of(i)
        sc.pop("motion_locked", None)
        if direction:
            sc["direction"] = re.sub(r"\s+", " ", direction).strip()[:900]
        sc["motion"] = seeds.choose(sc, project_seed, i, dna, ctx)

    def fallback(i):
        ctx = seeds.scene_ctx(scenes, i, light=light)
        settle(i, seeds.idea_seeds(dna, seed_of(i), ctx), 0)

    todo = [i for i in idx if (scenes[i].get("ui") or {}).get("type") != "big_word"]
    if mode == "batch" and todo:
        await _direct_batch(scenes, todo, header, dna, seed_of, settle, fallback, model, light)
    else:
        for n, i in enumerate(todo, start=1):
            if mode == "off":
                fallback(i)
                continue
            log.info("Diretor de cena: cena %d de %d", n, len(todo))
            ctx = seeds.scene_ctx(scenes, i, light=light)
            sugg = seeds.idea_seeds(dna, seed_of(i), ctx)
            prev = scenes[i - 1] if i > 0 else None
            nxt = scenes[i + 1] if i + 1 < len(scenes) else None
            ask = [header, "", _scene_card(scenes[i], f"CENA {i + 1} de {len(scenes)}")]
            if prev:
                ask.append(f'\nCENA ANTERIOR: "{prev.get("headline", "")}" (função {prev.get("funcao") or "?"}); '
                           f"motion escolhido: {_motion_line(prev.get('motion') or {}) or 'abertura do logo'}.")
            else:
                ask.append("\nCENA ANTERIOR: abertura com o logo (esta é a primeira cena).")
            if nxt:
                ask.append(f'PRÓXIMA CENA: "{nxt.get("headline", "")}" (função {nxt.get("funcao") or "?"}).')
            ask.append(f"\nSEMENTES DE IDEIA desta versão (#{seed_of(i)}; ponto de partida, pode desviar se a frase pedir outra coisa):\n"
                       + "\n".join(f"{k + 1}) {_motion_line(m)}" for k, m in enumerate(sugg)))
            ask.append("\nPense primeiro no verbo e na energia da frase. Escreva a \"direction\" (3 a 5 frases concretas), "
                       "depois 3 \"ideas\" realmente diferentes entre si (cada uma com um \"nome\" curto de 2 a 5 palavras e todos os campos), "
                       "e em \"pick\" o índice (0, 1 ou 2) da melhor para esta cena, que também contraste com a cena anterior.")
            msgs = [{"role": "system", "content": _director_system()}, {"role": "user", "content": "\n".join(ask)}]
            try:
                d = _parse_json(await _chat(model, msgs, fmt=SCENE_MOTION_SCHEMA, temperature=0.85, seed=seed_of(i)))
                ideas = [m for m in (seeds.sanitize_motion(x) for x in (d.get("ideas") or [])[:3]) if m.get("text_fx")]
                if not ideas:
                    raise ValueError("sem ideias válidas")
                while len(ideas) < 3:  # completa com as sementes para sempre haver 3 opções
                    ideas.append(sugg[len(ideas)])
                settle(i, ideas, int(d.get("pick") or 0) if str(d.get("pick", "0")).lstrip("-").isdigit() else 0, d.get("direction"))
            except Exception as e:
                log.warning("Diretor de cena falhou na cena %d (%s); usando o sorteio pela semente.", i + 1, e)
                fallback(i)
    if only is None:
        seeds.dedupe(scenes, dna, project_seed, light, locked=lambda sc: False)


async def _direct_batch(scenes, todo, header, dna, seed_of, settle, fallback, model, light) -> None:
    cards = "\n\n".join(_scene_card(scenes[i], f"CENA {i + 1}") for i in todo)
    ask = (header + "\n\n" + cards + "\n\nPara CADA cena acima, na ordem, escreva a \"direction\", 3 \"ideas\" diferentes entre si "
           "(com \"nome\" e todos os campos) e o \"pick\". Cenas vizinhas não repetem efeito de texto, câmera nem transição.")
    msgs = [{"role": "system", "content": _director_system()}, {"role": "user", "content": ask}]
    try:
        d = _parse_json(await _chat(model, msgs, fmt=BATCH_MOTION_SCHEMA, temperature=0.8, seed=seed_of(todo[0])))
        out = d.get("scenes") or []
    except Exception as e:
        log.warning("Diretor de cena (lote) falhou: %s", e)
        out = []
    for k, i in enumerate(todo):
        item = out[k] if k < len(out) and isinstance(out[k], dict) else {}
        ideas = [m for m in (seeds.sanitize_motion(x) for x in (item.get("ideas") or [])[:3]) if m.get("text_fx")]
        if ideas:
            pick = item.get("pick") if isinstance(item.get("pick"), int) else 0
            settle(i, ideas, pick, item.get("direction"))
        else:
            fallback(i)
