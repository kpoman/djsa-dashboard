import datetime
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Tambo — DJSA", page_icon="🐄", layout="wide")

# ── URLs Google Sheets ──────────────────────────────────────────────────────
URL_PARTE_DIARIO = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vQKK0HtdtrMX7fT9X0ZdOhZ8LZwFKkPKi_NaGbZgSk1SeFq0kz5H2tK48ne-wN4_YUF7Vg3ViX70aMe"
    "/pub?output=xlsx"
)
URL_DATOS_CREA = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vTaYOZHAcL06SuvN7VPwASlZ4G5-w6zBn8G4ucjXZCtGvGYgfFBIvBGVUmIyWkfPMN4lTKW9yBOSzSa"
    "/pub?output=xlsx"
)
URL_ALIMENTACION = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vSfp0TxyH1dX_7GWU-waeQRqk9cs1ynSsPYq49g4tyIjXTRuQHODOOiLl69b2Zwlx-lB_bGor9Qotp1"
    "/pub?output=xlsx"
)

# ── Datos históricos embedidos (datos.py equivalente) ───────────────────────
_PROD = {
    '2015': "569\t23,60\n523\t22,43\n498\t24,30\n549\t21,59\n541\t24,14\n547\t23,44\n518\t25,31\n527\t24,09\n464\t26,68\n501\t25,79\n501\t23,54\n500\t22,19",
    '2016': "456\t22,46\n457\t18,07\n456\t19,94\n466\t21,58\n501\t21,67\n506\t21,28\n491\t20,59\n518\t20,00\n460\t25,15\n473\t24,54\n459\t24,14\n475\t20,65",
    '2017': "424\t23,20\n461\t17,18\n460\t19,32\n465\t17,92\n397\t21,77\n407\t20,99\n427\t23,74\n417\t26,15\n411\t25,71\n390\t26,58\n427\t23,59\n410\t24,11",
    '2018': "362\t25,01\n400\t19,30\n417\t22,75\n430\t23,84\n443\t24,91\n466\t23,16\n477\t24,71\n471\t26,84\n483\t28,01\n493\t28,34\n541\t25,39\n504\t27,79",
    '2019': "485\t26,75\n484\t25,99\n520\t25,50\n578\t26,08\n616\t28,42\n623\t28,27\n632\t29,30\n642\t30,20\n641\t29,36\n636\t31,60\n651\t29,27\n619\t29,37",
    '2020': "521\t30,68\n563\t25,37\n602\t26,30\n596\t27,54\n612\t28,37\n591\t29,92\n593\t29,70\n617\t30,3\n630\t31,6\n645\t32,4\n668\t30,9\n675\t29,29",
    '2021': "599\t29,64\n552\t29,11\n586\t28,76\n603\t27,51\n612\t26,50\n589\t27,16\n587\t27,21\n618\t27,34\n651\t28,19\n665\t28,21\n702\t26,85\n721\t24,10",
    '2022': "678\t22,39\n621\t21,74\n641\t22,69\n660\t21,60\n635\t25,09\n636\t27,00\n623\t29,61\n643\t30,08\n666\t31,24\n672\t31,34\n702\t30,99\n698\t29,63",
    '2023': "642\t29,70\n602\t25,17\n616\t26,88\n609\t27,25\n650\t28,06\n671\t29,00\n687\t32,23\n713\t34,17\n718\t33,78\n717\t34,54\n746\t31,71\n725\t30,43",
    '2024': "629\t29,71\n632\t26,12\n626\t26,58\n626\t28,09\n666\t27,47\n690\t29,12\n723\t29,96\n742\t29,94\n777\t31,18\n789\t31,37\n795\t31,63\n780\t31,22",
    '2025': "692\t30,94\n609\t29,54\n659\t28,97\n659\t31,86\n678\t31,79\n718\t32,73\n737\t32,61\n767\t34,08\n803\t34,48\n794\t32,73\n838\t31,25\n842\t29,77",
    '2026': "729\t29,63\n638\t28,57\n616\t28,03",
}


def _get_datos_prod():
    rows = []
    for anio_str, bloque in _PROD.items():
        anio = int(anio_str)
        for mes, linea in enumerate(bloque.split('\n'), start=1):
            partes = linea.split('\t')
            vo = int(partes[0])
            ltvo = float(partes[1].replace(',', '.'))
            rows.append({'Ano': anio, 'Mes': mes, 'VO': vo, 'LTVO': ltvo})
    df = pd.DataFrame(rows)
    df['Prod'] = df['VO'] * df['LTVO']
    df['Date'] = df.apply(lambda r: datetime.datetime(int(r.Ano), int(r.Mes), 1), axis=1)
    return df


