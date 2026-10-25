# Entrada manual y referencias OEM — revisión

Estado: cambios locales en `automocion-ui`, sin push a la rama de despliegue.

## Cambios

- Retirados cargador de archivos y plantilla de la interfaz; lector CSV interno conservado.
- Formulario de marca, modelo, año, generación/motor/versión, mercado, condiciones
  de uso y selección de parámetros con unidades. Campos vacíos no equivalen a cero.
- Resultados puntuales por parámetro con recomendación y enlace oficial, o ausencia
  explícita de referencia aplicable. No se obtiene un pronóstico a partir de un dato.
- Referencias en JSON, sin dependencias nuevas ni persistencia de datos de usuarios.
- Coincidencia estricta por marca, modelo, año, mercado, tipo de vehículo y condiciones.
  El usuario debe confirmar que el manual corresponde a su generación/versión;
  no se decodifica VIN ni se comprueba automáticamente equipamiento.
- Español, inglés y alemán; datos y resultados conservados al cambiar de idioma.

## Cobertura verificada y límites

8 recomendaciones contextuales de un único parámetro, 4 modelos Tesla, EE. UU.
Manuales oficiales comprobados el 25.10.2026: Model 3 2024+, Model Y 2025+,
Model S y X 2021+. Comparación limitada a años hasta 2026, nunca a futuros modelos.
Solo profundidad de dibujo: `< 3 mm` en mojado, `< 4 mm` en nieve/aguanieve.
No son valores nominales de fábrica, ni límites legales ni una certificación.
No hay cobertura de todas las marcas/modelos del mundo, ni proveedor de pago
conectado. Los parámetros sin referencia no reciben valoración de fábrica.

Los archivos de referencias conservan citas breves y URLs; no manuales completos.
No se han obtenido licencias comerciales de bases técnicas. Expandir cobertura
requiere fuentes y permisos de reutilización adecuados, validación por versión y
condiciones documentadas. No se han inventado parámetros de motor o presión de neumáticos.

## Validación

- 64 pruebas unittest/AppTest, incluidas regresiones históricas: correctas.
- Casos nuevos: alcance de referencia, condiciones, fronteras exactas, unidades,
  fuentes, valores imposibles, ausencia de referencia, formulario sin cargador,
  campos requeridos y cambio de idioma conservando valores/resultados.
- `pip check`: sin incompatibilidades.
- `docker build -t mantenimiento-predictivo:manual-fabricantes .`: correcto.
- 7 pruebas del comparador y formulario dentro de la imagen final con 512 MiB/1 CPU:
  correctas, incluidos tres idiomas, valores conservados y ausencia de cargador.
- Las cifras de precisión y rendimiento de la entrega anterior corresponden al
  análisis histórico sintético; no se atribuyen a este comparador puntual.

## Pendiente de revisión humana

Traducciones `manual_review`, `manual_not_below`, `manual_confirm` en inglés y alemán
marcadas con `# revisar`; no revisadas por hablante nativo. Textos nativos del selector
múltiple y controles de Streamlit pueden aparecer en inglés (README).
No se ha certificado precisión de instrumentos ni aptitud para circulación.

## Navegador

Chromium local, formulario real con Tesla Model 3 2024, EE. UU., mojado, dibujo
2,5 mm: recomendación de revisión mostrada. Cambio es → en → de conservando
el componente y la lectura. 1440 px y 390 px: sin desborde horizontal ni errores
JavaScript, cero cargadores de archivos. Capturas del inicio y resultados en los
seis casos; `browser.json` conserva resultados. Se corrigió la restauración de
selectores traducidos al cambiar de idioma. `browser_check.cjs` reproduce este
recorrido en este entorno con la app de prueba en puerto 8503; Playwright y
Chromium son herramientas de QA existentes, no nuevas dependencias del producto.
No se ha probado Safari/Firefox ni realizado una auditoría completa de accesibilidad.
