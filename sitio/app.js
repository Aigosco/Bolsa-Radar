/* Bolsa-Radar: lee los JSON de datos/web (en GitHub: raw.githubusercontent.com, siempre lo último del repo),
   dibuja cada sección y se refresca sola cada 5 minutos. Cada sección falla por separado sin romper las demás. */
"use strict";

const REPO = "Aigosco/Bolsa-Radar";
const BASE = location.hostname.endsWith("github.io")
  ? `https://raw.githubusercontent.com/${REPO}/main/datos/web/`
  : "../datos/web/";
const ARCHIVOS = ["resumen", "mercado", "agenda", "titulares", "bot", "bonos", "valor", "tesis", "radar"];
const D = {};
let temaSel = null, radarSel = 0;
const TIPOS = { prediccion: "predicción", recomendacion: "recomendación", diagnostico: "diagnóstico" };

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const fmt = (v, d = 2) => v == null || Number.isNaN(v) ? "–" : Number(v).toLocaleString("es-CO", { minimumFractionDigits: d, maximumFractionDigits: d });
const pct = (v, d = 2) => v == null ? "–" : `${v > 0 ? "+" : ""}${fmt(v, d)} %`;
const clase = (v) => v == null ? "" : v > 0 ? "sube" : v < 0 ? "baja" : "";
const decimales = (v) => Math.abs(v) >= 1000 ? 0 : Math.abs(v) >= 100 ? 2 : Math.abs(v) >= 10 ? 2 : Math.abs(v) >= 1 ? 3 : 4;

function hora(dt, tz) {
  return new Intl.DateTimeFormat("es-CO", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: tz }).format(dt);
}
function fechaCorta(dt, tz) {
  return new Intl.DateTimeFormat("es-CO", { weekday: "short", day: "2-digit", timeZone: tz }).format(dt).replace(".", "");
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
  tip.style.left = Math.min(window.innerWidth - r.width - 8, x + 12) + "px";
  tip.style.top = Math.max(8, y - r.height - 10) + "px";
}
function ocultarTip() { tip.hidden = true; }

