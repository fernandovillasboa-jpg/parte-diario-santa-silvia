import os
import io
import datetime
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# ------------------------------------------------------------------------------
# CONFIGURACION GENERAL DE LA ESTANCIA
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="Parte Diario - Estancia Santa Silvia",
    page_icon="🐂",
    layout="wide",
    initial_sidebar_state="expanded"
)

EMPRESA = "SAN LUIS AGRICOLA GANADERA S.A."
ESTANCIA = "ESTANCIA SANTA SILVIA"

SECTORES_LLUVIA = ["CENTRAL", "R PASO ITA"]
EQUIPOS_COMBUSTIBLE = [
    "PALA SEM", "TRACTOR 12", "TRACTOR 9", "TRACTOR 8",
    "SCANIA", "VOLVO", "GENERADOR CONFINAMIENTO", "MAHINDRA",
    "PATRULLA CAP GIMENEZ", "APOYO ARREGLO DE CAMINO CALLE 9", "PATRULLA PASO MBUTU"
]
MAQUINAS_HABITUALES = [
    ("PALA SEM", "LUCIO SANCHEZ", "CARGA DE INSUMO EN CONFINAMIENTO Y LIMPIEZA"),
    ("TRACTOR 12", "EDGARD CRISTALDO", "REPARTO DE RACION EN CONFINAMIENTO"),
    ("TRACTOR 9", "ANGEL SANCHEZ", "ROTATIVEADA / RASTRA"),
    ("TRACTOR 8", "HILARIO GARCIA", "RASTRA CAÑERA / LIMPIEZA")
]
PERSONAL_LISTA = [
    "Nelson Martinez (Ayudante Taller)",
    "Hugo Torales",
    "Angel Sánchez",
    "Evelio Fernandez",
    "Diego Valdez",
    "Oscar Holt",
    "Lorenzo Lopez(jefe personal)",
    "Ramon Chamorro(carpintero)",
    "Eusebio Vera(puntero)"
]
CARGOS_ADM = [
    "COMISARIO",
    "MAYORDOMO",
    "ENCARGADO CONF",
    "CAPATAZ (Silverio V.)",
    "ESTANCIERO (Antonio V.)",
    "RETIRO PASO ITA (Oscar G.)"
]

# ------------------------------------------------------------------------------
# CONEXION A BASE DE DATOS (SUPABASE / POSTGRESQL)
# ------------------------------------------------------------------------------
@st.cache_resource
def get_engine():
    db_url = st.secrets.get("DATABASE_URL", os.environ.get("DATABASE_URL", ""))
    if not db_url:
        st.error("Falta configurar DATABASE_URL en los Secrets de Streamlit Cloud.")
        st.stop()
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    return create_engine(db_url, pool_pre_ping=True)

engine = get_engine()

def run_query(query_str, params=None):
    with engine.connect() as conn:
        return pd.read_sql(text(query_str), conn, params=params)

def execute_sql(query_str, params=None):
    with engine.begin() as conn:
        conn.execute(text(query_str), params or {})

# ------------------------------------------------------------------------------
# IMPORTADOR MAESTRO DESDE EXCEL (NOVIEMBRE 2026.xlsx / FORMATO ESTANCIA)
# ------------------------------------------------------------------------------
def fmt_fecha(val):
    if pd.isna(val):
        return None
    if isinstance(val, (datetime.datetime, datetime.date, pd.Timestamp)):
        return pd.to_datetime(val).strftime("%Y-%m-%d")
    s = str(val).strip()
    if not s or s.lower() == "nan":
        return None
    try:
        return pd.to_datetime(s).strftime("%Y-%m-%d")
    except Exception:
        return s[:10]

def num_val(val, default=0.0):
    if pd.isna(val):
        return default
    try:
        return float(val)
    except Exception:
        return default

def str_val(val, default=""):
    if pd.isna(val):
        return default
    s = str(val).strip()
    return default if s.lower() == "nan" else s

