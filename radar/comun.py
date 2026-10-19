"""Utilidades comunes de Bolsa-Radar: rutas, hora, lectura/escritura de JSON y clasificación de titulares por tema."""
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datos"
WEB = DATOS / "web"          # lo que lee la página (se sirve desde raw.githubusercontent.com)
TZ_NY = "America/New_York"
TZ_CO = "America/Bogota"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/130.0.0.0 Safari/537.36")

TEMAS = [
    ("Fed y tasas", r"\bfed\b|federal reserve|powell|warsh|rate cut|rate hike|interest rate|fomc|treasur|yield|bond"),
    ("Inflación", r"inflation|\bcpi\b|\bpce\b|prices rise|price index"),
    ("Empleo", r"\bjobs\b|payroll|unemployment|labor market|jobless"),
    ("Oro y metales", r"\bgold\b|silver|precious metal|bullion|copper|platinum"),
    ("Energía", r"\boil\b|crude|opec|natural gas|diesel|energy|\bwti\b|brent"),
    ("Geopolítica", r"\bwar\b|sanction|missile|military|ukraine|russia|israel|iran|gaza|taiwan|tariff|attack|conflict"
                    r"|hormuz|houthi"),
    ("China", r"china|chinese|beijing|yuan|\bxi\b"),
    ("Cripto", r"bitcoin|crypto|\bether|stablecoin|\bbtc\b|solana"),
    ("Bolsa y empresas", r"stock|shares|earnings|profit|revenue|\bipo\b|nasdaq|s&p|\bdow\b|wall street|nvidia|apple"
                         r"|microsoft|tesla|meta\b"),
]
GRANDES = ["reuters", "bloomberg", "cnbc", "wsj", "wall street journal", "financial times", "ft", "yahoo",
           "marketwatch", "investing", "fxstreet", "fed", "associated press", "ap news", "barron", "forbes",
           "the economist", "kitco", "nikkei", "axios", "politico", "new york times", "washington post", "bbc", "cnn"]
RUIDO = (r"gold (?:price|rate)s? today|rate today in|per tola|22k|24k|check latest rates|prices in (?:delhi|mumbai)"
         r"|price prediction for today|gold price in bangladesh|gold price update")


def ahora_utc():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def hace(dias=0, horas=0):
    return ahora_utc() - timedelta(days=dias, hours=horas)


def clave(texto):
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:16]


def leer_json(ruta, defecto=None):
    p = Path(ruta)
    if not p.exists():
        return defecto
    return json.loads(p.read_text(encoding="utf-8"))


def guardar_json(ruta, obj, compacto=False):
    p = Path(ruta)
    p.parent.mkdir(parents=True, exist_ok=True)
    txt = (json.dumps(obj, ensure_ascii=False, separators=(",", ":")) if compacto
           else json.dumps(obj, ensure_ascii=False, indent=1))
    p.write_text(txt + "\n", encoding="utf-8")


def temas_de(titulo):
    return [t for t, rx in TEMAS if re.search(rx, titulo, re.I)]


def es_grande(medio):
    m = (medio or "").lower()
    return any(g in m for g in GRANDES)


def limpiar(x, n=None):
    x = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", x or "")).strip()
    return x[:n].rsplit(" ", 1)[0] + "…" if n and len(x) > n else x
