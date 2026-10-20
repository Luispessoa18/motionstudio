"""Sementes e receitas de motion.

A semente do projeto sorteia o "DNA" do filme (ângulo criativo + receita visual). Cada cena tem a sua
semente, derivada da do projeto, do índice e de um contador de re-sorteio; assim dá para refazer uma
cena só sem mexer nas outras, e a mesma semente sempre gera o mesmo resultado.
"""
import hashlib
import random
import re

# ---------- vocabulário de motion (o runtime sabe fazer exatamente isto) ----------
TEXT_FX = ["rise", "bars", "blur", "type", "split", "marker", "underline", "scale",
           "rotate", "flip", "kinetic", "stack", "wave", "zoom", "slice"]
TEXT_BG = ["none", "bar", "block", "highlight", "glass", "outline"]
CAMERA = ["still", "push_in", "pull_out", "drift", "tilt", "spin_in", "shake", "parallax"]
EMPHASIS = ["none", "pop", "spin", "circle", "strike", "color_swap", "glow", "underline_draw"]
ORNAMENT = ["none", "spin_ring", "orbit_dots", "rotating_badge", "corner_brackets", "big_number_bg", "grid_sweep"]
ALIGN = ["left", "center", "right"]
TRANSITION = ["cut", "fade", "wipe", "slide", "push", "zoom", "iris", "spin", "blinds", "flash", "glitch", "match"]
MOTION_FIELDS = {"text_fx": TEXT_FX, "text_bg": TEXT_BG, "camera": CAMERA, "emphasis": EMPHASIS,
                 "ornament": ORNAMENT, "align": ALIGN, "transition": TRANSITION}
FUNCOES = ["mundo", "tensao", "virada", "mecanismo", "prova", "impacto"]

LETTER_FX = {"split", "flip", "wave", "type"}          # letra a letra: só frases curtas
SPINNERS = {"spin_ring", "orbit_dots", "rotating_badge"}
LOUD_TRANS = {"spin", "glitch", "flash", "match", "zoom"}
HEAVY_BG = {"bar", "block"}


def derive(seed, *keys) -> int:
    """Hash estável (não muda entre execuções do Python) de uma semente com chaves."""
    raw = ":".join(str(k) for k in (seed, *keys)).encode()
    return int.from_bytes(hashlib.blake2b(raw, digest_size=8).digest(), "big") % 2147483646 + 1


def rng(seed, *keys) -> random.Random:
    return random.Random(derive(seed, *keys))


def scene_seed(project_seed, index: int, reroll: int = 0) -> int:
    return derive(project_seed, "scene", index, reroll)


# ---------- ângulos criativos (como contar a história) ----------
ANGLES = [
    "Abra com uma pergunta que o público faz a si mesmo.",
    "Abra com a sensação (o que se vê, ouve e sente) antes de qualquer informação.",
    "Conte como um dia na vida de quem usa ou mora ali.",
    "Estruture como antes e depois: o problema de hoje, a virada, o novo normal.",
    "Abra com o detalhe mais surpreendente do pitch e depois abra o plano.",
    "Faça uma contagem regressiva de motivos (3, 2, 1) até a chamada.",
    "Use contraste forte: cidade x natureza, caos x calma, complexo x simples.",
    "Fale direto com o espectador em segunda pessoa, como um convite.",
    "Comece pelo fim: mostre o resultado e depois volte para explicar como se chega lá.",
    "Use uma palavra-tema que volta em várias cenas e muda de sentido a cada vez.",
    "Trate como manifesto: frases curtas, afirmativas, quase um grito de marca.",
    "Conte pela perspectiva de um objeto (a chave, o celular, o terreno, a transação).",
    "Use números como capítulos: cada cena é um dado que muda a percepção.",
    "Comece com o que todo mundo acredita e derrube essa crença.",
    "Construa suspense: esconda o produto até a virada e revele com força.",
    "Monte como checklist da vida real: problemas riscados um a um até a solução.",
]

