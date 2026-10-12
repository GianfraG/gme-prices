import json
import os
import urllib.request

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

st.set_page_config(
    page_title="foresee — Prezzi zonali MGP",
    layout="wide",
    page_icon="assets/favicon.png" if os.path.exists("assets/favicon.png") else "⚡",
)

# La raccolta dati (fetch_prices.py) gira una volta al giorno: questo
# auto-refresh serve solo a far avanzare la linea "Adesso" e a rileggere i
# file se nel frattempo è arrivato un aggiornamento, NON a scaricare nulla.
st.markdown('<meta http-equiv="refresh" content="900">', unsafe_allow_html=True)

DATA_FILE = "data/prezzi_zonali.csv"
LAST_UPDATE_FILE = "data/last_update.json"
GITHUB_REPO_URL = "https://github.com/GianfraG/gme-prices"
SITE_URL = "https://foresee.energy"
TZ = "Europe/Rome"
MERCATO = "MGP"
GIORNI_STORICO_MOSTRATI = 3  # più domani (MGP pubblicato) e dopodomani (previsione)
ZONA_PREVISTA = "SUD"        # zona per cui esistono previsione e ottimizzazione

# Risultati dell'ottimizzazione: branch dedicato, letti via raw con cache breve
RESULTS_BASE = os.environ.get(
    "FORESEE_RESULTS_BASE",
    "https://raw.githubusercontent.com/GianfraG/gme-prices/optimization-results",
)
RISULTATI_VECCHI_MIN = 45
ORE_PASSATO = 24
ORE_FUTURO = 48

# --- Design tokens (marchio foresee: blu notte + turchese) -------------------
BRAND = "#2dd4bf"
BG = "#0a1620"
SURFACE = "#0f2030"
BORDER = "#1c3346"
TEXT = "#e8eef3"
INK_SECONDARY = "#b4c3cf"
INK_MUTED = "#7b8fa1"
GRID = "#162b3c"
AXIS = "#29465c"
FONT = "Helvetica Neue, Helvetica, Arial, sans-serif"

# Palette categoriale delle zone (validata per contrasto/daltonismo), ordine fisso
ZONE_COLORS = {
    "NORD": "#3987e5",
    "CNOR": "#d95926",
    "CSUD": "#199e70",
    "SUD": "#c98500",
    "SICI": "#d55181",
    "SARD": "#008300",
    "CALA": "#9085e9",
}
COL_PREZZO = ZONE_COLORS["SUD"]
COL_DOMANDA = INK_SECONDARY
COL_PDC = ZONE_COLORS["NORD"]
COL_STORAGE = ZONE_COLORS["CNOR"]
COL_SOC = BRAND
COL_RES = ZONE_COLORS["SARD"]
COL_CARICA = ZONE_COLORS["CSUD"]
COL_SCARICA = ZONE_COLORS["CNOR"]
COL_TEMP_TES = ZONE_COLORS["SICI"]
COL_TEMP_ARIA = ZONE_COLORS["CNOR"]

CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=INK_SECONDARY, family=FONT, size=12),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
    margin=dict(t=40, l=10, r=10, b=10),
    hovermode="x unified",
    hoverlabel=dict(bgcolor=SURFACE, bordercolor=BORDER, font=dict(family=FONT, color=TEXT, size=12)),
)
AXIS_STYLE = dict(gridcolor=GRID, linecolor=AXIS, tickfont=dict(color=INK_MUTED, size=11), zeroline=False,
                  title_font=dict(color=INK_MUTED, size=11))

