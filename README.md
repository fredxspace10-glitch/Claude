# LiveClipper

Convierte un directo de YouTube en muchos clips **de más de 1 minuto** (lo mínimo para monetizar en TikTok y Facebook), con subtítulos automáticos, transiciones y formato vertical.

## Cómo empezar (Windows)

1. Instala **Python** desde https://www.python.org/downloads/ y marca la casilla **"Add python.exe to PATH"**.
2. Descarga este proyecto (botón verde **Code → Download ZIP** en GitHub) y descomprímelo.
3. Haz **doble clic en `INICIAR.bat`**. La primera vez instala lo necesario (ffmpeg, Deno y las librerías) y tarda unos minutos.
4. Se abre http://localhost:5000 en el navegador con tu directo ya escrito. Pulsa **Crear clips**.

En macOS/Linux, ejecuta `./iniciar.sh`.

## ¿Dónde están los clips?

En la carpeta **`CLIPS`** que se crea dentro del proyecto, en una subcarpeta con el nombre del directo:

```
CLIPS/
└── LA CASA DE ALOFOKE 3 (GRAN PREMIER DIA 1) [Dxi1CRQMQZo]/
    ├── 1_destacados/        ← los mejores minutos (súbelos primero)
    ├── 2_momentos/          ← reacciones, risas, gritos… con contexto
    ├── 3_directo_completo/  ← TODO el directo en partes de ~1 minuto
    └── PUBLICAR.txt         ← título, descripción y hashtags de cada clip
```

En la página web también tienes los botones **Abrir carpeta** y **Descargar todo (ZIP)**, y puedes ver y descargar cada clip por separado.

## Qué clips genera

Todos duran **mínimo 61 segundos** (por defecto entre 61 y 95 s). Los cortes caen en pausas del habla, nunca a mitad de una frase.

| Carpeta | Qué contiene |
|---|---|
| **1_destacados** | Los minutos con más energía: subidas de volumen, habla rápida, palabras como "increíble" o "jajaja" y, si el directo ya terminó, los picos de mensajes en el chat. |
| **2_momentos** | Picos cortos (una reacción, un grito, una risa) ampliados a más de 1 minuto, empezando unos segundos antes para que se entienda lo que pasa. |
| **3_directo_completo** | El directo entero, parte por parte, para no perder ningún momento. |

## Edición de cada clip

- **Subtítulos automáticos** (Whisper) estilo TikTok, con la palabra que se está diciendo resaltada en amarillo.
- **Vertical 9:16** con fondo desenfocado (u horizontal 16:9).
- **Zoom cada ~10 s** y **transiciones animadas** (deslizar, círculo, flash blanco, zoom, píxeles…), con la opción de **invertir las transiciones**.
- **Crédito visible** del creador en la esquina durante todo el clip y en la descripción (campo "Crédito", p. ej. `Contenido: @alofoke`), como suelen exigir los programas de clippers.
- **Invertir la imagen (espejo)**, mejora de color, rótulo inicial ("MOMENTO TOP #1"), barra de progreso y audio con el volumen igualado (-14 LUFS).

## Uso por terminal

```bash
python cli.py "https://www.youtube.com/live/Dxi1CRQMQZo"
python cli.py "https://www.youtube.com/live/Dxi1CRQMQZo" --limit-minutes 30 --mirror --reverse-transitions
python cli.py "https://www.youtube.com/live/Dxi1CRQMQZo" --no-make-full --top-count 10 --moment-count 30
python cli.py "https://www.youtube.com/live/Dxi1CRQMQZo" --min-seconds 90 --clip-seconds 100 --max-seconds 150
python cli.py "https://www.youtube.com/live/Dxi1CRQMQZo" --credit "Contenido: @alofoke"
python cli.py mi_video.mp4        # también funciona con un vídeo de tu PC
```
`python cli.py --help` muestra todas las opciones.

## Consejos

- **Directos largos**: un directo de 10 horas son unas 500 partes de 1 minuto y tarda horas. Para empezar, desmarca "Todo el directo" (solo destacados y momentos) o usa "Solo primeros N min".
- **Directo en curso**: se descarga desde el principio hasta el momento actual. Vuelve a ejecutarlo más tarde para incluir lo nuevo.
- **"Sign in to confirm you're not a bot"**: en la web, elige tu navegador en **Cookies del navegador** (tienes que haber iniciado sesión en YouTube en él), o usa `--cookies-browser chrome`. Si sigue fallando, actualiza con `pip install -U "yt-dlp[default]"`.
- **Subtítulos**: el modelo `small` es un buen equilibrio. Con tarjeta gráfica NVIDIA puedes usar `large-v3`.
- Si lo vuelves a ejecutar, se reutilizan la descarga, la transcripción y los clips ya hechos.

## Monetización y derechos de autor

TikTok (Creator Rewards) y Facebook solo pagan por **contenido original**. Si el directo no es tuyo, volver a subirlo aunque esté editado suele dar "contenido no original" (sin monetización) o reclamaciones de copyright. Úsalo con tus propios directos o con permiso por escrito del creador. Muchos canales grandes tienen programas oficiales de clippers.
