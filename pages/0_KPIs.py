import os
import streamlit as st
import pandas as pd
import numpy as np

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
        n_vacas   = df_12m['ID'].nunique()
        k['n_vacas'] = n_vacas

        n_partos   = (df_12m['Evento'] == 'PARTO').sum()
        n_insemin  = (df_12m['Evento'] == 'INSEMIN').sum()
        n_prenadas = (df_12m['Evento'] == 'PREÑADA').sum()
        n_abortos  = (df_12m['Evento'] == 'ABORTO').sum()
        n_muertas  = (df_12m['Evento'] == 'MUERTA').sum()
        n_vendidas = (df_12m['Evento'] == 'VENDIDA').sum()

        k['n_partos']  = int(n_partos)
        k['n_insemin'] = int(n_insemin)

        if n_insemin > 0:
            k['tc'] = n_prenadas / n_insemin * 100
        if n_prenadas > 0:
            k['nsp'] = n_insemin / n_prenadas
        if n_prenadas + n_abortos > 0:
            k['ta'] = n_abortos / (n_prenadas + n_abortos) * 100
        if n_vacas > 0:
            k['tm']  = n_muertas  / n_vacas * 100
            k['td']  = n_vendidas / n_vacas * 100

        # D1S: días parto → primer servicio
        df_p = df_ev[df_ev['Evento'] == 'PARTO'][['ID', 'Fecha']].rename(columns={'Fecha': 'FP'})
        df_i = df_ev[df_ev['Evento'] == 'INSEMIN'][['ID', 'Fecha']].rename(columns={'Fecha': 'FI'})
        df_p12 = df_p[df_p['FP'] >= ref_ev_12m]
        if not df_p12.empty and not df_i.empty:
            m = pd.merge(df_p12, df_i, on='ID')
            m = m[(m['FI'] > m['FP']) & (m['FI'] <= m['FP'] + pd.Timedelta(days=250))]
            if not m.empty:
                fi = m.sort_values('FI').groupby(['ID', 'FP']).first().reset_index()
                fi['d'] = (fi['FI'] - fi['FP']).dt.days
                k['d1s'] = float(fi['d'].mean())

        # DV: días vacíos parto → primera preñez
        df_pr = df_ev[df_ev['Evento'] == 'PREÑADA'][['ID', 'Fecha']].rename(columns={'Fecha': 'FPrena'})
        if not df_p12.empty and not df_pr.empty:
            m2 = pd.merge(df_p12, df_pr, on='ID')
            m2 = m2[(m2['FPrena'] > m2['FP']) & (m2['FPrena'] <= m2['FP'] + pd.Timedelta(days=400))]
            if not m2.empty:
                fp = m2.sort_values('FPrena').groupby(['ID', 'FP']).first().reset_index()
                fp['d'] = (fp['FPrena'] - fp['FP']).dt.days
                k['dv'] = float(fp['d'].mean())

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
        cs = df30['celulas_somaticas'].dropna()
        if not cs.empty:
            k['cs'] = float(cs.mean())
        ufc = df30['recuento_ufc'].dropna()
        if not ufc.empty:
            k['ufc'] = float(ufc.mean())
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


# ── UI ────────────────────────────────────────────────────────────────────────
st.title("🎯 Dashboard KPIs — Tambo DJSA")

with st.spinner("Calculando indicadores..."):
    k = _calc()

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
    _card("LTVO promedio (L/vc/día)",
          _fmt(v, 1),
          _color(v, 30, 26),
          f"verde ≥30 · amarillo 26-30 · rojo <26 · parte diario, 30d hasta {ref_ctrl}")

with c2:
    v = k.get('l305e')
    _card("Proyección L305E promedio",
          _fmt(v, 0, " L"),
          _color(v, 10000, 8500),
          "verde ≥10.000 · amarillo 8.500-10.000 · rojo <8.500 · últimos 12m")

with c3:
    n = k.get('n_partos')
    _card("Partos (12 meses)",
          _fmt(n, 0) if n else "s/d",
          'gris', f"total acumulado · hasta {ref_ev}")

with c4:
    n = k.get('n_insemin')
    _card("Inseminaciones (12 meses)",
          _fmt(n, 0) if n else "s/d",
          'gris', f"total acumulado · hasta {ref_ev}")

# ═══════════════════════════════════════════════════════════════════════
# GRUPO 2 — CALIDAD DE LECHE
# ═══════════════════════════════════════════════════════════════════════
st.markdown('<p class="kpi-group-title">🔬 Calidad de leche (últimos 30 días)</p>', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)

with c1:
    v = k.get('grasa')
    _card("Grasa butirosa (%)",
          _fmt(v, 2),
          _color(v, 3.2, 3.0),
          f"verde ≥3.2 · amarillo 3.0-3.2 · rojo <3.0 · hasta {ref_cal}")

with c2:
    v = k.get('proteina')
    _card("Proteína (%)",
          _fmt(v, 2),
          _color(v, 3.3, 3.1),
          f"verde ≥3.3 · amarillo 3.1-3.3 · rojo <3.1 · hasta {ref_cal}")

