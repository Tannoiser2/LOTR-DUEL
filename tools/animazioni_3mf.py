# -*- coding: utf-8 -*-
"""
Scheletri, pesi e animazioni per i modelli di gioco ricavati dal diorama 3MF.

Parte dai .blend "puliti" prodotti da tools/modelli_3mf.py:
    /home/claude/src/3mf/gandalf_pulito.blend, balrog_pulito.blend
e riesporta assets/3d/gandalf.glb e balrog.glb con armatura, skin e animazioni.

Uso (dalla radice del progetto):
    /home/claude/bvenv/bin/python tools/animazioni_3mf.py [gandalf|balrog|tutti] [--no-render] [--ossa]
        --ossa       solo la tavola di controllo delle ossa sovrapposte alle viste
        --no-render  salta le griglie di fotogrammi

Convenzioni (le stesse di modelli_3mf.py): metri, Z in alto in Blender, i personaggi
guardano verso -Y (= +Z in Godot), origine al centro dei piedi.  Il lato +X e' la
SINISTRA del personaggio (suffisso _sx), -X la destra (_dx).

Animazioni (azioni separate, 30 fps, nomi usati dal gioco):
    riposo (ciclo), attacco, colpito, sali, vittoria, caduta
La posa scolpita e' la posa di riposo dello scheletro: le animazioni sono scostamenti.
Le rotazioni si scrivono negli assi del MONDO (X avanti/indietro: +X piega in avanti
verso -Y; Y laterale; Z torsione) e si convertono nello spazio locale dell'osso.
Niente traslazioni della radice, salvo piccoli su/giu' (asse Z).

Pesi: invece del "calore" di Blender si usano pesi per prossimita' alle ossa con
maschere per regione, poi lisciati sulla mesh.  Motivo: il corpo di Gandalf e' fatto
di due meta' accostate (e le mani sono pezzi separati con perni dentro le maniche):
il calore risolve ogni isola per conto suo e da' pesi diversi ai due lati della
giunzione, che si aprirebbe in movimento; i pesi in funzione della posizione sono
invece identici sui due bordi.  Per il Balrog (un'unica isola) si prova il calore e si
ripiega sulla prossimita' dove fallisce o dove servono regole (frusta, mascella).
"""

import bpy
import math
import os
import pickle
import sys
import time

import numpy as np
from mathutils import Matrix, Quaternion, Vector
from mathutils.kdtree import KDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import modelli_3mf as M  # noqa: E402

FPS = 30
DIR_SRC = M.DIR_SRC
RENDER = "--no-render" not in sys.argv
SOLO_OSSA = "--ossa" in sys.argv
log = M.log


# ---------------------------------------------------------------------------
#  Utilita'
# ---------------------------------------------------------------------------

def catmull(chiavi, t):
    """Interpola una lista [(tempo, valore numpy)] con Catmull-Rom (tangenti morbide)."""
    ts = [k[0] for k in chiavi]
    if t <= ts[0]:
        return np.asarray(chiavi[0][1], float)
    if t >= ts[-1]:
        return np.asarray(chiavi[-1][1], float)
    i = max(j for j in range(len(ts) - 1) if ts[j] <= t)
    p1, p2 = np.asarray(chiavi[i][1], float), np.asarray(chiavi[i + 1][1], float)
    p0 = np.asarray(chiavi[i - 1][1], float) if i > 0 else p1
    p3 = np.asarray(chiavi[i + 2][1], float) if i + 2 < len(chiavi) else p2
    t1, t2 = ts[i], ts[i + 1]
    t0 = ts[i - 1] if i > 0 else t1 - (t2 - t1)
    t3 = ts[i + 2] if i + 2 < len(chiavi) else t2 + (t2 - t1)
    u = (t - t1) / (t2 - t1)
    m1 = (p2 - p0) / (t2 - t0) * (t2 - t1)
    m2 = (p3 - p1) / (t3 - t1) * (t2 - t1)
    u2, u3 = u * u, u * u * u
    return (2 * u3 - 3 * u2 + 1) * p1 + (u3 - 2 * u2 + u) * m1 + (-2 * u3 + 3 * u2) * p2 + (u3 - u2) * m2


def dist_segmenti(P, h, t):
    """Distanza di ogni punto P dal segmento h-t."""
    d = t - h
    L2 = max(d @ d, 1e-12)
    u = np.clip(((P - h) @ d) / L2, 0, 1)
    return np.linalg.norm(P - (h + np.outer(u, d)), axis=1)


def geodetica(v, f, sorgenti, maschera, iterazioni=4000):
    """Distanza lungo la superficie (rilassamento sui lati) ristretta ai vertici della maschera."""
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    e = e[maschera[e[:, 0]] & maschera[e[:, 1]]]
    a = np.concatenate([e[:, 0], e[:, 1]])
    b = np.concatenate([e[:, 1], e[:, 0]])
    L = np.linalg.norm(v[a] - v[b], axis=1)
    d = np.full(len(v), np.inf)
    d[sorgenti] = 0
    for _ in range(iterazioni):
        nuovo = d.copy()
        np.minimum.at(nuovo, a, d[b] + L)
        if np.allclose(nuovo, d, equal_nan=True) or np.array_equal(nuovo, d):
            break
        d = nuovo
    return d


def catena_lungo(P, dist, n, testa=None):
    """n+1 giunti lungo una struttura allungata: baricentri di n+1 fasce di distanza."""
    ok = np.isfinite(dist)
    P, dist = P[ok], dist[ok]
    q = np.linspace(0, np.percentile(dist, 99.5), n + 1)
    giunti = []
    for x in q:
        s = np.abs(dist - x) < (q[1] - q[0]) * 0.35
        giunti.append(P[s].mean(0))
    if testa is not None:
        giunti[0] = np.asarray(testa, float)
    return [np.asarray(g) for g in giunti]


# ---------------------------------------------------------------------------
#  Misure: GANDALF (metri, dalla cache ad alta risoluzione di modelli_3mf)
# ---------------------------------------------------------------------------

def gandalf_mm_a_m():
    """Trasformazione mm del file di stampa -> metri del modello (ricostruita dalla cache)."""
    d = np.load(os.path.join(M.DIR_CACHE, "gandalf_alta.npz"))
    scala = float(d["info"][0])
    cima_m = d["info"][1:4]
    cima_mm = np.array([-0.13, 7.51, 47.54])       # stampata da modelli_3mf (testa del bastone)
    centro = cima_mm - cima_m / scala
    return lambda p: (np.asarray(p, float) - centro) * scala, d


