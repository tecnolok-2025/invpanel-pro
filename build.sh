#!/usr/bin/env bash
set -o errexit

python -m pip install --upgrade pip
pip install -r requirements.txt

python manage.py migrate --noinput
python manage.py collectstatic --noinput

# Crea el usuario administrador inicial SOLO si aún no existe un superusuario.
# Variables esperadas (en Render → Environment):
#   - ADMIN_USERNAME (alias: ADMIN_USER)
#   - ADMIN_PASSWORD
#   - ADMIN_EMAIL (opcional)
# Para forzar reset de contraseña (si fuera necesario): ADMIN_FORCE_RESET=1
python manage.py bootstrap_admin
