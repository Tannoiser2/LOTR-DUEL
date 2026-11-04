## Il ponte di Khazad-dûm in 3D: abisso di fuoco, ponte a gradini, Gandalf e il Balrog con le loro luci,
## e gli effetti delle carte (fulmini di Gandalf, fiamme del Balrog, scintille quando i simboli si parano).
## Se esistono i modelli in assets/3d (gandalf.glb, balrog.glb, ponte.glb) li usa, altrimenti forme semplici.
class_name Scena3D
extends Node3D

const PASSO_X := 1.15
const PASSO_Y := 0.34
const COL_G := Color(0.75, 0.85, 1.0)
const COL_B := Color(1.0, 0.42, 0.08)

var cam: Camera3D
var perno: Node3D
var yaw := -0.12
var pitch := -0.22
var dist := 18.5
var trascina := false
var figure := {}
var luci := {}
var aure := {}
var bastone_luce: OmniLight3D
var fuoco_balrog: CPUParticles3D
var luce_abisso: OmniLight3D
var gradino := {"G": 0, "B": 0}
var scossa := 0.0
var t := 0.0
var auto_giro := true

func _ready() -> void:
	_ambiente()
	_abisso()
	_scogli()
	_ponte()
	_colonne()
	_figure()
	perno = Node3D.new()
	add_child(perno)
	cam = Camera3D.new()
	cam.fov = 48
	cam.far = 400
	perno.add_child(cam)
	_aggiorna_camera()

# ------------------------------------------------------------ costruzione

func _mat(col: Color, rough := 0.9, emiss := Color.BLACK, en := 0.0) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = col
	m.roughness = rough
	if en > 0.0:
		m.emission_enabled = true
		m.emission = emiss
		m.emission_energy_multiplier = en
	return m

func _mat_tex(path: String, col := Color.WHITE) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	if ResourceLoader.exists(path):
		m.albedo_texture = load(path)
	m.albedo_color = col
	m.roughness = 0.95
	return m

func _ambiente() -> void:
	var we := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.03, 0.012, 0.01)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.25, 0.22, 0.26)
	env.ambient_light_energy = 0.55
	env.glow_enabled = true
	env.glow_intensity = 1.1
	env.glow_bloom = 0.15
	env.glow_hdr_threshold = 1.3
	env.fog_enabled = true
	env.fog_light_color = Color(0.16, 0.07, 0.04)
	env.fog_density = 0.006
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	we.environment = env
	add_child(we)
	var sole := DirectionalLight3D.new()
	sole.light_color = Color(0.55, 0.6, 0.85)
	sole.light_energy = 0.5
	sole.rotation_degrees = Vector3(-55, 30, 0)
	add_child(sole)

func _abisso() -> void:
	# il fuoco in fondo all'abisso
	var lava := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(160, 160)
	lava.mesh = pm
	var ml := _mat(Color(0.3, 0.08, 0.02), 1.0, Color(0.8, 0.25, 0.04), 0.75)
	if ResourceLoader.exists("res://assets/3d/lava.webp"):
		ml.emission_texture = load("res://assets/3d/lava.webp")
		ml.albedo_texture = ml.emission_texture
		ml.uv1_scale = Vector3(5, 5, 1)
	lava.material_override = ml
	lava.position = Vector3(0, -34, 0)
	add_child(lava)
	luce_abisso = OmniLight3D.new()
	luce_abisso.light_color = Color(1.0, 0.4, 0.1)
	luce_abisso.light_energy = 3.2
	luce_abisso.omni_range = 46
	luce_abisso.omni_attenuation = 0.9
	luce_abisso.position = Vector3(0, -12, 0)
	add_child(luce_abisso)
	# braci che salgono dall'abisso
	var braci := CPUParticles3D.new()
	braci.amount = 260
	braci.lifetime = 7.0
	braci.preprocess = 7.0
	braci.emission_shape = CPUParticles3D.EMISSION_SHAPE_BOX
	braci.emission_box_extents = Vector3(20, 1, 7)
	braci.position = Vector3(0, -26, 0)
	braci.direction = Vector3(0, 1, 0)
	braci.spread = 18
	braci.initial_velocity_min = 3.0
	braci.initial_velocity_max = 6.5
	braci.gravity = Vector3(0, 0.6, 0)
	braci.scale_amount_min = 0.05
	braci.scale_amount_max = 0.16
	var q := QuadMesh.new()
	q.size = Vector2(1, 1)
	var mb := _mat(Color(1, 0.6, 0.2), 1.0, Color(1.0, 0.5, 0.1), 3.0)
	mb.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mb.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	mb.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mb.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	mb.vertex_color_use_as_albedo = true
	mb.albedo_texture = load("res://assets/3d/scintilla.png")
	q.material = mb
	braci.mesh = q
	var grad := Gradient.new()
	grad.set_color(0, Color(1, 0.8, 0.4, 1))
	grad.set_color(1, Color(1, 0.2, 0.0, 0))
	braci.color_ramp = grad
	add_child(braci)

