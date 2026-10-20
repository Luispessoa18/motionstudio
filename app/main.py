"""Motion Studio: API FastAPI que transforma pitch + logo + referências em motion HTML, MP4 e WebM."""
import asyncio
import io
import json
import random
import re
import logging
import shutil
import threading
import time
import uuid
import zipfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import audio, config, kitten, llm, seeds, stock, voice
from .brand import THEMES, auto_fix, brand_palette, preview_jpg, process_logo, process_ref, suggest_theme
from .builder import build_html
from .packs import categories, choose_pack, load_packs
from .render import render_video
from .story import DECOS, REVEALS, normalize_story

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("motion")
app = FastAPI(title="Motion Studio")
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")
JOBS: dict[str, dict] = {}
VIDEO_TYPES = {"mp4": "video/mp4", "webm": "video/webm"}


def _pdir(pid: str) -> Path:
    p = config.PROJECTS_DIR / pid
    if not pid.isalnum() or not (p / "project.json").exists():
        raise HTTPException(404, "Projeto não encontrado.")
    return p


def _load(pid: str) -> dict:
    return json.loads((_pdir(pid) / "project.json").read_text(encoding="utf-8"))


def _write(pdir: Path, project: dict) -> None:
    (pdir / "project.json").write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")


async def _save_and_build(pdir: Path, project: dict) -> dict:
    """Busca ícones e narração (com cache), monta o HTML e salva o projeto."""
    warnings = []
    _ensure_motion(project)
    if "theme" not in project["brand"]:  # projeto de versão anterior: escolhe o fundo, gera SVG e paleta agora
        o = project["options"]
        await asyncio.to_thread(_apply_logo, pdir, project["brand"], o.get("logo_fix"), o.get("theme"))
    await stock.fetch_icons(pdir, project)
    await stock.fetch_stickers(pdir, project)
    try:
        await voice.synthesize(pdir, project)
    except Exception as e:  # sem voz o vídeo continua; o aviso aparece na interface
        log.warning("Narração falhou: %s", e)
        project.pop("voice", None)
        warnings.append(f"Narração não gerada: {e}")
    if project["options"].get("narration") and not voice.enabled():
        warnings.append("Narração ligada, mas falta a chave da ElevenLabs (Configurações).")
    doc, spec = build_html(pdir, project)
    (pdir / "motion.html").write_text(doc, encoding="utf-8")
    project["duration"] = spec["duration"]
    project["reveal"] = spec["brand"]["reveal"]
    project["updated"] = time.time()
    project["has_audio"] = bool(spec.get("audio"))
    _write(pdir, project)
    for ext in VIDEO_TYPES:
        (pdir / f"video.{ext}").unlink(missing_ok=True)
    return _public(project) | {"warnings": warnings}


def _apply_logo(pdir: Path, brand: dict, fix: str | None = None, theme: str | None = None) -> None:
    """(Re)processa o logo a partir do arquivo original: fundo do vídeo (dark/light/brand), contraste
    (none/invert/plate), PNG, SVG e paleta. fix/theme None = automático."""
    src = pdir / "logo_src.png"
    data = (src if src.exists() else pdir / "logo.png").read_bytes()
    vis = brand.get("vision") or {}
    style_files = sorted((pdir / "refs").glob("sty*.jpg")) or sorted((pdir / "refs").glob("ref*.jpg"))
    refs = [f.read_bytes() for f in style_files]
    if "theme_auto" not in brand:
        m = process_logo(data, "none", simple=False)["metrics"]
        if auto_fix(m, "dark") == "plate" and auto_fix(m, "light") == "none":
            brand["theme_auto"] = "light"  # cores escuras são a marca: fundo claro sempre
        elif brand.get("theme_pref") in THEMES:
            brand["theme_auto"] = brand["theme_pref"]  # referências de estilo ou padrão da categoria
        else:
            brand["theme_auto"] = vis.get("theme") or suggest_theme(m, refs)
    theme = theme if theme in THEMES else brand["theme_auto"]
    bg = "light" if theme == "light" else "dark"
    lg = process_logo(data, fix, simple=vis.get("simple"), hint=vis.get("fix") if bg == "dark" else None, bg=bg)
    (pdir / "logo.png").write_bytes(lg["png"])
    svg = pdir / "logo.svg"
    svg.write_text(lg["svg"], encoding="utf-8") if lg["svg"] else svg.unlink(missing_ok=True)
    brand.update({"logo_w": lg["w"], "logo_h": lg["h"], "accent": lg["accent"], "recolored": lg["recolored"],
                  "fix": lg["fix"], "svg": bool(lg["svg"]), "theme": theme,
                  "palette": brand_palette(lg["rgb"], lg["alpha"], refs, lg["accent"],
                                           (brand.get("style_palette") or []) + (vis.get("palette") or []))})


