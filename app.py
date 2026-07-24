import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Prezzi Mercato Elettrico GME", layout="wide")
st.title("Prezzi Mercato Elettrico Italiano (GME)")

DATA_FILE = "data/prezzi_zonali.csv"


@st.cache_data(ttl=3600)
def load_data():
    df = pd.read_csv(DATA_FILE)
    df["data"] = pd.to_datetime(df["data"])
    return df


try:
    df = load_data()
except FileNotFoundError:
    st.warning(
        "Nessun dato ancora raccolto. Il file data/prezzi_zonali.csv verrà creato "
        "dalla prima esecuzione dello script/workflow di raccolta dati."
    )
    st.stop()

st.caption(f"Ultimo aggiornamento dati: {df['data'].max().date()} — {len(df)} righe totali")

col1, col2 = st.columns(2)
with col1:
    mercati_disponibili = sorted(df["mercato"].unique())
    mercato_sel = st.selectbox("Mercato", mercati_disponibili, index=0)
with col2:
    df_mercato = df[df["mercato"] == mercato_sel]
    # Individua dinamicamente le colonne di prezzo/zona presenti nei dati
    colonne_zona = [
        c for c in df_mercato.columns
        if c not in ("data", "mercato") and df_mercato[c].dtype != object
    ]
    zone_sel = st.multiselect("Zone", colonne_zona, default=colonne_zona[:3])

if zone_sel:
    plot_df = df_mercato.melt(
        id_vars="data", value_vars=zone_sel, var_name="zona", value_name="prezzo"
    )
    fig = px.line(
        plot_df, x="data", y="prezzo", color="zona",
        title=f"Andamento prezzi — {mercato_sel}",
        labels={"prezzo": "€/MWh", "data": "Data"},
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Seleziona almeno una zona per vedere il grafico.")

with st.expander("Dati grezzi"):
    st.dataframe(df_mercato, use_container_width=True)
