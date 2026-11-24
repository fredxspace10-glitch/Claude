"""Detecta los mejores momentos del directo y planifica los clips."""
import json
import re
import subprocess
from dataclasses import dataclass, asdict
from typing import List, Optional

import numpy as np

from .utils import require

KEYWORDS = [
    "jaja", "jajaja", "jeje", "xd", "wow", "guau", "increíble", "increible", "no puede ser",
    "qué locura", "que locura", "brutal", "vamos", "gol", "madre mía", "madre mia", "dios mío",
    "dios mio", "atención", "atencion", "importante", "secreto", "truco", "nunca", "mira",
    "escuchen", "ojo", "lol", "omg", "oh my god", "let's go", "insane", "crazy", "what",
]


@dataclass
class Clip:
    kind: str          # "completo" | "destacado" | "corto"
    index: int
    start: float
    end: float
    score: float = 0.0
    title: str = ""
    text: str = ""
    file: str = ""

    @property
    def duration(self) -> float:
        return self.end - self.start

    def to_dict(self) -> dict:
        d = asdict(self)
        d["duration"] = round(self.duration, 2)
        return d


# ---------------------------------------------------------------- señales por segundo

def audio_loudness(video: str, duration: float) -> np.ndarray:
    """Volumen (dB RMS) por segundo, leyendo el audio en streaming."""
    sr = 8000
    n = int(np.ceil(duration)) + 1
    out = np.full(n, -90.0)
    proc = subprocess.Popen([require("ffmpeg"), "-v", "error", "-i", video, "-vn", "-ac", "1",
                             "-ar", str(sr), "-f", "s16le", "-"], stdout=subprocess.PIPE)
    assert proc.stdout is not None
    i = 0
    while True:
        buf = proc.stdout.read(sr * 2)
        if not buf:
            break
        a = np.frombuffer(buf, dtype=np.int16).astype(np.float32) / 32768.0
        if i < n and len(a):
            out[i] = 20 * np.log10(np.sqrt(np.mean(a * a)) + 1e-6)
        i += 1
    proc.wait()
    return out


