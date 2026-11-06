// Il telefono del giocatore: entra nella stanza della TV, sceglie Gandalf o il Balrog,
// tiene le sue carte e sceglie quale giocare. In alto la barra dell'energia.
// Sono attive solo le scelte valide: le decide la TV.
import { creaRete, RADICE } from './rete.js';

const q = new URLSearchParams(location.search);
const app = document.getElementById('app');
let rete = null;
let codice = (q.get('s') || '').toUpperCase().replace(/[^A-Z]/g, '');
let uid = '';
let nome = localStorage.getItem('lotr_nome') || '';
let ruoloScelto = '';
let S = null;      // stato pubblico della partita (dalla TV)
let M = null;      // le mie carte e la domanda per me (solo per me)
let io = null;     // la mia iscrizione nella stanza
let inviato = -1;  // numero della decisione già inviata
let selezione = [];
let aperta = -1;   // carta ingrandita

const NOMI = { G: 'Gandalf', B: 'il Balrog' };
const NOMI_M = { G: 'Gandalf', B: 'Il Balrog' };
const img = (id) => `img/carte/${id}.webp`;
function esc(s) { return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }

// ------------------------------------------------------------------ ingresso
function schermataCodice(msg = '') {
  app.innerHTML = `<h1>Il Duello</h1><p class="sotto">Gandalf contro il Balrog</p>
    <div class="box"><h2>Entra nella partita</h2><p>Scrivi il codice di 4 lettere che vedi sulla TV.</p>
    <input id="cod" maxlength="4" placeholder="CODICE" autocapitalize="characters" autocomplete="off">
    <button class="primario" id="vai">Entra</button>${msg ? `<p class="piccolo">${esc(msg)}</p>` : ''}</div>`;
  const i = app.querySelector('#cod');
  const vai = () => {
    const c = i.value.toUpperCase().replace(/[^A-Z]/g, '');
    if (c.length === 4) location.search = '?s=' + c + (q.get('rete') ? '&rete=' + q.get('rete') : '');
  };
  app.querySelector('#vai').onclick = vai;
  i.onkeydown = (e) => { if (e.key === 'Enter') vai(); };
}

function schermataRuolo() {
  const cons = S?.consentiti || [];
  if (!ruoloScelto || !cons.includes(ruoloScelto) || S?.ruoli?.[ruoloScelto]) ruoloScelto = cons.find((r) => !S?.ruoli?.[r]) || '';
  const bott = ['G', 'B'].map((r) => {
    const occupato = S?.ruoli?.[r];
    const ok = cons.includes(r) && !occupato;
    return `<button class="ruolo ${r === ruoloScelto ? 'scelto' : ''}" data-r="${r}" ${ok ? '' : 'disabled'}>
      <img src="${img(r === 'G' ? 29 : 49)}" alt=""><span>${r === 'G' ? 'Gandalf' : 'Il Balrog'}</span>
      ${occupato ? `<div class="piccolo">preso da ${esc(occupato)}</div>` : (cons.includes(r) ? '' : '<div class="piccolo">lo gioca il computer</div>')}</button>`;
  }).join('');
  app.innerHTML = `<h1>Il Duello</h1><div class="box"><h2>Come ti chiami?</h2>
    <input id="nome" maxlength="14" placeholder="Il tuo nome" value="${esc(nome)}" autocomplete="off">
    <h2>Chi sei?</h2><div class="ruoli">${bott}</div>
    <button class="primario" id="entra" ${ruoloScelto ? '' : 'disabled'}>Prendi le carte</button>
    ${cons.length ? '' : '<p class="piccolo">Sulla TV non c\'è ancora una partita in corso.</p>'}</div>`;
  app.querySelectorAll('[data-r]').forEach((b) => { b.onclick = () => { ruoloScelto = b.dataset.r; nome = app.querySelector('#nome').value; schermataRuolo(); }; });
  app.querySelector('#entra').onclick = async () => {
    const n = app.querySelector('#nome').value.trim().slice(0, 14) || (ruoloScelto === 'G' ? 'Gandalf' : 'Balrog');
    nome = n;
    localStorage.setItem('lotr_nome', n);
    await rete.set(`${RADICE}/${codice}/giocatori/${uid}`, { nome: n, ruolo: ruoloScelto });
  };
}

