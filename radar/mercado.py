"""Mercado (Yahoo Finance) y bonos (Tesoro de EE. UU.) → datos/precios/*.csv, datos/tesoro.csv y JSON de la web.

  python -m radar.mercado            # foto cada 30 min → web/mercado.json
  python -m radar.mercado --diario   # además: historia diaria desde 2005, bonos, valor relativo (web/bonos.json, valor.json)

Precios de Yahoo: futuros continuos para materias primas (GC=F, CL=F…), así que difieren unos dólares del contado del
bróker (los niveles del bot se publican aparte con los precios de MT5). La tendencia de 4h usa el mismo Supertrend 10/3 del
laboratorio sobre velas de 4h armadas con velas de 1 h de Yahoo (aproximación: el corte horario no es el del bróker).
"""
import argparse
import csv
import io
import sys
from datetime import timedelta

import numpy as np
import pandas as pd
import requests
import yfinance as yf

from . import guia as G
from .comun import DATOS, UA, WEB, ahora_utc, guardar_json, iso

ACTIVOS = [  # clave, nombre, ticker de Yahoo, grupo
    ("XAUUSD", "Oro", "GC=F", "Metales"), ("XAGUSD", "Plata", "SI=F", "Metales"), ("COBRE", "Cobre", "HG=F", "Metales"),
    ("BTCUSD", "Bitcoin", "BTC-USD", "Cripto"), ("ETHUSD", "Ethereum", "ETH-USD", "Cripto"),
    ("US500", "S&P 500", "^GSPC", "Índices"), ("USTEC", "Nasdaq 100", "^NDX", "Índices"),
    ("US30", "Dow Jones", "^DJI", "Índices"), ("DE40", "DAX", "^GDAXI", "Índices"),
    ("XTIUSD", "Petróleo WTI", "CL=F", "Energía"), ("XBRUSD", "Brent", "BZ=F", "Energía"),
    ("JP225", "Nikkei 225", "^N225", "Índices"),
    ("EURUSD", "EUR/USD", "EURUSD=X", "Divisas"), ("USDJPY", "USD/JPY", "JPY=X", "Divisas"),
    ("GBPUSD", "GBP/USD", "GBPUSD=X", "Divisas"), ("USDCAD", "USD/CAD", "CAD=X", "Divisas"),
    ("AUDUSD", "AUD/USD", "AUDUSD=X", "Divisas"), ("NZDUSD", "NZD/USD", "NZDUSD=X", "Divisas"),
    ("USDCHF", "USD/CHF", "CHF=X", "Divisas"),
    ("DXY", "Dólar (DXY)", "DX-Y.NYB", "Divisas"), ("VIX", "VIX", "^VIX", "Riesgo"),
    ("BONO10", "Bono 10 años", "^TNX", "Riesgo"),
]
HISTORIA = [a[0] for a in ACTIVOS] + ["XPTUSD", "GASNAT", "US2000", "IBEX35"]
EXTRA = {"XPTUSD": "PL=F", "GASNAT": "NG=F", "US2000": "^RUT", "IBEX35": "^IBEX"}
TICKER = {a[0]: a[2] for a in ACTIVOS} | EXTRA
RATIOS = [("XAUUSD", "XAGUSD", "Oro / plata", "alto = plata barata frente al oro"),
          ("XAUUSD", "COBRE", "Oro / cobre", "alto = miedo frente a crecimiento"),
          ("XAUUSD", "US500", "Oro / S&P 500", "alto = oro caro frente a la bolsa"),
          ("XTIUSD", "XAUUSD", "Petróleo / oro", "bajo = petróleo barato en onzas de oro"),
          ("BTCUSD", "XAUUSD", "Bitcoin / oro", "onzas de oro por bitcoin")]
TESORO = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/"
          "{a}/all?type={t}&field_tdr_date_value={a}&page&_format=csv")
TIPOS = {"nominal": "daily_treasury_yield_curve", "real": "daily_treasury_real_yield_curve"}


# ------------------------------------------------------------------ indicadores (idénticos al laboratorio)
def atr(h, l, c, n=14):
    pc = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).ewm(alpha=1 / n, adjust=False, min_periods=n).mean().values


