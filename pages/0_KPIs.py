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
URL_DATOS_CREA = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vTaYOZHAcL06SuvN7VPwASlZ4G5-w6zBn8G4ucjXZCtGvGYgfFBIvBGVUmIyWkfPMN4lTKW9yBOSzSa"
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


@st.cache_data(ttl=3600, show_spinner=False)
def _load_crea():
    """Carga planilla CREA y calcula indicadores derivados."""
    df_raw = pd.read_excel(URL_DATOS_CREA, header=None, sheet_name=None)
    df_dc = df_raw['datos crea'].transpose()
    columns = df_dc.iloc[0][:35].to_list()
    columns[0] = 'Ano'
    columns[1] = 'Mes'
    df = df_dc.drop(range(35, 49), axis=1).set_axis(columns, axis=1)
    df.drop(0, axis=0, inplace=True)
    df['Ano'] = df['Ano'].ffill()
    df['Ano'] = df['Ano'].astype('Int64')
    df.dropna(subset=['Mes'], inplace=True)
    df['Mes'] = pd.to_datetime(df['Mes'], errors='coerce')
    df.dropna(subset=['Mes'], inplace=True)
    df['Mes'] = df['Mes'].apply(lambda x: x.month)
    df = df[df['VT'] > 0]
    if df.shape[1] > 33:
        df.drop(df.columns[33], axis=1, inplace=True)

    num_cols = ['Partos de vaca:', 'Partos de vaq.', 'Partos Totales', 'Partos Muertos',
                'VO', 'VS', 'VT', 'Muertes', 'Bajas Adultas', 'Dias Lactancia',
                'Abortos', 'Hembras nacidas', 'Muertes guachera', 'Muertes Recria']
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')

    df['Ano'] = df['Ano'].astype(int)
    df['Periodo'] = pd.to_datetime({'year': df['Ano'], 'month': df['Mes'], 'day': 1})

    def _spct(n, d):
        if n not in df.columns or d not in df.columns:
            return None
        return (df[n] / df[d].replace(0, np.nan) * 100).round(2)

    for col, nc, dc in [
        ('_pct_VO_VT',      'VO',               'VT'),
        ('_mort_perinatal', 'Partos Muertos',    'Partos Totales'),
        ('_mort_adultas',   'Muertes',           'VT'),
        ('_mort_guachera',  'Muertes guachera',  'Hembras nacidas'),
        ('_pct_hembras',    'Hembras nacidas',   'Partos Totales'),
        ('_tasa_abortos',   'Abortos',           'VT'),
    ]:
        v = _spct(nc, dc)
        if v is not None:
            df[col] = v

    # Tasa de parición ANUAL: suma móvil 12m de partos / VT promedio 12m × 100
    # El benchmark INTA (82.7 %) es anual — la cifra mensual (partos/VT ~6–9 %)
    # no es comparable. Se usa ventana de 12 meses para expresar en la misma unidad.
    df = df.sort_values('Periodo').reset_index(drop=True)
    if 'Partos Totales' in df.columns and 'VT' in df.columns:
        _partos = pd.to_numeric(df['Partos Totales'], errors='coerce')
        _vt     = pd.to_numeric(df['VT'],             errors='coerce')
        df['_tasa_paricion'] = (
            (_partos.rolling(12, min_periods=6).sum() /
             _vt.rolling(12, min_periods=6).mean().replace(0, np.nan) * 100)
            .round(2)
        )

    return df


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

    # ── CREA — indicadores de gestión del rodeo ───────────────────────────
    try:
        df_crea = _load_crea()
        ult_per = df_crea['Periodo'].max()
        row_c = df_crea[df_crea['Periodo'] == ult_per].iloc[0]
        k['ref_crea'] = ult_per.strftime('%b %Y')

        _KPI_MAP = {
            '_pct_VO_VT':      'crea_pct_vo_vt',
            '_tasa_paricion':  'crea_tasa_paricion',
            '_mort_perinatal': 'crea_mort_perinatal',
            '_mort_adultas':   'crea_mort_adultas',
            '_mort_guachera':  'crea_mort_guachera',
            '_tasa_abortos':   'crea_tasa_abortos',
            '_pct_hembras':    'crea_pct_hembras',
            'Dias Lactancia':  'crea_del',
        }
        for df_col, k_key in _KPI_MAP.items():
            if df_col in df_crea.columns:
                val = row_c.get(df_col)
                if val is not None and not pd.isna(val):
                    k[k_key] = float(val)
    except Exception as e:
        k['err_crea'] = str(e)

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

    # ══ CREA — indicadores de gestión del rodeo ═══════════════════════════
    try:
        df_crea = _load_crea()
        ult_crea = df_crea['Periodo'].max()
        df_c24 = df_crea[df_crea['Periodo'] >= ult_crea - pd.DateOffset(months=24)].copy()

        _CREA_CHRT = [
            # (col_df,          chart_key,             título,                    color,   meta_lo, meta_hi)
            ('_pct_VO_VT',      'crea_pct_vo_vt',      '% VO/VT — 24m',          AZUL,    75,  None),
            ('_tasa_paricion',  'crea_tasa_paricion',  'Tasa parición % — 24m',   VERDE,   80,  None),
            ('_mort_perinatal', 'crea_mort_perinatal', 'Mort. perinatal % — 24m', ROJO,    None, 5),
            ('_mort_adultas',   'crea_mort_adultas',   'Mort. adultas % — 24m',   ROJO,    None, 5.7),
            ('_mort_guachera',  'crea_mort_guachera',  'Mort. guachera % — 24m',  NARANJA, None, 10),
            ('_tasa_abortos',   'crea_tasa_abortos',   'Tasa abortos % — 24m',    ROJO,    None, 3),
            ('Dias Lactancia',  'crea_del',            'Días en lactancia — 24m', AZUL,    150,  175),
            ('_pct_hembras',    'crea_pct_hembras',    '% hembras nacidas — 24m', VERDE,   None, None),
        ]

        for df_col, chart_key, titulo, color, meta_lo, meta_hi in _CREA_CHRT:
            if df_col not in df_c24.columns:
                continue
            serie = df_c24[['Periodo', df_col]].dropna(subset=[df_col])
            if serie.empty:
                continue
            fig = go.Figure(go.Bar(
                x=serie['Periodo'], y=serie[df_col],
                marker_color=color,
                hovertemplate='%{x|%b %Y}<br>%{y:.1f}<extra></extra>',
            ))
            if meta_lo is not None:
                fig.add_hline(y=meta_lo, line_dash='dot', line_color=VERDE, line_width=1,
                              annotation_text=f'{meta_lo}', annotation_font_size=9)
            if meta_hi is not None:
                fig.add_hline(y=meta_hi, line_dash='dot', line_color=ROJO, line_width=1,
                              annotation_text=f'{meta_hi}', annotation_font_size=9)
            charts[chart_key] = _mini_layout(fig, titulo)
    except Exception:
        pass

    return charts


