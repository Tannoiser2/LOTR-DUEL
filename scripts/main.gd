## Menu, tavolo di gioco e interfaccia di Il Signore degli Anelli – Il Duello.
## Modi: contro il computer, due giocatori sullo stesso dispositivo, online (Firebase).
## La partita si ricostruisce sempre da seme + elenco delle decisioni: così funzionano salvataggi e online.
extends Node

const SALVA_LOCALE := "user://partita_lotrduel.json"
const CW := 108.0   # larghezza carta in mano
const CH := 167.0
const BARRA := 196.0   # larghezza della barra di stato a destra
const COL_ORO := Color(0.93, 0.8, 0.5)
const COL_G := Color(0.78, 0.86, 1.0)
const COL_B := Color(1.0, 0.5, 0.2)
const COL_TESTO := Color(0.94, 0.9, 0.84)

var F_TITOLO: Font
var F_DECO: Font
var F_TESTO: Font
var F_CORSIVO: Font

var scena: Scena3D
var ui: CanvasLayer
var radice: Control
var net: Rete

# partita
var st := {}
var decisioni := []
var seme := 0
var modo := ""          # "ia", "locale", "online"
var io := "G"           # il ruolo di chi guarda lo schermo
var livello := 1
var ia: IA
var in_partita := false
var occupato := 0.0     # secondi di animazione ancora da attendere
var mostrata := -1      # numero della decisione di cui si mostra la richiesta
var attesa_ia := 0.0
var passaggio := ""     # gioco locale: a chi va passato il dispositivo
var selezione := []     # carte scelte per il finale
var codice := ""
var aspetto_rete := false
var ultimo_salvataggio := 0.0
var nomi := {"G": "Gandalf", "B": "Balrog"}

# nodi dell'interfaccia di gioco
var tavolo: Control
var box_mano: Control
var box_avv: Control
var box_riga: Control
var lbl_titolo: Label
var lbl_msg: Label
var lbl_ponte: Label
var traccia: Control
var diario: RichTextLabel
var dialogo: Control
var popup_scambio: Control
var banner: Label
var pannello_riserve: Label
var lbl_incantata: Control
var finestra_diario: Control
# fila delle carte giocate: carta con lo spazio davanti (scambio in corso) e carta in volo
var gap_idx := -1
var vola_idx := -1
var vola_da := Vector2.ZERO
var riga_lay := {}
# telefoni: ruolo -> {uid, nome}
var telefoni: Telefoni
var tel := {}
var finestra_tel: Control
var lista_tel: Label
var box_scoperte: Control
var mano_sinistra := 0.0
var mano_destra := 0.0
var lbl_ultimo: Label

func _ready() -> void:
	randomize()
	F_TITOLO = _font("Cinzel.ttf", 700)
	F_DECO = load("res://assets/font/CinzelDecorative-Bold.ttf")
	F_TESTO = _font("EBGaramond.ttf", 500)
	F_CORSIVO = load("res://assets/font/EBGaramond-Italic.ttf")
	net = Rete.new()
	add_child(net)
	telefoni = Telefoni.new()
	add_child(telefoni)
	telefoni.evento.connect(_evento_telefono)
	scena = Scena3D.new()
	add_child(scena)
	ui = CanvasLayer.new()
	add_child(ui)
	radice = Control.new()
	radice.set_anchors_preset(Control.PRESET_FULL_RECT)
	radice.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ui.add_child(radice)
	var th := Theme.new()
	th.default_font = F_TESTO
	th.default_font_size = 19
	radice.theme = th
	if OS.get_environment("LOTR_TEST") != "":
		return
	mostra_menu()

func _font(nome: String, peso: int) -> Font:
	var base: FontFile = load("res://assets/font/" + nome)
	var fv := FontVariation.new()
	fv.base_font = base
	fv.variation_opentype = {TextServerManager.get_primary_interface().name_to_tag("wght"): peso}
	return fv

# ============================================================ elementi di interfaccia

func etichetta(testo: String, f: Font = null, size := 19, col := COL_TESTO) -> Label:
	var l := Label.new()
	l.text = testo
	l.add_theme_font_override("font", f if f else F_TESTO)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", col)
	l.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.8))
	l.add_theme_constant_override("shadow_offset_x", 1)
	l.add_theme_constant_override("shadow_offset_y", 2)
	return l

func stile(col: Color, bordo: Color, r := 10, w := 2) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = col
	s.border_color = bordo
	s.set_border_width_all(w)
	s.set_corner_radius_all(r)
	s.content_margin_left = 14
	s.content_margin_right = 14
	s.content_margin_top = 8
	s.content_margin_bottom = 8
	s.shadow_color = Color(0, 0, 0, 0.5)
	s.shadow_size = 6
	return s

func bottone(testo: String, cb: Callable, col := Color(0.24, 0.12, 0.08), size := 19) -> Button:
	var b := Button.new()
	b.text = testo
	b.add_theme_font_override("font", F_TITOLO)
	b.add_theme_font_size_override("font_size", size)
	b.add_theme_color_override("font_color", COL_ORO)
	b.add_theme_color_override("font_hover_color", Color(1, 0.95, 0.8))
	b.add_theme_stylebox_override("normal", stile(col, Color(0.62, 0.47, 0.22)))
	b.add_theme_stylebox_override("hover", stile(col.lightened(0.15), Color(0.95, 0.75, 0.35)))
	b.add_theme_stylebox_override("pressed", stile(col.darkened(0.2), Color(0.95, 0.75, 0.35)))
	b.add_theme_stylebox_override("focus", StyleBoxEmpty.new())
	b.add_theme_stylebox_override("disabled", stile(Color(0.15, 0.13, 0.12), Color(0.3, 0.27, 0.24)))
	b.pressed.connect(cb)
	return b

func pannello(col := Color(0.06, 0.03, 0.03, 0.88)) -> PanelContainer:
	var p := PanelContainer.new()
	p.add_theme_stylebox_override("panel", stile(col, Color(0.6, 0.45, 0.2), 14, 2))
	return p

func svuota(n: Node) -> void:
	for c in n.get_children():
		c.queue_free()

func tex_carta(id: int) -> Texture2D:
	return load("res://assets/carte/%d.webp" % id)

func tex_dorso(chi: String) -> Texture2D:
	return load("res://assets/carte/dorso_%s.webp" % chi)

func immagine_carta(tex: Texture2D, w: float, h: float) -> TextureRect:
	var t := TextureRect.new()
	t.texture = tex
	t.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	t.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	t.custom_minimum_size = Vector2(w, h)
	t.size = Vector2(w, h)
	return t

# ============================================================ menu

func mostra_menu() -> void:
	in_partita = false
	svuota(radice)
	scena.spostamento_px = 0.0
	scena.auto_giro = true
	scena.metti_figure(0, 0)
	var centro := CenterContainer.new()
	centro.set_anchors_preset(Control.PRESET_FULL_RECT)
	radice.add_child(centro)
	var p := pannello(Color(0.04, 0.02, 0.02, 0.82))
	p.custom_minimum_size = Vector2(560, 0)
	centro.add_child(p)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 10)
	p.add_child(v)
	var t1 := etichetta("IL SIGNORE DEGLI ANELLI", F_TITOLO, 22, COL_ORO)
	t1.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	v.add_child(t1)
	var t2 := etichetta("Il Duello", F_DECO, 64, Color(1.0, 0.86, 0.6))
	t2.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	v.add_child(t2)
	var t3 := etichetta("Gandalf contro il Balrog sul ponte di Khazad-dûm", F_CORSIVO, 21)
	t3.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	v.add_child(t3)
	v.add_child(HSeparator.new())
	v.add_child(bottone("Gioca contro il computer", _menu_ia, Color(0.3, 0.12, 0.06), 22))
	v.add_child(bottone("Due giocatori su questo dispositivo", func(): _nuova("locale", "G", 1), Color(0.2, 0.12, 0.08)))
	v.add_child(bottone("Partita online", _menu_online, Color(0.12, 0.14, 0.24)))
	if FileAccess.file_exists(SALVA_LOCALE):
		v.add_child(bottone("Continua la partita salvata", _carica, Color(0.14, 0.2, 0.12)))
	else:
		v.add_child(bottone("Recupera la partita salvata online", _carica_remoto, Color(0.14, 0.2, 0.12)))
	v.add_child(bottone("Regole del gioco", mostra_regole, Color(0.16, 0.14, 0.12)))
	var nota := etichetta("Peter Neugebauer, Kosmos 2002 – illustrazioni di John Howe. Versione digitale per uso personale. Suoni: Oculus Audio Pack (Meta, CC BY 4.0).", F_CORSIVO, 15, Color(0.75, 0.7, 0.65))
	nota.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	nota.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	v.add_child(nota)

