"""Transcripción con marcas de tiempo por palabra (faster-whisper)."""
import json
import os
from typing import List

from .utils import Log, fmt_time


def transcribe(video: str, outdir: str, log: Log, model_size: str = "small",
               language: str = "es") -> List[dict]:
    """Devuelve una lista de palabras: [{"start", "end", "word"}]. Se guarda en caché."""
    cache = os.path.join(outdir, f"transcript_{model_size}_{language}.json")
    if os.path.exists(cache):
        log("Transcripción ya existente, se reutiliza.")
        with open(cache, encoding="utf-8") as f:
            return json.load(f)

    from faster_whisper import WhisperModel  # import tardío: es pesado

    log(f"Cargando modelo Whisper '{model_size}' (la primera vez se descarga)...")
    model = WhisperModel(model_size, device="auto", compute_type="default")
    lang = None if language in ("", "auto") else language
    segments, info = model.transcribe(video, language=lang, word_timestamps=True, vad_filter=True,
                                      beam_size=5)
    log(f"Idioma detectado: {info.language} | duración: {fmt_time(info.duration)}")

    words: List[dict] = []
    last_report = 0.0
    for seg in segments:
        for w in seg.words or []:
            text = w.word.strip()
            if text:
                words.append({"start": round(w.start, 3), "end": round(w.end, 3), "word": text})
        if seg.end - last_report >= 120:
            last_report = seg.end
            log(f"Transcribiendo... {fmt_time(seg.end)} / {fmt_time(info.duration)}")

    with open(cache, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False)
    log(f"Transcripción lista: {len(words)} palabras.")
    return words