st.markdown(
    f"""
    <style>
      #MainMenu, footer {{visibility: hidden;}}
      header[data-testid="stHeader"] {{background: transparent;}}
      .block-container {{padding-top: 1.6rem; padding-bottom: 2rem; max-width: 1400px;}}
      html, body, [class*="css"] {{font-family: {FONT};}}
      .fs-top {{display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:.6rem;
                padding-bottom:1rem; border-bottom:1px solid {BORDER}; margin-bottom:1.6rem;}}
      a.fs-logo, a.fs-logo:hover, a.fs-logo:visited {{font-size:30px; font-weight:400; color:#ffffff !important;
                letter-spacing:-0.01em; text-decoration:none !important;}}
      a.fs-logo b {{font-weight:700; color:{BRAND} !important;}}
      .fs-tag {{color:{INK_MUTED}; font-size:12px; letter-spacing:.14em; text-transform:uppercase;}}
      .fs-eyebrow {{color:{BRAND}; font-size:11.5px; font-weight:700; letter-spacing:.16em;
                    text-transform:uppercase; margin:0 0 .25rem 0;}}
      .fs-h1 {{color:{TEXT}; font-size:1.9rem; font-weight:700; letter-spacing:-0.015em; margin:0 0 .3rem 0;}}
      .fs-h2 {{color:{TEXT}; font-size:1.35rem; font-weight:700; letter-spacing:-0.01em; margin:0 0 .25rem 0;}}
      .fs-h3 {{color:{TEXT}; font-size:1.02rem; font-weight:600; margin:1.2rem 0 .1rem 0;}}
      .fs-sub {{color:{INK_SECONDARY}; font-size:.92rem; margin:0 0 .2rem 0; line-height:1.5;}}
      .fs-note {{color:{INK_MUTED}; font-size:.8rem; margin:.1rem 0 .6rem 0; line-height:1.5;}}
      .fs-section {{margin-top:2.4rem; padding-top:1.4rem; border-top:1px solid {BORDER};}}
      .fs-kpis {{display:grid; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); gap:.75rem; margin:1.1rem 0 1.2rem 0;}}
      .fs-kpi {{background:{SURFACE}; border:1px solid {BORDER}; border-radius:10px; padding:.8rem 1rem;}}
      .fs-kpi .l {{color:{INK_MUTED}; font-size:.72rem; letter-spacing:.1em; text-transform:uppercase;}}
      .fs-kpi .v {{color:{TEXT}; font-size:1.55rem; font-weight:700; margin-top:.15rem; font-variant-numeric:tabular-nums;}}
      .fs-kpi .v span {{color:{INK_MUTED}; font-size:.8rem; font-weight:400; margin-left:.25rem;}}
      .fs-kpi .d {{color:{INK_MUTED}; font-size:.75rem; margin-top:.1rem;}}
      .fs-chips {{display:flex; flex-wrap:wrap; gap:.4rem; margin:.5rem 0 .3rem 0;}}
      .fs-chip {{border:1px solid {BORDER}; background:{SURFACE}; color:{INK_SECONDARY}; border-radius:999px;
                 padding:.18rem .65rem; font-size:.76rem; font-variant-numeric:tabular-nums;}}
      .fs-chip.ok {{border-color:rgba(45,212,191,.45); color:{BRAND};}}
      .fs-chip.warn {{border-color:rgba(217,89,38,.6); color:#f08a5d;}}
      .fs-foot {{margin-top:3rem; padding-top:1.2rem; border-top:1px solid {BORDER}; color:{INK_MUTED};
                 font-size:.78rem; line-height:1.7;}}
      .fs-foot a {{color:{INK_SECONDARY}; text-decoration:none;}}
    </style>
    """,
    unsafe_allow_html=True,
)


def html(s):
    st.markdown(s, unsafe_allow_html=True)


def fmt_num(v, dec=1):
    if v is None or pd.isna(v):
        return "—"
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ---------------------------------------------------------------------------
# Dati
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300)
def load_data():
    df = pd.read_csv(DATA_FILE, dtype={"ora": str})
    # Il timestamp UTC è univoco (a differenza di "data"+"ora" locali, che si
    # ripetono una volta l'anno al cambio dall'ora legale a quella solare).
    df["datetime"] = pd.to_datetime(df["utc"], utc=True).dt.tz_convert(TZ).dt.tz_localize(None)
    df["data"] = pd.to_datetime(df["data"])
    return df


@st.cache_data(ttl=300)
def load_last_update():
    if not os.path.exists(LAST_UPDATE_FILE):
        return None
    with open(LAST_UPDATE_FILE, encoding="utf-8") as f:
        return json.load(f)


def _risorsa(nome):
    return f"{RESULTS_BASE}/{nome}" if RESULTS_BASE.startswith("http") else os.path.join(RESULTS_BASE, nome)


@st.cache_data(ttl=120, show_spinner=False)
def load_optimization():
    sorgente = _risorsa("meta.json")
    if sorgente.startswith("http"):
        with urllib.request.urlopen(sorgente, timeout=15) as r:
            meta = json.loads(r.read().decode("utf-8"))
    else:
        with open(sorgente, encoding="utf-8") as f:
            meta = json.load(f)
    piano = pd.read_csv(_risorsa("plan.csv"))
    storico = pd.read_csv(_risorsa("history.csv"))
    for d in (piano, storico):
        if not d.empty:
            d["datetime"] = pd.to_datetime(d["ts_utc"], utc=True).dt.tz_convert(TZ).dt.tz_localize(None)
    return meta, piano, storico


def try_optimization():
    try:
        return load_optimization()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Intestazione
# ---------------------------------------------------------------------------
html(
    f"""
    <div class="fs-top">
      <a class="fs-logo" href="{SITE_URL}" target="_blank">fore<b>see</b></a>
      <div class="fs-tag">Market intelligence · Italia</div>
    </div>
    <p class="fs-eyebrow">Mercato elettrico · MGP</p>
    <p class="fs-h1">Prezzi zonali del mercato del giorno prima</p>
    <p class="fs-sub">Zone di offerta italiane, €/MWh. Risoluzione a 15 minuti dal 1° ottobre 2025, oraria in precedenza.</p>
    """
)