def ossa_gandalf():
    mm, d = gandalf_mm_a_m()
    v = d["v"].astype(np.float64)
    zona = np.round(d["a_zona"][:, 0] * 10).astype(int)
    # corpo: escluse le mani (perni compresi) -> zone legno/acciaio/oro/cuoio/cristallo e le mani
    # stanno sui pezzi separati; per le misure del tronco basta una fascia centrale in X.
    xc = mm([-7.0, 0, 0])[0]
    tronco = (np.abs(v[:, 0] - xc) < 0.13) & (zona != 4) & (zona < 5)

    def centro_fetta(z, larghezza=0.04):
        s = tronco & (np.abs(v[:, 2] - z) < larghezza)
        c = v[s].mean(0)
        return np.array([xc, c[1], z])

    bac = centro_fetta(0.95)
    spi = centro_fetta(1.12)
    pet = centro_fetta(1.33)
    col = centro_fetta(1.55)
    # la testa: indietro rispetto al baricentro della fetta (che include la barba davanti)
    tes = mm([-7.2, 9.6, 21.5])
    cima = np.array([tes[0], tes[1] + 0.01, 1.92])
    # braccia (misure sulle sezioni delle maniche, in mm)
    sp_sx, gom_sx = mm([-1.0, 9.5, 17.5]), mm([3.8, 6.5, 17.2])
    pol_sx = mm([7.97, 3.45, 20.18])
    sp_dx, gom_dx = mm([-13.2, 10.5, 16.0]), mm([-17.6, 11.5, 12.2])
    pol_dx = mm([-19.38, 10.31, 8.37])
    asse_sx = np.array([0.658, -0.607, 0.446])
    asse_dx = np.array([-0.732, -0.571, -0.371])
    # orlo della veste: baricentri di tre settori dell'anello basso
    orlo = tronco | ((v[:, 2] < 0.35) & (zona == 0))
    basso = v[orlo & (v[:, 2] < 0.12)]
    oc = basso.mean(0)
    settori = {"gonna_sx": (basso[:, 0] > oc[0]) & (basso[:, 1] < oc[1] + 0.05),
               "gonna_dx": (basso[:, 0] <= oc[0]) & (basso[:, 1] < oc[1] + 0.05),
               "gonna_dietro": basso[:, 1] >= oc[1] + 0.05}
    O = {}

    def osso(n, h, t, p=None, deform=True):
        O[n] = (np.asarray(h, float), np.asarray(t, float), p, deform)

    osso("radice", (0, 0, 0), (0, 0, 0.25), None, False)
    osso("bacino", bac, spi, "radice")
    osso("spina", spi, pet, "bacino")
    osso("petto", pet, col, "spina")
    osso("collo", col, tes, "petto")
    osso("testa", tes, cima, "collo")
    for n, s in settori.items():
        fine = basso[s].mean(0)
        inizio = bac + (fine - bac) * 0.12
        osso(n, inizio, fine, "bacino")
    osso("spalla_sx", col + (sp_sx - col) * 0.25 - np.array([0, 0, 0.05]), sp_sx, "petto")
    osso("braccio_sx", sp_sx, gom_sx, "spalla_sx")
    osso("avambraccio_sx", gom_sx, pol_sx, "braccio_sx")
    osso("mano_sx", pol_sx, pol_sx + asse_sx * 0.12, "avambraccio_sx")
    osso("spalla_dx", col + (sp_dx - col) * 0.25 - np.array([0, 0, 0.05]), sp_dx, "petto")
    osso("braccio_dx", sp_dx, gom_dx, "spalla_dx")
    osso("avambraccio_dx", gom_dx, pol_dx, "braccio_dx")
    osso("mano_dx", pol_dx, pol_dx + asse_dx * 0.12, "avambraccio_dx")
    return O


# ---------------------------------------------------------------------------
#  Misure: BALROG (dal file originale in mm, poi nei metri del modello)
# ---------------------------------------------------------------------------

def balrog_mm_a_m():
    o = M.carica_pkl()
    v = o["1"][0].astype(np.float64)
    f = o["1"][1]
    R = M.rot_asse(np.array([0, 0, 1.0]), math.pi / 2)
    vr = v @ R.T
    zmin = vr[:, 2].min()
    piedi = vr[vr[:, 2] < zmin + 4]
    centro = np.array([(piedi[:, 0].min() + piedi[:, 0].max()) / 2,
                       (piedi[:, 1].min() + piedi[:, 1].max()) / 2, zmin])
    scala = M.ALTEZZA_BALROG / (v[v[:, 0] < -70, 2].max() - zmin)
    return (lambda p: (np.asarray(p, float) @ R.T - centro) * scala), v, f


def ossa_balrog():
    mm, v, f = balrog_mm_a_m()
    x, y, z = v.T
    O = {}

    def osso(n, h, t, p=None, deform=True):
        O[n] = (mm(h), mm(t), p, deform)

    # --- gambe: due grappoli di vertici sotto il bacino (escluse coda e frusta) ---
    gambe = (z < -18) & (x < 6) & (y < 55) & (y > -70)
    yy = y[gambe & (z < -70)]
    c1, c2 = np.percentile(yy, 20), np.percentile(yy, 80)
    for _ in range(20):                                   # 2-medie in Y sui piedi
        lab = np.abs(yy - c1) < np.abs(yy - c2)
        c1, c2 = yy[lab].mean(), yy[~lab].mean()
    taglio = (c1 + c2) / 2
    gamba = {}
    for nome, lato in (("dx", y > taglio), ("sx", y <= taglio)):
        lato = lato & gambe
        pts = {}
        for zz in (-24, -48, -68):
            s = lato & (np.abs(z - zz) < 3)
            pts[zz] = v[s].mean(0)
        piede = lato & (z < -74)
        punta = v[piede][np.argmin(v[piede][:, 0])]
        gamba[nome] = (pts[-24], pts[-48], pts[-68], np.array([punta[0], pts[-68][1], -76]))
    # nel sistema originale il Balrog guarda verso -X: +Y e' la sua DESTRA (diventa -X in Blender)
    yc = (c1 + c2) / 2
    bacino = np.array([-6.0, yc, -20.0])
    osso("radice", (bacino[0], yc, -80), (bacino[0], yc, -70), None, False)
    osso("bacino", bacino, (-22, yc + 3, 2), "radice")
    osso("spina", (-22, yc + 3, 2), (-38, 4, 20), "bacino")
    osso("petto", (-38, 4, 20), (-50, 7, 30), "spina")
    osso("collo", (-50, 7, 30), (-58, 9, 34), "petto")
    osso("testa", (-58, 9, 34), (-84, 9, 40), "collo")
    osso("mascella", (-61, 9, 26.5), (-82, 9, 22.0), "testa")
    for lato, segno in (("sx", 1), ("dx", -1)):
        h, k, a, p = gamba[lato]
        hip = np.array([bacino[0], h[1], bacino[2] - 2])
        osso(f"coscia_{lato}", hip, k, "bacino")
        osso(f"stinco_{lato}", k, a, f"coscia_{lato}")
        osso(f"piede_{lato}", a, p, f"stinco_{lato}")
    # braccia (viste ortografiche): +Y = braccio destro, quello con la frusta
    osso("spalla_dx", (-40, 12, 24), (-38, 35, 27), "petto")
    osso("braccio_dx", (-38, 35, 27), (-30, 58, 11), "spalla_dx")
    osso("avambraccio_dx", (-30, 58, 11), (-20, 64.5, -6), "braccio_dx")
    osso("mano_dx", (-20, 64.5, -6), (-17, 66, -16), "avambraccio_dx")
    osso("spalla_sx", (-40, -4, 24), (-38, -36, 27), "petto")
    osso("braccio_sx", (-38, -36, 27), (-46, -60, 11), "spalla_sx")
    osso("avambraccio_sx", (-46, -60, 11), (-50, -76, -6), "braccio_sx")
    osso("mano_sx", (-50, -76, -6), (-52, -80, -18), "avambraccio_sx")
    # coda: baricentri di fasce lungo X dietro le anche
    coda = (x > 14) & (z < -8)
    xs = np.linspace(14, x[coda].max() - 2, 6)
    giunti = [np.array([4, yc, -24])]
    for a in xs:
        s = coda & (np.abs(x - a) < 3)
        giunti.append(v[s].mean(0))
    for i in range(6):
        osso(f"coda{i + 1}", giunti[i], giunti[i + 1], "bacino" if i == 0 else f"coda{i}")
    # criniera: tre ossa dalla schiena verso l'alto, lungo la spina dorsale
    linea = np.interp(x, [-64, -45, -30, -15, 0, 10, 15], [53, 46, 40, 30, 16, 2, -12])
    y_spina = np.interp(x, [-65, -55, -45, -35, -25, -15, -5, 5], [4, 1, -1, -3, -7, -10, -13, -15.5])
    for i, (a, b, padre) in enumerate(((-58, -40, "collo"), (-40, -22, "petto"), (-22, -2, "spina"))):
        s = (z > linea) & (np.abs(y - y_spina) < 10) & (x > a) & (x < b)
        c = v[s]
        xm = c[:, 0].mean()
        base = np.array([xm, np.interp(xm, [-65, -5], [4, -13]), np.interp(xm, [-64, 0], [53, 16]) - 4])
        cima = np.array([xm + 4, c[:, 1].mean(), np.percentile(c[:, 2], 85)])
        osso(f"criniera{i + 1}", base, cima, padre)
    O["_frusta"] = None        # la frusta si misura sulla cache in metri (vedi sotto)
    # frusta: ordine geodetico a partire dalla mano, sui vertici della zona "frusta"
    d = np.load(os.path.join(M.DIR_CACHE, "balrog_alta.npz"))
    vm = d["v"].astype(np.float64)
    zona = np.round(d["a_zona"][:, 0] * 10).astype(int)
    fr = zona == 2
    mano = O["mano_dx"][0]
    dm = np.linalg.norm(vm - mano, axis=1)
    sorg = np.where(fr & (dm < np.percentile(dm[fr], 1.5)))[0]
    g = geodetica(vm, d["f"], sorg, fr)
    giunti = catena_lungo(vm[fr], g[fr], 8, testa=O["mano_dx"][1])
    del O["_frusta"]
    for i in range(8):
        O[f"frusta{i + 1}"] = (giunti[i], giunti[i + 1], "mano_dx" if i == 0 else f"frusta{i}", True)
    return O, mm, v


