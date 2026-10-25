/* Bolsa-Radar: lee los JSON de datos/web (en GitHub: raw.githubusercontent.com, siempre lo último del repo),
   dibuja cada sección y se refresca sola cada 5 minutos. Cada sección falla por separado sin romper las demás.
   Todo lo que se muestra es una guía para la acción: cada activo abre su ficha (gráficos, niveles y plan). */
"use strict";

const REPO = "Aigosco/Bolsa-Radar";
const BASE = location.hostname.endsWith("github.io")
  ? `https://raw.githubusercontent.com/${REPO}/main/datos/web/`
  : "../datos/web/";
const ARCHIVOS = ["resumen", "mercado", "agenda", "titulares", "bot", "bonos", "valor", "tesis", "radar"];
const D = {};
let temaSel = null, radarSel = 0, grupoSel = "Principales", fichaAbierta = null;
let idioma = "es";
try { idioma = localStorage.getItem("radar-idioma") || "es"; } catch (e) { /* sin almacenamiento */ }
const TIPOS = { prediccion: "predicción", recomendacion: "recomendación", diagnostico: "diagnóstico" };
const PRINCIPALES = ["XAUUSD", "XAGUSD", "BTCUSD", "US500", "USTEC", "XTIUSD", "EURUSD", "DXY"];
const NIVEL_TXT = { alta: "Alta probabilidad", media: "Media probabilidad", baja: "Baja probabilidad" };

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const fmt = (v, d = 2) => v == null || Number.isNaN(v) ? "–" : Number(v).toLocaleString("es-CO", { minimumFractionDigits: d, maximumFractionDigits: d });
const pct = (v, d = 2) => v == null ? "–" : `${v > 0 ? "+" : ""}${fmt(v, d)} %`;
const clase = (v) => v == null ? "" : v > 0 ? "sube" : v < 0 ? "baja" : "";
const decimales = (v) => { const a = Math.abs(v); return a >= 1000 ? 0 : a >= 100 ? 2 : a >= 10 ? 2 : a >= 1 ? 4 : 5; };
const precio = (v, ref) => fmt(v, decimales(ref ?? v));
const activo = (clave) => (D.mercado?.activos || []).find((a) => a.clave === clave);

function hora(dt, tz) {
  return new Intl.DateTimeFormat("es-CO", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: tz }).format(dt);
}
function fechaCorta(dt, tz) {
  return new Intl.DateTimeFormat("es-CO", { weekday: "short", day: "2-digit", timeZone: tz }).format(dt).replace(".", "");
}
function fechaLarga(iso) {
  return new Intl.DateTimeFormat("es-CO", { day: "numeric", month: "short", timeZone: "America/Bogota" }).format(new Date(iso)).replace(".", "");
}
function haceTxt(iso) {
  if (!iso) return "–";
  const m = Math.round((Date.now() - new Date(iso)) / 60000);
  if (m < 1) return "ahora";
  if (m < 60) return `hace ${m} min`;
  const h = Math.floor(m / 60);
  return h < 48 ? `hace ${h} h ${m % 60 ? (m % 60) + " min" : ""}`.trim() : `hace ${Math.floor(h / 24)} días`;
}
function minutosNY(dt) {
  const p = new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "numeric", hour12: false, timeZone: "America/New_York" }).formatToParts(dt);
  const h = +p.find((x) => x.type === "hour").value % 24, m = +p.find((x) => x.type === "minute").value;
  return h * 60 + m;
}

/* ---------- tooltip ---------- */
const tip = $("tooltip");
function mostrarTip(html, x, y) {
  tip.innerHTML = html; tip.hidden = false;
  const r = tip.getBoundingClientRect();
  tip.style.left = Math.max(8, Math.min(window.innerWidth - r.width - 8, x + 12)) + "px";
  tip.style.top = Math.max(8, y - r.height - 10) + "px";
}
function ocultarTip() { tip.hidden = true; }
function conTips(raiz) {
  raiz.querySelectorAll("[data-tip]").forEach((c) => {
    c.addEventListener("pointermove", (ev) => mostrarTip(c.dataset.tip, ev.clientX, ev.clientY));
    c.addEventListener("pointerleave", ocultarTip);
  });
}

/* ---------- carga ---------- */
async function bajarJSON(n) {
  const r = await fetch(`${BASE}${n}.json?t=${Date.now()}`, { cache: "no-store" });
  return r.ok ? r.json() : null;
}
async function cargar() {
  await Promise.all(ARCHIVOS.map(async (n) => {
    try { const j = await bajarJSON(n); if (j) D[n] = j; } catch (e) { /* se queda con lo anterior */ }
  }));
  if (D.graficos) { try { D.graficos = (await bajarJSON("graficos")) || D.graficos; } catch (e) { /* nada */ } }
  pintar();
  if (fichaAbierta) seguro(() => pintarFicha(fichaAbierta));
}
async function graficos() {
  if (!D.graficos) { try { D.graficos = await bajarJSON("graficos"); } catch (e) { /* sin gráficos */ } }
  return D.graficos;
}
function seguro(fn) { try { fn(); } catch (e) { console.error(fn.name, e); } }
function pintar() {
  [frescura, sesiones, lectura, agenda, tablero, bot, ideas, titulares, bonos, valor, analistas, radar, pie].forEach(seguro);
}

/* ---------- barra superior ---------- */
function relojes() {
  const ahora = new Date();
  $("reloj-co").textContent = hora(ahora, "America/Bogota");
  $("reloj-ny").textContent = hora(ahora, "America/New_York");
  $("reloj-lo").textContent = hora(ahora, "Europe/London");
}
function frescura() {
  const n = D.titulares?.generado, m = D.mercado?.generado;
  const viejo = (iso, min) => !iso || (Date.now() - new Date(iso)) / 60000 > min;
  $("frescura").innerHTML =
    `<span class="${viejo(n, 45) ? "viejo" : "ok"}">Noticias ${haceTxt(n)}</span>` +
    `<span class="${viejo(m, 75) ? "viejo" : "ok"}">Mercado ${haceTxt(m)}</span>`;
}

