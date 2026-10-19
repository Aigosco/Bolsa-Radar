"""Guía para la acción: convierte cada activo y cada noticia del calendario en un plan con su probabilidad (alta, media o
baja, según lo medido en el laboratorio G1 del proyecto Trading).

Reglas (las mismas ideas probadas en el laboratorio del proyecto Trading; nada se inventa, todo sale de las velas):
  - Tendencia de fondo: precio sobre / bajo su media de 200 días (diaria).
  - Tendencia de corto plazo: Supertrend 10/3 en velas de 4h.
  - Gatillo de COMPRA: cierre de una vela de 4h por encima del máximo de las 20 velas de 4h anteriores (Donchian 20).
    Gatillo de VENTA: cierre por debajo del mínimo de esas 20 velas.
  - Stop: la línea del Supertrend de 4h si está del lado correcto; si no, 2 ATR de 4h desde el gatillo.
  - Objetivo: 2 veces el riesgo (2R).
  - Estado de cada lado: "posible" si las dos tendencias acompañan; "cautela" si solo una; "no" si ninguna.
  - Probabilidad (laboratorio G1, 2020-2026): ALTA = compra "posible" en oro, plata, BTC, ETH o USD/JPY; MEDIA = compra
    "posible" en índices o petróleo (el precio acompaña; el swap pesa); BAJA = todo lo demás (ventas, compras sin las dos
    tendencias, divisas).
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


GRUPO = {"XAUUSD": "metales", "XAGUSD": "metales", "BTCUSD": "cripto", "ETHUSD": "cripto", "XTIUSD": "energía",
         "XBRUSD": "energía", "US500": "índices", "USTEC": "índices", "US30": "índices", "DE40": "índices",
         "JP225": "índices", "EURUSD": "divisas", "USDJPY": "divisas", "GBPUSD": "divisas", "USDCAD": "divisas",
         "AUDUSD": "divisas", "NZDUSD": "divisas", "USDCHF": "divisas"}
# Laboratorio G1 (proyecto Trading, estrategia/resultados_laboratorio_G1.md; 2020-10 → 2026-10, velas de MT5, con
# costos y swaps de IC): (grupo, lado, estado) → (operaciones, R medio por operación, profit factor).
LAB = {
    ("metales", 1, "posible"): (168, 0.155, 1.24), ("metales", 1, "cautela"): (61, 0.036, 1.05),
    ("metales", 1, "no"): (12, -0.618, 0.33), ("metales", -1, "posible"): (69, -0.080, 0.88),
    ("metales", -1, "cautela"): (88, -0.134, 0.80), ("metales", -1, "no"): (18, -0.324, 0.59),
    ("cripto", 1, "posible"): (150, 0.214, 1.35), ("cripto", 1, "cautela"): (102, 0.010, 1.01),
    ("cripto", 1, "no"): (45, -0.196, 0.74), ("cripto", -1, "posible"): (79, 0.038, 1.06),
    ("cripto", -1, "cautela"): (114, -0.036, 0.95), ("cripto", -1, "no"): (40, -0.066, 0.91),
    ("índices", 1, "posible"): (394, -0.119, 0.84), ("índices", 1, "cautela"): (101, -0.074, 0.90),
    ("índices", 1, "no"): (24, -0.195, 0.76), ("índices", -1, "posible"): (136, -0.087, 0.88),
    ("índices", -1, "cautela"): (371, -0.164, 0.77), ("índices", -1, "no"): (59, -0.020, 0.97),
    ("divisas", 1, "posible"): (381, -0.032, 0.95), ("divisas", 1, "cautela"): (226, 0.014, 1.02),
    ("divisas", 1, "no"): (85, 0.025, 1.04), ("divisas", -1, "posible"): (311, -0.155, 0.79),
    ("divisas", -1, "cautela"): (295, -0.059, 0.92), ("divisas", -1, "no"): (65, 0.177, 1.29),
    ("energía", 1, "posible"): (131, 0.189, 1.31), ("energía", -1, "posible"): (79, -0.109, 0.85),
}
LAB_ACTIVO = {("USDJPY", 1, "posible"): (81, 0.503, 2.00)}   # excepción medida dentro del grupo divisas
# mismo laboratorio SIN swap (solo precio y costos de entrada) para las compras "posible": así se ve por qué índices y
# petróleo son de probabilidad media (el precio acompaña; el costo de mantener la posición se come o distorsiona el resultado)
LAB_SIN_SWAP = {("metales", 1, "posible"): (0.269, 1.46), ("cripto", 1, "posible"): (0.270, 1.47),
                ("índices", 1, "posible"): (0.155, 1.25), ("energía", 1, "posible"): (0.189, 1.31),
                ("divisas", 1, "posible"): (-0.025, 0.96)}
ALTA = {"XAUUSD", "XAGUSD", "BTCUSD", "ETHUSD", "USDJPY"}    # compras con las dos tendencias: positivas en ambos periodos


def probabilidad(clave, sentido, estado):
    """Alta / media / baja según lo medido en el laboratorio G1 (y por qué)."""
    g = GRUPO.get(clave)
    lab = LAB_ACTIVO.get((clave, sentido, estado)) or LAB.get((g, sentido, estado))
    if g is None:
        return "baja", "activo sin medir en el laboratorio (no se negocia en el bróker)", None
    if sentido < 0:
        return "baja", "en el laboratorio las ventas de esta estrategia pierden", lab
    if estado != "posible":
        return "baja", "sin las dos tendencias a favor, las compras no dieron ventaja en el laboratorio", lab
    if clave in ALTA:
        return "alta", "compra con las dos tendencias a favor: ganó en el laboratorio dentro y fuera de muestra", lab
    if g in ("índices", "energía"):
        motivo = ("el precio da la razón en el laboratorio, pero mantenerla semanas cuesta swap: mejor operación corta"
                  if g == "índices" else
                  "el precio da la razón en el laboratorio (sin swap); el resultado con swap del petróleo no es fiable")
        return "media", motivo, lab
    return "baja", "en divisas esta compra no dio ventaja en el laboratorio", lab


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
    prob, prob_motivo, lab = probabilidad(a.get("clave"), sentido, estado)
    g = GRUPO.get(a.get("clave"))
    ss = LAB_SIN_SWAP.get((g, sentido, estado)) if a.get("clave") not in ("USDJPY",) else None
    lab_d = None if lab is None else {"ops": lab[0], "E": lab[1], "PF": lab[2]}
    if lab_d and ss:
        lab_d |= {"E_ss": ss[0], "PF_ss": ss[1]}
    if g == "energía" and lab_d:
        lab_d["swap_dudoso"] = True   # el swap actual del petróleo aplicado a toda la historia no es fiable
    return {"accion": "compra" if sentido > 0 else "venta", "prob": prob, "prob_motivo": prob_motivo, "lab": lab_d,
            "gatillo": _r(gat), "stop": _r(stop),
            "stop_es": "Supertrend 4h" if st_ok else "2 ATR de 4h", "objetivo": _r(gat + sentido * 2 * riesgo),
            "riesgo_pct": round(riesgo / gat * 100, 2), "distancia_pct": round((gat / u - 1) * 100, 2),
            "distancia_atr": round(abs(gat - u) / atr4, 1), "ya_roto": ya_roto, "estado": estado, "a_favor": a_favor}


def plan_activo(a):
    """Sesgo del activo y sus dos planes (compra y venta). El sesgo resume la mejor probabilidad disponible."""
    compra, venta = lado(a, +1), lado(a, -1)
    mejor = max((p for p in (compra, venta) if p), key=lambda p: RANGO_PROB[p["prob"]], default=None)
    sesgo = None if mejor is None else (f"{mejor['accion']}_{mejor['prob']}" if mejor["prob"] != "baja" else "esperar")
    return {"sesgo": sesgo, "compra": compra, "venta": venta}


RANGO_PROB = {"alta": 2, "media": 1, "baja": 0}


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


def veredicto(salida):
    """La mejor opción del evento. Si el dato ya salió, solo cuenta el escenario que se dio.

    nivel = probabilidad del mejor plan: "alta", "media" o "baja" (laboratorio G1; un dato en línea con la previsión
    no da ventaja → "baja"). lejano: el gatillo está a más de 3 ATR de 4h (improbable en la sesión)."""
    hecho = salida[0].get("realizado")
    if hecho == "en línea":
        return {"nivel": "baja", "motivo": "en_linea"}
    cands = [(x, s) for x in salida for s in x["escenarios"] if not hecho or s["si"].startswith(f"dato {hecho}")]
    if not cands:
        return {"nivel": "baja", "motivo": "sin_datos"}
    x, s = min(cands, key=lambda c: (-RANGO_PROB[c[1]["prob"]], c[1]["distancia_atr"]))
    nivel = s["prob"]
    return {"nivel": nivel, "motivo": s["prob_motivo"], "estado": s["estado"], "clave": x["clave"],
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
                          f"a {s['distancia_pct']:+}% del precio) → probabilidad {s['prob'].upper()} ({s['prob_motivo']})")
        if x.get("realizado"):
            partes.append(f"{x['nombre']}: dato salió {x['realizado']}; reacción desde el dato {x.get('reaccion_pct')}%")
    v = g["veredicto"]
    cab = (f"PROBABILIDAD {v['nivel'].upper()}: {v.get('accion', '')} {v.get('nombre', '')} gatillo {v.get('gatillo')}"
           f"{' (lejano, >3 ATR 4h)' if v.get('lejano') else ''}" if v.get("accion") else f"PROBABILIDAD {v['nivel'].upper()} ({v['motivo']})")
    return f"   guía: {cab} | " + " ; ".join(partes)