# ── Semáforo histórico ────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def _build_semaforo_hist():
    """
    Devuelve (mat_score, mat_vals):
      mat_score — matriz indicadores × Periodo con scores continuos 0.0–1.0
                  (0 = en meta / verde puro · 1 = muy lejos de meta / rojo puro
                   NaN = sin dato)
      mat_vals  — misma forma con el valor numérico real (para hover)

    Normalización: el umbral 'good' mapea a 0.0 y el umbral 'warn' a 0.5.
    El punto 'bad' (2·warn − good) mapea a 1.0; valores peores se clampean a 1.0.
    """

    def _ns_hi(val, good, warn):
        """Mayor es mejor. good→0.0, warn→0.5, 2·warn−good→1.0"""
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return np.nan
        if good <= warn:   # degenerate
            return np.nan
        bad = 2 * warn - good
        return float(np.clip((good - val) / (good - bad), 0.0, 1.0))

    def _ns_lo(val, good, warn):
        """Menor es mejor. good→0.0, warn→0.5, 2·warn−good→1.0"""
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return np.nan
        if warn <= good:   # degenerate
            return np.nan
        bad = 2 * warn - good
        return float(np.clip((val - good) / (bad - good), 0.0, 1.0))

    def _ns_rng(val, lo_g, hi_g, lo_a, hi_a):
        """Rango óptimo [lo_g, hi_g]. Distancia normalizada desde el borde del rango."""
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return np.nan
        if lo_g <= val <= hi_g:
            return 0.0
        if val < lo_g:
            span = max(lo_g - lo_a, 0.01)
            return float(np.clip((lo_g - val) / span, 0.0, 1.0))
        span = max(hi_a - hi_g, 0.01)
        return float(np.clip((val - hi_g) / span, 0.0, 1.0))

    rows_sc = []   # score continuo
    rows_v  = []   # valor real

    def _add(p, lbl, val, score):
        rows_sc.append({'Periodo': p, 'indicador': lbl, 'score': score})
        rows_v.append( {'Periodo': p, 'indicador': lbl, 'valor': val})

    # ── CREA (mensual) ──────────────────────────────────────────────────
    try:
        dc = _load_crea()
        for _, r in dc.iterrows():
            p = r['Periodo']
            def _rv(col):
                v = r.get(col)
                return float(v) if v is not None and not pd.isna(v) else np.nan

            _add(p, '% VO/VT',        _rv('_pct_VO_VT'),    _ns_hi(_rv('_pct_VO_VT'),    75,  65))
            _add(p, 'Tasa parición',  _rv('_tasa_paricion'), _ns_hi(_rv('_tasa_paricion'),82,  75))
            _add(p, 'Días en leche',  _rv('Dias Lactancia'), _ns_rng(_rv('Dias Lactancia'),150,175,140,190))
            _add(p, 'Mort. perinatal',_rv('_mort_perinatal'),_ns_lo(_rv('_mort_perinatal'),5,   8))
            _add(p, 'Mort. adultas',  _rv('_mort_adultas'),  _ns_lo(_rv('_mort_adultas'),  3,   5.7))
            _add(p, 'Mort. guachera', _rv('_mort_guachera'), _ns_lo(_rv('_mort_guachera'), 8,  10.3))
            _add(p, 'Tasa abortos',   _rv('_tasa_abortos'),  _ns_lo(_rv('_tasa_abortos'),  3,   5))
    except Exception:
        pass

    # ── Calidad (mensual) ───────────────────────────────────────────────
    try:
        df_cal = _load_calidad()
        df_cal['Periodo'] = df_cal['fecha'].dt.to_period('M').dt.to_timestamp()
        df_cal['cs_f'] = pd.to_numeric(df_cal['celulas_somaticas'], errors='coerce').fillna(0)
        df_mes_cal = df_cal.groupby('Periodo').agg(
            grasa=('grasa_butirosa', 'mean'),
            proteina=('proteina',    'mean'),
            cs=('cs_f',             'mean'),
        ).reset_index()
        for _, r in df_mes_cal.iterrows():
            p = r['Periodo']
            cs_k = r['cs'] / 1000 if not np.isnan(r['cs']) else np.nan
            _add(p, 'Grasa (%)',    r['grasa'],    _ns_hi(r['grasa'],    3.2, 3.0))
            _add(p, 'Proteína (%)', r['proteina'], _ns_hi(r['proteina'], 3.3, 3.1))
            _add(p, 'CS (k/mL)',    cs_k,          _ns_lo(r['cs'], 250_000, 400_000))
    except Exception:
        pass

    # ── DairyComp (mensual, ventana 3 meses) ────────────────────────────
    try:
        df_ev_dc, _ = _load_dairycomp()
        df_ev_dc['Periodo'] = df_ev_dc['Fecha'].dt.to_period('M').dt.to_timestamp()
        max_ev_dc = df_ev_dc['Fecha'].max()
        cutoff_dc = max_ev_dc - pd.Timedelta(days=60)
        df_i_dc  = df_ev_dc[df_ev_dc['Evento']=='INSEMIN'][['ID','Fecha']].rename(columns={'Fecha':'FI'})
        df_pr_dc = df_ev_dc[df_ev_dc['Evento']=='PREÑADA'][['ID','Fecha']].rename(columns={'Fecha':'FPrena'})

        for mes in sorted(df_ev_dc['Periodo'].unique()):
            win_start = mes - pd.DateOffset(months=2)

            # TC — ventana 3m, excluir diagnósticos pendientes
            df_i_w = df_i_dc[(df_i_dc['FI'] >= win_start) &
                              (df_i_dc['FI'] <= mes) &
                              (df_i_dc['FI'] < cutoff_dc)]
            if len(df_i_w) >= 8:
                m = pd.merge(df_i_w, df_pr_dc, on='ID')
                m = m[(m['FPrena'] > m['FI']) &
                      (m['FPrena'] <= m['FI'] + pd.Timedelta(days=90))]
                tc_val = m.drop_duplicates(['ID','FI']).shape[0] / len(df_i_w) * 100
                _add(mes, 'TC (%)', tc_val, _ns_hi(tc_val, 51, 43))

            # Mort. rodeo — conteo mensual puntual
            df_m = df_ev_dc[df_ev_dc['Periodo'] == mes]
            n_id = df_m['ID'].nunique()
            n_mu = (df_m['Evento'] == 'MUERTA').sum()
            if n_id >= 10:
                mort_val = n_mu / n_id * 100
                _add(mes, 'Mort. rodeo/mes', mort_val, _ns_lo(mort_val, 0.5, 1.0))
    except Exception:
        pass

    if not rows_sc:
        return None, None

    df_sc = pd.DataFrame(rows_sc)
    df_v  = pd.DataFrame(rows_v)

    _ORDEN = [
        '% VO/VT', 'Tasa parición', 'Días en leche',
        'TC (%)', 'Mort. perinatal', 'Tasa abortos',
        'Mort. adultas', 'Mort. guachera', 'Mort. rodeo/mes',
        'Grasa (%)', 'Proteína (%)', 'CS (k/mL)',
    ]
    indicadores = [i for i in _ORDEN if i in df_sc['indicador'].unique()]
    indicadores += [i for i in df_sc['indicador'].unique() if i not in indicadores]
    periodos = sorted(df_sc['Periodo'].unique())

    mat_sc = pd.DataFrame(np.nan, index=indicadores, columns=periodos)
    mat_v  = pd.DataFrame(np.nan, index=indicadores, columns=periodos)

    for _, row in df_sc.iterrows():
        if row['indicador'] in mat_sc.index:
            mat_sc.loc[row['indicador'], row['Periodo']] = row['score']
    for _, row in df_v.iterrows():
        if row['indicador'] in mat_v.index:
            mat_v.loc[row['indicador'], row['Periodo']] = row['valor']

    return mat_sc, mat_v


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
            st.plotly_chart(charts['ltvo'], use_container_width=True, key="pop_ltvo")

