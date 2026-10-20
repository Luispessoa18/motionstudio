"""Roteiro ("story"): o JSON que a IA escreve. Aqui ficam o schema, a limpeza e a compilação para o runtime."""
import re

import random

from .brand import THEMES, glow_for, ink_for, make_theme, on_light
from .config import FONTS, FORMATS, MONO_FONT
from . import seeds
from .seeds import FUNCOES, MOTION_FIELDS, TEXT_FX, sanitize_motion

UI_TYPES = ["none", "counter", "cards", "chat", "flow", "checklist", "steps", "table",
            "verdict", "feed", "bars", "image", "gallery", "big_word", "hero"]

# Efeitos de entrada do logo (abertura e fecho). "draw" precisa do logo em SVG.
REVEALS = ["draw", "blur", "wipe", "slices", "glitch", "pixel", "iris", "shatter", "impact"]

# Como a foto da cena aparece e como a headline entra.
LAYOUTS = ["full", "split", "card", "kenburns"]

# Decoração animada do fundo.
DECOS = ["orbs", "shapes", "rings", "lines", "waves", "none"]

_S = {"type": "string"}
STORY_SCHEMA = {
    "type": "object",
    "properties": {
        "font": {"type": "string", "enum": list(FONTS)},
        "particles": {"type": "string", "enum": ["dash", "bits"]},
        "tagline": _S,
        "outro_narration": _S,
        "skin": {"type": "string", "enum": ["premium", "clean"]},
        "deco": {"type": "string", "enum": ["orbs", "shapes", "rings", "lines", "waves", "none"]},
        "logo_intro": {"type": "string", "enum": REVEALS},
        "logo_outro": {"type": "string", "enum": REVEALS},
        "scenes": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "direction": _S, "headline": _S, "caption": _S, "narration": _S, "photo": _S, "sticker": _S, "eyebrow": _S,
                "layout": {"type": "string", "enum": LAYOUTS}, "text_fx": {"type": "string", "enum": TEXT_FX},
                "funcao": {"type": "string", "enum": FUNCOES},
                "ui": {"type": "object", "properties": {
                    "type": {"type": "string", "enum": UI_TYPES},
                    "title": _S, "label": _S, "value": _S, "note": _S, "status": _S, "reason": _S,
                    "stamp": _S, "word": _S, "pre": _S, "image": _S, "highlight": {"type": "integer"},
                    "hero": _S, "state": _S, "stock": _S,
                    "items": {"type": "array", "items": {"type": "object", "properties": {
                        "label": _S, "value": _S, "sub": _S, "icon": _S, "image": _S}, "required": ["label"]}},
                    "segments": {"type": "array", "items": {"type": "object", "properties": {
                        "label": _S, "pct": {"type": "number"}}, "required": ["label", "pct"]}},
                    "messages": {"type": "array", "items": {"type": "object", "properties": {
                        "role": {"type": "string", "enum": ["user", "agent", "external"]},
                        "text": _S, "highlight": {"type": "boolean"}}, "required": ["role", "text"]}},
                    "nodes": {"type": "array", "items": {"type": "object", "properties": {
                        "title": _S, "sub": _S, "icon": _S}, "required": ["title"]}},
                    "steps": {"type": "array", "items": {"type": "object", "properties": {
                        "title": _S, "detail": _S, "lines": {"type": "array", "items": _S}},
                        "required": ["title", "lines"]}},
                    "columns": {"type": "array", "items": _S},
                    "rows": {"type": "array", "items": {"type": "array", "items": _S}},
                    "lines": {"type": "array", "items": _S},
                }, "required": ["type"]},
            },
            "required": ["headline", "ui"],
        }},
    },
    "required": ["font", "scenes"],
}

INTRO_DUR, OUTRO_DUR, OVERLAP = 3.6, 4.8, 0.25
VOICE_AT, VOICE_TAIL = 0.35, 0.75  # a fala começa 0,35s após a cena entrar e deixa 0,75s de respiro


