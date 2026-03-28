import os
import sqlite3
import urllib.parse

import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(page_title="Holistor — DJSA", page_icon="📊", layout="wide")

BASE_DATA = os.path.join(os.path.dirname(__file__), '..', 'data')

# ── Tipo de cambio ───────────────────────────────────────────────────────────
@st.cache_data(ttl=86400, show_spinner="Obteniendo tipo de cambio...")
def _get_dict_cambio():
    API_BASE = "https://apis.datos.gob.ar/series/api/"
    SERIE = '92.2_TIPO_CAMBIION_0_0_21_24'

    def _fetch(start, end):
        params = urllib.parse.urlencode({
            'ids': SERIE,
            'start_date': start,
            'end_date': end,
            'collapse': 'month',
            'format': 'csv',
        })
        url = f"{API_BASE}series?{params}"
        return pd.read_csv(url)

    try:
        df = pd.concat([
            _fetch('2010-01-01', '2014-12-01'),
            _fetch('2015-01-01', '2019-12-01'),
            _fetch('2020-01-01', '2023-01-01'),
        ])
        return {r['indice_tiempo']: r['tipo_cambio_valuacion']
                for r in df.to_dict('records')}
    except Exception:
        return {}


# ── Carga SQLite ─────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Cargando datos contables...")
def _load_data():
    dict_cambio = _get_dict_cambio()

    con_c = sqlite3.connect(os.path.join(BASE_DATA, 'cuentas.sqlite'))
    try:
        df_cuentas = pd.read_sql_query("SELECT * FROM cuentas", con_c)
    finally:
        con_c.close()

    # fallback CSV si la tabla no tiene datos
    if df_cuentas.empty:
        df_cuentas = pd.read_csv(
            os.path.join(BASE_DATA, 'cuenta_2022.csv'),
            dtype={'cuenta': 'object', 'c_nombre': 'object', 'nivel': 'int64'},
        )

    df_cuentas = df_cuentas.astype({'cuenta': 'object'})
    df_cuentas['c_nombre'] = df_cuentas['c_nombre'].str.rstrip()

    con_m = sqlite3.connect(os.path.join(BASE_DATA, 'movconta.sqlite'))
    try:
        df_mov = pd.read_sql_query("SELECT * FROM movconta", con_m)
    finally:
        con_m.close()

    df_mov = df_mov.astype({'cuenta': 'object'})
    df_mov['fecha'] = pd.to_datetime(df_mov['fecha_mov'], errors='coerce', format='%Y-%m-%d')

    def _dolarizar(row):
        f = str(row['fecha_mov'])[:8] + '01'
        tc = dict_cambio.get(f)
        if tc:
            return int(row['nmonto'] / tc)
        return np.nan

    df_mov['nmonto_usd'] = df_mov.apply(_dolarizar, axis=1)
    df_mov['cuenta_padre'] = df_mov['cuenta'].apply(_get_cuenta_padre)

    df_mov['anio'] = df_mov['fecha'].dt.year
    df_yearly = (
        df_mov
        .groupby(['anio', 'cuenta', 'cuenta_padre', 'ctipoas'])['nmonto_usd']
        .sum()
        .reset_index()
        .rename(columns={'anio': 'fecha'})
    )
    df_yearly = df_yearly.astype({'cuenta': 'object', 'fecha': 'int64'})

    cuentas_dic = {r['cuenta']: r['c_nombre'] for r in df_cuentas[['cuenta', 'c_nombre']].to_dict('records')}
    cuentas_dic['000000000000'] = 'DJSA'

    return df_mov, df_yearly, df_cuentas, cuentas_dic


# ── Helpers jerarquía ────────────────────────────────────────────────────────
def _get_cuenta_padre(cuenta: str) -> str:
    blocks = [cuenta[:1], cuenta[1:2], cuenta[2:3], cuenta[3:5],
              cuenta[5:7], cuenta[7:9], cuenta[9:11], cuenta[11:]]
    can_add = False
    out = []
    for b in blocks[::-1]:
        if (b == '0' or b == '00') and not can_add:
            pass
        else:
            if not can_add:
                can_add = True
            else:
                out.insert(0, b)
    return ''.join(out)[::-1].zfill(12)[::-1]


def _get_all_parents(start: str, root: str) -> list:
    parents = []
    parent = _get_cuenta_padre(start)
    while parent not in root and parent != '000000000000':
        parents.append(parent)
        parent = _get_cuenta_padre(parent)
    return parents


