import sqlite3
import pandas as pd
from sqlalchemy import create_engine

# Pega aquí tu enlace de conexión de Supabase (Transaction / Session pooler URI)
SUPABASE_URL = "postgresql://postgres.TU_PROYECTO:TU_CONTRASENA@aws-0-sa-east-1.pooler.supabase.com:6543/postgres"
SQLITE_LOCAL = "santa_silvia_parte_diario.db"

TABLAS = [
    "ganados_campo",
    "confinamiento",
    "recepcion_hoteleria",
    "maquinarias",
    "camiones",
    "combustible",
    "balanceados",
    "personal",
    "adm_supervision",
    "lluvias",
    "novedades"
]

def migrar():
    conn_local = sqlite3.connect(SQLITE_LOCAL)
    engine_nube = create_engine(SUPABASE_URL)

    for tabla in TABLAS:
        try:
            df = pd.read_sql_query(f"SELECT * FROM {tabla}", conn_local)
            if "id" in df.columns:
                df = df.drop(columns=["id"])
            if not df.empty:
                df.to_sql(tabla, engine_nube, if_exists="append", index=False)
                print(f"✅ {tabla}: {len(df)} registros subidos a la nube.")
            else:
                print(f"⚪ {tabla}: sin registros.")
        except Exception as e:
            print(f"⚠️ Error en {tabla}: {e}")

    conn_local.close()
    print("\n🎉 Migración completada. Todos tus datos ya están online.")

if __name__ == "__main__":
    migrar()
