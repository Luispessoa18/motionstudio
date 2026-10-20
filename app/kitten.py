"""KittenTTS local (https://github.com/KittenML/KittenTTS): vozes nativas e clonagem de voz, sem chave e sem internet
depois do primeiro download do modelo.

O modelo roda num processo separado (kitten_worker.py), no Python que tem o pacote `kittenml` instalado.
O processo fica vivo entre as falas para não recarregar o modelo a cada cena.
"""
import importlib.util
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import config

log = logging.getLogger("motion.kitten")
WORKER = Path(__file__).with_name("kitten_worker.py")


class KittenError(RuntimeError):
    pass


_lock = threading.Lock()          # um pedido por vez (o modelo não é thread-safe)
_start_lock = threading.Lock()
_proc: subprocess.Popen | None = None
_info: dict = {}
_state = {"status": "off", "error": "", "python": None}
_next_id = 1


def _has_kittenml(python: str) -> bool:
    try:
        r = subprocess.run([python, "-c", "import importlib.util,sys;sys.exit(0 if importlib.util.find_spec('kittenml') else 1)"],
                           capture_output=True, timeout=30)
        return r.returncode == 0
    except Exception:
        return False


def find_python() -> str | None:
    """KITTEN_PYTHON > este Python > outros Pythons do sistema (py -0p, PATH) que tenham o `kittenml`."""
    if _state["python"]:
        return _state["python"]
    found = None
    if config.KITTEN_PYTHON:
        found = config.KITTEN_PYTHON if _has_kittenml(config.KITTEN_PYTHON) else None
    elif importlib.util.find_spec("kittenml"):
        found = sys.executable
    else:
        cands = []
        if shutil.which("py"):
            try:
                out = subprocess.run(["py", "-0p"], capture_output=True, text=True, timeout=15).stdout
                cands += [ln.split()[-1] for ln in out.splitlines() if ln.strip().lower().endswith(".exe")]
            except Exception:
                pass
        cands += [p for p in (shutil.which("python3"), shutil.which("python")) if p]
        found = next((c for c in dict.fromkeys(cands) if c != sys.executable and _has_kittenml(c)), None)
    _state["python"] = found
    return found


def available() -> bool:
    """O pacote existe em algum Python desta máquina (não carrega o modelo)."""
    return config.KITTEN_ENABLED and bool(find_python())


def status() -> dict:
    return {"status": _state["status"], "error": _state["error"], "model": config.KITTEN_MODEL,
            "voices": _info.get("voices", []), "presets": _info.get("presets", []), "load_s": _info.get("load_s")}


def _read(proc: subprocess.Popen, want_id: int, timeout: float) -> dict:
    """Lê linhas até a resposta do pedido `want_id` (linhas que não são JSON são ignoradas)."""
    box: dict = {}

    def run():
        for line in proc.stdout:
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if msg.get("id") == want_id:
                box["msg"] = msg
                return

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(timeout)
    if "msg" not in box:
        if proc.poll() is not None:
            raise KittenError("O processo da KittenTTS terminou (veja o log do servidor).")
        raise KittenError(f"A KittenTTS não respondeu em {int(timeout)}s.")
    return box["msg"]


def _start() -> subprocess.Popen:
    global _proc, _info
    with _start_lock:
        if _proc and _proc.poll() is None:
            return _proc
        py = find_python()
        if not py:
            raise KittenError("KittenTTS não encontrada. Instale com: pip install kittenml (ou defina KITTEN_PYTHON).")
        _state.update(status="loading", error="")
        log.info("Iniciando KittenTTS (%s) com %s", config.KITTEN_MODEL, py)
        err_log = open(config.BASE_DIR / "kitten.log", "ab")
        # PYTHONUTF8: no Windows a lib abre o voices.json sem encoding e quebra em cp1252
        env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
        proc = subprocess.Popen([py, "-u", str(WORKER), config.KITTEN_MODEL], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=err_log, text=True, encoding="utf-8", bufsize=1, env=env,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            hello = _read(proc, 0, config.KITTEN_LOAD_TIMEOUT)  # 1ª vez inclui o download do modelo
        except KittenError as e:
            proc.kill()
            _state.update(status="error", error=str(e))
            raise
        if not hello.get("ok"):
            proc.kill()
            _state.update(status="error", error=hello.get("error", "falha ao carregar o modelo"))
            raise KittenError(f"KittenTTS não carregou: {_state['error']}")
        _info = hello
        _state.update(status="ready", error="")
        log.info("KittenTTS pronta em %ss · %d vozes", hello.get("load_s"), len(hello.get("voices") or []))
        _proc = proc
        return proc


def warm() -> None:
    """Carrega o modelo em segundo plano (para a lista de vozes aparecer sem travar a tela)."""
    if _state["status"] in ("loading", "ready") or not available():
        return
    threading.Thread(target=lambda: _safe(_start), daemon=True).start()


def _safe(fn):
    try:
        fn()
    except Exception as e:
        log.warning("KittenTTS: %s", e)


def voices() -> list[str]:
    _start()
    return list(_info.get("voices") or [])


def synth(text: str, out: Path, voice: str | None = None, reference: Path | None = None,
          reference_text: str | None = None, seed: int | None = None) -> float:
    """Gera a fala em `out` (.wav) e devolve a duração em segundos. Bloqueante: chame com asyncio.to_thread."""
    global _next_id
    with _lock:
        proc = _start()
        _next_id += 1
        rid = _next_id
        req = {"id": rid, "op": "tts", "text": text, "out": str(out), "seed": seed, "preset": config.KITTEN_PRESET or None}
        if reference:
            req.update(reference=str(reference), reference_text=reference_text or "")
        else:
            req["voice"] = voice
        t = time.time()
        try:
            proc.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
            proc.stdin.flush()
        except OSError as e:
            raise KittenError("O processo da KittenTTS caiu; tente de novo.") from e
        # CPU: ~ alguns segundos de processamento por segundo de fala; folga generosa para frases longas
        try:
            msg = _read(proc, rid, max(120.0, 25.0 * len(text.split())))
        except KittenError:
            proc.kill()  # resposta atrasada não pode cair no próximo pedido: recomeça do zero
            _state.update(status="off")
            raise
        if not msg.get("ok"):
            raise KittenError(msg.get("error") or "falha na síntese")
        log.info("KittenTTS: %.1fs de fala em %.1fs", msg.get("dur", 0), time.time() - t)
        return float(msg.get("dur") or 0)
