PARCHE v11.6 — Fix DEMO + schema-safe ai_summary/ai_action (Render)

Qué arregla:
- Evita IntegrityError NOT NULL (ai_summary / ai_action) al crear oportunidades DEMO.
- Hace create() "defensivo" frente a desfasajes entre código y esquema (DB).

Archivos tocados:
- core/reco_engine.py  (exporta create_reco_safe, usa concrete_fields)
- core/views.py        (DEMO usa create_reco_safe + defaults)

Cómo aplicar (Git):
1) Copiá este ZIP a tu PC y descomprimilo.
2) En la carpeta del repo:
   git apply 0001-demo-schema-safe.patch
3) Commit + push
4) En Render: Clear build cache + Deploy

Si NO usás git apply:
- Abrí core/reco_engine.py y pegá la función create_reco_safe como en el patch.
- En views.py, en el bloque DEMO, agregá ai_action y ai_summary o llamá create_reco_safe.
