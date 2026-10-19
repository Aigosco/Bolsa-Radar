"""Tesis de analistas → verificación diaria contra precios → datos/web/tesis.json.

Entrada: datos/tesis/<autor>/<video_id>.json (los publica el PC: la extracción se hace leyendo las transcripciones, que
no se suben al repo). Mismo esquema que el proyecto local (fundamental/analistas.py).

Regla de verificación (sin mirar el futuro, sin inventar):
  inicio = fecha del video o `fecha_desde`; plazo = `fecha_limite` o la ventana del horizonte (corto 30 d, mediano 182 d,
  largo 730 d). Con nivel o `magnitud_pct`: cumplida solo si el máximo/mínimo diario lo alcanza dentro del plazo. Sin
  nivel: cumplida si al vencer el precio está del lado dicho (lateral: ±5 %). Condicionales y pendientes no se miden.

  python -m radar.tesis
"""
import json
import re
import sys
from datetime import date

import numpy as np
import pandas as pd

from .comun import DATOS, WEB, ahora_utc, guardar_json, iso, limpiar
from .mercado import bajar, cargar

VENTANA = {"corto": 30, "mediano": 182, "largo": 730}
LATERAL = 0.05
ALIAS = {"F40": "^FCHI", "STOXX50": "^STOXX50E"}
TIPOS = {"prediccion": "predicción", "recomendacion": "recomendación", "diagnostico": "diagnóstico"}


