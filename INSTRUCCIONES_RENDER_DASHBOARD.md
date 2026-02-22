# InvPanel-Pro — Deploy por Render Dashboard (sin comandos raros)

> Objetivo: subir el proyecto a GitHub y desplegarlo en Render **usando la interfaz web** (Dashboard).
> **Nota**: las Push Notifications requieren HTTPS. En Render (https://...) funcionan; en IP local pueden fallar.

## 1) Preparar carpeta local
1. Creá una carpeta vacía, por ejemplo:
   `D:\Datos\000 Plataforma de Inversiones\invpanel-pro`
2. **Descomprimí este ZIP dentro de esa carpeta** (que queden archivos como `manage.py`, `requirements.txt`, `build.sh`, `render.yaml`, carpetas `core/`, `invpanel/`, `push/`, etc).

## 2) Subir a GitHub (GitHub Desktop)
1. Abrí GitHub Desktop → **File → Add Local Repository**
2. Elegí la carpeta `invpanel-pro`
3. Si te pide inicializar repo: aceptá.
4. Commit: “Initial commit”
5. Push: **Publish repository** (elige “Private” si tenés esa opción disponible en tu cuenta).

## 3) Crear el Web Service en Render (Dashboard)
1. En Render → **New +** → **Web Service**
2. Conectá tu GitHub y elegí el repo `invpanel-pro`
3. Settings:
   - **Branch**: `main`
   - **Root Directory**: (vacío)
   - **Build Command**: `bash ./build.sh`
   - **Start Command**:
     `python -m gunicorn invpanel.asgi:application -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`
   - Plan: podés arrancar con **Free** para probar.

## 4) Variables de entorno (Render → Environment)
Mínimas:
- `DJANGO_SETTINGS_MODULE` = `invpanel.settings`
- `SECRET_KEY` = (Render puede generarla; si no, poné una larga)
- `ADMIN_USERNAME` = tu usuario (ej: `nestor`)
- `ADMIN_PASSWORD` = una clave fuerte
- `ADMIN_EMAIL` = tu email

Push Notifications (si querés activarlas):
- `VAPID_PUBLIC_KEY`
- `VAPID_PRIVATE_KEY_PEM_B64`
- `VAPID_CLAIMS_SUB` = `mailto:tuemail@dominio.com`

### Cómo generar VAPID (en Windows, 1 solo comando)
En la carpeta del proyecto:
`py tools\generate_vapid.py`

Copiá las 2 líneas y pegarlas en Render.

## 5) Deploy
Tocá **Create Web Service** y esperá “Live”.

## 6) Primer login
Entrá a la URL pública (https://...).
Logueate con `ADMIN_USERNAME` y `ADMIN_PASSWORD`.

## 7) Sobre “FREE” y datos
- El Web Service Free sirve perfecto para **pruebas**.
- Para datos “para siempre”, se recomienda usar una **DB externa con backups** (Postgres pago o un proveedor externo).


## 8) PostgreSQL (RECOMENDADO para que no se borren los datos)
En Render podés crear una base PostgreSQL y conectarla al Web Service.

1. Render → **New +** → **PostgreSQL**
2. Elegí un plan pago (por ejemplo, “Starter”).
3. Una vez creada, Render te muestra el **Internal Database URL**.
4. En tu Web Service → **Environment** agregá:
   - `DATABASE_URL` = (pegá el Internal Database URL)
5. Redeploy del Web Service.

✅ Con esto: portfolios, oportunidades, históricos y simulaciones quedan persistentes.
