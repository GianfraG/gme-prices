# Prezzi Mercato Elettrico GME — raccolta + dashboard

Sistema minimo per scaricare quotidianamente i prezzi di tutti i mercati
elettrici italiani (GME) e vederli in un grafico raggiungibile con un link,
senza dipendere dal tuo PC essere acceso.

## Come funziona

- `fetch_prices.py`: scarica i prezzi da tutti i mercati GME (MGP, MI1-MI7...)
  usando la libreria non ufficiale `mercati-energetici`. Ogni volta che gira,
  controlla l'ultima data già salvata e recupera automaticamente tutti i
  giorni mancanti fino a oggi (quindi nessuna perdita dati se salta un run).
- `.github/workflows/daily_fetch.yml`: fa girare lo script ogni giorno sui
  server di GitHub (gratuito), non sul tuo computer. Salva i dati aggiornati
  in `data/prezzi_zonali.csv` dentro il repository stesso.
- `app.py`: dashboard Streamlit che legge quel CSV e mostra i grafici.
  Pubblicata su Streamlit Community Cloud, ottieni un link pubblico che si
  aggiorna da solo ogni volta che arrivano nuovi dati.

## Setup (stasera, ~20-30 minuti)

1. **Crea un repository GitHub** (pubblico, gratuito) e carica tutti questi
   file mantenendo la struttura delle cartelle (incluso `.github/workflows/`).

2. **Attiva GitHub Actions**: di solito è già attivo di default sui repo
   pubblici. Vai su "Actions" nel repo, dovresti vedere il workflow
   "Aggiorna prezzi GME". Lancialo manualmente una prima volta ("Run workflow")
   per popolare subito `data/prezzi_zonali.csv` invece di aspettare il cron
   delle 14:00 UTC.

3. **Pubblica la dashboard**: vai su https://share.streamlit.io , collega il
   tuo account GitHub, seleziona questo repository e il file `app.py`.
   In un paio di minuti ottieni un URL pubblico (tipo
   `https://tuonome-tuoprogetto.streamlit.app`) che puoi aprire da qualunque
   dispositivo. Si aggiorna da solo ogni volta che il workflow fa un nuovo
   commit dei dati.

## Nota importante sul primo avvio

Non conoscendo lo schema esatto restituito dall'API GME per ogni mercato
(la libreria non documenta il formato in dettaglio), `fetch_prices.py` e
`app.py` sono scritti per adattarsi automaticamente alle colonne che
arrivano davvero (via `pandas.json_normalize` e rilevamento dinamico delle
colonne numeriche). Dopo il primo run reale, conviene dare un'occhiata al
CSV generato e, se serve, rifinire i nomi delle colonne nella dashboard:
è il punto giusto per aprire questo progetto in Claude Code e chiedere
di sistemare i dettagli sulla base dei dati veri.

## Il problema "PC spento" — come è risolto

Niente gira più in locale: lo scheduler (GitHub Actions) e la dashboard
(Streamlit Cloud) sono entrambi servizi cloud gratuiti, sempre attivi,
indipendenti dal tuo computer. Il tuo PC serve solo per scrivere il codice,
non per farlo girare.
