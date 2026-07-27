import json
import os

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Prezzi Mercato Elettrico GME", layout="wide")

# La raccolta dati (fetch_prices.py) gira una volta al giorno: questo
# auto-refresh serve solo a far avanzare la linea "Adesso" nel grafico e a
# rileggere il CSV se nel frattempo è arrivato un aggiornamento, NON a
# ri-scaricare nulla lato dashboard.
st.markdown('<meta http-equiv="refresh" content="900">', unsafe_allow_html=True)

st.title("foresee")
st.markdown(
    "<p style='margin-top:-12px; color:gray; font-size:1.1rem;'>"
    "Italian zone electricity prices</p>",
    unsafe_allow_html=True,
)

DATA_FILE = "data/prezzi_zonali.csv"
LAST_UPDATE_FILE = "data/last_update.json"
GITHUB_REPO_URL = "https://github.com/GianfraG/gme-prices"
TZ = "Europe/Rome"
GIORNI_STORICO_MOSTRATI = 6  # più il giorno successivo (day-ahead), se pubblicato


@st.cache_data(ttl=300)
def load_data():
    df = pd.read_csv(DATA_FILE, dtype={"ora": str})
    # Il timestamp UTC è univoco (a differenza di "data"+"ora" locali, che si
    # ripetono davvero una volta l'anno nel giorno del cambio dall'ora legale
    # a quella solare): è la base corretta per ordinare/plottare senza
    # sovrapporre per errore due istanti reali distinti.
    df["datetime"] = pd.to_datetime(df["utc"], utc=True).dt.tz_convert(TZ).dt.tz_localize(None)
    df["data"] = pd.to_datetime(df["data"])
    return df


@st.cache_data(ttl=300)
def load_last_update():
    if not os.path.exists(LAST_UPDATE_FILE):
        return None
    with open(LAST_UPDATE_FILE, encoding="utf-8") as f:
        return json.load(f)


try:
    df = load_data()
except FileNotFoundError:
    st.warning(
        "Nessun dato ancora raccolto. Il file data/prezzi_zonali.csv verrà creato "
        "dalla prima esecuzione dello script/workflow di raccolta dati."
    )
    st.stop()

ultimo_controllo = load_last_update()
info_col1, info_col2 = st.columns(2)
with info_col1:
    st.caption(
        f"Dati disponibili fino al: **{df['datetime'].max().strftime('%d/%m/%Y %H:%M')}** "
        f"— campagna di raccolta dati dal {df['data'].min().strftime('%d/%m/%Y')}"
    )
with info_col2:
    if ultimo_controllo:
        ora_controllo = pd.Timestamp(ultimo_controllo["last_check"]).strftime("%d/%m/%Y %H:%M:%S")
        st.caption(f"Ultimo controllo pipeline: **{ora_controllo}**")
    else:
        st.caption("Ultimo controllo pipeline: non ancora disponibile")

col1, col2 = st.columns(2)
with col1:
    mercati_disponibili = sorted(df["mercato"].unique())
    mercato_sel = st.selectbox("Mercato", mercati_disponibili, index=0)
with col2:
    df_mercato = df[df["mercato"] == mercato_sel]
    # Individua dinamicamente le colonne di prezzo/zona presenti nei dati
    colonne_zona = [
        c for c in df_mercato.columns
        if c not in ("data", "ora", "utc", "mercato", "datetime") and df_mercato[c].dtype != object
    ]
    zone_sel = st.multiselect("Zone", colonne_zona, default=colonne_zona)

# Finestra di default mostrata: gli ultimi N giorni di dati "storici" più
# il giorno successivo (il mercato del giorno prima pubblica oggi i prezzi
# di domani). Tutto lo storico raccolto resta comunque intero nel CSV su
# GitHub: qui (grafico e tabella qui sotto) si filtra solo la vista.
adesso = pd.Timestamp.now(tz=TZ).tz_localize(None)  # avanza ad ogni refresh della dashboard
oggi = adesso.normalize()  # confine di calendario tra "storico" e "giorno-prima"
inizio_finestra = oggi - pd.Timedelta(days=GIORNI_STORICO_MOSTRATI - 1)
fine_finestra = oggi + pd.Timedelta(days=2) - pd.Timedelta(minutes=1)  # fino a fine "domani"

df_finestra = df_mercato[
    (df_mercato["datetime"] >= inizio_finestra) & (df_mercato["datetime"] <= fine_finestra)
]

if zone_sel:
    plot_df = df_finestra.melt(id_vars="datetime", value_vars=zone_sel, var_name="zona", value_name="prezzo")
    plot_df["periodo"] = plot_df["datetime"].apply(
        lambda dt: "Giorno-prima (domani)" if dt.normalize() > oggi else "Storico"
    )

    if plot_df.empty:
        st.info(
            f"Nessun dato nella finestra {inizio_finestra.strftime('%d/%m')} – "
            f"{fine_finestra.strftime('%d/%m')} per le zone selezionate."
        )
    else:
        fig = px.line(
            plot_df, x="datetime", y="prezzo", color="zona", line_dash="periodo",
            title=f"Andamento prezzi — {mercato_sel} (ultimi {GIORNI_STORICO_MOSTRATI} giorni + domani)",
            labels={"prezzo": "€/MWh", "datetime": "Data", "periodo": "Periodo"},
        )
        fig.add_vline(
            x=adesso, line_dash="dot", line_color="gray",
            annotation_text=f"Adesso {adesso.strftime('%H:%M')}",
        )
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Seleziona almeno una zona per vedere il grafico.")

with st.expander("Dati grezzi — stessa finestra mostrata nel grafico"):
    st.dataframe(
        df_finestra.drop(columns="datetime"), use_container_width=True,
    )
    st.caption(
        f"Storico completo della campagna di raccolta su GitHub: {GITHUB_REPO_URL}"
    )