async def _setup_brand(pdir: Path, brand: dict, logo_bytes: bytes, ref_bytes: list[bytes],
                       fix: str | None = None, theme: str | None = None) -> None:
    """Guarda o logo original, pede a opinião da IA de visão e prepara o logo para o fundo do vídeo."""
    process_logo(logo_bytes, simple=False)  # valida antes de gastar a chamada de visão
    (pdir / "logo_src.png").write_bytes(logo_bytes)
    vis = await llm.analyze_brand(preview_jpg(logo_bytes), ref_bytes)
    if vis:
        brand["vision"] = vis
        log.info("IA de visão sobre o logo: %s", vis)
    await asyncio.to_thread(_apply_logo, pdir, brand, fix, theme)


def _public(project: dict) -> dict:
    pdir = config.PROJECTS_DIR / project["id"]
    return {k: project[k] for k in ("id", "brand", "options", "reveal", "seed", "answers", "style", "story", "duration", "pack", "plan", "brief", "created", "updated", "has_audio", "dna")
            if k in project} | {
        "refs": [{"key": r["key"], "name": r["name"], "credit": r.get("credit"), "role": r.get("role", "asset"),
                  "titulo": r.get("titulo"), "tipo": r.get("tipo")} for r in project.get("refs", [])],
        "narrated": bool(project.get("voice")),
        "videos": [ext for ext in VIDEO_TYPES if (pdir / f"video.{ext}").exists()]}


def _n_scenes(duration: str, pitch: str) -> int:
    if duration != "auto":
        return max(3, min(9, round((float(duration) - 8) / 5.2)))
    return max(4, min(9, round(len(pitch.split()) / 45) + 3))


def _extras(opt: dict, n_scenes: int) -> dict:
    """Seções extras do prompt: narração (com orçamento de palavras pela duração) e fotos de banco."""
    ex = {"narration": bool(opt.get("narration")) and voice.enabled(), "stock": stock.images_enabled()}
    if ex["narration"] and opt.get("duration", "auto") != "auto":
        per_scene = (float(opt["duration"]) - 8.4) / max(n_scenes, 1)
        w = max(6, round((per_scene - 1.1) * 2.5))
        ex["words"] = f"{max(4, w - 3)} a {w + 2}"
    return ex


def _usable_keys(project: dict) -> list[str]:
    """Imagens que podem aparecer no vídeo (fotos do cliente e do banco). Referências de estilo não entram."""
    return [r["key"] for r in project.get("refs", []) if r.get("role", "asset") != "style"]


def _asset_catalog(project: dict) -> list[str]:
    out = []
    for r in project.get("refs", []):
        if r.get("role", "asset") == "style":
            continue
        if r.get("query"):
            out.append(f'{r["key"]}: foto de banco "{r["query"]}"')
            continue
        bits = [r.get("titulo") or r.get("name", "")]
        if r.get("tipo"):
            bits.append(f'tipo {r["tipo"]}')
        if r.get("descricao"):
            bits.append(r["descricao"])
        if r.get("uso"):
            bits.append({"fundo": "ótima como foto de fundo", "cartao": "melhor num cartão/moldura", "ambos": "serve de fundo ou cartão"}[r["uso"]])
        out.append(f'{r["key"]}: ' + " · ".join(b for b in bits if b))
    return out


def _dna(project: dict) -> dict:
    """Receita do filme sorteada pela semente (ângulo criativo + personalidade do movimento), filtrada pelo contexto."""
    opt = project["options"]
    project["dna"] = seeds.film_dna(project["seed"], project.get("pack", "geral"), project.get("style") or {},
                                    opt.get("font"), opt.get("skin"))
    return project["dna"]


def _director_brief(project: dict) -> dict:
    return {"name": project["brand"].get("name"), "style_brief": project.get("style") or {}}


async def _direct(project: dict, only: int | None = None) -> None:
    """Etapa 3: o diretor de cena pensa o motion de cada cena (ou só da cena `only`)."""
    opt = project["options"]
    dna = project.get("dna") or _dna(project)
    await llm.direct_scenes(project["story"]["scenes"], _director_brief(project), project.get("plan"), dna,
                            int(project["seed"]), opt.get("model"), project["brand"].get("theme") or "dark",
                            opt.get("format", "landscape"), only=only)


