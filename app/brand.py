"""Processamento de marca: recorte do logo, transparência, contraste com o fundo preto, SVG e paleta de cores."""
import colorsys
import io
import logging
import re

import numpy as np
from PIL import Image, ImageOps

log = logging.getLogger("motion.brand")

# Como deixar o logo legível sobre o fundo preto do vídeo.
#   none   : já é legível
#   invert : partes pretas/cinza-escuras viram brancas (ex.: texto preto de logo pensado para papel)
#   plate  : as cores escuras SÃO a marca (ex.: azul-marinho); o logo aparece sobre um fundo claro
FIXES = ("none", "invert", "plate")
PLATE_BG = "#F4F3EF"


def _estimate_bg(rgb: np.ndarray) -> np.ndarray:
    h, w, _ = rgb.shape
    k = max(4, min(h, w) // 40)
    corners = np.concatenate([rgb[:k, :k].reshape(-1, 3), rgb[:k, -k:].reshape(-1, 3),
                              rgb[-k:, :k].reshape(-1, 3), rgb[-k:, -k:].reshape(-1, 3)])
    return np.median(corners, axis=0)


def _lum_sat(rgb: np.ndarray):
    mx, mn = rgb.max(-1), rgb.min(-1)
    sat = (mx - mn) / np.maximum(mx, 1)
    lum = (0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]) / 255
    return lum, sat, mx


def _cutout(data: bytes):
    """Remove o fundo (se não houver transparência) e recorta. Devolve rgb (float 0-255) e alpha (0-1)."""
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGBA")
    arr = np.asarray(img).astype(np.float32)
    rgb, alpha = arr[..., :3], arr[..., 3] / 255.0
    if alpha.min() > 0.98:  # sem transparência real: remove o fundo pela cor dos cantos
        bg = _estimate_bg(rgb)
        dist = np.sqrt(((rgb - bg) ** 2).sum(-1))
        alpha = np.clip((dist - 14) / 70, 0, 1)
        a3 = np.maximum(alpha[..., None], 1e-3)
        rgb = np.clip((rgb - bg * (1 - a3)) / a3, 0, 255)
        rgb = np.where(alpha[..., None] > 0.02, rgb, 255)
    ys, xs = np.where(alpha > 0.06)
    if len(xs) == 0:
        raise ValueError("Não encontrei o desenho do logo. Tente um PNG com fundo transparente.")
    pad = 6
    y0, y1 = max(0, ys.min() - pad), min(alpha.shape[0], ys.max() + pad + 1)
    x0, x1 = max(0, xs.min() - pad), min(alpha.shape[1], xs.max() + pad + 1)
    return rgb[y0:y1, x0:x1], alpha[y0:y1, x0:x1]


def contrast_metrics(rgb: np.ndarray, alpha: np.ndarray) -> dict:
    lum, sat, _ = _lum_sat(rgb)
    opaque = alpha > 0.5
    n = max(1, int(opaque.sum()))
    return {"dark_neutral": float((opaque & (sat < 0.25) & (lum < 0.45)).sum() / n),
            "dark_colored": float((opaque & (sat >= 0.25) & (lum < 0.3)).sum() / n),
            "light_neutral": float((opaque & (sat < 0.2) & (lum > 0.8)).sum() / n),
            "light_colored": float((opaque & (sat >= 0.2) & (lum > 0.72)).sum() / n)}


def auto_fix(m: dict, bg: str = "dark") -> str:
    """bg: "dark" (fundo preto ou cor escura da marca) ou "light" (fundo claro)."""
    if bg == "light":
        if m["light_colored"] > 0.35:
            return "plate"
        if m["light_neutral"] > 0.15:
            return "invert"
        return "none"
    if m["dark_colored"] > 0.35:
        return "plate"
    if m["dark_neutral"] > 0.15:
        return "invert"
    return "none"


def suggest_theme(m: dict, refs: list[bytes]) -> str:
    """Logo feito para papel (partes pretas ou cores escuras) ou artes claras pedem fundo claro."""
    light_refs = 0
    for data in refs[:6]:
        try:
            im = Image.open(io.BytesIO(data)).convert("L"); im.thumbnail((64, 64))
            light_refs += float(np.asarray(im).mean()) > 150
        except Exception:
            pass
    if refs and light_refs * 2 > len(refs[:6]):
        return "light"
    if auto_fix(m, "dark") != "none" and auto_fix(m, "light") == "none":
        return "light"
    return "dark"


