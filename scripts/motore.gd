## Le regole di Il Signore degli Anelli – Il Duello (Kosmos / Rio Grande, 2002).
## Tutto lo stato della partita sta in un dizionario; ogni scelta di un giocatore è una "decisione"
## applicata con applica(). Il caso usa un generatore interno nello stato: stessa partenza e stesse
## decisioni danno la stessa partita su ogni dispositivo (serve per il gioco online e per i salvataggi).
class_name Motore
extends RefCounted

const INIZIO_DUELLO := 10   # casella con la D bianca sul tracciato energia
const INIZIO_FINALE := 15   # casella arancione in cima al tracciato
const FONDO := -4           # ultima casella dell'area negativa (0 … -4 sono negative)
const CIMA_PONTE := 5       # gradino più alto del ponte (0 = davanti al ponte)
const CARTE_MANO := 9

static func altro(chi: String) -> String:
	return "B" if chi == "G" else "G"

static func nome(chi: String) -> String:
	return "Gandalf" if chi == "G" else "il Balrog"

static func Nome(chi: String) -> String:
	return "Gandalf" if chi == "G" else "Il Balrog"

# ---------------------------------------------------------------- caso

static func _rnd(st: Dictionary, n: int) -> int:
	var s: int = st["rng"]
	s = (s * 1103515245 + 12345) & 0x7fffffff
	st["rng"] = s
	return (s >> 8) % n

static func _mescola(st: Dictionary, a: Array) -> void:
	for i in range(a.size() - 1, 0, -1):
		var j := _rnd(st, i + 1)
		var t = a[i]
		a[i] = a[j]
		a[j] = t

# ---------------------------------------------------------------- nuova partita

static func nuova(seme: int) -> Dictionary:
	var st := {
		"rng": (seme & 0x7fffffff) | 1,
		"seme": seme,
		"mazzo": {"G": Dati.mazzo("G"), "B": Dati.mazzo("B")},
		"mano": {"G": [], "B": []},
		"riserva": {"G": [], "B": []},          # carte messe da parte per il finale
		"riserva_duello": {"G": [], "B": []},   # prese dall'Inganno o dalla Magia in questo duello
		"rivelate": [],                          # carte del Balrog che Gandalf conosce (Astuzia)
		"figura": {"G": 0, "B": 0},
		"energia": {"G": INIZIO_DUELLO, "B": INIZIO_DUELLO},
		"duello": 1,
		"inizia": "G",
		"di_turno": "G",
		"turni": {"G": 0, "B": 0},
		"riga": [],          # carte sul tavolo nell'ordine: {id, chi, vuota}
		"attacco": {},       # carta il cui lato destro è l'attacco in corso: {id, chi, riflette}
		"f": {},             # effetti in corso nel duello
		"attesa": {},        # decisione richiesta: {chi, tipo, opzioni, ...}
		"vista": {"G": false, "B": false},
		"esiti": [],         # un riassunto per duello
		"perdente": "",
		"vincitore_finale": "",
		"vincitore": "",
		"n": 0,              # numero di decisioni applicate
		"diario": [],
	}
	_mescola(st, st["mazzo"]["G"])
	_mescola(st, st["mazzo"]["B"])
	var ev := []
	_pesca(st)
	_inizia_duello(st, "G", ev)
	return st

static func copia(st: Dictionary) -> Dictionary:
	return st.duplicate(true)

static func finita(st: Dictionary) -> bool:
	return st["vincitore"] != ""

static func finale(st: Dictionary) -> bool:
	return st["duello"] == 4

static func limite(st: Dictionary) -> int:
	return CARTE_MANO if finale(st) else 6

## Carte che un giocatore può ancora giocare (per il Balrog anche quella incantata sul tavolo).
static func disponibili(st: Dictionary, chi: String) -> int:
	var n: int = st["mano"][chi].size()
	if chi == "B" and st["f"].get("incantata", -1) != -1:
		n += 1
	return n

static func _log(st: Dictionary, testo: String) -> void:
	st["diario"].append(testo)
	if st["diario"].size() > 80:
		st["diario"].pop_front()

# ---------------------------------------------------------------- duelli

