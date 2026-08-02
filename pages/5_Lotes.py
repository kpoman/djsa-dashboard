import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go
import xml.etree.ElementTree as ET
import os, re, math
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Lotes — DJSA", page_icon="🗺️", layout="wide")

_DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

# ── Google Sheets (planteos locales + ejecución — vía service account) ─────
# Las referencias (Revista Márgenes, etc.) quedan en CSV local (cargadas por chat/OCR).
_WS_HEADER = "Planteos"
_WS_LINEAS = "Lineas"

try:
    _SHEET_ID = st.secrets.get("planteos", {}).get("sheet_id", "")
except Exception:
    _SHEET_ID = ""

URL_AMBIENTES = ""  # usa data/lotes_ambientes.csv local (generado del KML)
URL_REF_HDR  = ""   # pub?output=csv&gid=XXX  (tab "Referencia Header")
URL_REF_LIN  = ""   # pub?output=csv&gid=YYY  (tab "Referencia Lineas")

_LOCAL_AMB = os.path.join(_DATA_DIR, 'lotes_ambientes.csv')
_LOCAL_REF_HDR = os.path.join(_DATA_DIR, 'planteos_referencia_header.csv')
_LOCAL_REF_LIN = os.path.join(_DATA_DIR, 'planteos_referencia_lineas.csv')


# ── Cliente Google Sheets ────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _gs_client():
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return gspread.authorize(creds)


def _gs_worksheet(name, cols):
    sh = _gs_client().open_by_key(_SHEET_ID)
    try:
        ws = sh.worksheet(name)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=name, rows=1000, cols=max(len(cols), 10))
        ws.append_row(cols)
    return ws


def _gs_to_str(v):
    if v is None:
        return ''
    try:
        if pd.isna(v):
            return ''
    except (TypeError, ValueError):
        pass
    return str(v)


def _gs_read_df(name, cols):
    if not _SHEET_ID:
        return pd.DataFrame(columns=cols)
    ws = _gs_worksheet(name, cols)
    records = ws.get_all_records()
    if not records:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(records)
    return df.reindex(columns=cols)


def _gs_append_rows(name, cols, rows):
    ws = _gs_worksheet(name, cols)
    if not isinstance(rows, list):
        rows = [rows]
    values = [[_gs_to_str(r.get(c)) for c in cols] for r in rows]
    ws.append_rows(values, value_input_option="USER_ENTERED")


def _gs_update_lineas_real(sel_id, edited_df):
    """Actualiza precio_real/cant_real/valor_real/diferencia de las líneas de un planteo."""
    ws = _gs_worksheet(_WS_LINEAS, _LIN_COLS)
    all_vals = ws.get_all_values()
    if not all_vals:
        return
    header = all_vals[0]
    col_idx = {c: i for i, c in enumerate(header)}
    updates = []
    for i in range(1, len(all_vals)):
        row = all_vals[i]
        if row[col_idx['planteo_id']] != sel_id:
            continue
        _seccion = row[col_idx['seccion']]
        _orden = row[col_idx['orden']]
        _match = edited_df[
            (edited_df['seccion'].astype(str) == str(_seccion)) &
            (edited_df['orden'].astype(str) == str(_orden))
        ]
        if _match.empty:
            continue
        r = _match.iloc[0]
        precio_r = pd.to_numeric(r.get('precio_real'), errors='coerce')
        cant_r   = pd.to_numeric(r.get('cant_real'), errors='coerce')
        valor_r  = (precio_r * cant_r) if pd.notna(precio_r) and pd.notna(cant_r) else pd.to_numeric(r.get('valor_real'), errors='coerce')
        valor_p  = pd.to_numeric(row[col_idx['valor_ppto']], errors='coerce') if row[col_idx['valor_ppto']] != '' else np.nan
        dif      = (valor_r - valor_p) if pd.notna(valor_r) and pd.notna(valor_p) else np.nan

        _sheet_row = i + 1  # 1-indexed; all_vals[0] es la fila de encabezados (sheet row 1)
        for field, val in [('precio_real', precio_r), ('cant_real', cant_r),
                           ('valor_real', valor_r), ('diferencia', dif)]:
            _col = col_idx[field] + 1
            updates.append({
                'range': gspread.utils.rowcol_to_a1(_sheet_row, _col),
                'values': [[_gs_to_str(val)]],
            })
    if updates:
        ws.batch_update(updates)

_KML_PATHS = {
    'La Merced':   os.path.join(_DATA_DIR, 'la_merced.kml'),
    'Pillahuinco': os.path.join(_DATA_DIR, 'pillahuinco.kml'),
}

# ── Colores por actividad ────────────────────────────────────────────────────
_COLORES = {
    'Maíz':          '#F9A825', 'Soja':         '#558B2F',
    'Girasol':       '#FDD835', 'Trigo':         '#A1887F',
    'Cebada':        '#BCAAA4', 'Invernada':     '#1565C0',
    'Cría':          '#6A1B9A', 'Tambo':         '#00838F',
    'Pastura':       '#2E7D32', 'Campo Natural':  '#795548',
    'Verdeo':        '#00897B', 'Sin dato':       '#9E9E9E',
}

def _color(actividad):
    return _COLORES.get(actividad, '#9E9E9E')


# ── Parser KML → GeoJSON ─────────────────────────────────────────────────────
_KML_NS = 'http://www.opengis.net/kml/2.2'

def _kml_to_geojson(kml_path):
    """Convierte KML en un dict GeoJSON FeatureCollection."""
    tree = ET.parse(kml_path)
    root = tree.getroot()
    features = []
    for pm in root.iter(f'{{{_KML_NS}}}Placemark'):
        name_el = pm.find(f'{{{_KML_NS}}}name')
        name = name_el.text.strip() if name_el is not None and name_el.text else 'Sin nombre'

        coords_el = pm.find(f'.//{{{_KML_NS}}}coordinates')
        if coords_el is None or not coords_el.text:
            continue
        coords = []
        for token in coords_el.text.strip().split():
            parts = token.split(',')
            if len(parts) >= 2:
                try:
                    coords.append([float(parts[0]), float(parts[1])])
                except ValueError:
                    pass
        if len(coords) < 3:
            continue
        if coords[0] != coords[-1]:
            coords.append(coords[0])
        features.append({
            'type': 'Feature',
            'properties': {'name': name},
            'geometry': {'type': 'Polygon', 'coordinates': [coords]},
        })
    return {'type': 'FeatureCollection', 'features': features}


def _geojson_bounds(geojson):
    lats, lons = [], []
    for feat in geojson['features']:
        for lon, lat in feat['geometry']['coordinates'][0]:
            lats.append(lat); lons.append(lon)
    if not lats:
        return None
    return [[min(lats), min(lons)], [max(lats), max(lons)]]


def _polygon_area_ha(coords):
    """Área aproximada (hectáreas) de un polígono [lon,lat] vía proyección equirectangular local."""
    if len(coords) < 3:
        return 0.0
    _R = 6378137.0  # radio terrestre medio (m)
    lat0 = math.radians(sum(c[1] for c in coords) / len(coords))
    pts = [(math.radians(lon) * _R * math.cos(lat0), math.radians(lat) * _R) for lon, lat in coords]
    area = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0 / 10000.0  # m² → ha