# ---------------------------------------------------------------------------
#  Costruzione dell'armatura e pesi
# ---------------------------------------------------------------------------

def crea_armatura(nome, ossa):
    arm = bpy.data.armatures.new(nome + "_scheletro")
    ob = bpy.data.objects.new("Scheletro", arm)
    bpy.context.scene.collection.objects.link(ob)
    M.seleziona(ob)
    bpy.ops.object.mode_set(mode="EDIT")
    for n, (h, t, p, deform) in ossa.items():
        b = arm.edit_bones.new(n)
        b.head = Vector(h)
        b.tail = Vector(t)
        b.use_deform = deform
        # rollio coerente: l'asse Z dell'osso il piu' possibile verso -Y (avanti)
        b.align_roll(Vector((0, -1, 0)) if abs((Vector(t) - Vector(h)).normalized().y) < 0.9 else Vector((0, 0, 1)))
    for n, (h, t, p, deform) in ossa.items():
        if p:
            arm.edit_bones[n].parent = arm.edit_bones[p]
            arm.edit_bones[n].use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    arm.display_type = "STICK"
    return ob


def vertici(ob):
    co = np.empty(len(ob.data.vertices) * 3, np.float32)
    ob.data.vertices.foreach_get("co", co)
    return co.reshape(-1, 3).astype(np.float64)


def facce(ob):
    ob.data.calc_loop_triangles()
    t = np.empty(len(ob.data.loop_triangles) * 3, np.int32)
    ob.data.loop_triangles.foreach_get("vertices", t)
    return t.reshape(-1, 3)


def pesi_prossimita(V, ossa, consentite=None, potenza=5.0, eps=0.02):
    """Pesi 1/(d+eps)^p dai segmenti delle ossa deformanti; consentite: {osso: maschera vertici}."""
    nomi = [n for n, o in ossa.items() if o[3]]
    W = np.zeros((len(V), len(nomi)))
    for j, n in enumerate(nomi):
        h, t = ossa[n][0], ossa[n][1]
        W[:, j] = 1.0 / (dist_segmenti(V, h, t) + eps) ** potenza
        if consentite is not None and n in consentite:
            W[~consentite[n], j] = 0
    return nomi, W


def normalizza_top4(W):
    if W.shape[1] > 4:
        soglia = -np.sort(-W, axis=1)[:, 3:4]
        W = np.where(W >= soglia, W, 0)
    s = W.sum(1, keepdims=True)
    return W / np.maximum(s, 1e-12)


def applica_pesi(ob_mesh, nomi, W, soglia=0.01):
    ob_mesh.vertex_groups.clear()
    for j, n in enumerate(nomi):
        g = ob_mesh.vertex_groups.new(name=n)
        idx = np.where(W[:, j] > soglia)[0]
        for w in np.unique(np.round(W[idx, j], 3)):
            sel = idx[np.round(W[idx, j], 3) == w]
            g.add(sel.tolist(), float(w), "REPLACE")


def leggi_pesi(ob_mesh, nomi):
    W = np.zeros((len(ob_mesh.data.vertices), len(nomi)))
    idx = {g.index: nomi.index(g.name) for g in ob_mesh.vertex_groups if g.name in nomi}
    for v in ob_mesh.data.vertices:
        for g in v.groups:
            if g.group in idx:
                W[v.index, idx[g.group]] = g.weight
    return W


def collega_pelle(ob_mesh, ob_arm):
    ob_mesh.parent = ob_arm
    m = ob_mesh.modifiers.new("Armatura", "ARMATURE")
    m.object = ob_arm
    return m


