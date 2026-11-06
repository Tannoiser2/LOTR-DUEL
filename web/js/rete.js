// Collegamento tra la TV (ippodromo) e i telefoni dei giocatori.
// Due motori con la stessa interfaccia:
//  - Firebase Realtime Database (progetto condiviso della ludoteca, radice "lotrduel/telefoni")
//  - "locale": schede dello stesso browser collegate con BroadcastChannel (solo per prove: ?rete=locale)

const FIREBASE = {
  apiKey: 'AIzaSyCf1NQodB-J3OrdU_gHYQ1I6VJtXBk1ciU',
  authDomain: 'flammerouge-f8669.firebaseapp.com',
  databaseURL: 'https://flammerouge-f8669-default-rtdb.europe-west1.firebasedatabase.app',
  projectId: 'flammerouge-f8669',
};
export const RADICE = 'lotrduel/telefoni';

// ---------------------------------------------------------------- Firebase
class ReteFirebase {
  constructor() { this.tipo = 'firebase'; }
  async init() {
    const fb = await import('./vendor/firebase.js');
    this.fb = fb;
    const app = fb.initializeApp(FIREBASE);
    this.auth = fb.getAuth(app);
    this.db = fb.getDatabase(app);
    this.uid = await new Promise((ok, ko) => {
      const stop = fb.onAuthStateChanged(this.auth, (u) => {
        if (u) { stop(); ok(u.uid); }
      });
      fb.signInAnonymously(this.auth).catch((e) => { stop(); ko(e); });
    });
    // stato della connessione (per avvisare se il telefono perde la rete)
    fb.onValue(fb.ref(this.db, '.info/connected'), (s) => { this.connesso = !!s.val(); this.onConnessione?.(this.connesso); });
    return this.uid;
  }
  r(p) { return this.fb.ref(this.db, p); }
  set(p, v) { return this.fb.set(this.r(p), v); }
  update(p, v) { return this.fb.update(this.r(p), v); }
  remove(p) { return this.fb.remove(this.r(p)); }
  push(p, v) { return this.fb.push(this.r(p), v); }
  async get(p) { const s = await this.fb.get(this.r(p)); return s.val(); }
  on(p, cb) { return this.fb.onValue(this.r(p), (s) => cb(s.val())); }
  onFigli(p, { aggiunto, cambiato, tolto }) {
    const u = [];
    if (aggiunto) u.push(this.fb.onChildAdded(this.r(p), (s) => aggiunto(s.key, s.val())));
    if (cambiato) u.push(this.fb.onChildChanged(this.r(p), (s) => cambiato(s.key, s.val())));
    if (tolto) u.push(this.fb.onChildRemoved(this.r(p), (s) => tolto(s.key, s.val())));
    return () => u.forEach((f) => f());
  }
}

// ---------------------------------------------------------------- Locale (prove)
function parti(p) { return p.split('/').filter(Boolean); }
function leggi(albero, p) {
  let n = albero;
  for (const k of parti(p)) { if (n == null || typeof n !== 'object') return null; n = n[k]; }
  return n === undefined ? null : n;
}
function scrivi(albero, p, v) {
  const ks = parti(p);
  let n = albero;
  for (let i = 0; i < ks.length - 1; i++) {
    if (n[ks[i]] == null || typeof n[ks[i]] !== 'object') n[ks[i]] = {};
    n = n[ks[i]];
  }
  if (v === null || v === undefined) delete n[ks[ks.length - 1]];
  else n[ks[ks.length - 1]] = JSON.parse(JSON.stringify(v));
}

class ReteLocale {
  constructor() {
    this.tipo = 'locale';
    this.albero = {};
    this.ascolti = [];
    this.connesso = true;
  }
  async init() {
    let uid = sessionStorage.getItem('lotr_uid_locale');
    if (!uid) { uid = 'u' + Math.random().toString(36).slice(2, 10); sessionStorage.setItem('lotr_uid_locale', uid); }
    this.uid = uid;
    this.canale = new BroadcastChannel('lotrduel-locale');
    this.canale.onmessage = (e) => this.ricevi(e.data);
    // chiede l'albero alle altre schede
    await new Promise((ok) => {
      const fine = setTimeout(ok, 4000);
      this.attesaSync = (a) => { clearTimeout(fine); this.albero = a; ok(); };
      this.canale.postMessage({ op: 'sync?' });
    });
    this.attesaSync = null;
    return uid;
  }
  ricevi(m) {
    if (m.op === 'sync?') { this.canale.postMessage({ op: 'sync', albero: this.albero }); return; }
    if (m.op === 'sync') { if (this.attesaSync) this.attesaSync(m.albero); return; }
    if (m.op === 'w') { for (const [p, v] of m.w) scrivi(this.albero, p, v); this.avvisa(); }
  }
  applica(w) {
    for (const [p, v] of w) scrivi(this.albero, p, v);
    this.canale.postMessage({ op: 'w', w });
    setTimeout(() => this.avvisa(), 0);
    return Promise.resolve();
  }
  set(p, v) { return this.applica([[p, v]]); }
  update(p, v) { return this.applica(Object.entries(v).map(([k, x]) => [p + '/' + k, x])); }
  remove(p) { return this.applica([[p, null]]); }
  push(p, v) {
    const k = Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
    this.applica([[p + '/' + k, v]]);
    return Promise.resolve({ key: k });
  }
  get(p) { return Promise.resolve(JSON.parse(JSON.stringify(leggi(this.albero, p)))); }
  on(p, cb) {
    const a = { p, cb, tipo: 'v', ultimo: undefined };
    this.ascolti.push(a);
    setTimeout(() => this.avvisaUno(a), 0);
    return () => { this.ascolti = this.ascolti.filter((x) => x !== a); };
  }
  onFigli(p, h) {
    const a = { p, h, tipo: 'f', figli: {} };
    this.ascolti.push(a);
    setTimeout(() => this.avvisaUno(a), 0);
    return () => { this.ascolti = this.ascolti.filter((x) => x !== a); };
  }
  avvisa() { for (const a of [...this.ascolti]) this.avvisaUno(a); }
  avvisaUno(a) {
    const v = leggi(this.albero, a.p);
    if (a.tipo === 'v') {
      const j = JSON.stringify(v);
      if (j !== a.ultimo) { a.ultimo = j; a.cb(JSON.parse(j)); }
      return;
    }
    const ora = v && typeof v === 'object' ? v : {};
    const nuovi = {};
    for (const k of Object.keys(ora)) {
      const j = JSON.stringify(ora[k]);
      nuovi[k] = j;
      if (!(k in a.figli)) a.h.aggiunto?.(k, JSON.parse(j));
      else if (a.figli[k] !== j) a.h.cambiato?.(k, JSON.parse(j));
    }
    for (const k of Object.keys(a.figli)) if (!(k in nuovi)) a.h.tolto?.(k, JSON.parse(a.figli[k]));
    a.figli = nuovi;
  }
}

export function creaRete() {
  const q = new URLSearchParams(location.search);
  return q.get('rete') === 'locale' ? new ReteLocale() : new ReteFirebase();
}

const LETTERE = 'ABCDEFGHJKLMNPQRSTUVWXYZ';
export function nuovoCodice() {
  let s = '';
  for (let i = 0; i < 4; i++) s += LETTERE[Math.floor(Math.random() * LETTERE.length)];
  return s;
}