# ---------- receitas visuais (a personalidade do movimento do filme) ----------
# fits: tags de contexto onde a receita brilha; avoid: tags onde ela não entra.
RECIPES = {
    "editorial": {"name": "Editorial calmo", "ease": "smooth", "spin": .2,
                  "desc": "Revista de design: texto respirado, entradas suaves, muito espaço e cortes elegantes.",
                  "text_fx": ["blur", "rise", "underline", "marker"], "text_bg": ["none", "outline", "highlight"],
                  "camera": ["drift", "pull_out", "still"], "emphasis": ["underline_draw", "circle", "glow"],
                  "ornament": ["corner_brackets", "none", "grid_sweep"], "transition": ["fade", "iris", "slide", "cut"],
                  "fits": {"premium", "sober", "neutral"}, "avoid": set()},
    "kinetic": {"name": "Kinetic bold", "ease": "snappy", "spin": .5,
                "desc": "Tipografia cinética: palavras gigantes, ritmo de batida, cortes rápidos e barras sólidas.",
                "text_fx": ["kinetic", "stack", "scale", "bars", "slice"], "text_bg": ["bar", "block", "none", "highlight"],
                "camera": ["push_in", "shake", "still"], "emphasis": ["pop", "color_swap", "strike"],
                "ornament": ["big_number_bg", "none", "spin_ring"], "transition": ["cut", "wipe", "push", "flash", "blinds"],
                "fits": {"bold", "tech", "playful", "neutral"}, "avoid": {"luxury"}},
    "glitch": {"name": "Tech glitch", "ease": "snappy", "spin": .4,
               "desc": "Interface viva: digitação, cortes digitais, grades e varreduras, cara de terminal.",
               "text_fx": ["type", "slice", "flip", "bars", "zoom"], "text_bg": ["none", "bar", "glass"],
               "camera": ["shake", "push_in", "still", "parallax"], "emphasis": ["glow", "strike", "color_swap"],
               "ornament": ["grid_sweep", "spin_ring", "corner_brackets"], "transition": ["glitch", "cut", "blinds", "zoom", "wipe"],
               "fits": {"tech"}, "avoid": {"sober", "luxury", "playful"}},
    "colagem": {"name": "Revista/colagem", "ease": "snappy", "spin": .6,
                "desc": "Colagem gráfica: blocos de cor atrás do texto, selos girando, elementos tortos que assentam.",
                "text_fx": ["stack", "rotate", "split", "marker", "scale"], "text_bg": ["block", "highlight", "bar"],
                "camera": ["tilt", "drift", "still"], "emphasis": ["circle", "pop", "spin"],
                "ornament": ["rotating_badge", "spin_ring", "orbit_dots"], "transition": ["slide", "push", "wipe", "spin"],
                "fits": {"playful", "bold", "neutral"}, "avoid": {"luxury"}},
    "cinematico": {"name": "Cinemático", "ease": "smooth", "spin": .15,
                   "desc": "Trailer de cinema: câmera sempre em movimento, texto que vem de trás, revelações com íris e zoom.",
                   "text_fx": ["zoom", "blur", "rise", "scale"], "text_bg": ["none", "glass"],
                   "camera": ["push_in", "pull_out", "parallax", "drift"], "emphasis": ["glow", "underline_draw", "none"],
                   "ornament": ["none", "big_number_bg", "spin_ring"], "transition": ["zoom", "iris", "fade", "match", "flash"],
                   "fits": {"premium", "sober", "bold", "neutral"}, "avoid": set()},
    "pop": {"name": "Pop jovem", "ease": "snappy", "spin": .8,
            "desc": "Divertido e colorido: letras que pulam e giram, selos, pontos orbitando, transições com giro.",
            "text_fx": ["split", "wave", "flip", "kinetic", "scale"], "text_bg": ["highlight", "block", "none"],
            "camera": ["tilt", "spin_in", "push_in"], "emphasis": ["spin", "pop", "circle"],
            "ornament": ["orbit_dots", "rotating_badge", "spin_ring"], "transition": ["spin", "push", "wipe", "iris"],
            "fits": {"playful"}, "avoid": {"sober", "luxury"}},
    "suico": {"name": "Suíço minimal", "ease": "snappy", "spin": .1,
              "desc": "Grid suíço: alinhamento rígido, cortes secos, barras precisas, sem enfeite.",
              "text_fx": ["rise", "bars", "slice", "type"], "text_bg": ["none", "bar", "outline"],
              "camera": ["still", "drift"], "emphasis": ["underline_draw", "strike", "color_swap"],
              "ornament": ["corner_brackets", "grid_sweep", "none"], "transition": ["cut", "push", "wipe", "blinds"],
              "fits": {"tech", "neutral", "sober"}, "avoid": set()},
    "luxo": {"name": "Luxo respirado", "ease": "smooth", "spin": .15,
             "desc": "Alto padrão: serifas grandes, desfoques lentos, vidro sobre foto, íris e fades longos.",
             "text_fx": ["blur", "rise", "underline", "zoom"], "text_bg": ["none", "glass", "outline"],
             "camera": ["pull_out", "drift", "push_in"], "emphasis": ["underline_draw", "glow", "none"],
             "ornament": ["corner_brackets", "none", "rotating_badge"], "transition": ["fade", "iris", "slide", "zoom"],
             "fits": {"luxury", "premium", "sober"}, "avoid": {"tech"}},
    "manchete": {"name": "Manchete", "ease": "snappy", "spin": .3,
                 "desc": "Jornal/Reels: faixas sólidas atrás do texto, flashes, números enormes ao fundo.",
                 "text_fx": ["bars", "scale", "slice", "kinetic", "type"], "text_bg": ["bar", "block", "highlight"],
                 "camera": ["push_in", "shake", "still"], "emphasis": ["strike", "pop", "circle"],
                 "ornament": ["big_number_bg", "none", "rotating_badge"], "transition": ["flash", "cut", "wipe", "match"],
                 "fits": {"bold", "tech", "neutral"}, "avoid": {"luxury"}},
    "organico": {"name": "Orgânico fluido", "ease": "smooth", "spin": .35,
                 "desc": "Natureza e bem-estar: ondas, desfoques, pontos orbitando devagar, transições redondas.",
                 "text_fx": ["wave", "blur", "rise", "rotate"], "text_bg": ["none", "glass", "highlight"],
                 "camera": ["drift", "pull_out", "parallax"], "emphasis": ["glow", "circle", "underline_draw"],
                 "ornament": ["orbit_dots", "spin_ring", "none"], "transition": ["iris", "fade", "slide", "zoom"],
                 "fits": {"sober", "premium", "playful", "neutral"}, "avoid": {"tech"}},
}

