extends SceneTree
## Controlla le animazioni dei modelli nel gioco e scatta una foto a metà attacco.
func _initialize():
	var s := Scena3D.new()
	root.add_child(s)
	_run.call_deferred(s)
func _run(s):
	await process_frame
	s.metti_figure(4, 4)
	s.visuale(1)
	for chi in ["G", "B"]:
		var ap: AnimationPlayer = s.animatori.get(chi)
		print("ANIM ", chi, " ", ap.get_animation_list() if ap else "nessun AnimationPlayer", " in corso: ", ap.current_animation if ap else "")
	for i in 30: await process_frame
	print("ANIM luce prima ", s.bastone_luce.global_position)
	s.anima("G", "attacco")
	s.anima("B", "attacco")
	await create_timer(0.55).timeout
	print("ANIM luce durante ", s.bastone_luce.global_position)
	root.get_viewport().get_texture().get_image().save_png("/tmp/shot_anim.png")
	print("ANIM dopo: ", s.animatori["G"].current_animation, " / coda ", s.animatori["G"].get_queue())
	quit()
