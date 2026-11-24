"""Descarga del directo (o de su grabación) con yt-dlp."""
import glob
import json
import os
import re
import subprocess
from typing import Optional, Tuple

from .utils import Log, require, run


def video_id(url: str) -> str:
    m = re.search(r"(?:v=|/live/|youtu\.be/|/shorts/|/embed/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else re.sub(r"[^A-Za-z0-9_-]", "_", os.path.basename(url))[:40] or "video"


def probe(url: str, cookies: str = "") -> dict:
    cmd = [require("yt-dlp"), "-J", "--skip-download", "--no-playlist", url]
    if cookies:
        cmd[1:1] = ["--cookies", cookies]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError("yt-dlp no pudo leer el vídeo:\n" + out.stderr[-1500:])
    return json.loads(out.stdout)


def download(url: str, outdir: str, log: Log, cookies: str = "", max_height: int = 1080,
             limit_minutes: int = 0) -> Tuple[str, Optional[str], dict]:
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
    info = probe(url, cookies)
    slim = {k: info.get(k) for k in ("id", "title", "uploader", "channel", "duration",
                                      "is_live", "was_live", "live_status", "webpage_url")}
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(slim, f, ensure_ascii=False, indent=2)
    log(f"Título: {slim.get('title')} | estado: {slim.get('live_status')}")

    h = max_height
    cmd = [require("yt-dlp"), "--no-playlist", "--newline",
           "-f", f"bv*[height<={h}]+ba/b[height<={h}]/b",
           "--merge-output-format", "mp4",
           "-o", os.path.join(outdir, "source.%(ext)s")]
    if cookies:
        cmd += ["--cookies", cookies]
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
            chat_cmd = [require("yt-dlp"), "--skip-download", "--write-subs", "--sub-langs", "live_chat",
                        "--no-playlist", "-o", os.path.join(outdir, "chat.%(ext)s"), url]
            if cookies:
                chat_cmd[1:1] = ["--cookies", cookies]
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
