import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import re

st.set_page_config(page_title="Estrategia Electoral Madrid", layout="wide")

# 1. FUNCIÓN PARA LIMPIAR COORDENADAS WKT
def extract_coords(wkt_str):
    if pd.isna(wkt_str):
        return None, None
    match = re.search(r'POINT\s*\(\s*([-\d.]+)\s+([-\d.]+)\s*\)', str(wkt_str))
    if match:
        return float(match.group(2)), float(match.group(1))
    return None, None

# 2. PROCESAMIENTO Y NORMALIZACIÓN DE AMBAS BASES
@st.cache_data
def load_and_normalize_data():
    # Cargar datos actuales
    df_actual = pd.read_csv("MMV_XXX_15_160_XXX_XX_XX_XXX_2496_normalizado.csv", sep=";")
    df_actual = df_actual[df_actual['PARNOMBRE'] != 'CANDIDATOS TOTALES']
    
    # Cargar datos 2022
    df_2022_raw = pd.read_csv("2022.csv", sep=";")
    
    # Diccionario para normalizar los nombres de puestos de 2022
    homologacion = {
        'COLISEO  CUBIERTO MUNICIPAL': 'Coliseo Cubierto Municipal',
        'LICEO HACIENDA CASABLANCA': 'Liceo Hacienda Casablanca',
        'COLEGIO LA MAGNOLIA': 'Escuela La Magnolia',
        'SALON  COMUNAL  ALCAPARROS': 'Salón Comunal Alcaparros',
        'COLEGIO SAN PEDRO': 'Colegio San Pedro',
        'COLEGIO DEPTAL SERREZUELA': 'Colegio Departamental Serrezuela',
        'COLEGIO TIBAITATA': 'Colegio Tibaitatá',
        'COLEGIO MARIA TERESA ORTIZ': 'IED María Teresa Ortíz',
        'I.E.NUESTA SRA DEL LORETO': 'IED Nuestra Señora del Loreto',
        'COLEGIO TECNOLOGICO DE  MADRID': 'Colegio Tecnológico de Madrid',
        'COLEGIO GABRIEL ECHAVARRIA': 'Colegio Gabriel Echavarría',
        'COLEGIO SANTO TOMAS': 'Colegio Técnico Santo Tomás',
        'BLOQUE 2 - COLEGIO TECNOLOGICO': 'Colegio Tecnológico - Bloque 2',
        'COLEGIO  SAN  JOSE': 'IED San José',
        'PUENTE DE PIEDRA': 'IED San Patricio Puente de Piedra'
    }
    # Usamos .str para poder aplicar el método strip() a cada texto de la columna
    df_2022_raw['PUESNOMBRE_NORM'] = df_2022_raw['PUESNOMBRE'].str.strip().map(homologacion).fillna(df_2022_raw['PUESNOMBRE'])
    



    # --- PROCESAR HISTÓRICO 2022 (Ejemplo con candidato GUSTAVO PETRO) ---
    totales_puesto_2022 = df_2022_raw.groupby('PUESNOMBRE_NORM')['VOTOS'].sum().reset_index().rename(columns={'VOTOS': 'TOTAL_VOTOS_2022'})
    petro_2022 = df_2022_raw[df_2022_raw['CANNOMBRE'] == 'GUSTAVO PETRO'].groupby('PUESNOMBRE_NORM')['VOTOS'].sum().reset_index().rename(columns={'VOTOS': 'VOTOS_PETRO_2022'})
    
    df_comp_2022 = pd.merge(totales_puesto_2022, petro_2022, on='PUESNOMBRE_NORM', how='left').fillna(0)
    df_comp_2022['PORCENTAJE_2022'] = (df_comp_2022['VOTOS_PETRO_2022'] / df_comp_2022['TOTAL_VOTOS_2022']) * 100

    # --- PROCESAR ACTUALIDAD ---
    totales_puesto_act = df_actual.groupby('PUESNOMBRE')['VOTOS'].sum().reset_index().rename(columns={'VOTOS': 'TOTAL_VOTOS_ACTUAL'})
    # Asumimos evaluar al Pacto Histórico como continuidad del ejercicio estratégico
    candidato_act = df_actual[df_actual['PARNOMBRE'] == 'MOVIMIENTO POLÍTICO PACTO HISTÓRICO'].groupby('PUESNOMBRE')['VOTOS'].sum().reset_index().rename(columns={'VOTOS': 'VOTOS_ACTUAL'})
    
    df_comp_act = pd.merge(totales_puesto_act, candidato_act, on='PUESNOMBRE', how='left').fillna(0)
    df_comp_act['PORCENTAJE_ACTUAL'] = (df_comp_act['VOTOS_ACTUAL'] / df_comp_act['TOTAL_VOTOS_ACTUAL']) * 100
    
    # --- UNIFICAR AMBAS ERAS ---
    df_estrategia = pd.merge(df_comp_act, df_comp_2022, left_on='PUESNOMBRE', right_on='PUESNOMBRE_NORM', how='left').fillna(0)
    # Variación en puntos porcentuales (Métrica clave del dashboard objetivo)
    df_estrategia['DELTA_PTS'] = df_estrategia['PORCENTAJE_ACTUAL'] - df_estrategia['PORCENTAJE_2022']
    
    # Cargar Geografía
    df_geo_raw = pd.read_csv("Mapa sin nombre- Puestos_de_Votacion.csv")
    df_geo = df_geo_raw[df_geo_raw['WKT'].astype(str).str.startswith('POINT')].copy()
    df_geo['latitude'], df_geo['longitude'] = zip(*df_geo['WKT'].apply(extract_coords))
    df_geo = df_geo[['nombre', 'latitude', 'longitude']].rename(columns={'nombre': 'PUESNOMBRE'})
    
    return df_actual, pd.merge(df_estrategia, df_geo, on='PUESNOMBRE')