func _scogli() -> void:
	# le due sponde dell'abisso, con sopra le metà del tabellone originale
	for lato in [-1, 1]:
		var s := MeshInstance3D.new()
		var bm := BoxMesh.new()
		bm.size = Vector3(14, 40, 18)
		s.mesh = bm
		s.material_override = _mat(Color(0.16, 0.13, 0.13), 1.0)
		s.position = Vector3(lato * 13.6, -20.05, 0)
		add_child(s)
		var top := MeshInstance3D.new()
		var pm := PlaneMesh.new()
		pm.size = Vector2(14, 18)
		top.mesh = pm
		var tex := "res://assets/3d/sponda_G.webp" if lato < 0 else "res://assets/3d/sponda_B.webp"
		top.material_override = _mat_tex(tex, Color(0.8, 0.78, 0.82))
		top.position = Vector3(lato * 13.6, 0.0, 0)
		top.rotation_degrees.y = 90 if lato < 0 else -90
		add_child(top)
		# il bordo frastagliato della sponda: blocchi di roccia che scendono nell'abisso
		var roccia := _mat(Color(0.2, 0.17, 0.17), 1.0)
		for k in 12:
			var r := MeshInstance3D.new()
			var bb := BoxMesh.new()
			bb.size = Vector3(1.2 + randf() * 1.4, 3.0 + randf() * 6.0, 1.4 + randf() * 1.0)
			r.mesh = bb
			r.material_override = roccia
			r.position = Vector3(lato * (6.8 + randf() * 0.5), -bb.size.y * 0.5 - 0.05, -8.5 + k * 1.55)
			r.rotation_degrees = Vector3(randf_range(-6, 6), randf_range(-25, 25), randf_range(-6, 6))
			add_child(r)

func _ponte() -> void:
	if ResourceLoader.exists("res://assets/3d/ponte.glb"):
		var p: Node3D = load("res://assets/3d/ponte.glb").instantiate()
		add_child(p)
		return
	var pietra := _mat(Color(0.42, 0.39, 0.4), 0.95)
	# arco sottile senza parapetti, con i gradini su ogni lato
	for lato in [-1, 1]:
		for k in range(1, 6):
			var g := MeshInstance3D.new()
			var bm := BoxMesh.new()
			bm.size = Vector3(PASSO_X, 0.34 + k * PASSO_Y, 1.25)
			g.mesh = bm
			g.material_override = pietra
			g.position = Vector3(lato * (7.0 - k * PASSO_X - PASSO_X * 0.5 + 0.0), (k * PASSO_Y) * 0.5 - 0.17 + 0.17, 0)
			add_child(g)
	var cima := MeshInstance3D.new()
	var bc := BoxMesh.new()
	bc.size = Vector3(0.6, 0.34 + 5 * PASSO_Y, 1.25)
	cima.mesh = bc
	cima.material_override = pietra
	cima.position = Vector3(0, 5 * PASSO_Y * 0.5, 0)
	add_child(cima)
	var arco := MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.top_radius = 7.4
	cm.bottom_radius = 7.4
	cm.height = 1.1
	cm.radial_segments = 48
	arco.mesh = cm
	arco.material_override = _mat(Color(0.3, 0.27, 0.28), 1.0)
	arco.rotation_degrees.x = 90
	arco.position = Vector3(0, -6.2, 0)
	arco.scale = Vector3(1, 1, 1)
	add_child(arco)

