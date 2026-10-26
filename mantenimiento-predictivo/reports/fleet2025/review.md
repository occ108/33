# Revisión y evidencia

Preview informativo: **Ready with known limitations**. Ampliación diagnóstica
Europa/EE. UU. completa: **Not ready**; bloqueada por falta de datos/variantes,
referencias técnicas y licencias. No se ha publicado esta rama.

- 79 tests unittest/AppTest correctos (12,535 s en esta ejecución).
- 14 modelos/2 marcas con ventas 2025 verificadas; 0 variantes técnicas,
  0 umbrales y 0 asociaciones DTC-modelo documentadas en el catálogo nuevo.
- 3 categorías regulatorias DTC verificadas; no definiciones completas SAE.
- Chromium es/en/de, 1440/390 px: sin errores JS ni desbordes; sin cargador y
  atribución Francia correcta. No verificado Firefox/Safari ni WCAG completa.
- Microbenchmark sintético 100.000 registros: índice usado, p95 de consulta con
  coincidencia pendiente ~0,012 ms; RSS pico 22,125 MiB, DB ~87 MiB. No es una
  prueba de diagnóstico, ingestión completa, concurrencia, red o SLA en Render.
- `pip check` correcto; ninguna dependencia instalada nueva, jsonschema ya fijada
  pasa a declaración directa.
- Imagen de validación sobre dependencias existentes, 512 MiB/1 CPU: catálogo,
  base de solo lectura, tres idiomas y fallback correctos. Hashes de módulos y
  datos coinciden con archivos finales. No sustituye el build limpio del Dockerfile.
- Revisor independiente reprodujo y confirmó rechazo de columnas duplicadas,
  infinitos físicos, licencias incoherentes, mercado fuera de ámbito y DTC entre
  marcas. No encontró bloqueo restante para este preview informativo.
- UI no conecta el catálogo nuevo al comparador antiguo ni usa valores pendientes.
- Pendiente revisión nativa de `fleet_boundary` y `fleet_dtc` en inglés/alemán.

Genie no disponible. Inicialización ZzzOps no ejecutable: recursos de reglas
referenciados por su SKILL.md no disponibles; sin política aprobada ni loop ZzzOps.
Ver `docs/FLEET2025.md` para fuentes, comandos y límites de los complementos.