try:
    df = load_data()
except FileNotFoundError:
    st.warning("Dati non ancora disponibili: il file data/prezzi_zonali.csv viene creato dalla prima esecuzione della pipeline.")
    st.stop()

df_mercato = df[df["mercato"] == MERCATO]
ultimo_controllo = load_last_update()
opt = try_optimization()

adesso = pd.Timestamp.now(tz=TZ).tz_localize(None)  # avanza ad ogni refresh
oggi = adesso.normalize()
inizio_finestra = oggi - pd.Timedelta(days=GIORNI_STORICO_MOSTRATI - 1)
fine_domani = oggi + pd.Timedelta(days=2) - pd.Timedelta(minutes=1)
fine_dopodomani = oggi + pd.Timedelta(days=3) - pd.Timedelta(minutes=1)

colonne_zona = [
    c for c in df_mercato.columns
    if c not in ("data", "ora", "utc", "mercato", "datetime") and df_mercato[c].dtype != object
]

# --- Indicatori sintetici (zona SUD) ------------------------------------------
kpi = []  # (etichetta, valore, unità, dettaglio)
if ZONA_PREVISTA in df_mercato:
    sud = df_mercato[["datetime", ZONA_PREVISTA]].dropna().sort_values("datetime")
    corrente = sud[sud["datetime"] <= adesso].tail(1)
    oggi_s = sud[(sud["datetime"] >= oggi) & (sud["datetime"] < oggi + pd.Timedelta(days=1))][ZONA_PREVISTA]
    dom_s = sud[(sud["datetime"] >= oggi + pd.Timedelta(days=1)) & (sud["datetime"] < oggi + pd.Timedelta(days=2))][ZONA_PREVISTA]
    if not corrente.empty:
        kpi.append(("SUD · quarto d'ora corrente", fmt_num(corrente[ZONA_PREVISTA].iloc[0]), "€/MWh",
                    corrente["datetime"].iloc[0].strftime("%d/%m %H:%M")))
    if len(oggi_s):
        kpi.append(("SUD · media oggi", fmt_num(oggi_s.mean()), "€/MWh",
                    f"min {fmt_num(oggi_s.min(), 0)} · max {fmt_num(oggi_s.max(), 0)}"))
    if len(dom_s):
        kpi.append(("SUD · media domani", fmt_num(dom_s.mean()), "€/MWh", "MGP pubblicato"))
if opt is not None:
    meta_o, piano_o, _ = opt
    if not piano_o.empty and "price_source" in piano_o:
        prev_o = piano_o[(piano_o["price_source"] == "previsto") & (piano_o["datetime"] > df_mercato["datetime"].max())]
        if len(prev_o):
            giorno = prev_o["datetime"].dt.normalize()
            g = prev_o[giorno == giorno.min()]
            kpi.append((f"SUD · previsione {g['datetime'].iloc[0].strftime('%d/%m')}", fmt_num(g["price_eur_mwh"].mean()),
                        "€/MWh", "media sulle ore previste"))
    mae_o = meta_o.get("forecast_mae_7d_eur_mwh", meta_o.get("live_mae_7d_eur_mwh"))
    if mae_o is not None:
        kpi.append(("Errore di previsione", fmt_num(mae_o), "€/MWh",
                    "MAE ultimi 7 giorni, zona SUD"))
if kpi:
    html('<div class="fs-kpis">' + "".join(
        f'<div class="fs-kpi"><div class="l">{l}</div><div class="v">{v}<span>{u}</span></div><div class="d">{d}</div></div>'
        for l, v, u, d in kpi) + "</div>")

chips = [f"Dati MGP fino al {df_mercato['datetime'].max().strftime('%d/%m/%Y %H:%M')}",
         f"Storico dal {df_mercato['data'].min().strftime('%d/%m/%Y')}"]
if ultimo_controllo:
    chips.append("Ultimo controllo pipeline " + pd.Timestamp(ultimo_controllo["last_check"]).strftime("%d/%m/%Y %H:%M"))
html('<div class="fs-chips">' + "".join(f'<span class="fs-chip">{c}</span>' for c in chips) + "</div>")

# ---------------------------------------------------------------------------
# 1. Andamento prezzi
# ---------------------------------------------------------------------------
html('<div class="fs-section"><p class="fs-eyebrow">Prezzi</p><p class="fs-h2">Andamento e previsione</p>'
     '<p class="fs-note">Linea continua: prezzi realizzati. Puntinato: prezzi MGP già pubblicati per il giorno '
     f'successivo. Oltre l\'ultimo giorno pubblicato: previsione per la zona {ZONA_PREVISTA} (tratteggio) con '
     'intervallo di previsione all\'80% (area), stimato dagli errori storici per anticipo e fascia oraria.</p></div>')

