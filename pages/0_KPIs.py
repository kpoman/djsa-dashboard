import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(page_title="KPIs — DJSA", page_icon="🎯", layout="wide")

BASE_DATA = os.path.join(os.path.dirname(__file__), '..', 'data')

URL_PARTE_DIARIO = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vQKK0HtdtrMX7fT9X0ZdOhZ8LZwFKkPKi_NaGbZgSk1SeFq0kz5H2tK48ne-wN4_YUF7Vg3ViX70aMe"
    "/pub?output=xlsx"
)
URL_ALIMENTACION = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vSfp0TxyH1dX_7GWU-waeQRqk9cs1ynSsPYq49g4tyIjXTRuQHODOOiLl69b2Zwlx-lB_bGor9Qotp1"
    "/pub?output=xlsx"
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Tarjetas: fondos con suficiente opacidad para ser legibles en dark/light */
.kpi-card { padding:14px 16px; border-radius:8px; margin-bottom:10px; }
.kpi-verde    { background:rgba(40,167,69,0.18);  border-left:5px solid #28a745; }
.kpi-amarillo { background:rgba(255,193,7,0.18);  border-left:5px solid #ffc107; }
.kpi-rojo     { background:rgba(220,53,69,0.18);  border-left:5px solid #dc3545; }
.kpi-gris     { background:rgba(128,128,128,0.12); border-left:5px solid #888; }

/* Texto dentro de las tarjetas: hereda el color del tema (blanco en dark, negro en light) */
.kpi-label { font-size:0.70em; color:inherit; opacity:0.65; margin:0 0 3px;
             font-weight:700; text-transform:uppercase; letter-spacing:.5px; }
.kpi-value { font-size:1.65em; font-weight:800; margin:0 0 3px; color:inherit; }
.kpi-ref   { font-size:0.68em; color:inherit; opacity:0.50; margin:0; }

/* Títulos de grupo: hereda el color del tema, separador semi-transparente */
.kpi-group-title { margin:28px 0 10px; font-size:1.0em; font-weight:700;
                   color:inherit; border-bottom:2px solid rgba(128,128,128,0.3);
                   padding-bottom:5px; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _card(label, value, color, ref=""):
    st.markdown(
        f'<div class="kpi-card kpi-{color}">'
        f'<p class="kpi-label">{label}</p>'
        f'<p class="kpi-value">{value}</p>'
        f'<p class="kpi-ref">{ref}</p>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _color(val, good, warn, invert=False):
    """Devuelve 'verde'/'amarillo'/'rojo'/'gris'.
    invert=False → más alto mejor (ej. LTVO, TC)
    invert=True  → más bajo mejor (ej. días vacíos, UFC)
    """
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return 'gris'
    if not invert:
        if val >= good:  return 'verde'
        if val >= warn:  return 'amarillo'
        return 'rojo'
    else:
        if val <= good:  return 'verde'
        if val <= warn:  return 'amarillo'
        return 'rojo'


def _fmt(val, dec=1, suffix="", fallback="s/d"):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return fallback
    return f"{val:.{dec}f}{suffix}"


# ── Loaders ───────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _load_dairycomp():
    df_ev = pd.read_csv(
        os.path.join(BASE_DATA, 'eventos-202604.csv'),
        encoding='iso-8859-1', delimiter=';',
        parse_dates=['Fecha'], date_format='%d/%m/%y', dayfirst=True,
    )
    df_ev['Evento'] = df_ev['Evento'].str.strip()
    df_ctrl = pd.read_csv(
        os.path.join(BASE_DATA, 'control-202604.csv'),
        encoding='iso-8859-1', delimiter=';',
        parse_dates=['FechaCtr', 'FPART', 'FSECA'], date_format='%d/%m/%y', dayfirst=True,
    )
    df_ctrl = df_ctrl[df_ctrl['VALR'] > 0]
    return df_ev, df_ctrl


@st.cache_data(show_spinner=False)
def _load_calidad():
    df = pd.read_csv(os.path.join(BASE_DATA, 'calidad_leche.csv'))
    df['fecha'] = pd.to_datetime(df['fecha'], dayfirst=True, errors='coerce')
    for col in ['grasa_butirosa', 'proteina', 'solid_no_grasos', 'celulas_somaticas', 'recuento_ufc']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df[df['grasa_butirosa'].between(1, 7) | df['grasa_butirosa'].isna()]
    df = df[df['proteina'].between(2.5, 5.0) | df['proteina'].isna()]
    return df.dropna(subset=['fecha'])


@st.cache_data(ttl=3600, show_spinner=False)
def _load_ltvo_partediario():
    """Devuelve df con columnas [date, diaria_ltvo] del parte diario."""
    df_all = pd.read_excel(
        URL_PARTE_DIARIO, header=None,
        usecols=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        names=['cat', 'tarde_vo', 'tarde_tanque', 'tarde_prod',
               'maniana_vo', 'maniana_tanque', 'maniana_prod',
               'diaria_total', 'diaria_ltvo', 'entregado'],
        sheet_name=None,
    )
    keys = list(df_all.keys())
    tabs = []
    for i in range(len(keys)):
        tab_name = keys[len(keys) - i - 1]
        if len(tab_name.split('-')) == 2:
            tabs.append(df_all[tab_name])
    if not tabs:
        return None
    df = pd.concat(tabs)
    dates = df[df['cat'] == 'La Merced']['diaria_total'].to_list()
    df_total = df[df['cat'] == 'Total'].assign(date=dates).reset_index()
    df_total = df_total[df_total['diaria_ltvo'] > 0]
    df_total['date'] = pd.to_datetime(df_total['date'], errors='coerce')
    return df_total[['date', 'diaria_ltvo']].dropna()


@st.cache_data(ttl=3600, show_spinner=False)
def _load_alimentacion():
    try:
        df_raw = pd.read_excel(URL_ALIMENTACION, sheet_name=None)
        df_dietas = df_raw.get('Dietas', pd.DataFrame())
        df_prod = df_raw.get('Produccion', pd.DataFrame())
        if df_dietas.empty or df_prod.empty:
            return None
        # Parsear tipo de cambio
        path_tc = os.path.join(BASE_DATA, 'usdars.csv')
        df_tc = pd.read_csv(path_tc, encoding='utf-8-sig')
        df_tc['Fecha'] = pd.to_datetime(df_tc['Fecha'].str.strip().str.strip('"'), format='%d.%m.%Y')
        df_tc['TC'] = (df_tc['Último'].astype(str).str.strip().str.strip('"')
                       .str.replace('.', '', regex=False).str.replace(',', '.', regex=False).astype(float))
        df_tc = df_tc[['Fecha', 'TC']].sort_values('Fecha').set_index('Fecha')
        tc_daily = df_tc.resample('D').last().ffill()

        # Dietas: filtrar numéricas
        df_d = df_dietas.copy()
        date_col = df_d.columns[0]
        df_d = df_d.rename(columns={date_col: 'Fecha'})
        df_d['Fecha'] = pd.to_datetime(df_d['Fecha'], errors='coerce')
        df_d = df_d.dropna(subset=['Fecha'])

        # Producción: filtrar numéricas
        df_p = df_prod.copy()
        date_col_p = df_p.columns[0]
        df_p = df_p.rename(columns={date_col_p: 'Fecha'})
        df_p['Fecha'] = pd.to_datetime(df_p['Fecha'], errors='coerce')
        df_p = df_p.dropna(subset=['Fecha'])

        return {'dietas': df_d, 'prod': df_p, 'tc': tc_daily}
    except Exception:
        return None


# ── Cálculo KPIs ─────────────────────────────────────────────────────────────
def _calc():
    k = {}
    try:
        df_ev, df_ctrl = _load_dairycomp()

        # Referencias temporales basadas en max de cada archivo
        max_ctrl = df_ctrl['FechaCtr'].max()
        max_ev   = df_ev['Fecha'].max()
        ref_ctrl_30d  = max_ctrl - pd.Timedelta(days=30)
        ref_ev_12m    = max_ev - pd.DateOffset(months=12)

        k['ref_ctrl'] = max_ctrl.strftime('%d/%m/%Y')
        k['ref_ev']   = max_ev.strftime('%d/%m/%Y')

        # ── PRODUCCIÓN ────────────────────────────────────────────────────
        # L305E desde controles DairyComp (proyección individual por vaca)
        ctrl_12m  = df_ctrl[df_ctrl['FechaCtr'] >= ref_ev_12m]
        k['l305e'] = float(ctrl_12m['305E'].mean())

        # LTVO desde parte diario (producción real del rodeo)
        try:
            df_pd = _load_ltvo_partediario()
            if df_pd is not None and not df_pd.empty:
                max_pd = df_pd['date'].max()
                ref_pd_30d = max_pd - pd.Timedelta(days=30)
                df_pd_30d = df_pd[df_pd['date'] >= ref_pd_30d]
                k['ltvo'] = float(df_pd_30d['diaria_ltvo'].mean())
                k['ref_ctrl'] = max_pd.strftime('%d/%m/%Y')
            else:
                # Fallback: promedio LECH de controles recientes
                ctrl_30d = df_ctrl[df_ctrl['FechaCtr'] >= ref_ctrl_30d]
                k['ltvo'] = float(ctrl_30d['LECH'].mean())
        except Exception:
            ctrl_30d = df_ctrl[df_ctrl['FechaCtr'] >= ref_ctrl_30d]
            k['ltvo'] = float(ctrl_30d['LECH'].mean())

        # ── REPRODUCCIÓN ─────────────────────────────────────────────────
        df_12m = df_ev[df_ev['Fecha'] >= ref_ev_12m].copy()
        n_vacas    = df_12m['ID'].nunique()
        k['n_vacas'] = n_vacas

        n_partos   = (df_12m['Evento'] == 'PARTO').sum()
        n_abortos  = (df_12m['Evento'] == 'ABORTO').sum()
        n_muertas  = (df_12m['Evento'] == 'MUERTA').sum()
        n_vendidas = (df_12m['Evento'] == 'VENDIDA').sum()

        k['n_partos']  = int(n_partos)

        # ── Tablas base de eventos ────────────────────────────────────────
        df_p  = df_ev[df_ev['Evento'] == 'PARTO'  ][['ID','Fecha']].rename(columns={'Fecha':'FP'})
        df_i  = df_ev[df_ev['Evento'] == 'INSEMIN'][['ID','Fecha']].rename(columns={'Fecha':'FI'})
        df_pr = df_ev[df_ev['Evento'] == 'PREÑADA'][['ID','Fecha']].rename(columns={'Fecha':'FPrena'})

        # Partos dentro de ventana 12m
        df_p12 = df_p[df_p['FP'] >= ref_ev_12m]

        # ── TC corregido ──────────────────────────────────────────────────
        # Solo inseminaciones con suficiente tiempo para diagnóstico (~60d).
        # Para cada inseminación elegible, verifica si hay PREÑADA dentro de 90d.
        cutoff_diag = max_ev - pd.Timedelta(days=60)
        df_i_elig = df_i[(df_i['FI'] >= ref_ev_12m) & (df_i['FI'] < cutoff_diag)]
        k['n_insemin'] = int((df_12m['Evento'] == 'INSEMIN').sum())
        if not df_i_elig.empty:
            m_tc = pd.merge(df_i_elig, df_pr, on='ID')
            m_tc = m_tc[(m_tc['FPrena'] > m_tc['FI']) &
                        (m_tc['FPrena'] <= m_tc['FI'] + pd.Timedelta(days=90))]
            concebidas = m_tc.drop_duplicates(['ID','FI']).shape[0]
            k['tc'] = concebidas / len(df_i_elig) * 100

        # ── NS/P corregido ────────────────────────────────────────────────
        # Por vaca: cantidad de inseminaciones entre su parto y su primera preñez.
        # Solo partos con tiempo suficiente para tener diagnóstico.
        df_p12_elig = df_p12[df_p12['FP'] < cutoff_diag]
        if not df_p12_elig.empty and not df_pr.empty:
            m_pr = pd.merge(df_p12_elig, df_pr, on='ID')
            m_pr = m_pr[(m_pr['FPrena'] > m_pr['FP']) &
                        (m_pr['FPrena'] <= m_pr['FP'] + pd.Timedelta(days=400))]
            if not m_pr.empty:
                primera = m_pr.sort_values('FPrena').groupby(['ID','FP']).first().reset_index()
                nsp_list = []
                for _, r in primera.iterrows():
                    n = df_i[(df_i['ID'] == r['ID']) &
                             (df_i['FI'] > r['FP']) &
                             (df_i['FI'] <= r['FPrena'])].shape[0]
                    nsp_list.append(max(n, 1))  # mínimo 1 (la que confirmó)
                k['nsp'] = float(pd.Series(nsp_list).mean())

        # ── TA: % vacas con aborto confirmado post-preñez ────────────────
        # Vacas únicas con ABORTO / vacas únicas con PREÑADA en 12m.
        # Evita mezclar ciclos distintos usando conteo por vaca.
        n_prenadas_unicas = df_12m[df_12m['Evento'] == 'PREÑADA']['ID'].nunique()
        n_abortos_unicas  = df_12m[df_12m['Evento'] == 'ABORTO' ]['ID'].nunique()
        if n_prenadas_unicas + n_abortos_unicas > 0:
            k['ta'] = n_abortos_unicas / (n_prenadas_unicas + n_abortos_unicas) * 100

        if n_vacas > 0:
            k['tm'] = n_muertas  / n_vacas * 100
            k['td'] = n_vendidas / n_vacas * 100

        # ── D1S: días parto → primer servicio ────────────────────────────
        if not df_p12.empty and not df_i.empty:
            m_d1s = pd.merge(df_p12, df_i, on='ID')
            m_d1s = m_d1s[(m_d1s['FI'] > m_d1s['FP']) &
                          (m_d1s['FI'] <= m_d1s['FP'] + pd.Timedelta(days=250))]
            if not m_d1s.empty:
                fi = m_d1s.sort_values('FI').groupby(['ID','FP']).first().reset_index()
                fi['d'] = (fi['FI'] - fi['FP']).dt.days
                k['d1s'] = float(fi['d'].mean())

        # ── DV: días vacíos parto → concepción estimada ──────────────────
        # DairyComp registra la fecha de *diagnóstico* en PREÑADA, no la de
        # concepción. Restamos 42d (tacto estándar a 42d post-servicio) para
        # estimar la fecha real de concepción.
        if not df_p12.empty and not df_pr.empty:
            m_dv = pd.merge(df_p12, df_pr, on='ID')
            m_dv = m_dv[(m_dv['FPrena'] > m_dv['FP']) &
                        (m_dv['FPrena'] <= m_dv['FP'] + pd.Timedelta(days=400))]
            if not m_dv.empty:
                fp2 = m_dv.sort_values('FPrena').groupby(['ID','FP']).first().reset_index()
                fp2['d'] = (fp2['FPrena'] - fp2['FP']).dt.days - 42  # corrección diagnóstico
                k['dv'] = float(fp2['d'].mean())

        # ── TDC: tasa detección de celo con collares ─────────────────────
        # % de vacas con parto en 12m que tuvieron ≥1 CELO detectado.
        n_parto_unicas = df_p12['ID'].nunique()
        n_celo_unicas  = df_12m[df_12m['Evento'] == 'CELO']['ID'].nunique()
        if n_parto_unicas > 0:
            k['tdc'] = n_celo_unicas / n_parto_unicas * 100

        # Mastitis: % vacas únicas con MAST en 12m
        n_mast_vacas = df_12m[df_12m['Evento'] == 'MAST']['ID'].nunique()
        if n_vacas > 0:
            k['mast'] = n_mast_vacas / n_vacas * 100

    except Exception as e:
        k['err_dairy'] = str(e)

    # ── CALIDAD ───────────────────────────────────────────────────────────
    try:
        df_cal = _load_calidad()
        max_cal = df_cal['fecha'].max()
        ref_cal_30d = max_cal - pd.Timedelta(days=30)
        k['ref_cal'] = max_cal.strftime('%d/%m/%Y')
        df30 = df_cal[df_cal['fecha'] >= ref_cal_30d]
        k['grasa']   = float(df30['grasa_butirosa'].mean())
        k['proteina'] = float(df30['proteina'].mean())
        # Sin dato de CS = resultado 0 (igual que UFC)
        cs_filled = pd.to_numeric(df30['celulas_somaticas'], errors='coerce').fillna(0)
        k['cs'] = float(cs_filled.mean())
        cs_diario = (df30.groupby('fecha')['celulas_somaticas']
                     .apply(lambda x: pd.to_numeric(x, errors='coerce').fillna(0).mean()))
        k['cs_dias_alerta'] = int((cs_diario > 400_000).sum())
        k['cs_dias_medidos'] = int(len(cs_diario))
        # Sin dato de UFC = resultado 0 (no se registra cuando da negativo)
        ufc_filled = pd.to_numeric(df30['recuento_ufc'], errors='coerce').fillna(0)
        k['ufc'] = float(ufc_filled.mean())
        # Días únicos: promedio diario (NaN→0), contar días >50k
        ufc_diario = (df30.groupby('fecha')['recuento_ufc']
                      .apply(lambda x: pd.to_numeric(x, errors='coerce').fillna(0).mean()))
        k['ufc_dias_alerta'] = int((ufc_diario > 50_000).sum())
        k['ufc_dias_medidos'] = int(len(ufc_diario))
    except Exception as e:
        k['err_cal'] = str(e)

    # ── ALIMENTACIÓN (litros libres, costo/litro) ─────────────────────────
    try:
        alim = _load_alimentacion()
        if alim is not None:
            # Calcular métricas recientes desde la planilla
            # Usar lógica simplificada: buscar columnas clave
            df_d = alim['dietas']
            df_p_alim = alim['prod']
            tc_ser = alim['tc']['TC']
            # Intentar calcular litros libres y costo/litro de última fecha disponible
            k['alim_ok'] = True
    except Exception:
        pass

    return k


# ── Mini-chart helpers ────────────────────────────────────────────────────────
def _mini_layout(fig, title="", h=220):
    fig.update_layout(
        height=h, margin=dict(t=28, b=28, l=36, r=16),
        title=dict(text=title, font=dict(size=12)),
        showlegend=False, hovermode='x unified',
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor='rgba(128,128,128,0.15)')
    return fig


@st.cache_data(ttl=3600, show_spinner=False)
def _make_mini_charts():
    """Genera todos los gráficos mini para los popovers. Cachéado."""
    charts = {}
    AZUL   = '#5b8ff9'
    VERDE  = '#5ad8a6'
    NARANJA= '#f4a522'
    ROJO   = '#dc3545'

    # ── datos base ──
    try:
        df_ev, df_ctrl = _load_dairycomp()
        max_ev  = df_ev['Fecha'].max()
        ref_12m = max_ev - pd.DateOffset(months=12)
        df_12m  = df_ev[df_ev['Fecha'] >= ref_12m].copy()
    except Exception:
        df_ev = df_ctrl = df_12m = None

    try:
        df_cal = _load_calidad()
        max_cal  = df_cal['fecha'].max()
        ref_90d  = max_cal - pd.Timedelta(days=90)
        df_cal90 = df_cal[df_cal['fecha'] >= ref_90d].copy()
        df_cal90['recuento_ufc'] = pd.to_numeric(df_cal90['recuento_ufc'], errors='coerce').fillna(0)
        # Promedios diarios
        cal_dia = (df_cal90.groupby('fecha')
                   .agg(grasa=('grasa_butirosa','mean'),
                        proteina=('proteina','mean'),
                        cs=('celulas_somaticas','mean'),
                        ufc=('recuento_ufc','mean'))
                   .reset_index())
    except Exception:
        df_cal = cal_dia = None

    try:
        df_pd = _load_ltvo_partediario()
        if df_pd is not None:
            max_pd  = df_pd['date'].max()
            ref_90d_pd = max_pd - pd.Timedelta(days=90)
            pd90 = df_pd[df_pd['date'] >= ref_90d_pd].copy()
        else:
            pd90 = None
    except Exception:
        pd90 = None

    # ══ PRODUCCIÓN ═══════════════════════════════════════════════════════
    # LTVO — línea 90d
    if pd90 is not None and not pd90.empty:
        fig = go.Figure(go.Scatter(
            x=pd90['date'], y=pd90['diaria_ltvo'],
            mode='lines', line=dict(color=AZUL, width=1.5),
            hovertemplate='%{x|%d/%m}<br>%{y:.1f} L<extra></extra>',
        ))
        fig.add_hline(y=30, line_dash='dot', line_color=VERDE, line_width=1,
                      annotation_text='meta 30L', annotation_font_size=9)
        charts['ltvo'] = _mini_layout(fig, 'LTVO (L/vc/día) — últimos 90d')

    # L305E — histograma distribución vacas
    if df_ctrl is not None:
        ref_12m_ctrl = df_ctrl['FechaCtr'].max() - pd.DateOffset(months=12)
        l305 = df_ctrl[df_ctrl['FechaCtr'] >= ref_12m_ctrl]['305E'].dropna()
        if not l305.empty:
            fig = go.Figure(go.Histogram(
                x=l305, nbinsx=25,
                marker_color=AZUL, opacity=0.8,
                hovertemplate='%{x:.0f} L: %{y} vacas<extra></extra>',
            ))
            fig.add_vline(x=l305.mean(), line_dash='dash', line_color=NARANJA,
                          annotation_text=f'media {l305.mean():.0f}L',
                          annotation_font_size=9)
            charts['l305e'] = _mini_layout(fig, 'Distribución L305E — últimos 12m')

    # ══ CALIDAD ══════════════════════════════════════════════════════════
    if cal_dia is not None and not cal_dia.empty:
        # Grasa — línea 90d
        fig = go.Figure(go.Scatter(
            x=cal_dia['fecha'], y=cal_dia['grasa'],
            mode='lines', line=dict(color=NARANJA, width=1.5),
            hovertemplate='%{x|%d/%m}<br>%{y:.2f}%<extra></extra>',
        ))
        fig.add_hline(y=3.2, line_dash='dot', line_color=VERDE, line_width=1,
                      annotation_text='meta 3.2%', annotation_font_size=9)
        charts['grasa'] = _mini_layout(fig, 'Grasa butirosa (%) — últimos 90d')

        # Proteína — línea 90d
        fig = go.Figure(go.Scatter(
            x=cal_dia['fecha'], y=cal_dia['proteina'],
            mode='lines', line=dict(color=AZUL, width=1.5),
            hovertemplate='%{x|%d/%m}<br>%{y:.2f}%<extra></extra>',
        ))
        fig.add_hline(y=3.3, line_dash='dot', line_color=VERDE, line_width=1,
                      annotation_text='meta 3.3%', annotation_font_size=9)
        charts['proteina'] = _mini_layout(fig, 'Proteína (%) — últimos 90d')

        # CS — línea 90d
        cs_dia = cal_dia.dropna(subset=['cs'])
        if not cs_dia.empty:
            fig = go.Figure(go.Scatter(
                x=cs_dia['fecha'], y=cs_dia['cs'] / 1000,
                mode='lines+markers', marker=dict(size=4),
                line=dict(color=ROJO, width=1.5),
                hovertemplate='%{x|%d/%m}<br>%{y:.0f}k cél/mL<extra></extra>',
            ))
            fig.add_hline(y=250, line_dash='dot', line_color=VERDE, line_width=1,
                          annotation_text='250k', annotation_font_size=9)
            charts['cs'] = _mini_layout(fig, 'Células somáticas (miles/mL) — 90d')

        # UFC — barras 90d (días con UFC>0)
        ufc_dia = cal_dia[cal_dia['ufc'] > 0].copy()
        if not ufc_dia.empty:
            colores_ufc = ['#dc3545' if v > 50000 else '#ffc107' if v > 20000 else '#28a745'
                           for v in ufc_dia['ufc']]
            fig = go.Figure(go.Bar(
                x=ufc_dia['fecha'], y=ufc_dia['ufc'] / 1000,
                marker_color=colores_ufc,
                hovertemplate='%{x|%d/%m}<br>%{y:.0f}k UFC/mL<extra></extra>',
            ))
            fig.add_hline(y=20, line_dash='dot', line_color=VERDE, line_width=1,
                          annotation_text='20k', annotation_font_size=9)
            fig.add_hline(y=50, line_dash='dot', line_color=ROJO, line_width=1,
                          annotation_text='50k', annotation_font_size=9)
            charts['ufc'] = _mini_layout(fig, 'UFC/mL (miles) — días con conteo >0, 90d')

    # ══ REPRODUCCIÓN ═════════════════════════════════════════════════════
    if df_12m is not None:
        df_12m['mes'] = df_12m['Fecha'].dt.to_period('M')
        meses = sorted(df_12m['mes'].unique())
        fechas_mes = [m.to_timestamp() for m in meses]
        cutoff_diag = max_ev - pd.Timedelta(days=60)

        # TDC — barras mensuales (% vacas con celo detectado)
        tdc_mes = []
        for m in meses:
            dfm = df_12m[df_12m['mes'] == m]
            n_p = dfm[dfm['Evento']=='PARTO']['ID'].nunique()
            n_c = dfm[dfm['Evento']=='CELO']['ID'].nunique()
            tdc_mes.append(n_c / n_p * 100 if n_p > 0 else np.nan)
        fig = go.Figure(go.Bar(
            x=fechas_mes, y=tdc_mes, marker_color=VERDE,
            hovertemplate='%{x|%b %Y}<br>%{y:.1f}%<extra></extra>',
        ))
        fig.add_hline(y=90, line_dash='dot', line_color=VERDE, line_width=1,
                      annotation_text='meta 90%', annotation_font_size=9)
        charts['tdc'] = _mini_layout(fig, 'TDC mensual (%)')

        # TC — barras mensuales
        tc_mes = []
        for m in meses:
            df_i_m = df_ev[(df_ev['Evento']=='INSEMIN') &
                           (df_ev['Fecha'].dt.to_period('M')==m) &
                           (df_ev['Fecha'] < cutoff_diag)]
            df_p_all = df_ev[df_ev['Evento']=='PREÑADA'][['ID','Fecha']].rename(columns={'Fecha':'FP'})
            if len(df_i_m) == 0:
                tc_mes.append(np.nan); continue
            m_tc = pd.merge(df_i_m[['ID','Fecha']].rename(columns={'Fecha':'FI'}), df_p_all, on='ID')
            m_tc = m_tc[(m_tc['FP']>m_tc['FI']) & (m_tc['FP']<=m_tc['FI']+pd.Timedelta(days=90))]
            tc_mes.append(m_tc.drop_duplicates(['ID','FI']).shape[0] / len(df_i_m) * 100)
        colors_tc = ['#28a745' if v and v>=51 else '#ffc107' if v and v>=43 else '#dc3545'
                     for v in tc_mes]
        fig = go.Figure(go.Bar(
            x=fechas_mes, y=tc_mes, marker_color=colors_tc,
            hovertemplate='%{x|%b %Y}<br>%{y:.1f}%<extra></extra>',
        ))
        fig.add_hline(y=51, line_dash='dot', line_color=VERDE, line_width=1,
                      annotation_text='51%', annotation_font_size=9)
        charts['tc'] = _mini_layout(fig, 'Tasa de concepción mensual (%)')

        # NS/P — distribución de servicios por preñez
        df_p_ev = df_ev[(df_ev['Evento']=='PARTO') &
                        (df_ev['Fecha']>=ref_12m) &
                        (df_ev['Fecha']<cutoff_diag)][['ID','Fecha']].rename(columns={'Fecha':'FP'})
        df_pr_ev = df_ev[df_ev['Evento']=='PREÑADA'][['ID','Fecha']].rename(columns={'Fecha':'FPrena'})
        df_i_ev  = df_ev[df_ev['Evento']=='INSEMIN'][['ID','Fecha']].rename(columns={'Fecha':'FI'})
        if not df_p_ev.empty and not df_pr_ev.empty:
            mp = pd.merge(df_p_ev, df_pr_ev, on='ID')
            mp = mp[(mp['FPrena']>mp['FP']) & (mp['FPrena']<=mp['FP']+pd.Timedelta(days=400))]
            if not mp.empty:
                primera = mp.sort_values('FPrena').groupby(['ID','FP']).first().reset_index()
                nsp_list = []
                for _, r in primera.iterrows():
                    n = df_i_ev[(df_i_ev['ID']==r['ID']) &
                                (df_i_ev['FI']>r['FP']) &
                                (df_i_ev['FI']<=r['FPrena'])].shape[0]
                    nsp_list.append(max(n, 1))
                s = pd.Series(nsp_list).value_counts().sort_index()
                s.index = [f'{i}' if i < 5 else '5+' for i in s.index]
                fig = go.Figure(go.Bar(
                    x=s.index, y=s.values, marker_color=AZUL,
                    hovertemplate='%{x} serv.: %{y} vacas<extra></extra>',
                ))
                charts['nsp'] = _mini_layout(fig, 'Distribución servicios por preñez (# vacas)')

        # D1S — histograma días parto→1er servicio
        df_p12 = df_ev[(df_ev['Evento']=='PARTO') & (df_ev['Fecha']>=ref_12m)][['ID','Fecha']].rename(columns={'Fecha':'FP'})
        if not df_p12.empty and not df_i_ev.empty:
            md = pd.merge(df_p12, df_i_ev, on='ID')
            md = md[(md['FI']>md['FP']) & (md['FI']<=md['FP']+pd.Timedelta(days=250))]
            if not md.empty:
                fi = md.sort_values('FI').groupby(['ID','FP']).first().reset_index()
                fi['d'] = (fi['FI'] - fi['FP']).dt.days
                fig = go.Figure(go.Histogram(
                    x=fi['d'], nbinsx=20, marker_color=AZUL, opacity=0.8,
                    hovertemplate='%{x}d: %{y} vacas<extra></extra>',
                ))
                fig.add_vline(x=60, line_dash='dot', line_color=VERDE, line_width=1,
                              annotation_text='meta 60d', annotation_font_size=9)
                charts['d1s'] = _mini_layout(fig, 'Días parto → 1er servicio (distribución)')

        # DV — histograma días vacíos estimados
        if not df_p12.empty and not df_pr_ev.empty:
            mdv = pd.merge(df_p12, df_pr_ev, on='ID')
            mdv = mdv[(mdv['FPrena']>mdv['FP']) & (mdv['FPrena']<=mdv['FP']+pd.Timedelta(days=400))]
            if not mdv.empty:
                fp2 = mdv.sort_values('FPrena').groupby(['ID','FP']).first().reset_index()
                fp2['d'] = (fp2['FPrena'] - fp2['FP']).dt.days - 42
                fig = go.Figure(go.Histogram(
                    x=fp2['d'], nbinsx=20, marker_color=VERDE, opacity=0.8,
                    hovertemplate='%{x}d: %{y} vacas<extra></extra>',
                ))
                fig.add_vline(x=110, line_dash='dot', line_color=VERDE, line_width=1,
                              annotation_text='meta 110d', annotation_font_size=9)
                charts['dv'] = _mini_layout(fig, 'Días vacíos estimados (distribución)')

        # TA / TM / TD — barras mensuales
        for evento, clave, titulo in [
            ('ABORTO', 'ta', 'Abortos por mes'),
            ('MUERTA', 'tm', 'Muertes por mes'),
            ('VENDIDA','td', 'Descartes por mes'),
        ]:
            cnts = (df_12m[df_12m['Evento']==evento]
                    .groupby('mes').size().reindex(meses, fill_value=0))
            fig = go.Figure(go.Bar(
                x=fechas_mes, y=cnts.values, marker_color=ROJO,
                hovertemplate='%{x|%b %Y}<br>%{y} eventos<extra></extra>',
            ))
            charts[clave] = _mini_layout(fig, titulo + ' (conteo)')

        # Mastitis — barras mensuales
        mast_cnts = (df_12m[df_12m['Evento']=='MAST']
                     .groupby('mes')['ID'].nunique().reindex(meses, fill_value=0))
        fig = go.Figure(go.Bar(
            x=fechas_mes, y=mast_cnts.values, marker_color=NARANJA,
            hovertemplate='%{x|%b %Y}<br>%{y} vacas<extra></extra>',
        ))
        charts['mast'] = _mini_layout(fig, 'Vacas con mastitis por mes')

    return charts


# ── UI ────────────────────────────────────────────────────────────────────────
st.title("🎯 Dashboard KPIs — Tambo DJSA")

with st.spinner("Calculando indicadores..."):
    k = _calc()
    charts = _make_mini_charts()

if 'err_dairy' in k:
    st.error(f"Error DairyComp: {k['err_dairy']}")

ref_ctrl = k.get('ref_ctrl', '?')
ref_ev   = k.get('ref_ev',   '?')
ref_cal  = k.get('ref_cal',  '?')

st.caption(
    f"Controles hasta **{ref_ctrl}** · Eventos hasta **{ref_ev}** · "
    f"Calidad hasta **{ref_cal}** · Reproducción/Sanidad: últimos 12 meses"
)
st.divider()

# ═══════════════════════════════════════════════════════════════════════
# GRUPO 1 — PRODUCCIÓN
# ═══════════════════════════════════════════════════════════════════════
st.markdown('<p class="kpi-group-title">🥛 Producción</p>', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)

with c1:
    v = k.get('ltvo')
    _card("LTVO promedio (L/vc/día)", _fmt(v, 1), _color(v, 30, 26),
          f"verde ≥30 · amarillo 26-30 · rojo <26 · parte diario, 30d hasta {ref_ctrl}")
    if 'ltvo' in charts:
        with st.popover("📈 ver tendencia", use_container_width=True):
            st.plotly_chart(charts['ltvo'], use_container_width=True)

with c2:
    v = k.get('l305e')
    _card("Proyección L305E promedio", _fmt(v, 0, " L"), _color(v, 10000, 8500),
          "verde ≥10.000 · amarillo 8.500-10.000 · rojo <8.500 · últimos 12m")
    if 'l305e' in charts:
        with st.popover("📈 ver distribución", use_container_width=True):
            st.plotly_chart(charts['l305e'], use_container_width=True)

with c3:
    n = k.get('n_partos')
    _card("Partos (12 meses)", _fmt(n, 0) if n else "s/d", 'gris',
          f"total acumulado · hasta {ref_ev}")

with c4:
    n = k.get('n_insemin')
    _card("Inseminaciones (12 meses)", _fmt(n, 0) if n else "s/d", 'gris',
          f"total acumulado · hasta {ref_ev}")

# ═══════════════════════════════════════════════════════════════════════
# GRUPO 2 — CALIDAD DE LECHE
# ═══════════════════════════════════════════════════════════════════════
st.markdown('<p class="kpi-group-title">🔬 Calidad de leche (últimos 30 días)</p>', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)

with c1:
    v = k.get('grasa')
    _card("Grasa butirosa (%)", _fmt(v, 2), _color(v, 3.2, 3.0),
          f"verde ≥3.2 · amarillo 3.0-3.2 · rojo <3.0 · hasta {ref_cal}")
    if 'grasa' in charts:
        with st.popover("📈 ver tendencia", use_container_width=True):
            st.plotly_chart(charts['grasa'], use_container_width=True)

with c2:
    v = k.get('proteina')
    _card("Proteína (%)", _fmt(v, 2), _color(v, 3.3, 3.1),
          f"verde ≥3.3 · amarillo 3.1-3.3 · rojo <3.1 · hasta {ref_cal}")
    if 'proteina' in charts:
        with st.popover("📈 ver tendencia", use_container_width=True):
            st.plotly_chart(charts['proteina'], use_container_width=True)

with c3:
    v = k.get('cs')
    cs_dias_alerta  = k.get('cs_dias_alerta', 0)
    cs_dias_medidos = k.get('cs_dias_medidos', 0)
    disp = f"{v/1000:.0f}k cél/mL" if v and not np.isnan(v) else "s/d"
    cs_alerta_txt = (f"⚠️ {cs_dias_alerta} día{'s' if cs_dias_alerta != 1 else ''} >400k"
                     if cs_dias_alerta > 0 else "✓ ningún día >400k")
    _card("Células somáticas (SCC)", disp,
          _color(v, 250_000, 400_000, invert=True) if v else 'gris',
          f"verde <250k · amarillo 250-400k · rojo >400k · {cs_alerta_txt} en {cs_dias_medidos} días")
    if 'cs' in charts:
        with st.popover("📈 ver tendencia", use_container_width=True):
            st.plotly_chart(charts['cs'], use_container_width=True)

with c4:
    v = k.get('ufc')
    dias_alerta = k.get('ufc_dias_alerta', 0)
    dias_medidos = k.get('ufc_dias_medidos', 0)
    disp = f"{v/1000:.0f}k UFC/mL" if v and not np.isnan(v) else "s/d"
    alerta_txt = (f"⚠️ {dias_alerta} día{'s' if dias_alerta != 1 else ''} >50k"
                  if dias_alerta > 0 else "✓ ningún día >50k")
    _card("Recuento bacteriano (UFC)", disp,
          _color(v, 20_000, 50_000, invert=True) if v else 'gris',
          f"verde <20k · amarillo 20-50k · rojo >50k · {alerta_txt} en {dias_medidos} días medidos")
    if 'ufc' in charts:
        with st.popover("📈 ver detalle", use_container_width=True):
            st.plotly_chart(charts['ufc'], use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════
# GRUPO 3 — REPRODUCCIÓN
# ═══════════════════════════════════════════════════════════════════════
st.markdown('<p class="kpi-group-title">🐄 Reproducción (últimos 12 meses)</p>', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)

with c1:
    v = k.get('tdc')
    _card("Tasa detección de celo (collar)", _fmt(v, 1, " %"), _color(v, 90, 70),
          "verde ≥90 · amarillo 70-90 · rojo <70")
    if 'tdc' in charts:
        with st.popover("📈 ver mensual", use_container_width=True):
            st.plotly_chart(charts['tdc'], use_container_width=True)

with c2:
    v = k.get('tc')
    _card("Tasa de concepción (%)", _fmt(v, 1, " %"), _color(v, 51, 43),
          "verde ≥51 · amarillo 43-51 · rojo <43 · solo serv. con diagnóstico confirmado")
    if 'tc' in charts:
        with st.popover("📈 ver mensual", use_container_width=True):
            st.plotly_chart(charts['tc'], use_container_width=True)

with c3:
    v = k.get('nsp')
    _card("Servicios por preñez", _fmt(v, 2), _color(v, 1.7, 2.5, invert=True),
          "verde <1.7 · amarillo 1.7-2.5 · rojo >2.5 · promedio por vaca")
    if 'nsp' in charts:
        with st.popover("📈 ver distribución", use_container_width=True):
            st.plotly_chart(charts['nsp'], use_container_width=True)

with c4:
    v = k.get('d1s')
    _card("Días parto → 1er servicio", _fmt(v, 0, " d"), _color(v, 60, 75, invert=True),
          "verde <60 · amarillo 60-75 · rojo >75")
    if 'd1s' in charts:
        with st.popover("📈 ver distribución", use_container_width=True):
            st.plotly_chart(charts['d1s'], use_container_width=True)

c1, c2, c3, c4 = st.columns(4)

with c1:
    v = k.get('dv')
    _card("Días vacíos (estimado a concepción)", _fmt(v, 0, " d"),
          _color(v, 110, 140, invert=True),
          "verde <110 · amarillo 110-140 · rojo >140 · fecha PREÑADA − 42d")
    if 'dv' in charts:
        with st.popover("📈 ver distribución", use_container_width=True):
            st.plotly_chart(charts['dv'], use_container_width=True)

with c2:
    v = k.get('ta')
    _card("Tasa de aborto (%)", _fmt(v, 1, " %"), _color(v, 3, 5, invert=True),
          "verde <3 · amarillo 3-5 · rojo >5 · vacas únicas con ABORTO / (PREÑADA+ABORTO)")
    if 'ta' in charts:
        with st.popover("📈 ver mensual", use_container_width=True):
            st.plotly_chart(charts['ta'], use_container_width=True)

with c3:
    v = k.get('tm')
    _card("Tasa de mortandad (%)", _fmt(v, 1, " %"), _color(v, 3, 5, invert=True),
          "verde <3 · amarillo 3-5 · rojo >5")
    if 'tm' in charts:
        with st.popover("📈 ver mensual", use_container_width=True):
            st.plotly_chart(charts['tm'], use_container_width=True)

with c4:
    v = k.get('td')
    _card("Tasa de descarte (%)", _fmt(v, 1, " %"), _color(v, 20, 30, invert=True),
          "verde <20 · amarillo 20-30 · rojo >30")
    if 'td' in charts:
        with st.popover("📈 ver mensual", use_container_width=True):
            st.plotly_chart(charts['td'], use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════
# GRUPO 4 — SANIDAD
# ═══════════════════════════════════════════════════════════════════════
st.markdown('<p class="kpi-group-title">💊 Sanidad (últimos 12 meses)</p>', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)

with c1:
    v = k.get('mast')
    _card("Incidencia mastitis (% vacas)", _fmt(v, 1, " %"), _color(v, 15, 25, invert=True),
          "verde <15 · amarillo 15-25 · rojo >25")
    if 'mast' in charts:
        with st.popover("📈 ver mensual", use_container_width=True):
            st.plotly_chart(charts['mast'], use_container_width=True)

with c2:
    v = k.get('cs')
    disp = f"{v/1000:.0f}k" if v and not np.isnan(v) else "s/d"
    _card("Células somáticas (SCC prom.)", disp,
          _color(v, 250_000, 400_000, invert=True) if v else 'gris',
          "verde <250k · amarillo 250-400k · rojo >400k")
    if 'cs' in charts:
        with st.popover("📈 ver tendencia", use_container_width=True):
            st.plotly_chart(charts['cs'], use_container_width=True)

with c3:
    st.empty()

with c4:
    st.empty()

# ═══════════════════════════════════════════════════════════════════════
# Nota metodológica
# ═══════════════════════════════════════════════════════════════════════
st.divider()
with st.expander("ℹ️ Metodología y fuentes"):
    st.markdown(f"""
| KPI | Fuente | Período | Metodología |
|---|---|---|---|
| LTVO | Parte diario | 30d hasta {ref_ctrl} | Promedio diaria_ltvo |
| L305E | DairyComp controles | 12m | Promedio campo 305E |
| Grasa / Proteína | calidad_leche.csv | 30d hasta {ref_cal} | Promedio diario (outliers filtrados) |
| CS / UFC | calidad_leche.csv | 30d hasta {ref_cal} | Promedio días con medición |
| TDC (collar) | DairyComp eventos | 12m hasta {ref_ev} | Vacas únicas con CELO / vacas con PARTO en 12m |
| Tasa concepción | DairyComp eventos | 12m | Serv. con PREÑADA en 90d / total serv. elegibles (excl. últimos 60d sin diagnóstico) |
| NS/P | DairyComp eventos | 12m | Promedio por vaca: INSEMIN entre PARTO y primera PREÑADA |
| D1S | DairyComp eventos | 12m | Primer INSEMIN post-PARTO por vaca |
| DV (días vacíos) | DairyComp eventos | 12m | (Fecha PREÑADA − 42d) − Fecha PARTO · resta lag de diagnóstico |
| Tasa aborto | DairyComp eventos | 12m | Vacas únicas con ABORTO / (vacas únicas PREÑADA + ABORTO) |
| Tasa mortandad | DairyComp eventos | 12m | MUERTA / vacas únicas × 100 |
| Tasa descarte | DairyComp eventos | 12m | VENDIDA / vacas únicas × 100 |
| Mastitis | DairyComp eventos | 12m | Vacas únicas con MAST / vacas únicas × 100 |

*Fuente bibliográfica de umbrales: Piccardi, Bruno, Córdoba, Masía, Balzarini (2019) — CONICET / Editorial Brujas.*
    """)
