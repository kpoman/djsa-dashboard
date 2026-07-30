import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go
import os, io, tempfile

st.set_page_config(page_title="Lotes — DJSA", page_icon="🗺️", layout="wide")

# ── URLs Google Sheets (reemplazar con los links publicados) ─────────────────
URL_AMBIENTES = st.secrets.get("URL_AMBIENTES", "") if hasattr(st, "secrets") else ""
URL_PLANTEOS  = st.secrets.get("URL_PLANTEOS",  "") if hasattr(st, "secrets") else ""

# Fallback local mientras no hay sheet configurado
_LOCAL_AMB = os.path.join(os.path.dirname(__file__), '..', 'data', 'lotes_ambientes.csv')
_LOCAL_PLN = os.path.join(os.path.dirname(__file__), '..', 'data', 'lotes_planteos.csv')

# ── Colores por actividad ────────────────────────────────────────────────────
_COLORES = {
    'Maíz':       '#F9A825', 'Soja':       '#558B2F',
    'Girasol':    '#FDD835', 'Trigo':      '#A1887F',
    'Cebada':     '#BCAAA4', 'Invernada':  '#1565C0',
    'Cría':       '#6A1B9A', 'Tambo':      '#00838F',
    'Pastura':    '#2E7D32', 'Campo Natural': '#795548',
    'Verdeo':     '#00897B', 'Sin dato':   '#9E9E9E',
}

def _color(actividad):
    return _COLORES.get(actividad, '#9E9E9E')


# ── Carga de datos ───────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner="Cargando ambientes...")
def _get_ambientes():
    if URL_AMBIENTES:
        return pd.read_csv(URL_AMBIENTES)
    if os.path.exists(_LOCAL_AMB):
        return pd.read_csv(_LOCAL_AMB)
    return pd.DataFrame(columns=['campo','lote_id','lote_nombre','ambiente_id','ambiente_nombre','ha'])

@st.cache_data(ttl=3600, show_spinner="Cargando planteos...")
def _get_planteos():
    if URL_PLANTEOS:
        return pd.read_csv(URL_PLANTEOS)
    if os.path.exists(_LOCAL_PLN):
        return pd.read_csv(_LOCAL_PLN)
    return pd.DataFrame(columns=[
        'campo','lote_id','ambiente_id','campaña','actividad','escenario',
        'seccion','orden','item','unidad',
        'precio_ppto','cant_ppto','valor_ppto',
        'precio_real','cant_real','valor_real',
        'diferencia','nota'
    ])


df_amb = _get_ambientes()
df_pln = _get_planteos()

# ── Header ───────────────────────────────────────────────────────────────────
st.title("🗺️ Lotes y Ambientes")
col_h, col_ref = st.columns([8, 1])
col_h.markdown("Gestión de lotes por campo — mapa, planteos técnicos y control presupuestario.")
if col_ref.button("🔄 Actualizar", help="Limpiar cache"):
    _get_ambientes.clear(); _get_planteos.clear(); st.rerun()

# ── Selector jerárquico en sidebar ───────────────────────────────────────────
with st.sidebar:
    st.header("Filtros")
    campos = sorted(df_amb['campo'].dropna().unique()) if not df_amb.empty else []
    sel_campo = st.selectbox("Campo", ["(Todos)"] + campos)

    df_amb_f = df_amb if sel_campo == "(Todos)" else df_amb[df_amb['campo'] == sel_campo]
    lotes = sorted(df_amb_f['lote_nombre'].dropna().unique())
    sel_lote = st.selectbox("Lote", ["(Todos)"] + list(lotes))

    df_amb_f2 = df_amb_f if sel_lote == "(Todos)" else df_amb_f[df_amb_f['lote_nombre'] == sel_lote]
    ambs = sorted(df_amb_f2['ambiente_nombre'].dropna().unique())
    sel_amb = st.selectbox("Ambiente", ["(Todos)"] + list(ambs))

    st.divider()
    campanas = sorted(df_pln['campaña'].dropna().unique(), reverse=True) if not df_pln.empty else []
    sel_camp = st.selectbox("Campaña", ["(Todas)"] + list(campanas))

    actividades = sorted(df_pln['actividad'].dropna().unique()) if not df_pln.empty else []
    sel_act = st.multiselect("Actividad", actividades, default=actividades)

