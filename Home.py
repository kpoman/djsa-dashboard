import streamlit as st

st.set_page_config(
    page_title="DJSA Dashboard",
    page_icon="🐄",
    layout="wide",
)

st.title("🐄 Dashboard DJSA")
st.subheader("Don Jacinto San Antonio — La Merced")

st.markdown("---")

st.markdown("""
Bienvenido al panel de gestión integral del establecimiento.
Utilizá el menú de la izquierda para navegar entre las secciones:

| Sección | Descripción |
|---|---|
| 🐄 **Tambo** | Producción de leche, datos DairyComp y CREA |
| 🌾 **Gestión** | Márgenes brutos por campaña y cultivo |
| 📊 **Holistor** | Análisis contable jerárquico |
""")

st.markdown("---")
st.caption("Panel de control interno — DJSA")
