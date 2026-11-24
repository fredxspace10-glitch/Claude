# LiveClipper

Convierte un directo de YouTube en muchos clips listos para publicar:

| Tipo | Qué es |
|---|---|
| **Todo el directo** | El directo entero cortado en partes de ~1 minuto (los cortes caen en pausas, no a mitad de frase). |
| **Destacados** | Los minutos con más energía: picos de volumen, habla rápida, palabras como "increíble", "jajaja"… y, si el directo ya terminó, los picos de mensajes en el chat. |
| **Momentos cortos** | Fragmentos de ~20 s de los mejores momentos, para tener todavía más contenido. |

Cada clip se edita para que sea distinto del original:

- **Subtítulos automáticos** (Whisper) estilo Shorts/TikTok, con la palabra que se está diciendo resaltada en amarillo.
- **Formato vertical 9:16** con fondo desenfocado (u horizontal 16:9).
- **Cortes internos con zoom** cada ~10 s y **transiciones animadas** (deslizar, círculo, flash blanco, zoom, píxeles…). Opción para **invertir las transiciones**.
- **Invertir imagen (espejo)**, mejora de color, rótulo inicial ("MOMENTO TOP #1"), barra de progreso, audio normalizado a -14 LUFS.
- Un archivo `clips.json` con el título sugerido, la transcripción y el enlace al minuto exacto del directo original para cada clip.

## Instalación (en tu computadora)

1. Instala **Python 3.10+** y **ffmpeg**:
   - Windows: `winget install Gyan.FFmpeg`
   - macOS: `brew install ffmpeg`
   - Linux: `sudo apt install ffmpeg`
2. En la carpeta del proyecto:
   ```bash
   python -m venv .venv
   # Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
   pip install -r requirements.txt
   ```

## Uso

### Interfaz web
```bash
python app.py
```
Abre http://localhost:5000. El enlace del directo ya viene escrito; pulsa **Crear clips**. Puedes ver y descargar los clips desde la página a medida que se van creando.

### Terminal
```bash
python cli.py "https://www.youtube.com/live/Dxi1CRQMQZo"
# ejemplos de opciones
python cli.py "https://www.youtube.com/live/Dxi1CRQMQZo" --limit-minutes 30 --mirror --reverse-transitions
python cli.py "https://www.youtube.com/live/Dxi1CRQMQZo" --no-make-full --top-count 10 --short-count 30
python cli.py mi_video.mp4            # también funciona con un archivo local
```
`python cli.py --help` muestra todas las opciones.

Los resultados se guardan en `output/<id_del_video>/clips/`. Si lo vuelves a ejecutar, reutiliza la descarga, la transcripción y los clips que ya existan.

## Consejos

- **Tiempo**: un directo de 2 horas genera ~120 partes de 1 minuto y tarda bastante. Para probar, usa `--limit-minutes 10`, o desactiva "Todo el directo" y quédate solo con destacados y momentos cortos.
- **Subtítulos**: el modelo `small` es un buen equilibrio. Con tarjeta gráfica NVIDIA puedes usar `large-v3`. El modelo se descarga la primera vez.
- **Directo en curso**: si el directo sigue en emisión, se descarga desde el principio hasta el momento actual.
- **Error "Sign in to confirm you're not a bot"**: exporta tus cookies de YouTube a `cookies.txt` (con una extensión como "Get cookies.txt LOCALLY") y usa `--cookies cookies.txt`. Si falla la descarga, actualiza yt-dlp con `pip install -U yt-dlp`.

## Aviso legal

Usa esta herramienta con tus propios directos o con permiso del creador. Recortar y volver a subir contenido ajeno puede provocar reclamaciones de derechos de autor, aunque esté editado.
