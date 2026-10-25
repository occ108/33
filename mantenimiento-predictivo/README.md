# Axion — revisión de señales industriales y de automoción

Rama de revisión: **automocion-ui**. Esta entrega no se ha publicado ni enviado a
`deploy/mantenimiento-predictivo`. La web pública conserva la versión anterior.

## Ejecutar (Python 3.12)

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
.venv/bin/python -m streamlit run app.py
```

Windows: sustituya `.venv/bin/python` por `.venv\Scripts\python.exe`.
El entorno preparado usa `/workspace/.venvs/mantenimiento-predictivo/bin/python`.
No hay dependencias nuevas. Las opciones de `.streamlit/config.toml` se comprobaron
con `streamlit.config.get_config_options()` de la versión 1.66.1 instalada.

## Uso

1. Seleccione idioma, tipo de vehículo y componente. La plantilla conserva los
   identificadores de columna; las unidades aparecen junto a la selección.
2. Suba un CSV o pulse **Probar flota de ejemplo**. La flota es sintética y simplificada.
3. Elija equipo y parámetro. Confirme los límites con el fabricante y actívelos en
   la barra lateral. Para probar exclusivamente el escenario inventado de frenos,
   CAR-01/brake_pad_mm admite un umbral de demostración de 5 mm por debajo: NO es
   una recomendación para un vehículo real. Los límites de la interfaz están vacíos.
4. Consulte Datos, Anomalías y Mantenimiento. La estimación comienza en la última
   lectura, no en el día actual. El plan permite Hoy o simulación histórica; los
   datos atrasados no reciben una fecha de intervención actual.
5. Recursos, formato y ejemplo industrial anterior están plegados al final.

La banda es orientativa, no un intervalo de fallo calibrado. Una señal no diagnostica
averías ni certifica el estado de un vehículo. Frenos, neumáticos, suspensión y
 dirección muestran el aviso de inspección cualificada. No hay persistencia de CSV,
logs de datos subidos ni caché global de usuarios; los resultados solo se reutilizan
en `st.session_state`. Cambiar idioma conserva el contenido y los límites de la sesión.

## Catálogo y contrato

`catalog/automocion.json` contiene seis tipos de vehículo y trece componentes con
nombre/descripcion es/en/de, aplicabilidad, parámetros, métrica e intervalo de
referencia vacío. Añadir un componente con parámetros existentes solo requiere
editar ese archivo y reiniciar la app. No hay intervalos OEM universales inventados.

Se conservan timestamp, asset_id, los tres sensores industriales y operating_hours.
Se añaden vehicle_type, component y odometer_km opcionales. Los metadatos, si se
incluyen, deben ser constantes por asset_id. vehicle_type usa car, van, truck, bus,
motorcycle u other; component usa los identificadores del catálogo.

Parámetros nuevos: engine_rpm, engine_load_pct, coolant_temp_c, oil_temp_c,
oil_pressure_bar, boost_pressure_bar, egt_c, dpf_diff_pressure_kpa, battery_voltage_v,
gearbox_oil_temp_c, brake_temp_c, brake_pad_mm, tire_pressure_bar, tire_tread_mm,
fuel_consumption_l_100km; además battery_soh_pct y chain_elongation_pct permiten
representar salud de batería y desgaste de cadena explícitos. No se deducen de
voltaje o de otro sensor. boost_pressure_bar se declara **absoluta**; no se convierte
presión relativa automáticamente. No se convierte aceleración en velocidad RMS.

Los rangos físicos excluyen valores negativos donde carecen de sentido, temperaturas
bajo cero absoluto y porcentajes fuera de 0–100. Los rangos de plausibilidad son
cribados amplios, NO límites de mantenimiento ni especificaciones de fabricantes.
Los extremos plausibles avisan; las columnas desconocidas se descartan con aviso.
Los CSV existentes de ejemplo se mantienen aceptados. Una presión negativa antes
no validada se rechaza ahora: si el origen registra vacío o presión relativa,
confirme la semántica y no cambie unidades ni signos arbitrariamente.

Los errores usan `DataError.code` y parámetros; la UI traduce los mensajes.
La serie y la referencia se separan por vehículo. Para umbrales inferiores se
invierte la señal únicamente dentro del motor, se proyecta y se restituyen pendientes
y nivel; no se cambia el algoritmo de los casos superiores. El contador km alimenta
la proyección de uso sin convertir km a horas. Un contador ausente, constante o
reiniciado no genera kilometraje. Meses y ciclos del catálogo requieren seguimiento
manual: no se inventan contadores para ellos.

## Idiomas y límites de widgets

`locales/{es,en,de}.toml`, `t()`, códigos estables de widgets y parámetros con nombre.
URL ?lang= → Accept-Language (st.context.headers) → español. No se escriben cookies ni
preferencias en almacenamiento del navegador por la aplicación. Tablas, mensajes,
fechas y tooltips se formatean por idioma; CSV de intercambio mantiene identificadores
y tipos numéricos estándar. Los títulos originales de las fuentes no se traducen.

**Pendiente de revisión nativa:** claves critical, counter y band en inglés/alemán
(comentarios `# revisar`), terminología de batería, presión de admisión y SCR del
catálogo. `locales/glosario.md` lista los términos. No se certifica revisión nativa.