# ── Carga datos remotos con caché ───────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner="Cargando parte diario...")
def _get_partediario():
    df_all = pd.read_excel(
        URL_PARTE_DIARIO,
        header=None,
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

    def _rodeo(nombre, df=df, dates=dates):
        if isinstance(nombre, list):
            mask = df['cat'].isin(nombre)
        else:
            mask = df['cat'] == nombre
        r = df[mask].assign(date=dates).copy()
        r['roll_ltvo'] = r['diaria_ltvo'].rolling(7).mean()
        return r

    df_r1 = _rodeo('R 1')
    df_r2 = _rodeo('R 2')
    df_r3 = _rodeo('R 3')
    df_r0 = _rodeo(['R.Cero', 'R4', 'R 4'])
    df_rodeos = pd.concat([df_r1, df_r2, df_r3, df_r0]).reset_index()
    df_rodeos = df_rodeos[df_rodeos['diaria_total'] > 0]

    df_total = df[df['cat'] == 'Total'].assign(date=dates).reset_index()
    df_total = df_total[df_total['diaria_total'] > 0]
    df_total['roll'] = df_total['diaria_total'].rolling(7).mean()
    df_total['ltvo_roll'] = df_total['diaria_ltvo'].rolling(7).mean()

    return {'rodeos': df_rodeos, 'total': df_total}


@st.cache_data(ttl=3600, show_spinner="Cargando datos CREA...")
def _get_datos_crea():
    df_raw = pd.read_excel(URL_DATOS_CREA, header=None, sheet_name=None)
    df_dc = df_raw['datos crea'].transpose()
    columns = df_dc.iloc[0][:35].to_list()
    columns[0] = 'Ano'
    columns[1] = 'Mes'
    df_clean = df_dc.drop(range(35, 49), axis=1)
    df_clean = df_clean.set_axis(columns, axis=1)
    df_clean.drop(0, axis=0, inplace=True)
    df_clean['Ano'] = df_clean['Ano'].ffill()
    df_clean['Ano'] = df_clean['Ano'].astype('Int64')
    df_clean.dropna(subset=['Mes'], inplace=True)
    df_clean['Mes'] = pd.to_datetime(df_clean['Mes'], errors='coerce')
    df_clean.dropna(subset=['Mes'], inplace=True)
    df_clean['Mes'] = df_clean['Mes'].apply(lambda x: x.month)
    df_clean = df_clean[df_clean['VT'] > 0]
    if df_clean.shape[1] > 33:
        df_clean.drop(df_clean.columns[33], axis=1, inplace=True)

    int_cols = [
        'Partos de vaca:', 'Partos de vaq.', 'Partos Totales', 'Partos Muertos',
        'VO', 'VS', 'VT', 'Muertes', 'Ventas', 'Bajas Adultas', 'Dias Lactancia',
        'Abortos', 'Hembras nacidas de VACAS', 'Hembras nacidas de VAQ',
        'Hembras nacidas', 'Muertes guachera', 'Muertes Recria',
        'Vendidas guachera', 'Vendidas Recria', 'Bajas guachera-Recria',
        'MACHOS NACIDOS',
    ]
    for c in int_cols:
        if c in df_clean.columns:
            df_clean[c] = pd.to_numeric(df_clean[c], errors='coerce').astype('Int64')
    if 'VO PROYECTADAS' in df_clean.columns:
        df_clean['VO PROYECTADAS'] = pd.to_numeric(df_clean['VO PROYECTADAS'], errors='coerce').fillna(0).astype(int)

    df_clean['Ano'] = df_clean['Ano'].astype(int)
    df_clean['Periodo'] = pd.to_datetime({'year': df_clean['Ano'], 'month': df_clean['Mes'], 'day': 1})

    # ── Variables derivadas (indicadores de gestión) ─────────────────────────
    def _spct(num_col, den_col):
        """Cociente num/den × 100, devuelve None si alguna columna falta."""
        if num_col not in df_clean.columns or den_col not in df_clean.columns:
            return None
        num = pd.to_numeric(df_clean[num_col], errors='coerce')
        den = pd.to_numeric(df_clean[den_col], errors='coerce').replace(0, np.nan)
        return (num / den * 100).round(2)

    _derived = [
        ('_pct_VO_VT',       'VO',               'VT'),
        ('_mort_perinatal',  'Partos Muertos',    'Partos Totales'),
        ('_mort_adultas',    'Muertes',           'VT'),
        ('_mort_guachera',   'Muertes guachera',  'Hembras nacidas'),
        ('_mort_recria',     'Muertes Recria',    'Hembras nacidas'),
        ('_pct_hembras',     'Hembras nacidas',   'Partos Totales'),
        ('_tasa_abortos',    'Abortos',           'VT'),
    ]
    for new_col, num_c, den_c in _derived:
        v = _spct(num_c, den_c)
        if v is not None:
            df_clean[new_col] = v

    # Tasa de parición ANUAL: suma móvil 12m de partos / VT promedio 12m × 100
    # La referencia INTA (82.7 %) es anual — no se puede comparar contra datos mensuales.
    if 'Partos Totales' in df_clean.columns and 'VT' in df_clean.columns:
        _partos = pd.to_numeric(df_clean['Partos Totales'], errors='coerce')
        _vt     = pd.to_numeric(df_clean['VT'],             errors='coerce')
        df_clean['_tasa_paricion'] = (
            (_partos.rolling(12, min_periods=6).sum() /
             _vt.rolling(12, min_periods=6).mean().replace(0, np.nan) * 100)
            .round(2)
        )

    return df_clean


@st.cache_data(show_spinner="Cargando DairyComp...")
def _get_dairycomp():
    import os
    base = os.path.join(os.path.dirname(__file__), '..', 'data')
    df_ev = pd.read_csv(
        os.path.join(base, 'eventos-202605.csv'),
        encoding='iso-8859-1', delimiter=';',
        parse_dates=['Fecha'], date_format='%d/%m/%y', dayfirst=True,
    )
    df_ev['Mes'] = df_ev['Fecha'].dt.month
    df_ev['Ano'] = df_ev['Fecha'].dt.year
    df_ev['Evento'] = df_ev['Evento'].str.strip()
    cols_drop = [c for c in ['Nota', 'R', 'T', 'B', 'Protocolos;', 'Tecnico'] if c in df_ev.columns]
    df_ev.drop(cols_drop, axis=1, inplace=True)
    salud = ['MAST', 'ABORTO', 'RENGA', 'MUERTA', 'RETPLAC', 'SECA', 'ENFERMA',
             'CAIDA', 'ANESTRO', 'HIPOCAL', 'VENDIDA', 'UBRE', 'DIARREA', 'UTERO']
    repro = ['INSEMIN', 'PROSTA', 'PARTO', 'PREÑADA', 'VACIA', 'SECA', 'CELO', 'RECHAZO']
    df_ev['Tipo'] = df_ev['Evento'].apply(
        lambda x: 'salud' if x in salud else ('repro' if x in repro else 'noclasif')
    )
    df_ctrl = pd.read_csv(
        os.path.join(base, 'control-202605.csv'),
        encoding='iso-8859-1', delimiter=';',
        parse_dates=['FechaCtr', 'FPART', 'FSECA'],
        date_format='%d/%m/%y', dayfirst=True,
    )
    df_ctrl = df_ctrl[df_ctrl['VALR'] > 0]
    return {'eventos': df_ev, 'controles': df_ctrl}


@st.cache_data(show_spinner="Cargando calidad de leche...")
def _get_calidad_leche():
    import os
    path = os.path.join(os.path.dirname(__file__), '..', 'data', 'calidad_leche.csv')
    df = pd.read_csv(path)
    df['fecha'] = pd.to_datetime(df['fecha'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['fecha'])
    # Limpiar outliers evidentes
    df = df[df['grasa_butirosa'].between(1, 7, inclusive='both') | df['grasa_butirosa'].isna()]
    df = df[df['proteina'].between(2.5, 5.0, inclusive='both') | df['proteina'].isna()]
    # Convertir a numérico
    for col in ['grasa_butirosa', 'solid_no_grasos', 'proteina', 'acidez', 'pH',
                'celulas_somaticas', 'recuento_ufc']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    # Sin dato de UFC o CS = 0 (no se registra cuando da negativo/normal)
    df['recuento_ufc']      = df['recuento_ufc'].fillna(0)
    df['celulas_somaticas'] = df['celulas_somaticas'].fillna(0)
    # Promedio diario (hay ~2 lecturas por día)
    df_dia = (df.groupby('fecha')
              .agg(
                  grasa=('grasa_butirosa', 'mean'),
                  proteina=('proteina', 'mean'),
                  sng=('solid_no_grasos', 'mean'),
                  ph=('pH', 'mean'),
                  cs=('celulas_somaticas', 'mean'),
                  ufc=('recuento_ufc', 'mean'),
              ).reset_index())
    df_dia = df_dia.sort_values('fecha')

    # ── Reindexar a un espine diario completo para que el rolling no
    #    "puentee" los meses faltantes (ene-2020, dic-2020, nov-2022, ene-2023).
    #    Los días sin datos quedan NaN y el rolling los ignora (min_periods=3).
    full_idx = pd.date_range(df_dia['fecha'].min(), df_dia['fecha'].max(), freq='D')
    df_dia = (df_dia.set_index('fecha')
                    .reindex(full_idx)
                    .rename_axis('fecha')
                    .reset_index())

    # Rolling 7 días para composición (sobre el espine diario)
    df_dia['grasa_r7']    = df_dia['grasa'].rolling(7, min_periods=3).mean()
    df_dia['proteina_r7'] = df_dia['proteina'].rolling(7, min_periods=3).mean()
    df_dia['sng_r7']      = df_dia['sng'].rolling(7, min_periods=3).mean()

    # ── Agregación mensual sobre espine de meses completo —
    #    meses sin datos quedan NaN → Plotly dibuja un corte, no une con línea recta.
    df_dia['mes'] = df_dia['fecha'].dt.to_period('M')
    df_mes_real = (df_dia.groupby('mes')
                   .agg(
                       grasa=('grasa', 'mean'),
                       proteina=('proteina', 'mean'),
                       sng=('sng', 'mean'),
                       cs=('cs', 'mean'),
                       ufc=('ufc', 'mean'),
                   ).reset_index())
    # Espine mensual completo entre primer y último mes con datos
    min_mes = df_mes_real['mes'].min()
    max_mes = df_mes_real['mes'].max()
    full_mes = pd.period_range(min_mes, max_mes, freq='M')
    df_mes = (df_mes_real.set_index('mes')
                         .reindex(full_mes)
                         .rename_axis('mes')
                         .reset_index())
    df_mes['fecha_mes'] = df_mes['mes'].dt.to_timestamp()
    return {'diario': df_dia, 'mensual': df_mes}


# ── UI ───────────────────────────────────────────────────────────────────────
st.title("🐄 Tambo")

tab_prod, tab_alim, tab_crea, tab_dairycomp = st.tabs([
    "Producción de leche", "Alimentación", "Datos CREA", "DairyComp"
])

# ── Tab Producción de leche ─────────────────────────────────────────────────
with tab_prod:
    sub_rec, sub_hist, sub_cal = st.tabs(["Reciente", "Histórico", "Calidad de leche"])

    with sub_rec:
        data_pd = _get_partediario()
        if data_pd is None:
            st.warning("No se pudo cargar el parte diario.")
        else:
            df_total = data_pd['total']
            df_rodeos = data_pd['rodeos']

            st.subheader("LTVO total (media móvil 7d)")
            fig1 = px.line(df_total, x='date', y='ltvo_roll',
                           labels={'date': 'Fecha', 'ltvo_roll': 'LTVO'})
            fig1.update_yaxes(range=[20, 35])
            st.plotly_chart(fig1, use_container_width=True)
            df_ltvo_dl = df_total[['date', 'diaria_ltvo']].rename(columns={'date': 'Fecha', 'diaria_ltvo': 'LTVO'})
            st.download_button("Descargar LTVO total (CSV)", df_ltvo_dl.to_csv(index=False).encode('utf-8'),
                               file_name='ltvo_total.csv', mime='text/csv', key='dl_ltvo')

            st.subheader("LTVO por rodeo (media móvil 7d)")
            fig2 = px.line(df_rodeos, x='date', y='roll_ltvo', color='cat',
                           labels={'date': 'Fecha', 'roll_ltvo': 'LTVO', 'cat': 'Rodeo'})
            st.plotly_chart(fig2, use_container_width=True)
            df_rodeo_dl = df_rodeos[['date', 'cat', 'diaria_ltvo']].rename(columns={'date': 'Fecha', 'cat': 'Rodeo', 'diaria_ltvo': 'LTVO'})
            st.download_button("Descargar LTVO por rodeo (CSV)", df_rodeo_dl.to_csv(index=False).encode('utf-8'),
                               file_name='ltvo_por_rodeo.csv', mime='text/csv', key='dl_rodeo')

            st.subheader("Producción diaria total (media móvil 7d)")
            fig3 = px.line(df_total, x='date', y='roll',
                           labels={'date': 'Fecha', 'roll': 'Litros diarios'})
            st.plotly_chart(fig3, use_container_width=True)
            df_prod_dl = df_total[['date', 'diaria_total']].rename(columns={'date': 'Fecha', 'diaria_total': 'Produccion_total'})
            st.download_button("Descargar producción diaria (CSV)", df_prod_dl.to_csv(index=False).encode('utf-8'),
                               file_name='produccion_diaria.csv', mime='text/csv', key='dl_prod')

    with sub_hist:
        df_hist = _get_datos_prod()
        st.subheader("Histórico producción + VO (2015–2025)")
        fig_h = go.Figure()
        fig_h.add_trace(go.Scatter(x=df_hist['Date'], y=df_hist['Prod'],
                                   name='Producción Total', yaxis='y1'))
        fig_h.add_trace(go.Scatter(x=df_hist['Date'], y=df_hist['VO'],
                                   name='VO', yaxis='y2'))
        fig_h.update_layout(
            yaxis=dict(title='Litros diarios estimados'),
            yaxis2=dict(title='Vacas Ordeñadas', overlaying='y', side='right'),
            legend=dict(x=0, y=1),
            height=500,
        )
        st.plotly_chart(fig_h, use_container_width=True)

        st.divider()
        st.subheader("Descomposición estacional")

        _var_options = {'LTVO': 'LTVO', 'VO': 'VO', 'Producción total (L/día)': 'Prod'}
        col_v, col_m, col_rng = st.columns([2, 2, 3])
        with col_v:
            var_label = st.selectbox("Variable", list(_var_options.keys()), key="decomp_var")
        with col_m:
            model_type = st.selectbox("Modelo", ["additive", "multiplicative"],
                                      format_func=lambda x: "Aditivo" if x == "additive" else "Multiplicativo",
                                      key="decomp_model")
        with col_rng:
            min_date = df_hist['Date'].min().date()
            max_date = df_hist['Date'].max().date()
            date_range = st.slider(
                "Período",
                min_value=min_date,
                max_value=max_date,
                value=(min_date, max_date),
                format="MMM YYYY",
                key="decomp_range",
            )

        col_name = _var_options[var_label]
        df_dec = (
            df_hist[(df_hist['Date'].dt.date >= date_range[0]) &
                    (df_hist['Date'].dt.date <= date_range[1])]
            .set_index('Date')[[col_name]]
            .asfreq('MS')
        )

        n_obs = len(df_dec)
        if n_obs < 24:
            st.warning("Se necesitan al menos 24 meses para descomponer la serie. Ampliá el rango de fechas.")
        else:
            from statsmodels.tsa.seasonal import seasonal_decompose

            result = seasonal_decompose(df_dec[col_name], model=model_type, period=12)

            components = [
                ("Observado", result.observed),
                ("Tendencia", result.trend),
                ("Estacionalidad", result.seasonal),
                ("Residuo", result.resid),
            ]

            for title, series in components:
                fig_comp = go.Figure()
                fig_comp.add_trace(go.Scatter(
                    x=series.index, y=series.values,
                    mode='lines',
                    line=dict(width=2),
                ))
                fig_comp.update_layout(
                    title=title,
                    height=220,
                    margin=dict(t=40, b=30, l=50, r=20),
                    yaxis_title=var_label,
                )
                st.plotly_chart(fig_comp, use_container_width=True)

    with sub_cal:
        try:
            cal = _get_calidad_leche()
            df_dia = cal['diario']
            df_mes = cal['mensual']

            # ── KPIs últimos 30 días ────────────────────────────────────────
            ultimos = df_dia[df_dia['fecha'] >= df_dia['fecha'].max() - pd.Timedelta(days=30)]
            cs_ult = ultimos['cs'].mean()
            ufc_ult = ultimos['ufc'].mean()
            gr_ult = ultimos['grasa'].mean()
            pr_ult = ultimos['proteina'].mean()

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("🧈 Grasa butirosa", f"{gr_ult:.2f} %" if pd.notna(gr_ult) else "—")
            k2.metric("🥛 Proteína", f"{pr_ult:.2f} %" if pd.notna(pr_ult) else "—")
            cs_label = f"{cs_ult/1000:.0f}k" if pd.notna(cs_ult) else "—"
            cs_color = "normal" if pd.isna(cs_ult) else ("normal" if cs_ult < 300_000 else "inverse")
            k3.metric("🔬 Cél. somáticas (prom. 30d)", cs_label, delta=None)
            ufc_label = f"{ufc_ult/1000:.0f}k UFC/mL" if pd.notna(ufc_ult) else "—"
            k4.metric("🦠 Recuento bacteriano (prom. 30d)", ufc_label, delta=None)

            st.divider()

            # ── Composición diaria — stacked area + UFC overlay ──────────────
            _c_hdr, _c_chk = st.columns([6, 1])
            _c_hdr.subheader("Composición de la leche (media móvil 7 días)")
            _comp_stacked = _c_chk.checkbox("Acumulado", value=False, key="comp_stacked")

            df_comp = df_dia[['fecha', 'grasa_r7', 'proteina_r7', 'sng_r7']].copy()
            df_comp['otros_r7'] = (df_comp['sng_r7'] - df_comp['proteina_r7']).clip(lower=0)
            df_comp = df_comp.dropna(subset=['grasa_r7', 'proteina_r7', 'otros_r7'])

            df_ufc = df_dia[df_dia['ufc'] > 0][['fecha', 'ufc']].copy()

            fig_comp = go.Figure()

            _comp_traces = [
                ('otros_r7',    'Otros sólidos (%)',  'rgba(90, 216, 166, 0.75)', 'rgba(90, 216, 166, 0.9)',  'Otros sólidos: %{y:.2f}%'),
                ('proteina_r7', 'Proteína (%)',        'rgba(91, 143, 249, 0.75)', 'rgba(91, 143, 249, 0.9)',  'Proteína: %{y:.2f}%'),
                ('grasa_r7',    'Grasa butirosa (%)',  'rgba(244, 165, 34, 0.75)', 'rgba(244, 165, 34, 0.9)',  'Grasa: %{y:.2f}%'),
            ]
            for col, name, fillcol, linecol, htmpl in _comp_traces:
                fig_comp.add_trace(go.Scatter(
                    x=df_comp['fecha'], y=df_comp[col],
                    name=name,
                    **(dict(stackgroup='comp', fillcolor=fillcol,
                            line=dict(color=linecol, width=0.5))
                       if _comp_stacked else
                       dict(line=dict(color=linecol, width=2))),
                    mode='lines',
                    hovertemplate=htmpl + '<extra></extra>',
                ))

            # UFC overlay — eje Y = UFC, tamaño del punto = células somáticas
            df_cs_raw = df_dia[df_dia['cs'] > 0][['fecha', 'cs']].copy()
            if not df_ufc.empty:
                # Cruzar UFC con CS por fecha (inner join — solo días con ambos valores)
                df_ufc_cs = df_ufc.merge(df_cs_raw, on='fecha', how='left')
                # Para días sin CS usar tamaño neutro; si hay CS, escalar
                cs_vals = df_ufc_cs['cs'].values
                cs_min = np.nanmin(cs_vals) if not np.all(np.isnan(cs_vals)) else 0
                cs_max = np.nanmax(cs_vals) if not np.all(np.isnan(cs_vals)) else 1
                marker_sizes = np.where(
                    np.isnan(cs_vals),
                    8,
                    7 + 28 * (cs_vals - cs_min) / max(cs_max - cs_min, 1)
                )
                hover_text = [
                    f"UFC: {u:,.0f}/mL<br>CS: {c:,.0f}" if not np.isnan(c)
                    else f"UFC: {u:,.0f}/mL<br>CS: sin dato"
                    for u, c in zip(df_ufc_cs['ufc'], cs_vals)
                ]
                fig_comp.add_trace(go.Scatter(
                    x=df_ufc_cs['fecha'],
                    y=df_ufc_cs['ufc'],
                    name='UFC/mL (eje der.)',
                    mode='markers',
                    yaxis='y2',
                    marker=dict(
                        size=marker_sizes,
                        color='rgba(210, 40, 40, 0.75)',
                        line=dict(color='darkred', width=1),
                    ),
                    text=hover_text,
                    hovertemplate='%{text}<extra></extra>',
                ))
                fig_comp.update_layout(
                    yaxis2=dict(
                        title='UFC/mL',
                        overlaying='y',
                        side='right',
                        showgrid=False,
                        rangemode='tozero',
                        tickformat='.0f',
                    )
                )

            fig_comp.update_layout(
                height=480,
                yaxis=dict(title='Composición (%)'),
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
                hovermode='x unified',
                margin=dict(t=60, r=80),
            )
            st.plotly_chart(fig_comp, use_container_width=True)

            st.divider()

            # ── Grasa × Producción ────────────────────────────────────────────
            st.subheader("Grasa butirosa vs Producción (LTVO)")
            st.caption("Relación entre % grasa, litros por vaca y kg de grasa producidos · datos mensuales")

            # LTVO mensual histórico desde _PROD
            df_prod_hist = _get_datos_prod()
            df_prod_hist['mes'] = df_prod_hist['Date'].dt.to_period('M')
            ltvo_mes = df_prod_hist[['mes', 'LTVO']].copy()

            # Grasa mensual ya viene en df_mes (con NaN en los meses faltantes)
            # Usamos left join: meses sin calidad quedan con grasa=NaN → kg_grasa=NaN
            # y los gráficos muestran un corte en esos puntos.
            grasa_mes = df_mes[['mes', 'grasa']].copy()

            # Join por mes
            df_gx = pd.merge(ltvo_mes, grasa_mes, on='mes', how='left')
            df_gx['fecha_mes'] = df_gx['mes'].dt.to_timestamp()
            df_gx['kg_grasa'] = (df_gx['LTVO'] * df_gx['grasa'] / 100).round(3)
            df_gx = df_gx.sort_values('fecha_mes')

            if not df_gx.empty:
                # Gráfico 1: LTVO + % Grasa (doble eje)
                fig_gx = go.Figure()
                fig_gx.add_trace(go.Scatter(
                    x=df_gx['fecha_mes'], y=df_gx['LTVO'],
                    name='LTVO (L/vc/día)', mode='lines+markers',
                    line=dict(color='#5b8ff9', width=2),
                    marker=dict(size=5),
                    hovertemplate='LTVO: %{y:.1f} L<extra></extra>',
                ))
                fig_gx.add_trace(go.Scatter(
                    x=df_gx['fecha_mes'], y=df_gx['grasa'],
                    name='Grasa (%)', mode='lines+markers',
                    yaxis='y2',
                    line=dict(color='#f4a522', width=2),
                    marker=dict(size=5),
                    hovertemplate='Grasa: %{y:.2f}%<extra></extra>',
                ))
                fig_gx.update_layout(
                    height=400,
                    yaxis=dict(title='LTVO (L/vc/día)', rangemode='tozero'),
                    yaxis2=dict(title='Grasa (%)', overlaying='y', side='right',
                                showgrid=False, range=[2.5, 4.5]),
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
                    hovermode='x unified',
                    margin=dict(t=50, r=70),
                )
                st.plotly_chart(fig_gx, use_container_width=True)

                # Gráfico 2: kg grasa/vaca/día
                fig_kg = go.Figure()
                fig_kg.add_trace(go.Scatter(
                    x=df_gx['fecha_mes'], y=df_gx['kg_grasa'],
                    name='kg grasa/vaca/día',
                    mode='lines+markers',
                    fill='tozeroy',
                    fillcolor='rgba(244, 165, 34, 0.15)',
                    line=dict(color='#f4a522', width=2),
                    marker=dict(size=5),
                    hovertemplate='%{x|%b %Y}<br>kg grasa: %{y:.3f} kg/vc/día<extra></extra>',
                ))
                fig_kg.update_layout(
                    height=300,
                    title='kg grasa / vaca / día = LTVO × % grasa',
                    yaxis=dict(title='kg grasa/vc/día', rangemode='tozero'),
                    hovermode='x unified',
                    margin=dict(t=50),
                )
                st.plotly_chart(fig_kg, use_container_width=True)

                # Gráfico 3: scatter LTVO vs % grasa (efecto dilución)
                st.subheader("Efecto dilución: LTVO vs % Grasa")
                st.caption("A mayor producción de leche, la grasa tiende a diluirse (relación inversa)")
                df_sc = df_gx.dropna(subset=['LTVO', 'grasa'])  # excluir meses sin calidad
                fig_sc = go.Figure()
                fig_sc.add_trace(go.Scatter(
                    x=df_sc['LTVO'], y=df_sc['grasa'],
                    mode='markers+text',
                    text=df_sc['fecha_mes'].dt.strftime('%b %y'),
                    textposition='top center',
                    textfont=dict(size=8),
                    marker=dict(
                        size=10,
                        color=df_sc['fecha_mes'].astype(np.int64),
                        colorscale='Viridis',
                        showscale=True,
                        colorbar=dict(title='Tiempo', tickvals=[], ticktext=[]),
                    ),
                    hovertemplate='%{text}<br>LTVO: %{x:.1f} L<br>Grasa: %{y:.2f}%<extra></extra>',
                ))
                # Línea de tendencia (solo con puntos reales)
                if len(df_sc) >= 3:
                    z = np.polyfit(df_sc['LTVO'], df_sc['grasa'], 1)
                    x_line = np.linspace(df_sc['LTVO'].min(), df_sc['LTVO'].max(), 50)
                    y_line = np.polyval(z, x_line)
                    fig_sc.add_trace(go.Scatter(
                        x=x_line, y=y_line,
                        mode='lines', name='Tendencia',
                        line=dict(color='red', width=1.5, dash='dash'),
                        hoverinfo='skip',
                    ))
                    corr = df_sc['LTVO'].corr(df_sc['grasa'])
                    st.caption(f"Correlación LTVO ↔ Grasa: **{corr:.2f}** "
                               f"({'inversa esperada ✓' if corr < 0 else 'positiva — revisar'})")
                fig_sc.update_layout(
                    height=380,
                    xaxis=dict(title='LTVO (L/vc/día)'),
                    yaxis=dict(title='Grasa (%)'),
                    showlegend=False,
                    margin=dict(t=30),
                )
                st.plotly_chart(fig_sc, use_container_width=True)

                # Descarga
                st.download_button(
                    "⬇️ Descargar grasa × producción (CSV)",
                    df_gx[['fecha_mes', 'LTVO', 'grasa', 'kg_grasa']].to_csv(index=False).encode('utf-8'),
                    file_name='grasa_vs_ltvo.csv', mime='text/csv', key='dl_gxprod',
                )

            st.divider()

            # ── Sanidad — Células somáticas ───────────────────────────────────
            st.subheader("Sanidad — Células somáticas")
            st.caption("Solo se registran en determinadas fechas (≈23% de los días)")

            df_cs = df_dia[df_dia['cs'] > 0][['fecha', 'cs']].copy()

            if not df_cs.empty:
                df_cs['Categoría'] = pd.cut(
                    df_cs['cs'],
                    bins=[0, 200_000, 400_000, float('inf')],
                    labels=['< 200k (excelente)', '200-400k (aceptable)', '> 400k (alerta)']
                )
                fig_cs = px.scatter(
                    df_cs, x='fecha', y='cs',
                    color='Categoría',
                    color_discrete_map={
                        '< 200k (excelente)': '#52c41a',
                        '200-400k (aceptable)': '#faad14',
                        '> 400k (alerta)': '#f5222d',
                    },
                    labels={'fecha': '', 'cs': 'Células somáticas'},
                    title='Células somáticas (CS)',
                    height=360,
                )
                if not df_mes.empty:
                    df_cs_mes = df_mes[df_mes['cs'].notna()][['fecha_mes', 'cs']]
                    fig_cs.add_trace(go.Scatter(
                        x=df_cs_mes['fecha_mes'], y=df_cs_mes['cs'],
                        mode='lines', name='Media mensual',
                        line=dict(color='black', width=2, dash='dot'),
                    ))
                fig_cs.add_hline(y=400_000, line_dash='dash', line_color='red',
                                 annotation_text='Umbral 400k', annotation_position='top left')
                fig_cs.update_yaxes(tickformat='.0f')
                st.plotly_chart(fig_cs, use_container_width=True)

            st.divider()
            st.download_button(
                "⬇️ Descargar datos calidad (CSV)",
                df_dia[['fecha','grasa','proteina','sng','ph','cs','ufc']].to_csv(index=False).encode('utf-8'),
                file_name='calidad_leche_diario.csv',
                mime='text/csv',
                key='dl_calidad',
            )

        except Exception as e:
            st.error(f"Error cargando calidad de leche: {e}")
            import traceback; st.code(traceback.format_exc())


# ── Tab Alimentación ────────────────────────────────────────────────────────
with tab_alim:
    try:
        @st.cache_data(show_spinner="Cargando tipo de cambio USD/ARS...")
        def _get_tc():
            import os
            path = os.path.join(os.path.dirname(__file__), '..', 'data', 'usdars.csv')
            df_tc = pd.read_csv(path, encoding='utf-8-sig')
            df_tc['Fecha'] = pd.to_datetime(df_tc['Fecha'].str.strip().str.strip('"'), format='%d.%m.%Y')
            # Parsear "Último" que viene como "1.395,24" (punto miles, coma decimal)
            df_tc['TC'] = (
                df_tc['Último'].astype(str).str.strip().str.strip('"')
                .str.replace('.', '', regex=False)
                .str.replace(',', '.', regex=False)
                .astype(float)
            )
            df_tc = df_tc[['Fecha', 'TC']]
            df_tc = df_tc.sort_values('Fecha').set_index('Fecha')
            df_tc = df_tc.resample('D').ffill()
            return df_tc

        @st.cache_data(ttl=3600, show_spinner="Cargando datos de alimentación...")
        def _get_alimentacion():
            sheets = pd.read_excel(URL_ALIMENTACION, sheet_name=None)
            df_d = sheets['Dietas'].copy()
            df_p = sheets['Produccion'].copy()
            df_d['Fecha'] = pd.to_datetime(df_d['Fecha'])
            df_p['Fecha'] = pd.to_datetime(df_p['Fecha'])
            rodeo_cols = [c for c in df_d.columns if c not in ['Fecha', 'Nombre', 'Precio ($)', 'Unidad']]
            return df_d, df_p, rodeo_cols

        df_tc = _get_tc()
        df_dietas, df_produccion, rodeo_cols_dieta = _get_alimentacion()

        # Agregar TC a dietas y produccion por fecha
        df_dietas = df_dietas.merge(df_tc, left_on='Fecha', right_index=True, how='left')
        df_dietas['Precio (U$D)'] = df_dietas['Precio ($)'] / df_dietas['TC']
        df_produccion = df_produccion.merge(df_tc, left_on='Fecha', right_index=True, how='left')
        df_produccion['Precio_USD'] = df_produccion['Precio'] / df_produccion['TC']

        # Rodeos que están en ambas tablas
        rodeos_prod = sorted(df_produccion['Rodeo'].unique())
        rodeos_comunes = [r for r in rodeo_cols_dieta if r in rodeos_prod]
        rodeos_solo_prod = [r for r in rodeos_prod if r not in rodeo_cols_dieta]

        fechas_comunes = sorted(set(df_dietas['Fecha'].unique()) & set(df_produccion['Fecha'].unique()))

        # ── Calcular costos por fecha y rodeo (en USD) ────────────────
        registros = []
        for fecha in fechas_comunes:
            d_f = df_dietas[df_dietas['Fecha'] == fecha]
            p_f = df_produccion[df_produccion['Fecha'] == fecha]
            precio_leche_usd = p_f['Precio_USD'].iloc[0] if (not p_f.empty and 'Precio_USD' in p_f.columns) else 0

            for rodeo in rodeo_cols_dieta:
                costo_vaca_dia = 0
                composicion = {}
                for _, row in d_f.iterrows():
                    precio_usd = row.get('Precio (U$D)', None)
                    kg = row[rodeo]
                    if pd.notna(precio_usd) and pd.notna(kg) and kg > 0:
                        costo_item = precio_usd * kg
                        costo_vaca_dia += costo_item
                        composicion[row['Nombre']] = {'kg': kg, 'costo': costo_item}

                if costo_vaca_dia == 0:
                    continue

                p_rod = p_f[p_f['Rodeo'] == rodeo]
                vacas = p_rod['Vacas'].sum() if not p_rod.empty else 0
                litros = p_rod['Litros'].sum() if not p_rod.empty else 0

                costo_total = costo_vaca_dia * vacas if vacas > 0 else 0
                ingreso = litros * precio_leche_usd
                litros_equiv = costo_total / precio_leche_usd if precio_leche_usd > 0 else 0
                litros_libres = litros - litros_equiv
                ltvo = litros / vacas if vacas > 0 else 0
                costo_por_litro = costo_vaca_dia / ltvo if ltvo > 0 else 0

                registros.append({
                    'Fecha': fecha,
                    'Rodeo': rodeo,
                    'Vacas': vacas,
                    'Litros': litros,
                    'LTVO': round(ltvo, 1),
                    'Precio_leche_USD': round(precio_leche_usd, 3),
                    'Costo_vaca_dia_USD': round(costo_vaca_dia, 2),
                    'Costo_total_USD': round(costo_total, 0),
                    'Ingreso_USD': round(ingreso, 0),
                    'Litros_equiv_costo': round(litros_equiv, 0),
                    'Litros_libres': round(litros_libres, 0),
                    'Pct_litros_libres': round(litros_libres / litros * 100, 1) if litros > 0 else 0,
                    'Costo_por_litro_USD': round(costo_por_litro, 3),
                })

                for alim, vals in composicion.items():
                    registros[-1][f'kg_{alim}'] = vals['kg']
                    registros[-1][f'USD_{alim}'] = round(vals['costo'], 2)

        df_costos = pd.DataFrame(registros)

        # ── Filtros ─────────────────────────────────────────────────────
        col_rod, col_fecha = st.columns([2, 3])
        with col_rod:
            rodeos_disp = sorted(df_costos['Rodeo'].unique())
            sel_rodeos = st.multiselect("Rodeo(s)", rodeos_disp, default=rodeos_disp, key="alim_rodeos")
        with col_fecha:
            fecha_min = df_costos['Fecha'].min().date()
            fecha_max = df_costos['Fecha'].max().date()
            rango = st.slider("Período", min_value=fecha_min, max_value=fecha_max,
                              value=(fecha_min, fecha_max), format="DD/MM/YY", key="alim_rango")

        df_vis = df_costos[
            (df_costos['Rodeo'].isin(sel_rodeos)) &
            (df_costos['Fecha'].dt.date >= rango[0]) &
            (df_costos['Fecha'].dt.date <= rango[1])
        ].copy()

        if df_vis.empty:
            st.warning("No hay datos con los filtros seleccionados.")
        else:
            # ── KPIs última fecha ───────────────────────────────────────
            ult = df_vis[df_vis['Fecha'] == df_vis['Fecha'].max()]
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Costo/vaca/día (media)", f"U$D {ult['Costo_vaca_dia_USD'].mean():,.2f}")
            k2.metric("Litros libres totales", f"{ult['Litros_libres'].sum():,.0f} L")
            k3.metric("% Litros libres", f"{ult['Pct_litros_libres'].mean():.0f}%")
            k4.metric("Costo/litro (media)", f"U$D {ult['Costo_por_litro_USD'].mean():,.3f}")

            sub_efic, sub_comp, sub_evol, sub_datos = st.tabs([
                "Eficiencia", "Composición dieta", "Evolución costos", "Datos"
            ])

            # ── Tab Eficiencia (Litros Libres) ──────────────────────────
            with sub_efic:
                modo_ll = st.radio(
                    "Ver litros libres", ["Total del rodeo", "Por animal (÷ vacas)"],
                    horizontal=True, key="modo_litros_libres"
                )

                df_ll = df_vis.sort_values(['Fecha', 'Rodeo']).copy()
                if modo_ll == "Por animal (÷ vacas)":
                    df_ll['Litros_libres_plot'] = (df_ll['Litros_libres'] / df_ll['Vacas'].replace(0, np.nan)).round(1)
                    ylabel = 'Litros libres / vaca'
                    titulo = 'Litros libres por vaca por rodeo'
                else:
                    df_ll['Litros_libres_plot'] = df_ll['Litros_libres']
                    ylabel = 'Litros libres totales'
                    titulo = 'Litros libres totales por rodeo'

                fig_ll = px.area(
                    df_ll, x='Fecha', y='Litros_libres_plot', color='Rodeo',
                    title=titulo,
                    labels={'Litros_libres_plot': ylabel, 'Fecha': ''},
                )
                fig_ll.update_layout(height=450)
                st.plotly_chart(fig_ll, use_container_width=True)

                st.subheader("% Litros libres sobre producción")
                fig_pct = px.line(
                    df_vis, x='Fecha', y='Pct_litros_libres', color='Rodeo',
                    markers=True,
                    title='% de litros libres (mayor = más eficiente)',
                    labels={'Pct_litros_libres': '% Litros libres', 'Fecha': ''},
                )
                fig_pct.update_layout(height=400)
                st.plotly_chart(fig_pct, use_container_width=True)

                st.subheader("Costo por litro de leche producido (U$D)")
                fig_cpl = px.line(
                    df_vis, x='Fecha', y='Costo_por_litro_USD', color='Rodeo',
                    markers=True,
                    title='Costo alimentación por litro en U$D (menor = más eficiente)',
                    labels={'Costo_por_litro_USD': 'U$D/litro', 'Fecha': ''},
                )
                fig_cpl.update_layout(height=400)
                st.plotly_chart(fig_cpl, use_container_width=True)

            # ── Tab Composición ─────────────────────────────────────────
            with sub_comp:
                alimentos = sorted(df_dietas['Nombre'].dropna().unique())
                kg_cols = [f'kg_{a}' for a in alimentos if f'kg_{a}' in df_vis.columns]
                costo_cols = [f'$_{a}' for a in alimentos if f'$_{a}' in df_vis.columns]

                rod_comp = st.selectbox("Rodeo", sel_rodeos, key="comp_rodeo")
                df_rod = df_vis[df_vis['Rodeo'] == rod_comp]

                st.subheader(f"Composición de la dieta — {rod_comp} (kg/vaca/día)")
                # Melt kg columns
                kg_present = [c for c in kg_cols if df_rod[c].notna().any()]
                if kg_present:
                    df_kg = df_rod[['Fecha'] + kg_present].melt(id_vars='Fecha', var_name='Alimento', value_name='kg')
                    df_kg['Alimento'] = df_kg['Alimento'].str.replace('kg_', '')
                    df_kg = df_kg.dropna(subset=['kg'])
                    fig_kg = px.area(
                        df_kg, x='Fecha', y='kg', color='Alimento',
                        title=f'Dieta {rod_comp} — kg/vaca/día por alimento',
                        labels={'kg': 'kg/vaca/día', 'Fecha': ''},
                    )
                    fig_kg.update_layout(height=450)
                    st.plotly_chart(fig_kg, use_container_width=True)

                st.subheader(f"Composición del costo — {rod_comp} (U$D/vaca/día)")
                costo_cols_usd = [f'USD_{a}' for a in alimentos if f'USD_{a}' in df_vis.columns]
                costo_present = [c for c in costo_cols_usd if df_rod[c].notna().any()]
                if costo_present:
                    df_cst = df_rod[['Fecha'] + costo_present].melt(id_vars='Fecha', var_name='Alimento', value_name='Costo')
                    df_cst['Alimento'] = df_cst['Alimento'].str.replace(r'^USD_', '', regex=True)
                    df_cst = df_cst.dropna(subset=['Costo'])
                    fig_cst = px.area(
                        df_cst, x='Fecha', y='Costo', color='Alimento',
                        title=f'Costo dieta {rod_comp} — U$D/vaca/día por alimento',
                        labels={'Costo': 'U$D/vaca/día', 'Fecha': ''},
                    )
                    fig_cst.update_layout(height=450)
                    st.plotly_chart(fig_cst, use_container_width=True)

                # Pie de última fecha
                ult_rod = df_rod[df_rod['Fecha'] == df_rod['Fecha'].max()]
                if not ult_rod.empty and costo_present:
                    vals = {c.replace('USD_', ''): ult_rod.iloc[0][c] for c in costo_present if pd.notna(ult_rod.iloc[0][c]) and ult_rod.iloc[0][c] > 0}
                    if vals:
                        fig_pie = px.pie(
                            names=list(vals.keys()), values=list(vals.values()),
                            title=f'Composición costo última fecha ({ult_rod.iloc[0]["Fecha"].strftime("%d/%m/%Y")})',
                        )
                        st.plotly_chart(fig_pie, use_container_width=True)

            # ── Tab Evolución costos ────────────────────────────────────
            with sub_evol:
                st.subheader("Costo total alimentación por rodeo (U$D)")
                fig_cvd = px.area(
                    df_vis.sort_values(['Fecha', 'Rodeo']),
                    x='Fecha', y='Costo_total_USD', color='Rodeo',
                    title='Costo total alimentación por rodeo (U$D, stacked)',
                    labels={'Costo_total_USD': 'U$D/día total rodeo', 'Fecha': ''},
                )
                fig_cvd.update_layout(height=450)
                st.plotly_chart(fig_cvd, use_container_width=True)

                st.subheader("Costo por vaca por día (U$D)")
                fig_cvd2 = px.area(
                    df_vis.sort_values(['Fecha', 'Rodeo']),
                    x='Fecha', y='Costo_vaca_dia_USD', color='Rodeo',
                    title='Costo alimentación por vaca/día (U$D, stacked)',
                    labels={'Costo_vaca_dia_USD': 'U$D/vaca/día', 'Fecha': ''},
                )
                fig_cvd2.update_layout(height=450)
                st.plotly_chart(fig_cvd2, use_container_width=True)

                st.subheader("Precio de la leche vs Costo alimentación (U$D/litro)")
                df_total = df_vis.groupby('Fecha').agg(
                    Costo_medio=('Costo_vaca_dia_USD', 'mean'),
                    Precio_leche=('Precio_leche_USD', 'first'),
                    LTVO_medio=('LTVO', 'mean'),
                ).reset_index()
                df_total['Costo_por_litro'] = df_total['Costo_medio'] / df_total['LTVO_medio']
                fig_pvsc = go.Figure()
                fig_pvsc.add_trace(go.Scatter(x=df_total['Fecha'], y=df_total['Precio_leche'],
                                              name='Precio leche (U$D/L)', mode='lines+markers'))
                fig_pvsc.add_trace(go.Scatter(x=df_total['Fecha'], y=df_total['Costo_por_litro'],
                                              name='Costo alim. (U$D/L)', mode='lines+markers'))
                fig_pvsc.update_layout(title='Precio leche vs Costo alimentación por litro (U$D)',
                                       yaxis_title='U$D/litro', height=400)
                st.plotly_chart(fig_pvsc, use_container_width=True)

                st.subheader("Evolución del precio de alimentos (U$D)")
                precios_evol = df_dietas[df_dietas['Precio (U$D)'].notna()].copy()
                fig_pa = px.line(
                    precios_evol, x='Fecha', y='Precio (U$D)', color='Nombre',
                    markers=True, title='Precio de alimentos en U$D',
                    labels={'Precio (U$D)': 'U$D/unidad', 'Fecha': ''},
                )
                fig_pa.update_layout(height=450)
                st.plotly_chart(fig_pa, use_container_width=True)

            # ── Tab Datos ───────────────────────────────────────────────
            with sub_datos:
                cols_show = ['Fecha', 'Rodeo', 'Vacas', 'Litros', 'LTVO', 'Precio_leche_USD',
                             'Costo_vaca_dia_USD', 'Litros_equiv_costo', 'Litros_libres',
                             'Pct_litros_libres', 'Costo_por_litro_USD']
                st.dataframe(df_vis[cols_show].sort_values(['Fecha', 'Rodeo'], ascending=[False, True]),
                             use_container_width=True, hide_index=True)
                csv = df_vis.to_csv(index=False).encode('utf-8')
                st.download_button("Descargar datos (CSV)", csv,
                                   file_name='alimentacion_costos.csv', mime='text/csv')

    except Exception as e:
        st.error(f"Error cargando datos de alimentación: {e}")


# ── Tab Datos CREA ──────────────────────────────────────────────────────────
with tab_crea:
    try:
        df_crea = _get_datos_crea()
        cols_numericas = [c for c in df_crea.columns
                          if c not in ('Ano', 'Mes', 'Periodo') and
                          pd.api.types.is_numeric_dtype(df_crea[c])]

        _COLORS = ['#f4a522', '#5b8ff9', '#5ad8a6', '#ff6b6b',
                   '#c050e8', '#ff9f40', '#00c0c7', '#e8825a']
        MESES_STR = ['Ene','Feb','Mar','Abr','May','Jun',
                     'Jul','Ago','Sep','Oct','Nov','Dic']

        # ── KPIs del mes más reciente ────────────────────────────────────────
        # Definición: (col, label, unit, meta_lo, meta_hi, dir, referencia)
        # dir: 'up' = mayor es mejor, 'down' = menor es mejor, None = rango óptimo
        _KPI_DEFS = [
            ('_pct_VO_VT',      '% VO/VT',           '%',   75,  None, 'up',
             'Meta ≥75 % · INTA EEA Rafaela'),
            ('Dias Lactancia',  'Días en lactancia',  'd',  150,   175, None,
             'Meta 150–175 d · Piccardi (2014) CONICET, 291 tambos SF+Córdoba'),
            ('_tasa_paricion',  'Tasa parición',      '%',   80,  None, 'up',
             'Meta ≥80 % · INTA Enc. Lechera 2018–19: media 82.7 %'),
            ('_mort_perinatal', 'Mort. perinatal',    '%',  None,   5, 'down',
             'Meta <5 % · Piccardi (2014) CONICET'),
            ('_mort_adultas',   'Mort. adultas',      '%',  None, 5.7, 'down',
             'Meta <5.7 % · INTA Enc. Lechera 2018–19: media 5.7 %'),
            ('_mort_guachera',  'Mort. guachera',     '%',  None,  10, 'down',
             'Meta <10 % · INTA Enc. Lechera 2018–19: media 10.3 %'),
            ('_tasa_abortos',   'Tasa abortos',       '%',  None,   3, 'down',
             'Meta <3 % · referencia de manejo'),
            ('_pct_hembras',    '% hembras nacidas',  '%',   47,  53, None,
             'Esperado 48–52 % (50 % biológico esperado)'),
        ]

        ult_per = df_crea['Periodo'].max()
        row_ult = df_crea[df_crea['Periodo'] == ult_per]
        row_pen = df_crea[df_crea['Periodo'] < ult_per].sort_values('Periodo').tail(1)

        kpis_visibles = [
            kd for kd in _KPI_DEFS
            if kd[0] in df_crea.columns
            and not row_ult[kd[0]].isna().all()
        ]

        if kpis_visibles and not row_ult.empty:
            st.subheader(f"Indicadores clave — {ult_per.strftime('%b %Y')}")
            st.caption(
                "Comparación con mes anterior · "
                "🟢 dentro del objetivo · 🔴 fuera del objetivo · ⚪ sin meta definida"
            )
            n_cols = 4
            grid = [kpis_visibles[i:i + n_cols] for i in range(0, len(kpis_visibles), n_cols)]
            for fila in grid:
                cols_kpi = st.columns(n_cols)
                for j, (col, label, unit, meta_lo, meta_hi, direction, ref) in enumerate(fila):
                    val_raw  = row_ult[col].values[0]
                    val      = float(val_raw)  if not pd.isna(val_raw) else None
                    prev_raw = row_pen[col].values[0] if not row_pen.empty else None
                    val_prev = float(prev_raw) if (prev_raw is not None and not pd.isna(prev_raw)) else None

                    if val is None:
                        continue

                    # Estado semáforo
                    if direction == 'up' and meta_lo is not None:
                        good = val >= meta_lo
                    elif direction == 'down' and meta_hi is not None:
                        good = val <= meta_hi
                    elif meta_lo is not None and meta_hi is not None:
                        good = meta_lo <= val <= meta_hi
                    else:
                        good = None
                    icon = '🟢' if good is True else ('🔴' if good is False else '⚪')

                    delta_str = (
                        f"{val - val_prev:+.1f} {unit}"
                        if val_prev is not None else None
                    )

                    with cols_kpi[j]:
                        st.metric(
                            f"{icon} {label}",
                            f"{val:.1f} {unit}",
                            delta=delta_str,
                        )
                        st.caption(f"📚 {ref}")

            st.divider()

        sub_exp, sub_seas, sub_tend = st.tabs([
            "🔍 Explorador", "📅 Estacionalidad", "📈 Tendencia"
        ])

        # ── Explorador: multi-variable con ejes independientes ───────────────
        with sub_exp:
            st.caption(
                "Superponé hasta 4 variables. Con 1–2 variables se usan ejes "
                "independientes izquierda/derecha. Con 3–4, o activando "
                "**Normalizar**, todas van a la misma escala 0–100 %."
            )
            c1, c2, c3 = st.columns([4, 1, 2])
            with c1:
                vars_sel = st.multiselect(
                    "Variables", cols_numericas,
                    default=[v for v in ['VT', 'LTVO'] if v in cols_numericas]
                             or cols_numericas[:2],
                    key='crea_vars',
                )
            with c2:
                normalizar = st.checkbox("Normalizar\n(0–100)", value=False,
                                         key='crea_norm')
            with c3:
                anos_disp_e = sorted(df_crea['Ano'].unique())
                rango_anos = st.select_slider(
                    "Período",
                    options=anos_disp_e,
                    value=(anos_disp_e[0], anos_disp_e[-1]),
                    key='crea_rango',
                )

            vars_sel = vars_sel[:4]  # tope de 4
            forzar_norm = normalizar or len(vars_sel) > 2

            if not vars_sel:
                st.info("Seleccioná al menos una variable.")
            else:
                df_f = df_crea[
                    df_crea['Ano'].between(rango_anos[0], rango_anos[1])
                ].copy()

                fig_exp = go.Figure()

                for i, var in enumerate(vars_sel):
                    serie = df_f.set_index('Periodo')[var].dropna()
                    color = _COLORS[i % len(_COLORS)]

                    if forzar_norm:
                        mn, mx = serie.min(), serie.max()
                        y_vals = ((serie - mn) / (mx - mn) * 100
                                  if mx > mn else serie * 0 + 50)
                        yref = 'y'
                        htmpl = f'{var}: %{{y:.1f}} % norm<extra></extra>'
                    else:
                        y_vals = serie
                        yref = 'y' if i == 0 else 'y2'
                        htmpl = f'{var}: %{{y:.2f}}<extra></extra>'

                    fig_exp.add_trace(go.Scatter(
                        x=serie.index, y=y_vals,
                        name=var, yaxis=yref,
                        line=dict(color=color, width=2),
                        hovertemplate=htmpl,
                        mode='lines',
                    ))

                layout_exp = dict(
                    height=430,
                    hovermode='x unified',
                    legend=dict(orientation='h', yanchor='bottom',
                                y=1.02, xanchor='left', x=0),
                    margin=dict(t=50, r=70 if not forzar_norm
                                and len(vars_sel) == 2 else 20),
                )
                if forzar_norm:
                    layout_exp['yaxis'] = dict(title='% normalizado',
                                               range=[-5, 105])
                elif len(vars_sel) == 2:
                    layout_exp['yaxis']  = dict(
                        title=dict(text=vars_sel[0],
                                   font=dict(color=_COLORS[0])),
                        tickfont=dict(color=_COLORS[0]),
                    )
                    layout_exp['yaxis2'] = dict(
                        title=dict(text=vars_sel[1],
                                   font=dict(color=_COLORS[1])),
                        tickfont=dict(color=_COLORS[1]),
                        overlaying='y', side='right',
                        showgrid=False,
                    )
                else:
                    layout_exp['yaxis'] = dict(title=vars_sel[0])

                fig_exp.update_layout(**layout_exp)
                st.plotly_chart(fig_exp, use_container_width=True,
                                key='crea_exp_chart')

        # ── Estacionalidad ───────────────────────────────────────────────────
        with sub_seas:
            st.caption(
                "**Box por mes**: distribución histórica de cada mes (todos los años). "
                "**Años superpuestos**: cada año como una línea ene→dic para ver patrones estacionales."
            )
            c1, c2 = st.columns([2, 2])
            with c1:
                var_seas = st.selectbox(
                    "Variable", cols_numericas,
                    index=cols_numericas.index('VT') if 'VT' in cols_numericas else 0,
                    key='crea_seas_var',
                )
            with c2:
                modo_seas = st.radio(
                    "Modo", ["Box por mes", "Años superpuestos"],
                    horizontal=True, key='crea_seas_modo',
                )

            df_s = df_crea[['Ano', 'Mes', var_seas]].dropna(subset=[var_seas])

            if modo_seas == "Box por mes":
                fig_seas = go.Figure()
                for m in range(1, 13):
                    vals = df_s[df_s['Mes'] == m][var_seas]
                    fig_seas.add_trace(go.Box(
                        y=vals, name=MESES_STR[m - 1],
                        marker_color='#5b8ff9',
                        boxmean='sd',
                        showlegend=False,
                    ))
                fig_seas.update_layout(
                    height=400, yaxis_title=var_seas,
                    margin=dict(t=20),
                )
            else:
                fig_seas = go.Figure()
                SEAS_COL = px.colors.qualitative.Set2
                for i, ano in enumerate(sorted(df_s['Ano'].unique())):
                    df_ano = df_s[df_s['Ano'] == ano].sort_values('Mes')
                    fig_seas.add_trace(go.Scatter(
                        x=df_ano['Mes'], y=df_ano[var_seas],
                        name=str(int(ano)),
                        mode='lines+markers',
                        line=dict(width=1.8, color=SEAS_COL[i % len(SEAS_COL)]),
                        marker=dict(size=5),
                    ))
                fig_seas.update_layout(
                    height=400,
                    xaxis=dict(
                        tickmode='array',
                        tickvals=list(range(1, 13)),
                        ticktext=MESES_STR,
                        title='Mes',
                    ),
                    yaxis_title=var_seas,
                    hovermode='x unified',
                    legend=dict(orientation='h', yanchor='bottom',
                                y=1.02, xanchor='left', x=0),
                    margin=dict(t=40),
                )

            st.plotly_chart(fig_seas, use_container_width=True, key='crea_seas_chart')

        # ── Tendencia ────────────────────────────────────────────────────────
        with sub_tend:
            st.caption(
                "Serie original más media móvil centrada. "
                "Ajustá la ventana para ver tendencias de corto o largo plazo."
            )
            c1, c2 = st.columns([2, 2])
            with c1:
                var_tend = st.selectbox(
                    "Variable", cols_numericas,
                    index=cols_numericas.index('VT') if 'VT' in cols_numericas else 0,
                    key='crea_tend_var',
                )
            with c2:
                ventana = st.slider(
                    "Ventana media móvil (meses)", 2, 24, 6,
                    key='crea_tend_ventana',
                )

            df_t = (df_crea[['Periodo', var_tend]]
                    .dropna(subset=[var_tend])
                    .sort_values('Periodo'))
            rolling = (df_t[var_tend]
                       .rolling(ventana, center=True,
                                min_periods=max(1, ventana // 2))
                       .mean())

            fig_tend = go.Figure()
            fig_tend.add_trace(go.Scatter(
                x=df_t['Periodo'], y=df_t[var_tend],
                name='Dato real', mode='lines',
                line=dict(color='rgba(91,143,249,0.4)', width=1.2),
                hovertemplate=f'{var_tend}: %{{y:.2f}}<extra></extra>',
            ))
            fig_tend.add_trace(go.Scatter(
                x=df_t['Periodo'], y=rolling,
                name=f'Media móvil {ventana}m', mode='lines',
                line=dict(color='#f4a522', width=2.5),
                hovertemplate=f'Tendencia ({ventana}m): %{{y:.2f}}<extra></extra>',
            ))
            fig_tend.update_layout(
                height=400,
                yaxis_title=var_tend,
                hovermode='x unified',
                legend=dict(orientation='h', yanchor='bottom',
                            y=1.02, xanchor='left', x=0),
                margin=dict(t=40),
            )
            st.plotly_chart(fig_tend, use_container_width=True, key='crea_tend_chart')

        with st.expander("Datos brutos CREA"):
            st.dataframe(df_crea, use_container_width=True)

    except Exception as e:
        st.error(f"Error cargando datos CREA: {e}")


# ── Tab DairyComp ───────────────────────────────────────────────────────────
with tab_dairycomp:
    try:
        dc = _get_dairycomp()
        df_ev = dc['eventos']
        df_ctrl = dc['controles']

        grouped = df_ev.groupby(['Ano', 'Mes', 'Tipo', 'Evento']).count()['ID'].reset_index()
        grouped_y = grouped.groupby(['Ano', 'Tipo', 'Evento']).sum().reset_index()
        grouped_m = grouped.groupby(['Mes', 'Tipo', 'Evento']).mean().reset_index()

        sub_salud, sub_repro, sub_ctrl, sub_animal, sub_expl = st.tabs([
            "Estadísticas Salud", "Estadísticas Reproducción", "Control Lechero",
            "Historial Animal", "📊 Explorador",
        ])

        with sub_salud:
            col_a, col_b = st.columns(2)
            with col_a:
                fig_sm = px.area(
                    grouped_m[grouped_m['Tipo'] == 'salud'],
                    x='Mes', y='ID', color='Evento',
                    title='Eventos Salud por mes (promedio)',
                    labels={'ID': 'Cantidad media mensual'},
                )
                st.plotly_chart(fig_sm, use_container_width=True)
            with col_b:
                fig_sy = px.area(
                    grouped_y[grouped_y['Tipo'] == 'salud'],
                    x='Ano', y='ID', color='Evento',
                    title='Eventos Salud por año',
                    labels={'Ano': 'Año', 'ID': 'Cantidad anual'},
                )
                st.plotly_chart(fig_sy, use_container_width=True)

        with sub_repro:
            col_a, col_b = st.columns(2)
            with col_a:
                fig_rm = px.area(
                    grouped_m[grouped_m['Tipo'] == 'repro'],
                    x='Mes', y='ID', color='Evento',
                    title='Eventos Reproducción por mes (promedio)',
                    labels={'ID': 'Cantidad media mensual'},
                )
                st.plotly_chart(fig_rm, use_container_width=True)
            with col_b:
                fig_ry = px.area(
                    grouped_y[grouped_y['Tipo'] == 'repro'],
                    x='Ano', y='ID', color='Evento',
                    title='Eventos Reproducción por año',
                    labels={'Ano': 'Año', 'ID': 'Cantidad anual'},
                )
                st.plotly_chart(fig_ry, use_container_width=True)

        with sub_ctrl:
            col_a, col_b = st.columns(2)
            with col_a:
                fig_dl = px.violin(df_ctrl, x='LACT', y='DE',
                                   title='Días en Leche por Lactancia',
                                   labels={'LACT': 'Lactancia', 'DE': 'Días en leche'})
                st.plotly_chart(fig_dl, use_container_width=True)
            with col_b:
                fig_pl = px.violin(df_ctrl, x='LACT', y='LECH',
                                   title='Producción de Leche por Lactancia',
                                   labels={'LACT': 'Lactancia', 'LECH': 'Producción'})
                st.plotly_chart(fig_pl, use_container_width=True)

            df_ctrl_ym = df_ctrl.groupby(['FechaCtr', 'LACT']).mean(numeric_only=True).reset_index()
            fig_hist_ctrl = px.line(
                df_ctrl_ym, x='FechaCtr', y='LECH', color='LACT',
                title='Histórico Controles Lecheros por Lactancia',
                labels={'LECH': 'Producción media', 'FechaCtr': 'Fecha del Control'},
            )
            st.plotly_chart(fig_hist_ctrl, use_container_width=True)

            # ── Curva de lactancia Wood: y = a * t^b * exp(-c*t) ─────────
            st.divider()
            st.subheader("Curva de lactancia (modelo de Wood)")

            from scipy.optimize import curve_fit

            def wood_model(t, a, b, c):
                return a * np.power(t, b) * np.exp(-c * t)

            col_lact, col_fecha_range = st.columns([1, 2])
            with col_lact:
                lacts_disponibles = sorted(df_ctrl['LACT'].dropna().unique())
                lact_sel = st.selectbox(
                    "Lactancia", lacts_disponibles,
                    format_func=lambda x: f"L{int(x)}",
                    key="wood_lact",
                )
            with col_fecha_range:
                fechas_ctrl = df_ctrl['FechaCtr'].dropna().sort_values().unique()
                fecha_min = pd.Timestamp(fechas_ctrl.min()).date()
                fecha_max = pd.Timestamp(fechas_ctrl.max()).date()
                rango_fecha = st.slider(
                    "Rango de fechas de control",
                    min_value=fecha_min, max_value=fecha_max,
                    value=(fecha_min, fecha_max),
                    format="DD/MM/YY", key="wood_fecha_range",
                )

            df_wood = df_ctrl[
                (df_ctrl['LACT'] == lact_sel) &
                (df_ctrl['FechaCtr'].dt.date >= rango_fecha[0]) &
                (df_ctrl['FechaCtr'].dt.date <= rango_fecha[1]) &
                (df_ctrl['DE'] > 0) & (df_ctrl['DE'] <= 500) &
                (df_ctrl['LECH'] > 0) & (df_ctrl['LECH'] <= 70)
            ].copy()
            # Filtro IQR por grupo de DE para limpiar outliers
            q1 = df_wood.groupby(pd.cut(df_wood['DE'], bins=20))['LECH'].transform('quantile', 0.05)
            q3 = df_wood.groupby(pd.cut(df_wood['DE'], bins=20))['LECH'].transform('quantile', 0.95)
            df_wood = df_wood[(df_wood['LECH'] >= q1) & (df_wood['LECH'] <= q3)]
            df_wood['fechatosca'] = df_wood['FechaCtr'].dt.strftime('%Y%m%d')

            fechas_unicas = sorted(df_wood['fechatosca'].unique())
            min_puntos = st.slider("Mínimo de animales por control para ajustar curva",
                                   min_value=3, max_value=30, value=8, key="wood_min_pts")

            import plotly.express as _px
            _colors = _px.colors.qualitative.Plotly + _px.colors.qualitative.D3
            color_map = {f: _colors[i % len(_colors)] for i, f in enumerate(fechas_unicas)}

            fig_wood = go.Figure()
            params_table = []
            t_fit = np.linspace(5, min(500, df_wood['DE'].max() + 30), 300)

            for fecha in fechas_unicas:
                sub = df_wood[df_wood['fechatosca'] == fecha]
                t_data = sub['DE'].values.astype(float)
                y_data = sub['LECH'].values.astype(float)
                color = color_map[fecha]

                # Scatter de puntos
                fig_wood.add_trace(go.Scatter(
                    x=t_data, y=y_data,
                    mode='markers', name=fecha,
                    legendgroup=fecha,
                    marker=dict(color=color, size=5, opacity=0.45),
                    hovertemplate='DE: %{x}<br>Prod: %{y} L<extra></extra>',
                ))

                if len(t_data) < min_puntos:
                    continue

                try:
                    popt, _ = curve_fit(
                        wood_model, t_data, y_data,
                        p0=[15, 0.2, 0.003],
                        bounds=([0.1, 0.001, 0.0001], [200, 3.0, 0.1]),
                        maxfev=10000,
                    )
                    a, b, c = popt
                    y_fit = wood_model(t_fit, a, b, c)

                    de_pico = b / c
                    pico = a * (b / c) ** b * np.exp(-b)
                    persistencia = -(b + 1) * np.log(c)

                    fig_wood.add_trace(go.Scatter(
                        x=t_fit, y=y_fit,
                        mode='lines', name=f'{fecha} (Wood)',
                        legendgroup=fecha,
                        showlegend=False,
                        line=dict(color=color, width=2.5),
                        hovertemplate=(
                            f'<b>{fecha}</b><br>'
                            f'Pico: {pico:.1f}L @ DE {de_pico:.0f}<br>'
                            f'Persistencia: {persistencia:.2f}'
                            '<extra></extra>'
                        ),
                    ))

                    params_table.append({
                        'Control': fecha,
                        'n vacas': len(sub),
                        'a': round(a, 3),
                        'b': round(b, 4),
                        'c': round(c, 5),
                        'Pico (L)': round(pico, 1),
                        'DE al pico': round(de_pico, 0),
                        'Persistencia': round(persistencia, 2),
                    })
                except Exception:
                    pass

            fig_wood.update_layout(
                title=f'Producción L{int(lact_sel)} + curvas Wood',
                xaxis_title='Días en leche',
                yaxis_title='Producción (L)',
                height=600,
                legend=dict(title='Control', x=1.02, y=1),
            )
            st.plotly_chart(fig_wood, use_container_width=True)

            if params_table:
                st.markdown("**Parámetros del modelo de Wood** — `y = a · t^b · exp(-c·t)`")
                st.dataframe(
                    pd.DataFrame(params_table),
                    use_container_width=True, hide_index=True,
                )
                st.caption(
                    "**Pico**: producción máxima estimada. "
                    "**DE al pico**: día de lactancia al pico. "
                    "**Persistencia**: -(b+1)·ln(c) — mayor valor = menor caída post-pico."
                )
            else:
                st.info("No se pudo ajustar ninguna curva. Probá bajando el mínimo de animales o ampliando el rango de fechas.")

        with sub_animal:
            # ── Clasificación de eventos ────────────────────────────────────
            _REPRO  = {'INSEMIN', 'PROSTA', 'PARTO', 'PREÑADA', 'VACIA', 'SECA',
                       'CELO', 'RECHAZO', 'ABORTO', 'GNRH', 'DIB', 'ALTAMAS',
                       'SIGUEP', 'DESVASA', 'RECK', 'CET'}
            _SALUD  = {'MAST', 'RENGA', 'MUERTA', 'RETPLAC', 'ENFERMA', 'CAIDA',
                       'ANESTRO', 'HIPOCAL', 'UBRE', 'DIARREA', 'UTERO', 'METRIT',
                       'QUISTE', 'ENDOMET', 'TRATADA'}
            _COLOR  = {
                'repro':    '#2196F3',
                'salud':    '#F44336',
                'manejo':   '#FF9800',
                'otro':     '#9E9E9E',
            }
            _SIMBOLO = {
                'PARTO':    'star',
                'INSEMIN':  'triangle-up',
                'PREÑADA':  'diamond',
                'VACIA':    'x',
                'SECA':     'square',
                'ABORTO':   'triangle-down',
                'MAST':     'circle',
                'MUERTA':   'cross',
                'VENDIDA':  'pentagon',
            }

            def _clasificar(ev):
                if ev in _REPRO:   return 'repro'
                if ev in _SALUD:   return 'salud'
                return 'manejo'

            # ── Estado de cada animal ───────────────────────────────────────
            _ev_sets   = df_ev.groupby('ID')['Evento'].apply(set)
            _ev_counts = df_ev.groupby('ID')['Evento'].count()
            _ev_first  = df_ev.groupby('ID')['Fecha'].min()
            _ev_last   = df_ev.groupby('ID')['Fecha'].max()
            # Eventos que marcan inicio de vida productiva (primera inseminación)
            _EVENTOS_INICIO_PROD = {'INSEMIN', 'DIB'}
            # Eventos que NO son de nacimiento/muerte para distinguir vida productiva
            _EVENTOS_PROD = {'PARTO', 'INSEMIN', 'DIB', 'PREÑADA', 'VACIA', 'SECA',
                             'MAST', 'RENGA', 'RETPLAC', 'ENFERMA', 'TRATADA',
                             'METRIT', 'ENDOMET', 'ABORTO', 'CELO'}
            def _estado_animal(row):
                evs = row['evs']
                if 'MUERTA' in evs:
                    if evs & _EVENTOS_PROD:
                        return 'MUERTA'
                    else:
                        return 'NATIMUERTA'
                if 'VENDIDA' in evs: return 'VENDIDA'
                if 'SECA' in evs and 'PARTO' not in evs: return 'SECA'
                # REPO: nunca tuvo INSEMIN ni DIB → aún no entró en fase productiva
                if not (evs & _EVENTOS_INICIO_PROD):
                    return 'REPO'
                return 'ACTIVA'
            _ev_df = pd.DataFrame({
                'evs': _ev_sets,
                'n':   _ev_counts,
            })
            _estado_map = _ev_df.apply(_estado_animal, axis=1)

            _todos_ids_full = sorted(df_ev['ID'].dropna().unique())
            _conteos = _estado_map.value_counts()

            # ── Filtros por estado ──────────────────────────────────────────
            st.markdown("**Filtrar por estado:**")
            _fcol1, _fcol2, _fcol3, _fcol4, _fcol5, _fcol6 = st.columns(6)
            _estados_posibles = [
                ('ACTIVA',     '🟢', _fcol1),
                ('REPO', '🟣', _fcol2),
                ('VENDIDA',    '🟡', _fcol3),
                ('MUERTA',     '🔴', _fcol4),
                ('NATIMUERTA', '⚫', _fcol5),
                ('SECA',       '🔵', _fcol6),
            ]
            _filtros = {}
            for _est, _ico, _col in _estados_posibles:
                _n = _conteos.get(_est, 0)
                _filtros[_est] = _col.checkbox(
                    f"{_ico} {_est} ({_n})",
                    value=(_est == 'ACTIVA'),
                    key=f"flt_{_est.lower()}",
                )
            _estados_sel = [e for e, v in _filtros.items() if v]
            if not _estados_sel:
                _estados_sel = [e for e, _i, _c in _estados_posibles]  # si nada seleccionado, mostrar todos

            todos_ids = [i for i in _todos_ids_full if _estado_map.get(i, 'ACTIVA') in _estados_sel]

            # ── Selector de animal ──────────────────────────────────────────
            col_srch, col_info = st.columns([2, 3])
            with col_srch:
                animal_id = st.selectbox(
                    f"Seleccioná un animal (ID) — {len(todos_ids)} animales",
                    options=todos_ids,
                    format_func=lambda x: f"#{int(x)} [{_estado_map.get(x, '?')}]",
                    key="animal_id",
                )

            if animal_id:
                ev_animal  = df_ev[df_ev['ID'] == animal_id].copy()
                ctr_animal = df_ctrl[df_ctrl['ID'] == animal_id].copy()

                ev_animal['Categoria'] = ev_animal['Evento'].apply(_clasificar)
                n_partos = (ev_animal['Evento'] == 'PARTO').sum()
                ultimo_ev = ev_animal['Fecha'].max()
                estado = _estado_map.get(animal_id, 'ACTIVA')

                with col_info:
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("ID", f"#{int(animal_id)}")
                    c2.metric("Partos", n_partos)
                    c3.metric("Estado", estado)
                    c4.metric("Último evento", ultimo_ev.strftime('%d/%m/%Y') if pd.notna(ultimo_ev) else '—')

                # ── Figura principal ────────────────────────────────────────
                fig_a = go.Figure()

                # Curva de producción por lactancia
                if not ctr_animal.empty:
                    for lact in sorted(ctr_animal['LACT'].unique()):
                        df_l = ctr_animal[ctr_animal['LACT'] == lact].sort_values('FechaCtr')
                        fig_a.add_trace(go.Scatter(
                            x=df_l['FechaCtr'],
                            y=df_l['LECH'],
                            mode='lines+markers',
                            name=f'Producción L{int(lact)}',
                            yaxis='y1',
                            line=dict(width=2),
                            marker=dict(size=6),
                            hovertemplate=(
                                '<b>Control L%d</b><br>' % lact +
                                'Fecha: %{x|%d/%m/%Y}<br>' +
                                'Producción: %{y} L<br>' +
                                'DE: ' + df_l['DE'].astype(str).str.strip() + 'd<extra></extra>'
                            ),
                        ))

                # Eventos como scatter en eje secundario
                for cat, grp in ev_animal.groupby('Categoria'):
                    for evento, subgrp in grp.groupby('Evento'):
                        subgrp = subgrp.sort_values('Fecha')
                        notas = subgrp['Nota'].fillna('').str.strip().tolist() if 'Nota' in subgrp.columns else [''] * len(subgrp)
                        fig_a.add_trace(go.Scatter(
                            x=subgrp['Fecha'],
                            y=[cat] * len(subgrp),
                            mode='markers',
                            name=evento,
                            yaxis='y2',
                            marker=dict(
                                symbol=_SIMBOLO.get(evento, 'circle'),
                                size=10,
                                color=_COLOR[cat],
                                line=dict(width=1, color='white'),
                            ),
                            customdata=notas,
                            hovertemplate=(
                                f'<b>{evento}</b><br>' +
                                'Fecha: %{x|%d/%m/%Y}<br>' +
                                'Nota: %{customdata}<extra></extra>'
                            ),
                        ))

                fig_a.update_layout(
                    title=f'Historial animal #{int(animal_id)}',
                    height=550,
                    yaxis=dict(title='Producción (L)', side='left'),
                    yaxis2=dict(
                        title='Categoría evento',
                        overlaying='y',
                        side='right',
                        showgrid=False,
                        tickvals=['repro', 'salud', 'manejo'],
                        ticktext=['Repro', 'Salud', 'Manejo'],
                    ),
                    legend=dict(x=1.08, y=1, font=dict(size=10)),
                    hovermode='x unified',
                    margin=dict(r=220),
                )

                # Líneas verticales en cada parto
                for _, row in ev_animal[ev_animal['Evento'] == 'PARTO'].iterrows():
                    fig_a.add_vline(
                        x=row['Fecha'].timestamp() * 1000,
                        line_dash='dot',
                        line_color='green',
                        opacity=0.5,
                        annotation_text='PARTO',
                        annotation_position='top',
                        annotation_font_size=9,
                    )

                st.plotly_chart(fig_a, use_container_width=True)

                # Tablas de detalle
                col_ev, col_ctr = st.columns(2)
                with col_ev:
                    with st.expander(f"Eventos ({len(ev_animal)})"):
                        cols_show = [c for c in ['Fecha', 'Evento', 'DEL', 'Nota', 'Categoria'] if c in ev_animal.columns]
                        st.dataframe(
                            ev_animal[cols_show].sort_values('Fecha', ascending=False),
                            use_container_width=True, hide_index=True,
                        )
                with col_ctr:
                    with st.expander(f"Controles lecheros ({len(ctr_animal)})"):
                        cols_ctr = [c for c in ['FechaCtr', 'LACT', 'DE', 'LECH', 'PCT', 'LCG', '305E'] if c in ctr_animal.columns]
                        st.dataframe(
                            ctr_animal[cols_ctr].sort_values('FechaCtr', ascending=False),
                            use_container_width=True, hide_index=True,
                        )

        # ── Sub-tab Explorador ───────────────────────────────────────────────
        with sub_expl:
            # ── Construir serie mensual unificada ────────────────────────────
            # Eventos: contar por tipo por mes
            _EV_INTERES = [
                'INSEMIN', 'PARTO', 'PREÑADA', 'VACIA', 'CELO',
                'MAST', 'RENGA', 'SECA', 'MUERTA', 'VENDIDA',
                'RETPLAC', 'ABORTO', 'ANESTRO',
            ]
            df_ev2 = df_ev.copy()
            df_ev2['Periodo'] = pd.to_datetime(
                df_ev2['Ano'].astype(str) + '-' +
                df_ev2['Mes'].astype(str).str.zfill(2) + '-01'
            )
            ev_series = {}
            for ev in _EV_INTERES:
                s = (df_ev2[df_ev2['Evento'] == ev]
                     .groupby('Periodo')['ID'].count()
                     .rename(f'n_{ev}'))
                if s.sum() > 0:
                    ev_series[f'n_{ev}'] = s

            # Controles: promedio mensual
            df_ctrl3 = df_ctrl.copy()
            df_ctrl3['Periodo'] = df_ctrl3['FechaCtr'].dt.to_period('M').dt.to_timestamp()
            _CTRL_COLS = [c for c in ['LECH', 'DE', 'PCT', 'LCG', '305E', 'LACT']
                         if c in df_ctrl3.columns]
            ctrl_m = df_ctrl3.groupby('Periodo')[_CTRL_COLS].mean()

            # Espine mensual completo
            full_range_dc = pd.date_range(
                df_ev2['Periodo'].min(),
                df_ev2['Periodo'].max(),
                freq='MS',
            )
            df_expl = pd.DataFrame({'Periodo': full_range_dc})
            for name, s in ev_series.items():
                df_expl[name] = df_expl['Periodo'].map(s).fillna(0)
            for col in _CTRL_COLS:
                if col in ctrl_m.columns:
                    df_expl[col] = df_expl['Periodo'].map(ctrl_m[col])
            df_expl['Ano'] = df_expl['Periodo'].dt.year
            df_expl['Mes'] = df_expl['Periodo'].dt.month

            # Nombres amigables
            _LABELS = {
                'n_INSEMIN': 'Inseminaciones', 'n_PARTO': 'Partos',
                'n_PREÑADA': 'Preñeces', 'n_VACIA': 'Vacías',
                'n_CELO': 'Celos detectados', 'n_MAST': 'Mastitis',
                'n_RENGA': 'Rengas', 'n_SECA': 'Secas',
                'n_MUERTA': 'Muertes', 'n_VENDIDA': 'Vendidas',
                'n_RETPLAC': 'Ret. placenta', 'n_ABORTO': 'Abortos',
                'n_ANESTRO': 'Anestros',
                'LECH': 'Producción media (L)', 'DE': 'Días en leche',
                'PCT': 'PCT', 'LCG': 'LCG', '305E': '305E', 'LACT': 'Lactancia media',
            }
            cols_expl = [c for c in df_expl.columns
                        if c not in ('Periodo', 'Ano', 'Mes')]
            _COLORS_DC = ['#f4a522', '#5b8ff9', '#5ad8a6', '#ff6b6b',
                          '#c050e8', '#ff9f40', '#00c0c7', '#e8825a']
            _MESES_DC = ['Ene','Feb','Mar','Abr','May','Jun',
                         'Jul','Ago','Sep','Oct','Nov','Dic']

            xp_exp, xp_seas, xp_tend = st.tabs([
                "🔍 Explorador", "📅 Estacionalidad", "📈 Tendencia"
            ])

            # ── Explorador ───────────────────────────────────────────────────
            with xp_exp:
                st.caption(
                    "Variables derivadas de eventos (conteos mensuales) y de controles "
                    "lecheros (promedios mensuales). 1–2 variables → ejes duales; "
                    "3–4 o **Normalizar** → escala 0–100 %."
                )
                cx1, cx2, cx3 = st.columns([4, 1, 2])
                with cx1:
                    dc_vars = st.multiselect(
                        "Variables",
                        cols_expl,
                        format_func=lambda c: _LABELS.get(c, c),
                        default=[c for c in ['n_INSEMIN', 'LECH'] if c in cols_expl],
                        key='dc_vars',
                    )
                with cx2:
                    dc_norm = st.checkbox("Normalizar\n(0–100)", key='dc_norm')
                with cx3:
                    anos_dc = sorted(df_expl['Ano'].unique())
                    dc_rango = st.select_slider(
                        "Período", options=anos_dc,
                        value=(anos_dc[0], anos_dc[-1]),
                        key='dc_rango',
                    )

                dc_vars = dc_vars[:4]
                dc_forzar = dc_norm or len(dc_vars) > 2

                if not dc_vars:
                    st.info("Seleccioná al menos una variable.")
                else:
                    df_fx = df_expl[df_expl['Ano'].between(dc_rango[0], dc_rango[1])].copy()
                    fig_dcx = go.Figure()

                    for i, var in enumerate(dc_vars):
                        serie = df_fx.set_index('Periodo')[var].dropna()
                        color = _COLORS_DC[i % len(_COLORS_DC)]
                        lbl = _LABELS.get(var, var)

                        if dc_forzar:
                            mn, mx = serie.min(), serie.max()
                            yv = (serie - mn) / (mx - mn) * 100 if mx > mn else serie * 0 + 50
                            yref = 'y'
                            ht = f'{lbl}: %{{y:.1f}} % norm<extra></extra>'
                        else:
                            yv = serie
                            yref = 'y' if i == 0 else 'y2'
                            ht = f'{lbl}: %{{y:.2f}}<extra></extra>'

                        fig_dcx.add_trace(go.Scatter(
                            x=serie.index, y=yv,
                            name=lbl, yaxis=yref,
                            line=dict(color=color, width=2),
                            hovertemplate=ht,
                            mode='lines',
                        ))

                    lo_dc = dict(
                        height=430, hovermode='x unified',
                        legend=dict(orientation='h', yanchor='bottom',
                                    y=1.02, xanchor='left', x=0),
                        margin=dict(t=50, r=70 if not dc_forzar and len(dc_vars) == 2 else 20),
                    )
                    if dc_forzar:
                        lo_dc['yaxis'] = dict(title='% normalizado', range=[-5, 105])
                    elif len(dc_vars) == 2:
                        lo_dc['yaxis']  = dict(
                            title=dict(text=_LABELS.get(dc_vars[0], dc_vars[0]),
                                       font=dict(color=_COLORS_DC[0])),
                            tickfont=dict(color=_COLORS_DC[0]),
                        )
                        lo_dc['yaxis2'] = dict(
                            title=dict(text=_LABELS.get(dc_vars[1], dc_vars[1]),
                                       font=dict(color=_COLORS_DC[1])),
                            tickfont=dict(color=_COLORS_DC[1]),
                            overlaying='y', side='right', showgrid=False,
                        )
                    else:
                        lo_dc['yaxis'] = dict(title=_LABELS.get(dc_vars[0], dc_vars[0]))

                    fig_dcx.update_layout(**lo_dc)
                    st.plotly_chart(fig_dcx, use_container_width=True, key='dc_exp_chart')

            # ── Estacionalidad ───────────────────────────────────────────────
            with xp_seas:
                st.caption(
                    "**Box por mes**: distribución histórica de cada mes. "
                    "**Años superpuestos**: cada año como línea ene→dic."
                )
                cs1, cs2 = st.columns([2, 2])
                with cs1:
                    dc_var_s = st.selectbox(
                        "Variable", cols_expl,
                        format_func=lambda c: _LABELS.get(c, c),
                        key='dc_seas_var',
                    )
                with cs2:
                    dc_modo_s = st.radio(
                        "Modo", ["Box por mes", "Años superpuestos"],
                        horizontal=True, key='dc_seas_modo',
                    )

                df_ss = df_expl[['Ano', 'Mes', dc_var_s]].dropna(subset=[dc_var_s])
                lbl_s = _LABELS.get(dc_var_s, dc_var_s)

                if dc_modo_s == "Box por mes":
                    fig_dcs = go.Figure()
                    for m in range(1, 13):
                        vals = df_ss[df_ss['Mes'] == m][dc_var_s]
                        fig_dcs.add_trace(go.Box(
                            y=vals, name=_MESES_DC[m - 1],
                            marker_color='#5b8ff9',
                            boxmean='sd', showlegend=False,
                        ))
                    fig_dcs.update_layout(
                        height=400, yaxis_title=lbl_s, margin=dict(t=20),
                    )
                else:
                    fig_dcs = go.Figure()
                    SEAS_DC = px.colors.qualitative.Set2
                    for i, ano in enumerate(sorted(df_ss['Ano'].unique())):
                        df_ano = df_ss[df_ss['Ano'] == ano].sort_values('Mes')
                        fig_dcs.add_trace(go.Scatter(
                            x=df_ano['Mes'], y=df_ano[dc_var_s],
                            name=str(int(ano)), mode='lines+markers',
                            line=dict(width=1.8, color=SEAS_DC[i % len(SEAS_DC)]),
                            marker=dict(size=5),
                        ))
                    fig_dcs.update_layout(
                        height=400,
                        xaxis=dict(tickmode='array', tickvals=list(range(1, 13)),
                                   ticktext=_MESES_DC, title='Mes'),
                        yaxis_title=lbl_s,
                        hovermode='x unified',
                        legend=dict(orientation='h', yanchor='bottom',
                                    y=1.02, xanchor='left', x=0),
                        margin=dict(t=40),
                    )

                st.plotly_chart(fig_dcs, use_container_width=True, key='dc_seas_chart')

            # ── Tendencia ────────────────────────────────────────────────────
            with xp_tend:
                st.caption(
                    "Serie mensual real + media móvil centrada. "
                    "Ajustá la ventana para separar ruido de tendencia."
                )
                ct1, ct2 = st.columns([2, 2])
                with ct1:
                    dc_var_t = st.selectbox(
                        "Variable", cols_expl,
                        format_func=lambda c: _LABELS.get(c, c),
                        key='dc_tend_var',
                    )
                with ct2:
                    dc_vent = st.slider(
                        "Ventana media móvil (meses)", 2, 24, 6, key='dc_tend_vent',
                    )

                lbl_t = _LABELS.get(dc_var_t, dc_var_t)
                df_tt = (df_expl[['Periodo', dc_var_t]]
                         .dropna(subset=[dc_var_t])
                         .sort_values('Periodo'))
                roll_dc = (df_tt[dc_var_t]
                           .rolling(dc_vent, center=True,
                                    min_periods=max(1, dc_vent // 2))
                           .mean())

                fig_dct = go.Figure()
                fig_dct.add_trace(go.Scatter(
                    x=df_tt['Periodo'], y=df_tt[dc_var_t],
                    name='Dato real', mode='lines',
                    line=dict(color='rgba(91,143,249,0.4)', width=1.2),
                    hovertemplate=f'{lbl_t}: %{{y:.1f}}<extra></extra>',
                ))
                fig_dct.add_trace(go.Scatter(
                    x=df_tt['Periodo'], y=roll_dc,
                    name=f'Media móvil {dc_vent}m', mode='lines',
                    line=dict(color='#f4a522', width=2.5),
                    hovertemplate=f'Tendencia: %{{y:.1f}}<extra></extra>',
                ))
                fig_dct.update_layout(
                    height=400, yaxis_title=lbl_t,
                    hovermode='x unified',
                    legend=dict(orientation='h', yanchor='bottom',
                                y=1.02, xanchor='left', x=0),
                    margin=dict(t=40),
                )
                st.plotly_chart(fig_dct, use_container_width=True, key='dc_tend_chart')

    except Exception as e:
        st.error(f"Error cargando DairyComp: {e}")