# Breadcrumb
_parts = [p for p in [sel_campo, sel_lote, sel_amb] if p != "(Todos)"]
if _parts:
    st.caption("📍 " + " › ".join(_parts))

# ── Tabs principales ─────────────────────────────────────────────────────────
tab_mapa, tab_planteo, tab_analiticos = st.tabs(["🗺️ Mapa", "📋 Planteo", "📊 Analíticos"])

# ════════════════════════════════════════════════════════════════════════════
# TAB MAPA
# ════════════════════════════════════════════════════════════════════════════
with tab_mapa:
    col_map, col_kml = st.columns([3, 1])

    with col_kml:
        st.subheader("KML")
        st.caption("Subí los archivos KML de cada campo para ver los lotes en el mapa.")
        kml_merced    = st.file_uploader("La Merced (.kml)", type=['kml'], key='kml_merced')
        kml_pillahuinco = st.file_uploader("Pillahuinco (.kml)", type=['kml'], key='kml_pillahuinco')

        # Persistir en data/ si se sube
        for _fname, _fobj in [('la_merced.kml', kml_merced), ('pillahuinco.kml', kml_pillahuinco)]:
            if _fobj:
                _dst = os.path.join(os.path.dirname(__file__), '..', 'data', _fname)
                with open(_dst, 'wb') as f:
                    f.write(_fobj.read())
                st.success(f"Guardado: {_fname}")

        st.divider()
        st.caption("**Leyenda actividades**")
        for act, col in _COLORES.items():
            st.markdown(
                f'<span style="background:{col};padding:2px 8px;border-radius:4px;'
                f'color:white;font-size:12px">{act}</span>',
                unsafe_allow_html=True
            )

    with col_map:
        # Cargar KML desde data/ si existen
        _kml_files = {}
        for _campo, _fname in [('La Merced', 'la_merced.kml'), ('Pillahuinco', 'pillahuinco.kml')]:
            _path = os.path.join(os.path.dirname(__file__), '..', 'data', _fname)
            if os.path.exists(_path):
                _kml_files[_campo] = _path

        # Filtrar planteos para colorear el mapa
        _df_map = df_pln.copy()
        if sel_camp != "(Todas)":
            _df_map = _df_map[_df_map['campaña'] == sel_camp]
        _act_por_amb = _df_map.groupby('ambiente_id')['actividad'].first().to_dict() if not _df_map.empty else {}

        # Mapa base centrado en Buenos Aires
        m = folium.Map(location=[-36.5, -62.0], zoom_start=8, tiles='CartoDB positron')

        if _kml_files:
            for _campo, _kml_path in _kml_files.items():
                folium.GeoJson(
                    _kml_path,
                    name=_campo,
                    style_function=lambda feat, _c=_campo: {
                        'fillColor': _color(
                            _act_por_amb.get(
                                feat['properties'].get('name', ''), 'Sin dato'
                            )
                        ),
                        'color': '#333',
                        'weight': 1.5,
                        'fillOpacity': 0.6,
                    },
                    tooltip=folium.GeoJsonTooltip(
                        fields=['name', 'description'],
                        aliases=['Ambiente', 'Descripción'],
                        localize=True,
                    ),
                ).add_to(m)
            folium.LayerControl().add_to(m)
            st_folium(m, width='100%', height=580)
        else:
            st.info("Subí los KML en el panel de la derecha para ver los lotes en el mapa.")
            st_folium(m, width='100%', height=400)

