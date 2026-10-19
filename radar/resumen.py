"""Lectura del momento con IA (Claude) a partir de los datos ya publicados → datos/web/resumen.json.

Se ejecuta 3 veces al día en GitHub Actions (cierre de Asia, mañana de NY y cierre de NY) si existe el secreto
ANTHROPIC_API_KEY. El paquete que recibe Claude se guarda en datos/resumen/paquete_AAAA-MM-DD_HH.md para poder auditar
de dónde sale cada afirmación. Sin clave: no hace nada (la página muestra la última lectura disponible).

  python -m radar.resumen [--solo-paquete]
"""
import sys

from .comun import DATOS, WEB, ahora_utc, guardar_json, iso, leer_json
from . import ia

ESQUEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["lo_esencial", "temas", "ideas", "analistas", "vigilar"],
    "properties": {
        "lo_esencial": {"type": "array", "items": {"type": "string"}},
        "temas": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["tema", "que_paso", "coinciden", "discrepan", "efecto_posible", "medios"],
            "properties": {"tema": {"type": "string"}, "que_paso": {"type": "string"}, "coinciden": {"type": "string"},
                           "discrepan": {"type": "string"}, "efecto_posible": {"type": "string"},
                           "medios": {"type": "array", "items": {"type": "string"}}}}},
        "ideas": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["activo", "horizonte", "idea", "a_favor", "en_contra", "que_la_invalida"],
            "properties": {"activo": {"type": "string"}, "horizonte": {"type": "string", "enum": ["corto", "mediano", "largo"]},
                           "idea": {"type": "string"}, "a_favor": {"type": "string"}, "en_contra": {"type": "string"},
                           "que_la_invalida": {"type": "string"}}}},
        "analistas": {"type": "string"},
        "vigilar": {"type": "array", "items": {"type": "string"}},
    },
}
SISTEMA = """Preparas la lectura de mercado de una página que un inversor/trader consulta durante el día. Trabajas SOLO con
el paquete de datos que recibes: titulares (medio y hora), calendario, precios, bonos, estado del bot y tesis de analistas
con su verificación. No uses conocimiento externo de noticias ni inventes cifras, niveles ni hechos: si algo no está en el
paquete, no lo afirmes. Distingue hecho de interpretación. Cuando un tema aparece en varios medios, di en qué coinciden y en
qué difieren. Las ideas son para DISCUTIR, no órdenes: cada una con argumentos a favor, en contra y qué la invalidaría.
Ten presente lo medido (estudio F1): las noticias mueven en los primeros minutos y no deciden la tendencia del día; son
contexto y filtro de riesgo, no gatillo. Escribe en español, claro, frases cortas, sin adornos."""


def paquete():
    ahora = ahora_utc()
    p = [f"# Paquete {iso(ahora)}"]
    tit = leer_json(WEB / "titulares.json", {})
    p.append(f"\n## Titulares por tema (últimas 36 h; {tit.get('total_24h')} en 24 h)")
    for g in tit.get("temas", []):
        p.append(f"\n### {g['tema']} ({g['n_24h']} en 24 h, {g['medios']} medios)")
        p += [f"- {t['publicado'][:16]} · {t['medio']}: {t['titulo']}" for t in g["titulares"]]
    ag = leer_json(WEB / "agenda.json", {})
    p.append("\n## Calendario (24 h atrás → 7 días; hora UTC)")
    for e in ag.get("eventos", []):
        real = f" | real {e['actual']}" if e.get("actual") else ""
        p.append(f"- {e['fecha_utc']} {e['moneda']} [{e['impacto']}] {e['nombre']} | previsión {e['previsto']} | "
                 f"anterior {e['anterior']}{real}")
    m = leer_json(WEB / "mercado.json", {})
    p.append("\n## Mercado (Yahoo): activo | último | 1 d % | 5 d % | 1 mes % | vs media 200 d % | tend. diaria | tend. 4h")
    for a in m.get("activos", []):
        if not a.get("sin_datos"):
            p.append(f"- {a['nombre']} | {a['ultimo']} | {a['ch_1d']} | {a['ch_5d']} | {a['ch_1m']} | {a['vs_ma200']} | "
                     f"{a['tend_diaria']} | {a['tend_4h']}")
    b = leer_json(WEB / "bonos.json", {})
    for f in b.get("tabla", []):
        p.append(f"- Bono {f['nombre']}: {f['ultimo']} ({f['d1_pb']:+} pb 1 d, {f['d5_pb']:+} pb 1 sem) al {f['fecha']}")
    bot = leer_json(WEB / "bot.json", {})
    p.append(f"\n## Bot de tendencia (demo): {len(bot.get('posiciones', []))} posiciones")
    p += [f"- {s['simbolo']} ({s['estrategia']}): {s['distancia']}" for s in bot.get("senales", [])]
    ef = leer_json(DATOS / "f1_efecto.json", {})
    if ef:
        p.append("\n## Estudio F1 (efecto histórico de noticias USD de alto impacto)\n" + ef.get("_nota", ""))
        for fam in ("Fed", "Empleo", "Inflación", "Actividad"):
            o = ef.get(fam, {}).get("XAUUSD")
            s = ef.get(fam, {}).get("US500")
            if o and s:
                p.append(f"- {fam}: oro 'de libro' {o['libro_15m']:.0%} a 15 min, mueve {o['mov_1h']}% (p90 {o['p90_1h']}%) "
                         f"en 1 h; S&P 'de libro' {s['libro_15m']:.0%} a 15 min")
    ts = leer_json(WEB / "tesis.json", {})
    p.append(f"\n## Analistas: marcador {ts.get('marcador', [])[:6]}")
    for t in ts.get("recientes", [])[:30]:
        p.append(f"- {t['fecha_video']} {t['autor']}: [{t['tipo']}] {t['activo']} {t['direccion']} {t['horizonte']} — "
                 f"«{t['cita'][:220]}» → {t['estado']}")
    return "\n".join(p)


def main(llamar=True):
    ahora = ahora_utc()
    txt = paquete()
    ruta = DATOS / "resumen" / f"paquete_{ahora:%Y-%m-%d_%H}.md"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(txt, encoding="utf-8")
    print(f"paquete: {ruta.name} ({len(txt)} caracteres)")
    if not llamar:
        return
    if not ia.disponible():
        print("Sin ANTHROPIC_API_KEY: no se genera la lectura con IA.")
        return
    try:
        d, info = ia.pedir_json(SISTEMA, txt, ESQUEMA, esfuerzo="high")
    except RuntimeError as e:
        print("IA:", e)
        return
    d.update({"generado": iso(ahora), "modelo": info["modelo"], "paquete": ruta.name})
    guardar_json(WEB / "resumen.json", d)
    print(f"web/resumen.json ({info['entrada']}+{info['salida']} tokens)")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(llamar="--solo-paquete" not in sys.argv)