static func _inizia_duello(st: Dictionary, chi_inizia: String, ev: Array) -> void:
	st["riga"] = []
	st["attacco"] = {}
	st["f"] = {}
	st["turni"] = {"G": 0, "B": 0}
	st["riserva_duello"] = {"G": [], "B": []}
	st["inizia"] = chi_inizia
	st["di_turno"] = chi_inizia
	st["vista"] = {"G": false, "B": false}
	var e := INIZIO_FINALE if finale(st) else INIZIO_DUELLO
	st["energia"] = {"G": e, "B": e}
	ev.append({"t": "duello", "n": st["duello"], "inizia": chi_inizia})
	_log(st, ("Duello finale" if finale(st) else "Duello %d" % st["duello"]) + ": inizia " + nome(chi_inizia) + ".")
	_chiedi_giocata(st, ev)

## Pesca le 9 carte di un nuovo duello preliminare.
static func _pesca(st: Dictionary) -> void:
	for chi in ["G", "B"]:
		var m: Array = st["mazzo"][chi]
		st["mano"][chi] = m.slice(0, CARTE_MANO)
		st["mazzo"][chi] = m.slice(CARTE_MANO)

## Prepara la richiesta di giocare una carta per chi è di turno (o chiude il duello).
static func _chiedi_giocata(st: Dictionary, ev: Array) -> void:
	var chi: String = st["di_turno"]
	var f: Dictionary = st["f"]
	if _duello_finito(st):
		_chiudi_duello(st, ev)
		return
	if chi == "G" and f.get("forzata", -1) != -1:
		var c: int = f["forzata"]
		if c in st["mano"]["G"]:
			st["attesa"] = {"chi": "G", "tipo": "gioca", "opzioni": [c], "motivo": "forza"}
			return
		f.erase("forzata")
	if chi == "B":
		var inc: int = f.get("incantata", -1)
		if inc != -1:
			if st["mano"]["B"].is_empty():
				st["attesa"] = {"chi": "B", "tipo": "gioca", "opzioni": [inc], "motivo": "incantata"}
				return
			if not f.get("incanto_deciso", false):
				st["attesa"] = {"chi": "G", "tipo": "incanto", "opzioni": [true, false], "carta": inc}
				return
			f.erase("incanto_deciso")
			if f.get("incanto_forza", false):
				f.erase("incanto_forza")
				st["attesa"] = {"chi": "B", "tipo": "gioca", "opzioni": [inc], "motivo": "incantata"}
				return
	st["attesa"] = {"chi": chi, "tipo": "gioca", "opzioni": st["mano"][chi].duplicate()}

static func _duello_finito(st: Dictionary) -> bool:
	var e: Dictionary = st["energia"]
	var lim := limite(st)
	var t: Dictionary = st["turni"]
	if e["G"] <= 0 or e["B"] <= 0:
		# eccezione: entrambi nella stessa casella negativa e restano carte da giocare
		if e["G"] == e["B"] and (t["G"] < lim or t["B"] < lim) and disponibili(st, st["di_turno"]) > 0:
			return false
		return true
	var chi: String = st["di_turno"]
	return t[chi] >= lim or disponibili(st, chi) == 0

# ---------------------------------------------------------------- decisioni

## Applica una decisione {"tipo": ..., "v": valore} della persona attesa. Restituisce gli eventi
## (per le animazioni). Una decisione non valida non cambia nulla e restituisce [].
static func applica(st: Dictionary, d: Dictionary) -> Array:
	var ev := []
	var a: Dictionary = st["attesa"]
	if a.is_empty() or d.get("tipo", "") != a["tipo"]:
		return ev
	var v = d.get("v")
	match a["tipo"]:
		"gioca":
			if not _contiene(a["opzioni"], v):
				return ev
			st["n"] += 1
			_gioca(st, a["chi"], int(v), ev)
		"incanto":
			st["n"] += 1
			st["f"]["incanto_deciso"] = true
			st["f"]["incanto_forza"] = bool(v)
			if bool(v):
				ev.append({"t": "incanto_forzato", "id": a["carta"]})
				_log(st, "Gandalf costringe il Balrog a giocare la carta incantata.")
			_chiedi_giocata(st, ev)
		"magia":
			st["n"] += 1
			_decidi_magia(st, bool(v), ev)
		"frusta":
			if not _contiene(a["opzioni"], v):
				return ev
			st["n"] += 1
			_frusta(st, int(v), ev)
		"difesa":
			if not _contiene(a["opzioni"], v):
				return ev
			st["n"] += 1
			_riempi_vuoto(st, int(v), ev)
		"riserva":
			if not (v is Array) or v.size() != a["quante"]:
				return ev
			for x in v:
				if not _contiene(a["opzioni"], x):
					return ev
			var vv := []
			for x in v:
				if not _contiene(vv, x):
					vv.append(int(x))
			if vv.size() != a["quante"]:
				return ev
			st["n"] += 1
			_scegli_riserva(st, a["chi"], vv, ev)
		"inizio":
			if not (v in ["G", "B"]):
				return ev
			st["n"] += 1
			_log(st, Nome(a["chi"]) + " decide che inizia " + nome(v) + ".")
			_inizia_duello(st, v, ev)
		"avanti":
			st["n"] += 1
			_dopo_esito(st, ev)
	return ev

