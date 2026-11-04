extends SceneTree
## Foto della sola scena 3D, figure sui gradini indicati: godot --path . -s res://tests/foto3d.gd -- <gradino G> <gradino B> <visuale>
func _initialize():
	var s := Scena3D.new()
	root.add_child(s)
	_run.call_deferred(s)
func _run(s):
	var a := OS.get_cmdline_user_args()
	await process_frame
	s.metti_figure(int(a[0]), int(a[1]))
	s.visuale(int(a[2]))
	for i in 40: await process_frame
	s.scambio("G", "B", [0, 2], [1], [3])
	for i in 18: await process_frame
	root.get_viewport().get_texture().get_image().save_png("/tmp/shot_3d_%s.png" % a[2])
	quit()
