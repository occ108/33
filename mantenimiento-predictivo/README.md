# Axion — revisión de señales industriales y de automoción

## Ampliación Europa/EE. UU. — revisión 26.10.2026

Nueva rama `data-eu-us-2025`: catálogo con **14 modelos comerciales** que superan
50 ventas verificadas en 2025 (2 marcas), esquema JSON/SQL, importación SQLite
atómica y cobertura informativa es/en/de. **Cero variantes técnicas, umbrales OEM
o enlaces DTC-modelo verificados en este catálogo nuevo**: no se aplican a las
mediciones del usuario ni sustituyen las referencias de neumáticos anteriores.
No hay cobertura completa del parque ni scheduler o proveedor de datos conectado.

Consulte [arquitectura, fuentes, QA, limitaciones y comandos](docs/FLEET2025.md).
La base se reproduce con `python scripts/build_fleet_catalog.py`; la puerta
`python scripts/check_fleet_release.py --profile diagnostic` devuelve 2 de forma
intencionada hasta completar las fuentes y cobertura necesarias. Esta ampliación
no se ha publicado ni enviado a `deploy/mantenimiento-predictivo`.

Base publicada: `a00bfec`, con formulario y referencias de neumáticos. La ampliación
de catálogo de esta rama es una entrega nueva para revisión.

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

## Uso: mediciones desde la página

1. Seleccione idioma, tipo de vehículo y componente; marque los parámetros que desea comprobar.
2. Escriba marca, modelo, año, versión/motor/generación y mercado. Introduzca las
   mediciones en las unidades indicadas. Los campos vacíos no equivalen a cero.
3. Para la comparación de neumáticos, seleccione condiciones de uso y compruebe el
   enlace al manual. Confirme su aplicabilidad a su generación y versión.
4. Pulse **Comprobar mediciones**. Cada resultado incluye recomendación, condiciones
   y fuente, o **Sin referencia verificada aplicable**. No se extrapola entre modelos.
5. Opcionalmente pruebe la flota sintética para explorar las pestañas de análisis
   histórico. Los umbrales configurados en esa demo no son referencias OEM verificadas.

Ya no hay cargador de archivos ni descarga de plantilla en la interfaz. El lector
CSV se conserva internamente para ejemplos y regresiones. Las mediciones y los
resultados se mantienen solo en la sesión y sobreviven al cambio de idioma.
Una medición aislada no permite predecir fallo, fecha ni kilometraje de mantenimiento.
Los resultados corresponden a la última comprobación enviada, no a campos editados
que aún no se han enviado. No se certifica el estado ni la seguridad del vehículo.

### Cobertura real de fabricantes

`catalog/manufacturer_references.json` contiene **8 recomendaciones contextuales,
4 modelos, 1 marca y 1 parámetro**: profundidad del dibujo de neumáticos. Proceden
exclusivamente de los manuales oficiales de EE. UU. de Tesla Model 3 (2024–2026),
Model Y (2025–2026), Model S y Model X (2021–2026), verificados el 25.10.2026.
El índice identifica las generaciones 2024+, 2025+ y 2021+, respectivamente.
El usuario debe comprobar que el manual corresponde a su vehículo concreto.
La app no verifica automáticamente VIN ni equipamiento; la versión se registra
como información aportada por el usuario y requiere su confirmación del manual.

Son recomendaciones de uso, **no valores nominales de fábrica ni límites legales**:
el manual desaconseja el uso con dibujo menor de 3 mm en mojado y menor de 4 mm en
nieve/aguanieve. Se conservan los valores publicados en mm, sin convertir pulgadas.
La comparación usa `<`, como el texto original; igualar el valor no certifica aptitud.
La presión recomendada depende de la etiqueta del vehículo: no se ha inventado una
presión fija a partir del modelo.

Se puede introducir cualquier marca/modelo, pero **no hay una base de datos de todos
los coches del mundo**. Para ampliar la cobertura hacen falta documentación técnica
por variante, condiciones de medición y derechos de reutilización o un proveedor
con licencia. No se ha contratado ni conectado ningún proveedor comercial. No se
confunden rangos físicos genéricos con referencias del fabricante.

Cada registro incluye ámbito, parámetro, unidad, operador, valor, condiciones,
URL oficial, sección, cita breve, fecha y SHA-256 del HTML decodificado y recodificado
como UTF-8. No se redistribuyen manuales completos ni se consulta la red con datos
introducidos por usuarios. Unidades incompatibles o referencias ambiguas no producen
comparación. Añadir una referencia del mismo tipo solo requiere editar el JSON;
parámetros nuevos requieren además su contrato y método de comparación.

Fuentes: [Model 3](https://www.tesla.com/ownersmanual/model3/en_us/GUID-94F63B13-EA2C-45D9-83AB-5DCA6295D587.html),
[Model Y](https://www.tesla.com/ownersmanual/modely/en_us/GUID-94F63B13-EA2C-45D9-83AB-5DCA6295D587.html),
[Model S](https://www.tesla.com/ownersmanual/models/en_us/GUID-94F63B13-EA2C-45D9-83AB-5DCA6295D587.html),
[Model X](https://www.tesla.com/ownersmanual/modelx/en_us/GUID-94F63B13-EA2C-45D9-83AB-5DCA6295D587.html).

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

**Textos nativos que pueden permanecer en inglés:** selector múltiple de parámetros
(Choose options / Select all), controles de tabla, opciones de menú de gráficos,
accesibilidad nativa Skip to main content y
Stop durante ejecución pueden permanecer en inglés. Los números de los campos de
entrada nativos usan punto decimal. Se minimizan con toolbarMode=minimal ; no se emplea CSS dependiente de clases internas ni hacks del DOM.
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
or use `?lang=en`. Enter vehicle details and measurements, confirm the applicable
manual, then check readings. OEM reference coverage is limited to tyre tread
recommendations for four Tesla models in the US; unsupported readings show no reference.
The optional fleet demo is synthetic. Confirm thresholds in the manufacturer's manual. Indicative estimates do not replace professional inspection. Native Streamlit
controls may remain English; vehicle scenarios are synthetic.

## Kurzanleitung auf Deutsch

Installieren Sie die Abhängigkeiten mit Python 3.12 und starten Sie
`python -m streamlit run app.py`. Wählen Sie Deutsch oder verwenden Sie `?lang=de`.
Geben Sie Fahrzeugdaten und Messwerte ein und prüfen Sie das passende Handbuch.
Herstellerreferenzen umfassen bisher nur Reifenprofiltiefen für vier Tesla-Modelle
in den USA. Ohne passende Referenz erfolgt kein Herstellervergleich.
Die optionale Beispielflotte ist synthetisch. Prüfen Sie Grenzwerte im Herstellerhandbuch.
Orientierende Schätzungen ersetzen keine fachgerechte Prüfung. Einige native
Streamlit-Bedienelemente bleiben englisch. Die Fahrzeugszenarien sind synthetisch.
