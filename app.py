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

# 2. PROCESAMIENTO Y NORMALIZACIÓN DE DATOS
@st.cache_data
def load_and_normalize_data():
    # Cargar datos actuales
    df_actual = pd.read_csv("MMV_XXX_15_160_XXX_XX_XX_XXX_2496_normalizado.csv", sep=";")
    # Filtrar filas de control que alteran los totales reales
    df_actual = df_actual[~df_actual['PARNOMBRE'].isin(['CANDIDATOS TOTALES'])]
    df_actual = df_actual[~df_actual['CANNOMBRE'].isin(['CANDIDATOS TOTALES'])]
    
    # Cargar datos 2022
    df_2022_raw = pd.read_csv("2022.csv", sep=";")
    
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
    df_2022_raw['PUESNOMBRE_NORM'] = df_2022_raw['PUESNOMBRE'].str.strip().map(homologacion).fillna(df_2022_raw['PUESNOMBRE'])
    
    # --- PROCESAR HISTÓRICO 2022 (Referencia: GUSTAVO PETRO) ---
    totales_puesto_2022 = df_2022_raw.groupby('PUESNOMBRE_NORM')['VOTOS'].sum().reset_index().rename(columns={'VOTOS': 'TOTAL_VOTOS_2022'})
    petro_2022 = df_2022_raw[df_2022_raw['CANNOMBRE'] == 'GUSTAVO PETRO'].groupby('PUESNOMBRE_NORM')['VOTOS'].sum().reset_index().rename(columns={'VOTOS': 'VOTOS_PETRO_2022'})
    
    df_comp_2022 = pd.merge(totales_puesto_2022, petro_2022, on='PUESNOMBRE_NORM', how='left').fillna(0)
    df_comp_2022['PORCENTAJE_2022'] = (df_comp_2022['VOTOS_PETRO_2022'] / df_comp_2022['TOTAL_VOTOS_2022']) * 100

    # --- PROCESAR ACTUALIDAD ---
    totales_puesto_act = df_actual.groupby('PUESNOMBRE')['VOTOS'].sum().reset_index().rename(columns={'VOTOS': 'TOTAL_VOTOS_ACTUAL'})
    candidato_act = df_actual[df_actual['PARNOMBRE'] == 'MOVIMIENTO POLÍTICO PACTO HISTÓRICO'].groupby('PUESNOMBRE')['VOTOS'].sum().reset_index().rename(columns={'VOTOS': 'VOTOS_ACTUAL'})
    
    df_comp_act = pd.merge(totales_puesto_act, candidato_act, on='PUESNOMBRE', how='left').fillna(0)
    df_comp_act['PORCENTAJE_ACTUAL'] = (df_comp_act['VOTOS_ACTUAL'] / df_comp_act['TOTAL_VOTOS_ACTUAL']) * 100
    
    # --- UNIFICAR AMBAS ERAS ---
    df_comp_act['PUESNOMBRE'] = df_comp_act['PUESNOMBRE'].astype(str).str.strip()
    df_estrategia = pd.merge(df_comp_act, df_comp_2022, left_on='PUESNOMBRE', right_on='PUESNOMBRE_NORM', how='left')
    
    df_estrategia['ES_NUEVO'] = df_estrategia['TOTAL_VOTOS_2022'].isna()
    df_estrategia['DELTA_PTS'] = df_estrategia['PORCENTAJE_ACTUAL'] - df_estrategia['PORCENTAJE_2022']
    df_estrategia = df_estrategia.fillna(0)
    
    # Cargar Geografía
    df_geo_raw = pd.read_csv("Mapa sin nombre- Puestos_de_Votacion.csv")
    df_geo = df_geo_raw[df_geo_raw['WKT'].astype(str).str.startswith('POINT')].copy()
    df_geo['latitude'], df_geo['longitude'] = zip(*df_geo['WKT'].apply(extract_coords))
    df_geo = df_geo[['nombre', 'latitude', 'longitude']].rename(columns={'nombre': 'PUESNOMBRE'})
    df_geo['PUESNOMBRE'] = df_geo['PUESNOMBRE'].astype(str).str.strip()
    
    return df_actual, pd.merge(df_estrategia, df_geo, on='PUESNOMBRE')

