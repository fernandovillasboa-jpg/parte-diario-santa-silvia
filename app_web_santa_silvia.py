import os
import io
import datetime
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# ==============================================================================
# CONFIGURACION GENERAL DE LA ESTANCIA
# ==============================================================================
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
PLANTILLA_MAQUINARIAS = [
    {"maquina": "PALA SEM", "operador": "LUCIO SANCHEZ", "actividad": "CARGA DE INSUMO EN CONFINAMIENTO Y LIMPIEZA"},
    {"maquina": "TRACTOR 12", "operador": "EDGARD CRISTALDO", "actividad": "REPARTO DE RACION EN CONFINAMIENTO"},
    {"maquina": "TRACTOR 9", "operador": "ANGEL SANCHEZ", "actividad": "REPARTO DE RACION EN CONFINAMIENTO"},
    {"maquina": "TRACTOR 8", "operador": "HILARIO GARCIA", "actividad": "ROTATIVEADA SECTOR CONFINAMIENTO"}
]
OPERADORES_MAQUINARIA = ["LUCIO SANCHEZ", "EDGARD CRISTALDO", "ANGEL SANCHEZ", "HILARIO GARCIA", "OSCAR HOLT"]
ACTIVIDADES_MAQUINARIA = [
    "CARGA DE INSUMO EN CONFINAMIENTO Y LIMPIEZA",
    "REPARTO DE RACION EN CONFINAMIENTO",
    "ROTATIVEADA SECTOR CONFINAMIENTO",
    "ROTATIVEADA SECTOR ENTRADAS",
    "ROTATIVEADA SECTOR PASO ITA",
    "ROTATIVEADA EN SECTOR CAPIASU",
    "RASTREADA EN SECTOR ENTRADA CAMINERA",
    "RASTREADA EN SECTOR ENTRADAS",
    "RASTRA CAÑERA EN SECTOR CAPIASU CONFI",
    "PERFILACION DE PISTA AVIACION",
    "CORTA FUEGO CALLE 7,8,6",
    "SIN ACTIVIDAD"
]
PLANTILLA_ADM = [
    {"cargo": "COMISARIO", "actividad": "RECORRIDA Y LECTURA DE BATEA"},
    {"cargo": "MAYORDOMO", "actividad": "PLANTEAMIENTO DE ACTIVIDADES"},
    {"cargo": "ENCARGADO CONF", "actividad": "RECORRIDA EN CONFINAMIENTO Y SUPERVISAR FABRICA DE BALANCEADO"},
    {"cargo": "CAPATAZ (Silverio V.)", "actividad": "RECORRIDA DE POTREROS Y CONTROL DE HACIENDA"},
    {"cargo": "ESTANCIERO (Antonio V.)", "actividad": "CONTROL DE AGUADAS Y POTREROS"},
    {"cargo": "RETIRO PASO ITA (Oscar G.)", "actividad": "RECORRIDA RETIRO PASO ITA"}
]
ACTIVIDADES_ADM = [
    "RECORRIDA Y LECTURA DE BATEA", "LECTURA DE BATEA", "RECORRIDA Y PESAJE DE TERNERO TE",
    "PESAJE DE LOTE MINERVA FOODS", "PLANTEAMIENTO DE ACTIVIDADES",
    "RECORRIDA EN CONFINAMIENTO Y SUPERVISAR FABRICA DE BALANCEADO",
    "APOYO PESAJE LOTE MINERVA FOODS", "APOYO EN PESAJE Y EMBARQUE EN EL CORRAL",
    "RECORRIDA DE POTREROS Y CONTROL DE HACIENDA", "CONTROL DE AGUADAS Y POTREROS",
    "RECORRIDA RETIRO PASO ITA", "EN DESCANSO"
]
LISTA_PERSONAL = [
    {"nombre": "Lorenzo Lopez (Jefe Personal)", "actividad_default": "Produccion de nucleo"},
    {"nombre": "Nelson Martinez (Ayudante Taller)", "actividad_default": "Control de bebedero en confinamiento y campo"},
    {"nombre": "Hugo Torales", "actividad_default": "Produccion de nucleo"},
    {"nombre": "Angel Sánchez", "actividad_default": "Reparto de racion en confinamiento"},
    {"nombre": "Evelio Fernandez", "actividad_default": "Apoyo estanciero"},
    {"nombre": "Diego Valdez", "actividad_default": "Produccion de balanceados"},
    {"nombre": "Oscar Holt", "actividad_default": "Apoyo taller"},
    {"nombre": "Ramon Chamorro (Carpintero)", "actividad_default": "Arreglo de alambrada en confinamiento"},
    {"nombre": "Eusebio Vera (Puntero)", "actividad_default": "Ayudante estanciero"},
    {"nombre": "Digno Roman", "actividad_default": "Apoyo en confinamiento"},
    {"nombre": "Gabriel Eudes Roman", "actividad_default": "Apoyo en el corral"},
    {"nombre": "Lucio Sanchez", "actividad_default": "Operador Pala SEM"},
    {"nombre": "Edgard Cristaldo", "actividad_default": "Operador Tractor 12"},
    {"nombre": "Hilario Garcia", "actividad_default": "Operador Tractor 8"}
]
ACTIVIDADES_FRECUENTES = [
    "Produccion de nucleo", "Produccion de balanceados", "Reparto de racion en confinamiento",
    "Control de bebedero en confinamiento y campo", "Apoyo estanciero", "Ayudante estanciero",
    "Apoyo taller", "Arreglo de alambrada en confinamiento", "Apoyo en confinamiento",
    "Apoyo en el corral", "Corta fuego sector calle 8,7,6", "Sin actividad", "AUSENTE"
]