def story_schema(pid: str) -> dict:
    """Schema com os heróis e estados do pacote escolhido como enum (o Ollama força a saída a obedecer)."""
    import copy
    from .packs import load_packs
    sch = copy.deepcopy(STORY_SCHEMA)
    heroes = load_packs().get(pid, {}).get("heroes", {})
    ui = sch["properties"]["scenes"]["items"]["properties"]["ui"]["properties"]
    if heroes:
        ui["hero"] = {"type": "string", "enum": list(heroes)}
        ui["state"] = {"type": "string", "enum": sorted({st for h in heroes.values() for st in h["states"]})}
    else:
        ui["type"]["enum"] = [t for t in UI_TYPES if t != "hero"]
        ui.pop("hero"); ui.pop("state")
    return sch


def _s(v, maxw=None):
    if v is None:
        return ""
    v = re.sub(r"\s+", " ", str(v)).strip()
    if maxw:
        words = v.split(" ")
        if len(words) > maxw:
            v = " ".join(words[:maxw]).rstrip(",;:") + "…"
    return v


def _icon(v) -> str:
    """Nome de ícone Lucide em kebab-case (ex. "shield-check"); vazio se inválido."""
    v = re.sub(r"[^a-z0-9-]+", "-", str(v or "").strip().lower().split(":")[-1]).strip("-")
    return v[:40]


def _items(lst, n=5):
    out = []
    for it in (lst or [])[:n]:
        if isinstance(it, str):
            it = {"label": it}
        if not isinstance(it, dict):
            continue
        lab = _s(it.get("label") or it.get("title") or it.get("text"), 8)
        if lab:
            item = {"label": lab, "value": _s(it.get("value"), 4), "sub": _s(it.get("sub"), 10)}
            if _icon(it.get("icon")):
                item["icon"] = _icon(it.get("icon"))
            out.append(item)
    return out


