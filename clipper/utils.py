import json
import shutil
import subprocess
from typing import Callable, List, Optional

Log = Callable[[str], None]


def require(binary: str) -> str:
    path = shutil.which(binary)
    if not path:
        raise RuntimeError(f"No se encontró '{binary}'. Instálalo y asegúrate de que está en el PATH.")
    return path


def run(cmd: List[str], log: Optional[Log] = None, cwd: Optional[str] = None) -> str:
    """Ejecuta un comando, reenvía su salida al log y lanza error si falla."""
    proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace")
    lines = []
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        lines.append(line)
        if log and line:
            log(line)
    proc.wait()
    if proc.returncode != 0:
        tail = "\n".join(lines[-25:])
        raise RuntimeError(f"Falló el comando ({proc.returncode}): {' '.join(cmd[:3])}...\n{tail}")
    return "\n".join(lines)


def ffprobe_duration(path: str) -> float:
    out = subprocess.run(
        [require("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "json", path],
        capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


def has_audio(path: str) -> bool:
    out = subprocess.run(
        [require("ffprobe"), "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
         "-of", "csv=p=0", path], capture_output=True, text=True).stdout
    return bool(out.strip())


def fmt_time(sec: float) -> str:
    sec = int(round(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