/* ---------- sesiones (24 h en hora de Nueva York) ---------- */
const SESIONES = [
  { n: "Asia", a: 19 * 60, b: 28 * 60, c: "var(--asia)" },
  { n: "Londres", a: 3 * 60, b: 12 * 60, c: "var(--londres)" },
  { n: "Nueva York", a: 8 * 60, b: 17 * 60, c: "var(--ny)" },
];
function sesiones() {
  const el = $("linea-sesiones"), W = el.clientWidth || 900, H = 96, x0 = 8, x1 = W - 8;
  const X = (min) => x0 + (x1 - x0) * (((min % 1440) + 1440) % 1440) / 1440;
  const ahoraMin = minutosNY(new Date());
  let s = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">`;
  SESIONES.forEach((ss, i) => {
    const y = 8 + i * 18;
    const tramos = ss.b > 1440 ? [[ss.a, 1440], [0, ss.b - 1440]] : [[ss.a, ss.b]];
    tramos.forEach(([a, b]) => { s += `<rect x="${X(a)}" y="${y}" width="${X(b === 1440 ? 1439.9 : b) - X(a)}" height="14" rx="3" fill="${ss.c}"/>`; });
    s += `<text class="banda-etq" x="${X(ss.a > 1200 ? 0 : ss.a) + 6}" y="${y + 11}">${ss.n}</text>`;
  });
  for (let h = 0; h <= 24; h += 3) {
    const x = X(h === 24 ? 1439.9 : h * 60);
    s += `<line x1="${x}" x2="${x}" y1="63" y2="67" stroke="var(--linea)"/><text x="${x}" y="80" text-anchor="${h === 0 ? "start" : h === 24 ? "end" : "middle"}">${String(h).padStart(2, "0")}:00</text>`;
  }
  s += `<line x1="${x0}" x2="${x1}" y1="63" y2="63" stroke="var(--linea)"/>`;
  const hoyNY = new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York" }).format(new Date());
  (D.agenda?.eventos || []).forEach((e) => {
    const dt = new Date(e.t * 1000);
    if (new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York" }).format(dt) !== hoyNY) return;
    const x = X(minutosNY(dt)), alto = e.impacto?.toLowerCase() === "high";
    s += `<circle class="evento ${alto ? "" : "medio"}" cx="${x}" cy="63" r="${alto ? 5 : 4}" data-tip="${esc(hora(dt, "America/New_York") + " NY · " + e.moneda + " " + e.nombre)}"/>`;
  });
  const xa = X(ahoraMin);
  s += `<line class="ahora" x1="${xa}" x2="${xa}" y1="2" y2="69"/><text class="ahora-etq" x="${Math.min(Math.max(xa, 30), W - 30)}" y="93" text-anchor="middle">ahora</text></svg>`;
  el.innerHTML = s;
  conTips(el);
  const abiertas = SESIONES.filter((ss) => (ahoraMin >= ss.a && ahoraMin < ss.b) || (ss.b > 1440 && ahoraMin < ss.b - 1440)).map((ss) => ss.n);
  const dia = new Date().toLocaleDateString("en-US", { weekday: "short", timeZone: "America/New_York" });
  const finde = (dia === "Sat") || (dia === "Sun" && ahoraMin < 17 * 60);
  $("sesion-ahora").textContent = finde ? "Fin de semana: solo cotiza cripto." : abiertas.length ? `Abierta ahora: ${abiertas.join(" y ")}.` : "Entre sesiones.";
}

/* ---------- lo esencial ---------- */
function lectura() {
  const r = D.resumen;
  if (!r) { $("esencial").innerHTML = `<li class="vacio">Aún no hay lectura con IA.</li>`; return; }
  $("lectura-meta").textContent = `Lectura con IA ${haceTxt(r.generado)}`;
  $("esencial").innerHTML = (r.lo_esencial || []).map((x) => `<li>${esc(x)}</li>`).join("");
  $("vigilar").innerHTML = (r.vigilar || []).map((x) => `<li>${esc(x)}</li>`).join("");
}

/* ---------- textos de los planes ---------- */
function linea(p, ref) {
  const rel = p.accion === "compra" ? "sobre" : "bajo";
  return `<b>${p.accion === "compra" ? "Compra" : "Venta"}</b> si una vela de 4h cierra ${rel} <b class="num">${precio(p.gatillo, ref)}</b>` +
    ` · stop <span class="num">${precio(p.stop, ref)}</span> · objetivo <span class="num">${precio(p.objetivo, ref)}</span>`;
}
function porQue(p) {
  if (p.estado === "posible") return "las tendencias diaria y de 4h acompañan";
  if (p.estado === "cautela") return `solo acompaña la tendencia ${p.a_favor.join(" y ")}; la otra va en contra`;
  return "va contra las tendencias diaria y de 4h";
}
function labTxt(p) {
  const L = p.lab;
  if (!L) return "";
  const r = (v) => `${v >= 0 ? "+" : ""}${fmt(v)} R`;
  if (L.swap_dudoso) return `Laboratorio 2020-2026 (${L.ops} operaciones): ${L.E_ss != null ? `${r(L.E_ss)} por operación sin swap (factor de beneficio ${fmt(L.PF_ss)})` : `${r(L.E)} por operación`}; el resultado con swap del petróleo no es fiable`;
  if (L.E_ss != null) return `Laboratorio 2020-2026 (${L.ops} operaciones): ${r(L.E_ss)} por operación sin swap y ${r(L.E)} con swap (factor de beneficio ${fmt(L.PF_ss)} / ${fmt(L.PF)})`;
  return `Laboratorio 2020-2026 (${L.ops} operaciones): ${r(L.E)} por operación con swap, factor de beneficio ${fmt(L.PF)}`;
}
const may = (s) => s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
function etiquetaProb(n) { return `<span class="nivel ${n}">${NIVEL_TXT[n]}</span>`; }
function extras(p) {
  const x = [];
  if (p.ya_roto) x.push("el precio ya pasó el gatillo: no perseguir, esperar retroceso");
  else x.push(`gatillo a ${fmt(Math.abs(p.distancia_pct))} % del precio (${fmt(p.distancia_atr, 1)} velas de 4h de recorrido medio)`);
  if (!p.ya_roto && p.distancia_atr > 3) x.push("lejos: poco probable en esta sesión");
  x.push(`riesgo ${fmt(p.riesgo_pct)} % hasta el stop (${p.stop_es})`);
  return x.join(" · ");
}
function fraseVeredicto(v) {
  if (v.motivo === "en_linea") return "El dato salió en línea con la previsión: no hay sorpresa que aprovechar. No entrar por esta noticia.";
  if (v.motivo === "sin_datos" || !v.accion) return "Sin niveles suficientes para un plan.";
  const ref = activo(v.clave)?.ultimo ?? v.gatillo;
  const quien = `<button type="button" class="enlace-activo" data-clave="${esc(v.clave)}">${esc(v.nombre)}</button>`;
  const rel = v.accion === "compra" ? "sobre" : "bajo";
  const cond = v.publicado ? "" : `Si sale el ${esc(v.si.replace(/^dato /, "dato "))}: `;
  let t = `${cond}${v.accion === "compra" ? "compra" : "venta"} de ${quien} si una vela de 4h cierra ${rel} <b class="num">${precio(v.gatillo, ref)}</b>, stop <span class="num">${precio(v.stop, ref)}</span>, objetivo <span class="num">${precio(v.objetivo, ref)}</span>.`;
  t += ` ${v.nivel === "alta" ? "Alta probabilidad" : v.nivel === "media" ? "Probabilidad media" : "Baja probabilidad"}: ${esc(v.motivo)}.`;
  if (v.nivel === "baja") t += " Mejor no operar esta noticia.";
  if (v.ya_roto) t += " El precio ya pasó el gatillo: no perseguir.";
  else if (v.lejano) t += ` El gatillo está lejos (${fmt(v.distancia_atr, 1)} veces el recorrido medio de una vela de 4h): poco probable hoy.`;
  return t.charAt(0).toUpperCase() + t.slice(1);
}

/* ---------- agenda para la acción ---------- */
function cuentaAtras(t) {
  const s = Math.round(t - Date.now() / 1000);
  if (s <= 0) return "";
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  return h >= 24 ? `en ${Math.floor(h / 24)} d ${h % 24} h` : `en ${h ? h + " h " : ""}${m} min`;
}
function gruposAgenda() {
  const g = new Map();
  (D.agenda?.eventos || []).forEach((e) => {
    const k = `${e.t}-${e.moneda}`;
    if (!g.has(k)) g.set(k, []);
    g.get(k).push(e);
  });
  return [...g.values()];
}
function tarjetaEvento(evs) {
  const altos = evs.filter((e) => (e.impacto || "").toLowerCase() === "high");
  const base = (altos.find((e) => e.actual) || evs.find((e) => e.actual) || altos[0] || evs[0]);
  const gu = base.guia, v = gu.veredicto, dt = new Date(base.t * 1000), publicado = base.publicado;
  const ia = (D.resumen?.agenda_accion || []).filter((x) => evs.some((e) => e.id === x.evento_id)).map((x) => x.lectura);
  const datos = evs.map((e) => `<li><span class="impacto ${(e.impacto || "").toLowerCase()}" title="Impacto ${(e.impacto || "").toLowerCase() === "high" ? "alto" : "medio"}"></span>
      <span class="ev-nombre">${esc(e.nombre)}</span>
      <span class="valores">${e.actual ? `real <b class="${e.mejor_peor == 1 ? "sube" : e.mejor_peor == 2 ? "baja" : ""}">${esc(e.actual)}</b>` : ""}
      <span>previsión ${esc(e.previsto || "–")}</span><span>anterior ${esc(e.anterior || "–")}</span></span></li>`).join("");
  const activos = gu.activos.map((x) => {
    const escs = x.escenarios.map((s) => {
      const dado = x.realizado && s.si.startsWith(`dato ${x.realizado}`), descartado = x.realizado && !dado;
      return `<div class="esc ${descartado ? "descartado" : ""} ${dado ? "dado" : ""}">
        <div class="esc-si">Si sale ${esc(s.si.replace(/^dato /, ""))}${dado ? ` <span class="chip acento">así salió</span>` : ""}</div>
        <div class="esc-plan">${etiquetaProb(s.prob)} ${linea(s, x.ultimo)}</div>
        <div class="esc-pq">${esc(s.prob_motivo)} · ${esc(porQue(s))} · ${esc(extras(s))}${s.lab ? ` · ${esc(labTxt(s))}` : ""}</div></div>`;
    }).join("");
    const reac = x.reaccion_pct != null ? `<span class="reac">Desde el dato: <b class="${clase(x.reaccion_pct)}">${pct(x.reaccion_pct)}</b></span>` : "";
    return `<div class="ev-activo">
      <div class="ev-activo-cab"><button type="button" class="enlace-activo grande" data-clave="${esc(x.clave)}">${esc(x.nombre)} <span class="num">${precio(x.ultimo)}</span> <span aria-hidden="true">›</span></button>
        <span class="chips"><span class="chip ${x.tend_diaria || ""}">Diaria ${x.tend_diaria || "–"}</span><span class="chip ${x.tend_4h || ""}">4h ${x.tend_4h || "–"}</span></span>${reac}</div>
      ${escs}</div>`;
  }).join("");
  const ef = base.efecto?.XAUUSD ? `<p class="historial">Historial (${esc(base.familia)}, ${D.agenda?.nota_efecto ? "estudio F1" : ""}): el oro reaccionó "de libro" el ${Math.round(base.efecto.XAUUSD.libro_15m * 100)} % de las veces a los 15 min y se movió ${fmt(base.efecto.XAUUSD.mov_1h)} % en la primera hora (1 de cada 10 veces, más de ${fmt(base.efecto.XAUUSD.p90_1h)} %). La reacción ocurre en minutos: el plan entra por cierre de vela de 4h, no persiguiendo el primer impulso.</p>` : "";
  return `<article class="ev-card ${publicado ? "pasado" : ""}">
    <header class="ev-cab">
      <div class="cuando"><b>${fechaCorta(dt, "America/Bogota")} ${hora(dt, "America/Bogota")}</b><small>Bogotá · ${hora(dt, "America/New_York")} NY</small></div>
      <div class="ev-tit"><h3>${esc(base.moneda)} · ${esc(evs.length > 1 ? `${evs.length} datos` : base.nombre)}</h3><ul class="ev-datos">${datos}</ul></div>
      <div class="cuenta" data-t="${base.t}">${publicado ? "publicado" : cuentaAtras(base.t)}</div>
    </header>
    <div class="veredicto v-${v.nivel}">${etiquetaProb(v.nivel)}<p>${fraseVeredicto(v)}</p></div>
    ${ia.length ? `<p class="ia-lectura"><span class="etq">Lectura IA</span> ${ia.map(esc).join(" ")}</p>` : ""}
    <div class="ev-activos">${activos}</div>${ef}</article>`;
}
function agenda() {
  const ahora = Date.now() / 1000;
  const gs = gruposAgenda().filter((g) => g[0].t >= ahora - 12 * 3600);
  const cerca = gs.filter((g) => g[0].t <= ahora + 36 * 3600), lejos = gs.filter((g) => g[0].t > ahora + 36 * 3600);
  $("agenda").innerHTML = cerca.length ? cerca.map(tarjetaEvento).join("") : `<p class="vacio">Sin noticias con guía en las próximas 36 horas.</p>`;
  $("agenda-mas").innerHTML = lejos.map(tarjetaEvento).join("");
  $("agenda-mas-env").hidden = !lejos.length;
  $("agenda-mas-env").querySelector("summary").textContent = `Resto de la semana (${lejos.length} noticias)`;
}

/* ---------- tablero ---------- */
function sparkline(v, w = 210, h = 38) {
  if (!v || v.length < 2) return "";
  const mn = Math.min(...v), mx = Math.max(...v), rg = mx - mn || 1;
  const pts = v.map((y, i) => [2 + (w - 6) * i / (v.length - 1), 3 + (h - 6) * (1 - (y - mn) / rg)]);
  const d = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join("");
  const col = v[v.length - 1] >= v[0] ? "var(--sube)" : "var(--baja)";
  const u = pts[pts.length - 1];
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true">
    <path class="area" d="${d}L${u[0]},${h}L${pts[0][0]},${h}Z" fill="${col}"/>
    <path d="${d}" fill="none" stroke="${col}" stroke-width="1.6" vector-effect="non-scaling-stroke"/>
    <circle cx="${u[0]}" cy="${u[1]}" r="2.6" fill="${col}"/></svg>`;
}
const SESGO_TXT = { compra_alta: "Compra: alta probabilidad", compra_media: "Compra: probabilidad media",
  venta_alta: "Venta: alta probabilidad", venta_media: "Venta: probabilidad media", esperar: "Esperar: baja probabilidad" };
const sesgoClase = (s) => !s ? "" : s === "esperar" ? "esperar" : s.endsWith("alta") ? "alta" : "media";
function tablero() {
  const todos = D.mercado?.activos || [];
  const grupos = ["Principales", ...new Set(todos.map((a) => a.grupo)), "Todos"];
  $("grupos").innerHTML = grupos.map((g) => `<button class="pestana" role="tab" type="button" aria-selected="${g === grupoSel}" data-g="${esc(g)}">${esc(g)}</button>`).join("");
  $("grupos").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => { grupoSel = b.dataset.g; tablero(); }));
  const a = grupoSel === "Todos" ? todos : grupoSel === "Principales" ? PRINCIPALES.map(activo).filter(Boolean) : todos.filter((x) => x.grupo === grupoSel);
  $("tablero").innerHTML = a.map((x) => x.sin_datos ? `<div class="activo"><div class="nombre">${esc(x.nombre)}</div><div class="vacio">Sin datos</div></div>` : `
    <button type="button" class="activo" data-clave="${esc(x.clave)}" aria-label="Abrir la ficha de ${esc(x.nombre)}">
      <span class="fila"><span class="nombre">${esc(x.nombre)}</span><span class="grupo">${esc(x.grupo)}</span></span>
      <span class="fila"><span class="precio">${precio(x.ultimo)}</span><span class="var ${clase(x.ch_1d)}">${pct(x.ch_1d)} <small>hoy</small></span></span>
      ${sparkline(x.spark)}
      <span class="fila"><span class="chips">
        <span class="chip ${x.tend_diaria || ""}" title="Tendencia de fondo: precio frente a su media de 200 días">Diaria ${x.tend_diaria || "–"}</span>
        <span class="chip ${x.tend_4h || ""}" title="Tendencia de corto plazo: Supertrend 10/3 en velas de 4 h">4h ${x.tend_4h || "–"}</span></span></span>
      <span class="sesgo ${sesgoClase(x.plan?.sesgo)}">${SESGO_TXT[x.plan?.sesgo] || "Sin plan"}<span aria-hidden="true"> ›</span></span>
    </button>`).join("");
}

/* ---------- bot ---------- */
function bot() {
  const b = D.bot;
  if (!b) { $("bot").innerHTML = `<p class="vacio">El PC aún no publicó el estado del bot.</p>`; return; }
  $("bot-meta").textContent = `Demo · ${fmt(b.riesgo_por_operacion_pct, 1)} % por operación · ${haceTxt(b.generado)}`;
  const pos = (b.posiciones || []).map((p) => `<div class="senal"><div class="fila"><button type="button" class="enlace-activo grande" data-clave="${esc(p.simbolo)}">${esc(p.simbolo)} ›</button>
      <span class="chip acento">${esc(p.tipo)} · ${p.R == null ? "–" : (p.R > 0 ? "+" : "") + fmt(p.R) + " R"}</span></div>
      <div class="dist">entrada ${precio(p.entrada)} · stop ${precio(p.stop)} · ${esc(p.estrategia || "")}</div></div>`).join("");
  const sen = (b.senales || []).map((s) => {
    const m = /([+-]?\d+[.,]\d+)%\)?\s*(?:·|$)/.exec(s.distancia) || /falta \+?(\d+[.,]\d+)%/.exec(s.distancia);
    const falta = m ? Math.abs(parseFloat(m[1].replace(",", "."))) : null;
    const lleno = falta == null ? 0 : Math.max(4, 100 - Math.min(falta, 10) * 10);
    const cand = /candidata/.test(s.estrategia);
    const conFicha = !!activo(s.simbolo);
    return `<div class="senal"><div class="fila">${conFicha ? `<button type="button" class="enlace-activo grande" data-clave="${esc(s.simbolo)}">${esc(s.simbolo)} ›</button>` : `<span class="sim">${esc(s.simbolo)}</span>`}
      <span class="chip ${cand ? "" : "acento"}">${cand ? "candidata, sin bot" : "en el bot"}</span></div>
      <div class="dist">${esc(s.estrategia)} · cierre 4h ${esc(s.cierre_4h)}</div><div class="dist">${esc(s.distancia)}</div>
      ${falta != null ? `<div class="medidor" title="Cercanía a la señal (lleno = a punto)"><span style="width:${lleno}%"></span></div>` : ""}</div>`;
  }).join("");
  $("bot").innerHTML = (pos ? `<h3 class="sub">Posiciones abiertas</h3>${pos}` : `<p class="nota">Sin posiciones abiertas.</p>`) +
    `<h3 class="sub">Distancia a la señal de compra</h3>${sen}`;
}

/* ---------- ideas ---------- */
function claveDeIdea(x) {
  if (x.clave && activo(x.clave)) return x.clave;
  const t = (x.activo || "").toLowerCase();
  const a = (D.mercado?.activos || []).find((m) => t.includes(m.clave.toLowerCase()) || t.includes(m.nombre.toLowerCase()));
  return a?.clave;
}
function ideas() {
  const ii = D.resumen?.ideas || [];
  $("ideas").innerHTML = ii.length ? ii.map((x) => {
    const k = claveDeIdea(x);
    return `<article class="idea"><div class="fila">${k ? `<button type="button" class="enlace-activo grande" data-clave="${esc(k)}">${esc(x.activo)} ›</button>` : `<h3>${esc(x.activo)}</h3>`}<span class="chip">${esc(x.horizonte)}</span></div>
      <div>${esc(x.idea)}</div>${x.plan ? `<div class="idea-plan"><span class="etq">Plan</span> ${esc(x.plan)}</div>` : ""}
      <dl><div><dt>A favor</dt><dd>${esc(x.a_favor)}</dd></div><div><dt>En contra</dt><dd>${esc(x.en_contra)}</dd></div>
      <div><dt>Qué la invalida</dt><dd>${esc(x.que_la_invalida)}</dd></div></dl></article>`;
  }).join("") : `<p class="vacio">Sin ideas en la última lectura.</p>`;
}

/* ---------- titulares ---------- */
function tituloDe(x) { return idioma === "es" && x.titulo_es ? x.titulo_es : x.titulo; }
function titulares() {
  const t = D.titulares;
  if (!t) return;
  $("lang-es").setAttribute("aria-pressed", idioma === "es");
  $("lang-en").setAttribute("aria-pressed", idioma !== "es");
  $("titulares-meta").textContent = `${t.total_24h} titulares únicos en 24 h · ${haceTxt(t.generado)}${idioma === "es" ? " · traducción automática" : ""}`;
  const ph = t.por_hora || [], mx = Math.max(1, ...ph.map((x) => x.n)), W = $("actividad").clientWidth || 900, H = 46, bw = W / ph.length;
  $("actividad").innerHTML = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">${ph.map((x, i) => {
    const h = Math.max(1.5, (H - 4) * x.n / mx);
    return `<rect x="${i * bw + 1}" y="${H - h}" width="${Math.max(1, bw - 2)}" height="${h}" rx="2" data-tip="${hora(new Date(x.hora), "America/Bogota")} Bogotá · ${x.n} titulares"/>`;
  }).join("")}</svg>`;
  conTips($("actividad"));
  const temas = t.temas || [];
  if (!temaSel || !temas.find((x) => x.tema === temaSel)) temaSel = temas[0]?.tema;
  $("pestanas").innerHTML = temas.map((x) => `<button class="pestana" role="tab" type="button" aria-selected="${x.tema === temaSel}" data-tema="${esc(x.tema)}">${esc(x.tema)}<span class="c">${x.n_24h}</span></button>`).join("");
  $("pestanas").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => { temaSel = b.dataset.tema; titulares(); }));
  const g = temas.find((x) => x.tema === temaSel);
  const norm = (s) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  const temasIA = D.resumen?.temas || [];
  const ia = temasIA.find((x) => x.tema === temaSel) ||
    temasIA.find((x) => norm(x.tema).split(/[^a-z0-9]+/).some((w) => w.length > 3 && norm(temaSel || "").split(/[^a-z0-9]+/).includes(w)));
  const analisis = ia ? `<div class="analisis-tema">
      <div><b>${ia.modo === "resumen" ? "Contexto." : "Qué pasó."}</b> ${esc(ia.que_paso)}</div>${ia.coinciden ? `<div><b>Coinciden.</b> ${esc(ia.coinciden)}</div>` : ""}
      ${ia.discrepan ? `<div><b>Difieren.</b> ${esc(ia.discrepan)}</div>` : ""}${ia.efecto_posible ? `<div><b>Efecto posible.</b> ${esc(ia.efecto_posible)}</div>` : ""}
      <p class="nota">Lectura con IA ${haceTxt(D.resumen.generado)}.</p></div>`
    : `<div class="analisis-tema"><p class="nota">${g ? `${g.n_24h} titulares en 24 h de ${g.medios} medios distintos.` : ""}</p></div>`;
  $("tema-panel").innerHTML = g ? analisis + `<ul class="titulares">${g.titulares.map((x) => `<li><span class="t">${hora(new Date(x.publicado), "America/Bogota")}</span>
      <div><a href="${esc(x.enlace)}" target="_blank" rel="noopener" lang="${idioma === "es" && x.titulo_es ? "es" : "en"}">${esc(tituloDe(x))}</a><div class="m">${esc(x.medio)} · ${haceTxt(x.publicado)}</div></div></li>`).join("")}</ul>` : `<p class="vacio">Sin titulares.</p>`;
}
function ponerIdioma(l) {
  idioma = l;
  try { localStorage.setItem("radar-idioma", l); } catch (e) { /* nada */ }
  titulares();
}
$("lang-es").addEventListener("click", () => ponerIdioma("es"));
$("lang-en").addEventListener("click", () => ponerIdioma("en"));