def importar_excel_maestro(uploaded_file, reemplazar_fechas=True):
    xls = pd.ExcelFile(uploaded_file)
    hojas = xls.sheet_names
    resumen = {}

    with engine.begin() as conn:
        # 1. GANADOS
        if "GANADOS" in hojas:
            df = pd.read_excel(xls, sheet_name="GANADOS", header=2)
            df = df[df.iloc[:, 0].notna()].copy()
            fechas_excel = set()
            registros = []
            for _, r in df.iterrows():
                f = fmt_fecha(r.iloc[0])
                act = str_val(r.iloc[1])
                if not f or not act or f == "FECHA":
                    continue
                fechas_excel.add(f)
                registros.append({
                    "fecha": f,
                    "actividad": act,
                    "lote": str_val(r.iloc[2]),
                    "categoria": str_val(r.iloc[3]),
                    "potrero": str_val(r.iloc[4]),
                    "fecha_ultimo_pesaje": fmt_fecha(r.iloc[5]) or f,
                    "pm": num_val(r.iloc[6]),
                    "cantidad": int(num_val(r.iloc[7])),
                    "origen_destino": str_val(r.iloc[9]),
                    "gmd_esperado": num_val(r.iloc[11], 0.4),
                    "consumo_pct_pv": num_val(r.iloc[15], 0.0055)
                })
            if reemplazar_fechas and fechas_excel:
                for f in fechas_excel:
                    conn.execute(text("DELETE FROM ganados_campo WHERE fecha = :f"), {"f": f})
            for reg in registros:
                conn.execute(text("""
                    INSERT INTO ganados_campo
                    (fecha, actividad, lote, categoria, potrero, fecha_ultimo_pesaje, pm, cantidad, origen_destino, gmd_esperado, consumo_pct_pv)
                    VALUES (:fecha, :actividad, :lote, :categoria, :potrero, :fecha_ultimo_pesaje, :pm, :cantidad, :origen_destino, :gmd_esperado, :consumo_pct_pv)
                """), reg)
            resumen["Ganados Campo"] = len(registros)

        # 2. CONFINAMIENTO
        if "CONFINAMIENTO" in hojas:
            df = pd.read_excel(xls, sheet_name="CONFINAMIENTO", header=2)
            df = df[df.iloc[:, 0].notna()].copy()
            count_conf = 0
            for _, r in df.iterrows():
                corral = str_val(r.iloc[0])
                lote = str_val(r.iloc[1])
                if not corral or not lote or corral.upper() in ["CORRAL", "TOTAL"]:
                    continue
                if corral.endswith(".0"):
                    corral = corral[:-2]
                conn.execute(text("""
                    INSERT INTO confinamiento (corral, lote, cantidad, peso_entrada, fecha_entrada, gmd, propietario)
                    VALUES (:corral, :lote, :cantidad, :peso_entrada, :fecha_entrada, :gmd, :propietario)
                    ON CONFLICT (corral) DO UPDATE SET
                        lote = EXCLUDED.lote,
                        cantidad = EXCLUDED.cantidad,
                        peso_entrada = EXCLUDED.peso_entrada,
                        fecha_entrada = EXCLUDED.fecha_entrada,
                        gmd = EXCLUDED.gmd,
                        propietario = EXCLUDED.propietario
                """), {
                    "corral": corral,
                    "lote": lote,
                    "cantidad": int(num_val(r.iloc[2])),
                    "peso_entrada": num_val(r.iloc[3]),
                    "fecha_entrada": fmt_fecha(r.iloc[4]) or datetime.date.today().strftime("%Y-%m-%d"),
                    "gmd": num_val(r.iloc[9], 1.4),
                    "propietario": str_val(r.iloc[10], "SAN LUIS AGSA")
                })
                count_conf += 1
            resumen["Confinamiento (Corrales)"] = count_conf

        # 3. MAQUINARIAS
        if "MAQUINARIAS" in hojas:
            df = pd.read_excel(xls, sheet_name="MAQUINARIAS", header=2)
            df = df[df.iloc[:, 0].notna()].copy()
            fechas_excel = set()
            registros = []
            for _, r in df.iterrows():
                f = fmt_fecha(r.iloc[0])
                maq = str_val(r.iloc[1])
                if not f or not maq or f == "FECHA":
                    continue
                fechas_excel.add(f)
                ini = num_val(r.iloc[4])
                fin = num_val(r.iloc[5])
                hs = num_val(r.iloc[6], max(0.0, fin - ini))
                registros.append({
                    "fecha": f,
                    "maquina": maq,
                    "operador": str_val(r.iloc[2]),
                    "actividad": str_val(r.iloc[3]),
                    "horometro_inicio": ini,
                    "horometro_final": fin,
                    "hs_dia": hs,
                    "combustible_l": num_val(r.iloc[7])
                })
            if reemplazar_fechas and fechas_excel:
                for f in fechas_excel:
                    conn.execute(text("DELETE FROM maquinarias WHERE fecha = :f"), {"f": f})
            for reg in registros:
                conn.execute(text("""
                    INSERT INTO maquinarias
                    (fecha, maquina, operador, actividad, horometro_inicio, horometro_final, hs_dia, combustible_l)
                    VALUES (:fecha, :maquina, :operador, :actividad, :horometro_inicio, :horometro_final, :hs_dia, :combustible_l)
                """), reg)
            resumen["Maquinarias"] = len(registros)

        # 4. CAMIONES
        if "CAMIONES" in hojas:
            df = pd.read_excel(xls, sheet_name="CAMIONES", header=2)
            df = df[df.iloc[:, 0].notna()].copy()
            fechas_excel = set()
            registros = []
            for _, r in df.iterrows():
                f = fmt_fecha(r.iloc[0])
                cam = str_val(r.iloc[1])
                if not f or not cam or f == "FECHA":
                    continue
                fechas_excel.add(f)
                registros.append({
                    "fecha": f,
                    "camion": cam,
                    "destino": str_val(r.iloc[2]),
                    "descripcion_carga": str_val(r.iloc[3]),
                    "kilometraje": num_val(r.iloc[4]),
                    "combustible_l": num_val(r.iloc[5]),
                    "observaciones": str_val(r.iloc[6])
                })
            if reemplazar_fechas and fechas_excel:
                for f in fechas_excel:
                    conn.execute(text("DELETE FROM camiones WHERE fecha = :f"), {"f": f})
            for reg in registros:
                conn.execute(text("""
                    INSERT INTO camiones
                    (fecha, camion, destino, descripcion_carga, kilometraje, combustible_l, observaciones)
                    VALUES (:fecha, :camion, :destino, :descripcion_carga, :kilometraje, :combustible_l, :observaciones)
                """), reg)
            resumen["Camiones"] = len(registros)

        # 5. COMBUSTIBLE (Tabla cruzada: Fecha x Equipos)
        if "COMBUSTIBLE" in hojas:
            df = pd.read_excel(xls, sheet_name="COMBUSTIBLE", header=0)
            cols = list(df.columns)
            fechas_excel = set()
            registros = []
            for _, r in df.iterrows():
                f = fmt_fecha(r.iloc[0])
                if not f or f == "FECHA":
                    continue
                fechas_excel.add(f)
                for idx in range(1, len(cols)):
                    col_name = str(cols[idx]).strip()
                    if col_name.upper().startswith("TOTAL") or col_name.startswith("Unnamed"):
                        continue
                    litros = num_val(r.iloc[idx])
                    if litros > 0:
                        cat = "CAMION" if col_name.upper() in ["SCANIA", "VOLVO"] else (
                            "TRACTOR / PALA" if ("TRACTOR" in col_name.upper() or "PALA" in col_name.upper()) else "GENERADOR / OTROS"
                        )
                        registros.append({
                            "fecha": f,
                            "equipo": col_name.upper(),
                            "categoria": cat,
                            "litros": litros,
                            "horometro_km": 0.0,
                            "observaciones": "Importado desde Excel"
                        })
            if reemplazar_fechas and fechas_excel:
                for f in fechas_excel:
                    conn.execute(text("DELETE FROM combustible WHERE fecha = :f"), {"f": f})
            for reg in registros:
                conn.execute(text("""
                    INSERT INTO combustible (fecha, equipo, categoria, litros, horometro_km, observaciones)
                    VALUES (:fecha, :equipo, :categoria, :litros, :horometro_km, :observaciones)
                """), reg)
            resumen["Combustible"] = len(registros)

        # 6. NUCLEO Y BALANCEADOS
        if "NUCLEO Y BALANCEADOS" in hojas:
            df = pd.read_excel(xls, sheet_name="NUCLEO Y BALANCEADOS", header=2)
            df = df[df.iloc[:, 0].notna()].copy()
            fechas_excel = set()
            registros = []
            for _, r in df.iterrows():
                f = fmt_fecha(r.iloc[0])
                tipo = str_val(r.iloc[1])
                if not f or not tipo or f == "FECHA":
                    continue
                fechas_excel.add(f)
                registros.append({
                    "fecha": f,
                    "tipo": tipo,
                    "produccion_kg": num_val(r.iloc[2]),
                    "destino": str_val(r.iloc[3]),
                    "observaciones": str_val(r.iloc[4])
                })
            if reemplazar_fechas and fechas_excel:
                for f in fechas_excel:
                    conn.execute(text("DELETE FROM balanceados WHERE fecha = :f"), {"f": f})
            for reg in registros:
                conn.execute(text("""
                    INSERT INTO balanceados (fecha, tipo, produccion_kg, destino, observaciones)
                    VALUES (:fecha, :tipo, :produccion_kg, :destino, :observaciones)
                """), reg)
            resumen["Balanceados"] = len(registros)

        # 7. PERSONAL
        if "PERSONAL" in hojas:
            df = pd.read_excel(xls, sheet_name="PERSONAL", header=2)
            df = df[df.iloc[:, 0].notna()].copy()
            fechas_excel = set()
            registros = []
            for _, r in df.iterrows():
                f = fmt_fecha(r.iloc[0])
                pers = str_val(r.iloc[1])
                if not f or not pers or f == "FECHA":
                    continue
                fechas_excel.add(f)
                act = str_val(r.iloc[2])
                asist = str_val(r.iloc[3], "PRESENTE")
                if act.upper() == "AUSENTE":
                    asist = "AUSENTE"
                registros.append({
                    "fecha": f,
                    "personal": pers,
                    "actividad": act,
                    "asistencia": asist
                })
            if reemplazar_fechas and fechas_excel:
                for f in fechas_excel:
                    conn.execute(text("DELETE FROM personal WHERE fecha = :f"), {"f": f})
            for reg in registros:
                conn.execute(text("""
                    INSERT INTO personal (fecha, personal, actividad, asistencia)
                    VALUES (:fecha, :personal, :actividad, :asistencia)
                """), reg)
            resumen["Personal"] = len(registros)

        # 8. ADM (Supervisión)
        if "ADM" in hojas:
            df = pd.read_excel(xls, sheet_name="ADM", header=2)
            cols = list(df.columns)
            fechas_excel = set()
            registros = []
            for _, r in df.iterrows():
                f = fmt_fecha(r.iloc[0])
                if not f or f == "FECHA":
                    continue
                fechas_excel.add(f)
                for idx in range(1, len(cols)):
                    cargo = str(cols[idx]).strip()
                    act = str_val(r.iloc[idx])
                    if act and not cargo.startswith("Unnamed"):
                        registros.append({
                            "fecha": f,
                            "cargo": cargo,
                            "actividad": act
                        })
            if reemplazar_fechas and fechas_excel:
                for f in fechas_excel:
                    conn.execute(text("DELETE FROM adm_supervision WHERE fecha = :f"), {"f": f})
            for reg in registros:
                conn.execute(text("""
                    INSERT INTO adm_supervision (fecha, cargo, actividad)
                    VALUES (:fecha, :cargo, :actividad)
                """), reg)
            resumen["ADM / Supervisión"] = len(registros)

        # 9. LLUVIAS
        if "LLUVIAS" in hojas:
            df = pd.read_excel(xls, sheet_name="LLUVIAS", header=2)
            df = df[df.iloc[:, 0].notna()].copy()
            fechas_excel = set()
            registros = []
            for _, r in df.iterrows():
                f = fmt_fecha(r.iloc[0])
                sec = str_val(r.iloc[1])
                if not f or not sec or f == "FECHA":
                    continue
                fechas_excel.add(f)
                registros.append({
                    "fecha": f,
                    "sector": sec,
                    "precipitacion_mm": num_val(r.iloc[2]),
                    "observaciones": str_val(r.iloc[3])
                })
            if reemplazar_fechas and fechas_excel:
                for f in fechas_excel:
                    conn.execute(text("DELETE FROM lluvias WHERE fecha = :f"), {"f": f})
            for reg in registros:
                conn.execute(text("""
                    INSERT INTO lluvias (fecha, sector, precipitacion_mm, observaciones)
                    VALUES (:fecha, :sector, :precipitacion_mm, :observaciones)
                """), reg)
            resumen["Lluvias"] = len(registros)

        # 10. IMPORTANTES (Novedades)
        if "IMPORTANTES" in hojas:
            df = pd.read_excel(xls, sheet_name="IMPORTANTES", header=2)
            df = df[df.iloc[:, 0].notna()].copy()
            fechas_excel = set()
            registros = []
            for _, r in df.iterrows():
                f = fmt_fecha(r.iloc[0])
                nov = str_val(r.iloc[1])
                if not f or not nov or f == "FECHA":
                    continue
                fechas_excel.add(f)
                registros.append({
                    "fecha": f,
                    "novedad": nov,
                    "prioridad": str_val(r.iloc[2], "MEDIA")
                })
            if reemplazar_fechas and fechas_excel:
                for f in fechas_excel:
                    conn.execute(text("DELETE FROM novedades WHERE fecha = :f"), {"f": f})
            for reg in registros:
                conn.execute(text("""
                    INSERT INTO novedades (fecha, novedad, prioridad)
                    VALUES (:fecha, :novedad, :prioridad)
                """), reg)
            resumen["Novedades Importantes"] = len(registros)

    return resumen

