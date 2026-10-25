# Revisión de Axion / automocion-ui

## Estado y alcance

Candidata para revisión con limitaciones conocidas. No se ha publicado ni se ha hecho
push a deploy/mantenimiento-predictivo. Referencia remota conservada:
`dc8fb5751418da698158082bdfea3d39e35861a2`.

## Problemas anteriores

1. Observado: recursos antes de la carga. Corrección: la biblioteca estaba plegada
   inicialmente, por lo que no ocupaba toda la pantalla mientras seguía cerrada.
2. Observado: Upload, MB per file y herramientas nativas en inglés. Se minimiza la
   barra de herramientas; el límite anunciado ahora es 10 MB. Persisten controles
   nativos documentados. No se afirma traducción completa de la interfaz de Streamlit.
3. Confirmado en código: uso de formato numérico inglés en recursos. Nuevo formateador
   por idioma, tabla de presentación y tooltips con números y fechas explícitos.
4. Observado: subtítulo Fase 2 y notas técnicas antes de la acción. Se retiran del
   flujo; referencias y detalles quedan plegados al final.
5. Observado: dos casillas de demo. Sustituidas por botón principal de flota y ejemplo
   industrial secundario dentro de ayuda, con avisos sintéticos claros.
6. Observado: sin identidad propia y título grande. Nueva identidad Axion, SVG, favicon,
   tema claro y tarjetas. Capturas de inicio y resultados muestran los cambios.

## Evidencia

- before/: español a1440 y390. Antes no existían inglés/alemán: no se fabrican capturas.
- after/: inicio y datos de ejemplo, tresidiomas×dosanchos; browser.json registra
  ausencia de desbordamiento horizontal y errores JS en esas capturas Chromium.
- upload_language.json: archivo subido preservado y detección del idioma de navegador.
- tests.txt: suite real; tests existentes de UI se migraron a botones y claves estables,
  conservando carga/selección, gráficos, datos cortos y guardia de antigüedad del plan.
- evaluation.json: clasificación de picos sintéticos separada de la proyección de cinco
  tendencias. Los límites del evaluador no se muestran como valores OEM en la interfaz.
- benchmark_auto.json:100000filas,5equipos,3parámetros. No es prueba de concurrencia.

## Pendientes y límites

- Revisión nativa de critical/counter/band en inglés/alemán (comentarios # revisar),
  además de términos de batería, SCR y admisión del catálogo. Véase glosario.
- UI nativa: Upload/MB per file, Stop transitorio, tablas/gráficos, salto de navegación
  e inputs numéricos pueden seguir usando idioma/formato inglés de Streamlit.
- No se certifica WCAG AA completo ni se probaron Safari/Firefox/lectores de pantalla.
  Se aplicó la paleta, texto oscuro y señales con icono+texto, sin CSS de clases internas.
- Meses/ciclos: seguimiento manual, sin conversión automática a km/horas.
- Mapeo de columnas opcional no implementado.
- No se añadieron recursos vehiculares sin validación conjunta. Se revisaron respuestas
  oficiales de UCI APS/Scania y HCRL; registro en resources_review.json.
- No hay modelos de avería real, intervalos OEM precargados, recomendaciones legales
  ni certificación del estado de vehículos. Se necesita validación técnica con datos reales.