def pesi_gandalf(ob, arm_ob, ossa):
    V = vertici(ob)
    F = facce(ob)
    lab = M.componenti(len(V), F)
    u, c = np.unique(lab, return_counts=True)
    # isole: le due piu' grandi sono le meta' del corpo; mano+bastone e mano+spada si
    # riconoscono dalla vicinanza ai polsi
    isole = u[np.argsort(-c)]
    mano = {}
    for lato in ("sx", "dx"):
        polso = ossa[f"mano_{lato}"][0]
        dist = [np.linalg.norm(V[lab == i] - polso, axis=1).min() for i in isole[:4]]
        # la mano e' l'isola (non tra le due piu' grandi) piu' vicina al polso
        cand = [(dd, i) for dd, i in zip(dist, isole[:4]) if i not in isole[:2]]
        mano[lato] = lab == min(cand)[1]
    log(f"   isole {len(u)}; mano_sx {mano['sx'].sum()} v, mano_dx {mano['dx'].sum()} v")
    # zone (capelli/barba) dalla cache ad alta risoluzione, per vertice piu' vicino
    d = np.load(os.path.join(M.DIR_CACHE, "gandalf_alta.npz"))
    vh = d["v"].astype(np.float64)
    zh = np.round(d["a_zona"][:, 0] * 10).astype(int)
    kd = KDTree(len(vh))
    for i, p in enumerate(vh):
        kd.insert(p, i)
    kd.balance()
    zona = np.array([zh[kd.find(p)[1]] for p in V])
    capelli = zona == 1
    corpo = ~(mano["sx"] | mano["dx"])
    nomi_def = [n for n, o in ossa.items() if o[3]]
    consentite = {n: corpo.copy() for n in nomi_def}
    for lato in ("sx", "dx"):
        consentite[f"mano_{lato}"] = mano[lato].copy()
    for n in nomi_def:
        if n not in ("testa", "collo", "petto"):
            consentite[n] &= ~capelli
    # sotto la cintura solo bacino e gonna; le ossa della gonna non salgono sopra il bacino
    sotto = V[:, 2] < 1.0
    for n in nomi_def:
        if n not in ("bacino", "gonna_sx", "gonna_dx", "gonna_dietro", "spina"):
            consentite[n] &= ~sotto | capelli
    for n in ("gonna_sx", "gonna_dx", "gonna_dietro"):
        consentite[n] &= V[:, 2] < 1.02
    nomi, W = pesi_prossimita(V, ossa, consentite)
    W = normalizza_top4(W)
    vic = M.Vicinato(len(V), F)
    for _ in range(6):                              # lisciatura sulla superficie
        W = 0.5 * W + 0.5 * vic.media(W)
    W[mano["sx"]] = 0
    W[mano["sx"], nomi.index("mano_sx")] = 1
    W[mano["dx"]] = 0
    W[mano["dx"], nomi.index("mano_dx")] = 1
    W = normalizza_top4(W)
    applica_pesi(ob, nomi, W)
    collega_pelle(ob, arm_ob)


def pesi_balrog(ob, arm_ob, ossa, mm):
    V = vertici(ob)
    F = facce(ob)
    nomi_def = [n for n, o in ossa.items() if o[3]]
    # 1) calore
    t0 = time.time()
    M.seleziona(ob, [])
    ob.select_set(True)
    arm_ob.select_set(True)
    bpy.context.view_layer.objects.active = arm_ob
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    Wc = leggi_pesi(ob, nomi_def)
    vuoti = Wc.sum(1) < 1e-4
    log(f"   calore: {time.time() - t0:.0f}s, vertici senza pesi {vuoti.sum()} su {len(V)}")
    # 2) prossimita' con regole per regione (nel sistema originale in mm per le regioni)
    Rinv = None
    consentite = {n: np.ones(len(V), bool) for n in nomi_def}
    frusta = np.zeros(len(V), bool)
    d = np.load(os.path.join(M.DIR_CACHE, "balrog_alta.npz"))
    vh = d["v"].astype(np.float64)
    zh = np.round(d["a_zona"][:, 0] * 10).astype(int)
    kd = KDTree(len(vh))
    for i, p in enumerate(vh):
        kd.insert(p, i)
    kd.balance()
    zona = np.array([zh[kd.find(p)[1]] for p in V])
    frusta = zona == 2
    fr_ossa = [n for n in nomi_def if n.startswith("frusta")]
    for n in nomi_def:
        if n in fr_ossa:
            consentite[n] = frusta.copy()
        elif n not in ("mano_dx", "avambraccio_dx"):
            consentite[n] = ~frusta
    nomi, Wp = pesi_prossimita(V, ossa, consentite, potenza=5.0, eps=0.04)
    Wp = normalizza_top4(Wp)
    # 3) combinazione: calore dove c'e', prossimita' sui vuoti e sulla frusta
    W = Wc / np.maximum(Wc.sum(1, keepdims=True), 1e-12)
    usa_p = vuoti | frusta
    W[usa_p] = Wp[usa_p]
    # niente pesi della frusta fuori dalla frusta (e viceversa)
    for j, n in enumerate(nomi):
        if n in fr_ossa:
            W[~frusta, j] = 0
    # mascella: regione sotto la linea della bocca, nel sistema in mm ricostruito
    inv = np.linalg.inv
    # (le regioni si calcolano sui vertici in metri riportati in mm)
    centro_s = mm(np.zeros(3))
    scala = np.linalg.norm(mm(np.array([1.0, 0, 0])) - centro_s)
    R = M.rot_asse(np.array([0, 0, 1.0]), math.pi / 2)
    Vmm = ((V - centro_s) / scala) @ R          # inversa di (p @ R.T - c) * s
    xm, ym, zm = Vmm.T
    linea_bocca = np.interp(xm, [-88, -72, -62, -56], [27.0, 26.0, 23.5, 22.0])
    mas = (xm < -57) & (np.abs(ym - 9) < 7.5) & (zm < linea_bocca) & (zm > 13)
    peso_m = np.clip((linea_bocca - zm) / 1.5, 0, 1) * np.clip((-57 - xm) / 4, 0, 1)
    j = nomi.index("mascella")
    W[mas] *= (1 - peso_m[mas])[:, None]
    W[mas, j] += peso_m[mas]
    W[~mas, j] = 0
    log(f"   mascella: {mas.sum()} vertici")
    vic = M.Vicinato(len(V), F)
    for _ in range(3):
        W = 0.5 * W + 0.5 * vic.media(W)
        for jj, n in enumerate(nomi):
            if n in fr_ossa:
                W[~frusta, jj] = 0
    W = normalizza_top4(W)
    applica_pesi(ob, nomi, W)
    # il calore ha gia' creato modificatore e genitore
    if not any(m.type == "ARMATURE" for m in ob.modifiers):
        collega_pelle(ob, arm_ob)


# ---------------------------------------------------------------------------
#  Animazioni
# ---------------------------------------------------------------------------

def q_mondo(arm_ob, osso, gradi):
    """Rotazione data negli assi del mondo (gradi X, Y, Z) -> quaternione locale dell'osso."""
    Mr = arm_ob.data.bones[osso].matrix_local.to_3x3().normalized()
    rx, ry, rz = (math.radians(a) for a in gradi)
    Rw = (Matrix.Rotation(rz, 3, "Z") @ Matrix.Rotation(ry, 3, "Y") @ Matrix.Rotation(rx, 3, "X"))
    return (Mr.inverted() @ Rw @ Mr).to_quaternion()


def crea_azione(arm_ob, nome, durata, posa, ciclo=False):
    """posa(t) -> ({osso: (gx, gy, gz)}, dz_radice); campionata a ogni fotogramma."""
    act = bpy.data.actions.new(nome)
    act.use_fake_user = True
    arm_ob.animation_data_create()
    arm_ob.animation_data.action = act
    n = int(round(durata * FPS))
    pb = arm_ob.pose.bones
    for b in pb:
        b.rotation_mode = "QUATERNION"
    for fr in range(n + 1):
        t = fr / FPS
        if ciclo and fr == n:
            t = 0.0                                   # ultimo = primo: ciclo perfetto
        rot, dz = posa(t)
        for b in pb:
            b.rotation_quaternion = q_mondo(arm_ob, b.name, rot.get(b.name, (0, 0, 0)))
            b.location = (0, 0, 0)
            b.keyframe_insert("rotation_quaternion", frame=fr + 1)
        r = pb["radice"]
        # spostamento verticale nello spazio dell'osso radice (che punta in alto: Y locale = Z)
        r.location = (0, dz, 0)
        r.keyframe_insert("location", frame=fr + 1)
    for fc in act.fcurves:
        for k in fc.keyframe_points:
            k.interpolation = "LINEAR"
    arm_ob.animation_data.action = None
    tr = arm_ob.animation_data.nla_tracks.new()
    tr.name = nome
    tr.strips.new(nome, 1, act)
    tr.mute = True
    log(f"   azione {nome}: {n + 1} fotogrammi ({durata:.2f}s)")
    return act