func _colonne() -> void:
	# le grandi colonne di Moria, nella penombra
	var m := _mat(Color(0.2, 0.17, 0.17), 1.0)
	for i in 10:
		for lato in [-1, 1]:
			var c := MeshInstance3D.new()
			var cm := CylinderMesh.new()
			cm.top_radius = 1.1
			cm.bottom_radius = 1.4
			cm.height = 70
			c.mesh = cm
			c.material_override = m
			c.position = Vector3(-40 + i * 9, -10, lato * (16 + (i % 3) * 3))
			add_child(c)

func _figure() -> void:
	figure["G"] = _carica_o("res://assets/3d/gandalf.glb", _gandalf_semplice)
	figure["B"] = _carica_o("res://assets/3d/balrog.glb", _balrog_semplice)
	for chi in ["G", "B"]:
		add_child(figure[chi])
		var ap := _trova_animatore(figure[chi])
		if ap:
			animatori[chi] = ap
			if ap.has_animation("riposo"):
				ap.get_animation("riposo").loop_mode = Animation.LOOP_LINEAR
				ap.play("riposo")
		figure[chi].position = pos_gradino(chi, 0)
		figure[chi].rotation.y = PI / 2 if chi == "G" else -PI / 2
	# la luce del bastone di Gandalf
	bastone_luce = OmniLight3D.new()
	bastone_luce.light_color = Color(0.8, 0.88, 1.0)
	bastone_luce.light_energy = 2.2
	bastone_luce.omni_range = 7
	var modelli := ResourceLoader.exists("res://assets/3d/gandalf.glb")
	bastone_luce.position = Vector3(0.2, 2.62, 0.22) if modelli else Vector3(0.0, 2.2, 0.35)
	_aggancia_a_osso(figure["G"], "mano_sx", bastone_luce)
	var punta := MeshInstance3D.new()
	var sm := SphereMesh.new()
	sm.radius = 0.09
	sm.height = 0.18
	punta.mesh = sm
	punta.material_override = _mat(Color.WHITE, 0.2, Color(0.85, 0.92, 1.0), 9.0)
	punta.position = bastone_luce.position
	if not modelli:
		figure["G"].add_child(punta)
	# il fuoco del Balrog
	var lb := OmniLight3D.new()
	lb.light_color = COL_B
	lb.light_energy = 3.0
	lb.omni_range = 8
	lb.position = Vector3(0, 1.8, 0)
	figure["B"].add_child(lb)
	luci["B"] = lb
	luci["G"] = bastone_luce
	fuoco_balrog = _fuoco(Vector3(0, 2.6, -0.6), 50, 0.8)
	figure["B"].add_child(fuoco_balrog)

var animatori := {}

## Animazioni previste nei modelli: riposo (ciclo), attacco, colpito, sali, caduta, vittoria.
func anima(chi: String, nome: String) -> void:
	var ap: AnimationPlayer = animatori.get(chi)
	if ap == null or not ap.has_animation(nome):
		return
	ap.play(nome, 0.15)
	if nome != "riposo" and nome != "caduta" and nome != "vittoria" and ap.has_animation("riposo"):
		ap.queue("riposo")

func _trova_animatore(n: Node) -> AnimationPlayer:
	if n is AnimationPlayer:
		return n
	for c in n.get_children():
		var a := _trova_animatore(c)
		if a:
			return a
	return null

## Mette il nodo (posizione data nello spazio della figura) su un osso dello scheletro, così segue le animazioni.
func _aggancia_a_osso(fig: Node3D, osso: String, nodo: Node3D) -> void:
	var sk := _trova_scheletro(fig)
	var idx := sk.find_bone(osso) if sk else -1
	if idx < 0:
		fig.add_child(nodo)
		return
	var att := BoneAttachment3D.new()
	att.bone_name = osso
	sk.add_child(att)
	# posizione nello spazio dello scheletro, poi relativa all'osso in posa di riposo
	var in_sk: Vector3 = sk.transform.affine_inverse() * _locale_a(fig, sk) * nodo.position
	nodo.position = sk.get_bone_global_rest(idx).affine_inverse() * in_sk
	att.add_child(nodo)

## Trasformazione dallo spazio della figura allo spazio del genitore dello scheletro.
func _locale_a(fig: Node3D, sk: Node3D) -> Transform3D:
	var t := Transform3D.IDENTITY
	var n: Node = sk.get_parent()
	var catena := []
	while n != null and n != fig:
		catena.push_front(n)
		n = n.get_parent()
	for c in catena:
		if c is Node3D:
			t = t * (c as Node3D).transform
	return t.affine_inverse()