df_actual, df_final = load_and_normalize_data()

# 3. INTERFAZ DE PESTAÑAS (TABS)
st.title("🗳️ Centro de Inteligencia Electoral - Madrid")
st.write("---")

# Definición de las pestañas principales
tab1, tab2, tab3 = st.tabs(["🎯 Cuarto de Guerra (General)", "👥 Análisis por Candidato", "🏫 Radiografía de Puestos"])

# ==========================================
# PESTAÑA 1: CUARTO DE GUERRA
# ==========================================
with tab1:
    tot_votos_mun = int(df_final['TOTAL_VOTOS_ACTUAL'].sum())
    st.metric("Votos Válidos Totales en el Municipio", f"{tot_votos_mun:,} votos")
    
    col1, col2 = st.columns([1.8, 1.2])
    with col1:
        st.subheader("Mapa de Rendimiento Territorial")
        m = folium.Map(location=[4.7324, -74.2642], zoom_start=13, tiles="CartoDB positron")
        
        for idx, row in df_final.iterrows():
            if row['ES_NUEVO']:
                color_indicador = "#3498DB"
                texto_variacion = "Puesto Nuevo (Sin histórico)"
            else:
                color_indicador = "#C0392B" if row['DELTA_PTS'] < 0 else "#5B2C6F"
                texto_variacion = f"Variación: {row['DELTA_PTS']:.1f} pts"
            
            popup_html = f"<b>{row['PUESNOMBRE']}</b><br>{texto_variacion}<br><b>Potencial Actual:</b> {int(row['TOTAL_VOTOS_ACTUAL']):,}"
            
            folium.CircleMarker(
                location=[row['latitude'], row['longitude']],
                radius=int(row['TOTAL_VOTOS_ACTUAL'] / 450) + 4,
                color=color_indicador,
                fill=True,
                fill_color=color_indicador,
                fill_opacity=0.6,
                popup=folium.Popup(popup_html, max_width=250)
            ).add_to(m)
        st_folium(m, width="100%", height=500)

    with col2:
        st.markdown("## **Top estratégicos**")
        
        st.markdown("### ⚠️ **Puestos a recuperar**")
        df_recuperar = df_final[(df_final['DELTA_PTS'] < 0) & (df_final['ES_NUEVO'] == False)].sort_values(by='DELTA_PTS')
        for _, row in df_recuperar.iterrows():
            st.markdown(f"""
                <div style="display: flex; justify-content: space-between; border-bottom: 1px dotted #BDC3C7; padding: 6px 0;">
                    <span style="color: #2C3E50;">{row['PUESNOMBRE']}</span>
                    <span style="color: #C0392B; font-weight: bold;">{row['DELTA_PTS']:.1f} pts • {int(row['VOTOS_ACTUAL']):,} votos</span>
                </div>
            """, unsafe_allow_html=True)
            
        st.markdown("### 📊 **Puestos de volumen**")
        df_volumen = df_final.sort_values(by='VOTOS_ACTUAL', ascending=False).head(5)
        for _, row in df_volumen.iterrows():
            st.markdown(f"""
                <div style="display: flex; justify-content: space-between; border-bottom: 1px dotted #BDC3C7; padding: 6px 0;">
                    <span style="color: #2C3E50;">{row['PUESNOMBRE']}</span>
                    <span style="color: #1A5276; font-weight: bold;">{row['PORCENTAJE_ACTUAL']:.1f}% • {int(row['VOTOS_ACTUAL']):,} votos</span>
                </div>
            """, unsafe_allow_html=True)

