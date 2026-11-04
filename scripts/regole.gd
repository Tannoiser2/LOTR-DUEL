## Il regolamento in italiano, mostrato dal pulsante «Regole».
class_name Regole
extends RefCounted

const TESTO := """[b]Scopo del gioco[/b]
Gandalf e il Balrog si affrontano sul ponte di Khazad-dûm in quattro duelli: tre duelli preliminari e un duello finale. Chi vince un duello sale i gradini del ponte. Alla fine vince chi è più in alto; a parità vince chi ha vinto il duello finale. Se dopo il secondo o il terzo duello una figura raggiunge la cima del ponte (gradino 5), la partita finisce subito.

[b]Le carte[/b]
Ogni giocatore ha 27 carte. Ogni carta ha quattro posti per i simboli magici su ciascun lato: i simboli sul lato [i]destro[/i] sono la forza d'attacco, quelli sul lato [i]sinistro[/i] la forza di difesa. Alcune carte hanno un testo: sono le carte speciali. Due carte (una per parte) non hanno né simboli né testo: sono le carte della Trance, il punto debole del duello.

[b]Il duello[/b]
All'inizio di ogni duello preliminare si pescano 9 carte e i segnalini energia tornano sulla casella bianca del tracciato. Il primo duello lo apre Gandalf, giocando una carta d'attacco. L'avversario risponde con una carta: si confrontano riga per riga il lato destro della carta d'attacco con il lato sinistro della carta che risponde.
– Simbolo su entrambe le carte: si annullano.
– Simbolo su una carta sola: chi non ha il simbolo in quella riga scende di una casella sul tracciato dell'energia.
– Nessun simbolo: non succede nulla.
La carta che ha risposto diventa subito il nuovo attacco, e tocca all'altro rispondere. Le carte speciali prima si confrontano normalmente, poi si applica il loro testo.

[b]Distacco di 3 caselle[/b]
Se dopo uno scambio tra i due segnalini ci sono 3 o più caselle vuote, chi sta più in alto può guardare le carte in mano all'avversario (nel gioco le vedi scoperte in alto).

[b]Fine del duello[/b]
Il duello finisce quando ciascuno ha giocato 6 carte (9 nel duello finale) oppure quando un segnalino entra nell'area negativa. Se entrambi i segnalini sono sulla stessa casella negativa e restano carte da giocare, si continua finché uno è più in basso dell'altro. Se il duello finisce nell'area negativa, il testo dell'ultima carta speciale non si applica.
Vince chi ha il segnalino più in alto e sale sul ponte: con 0, 1 o 2 caselle vuote tra i segnalini sale di 1 gradino, con 3 o 4 di 2 gradini, con 5 o più di 3 gradini. In caso di pareggio perde chi ha iniziato il duello e il vincitore sale di 1 gradino.
Le 3 carte rimaste in mano si mettono da parte per il duello finale (se ne restano di più se ne scelgono 3). Le carte giocate escono dal gioco.

[b]Secondo e terzo duello[/b]
Le figure restano dove sono, i segnalini tornano sulla casella bianca, si pescano 9 nuove carte e chi ha perso il duello precedente decide chi inizia.

[b]Il duello finale[/b]
Ciascuno gioca con le 9 carte messe da parte. I segnalini partono dalla casella arancione in cima al tracciato. Decide chi inizia chi ha la figura più in basso sul ponte (a parità, chi ha perso l'ultimo duello). Il vincitore sale di 1, 2 o 3 gradini come negli altri duelli.

[b]Le carte speciali di Gandalf[/b]
[i]Equilibrio[/i]: dopo lo scambio, se Gandalf è più in alto sul tracciato sale di 1; se i segnalini sono pari Gandalf sale di 1 e il Balrog scende di 1; se Gandalf è più in basso sale di 2 e il Balrog scende di 1. Nessun segnalino può salire oltre la casella di partenza del duello.
[i]Astuzia[/i]: il Balrog gioca il resto del duello a mano scoperta; le carte che mette da parte per il finale restano note a Gandalf.
[i]Specchio[/i]: neutralizza l'attacco del Balrog e glielo rimanda: il Balrog deve difendersi dalla sua stessa ultima carta, come se fosse di Gandalf. Una carta speciale che risponde allo Specchio perde l'effetto (tranne la Frusta). Se lo Specchio è l'ultima carta del duello non si muove nulla.
[i]Magia[/i]: da ora Gandalf può prendere una sola delle carte che il Balrog gioca in questo duello: quella carta va tra le carte del Balrog per il finale e il Balrog ne gioca un'altra. Nel duello finale non ha effetto.
[i]Ira[/i]: la prossima carta speciale del Balrog in questo duello perde l'effetto (la Frusta no, e l'Ira resta).
[i]Incantesimo[/i]: Gandalf prende a caso una carta dalla mano del Balrog e la mette scoperta sul tavolo; prima di ogni giocata del Balrog decide se il Balrog deve giocare proprio quella. Se non viene giocata, il Balrog può tenerla per il finale; nel finale, se Gandalf non la chiama mai, è l'ultima carta del Balrog.

[b]Le carte speciali del Balrog[/b]
[i]Frusta[/i]: il Balrog riprende una sua carta già giocata (non speciale), la mette in fondo alla fila come risposta all'attacco e mette la Frusta nel posto rimasto vuoto. La Frusta non ha simboli: se il Balrog non ha carte da riprendere, conta come una carta senza simboli.
[i]Forza[/i]: il Balrog pesca a caso una carta dalla mano di Gandalf, che Gandalf deve giocare come risposta.
[i]Difesa[/i]: l'ultima carta di Gandalf viene spostata a rispondere alla Difesa (e si confronta di nuovo); Gandalf mette una carta qualsiasi della sua mano nel posto vuoto, e quella non conta. Uno Specchio spostato così mantiene il suo effetto.
[i]Inganno[/i]: il Balrog pesca a caso una carta dalla mano di Gandalf e la mette da parte come una delle 3 carte di Gandalf per il finale. Nel duello finale non ha effetto.
[i]Potenza[/i]: dopo lo scambio, se la figura del Balrog è più in alto sul ponte il Balrog sale di 1 sul tracciato; a parità il Balrog sale di 1 e Gandalf scende di 1; se il Balrog è più in basso sale di 2 e Gandalf scende di 1.

[b]Comandi[/b]
Clicca una carta illuminata per giocarla; passa sopra le carte per ingrandirle. Trascina con il mouse per ruotare la vista del ponte, rotellina per avvicinarti; il pulsante «Visuale» cambia inquadratura.
"""
