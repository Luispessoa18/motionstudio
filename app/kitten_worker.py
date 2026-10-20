"""Processo da KittenTTS: carrega o modelo uma vez e atende pedidos por linhas JSON (stdin -> stdout).

Roda no Python onde o pacote `kittenml` está instalado (pode ser outro, não o .venv do app), assim o torch
não precisa ser instalado duas vezes. Uso: python kitten_worker.py <modelo>

Pedidos:  {"id": 1, "op": "info"}
          {"id": 2, "op": "tts", "text": "...", "out": "x.wav", "voice": "Bruno" | "reference": "a.wav",
           "reference_text": "...", "seed": 7, "preset": "stable"}
Respostas: {"id": 1, "ok": true, ...} ou {"id": 1, "ok": false, "error": "..."}
"""
import json
import sys
import time


def main() -> None:
    model_name = sys.argv[1] if len(sys.argv) > 1 else "KittenML/kitten-tts-2"
    out = sys.stdout
    sys.stdout = sys.stderr  # qualquer print de biblioteca vai para o log, não para o protocolo

    def reply(obj):
        out.write(json.dumps(obj, ensure_ascii=False) + "\n")
        out.flush()

    t0 = time.time()
    try:
        from kittenml import KittenTTS
        import soundfile as sf
        m = KittenTTS(model_name)
    except Exception as e:  # o app mostra o erro e desliga a KittenTTS
        reply({"id": 0, "ok": False, "error": f"{type(e).__name__}: {e}"})
        return
    voices = list(getattr(m, "available_voices", []) or [])
    presets = list(getattr(m, "decode_presets", {}) or {})
    reply({"id": 0, "ok": True, "ready": True, "model": model_name, "voices": voices, "presets": presets,
           "sample_rate": m.sample_rate, "clone": hasattr(m, "_clone_reference"), "load_s": round(time.time() - t0, 1)})

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except ValueError:
            continue
        rid = req.get("id")
        try:
            if req.get("op") == "info":
                reply({"id": rid, "ok": True, "voices": voices, "presets": presets})
                continue
            if req.get("op") != "tts":
                raise ValueError(f"operação desconhecida: {req.get('op')}")
            kw = {"normalize": bool(req.get("normalize", False))}  # o roteiro já escreve números por extenso
            if req.get("reference"):
                kw["reference"] = req["reference"]
                if req.get("reference_text"):
                    kw["reference_text"] = req["reference_text"]
                else:
                    # sem transcrição: clona só pelo timbre (a transcrição automática da lib é forçada em inglês)
                    kw["reference_text"] = "."
                    kw["use_reference_prompt"] = False
            else:
                kw["voice"] = req.get("voice") or None
            if req.get("preset") and req["preset"] in presets:
                kw["preset"] = req["preset"]
            if req.get("seed") is not None:
                kw["advanced"] = {"seed": int(req["seed"])}
            t = time.time()
            audio = m.generate(req["text"], **kw)
            sf.write(req["out"], audio, m.sample_rate)
            reply({"id": rid, "ok": True, "out": req["out"], "dur": round(len(audio) / m.sample_rate, 3),
                   "gen_s": round(time.time() - t, 1)})
        except Exception as e:
            reply({"id": rid, "ok": False, "error": f"{type(e).__name__}: {e}"})


if __name__ == "__main__":
    main()
