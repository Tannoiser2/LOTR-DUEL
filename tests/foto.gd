extends SceneTree
## Screenshot dell'interfaccia: xvfb-run godot --path . -s res://tests/foto.gd -- <modo> [mosse]
## modo: menu | partita (gioca a caso n mosse come Gandalf contro l'IA e scatta) | esito | fine
var main

func _initialize():
	main = load("res://scenes/main.tscn").instantiate()
	root.add_child(main)
	_run.call_deferred()

func shot(nome: String, attesa := 20):
	for i in attesa: await process_frame
	root.get_viewport().get_texture().get_image().save_png("/tmp/shot_%s.png" % nome)
	print("shot ", nome)

func _run():
	var args := OS.get_cmdline_user_args()
	var modo: String = args[0] if args.size() > 0 else "menu"
	var mosse := int(args[1]) if args.size() > 1 else 4
	await shot("menu", 40)
	if modo == "menu":
		quit(); return
	main._nuova("ia", "G", 1, 4242)
	var ia := IA.new(1, 7)
	var fatte := 0
	var passi := 0
	while passi < 6000:
		await process_frame
		passi += 1
		if Motore.finita(main.st):
			break
		if main.occupato > 0.0:
			continue
		var a: Dictionary = main.st["attesa"]
		if a.is_empty():
			continue
		var mio: bool = a["chi"] == "G" or a["chi"] == ""
		if not mio:
			continue
		if modo == "esito" and a["tipo"] == "avanti":
			await shot("esito", 30)
			quit(); return
		if modo == "partita" and fatte >= mosse and a["tipo"] == "gioca":
			# lascia vedere lo scambio in corso
			await shot("partita", 10)
			var dd: Dictionary = ia.scegli(main.st)
			var n0: int = main.st["n"]
			main._applica(dd)
			print("decisione ", dd, " n ", n0, " -> ", main.st["n"], " attesa ", main.st["attesa"].get("tipo"))
			await create_timer(1.6).timeout
			await shot("scambio", 1)
			quit(); return
		main._applica(ia.scegli(main.st))
		fatte += 1
	main._aggiorna()
	await shot("fine", 120)
	quit()
