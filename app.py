import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import re

# Configuración de página de Streamlit
st.set_page_config(page_title="Visor Electoral Madrid", layout="wide")

# 1. FUNCIÓN PARA LIMPIAR Y EXTRAER COORDENADAS DEL WKT
def extract_coords(wkt_str):
    if pd.isna(wkt_str):
        return None, None
    match = re.search(r'POINT\s*\(\s*([-\d.]+)\s+([-\d.]+)\s*\)', str(wkt_str))
    if match:
        # Retorna (Latitud, Longitud) -> WKT guarda (Lon Lat)
        return float(match.group(2)), float(match.group(1))
    return None, None

# 2. CARGA Y PROCESAMIENTO DE DATOS
@st.cache_data
def load_data():
    # Cargar base de votación
    df_votos = pd.read_csv("MMV_XXX_15_160_XXX_XX_XX_XXX_2496_normalizado.csv", sep=";", skip_blank_lines=True)
    
    # Cargar base geográfica y limpiar filas de metadatos
    df_geo_raw = pd.read_csv("Mapa sin nombre- Puestos_de_Votacion.csv")
    df_geo = df_geo_raw[df_geo_raw['WKT'].astype(str).str.startswith('POINT')].copy()
    df_geo['latitude'], df_geo['longitude'] = zip(*df_geo['WKT'].apply(extract_coords))
    df_geo = df_geo[['nombre', 'latitude', 'longitude']].rename(columns={'nombre': 'PUESNOMBRE'})
    
    # Calcular Totales y Rankings por puesto
    station_votes = df_votos.groupby('PUESNOMBRE')['VOTOS'].sum().reset_index()
    station_votes = station_votes.sort_values(by='VOTOS', ascending=False).reset_index(drop=True)
    station_votes['RANKING'] = station_votes.index + 1
    
    # Unificar Geografía con Totales
    df_mapa_base = pd.merge(station_votes, df_geo, on='PUESNOMBRE')
    
    return df_votos, df_mapa_base

df_votos, df_mapa_base = load_data()

# 3. INTERFAZ DE USUARIO
st.title("🗳️ Observatorio Electoral Público - Madrid, Cundinamarca")
st.markdown("Herramienta comunitaria de consulta abierta para el análisis de puestos de votación y comportamiento electoral.")
st.write("---")

# Crear diseño de dos columnas (Izquierda: Mapa, Derecha: Estadísticas del puesto)
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Mapa Interactivo de Puestos de Votación")
    
    # Centrar el mapa en el casco urbano de Madrid
    m = folium.Map(location=[4.7324, -74.2642], zoom_start=13, tiles="OpenStreetMap")
    
    # Añadir los marcadores con popups informativos
    for idx, row in df_mapa_base.iterrows():
        # El tamaño del círculo dependerá proporcionalmente del volumen de votación
        radius_size = int(row['VOTOS'] / 350)
        
        popup_html = f"""
        <div style='font-family: Arial, sans-serif; min-width: 200px;'>
            <h4 style='margin:0 0 5px 0; color:#2C3E50;'>{row['PUESNOMBRE']}</h4>
            <hr style='margin:5px 0;'>
            <b>Ranking del Municipio:</b> #{row['RANKING']}<br>
            <b>Total Votos Registrados:</b> {row['VOTOS']:,}<br>
        </div>
        """
        
        folium.CircleMarker(
            location=[row['latitude'], row['longitude']],
            radius=radius_size,
            color='#1A5276',
            fill=True,
            fill_color='#5DADE2',
            fill_opacity=0.7,
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"#{row['RANKING']} - {row['PUESNOMBRE']}"
        ).add_to(m)
        
    # Renderizar mapa folium dentro de Streamlit
    st_folium(m, width="100%", height=550)

with col2:
    st.subheader("📊 Análisis por Puesto")
    
    # Selector de puesto para análisis profundo
    puesto_sel = st.selectbox("Selecciona un Puesto de Votación:", df_mapa_base['PUESNOMBRE'])
    
    # Extraer métricas específicas del puesto
    datos_puesto = df_mapa_base[df_mapa_base['PUESNOMBRE'] == puesto_sel].iloc[0]
    df_filtrado = df_votos[df_votos['PUESNOMBRE'] == puesto_sel]
    
    st.metric(label="Ranking de Votación", value=f"#{datos_puesto['RANKING']} de 21")
    st.metric(label="Total Votos en este Puesto", value=f"{datos_puesto['VOTOS']:,} votos")
    
    # Análisis 1: Top Partidos en el puesto seleccionado
    st.markdown("### Top 5 Partidos Políticos")
    top_partidos = df_filtrado.groupby('PARNOMBRE')['VOTOS'].sum().nlargest(5).reset_index()
    st.bar_chart(data=top_partidos, x='PARNOMBRE', y='VOTOS', color="#2E86C1")
    
    # Análisis 2: Mesas más activas
    st.markdown("### Distribución de Votos por Mesa")
    votos_mesas = df_filtrado.groupby('MESA')['VOTOS'].sum().reset_index()
    st.line_chart(data=votos_mesas, x='MESA', y='VOTOS', color="#E67E22")