def _invert_dark(rgb: np.ndarray) -> np.ndarray:
    lum, sat, _ = _lum_sat(rgb)
    k = np.clip((0.45 - lum) / 0.3, 0, 1)[..., None] * ((sat < 0.25)[..., None])
    return rgb * (1 - k) + 255 * k


def _invert_light(rgb: np.ndarray) -> np.ndarray:
    lum, sat, _ = _lum_sat(rgb)
    k = np.clip((lum - 0.55) / 0.3, 0, 1)[..., None] * ((sat < 0.2)[..., None])
    return rgb * (1 - k) + 22 * k


def _accent(rgb: np.ndarray, alpha: np.ndarray):
    """Matiz dominante entre os pixels saturados do logo."""
    lum, sat, mx = _lum_sat(rgb)
    opaque = alpha > 0.5
    sel = opaque & (sat > 0.4) & (mx > 90)
    if sel.sum() <= max(200, 0.01 * opaque.sum()):
        return None
    px = (rgb[sel] / 255)[:: max(1, int(sel.sum()) // 4000)]
    hues = np.array([colorsys.rgb_to_hsv(*p)[0] for p in px])
    hist, edges = np.histogram(hues, bins=24, range=(0, 1))
    b = hist.argmax()
    sub = px[(hues >= edges[b]) & (hues < edges[b + 1])]
    return _hex(np.median(sub, axis=0) * 255)


# ---------- vetorização ----------

def _kmeans(px: np.ndarray, k: int, it: int = 12):
    rng = np.random.default_rng(0)
    c = px[rng.choice(len(px), k, replace=False)].astype(np.float64)
    for _ in range(it):
        lab = ((px[:, None] - c[None]) ** 2).sum(-1).argmin(1)
        c = np.array([px[lab == i].mean(0) if (lab == i).any() else c[i] for i in range(k)])
    d = ((px[:, None] - c[None]) ** 2).sum(-1)
    return c, d.argmin(1), float(np.sqrt(d.min(1)).mean())


def _drop_mixes(c: np.ndarray, px: np.ndarray) -> np.ndarray:
    """Remove cores que são só a borda suavizada entre duas outras (ou entre uma cor e o fundo branco/preto),
    para o SVG não ganhar um contorno fantasma."""
    if len(c) < 3:
        return c
    share = np.bincount(((px[:, None] - c[None]) ** 2).sum(-1).argmin(1), minlength=len(c)) / len(px)
    anchors = list(c) + [np.array([255.0] * 3), np.array([0.0] * 3)]
    keep = []
    for i in range(len(c)):
        mix = False
        if share[i] < 0.25:
            for j in range(len(anchors)):
                for k in range(j + 1, len(anchors)):
                    if i in (j, k):
                        continue
                    a, b = anchors[j], anchors[k]
                    if min(np.sqrt(((c[i] - a) ** 2).sum()), np.sqrt(((c[i] - b) ** 2).sum())) < 45:
                        continue  # é praticamente uma das pontas (ex.: o preto do logo), não uma mistura
                    t = np.clip(np.dot(c[i] - a, b - a) / max(np.dot(b - a, b - a), 1e-6), 0.12, 0.88)
                    if np.sqrt(((a + t * (b - a) - c[i]) ** 2).sum()) < 22:
                        mix = True
        if not mix:
            keep.append(i)
    return c[keep] if keep else c


def vectorize(im: Image.Image, max_colors: int = 5, max_paths: int = 450) -> str | None:
    """Converte um logo simples (poucas cores chapadas) em SVG. Devolve None se o logo for complexo
    (foto, degradê) ou se o vtracer não estiver instalado."""
    try:
        import vtracer
    except ImportError:
        log.info("vtracer não instalado; logo segue só em PNG.")
        return None
    a = np.asarray(im.convert("RGBA")).astype(np.float32)
    rgb, al = a[..., :3], a[..., 3]
    m = al > 127
    if m.sum() < 50:
        return None
    px = rgb[m][:: max(1, int(m.sum()) // 20000)]
    best = None
    for k in range(1, max_colors + 1):
        if len(px) < k:
            break
        c, lab, err = _kmeans(px, k)
        d = np.sqrt(((px - c[lab]) ** 2).sum(-1))
        # média baixa = cores chapadas; mediana baixa com poucos pixels distantes = logo pequeno com muita borda suavizada
        if err < 18 or (np.median(d) < 14 and (d > 40).mean() < 0.2):
            best = c
            break
    if best is None:
        return None
    best = _drop_mixes(best, px)
    full = rgb[m]
    dist = ((full[:, None] - best[None]) ** 2).sum(-1)
    lab = dist.argmin(1)
    far = np.sqrt(dist.min(1)) > 90  # borda contra o fundo que não pertence a nenhuma cor: vira transparente
    out = np.zeros_like(a)
    out[m, :3] = best[lab]
    out[m, 3] = np.where(far, 0, 255)
    buf = io.BytesIO(); Image.fromarray(out.astype(np.uint8)).save(buf, "PNG")
    try:
        svg = vtracer.convert_raw_image_to_svg(
            buf.getvalue(), img_format="png", colormode="color", hierarchical="cutout", mode="spline",
            filter_speckle=8, color_precision=8, layer_difference=8, corner_threshold=60,
            length_threshold=4.0, splice_threshold=45, path_precision=2)
    except Exception as e:
        log.warning("Vetorização falhou: %s", e)
        return None
    if svg.count("<path") > max_paths:
        return None
    svg = re.sub(r"<\?xml[^>]*\?>|<!--.*?-->", "", svg, flags=re.S).strip()
    return svg.replace("<svg ", f'<svg viewBox="0 0 {im.width} {im.height}" ', 1)


# ---------- paleta ----------

def _hex(c) -> str:
    return "#%02X%02X%02X" % tuple(int(round(max(0, min(255, v)))) for v in c)


def _rgb(h: str) -> np.ndarray:
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float64)


def visible(h: str) -> str:
    """Garante que a cor aparece sobre preto (clareia cores muito escuras sem mudar o matiz)."""
    r, g, b = _rgb(h) / 255
    hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
    if ll < 0.42:
        ll = 0.42 + (0.42 - ll) * 0.3
    return _hex(np.array(colorsys.hls_to_rgb(hh, ll, ss)) * 255)


def _candidates(rgb: np.ndarray, alpha: np.ndarray, refs: list[bytes]) -> list[tuple[np.ndarray, float]]:
    """Centros de cor (com peso) do logo (peso 3) e das artes de referência (peso 1)."""
    out = []
    lum, sat, _ = _lum_sat(rgb)
    sel = (alpha > 0.5) & (sat > 0.2) & (lum > 0.08) & (lum < 0.94)
    sources = [(rgb[sel], 3.0)]
    for data in refs[:6]:
        try:
            im = Image.open(io.BytesIO(data)).convert("RGB")
            im.thumbnail((96, 96))
            a = np.asarray(im).astype(np.float32).reshape(-1, 3)
            l2, s2, _ = _lum_sat(a)
            sources.append((a[(s2 > 0.25) & (l2 > 0.08) & (l2 < 0.94)], 1.0))
        except Exception:
            continue
    for px, w in sources:
        if len(px) < 30:
            continue
        px = px[:: max(1, len(px) // 6000)]
        k = min(5, len(px) // 10)
        c, lab, _ = _kmeans(px, k)
        for i in range(k):
            share = float((lab == i).mean())
            if share > 0.04:
                s = _lum_sat(c[i][None])[1][0]
                out.append((c[i], w * share * (0.4 + s)))
    return sorted(out, key=lambda x: -x[1])


def _pick_distinct(cands: list[np.ndarray], n: int = 3, min_d: float = 70) -> list[np.ndarray]:
    chosen = []
    for c in cands:
        if all(np.sqrt(((c - x) ** 2).sum()) > min_d for x in chosen):
            chosen.append(c)
        if len(chosen) == n:
            break
    return chosen


def _derive(base: str, n: int) -> list[str]:
    """Completa a paleta a partir de uma cor: vizinha análoga e uma versão clara."""
    r, g, b = _rgb(base) / 255
    hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
    extra = [colorsys.hls_to_rgb((hh + 0.09) % 1, min(.7, ll + .05), ss),
             colorsys.hls_to_rgb(hh, min(.86, ll + .28), max(.25, ss * .6))]
    return [_hex(np.array(x) * 255) for x in extra[:n]]


def brand_palette(rgb: np.ndarray, alpha: np.ndarray, refs: list[bytes], accent: str | None,
                  hints: list[str] | None = None) -> list[str]:
    """3 cores de referência da marca. hints (da IA de visão) são encaixados no centro de cor real mais próximo."""
    cands = [c for c, _ in _candidates(rgb, alpha, refs)]
    picked = []
    if hints:
        for h in hints:
            v = _rgb(h)
            near = min(cands, key=lambda c: ((c - v) ** 2).sum(), default=None)
            picked.append(near if near is not None and np.sqrt(((near - v) ** 2).sum()) < 60 else v)
    if accent:
        picked.insert(0, _rgb(accent))
    pal = _pick_distinct(picked + cands)
    out = [visible(_hex(c)) for c in pal]
    if not out:
        return ["#FFFFFF", "#BDBDBD", "#7A7A7A"]
    return (out + _derive(out[0], 3 - len(out)))[:3]


# ---------- temas (cor de fundo do vídeo) ----------

THEMES = ("dark", "light", "brand")


def _hls(h: str):
    r, g, b = _rgb(h) / 255
    return colorsys.rgb_to_hls(r, g, b)


def _from_hls(hh, ll, ss) -> str:
    return _hex(np.array(colorsys.hls_to_rgb(hh % 1, max(0, min(1, ll)), max(0, min(1, ss)))) * 255)


def _lum(h: str) -> float:
    r, g, b = _rgb(h) / 255
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _rel_lum(h: str) -> float:
    """Luminância relativa da WCAG (sRGB linearizado)."""
    c = _rgb(h) / 255
    c = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return float(0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2])


def contrast_ratio(a: str, b: str) -> float:
    la, lb = sorted((_rel_lum(a), _rel_lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def ensure_contrast(color: str, bg: str, ratio: float = 3.0) -> str:
    """Escurece (fundo claro) ou clareia (fundo escuro) a cor, mantendo o matiz, até atingir o contraste mínimo."""
    if contrast_ratio(color, bg) >= ratio:
        return color
    hh, ll, ss = _hls(color)
    step = -0.03 if _rel_lum(bg) > 0.18 else 0.03
    for _ in range(40):
        ll = max(0.0, min(1.0, ll + step))
        c = _from_hls(hh, ll, ss)
        if contrast_ratio(c, bg) >= ratio:
            return c
    return "#121316" if step < 0 else "#FFFFFF"


def on_light(h: str) -> str:
    """Escurece uma cor clara demais para servir de destaque sobre fundo claro."""
    hh, ll, ss = _hls(h)
    return _from_hls(hh, min(ll, 0.42), max(ss, 0.5) if ss > 0.15 else ss) if _lum(h) > 0.5 else h


def make_theme(name: str, palette: list[str]) -> dict:
    """Cores do vídeo. dark: preto. light: papel claro com tinta escura. brand: cor da marca bem escura."""
    p = [c for c in palette if c.upper() not in ("#FFFFFF", "#BDBDBD", "#7A7A7A")] or ["#FFFFFF"]
    # destaque sobre foto escurecida (o texto vira branco): a cor original, clara o bastante
    acc_ph = ensure_contrast(p[0], "#1C1C1E", 3.2) if p[0] != "#FFFFFF" else "#FFFFFF"
    if name == "light":
        hh, _, ss = _hls(p[0])
        bg = _from_hls(hh, 0.965, min(ss, 0.25))
        acc = ensure_contrast(on_light(p[0]), bg, 3.2) if p[0] != "#FFFFFF" else "#141416"
        return {"bg": bg, "fg": "#121316", "muted": ensure_contrast("#4A4B50", bg, 5),
                "card": "#FFFFFF", "line": _from_hls(hh, 0.86, min(ss, 0.15)), "acc": acc, "accPh": acc_ph,
                "palette": [acc] + [on_light(c) for c in palette[1:3]], "plate": "#141416", "plateInk": "#FFFFFF",
                "mode": "light"}
    if name == "brand" and p[0] != "#FFFFFF":
        hh, _, ss = _hls(p[0])
        bg = _from_hls(hh, 0.11, min(max(ss, 0.45), 0.7))
        # destaque: a cor da paleta que mais contrasta com o fundo (o fundo já é a cor principal)
        cands = palette[1:] + [palette[0]]
        acc = max(cands, key=lambda c: abs(_lum(c) - _lum(bg)) + 0.6 * min(abs(_hls(c)[0] - hh), 1 - abs(_hls(c)[0] - hh)))
        if abs(_lum(acc) - _lum(bg)) < 0.3:
            acc = "#FFFFFF"
        acc = ensure_contrast(acc, bg, 3.2)
        return {"bg": bg, "fg": "#FFFFFF", "muted": ensure_contrast(_from_hls(hh, 0.72, 0.2), bg, 4.5),
                "card": _from_hls(hh, 0.16, min(ss, 0.5)), "accPh": acc_ph,
                "line": _from_hls(hh, 0.26, min(ss, 0.4)), "acc": acc,
                "palette": [acc] + [c for c in palette if c != acc][:2], "plate": PLATE_BG, "plateInk": "#141416",
                "mode": "brand"}
    return {"bg": "#000000", "fg": "#FFFFFF", "muted": "#9A9AA0", "card": "#0B0B0C", "line": "#2A2A2E",
            "acc": ensure_contrast(palette[0], "#000000", 3.2), "accPh": acc_ph,
            "palette": palette[:3], "plate": PLATE_BG, "plateInk": "#141416", "mode": "dark"}


# ---------- entrada principal ----------

def process_logo(data: bytes, fix: str | None = None, max_w: int = 1400, simple: bool | None = None,
                 hint: str | None = None, bg: str = "dark") -> dict:
    """Devolve o logo pronto para o fundo do vídeo (PNG e, se for simples, SVG) e as métricas de contraste.
    bg: "dark" ou "light". fix: none | invert | plate (None = automático). hint: palpite da IA de visão, que
    só vale quando a medição dos pixels não viu problema ou para trocar "invert" por "plate" (a medida é mais
    confiável que a IA para dizer se algo é escuro demais). simple=False força pular o SVG."""
    rgb, alpha = _cutout(data)
    metrics = contrast_metrics(rgb, alpha)
    if fix not in FIXES:
        fix = auto_fix(metrics, bg)
        if hint in FIXES and (fix == "none" or (fix == "invert" and hint == "plate")):
            fix = hint
    accent = _accent(rgb, alpha)
    shown = (_invert_light(rgb) if bg == "light" else _invert_dark(rgb)) if fix == "invert" else rgb
    out = np.dstack([np.clip(shown, 0, 255), np.clip(alpha * 255, 0, 255)]).astype(np.uint8)
    im = Image.fromarray(out, "RGBA")
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    elif im.width < 900:  # logo pequeno: amplia (fica menos borrado e vetoriza melhor)
        k = 900 / im.width
        im = im.resize((900, round(im.height * k)), Image.LANCZOS)
    buf = io.BytesIO(); im.save(buf, "PNG", optimize=True)
    svg = vectorize(im) if simple is not False else None
    return {"png": buf.getvalue(), "svg": svg, "w": im.width, "h": im.height, "accent": accent,
            "fix": fix, "recolored": fix == "invert", "metrics": metrics, "rgb": rgb, "alpha": alpha}


def preview_jpg(data: bytes) -> bytes:
    """Logo original sobre cinza médio, para a IA de visão enxergar partes claras e escuras."""
    rgb, alpha = _cutout(data)
    a = alpha[..., None]
    comp = rgb * a + 128 * (1 - a)
    im = Image.fromarray(comp.astype(np.uint8), "RGB")
    im.thumbnail((800, 800))
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=88)
    return buf.getvalue()


def process_ref(data: bytes, max_side: int = 1600) -> dict:
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    s = max_side / max(img.size)
    if s < 1:
        img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    buf = io.BytesIO(); img.save(buf, "JPEG", quality=86)
    return {"jpg": buf.getvalue(), "w": img.width, "h": img.height}


def ink_for(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return "#000000" if lum > 0.45 else "#FFFFFF"


def glow_for(hex_color: str, a: float = 0.55) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{a})"
