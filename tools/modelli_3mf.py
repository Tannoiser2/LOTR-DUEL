# -*- coding: utf-8 -*-
"""
Modelli 3D di gioco (Gandalf e il Balrog) ricavati dal diorama scolpito per la stampa 3D.

Punto di partenza: /home/claude/src/3mf/objs.pkl, estratto dal file .3mf del diorama:
    dict {'1': (vertici Nx3 float32, triangoli Mx3 int32), '3': ..., '5': ...}
    unita' millimetri, Z in alto (sistema di stampa), ogni pezzo centrato sul proprio bbox.
      '1' = il Balrog (220k vertici)
      '3' = la mano destra di Gandalf con Glamdring, con il perno del polso
      '5' = il corpo di Gandalf (due meta' gia' accostate, maniche cave con un foro
            per il perno) + un'isola separata: la mano sinistra col bastone, distesa.

Fasi (tutte in questo script):
  1. "rimonta le braccia": separa le isole di '5', infila il perno di ogni mano nel
     foro della manica (asse del perno = asse del foro) e ruota la mano attorno
     all'asse come nelle foto del diorama montato (bastone alzato quasi verticale
     nella mano verso il Balrog, Glamdring piu' in basso e in avanti nell'altra).
  2. colori per vertice sull'alta risoluzione (zone ricavate con euristiche
     geometriche: altezza, proiezioni frontali, distanze da assi, cavita').
  3. decimazione (collapse) a un budget web, UV automatiche, "cottura" Cycles
     dall'alta alla bassa risoluzione: mappa normale, colore, emissione,
     rugosita'/metallo, occlusione ambientale (moltiplicata nel colore).
  4. esportazione .glb (texture JPEG incorporate), .blend "puliti" per il rigging
     futuro, anteprime e verifica.

Uso (dalla radice del progetto):
    /home/claude/bvenv/bin/python tools/modelli_3mf.py [gandalf|balrog|tutti|verifica] [--rifai] [--no-render]

    --rifai      ricalcola anche le cache intermedie (alta risoluzione + colori)
    --no-render  salta le anteprime

Convenzioni (le stesse di tools/modelli_blender.py):
  - 1 unita' Blender = 1 metro = 1 unita' Godot.
  - Blender Z in alto; l'esportatore glTF mappa Blender (x, y, z) -> glTF (x, z, -y).
  - I personaggi guardano verso -Y in Blender, cioe' verso +Z in Godot.
  - Origine al centro dei piedi, suola a quota 0.
"""

import bpy
import math
import os
import pickle
import sys
import time

import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR_ASSET = os.path.join(RADICE, "assets", "3d")
DIR_SRC = "/home/claude/src/3mf"
DIR_CACHE = os.path.join(DIR_SRC, "cache")
DIR_ANTEPRIME = "/home/claude/src"
PKL = os.path.join(DIR_SRC, "objs.pkl")

RIFAI = "--rifai" in sys.argv
RENDER = "--no-render" not in sys.argv

ALTEZZA_GANDALF = 1.9    # dalla suola alla sommita' della testa (senza bastone)
ALTEZZA_BALROG = 3.4     # dalla suola alla sommita' di testa/corna (la criniera va oltre)


