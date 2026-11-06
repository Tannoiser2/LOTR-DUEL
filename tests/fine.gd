extends SceneTree
## Foto delle carte scoperte e della fine partita.
var main
func _initialize():
	main = load("res://scenes/main.tscn").instantiate()
	root.add_child(main)
	_run.call_deferred()
func _run():
	await process_frame
	main._nuova("ia", "G", 1, 4242)
	await create_timer(0.5).timeout
	main.st["vista"]["G"] = true
	main.occupato = 0.0
	main._aggiorna()
	await create_timer(0.5).timeout
	root.get_viewport().get_texture().get_image().save_png("/tmp/shot_scoperte.png")
	main.st["vista"]["G"] = false
	var ia := IA.new(1, 7)
	var passi := 0
	while not Motore.finita(main.st) and passi < 400:
		passi += 1
		var a: Dictionary = main.st["attesa"]
		if a.is_empty():
			break
		var d: Dictionary = (ia if (a["chi"] == "G" or a["chi"] == "") else main.ia).scegli(main.st)
		if Motore.finita(main.st):
			break
		# l'ultima decisione passa dall'interfaccia, per vedere l'animazione finale
		var copia := Motore.copia(main.st)
		Motore.applica(copia, d)
		if Motore.finita(copia):
			main.occupato = 0.0
			main._applica(d)
			break
		Motore.applica(main.st, d)
		main.decisioni.append(d)
	main.scena.metti_figure(main.st["figura"]["G"], main.st["figura"]["B"])
	for t in [1.5, 3.2, 8.0]:
		await create_timer(t - (0.0 if t == 1.5 else (1.5 if t == 3.2 else 3.2))).timeout
		root.get_viewport().get_texture().get_image().save_png("/tmp/shot_fine_%s.png" % str(t))
	quit()