def supertrend(h, l, c, n=10, mult=3.0):
    a = atr(h, l, c, n)
    hl2 = (h + l) / 2
    up, dn = hl2 - mult * a, hl2 + mult * a
    fu, fd = up.copy(), dn.copy()
    d = np.ones(len(c), int)
    linea = np.full(len(c), np.nan)
    for i in range(1, len(c)):
        if np.isnan(a[i]):
            continue
        fu[i] = max(up[i], fu[i - 1]) if c[i - 1] > fu[i - 1] and not np.isnan(fu[i - 1]) else up[i]
        fd[i] = min(dn[i], fd[i - 1]) if c[i - 1] < fd[i - 1] and not np.isnan(fd[i - 1]) else dn[i]
        if d[i - 1] == 1:
            d[i] = -1 if c[i] < fu[i] else 1
        else:
            d[i] = 1 if c[i] > fd[i] else -1
        linea[i] = fu[i] if d[i] == 1 else fd[i]
    return linea, d


# ------------------------------------------------------------------ descarga
def bajar(tickers, **kw):
    d = yf.download(tickers, progress=False, auto_adjust=False, group_by="ticker", threads=True, **kw)
    out = {}
    for t in tickers:
        try:
            x = d[t] if isinstance(d.columns, pd.MultiIndex) else d
            x = x.dropna(subset=["Close"])
            if len(x):
                out[t] = x
        except KeyError:
            pass
    return out


def r6(v):
    return None if v is None or not np.isfinite(v) else float(f"{float(v):.6g}")


def velas_4h(h1):
    """Velas de 4h CERRADAS a partir de velas de 1 h (UTC), con el Supertrend 10/3 (línea y dirección)."""
    x = h1.copy()
    x.index = pd.to_datetime(x.index, utc=True)
    v4 = x.resample("4h", origin="epoch").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"}).dropna()
    if len(v4) and v4.index[-1] + pd.Timedelta(hours=4) > pd.Timestamp.now(tz="UTC"):
        v4 = v4.iloc[:-1]  # la última vela aún no cerró
    if len(v4) < 30:
        return None
    linea, d = supertrend(v4["High"].values, v4["Low"].values, v4["Close"].values)
    v4["st"], v4["st_dir"] = linea, d
    v4["atr"] = atr(v4["High"].values, v4["Low"].values, v4["Close"].values)
    return v4


def niveles(c_dia, x_dia, v4):
    """Niveles técnicos medibles para los planes de acción (nada inventado: todo sale de las velas).

    Donchian 20 en 4h = máximo / mínimo de las 20 velas de 4h cerradas ANTERIORES a la última (como el bot P5);
    Supertrend 10/3 de 4h; ATR de 4h y diario; máximo / mínimo de 20 días; media de 200 días."""
    n = {}
    if v4 is not None and len(v4) > 21:
        prev = v4.iloc[-21:-1]
        n |= {"donchian_alto": r6(prev["High"].max()), "donchian_bajo": r6(prev["Low"].min()),
              "st_4h": r6(v4["st"].iloc[-1]), "st_dir": "alcista" if v4["st_dir"].iloc[-1] > 0 else "bajista",
              "atr_4h": r6(v4["atr"].iloc[-1]), "cierre_4h": r6(v4["Close"].iloc[-1]),
              "hora_4h": v4.index[-1].strftime("%Y-%m-%dT%H:%MZ")}
        # desde cuándo dura la dirección actual del Supertrend
        cambio = np.nonzero(np.diff(v4["st_dir"].values))[0]
        if len(cambio):
            n["st_desde"] = v4.index[cambio[-1] + 1].strftime("%Y-%m-%dT%H:%MZ")
    if len(x_dia) > 21:
        n |= {"max_20d": r6(x_dia["High"].iloc[-21:-1].max()), "min_20d": r6(x_dia["Low"].iloc[-21:-1].min()),
              "atr_d": r6(atr(x_dia["High"].values.astype(float), x_dia["Low"].values.astype(float),
                              c_dia.values)[-1])}
    if len(c_dia) >= 200:
        n["ma200"] = r6(c_dia.rolling(200).mean().iloc[-1])
    return n