func _menu_ia() -> void:
	svuota(radice)
	var centro := CenterContainer.new()
	centro.set_anchors_preset(Control.PRESET_FULL_RECT)
	radice.add_child(centro)
	var p := pannello()
	p.custom_minimum_size = Vector2(620, 0)
	centro.add_child(p)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 12)
	p.add_child(v)
	var t := etichetta("Chi vuoi essere?", F_TITOLO, 30, COL_ORO)
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	v.add_child(t)
	var h := HBoxContainer.new()
	h.alignment = BoxContainer.ALIGNMENT_CENTER
	h.add_theme_constant_override("separation", 30)
	v.add_child(h)
	var scelta := {"ruolo": "G", "livello": 1}
	var bottoni := {}
	for chi in ["G", "B"]:
		var c := VBoxContainer.new()
		var img := immagine_carta(tex_carta(29 if chi == "G" else 49), 150, 232)
		c.add_child(img)
		var b := Button.new()
		b.toggle_mode = true
		b.text = "Gandalf" if chi == "G" else "Il Balrog"
		b.add_theme_font_override("font", F_TITOLO)
		b.add_theme_font_size_override("font_size", 22)
		b.button_pressed = chi == "G"
		b.add_theme_stylebox_override("normal", stile(Color(0.15, 0.1, 0.08), Color(0.4, 0.3, 0.2)))
		b.add_theme_stylebox_override("pressed", stile(Color(0.4, 0.18, 0.06), Color(1, 0.8, 0.4)))
		b.add_theme_stylebox_override("hover", stile(Color(0.25, 0.15, 0.1), Color(0.8, 0.6, 0.3)))
		b.add_theme_stylebox_override("hover_pressed", stile(Color(0.45, 0.2, 0.08), Color(1, 0.85, 0.45)))
		b.add_theme_color_override("font_color", COL_ORO)
		b.add_theme_color_override("font_pressed_color", Color(1, 0.95, 0.8))
		bottoni[chi] = b
		c.add_child(b)
		h.add_child(c)
	for chi in ["G", "B"]:
		var cc: String = chi
		bottoni[chi].pressed.connect(func():
			scelta["ruolo"] = cc
			bottoni["G"].button_pressed = cc == "G"
			bottoni["B"].button_pressed = cc == "B")
	var lv := etichetta("Livello del computer", F_TITOLO, 20, COL_ORO)
	lv.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	v.add_child(lv)
	var hl := HBoxContainer.new()
	hl.alignment = BoxContainer.ALIGNMENT_CENTER
	v.add_child(hl)
	var ob := OptionButton.new()
	ob.add_item("Apprendista", 0)
	ob.add_item("Stregone", 1)
	ob.add_item("Maia", 2)
	ob.selected = 1
	ob.add_theme_font_size_override("font_size", 20)
	ob.item_selected.connect(func(i): scelta["livello"] = i)
	hl.add_child(ob)
	v.add_child(bottone("Al ponte!", func(): _nuova("ia", scelta["ruolo"], scelta["livello"]), Color(0.42, 0.14, 0.05), 24))
	v.add_child(bottone("Indietro", mostra_menu, Color(0.15, 0.13, 0.12)))

# ============================================================ regole

func mostra_regole() -> void:
	var fuori := ColorRect.new()
	fuori.color = Color(0, 0, 0, 0.6)
	fuori.set_anchors_preset(Control.PRESET_FULL_RECT)
	radice.add_child(fuori)
	var p := pannello(Color(0.08, 0.05, 0.04, 0.97))
	p.set_anchors_preset(Control.PRESET_FULL_RECT)
	p.offset_left = 60
	p.offset_right = -60
	p.offset_top = 30
	p.offset_bottom = -30
	fuori.add_child(p)
	var v := VBoxContainer.new()
	p.add_child(v)
	var t := etichetta("Regole del Duello", F_TITOLO, 30, COL_ORO)
	v.add_child(t)
	var r := RichTextLabel.new()
	r.bbcode_enabled = true
	r.size_flags_vertical = Control.SIZE_EXPAND_FILL
	r.add_theme_font_override("normal_font", F_TESTO)
	r.add_theme_font_override("bold_font", F_TITOLO)
	r.add_theme_font_override("italics_font", F_CORSIVO)
	r.add_theme_font_size_override("normal_font_size", 19)
	r.add_theme_font_size_override("bold_font_size", 18)
	r.add_theme_color_override("default_color", COL_TESTO)
	r.text = Regole.TESTO
	v.add_child(r)
	v.add_child(bottone("Chiudi", fuori.queue_free))

# ============================================================ nuova partita, salvataggi

func _nuova(m: String, ruolo: String, lv: int, s := 0) -> void:
	modo = m
	io = ruolo
	livello = lv
	seme = s if s != 0 else (randi() & 0x7fffffff)
	decisioni = []
	st = Motore.nuova(seme)
	ia = IA.new(livello, seme)
	nomi = {"G": "Gandalf", "B": "Balrog"}
	if modo == "ia":
		nomi[Motore.altro(io)] = ("Gandalf" if io == "B" else "Balrog") + " (computer)"
	_apri_tavolo()
	_salva(true)

func _stato_salvato() -> Dictionary:
	return {"seme": seme, "dec": decisioni, "modo": modo, "io": io, "livello": livello}

func _ricostruisci(dati: Dictionary) -> bool:
	if not dati.has("seme"):
		return false
	modo = str(dati.get("modo", "ia"))
	io = str(dati.get("io", "G"))
	livello = int(dati.get("livello", 1))
	seme = int(dati["seme"])
	st = Motore.nuova(seme)
	ia = IA.new(livello, seme)
	decisioni = []
	for d in dati.get("dec", []):
		var n0: int = st["n"]
		Motore.applica(st, d)
		if st["n"] == n0:
			break
		decisioni.append(d)
	nomi = {"G": "Gandalf", "B": "Balrog"}
	if modo == "ia":
		nomi[Motore.altro(io)] = ("Gandalf" if io == "B" else "Balrog") + " (computer)"
	return true

func _carica() -> void:
	var f := FileAccess.open(SALVA_LOCALE, FileAccess.READ)
	if f == null:
		return
	var dati = JSON.parse_string(f.get_as_text())
	if dati is Dictionary and _ricostruisci(dati):
		_apri_tavolo()

func _carica_remoto() -> void:
	var dati := await net.carica_partita()
	if dati.is_empty() or not _ricostruisci(dati):
		_avviso("Nessuna partita salvata online trovata.")
		return
	_apri_tavolo()

func _salva(subito := false) -> void:
	if modo == "online" or not in_partita and not subito:
		return
	var dati := _stato_salvato()
	if Motore.finita(st):
		if FileAccess.file_exists(SALVA_LOCALE):
			DirAccess.remove_absolute(ProjectSettings.globalize_path(SALVA_LOCALE))
		net.cancella_partita()
		return
	var f := FileAccess.open(SALVA_LOCALE, FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(dati))
		f.close()
	var ora := Time.get_unix_time_from_system()
	if subito or ora - ultimo_salvataggio > 15.0:
		ultimo_salvataggio = ora
		net.salva_partita(dati)

# ============================================================ online

var on_nome: LineEdit
var on_codice: LineEdit
var on_stato: Label
var on_ruolo := "G"

func _menu_online() -> void:
	svuota(radice)
	var centro := CenterContainer.new()
	centro.set_anchors_preset(Control.PRESET_FULL_RECT)
	radice.add_child(centro)
	var p := pannello()
	p.custom_minimum_size = Vector2(600, 0)
	centro.add_child(p)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 10)
	p.add_child(v)
	v.add_child(etichetta("Partita online", F_TITOLO, 30, COL_ORO))
	v.add_child(etichetta("Il tuo nome"))
	on_nome = LineEdit.new()
	on_nome.text = str(net.load_session().get("name", "Viandante"))
	on_nome.max_length = 20
	v.add_child(on_nome)
	var h := HBoxContainer.new()
	h.add_child(etichetta("Nella stanza che crei sarai: "))
	var ob := OptionButton.new()
	ob.add_item("Gandalf")
	ob.add_item("Il Balrog")
	ob.item_selected.connect(func(i): on_ruolo = "G" if i == 0 else "B")
	h.add_child(ob)
	v.add_child(h)
	v.add_child(bottone("Crea una stanza", _online_crea, Color(0.3, 0.12, 0.06)))
	v.add_child(HSeparator.new())
	var h2 := HBoxContainer.new()
	h2.add_child(etichetta("Codice della stanza: "))
	on_codice = LineEdit.new()
	on_codice.max_length = 4
	on_codice.custom_minimum_size = Vector2(110, 0)
	h2.add_child(on_codice)
	h2.add_child(bottone("Entra", _online_entra, Color(0.12, 0.14, 0.24)))
	v.add_child(h2)
	on_stato = etichetta("", F_CORSIVO, 18)
	on_stato.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	v.add_child(on_stato)
	var ses := net.load_session()
	if str(ses.get("room", "")) != "":
		v.add_child(bottone("Rientra nella stanza " + str(ses["room"]), func(): on_codice.text = str(ses["room"]); _online_entra(), Color(0.14, 0.2, 0.12)))
	v.add_child(bottone("Indietro", mostra_menu, Color(0.15, 0.13, 0.12)))

func _online_crea() -> void:
	on_stato.text = "Creo la stanza..."
	net._save({"name": on_nome.text})
	var c := await net.create_room(on_nome.text, {"ruolo_host": on_ruolo})
	if c == "":
		on_stato.text = "Non riesco a creare la stanza: " + net.last_error
		return
	codice = c
	net.remember_room(c, 0)
	on_stato.text = "Stanza %s creata. Dai il codice al tuo avversario: la partita parte appena entra." % c
	while is_instance_valid(on_stato) and not in_partita:
		var room := await net.room(codice)
		var seats := Rete._as_dict(room.get("seats", {}))
		if seats.size() >= 2:
			var s := (randi() & 0x7fffffff) | 1
			var game := {"seed": s, "ruolo_host": on_ruolo, "nomi": {"0": seats["0"].get("name", "?"), "1": seats["1"].get("name", "?")}}
			if await net.start_room(codice, game):
				room["game"] = JSON.stringify(game)
				_avvia_online(room, 0)
			return
		await get_tree().create_timer(1.5).timeout

func _online_entra() -> void:
	var c := on_codice.text.strip_edges().to_upper()
	if c.length() != 4:
		on_stato.text = "Il codice ha 4 lettere."
		return
	on_stato.text = "Entro nella stanza %s..." % c
	net._save({"name": on_nome.text})
	var p := await net.join_room(c, on_nome.text, 2)
	if p < 0:
		on_stato.text = "Non riesco a entrare (stanza piena o inesistente). " + net.last_error
		return
	codice = c
	net.remember_room(c, p)
	on_stato.text = "Sei nella stanza %s. Aspetto che la partita parta..." % c
	while is_instance_valid(on_stato) and not in_partita:
		var room := await net.room(codice)
		if room.get("status", "") == "playing":
			_avvia_online(room, p)
			return
		await get_tree().create_timer(1.5).timeout

