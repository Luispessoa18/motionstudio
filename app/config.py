import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_local_env() -> None:
    """Carrega .env local sem sobrescrever variáveis definidas pelo processo."""
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if value[:1] == value[-1:] and value[:1] in ("'", '"'):
            value = value[1:-1]
        os.environ.setdefault(key, value)


_load_local_env()

RUNTIME_DIR = BASE_DIR / "runtime"
STATIC_DIR = BASE_DIR / "static"
EXAMPLES_DIR = BASE_DIR / "examples"
PROJECTS_DIR = Path(os.getenv("MOTION_PROJECTS_DIR", BASE_DIR / "projects"))
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
# Provedor OpenAI-compatible (9router). A URL deve terminar em /v1.
NINEROUTER_URL = os.getenv("NINEROUTER_URL", os.getenv("OPENAI_BASE_URL", "http://localhost:20128/v1")).rstrip("/")
NINEROUTER_API_KEY = os.getenv("NINEROUTER_API_KEY", os.getenv("OPENAI_API_KEY", ""))
# Modelo de texto que escreve o roteiro (JSON). qwen2.5:14b é o equilíbrio recomendado; qwen2.5:7b roda em GPUs menores.
MOTION_MODEL = os.getenv("MOTION_MODEL", "qwen2.5:14b")
MAX_TOKENS = int(os.getenv("MOTION_MAX_TOKENS", "16000"))  # roteiros detalhados são longos
# Modelo de visão opcional, usado só para descrever as imagens de referência. Deixe vazio para desligar.
VISION_MODEL = os.getenv("VISION_MODEL", "qwen2.5vl:7b")
# "ollama" (padrão), "9router"/"openai" ou "mock" (usa examples/demo.story.json).
LLM_BACKEND = os.getenv("MOTION_LLM", "ollama")
LLM_TIMEOUT = float(os.getenv("MOTION_LLM_TIMEOUT", "300"))
NUM_CTX = int(os.getenv("MOTION_NUM_CTX", "12288"))
REASONING_EFFORT = os.getenv("MOTION_REASONING_EFFORT", "high")
# Duas etapas: primeiro um plano de direção (batidas + visuais), depois o roteiro. Desligue com MOTION_TWO_STAGE=0.
TWO_STAGE = os.getenv("MOTION_TWO_STAGE", "1") != "0"
# Etapa 3, diretor de cena: "per_scene" (uma chamada por cena, mais elaborado), "batch" (uma chamada para
# todas) ou "off" (só o sorteio pela semente, sem IA).
SCENE_DIRECTOR = os.getenv("MOTION_SCENE_DIRECTOR", "per_scene").strip().lower()

# Narração (ElevenLabs). Sem chave, a narração fica desligada.
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")
ELEVENLABS_MODEL = os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2")
ELEVENLABS_ENABLED = os.getenv("ELEVENLABS_ENABLED", "1")  # "0" desliga a ElevenLabs sem apagar a chave
# Narração local com KittenTTS (pip install kittenml): vozes nativas e vozes clonadas, sem chave.
# TTS_ENGINE: motor padrão quando o projeto não escolheu voz ("auto" = KittenTTS se instalada, senão ElevenLabs).
TTS_ENGINE = os.getenv("TTS_ENGINE", "kitten")
KITTEN_ENABLED = os.getenv("KITTEN_ENABLED", "1") != "0"
KITTEN_MODEL = os.getenv("KITTEN_MODEL", "KittenML/kitten-tts-2")
KITTEN_PYTHON = os.getenv("KITTEN_PYTHON", "")  # Python que tem o kittenml; vazio = procura sozinho
KITTEN_VOICE = os.getenv("KITTEN_VOICE", "")    # voz nativa padrão; vazio = a padrão do modelo
KITTEN_PRESET = os.getenv("KITTEN_PRESET", "")  # "stable" (padrão do modelo) ou "expressive"
KITTEN_LOAD_TIMEOUT = float(os.getenv("KITTEN_LOAD_TIMEOUT", "1800"))  # 1ª vez baixa ~1 GB
VOICES_DIR = Path(os.getenv("MOTION_VOICES_DIR", BASE_DIR / "voices"))  # vozes clonadas (wav + json)
VOICES_DIR.mkdir(parents=True, exist_ok=True)
# Bancos de imagem. Basta uma das chaves; o Pexels é tentado primeiro.
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")