def K(*chiavi):
    """Scorciatoia: K((t, (gx,gy,gz)), ...) -> funzione t -> vettore."""
    return lambda t: catmull(list(chiavi), t)


def onda(t, T, armonica=1, fase=0.0):
    return math.sin(2 * math.pi * (armonica * t / T) + fase)


# --- Gandalf -----------------------------------------------------------------

def animazioni_gandalf(a):
    def riposo(t, T=3.0):
        r = onda(t, T)                      # respiro
        o = onda(t, T, 1, 1.2)              # ondeggiare
        p = {"bacino": (0, 0.8 * o, 0), "spina": (1.2 * r, 0, 0.6 * o), "petto": (1.5 * r, 0, 0),
             "collo": (-1.0 * r, 0, 1.0 * onda(t, T, 1, 2.0)), "testa": (-1.0 * r, 0.8 * o, 0),
             "spalla_sx": (0, -1.2 * r, 0), "braccio_sx": (2.0 * onda(t, T, 1, 0.6), -1.0 * r, 0),
             "mano_sx": (2.5 * onda(t, T, 1, 1.0), 0, 1.5 * onda(t, T, 2, 0.3)),
             "spalla_dx": (0, 1.2 * r, 0), "braccio_dx": (1.5 * onda(t, T, 1, 2.2), 0, 0),
             "mano_dx": (2.0 * onda(t, T, 1, 2.6), 0, 0),
             "gonna_sx": (1.5 * onda(t, T, 1, 0.5), 0, 0), "gonna_dx": (1.5 * onda(t, T, 1, 1.3), 0, 0),
             "gonna_dietro": (-1.5 * onda(t, T, 1, 0.9), 0, 0)}
        return p, 0.004 * r

    # attacco: carica (bastone indietro e in alto), spinta in avanti, fendente di Glamdring
    sp = K((0, (0, 0, 0)), (0.25, (-5, 0, 8)), (0.42, (6, 0, -10)), (0.62, (5, 0, -6)), (1.2, (0, 0, 0)))
    pe = K((0, (0, 0, 0)), (0.25, (-4, 0, 6)), (0.42, (5, 0, -8)), (0.62, (4, 0, -5)), (1.2, (0, 0, 0)))
    tes = K((0, (0, 0, 0)), (0.25, (3, 0, -4)), (0.42, (-8, 0, 6)), (0.7, (-4, 0, 3)), (1.2, (0, 0, 0)))
    bsx = K((0, (0, 0, 0)), (0.25, (-14, -12, 0)), (0.42, (14, -6, 0)), (0.65, (11, -4, 0)), (1.2, (0, 0, 0)))
    msx = K((0, (0, 0, 0)), (0.25, (-12, 0, 0)), (0.42, (6, 0, 0)), (0.65, (5, 0, 0)), (1.2, (0, 0, 0)))
    bdx = K((0, (0, 0, 0)), (0.3, (-10, 20, 0)), (0.5, (25, -15, 10)), (0.75, (15, -8, 5)), (1.2, (0, 0, 0)))
    mdx = K((0, (0, 0, 0)), (0.3, (-20, 0, 15)), (0.5, (40, 0, -20)), (0.75, (20, 0, -10)), (1.2, (0, 0, 0)))
    gon = K((0, (0, 0, 0)), (0.3, (4, 0, 0)), (0.5, (-6, 0, 0)), (0.8, (2, 0, 0)), (1.2, (0, 0, 0)))
    zr = K((0, 0.0), (0.25, -0.03), (0.42, 0.01), (0.7, 0.0), (1.2, 0.0))

    def attacco(t):
        return ({"spina": sp(t), "petto": pe(t), "testa": tes(t), "braccio_sx": bsx(t), "mano_sx": msx(t),
                 "braccio_dx": bdx(t), "mano_dx": mdx(t), "gonna_sx": gon(t), "gonna_dx": gon(t),
                 "gonna_dietro": -gon(t)}, float(zr(t)))

    cs = K((0, (0, 0, 0)), (0.12, (-14, 0, 4)), (0.3, (-8, 0, 2)), (0.7, (0, 0, 0)))
    ct = K((0, (0, 0, 0)), (0.12, (-12, 4, 0)), (0.35, (-4, 0, 0)), (0.7, (0, 0, 0)))
    cbs = K((0, (0, 0, 0)), (0.12, (-12, -12, 0)), (0.4, (-4, -4, 0)), (0.7, (0, 0, 0)))
    cbd = K((0, (0, 0, 0)), (0.12, (-10, 15, 0)), (0.4, (-3, 4, 0)), (0.7, (0, 0, 0)))
    cg = K((0, (0, 0, 0)), (0.15, (8, 0, 0)), (0.4, (-3, 0, 0)), (0.7, (0, 0, 0)))
    cz = K((0, 0.0), (0.12, -0.04), (0.4, -0.01), (0.7, 0.0))

    def colpito(t):
        return ({"bacino": cs(t) * 0.4, "spina": cs(t), "petto": cs(t) * 0.6, "testa": ct(t),
                 "braccio_sx": cbs(t), "braccio_dx": cbd(t), "gonna_sx": cg(t), "gonna_dx": cg(t),
                 "gonna_dietro": cg(t) * 0.5}, float(cz(t)))

    sz = K((0, 0.0), (0.08, -0.05), (0.2, 0.12), (0.32, -0.03), (0.4, 0.0))
    ss = K((0, (0, 0, 0)), (0.08, (8, 0, 0)), (0.2, (-3, 0, 0)), (0.32, (5, 0, 0)), (0.4, (0, 0, 0)))
    sg = K((0, (0, 0, 0)), (0.08, (-4, 0, 0)), (0.2, (-8, 0, 0)), (0.32, (6, 0, 0)), (0.4, (0, 0, 0)))

    def sali(t):
        return ({"spina": ss(t), "testa": -ss(t) * 0.5, "gonna_sx": sg(t), "gonna_dx": sg(t),
                 "gonna_dietro": -sg(t), "braccio_sx": -ss(t)}, float(sz(t)))

    vb = K((0, (0, 0, 0)), (0.35, (-6, 4, 0)), (0.9, (-4, -24, 0)), (1.2, (-5, -27, 0)), (1.5, (-5, -26, 0)))
    vm = K((0, (0, 0, 0)), (0.35, (-6, 0, 0)), (0.9, (-4, 30, 0)), (1.2, (-4, 34, 0)), (1.5, (-4, 33, 0)))
    vd = K((0, (0, 0, 0)), (0.5, (0, 10, 0)), (1.0, (-10, 20, 0)), (1.5, (-8, 18, 0)))
    vs = K((0, (0, 0, 0)), (0.35, (4, 0, 0)), (0.9, (-6, 0, 0)), (1.5, (-5, 0, 0)))
    vt = K((0, (0, 0, 0)), (0.35, (5, 0, 0)), (0.9, (-14, 0, 0)), (1.5, (-12, 0, 0)))

    def vittoria(t):
        return ({"spina": vs(t), "petto": vs(t), "testa": vt(t), "spalla_sx": vb(t) * 0.3,
                 "braccio_sx": vb(t), "mano_sx": vm(t), "braccio_dx": vd(t)}, 0.0)

    fb = K((0, (0, 0, 0)), (0.3, (-6, 3, 0)), (0.8, (-18, 6, 0)), (1.5, (-30, 8, 0)))
    fs = K((0, (0, 0, 0)), (0.3, (-4, 0, 3)), (0.8, (-10, 0, 5)), (1.5, (-14, 0, 6)))
    fsx = K((0, (0, 0, 0)), (0.4, (-8, -15, 0)), (1.0, (-18, -26, 0)), (1.5, (-20, -30, 0)))
    fdx = K((0, (0, 0, 0)), (0.4, (-8, 18, 0)), (1.0, (-16, 30, 0)), (1.5, (-20, 34, 0)))
    ft = K((0, (0, 0, 0)), (0.5, (-8, 0, 0)), (1.5, (-20, 0, 0)))
    fg = K((0, (0, 0, 0)), (0.5, (6, 0, 0)), (1.0, (14, 0, 0)), (1.5, (18, 0, 0)))

    def caduta(t):
        return ({"bacino": fb(t), "spina": fs(t), "petto": fs(t), "testa": ft(t), "braccio_sx": fsx(t),
                 "braccio_dx": fdx(t), "gonna_sx": fg(t), "gonna_dx": fg(t), "gonna_dietro": fg(t) * 1.3},
                0.0)

    crea_azione(a, "riposo", 3.0, riposo, ciclo=True)
    crea_azione(a, "attacco", 1.2, attacco)
    crea_azione(a, "colpito", 0.7, colpito)
    crea_azione(a, "sali", 0.4, sali)
    crea_azione(a, "vittoria", 1.5, vittoria)
    crea_azione(a, "caduta", 1.5, caduta)


