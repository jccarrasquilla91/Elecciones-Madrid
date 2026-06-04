import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
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
    df_actual = df_actual[~df_actual['PARNOMBRE'].isin(['CANDIDATOS TOTALES'])]
    df_actual = df_actual[~df_actual['CANNOMBRE'].isin(['CANDIDATOS TOTALES'])]
    
    # Acortar nombres de candidatos para los gráficos estilo tus referentes
# 1. Pasamos TODOS los nombres de la base a formato "Título" automáticamente
    # Esto convierte "SONDRA MACOLLINS" en "Sondra Macollins"
    df_actual['CANNOMBRE_LIMPIO'] = df_actual['CANNOMBRE'].astype(str).str.title()

    # 2. Diccionario de nombres cortos (ahora con las llaves en formato Título)
    mapeo_nombres = {
        'Iván Cepeda Castro': 'Cepeda',
        'Abelardo De La Espriella': 'De la Espriella',
        'Paloma Valencia Laserna': 'P. Valencia',
        'Sergio Fajardo Valderrama': 'Fajardo',
        'Claudia López': 'C. López',
        'Raúl Santiago Botero Jaramillo': 'Botero J.',
        'Óscar Mauricio Lizcano Arango': 'Lizcano',
        'Miguel Uribe Londoño': 'M. Uribe',
        'Luis Gilberto Murillo Urrutia': 'Murillo',
        'Roy Barreras': 'Barreras'
    }
    
    # 3. Aplicamos el mapeo sobre la columna limpia. 
    # Si el candidato no está en el mapa, se queda con su nombre en formato "Sondra Macollins"
    df_actual['CANDIDATO_CORTO'] = df_actual['CANNOMBRE_LIMPIO'].map(mapeo_nombres).fillna(df_actual['CANNOMBRE_LIMPIO'])
    
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

# 3. MAQUETACIÓN EN PESTAÑAS
st.title("🎯 Centro de Analítica Electoral - Madrid, Cundinamarca")
st.write("---")

tab1, tab2 = st.tabs(["🗺️ Mapa Estratégico y Alertas", "📈 Gráficos Avanzados de Dominancia"])

# =========================================================
# PESTAÑA 1: MAPA Y ESTRATEGIA ("CUARTO DE GUERRA")
# =========================================================
with tab1:
    tot_votos_mun = int(df_final['TOTAL_VOTOS_ACTUAL'].sum())
    st.metric("Votos Válidos Municipales (Periodo Actual)", f"{tot_votos_mun:,} votos")
    
    col1, col2 = st.columns([1.8, 1.2])
    with col1:
        st.subheader("Rendimiento Territorial Territorial")
        m = folium.Map(location=[4.7324, -74.2642], zoom_start=13, tiles="CartoDB positron")
        
        for idx, row in df_final.iterrows():
            if row['ES_NUEVO']:
                color_indicador = "#3498DB"  # Azul claro para puestos nuevos
                texto_variacion = "Puesto Nuevo (Sin histórico)"
            else:
                color_indicador = "#C0392B" if row['DELTA_PTS'] < 0 else "#5B2C6F"  # Rojo o Morado
                texto_variacion = f"Variación: {row['DELTA_PTS']:.1f} pts"
            
            popup_html = f"<b>{row['PUESNOMBRE']}</b><br>{texto_variacion}<br><b>Votos Actuales:</b> {int(row['TOTAL_VOTOS_ACTUAL']):,}"
            
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