def _ensure_motion(project: dict) -> None:
    """Projetos antigos (sem motion por cena) ganham o sorteio pela semente, sem chamar a IA."""
    scenes = (project.get("story") or {}).get("scenes") or []
    missing = [i for i, sc in enumerate(scenes) if not sc.get("motion") and (sc.get("ui") or {}).get("type") != "big_word"]
    if not missing:
        return
    project.setdefault("seed", random.randint(1, 999999))
    dna = project.get("dna") or _dna(project)
    light = project["brand"].get("theme") == "light"
    for i in missing:
        ctx = seeds.scene_ctx(scenes, i, light=light)
        legacy = {"text_fx": scenes[i]["text_fx"]} if scenes[i].get("text_fx") else {}
        scenes[i]["ideas"] = seeds.idea_seeds(dna, seeds.scene_seed(project["seed"], i), ctx)
        scenes[i]["motion"] = seeds.harmonize({**seeds.choose(scenes[i], project["seed"], i, dna, ctx), **legacy}, ctx)


async def _write_story(pdir: Path, project: dict) -> None:
    """Pede o roteiro à IA, baixa fotos de banco pedidas, normaliza e dirige cada cena."""
    opt, brief = project["options"], dict(project["brief"])
    b = project["brand"]
    brief["logo"] = (("vetorizado (pode usar draw)" if b.get("svg") else "em imagem, NÃO use draw")
                     + f"; cores da marca: {', '.join(b.get('palette') or [])}")
    pk = load_packs().get(project.get("pack", "geral"), {})
    qs = {q["id"]: q["label"] for q in (pk.get("onboarding") or {}).get("questions", [])}
    brief["answers"] = [f"{qs.get(k, k)}: {v}" for k, v in (project.get("answers") or {}).items() if str(v).strip()]
    brief["assets"] = _asset_catalog(project)
    brief["style_brief"] = project.get("style") or {}
    brief["photo_hint"] = (pk.get("onboarding") or {}).get("photo_hint", "")
    seed = project.setdefault("seed", random.randint(1, 999999))
    dna = _dna(project)
    brief["angle"] = dna["angle"]
    brief["dna"] = dna
    brief["seed"] = seed
    n = _n_scenes(opt["duration"], brief["pitch"])
    keys = _usable_keys(project)
    try:
        raw = await llm.write_story(brief, project.get("ref_desc", ""), keys, n, project.get("pack", "geral"),
                                    opt.get("model"), _extras(opt, n) | {"refs": keys})
        await stock.fetch_stock(pdir, project, raw)
        project["story"] = normalize_story(raw, _usable_keys(project))
        project["plan"] = raw.get("_plan")
        await _direct(project)
    except llm.LLMError as e:
        raise HTTPException(503, str(e))
    except ValueError as e:
        raise HTTPException(502, f"Roteiro inválido: {e}")


def _local_only(request: Request) -> None:
    if request.client and request.client.host not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(403, "Configurações só podem ser alteradas no próprio computador.")