# ==========================================
# PESTAÑA 2: ANÁLISIS POR CANDIDATO
# ==========================================
with tab2:
    st.subheader("Desglose de Votación por Líder Político")
    st.write("Selecciona un candidato para ver cómo se distribuyeron sus votos en cada infraestructura electoral del municipio.")
    
    # Selector de candidato único de la lista
    lista_candidatos = df_actual['CANNOMBRE'].unique().tolist()
    cand_sel = st.selectbox("Selecciona el Candidato a evaluar:", lista_candidatos)
    
    # Calcular matriz de votación por puesto para ese candidato
    df_cand_puestos = df_actual[df_actual['CANNOMBRE'] == cand_sel].groupby('PUESNOMBRE')['VOTOS'].sum().reset_index()
    
    # Unir con el total del puesto para calcular el peso relativo (%)
    df_cand_puestos = pd.merge(df_cand_puestos, df_final[['PUESNOMBRE', 'TOTAL_VOTOS_ACTUAL']], on='PUESNOMBRE')
    df_cand_puestos['% Participación'] = (df_cand_puestos['VOTOS'] / df_cand_puestos['TOTAL_VOTOS_ACTUAL']) * 100
    df_cand_puestos = df_cand_puestos.sort_values(by='VOTOS', ascending=False).reset_index(drop=True)
    
    # Formatear la tabla para presentación ejecutiva
    df_cand_puestos.columns = ['Puesto de Votación', 'Votos Obtenidos', 'Votos Totales del Puesto', '% de Fuerza']
    
    # Mostrar KPI Global del candidato seleccionado
    votos_tot_cand = df_cand_puestos['Votos Obtenidos'].sum()
    porc_global_cand = (votos_tot_cand / tot_votos_mun) * 100
    
    col_c1, col_c2 = st.columns(2)
    col_c1.metric(f"Votos Totales de {cand_sel}", f"{votos_tot_cand:,} votos")
    col_c2.metric("Porcentaje sobre el total de Madrid", f"{porc_global_cand:.2f}%")
    
    # Gráfico de barras del rendimiento del candidato por puesto
    st.markdown(f"#### Fuerza de {cand_sel} por Puesto de Votación")
    st.bar_chart(data=df_cand_puestos, x='Puesto de Votación', y='Votos Obtenidos', color="#5B2C6F")
    
    # Mostrar tabla interactiva de consulta pública
    st.markdown("#### Tabla Completa de Datos")
    st.dataframe(df_cand_puestos.style.format({'Votos Obtenidos': '{:,}', 'Votos Totales del Puesto': '{:,}', '% de Fuerza': '{:.2f}%'}), use_container_width=True)

# ==========================================
# PESTAÑA 3: RADIOGRAFÍA DE PUESTOS
# ==========================================
with tab3:
    st.subheader("Consulta de Datos por Colegio / Salón Comunal")
    
    puesto_radiografia = st.selectbox("Selecciona un Puesto específico para ver su informe:", df_final['PUESNOMBRE'])
    
    df_puesto_especifico = df_actual[df_actual['PUESNOMBRE'] == puesto_radiografia]
    
    # Agrupar votos por candidatos en ese puesto específico
    votos_cand_puesto = df_puesto_especifico.groupby(['CANNOMBRE', 'PARNOMBRE'])['VOTOS'].sum().reset_index()
    votos_cand_puesto = votos_cand_puesto.sort_values(by='VOTOS', ascending=False).reset_index(drop=True)
    votos_cand_puesto.columns = ['Candidato', 'Partido / Coalición', 'Votos']
    
    col_r1, col_r2 = st.columns([1, 2])
    
    with col_r1:
        st.markdown("#### Resumen del Puesto")
        info_general_puesto = df_final[df_final['PUESNOMBRE'] == puesto_radiografia].iloc[0]
        st.write(f"**Votos Válidos Actuales:** {int(info_general_puesto['TOTAL_VOTOS_ACTUAL']):,}")
        if info_general_puesto['ES_NUEVO']:
            st.info("✨ Este puesto es nuevo para este periodo electoral.")
        else:
            st.write(f"**Variación frente a 2022:** {info_general_puesto['DELTA_PTS']:.2f} puntos")
            
        st.markdown("##### Distribución de Fuerza")
        st.dataframe(votos_cand_puesto.style.format({'Votos': '{:,}'}), use_container_width=True)
        
    with col2:
        st.markdown("#### Distribución de Votos en este Puesto")
        st.bar_chart(data=votos_cand_puesto, x='Candidato', y='Votos', color="#2E86C1")
