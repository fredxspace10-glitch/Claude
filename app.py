"""Interfaz web local:  python app.py  ->  abre http://localhost:5000"""
import io
import os
import platform
import subprocess
import threading
import uuid
import zipfile

from flask import Flask, abort, jsonify, render_template, request, send_file, send_from_directory

from clipper.config import Options
from clipper.pipeline import Job, run_job

DEFAULT_URL = "https://www.youtube.com/live/Dxi1CRQMQZo"
app = Flask(__name__)
JOBS: dict = {}


@app.get("/")
def index():
    return render_template("index.html", defaults=Options(url=DEFAULT_URL).to_dict())


@app.post("/api/jobs")
def create_job():
    data = request.get_json(force=True) or {}
    opts = Options.from_dict(data)
    if not opts.url:
        return jsonify(error="Falta el enlace"), 400
    jid = uuid.uuid4().hex[:8]
    job = Job(opts)
    JOBS[jid] = job
    threading.Thread(target=run_job, args=(job,), daemon=True).start()
    return jsonify(id=jid)


@app.get("/api/jobs/<jid>")
def job_status(jid):
    job = JOBS.get(jid) or abort(404)
    return jsonify(job.snapshot())


def _job_or_404(jid) -> Job:
    job = JOBS.get(jid)
    if not job or not job.out_dir or not os.path.isdir(job.out_dir):
        abort(404)
    return job


@app.get("/media/<jid>/<path:name>")
def media(jid, name):
    job = _job_or_404(jid)
    return send_from_directory(job.out_dir, name, as_attachment=request.args.get("dl") == "1")


@app.get("/api/jobs/<jid>/zip")
def zip_all(jid):
    """Descarga todos los clips (y PUBLICAR.txt) en un único ZIP."""
    job = _job_or_404(jid)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        for root, _, files in os.walk(job.out_dir):
            for f in files:
                if f.endswith((".mp4", ".txt", ".json")) and ".part" not in f:
                    full = os.path.join(root, f)
                    z.write(full, os.path.relpath(full, job.out_dir))
    buf.seek(0)
    return send_file(buf, mimetype="application/zip", as_attachment=True,
                     download_name=os.path.basename(job.out_dir) + ".zip")


@app.post("/api/jobs/<jid>/open")
def open_folder(jid):
    """Abre la carpeta de los clips en el explorador de archivos del ordenador."""
    job = _job_or_404(jid)
    system = platform.system()
    if system == "Windows":
        os.startfile(job.out_dir)  # type: ignore[attr-defined]
    elif system == "Darwin":
        subprocess.Popen(["open", job.out_dir])
    else:
        subprocess.Popen(["xdg-open", job.out_dir])
    return jsonify(ok=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Abre http://localhost:{port} en tu navegador")
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
