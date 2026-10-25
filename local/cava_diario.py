"""Videos nuevos de los analistas seguidos (José Luis Cava, Pablo Gil) → transcripción → tesis (Claude Code en el PC)
→ GitHub. Los canales están en CANALES; añadir uno nuevo = una línea más.

Corre EN EL PC (YouTube bloquea a los servidores de GitHub). De lunes a viernes, cada hora de 7:30 a 16:30 Bogotá: Cava
publica entre las 5:00 y las 8:40 Bogotá y YouTube tarda un rato en generar los subtítulos automáticos, así que se
reintenta hasta que aparezcan. "Sin subtítulos todavía" es normal en la primera hora; un bloqueo de YouTube se reporta
aparte ("YouTube bloquea") y detiene la ejecución sin insistir.

  1. Revisa solo los últimos N videos del canal (consulta ligera; nunca listar el canal entero: provocó un bloqueo).
  2. Por cada video sin tesis: baja SOLO la transcripción (sin video) con las funciones del proyecto local. Si YouTube
     aún no generó los subtítulos, baja solo el audio y lo transcribe en el PC con Whisper (fundamental/audio.py).
     Si YouTube bloquea la IP (también el audio), queda la vía manual desde el navegador: fundamental/receptor.py.
  3. Claude Code (plan Pro, Opus) lee la transcripción completa con las mismas reglas que se usaron para los 40 videos
     (fundamental/analistas.py: SISTEMA + ESQUEMA) y devuelve el JSON de tesis.
  4. Comprueba que cada cita existe en la transcripción (las correcciones del reconocimiento de voz van entre corchetes);
     guarda el resultado de esa comprobación en el propio archivo.
  5. Guarda fuentes/cava/<id>/tesis.json en el proyecto local, lo importa a la base local y publica en el repo
     (datos/tesis/cava/<id>.json). La nube lo verifica con precios en su cierre diario y la página lo muestra.

  python local/cava_diario.py [--ultimos 5] [--sin-push] [--video ID]
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TRADING = Path(os.environ.get("TRADING_DIR", r"C:\Users\franc\OneDrive\Desktop\Proyectos Python\Trading"))
sys.path.insert(0, str(TRADING))
sys.path.insert(0, str(REPO / "local"))
from fundamental import analistas as A  # noqa: E402
from fundamental import audio as AU  # noqa: E402
from fundamental import youtube as Y  # noqa: E402

CANALES = {  # autor (carpeta fuentes/<autor>) → canal. Pablo Gil publica ~1 video por semana (desde 2026-10-25)
    "cava": "https://www.youtube.com/@JoseLuisCavatv/videos",
    "pablogil": "https://www.youtube.com/@PabloGilTrader/videos",
}
CLAUDE = shutil.which("claude") or str(Path.home() / ".local" / "bin" / "claude.exe")
NO_HERRAMIENTAS = "Bash,Read,Write,Edit,Glob,Grep,WebFetch,WebSearch,Agent,Task,NotebookEdit"
EXTRA = """
Además:
- La cita debe ser LITERAL de la transcripción (puedes recortar con [...]). Si corriges una palabra mal reconocida, ponla
  entre corchetes: "[Bessent]". No parafrasees dentro de la cita.
- minuto: el del bloque [m:ss] donde empieza la cita.
- simbolo: usa las claves dadas; para acciones, su ticker de Yahoo (MC.PA, AVGO). Niveles en la escala de SU gráfico que
  no correspondan al precio del símbolo (p. ej. "108" en el franco/euro) van en la condición, no en nivel.