@st.cache_data(ttl=3600, show_spinner=False)
def _get_kml_areas(campo):
    """{ambiente_id: ha} calculado desde los polígonos del KML del campo."""
    kml_path = _KML_PATHS.get(campo)
    if not kml_path or not os.path.exists(kml_path):
        return {}
    gj = _kml_to_geojson(kml_path)
    areas = {}
    for feat in gj['features']:
        name = feat['properties'].get('name', '')
        amb_id = name.lower().replace(' ', '_')
        areas[amb_id] = _polygon_area_ha(feat['geometry']['coordinates'][0])
    return areas


# ── Carga de datos ───────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner="Cargando ambientes...")
def _get_ambientes():
    if URL_AMBIENTES:
        return pd.read_csv(URL_AMBIENTES)
    if os.path.exists(_LOCAL_AMB):
        return pd.read_csv(_LOCAL_AMB)
    return pd.DataFrame(columns=['campo','lote_id','lote_nombre','ambiente_id','ambiente_nombre','ha'])


_HDR_COLS = ['planteo_id','campo','lote_id','ambiente_id','campaña','actividad',
             'ha','escenario','fecha_siembra','fecha_cosecha','referencia_id','referencia','nota']
_LIN_COLS = ['planteo_id','mes','seccion','orden','item','unidad',
             'precio_ppto','cant_ppto','valor_ppto',
             'precio_real','cant_real','valor_real','diferencia','nota']
_REF_HDR_COLS = ['referencia_id','cultivo','campaña','fuente','fecha_publicacion','zona','nota']
_REF_LIN_COLS = ['referencia_id','seccion','orden','item','unidad','precio','cantidad','valor','nota']


def _csv_load(url, local, cols):
    if url:
        try:
            df = pd.read_csv(url)
            if not df.empty and df.shape[1] >= 5:
                return df
        except Exception:
            pass
    if os.path.exists(local):
        return pd.read_csv(local)
    return pd.DataFrame(columns=cols)


@st.cache_data(ttl=300, show_spinner="Cargando planteos (Google Sheets)...")
def _get_header():
    df = _gs_read_df(_WS_HEADER, _HDR_COLS)
    if not df.empty and 'ha' in df.columns:
        df['ha'] = pd.to_numeric(df['ha'], errors='coerce')
    return df


@st.cache_data(ttl=300, show_spinner="Cargando líneas (Google Sheets)...")
def _get_lineas():
    df = _gs_read_df(_WS_LINEAS, _LIN_COLS)
    _num_cols = ['orden', 'precio_ppto', 'cant_ppto', 'valor_ppto',
                 'precio_real', 'cant_real', 'valor_real', 'diferencia']
    for c in _num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
    return df


@st.cache_data(ttl=3600, show_spinner="Cargando planteos de referencia...")
def _get_ref_header():
    return _csv_load(URL_REF_HDR, _LOCAL_REF_HDR, _REF_HDR_COLS)


@st.cache_data(ttl=3600, show_spinner="Cargando líneas de referencia...")
def _get_ref_lineas():
    return _csv_load(URL_REF_LIN, _LOCAL_REF_LIN, _REF_LIN_COLS)


# ── Generación de planteo_id y escritura local ───────────────────────────────
_CAMPO_PREFIX = {'La Merced': 'LM', 'Pillahuinco': 'PM'}
_CULTIVO_PREFIX = {
    'Maíz': 'MAI', 'Soja': 'SOJ', 'Girasol': 'GIR', 'Trigo': 'TRI',
    'Cebada': 'CEB', 'Invernada': 'INV', 'Cría': 'CRI', 'Tambo': 'TAM',
    'Pastura': 'PAS', 'Campo Natural': 'CNA', 'Verdeo': 'VER',
}


def _campaña_prefix(campaña):
    return re.sub(r'\D', '', str(campaña))


def _gen_planteo_id(campo, cultivo, campaña, df_hdr_existente):
    cp = _CAMPO_PREFIX.get(campo, re.sub(r'[^A-Z]', '', campo.upper())[:2] or 'XX')
    kp = _CULTIVO_PREFIX.get(cultivo, re.sub(r'[^A-Z]', '', cultivo.upper())[:3] or 'XXX')
    camp = _campaña_prefix(campaña)
    prefix = f"{cp}_{kp}_{camp}_"
    existentes = df_hdr_existente['planteo_id'].astype(str) if not df_hdr_existente.empty else pd.Series(dtype=str)
    seqs = [int(pid[len(prefix):]) for pid in existentes if pid.startswith(prefix) and pid[len(prefix):].isdigit()]
    seq = (max(seqs) + 1) if seqs else 1
    return f"{prefix}{seq:03d}"


def _get_planteos_flat():
    """Join lineas + header → vista plana para tabs existentes."""
    df_hdr = _get_header()
    df_lin = _get_lineas()
    if df_hdr.empty or df_lin.empty:
        return pd.DataFrame()
    _join = ['planteo_id','campo','lote_id','ambiente_id','campaña','actividad','ha','escenario']
    return df_lin.merge(df_hdr[_join], on='planteo_id', how='left')


df_amb = _get_ambientes()
df_hdr = _get_header()
df_lin = _get_lineas()
df_ref_hdr = _get_ref_header()
df_ref_lin = _get_ref_lineas()
df_pln = _get_planteos_flat()

# ── Header ───────────────────────────────────────────────────────────────────
st.title("🗺️ Lotes y Ambientes")
col_h, col_ref = st.columns([8, 1])
col_h.markdown("Gestión de lotes por campo — mapa, planteos técnicos y control presupuestario.")
if col_ref.button("🔄 Actualizar", help="Limpiar cache"):
    _get_ambientes.clear(); _get_header.clear(); _get_lineas.clear()
    _get_ref_header.clear(); _get_ref_lineas.clear()
    st.rerun()

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

    st.divider()
    st.caption("**Leyenda actividades**")
    for act, col in _COLORES.items():
        if act != 'Sin dato':
            st.markdown(
                f'<span style="background:{col};padding:2px 8px;border-radius:4px;'
                f'color:white;font-size:11px">{act}</span> ',
                unsafe_allow_html=True
            )

# Breadcrumb
_parts = [p for p in [sel_campo, sel_lote, sel_amb] if p != "(Todos)"]
if _parts:
    st.caption("📍 " + " › ".join(_parts))

# ── Tabs principales ─────────────────────────────────────────────────────────
# Se usa segmented_control en vez de st.tabs(): st.tabs() no persiste la tab
# activa de forma confiable cuando conviven componentes custom (folium) con
# selectbox dinámicos en otras tabs — resetea a la primera en cada rerun.
_main_tab = st.segmented_control(
    "Sección", ["🗺️ Mapa", "📋 Planteo", "📊 Analíticos"],
    default="🗺️ Mapa", key='main_tab', label_visibility='collapsed',
)