with c3:
    v = k.get('cs')
    disp = f"{v/1000:.0f}k cél/mL" if v and not np.isnan(v) else "s/d"
    _card("Células somáticas (SCC)",
          disp,
          _color(v, 250_000, 400_000, invert=True) if v else 'gris',
          f"verde <250k · amarillo 250-400k · rojo >400k · hasta {ref_cal}")

with c4:
    v = k.get('ufc')
    disp = f"{v/1000:.0f}k UFC/mL" if v and not np.isnan(v) else "s/d"
    _card("Recuento bacteriano (UFC)",
          disp,
          _color(v, 20_000, 50_000, invert=True) if v else 'gris',
          f"verde <20k · amarillo 20-50k · rojo >50k · hasta {ref_cal}")

# ═══════════════════════════════════════════════════════════════════════
# GRUPO 3 — REPRODUCCIÓN
# ═══════════════════════════════════════════════════════════════════════
st.markdown('<p class="kpi-group-title">🐄 Reproducción (últimos 12 meses)</p>', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)

with c1:
    v = k.get('dv')
    _card("Días vacíos (parto → preñez)",
          _fmt(v, 0, " d"),
          _color(v, 110, 140, invert=True),
          "verde <110 · amarillo 110-140 · rojo >140")

with c2:
    v = k.get('d1s')
    _card("Días parto → 1er servicio",
          _fmt(v, 0, " d"),
          _color(v, 60, 75, invert=True),
          "verde <60 · amarillo 60-75 · rojo >75")

with c3:
    v = k.get('nsp')
    _card("Servicios por preñez",
          _fmt(v, 2),
          _color(v, 1.7, 2.5, invert=True),
          "verde <1.7 · amarillo 1.7-2.5 · rojo >2.5")

with c4:
    v = k.get('tc')
    _card("Tasa de concepción (%)",
          _fmt(v, 1, " %"),
          _color(v, 51, 43),
          "verde ≥51 · amarillo 43-51 · rojo <43")

c1, c2, c3, c4 = st.columns(4)

with c1:
    v = k.get('ta')
    _card("Tasa de aborto (%)",
          _fmt(v, 1, " %"),
          _color(v, 3, 5, invert=True),
          "verde <3 · amarillo 3-5 · rojo >5")

with c2:
    v = k.get('tm')
    _card("Tasa de mortandad (%)",
          _fmt(v, 1, " %"),
          _color(v, 3, 5, invert=True),
          "verde <3 · amarillo 3-5 · rojo >5")

with c3:
    v = k.get('td')
    _card("Tasa de descarte (%)",
          _fmt(v, 1, " %"),
          _color(v, 20, 30, invert=True),
          "verde <20 · amarillo 20-30 · rojo >30")

with c4:
    n = k.get('n_vacas')
    _card("Vacas en seguimiento",
          _fmt(n, 0) if n else "s/d",
          'gris', f"IDs únicos con eventos · hasta {ref_ev}")

# ═══════════════════════════════════════════════════════════════════════
# GRUPO 4 — SANIDAD
# ═══════════════════════════════════════════════════════════════════════
st.markdown('<p class="kpi-group-title">💊 Sanidad (últimos 12 meses)</p>', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)

with c1:
    v = k.get('mast')
    _card("Incidencia mastitis (% vacas)",
          _fmt(v, 1, " %"),
          _color(v, 15, 25, invert=True),
          "verde <15 · amarillo 15-25 · rojo >25")

with c2:
    # CS ya está en calidad, repetir aquí para sanidad
    v = k.get('cs')
    disp = f"{v/1000:.0f}k" if v and not np.isnan(v) else "s/d"
    _card("Células somáticas (SCC prom.)",
          disp,
          _color(v, 250_000, 400_000, invert=True) if v else 'gris',
          "verde <250k · amarillo 250-400k · rojo >400k")

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
| LTVO | DairyComp controles | 30d hasta {ref_ctrl} | Promedio LECH (VALR>0) |
| L305E | DairyComp controles | 12m | Promedio campo 305E |
| Grasa / Proteína | calidad_leche.csv | 30d hasta {ref_cal} | Promedio diario (outliers filtrados) |
| CS / UFC | calidad_leche.csv | 30d hasta {ref_cal} | Promedio días con medición (~23% de días) |
| DV (días vacíos) | DairyComp eventos | 12m hasta {ref_ev} | Primera PREÑADA post-PARTO por vaca |
| D1S | DairyComp eventos | 12m | Primer INSEMIN post-PARTO por vaca |
| NS/P | DairyComp eventos | 12m | Total INSEMIN / Total PREÑADA |
| Tasa concepción | DairyComp eventos | 12m | PREÑADA / INSEMIN × 100 |
| Tasa aborto | DairyComp eventos | 12m | ABORTO / (PREÑADA+ABORTO) × 100 |
| Tasa mortandad | DairyComp eventos | 12m | MUERTA / vacas únicas × 100 |
| Tasa descarte | DairyComp eventos | 12m | VENDIDA / vacas únicas × 100 |
| Mastitis | DairyComp eventos | 12m | Vacas únicas con MAST / vacas únicas × 100 |

*Fuente bibliográfica de umbrales: Piccardi, Bruno, Córdoba, Masía, Balzarini (2019) — CONICET / Editorial Brujas.*
    """)
