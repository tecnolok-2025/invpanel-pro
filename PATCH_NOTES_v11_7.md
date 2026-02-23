# InvPanel PRO — Rev 7 (v11.7)

## Objetivo de esta revisión
Mejorar la **operación real** (usuario final) y reducir problemas frecuentes en Render:
- Manual mucho más **narrado** y “paso a paso” (qué tocar, qué esperar ver, y dónde mirar si no aparece nada).
- Logout corregido (por seguridad, Django 5 requiere POST): elimina el 405 al hacer click en “Salir”.
- PWA assets (sw.js / manifest) servidos como bytes para evitar warnings ruidosos en logs ASGI.

## Cambios incluidos
1) **Manual (HTML + PDF)**
- Manual ampliado y reestructurado: incluye guía de primera prueba, pantalla por pantalla, y procedimientos por botón.

2) **Logout**
- El menú “Salir” ahora hace un POST con CSRF.
- Nota: si alguien tipea /logout/ en el navegador (GET) puede ver 405. Es normal y es parte de la seguridad.

3) **Oportunidades: ayuda contextual**
- Se agregó “Ayuda rápida” dentro de la pantalla de Oportunidades, para que el usuario tenga guía sin depender del PDF.

4) **PWA logs**
- sw.js y manifest se devuelven con HttpResponse(bytes) (archivos chicos) en vez de FileResponse.

## Archivos tocados
- templates/base.html
- templates/core/opportunities.html
- templates/core/manual.html
- core/views.py
- core/pwa_views.py
- INSTRUCCIONES_RENDER_DASHBOARD.md

## Cómo aplicar
### Opción A (recomendada): aplicar patch en tu repo
1) Copiá `0002-rev7-manual-logout-pwa.patch` a la raíz del repo.
2) Ejecutá:
   - `git apply 0002-rev7-manual-logout-pwa.patch`
3) Commit + push.
4) En Render: **Clear build cache** + Deploy.

### Opción B: reemplazar por ZIP completo
- Subís el ZIP completo de Rev 7 a tu repo (sobreescribe archivos) y desplegás.