def foto():
    ahora = ahora_utc()
    tks = [a[2] for a in ACTIVOS]
    dia = bajar(tks, period="2y", interval="1d")
    hora = bajar(tks, period="60d", interval="1h")
    filas, graficos = [], {}
    for clave, nombre, tk, grupo in ACTIVOS:
        x = dia.get(tk)
        if x is None or len(x) < 30:
            filas.append({"clave": clave, "nombre": nombre, "grupo": grupo, "sin_datos": True})
            continue
        c = x["Close"].astype(float)
        u = float(c.iloc[-1])
        ma200 = float(c.rolling(200).mean().iloc[-1]) if len(c) >= 200 else None
        ch = lambda n: round((u / float(c.iloc[-1 - n]) - 1) * 100, 2) if len(c) > n else None  # noqa: E731
        v4 = velas_4h(hora[tk]) if tk in hora else None
        niv = niveles(c, x, v4)
        fila = {
            "clave": clave, "nombre": nombre, "grupo": grupo, "ticker": tk, "ultimo": round(u, 5),
            "fecha": str(c.index[-1].date()), "ch_1d": ch(1), "ch_5d": ch(5), "ch_1m": ch(21),
            "vs_ma200": round((u / ma200 - 1) * 100, 2) if ma200 else None,
            "tend_diaria": ("alcista" if u > ma200 else "bajista") if ma200 else None,
            "tend_4h": niv.get("st_dir"), "supertrend_4h": niv.get("st_4h"),
            "max_52s": round(float(c.iloc[-252:].max()), 5), "min_52s": round(float(c.iloc[-252:].min()), 5),
            "spark": [round(float(v), 5) for v in c.iloc[-90:]], "niveles": niv,
        }
        fila["plan"] = G.plan_activo(fila)
        filas.append(fila)
        # velas para los gráficos de la página (6 meses diarios con media de 200 días; ~15 días de 4h; 72 h de 1h)
        ma = c.rolling(200).mean()
        d = x.iloc[-130:]
        graficos[clave] = {
            "d": [[f"{i:%Y-%m-%d}", r6(o), r6(h), r6(lo), r6(cc), r6(ma.loc[i])]
                  for i, o, h, lo, cc in zip(d.index, d["Open"], d["High"], d["Low"], d["Close"])],
            "h4": [] if v4 is None else [[f"{i:%Y-%m-%dT%H:%MZ}", r6(o), r6(h), r6(lo), r6(cc), r6(s), int(sd)]
                                         for i, o, h, lo, cc, s, sd in zip(v4.index[-90:], *(v4[k].iloc[-90:] for k in
                                                                       ("Open", "High", "Low", "Close", "st", "st_dir")))],
            "h1": [] if tk not in hora else [[f"{pd.Timestamp(i).tz_convert('UTC'):%Y-%m-%dT%H:%MZ}", r6(v)]
                                             for i, v in hora[tk]["Close"].iloc[-72:].items()],
        }
    guardar_json(WEB / "mercado.json", {"generado": iso(ahora), "fuente": "Yahoo Finance", "activos": filas},
                 compacto=True)
    guardar_json(WEB / "graficos.json", {"generado": iso(ahora), "activos": graficos}, compacto=True)
    print(f"web/mercado.json: {sum(not f.get('sin_datos') for f in filas)}/{len(filas)} activos · web/graficos.json")


# ------------------------------------------------------------------ historia diaria, bonos y valor relativo
def ruta(clave):
    return DATOS / "precios" / f"{clave}.csv"


def historia():
    for clave in HISTORIA:
        p = ruta(clave)
        viejo = pd.read_csv(p, parse_dates=["fecha"]) if p.exists() else None
        desde = (viejo["fecha"].max() - timedelta(days=7)).strftime("%Y-%m-%d") if viejo is not None else "2005-01-01"
        x = bajar([TICKER[clave]], start=desde, interval="1d").get(TICKER[clave])
        if x is None:
            print(f"{clave}: sin datos")
            continue
        nuevo = pd.DataFrame({"fecha": pd.to_datetime(x.index).tz_localize(None).normalize(),
                              "cierre": x["Close"].values, "maximo": x["High"].values, "minimo": x["Low"].values})
        df = pd.concat([viejo, nuevo]) if viejo is not None else nuevo
        df = df.drop_duplicates("fecha", keep="last").sort_values("fecha")
        p.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(p, index=False, float_format="%.6g", date_format="%Y-%m-%d")
        print(f"{clave}: {len(df)} días hasta {df['fecha'].max():%Y-%m-%d}")


def cargar(clave):
    p = ruta(clave)
    return pd.read_csv(p, parse_dates=["fecha"], index_col="fecha") if p.exists() else pd.DataFrame()


def pctl(serie, valor):
    s = serie.dropna()
    return round(float((s < valor).mean() * 100), 0) if len(s) else None