# vetos por contexto: o que nunca combina
VETO = {
    "luxury": {"text_fx": {"split", "wave", "kinetic", "slice", "type"}, "camera": {"shake", "spin_in"},
               "emphasis": {"spin", "pop", "strike"}, "transition": {"glitch", "spin", "blinds", "flash"},
               "text_bg": {"bar", "block"}, "ornament": {"orbit_dots", "big_number_bg"}},
    "sober": {"camera": {"shake", "spin_in"}, "transition": {"glitch", "spin"}, "emphasis": {"spin"}},
    "tech": set(),
}

PACK_TAGS = {
    "imobiliario": {"premium", "sober"}, "residencial": {"premium", "sober"}, "saude": {"sober"},
    "financas": {"premium", "sober"}, "saas": {"tech"}, "seguranca": {"tech", "bold"},
    "varejo": {"playful", "bold"}, "educacao": {"playful"}, "gastronomia": {"playful"}, "geral": {"neutral"},
}

# energia da batida: o que cada função pede
FUNC_PREFS = {
    "mundo": {"text_fx": ["blur", "rise", "kinetic", "wave", "zoom"], "camera": ["drift", "pull_out", "push_in"],
              "transition": ["fade", "iris", "wipe"], "text_bg": ["none", "glass"]},
    "tensao": {"text_fx": ["slice", "bars", "type", "split", "kinetic"], "camera": ["shake", "push_in", "still"],
               "transition": ["cut", "glitch", "blinds", "flash", "wipe"], "text_bg": ["bar", "block", "none"],
               "emphasis": ["strike", "pop", "color_swap"]},
    "virada": {"text_fx": ["zoom", "scale", "rotate", "flip"], "camera": ["push_in", "tilt", "spin_in"],
               "transition": ["zoom", "match", "flash", "iris", "spin"], "emphasis": ["circle", "glow", "pop"],
               "ornament": ["spin_ring", "rotating_badge"]},
    "mecanismo": {"text_fx": ["rise", "stack", "type", "marker", "underline"], "camera": ["still", "drift", "parallax"],
                  "transition": ["push", "slide", "wipe", "cut"], "ornament": ["corner_brackets", "grid_sweep", "none"]},
    "prova": {"text_fx": ["scale", "underline", "stack", "bars"], "camera": ["push_in", "still"],
              "transition": ["zoom", "iris", "wipe"], "emphasis": ["pop", "circle", "underline_draw"],
              "ornament": ["rotating_badge", "big_number_bg"]},
    "impacto": {"text_fx": ["kinetic", "scale", "zoom", "blur"], "camera": ["push_in", "pull_out", "still"],
                "transition": ["flash", "match", "cut", "zoom"], "align": ["center"], "emphasis": ["glow", "pop"]},
}

