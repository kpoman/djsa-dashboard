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
    return df_clean


@st.cache_data(show_spinner="Cargando DairyComp...")
def _get_dairycomp():
    import os
    base = os.path.join(os.path.dirname(__file__), '..', 'data')
    df_ev = pd.read_csv(
        os.path.join(base, 'eventos-202604.csv'),
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
        os.path.join(base, 'control-202604.csv'),
        encoding='iso-8859-1', delimiter=';',
        parse_dates=['FechaCtr', 'FPART', 'FSECA'],
        date_format='%d/%m/%y', dayfirst=True,
    )
    df_ctrl = df_ctrl[df_ctrl['VALR'] > 0]
    return {'eventos': df_ev, 'controles': df_ctrl}


# ── UI ───────────────────────────────────────────────────────────────────────
st.title("🐄 Tambo")

tab_prod, tab_alim, tab_crea, tab_dairycomp = st.tabs([
    "Producción de leche", "Alimentación", "Datos CREA", "DairyComp"
])

# ── Tab Producción de leche ─────────────────────────────────────────────────
with tab_prod:
    sub_rec, sub_hist = st.tabs(["Reciente", "Histórico"])

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
                st.subheader("Litros libres por rodeo")
                fig_ll = px.bar(
                    df_vis, x='Fecha', y='Litros_libres', color='Rodeo',
                    barmode='group',
                    title='Litros libres (Producción - Costo alimentación en litros)',
                    labels={'Litros_libres': 'Litros libres', 'Fecha': ''},
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

        col1, col2 = st.columns(2)
        with col1:
            variable = st.selectbox("Variable a graficar", cols_numericas,
                                    index=cols_numericas.index('VT') if 'VT' in cols_numericas else 0)
        with col2:
            anos_disp = sorted(df_crea['Ano'].unique())
            anos_sel = st.multiselect("Año(s)", anos_disp, default=anos_disp[-5:])

        df_crea_f = df_crea[df_crea['Ano'].isin(anos_sel)] if anos_sel else df_crea
        fig_c = px.line(df_crea_f, x='Periodo', y=variable, color='Ano',
                        title=f'{variable} por período',
                        labels={'Periodo': 'Fecha', variable: variable})
        st.plotly_chart(fig_c, use_container_width=True)

        with st.expander("Datos brutos CREA"):
            st.dataframe(df_crea_f, use_container_width=True)

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

        sub_salud, sub_repro, sub_ctrl, sub_animal = st.tabs([
            "Estadísticas Salud", "Estadísticas Reproducción", "Control Lechero", "Historial Animal"
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

            # ── Selector de animal ──────────────────────────────────────────
            todos_ids = sorted(df_ev['ID'].dropna().unique())
            col_srch, col_info = st.columns([2, 3])
            with col_srch:
                animal_id = st.selectbox(
                    "Seleccioná un animal (ID)",
                    options=todos_ids,
                    format_func=lambda x: f"#{int(x)}",
                    key="animal_id",
                )

            if animal_id:
                ev_animal  = df_ev[df_ev['ID'] == animal_id].copy()
                ctr_animal = df_ctrl[df_ctrl['ID'] == animal_id].copy()

                ev_animal['Categoria'] = ev_animal['Evento'].apply(_clasificar)
                n_partos = (ev_animal['Evento'] == 'PARTO').sum()
                ultimo_ev = ev_animal['Fecha'].max()
                estado = 'ACTIVA'
                if (ev_animal['Evento'] == 'MUERTA').any():
                    estado = 'MUERTA'
                elif (ev_animal['Evento'] == 'VENDIDA').any():
                    estado = 'VENDIDA'

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

    except Exception as e:
        st.error(f"Error cargando DairyComp: {e}")