# =========================================================
# PESTAÑA 2: COMPLEMENTO - GRÁFICOS INTERACTIVOS (PLOTLY)
# =========================================================
with tab2:
    st.subheader("📊 Galería de Inteligencia Analítica Interactiva")
    st.write("Pasa el cursor sobre las barras o celdas para ver el detalle de los votos. Usa la leyenda para filtrar.")
    
    opcion_grafico = st.selectbox("Selecciona la visualización estratégica:", [
        "1. Ranking General de Votos por Candidato",
        "2. Ganador Absoluto por Puesto de Votación",
        "3. Participación Porcentual de cada Candidato por Puesto (Apilado)",
        "4. Mapa de Calor: Dominancia Territorial por Candidato (%)",
        "5. Comparativo de Votos Absolutos por Puesto y Candidato (Matriz)"
    ])
    
    # --- PROCESAMIENTO BASE PARA MATRICES ---
    # Crear la matriz pivoteada de puestos vs candidatos
    matriz_votos = df_actual.pivot_table(index='PUESNOMBRE', columns='CANDIDATO_CORTO', values='VOTOS', aggfunc='sum').fillna(0)
    # Ordenar columnas por los más votados a nivel municipal
    top_cand_global = df_actual.groupby('CANDIDATO_CORTO')['VOTOS'].sum().sort_values(ascending=False).index
    matriz_votos = matriz_votos[top_cand_global].sort_values(by=top_cand_global[0], ascending=False)
    
    # -----------------------------------------------------
    # GRÁFICO 1: RANKING GENERAL (INTERACTIVO)
    # -----------------------------------------------------
    if opcion_grafico == "1. Ranking General de Votos por Candidato":
        ranking_gen = df_actual.groupby('CANDIDATO_CORTO')['VOTOS'].sum().sort_values(ascending=False).reset_index()
        
        fig = px.bar(ranking_gen, x='VOTOS', y='CANDIDATO_CORTO', orientation='h',
                     title="Ranking General de Votos por Candidato",
                     labels={'VOTOS': 'Total de Votos', 'CANDIDATO_CORTO': 'Candidato'},
                     text_auto=',.0f', color='VOTOS', color_continuous_scale='Viridis')
        fig.update_layout(yaxis={'categoryorder':'total ascending'}, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    # -----------------------------------------------------
    # GRÁFICO 2: GANADOR POR PUESTO (INTERACTIVO)
    # -----------------------------------------------------
    elif opcion_grafico == "2. Ganador Absoluto por Puesto de Votación":
        puesto_cand = df_actual.groupby(['PUESNOMBRE', 'CANDIDATO_CORTO'])['VOTOS'].sum().reset_index()
        idx_ganadores = puesto_cand.groupby('PUESNOMBRE')['VOTOS'].idxmax()
        ganadores_puesto = puesto_cand.loc[idx_ganadores].sort_values(by='VOTOS', ascending=True)
        
        fig = px.bar(ganadores_puesto, x='VOTOS', y='PUESNOMBRE', color='CANDIDATO_CORTO',
                     orientation='h', title="Ganador Absoluto por Puesto de Votación",
                     labels={'VOTOS': 'Votos Obtenidos', 'PUESNOMBRE': 'Puesto de Votación', 'CANDIDATO_CORTO': 'Ganador'},
                     color_discrete_map={"Cepeda": "#B03A2E", "De la Espriella": "#2E86C1"},
                     text_auto=',.0f')
        st.plotly_chart(fig, use_container_width=True)

    # -----------------------------------------------------
    # GRÁFICO 3: BARRAS APILADAS % (INTERACTIVO)
    # -----------------------------------------------------
    elif opcion_grafico == "3. Participación Porcentual de cada Candidato por Puesto (Apilado)":
        matriz_porcentaje = matriz_votos.div(matriz_votos.sum(axis=1), axis=0) * 100
        matriz_porcentaje = matriz_porcentaje.reset_index()
        
        # Derretir la matriz para que Plotly la entienda fácilmente
        df_melt = matriz_porcentaje.melt(id_vars='PUESNOMBRE', var_name='Candidato', value_name='Porcentaje')
        
        fig = px.bar(df_melt, x='PUESNOMBRE', y='Porcentaje', color='Candidato',
                     title="Participación Porcentual de cada Candidato por Puesto",
                     labels={'Porcentaje': 'Participación (%)', 'PUESNOMBRE': 'Puesto de Votación'},
                     color_continuous_scale=px.colors.qualitative.Plotly)
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

    # -----------------------------------------------------
    # GRÁFICO 4: HEATMAP PORCENTUAL % (INTERACTIVO)
    # -----------------------------------------------------
    elif opcion_grafico == "4. Mapa de Calor: Dominancia Territorial por Candidato (%)":
        matriz_porcentaje = matriz_votos.div(matriz_votos.sum(axis=1), axis=0) * 100
        
        fig = px.imshow(matriz_porcentaje, text_auto=".1f",
                        aspect="auto", color_continuous_scale="YlOrRd",
                        title="Mapa de Calor: Dominancia Territorial por Candidato (%)",
                        labels=dict(x="Candidato", y="Puesto de votación", color="% de Votos"))
        st.plotly_chart(fig, use_container_width=True)

    # -----------------------------------------------------
    # GRÁFICO 5: HEATMAP ABSOLUTO (INTERACTIVO)
    # -----------------------------------------------------
    elif opcion_grafico == "5. Comparativo de Votos Absolutos por Puesto y Candidato (Matriz)":
        fig = px.imshow(matriz_votos, text_auto=",.0f",
                        aspect="auto", color_continuous_scale="Blues",
                        title="Comparativo de Votos Absolutos por Puesto y Candidato",
                        labels=dict(x="Candidato", y="Puesto de votación", color="Votos Absolutos"))
        st.plotly_chart(fig, use_container_width=True)