func _trova_scheletro(n: Node) -> Skeleton3D:
	if n is Skeleton3D:
		return n
	for c in n.get_children():
		var k := _trova_scheletro(c)
		if k:
			return k
	return null

func _carica_o(path: String, ripiego: Callable) -> Node3D:
	if ResourceLoader.exists(path):
		return load(path).instantiate()
	return ripiego.call()

func _gandalf_semplice() -> Node3D:
	var n := Node3D.new()
	var veste := MeshInstance3D.new()
	var cm := CylinderMesh.new()
	cm.top_radius = 0.16
	cm.bottom_radius = 0.42
	cm.height = 1.45
	veste.mesh = cm
	veste.material_override = _mat(Color(0.62, 0.64, 0.68), 0.9)
	veste.position.y = 0.72
	n.add_child(veste)
	var testa := MeshInstance3D.new()
	var sm := SphereMesh.new()
	sm.radius = 0.17
	sm.height = 0.34
	testa.mesh = sm
	testa.material_override = _mat(Color(0.86, 0.76, 0.68))
	testa.position.y = 1.58
	n.add_child(testa)
	var barba := MeshInstance3D.new()
	var bm := PrismMesh.new()
	bm.size = Vector3(0.26, 0.5, 0.12)
	barba.mesh = bm
	barba.material_override = _mat(Color(0.92, 0.92, 0.94))
	barba.position = Vector3(0, 1.32, 0.13)
	barba.rotation_degrees.z = 180
	n.add_child(barba)
	var cappello := MeshInstance3D.new()
	var cc := CylinderMesh.new()
	cc.top_radius = 0.0
	cc.bottom_radius = 0.24
	cc.height = 0.55
	cappello.mesh = cc
	cappello.material_override = _mat(Color(0.5, 0.52, 0.56))
	cappello.position.y = 1.9
	cappello.rotation_degrees.x = -12
	n.add_child(cappello)
	var bastone := MeshInstance3D.new()
	var bc := CylinderMesh.new()
	bc.top_radius = 0.03
	bc.bottom_radius = 0.03
	bc.height = 2.2
	bastone.mesh = bc
	bastone.material_override = _mat(Color(0.35, 0.25, 0.16))
	bastone.position = Vector3(0.0, 1.1, 0.35)
	n.add_child(bastone)
	return n

func _balrog_semplice() -> Node3D:
	var n := Node3D.new()
	var nero := _mat(Color(0.08, 0.05, 0.05), 0.8, Color(0.6, 0.1, 0.0), 0.4)
	var corpo := MeshInstance3D.new()
	var cm := CapsuleMesh.new()
	cm.radius = 0.55
	cm.height = 2.4
	corpo.mesh = cm
	corpo.material_override = nero
	corpo.position.y = 1.4
	n.add_child(corpo)
	var testa := MeshInstance3D.new()
	var sm := SphereMesh.new()
	sm.radius = 0.36
	sm.height = 0.6
	testa.mesh = sm
	testa.material_override = nero
	testa.position = Vector3(0, 2.85, 0.15)
	n.add_child(testa)
	for l in [-1, 1]:
		var corno := MeshInstance3D.new()
		var c := CylinderMesh.new()
		c.top_radius = 0.0
		c.bottom_radius = 0.08
		c.height = 0.6
		corno.mesh = c
		corno.material_override = nero
		corno.position = Vector3(l * 0.25, 3.15, 0.05)
		corno.rotation_degrees = Vector3(-20, 0, l * -35)
		n.add_child(corno)
		var ala := MeshInstance3D.new()
		var am := PrismMesh.new()
		am.size = Vector3(2.6, 2.0, 0.05)
		ala.mesh = am
		var ma := _mat(Color(0.06, 0.03, 0.03), 0.9)
		ma.cull_mode = BaseMaterial3D.CULL_DISABLED
		ala.material_override = ma
		ala.position = Vector3(l * 1.3, 2.4, -0.35)
		ala.rotation_degrees = Vector3(0, l * 20, l * -20)
		n.add_child(ala)
		var occhio := MeshInstance3D.new()
		var os := SphereMesh.new()
		os.radius = 0.05
		os.height = 0.1
		occhio.mesh = os
		occhio.material_override = _mat(Color(1, 0.7, 0.2), 0.3, Color(1, 0.5, 0.0), 12.0)
		occhio.position = Vector3(l * 0.13, 2.92, 0.46)
		n.add_child(occhio)
	n.scale = Vector3(1.15, 1.15, 1.15)
	return n