zone_sel = st.multiselect("Zone", colonne_zona, default=colonne_zona)
df_finestra = df_mercato[(df_mercato["datetime"] >= inizio_finestra) & (df_mercato["datetime"] <= fine_domani)]


def add_forecast(fig, opt_data, ultimo_pubblicato):
    """Previsione della zona SUD oltre l'orizzonte MGP pubblicato, con banda."""
    if opt_data is None:
        return False
    _, piano, _ = opt_data
    if piano.empty or "price_source" not in piano:
        return False
    prev = piano[(piano["price_source"] == "previsto") & (piano["datetime"] > ultimo_pubblicato)].copy()
    if prev.empty:
        return False
    colore = ZONE_COLORS.get(ZONA_PREVISTA, BRAND)
    banda = {"price_lo_eur_mwh", "price_hi_eur_mwh"} <= set(prev.columns) and prev["price_hi_eur_mwh"].notna().any()
    if banda:
        fig.add_trace(go.Scatter(x=prev["datetime"], y=prev["price_hi_eur_mwh"], mode="lines",
                                 line=dict(width=0, shape="hv"), showlegend=False, hoverinfo="skip", legendgroup="prev"))
        fig.add_trace(go.Scatter(x=prev["datetime"], y=prev["price_lo_eur_mwh"], mode="lines",
                                 line=dict(width=0, shape="hv"), fill="tonexty", fillcolor="rgba(201,133,0,0.18)",
                                 name=f"{ZONA_PREVISTA} · intervallo 80%", legendgroup="prev", hoverinfo="skip"))
        hover = ("%{y:.1f} €/MWh  (80%: %{customdata[0]:.0f}–%{customdata[1]:.0f})"
                 f"<extra>{ZONA_PREVISTA} previsione</extra>")
        custom = prev[["price_lo_eur_mwh", "price_hi_eur_mwh"]].to_numpy()
    else:
        hover, custom = f"%{{y:.1f}} €/MWh<extra>{ZONA_PREVISTA} previsione</extra>", None
    fig.add_trace(go.Scatter(x=prev["datetime"], y=prev["price_eur_mwh"], mode="lines",
                             name=f"{ZONA_PREVISTA} · previsione", legendgroup="prev", customdata=custom,
                             line=dict(color=colore, width=2, dash="dash", shape="hv"), hovertemplate=hover))
    fig.add_vrect(x0=ultimo_pubblicato, x1=prev["datetime"].max(), fillcolor="rgba(255,255,255,0.03)", line_width=0,
                  annotation_text="PREVISIONE", annotation_position="top left",
                  annotation_font=dict(color=INK_MUTED, size=10))
    return True


if zone_sel:
    if df_mercato.empty:
        st.info("Nessun dato disponibile per le zone selezionate.")
    else:
        fig = go.Figure()
        for zona in zone_sel:
            colore = ZONE_COLORS.get(zona, INK_SECONDARY)
            serie = df_mercato[["datetime", zona]].dropna().sort_values("datetime")
            avvenuto = serie[serie["datetime"] <= adesso]
            futuro = serie[serie["datetime"] > adesso]
            if not avvenuto.empty and not futuro.empty:
                # l'ultimo punto avvenuto apre la tratta futura: linee connesse
                futuro = pd.concat([avvenuto.iloc[[-1]], futuro], ignore_index=True)
            hover = "%{y:.1f} €/MWh<extra>" + zona + "</extra>"
            # Scattergl: fluido anche con tutto lo storico nel range slider
            if not avvenuto.empty:
                fig.add_trace(go.Scattergl(x=avvenuto["datetime"], y=avvenuto[zona], mode="lines", name=zona,
                                           legendgroup=zona, line=dict(color=colore, width=1.8), hovertemplate=hover))
            if not futuro.empty:
                fig.add_trace(go.Scattergl(x=futuro["datetime"], y=futuro[zona], mode="lines", name=zona,
                                           legendgroup=zona, showlegend=avvenuto.empty,
                                           line=dict(color=colore, width=1.8, dash="dot"), hovertemplate=hover))
        if ZONA_PREVISTA in zone_sel:
            add_forecast(fig, opt, df_mercato["datetime"].max())
        fig.add_vline(x=adesso, line_dash="dot", line_color=INK_MUTED, line_width=1)
        fig.add_annotation(x=adesso, y=1.0, yref="paper", text=f"Adesso {adesso.strftime('%H:%M')}", showarrow=False,
                           yanchor="bottom", font=dict(color=INK_MUTED, size=10))
        fig.update_xaxes(
            range=[inizio_finestra, fine_dopodomani],
            rangeslider=dict(visible=True, thickness=0.07, bgcolor="rgba(255,255,255,0.02)", bordercolor=AXIS),
            rangeselector=dict(
                buttons=[
                    dict(count=7, label="7g", step="day", stepmode="backward"),
                    dict(count=1, label="1m", step="month", stepmode="backward"),
                    dict(count=3, label="3m", step="month", stepmode="backward"),
                    dict(count=1, label="1a", step="year", stepmode="backward"),
                    dict(step="all", label="Tutto"),
                ],
                bgcolor="rgba(255,255,255,0.05)", activecolor="rgba(45,212,191,0.35)",
                font=dict(color=INK_SECONDARY, size=11), x=0, xanchor="left", y=1.02, yanchor="bottom",
            ),
            **AXIS_STYLE,
        )
        fig.update_yaxes(title_text="€/MWh", **AXIS_STYLE)
        fig.update_layout(**CHART_LAYOUT, height=580)
        # legenda a destra, selettore del periodo a sinistra: nessuna sovrapposizione
        fig.update_layout(margin=dict(t=90, l=10, r=10, b=10),
                          legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                                      bgcolor="rgba(0,0,0,0)", font=dict(size=11)))
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Selezionare almeno una zona.")