// ------------------------------------------------------------------ partita
function barraEnergia() {
  const e = S.energia || { G: 10, B: 10 };
  let celle = '';
  for (let v = -4; v <= 15; v++) {
    const cls = ['casella'];
    if (v <= 0) cls.push('neg');
    if (v === 10) cls.push('d');
    if (v === 15) cls.push('f');
    celle += `<div class="${cls.join(' ')}">${e.G === v ? '<div class="seg g"></div>' : ''}${e.B === v ? '<div class="seg b"></div>' : ''}</div>`;
  }
  return `<div class="energia"><div class="traccia">${celle}</div>
    <div class="info"><span><b>${esc(S.titolo || '')}</b></span><span>Gandalf ${e.G}, Balrog ${e.B}, vuote ${S.vuote ?? 0}</span></div></div>`;
}

function cartaHtml(id, attiva, scelta, etichetta = '') {
  return `<div class="carta ${attiva ? 'attiva' : 'spenta'} ${scelta ? 'scelta' : ''}" data-id="${id}">
    ${etichetta ? `<div class="etichetta">${esc(etichetta)}</div>` : ''}<img src="${img(id)}" alt=""></div>`;
}

function invia(tipo, v) {
  if (!M || inviato === M.n) return;
  inviato = M.n;
  aperta = -1;
  rete.push(`${RADICE}/${codice}/azioni`, { da: uid, p: JSON.stringify({ tipo, v, n: M.n }), k: 'd' });
  disegna();
}

function disegna() {
  document.querySelectorAll('.grande').forEach((x) => x.remove());
  if (!io) { schermataRuolo(); return; }
  if (!S) { app.innerHTML = '<p class="attesa">Collegamento con la TV...</p>'; return; }
  const ruolo = io.ruolo;
  const tipo = M?.tipo || '';
  const mio = M && M.n !== inviato && tipo;
  let corpo = '';
  let msg = S.msg || '';
  if (S.fine) {
    const vinto = S.fine === ruolo;
    corpo = `<div class="fine">${vinto ? 'Hai vinto!' : 'Hai perso'}</div><p class="attesa">${esc(S.ultimo || '')}</p>`;
  } else if (mio && ['incanto', 'magia'].includes(tipo)) {
    const domanda = tipo === 'incanto' ? 'Il Balrog deve giocare ora la carta incantata?' : 'Prendi questa carta del Balrog per il suo duello finale?';
    corpo = `<div class="box"><h2>${domanda}</h2>${cartaHtml(M.carta, true, false)}
      <button class="primario" id="si">Sì</button><button id="no">No</button></div>`;
  } else if (mio && tipo === 'inizio') {
    corpo = `<div class="box"><h2>Chi inizia il duello?</h2><p class="piccolo">Chi inizia perde in caso di pareggio.</p>
      <button class="primario" data-ini="G">Gandalf</button><button data-ini="B">Il Balrog</button></div>`;
  } else if (mio && tipo === 'frusta') {
    corpo = `<div class="box"><h2>Frusta: quale tua carta riusi?</h2><div class="riga">
      ${M.riga.map((r) => `<div class="carta attiva" data-frusta="${r.i}"><img src="${img(r.id)}" alt=""></div>`).join('')}</div></div>`;
  } else if (mio && tipo === 'avanti') {
    corpo = `<div class="box"><p>${esc(S.ultimo || '')}</p><button class="primario" id="avanti">Continua</button></div>`;
  }
  if (mio && tipo === 'riserva') msg = `Scegli ${M.quante} carte per il duello finale (${selezione.length}/${M.quante})`;
  else if (mio && tipo === 'difesa') msg = 'Metti una carta nello spazio vuoto (non conta)';
  else if (mio && tipo === 'gioca') msg = M.motivo === 'forza' ? 'Devi rispondere con la carta pescata dal Balrog' : (M.motivo === 'incantata' ? 'Devi giocare la carta incantata' : 'Tocca a te: scegli la carta');
  else if (!S.fine && !mio) msg = S.msg || '';
  // la mano
  const opz = (mio && ['gioca', 'difesa', 'riserva'].includes(tipo)) ? (M.opzioni || []) : [];
  const mano = [...(M?.mano || [])];
  if (M?.incantata >= 0) mano.push(M.incantata);
  const carte = mano.map((id) => cartaHtml(id, opz.includes(id), selezione.includes(id), id === M?.incantata ? 'incantata' : (id === M?.forzata ? 'pescata' : ''))).join('');
  const scop = (M?.scoperte || []).length ? `<div class="box"><span class="piccolo">Carte di ${NOMI[ruolo === 'G' ? 'B' : 'G']}</span>
    <div class="scoperte">${M.scoperte.map((id) => `<img src="${img(id)}" alt="" data-vedi="${id}">`).join('')}</div></div>` : '';
  const conferma = (mio && tipo === 'riserva') ? `<button class="primario" id="conf" ${selezione.length === M.quante ? '' : 'disabled'}>Conferma</button>` : '';
  app.innerHTML = `${barraEnergia()}<div class="messaggio ${mio ? 'tocca' : ''}">${esc(msg)}</div>${corpo}
    ${S.fine ? '' : `<div class="mano">${carte}</div>${conferma}`}${scop}
    <p class="piccolo" style="text-align:center">${esc(nome)}: sei ${NOMI[ruolo]} &middot; stanza ${esc(codice)}</p>`;
  // gestori
  app.querySelector('#si')?.addEventListener('click', () => invia(tipo, true));
  app.querySelector('#no')?.addEventListener('click', () => invia(tipo, false));
  app.querySelector('#avanti')?.addEventListener('click', () => invia('avanti', true));
  app.querySelector('#conf')?.addEventListener('click', () => { invia('riserva', selezione.slice()); selezione = []; });
  app.querySelectorAll('[data-ini]').forEach((b) => { b.onclick = () => invia('inizio', b.dataset.ini); });
  app.querySelectorAll('[data-frusta]').forEach((b) => { b.onclick = () => invia('frusta', Number(b.dataset.frusta)); });
  app.querySelectorAll('.mano .carta').forEach((c) => {
    c.onclick = () => {
      const id = Number(c.dataset.id);
      if (tipo === 'riserva' && opz.includes(id)) {
        if (selezione.includes(id)) selezione = selezione.filter((x) => x !== id);
        else if (selezione.length < M.quante) selezione.push(id);
        disegna();
        return;
      }
      ingrandisci(id, opz.includes(id) ? tipo : '');
    };
  });
  app.querySelectorAll('[data-vedi]').forEach((c) => { c.onclick = () => ingrandisci(Number(c.dataset.vedi), ''); });
  if (aperta >= 0) ingrandisci(aperta, opz.includes(aperta) ? tipo : '');
}

