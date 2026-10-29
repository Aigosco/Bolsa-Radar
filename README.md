# Bolsa-Radar

Noticias, calendario económico, mercado, bonos, bot de tendencia y tesis de analistas en una página que se actualiza
sola durante todo el día. Todo corre en GitHub Actions; la página se publica con GitHub Pages y lee los datos en vivo
desde este repo.

## Qué se actualiza y cuándo

| Flujo | Frecuencia | Qué hace |
|---|---|---|
| `noticias.yml` | 7, 8 y 9 a. m. Colombia, L-V | Lee 27 feeds RSS (Bloomberg, Reuters vía Google News, WSJ, FT, CNBC, Yahoo, Investing, FXStreet, Fed…) y guarda cada titular una vez en `datos/titulares/AAAA/MM/DD.jsonl` |
| `mercado.yml` | cada 30 min | Calendario de Forex Factory y foto de mercado (Yahoo) |
| `mercado.yml` | 22:43 UTC | Cierre diario: historia de precios desde 2005, bonos del Tesoro, valor relativo, verificación de tesis |
| `resumen.yml` | 08:15 Bogotá, todos los días | Lectura del momento con Claude (necesita el secreto `ANTHROPIC_API_KEY`) |
| `pagina.yml` | al cambiar `sitio/` | Publica la página |

Desde el PC (MT5 y YouTube no funcionan en la nube): `python local/publicar_desde_pc.py` sube el estado del bot (sin datos
de la cuenta), las tesis de analistas, el radar de acciones y el efecto histórico de las noticias.

## Por qué cada 15 minutos
Medido el 2026-10-18: Investing.com publica unos 20 titulares por hora y su feed solo trae 10 (cubre ~30 min); Yahoo
cubre 7–12 h; Google News ~1 día. Leer cada hora perdería la mayoría de Investing.

## Datos para estrategias
- `datos/titulares/…jsonl`: un titular por línea con `publicado` (del medio) y `capturado` (cuando lo leímos). Para
  backtesting usar `capturado`: es la hora en que la información estuvo disponible.
- `datos/precios/*.csv`, `datos/tesoro.csv`, `datos/calendario/AAAA-MM.json`.
- Lectura directa: `https://raw.githubusercontent.com/Aigosco/Bolsa-Radar/main/datos/…`

No es asesoría financiera.
