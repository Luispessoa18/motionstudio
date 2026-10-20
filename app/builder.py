"""Gera um HTML único e autocontido (runtime, GSAP, logo e imagens embutidos)."""
import base64
import html
import json
import logging
from pathlib import Path

from . import audio
from .config import RUNTIME_DIR
from .packs import load_packs
from .story import compile_spec

log = logging.getLogger("motion.builder")


def _b64(path: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def build_html(pdir: Path, project: dict) -> tuple[str, dict]:
    spec = compile_spec(project)
    spec["brand"]["logo"] = _b64(pdir / "logo.png", "image/png")
    svg = pdir / "logo.svg"
    spec["brand"]["svg"] = svg.read_text(encoding="utf-8") if svg.exists() and project["brand"].get("svg") else None
    spec["refs"] = {}
    for r in project.get("refs", []):
        p = pdir / "refs" / r["file"]
        if p.exists():
            spec["refs"][r["key"]] = {"src": _b64(p, "image/jpeg"), "ar": r["w"] / r["h"], "titulo": r.get("titulo") or ""}
    spec["icons"] = project.get("icons") or {}
    spec["stickers"] = project.get("stickers") or {}
    spec["audio"] = None
    try:
        track = audio.mix(pdir, project, spec)
        if track:
            spec["audio"] = _b64(track, "audio/mpeg")
    except Exception as e:  # sem trilha o vídeo continua funcionando
        log.warning("Trilha de áudio falhou: %s", e)
    if not spec["audio"]:
        (pdir / "audio" / "mix.mp3").unlink(missing_ok=True)
    css = (RUNTIME_DIR / "motion.css").read_text(encoding="utf-8")
    packs = load_packs()
    css += "\n" + "\n".join(p["css"] for p in packs.values())
    js = (RUNTIME_DIR / "motion.js").read_text(encoding="utf-8")
    js = js.replace("/*@@PACKS@@*/", "\n".join(f"/* pacote: {pid} */\n{p['js']}" for pid, p in packs.items()))
    gsap = (RUNTIME_DIR / "vendor" / "gsap.min.js").read_text(encoding="utf-8")
    data = json.dumps(spec, ensure_ascii=False).replace("</", "<\\/")
    title = html.escape(f"{project['brand'].get('name') or 'Motion'}, motion")
    doc = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{html.escape(spec['fontsCss'])}" rel="stylesheet">
<style>{css}</style>
</head>
<body>
<div id="stage"><div id="anchor"></div></div>
<button id="replay" type="button">Assistir de novo</button>
<script>{gsap}</script>
<script>window.MOTION_SPEC={data};</script>
<script>
(function(){{
  var T=window.MOTION_SPEC.theme, f=document.fonts;
  var load=f?Promise.all([f.load(T.weight+' 60px "'+T.fontDisplay+'"'),f.load('400 60px "'+T.fontDisplay+'"'),f.load((T.weightLight||400)+' 60px "'+T.fontDisplay+'"'),f.load('500 30px "'+T.fontBody+'"'),f.load('600 20px "'+T.fontMono+'"'),f.load('800 20px "'+T.fontMono+'"')]).then(function(){{return f.ready}}):Promise.resolve();
  var timeout=new Promise(function(r){{setTimeout(r,5000)}});
  Promise.race([load.catch(function(){{}}),timeout]).then(function(){{
{js}
  }});
}})();
</script>
</body>
</html>"""
    return doc, spec