func _avvia_online(room: Dictionary, posto: int) -> void:
	var game = JSON.parse_string(str(room.get("game", "{}")))
	if not (game is Dictionary):
		return
	modo = "online"
	var rh: String = str(game.get("ruolo_host", "G"))
	io = rh if posto == 0 else Motore.altro(rh)
	seme = int(game["seed"])
	st = Motore.nuova(seme)
	decisioni = []
	var gn: Dictionary = game.get("nomi", {})
	nomi = {rh: str(gn.get("0", "?")), Motore.altro(rh): str(gn.get("1", "?"))}
	var log := await net.get_decisions(codice, 0)
	var n := 0
	while log.has(n):
		var n0: int = st["n"]
		Motore.applica(st, log[n])
		if st["n"] == n0:
			break
		decisioni.append(log[n])
		n += 1
	_apri_tavolo()

func _aspetta_remoto() -> void:
	aspetto_rete = true
	var n: int = st["n"]
	var d = await net.get_decision(codice, n)
	if in_partita and d is Dictionary and d.has("tipo") and int(st["n"]) == n:
		_applica(d, false)
	else:
		await get_tree().create_timer(1.0).timeout
	aspetto_rete = false

# ============================================================ tavolo di gioco

func _apri_tavolo() -> void:
	svuota(radice)
	in_partita = true
	mostrata = -1
	occupato = 0.3
	passaggio = ""
	scena.auto_giro = false
	scena.visuale(0)
	scena.spostamento_px = BARRA * 0.5
	scena.suoni.avvia_sottofondo()
	# per le prove: ?tel apre subito la stanza dei telefoni
	if OS.has_feature("web") and str(JavaScriptBridge.eval("new URLSearchParams(location.search).has('tel')")) == "true":
		_apri_telefono.call_deferred()
	if decisioni.is_empty():
		scena.frase("G", 1.2, "gandalf_non_passerai")
	scena.metti_figure(st["figura"]["G"], st["figura"]["B"])
	tavolo = Control.new()
	tavolo.set_anchors_preset(Control.PRESET_FULL_RECT)
	tavolo.mouse_filter = Control.MOUSE_FILTER_IGNORE
	radice.add_child(tavolo)
	# barra di stato a destra: titolo, pulsanti, avversario, carte per il finale, energia in colonna
	var barra := PanelContainer.new()
	barra.add_theme_stylebox_override("panel", stile(Color(0.05, 0.03, 0.03, 0.82), Color(0.55, 0.42, 0.2), 0, 1))
	barra.set_anchors_preset(Control.PRESET_RIGHT_WIDE)
	barra.offset_left = -BARRA
	barra.offset_right = 0
	tavolo.add_child(barra)
	var vb := VBoxContainer.new()
	vb.add_theme_constant_override("separation", 8)
	barra.add_child(vb)
	lbl_titolo = etichetta("", F_TITOLO, 20, COL_ORO)
	lbl_titolo.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vb.add_child(lbl_titolo)
	var griglia := GridContainer.new()
	griglia.columns = 2
	griglia.add_theme_constant_override("h_separation", 6)
	griglia.add_theme_constant_override("v_separation", 6)
	for b2 in [bottone("Visuale", _cambia_visuale, Color(0.15, 0.12, 0.1), 12), bottone("Diario", _apri_diario, Color(0.15, 0.12, 0.1), 12), bottone("Regole", mostra_regole, Color(0.15, 0.12, 0.1), 12), bottone("Menu", _chiedi_menu, Color(0.15, 0.12, 0.1), 12)]:
		b2.add_theme_stylebox_override("normal", _stile_piccolo(Color(0.15, 0.12, 0.1)))
		b2.add_theme_stylebox_override("hover", _stile_piccolo(Color(0.25, 0.18, 0.12)))
		b2.add_theme_stylebox_override("pressed", _stile_piccolo(Color(0.1, 0.08, 0.06)))
		b2.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		griglia.add_child(b2)
	vb.add_child(griglia)
	var b_audio := bottone("Audio: sì" if scena.suoni.attivo else "Audio: no", func(): pass, Color(0.15, 0.12, 0.1), 12)
	b_audio.add_theme_stylebox_override("normal", _stile_piccolo(Color(0.15, 0.12, 0.1)))
	b_audio.add_theme_stylebox_override("hover", _stile_piccolo(Color(0.25, 0.18, 0.12)))
	b_audio.pressed.connect(func(): b_audio.text = "Audio: sì" if scena.suoni.cambia() else "Audio: no")
	vb.add_child(b_audio)
	if telefoni.disponibile():
		var b_tel := bottone("Gioca col telefono", _apri_telefono, Color(0.2, 0.1, 0.06), 12)
		b_tel.add_theme_stylebox_override("normal", _stile_piccolo(Color(0.3, 0.12, 0.05)))
		b_tel.add_theme_stylebox_override("hover", _stile_piccolo(Color(0.4, 0.18, 0.08)))
		vb.add_child(b_tel)
	lbl_ponte = etichetta("", F_TITOLO, 1, COL_TESTO)
	lbl_ponte.visible = false
	vb.add_child(lbl_ponte)
	# l'energia sta sempre allo stesso posto, subito sotto i pulsanti
	traccia = Control.new()
	traccia.mouse_filter = Control.MOUSE_FILTER_IGNORE
	vb.add_child(traccia)
	vb.add_child(HSeparator.new())
	# sotto, le informazioni che cambiano: se sono tante si scorrono, senza spostare nulla
	var scorri := ScrollContainer.new()
	scorri.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scorri.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	vb.add_child(scorri)
	var info := VBoxContainer.new()
	info.add_theme_constant_override("separation", 6)
	scorri.add_child(info)
	box_avv = Control.new()
	box_avv.mouse_filter = Control.MOUSE_FILTER_IGNORE
	info.add_child(box_avv)
	pannello_riserve = etichetta("", F_TESTO, 16, Color(0.9, 0.85, 0.78))
	pannello_riserve.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	pannello_riserve.custom_minimum_size = Vector2(BARRA - 34, 0)
	info.add_child(pannello_riserve)
	box_riga = Control.new()
	box_riga.mouse_filter = Control.MOUSE_FILTER_IGNORE
	tavolo.add_child(box_riga)
	# il diario si apre in una finestra a parte (pulsante «Diario»)
	diario = RichTextLabel.new()
	diario.bbcode_enabled = true
	diario.scroll_following = true
	diario.add_theme_font_size_override("normal_font_size", 17)
	diario.add_theme_color_override("default_color", Color(0.92, 0.88, 0.82))
	# messaggio e mano
	lbl_msg = etichetta("", F_TITOLO, 21, Color(1, 0.93, 0.78))
	lbl_msg.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
	lbl_msg.offset_top = -CH - 58
	lbl_msg.offset_bottom = -CH - 24
	lbl_msg.offset_right = -BARRA
	lbl_msg.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	tavolo.add_child(lbl_msg)
	# l'ultima riga del diario, piccola, sopra il messaggio
	lbl_ultimo = etichetta("", F_CORSIVO, 17, Color(0.92, 0.86, 0.76))
	lbl_ultimo.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
	lbl_ultimo.offset_top = -CH - 84
	lbl_ultimo.offset_bottom = -CH - 58
	lbl_ultimo.offset_right = -BARRA
	lbl_ultimo.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	tavolo.add_child(lbl_ultimo)
	box_mano = Control.new()
	box_mano.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
	box_mano.offset_top = -CH - 12
	box_mano.mouse_filter = Control.MOUSE_FILTER_IGNORE
	tavolo.add_child(box_mano)
	box_scoperte = Control.new()
	box_scoperte.mouse_filter = Control.MOUSE_FILTER_IGNORE
	tavolo.add_child(box_scoperte)
	lbl_incantata = Control.new()
	lbl_incantata.mouse_filter = Control.MOUSE_FILTER_IGNORE
	tavolo.add_child(lbl_incantata)
	banner = etichetta("", F_DECO, 40, Color(1, 0.9, 0.7))
	banner.set_anchors_preset(Control.PRESET_CENTER_TOP)
	banner.offset_top = 210
	banner.offset_left = -500 - BARRA * 0.5
	banner.offset_right = 500 - BARRA * 0.5
	banner.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	banner.modulate.a = 0
	tavolo.add_child(banner)
	finestra_diario = Control.new()
	finestra_diario.set_anchors_preset(Control.PRESET_FULL_RECT)
	finestra_diario.mouse_filter = Control.MOUSE_FILTER_IGNORE
	finestra_diario.visible = false
	tavolo.add_child(finestra_diario)
	_costruisci_diario()
	finestra_tel = Control.new()
	finestra_tel.set_anchors_preset(Control.PRESET_FULL_RECT)
	finestra_tel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	finestra_tel.visible = false
	tavolo.add_child(finestra_tel)
	popup_scambio = Control.new()
	popup_scambio.mouse_filter = Control.MOUSE_FILTER_IGNORE
	tavolo.add_child(popup_scambio)
	dialogo = Control.new()
	dialogo.set_anchors_preset(Control.PRESET_FULL_RECT)
	dialogo.mouse_filter = Control.MOUSE_FILTER_IGNORE
	tavolo.add_child(dialogo)
	get_viewport().size_changed.connect(_aggiorna)
	_aggiorna()

func _stile_piccolo(col: Color) -> StyleBoxFlat:
	var sb := stile(col, Color(0.62, 0.47, 0.22), 7, 1)
	sb.content_margin_left = 6
	sb.content_margin_right = 6
	sb.content_margin_top = 3
	sb.content_margin_bottom = 3
	sb.shadow_size = 2
	return sb

