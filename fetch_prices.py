"""
Scarica i prezzi zonali del mercato del giorno prima (MGP) dell'energia
elettrica italiana dalla ENTSO-E Transparency Platform, e li accumula in un CSV.

La libreria non ufficiale `mercati-energetici` (usata in precedenza) si basava
su un endpoint privato dell'app mobile GME che è stato dismesso/protetto: il
progetto upstream è archiviato dal 2025-08-12 e non è più utilizzabile da
nessuno, non solo da questo progetto. ENTSO-E è la piattaforma ufficiale
europea a cui il GME stesso trasmette gli esiti del mercato del giorno prima,
richiede solo una registrazione gratuita (vedi README) e non ha le
restrizioni di rete dell'endpoint precedente.

Nota: ENTSO-E espone solo l'equivalente del mercato del giorno prima (MGP),
non i mercati infragiornalieri MI1-MI7 che forniva la vecchia API. Dal
2025-10-01 (riforma europea SDAC) questo mercato pubblica i prezzi a
risoluzione di 15 minuti (96 valori/giorno) invece che oraria: la libreria
`entsoe-py` restituisce automaticamente la risoluzione corretta in base alla
data, quindi la colonna "ora" qui sotto è una stringa "HH:MM" (non un intero
1-24) proprio per restare corretta in entrambi i regimi.

Attenzione al cambio dall'ora legale a quella solare (fine ottobre): l'ora
locale si ripete davvero due volte (le 02:00, o i suoi quarti d'ora,
accadono due volte). "data"+"ora" da soli non bastano quindi a identificare
in modo univoco una riga: per questo c'è anche la colonna "utc" (timestamp
UTC, sempre univoco), usata per la deduplicazione idempotente invece delle
colonne locali. Senza questo accorgimento, un'ora reale di dati verrebbe
scartata per errore ogni anno scambiandola per un duplicato.

Caratteristiche chiave:
- IDEMPOTENTE: se lo lanci più volte sullo stesso giorno, non duplica i dati.
- AUTO-RIPARANTE: ogni esecuzione controlla qual è l'ultima data presente
  nel CSV e scarica tutti i giorni mancanti fino a oggi (incluso "domani",
  se il mercato del giorno prima per domani è già stato pubblicato), più un
  margine di alcuni giorni indietro (GIORNI_MARGINE_RICONTROLLO) per colmare
  automaticamente eventuali buchi dovuti a pubblicazioni in ritardo lato
  ENTSO-E. Se lo scheduler (GitHub Actions) salta un'esecuzione o il tuo PC
  è spento per giorni, al run successivo il buco viene colmato da solo.
- Ad ogni esecuzione, riuscita o meno nel trovare dati nuovi, viene
  aggiornato `data/last_update.json` con l'orario dell'ultimo controllo.
  Lo script gira una volta al giorno (vedi workflow): la risoluzione a 15
  minuti riguarda la granularità dei prezzi pubblicati dal mercato, non la
  frequenza con cui ha senso scaricarli, che restano pubblicati una volta
  al giorno. È la dashboard (app.py), non questo script, che si aggiorna
  ogni 15 minuti — solo per riflettere visivamente l'orario corrente.

Uso:
    ENTSOE_API_TOKEN=<token> python fetch_prices.py
"""

import json
import os
from datetime import date, timedelta

import pandas as pd
from entsoe import EntsoePandasClient
from entsoe.exceptions import NoMatchingDataError

DATA_DIR = "data"
DATA_FILE = os.path.join(DATA_DIR, "prezzi_zonali.csv")
LAST_UPDATE_FILE = os.path.join(DATA_DIR, "last_update.json")

# Zone di mercato italiane (nomenclatura GME) -> codice area ENTSO-E
ZONES = {
    "NORD": "IT_NORD",
    "CNOR": "IT_CNOR",
    "CSUD": "IT_CSUD",
    "SUD": "IT_SUD",
    "SICI": "IT_SICI",
    "SARD": "IT_SARD",
    "CALA": "IT_CALA",
}

MERCATO = "MGP"
TZ = "Europe/Rome"

MIN_START_DATE = date(2024, 1, 1)  # da dove partire se il CSV non esiste ancora

# Margine di ri-controllo: quanti giorni PRIMA dell'ultima data presente nel
# CSV vengono comunque richiesti di nuovo ad ogni run. Serve a colmare buchi
# dovuti a pubblicazioni in ritardo da parte di ENTSO-E: se in un dato giorno
# l'API restituisce un intervallo con un giorno mancante nel mezzo (es. il
# 13/8 non ancora pubblicato mentre il 14/8 si', gia' successo in pratica),
# il segnalibro (ultima data presente) avanzerebbe comunque fino al 14/8,
# scavalcando per sempre il 13/8 - il codice controllava solo "ho ricevuto
# qualcosa", non "ho ricevuto ogni giorno richiesto". Ri-controllando sempre
# gli ultimi giorni (idempotente, non crea duplicati) un buco del genere
# viene ritrovato e colmato automaticamente non appena il dato arriva.
GIORNI_MARGINE_RICONTROLLO = 5


def last_date_in_file():
    """Ultima data già presente nel CSV, o None se il file non esiste ancora."""
    if not os.path.exists(DATA_FILE):
        return None
    df = pd.read_csv(DATA_FILE, usecols=["data"])
    if df.empty:
        return None
    return pd.to_datetime(df["data"]).dt.date.max()