# --- Balrog ------------------------------------------------------------------

def animazioni_balrog(a):
    coda = [f"coda{i}" for i in range(1, 7)]
    frusta = [f"frusta{i}" for i in range(1, 9)]
    crin = [f"criniera{i}" for i in range(1, 4)]

    def riposo(t, T=2.5):
        r = onda(t, T)
        p = {"bacino": (0, 0, 1.0 * onda(t, T, 1, 0.8)), "spina": (1.5 * r, 0, 0), "petto": (2.5 * r, 0, 0),
             "collo": (-1.5 * r, 0, 0), "testa": (-1.5 * r, 0, 2.0 * onda(t, T, 1, 1.5)),
             "mascella": (2.0 + 2.0 * r, 0, 0),
             "spalla_sx": (0, -2.0 * r, 0), "spalla_dx": (0, 2.0 * r, 0),
             "braccio_sx": (2.0 * onda(t, T, 1, 0.5), 0, 0), "braccio_dx": (2.0 * onda(t, T, 1, 1.5), 0, 0),
             "mano_sx": (4.0 * onda(t, T, 1, 2.0), 0, 0)}
        for i, n in enumerate(coda):
            p[n] = (2.5 * onda(t, T, 1, -0.6 * i), 0, 5.0 * onda(t, T, 1, -0.7 * i))
        for i, n in enumerate(frusta):
            p[n] = (5.0 * onda(t, T, 1, -0.8 * i), 4.0 * onda(t, T, 2, -0.6 * i), 6.0 * onda(t, T, 1, -0.9 * i + 1))
        for i, n in enumerate(crin):
            p[n] = (3.0 * onda(t, T, 3, 1.7 * i), 2.5 * onda(t, T, 5, 0.9 * i), 0)
        return p, 0.012 * r

    # attacco: carica (braccio indietro e in alto), sferzata in avanti, onda lungo la frusta
    # braccio della frusta (destro, lato -X): alzare = +Y; per un osso che pende verso il
    # basso +X porta la punta INDIETRO, quindi la sferzata in avanti e' una rotazione -X
    bfr = K((0, (0, 0, 0)), (0.3, (25, 40, -10)), (0.5, (-40, -10, 12)), (0.75, (-30, -6, 8)), (1.3, (0, 0, 0)))
    afr = K((0, (0, 0, 0)), (0.3, (20, 10, 0)), (0.5, (-25, -5, 0)), (0.75, (-15, 0, 0)), (1.3, (0, 0, 0)))
    sp = K((0, (0, 0, 0)), (0.3, (-8, 4, 15)), (0.5, (12, -3, -15)), (0.8, (8, 0, -8)), (1.3, (0, 0, 0)))
    te = K((0, (0, 0, 0)), (0.3, (-10, 0, 0)), (0.55, (6, 0, -5)), (0.9, (2, 0, 0)), (1.3, (0, 0, 0)))
    ma = K((0, (0, 0, 0)), (0.3, (5, 0, 0)), (0.55, (22, 0, 0)), (0.95, (18, 0, 0)), (1.3, (0, 0, 0)))
    bli = K((0, (0, 0, 0)), (0.3, (-8, -10, 0)), (0.5, (10, 4, 0)), (1.3, (0, 0, 0)))

    def attacco(t):
        p = {"spina": sp(t) * 0.5, "petto": sp(t), "testa": te(t), "mascella": ma(t), "braccio_dx": bfr(t),
             "avambraccio_dx": afr(t), "braccio_sx": bli(t)}
        for i, n in enumerate(frusta):
            ri = 0.04 * i                          # ritardo crescente lungo la frusta
            # la frusta resta indietro durante la sferzata (+X) e poi schiocca in avanti (-X)
            f = K((0, (0, 0, 0)), (0.3 + ri, (-6, 3, -4)), (0.5 + ri, (9, -2, 4)),
                  (0.68 + ri, (-12, 2, -5)), (0.9 + ri, (4, 0, 2)), (1.3, (0, 0, 0)))
            p[n] = f(t)
        for i, n in enumerate(coda):
            p[n] = tuple(np.array((0, 0, 6.0)) * math.sin(2 * math.pi * t / 1.3 - 0.5 * i)
                         * math.sin(math.pi * t / 1.3))
        return p, 0.0

    cs = K((0, (0, 0, 0)), (0.12, (-12, 0, 5)), (0.35, (-5, 0, 2)), (0.7, (0, 0, 0)))
    ct = K((0, (0, 0, 0)), (0.12, (-15, 5, 0)), (0.4, (-4, 0, 0)), (0.7, (0, 0, 0)))
    cb = K((0, (0, 0, 0)), (0.12, (-15, 0, 0)), (0.4, (-4, 0, 0)), (0.7, (0, 0, 0)))
    cm = K((0, (0, 0, 0)), (0.12, (15, 0, 0)), (0.4, (6, 0, 0)), (0.7, (0, 0, 0)))
    cz = K((0, 0.0), (0.12, -0.05), (0.4, -0.01), (0.7, 0.0))

    def colpito(t):
        p = {"bacino": cs(t) * 0.4, "spina": cs(t), "petto": cs(t), "testa": ct(t), "mascella": cm(t),
             "braccio_sx": cb(t) + np.array((0, -6, 0)) * (cb(t)[0] / -15),
             "braccio_dx": cb(t) + np.array((0, 6, 0)) * (cb(t)[0] / -15)}
        for i, n in enumerate(coda + frusta):
            p[n] = (0, 0, 5.0 * math.sin(2 * math.pi * t / 0.7 - 0.6 * i) * math.sin(math.pi * t / 0.7))
        return p, float(cz(t))

    sz = K((0, 0.0), (0.08, -0.08), (0.2, 0.15), (0.32, -0.05), (0.4, 0.0))
    ss = K((0, (0, 0, 0)), (0.08, (8, 0, 0)), (0.2, (-4, 0, 0)), (0.32, (6, 0, 0)), (0.4, (0, 0, 0)))
    sk = K((0, (0, 0, 0)), (0.08, (-10, 0, 0)), (0.2, (8, 0, 0)), (0.32, (-8, 0, 0)), (0.4, (0, 0, 0)))

    def sali(t):
        p = {"spina": ss(t), "petto": ss(t) * 0.5, "testa": -ss(t), "coscia_sx": sk(t), "coscia_dx": sk(t),
             "stinco_sx": -sk(t) * 1.2, "stinco_dx": -sk(t) * 1.2}
        for i, n in enumerate(coda):
            p[n] = -ss(t) * (0.6 + 0.2 * i)
        return p, float(sz(t))

    vb = K((0, (0, 0, 0)), (0.5, (-5, 0, 0)), (1.0, (-15, -30, 0)), (1.5, (-14, -28, 0)))
    vd = K((0, (0, 0, 0)), (0.5, (-5, 0, 0)), (1.0, (-15, 30, 0)), (1.5, (-14, 28, 0)))
    vs = K((0, (0, 0, 0)), (0.5, (4, 0, 0)), (1.0, (-10, 0, 0)), (1.5, (-9, 0, 0)))
    vt = K((0, (0, 0, 0)), (0.5, (6, 0, 0)), (1.0, (-18, 0, 0)), (1.5, (-16, 0, 0)))
    vm = K((0, (0, 0, 0)), (0.6, (4, 0, 0)), (1.0, (24, 0, 0)), (1.5, (22, 0, 0)))

    def vittoria(t):
        p = {"spina": vs(t) * 0.5, "petto": vs(t), "testa": vt(t), "mascella": vm(t),
             "braccio_sx": vb(t), "braccio_dx": vd(t), "spalla_sx": vb(t) * 0.3, "spalla_dx": vd(t) * 0.3}
        for i, n in enumerate(crin):
            p[n] = (4 * math.sin(2 * math.pi * t * 3 + i), 0, 0)
        for i, n in enumerate(coda):
            p[n] = (-4.0 * min(t / 1.0, 1), 0, 0)
        return p, 0.0

    fb = K((0, (0, 0, 0)), (0.3, (-6, -3, 0)), (0.8, (-18, -6, 0)), (1.5, (-28, -8, 0)))
    fsx = K((0, (0, 0, 0)), (0.4, (-10, -20, 0)), (1.0, (-25, -40, 0)), (1.5, (-30, -45, 0)))
    fdx = K((0, (0, 0, 0)), (0.4, (-10, 20, 0)), (1.0, (-25, 40, 0)), (1.5, (-30, 45, 0)))
    ft = K((0, (0, 0, 0)), (0.5, (-8, 0, 0)), (1.5, (-18, 0, 0)))
    fm = K((0, (0, 0, 0)), (0.5, (10, 0, 0)), (1.5, (20, 0, 0)))

    def caduta(t):
        p = {"bacino": fb(t), "spina": fb(t) * 0.4, "petto": fb(t) * 0.3, "testa": ft(t), "mascella": fm(t),
             "braccio_sx": fsx(t), "braccio_dx": fdx(t), "coscia_sx": -fb(t) * 0.5, "coscia_dx": -fb(t) * 0.3}
        for i, n in enumerate(frusta):
            p[n] = (6 * math.sin(2 * math.pi * t / 0.75 - 0.7 * i), 0, 0)
        for i, n in enumerate(coda):
            p[n] = (8 * min(t / 1.5, 1), 0, 4 * math.sin(2 * math.pi * t / 0.75 - 0.6 * i))
        return p, 0.0

    crea_azione(a, "riposo", 2.5, riposo, ciclo=True)
    crea_azione(a, "attacco", 1.3, attacco)
    crea_azione(a, "colpito", 0.7, colpito)
    crea_azione(a, "sali", 0.4, sali)
    crea_azione(a, "vittoria", 1.5, vittoria)
    crea_azione(a, "caduta", 1.5, caduta)