func _costruisci_diario() -> void:
	var p := pannello(Color(0.05, 0.03, 0.02, 0.94))
	p.set_anchors_preset(Control.PRESET_CENTER_RIGHT)
	p.offset_left = -440
	p.offset_right = -14
	p.offset_top = -250
	p.offset_bottom = 250
	finestra_diario.add_child(p)
	var v := VBoxContainer.new()
	p.add_child(v)
	var h := HBoxContainer.new()
	v.add_child(h)
	var t := etichetta("Diario del duello", F_TITOLO, 20, COL_ORO)
	t.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	h.add_child(t)
	h.add_child(bottone("Chiudi", func(): finestra_diario.visible = false, Color(0.15, 0.12, 0.1), 14))
	diario.size_flags_vertical = Control.SIZE_EXPAND_FILL
	v.add_child(diario)

func _apri_diario() -> void:
	finestra_diario.visible = not finestra_diario.visible

# ============================================================ telefoni

func _ruoli_consentiti() -> Array:
	if not in_partita:
		return []
	return ["G", "B"] if modo == "locale" else [io]

func _apri_telefono() -> void:
	telefoni.avvia()
	finestra_tel.visible = not finestra_tel.visible
	_disegna_finestra_tel()

func _disegna_finestra_tel() -> void:
	svuota(finestra_tel)
	if not finestra_tel.visible:
		return
	var p := pannello(Color(0.05, 0.03, 0.02, 0.95))
	p.set_anchors_preset(Control.PRESET_CENTER_RIGHT)
	p.offset_left = -BARRA - 360
	p.offset_right = -BARRA - 14
	p.offset_top = -270
	p.offset_bottom = 270
	finestra_tel.add_child(p)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 8)
	p.add_child(v)
	v.add_child(etichetta("Gioca col telefono", F_TITOLO, 20, COL_ORO))
	var spieg := etichetta("Inquadra il codice con la fotocamera: le tue carte passano sul telefono e spariscono dalla TV.", F_TESTO, 16)
	spieg.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	spieg.custom_minimum_size = Vector2(300, 0)
	v.add_child(spieg)
	if telefoni.codice == "":
		v.add_child(etichetta("Apro la stanza...", F_CORSIVO, 18))
	else:
		var cc := CenterContainer.new()
		var t := TextureRect.new()
		t.texture = telefoni.qr(telefoni.url, 240)
		t.custom_minimum_size = Vector2(240, 240)
		cc.add_child(t)
		v.add_child(cc)
		var c := etichetta("Codice: " + telefoni.codice, F_TITOLO, 24, Color(1, 0.9, 0.7))
		c.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		v.add_child(c)
	lista_tel = etichetta("", F_TESTO, 16)
	lista_tel.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	lista_tel.custom_minimum_size = Vector2(300, 0)
	v.add_child(lista_tel)
	_aggiorna_lista_tel()
	v.add_child(bottone("Chiudi", func(): finestra_tel.visible = false, Color(0.15, 0.12, 0.1), 15))

func _aggiorna_lista_tel() -> void:
	if not is_instance_valid(lista_tel):
		return
	var t := ""
	for r in ["G", "B"]:
		if tel.has(r):
			t += "%s: telefono di %s\n" % ["Gandalf" if r == "G" else "Il Balrog", tel[r]["nome"]]
	lista_tel.text = t if t != "" else "Nessun telefono collegato."

func _evento_telefono(e: Dictionary) -> void:
	match e.get("e", ""):
		"stanza":
			if is_instance_valid(finestra_tel) and finestra_tel.visible:
				_disegna_finestra_tel()
			_invia_telefoni()
		"entra":
			var r := str(e.get("ruolo", ""))
			var uid := str(e.get("uid", ""))
			if not (r in _ruoli_consentiti()) or (tel.has(r) and tel[r]["uid"] != uid):
				telefoni.togli(uid)
				return
			for k in tel.keys():
				if tel[k]["uid"] == uid and k != r:
					tel.erase(k)
			tel[r] = {"uid": uid, "nome": str(e.get("nome", "?"))}
			_avviso("%s prende le carte di %s sul telefono." % [tel[r]["nome"], "Gandalf" if r == "G" else "il Balrog"])
			# tutti i ruoli giocabili hanno il telefono: il QR code si chiude da solo
			var tutti := true
			for rr in _ruoli_consentiti():
				if not tel.has(rr):
					tutti = false
			if tutti and is_instance_valid(finestra_tel):
				finestra_tel.visible = false
			svuota(dialogo)
			mostrata = -1
			_aggiorna_lista_tel()
			_aggiorna()
		"esce":
			for k in tel.keys():
				if tel[k]["uid"] == str(e.get("uid", "")):
					tel.erase(k)
					mostrata = -1
			_aggiorna_lista_tel()
			_aggiorna()
		"azione":
			var d = JSON.parse_string(str(e.get("p", "")))
			if not (d is Dictionary) or not in_partita or occupato > 0.0 and d.get("tipo", "") != "avanti":
				if d is Dictionary and in_partita:
					# animazione in corso: la mossa si applica appena finisce
					get_tree().create_timer(max(occupato, 0.1) + 0.05).timeout.connect(func(): _evento_telefono(e))
				return
			var a: Dictionary = st["attesa"]
			if a.is_empty() or int(d.get("n", -1)) != int(st["n"]):
				return
			var ruolo := ""
			for k in tel:
				if tel[k]["uid"] == str(e.get("uid", "")):
					ruolo = k
			if ruolo == "" or (a["chi"] != ruolo and a["tipo"] != "avanti"):
				return
			var v = d.get("v")
			if v is float:
				v = int(v)
			if v is Array:
				var vv := []
				for x in v:
					vv.append(int(x))
				v = vv
			_applica({"tipo": str(d.get("tipo", "")), "v": v})

## Manda a ogni telefono lo stato della partita e, solo a lui, le sue carte e la domanda.
func _invia_telefoni() -> void:
	if telefoni == null or telefoni.codice == "" or st.is_empty():
		return
	var ruoli := {"G": "", "B": ""}
	for r in tel:
		ruoli[r] = tel[r]["nome"]
	var e: Dictionary = st["energia"]
	telefoni.stato({"titolo": "Duello finale" if st["duello"] == 4 else "Duello %d di 3" % st["duello"],
		"energia": e, "vuote": max(0, abs(e["G"] - e["B"]) - 1), "figura": st["figura"],
		"msg": Motore.descrivi_attesa(st), "ultimo": st["diario"][-1] if not st["diario"].is_empty() else "",
		"ruoli": ruoli, "consentiti": _ruoli_consentiti(), "fine": st["vincitore"]})
	var a: Dictionary = st["attesa"]
	for r in tel:
		var m := {"n": st["n"], "ruolo": r, "mano": st["mano"][r], "incantata": -1, "forzata": st["f"].get("forzata", -1) if r == "G" else -1, "tipo": "", "scoperte": []}
		if r == "B":
			m["incantata"] = st["f"].get("incantata", -1)
		var altro := Motore.altro(r)
		for id in st["mano"][altro]:
			if Motore.vede_mano(st, r) or (r == "G" and id in st["rivelate"]):
				m["scoperte"].append(id)
		if not a.is_empty() and (a["chi"] == r or a["tipo"] == "avanti"):
			m["tipo"] = a["tipo"]
			m["opzioni"] = a.get("opzioni", [])
			m["quante"] = a.get("quante", 0)
			m["carta"] = a.get("carta", -1)
			m["motivo"] = a.get("motivo", "")
			if a["tipo"] == "frusta":
				var righe := []
				for i in a["opzioni"]:
					righe.append({"i": i, "id": st["riga"][i]["id"]})
				m["riga"] = righe
		telefoni.segreto(tel[r]["uid"], m)

func _cambia_visuale() -> void:
	var n: int = (scena.get_meta("v", 0) + 1) % 4
	scena.set_meta("v", n)
	scena.visuale(n)

func _chiedi_menu() -> void:
	_conferma("Tornare al menu? " + ("La partita resta salvata." if modo != "online" else "Potrai rientrare con il codice della stanza."), func():
		_salva(true)
		mostra_menu())

## Chi sta guardando lo schermo in questo momento.
func spettatore() -> String:
	if modo == "locale":
		# resta chi ha preso il dispositivo, finché non lo passa all'altro
		return passaggio if passaggio != "" else "G"
	return io

func _process(delta: float) -> void:
	if not in_partita or st.is_empty():
		return
	if occupato > 0.0:
		occupato -= delta
		return
	if Motore.finita(st):
		return
	var a: Dictionary = st["attesa"]
	if a.is_empty():
		return
	if a["tipo"] == "avanti":
		if mostrata != st["n"]:
			mostrata = st["n"]
			_mostra_esito(a["esito"])
		# online può premere «Continua» anche l'avversario: si ascolta la rete
		if modo == "online" and not aspetto_rete:
			_aspetta_remoto()
		return
	var chi: String = a["chi"]
	if tel.has(chi):
		# decide il telefono: la TV aspetta
		mostrata = st["n"]
		return
	if modo == "ia" and chi != io:
		attesa_ia += delta
		if attesa_ia > 0.7:
			attesa_ia = 0.0
			_applica(ia.scegli(st), true)
		return
	if modo == "online" and chi != io:
		if not aspetto_rete:
			_aspetta_remoto()
		return
	if mostrata != st["n"]:
		mostrata = st["n"]
		if modo == "locale" and passaggio != chi:
			_schermo_passaggio(chi)
			return
		_mostra_richiesta()

## Applica una decisione: online la pubblica prima su Firebase.
func _applica(d: Dictionary, locale_ok := true) -> void:
	if modo == "online" and locale_ok:
		var n: int = st["n"]
		var ok := await net.post_decision(codice, n, d)
		if not ok:
			_avviso("Rete: mossa non inviata (" + net.last_error + "). Riprova.")
			mostrata = -1
			return
		if int(st["n"]) != n:
			return
	var n0: int = st["n"]
	var ev := Motore.applica(st, d)
	if st["n"] == n0:
		return
	decisioni.append(d)
	svuota(dialogo)
	_prepara_riga(ev, d)
	_anima(ev)
	_aggiorna()
	_salva()

# ============================================================ animazioni