def fetch_range(client, start, end):
    """Scarica i prezzi di tutte le zone per il periodo [start, end] incluso
    (risoluzione oraria o a 15 minuti a seconda della data, vedi entsoe-py)."""
    start_ts = pd.Timestamp(start, tz=TZ)
    end_ts = pd.Timestamp(end, tz=TZ) + pd.Timedelta(days=1) - pd.Timedelta(minutes=1)

    series_per_zona = {}
    for zona, area_code in ZONES.items():
        try:
            series = client.query_day_ahead_prices(area_code, start=start_ts, end=end_ts)
        except NoMatchingDataError:
            print(f"  [skip] {zona}: nessun dato pubblicato per questo periodo")
            continue
        series_per_zona[zona] = series
        print(f"  [ok]   {zona}: {len(series)} valori")

    if not series_per_zona:
        return pd.DataFrame()

    df = pd.concat(series_per_zona, axis=1)
    df.index.name = "datetime"
    df = df.reset_index()
    df["data"] = df["datetime"].dt.strftime("%Y-%m-%d")
    df["ora"] = df["datetime"].dt.strftime("%H:%M")
    # Timestamp UTC univoco: "data"+"ora" locali da soli non bastano a
    # distinguere le due occorrenze reali della stessa ora nel giorno del
    # cambio dall'ora legale a quella solare.
    df["utc"] = df["datetime"].dt.tz_convert("UTC").dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    df["mercato"] = MERCATO
    df = df.drop(columns="datetime")
    colonne = ["data", "ora", "utc", "mercato"] + list(ZONES.keys())
    return df[[c for c in colonne if c in df.columns]]


def write_last_update(esito, righe_aggiunte, errore=None):
    """Registra data/ora dell'ultimo controllo, che tu abbia trovato dati
    nuovi o no: e' cosi' che la dashboard sa quando e' stato interrogato
    per l'ultima volta ENTSO-E, distinto da "fino a quando" arrivano i dati."""
    payload = {
        "last_check": pd.Timestamp.now(tz=TZ).isoformat(),
        "esito": esito,  # "nuovi_dati" | "nessun_dato_nuovo" | "errore"
        "righe_aggiunte": righe_aggiunte,
    }
    if errore:
        payload["errore"] = str(errore)
    with open(LAST_UPDATE_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def write_github_output(new_data_found, n_new_rows, ultima_data_mgp):
    """Se lo script gira dentro GitHub Actions, espone dei valori che il
    workflow può leggere per decidere se inviare l'email di notifica."""
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return  # non stiamo girando dentro Actions (es. run locale): si ignora
    with open(output_path, "a") as f:
        f.write(f"new_data={'true' if new_data_found else 'false'}\n")
        f.write(f"n_new_rows={n_new_rows}\n")
        f.write(f"ultima_data_mgp={ultima_data_mgp}\n")


def main():
    api_key = os.environ.get("ENTSOE_API_TOKEN")
    if not api_key:
        raise SystemExit(
            "Variabile d'ambiente ENTSOE_API_TOKEN mancante.\n"
            "Registrati gratuitamente su https://transparency.entsoe.eu e "
            "richiedi un token API (istruzioni nel README), poi:\n"
            "  - in locale: ENTSOE_API_TOKEN=<token> python fetch_prices.py\n"
            "  - su GitHub Actions: aggiungilo come secret del repository."
        )
    client = EntsoePandasClient(api_key=api_key)

    os.makedirs(DATA_DIR, exist_ok=True)

    last = last_date_in_file()
    if last:
        # Riparte qualche giorno prima dell'ultima data vista, per colmare
        # automaticamente eventuali buchi da pubblicazioni in ritardo (vedi
        # commento su GIORNI_MARGINE_RICONTROLLO). Mai prima di MIN_START_DATE.
        start = max(MIN_START_DATE, last + timedelta(days=1) - timedelta(days=GIORNI_MARGINE_RICONTROLLO))
    else:
        start = MIN_START_DATE
    end = date.today() + timedelta(days=1)  # includi "domani" se già pubblicato

    if start > end:
        print("Nessun nuovo giorno da scaricare, tutto aggiornato.")
        write_last_update("nessun_dato_nuovo", 0)
        write_github_output(False, 0, last)
        return

    print(f"Scarico dati da {start} a {end} (inclusi)...")
    new_data = fetch_range(client, start, end)

    if new_data.empty:
        print("Nessun dato nuovo restituito dall'API in questo intervallo.")
        write_last_update("nessun_dato_nuovo", 0)
        write_github_output(False, 0, last)
        return

    if os.path.exists(DATA_FILE):
        old_data = pd.read_csv(DATA_FILE)
        combined = pd.concat([old_data, new_data], ignore_index=True)
    else:
        old_data = pd.DataFrame()
        combined = new_data

    # Rimuove eventuali duplicati (idempotenza), usando il timestamp UTC come
    # chiave univoca (non "data"+"ora" locali, ambigue nel giorno del cambio
    # dall'ora legale a quella solare). Tutto lo storico raccolto viene
    # sempre conservato: non si scarta mai nulla, si aggiunge soltanto.
    combined = combined.drop_duplicates(subset=["utc", "mercato"], keep="last")
    combined = combined.sort_values(["utc"]).reset_index(drop=True)
    righe_aggiunte = len(combined) - len(old_data)
    combined.to_csv(DATA_FILE, index=False)
    print(f"Salvate {len(combined)} righe totali in {DATA_FILE} ({righe_aggiunte} nuove)")

    ultima_data_mgp = new_data["data"].max()
    write_last_update("nuovi_dati" if righe_aggiunte > 0 else "nessun_dato_nuovo", righe_aggiunte)
    write_github_output(righe_aggiunte > 0, righe_aggiunte, ultima_data_mgp)


if __name__ == "__main__":
    main()
