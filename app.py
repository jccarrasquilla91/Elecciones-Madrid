import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
import re

st.set_page_config(page_title="Estrategia Electoral Madrid", layout="wide")

# =========================================================
# 1. FUNCIÓN PARA LIMPIAR COORDENADAS WKT
# =========================================================
def extract_coords(wkt_str):
    if pd.isna(wkt_str):
        return None, None
    match = re.search(r'POINT\s*\(\s*([-\d.]+)\s+([-\d.]+)\s*\)', str(wkt_str))
    if match:
        # Retorna (Latitud, Longitud) -> WKT guarda (Lon Lat)
        return float(match.group(2)), float(match.group(1))
    return None, None

# =========================================================
# 2. PROCESAMIENTO Y NORMALIZACIÓN DE DATOS
# =========================================================
@st.cache_data
def load_and_normalize_data():
    # A. Cargar datos actuales
    df_actual = pd.read_csv("MMV_XXX_15_160_XXX_XX_XX_XXX_2496_normalizado.csv", sep=";")
    df_actual = df_actual[~df_actual['PARNOMBRE'].isin(['CANDIDATOS TOTALES'])]
    df_actual = df_actual[~df_actual['CANNOMBRE'].isin(['CANDIDATOS TOTALES'])]
    
    # Estandarizar nombres a formato "Título" (Mayúscula inicial y minúsculas)
    df_actual['CANNOMBRE_LIMPIO'] = df_actual['CANNOMBRE'].astype(str).str.title()
    
    # Diccionario de nombres cortos unificado
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
    df_actual['CANDIDATO_CORTO'] = df_actual['CANNOMBRE_LIMPIO'].map(mapeo_nombres).fillna(df_actual['CANNOMBRE_LIMPIO'])
    
    # B. Cargar datos 2022
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
    
    # C. Procesar Histórico 2022 (Referencia: GUSTAVO PETRO)
    totales_puesto_2022 = df_2022_raw.groupby('PUESNOMBRE_NORM')['VOTOS'].sum().reset_index().rename(columns={'VOTOS': 'TOTAL_VOTOS_2022'})
    petro_2022 = df_2022_raw[df_2022_raw['CANNOMBRE'] == 'GUSTAVO PETRO'].groupby('PUESNOMBRE_NORM')['VOTOS'].sum().reset_index().rename(columns={'VOTOS': 'VOTOS_PETRO_2022'})
    
    df_comp_2022 = pd.merge(totales_puesto_2022, petro_2022, on='PUESNOMBRE_NORM', how='left').fillna(0)
    df_comp_2022['PORCENTAJE_2022'] = (df_comp_2022['VOTOS_PETRO_2022'] / df_comp_2022['TOTAL_VOTOS_2022']) * 100

    # D. Procesar Actualidad
    totales_puesto_act = df_actual.groupby('PUESNOMBRE')['VOTOS'].sum().reset_index().rename(columns={'VOTOS': 'TOTAL_VOTOS_ACTUAL'})
    candidato_act = df_actual[df_actual['PARNOMBRE'] == 'MOVIMIENTO POLÍTICO PACTO HISTÓRICO'].groupby('PUESNOMBRE')['VOTOS'].sum().reset_index().rename(columns={'VOTOS': 'VOTOS_ACTUAL'})
    
    # Extraer la Zona oficial de cada puesto desde la base original
    zonas_puesto = df_actual.groupby('PUESNOMBRE')['ZONA'].first().reset_index()
    
    df_comp_act = pd.merge(totales_puesto_act, candidato_act, on='PUESNOMBRE', how='left').fillna(0)
    df_comp_act = pd.merge(df_comp_act, zonas_puesto, on='PUESNOMBRE', how='left')
    df_comp_act['PORCENTAJE_ACTUAL'] = (df_comp_act['VOTOS_ACTUAL'] / df_comp_act['TOTAL_VOTOS_ACTUAL']) * 100
    
    # E. Unificar Ambas Eras
    df_comp_act['PUESNOMBRE'] = df_comp_act['PUESNOMBRE'].astype(str).str.strip()
    df_estrategia = pd.merge(df_comp_act, df_comp_2022, left_on='PUESNOMBRE', right_on='PUESNOMBRE_NORM', how='left')
    
    df_estrategia['ES_NUEVO'] = df_estrategia['TOTAL_VOTOS_2022'].isna()
    df_estrategia['DELTA_PTS'] = df_estrategia['PORCENTAJE_ACTUAL'] - df_estrategia['PORCENTAJE_2022']
    df_estrategia = df_estrategia.fillna(0)
    
    # F. Cargar Geografía
    df_geo_raw = pd.read_csv("Mapa sin nombre- Puestos_de_Votacion.csv")
    df_geo = df_geo_raw[df_geo_raw['WKT'].astype(str).str.startswith('POINT')].copy()
    df_geo['latitude'], df_geo['longitude'] = zip(*df_geo['WKT'].apply(extract_coords))
    df_geo = df_geo[['nombre', 'latitude', 'longitude']].rename(columns={'nombre': 'PUESNOMBRE'})
    df_geo['PUESNOMBRE'] = df_geo['PUESNOMBRE'].astype(str).str.strip()
    
    return df_actual, pd.merge(df_estrategia, df_geo, on='PUESNOMBRE')