with st.expander("Dati tabellari (finestra visualizzata)"):
    st.dataframe(df_finestra.drop(columns="datetime"), use_container_width=True)

# ---------------------------------------------------------------------------
# 2. Distribuzione mensile
# ---------------------------------------------------------------------------
html('<div class="fs-section"><p class="fs-eyebrow">Statistiche</p><p class="fs-h2">Distribuzione mensile dei prezzi</p>'
     '<p class="fs-note">Ultimi 24 mesi. Box: primo quartile, mediana, terzo quartile; baffi entro 1,5 × IQR. '
     f'Zona {ZONA_PREVISTA} visibile di default, le altre selezionabili dalla legenda.</p></div>')

due_anni_fa = oggi - pd.DateOffset(years=2)
df_2anni = df_mercato[(df_mercato["datetime"] >= due_anni_fa) & (df_mercato["datetime"] <= adesso)]

if zone_sel:
    if df_2anni.empty:
        st.info("Nessun dato storico disponibile per le zone selezionate.")
    else:
        box_long = df_2anni.melt(id_vars="datetime", value_vars=zone_sel, var_name="zona", value_name="prezzo")
        box_long["mese"] = box_long["datetime"].dt.strftime("%Y-%m")
        # Statistiche pre-calcolate lato server (Tukey 1.5*IQR): al browser
        # arrivano poche righe aggregate invece di centinaia di migliaia di punti.
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
                name=zona, marker_color=ZONE_COLORS.get(zona, INK_SECONDARY), line=dict(width=1.2),
                visible=True if zona == ZONA_PREVISTA else "legendonly",
            ))
        fig_box.update_layout(boxmode="group")
        fig_box.update_xaxes(tickangle=45, **AXIS_STYLE)
        fig_box.update_yaxes(title_text="€/MWh", **AXIS_STYLE)
        fig_box.update_layout(**CHART_LAYOUT, height=440)
        st.plotly_chart(fig_box, use_container_width=True)
else:
    st.info("Selezionare almeno una zona.")


# ---------------------------------------------------------------------------
# 3. Ottimizzazione degli accumuli (orizzonte 48 h)
# ---------------------------------------------------------------------------
# I risultati arrivano dal branch "optimization-results" (un commit
# sovrascritto ad ogni calcolo): i push frequenti non riavviano l'app e non
# appesantiscono la storia di main. Sezione isolata: se i file mancano o
# qualcosa fallisce compare solo un avviso, il resto della pagina non cambia.

def _passato_futuro(storico, piano, colonna):
    """Storico eseguito (continuo) fino all'inizio del piano, piano corrente
    (tratteggiato) dopo; l'ultimo punto passato apre la tratta futura."""
    inizio_piano = piano["datetime"].min()
    passato = storico[storico["datetime"] < inizio_piano][["datetime", colonna]] if not storico.empty else pd.DataFrame()
    futuro = piano[["datetime", colonna]]
    if not passato.empty and not futuro.empty:
        futuro = pd.concat([passato.iloc[[-1]], futuro], ignore_index=True)
    return passato, futuro