def normalize_ui(ui: dict, ref_keys: list) -> dict:
    ui = dict(ui or {})
    t = ui.get("type") if ui.get("type") in UI_TYPES else None
    if not t:  # tenta inferir pelo conteúdo
        for key, guess in (("messages", "chat"), ("steps", "steps"), ("nodes", "flow"), ("rows", "table"),
                           ("lines", "feed"), ("word", "big_word"), ("status", "verdict"), ("items", "cards"),
                           ("value", "counter")):
            if ui.get(key):
                t = guess; break
    t = t or "none"
    if t == "hero" or (ui.get("hero") and t == "none"):
        from .packs import all_heroes
        heroes = all_heroes()
        name = ui.get("hero")
        if name not in heroes:
            return {"type": "none"}
        states = heroes[name]
        st = ui.get("state") if ui.get("state") in states else states[0]
        u = {"type": "hero", "hero": name, "state": st}
        for k, n in (("title", 6), ("label", 6), ("value", 5), ("note", 16), ("status", 2), ("reason", 18)):
            if ui.get(k):
                u[k] = _s(ui[k], n)
        if isinstance(ui.get("highlight"), int):
            u["highlight"] = ui["highlight"]
        items = _items(ui.get("items"), 6)
        if items:
            u["items"] = items
        return u
    u = {"type": t}
    if t == "counter":
        u.update(label=_s(ui.get("label"), 10), value=_s(ui.get("value"), 3), note=_s(ui.get("note"), 20))
        segs = []
        for sg in (ui.get("segments") or [])[:3]:
            if isinstance(sg, dict) and sg.get("label"):
                try:
                    pct = float(sg.get("pct"))
                except (TypeError, ValueError):
                    pct = None
                segs.append({"label": _s(sg["label"], 6), "pct": pct})
        if segs:
            u["segments"] = segs
        if not u["value"]:
            return normalize_ui({**ui, "type": "cards"}, ref_keys) if ui.get("items") else {"type": "none"}
    elif t in ("cards", "bars"):
        u["items"] = _items(ui.get("items"), 5 if t == "cards" else 4)
        u["note"] = _s(ui.get("note"), 20)
        if not u["items"]:
            return {"type": "none"}
    elif t == "checklist":
        u.update(title=_s(ui.get("title"), 6), stamp=_s(ui.get("stamp"), 5),
                 items=_items(ui.get("items") or ui.get("lines"), 6))
        if not u["items"]:
            return {"type": "none"}
    elif t == "chat":
        msgs = []
        for m in (ui.get("messages") or [])[:6]:
            if isinstance(m, dict) and m.get("text"):
                role = m.get("role") if m.get("role") in ("user", "agent", "external") else "agent"
                msgs.append({"role": role, "text": _s(m["text"], 30), "highlight": bool(m.get("highlight"))})
        if not msgs:
            return {"type": "none"}
        u.update(title=_s(ui.get("title"), 6), note=_s(ui.get("note"), 3), messages=msgs)
    elif t == "flow":
        nodes = [{"title": _s(n.get("title"), 3), "sub": _s(n.get("sub"), 5), **({"icon": _icon(n["icon"])} if _icon(n.get("icon")) else {})}
                 for n in (ui.get("nodes") or [])[:4] if isinstance(n, dict) and n.get("title")]
        if len(nodes) < 2:
            return {"type": "none"}
        hi = ui.get("highlight")
        u.update(nodes=nodes, label=_s(ui.get("label"), 4),
                 highlight=hi if isinstance(hi, int) and 0 <= hi < len(nodes) else len(nodes) - 1)
    elif t == "steps":
        steps = []
        for st in (ui.get("steps") or [])[:5]:
            if isinstance(st, dict) and st.get("title"):
                steps.append({"title": _s(st["title"], 5), "detail": _s(st.get("detail"), 10),
                              "lines": [_s(x, 10) for x in (st.get("lines") or [])[:5] if _s(x)]})
        if len(steps) < 2:
            return normalize_ui({**ui, "type": "checklist", "items": [s["title"] for s in steps]}, ref_keys) if steps else {"type": "none"}
        u["steps"] = steps
    elif t == "table":
        cols = [_s(c, 3) for c in (ui.get("columns") or [])[:4] if _s(c)]
        rows = [[_s(c, 5) for c in r][:len(cols)] for r in (ui.get("rows") or [])[:6] if isinstance(r, list)]
        if len(cols) < 2 or not rows:
            return {"type": "none"}
        u.update(title=_s(ui.get("title"), 6), columns=cols, rows=[r + [""] * (len(cols) - len(r)) for r in rows])
    elif t == "verdict":
        u.update(status=_s(ui.get("status") or "VEREDITO", 2).upper()[:14], reason=_s(ui.get("reason"), 26),
                 stamp=_s(ui.get("stamp"), 5), items=_items(ui.get("items"), 4))
    elif t == "feed":
        lines = [_s(x, 8) for x in (ui.get("lines") or [i.get("label") for i in _items(ui.get("items"), 16)]) if _s(x)][:16]
        if len(lines) < 3:
            return {"type": "none"}
        u.update(title=_s(ui.get("title"), 5), label=_s(ui.get("label"), 2), note=_s(ui.get("note"), 2), lines=lines)
    elif t == "image":
        key = ui.get("image") if ui.get("image") in ref_keys else (ref_keys[0] if ref_keys else None)
        if not key:
            return {"type": "none"}
        u.update(image=key, items=_items(ui.get("items"), 3))
        if ui.get("stock"):
            u["stock"] = _s(ui["stock"], 10)
    elif t == "gallery":
        its = [{"image": it["image"], "label": _s(it.get("label"), 5)} for it in (ui.get("items") or [])
               if isinstance(it, dict) and it.get("image") in ref_keys][:4]
        if len(its) < 2:
            return {"type": "none"}
        u.update(items=its)
    elif t == "big_word":
        word = _s(ui.get("word"), 2).upper()
        if not word:
            return {"type": "none"}
        u.update(word=word[:12], pre=_s(ui.get("pre"), 8))
    return u


