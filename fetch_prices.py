"""
Scarica i prezzi zonali dell'energia elettrica da tutti i mercati GME
(MGP = giorno prima, MI1-MI7 = infragiornaliero, ecc.) usando la libreria
non ufficiale `mercati-energetici`, e li accumula in un CSV.

Caratteristiche chiave:
- IDEMPOTENTE: se lo lanci più volte sullo stesso giorno, non duplica i dati.
- AUTO-RIPARANTE: ogni esecuzione controlla qual è l'ultima data presente
  nel CSV e scarica tutti i giorni mancanti fino a oggi. Se lo scheduler
  (GitHub Actions) salta un'esecuzione o il tuo PC è spento per giorni,
  al run successivo il buco viene colmato da solo.

Uso:
    python fetch_prices.py
"""

import asyncio
import csv
import os
from datetime import date, timedelta

import pandas as pd
from mercati_energetici import MercatiElettrici

DATA_DIR = "data"
DATA_FILE = os.path.join(DATA_DIR, "prezzi_zonali.csv")

# Segmenti di mercato da provare ogni giorno. Se un segmento non è attivo
# in una certa data, la chiamata fallisce silenziosamente e si passa oltre.
MARKETS = ["MGP", "MI-A1", "MI-A2", "MI-A3", "MI1", "MI2", "MI3", "MI4", "MI5", "MI6", "MI7"]

MIN_START_DATE = date(2024, 1, 1)  # da dove partire se il CSV non esiste ancora


def last_date_in_file():
    """Ultima data già presente nel CSV, o None se il file non esiste ancora."""
    if not os.path.exists(DATA_FILE):
        return None
    df = pd.read_csv(DATA_FILE, usecols=["data"])
    if df.empty:
        return None
    return pd.to_datetime(df["data"]).dt.date.max()


def normalize(raw, day, market):
    """Trasforma l'output grezzo dell'API in righe tabellari standard.

    L'output esatto della libreria può variare per struttura (lista di dict
    con una chiave per zona, oppure lista di dict con 'Zona'/'Prezzo'), quindi
    normalizziamo in modo robusto con pandas invece di assumere uno schema fisso.
    """
    if not raw:
        return pd.DataFrame()
    df = pd.json_normalize(raw)
    df["data"] = day.isoformat()
    df["mercato"] = market
    return df


async def fetch_range(start, end):
    """Scarica tutti i mercati per ogni giorno tra start ed end (inclusi)."""
    rows = []
    async with MercatiElettrici() as me:
        # Necessario dalla libreria per accettare i termini d'uso dell'API GME
        await me.get_general_conditions()
        await me.get_disclaimer()

        day = start
        while day <= end:
            for market in MARKETS:
                try:
                    raw = await me.get_prices(market, day)
                except Exception as e:
                    # Mercato non attivo in quel giorno, o errore di rete: si salta
                    print(f"  [skip] {market} {day}: {e}")
                    continue
                df = normalize(raw, day, market)
                if not df.empty:
                    rows.append(df)
                    print(f"  [ok]   {market} {day}: {len(df)} righe")
            day += timedelta(days=1)

    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


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
    os.makedirs(DATA_DIR, exist_ok=True)

    last = last_date_in_file()
    start = (last + timedelta(days=1)) if last else MIN_START_DATE
    end = date.today()

    if start > end:
        print("Nessun nuovo giorno da scaricare, tutto aggiornato.")
        write_github_output(False, 0, last)
        return

    print(f"Scarico dati da {start} a {end} (inclusi)...")
    new_data = asyncio.run(fetch_range(start, end))

    if new_data.empty:
        print("Nessun dato nuovo restituito dall'API in questo intervallo.")
        write_github_output(False, 0, last)
        return

    if os.path.exists(DATA_FILE):
        old_data = pd.read_csv(DATA_FILE)
        combined = pd.concat([old_data, new_data], ignore_index=True)
    else:
        old_data = pd.DataFrame()
        combined = new_data

    # Rimuove eventuali duplicati (idempotenza)
    combined = combined.drop_duplicates()
    righe_aggiunte = len(combined) - len(old_data)
    combined.to_csv(DATA_FILE, index=False)
    print(f"Salvate {len(combined)} righe totali in {DATA_FILE} ({righe_aggiunte} nuove)")

    ultima_data_mgp = new_data[new_data["mercato"] == "MGP"]["data"].max() if "mercato" in new_data else end.isoformat()
    write_github_output(righe_aggiunte > 0, righe_aggiunte, ultima_data_mgp)


if __name__ == "__main__":
    main()