/* ---------- gráfico de velas (un eje de precio, a la derecha; cruz con tooltip) ---------- */
function ticks(mn, mx, n = 5) {
  const paso0 = (mx - mn) / n, p10 = Math.pow(10, Math.floor(Math.log10(paso0)));
  const paso = [1, 2, 2.5, 5, 10].map((k) => k * p10).find((k) => k >= paso0) || paso0;
  const out = [];
  for (let v = Math.ceil(mn / paso) * paso; v <= mx + 1e-9; v += paso) out.push(v);
  return out;
}
function velas(el, filas, op) {
  const n = filas.length;
  if (!n) { el.innerHTML = `<p class="vacio">Sin velas para este gráfico.</p>`; return; }
  const W = Math.max(320, el.clientWidth || 700), H = op.alto || 250, ml = 6, mr = 112, mt = 10, mb = 24;
  const valores = filas.flatMap((f) => [f[2], f[3]]);
  (op.lineas || []).forEach((l) => filas.forEach((f, i) => { const v = l.v(f, i); if (v != null) valores.push(v); }));
  (op.niveles || []).forEach((l) => valores.push(l.v));
  let mn = Math.min(...valores.filter((v) => v != null)), mx = Math.max(...valores.filter((v) => v != null));
  const pad = (mx - mn) * 0.04 || 1; mn -= pad; mx += pad;
  const X = (i) => ml + (W - ml - mr) * (i + 0.5) / n, Y = (v) => mt + (H - mt - mb) * (1 - (v - mn) / (mx - mn));
  const bw = Math.max(1, (W - ml - mr) / n * 0.62);
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(op.titulo || "Gráfico de velas")}">`;
  ticks(mn, mx).forEach((v) => { s += `<line class="rejilla" x1="${ml}" x2="${W - mr}" y1="${Y(v)}" y2="${Y(v)}"/><text x="${W - mr + 6}" y="${Y(v) + 4}">${precio(v, op.ref)}</text>`; });
  const idxF = [0, Math.floor(n / 3), Math.floor(2 * n / 3), n - 1];
  idxF.forEach((i, k) => { s += `<text x="${X(i)}" y="${H - 6}" text-anchor="${k === 0 ? "start" : k === 3 ? "end" : "middle"}">${esc(op.fecha(filas[i][0]))}</text>`; });
  filas.forEach((f, i) => {
    const [, o, h, l, c] = f;
    if (o == null || c == null) return;
    const col = c >= o ? "var(--sube)" : "var(--baja)", y1 = Y(Math.max(o, c)), y2 = Y(Math.min(o, c));
    s += `<line x1="${X(i)}" x2="${X(i)}" y1="${Y(h)}" y2="${Y(l)}" stroke="${col}" stroke-width="1"/>` +
      `<rect x="${X(i) - bw / 2}" y="${y1}" width="${bw}" height="${Math.max(1, y2 - y1)}" fill="${col}" rx="${bw > 5 ? 1 : 0}"/>`;
  });
  (op.lineas || []).forEach((l) => {
    let d = "", prev = null;
    filas.forEach((f, i) => {
      const v = l.v(f, i), col = l.color(f, i);
      if (v == null) { prev = null; return; }
      if (prev && prev.col === col) d += `L${X(i).toFixed(1)},${Y(v).toFixed(1)}`;
      else { if (d) s += `<path d="${d}" fill="none" stroke="${prev.col}" stroke-width="2" ${l.raya ? 'stroke-dasharray="6 4"' : ""} stroke-linejoin="round"/>`; d = `M${X(i).toFixed(1)},${Y(v).toFixed(1)}`; }
      prev = { col };
    });
    if (d && prev) s += `<path d="${d}" fill="none" stroke="${prev.col}" stroke-width="2" ${l.raya ? 'stroke-dasharray="6 4"' : ""} stroke-linejoin="round"/>`;
  });
  const etqs = (op.niveles || []).map((l) => ({ ...l, y: Y(l.v) })).sort((a, b) => a.y - b.y);
  for (let i = 1; i < etqs.length; i++) if (etqs[i].y - etqs[i - 1].y < 15) etqs[i].y = etqs[i - 1].y + 15;
  etqs.forEach((l) => {
    s += `<line x1="${ml}" x2="${W - mr}" y1="${Y(l.v)}" y2="${Y(l.v)}" stroke="${l.color}" stroke-width="1.5" stroke-dasharray="5 4"/>` +
      `<rect x="${W - mr + 2}" y="${l.y - 8}" width="${mr - 4}" height="16" rx="3" fill="${l.color}"/>` +
      `<text class="etq-nivel" x="${W - mr + 6}" y="${l.y + 4}">${esc(l.etq)} ${precio(l.v, op.ref)}</text>`;
  });
  s += `<line class="cruz" x1="0" x2="0" y1="${mt}" y2="${H - mb}" visibility="hidden"/><rect class="hit" x="${ml}" y="${mt}" width="${W - ml - mr}" height="${H - mt - mb}" fill="transparent"/></svg>`;
  el.innerHTML = (op.leyenda ? `<div class="leyenda">${op.leyenda}</div>` : "") + s;
  const svg = el.querySelector("svg"), cruz = svg.querySelector(".cruz"), hit = svg.querySelector(".hit");
  hit.addEventListener("pointermove", (ev) => {
    const r = svg.getBoundingClientRect(), xs = (ev.clientX - r.left) * W / r.width;
    const i = Math.max(0, Math.min(n - 1, Math.round((xs - ml) / (W - ml - mr) * n - 0.5)));
    const f = filas[i];
    cruz.setAttribute("x1", X(i)); cruz.setAttribute("x2", X(i)); cruz.setAttribute("visibility", "visible");
    mostrarTip(`<b>${esc(op.fechaLarga(f[0]))}</b><br><span class="num">apertura ${precio(f[1], op.ref)}<br>máximo ${precio(f[2], op.ref)}<br>mínimo ${precio(f[3], op.ref)}<br>cierre ${precio(f[4], op.ref)}</span>${(op.lineas || []).map((l) => l.v(f, i) != null ? `<br>${esc(l.nombre)} <span class="num">${precio(l.v(f, i), op.ref)}</span>` : "").join("")}`, ev.clientX, ev.clientY);
  });
  hit.addEventListener("pointerleave", () => { cruz.setAttribute("visibility", "hidden"); ocultarTip(); });
}