static func _contiene(arr: Array, v) -> bool:
	for x in arr:
		if typeof(x) == typeof(v) and x == v:
			return true
		if (typeof(x) == TYPE_INT or typeof(x) == TYPE_FLOAT) and (typeof(v) == TYPE_INT or typeof(v) == TYPE_FLOAT) and int(x) == int(v):
			return true
	return false

# ---------------------------------------------------------------- giocare una carta

static func _gioca(st: Dictionary, chi: String, id: int, ev: Array) -> void:
	var f: Dictionary = st["f"]
	if chi == "B" and f.get("incantata", -1) == id:
		f["incantata"] = -1
	else:
		st["mano"][chi].erase(id)
	if chi == "G" and f.get("forzata", -1) == id:
		f.erase("forzata")
	ev.append({"t": "carta", "chi": chi, "id": id})
	# Magia di Gandalf: può prendere questa carta del Balrog per il finale
	if chi == "B" and f.get("magia", false) and not f.get("magia_usata", false) and not finale(st) and disponibili(st, "B") > 0:
		st["attesa"] = {"chi": "G", "tipo": "magia", "opzioni": [true, false], "carta": id}
		return
	_posa(st, chi, id, ev)

static func _decidi_magia(st: Dictionary, prendi: bool, ev: Array) -> void:
	var id: int = st["attesa"]["carta"]
	if prendi:
		st["f"]["magia_usata"] = true
		st["riserva_duello"]["B"].append(id)
		ev.append({"t": "magia_presa", "id": id})
		_log(st, "Magia di Gandalf: la carta del Balrog va tra le sue carte del finale; il Balrog ne gioca un'altra.")
		st["di_turno"] = "B"
		_chiedi_giocata(st, ev)
	else:
		_posa(st, "B", id, ev)

## La carta è ormai sul tavolo: conta il turno, si confrontano i simboli, poi l'effetto speciale.
static func _posa(st: Dictionary, chi: String, id: int, ev: Array) -> void:
	var f: Dictionary = st["f"]
	st["turni"][chi] += 1
	var att: Dictionary = st["attacco"]
	var s := Dati.spec(id)
	var attivo := Dati.speciale(id)
	var perche := ""
	if attivo and finale(st) and s in ["magia", "inganno"]:
		attivo = false
		perche = "nel finale non ha effetto"
	if attivo and att.get("riflette", -1) != -1 and not (s in ["frusta", "difesa"]):
		attivo = false
		perche = "risponde allo Specchio"
	if attivo and chi == "B" and f.get("ira", false) and s != "frusta":
		if not (finale(st) and s == "inganno"):
			attivo = false
			f["ira"] = false
			perche = "annullata dall'Ira di Gandalf"
	if Dati.speciale(id) and not attivo:
		ev.append({"t": "annullata", "id": id, "perche": perche})
		_log(st, "%s: effetto annullato (%s)." % [Dati.carta(id)["nome"], perche])
	# Frusta del Balrog: sceglie una sua carta già giocata
	if s == "frusta" and attivo:
		var opz := []
		for i in st["riga"].size():
			var r: Dictionary = st["riga"][i]
			if r["chi"] == "B" and not r.get("vuota", false) and not Dati.speciale(r["id"]):
				opz.append(i)
		if not opz.is_empty():
			st["attesa"] = {"chi": "B", "tipo": "frusta", "opzioni": opz, "carta": id}
			return
	st["riga"].append({"id": id, "chi": chi})
	var precedente: Dictionary = att.duplicate()
	if s == "specchio" and attivo and not att.is_empty() and att["chi"] == "B":
		# lo Specchio neutralizza l'attacco e lo rimanda al Balrog
		var m: int = att["id"] if att.get("riflette", -1) == -1 else att["riflette"]
		st["attacco"] = {"id": id, "chi": "G", "riflette": m}
		ev.append({"t": "specchio", "riflette": m})
		_log(st, "Specchio di Gandalf: l'attacco del Balrog gli viene rimandato contro.")
	else:
		_confronta(st, chi, id, ev)
		st["attacco"] = {"id": id, "chi": chi}
	_dopo_confronto(st, chi, id, s if attivo else "", precedente, ev)

