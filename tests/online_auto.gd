extends SceneTree
## Prova online: due istanze (host = Gandalf, ospite = Balrog) giocano una partita intera sul finto Firebase;
## le decisioni le prende l'IA. Alla fine stampano l'impronta della partita, che deve coincidere.
## LOTR_ROLE=host|guest LOTR_CODEFILE=file  (più FR_DB_URL, FR_AUTH_URL, FR_REFRESH_URL, FR_SESSION)
var main
func _initialize():
	main = load("res://scenes/main.tscn").instantiate()
	root.add_child(main)
	_run.call_deferred()
func _w(s: float):
	await create_timer(s).timeout
func _run():
	await _w(0.3)
	var role := OS.get_environment("LOTR_ROLE")
	var cf := OS.get_environment("LOTR_CODEFILE")
	main._menu_online()
	main.on_nome.text = "Host" if role == "host" else "Ospite"
	main.on_ruolo = "G"
	if role == "host":
		main._online_crea()
		while main.codice == "":
			await _w(0.2)
		var f := FileAccess.open(cf, FileAccess.WRITE)
		f.store_string(main.codice)
		f.close()
		printerr("LOTR stanza ", main.codice)
	else:
		var code := ""
		while code == "":
			if FileAccess.file_exists(cf):
				code = FileAccess.get_file_as_string(cf).strip_edges()
			await _w(0.3)
		main.on_codice.text = code
		main._online_entra()
	var k := 0
	while not main.in_partita:
		await _w(0.3)
		k += 1
		if k % 10 == 0:
			printerr("LOTR attesa ", role, ": ", main.on_stato.text if is_instance_valid(main.on_stato) else "?", " | ", main.net.last_error)
	var ia := IA.new(1, 3 if role == "host" else 4)
	var t0 := Time.get_ticks_msec()
	while not Motore.finita(main.st) and Time.get_ticks_msec() - t0 < 800000:
		await process_frame
		main.occupato = 0.0
		var a: Dictionary = main.st["attesa"]
		if a.is_empty():
			continue
		var mio: bool = a["chi"] == main.io or (a["chi"] == "" and role == "host")
		if mio and main.mostrata == int(main.st["n"]):
			main.mostrata = -5
			await main._applica(ia.scegli(main.st))
	printerr("LOTR fine ", role, " io ", main.io, " n ", main.st["n"], " vince ", main.st["vincitore"], " impronta ", str(main.st["esiti"]).hash(), " ", str(main.st["riga"]).hash())
	quit()