df_actual, df_final = load_and_normalize_data()

# 3. MAQUETACIÓN ESTILO DASHBOARD DE SEGUNDA VUELTA
st.title("🎯 Cuarto de Guerra Electoral - Madrid, Cundinamarca")
st.write("---")

# Fila superior de Indicadores (KPI Cards globales)
tot_votos_mun = int(df_final['TOTAL_VOTOS_ACTUAL'].sum())
st.columns(4)[0].metric("Votos Válidos Municipio", f"{tot_votos_mun:,}")

col1, col2 = st.columns([1.8, 1.2])

with col1:
    st.subheader("Mapa de Rendimiento Estratégico")
    m = folium.Map(location=[4.7324, -74.2642], zoom_start=13, tiles="CartoDB positron")
    
    for idx, row in df_final.iterrows():
        # Rojo si cayó en porcentaje de votación, Morado si subió o se mantuvo
        color_indicador = "#C0392B" if row['DELTA_PTS'] < 0 else "#5B2C6F"
        
        popup_html = f"<b>{row['PUESNOMBRE']}</b><br>Variación: {row['DELTA_PTS']:.1f} pts<br>Votos: {int(row['VOTOS_ACTUAL']):,}"
        
        folium.CircleMarker(
            location=[row['latitude'], row['longitude']],
            radius=int(row['TOTAL_VOTOS_ACTUAL'] / 400) + 3,
            color=color_indicador,
            fill=True,
            fill_color=color_indicador,
            fill_opacity=0.6,
            popup=folium.Popup(popup_html, max_width=250)
        ).add_to(m)
        
    st_folium(m, width="100%", height=500)

with col2:
    st.markdown("## **Top estratégicos**")
    st.caption("Recuperar caídas y cuidar volumen.")
    
    # 1. PUESTOS A RECUPERAR (Variación negativa)
    st.markdown("### ⚠️ **Puestos a recuperar**")
    df_recuperar = df_final[df_final['DELTA_PTS'] < 0].sort_values(by='DELTA_PTS')
    if df_recuperar.empty:
        st.success("¡No hay puestos con caídas respecto a 2022!")
    else:
        for _, row in df_recuperar.iterrows():
            st.markdown(f"""
                <div style="display: flex; justify-content: space-between; border-bottom: 1px dotted #BDC3C7; padding: 6px 0;">
                    <span style="color: #2C3E50;">{row['PUESNOMBRE']}</span>
                    <span style="color: #C0392B; font-weight: bold;">{row['DELTA_PTS']:.1f} pts • {int(row['VOTOS_ACTUAL']):,} votos</span>
                </div>
            """, unsafe_allow_html=True)
            
    # 2. PUESTOS DE VOLUMEN (Mayor cantidad de votos absolutos aportados)
    st.markdown("### 📊 **Puestos de volumen**")
    df_volumen = df_final.sort_values(by='VOTOS_ACTUAL', ascending=False).head(5)
    for _, row in df_volumen.iterrows():
        st.markdown(f"""
            <div style="display: flex; justify-content: space-between; border-bottom: 1px dotted #BDC3C7; padding: 6px 0;">
                <span style="color: #2C3E50;">{row['PUESNOMBRE']}</span>
                <span style="color: #1A5276; font-weight: bold;">{row['PORCENTAJE_ACTUAL']:.1f}% • {int(row['VOTOS_ACTUAL']):,} votos</span>
            </div>
        """, unsafe_allow_html=True)

