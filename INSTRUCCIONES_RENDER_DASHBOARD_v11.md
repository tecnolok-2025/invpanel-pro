# InvPanel-Pro v11 — Render (Dashboard) — configuración recomendada

## 1) Start Command (MUY IMPORTANTE)
En **Settings → Start Command**, poné exactamente:

`bash bin/start.sh`

Esto evita problemas de expansión de `$PORT` y asegura que Gunicorn escuche en `0.0.0.0:${PORT}`.

## 2) Build Command
En **Settings → Build Command** (si lo usás):

`bash build.sh`

## 3) Health Check Path
En **Settings → Health Check Path**:

`/healthz/`

> En v11, `/healthz/` está exento de redirección HTTPS para que Render lo pueda chequear siempre.

## 4) Variables de entorno mínimas
En **Environment → Environment Variables**:

- `SECRET_KEY` (obligatoria)
- `DJANGO_SETTINGS_MODULE=invpanel.settings`
- `WEB_CONCURRENCY=1` (Starter está bien)

### Recomendado (producción)
- `DEBUG=0`
- `ALLOWED_HOSTS=invpanel-pro.onrender.com` (opcional, porque ya se auto-agrega con `RENDER_EXTERNAL_HOSTNAME`)

## 5) Base de datos (PostgreSQL pago)
- Create → **PostgreSQL**
- Enlazalo al servicio Web y asegurate de tener `DATABASE_URL` configurada automáticamente por Render.
- Luego hacé redeploy.

## 6) Si vuelve a aparecer “No open HTTP ports detected”
1. Verificá que el **Start Command** sea `bash bin/start.sh`.
2. Confirmá que el log muestre `--bind 0.0.0.0:<PORT>`.
3. Dejá el **Health Check Path** en `/healthz/`.

