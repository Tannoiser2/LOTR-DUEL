extends SceneTree
## Gioca come Balrog contro il computer finché non tocca giocare la carta incantata, poi la clicca dall'interfaccia.
var main
func _initialize():
	main = load("res://scenes/main.tscn").instantiate()
	root.add_child(main)
	_run.call_deferred()
func _run():
	await process_frame
	var trovate := 0
	for seme in range(1, 200):
		main._nuova("ia", "B", 1, seme)
		var ia := IA.new(1, 5)
		var passi := 0
		while not Motore.finita(main.st) and passi < 400:
			passi += 1
			var a: Dictionary = main.st["attesa"]
			if a.is_empty():
				break
			if a["chi"] == "B" and a.get("motivo", "") == "incantata":
				main.occupato = 0.0
				main.passaggio = ""
				main._aggiorna()
				var id: int = a["opzioni"][0]
				var bottoni := []
				for c in main.box_mano.get_children():
					if c is TextureButton and c.pressed.get_connections().size() > 0:
						bottoni.append(c)
				var n0: int = main.st["n"]
				for b in bottoni:
					b.pressed.emit()
				print("INCANTATA seme ", seme, " carta ", id, " cliccabili ", bottoni.size(), " applicata ", main.st["n"] > n0)
				trovate += 1
				break
			var chi: String = a["chi"] if a["chi"] != "" else "G"
			var d: Dictionary = (main.ia if chi == "G" else ia).scegli(main.st)
			var ev := Motore.applica(main.st, d)
			main.decisioni.append(d)
		if trovate >= 3:
			break
	quit()