# ════════════════════════════════════════════════════════════════════════════
# TAB MAPA
# ════════════════════════════════════════════════════════════════════════════
if _main_tab == "🗺️ Mapa":
    # Determinar qué campos mostrar
    campos_show = [sel_campo] if sel_campo != "(Todos)" and sel_campo in _KML_PATHS else list(_KML_PATHS.keys())

    # Actividad por ambiente para colorear
    _df_map = df_pln.copy()
    if sel_camp != "(Todas)":
        _df_map = _df_map[_df_map['campaña'] == sel_camp]
    _act_por_amb = _df_map.groupby('ambiente_id')['actividad'].first().to_dict() if not _df_map.empty else {}

    # Ambientes destacados (selección del sidebar)
    _highlight_ids = set()
    if sel_amb != "(Todos)":
        row = df_amb[df_amb['ambiente_nombre'] == sel_amb]
        if not row.empty:
            _highlight_ids = {row.iloc[0]['ambiente_id']}
    elif sel_lote != "(Todos)":
        _highlight_ids = set(df_amb[df_amb['lote_nombre'] == sel_lote]['ambiente_id'])

    # Primera pasada: recopilar GeoJSON y bounds de todos los campos
    _geojsons = {}
    all_lats, all_lons = [], []
    for campo_name in campos_show:
        kml_path = _KML_PATHS.get(campo_name)
        if not kml_path or not os.path.exists(kml_path):
            continue
        gj = _kml_to_geojson(kml_path)
        _geojsons[campo_name] = gj
        b = _geojson_bounds(gj)
        if b:
            all_lats.extend([b[0][0], b[1][0]])
            all_lons.extend([b[0][1], b[1][1]])

    # Centro y zoom calculados desde los bounds (sin fit_bounds)
    if all_lats:
        _clat = (min(all_lats) + max(all_lats)) / 2
        _clon = (min(all_lons) + max(all_lons)) / 2
        _zoom = 8 if len(_geojsons) > 1 else 11
    else:
        _clat, _clon, _zoom = -37.0, -61.0, 8

    m = folium.Map(location=[_clat, _clon], zoom_start=_zoom, tiles='CartoDB positron')

    # Segunda pasada: agregar capas GeoJSON
    for campo_name, gj in _geojsons.items():
        def _style(feat, _a=_act_por_amb, _h=_highlight_ids):
            name = feat['properties'].get('name', '')
            amb_id = name.lower().replace(' ', '_')
            act = _a.get(amb_id, 'Sin dato')
            is_hi = amb_id in _h
            return {
                'fillColor': _color(act),
                'color':     '#E65100' if is_hi else '#333',
                'weight':    3 if is_hi else 1.2,
                'fillOpacity': 0.75 if is_hi else 0.55,
            }

        folium.GeoJson(
            gj,
            name=campo_name,
            style_function=_style,
            tooltip=folium.GeoJsonTooltip(
                fields=['name'],
                aliases=['Lote/Ambiente:'],
                localize=True,
            ),
        ).add_to(m)

    folium.LayerControl().add_to(m)
    _map_key = "mapa_" + "_".join(sorted(campos_show)) + f"_z{_zoom}"
    st_folium(m, width=870, height=580, returned_objects=[], key=_map_key)