# ==============================================================================
# CONEXION A BASE DE DATOS (NUBE SUPABASE/POSTGRES O SQLITE RESPALDO)
# ==============================================================================
@st.cache_resource
def get_engine():
    db_url = None
    try:
        if "DATABASE_URL" in st.secrets:
            db_url = st.secrets["DATABASE_URL"]
    except Exception:
        pass
    if not db_url:
        db_url = os.environ.get("DATABASE_URL")

    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        return create_engine(db_url, pool_pre_ping=True)
    return create_engine("sqlite:///santa_silvia_parte_diario.db")


def init_db():
    eng = get_engine()
    is_pg = eng.dialect.name == "postgresql"
    id_col = "SERIAL PRIMARY KEY" if is_pg else "INTEGER PRIMARY KEY AUTOINCREMENT"

    stmts = [
        f"""CREATE TABLE IF NOT EXISTS ganados_campo (
            id {id_col}, fecha TEXT NOT NULL, actividad TEXT, lote TEXT, categoria TEXT,
            potrero TEXT, fecha_ultimo_pesaje TEXT, pm DOUBLE PRECISION DEFAULT 0,
            cantidad INTEGER DEFAULT 0, origen_destino TEXT,
            gmd_esperado DOUBLE PRECISION DEFAULT 0.4, consumo_pct_pv DOUBLE PRECISION DEFAULT 0.0055
        )""",
        f"""CREATE TABLE IF NOT EXISTS confinamiento (
            id {id_col}, corral TEXT UNIQUE, lote TEXT, cantidad INTEGER DEFAULT 0,
            peso_entrada DOUBLE PRECISION DEFAULT 0, fecha_entrada TEXT,
            gmd DOUBLE PRECISION DEFAULT 1.4, propietario TEXT
        )""",
        f"""CREATE TABLE IF NOT EXISTS recepcion_hoteleria (
            id {id_col}, fecha_llegada TEXT NOT NULL, propietario TEXT,
            modalidad TEXT DEFAULT 'HOTELERIA', tropa_lote TEXT,
            categoria TEXT DEFAULT 'NOVILLO', cantidad INTEGER DEFAULT 0,
            peso_prom_kg DOUBLE PRECISION DEFAULT 0, corral_destino TEXT,
            estado TEXT DEFAULT 'EN RECEPCION / PESAJE', observaciones TEXT
        )""",
        f"""CREATE TABLE IF NOT EXISTS maquinarias (
            id {id_col}, fecha TEXT NOT NULL, maquina TEXT, operador TEXT, actividad TEXT,
            horometro_inicio DOUBLE PRECISION DEFAULT 0, horometro_final DOUBLE PRECISION DEFAULT 0,
            hs_dia DOUBLE PRECISION DEFAULT 0, combustible_l DOUBLE PRECISION DEFAULT 0
        )""",
        f"""CREATE TABLE IF NOT EXISTS camiones (
            id {id_col}, fecha TEXT NOT NULL, camion TEXT, destino TEXT,
            descripcion_carga TEXT, kilometraje DOUBLE PRECISION DEFAULT 0,
            combustible_l DOUBLE PRECISION DEFAULT 0, observaciones TEXT
        )""",
        f"""CREATE TABLE IF NOT EXISTS combustible (
            id {id_col}, fecha TEXT NOT NULL, equipo TEXT, categoria TEXT,
            litros DOUBLE PRECISION DEFAULT 0, horometro_km DOUBLE PRECISION DEFAULT 0, observaciones TEXT
        )""",
        f"""CREATE TABLE IF NOT EXISTS balanceados (
            id {id_col}, fecha TEXT NOT NULL, tipo TEXT,
            produccion_kg DOUBLE PRECISION DEFAULT 0, destino TEXT, observaciones TEXT
        )""",
        f"""CREATE TABLE IF NOT EXISTS personal (
            id {id_col}, fecha TEXT NOT NULL, personal TEXT, actividad TEXT, asistencia TEXT
        )""",
        f"""CREATE TABLE IF NOT EXISTS adm_supervision (
            id {id_col}, fecha TEXT NOT NULL, cargo TEXT, actividad TEXT
        )""",
        f"""CREATE TABLE IF NOT EXISTS lluvias (
            id {id_col}, fecha TEXT NOT NULL, sector TEXT,
            precipitacion_mm DOUBLE PRECISION DEFAULT 0, observaciones TEXT
        )""",
        f"""CREATE TABLE IF NOT EXISTS novedades (
            id {id_col}, fecha TEXT NOT NULL, novedad TEXT, prioridad TEXT
        )"""
    ]
    with eng.begin() as conn:
        for s in stmts:
            conn.execute(text(s))
        try:
            conn.execute(text("ALTER TABLE recepcion_hoteleria ADD COLUMN categoria TEXT DEFAULT 'NOVILLO'"))
        except Exception:
            pass


def run_query(sql, params=None):
    eng = get_engine()
    with eng.connect() as conn:
        return pd.read_sql_query(text(sql), conn, params=params or {})


def run_exec(sql, params=None):
    eng = get_engine()
    with eng.begin() as conn:
        conn.execute(text(sql), params or {})


# ==============================================================================
# SISTEMA DE LOGIN CON USUARIO, CONTRASEÑA Y ROLES (CARGA VS LECTURA)
# ==============================================================================
def get_users_db():
    # Se leen desde st.secrets["users"] en la nube o usa estos por defecto
    try:
        if "users" in st.secrets:
            return dict(st.secrets["users"])
    except Exception:
        pass
    return {
        "admin": {"password": "SantaSilvia2026", "nombre": "Administrador Estancia", "rol": "editor"},
        "gerencia": {"password": "SanLuis2026", "nombre": "Gerencia / Directorio", "rol": "lector"}
    }