with c2:
    v = k.get('l305e')
    _card("Proyección L305E promedio", _fmt(v, 0, " L"), _color(v, 10000, 8500),
          "verde ≥10.000 · amarillo 8.500-10.000 · rojo <8.500 · últimos 12m")
    if 'l305e' in charts:
        with st.popover("📈 ver distribución", use_container_width=True):
            st.plotly_chart(charts['l305e'], use_container_width=True, key="pop_l305e")

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
            st.plotly_chart(charts['grasa'], use_container_width=True, key="pop_grasa")

with c2:
    v = k.get('proteina')
    _card("Proteína (%)", _fmt(v, 2), _color(v, 3.3, 3.1),
          f"verde ≥3.3 · amarillo 3.1-3.3 · rojo <3.1 · hasta {ref_cal}")
    if 'proteina' in charts:
        with st.popover("📈 ver tendencia", use_container_width=True):
            st.plotly_chart(charts['proteina'], use_container_width=True, key="pop_proteina")

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
            st.plotly_chart(charts['cs'], use_container_width=True, key="pop_cs")

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
            st.plotly_chart(charts['ufc'], use_container_width=True, key="pop_ufc")

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
            st.plotly_chart(charts['tdc'], use_container_width=True, key="pop_tdc")

with c2:
    v = k.get('tc')
    _card("Tasa de concepción (%)", _fmt(v, 1, " %"), _color(v, 51, 43),
          "verde ≥51 · amarillo 43-51 · rojo <43 · solo serv. con diagnóstico confirmado")
    if 'tc' in charts:
        with st.popover("📈 ver mensual", use_container_width=True):
            st.plotly_chart(charts['tc'], use_container_width=True, key="pop_tc")

with c3:
    v = k.get('nsp')
    _card("Servicios por preñez", _fmt(v, 2), _color(v, 1.7, 2.5, invert=True),
          "verde <1.7 · amarillo 1.7-2.5 · rojo >2.5 · promedio por vaca")
    if 'nsp' in charts:
        with st.popover("📈 ver distribución", use_container_width=True):
            st.plotly_chart(charts['nsp'], use_container_width=True, key="pop_nsp")

with c4:
    v = k.get('d1s')
    _card("Días parto → 1er servicio", _fmt(v, 0, " d"), _color(v, 60, 75, invert=True),
          "verde <60 · amarillo 60-75 · rojo >75")
    if 'd1s' in charts:
        with st.popover("📈 ver distribución", use_container_width=True):
            st.plotly_chart(charts['d1s'], use_container_width=True, key="pop_d1s")

c1, c2, c3, c4 = st.columns(4)

with c1:
    v = k.get('dv')
    _card("Días vacíos (estimado a concepción)", _fmt(v, 0, " d"),
          _color(v, 110, 140, invert=True),
          "verde <110 · amarillo 110-140 · rojo >140 · fecha PREÑADA − 42d")
    if 'dv' in charts:
        with st.popover("📈 ver distribución", use_container_width=True):
            st.plotly_chart(charts['dv'], use_container_width=True, key="pop_dv")

with c2:
    v = k.get('ta')
    _card("Tasa de aborto (%)", _fmt(v, 1, " %"), _color(v, 3, 5, invert=True),
          "verde <3 · amarillo 3-5 · rojo >5 · vacas únicas con ABORTO / (PREÑADA+ABORTO)")
    if 'ta' in charts:
        with st.popover("📈 ver mensual", use_container_width=True):
            st.plotly_chart(charts['ta'], use_container_width=True, key="pop_ta")