# ------------------------------------------------------------------------------
# EXPORTACION A EXCEL
# ------------------------------------------------------------------------------
def generar_excel(fecha_str=None, mes_prefix=None):
    output = io.BytesIO()
    where_clause = f"WHERE fecha = '{fecha_str}'" if fecha_str else (
        f"WHERE fecha LIKE '{mes_prefix}%'" if mes_prefix else ""
    )
    tablas = {
        "GANADOS": f"SELECT * FROM ganados_campo {where_clause} ORDER BY fecha, id",
        "CONFINAMIENTO": "SELECT * FROM confinamiento ORDER BY corral",
        "MAQUINARIAS": f"SELECT * FROM maquinarias {where_clause} ORDER BY fecha, id",
        "CAMIONES": f"SELECT * FROM camiones {where_clause} ORDER BY fecha, id",
        "COMBUSTIBLE": f"SELECT * FROM combustible {where_clause} ORDER BY fecha, id",
        "BALANCEADOS": f"SELECT * FROM balanceados {where_clause} ORDER BY fecha, id",
        "PERSONAL": f"SELECT * FROM personal {where_clause} ORDER BY fecha, id",
        "ADM": f"SELECT * FROM adm_supervision {where_clause} ORDER BY fecha, id",
        "LLUVIAS": f"SELECT * FROM lluvias {where_clause} ORDER BY fecha, id",
        "NOVEDADES": f"SELECT * FROM novedades {where_clause} ORDER BY fecha, id"
    }
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet, sql in tablas.items():
            df = run_query(sql)
            df.to_excel(writer, sheet_name=sheet, index=False)
    output.seek(0)
    return output

