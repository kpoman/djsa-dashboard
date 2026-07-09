import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import os

st.set_page_config(page_title="Patrimonio — DJSA", page_icon="🏦", layout="wide")

st.title("🏦 Patrimonio")
col_title, col_refresh = st.columns([8, 1])
col_title.markdown("Evolución patrimonial — valores convertidos a USD al tipo de cambio del 31 de diciembre de cada año.")
if col_refresh.button("🔄 Actualizar", help="Limpiar cache y recargar datos"):
    _get_patrimonio.clear()
    st.rerun()

URL_PATRIMONIO = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vQlld86JegRoZHrKhWkWcb4kwt5etllP3W7bN57mqKRIP8jyMd8uW-4kjDZZMMe54BRL7PDtDUkYtY4"
    "/pub?output=csv"
)

# TC aproximado para años previos al CSV histórico (pre-2010)
_TC_MANUAL = {
    2004: 2.97,
    2005: 3.03,
    2006: 3.07,
    2007: 3.15,
    2008: 3.45,
    2009: 3.80,
}


@st.cache_data(show_spinner="Cargando datos patrimoniales...")
def _get_patrimonio():
    base = os.path.dirname(__file__)
    local_csv = os.path.join(base, '..', 'data', 'patrimonio.csv')

    # Lee del CSV local (caché en repo). Si no existe, baja de Google Sheets.
    if os.path.exists(local_csv):
        df = pd.read_csv(local_csv)
    else:
        df = pd.read_csv(URL_PATRIMONIO)
    df['Tipo'] = df['Tipo'].str.strip().str.lower()
    df['Item'] = df['Item'].str.strip().str.lower()

    df_tc_raw = pd.read_csv(
        os.path.join(base, '..', 'data', 'usdars.csv'),
        encoding='utf-8-sig'
    )
    df_tc_raw['Fecha'] = pd.to_datetime(
        df_tc_raw['Fecha'].astype(str).str.strip().str.strip('"'),
        format='%d.%m.%Y'
    )
    df_tc_raw['TC'] = (
        df_tc_raw['Último'].astype(str).str.strip().str.strip('"')
        .str.replace('.', '', regex=False)
        .str.replace(',', '.', regex=False)
        .astype(float)
    )
    df_tc = df_tc_raw[['Fecha', 'TC']].sort_values('Fecha').set_index('Fecha')

    tc_anual = dict(_TC_MANUAL)
    for anio in df['Anio'].unique():
        a = int(anio)
        if a not in tc_anual:
            subset = df_tc[df_tc.index <= pd.Timestamp(f'{a}-12-31')]
            if not subset.empty:
                tc_anual[a] = float(subset['TC'].iloc[-1])

    df['TC'] = df['Anio'].map(tc_anual)
    df['Monto_USD'] = df['Monto'] / df['TC']

    return df, tc_anual


