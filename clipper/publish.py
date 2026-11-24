"""Genera PUBLICAR.txt: título, descripción y hashtags listos para copiar en TikTok/Facebook."""
import os
import re
from collections import Counter
from typing import List

from .utils import fmt_time

STOP = set("""a al algo algunos ante antes aquí así aunque bien cada como con contra cual cuando de del
desde donde dos el ella ellas ellos en entonces entre era eres es esa esas ese eso esos esta está están
estas este esto estos estoy fue fueron ha hace hacer han hasta hay he la las le les lo los más me mi mis
mucho muy nada ni no nos nosotros o os otra otro para pero poco por porque que qué quien se sea ser si sí
sin sobre solo son su sus también tan te tengo ti tiene todo todos tu tú tus un una uno unos va vamos
ver voy y ya yo puede puedo hacer tiene estar está eh ah oh pues bueno entonces digo dice decir verdad osea vale okay ok the and you that
this is to of it in i we for on was with""".split())

GENERIC = {
    "tiktok": ["#fyp", "#parati", "#viral"],
    "facebook": ["#reels", "#viral", "#directo"],
}
SECTION = {"destacado": "DESTACADOS", "momento": "MOMENTOS", "completo": "DIRECTO COMPLETO"}


def keywords(text: str, n: int = 4) -> List[str]:
    words = [re.sub(r"[^\wáéíóúñü]", "", w.lower()) for w in text.split()]
    c = Counter(w for w in words if len(w) > 3 and w not in STOP and not w.isdigit())
    return [w for w, _ in c.most_common(n)]


def hashtags(clip_text: str, global_text: str) -> List[str]:
    tags = []
    for w in keywords(clip_text, 3) + keywords(global_text, 2):
        t = "#" + w
        if t not in tags:
            tags.append(t)
    return tags[:5]


def write_publish_file(path: str, title: str, source_url: str, clips: List[dict]):
    all_text = " ".join(c.get("text", "") for c in clips)
    out = [f"CLIPS DE: {title}", f"Original: {source_url}", "",
           "Todos los clips duran más de 1 minuto (requisito para monetizar en TikTok y Facebook).",
           "Copia el título y la descripción de cada clip al subirlo.", ""]
    current = None
    for c in clips:
        if c["kind"] != current:
            current = c["kind"]
            out += ["=" * 60, SECTION[current], "=" * 60, ""]
        tags = hashtags(c.get("text", ""), all_text)
        extra = {k: [g for g in v if g not in tags] for k, v in GENERIC.items()}
        out += [
            f"▶ ARCHIVO: {c['file']}   ({fmt_time(c['duration'])} min · minuto {c['range']} del directo)",
            f"TÍTULO: {c['title']}",
            f"DESCRIPCIÓN TIKTOK: {c['title']} {' '.join(tags + extra['tiktok'])}",
            f"DESCRIPCIÓN FACEBOOK: {c['title']}\n{' '.join(tags + extra['facebook'])}",
        ]
        if c.get("source_link"):
            out.append(f"CRÉDITO / ORIGINAL: {c['source_link']}")
        out.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def safe_name(s: str, max_len: int = 60) -> str:
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", s or "").strip().strip(".")
    return re.sub(r"\s+", " ", s)[:max_len].strip() or "directo"


def folder_for(clips_root: str, title: str, vid: str) -> str:
    return os.path.abspath(os.path.join(clips_root, f"{safe_name(title)} [{vid}]"))
