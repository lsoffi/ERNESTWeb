# Prova separata di recupero dell’app e dei dati

## Prova del 12 settembre 2026

Il recupero viene provato su una copia temporanea CERN DBOD, senza ripristinare il database della community in uso. La copia non è collegata alla Route pubblica e il processo di verifica non riceve il Secret della posta.

- Prova effettuata il **12 settembre 2026** su una copia di un backup dello stesso giorno.
- App recuperata dall’immagine della versione in uso, fissata per digest.
- Script ripetibile: [ops/recovery_drill.py](ops/recovery_drill.py).

**Esito: riuscito.** Il processo temporaneo è terminato correttamente e tutti i controlli seguenti hanno avuto esito positivo. Il resoconto pubblico non contiene endpoint, identificativi di istanze o credenziali.

| Controllo | Esito |
| --- | --- |
| Clone ottenuto dal backup DBOD e connessione TLS verificata | Riuscito |
| Migrazioni e scadenze sulla copia, preservando i risultati degli account confermati | Riuscito |
| Avvio nuovo dell’app e successivo riavvio, con pagina, CSS, JavaScript e logo disponibili | Riuscito |
| Accesso, quiz, punteggio e timbro di un account sintetico | Riuscito |
| Ricomparsa simulata dell’account da una copia precedente e riapplicazione della cancellazione firmata | Riuscito |
| Seconda riapplicazione della stessa cancellazione senza effetti ulteriori | Riuscito |
| Account, email, tentativi e sessione sintetici assenti dopo la cancellazione | Riuscito |
| Risultati degli altri account invariati | Riuscito |

La preparazione della copia ha richiesto circa 15 minuti. I due avvii locali dell’app nel contenitore hanno richiesto circa 0,53 secondi ciascuno; non comprendono creazione del contenitore, recupero dell’immagine o attesa del database. Le migrazioni erano già state applicate durante la prima esecuzione.

La prima esecuzione ha evidenziato un limite della copia JSON usata **nel test**: il serializzatore standard arrotondava la data di creazione dell’account ai millisecondi. La ricevuta richiede correttamente la data esatta e non ha riconosciuto quell’account modificato. Lo strumento di prova ora conserva i microsecondi, come il backup nativo MySQL; un test automatico copre questa proprietà. Non è stata indebolita la verifica delle ricevute.

I processi temporanei sono stati rimossi e la community originale risponde correttamente. Il clone è stato arrestato con successo. La richiesta di eliminazione definitiva ha restituito un errore del servizio anche dopo un secondo tentativo: questa pulizia resta da completare con CERN DBOD. La copia non è stata dichiarata eliminata.

## Cosa verifica il processo

1. Accetta solo un endpoint esplicitamente indicato come clone ERNEST; rifiuta quello di produzione e la porta originale. La connessione mantiene la verifica del certificato TLS CERN.
2. Legge una sintesi interna dei risultati completati degli account confermati. Applica le migrazioni e le scadenze alla copia recuperata, verificando che questi risultati restino invariati.
3. Avvia l’app da zero e la riavvia una seconda volta contro lo stesso database recuperato. Il server ascolta soltanto sull’indirizzo locale del contenitore. Verifica la risposta dell’app e la conservazione dei risultati.
4. Crea nel clone un solo account sintetico con indirizzo `example.invalid`. Prova accesso, quiz, punteggio, timbro e rimozione delle singole risposte a fine quiz.
5. Salva una copia logica **dei soli dati sintetici**, cancella l’account e lo reintroduce da questa copia precedente. Riapplica una ricevuta firmata di cancellazione e verifica che spariscano account, email, tentativi e sessione. Ripete la riapplicazione per verificarne l’idempotenza.
6. Ricontrolla che i risultati degli altri account siano invariati. Nei log scrive soltanto esiti e tempi, senza email, password, risposte, nickname o dump del database.

Il clone DBOD prova il recupero da un backup del servizio. Il passaggio con la copia logica sintetica prova separatamente la riapplicazione delle cancellazioni: non comporta la cancellazione di un account reale né la sua successiva reintroduzione in produzione.

## Ripetere la prova

Dal portale DBOD scegliere **Clones → Create new clone → Clone from backup** sull’istanza della community. Usare esclusivamente i parametri del nuovo clone. Il processo deve utilizzare un’immagine dell’app fissata per digest e una revisione verificata dello script; nessun Service o Route pubblica, nessun Secret SMTP e nessun token Kubernetes montato.

Prima di riaprire un database recuperato per uso reale, applicare le migrazioni, eseguire `cleanup_community`, verificare e riapplicare tutte le ricevute di cancellazione successive al backup. Conservare queste ricevute in uno spazio riservato separato dal database. Le istruzioni sono in [PRIVACY_OPERATIONS.md](PRIVACY_OPERATIONS.md).

A fine prova rimuovere il processo temporaneo ed effettuare l’expire del solo clone. Verificare nel portale l’esito della rimozione e controllare che la community originale risponda ancora.

I tempi di questa prova non costituiscono una garanzia di recupero durante un guasto CERN. Non viene simulata la perdita dell’intero progetto PaaS, dei Secret, delle chiavi di firma o del registro immagini. Il controllo non certifica cifratura a riposo o durata di conservazione dei backup.
