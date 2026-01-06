import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta

# Configuración de la página
st.set_page_config(
    page_title="Monitor Lechero Pro",
    page_icon="🐄",
    layout="wide"
)

# --- FUNCIONES AUXILIARES ---

def generar_datos_iniciales():
    """
    Genera datos ficticios para los últimos 30 días para demostrar la funcionalidad.
    En un caso real, esto vendría de una base de datos o CSV.
    """
    fechas = [datetime.today() - timedelta(days=x) for x in range(30)]
    fechas.reverse()
    
    datos = []
    for fecha in fechas:
        vacas = np.random.randint(45, 55) # Número de vacas ordeñadas
        promedio_litros = np.random.uniform(22, 28) # Promedio por vaca
        litros_total = int(vacas * promedio_litros)
        grasa = np.random.uniform(3.2, 4.0)
        proteina = np.random.uniform(3.0, 3.6)
        
        datos.append({
            "Fecha": fecha.date(),
            "Litros Totales": litros_total,
            "Vacas Ordeñadas": vacas,
            "Promedio por Vaca (L)": round(litros_total / vacas, 2),
            "% Grasa": round(grasa, 2),
            "% Proteína": round(proteina, 2)
        })
    
    return pd.DataFrame(datos)

# --- GESTIÓN DE ESTADO (SESSION STATE) ---
# Esto permite guardar los datos mientras la app está abierta sin una base de datos real
if 'df_produccion' not in st.session_state:
    st.session_state.df_produccion = generar_datos_iniciales()

# --- BARRA LATERAL (SIDEBAR) ---
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2395/2395798.png", width=100)
st.sidebar.title("Configuración")

# Filtros de Fecha
st.sidebar.subheader("Filtrar Datos")
df = st.session_state.df_produccion # Alias corto
fecha_min = df["Fecha"].min()
fecha_max = df["Fecha"].max()

fecha_inicio = st.sidebar.date_input("Fecha Inicio", fecha_min)
fecha_fin = st.sidebar.date_input("Fecha Fin", fecha_max)

# Filtrar el DataFrame según la selección
mask = (df["Fecha"] >= fecha_inicio) & (df["Fecha"] <= fecha_fin)
df_filtrado = df.loc[mask]

# --- CUERPO PRINCIPAL ---

st.title("🐄 Dashboard de Producción Lechera")
st.markdown("Monitor de rendimiento diario, calidad y volumen del hato.")

# 1. METRICAS PRINCIPALES (KPIs)
st.subheader("Resumen del Periodo Seleccionado")

col1, col2, col3, col4 = st.columns(4)

total_litros = df_filtrado["Litros Totales"].sum()
promedio_diario = df_filtrado["Litros Totales"].mean()
promedio_vaca = df_filtrado["Promedio por Vaca (L)"].mean()
promedio_grasa = df_filtrado["% Grasa"].mean()

with col1:
    st.metric(label="Producción Total (L)", value=f"{total_litros:,.0f}")
with col2:
    st.metric(label="Promedio Diario (L)", value=f"{promedio_diario:,.0f}")
with col3:
    st.metric(label="Promedio por Vaca (L)", value=f"{promedio_vaca:.1f}")
with col4:
    st.metric(label="Calidad Grasa Promedio", value=f"{promedio_grasa:.2f}%")

st.divider()

# 2. GRÁFICOS
col_chart1, col_chart2 = st.columns([2, 1])

with col_chart1:
    st.subheader("Tendencia de Producción (Litros)")
    fig_prod = px.line(df_filtrado, x="Fecha", y="Litros Totales", markers=True, 
                       title="Litros por Día", template="plotly_white")
    fig_prod.update_traces(line_color='#1f77b4', line_width=3)
    st.plotly_chart(fig_prod, use_container_width=True)

with col_chart2:
    st.subheader("Calidad de Leche")
    # Reformatear datos para mostrar Grasa y Proteina en el mismo gráfico
    df_calidad = df_filtrado.melt(id_vars=["Fecha"], value_vars=["% Grasa", "% Proteína"], 
                                  var_name="Componente", value_name="Porcentaje")
    fig_qual = px.bar(df_calidad, x="Fecha", y="Porcentaje", color="Componente", barmode="group",
                      color_discrete_map={"% Grasa": "#ff7f0e", "% Proteína": "#2ca02c"})
    st.plotly_chart(fig_qual, use_container_width=True)

# 3. ANÁLISIS DE EFICIENCIA
st.subheader("Relación Vacas vs. Producción")
fig_scatter = px.scatter(df_filtrado, x="Vacas Ordeñadas", y="Litros Totales", 
                         size="Promedio por Vaca (L)", color="Promedio por Vaca (L)",
                         title="Eficiencia del Hato (El tamaño del punto indica L/Vaca)",
                         hover_data=["Fecha"])
st.plotly_chart(fig_scatter, use_container_width=True)

st.divider()

# 4. REGISTRO DE NUEVA PRODUCCIÓN
st.subheader("📝 Registrar Producción Diaria")

with st.form("registro_form", clear_on_submit=True):
    col_in1, col_in2, col_in3, col_in4, col_in5 = st.columns(5)
    
    input_fecha = col_in1.date_input("Fecha", datetime.today())
    input_litros = col_in2.number_input("Litros Totales", min_value=0, value=1000)
    input_vacas = col_in3.number_input("Vacas Ordeñadas", min_value=1, value=50)
    input_grasa = col_in4.number_input("% Grasa", min_value=0.0, max_value=10.0, value=3.6, step=0.1)
    input_proteina = col_in5.number_input("% Proteína", min_value=0.0, max_value=10.0, value=3.2, step=0.1)
    
    submit_btn = st.form_submit_button("Guardar Registro")
    
    if submit_btn:
        nuevo_registro = {
            "Fecha": input_fecha,
            "Litros Totales": input_litros,
            "Vacas Ordeñadas": input_vacas,
            "Promedio por Vaca (L)": round(input_litros / input_vacas, 2),
            "% Grasa": round(input_grasa, 2),
            "% Proteína": round(input_proteina, 2)
        }
        
        # Añadir al DataFrame en session_state
        nueva_fila = pd.DataFrame([nuevo_registro])
        st.session_state.df_produccion = pd.concat([st.session_state.df_produccion, nueva_fila], ignore_index=True)
        # Ordenar por fecha por si acaso se inserta una fecha antigua
        st.session_state.df_produccion = st.session_state.df_produccion.sort_values(by="Fecha", ascending=False)
        st.success("¡Registro añadido exitosamente!")
        st.rerun()

# 5. TABLA DE DATOS
with st.expander("Ver Datos Crudos (Tabla)"):
    st.dataframe(df_filtrado.style.highlight_max(axis=0, color='lightgreen'), use_container_width=True)
    
    # Botón de descarga CSV
    csv = df_filtrado.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Descargar datos como CSV",
        data=csv,
        file_name='produccion_leche.csv',
        mime='text/csv',
    )
