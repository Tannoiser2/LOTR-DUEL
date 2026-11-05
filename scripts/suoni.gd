## I suoni del gioco: voci di Gandalf e del Balrog, effetti, e il brontolio della lava di sottofondo.
## Voci ed effetti registrati: Oculus Audio Pack (Meta, CC BY 4.0). Fulmine, frusta, fuoco e lava sintetizzati.
class_name Suoni
extends Node

const DIR := "res://assets/audio/"
var attivo := true
var lettori: Array[AudioStreamPlayer] = []
var lava: AudioStreamPlayer
var drone: AudioStreamPlayer
var cache := {}
var ultima := {}   # per non ripetere sempre la stessa variante

func _ready() -> void:
	for i in 12:
		var p := AudioStreamPlayer.new()
		add_child(p)
		lettori.append(p)
	lava = _sottofondo("lava", -14.0)
	drone = _sottofondo("drone", -24.0)
	var c := ConfigFile.new()
	if c.load("user://audio_lotrduel.cfg") == OK:
		attivo = bool(c.get_value("a", "attivo", true))
	_applica_volume()

func _sottofondo(nome: String, db: float) -> AudioStreamPlayer:
	var p := AudioStreamPlayer.new()
	var s = _stream(nome)
	if s is AudioStreamOggVorbis:
		s = s.duplicate()
		s.loop = true
	p.stream = s
	p.volume_db = db
	add_child(p)
	return p

func _stream(nome: String) -> AudioStream:
	if not cache.has(nome):
		var path := DIR + nome + ".ogg"
		cache[nome] = load(path) if ResourceLoader.exists(path) else null
	return cache[nome]

## Accende o spegne tutto l'audio (la scelta resta sul dispositivo).
func cambia() -> bool:
	attivo = not attivo
	var c := ConfigFile.new()
	c.set_value("a", "attivo", attivo)
	c.save("user://audio_lotrduel.cfg")
	_applica_volume()
	return attivo

func _applica_volume() -> void:
	AudioServer.set_bus_mute(0, not attivo)

func avvia_sottofondo() -> void:
	if not lava.playing:
		lava.play()
	if not drone.playing:
		drone.play()

## Suona un effetto. nome può avere varianti: "balrog_ruggito" sceglie tra balrog_ruggito_1, _2, _3…
func suona(nome: String, db := 0.0, ritardo := 0.0, tono := 1.0) -> void:
	if ritardo > 0.0:
		get_tree().create_timer(ritardo).timeout.connect(func(): suona(nome, db, 0.0, tono))
		return
	var s := _stream(nome)
	if s == null:
		var varianti := []
		for i in range(1, 6):
			if _stream("%s_%d" % [nome, i]) != null:
				varianti.append(i)
		if varianti.is_empty():
			return
		var scelta: int = varianti[randi() % varianti.size()]
		if varianti.size() > 1 and scelta == ultima.get(nome, -1):
			scelta = varianti[(varianti.find(scelta) + 1) % varianti.size()]
		ultima[nome] = scelta
		s = _stream("%s_%d" % [nome, scelta])
	var libero: AudioStreamPlayer = null
	for p in lettori:
		if not p.playing:
			libero = p
			break
	if libero == null:
		libero = lettori[0]
	libero.stream = s
	libero.volume_db = db
	libero.pitch_scale = tono * randf_range(0.96, 1.04)
	libero.play()
