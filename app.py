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
    <p style="margin-top:0.1rem; margin-bottom:0.3rem;">
      <a href="https://www.foresee.energy" style="color:{ZONE_COLORS['NORD']}; text-decoration:none; font-weight:600;">
        www.foresee.energy
      </a>
    </p>
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
    if df_mercato.empty:
        st.info("Nessun dato disponibile per le zone selezionate.")
    else:
        fig = go.Figure()
        for zona in zone_sel:
            colore = ZONE_COLORS.get(zona, INK_SECONDARY)
            # Tutto lo storico (non solo la finestra di default): la vista
            # iniziale del grafico resta gli ultimi giorni come prima, ma
            # con il range slider sotto si puo' scorrere indietro a
            # piacere su tutta la campagna di raccolta.
            serie = df_mercato[["datetime", zona]].dropna().sort_values("datetime")
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
            # Scattergl (WebGL) invece di Scatter: con tutto lo storico
            # caricato (decine di migliaia di punti per zona) resta fluido
            # da spostare/zoomare nel range slider.
            if not avvenuto.empty:
                fig.add_trace(go.Scattergl(
                    x=avvenuto["datetime"], y=avvenuto[zona], mode="lines", name=zona,
                    legendgroup=zona, line=dict(color=colore, width=2), hovertemplate=hover,
                ))
            if not futuro.empty:
                fig.add_trace(go.Scattergl(
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
        fig.update_xaxes(
            range=[inizio_finestra, fine_dopodomani],  # vista di default: invariata
            rangeslider=dict(visible=True, thickness=0.08, bgcolor="rgba(255,255,255,0.03)", bordercolor=AXIS),
            rangeselector=dict(
                buttons=[
                    dict(count=7, label="7g", step="day", stepmode="backward"),
                    dict(count=1, label="1m", step="month", stepmode="backward"),
                    dict(count=3, label="3m", step="month", stepmode="backward"),
                    dict(count=1, label="1a", step="year", stepmode="backward"),
                    dict(step="all", label="Tutto"),
                ],
                bgcolor="rgba(255,255,255,0.06)", activecolor=ZONE_COLORS["NORD"],
                font=dict(color=INK_SECONDARY, size=11),
            ),
            **AXIS_STYLE,
        )
        fig.update_yaxes(title_text="€/MWh", **AXIS_STYLE)
        fig.update_layout(**CHART_LAYOUT, height=540)
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


# ---------------------------------------------------------------------------
# Ottimizzazione storage (receding horizon a 48 h, ricalcolata ogni 15 minuti)
# ---------------------------------------------------------------------------
# I risultati NON sono in questo branch: un processo esterno li pubblica sul
# branch dedicato "optimization-results" (un solo commit sovrascritto), cosi'
# i push frequenti non riavviano la dashboard e non gonfiano la storia di main.
# Qui si leggono via raw.githubusercontent.com con cache breve. Tutta la
# sezione e' isolata: se i file mancano o qualcosa fallisce, compare solo un
# messaggio informativo e il resto della pagina non cambia.
RESULTS_BASE = os.environ.get(
    "FORESEE_RESULTS_BASE",
    "https://raw.githubusercontent.com/GianfraG/gme-prices/optimization-results",
)
RISULTATI_VECCHI_MIN = 45
ORE_PASSATO = 24
ORE_FUTURO = 48
COL_PREZZO = ZONE_COLORS["SUD"]
COL_DOMANDA = INK_SECONDARY
COL_PDC = ZONE_COLORS["NORD"]
COL_STORAGE = ZONE_COLORS["CNOR"]
COL_SOC = ZONE_COLORS["CSUD"]
COL_RES = ZONE_COLORS["SARD"]
COL_CARICA = ZONE_COLORS["CSUD"]
COL_SCARICA = ZONE_COLORS["CNOR"]


def _leggi(nome):
    if RESULTS_BASE.startswith("http"):
        return f"{RESULTS_BASE}/{nome}"
    return os.path.join(RESULTS_BASE, nome)


@st.cache_data(ttl=120, show_spinner=False)
def load_optimization():
    import urllib.request

    sorgente = _leggi("meta.json")
    if sorgente.startswith("http"):
        with urllib.request.urlopen(sorgente, timeout=15) as r:
            meta = json.loads(r.read().decode("utf-8"))
    else:
        with open(sorgente, encoding="utf-8") as f:
            meta = json.load(f)
    piano = pd.read_csv(_leggi("plan.csv"))
    storico = pd.read_csv(_leggi("history.csv"))
    for d in (piano, storico):
        if not d.empty:
            d["datetime"] = pd.to_datetime(d["ts_utc"], utc=True).dt.tz_convert(TZ).dt.tz_localize(None)
    return meta, piano, storico


def _passato_futuro(storico, piano, colonna, adesso):
    """Serie continua fino ad 'adesso' (storico eseguito) e tratteggiata dopo
    (piano corrente), con l'ultimo punto passato ripetuto come primo del
    futuro per connettere le due tratte."""
    inizio_piano = piano["datetime"].min() if not piano.empty else adesso
    passato = storico[storico["datetime"] < inizio_piano][["datetime", colonna]] if not storico.empty else pd.DataFrame()
    futuro = piano[["datetime", colonna]] if not piano.empty else pd.DataFrame()
    if not passato.empty and not futuro.empty:
        futuro = pd.concat([passato.iloc[[-1]], futuro], ignore_index=True)
    return passato, futuro


def _linea(fig, row, passato, futuro, colonna, nome, colore, unita, fill=None):
    hover = "%{y:.1f} " + unita + "<extra>" + nome + "</extra>"
    if not passato.empty:
        fig.add_trace(go.Scatter(x=passato["datetime"], y=passato[colonna], mode="lines", name=nome,
                                 legendgroup=nome, line=dict(color=colore, width=2), hovertemplate=hover,
                                 fill=fill), row=row, col=1)
    if not futuro.empty:
        fig.add_trace(go.Scatter(x=futuro["datetime"], y=futuro[colonna], mode="lines", name=nome,
                                 legendgroup=nome, showlegend=passato.empty,
                                 line=dict(color=colore, width=2, dash="dot"), hovertemplate=hover,
                                 fill=fill, opacity=0.8), row=row, col=1)


def _barre(fig, row, passato, futuro, colonna, nome, colore, unita, segno=1):
    hover = "%{y:.0f} " + unita + "<extra>" + nome + "</extra>"
    for parte, opacita, mostra in ((passato, 0.85, True), (futuro.iloc[1:] if not passato.empty else futuro, 0.35, passato.empty)):
        if parte.empty:
            continue
        fig.add_trace(go.Bar(x=parte["datetime"], y=segno * parte[colonna], name=nome, legendgroup=nome,
                             showlegend=mostra, marker_color=colore, opacity=opacita, hovertemplate=hover,
                             marker_line_width=0), row=row, col=1)


def _prezzo(fig, row, storico, piano, adesso):
    passato, futuro = _passato_futuro(storico, piano, "price_eur_mwh", adesso)
    if not passato.empty:
        fig.add_trace(go.Scatter(x=passato["datetime"], y=passato["price_eur_mwh"], mode="lines", name="Prezzo SUD",
                                 legendgroup="prezzo", line=dict(color=COL_PREZZO, width=2, shape="hv"),
                                 hovertemplate="%{y:.1f} €/MWh<extra>SUD</extra>"), row=row, col=1)
    if not futuro.empty:
        # parte pubblicata (MGP noto) e parte prevista (ML) distinte; il punto
        # di confine e' ripetuto per non lasciare buchi tra le due tratte
        pub = futuro.copy()
        prev = futuro.copy()
        src = pd.concat([pd.Series(["pubblicato"] if not passato.empty else []), piano["price_source"]], ignore_index=True)
        pub.loc[src.values != "pubblicato", "price_eur_mwh"] = None
        is_prev = src.values == "previsto"
        primo_prev = is_prev.argmax() if is_prev.any() else None
        if primo_prev:
            is_prev[primo_prev - 1] = True
        prev.loc[~is_prev, "price_eur_mwh"] = None
        fig.add_trace(go.Scatter(x=pub["datetime"], y=pub["price_eur_mwh"], mode="lines", name="Prezzo SUD",
                                 legendgroup="prezzo", showlegend=passato.empty,
                                 line=dict(color=COL_PREZZO, width=2, dash="dot", shape="hv"),
                                 hovertemplate="%{y:.1f} €/MWh<extra>SUD pubblicato</extra>"), row=row, col=1)
        if is_prev.any():
            fig.add_trace(go.Scatter(x=prev["datetime"], y=prev["price_eur_mwh"], mode="lines",
                                     name="Prezzo SUD previsto (ML)", line=dict(color=INK_MUTED, width=2, dash="dash", shape="hv"),
                                     hovertemplate="%{y:.1f} €/MWh<extra>SUD previsto</extra>"), row=row, col=1)


def _finalizza(fig, adesso, n_righe, titoli_y, altezza):
    for i, t in enumerate(titoli_y, start=1):
        fig.update_yaxes(title_text=t, row=i, col=1, **AXIS_STYLE)
    fig.update_xaxes(range=[adesso - pd.Timedelta(hours=ORE_PASSATO), adesso + pd.Timedelta(hours=ORE_FUTURO)],
                     **AXIS_STYLE)
    fig.add_vline(x=adesso, line_dash="dot", line_color=INK_MUTED)
    fig.add_annotation(x=adesso, y=1.0, yref="paper", text=f"Adesso {adesso.strftime('%H:%M')}", showarrow=False,
                       yanchor="bottom", font=dict(color=INK_MUTED, size=11))
    fig.update_layout(**CHART_LAYOUT, height=altezza, barmode="relative", bargap=0)
    fig.update_layout(margin=dict(t=60, l=10, r=10, b=10))


def sezione_ottimizzazione():
    from plotly.subplots import make_subplots

    st.markdown("#### Ottimizzazione storage — prossime 48 ore")
    st.caption(
        "Ogni 15 minuti un modello di ottimizzazione ricalcola come usare uno storage termico e una "
        "batteria di un sito industriale nelle 48 ore successive. Linea continua: cio' che e' stato "
        "eseguito; tratteggio: il piano corrente. Dove il prezzo MGP non e' ancora pubblicato viene "
        "usata una previsione. La domanda del sito e' simulata."
    )
    try:
        meta, piano, storico = load_optimization()
    except Exception:
        st.info("Risultati dell'ottimizzazione non disponibili al momento: la sezione verrà mostrata appena pubblicati.")
        return
    if piano.empty:
        st.info("Nessun piano di ottimizzazione pubblicato al momento.")
        return

    adesso = pd.Timestamp.now(tz=TZ).tz_localize(None)
    generato = pd.Timestamp(meta.get("generated_at")).tz_convert(TZ).tz_localize(None)
    eta_min = (adesso - generato).total_seconds() / 60
    c1, c2 = st.columns(2)
    with c1:
        st.caption(f"Ultimo aggiornamento: **{generato.strftime('%d/%m/%Y %H:%M')}** "
                   f"— solver: {meta.get('solver_status', 'n/d')}"
                   + (f", gap {100 * meta['mip_gap']:.2f}%" if meta.get("mip_gap") is not None else ""))
    with c2:
        st.caption(f"Previsione prezzi: {meta.get('price_model_version') or meta.get('price_model') or 'n/d'}"
                   f" — passi previsti: {meta.get('price_steps_forecast', 'n/d')}"
                   + (" — domanda simulata" if meta.get("demand_is_simulated") else ""))
    if eta_min > RISULTATI_VECCHI_MIN:
        st.warning(f"I risultati dell'ottimizzazione hanno {eta_min:.0f} minuti: il processo di calcolo potrebbe essere fermo.")

    inizio = adesso - pd.Timedelta(hours=ORE_PASSATO + 1)
    if not storico.empty:
        storico = storico[storico["datetime"] >= inizio]
    storico = storico.copy()
    piano = piano.copy()
    for d in (storico, piano):
        if not d.empty:
            d["tes_scarica_kw"] = (-d["tes_net_kw"]).clip(lower=0)
            d["tes_carica_kw"] = d["tes_net_kw"].clip(lower=0)

    # --- 1. Storage termico ---------------------------------------------------
    st.markdown("##### Storage termico")
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.035,
                        row_heights=[0.25, 0.27, 0.22, 0.26])
    _prezzo(fig, 1, storico, piano, adesso)
    p, f = _passato_futuro(storico, piano, "heat_demand_kw", adesso)
    _linea(fig, 2, p, f, "heat_demand_kw", "Domanda termica", COL_DOMANDA, "kW")
    p, f = _passato_futuro(storico, piano, "tes_scarica_kw", adesso)
    _barre(fig, 2, p, f, "tes_scarica_kw", "Calore fornito dallo storage", COL_STORAGE, "kW")
    p, f = _passato_futuro(storico, piano, "hp_heat_kw", adesso)
    _linea(fig, 2, p, f, "hp_heat_kw", "Calore prodotto dalla pompa di calore", COL_PDC, "kW")
    p, f = _passato_futuro(storico, piano, "tes_soc_pct", adesso)
    _linea(fig, 3, p, f, "tes_soc_pct", "Carica storage termico", COL_SOC, "%")
    p, f = _passato_futuro(storico, piano, "tes_carica_kw", adesso)
    _barre(fig, 4, p, f, "tes_carica_kw", "Carica storage", COL_CARICA, "kW")
    p, f = _passato_futuro(storico, piano, "tes_scarica_kw", adesso)
    _barre(fig, 4, p, f, "tes_scarica_kw", "Scarica storage", COL_SCARICA, "kW", segno=-1)
    _finalizza(fig, adesso, 4, ["€/MWh", "kW termici", "Carica %", "kW termici"], 820)
    fig.update_yaxes(range=[0, 105], row=3, col=1)
    st.plotly_chart(fig, use_container_width=True)

    # --- 2. Batteria ---------------------------------------------------------
    st.markdown("##### Batteria")
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.035,
                        row_heights=[0.27, 0.25, 0.22, 0.26])
    p, f = _passato_futuro(storico, piano, "res_kw", adesso)
    _linea(fig, 1, p, f, "res_kw", "Produzione rinnovabile", COL_RES, "kW", fill="tozeroy")
    p, f = _passato_futuro(storico, piano, "el_demand_kw", adesso)
    _linea(fig, 1, p, f, "el_demand_kw", "Domanda elettrica", COL_DOMANDA, "kW")
    _prezzo(fig, 2, storico, piano, adesso)
    p, f = _passato_futuro(storico, piano, "bess_soc_pct", adesso)
    _linea(fig, 3, p, f, "bess_soc_pct", "Carica batteria", COL_SOC, "%")
    p, f = _passato_futuro(storico, piano, "bess_charge_kw", adesso)
    _barre(fig, 4, p, f, "bess_charge_kw", "Carica batteria (kW)", COL_CARICA, "kW")
    p, f = _passato_futuro(storico, piano, "bess_discharge_kw", adesso)
    _barre(fig, 4, p, f, "bess_discharge_kw", "Scarica batteria (kW)", COL_SCARICA, "kW", segno=-1)
    _finalizza(fig, adesso, 4, ["kW elettrici", "€/MWh", "Carica %", "kW elettrici"], 820)
    fig.update_yaxes(range=[0, 105], row=3, col=1)
    st.plotly_chart(fig, use_container_width=True)


try:
    sezione_ottimizzazione()
except Exception:
    st.info("Sezione ottimizzazione temporaneamente non disponibile.")
