"""Descarga del directo (o de su grabación) con yt-dlp."""
import glob
import json
import os
import re
import shutil
import subprocess
from typing import List, Optional, Tuple

from .utils import Log, require, run


def video_id(url: str) -> str:
    m = re.search(r"(?:v=|/live/|youtu\.be/|/shorts/|/embed/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else re.sub(r"[^A-Za-z0-9_-]", "_", os.path.basename(url))[:40] or "video"


CLIENT_FALLBACKS = ["", "web_safari", "mweb", "tv"]


def _base_args(cookies: str = "", cookies_browser: str = "", client: str = "") -> List[str]:
    args = [require("yt-dlp"), "--no-playlist"]
    # YouTube exige un motor JavaScript; se usa deno o, si no está, node.
    if not shutil.which("deno") and shutil.which("node"):
        args += ["--js-runtimes", "node"]
    if cookies:
        args += ["--cookies", cookies]
    elif cookies_browser:
        args += ["--cookies-from-browser", cookies_browser]
    if client:
        args += ["--extractor-args", f"youtube:player_client={client}"]
    return args


def probe(url: str, cookies: str = "", cookies_browser: str = "") -> Tuple[dict, str]:
    """Lee la información del vídeo probando varios clientes de YouTube. Devuelve (info, cliente)."""
    last = ""
    for client in CLIENT_FALLBACKS:
        out = subprocess.run(_base_args(cookies, cookies_browser, client) + ["-J", "--skip-download", url],
                             capture_output=True, text=True, encoding="utf-8", errors="replace")
        if out.returncode == 0:
            info = json.loads(out.stdout)
            if info.get("formats"):
                return info, client
        last = out.stderr[-1200:]
    hint = ""
    if "not a bot" in last or "Sign in" in last:
        hint = ("\n\nYouTube pide iniciar sesión. Solución: usa la opción 'cookies del navegador' "
                "(chrome/edge/firefox) o un archivo cookies.txt. Más detalles en el README.")
    raise RuntimeError("yt-dlp no pudo leer el vídeo:\n" + last + hint)


def download(url: str, outdir: str, log: Log, cookies: str = "", max_height: int = 1080,
             limit_minutes: int = 0, cookies_browser: str = "") -> Tuple[str, Optional[str], dict]:
    """Devuelve (ruta_video, ruta_chat_o_None, info)."""
    os.makedirs(outdir, exist_ok=True)
    existing = [p for p in glob.glob(os.path.join(outdir, "source.*"))
                if p.endswith((".mp4", ".mkv", ".webm"))]
    info_path = os.path.join(outdir, "info.json")
    if existing and os.path.exists(info_path):
        log("Vídeo ya descargado, se reutiliza.")
        chat = _find_chat(outdir)
        with open(info_path, encoding="utf-8") as f:
            return existing[0], chat, json.load(f)

    log("Leyendo información del vídeo...")
    info, client = probe(url, cookies, cookies_browser)
    slim = {k: info.get(k) for k in ("id", "title", "uploader", "channel", "duration",
                                      "is_live", "was_live", "live_status", "webpage_url")}
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(slim, f, ensure_ascii=False, indent=2)
    log(f"Título: {slim.get('title')} | estado: {slim.get('live_status')}")

    h = max_height
    cmd = _base_args(cookies, cookies_browser, client) + [
        "--newline", "-f", f"bv*[height<={h}]+ba/b[height<={h}]/b",
        "--merge-output-format", "mp4", "-o", os.path.join(outdir, "source.%(ext)s")]
    if slim.get("live_status") == "is_live":
        log("El directo sigue en emisión: se descarga desde el principio hasta ahora "
            "(o hasta el límite de minutos).")
        cmd += ["--live-from-start"]
    if limit_minutes and limit_minutes > 0:
        cmd += ["--download-sections", f"*0-{int(limit_minutes) * 60}"]
    cmd.append(url)
    run(cmd, log=_throttle(log))

    # Chat repetido del directo (si existe): sirve para detectar los momentos con más reacciones.
    if slim.get("live_status") in ("was_live", "post_live"):
        try:
            chat_cmd = _base_args(cookies, cookies_browser) + [
                "--skip-download", "--write-subs", "--sub-langs", "live_chat",
                "-o", os.path.join(outdir, "chat.%(ext)s"), url]
            log("Descargando el chat del directo (para detectar momentos clave)...")
            run(chat_cmd, log=_throttle(log))
        except Exception as e:  # el chat es opcional
            log(f"No se pudo descargar el chat (se continúa sin él): {str(e)[:200]}")

    files = [p for p in glob.glob(os.path.join(outdir, "source.*"))
             if p.endswith((".mp4", ".mkv", ".webm"))]
    if not files:
        raise RuntimeError("La descarga terminó pero no se encontró el vídeo.")
    return files[0], _find_chat(outdir), slim


def _find_chat(outdir: str) -> Optional[str]:
    c = glob.glob(os.path.join(outdir, "chat*.live_chat.json"))
    return c[0] if c else None


def _throttle(log: Log) -> Log:
    """Evita inundar el log con cientos de líneas de progreso."""
    state = {"last": -10.0}

    def inner(line: str):
        m = re.search(r"\[download\]\s+([\d.]+)%", line)
        if m:
            pct = float(m.group(1))
            if pct - state["last"] < 5 and pct < 100:
                return
            state["last"] = pct
        log(line)
    return inner