def precios(simbolo):
    px = cargar(simbolo)
    if len(px):
        return px
    tk = ALIAS.get(simbolo, simbolo)
    p = DATOS / "precios" / "extra" / (re.sub(r"[^\w.-]", "_", tk) + ".csv")
    viejo = pd.read_csv(p, parse_dates=["fecha"], index_col="fecha") if p.exists() else None
    desde = "2020-01-01" if viejo is None else (viejo.index.max() - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
    x = bajar([tk], start=desde, interval="1d").get(tk)
    if x is not None:
        nuevo = pd.DataFrame({"cierre": x["Close"].values, "maximo": x["High"].values, "minimo": x["Low"].values},
                             index=pd.to_datetime(x.index).tz_localize(None).normalize().rename("fecha"))
        df = pd.concat([viejo, nuevo]) if viejo is not None else nuevo
        df = df[~df.index.duplicated(keep="last")].sort_index()
        p.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(p, float_format="%.6g", date_format="%Y-%m-%d")
        return df
    return viejo if viejo is not None else pd.DataFrame()


def evaluar(t, px, hoy):
    inicio = pd.Timestamp(t.get("fecha_desde") or t["fecha_video"])
    if hoy < inicio:
        return {"estado": f"pendiente (empieza el {inicio:%Y-%m-%d})", "precio_hoy": float(px["cierre"].iloc[-1])}
    ref = px[px.index >= inicio]
    if ref.empty:
        return None
    p0 = float(ref["cierre"].iloc[0])
    plazo = pd.Timestamp(t["fecha_limite"]) if t.get("fecha_limite") else \
        inicio + pd.Timedelta(days=VENTANA.get(t.get("horizonte") or "mediano", 182))
    tramo = ref[ref.index <= plazo]
    p_hoy = float(ref["cierre"].iloc[-1])
    r_hoy, vencida = p_hoy / p0 - 1, hoy > plazo
    r_plazo = float(tramo["cierre"].iloc[-1]) / p0 - 1 if len(tramo) else np.nan
    niv, por_nivel = None, t.get("nivel") is not None
    if por_nivel:
        niv = float(t["nivel"])
    elif t.get("magnitud_pct") is not None:
        niv = p0 * (1 + float(t["magnitud_pct"]) / 100)
    tocado = ""
    if niv is not None and len(tramo) and t["direccion"] in ("sube", "baja"):
        m = tramo[tramo["maximo"] >= niv] if t["direccion"] == "sube" else tramo[tramo["minimo"] <= niv]
        tocado = m.index[0].strftime("%Y-%m-%d") if len(m) else ""
    signo = {"sube": 1, "baja": -1}.get(t["direccion"], 0)
    if tocado:
        estado = "cumplida (tocó el nivel)" if por_nivel else "cumplida (recorrió el % dicho)"
    elif t["direccion"] == "lateral":
        ok = abs(r_plazo if vencida else r_hoy) <= LATERAL
        estado = ("cumplida" if ok else "fallida") if vencida else ("en curso (a favor)" if ok else "en curso (en contra)")
    elif niv is not None and vencida:
        estado = "fallida (no tocó el nivel)" if por_nivel else "fallida (no recorrió el % dicho)"
    elif vencida:
        estado = "cumplida" if r_plazo * signo > 0 else "fallida"
    elif r_hoy == 0:
        estado = "en curso (sin cambio)"
    else:
        estado = "en curso (a favor)" if r_hoy * signo > 0 else "en curso (en contra)"
    return {"precio_ref": p0, "fecha_ref": f"{ref.index[0]:%Y-%m-%d}", "plazo": f"{plazo:%Y-%m-%d}", "precio_hoy": p_hoy,
            "ret_hoy": round(r_hoy, 4), "ret_plazo": None if np.isnan(r_plazo) else round(r_plazo, 4),
            "objetivo": None if niv is None else round(niv, 4), "tocado": tocado, "estado": estado}


def main():
    hoy = pd.Timestamp(date.today())
    videos, todas = [], []
    for f in sorted((DATOS / "tesis").glob("*/*.json")):
        v = json.loads(f.read_text(encoding="utf-8"))
        videos.append({"autor": f.parent.name, "video_id": v["video_id"], "titulo": v.get("titulo"), "fecha": v.get("fecha"),
                       "resumen": v.get("resumen"), "temas": v.get("temas", []), "url": f"https://youtu.be/{v['video_id']}",
                       "n_tesis": len(v.get("tesis", []))})
        for n, t in enumerate(v.get("tesis", [])):
            todas.append(dict(t, autor=f.parent.name, video_id=v["video_id"], n=n, fecha_video=v.get("fecha"),
                              titulo_video=v.get("titulo")))
    cache = {}
    for t in todas:
        res = None
        if t["tipo"] == "diagnostico":
            t["estado"] = "no verificable (diagnóstico)"
            continue
        if not t.get("activa_desde_ya", True):
            t["estado"] = "condicional (espera su disparador)"
            continue
        if not t.get("simbolo") or t["direccion"] not in ("sube", "baja", "lateral"):
            t["estado"] = "no verificable (sin activo medible)"
            continue
        if t["simbolo"] not in cache:
            try:
                cache[t["simbolo"]] = precios(t["simbolo"])
            except Exception as ex:  # noqa: BLE001
                print(f"{t['simbolo']}: sin precios ({ex})")
                cache[t["simbolo"]] = pd.DataFrame()
        px = cache[t["simbolo"]]
        res = evaluar(t, px, hoy) if len(px) else None
        t.update(res or {"estado": "no verificable (sin precios)"})
    medibles = [t for t in todas if not re.match(r"^(no verificable|condicional|pendiente)", t["estado"])]
    marcador = {}
    for t in medibles:
        m = marcador.setdefault(t["simbolo"], {"simbolo": t["simbolo"], "tesis": 0, "cumplidas": 0, "fallidas": 0,
                                               "a_favor": 0, "en_contra": 0})
        m["tesis"] += 1
        e = t["estado"]
        m["cumplidas"] += e.startswith("cumplida")
        m["fallidas"] += e.startswith("fallida")
        m["a_favor"] += e == "en curso (a favor)"
        m["en_contra"] += e == "en curso (en contra)"
    corto = lambda t: {k: t.get(k) for k in ("autor", "fecha_video", "titulo_video", "video_id", "tipo", "activo", "simbolo",  # noqa: E731
                                            "direccion", "horizonte", "nivel", "magnitud_pct", "fecha_desde",
                                            "fecha_limite", "condicion", "cita", "minuto", "conviccion", "estado",
                                            "precio_ref", "precio_hoy", "ret_hoy", "ret_plazo", "plazo", "objetivo")}
    limite21 = (hoy - pd.Timedelta(days=21)).strftime("%Y-%m-%d")
    recientes = [corto(t) for t in todas if t["tipo"] != "diagnostico" and (t["fecha_video"] or "") >= limite21]
    cerradas = [corto(t) for t in todas if re.match(r"^(cumplida|fallida)", t["estado"])]
    pendientes = sorted([corto(t) for t in todas if t["estado"].startswith("pendiente")], key=lambda x: x["fecha_desde"])
    condicionales = [corto(t) for t in todas if t["estado"].startswith("condicional")]
    totales = {"videos": len(videos), "tesis": len(todas),
               "por_tipo": {TIPOS[k]: sum(t["tipo"] == k for t in todas) for k in TIPOS},
               "cumplidas": sum(t["estado"].startswith("cumplida") for t in todas),
               "fallidas": sum(t["estado"].startswith("fallida") for t in todas),
               "en_curso": sum(t["estado"].startswith("en curso") for t in todas),
               "pendientes": len(pendientes), "condicionales": len(condicionales)}
    videos.sort(key=lambda v: v["fecha"] or "", reverse=True)
    for v in videos:
        v["resumen"] = limpiar(v["resumen"], 420)
    guardar_json(WEB / "tesis.json", {
        "generado": iso(ahora_utc()), "totales": totales,
        "marcador": sorted(marcador.values(), key=lambda m: -m["tesis"]),
        "recientes": sorted(recientes, key=lambda x: x["fecha_video"], reverse=True)[:60],
        "cerradas": sorted(cerradas, key=lambda x: x["fecha_video"], reverse=True),
        "pendientes": pendientes, "condicionales": condicionales, "videos": videos[:12],
    }, compacto=True)
    print(f"web/tesis.json: {len(videos)} videos, {len(todas)} tesis, {len(medibles)} medibles")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