/* ---------- ficha de un activo ---------- */
function barraCambio(etq, v, escala) {
  const w = v == null ? 0 : Math.min(50, Math.abs(v) / escala * 50);
  return `<div class="cambio"><span>${esc(etq)}</span><div class="riel-c"><span class="${v >= 0 ? "pos" : "neg"}" style="width:${w}%;${v >= 0 ? "left:50%" : `left:${50 - w}%`}"></span></div><b class="num ${clase(v)}">${pct(v, 1)}</b></div>`;
}
function explicar(a) {
  const n = a.niveles || {}, t = [];
  if (a.vs_ma200 != null) t.push(`<p><b>Tendencia de fondo (meses): ${a.tend_diaria}.</b> El precio está ${fmt(Math.abs(a.vs_ma200), 1)} % ${a.vs_ma200 >= 0 ? "por encima" : "por debajo"} de su precio medio de los últimos 200 días (<span class="num">${precio(n.ma200, a.ultimo)}</span>, la línea azul punteada del gráfico diario). ${a.vs_ma200 >= 0 ? "Mientras siga encima, las caídas son correcciones dentro de una subida." : "Mientras siga debajo, las subidas son rebotes dentro de una bajada."}</p>`);
  if (n.st_4h != null) t.push(`<p><b>Tendencia de corto plazo (días): ${a.tend_4h}.</b> El Supertrend de 4 horas está ${a.tend_4h === "alcista" ? "por debajo del precio, en" : "por encima del precio, en"} <span class="num">${precio(n.st_4h, a.ultimo)}</span>${n.st_desde ? ` desde el ${fechaLarga(n.st_desde)}` : ""}. Si una vela de 4h cierra al otro lado, la tendencia de corto plazo gira.</p>`);
  const s = a.plan?.sesgo;
  const mejor = s && s !== "esperar" ? a.plan[s.split("_")[0]] : null;
  const tend = a.tend_diaria && a.tend_4h ? (a.tend_diaria === a.tend_4h ? `Las dos tendencias son ${a.tend_diaria}s.` : "Las tendencias diaria y de 4h se contradicen.") : "";
  t.push(`<p class="conclusion ${sesgoClase(s)}"><b>${SESGO_TXT[s] || "Sin plan"}.</b> ${tend} ${mejor ? `${esc(mejor.prob_motivo.charAt(0).toUpperCase() + mejor.prob_motivo.slice(1))}. El plan está abajo.` : "Ningún plan de este activo tiene ventaja medida ahora mismo: mejor esperar a que cambie la situación."}</p>`);
  return t.join("");
}
function planCaja(p, a) {
  if (!p) return "";
  return `<div class="plan-caja ${p.accion}"><div class="fila"><h3>${p.accion === "compra" ? "Plan de compra" : "Plan de venta"}</h3>${etiquetaProb(p.prob)}</div>
    <dl class="niveles"><div><dt>Gatillo</dt><dd class="num">cierre 4h ${p.accion === "compra" ? "sobre" : "bajo"} ${precio(p.gatillo, a.ultimo)}</dd></div>
      <div><dt>Stop</dt><dd class="num">${precio(p.stop, a.ultimo)}</dd></div><div><dt>Objetivo (2R)</dt><dd class="num">${precio(p.objetivo, a.ultimo)}</dd></div></dl>
    <p class="nota"><b>${esc(may(p.prob_motivo))}.</b> ${esc(may(porQue(p)))}. ${esc(may(extras(p)))}.${p.lab ? ` ${esc(labTxt(p))}.` : ""}</p></div>`;
}
async function abrirFicha(clave) {
  const a = activo(clave);
  if (!a) return;
  fichaAbierta = clave;
  const dlg = $("ficha");
  if (!dlg.open) dlg.showModal();
  pintarFicha(clave);
  await graficos();
  if (fichaAbierta === clave) pintarFicha(clave);
}
function pintarFicha(clave) {
  const a = activo(clave);
  if (!a) return;
  $("ficha-titulo").textContent = `${a.nombre}  ${precio(a.ultimo)}`;
  $("ficha-sub").innerHTML = `<span class="${clase(a.ch_1d)}">${pct(a.ch_1d)} hoy</span> · ${esc(a.grupo)} · Yahoo ${esc(a.ticker)} · ${haceTxt(D.mercado?.generado)}`;
  const esc_ = Math.max(1, ...[a.ch_1d, a.ch_5d, a.ch_1m].map((v) => Math.abs(v || 0)));
  const eventos = gruposAgenda().filter((g) => g[0].t >= Date.now() / 1000 - 12 * 3600 && g[0].guia.activos.some((x) => x.clave === clave)).slice(0, 4);
  const senal = (D.bot?.senales || []).find((s) => s.simbolo === clave);
  const tes = (D.tesis?.recientes || []).filter((x) => x.simbolo === clave).slice(0, 4);
  const g = D.graficos?.activos?.[clave];
  $("ficha-cuerpo").innerHTML = `
    <div class="ficha-grid">
      <div class="ficha-texto">
        <h3 class="sub">Cómo va</h3>
        ${barraCambio("Hoy", a.ch_1d, esc_)}${barraCambio("5 días", a.ch_5d, esc_)}${barraCambio("1 mes", a.ch_1m, esc_)}
        <p class="nota">Cuánto cambió el precio en cada periodo. Las barras usan la misma escala.</p>
        <h3 class="sub">Qué dicen las tendencias</h3>${explicar(a)}
      </div>
      <div class="ficha-planes"><h3 class="sub">Planes de entrada</h3>${planCaja(a.plan?.compra, a)}${planCaja(a.plan?.venta, a)}</div>
    </div>
    <h3 class="sub">Diario · 6 meses</h3><div class="graf-velas" id="g-diario">${g ? "" : `<p class="vacio">Cargando gráfico…</p>`}</div>
    <h3 class="sub">4 horas · últimas 90 velas</h3><div class="graf-velas" id="g-4h">${g ? "" : `<p class="vacio">Cargando gráfico…</p>`}</div>
    ${eventos.length ? `<h3 class="sub">Noticias que lo mueven</h3><ul class="ficha-lista">${eventos.map((ev) => { const e = ev[0], dt = new Date(e.t * 1000); return `<li><span class="num">${fechaCorta(dt, "America/Bogota")} ${hora(dt, "America/Bogota")}</span> ${esc(e.moneda)} · ${esc(ev.map((x) => x.nombre).join(", "))} ${etiquetaProb(e.guia.veredicto.nivel)}</li>`; }).join("")}</ul>` : ""}
    ${senal ? `<h3 class="sub">Bot</h3><p>${esc(senal.estrategia)}: ${esc(senal.distancia)}</p>` : ""}
    ${tes.length ? `<h3 class="sub">Lo que dicen los analistas</h3><div class="tesis-lista corta">${tes.map((x) => `<div class="tes"><div class="fila"><span>${esc(TIPOS[x.tipo] || x.tipo)} ${esc(x.direccion)} ${esc(x.horizonte)}</span><span class="estado ${estadoClase(x.estado)}">${esc(x.estado)}</span></div><q>${esc(x.cita)}</q><span class="nota">${esc(AUTORES[x.autor] || x.autor || "")} · ${esc(x.fecha_video)} · <a href="https://youtu.be/${esc(x.video_id)}?t=${minutoSeg(x.minuto)}" target="_blank" rel="noopener">${esc(x.minuto)}</a></span></div>`).join("")}</div>` : ""}`;
  if (!g) return;
  const n = a.niveles || {}, pl = a.plan || {};
  velas($("g-diario"), g.d, {
    ref: a.ultimo, titulo: `${a.nombre}, velas diarias`, alto: 260,
    fecha: (f) => fechaLarga(f + "T12:00:00Z"), fechaLarga: (f) => f,
    lineas: [{ nombre: "Media 200 días", v: (f) => f[5], color: () => "var(--s1)", raya: true }],
    leyenda: `<span><i style="background:var(--s1)"></i>Media de 200 días (tendencia de fondo)</span>`,
  });
  const niveles4 = [];
  if (pl.compra) niveles4.push({ v: pl.compra.gatillo, etq: "Compra", color: "var(--sube)" });
  if (pl.venta) niveles4.push({ v: pl.venta.gatillo, etq: "Venta", color: "var(--baja)" });
  velas($("g-4h"), g.h4, {
    ref: a.ultimo, titulo: `${a.nombre}, velas de 4 horas`, alto: 270,
    fecha: (f) => fechaLarga(f), fechaLarga: (f) => `${fechaLarga(f)} ${hora(new Date(f), "America/Bogota")} Bogotá`,
    lineas: [{ nombre: "Supertrend", v: (f) => f[5], color: (f) => f[6] > 0 ? "var(--sube)" : "var(--baja)" }],
    niveles: niveles4,
    leyenda: `<span><i style="background:var(--sube)"></i>Supertrend alcista</span><span><i style="background:var(--baja)"></i>Supertrend bajista</span><span><i class="raya"></i>Gatillos: máximo y mínimo de las 20 velas anteriores</span>`,
  });
}
$("ficha-cerrar").addEventListener("click", () => $("ficha").close());
$("ficha").addEventListener("close", () => { fichaAbierta = null; ocultarTip(); });
$("ficha").addEventListener("click", (ev) => { if (ev.target === $("ficha")) $("ficha").close(); });
document.addEventListener("click", (ev) => {
  const b = ev.target.closest("[data-clave]");
  if (b) { ev.preventDefault(); abrirFicha(b.dataset.clave); }
});

