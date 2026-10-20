"""Narração: ElevenLabs (nuvem), KittenTTS (local, vozes nativas) ou voz clonada (KittenTTS a partir de uma gravação).

A voz do projeto é um id com prefixo:
  "<id da ElevenLabs>"   ElevenLabs
  "kitten:<Nome>"        voz nativa da KittenTTS (ex. kitten:Portuguese)
  "clone:<id>"           voz clonada guardada em voices/<id>.wav (+ .json com nome e transcrição)
Cada fala vira um arquivo em cache (mesmo texto + mesma voz = mesmo arquivo, sem gerar de novo).
"""
import asyncio
import hashlib
import json
import logging
import re
import subprocess
import time
import uuid
from pathlib import Path

import httpx

from . import config, kitten
from .audio import duration_of

log = logging.getLogger("motion.voice")
API = "https://api.elevenlabs.io/v1"

# vozes nativas da KittenTTS 2 (a lista real vem do modelo quando ele está carregado)
KITTEN_FALLBACK = ["Portuguese", "Bella", "Jasper", "Luna", "Bruno", "Rosie", "Hugo", "Kiki", "Leo", "Matthew", "Elliot",
                   "Willow", "Dolores", "Victor", "Dante", "Alfred", "Claire", "Raven", "Marcus", "Diana", "Grace", "Iris",
                   "Julian", "Eleanor", "Victoria", "Spanish", "French", "Italian", "German"]
CLONE_MIN_S, CLONE_MAX_S = 4.0, 30.0


class VoiceError(RuntimeError):
    pass


def eleven_enabled() -> bool:
    """Tem chave e não foi desligada em Configurações (ELEVENLABS_ENABLED=0)."""
    return bool(config.ELEVENLABS_API_KEY) and str(config.ELEVENLABS_ENABLED).strip().lower() not in ("0", "false", "off", "")


def enabled() -> bool:
    return eleven_enabled() or kitten.available()


def engine_of(voice: str | None) -> str:
    v = voice or ""
    return "kitten" if v.startswith("kitten:") else "clone" if v.startswith("clone:") else "eleven"


# ---------- vozes clonadas ----------

def _clone_paths(cid: str) -> tuple[Path, Path]:
    if not re.fullmatch(r"[a-f0-9]{8,16}", cid or ""):
        raise VoiceError("Voz clonada inválida.")
    return config.VOICES_DIR / f"{cid}.wav", config.VOICES_DIR / f"{cid}.json"