def check_login():
    if st.session_state.get("authenticated"):
        return True

    st.markdown(f"""
        <div style="background-color:#1B4332;padding:20px;border-radius:10px;text-align:center;margin-bottom:20px;">
            <h2 style="color:white;margin:0;">{EMPRESA}</h2>
            <p style="color:#B7E4C7;margin:5px 0 0 0;">SISTEMA PARTE DIARIO ONLINE — {ESTANCIA}</p>
        </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.subheader("🔐 Iniciar Sesión")
        with st.form("login_form"):
            usuario = st.text_input("Usuario").strip().lower()
            clave = st.text_input("Contraseña", type="password").strip()
            entrar = st.form_submit_button("Ingresar al Sistema", use_container_width=True, type="primary")
            if entrar:
                users = get_users_db()
                if usuario in users and users[usuario]["password"] == clave:
                    st.session_state["authenticated"] = True
                    st.session_state["usuario"] = usuario
                    st.session_state["nombre_usuario"] = users[usuario].get("nombre", usuario)
                    st.session_state["rol"] = users[usuario].get("rol", "lector")
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos.")
    return False


# ==============================================================================
# EXPORTACION A EXCEL DESCARGABLE
# ==============================================================================
def build_excel_bytes(f_sel, modo="dia"):
    output = io.BytesIO()
    mes = f_sel[:7]
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        if modo == "dia":
            run_query("SELECT fecha, sector, precipitacion_mm, observaciones FROM lluvias WHERE fecha = :f", {"f": f_sel}).to_excel(writer, sheet_name="LLUVIAS_DIA", index=False)
            run_query("SELECT fecha, maquina, operador, actividad, horometro_inicio, horometro_final, hs_dia, combustible_l FROM maquinarias WHERE fecha = :f", {"f": f_sel}).to_excel(writer, sheet_name="MAQUINARIAS_DIA", index=False)
            run_query("SELECT fecha, camion, destino, descripcion_carga, kilometraje, combustible_l, observaciones FROM camiones WHERE fecha = :f", {"f": f_sel}).to_excel(writer, sheet_name="CAMIONES_DIA", index=False)
            run_query("SELECT fecha, equipo, categoria, litros, observaciones FROM combustible WHERE fecha = :f", {"f": f_sel}).to_excel(writer, sheet_name="COMBUSTIBLE_DIA", index=False)
            run_query("SELECT fecha, tipo, produccion_kg, destino, observaciones FROM balanceados WHERE fecha = :f", {"f": f_sel}).to_excel(writer, sheet_name="BALANCEADOS_DIA", index=False)
            run_query("SELECT fecha, personal, actividad, asistencia FROM personal WHERE fecha = :f", {"f": f_sel}).to_excel(writer, sheet_name="PERSONAL_DIA", index=False)
            run_query("SELECT fecha, cargo, actividad FROM adm_supervision WHERE fecha = :f", {"f": f_sel}).to_excel(writer, sheet_name="SUPERVISION_ADM", index=False)
            run_query("SELECT fecha, actividad, lote, categoria, potrero, pm, cantidad, origen_destino FROM ganados_campo WHERE fecha = :f", {"f": f_sel}).to_excel(writer, sheet_name="GANADOS_CAMPO", index=False)
            run_query("SELECT corral, lote, cantidad, peso_entrada, fecha_entrada, gmd, propietario FROM confinamiento ORDER BY corral").to_excel(writer, sheet_name="CONFINAMIENTO", index=False)
            run_query("SELECT fecha_llegada, propietario, modalidad, tropa_lote, categoria, cantidad, peso_prom_kg, corral_destino, estado, observaciones FROM recepcion_hoteleria ORDER BY fecha_llegada DESC").to_excel(writer, sheet_name="RECEPCION_HOTELERIA", index=False)
            run_query("SELECT fecha, novedad, prioridad FROM novedades WHERE fecha = :f", {"f": f_sel}).to_excel(writer, sheet_name="NOVEDADES_DIA", index=False)
        else:
            m_like = f"{mes}%"
            run_query("SELECT * FROM ganados_campo WHERE fecha LIKE :m", {"m": m_like}).to_excel(writer, sheet_name="GANADOS", index=False)
            run_query("SELECT * FROM confinamiento ORDER BY corral").to_excel(writer, sheet_name="CONFINAMIENTO", index=False)
            run_query("SELECT * FROM recepcion_hoteleria ORDER BY fecha_llegada DESC").to_excel(writer, sheet_name="RECEPCION_HOTELERIA", index=False)
            run_query("SELECT * FROM maquinarias WHERE fecha LIKE :m", {"m": m_like}).to_excel(writer, sheet_name="MAQUINARIAS", index=False)
            run_query("SELECT * FROM camiones WHERE fecha LIKE :m", {"m": m_like}).to_excel(writer, sheet_name="CAMIONES", index=False)
            run_query("SELECT * FROM combustible WHERE fecha LIKE :m", {"m": m_like}).to_excel(writer, sheet_name="COMBUSTIBLE", index=False)
            run_query("SELECT * FROM balanceados WHERE fecha LIKE :m", {"m": m_like}).to_excel(writer, sheet_name="BALANCEADOS", index=False)
            run_query("SELECT * FROM personal WHERE fecha LIKE :m", {"m": m_like}).to_excel(writer, sheet_name="PERSONAL", index=False)
            run_query("SELECT * FROM adm_supervision WHERE fecha LIKE :m", {"m": m_like}).to_excel(writer, sheet_name="ADM", index=False)
            run_query("SELECT * FROM lluvias WHERE fecha LIKE :m", {"m": m_like}).to_excel(writer, sheet_name="LLUVIAS", index=False)
            run_query("SELECT * FROM novedades WHERE fecha LIKE :m", {"m": m_like}).to_excel(writer, sheet_name="NOVEDADES", index=False)
    return output.getvalue()


# ==============================================================================
# APLICACION PRINCIPAL
# ==============================================================================
def main():
    init_db()
    if not check_login():
        return

    es_editor = st.session_state.get("rol") == "editor"

    # Barra lateral de control
    with st.sidebar:
        st.markdown(f"### 🐂 {ESTANCIA}")
        st.caption(EMPRESA)
        st.info(f"👤 **{st.session_state['nombre_usuario']}**\n\nPerfil: **{'Carga y Edición' if es_editor else 'Solo Lectura'}**")

        fecha_dt = st.date_input("📅 Fecha de Consulta / Carga", value=datetime.date.today())
        f_sel = fecha_dt.strftime("%Y-%m-%d")
        mes_prefix = f_sel[:7]

        if st.button("🔄 Actualizar Datos", use_container_width=True):
            st.rerun()

        st.divider()
        st.download_button(
            label="📥 Descargar Excel del Día",
            data=build_excel_bytes(f_sel, "dia"),
            file_name=f"PARTE_DIARIO_SANTA_SILVIA_{f_sel}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        st.download_button(
            label="📊 Descargar Excel del Mes",
            data=build_excel_bytes(f_sel, "mes"),
            file_name=f"REPORTE_MENSUAL_SANTA_SILVIA_{mes_prefix}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

        st.divider()
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    # Encabezado superior
    st.markdown(f"""
        <div style="background-color:#1B4332;padding:14px 20px;border-radius:8px;margin-bottom:12px;">
            <h3 style="color:white;margin:0;">{EMPRESA} — {ESTANCIA}</h3>
            <span style="color:#B7E4C7;font-size:14px;">Parte Diario Online en Tiempo Real | Fecha seleccionada: <b>{f_sel}</b></span>
        </div>
    """, unsafe_allow_html=True)

    # Consultas globales para KPIs y Resumen
    df_gan_dia = run_query("SELECT * FROM ganados_campo WHERE fecha = :f ORDER BY id DESC", {"f": f_sel})
    df_conf = run_query("SELECT * FROM confinamiento ORDER BY corral")
    df_rec = run_query("SELECT * FROM recepcion_hoteleria ORDER BY fecha_llegada DESC, id DESC")
    df_maq_dia = run_query("SELECT * FROM maquinarias WHERE fecha = :f ORDER BY id DESC", {"f": f_sel})
    df_cam_dia = run_query("SELECT * FROM camiones WHERE fecha = :f ORDER BY id DESC", {"f": f_sel})
    df_comb_dia = run_query("SELECT * FROM combustible WHERE fecha = :f ORDER BY id DESC", {"f": f_sel})
    df_bal_dia = run_query("SELECT * FROM balanceados WHERE fecha = :f ORDER BY id DESC", {"f": f_sel})
    df_per_dia = run_query("SELECT * FROM personal WHERE fecha = :f ORDER BY id DESC", {"f": f_sel})
    df_adm_dia = run_query("SELECT * FROM adm_supervision WHERE fecha = :f ORDER BY id DESC", {"f": f_sel})
    df_llu_mes = run_query("SELECT * FROM lluvias WHERE fecha LIKE :m ORDER BY fecha DESC, id DESC", {"m": f"{mes_prefix}%"})
    df_nov_dia = run_query("SELECT * FROM novedades WHERE fecha = :f ORDER BY id DESC", {"f": f_sel})

    stock_conf = int(df_conf["cantidad"].sum()) if not df_conf.empty else 0
    stock_campo = int(df_gan_dia["cantidad"].sum()) if not df_gan_dia.empty else 0
    hs_maq = float(df_maq_dia["hs_dia"].sum()) if not df_maq_dia.empty else 0.0
    comb_hoy = float(df_comb_dia["litros"].sum()) if not df_comb_dia.empty else 0.0
    prod_bal = float(df_bal_dia["produccion_kg"].sum()) if not df_bal_dia.empty else 0.0
    pers_pres = int((df_per_dia["asistencia"].str.upper() == "PRESENTE").sum()) if not df_per_dia.empty else 0

    df_llu_hoy = df_llu_mes[df_llu_mes["fecha"] == f_sel] if not df_llu_mes.empty else pd.DataFrame()
    lluvia_hoy_prom = float(df_llu_hoy["precipitacion_mm"].mean()) if not df_llu_hoy.empty else 0.0
    lluvia_mes_prom = float(df_llu_mes.groupby("sector")["precipitacion_mm"].sum().mean()) if not df_llu_mes.empty else 0.0

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

    # --------------------------------------------------------------------------
    # TAB 1: RESUMEN DIARIO
    # --------------------------------------------------------------------------
    with tabs[0]:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🌧️ Lluvia Hoy (Prom.)", f"{lluvia_hoy_prom:.1f} mm")
        c2.metric("🌦️ Lluvia Acum. Mes", f"{lluvia_mes_prom:.1f} mm")
        c3.metric("🚜 Hs Maquinaria Hoy", f"{hs_maq:.1f} hs")
        c4.metric("⛽ Combustible Hoy", f"{comb_hoy:.0f} L")

        c5, c6, c7, c8 = st.columns(4)
        c5.metric("🐂 Ganado Confinamiento", f"{stock_conf:,} cab.")
        c6.metric("🌿 Ganado a Campo", f"{stock_campo:,} cab.")
        c7.metric("🌾 Prod. Balanceado Hoy", f"{prod_bal:,.0f} kg")
        c8.metric("👷 Personal Presente", f"{pers_pres} pers.")

        st.divider()
        col_izq, col_der = st.columns([1.1, 1])

        with col_izq:
            st.subheader("🌧️ Pluviometría por Sector")
            lluvia_det_wa = []
            rows_pluv = []
            for sec in SECTORES_LLUVIA:
                mm_h = float(df_llu_hoy[df_llu_hoy["sector"] == sec]["precipitacion_mm"].sum()) if not df_llu_hoy.empty else 0.0
                mm_m = float(df_llu_mes[df_llu_mes["sector"] == sec]["precipitacion_mm"].sum()) if not df_llu_mes.empty else 0.0
                rows_pluv.append({"SECTOR": sec, "LLUVIA HOY (MM)": mm_h, "ACUMULADO MES (MM)": mm_m})
                lluvia_det_wa.append(f"  - {sec}: {mm_h:.0f} mm hoy (Acum. mes: {mm_m:.0f} mm)")
            st.dataframe(pd.DataFrame(rows_pluv), use_container_width=True, hide_index=True)

            st.subheader("⚠️ Novedades Importantes del Día")
            if df_nov_dia.empty:
                st.info("Sin novedades registradas para esta fecha.")
            else:
                st.dataframe(df_nov_dia[["fecha", "novedad", "prioridad"]], use_container_width=True, hide_index=True)

        with col_der:
            st.subheader("📲 Reporte Ejecutivo para WhatsApp")
            rec_pend = df_rec[df_rec["estado"].str.upper() != "INGRESADO A CORRAL"] if not df_rec.empty else pd.DataFrame()
            rec_wa = [f"  * {r['propietario']} ({r['modalidad']}): {r['tropa_lote']} [{r.get('categoria', '')}] — {r['cantidad']} cab. | {r['estado']}" for _, r in rec_pend.iterrows()]
            maq_wa = [f"  * {r['maquina']} ({r['operador']}): {r['actividad']} — {r['hs_dia']:.1f} hs | {r['combustible_l']:.0f} L" for _, r in df_maq_dia.iterrows()]
            cam_wa = [f"  * {r['camion']} -> {r['destino']} ({r['descripcion_carga']}) — {r['kilometraje']:.0f} km | {r['combustible_l']:.0f} L" for _, r in df_cam_dia.iterrows()]
            nov_wa = [f"  * [{r['prioridad']}] {r['novedad']}" for _, r in df_nov_dia.iterrows()]
            adm_wa = [f"  * {r['cargo']}: {r['actividad']}" for _, r in df_adm_dia.iterrows()]
            ausentes = df_per_dia[df_per_dia["asistencia"].str.upper() != "PRESENTE"]["personal"].tolist() if not df_per_dia.empty else []

            wa_text = (
                f"*{EMPRESA}*\n"
                f"*PARTE DIARIO — {ESTANCIA}*\n"
                f"📅 Fecha: *{f_sel}*\n"
                f"----------------------------------------\n"
                f"🌧️ *LLUVIAS:*\n" + "\n".join(lluvia_det_wa) + "\n\n"
                f"🐂 *EXISTENCIA HACIENDA:*\n"
                f"  - Confinamiento (Feedlot): *{stock_conf:,} cab.*\n"
                f"  - Campo (Suplementación): *{stock_campo:,} cab.*\n"
                f"  - Total General: *{stock_conf + stock_campo:,} cab.*\n"
                + (f"📥 *EN RECEPCIÓN / HOTELERÍA:*\n" + "\n".join(rec_wa) + "\n\n" if rec_wa else "\n") +
                f"🌾 *FÁBRICA Y OPERACIÓN:*\n"
                f"  - Prod. Balanceado/Núcleo hoy: *{prod_bal:,.0f} kg*\n"
                f"  - Horas Maquinaria hoy: *{hs_maq:.1f} hs*\n"
                f"  - Consumo Combustible hoy: *{comb_hoy:.0f} L*\n"
                f"  - Personal presente: *{pers_pres}* (Ausentes/Permiso: {', '.join(ausentes) if ausentes else 'Ninguno'})\n\n"
                f"🚜 *MAQUINARIAS:*\n" + ("\n".join(maq_wa) if maq_wa else "  * Sin movimiento.") + "\n\n"
                f"🚛 *CAMIONES:*\n" + ("\n".join(cam_wa) if cam_wa else "  * Sin fletes.") + "\n\n"
                f"⚠️ *NOVEDADES:*\n" + ("\n".join(nov_wa) if nov_wa else "  * Sin novedades.") + "\n\n"
                f"📋 *SUPERVISIÓN / CAPATACES:*\n" + ("\n".join(adm_wa) if adm_wa else "  * Sin registros.")
            )
            st.code(wa_text, language=None)

    # --------------------------------------------------------------------------
    # TAB 2: GANADOS A CAMPO
    # --------------------------------------------------------------------------
    with tabs[1]:
        if es_editor:
            with st.expander("➕ Registrar Ganado a Campo / Suplementación", expanded=True):
                with st.form("form_ganado"):
                    c1, c2, c3, c4, c5 = st.columns(5)
                    act = c1.text_input("Actividad", "SUPLEMENTACION Y CONTROL")
                    lote = c2.text_input("Lote", "DMM-SANTA LUCIA-CAB")
                    cat = c3.text_input("Categoría", "CB6")
                    pot = c4.text_input("Potrero", "PIATA1")
                    f_pes = c5.date_input("Último Pesaje", value=fecha_dt)
                    c6, c7, c8, c9, c10 = st.columns(5)
                    pm = c6.number_input("PM (kg)", value=200.0, step=1.0)
                    cant = c7.number_input("Cantidad", value=300, step=1)
                    orig = c8.text_input("Origen / Destino", "ESTANCIA SANTA LUCIA")
                    gmd = c9.number_input("GMD Esperado", value=0.4, step=0.05)
                    pct = c10.number_input("Consumo %PV", value=0.0055, format="%.4f")
                    if st.form_submit_button("Guardar Registro", type="primary"):
                        run_exec("""
                            INSERT INTO ganados_campo (fecha, actividad, lote, categoria, potrero, fecha_ultimo_pesaje, pm, cantidad, origen_destino, gmd_esperado, consumo_pct_pv)
                            VALUES (:f, :act, :lote, :cat, :pot, :fp, :pm, :cant, :orig, :gmd, :pct)
                        """, {"f": f_sel, "act": act, "lote": lote, "cat": cat, "pot": pot, "fp": f_pes.strftime("%Y-%m-%d"), "pm": pm, "cant": int(cant), "orig": orig, "gmd": gmd, "pct": pct})
                        st.success("Guardado correctamente.")
                        st.rerun()

        df_gan_mes = run_query("SELECT * FROM ganados_campo WHERE fecha LIKE :m ORDER BY fecha DESC, id DESC", {"m": f"{mes_prefix}%"})
        st.dataframe(df_gan_mes, use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------------
    # TAB 3: CONFINAMIENTO Y RECEPCION HOTELERIA (CON CATEGORIA)
    # --------------------------------------------------------------------------
    with tabs[2]:
        st.subheader("🐂 Corrales Activos en Confinamiento / Engorde")
        if es_editor:
            with st.expander("➕ Cargar / Actualizar Corral Activo"):
                with st.form("form_corral"):
                    c1, c2, c3, c4 = st.columns(4)
                    corral = c1.text_input("Corral", "51")
                    lote_c = c2.text_input("Lote", "LOTE 51 - FRIGOMER")
                    cant_c = c3.number_input("Cantidad", value=100, step=1)
                    peso_e = c4.number_input("Peso Entrada (kg)", value=320.0, step=1.0)
                    c5, c6, c7 = st.columns(3)
                    f_ent = c5.date_input("Fecha Entrada", value=fecha_dt)
                    gmd_c = c6.number_input("GMD (kg/día)", value=1.4, step=0.05)
                    prop_c = c7.text_input("Propietario", "FRIGOMER")
                    if st.form_submit_button("Guardar Corral", type="primary"):
                        run_exec("DELETE FROM confinamiento WHERE corral = :c", {"c": corral.strip()})
                        run_exec("""
                            INSERT INTO confinamiento (corral, lote, cantidad, peso_entrada, fecha_entrada, gmd, propietario)
                            VALUES (:c, :l, :cant, :pe, :fe, :gmd, :prop)
                        """, {"c": corral.strip(), "l": lote_c, "cant": int(cant_c), "pe": peso_e, "fe": f_ent.strftime("%Y-%m-%d"), "gmd": gmd_c, "prop": prop_c})
                        st.success(f"Corral {corral} actualizado.")
                        st.rerun()

        if not df_conf.empty:
            df_c_view = df_conf.copy()
            df_c_view["dias_feedlot"] = df_c_view["fecha_entrada"].apply(lambda x: max(0, (fecha_dt - datetime.datetime.strptime(str(x)[:10], "%Y-%m-%d").date()).days))
            df_c_view["ganancia_kg"] = (df_c_view["dias_feedlot"] * df_c_view["gmd"]).round(1)
            df_c_view["peso_proy_kg"] = (df_c_view["peso_entrada"] + df_c_view["ganancia_kg"]).round(2)
            st.dataframe(df_c_view, use_container_width=True, hide_index=True)
        else:
            st.info("No hay corrales activos registrados.")

        st.divider()
        st.subheader("📥 Recepción de Tropas / Entradas de Hotelería (Pendientes de Corral)")
        if es_editor:
            with st.expander("➕ Registrar Entrada / Recepción de Hotelería", expanded=True):
                with st.form("form_recepcion"):
                    r1, r2, r3, r4, r5 = st.columns(5)
                    rec_fecha = r1.date_input("Fecha Llegada", value=fecha_dt)
                    rec_prop = r2.selectbox("Propietario / Cliente", ["FRIGOMER", "AG LA MARIA SA", "SAN LUIS AGSA", "MINERVA FOODS", "OTRO CLIENTE HOTELERIA"])
                    rec_mod = r3.selectbox("Modalidad", ["HOTELERIA", "PROPIO", "CAPITALIZACION"])
                    rec_lote = r4.text_input("Tropa / Lote", "TROPA 1 - FRIGOMER")
                    rec_cat = r5.selectbox("Categoría", ["NOVILLO", "TORITO", "VAQUILLONA", "DESMAMANTE MACHO", "DESMAMANTE HEMBRA", "VACA", "TORO"])

                    r6, r7, r8, r9, r10 = st.columns(5)
                    rec_cant = r6.number_input("Cantidad (cab.)", value=0, step=1)
                    rec_peso = r7.number_input("Peso Prom. (kg)", value=0.0, step=1.0)
                    rec_corral = r8.text_input("Corral Previsto", "51")
                    rec_estado = r9.selectbox("Estado", ["EN RECEPCION / PESAJE", "EN DESCARGA", "CUARENTENA / SANITACION", "INGRESADO A CORRAL"])
                    rec_obs = r10.text_input("Observaciones", "Entrada de hotelería en proceso")

                    if st.form_submit_button("📥 Registrar Entrada / Recepción", type="primary"):
                        run_exec("""
                            INSERT INTO recepcion_hoteleria (fecha_llegada, propietario, modalidad, tropa_lote, categoria, cantidad, peso_prom_kg, corral_destino, estado, observaciones)
                            VALUES (:fl, :pr, :mo, :lo, :ca, :cn, :pe, :co, :es, :ob)
                        """, {
                            "fl": rec_fecha.strftime("%Y-%m-%d"), "pr": rec_prop, "mo": rec_mod,
                            "lo": rec_lote, "ca": rec_cat, "cn": int(rec_cant), "pe": rec_peso,
                            "co": rec_corral.strip(), "es": rec_estado, "ob": rec_obs
                        })
                        st.success("Entrada de hotelería registrada.")
                        st.rerun()

        st.dataframe(df_rec, use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------------
    # TAB 4: MAQUINARIAS Y CAMIONES
    # --------------------------------------------------------------------------
    with tabs[3]:
        st.subheader("🚜 Maquinarias")
        if es_editor:
            c_btn1, _ = st.columns([1.5, 3])
            if c_btn1.button("⚡ Cargar las 4 Máquinas Habituales del Día"):
                for item in PLANTILLA_MAQUINARIAS:
                    df_ult = run_query("SELECT horometro_final FROM maquinarias WHERE maquina = :m AND horometro_final > 0 ORDER BY fecha DESC, id DESC LIMIT 1", {"m": item["maquina"]})
                    ult_h = float(df_ult.iloc[0]["horometro_final"]) if not df_ult.empty else 0.0
                    run_exec("""
                        INSERT INTO maquinarias (fecha, maquina, operador, actividad, horometro_inicio, horometro_final, hs_dia, combustible_l)
                        VALUES (:f, :m, :op, :act, :hi, :hf, 0, 0)
                    """, {"f": f_sel, "m": item["maquina"], "op": item["operador"], "act": item["actividad"], "hi": ult_h, "hf": ult_h})
                st.success("Plantilla de maquinarias cargada.")
                st.rerun()

            with st.form("form_maq"):
                m1, m2, m3, m4, m5, m6 = st.columns([1.2, 1.4, 2, 1, 1, 1])
                maq = m1.selectbox("Máquina", ["PALA SEM", "TRACTOR 12", "TRACTOR 9", "TRACTOR 8"])
                op = m2.selectbox("Operador", OPERADORES_MAQUINARIA)
                act_m = m3.selectbox("Actividad", ACTIVIDADES_MAQUINARIA)
                h_ini = m4.number_input("Horóm. Ini", value=0.0, step=0.1)
                h_fin = m5.number_input("Horóm. Fin", value=0.0, step=0.1)
                comb_m = m6.number_input("Comb. (L)", value=0.0, step=1.0)
                if st.form_submit_button("Guardar Máquina", type="primary"):
                    hs = max(0.0, h_fin - h_ini)
                    run_exec("""
                        INSERT INTO maquinarias (fecha, maquina, operador, actividad, horometro_inicio, horometro_final, hs_dia, combustible_l)
                        VALUES (:f, :m, :op, :act, :hi, :hf, :hs, :cb)
                    """, {"f": f_sel, "m": maq, "op": op, "act": act_m, "hi": h_ini, "hf": h_fin, "hs": hs, "cb": comb_m})
                    if comb_m > 0:
                        run_exec("INSERT INTO combustible (fecha, equipo, categoria, litros, horometro_km, observaciones) VALUES (:f, :eq, 'MAQUINARIA', :lt, :hk, 'Carga desde Maquinarias')",
                                 {"f": f_sel, "eq": maq, "lt": comb_m, "hk": h_fin})
                    st.rerun()

        df_maq_mes = run_query("SELECT * FROM maquinarias WHERE fecha LIKE :m ORDER BY fecha DESC, id DESC", {"m": f"{mes_prefix}%"})
        st.dataframe(df_maq_mes, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("🚛 Camiones y Fletes")
        if es_editor:
            with st.form("form_cam"):
                k1, k2, k3, k4, k5, k6 = st.columns([1, 1.3, 2, 1, 1, 1.5])
                cam = k1.text_input("Camión", "SCANIA")
                dest = k2.text_input("Destino", "FRIG BELEN")
                carga = k3.text_input("Carga", "TRANSPORTE DE TROPAS")
                km = k4.number_input("Km", value=0.0, step=1.0)
                comb_c = k5.number_input("Comb. (L)", value=0.0, step=1.0)
                obs_c = k6.text_input("Observaciones", "")
                if st.form_submit_button("Guardar Camión", type="primary"):
                    run_exec("""
                        INSERT INTO camiones (fecha, camion, destino, descripcion_carga, kilometraje, combustible_l, observaciones)
                        VALUES (:f, :c, :d, :cg, :km, :cb, :ob)
                    """, {"f": f_sel, "c": cam, "d": dest, "cg": carga, "km": km, "cb": comb_c, "ob": obs_c})
                    if comb_c > 0:
                        run_exec("INSERT INTO combustible (fecha, equipo, categoria, litros, horometro_km, observaciones) VALUES (:f, :eq, 'CAMION', :lt, :hk, 'Carga desde Camiones')",
                                 {"f": f_sel, "eq": cam, "lt": comb_c, "hk": km})
                    st.rerun()

        df_cam_mes = run_query("SELECT * FROM camiones WHERE fecha LIKE :m ORDER BY fecha DESC, id DESC", {"m": f"{mes_prefix}%"})
        st.dataframe(df_cam_mes, use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------------
    # TAB 5: COMBUSTIBLE
    # --------------------------------------------------------------------------
    with tabs[4]:
        if es_editor:
            with st.form("form_comb"):
                b1, b2, b3, b4 = st.columns([1.8, 1.2, 1, 2])
                eq = b1.selectbox("Equipo / Vehículo", EQUIPOS_COMBUSTIBLE)
                cat_cb = b2.selectbox("Categoría", ["GENERADOR", "PATRULLA/VEHICULO", "MAQUINARIA", "CAMION"])
                litros = b3.number_input("Litros (L)", value=40.0, step=1.0)
                obs_cb = b4.text_input("Observaciones", "")
                if st.form_submit_button("Registrar Despacho", type="primary"):
                    run_exec("INSERT INTO combustible (fecha, equipo, categoria, litros, horometro_km, observaciones) VALUES (:f, :eq, :cat, :lt, 0, :ob)",
                             {"f": f_sel, "eq": eq, "cat": cat_cb, "lt": litros, "ob": obs_cb})
                    st.rerun()

        df_comb_mes = run_query("SELECT * FROM combustible WHERE fecha LIKE :m ORDER BY fecha DESC, id DESC", {"m": f"{mes_prefix}%"})
        st.dataframe(df_comb_mes, use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------------
    # TAB 6: BALANCEADOS
    # --------------------------------------------------------------------------
    with tabs[5]:
        if es_editor:
            with st.form("form_bal"):
                d1, d2, d3, d4 = st.columns([1.5, 1, 1.5, 2])
                tipo_b = d1.selectbox("Tipo", ["N. Terminacion", "Prem - Terminacion", "BALANCEADO PROTEICO", "NUCLEO RECRIA"])
                kg_b = d2.number_input("Producción (kg)", value=500.0, step=50.0)
                dest_b = d3.text_input("Destino", "ESS (Estancia Santa Silvia)")
                obs_b = d4.text_input("Observaciones", "Producción normal de la mañana")
                if st.form_submit_button("Guardar Producción", type="primary"):
                    run_exec("INSERT INTO balanceados (fecha, tipo, produccion_kg, destino, observaciones) VALUES (:f, :tp, :kg, :ds, :ob)",
                             {"f": f_sel, "tp": tipo_b, "kg": kg_b, "ds": dest_b, "ob": obs_b})
                    st.rerun()

        df_bal_mes = run_query("SELECT * FROM balanceados WHERE fecha LIKE :m ORDER BY fecha DESC, id DESC", {"m": f"{mes_prefix}%"})
        st.dataframe(df_bal_mes, use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------------
    # TAB 7: PERSONAL Y ADM
    # --------------------------------------------------------------------------
    with tabs[6]:
        st.subheader("👷 Asistencia y Trabajos del Personal")
        if es_editor:
            if st.button("⚡ Cargar Todo el Personal (Todos Presentes)"):
                for item in LISTA_PERSONAL:
                    run_exec("INSERT INTO personal (fecha, personal, actividad, asistencia) VALUES (:f, :p, :a, 'PRESENTE')",
                             {"f": f_sel, "p": item["nombre"], "a": item["actividad_default"]})
                st.rerun()

            with st.form("form_per"):
                p1, p2, p3 = st.columns([1.5, 2.2, 1])
                nom_p = p1.selectbox("Personal", [x["nombre"] for x in LISTA_PERSONAL])
                act_p = p2.selectbox("Actividad", ACTIVIDADES_FRECUENTES)
                est_p = p3.selectbox("Estado", ["PRESENTE", "AUSENTE", "PERMISO", "REPOSO"])
                if st.form_submit_button("Agregar Personal", type="primary"):
                    run_exec("INSERT INTO personal (fecha, personal, actividad, asistencia) VALUES (:f, :p, :a, :e)",
                             {"f": f_sel, "p": nom_p, "a": act_p, "e": est_p})
                    st.rerun()

        df_per_mes = run_query("SELECT * FROM personal WHERE fecha LIKE :m ORDER BY fecha DESC, id DESC", {"m": f"{mes_prefix}%"})
        st.dataframe(df_per_mes, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("📋 Supervisión Administrativa y Capataces (ADM)")
        if es_editor:
            if st.button("⚡ Cargar Todos los Encargados / Capataces ADM"):
                for item in PLANTILLA_ADM:
                    run_exec("INSERT INTO adm_supervision (fecha, cargo, actividad) VALUES (:f, :c, :a)",
                             {"f": f_sel, "c": item["cargo"], "a": item["actividad"]})
                st.rerun()

            with st.form("form_adm"):
                a1, a2 = st.columns([1.5, 3])
                cargo_a = a1.selectbox("Cargo", [x["cargo"] for x in PLANTILLA_ADM])
                act_a = a2.selectbox("Actividad", ACTIVIDADES_ADM)
                if st.form_submit_button("Registrar ADM", type="primary"):
                    run_exec("INSERT INTO adm_supervision (fecha, cargo, actividad) VALUES (:f, :c, :a)",
                             {"f": f_sel, "c": cargo_a, "a": act_a})
                    st.rerun()

        df_adm_mes = run_query("SELECT * FROM adm_supervision WHERE fecha LIKE :m ORDER BY fecha DESC, id DESC", {"m": f"{mes_prefix}%"})
        st.dataframe(df_adm_mes, use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------------
    # TAB 8: LLUVIAS Y NOVEDADES
    # --------------------------------------------------------------------------
    with tabs[7]:
        st.subheader("🌧️ Pluviometría por Sector")
        if es_editor:
            with st.form("form_llu"):
                l1, l2, l3 = st.columns([1.2, 1, 2.5])
                sec_l = l1.selectbox("Sector", SECTORES_LLUVIA)
                mm_l = l2.number_input("Precipitación (mm)", value=0.0, step=0.5)
                obs_l = l3.text_input("Observaciones", "")
                if st.form_submit_button("Guardar Lluvia", type="primary"):
                    run_exec("INSERT INTO lluvias (fecha, sector, precipitacion_mm, observaciones) VALUES (:f, :s, :mm, :ob)",
                             {"f": f_sel, "s": sec_l, "mm": mm_l, "ob": obs_l})
                    st.rerun()

        st.dataframe(df_llu_mes, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("⚠️ Novedades Importantes")
        if es_editor:
            with st.form("form_nov"):
                n1, n2 = st.columns([3.5, 1])
                nov_t = n1.text_input("Novedad / Evento Destacado", "")
                prio_t = n2.selectbox("Prioridad", ["ALTA", "MEDIA", "BAJA"])
                if st.form_submit_button("Registrar Novedad", type="primary"):
                    if nov_t.strip():
                        run_exec("INSERT INTO novedades (fecha, novedad, prioridad) VALUES (:f, :n, :p)",
                                 {"f": f_sel, "n": nov_t.strip(), "p": prio_t})
                        st.rerun()

        df_nov_mes = run_query("SELECT * FROM novedades WHERE fecha LIKE :m ORDER BY fecha DESC, id DESC", {"m": f"{mes_prefix}%"})
        st.dataframe(df_nov_mes, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