with c3:
    v = k.get('tm')
    _card("Tasa de mortandad (%)", _fmt(v, 1, " %"), _color(v, 3, 5, invert=True),
          "verde <3 · amarillo 3-5 · rojo >5")
    if 'tm' in charts:
        with st.popover("📈 ver mensual", use_container_width=True):
            st.plotly_chart(charts['tm'], use_container_width=True, key="pop_tm")

with c4:
    v = k.get('td')
    _card("Tasa de descarte (%)", _fmt(v, 1, " %"), _color(v, 20, 30, invert=True),
          "verde <20 · amarillo 20-30 · rojo >30")
    if 'td' in charts:
        with st.popover("📈 ver mensual", use_container_width=True):
            st.plotly_chart(charts['td'], use_container_width=True, key="pop_td")

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
            st.plotly_chart(charts['mast'], use_container_width=True, key="pop_mast")

with c2:
    v = k.get('cs')
    disp = f"{v/1000:.0f}k" if v and not np.isnan(v) else "s/d"
    _card("Células somáticas (SCC prom.)", disp,
          _color(v, 250_000, 400_000, invert=True) if v else 'gris',
          "verde <250k · amarillo 250-400k · rojo >400k")
    if 'cs' in charts:
        with st.popover("📈 ver tendencia", use_container_width=True):
            st.plotly_chart(charts['cs'], use_container_width=True, key="pop_cs_2")

with c3:
    st.empty()

with c4:
    st.empty()

# ═══════════════════════════════════════════════════════════════════════
# GRUPO 5 — GESTIÓN DEL RODEO (CREA)
# ═══════════════════════════════════════════════════════════════════════
ref_crea = k.get('ref_crea', '?')
st.markdown(
    f'<p class="kpi-group-title">📊 Gestión del rodeo — datos CREA ({ref_crea})</p>',
    unsafe_allow_html=True,
)

if 'err_crea' in k:
    st.warning(f"No se pudieron cargar datos CREA: {k['err_crea']}")
else:
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        v = k.get('crea_pct_vo_vt')
        _card("% VO / VT", _fmt(v, 1, " %"), _color(v, 75, 65) if v else 'gris',
              "verde ≥75 · amarillo 65–75 · rojo <65 · INTA EEA Rafaela")
        if 'crea_pct_vo_vt' in charts:
            with st.popover("📈 ver 24m", use_container_width=True):
                st.plotly_chart(charts['crea_pct_vo_vt'], use_container_width=True, key="pop_crea_vo")

    with c2:
        v = k.get('crea_tasa_paricion')
        _card("Tasa parición (%)", _fmt(v, 1, " %"), _color(v, 82, 75) if v else 'gris',
              "verde ≥82 · amarillo 75–82 · rojo <75 · INTA Enc. Lechera 2018-19: media 82.7%")
        if 'crea_tasa_paricion' in charts:
            with st.popover("📈 ver 24m", use_container_width=True):
                st.plotly_chart(charts['crea_tasa_paricion'], use_container_width=True, key="pop_crea_paricion")

    with c3:
        v = k.get('crea_del')
        if v:
            col_del = 'verde' if 150 <= v <= 175 else ('amarillo' if 140 <= v < 150 or 175 < v <= 190 else 'rojo')
        else:
            col_del = 'gris'
        _card("Días en lactancia", _fmt(v, 0, " d"), col_del,
              "verde 150–175 d · amarillo 140–150 o 175–190 · rojo fuera · Piccardi (2014) CONICET")
        if 'crea_del' in charts:
            with st.popover("📈 ver 24m", use_container_width=True):
                st.plotly_chart(charts['crea_del'], use_container_width=True, key="pop_crea_del")

    with c4:
        v = k.get('crea_mort_perinatal')
        _card("Mort. perinatal (%)", _fmt(v, 1, " %"), _color(v, 5, 8, invert=True) if v else 'gris',
              "verde <5 · amarillo 5–8 · rojo >8 · Piccardi (2014) CONICET")
        if 'crea_mort_perinatal' in charts:
            with st.popover("📈 ver 24m", use_container_width=True):
                st.plotly_chart(charts['crea_mort_perinatal'], use_container_width=True, key="pop_crea_perinat")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        v = k.get('crea_mort_adultas')
        _card("Mort. adultas (%)", _fmt(v, 1, " %"), _color(v, 3, 5.7, invert=True) if v else 'gris',
              "verde <3 · amarillo 3–5.7 · rojo >5.7 · INTA Enc. Lechera 2018-19: media 5.7%")
        if 'crea_mort_adultas' in charts:
            with st.popover("📈 ver 24m", use_container_width=True):
                st.plotly_chart(charts['crea_mort_adultas'], use_container_width=True, key="pop_crea_mort_a")

    with c2:
        v = k.get('crea_mort_guachera')
        _card("Mort. guachera (%)", _fmt(v, 1, " %"), _color(v, 8, 10.3, invert=True) if v else 'gris',
              "verde <8 · amarillo 8–10.3 · rojo >10.3 · INTA Enc. Lechera 2018-19: media 10.3%")
        if 'crea_mort_guachera' in charts:
            with st.popover("📈 ver 24m", use_container_width=True):
                st.plotly_chart(charts['crea_mort_guachera'], use_container_width=True, key="pop_crea_guach")

    with c3:
        v = k.get('crea_tasa_abortos')
        _card("Tasa abortos CREA (%)", _fmt(v, 1, " %"), _color(v, 3, 5, invert=True) if v else 'gris',
              "verde <3 · amarillo 3–5 · rojo >5 · Piccardi (2014) CONICET")
        if 'crea_tasa_abortos' in charts:
            with st.popover("📈 ver 24m", use_container_width=True):
                st.plotly_chart(charts['crea_tasa_abortos'], use_container_width=True, key="pop_crea_abort")

    with c4:
        v = k.get('crea_pct_hembras')
        _card("% hembras nacidas", _fmt(v, 1, " %"), 'gris',
              "esperado ~50 % (biológico) · sin meta de manejo")
        if 'crea_pct_hembras' in charts:
            with st.popover("📈 ver 24m", use_container_width=True):
                st.plotly_chart(charts['crea_pct_hembras'], use_container_width=True, key="pop_crea_hembr")