# o verbo da frase pede o movimento
VERB_HINTS = [
    (r"\b(cai|caem|despenc|desab|perd|quebr|afund|some|sumir|atras)", {"text_fx": ["slice", "split"], "camera": ["shake"], "emphasis": ["strike"]}),
    (r"\b(cresc|sobe|sobem|escal|multiplic|aument|dispar|acelera)", {"text_fx": ["scale", "stack", "zoom"], "camera": ["push_in"], "emphasis": ["pop"]}),
    (r"\b(gir|vira|virou|mud|transform|troc|revir|ciclo|sempre)", {"text_fx": ["rotate", "flip"], "ornament": ["spin_ring"], "transition": ["spin"]}),
    (r"\b(conect|flui|flu[ie]|integr|une|junt|rede|ecossistema)", {"text_fx": ["wave", "rise"], "camera": ["drift"], "ornament": ["orbit_dots"]}),
    (r"\b(rápid|agora|segundos|instant|já\b|minutos)", {"text_fx": ["kinetic", "type"], "transition": ["wipe", "cut"]}),
    (r"\b(calm|respir|natureza|conforto|paz|silêncio|serra|mar)", {"text_fx": ["blur", "wave"], "camera": ["drift", "pull_out"], "transition": ["fade", "iris"]}),
    (r"\b(bloque|protege|garant|segur|blind|trava)", {"text_fx": ["bars"], "text_bg": ["bar", "block"], "ornament": ["corner_brackets", "rotating_badge"]}),
    (r"\b(nunca|chega|pare|fim|basta|não)\b", {"emphasis": ["strike"], "text_fx": ["slice", "bars"]}),
]


def context_tags(pack: str, style: dict | None = None, font: str | None = None, skin: str | None = None) -> set:
    tags = set(PACK_TAGS.get(pack or "geral", {"neutral"}))
    style = style or {}
    if font in ("luxury", "elegant") or style.get("font") in ("luxury", "elegant"):
        tags.add("luxury" if (font or style.get("font")) == "luxury" else "premium")
    if (skin or style.get("skin")) == "premium":
        tags.add("premium")
    if font == "tech" or style.get("font") == "tech":
        tags.add("tech")
    return tags or {"neutral"}


def _vetoed(tags: set) -> dict:
    out = {}
    for t in tags:
        for f, vals in (VETO.get(t) or {}).items():
            out.setdefault(f, set()).update(vals)
    return out


def film_dna(seed, pack: str = "geral", style: dict | None = None, font: str | None = None, skin: str | None = None) -> dict:
    """Receita do filme inteiro, filtrada pelo contexto (categoria, estilo das referências, fonte)."""
    tags = context_tags(pack, style, font, skin)
    r = rng(seed, "dna")
    ok = [k for k, v in RECIPES.items() if not (v["avoid"] & tags)] or list(RECIPES)
    weights = [1 + 3 * len(RECIPES[k]["fits"] & tags) for k in ok]
    rid = r.choices(ok, weights=weights)[0]
    rec = RECIPES[rid]
    veto = _vetoed(tags)
    prefs = {f: [v for v in rec[f] if v not in veto.get(f, set())] or [MOTION_FIELDS[f][0]]
             for f in ("text_fx", "text_bg", "camera", "emphasis", "ornament", "transition")}
    return {"recipe": rid, "name": rec["name"], "desc": rec["desc"], "ease": rec["ease"], "spin": rec["spin"],
            "prefs": prefs, "veto": {k: sorted(v) for k, v in veto.items()}, "tags": sorted(tags),
            "angle": ANGLES[derive(seed, "angle") % len(ANGLES)]}