def list_clones() -> list[dict]:
    out = []
    for meta in sorted(config.VOICES_DIR.glob("*.json")):
        try:
            d = json.loads(meta.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if (config.VOICES_DIR / f"{meta.stem}.wav").exists():
            out.append({"id": f"clone:{meta.stem}", "cid": meta.stem, "name": d.get("name") or meta.stem,
                        "text": d.get("text") or "", "dur": d.get("dur"), "created": d.get("created")})
    return sorted(out, key=lambda c: c.get("created") or 0, reverse=True)


def save_clone(name: str, data: bytes, text: str = "") -> dict:
    """Converte a gravação (webm, mp3, wav, m4a...) para wav mono 24 kHz, com no máximo 30s, e guarda."""
    cid = uuid.uuid4().hex[:10]
    wav, meta = _clone_paths(cid)
    src = config.VOICES_DIR / f"{cid}.src"
    src.write_bytes(data)
    try:
        # tira o silêncio do começo e normaliza o volume: a referência limpa melhora a clonagem
        r = subprocess.run([config.ffmpeg_exe(), "-v", "error", "-y", "-i", str(src), "-t", str(CLONE_MAX_S + 5),
                            "-af", "silenceremove=start_periods=1:start_threshold=-45dB,loudnorm=I=-18:TP=-2",
                            "-ac", "1", "-ar", "24000", "-t", str(CLONE_MAX_S), str(wav)], capture_output=True)
        if r.returncode != 0 or not wav.exists():
            raise VoiceError(f"Não consegui ler o áudio: {r.stderr.decode(errors='ignore')[:200]}")
    finally:
        src.unlink(missing_ok=True)
    dur = duration_of(wav)
    if dur < CLONE_MIN_S:
        wav.unlink(missing_ok=True)
        raise VoiceError(f"A gravação tem {dur:.1f}s. Grave pelo menos {int(CLONE_MIN_S)}s (o ideal é 10 a 20s).")
    meta.write_text(json.dumps({"name": (name or "Minha voz").strip()[:40], "text": re.sub(r"\s+", " ", text or "").strip()[:600],
                                "dur": round(dur, 1), "created": time.time()}, ensure_ascii=False), encoding="utf-8")
    return next(c for c in list_clones() if c["cid"] == cid)


def delete_clone(cid: str) -> None:
    for p in _clone_paths(cid):
        p.unlink(missing_ok=True)


def clone_audio(cid: str) -> Path:
    wav, _ = _clone_paths(cid)
    if not wav.exists():
        raise VoiceError("Voz clonada não encontrada.")
    return wav


# ---------- listas e padrão ----------

async def _eleven_voices() -> list[dict]:
    if not eleven_enabled():
        return []
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{API}/voices", headers={"xi-api-key": config.ELEVENLABS_API_KEY})
            r.raise_for_status()
        voices = [{"id": v["voice_id"], "name": v.get("name", v["voice_id"]), "engine": "eleven",
                   "desc": ", ".join(str(x) for x in (v.get("labels") or {}).values() if x)}
                  for v in r.json().get("voices", [])]
        return sorted(voices, key=lambda v: v["name"].lower())
    except Exception as e:
        log.warning("Não consegui listar as vozes da ElevenLabs: %s", e)
        return []


def kitten_voices() -> list[dict]:
    if not kitten.available():
        return []
    kitten.warm()  # carrega o modelo em segundo plano; enquanto isso vale a lista conhecida
    names = kitten.status()["voices"] or KITTEN_FALLBACK
    names = sorted(names, key=lambda n: (n != "Portuguese", n))  # a voz em português primeiro
    return [{"id": f"kitten:{n}", "name": n, "engine": "kitten", "desc": "fala português" if n == "Portuguese" else ""} for n in names]


async def list_voices() -> list[dict]:
    clones = [{"id": c["id"], "name": c["name"], "engine": "clone", "desc": f"clonada · {c['dur']}s"} for c in list_clones()] \
        if kitten.available() else []
    return (await _eleven_voices()) + kitten_voices() + clones


def default_engine() -> str:
    eng = (config.TTS_ENGINE or "auto").lower()
    if eng in ("elevenlabs", "eleven") and eleven_enabled():
        return "eleven"
    # padrão: KittenTTS (local); a ElevenLabs só entra se for a única disponível
    return "kitten" if kitten.available() else "eleven" if eleven_enabled() else "none"


async def default_voice() -> str:
    eng = default_engine()
    if eng == "kitten":
        return f"kitten:{config.KITTEN_VOICE or 'Portuguese'}"
    if eng == "eleven":
        if config.ELEVENLABS_VOICE_ID:
            return config.ELEVENLABS_VOICE_ID
        voices = await _eleven_voices()
        if voices:
            return voices[0]["id"]
        raise VoiceError("Nenhuma voz disponível na ElevenLabs. Confira a chave da API.")
    raise VoiceError("Nenhum motor de voz disponível: configure a ElevenLabs ou instale a KittenTTS (pip install kittenml).")


# ---------- síntese ----------

async def _eleven_tts(client: httpx.AsyncClient, text: str, voice: str, prev: str, nxt: str, out: Path) -> None:
    if not eleven_enabled():
        raise VoiceError("A voz escolhida é da ElevenLabs, mas falta a chave da API (Configurações).")
    body = {"text": text, "model_id": config.ELEVENLABS_MODEL,
            "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.15, "use_speaker_boost": True}}
    # Contexto vizinho deixa a entonação contínua entre as cenas.
    if prev:
        body["previous_text"] = prev
    if nxt:
        body["next_text"] = nxt
    r = await client.post(f"{API}/text-to-speech/{voice}", params={"output_format": "mp3_44100_128"},
                          headers={"xi-api-key": config.ELEVENLABS_API_KEY}, json=body)
    if r.status_code >= 400:
        raise VoiceError(f"ElevenLabs respondeu {r.status_code}: {r.text[:300]}")
    out.write_bytes(r.content)


async def _kitten_tts(text: str, voice: str, out: Path, seed: int | None) -> None:
    if not kitten.available():
        raise VoiceError("A voz escolhida é da KittenTTS, mas o pacote não foi encontrado (pip install kittenml).")
    try:
        if voice.startswith("clone:"):
            cid = voice.split(":", 1)[1]
            meta = json.loads(_clone_paths(cid)[1].read_text(encoding="utf-8"))
            await asyncio.to_thread(kitten.synth, text, out, reference=clone_audio(cid),
                                    reference_text=meta.get("text") or None, seed=seed)
        else:
            await asyncio.to_thread(kitten.synth, text, out, voice=voice.split(":", 1)[1], seed=seed)
    except kitten.KittenError as e:
        raise VoiceError(f"KittenTTS: {e}") from e


def _cache_key(voice: str, text: str) -> str:
    eng = engine_of(voice)
    if eng == "eleven":
        parts = [voice, config.ELEVENLABS_MODEL, text]
    else:
        parts = [voice, config.KITTEN_MODEL, config.KITTEN_PRESET, text]
        if eng == "clone":  # regravar a voz invalida o cache
            wav = config.VOICES_DIR / f"{voice.split(':', 1)[1]}.wav"
            parts.append(str(int(wav.stat().st_mtime)) if wav.exists() else "")
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:16]


async def speak(text: str, voice: str, out_dir: Path, seed: int | None = None, prev: str = "", nxt: str = "") -> Path:
    """Gera (ou reaproveita) uma fala e devolve o arquivo."""
    eng = engine_of(voice)
    out = out_dir / f"voz_{_cache_key(voice, text)}.{'mp3' if eng == 'eleven' else 'wav'}"
    if not out.exists():
        tmp = out.with_name(out.stem + ".part" + out.suffix)  # arquivo parcial nunca vira cache
        if eng == "eleven":
            async with httpx.AsyncClient(timeout=120) as c:
                await _eleven_tts(c, text, voice, prev, nxt, tmp)
        else:
            await _kitten_tts(text, voice, tmp, seed)
        tmp.replace(out)
    return out


async def synthesize(pdir: Path, project: dict) -> None:
    """Gera (ou reaproveita) a fala de cada cena e grava arquivo + duração em project["voice"]."""
    opt, story = project["options"], project["story"]
    if not opt.get("narration") or not enabled():
        project.pop("voice", None)
        return
    voice = opt.get("voice") or await default_voice()
    if engine_of(voice) == "eleven" and not eleven_enabled():  # projeto antigo com voz da ElevenLabs desligada
        voice = await default_voice()
    lines = [s.get("narration", "") for s in story["scenes"]] + [story.get("outro_narration", "")]
    folder = pdir / "audio"
    folder.mkdir(exist_ok=True)
    seed = int(project.get("seed") or 7) % 2147483646
    clips = []
    for i, text in enumerate(lines):
        if not text:
            clips.append(None)
            continue
        prev = next((t for t in reversed(lines[:i]) if t), "")
        nxt = next((t for t in lines[i + 1:] if t), "")
        out = await speak(text, voice, folder, seed, prev, nxt)
        clips.append({"file": out.name, "dur": round(duration_of(out), 3)})
    used = {c["file"] for c in clips if c}
    for old in folder.glob("voz_*.*"):  # limpa falas que saíram do roteiro
        if old.name not in used:
            old.unlink(missing_ok=True)
    project["voice"] = {"voice": voice, "engine": engine_of(voice), "scenes": clips[:-1], "outro": clips[-1]}