def _linea(fig, row, storico, piano, colonna, nome, colore, unita, fill=None, width=1.8, opacity=1.0):
    passato, futuro = _passato_futuro(storico, piano, colonna)
    hover = "%{y:.1f} " + unita + "<extra>" + nome + "</extra>"
    if not passato.empty:
        fig.add_trace(go.Scatter(x=passato["datetime"], y=passato[colonna], mode="lines", name=nome,
                                 legendgroup=nome, line=dict(color=colore, width=width), hovertemplate=hover,
                                 fill=fill, opacity=opacity), row=row, col=1)
    if not futuro.empty:
        fig.add_trace(go.Scatter(x=futuro["datetime"], y=futuro[colonna], mode="lines", name=nome,
                                 legendgroup=nome, showlegend=passato.empty,
                                 line=dict(color=colore, width=width, dash="dot"), hovertemplate=hover,
                                 fill=fill, opacity=0.8 * opacity), row=row, col=1)


def _barre(fig, row, storico, piano, colonna, nome, colore, unita, segno=1):
    passato, futuro = _passato_futuro(storico, piano, colonna)
    hover = "%{y:.0f} " + unita + "<extra>" + nome + "</extra>"
    futuro = futuro.iloc[1:] if not passato.empty else futuro
    for parte, opacita, mostra in ((passato, 0.85, True), (futuro, 0.35, passato.empty)):
        if parte.empty:
            continue
        fig.add_trace(go.Bar(x=parte["datetime"], y=segno * parte[colonna], name=nome, legendgroup=nome,
                             showlegend=mostra, marker_color=colore, opacity=opacita, hovertemplate=hover,
                             marker_line_width=0), row=row, col=1)


def _prezzo(fig, row, storico, piano):
    passato, futuro = _passato_futuro(storico, piano, "price_eur_mwh")
    if not passato.empty:
        fig.add_trace(go.Scatter(x=passato["datetime"], y=passato["price_eur_mwh"], mode="lines", name="Prezzo SUD",
                                 legendgroup="prezzo", line=dict(color=COL_PREZZO, width=1.8, shape="hv"),
                                 hovertemplate="%{y:.1f} €/MWh<extra>SUD</extra>"), row=row, col=1)
    if futuro.empty:
        return
    src = pd.concat([pd.Series(["pubblicato"] if not passato.empty else []), piano["price_source"]], ignore_index=True)
    pub, prev = futuro.copy(), futuro.copy()
    pub.loc[src.values != "pubblicato", "price_eur_mwh"] = None
    is_prev = src.values == "previsto"
    primo = is_prev.argmax() if is_prev.any() else None
    if primo:
        is_prev[primo - 1] = True  # punto di raccordo tra le due tratte
    prev.loc[~is_prev, "price_eur_mwh"] = None
    fig.add_trace(go.Scatter(x=pub["datetime"], y=pub["price_eur_mwh"], mode="lines", name="Prezzo SUD",
                             legendgroup="prezzo", showlegend=passato.empty,
                             line=dict(color=COL_PREZZO, width=1.8, dash="dot", shape="hv"),
                             hovertemplate="%{y:.1f} €/MWh<extra>SUD MGP</extra>"), row=row, col=1)
    if is_prev.any():
        if "price_hi_eur_mwh" in piano and piano["price_hi_eur_mwh"].notna().any():
            band = piano[piano["price_source"] == "previsto"]
            fig.add_trace(go.Scatter(x=band["datetime"], y=band["price_hi_eur_mwh"], mode="lines",
                                     line=dict(width=0, shape="hv"), showlegend=False, hoverinfo="skip",
                                     legendgroup="prev"), row=row, col=1)
            fig.add_trace(go.Scatter(x=band["datetime"], y=band["price_lo_eur_mwh"], mode="lines",
                                     line=dict(width=0, shape="hv"), fill="tonexty", fillcolor="rgba(201,133,0,0.16)",
                                     name="Intervallo 80%", legendgroup="prev", hoverinfo="skip",
                                     showlegend=row == 1), row=row, col=1)
        fig.add_trace(go.Scatter(x=prev["datetime"], y=prev["price_eur_mwh"], mode="lines", name="Prezzo SUD previsto",
                                 legendgroup="prev", showlegend=row == 1,
                                 line=dict(color=COL_PREZZO, width=1.8, dash="dash", shape="hv"),
                                 opacity=0.85, hovertemplate="%{y:.1f} €/MWh<extra>SUD previsto</extra>"),
                      row=row, col=1)


def _finalizza(fig, titoli_y, altezza):
    for i, t in enumerate(titoli_y, start=1):
        fig.update_yaxes(title_text=t, row=i, col=1, **AXIS_STYLE)
    fig.update_xaxes(range=[adesso - pd.Timedelta(hours=ORE_PASSATO), adesso + pd.Timedelta(hours=ORE_FUTURO)],
                     **AXIS_STYLE)
    fig.add_vline(x=adesso, line_dash="dot", line_color=INK_MUTED, line_width=1)
    fig.add_annotation(x=adesso, y=1.0, yref="paper", text=f"Adesso {adesso.strftime('%H:%M')}", showarrow=False,
                       yanchor="bottom", font=dict(color=INK_MUTED, size=10))
    fig.update_layout(**CHART_LAYOUT, height=altezza, barmode="relative", bargap=0)
    fig.update_layout(margin=dict(t=64, l=10, r=10, b=10))


