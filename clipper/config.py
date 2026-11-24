from dataclasses import dataclass, asdict, fields


@dataclass
class Options:
    # Fuente
    url: str = ""                  # enlace de YouTube o ruta a un archivo local
    workdir: str = "output"
    cookies: str = ""              # cookies.txt opcional (directos con restricción de edad/miembros)
    max_height: int = 1080
    limit_minutes: int = 0         # 0 = todo el directo

    # Qué clips generar
    clip_seconds: int = 60         # duración de los clips "completos" y "destacados"
    short_seconds: int = 20        # duración de los "momentos cortos"
    make_full: bool = True         # cortar TODO el directo en clips de 1 minuto
    max_full_clips: int = 0        # 0 = sin límite
    top_count: int = 0             # destacados de 1 min (0 = automático)
    short_count: int = 0           # momentos cortos (0 = automático)

    # Edición
    vertical: bool = True          # 9:16 para Shorts/TikTok/Reels con fondo desenfocado
    mirror: bool = False           # invertir la imagen (espejo)
    transitions: bool = True       # cortes internos con zoom + transiciones animadas
    reverse_transitions: bool = False  # invertir el sentido de las transiciones
    segment_seconds: float = 10.0  # cada cuánto se hace un corte interno
    transition_seconds: float = 0.45
    color_boost: bool = True       # contraste/saturación ligeramente mejorados
    hook_title: bool = True        # rótulo en los primeros segundos

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