func _fuoco(pos: Vector3, quanti: int, raggio: float) -> CPUParticles3D:
	var p := CPUParticles3D.new()
	p.amount = quanti
	p.lifetime = 0.9
	p.position = pos
	p.emission_shape = CPUParticles3D.EMISSION_SHAPE_SPHERE
	p.emission_sphere_radius = raggio
	p.direction = Vector3(0, 1, 0)
	p.spread = 25
	p.initial_velocity_min = 0.6
	p.initial_velocity_max = 1.8
	p.gravity = Vector3(0, 1.8, 0)
	p.scale_amount_min = 0.25
	p.scale_amount_max = 0.6
	var q := QuadMesh.new()
	var m := _mat(Color(1, 0.5, 0.1), 1.0, Color(1.0, 0.35, 0.05), 4.0)
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	m.vertex_color_use_as_albedo = true
	if ResourceLoader.exists("res://assets/3d/fiamma.png"):
		m.albedo_texture = load("res://assets/3d/fiamma.png")
	q.material = m
	p.mesh = q
	var g := Gradient.new()
	g.set_color(0, Color(1, 0.75, 0.3, 0.9))
	g.add_point(0.5, Color(1, 0.3, 0.05, 0.6))
	g.set_color(g.get_point_count() - 1, Color(0.3, 0.05, 0.0, 0.0))
	p.color_ramp = g
	var c := Curve.new()
	c.add_point(Vector2(0, 0.6))
	c.add_point(Vector2(0.4, 1.0))
	c.add_point(Vector2(1, 0.1))
	p.scale_amount_curve = c
	return p

# ------------------------------------------------------------ posizione delle figure

func pos_gradino(chi: String, k: int) -> Vector3:
	var lato := -1.0 if chi == "G" else 1.0
	if k <= 0:
		return Vector3(lato * 8.6, 0.0, 0)
	var x := 7.0 - k * PASSO_X
	if k == 5:
		x = 0.75
	return Vector3(lato * x, 0.34 + k * PASSO_Y, 0)

func metti_figure(fg: int, fb: int) -> void:
	gradino = {"G": fg, "B": fb}
	figure["G"].position = pos_gradino("G", fg)
	figure["B"].position = pos_gradino("B", fb)

## La figura sale i gradini uno alla volta.
func sali(chi: String, da: int, a: int) -> void:
	gradino[chi] = a
	anima(chi, "sali")
	var tw := create_tween()
	var prima := pos_gradino(chi, da)
	for k in range(da + 1, a + 1):
		var p := pos_gradino(chi, k)
		tw.tween_property(figure[chi], "position", (prima + p) * 0.5 + Vector3(0, 0.45, 0), 0.2)
		tw.tween_property(figure[chi], "position", p, 0.2)
		prima = p
	tw.tween_callback(func(): _lampo(chi, 2.5))

# ------------------------------------------------------------ effetti

func _process(delta: float) -> void:
	t += delta
	if auto_giro and not trascina:
		yaw += delta * 0.025
	if scossa > 0.0:
		scossa = max(0.0, scossa - delta * 2.5)
	_aggiorna_camera()
	luce_abisso.light_energy = 3.0 + sin(t * 1.7) * 0.4 + sin(t * 4.3) * 0.2
	if is_instance_valid(bastone_luce):
		bastone_luce.light_energy = lerp(bastone_luce.light_energy, 2.2 + sin(t * 3.0) * 0.15, delta * 3.0)
	if luci.has("B"):
		luci["B"].light_energy = lerp(luci["B"].light_energy, 3.0 + sin(t * 9.0) * 0.5, delta * 4.0)

func _aggiorna_camera() -> void:
	if cam == null:
		return
	pitch = clamp(pitch, -1.25, 0.15)
	dist = clamp(dist, 6.0, 30.0)
	var centro := Vector3(0, 1.4, 0)
	var dir := Vector3(sin(yaw) * cos(pitch), -sin(pitch), cos(yaw) * cos(pitch))
	var j := Vector3.ZERO
	if scossa > 0.0:
		j = Vector3(randf_range(-1, 1), randf_range(-1, 1), randf_range(-1, 1)) * scossa * 0.18
	cam.position = centro + dir * dist + j
	cam.look_at(centro + j * 0.5, Vector3.UP)

