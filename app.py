import json
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="foresee — Italian zone electricity prices", layout="wide", page_icon="⚡")

# La raccolta dati (fetch_prices.py) gira una volta al giorno: questo
# auto-refresh serve solo a far avanzare la linea "Adesso" nel grafico e a
# rileggere il CSV se nel frattempo è arrivato un aggiornamento, NON a
# ri-scaricare nulla lato dashboard.
st.markdown('<meta http-equiv="refresh" content="900">', unsafe_allow_html=True)

DATA_FILE = "data/prezzi_zonali.csv"
LAST_UPDATE_FILE = "data/last_update.json"
GITHUB_REPO_URL = "https://github.com/GianfraG/gme-prices"
TZ = "Europe/Rome"
MERCATO = "MGP"  # unica fonte oggi (ENTSO-E non espone i mercati infragiornalieri)
GIORNI_STORICO_MOSTRATI = 3  # più domani (tratteggiato) più dopodomani (spazio vuoto)

# Palette categoriale (validata per contrasto/daltonismo), ordine fisso non ciclico
ZONE_COLORS = {
    "NORD": "#3987e5",  # blue
    "CNOR": "#d95926",  # orange
    "CSUD": "#199e70",  # aqua
    "SUD": "#c98500",   # yellow
    "SICI": "#d55181",  # magenta
    "SARD": "#008300",  # green
    "CALA": "#9085e9",  # violet
}
INK_SECONDARY = "#c3c2b7"
INK_MUTED = "#898781"
GRID = "#2c2c2a"
AXIS = "#383835"

CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=INK_SECONDARY, family="system-ui, -apple-system, Segoe UI, sans-serif"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, bgcolor="rgba(0,0,0,0)"),
    margin=dict(t=40, l=10, r=10, b=10),
    hovermode="x unified",
)
AXIS_STYLE = dict(gridcolor=GRID, linecolor=AXIS, tickfont=dict(color=INK_MUTED), zeroline=False)

st.markdown(
    f"""
    <h1 style="font-size:2.6rem; font-weight:800; letter-spacing:-0.02em; margin-bottom:0;">foresee</h1>
    <p style="color:{INK_SECONDARY}; font-size:1.05rem; margin-top:0; margin-bottom:0.4rem;">
      Italian zone electricity prices
    </p>
    <p style="color:{INK_MUTED}; font-size:0.85rem; margin-bottom:1.4rem;">
      <a href="{GITHUB_REPO_URL}" style="color:{ZONE_COLORS['NORD']}; text-decoration:none; font-weight:600;">
        GianfraG/gme-prices
      </a>
      &nbsp;·&nbsp;codice e storico completo della campagna di raccolta
    </p>
    """,
    unsafe_allow_html=True,
)


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

# Finestra mostrata: gli ultimi N giorni "storici" (oggi incluso) + domani
# (tratteggiato, il giorno-prima pubblicato oggi) + dopodomani lasciato
# vuoto apposta, come spazio riservato per un futuro modulo di previsione.
# Tutto lo storico raccolto resta comunque intero nel CSV su GitHub: qui
# (grafico e tabella qui sotto) si filtra solo la vista.
adesso = pd.Timestamp.now(tz=TZ).tz_localize(None)  # avanza ad ogni refresh della dashboard
oggi = adesso.normalize()
inizio_finestra = oggi - pd.Timedelta(days=GIORNI_STORICO_MOSTRATI - 1)
fine_domani = oggi + pd.Timedelta(days=2) - pd.Timedelta(minutes=1)  # fine di "domani"
fine_dopodomani = oggi + pd.Timedelta(days=3) - pd.Timedelta(minutes=1)  # per lo spazio vuoto

df_finestra = df_mercato[
    (df_mercato["datetime"] >= inizio_finestra) & (df_mercato["datetime"] <= fine_domani)
]

st.markdown("#### Andamento prezzi")