# ═══════════════════════════════════════════════════════════════════════
# Documentación de KPIs
# ═══════════════════════════════════════════════════════════════════════
def _doc_kpi(titulo, descripcion, formula, umbrales, referencia, fuente, chart_key=None):
    """Renderiza un bloque de documentación con texto + gráfico opcional."""
    has_chart = chart_key and chart_key in charts
    if has_chart:
        ct, cc = st.columns([3, 2])
    else:
        ct, cc = st.container(), None
    ct.markdown(f"**{titulo}**")
    ct.markdown(descripcion)
    ct.caption(f"📐 **Fórmula:** {formula}")
    ct.caption(f"🎯 **Umbrales:** {umbrales}")
    ct.caption(f"📚 **Referencia:** {referencia}")
    ct.caption(f"💾 **Fuente actual:** {fuente}")
    if has_chart:
        cc.plotly_chart(charts[chart_key], use_container_width=True,
                        key=f"doc_{chart_key}")
    st.divider()


st.divider()

# ═══════════════════════════════════════════════════════════════════════
# SEMÁFORO HISTÓRICO
# ═══════════════════════════════════════════════════════════════════════
st.markdown('<p class="kpi-group-title">📅 Semáforo histórico — evolución de indicadores</p>',
            unsafe_allow_html=True)
st.caption(
    "Cada celda muestra el estado del indicador en ese mes. "
    "🟩 verde = dentro del objetivo · 🟨 amarillo = alerta · 🟥 rojo = fuera de rango · "
    "⬜ gris = sin dato. "
    "Períodos con múltiples rojos simultáneos señalan momentos de disfunción sistémica."
)

with st.spinner("Construyendo semáforo histórico..."):
    mat_s, mat_v = _build_semaforo_hist()

if mat_s is None:
    st.info("No hay datos suficientes para construir el semáforo histórico.")
else:
    # Filtro de rango de fechas
    _all_periodos = list(mat_s.columns)
    _min_p = pd.Timestamp(_all_periodos[0])
    _max_p = pd.Timestamp(_all_periodos[-1])
    _col_rng, _col_gap = st.columns([3, 1])
    with _col_rng:
        _rng = st.slider(
            "Período",
            min_value=_min_p.date(), max_value=_max_p.date(),
            value=(_min_p.date(), _max_p.date()),
            format="MMM YYYY", key="sem_hist_rng",
        )
    _sel_cols = [p for p in _all_periodos
                 if _rng[0] <= pd.Timestamp(p).date() <= _rng[1]]
    mat_f = mat_s[_sel_cols]
    val_f = mat_v[_sel_cols]

    # Colorscale continua verde→amarillo→naranja→rojo (zmin=0, zmax=1)
    _CS = [
        [0.00, '#27ae60'],  # verde puro  — en meta
        [0.35, '#f1c40f'],  # amarillo    — zona de alerta
        [0.65, '#e67e22'],  # naranja     — alejándose
        [1.00, '#c0392b'],  # rojo oscuro — muy lejos de meta
    ]

    # Hover con valor real
    _UNITS = {
        '% VO/VT': '%', 'Tasa parición': '%', 'Días en leche': 'd',
        'TC (%)': '%', 'Mort. perinatal': '%', 'Tasa abortos': '%',
        'Mort. adultas': '%', 'Mort. guachera': '%', 'Mort. rodeo/mes': '%',
        'Grasa (%)': '%', 'Proteína (%)': '%', 'CS (k/mL)': 'k/mL',
    }
    hover_text = []
    for ind in mat_f.index:
        row_txt = []
        unit = _UNITS.get(ind, '')
        for p in _sel_cols:
            v   = val_f.loc[ind, p]
            sc  = mat_f.loc[ind, p]
            if np.isnan(v) or np.isnan(sc):
                row_txt.append(f"<b>{ind}</b><br>{pd.Timestamp(p).strftime('%b %Y')}<br>sin dato")
            else:
                dec = 0 if unit == 'd' else 1
                pct_meta = int((1 - sc) * 100)
                row_txt.append(
                    f"<b>{ind}</b><br>{pd.Timestamp(p).strftime('%b %Y')}<br>"
                    f"valor: {v:.{dec}f} {unit}<br>"
                    f"cercanía a meta: {pct_meta} %"
                )
        hover_text.append(row_txt)

    x_labels = [pd.Timestamp(p).strftime('%b %y') for p in _sel_cols]

    # Reemplazar NaN por None para que Plotly los muestre en gris
    z_vals = mat_f.where(mat_f.notna(), other=None).values.tolist()

    fig_sem = go.Figure(go.Heatmap(
        z=z_vals,
        x=x_labels,
        y=list(mat_f.index),
        text=hover_text,
        hovertemplate='%{text}<extra></extra>',
        colorscale=_CS,
        zmin=0, zmax=1,
        showscale=True,
        colorbar=dict(
            title=dict(text='← meta / lejos →'),
            tickvals=[0, 0.5, 1],
            ticktext=['en meta', 'alerta', 'crítico'],
            len=0.6,
        ),
        xgap=2, ygap=2,
    ))

    # Separadores visuales entre grupos
    _SEPARADORES = ['TC (%)', 'Grasa (%)']
    for sep_ind in _SEPARADORES:
        if sep_ind in list(mat_f.index):
            idx_sep = list(mat_f.index).index(sep_ind)
            fig_sem.add_hline(
                y=idx_sep + 0.5,
                line_width=2, line_color='rgba(255,255,255,0.5)',
                line_dash='dot',
            )

    _h = max(320, len(mat_f.index) * 40 + 80)
    fig_sem.update_layout(
        height=_h,
        margin=dict(t=20, b=60, l=160, r=120),
        xaxis=dict(side='bottom', tickangle=-45, tickfont=dict(size=10)),
        yaxis=dict(tickfont=dict(size=11), autorange='reversed'),
        plot_bgcolor='rgba(128,128,128,0.08)',
        paper_bgcolor='rgba(0,0,0,0)',
    )
    st.plotly_chart(fig_sem, use_container_width=True, key='semaforo_hist')

    st.caption(
        "⬜ gris = sin dato · "
        '<span style="color:#27ae60">■</span> verde = en meta · '
        '<span style="color:#f1c40f">■</span> amarillo = alerta · '
        '<span style="color:#e67e22">■</span> naranja = alejándose · '
        '<span style="color:#c0392b">■</span> rojo = crítico — '
        'el color es proporcional a la distancia al objetivo, no un umbral fijo',
        unsafe_allow_html=True,
    )