try:
    df, tc_anual = _get_patrimonio()

    # Agregar por año y tipo
    df_agg = df.groupby(['Anio', 'Tipo'])['Monto_USD'].sum().reset_index()

    df_piv = df_agg.pivot_table(
        index='Anio', columns='Tipo', values='Monto_USD', aggfunc='sum'
    ).fillna(0).reset_index()

    def _col(name):
        return df_piv[name] if name in df_piv.columns else pd.Series([0] * len(df_piv))

    df_piv['Activo Total']    = _col('activo corriente') + _col('activo no corriente')
    df_piv['Pasivo Total']    = _col('pasivo corriente') + _col('pasivo no corriente')
    df_piv['PN']              = df_piv['Activo Total'] - df_piv['Pasivo Total']
    df_piv['PN_declarado']    = _col('patrimonio neto')
    df_piv = df_piv.sort_values('Anio')

    anios = df_piv['Anio'].astype(int).tolist()

    # ── KPIs ────────────────────────────────────────────────────────────────────
    ult  = df_piv.iloc[-1]
    prev = df_piv.iloc[-2] if len(df_piv) >= 2 else None

    def _delta(col):
        if prev is None:
            return None
        return f"U$D {(ult[col] - prev[col]) / 1e6:+,.1f}M"

    k1, k2, k3, k4 = st.columns(4)
    k1.metric(f"Activo ({int(ult['Anio'])})",
              f"U$D {ult['Activo Total'] / 1e6:,.1f}M", delta=_delta('Activo Total'))
    k2.metric(f"Pasivo ({int(ult['Anio'])})",
              f"U$D {ult['Pasivo Total'] / 1e6:,.1f}M", delta=_delta('Pasivo Total'))
    k3.metric(f"Patrimonio Neto ({int(ult['Anio'])})",
              f"U$D {ult['PN'] / 1e6:,.1f}M", delta=_delta('PN'))
    lev = ult['Pasivo Total'] / ult['PN'] if ult['PN'] > 0 else 0
    k4.metric("Leverage (Pasivo / PN)", f"{lev:.2f}x",
              delta=f"{lev - prev['Pasivo Total'] / prev['PN']:.2f}x" if prev is not None and prev['PN'] > 0 else None,
              delta_color="inverse")

    st.divider()

    tab_evol, tab_comp, tab_datos = st.tabs(["Evolución", "Composición", "Datos"])

    # ── Tab Evolución ────────────────────────────────────────────────────────────
    with tab_evol:
        fig = go.Figure()

        # Activo: corriente (base) + no corriente (encima)
        ac  = (_col('activo corriente').values  / 1e6).tolist()
        anc = (_col('activo no corriente').values / 1e6).tolist()
        pc  = (_col('pasivo corriente').values   / 1e6).tolist()
        pnc = (_col('pasivo no corriente').values / 1e6).tolist()
        pn  = (df_piv['PN'].values / 1e6).tolist()

        fig.add_trace(go.Bar(
            x=anios, y=ac,  name='Activo Corriente',
            marker_color='#1976D2', offsetgroup=0,
        ))
        fig.add_trace(go.Bar(
            x=anios, y=anc, name='Activo No Corriente',
            marker_color='#90CAF9', offsetgroup=0,
        ))
        fig.add_trace(go.Bar(
            x=anios, y=pc,  name='Pasivo Corriente',
            marker_color='#C62828', offsetgroup=1,
        ))
        fig.add_trace(go.Bar(
            x=anios, y=pnc, name='Pasivo No Corriente',
            marker_color='#FFCDD2', offsetgroup=1,
        ))
        fig.add_trace(go.Scatter(
            x=anios, y=pn,
            mode='lines+markers',
            name='Patrimonio Neto',
            line=dict(color='#2E7D32', width=3),
            marker=dict(size=9, symbol='circle'),
        ))

        fig.update_layout(
            barmode='group',
            title='Evolución patrimonial (millones USD)',
            yaxis_title='Millones USD',
            xaxis=dict(type='category', title='Año'),
            height=520,
            hovermode='x unified',
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Solvencia
        df_piv['Leverage'] = df_piv['Pasivo Total'] / df_piv['PN'].replace(0, float('nan'))
        fig_lev = go.Figure()
        fig_lev.add_trace(go.Scatter(
            x=anios, y=df_piv['Leverage'].tolist(),
            mode='lines+markers',
            line=dict(color='#F57C00', width=2),
            marker=dict(size=7),
            name='Leverage',
        ))
        fig_lev.add_hline(y=1, line_dash='dash', line_color='gray',
                          annotation_text='Leverage = 1')
        fig_lev.update_layout(
            title='Leverage (Pasivo / Patrimonio Neto)',
            xaxis=dict(type='category', title='Año'),
            yaxis_title='Pasivo / PN',
            height=300,
        )
        st.plotly_chart(fig_lev, use_container_width=True)

        # ── Detalle por sub-ítem ─────────────────────────────────────────────────
        st.divider()
        st.subheader("Evolución por sub-ítem")

        categorias_disp = sorted(df[~df['Tipo'].str.startswith('patrimonio')]['Tipo'].unique())
        cats_sel = st.multiselect(
            "Categoría(s)",
            options=categorias_disp,
            default=[categorias_disp[0]] if categorias_disp else [],
            format_func=str.title,
            key='evol_cats',
        )

        if cats_sel:
            df_items = df[df['Tipo'].isin(cats_sel)].copy()
            df_items['Item_label'] = df_items['Item'].str.title()

            # Agregar por año e ítem (suma si hay duplicados)
            df_items_agg = (
                df_items
                .groupby(['Anio', 'Item_label'])['Monto_USD']
                .sum()
                .reset_index()
                .sort_values('Anio')
            )

            # Stacked bar por ítem a lo largo del tiempo
            fig_items = px.bar(
                df_items_agg,
                x='Anio', y='Monto_USD',
                color='Item_label',
                title=f'Evolución de ítems — {", ".join(t.title() for t in cats_sel)}',
                labels={'Monto_USD': 'USD', 'Anio': 'Año', 'Item_label': 'Ítem'},
                barmode='stack',
            )
            fig_items.update_layout(
                xaxis=dict(type='category'),
                yaxis_title='USD',
                height=480,
                hovermode='x unified',
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
            )
            fig_items.update_traces(hovertemplate='%{y:,.0f}')
            st.plotly_chart(fig_items, use_container_width=True)

            # Stacked area para ver tendencia continua
            fig_area = px.area(
                df_items_agg,
                x='Anio', y='Monto_USD',
                color='Item_label',
                title='Tendencia (área apilada)',
                labels={'Monto_USD': 'USD', 'Anio': 'Año', 'Item_label': 'Ítem'},
            )
            fig_area.update_layout(
                xaxis=dict(type='category'),
                yaxis_title='USD',
                height=380,
                hovermode='x unified',
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
            )
            st.plotly_chart(fig_area, use_container_width=True)
        else:
            st.info("Seleccioná al menos una categoría para ver el detalle.")

    # ── Tab Composición ──────────────────────────────────────────────────────────
    with tab_comp:
        anio_sel = st.selectbox("Año", sorted(df['Anio'].unique(), reverse=True))
        df_anio = df[df['Anio'] == anio_sel].copy()
        df_sin_pn = df_anio[~df_anio['Tipo'].str.startswith('patrimonio')]
        df_sin_pn = df_sin_pn[df_sin_pn['Monto_USD'] > 0]

        col_pie_a, col_pie_p = st.columns(2)
        with col_pie_a:
            df_act = df_sin_pn[df_sin_pn['Tipo'].str.startswith('activo')]
            if not df_act.empty:
                fig_pa = px.pie(
                    df_act, values='Monto_USD', names='Item',
                    title=f'Composición Activo {anio_sel}',
                    hole=0.35,
                    color_discrete_sequence=px.colors.sequential.Blues_r,
                )
                st.plotly_chart(fig_pa, use_container_width=True)

        with col_pie_p:
            df_pas = df_sin_pn[df_sin_pn['Tipo'].str.startswith('pasivo')]
            if not df_pas.empty:
                fig_pp = px.pie(
                    df_pas, values='Monto_USD', names='Item',
                    title=f'Composición Pasivo {anio_sel}',
                    hole=0.35,
                    color_discrete_sequence=px.colors.sequential.Reds_r,
                )
                st.plotly_chart(fig_pp, use_container_width=True)

        # Treemap
        df_tree = df_sin_pn.copy()
        df_tree['Categoría'] = df_tree['Tipo'].apply(
            lambda x: 'Activo' if x.startswith('activo') else 'Pasivo'
        )
        df_tree['Tipo_label'] = df_tree['Tipo'].str.title()
        df_tree['Item_label'] = df_tree['Item'].str.title()
        fig_tree = px.treemap(
            df_tree,
            path=['Categoría', 'Tipo_label', 'Item_label'],
            values='Monto_USD',
            title=f'Desglose patrimonial — {anio_sel}',
            color='Categoría',
            color_discrete_map={'Activo': '#1976D2', 'Pasivo': '#C62828'},
        )
        fig_tree.update_traces(
            texttemplate='%{label}<br>U$D %{value:,.0f}',
        )
        fig_tree.update_layout(height=480)
        st.plotly_chart(fig_tree, use_container_width=True)

    # ── Tab Datos ────────────────────────────────────────────────────────────────
    with tab_datos:
        st.subheader("Resumen por año (USD)")
        df_resumen = df_piv[['Anio', 'Activo Total', 'Pasivo Total', 'PN', 'PN_declarado', 'Leverage']].copy()
        df_resumen.columns = ['Año', 'Activo', 'Pasivo', 'PN (Activo−Pasivo)', 'PN Declarado', 'Leverage']
        st.dataframe(
            df_resumen.style.format({
                'Activo':             'U$D {:,.0f}',
                'Pasivo':             'U$D {:,.0f}',
                'PN (Activo−Pasivo)': 'U$D {:,.0f}',
                'PN Declarado':       'U$D {:,.0f}',
                'Leverage':           '{:.2f}x',
            }),
            use_container_width=True,
        )

        st.divider()
        st.subheader("Detalle por ítem")
        df_det = df[['Anio', 'Tipo', 'Item', 'Monto', 'TC', 'Monto_USD']].copy()
        df_det.columns = ['Año', 'Tipo', 'Ítem', 'Monto ARS', 'TC', 'Monto USD']
        st.dataframe(
            df_det.style.format({
                'Monto ARS': '{:,.0f}',
                'TC':        '{:.2f}',
                'Monto USD': '{:,.0f}',
            }),
            use_container_width=True,
        )

        csv_exp = df_det.to_csv(index=False).encode('utf-8')
        st.download_button("Descargar CSV", csv_exp,
                           file_name='patrimonio_usd.csv', mime='text/csv')

except Exception as e:
    st.error(f"Error cargando datos: {e}")
    st.exception(e)
