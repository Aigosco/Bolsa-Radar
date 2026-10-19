# Bolsa-Radar: contexto completo para retomar en cualquier sesión

Responde SIEMPRE en español. Este archivo es la fuente de verdad del sistema: léelo entero antes de tocar nada. Al
terminar un cambio relevante, actualiza la sección "Estado y pendientes" de abajo.

## 1. Qué es
Un sistema de información de mercados que trabaja **entre el PC del usuario y la nube (GitHub)**:
- **La nube** (GitHub Actions, repo público `Aigosco/Bolsa-Radar`) recoge noticias, calendario económico, precios, bonos y
  verifica las tesis de analistas, todo el día, aunque el PC esté apagado.
- **El PC** hace lo que la nube no puede: MetaTrader 5 (bot de trading en demo), YouTube (bloquea a los servidores de
  GitHub) y, mientras la API de Anthropic no tenga saldo, la lectura con IA (Claude Code con el plan Pro del usuario).
- **La página** https://aigosco.github.io/Bolsa-Radar/ (GitHub Pages) lo muestra todo y se actualiza sola: lee los JSON de
  `datos/web/` directamente de `raw.githubusercontent.com`, así que no hace falta republicarla para que cambien los datos.

Usuario: trader/inversor en Colombia (hora de Bogotá, UTC−5). Sigue oro, plata, BTC, índices de EE. UU. y al analista
José Luis Cava. Correo: nefranco93@gmail.com. El repo está en la cuenta **Aigosco** (la de `gh` en este PC); la idea a
futuro es transferirlo a la cuenta de nefranco93 (si se hace: cambiar `REPO` en `sitio/app.js` y la URL de este archivo).

## 0. Orden de arranque: "ejecutar bolsa"
Cuando el usuario encienda el PC y diga **"ejecutar bolsa"** (o "arranca todo", o `/ejecutar-bolsa`), se usa la skill
personal `C:\Users\franc\.claude\skills\ejecutar-bolsa\SKILL.md`. Esa skill corre `local/arrancar.py`, que hace esto:
1. abre MT5 (`C:\Program Files\MetaTrader 5 IC Markets Global\terminal64.exe`) y espera a que conecte; avisa si "Algo Trading"
   está apagado;
2. arranca el bot (`Trading\iniciar_bot_tendencia.bat`, en su ventana) si no corre;
3. ejecuta `git pull`;
4. lanza noticias y mercado en la nube (con cierre diario si falta) y espera a que terminen;
5. revisa los videos nuevos de Cava;
6. genera la lectura con IA si no hay una de hoy;
7. publica desde el PC;
8. muestra el estado.

El usuario también puede hacer doble clic en `local\arrancar.bat`. Al terminar, se informa de cada paso en español.

## 2. Rutas
| Qué | Dónde |
|---|---|
| Este repo (copia local) | `C:\Users\franc\Bolsa-Radar` (fuera de OneDrive a propósito) |
| Proyecto local de trading (bot, laboratorio, bases grandes, transcripciones) | `C:\Users\franc\OneDrive\Desktop\Proyectos Python\Trading` — tiene su propio `CLAUDE.md` |
| Python a usar en el PC | `C:\Users\franc\OneDrive\Desktop\Proyectos Python\Trading\.venv\Scripts\python.exe` (Python 3.13, tiene yfinance, pandas, yt-dlp, MetaTrader5, anthropic) |
| Claude Code (para llamadas sin ventana) | `C:\Users\franc\.local\bin\claude.exe` |
| GitHub | https://github.com/Aigosco/Bolsa-Radar · Actions: /actions · Secretos: /settings/secrets/actions |

En Bash usa `PYTHONIOENCODING=utf-8`; en `.bat` ya está puesto (la consola cp1252 rompe los `print` con acentos).