# ------------------------------------------------------------------------------
# AUTENTICACION DE USUARIOS
# ------------------------------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.user_label = ""

if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown(f"## 🐂 {ESTANCIA}")
        st.caption(EMPRESA)
        st.markdown("---")
        user_in = st.text_input("Usuario")
        pass_in = st.text_input("Contraseña", type="password")
        if st.button("Iniciar Sesión", use_container_width=True, type="primary"):
            if user_in.strip().lower() == "admin" and pass_in == "SantaSilvia2026":
                st.session_state.logged_in = True
                st.session_state.role = "admin"
                st.session_state.user_label = "Administrador Estancia"
                st.rerun()
            elif user_in.strip().lower() == "gerencia" and pass_in == "SanLuis2026":
                st.session_state.logged_in = True
                st.session_state.role = "gerencia"
                st.session_state.user_label = "Gerencia / Directorio"
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")
    st.stop()

is_admin = st.session_state.role == "admin"

# ------------------------------------------------------------------------------
# BARRA LATERAL (CONTROLES, EXPORTACION E IMPORTACION EXCEL)
# ------------------------------------------------------------------------------
with st.sidebar:
    st.markdown(f"### 🐂 {ESTANCIA}")
    st.caption(EMPRESA)
    st.info(f"👤 **{st.session_state.user_label}**\n\nPerfil: {'Carga y Edición' if is_admin else 'Solo Lectura'}")

    fecha_sel = st.date_input("📅 Fecha de Consulta / Carga", datetime.date.today())
    fecha_str = fecha_sel.strftime("%Y-%m-%d")
    mes_prefix = fecha_sel.strftime("%Y-%m")

    if st.button("🔄 Actualizar Datos", use_container_width=True):
        st.rerun()

    st.download_button(
        label="📥 Descargar Excel del Día",
        data=generar_excel(fecha_str=fecha_str),
        file_name=f"Parte_Diario_Santa_Silvia_{fecha_str}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

    st.download_button(
        label="📊 Descargar Excel del Mes",
        data=generar_excel(mes_prefix=mes_prefix),
        file_name=f"Consolidado_Mensual_Santa_Silvia_{mes_prefix}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

    if is_admin:
        st.markdown("---")
        st.markdown("### 📤 Importar Excel Maestro")
        archivo_excel = st.file_uploader("Subir planilla (.xlsx)", type=["xlsx"], key="excel_uploader")
        reemplazar_opt = st.checkbox("Reemplazar datos de las fechas del Excel", value=True)
        if archivo_excel is not None:
            if st.button("⚡ Actualizar Sistema desde Excel", type="primary", use_container_width=True):
                with st.spinner("Importando todas las hojas a Supabase..."):
                    try:
                        res = importar_excel_maestro(archivo_excel, reemplazar_fechas=reemplazar_opt)
                        detalle = "\n".join([f"• **{k}:** {v} registros" for k, v in res.items()])
                        st.success(f"¡Importación completada!\n\n{detalle}")
                    except Exception as e:
                        st.error(f"Error al importar Excel: {e}")

    st.markdown("---")
    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.role = None
        st.rerun()

# ------------------------------------------------------------------------------
# ENCABEZADO PRINCIPAL Y PESTAÑAS
# ------------------------------------------------------------------------------
st.markdown(f"## {EMPRESA} — {ESTANCIA}")
st.caption(f"Parte Diario Online en Tiempo Real | Fecha seleccionada: **{fecha_str}**")

tabs = st.tabs([
    "1. RESUMEN DIARIO",
    "2. GANADOS CAMPO",
    "3. CONFINAMIENTO",
    "4. MAQUINARIAS / CAMIONES",
    "5. COMBUSTIBLE",
    "6. BALANCEADOS",
    "7. PERSONAL Y ADM",
    "8. LLUVIAS / NOVEDADES"
])

# ------------------------------------------------------------------------------
# TAB 1: RESUMEN DIARIO + WHATSAPP
# ------------------------------------------------------------------------------
with tabs[0]:
    df_lluvia_hoy = run_query("SELECT * FROM lluvias WHERE fecha = :f", {"f": fecha_str})
    df_lluvia_mes = run_query("SELECT * FROM lluvias WHERE fecha LIKE :m", {"m": f"{mes_prefix}%"})
    df_ganado = run_query("SELECT * FROM ganados_campo WHERE fecha = :f", {"f": fecha_str})
    df_conf = run_query("SELECT * FROM confinamiento ORDER BY corral")
    df_maq = run_query("SELECT * FROM maquinarias WHERE fecha = :f", {"f": fecha_str})
    df_cam = run_query("SELECT * FROM camiones WHERE fecha = :f", {"f": fecha_str})
    df_comb = run_query("SELECT * FROM combustible WHERE fecha = :f", {"f": fecha_str})
    df_bal = run_query("SELECT * FROM balanceados WHERE fecha = :f", {"f": fecha_str})
    df_pers = run_query("SELECT * FROM personal WHERE fecha = :f", {"f": fecha_str})
    df_adm = run_query("SELECT * FROM adm_supervision WHERE fecha = :f", {"f": fecha_str})
    df_nov = run_query("SELECT * FROM novedades WHERE fecha = :f", {"f": fecha_str})

    lluvia_prom_hoy = df_lluvia_hoy["precipitacion_mm"].mean() if not df_lluvia_hoy.empty else 0.0
    lluvia_acum_mes = df_lluvia_mes.groupby("sector")["precipitacion_mm"].sum().mean() if not df_lluvia_mes.empty else 0.0
    total_conf = int(df_conf["cantidad"].sum()) if not df_conf.empty else 0
    total_campo = int(df_ganado["cantidad"].sum()) if not df_ganado.empty else 0
    hs_maq = float(df_maq["hs_dia"].sum()) if not df_maq.empty else 0.0
    kg_bal = float(df_bal["produccion_kg"].sum()) if not df_bal.empty else 0.0
    litros_comb = float(df_comb["litros"].sum()) if not df_comb.empty else 0.0
    pers_presente = int((df_pers["asistencia"].str.upper() == "PRESENTE").sum()) if not df_pers.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🌧️ Lluvia Hoy (Prom.)", f"{lluvia_prom_hoy:.1f} mm")
    c2.metric("🌦️ Lluvia Acum. Mes", f"{lluvia_acum_mes:.1f} mm")
    c3.metric("🚜 Hs Maquinaria Hoy", f"{hs_maq:.1f} hs")
    c4.metric("⛽ Combustible Hoy", f"{litros_comb:,.0f} L")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("🐂 Ganado Confinamiento", f"{total_conf:,} cab.")
    c6.metric("🌿 Ganado a Campo", f"{total_campo:,} cab.")
    c7.metric("🌾 Prod. Balanceado Hoy", f"{kg_bal:,.0f} kg")
    c8.metric("👷 Personal Presente", f"{pers_presente} pers.")

    st.markdown("---")
    col_izq, col_der = st.columns([1, 1.2])

    with col_izq:
        st.markdown("### 🌧️ Pluviometría por Sector")
        res_lluvia = []
        for sec in SECTORES_LLUVIA:
            hoy_s = df_lluvia_hoy[df_lluvia_hoy["sector"] == sec]["precipitacion_mm"].sum() if not df_lluvia_hoy.empty else 0.0
            mes_s = df_lluvia_mes[df_lluvia_mes["sector"] == sec]["precipitacion_mm"].sum() if not df_lluvia_mes.empty else 0.0
            res_lluvia.append({"SECTOR": sec, "LLUVIA HOY (MM)": hoy_s, "ACUMULADO MES (MM)": mes_s})
        st.dataframe(pd.DataFrame(res_lluvia), use_container_width=True, hide_index=True)

        if not df_nov.empty:
            st.markdown("### ⚠️ Novedades del Día")
            st.dataframe(df_nov[["novedad", "prioridad"]], use_container_width=True, hide_index=True)

    with col_der:
        st.markdown("### 📱 Reporte Ejecutivo para WhatsApp")
        lineas = [
            f"*{EMPRESA}*",
            f"*PARTE DIARIO - {ESTANCIA}*",
            f"📅 Fecha: *{fecha_str}*",
            "",
            "*🌧️ LLUVIAS*",
        ]
        for r in res_lluvia:
            lineas.append(f"• {r['SECTOR']}: {r['LLUVIA HOY (MM)']:.0f} mm (Acum. Mes: {r['ACUMULADO MES (MM)']:.0f} mm)")

        lineas.extend([
            "",
            f"*🐂 EXISTENCIA GANADO*",
            f"• Confinamiento: *{total_conf:,} cab.* ({len(df_conf)} corrales)",
            f"• Campo (mov./control hoy): *{total_campo:,} cab.*",
            "",
            f"*🚜 MAQUINARIAS ({hs_maq:.1f} hs)*"
        ])
        if df_maq.empty:
            lineas.append("• Sin registros hoy")
        else:
            for _, r in df_maq.iterrows():
                lineas.append(f"• {r['maquina']} ({r['operador']}): {r['hs_dia']:.0f} hs - {r['actividad']}")

        lineas.extend(["", "*🚛 CAMIONES*"])
        if df_cam.empty:
            lineas.append("• Sin registros hoy")
        else:
            for _, r in df_cam.iterrows():
                lineas.append(f"• {r['camion']} -> {r['destino']}: {r['descripcion_carga']}")

        lineas.extend(["", f"*🌾 BALANCEADOS ({kg_bal:,.0f} kg)*"])
        if df_bal.empty:
            lineas.append("• Sin producción hoy")
        else:
            for _, r in df_bal.iterrows():
                lineas.append(f"• {r['tipo']}: {r['produccion_kg']:,.0f} kg ({r['destino']})")

        lineas.extend(["", f"*⛽ COMBUSTIBLE ({litros_comb:,.0f} L)*"])
        if df_comb.empty:
            lineas.append("• Sin despacho hoy")
        else:
            for _, r in df_comb.iterrows():
                lineas.append(f"• {r['equipo']}: {r['litros']:,.0f} L")

        if not df_nov.empty:
            lineas.extend(["", "*⚠️ NOVEDADES IMPORTANTES*"])
            for _, r in df_nov.iterrows():
                lineas.append(f"• [{r['prioridad']}] {r['novedad']}")

        texto_wsp = "\n".join(lineas)
        st.code(texto_wsp, language="markdown")

# ------------------------------------------------------------------------------
# TAB 2: GANADOS CAMPO
# ------------------------------------------------------------------------------
with tabs[1]:
    st.markdown("### 🌿 Movimiento y Control de Ganado a Campo")
    if is_admin:
        with st.expander("➕ Registrar Movimiento / Control de Ganado", expanded=False):
            with st.form("form_ganado"):
                c1, c2, c3 = st.columns(3)
                act = c1.selectbox("Actividad", ["SUPLEMENTACION Y CONTROL", "PESAJE", "TRASLADO INTERNO", "INGRESO", "SALIDA / VENTA", "SANIDAD"])
                lote = c2.text_input("Lote / Tropa")
                cat = c3.text_input("Categoría", value="VARIOS")
                c4, c5, c6 = st.columns(3)
                potrero = c4.text_input("Potrero")
                pm = c5.number_input("Peso Medio (kg)", min_value=0.0, step=1.0)
                cant = c6.number_input("Cantidad (cabezas)", min_value=0, step=1)
                c7, c8, c9 = st.columns(3)
                origen = c7.text_input("Origen / Destino", value="INTERNO")
                gmd_esp = c8.number_input("GMD Esperado (kg/día)", value=0.40, step=0.05)
                cons_pct = c9.number_input("Consumo % PV", value=0.0055, format="%.4f", step=0.0005)
                if st.form_submit_button("Guardar Registro de Ganado", type="primary"):
                    execute_sql("""
                        INSERT INTO ganados_campo (fecha, actividad, lote, categoria, potrero, fecha_ultimo_pesaje, pm, cantidad, origen_destino, gmd_esperado, consumo_pct_pv)
                        VALUES (:f, :act, :lote, :cat, :pot, :f, :pm, :cant, :orig, :gmd, :cons)
                    """, {"f": fecha_str, "act": act, "lote": lote, "cat": cat, "pot": potrero, "pm": pm, "cant": cant, "orig": origen, "gmd": gmd_esp, "cons": cons_pct})
                    st.success("Registro guardado.")
                    st.rerun()

    df_g = run_query("SELECT * FROM ganados_campo WHERE fecha = :f ORDER BY id", {"f": fecha_str})
    st.dataframe(df_g, use_container_width=True, hide_index=True)

# ------------------------------------------------------------------------------
# TAB 3: CONFINAMIENTO
# ------------------------------------------------------------------------------
with tabs[2]:
    st.markdown("### 🐂 Existencia y Proyección en Corrales de Confinamiento")
    if is_admin:
        with st.expander("➕ Agregar o Actualizar Corral", expanded=False):
            with st.form("form_conf"):
                c1, c2, c3 = st.columns(3)
                corral = c1.text_input("Corral N°")
                lote_c = c2.text_input("Lote")
                prop_c = c3.selectbox("Propietario", ["SAN LUIS AGSA", "AG LA MARIA SA", "HOTELERIA / TERCEROS"])
                c4, c5, c6, c7 = st.columns(4)
                cant_c = c4.number_input("Cantidad Cabezas", min_value=0, step=1)
                peso_ini = c5.number_input("Peso Entrada (kg)", min_value=0.0, step=1.0)
                fecha_ent = c6.date_input("Fecha Entrada", datetime.date.today())
                gmd_c = c7.number_input("GMD (kg/día)", value=1.40, step=0.05)
                if st.form_submit_button("Guardar Corral", type="primary"):
                    execute_sql("""
                        INSERT INTO confinamiento (corral, lote, cantidad, peso_entrada, fecha_entrada, gmd, propietario)
                        VALUES (:corral, :lote, :cant, :peso, :f_ent, :gmd, :prop)
                        ON CONFLICT (corral) DO UPDATE SET
                            lote = EXCLUDED.lote, cantidad = EXCLUDED.cantidad, peso_entrada = EXCLUDED.peso_entrada,
                            fecha_entrada = EXCLUDED.fecha_entrada, gmd = EXCLUDED.gmd, propietario = EXCLUDED.propietario
                    """, {"corral": corral.strip(), "lote": lote_c, "cant": cant_c, "peso": peso_ini, "f_ent": fecha_ent.strftime("%Y-%m-%d"), "gmd": gmd_c, "prop": prop_c})
                    st.success("Corral actualizado.")
                    st.rerun()

    df_c = run_query("SELECT * FROM confinamiento ORDER BY corral")
    if not df_c.empty:
        df_c["dias_feedlot"] = (pd.to_datetime(fecha_str) - pd.to_datetime(df_c["fecha_entrada"])).dt.days.clip(lower=0)
        df_c["ganancia_total_kg"] = (df_c["dias_feedlot"] * df_c["gmd"]).round(1)
        df_c["peso_proyectado_kg"] = (df_c["peso_entrada"] + df_c["ganancia_total_kg"]).round(1)
    st.dataframe(df_c, use_container_width=True, hide_index=True)

# ------------------------------------------------------------------------------
# TAB 4: MAQUINARIAS Y CAMIONES
# ------------------------------------------------------------------------------
with tabs[3]:
    col_m, col_cam = st.columns(2)
    with col_m:
        st.markdown("### 🚜 Maquinarias")
        if is_admin:
            if st.button("⚡ Cargar las 4 Máquinas Habituales del Día"):
                for maq, op, act in MAQUINAS_HABITUALES:
                    last = run_query("SELECT horometro_final FROM maquinarias WHERE maquina = :m ORDER BY fecha DESC, id DESC LIMIT 1", {"m": maq})
                    ini = float(last.iloc[0]["horometro_final"]) if not last.empty else 0.0
                    execute_sql("""
                        INSERT INTO maquinarias (fecha, maquina, operador, actividad, horometro_inicio, horometro_final, hs_dia, combustible_l)
                        VALUES (:f, :m, :op, :act, :ini, :ini, 0, 0)
                    """, {"f": fecha_str, "m": maq, "op": op, "act": act, "ini": ini})
                st.rerun()

            with st.form("form_maq"):
                m_sel = st.selectbox("Máquina", ["PALA SEM", "TRACTOR 12", "TRACTOR 9", "TRACTOR 8", "OTRO"])
                op_in = st.text_input("Operador")
                act_in = st.text_input("Actividad Realizada")
                c1, c2, c3 = st.columns(3)
                h_ini = c1.number_input("Horómetro Inicio", min_value=0.0, step=1.0)
                h_fin = c2.number_input("Horómetro Final", min_value=0.0, step=1.0)
                comb_m = c3.number_input("Combustible (L)", min_value=0.0, step=1.0)
                if st.form_submit_button("Registrar Máquina", type="primary"):
                    hs = max(0.0, h_fin - h_ini)
                    execute_sql("""
                        INSERT INTO maquinarias (fecha, maquina, operador, actividad, horometro_inicio, horometro_final, hs_dia, combustible_l)
                        VALUES (:f, :m, :op, :act, :ini, :fin, :hs, :comb)
                    """, {"f": fecha_str, "m": m_sel, "op": op_in, "act": act_in, "ini": h_ini, "fin": h_fin, "hs": hs, "comb": comb_m})
                    st.rerun()

        df_m = run_query("SELECT * FROM maquinarias WHERE fecha = :f ORDER BY id", {"f": fecha_str})
        st.dataframe(df_m, use_container_width=True, hide_index=True)

    with col_cam:
        st.markdown("### 🚛 Camiones y Fletes")
        if is_admin:
            with st.form("form_cam"):
                cam_sel = st.selectbox("Camión", ["SCANIA", "VOLVO", "OTRO"])
                dest_in = st.text_input("Destino", value="ESS")
                carga_in = st.text_input("Descripción de Carga", value="PARADO EN SANTA SILVIA")
                c1, c2 = st.columns(2)
                km_in = c1.number_input("Kilometraje", min_value=0.0, step=1.0)
                comb_c = c2.number_input("Combustible (L)", min_value=0.0, step=1.0)
                obs_c = st.text_input("Observaciones")
                if st.form_submit_button("Registrar Camión", type="primary"):
                    execute_sql("""
                        INSERT INTO camiones (fecha, camion, destino, descripcion_carga, kilometraje, combustible_l, observaciones)
                        VALUES (:f, :cam, :dest, :carga, :km, :comb, :obs)
                    """, {"f": fecha_str, "cam": cam_sel, "dest": dest_in, "carga": carga_in, "km": km_in, "comb": comb_c, "obs": obs_c})
                    st.rerun()

        df_ca = run_query("SELECT * FROM camiones WHERE fecha = :f ORDER BY id", {"f": fecha_str})
        st.dataframe(df_ca, use_container_width=True, hide_index=True)

# ------------------------------------------------------------------------------
# TAB 5: COMBUSTIBLE
# ------------------------------------------------------------------------------
with tabs[4]:
    st.markdown("### ⛽ Control Diario de Despacho de Combustible")
    if is_admin:
        with st.form("form_comb"):
            c1, c2, c3, c4 = st.columns(4)
            eq_sel = c1.selectbox("Equipo / Vehículo", EQUIPOS_COMBUSTIBLE)
            cat_sel = c2.selectbox("Categoría", ["TRACTOR / PALA", "CAMION", "GENERADOR / OTROS", "PATRULLA / CAMIONETA"])
            lit_in = c3.number_input("Litros (L)", min_value=0.0, step=1.0)
            obs_comb = c4.text_input("Observaciones")
            if st.form_submit_button("Registrar Despacho", type="primary"):
                execute_sql("""
                    INSERT INTO combustible (fecha, equipo, categoria, litros, horometro_km, observaciones)
                    VALUES (:f, :eq, :cat, :lit, 0, :obs)
                """, {"f": fecha_str, "eq": eq_sel, "cat": cat_sel, "lit": lit_in, "obs": obs_comb})
                st.rerun()

    df_co = run_query("SELECT * FROM combustible WHERE fecha = :f ORDER BY id", {"f": fecha_str})
    st.dataframe(df_co, use_container_width=True, hide_index=True)

# ------------------------------------------------------------------------------
# TAB 6: BALANCEADOS
# ------------------------------------------------------------------------------
with tabs[5]:
    st.markdown("### 🌾 Producción de Núcleos y Balanceados")
    if is_admin:
        with st.form("form_bal"):
            c1, c2, c3, c4 = st.columns(4)
            tipo_b = c1.selectbox("Tipo", ["N. Terminacion", "Prem - Terminacion", "Recria", "Inicio", "Otro"])
            kg_b = c2.number_input("Producción (kg)", min_value=0.0, step=50.0, value=500.0)
            dest_b = c3.text_input("Destino", value="ESS (Estancia Santa Silvia)")
            obs_b = c4.text_input("Observaciones", value="Producción normal de la mañana")
            if st.form_submit_button("Registrar Producción", type="primary"):
                execute_sql("""
                    INSERT INTO balanceados (fecha, tipo, produccion_kg, destino, observaciones)
                    VALUES (:f, :t, :kg, :d, :o)
                """, {"f": fecha_str, "t": tipo_b, "kg": kg_b, "d": dest_b, "o": obs_b})
                st.rerun()

    df_ba = run_query("SELECT * FROM balanceados WHERE fecha = :f ORDER BY id", {"f": fecha_str})
    st.dataframe(df_ba, use_container_width=True, hide_index=True)

# ------------------------------------------------------------------------------
# TAB 7: PERSONAL Y ADM
# ------------------------------------------------------------------------------
with tabs[6]:
    col_p, col_a = st.columns(2)
    with col_p:
        st.markdown("### 👷 Asistencia y Tareas de Personal")
        if is_admin:
            if st.button("⚡ Cargar Todo el Personal (Presente)"):
                for p in PERSONAL_LISTA:
                    execute_sql("""
                        INSERT INTO personal (fecha, personal, actividad, asistencia)
                        VALUES (:f, :p, 'Actividades operativas de rutina', 'PRESENTE')
                    """, {"f": fecha_str, "p": p})
                st.rerun()

            with st.form("form_pers"):
                p_sel = st.selectbox("Personal", PERSONAL_LISTA)
                act_p = st.text_input("Actividad Realizada")
                asist_p = st.selectbox("Asistencia", ["PRESENTE", "AUSENTE", "DESCANSO", "PERMISO"])
                if st.form_submit_button("Registrar Personal", type="primary"):
                    execute_sql("""
                        INSERT INTO personal (fecha, personal, actividad, asistencia)
                        VALUES (:f, :p, :act, :asist)
                    """, {"f": fecha_str, "p": p_sel, "act": act_p, "asist": asist_p})
                    st.rerun()

        df_pe = run_query("SELECT * FROM personal WHERE fecha = :f ORDER BY id", {"f": fecha_str})
        st.dataframe(df_pe, use_container_width=True, hide_index=True)

    with col_a:
        st.markdown("### 📋 Supervisión Administrativa y Capataces")
        if is_admin:
            if st.button("⚡ Cargar Todos los Encargados"):
                for c in CARGOS_ADM:
                    execute_sql("""
                        INSERT INTO adm_supervision (fecha, cargo, actividad)
                        VALUES (:f, :c, 'Recorrida y supervisión general')
                    """, {"f": fecha_str, "c": c})
                st.rerun()

            with st.form("form_adm"):
                c_sel = st.selectbox("Cargo", CARGOS_ADM)
                act_a = st.text_input("Actividad / Supervisión")
                if st.form_submit_button("Registrar Supervisión", type="primary"):
                    execute_sql("""
                        INSERT INTO adm_supervision (fecha, cargo, actividad)
                        VALUES (:f, :c, :act)
                    """, {"f": fecha_str, "c": c_sel, "act": act_a})
                    st.rerun()

        df_ad = run_query("SELECT * FROM adm_supervision WHERE fecha = :f ORDER BY id", {"f": fecha_str})
        st.dataframe(df_ad, use_container_width=True, hide_index=True)

# ------------------------------------------------------------------------------
# TAB 8: LLUVIAS Y NOVEDADES
# ------------------------------------------------------------------------------
with tabs[7]:
    col_ll, col_no = st.columns(2)
    with col_ll:
        st.markdown("### 🌧️ Registro de Pluviometría")
        if is_admin:
            with st.form("form_lluvia"):
                sec_l = st.selectbox("Sector", SECTORES_LLUVIA)
                mm_l = st.number_input("Precipitación (mm)", min_value=0.0, step=0.5)
                obs_l = st.text_input("Observaciones", value="Día parcial nublado")
                if st.form_submit_button("Registrar Lluvia", type="primary"):
                    execute_sql("""
                        INSERT INTO lluvias (fecha, sector, precipitacion_mm, observaciones)
                        VALUES (:f, :s, :mm, :obs)
                    """, {"f": fecha_str, "s": sec_l, "mm": mm_l, "obs": obs_l})
                    st.rerun()

        df_ll = run_query("SELECT * FROM lluvias WHERE fecha = :f ORDER BY id", {"f": fecha_str})
        st.dataframe(df_ll, use_container_width=True, hide_index=True)

    with col_no:
        st.markdown("### ⚠️ Novedades Importantes y Eventos")
        if is_admin:
            with st.form("form_nov"):
                nov_t = st.text_input("Novedad / Evento Destacado")
                prio_t = st.selectbox("Prioridad", ["ALTA", "MEDIA", "BAJA"])
                if st.form_submit_button("Registrar Novedad", type="primary"):
                    execute_sql("""
                        INSERT INTO novedades (fecha, novedad, prioridad)
                        VALUES (:f, :n, :p)
                    """, {"f": fecha_str, "n": nov_t, "p": prio_t})
                    st.rerun()

        df_no = run_query("SELECT * FROM novedades WHERE fecha = :f ORDER BY id", {"f": fecha_str})
        st.dataframe(df_no, use_container_width=True, hide_index=True)