## Confronta il lato sinistro (difesa) della carta di chi risponde con l'attacco in corso.
static func _confronta(st: Dictionary, chi: String, id_dif: int, ev: Array) -> void:
	var difesa: Array = Dati.sx(id_dif)
	var att: Dictionary = st["attacco"]
	if att.is_empty():
		return
	var colpo: Array
	var attaccante: String
	var id_att: int
	if att.get("riflette", -1) != -1:
		id_att = att["riflette"]
		attaccante = "G"
	else:
		id_att = att["id"]
		attaccante = att["chi"]
	colpo = Dati.dx(id_att)
	var subiti := []   # righe in cui chi risponde viene colpito
	var inflitti := [] # righe in cui la difesa colpisce l'attaccante
	var parati := []
	for r in 4:
		var a: int = colpo[r]
		var d: int = difesa[r]
		if a == 1 and d == 0:
			subiti.append(r)
		elif d == 1 and a == 0:
			inflitti.append(r)
		elif a == 1 and d == 1:
			parati.append(r)
	_energia(st, chi, -subiti.size())
	_energia(st, attaccante, -inflitti.size())
	ev.append({"t": "scambio", "attaccante": attaccante, "difensore": chi, "subiti": subiti, "inflitti": inflitti, "parati": parati,
		"carta_att": id_att, "carta_dif": id_dif, "riflesso": att.get("riflette", -1) != -1})
	if subiti.size() + inflitti.size() > 0:
		_log(st, "%s perde %d, %s perde %d." % [Nome(chi), subiti.size(), nome(attaccante), inflitti.size()])
	_aggiorna_vista(st)

static func _energia(st: Dictionary, chi: String, d: int, tetto := false) -> void:
	var e: int = st["energia"][chi] + d
	if tetto:
		e = min(e, INIZIO_FINALE if finale(st) else INIZIO_DUELLO)
	st["energia"][chi] = clampi(e, FONDO, INIZIO_FINALE)

## Con 3 o più caselle vuote tra i segnalini, chi sta più in alto guarda la mano dell'altro.
static func _aggiorna_vista(st: Dictionary) -> void:
	var g: int = st["energia"]["G"]
	var b: int = st["energia"]["B"]
	var vuote: int = abs(g - b) - 1
	st["vista"] = {"G": vuote >= 3 and g > b, "B": vuote >= 3 and b > g}

static func _negativo(st: Dictionary) -> bool:
	return st["energia"]["G"] <= 0 or st["energia"]["B"] <= 0

