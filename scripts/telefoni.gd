## I telefoni dei giocatori: la TV apre una stanza su Firebase (web/js/ponte.js), mostra il QR code,
## e chi lo inquadra prende le carte di Gandalf o del Balrog sul proprio telefono.
## Fuori dal browser (editor, prove) non fa nulla.
class_name Telefoni
extends Node

signal evento(e: Dictionary)

var lt = null
var codice := ""
var url := ""
var avviata := false

func _ready() -> void:
	if OS.has_feature("web"):
		lt = JavaScriptBridge.get_interface("LT")

## Il ponte JavaScript si carica come modulo: può arrivare dopo l'avvio di Godot, quindi si riprova.
func _ponte():
	if lt == null and OS.has_feature("web"):
		lt = JavaScriptBridge.get_interface("LT")
	return lt

func disponibile() -> bool:
	return OS.has_feature("web")

func avvia() -> void:
	_ponte()
	if lt and not avviata:
		avviata = true
		var prima := ""
		var c = JavaScriptBridge.eval("localStorage.getItem('lotr_stanza') || ''")
		if c != null:
			prima = str(c)
		lt.avvia(prima)

func _process(_d: float) -> void:
	if lt == null:
		if avviata == false:
			return
		_ponte()
		if lt == null:
			return
	var s = lt.preleva()
	if s == null or str(s) == "[]" or str(s) == "":
		return
	var l = JSON.parse_string(str(s))
	if not (l is Array):
		return
	for e in l:
		if e is Dictionary:
			if e.get("e") == "stanza":
				codice = str(e.get("codice", ""))
				url = str(e.get("url", ""))
				JavaScriptBridge.eval("localStorage.setItem('lotr_stanza', %s)" % JSON.stringify(codice))
			evento.emit(e)

func stato(d: Dictionary) -> void:
	if lt and codice != "":
		lt.stato(JSON.stringify(d))

func segreto(uid: String, d: Dictionary) -> void:
	if lt and codice != "":
		lt.segreto(uid, JSON.stringify(d))

func togli(uid: String) -> void:
	if lt:
		lt.togli(uid)

## Il QR code come immagine (moduli neri su bianco, con il margine).
func qr(testo: String, lato := 220) -> Texture2D:
	_ponte()
	if lt == null:
		return null
	var bits := str(lt.qr(testo))
	var n := int(sqrt(bits.length()))
	if n == 0:
		return null
	var m := 4
	var img := Image.create(n + 2 * m, n + 2 * m, false, Image.FORMAT_RGB8)
	img.fill(Color.WHITE)
	for y in n:
		for x in n:
			if bits[y * n + x] == "1":
				img.set_pixel(x + m, y + m, Color.BLACK)
	img.resize(lato, lato, Image.INTERPOLATE_NEAREST)
	return ImageTexture.create_from_image(img)