/* ---------- bonos: un eje (rendimiento en %), 4 series, cruz con tooltip ---------- */
function bonos() {
  const b = D.bonos;
  if (!b) return;
  $("bonos-meta").textContent = `Rendimiento en % · último dato ${b.tabla?.[0]?.fecha || "–"}`;
  $("bonos-tabla").innerHTML = `<thead><tr><th>Plazo</th><th class="n">Hoy</th><th class="n">1 día</th><th class="n">1 semana</th><th class="n">1 mes</th></tr></thead><tbody>${
    (b.tabla || []).map((f) => `<tr><td>${esc(f.nombre)}</td><td class="n">${fmt(f.ultimo)}${f.es_pendiente ? " pp" : " %"}</td>${["d1_pb", "d5_pb", "d21_pb"].map((k) => `<td class="n ${clase(f[k])}">${f[k] > 0 ? "+" : ""}${f[k]} pb</td>`).join("")}</tr>`).join("")}</tbody>`;
  const nombres = Object.keys(b.series || {}), cols = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)"];
  const el = $("bonos-graf"), W = el.clientWidth || 560, H = 210, ml = 34, mr = 104, mt = 8, mb = 22;
  const todas = nombres.flatMap((n) => b.series[n].map((p) => p[1]));
  if (!todas.length) return;
  const mn = Math.floor(Math.min(...todas) * 2) / 2, mx = Math.ceil(Math.max(...todas) * 2) / 2;
  const fechas = b.series[nombres[0]].map((p) => p[0]);
  const X = (i, n) => ml + (W - ml - mr) * i / Math.max(1, n - 1), Y = (v) => mt + (H - mt - mb) * (1 - (v - mn) / (mx - mn || 1));
  let s = `<svg viewBox="0 0 ${W} ${H}">`;
  for (let v = mn; v <= mx + 1e-9; v += 0.5) s += `<line class="rejilla" x1="${ml}" x2="${W - mr}" y1="${Y(v)}" y2="${Y(v)}"/><text x="${ml - 6}" y="${Y(v) + 3}" text-anchor="end">${v.toFixed(1)}</text>`;
  [0, Math.floor(fechas.length / 2), fechas.length - 1].forEach((i) => { s += `<text x="${X(i, fechas.length)}" y="${H - 6}" text-anchor="${i === 0 ? "start" : i === fechas.length - 1 ? "end" : "middle"}">${esc(fechas[i]?.slice(0, 7))}</text>`; });
  const fin = [];
  nombres.forEach((n, k) => {
    const sr = b.series[n];
    s += `<path d="${sr.map((p, i) => `${i ? "L" : "M"}${X(i, sr.length).toFixed(1)},${Y(p[1]).toFixed(1)}`).join("")}" fill="none" stroke="${cols[k]}" stroke-width="2" stroke-linejoin="round"/>`;
    const u = sr[sr.length - 1];
    fin.push({ y: Y(u[1]), n, v: u[1], c: cols[k], x: X(sr.length - 1, sr.length) });
  });
  fin.sort((a, c) => a.y - c.y);
  for (let i = 1; i < fin.length; i++) if (fin[i].y - fin[i - 1].y < 14) fin[i].y = fin[i - 1].y + 14;
  fin.forEach((f) => { s += `<circle cx="${f.x}" cy="${Y(f.v)}" r="3.5" fill="${f.c}" stroke="var(--panel)" stroke-width="2"/><text class="etq-serie" x="${W - mr + 8}" y="${f.y + 4}">${esc(f.n)} ${fmt(f.v)}</text>`; });
  s += `<line class="cruz" id="bonos-cruz" x1="0" x2="0" y1="${mt}" y2="${H - mb}" visibility="hidden"/><rect x="${ml}" y="${mt}" width="${W - ml - mr}" height="${H - mt - mb}" fill="transparent" id="bonos-hit"/></svg>`;
  el.innerHTML = `<div class="leyenda">${nombres.map((n, k) => `<span><i style="background:${cols[k]}"></i>${esc(n)}</span>`).join("")}</div>` + s;
  const hit = $("bonos-hit"), cruz = $("bonos-cruz"), svg = el.querySelector("svg");
  hit.addEventListener("pointermove", (ev) => {
    const r = svg.getBoundingClientRect(), xs = (ev.clientX - r.left) * W / r.width;
    const i = Math.max(0, Math.min(fechas.length - 1, Math.round((xs - ml) / (W - ml - mr) * (fechas.length - 1))));
    cruz.setAttribute("x1", X(i, fechas.length)); cruz.setAttribute("x2", X(i, fechas.length)); cruz.setAttribute("visibility", "visible");
    mostrarTip(`<b>${esc(fechas[i])}</b><br>${nombres.map((n, k) => `<span style="color:${cols[k]}">■</span> ${esc(n)} <span class="num">${fmt(b.series[n][i]?.[1])} %</span>`).join("<br>")}`, ev.clientX, ev.clientY);
  });
  hit.addEventListener("pointerleave", () => { cruz.setAttribute("visibility", "hidden"); ocultarTip(); });
}