func _unhandled_input(ev: InputEvent) -> void:
	if ev is InputEventMouseButton:
		if ev.button_index == MOUSE_BUTTON_LEFT or ev.button_index == MOUSE_BUTTON_RIGHT:
			trascina = ev.pressed
			if ev.pressed:
				auto_giro = false
		elif ev.button_index == MOUSE_BUTTON_WHEEL_UP and ev.pressed:
			dist -= 0.8
		elif ev.button_index == MOUSE_BUTTON_WHEEL_DOWN and ev.pressed:
			dist += 0.8
	elif ev is InputEventMouseMotion and trascina:
		yaw -= ev.relative.x * 0.006
		pitch -= ev.relative.y * 0.005
	elif ev is InputEventMagnifyGesture:
		dist /= ev.factor

func visuale(n: int) -> void:
	auto_giro = false
	match n:
		0:
			yaw = -0.12
			pitch = -0.22
			dist = 18.5
		1:
			yaw = -PI / 2 + 0.2
			pitch = -0.18
			dist = 11
		2:
			yaw = PI / 2 - 0.2
			pitch = -0.18
			dist = 11
		3:
			yaw = 0.0
			pitch = -1.15
			dist = 20

func _lampo(chi: String, forza := 4.0) -> void:
	var l: OmniLight3D = luci[chi]
	l.light_energy = forza * 3.0

func _testa(chi: String) -> Vector3:
	var f: Node3D = figure[chi]
	return f.global_position + Vector3(0, 2.1 if chi == "G" else 2.6, 0)

## Una carta giocata: il bagliore di chi la gioca.
func carta_giocata(chi: String) -> void:
	_lampo(chi, 3.0)
	anima(chi, "attacco")
	if chi == "B":
		var b := _fuoco(Vector3(0, 1.6, 0), 60, 0.9)
		b.one_shot = true
		b.explosiveness = 0.8
		b.initial_velocity_max = 4.0
		figure["B"].add_child(b)
		b.emitting = true
		get_tree().create_timer(2.0).timeout.connect(b.queue_free)

## Le righe dello scambio: colpi che vanno a segno e simboli che si parano.
func scambio(attaccante: String, difensore: String, subiti: Array, inflitti: Array, parati: Array) -> void:
	var ritardo := 0.0
	for r in subiti:
		_colpo(attaccante, difensore, r, ritardo)
		ritardo += 0.18
	for r in inflitti:
		_colpo(difensore, attaccante, r, ritardo)
		ritardo += 0.18
	for r in parati:
		_scintille(r, ritardo)
		ritardo += 0.12

func _colpo(da: String, a: String, riga: int, ritardo: float) -> void:
	await get_tree().create_timer(ritardo).timeout
	var p0 := _testa(da) + Vector3(0, 0.3 - riga * 0.25, 0)
	var p1 := _testa(a) + Vector3(0, -0.4 - riga * 0.2, 0)
	if da == "G":
		_fulmine(p0, p1, COL_G)
	else:
		_palla_fuoco(p0, p1)
	await get_tree().create_timer(0.3).timeout
	_lampo(a, 5.0)
	anima(a, "colpito")
	scossa = min(1.0, scossa + 0.35)
	var ferita := _fuoco(figure[a].to_local(p1), 30, 0.3) if a == "B" else _scintille_su(p1, COL_G)
	if a == "B":
		ferita.one_shot = true
		ferita.explosiveness = 0.9
		figure[a].add_child(ferita)
		ferita.emitting = true
		get_tree().create_timer(1.5).timeout.connect(ferita.queue_free)

