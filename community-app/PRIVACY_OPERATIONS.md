# Richieste privacy della community — procedura operativa

Questa procedura riguarda soltanto ERNEST Community. Il canale ordinario è communication@ernest-project.eu; prendere in carico anche richieste riconoscibili ricevute altrove. Gli strumenti assistono la referente autorizzata e non decidono automaticamente se accogliere una richiesta.

## 1. Ricezione e verifica

- Assegna un riferimento senza dati personali, ad esempio `R-2026-001`; conserva nella corrispondenza riservata data di ricezione, richiesta e scadenza del riscontro. Le richieste in attesa si gestiscono qui; il pannello registra le operazioni effettivamente eseguite.
- Cerca l’account nel pannello. Non confermarne l’esistenza a una persona non verificata.
- Se la richiesta è già adeguatamente autenticata, non ripetere inutilmente la verifica. Altrimenti scrivi alla **casella verificata memorizzata nell’account**, chiedendo una conferma riferita al numero e al tipo di richiesta. Non usare automaticamente il Reply-To del messaggio ricevuto.
- Conserva il riscontro nella corrispondenza riservata. Il modulo annota metodo e data: le spunte **non verificano automaticamente l’identità**. Non chiedere password, codici MFA o documenti d’identità come prassi ordinaria.
- Casella non accessibile, rappresentanti o dubbi: concorda un metodo proporzionato con il riferimento privacy competente prima di procedere; il nickname da solo non basta.

Testo per la conferma: «Abbiamo ricevuto la richiesta [riferimento] di [operazione]. Per confermarla, rispondi a questo messaggio indicando il riferimento e l’operazione. Non inviare password o codici. Se non l’hai presentata tu, segnalacelo.» L’invio resta manuale.

## 2. Operazione riservata

Accedi a `/admin/` con password e secondo fattore. Apri l’utente e **Gestisci una richiesta verificata**. Inserisci riferimento, date, metodo di verifica e riscrivi il nickname interessato. Controlla l’ambito della richiesta prima di confermare.

- **Copia dei dati:** scarica un JSON comprensibile relativo al solo account. Contiene profilo, tentativi, punteggi, timbri e scadenze delle sessioni; esclude password, hash, token, identificativi di sessione e segreti MFA. Le risposte già eliminate non vengono ricostruite. Controlla il file prima della consegna: la copia va accompagnata dal riscontro e dalle informazioni privacy pertinenti; non è da sola una risposta giuridicamente completa.
- **Rettifica:** correggi nickname e/o email. Per cambiare email verifica prima, separatamente, il controllo della nuova casella e confermalo nel modulo. Non si modificano punteggi o privilegi. Il salvataggio viene riletto e controllato; le sessioni memorizzate dell’account vengono eliminate. La rettifica non riattiva un account disattivato.
- **Cancellazione:** elimina account, email associata, tentativi, risultati, timbri derivati e sessioni riconducibili all’account dal database attivo. Controlla che account, email e tentativi non esistano più. Un errore annulla la transazione. Nessun dato di altri account viene cancellato.

I riferimenti sono univoci: un secondo invio dello stesso modulo non ripete l’operazione. Se i dati dell’account sono cambiati nel frattempo, la pagina scade e deve essere ricaricata. Gli account amministrativi sono esclusi da rettifica/cancellazione tramite questi strumenti: richiedono gestione separata con continuità dell’accesso amministrativo. L’esportazione di un account amministrativo è anch’essa da gestire separatamente.

## 3. Controllo e riscontro

Apri **Operazioni privacy**, controlla l’esito e scarica la ricevuta. Dopo un’esportazione, il download non prova che il file sia stato consegnato. Invia il riscontro attraverso il canale verificato, poi annota nella ricevuta la data effettiva di risposta. Non inserire nel registro password, documenti o il testo delle email.

Rispondi senza ingiustificato ritardo e, ordinariamente, entro un mese dalla ricezione. Il pannello mostra la data corrispondente del mese successivo; non la ricalcola dalla verifica dell’identità. Eventuali proroghe, eccezioni o rifiuti richiedono valutazione e riscontro appropriati, non un automatismo del software. [Indicazioni del Garante](https://www.garanteprivacy.it/regolamentoue/diritti-degli-interessati).

Il registro contiene riferimento, date, metodo, operatore, account interessato, azione ed esito. Dopo cancellazione non conserva nickname o email del soggetto, ma l’identificativo tecnico e la data di creazione necessari a distinguere l’account in caso di ripristino. Anche questi riferimenti sono riservati. Nella configurazione attuale il registro viene cancellato alla fine di aprile 2028 con gli altri dati: rivalutare il termine con il titolare prima della scadenza, se occorre conservare evidenza per un periodo diverso. I file scaricati e la corrispondenza restano da custodire ed eliminare secondo la procedura approvata; non vengono cancellati dal CronJob dell’app.

## 4. Backup e ripristino

La cancellazione non modifica direttamente backup, log CERN o registri del servizio email. Descrivi questo limite nel riscontro, senza promettere la scomparsa immediata da ogni copia.

Conserva le ricevute firmate di cancellazione in uno spazio riservato approvato, separato dal database che potrebbe essere ripristinato, mai in Git o nel sito pubblico. Prima di riaprire un database ripristinato:

```sh
python manage.py reapply_privacy_deletions /percorso/riservato/ricevuta.json
python manage.py reapply_privacy_deletions /percorso/riservato/ricevuta.json --apply
python manage.py cleanup_community
```

Il primo comando verifica firme e conteggi senza modifiche. Il secondo riapplica solo cancellazioni già attestate, confrontando identificativo **e data di creazione**; ignora account già assenti. Una ricevuta alterata non è accettata. Occorre la chiave di firma dell’app che ha emesso la ricevuta (gestita tramite i Secret CERN e gli eventuali meccanismi di rotazione): se manca, la verifica si arresta, senza aggirarla. Il 12 settembre 2026 è stata completata una prova su un clone ottenuto da un backup CERN DBOD, con riavvio dell’app e riapplicazione di una cancellazione sintetica. Esiti, confini della prova e procedura ripetibile: [RECOVERY_REHEARSAL.md](RECOVERY_REHEARSAL.md).

## Configurazione tecnica

`PRIVACY_OPERATOR_USERNAME` indica il solo account designato. Vuoto disabilita questi strumenti. L’account deve anche essere attivo, staff e autenticato con TOTP; il solo ruolo superuser non supera questa restrizione. Il gruppo di gestione CERN non concede automaticamente accesso al pannello privacy.

Applicare la migrazione `0004_privacyoperation` prima di abilitare gli strumenti. Aggiornare anche l’immagine del CronJob di conservazione. Nessuna esportazione viene salvata dal server su disco o inviata automaticamente; niente dati personali nei manifest, nelle ricevute pubbliche di rilascio o nei log di verifica.
