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
# IMPORTADOR AUTOMATICO DE PLANILLA EXCEL (NOVIEMBRE 2026.xlsx O EXPORTADO)
# ==============================================================================
def _clean_date(val):
    if pd.isna(val):
        return None
    s = str(val).strip()
    if not s or s.lower() in ["nan", "nat", "total", "none"]:
        return None
    try:
        dt = pd.to_datetime(val, errors="coerce")
        if pd.isna(dt):
            return None
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def _clean_float(val, default=0.0):
    try:
        if pd.isna(val):
            return default
        return float(val)
    except Exception:
        return default


def _clean_int(val, default=0):
    try:
        if pd.isna(val):
            return default
        return int(float(val))
    except Exception:
        return default


def _clean_str(val, default=""):
    if pd.isna(val):
        return default
    s = str(val).strip()
    return default if s.lower() in ["nan", "none", "nat"] else s


def importar_excel_a_nube(uploaded_file, modo_reemplazo="mes"):
    xls = pd.ExcelFile(uploaded_file)
    sheets = xls.sheet_names
    eng = get_engine()
    resumen = {}
    fechas_detectadas = set()

    # 1. GANADOS
    df_gan_rows = []
    sheet_gan = "GANADOS" if "GANADOS" in sheets else ("GANADOS_CAMPO" if "GANADOS_CAMPO" in sheets else None)
    if sheet_gan:
        hdr = 2 if sheet_gan == "GANADOS" else 0
        df = pd.read_excel(xls, sheet_name=sheet_gan, header=hdr)
        df.columns = [str(c).strip().upper() for c in df.columns]
        for _, r in df.iterrows():
            f_str = _clean_date(r.get("FECHA"))
            lote = _clean_str(r.get("LOTE"))
            if not f_str or not lote:
                continue
            fechas_detectadas.add(f_str)
            df_gan_rows.append({
                "fecha": f_str,
                "actividad": _clean_str(r.get("ACTIVIDAD"), "SUPLEMENTACION Y CONTROL"),
                "lote": lote,
                "categoria": _clean_str(r.get("CATEGORIA") or r.get("CATEGORÍA")),
                "potrero": _clean_str(r.get("POTRERO")),
                "fecha_ultimo_pesaje": _clean_date(r.get("FECHA ULTIMO PESAJE") or r.get("FECHA_ULTIMO_PESAJE")) or f_str,
                "pm": _clean_float(r.get("PM")),
                "cantidad": _clean_int(r.get("CANTIDAD")),
                "origen_destino": _clean_str(r.get("ORIGEN / DESTINO") or r.get("ORIGEN_DESTINO")),
                "gmd_esperado": _clean_float(r.get("GMD ESPERADO") or r.get("GMD_ESPERADO"), 0.4),
                "consumo_pct_pv": _clean_float(r.get("CONSUMO / % PV") or r.get("CONSUMO_PCT_PV"), 0.0055),
            })

    # 2. CONFINAMIENTO
    df_conf_rows = []
    if "CONFINAMIENTO" in sheets:
        raw_c = pd.read_excel(xls, sheet_name="CONFINAMIENTO", header=None)
        hdr_c = 2 if str(raw_c.iloc[2, 0]).strip().upper() == "CORRAL" else 0
        df = pd.read_excel(xls, sheet_name="CONFINAMIENTO", header=hdr_c)
        df.columns = [str(c).strip().upper() for c in df.columns]
        for _, r in df.iterrows():
            corral = _clean_str(r.get("CORRAL")).replace(".0", "")
            lote = _clean_str(r.get("LOTE"))
            if not corral or not lote or corral.lower() == "total":
                continue
            df_conf_rows.append({
                "corral": corral,
                "lote": lote,
                "cantidad": _clean_int(r.get("CANTIDAD")),
                "peso_entrada": _clean_float(r.get("PESO DE ENTRADAS") or r.get("PESO_ENTRADA")),
                "fecha_entrada": _clean_date(r.get("FECHA DE ENTRADAS") or r.get("FECHA_ENTRADA")) or datetime.date.today().strftime("%Y-%m-%d"),
                "gmd": _clean_float(r.get("GANANCIA DIARIA (KG/DÍA)") or r.get("GMD"), 1.4),
                "propietario": _clean_str(r.get("PROPIETARIO"), "SAN LUIS AGSA"),
            })

    # 3. MAQUINARIAS
    df_maq_rows = []
    sheet_maq = "MAQUINARIAS" if "MAQUINARIAS" in sheets else ("MAQUINARIAS_DIA" if "MAQUINARIAS_DIA" in sheets else None)
    if sheet_maq:
        hdr = 2 if sheet_maq == "MAQUINARIAS" else 0
        df = pd.read_excel(xls, sheet_name=sheet_maq, header=hdr)
        df.columns = [str(c).strip().upper() for c in df.columns]
        for _, r in df.iterrows():
            f_str = _clean_date(r.get("FECHA"))
            maq = _clean_str(r.get("MAQUINA"))
            if not f_str or not maq:
                continue
            fechas_detectadas.add(f_str)
            h_ini = _clean_float(r.get("INICIO") or r.get("HOROMETRO_INICIO"))
            h_fin = _clean_float(r.get("FINAL") or r.get("HOROMETRO_FINAL"))
            hs_d = _clean_float(r.get("HS/DIA") or r.get("HS_DIA"), max(0.0, h_fin - h_ini))
            df_maq_rows.append({
                "fecha": f_str,
                "maquina": maq,
                "operador": _clean_str(r.get("OPERADOR")),
                "actividad": _clean_str(r.get("ACTIVIDAD")),
                "horometro_inicio": h_ini,
                "horometro_final": h_fin,
                "hs_dia": hs_d,
                "combustible_l": _clean_float(r.get("COMBUSTIBLE (L)") or r.get("COMBUSTIBLE_L")),
            })

    # 4. CAMIONES
    df_cam_rows = []
    sheet_cam = "CAMIONES" if "CAMIONES" in sheets else ("CAMIONES_DIA" if "CAMIONES_DIA" in sheets else None)
    if sheet_cam:
        hdr = 2 if sheet_cam == "CAMIONES" else 0
        df = pd.read_excel(xls, sheet_name=sheet_cam, header=hdr)
        df.columns = [str(c).strip().upper() for c in df.columns]
        for _, r in df.iterrows():
            f_str = _clean_date(r.get("FECHA"))
            cam = _clean_str(r.get("CAMION"))
            if not f_str or not cam:
                continue
            fechas_detectadas.add(f_str)
            df_cam_rows.append({
                "fecha": f_str,
                "camion": cam,
                "destino": _clean_str(r.get("DESTINO")),
                "descripcion_carga": _clean_str(r.get("DESCRIPCION DE CARGA") or r.get("DESCRIPCION_CARGA")),
                "kilometraje": _clean_float(r.get("KILOMETRAJE")),
                "combustible_l": _clean_float(r.get("COMBUSTIBLE (L)") or r.get("COMBUSTIBLE_L")),
                "observaciones": _clean_str(r.get("OBSERVACIONES")),
            })

    # 5. COMBUSTIBLE (Matriz por equipo o tabla plana)
    df_comb_rows = []
    sheet_comb = "COMBUSTIBLE" if "COMBUSTIBLE" in sheets else ("COMBUSTIBLE_DIA" if "COMBUSTIBLE_DIA" in sheets else None)
    if sheet_comb:
        df = pd.read_excel(xls, sheet_name=sheet_comb, header=0)
        cols_up = [str(c).strip().upper() for c in df.columns]
        df.columns = cols_up
        if "EQUIPO" in cols_up and "LITROS" in cols_up:
            for _, r in df.iterrows():
                f_str = _clean_date(r.get("FECHA"))
                eq = _clean_str(r.get("EQUIPO"))
                lt = _clean_float(r.get("LITROS"))
                if not f_str or not eq or lt <= 0:
                    continue
                fechas_detectadas.add(f_str)
                df_comb_rows.append({
                    "fecha": f_str, "equipo": eq,
                    "categoria": _clean_str(r.get("CATEGORIA"), "GENERAL"),
                    "litros": lt, "horometro_km": _clean_float(r.get("HOROMETRO_KM")),
                    "observaciones": _clean_str(r.get("OBSERVACIONES")),
                })
        else:
            ignore_cols = {"FECHA", "TOTAL"}
            eq_cols = [c for c in cols_up if c not in ignore_cols and not c.startswith("UNNAMED")]
            for _, r in df.iterrows():
                f_str = _clean_date(r.get("FECHA"))
                if not f_str:
                    continue
                fechas_detectadas.add(f_str)
                for eq in eq_cols:
                    lt = _clean_float(r.get(eq))
                    if lt > 0:
                        if any(x in eq for x in ["TRACTOR", "PALA"]):
                            cat_cb = "MAQUINARIA"
                        elif any(x in eq for x in ["SCANIA", "VOLVO"]):
                            cat_cb = "CAMION"
                        elif "GENERADOR" in eq:
                            cat_cb = "GENERADOR"
                        else:
                            cat_cb = "PATRULLA/VEHICULO"
                        df_comb_rows.append({
                            "fecha": f_str, "equipo": eq, "categoria": cat_cb,
                            "litros": lt, "horometro_km": 0.0,
                            "observaciones": "Importado desde Excel",
                        })

    # 6. BALANCEADOS
    df_bal_rows = []
    sheet_bal = next((s for s in ["NUCLEO Y BALANCEADOS", "BALANCEADOS", "BALANCEADOS_DIA"] if s in sheets), None)
    if sheet_bal:
        hdr = 2 if sheet_bal == "NUCLEO Y BALANCEADOS" else 0
        df = pd.read_excel(xls, sheet_name=sheet_bal, header=hdr)
        df.columns = [str(c).strip().upper() for c in df.columns]
        for _, r in df.iterrows():
            f_str = _clean_date(r.get("FECHA"))
            tipo = _clean_str(r.get("TIPO DE BALANCEADO O NUCLEO") or r.get("TIPO"))
            kg = _clean_float(r.get("PRODUCCION (KG)") or r.get("PRODUCCION_KG"))
            if not f_str or (not tipo and kg <= 0):
                continue
            fechas_detectadas.add(f_str)
            df_bal_rows.append({
                "fecha": f_str,
                "tipo": tipo or "BALANCEADO",
                "produccion_kg": kg,
                "destino": _clean_str(r.get("DESTINO"), "ESS (Estancia Santa Silvia)"),
                "observaciones": _clean_str(r.get("OBSERVACIONES")),
            })

    # 7. PERSONAL
    df_per_rows = []
    sheet_per = "PERSONAL" if "PERSONAL" in sheets else ("PERSONAL_DIA" if "PERSONAL_DIA" in sheets else None)
    if sheet_per:
        raw_p = pd.read_excel(xls, sheet_name=sheet_per, header=None)
        hdr_p = 2 if str(raw_p.iloc[2, 0]).strip().upper() == "FECHA" else 0
        df = pd.read_excel(xls, sheet_name=sheet_per, header=hdr_p)
        df.columns = [str(c).strip().upper() for c in df.columns]
        for _, r in df.iterrows():
            f_str = _clean_date(r.get("FECHA"))
            nom = _clean_str(r.get("PERSONAL"))
            if not f_str or not nom:
                continue
            fechas_detectadas.add(f_str)
            act = _clean_str(r.get("ACTIVIDAD REALIZADA") or r.get("ACTIVIDAD"))
            asis = _clean_str(r.get("ASISTENCIA"), "PRESENTE").upper()
            if act.upper() == "AUSENTE":
                asis = "AUSENTE"
            df_per_rows.append({
                "fecha": f_str, "personal": nom, "actividad": act, "asistencia": asis
            })

    # 8. ADM
    df_adm_rows = []
    sheet_adm = "ADM" if "ADM" in sheets else ("SUPERVISION_ADM" if "SUPERVISION_ADM" in sheets else None)
    if sheet_adm:
        raw_a = pd.read_excel(xls, sheet_name=sheet_adm, header=None)
        hdr_a = 2 if str(raw_a.iloc[2, 0]).strip().upper() == "FECHA" else 0
        df = pd.read_excel(xls, sheet_name=sheet_adm, header=hdr_a)
        cols_up = [str(c).strip().upper() for c in df.columns]
        df.columns = cols_up
        if "CARGO" in cols_up and "ACTIVIDAD" in cols_up:
            for _, r in df.iterrows():
                f_str = _clean_date(r.get("FECHA"))
                cargo = _clean_str(r.get("CARGO"))
                act = _clean_str(r.get("ACTIVIDAD"))
                if f_str and cargo and act:
                    fechas_detectadas.add(f_str)
                    df_adm_rows.append({"fecha": f_str, "cargo": cargo, "actividad": act})
        else:
            cargos = [c for c in cols_up if c != "FECHA" and not c.startswith("UNNAMED")]
            for _, r in df.iterrows():
                f_str = _clean_date(r.get("FECHA"))
                if not f_str:
                    continue
                fechas_detectadas.add(f_str)
                for cg in cargos:
                    act = _clean_str(r.get(cg))
                    if act:
                        df_adm_rows.append({"fecha": f_str, "cargo": cg, "actividad": act})

    # 9. LLUVIAS
    df_llu_rows = []
    sheet_llu = "LLUVIAS" if "LLUVIAS" in sheets else ("LLUVIAS_DIA" if "LLUVIAS_DIA" in sheets else None)
    if sheet_llu:
        raw_l = pd.read_excel(xls, sheet_name=sheet_llu, header=None)
        hdr_l = 2 if str(raw_l.iloc[2, 0]).strip().upper() == "FECHA" else 0
        df = pd.read_excel(xls, sheet_name=sheet_llu, header=hdr_l)
        df.columns = [str(c).strip().upper() for c in df.columns]
        for _, r in df.iterrows():
            f_str = _clean_date(r.get("FECHA"))
            sec = _clean_str(r.get("SECTOR"))
            if not f_str or not sec:
                continue
            fechas_detectadas.add(f_str)
            df_llu_rows.append({
                "fecha": f_str, "sector": sec,
                "precipitacion_mm": _clean_float(r.get("PRECIPITACION (MM)") or r.get("PRECIPITACION_MM")),
                "observaciones": _clean_str(r.get("OBSERVACIONES")),
            })

    # 10. NOVEDADES
    df_nov_rows = []
    sheet_nov = next((s for s in ["IMPORTANTES", "NOVEDADES", "NOVEDADES_DIA"] if s in sheets), None)
    if sheet_nov:
        raw_n = pd.read_excel(xls, sheet_name=sheet_nov, header=None)
        hdr_n = 2 if str(raw_n.iloc[2, 0]).strip().upper() == "FECHA" else 0
        df = pd.read_excel(xls, sheet_name=sheet_nov, header=hdr_n)
        df.columns = [str(c).strip().upper() for c in df.columns]
        for _, r in df.iterrows():
            f_str = _clean_date(r.get("FECHA"))
            nov = _clean_str(r.get("NOVEDAD / EVENTO DESTACADO") or r.get("NOVEDAD"))
            if not f_str or not nov or nov == "0":
                continue
            fechas_detectadas.add(f_str)
            prio = _clean_str(r.get("NIVEL DE PRIORIDAD") or r.get("PRIORIDAD"), "MEDIA").upper()
            if prio not in ["ALTA", "MEDIA", "BAJA"]:
                prio = "MEDIA"
            df_nov_rows.append({"fecha": f_str, "novedad": nov, "prioridad": prio})

    if not fechas_detectadas and not df_conf_rows:
        return {"error": "No se encontraron registros válidos con fecha en el archivo Excel."}

    meses_afectados = sorted({f[:7] for f in fechas_detectadas})
    with eng.begin() as conn:
        tablas_diarias = [
            "ganados_campo", "maquinarias", "camiones", "combustible",
            "balanceados", "personal", "adm_supervision", "lluvias", "novedades"
        ]
        if modo_reemplazo == "mes":
            for m in meses_afectados:
                for tb in tablas_diarias:
                    conn.execute(text(f"DELETE FROM {tb} WHERE fecha LIKE :m"), {"m": f"{m}%"})
        elif modo_reemplazo == "fechas":
            for f_d in fechas_detectadas:
                for tb in tablas_diarias:
                    conn.execute(text(f"DELETE FROM {tb} WHERE fecha = :f"), {"f": f_d})

        if df_gan_rows:
            conn.execute(text("""
                INSERT INTO ganados_campo (fecha, actividad, lote, categoria, potrero, fecha_ultimo_pesaje, pm, cantidad, origen_destino, gmd_esperado, consumo_pct_pv)
                VALUES (:fecha, :actividad, :lote, :categoria, :potrero, :fecha_ultimo_pesaje, :pm, :cantidad, :origen_destino, :gmd_esperado, :consumo_pct_pv)
            """), df_gan_rows)
        if df_conf_rows:
            for row in df_conf_rows:
                conn.execute(text("DELETE FROM confinamiento WHERE corral = :c"), {"c": row["corral"]})
            conn.execute(text("""
                INSERT INTO confinamiento (corral, lote, cantidad, peso_entrada, fecha_entrada, gmd, propietario)
                VALUES (:corral, :lote, :cantidad, :peso_entrada, :fecha_entrada, :gmd, :propietario)
            """), df_conf_rows)
        if df_maq_rows:
            conn.execute(text("""
                INSERT INTO maquinarias (fecha, maquina, operador, actividad, horometro_inicio, horometro_final, hs_dia, combustible_l)
                VALUES (:fecha, :maquina, :operador, :actividad, :horometro_inicio, :horometro_final, :hs_dia, :combustible_l)
            """), df_maq_rows)
        if df_cam_rows:
            conn.execute(text("""
                INSERT INTO camiones (fecha, camion, destino, descripcion_carga, kilometraje, combustible_l, observaciones)
                VALUES (:fecha, :camion, :destino, :descripcion_carga, :kilometraje, :combustible_l, :observaciones)
            """), df_cam_rows)
        if df_comb_rows:
            conn.execute(text("""
                INSERT INTO combustible (fecha, equipo, categoria, litros, horometro_km, observaciones)
                VALUES (:fecha, :equipo, :categoria, :litros, :horometro_km, :observaciones)
            """), df_comb_rows)
        if df_bal_rows:
            conn.execute(text("""
                INSERT INTO balanceados (fecha, tipo, produccion_kg, destino, observaciones)
                VALUES (:fecha, :tipo, :produccion_kg, :destino, :observaciones)
            """), df_bal_rows)
        if df_per_rows:
            conn.execute(text("""
                INSERT INTO personal (fecha, personal, actividad, asistencia)
                VALUES (:fecha, :personal, :actividad, :asistencia)
            """), df_per_rows)
        if df_adm_rows:
            conn.execute(text("""
                INSERT INTO adm_supervision (fecha, cargo, actividad)
                VALUES (:fecha, :cargo, :actividad)
            """), df_adm_rows)
        if df_llu_rows:
            conn.execute(text("""
                INSERT INTO lluvias (fecha, sector, precipitacion_mm, observaciones)
                VALUES (:fecha, :sector, :precipitacion_mm, :observaciones)
            """), df_llu_rows)
        if df_nov_rows:
            conn.execute(text("""
                INSERT INTO novedades (fecha, novedad, prioridad)
                VALUES (:fecha, :novedad, :prioridad)
            """), df_nov_rows)

    resumen["Ganados Campo"] = len(df_gan_rows)
    resumen["Corrales Confinamiento"] = len(df_conf_rows)
    resumen["Maquinarias"] = len(df_maq_rows)
    resumen["Camiones"] = len(df_cam_rows)
    resumen["Combustible"] = len(df_comb_rows)
    resumen["Balanceados"] = len(df_bal_rows)
    resumen["Personal"] = len(df_per_rows)
    resumen["Supervisión ADM"] = len(df_adm_rows)
    resumen["Lluvias"] = len(df_llu_rows)
    resumen["Novedades"] = len(df_nov_rows)
    resumen["ultima_fecha"] = max(fechas_detectadas) if fechas_detectadas else None
    return resumen


# ==============================================================================
# SISTEMA DE LOGIN CON USUARIO, CONTRASEÑA Y ROLES (CARGA VS LECTURA)
# ==============================================================================
def get_users_db():
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
            run_query("SELECT fecha, camion, destino, descripcion_carga,
