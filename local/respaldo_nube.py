"""Respaldo de los horarios de GitHub: si mercado no corrió en los últimos 40 min, lo lanza desde el PC.

Desde 2026-10-29 las noticias SOLO corren a las 7, 8 y 9 a. m. (Colombia, L-V) por decisión del equipo: este respaldo
ya no las lanza (antes las relanzaba si pasaban 20 min).

GitHub no disparaba los cron del repo nuevo (comprobado el 2026-10-19). Mientras el PC esté encendido, esta tarea
(cada 15 min) garantiza noticias frescas; la de mercado se lanza si no corrió en 40 min. Si los cron de GitHub ya
funcionan, no hace nada (encuentra ejecuciones recientes).
"""
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone

GH_REPO = "inversion-lab/Bolsa-Radar"


def ultima(flujo):
    r = subprocess.run(["gh", "run", "list", "-R", GH_REPO, "--workflow", flujo, "--limit", "1", "--json", "createdAt"],
                       capture_output=True, text=True)
    d = json.loads(r.stdout or "[]")
    return datetime.fromisoformat(d[0]["createdAt"].replace("Z", "+00:00")) if d else None


def main():
    ahora = datetime.now(timezone.utc)
    for flujo, minutos in (("mercado.yml", 40),):
        u = ultima(flujo)
        if u is None or ahora - u > timedelta(minutes=minutos):
            subprocess.run(["gh", "workflow", "run", flujo, "-R", GH_REPO])
            print(f"{ahora:%H:%M} {flujo}: lanzado (última {u:%H:%M} UTC)" if u else f"{flujo}: lanzado")
        else:
            print(f"{ahora:%H:%M} {flujo}: al día (última {u:%H:%M} UTC)")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