- resumen: 4-8 frases con lo que dice y su conclusión; menciona si el video está patrocinado.
- Fecha de hoy: {hoy}. Fechas relativas ("el próximo viernes", "a partir del 3 de noviembre") se convierten a AAAA-MM-DD
  usando la fecha de publicación del video."""


def ultimos(n, canal):
    r = subprocess.run([sys.executable, "-m", "yt_dlp", "--flat-playlist", "--playlist-end", str(n),
                        "--print", "%(id)s|%(title)s", canal], capture_output=True, text=True, encoding="utf-8",
                       timeout=180)
    if "not a bot" in (r.stderr or ""):
        raise RuntimeError("YouTube pide confirmar que no eres un bot: se detiene sin insistir")
    return [ln.split("|", 1) for ln in r.stdout.splitlines() if "|" in ln]


def norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s)).strip()


def comprobar_citas(tesis, transcripcion):
    """Fragmentos de cita (fuera de corchetes, ≥4 palabras) que no aparecen literalmente en la transcripción."""
    etq = re.compile(r"\[[0-9:]+\]\s*(\d+ minutos? y \d+ segundos?|\d+ segundos?|\d+ minutos?)?")
    trans = norm(etq.sub(" ", transcripcion))
    malas = []
    for t in tesis:
        for p in re.split(r"\[[^\]]*\]", t["cita"]):
            q = norm(p)
            if len(q.split()) >= 4 and q not in trans:
                malas.append({"minuto": t["minuto"], "fragmento": p.strip()[:120]})
    return malas


def extraer(carpeta):
    info = json.loads((carpeta / "info.json").read_text(encoding="utf-8"))
    trans = (carpeta / "transcripcion.txt").read_text(encoding="utf-8", errors="replace")
    fecha = str(info.get("fecha_publicacion") or "")[:10]
    entrada = f"Video: {info.get('titulo')} | canal {info.get('canal')} | publicado {fecha}\n\n{trans}"
    sistema = A.SISTEMA + EXTRA.format(hoy=date.today().isoformat())
    r = subprocess.run([CLAUDE, "-p", "--output-format", "json", "--json-schema", json.dumps(A.ESQUEMA),
                        "--system-prompt", sistema, "--disallowedTools", NO_HERRAMIENTAS, "--no-session-persistence"],
                       input=entrada, capture_output=True, text=True, encoding="utf-8", timeout=1800,
                       cwd=os.environ.get("TEMP", str(REPO)))
    salida = json.loads(r.stdout)
    d = salida.get("structured_output")
    if salida.get("is_error") or not isinstance(d, dict) or "tesis" not in d:
        raise RuntimeError(f"extracción inválida: {salida.get('subtype')} {str(salida.get('result'))[:200]}")
    malas = comprobar_citas(d["tesis"], trans)
    modelo = next(iter(salida.get("modelUsage", {}) or {"claude": 0}))
    d.update({"video_id": carpeta.name, "origen": f"claude-code automático ({modelo}, plan Pro)",
              "fecha_extraccion": date.today().isoformat(),
              "comprobacion_citas": {"tesis": len(d["tesis"]), "fragmentos_no_literales": malas}})
    (carpeta / "tesis.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{carpeta.name}: {len(d['tesis'])} tesis · citas no literales: {len(malas)} · "
          f"{salida.get('duration_ms', 0) / 1000:.0f} s")
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ultimos", type=int, default=5)
    ap.add_argument("--video")
    ap.add_argument("--autor", choices=list(CANALES), help="solo este analista (por defecto, todos)")
    ap.add_argument("--sin-push", action="store_true")
    a = ap.parse_args()
    nuevos = 0
    autores = [a.autor] if a.autor else list(CANALES)
    if a.video and len(autores) != 1:
        raise SystemExit("--video necesita --autor")
    lista = []
    for autor in autores:
        try:
            lista += [(autor, vid, t) for vid, t in ([[a.video, ""]] if a.video else ultimos(a.ultimos, CANALES[autor]))]
        except RuntimeError as ex:
            print(f"{autor}: {ex}")
            break
    for autor, vid, titulo in lista:
        carpeta = TRADING / "fuentes" / autor / vid
        if (carpeta / "tesis.json").exists():
            continue
        if not (carpeta / "transcripcion.txt").exists():
            try:
                res, ok = Y.bajar(vid, carpeta)
            except Y.Bloqueo as ex:
                print(f"{vid}: YouTube bloquea ({ex}); se detiene sin insistir")
                break
            if ok:
                print(f"{vid}: transcripción bajada · {res.get('fecha_publicacion')} · {res.get('titulo')}")
            else:  # plan B: bajar solo el audio y transcribirlo en el PC con Whisper (~8 min por video)
                print(f"{vid}: sin subtítulos todavía; se transcribe el audio con Whisper…", flush=True)
                try:
                    res, seg = AU.transcribir(vid, carpeta)
                    print(f"{vid}: audio transcrito en {seg:.0f} s · {res.get('titulo')}")
                except AU.Bloqueo as ex:
                    print(f"{vid}: YouTube bloquea también el audio ({str(ex)[:80]}); se reintentará en la próxima ejecución")
                    break
                except Exception as ex:  # noqa: BLE001
                    print(f"{vid}: falló la transcripción por audio ({ex}); se reintentará en la próxima ejecución")
                    continue
        try:
            extraer(carpeta)
            nuevos += 1
        except Exception as ex:  # noqa: BLE001 — un video fallido no impide los demás
            print(f"{vid}: fallo en la extracción ({ex})")
    print(f"videos nuevos analizados: {nuevos}")
    if nuevos:
        A.importar()               # base local del proyecto Trading (para la revista y el Excel); todos los autores
        A.verificar()
        A.informe()
        import publicar_desde_pc as P
        P.tesis()
        if not a.sin_push:
            P.git_push()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
