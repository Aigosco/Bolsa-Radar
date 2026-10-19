"""Lectura del momento generada EN EL PC con Claude Code (plan Pro del usuario), mientras la API no tiene saldo.

Hace lo mismo que el flujo de la nube (radar/resumen.py): mismo paquete de datos, mismo prompt y mismo esquema JSON,
pero llama a `claude -p --json-schema …` en vez de a la API. Consume del plan Pro, no de créditos de API.

  python local/lectura_ia_pc.py [--sin-push]
Programado a diario a las 8:10 Bogotá (Programador de tareas: "Bolsa-Radar lectura IA").
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "local"))
from radar.comun import DATOS, WEB, guardar_json, iso  # noqa: E402
from radar.resumen import ESQUEMA, SISTEMA, paquete  # noqa: E402

CLAUDE = shutil.which("claude") or str(Path.home() / ".local" / "bin" / "claude.exe")
NO_HERRAMIENTAS = "Bash,Read,Write,Edit,Glob,Grep,WebFetch,WebSearch,Agent,Task,NotebookEdit"


def git(*a):
    return subprocess.run(["git", "-C", str(REPO), *a], capture_output=True, text=True)


def main(push=True, forzar=False):
    git("pull", "-q", "--rebase", "--autostash", "-X", "theirs")  # datos frescos de la nube
    ahora = datetime.now(timezone.utc)
    previa = json.loads((WEB / "resumen.json").read_text(encoding="utf-8")) if (WEB / "resumen.json").exists() else {}
    if not forzar and previa.get("generado") and "PC" in previa.get("modelo", ""):
        dia = datetime.fromisoformat(previa["generado"].replace("Z", "+00:00")).astimezone().date()
        if dia == datetime.now().date():
            print(f"Ya hay lectura de hoy ({previa['generado']}); no se repite (usa --forzar para rehacerla).")
            return 0
    txt = paquete()
    ruta = DATOS / "resumen" / f"paquete_{ahora:%Y-%m-%d_%H}.md"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(txt, encoding="utf-8")
    print(f"paquete: {ruta.name} ({len(txt)} caracteres)")
    r = subprocess.run([CLAUDE, "-p", "--output-format", "json", "--json-schema", json.dumps(ESQUEMA),
                        "--system-prompt", SISTEMA, "--disallowedTools", NO_HERRAMIENTAS, "--no-session-persistence"],
                       input=txt, capture_output=True, text=True, encoding="utf-8", timeout=1200,
                       cwd=os.environ.get("TEMP", str(REPO)))
    try:
        salida = json.loads(r.stdout)
    except json.JSONDecodeError:
        print("Claude Code no devolvió JSON:", (r.stdout or r.stderr)[-500:])
        return 1
    d = salida.get("structured_output")
    if salida.get("is_error") or not isinstance(d, dict) or not all(k in d for k in ESQUEMA["required"]):
        print("Lectura inválida:", salida.get("subtype"), str(salida.get("result"))[:300])
        return 1
    uso = salida.get("usage", {})
    modelo = next(iter(salida.get("modelUsage", {}) or {"claude": 0}))
    d.update({"generado": iso(ahora), "modelo": f"{modelo} (Claude Code en el PC, plan Pro)", "paquete": ruta.name,
              "tokens": {"entrada": uso.get("input_tokens", 0) + uso.get("cache_creation_input_tokens", 0)
                         + uso.get("cache_read_input_tokens", 0), "salida": uso.get("output_tokens")}})
    guardar_json(WEB / "resumen.json", d)
    print(f"web/resumen.json · {modelo} · tokens {d['tokens']} · {salida.get('duration_ms', 0) / 1000:.0f} s")
    if push:
        git("add", "datos/web/resumen.json", "datos/resumen")
        git("commit", "-q", "-m", f"lectura IA (PC) {ahora:%Y-%m-%dT%H:%MZ}")
        for _ in range(3):
            git("pull", "-q", "--rebase", "--autostash", "-X", "theirs")
            p = git("push", "-q")
            if p.returncode == 0:
                print("push OK")
                return 0
        print("push FALLÓ:", p.stderr[-300:])
        return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--sin-push", action="store_true")
    ap.add_argument("--forzar", action="store_true")
    a = ap.parse_args()
    sys.exit(main(push=not a.sin_push, forzar=a.forzar))