def dna_prompt(dna: dict) -> str:
    p = dna["prefs"]
    txt = (f"RECEITA VISUAL desta versão: {dna['name']}. {dna['desc']} "
           f"Efeitos de texto preferidos: {', '.join(p['text_fx'])}. Transições preferidas: {', '.join(p['transition'])}. "
           f"Câmera: {', '.join(p['camera'])}. Base do texto: {', '.join(p['text_bg'])}.")
    if dna.get("veto"):
        txt += " NÃO use: " + "; ".join(f"{k} = {', '.join(v)}" for k, v in dna["veto"].items() if v) + "."
    return txt


# ---------- motion de uma cena ----------

def sanitize_motion(m) -> dict:
    """Só valores conhecidos; campos inválidos somem (o runtime usa o padrão)."""
    if not isinstance(m, dict):
        return {}
    out = {}
    for f, vals in MOTION_FIELDS.items():
        v = str(m.get(f) or "").strip().lower().replace("-", "_").replace(" ", "_")
        if v in vals:
            out[f] = v
    nome = re.sub(r"\s+", " ", str(m.get("nome") or "")).strip()[:40]
    if nome and out:
        out["nome"] = nome
    return out


def _words(headline: str) -> int:
    return len(re.sub(r"[*]", "", headline or "").split())


def _pick(r: random.Random, field: str, ctx: dict, dna: dict, avoid=()) -> str:
    """Sorteio ponderado: receita + função da batida + verbo da frase, sem vetos e sem repetir a vizinha."""
    veto = set(dna.get("veto", {}).get(field, [])) | set(avoid)
    score: dict[str, float] = {}
    for v in MOTION_FIELDS[field]:
        score[v] = 0.15
    for i, v in enumerate(dna["prefs"].get(field, [])):
        score[v] = score.get(v, 0) + 3 - i * 0.4
    for i, v in enumerate(FUNC_PREFS.get(ctx.get("funcao") or "", {}).get(field, [])):
        score[v] = score.get(v, 0) + 2.2 - i * 0.3
    head = (ctx.get("headline") or "").lower()
    for pat, hint in VERB_HINTS:
        if re.search(pat, head):
            for v in hint.get(field, []):
                score[v] = score.get(v, 0) + 2.5
    n = _words(ctx.get("headline"))
    if field == "text_fx":
        if n > 5:
            veto |= LETTER_FX | {"kinetic"}
        if n < 2:
            veto |= {"kinetic", "stack"}
        if ctx.get("has_component"):
            veto |= {"kinetic"}  # a palavra gigante no centro cobriria o componente
        if "*" not in (ctx.get("headline") or ""):
            veto |= {"marker", "underline"}
    if field == "emphasis" and "*" not in (ctx.get("headline") or ""):
        return "none"
    if field == "transition":
        if ctx.get("index") == 0:
            return r.choice([v for v in ("fade", "wipe", "iris") if v not in veto] or ["fade"])
        if ctx.get("cont_hero"):
            return "cut" if r.random() < .6 else "fade"
        if ctx.get("prev_loud"):
            veto |= LOUD_TRANS
        if not ctx.get("prev_has_acc"):
            veto |= {"match"}
    if field == "ornament":
        if r.random() > 0.42 + dna.get("spin", .3) * .5:
            return "none"
        veto |= {"none"}  # passou no sorteio: a cena ganha um ornamento de verdade
    if field == "ornament" and ctx.get("ui_type") not in (None, "none"):
        veto |= {"big_number_bg"}  # o número gigante só cabe em cena sem componente
    if field == "text_bg":
        if ctx.get("photo_full"):
            return r.choice(["glass", "bar"]) if r.random() < .7 else "glass"
        if ctx.get("recent_heavy_bg"):
            veto |= HEAVY_BG
    if field == "align":
        prefs = FUNC_PREFS.get(ctx.get("funcao") or "", {}).get("align")
        if prefs:
            return prefs[0]
        return "center" if not ctx.get("has_component") and r.random() < .45 else "left"
    cands = [(v, w) for v, w in score.items() if v not in veto and w > 0]
    if not cands:
        return MOTION_FIELDS[field][0]
    vals, ws = zip(*cands)
    return r.choices(vals, weights=[w * w for w in ws])[0]


