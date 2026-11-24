from dataclasses import dataclass, asdict, fields


@dataclass
class Options:
    # Fuente
    url: str = ""                  # enlace de YouTube o ruta a un archivo local
    workdir: str = "output"        # descargas y caché (vídeo original, transcripción)
    clips_dir: str = "CLIPS"       # AQUÍ quedan los clips listos para subir
    cookies: str = ""              # ruta a cookies.txt (si YouTube pide "confirmar que no eres un bot")
    cookies_browser: str = ""      # o leerlas del navegador: chrome / edge / firefox / brave
    max_height: int = 1080
    limit_minutes: int = 0         # 0 = todo el directo

    # Qué clips generar
    # TikTok (Creator Rewards) y Facebook solo monetizan vídeos de MÁS de 1 minuto,
    # así que ningún clip baja de min_seconds.
    min_seconds: int = 61          # duración mínima garantizada de TODOS los clips
    clip_seconds: int = 70         # duración objetivo
    max_seconds: int = 95          # duración máxima (salvo la última parte del directo)
    make_full: bool = True         # cortar TODO el directo en partes de ~1 minuto
    max_full_clips: int = 0        # 0 = sin límite
    top_count: int = 0             # destacados: los minutos con más energía (0 = automático)
    moment_count: int = 0          # momentos: picos cortos ampliados a 1 min con contexto (0 = automático)
    peak_seconds: int = 20         # tamaño de la ventana para detectar picos

    # Edición
    vertical: bool = True          # 9:16 para Shorts/TikTok/Reels con fondo desenfocado
    mirror: bool = False           # invertir la imagen (espejo)
    transitions: bool = True       # cortes internos con zoom + transiciones animadas
    reverse_transitions: bool = False  # invertir el sentido de las transiciones
    segment_seconds: float = 10.0  # cada cuánto se hace un corte interno
    transition_seconds: float = 0.45
    color_boost: bool = True       # contraste/saturación ligeramente mejorados
    hook_title: bool = True        # rótulo en los primeros segundos
    credit: str = ""               # crédito visible todo el clip, p. ej. "Contenido: @alofokeradioshow"

    # Subtítulos
    subtitles: bool = True
    whisper_model: str = "small"   # tiny / base / small / medium / large-v3
    language: str = "es"           # "auto" para detectar el idioma
    font: str = "Arial"
    words_per_line: int = 3

    # Rendimiento
    workers: int = 2

    @classmethod
    def from_dict(cls, d: dict) -> "Options":
        names = {f.name: f.type for f in fields(cls)}
        out = {}
        for k, v in d.items():
            if k not in names:
                continue
            default = getattr(cls, k)
            if isinstance(default, bool):
                v = v if isinstance(v, bool) else str(v).lower() in ("1", "true", "on", "yes", "si", "sí")
            elif isinstance(default, int):
                v = int(float(v or 0))
            elif isinstance(default, float):
                v = float(v or 0)
            out[k] = v
        return cls(**out)

    def to_dict(self) -> dict:
        return asdict(self)