/* ---------- valor relativo ---------- */
function valor() {
  const v = D.valor;
  if (!v) return;
  const orden = ["XAUUSD", "XAGUSD", "XPTUSD", "COBRE", "XTIUSD", "GASNAT", "BTCUSD", "ETHUSD", "US500", "USTEC", "DE40", "IBEX35", "DXY", "BONO10", "VIX"];
  const act = orden.map((k) => v.activos.find((a) => a.clave === k)).filter(Boolean);
  $("valor").innerHTML = act.map((a) => `<div class="pctl" data-tip="${esc(`${a.nombre} ${fmt(a.ultimo, decimales(a.ultimo))} · rango 10 años ${fmt(a.min_10a, decimales(a.min_10a))}–${fmt(a.max_10a, decimales(a.max_10a))} · vs máximo 10 años ${pct(a.vs_max_10a, 1)} · 12 meses ${pct(a.ch_12m, 1)}`)}">
      <span>${esc(a.nombre)}</span><div class="riel"><span class="marca-p" style="left:${a.pctl_10a}%"></span></div><span class="v">${a.pctl_10a ?? "–"}</span></div>`).join("");
  conTips($("valor"));
  $("ratios").innerHTML = (v.ratios || []).map((r) => `<div class="ratio"><div><b>${esc(r.nombre)}</b> <span class="num">${fmt(r.hoy, r.hoy < 10 ? 3 : 1)}</span> · percentil ${r.pctl_10a}</div>
      <div class="l">${esc(r.lectura)} · mediana 10 años ${fmt(r.mediana_10a, r.mediana_10a < 10 ? 3 : 1)}</div>${sparkline(r.serie, 90, 30)}</div>`).join("");
}