func _fulmine(p0: Vector3, p1: Vector3, col: Color) -> void:
	var mi := MeshInstance3D.new()
	var im := ImmediateMesh.new()
	mi.mesh = im
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.albedo_color = col
	m.emission_enabled = true
	m.emission = col
	m.emission_energy_multiplier = 8.0
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mi.material_override = m
	add_child(mi)
	var dirs := (p1 - p0)
	var lato := dirs.cross(Vector3.UP).normalized()
	for ramo in 3:
		im.surface_begin(Mesh.PRIMITIVE_TRIANGLES)
		var prev := p0
		var n := 10
		for i in range(1, n + 1):
			var f := float(i) / n
			var q := p0 + dirs * f
			if i < n:
				q += Vector3(0, randf_range(-0.35, 0.35), 0) + lato * randf_range(-0.35, 0.35)
			var w := 0.05 if ramo == 0 else 0.02
			var off := Vector3(0, w, 0)
			im.surface_add_vertex(prev - off)
			im.surface_add_vertex(prev + off)
			im.surface_add_vertex(q + off)
			im.surface_add_vertex(prev - off)
			im.surface_add_vertex(q + off)
			im.surface_add_vertex(q - off)
			prev = q
		im.surface_end()
	var luce := OmniLight3D.new()
	luce.light_color = col
	luce.light_energy = 6.0
	luce.omni_range = 9
	luce.position = (p0 + p1) * 0.5
	add_child(luce)
	var tw := create_tween()
	tw.tween_property(m, "albedo_color:a", 0.0, 0.45)
	tw.parallel().tween_property(luce, "light_energy", 0.0, 0.45)
	tw.tween_callback(func(): mi.queue_free(); luce.queue_free())

func _palla_fuoco(p0: Vector3, p1: Vector3) -> void:
	var n := Node3D.new()
	add_child(n)
	n.position = p0
	var f := _fuoco(Vector3.ZERO, 70, 0.22)
	f.lifetime = 0.35
	f.local_coords = false
	n.add_child(f)
	var l := OmniLight3D.new()
	l.light_color = COL_B
	l.light_energy = 5.0
	l.omni_range = 6
	n.add_child(l)
	var tw := create_tween()
	tw.tween_property(n, "position", p1, 0.32).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	tw.tween_callback(func(): f.emitting = false)
	tw.tween_property(l, "light_energy", 0.0, 0.3)
	tw.tween_callback(n.queue_free)

func _scintille(riga: int, ritardo: float) -> void:
	await get_tree().create_timer(ritardo).timeout
	var c := (_testa("G") + _testa("B")) * 0.5 + Vector3(0, 0.3 - riga * 0.25, 0)
	_scintille_su(c, Color(1.0, 0.85, 0.55))

func _scintille_su(p: Vector3, col: Color) -> CPUParticles3D:
	var s := CPUParticles3D.new()
	s.amount = 40
	s.lifetime = 0.6
	s.one_shot = true
	s.explosiveness = 1.0
	s.direction = Vector3(0, 1, 0)
	s.spread = 180
	s.initial_velocity_min = 2
	s.initial_velocity_max = 5
	s.gravity = Vector3(0, -6, 0)
	s.scale_amount_min = 0.03
	s.scale_amount_max = 0.07
	var q := QuadMesh.new()
	var m := _mat(col, 1.0, col, 8.0)
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	m.albedo_texture = load("res://assets/3d/scintilla.png")
	q.material = m
	s.mesh = q
	s.position = p
	add_child(s)
	s.emitting = true
	var l := OmniLight3D.new()
	l.light_color = col
	l.light_energy = 4
	l.omni_range = 4
	l.position = p
	add_child(l)
	var tw := create_tween()
	tw.tween_property(l, "light_energy", 0.0, 0.5)
	get_tree().create_timer(1.2).timeout.connect(func(): s.queue_free(); l.queue_free())
	return s

## Effetto visivo di una carta speciale.
func speciale(spec: String) -> void:
	match spec:
		"specchio":
			_scudo(COL_G)
		"equilibrio", "magia", "astuzia", "incantesimo":
			_anello("G", Color(0.6, 0.75, 1.0) if spec != "magia" else Color(0.5, 0.65, 1.0))
		"ira":
			_anello("G", Color(1, 1, 1))
			scossa = 1.0
		"potenza", "forza", "inganno":
			_vampata()
		"difesa":
			_muro_fuoco()
		"frusta":
			_frusta()

