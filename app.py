"""Interfaz web local:  python app.py  ->  abre http://localhost:5000"""
import os
import threading
import uuid

from flask import Flask, abort, jsonify, render_template, request, send_from_directory

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


@app.get("/media/<jid>/<path:name>")
def media(jid, name):
    job = JOBS.get(jid) or abort(404)
    folder = os.path.join(job.job_dir, "clips")
    if not job.job_dir or not os.path.isdir(folder):
        abort(404)
    return send_from_directory(folder, name, as_attachment=request.args.get("dl") == "1")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Abre http://localhost:{port} en tu navegador")
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