# ════════════════════════════════════════════════════════════════════════════
# TAB PLANTEO
# ════════════════════════════════════════════════════════════════════════════
with tab_planteo:
    if df_pln.empty or df_amb.empty:
        st.info("Configurá el Google Sheet de Planteos para ver los datos aquí.")
        st.markdown("""
**Estructura del Sheet necesaria:**

**Tab `Ambientes`:**
`campo | lote_id | lote_nombre | ambiente_id | ambiente_nombre | ha`

**Tab `Planteos`:**
`campo | lote_id | ambiente_id | campaña | actividad | escenario | seccion | orden | item | unidad | precio_ppto | cant_ppto | valor_ppto | precio_real | cant_real | valor_real | diferencia | nota`
        """)
        st.stop()

    # Filtrar planteos según selección sidebar
    df_f = df_pln.copy()
    if sel_campo != "(Todos)":
        df_f = df_f[df_f['campo'] == sel_campo]
    if sel_lote != "(Todos)":
        _amb_ids = df_amb[df_amb['lote_nombre'] == sel_lote]['ambiente_id'].unique()
        df_f = df_f[df_f['ambiente_id'].isin(_amb_ids)]
    if sel_amb != "(Todos)":
        _amb_id = df_amb[df_amb['ambiente_nombre'] == sel_amb]['ambiente_id'].values
        df_f = df_f[df_f['ambiente_id'].isin(_amb_id)]
    if sel_camp != "(Todas)":
        df_f = df_f[df_f['campaña'] == sel_camp]
    if sel_act:
        df_f = df_f[df_f['actividad'].isin(sel_act)]

    if df_f.empty:
        st.warning("Sin datos para la selección actual.")
        st.stop()

    # ── Selector de planteo específico ──────────────────────────────────────
    col_p1, col_p2, col_p3 = st.columns(3)
    _camps  = sorted(df_f['campaña'].unique(), reverse=True)
    _acts   = sorted(df_f['actividad'].unique())
    _escs   = sorted(df_f['escenario'].unique())

    _camp_sel = col_p1.selectbox("Campaña", _camps, key='plt_camp')
    _act_sel  = col_p2.selectbox("Actividad", _acts, key='plt_act')
    _esc_sel  = col_p3.selectbox("Escenario", _escs, key='plt_esc')

    df_plt = df_f[
        (df_f['campaña'] == _camp_sel) &
        (df_f['actividad'] == _act_sel) &
        (df_f['escenario'] == _esc_sel)
    ].sort_values(['seccion', 'orden'])

    if df_plt.empty:
        st.warning("Sin datos para esta combinación.")
        st.stop()

    # ── Tabla estilo Márgenes: ppto vs real vs diferencia ───────────────────
    st.subheader(f"{_act_sel} — {_camp_sel} — {_esc_sel}")

    for seccion, df_sec in df_plt.groupby('seccion', sort=False):
        st.markdown(f"**{seccion.upper()}**")

        rows = []
        for _, r in df_sec.iterrows():
            dif = r.get('diferencia', r.get('valor_real', 0) - r.get('valor_ppto', 0))
            rows.append({
                'Ítem':          r['item'],
                'Unidad':        r.get('unidad', ''),
                'Ppto (US$/ha)': r.get('valor_ppto', ''),
                'Real (US$/ha)': r.get('valor_real', ''),
                'Diferencia':    dif,
                'Nota':          r.get('nota', ''),
            })
        df_tabla = pd.DataFrame(rows)

        def _color_diff(val):
            try:
                v = float(val)
                if v > 0:   return 'color: #C62828'  # costo mayor al ppto → rojo
                if v < 0:   return 'color: #2E7D32'  # costo menor al ppto → verde
            except:
                pass
            return ''

        st.dataframe(
            df_tabla.style.applymap(_color_diff, subset=['Diferencia'])
                          .format({'Ppto (US$/ha)': '{:.1f}', 'Real (US$/ha)': '{:.1f}', 'Diferencia': '{:+.1f}'}, na_rep='—'),
            use_container_width=True,
            hide_index=True,
        )

    # ── KPIs resumen ────────────────────────────────────────────────────────
    st.divider()
    _total_ppto = df_plt['valor_ppto'].sum()
    _total_real = df_plt['valor_real'].sum()
    _total_dif  = _total_real - _total_ppto
    k1, k2, k3 = st.columns(3)
    k1.metric("Total presupuesto (US$/ha)", f"{_total_ppto:,.0f}")
    k2.metric("Total ejecutado (US$/ha)",   f"{_total_real:,.0f}")
    k3.metric("Desvío",                     f"{_total_dif:+,.0f}",
              delta_color="inverse" if _total_dif > 0 else "normal")

    # ── Gráfico de desvío por sección ───────────────────────────────────────
    df_dev = df_plt.groupby('seccion')[['valor_ppto','valor_real']].sum().reset_index()
    df_dev['desvio'] = df_dev['valor_real'] - df_dev['valor_ppto']
    df_dev['color']  = df_dev['desvio'].apply(lambda x: '#C62828' if x > 0 else '#2E7D32')

    fig_dev = go.Figure(go.Bar(
        x=df_dev['seccion'], y=df_dev['desvio'],
        marker_color=df_dev['color'],
        text=df_dev['desvio'].apply(lambda x: f'{x:+.0f}'),
        textposition='outside',
    ))
    fig_dev.update_layout(
        title='Desvío por sección (real − ppto, US$/ha)',
        yaxis_title='US$/ha', xaxis_title='',
        height=320, showlegend=False,
    )
    st.plotly_chart(fig_dev, use_container_width=True)