# ════════════════════════════════════════════════════════════════════════════
# TAB PLANTEO
# ════════════════════════════════════════════════════════════════════════════
elif _main_tab == "📋 Planteo":
    # ── Derivar planteo local desde una Referencia (Revista Márgenes, etc.) ──
    with st.expander("➕ Derivar planteo local desde una Referencia", expanded=df_hdr.empty):
        if df_ref_hdr.empty:
            st.caption(
                "No hay planteos de referencia cargados todavía. "
                "Pasame un screenshot de la Revista Márgenes (u otra fuente) en el chat y te los cargo acá."
            )
        else:
            def _ref_label(row):
                partes = [row['cultivo'], row['campaña']]
                if pd.notna(row.get('zona')) and str(row.get('zona')).strip():
                    partes.append(f"({row['zona']})")
                _rinde_match = re.search(r'rinde \w+ [\d.]+ qq/ha', str(row.get('nota', '')))
                if _rinde_match:
                    partes.append(f"· {_rinde_match.group(0)}")
                partes.append(f"[{row['referencia_id']}]")
                return ' '.join(str(p) for p in partes)

            _ref_f = df_ref_hdr.copy()
            _ref_f['_label'] = _ref_f.apply(_ref_label, axis=1)
            _ref_labels = _ref_f['_label'].tolist()
            _ref_ids = _ref_f['referencia_id'].tolist()

            _sel_ref_label = st.selectbox("Planteo de referencia", _ref_labels, key='deriv_ref')
            _sel_ref_id = _ref_ids[_ref_labels.index(_sel_ref_label)]
            _ref_row = _ref_f[_ref_f['referencia_id'] == _sel_ref_id].iloc[0]

            df_ref_lin_sel = df_ref_lin[df_ref_lin['referencia_id'] == _sel_ref_id].sort_values(['seccion', 'orden'])

            if df_ref_lin_sel.empty:
                st.warning("Esta referencia no tiene líneas cargadas.")
            else:
                st.caption(f"Base: **{_sel_ref_label}** · {len(df_ref_lin_sel)} líneas (US$/ha)")

                dc1, dc2, dc3, dc4 = st.columns(4)
                _campos_disp = sorted(df_amb['campo'].dropna().unique()) if not df_amb.empty else list(_CAMPO_PREFIX.keys())
                _d_campo = dc1.selectbox("Campo destino", _campos_disp, key='deriv_campo')

                _kml_areas = _get_kml_areas(_d_campo)

                _lotes_campo = ["(campo entero)"] + sorted(
                    df_amb[df_amb['campo'] == _d_campo]['lote_nombre'].dropna().unique()
                ) if not df_amb.empty else ["(campo entero)"]
                _d_lote = dc2.selectbox("Lote", _lotes_campo, key='deriv_lote')

                _amb_f = df_amb[(df_amb['campo'] == _d_campo) & (df_amb['lote_nombre'] == _d_lote)] if _d_lote != "(campo entero)" else pd.DataFrame()
                _ambs_lote = ["(lote entero)"] + sorted(_amb_f['ambiente_nombre'].dropna().unique()) if not _amb_f.empty else ["(lote entero)"]
                _d_amb = dc3.selectbox("Ambiente", _ambs_lote, key='deriv_ambiente', disabled=(_d_lote == "(campo entero)"))

                # Hectáreas: default calculado del polígono KML (ambiente > lote > campo), editable/sobre-escribible
                if _d_lote == "(campo entero)":
                    _amb_ids = df_amb[df_amb['campo'] == _d_campo]['ambiente_id'].tolist()
                elif _d_amb == "(lote entero)":
                    _amb_ids = _amb_f['ambiente_id'].tolist()
                else:
                    _amb_ids = _amb_f[_amb_f['ambiente_nombre'] == _d_amb]['ambiente_id'].tolist()
                _ha_default = round(sum(_kml_areas.get(a, 0.0) for a in _amb_ids), 1)
                # Key depende de la selección: así el default se refresca al cambiar campo/lote/ambiente,
                # pero un valor editado a mano se preserva mientras no cambie la selección.
                _ha_key = f'deriv_ha__{_d_campo}__{_d_lote}__{_d_amb}'
                _d_ha = dc4.number_input("Hectáreas", min_value=0.0, value=_ha_default, step=1.0, key=_ha_key,
                                          help="Calculado desde el polígono KML. Editable si el área real difiere.")

                dc5, dc6, dc7 = st.columns(3)
                _d_escenario = dc5.selectbox("Escenario", ["Planificado", "Real"], key='deriv_escenario')
                _d_siembra = dc6.date_input("Fecha siembra", value=None, key='deriv_siembra')
                _d_cosecha = dc7.date_input("Fecha cosecha", value=None, key='deriv_cosecha')

                _d_nota = st.text_input("Nota (opcional)", key='deriv_nota')

                st.markdown("**Ajustá escala de costos/rindes antes de crear el planteo:**")
                _df_preview = df_ref_lin_sel[['seccion', 'orden', 'item', 'unidad', 'precio', 'cantidad', 'valor', 'nota']].copy()
                _df_edit = st.data_editor(
                    _df_preview, use_container_width=True, hide_index=True,
                    num_rows="dynamic", key='deriv_editor',
                )

                if st.button("✅ Crear planteo local", key='deriv_submit'):
                    _cultivo = _ref_row['cultivo']
                    _campaña = _ref_row['campaña']
                    _new_id = _gen_planteo_id(_d_campo, _cultivo, _campaña, df_hdr)

                    if _d_lote == "(campo entero)":
                        _lote_id_val, _amb_id_val = "(campo entero)", "(campo entero)"
                    else:
                        _lote_id_val = _amb_f['lote_id'].iloc[0] if not _amb_f.empty else _d_lote
                        if _d_amb == "(lote entero)":
                            _amb_id_val = "(lote entero)"
                        else:
                            _match_amb = _amb_f[_amb_f['ambiente_nombre'] == _d_amb]
                            _amb_id_val = _match_amb['ambiente_id'].iloc[0] if not _match_amb.empty else _d_amb

                    _hdr_row = {
                        'planteo_id': _new_id, 'campo': _d_campo,
                        'lote_id': _lote_id_val, 'ambiente_id': _amb_id_val,
                        'campaña': _campaña, 'actividad': _cultivo,
                        'ha': _d_ha, 'escenario': _d_escenario,
                        'fecha_siembra': _d_siembra.isoformat() if _d_siembra else '',
                        'fecha_cosecha': _d_cosecha.isoformat() if _d_cosecha else '',
                        'referencia_id': _sel_ref_id,
                        'referencia': _sel_ref_label,
                        'nota': _d_nota,
                    }

                    _lin_rows = []
                    for _, r in _df_edit.iterrows():
                        precio = pd.to_numeric(r.get('precio'), errors='coerce')
                        cantidad = pd.to_numeric(r.get('cantidad'), errors='coerce')
                        valor = (precio * cantidad) if pd.notna(precio) and pd.notna(cantidad) else pd.to_numeric(r.get('valor'), errors='coerce')
                        _lin_rows.append({
                            'planteo_id': _new_id, 'mes': '',
                            'seccion': r.get('seccion'), 'orden': r.get('orden'),
                            'item': r.get('item'), 'unidad': r.get('unidad'),
                            'precio_ppto': precio, 'cant_ppto': cantidad, 'valor_ppto': valor,
                            'precio_real': None, 'cant_real': None, 'valor_real': None,
                            'diferencia': None, 'nota': r.get('nota', ''),
                        })

                    _gs_append_rows(_WS_HEADER, _HDR_COLS, _hdr_row)
                    _gs_append_rows(_WS_LINEAS, _LIN_COLS, _lin_rows)
                    _get_header.clear(); _get_lineas.clear()
                    # Recargar en memoria (sin rerun explícito, para no perder el tab activo)
                    df_hdr = _get_header()
                    df_lin = _get_lineas()
                    df_pln = _get_planteos_flat()
                    st.session_state['plt_id_pending'] = _new_id
                    st.success(f"✅ Planteo local **{_new_id}** creado a partir de {_sel_ref_label} ({_d_ha:.0f} ha).")

    st.divider()

    if df_hdr.empty or df_lin.empty:
        if not _SHEET_ID:
            st.info("Sin `sheet_id` configurado en `.streamlit/secrets.toml` (sección `[planteos]`).")
        else:
            st.info(
                "Sin planteos locales todavía. Derivá uno desde una Referencia con el formulario de arriba "
                "— se va a guardar en las pestañas `Planteos` / `Lineas` del Google Sheet."
            )
        st.stop()

    # ── Selector de planteo por ID ───────────────────────────────────────────
    # Filtrar header según sidebar
    _hdr_f = df_hdr.copy()
    if sel_campo != "(Todos)":
        _hdr_f = _hdr_f[_hdr_f['campo'] == sel_campo]
    if sel_camp != "(Todas)":
        _hdr_f = _hdr_f[_hdr_f['campaña'] == sel_camp]
    if sel_act:
        _hdr_f = _hdr_f[_hdr_f['actividad'].isin(sel_act)]

    if _hdr_f.empty:
        st.warning("Sin planteos para la selección actual.")
        st.stop()

    # Etiquetas legibles para el selector
    def _label(row):
        partes = [row['planteo_id'], '—', row['campo'], '·', row['actividad'], row['campaña'], row['escenario']]
        if pd.notna(row.get('ha')) and str(row.get('ha')).strip():
            partes.append(f"({row['ha']} ha)")
        return ' '.join(str(p) for p in partes)

    _hdr_f = _hdr_f.copy()
    _hdr_f['_label'] = _hdr_f.apply(_label, axis=1)
    _ids   = _hdr_f['planteo_id'].tolist()
    _labels = _hdr_f['_label'].tolist()

    _pending_id = st.session_state.pop('plt_id_pending', None)
    if _pending_id and _pending_id in _ids:
        st.session_state['plt_id'] = _labels[_ids.index(_pending_id)]

    _sel_label = st.selectbox("Planteo", _labels, key='plt_id')
    _sel_id    = _ids[_labels.index(_sel_label)]
    _hdr_sel   = _hdr_f[_hdr_f['planteo_id'] == _sel_id].iloc[0]

    # ── Info del planteo seleccionado ────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("ID", _sel_id)
    c2.metric("Campo", _hdr_sel['campo'])
    c3.metric("Actividad", f"{_hdr_sel['actividad']} {_hdr_sel['campaña']}")
    c4.metric("Hectáreas", f"{_hdr_sel['ha']} ha" if pd.notna(_hdr_sel.get('ha')) else "—")
    c5.metric("Escenario", _hdr_sel['escenario'])

    _ref = _hdr_sel.get('referencia','')
    _f_siem = _hdr_sel.get('fecha_siembra','')
    _f_cos  = _hdr_sel.get('fecha_cosecha','')
    _meta = []
    if pd.notna(_ref) and str(_ref).strip():   _meta.append(f"Referencia: **{_ref}**")
    if pd.notna(_f_siem) and str(_f_siem).strip(): _meta.append(f"Siembra: {_f_siem}")
    if pd.notna(_f_cos) and str(_f_cos).strip():   _meta.append(f"Cosecha: {_f_cos}")
    if _meta:
        st.caption(" · ".join(_meta))

    st.divider()

    # ── Líneas del planteo ───────────────────────────────────────────────────
    df_lin_sel = df_lin[df_lin['planteo_id'] == _sel_id].sort_values(['seccion','orden','mes'])

    if df_lin_sel.empty:
        st.warning("Sin líneas para este planteo.")
        st.stop()

    # ── Cargar / editar ejecución (valor real) ───────────────────────────────
    with st.expander("✏️ Cargar ejecución (valor real)", expanded=False):
        st.caption("Editá precio/cantidad/valor **real** por línea. Ppto queda fijo como referencia.")
        _df_exec = df_lin_sel[[
            'mes', 'seccion', 'orden', 'item', 'unidad',
            'precio_ppto', 'cant_ppto', 'valor_ppto',
            'precio_real', 'cant_real', 'valor_real', 'nota',
        ]].copy()
        _exec_edit = st.data_editor(
            _df_exec, use_container_width=True, hide_index=True, num_rows="fixed",
            disabled=['mes', 'seccion', 'orden', 'item', 'unidad', 'precio_ppto', 'cant_ppto', 'valor_ppto'],
            key=f'exec_editor_{_sel_id}',
        )

        if st.button("💾 Guardar ejecución", key=f'exec_save_{_sel_id}'):
            _gs_update_lineas_real(_sel_id, _exec_edit)
            _get_lineas.clear()
            df_lin = _get_lineas()
            df_pln = _get_planteos_flat()
            df_lin_sel = df_lin[df_lin['planteo_id'] == _sel_id].sort_values(['seccion', 'orden', 'mes'])
            st.success("✅ Ejecución guardada en Google Sheets.")

    _tiene_mes = df_lin_sel['mes'].notna().any() and (df_lin_sel['mes'].astype(str).str.strip() != '').any()
    _tiene_ppto = df_lin_sel['valor_ppto'].notna().any()

    # Sub-tabs Planteo
    if _tiene_mes:
        ptab_res, ptab_tl = st.tabs(["📋 Resumen", "📅 Timeline"])
    else:
        ptab_res = st.container()

    # ── Resumen ──────────────────────────────────────────────────────────────
    with ptab_res if _tiene_mes else ptab_res:
        _df_res = df_lin_sel[df_lin_sel['mes'].isna() | (df_lin_sel['mes'].astype(str).str.strip() == '')]
        if _df_res.empty:
            _df_res = df_lin_sel.groupby(['seccion','orden','item','unidad'])[
                ['valor_ppto','valor_real']].sum().reset_index()

        _ha_sel = pd.to_numeric(_hdr_sel.get('ha'), errors='coerce')
        _tiene_ha = pd.notna(_ha_sel) and _ha_sel > 0

        if _tiene_ha:
            _modo_val = st.radio(
                "Mostrar valores en", ["US$/ha", f"US$ total ({_ha_sel:.0f} ha)"],
                horizontal=True, key='plt_modo_val',
            )
            _es_total = _modo_val.startswith("US$ total")
        else:
            _es_total = False
        _mult = float(_ha_sel) if _es_total else 1.0
        _unid_lbl = "US$" if _es_total else "US$/ha"

        def _color_diff(val):
            try:
                v = float(val)
                return 'color: #C62828' if v > 0 else ('color: #43A047' if v < 0 else '')
            except Exception:
                return ''

        for seccion, df_sec in _df_res.groupby('seccion', sort=False):
            _es_ing = seccion == 'Ingresos'
            st.markdown(
                f"<span style='font-weight:700;color:{'#43A047' if _es_ing else '#E53935'}'>"
                f"{'▲' if _es_ing else '▼'} {seccion.upper()}</span>",
                unsafe_allow_html=True,
            )
            rows = []
            for _, r in df_sec.sort_values('orden').iterrows():
                dif = (r.get('valor_real', np.nan) or np.nan) - (r.get('valor_ppto', np.nan) or np.nan)
                rows.append({
                    'Mes':           r.get('mes', '') or '',
                    'Ítem':          r['item'],
                    'Unidad':        r.get('unidad', ''),
                    f'Ppto ({_unid_lbl})': (r.get('valor_ppto', np.nan) or np.nan) * _mult,
                    f'Real ({_unid_lbl})': (r.get('valor_real', np.nan) or np.nan) * _mult,
                    'Diferencia':    (dif * _mult) if pd.notna(dif) else np.nan,
                    'Nota':          r.get('nota', '') or '',
                })
            df_t = pd.DataFrame(rows)
            _fmt = {f'Ppto ({_unid_lbl})': '{:,.1f}', f'Real ({_unid_lbl})': '{:,.1f}', 'Diferencia': '{:+,.1f}'}
            _show_cols = [c for c in df_t.columns if c != 'Mes' or _tiene_mes]
            st.dataframe(
                df_t[_show_cols].style.map(_color_diff, subset=['Diferencia']).format(_fmt, na_rep='—'),
                use_container_width=True, hide_index=True,
            )

        # KPIs
        st.divider()
        _ing_r = _df_res[_df_res['seccion']=='Ingresos']['valor_real'].sum() * _mult
        _cos_r = _df_res[_df_res['seccion'].str.startswith('Costos')]['valor_real'].sum() * _mult
        _mb_r  = _ing_r - _cos_r
        _ing_p = _df_res[_df_res['seccion']=='Ingresos']['valor_ppto'].sum() * _mult
        _cos_p = _df_res[_df_res['seccion'].str.startswith('Costos')]['valor_ppto'].sum() * _mult
        _mb_p  = _ing_p - _cos_p
        _suf = "" if _es_total else "/ha"

        k1, k2, k3, k4 = st.columns(4)
        if _tiene_ppto:
            k1.metric("Ingresos ppto", f"U$S {_ing_p:,.0f}{_suf}")
            k2.metric("Costos ppto",   f"U$S {_cos_p:,.0f}{_suf}")
            k3.metric("MB ppto",       f"U$S {_mb_p:+,.0f}{_suf}")
            k4.metric("MB real vs ppto", f"U$S {_mb_r - _mb_p:+,.0f}{_suf}",
                      delta_color="normal" if _mb_r >= _mb_p else "inverse")
        else:
            k1.metric("Ingresos", f"U$S {_ing_r:,.0f}{_suf}")
            k2.metric("Costos Directos", f"U$S {_cos_r:,.0f}{_suf}")
            k3.metric("Margen Bruto", f"U$S {_mb_r:+,.0f}{_suf}",
                      delta_color="normal" if _mb_r > 0 else "inverse")
            k4.metric("Ha totales", f"{_hdr_sel['ha']}" if pd.notna(_hdr_sel.get('ha')) else "—")

    # ── Timeline ─────────────────────────────────────────────────────────────
    if _tiene_mes:
        with ptab_tl:
            _df_tl = df_lin_sel[df_lin_sel['mes'].notna() & (df_lin_sel['mes'].astype(str).str.strip() != '')].copy()
            _df_tl['signo'] = _df_tl['seccion'].apply(lambda s: 1 if s == 'Ingresos' else -1)
            _df_tl['valor_signed'] = _df_tl['valor_real'].fillna(0) * _df_tl['signo']

            # Ordenar meses cronológicamente
            _meses_ord = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']
            _df_tl['mes_ord'] = _df_tl['mes'].apply(
                lambda m: _meses_ord.index(str(m).strip()[:3].capitalize())
                if str(m).strip()[:3].capitalize() in _meses_ord else 99
            )
            _df_tl = _df_tl.sort_values('mes_ord')

            # Colores: ingresos verdes, costos rojos
            _items_i = sorted(_df_tl[_df_tl['seccion']=='Ingresos']['item'].unique())
            _items_c = sorted(_df_tl[_df_tl['seccion']!='Ingresos']['item'].unique())
            _g = ['#1B5E20','#2E7D32','#43A047','#66BB6A','#A5D6A7']
            _r = ['#B71C1C','#C62828','#E53935','#EF5350','#EF9A9A','#FFCDD2','#FFEBEE']
            _cmap = {it: _g[i % len(_g)] for i, it in enumerate(_items_i)}
            _cmap.update({it: _r[i % len(_r)] for i, it in enumerate(_items_c)})

            fig_tl = px.bar(
                _df_tl, x='mes', y='valor_signed', color='item',
                barmode='relative',
                color_discrete_map=_cmap,
                title=f"Flujo mensual — {_sel_id}",
                labels={'valor_signed': 'US$/ha', 'mes': 'Mes', 'item': 'Ítem'},
                category_orders={'mes': [m for m in _meses_ord if m in _df_tl['mes'].values]},
            )
            fig_tl.add_hline(y=0, line_color='#555', line_width=1.2)
            fig_tl.update_layout(height=420)
            st.plotly_chart(fig_tl, use_container_width=True)

            # Tabla mes a mes
            _tl_pivot = _df_tl.groupby(['mes','seccion'])['valor_real'].sum().reset_index()
            _tl_pivot = _tl_pivot.pivot_table(index='mes', columns='seccion', values='valor_real', aggfunc='sum').fillna(0)
            if 'Ingresos' in _tl_pivot.columns and any(c.startswith('Costos') for c in _tl_pivot.columns):
                _cos_cols = [c for c in _tl_pivot.columns if c.startswith('Costos')]
                _tl_pivot['MB'] = _tl_pivot['Ingresos'] - _tl_pivot[_cos_cols].sum(axis=1)
            st.dataframe(_tl_pivot.style.format('{:,.1f}', na_rep='—'), use_container_width=True)