def chat_density(chat_path: Optional[str], n: int) -> Optional[np.ndarray]:
    if not chat_path:
        return None
    counts = np.zeros(n)
    pat = re.compile(r'"videoOffsetTimeMsec"\s*:\s*"?(\d+)')
    with open(chat_path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = pat.search(line)
            if m:
                s = int(m.group(1)) // 1000
                if 0 <= s < n:
                    counts[s] += 1
    return counts if counts.sum() > 0 else None


def speech_features(words: List[dict], n: int):
    rate = np.zeros(n)
    kw = np.zeros(n)
    for w in words:
        s = int(w["start"])
        if 0 <= s < n:
            rate[s] += 1
            txt = w["word"].lower()
            if "!" in txt or "?" in txt:
                kw[s] += 0.5
    # palabras clave de varias palabras: se buscan en ventanas de texto
    for i in range(len(words)):
        chunk = " ".join(x["word"].lower() for x in words[i:i + 4])
        for k in KEYWORDS:
            if chunk.startswith(k) or chunk.split(" ")[0].strip(".,!?¡¿") == k:
                s = int(words[i]["start"])
                if 0 <= s < n:
                    kw[s] += 1
                break
    return rate, kw


def _z(x: np.ndarray) -> np.ndarray:
    sd = x.std()
    if sd < 1e-9:
        return np.zeros_like(x)
    return np.clip((x - x.mean()) / sd, -3, 3)


def _smooth(x: np.ndarray, w: int) -> np.ndarray:
    if w <= 1 or len(x) < w:
        return x
    k = np.ones(w) / w
    return np.convolve(x, k, mode="same")


def score_timeline(video: str, duration: float, words: List[dict],
                   chat_path: Optional[str]) -> np.ndarray:
    n = int(np.ceil(duration)) + 1
    loud = audio_loudness(video, duration)[:n]
    loud_z = _z(_smooth(loud, 3))
    jump = np.maximum(np.diff(loud, prepend=loud[0]), 0)
    jump_z = _z(_smooth(jump, 3))
    rate, kw = speech_features(words, n)
    rate_z = _z(_smooth(rate, 5))
    kw_z = _z(_smooth(kw, 5))
    parts = [(0.35, loud_z), (0.15, jump_z), (0.2, rate_z), (0.1, kw_z)]
    chat = chat_density(chat_path, n)
    if chat is not None:
        # el chat reacciona con unos segundos de retraso: se adelanta 6 s
        chat = np.roll(_smooth(chat, 10), -6)
        parts.append((0.3, _z(chat)))
    total_w = sum(w for w, _ in parts)
    score = sum(w * p for w, p in parts) / total_w
    return _smooth(score, 5)


# ---------------------------------------------------------------- planificación

class PauseSnapper:
    """Ajusta los cortes a pausas del habla para no cortar frases a la mitad."""

    def __init__(self, words: List[dict]):
        pts = []
        for a, b in zip(words, words[1:]):
            if b["start"] - a["end"] >= 0.25:
                pts.append((a["end"] + b["start"]) / 2)
        self.pts = np.array(pts)

    def snap(self, t: float, tol: float) -> float:
        if not len(self.pts):
            return t
        i = int(np.argmin(np.abs(self.pts - t)))
        return float(self.pts[i]) if abs(self.pts[i] - t) <= tol else t


def _top_windows(score: np.ndarray, length: int, count: int, gap: int,
                 taken: List[tuple]) -> List[tuple]:
    n = len(score)
    if n <= length or count <= 0:
        return []
    cs = np.concatenate([[0], np.cumsum(score)])
    win = (cs[length:] - cs[:-length]) / length
    win = win.astype(float).copy()
    for a, b in taken:  # evita repetir exactamente lo ya elegido
        lo = max(0, int(a) - length + int(length * 0.5))
        hi = min(len(win), int(b) - int(length * 0.5))
        if hi > lo:
            win[lo:hi] = -np.inf
    res = []
    for _ in range(count):
        i = int(np.argmax(win))
        if not np.isfinite(win[i]):
            break
        res.append((i, i + length, float(win[i])))
        win[max(0, i - length - gap):i + length + gap] = -np.inf
    return res


def text_between(words: List[dict], start: float, end: float) -> str:
    return " ".join(w["word"] for w in words if start <= w["start"] < end).strip()


def make_title(text: str, kind: str, idx: int) -> str:
    if not text:
        return {"completo": "Parte", "destacado": "Momento top", "corto": "Momento corto"}[kind] + f" {idx}"
    first = re.split(r"(?<=[.!?¿¡])\s", text)[0]
    words = first.split()
    t = " ".join(words[:10])
    return (t[:1].upper() + t[1:]).rstrip(",;:") + ("…" if len(words) > 10 else "")


def plan_clips(duration: float, score: np.ndarray, words: List[dict], opts) -> List[Clip]:
    snap = PauseSnapper(words)
    clips: List[Clip] = []
    L = int(opts.clip_seconds)
    minutes = duration / 60

    # 1) Todo el directo en partes de ~1 minuto (cada momento)
    if opts.make_full:
        t, i = 0.0, 1
        while t < duration - 1:
            end = min(duration, snap.snap(t + L, tol=6))
            if duration - end < L * 0.25:
                end = duration
            sc = float(score[int(t):int(end)].mean()) if end > t + 1 else 0.0
            clips.append(Clip("completo", i, round(t, 2), round(end, 2), sc))
            i += 1
            t = end
            if opts.max_full_clips and i > opts.max_full_clips:
                break

    # 2) Destacados de 1 minuto (los picos de energía/chat/habla)
    top_n = opts.top_count or max(3, round(minutes / 6))
    top = _top_windows(score, L, top_n, gap=5, taken=[])
    for rank, (a, b, sc) in enumerate(top, 1):
        s = max(0.0, snap.snap(a, tol=3))
        e = min(duration, snap.snap(s + L, tol=4))
        clips.append(Clip("destacado", rank, round(s, 2), round(e, 2), sc))

    # 3) Momentos cortos (más cantidad de contenido)
    S = int(opts.short_seconds)
    short_n = opts.short_count or max(5, round(minutes / 3))
    shorts = _top_windows(score, S, short_n, gap=3, taken=[])
    for rank, (a, b, sc) in enumerate(shorts, 1):
        s = max(0.0, snap.snap(a, tol=2))
        e = min(duration, snap.snap(s + S, tol=2))
        clips.append(Clip("corto", rank, round(s, 2), round(e, 2), sc))

    for c in clips:
        c.text = text_between(words, c.start, c.end)
        c.title = make_title(c.text, c.kind, c.index)
    return [c for c in clips if c.duration >= 3]


def save_analysis(path: str, score: np.ndarray, clips: List[Clip]):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"score": [round(float(x), 3) for x in score],
                   "clips": [c.to_dict() for c in clips]}, f, ensure_ascii=False)
