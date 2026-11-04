## L'avversario guidato dal computer. Non sbircia: le carte nascoste dell'avversario vengono
## "indovinate" più volte tra quelle che potrebbe avere, e per ogni mossa si guarda la risposta
## migliore dell'avversario. Il livello cambia il numero di prove e quanto si sbaglia apposta.
class_name IA
extends RefCounted

var rng := RandomNumberGenerator.new()
var prove := 8        # quante volte si indovinano le carte nascoste
var errore := 0.0     # rumore sulle valutazioni (livello facile)

func _init(livello := 2, seme := 0) -> void:
	rng.seed = seme if seme != 0 else Time.get_ticks_usec()
	match livello:
		0:
			prove = 2
			errore = 1.6
		1:
			prove = 4
			errore = 0.6
		_:
			prove = 10
			errore = 0.0

## Valore di una carta da conservare per il finale.
static func valore_carta(id: int) -> float:
	var v := float(Dati.forza(id))
	match Dati.spec(id):
		"specchio": v += 4.5
		"equilibrio", "potenza": v += 3.0
		"difesa", "frusta": v += 3.0
		"forza", "ira", "incantesimo": v += 2.0
		"astuzia": v += 1.0
		"magia", "inganno": v -= 1.0   # nel finale non hanno effetto
		"trance": v -= 2.0
	return v

## Decide per il giocatore atteso. Restituisce la decisione {"tipo", "v"}.
func scegli(st: Dictionary) -> Dictionary:
	var a: Dictionary = st["attesa"]
	var chi: String = a["chi"]
	match a["tipo"]:
		"avanti":
			return {"tipo": "avanti", "v": true}
		"inizio":
			# chi inizia perde i pareggi e il suo primo attacco non para nulla: meglio far iniziare l'altro
			return {"tipo": "inizio", "v": Motore.altro(chi)}
		"riserva":
			var pool: Array = a["opzioni"].duplicate()
			pool.sort_custom(func(x, y): return valore_carta(x) > valore_carta(y))
			return {"tipo": "riserva", "v": pool.slice(0, a["quante"])}
		"difesa":
			var p: Array = a["opzioni"].duplicate()
			p.sort_custom(func(x, y): return valore_carta(x) < valore_carta(y))
			return {"tipo": "difesa", "v": p[0]}
	var opz: Array = a["opzioni"]
	if opz.size() == 1:
		return {"tipo": a["tipo"], "v": opz[0]}
	var migliore = opz[0]
	var best := -INF
	for o in opz:
		var tot := 0.0
		for k in prove:
			var s2 := _indovina(st, chi)
			tot += _valuta_mossa(s2, chi, {"tipo": a["tipo"], "v": o})
		var val := tot / prove + rng.randf_range(-errore, errore)
		if a["tipo"] == "gioca":
			# conserva le carte forti per il finale, e non sprecare le speciali a vuoto
			val -= 0.06 * valore_carta(o)
		if val > best:
			best = val
			migliore = o
	return {"tipo": a["tipo"], "v": migliore}

## Copia dello stato in cui la mano nascosta dell'avversario è sostituita da carte plausibili.
func _indovina(st: Dictionary, chi: String) -> Dictionary:
	var s2 := st.duplicate(true)
	s2["diario"] = []
	var o := Motore.altro(chi)
	if Motore.vede_mano(st, chi):
		return s2
	var visti := {}
	for r in st["riga"]:
		visti[r["id"]] = true
	for c in st["rivelate"]:
		visti[c] = true
	if st["f"].get("incantata", -1) != -1:
		visti[st["f"]["incantata"]] = true
	if chi == "B" and st["f"].get("ingannata", -1) != -1:
		visti[st["f"]["ingannata"]] = true
	var pool := []
	for c in st["mazzo"][o] + st["mano"][o] + st["riserva"][o] + st["riserva_duello"][o]:
		if not visti.has(c):
			pool.append(c)
	# le carte giocate nei duelli precedenti non sono più nel mazzo: il pool è già giusto
	var n: int = st["mano"][o].size()
	var nuova := []
	# le carte rivelate che sono in mano restano note
	for c in st["mano"][o]:
		if visti.has(c):
			nuova.append(c)
	for i in range(pool.size() - 1, 0, -1):
		var j := rng.randi_range(0, i)
		var t = pool[i]
		pool[i] = pool[j]
		pool[j] = t
	var i2 := 0
	while nuova.size() < n and i2 < pool.size():
		nuova.append(pool[i2])
		i2 += 1
	s2["mano"][o] = nuova
	# le opzioni già calcolate per l'avversario non servono: verranno ricalcolate dal motore
	return s2

## Applica la mossa, lascia rispondere l'avversario nel modo per lui migliore e valuta il risultato.
func _valuta_mossa(s2: Dictionary, chi: String, d: Dictionary) -> float:
	Motore.applica(s2, d)
	var passi := 0
	while passi < 6 and not s2["attesa"].is_empty() and s2["attesa"]["tipo"] != "avanti":
		var a: Dictionary = s2["attesa"]
		if a["tipo"] in ["riserva", "inizio"]:
			break
		var tocca: String = a["chi"]
		if tocca == chi:
			if a["tipo"] == "gioca" and passi > 0:
				break
			# scelte successive dello stesso giocatore (Frusta, ecc.): la più conveniente subito
			var meglio = null
			var mv := -INF
			for o in a["opzioni"]:
				var s3 := s2.duplicate(true)
				Motore.applica(s3, {"tipo": a["tipo"], "v": o})
				var v := _valuta(s3, chi)
				if v > mv:
					mv = v
					meglio = o
			Motore.applica(s2, {"tipo": a["tipo"], "v": meglio})
		else:
			# l'avversario sceglie la risposta peggiore per noi
			var peggio = null
			var pv := INF
			for o in a["opzioni"]:
				var s3 := s2.duplicate(true)
				Motore.applica(s3, {"tipo": a["tipo"], "v": o})
				var v := _valuta(s3, chi)
				if a["tipo"] == "gioca":
					v += 0.06 * valore_carta(o)
				if v < pv:
					pv = v
					peggio = o
			Motore.applica(s2, {"tipo": a["tipo"], "v": peggio})
			if a["tipo"] == "gioca":
				break
		passi += 1
	return _valuta(s2, chi)

## Quanto è buona la situazione per chi: distacco di energia (con i salti di gradini) e ponte.
func _valuta(s: Dictionary, chi: String) -> float:
	var o := Motore.altro(chi)
	var e: Dictionary = s["energia"]
	var diff: int = e[chi] - e[o]
	var v := float(diff)
	# il numero di caselle vuote decide i gradini: premia il superare le soglie
	var vuote: int = abs(diff) - 1
	var gradini := 1 if vuote <= 2 else (2 if vuote <= 4 else 3)
	if diff != 0:
		v += sign(diff) * gradini * 0.8
	if e[o] <= 0 and e[chi] > e[o]:
		v += 1.5
	if e[chi] <= 0 and e[o] > e[chi]:
		v -= 1.5
	v += 3.0 * (s["figura"][chi] - s["figura"][o])
	if s["vincitore"] == chi:
		v += 100.0
	elif s["vincitore"] == o:
		v -= 100.0
	return v
