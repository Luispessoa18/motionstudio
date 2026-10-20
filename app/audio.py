"""Trilha de áudio: narração + efeitos sincronizados com as animações + música com ducking.

Tudo é decodificado para PCM pelo ffmpeg, mixado com numpy e codificado num único mp3,
que vai embutido no HTML (preview) e é multiplexado no MP4/WebM.
"""
import logging
import re
import subprocess
from pathlib import Path

import numpy as np

from . import config

log = logging.getLogger("motion.audio")
SR = 44100

# Papel de cada efeito, deduzido pelo nome do arquivo em sfx/. Prefixe o nome (ex. "impact-boom.mp3") para forçar.
ROLES = {
    "intro": r"intro|cue|logo|tone|cinematic|reveal",
    "whoosh": r"whoo?sh|whoshe|swoosh|swish|woosh|transition|swipe",
    "impact": r"impact|hit|boom|bass|drop|slam|thud",
    "pop": r"pop|click|blip|tick|ui|bubble|ding",
}
# Se não houver arquivo para um papel, tenta o próximo da lista.
FALLBACK = {"impact": ["intro"], "pop": [], "intro": ["impact"], "whoosh": []}


def decode(path: Path) -> np.ndarray:
    """Arquivo de áudio -> array float32 (amostras, 2) a 44,1 kHz."""
    r = subprocess.run([config.ffmpeg_exe(), "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                       capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"Não consegui ler {path.name}: {r.stderr.decode(errors='ignore')[:200]}")
    return np.frombuffer(r.stdout, dtype=np.float32).reshape(-1, 2).copy()


def duration_of(path: Path) -> float:
    return len(decode(path)) / SR


def library(kind: str) -> list[Path]:
    folder = config.SFX_DIR if kind == "sfx" else config.MUSIC_DIR
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in config.AUDIO_EXTS)


def sfx_roles() -> dict[str, list[Path]]:
    found = {r: [] for r in ROLES}
    for p in library("sfx"):
        name = p.stem.lower()
        role = next((r for r in ROLES if name.startswith(r)), None) or next((r for r, rx in ROLES.items() if re.search(rx, name)), None)
        if role:
            found[role].append(p)
    for role, alts in FALLBACK.items():
        if not found[role]:
            found[role] = next((found[a] for a in alts if found[a]), [])
    return found


def cues(spec: dict) -> list[tuple[float, str, float]]:
    """(segundo, papel, ganho) acompanhando os tempos de entrada do runtime (motion.js)."""
    out = [(0.0, "intro", 0.8)]
    for sc in spec["scenes"]:
        t0, kind = sc["at"], sc["ui"]["type"]
        if kind == "big_word":
            out += [(t0 - 0.15, "whoosh", 0.7), (t0 + 0.7, "impact", 0.85)]
            continue
        tr = (sc.get("motion") or {}).get("transition")
        if tr in ("flash", "zoom", "match", "glitch"):  # transição de golpe: impacto no corte
            out += [(t0 - 0.2, "whoosh", 0.45), (t0 + 0.05, "impact", 0.7)]
        elif tr in ("fade", "iris"):
            out.append((t0 - 0.1, "whoosh", 0.3))
        elif tr != "cut":
            out.append((t0 - (0.15 if tr in ("wipe", "push", "slide", "spin", "blinds") else 0), "whoosh", 0.55))
        if (sc.get("motion") or {}).get("camera") == "shake":
            out.append((t0 + 0.5, "impact", 0.5))
        if kind != "none":
            out.append((t0 + 0.45, "pop", 0.45))
    oa = spec["outro"]["at"]
    out += [(oa + 0.45, "whoosh", 0.6), (oa + 2.15, "impact", 0.8)]
    return out


def _place(buf: np.ndarray, clip: np.ndarray, at: float, gain: float) -> None:
    i = max(0, int(at * SR))
    if i >= len(buf):
        return
    n = min(len(clip), len(buf) - i)
    buf[i:i + n] += clip[:n] * gain


def _fade(x: np.ndarray, fin: float, fout: float) -> np.ndarray:
    n = len(x)
    a, b = min(n, int(fin * SR)), min(n, int(fout * SR))
    if a:
        x[:a] *= np.linspace(0, 1, a, dtype=np.float32)[:, None]
    if b:
        x[n - b:] *= np.linspace(1, 0, b, dtype=np.float32)[:, None]
    return x


def _smooth(env: np.ndarray, sec: float) -> np.ndarray:
    k = max(1, int(sec * SR))
    return np.convolve(env, np.ones(k, dtype=np.float32) / k, mode="same")


def music_file(name: str | None) -> Path | None:
    tracks = library("music")
    if not name or not tracks:
        return None
    if name == "auto":
        return tracks[0]
    return next((p for p in tracks if p.name == name), None)


def mix(pdir: Path, project: dict, spec: dict) -> Path | None:
    """Monta audio/mix.mp3. Devolve None se não houver nada para tocar."""
    opt, voice = project["options"], project.get("voice") or {}
    total = spec["duration"]
    n = int(total * SR) + SR
    narr = np.zeros((n, 2), np.float32)
    fx = np.zeros((n, 2), np.float32)
    has = False

    for sc, clip in zip(spec["scenes"], voice.get("scenes") or []):
        if clip and (pdir / "audio" / clip["file"]).exists():
            _place(narr, decode(pdir / "audio" / clip["file"]), sc["at"] + sc.get("voice_at", 0.35), 1.0)
            has = True
    out = voice.get("outro")
    if out and (pdir / "audio" / out["file"]).exists():
        _place(narr, decode(pdir / "audio" / out["file"]), spec["outro"]["at"] + 0.6, 1.0)
        has = True

    if opt.get("sfx", True):
        roles, cache, used = sfx_roles(), {}, {}
        for at, role, gain in cues(spec):
            files = roles.get(role) or []
            if not files:
                continue
            f = files[used.get(role, 0) % len(files)]  # alterna entre arquivos do mesmo papel
            used[role] = used.get(role, 0) + 1
            if f not in cache:
                cache[f] = _fade(decode(f), 0.005, 0.08)
            _place(fx, cache[f], at, gain * float(opt.get("sfx_volume", 0.6)))
            has = True

    mpath = music_file(opt.get("music"))
    bed = np.zeros((n, 2), np.float32)
    if mpath:
        m = decode(mpath)
        if len(m):
            end = int(total * SR)
            reps = int(np.ceil(end / len(m)))
            bed[:end] = _fade(np.tile(m, (reps, 1))[:end].copy(), 1.5, 3.0)
            vol = float(opt.get("music_volume", 0.25))
            # Ducking: a música abaixa para ~35% enquanto o locutor fala.
            talk = _smooth((np.abs(narr).max(axis=1) > 0.01).astype(np.float32), 0.35)
            bed *= (vol * (1 - 0.65 * np.clip(talk * 1.5, 0, 1)))[:, None]
            has = True
    if not has:
        return None

    mixed = (narr + fx + bed)[: int(total * SR)]
    peak = float(np.abs(mixed).max() or 1)
    mixed *= min(3.0, 0.95 / peak)  # normaliza o pico (sobe trilhas baixas até 3x, nunca estoura)
    dest = pdir / "audio" / "mix.mp3"
    dest.parent.mkdir(exist_ok=True)
    r = subprocess.run([config.ffmpeg_exe(), "-y", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                        "-c:a", "libmp3lame", "-b:a", "160k", str(dest)], input=mixed.astype(np.float32).tobytes())
    if r.returncode != 0:
        raise RuntimeError("ffmpeg falhou ao gerar a trilha.")
    return dest
