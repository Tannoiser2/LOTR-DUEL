## Dati delle 54 carte: simboli magici a sinistra (difesa) e a destra (attacco), dall'alto in basso.
## Valori ricontrollati sulle immagini delle carte (il modulo TTS sbagliava le carte 20, 50 e 54).
class_name Dati
extends RefCounted

const CARTE := {
	8: {"lato": "G", "sx": [1, 0, 1, 0], "dx": [0, 1, 0, 1], "spec": "equilibrio", "nome": "Equilibrio di Gandalf", "testo": "Dopo lo scambio sposta i segnalini energia in base alla loro posizione."},
	9: {"lato": "G", "sx": [1, 1, 1, 1], "dx": [0, 0, 0, 1], "spec": "astuzia", "nome": "Astuzia di Gandalf", "testo": "Il Balrog deve giocare il resto di questo duello con la mano scoperta sul tavolo."},
	10: {"lato": "G", "sx": [0, 0, 0, 0], "dx": [0, 0, 0, 0], "spec": "specchio", "nome": "Specchio di Gandalf", "testo": "Il Balrog deve difendersi dalla forza dell'ultima carta che ha giocato. Se era una carta speciale, il suo effetto non si ripete."},
	11: {"lato": "G", "sx": [0, 0, 1, 1], "dx": [1, 0, 0, 1], "spec": "magia", "nome": "Magia di Gandalf", "testo": "Gandalf può costringere una futura carta del Balrog a diventare una delle 3 carte per il duello finale. Il Balrog gioca allora una nuova carta."},
	12: {"lato": "G", "sx": [0, 1, 0, 1], "dx": [1, 0, 0, 1], "spec": "ira", "nome": "Ira di Gandalf", "testo": "La prossima carta speciale che il Balrog gioca in questo duello perde il suo effetto, ma non la sua forza magica."},
	13: {"lato": "G", "sx": [1, 0, 0, 1], "dx": [0, 1, 1, 0], "spec": "incantesimo", "nome": "Incantesimo di Gandalf", "testo": "Gandalf prende a caso una carta dalla mano del Balrog e la mette scoperta sul tavolo. Gandalf decide quando il Balrog la gioca."},
	14: {"lato": "B", "sx": [0, 0, 0, 0], "dx": [0, 0, 0, 0], "spec": "frusta", "nome": "Frusta del Balrog", "testo": "Il Balrog riusa una carta già giocata (non speciale). Metti questa carta nello spazio rimasto vuoto."},
	15: {"lato": "B", "sx": [1, 0, 0, 1], "dx": [0, 1, 1, 0], "spec": "forza", "nome": "Forza del Balrog", "testo": "Il Balrog pesca a caso una carta dalla mano di Gandalf, che Gandalf deve giocare come risposta a questa carta."},
	16: {"lato": "B", "sx": [1, 1, 0, 0], "dx": [1, 0, 1, 1], "spec": "difesa", "nome": "Difesa del Balrog", "testo": "Sposta l'ultima carta giocata da Gandalf come risposta a questa carta. Gandalf mette una carta qualsiasi della sua mano nello spazio vuoto."},
	17: {"lato": "B", "sx": [0, 1, 0, 1], "dx": [0, 1, 1, 0], "spec": "inganno", "nome": "Inganno del Balrog", "testo": "Il Balrog pesca a caso una carta dalla mano di Gandalf e la mette da parte come una delle 3 carte di Gandalf per il duello finale."},
	18: {"lato": "B", "sx": [0, 1, 0, 1], "dx": [1, 0, 1, 0], "spec": "potenza", "nome": "Potenza del Balrog", "testo": "Dopo lo scambio le figure sul ponte determinano lo spostamento dei segnalini energia."},
	19: {"lato": "G", "sx": [0, 1, 1, 1], "dx": [1, 0, 1, 1], "spec": "", "nome": "Gandalf", "testo": ""},
	20: {"lato": "G", "sx": [1, 1, 0, 1], "dx": [0, 0, 1, 1], "spec": "", "nome": "Gandalf", "testo": ""},
	21: {"lato": "G", "sx": [1, 0, 1, 1], "dx": [1, 1, 1, 1], "spec": "", "nome": "Gandalf", "testo": ""},
	22: {"lato": "G", "sx": [0, 0, 0, 1], "dx": [1, 1, 1, 1], "spec": "", "nome": "Gandalf", "testo": ""},
	23: {"lato": "G", "sx": [0, 1, 1, 0], "dx": [1, 0, 0, 1], "spec": "", "nome": "Gandalf", "testo": ""},
	24: {"lato": "G", "sx": [1, 1, 1, 1], "dx": [1, 0, 0, 1], "spec": "", "nome": "Gandalf", "testo": ""},
	25: {"lato": "G", "sx": [1, 0, 1, 1], "dx": [1, 1, 0, 1], "spec": "", "nome": "Gandalf", "testo": ""},
	26: {"lato": "G", "sx": [1, 1, 0, 0], "dx": [0, 0, 1, 1], "spec": "", "nome": "Gandalf", "testo": ""},
	27: {"lato": "G", "sx": [0, 0, 1, 1], "dx": [1, 1, 1, 0], "spec": "", "nome": "Gandalf", "testo": ""},
	28: {"lato": "G", "sx": [1, 1, 1, 1], "dx": [0, 1, 1, 0], "spec": "", "nome": "Gandalf", "testo": ""},
	29: {"lato": "G", "sx": [0, 1, 1, 1], "dx": [1, 1, 1, 1], "spec": "", "nome": "Gandalf", "testo": ""},
	30: {"lato": "G", "sx": [1, 0, 0, 0], "dx": [0, 1, 1, 1], "spec": "", "nome": "Gandalf", "testo": ""},
	31: {"lato": "G", "sx": [0, 0, 1, 0], "dx": [1, 1, 0, 1], "spec": "", "nome": "Gandalf", "testo": ""},
	32: {"lato": "G", "sx": [0, 1, 1, 1], "dx": [1, 0, 1, 0], "spec": "", "nome": "Gandalf", "testo": ""},
	33: {"lato": "G", "sx": [0, 0, 0, 1], "dx": [0, 1, 1, 0], "spec": "", "nome": "Gandalf", "testo": ""},
	34: {"lato": "G", "sx": [0, 0, 0, 0], "dx": [0, 0, 0, 0], "spec": "trance", "nome": "Trance di Gandalf", "testo": ""},
	35: {"lato": "G", "sx": [1, 1, 0, 0], "dx": [0, 1, 1, 1], "spec": "", "nome": "Gandalf", "testo": ""},
	36: {"lato": "G", "sx": [1, 0, 0, 0], "dx": [0, 1, 0, 0], "spec": "", "nome": "Gandalf", "testo": ""},
	37: {"lato": "G", "sx": [0, 1, 0, 0], "dx": [1, 1, 1, 1], "spec": "", "nome": "Gandalf", "testo": ""},
	38: {"lato": "G", "sx": [0, 0, 0, 1], "dx": [0, 0, 1, 0], "spec": "", "nome": "Gandalf", "testo": ""},
	39: {"lato": "G", "sx": [0, 0, 1, 0], "dx": [1, 0, 0, 1], "spec": "", "nome": "Gandalf", "testo": ""},
	40: {"lato": "B", "sx": [0, 0, 0, 1], "dx": [1, 1, 1, 0], "spec": "", "nome": "Balrog", "testo": ""},
	41: {"lato": "B", "sx": [1, 1, 0, 1], "dx": [0, 0, 1, 1], "spec": "", "nome": "Balrog", "testo": ""},
	42: {"lato": "B", "sx": [1, 0, 1, 0], "dx": [0, 1, 0, 1], "spec": "", "nome": "Balrog", "testo": ""},
	43: {"lato": "B", "sx": [1, 1, 1, 1], "dx": [1, 0, 0, 1], "spec": "", "nome": "Balrog", "testo": ""},
	44: {"lato": "B", "sx": [0, 1, 0, 0], "dx": [1, 0, 1, 1], "spec": "", "nome": "Balrog", "testo": ""},
	45: {"lato": "B", "sx": [0, 1, 1, 0], "dx": [1, 0, 1, 1], "spec": "", "nome": "Balrog", "testo": ""},
	46: {"lato": "B", "sx": [0, 1, 1, 0], "dx": [0, 0, 1, 1], "spec": "", "nome": "Balrog", "testo": ""},
	47: {"lato": "B", "sx": [1, 0, 1, 0], "dx": [1, 1, 0, 1], "spec": "", "nome": "Balrog", "testo": ""},
	48: {"lato": "B", "sx": [1, 0, 0, 1], "dx": [0, 1, 1, 0], "spec": "", "nome": "Balrog", "testo": ""},
	49: {"lato": "B", "sx": [1, 1, 1, 0], "dx": [1, 1, 1, 1], "spec": "", "nome": "Balrog", "testo": ""},
	50: {"lato": "B", "sx": [1, 1, 0, 1], "dx": [1, 1, 1, 1], "spec": "", "nome": "Balrog", "testo": ""},
	51: {"lato": "B", "sx": [1, 1, 1, 1], "dx": [0, 1, 1, 0], "spec": "", "nome": "Balrog", "testo": ""},
	52: {"lato": "B", "sx": [1, 1, 1, 1], "dx": [1, 1, 1, 1], "spec": "", "nome": "Balrog", "testo": ""},
	53: {"lato": "B", "sx": [1, 0, 0, 0], "dx": [1, 1, 0, 0], "spec": "", "nome": "Balrog", "testo": ""},
	54: {"lato": "B", "sx": [1, 1, 1, 0], "dx": [0, 1, 1, 1], "spec": "", "nome": "Balrog", "testo": ""},
	55: {"lato": "B", "sx": [0, 0, 1, 0], "dx": [1, 1, 1, 1], "spec": "", "nome": "Balrog", "testo": ""},
	56: {"lato": "B", "sx": [0, 0, 0, 1], "dx": [0, 0, 1, 0], "spec": "", "nome": "Balrog", "testo": ""},
	57: {"lato": "B", "sx": [1, 1, 0, 1], "dx": [1, 1, 1, 0], "spec": "", "nome": "Balrog", "testo": ""},
	58: {"lato": "B", "sx": [0, 0, 0, 1], "dx": [1, 1, 1, 1], "spec": "", "nome": "Balrog", "testo": ""},
	59: {"lato": "B", "sx": [0, 0, 0, 0], "dx": [0, 0, 0, 0], "spec": "trance", "nome": "Trance del Balrog", "testo": ""},
	60: {"lato": "B", "sx": [1, 0, 1, 1], "dx": [1, 1, 0, 0], "spec": "", "nome": "Balrog", "testo": ""},
	61: {"lato": "B", "sx": [1, 0, 0, 0], "dx": [0, 1, 0, 0], "spec": "", "nome": "Balrog", "testo": ""},
}

static func carta(id: int) -> Dictionary:
	return CARTE[id]

static func lato(id: int) -> String:
	return CARTE[id]["lato"]

static func sx(id: int) -> Array:
	return CARTE[id]["sx"]

static func dx(id: int) -> Array:
	return CARTE[id]["dx"]

## Chiave della carta speciale ("" per le carte normali; "trance" non ha effetti).
static func spec(id: int) -> String:
	return CARTE[id]["spec"]

static func speciale(id: int) -> bool:
	var s: String = CARTE[id]["spec"]
	return s != "" and s != "trance"

static func mazzo(l: String) -> Array:
	var out := []
	for id in CARTE:
		if CARTE[id]["lato"] == l:
			out.append(id)
	out.sort()
	return out

## Numero di simboli magici (per l'IA e per l'ordinamento).
static func forza(id: int) -> int:
	var n := 0
	for x in CARTE[id]["sx"]:
		n += x
	for x in CARTE[id]["dx"]:
		n += x
	return n
