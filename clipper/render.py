"""Renderiza cada clip con ffmpeg: formato, espejo, zooms, transiciones y subtítulos."""
import os
from typing import List

from .analyze import Clip, PauseSnapper
from .subtitles import build_ass
from .utils import Log, has_audio, require, run

TRANSITIONS = ["slideleft", "circleopen", "fadewhite", "smoothup", "zoomin",
               "wipeleft", "radial", "slideup", "pixelize", "smoothleft"]
REVERSED = {"slideleft": "slideright", "slideright": "slideleft", "slideup": "slidedown",
            "slidedown": "slideup", "wipeleft": "wiperight", "wiperight": "wipeleft",
            "smoothleft": "smoothright", "smoothright": "smoothleft", "smoothup": "smoothdown",
            "smoothdown": "smoothup", "circleopen": "circleclose", "circleclose": "circleopen",
            "zoomin": "fadeblack", "fadewhite": "fadeblack"}
ZOOMS = [1.0, 1.14, 1.0, 1.24, 1.07]
HOOKS = {"completo": "Parte {i}", "destacado": "Momento top #{i}", "corto": "No te lo pierdas"}
FPS = 30


def _cut_points(clip: Clip, snap: PauseSnapper, seg: float, trans: float) -> List[float]:
    """Cortes internos (relativos al clip), alineados a pausas del habla."""
    dur = clip.duration
    if seg <= 0 or dur < seg * 1.5:
        return []
    cuts, t, k = [], 0.0, 0
    while True:
        step = seg * (0.8 if k % 2 else 1.2)  # ritmo irregular, más natural
        t += step
        k += 1
        if t > dur - seg * 0.6:
            break
        c = snap.snap(clip.start + t, tol=1.5) - clip.start
        if cuts and c - cuts[-1] < trans * 3:
            continue
        if c < trans * 3 or c > dur - trans * 3:
            continue
        cuts.append(round(c, 3))
        t = c
    return cuts


def build_filter(clip: Clip, opts, cuts: List[float], ass_name: str, audio: bool):
    W, H = (1080, 1920) if opts.vertical else (1920, 1080)
    dur = clip.duration
    d = opts.transition_seconds
    f = []

    src = "[0:v]setpts=PTS-STARTPTS"
    if opts.mirror:
        src += ",hflip"
    if opts.color_boost:
        src += ",eq=contrast=1.06:saturation=1.18:brightness=0.01"
    if opts.vertical:
        f.append(f"{src},split=2[bgsrc][fgsrc]")
        f.append(f"[bgsrc]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                 f"gblur=sigma=28,eq=brightness=-0.12[bg]")
        f.append(f"[fgsrc]scale={W}:-2[fg]")
        f.append(f"[bg][fg]overlay=(W-w)/2:(H-h)/2-{int(H * 0.04)},"
                 f"fps={FPS},format=yuv420p,settb=AVTB[base]")
    else:
        f.append(f"{src},scale={W}:{H}:force_original_aspect_ratio=decrease,"
                 f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={FPS},format=yuv420p,settb=AVTB[base]")

    last = "base"
    if opts.transitions and cuts:
        n = len(cuts) + 1
        f.append(f"[base]split={n}" + "".join(f"[s{i}]" for i in range(n)))
        bounds = [0.0] + cuts + [dur]
        for i in range(n):
            a = 0.0 if i == 0 else bounds[i] - d
            b = bounds[i + 1]
            z = ZOOMS[i % len(ZOOMS)]
            zoom = "" if z == 1.0 else (f",crop=trunc(iw/{z}/2)*2:trunc(ih/{z}/2)*2,"
                                         f"scale={W}:{H},setsar=1")
            f.append(f"[s{i}]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS{zoom}[p{i}]")
        cur = "p0"
        for i in range(1, n):
            tr = TRANSITIONS[(clip.index + i) % len(TRANSITIONS)]
            if opts.reverse_transitions:
                tr = REVERSED.get(tr, tr)
            out = f"x{i}"
            f.append(f"[{cur}][p{i}]xfade=transition={tr}:duration={d:.3f}:offset={cuts[i - 1] - d:.3f}[{out}]")
            cur = out
        last = cur

    post = f"[{last}]fade=t=in:st=0:d=0.25,fade=t=out:st={max(0, dur - 0.35):.3f}:d=0.35"
    # barra de progreso inferior (retiene la atención)
    post += (f",drawbox=x=0:y=ih-{int(H * 0.006)}:w='iw*t/{dur:.3f}':h={int(H * 0.006)}"
             f":color=0xFFE500@0.9:t=fill")
    if ass_name:
        post += f",ass={ass_name}"
    f.append(post + "[vout]")

    if audio:
        f.append(f"[0:a]asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.15,"
                 f"afade=t=out:st={max(0, dur - 0.35):.3f}:d=0.35,"
                 f"loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[aout]")
    return ";\n".join(f), (W, H)


def render_clip(source: str, clip: Clip, words: List[dict], snap: PauseSnapper, opts,
                clips_dir: str, log: Log) -> str:
    os.makedirs(clips_dir, exist_ok=True)
    name = f"{clip.kind}_{clip.index:03d}"
    out_file = f"{name}.mp4"
    if os.path.exists(os.path.join(clips_dir, out_file)):
        return out_file

    W, H = (1080, 1920) if opts.vertical else (1920, 1080)
    ass_name = ""
    hook = HOOKS[clip.kind].format(i=clip.index) if opts.hook_title else ""
    if opts.subtitles or hook:
        ass_name = f"{name}.ass"
        with open(os.path.join(clips_dir, ass_name), "w", encoding="utf-8") as fh:
            fh.write(build_ass(words if opts.subtitles else [], clip.start, clip.end, W, H,
                               font=opts.font, per_line=opts.words_per_line, hook=hook))

    audio = has_audio(source)
    cuts = _cut_points(clip, snap, opts.segment_seconds, opts.transition_seconds) if opts.transitions else []
    graph, _ = build_filter(clip, opts, cuts, ass_name, audio)
    script = os.path.join(clips_dir, f"{name}.filter.txt")
    with open(script, "w", encoding="utf-8") as fh:
        fh.write(graph)

    tmp = f"{name}.part.mp4"
    cmd = [require("ffmpeg"), "-y", "-hide_banner", "-loglevel", "error",
           "-ss", f"{clip.start:.3f}", "-t", f"{clip.duration:.3f}", "-i", os.path.abspath(source),
           "-filter_complex_script", f"{name}.filter.txt", "-map", "[vout]"]
    if audio:
        cmd += ["-map", "[aout]", "-c:a", "aac", "-b:a", "160k"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-r", str(FPS), "-movflags", "+faststart", "-t", f"{clip.duration:.3f}", "-f", "mp4", tmp]
    run(cmd, log=log, cwd=clips_dir)
    os.replace(os.path.join(clips_dir, tmp), os.path.join(clips_dir, out_file))
    for extra in (script,):
        try:
            os.remove(extra)
        except OSError:
            pass
    return out_file