st.divider()
with st.expander("ℹ️ Definición, metodología y fuentes de cada KPI"):

    # ── Producción ───────────────────────────────────────────────────────────
    st.markdown("### 🥛 Producción")
    _doc_kpi(
        "LTVO — Litros por Vaca Ordeñada",
        "Producción diaria promedio del rodeo por vaca en ordeño (sin incluir secas). "
        "Es el termómetro más directo de la eficiencia productiva diaria.",
        f"promedio `diaria_ltvo` últimos 30d → hasta {ref_ctrl}",
        "🟢 ≥ 30 L · 🟡 26–30 L · 🔴 < 26 L",
        "Benchmarks CREA Litoral (tambo intensivo, HF)",
        "Parte Diario — Google Sheets, actualización manual diaria",
        chart_key='ltvo',
    )
    _doc_kpi(
        "L305E — Proyección a 305 días",
        "Producción total proyectada de cada vaca normalizada a 305 días de lactancia "
        "según modelo de Wood (y = a·t^b·e^−ct). Permite comparar vacas en distintos "
        "estadios sobre una base común. El gráfico muestra la distribución del rodeo.",
        "promedio campo `305E` en controles DairyComp — últimos 12m",
        "🟢 ≥ 10.000 L · 🟡 8.500–10.000 L · 🔴 < 8.500 L",
        "Piccardi et al. (2019), CONICET / Editorial Brujas",
        "`control-202604.csv` — exportación estática de DairyComp",
        chart_key='l305e',
    )

    # ── Calidad ───────────────────────────────────────────────────────────────
    st.markdown("### 🔬 Calidad de leche")
    _doc_kpi(
        "Grasa butirosa (%)",
        "% de grasa en leche. Afecta precio pagado por industria. "
        "Influenciado por fibra efectiva en la dieta, estado corporal y etapa de lactancia.",
        "promedio diario `grasa_butirosa` últimos 30d (outliers filtrados: rango 1–7 %)",
        "🟢 ≥ 3.2 % · 🟡 3.0–3.2 % · 🔴 < 3.0 %",
        "SENASA / Piccardi et al. (2019)",
        f"`calidad_leche.csv` — PDFs laboratorio, OCR + revisión manual — hasta {ref_cal}",
        chart_key='grasa',
    )
    _doc_kpi(
        "Proteína (%)",
        "% de proteína bruta en leche. Indicador de eficiencia en uso de proteína dietaria. "
        "Valores bajos sugieren déficit energético o proteico.",
        "promedio diario `proteina` últimos 30d (rango fisiológico: 2.5–5.0 %)",
        "🟢 ≥ 3.3 % · 🟡 3.1–3.3 % · 🔴 < 3.1 %",
        "Piccardi et al. (2019)",
        f"`calidad_leche.csv` — hasta {ref_cal}",
        chart_key='proteina',
    )
    _doc_kpi(
        "Células somáticas — SCC (cel/mL)",
        "Recuento de células somáticas: indicador primario de mastitis subclínica y "
        "salud de ubre. Valores altos reducen precio, vida útil y producción futura. "
        "Días sin dato se interpretan como 0 (sin evento de mastitis).",
        "promedio diario `celulas_somaticas` últimos 30d (sin dato = 0)",
        "🟢 < 250k · 🟡 250–400k · 🔴 > 400k cel/mL",
        "Reglamento 2687 SENASA; Schukken et al. (2003); Piccardi et al. (2019)",
        f"`calidad_leche.csv` — hasta {ref_cal}",
        chart_key='cs',
    )
    _doc_kpi(
        "Recuento bacteriano — UFC (UFC/mL)",
        "Unidades formadoras de colonias por mL. Indicador de higiene de ordeño, "
        "limpieza de equipos y cadena de frío. Días sin análisis = 0. "
        "El gráfico muestra solo los días con conteo > 0, coloreados por severidad.",
        "promedio diario `recuento_ufc` últimos 30d (sin dato = 0)",
        "🟢 < 20k · 🟡 20–50k · 🔴 > 50k UFC/mL",
        "Resolución 2/2020 SENASA; Piccardi et al. (2019)",
        f"`calidad_leche.csv` — hasta {ref_cal}",
        chart_key='ufc',
    )

    # ── Reproducción ─────────────────────────────────────────────────────────
    st.markdown("### 🐄 Reproducción")
    _doc_kpi(
        "TDC — Tasa de Detección de Celo (%)",
        "% de vacas con parto en 12m que tuvieron al menos un celo detectado por collar. "
        "Alta TDC indica buena expresión del celo (salud metabólica) y eficacia del sistema "
        "(collar de actividad). El gráfico muestra la evolución mensual.",
        "vacas únicas con CELO / vacas únicas con PARTO en 12m × 100",
        "🟢 ≥ 90 % · 🟡 70–90 % · 🔴 < 70 %",
        "Cavestany & Galina (2002); benchmarks CREA",
        f"`eventos-202604.csv` — DairyComp (collares) — hasta {ref_ev}",
        chart_key='tdc',
    )
    _doc_kpi(
        "TC — Tasa de Concepción (%)",
        "% de inseminaciones que resultan en preñez confirmada (PREÑADA dentro de 90d). "
        "Se excluyen servicios de los últimos 60 días para no penalizar diagnósticos aún "
        "pendientes. El gráfico muestra TC mensual — útil para detectar meses problemáticos.",
        "serv. con PREÑADA en 90d / total serv. elegibles (excl. últimos 60d) × 100",
        "🟢 ≥ 51 % · 🟡 43–51 % · 🔴 < 43 %",
        "Piccardi et al. (2019); Lucy (2001) J. Dairy Sci.",
        f"`eventos-202604.csv` — hasta {ref_ev}",
        chart_key='tc',
    )
    _doc_kpi(
        "NS/P — Número de servicios por preñez",
        "Promedio de inseminaciones necesarias para lograr una preñez por vaca. "
        "Relacionado con TC: NS/P ≈ 1/TC. El gráfico muestra cuántas vacas necesitaron "
        "1, 2, 3… servicios — la forma de la distribución es tan informativa como el promedio.",
        "promedio de INSEMIN entre PARTO y primera PREÑADA, por vaca, en partos de 12m",
        "🟢 < 1.7 · 🟡 1.7–2.5 · 🔴 > 2.5",
        "Piccardi et al. (2019)",
        f"`eventos-202604.csv` — hasta {ref_ev}",
        chart_key='nsp',
    )
    _doc_kpi(
        "D1S — Días parto → primer servicio",
        "Días entre el parto y la primera inseminación. Refleja el período voluntario de "
        "espera (PVE). El histograma muestra si el grueso del rodeo arranca antes de los 60d "
        "o si hay vacas que se retrasan (anestros, problemas puerperales).",
        "fecha 1er INSEMIN − fecha PARTO, por vaca, partos en 12m",
        "🟢 < 60 d · 🟡 60–75 d · 🔴 > 75 d",
        "Risco & Melendez (2011); Piccardi et al. (2019)",
        f"`eventos-202604.csv` — hasta {ref_ev}",
        chart_key='d1s',
    )
    _doc_kpi(
        "DV — Días vacíos (estimado a concepción)",
        "Días entre parto y concepción real estimada. DairyComp registra la fecha del "
        "diagnóstico (tacto), no la de concepción. Se restan 42 días (lag estándar de "
        "diagnóstico) para estimar cuándo ocurrió la concepción real.",
        "(fecha PREÑADA − 42d) − fecha PARTO · primera PREÑADA por vaca en 12m",
        "🟢 < 110 d · 🟡 110–140 d · 🔴 > 140 d",
        "Stevenson (2001); benchmarks CREA Litoral",
        f"`eventos-202604.csv` — hasta {ref_ev}",
        chart_key='dv',
    )
    _doc_kpi(
        "TA — Tasa de aborto (%)",
        "% de gestaciones confirmadas que terminan en aborto. Puede indicar problemas "
        "sanitarios (BVD, leptospira, neospora) o nutricionales. Se calcula sobre vacas "
        "únicas para no contar múltiples abortos de la misma vaca como casos distintos.",
        "vacas únicas con ABORTO / (vacas únicas PREÑADA + ABORTO) × 100 · 12m",
        "🟢 < 3 % · 🟡 3–5 % · 🔴 > 5 %",
        "Gnemmi & Maraboli (2010); Piccardi et al. (2019)",
        f"`eventos-202604.csv` — hasta {ref_ev}",
        chart_key='ta',
    )
    _doc_kpi(
        "TM — Tasa de mortandad (%) / TD — Tasa de descarte (%)",
        "TM: % de vacas que mueren en el año (indica problemas sanitarios). "
        "TD: % de vacas vendidas (puede ser descarte voluntario por selección genética "
        "o forzado por salud/reproducción). Ambos sobre vacas únicas activas en 12m.",
        "vacas únicas MUERTA (o VENDIDA) / vacas únicas activas × 100 · 12m",
        "TM 🟢 < 3% · 🟡 3–5% · 🔴 > 5% | TD 🟢 < 20% · 🟡 20–30% · 🔴 > 30%",
        "Hadley et al. (2006); Piccardi et al. (2019)",
        f"`eventos-202604.csv` — hasta {ref_ev}",
    )

    # ── Sanidad ───────────────────────────────────────────────────────────────
    st.markdown("### 💊 Sanidad")
    _doc_kpi(
        "Incidencia de mastitis (% vacas)",
        "% de vacas con al menos un evento de mastitis clínica registrada en DairyComp "
        "en 12 meses. Complementa el SCC (que mide mastitis subclínica). El gráfico "
        "muestra la distribución mensual de casos para detectar estacionalidad.",
        "vacas únicas con MAST / vacas únicas activas × 100 · 12m",
        "🟢 < 15 % · 🟡 15–25 % · 🔴 > 25 %",
        "Schukken et al. (2003); Piccardi et al. (2019)",
        f"`eventos-202604.csv` — DairyComp, registros de tratamientos — hasta {ref_ev}",
        chart_key='mast',
    )

    # ── Gestión del rodeo (CREA) ──────────────────────────────────────────────
    st.markdown("### 📊 Gestión del rodeo (CREA)")
    _doc_kpi(
        "% VO / VT — Vacas en ordeño sobre total",
        "Proporción del rodeo efectivamente en producción. Refleja la eficiencia "
        "reproductiva y el manejo de secado. Un valor bajo puede indicar exceso de "
        "vacas secas, alta mortalidad o problemas de concepción.",
        "VO / VT × 100 · dato del mes más reciente de la planilla CREA",
        "🟢 ≥ 75 % · 🟡 65–75 % · 🔴 < 65 %",
        "INTA EEA Rafaela — referencia de gestión para tambos del Litoral",
        f"Planilla CREA (Google Sheets) — hasta {ref_crea}",
        chart_key='crea_pct_vo_vt',
    )
    _doc_kpi(
        "Tasa de parición (%)",
        "% de vacas totales que parieron en el mes. Acumulada en 12 meses es el "
        "indicador más directo de eficiencia reproductiva anual del rodeo completo. "
        "La media nacional en la Encuesta Sectorial INTA 2018-19 fue 82.7 %.",
        "Partos Totales / VT × 100 · dato mensual CREA",
        "🟢 ≥ 82 % · 🟡 75–82 % · 🔴 < 75 %",
        "Gastaldi L. et al. (2020). *Encuesta Sectorial Lechera 2018–2019.* INTA EEA Rafaela.",
        f"Planilla CREA — hasta {ref_crea}",
        chart_key='crea_tasa_paricion',
    )
    _doc_kpi(
        "Días en lactancia (DEL promedio)",
        "Promedio de días en leche del rodeo. Refleja el estado medio de la curva de "
        "lactancia. Un DEL muy alto indica rodeo 'envejecido' (vacas que no repiten); "
        "muy bajo, exceso de frescas recientes. Piccardi (2014) reportó medianas de "
        "111–171 d según tipo de tambo (baja a alta producción).",
        "promedio campo `Dias Lactancia` de la planilla CREA",
        "🟢 150–175 d · 🟡 140–150 d o 175–190 d · 🔴 fuera de ese rango",
        "Piccardi M.A. (2014). *Tesis doctoral UNC/CONICET* — 291 tambos SF+Córdoba, DairyComp305.",
        f"Planilla CREA — hasta {ref_crea}",
        chart_key='crea_del',
    )
    _doc_kpi(
        "Mortalidad perinatal (%)",
        "% de terneros nacidos muertos sobre el total de partos. Incluye tanto mortinatos "
        "como muertes en las primeras horas. Indicador de condición corporal al parto, "
        "manejo del preparto y distocias.",
        "Partos Muertos / Partos Totales × 100",
        "🟢 < 5 % · 🟡 5–8 % · 🔴 > 8 %",
        "Piccardi M.A. (2014). *Tesis doctoral UNC/CONICET.*",
        f"Planilla CREA — hasta {ref_crea}",
        chart_key='crea_mort_perinatal',
    )
    _doc_kpi(
        "Mortalidad de adultas (%)",
        "% de vacas muertas sobre el total del rodeo. Incluye muertes por enfermedad, "
        "accidente o sacrificio. La media nacional (INTA 2018-19) fue 5.7 %; valores "
        "superiores al 6 % ameritan revisión sanitaria.",
        "Muertes / VT × 100",
        "🟢 < 3 % · 🟡 3–5.7 % · 🔴 > 5.7 %",
        "Gastaldi L. et al. (2020). *Encuesta Sectorial Lechera 2018–2019.* INTA EEA Rafaela. "
        "Piccardi M.A. (2014). *Tesis doctoral UNC/CONICET* — mortalidad por tipo de tambo: 7.2–11.1 %.",
        f"Planilla CREA — hasta {ref_crea}",
        chart_key='crea_mort_adultas',
    )
    _doc_kpi(
        "Mortalidad en guachera (%)",
        "% de terneras muertas en crianza artificial sobre las hembras nacidas. "
        "Alta mortalidad señala problemas de calostrado, manejo sanitario de terneras "
        "o instalaciones. La media INTA 2018-19 fue 10.3 %.",
        "Muertes guachera / Hembras nacidas × 100",
        "🟢 < 8 % · 🟡 8–10.3 % · 🔴 > 10.3 %",
        "Gastaldi L. et al. (2020). *Encuesta Sectorial Lechera 2018–2019.* INTA EEA Rafaela.",
        f"Planilla CREA — hasta {ref_crea}",
        chart_key='crea_mort_guachera',
    )
    _doc_kpi(
        "Tasa de abortos — CREA (%)",
        "% de abortos sobre el total de vacas. Complementa la tasa calculada desde "
        "DairyComp (que usa diagnóstico por vaca). Valores elevados sostenidos justifican "
        "serología para BVD, leptospira y neospora.",
        "Abortos / VT × 100",
        "🟢 < 3 % · 🟡 3–5 % · 🔴 > 5 %",
        "Gnemmi G. & Maraboli C. (2010). *Manejo reproductivo bovino.* Merial. "
        "Piccardi M.A. (2014). *Tesis doctoral UNC/CONICET.*",
        f"Planilla CREA — hasta {ref_crea}",
        chart_key='crea_tasa_abortos',
    )
    _doc_kpi(
        "% Hembras nacidas",
        "Proporción de hembras sobre el total de terneros nacidos. Sin meta de manejo "
        "— se espera ~50 % por distribución biológica. Una desviación sostenida puede "
        "indicar errores de registro, no causas biológicas.",
        "Hembras nacidas / Partos Totales × 100",
        "⚪ referencia ~50 % (biológico esperado)",
        "Valor informativo — sin umbral de gestión establecido.",
        f"Planilla CREA — hasta {ref_crea}",
        chart_key='crea_pct_hembras',
    )

    # ── Fuentes ───────────────────────────────────────────────────────────────
    st.markdown("### 💾 Resumen de fuentes y bibliografía")
    st.markdown(f"""
| Fuente | Tipo | Cobertura | Actualización |
|---|---|---|---|
| Parte Diario | Google Sheets (público) | hasta {ref_ctrl} | Manual, diaria |
| DairyComp eventos | CSV estático `eventos-202604.csv` | hasta {ref_ev} | Manual, exportar DairyComp |
| DairyComp controles | CSV estático `control-202604.csv` | hasta {ref_ctrl} | Manual, exportar DairyComp |
| Calidad de leche | CSV estático `calidad_leche.csv` | hasta {ref_cal} | Manual, PDFs laboratorio |
| Planilla CREA | Google Sheets (privado) | hasta {ref_crea} | Manual, mensual |
| Tipo de cambio | CSV estático `usdars.csv` | histórico 2010–2026 | Periódica |

**Bibliografía de umbrales:**

- Piccardi M.A. (2014). *Indicadores de eficiencia productiva y reproductiva en rodeos lecheros argentinos.* Tesis doctoral, Universidad Nacional de Córdoba / CONICET. 291 tambos SF+Córdoba, DairyComp305.
- Gastaldi L., Doménech A., Litwin G., Cappelletti M. (2020). *Encuesta Sectorial Lechera 2018–2019.* INTA EEA Rafaela, Documento de Trabajo Nº 8.
- Lucy M.C. (2001). Reproductive loss in high-producing dairy cattle. *J. Dairy Sci.* 84:1277–1293.
- Schukken Y.H. et al. (2003). Monitoring udder health and milk quality using somatic cell counts. *Prev. Vet. Med.* 61:75–93.
- Stevenson J.S. (2001). Reproductive management of dairy cows in high milk-producing herds. *J. Dairy Sci.* 84(E. Suppl.):E128–E143.
- Gnemmi G. & Maraboli C. (2010). *Manejo reproductivo bovino.* Merial Argentina.
- Hadley G.L., Wolf C.A., Harsh S.B. (2006). Dairy cattle culling patterns, explanations, and implications. *J. Dairy Sci.* 89:2286–2296.
- Cavestany D. & Galina C.S. (2002). *Evaluación de la eficiencia reproductiva.* INIA Uruguay.
""")

