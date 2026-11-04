# -*- coding: utf-8 -*-
"""
Generatore procedurale dei modelli 3D per il duello sul Ponte di Khazad-dum.

Costruisce da zero (scena azzerata ogni volta), con l'API Python di Blender
(bpy usato come modulo, senza interfaccia), tre modelli:

  - Gandalf il Grigio   -> assets/3d/gandalf.glb
  - il Balrog           -> assets/3d/balrog.glb
  - il Ponte            -> assets/3d/ponte.glb

e rende un'anteprima PNG di ciascuno in /home/claude/src/.

Uso (dalla radice del progetto):
    /home/claude/bvenv/bin/python tools/modelli_blender.py [gandalf|balrog|ponte|verifica|tutti] [--no-render]

Convenzioni:
  - 1 unita' Blender = 1 metro = 1 unita' Godot.
  - In Blender Z e' l'alto; l'esportatore glTF mappa Blender (x, y, z) -> glTF (x, z, -y).
    I personaggi guardano verso -Y in Blender, cioe' verso +Z in Godot.
  - I nodi procedurali non sopravvivono all'esportazione glTF: tutte le texture
    procedurali vengono "cotte" (bake Cycles) in immagini e impacchettate nel .glb.
"""

import bpy
import bmesh
import math
import os
import random
import sys
import time
from mathutils import Vector, Matrix, Quaternion, noise

RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR_ASSET = os.path.join(RADICE, "assets", "3d")
DIR_ANTEPRIME = "/home/claude/src"

RENDER = "--no-render" not in sys.argv


# ---------------------------------------------------------------------------
#  Utilita' generali
# ---------------------------------------------------------------------------

def azzera_scena():
    """Riporta Blender alle impostazioni di fabbrica, scena vuota."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.unit_settings.system = "METRIC"


def collega(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def mesh_da_dati(nome, vertici, facce):
    me = bpy.data.meshes.new(nome)
    me.from_pydata([tuple(v) for v in vertici], [], facce)
    me.validate()
    me.update()
    return collega(bpy.data.objects.new(nome, me))


def catmull(punti, n=6):
    """Spline Catmull-Rom attraverso i punti dati, n campioni per segmento."""
    P = [Vector(p) for p in punti]
    out = []
    for i in range(len(P) - 1):
        p0 = P[i - 1] if i > 0 else 2 * P[i] - P[i + 1]
        p1, p2 = P[i], P[i + 1]
        p3 = P[i + 2] if i + 2 < len(P) else 2 * P[i + 1] - P[i]
        for k in range(n):
            t = k / n
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t
                              + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-1].copy())
    return out


def tubo(nome, spina, raggio, seg=10, tappi=True, su=(0, 0, 1), forma=None):
    """Tubo lungo una polilinea con sezioni trasportate in parallelo.

    raggio: funzione t -> r oppure t -> (rx, ry)   (t in [0,1] lungo la spina)
    forma:  funzione opzionale (t, angolo) -> moltiplicatore del raggio
    """
    spina = [Vector(p) for p in spina]
    n = len(spina)
    T = []
    for i in range(n):
        a = spina[max(i - 1, 0)]
        b = spina[min(i + 1, n - 1)]
        T.append((b - a).normalized())
    su = Vector(su)
    N0 = su - T[0] * su.dot(T[0])
    if N0.length < 1e-4:
        N0 = Vector((1, 0, 0)) - T[0] * T[0].x
    N0.normalize()
    Ns = [N0]
    for i in range(1, n):
        rot = T[i - 1].rotation_difference(T[i])
        Ns.append((rot @ Ns[-1]).normalized())
    V, F = [], []
    for i in range(n):
        t = i / (n - 1)
        Nn = Ns[i]
        B = T[i].cross(Nn)
        r = raggio(t)
        rx, ry = (r if isinstance(r, tuple) else (r, r))
        for j in range(seg):
            a = 2 * math.pi * j / seg
            m = 1.0 if forma is None else forma(t, a)
            V.append(spina[i] + (Nn * math.cos(a) * rx + B * math.sin(a) * ry) * m)
    for i in range(n - 1):
        for j in range(seg):
            a = i * seg + j
            b = i * seg + (j + 1) % seg
            F.append((a, b, b + seg, a + seg))
    if tappi:
        c0 = len(V)
        V.append(spina[0])
        c1 = len(V)
        V.append(spina[-1])
        for j in range(seg):
            F.append((c0, (j + 1) % seg, j))
            F.append((c1, (n - 1) * seg + j, (n - 1) * seg + (j + 1) % seg))
    return mesh_da_dati(nome, V, F)


def griglia(nome, nu, nv, funz, chiusa_u=False):
    """Superficie parametrica: funz(u, v) -> Vector, u,v in [0,1]."""
    V, F = [], []
    cu = nu if chiusa_u else nu + 1
    for j in range(nv + 1):
        for i in range(cu):
            V.append(funz(i / nu, j / nv))
    for j in range(nv):
        for i in range(nu):
            a = j * cu + i
            b = j * cu + (i + 1) % cu
            F.append((a, b, b + cu, a + cu))
    return mesh_da_dati(nome, V, F)


def sfera(nome, centro, scala, seg=16, anelli=10):
    me = bpy.data.meshes.new(nome)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=anelli, radius=1.0)
    bm.to_mesh(me)
    bm.free()
    ob = collega(bpy.data.objects.new(nome, me))
    ob.location = centro
    ob.scale = scala
    applica_trasformazioni(ob)
    return ob


def icosfera(nome, centro, scala, suddiv=2):
    me = bpy.data.meshes.new(nome)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=suddiv, radius=1.0)
    bm.to_mesh(me)
    bm.free()
    ob = collega(bpy.data.objects.new(nome, me))
    ob.location = centro
    ob.scale = scala
    applica_trasformazioni(ob)
    return ob


def applica_trasformazioni(ob):
    mw = ob.matrix_basis.copy()
    ob.data.transform(mw)
    ob.matrix_basis = Matrix.Identity(4)


def modificatore(ob, tipo, **kw):
    m = ob.modifiers.new(tipo.lower(), tipo)
    for k, v in kw.items():
        setattr(m, k, v)
    return m


def applica_modificatori(ob):
    """Applica tutti i modificatori usando la mesh valutata (senza operatori)."""
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    vecchia = ob.data
    ob.modifiers.clear()
    ob.data = me
    if vecchia.users == 0:
        bpy.data.meshes.remove(vecchia)


def texture_rumore(nome, tipo="CLOUDS", scala=0.25, **kw):
    tx = bpy.data.textures.new(nome, tipo)
    if hasattr(tx, "noise_scale"):
        tx.noise_scale = scala
    for k, v in kw.items():
        setattr(tx, k, v)
    return tx


def normali_fuori(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()


def liscia(ob, angolo=None):
    for p in ob.data.polygons:
        p.use_smooth = True
    if angolo is not None:
        try:
            ob.data.set_sharp_from_angle(angle=angolo)
        except Exception:
            pass


def unisci(nome, oggetti):
    """Unisce piu' oggetti in uno solo (le slot materiale restano per faccia)."""
    oggetti = [o for o in oggetti if o is not None]
    base = oggetti[0]
    with bpy.context.temp_override(active_object=base, object=base,
                                   selected_objects=oggetti,
                                   selected_editable_objects=oggetti):
        bpy.ops.object.join()
    base.name = nome
    base.data.name = nome
    return base