## 3. Calendario diario (hora de Bogotá)
| Hora | Dónde | Qué | Archivo |
|---|---|---|---|
| cada 15 min (:04 :19 :34 :49 UTC) | Nube | Noticias de 28 feeds RSS | `.github/workflows/noticias.yml` → `radar/noticias.py` |
| cada 30 min (:11 :41 UTC) | Nube | Calendario Forex Factory + foto de mercado (Yahoo) | `mercado.yml` → `radar/calendario.py`, `radar/mercado.py` |
| 17:43 (22:43 UTC) | Nube | Cierre diario: historia de precios desde 2005, bonos del Tesoro, valor 10 años, **verificación de tesis** | `mercado.yml` (`--diario`) → `radar/mercado.py --diario`, `radar/tesis.py` |
| 5:00–8:40 | YouTube | Cava publica su video (03:00–06:40 hora del Pacífico, medido en 12 videos), L-V; los subtítulos automáticos tardan un rato más en aparecer | — |
| **7:30–16:30 L-V, cada hora** | PC | Videos nuevos de Cava (reintenta cada hora mientras no haya subtítulos) → transcripción → tesis con Claude Code → GitHub | tarea "Bolsa-Radar videos de Cava" → `local/cava_diario.bat` |
| **8:10 diario** | PC | Lectura del día con IA (Claude Code, plan Pro) → `datos/web/resumen.json` | tarea "Bolsa-Radar lectura IA" → `local/lectura_ia_pc.bat` |
| **cada hora (:05)** | PC | Estado del bot (MT5), tesis, radar de acciones, efecto F1 → GitHub | tarea "Bolsa-Radar publicar desde PC" → `local/publicar_desde_pc.bat` |
| **cada 15 min** | PC | Respaldo: si GitHub no corrió noticias en 20 min (o mercado en 40), los lanza con `gh workflow run` | tarea "Bolsa-Radar respaldo nube" → `local/respaldo_nube.bat` (log `%TEMP%\bolsa_radar_respaldo.log`) |
| al cambiar `sitio/` | Nube | Publica la página | `pagina.yml` |
| (en pausa) 8:15 | Nube | Lectura con IA vía API | `resumen.yml` — horario comentado hasta que la API tenga saldo |

Los cron de GitHub son aproximados (pueden retrasarse minutos). Las tareas del PC solo corren con la sesión de Windows
abierta ("Solo interactivo") y necesitan MT5 abierto para la parte del bot. Logs del PC: `%TEMP%\bolsa_radar_cava.log`,
`%TEMP%\bolsa_radar_lectura.log`, `%TEMP%\bolsa_radar_publicar.log`.

## 4. Código
```
radar/            (corre en la nube y en el PC)
  comun.py        rutas, hora, JSON, temas de titulares (TEMAS/RUIDO/GRANDES)
  noticias.py     FEEDS; guarda cada titular una vez (vistos.json, 60 días) en datos/titulares/AAAA/MM/DD.jsonl; web/titulares.json
  calendario.py   Forex Factory del mes → datos/calendario/AAAA-MM.json; web/agenda.json con efecto histórico F1
  mercado.py      ACTIVOS (16, tickers Yahoo); foto → web/mercado.json; --diario: precios/*.csv, valor.json, tesoro.csv, bonos.json
  tesis.py        verifica datos/tesis/<autor>/*.json con precios → web/tesis.json (marcador, recientes, cerradas, pendientes)
  resumen.py      paquete del día (desde web/*.json) + ESQUEMA/SISTEMA de la lectura con IA; llama a la API (ia.py)
  ia.py           cliente de Claude (Opus 5.5, salida JSON con esquema, fallbacks "default"; admite ANTHROPIC_WORKSPACE_ID)
local/            (solo en el PC)
  publicar_desde_pc.py   bot.json (sin datos de cuenta), tesis, radar.json, f1_efecto.json; --historico; git push
  cava_diario.py         últimos 5 videos de Cava → transcripción (fundamental/youtube.py del proyecto local) → tesis con
                         `claude -p --json-schema` (reglas de fundamental/analistas.py) → comprueba citas → publica
  lectura_ia_pc.py       misma lectura que resumen.py pero con `claude -p --json-schema` (plan Pro)
sitio/            la página: index.html + estilo.css + app.js (sin librerías; se refresca cada 5 min)
scripts/subir_datos.sh   commit + push con reintentos desde Actions (todos los flujos comparten la cola "escritura-datos")
datos/            todo lo publicado (ver sección 5)
```

## 5. Datos (para la página y para estrategias)
- `datos/titulares/AAAA/MM/DD.jsonl`: un titular por línea `{id, feed, medio, titulo, resumen, enlace, publicado, capturado}`.
  **En backtesting usar `capturado`** (cuándo estuvo disponible), no `publicado`.
- `datos/calendario/AAAA-MM.json`, `datos/precios/<CLAVE>.csv` (fecha, cierre, maximo, minimo; desde 2005),
  `datos/precios/extra/*.csv` (tickers de tesis), `datos/tesoro.csv`, `datos/tesis/cava/<video_id>.json`,
  `datos/f1_efecto.json`, `datos/resumen/paquete_*.md` (lo que vio la IA, para auditar).
- `datos/web/*.json`: lo que lee la página (resumen, mercado, agenda, titulares, bot, bonos, valor, tesis, radar).
- Lectura directa desde cualquier sitio: `https://raw.githubusercontent.com/Aigosco/Bolsa-Radar/main/datos/...`

## 6. Reglas (decididas por el usuario; no romperlas)
1. **Nunca inventar datos.** Si una fuente falla, se dice "sin datos"; nada de valores de relleno.
2. **El repo es PÚBLICO** (para tener Actions y Pages gratis): jamás subir el número de cuenta de MT5, el balance, resultados
   en USD, el portafolio personal ni transcripciones completas (derechos de autor). Las claves solo como *secrets*.
