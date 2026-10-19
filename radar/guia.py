"""Guía para la acción: convierte cada activo y cada noticia del calendario en un plan con opción de entrada o de NO entrada.

Reglas (las mismas ideas probadas en el laboratorio del proyecto Trading; nada se inventa, todo sale de las velas):
  - Tendencia de fondo: precio sobre / bajo su media de 200 días (diaria).
  - Tendencia de corto plazo: Supertrend 10/3 en velas de 4h.
  - Gatillo de COMPRA: cierre de una vela de 4h por encima del máximo de las 20 velas de 4h anteriores (Donchian 20).
    Gatillo de VENTA: cierre por debajo del mínimo de esas 20 velas.
  - Stop: la línea del Supertrend de 4h si está del lado correcto; si no, 2 ATR de 4h desde el gatillo.
  - Objetivo: 2 veces el riesgo (2R).
  - Estado de cada lado: "posible" si las dos tendencias acompañan; "cautela" si solo una; "no" si ninguna.
Noticias: un dato mejor que la previsión fortalece la moneda; se traduce a la dirección de cada activo relacionado y se cruza
con el plan técnico. Si la reacción esperada va contra la tendencia, la guía dice NO ENTRAR y por qué.
Precios de Yahoo (futuros continuos y divisas al contado): pueden diferir unos puntos del bróker.
"""
from datetime import datetime, timezone

# moneda → activos del tablero y signo de su movimiento cuando la moneda se FORTALECE
MAPA = {
    "USD": [("XAUUSD", -1), ("EURUSD", -1), ("USDJPY", +1)],
    "EUR": [("EURUSD", +1)], "GBP": [("GBPUSD", +1)], "JPY": [("USDJPY", -1)], "CAD": [("USDCAD", -1)],
    "AUD": [("AUDUSD", +1)], "NZD": [("NZDUSD", +1)], "CHF": [("USDCHF", -1)], "CNY": [("AUDUSD", +1), ("COBRE", +1)],
}
NOMBRE_MONEDA = {"USD": "dólar", "EUR": "euro", "GBP": "libra", "JPY": "yen", "CAD": "dólar canadiense",
                 "AUD": "dólar australiano", "NZD": "dólar neozelandés", "CHF": "franco suizo", "CNY": "yuan"}


def _r(v):
    return None if v is None else float(f"{v:.6g}")


def lado(a, sentido):
    """Plan de compra (sentido=+1) o venta (-1) de un activo con sus niveles. None si faltan datos."""
    n = a.get("niveles") or {}
    gat = n.get("donchian_alto" if sentido > 0 else "donchian_bajo")
    atr4, st, u = n.get("atr_4h"), n.get("st_4h"), a.get("ultimo")
    if gat is None or atr4 is None or u is None:
        return None
    st_ok = st is not None and n.get("st_dir") == ("alcista" if sentido > 0 else "bajista") and (st - gat) * sentido < 0
    stop = st if st_ok else gat - sentido * 2 * atr4
    riesgo = abs(gat - stop)
    if riesgo <= 0:
        return None
    a_favor = [t for t, v in (("diaria", a.get("tend_diaria")), ("4h", a.get("tend_4h")))
               if v == ("alcista" if sentido > 0 else "bajista")]
    estado = "posible" if len(a_favor) == 2 else "cautela" if a_favor else "no"
    ya_roto = (u - gat) * sentido > 0
    return {"accion": "compra" if sentido > 0 else "venta", "gatillo": _r(gat), "stop": _r(stop),
            "stop_es": "Supertrend 4h" if st_ok else "2 ATR de 4h", "objetivo": _r(gat + sentido * 2 * riesgo),
            "riesgo_pct": round(riesgo / gat * 100, 2), "distancia_pct": round((gat / u - 1) * 100, 2),
            "distancia_atr": round(abs(gat - u) / atr4, 1), "ya_roto": ya_roto, "estado": estado, "a_favor": a_favor}


def plan_activo(a):
    """Sesgo del activo y sus dos planes (compra y venta)."""
    d, h = a.get("tend_diaria"), a.get("tend_4h")
    if d and h and d == h:
        sesgo = "compras" if d == "alcista" else "ventas"
    elif d and h:
        sesgo = "esperar"
    else:
        sesgo = None
    return {"sesgo": sesgo, "compra": lado(a, +1), "venta": lado(a, -1)}