# ════════════════════════════════════════════════════════════════════════════
# TAB ANALÍTICOS
# ════════════════════════════════════════════════════════════════════════════
elif _main_tab == "📊 Analíticos":
    if df_pln.empty:
        st.warning(
            f"Sin datos de planteos. "
            f"Google Sheet: {'configurado' if _SHEET_ID else '❌ sin `sheet_id` en secrets'} "
            f"(pestañas `{_WS_HEADER}` / `{_WS_LINEAS}`)."
        )
        st.stop()

    # ── Helper: MB por campo/actividad/campaña ────────────────────────────────
    def _mb_por_cultivo(df):
        ing = (df[df['seccion'] == 'Ingresos']
               .groupby(['campo', 'actividad', 'campaña'])['valor_real']
               .sum().rename('ingresos'))
        cos = (df[df['seccion'].str.startswith('Costos')]
               .groupby(['campo', 'actividad', 'campaña'])['valor_real']
               .sum().rename('costos'))
        mb = pd.concat([ing, cos], axis=1).fillna(0)
        mb['mb'] = mb['ingresos'] - mb['costos']
        return mb.reset_index()

    df_mb = _mb_por_cultivo(df_pln)

    # ── Sub-tabs ──────────────────────────────────────────────────────────────
    atab_res, atab_wf, atab_sens = st.tabs([
        "🏁 Resumen & Ranking", "🌊 Descomposición", "🎯 Sensibilidad",
    ])

    # ════════════════════════════════════════════════════════════════════════
    # RESUMEN & RANKING
    # ════════════════════════════════════════════════════════════════════════
    with atab_res:
        if df_mb.empty:
            st.warning("Sin datos para calcular MB.")
            st.stop()

        _best  = df_mb.loc[df_mb['mb'].idxmax()]
        _worst = df_mb.loc[df_mb['mb'].idxmin()]

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Cultivos analizados", len(df_mb))
        k2.metric(
            f"Mejor · {_best['campo']} {_best['actividad']}",
            f"U$S {_best['mb']:+,.0f}/ha",
        )
        k3.metric(
            f"Peor · {_worst['campo']} {_worst['actividad']}",
            f"U$S {_worst['mb']:+,.0f}/ha",
        )
        k4.metric("Promedio MB/ha", f"U$S {df_mb['mb'].mean():+,.0f}/ha")

        st.divider()

        # ── Tabla semáforo ────────────────────────────────────────────────────
        st.subheader("Semáforo de Márgenes Brutos")

        def _semaforo(mb):
            if mb > 100: return "🟢"
            if mb > 0:   return "🟡"
            return "🔴"

        def _color_mb_cell(val):
            try:
                v = float(val)
                if v > 100: return 'background-color:#C8E6C9;color:#1B5E20'
                if v > 0:   return 'background-color:#FFF9C4;color:#7B6200'
                return 'background-color:#FFCDD2;color:#B71C1C'
            except Exception:
                return ''

        df_tabla = df_mb.copy()
        df_tabla.insert(0, '', df_tabla['mb'].apply(_semaforo))
        df_tabla = df_tabla[['', 'campo', 'actividad', 'campaña', 'ingresos', 'costos', 'mb']]
        df_tabla.columns = ['', 'Campo', 'Cultivo', 'Campaña', 'Ingresos', 'Costos', 'MB']
        df_tabla = df_tabla.sort_values('MB', ascending=False)

        st.dataframe(
            df_tabla.style
                .map(_color_mb_cell, subset=['MB'])
                .format({'Ingresos': 'U$S {:,.0f}', 'Costos': 'U$S {:,.0f}', 'MB': 'U$S {:+,.0f}'}),
            use_container_width=True,
            hide_index=True,
        )

        st.divider()

        # ── Ranking horizontal ────────────────────────────────────────────────
        st.subheader("Ranking MB/ha")

        df_rank = df_mb.sort_values('mb').copy()
        df_rank['label'] = df_rank['campo'] + ' · ' + df_rank['actividad'] + ' ' + df_rank['campaña']

        fig_rank = go.Figure(go.Bar(
            x=df_rank['mb'],
            y=df_rank['label'],
            orientation='h',
            marker_color=df_rank['mb'].apply(lambda x: '#43A047' if x > 0 else '#E53935'),
            text=df_rank['mb'].apply(lambda x: f'U$S {x:+,.0f}/ha'),
            textposition='outside',
        ))
        fig_rank.add_vline(x=0, line_color='#555', line_width=1.5)
        fig_rank.update_layout(
            title='Ranking de Márgenes Brutos (US$/ha)',
            xaxis_title='US$/ha', yaxis_title='',
            height=max(300, len(df_rank) * 55 + 80),
            showlegend=False,
            margin=dict(l=200, r=120),
        )
        st.plotly_chart(fig_rank, use_container_width=True)

        st.divider()

        # ── Ingresos vs Costos con MB superpuesto ─────────────────────────────
        st.subheader("Ingresos vs Costos — visión comparada")

        df_ic = df_mb.copy()
        df_ic['label'] = df_ic['campo'] + '<br>' + df_ic['actividad'] + ' ' + df_ic['campaña']

        fig_ic = go.Figure()
        fig_ic.add_trace(go.Bar(
            name='Ingresos', x=df_ic['label'], y=df_ic['ingresos'],
            marker_color='#43A047',
            text=df_ic['ingresos'].apply(lambda x: f'{x:,.0f}'),
            textposition='inside', textfont=dict(color='white'),
        ))
        fig_ic.add_trace(go.Bar(
            name='Costos', x=df_ic['label'], y=df_ic['costos'],
            marker_color='#E53935',
            text=df_ic['costos'].apply(lambda x: f'{x:,.0f}'),
            textposition='inside', textfont=dict(color='white'),
        ))
        fig_ic.add_trace(go.Scatter(
            name='MB', x=df_ic['label'], y=df_ic['mb'],
            mode='markers+text',
            marker=dict(
                size=16, symbol='diamond',
                color=df_ic['mb'].apply(lambda x: '#2E7D32' if x > 0 else '#B71C1C'),
                line=dict(width=2, color='white'),
            ),
            text=df_ic['mb'].apply(lambda x: f'{x:+,.0f}'),
            textposition='top center',
        ))
        fig_ic.update_layout(
            barmode='group',
            title='Ingresos vs Costos con MB (US$/ha)',
            yaxis_title='US$/ha',
            height=460,
            hovermode='x unified',
        )
        st.plotly_chart(fig_ic, use_container_width=True)

    # ════════════════════════════════════════════════════════════════════════
    # WATERFALL / DESCOMPOSICIÓN
    # ════════════════════════════════════════════════════════════════════════
    with atab_wf:
        col_w1, col_w2, col_w3 = st.columns(3)
        _campos_wf = sorted(df_pln['campo'].unique())
        _acts_wf   = sorted(df_pln['actividad'].unique())
        _camps_wf  = sorted(df_pln['campaña'].unique(), reverse=True)

        sel_w_campo = col_w1.selectbox("Campo", _campos_wf, key='wf_campo')
        sel_w_act   = col_w2.selectbox("Cultivo", _acts_wf, key='wf_act')
        sel_w_camp  = col_w3.selectbox("Campaña", _camps_wf, key='wf_camp')

        df_wf = df_pln[
            (df_pln['campo'] == sel_w_campo) &
            (df_pln['actividad'] == sel_w_act) &
            (df_pln['campaña'] == sel_w_camp)
        ].sort_values(['seccion', 'orden'])

        if df_wf.empty:
            st.warning("Sin datos para esta combinación.")
        else:
            # ── Waterfall ─────────────────────────────────────────────────────
            labels, values, measures = [], [], []

            for _, row in df_wf[df_wf['seccion'] == 'Ingresos'].sort_values('orden').iterrows():
                labels.append(row['item'])
                values.append(float(row['valor_real']) if pd.notna(row['valor_real']) else 0.0)
                measures.append('relative')

            for _, row in df_wf[df_wf['seccion'].str.startswith('Costos')].sort_values('orden').iterrows():
                labels.append(row['item'])
                values.append(-(float(row['valor_real']) if pd.notna(row['valor_real']) else 0.0))
                measures.append('relative')

            labels.append('Margen Bruto')
            values.append(None)
            measures.append('total')

            _mb_color = '#1565C0' if sum(v for v in values if v is not None) > 0 else '#6A1B9A'

            fig_wf = go.Figure(go.Waterfall(
                orientation='v',
                measure=measures,
                x=labels,
                y=values,
                connector={'line': {'color': '#aaa', 'dash': 'dot'}},
                increasing={'marker': {'color': '#43A047'}},
                decreasing={'marker': {'color': '#E53935'}},
                totals={'marker': {'color': _mb_color}},
                text=[f'{v:+.1f}' if v is not None else '' for v in values],
                textposition='outside',
            ))
            fig_wf.add_hline(y=0, line_color='#555', line_width=1.2, line_dash='dash')
            fig_wf.update_layout(
                title=f"Descomposición MB — {sel_w_campo} · {sel_w_act} {sel_w_camp}",
                yaxis_title='US$/ha',
                height=500,
                showlegend=False,
            )
            st.plotly_chart(fig_wf, use_container_width=True)

            # ── Comparación inter-campo: mismo cultivo/campaña ─────────────
            df_todos = df_pln[
                (df_pln['actividad'] == sel_w_act) &
                (df_pln['campaña'] == sel_w_camp)
            ]
            campos_comp = sorted(df_todos['campo'].unique())

            if len(campos_comp) > 1:
                st.divider()
                st.subheader(f"Comparación inter-campo — {sel_w_act} {sel_w_camp}")
                st.caption("Mismo cultivo y campaña en ambos campos: ¿qué explica la diferencia en MB?")

                # Bar apilado relativo: ingresos arriba, costos abajo
                _bars = []
                for campo in campos_comp:
                    df_c = df_todos[df_todos['campo'] == campo]
                    for _, row in df_c.iterrows():
                        signo = 1 if row['seccion'] == 'Ingresos' else -1
                        _bars.append({
                            'campo': campo,
                            'item':  row['item'],
                            'seccion': row['seccion'],
                            'valor': (float(row['valor_real']) if pd.notna(row['valor_real']) else 0.0) * signo,
                        })
                df_bars = pd.DataFrame(_bars)

                # Colores: ingresos en verdes, costos en rojos
                _items_ing = sorted(df_bars[df_bars['seccion']=='Ingresos']['item'].unique())
                _items_cos = sorted(df_bars[df_bars['seccion']!='Ingresos']['item'].unique())
                _greens = ['#1B5E20','#2E7D32','#388E3C','#43A047','#66BB6A','#A5D6A7']
                _reds   = ['#B71C1C','#C62828','#D32F2F','#E53935','#EF5350','#EF9A9A','#FFCDD2','#FFEBEE']
                _color_map = {it: _greens[i % len(_greens)] for i, it in enumerate(_items_ing)}
                _color_map.update({it: _reds[i % len(_reds)] for i, it in enumerate(_items_cos)})

                fig_comp = px.bar(
                    df_bars,
                    x='campo', y='valor', color='item',
                    barmode='relative',
                    title=f"Composición MB por campo — {sel_w_act} {sel_w_camp}",
                    labels={'valor': 'US$/ha', 'campo': '', 'item': 'Ítem'},
                    color_discrete_map=_color_map,
                )
                # Overlay MB como diamante
                _mb_comp = df_mb[
                    (df_mb['actividad'] == sel_w_act) & (df_mb['campaña'] == sel_w_camp)
                ]
                fig_comp.add_trace(go.Scatter(
                    x=_mb_comp['campo'], y=_mb_comp['mb'],
                    mode='markers+text', name='MB',
                    marker=dict(size=18, symbol='diamond', color='#1565C0',
                                line=dict(width=2, color='white')),
                    text=_mb_comp['mb'].apply(lambda x: f'MB {x:+,.0f}'),
                    textposition='top center',
                ))
                fig_comp.add_hline(y=0, line_color='#555', line_width=1.5)
                fig_comp.update_layout(height=480)
                st.plotly_chart(fig_comp, use_container_width=True)

                # ── Diagnóstico cuantitativo (2 campos) ───────────────────
                if len(campos_comp) == 2:
                    c_a, c_b = campos_comp[0], campos_comp[1]
                    _row_a = df_mb[(df_mb['campo']==c_a) & (df_mb['actividad']==sel_w_act) & (df_mb['campaña']==sel_w_camp)]
                    _row_b = df_mb[(df_mb['campo']==c_b) & (df_mb['actividad']==sel_w_act) & (df_mb['campaña']==sel_w_camp)]

                    if not _row_a.empty and not _row_b.empty:
                        _ing_a, _cos_a, _mb_a = _row_a.iloc[0][['ingresos','costos','mb']]
                        _ing_b, _cos_b, _mb_b = _row_b.iloc[0][['ingresos','costos','mb']]

                        _rinde_a = df_todos[(df_todos['campo']==c_a) & (df_todos['item']=='Cosecha')]['cant_real'].mean()
                        _rinde_b = df_todos[(df_todos['campo']==c_b) & (df_todos['item']=='Cosecha')]['cant_real'].mean()

                        d1, d2, d3 = st.columns(3)
                        d1.metric(f"Diferencia MB ({c_b} vs {c_a})",
                                  f"U$S {_mb_b - _mb_a:+,.0f}/ha")
                        d2.metric("Δ Ingresos",
                                  f"U$S {_ing_b - _ing_a:+,.0f}/ha",
                                  f"Rinde: {_rinde_a:.2f} vs {_rinde_b:.2f} tn/ha"
                                  if pd.notna(_rinde_a) and pd.notna(_rinde_b) else None)
                        d3.metric("Δ Costos Directos",
                                  f"U$S {_cos_b - _cos_a:+,.0f}/ha",
                                  delta_color="inverse")

                        _driver = "rendimiento/precio" if abs(_ing_b-_ing_a) > abs(_cos_b-_cos_a) else "estructura de costos"
                        st.info(
                            f"**El principal driver de la diferencia es el {_driver}.** "
                            f"Δ Ingresos: U$S {_ing_b-_ing_a:+,.0f}/ha · "
                            f"Δ Costos: U$S {_cos_b-_cos_a:+,.0f}/ha."
                        )

    # ════════════════════════════════════════════════════════════════════════
    # SENSIBILIDAD
    # ════════════════════════════════════════════════════════════════════════
    with atab_sens:
        st.subheader("Análisis de sensibilidad")
        st.caption("¿Qué pasa con el MB si cambia el precio del grano o el rendimiento?")

        col_s1, col_s2, col_s3 = st.columns(3)
        sel_s_campo = col_s1.selectbox("Campo",    sorted(df_pln['campo'].unique()),    key='sens_campo')
        sel_s_act   = col_s2.selectbox("Cultivo",  sorted(df_pln['actividad'].unique()), key='sens_act')
        sel_s_camp  = col_s3.selectbox("Campaña",  sorted(df_pln['campaña'].unique(), reverse=True), key='sens_camp')

        df_sens = df_pln[
            (df_pln['campo'] == sel_s_campo) &
            (df_pln['actividad'] == sel_s_act) &
            (df_pln['campaña'] == sel_s_camp)
        ]

        if df_sens.empty:
            st.warning("Sin datos para esta combinación.")
        else:
            _cosecha_row = df_sens[df_sens['item'] == 'Cosecha']
            _base_precio = (float(_cosecha_row['precio_real'].dropna().iloc[0])
                            if not _cosecha_row.empty and _cosecha_row['precio_real'].notna().any() else None)
            _base_rinde  = (float(_cosecha_row['cant_real'].dropna().iloc[0])
                            if not _cosecha_row.empty and _cosecha_row['cant_real'].notna().any()  else None)

            _base_ing    = df_sens[df_sens['seccion'] == 'Ingresos']['valor_real'].sum()
            _base_cos    = df_sens[df_sens['seccion'].str.startswith('Costos')]['valor_real'].sum()
            _base_mb     = _base_ing - _base_cos
            _otros_ing   = df_sens[(df_sens['seccion'] == 'Ingresos') & (df_sens['item'] != 'Cosecha')]['valor_real'].sum()

            if _base_precio is None or _base_rinde is None:
                st.warning("No se encontró precio/rendimiento para 'Cosecha'. Verificá los datos.")
            else:
                col_sl1, col_sl2 = st.columns(2)
                with col_sl1:
                    delta_precio_pct = st.slider(
                        f"Δ precio grano (base: U$S {_base_precio:.0f}/tn)",
                        min_value=-50, max_value=50, value=0, step=5, format="%d%%",
                        key='sens_precio_sl',
                    )
                with col_sl2:
                    delta_rinde_pct = st.slider(
                        f"Δ rendimiento (base: {_base_rinde:.2f} tn/ha)",
                        min_value=-50, max_value=50, value=0, step=5, format="%d%%",
                        key='sens_rinde_sl',
                    )

                _new_precio  = _base_precio * (1 + delta_precio_pct / 100)
                _new_rinde   = _base_rinde  * (1 + delta_rinde_pct / 100)
                _new_cosecha = _new_precio * _new_rinde
                _new_mb      = _new_cosecha + _otros_ing - _base_cos

                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Precio grano", f"U$S {_new_precio:.1f}/tn",
                          f"{delta_precio_pct:+d}%")
                k2.metric("Rendimiento",  f"{_new_rinde:.2f} tn/ha",
                          f"{delta_rinde_pct:+d}%")
                k3.metric("Ingreso cosecha", f"U$S {_new_cosecha:.0f}/ha",
                          f"{_new_cosecha - _base_precio * _base_rinde:+.0f}")
                k4.metric("Nuevo MB", f"U$S {_new_mb:+,.0f}/ha",
                          f"{_new_mb - _base_mb:+,.0f} vs base",
                          delta_color="normal" if _new_mb >= _base_mb else "inverse")

                # Punto de equilibrio (descontando otros ingresos)
                _be_precio = (_base_cos - _otros_ing) / _base_rinde
                _be_rinde  = (_base_cos - _otros_ing) / _base_precio
                st.info(
                    f"**Punto de equilibrio:** precio ≥ **U$S {_be_precio:.1f}/tn** "
                    f"(actual U$S {_base_precio:.1f}/tn, {(_base_precio/_be_precio-1)*100:+.0f}% de margen) "
                    f"· rinde ≥ **{_be_rinde:.2f} tn/ha** "
                    f"(actual {_base_rinde:.2f} tn/ha, {(_base_rinde/_be_rinde-1)*100:+.0f}% de margen)"
                )

                st.divider()

                # ── Heatmap precio × rendimiento ──────────────────────────────
                st.subheader("Mapa de calor: precio × rendimiento → MB")
                st.caption("Verde = MB positivo · Rojo = negativo · La estrella ★ marca el escenario seleccionado arriba.")

                _steps = list(range(-40, 45, 10))
                mb_matrix = np.array([
                    [
                        _base_precio * (1 + pp/100) * _base_rinde * (1 + rp/100) + _otros_ing - _base_cos
                        for pp in _steps
                    ]
                    for rp in _steps
                ])
                _x_labels = [f'{p:+d}%' for p in _steps]
                _y_labels = [f'{r:+d}%' for r in _steps]

                fig_hm = go.Figure(go.Heatmap(
                    z=mb_matrix,
                    x=_x_labels,
                    y=_y_labels,
                    colorscale=[
                        [0.0,  '#B71C1C'],
                        [0.45, '#FFCDD2'],
                        [0.50, '#FFFFFF'],
                        [0.55, '#C8E6C9'],
                        [1.0,  '#1B5E20'],
                    ],
                    zmid=0,
                    text=np.vectorize(lambda x: f'{x:+.0f}')(mb_matrix),
                    texttemplate='%{text}',
                    textfont={'size': 9},
                    colorbar={'title': 'MB<br>US$/ha'},
                ))
                # Marcar escenario actual
                _star_x = f'{delta_precio_pct:+d}%'
                _star_y = f'{delta_rinde_pct:+d}%'
                fig_hm.add_trace(go.Scatter(
                    x=[_star_x], y=[_star_y],
                    mode='markers', name='Escenario',
                    marker=dict(size=18, symbol='star', color='white',
                                line=dict(color='#333', width=2)),
                    showlegend=False,
                ))
                fig_hm.update_layout(
                    title=f"MB (US$/ha) — {sel_s_campo} · {sel_s_act} {sel_s_camp}",
                    xaxis_title='Δ Precio grano',
                    yaxis_title='Δ Rendimiento',
                    height=440,
                )
                st.plotly_chart(fig_hm, use_container_width=True)
