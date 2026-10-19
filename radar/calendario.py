"""Calendario económico de Forex Factory → datos/calendario/AAAA-MM.json y datos/web/agenda.json.

Se ejecuta cada hora: así entran los datos reales poco después de publicarse. Guarda el mes en curso (y el siguiente
desde el día 25). Los valores numéricos se derivan del texto de Forex Factory sin inventar nada.
El efecto histórico por familia (estudio F1, calculado en el PC con velas de 5 min) se lee de datos/f1_efecto.json.

  python -m radar.calendario
"""
import json
import re
import sys
from datetime import datetime, timedelta, timezone

import requests

from .comun import DATOS, UA, WEB, ahora_utc, guardar_json, iso, leer_json

URL = "https://www.forexfactory.com/calendar?month={}"
MESES = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
MULT = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}
FAMILIAS = [  # misma clasificación que el estudio F1 (fundamental/reaccion.py del proyecto local)
    ("Fed", ["Federal Funds Rate", "FOMC Statement", "FOMC Press Conference", "FOMC Meeting Minutes", "Powell", "Warsh"]),
    ("Empleo", ["Non-Farm Employment Change", "Unemployment Rate", "Average Hourly Earnings", "ADP Non-Farm",
                "Unemployment Claims", "JOLTS"]),
    ("Inflación", ["CPI", "PPI", "PCE"]),
    ("Actividad", ["ISM", "Retail Sales", "PMI", "GDP", "UoM", "Durable", "Consumer Confidence"]),
]


def familia(nombre):
    for fam, pats in FAMILIAS:
        if any(p.lower() in nombre.lower() for p in pats):
            return fam
    return "Otros"


def numero(s):
    if not s:
        return None
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*([KMBT]?)\s*%?", s.strip().replace(",", ""))
    return float(m.group(1)) * MULT.get(m.group(2), 1) if m else None


def extraer(html):
    i = html.find("window.calendarComponentStates[1]")
    if i < 0:
        raise ValueError("no aparece calendarComponentStates (¿bloqueo o cambio de la página?)")
    k = html.find("[", html.find("days:", i))
    dias, _ = json.JSONDecoder().raw_decode(html[k:])
    return [e for d in dias for e in d.get("events", [])]


def evento(e):
    a, p, an = (e.get(k, "") or "" for k in ("actual", "forecast", "previous"))
    t = int(e["dateline"])
    return {"id": e["id"], "t": t, "fecha_utc": datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
            "moneda": e.get("currency"), "impacto": e.get("impactName"), "nombre": e.get("name"),
            "hora_oculta": bool(e.get("timeMasked")), "actual": a, "previsto": p, "anterior": an,
            "revision": e.get("revision") or "", "actual_n": numero(a), "previsto_n": numero(p),
            "mejor_peor": e.get("actualBetterWorse"), "url": e.get("url") or e.get("soloUrl")}


def descargar_mes(y, m):
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    r = s.get(URL.format(f"{MESES[m - 1]}.{y}"), timeout=60)
    r.raise_for_status()
    ev = [evento(e) for e in extraer(r.content.decode("cp1252", errors="replace"))]
    guardar_json(DATOS / "calendario" / f"{y}-{m:02d}.json", {"descargado": iso(ahora_utc()), "eventos": ev},
                 compacto=True)
    print(f"{y}-{m:02d}: {len(ev)} eventos")
    return ev


def eventos_de(y, m):
    return (leer_json(DATOS / "calendario" / f"{y}-{m:02d}.json", {}) or {}).get("eventos", [])


def web():
    ahora = ahora_utc()
    meses = {(ahora.year, ahora.month), ((ahora + timedelta(days=8)).year, (ahora + timedelta(days=8)).month),
             ((ahora - timedelta(days=2)).year, (ahora - timedelta(days=2)).month)}
    ev = {e["id"]: e for y, m in meses for e in eventos_de(y, m)}.values()
    t0, t1 = int((ahora - timedelta(hours=24)).timestamp()), int((ahora + timedelta(days=7)).timestamp())
    efecto = leer_json(DATOS / "f1_efecto.json", {}) or {}
    sel = []
    for e in sorted(ev, key=lambda x: x["t"]):
        if not (t0 <= e["t"] <= t1) or (e["impacto"] or "").lower() not in ("high", "medium"):
            continue
        fam = familia(e["nombre"]) if e["moneda"] == "USD" else None
        x = dict(e, familia=fam, publicado=e["t"] <= ahora.timestamp(),
                 sorpresa=(round(e["actual_n"] - e["previsto_n"], 4)
                           if e["actual_n"] is not None and e["previsto_n"] is not None else None))
        if fam and (e["impacto"] or "").lower() == "high":
            x["efecto"] = efecto.get(fam)
        sel.append(x)
    guardar_json(WEB / "agenda.json", {"generado": iso(ahora), "eventos": sel,
                                       "nota_efecto": (efecto or {}).get("_nota")}, compacto=True)
    print(f"web/agenda.json: {len(sel)} eventos (24 h atrás → 7 días)")


def main():
    ahora = ahora_utc()
    meses = [(ahora.year, ahora.month)]
    sig = ahora.replace(day=1) + timedelta(days=32)
    if ahora.day >= 25:
        meses.append((sig.year, sig.month))
    for y, m in meses:
        try:
            descargar_mes(y, m)
        except Exception as ex:  # noqa: BLE001 — se usa lo último guardado
            print(f"{y}-{m:02d}: fallo {ex}")
    web()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
