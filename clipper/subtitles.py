"""Genera subtítulos .ass animados (palabra resaltada, estilo Shorts/TikTok)."""
from typing import List

HIGHLIGHT = r"{\c&H00E5FF&\fscx112\fscy112}"   # amarillo (BGR) y un pequeño "pop"
RESET = r"{\r}"


def _ts(t: float) -> str:
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _clean(text: str) -> str:
    return text.replace("\\", "/").replace("{", "(").replace("}", ")").replace("\n", " ")


def _chunks(words: List[dict], per_line: int) -> List[List[dict]]:
    out, cur = [], []
    for w in words:
        if cur and (len(cur) >= per_line or w["start"] - cur[-1]["end"] > 0.8):
            out.append(cur)
            cur = []
        cur.append(w)
        if w["word"][-1:] in ".!?":
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def build_ass(words: List[dict], clip_start: float, clip_end: float, width: int, height: int,
              font: str = "Arial", per_line: int = 3, hook: str = "", hook_seconds: float = 2.8,
              credit: str = "") -> str:
    vertical = height > width
    size = int(height * (0.045 if vertical else 0.06))
    margin_v = int(height * (0.27 if vertical else 0.08))
    hook_size = int(height * (0.035 if vertical else 0.055))
    hook_margin = int(height * (0.12 if vertical else 0.06))
    dur = clip_end - clip_start

    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{font},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,{max(3, size // 14)},2,2,60,60,{margin_v},1
Style: Credit,{font},{int(height * (0.022 if vertical else 0.03))},&H30FFFFFF,&H30FFFFFF,&H60000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,1,9,40,40,{int(height * (0.05 if vertical else 0.04))},1
Style: Hook,{font},{hook_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&HC0101010,-1,0,0,0,100,100,1,0,3,{max(10, hook_size // 4)},0,8,60,60,{hook_margin},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [head]
    if credit:
        lines.append(f"Dialogue: 2,{_ts(0)},{_ts(dur)},Credit,,0,0,0,,{_clean(credit)}\n")
    if hook:
        lines.append(f"Dialogue: 1,{_ts(0.15)},{_ts(min(hook_seconds, dur))},Hook,,0,0,0,,"
                     rf"{{\fad(150,250)}}{_clean(hook.upper())}" + "\n")

    sel = [dict(w, start=w["start"] - clip_start, end=w["end"] - clip_start)
           for w in words if clip_start <= w["start"] < clip_end]
    groups = _chunks(sel, per_line)
    for gi, g in enumerate(groups):
        next_start = groups[gi + 1][0]["start"] if gi + 1 < len(groups) else dur
        tokens = [_clean(w["word"]).upper() for w in g]
        for i, w in enumerate(g):
            st = w["start"]
            en = g[i + 1]["start"] if i + 1 < len(g) else min(w["end"] + 0.35, next_start)
            if en <= st:
                en = st + 0.08
            text = " ".join((HIGHLIGHT + t + RESET) if j == i else t for j, t in enumerate(tokens))
            lines.append(f"Dialogue: 0,{_ts(st)},{_ts(min(en, dur))},Sub,,0,0,0,,{text}\n")
    return "".join(lines)
