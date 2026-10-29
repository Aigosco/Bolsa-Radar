"""ARRANQUE COMPLETO del sistema al encender el PC (orden del usuario: "ejecutar bolsa").

Pasos, en orden; cada uno informa y, si falla, los demás siguen:
  1. Abre MetaTrader 5 si no está abierto y espera a que conecte.
  2. Recuerda la caja 1: sin bots desde el 2026-10-28 (trading supervisado con ETR Edge).
  3. Trae lo último del repo (git pull).
  4. Pone al día la nube: lanza noticias y mercado (con cierre diario si falta el de ayer) y espera a que terminen.
  5. Videos nuevos de Cava (lunes a viernes; recupera los que falten).
  6. Lectura del día con IA, si aún no hay una de hoy.
  7. Publica desde el PC: tesis, radar y cerebro.
  8. Resumen del estado.

  python local/arrancar.py
"""
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TRADING = Path(r"C:\Users\franc\OneDrive\Desktop\Proyectos Python\Trading")
PY = TRADING / ".venv" / "Scripts" / "python.exe"
MT5 = Path(r"C:\Program Files\MetaTrader 5 IC Markets Global\terminal64.exe")
GH_REPO = "inversion-lab/Bolsa-Radar"
HOY_CO = datetime.now().strftime("%Y-%m-%d")   # el PC está en hora de Bogotá


def paso(n, txt):
    print(f"\n=== {n}. {txt}", flush=True)


def ps(cmd):
    return subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True)


def corre(*args, timeout=None, cwd=REPO):
    r = subprocess.run(list(map(str, args)), cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    salida = (r.stdout + r.stderr).strip()
    if salida:
        print("\n".join(salida.splitlines()[-12:]), flush=True)
    return r.returncode


def mt5():
    if "terminal64" in ps("Get-Process terminal64 -ErrorAction SilentlyContinue | Select -Expand Name").stdout:
        print("MT5 ya estaba abierto.")
    else:
        subprocess.Popen([str(MT5)])
        print("MT5 abierto; esperando a que conecte…")
    for _ in range(24):  # hasta 2 minutos
        r = subprocess.run([str(PY), "-c", "import MetaTrader5 as m; ok=m.initialize(); a=m.account_info() if ok else None;"
                            "print('OK' if a else 'NO', 'algo' if ok and m.terminal_info().trade_allowed else 'sin-algo');"
                            "m.shutdown()"], capture_output=True, text=True)
        if r.stdout.startswith("OK"):
            print("MT5 conectado (solo datos para la revista; no hay bots).")
            return True
        time.sleep(5)
    print("AVISO: MT5 no respondió en 2 minutos (¿sesión del bróker?). La revista local saldrá sin datos de MT5.")
    return False


def nube():
    tesis = json.loads((REPO / "datos" / "web" / "tesis.json").read_text(encoding="utf-8")).get("generado", "")
    diario = "true" if tesis[:10] < datetime.now(timezone.utc).strftime("%Y-%m-%d") else "false"
    corre("gh", "workflow", "run", "noticias.yml", "-R", GH_REPO)
    corre("gh", "workflow", "run", "mercado.yml", "-R", GH_REPO, "-f", f"diario={diario}")
    print(f"Lanzados noticias y mercado (cierre diario: {'sí' if diario == 'true' else 'no, ya está'}). Esperando…")
    time.sleep(15)
    ids = subprocess.run(["gh", "run", "list", "-R", GH_REPO, "--limit", "4", "--json", "databaseId,status,workflowName",
                          "-q", '.[] | select(.status != "completed") | .databaseId'], capture_output=True, text=True).stdout.split()
    for i in ids:
        corre("gh", "run", "watch", i, "-R", GH_REPO, "--exit-status", timeout=900)
    corre("git", "pull", "-q", "--rebase", "--autostash", "-X", "theirs")
    print("Nube al día.")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"ARRANQUE Bolsa-Radar · {datetime.now():%Y-%m-%d %H:%M}")
    paso(1, "MetaTrader 5")
    try:
        mt5()
    except Exception as e:  # noqa: BLE001
        print("fallo:", e)
    paso(2, "Caja 1")
    print("Sin bots desde el 2026-10-28: scalp e intradía en vivo con el profesor (ETR Edge). Zoom NY 8:15 a. m. y Asia 7:45 p. m. (Bogotá).")
    paso(3, "Repo al día")
    corre("git", "pull", "-q", "--rebase", "--autostash", "-X", "theirs")
    paso(4, "Nube: noticias, mercado y cierre diario")
    try:
        nube()
    except Exception as e:  # noqa: BLE001
        print("fallo:", e)
    paso(5, "Videos nuevos de Cava")
    if datetime.now().weekday() < 6:  # de lunes a sábado (recupera el del viernes si el PC estuvo apagado)
        corre(PY, "local/cava_diario.py", timeout=3600)
    paso(6, "Lectura del día con IA")
    res = json.loads((REPO / "datos" / "web" / "resumen.json").read_text(encoding="utf-8"))
    gen = datetime.fromisoformat(res["generado"].replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d")
    if gen == HOY_CO and "PC" in res.get("modelo", ""):
        print(f"Ya hay lectura de hoy ({res['generado']}); no se repite.")
    else:
        corre(PY, "local/lectura_ia_pc.py", timeout=1800)
    paso(7, "Publicar desde el PC (tesis, radar, cerebro)")
    corre(PY, "local/publicar_desde_pc.py", timeout=600)
    paso(8, "Estado")
    corre("gh", "run", "list", "-R", GH_REPO, "--limit", "5")
    print("\nPágina: https://inversion-lab.github.io/Bolsa-Radar/")
    print("Tareas de Windows: videos de Cava (L-V 7:20, 8:20, 9:20), lectura IA (8:10), publicar (L-V 7:35, 8:35, 9:35). Respaldo nube desactivado.")


if __name__ == "__main__":
    main()
