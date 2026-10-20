"""Mídia externa: fotos do Pexels/Pixabay (para o componente image) e ícones Lucide via Iconify (sem chave)."""
import logging
import re
from pathlib import Path

import httpx

from . import config
from .brand import process_ref

log = logging.getLogger("motion.stock")
ICON_RX = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def images_enabled() -> bool:
    return bool(config.PEXELS_API_KEY or config.PIXABAY_API_KEY)


async def _search(c: httpx.AsyncClient, query: str, portrait: bool) -> tuple[str, str] | None:
    """Devolve (url da imagem, crédito)."""
    if config.PEXELS_API_KEY:
        r = await c.get("https://api.pexels.com/v1/search", headers={"Authorization": config.PEXELS_API_KEY},
                        params={"query": query, "per_page": 5, "orientation": "portrait" if portrait else "landscape"})
        if r.status_code == 200 and r.json().get("photos"):
            p = r.json()["photos"][0]
            return p["src"]["large2x"], f"{p.get('photographer', '')} / Pexels"
        log.warning("Pexels sem resultado para %r (%s)", query, r.status_code)
    if config.PIXABAY_API_KEY:
        r = await c.get("https://pixabay.com/api/", params={
            "key": config.PIXABAY_API_KEY, "q": query, "image_type": "photo", "per_page": 5, "safesearch": "true",
            "orientation": "vertical" if portrait else "horizontal"})
        if r.status_code == 200 and r.json().get("hits"):
            h = r.json()["hits"][0]
            return h["largeImageURL"], f"{h.get('user', '')} / Pixabay"
        log.warning("Pixabay sem resultado para %r (%s)", query, r.status_code)
    return None


async def fetch_stock(pdir: Path, project: dict, raw: dict) -> None:
    """Baixa as fotos de banco pedidas no roteiro e as registra como referências:
    cenas "image" com "stock" e fotos de fundo ("photo" com uma busca em inglês em vez de uma chave ref)."""
    scenes = [s for s in (raw.get("scenes") or []) if isinstance(s, dict)]
    keys = {r["key"] for r in project["refs"]}
    wanted = [(s["ui"], "stock", "image") for s in scenes if isinstance(s.get("ui"), dict) and s["ui"].get("type") == "image"
              and s["ui"].get("stock") and s["ui"].get("image") not in keys]
    wanted += [(s, "photo", "photo") for s in scenes if isinstance(s.get("photo"), str) and s["photo"].strip()
               and s["photo"] not in keys]
    if not wanted:
        return
    if not images_enabled():
        log.warning("Roteiro pediu fotos, mas não há chave do Pexels/Pixabay.")
        return
    portrait = project["options"].get("format") == "portrait"
    refs = project["refs"]
    (pdir / "refs").mkdir(exist_ok=True)
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        for ui, qk, dest in wanted:
            query = str(ui[qk]).strip()[:80]
            hit = next((r for r in refs if r.get("query") == query), None)
            if not hit:
                try:
                    found = await _search(c, query, portrait)
                    if not found:
                        if dest == "photo":
                            ui.pop("photo", None)
                        continue
                    img = await c.get(found[0])
                    img.raise_for_status()
                    rp = process_ref(img.content)
                except Exception as e:
                    log.warning("Falha ao baixar foto %r: %s", query, e)
                    if dest == "photo":
                        ui.pop("photo", None)
                    continue
                n = 1 + sum(1 for r in refs if r["key"].startswith("stock"))
                hit = {"key": f"stock{n}", "file": f"stock{n}.jpg", "name": query, "query": query,
                       "credit": found[1], "w": rp["w"], "h": rp["h"]}
                (pdir / "refs" / hit["file"]).write_bytes(rp["jpg"])
                refs.append(hit)
            ui[dest] = hit["key"]


def _icon_names(story: dict) -> set[str]:
    names = set()
    for sc in story["scenes"]:
        ui = sc["ui"]
        for it in (ui.get("items") or []) + (ui.get("nodes") or []):
            if it.get("icon"):
                names.add(it["icon"])
    return names


async def _icon(c: httpx.AsyncClient, name: str):
    """Ícone Solar duotone (dois tons, mais elaborado); se não existir, busca o mais parecido; por fim Lucide."""
    base = re.sub(r"-(bold|linear|outline|broken|duotone|bold-duotone|line-duotone)$", "", name)
    r = await c.get(f"https://api.iconify.design/solar/{base}-bold-duotone.svg")
    if r.status_code == 200 and "<svg" in r.text:
        return r
    for prefix in ("solar", "lucide"):
        s = await c.get("https://api.iconify.design/search", params={"query": base.replace("-", " "), "prefix": prefix, "limit": 20})
        hits = s.json().get("icons", []) if s.status_code == 200 else []
        if prefix == "solar":
            hits = [h for h in hits if h.endswith("-bold-duotone")]
        if hits:
            r = await c.get(f"https://api.iconify.design/{hits[0].replace(':', '/')}.svg")
            if r.status_code == 200 and "<svg" in r.text:
                return r
    return None


async def fetch_icons(pdir: Path, project: dict) -> None:
    """Baixa os SVGs dos ícones citados no roteiro para pdir/icons (cache) e guarda em project["icons"]."""
    folder = pdir / "icons2"  # pasta nova: ícones Solar duotone (a antiga "icons" tinha Lucide)
    icons = {}
    missing = []
    for name in _icon_names(project["story"]):
        if not ICON_RX.match(name):
            continue
        f = folder / f"{name}.svg"
        if f.exists():
            icons[name] = f.read_text(encoding="utf-8")
        else:
            missing.append(name)
    if missing:
        folder.mkdir(parents=True, exist_ok=True)
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                for name in missing:
                    r = await _icon(c, name)
                    if r is None:
                        continue
                    (folder / f"{name}.svg").write_text(r.text, encoding="utf-8")
                    icons[name] = r.text
        except Exception as e:
            log.warning("Falha ao buscar ícones: %s", e)
    project["icons"] = icons


STICKER_SETS = "fluent-emoji-flat,noto"


async def fetch_stickers(pdir: Path, project: dict) -> None:
    """Ilustrações coloridas (Fluent Emoji Flat / Noto, via Iconify) pedidas nas cenas com "sticker"."""
    folder = pdir / "stickers"
    out = {}
    words = {sc["sticker"] for sc in project["story"]["scenes"] if sc.get("sticker")}
    missing = []
    for w in words:
        f = folder / (re.sub(r"[^a-z0-9]+", "-", w) + ".svg")
        if f.exists():
            out[w] = f.read_text(encoding="utf-8")
        else:
            missing.append((w, f))
    if missing:
        folder.mkdir(parents=True, exist_ok=True)
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                for w, f in missing:
                    s = await c.get("https://api.iconify.design/search", params={"query": w, "prefixes": STICKER_SETS, "limit": 12})
                    hits = s.json().get("icons", []) if s.status_code == 200 else []
                    if not hits:
                        log.info("Sem ilustração para %r", w)
                        continue
                    slug = re.sub(r"[^a-z0-9]+", "-", w).strip("-")
                    hits.sort(key=lambda h: (not h.endswith(":" + slug), not h.startswith("fluent")))  # nome exato, depois Fluent
                    r = await c.get(f"https://api.iconify.design/{hits[0].replace(':', '/')}.svg")
                    if r.status_code == 200 and "<svg" in r.text:
                        f.write_text(r.text, encoding="utf-8")
                        out[w] = r.text
        except Exception as e:
            log.warning("Falha ao buscar ilustrações: %s", e)
    project["stickers"] = out
