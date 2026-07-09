import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Gestión — DJSA", page_icon="📊", layout="wide")

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
    currency_cols = ['Gasto U$D', 'Ingreso U$D', 'MB U$D', 'MB/ha U$D',
                     'Valor/tn', 'Gasto U$D/ha', 'Ingreso U$D/ha',
                     'Gasto AR$', 'Ingreso AR$', 'MB AR$']
    for col in currency_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].apply(_clean_currency), errors='coerce')
    return df


# ── UI ───────────────────────────────────────────────────────────────────────
st.title("📊 Gestión")
col_title, col_refresh = st.columns([8, 1])
col_title.markdown("Márgenes brutos por campaña, establecimiento, rubro y actividad.")
if col_refresh.button("🔄 Actualizar", help="Limpiar cache y recargar datos"):
    _get_gestion.clear()
    st.rerun()

try:
    df = _get_gestion()

    # ── Filtros principales ──────────────────────────────────────────────────
    col_est, col_rub, col_act, col_sub, col_camp = st.columns(5)
    with col_est:
        establecimientos = sorted(df['Establecimiento'].dropna().unique())
        sel_est = st.multiselect("Establecimiento", establecimientos, default=establecimientos)
    with col_rub:
        rubros = sorted(df['Rubro'].dropna().unique())
        sel_rubro = st.multiselect("Rubro", rubros, default=rubros)
    with col_act:
        _df_act = df[df['Rubro'].isin(sel_rubro)] if sel_rubro else df
        acts_disp = sorted(_df_act['Actividad'].dropna().unique())
        sel_act = st.multiselect("Actividad", acts_disp, default=acts_disp)
    with col_sub:
        _df_sub = df[df['Actividad'].isin(sel_act)] if sel_act else df
        subcats = sorted(_df_sub['Subcategoria'].dropna().unique()) if 'Subcategoria' in df.columns else []
        sel_sub = st.multiselect("Subcategoría", subcats, default=subcats)
    with col_camp:
        campanas = sorted(df['Campaña'].unique())
        sel_camp = st.multiselect("Campaña(s)", campanas, default=campanas[-5:])

    # Aplicar filtros
    df_f = df.copy()
    if sel_est:
        df_f = df_f[df_f['Establecimiento'].isin(sel_est)]
    if sel_rubro:
        df_f = df_f[df_f['Rubro'].isin(sel_rubro)]
    if sel_sub and 'Subcategoria' in df_f.columns:
        df_f = df_f[df_f['Subcategoria'].isin(sel_sub)]
    if sel_act:
        df_f = df_f[df_f['Actividad'].isin(sel_act)]
    if sel_camp:
        df_f = df_f[df_f['Campaña'].isin(sel_camp)]

    if df_f.empty:
        st.warning("No hay datos con los filtros seleccionados.")
        st.stop()

    # ── Selector de métrica ──────────────────────────────────────────────────
    metricas_usd = ['MB U$D', 'Ingreso U$D', 'Gasto U$D', 'MB/ha U$D',
                    'Ingreso U$D/ha', 'Gasto U$D/ha', 'Valor/tn']
    metricas_disp = [m for m in metricas_usd if m in df_f.columns and df_f[m].notna().any()]

    metrica = st.selectbox("Métrica", metricas_disp, key="metrica_gestion")

    # Métricas por unidad (ya son /ha o /tn): se promedian, no se suman
    _METRICAS_PROM = {'MB/ha U$D', 'Ingreso U$D/ha', 'Gasto U$D/ha', 'Valor/tn'}
    _es_prom = metrica in _METRICAS_PROM
    _agg = 'mean' if _es_prom else 'sum'

    # ── KPIs resumidos ───────────────────────────────────────────────────────
    ultima_camp = df_f['Campaña'].max()
    df_ult = df_f[df_f['Campaña'] == ultima_camp]
    penult = sorted(df_f['Campaña'].unique())[-2] if len(df_f['Campaña'].unique()) >= 2 else None
    df_pen = df_f[df_f['Campaña'] == penult] if penult else pd.DataFrame()

    k1, k2, k3, k4 = st.columns(4)
    total_ult = df_ult[metrica].mean() if _es_prom else df_ult[metrica].sum()
    total_pen = (df_pen[metrica].mean() if _es_prom else df_pen[metrica].sum()) if not df_pen.empty else 0
    delta = total_ult - total_pen if total_pen != 0 else None
    _kpi_label = f"Promedio {metrica}" if _es_prom else f"Total {metrica}"

    k1.metric(f"{_kpi_label} ({ultima_camp})", f"${total_ult:,.0f}",
              delta=f"${delta:,.0f}" if delta is not None else None)
    k2.metric("Establecimientos", len(df_f['Establecimiento'].unique()))
    k3.metric("Actividades", len(df_f['Actividad'].unique()))
    k4.metric("Campañas", len(df_f['Campaña'].unique()))

    st.divider()

    # ── Tabs de visualización ────────────────────────────────────────────────
    tab_evol, tab_comp, tab_sede, tab_detalle = st.tabs([
        "Evolución", "Comparación", "Por Establecimiento", "Datos"
    ])

    # ── Tab Evolución ────────────────────────────────────────────────────────
    with tab_evol:
        col_color = st.radio("Agrupar por", ['Rubro', 'Actividad', 'Establecimiento'],
                             horizontal=True, key="evol_color")

        df_evo = df_f.groupby(['Date', 'Campaña', col_color])[metrica].agg(_agg).reset_index()
        df_evo = df_evo.sort_values('Date')
        _camp_order = df_evo.drop_duplicates('Campaña').sort_values('Date')['Campaña'].tolist()

        fig_evo = px.bar(
            df_evo, x='Campaña', y=metrica, color=col_color,
            title=f'Evolución {metrica}',
            barmode='group',
            category_orders={'Campaña': _camp_order},
        )
        fig_evo.update_layout(height=500, xaxis_tickangle=-45)
        st.plotly_chart(fig_evo, use_container_width=True)

        # Línea de evolución
        df_acum = df_f.groupby(['Date', 'Campaña'])[metrica].agg(_agg).reset_index()
        df_acum = df_acum.sort_values('Date')
        _evol_title = f'Evolución {"promedio" if _es_prom else "total"} {metrica}'
        fig_linea = px.line(
            df_acum, x='Campaña', y=metrica,
            title=_evol_title,
            markers=True,
            category_orders={'Campaña': _camp_order},
        )
        fig_linea.update_layout(height=400)
        st.plotly_chart(fig_linea, use_container_width=True)

    # ── Tab Comparación ──────────────────────────────────────────────────────
    with tab_comp:
        st.subheader(f"Composición de {metrica}")

        col_tipo, col_camp_sel = st.columns(2)
        with col_tipo:
            tipo_comp = st.radio("Desglose por", ['Actividad', 'Rubro'], horizontal=True, key="comp_tipo")
        with col_camp_sel:
            camp_comp = st.selectbox("Campaña", sorted(df_f['Campaña'].unique(), reverse=True), key="comp_camp")

        df_comp = df_f[df_f['Campaña'] == camp_comp]

        col_pie, col_bar = st.columns(2)
        with col_pie:
            df_pie = df_comp.groupby(tipo_comp)[metrica].agg(_agg).reset_index()
            df_pie = df_pie[df_pie[metrica] != 0]
            fig_pie = px.pie(df_pie, values=metrica, names=tipo_comp,
                             title=f'{metrica} — {camp_comp}')
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_bar:
            df_bar = df_comp.groupby([tipo_comp])[metrica].agg(_agg).reset_index().sort_values(metrica, ascending=True)
            fig_hbar = px.bar(df_bar, x=metrica, y=tipo_comp, orientation='h',
                              title=f'{metrica} por {tipo_comp} — {camp_comp}',
                              color=tipo_comp)
            fig_hbar.update_layout(showlegend=False, height=400)
            st.plotly_chart(fig_hbar, use_container_width=True)

        # Treemap
        group_cols = ['Establecimiento', 'Rubro', 'Actividad']
        df_tree = df_comp.groupby(group_cols)[metrica].agg(_agg).reset_index()
        df_tree = df_tree[df_tree[metrica] > 0]
        if not df_tree.empty:
            fig_tree = px.treemap(
                df_tree, path=['Establecimiento', 'Rubro', 'Actividad'],
                values=metrica,
                title=f'Treemap {metrica} — {camp_comp}',
                color='Rubro',
            )
            fig_tree.update_layout(height=500)
            st.plotly_chart(fig_tree, use_container_width=True)

    # ── Tab Por Establecimiento ──────────────────────────────────────────────
    with tab_sede:
        st.subheader("Comparación entre establecimientos")

        df_sede = df_f.groupby(['Campaña', 'Establecimiento'])[metrica].agg(_agg).reset_index()
        df_sede = df_sede.merge(df_f[['Campaña','Date']].drop_duplicates(), on='Campaña').sort_values('Date')
        fig_sede = px.bar(
            df_sede, x='Campaña', y=metrica, color='Establecimiento',
            barmode='group',
            title=f'{metrica} por establecimiento',
            category_orders={'Campaña': _camp_order},
        )
        fig_sede.update_layout(height=450, xaxis_tickangle=-45)
        st.plotly_chart(fig_sede, use_container_width=True)

        # Por rubro dentro de cada sede
        for est in sorted(df_f['Establecimiento'].unique()):
            df_est = df_f[df_f['Establecimiento'] == est]
            df_est_g = df_est.groupby(['Campaña', 'Rubro'])[metrica].agg(_agg).reset_index()
            df_est_g = df_est_g.merge(df_f[['Campaña','Date']].drop_duplicates(), on='Campaña').sort_values('Date')
            fig_est = px.bar(
                df_est_g, x='Campaña', y=metrica, color='Rubro',
                title=f'{est} — {metrica} por rubro',
                barmode='stack',
                category_orders={'Campaña': _camp_order},
            )
            fig_est.update_layout(height=400, xaxis_tickangle=-45)
            st.plotly_chart(fig_est, use_container_width=True)

    # ── Tab Datos ────────────────────────────────────────────────────────────
    with tab_detalle:
        st.subheader("Tabla resumen por campaña")
        group_cols = [c for c in ['Establecimiento', 'Rubro', 'Actividad'] if c in df_f.columns]
        if group_cols:
            df_tabla = df_f.groupby(group_cols + ['Campaña'])[metrica].agg(_agg).reset_index()
            df_wide = df_tabla.pivot_table(index=group_cols, columns='Campaña', values=metrica, aggfunc=_agg)
            _col_resumen = 'PROMEDIO' if _es_prom else 'TOTAL'
            df_wide[_col_resumen] = df_wide.mean(axis=1) if _es_prom else df_wide.sum(axis=1)
            df_wide = df_wide.sort_values(_col_resumen, ascending=False)
            st.dataframe(df_wide.style.format('${:,.0f}'), use_container_width=True)

        st.divider()
        st.subheader("Datos brutos")
        st.dataframe(df_f, use_container_width=True)

        csv = df_f.to_csv(index=False).encode('utf-8')
        st.download_button("Descargar datos filtrados (CSV)", csv,
                           file_name='gestion_filtrado.csv', mime='text/csv')

except Exception as e:
    st.error(f"Error cargando datos de gestión: {e}")