func _anello(chi: String, col: Color) -> void:
	var mi := MeshInstance3D.new()
	var tm := TorusMesh.new()
	tm.inner_radius = 0.5
	tm.outer_radius = 0.6
	mi.mesh = tm
	var m := _mat(col, 1.0, col, 6.0)
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mi.material_override = m
	mi.position = figure[chi].position + Vector3(0, 0.2, 0)
	add_child(mi)
	_lampo(chi, 6.0)
	var tw := create_tween()
	tw.tween_property(mi, "scale", Vector3(5, 1, 5), 0.9).set_ease(Tween.EASE_OUT)
	tw.parallel().tween_property(mi, "position:y", mi.position.y + 1.6, 0.9)
	tw.parallel().tween_property(m, "albedo_color:a", 0.0, 0.9)
	tw.tween_callback(mi.queue_free)

func _scudo(col: Color) -> void:
	var mi := MeshInstance3D.new()
	var sm := SphereMesh.new()
	sm.radius = 1.3
	sm.height = 2.6
	mi.mesh = sm
	var m := _mat(col, 0.0, col, 3.0)
	m.metallic = 1.0
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.albedo_color.a = 0.35
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	mi.material_override = m
	mi.position = figure["G"].position + Vector3(0, 1.2, 0)
	mi.scale = Vector3(0.1, 0.1, 0.1)
	add_child(mi)
	_lampo("G", 8.0)
	var tw := create_tween()
	tw.tween_property(mi, "scale", Vector3(1, 1.2, 1), 0.35).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tw.tween_interval(0.5)
	tw.tween_callback(func(): _palla_fuoco(_testa("G"), _testa("B")))
	tw.tween_property(m, "albedo_color:a", 0.0, 0.6)
	tw.tween_callback(mi.queue_free)

func _vampata() -> void:
	var f := _fuoco(Vector3(0, 1.6, 0), 200, 1.4)
	f.one_shot = true
	f.explosiveness = 0.6
	f.initial_velocity_max = 5.0
	f.scale_amount_max = 1.1
	figure["B"].add_child(f)
	f.emitting = true
	_lampo("B", 9.0)
	scossa = 0.8
	var tw := create_tween()
	tw.tween_property(figure["B"], "scale", figure["B"].scale * 1.25, 0.25)
	tw.tween_property(figure["B"], "scale", figure["B"].scale, 0.5)
	get_tree().create_timer(2.5).timeout.connect(f.queue_free)

func _muro_fuoco() -> void:
	var f := _fuoco(Vector3(-1.2, 0.6, 0), 220, 1.0)
	f.emission_shape = CPUParticles3D.EMISSION_SHAPE_BOX
	f.emission_box_extents = Vector3(0.15, 0.6, 1.4)
	f.one_shot = true
	f.explosiveness = 0.3
	f.lifetime = 1.3
	figure["B"].add_child(f)
	f.emitting = true
	_lampo("B", 7.0)
	get_tree().create_timer(3.0).timeout.connect(f.queue_free)

func _frusta() -> void:
	var p0: Vector3 = figure["B"].global_position + Vector3(-0.6, 2.0, 0.4)
	var p1: Vector3 = figure["G"].global_position + Vector3(0, 0.3, 0)
	var n := 14
	for i in n:
		var f := float(i) / (n - 1)
		var q: Vector3 = p0.lerp(p1, f) + Vector3(0, sin(f * PI) * 1.6, sin(f * PI * 2.0) * 0.5)
		var s := _fuoco(q, 10, 0.08)
		s.one_shot = true
		s.explosiveness = 1.0
		s.lifetime = 0.5
		add_child(s)
		get_tree().create_timer(i * 0.025).timeout.connect(func(): s.emitting = true)
		get_tree().create_timer(1.5).timeout.connect(s.queue_free)
	_lampo("B", 6.0)
	scossa = 0.6

## Fine partita: il ponte si spezza sotto lo sconfitto, che precipita nell'abisso.
func caduta(perdente: String) -> void:
	var f: Node3D = figure[perdente]
	anima(perdente, "caduta")
	anima(Motore.altro(perdente), "vittoria")
	var tw := create_tween()
	tw.tween_interval(0.6)
	tw.tween_property(f, "position", f.position + Vector3(0, 0.3, 0), 0.25)
	tw.tween_property(f, "position", f.position + Vector3(0, -38, 0), 2.2).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	tw.parallel().tween_property(f, "rotation:z", f.rotation.z + 2.5, 2.2)
	scossa = 1.0
	var vinc := Motore.altro(perdente)
	_lampo(vinc, 10.0)
