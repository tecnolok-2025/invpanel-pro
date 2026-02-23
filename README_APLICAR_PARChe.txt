PARCHE v11.7 — Manual narrado + Logout seguro (POST) + PWA sin warnings (Render)

Qué agrega / arregla:
- Manual mucho más narrado y operativo (paso a paso por pantalla y botones).
- “Salir / Logout” pasa a ser POST (seguridad). Evita el 405 cuando el usuario hace click desde el menú.
- PWA assets (sw.js / manifest) se sirven como bytes para evitar warnings ruidosos en logs ASGI.

Archivos tocados:
- templates/base.html
- templates/core/opportunities.html
- templates/core/manual.html
- core/views.py
- core/pwa_views.py

Cómo aplicar (Git):
1) Copiá este ZIP a tu PC y descomprimilo.
2) En la carpeta del repo:
   git apply 0002-rev7-manual-logout-pwa.patch
3) Commit + push
4) En Render: Clear build cache + Deploy

Si NO usás git apply:
- Aplicá los cambios manualmente en los 5 archivos listados arriba.