## Effetti delle carte speciali dopo il confronto, poi tocca all'altro.
static func _dopo_confronto(st: Dictionary, chi: String, id: int, s: String, precedente: Dictionary, ev: Array) -> void:
	var f: Dictionary = st["f"]
	if s != "" and _negativo(st):
		ev.append({"t": "annullata", "id": id, "perche": "il duello è finito"})
		s = ""
	if s != "":
		ev.append({"t": "speciale", "id": id, "spec": s})
	match s:
		"equilibrio":
			var g: int = st["energia"]["G"]
			var b: int = st["energia"]["B"]
			if g > b:
				_energia(st, "G", 1, true)
			elif g == b:
				_energia(st, "G", 1, true)
				_energia(st, "B", -1)
			else:
				_energia(st, "G", 2, true)
				_energia(st, "B", -1)
			_aggiorna_vista(st)
			_log(st, "Equilibrio di Gandalf: i segnalini energia si spostano.")
		"potenza":
			var fg: int = st["figura"]["G"]
			var fb: int = st["figura"]["B"]
			if fb > fg:
				_energia(st, "B", 1, true)
			elif fb == fg:
				_energia(st, "B", 1, true)
				_energia(st, "G", -1)
			else:
				_energia(st, "B", 2, true)
				_energia(st, "G", -1)
			_aggiorna_vista(st)
			_log(st, "Potenza del Balrog: i segnalini energia si spostano.")
		"astuzia":
			f["astuzia"] = true
			_log(st, "Astuzia di Gandalf: il Balrog gioca a mano scoperta.")
		"magia":
			f["magia"] = true
			_log(st, "Magia di Gandalf: potrà prendere una delle prossime carte del Balrog.")
		"ira":
			f["ira"] = true
			_log(st, "Ira di Gandalf: la prossima carta speciale del Balrog perde l'effetto.")
		"incantesimo":
			var mb: Array = st["mano"]["B"]
			if not mb.is_empty():
				var c: int = mb[_rnd(st, mb.size())]
				mb.erase(c)
				f["incantata"] = c
				ev.append({"t": "incantata", "id": c})
				_log(st, "Incantesimo di Gandalf: una carta del Balrog finisce scoperta sul tavolo.")
		"forza":
			var mg: Array = st["mano"]["G"]
			if not mg.is_empty():
				f["forzata"] = mg[_rnd(st, mg.size())]
				ev.append({"t": "forzata", "id": f["forzata"]})
				_log(st, "Forza del Balrog: Gandalf deve rispondere con la carta pescata.")
		"inganno":
			var mg2: Array = st["mano"]["G"]
			if not mg2.is_empty():
				var c2: int = mg2[_rnd(st, mg2.size())]
				mg2.erase(c2)
				st["riserva_duello"]["G"].append(c2)
				f["ingannata"] = c2
				ev.append({"t": "ingannata", "id": c2})
				_log(st, "Inganno del Balrog: una carta di Gandalf va tra le sue carte del finale.")
		"difesa":
			if not precedente.is_empty() and precedente["chi"] == "G":
				_difesa(st, id, precedente, ev)
				return
	if _negativo(st):
		ev.append({"t": "energia"})
	st["di_turno"] = altro(chi)
	_chiedi_giocata(st, ev)

## Difesa del Balrog: l'ultima carta di Gandalf viene spostata a rispondere alla Difesa,
## e Gandalf riempie lo spazio vuoto con una carta qualsiasi (che non conta).
static func _difesa(st: Dictionary, id_difesa: int, precedente: Dictionary, ev: Array) -> void:
	var y: int = precedente["id"]
	var riga: Array = st["riga"]
	var pos := -1
	for i in riga.size():
		if riga[i]["id"] == y and riga[i]["chi"] == "G" and not riga[i].get("vuota", false):
			pos = i
	if pos == -1:
		st["di_turno"] = "G"
		_chiedi_giocata(st, ev)
		return
	riga[pos] = {"id": -1, "chi": "G", "vuota": true, "buco": true}
	riga.append({"id": y, "chi": "G", "spostata": true})
	ev.append({"t": "difesa", "id": y})
	if Dati.spec(y) == "specchio":
		st["attacco"] = {"id": y, "chi": "G", "riflette": id_difesa}
		ev.append({"t": "specchio", "riflette": id_difesa})
		_log(st, "Lo Specchio di Gandalf, spostato, rimanda al Balrog la sua Difesa.")
	else:
		_confronta(st, "G", y, ev)
		st["attacco"] = {"id": y, "chi": "G"}
	_log(st, "Difesa del Balrog: la carta di Gandalf risponde alla Difesa.")
	if st["mano"]["G"].is_empty() or _negativo(st):
		st["di_turno"] = "B"
		_chiedi_giocata(st, ev)
		return
	st["attesa"] = {"chi": "G", "tipo": "difesa", "opzioni": st["mano"]["G"].duplicate()}