def normalize_story(raw: dict, ref_keys: list, max_scenes: int = 9) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    scenes = []
    for sc in (raw.get("scenes") or [])[:max_scenes]:
        if not isinstance(sc, dict):
            continue
        ui = normalize_ui(sc.get("ui") or {}, ref_keys)
        head = _s(sc.get("headline"), 9)
        if not head and ui["type"] != "big_word":
            continue
        scene = {"headline": head, "caption": _s(sc.get("caption"), 24), "ui": ui}
        if _s(sc.get("narration")):
            scene["narration"] = _s(sc.get("narration"), 70)
        if sc.get("photo") in ref_keys and ui["type"] not in ("image", "big_word"):
            scene["photo"] = sc["photo"]
            scene["layout"] = sc.get("layout") if sc.get("layout") in LAYOUTS else "full"
        if sc.get("funcao") in FUNCOES:
            scene["funcao"] = sc["funcao"]
        motion = sanitize_motion(sc.get("motion"))
        if sc.get("text_fx") in TEXT_FX and "text_fx" not in motion:  # roteiros antigos: text_fx solto na cena
            motion["text_fx"] = sc["text_fx"]
        if motion:
            scene["motion"] = motion
        ideas = [m for m in (sanitize_motion(x) for x in (sc.get("ideas") or [])[:3]) if m]
        if ideas:
            scene["ideas"] = ideas
            if isinstance(sc.get("pick"), int) and 0 <= sc["pick"] < len(ideas):
                scene["pick"] = sc["pick"]
        for k in ("seed", "reroll"):
            if isinstance(sc.get(k), int) and sc[k] >= 0:
                scene[k] = sc[k]
        if sc.get("motion_locked"):
            scene["motion_locked"] = True
        if _s(sc.get("direction")):
            scene["direction"] = _s(sc.get("direction"), 140)
        eb = _s(sc.get("eyebrow"), 5)
        if eb and len(eb) <= 34 and ui["type"] != "big_word":
            scene["eyebrow"] = eb
        st = str(sc.get("sticker") or "").strip().lower()
        if re.fullmatch(r"[a-z][a-z \-]{1,30}", st) and ui["type"] != "big_word":
            scene["sticker"] = st
        scenes.append(scene)
    if not scenes:
        raise ValueError("O roteiro veio sem cenas válidas.")
    return {
        "font": raw.get("font") if raw.get("font") in FONTS else "grotesk",
        "particles": raw.get("particles") if raw.get("particles") in ("dash", "bits") else "dash",
        "tagline": _s(raw.get("tagline"), 12),
        "outro_narration": _s(raw.get("outro_narration"), 24),
        "deco": raw.get("deco") if raw.get("deco") in DECOS else None,
        "skin": raw.get("skin") if raw.get("skin") in ("premium", "clean") else None,
        "logo_intro": raw.get("logo_intro") if raw.get("logo_intro") in REVEALS else None,
        "logo_outro": raw.get("logo_outro") if raw.get("logo_outro") in REVEALS else None,
        "scenes": scenes,
    }


def _weight(sc) -> float:
    t = sc["ui"]["type"]
    base = {"none": 4.0, "counter": 5.6, "cards": 5.4, "chat": 6.2, "flow": 5.2, "checklist": 5.2,
            "table": 5.4, "verdict": 6.4, "feed": 5.6, "bars": 5.2, "image": 5.0, "big_word": 5.0,
            "gallery": 3.4 + 1.4 * len(sc["ui"].get("items", []))}.get(t, 5.0)
    if t == "steps":
        base = 3.6 * len(sc["ui"]["steps"]) + 1.4
    if t == "hero":
        base = 5.4 + 0.25 * len(sc["ui"].get("items", []))
    words = len((sc["headline"] + " " + sc["caption"]).split())
    return base + max(0, words - 14) * 0.08