# ---------------------------------------------------------------------------
#  Controlli visivi
# ---------------------------------------------------------------------------

def tavola_ossa(nome, ossa, viste):
    """Ossa sovrapposte a due viste ortografiche (workbench) -> /tmp/ossa_<nome>.png."""
    import subprocess
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.color_type = "TEXTURE"
    file = []
    for k, (c, d, m) in enumerate(viste):
        cam = M.collega(bpy.data.objects.new("c", bpy.data.cameras.new("c")))
        cam.data.type = "ORTHO"
        dv = Vector(d).normalized()
        cam.location = Vector(c) + dv * 20
        cam.rotation_euler = (-dv).to_track_quat("-Z", "Y").to_euler()
        cam.data.ortho_scale = 2 * m
        cam.data.clip_end = 60
        sc.camera = cam
        sc.render.resolution_x = sc.render.resolution_y = 800
        p = f"/tmp/ossa_{nome}_{k}.png"
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        bpy.data.objects.remove(cam)
        file.append((p, c, d, m))
    import json
    dati = {n: [list(o[0]), list(o[1])] for n, o in ossa.items()}
    json.dump({"file": [(p, list(c), list(d), m) for p, c, d, m in file], "ossa": dati},
              open(f"/tmp/ossa_{nome}.json", "w"))
    subprocess.run(["python3", "/home/claude/src/3mf/anim/_tavola_ossa.py",
                    f"/tmp/ossa_{nome}.json", f"/tmp/ossa_{nome}.png"])