static func _riempi_vuoto(st: Dictionary, id: int, ev: Array) -> void:
	st["mano"]["G"].erase(id)
	if st["f"].get("forzata", -1) == id:
		st["f"].erase("forzata")
	st["turni"]["G"] += 1
	for i in st["riga"].size():
		if st["riga"][i].get("buco", false):
			st["riga"][i] = {"id": id, "chi": "G", "riempita": true}
	ev.append({"t": "riempita", "id": id})
	st["di_turno"] = "B"
	_chiedi_giocata(st, ev)

## Frusta del Balrog: la carta scelta va in fondo alla riga e risponde all'attacco; la Frusta prende il suo posto.
static func _frusta(st: Dictionary, pos: int, ev: Array) -> void:
	var id_frusta: int = st["attesa"]["carta"]
	var riga: Array = st["riga"]
	var c: int = riga[pos]["id"]
	riga[pos] = {"id": id_frusta, "chi": "B", "frusta": true}
	riga.append({"id": c, "chi": "B", "frustata": true})
	ev.append({"t": "speciale", "id": id_frusta, "spec": "frusta"})
	ev.append({"t": "frusta", "id": c})
	_log(st, "Frusta del Balrog: il Balrog riusa una sua carta.")
	var precedente: Dictionary = st["attacco"].duplicate()
	_confronta(st, "B", c, ev)
	st["attacco"] = {"id": c, "chi": "B"}
	_dopo_confronto(st, "B", c, "", precedente, ev)

# ---------------------------------------------------------------- fine del duello

static func _chiudi_duello(st: Dictionary, ev: Array) -> void:
	var g: int = st["energia"]["G"]
	var b: int = st["energia"]["B"]
	var vinc := ""
	var passi := 1
	if g == b:
		vinc = altro(st["inizia"])
	else:
		vinc = "G" if g > b else "B"
		var vuote: int = abs(g - b) - 1
		passi = 1 if vuote <= 2 else (2 if vuote <= 4 else 3)
	var da: int = st["figura"][vinc]
	st["figura"][vinc] = min(CIMA_PONTE, da + passi)
	st["perdente"] = altro(vinc)
	if finale(st):
		st["vincitore_finale"] = vinc
	var esito := {"duello": st["duello"], "vincitore": vinc, "passi": st["figura"][vinc] - da, "energia": {"G": g, "B": b}, "pari": g == b}
	st["esiti"].append(esito)
	ev.append({"t": "fine_duello", "vincitore": vinc, "passi": esito["passi"], "da": da, "a": st["figura"][vinc], "pari": g == b})
	_log(st, "%s vince il %s e sale di %d gradin%s." % [Nome(vinc), "duello finale" if finale(st) else "duello %d" % st["duello"], esito["passi"], "o" if esito["passi"] == 1 else "i"])
	st["attesa"] = {"chi": "", "tipo": "avanti", "opzioni": [true], "esito": esito}

## Dopo aver mostrato l'esito: carte per il finale, fine partita o nuovo duello.
static func _dopo_esito(st: Dictionary, ev: Array) -> void:
	var vinc: String = st["esiti"][-1]["vincitore"]
	if finale(st):
		_fine_partita(st, ev)
		return
	if st["duello"] >= 2 and st["figura"][vinc] >= CIMA_PONTE:
		st["vincitore"] = vinc
		ev.append({"t": "fine_partita", "vincitore": vinc, "cima": true})
		_log(st, "%s raggiunge la cima del ponte e vince la partita!" % Nome(vinc))
		st["attesa"] = {}
		return
	st["f_scelta"] = ["G", "B"]
	_prossima_riserva(st, ev)

static func _pool_riserva(st: Dictionary, chi: String) -> Array:
	var pool: Array = st["mano"][chi].duplicate()
	if chi == "B" and st["f"].get("incantata", -1) != -1:
		pool.append(st["f"]["incantata"])
	return pool

