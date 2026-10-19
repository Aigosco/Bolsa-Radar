"""ARRANQUE COMPLETO del sistema al encender el PC (orden del usuario: "ejecutar bolsa").

Pasos, en orden; cada uno informa y, si falla, los demás siguen:
  1. Abre MetaTrader 5 si no está abierto y espera a que conecte.
  2. Arranca el bot de tendencia (iniciar_bot_tendencia.bat, en su propia ventana) si no está corriendo.
  3. Trae lo último del repo (git pull).
  4. Pone al día la nube: lanza noticias y mercado (con cierre diario si falta el de ayer) y espera a que terminen.
  5. Videos nuevos de Cava (lunes a viernes; recupera los que falten).
  6. Lectura del día con IA, si aún no hay una de hoy.
  7. Publica desde el PC: estado del bot, tesis, radar.
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
GH_REPO = "Aigosco/Bolsa-Radar"
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
            print("MT5 conectado." + ("" if "algo" in r.stdout and "sin-algo" not in r.stdout else
                                      " AVISO: el botón 'Algo Trading' está APAGADO: actívalo en MT5 o el bot no podrá operar."))
            return True
        time.sleep(5)
    print("AVISO: MT5 no respondió en 2 minutos (¿sesión del bróker?). El bot no operará hasta que conecte.")
    return False


def bot():
    r = ps("Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | ? { $_.CommandLine -match 'vivo.tendencia' } "
           "| Select -Expand ProcessId")
    if r.stdout.strip():
        print(f"El bot ya estaba corriendo (proceso {r.stdout.split()[0]}).")
        return
    subprocess.Popen(["cmd", "/c", "start", "Bot tendencia", str(TRADING / "iniciar_bot_tendencia.bat")], cwd=TRADING)
    time.sleep(20)
    log = (TRADING / "registros" / "vivo_tendencia.log").read_text(encoding="utf-8", errors="replace").splitlines()
    print("Bot arrancado en su propia ventana. Últimas líneas del log:")
    print("\n".join(log[-4:]))


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
    paso(2, "Bot de tendencia (demo)")
    try:
        bot()
    except Exception as e:  # noqa: BLE001
        print("fallo:", e)
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
    paso(7, "Publicar desde el PC (bot, tesis, radar)")
    corre(PY, "local/publicar_desde_pc.py", timeout=600)
    paso(8, "Estado")
    corre("gh", "run", "list", "-R", GH_REPO, "--limit", "5")
    print("\nPágina: https://aigosco.github.io/Bolsa-Radar/")
    print("Tareas de Windows activas: videos de Cava (L-V cada hora 7:30-16:30), lectura IA (8:10), publicar (cada hora), respaldo nube (15 min).")


if __name__ == "__main__":
    main()