def _build_sunburst(df_yearly, cuentas_dic, fechas=None, cuenta_base=None, tipoas=None):
    df = df_yearly.copy()
    if fechas:
        df = df[df['fecha'].isin(fechas)]
    if tipoas:
        df = df[df['ctipoas'].isin(tipoas)]
    if cuenta_base:
        base = cuenta_base.rstrip('0')
        df = df[df['cuenta'].str.startswith(base)]

    # Agregar por cuenta (colapsar años y tipos)
    df_agg = (df.groupby(['cuenta', 'cuenta_padre'])['nmonto_usd']
               .sum()
               .reset_index())
    df_agg = df_agg[df_agg['nmonto_usd'].notna()].copy()

    if df_agg.empty:
        return {'ids': [], 'names': [], 'parents': [], 'values': []}

    all_ids = set(df_agg['cuenta'].tolist())

    # Agregar nodos intermedios faltantes recorriendo la jerarquía
    rows_to_add = []
    for cuenta in list(all_ids):
        current = cuenta
        while True:
            padre = _get_cuenta_padre(current)
            if padre == current or padre == '000000000000':
                break
            if padre not in all_ids:
                all_ids.add(padre)
                rows_to_add.append({
                    'cuenta': padre,
                    'cuenta_padre': _get_cuenta_padre(padre),
                    'nmonto_usd': 0,
                })
            current = padre

    if rows_to_add:
        df_agg = pd.concat([df_agg, pd.DataFrame(rows_to_add)], ignore_index=True)
        df_agg = df_agg.groupby(['cuenta', 'cuenta_padre'])['nmonto_usd'].sum().reset_index()

    # El nodo raíz debe tener parent vacío para que Plotly lo renderice
    if cuenta_base and cuenta_base in df_agg['cuenta'].values:
        df_agg.loc[df_agg['cuenta'] == cuenta_base, 'cuenta_padre'] = ''
    else:
        # Nodos cuyo padre no está en la lista → son raíces
        known = set(df_agg['cuenta'])
        df_agg.loc[~df_agg['cuenta_padre'].isin(known), 'cuenta_padre'] = ''

    def _label(c):
        key = c[::-1].zfill(12)[::-1]
        return cuentas_dic.get(key, c)

    # Plotly sunburst necesita valores positivos
    df_agg['valor'] = df_agg['nmonto_usd'].abs()

    return {
        'ids': df_agg['cuenta'].tolist(),
        'names': [_label(c) for c in df_agg['cuenta']],
        'parents': df_agg['cuenta_padre'].tolist(),
        'values': df_agg['valor'].tolist(),
    }


# ── UI ────────────────────────────────────────────────────────────────────────
st.title("📊 Holistor — Análisis Contable")
st.markdown("Seleccioná año(s), cuenta contable y tipo de asiento para explorar el sunburst.")

try:
    df_mov, df_yearly, df_cuentas, cuentas_dic = _load_data()

    # ── Filtros ──────────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns([2, 3, 2])
    with col1:
        anos_disp = sorted(df_mov['fecha'].dt.year.dropna().unique().astype(int))
        sel_anos = st.multiselect("Año(s)", anos_disp, default=[anos_disp[-1]] if anos_disp else [])
    with col2:
        df_c_opciones = df_cuentas[df_cuentas['nivel'] < 8][['cuenta', 'c_nombre', 'nivel']]
        opciones_cuentas = {
            f"{'_' * (int(r['nivel']) - 1)}({r['cuenta']}) {r['c_nombre']}": r['cuenta']
            for _, r in df_c_opciones.sort_values('cuenta').iterrows()
        }
        sel_label = st.selectbox("Cuenta contable base", list(opciones_cuentas.keys()))
        sel_cuenta = opciones_cuentas[sel_label]
    with col3:
        tipoas_disp = sorted(df_mov['ctipoas'].dropna().unique())
        sel_tipo = st.multiselect("Tipo de asiento", tipoas_disp)

    if st.button("Actualizar"):
        st.cache_data.clear()

    # ── Sunburst ──────────────────────────────────────────────────────────────
    sb_data = _build_sunburst(
        df_yearly,
        cuentas_dic,
        fechas=sel_anos if sel_anos else None,
        cuenta_base=sel_cuenta if sel_cuenta else None,
        tipoas=sel_tipo if sel_tipo else None,
    )

    if sb_data['ids']:
        fig_sb = px.sunburst(
            sb_data,
            ids='ids',
            names='names',
            parents='parents',
            values='values',
            title='Distribución de cuentas (USD)',
            height=700,
            branchvalues='total',
        )
        fig_sb.update_traces(textinfo='label+percent parent')
        st.plotly_chart(fig_sb, use_container_width=True)
    else:
        st.info("Sin datos para la selección.")

    # ── Histórico de cuenta seleccionada ─────────────────────────────────────
    st.subheader("Evolución histórica de la cuenta seleccionada")
    base_str = sel_cuenta.rstrip('0') if sel_cuenta else ''
    if base_str:
        df_hist = df_mov[df_mov['cuenta'].str.startswith(base_str)].copy()
        if sel_anos:
            df_hist = df_hist[df_hist['fecha'].dt.year.isin(sel_anos)]
        if sel_tipo:
            df_hist = df_hist[df_hist['ctipoas'].isin(sel_tipo)]

        df_hist['Ano'] = df_hist['fecha'].dt.year
        df_hist['Mes'] = df_hist['fecha'].dt.month
        df_grp2 = (
            df_hist.groupby(['Ano', 'Mes', 'ctipoas'])['nmonto_usd']
            .sum()
            .reset_index()
        )
        df_grp2['Date'] = pd.to_datetime({'year': df_grp2['Ano'], 'month': df_grp2['Mes'], 'day': 1})
        nombre_cuenta = cuentas_dic.get(sel_cuenta[::-1].zfill(12)[::-1], sel_cuenta)
        fig_hist = px.line(df_grp2, x='Date', y='nmonto_usd', color='ctipoas',
                           title=f'Evolución — {nombre_cuenta}',
                           labels={'nmonto_usd': 'Monto USD', 'ctipoas': 'Tipo asiento'})
        st.plotly_chart(fig_hist, use_container_width=True)

        # ── Tabla detalle ─────────────────────────────────────────────────────
        with st.expander("Detalle de movimientos"):
            cols_show = [c for c in ['fecha_mov', 'ctipoas', 'cuenta', 'cleyenda', 'concepto', 'nmonto_usd']
                         if c in df_hist.columns]
            st.dataframe(df_hist[cols_show].sort_values('fecha_mov', ascending=False),
                         use_container_width=True)

except Exception as e:
    st.error(f"Error cargando datos contables: {e}")
    st.exception(e)
