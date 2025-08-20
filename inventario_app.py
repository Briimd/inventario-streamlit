import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Control de Faltantes y Excedentes", layout="wide")
st.title("📦 App de Inventario: Faltantes y Excedentes")

# Paso 1: Cargar el archivo Excel
archivo = st.file_uploader("Sube el archivo de inventario (.xlsx o .csv)", type=["xlsx", "csv"])

if archivo:
    # Leer el archivo dependiendo de la extensión
    if archivo.name.endswith(".csv"):
        df = pd.read_csv(archivo)
    else:
        df = pd.read_excel(archivo)

    st.subheader("Vista previa del archivo cargado")
    st.dataframe(df.head())

    # Validar columnas necesarias
    columnas_requeridas = ["SUCURSAL", "CODIGO", "EXISTENCIA", "MAXIMO", "COSTO", "PESO", "CUADRO BASICO", "DESCRIPCION"]
    if not all(col in df.columns for col in columnas_requeridas):
        st.error(f"Faltan columnas requeridas. Asegúrate de incluir: {', '.join(columnas_requeridas)}")
    else:
        # Filtrar solo artículos con CUADRO BASICO en S, P, O o vacío
        df_filtrado = df[df["CUADRO BASICO"].isin(["S", "P", "O"]) | df["CUADRO BASICO"].isna()].copy()

        # Calcular faltantes solo para S y P
        df_filtrado["Faltante"] = 0
        mask_sp = df_filtrado["CUADRO BASICO"].isin(["S", "P"])
        df_filtrado.loc[mask_sp, "Faltante"] = df_filtrado.loc[mask_sp, "MAXIMO"] - df_filtrado.loc[mask_sp, "EXISTENCIA"]
        df_filtrado["Faltante"] = df_filtrado["Faltante"].clip(lower=0)
        df_faltantes = df_filtrado[df_filtrado["Faltante"] > 0].copy()

        # Calcular excedentes
        df_filtrado["Excedente"] = 0
        mask_o_blanco = df_filtrado["CUADRO BASICO"].isin(["O"]) | df_filtrado["CUADRO BASICO"].isna()
        df_filtrado.loc[mask_sp, "Excedente"] = df_filtrado.loc[mask_sp, "EXISTENCIA"] - df_filtrado.loc[mask_sp, "MAXIMO"]
        df_filtrado.loc[mask_sp, "Excedente"] = df_filtrado.loc[mask_sp, "Excedente"].clip(lower=0)
        df_filtrado.loc[mask_o_blanco, "Excedente"] = df_filtrado.loc[mask_o_blanco, "EXISTENCIA"]
        df_excedentes = df_filtrado[df_filtrado["Excedente"] > 0].copy()

        # Cruzar faltantes con excedentes para sugerir traspasos
        sugerencias = []
        for _, faltante_row in df_faltantes.iterrows():
            cod = faltante_row["CODIGO"]
            desc = faltante_row["DESCRIPCION"]
            suc_faltante = faltante_row["SUCURSAL"]
            faltan = faltante_row["Faltante"]
            costo_faltante = faltante_row["COSTO"]
            peso_unit = faltante_row["PESO"]

            # Buscar excedentes del mismo código en otras sucursales con costo <= al de la sucursal con faltante
            candidatos = df_excedentes[(df_excedentes["CODIGO"] == cod) &
                                        (df_excedentes["SUCURSAL"] != suc_faltante) &
                                        (df_excedentes["COSTO"] <= costo_faltante)]

            for _, ex_row in candidatos.iterrows():
                sugerido = min(faltan, ex_row["Excedente"])
                faltante_restante = faltan - sugerido
                estado = "✅ Cubierto" if faltante_restante <= 0 else "❗ Aún falta"
                sugerencias.append({
                    "CODIGO": cod,
                    "DESCRIPCION": desc,
                    "Faltante en": suc_faltante,
                    "Desde Sucursal": ex_row["SUCURSAL"],
                    "Cantidad Sugerida": sugerido,
                    "Faltante Total": faltan,
                    "Faltante Restante": max(faltante_restante, 0),
                    "Estado Faltante": estado,
                    "Costo Origen": ex_row["COSTO"],
                    "Costo Destino": costo_faltante,
                    "Peso Total (kg)": sugerido * peso_unit,
                    "Fecha de Generación": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })

        df_sugerencias = pd.DataFrame(sugerencias)

        # Filtros por sucursal y código
        st.subheader("🔎 Filtros de Sugerencias")
        sucursales = ["Todas"] + sorted(df_sugerencias["Faltante en"].unique().tolist())
        codigos = ["Todos"] + sorted(df_sugerencias["CODIGO"].unique().tolist())
        sucursal_seleccionada = st.selectbox("Filtrar por Sucursal con Faltante:", sucursales)
        codigo_seleccionado = st.selectbox("Filtrar por Código de Artículo:", codigos)

        df_sugerencias_filtrado = df_sugerencias.copy()
        if sucursal_seleccionada != "Todas":
            df_sugerencias_filtrado = df_sugerencias_filtrado[df_sugerencias_filtrado["Faltante en"] == sucursal_seleccionada]
        if codigo_seleccionado != "Todos":
            df_sugerencias_filtrado = df_sugerencias_filtrado[df_sugerencias_filtrado["CODIGO"] == codigo_seleccionado]

        # Mostrar resumen general
        st.subheader("🔎 Resumen General")
        col1, col2, col3 = st.columns(3)
        col1.metric("Artículos con Faltante", len(df_faltantes))
        col2.metric("Artículos con Excedente", len(df_excedentes))
        col3.metric("Sugerencias de Traspaso", len(df_sugerencias_filtrado))

        # Mostrar faltantes
        st.subheader("📉 Lista de Faltantes")
        st.dataframe(df_faltantes[["SUCURSAL", "CODIGO", "DESCRIPCION", "Faltante", "COSTO", "PESO"]])

        # Mostrar excedentes
        st.subheader("📈 Lista de Excedentes")
        st.dataframe(df_excedentes[["SUCURSAL", "CODIGO", "DESCRIPCION", "Excedente", "COSTO"]])

        # Mostrar sugerencias
        st.subheader("🔁 Sugerencias de Traspasos")
        if not df_sugerencias_filtrado.empty:
            st.dataframe(df_sugerencias_filtrado)
            st.download_button("📥 Descargar Sugerencias Filtradas", df_sugerencias_filtrado.to_csv(index=False), "sugerencias_filtradas.csv")
        else:
            st.info("No se encontraron traspasos sugeridos con los filtros seleccionados.")

        # Exportación opcional
        st.download_button("📥 Descargar Faltantes", df_faltantes.to_csv(index=False), "faltantes.csv")
        st.download_button("📥 Descargar Excedentes", df_excedentes.to_csv(index=False), "excedentes.csv")