def fallback_motion(dna: dict, seed: int, ctx: dict) -> dict:
    """Motion completo e coerente, sorteado sem IA (usado quando a IA falha ou no modo mock)."""
    r = random.Random(seed)
    prev = ctx.get("prev") or {}
    m = {}
    for f in ("text_fx", "camera", "transition", "text_bg", "emphasis", "ornament", "align"):
        avoid = [prev[f]] if prev.get(f) and f in ("text_fx", "camera", "transition", "ornament") and prev[f] not in ("none", "still") else []
        m[f] = _pick(r, f, ctx, dna, avoid)
    return harmonize(m, ctx)


def harmonize(m: dict, ctx: dict) -> dict:
    """Regras de bom senso: um gesto forte por cena, nada que brigue entre si."""
    m = dict(m)
    if m.get("camera") in ("spin_in", "shake") and m.get("text_fx") in ("kinetic", "split", "flip", "zoom", "wave"):
        m["text_fx"] = "rise" if m["camera"] == "spin_in" else "bars"
    if m.get("camera") == "spin_in" and m.get("transition") == "spin":
        m["camera"] = "still"
    if m.get("text_fx") == "kinetic" and m.get("text_bg") in HEAVY_BG:
        m["text_bg"] = "none"
    if m.get("text_fx") == "bars" and m.get("text_bg") == "bar":
        m["text_fx"] = "rise"
    if m.get("emphasis") == "spin" and m.get("ornament") in SPINNERS:
        m["emphasis"] = "pop"
    if ctx.get("photo_full") and m.get("text_bg") in (None, "none", "outline", "highlight"):
        m["text_bg"] = "glass"
    if m.get("ornament") == "big_number_bg" and ctx.get("ui_type") not in (None, "none"):
        m["ornament"] = "none"
    if ctx.get("cont_hero") and m.get("transition") not in ("cut", "fade"):
        m["transition"] = "cut"
    if "*" not in (ctx.get("headline") or ""):
        m["emphasis"] = "none"
        if m.get("text_fx") in ("marker", "underline"):
            m["text_fx"] = "rise"
        if m.get("text_bg") == "highlight":
            m["text_bg"] = "none"
    if _words(ctx.get("headline")) > 5 and m.get("text_fx") in LETTER_FX | {"kinetic"}:
        m["text_fx"] = "rise"
    if m.get("text_fx") == "kinetic" and ctx.get("has_component"):
        m["text_fx"] = "stack"
    return m


def idea_seeds(dna: dict, seed: int, ctx: dict, n: int = 3) -> list[dict]:
    """n ideias diferentes entre si (efeito de texto distinto) para provocar a IA ou servir de reserva."""
    out, used = [], set()
    for k in range(n * 4):
        m = fallback_motion(dna, derive(seed, "idea", k), ctx)
        if m["text_fx"] in used:
            continue
        extra = m["ornament"] if m.get("ornament") not in (None, "none") else m.get("camera")
        m["nome"] = f"{m['text_fx']} + {extra}".replace("_", " ")
        used.add(m["text_fx"]); out.append(m)
        if len(out) == n:
            break
    return out


def scene_ctx(scenes: list, i: int, *, light: bool = False) -> dict:
    """Contexto que as regras de motion precisam saber sobre a cena i (e a anterior)."""
    sc = scenes[i]
    prev = scenes[i - 1] if i > 0 else None
    ui = sc.get("ui") or {}
    pui = (prev or {}).get("ui") or {}
    pm = (prev or {}).get("motion") or {}
    recent = [(scenes[j].get("motion") or {}).get("text_bg") for j in range(max(0, i - 2), i)]
    return {"index": i, "funcao": sc.get("funcao"), "headline": sc.get("headline") or "", "ui_type": ui.get("type"),
            "has_component": ui.get("type") not in (None, "none"), "light": light,
            "photo_full": bool(sc.get("photo")) and (sc.get("layout") or "full") in ("full", "kenburns") and ui.get("type") != "big_word",
            "cont_hero": ui.get("type") == "hero" and pui.get("type") == "hero" and ui.get("hero") == pui.get("hero"),
            "prev": pm, "prev_loud": pm.get("transition") in LOUD_TRANS,
            "prev_has_acc": "*" in ((prev or {}).get("headline") or ""),
            "recent_heavy_bg": any(b in HEAVY_BG for b in recent)}