**Textos de Streamlit que permanecen:** Upload, indicador MB per file/CSV, controles
de tabla, opciones de menú de gráficos, accesibilidad nativa Skip to main content y
Stop durante ejecución pueden permanecer en inglés. Los números de los campos de
entrada nativos usan punto decimal. Se minimizan con toolbarMode=minimal y evitando
multiselect; no se emplea CSS dependiente de clases internas ni hacks del DOM.
Esta es una limitación conocida respecto a una interfaz absolutamente monolingüe.

## Pruebas, evaluación y capturas

```sh
python -m unittest discover -s tests -v
python scripts/generate_vehicles.py
python scripts/evaluate_vehicles.py
python scripts/benchmark_automotive.py --output reports/automocion/benchmark_auto.json
```

Las pruebas anteriores de interfaz se migraron a botones y claves estables; se
conservan sus comprobaciones de carga, selección, muestreo de gráfica y planificación.
Se añaden catálogo, paridad de claves/marcadores, cambio de idioma, conservación de
contenido y límites, alerta inferior, constantes, CSV industrial y plausibilidad.
Los resultados ejecutados se guardan en `reports/automocion/`.

Simulación semilla 84: cuatro vehículos, 90 días horarios, cinco escenarios de
desgaste/degradación más picos conocidos. Referencia inicial 30 días y prueba temporal
60 días; la línea base sigue siendo causal. Evaluación de picos por vehículo/sensor:
**120 TP, 4 FP, 0 FN; precisión 96,77 %, recall 100 %; 60/60 eventos**, retraso medio
**0 h** (primera lectura del evento, no anticipación de averías). Las cinco tendencias
producen proyección en km con banda. En el escenario de frenos el contador previsto
es aproximadamente **77.160 km**, banda **76.087–78.352 km**. Son contadores acumulados,
no km restantes. Los umbrales del evaluador son fixtures inventados, no valores OEM.

100.000 filas, 5 equipos y 3 parámetros de automoción: **4,98 s** de flujo completo,
**281,53 MiB RSS** en un proceso Linux, incluidas lectura, análisis, proyecciones,
plan y exportaciones. No es una prueba de concurrencia ni un SLA de Render.

Antes: `before/1440.png`, `before/390.png`; solo español, ya que la app anterior no
tenía inglés/alemán. Después: seis capturas de inicio y seis de resultados en
`after/`, tres idiomas × 1440/390 px. No hubo desborde horizontal ni errores JS en
esas pruebas Chromium. Se verificaron cabecera Accept-Language alemana y conservación
de un CSV realmente subido al cambiar de español a inglés. No se han verificado
Safari, Firefox, lectores de pantalla ni conformidad WCAG completa.

## Recursos vehiculares

Se consultaron UCI APS Failure at Scania Trucks y HCRL Car-Hacking. No se añadieron
como fuentes vehiculares listas para importar porque no se confirmó conjuntamente
licencia, unidades y cronología. `resources_review.json` registra respuestas y límites.
Las fuentes industriales anteriores permanecen como referencias, no como evidencia
para turismos o motocicletas. No se inventan recursos ni se incorpora acceso privado.

## Docker y revisión

```sh
docker build -t axion-review .
docker run --rm -p 8501:8501 --memory=512m axion-review
```

Docker incorpora módulos, catálogo, idiomas, activos y config del tema. La construcción
local admite `.wheels/` obtenidas por HTTPS verificado: `pip download --only-binary=:all:
-r requirements.txt -d .wheels`, seguido de `docker build --network=none ...`. Las wheels
no se incluyen en Git ni ZIP ni permanecen como archivos de distribución en la imagen.
La app es una candidata de revisión, no una publicación aprobada. El asistente de
mapeo opcional no se ha implementado. No se ha realizado validación con una flota real.

## English quick start

Install Python 3.12 dependencies, run `python -m streamlit run app.py`, select English
or use `?lang=en`, then try the example fleet. Confirm thresholds in the manufacturer's
manual. Indicative estimates do not replace professional inspection. Native Streamlit
controls may remain English; vehicle scenarios are synthetic.

## Kurzanleitung auf Deutsch

Installieren Sie die Abhängigkeiten mit Python 3.12 und starten Sie
`python -m streamlit run app.py`. Wählen Sie Deutsch oder verwenden Sie `?lang=de`.
Testen Sie die Beispielflotte. Prüfen Sie Grenzwerte im Herstellerhandbuch.
Orientierende Schätzungen ersetzen keine fachgerechte Prüfung. Einige native
Streamlit-Bedienelemente bleiben englisch. Die Fahrzeugszenarien sind synthetisch.
