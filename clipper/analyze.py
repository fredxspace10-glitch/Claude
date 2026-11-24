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
    kind: str          # "completo" | "destacado" | "momento"
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

    def snap_in(self, target: float, lo: float, hi: float) -> float:
        """Pausa más cercana a `target` dentro de [lo, hi]; si no hay, `target` acotado."""
        if hi < lo:
            return hi
        if len(self.pts):
            cand = self.pts[(self.pts >= lo) & (self.pts <= hi)]
            if len(cand):
                return float(cand[np.argmin(np.abs(cand - target))])
        return float(min(max(target, lo), hi))

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


KIND_LABEL = {"completo": "Parte", "destacado": "Momento top", "momento": "Momento"}


def make_title(text: str, kind: str, idx: int) -> str:
    if not text:
        return f"{KIND_LABEL[kind]} {idx}"
    first = re.split(r"(?<=[.!?¿¡])\s", text)[0]
    words = first.split()
    t = " ".join(words[:10])
    return (t[:1].upper() + t[1:]).rstrip(",;:") + ("…" if len(words) > 10 else "")


def _overlap(a0, a1, b0, b1) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def _fit(start: float, duration: float, snap: "PauseSnapper", o) -> tuple:
    """Ajusta (inicio, fin) a pausas del habla garantizando min_seconds <= duración <= max_seconds."""
    mn, target, mx = float(o.min_seconds), float(o.clip_seconds), float(max(o.max_seconds, o.min_seconds))
    if duration <= mn:
        return 0.0, duration
    s = snap.snap_in(start, start - 3, start + 1)
    s = min(max(0.0, s), duration - mn)
    e = snap.snap_in(s + target, s + mn, min(duration, s + mx))
    e = min(e, duration)
    if e - s < mn:  # al final del vídeo: se retrocede el inicio para no bajar del mínimo
        s = max(0.0, e - mn)
    return round(s, 2), round(e, 2)


def plan_clips(duration: float, score: np.ndarray, words: List[dict], opts) -> List[Clip]:
    snap = PauseSnapper(words)
    clips: List[Clip] = []
    mn = float(opts.min_seconds)
    L = int(opts.clip_seconds)
    minutes = duration / 60
    if duration < mn:
        # vídeo más corto que el mínimo: un único clip con todo
        c = Clip("completo", 1, 0.0, round(duration, 2), float(score.mean()))
        c.text = text_between(words, c.start, c.end)
        c.title = make_title(c.text, c.kind, 1)
        return [c]

    # 1) Todo el directo en partes de ~1 minuto, ninguna por debajo del mínimo
    if opts.make_full:
        t, i = 0.0, 1
        while duration - t >= 1:
            e = snap.snap_in(t + L, t + mn, min(duration, t + opts.max_seconds))
            if duration - e < mn:      # lo que queda no llega al mínimo: se une a esta parte
                e = duration
            sc = float(score[int(t):int(e)].mean()) if e > t + 1 else 0.0
            clips.append(Clip("completo", i, round(t, 2), round(e, 2), sc))
            i += 1
            t = e
            if opts.max_full_clips and i > opts.max_full_clips:
                break

    # 2) Destacados: los minutos completos con más energía
    top_n = opts.top_count or max(3, round(minutes / 6))
    chosen: List[tuple] = []
    for rank, (a, b, sc) in enumerate(_top_windows(score, L, top_n, gap=5, taken=[]), 1):
        s, e = _fit(a, duration, snap, opts)
        clips.append(Clip("destacado", rank, s, e, sc))
        chosen.append((s, e))

    # 3) Momentos: picos cortos (reacciones, risas, gritos) ampliados a +1 min con contexto,
    #    empezando unos segundos antes del pico para que se entienda qué pasa.
    P = int(opts.peak_seconds)
    want = opts.moment_count or max(5, round(minutes / 3))
    rank = 0
    for a, b, sc in _top_windows(score, P, want * 3, gap=3, taken=[]):
        lead = (L - P) * 0.6
        s, e = _fit(max(0.0, a - lead), duration, snap, opts)
        if any(_overlap(s, e, x0, x1) > 0.5 * (e - s) for x0, x1 in chosen):
            continue  # demasiado parecido a otro destacado/momento
        if any(_overlap(s, e, c.start, c.end) > 0.9 * (e - s) for c in clips if c.kind == "completo"):
            continue  # prácticamente igual a una parte del directo completo
        rank += 1
        clips.append(Clip("momento", rank, s, e, sc))
        chosen.append((s, e))
        if rank >= want:
            break

    for c in clips:
        c.text = text_between(words, c.start, c.end)
        c.title = make_title(c.text, c.kind, c.index)
    return clips


def save_analysis(path: str, score: np.ndarray, clips: List[Clip]):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"score": [round(float(x), 3) for x in score],
                   "clips": [c.to_dict() for c in clips]}, f, ensure_ascii=False)