## Dove deve volare la carta appena giocata e dove aprire lo spazio per lo scambio.
func _prepara_riga(ev: Array, d: Dictionary) -> void:
	var riga: Array = st["riga"]
	var trova := func(id: int) -> int:
		for i in range(riga.size() - 1, -1, -1):
			if riga[i]["id"] == id and not riga[i].get("vuota", false):
				return i
		return -1
	for e in ev:
		if e["t"] == "carta":
			var i: int = trova.call(e["id"])
			if i >= 0:
				vola_idx = i
				var vs := get_viewport().get_visible_rect().size
				if e["chi"] == spettatore() and not (modo == "ia" and e["chi"] != io):
					vola_da = Vector2(vs.x * 0.5, vs.y - CH)
				else:
					var p3: Vector3 = scena.figure[e["chi"]].global_position + Vector3(0, 1.5, 0)
					vola_da = scena.cam.unproject_position(p3) if not scena.cam.is_position_behind(p3) else Vector2(vs.x * 0.5, vs.y * 0.5)
		elif e["t"] == "scambio":
			gap_idx = trova.call(e["carta_dif"])
			if vola_idx < 0:
				vola_idx = gap_idx

func _chiudi_spazio() -> void:
	if gap_idx < 0:
		return
	var da := gap_idx
	gap_idx = -1
	var g: float = riga_lay.get("gap", 0.0)
	for c in box_riga.get_children():
		if c.get_meta("i", -1) >= da:
			var tw := create_tween()
			tw.tween_property(c, "position:x", c.position.x - g, 0.45).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_IN_OUT)

func _anima(ev: Array) -> void:
	var t := 0.0
	for e in ev:
		var ee: Dictionary = e
		match ee["t"]:
			"carta":
				_dopo(t, func(): scena.carta_giocata(ee["chi"]))
				t += 0.6 if ee["chi"] == "B" else 0.35
			"scambio":
				t += 0.5   # il tempo del volo della carta
				_dopo(t, func(): _mostra_scambio(ee); scena.scambio(ee["attaccante"], ee["difensore"], ee["subiti"], ee["inflitti"], ee["parati"]))
				t += 2.8
				_dopo(t - 0.3, _chiudi_spazio)
			"speciale":
				_dopo(t, func(): _banner(Dati.carta(ee["id"])["nome"]); scena.speciale(ee["spec"]))
				t += 2.0
			"annullata":
				_dopo(t, func(): _banner(Dati.carta(ee["id"])["nome"] + ": senza effetto", 30))
				t += 1.0
			"magia_presa":
				_dopo(t, func(): _banner("La Magia di Gandalf prende la carta"); scena.speciale("magia"))
				t += 1.2
			"incantata":
				_dopo(t, func(): scena.speciale("incantesimo"))
			"fine_duello":
				_dopo(t, func(): scena.sali(ee["vincitore"], ee["da"], ee["a"]); _banner(("Gandalf" if ee["vincitore"] == "G" else "Il Balrog") + " vince il duello"))
				t += 1.8
			"fine_partita":
				_dopo(t, func(): _fine_partita(scena.caduta(Motore.altro(ee["vincitore"]))))
				t += 6.0
			"duello":
				_dopo(t, func(): _banner("Duello finale" if ee["n"] == 4 else "Duello %d" % ee["n"]))
				if ee["n"] == 4:
					_dopo(t + 0.3, func(): scena.frase("G", 0.0, "gandalf_non_passerai"))
				t += 1.0
	occupato = max(occupato, t + 0.2)

func _dopo(t: float, cb: Callable) -> void:
	if t <= 0.0:
		cb.call()
	else:
		get_tree().create_timer(t).timeout.connect(cb)

func _banner(testo: String, size := 40) -> void:
	if not is_instance_valid(banner):
		return
	banner.text = testo
	banner.add_theme_font_size_override("font_size", size)
	var tw := create_tween()
	banner.modulate.a = 0.0
	tw.tween_property(banner, "modulate:a", 1.0, 0.2)
	tw.tween_interval(1.0)
	tw.tween_property(banner, "modulate:a", 0.0, 0.4)

## Lo scambio si vede nella fila: tra la carta d'attacco (a sinistra) e quella appena giocata (a destra)
## si apre uno spazio, e lì passano i colpi (da una carta all'altra) e le parate (che si fermano a metà).
func _mostra_scambio(e: Dictionary) -> void:
	if not is_instance_valid(popup_scambio) or gap_idx < 1 or riga_lay.is_empty():
		return
	svuota(popup_scambio)
	popup_scambio.modulate.a = 1.0
	var w: float = riga_lay["w"]
	var h: float = riga_lay["h"]
	var sx: float = _slot(gap_idx - 1).x + w     # bordo destro della carta d'attacco
	var dx: float = _slot(gap_idx).x             # bordo sinistro della carta che risponde
	var y0: float = riga_lay["y0"]
	var centro := (sx + dx) * 0.5
	var righe := [0.2, 0.42, 0.64, 0.86]
	var col_att := COL_G if e["attaccante"] == "G" else COL_B
	var col_dif := COL_G if e["difensore"] == "G" else COL_B
	var rit := 0.0
	for r in e["subiti"]:
		_freccia_sfumata(Vector2(sx, y0 + h * righe[r]), Vector2(dx, y0 + h * righe[r]), col_att, rit, true, _scuoti.bind(gap_idx, col_att))
		rit += 0.38
	for r in e["inflitti"]:
		_freccia_sfumata(Vector2(dx, y0 + h * righe[r]), Vector2(sx, y0 + h * righe[r]), col_dif, rit, true, _scuoti.bind(gap_idx - 1, col_dif))
		rit += 0.38
	for r in e["parati"]:
		var y: float = y0 + h * righe[r]
		_freccia_sfumata(Vector2(sx, y), Vector2(centro, y), COL_ORO, rit, false, _bagliore.bind(Vector2(centro, y)))
		_freccia_sfumata(Vector2(dx, y), Vector2(centro, y), COL_ORO, rit, false)
		rit += 0.3
	if e.get("riflesso", false):
		var l := etichetta("riflesso", F_CORSIVO, 15, COL_G)
		l.position = Vector2(centro - 28, y0 + h + 6)
		popup_scambio.add_child(l)
	var tw := create_tween()
	tw.tween_interval(2.3)
	tw.tween_property(popup_scambio, "modulate:a", 0.0, 0.4)
	tw.tween_callback(func(): svuota(popup_scambio))

## Freccia dalla carta: la parata svanisce prima del centro; il colpo passa, sfuma a metà e torna piena
## sulla carta colpita, dove finisce con una punta.
func _freccia_sfumata(a: Vector2, b: Vector2, col: Color, ritardo := 0.0, colpo := false, alla_fine := Callable()) -> void:
	var piena := Color(col.r, col.g, col.b, 1.0)
	var vuota := Color(col.r, col.g, col.b, 0.0)
	var l := Line2D.new()
	l.width = 10
	var g := Gradient.new()
	var c := Curve.new()
	if colpo:
		g.set_color(0, piena)
		g.set_color(1, piena)
		g.add_point(0.5, Color(col.r, col.g, col.b, 0.18))
		c.add_point(Vector2(0, 1.0))
		c.add_point(Vector2(0.5, 0.45))
		c.add_point(Vector2(1, 1.0))
	else:
		g.set_color(0, piena)
		g.set_color(1, vuota)
		g.add_point(0.35, Color(col.r, col.g, col.b, 0.85))
		c.add_point(Vector2(0, 1.0))
		c.add_point(Vector2(1, 0.25))
	l.gradient = g
	l.width_curve = c
	l.begin_cap_mode = Line2D.LINE_CAP_ROUND
	l.texture_mode = Line2D.LINE_TEXTURE_NONE
	var alone := Line2D.new()
	alone.width = 22
	alone.width_curve = c
	var g2 := Gradient.new()
	g2.offsets = g.offsets
	var cs2 := PackedColorArray()
	for cc in g.colors:
		cs2.append(Color(cc.r, cc.g, cc.b, cc.a * 0.35))
	g2.colors = cs2
	alone.gradient = g2
	popup_scambio.add_child(alone)
	popup_scambio.add_child(l)
	var punta := Polygon2D.new()
	if colpo:
		var dir := (b - a).normalized()
		var n := Vector2(-dir.y, dir.x)
		punta.polygon = PackedVector2Array([b + dir * 4, b - dir * 16 + n * 11, b - dir * 16 - n * 11])
		punta.color = piena
		punta.visible = false
		popup_scambio.add_child(punta)
	l.visible = false
	alone.visible = false
	var tw := create_tween()
	tw.tween_interval(ritardo + 0.15)
	# la linea si allunga mantenendo la sfumatura giusta (punti fissi, si scopre con una maschera di lunghezza)
	tw.tween_method(func(t: float):
		l.visible = true
		alone.visible = true
		var p := a.lerp(b, t)
		var pts := PackedVector2Array()
		var passi := 16
		for i in passi + 1:
			pts.append(a.lerp(p, float(i) / passi))
		l.points = pts
		alone.points = pts
		# il gradiente segue la lunghezza totale, non quella già scoperta
		l.gradient = _taglia(g, t)
		alone.gradient = _taglia(g2, t)
		if colpo and t >= 0.999:
			punta.visible = true, 0.0, 1.0, 0.45 if colpo else 0.35).set_ease(Tween.EASE_IN)
	if alla_fine.is_valid():
		tw.tween_callback(alla_fine)
	if not colpo:
		# la parata, dopo l'incontro, si dissolve
		tw.tween_property(l, "modulate:a", 0.0, 0.5)
		tw.parallel().tween_property(alone, "modulate:a", 0.0, 0.5)