def griglia_fotogrammi(nome, arm_ob, righe, altezza, uscita):
    """righe: [(azione, [secondi...])] -> griglia di render Cycles piccoli."""
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    h = altezza
    k = h / 1.9
    luci = [("AREA", (3.0 * k, -4.0 * k, 3.5 * k), 900.0 * k * k, (1.0, 0.8, 0.6), 2.5 * k),
            ("AREA", (-4.0 * k, -2.0 * k, 2.0 * k), 300.0 * k * k, (0.6, 0.7, 1.0), 3.0 * k),
            ("AREA", (-1.0 * k, 5.0 * k, 4.0 * k), 500.0 * k * k, (1.0, 0.6, 0.4), 2.0 * k)]
    d = 4.4 * k
    file_righe = []
    for azione, tempi in righe:
        act = bpy.data.actions[azione]
        arm_ob.animation_data.action = act
        file = []
        for t in tempi:
            sc.frame_set(int(round(t * FPS)) + 1)
            p = f"/tmp/fot_{nome}_{azione}_{t:.2f}.png"
            M.scatta(p, (0.62 * d, -0.78 * d, 0.62 * h), (0, 0, 0.6 * h), lente=50, dim=(360, 360),
                     campioni=12, luci=luci)
            file.append(p)
        M.affianca(file, f"/tmp/riga_{nome}_{azione}.png")
        file_righe.append(f"/tmp/riga_{nome}_{azione}.png")
    arm_ob.animation_data.action = None
    # impila le righe in verticale
    imgs = [bpy.data.images.load(p) for p in file_righe]
    W, H = imgs[0].size
    tot = np.zeros((H * len(imgs), W, 4), np.float32)
    for i, im in enumerate(reversed(imgs)):        # Blender: origine in basso
        px = np.empty(W * H * 4, np.float32)
        im.pixels.foreach_get(px)
        tot[i * H:(i + 1) * H] = px.reshape(H, W, 4)
    out = bpy.data.images.new("griglia", W, H * len(imgs), alpha=False)
    out.pixels.foreach_set(tot.ravel())
    out.filepath_raw = uscita
    out.file_format = "PNG"
    out.save()
    log(f"   griglia {uscita}")


# ---------------------------------------------------------------------------
#  Esportazione e verifica
# ---------------------------------------------------------------------------

def esporta(percorso, ob_mesh, arm_ob):
    bpy.context.scene.render.fps = FPS
    M.seleziona(arm_ob, [ob_mesh])
    bpy.ops.export_scene.gltf(
        filepath=percorso, export_format="GLB", use_selection=True,
        export_yup=True, export_texcoords=True, export_normals=True, export_tangents=False,
        export_materials="EXPORT", export_image_format="JPEG", export_jpeg_quality=85,
        export_cameras=False, export_lights=False,
        export_skins=True, export_all_influences=False, export_def_bones=False,
        export_animations=True, export_animation_mode="ACTIONS", export_force_sampling=True,
        export_frame_range=False, export_anim_slide_to_zero=True, export_optimize_animation_size=True,
        export_reset_pose_bones=True, export_morph=False, export_apply=False)
    log(f"   esportato {percorso}: {os.path.getsize(percorso) / 1048576:.2f} MB")


def verifica_glb(percorso):
    """Legge il .glb (JSON interno): animazioni con durata, giunti, poi reimporta in scena vuota."""
    import json
    import struct
    dati = open(percorso, "rb").read()
    lung = struct.unpack("<I", dati[12:16])[0]
    j = json.loads(dati[20:20 + lung])
    bin0 = 20 + lung + 8
    out = []
    for a in j.get("animations", []):
        tmax = 0
        for c in a["channels"]:
            acc = j["accessors"][a["samplers"][c["sampler"]]["input"]]
            tmax = max(tmax, acc["max"][0])
        out.append((a["name"], tmax))
    giunti = len(j["skins"][0]["joints"]) if j.get("skins") else 0
    M.azzera_scena()
    bpy.ops.import_scene.gltf(filepath=percorso)
    arm = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    # (l'importatore aggiunge una mesh di forma per le ossa: si tengono solo le mesh con pelle)
    mesh = [o for o in bpy.context.scene.objects if o.type == "MESH" and o.find_armature()]
    pts = np.concatenate([vertici(o) @ np.array(o.matrix_world)[:3, :3].T + np.array(o.matrix_world)[:3, 3]
                          for o in mesh])
    g = np.stack([pts[:, 0], pts[:, 2], -pts[:, 1]], 1)
    log(f"   {os.path.basename(percorso)}: {os.path.getsize(percorso) / 1048576:.2f} MB, giunti {giunti}, "
        f"armature {len(arm)}, mesh {len(mesh)}")
    log(f"     bbox Godot min {np.round(g.min(0), 3)} max {np.round(g.max(0), 3)}")
    for n, d in out:
        log(f"     animazione {n}: {d:.3f}s")
    return out, giunti


# ---------------------------------------------------------------------------
#  Programma
# ---------------------------------------------------------------------------

def prepara(nome):
    bpy.ops.wm.open_mainfile(filepath=os.path.join(DIR_SRC, f"{nome}_pulito.blend"))
    sc = bpy.context.scene
    sc.render.fps = FPS
    ob = [o for o in sc.objects if o.type == "MESH"][0]
    return ob


def gandalf():
    log("== Gandalf: scheletro e animazioni ==")
    ob = prepara("gandalf")
    ossa = ossa_gandalf()
    arm = crea_armatura("gandalf", ossa)
    if SOLO_OSSA:
        tavola_ossa("gandalf", ossa, [((0, 0, 1.3), (0, -1, 0), 1.4), ((0, -0.2, 1.3), (1, 0, 0), 1.4)])
        return
    pesi_gandalf(ob, arm, ossa)
    animazioni_gandalf(arm)
    log(f"   ossa: {len(arm.data.bones)}")
    if RENDER:
        griglia_fotogrammi("gandalf", arm, [("attacco", [0.0, 0.25, 0.42, 0.62, 0.9]),
                                            ("riposo", [0.0, 0.75, 1.5, 2.25, 2.9]),
                                            ("caduta", [0.3, 0.8, 1.5, 1.5, 1.5]),
                                            ("vittoria", [0.5, 1.5, 1.5, 1.5, 1.5])],
                           M.ALTEZZA_GANDALF, "/home/claude/src/anim_gandalf.png")
    esporta(os.path.join(M.DIR_ASSET, "gandalf.glb"), ob, arm)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(DIR_SRC, "gandalf_rig.blend"), compress=True)
    verifica_glb(os.path.join(M.DIR_ASSET, "gandalf.glb"))


def balrog():
    log("== Balrog: scheletro e animazioni ==")
    ob = prepara("balrog")
    ossa, mm, _ = ossa_balrog()
    arm = crea_armatura("balrog", ossa)
    if SOLO_OSSA:
        tavola_ossa("balrog", ossa, [((0, 0, 2.0), (0, -1, 0), 2.6), ((0, 0.5, 2.0), (1, 0, 0), 2.6)])
        return
    pesi_balrog(ob, arm, ossa, mm)
    animazioni_balrog(arm)
    log(f"   ossa: {len(arm.data.bones)}")
    if RENDER:
        griglia_fotogrammi("balrog", arm, [("attacco", [0.0, 0.3, 0.5, 0.65, 0.9]),
                                           ("riposo", [0.0, 0.6, 1.25, 1.9, 2.4]),
                                           ("caduta", [0.3, 0.8, 1.5, 1.5, 1.5]),
                                           ("vittoria", [0.5, 1.5, 1.5, 1.5, 1.5])],
                           M.ALTEZZA_BALROG, "/home/claude/src/anim_balrog.png")
    esporta(os.path.join(M.DIR_ASSET, "balrog.glb"), ob, arm)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(DIR_SRC, "balrog_rig.blend"), compress=True)
    verifica_glb(os.path.join(M.DIR_ASSET, "balrog.glb"))


if __name__ == "__main__":
    scelta = [a for a in sys.argv[1:] if not a.startswith("--")]
    scelta = scelta[0] if scelta else "tutti"
    if scelta in ("gandalf", "tutti"):
        gandalf()
    if scelta in ("balrog", "tutti"):
        balrog()