def _reaccion(g, t):
    """% de cambio del activo desde la última vela de 1h anterior al dato hasta la última disponible."""
    h1 = (g or {}).get("h1") or []
    antes = [c for ts, c in h1 if datetime.strptime(ts, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc).timestamp() <= t]
    if not antes or not h1 or h1[-1][1] is None or not antes[-1]:
        return None
    return round((h1[-1][1] / antes[-1] - 1) * 100, 2)


def plan_evento(e, activos, graficos):
    """Para una noticia: por cada activo relacionado, qué hacer si el dato sale mejor o peor que la previsión."""
    pares = list(MAPA.get(e.get("moneda"), []))
    if e.get("moneda") == "USD" and e.get("familia") in ("Inflación", "Fed"):
        pares.append(("US500", -1))  # inflación o Fed duros → índices bajan (estudio F1)
    mon = NOMBRE_MONEDA.get(e.get("moneda"), e.get("moneda"))
    salida = []
    for clave, signo in pares:
        a = activos.get(clave)
        if not a or a.get("sin_datos"):
            continue
        esc = []
        for cual, s in (("mejor", signo), ("peor", -signo)):
            p = lado(a, s)
            if p:
                esc.append(dict(p, si=f"dato {cual} que la previsión ({mon} {'fuerte' if cual == 'mejor' else 'débil'})"))
        if not esc:
            continue
        mp = e.get("mejor_peor")
        realizado = None
        if e.get("publicado") and e.get("actual"):
            realizado = "mejor" if mp == 1 else "peor" if mp == 2 else "en línea"
        salida.append({"clave": clave, "nombre": a["nombre"], "ultimo": a["ultimo"], "tend_diaria": a.get("tend_diaria"),
                       "tend_4h": a.get("tend_4h"), "escenarios": esc, "realizado": realizado,
                       "reaccion_pct": _reaccion(graficos.get(clave), e["t"]) if e.get("publicado") else None})
    if not salida:
        return None
    return {"activos": salida, "veredicto": veredicto(salida)}


RANGO = {"posible": 0, "cautela": 1, "no": 2}


def veredicto(salida):
    """La mejor opción del evento (o por qué no hay). Si el dato ya salió, solo cuenta el escenario que se dio.

    nivel: "entrar" (las dos tendencias acompañan), "cautela" (solo una; esperar el gatillo), "no" (ninguna, o dato
    sin sorpresa). lejano: el gatillo está a más de 3 ATR de 4h (improbable en la sesión)."""
    hecho = salida[0].get("realizado")
    if hecho == "en línea":
        return {"nivel": "no", "motivo": "en_linea"}
    cands = [(x, s) for x in salida for s in x["escenarios"] if not hecho or s["si"].startswith(f"dato {hecho}")]
    if not cands:
        return {"nivel": "no", "motivo": "sin_datos"}
    x, s = min(cands, key=lambda c: (RANGO[c[1]["estado"]], c[1]["distancia_atr"]))
    nivel = {"posible": "entrar", "cautela": "cautela", "no": "no"}[s["estado"]]
    return {"nivel": nivel, "motivo": "tendencias" if nivel != "no" else "contra", "clave": x["clave"],
            "nombre": x["nombre"], "accion": s["accion"], "gatillo": s["gatillo"], "stop": s["stop"],
            "objetivo": s["objetivo"], "a_favor": s["a_favor"], "lejano": s["distancia_atr"] > 3,
            "distancia_atr": s["distancia_atr"], "ya_roto": s["ya_roto"], "si": s["si"], "publicado": bool(hecho)}


def texto_evento(e):
    """Resumen en texto plano de la guía de un evento (para el paquete de la IA)."""
    g = e.get("guia")
    if not g:
        return ""
    partes = []
    for x in g["activos"]:
        for s in x["escenarios"]:
            partes.append(f"{x['nombre']}: si {s['si']} → {s['accion']} al cerrar 4h {'sobre' if s['accion'] == 'compra' else 'bajo'} "
                          f"{s['gatillo']} (stop {s['stop']} = {s['stop_es']}, objetivo {s['objetivo']}, "
                          f"a {s['distancia_pct']:+}% del precio) → estado {s['estado'].upper()}")
        if x.get("realizado"):
            partes.append(f"{x['nombre']}: dato salió {x['realizado']}; reacción desde el dato {x.get('reaccion_pct')}%")
    v = g["veredicto"]
    cab = (f"{v['nivel'].upper()}: {v.get('accion', '')} {v.get('nombre', '')} gatillo {v.get('gatillo')}"
           f"{' (lejano, >3 ATR 4h)' if v.get('lejano') else ''}" if v.get("accion") else f"{v['nivel'].upper()} ({v['motivo']})")
    return f"   guía: {cab} | " + " ; ".join(partes)