/* ---------- carga ---------- */
async function cargar() {
  const t = Date.now();
  await Promise.all(ARCHIVOS.map(async (n) => {
    try {
      const r = await fetch(`${BASE}${n}.json?t=${t}`, { cache: "no-store" });
      if (r.ok) D[n] = await r.json();
    } catch (e) { /* se queda con lo anterior */ }
  }));
  pintar();
}
function seguro(fn) { try { fn(); } catch (e) { console.error(fn.name, e); } }
function pintar() {
  [frescura, sesiones, lectura, tablero, agenda, bot, titulares, ideas, bonos, valor, analistas, radar, pie].forEach(seguro);
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
  const el = $("linea-sesiones"), W = el.clientWidth || 900, H = 92, x0 = 8, x1 = W - 8;
  const X = (min) => x0 + (x1 - x0) * (((min % 1440) + 1440) % 1440) / 1440;
  const ahoraMin = minutosNY(new Date());
  let s = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">`;
  SESIONES.forEach((ss, i) => {
    const y = 8 + i * 17;
    const tramos = ss.b > 1440 ? [[ss.a, 1440], [0, ss.b - 1440]] : [[ss.a, ss.b]];
    tramos.forEach(([a, b]) => { s += `<rect x="${X(a)}" y="${y}" width="${X(b === 1440 ? 1439.9 : b) - X(a)}" height="13" rx="3" fill="${ss.c}"/>`; });
    s += `<text class="banda-etq" x="${X(ss.a > 1200 ? 0 : ss.a) + 6}" y="${y + 10}">${ss.n}</text>`;
  });
  for (let h = 0; h <= 24; h += 3) {
    const x = X(h === 24 ? 1439.9 : h * 60);
    s += `<line x1="${x}" x2="${x}" y1="60" y2="64" stroke="var(--linea)"/><text x="${x}" y="76" text-anchor="${h === 0 ? "start" : h === 24 ? "end" : "middle"}">${String(h).padStart(2, "0")}:00</text>`;
  }
  s += `<line x1="${x0}" x2="${x1}" y1="60" y2="60" stroke="var(--linea)"/>`;
  // noticias de hoy (hora NY) sobre la línea
  const hoyNY = new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York" }).format(new Date());
  (D.agenda?.eventos || []).forEach((e) => {
    const dt = new Date(e.t * 1000);
    if (new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York" }).format(dt) !== hoyNY) return;
    const x = X(minutosNY(dt)), alto = e.impacto?.toLowerCase() === "high";
    s += `<circle class="evento ${alto ? "" : "medio"}" cx="${x}" cy="60" r="${alto ? 4.5 : 3.5}" data-tip="${esc(hora(dt, "America/New_York") + " NY · " + e.moneda + " " + e.nombre)}"/>`;
  });
  const xa = X(ahoraMin);
  s += `<line class="ahora" x1="${xa}" x2="${xa}" y1="2" y2="66"/><text class="ahora-etq" x="${Math.min(Math.max(xa, 30), W - 30)}" y="88" text-anchor="middle">ahora</text></svg>`;
  el.innerHTML = s;
  el.querySelectorAll("[data-tip]").forEach((c) => {
    c.addEventListener("pointerenter", (ev) => mostrarTip(c.dataset.tip, ev.clientX, ev.clientY));
    c.addEventListener("pointerleave", ocultarTip);
  });
  const abiertas = SESIONES.filter((ss) => (ahoraMin >= ss.a && ahoraMin < ss.b) || (ss.b > 1440 && ahoraMin < ss.b - 1440)).map((ss) => ss.n);
  const dia = new Date().toLocaleDateString("en-US", { weekday: "short", timeZone: "America/New_York" });
  const finde = (dia === "Sat") || (dia === "Sun" && ahoraMin < 17 * 60);
  $("sesion-ahora").textContent = finde ? "Fin de semana: solo cotiza cripto." : abiertas.length ? `Abierta ahora: ${abiertas.join(" y ")}.` : "Entre sesiones.";
}

/* ---------- lectura del momento ---------- */
function lectura() {
  const r = D.resumen;
  if (!r) { $("esencial").innerHTML = `<li class="vacio">Aún no hay lectura con IA.</li>`; return; }
  $("lectura-meta").textContent = `${haceTxt(r.generado)} · ${r.modelo || ""}`;
  $("esencial").innerHTML = (r.lo_esencial || []).map((x) => `<li>${esc(x)}</li>`).join("");
  $("vigilar").innerHTML = (r.vigilar || []).map((x) => `<li>${esc(x)}</li>`).join("");
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
function tablero() {
  const a = D.mercado?.activos || [];
  $("tablero").innerHTML = a.map((x) => x.sin_datos ? `<div class="activo"><div class="nombre">${esc(x.nombre)}</div><div class="vacio">Sin datos</div></div>` : `
    <article class="activo" data-tip="${esc(`${x.nombre} · 5 días ${pct(x.ch_5d)} · 1 mes ${pct(x.ch_1m)} · vs media 200 d ${pct(x.vs_ma200, 1)} · rango 52 semanas ${fmt(x.min_52s, decimales(x.ultimo))}–${fmt(x.max_52s, decimales(x.ultimo))}`)}">
      <div class="fila"><span class="nombre">${esc(x.nombre)}</span><span class="grupo">${esc(x.grupo)}</span></div>
      <div class="fila"><span class="precio">${fmt(x.ultimo, decimales(x.ultimo))}</span><span class="var ${clase(x.ch_1d)}">${pct(x.ch_1d)}</span></div>
      ${sparkline(x.spark)}
      <div class="fila"><div class="chips">
        <span class="chip ${x.tend_diaria || ""}" title="Precio frente a su media de 200 días">Diaria ${x.tend_diaria || "–"}</span>
        <span class="chip ${x.tend_4h || ""}" title="Supertrend 10/3 en velas de 4 h">4h ${x.tend_4h || "–"}</span></div>
        <span class="mini"><span class="${clase(x.ch_5d)}">5d ${pct(x.ch_5d, 1)}</span></span></div>
    </article>`).join("");
  $("tablero").querySelectorAll("[data-tip]").forEach((c) => {
    c.addEventListener("pointermove", (ev) => mostrarTip(c.dataset.tip, ev.clientX, ev.clientY));
    c.addEventListener("pointerleave", ocultarTip);
  });
}

/* ---------- agenda ---------- */
function cuentaAtras(t) {
  const s = Math.round(t - Date.now() / 1000);
  if (s <= 0) return "";
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  return h >= 24 ? `en ${Math.floor(h / 24)} d ${h % 24} h` : `en ${h ? h + " h " : ""}${m} min`;
}
function agenda() {
  const ev = D.agenda?.eventos || [];
  if (!ev.length) { $("agenda").innerHTML = `<li class="vacio">Sin eventos en el calendario descargado.</li>`; return; }
  const pasados = ev.filter((e) => e.publicado).slice(-4), futuros = ev.filter((e) => !e.publicado).slice(0, 14);
  $("agenda").innerHTML = [...pasados, ...futuros].map((e) => {
    const dt = new Date(e.t * 1000), imp = (e.impacto || "").toLowerCase();
    let efecto = "";
    if (e.efecto?.XAUUSD) {
      const o = e.efecto.XAUUSD, sp = e.efecto.US500;
      efecto = `<div class="efecto">Historial (${esc(e.familia)}): el oro se movió "de libro" el ${Math.round(o.libro_15m * 100)} % de las veces a 15 min; mueve ${fmt(o.mov_1h)} % en 1 h (p90 ${fmt(o.p90_1h)} %)${sp ? `; S&P 500 de libro ${Math.round(sp.libro_15m * 100)} %` : ""}.</div>`;
    }
    const real = e.actual ? `<span>real <b class="${e.mejor_peor == 1 ? "sube" : e.mejor_peor == 2 ? "baja" : ""}">${esc(e.actual)}</b></span>` : "";
    return `<li class="ev ${e.publicado ? "pasado" : ""}">
      <div class="cuando">${fechaCorta(dt, "America/Bogota")} ${hora(dt, "America/Bogota")}<small>${hora(dt, "America/New_York")} NY</small></div>
      <div><div class="nombre"><span class="impacto ${imp}" title="Impacto ${imp === "high" ? "alto" : "medio"}"></span>${esc(e.moneda)} · ${esc(e.nombre)}</div>
        <div class="valores">${real}<span>previsión ${esc(e.previsto || "–")}</span><span>anterior ${esc(e.anterior || "–")}</span></div></div>
      <div class="cuenta" data-t="${e.t}">${e.publicado ? "publicado" : cuentaAtras(e.t)}</div>${efecto}</li>`;
  }).join("");
}

/* ---------- bot ---------- */
function bot() {
  const b = D.bot;
  if (!b) { $("bot").innerHTML = `<p class="vacio">El PC aún no publicó el estado del bot.</p>`; return; }
  $("bot-meta").textContent = `Demo · ${fmt(b.riesgo_por_operacion_pct, 1)} % por operación · ${haceTxt(b.generado)}`;
  const pos = (b.posiciones || []).map((p) => `<div class="senal"><div class="fila"><span class="sim">${esc(p.simbolo)}</span>
      <span class="chip acento">${esc(p.tipo)} · ${p.R == null ? "–" : (p.R > 0 ? "+" : "") + fmt(p.R) + " R"}</span></div>
      <div class="dist">entrada ${fmt(p.entrada, decimales(p.entrada))} · stop ${fmt(p.stop, decimales(p.stop))} · ${esc(p.estrategia || "")}</div></div>`).join("");
  const sen = (b.senales || []).map((s) => {
    const m = /([+-]?\d+[.,]\d+)%\)?\s*(?:·|$)/.exec(s.distancia) || /falta \+?(\d+[.,]\d+)%/.exec(s.distancia);
    const falta = m ? Math.abs(parseFloat(m[1].replace(",", "."))) : null;
    const lleno = falta == null ? 0 : Math.max(4, 100 - Math.min(falta, 10) * 10);
    const cand = /candidata/.test(s.estrategia);
    return `<div class="senal"><div class="fila"><span class="sim">${esc(s.simbolo)}</span><span class="chip ${cand ? "" : "acento"}">${cand ? "candidata, sin bot" : "en el bot"}</span></div>
      <div class="dist">${esc(s.estrategia)} · cierre 4h ${esc(s.cierre_4h)}</div><div class="dist">${esc(s.distancia)}</div>
      ${falta != null ? `<div class="medidor" title="Cercanía a la señal (lleno = a punto)"><span style="width:${lleno}%"></span></div>` : ""}</div>`;
  }).join("");
  $("bot").innerHTML = (pos ? `<h3 class="sub">Posiciones abiertas</h3>${pos}` : `<p class="nota">Sin posiciones abiertas.</p>`) +
    `<h3 class="sub">Distancia a la señal de compra</h3>${sen}`;
}

/* ---------- titulares ---------- */
function titulares() {
  const t = D.titulares;
  if (!t) return;
  $("titulares-meta").textContent = `${t.total_24h} titulares únicos en 24 h · ${haceTxt(t.generado)}`;
  const ph = t.por_hora || [], mx = Math.max(1, ...ph.map((x) => x.n)), W = $("actividad").clientWidth || 900, H = 46, bw = W / ph.length;
  $("actividad").innerHTML = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">${ph.map((x, i) => {
    const h = Math.max(1.5, (H - 4) * x.n / mx);
    return `<rect x="${i * bw + 1}" y="${H - h}" width="${Math.max(1, bw - 2)}" height="${h}" rx="2" data-tip="${hora(new Date(x.hora), "America/Bogota")} Bogotá · ${x.n} titulares"/>`;
  }).join("")}</svg>`;
  $("actividad").querySelectorAll("rect").forEach((r) => {
    r.addEventListener("pointermove", (ev) => mostrarTip(r.dataset.tip, ev.clientX, ev.clientY));
    r.addEventListener("pointerleave", ocultarTip);
  });
  const temas = t.temas || [];
  if (!temaSel || !temas.find((x) => x.tema === temaSel)) temaSel = temas[0]?.tema;
  $("pestanas").innerHTML = temas.map((x) => `<button class="pestana" role="tab" type="button" id="tab-${esc(x.tema)}" aria-selected="${x.tema === temaSel}" data-tema="${esc(x.tema)}">${esc(x.tema)}<span class="c">${x.n_24h}</span></button>`).join("");
  $("pestanas").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => { temaSel = b.dataset.tema; titulares(); }));
  const g = temas.find((x) => x.tema === temaSel);
  const ia = (D.resumen?.temas || []).find((x) => x.tema.toLowerCase() === (temaSel || "").toLowerCase());
  const analisis = ia ? `<div class="analisis-tema">
      <div><b>Qué pasó.</b> ${esc(ia.que_paso)}</div>${ia.coinciden ? `<div><b>Coinciden.</b> ${esc(ia.coinciden)}</div>` : ""}
      ${ia.discrepan ? `<div><b>Difieren.</b> ${esc(ia.discrepan)}</div>` : ""}${ia.efecto_posible ? `<div><b>Efecto posible.</b> ${esc(ia.efecto_posible)}</div>` : ""}
      <p class="nota">Lectura con IA ${haceTxt(D.resumen.generado)}.</p></div>`
    : `<div class="analisis-tema"><p class="nota">${g ? `${g.n_24h} titulares en 24 h de ${g.medios} medios distintos. La lectura con IA de este tema aparecerá en la próxima actualización.` : ""}</p></div>`;
  $("tema-panel").innerHTML = g ? analisis + `<ul class="titulares">${g.titulares.map((x) => `<li><span class="t">${hora(new Date(x.publicado), "America/Bogota")}</span>
      <div><a href="${esc(x.enlace)}" target="_blank" rel="noopener">${esc(x.titulo)}</a><div class="m">${esc(x.medio)} · ${haceTxt(x.publicado)}</div></div></li>`).join("")}</ul>` : `<p class="vacio">Sin titulares.</p>`;
}

/* ---------- ideas ---------- */
function ideas() {
  const ii = D.resumen?.ideas || [];
  $("ideas").style.setProperty("--cols", Math.min(Math.max(ii.length, 1), 5));
  $("ideas").innerHTML = ii.length ? ii.map((x) => `<article class="idea"><div class="fila"><h3>${esc(x.activo)}</h3><span class="chip">${esc(x.horizonte)}</span></div>
      <div>${esc(x.idea)}</div><dl><div><dt>A favor</dt><dd>${esc(x.a_favor)}</dd></div><div><dt>En contra</dt><dd>${esc(x.en_contra)}</dd></div>
      <div><dt>Qué la invalida</dt><dd>${esc(x.que_la_invalida)}</dd></div></dl></article>`).join("") : `<p class="vacio">Sin ideas en la última lectura.</p>`;
}

/* ---------- bonos: un eje (rendimiento en %), 4 series, cruz con tooltip ---------- */
function bonos() {
  const b = D.bonos;
  if (!b) return;
  $("bonos-meta").textContent = `Rendimiento en % · último dato ${b.tabla?.[0]?.fecha || "–"}`;
  $("bonos-tabla").innerHTML = `<thead><tr><th>Plazo</th><th class="n">Hoy</th><th class="n">1 día</th><th class="n">1 semana</th><th class="n">1 mes</th></tr></thead><tbody>${
    (b.tabla || []).map((f) => `<tr><td>${esc(f.nombre)}</td><td class="n">${fmt(f.ultimo)}${f.es_pendiente ? " pp" : " %"}</td>${["d1_pb", "d5_pb", "d21_pb"].map((k) => `<td class="n ${clase(f[k])}">${f[k] > 0 ? "+" : ""}${f[k]} pb</td>`).join("")}</tr>`).join("")}</tbody>`;
  const nombres = Object.keys(b.series || {}), cols = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)"];
  const el = $("bonos-graf"), W = el.clientWidth || 560, H = 210, ml = 34, mr = 92, mt = 8, mb = 22;
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
  for (let i = 1; i < fin.length; i++) if (fin[i].y - fin[i - 1].y < 13) fin[i].y = fin[i - 1].y + 13;
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
  $("valor").querySelectorAll("[data-tip]").forEach((c) => { c.addEventListener("pointermove", (ev) => mostrarTip(c.dataset.tip, ev.clientX, ev.clientY)); c.addEventListener("pointerleave", ocultarTip); });
  $("ratios").innerHTML = (v.ratios || []).map((r) => `<div class="ratio"><div><b>${esc(r.nombre)}</b> <span class="num">${fmt(r.hoy, r.hoy < 10 ? 3 : 1)}</span> · percentil ${r.pctl_10a}</div>
      <div class="l">${esc(r.lectura)} · mediana 10 años ${fmt(r.mediana_10a, r.mediana_10a < 10 ? 3 : 1)}</div>${sparkline(r.serie, 90, 30)}</div>`).join("");
}

/* ---------- analistas ---------- */
function estadoClase(e) {
  return e.startsWith("cumplida") ? "cumplida" : e.startsWith("fallida") ? "fallida" : e === "en curso (a favor)" ? "favor" : e === "en curso (en contra)" ? "contra" : "";
}
function analistas() {
  const t = D.tesis;
  if (!t) return;
  const T = t.totales;
  $("analistas-meta").textContent = `José Luis Cava · ${T.videos} videos · ${T.tesis} tesis con cita y minuto · verificadas contra precios ${haceTxt(t.generado)}`;
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
      <span class="nota">${esc(x.fecha_video)} · <a href="https://youtu.be/${esc(x.video_id)}?t=${minutoSeg(x.minuto)}" target="_blank" rel="noopener">${esc(x.minuto)}</a>${x.ret_hoy != null ? ` · desde el video ${pct(x.ret_hoy * 100, 1)}` : ""}${x.condicion ? ` · ${esc(x.condicion)}` : ""}</span></div>`).join("");
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
  });
})();

/* ---------- arranque ---------- */
relojes();
setInterval(relojes, 15000);
setInterval(() => { seguro(frescura); seguro(sesiones); document.querySelectorAll(".cuenta[data-t]").forEach((c) => { if (c.textContent !== "publicado") c.textContent = cuentaAtras(+c.dataset.t) || "publicado"; }); }, 30000);
setInterval(cargar, 5 * 60 * 1000);
window.addEventListener("resize", () => { seguro(sesiones); seguro(bonos); seguro(titulares); });
document.addEventListener("visibilitychange", () => { if (!document.hidden) cargar(); });
cargar();