static func _prossima_riserva(st: Dictionary, ev: Array) -> void:
	while not st["f_scelta"].is_empty():
		var chi: String = st["f_scelta"][0]
		var pool := _pool_riserva(st, chi)
		var quante: int = max(0, 3 - st["riserva_duello"][chi].size())
		if pool.size() > quante:
			st["attesa"] = {"chi": chi, "tipo": "riserva", "opzioni": pool, "quante": quante}
			return
		st["f_scelta"].pop_front()
		_metti_riserva(st, chi, pool)
	st.erase("f_scelta")
	_nuovo_duello(st, ev)

static func _scegli_riserva(st: Dictionary, chi: String, scelte: Array, ev: Array) -> void:
	st["f_scelta"].pop_front()
	_metti_riserva(st, chi, scelte)
	_prossima_riserva(st, ev)

static func _metti_riserva(st: Dictionary, chi: String, scelte: Array) -> void:
	var tutte: Array = st["riserva_duello"][chi] + scelte
	st["riserva"][chi] += tutte
	st["riserva_duello"][chi] = []
	if chi == "B" and st["f"].get("astuzia", false):
		for c in tutte:
			if not (c in st["rivelate"]):
				st["rivelate"].append(c)
	st["mano"][chi] = []
	if chi == "B":
		st["f"]["incantata"] = -1

static func _nuovo_duello(st: Dictionary, ev: Array) -> void:
	st["duello"] += 1
	st["riga"] = []
	st["attacco"] = {}
	st["f"] = {}
	if finale(st):
		st["mano"]["G"] = st["riserva"]["G"].duplicate()
		st["mano"]["B"] = st["riserva"]["B"].duplicate()
		st["riserva"] = {"G": [], "B": []}
		var fg: int = st["figura"]["G"]
		var fb: int = st["figura"]["B"]
		var decide: String = st["perdente"]
		if fg < fb:
			decide = "G"
		elif fb < fg:
			decide = "B"
		st["attesa"] = {"chi": decide, "tipo": "inizio", "opzioni": ["G", "B"]}
	else:
		_pesca(st)
		st["attesa"] = {"chi": st["perdente"], "tipo": "inizio", "opzioni": ["G", "B"]}
	ev.append({"t": "nuove_carte", "duello": st["duello"]})

static func _fine_partita(st: Dictionary, ev: Array) -> void:
	var fg: int = st["figura"]["G"]
	var fb: int = st["figura"]["B"]
	var v: String = st["vincitore_finale"]
	if fg > fb:
		v = "G"
	elif fb > fg:
		v = "B"
	st["vincitore"] = v
	st["attesa"] = {}
	ev.append({"t": "fine_partita", "vincitore": v, "cima": false})
	_log(st, "%s vince la partita!" % Nome(v))

# ---------------------------------------------------------------- informazioni per l'interfaccia

## Le carte del Balrog che Gandalf può vedere (Astuzia, distacco di 3 caselle, carte rivelate).
static func vede_mano(st: Dictionary, chi: String) -> bool:
	if st["vista"][chi]:
		return true
	return chi == "G" and st["f"].get("astuzia", false)

static func descrivi_attesa(st: Dictionary) -> String:
	var a: Dictionary = st["attesa"]
	if a.is_empty():
		return ""
	match a["tipo"]:
		"gioca":
			if a.get("motivo", "") == "forza":
				return "Gandalf deve rispondere con la carta pescata dal Balrog."
			if a.get("motivo", "") == "incantata":
				return "Il Balrog deve giocare la carta incantata."
			if st["attacco"].is_empty():
				return "%s apre il duello: scegli la carta d'attacco." % Nome(a["chi"])
			return "%s risponde all'attacco." % Nome(a["chi"])
		"incanto":
			return "Gandalf: il Balrog deve giocare ora la carta incantata?"
		"magia":
			return "Gandalf: prendi questa carta del Balrog per il finale?"
		"frusta":
			return "Il Balrog sceglie quale sua carta riusare con la Frusta."
		"difesa":
			return "Gandalf mette una carta nello spazio vuoto (non conta)."
		"riserva":
			return "%s sceglie %d cart%s per il duello finale." % [Nome(a["chi"]), a["quante"], "a" if a["quante"] == 1 else "e"]
		"inizio":
			return "%s decide chi inizia il %s." % [Nome(a["chi"]), "duello finale" if st["duello"] == 4 else "duello %d" % st["duello"]]
		"avanti":
			return "Fine del duello."
	return ""
