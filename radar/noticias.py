"""Titulares RSS → datos/titulares/AAAA/MM/DD.jsonl (por fecha de captura UTC) y datos/web/titulares.json.

Se ejecuta cada 15 minutos en GitHub Actions. Los feeds no tienen historial (traen sus últimos 10–100 titulares), así que
la frecuencia decide qué se pierde: Investing cubre ~30 min, Yahoo 7–12 h, Google News ~1 día (medido el 2026-10-18).
Cada titular se guarda una sola vez (clave = hash del guid/enlace; registro de vistos de 60 días).
`capturado` es la hora en que lo leímos: es la que se debe usar en backtesting para no mirar el futuro.

  python -m radar.noticias            # una pasada + JSON de la web
  python -m radar.noticias --solo-web # rehace solo el JSON de la web
"""
import argparse
import json
import re
import sys
from collections import Counter
from datetime import timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape

import requests

from .comun import (DATOS, UA, WEB, ahora_utc, clave, es_grande, guardar_json, iso, leer_json, limpiar, RUIDO,
                    temas_de, TEMAS)

FEEDS = {
    "bloomberg/markets": "https://feeds.bloomberg.com/markets/news.rss",
    "bloomberg/economics": "https://feeds.bloomberg.com/economics/news.rss",
    "bloomberg/politics": "https://feeds.bloomberg.com/politics/news.rss",
    "bloomberg/technology": "https://feeds.bloomberg.com/technology/news.rss",
    "bloomberg/industries": "https://feeds.bloomberg.com/industries/news.rss",
    "bloomberg/opinion": "https://feeds.bloomberg.com/bview/news.rss",
    "yahoo/oro": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=GC=F&region=US&lang=en-US",
    "yahoo/plata": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=SI=F&region=US&lang=en-US",
    "yahoo/sp500": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5EGSPC&region=US&lang=en-US",
    "yahoo/nasdaq": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5EIXIC&region=US&lang=en-US",
    "yahoo/bitcoin": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=BTC-USD&region=US&lang=en-US",
    "yahoo/dolar": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=DX-Y.NYB&region=US&lang=en-US",
    "cnbc/economia": "https://www.cnbc.com/id/20910258/device/rss/rss.html",
    "cnbc/mercados": "https://www.cnbc.com/id/10000664/device/rss/rss.html",
    "cnbc/top": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "wsj/mercados": "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain",
    "marketwatch/top": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "ft/mercados": "https://www.ft.com/markets?format=rss",
    "investing/noticias": "https://www.investing.com/rss/news.rss",
    "fxstreet/noticias": "https://www.fxstreet.com/rss/news",
    "fed/comunicados": "https://www.federalreserve.gov/feeds/press_all.xml",
    "fed/discursos": "https://www.federalreserve.gov/feeds/speeches.xml",
    "google/reuters": "https://news.google.com/rss/search?q=site:reuters.com+markets+when:1d&hl=en-US&gl=US&ceid=US:en",
    "google/oro": "https://news.google.com/rss/search?q=gold+price+when:1d&hl=en-US&gl=US&ceid=US:en",
    "google/fed": "https://news.google.com/rss/search?q=federal+reserve+when:1d&hl=en-US&gl=US&ceid=US:en",
    "google/geopolitica": "https://news.google.com/rss/search?q=war+OR+sanctions+OR+geopolitical+when:1d&hl=en-US&gl=US"
                          "&ceid=US:en",
    # Investing publica ~20 titulares/hora y su feed solo trae 10: esta búsqueda recupera parte de lo que se escapa
    "google/investing": "https://news.google.com/rss/search?q=site:investing.com+when:1d&hl=en-US&gl=US&ceid=US:en",
    # FXStreet responde 403 a los servidores de GitHub (2026-10-19); su contenido llega por esta búsqueda
    "google/fxstreet": "https://news.google.com/rss/search?q=site:fxstreet.com+when:1d&hl=en-US&gl=US&ceid=US:en",
}
NOMBRES = {"bloomberg": "Bloomberg", "yahoo": "Yahoo Finance", "cnbc": "CNBC", "wsj": "WSJ", "marketwatch": "MarketWatch",
           "ft": "Financial Times", "investing": "Investing.com", "fxstreet": "FXStreet", "fed": "Reserva Federal"}