def triangoli(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def decima_a(ob, massimo):
    t = triangoli(ob)
    if t > massimo:
        modificatore(ob, "DECIMATE", ratio=massimo / t * 0.98, use_collapse_triangulate=True)
        applica_modificatori(ob)
    return triangoli(ob)


def uv_automatiche(ob, margine=0.004, angolo=66):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(angolo), island_margin=margine,
                             area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    ob.select_set(False)
    if ob.data.uv_layers:
        ob.data.uv_layers[0].name = "UVMap"


# ---------------------------------------------------------------------------
#  Nodi shader: piccole scorciatoie
# ---------------------------------------------------------------------------

class Nodi:
    """Aiutante per costruire alberi di nodi in poche righe."""

    def __init__(self, nt):
        self.nt = nt

    def n(self, tipo, **prop):
        nodo = self.nt.nodes.new(tipo)
        for k, v in prop.items():
            if k.startswith("i_"):
                nodo.inputs[k[2:].replace("__", " ")].default_value = v
            else:
                setattr(nodo, k, v)
        return nodo

    def l(self, uscita, ingresso):
        self.nt.links.new(uscita, ingresso)

    # --- operazioni frequenti ---
    def coord(self):
        tc = self.n("ShaderNodeTexCoord")
        return tc.outputs["Object"]

    def mat(self, op, a, b=None, clamp=False):
        m = self.n("ShaderNodeMath", operation=op, use_clamp=clamp)
        for i, x in enumerate((a, b)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                m.inputs[i].default_value = x
            else:
                self.l(x, m.inputs[i])
        return m.outputs[0]

    def mix(self, fac, a, b):
        m = self.n("ShaderNodeMix", data_type="RGBA", blend_type="MIX")
        for sock, val in ((m.inputs[0], fac), (m.inputs[6], a), (m.inputs[7], b)):
            if isinstance(val, (int, float)):
                sock.default_value = val
            elif isinstance(val, tuple):
                sock.default_value = val if len(val) == 4 else (*val, 1.0)
            else:
                self.l(val, sock)
        return m.outputs[2]

    def rampa(self, fac, punti):
        r = self.n("ShaderNodeValToRGB")
        el = r.color_ramp.elements
        while len(el) > len(punti):
            el.remove(el[-1])
        while len(el) < len(punti):
            el.new(0.5)
        for e, (pos, col) in zip(el, punti):
            e.position = pos
            e.color = col if len(col) == 4 else (*col, 1.0)
        self.l(fac, r.inputs[0])
        return r.outputs[0]

    def rumore(self, vett, scala, dettaglio=4.0, rug=0.55, distorsione=0.0):
        t = self.n("ShaderNodeTexNoise", i_Scale=scala, i_Detail=dettaglio,
                   i_Roughness=rug, i_Distortion=distorsione)
        self.l(vett, t.inputs["Vector"])
        return t.outputs["Fac"]

    def voronoi(self, vett, scala, caratteristica="F1", casuale=1.0):
        t = self.n("ShaderNodeTexVoronoi", feature=caratteristica, i_Scale=scala,
                   i_Randomness=casuale)
        self.l(vett, t.inputs["Vector"])
        return t

    def scala_vett(self, vett, s):
        m = self.n("ShaderNodeVectorMath", operation="SCALE")
        m.inputs["Scale"].default_value = s
        self.l(vett, m.inputs[0])
        return m.outputs[0]

    def somma_vett(self, a, b):
        m = self.n("ShaderNodeVectorMath", operation="ADD")
        self.l(a, m.inputs[0])
        if isinstance(b, tuple):
            m.inputs[1].default_value = b
        else:
            self.l(b, m.inputs[1])
        return m.outputs[0]

    def separa(self, vett):
        s = self.n("ShaderNodeSeparateXYZ")
        self.l(vett, s.inputs[0])
        return s.outputs

    def combina(self, x, y, z):
        c = self.n("ShaderNodeCombineXYZ")
        for i, v in enumerate((x, y, z)):
            if isinstance(v, (int, float)):
                c.inputs[i].default_value = v
            else:
                self.l(v, c.inputs[i])
        return c.outputs[0]


def cuoci(ob, costruttore, dimensione, nome, tipo="EMIT"):
    """Cuoce (bake) una texture procedurale sull'oggetto e restituisce l'immagine.

    costruttore(N) riceve l'aiutante Nodi e restituisce:
      - per tipo EMIT:   la presa (socket) del colore
      - per tipo NORMAL: la presa dell'altezza (bump)
    """
    sc = bpy.context.scene
    img = bpy.data.images.new(nome, dimensione, dimensione, alpha=False)
    if tipo == "NORMAL":
        img.colorspace_settings.name = "Non-Color"
    mat = bpy.data.materials.new("tmp_" + nome)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    N = Nodi(nt)
    out = N.n("ShaderNodeOutputMaterial")
    if tipo == "EMIT":
        em = N.n("ShaderNodeEmission", i_Strength=1.0)
        N.l(costruttore(N), em.inputs["Color"])
        N.l(em.outputs[0], out.inputs["Surface"])
        sc.cycles.samples = 1
    else:
        bsdf = N.n("ShaderNodeBsdfPrincipled")
        altezza, forza = costruttore(N)
        bump = N.n("ShaderNodeBump", i_Strength=forza, i_Distance=0.02)
        N.l(altezza, bump.inputs["Height"])
        N.l(bump.outputs[0], bsdf.inputs["Normal"])
        N.l(bsdf.outputs[0], out.inputs["Surface"])
        sc.cycles.samples = 4
    tex = N.n("ShaderNodeTexImage")
    tex.image = img
    nt.nodes.active = tex
    vecchi = list(ob.data.materials)
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    sc.render.bake.margin = 6
    sc.render.bake.use_clear = True
    sc.render.bake.normal_space = "TANGENT"
    t0 = time.time()
    bpy.ops.object.bake(type=tipo)
    print(f"   bake {nome} ({tipo}, {dimensione}px) in {time.time() - t0:.1f}s")
    ob.select_set(False)
    ob.data.materials.clear()
    for m in vecchi:
        ob.data.materials.append(m)
    bpy.data.materials.remove(mat)
    img.pack()
    return img


def materiale(nome, colore=(0.5, 0.5, 0.5), rug=0.8, metal=0.0, img_colore=None,
              img_normale=None, forza_normale=1.0, emissione=None, img_emissione=None,
              forza_emissione=1.0):
    """Materiale Principled compatibile glTF (immagini cotte o colori semplici)."""
    mat = bpy.data.materials.new(nome)
    mat.use_nodes = True
    nt = mat.node_tree
    N = Nodi(nt)
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = rug
    bsdf.inputs["Metallic"].default_value = metal
    if img_colore is not None:
        t = N.n("ShaderNodeTexImage")
        t.image = img_colore
        N.l(t.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = (*colore, 1.0)
    if img_normale is not None:
        t = N.n("ShaderNodeTexImage")
        t.image = img_normale
        nm = N.n("ShaderNodeNormalMap", i_Strength=forza_normale)
        N.l(t.outputs["Color"], nm.inputs["Color"])
        N.l(nm.outputs[0], bsdf.inputs["Normal"])
    if img_emissione is not None:
        t = N.n("ShaderNodeTexImage")
        t.image = img_emissione
        N.l(t.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = forza_emissione
    elif emissione is not None:
        bsdf.inputs["Emission Color"].default_value = (*emissione, 1.0)
        bsdf.inputs["Emission Strength"].default_value = forza_emissione
    return mat


def assegna(ob, mat):
    ob.data.materials.clear()
    ob.data.materials.append(mat)


def finitura_cotta(ob, nome, dim, colore_fn, rug=0.8, metal=0.0, normale_fn=None,
                   emissione_fn=None, forza_emissione=1.0, forza_normale=1.0, uv=True):
    """UV automatiche + bake colore (e opzionalmente normale/emissione) + materiale finale."""
    if uv:
        uv_automatiche(ob)
    img_c = cuoci(ob, colore_fn, dim, nome + "_colore")
    img_n = cuoci(ob, normale_fn, dim, nome + "_normale", tipo="NORMAL") if normale_fn else None
    img_e = cuoci(ob, emissione_fn, dim, nome + "_emissione") if emissione_fn else None
    assegna(ob, materiale(nome, rug=rug, metal=metal, img_colore=img_c, img_normale=img_n,
                          img_emissione=img_e, forza_emissione=forza_emissione,
                          forza_normale=forza_normale))
    return ob


# ---------------------------------------------------------------------------
#  Anteprima ed esportazione
# ---------------------------------------------------------------------------

def guarda_verso(ob, bersaglio):
    d = Vector(bersaglio) - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def anteprima(percorso, cam_pos, bersaglio, lente=50, dim=(800, 800), campioni=24,
              luci=None, sfondo=(0.06, 0.06, 0.07)):
    if not RENDER:
        return
    sc = bpy.context.scene
    cam = collega(bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera")))
    cam.data.lens = lente
    cam.data.clip_end = 200
    cam.location = cam_pos
    guarda_verso(cam, bersaglio)
    sc.camera = cam
    if luci is None:
        luci = [("SUN", (4, -6, 8), 3.0, (1.0, 0.95, 0.9)),
                ("SUN", (-6, 3, 3), 0.8, (0.6, 0.7, 1.0))]
    for i, (tipo, pos, energia, col) in enumerate(luci):
        ld = bpy.data.lights.new(f"luce{i}", tipo)
        ld.energy = energia
        ld.color = col
        if tipo == "SUN":
            ld.angle = math.radians(8)
        lo = collega(bpy.data.objects.new(f"luce{i}", ld))
        lo.location = pos
        guarda_verso(lo, bersaglio)
    mondo = bpy.data.worlds.new("Mondo")
    mondo.use_nodes = True
    mondo.node_tree.nodes["Background"].inputs[0].default_value = (*sfondo, 1)
    mondo.node_tree.nodes["Background"].inputs[1].default_value = 1.0
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
    print(f"   anteprima {percorso} in {time.time() - t0:.1f}s")
    # rimuove camera e luci per non esportarle
    for o in [o for o in sc.objects if o.type in ("CAMERA", "LIGHT")]:
        bpy.data.objects.remove(o)
    bpy.context.view_layer.update()


def esporta(percorso, oggetti):
    for o in bpy.context.scene.objects:
        o.select_set(o in oggetti)
    bpy.ops.export_scene.gltf(
        filepath=percorso, export_format="GLB", use_selection=True,
        export_apply=True, export_yup=True, export_texcoords=True, export_normals=True,
        export_materials="EXPORT", export_image_format="JPEG", export_jpeg_quality=88,
        export_cameras=False, export_lights=False, export_animations=False,
        export_skins=False, export_morph=False)
    print(f"   esportato {percorso}: {os.path.getsize(percorso) / 1024:.0f} KB")


# ---------------------------------------------------------------------------
#  MODELLO 1 - GANDALF IL GRIGIO
# ---------------------------------------------------------------------------
#  Blender: guarda verso -Y, mano destra verso -X.

GANDALF_CRISTALLO = Vector((-0.40, -0.19, 1.835))   # centro del cristallo del bastone


def profilo_veste(z):
    """(rx, ry, cy) della veste alla quota z (interpolazione lineare)."""
    tab = [(0.00, 0.34, 0.31, 0.05), (0.12, 0.32, 0.285, 0.04), (0.45, 0.27, 0.225, 0.02),
           (0.80, 0.225, 0.175, 0.01), (0.98, 0.205, 0.155, 0.0), (1.15, 0.225, 0.16, 0.0),
           (1.30, 0.245, 0.155, 0.01), (1.38, 0.22, 0.14, 0.015), (1.44, 0.14, 0.11, 0.0),
           (1.49, 0.065, 0.065, 0.0)]
    for (z0, a0, b0, c0), (z1, a1, b1, c1) in zip(tab, tab[1:]):
        if z <= z1:
            t = max(0.0, (z - z0) / (z1 - z0))
            t = t * t * (3 - 2 * t)
            return a0 + (a1 - a0) * t, b0 + (b1 - b0) * t, c0 + (c1 - c0) * t
    return tab[-1][1:]


def gandalf_veste():
    zmax = 1.49

    def f(u, v):
        th = 2 * math.pi * u
        z = zmax * v
        rx, ry, cy = profilo_veste(z)
        s = max(0.0, 1 - z / 1.35)
        # pieghe verticali del tessuto, piu' marcate verso l'orlo
        piega = (0.55 * math.sin(7 * th + 0.8 + 1.2 * s) + 0.30 * math.sin(12 * th + 2.1 - 2 * s)
                 + 0.15 * math.sin(19 * th + 0.3))
        piega = math.copysign(abs(piega) ** 0.8, piega)
        m = 1 + 0.11 * s ** 1.2 * piega + 0.012 * noise.noise(Vector((3 * math.cos(th), 3 * math.sin(th), 4 * z)))
        x = math.cos(th) * rx * m
        y = math.sin(th) * ry * m + cy
        # il vento spinge l'orlo all'indietro (+Y) e un poco di lato
        y += 0.10 * s ** 2 * (0.6 + 0.4 * math.sin(th))
        x += 0.03 * s ** 2
        zz = z
        if v == 0:
            zz = 0.015 + 0.02 * (1 + math.sin(5 * th + 1.0))
        return Vector((x, y, zz))

    ob = griglia("Veste", 64, 44, f, chiusa_u=True)
    # fondo chiuso (sotto la veste)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    anello = [bm.verts[i] for i in range(64)]
    bmesh.ops.contextual_create(bm, geom=[e for e in bm.edges if all(v in anello for v in e.verts)])
    bm.to_mesh(ob.data)
    bm.free()
    normali_fuori(ob)
    return ob


def gandalf_mantello():
    def f(u, v):
        # u: da un fianco all'altro passando per la schiena; v: dall'alto al basso
        a0, a1 = -0.15 + 0.35 * v, math.pi + 0.15 - 0.30 * v
        th = a0 + (a1 - a0) * u
        if v < 0.08:
            k = v / 0.08
            z = 1.50 - 0.10 * k
            rx = 0.15 + 0.17 * k
            ry = 0.12 + 0.08 * k
            cy = 0.0
        else:
            s = (v - 0.08) / 0.92
            z = 1.40 - 1.30 * s
            # orlo inferiore frastagliato dal vento
            z += 0.10 * s ** 3 * (0.5 + 0.5 * math.sin(6 * th + 1.7))
            rx = 0.32 + 0.16 * s
            ry = 0.20 + 0.14 * s
            cy = 0.03 + 0.34 * s ** 1.6
        s = max(0.0, (v - 0.08) / 0.92)
        piega = math.sin(9 * th + 3 * s + 0.4) * 0.6 + math.sin(15 * th - 2 * s) * 0.4
        m = 1 + (0.02 + 0.11 * s) * piega
        x = math.cos(th) * rx * m + 0.07 * s ** 2
        y = math.sin(th) * ry * m + cy + 0.05 * s ** 2 * math.sin(4 * u * math.pi + 3 * s)
        return Vector((x, y, z))

    ob = griglia("Mantello", 48, 40, f)
    modificatore(ob, "SOLIDIFY", thickness=0.014, offset=1.0)
    applica_modificatori(ob)
    normali_fuori(ob)
    return ob


def gandalf_braccio(nome, punti, mano_dir):
    """Manica larga da mago: stretta alla spalla, svasata e cadente al polso."""
    spina = catmull(punti, 8)

    def r(t):
        if t < 0.55:
            return 0.07 + 0.005 * t
        k = (t - 0.55) / 0.45
        return 0.075 + 0.07 * k ** 1.6

    def forma(t, a):
        k = max(0.0, (t - 0.6) / 0.4)
        return 1 + 0.08 * math.sin(6 * a + 2 * t) * (0.3 + k)

    ob = tubo(nome, spina, r, seg=16, tappi=False, su=(0, 0, 1), forma=forma)
    # la parte inferiore del polsino ricade verso il basso
    for v in ob.data.vertices:
        p = v.co
        fine = Vector(punti[-1])
        d = (p - fine).length
        if d < 0.14:
            k = 1 - d / 0.14
            if p.z < fine.z:
                p.z -= 0.05 * k
    modificatore(ob, "SOLIDIFY", thickness=0.012, offset=-1.0)
    applica_modificatori(ob)
    return ob


def gandalf_mano(nome, centro, scala):
    m = sfera(nome, centro, scala, seg=12, anelli=8)
    return m


def gandalf_testa():
    parti = []
    testa = sfera("Testa", (0, -0.015, 1.575), (0.085, 0.095, 0.105), seg=20, anelli=14)
    parti.append(testa)
    naso = tubo("Naso", catmull([(0, -0.095, 1.605), (0, -0.118, 1.575), (0, -0.122, 1.553)], 4),
                lambda t: 0.017 - 0.006 * t, seg=8)
    parti.append(naso)
    # orecchie
    for sx in (-1, 1):
        parti.append(sfera("Orecchio", (sx * 0.083, -0.01, 1.575), (0.015, 0.025, 0.035), 8, 6))
    return unisci("Pelle", parti)


def gandalf_occhi():
    return unisci("Occhi", [sfera("Occhio", (sx * 0.034, -0.085, 1.592), (0.013, 0.008, 0.009), 8, 6)
                            for sx in (-1, 1)])


def gandalf_barba():
    parti = []
    rng = random.Random(7)
    # massa principale della barba: dal mento al petto, appuntita e mossa dal vento
    sp = catmull([(0, -0.085, 1.515), (0, -0.115, 1.45), (0.008, -0.145, 1.34), (0.022, -0.15, 1.23),
                  (0.04, -0.135, 1.12), (0.055, -0.115, 1.04)], 6)

    def rb(t):
        w = 0.075 * (1 - t) ** 0.7 + 0.008
        return (w * 0.55, w)

    def fb(t, a):
        return 1 + 0.12 * math.sin(11 * a + 6 * t) + 0.05 * math.sin(5 * a)

    parti.append(tubo("Barba", sp, rb, seg=20, su=(0, -1, 0), forma=fb))
    # basette/guance: dalla tempia lungo la mascella fino al mento
    for sx in (-1, 1):
        pts = [(sx * 0.078, -0.02, 1.575), (sx * 0.076, -0.06, 1.52), (sx * 0.055, -0.095, 1.48),
               (sx * 0.02, -0.11, 1.45)]
        parti.append(tubo("Basetta", catmull(pts, 5), lambda t: 0.024 + 0.006 * math.sin(math.pi * t), seg=9))
    # baffi spioventi
    for sx in (-1, 1):
        parti.append(tubo("Baffo", catmull([(0, -0.112, 1.535), (sx * 0.03, -0.112, 1.522),
                                            (sx * 0.05, -0.10, 1.49), (sx * 0.055, -0.095, 1.44)], 4),
                          lambda t: 0.013 * (1 - t) + 0.004, seg=8))
    # ciocche della barba
    for i in range(12):
        sx = rng.uniform(-1, 1)
        base = Vector((sx * 0.055, -0.105 + abs(sx) * 0.03, 1.49 - rng.uniform(0, 0.05)))
        lung = rng.uniform(0.18, 0.40)
        pts = [base, base + Vector((sx * 0.01, -0.04, -lung * 0.4)),
               base + Vector((sx * 0.01 + 0.015, -0.035, -lung * 0.75)),
               base + Vector((0.025 + sx * 0.008, -0.02, -lung))]
        parti.append(tubo("Ciocca", catmull(pts, 4), lambda t: 0.016 * (1 - t) + 0.003, seg=6))
    # capelli: massa dietro la testa fino alle scapole, spinta indietro dal vento
    sp = catmull([(0, 0.03, 1.63), (0, 0.085, 1.55), (0.01, 0.15, 1.44), (0.03, 0.22, 1.34)], 6)
    parti.append(tubo("Chioma", sp, lambda t: (0.06 * (1 - t) + 0.02, 0.105 * (1 - 0.35 * t)), seg=16,
                      su=(0, 1, 0), forma=lambda t, a: 1 + 0.1 * math.sin(9 * a + 5 * t)))
    # ciocche laterali che scendono sulle spalle
    for sx in (-1, 1):
        for k in range(3):
            base = Vector((sx * 0.085, 0.0 + 0.03 * k, 1.60))
            pts = [base, base + Vector((sx * 0.02, 0.02, -0.08)),
                   base + Vector((sx * 0.035, 0.05 + 0.02 * k, -0.18)),
                   base + Vector((sx * 0.04, 0.13 + 0.04 * k, -0.27 + 0.03 * k))]
            parti.append(tubo("Capelli", catmull(pts, 4), lambda t: 0.024 * (1 - t) ** 0.7 + 0.005, seg=7))
    # sopracciglia folte e sporgenti
    for sx in (-1, 1):
        parti.append(tubo("Sopracciglio", catmull([(sx * 0.010, -0.095, 1.611), (sx * 0.04, -0.097, 1.62),
                                                   (sx * 0.072, -0.08, 1.627)], 3),
                          lambda t: 0.011 + 0.004 * t, seg=6))
    return unisci("Barba", parti)


def gandalf_dita(centro, asse, raggio_presa, verso):
    """Quattro dita chiuse attorno a un'asta (bastone o elsa)."""
    asse = Vector(asse).normalized()
    a = asse.orthogonal().normalized()
    b = asse.cross(a)
    parti = []
    for k in range(4):
        c = centro + asse * (0.022 * (k - 1.5))
        pts = []
        for j in range(5):
            ang = verso + j * 0.55
            pts.append(c + (a * math.cos(ang) + b * math.sin(ang)) * raggio_presa)
        parti.append(tubo("Dito", pts, lambda t: 0.0105 - 0.002 * t, seg=6))
    return parti


def gandalf_cappello():
    parti = []
    # tesa larga, leggermente cadente e ondulata, inclinata in avanti
    def tesa(u, v):
        th = 2 * math.pi * u
        r = 0.10 + 0.21 * v
        cad = 0.05 * v ** 2 + 0.018 * v * math.sin(3 * th + 0.5)
        return Vector((math.cos(th) * r, math.sin(th) * r * 0.95, 1.655 - cad))

    t = griglia("Tesa", 48, 8, tesa, chiusa_u=True)
    modificatore(t, "SOLIDIFY", thickness=0.012, offset=0.0)
    applica_modificatori(t)
    parti.append(t)
    # cono con la punta piegata all'indietro
    sp = catmull([(0, 0.0, 1.645), (0, 0.005, 1.72), (0.0, 0.03, 1.80), (0.01, 0.075, 1.86),
                  (0.02, 0.14, 1.895), (0.025, 0.19, 1.90)], 8)

    def rc(t):
        return 0.105 * (1 - t) ** 1.25 + 0.004

    def fc(t, a):
        return 1 + 0.04 * math.sin(5 * a + 4 * t) * (1 - t)

    parti.append(tubo("Cono", sp, rc, seg=24, forma=fc, su=(0, -1, 0)))
    cap = unisci("Cappello", parti)
    # inclinazione complessiva
    cap.data.transform(Matrix.Translation((0, 0, 1.6)) @ Matrix.Rotation(math.radians(-6), 4, "X")
                       @ Matrix.Translation((0, 0, -1.6)))
    return cap


def gandalf_nastro():
    """Fascia scura del cappello e cintura."""
    parti = []
    m6 = Matrix.Translation((0, 0, 1.6)) @ Matrix.Rotation(math.radians(-6), 4, "X") @ Matrix.Translation((0, 0, -1.6))
    pts = [Vector((math.cos(a) * 0.104, math.sin(a) * 0.104, 1.672)) for a in
           [2 * math.pi * i / 32 for i in range(33)]]
    f = tubo("Fascia", pts, lambda t: (0.006, 0.018), seg=6, tappi=False, su=(0, 0, 1))
    f.data.transform(m6)
    parti.append(f)
    # cintura
    rx, ry, cy = profilo_veste(0.98)
    pts = [Vector((math.cos(a) * (rx + 0.01), math.sin(a) * (ry + 0.01) + cy + 0.003, 0.98))
           for a in [2 * math.pi * i / 40 for i in range(41)]]
    parti.append(tubo("Cintura", pts, lambda t: (0.008, 0.024), seg=6, tappi=False, su=(0, 0, 1)))
    # estremita' pendente della cintura
    parti.append(tubo("Pendente", catmull([(0.09, -0.16, 0.975), (0.10, -0.175, 0.86), (0.105, -0.17, 0.74)], 4),
                      lambda t: (0.007, 0.018), seg=6, su=(0, -1, 0)))
    # borsa alla cintura
    parti.append(sfera("Borsa", (-0.17, -0.10, 0.90), (0.045, 0.03, 0.06), 10, 8))
    return unisci("Cuoio", parti)


def gandalf_bastone():
    x0, y0 = GANDALF_CRISTALLO.x, GANDALF_CRISTALLO.y
    parti = []
    sp = catmull([(x0 + 0.03, y0 + 0.02, 0.0), (x0 + 0.02, y0 + 0.01, 0.5), (x0 - 0.005, y0, 1.1),
                  (x0 + 0.005, y0 - 0.005, 1.55), (x0, y0, 1.74)], 8)

    def rs(t):
        return 0.017 + 0.007 * t + 0.003 * math.sin(40 * t)

    parti.append(tubo("Asta", sp, rs, seg=10))
    # testa nodosa: rami ricurvi che stringono il cristallo
    for i in range(4):
        a = i * math.pi / 2 + 0.4
        dx, dy = math.cos(a), math.sin(a)
        c = GANDALF_CRISTALLO
        pts = [(x0, y0, 1.72), (x0 + dx * 0.035, y0 + dy * 0.035, 1.78),
               (c.x + dx * 0.045, c.y + dy * 0.045, c.z + 0.02), (c.x + dx * 0.018, c.y + dy * 0.018, c.z + 0.075)]
        parti.append(tubo("Ramo", catmull(pts, 5), lambda t: 0.012 * (1 - t) + 0.003, seg=7))
    return unisci("Bastone", parti)


def gandalf_cristallo():
    c = GANDALF_CRISTALLO
    cr = icosfera("Cristallo", c, (0.028, 0.028, 0.045), suddiv=1)
    return cr


def gandalf_spada(mano):
    """Glamdring nella mano sinistra, alzata in diagonale."""
    d = Vector((0.30, -0.40, 1.0)).normalized()
    lato = d.cross(Vector((0, -1, 0))).normalized()
    piatto = d.cross(lato).normalized()
    parti_lama, parti_elsa = [], []
    base = mano + d * 0.06
    lung = 0.74
    V, F = [], []
    sez = 12
    for i in range(sez + 1):
        t = i / sez
        p = base + d * (lung * t)
        w = 0.024 * (1 - t ** 3) + 0.001
        sp = 0.006 * (1 - t) + 0.001
        V += [p + lato * w, p + piatto * sp, p - lato * w, p - piatto * sp]
    for i in range(sez):
        for j in range(4):
            a = i * 4 + j
            b = i * 4 + (j + 1) % 4
            F.append((a, b, b + 4, a + 4))
    F.append((0, 3, 2, 1))
    lama = mesh_da_dati("Lama", V, F)
    normali_fuori(lama)
    parti_lama.append(lama)
    # elsa: guardia curva, impugnatura, pomo
    g = [mano + d * 0.06 + lato * (k * 0.09) + d * (0.025 * abs(k) ** 2) for k in (-1, -0.5, 0, 0.5, 1)]
    parti_elsa.append(tubo("Guardia", catmull(g, 3), lambda t: 0.011, seg=8))
    parti_elsa.append(tubo("Impugnatura", [mano - d * 0.07, mano + d * 0.06], lambda t: 0.014, seg=8))
    parti_elsa.append(sfera("Pomo", mano - d * 0.085, (0.022, 0.022, 0.022), 10, 8))
    return unisci("Lama", parti_lama), unisci("Elsa", parti_elsa)


def costruisci_gandalf():
    print("== Gandalf ==")
    azzera_scena()
    veste = gandalf_veste()
    mantello = gandalf_mantello()
    # braccio destro (-X): regge il bastone; braccio sinistro (+X): alza la spada
    mano_d = Vector((GANDALF_CRISTALLO.x + 0.005, GANDALF_CRISTALLO.y + 0.005, 1.14))
    br_d = gandalf_braccio("ManicaD", [(-0.22, 0.02, 1.37), (-0.31, 0.03, 1.22), (-0.35, 0.0, 1.07),
                                       (-0.38, -0.12, 1.10), (mano_d.x + 0.01, mano_d.y + 0.02, mano_d.z + 0.02)], None)
    mano_s = Vector((0.44, -0.24, 1.47))
    br_s = gandalf_braccio("ManicaS", [(0.22, 0.02, 1.37), (0.33, 0.0, 1.27), (0.41, -0.08, 1.30),
                                       (0.44, -0.18, 1.40), (mano_s.x - 0.005, mano_s.y + 0.035, mano_s.z - 0.04)], None)
    veste = unisci("Veste", [veste, br_d, br_s])
    pelle = gandalf_testa()
    asta = Vector((GANDALF_CRISTALLO.x, GANDALF_CRISTALLO.y, mano_d.z))
    mani = [gandalf_mano("ManoD", asta + Vector((-0.02, 0.025, 0.0)), (0.032, 0.04, 0.05)),
            gandalf_mano("ManoS", mano_s + Vector((0.01, 0.02, -0.01)), (0.038, 0.034, 0.045))]
    mani += gandalf_dita(asta, (0, 0, 1), 0.032, 2.4)
    mani.append(tubo("Pollice", [asta + Vector((0.0, 0.03, 0.035)), asta + Vector((0.022, 0.0, 0.055))],
                     lambda t: 0.012, seg=6))
    d_spada = Vector((0.30, -0.40, 1.0)).normalized()
    mani += gandalf_dita(mano_s, d_spada, 0.026, 0.5)
    pelle = unisci("Pelle", [pelle] + mani)
    occhi = gandalf_occhi()
    barba = gandalf_barba()
    cappello = gandalf_cappello()
    cuoio = gandalf_nastro()
    bastone = gandalf_bastone()
    cristallo = gandalf_cristallo()
    lama, elsa = gandalf_spada(mano_s)
    # scarponi che spuntano sotto la veste
    stivali = unisci("Stivali", [sfera("Stivale", (sx * 0.095, -0.23, 0.04), (0.055, 0.095, 0.045), 12, 8)
                                 for sx in (-1, 1)])

    # rumore leggero sul tessuto
    for ob, forza in ((veste, 0.008), (mantello, 0.01), (cappello, 0.005)):
        tx = texture_rumore("rumore_" + ob.name, "CLOUDS", 0.06)
        modificatore(ob, "DISPLACE", texture=tx, strength=forza, texture_coords="OBJECT")
        applica_modificatori(ob)
    for ob in (veste, mantello, pelle, barba, cappello, cuoio, bastone, stivali, elsa):
        liscia(ob)
    for ob in (cristallo, lama):
        liscia(ob, math.radians(30))

    # ---- materiali cotti ----
    def tessuto(base, scuro):
        def c(N):
            co = N.coord()
            # trama verticale del tessuto + macchie + orlo sporco
            sx, sy, sz = N.separa(co)
            stir = N.combina(N.mat("MULTIPLY", sx, 18.0), N.mat("MULTIPLY", sy, 18.0), N.mat("MULTIPLY", sz, 1.5))
            fibre = N.rumore(stir, 6.0, 3.0, 0.5)
            macchie = N.rumore(co, 4.0, 5.0, 0.6)
            f = N.mat("ADD", N.mat("MULTIPLY", fibre, 0.5), N.mat("MULTIPLY", macchie, 0.5))
            col = N.rampa(f, [(0.3, scuro), (0.7, base)])
            sporco = N.mat("SUBTRACT", 1.0, N.mat("MULTIPLY", sz, 3.0), clamp=True)
            return N.mix(N.mat("MULTIPLY", sporco, 0.6), col, (0.12, 0.11, 0.10))
        return c

    finitura_cotta(veste, "Veste", 1024, tessuto((0.22, 0.22, 0.23), (0.10, 0.10, 0.11)), rug=0.9)
    finitura_cotta(mantello, "Mantello", 1024, tessuto((0.17, 0.175, 0.19), (0.075, 0.08, 0.09)), rug=0.9)
    finitura_cotta(cappello, "Cappello", 512, tessuto((0.20, 0.20, 0.21), (0.09, 0.09, 0.10)), rug=0.9)

    def capelli(N):
        co = N.coord()
        sx, sy, sz = N.separa(co)
        stir = N.combina(N.mat("MULTIPLY", sx, 30.0), N.mat("MULTIPLY", sy, 30.0), N.mat("MULTIPLY", sz, 2.0))
        f = N.rumore(stir, 8.0, 4.0, 0.6)
        return N.rampa(f, [(0.25, (0.45, 0.45, 0.45)), (0.75, (0.85, 0.85, 0.83))])

    finitura_cotta(barba, "Barba", 512, capelli, rug=0.85)

    def pelle_c(N):
        f = N.rumore(N.coord(), 30.0, 3.0, 0.5)
        return N.rampa(f, [(0.3, (0.55, 0.38, 0.30)), (0.7, (0.72, 0.55, 0.45))])

    finitura_cotta(pelle, "Pelle", 512, pelle_c, rug=0.6)

    def legno(N):
        co = N.coord()
        sx, sy, sz = N.separa(co)
        stir = N.combina(N.mat("MULTIPLY", sx, 40.0), N.mat("MULTIPLY", sy, 40.0), sz)
        f = N.rumore(stir, 4.0, 6.0, 0.6, distorsione=1.5)
        return N.rampa(f, [(0.3, (0.05, 0.03, 0.015)), (0.5, (0.14, 0.085, 0.045)), (0.75, (0.09, 0.055, 0.03))])

    finitura_cotta(bastone, "Legno", 512, legno, rug=0.7)

    assegna(occhi, materiale("Occhi", (0.02, 0.02, 0.025), rug=0.3))
    assegna(cuoio, materiale("Cuoio", (0.10, 0.065, 0.04), rug=0.7))
    assegna(stivali, materiale("Stivali", (0.035, 0.025, 0.018), rug=0.7))
    assegna(cristallo, materiale("Cristallo", (0.8, 0.9, 1.0), rug=0.1,
                                 emissione=(0.75, 0.88, 1.0), forza_emissione=6.0))
    assegna(lama, materiale("Glamdring", (0.85, 0.87, 0.92), rug=0.22, metal=1.0,
                            emissione=(0.55, 0.7, 1.0), forza_emissione=0.4))
    assegna(elsa, materiale("Elsa", (0.75, 0.6, 0.3), rug=0.35, metal=1.0))

    oggetti = [veste, mantello, pelle, occhi, barba, cappello, cuoio, bastone, cristallo, lama, elsa, stivali]
    gandalf = unisci("Gandalf", oggetti)
    tri = decima_a(gandalf, 35000)
    print(f"   triangoli Gandalf: {tri}")
    if "--retro" in sys.argv:
        anteprima("/tmp/retro_gandalf.png", (-2.6, 2.6, 1.6), (0, 0, 1.0), lente=50, dim=(500, 500))
    if "--primo-piano" in sys.argv:
        anteprima("/tmp/primo_gandalf.png", (0.5, -1.2, 1.62), (0, 0, 1.5), lente=50, dim=(500, 500))
    anteprima(os.path.join(DIR_ANTEPRIME, "anteprima_gandalf.png"), (2.2, -3.2, 1.7), (0, 0, 1.0),
              lente=50)
    esporta(os.path.join(DIR_ASSET, "gandalf.glb"), [gandalf])


# ---------------------------------------------------------------------------
#  MODELLO 2 - IL BALROG
# ---------------------------------------------------------------------------
#  Blender: guarda verso -Y; mano destra (frusta) a -X, sinistra (spada) a +X.

BALROG_MANO_D = Vector((-1.12, -0.55, 1.62))
BALROG_MANO_S = Vector((1.05, -0.62, 2.05))
FATTORE_MB = 1 / 0.574       # raggio metaball -> raggio superficie (soglia 0.6, rigidita' 2)


class Metaball:
    def __init__(self, nome, risoluzione=0.05):
        self.dati = bpy.data.metaballs.new(nome)
        self.dati.resolution = risoluzione
        self.dati.render_resolution = risoluzione
        self.dati.threshold = 0.6
        self.ob = collega(bpy.data.objects.new(nome, self.dati))

    def palla(self, c, r, scala=(1, 1, 1), rot=None, rig=2.0):
        e = self.dati.elements.new()
        if scala != (1, 1, 1):
            e.type = "ELLIPSOID"
            e.size_x, e.size_y, e.size_z = scala
        e.co = c
        e.radius = r * FATTORE_MB
        e.stiffness = rig
        if rot is not None:
            e.rotation = rot
        return e

    def capsula(self, a, b, r, rig=2.0):
        a, b = Vector(a), Vector(b)
        d = b - a
        e = self.dati.elements.new()
        e.type = "CAPSULE"
        e.co = (a + b) / 2
        e.radius = r * FATTORE_MB
        e.size_x = d.length / 2
        e.rotation = Vector((1, 0, 0)).rotation_difference(d.normalized())
        e.stiffness = rig
        return e

    def simm(self, metodo, *args, **kw):
        """Applica l'elemento e il suo speculare rispetto al piano YZ."""
        getattr(self, metodo)(*args, **kw)
        spec = []
        for a in args:
            if isinstance(a, (tuple, Vector)) and len(a) == 3 and not isinstance(a, Quaternion):
                spec.append((-a[0], a[1], a[2]))
            else:
                spec.append(a)
        getattr(self, metodo)(*spec, **kw)

    def in_mesh(self, nome):
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(self.ob.evaluated_get(dg))
        bpy.data.objects.remove(self.ob)
        return collega(bpy.data.objects.new(nome, me))


def balrog_corpo():
    mb = Metaball("CorpoMB", 0.045)
    # --- busto ---
    mb.palla((0, 0.02, 2.30), 0.40, scala=(1.25, 0.85, 1.0))           # torace
    mb.simm("palla", (0.20, -0.12, 2.42), 0.22, scala=(1.1, 0.7, 0.8))  # pettorali
    mb.palla((0, -0.06, 2.02), 0.24, scala=(1.1, 0.8, 1.0))             # addome
    for z in (2.18, 2.06, 1.94):                                        # addominali
        mb.simm("palla", (0.075, -0.18, z), 0.07)
    mb.palla((0, 0.05, 1.78), 0.27, scala=(1.25, 0.9, 0.8))             # bacino
    mb.palla((0, 0.15, 2.45), 0.33, scala=(1.3, 0.7, 0.9))              # dorso
    mb.simm("palla", (0.42, 0.06, 2.60), 0.23)                          # trapezi/spalle
    mb.capsula((0, 0.02, 2.62), (0, -0.02, 2.82), 0.15)                 # collo
    mb.simm("palla", (0.15, 0.06, 2.66), 0.15)                          # trapezio
    # --- testa: cranio, arcata sopraccigliare, muso/mascella ---
    mb.palla((0, -0.02, 3.00), 0.19, scala=(1.0, 1.1, 1.0))
    mb.capsula((-0.12, -0.18, 3.06), (0.12, -0.18, 3.06), 0.065)        # arcata
    mb.palla((0, -0.22, 2.90), 0.12, scala=(1.0, 1.2, 0.9))             # muso
    mb.capsula((-0.11, -0.13, 2.84), (0.11, -0.13, 2.84), 0.085)        # mascella
    mb.palla((0, -0.15, 2.78), 0.09)                                    # mento
    # --- braccia: deltoide, bicipite, avambraccio, pugno ---
    for sx, mano, gomito in ((-1, BALROG_MANO_D, Vector((-0.98, -0.02, 2.05))),
                             (1, BALROG_MANO_S, Vector((1.02, -0.12, 2.22)))):
        spalla = Vector((sx * 0.66, 0.04, 2.58))
        mb.palla(spalla, 0.22)
        mb.capsula(spalla, gomito, 0.15)
        mb.palla(spalla.lerp(gomito, 0.45) + Vector((0, -0.05, 0)), 0.15, scala=(1, 1, 1.15))
        mb.capsula(gomito, mano, 0.12)
        mb.palla(gomito.lerp(mano, 0.3), 0.14)
        mb.palla(mano, 0.13, scala=(1.0, 1.0, 1.1))
    # --- gambe digitigrade ---
    for sx in (-1, 1):
        anca = Vector((sx * 0.30, 0.05, 1.65))
        ginocchio = Vector((sx * 0.40, -0.30, 1.05))
        garretto = Vector((sx * 0.43, 0.22, 0.48))
        piede = Vector((sx * 0.45, -0.12, 0.10))
        mb.capsula(anca, ginocchio, 0.20)
        mb.palla(anca.lerp(ginocchio, 0.4) + Vector((0, -0.03, 0)), 0.24, scala=(1, 1, 1.2))  # coscia
        mb.palla(ginocchio, 0.15)
        mb.capsula(ginocchio, garretto, 0.12)
        mb.palla(ginocchio.lerp(garretto, 0.3) + Vector((0, 0.06, 0)), 0.15, scala=(1, 1, 1.2))  # polpaccio
        mb.capsula(garretto, piede, 0.09)
        mb.palla(piede + Vector((0, -0.05, 0)), 0.12, scala=(1.1, 1.4, 0.7))
    return mb.in_mesh("Corpo")


def balrog_artigli():
    parti = []
    for sx in (-1, 1):
        for k in (-1, 0, 1):
            b = Vector((sx * 0.45 + k * 0.07, -0.28, 0.06))
            parti.append(tubo("Artiglio", catmull([b, b + Vector((k * 0.02, -0.08, 0.0)),
                                                   b + Vector((k * 0.03, -0.14, -0.05))], 3),
                              lambda t: 0.035 * (1 - t) + 0.003, seg=8))
    return unisci("Artigli", parti)


def balrog_corna():
    parti = []
    for sx in (-1, 1):
        pts = [(sx * 0.12, -0.02, 3.10), (sx * 0.28, 0.04, 3.17), (sx * 0.46, 0.02, 3.17),
               (sx * 0.60, -0.08, 3.26), (sx * 0.64, -0.20, 3.40)]
        sp = catmull(pts, 8)
        parti.append(tubo("Corno", sp, lambda t: 0.085 * (1 - t) ** 0.9 + 0.006, seg=14,
                          forma=lambda t, a: 1 + 0.07 * max(0, math.sin(60 * t)) * (1 - t)))
        # corna secondarie piu' piccole
        pts2 = [(sx * 0.10, -0.10, 3.10), (sx * 0.17, -0.06, 3.20), (sx * 0.20, 0.02, 3.27)]
        parti.append(tubo("Corno2", catmull(pts2, 5), lambda t: 0.035 * (1 - t) + 0.004, seg=8))
    return unisci("Corna", parti)


def superficie_frontale(corpo, x, z):
    """Coordinata y della superficie del corpo vista da davanti (raggio da -Y verso +Y)."""
    ok, pos, _, _ = corpo.ray_cast(Vector((x, -3.0, z)), Vector((0, 1, 0)))
    return pos.y if ok else -0.25


def balrog_occhi(corpo):
    """Occhi incandescenti e bocca, appoggiati sulla superficie del viso."""
    parti = []
    for sx in (-1, 1):
        x, z = sx * 0.075, 3.0
        y = superficie_frontale(corpo, x, z)
        parti.append(sfera("Occhio", (x, y + 0.012, z), (0.045, 0.022, 0.02), 10, 6))
        # bagliore obliquo, occhi a mandorla inclinati verso il centro
        parti[-1].data.transform(Matrix.Translation((x, y, z)) @ Matrix.Rotation(sx * math.radians(-18), 4, "Y")
                                 @ Matrix.Translation((-x, -y, -z)))
    y = superficie_frontale(corpo, 0.0, 2.84)
    parti.append(sfera("Bocca", (0, y + 0.006, 2.84), (0.07, 0.02, 0.011), 10, 6))
    return unisci("Occhi", parti)


def balrog_ali():
    """Ali di pipistrello: ossa (dita) e membrana a pannelli con bordo smerlato."""
    ossa, membrane = [], []
    for sx in (-1, 1):
        attacco = Vector((sx * 0.28, 0.28, 2.55))
        polso = Vector((sx * 1.25, 0.75, 3.15))
        punte = [Vector((sx * 2.75, 1.05, 3.55)), Vector((sx * 3.05, 1.30, 2.75)),
                 Vector((sx * 2.75, 1.40, 1.90)), Vector((sx * 2.00, 1.25, 1.30))]
        radice = Vector((sx * 0.35, 0.32, 1.80))       # la membrana si attacca al fianco
        omero = catmull([attacco, attacco.lerp(polso, 0.5) + Vector((0, 0, 0.18)), polso], 6)
        ossa.append(tubo("Omero", omero, lambda t: 0.075 - 0.03 * t, seg=10))
        ossa.append(sfera("Polso", polso, (0.07, 0.07, 0.07), 10, 8))
        dita = []
        for i, p in enumerate(punte):
            medio = polso.lerp(p, 0.5) + Vector((0, 0.05, 0.12 - 0.05 * i))
            sp = catmull([polso, medio, p], 8)
            dita.append(sp)
            ossa.append(tubo("Dito", sp, lambda t: 0.04 * (1 - t) + 0.008, seg=8))
        # artiglio sul polso
        ossa.append(tubo("Unghia", catmull([polso, polso + Vector((sx * 0.05, -0.05, 0.15)),
                                             polso + Vector((sx * 0.0, -0.12, 0.22))], 3),
                         lambda t: 0.035 * (1 - t) + 0.003, seg=7))
        nu, nv = 10, 16
        # pannelli tra dita consecutive (escluso il primo tra omero e primo dito)
        for k in range(len(dita)):
            A = dita[k]
            if k + 1 < len(dita):
                B = dita[k + 1]
            else:
                # ultimo pannello: dall'ultimo dito al fianco del corpo
                B = catmull([polso.lerp(radice, 0.15), polso.lerp(radice, 0.6) + Vector((0, 0.10, 0)), radice],
                            8)
                B = [polso] + B[1:]

            def campiona(cat, s):
                f = s * (len(cat) - 1)
                i = min(int(f), len(cat) - 2)
                return cat[i].lerp(cat[i + 1], f - i)

            def pannello(u, v, A=A, B=B, k=k):
                a = campiona(A, v)
                b = campiona(B, v)
                p = a.lerp(b, u)
                arco = math.sin(math.pi * u)
                # bordo smerlato: verso la punta la membrana rientra verso il polso
                p = p.lerp(polso, 0.40 * arco * v ** 2.5)
                # gonfiore della membrana all'indietro (vento/aria calda)
                p += Vector((0, 0.18, 0)) * arco * math.sin(math.pi * min(v, 0.95)) * 0.8
                return p

            membrane.append(griglia("Membrana", nu, nv, pannello))
    membrana = unisci("Membrana", membrane)
    bm = bmesh.new()
    bm.from_mesh(membrana.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.002)
    bm.to_mesh(membrana.data)
    bm.free()
    modificatore(membrana, "SOLIDIFY", thickness=0.025, offset=0.0)
    applica_modificatori(membrana)
    normali_fuori(membrana)
    return unisci("Ossa", ossa), membrana


def balrog_frusta():
    """Frusta a piu' code nella mano destra: le code ricadono e serpeggiano a terra davanti."""
    parti = []
    m = BALROG_MANO_D
    manico = [m + Vector((0, 0.02, 0.16)), m + Vector((0, -0.02, -0.20))]
    parti.append(tubo("Manico", manico, lambda t: 0.045, seg=10))
    origine = manico[-1]
    for k in range(3):
        o = origine
        dx = (k - 1) * 0.22
        pts = [o, o + Vector((dx * 0.3, -0.12, -0.45)), o + Vector((dx * 0.6 + 0.05, -0.30, -0.95)),
               Vector((o.x + dx + 0.10, o.y - 0.55, 0.05))]
        terra = pts[-1]
        for j in range(1, 9):
            onda = math.sin(j * 1.25 + k * 1.1) * (0.22 - 0.015 * j)
            pts.append(terra + Vector((onda + 0.05 * j + dx * 0.25 * j, -0.12 * j, 0.0)))
        for p in pts[3:]:
            p.z = 0.035
        sp = catmull(pts, 9)
        parti.append(tubo("Coda", sp, lambda t: 0.034 * (1 - t) ** 0.7 + 0.007, seg=8,
                          forma=lambda t, a: 1 + 0.15 * math.sin(50 * t + a)))
    return unisci("Frusta", parti)


def balrog_spine():
    """Spine lungo la schiena e sui gomiti."""
    parti = []
    for i in range(6):
        z = 2.75 - i * 0.17
        b = Vector((0, 0.30 - 0.02 * i, z))
        parti.append(tubo("Spina", [b - Vector((0, 0.08, 0)), b + Vector((0, 0.10, 0.05)),
                                     b + Vector((0, 0.26 - 0.02 * i, 0.16 - 0.01 * i))],
                          lambda t: 0.05 * (1 - t) + 0.004, seg=8))
    for sx, gomito in ((-1, Vector((-0.98, -0.02, 2.05))), (1, Vector((1.02, -0.12, 2.22)))):
        b = gomito + Vector((sx * 0.05, 0.10, -0.02))
        parti.append(tubo("SpinaGomito", [b - Vector((sx * 0.05, 0.07, 0)), b + Vector((sx * 0.06, 0.18, -0.12))],
                          lambda t: 0.045 * (1 - t) + 0.004, seg=8))
    return unisci("Spine", parti)


def balrog_spada():
    """Spada fiammeggiante nella mano sinistra, puntata in alto e in avanti."""
    m = BALROG_MANO_S
    d = Vector((0.15, -0.45, 1.0)).normalized()
    lato = d.cross(Vector((0, -1, 0))).normalized()
    piatto = d.cross(lato).normalized()
    V, F = [], []
    sez = 14
    base = m + d * 0.12
    for i in range(sez + 1):
        t = i / sez
        p = base + d * (1.35 * t) + lato * 0.03 * math.sin(math.pi * t * 3) * (1 - t)  # lama ondulata
        w = 0.07 * (1 - t ** 2) + 0.003
        s = 0.018 * (1 - t) + 0.002
        V += [p + lato * w, p + piatto * s, p - lato * w, p - piatto * s]
    for i in range(sez):
        for j in range(4):
            a = i * 4 + j
            b = i * 4 + (j + 1) % 4
            F.append((a, b, b + 4, a + 4))
    F.append((0, 3, 2, 1))
    lama = mesh_da_dati("LamaBalrog", V, F)
    normali_fuori(lama)
    guardia = tubo("Guardia", catmull([m + d * 0.12 + lato * k * 0.18 + d * 0.06 * k * k for k in (-1, 0, 1)], 4),
                   lambda t: 0.03, seg=8)
    impugnatura = tubo("Impugnatura", [m - d * 0.2, m + d * 0.12], lambda t: 0.035, seg=8)
    return lama, unisci("ElsaBalrog", [guardia, impugnatura])


def costruisci_balrog():
    print("== Balrog ==")
    azzera_scena()
    t0 = time.time()
    corpo = balrog_corpo()
    print(f"   metaball -> mesh: {triangoli(corpo)} tri in {time.time() - t0:.1f}s")
    # superficie rocciosa a placche
    tx = texture_rumore("roccia", "VORONOI", 0.12)
    tx.distance_metric = "DISTANCE"
    modificatore(corpo, "DISPLACE", texture=tx, strength=-0.035, mid_level=0.5, texture_coords="OBJECT")
    tx2 = texture_rumore("roccia2", "CLOUDS", 0.05)
    modificatore(corpo, "DISPLACE", texture=tx2, strength=0.02, texture_coords="OBJECT")
    applica_modificatori(corpo)
    decima_a(corpo, 20000)
    liscia(corpo)
    artigli = unisci("Artigli", [balrog_artigli(), balrog_spine()])
    corna = balrog_corna()
    occhi = balrog_occhi(corpo)
    ossa, membrana = balrog_ali()
    frusta = balrog_frusta()
    lama, elsa = balrog_spada()
    for ob in (artigli, corna, ossa, membrana, frusta, elsa):
        liscia(ob)

    # ---- pelle: roccia carbonizzata con crepe di lava ----
    def crepe(N, scala=3.2):
        co = N.coord()
        dist = N.somma_vett(co, N.scala_vett(N.n("ShaderNodeTexNoise", i_Scale=2.5, i_Detail=3.0).outputs["Color"],
                                             0.35))
        vor = N.voronoi(dist, scala, "DISTANCE_TO_EDGE")
        d = vor.outputs["Distance"]
        # larghezza variabile delle crepe: in alcune zone si chiudono del tutto
        var = N.rumore(co, 1.8, 2.0)
        largh = N.mat("MAXIMUM", N.mat("MULTIPLY", N.mat("SUBTRACT", var, 0.38), 0.12), 0.0)
        m = N.mat("SUBTRACT", 1.0, N.mat("DIVIDE", d, N.mat("ADD", largh, 0.001)), clamp=True)
        vor2 = N.voronoi(dist, scala * 3.3, "DISTANCE_TO_EDGE")
        m2 = N.mat("SUBTRACT", 1.0, N.mat("DIVIDE", vor2.outputs["Distance"], 0.012), clamp=True)
        m2 = N.mat("MULTIPLY", m2, N.mat("GREATER_THAN", N.rumore(co, 1.2, 2.0), 0.58))
        return N.mat("MAXIMUM", m, N.mat("MULTIPLY", m2, 0.6))

    def colore_pelle(N):
        co = N.coord()
        roccia = N.rampa(N.rumore(co, 8.0, 6.0, 0.6), [(0.35, (0.012, 0.010, 0.010)),
                                                         (0.65, (0.06, 0.05, 0.045))])
        m = crepe(N)
        lava = N.rampa(m, [(0.0, (0.12, 0.02, 0.0)), (0.6, (0.7, 0.18, 0.01)), (1.0, (0.9, 0.5, 0.1))])
        return N.mix(N.mat("POWER", m, 0.8), roccia, lava)

    def emissione_pelle(N):
        m = crepe(N)
        lava = N.rampa(m, [(0.0, (0, 0, 0)), (0.3, (0.25, 0.03, 0.0)), (0.75, (0.9, 0.28, 0.02)),
                           (1.0, (1.0, 0.65, 0.2))])
        return lava

    def normale_pelle(N):
        m = crepe(N)
        h = N.mat("SUBTRACT", N.rumore(N.coord(), 12.0, 4.0), N.mat("MULTIPLY", m, 0.8))
        return h, 0.5

    finitura_cotta(corpo, "PelleBalrog", 1024, colore_pelle, rug=0.85, normale_fn=normale_pelle,
                   emissione_fn=emissione_pelle, forza_emissione=3.0)

    def corno_c(N):
        co = N.coord()
        sx, sy, sz = N.separa(co)
        anelli = N.rumore(N.combina(sx, sy, N.mat("MULTIPLY", sz, 1.0)), 25.0, 3.0)
        return N.rampa(anelli, [(0.3, (0.03, 0.025, 0.02)), (0.7, (0.14, 0.11, 0.08))])

    finitura_cotta(corna, "Corna", 256, corno_c, rug=0.6)

    def membrana_c(N):
        co = N.coord()
        ven = N.voronoi(co, 2.5, "DISTANCE_TO_EDGE").outputs["Distance"]
        v = N.mat("SUBTRACT", 1.0, N.mat("DIVIDE", ven, 0.018), clamp=True)
        v = N.mat("MULTIPLY", v, N.rumore(co, 1.5, 2.0))
        base = N.rampa(N.rumore(co, 6.0, 4.0), [(0.3, (0.025, 0.012, 0.01)), (0.7, (0.07, 0.03, 0.02))])
        return N.mix(N.mat("MULTIPLY", v, 0.6), base, (0.35, 0.06, 0.01))

    def membrana_e(N):
        co = N.coord()
        ven = N.voronoi(co, 2.5, "DISTANCE_TO_EDGE").outputs["Distance"]
        v = N.mat("SUBTRACT", 1.0, N.mat("DIVIDE", ven, 0.018), clamp=True)
        v = N.mat("MULTIPLY", v, N.rumore(co, 1.5, 2.0))
        return N.rampa(v, [(0.0, (0, 0, 0)), (0.6, (0.8, 0.16, 0.02))])

    finitura_cotta(membrana, "Ali", 1024, membrana_c, rug=0.7, emissione_fn=membrana_e, forza_emissione=1.0)

    assegna(ossa, materiale("OssaAli", (0.03, 0.025, 0.022), rug=0.75))
    assegna(artigli, materiale("Artigli", (0.02, 0.018, 0.016), rug=0.4))
    assegna(occhi, materiale("OcchiBalrog", (1.0, 0.7, 0.1), rug=0.3, emissione=(1.0, 0.65, 0.08),
                             forza_emissione=12.0))

    def frusta_c(N):
        f = N.rumore(N.coord(), 18.0, 3.0)
        return N.rampa(f, [(0.3, (0.18, 0.02, 0.0)), (0.7, (0.85, 0.28, 0.02))])

    finitura_cotta(frusta, "Frusta", 512, frusta_c, rug=0.6, emissione_fn=frusta_c, forza_emissione=1.6)

    def lama_c(N):
        f = N.rumore(N.coord(), 10.0, 4.0)
        return N.rampa(f, [(0.3, (0.45, 0.06, 0.0)), (0.7, (1.0, 0.42, 0.05))])

    finitura_cotta(lama, "SpadaFuoco", 256, lama_c, rug=0.4, emissione_fn=lama_c, forza_emissione=1.8)
    assegna(elsa, materiale("ElsaBalrog", (0.03, 0.025, 0.02), rug=0.5, metal=0.6))

    balrog = unisci("Balrog", [corpo, artigli, corna, occhi, ossa, membrana, frusta, lama, elsa])
    tri = decima_a(balrog, 35000)
    print(f"   triangoli Balrog: {tri}")
    if "--primo-piano" in sys.argv:
        anteprima("/tmp/primo_balrog.png", (0.9, -2.2, 3.0), (0, 0, 2.85), lente=50, dim=(500, 500))
    if "--retro" in sys.argv:
        anteprima("/tmp/retro_balrog.png", (-5, 6, 3), (0, 0, 2.0), lente=40, dim=(500, 500))
    anteprima(os.path.join(DIR_ANTEPRIME, "anteprima_balrog.png"), (4.6, -7.2, 2.6), (0, 0.3, 1.8),
              lente=45, luci=[("SUN", (4, -6, 8), 2.0, (1.0, 0.9, 0.85)),
                              ("SUN", (-6, 3, 3), 0.8, (0.6, 0.7, 1.0))])
    esporta(os.path.join(DIR_ASSET, "balrog.glb"), [balrog])


# ---------------------------------------------------------------------------
#  MODELLO 3 - IL PONTE DI KHAZAD-DUM
# ---------------------------------------------------------------------------
#  Asse del ponte = X; larghezza su Y (Blender) = Z (Godot); alto = Z (Blender) = Y (Godot).

PONTE_GRADINO = 0.34
PONTE_PEDATA = 1.15
PONTE_LARGHEZZA = 1.25


def quota_ponte(x):
    """Altezza della superficie calpestabile in funzione di x (simmetrica)."""
    a = abs(x)
    if a <= 1.825:
        return 5 * PONTE_GRADINO
    for k in range(4, -1, -1):
        c = 7.0 - k * PONTE_PEDATA
        if a <= c + 0.575:
            return PONTE_GRADINO * (k + 1)
    return 0.0


def profilo_ponte():
    """Contorno chiuso del ponte nel piano XZ (Blender), in senso antiorario."""
    # quote dei gradini (lato +x), dalla cima verso l'estremita'
    bordi = [1.825, 2.975, 4.125, 5.275, 6.425, 7.0]
    alto = []
    # sommita'
    alto.append((-1.825, 2.04))
    alto.append((1.825, 2.04))
    y = 2.04
    for i in range(len(bordi) - 1):
        x0, x1 = bordi[i], bordi[i + 1]
        y_basso = round(y - PONTE_GRADINO, 4)
        alto.append((x0, y_basso))
        alto.append((x1, y_basso))
        y = y_basso
    # da x=7.0 il ponte scende sotto il ciglio della rupe
    alto.append((7.0, -0.06))
    alto.append((7.4, -0.06))
    # intradosso: arco ellittico ribassato, sottile in cima e spesso alle estremita'
    sotto = []
    n = 60
    for i in range(n + 1):
        x = 7.4 - 14.8 * i / n
        t = abs(x) / 7.4
        y = 1.52 - 3.42 * (t ** 2.1)
        sotto.append((x, y))
    # contorno: lato sinistro (specchiato), cima e lato destro, poi l'intradosso da +x a -x
    meta_sx = [(-x, y) for (x, y) in reversed(alto[2:])]
    contorno = meta_sx + alto + sotto
    # rimuove duplicati consecutivi
    pulito = []
    for p in contorno:
        if not pulito or (abs(p[0] - pulito[-1][0]) > 1e-6 or abs(p[1] - pulito[-1][1]) > 1e-6):
            pulito.append(p)
    return pulito


def costruisci_ponte():
    print("== Ponte ==")
    azzera_scena()
    contorno = profilo_ponte()
    # prisma estruso lungo Y
    bm = bmesh.new()
    vf = [bm.verts.new((x, -PONTE_LARGHEZZA / 2, z)) for x, z in contorno]
    faccia = bm.faces.new(vf)
    bmesh.ops.triangulate(bm, faces=[faccia])
    ext = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])
    nuovi = [v for v in ext["geom"] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=nuovi, vec=(0, PONTE_LARGHEZZA, 0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("Ponte")
    bm.to_mesh(me)
    bm.free()
    ponte = collega(bpy.data.objects.new("Ponte", me))
    # leggera smussatura, poi rimesh voxel per una distribuzione uniforme dei vertici
    modificatore(ponte, "BEVEL", width=0.03, segments=2, limit_method="ANGLE")
    modificatore(ponte, "REMESH", mode="VOXEL", voxel_size=0.035, adaptivity=0.0)
    applica_modificatori(ponte)
    # scheggiature e usura: celle di voronoi soprattutto rientranti
    tx = texture_rumore("schegge", "VORONOI", 0.18)
    tx.distance_metric = "DISTANCE"
    modificatore(ponte, "DISPLACE", texture=tx, strength=0.03, mid_level=0.68, texture_coords="OBJECT")
    tx2 = texture_rumore("usura", "CLOUDS", 0.08)
    modificatore(ponte, "DISPLACE", texture=tx2, strength=0.012, mid_level=0.5, texture_coords="OBJECT")
    applica_modificatori(ponte)
    tri = decima_a(ponte, 24500)
    print(f"   triangoli Ponte: {tri}")
    liscia(ponte, math.radians(40))

    def mattoni(N, vett):
        b = N.n("ShaderNodeTexBrick", i_Scale=1.0, i_Mortar__Size=0.01, i_Bias=0.0,
                i_Brick__Width=0.85, i_Row__Height=0.32, offset=0.5, squash=1.0, squash_frequency=2)
        b.inputs["Color1"].default_value = (0.0, 0.0, 0.0, 1)
        b.inputs["Color2"].default_value = (1.0, 1.0, 1.0, 1)
        b.inputs["Mortar"].default_value = (1, 1, 1, 1)
        N.l(vett, b.inputs["Vector"])
        return b

    def triplanare(N, uscita):
        """Restituisce (valore lato, valore testa, valore piano) mescolati per normale."""
        co = N.coord()
        sx, sy, sz = N.separa(co)
        geo = N.n("ShaderNodeNewGeometry")
        nx, ny, nz = N.separa(geo.outputs["Normal"])
        lato = mattoni(N, N.combina(sx, sz, 0))
        testa = mattoni(N, N.combina(sy, sz, 0))
        piano = mattoni(N, N.combina(sx, N.mat("ADD", sy, 0.135), 0))
        a = N.mat("GREATER_THAN", N.mat("ABSOLUTE", nx), 0.75)
        c = N.mat("GREATER_THAN", N.mat("ABSOLUTE", nz), 0.7)
        r = N.mix(a, lato.outputs[uscita], testa.outputs[uscita])
        return N.mix(c, r, piano.outputs[uscita])

    def conci(N):
        """Ghiera dell'arco: conci radiali lungo l'intradosso sulle facce laterali.
        Restituisce (maschera della fascia, malta dei conci)."""
        co = N.coord()
        sx, sy, sz = N.separa(co)
        geo = N.n("ShaderNodeNewGeometry")
        nx, ny, nz = N.separa(geo.outputs["Normal"])
        ax = N.mat("ABSOLUTE", sx)
        t = N.mat("DIVIDE", ax, 7.4)
        f = N.mat("SUBTRACT", 1.52, N.mat("MULTIPLY", N.mat("POWER", t, 2.1), 3.42))
        # derivata dell'intradosso (con segno di x)
        der = N.mat("MULTIPLY", N.mat("MULTIPLY", N.mat("POWER", t, 1.1), -3.42 * 2.1 / 7.4),
                    N.mat("SIGN", sx))
        lung = N.mat("SQRT", N.mat("ADD", 1.0, N.mat("MULTIPLY", der, der)))
        d = N.mat("DIVIDE", N.mat("SUBTRACT", sz, f), lung)          # distanza normale dall'intradosso
        x0 = N.mat("ADD", sx, N.mat("DIVIDE", N.mat("MULTIPLY", d, der), lung))
        # ascissa curvilinea approssimata: integra la pendenza (x0 * lung)
        s = N.mat("MULTIPLY", x0, lung)
        giunto = N.mat("SUBTRACT", 1.0, N.mat("DIVIDE", N.mat("ABSOLUTE", N.mat("SUBTRACT",
                    N.mat("FRACT", N.mat("DIVIDE", s, 0.42)), 0.5)), 0.5))   # 1 al giunto
        giunto = N.mat("GREATER_THAN", giunto, 0.975)
        bordo = N.mat("LESS_THAN", N.mat("ABSOLUTE", N.mat("SUBTRACT", d, 0.45)), 0.012)
        dentro = N.mat("MULTIPLY", N.mat("LESS_THAN", d, 0.457), N.mat("GREATER_THAN", N.mat("ABSOLUTE", ny), 0.7))
        malta = N.mat("MAXIMUM", giunto, bordo)
        return dentro, malta

    def malta_tot(N):
        dentro, malta_c = conci(N)
        malta = triplanare(N, "Fac")
        return N.mix(dentro, malta, malta_c)

    def crepe(N):
        co = N.coord()
        dist = N.somma_vett(co, N.scala_vett(N.n("ShaderNodeTexNoise", i_Scale=2.0).outputs["Color"], 0.4))
        d = N.voronoi(dist, 1.6, "DISTANCE_TO_EDGE").outputs["Distance"]
        m = N.mat("SUBTRACT", 1.0, N.mat("DIVIDE", d, 0.012), clamp=True)
        return N.mat("MULTIPLY", m, N.mat("GREATER_THAN", N.rumore(co, 0.8, 2.0), 0.55))

    def colore(N):
        co = N.coord()
        sx, sy, sz = N.separa(co)
        malta = malta_tot(N)
        tono = triplanare(N, "Color")     # variazione per blocco (0..1)
        macchie = N.rumore(co, 3.0, 6.0, 0.6)
        grana = N.rumore(co, 40.0, 3.0, 0.5)
        f = N.mat("ADD", N.mat("MULTIPLY", tono, 0.25),
                  N.mat("ADD", N.mat("MULTIPLY", macchie, 0.55), N.mat("MULTIPLY", grana, 0.2)))
        pietra = N.rampa(f, [(0.25, (0.045, 0.045, 0.05)), (0.5, (0.10, 0.10, 0.105)), (0.8, (0.19, 0.185, 0.185))])
        # sporco/umidita' verso il basso
        basso = N.mat("SUBTRACT", 1.0, N.mat("MULTIPLY", N.mat("ADD", sz, 1.8), 0.45), clamp=True)
        pietra = N.mix(N.mat("MULTIPLY", basso, 0.6), pietra, (0.035, 0.035, 0.04))
        # la ghiera dell'arco e' leggermente piu' scura e uniforme
        dentro, _ = conci(N)
        pietra = N.mix(N.mat("MULTIPLY", dentro, 0.35), pietra, (0.05, 0.05, 0.055))
        pietra = N.mix(N.mat("MULTIPLY", malta, 0.7), pietra, (0.02, 0.02, 0.022))
        return N.mix(N.mat("MULTIPLY", crepe(N), 0.65), pietra, (0.01, 0.01, 0.01))

    def normale(N):
        malta = malta_tot(N)
        co = N.coord()
        h = N.mat("SUBTRACT", N.mat("MULTIPLY", N.rumore(co, 9.0, 5.0), 0.6), malta)
        h = N.mat("SUBTRACT", h, N.mat("MULTIPLY", crepe(N), 0.8))
        return h, 0.6

    finitura_cotta(ponte, "Pietra", 1024, colore, rug=0.92, normale_fn=normale)
    anteprima(os.path.join(DIR_ANTEPRIME, "anteprima_ponte.png"), (7.0, -12.0, 6.5), (0, 0, -0.1),
              lente=32, dim=(1000, 600))
    esporta(os.path.join(DIR_ASSET, "ponte.glb"), [ponte])


# ---------------------------------------------------------------------------
#  VERIFICA: re-importa i .glb e stampa i dati principali
# ---------------------------------------------------------------------------

def verifica():
    print("== Verifica ==")
    for nome in ("gandalf", "balrog", "ponte"):
        percorso = os.path.join(DIR_ASSET, nome + ".glb")
        if not os.path.exists(percorso):
            print(f" {nome}: MANCANTE")
            continue
        azzera_scena()
        bpy.ops.import_scene.gltf(filepath=percorso)
        mesh = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        tri = 0
        mn = Vector((1e9, 1e9, 1e9))
        mx = -mn
        for o in mesh:
            o.data.calc_loop_triangles()
            tri += len(o.data.loop_triangles)
            for v in o.data.vertices:
                w = o.matrix_world @ v.co
                g = Vector((w.x, w.z, -w.y))       # assi glTF/Godot
                mn = Vector(map(min, mn, g))
                mx = Vector(map(max, mx, g))
        mats = sorted({m.name for o in mesh for m in o.data.materials if m})
        imgs = [i for i in bpy.data.images if i.source != "VIEWER" and i.type == "IMAGE"]
        incorporate = all(i.packed_file is not None or not i.filepath for i in imgs)
        print(f" {nome}.glb: {os.path.getsize(percorso) / 1024:.0f} KB, triangoli {tri}")
        print(f"   bbox Godot min ({mn.x:.3f}, {mn.y:.3f}, {mn.z:.3f}) max ({mx.x:.3f}, {mx.y:.3f}, {mx.z:.3f})")
        print(f"   materiali: {', '.join(mats)}")
        # centro dei materiali notevoli (punti luce / prese) in assi Godot
        for o in mesh:
            for mi, m in enumerate(o.data.materials):
                if m and m.name in ("Cristallo", "OcchiBalrog"):
                    vs = {v for p in o.data.polygons if p.material_index == mi for v in p.vertices}
                    c = sum((o.matrix_world @ o.data.vertices[v].co for v in vs), Vector()) / max(1, len(vs))
                    print(f"   centro {m.name}: Godot ({c.x:.3f}, {c.z:.3f}, {-c.y:.3f})")
        print(f"   immagini: {len(imgs)} ({', '.join(f'{i.name} {i.size[0]}x{i.size[1]}' for i in imgs)}),"
              f" incorporate: {incorporate}")
        if nome == "ponte":
            dg = bpy.context.evaluated_depsgraph_get()
            for x, atteso in ((6.7, 0.34), (5.85, 0.68), (4.7, 1.02), (3.55, 1.36), (2.4, 1.70), (0.75, 2.04),
                              (-6.7, 0.34), (-4.7, 1.02), (-0.75, 2.04)):
                for zg in (0.0, 0.45, -0.45):
                    # Godot (x, y, z) -> Blender (x, -z, y); raggio verso il basso da y=5
                    ok, pos, *_ = bpy.context.scene.ray_cast(dg, Vector((x, -zg, 5.0)), Vector((0, 0, -1)))
                    h = pos.z if ok else float("nan")
                    stato = "OK" if ok and abs(h - atteso) <= 0.03 else "FUORI TOLLERANZA"
                    print(f"   x={x:+.2f} z={zg:+.2f}: quota {h:.3f} (attesa {atteso:.2f}) {stato}")


def main():
    os.makedirs(DIR_ASSET, exist_ok=True)
    os.makedirs(DIR_ANTEPRIME, exist_ok=True)
    scelte = [a for a in sys.argv[1:] if not a.startswith("--")] or ["tutti"]
    if "tutti" in scelte:
        scelte = ["gandalf", "balrog", "ponte", "verifica"]
    for s in scelte:
        {"gandalf": costruisci_gandalf, "balrog": costruisci_balrog,
         "ponte": costruisci_ponte, "verifica": verifica}[s]()


if __name__ == "__main__":
    main()
