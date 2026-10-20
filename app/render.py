"""Renderiza o HTML para MP4 ou WebM quadro a quadro.

O Playwright posiciona a timeline em cada instante (seek) e tira um print; o ffmpeg codifica.
Para acelerar, o vídeo é dividido em trechos renderizados em paralelo (um Chromium por processo)
e depois concatenados sem recodificar.
"""
import multiprocessing as mp
import os
import subprocess
import tempfile
from pathlib import Path


from .config import ffmpeg_exe as _ffmpeg

VCODEC = {
    "mp4": ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p"],
    "webm": ["-c:v", "libvpx-vp9", "-crf", "30", "-b:v", "0", "-row-mt", "1", "-deadline", "good", "-cpu-used", "3",
             "-pix_fmt", "yuv420p"],
}
ACODEC = {"mp4": ["-c:a", "aac", "-b:a", "192k"], "webm": ["-c:a", "libopus", "-b:a", "160k"]}


def _worker(html_uri: str, seg_path: str, w: int, h: int, fps: int, start: int, end: int, counter, idx: int, container: str):
    from playwright.sync_api import sync_playwright
    cmd = [_ffmpeg(), "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg", "-i", "-",
           *VCODEC[container], seg_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        with sync_playwright() as pw:
            kw = {"args": ["--no-sandbox", "--disable-dev-shm-usage", "--force-color-profile=srgb", "--hide-scrollbars"]}
            if os.getenv("CHROMIUM_PATH"):
                kw["executable_path"] = os.getenv("CHROMIUM_PATH")
            browser = pw.chromium.launch(**kw)
            page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
            page.goto(html_uri, wait_until="load", timeout=60000)
            page.wait_for_function("window.__motion && window.__motion.ready", timeout=60000)
            for i in range(start, end):
                page.evaluate(f"window.__motion.seek({i / fps:.5f})")
                proc.stdin.write(page.screenshot(type="jpeg", quality=93))
                counter[idx] = i - start + 1
            browser.close()
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError("ffmpeg falhou")
    finally:
        if proc.poll() is None:
            proc.kill()


def render_video(html_path: Path, out_path: Path, w: int, h: int, duration: float, fps: int = 30, on_progress=None,
                 workers: int | None = None, audio: Path | None = None):
    """out_path termina em .mp4 ou .webm; audio (opcional) é a trilha mixada, multiplexada no final."""
    container = "webm" if out_path.suffix.lower() == ".webm" else "mp4"
    frames = int(round(duration * fps))
    workers = workers or int(os.getenv("MOTION_RENDER_WORKERS", "0")) or max(1, min(4, (os.cpu_count() or 2) // 2))
    workers = max(1, min(workers, frames // (fps * 2) or 1))
    uri = html_path.resolve().as_uri() + "?render=1"
    ctx = mp.get_context("spawn")
    counter = ctx.Array("i", workers)
    bounds = [round(frames * k / workers) for k in range(workers + 1)]
    with tempfile.TemporaryDirectory() as td:
        segs = [str(Path(td) / f"seg{k:02d}.{container}") for k in range(workers)]
        procs = [ctx.Process(target=_worker, args=(uri, segs[k], w, h, fps, bounds[k], bounds[k + 1], counter, k, container))
                 for k in range(workers)]
        for p in procs:
            p.start()
        while any(p.is_alive() for p in procs):
            for p in procs:
                p.join(timeout=1)
            if on_progress:
                on_progress(sum(counter[:]), frames)
        if any(p.exitcode != 0 for p in procs):
            raise RuntimeError("Um dos processos de render falhou. Veja o log do servidor.")
        lst = Path(td) / "list.txt"
        lst.write_text("".join(f"file '{Path(s).as_posix()}'\n" for s in segs))
        tmp = out_path.with_suffix(f".part.{container}")
        cmd = [_ffmpeg(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst)]
        if audio and audio.exists():
            cmd += ["-i", str(audio), "-map", "0:v", "-map", "1:a", "-c:v", "copy", *ACODEC[container], "-t", f"{duration:.3f}"]
        else:
            cmd += ["-c", "copy"]
        if container == "mp4":
            cmd += ["-movflags", "+faststart"]
        r = subprocess.run(cmd + [str(tmp)])
        if r.returncode != 0:
            raise RuntimeError("ffmpeg falhou ao juntar os trechos.")
        tmp.replace(out_path)
    if on_progress:
        on_progress(frames, frames)