VISTOS = DATOS / "titulares" / "vistos.json"
DIAS_VISTOS = 60


def campo(item, tag):
    m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", item, re.S)
    if not m:
        return ""
    x = re.sub(r"^<!\[CDATA\[|\]\]>$", "", m.group(1).strip())
    return unescape(re.sub(r"<[^>]+>", "", x)).strip()


def medio_de(feed, titulo):
    fuente = feed.split("/")[0]
    if fuente == "google":
        m = re.search(r" - ([^-]+)$", titulo)
        return m.group(1).strip() if m else "Google News"
    return NOMBRES.get(fuente, fuente)


def leer_feed(nombre, url):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    xml = r.content.decode("utf-8", errors="replace")
    salida = []
    for it in re.findall(r"<item>(.*?)</item>", xml, re.S):
        titulo = campo(it, "title")
        enlace = campo(it, "link")
        pub = campo(it, "pubDate")
        try:
            pub = iso(parsedate_to_datetime(pub))
        except Exception:  # noqa: BLE001 — fecha rara: se guarda tal cual
            pass
        salida.append({"id": clave(campo(it, "guid") or enlace or titulo), "feed": nombre,
                       "medio": medio_de(nombre, titulo), "titulo": re.sub(r" - [^-]+$", "", titulo)
                       if nombre.startswith("google/") else titulo, "resumen": limpiar(campo(it, "description"), 300),
                       "enlace": enlace, "publicado": pub})
    return salida


def pasada():
    ahora = ahora_utc()
    vistos = leer_json(VISTOS, {})
    limite = (ahora - timedelta(days=DIAS_VISTOS)).strftime("%Y-%m-%d")
    vistos = {k: v for k, v in vistos.items() if v >= limite}
    nuevos, estado = [], {}
    for nombre, url in FEEDS.items():
        try:
            items = leer_feed(nombre, url)
        except Exception as ex:  # noqa: BLE001 — un feed caído no detiene a los demás
            estado[nombre] = {"ok": False, "error": str(ex)[:120], "nuevos": 0}
            print(f"{nombre}: fallo {ex}")
            continue
        n = 0
        for t in items:
            if t["id"] in vistos:
                continue
            t["capturado"] = iso(ahora)
            vistos[t["id"]] = ahora.strftime("%Y-%m-%d")
            nuevos.append(t)
            n += 1
        estado[nombre] = {"ok": True, "items": len(items), "nuevos": n}
        print(f"{nombre}: {len(items)} en el feed, {n} nuevos")
    if nuevos:
        f = DATOS / "titulares" / ahora.strftime("%Y/%m/%d.jsonl")
        f.parent.mkdir(parents=True, exist_ok=True)
        with open(f, "a", encoding="utf-8") as fh:
            for t in nuevos:
                fh.write(json.dumps(t, ensure_ascii=False) + "\n")
    guardar_json(VISTOS, vistos, compacto=True)
    guardar_json(DATOS / "titulares" / "estado_feeds.json", {"actualizado": iso(ahora), "feeds": estado})
    print(f"total nuevos: {len(nuevos)}")
    return len(nuevos)


