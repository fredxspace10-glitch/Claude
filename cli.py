"""Uso por terminal:  python cli.py "https://www.youtube.com/live/Dxi1CRQMQZo" [opciones]"""
import argparse
from dataclasses import fields

from clipper.config import Options
from clipper.pipeline import Job, run_job


def main():
    p = argparse.ArgumentParser(description="Convierte un directo de YouTube en clips con subtítulos.")
    p.add_argument("url", help="Enlace de YouTube o ruta a un vídeo local")
    for f in fields(Options):
        if f.name == "url":
            continue
        default = getattr(Options, f.name)
        flag = "--" + f.name.replace("_", "-")
        if isinstance(default, bool):
            p.add_argument(flag, dest=f.name, action=argparse.BooleanOptionalAction, default=default)
        else:
            p.add_argument(flag, dest=f.name, type=type(default), default=default)
    args = vars(p.parse_args())
    job = run_job(Job(Options.from_dict(args)))
    raise SystemExit(0 if job.status == "terminado" else 1)


if __name__ == "__main__":
    main()