/* ---------- analistas ---------- */
const AUTORES = { cava: "José Luis Cava", pablogil: "Pablo Gil", dalio: "Ray Dalio" };
function estadoClase(e) {
  return e.startsWith("cumplida") ? "cumplida" : e.startsWith("fallida") ? "fallida" : e === "en curso (a favor)" ? "favor" : e === "en curso (en contra)" ? "contra" : "";
}
function analistas() {
  const t = D.tesis;
  if (!t) return;
  const T = t.totales;
  $("analistas-meta").textContent = `${[...new Set((t.recientes || []).map((x) => AUTORES[x.autor] || x.autor).filter(Boolean))].join(", ") || "José Luis Cava"} · ${T.videos} videos · ${T.tesis} tesis con cita y minuto · verificadas contra precios ${haceTxt(t.generado)}`;
  const mx = Math.max(...t.marcador.map((m) => m.tesis));
  $("marcador").innerHTML = `<div class="totales"><div class="total"><div class="v">${T.cumplidas}</div><span class="etq">cumplidas</span></div>
      <div class="total"><div class="v">${T.fallidas}</div><span class="etq">fallidas</span></div><div class="total"><div class="v">${T.en_curso}</div><span class="etq">en curso</span></div>
      <div class="total"><div class="v">${T.pendientes}</div><span class="etq">empiezan después</span></div></div>` +
    t.marcador.slice(0, 10).map((m) => `<div class="marc"><span class="sim">${esc(m.simbolo)}</span><div class="barra-m" style="width:${100 * m.tesis / mx}%">
      ${[["cumplidas", "b-cumplida"], ["fallidas", "b-fallida"], ["a_favor", "b-favor"], ["en_contra", "b-contra"]].filter(([k]) => m[k]).map(([k, c]) => `<span class="${c}" style="flex:${m[k]}" title="${m[k]} ${k.replace("_", " ")}"></span>`).join("")}</div>
      <span class="k">${m.cumplidas}✓ ${m.fallidas}✗</span></div>`).join("") +
    `<div class="leyenda-marc"><span><i class="b-cumplida"></i>cumplida</span><span><i class="b-fallida"></i>fallida</span><span><i class="b-favor"></i>en curso a favor</span><span><i class="b-contra"></i>en curso en contra</span></div>`;
  const porFecha = {};
  t.pendientes.forEach((p) => { (porFecha[p.fecha_desde] ||= []).push(p); });
  $("pendientes").innerHTML = Object.entries(porFecha).map(([f, l]) => `<li><span class="f">${esc(f)}</span><span>${l.length} tesis empiezan a contar: ${[...new Set(l.map((x) => `${x.activo} ${x.direccion}`))].slice(0, 4).map(esc).join("; ")}</span></li>`).join("")
    + (t.condicionales.length ? `<li><span class="f">disparador</span><span>${t.condicionales.length} tesis condicionales esperan su disparador (p. ej. ${esc(t.condicionales[0].condicion)}).</span></li>` : "");
  $("tesis-recientes").innerHTML = t.recientes.slice(0, 30).map((x) => `<div class="tes"><div class="fila"><span><b>${esc(x.activo)}</b> · ${esc(TIPOS[x.tipo] || x.tipo)} ${esc(x.direccion)} ${esc(x.horizonte)}${x.nivel != null ? ` · nivel ${fmt(x.nivel, decimales(x.nivel))}` : ""}</span>
      <span class="estado ${estadoClase(x.estado)}">${esc(x.estado)}</span></div><q>${esc(x.cita)}</q>
      <span class="nota">${esc(AUTORES[x.autor] || x.autor || "")} · ${esc(x.fecha_video)} · <a href="https://youtu.be/${esc(x.video_id)}?t=${minutoSeg(x.minuto)}" target="_blank" rel="noopener">${esc(x.minuto)}</a>${x.ret_hoy != null ? ` · desde el video ${pct(x.ret_hoy * 100, 1)}` : ""}${x.condicion ? ` · ${esc(x.condicion)}` : ""}</span></div>`).join("");
}
function minutoSeg(m) { return String(m || "0").split(":").reduce((a, x) => a * 60 + (+x || 0), 0); }

