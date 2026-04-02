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

tab_prod, tab_crea, tab_dairycomp = st.tabs([
    "Producción de leche", "Datos CREA", "DairyComp"
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

            st.subheader("LTVO por rodeo (media móvil 7d)")
            fig2 = px.line(df_rodeos, x='date', y='roll_ltvo', color='cat',
                           labels={'date': 'Fecha', 'roll_ltvo': 'LTVO', 'cat': 'Rodeo'})
            st.plotly_chart(fig2, use_container_width=True)

            st.subheader("Producción diaria total (media móvil 7d)")
            fig3 = px.line(df_total, x='date', y='roll',
                           labels={'date': 'Fecha', 'roll': 'Litros diarios'})
            st.plotly_chart(fig3, use_container_width=True)

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

            df_lact1 = df_ctrl[(df_ctrl['LACT'] == 1) & (df_ctrl['FechaCtr'] > '2020-09-01')].copy()
            df_lact1['fechatosca'] = df_lact1['FechaCtr'].dt.strftime('%Y%m%d')
            fig_l1 = px.scatter(df_lact1, x='DE', y='LECH',
                                title='Prod Leche Vaquillonas (L1, post Sep-2020)',
                                color='fechatosca',
                                labels={'DE': 'Días en leche', 'LECH': 'Producción'})
            st.plotly_chart(fig_l1, use_container_width=True)

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