# Bibliotecas de áudio locais: coloque .mp3/.wav nessas pastas.
SFX_DIR = Path(os.getenv("MOTION_SFX_DIR", BASE_DIR / "sfx"))
MUSIC_DIR = Path(os.getenv("MOTION_MUSIC_DIR", BASE_DIR / "music"))
SFX_DIR.mkdir(parents=True, exist_ok=True)
MUSIC_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_EXTS = (".mp3", ".wav", ".ogg", ".m4a", ".flac")

# Chaves que a tela de configurações pode gravar no .env.
EDITABLE_KEYS = ("ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID", "ELEVENLABS_MODEL", "PEXELS_API_KEY", "PIXABAY_API_KEY",
                 "TTS_ENGINE", "KITTEN_VOICE", "KITTEN_PRESET", "ELEVENLABS_ENABLED")


def save_env(updates: dict) -> None:
    """Grava as chaves no .env (preservando o resto do arquivo) e aplica no processo atual."""
    env_file = BASE_DIR / ".env"
    lines = env_file.read_text(encoding="utf-8").splitlines() if env_file.exists() else []
    pending = dict(updates)
    for i, raw in enumerate(lines):
        key = raw.split("=", 1)[0].strip()
        if not raw.lstrip().startswith("#") and key in pending:
            lines[i] = f"{key}={pending.pop(key)}"
    lines += [f"{k}={v}" for k, v in pending.items()]
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for k, v in updates.items():
        os.environ[k] = v
        globals()[k] = v


def ffmpeg_exe() -> str:
    """ffmpeg do PATH ou o binário que vem com o pacote imageio-ffmpeg."""
    import shutil
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:
        raise RuntimeError("ffmpeg não encontrado. Rode: pip install imageio-ffmpeg") from e

FORMATS = {
    "landscape": {"w": 1920, "h": 1080, "label": "16:9 (1920×1080)"},
    "portrait": {"w": 1080, "h": 1920, "label": "9:16 (1080×1920)"},
}

# Presets de tipografia (Google Fonts). A IA escolhe uma chave; o usuário pode trocar na interface.
FONTS = {
    # weight: peso das headlines; light: peso das palavras finas no estilo premium (headline com pesos mistos)
    "grotesk": {"display": "Space Grotesk", "weight": "700", "light": "400", "stretch": "100%",
                 "css": "family=Space+Grotesk:wght@300..700"},
    "geometric": {"display": "Sora", "weight": "800", "light": "300", "stretch": "100%",
                   "css": "family=Sora:wght@300..800"},
    "wide": {"display": "Archivo", "weight": "800", "light": "400", "stretch": "112%",
              "css": "family=Archivo:wdth,wght@62..125,300..900"},
    "clean": {"display": "Inter Tight", "weight": "700", "light": "300", "stretch": "100%",
               "css": "family=Inter+Tight:wght@300..800"},
    "tech": {"display": "Unbounded", "weight": "700", "light": "300", "stretch": "100%",
              "css": "family=Unbounded:wght@300..700"},
    "elegant": {"display": "Fraunces", "weight": "700", "light": "400", "stretch": "100%",
                 "body": {"name": "Inter Tight", "css": "family=Inter+Tight:wght@400;500;600"},
                 "css": "family=Fraunces:opsz,wght@9..144,300..800"},
    "luxury": {"display": "Cormorant Garamond", "weight": "700", "light": "500", "stretch": "100%",
                "body": {"name": "Montserrat", "css": "family=Montserrat:wght@400;500;600"},
                 "css": "family=Cormorant+Garamond:wght@400..700"},
    "soft": {"display": "Montserrat", "weight": "700", "light": "300", "stretch": "100%",
              "css": "family=Montserrat:wght@300..800"},
}
MONO_FONT = {"name": "JetBrains Mono", "css": "family=JetBrains+Mono:wght@400;600;800"}
