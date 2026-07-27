import json
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="foresee — Italian zone electricity prices", layout="wide")

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
MERCATO = "MGP"  # unica fonte oggi (ENTSO-E non espone i mercati infragiornalieri)
GIORNI_STORICO_MOSTRATI = 3  # più domani (tratteggiato) più dopodomani (spazio vuoto)
PALETTE = px.colors.qualitative.Plotly

st.caption(f"Codice e storico completo della campagna di raccolta su [GitHub]({GITHUB_REPO_URL})")


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

df_mercato = df[df["mercato"] == MERCATO]

ultimo_controllo = load_last_update()
info_col1, info_col2 = st.columns(2)
with info_col1:
    st.caption(
        f"Dati disponibili fino al: **{df_mercato['datetime'].max().strftime('%d/%m/%Y %H:%M')}** "
        f"— campagna di raccolta dati dal {df_mercato['data'].min().strftime('%d/%m/%Y')}"
    )
with info_col2:
    if ultimo_controllo:
        ora_controllo = pd.Timestamp(ultimo_controllo["last_check"]).strftime("%d/%m/%Y %H:%M:%S")
        st.caption(f"Ultimo controllo pipeline: **{ora_controllo}**")
    else:
        st.caption("Ultimo controllo pipeline: non ancora disponibile")

# Individua dinamicamente le colonne di prezzo/zona presenti nei dati
colonne_zona = [
    c for c in df_mercato.columns
    if c not in ("data", "ora", "utc", "mercato", "datetime") and df_mercato[c].dtype != object
]
zone_sel = st.multiselect("Zone", colonne_zona, default=colonne_zona)
colore_zona = {zona: PALETTE[i % len(PALETTE)] for i, zona in enumerate(zone_sel)}

# Finestra mostrata: gli ultimi N giorni "storici" (oggi incluso) + domani
# (tratteggiato, il giorno-prima pubblicato oggi) + dopodomani lasciato
# vuoto apposta, come spazio riservato per un futuro modulo di previsione.
# Tutto lo storico raccolto resta comunque intero nel CSV su GitHub: qui
# (grafico e tabella qui sotto) si filtra solo la vista.
adesso = pd.Timestamp.now(tz=TZ).tz_localize(None)  # avanza ad ogni refresh della dashboard
oggi = adesso.normalize()  # confine di calendario tra "storico" e "giorno-prima"
inizio_finestra = oggi - pd.Timedelta(days=GIORNI_STORICO_MOSTRATI - 1)
fine_domani = oggi + pd.Timedelta(days=2) - pd.Timedelta(minutes=1)  # fine di "domani"
fine_dopodomani = oggi + pd.Timedelta(days=3) - pd.Timedelta(minutes=1)  # per lo spazio vuoto

df_finestra = df_mercato[
    (df_mercato["datetime"] >= inizio_finestra) & (df_mercato["datetime"] <= fine_domani)
]

if zone_sel:
    if df_finestra.empty:
        st.info(
            f"Nessun dato nella finestra {inizio_finestra.strftime('%d/%m')} – "
            f"{fine_domani.strftime('%d/%m')} per le zone selezionate."
        )
    else:
        fig = go.Figure()
        for zona in zone_sel:
            serie = df_finestra[["datetime", zona]].dropna().sort_values("datetime")
            storico = serie[serie["datetime"] <= oggi]
            domani = serie[serie["datetime"] > oggi]
            if not storico.empty and not domani.empty:
                # Ripete l'ultimo punto storico come primo punto della tratta
                # tratteggiata, cosi' le due linee restano visivamente connesse.
                domani = pd.concat([storico.iloc[[-1]], domani], ignore_index=True)
            colore = colore_zona[zona]
            if not storico.empty:
                fig.add_trace(go.Scatter(
                    x=storico["datetime"], y=storico[zona], mode="lines", name=zona,
                    legendgroup=zona, line=dict(color=colore),
                ))
            if not domani.empty:
                fig.add_trace(go.Scatter(
                    x=domani["datetime"], y=domani[zona], mode="lines", name=zona,
                    legendgroup=zona, showlegend=storico.empty,
                    line=dict(color=colore, dash="dot"),
                ))

        fig.add_vline(
            x=adesso, line_dash="dot", line_color="gray",
            annotation_text=f"Adesso {adesso.strftime('%H:%M')}",
        )
        fig.add_annotation(
            x=oggi + pd.Timedelta(days=2.5), y=0.5, yref="paper",
            text="Previsioni<br>(prossimamente)", showarrow=False,
            font=dict(color="lightgray", size=12),
        )
        fig.update_xaxes(range=[inizio_finestra, fine_dopodomani], title_text="Data")
        fig.update_yaxes(title_text="€/MWh")
        fig.update_layout(
            title=f"Andamento prezzi — {MERCATO} (ultimi {GIORNI_STORICO_MOSTRATI} giorni + domani)",
        )
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Seleziona almeno una zona per vedere il grafico.")

with st.expander("Dati grezzi — stessa finestra mostrata nel grafico"):
    st.dataframe(df_finestra.drop(columns="datetime"), use_container_width=True)

st.subheader("Distribuzione mensile dei prezzi (ultimi 2 anni)")
due_anni_fa = oggi - pd.DateOffset(years=2)
df_2anni = df_mercato[(df_mercato["datetime"] >= due_anni_fa) & (df_mercato["datetime"] <= adesso)]

if zone_sel:
    if df_2anni.empty:
        st.info("Nessun dato storico disponibile negli ultimi 2 anni per le zone selezionate.")
    else:
        box_df = df_2anni.melt(id_vars="datetime", value_vars=zone_sel, var_name="zona", value_name="prezzo")
        box_df["mese"] = box_df["datetime"].dt.strftime("%Y-%m")
        fig_box = px.box(
            box_df, x="mese", y="prezzo", color="zona",
            color_discrete_map=colore_zona,
            labels={"prezzo": "€/MWh", "mese": "Mese", "zona": "Zona"},
        )
        fig_box.update_xaxes(tickangle=45)
        st.plotly_chart(fig_box, use_container_width=True)
else:
    st.info("Seleziona almeno una zona per vedere la distribuzione mensile.")
