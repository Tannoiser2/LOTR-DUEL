extends SceneTree
## Controlla che ogni suono usato dal gioco esista e si carichi.
func _initialize():
	var s := Suoni.new()
	root.add_child(s)
	await process_frame
	var nomi := ["carta", "balrog_ruggito", "balrog_ruggito_forte", "balrog_dolore", "balrog_caduta", "balrog_vittoria",
		"gandalf_sforzo", "gandalf_dolore", "gandalf_caduta", "fulmine", "fuoco", "impatto", "parata", "magia",
		"soffio_1", "frusta", "passo", "musica_vittoria", "musica_sconfitta", "lava", "drone"]
	var mancano := []
	for n in nomi:
		if s._stream(n) == null and s._stream(n + "_1") == null:
			mancano.append(n)
		s.suona(n)
	print("AUDIO mancano: ", mancano, " lava in ciclo: ", s.lava.stream.loop if s.lava.stream else "?")
	quit()
