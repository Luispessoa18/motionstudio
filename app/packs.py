"""Pacotes de domínio: heróis (JS/CSS), descrição para a IA e roteiros-exemplo."""
import json
import re
from functools import lru_cache

from .config import BASE_DIR

PACKS_DIR = BASE_DIR / "packs"
SKILLS_DIR = BASE_DIR / "skills"


@lru_cache(maxsize=1)
def load_packs() -> dict:
    packs = {}
    for d in sorted(PACKS_DIR.iterdir()):
        pj = d / "pack.json"
        if not pj.exists():
            continue
        p = json.loads(pj.read_text(encoding="utf-8"))
        p["js"] = (d / "heroes.js").read_text(encoding="utf-8") if (d / "heroes.js").exists() else ""
        p["css"] = (d / "heroes.css").read_text(encoding="utf-8") if (d / "heroes.css").exists() else ""
        p["examples"] = [json.loads(f.read_text(encoding="utf-8")) for f in sorted((d / "examples").glob("*.json"))] if (d / "examples").exists() else []
        packs[p["id"]] = p
    # heróis emprestados de outro pacote (o JS de todos os pacotes já vai para o runtime)
    for p in packs.values():
        for name, src in (p.get("borrow_heroes") or {}).items():
            h = packs.get(src, {}).get("heroes", {}).get(name)
            if h:
                p.setdefault("heroes", {})[name] = h
    return packs


def categories() -> list[dict]:
    """Pacotes como categorias do onboarding, na ordem de exibição."""
    packs = load_packs()
    out = [{"id": p["id"], "name": p["name"], "description": p.get("description", ""), "icon": p.get("icon", ""),
            "onboarding": p.get("onboarding") or {}, "style": p.get("style_defaults") or {}}
           for p in packs.values()]
    return sorted(out, key=lambda c: packs[c["id"]].get("order", 9))


def all_heroes() -> dict:
    """{nome_do_heroi: [estados em ordem]} de todos os pacotes."""
    out = {}
    for p in load_packs().values():
        for name, h in p.get("heroes", {}).items():
            out[name] = list(h["states"])
    return out


def choose_pack(text: str, explicit: str | None = None) -> str:
    packs = load_packs()
    if explicit and explicit in packs:
        return explicit
    t = text.lower()
    best, score = "geral", 0
    for pid, p in packs.items():
        s = sum(t.count(k.lower()) for k in p.get("keywords", []))
        if s > score:
            best, score = pid, s
    return best if score >= 2 else "geral"


@lru_cache(maxsize=None)
def _skill(name: str) -> str:
    raw = (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")
    return re.sub(r"^---.*?---\s*", "", raw, flags=re.S).strip()


def skill_text(*names: str) -> str:
    """Corpo das skills pedidas (sem o cabeçalho), na ordem. Sem nomes: a skill de roteiro."""
    return "\n\n".join(_skill(n) for n in (names or ("roteiro",)))


def pack_prompt(pid: str) -> str:
    p = load_packs()[pid]
    lines = [f"PACOTE DE DOMÍNIO: {p['name']}. {p['description']}"]
    if p.get("heroes"):
        lines.append('Heróis disponíveis (ui.type = "hero", ui.hero = nome, ui.state = estado):')
        for name, h in p["heroes"].items():
            lines.append(f'- "{name}": {h["desc"]}')
            for st, desc in h["states"].items():
                lines.append(f'    · "{st}": {desc}')
            if h.get("fields"):
                lines.append(f"    campos: {h['fields']}")
    if p.get("metaphors"):
        lines.append("Boas escolhas visuais neste domínio:")
        lines += [f"- {m}" for m in p["metaphors"]]
    if p.get("notes"):
        lines.append(f"Tom: {p['notes']}")
    return "\n".join(lines)
