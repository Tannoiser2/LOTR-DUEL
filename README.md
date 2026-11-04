# Il Signore degli Anelli – Il Duello (versione digitale)

Versione digitale per uso personale di *Lord of the Rings: The Duel* (Peter Neugebauer, Kosmos / Rio Grande 2002,
illustrazioni di John Howe): Gandalf e il Balrog si affrontano sul ponte di Khazad-dûm in tre duelli e un finale.

Si gioca qui: https://tannoiser2.github.io/LOTR-DUEL/ (e, con i segreti Cloudflare, su `lotr-duel.ludoteca-digitale.com`).

## Cosa c'è

- **Regole complete** dal regolamento ufficiale: confronto riga per riga dei simboli, distacco di 3 caselle (mano
  scoperta), fine del duello con l'eccezione dell'area negativa, gradini sul ponte (1/2/3), carte messe da parte per
  il finale, vittoria anticipata in cima al ponte, e tutte le 11 carte speciali con i loro casi particolari
  (Specchio contro Difesa e Frusta, Ira, Magia e Inganno senza effetto nel finale, Incantesimo nel finale…).
- **Le 54 carte del gioco**, con le 11 speciali ricomposte in italiano. I valori dei simboli sono ricontrollati sulle
  immagini: il modulo TTS sbagliava le carte 20, 50 e 54.
- **Ponte 3D**: abisso di lava, colonne di Moria, Gandalf, il Balrog e il ponte modellati in Blender
  (`tools/modelli_blender.py`), luci del bastone e del fuoco, fulmini, palle di fuoco, scintille quando i simboli si
  parano, effetti per ogni carta speciale, e lo sconfitto che precipita nell'abisso. Vista ruotabile col mouse.
- **Avversario computer** su tre livelli (Apprendista, Stregone, Maia): non sbircia le carte nascoste, le "indovina"
  più volte e valuta la risposta migliore dell'avversario.
- **Due giocatori sullo stesso dispositivo** con schermata di passaggio, e **partite online** con stanze di 4 lettere
  su Firebase; **salvataggio** automatico sul dispositivo e su Firebase.

## File

- `scripts/motore.gd` – le regole: tutto lo stato in un dizionario, decisioni numerate (stessa sequenza = stessa partita).
- `scripts/dati.gd` – le 54 carte; `scripts/ia.gd` – il computer; `scripts/regole.gd` – il regolamento in italiano.
- `scripts/scena3d.gd` – il ponte 3D e gli effetti; `scripts/main.gd` – menu e interfaccia; `scripts/rete.gd` – Firebase.
- `tools/componi_carte.py` – ricompone le carte dal modulo TTS; `tools/modelli_blender.py` – costruisce i modelli 3D.
- `firebase/database.rules.json` – regole del database (radice `lotrduel`, da unire a quelle del progetto condiviso).
- `ludoteca/` – scheda e copertina per la ludoteca.

## Prove

```
godot --headless --path . -s res://tests/sim.gd -- 30            # 30 partite IA contro IA
python3 tools/controlla_glifi.py                                   # ogni carattere esiste nei font
xvfb-run godot --path . -s res://tests/foto.gd -- partita 3        # screenshot dell'interfaccia
python3 tests/firebase_mock.py 8765 &                              # finto Firebase per la prova online
```

## Pubblicazione

Solo su richiesta: Actions → *Pubblica* → *Run workflow*, oppure un commit con `[pubblica]` nel messaggio.