if zone_sel:
    if df_finestra.empty:
        st.info(
            f"Nessun dato nella finestra {inizio_finestra.strftime('%d/%m')} – "
            f"{fine_domani.strftime('%d/%m')} per le zone selezionate."
        )
    else:
        fig = go.Figure()
        for zona in zone_sel:
            colore = ZONE_COLORS.get(zona, INK_SECONDARY)
            serie = df_finestra[["datetime", zona]].dropna().sort_values("datetime")
            # Il confine tra continuo e tratteggiato e' l'istante esatto di
            # "adesso" (cio' che e' gia' accaduto vs cio' che deve ancora
            # accadere), non il confine di calendario tra oggi e domani.
            avvenuto = serie[serie["datetime"] <= adesso]
            futuro = serie[serie["datetime"] > adesso]
            if not avvenuto.empty and not futuro.empty:
                # Ripete l'ultimo punto avvenuto come primo punto della tratta
                # futura, cosi' le due linee restano visivamente connesse.
                futuro = pd.concat([avvenuto.iloc[[-1]], futuro], ignore_index=True)
            hover = "%{y:.1f} €/MWh<extra>" + zona + "</extra>"
            if not avvenuto.empty:
                fig.add_trace(go.Scatter(
                    x=avvenuto["datetime"], y=avvenuto[zona], mode="lines", name=zona,
                    legendgroup=zona, line=dict(color=colore, width=2), hovertemplate=hover,
                ))
            if not futuro.empty:
                fig.add_trace(go.Scatter(
                    x=futuro["datetime"], y=futuro[zona], mode="lines", name=zona,
                    legendgroup=zona, showlegend=avvenuto.empty,
                    line=dict(color=colore, width=2, dash="dot"), hovertemplate=hover,
                ))

        fig.add_vline(x=adesso, line_dash="dot", line_color=INK_MUTED)
        fig.add_annotation(
            x=oggi + pd.Timedelta(days=2.5), y=0.5, yref="paper",
            text="previsioni<br>in arrivo", showarrow=False,
            font=dict(color=INK_MUTED, size=12),
        )
        fig.update_xaxes(range=[inizio_finestra, fine_dopodomani], **AXIS_STYLE)
        fig.update_yaxes(title_text="€/MWh", **AXIS_STYLE)
        fig.update_layout(**CHART_LAYOUT, height=460)
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Seleziona almeno una zona per vedere il grafico.")

with st.expander("Dati grezzi"):
    st.dataframe(df_finestra.drop(columns="datetime"), use_container_width=True)

st.markdown("#### Distribuzione mensile dei prezzi")

due_anni_fa = oggi - pd.DateOffset(years=2)
df_2anni = df_mercato[(df_mercato["datetime"] >= due_anni_fa) & (df_mercato["datetime"] <= adesso)]

if zone_sel:
    if df_2anni.empty:
        st.info("Nessun dato storico disponibile per le zone selezionate.")
    else:
        box_long = df_2anni.melt(id_vars="datetime", value_vars=zone_sel, var_name="zona", value_name="prezzo")
        box_long["mese"] = box_long["datetime"].dt.strftime("%Y-%m")

        # Statistiche pre-calcolate lato server (quartili/baffi per zona/mese,
        # convenzione Tukey 1.5*IQR): al grafico arrivano ~168 righe aggregate
        # invece di ~300.000 punti grezzi, molto piu' leggero da renderizzare
        # nel browser (tutto vettorizzato con pandas, niente loop Python).
        grouped = box_long.groupby(["zona", "mese"])["prezzo"]
        stats = grouped.quantile(0.25).rename("q1").reset_index()
        stats["mediana"] = grouped.median().values
        stats["q3"] = grouped.quantile(0.75).values
        iqr = stats["q3"] - stats["q1"]
        stats["_lo_fence"] = stats["q1"] - 1.5 * iqr
        stats["_hi_fence"] = stats["q3"] + 1.5 * iqr

        entro_baffi = box_long.merge(stats[["zona", "mese", "_lo_fence", "_hi_fence"]], on=["zona", "mese"])
        entro_baffi = entro_baffi[
            (entro_baffi["prezzo"] >= entro_baffi["_lo_fence"]) & (entro_baffi["prezzo"] <= entro_baffi["_hi_fence"])
        ]
        baffi = entro_baffi.groupby(["zona", "mese"])["prezzo"].agg(baffo_min="min", baffo_max="max").reset_index()
        stats = stats.merge(baffi, on=["zona", "mese"], how="left").sort_values("mese")
        stats["baffo_min"] = stats["baffo_min"].fillna(stats["q1"])
        stats["baffo_max"] = stats["baffo_max"].fillna(stats["q3"])

        fig_box = go.Figure()
        for zona in zone_sel:
            sub = stats[stats["zona"] == zona]
            fig_box.add_trace(go.Box(
                x=sub["mese"], q1=sub["q1"], median=sub["mediana"], q3=sub["q3"],
                lowerfence=sub["baffo_min"], upperfence=sub["baffo_max"],
                name=zona, marker_color=ZONE_COLORS.get(zona, INK_SECONDARY),
                # Solo SUD visibile di default: le altre restano in legenda,
                # cliccabili per essere mostrate a piacere.
                visible=True if zona == "SUD" else "legendonly",
            ))
        fig_box.update_layout(boxmode="group")
        fig_box.update_xaxes(tickangle=45, **AXIS_STYLE)
        fig_box.update_yaxes(title_text="€/MWh", **AXIS_STYLE)
        fig_box.update_layout(**CHART_LAYOUT, height=460)
        st.plotly_chart(fig_box, use_container_width=True)
else:
    st.info("Seleziona almeno una zona per vedere la distribuzione mensile.")
