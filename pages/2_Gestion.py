import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Gestión — DJSA", page_icon="🌾", layout="wide")

URL_GESTION = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vSYcv3ILMWpHRSaNwv73Zbg6xgtHm8Uor7fJ0HkGXWocs-gNwx08p8nseWwwykHVFDHB1OhpCTlhrKJ"
    "/pub?output=csv"
)


def _clean_currency(x):
    if isinstance(x, str):
        return x.replace('$', '').replace(',', '').strip()
    return x


@st.cache_data(ttl=3600, show_spinner="Cargando datos de gestión...")
def _get_gestion():
    df = pd.read_csv(URL_GESTION)
    df['Date'] = df['Campaña'].apply(lambda x: pd.to_datetime('20' + str(x)[-2:] + '-07-01'))
    for col in ['Gasto U$D', 'Ingreso U$D', 'MB U$D', 'MB/ha U$D', 'Valor/tn', 'Gasto U$D/ha']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].apply(_clean_currency), errors='coerce')
    return df


st.title("🌾 Gestión de Cultivos")
st.markdown("Márgenes brutos por campaña, rubro y actividad.")

try:
    df = _get_gestion()

    # ── Filtros ──────────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    with col1:
        campanas = sorted(df['Campaña'].unique())
        sel_camp = st.multiselect("Campaña(s)", campanas, default=campanas)
    with col2:
        rubros = sorted(df['Rubro'].dropna().unique()) if 'Rubro' in df.columns else []
        sel_rubro = st.multiselect("Rubro(s)", rubros, default=rubros)
    with col3:
        metrica = st.selectbox("Métrica", ['MB U$D', 'Ingreso U$D', 'Gasto U$D', 'MB/ha U$D'])

    df_f = df.copy()
    if sel_camp:
        df_f = df_f[df_f['Campaña'].isin(sel_camp)]
    if sel_rubro and 'Rubro' in df_f.columns:
        df_f = df_f[df_f['Rubro'].isin(sel_rubro)]

    # ── Gráfico por campaña + rubro ──────────────────────────────────────────
    st.markdown("---")
    if 'Rubro' in df_f.columns:
        df_pivot = df_f.groupby(['Date', 'Rubro'])[metrica].sum().reset_index()
        fig = px.bar(
            df_pivot, x='Date', y=metrica, color='Rubro',
            title=f'{metrica} por Campaña y Rubro',
            labels={'Date': 'Campaña', metrica: metrica},
            barmode='group',
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Tabla pivot manual ───────────────────────────────────────────────────
    st.subheader("Tabla resumen por campaña")
    group_cols = [c for c in ['Rubro', 'Actividad'] if c in df_f.columns]
    if group_cols:
        df_tabla = df_f.groupby(group_cols + ['Campaña'])[metrica].sum().reset_index()
        df_wide = df_tabla.pivot_table(index=group_cols, columns='Campaña', values=metrica, aggfunc='sum')
        df_wide['TOTAL'] = df_wide.sum(axis=1)
        df_wide = df_wide.sort_values('TOTAL', ascending=False)
        st.dataframe(df_wide.style.format('${:,.0f}'), use_container_width=True)

    # ── Evolución por rubro ──────────────────────────────────────────────────
    if 'Rubro' in df_f.columns:
        st.subheader("Evolución de MB U$D por rubro")
        df_evo = df_f.groupby(['Date', 'Rubro'])['MB U$D'].sum().reset_index()
        fig2 = px.line(df_evo, x='Date', y='MB U$D', color='Rubro',
                       markers=True, labels={'Date': 'Campaña'})
        st.plotly_chart(fig2, use_container_width=True)

    with st.expander("Datos brutos"):
        st.dataframe(df_f, use_container_width=True)

except Exception as e:
    st.error(f"Error cargando datos de gestión: {e}")
