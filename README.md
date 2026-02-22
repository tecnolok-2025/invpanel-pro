# INVPanel PRO (V5)

Sistema web para registro de carteras, simulación y análisis estadístico educativo.

> **Aviso**: el sistema y sus rankings son **educativos** y **no constituyen asesoramiento financiero**.

---

## 1) Qué incluye la V5 (PRO)

- **Panel / Dashboard**
- **Portafolios** (registro de transacciones reales)
- **Simulador** (dinero virtual, precios sintéticos)
- **Análisis (PRO)** con métricas simples sobre históricos cargados por CSV:
  - Retorno del período
  - Volatilidad anualizada (aprox.)
  - Sharpe simple (rf=0)
  - Max drawdown
- **Carga de precios por CSV** (por activo)
- **Respaldo** (descarga JSON por dumpdata)
- **Alertas por email** (opcional): ranking + procedimiento paso a paso dentro del mail

---

## 2) Requisitos locales

- Python 3.11+ (recomendado 3.12)
- pip

### Instalación local rápida

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
# source .venv/bin/activate

pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Ingresá a: http://127.0.0.1:8000/

---

## 3) Variables de entorno (mínimas)

### Seguridad / dominio

- `SECRET_KEY` (obligatoria)
- `DEBUG` (0 en producción)
- `ALLOWED_HOSTS` (ej: `invpanel-pro.onrender.com`)
- `CSRF_TRUSTED_ORIGINS` (ej: `https://invpanel-pro.onrender.com`)

### Usuario admin inicial

Se crea automáticamente en el deploy si definís:

- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `ADMIN_EMAIL`

---

## 4) Base persistente “free” (recomendado)

Render free no garantiza persistencia de SQLite entre deploys. Para "resguardo para siempre" sin pagar, lo más estable es:

### Opción A: Postgres gratuito externo (Neon / Supabase)

1) Creá una base Postgres free en Neon o Supabase.
2) Copiá la cadena de conexión.
3) En Render (invpanel-pro), configurá:

- `USE_POSTGRES=1`
- `DATABASE_URL=<tu cadena>`

Listo: el dato queda fuera de Render (persistente).

### Opción B: Backup manual

- URL: `/backup/` (requiere usuario staff/admin)
- Descarga un `.json` con `dumpdata`.

Restauración (cuando se necesite):

```bash
python manage.py loaddata backup.json
```

---

## 5) Alertas por mail (ranking + procedimiento dentro del mail)

### 5.1 Variables SMTP

Configurá un SMTP. Ejemplo con Gmail (requiere **App Password**):

- `EMAIL_HOST=smtp.gmail.com`
- `EMAIL_PORT=587`
- `EMAIL_HOST_USER=<tu gmail>`
- `EMAIL_HOST_PASSWORD=<app password>`
- `EMAIL_USE_TLS=1`
- `DEFAULT_FROM_EMAIL=<tu gmail o alias>`

### 5.2 Variables de alertas

- `ALERT_EMAIL_TO=<casilla destino exclusiva>`
- `INV_BASE_URL=https://invpanel-pro.onrender.com`
- `ALERT_RUN_TOKEN=<token largo y secreto>`

### 5.3 Probar manualmente

- Logueate como admin → menú **Alertas** → `/alerts/test/`

### 5.4 Automatizar (sin iPhone)

#### Opción A: Render Cron Job

Si tu plan lo permite, creá un cron job que ejecute:

```bash
python manage.py send_alerts --base-url "$INV_BASE_URL"
```

#### Opción B: GitHub Actions (gratis)

Crear `.github/workflows/alerts.yml`:

```yaml
name: invpanel-pro-alerts
on:
  schedule:
    - cron: "0 12 * * *"  # todos los días 12:00 UTC
jobs:
  ping:
    runs-on: ubuntu-latest
    steps:
      - name: Call alerts endpoint
        run: |
          curl -fsSL "https://invpanel-pro.onrender.com/alerts/run/<TOKEN>/" || exit 1
```

> Reemplazá `<TOKEN>` por tu `ALERT_RUN_TOKEN`.

---

## 6) Carga de precios (CSV)

Ruta: `/prices/upload/`

Formato recomendado:

```csv
date,close
2025-01-02,101.25
2025-01-03,103.10
```

También soporta `fecha,precio`.

---

## 7) Render (paso a paso)

> Objetivo: crear **un servicio nuevo** “invpanel-pro” sin tocar tu invpanel actual.

### 7.1 Subir el proyecto

- Opción 1: nuevo repo `invpanel-pro`
- Opción 2: misma repo, nueva rama `pro`

Subí este código tal cual.

### 7.2 Crear Web Service en Render

1) Render → **New** → **Web Service**
2) Conectá el repo/rama
3) Runtime: **Python**
4) Build Command: `bash ./build.sh`
5) Start Command:

```bash
python -m gunicorn invpanel.asgi:application -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT
```

### 7.3 Configurar Environment Variables

**Mínimas**:
- `SECRET_KEY`
- `DEBUG=0`
- `ALLOWED_HOSTS=invpanel-pro.onrender.com`
- `CSRF_TRUSTED_ORIGINS=https://invpanel-pro.onrender.com`
- `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_EMAIL`

**Persistencia (recomendado)**:
- `USE_POSTGRES=1`
- `DATABASE_URL=...`

**Alertas (opcional)**:
- `INV_BASE_URL=https://invpanel-pro.onrender.com`
- `ALERT_RUN_TOKEN=...`
- `ALERT_EMAIL_TO=...`
- SMTP (`EMAIL_HOST`, etc.)

---

## 8) Seguridad

- No subas claves ni contraseñas al repo.
- Usá tokens largos (32+ caracteres) para `ALERT_RUN_TOKEN`.
- Cambiá `ADMIN_PASSWORD` periódicamente.