df_actual, df_final = load_and_normalize_data()

# =========================================================
# 3. INTERFAZ GRÁFICA EN PESTAÑAS (TABS)
# =========================================================
st.title("🎯 Centro de Analítica Electoral - Madrid, Cundinamarca")
st.write("---")

tab1, tab2 = st.tabs(["🗺️ Mapa de Zonas y Alertas", "📈 Gráficos Avanzados de Dominancia"])

# ---------------------------------------------------------
# PESTAÑA 1: MAPA Y ESTRATEGIA ("CUARTO DE GUERRA")
# ---------------------------------------------------------
with tab1:
    tot_votos_mun = int(df_final['TOTAL_VOTOS_ACTUAL'].sum())
    st.metric("Votos Válidos Municipales (Periodo Actual)", f"{tot_votos_mun:,} votos")
    
    col1, col2 = st.columns([1.8, 1.2])
    with col1:
        st.subheader("Rendimiento Territorial por Zonas Electorales")
        m = folium.Map(location=[4.7324, -74.2642], zoom_start=12, tiles="CartoDB positron")
        
        # Colores oficiales para las macro-regiones DIVIPOLE de Madrid
        colores_zonas = {
            1: "#27AE60",   # Zona 01 - Occidental (Verde)
            2: "#8E44AD",   # Zona 02 - Centro-Oriental (Morado)
            99: "#D35400"  # Zona 99 - Rural / Puente de Piedra (Naranja)
        }
        
        for idx, row in df_final.iterrows():
            zona_id = int(row.get('ZONA', 1))
            color_zona = colores_zonas.get(zona_id, "#34495E")
            
            if row['ES_NUEVO']:
                texto_variacion = "Puesto Nuevo (Sin histórico)"
            else:
                texto_variacion = f"Variación: {row['DELTA_PTS']:.1f} pts"
            
            popup_html = f"""
            <div style='font-family: Arial, sans-serif;'>
                <h4 style='margin:0; color:{color_zona};'><b>ZONA 0{zona_id if zona_id != 99 else 99}</b></h4>
                <hr style='margin:5px 0;'>
                <b>Puesto:</b> {row['PUESNOMBRE']}<br>
                {texto_variacion}<br>
                <b>Votos Actuales en este Puesto:</b> {int(row['TOTAL_VOTOS_ACTUAL']):,}<br>
            </div>
            """
            
            folium.CircleMarker(
                location=[row['latitude'], row['longitude']],
                radius=int(row['TOTAL_VOTOS_ACTUAL'] / 450) + 4,
                color=color_zona,
                fill=True,
                fill_color=color_zona,
                fill_opacity=0.6,
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=f"Zona 0{zona_id if zona_id != 99 else 99} - {row['PUESNOMBRE']}"
            ).add_to(m)
            
        st_folium(m, width="100%", height=500)
        
        # Leyenda explicativa en pantalla
        st.markdown("""
        <div style="display: flex; gap: 20px; justify-content: center; background-color: #F8F9FA; padding: 10px; border-radius: 5px; margin-top: 10px;">
            <div><span style="color: #27AE60; font-size: 20px;">■</span> <b>Zona 01 (Occidente):</b> 11 Puestos | 138 Mesas</div>
            <div><span style="color: #8E44AD; font-size: 20px;">■</span> <b>Zona 02 (Centro-Oriente):</b> 9 Puestos | 126 Mesas</div>
            <div><span style="color: #D35400; font-size: 20px;">■</span> <b>Zona 99 (Rural):</b> 1 Puesto | 10 Mesas</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("## **Top estratégicos**")
        st.caption("Filtro ejecutivo para toma de decisiones.")
        
        st.markdown("### ⚠️ **Puestos a recuperar**")
        df_recuperar = df_final[(df_final['DELTA_PTS'] < 0) & (df_final['ES_NUEVO'] == False)].sort_values(by='DELTA_PTS')
        if df_recuperar.empty:
            st.success("¡No hay pérdidas registradas frente a 2022!")
        else:
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

# ---------------------------------------------------------
# PESTAÑA 2: COMPLEMENTO - GRÁFICOS INTERACTIVOS (PLOTLY)
# ---------------------------------------------------------
with tab2:
    st.subheader("📊 Galería de Inteligencia Analítica Interactiva")
    st.write("Pasa el cursor sobre los elementos para ver detalles dinámicos. Haz clic en las leyendas para filtrar partidos.")
    
    opcion_grafico = st.selectbox("Selecciona la visualización estratégica:", [
        "1. Ranking General de Votos por Candidato",
        "2. Ganador Absoluto por Puesto de Votación",
        "3. Participación Porcentual de cada Candidato por Puesto (Apilado)",
        "4. Mapa de Calor: Dominancia Territorial por Candidato (%)",
        "5. Comparativo de Votos Absolutos por Puesto y Candidato (Matriz)"
    ])
    
    # --- CONSTRUCCIÓN DE MATRICES PIVOTEADAS ---
    matriz_votos = df_actual.pivot_table(index='PUESNOMBRE', columns='CANDIDATO_CORTO', values='VOTOS', aggfunc='sum').fillna(0)
    top_cand_global = df_actual.groupby('CANDIDATO_CORTO')['VOTOS'].sum().sort_values(ascending=False).index
    matriz_votos = matriz_votos[top_cand_global].sort_values(by=top_cand_global[0], ascending=False)
    
    # Gráfico 1: Ranking General
    if opcion_grafico == "1. Ranking General de Votos por Candidato":
        ranking_gen = df_actual.groupby('CANDIDATO_CORTO')['VOTOS'].sum().sort_values(ascending=False).reset_index()
        fig = px.bar(ranking_gen, x='VOTOS', y='CANDIDATO_CORTO', orientation='h',
                     title="Ranking General de Votos por Candidato",
                     labels={'VOTOS': 'Total de Votos', 'CANDIDATO_CORTO': 'Candidato'},
                     text_auto=',.0f', color='VOTOS', color_continuous_scale='Viridis')
        fig.update_layout(yaxis={'categoryorder':'total ascending'}, showlegend=False, template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)

    # Gráfico 2: Ganador por Puesto
    elif opcion_grafico == "2. Ganador Absoluto por Puesto de Votación":
        puesto_cand = df_actual.groupby(['PUESNOMBRE', 'CANDIDATO_CORTO'])['VOTOS'].sum().reset_index()
        idx_ganadores = puesto_cand.groupby('PUESNOMBRE')['VOTOS'].idxmax()
        ganadores_puesto = puesto_cand.loc[idx_ganadores].sort_values(by='VOTOS', ascending=True)
        
        fig = px.bar(ganadores_puesto, x='VOTOS', y='PUESNOMBRE', color='CANDIDATO_CORTO',
                     orientation='h', title="Ganador Absoluto por Puesto de Votación",
                     labels={'VOTOS': 'Votos Obtenidos', 'PUESNOMBRE': 'Puesto de Votación', 'CANDIDATO_CORTO': 'Ganador'},
                     color_discrete_map={"Cepeda": "#B03A2E", "De la Espriella": "#2E86C1"},
                     text_auto=',.0f')
        fig.update_layout(template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)

    # Gráfico 3: Barras Apiladas
    elif opcion_grafico == "3. Participación Porcentual de cada Candidato por Puesto (Apilado)":
        matriz_porcentaje = matriz_votos.div(matriz_votos.sum(axis=1), axis=0) * 100
        matriz_porcentaje = matriz_porcentaje.reset_index()
        df_melt = matriz_porcentaje.melt(id_vars='PUESNOMBRE', var_name='Candidato', value_name='Porcentaje')
        
        fig = px.bar(df_melt, x='PUESNOMBRE', y='Porcentaje', color='Candidato',
                     title="Participación Porcentual de cada Candidato por Puesto",
                     labels={'Porcentaje': 'Participación (%)', 'PUESNOMBRE': 'Puesto de Votación'},
                     color_discrete_sequence=px.colors.qualitative.Plotly)
        fig.update_layout(xaxis_tickangle=-45, template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)

    # Gráfico 4: Heatmap Porcentual
    elif opcion_grafico == "4. Mapa de Calor: Dominancia Territorial por Candidato (%)":
        matriz_porcentaje = matriz_votos.div(matriz_votos.sum(axis=1), axis=0) * 100
        fig = px.imshow(matriz_porcentaje, text_auto=".1f", aspect="auto", color_continuous_scale="YlOrRd",
                        title="Mapa de Calor: Dominancia Territorial por Candidato (%)",
                        labels=dict(x="Candidato", y="Puesto de votación", color="% de Votos"))
        st.plotly_chart(fig, use_container_width=True)

    # Gráfico 5: Heatmap Absoluto
    elif opcion_grafico == "5. Comparativo de Votos Absolutos por Puesto y Candidato (Matriz)":
        fig = px.imshow(matriz_votos, text_auto=",.0f", aspect="auto", color_continuous_scale="Blues",
                        title="Comparativo de Votos Absolutos por Puesto y Candidato",
                        labels=dict(x="Candidato", y="Puesto de votación", color="Votos Absolutos"))

# --- NUEVO BLOQUE ANALÍTICO EN APP.PY ---
        st.write("---")
        st.subheader("💡 Análisis de Estrategia: La Bolsa de Votos en Disputa")
        st.markdown("""
        En una eventual segunda vuelta o consolidación de fuerzas, los votos de candidatos como **Fajardo, Claudia López y P. Valencia** 
        son el eje decisivo. Aquí se muestra cuántos votos están 'disponibles' en cada zona del municipio:
        """)
        
        # Procesar la bolsa de votos por zona en el código
        df_actual['Alternativos'] = df_actual['CANDIDATO_CORTO'].isin(['Fajardo', 'C. López', 'P. Valencia'])
        df_bolsa = df_actual.groupby(['ZONA', 'CANDIDATO_CORTO'])['VOTOS'].sum().unstack().fillna(0)
        df_bolsa['Bolsa Total'] = df_bolsa.get('Fajardo', 0) + df_bolsa.get('C. López', 0) + df_bolsa.get('P. Valencia', 0)
        df_bolsa = df_bolsa.reset_index()
        
        # Crear un gráfico de barras interactivo con Plotly para esta sección
        fig_bolsa = px.bar(df_bolsa, x='ZONA', y='Bolsa Total', 
                           title="Volumen de Votos Disponibles (Terceras Fuerzas) por Zona",
                           labels={'ZONA': 'Zona Electoral DIVIPOLE', 'Bolsa Total': 'Votos Disponibles'},
                           text_auto=True, color='Bolsa Total', color_continuous_scale='Cividis')
        fig_bolsa.update_layout(xaxis=dict(tickmode='array', tickvals=[1, 2, 99], ticktext=['Zona 01 (Occ)', 'Zona 02 (Ori)', 'Zona 99 (Rural)']))
        st.plotly_chart(fig_bolsa, use_container_width=True)


        
        st.plotly_chart(fig, use_container_width=True)