def valor():
    hoy = pd.Timestamp.now().normalize()
    nombres = {a[0]: a[1] for a in ACTIVOS} | {"XPTUSD": "Platino", "GASNAT": "Gas natural", "US2000": "Russell 2000",
                                                "IBEX35": "IBEX 35", "JP225": "Nikkei 225"}
    filas, ratios = [], []
    for clave in HISTORIA:
        px = cargar(clave)
        if px.empty:
            continue
        c = px["cierre"]
        u = float(c.iloc[-1])
        diez = c[c.index >= hoy - pd.DateOffset(years=10)]
        filas.append({"clave": clave, "nombre": nombres.get(clave, clave), "ultimo": u, "pctl_10a": pctl(diez, u),
                      "vs_max_10a": round((u / diez.max() - 1) * 100, 1), "vs_max_hist": round((u / px["maximo"].max() - 1) * 100, 1),
                      "ch_12m": round((u / float(c.iloc[-253]) - 1) * 100, 1) if len(c) > 253 else None,
                      "min_10a": float(diez.min()), "max_10a": float(diez.max()), "fecha": f"{c.index[-1]:%Y-%m-%d}"})
    for a, b, nombre, lectura in RATIOS:
        pa, pb = cargar(a), cargar(b)
        if pa.empty or pb.empty:
            continue
        r = (pa["cierre"] / pb["cierre"]).dropna()
        diez = r[r.index >= hoy - pd.DateOffset(years=10)]
        u = float(r.iloc[-1])
        ratios.append({"nombre": nombre, "hoy": u, "pctl_10a": pctl(diez, u), "mediana_10a": float(diez.median()),
                       "min_10a": float(diez.min()), "max_10a": float(diez.max()), "lectura": lectura,
                       "serie": [round(float(v), 4) for v in diez.resample("ME").last().dropna()]})
    guardar_json(WEB / "valor.json", {"generado": iso(ahora_utc()), "activos": filas, "ratios": ratios}, compacto=True)
    print(f"web/valor.json: {len(filas)} activos, {len(ratios)} ratios")


def tesoro():
    p = DATOS / "tesoro.csv"
    viejo = pd.read_csv(p) if p.exists() else pd.DataFrame(columns=["fecha", "tipo", "plazo", "rendimiento"])
    anios = [ahora_utc().year] if len(viejo) else list(range(2023, ahora_utc().year + 1))
    filas = []
    for a in anios:
        for tipo, t in TIPOS.items():
            r = requests.get(TESORO.format(a=a, t=t), headers={"User-Agent": UA}, timeout=60)
            r.raise_for_status()
            for f in csv.DictReader(io.StringIO(r.text)):
                fecha = pd.to_datetime(f.pop("Date"), format="%m/%d/%Y").strftime("%Y-%m-%d")
                filas += [(fecha, tipo, k, float(v)) for k, v in f.items() if v not in ("", None)]
    df = pd.concat([viejo, pd.DataFrame(filas, columns=viejo.columns)]).drop_duplicates(["fecha", "tipo", "plazo"],
                                                                                         keep="last")
    df.sort_values(["fecha", "tipo", "plazo"]).to_csv(p, index=False)
    piv = df.assign(k=df["tipo"] + " " + df["plazo"].str.upper()).pivot_table(index="fecha", columns="k",
                                                                              values="rendimiento").sort_index()
    series = {"2 años": "nominal 2 YR", "10 años": "nominal 10 YR", "30 años": "nominal 30 YR", "Real 10 años": "real 10 YR"}
    tabla, graf = [], {}
    for nombre, k in series.items():
        if k not in piv:
            continue
        s = piv[k].dropna()
        tabla.append({"nombre": nombre, "ultimo": float(s.iloc[-1]), "fecha": s.index[-1],
                      "d1_pb": round((s.iloc[-1] - s.iloc[-2]) * 100), "d5_pb": round((s.iloc[-1] - s.iloc[-6]) * 100),
                      "d21_pb": round((s.iloc[-1] - s.iloc[-22]) * 100)})
        graf[nombre] = [[f, float(v)] for f, v in s.iloc[-260:].items()]
    if "nominal 10 YR" in piv and "nominal 2 YR" in piv:
        cur = (piv["nominal 10 YR"] - piv["nominal 2 YR"]).dropna()
        tabla.append({"nombre": "Pendiente 10–2", "ultimo": round(float(cur.iloc[-1]), 2), "fecha": cur.index[-1],
                      "d1_pb": round((cur.iloc[-1] - cur.iloc[-2]) * 100), "d5_pb": round((cur.iloc[-1] - cur.iloc[-6]) * 100),
                      "d21_pb": round((cur.iloc[-1] - cur.iloc[-22]) * 100), "es_pendiente": True})
    guardar_json(WEB / "bonos.json", {"generado": iso(ahora_utc()), "fuente": "Tesoro de EE. UU.", "tabla": tabla,
                                      "series": graf}, compacto=True)
    print(f"web/bonos.json: {len(tabla)} filas")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--diario", action="store_true")
    a = ap.parse_args()
    foto()
    if a.diario:
        for paso in (historia, valor, tesoro):
            try:
                paso()
            except Exception as ex:  # noqa: BLE001 — un paso caído no impide los demás
                print(f"{paso.__name__}: fallo {ex}")