3. **Tesis de analistas:** solo lo que el autor dice, con cita literal y minuto; correcciones del reconocimiento de voz entre
   corchetes; si dio un nivel o un %, la verificación exige que el precio lo alcance; condicionales y fechas futuras no se
   miden hasta su disparador.
4. **Lectura con IA:** una vez al día por la mañana (no tres). Solo con el paquete de datos; las ideas son para discutir.
5. **YouTube:** nunca listar el canal entero (provocó un bloqueo de IP el 2026-10-17); solo los últimos 3–5 videos.
6. El bot de trading está en **demo** y no se cambian sus parámetros durante la prueba (ver CLAUDE.md del proyecto Trading).

## 7. Cómo operar (comandos frecuentes)
Desde `C:\Users\franc\Bolsa-Radar` con el Python del PC (`$PY`):
- Estado de la nube: `gh run list -R Aigosco/Bolsa-Radar --limit 10` · solo programadas: `--event schedule`
- Lanzar a mano: `gh workflow run noticias.yml` · `gh workflow run mercado.yml -f diario=true` · `gh workflow run pagina.yml`
- Ver el log de una ejecución: `gh run view <id> --log | grep -E "fallo|web/|Push"`
- Tareas del PC: `schtasks /Query /TN "Bolsa-Radar videos de Cava" /FO LIST` (igual con "lectura IA" y "publicar desde PC");
  ejecutar ya: `schtasks /Run /TN "<nombre>"`
- Analizar un video concreto de Cava: `$PY local/cava_diario.py --video <ID>`
- Rehacer la lectura del día: `$PY local/lectura_ia_pc.py`
- Publicar ya lo del PC: `$PY local/publicar_desde_pc.py`
- Probar la página en local: `$PY -m http.server 8765` y abrir http://127.0.0.1:8765/sitio/ (lee `../datos/web/`)
- Antes de editar en local: `git pull --rebase -X theirs` (los flujos de la nube hacen commits cada 15 min).
- Commits: autor `Aigosco <nefranco93@gmail.com>` y al final del mensaje las líneas `Co-Authored-By:` que indique el sistema.

## 8. Problemas conocidos y cómo se resolvieron
- **FXStreet** responde 403 a los servidores de GitHub → se lee vía Google News (`google/fxstreet`).
- **Investing.com** publica ~20 titulares/hora y su feed trae 10 → refuerzo con `google/investing`; por eso se lee cada 15 min.
- **Forex Factory** sí funciona desde GitHub (comprobado 2026-10-19). Su impacto viene en minúsculas ("high").
- **API de Anthropic:** la clave debe pertenecer a un *workspace* (la de alcance "Organización" da error 400). La clave del
  workspace Default ya está en el secreto `ANTHROPIC_API_KEY`, pero la cuenta no tiene saldo ("credit balance is too low").
- **Heredocs en Git Bash** pueden estropear caracteres no ASCII (·, ó) y las barras invertidas: para editar código con tildes
  usa la herramienta de edición, no `sed`/heredoc.
- Yahoo da futuros continuos (oro GC=F) que difieren unos dólares del contado del bróker; los niveles del bot salen de MT5.

## 9. Estado y pendientes (actualizar al cerrar cada sesión)
Último estado: 2026-10-19.
- Funcionando: noticias, mercado, calendario, tesis (40 videos de Cava, 224 tesis), página, bot.json, lectura IA desde el PC,
  extracción automática de videos nuevos de Cava (probada: 11 tesis, 0 citas no literales, 30 s).
- **Vigilar:** a las 06:22 UTC del 19-oct GitHub aún no había disparado NINGUNA ejecución programada (solo las manuales),
  ni tras mover los cron a minutos poco concurridos. Mientras tanto, el respaldo del PC ("Bolsa-Radar respaldo nube",
  cada 15 min) las lanza. Comprobar con `gh run list -R Aigosco/Bolsa-Radar --event schedule`. Si GitHub empieza a
  dispararlas, el respaldo no hace nada (solo actúa si no hubo ejecución reciente). Con el PC apagado y sin cron de GitHub,
  la nube no se actualiza: es el punto débil a resolver (posibles causas: retraso de GitHub en repos nuevos; si persiste
  días, contactar soporte de GitHub o usar un disparador externo).
- Pendiente del usuario: cargar saldo en la API (platform.claude.com → Facturación) y entonces descomentar el horario de
  `resumen.yml` y desactivar la tarea "Bolsa-Radar lectura IA"; decidir si transferir el repo a la cuenta nefranco93.
- Ideas aparcadas: correo diario (sustituido por la página), n8n, filtro de riesgo electoral y VIX>20 en el laboratorio,
  estrategia del "truco" de Cava (ruptura de lateral + retesteo) en el laboratorio.