def recientes(horas=36):
    """Titulares capturados en los últimos días con fecha de publicación dentro de `horas`."""
    ahora = ahora_utc()
    desde = iso(ahora - timedelta(hours=horas))
    filas = []
    for d in range(3):
        f = DATOS / "titulares" / (ahora - timedelta(days=d)).strftime("%Y/%m/%d.jsonl")
        if f.exists():
            filas += [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
    vistos, salida = set(), []
    for t in sorted(filas, key=lambda x: x.get("publicado") or "", reverse=True):
        llave = re.sub(r"\W+", " ", t["titulo"].lower()).strip()
        if (t.get("publicado") or "") < desde or llave in vistos or re.search(RUIDO, t["titulo"], re.I):
            continue
        vistos.add(llave)
        t["temas"] = temas_de(t["titulo"])
        t["grande"] = es_grande(t["medio"])
        salida.append(t)
    return salida


TRAD = DATOS / "titulares" / "traduccion_es.json"
GTX = "https://translate.googleapis.com/translate_a/single"


def traducir(titulos):
    """Traducción al español de los titulares con el traductor público de Google (sin clave). Caché por titular:
    cada uno se traduce una sola vez. Si el servicio falla, el titular queda en inglés (la página lo muestra así)."""
    cache = leer_json(TRAD, {}) or {}
    faltan = [t for t in dict.fromkeys(titulos) if clave(t) not in cache]
    for i in range(0, len(faltan), 40):
        lote = [re.sub(r"\s+", " ", t).strip() for t in faltan[i:i + 40]]
        try:
            r = requests.post(GTX, params={"client": "gtx", "sl": "auto", "tl": "es", "dt": "t"},
                              data={"q": "\n".join(lote)}, headers={"User-Agent": UA}, timeout=30)
            r.raise_for_status()
            lineas = "".join(x[0] for x in r.json()[0] if x and x[0]).split("\n")
        except Exception as ex:  # noqa: BLE001
            print(f"traducción: fallo ({ex}); quedan en inglés")
            break
        if len(lineas) != len(lote):
            print(f"traducción: el lote volvió con {len(lineas)} líneas en vez de {len(lote)}; se omite")
            continue
        for t, es in zip(faltan[i:i + 40], lineas):
            cache[clave(t)] = es.strip()
    vivos = {clave(t) for t in titulos}
    guardar_json(TRAD, {k: v for k, v in cache.items() if k in vivos}, compacto=True)
    return {t: cache.get(clave(t)) for t in titulos}


def web():
    ahora = ahora_utc()
    tit = recientes(36)
    ult24 = [t for t in tit if t["publicado"] >= iso(ahora - timedelta(hours=24))]
    por_hora = Counter(t["publicado"][:13] for t in ult24)
    horas = [(ahora - timedelta(hours=h)).strftime("%Y-%m-%dT%H") for h in range(23, -1, -1)]
    temas = []
    for tema, _ in TEMAS:
        g = [t for t in tit if tema in t["temas"]]
        if not g:
            continue
        # se eligen primero los medios grandes y se muestran en orden cronológico
        g = sorted(sorted(g, key=lambda t: (t["grande"], t["publicado"]), reverse=True)[:14],
                   key=lambda t: t["publicado"], reverse=True)
        temas.append({"tema": tema, "n": len(g), "medios": len({t["medio"] for t in g}),
                      "n_24h": sum(t["publicado"] >= iso(ahora - timedelta(hours=24)) for t in g),
                      "titulares": [{k: t[k] for k in ("titulo", "medio", "enlace", "publicado")} for t in g[:14]]})
    es = traducir([t["titulo"] for g in temas for t in g["titulares"]] + [t["titulo"] for t in tit[:60]])
    for g in temas:
        for t in g["titulares"]:
            t["titulo_es"] = es.get(t["titulo"])
    estado = leer_json(DATOS / "titulares" / "estado_feeds.json", {})
    guardar_json(WEB / "titulares.json", compacto=True, obj={
        "generado": iso(ahora), "total_36h": len(tit), "total_24h": len(ult24),
        "por_hora": [{"hora": h + ":00Z", "n": por_hora.get(h, 0)} for h in horas],
        "temas": sorted(temas, key=lambda x: -x["n_24h"]),
        "ultimos": [{k: t[k] for k in ("titulo", "medio", "enlace", "publicado", "temas", "grande")} | {"titulo_es": es.get(t["titulo"])}
                    for t in tit[:60]],
        "feeds": estado.get("feeds", {}), "feeds_actualizado": estado.get("actualizado"),
    })
    print(f"web/titulares.json: {len(tit)} titulares (36 h), {len(temas)} temas")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo-web", action="store_true")
    a = ap.parse_args()
    if not a.solo_web:
        pasada()
    web()