/* ---------- radar de acciones ---------- */
function radar() {
  const r = D.radar;
  if (!r) return;
  const listas = Object.entries(r.listas);
  $("radar-meta").textContent = `PER y P/FCF frente a sus propios 10 años (SEC + precios) · precios al ${r.precios_al}`;
  $("radar-pestanas").innerHTML = listas.map(([n, l], i) => `<button class="pestana" type="button" role="tab" id="radar-${i}" aria-selected="${i === radarSel}" data-i="${i}">${esc(n.replace(/^\d\.\s*/, ""))}<span class="c">${l.total}</span></button>`).join("");
  $("radar-pestanas").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => { radarSel = +b.dataset.i; radar(); }));
  const l = listas[radarSel]?.[1];
  $("radar-tabla").innerHTML = `<thead><tr><th>Ticker</th><th>Empresa</th><th>Sector</th><th class="n">PER</th><th class="n">PER mediana 10 a</th><th class="n">Percentil PER</th><th class="n">Calidad</th><th class="n">6 meses</th><th class="n">vs media 200 d</th></tr></thead><tbody>${
    (l?.empresas || []).map((e) => `<tr><td class="num">${esc(e.ticker)}</td><td>${esc(e.empresa)}</td><td>${esc(e.sector)}</td><td class="n">${e.per == null ? "pérdidas" : fmt(e.per, 1)}</td><td class="n">${fmt(e.per_med_10a, 1)}</td><td class="n">${e.pctl_per ?? "–"}</td><td class="n">${e.calidad}</td><td class="n ${clase(e.ret_6m)}">${pct(e.ret_6m, 1)}</td><td class="n ${clase(e.vs_ma200)}">${pct(e.vs_ma200, 1)}</td></tr>`).join("")}</tbody>`;
}

/* ---------- pie: estado de las fuentes ---------- */
function pie() {
  const f = D.titulares?.feeds || {};
  $("fuentes").innerHTML = `<div class="etq" style="margin-bottom:.3rem">Fuentes de noticias (última lectura ${haceTxt(D.titulares?.feeds_actualizado)})</div><div class="feeds">${
    Object.entries(f).map(([n, e]) => `<span class="${e.ok ? "" : "mal"}" title="${esc(e.ok ? `${e.items} en el feed, ${e.nuevos} nuevos` : e.error)}">${esc(n)}</span>`).join("")}</div>`;
}

/* ---------- tema claro/oscuro ---------- */
(function tema() {
  try { const t = localStorage.getItem("radar-tema"); if (t) document.documentElement.dataset.theme = t; } catch (e) { /* sin almacenamiento */ }
  $("tema").addEventListener("click", () => {
    const oscuro = document.documentElement.dataset.theme === "dark" || (!document.documentElement.dataset.theme && matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.dataset.theme = oscuro ? "light" : "dark";
    try { localStorage.setItem("radar-tema", document.documentElement.dataset.theme); } catch (e) { /* nada */ }
    pintar();
    if (fichaAbierta) pintarFicha(fichaAbierta);
  });
})();

/* ---------- arranque ---------- */
relojes();
setInterval(relojes, 15000);
setInterval(() => { seguro(frescura); seguro(sesiones); document.querySelectorAll(".cuenta[data-t]").forEach((c) => { if (c.textContent !== "publicado") c.textContent = cuentaAtras(+c.dataset.t) || "publicado"; }); }, 30000);
setInterval(cargar, 5 * 60 * 1000);
window.addEventListener("resize", () => { seguro(sesiones); seguro(bonos); seguro(titulares); if (fichaAbierta) seguro(() => pintarFicha(fichaAbierta)); });
document.addEventListener("visibilitychange", () => { if (!document.hidden) cargar(); });
cargar();