def pick_reveals(project: dict) -> dict:
    """Efeito de abertura e de fecho do logo: escolha do usuário > escolha da IA > sorteio fixo por projeto.
    Os dois nunca são iguais, e "draw" só entra quando o logo virou SVG."""
    opt, story, brand = project["options"], project["story"], project["brand"]
    ok = [r for r in REVEALS if r != "draw" or brand.get("svg")]
    vis = (brand.get("vision") or {}).get("reveal")
    def choose(key, avoid, k):
        if opt.get(key) in ok:  # escolha explícita do usuário sempre vale
            return opt[key]
        for c in (story.get(key), vis if k == 0 else None):
            if c in ok and c != avoid:
                return c
        rest = [r for r in ok if r != avoid]
        return random.Random(f"{project.get('id', '')}:{project.get('seed', 0)}:{key}").choice(rest)
    intro = choose("logo_intro", None, 0)
    return {"intro": intro, "outro": choose("logo_outro", intro, 1)}


def _deco_palette(brand_pal: list, th: dict) -> list:
    """Cores da decoração: as da marca (sem cinzas), mesmo que o destaque do texto seja neutro."""
    cols = [c for c in brand_pal if _sat(c) > 0.18] or [c for c in th["palette"] if _sat(c) > 0.18] or th["palette"]
    if th["mode"] == "light":
        cols = [on_light(c) for c in cols]
    return (cols * 3)[:3]


