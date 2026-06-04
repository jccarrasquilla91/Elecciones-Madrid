import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
import seaborn as sns
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
    mapeo_nombres = {
        'IVÁN CEPEDA CASTRO': 'Cepeda',
        'ABELARDO DE LA ESPRIELLA': 'De la Espriella',
        'PALOMA VALENCIA LASERNA': 'P. Valencia',
        'SERGIO FAJARDO VALDERRAMA': 'Fajardo',
        'CLAUDIA LÓPEZ': 'C. López',
        'RAÚL SANTIAGO BOTERO JARAMILLO': 'Botero J.',
        'ÓSCAR MAURICIO LIZCANO ARANGO': 'Lizcano',
        'MIGUEL URIBE LONDOÑO': 'M. Uribe',
        'LUIS GILBERTO MURILLO URRUTIA': 'Murillo',
        'ROY BARRERAS': 'Barreras'
    }
    df_actual['CANDIDATO_CORTO'] = df_actual['CANNOMBRE'].map(mapeo_nombres).fillna(df_actual['CANNOMBRE'])
    
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
# PESTAÑA 2: COMPLEMENTO - GRÁFICOS AVANZADOS
# =========================================================
with tab2:
    st.subheader("Galería de Inteligencia Analítica")
    st.write("Selecciona una opción del menú para renderizar los gráficos de distribución y cruces matriciales.")
    
    opcion_grafico = st.selectbox("Selecciona la visualización estratégica:", [
        "1. Ranking General de Votos por Candidato",
        "2. Ganador Absoluto por Puesto de Votación",
        "3. Participación Porcentual de cada Candidato por Puesto (Apilado)",
        "4. Mapa de Calor: Dominancia Territorial por Candidato (%)",
        "5. Comparativo de Votos Absolutos por Puesto y Candidato (Matriz)"
    ])
    
    # Gráfico 1: Ranking General
    if opcion_grafico == "1. Ranking General de Votos por Candidato":
        ranking_gen = df_actual.groupby('CANDIDATO_CORTO')['VOTOS'].sum().sort_values(ascending=False).reset_index()
        fig, ax = plt.subplots(figsize=(10, 5))
        sns.barplot(data=ranking_gen, x='VOTOS', y='CANDIDATO_CORTO', palette="tab10", ax=ax)
        for index, value in enumerate(ranking_gen['VOTOS']):
            ax.text(value + 100, index, f"{value:,}", va='center', fontsize=10)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        plt.title("Ranking general de votos por candidato\nMadrid, Cundinamarca", fontsize=12, fontweight='bold', pad=15)
        plt.xlabel("Total de votos")
        plt.ylabel("Candidato")
        st.pyplot(fig)

    # Gráfico 2: Ganador por Puesto
    elif opcion_grafico == "2. Ganador Absoluto por Puesto de Votación":
        puesto_cand = df_actual.groupby(['PUESNOMBRE', 'CANDIDATO_CORTO'])['VOTOS'].sum().reset_index()
        idx_ganadores = puesto_cand.groupby('PUESNOMBRE')['VOTOS'].idxmax()
        ganadores_puesto = puesto_cand.loc[idx_ganadores].sort_values(by='VOTOS', ascending=False)
        
        fig, ax = plt.subplots(figsize=(12, 7))
        colores_ganadores = {"Cepeda": "#B03A2E", "De la Espriella": "#2E86C1"}
        sns.barplot(data=ganadores_puesto, x='VOTOS', y='PUESNOMBRE', hue='CANDIDATO_CORTO', palette=colores_ganadores, dodge=False, ax=ax)
        for index, row in enumerate(ganadores_puesto.itertuples()):
            ax.text(row.VOTOS + 30, index, f"{row.CANDIDATO_CORTO} ({row.VOTOS:,})", va='center', fontsize=9)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        plt.title("Ganador por puesto de votación\nMadrid, Cundinamarca", fontsize=12, fontweight='bold', pad=15)
        plt.xlabel("Votos del ganador en el puesto")
        plt.ylabel("Puesto de votación")
        st.pyplot(fig)

    # Gráfico 3: Barras Apiladas
    elif opcion_grafico == "3. Participación Porcentual de cada Candidato por Puesto (Apilado)":
        matriz_votos = df_actual.pivot_table(index='PUESNOMBRE', columns='CANDIDATO_CORTO', values='VOTOS', aggfunc='sum').fillna(0)
        matriz_porcentaje = matriz_votos.div(matriz_votos.sum(axis=1), axis=0) * 100
        matriz_porcentaje = matriz_porcentaje.loc[matriz_votos.sum(axis=1).sort_values(ascending=False).index]
        
        fig, ax = plt.subplots(figsize=(14, 7))
        matriz_porcentaje.plot(kind='bar', stacked=True, ax=ax, cmap="tab20")
        plt.title("Participación porcentual de cada candidato por puesto\nMadrid, Cundinamarca", fontsize=12, fontweight='bold', pad=15)
        plt.xticks(rotation=45, ha='right', fontsize=9)
        plt.ylabel("Participación (%)")
        plt.xlabel("Puesto de votación")
        plt.legend(title="Candidato", bbox_to_anchor=(1.01, 1), loc='upper left')
        st.pyplot(fig)

    # Gráfico 4: Heatmap Porcentual
    elif opcion_grafico == "4. Mapa de Calor: Dominancia Territorial por Candidato (%)":
        matriz_votos = df_actual.pivot_table(index='PUESNOMBRE', columns='CANDIDATO_CORTO', values='VOTOS', aggfunc='sum').fillna(0)
        matriz_porcentaje = matriz_votos.div(matriz_votos.sum(axis=1), axis=0) * 100
        top_cand_global = df_actual.groupby('CANDIDATO_CORTO')['VOTOS'].sum().sort_values(ascending=False).index
        matriz_porcentaje = matriz_porcentaje[top_cand_global].sort_values(by=top_cand_global[0], ascending=False)
        
        fig, ax = plt.subplots(figsize=(14, 8))
        sns.heatmap(matriz_porcentaje, annot=True, fmt=".1f", cmap="YlOrRd", linewidths=.5, cbar_kws={'label': '% de votos en el puesto'}, ax=ax)
        plt.title("Mapa de calor: dominancia territorial por candidato (%)\nMadrid, Cundinamarca", fontsize=12, fontweight='bold', pad=15)
        plt.xticks(rotation=35, ha='right')
        plt.xlabel("Candidato")
        plt.ylabel("Puesto de votación")
        st.pyplot(fig)

    # Gráfico 5: Heatmap Absoluto
    elif opcion_grafico == "5. Comparativo de Votos Absolutos por Puesto y Candidato (Matriz)":
        matriz_votos = df_actual.pivot_table(index='PUESNOMBRE', columns='CANDIDATO_CORTO', values='VOTOS', aggfunc='sum').fillna(0)
        top_cand_global = df_actual.groupby('CANDIDATO_CORTO')['VOTOS'].sum().sort_values(ascending=False).index
        matriz_votos = matriz_votos[top_cand_global].sort_values(by=top_cand_global[0], ascending=False)
        
        fig, ax = plt.subplots(figsize=(14, 8))
        sns.heatmap(matriz_votos, annot=True, fmt=",.0f", cmap="Blues", linewidths=.5, cbar_kws={'label': 'Votos absolutos'}, ax=ax)
        plt.title("Comparativo de votos absolutos por puesto y candidato\nMadrid, Cundinamarca", fontsize=12, fontweight='bold', pad=15)
        plt.xticks(rotation=35, ha='right')
        plt.xlabel("Candidato")
        plt.ylabel("Puesto de votación")
        st.pyplot(fig)
