// Ponte tra la TV (Godot, versione web) e i telefoni dei giocatori: stanza su Firebase e QR code.
// Godot lo usa con JavaScriptBridge.get_interface("LT"). Tutto passa come testo JSON.
import { creaRete, nuovoCodice, RADICE } from './rete.js';

const coda = [];
const q = new URLSearchParams(location.search);
let rete = null;
let codice = '';
let stacca = [];

function base() {
  return location.href.split('?')[0].split('#')[0].replace(/index\.html$/, '');
}

window.LT = {
  codice() { return codice; },
  preleva() {
    if (!coda.length) return '[]';
    const s = JSON.stringify(coda);
    coda.length = 0;
    return s;
  },
  // crea la stanza (o riprende quella di prima, se è ancora nostra)
  async avvia(riprendi) {
    try {
      if (!rete) { rete = creaRete(); await rete.init(); }
      for (const f of stacca) { try { f(); } catch (e) { /* ok */ } }
      stacca = [];
      let c = '';
      if (riprendi) {
        const h = await rete.get(`${RADICE}/${riprendi}/host`);
        if (h === rete.uid) c = riprendi;
      }
      if (!c) {
        for (let i = 0; i < 30 && !c; i++) {
          const k = nuovoCodice();
          const h = await rete.get(`${RADICE}/${k}/host`);
          if (!h) c = k;
        }
        await rete.set(`${RADICE}/${c}/host`, rete.uid);
        await rete.set(`${RADICE}/${c}/created`, Date.now());
      }
      codice = c;
      const url = base() + 'telefono.html?s=' + c + (q.get('rete') === 'locale' ? '&rete=locale' : '');
      coda.push({ e: 'stanza', codice: c, url });
      stacca.push(rete.onFigli(`${RADICE}/${c}/giocatori`, {
        aggiunto: (k, v) => coda.push({ e: 'entra', uid: k, nome: v?.nome || '', ruolo: v?.ruolo || '' }),
        cambiato: (k, v) => coda.push({ e: 'entra', uid: k, nome: v?.nome || '', ruolo: v?.ruolo || '' }),
        tolto: (k) => coda.push({ e: 'esce', uid: k }),
      }));
      stacca.push(rete.onFigli(`${RADICE}/${c}/azioni`, {
        aggiunto: (k, v) => {
          if (v && v.da) coda.push({ e: 'azione', uid: v.da, p: v.p, k: v.k });
          if (c === codice) rete.remove(`${RADICE}/${c}/azioni/${k}`);
        },
      }));
    } catch (e) {
      console.error(e);
      coda.push({ e: 'errore', msg: String(e?.message || e) });
    }
  },
  stato(j) { if (rete && codice) rete.set(`${RADICE}/${codice}/stato`, j).catch((e) => console.warn(e)); },
  segreto(uid, j) { if (rete && codice) rete.set(`${RADICE}/${codice}/segreti/${uid}`, j).catch((e) => console.warn(e)); },
  togli(uid) { if (rete && codice) rete.remove(`${RADICE}/${codice}/giocatori/${uid}`).catch((e) => console.warn(e)); },
  qr(testo) {
    /* global qrcode */
    try {
      const qq = qrcode(0, 'M');
      qq.addData(testo);
      qq.make();
      const n = qq.getModuleCount();
      let s = '';
      for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) s += qq.isDark(y, x) ? '1' : '0';
      return s;
    } catch (e) { return ''; }
  },
};