def _sat(h: str) -> float:
    r, g, b = (int(h.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    return (max(r, g, b) - min(r, g, b)) / max(max(r, g, b), 1)


def _cat_style(project: dict) -> dict:
    from .packs import load_packs
    return load_packs().get(project.get("pack", "geral"), {}).get("style_defaults") or {}


def pick_deco(project: dict) -> str:
    """Decoração animada do fundo: escolha do usuário > da IA > sorteio fixo por projeto."""
    for c in (project["options"].get("deco"), project["story"].get("deco"), (project.get("style") or {}).get("deco"), _cat_style(project).get("deco")):
        if c in DECOS:
            return c
    return random.Random(f"{project.get('id', '')}:{project.get('seed', 0)}:deco").choice(DECOS[:5])


def compile_spec(project: dict) -> dict:
    """Junta roteiro + opções + marca e calcula os tempos de cada cena."""
    story, opt, brand = project["story"], project["options"], project["brand"]
    fmt = FORMATS[opt.get("format", "landscape")]
    scenes = [dict(s) for s in story["scenes"]]
    pseed = int(project.get("seed") or 11)
    for i, s in enumerate(scenes):  # semente própria de cada cena: mudar uma não mexe nas outras
        s["seed"] = s.get("seed") or seeds.scene_seed(pseed, i, s.get("reroll") or 0)
        s.pop("ideas", None)
        if "motion" not in s and s.get("text_fx"):
            s["motion"] = {"text_fx": s["text_fx"]}
    weights = [_weight(s) for s in scenes]
    target = opt.get("duration", "auto")
    if target != "auto":
        avail = float(target) - INTRO_DUR - OUTRO_DUR + OVERLAP * (len(scenes) + 1)
        k = avail / sum(weights)
        mins = [max(3.2, 2.6 * len(s["ui"].get("steps", [])) + 1.2) for s in scenes]
        durs = [max(m, w * k) for w, m in zip(weights, mins)]
    else:
        durs = weights
    # Com narração, a cena dura pelo menos o tempo da fala (o locutor nunca é cortado).
    voice = project.get("voice") or {}
    for i, clip in enumerate((voice.get("scenes") or [])[:len(scenes)]):
        if clip:
            scenes[i]["voice_at"] = VOICE_AT
            durs[i] = max(durs[i], VOICE_AT + clip["dur"] + VOICE_TAIL)
    outro_dur = OUTRO_DUR
    if voice.get("outro"):
        outro_dur = max(OUTRO_DUR, 0.6 + voice["outro"]["dur"] + 1.0)
    at = INTRO_DUR - OVERLAP
    for s, d in zip(scenes, durs):
        s["at"], s["dur"] = round(at, 3), round(d, 3)
        at += d - OVERLAP
    outro_at = round(at, 3)
    total = round(outro_at + outro_dur, 3)

    font = FONTS.get(opt.get("font") or story.get("font"), FONTS["grotesk"])
    pal = list(brand.get("palette") or [])
    # a paleta já traz a cor do logo clareada para aparecer sobre preto (ex.: azul-marinho vira azul)
    accent = opt.get("accent") or (pal[0] if pal else None) or brand.get("accent") or "#FFFFFF"
    if accent.upper() in ("#FFFFFF", "#FFF"):
        pal = ["#FFFFFF", "#BDBDBD", "#7A7A7A"]
    else:
        pal = [accent] + [c for c in pal if c.upper() != accent.upper()]
        pal = (pal + ["#FFFFFF", "#8C8C8F"])[:3]
    mode = brand.get("theme") if brand.get("theme") in THEMES else "dark"
    th = make_theme(mode, pal)
    acc = th["acc"]
    portrait = fmt["h"] > fmt["w"]
    # letra fina some no fundo claro: o peso "leve" da headline mista nunca fica abaixo de 500 ali
    wl = int(font.get("light", "400"))
    wl = max(wl, 500) if th["mode"] == "light" else max(wl, 400)
    dna = project.get("dna") or {}
    theme = {
        "bg": th["bg"], "fg": th["fg"], "muted": th["muted"], "card": th["card"], "line": th["line"], "mode": th["mode"],
        "acc": acc, "accInk": ink_for(acc), "accGlow": glow_for(acc), "palette": th["palette"],
        "plateInk": th["plateInk"],
        "fontDisplay": font["display"], "fontBody": (font.get("body") or {}).get("name") or font["display"],
        "fontMono": MONO_FONT["name"], "weight": font["weight"],
        "stretch": font["stretch"], "particles": story.get("particles", "dash"),
        "texture": "dots" if acc.upper() in ("#FFFFFF", "#FFF", "#141416") else "grid",
        "deco": pick_deco(project),
        "skin": opt.get("skin") or story.get("skin") or (project.get("style") or {}).get("skin") or _cat_style(project).get("skin") or "premium",
        "textFx": (project.get("style") or {}).get("text_fx"),
        "weightLight": str(wl),
        "accPh": th.get("accPh") or acc,
        "minFont": 84 if portrait else 72,
        # serifadas de olho pequeno (Cormorant, Fraunces) parecem menores no mesmo tamanho: compensa
        "fontScale": {"Cormorant Garamond": 1.2, "Fraunces": 1.06}.get(font["display"], 1),
        "ease": dna.get("ease") or "smooth", "spin": dna.get("spin", .3),
        "decoPalette": _deco_palette(brand.get("palette") or [], th),
    }
    return {
        "format": {"w": fmt["w"], "h": fmt["h"]}, "seed": pseed,
        "duration": total, "progress": bool(opt.get("progress", True)),
        "theme": theme,
        "fontsCss": "https://fonts.googleapis.com/css2?" + "&".join(
            [font["css"]] + ([font["body"]["css"]] if font.get("body") else []) + [MONO_FONT["css"], "display=swap"]),
        "brand": {"name": brand.get("name", ""), "tagline": opt.get("tagline") or story.get("tagline") or "",
                  "cta": opt.get("cta") or "", "logoW": brand["logo_w"], "logoH": brand["logo_h"],
                  "plate": th["plate"] if brand.get("fix") == "plate" else None,
                  "reveal": pick_reveals(project)},
        "intro": {"dur": INTRO_DUR}, "outro": {"at": outro_at, "dur": outro_dur},
        "scenes": scenes,
    }