## La carta colpita sobbalza e si illumina del colore di chi colpisce.
func _scuoti(i: int, col: Color) -> void:
	for c in box_riga.get_children():
		if c.get_meta("i", -1) != i or not (c is TextureRect or c is TextureButton):
			continue
		var x0: float = c.position.x
		var tw := create_tween()
		for k in 6:
			var d := 9.0 * (1.0 - k / 6.0) * (1 if k % 2 == 0 else -1)
			tw.tween_property(c, "position:x", x0 + d, 0.035)
		tw.tween_property(c, "position:x", x0, 0.035)
		c.modulate = Color(1.0 + col.r, 1.0 + col.g * 0.6, 1.0 + col.b * 0.6)
		var tw2 := create_tween()
		tw2.tween_property(c, "modulate", Color.WHITE, 0.4)
	_bagliore(Vector2.INF, col, 0.6, i)

## Un lampo di luce morbido (parate a metà strada, oppure sulla carta colpita).
func _bagliore(p: Vector2, col := COL_ORO, forza := 1.0, su_carta := -1) -> void:
	if su_carta >= 0 and not riga_lay.is_empty():
		p = _slot(su_carta) + Vector2(riga_lay["w"] * 0.5, riga_lay["h"] * 0.5)
	var t := TextureRect.new()
	t.texture = load("res://assets/3d/scintilla.png")
	t.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	var dim := 90.0 * forza
	t.size = Vector2(dim, dim)
	t.pivot_offset = t.size * 0.5
	t.position = p - t.size * 0.5
	t.modulate = Color(col.r * 1.4, col.g * 1.3, col.b * 1.2, 1.0)
	var m := CanvasItemMaterial.new()
	m.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	t.material = m
	t.mouse_filter = Control.MOUSE_FILTER_IGNORE
	t.scale = Vector2(0.3, 0.3)
	popup_scambio.add_child(t)
	var tw := create_tween()
	tw.tween_property(t, "scale", Vector2(1.6, 1.6), 0.18).set_ease(Tween.EASE_OUT)
	tw.tween_property(t, "scale", Vector2(2.2, 2.2), 0.4)
	tw.parallel().tween_property(t, "modulate:a", 0.0, 0.4)
	tw.tween_callback(t.queue_free)
	# qualche scintilla che schizza
	for k in 10:
		var sc := TextureRect.new()
		sc.texture = t.texture
		sc.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		sc.size = Vector2(10, 10)
		sc.position = p - Vector2(5, 5)
		sc.material = m
		sc.modulate = t.modulate
		sc.mouse_filter = Control.MOUSE_FILTER_IGNORE
		popup_scambio.add_child(sc)
		var dir := Vector2.from_angle(randf() * TAU) * randf_range(25, 60) * forza
		var tw2 := create_tween()
		tw2.tween_property(sc, "position", sc.position + dir, 0.45).set_ease(Tween.EASE_OUT)
		tw2.parallel().tween_property(sc, "modulate:a", 0.0, 0.45)
		tw2.tween_callback(sc.queue_free)

## Il pezzo [0, t] di un gradiente, riscalato su [0, 1].
func _taglia(g: Gradient, t: float) -> Gradient:
	var out := Gradient.new()
	var n := 8
	var cols := []
	for i in n + 1:
		cols.append(g.sample(t * float(i) / n))
	out.set_color(0, cols[0])
	out.set_color(1, cols[n])
	for i in range(1, n):
		out.add_point(float(i) / n, cols[i])
	return out

# ============================================================ disegno del tavolo

func _aggiorna() -> void:
	if not in_partita or not is_instance_valid(tavolo):
		return
	_invia_telefoni()
	var vs := get_viewport().get_visible_rect().size
	var duello: int = st["duello"]
	lbl_titolo.text = "Duello finale" if duello == 4 else "Duello %d di 3" % duello
	lbl_ponte.text = ""
	_disegna_traccia(vs)
	_disegna_mano(vs)
	_disegna_avversario(vs)
	_disegna_riga(vs)
	_disegna_riserve()
	var testo := ""
	for l in st["diario"].slice(-30):
		testo += l + "\n"
	diario.text = testo
	lbl_ultimo.text = st["diario"][-1] if not st["diario"].is_empty() else ""
	lbl_msg.text = Motore.descrivi_attesa(st)

## Il tracciato dell'energia in colonna: in alto più energia, in basso l'area negativa.
## Gandalf (bianco) nella metà sinistra delle caselle, il Balrog (rosso) in quella destra.
func _disegna_traccia(_vs: Vector2) -> void:
	svuota(traccia)
	var vs := get_viewport().get_visible_rect().size
	# altezza fissa: dipende solo dallo schermo, lascia sotto lo spazio per le informazioni
	var chh: float = clamp((vs.y - 150.0 - 260.0) / 20.0, 11.0, 26.0)
	traccia.custom_minimum_size = Vector2(BARRA - 30, 26 + 20 * chh + 46)
	var cw := 54.0
	var x0 := (BARRA - 30 - cw) * 0.5 - 8
	var lab := etichetta("Energia", F_TITOLO, 16, COL_ORO)
	lab.size = Vector2(BARRA - 30, 22)
	lab.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	lab.position = Vector2(0, 0)
	traccia.add_child(lab)
	for i in 20:
		var val := 15 - i
		var r := Panel.new()
		var col := Color(0.16, 0.18, 0.42) if val > 0 else Color(0.34, 0.11, 0.13)
		var bordo := Color(0.45, 0.5, 0.75) if val > 0 else Color(0.65, 0.28, 0.28)
		var w := 1
		if val == Motore.INIZIO_FINALE:
			bordo = Color(1.0, 0.6, 0.2)
			w = 2
		elif val == Motore.INIZIO_DUELLO:
			bordo = Color(1, 1, 1)
			w = 2
		r.add_theme_stylebox_override("panel", stile(col, bordo, 3, w))
		r.position = Vector2(x0, 26 + i * chh)
		r.size = Vector2(cw, chh - 2)
		r.mouse_filter = Control.MOUSE_FILTER_IGNORE
		traccia.add_child(r)
		if val > 0:
			var nn := etichetta(str(val), F_TESTO, 13, Color(0.8, 0.8, 0.9, 0.7))
			nn.position = Vector2(x0 + cw + 6, 26 + i * chh + chh * 0.5 - 11)
			traccia.add_child(nn)
	var d: float = min(chh - 6, 18.0)
	for chi in ["G", "B"]:
		var e: int = st["energia"][chi]
		var g := Panel.new()
		var sb := StyleBoxFlat.new()
		sb.bg_color = Color(0.9, 0.92, 1.0) if chi == "G" else Color(0.9, 0.18, 0.08)
		sb.set_corner_radius_all(int(d))
		sb.border_color = Color(0.08, 0.08, 0.08)
		sb.set_border_width_all(2)
		g.add_theme_stylebox_override("panel", sb)
		g.size = Vector2(d, d)
		g.position = Vector2(x0 + (cw * 0.27 if chi == "G" else cw * 0.73) - d * 0.5, 26 + (15 - e) * chh + (chh - 2 - d) * 0.5)
		g.mouse_filter = Control.MOUSE_FILTER_IGNORE
		traccia.add_child(g)
	var vuote: int = max(0, abs(st["energia"]["G"] - st["energia"]["B"]) - 1)
	var info := etichetta("G %d, B %d, vuote %d" % [st["energia"]["G"], st["energia"]["B"], vuote], F_TESTO, 14, Color(0.9, 0.86, 0.78))
	info.size = Vector2(BARRA - 30, 22)
	info.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	info.position = Vector2(0, 30 + 20 * chh)
	traccia.add_child(info)

func _opzioni_mie() -> Array:
	var a: Dictionary = st["attesa"]
	if a.is_empty() or occupato > 0.0 or passaggio_attivo():
		return []
	if a["chi"] != spettatore():
		return []
	if modo == "ia" and a["chi"] != io:
		return []
	return a["opzioni"] if a["tipo"] in ["gioca", "difesa"] else []

func passaggio_attivo() -> bool:
	return is_instance_valid(dialogo) and dialogo.get_child_count() > 0 and dialogo.get_meta("passaggio", false)

func _disegna_mano(vs: Vector2) -> void:
	svuota(box_mano)
	if tel.has(spettatore()):
		var l := etichetta("Le carte di %s sono sul telefono di %s" % ["Gandalf" if spettatore() == "G" else "Balrog", tel[spettatore()]["nome"]], F_CORSIVO, 20, COL_ORO)
		l.position = Vector2(0, CH * 0.5)
		l.size = Vector2(vs.x - BARRA, 30)
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		box_mano.add_child(l)
		mano_sinistra = (vs.x - BARRA) * 0.5
		mano_destra = mano_sinistra
		return
	var chi := spettatore()
	var mano: Array = st["mano"][chi]
	var opz := _opzioni_mie()
	var ordinate := mano.duplicate()
	ordinate.sort()
	# la carta incantata è scoperta sul tavolo ma resta del Balrog: si gioca da qui, in fondo alla mano
	var inc: int = st["f"].get("incantata", -1)
	if chi == "B" and inc != -1:
		ordinate.append(inc)
	var n := ordinate.size()
	mano_sinistra = (vs.x - BARRA) * 0.5
	mano_destra = mano_sinistra
	if n == 0:
		return
	var area := vs.x - BARRA
	# a sinistra resta lo spazio per le carte scoperte dell'avversario
	var sx := 30.0
	var k_sc := _quante_scoperte()
	if k_sc > 0:
		var hs := (CH - 26.0) * 0.5
		sx = 30.0 + ceil(k_sc / 2.0) * (hs / 1.55 + 4) + 20.0
	var largo_area := area - sx - 30.0
	var passo: float = min(CW + 6, (largo_area - CW) / max(1, n - 1)) if n > 1 else CW
	var x0: float = sx + largo_area * 0.5 - (passo * (n - 1) + CW) * 0.5
	mano_sinistra = x0
	mano_destra = x0 + passo * (n - 1) + CW
	for k in ordinate.size():
		var id: int = ordinate[k]
		var c := _carta_cliccabile(id, CW, CH, _contiene(opz, id))
		c.position = Vector2(x0 + k * passo, 0)
		box_mano.add_child(c)
		if id == inc and chi == "B":
			var l := etichetta("incantata", F_CORSIVO, 15, COL_G)
			l.position = Vector2(4, -22)
			c.add_child(l)