// la carta ingrandita, con il pulsante per giocarla se si può
function ingrandisci(id, tipo) {
  aperta = id;
  const d = document.createElement('div');
  d.className = 'grande';
  const testo = tipo === 'gioca' ? 'Gioca questa carta' : (tipo === 'difesa' ? 'Metti nello spazio vuoto' : '');
  d.innerHTML = `<img src="${img(id)}" alt=""><div class="azioni">${testo ? `<button class="primario" id="gioca">${testo}</button>` : ''}
    <button id="chiudi">Chiudi</button></div>`;
  document.body.appendChild(d);
  const chiudi = () => { aperta = -1; d.remove(); };
  d.querySelector('#chiudi').onclick = chiudi;
  d.onclick = (e) => { if (e.target === d) chiudi(); };
  d.querySelector('#gioca')?.addEventListener('click', () => { d.remove(); invia(tipo, id); });
}

// ------------------------------------------------------------------ avvio
async function avvia() {
  if (!codice) { schermataCodice(); return; }
  app.innerHTML = '<p class="attesa">Collegamento...</p>';
  rete = creaRete();
  try { uid = await rete.init(); } catch (e) { schermataCodice('Non riesco a collegarmi: ' + (e?.message || e)); return; }
  const host = await rete.get(`${RADICE}/${codice}/host`);
  if (!host) { schermataCodice('La stanza ' + codice + ' non esiste: controlla il codice sulla TV.'); return; }
  rete.on(`${RADICE}/${codice}/stato`, (v) => {
    try { S = v ? JSON.parse(v) : null; } catch (e) { S = null; }
    document.querySelectorAll('.grande').forEach((x) => x.remove());
    disegna();
  });
  rete.on(`${RADICE}/${codice}/giocatori/${uid}`, (v) => { io = v && v.ruolo ? v : null; disegna(); });
  rete.on(`${RADICE}/${codice}/segreti/${uid}`, (v) => {
    let m = null;
    try { m = v ? JSON.parse(v) : null; } catch (e) { m = null; }
    if (m && M && m.n !== M.n) selezione = [];
    M = m;
    document.querySelectorAll('.grande').forEach((x) => x.remove());
    disegna();
  });
  // lo schermo resta acceso durante la partita
  try { if ('wakeLock' in navigator) await navigator.wakeLock.request('screen'); } catch (e) { /* ok */ }
}
avvia();
