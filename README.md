# Prezzi Mercato Elettrico Italiano (GME)

Raccolta automatica e dashboard dei prezzi zonali orari del mercato del
giorno prima (MGP) dell'energia elettrica italiana, pubblicati dal
Gestore dei Mercati Energetici (GME) e ripresi ufficialmente dalla
piattaforma europea ENTSO-E Transparency Platform.

> **Nota:** il progetto usava inizialmente la libreria non ufficiale
> `mercati-energetici`, basata su un endpoint privato dell'app mobile GME.
> Quell'endpoint è stato dismesso/protetto e il progetto upstream è stato
> archiviato dal maintainer il 12/08/2025: non funziona più per nessuno.
> Per questo la raccolta dati ora usa l'API ufficiale ENTSO-E, che copre
> il mercato del giorno prima (equivalente MGP) ma non i mercati
> infragiornalieri MI1-MI7 che forniva la vecchia fonte.

## Cosa fa

- Una volta al giorno (tramite GitHub Actions), dopo che il mercato del
  giorno prima ha pubblicato i risultati, scarica da ENTSO-E i prezzi di
  tutte le 7 zone di mercato italiane. Dal 2025-10-01 questo mercato
  pubblica a risoluzione di 15 minuti (96 valori/giorno) invece che
  oraria — è una proprietà del dato, non della frequenza di raccolta:
  un solo download al giorno è sufficiente, la pubblicazione stessa
  avviene una volta al giorno.
- Accumula **tutto** lo storico raccolto in un unico dataset
  (`data/prezzi_zonali.csv`), senza mai scartare dati: è pensato come una
  campagna di raccolta continua, non solo come cache degli ultimi giorni.
- Registra anche l'orario dell'ultima esecuzione della pipeline
  (`data/last_update.json`).
- Mostra i dati raccolti in una dashboard web interattiva, che si
  aggiorna da sola ogni 15 minuti — non per riscaricare dati, ma solo per
  far avanzare la linea "Adesso" nel grafico e rileggere il CSV nel caso
  sia arrivato un aggiornamento.

## Come è organizzato

| File | Cosa fa |
|---|---|
| `fetch_prices.py` | Scarica i prezzi da ENTSO-E (una volta al giorno) e li aggiunge al dataset |
| `app.py` | Dashboard web (Streamlit), si auto-aggiorna ogni 15 minuti |
| `requirements.txt` | Librerie Python necessarie |
| `.github/workflows/daily_fetch.yml` | Esegue `fetch_prices.py` una volta al giorno |
| `data/prezzi_zonali.csv` | L'intero storico raccolto (creato al primo utilizzo) |
| `data/last_update.json` | Orario dell'ultima esecuzione della pipeline |

## Aggiornamento dei dati

La pipeline gira da sola una volta al giorno (14:00 UTC, dopo la
pubblicazione dei risultati), senza bisogno di intervento manuale. Se un
run salta per qualche motivo, quello successivo recupera automaticamente
tutti i giorni mancanti: non è necessario monitorarlo attivamente.

La dashboard invece si aggiorna ogni 15 minuti per conto proprio (un
refresh lato pagina, non un nuovo download): serve solo a far avanzare la
linea "Adesso" nel grafico e a mostrare subito eventuali dati arrivati
nel frattempo, non a interrogare ENTSO-E più spesso.

## Usare la dashboard

La dashboard mostra due controlli:
- **Mercato**: quale segmento di mercato visualizzare (al momento solo MGP)
- **Zone**: quali zone di mercato (Nord, Centro-Sud, Sicilia, ecc.)
  mostrare nel grafico, selezionabili singolarmente

Il grafico mostra di default gli ultimi 6 giorni più il giorno successivo
(il "giorno prima" pubblicato oggi per domani), con uno stile tratteggiato
che distingue i prezzi già storicizzati da quelli del giorno-prima appena
pubblicato, e una linea verticale "Adesso" che segna il momento preciso
in cui stai guardando la dashboard (avanza ogni 15 minuti). Questa è solo
una finestra di visualizzazione: l'intero storico raccolto dalla campagna
resta sempre disponibile, senza filtri, nella tabella "Dati grezzi" in
fondo alla pagina.

## Ottenere un token API ENTSO-E (gratuito)

1. Vai su https://transparency.entsoe.eu, clicca "Sign In" > "Register" e
   crea un account (poi verificalo tramite il link inviato via email).
2. Invia una email a **transparency@entsoe.eu** con oggetto
   **"RESTful API access"** e nel corpo l'indirizzo email con cui ti sei
   registrato.
3. Attendi l'email di conferma (di norma entro 3 giorni lavorativi).
4. Rientra su transparency.entsoe.eu, vai su "My Account" e genera un
   Security Token: sarà il valore da usare come `ENTSOE_API_TOKEN`.

## Eseguire il progetto in locale

pip install -r requirements.txt
ENTSOE_API_TOKEN=<il-tuo-token> python fetch_prices.py   # scarica/aggiorna il dataset
streamlit run app.py                                      # apre la dashboard in locale

## Configurare GitHub Actions

Nel repository GitHub, vai su Settings > Secrets and variables > Actions
e crea un secret chiamato `ENTSOE_API_TOKEN` con il token ottenuto sopra.
Il workflow `.github/workflows/daily_fetch.yml` lo legge automaticamente.

## Fonte dei dati

I dati provengono dalla ENTSO-E Transparency Platform (piattaforma
ufficiale europea di trasparenza dei mercati elettrici), a cui il GME
trasmette gli esiti del mercato del giorno prima. Il GME e' l'ente che
gestisce i mercati elettrici italiani; non va confuso con il GSE
(Gestore Servizi Energetici), che si occupa invece di incentivi alle
rinnovabili.