func _contiene(a: Array, v) -> bool:
	for x in a:
		if int(x) == int(v):
			return true
	return false

func _carta_cliccabile(id: int, w: float, h: float, attiva: bool) -> Control:
	var b := TextureButton.new()
	b.texture_normal = tex_carta(id)
	b.ignore_texture_size = true
	b.stretch_mode = TextureButton.STRETCH_KEEP_ASPECT_CENTERED
	b.size = Vector2(w, h)
	b.custom_minimum_size = Vector2(w, h)
	b.pivot_offset = Vector2(w * 0.5, h)
	if not attiva:
		b.modulate = Color(0.72, 0.7, 0.68) if _opzioni_mie().size() > 0 else Color(1, 1, 1)
		b.mouse_entered.connect(func(): b.scale = Vector2(1.7, 1.7); b.z_index = 10)
		b.mouse_exited.connect(func(): b.scale = Vector2.ONE; b.z_index = 0)
		return b
	b.mouse_entered.connect(func():
		b.scale = Vector2(1.7, 1.7)
		b.z_index = 10)
	b.mouse_exited.connect(func():
		b.scale = Vector2.ONE
		b.z_index = 0)
	b.pressed.connect(func(): _clic_carta(id))
	# alone dorato sulle carte giocabili
	var alone := Panel.new()
	var s := StyleBoxFlat.new()
	s.bg_color = Color(0, 0, 0, 0)
	s.border_color = Color(1, 0.8, 0.35)
	s.set_border_width_all(3)
	s.set_corner_radius_all(12)
	alone.add_theme_stylebox_override("panel", s)
	alone.size = Vector2(w, h)
	alone.mouse_filter = Control.MOUSE_FILTER_IGNORE
	b.add_child(alone)
	return b

func _clic_carta(id: int) -> void:
	var a: Dictionary = st["attesa"]
	if a.is_empty() or occupato > 0.0:
		return
	if a["tipo"] == "gioca" or a["tipo"] == "difesa":
		_applica({"tipo": a["tipo"], "v": id})

func _quante_scoperte() -> int:
	if tel.has(spettatore()):
		return 0
	var chi := Motore.altro(spettatore())
	var vede := Motore.vede_mano(st, spettatore())
	var k := 0
	for id in st["mano"][chi]:
		if vede or (spettatore() == "G" and id in st["rivelate"]):
			k += 1
	return k

func _disegna_avversario(vs: Vector2) -> void:
	svuota(box_avv)
	var chi := Motore.altro(spettatore())
	var mano: Array = st["mano"][chi].duplicate()
	mano.sort()
	var vede := Motore.vede_mano(st, spettatore())
	var nome := etichetta("%s\n%d cart%s in mano%s" % [nomi[chi], mano.size(), "a" if mano.size() == 1 else "e", ", scoperte" if vede else ""], F_TITOLO, 13, COL_G if chi == "G" else COL_B)
	box_avv.add_child(nome)
	nome.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	nome.custom_minimum_size = Vector2(BARRA - 34, 0)
	nome.size = Vector2(BARRA - 34, 64)
	box_avv.custom_minimum_size = Vector2(BARRA - 34, 64)
	# le carte scoperte dell'avversario: piccole, accanto alla tua mano, su due righe
	svuota(box_scoperte)
	if tel.has(spettatore()):
		return
	var scoperte := []
	for id in mano:
		if vede or (spettatore() == "G" and id in st["rivelate"]):
			scoperte.append(id)
	if scoperte.is_empty():
		return
	var h := (CH - 26.0) * 0.5
	var w := h / 1.55
	var colonne := int(ceil(scoperte.size() / 2.0))
	var area := vs.x - BARRA
	var largo := colonne * (w + 4)
	var x0: float = max(12.0, mano_sinistra - 16.0 - largo)
	var y0: float = vs.y - CH - 12.0
	var tit := etichetta("Carte di " + nomi[chi], F_CORSIVO, 14, COL_G if chi == "G" else COL_B)
	tit.position = Vector2(x0, y0 - 2)
	box_scoperte.add_child(tit)
	for k in scoperte.size():
		var t := immagine_carta(tex_carta(scoperte[k]), w, h)
		t.position = Vector2(x0 + (k % colonne) * (w + 4), y0 + 22 + (k / colonne) * (h + 4))
		t.mouse_filter = Control.MOUSE_FILTER_PASS
		t.pivot_offset = Vector2(w * 0.5, h)
		t.mouse_entered.connect(func(): t.scale = Vector2(2.6, 2.6); t.z_index = 10)
		t.mouse_exited.connect(func(): t.scale = Vector2.ONE; t.z_index = 0)
		box_scoperte.add_child(t)
	# la carta incantata, scoperta sul tavolo
	svuota(lbl_incantata)
	var inc: int = st["f"].get("incantata", -1)
	if inc != -1:
		var t2 := immagine_carta(tex_carta(inc), 70, 108)
		t2.position = Vector2(12, 300)
		lbl_incantata.add_child(t2)
		var l2 := etichetta("incantata", F_CORSIVO, 15, COL_G)
		l2.position = Vector2(12, 410)
		lbl_incantata.add_child(l2)

func _disegna_riga(vs: Vector2) -> void:
	svuota(box_riga)
	var riga: Array = st["riga"]
	if riga.is_empty():
		gap_idx = -1
		vola_idx = -1
		return
	var n := riga.size()
	var a: Dictionary = st["attesa"]
	var frusta: bool = not a.is_empty() and a["tipo"] == "frusta" and a["chi"] == spettatore() and occupato <= 0.0
	# le carte si rimpiccioliscono man mano che la fila si allunga
	var area := vs.x - BARRA
	var w: float = clamp((area - 40.0 - 190.0) / max(n, 8) - 6.0, 62.0, 135.0)
	var h := w * 1.55
	var passo := w + 6.0
	var gap: float = max(190.0, w * 1.8) if gap_idx >= 0 and gap_idx < n else 0.0
	var x0: float = area * 0.5 - (passo * (n - 1) + w + gap) * 0.5
	var y0 := 14.0
	riga_lay = {"x0": x0, "y0": y0, "w": w, "h": h, "passo": passo, "gap": gap}
	for i in n:
		var r: Dictionary = riga[i]
		var c: Control
		if r.get("vuota", false):
			var p := Panel.new()
			p.add_theme_stylebox_override("panel", stile(Color(0, 0, 0, 0.3), Color(0.6, 0.5, 0.3), 8, 1))
			p.size = Vector2(w, h)
			c = p
		elif frusta and _contiene(a["opzioni"], i):
			var ii := i
			c = _carta_cliccabile(r["id"], w, h, true)
			(c as TextureButton).pressed.connect(func(): _applica({"tipo": "frusta", "v": ii}))
		else:
			var t := immagine_carta(tex_carta(r["id"]), w, h)
			t.mouse_filter = Control.MOUSE_FILTER_PASS
			t.pivot_offset = Vector2(w * 0.5, 0)
			t.mouse_entered.connect(func(): t.scale = Vector2(2.2, 2.2); t.z_index = 10)
			t.mouse_exited.connect(func(): t.scale = Vector2.ONE; t.z_index = 0)
			c = t
			if r.get("frusta", false) or r.get("riempita", false):
				c.modulate = Color(0.6, 0.6, 0.6)
		var pos := _slot(i)
		c.position = pos
		c.set_meta("i", i)
		box_riga.add_child(c)
		var bordo := Panel.new()
		var s := StyleBoxFlat.new()
		s.bg_color = Color(0, 0, 0, 0)
		s.border_color = COL_G if r["chi"] == "G" else COL_B
		s.border_width_bottom = 4
		s.set_corner_radius_all(6)
		bordo.add_theme_stylebox_override("panel", s)
		bordo.size = Vector2(w, h + 4)
		bordo.position = pos
		bordo.mouse_filter = Control.MOUSE_FILTER_IGNORE
		bordo.set_meta("i", i)
		box_riga.add_child(bordo)
		# la carta appena giocata arriva in volo
		if i == vola_idx:
			for nodo in [c, bordo]:
				nodo.position = vola_da - Vector2(w * 0.5, h * 0.5)
				nodo.scale = Vector2(1.6, 1.6)
				nodo.z_index = 20
				var tw := create_tween()
				tw.tween_property(nodo, "position", pos, 0.5).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
				tw.parallel().tween_property(nodo, "scale", Vector2.ONE, 0.5)
				tw.tween_callback(func(): nodo.z_index = 0)
	vola_idx = -1

## Posizione della carta i nella fila (con lo spazio dello scambio, se aperto).
func _slot(i: int) -> Vector2:
	var x: float = riga_lay["x0"] + i * riga_lay["passo"]
	if gap_idx >= 0 and i >= gap_idx:
		x += riga_lay["gap"]
	return Vector2(x, riga_lay["y0"])

func _disegna_riserve() -> void:
	var chi := spettatore()
	var mie: Array = st["riserva"][chi] + st["riserva_duello"][chi]
	var sue: int = st["riserva"][Motore.altro(chi)].size() + st["riserva_duello"][Motore.altro(chi)].size()
	var t := "Carte per il finale: tue %d, avversario %d" % [mie.size(), sue]
	if st["duello"] == 4:
		t = "Duello finale: si giocano le carte messe da parte"
	var f: Dictionary = st["f"]
	if f.get("astuzia", false):
		t += "\nAstuzia: il Balrog gioca a mano scoperta"
	if f.get("magia", false) and not f.get("magia_usata", false) and st["duello"] < 4:
		t += "\nMagia di Gandalf pronta"
	if f.get("ira", false):
		t += "\nIra di Gandalf: la prossima speciale del Balrog è annullata"
	if chi == "G" and f.get("forzata", -1) != -1:
		t += "\nDevi rispondere con la carta pescata dal Balrog"
	pannello_riserve.text = t

# ============================================================ richieste

