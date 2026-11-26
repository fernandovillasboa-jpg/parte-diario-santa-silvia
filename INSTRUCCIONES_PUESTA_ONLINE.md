# Guía Paso a Paso: Parte Diario Online — Estancia Santa Silvia

Este paquete transforma tu sistema en una **Aplicación Web Online** con:
- **Guardado automático en la nube** (lo que cargás en la estancia aparece al instante para gerencia o el dueño desde cualquier celular o computadora).
- **Usuario y contraseña con permisos** (`admin` para cargar/editar y `gerencia` para ver y descargar Excel sin borrar nada).
- **Actualización automática**: cada vez que subís una mejora a GitHub, la página web se actualiza sola para todos.

---

## Paso 1: Crear la Base de Datos en la Nube (Supabase - Gratis)
1. Entrá a [supabase.com](https://supabase.com) e iniciá sesión con tu cuenta de Google/Gmail.
2. Hacé clic en **New Project**, poné de nombre `santa-silvia-db`, elegí una contraseña fuerte y seleccioná la región más cercana (ej. *South America - São Paulo*).
3. Una vez creado, arriba hacé clic en el botón **Connect** -> elegí **URI** (Session pooler) y copiá la dirección que empieza con `postgresql://...` (reemplazando `[YOUR-PASSWORD]` por la contraseña que creaste).

---

## Paso 2: Subir el Código a GitHub (Para actualización automática)
1. Entrá a [github.com](https://github.com) y creá una cuenta gratuita (o iniciá sesión).
2. Creá un repositorio nuevo (**New repository**) llamado `parte-diario-santa-silvia` y marcalo como **Private** (Privado).
3. Subí estos dos archivos dentro del repositorio:
   - `app_web_santa_silvia.py`
   - `requirements.txt`

---

## Paso 3: Publicar la Página Web (Streamlit Cloud - Gratis)
1. Entrá a [share.streamlit.io](https://share.streamlit.io) e iniciá sesión con tu cuenta de GitHub.
2. Hacé clic en **Create app** -> **Yup, I have an app**.
3. Elegí tu repositorio `parte-diario-santa-silvia`, rama `main`, y archivo principal `app_web_santa_silvia.py`.
4. Antes de abrir, hacé clic en **Advanced settings...** -> sección **Secrets** y pegá lo siguiente con tus datos reales:

```toml
DATABASE_URL = "postgresql://postgres.xxxxx:TU_CLAVE_SUPABASE@aws-0-sa-east-1.pooler.supabase.com:6543/postgres"

[users.admin]
password = "SantaSilvia2026"
nombre = "Administrador Estancia"
rol = "editor"

[users.gerencia]
password = "SanLuis2026"
nombre = "Gerencia / Directorio"
rol = "lector"
```

5. Hacé clic en **Deploy**. En 1 minuto vas a tener tu enlace web privado listo para compartir por WhatsApp.

---

## Paso 4: Subir tus datos actuales (Opcional)
Si ya tenés datos cargados en tu computadora dentro de `santa_silvia_parte_diario.db`:
1. Abrí el archivo `migrar_datos_a_nube.py` en la misma carpeta donde está tu `.db`.
2. Pegá tu `DATABASE_URL` de Supabase en la línea `SUPABASE_URL`.
3. Ejecutalo una sola vez (`python migrar_datos_a_nube.py`) y todos tus registros pasarán a la nube.
