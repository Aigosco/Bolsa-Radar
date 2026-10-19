"""Se ejecuta EN EL PC (no en la nube): publica en el repo lo que solo existe localmente y hace commit + push.

  - datos/tesis/<autor>/<id>.json   tesis de analistas (sin transcripciones: tienen derechos de autor)
  - datos/f1_efecto.json            efecto histórico de las noticias USD (estudio F1, velas de 5 min de MT5)
  - datos/web/bot.json              estado del bot de tendencia SIN datos de la cuenta (ni número, ni balance, ni USD):
                                    solo símbolos, niveles, R y distancia a la señal
  - datos/web/radar.json            radar de valor del S&P 500 (las listas principales)
  - datos/titulares/AAAA/MM/DD.jsonl  (solo con --historico) titulares ya capturados en el PC, para no perderlos

  python local/publicar_desde_pc.py [--historico] [--sin-push]
Variable TRADING_DIR = carpeta del proyecto local (por defecto la de OneDrive).
"""
import argparse
import json
import os
import sqlite3
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TRADING = Path(os.environ.get("TRADING_DIR", r"C:\Users\franc\OneDrive\Desktop\Proyectos Python\Trading"))
sys.path.insert(0, str(REPO))
from radar.comun import clave, es_grande, guardar_json, iso, limpiar  # noqa: E402