@app.get("/", response_class=HTMLResponse)
def index():
    return (config.STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/api/config")
async def get_config():
    models, ok = await llm.list_models()
    provider = "9router" if config.LLM_BACKEND in ("9router", "openai") else config.LLM_BACKEND
    return {"backend": config.LLM_BACKEND, "provider": provider, "connected": ok, "ollama": ok,
            "models": models, "default_model": config.MOTION_MODEL,
            "vision_model": config.VISION_MODEL, "fonts": list(config.FONTS), "two_stage": config.TWO_STAGE,
            "packs": [{"id": p["id"], "name": p["name"], "description": p["description"]} for p in load_packs().values()],
            "categories": categories(),
            "formats": {k: v["label"] for k, v in config.FORMATS.items()},
            "narration": voice.enabled(), "tts": {"eleven": voice.eleven_enabled(), "kitten": kitten.available(), "default": voice.default_engine()},
            "stock": stock.images_enabled(),
            "music": [p.name for p in audio.library("music")]}


# ---------- configurações (chaves de API) ----------

@app.get("/api/settings")
def get_settings():
    """Nunca devolve as chaves, só se estão preenchidas."""
    return {k: {"set": bool(getattr(config, k)), "value": getattr(config, k) if not k.endswith("_KEY") else ""}
            for k in config.EDITABLE_KEYS}


@app.put("/api/settings")
def put_settings(request: Request, values: dict[str, str]):
    _local_only(request)
    upd = {k: str(v).strip() for k, v in values.items() if k in config.EDITABLE_KEYS and v is not None}
    if any("\n" in v for v in upd.values()):
        raise HTTPException(400, "Valor inválido.")
    if upd:
        config.save_env(upd)
    return get_settings()


@app.get("/api/voices")
async def get_voices():
    """Vozes da ElevenLabs, nativas da KittenTTS e clonadas, com o estado de cada motor."""
    try:
        dflt = await voice.default_voice() if voice.enabled() else ""
    except voice.VoiceError:
        dflt = ""
    return {"voices": await voice.list_voices(), "default": dflt, "eleven_default": config.ELEVENLABS_VOICE_ID,
            "engines": {"eleven": voice.eleven_enabled(), "kitten": kitten.available(), "default": voice.default_engine()},
            "kitten": kitten.status() if kitten.available() else None, "clones": voice.list_clones()}


@app.post("/api/voices/clone")
async def clone_voice(request: Request, name: str = Form("Minha voz"), text: str = Form(""), file: UploadFile = File(...)):
    """Grava uma voz clonada a partir de uma gravação do navegador ou de um arquivo enviado (5 a 30s de uma pessoa só)."""
    _local_only(request)
    if not kitten.available():
        raise HTTPException(400, "A clonagem usa a KittenTTS: instale com pip install kittenml.")
    data = await file.read()
    if len(data) > 30 * 1024 * 1024:
        raise HTTPException(400, "Arquivo grande demais (máximo 30 MB).")
    try:
        c = await asyncio.to_thread(voice.save_clone, name, data, text)
    except voice.VoiceError as e:
        raise HTTPException(400, str(e))
    kitten.warm()
    return c


@app.delete("/api/voices/clone/{cid}")
def delete_clone(request: Request, cid: str):
    _local_only(request)
    try:
        voice.delete_clone(cid)
    except voice.VoiceError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.get("/api/voices/clone/{cid}/audio")
def clone_audio(cid: str):
    try:
        return FileResponse(voice.clone_audio(cid), media_type="audio/wav")
    except voice.VoiceError as e:
        raise HTTPException(404, str(e))


class PreviewReq(BaseModel):
    voice: str = ""
    text: str = ""


PREVIEW_TEXT = "Olá! Esta é a voz que vai narrar o seu vídeo, do começo ao fim."


@app.post("/api/voices/preview")
async def preview_voice(req: PreviewReq):
    """Amostra curta da voz (em cache). Na KittenTTS em CPU leva de 20 a 60s na primeira vez."""
    text = re.sub(r"\s+", " ", req.text or PREVIEW_TEXT).strip()[:240]
    try:
        v = req.voice or await voice.default_voice()
        folder = config.VOICES_DIR / "_preview"
        folder.mkdir(exist_ok=True)
        out = await voice.speak(text, v, folder, seed=7)
    except voice.VoiceError as e:
        raise HTTPException(400, str(e))
    return FileResponse(out, media_type="audio/mpeg" if out.suffix == ".mp3" else "audio/wav")


# ---------- biblioteca de áudio (sfx/ e music/) ----------

@app.get("/api/library")
def get_library():
    roles = audio.sfx_roles()
    return {"music": [p.name for p in audio.library("music")],
            "sfx": [{"name": p.name, "role": next((r for r, fs in roles.items() if p in fs), None)} for p in audio.library("sfx")]}


@app.post("/api/library/{kind}")
async def upload_library(request: Request, kind: str, file: UploadFile = File(...)):
    _local_only(request)
    if kind not in ("sfx", "music"):
        raise HTTPException(404, "Biblioteca inválida.")
    name = Path(file.filename or "").name
    if not name or Path(name).suffix.lower() not in config.AUDIO_EXTS:
        raise HTTPException(400, "Envie um arquivo .mp3, .wav, .ogg, .m4a ou .flac.")
    folder = config.SFX_DIR if kind == "sfx" else config.MUSIC_DIR
    (folder / name).write_bytes(await file.read())
    return get_library()


@app.get("/api/library/{kind}/{name}")
def play_library(kind: str, name: str):
    folder = config.SFX_DIR if kind == "sfx" else config.MUSIC_DIR if kind == "music" else None
    p = (folder / Path(name).name) if folder else None
    if not p or not p.exists():
        raise HTTPException(404, "Arquivo não encontrado.")
    return FileResponse(p)


# ---------- projetos ----------

@app.get("/api/projects")
def list_projects():
    out = []
    for d in config.PROJECTS_DIR.iterdir():
        f = d / "project.json"
        if not f.exists():
            continue
        try:
            p = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        out.append({"id": p["id"], "name": p["brand"].get("name") or "(sem nome)",
                    "headline": (p.get("story", {}).get("scenes") or [{}])[0].get("headline", ""),
                    "created": p.get("created"), "updated": p.get("updated") or p.get("created"),
                    "duration": p.get("duration"), "format": p["options"].get("format"),
                    "scenes": len(p.get("story", {}).get("scenes", [])), "narrated": bool(p.get("voice")),
                    "videos": [ext for ext in VIDEO_TYPES if (d / f"video.{ext}").exists()]})
    return sorted(out, key=lambda x: x["updated"] or 0, reverse=True)


async def _read_images(files: list[UploadFile], limit: int) -> list[tuple[str, dict]]:
    out = []
    for f in [x for x in files if x and x.filename][:limit]:
        try:
            out.append((f.filename, process_ref(await f.read())))
        except Exception:
            continue
    return out


@app.post("/api/analyze/assets")
async def analyze_assets_ep(category: str = Form(""), files: list[UploadFile] = File(default=[])):
    imgs = await _read_images(files, 12)
    name = load_packs().get(category, {}).get("name", "")
    tags = await llm.analyze_assets([r["jpg"] for _, r in imgs], name)
    return {"items": [{"name": n, **(tags[i] if i < len(tags) else {})} for i, (n, _) in enumerate(imgs)]}


@app.post("/api/analyze/style")
async def analyze_style_ep(files: list[UploadFile] = File(default=[])):
    imgs = await _read_images(files, 5)
    return await llm.analyze_style([r["jpg"] for _, r in imgs])


@app.post("/api/projects")
async def create_project(
    pitch: str = Form(...), name: str = Form(""), tagline: str = Form(""), cta: str = Form(""),
    style_note: str = Form("", alias="style"), format: str = Form("landscape"), duration: str = Form("auto"),
    accent: str = Form(""), font: str = Form(""), progress: bool = Form(True), model: str = Form(""), pack: str = Form("auto"),
    narration: bool = Form(False), voice_id: str = Form(""), music: str = Form(""), sfx: bool = Form(True),
    logo_intro: str = Form(""), logo_outro: str = Form(""), logo_fix: str = Form("auto"),
    theme: str = Form("auto"), deco: str = Form(""), skin: str = Form(""),
    answers: str = Form("{}"), asset_info: str = Form("[]"), style_info: str = Form(""),
    logo: UploadFile | None = File(None), logo_from: str = Form(""),
    refs: list[UploadFile] = File(default=[]), assets: list[UploadFile] = File(default=[]),
):
    """refs = referências de ESTILO (não aparecem no vídeo); assets = fotos para usar nas cenas.
    logo_from = id de um projeto existente: reaproveita o logo original dele (projeto reaberto no formulário)."""
    if format not in config.FORMATS:
        raise HTTPException(400, "Formato inválido.")
    if duration != "auto" and duration not in ("15", "20", "30", "45", "60", "90"):
        raise HTTPException(400, "Duração inválida.")
    if len(pitch.strip()) < 20:
        raise HTTPException(400, "Escreva um pitch um pouco maior.")
    if logo is not None and logo.filename:
        logo_bytes = await logo.read()
    elif logo_from:
        src = _pdir(logo_from)
        logo_bytes = next((f.read_bytes() for f in (src / "logo_src.png", src / "logo.png") if f.exists()), b"")
    else:
        logo_bytes = b""
    if not logo_bytes:
        raise HTTPException(400, "Escolha o arquivo do logo.")
    pid = uuid.uuid4().hex[:12]
    pdir = config.PROJECTS_DIR / pid
    (pdir / "refs").mkdir(parents=True)
    category = pack if pack in load_packs() else None
    ref_list, style_bytes = [], []
    for i, (fname, rp) in enumerate(await _read_images(refs, 6), start=1):
        fn = f"sty{i}.jpg"
        (pdir / "refs" / fn).write_bytes(rp["jpg"])
        ref_list.append({"key": f"sty{i}", "file": fn, "name": fname, "w": rp["w"], "h": rp["h"], "role": "style"})
        style_bytes.append(rp["jpg"])
    asset_imgs = await _read_images(assets, 12)
    try:
        info = json.loads(asset_info or "[]")
    except ValueError:
        info = []
    if len(info) != len(asset_imgs):  # o onboarding não mandou a análise: a IA de visão faz agora
        pname = load_packs().get(category or "geral", {}).get("name", "")
        info = await llm.analyze_assets([r["jpg"] for _, r in asset_imgs], pname)
    for i, (fname, rp) in enumerate(asset_imgs, start=1):
        fn = f"img{i}.jpg"
        (pdir / "refs" / fn).write_bytes(rp["jpg"])
        tag = info[i - 1] if i - 1 < len(info) and isinstance(info[i - 1], dict) else {}
        ref_list.append({"key": f"img{i}", "file": fn, "name": fname, "w": rp["w"], "h": rp["h"], "role": "asset",
                         **{k: str(tag.get(k, ""))[:240] for k in ("tipo", "titulo", "descricao", "uso", "destaque") if tag.get(k)}})
    try:
        style = json.loads(style_info) if style_info else None
    except ValueError:
        style = None
    if style is None:
        style = await llm.analyze_style(style_bytes) if style_bytes else {}
    cat_style = load_packs().get(category or "geral", {}).get("style_defaults") or {}
    brand = {"name": name, "style_palette": style.get("palette") or [],
             "theme_pref": (theme if theme in THEMES else None) or style.get("theme") or cat_style.get("theme")}
    try:
        await _setup_brand(pdir, brand, logo_bytes, style_bytes, logo_fix if logo_fix in ("none", "invert", "plate") else None,
                           theme if theme in THEMES else None)
    except Exception as e:
        shutil.rmtree(pdir, ignore_errors=True)
        raise HTTPException(400, f"Não consegui processar o logo: {e}")

    try:
        ans = {str(k)[:40]: str(v)[:400] for k, v in json.loads(answers or "{}").items()}
    except (ValueError, AttributeError):
        ans = {}
    brief = {"name": name, "tagline": tagline, "style": style_note, "pitch": pitch}
    project = {
        "id": pid, "created": time.time(), "brief": brief, "answers": ans, "style": style, "seed": random.randint(1, 999999),
        "pack": choose_pack(f"{name} {style_note} {pitch} {' '.join(ans.values())}", category),
        "brand": brand,
        "options": {"format": format, "duration": duration, "accent": accent or None, "font": font or None,
                    "progress": progress, "tagline": tagline, "cta": cta, "model": model or None,
                    "narration": narration, "voice": voice_id or None, "music": music or None, "sfx": sfx,
                    "music_volume": 0.25, "sfx_volume": 0.6,
                    "logo_intro": logo_intro if logo_intro in REVEALS else None,
                    "logo_outro": logo_outro if logo_outro in REVEALS else None,
                    "logo_fix": logo_fix if logo_fix in ("none", "invert", "plate") else None,
                    "theme": theme if theme in THEMES else None, "deco": deco if deco in DECOS else None,
                    "skin": skin if skin in ("premium", "clean") else None},
        "refs": ref_list,
    }
    try:
        project["ref_desc"] = style.get("resumo", "")
        await _write_story(pdir, project)
    except HTTPException:
        shutil.rmtree(pdir, ignore_errors=True)  # não deixa projeto quebrado na lista
        raise
    return await _save_and_build(pdir, project)


class SeedReq(BaseModel):
    seed: int | None = None  # vazio = sorteia uma nova


def _set_seed(project: dict, req: SeedReq | None) -> None:
    s = req.seed if req and req.seed and req.seed > 0 else random.randint(1, 999999)
    project["seed"] = int(s) % 2147483646 or 1


@app.post("/api/projects/{pid}/regenerate")
async def regenerate(pid: str, req: SeedReq | None = None):
    """Novo roteiro com outra semente (ou a semente pedida): outro ângulo, outra receita, outros efeitos."""
    pdir, project = _pdir(pid), _load(pid)
    _set_seed(project, req)
    await _write_story(pdir, project)
    return await _save_and_build(pdir, project)


@app.post("/api/projects/{pid}/remotion")
async def remotion(pid: str, req: SeedReq | None = None):
    """Mesmo roteiro, motion novo: outra semente, outra receita, e o diretor pensa cada cena de novo."""
    pdir, project = _pdir(pid), _load(pid)
    _set_seed(project, req)
    _dna(project)
    for sc in project["story"]["scenes"]:
        for k in ("seed", "reroll", "ideas", "pick", "motion", "motion_locked"):
            sc.pop(k, None)
    try:
        await _direct(project)
    except llm.LLMError as e:
        raise HTTPException(503, str(e))
    return await _save_and_build(pdir, project)


def _scene(project: dict, i: int) -> dict:
    scenes = project["story"]["scenes"]
    if not 0 <= i < len(scenes):
        raise HTTPException(404, "Cena não encontrada.")
    if (scenes[i].get("ui") or {}).get("type") == "big_word":
        raise HTTPException(400, "A cena de palavra gigante tem animação própria.")
    return scenes[i]


@app.post("/api/projects/{pid}/scenes/{i}/reroll")
async def reroll_scene(pid: str, i: int):
    """Sorteia de novo só esta cena: passa pelas ideias do diretor e depois inventa novas pela semente. Sem IA."""
    pdir, project = _pdir(pid), _load(pid)
    sc = _scene(project, i)
    dna = project.get("dna") or _dna(project)
    sc["reroll"] = int(sc.get("reroll") or 0) + 1
    sc["seed"] = seeds.scene_seed(project["seed"], i, sc["reroll"])
    sc.pop("motion_locked", None)
    ctx = seeds.scene_ctx(project["story"]["scenes"], i, light=project["brand"].get("theme") == "light")
    m = seeds.choose(sc, project["seed"], i, dna, ctx)
    prev = ctx["prev"]
    if m == sc.get("motion") or (prev and m.get("text_fx") == prev.get("text_fx")):  # garante mudança visível
        m = seeds.fallback_motion(dna, seeds.derive(sc["seed"], "again"), ctx)
    sc["motion"] = m
    return await _save_and_build(pdir, project)


@app.post("/api/projects/{pid}/scenes/{i}/redirect")
async def redirect_scene(pid: str, i: int):
    """O diretor de cena (IA) pensa só esta cena de novo, com 3 ideias novas."""
    pdir, project = _pdir(pid), _load(pid)
    sc = _scene(project, i)
    sc["reroll"] = int(sc.get("reroll") or 0) + 1
    try:
        await _direct(project, only=i)
    except llm.LLMError as e:
        raise HTTPException(503, str(e))
    return await _save_and_build(pdir, project)


@app.get("/api/projects/{pid}")
def get_project(pid: str):
    return _public(_load(pid))


@app.delete("/api/projects/{pid}")
def delete_project(pid: str):
    shutil.rmtree(_pdir(pid))
    return {"ok": True}


@app.get("/api/projects/{pid}/logo")
def get_logo(pid: str):
    return FileResponse(_pdir(pid) / "logo.png", media_type="image/png")


@app.put("/api/projects/{pid}/story")
async def put_story(pid: str, story: dict):
    pdir, project = _pdir(pid), _load(pid)
    await stock.fetch_stock(pdir, project, story)  # o usuário pode pedir foto escrevendo "stock" no JSON
    try:
        project["story"] = normalize_story(story, [r["key"] for r in project.get("refs", [])])
    except ValueError as e:
        raise HTTPException(400, str(e))
    return await _save_and_build(pdir, project)


class Options(BaseModel):
    format: str | None = None
    duration: str | None = None
    accent: str | None = None
    font: str | None = None
    progress: bool | None = None
    tagline: str | None = None
    cta: str | None = None
    narration: bool | None = None
    voice: str | None = None
    music: str | None = None
    music_volume: float | None = None
    sfx: bool | None = None
    sfx_volume: float | None = None
    logo_intro: str | None = None
    logo_outro: str | None = None
    logo_fix: str | None = None
    theme: str | None = None
    deco: str | None = None
    skin: str | None = None


@app.patch("/api/projects/{pid}/options")
async def patch_options(pid: str, opts: Options):
    pdir, project = _pdir(pid), _load(pid)
    upd = opts.model_dump(exclude_unset=True)
    if "format" in upd and upd["format"] not in config.FORMATS:
        raise HTTPException(400, "Formato inválido.")
    if upd.get("font") and upd["font"] not in config.FONTS:
        raise HTTPException(400, "Fonte inválida.")
    for k in ("music_volume", "sfx_volume"):
        if upd.get(k) is not None:
            upd[k] = max(0.0, min(1.0, upd[k]))
    for k in ("accent", "font", "voice", "music"):
        if k in upd and not upd[k]:
            upd[k] = None
    if "logo_fix" in upd and upd["logo_fix"] not in ("none", "invert", "plate"):
        upd["logo_fix"] = None
    if "theme" in upd and upd["theme"] not in THEMES:
        upd["theme"] = None
    if "skin" in upd and upd["skin"] not in ("premium", "clean"):
        upd["skin"] = None
    if "deco" in upd and upd["deco"] not in DECOS:
        upd["deco"] = None
    if "logo_fix" in upd or "theme" in upd:
        o = project["options"] | upd
        await asyncio.to_thread(_apply_logo, pdir, project["brand"], o.get("logo_fix"), o.get("theme"))
    for k in ("logo_intro", "logo_outro"):
        if k in upd and upd[k] not in REVEALS:
            upd[k] = None
    project["options"].update(upd)
    return await _save_and_build(pdir, project)


@app.get("/p/{pid}", response_class=HTMLResponse)
def preview(pid: str):
    return (_pdir(pid) / "motion.html").read_text(encoding="utf-8")


@app.get("/api/projects/{pid}/html")
def download_html(pid: str):
    p = _pdir(pid)
    return FileResponse(p / "motion.html", filename=f"motion-{pid}.html", media_type="text/html")


@app.get("/api/projects/{pid}/export")
def export_project(pid: str):
    """Projeto inteiro (roteiro, logo, referências, falas) num .zip para guardar ou levar a outro computador."""
    pdir = _pdir(pid)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in pdir.rglob("*"):
            if f.is_file() and f.suffix not in (".mp4", ".webm") and ".part." not in f.name:
                z.write(f, f.relative_to(pdir).as_posix())
    name = "".join(ch for ch in (_load(pid)["brand"].get("name") or "projeto") if ch.isalnum()) or "projeto"
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="motion-{name}-{pid}.zip"'})


@app.post("/api/projects/import")
async def import_project(file: UploadFile = File(...)):
    try:
        z = zipfile.ZipFile(io.BytesIO(await file.read()))
        project = json.loads(z.read("project.json").decode("utf-8"))
    except (zipfile.BadZipFile, KeyError, ValueError):
        raise HTTPException(400, "Arquivo inválido: envie um .zip exportado pelo Motion Studio.")
    pid = uuid.uuid4().hex[:12]  # id novo: nunca sobrescreve um projeto existente
    pdir = config.PROJECTS_DIR / pid
    pdir.mkdir(parents=True)
    for info in z.infolist():
        target = (pdir / info.filename).resolve()
        if info.is_dir() or not target.is_relative_to(pdir.resolve()):
            continue  # ignora caminhos que tentam sair da pasta do projeto
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(z.read(info))
    if not (pdir / "logo.png").exists() or "story" not in project:
        shutil.rmtree(pdir, ignore_errors=True)
        raise HTTPException(400, "O .zip não tem logo ou roteiro.")
    project["id"] = pid
    return await _save_and_build(pdir, project)


class RenderReq(BaseModel):
    fps: int = 30
    format: str = "mp4"


@app.post("/api/projects/{pid}/render")
def start_render(pid: str, req: RenderReq):
    pdir, project = _pdir(pid), _load(pid)
    if req.fps not in (24, 30, 60):
        raise HTTPException(400, "FPS deve ser 24, 30 ou 60.")
    if req.format not in VIDEO_TYPES:
        raise HTTPException(400, "Formato deve ser mp4 ou webm.")
    for j in JOBS.values():
        if j["pid"] == pid and j["status"] == "running":
            return j
    try:
        config.ffmpeg_exe()
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    fmt = config.FORMATS[project["options"]["format"]]
    jid = uuid.uuid4().hex[:10]
    job = JOBS[jid] = {"id": jid, "pid": pid, "status": "running", "done": 0, "total": 0, "error": None, "format": req.format}

    def work():
        try:
            mix = pdir / "audio" / "mix.mp3"
            render_video(pdir / "motion.html", pdir / f"video.{req.format}", fmt["w"], fmt["h"], project["duration"], req.fps,
                         lambda d, t: job.update(done=d, total=t), audio=mix if mix.exists() else None)
            job["status"] = "done"
        except Exception as e:
            log.exception("Render falhou")
            job.update(status="error", error=str(e))

    threading.Thread(target=work, daemon=True).start()
    return job


@app.get("/api/jobs/{jid}")
def get_job(jid: str):
    if jid not in JOBS:
        raise HTTPException(404, "Job não encontrado.")
    return JOBS[jid]


@app.get("/api/projects/{pid}/video")
def get_video(pid: str, fmt: str = "mp4"):
    if fmt not in VIDEO_TYPES:
        raise HTTPException(400, "Formato deve ser mp4 ou webm.")
    p = _pdir(pid) / f"video.{fmt}"
    if not p.exists():
        raise HTTPException(404, "Vídeo ainda não renderizado.")
    name = "".join(ch for ch in (_load(pid)["brand"].get("name") or "motion") if ch.isalnum()) or "motion"
    return FileResponse(p, filename=f"{name}-{pid}.{fmt}", media_type=VIDEO_TYPES[fmt])