# ════════════════════════════════════════════════════════════════════════════
# TAB ANALÍTICOS
# ════════════════════════════════════════════════════════════════════════════
with tab_analiticos:
    if df_pln.empty:
        st.info("Sin datos de planteos todavía.")
        st.stop()

    # Filtros analíticos
    col_a1, col_a2, col_a3 = st.columns(3)
    _camps_a = sorted(df_pln['campaña'].dropna().unique(), reverse=True)
    _acts_a  = sorted(df_pln['actividad'].dropna().unique())
    sel_camp_a = col_a1.multiselect("Campaña(s)", _camps_a, default=_camps_a[:3] if len(_camps_a) >= 3 else _camps_a)
    sel_act_a  = col_a2.multiselect("Actividad(es)", _acts_a, default=_acts_a)
    metrica_a  = col_a3.radio("Métrica", ["Presupuesto", "Ejecutado", "Desvío"], horizontal=True)

    df_an = df_pln.copy()
    if sel_camp_a: df_an = df_an[df_an['campaña'].isin(sel_camp_a)]
    if sel_act_a:  df_an = df_an[df_an['actividad'].isin(sel_act_a)]

    _col_val = {'Presupuesto': 'valor_ppto', 'Ejecutado': 'valor_real', 'Desvío': None}[metrica_a]

    if metrica_a == 'Desvío':
        df_an['_val'] = df_an['valor_real'] - df_an['valor_ppto']
    else:
        df_an['_val'] = df_an[_col_val]

    # Margen bruto por ambiente y campaña
    df_mb = df_an.groupby(['ambiente_id', 'campaña', 'actividad'])['_val'].sum().reset_index()
    df_mb = df_mb.merge(df_amb[['ambiente_id','ambiente_nombre','lote_nombre','campo']], on='ambiente_id', how='left')

    if df_mb.empty:
        st.warning("Sin datos para la selección.")
        st.stop()

    fig_mb = px.bar(
        df_mb, x='ambiente_nombre', y='_val', color='campaña',
        barmode='group',
        facet_col='campo', facet_col_wrap=2,
        title=f'{metrica_a} total por ambiente y campaña (US$/ha)',
        labels={'_val': 'US$/ha', 'ambiente_nombre': 'Ambiente'},
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig_mb.update_layout(height=480)
    st.plotly_chart(fig_mb, use_container_width=True)

    # Costos por sección/categoría
    df_sec = df_an.groupby(['seccion', 'campaña'])['_val'].sum().reset_index()
    fig_sec = px.bar(
        df_sec, x='seccion', y='_val', color='campaña',
        barmode='group',
        title=f'{metrica_a} por sección',
        labels={'_val': 'US$/ha', 'seccion': 'Sección'},
    )
    fig_sec.update_layout(height=380, xaxis_tickangle=-30)
    st.plotly_chart(fig_sec, use_container_width=True)

    # Evolución por campaña
    df_evol = df_an.groupby(['campaña', 'actividad'])['_val'].sum().reset_index()
    fig_evol = px.line(
        df_evol, x='campaña', y='_val', color='actividad',
        markers=True,
        title=f'Evolución {metrica_a} por actividad',
        labels={'_val': 'US$/ha', 'campaña': 'Campaña'},
    )
    fig_evol.update_layout(height=350)
    st.plotly_chart(fig_evol, use_container_width=True)
