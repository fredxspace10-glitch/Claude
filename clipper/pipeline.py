"""Orquesta todo: descarga -> transcripción -> análisis -> renderizado."""
import json
import os
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, List, Optional

from . import analyze, download, publish, render, transcribe
from .config import Options
from .utils import ffprobe_duration, fmt_time


class Job:
    def __init__(self, opts: Options, on_update: Optional[Callable[["Job"], None]] = None):
        self.opts = opts
        self.status = "en cola"
        self.progress = 0.0
        self.logs: List[str] = []
        self.clips: List[dict] = []
        self.error = ""
        self.title = ""
        self.job_dir = ""
        self.out_dir = ""   # carpeta final con los clips listos para subir
        self.started = time.time()
        self._on_update = on_update

    def log(self, msg: str):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        self.logs.append(line)
        self.logs = self.logs[-400:]
        print(line, flush=True)
        if self._on_update:
            self._on_update(self)

    def snapshot(self) -> dict:
        return {"status": self.status, "progress": round(self.progress, 1), "title": self.title,
                "error": self.error, "logs": self.logs[-60:], "clips": self.clips,
                "job": os.path.basename(self.job_dir), "out_dir": self.out_dir}


def run_job(job: Job) -> Job:
    o = job.opts
    try:
        local = os.path.isfile(o.url)
        vid = os.path.splitext(os.path.basename(o.url))[0] if local else download.video_id(o.url)
        job.job_dir = os.path.abspath(os.path.join(o.workdir, vid))
        os.makedirs(job.job_dir, exist_ok=True)
        with open(os.path.join(job.job_dir, "options.json"), "w", encoding="utf-8") as f:
            json.dump(o.to_dict(), f, ensure_ascii=False, indent=2)

        # 1. Fuente
        job.status = "descargando"
        chat = None
        info = {"title": vid, "webpage_url": o.url}
        if local:
            source = o.url
            job.log(f"Usando archivo local: {source}")
        else:
            source, chat, info = download.download(o.url, job.job_dir, job.log, o.cookies,
                                                   o.max_height, o.limit_minutes, o.cookies_browser)
        job.title = info.get("title") or vid
        job.out_dir = publish.folder_for(o.clips_dir, job.title, vid)
        job.log(f"Los clips se guardarán en: {job.out_dir}")
        duration = ffprobe_duration(source)
        job.log(f"Duración del vídeo: {fmt_time(duration)}")
        job.progress = 15

        # 2. Transcripción
        # (también se usa para detectar momentos y cortar en pausas, no solo para subtítulos)
        words: List[dict] = []
        job.status = "transcribiendo"
        try:
            words = transcribe.transcribe(source, job.job_dir, job.log, o.whisper_model, o.language)
        except Exception as e:
            if o.subtitles:
                raise
            job.log(f"Sin transcripción ({e}); se continúa sin ella.")
        job.progress = 45

        # 3. Análisis de momentos
        job.status = "analizando momentos"
        job.log("Analizando volumen, ritmo del habla, palabras clave" + (" y chat..." if chat else "..."))
        score = analyze.score_timeline(source, duration, words, chat)
        plan = analyze.plan_clips(duration, score, words, o)
        analyze.save_analysis(os.path.join(job.job_dir, "analysis.json"), score, plan)
        counts = {k: sum(1 for c in plan if c.kind == k) for k in ("completo", "destacado", "momento")}
        job.log(f"Plan: {counts['destacado']} destacados, {counts['momento']} momentos y "
                f"{counts['completo']} partes del directo completo (todos de {o.min_seconds}+ s).")
        job.progress = 50

        # 4. Renderizado
        job.status = "renderizando clips"
        tmp_dir = os.path.join(job.job_dir, "_tmp")
        snap = analyze.PauseSnapper(words)
        base_url = info.get("webpage_url") or o.url
        done = 0
        # primero los destacados y cortos: son los más valiosos
        rank = {"destacado": 0, "momento": 1, "completo": 2}
        order = sorted(plan, key=lambda c: rank[c.kind])
        with ThreadPoolExecutor(max_workers=max(1, o.workers)) as pool:
            futs = {pool.submit(render.render_clip, source, c, words, snap, o, job.out_dir, tmp_dir,
                                lambda m: None): c
                    for c in order}
            for fut in as_completed(futs):
                c = futs[fut]
                try:
                    c.file = fut.result()
                    d = c.to_dict()
                    d["source_link"] = _link(base_url, c.start) if not local else ""
                    d["range"] = f"{fmt_time(c.start)} - {fmt_time(c.end)}"
                    job.clips.append(d)
                    job.log(f"Clip listo: {c.file} ({d['range']}) — {c.title}")
                except Exception as e:
                    job.log(f"Error en {c.kind} {c.index}: {str(e)[:400]}")
                done += 1
                job.progress = 50 + 50 * done / max(1, len(order))

        job.clips.sort(key=lambda d: (rank[d["kind"]], d["index"]))
        with open(os.path.join(job.out_dir, "clips.json"), "w", encoding="utf-8") as f:
            json.dump({"title": job.title, "source": base_url, "clips": job.clips}, f,
                      ensure_ascii=False, indent=2)
        publish.write_publish_file(os.path.join(job.out_dir, "PUBLICAR.txt"), job.title,
                                   base_url if not local else o.url, job.clips, o.credit)
        job.status = "terminado"
        job.progress = 100
        job.log(f"Terminado: {len(job.clips)} clips. Están en: {job.out_dir}")
        job.log("Dentro: 1_destacados, 2_momentos, 3_directo_completo y PUBLICAR.txt "
                "(títulos y hashtags para cada clip).")
    except Exception as e:
        job.status = "error"
        job.error = str(e)
        job.log("ERROR: " + str(e))
        traceback.print_exc()
    return job


def _link(url: str, t: float) -> str:
    vid = download.video_id(url)
    return f"https://www.youtube.com/watch?v={vid}&t={int(t)}s"
