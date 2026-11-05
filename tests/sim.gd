extends SceneTree
## Partite automatiche IA contro IA: controlla che finiscano sempre e conta i risultati.
## godot --headless --path . -s res://tests/sim.gd -- [partite] [livello G] [livello B]

func _init() -> void:
	var args := OS.get_cmdline_user_args()
	var n := int(args[0]) if args.size() > 0 else 20
	var lg := int(args[1]) if args.size() > 1 else 2
	var lb := int(args[2]) if args.size() > 2 else 2
	var vinte := {"G": 0, "B": 0, "NON FINITA": 0}
	var cima := 0
	var tot := 0
	var spec := {}
	var t0 := Time.get_ticks_msec()
	for p in n:
		var st := Motore.nuova(p * 7919 + 13)
		var ia := {"G": IA.new(lg, p + 1), "B": IA.new(lb, p + 1001)}
		var passi := 0
		while not Motore.finita(st) and passi < 2000:
			var a: Dictionary = st["attesa"]
			if a.is_empty():
				push_error("nessuna decisione attesa ma partita non finita")
				break
			var chi: String = a["chi"] if a["chi"] != "" else "G"
			var d: Dictionary = ia[chi].scegli(st)
			var n0: int = st["n"]
			var ev := Motore.applica(st, d)
			if st["n"] == n0:
				push_error("decisione rifiutata %s" % [d])
				print(a)
				break
			for e in ev:
				if e["t"] == "speciale":
					spec[e["spec"]] = spec.get(e["spec"], 0) + 1
			passi += 1
			_controlla(st)
		tot += passi
		var v: String = st["vincitore"] if st["vincitore"] != "" else "NON FINITA"
		vinte[v] += 1
		if st["esiti"].size() < 4:
			cima += 1
		if p < 2 or v == "NON FINITA":
			print("partita %d: vince %s, passi %d, ponte G%d B%d, esiti %s" % [p, v, passi, st["figura"]["G"], st["figura"]["B"], st["esiti"]])
			if p == 0:
				for l in st["diario"]:
					print("   ", l)
	print("RISULTATI ", vinte, " finite in cima prima del finale: ", cima, " passi medi ", tot / max(1, n), " speciali ", spec, " ms ", Time.get_ticks_msec() - t0)
	quit()

## Controlli di coerenza: nessuna carta persa o duplicata; ogni carta giocabile si vede nella mano.
func _controlla(st: Dictionary) -> void:
	var a: Dictionary = st["attesa"]
	if not a.is_empty() and a["tipo"] in ["gioca", "difesa"]:
		var visibili: Array = st["mano"][a["chi"]].duplicate()
		if a["chi"] == "B" and st["f"].get("incantata", -1) != -1:
			visibili.append(st["f"]["incantata"])
		for o in a["opzioni"]:
			if not (o in visibili):
				push_error("carta giocabile %d non visibile nella mano di %s" % [o, a["chi"]])
	for chi in ["G", "B"]:
		var tutte := []
		tutte += st["mazzo"][chi] + st["mano"][chi] + st["riserva"][chi] + st["riserva_duello"][chi]
		if chi == "B" and st["f"].get("incantata", -1) != -1:
			tutte.append(st["f"]["incantata"])
		var visti := {}
		for c in tutte:
			if visti.has(c):
				push_error("carta duplicata %d" % c)
			visti[c] = true