def choose(sc: dict, project_seed, i: int, dna: dict, ctx: dict) -> dict:
    """Motion final da cena: re-sorteio 0 = escolha da IA; 1, 2... = próximas ideias; depois, ideias novas sem IA."""
    ideas = [x for x in (sc.get("ideas") or []) if x]
    k = int(sc.get("reroll") or 0)
    pick = sc.get("pick") if isinstance(sc.get("pick"), int) and 0 <= sc.get("pick") < len(ideas) else 0
    if ideas and k < len(ideas):
        base = ideas[(pick + k) % len(ideas)]
        return harmonize(fill(base, dna, scene_seed(project_seed, i, k), ctx), ctx)
    return fallback_motion(dna, scene_seed(project_seed, i, k), ctx)


def fill(m: dict, dna: dict, seed: int, ctx: dict) -> dict:
    """Completa os campos que a IA não mandou com o sorteio da receita."""
    m = sanitize_motion(m)
    if all(f in m for f in MOTION_FIELDS):
        return m
    fb = fallback_motion(dna, seed, ctx)
    return {**fb, **m}


def dedupe(scenes: list, dna: dict, project_seed, light: bool = False, locked=lambda sc: False) -> None:
    """Passa pelo filme corrigindo repetições entre vizinhas e excessos (barras, giros, transições fortes)."""
    spins, max_spin = 0, max(1, (len(scenes) + 1) // 2)
    for i, sc in enumerate(scenes):
        if sc.get("ui", {}).get("type") == "big_word" or locked(sc):
            continue
        m = dict(sc.get("motion") or {})
        ctx = scene_ctx(scenes, i, light=light)
        prev = ctx["prev"]
        r = rng(project_seed, "dedupe", i, sc.get("reroll") or 0)
        for f in ("text_fx", "camera", "transition"):
            if prev.get(f) and m.get(f) == prev[f] and m[f] not in ("still",) and not (f == "transition" and ctx["cont_hero"]):
                if f == "transition" and m[f] in ("push", "slide") and ctx.get("funcao") == "mecanismo":
                    continue  # sequência de mecanismo na mesma direção é intencional
                alt = next((x.get(f) for x in sc.get("ideas") or [] if x.get(f) and x.get(f) != prev[f]), None)
                m[f] = alt or _pick(r, f, ctx, dna, [prev[f]])
        if m.get("text_bg") in HEAVY_BG and ctx["recent_heavy_bg"] and not ctx["photo_full"]:
            m["text_bg"] = "highlight" if "*" in ctx["headline"] else "none"
        if i >= 2 and m.get("transition") in LOUD_TRANS and all(
                (scenes[j].get("motion") or {}).get("transition") in LOUD_TRANS for j in (i - 1, i - 2)):
            m["transition"] = r.choice(["cut", "fade", "push"])
        spinning = m.get("ornament") in SPINNERS or m.get("emphasis") == "spin" or m.get("camera") == "spin_in"
        if spinning:
            if spins >= max_spin:
                if m.get("ornament") in SPINNERS:
                    m["ornament"] = "none"
                if m.get("emphasis") == "spin":
                    m["emphasis"] = "pop"
                if m.get("camera") == "spin_in":
                    m["camera"] = "tilt"
            else:
                spins += 1
        m = harmonize(m, ctx)
        for f in ("text_fx", "transition"):  # o harmonize pode ter trocado o efeito para um igual ao da vizinha
            if prev.get(f) and m.get(f) == prev[f] and not (f == "transition" and (ctx["cont_hero"] or m[f] in ("push", "slide"))):
                for _ in range(6):
                    m2 = harmonize({**m, f: _pick(r, f, ctx, dna, [prev[f]])}, ctx)
                    if m2.get(f) != prev[f]:
                        m = m2
                        break
        orig = sc.get("motion") or {}
        if any(m.get(f) != orig.get(f) for f in MOTION_FIELDS):
            m.pop("nome", None)  # deixou de ser a ideia que tinha esse nome
        sc["motion"] = m