def tesis():
    n = 0
    for f in (TRADING / "fuentes").glob("*/*/tesis.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        info = json.loads((f.parent / "info.json").read_text(encoding="utf-8"))
        d.update({"titulo": info.get("titulo"), "canal": info.get("canal"),
                  "fecha": str(info.get("fecha_publicacion") or "")[:10]})
        guardar_json(REPO / "datos" / "tesis" / f.parent.parent.name / f"{d['video_id']}.json", d)
        n += 1
    print(f"tesis: {n} videos")


def f1():
    import pandas as pd
    p = TRADING / "registros" / "fundamental_F1.xlsx"
    x = pd.ExcelFile(p)
    s = pd.read_excel(x, "Sorpresa total")
    m = pd.read_excel(x, [n for n in x.sheet_names if n.startswith("Tama")][0])
    out = {"_nota": "Estudio F1 (sep-2023 → oct-2026): % de veces que el activo se movió 'de libro' (dato bueno para el "
                    "USD → oro baja; inflación caliente → índices bajan) y movimiento absoluto mediano / p90 en 1 h."}
    for fam in ("Fed", "Empleo", "Inflación", "Actividad"):
        out[fam] = {}
        for a in ("XAUUSD", "XAGUSD", "US500", "USTEC", "BTCUSD"):
            g = s[(s["familia"] == fam) & (s["activo"] == a)].set_index("horizonte")
            mm = m[(m["familia"] == fam) & (m["activo"] == a)]
            if g.empty:
                continue
            out[fam][a] = {"libro_15m": round(float(g["%_direccion_de_libro"].get("15m")), 3),
                           "libro_1h": round(float(g["%_direccion_de_libro"].get("1h")), 3),
                           "mov_1h": round(float(mm["mediana_|mov|_1h_%"].iloc[0]), 3) if len(mm) else None,
                           "p90_1h": round(float(mm["p90_|mov|_1h_%"].iloc[0]), 3) if len(mm) else None}
    guardar_json(REPO / "datos" / "f1_efecto.json", out)
    print("f1_efecto.json")


def bot():
    """Lee MT5 en el PC con las mismas funciones del bot y publica solo niveles y R (nada de la cuenta)."""
    sys.path.insert(0, str(TRADING))
    import MetaTrader5 as mt5
    from bot import datos
    from vivo import tendencia as T
    from fundamental import revista as R
    if not mt5.initialize():
        print("bot: MT5 no disponible; no se publica")
        return
    est = json.loads((TRADING / "registros" / "vivo_tendencia_estado.json").read_text(encoding="utf-8"))
    pos = []
    for p in (mt5.positions_get() or []):
        if p.magic != T.MAGIC:
            continue
        reg = est.get("posiciones", {}).get(str(p.identifier)) or est.get("posiciones", {}).get(str(p.ticket)) or {}
        r1 = (p.price_open - (reg.get("sl0") or p.sl)) or None
        pos.append({"simbolo": p.symbol, "tipo": "compra" if p.type == 0 else "venta", "entrada": p.price_open,
                    "stop": p.sl, "precio": p.price_current, "estrategia": reg.get("estrategia"),
                    "desde": reg.get("hora_entrada"),
                    "R": round((p.price_current - p.price_open) / r1, 2) if r1 else None})
    senales = [{"simbolo": a, "estrategia": b, "cierre_4h": c, "distancia": d}
               for a, b, c, d in R.cerca_de_senal((mt5, None)) + R.cerca_de_senal((mt5, None), candidatas=True)]
    cerradas = []
    ops = TRADING / "registros" / "vivo_tendencia_operaciones.csv"
    if ops.exists():
        import pandas as pd
        c = pd.read_csv(ops)
        cerradas = [{"simbolo": r.simbolo, "entrada": r.hora_entrada, "salida": r.hora_salida, "motivo": r.motivo,
                     "R": r.R} for r in c.tail(20).itertuples()]
    guardar_json(REPO / "datos" / "web" / "bot.json", {
        "generado": iso(datetime.now(timezone.utc)), "version": T.VERSION, "modo": "demo",
        "estrategias": {s: v[0] for s, v in T.ESTRATEGIAS.items()}, "riesgo_por_operacion_pct": T.RIESGO * 100,
        "posiciones": pos, "senales": senales, "cerradas_R": cerradas,
        "nota": "Precios de MT5 (contado del bróker); sin datos de la cuenta."}, compacto=True)
    print(f"bot.json: {len(pos)} posiciones, {len(senales)} activos vigilados")


def radar():
    import pandas as pd
    p = TRADING / "registros" / "radar_valor.pkl"
    if not p.exists():
        return
    rad = pd.read_pickle(p)
    listas = {}
    for lab in ["1. Barata + calidad + tendencia a favor", "2. Barata + calidad, aún bajista (esperar giro)",
                "3. Barata pero ganancias/ventas cayendo (posible trampa)"]:
        g = rad[rad["lectura"] == lab].sort_values("puntaje_valor", ascending=False).head(15)
        listas[lab] = {"total": int((rad["lectura"] == lab).sum()), "empresas": [
            {"ticker": r["ticker"], "empresa": r["empresa"], "sector": r["sector"],
             "per": None if r["PER"] != r["PER"] else round(float(r["PER"]), 1),
             "per_med_10a": None if r["PER_mediana_10a"] != r["PER_mediana_10a"] else round(float(r["PER_mediana_10a"]), 1),
             "pctl_per": None if r["PER_percentil_10a"] != r["PER_percentil_10a"] else round(float(r["PER_percentil_10a"])),
             "calidad": int(r["puntaje_calidad"]), "ret_6m": round(float(r["ret_6m_%"]), 1),
             "vs_ma200": round(float(r["precio_vs_MA200_%"]), 1)} for r in g.to_dict("records")]}
    guardar_json(REPO / "datos" / "web" / "radar.json", {"generado": iso(datetime.now(timezone.utc)),
                                                          "precios_al": str(rad["fecha_precio"].max()), "listas": listas},
                 compacto=True)
    print("radar.json")


def historico():
    """Titulares capturados en el PC (base local) → archivos diarios del repo, sin duplicar."""
    cx = sqlite3.connect(TRADING / "datos_mercado" / "fundamental.sqlite")
    vistos_p = REPO / "datos" / "titulares" / "vistos.json"
    vistos = json.loads(vistos_p.read_text(encoding="utf-8")) if vistos_p.exists() else {}
    por_dia = defaultdict(list)
    for guid, feed, titulo, resumen, enlace, pub, cap in cx.execute(
            "SELECT guid, feed, titulo, resumen, enlace, publicado_utc, capturado_utc FROM titulares"):
        k = clave(guid or enlace or titulo)
        if k in vistos:
            continue
        medio = titulo.rsplit(" - ", 1)[1].strip() if feed.startswith("google/") and " - " in titulo else feed.split("/")[0]
        t = {"id": k, "feed": feed, "medio": medio, "titulo": titulo.rsplit(" - ", 1)[0] if feed.startswith("google/") else titulo,
             "resumen": limpiar(resumen, 300), "enlace": enlace,
             "publicado": (pub or "").replace(" ", "T") + ("Z" if pub and "Z" not in pub else ""),
             "capturado": (cap or "").replace(" ", "T") + "Z", "grande": es_grande(medio)}
        t.pop("grande")
        vistos[k] = (cap or "")[:10]
        por_dia[(cap or "")[:10]].append(t)
    for dia, filas in por_dia.items():
        f = REPO / "datos" / "titulares" / dia[:4] / dia[5:7] / f"{dia[8:10]}.jsonl"
        f.parent.mkdir(parents=True, exist_ok=True)
        with open(f, "a", encoding="utf-8") as fh:
            for t in filas:
                fh.write(json.dumps(t, ensure_ascii=False) + "\n")
    vistos_p.write_text(json.dumps(vistos, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"histórico: {sum(len(v) for v in por_dia.values())} titulares en {len(por_dia)} días")


def git_push():
    def g(*a):
        return subprocess.run(["git", "-C", str(REPO), *a], capture_output=True, text=True)
    g("add", "datos")
    if g("diff", "--cached", "--quiet").returncode == 0:
        print("sin cambios que subir")
        return
    g("commit", "-m", f"datos del PC {datetime.now():%Y-%m-%d %H:%M}")
    for _ in range(3):
        g("pull", "--rebase", "--autostash", "-X", "theirs")
        r = g("push")
        if r.returncode == 0:
            print("push OK")
            return
    print("push FALLÓ:", r.stderr[-300:])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--historico", action="store_true")
    ap.add_argument("--sin-push", action="store_true")
    a = ap.parse_args()
    for paso in ([historico] if a.historico else []) + [tesis, f1, radar, bot]:
        try:
            paso()
        except Exception as ex:  # noqa: BLE001
            print(f"{paso.__name__}: fallo {ex}")
    if not a.sin_push:
        git_push()