func _mostra_richiesta() -> void:
	_aggiorna()
	var a: Dictionary = st["attesa"]
	match a["tipo"]:
		"incanto":
			_si_no("Il Balrog sta per giocare. Vuoi costringerlo a giocare la carta incantata?", a["carta"], "incanto")
		"magia":
			_si_no("Magia di Gandalf: prendi questa carta del Balrog per il suo duello finale? Il Balrog dovrà giocarne un'altra.", a["carta"], "magia")
		"riserva":
			_scegli_riserva(a)
		"inizio":
			_scegli_inizio(a)

func _finestra(titolo: String) -> VBoxContainer:
	svuota(dialogo)
	dialogo.set_meta("passaggio", false)
	var fuori := ColorRect.new()
	fuori.color = Color(0, 0, 0, 0.45)
	fuori.set_anchors_preset(Control.PRESET_FULL_RECT)
	dialogo.add_child(fuori)
	var cc := CenterContainer.new()
	cc.set_anchors_preset(Control.PRESET_FULL_RECT)
	dialogo.add_child(cc)
	var p := pannello()
	cc.add_child(p)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 12)
	p.add_child(v)
	var t := etichetta(titolo, F_TITOLO, 22, COL_ORO)
	t.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	t.custom_minimum_size = Vector2(520, 0)
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	v.add_child(t)
	return v

func _si_no(testo: String, carta: int, tipo: String) -> void:
	var v := _finestra(testo)
	var c := CenterContainer.new()
	c.add_child(immagine_carta(tex_carta(carta), 180, 279))
	v.add_child(c)
	var h := HBoxContainer.new()
	h.alignment = BoxContainer.ALIGNMENT_CENTER
	h.add_theme_constant_override("separation", 24)
	h.add_child(bottone("Sì", func(): _applica({"tipo": tipo, "v": true}), Color(0.35, 0.14, 0.06), 22))
	h.add_child(bottone("No", func(): _applica({"tipo": tipo, "v": false}), Color(0.15, 0.13, 0.12), 22))
	v.add_child(h)

func _scegli_inizio(a: Dictionary) -> void:
	var v := _finestra("Chi inizia il " + ("duello finale" if st["duello"] == 4 else "duello %d" % st["duello"]) + "? (Chi inizia perde in caso di pareggio.)")
	var h := HBoxContainer.new()
	h.alignment = BoxContainer.ALIGNMENT_CENTER
	h.add_theme_constant_override("separation", 24)
	h.add_child(bottone("Gandalf", func(): _applica({"tipo": "inizio", "v": "G"}), Color(0.15, 0.18, 0.3), 22))
	h.add_child(bottone("Il Balrog", func(): _applica({"tipo": "inizio", "v": "B"}), Color(0.4, 0.12, 0.05), 22))
	v.add_child(h)
	var mano := HBoxContainer.new()
	mano.alignment = BoxContainer.ALIGNMENT_CENTER
	for id in st["mano"][a["chi"]]:
		mano.add_child(immagine_carta(tex_carta(id), 76, 118))
	v.add_child(etichetta("Le tue carte per questo duello:", F_CORSIVO, 17))
	v.add_child(mano)

func _scegli_riserva(a: Dictionary) -> void:
	selezione = []
	var quante: int = a["quante"]
	var v := _finestra("Scegli %d cart%s da mettere da parte per il duello finale. Le altre vanno nella scatola." % [quante, "a" if quante == 1 else "e"])
	var h := HBoxContainer.new()
	h.alignment = BoxContainer.ALIGNMENT_CENTER
	h.add_theme_constant_override("separation", 6)
	v.add_child(h)
	var ok := bottone("Conferma", func(): _applica({"tipo": "riserva", "v": selezione.duplicate()}), Color(0.35, 0.14, 0.06), 22)
	ok.disabled = true
	for id in a["opzioni"]:
		var b := TextureButton.new()
		b.texture_normal = tex_carta(id)
		b.ignore_texture_size = true
		b.stretch_mode = TextureButton.STRETCH_KEEP_ASPECT_CENTERED
		b.custom_minimum_size = Vector2(118, 183)
		b.toggle_mode = true
		b.modulate = Color(0.65, 0.65, 0.65)
		var idd: int = id
		b.toggled.connect(func(on):
			if on:
				if selezione.size() >= quante:
					b.set_pressed_no_signal(false)
					return
				selezione.append(idd)
				b.modulate = Color(1, 1, 1)
			else:
				selezione.erase(idd)
				b.modulate = Color(0.65, 0.65, 0.65)
			ok.disabled = selezione.size() != quante)
		h.add_child(b)
	v.add_child(ok)

func _schermo_passaggio(chi: String) -> void:
	svuota(dialogo)
	dialogo.set_meta("passaggio", true)
	var fuori := ColorRect.new()
	fuori.color = Color(0.02, 0.01, 0.01, 0.96)
	fuori.set_anchors_preset(Control.PRESET_FULL_RECT)
	dialogo.add_child(fuori)
	var cc := CenterContainer.new()
	cc.set_anchors_preset(Control.PRESET_FULL_RECT)
	dialogo.add_child(cc)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 16)
	cc.add_child(v)
	var t := etichetta("Tocca a " + ("Gandalf" if chi == "G" else "il Balrog"), F_DECO, 46, COL_G if chi == "G" else COL_B)
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	v.add_child(t)
	v.add_child(etichetta("Passa il dispositivo: le carte in mano sono segrete.", F_CORSIVO, 20))
	v.add_child(bottone("Sono pronto", func():
		passaggio = chi
		dialogo.set_meta("passaggio", false)
		svuota(dialogo)
		mostrata = -1
		_aggiorna(), Color(0.35, 0.14, 0.06), 22))
	box_mano.visible = true
	_aggiorna()

func _mostra_esito(e: Dictionary) -> void:
	_aggiorna()
	var v := _finestra(("Gandalf" if e["vincitore"] == "G" else "Il Balrog") + (" vince il duello finale" if e["duello"] == 4 else " vince il duello %d" % e["duello"]))
	var g: int = e["energia"]["G"]
	var b: int = e["energia"]["B"]
	var testo := "Energia: Gandalf %d, Balrog %d." % [g, b]
	if e["pari"]:
		testo += " Pareggio: perde chi ha iniziato il duello."
	else:
		testo += " Caselle vuote tra i segnalini: %d." % max(0, abs(g - b) - 1)
	testo += "\nSale di %d gradin%s sul ponte." % [e["passi"], "o" if e["passi"] == 1 else "i"]
	testo += "\nPonte: Gandalf al gradino %d, Balrog al gradino %d." % [st["figura"]["G"], st["figura"]["B"]]
	var l := etichetta(testo, F_TESTO, 20)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	v.add_child(l)
	v.add_child(bottone("Continua", func(): _applica({"tipo": "avanti", "v": true}), Color(0.35, 0.14, 0.06), 22))

## Il riquadro di fine partita sta in alto, al posto della fila di carte, così la scena resta libera.
func _fine_partita(attesa := 2.0) -> void:
	in_partita = true
	svuota(dialogo)
	var ho_vinto: bool = modo == "locale" or st["vincitore"] == io
	scena.suoni.suona("musica_vittoria" if ho_vinto else "musica_sconfitta", -4.0, attesa + 2.0)
	box_riga.visible = false
	svuota(popup_scambio)
	var vinc: String = st["vincitore"]
	var p := PanelContainer.new()
	p.add_theme_stylebox_override("panel", stile(Color(0.05, 0.03, 0.02, 0.88), COL_G if vinc == "G" else COL_B, 14, 2))
	p.set_anchors_preset(Control.PRESET_TOP_WIDE)
	p.offset_left = 14
	p.offset_right = -BARRA - 14
	p.offset_top = 10
	tavolo.add_child(p)
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 26)
	p.add_child(h)
	var v := VBoxContainer.new()
	v.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	h.add_child(v)
	v.add_child(etichetta(("Gandalf" if vinc == "G" else "Il Balrog") + " vince!", F_DECO, 44, COL_G if vinc == "G" else COL_B))
	var frase := "Tu non puoi passare! Il Balrog precipita nell'abisso." if vinc == "G" else "Il ponte si spezza: Gandalf cade nell'ombra di Moria."
	v.add_child(etichetta(frase, F_CORSIVO, 20))
	var es := ""
	for e in st["esiti"]:
		es += "%s: %s (+%d)\n" % ["Finale" if e["duello"] == 4 else "Duello %d" % e["duello"], "Gandalf" if e["vincitore"] == "G" else "Balrog", e["passi"]]
	h.add_child(etichetta(es.strip_edges(), F_TESTO, 17))
	var vb := VBoxContainer.new()
	vb.alignment = BoxContainer.ALIGNMENT_CENTER
	h.add_child(vb)
	vb.add_child(bottone("Nuova partita", func(): _nuova(modo if modo != "online" else "ia", io, livello), Color(0.35, 0.14, 0.06), 18))
	vb.add_child(bottone("Menu", mostra_menu, Color(0.15, 0.13, 0.12), 16))
	p.modulate.a = 0.0
	var tw := create_tween()
	tw.tween_interval(attesa + 1.2)
	tw.tween_property(p, "modulate:a", 1.0, 0.6)
	_salva(true)

func _conferma(testo: String, si: Callable) -> void:
	var v := _finestra(testo)
	var h := HBoxContainer.new()
	h.alignment = BoxContainer.ALIGNMENT_CENTER
	h.add_theme_constant_override("separation", 24)
	h.add_child(bottone("Sì", si, Color(0.35, 0.14, 0.06)))
	h.add_child(bottone("No", func(): svuota(dialogo); mostrata = -1, Color(0.15, 0.13, 0.12)))
	v.add_child(h)

func _avviso(testo: String) -> void:
	var l := etichetta(testo, F_TESTO, 18, Color(1, 0.8, 0.6))
	l.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	l.position.y -= 40
	radice.add_child(l)
	get_tree().create_timer(4.0).timeout.connect(l.queue_free)