def sezione_ottimizzazione():
    html('<div class="fs-section"><p class="fs-eyebrow">Ottimizzazione operativa</p>'
         '<p class="fs-h2">Gestione predittiva degli accumuli</p>'
         '<p class="fs-note">Pianificazione ottimizzata su orizzonte mobile di 48 h con passo di 15 minuti, '
         'aggiornata ogni 15 minuti. Accumulo termico con pompa di calore e batteria elettrica di un sito industriale; '
         'prezzo di riferimento zona SUD (MGP pubblicato o previsto). Linea continua: esercizio realizzato; '
         'tratteggio: piano corrente. Profili di domanda del sito simulati.</p></div>')
    if opt is None:
        st.info("Risultati di ottimizzazione non disponibili al momento.")
        return
    meta, piano, storico = opt
    if piano.empty:
        st.info("Nessun piano di ottimizzazione disponibile al momento.")
        return

    generato = pd.Timestamp(meta.get("generated_at")).tz_convert(TZ).tz_localize(None)
    eta_min = (adesso - generato).total_seconds() / 60
    stato = meta.get("status", "n/d")
    etichetta_stato = {"ok": "Piano aggiornato", "piano_precedente": "Piano precedente in uso"}.get(stato, "Stato n/d")
    chips = [(f"Ultimo calcolo {generato.strftime('%d/%m %H:%M')}", "ok" if eta_min <= RISULTATI_VECCHI_MIN else "warn"),
             (etichetta_stato, "ok" if stato == "ok" else "warn")]
    if meta.get("price_forecast_version"):
        chips.append((f"Previsione prezzi v. {meta['price_forecast_version']}", ""))
    if meta.get("price_steps_forecast") is not None:
        chips.append((f"Passi a prezzo previsto {meta['price_steps_forecast']}/{meta.get('horizon_steps', 192)}", ""))
    if meta.get("demand_is_simulated"):
        chips.append(("Domanda simulata", ""))
    html('<div class="fs-chips">' + "".join(f'<span class="fs-chip {c}">{t}</span>' for t, c in chips) + "</div>")
    if eta_min > RISULTATI_VECCHI_MIN:
        st.warning(f"Ultimo calcolo di {eta_min:.0f} minuti fa: il processo di ottimizzazione potrebbe essere fermo.")

    storico = (storico[storico["datetime"] >= adesso - pd.Timedelta(hours=ORE_PASSATO + 1)].copy()
               if not storico.empty else storico.copy())
    piano = piano.copy()
    for c in piano.columns:
        if c not in storico.columns:
            storico[c] = float("nan") if c != "price_source" else "pubblicato"
    for d in (storico, piano):
        if not d.empty:
            d["tes_scarica_kw"] = (-d["tes_net_kw"]).clip(lower=0)
            d["tes_carica_kw"] = d["tes_net_kw"].clip(lower=0)

    # --- Accumulo termico -------------------------------------------------------
    html('<p class="fs-h3">Accumulo termico (TES) e pompa di calore</p>'
         '<p class="fs-note">Prezzo · bilancio termico (domanda di processo, calore da accumulo e da pompa di calore) · '
         'stato di carica · temperatura dell\'accumulo · potenza di carica/scarica.</p>')
    con_temp = "tes_temp_c" in piano.columns
    n = 5 if con_temp else 4
    fig = make_subplots(rows=n, cols=1, shared_xaxes=True, vertical_spacing=0.03,
                        row_heights=[0.21, 0.23, 0.17, 0.17, 0.22] if con_temp else [0.25, 0.27, 0.22, 0.26])
    _prezzo(fig, 1, storico, piano)
    # barre, poi pompa di calore (modulazione on/off frequente: linea sottile), poi domanda in primo piano
    _barre(fig, 2, storico, piano, "tes_scarica_kw", "Calore da accumulo", COL_STORAGE, "kW")
    _linea(fig, 2, storico, piano, "hp_heat_kw", "Calore da pompa di calore", COL_PDC, "kW", width=1, opacity=0.55)
    _linea(fig, 2, storico, piano, "heat_demand_kw", "Domanda termica", COL_DOMANDA, "kW")
    _linea(fig, 3, storico, piano, "tes_soc_pct", "Stato di carica TES", COL_SOC, "%")
    if con_temp:
        _linea(fig, 4, storico, piano, "tes_temp_c", "Temperatura TES", COL_TEMP_TES, "°C")
        for y, testo in ((85, "T processo 85 °C"), (95, "T max 95 °C")):
            fig.add_hline(y=y, line_dash="dot", line_color=INK_MUTED, line_width=1, row=4, col=1,
                          annotation_text=testo, annotation_position="top left",
                          annotation_font=dict(color=INK_MUTED, size=10))
    _barre(fig, n, storico, piano, "tes_carica_kw", "Carica TES", COL_CARICA, "kW")
    _barre(fig, n, storico, piano, "tes_scarica_kw", "Scarica TES", COL_SCARICA, "kW", segno=-1)
    titoli = ["€/MWh", "kW termici", "SoC %"] + (["°C"] if con_temp else []) + ["kW termici"]
    _finalizza(fig, titoli, 960 if con_temp else 820)
    fig.update_yaxes(range=[0, 105], row=3, col=1)
    st.plotly_chart(fig, use_container_width=True)

    # --- Batteria -----------------------------------------------------------------
    html('<p class="fs-h3">Batteria (BESS)</p>'
         '<p class="fs-note">Produzione fotovoltaica e domanda elettrica · prezzo · stato di carica · '
         'potenza di carica/scarica.</p>')
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.035,
                        row_heights=[0.27, 0.25, 0.22, 0.26])
    _linea(fig, 1, storico, piano, "res_kw", "Produzione FV", COL_RES, "kW", fill="tozeroy")
    _linea(fig, 1, storico, piano, "el_demand_kw", "Domanda elettrica", COL_DOMANDA, "kW")
    _prezzo(fig, 2, storico, piano)
    _linea(fig, 3, storico, piano, "bess_soc_pct", "Stato di carica BESS", COL_SOC, "%")
    _barre(fig, 4, storico, piano, "bess_charge_kw", "Carica BESS", COL_CARICA, "kW")
    _barre(fig, 4, storico, piano, "bess_discharge_kw", "Scarica BESS", COL_SCARICA, "kW", segno=-1)
    _finalizza(fig, ["kW elettrici", "€/MWh", "SoC %", "kW elettrici"], 820)
    fig.update_yaxes(range=[0, 105], row=3, col=1)
    st.plotly_chart(fig, use_container_width=True)

    # --- Meteo ----------------------------------------------------------------------
    if "air_temp_c" in piano.columns:
        html('<p class="fs-h3">Condizioni meteo al sito</p>'
             '<p class="fs-note">Modello numerico Open-Meteo (anche per il passato: stime di modello, non misure di stazione). '
             'Temperatura dell\'aria · irraggiamento globale orizzontale (GHI) e sul piano dei moduli (GTI) · '
             'vento a 10 e 80 m · nuvolosità.</p>')
        fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.035,
                            row_heights=[0.25, 0.27, 0.25, 0.23])
        _linea(fig, 1, storico, piano, "air_temp_c", "Temperatura aria", COL_TEMP_ARIA, "°C")
        _linea(fig, 2, storico, piano, "ghi_wm2", "GHI", COL_PREZZO, "W/m²", fill="tozeroy")
        _linea(fig, 2, storico, piano, "gti_wm2", "GTI", ZONE_COLORS["SICI"], "W/m²")
        _linea(fig, 3, storico, piano, "wind10_kmh", "Vento 10 m", COL_PDC, "km/h")
        _linea(fig, 3, storico, piano, "wind80_kmh", "Vento 80 m", ZONE_COLORS["CALA"], "km/h")
        _linea(fig, 4, storico, piano, "cloud_pct", "Nuvolosità", COL_DOMANDA, "%", fill="tozeroy")
        _finalizza(fig, ["°C", "W/m²", "km/h", "%"], 760)
        fig.update_yaxes(range=[0, 105], row=4, col=1)
        st.plotly_chart(fig, use_container_width=True)


try:
    sezione_ottimizzazione()
except Exception:
    st.info("Sezione di ottimizzazione temporaneamente non disponibile.")

# ---------------------------------------------------------------------------
# Piè di pagina
# ---------------------------------------------------------------------------
html(
    f"""
    <div class="fs-foot">
      <a class="fs-logo" style="font-size:20px;" href="{SITE_URL}" target="_blank">fore<b>see</b></a>
      &nbsp;·&nbsp; See ahead. Save ahead.<br>
      Fonti: prezzi MGP del GME tramite ENTSO-E Transparency Platform · dati meteo
      <a href="https://open-meteo.com" target="_blank">Open-Meteo</a> (CC BY 4.0).
      Storico e pipeline di raccolta: <a href="{GITHUB_REPO_URL}" target="_blank">GianfraG/gme-prices</a>.
      Le previsioni hanno carattere indicativo.
    </div>
    """
)