def log(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------------------
#  Utilita' numpy sulle mesh
# ---------------------------------------------------------------------------

def componenti(nv, f):
    """Etichetta delle componenti connesse (propagazione del minimo + salti di puntatore)."""
    lab = np.arange(nv)
    while True:
        m = lab[f].min(1)
        vecchio = lab.copy()
        for i in range(3):
            np.minimum.at(lab, f[:, i], m)
        for _ in range(6):
            lab = lab[lab]
        if (lab == vecchio).all():
            return lab


def sotto_mesh(v, f, maschera_v):
    """Estrae i vertici selezionati e i triangoli che li usano, rinumerati."""
    idx = np.where(maschera_v)[0]
    nuovo = -np.ones(len(v), np.int64)
    nuovo[idx] = np.arange(len(idx))
    ft = f[maschera_v[f[:, 0]]]
    return v[idx].copy(), nuovo[ft].astype(np.int32)


def normali_vertici(v, f):
    fn = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    n = np.zeros_like(v, dtype=np.float64)
    for i in range(3):
        for k in range(3):
            n[:, k] += np.bincount(f[:, i], fn[:, k], minlength=len(v))
    return n / (np.linalg.norm(n, axis=1)[:, None] + 1e-12)


class Vicinato:
    """Media sui vicini (operatore "ombrello") per lisciare posizioni e attributi."""

    def __init__(self, nv, f):
        e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
        self.a = np.concatenate([e[:, 0], e[:, 1]])
        self.b = np.concatenate([e[:, 1], e[:, 0]])
        self.nv = nv
        self.grado = np.bincount(self.a, minlength=nv).astype(np.float64) + 1e-9

    def media(self, x):
        if x.ndim == 1:
            return np.bincount(self.a, x[self.b], minlength=self.nv) / self.grado
        return np.stack([self.media(x[:, k]) for k in range(x.shape[1])], 1)

    def liscia(self, x, iterazioni):
        for _ in range(iterazioni):
            x = 0.5 * x + 0.5 * self.media(x)
        return x


def cavita(v, f, n, vic, iterazioni):
    """> 0 nelle pieghe/crepe (concavo), < 0 sui rilievi; in unita' della mesh."""
    p = vic.liscia(v.astype(np.float64), iterazioni)
    return ((p - v) * n).sum(1)


def spessore(v, n, bvh, massimo):
    """Spessore locale: raggio lanciato verso l'interno lungo -normale."""
    out = np.full(len(v), massimo)
    for i in range(len(v)):
        o = Vector(v[i] - n[i] * 1e-3)
        h = bvh.ray_cast(o, Vector(-n[i]), massimo)
        if h[0] is not None:
            out[i] = h[3]
    return out


def bvh_da(v, f):
    return BVHTree.FromPolygons(v.tolist(), f.tolist(), all_triangles=True)


def srgb(c):
    """Colore sRGB (0..1) -> lineare (gli attributi colore di Blender sono lineari)."""
    c = np.asarray(c, np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def rumore3(p, scala, seme=0):
    """Rumore "di valore" 3D economico (somma di sinusoidi sfasate), ~[-1, 1]."""
    rng = np.random.default_rng(seme)
    out = np.zeros(len(p))
    for k in range(6):
        d = rng.normal(size=3)
        d /= np.linalg.norm(d)
        fr = scala * (1.7 ** k)
        out += np.sin(p @ d * fr + rng.uniform(0, 6.28)) / (1.6 ** k)
    return out / 2.2


def in_poligono(x, y, poli):
    """Punto nel poligono (ray casting vettoriale)."""
    poli = np.asarray(poli, np.float64)
    dentro = np.zeros(len(x), bool)
    j = len(poli) - 1
    for i in range(len(poli)):
        xi, yi = poli[i]
        xj, yj = poli[j]
        c = ((yi > y) != (yj > y)) & (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi)
        dentro ^= c
        j = i
    return dentro


def superficie_esposta(v, asse_vista, asse_u, asse_w, cella, tolleranza, verso=1):
    """Vertici sulla superficie visibile guardando lungo un asse (z-buffer a celle).

    verso=+1: visibili da chi guarda dal lato dei valori minimi di asse_vista
    (es. asse_vista=1 -> visibili da davanti, da -Y)."""
    u = np.floor(v[:, asse_u] / cella).astype(np.int64)
    w = np.floor(v[:, asse_w] / cella).astype(np.int64)
    u -= u.min()
    w -= w.min()
    chiave = u * (w.max() + 1) + w
    prof = v[:, asse_vista] * verso
    pmin = np.full(chiave.max() + 1, np.inf)
    np.minimum.at(pmin, chiave, prof)
    # allarga il minimo alle celle vicine per evitare buchi
    return prof - pmin[chiave] < tolleranza


# ---------------------------------------------------------------------------
#  Rotazioni
# ---------------------------------------------------------------------------

def rot_da_a(a, b):
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    v = np.cross(a, b)
    c = a @ b
    if c < -0.9999:
        p = np.cross(a, [1, 0, 0])
        if np.linalg.norm(p) < 1e-3:
            p = np.cross(a, [0, 1, 0])
        p /= np.linalg.norm(p)
        return 2 * np.outer(p, p) - np.eye(3)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K / (1 + c)


def rot_asse(a, ang):
    a = a / np.linalg.norm(a)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(ang) * K + (1 - math.cos(ang)) * K @ K


def infila(perno, normale_perno, foro, asse_foro, profondita, gradi):
    """Rototraslazione che porta il perno nel foro.

    Il perno (centro del tappo piatto + normale uscente) va contro l'asse del foro
    (asse_foro punta verso l'esterno della manica), con il tappo `profondita` mm
    dentro il foro; poi rotazione di `gradi` attorno all'asse."""
    asse_foro = np.asarray(asse_foro, np.float64)
    asse_foro /= np.linalg.norm(asse_foro)
    R = rot_asse(asse_foro, math.radians(gradi)) @ rot_da_a(np.asarray(normale_perno, np.float64), -asse_foro)
    t = np.asarray(foro) - asse_foro * profondita - R @ np.asarray(perno)
    return R, t


# ---------------------------------------------------------------------------
#  GANDALF: montaggio e colori (tutto nel sistema in mm del file di stampa)
# ---------------------------------------------------------------------------
#  Misure ricavate dall'analisi del modello (sezioni delle maniche, tappi dei perni):
#   - foro della manica sinistra (alzata, lato +X):  centro (7.97, 3.45, 20.18),
#     asse verso l'esterno (0.658, -0.607, 0.446), raggio ~1.2 mm
#   - foro della manica destra (lato -X):            centro (-19.38, 10.31, 8.37),
#     asse verso l'esterno (-0.732, -0.571, -0.371)
#   - perno della mano col bastone: tappo (17.35, -4.79, -17.53), normale (-0.445, -0.248, 0.861)
#   - perno della mano con la spada: tappo (0.36, 15.14, -3.93), normale (0.119, 0.606, 0.786)
#  Gli angoli attorno all'asse sono stati scelti confrontando le anteprime con le foto:
#  bastone con la testa in alto, inclinato verso la testa di Gandalf; Glamdring in
#  avanti e verso l'alto, davanti al petto, puntata verso il Balrog.

FORO_SIN = ((7.97, 3.45, 20.18), (0.658, -0.607, 0.446))
FORO_DES = ((-19.38, 10.31, 8.37), (-0.732, -0.571, -0.371))
PERNO_BASTONE = ((17.35, -4.79, -17.53), (-0.445, -0.248, 0.861))
PERNO_SPADA = ((0.36, 15.14, -3.93), (0.119, 0.606, 0.786))
POSA_BASTONE = dict(profondita=1.7, gradi=94)
POSA_SPADA = dict(profondita=2.0, gradi=329)
# riferimenti nei sistemi originali dei pezzi
BASTONE_ASSE = np.array([0.049, 0.982, 0.181])          # verso la testa del bastone
CRISTALLO_BASTONE = np.array([20.8, 23.4, -16.9])        # pietra sfaccettata nella testa
SPADA_POMOLO = np.array([0.56, 15.45, -12.9])
SPADA_ASSE = np.array([-0.045, -0.779, 0.625])           # dal pomolo verso la punta

# palette (sRGB)
C_VESTE = (0.47, 0.50, 0.56)
C_VESTE_SCURA = (0.27, 0.29, 0.34)
C_CAPELLI = (0.84, 0.84, 0.82)
C_CAPELLI_SCURI = (0.52, 0.52, 0.52)
C_PELLE = (0.80, 0.62, 0.52)
C_CORDA = (0.36, 0.34, 0.31)
C_LEGNO = (0.36, 0.23, 0.12)
C_LEGNO_SCURO = (0.17, 0.10, 0.05)
C_ACCIAIO = (0.78, 0.80, 0.83)
C_ORO = (0.86, 0.66, 0.30)
C_CUOIO = (0.22, 0.13, 0.07)
C_CRISTALLO = (0.85, 0.93, 1.0)


def carica_pkl():
    return pickle.load(open(PKL, "rb"))


def gandalf_alta():
    """Restituisce (v, f, attributi) dell'alta risoluzione montata, in metri."""
    os.makedirs(DIR_CACHE, exist_ok=True)
    cache = os.path.join(DIR_CACHE, "gandalf_alta.npz")
    if os.path.exists(cache) and not RIFAI:
        d = np.load(cache)
        return d["v"], d["f"], {k[2:]: d[k] for k in d.files if k.startswith("a_")}, d["info"]
    t0 = time.time()
    o = carica_pkl()
    v5, f5 = o["5"]
    v5 = v5.astype(np.float64)
    lab = componenti(len(v5), f5)
    u, c = np.unique(lab, return_counts=True)
    ordine = u[np.argsort(-c)]
    # le due meta' del corpo (le isole piu' grandi che superano lo zero in Z) e la mano col bastone
    corpo_m = (lab == ordine[0]) | (lab == ordine[1])
    bast_m = lab == ordine[2]
    vc, fc = sotto_mesh(v5, f5, corpo_m)
    vb, fb = sotto_mesh(v5, f5, bast_m)
    vs, fs = o["3"][0].astype(np.float64), o["3"][1].astype(np.int32)
    log(f"   corpo {len(fc)} tri, mano+bastone {len(fb)} tri, mano+spada {len(fs)} tri")

    # --- zone delle mani nei loro sistemi originali ---------------------------------
    # 0 veste, 1 capelli/barba, 2 pelle, 3 corda, 4 legno, 5 cristallo, 6 acciaio, 7 oro, 8 cuoio
    zb = zone_mano_bastone(vb)
    zs = zone_mano_spada(vs)

    # --- montaggio ---------------------------------------------------------------------
    Rb, tb = infila(*PERNO_BASTONE, *FORO_SIN, **POSA_BASTONE)
    Rs, ts = infila(*PERNO_SPADA, *FORO_DES, **POSA_SPADA)
    vb = vb @ Rb.T + tb
    vs = vs @ Rs.T + ts
    cima_bastone = (vb[np.argmax((vb - tb) @ (Rb @ BASTONE_ASSE))])
    cristallo = Rb @ CRISTALLO_BASTONE + tb
    log(f"   testa del bastone (mm) {np.round(cima_bastone, 2)}, cristallo {np.round(cristallo, 2)}")

    zc = zone_corpo(vc)

    v = np.concatenate([vc, vb, vs])
    f = np.concatenate([fc, fb + len(vc), fs + len(vc) + len(vb)]).astype(np.int32)
    zona = np.concatenate([zc, zb, zs])
    log(f"   montato: {len(v)} vertici, {len(f)} triangoli ({time.time() - t0:.0f}s)")

    attr = colori_gandalf(v, f, zona, cristallo)

    # --- in metri, origine al centro dei piedi -----------------------------------------
    zmin = vc[:, 2].min()
    piedi = vc[vc[:, 2] < zmin + 1.0]
    centro = np.array([(piedi[:, 0].min() + piedi[:, 0].max()) / 2,
                       (piedi[:, 1].min() + piedi[:, 1].max()) / 2, zmin])
    scala = ALTEZZA_GANDALF / (vc[:, 2].max() - zmin)
    v = (v - centro) * scala
    punti = {"cima_bastone": (cima_bastone - centro) * scala,
             "cristallo": (cristallo - centro) * scala}
    info = np.array([scala, *punti["cima_bastone"], *punti["cristallo"]])
    np.savez(cache, v=v.astype(np.float32), f=f, info=info,
             **{"a_" + k: a.astype(np.float32) for k, a in attr.items()})
    log(f"   scala {scala:.5f} m/mm, cache salvata ({time.time() - t0:.0f}s)")
    return v.astype(np.float32), f, attr, info


def zone_mano_bastone(v):
    """Zone della mano col bastone (sistema originale del pezzo)."""
    zona = np.full(len(v), 4)                       # legno
    a = BASTONE_ASSE / np.linalg.norm(BASTONE_ASSE)
    c0 = np.array(PERNO_BASTONE[0])
    t = (v - c0) @ a
    # retta del bastone stimata dai baricentri delle fette lontane dalla mano
    centri, ts = [], []
    for t0 in list(np.arange(-12, -5, 0.5)) + list(np.arange(5, 12, 0.5)):
        s = (t >= t0) & (t < t0 + 0.5)
        if s.sum() > 20:
            centri.append(v[s].mean(0))
            ts.append(t0 + 0.25)
    centri = np.array(centri)
    ts = np.array(ts)
    A = np.stack([ts, np.ones_like(ts)], 1)
    coef = np.linalg.lstsq(A, centri, rcond=None)[0]       # centro(t) = coef[0]*t + coef[1]
    asse = coef[0] / np.linalg.norm(coef[0])
    d = v - coef[1]
    tt = d @ asse
    r = np.linalg.norm(d - np.outer(tt, asse), axis=1)
    lontano = (np.abs(t) > 5) & (np.abs(t) < 12)
    r_bast = np.percentile(r[lontano], 90)
    mano = (np.abs(t) < 5.5) & (r > r_bast * 1.15 + 0.12)
    zona[mano] = 2
    # polsino / perno (dentro la manica): colore della veste
    n = np.array(PERNO_BASTONE[1])
    n /= np.linalg.norm(n)
    tp = (v - c0) @ (-n)
    rp = np.linalg.norm((v - c0) - np.outer((v - c0) @ n, n), axis=1)
    zona[(tp > -0.3) & (tp < 3.4) & (rp < 2.2)] = 0
    # pietra nella testa del bastone
    zona[np.linalg.norm(v - CRISTALLO_BASTONE, axis=1) < 0.95] = 5
    log(f"   bastone: raggio {r_bast:.2f} mm, mano {mano.sum()} v, cristallo {(zona == 5).sum()} v")
    return zona


def zone_mano_spada(v):
    a = SPADA_ASSE / np.linalg.norm(SPADA_ASSE)
    d = v - SPADA_POMOLO
    t = d @ a
    r = np.linalg.norm(d - np.outer(t, a), axis=1)
    zona = np.full(len(v), 7)                       # oro: pomolo, impugnatura, elsa
    zona[t >= 10.4] = 6                             # lama
    impugnatura = (t >= 2.0) & (t < 8.2)
    zona[impugnatura & (r < 0.62)] = 8              # cuoio dell'impugnatura
    zona[impugnatura & (r >= 0.62)] = 2             # mano
    c0 = np.array(PERNO_SPADA[0])
    n = np.array(PERNO_SPADA[1])
    n /= np.linalg.norm(n)
    tp = (v - c0) @ (-n)
    rp = np.linalg.norm((v - c0) - np.outer((v - c0) @ n, n), axis=1)
    zona[(tp > -0.3) & (tp < 3.6) & (rp < 2.0)] = 0
    return zona


# poligoni in proiezione frontale (x, z) misurati sulle viste ortografiche
POLI_BARBA = [(-9.9, 22.7), (-4.3, 22.7), (-3.0, 20.5), (-2.6, 17.0), (-3.2, 13.5), (-5.0, 11.2),
              (-7.5, 10.4), (-10.0, 11.2), (-11.5, 13.5), (-12.0, 17.0), (-11.6, 20.5)]
POLI_CIOCCA_SIN = [(-14.8, 25.0), (-9.6, 25.5), (-9.9, 21.0), (-11.9, 17.0), (-12.3, 15.0), (-13.6, 16.6), (-14.8, 18.0)]
POLI_CIOCCA_DES = [(-4.6, 25.5), (-1.0, 24.0), (-0.6, 19.0), (-1.6, 15.8), (-3.0, 15.8), (-2.9, 20.5)]


def zone_corpo(v):
    x, y, z = v[:, 0], v[:, 1], v[:, 2]
    zona = np.zeros(len(v), np.int64)
    davanti = superficie_esposta(v, 1, 0, 2, 0.3, 1.6, verso=1)
    dietro = superficie_esposta(v, 1, 0, 2, 0.3, 1.6, verso=-1)
    # massa della testa (capelli) + ciocche + barba + capelli lunghi dietro
    testa = ((x + 7.2) / 6.6) ** 2 + ((y - 8.8) / 6.9) ** 2 + ((z - 23.0) / 4.7) ** 2 < 1
    barba = davanti & in_poligono(x, z, POLI_BARBA)
    ciocche = davanti & (in_poligono(x, z, POLI_CIOCCA_SIN) | in_poligono(x, z, POLI_CIOCCA_DES))
    nuca = dietro & (x > -14.5) & (x < -1.2) & (z > 15.8)
    capelli = testa | barba | ciocche | nuca
    zona[capelli] = 1
    # viso
    viso = davanti & (((x + 7.1) / 2.55) ** 2 + ((z - 24.15) / 2.05) ** 2 < 1)
    zona[viso] = 2
    # cintura di corda
    corda = davanti & (z > 1.9) & (z < 4.4) & (x > -15.5) & (x < 0.8)
    zona[corda & ~capelli] = 3
    return zona


def colori_gandalf(v, f, zona, cristallo):
    """Attributi per vertice: base (colore), emis (emissione), mr (0, rugosita', metallo)."""
    t0 = time.time()
    n = normali_vertici(v, f)
    vic = Vicinato(len(v), f)
    cav_f = cavita(v, f, n, vic, 4)          # pieghe fini (ciocche, trama)
    cav_m = cavita(v, f, n, vic, 30)         # pieghe medie (panneggio)
    log(f"   cavita' calcolata ({time.time() - t0:.0f}s)")
    k_f = np.clip(cav_f / 0.05, -1, 1)
    k_m = np.clip(cav_m / 0.35, -1, 1)
    ru = rumore3(v, 0.35, 1)
    base = np.zeros((len(v), 3))
    emis = np.zeros((len(v), 3))
    mr = np.zeros((len(v), 3))

    def tinta(m, chiaro, scuro, fattore):
        base[m] = srgb(chiaro) * (1 - fattore[m, None]) + srgb(scuro) * fattore[m, None]

    # veste: piu' scura nelle pieghe, leggere variazioni
    m = zona == 0
    fat = np.clip(0.55 * smooth(-0.2, 1.0, k_m) + 0.25 * smooth(0, 1, k_f) + 0.12 * ru, 0, 1)
    tinta(m, C_VESTE, C_VESTE_SCURA, fat)
    mr[m] = (0, 0.88, 0)
    # capelli e barba: ciocche evidenziate dalla cavita' fine
    m = zona == 1
    fat = np.clip(0.75 * smooth(-0.3, 1.0, k_f) + 0.25 * smooth(0, 1, k_m) + 0.1 * ru, 0, 1)
    tinta(m, C_CAPELLI, C_CAPELLI_SCURI, fat)
    mr[m] = (0, 0.7, 0)
    # pelle
    m = zona == 2
    fat = np.clip(0.6 * smooth(-0.2, 1, k_f) + 0.4 * smooth(0, 1, k_m), 0, 1)
    tinta(m, C_PELLE, (0.50, 0.33, 0.27), fat)
    mr[m] = (0, 0.6, 0)
    # corda
    m = zona == 3
    tinta(m, C_CORDA, (0.16, 0.15, 0.13), np.clip(smooth(-0.3, 1, k_f), 0, 1))
    mr[m] = (0, 0.9, 0)
    # legno del bastone (venature dal rumore + cavita')
    m = zona == 4
    ven = 0.5 + 0.5 * np.sin(v @ np.array([1.3, 0.2, 0.7]) * 3.0 + ru * 4)
    tinta(m, C_LEGNO, C_LEGNO_SCURO, np.clip(0.5 * smooth(-0.3, 1, k_f) + 0.25 * ven + 0.2 * smooth(0, 1, k_m), 0, 1))
    mr[m] = (0, 0.75, 0)
    # cristallo luminoso
    m = zona == 5
    base[m] = srgb(C_CRISTALLO)
    emis[m] = srgb((0.75, 0.88, 1.0))
    mr[m] = (0, 0.15, 0)
    # attenuazione dolce attorno al cristallo
    dc = np.linalg.norm(v - cristallo, axis=1)
    alone = (zona == 4) & (dc < 1.6)
    emis[alone] = srgb((0.75, 0.88, 1.0)) * (smooth(1.6, 0.9, dc[alone])[:, None] * 0.35)
    # acciaio, oro, cuoio
    m = zona == 6
    tinta(m, C_ACCIAIO, (0.45, 0.47, 0.5), np.clip(smooth(0, 1, k_f), 0, 1))
    mr[m] = (0, 0.28, 1.0)
    m = zona == 7
    tinta(m, C_ORO, (0.45, 0.30, 0.10), np.clip(smooth(-0.2, 1, k_f), 0, 1))
    mr[m] = (0, 0.35, 1.0)
    m = zona == 8
    base[m] = srgb(C_CUOIO)
    mr[m] = (0, 0.8, 0)
    log(f"   colori Gandalf ({time.time() - t0:.0f}s)")
    return {"base": base, "emis": emis, "mr": mr, "zona": np.stack([zona / 10.0] * 3, 1)}


# ---------------------------------------------------------------------------
#  IL BALROG: zone e colori (sistema originale in mm: guarda verso -X, Z in alto)
# ---------------------------------------------------------------------------
#  Riferimenti misurati sulle viste ortografiche del pezzo:
#   testa tra x -82 e -45, bocca aperta verso x -78 (Y 4..13, z 23..31), corna ai lati;
#   mano con la frusta a Y ~ +64, z ~ -9; l'altra mano a Y ~ -78; piedi a z ~ -80.

MANO_FRUSTA = np.array([-47.0, 64.5, -9.0])     # x raffinata nel calcolo
MANO_LIBERA = np.array([-40.0, -78.0, -10.0])

C_ROCCIA = (0.055, 0.045, 0.041)
C_ROCCIA_CHIARA = (0.15, 0.125, 0.11)
C_CORNO = (0.26, 0.20, 0.15)
C_ARTIGLIO = (0.13, 0.11, 0.095)
C_LAVA = (1.0, 0.30, 0.03)
C_LAVA_GIALLA = (1.0, 0.78, 0.30)


def balrog_alta():
    os.makedirs(DIR_CACHE, exist_ok=True)
    cache = os.path.join(DIR_CACHE, "balrog_alta.npz")
    if os.path.exists(cache) and not RIFAI:
        d = np.load(cache)
        return d["v"], d["f"], {k[2:]: d[k] for k in d.files if k.startswith("a_")}, d["info"]
    t0 = time.time()
    o = carica_pkl()
    v, f = o["1"]
    v = v.astype(np.float64)
    f = f.astype(np.int32)
    x, y, z = v[:, 0], v[:, 1], v[:, 2]
    n = normali_vertici(v, f)
    vic = Vicinato(len(v), f)
    k_f = np.clip(cavita(v, f, n, vic, 3) / 0.08, -1, 1)
    k_m = np.clip(cavita(v, f, n, vic, 25) / 0.6, -1, 1)
    bvh = bvh_da(v, f)
    sp = spessore(v, n, bvh, 12.0)
    sp = vic.liscia(sp, 4)
    log(f"   cavita' e spessore ({time.time() - t0:.0f}s)")

    # posizioni di riferimento raffinate sulla geometria
    vicino = np.linalg.norm(v[:, 1:] - MANO_FRUSTA[1:], axis=1) < 6
    mano_frusta = np.array([np.median(x[vicino]), MANO_FRUSTA[1], MANO_FRUSTA[2]])
    testa = (x < -45) & (z > 14)
    cima_testa = z[x < -70].max()      # arcata, cranio e corna (la criniera parte piu indietro)
    log(f"   mano frusta {np.round(mano_frusta, 1)}, sommita' testa z={cima_testa:.1f}")

    # zone: 0 pelle, 1 criniera/fiamme, 2 frusta, 3 corna, 4 artigli
    zona = np.zeros(len(v), np.int64)
    sottile = sp < 2.6
    d_mani = np.minimum(np.linalg.norm(v - mano_frusta, axis=1), np.linalg.norm(v - MANO_LIBERA, axis=1))
    fiamme = sottile & ~testa & (z > -58) & (d_mani > 11)
    # cresta dorsale: lamina piu' spessa lungo la schiena, sopra il corpo
    # (sopra la linea della schiena vista di fianco, vicino al piano della spina dorsale)
    linea = np.interp(x, [-64, -45, -30, -15, 0, 10, 15], [53, 46, 40, 30, 16, 2, -12])
    y_spina = np.interp(x, [-65, -55, -45, -35, -25, -15, -5, 5], [4, 1, -1, -3, -7, -10, -13, -15.5])
    cresta = (z > linea) & (np.abs(y - y_spina) < 10.0) & (x > -64) & (d_mani > 11)
    fiamme |= cresta
    zona[fiamme] = 1
    frusta = ((y > 68) | ((y > 46) & (z < -15))) & (z < 8)
    zona[frusta] = 2
    d_testa = np.linalg.norm(v - np.array([-66.0, 9.0, 34.0]), axis=1)
    corna = (x < -52) & (np.abs(y - 9.0) > 7.0) & (d_testa < 24) & (z > 14) & (z < 52)
    zona[corna] = 3
    artigli = sottile & ((z < -70) | (d_mani < 11)) & ~frusta
    zona[artigli] = 4

    # occhi: le due cavita' piu' profonde sotto le arcate sopraccigliari
    cand = testa & (z > 31) & (z < 39) & (y > 0) & (y < 19) & (x < -62) & (zona == 0)
    occhi = []
    sc_ = np.where(cand, cavita(v, f, n, vic, 10), -1e9)
    for lato in ((y < 9), (y >= 9)):
        i = np.argmax(np.where(lato, sc_, -1e9))
        occhi.append(v[i].copy())
    log(f"   occhi (mm) {np.round(occhi[0], 1)} {np.round(occhi[1], 1)}")
    bocca = (x < -60) & (y > 2.5) & (y < 14.5) & (z > 21.5) & (z < 31.5)

    ru = rumore3(v, 0.12, 3)
    ru2 = rumore3(v, 0.3, 7)
    base = np.zeros((len(v), 3))
    emis = np.zeros((len(v), 3))
    mr = np.zeros((len(v), 3))

    # pelle di roccia carbonizzata: rilievi un po' piu' chiari, crepe di lava
    m = zona == 0
    chiaro = np.clip(smooth(0.0, -0.8, k_m) * 0.6 + 0.25 * (ru2 * 0.5 + 0.5), 0, 1)
    base[m] = srgb(C_ROCCIA) * (1 - chiaro[m, None]) + srgb(C_ROCCIA_CHIARA) * chiaro[m, None]
    vene = smooth(0.16, 0.02, np.abs(ru)) * smooth(-0.1, 0.5, k_m)          # vene lungo i solchi
    crepe = smooth(0.25, 0.9, k_f) * smooth(-0.2, 0.4, k_m)                  # crepe fini
    lava = np.clip(np.maximum(vene * 0.9, crepe), 0, 1)
    caldo = np.clip(smooth(0.2, 1.0, k_m), 0, 1)                             # piu' giallo nel profondo
    col_lava = srgb(C_LAVA) * (1 - caldo[:, None]) + srgb(C_LAVA_GIALLA) * caldo[:, None]
    emis[m] = col_lava[m] * lava[m, None]
    base[m] = base[m] * (1 - lava[m, None]) + srgb((0.55, 0.18, 0.04)) * lava[m, None]
    mr[m] = (0, 0.82, 0)
    # fiamme della criniera e degli avambracci: arancio alla base, giallo sulle punte sottili
    for zz, intensita in ((1, 0.7), (2, 0.65)):
        m = zona == zz
        punta = np.clip(np.maximum(smooth(2.6, 0.5, sp), smooth(4, 30, z - linea) * cresta * 0.6), 0, 1)
        col = srgb(C_LAVA) * (1 - punta[:, None]) + srgb(C_LAVA_GIALLA) * punta[:, None]
        anima = np.clip(0.55 + 0.45 * punta - 0.25 * smooth(0, 1, k_f), 0, 1)
        emis[m] = col[m] * (anima[m, None] * intensita)
        base[m] = srgb((0.30, 0.07, 0.02)) * (1 - punta[m, None]) + srgb((0.70, 0.36, 0.08)) * punta[m, None]
        mr[m] = (0, 0.7, 0)
    # il nucleo della frusta (spesso) resta piu' scuro e brace
    m = (zona == 2) & (sp > 2.6)
    emis[m] *= 0.45
    # corna e artigli
    m = zona == 3
    fat = np.clip(0.6 * smooth(-0.2, 1, k_f) + 0.3 * (ru2 * 0.5 + 0.5), 0, 1)
    base[m] = srgb(C_CORNO) * (1 - fat[m, None]) + srgb((0.08, 0.06, 0.05)) * fat[m, None]
    mr[m] = (0, 0.5, 0)
    m = zona == 4
    base[m] = srgb(C_ARTIGLIO)
    mr[m] = (0, 0.45, 0)
    # bocca e occhi incandescenti
    m = bocca & (k_m > -0.1) & (zona == 0)
    forza = np.clip(smooth(-0.1, 0.5, k_m), 0, 1)
    emis[m] = np.maximum(emis[m], srgb(C_LAVA_GIALLA) * forza[m, None])
    base[m] = np.maximum(base[m], srgb((0.6, 0.25, 0.05)) * forza[m, None])
    for c in occhi:
        d = np.linalg.norm(v - c, axis=1)
        m = d < 2.4
        w = smooth(2.4, 1.0, d[m])[:, None]
        emis[m] = np.maximum(emis[m], srgb((1.0, 0.85, 0.4)) * w)
        base[m] = np.maximum(base[m], srgb((0.9, 0.6, 0.2)) * w)

    # orientamento di gioco: ruota di +90 gradi attorno a Z (da -X verso -Y)
    R = rot_asse(np.array([0, 0, 1.0]), math.pi / 2)
    v = v @ R.T
    occhi = [R @ c for c in occhi]
    mano_frusta = R @ mano_frusta
    zmin = v[:, 2].min()
    piedi = v[v[:, 2] < zmin + 4]
    centro = np.array([(piedi[:, 0].min() + piedi[:, 0].max()) / 2,
                       (piedi[:, 1].min() + piedi[:, 1].max()) / 2, zmin])
    scala = ALTEZZA_BALROG / (cima_testa - zmin)
    v = (v - centro) * scala
    info = np.concatenate([[scala], (mano_frusta - centro) * scala,
                           (occhi[0] - centro) * scala, (occhi[1] - centro) * scala])
    attr = {"base": base, "emis": emis, "mr": mr, "zona": np.stack([zona / 10.0] * 3, 1)}
    np.savez(cache, v=v.astype(np.float32), f=f, info=info,
             **{"a_" + k: a.astype(np.float32) for k, a in attr.items()})
    log(f"   scala {scala:.5f} m/mm ({time.time() - t0:.0f}s)")
    return v.astype(np.float32), f, attr, info


# ---------------------------------------------------------------------------
#  Blender: scena, mesh, materiali
# ---------------------------------------------------------------------------

def azzera_scena():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.unit_settings.system = "METRIC"
    return sc


def collega(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def mesh_numpy(nome, v, f, attributi=None):
    me = bpy.data.meshes.new(nome)
    me.vertices.add(len(v))
    me.vertices.foreach_set("co", np.asarray(v, np.float32).ravel())
    me.loops.add(len(f) * 3)
    me.loops.foreach_set("vertex_index", np.asarray(f, np.int32).ravel())
    me.polygons.add(len(f))
    me.polygons.foreach_set("loop_start", np.arange(0, len(f) * 3, 3, dtype=np.int32))
    me.update()
    me.validate()
    for nome_a, val in (attributi or {}).items():
        a = me.attributes.new(nome_a, "FLOAT_COLOR", "POINT")
        rgba = np.ones((len(v), 4), np.float32)
        rgba[:, :3] = val
        a.data.foreach_set("color", rgba.ravel())
    me.polygons.foreach_set("use_smooth", np.ones(len(f), bool))
    return collega(bpy.data.objects.new(nome, me))


def mat_attributo(nome, attributo, emissione=False):
    """Materiale che mostra un attributo colore (per anteprime di controllo e per le cotture)."""
    mat = bpy.data.materials.new(nome)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    at = nt.nodes.new("ShaderNodeAttribute")
    at.attribute_name = attributo
    if emissione:
        sh = nt.nodes.new("ShaderNodeEmission")
        sh.inputs["Strength"].default_value = 1.0
        nt.links.new(at.outputs["Color"], sh.inputs["Color"])
    else:
        sh = nt.nodes.new("ShaderNodeBsdfPrincipled")
        nt.links.new(at.outputs["Color"], sh.inputs["Base Color"])
        sh.inputs["Roughness"].default_value = 0.8
    nt.links.new(sh.outputs[0], out.inputs["Surface"])
    return mat


def guarda_verso(ob, bersaglio):
    d = Vector(bersaglio) - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def scatta(percorso, cam_pos, bersaglio, lente=50, dim=(900, 900), campioni=32, luci=None,
           sfondo=(0.025, 0.022, 0.025), orto=None):
    """Render Cycles con camera e luci temporanee."""
    sc = bpy.context.scene
    cam = collega(bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera")))
    cam.data.lens = lente
    cam.data.clip_end = 500
    if orto:
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = orto
    cam.location = cam_pos
    guarda_verso(cam, bersaglio)
    sc.camera = cam
    if luci is None:
        luci = [("AREA", (3.0, -4.0, 4.0), 900.0, (1.0, 0.78, 0.55), 2.5),     # luce calda principale
                ("AREA", (-4.0, -1.0, 2.5), 250.0, (0.55, 0.65, 1.0), 3.0),    # riempimento freddo
                ("AREA", (-1.0, 5.0, 4.0), 500.0, (1.0, 0.6, 0.35), 2.0)]      # controluce
    oggetti = [cam]
    for i, (tipo, pos, energia, col, dimensione) in enumerate(luci):
        ld = bpy.data.lights.new(f"luce{i}", tipo)
        ld.energy = energia
        ld.color = col
        if tipo == "AREA":
            ld.size = dimensione
        lo = collega(bpy.data.objects.new(f"luce{i}", ld))
        lo.location = pos
        guarda_verso(lo, bersaglio)
        oggetti.append(lo)
    mondo = bpy.data.worlds.new("Mondo")
    mondo.use_nodes = True
    mondo.node_tree.nodes["Background"].inputs[0].default_value = (*sfondo, 1)
    sc.world = mondo
    sc.render.resolution_x, sc.render.resolution_y = dim
    sc.render.resolution_percentage = 100
    sc.cycles.samples = campioni
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 4
    sc.view_settings.view_transform = "AgX"
    sc.render.image_settings.file_format = "PNG"
    sc.render.filepath = percorso
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    log(f"   render {percorso} ({time.time() - t0:.0f}s)")
    for o in oggetti:
        bpy.data.objects.remove(o)


def affianca(percorsi, uscita):
    """Affianca orizzontalmente piu' PNG della stessa altezza (senza PIL)."""
    imgs = [bpy.data.images.load(p) for p in percorsi]
    h = imgs[0].size[1]
    W = sum(i.size[0] for i in imgs)
    tot = np.zeros((h, W, 4), np.float32)
    x = 0
    for im in imgs:
        w = im.size[0]
        px = np.empty(w * h * 4, np.float32)
        im.pixels.foreach_get(px)
        tot[:, x:x + w] = px.reshape(h, w, 4)
        x += w
    out = bpy.data.images.new("affiancate", W, h, alpha=False)
    out.pixels.foreach_set(tot.ravel())
    out.filepath_raw = uscita
    out.file_format = "PNG"
    out.save()
    for im in imgs:
        bpy.data.images.remove(im)
    bpy.data.images.remove(out)


def controlla_zone(nome, v, f, attr, viste):
    """Anteprima dell'alta risoluzione con i colori per vertice (controllo delle zone)."""
    azzera_scena()
    ob = mesh_numpy(nome, v, f, {"base": attr["base"], "emis": attr["emis"]})
    ob.data.materials.append(mat_attributo("vc", "base"))
    file = []
    for i, (pos, bers, orto) in enumerate(viste):
        p = f"/tmp/zone_{nome}_{i}.png"
        scatta(p, pos, bers, dim=(600, 600), campioni=12, orto=orto, sfondo=(0.2, 0.2, 0.22),
               luci=[("SUN", (2, -5, 6), 4.0, (1, 1, 1), 0), ("SUN", (-5, 2, 2), 1.5, (1, 1, 1), 0)])
        file.append(p)
    affianca(file, f"/tmp/zone_{nome}.png")


# ---------------------------------------------------------------------------
#  Bassa risoluzione, UV, cottura delle texture
# ---------------------------------------------------------------------------

def seleziona(attivo, altri=()):
    bpy.context.view_layer.update()
    for o in bpy.context.scene.objects:
        o.select_set(False)
    for o in altri:
        o.select_set(True)
    attivo.select_set(True)
    bpy.context.view_layer.objects.active = attivo


def decima(ob, triangoli):
    t0 = time.time()
    n0 = len(ob.data.polygons)
    seleziona(ob)
    m = ob.modifiers.new("decima", "DECIMATE")
    m.decimate_type = "COLLAPSE"
    m.ratio = triangoli / n0
    m.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=m.name)
    log(f"   decimazione {n0} -> {len(ob.data.polygons)} triangoli ({time.time() - t0:.0f}s)")


def uv_automatiche(ob, margine=0.0025):
    t0 = time.time()
    seleziona(ob)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=margine, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.pack_islands(rotate=True, margin=margine)
    bpy.ops.object.mode_set(mode="OBJECT")
    log(f"   UV automatiche ({time.time() - t0:.0f}s)")


def immagine_np(img):
    px = np.empty(img.size[0] * img.size[1] * 4, np.float32)
    img.pixels.foreach_get(px)
    return px.reshape(img.size[1], img.size[0], 4)


def cuoci(basso, alto, tipo, dim, nome, attributo=None, estrusione=0.01, distanza=0.04, campioni=1):
    """Cottura Cycles dall'alta (alto) alla bassa risoluzione (basso) in una nuova immagine."""
    sc = bpy.context.scene
    img = bpy.data.images.new(nome, dim, dim, alpha=False, float_buffer=(tipo != "NORMAL"))
    if tipo != "EMIT":
        img.colorspace_settings.name = "Non-Color"
    # materiale dell'alta: emissione dell'attributo (per EMIT), altrimenti neutro
    alto.data.materials.clear()
    alto.data.materials.append(mat_attributo("cott_" + nome, attributo or "base", emissione=True))
    mat = bpy.data.materials.new("bersaglio_" + nome)
    mat.use_nodes = True
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = img
    mat.node_tree.nodes.active = tex
    basso.data.materials.clear()
    basso.data.materials.append(mat)
    seleziona(basso, [alto])
    sc.cycles.samples = campioni
    b = sc.render.bake
    b.use_selected_to_active = True
    b.cage_extrusion = estrusione
    b.max_ray_distance = distanza
    b.margin = 8
    b.margin_type = "EXTEND"
    b.use_clear = True
    b.normal_space = "TANGENT"
    t0 = time.time()
    bpy.ops.object.bake(type=tipo)
    log(f"   cottura {nome} ({tipo}, {dim}px) {time.time() - t0:.0f}s")
    basso.data.materials.clear()
    return img


def immagine_da_np(nome, arr, colore=True):
    h, w = arr.shape[:2]
    img = bpy.data.images.new(nome, w, h, alpha=False)
    if not colore:        # prima di scrivere i pixel: cambiare spazio colore rigenera l'immagine
        img.colorspace_settings.name = "Non-Color"
    rgba = np.ones((h, w, 4), np.float32)
    rgba[..., :3] = arr[..., :3]
    img.pixels.foreach_set(np.clip(rgba, 0, 1).ravel())
    img.pack()
    return img


def materiale_finale(nome, img_base, img_norm, img_mr, img_emis=None, forza_emis=1.0, forza_norm=1.0):
    """Principled compatibile glTF: colore, normale, rugosita'/metallo (G/B), emissione."""
    mat = bpy.data.materials.new(nome)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = img_base
    nt.links.new(t.outputs["Color"], bsdf.inputs["Base Color"])
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = img_norm
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.inputs["Strength"].default_value = forza_norm
    nt.links.new(t.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs[0], bsdf.inputs["Normal"])
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = img_mr
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(t.outputs["Color"], sep.inputs[0])
    nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
    if img_emis is not None:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = img_emis
        nt.links.new(t.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = forza_emis
    return mat


def costruisci(nome, v, f, attr, triangoli, dim=2048, dim_piccola=1024, estrusione=0.01,
               distanza=0.04, ao_distanza=0.12, ao_min=0.35, forza_emis=4.0, scurisci=None):
    """Alta -> bassa risoluzione con texture cotte; restituisce l'oggetto finale."""
    azzera_scena()
    alto = mesh_numpy(nome + "_alta", v, f, {k: attr[k] for k in ("base", "emis", "mr")})
    basso = mesh_numpy(nome, v, f)
    decima(basso, triangoli)
    uv_automatiche(basso)
    sc = bpy.context.scene
    sc.world = bpy.data.worlds.new("Mondo")
    sc.world.light_settings.distance = ao_distanza
    i_norm = cuoci(basso, alto, "NORMAL", dim, nome + "_normale", estrusione=estrusione, distanza=distanza)
    i_base = cuoci(basso, alto, "EMIT", dim, nome + "_base", "base", estrusione, distanza)
    i_ao = cuoci(basso, alto, "AO", dim_piccola, nome + "_ao", estrusione=estrusione, distanza=distanza, campioni=24)
    i_emis = cuoci(basso, alto, "EMIT", dim, nome + "_emis_c", "emis", estrusione, distanza)
    i_mr = cuoci(basso, alto, "EMIT", dim_piccola, nome + "_mr_c", "mr", estrusione, distanza)
    # composizione: occlusione moltiplicata nel colore (lineare)
    base = immagine_np(i_base)[..., :3]
    ao = immagine_np(i_ao)[..., 0]
    ao = np.kron(ao, np.ones((dim // dim_piccola, dim // dim_piccola)))[..., None]
    col = base * (ao_min + (1 - ao_min) * ao)
    if scurisci is not None:
        col = scurisci(col, ao)
    emis = immagine_np(i_emis)[..., :3]
    mr = immagine_np(i_mr)[..., :3]
    # le immagini finali (8 bit, sRGB per colore ed emissione)
    def a_srgb(x):
        x = np.clip(x, 0, 1)
        return np.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055)
    # immagini a 8 bit: i pixel si scrivono gia' codificati sRGB (colore, emissione)
    img_c = immagine_da_np(nome + "_colore", a_srgb(col))
    i_norm.pack()
    img_mr = immagine_da_np(nome + "_rugmet", mr, colore=False)
    img_e = None
    if emis.max() > 0.01:
        picco = float(emis.max())
        img_e = immagine_da_np(nome + "_emissione", a_srgb(emis / picco))
        forza_emis *= picco
    for im in (img_c, i_norm, img_mr, i_ao):          # copie di controllo
        im.save(filepath=f"/tmp/tex_{im.name}.png") if im is i_ao else im.save_render(f"/tmp/tex_{im.name}.png")
    for im in (i_base, i_ao, i_emis, i_mr):
        bpy.data.images.remove(im)
    basso.data.materials.append(materiale_finale(nome, img_c, i_norm, img_mr, img_e, forza_emis))
    bpy.data.objects.remove(alto)
    return basso


def esporta(percorso, ob):
    seleziona(ob)
    bpy.ops.export_scene.gltf(
        filepath=percorso, export_format="GLB", use_selection=True,
        export_apply=True, export_yup=True, export_texcoords=True, export_normals=True,
        export_tangents=False, export_materials="EXPORT", export_image_format="JPEG",
        export_jpeg_quality=85, export_cameras=False, export_lights=False,
        export_animations=False, export_skins=False, export_morph=False)
    log(f"   esportato {percorso}: {os.path.getsize(percorso) / 1048576:.2f} MB")


def salva_blend(percorso, ob):
    """Salva il .blend con la sola mesh pulita (texture impacchettate) per il rigging futuro."""
    for o in list(bpy.context.scene.objects):
        if o is not ob:
            bpy.data.objects.remove(o)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=percorso, compress=True)
    log(f"   salvato {percorso}")


# ---------------------------------------------------------------------------
#  Anteprime, verifica, programma principale
# ---------------------------------------------------------------------------

def anteprima_finale(ob, percorso, altezza, punti_luce=()):
    """Due inquadrature (3/4 frontale e laterale) affiancate, sfondo scuro, luce calda."""
    if not RENDER:
        return
    sc = bpy.context.scene
    extra = []
    for p, col, en in punti_luce:            # luci puntiformi (es. il cristallo del bastone)
        ld = bpy.data.lights.new("pl", "POINT")
        ld.energy = en
        ld.color = col
        ld.shadow_soft_size = 0.05 * altezza
        lo = collega(bpy.data.objects.new("pl", ld))
        lo.location = p
        extra.append(lo)
    h = altezza
    bers = (0, 0, 0.66 * h)
    k = h / 1.9
    luci = [("AREA", (3.0 * k, -4.0 * k, 3.5 * k), 900.0 * k * k, (1.0, 0.75, 0.5), 2.5 * k),
            ("AREA", (-4.0 * k, -2.0 * k, 2.0 * k), 220.0 * k * k, (0.5, 0.6, 1.0), 3.0 * k),
            ("AREA", (-1.0 * k, 5.0 * k, 4.0 * k), 500.0 * k * k, (1.0, 0.55, 0.3), 2.0 * k)]
    d = 4.9 * k
    scatta("/tmp/fin_a.png", (0.62 * d, -0.78 * d, 0.62 * h), bers, lente=50, luci=luci)
    scatta("/tmp/fin_b.png", (d, 0.0, 0.55 * h), bers, lente=50, luci=luci)
    affianca(["/tmp/fin_a.png", "/tmp/fin_b.png"], percorso)
    for o in extra:
        bpy.data.objects.remove(o)
    log(f"   anteprima {percorso}")


def godot(p):
    """Blender (x, y, z) -> Godot/glTF (x, z, -y)."""
    return np.array([p[0], p[2], -p[1]])


def gandalf():
    log("== Gandalf ==")
    v, f, attr, info = gandalf_alta()
    ob = costruisci("gandalf", v, f, attr, triangoli=56000, estrusione=0.012, distanza=0.04,
                    ao_distanza=0.12, ao_min=0.4, forza_emis=6.0)
    cristallo = info[4:7]
    anteprima_finale(ob, os.path.join(DIR_ANTEPRIME, "anteprima3mf_gandalf.png"), ALTEZZA_GANDALF,
                     [(tuple(cristallo + np.array([0, -0.06, 0.06])), (0.75, 0.85, 1.0), 25.0)])
    esporta(os.path.join(DIR_ASSET, "gandalf.glb"), ob)
    log(f"   cima del bastone (Godot) {np.round(godot(info[1:4]), 3)}, cristallo (Godot) {np.round(godot(cristallo), 3)}")
    salva_blend(os.path.join(DIR_SRC, "gandalf_pulito.blend"), ob)


def balrog():
    log("== Balrog ==")
    v, f, attr, info = balrog_alta()
    ob = costruisci("balrog", v, f, attr, triangoli=68000, estrusione=0.02, distanza=0.07,
                    ao_distanza=0.25, ao_min=0.3, forza_emis=2.2)
    anteprima_finale(ob, os.path.join(DIR_ANTEPRIME, "anteprima3mf_balrog.png"), ALTEZZA_BALROG,
                     [((0.0, 0.6, 2.2), (1.0, 0.45, 0.12), 120.0)])
    esporta(os.path.join(DIR_ASSET, "balrog.glb"), ob)
    log(f"   mano della frusta (Godot) {np.round(godot(info[1:4]), 3)}")
    log(f"   occhi (Godot) {np.round(godot(info[4:7]), 3)} {np.round(godot(info[7:10]), 3)}")
    salva_blend(os.path.join(DIR_SRC, "balrog_pulito.blend"), ob)


def verifica():
    """Reimporta ogni .glb in una scena vuota: bbox (assi Godot), triangoli, materiali, immagini."""
    log("== Verifica ==")
    for nome in ("gandalf", "balrog"):
        p = os.path.join(DIR_ASSET, nome + ".glb")
        azzera_scena()
        bpy.ops.import_scene.gltf(filepath=p)
        mesh = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        tri = 0
        pts = []
        for o in mesh:
            o.data.calc_loop_triangles()
            tri += len(o.data.loop_triangles)
            co = np.empty(len(o.data.vertices) * 3, np.float32)
            o.data.vertices.foreach_get("co", co)
            co = co.reshape(-1, 3) @ np.array(o.matrix_world)[:3, :3].T + np.array(o.matrix_world)[:3, 3]
            pts.append(co)
        pts = np.concatenate(pts)
        g = np.stack([pts[:, 0], pts[:, 2], -pts[:, 1]], 1)
        log(f"   {nome}.glb {os.path.getsize(p) / 1048576:.2f} MB, {len(mesh)} mesh, {tri} triangoli")
        log(f"     bbox Godot min {np.round(g.min(0), 3)} max {np.round(g.max(0), 3)}")
        for m in bpy.data.materials:
            if m.users and m.use_nodes:
                b = m.node_tree.nodes.get("Principled BSDF")
                log(f"     materiale {m.name}: emissione forza {b.inputs['Emission Strength'].default_value:.2f}" if b else f"     materiale {m.name}")
        for im in bpy.data.images:
            if im.users:
                log(f"     immagine {im.name} {im.size[0]}x{im.size[1]}")


if __name__ == "__main__":
    scelta = [a for a in sys.argv[1:] if not a.startswith("--")]
    scelta = scelta[0] if scelta else "tutti"
    if scelta in ("gandalf", "tutti"):
        gandalf()
    if scelta in ("balrog", "tutti"):
        balrog()
    if scelta in ("verifica", "tutti"):
        verifica()
