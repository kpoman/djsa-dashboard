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
@st.cache_data(ttl=86400, show_spinner="Cargando tipo de cambio...")
def _get_dict_cambio():
    """Carga USD/ARS desde data/usdars.csv y devuelve dict {YYYY-MM-01: tc}."""
    try:
        path = os.path.join(BASE_DATA, 'usdars.csv')
        df_tc = pd.read_csv(path, encoding='utf-8-sig')
        df_tc['Fecha'] = pd.to_datetime(
            df_tc['Fecha'].str.strip().str.strip('"'), format='%d.%m.%Y'
        )
        df_tc['TC'] = (
            df_tc['Último'].astype(str).str.strip().str.strip('"')
            .str.replace('.', '', regex=False)
            .str.replace(',', '.', regex=False)
            .astype(float)
        )
        df_tc = df_tc[['Fecha', 'TC']].dropna().sort_values('Fecha')
        df_tc = df_tc.set_index('Fecha').resample('MS').last().ffill()
        return {d.strftime('%Y-%m-%d'): tc for d, tc in df_tc['TC'].items()}
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

    # Sumar por cuenta hoja (colapsar años y tipos)
    df_agg = (df.groupby('cuenta')['nmonto_usd']
               .sum()
               .reset_index()
               .dropna(subset=['nmonto_usd']))
    df_agg['valor'] = df_agg['nmonto_usd'].abs()
    df_agg = df_agg[df_agg['valor'] > 0]

    if df_agg.empty:
        return None

    # Construir jerarquía completa: para cada hoja agregar todos sus ancestros
    leaf_ids = set(df_agg['cuenta'].tolist())
    all_accounts = set(leaf_ids)

    for cuenta in list(leaf_ids):
        current = cuenta
        for _ in range(10):
            padre = _get_cuenta_padre(current)
            if padre == current or padre == '000000000000':
                break
            all_accounts.add(padre)
            current = padre

    # Nodo raíz = cuenta_base (o nodo virtual si no hay base)
    root_id = cuenta_base if cuenta_base else 'ROOT'
    root_label = cuentas_dic.get(cuenta_base, cuenta_base) if cuenta_base else 'Total'

    ids, labels, parents, values = [root_id], [root_label], [''], [0]

    def _label(c):
        return cuentas_dic.get(c, c)

    def _parent_of(c):
        """Padre directo dentro del árbol, o root si su padre es el tope."""
        p = _get_cuenta_padre(c)
        if p == '000000000000' or p == c:
            return root_id
        if cuenta_base and not p.rstrip('0').startswith(cuenta_base.rstrip('0')):
            return root_id
        if p in all_accounts:
            return p
        return root_id

    # Agregar nodos intermedios (valor = suma de sus hojas)
    inter_ids = all_accounts - leaf_ids - {cuenta_base}
    for node in sorted(inter_ids):
        # Suma de hojas que cuelgan de este nodo
        prefix = node.rstrip('0')
        v = df_agg[df_agg['cuenta'].str.startswith(prefix)]['valor'].sum()
        ids.append(node)
        labels.append(_label(node))
        parents.append(_parent_of(node))
        values.append(v)

    # Agregar hojas
    for _, row in df_agg.iterrows():
        ids.append(row['cuenta'])
        labels.append(_label(row['cuenta']))
        parents.append(_parent_of(row['cuenta']))
        values.append(row['valor'])

    return {'ids': ids, 'labels': labels, 'parents': parents, 'values': values}


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

    if sb_data:
        fig_sb = px.sunburst(
            sb_data,
            ids='ids',
            names='labels',
            parents='parents',
            values='values',
            title='Distribución de cuentas (USD)',
            height=700,
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
