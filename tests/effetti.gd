extends SceneTree
## Foto degli effetti speciali: godot --path . -s res://tests/effetti.gd -- <spec> <secondi>
func _initialize():
	var s := Scena3D.new()
	root.add_child(s)
	_run.call_deferred(s)
func _run(s):
	var a := OS.get_cmdline_user_args()
	await process_frame
	s.metti_figure(3, 3)
	s.visuale(0)
	s.dist = 13.0
	await create_timer(0.5).timeout
	s.speciale(a[0])
	await create_timer(float(a[1])).timeout
	root.get_viewport().get_texture().get_image().save_png("/tmp/eff_%s.png" % a[0])
	quit()
