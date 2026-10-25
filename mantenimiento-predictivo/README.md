# Mantenimiento Predictivo Ligero · Fase 2

Aplicación Streamlit para revisar históricos de sensores, señalar **indicios de anomalía** y estimar de forma orientativa cuándo una señal creciente alcanzaría un umbral superior elegido por el usuario.

**Una variación del sensor no demuestra una avería. Sin etiquetas reales de fallos no se puede afirmar «predicción de fallos».** Las estimaciones no son órdenes de mantenimiento ni sustituyen la revisión técnica.

La **Fase 2 está desplegada** en <https://mantenimiento-predictivo-demo.onrender.com>.
Se verificaron el despliegue `live`, la salud HTTPS y una sesión pública con el histórico
grande, las cinco máquinas y la proyección de M-005 con banda y horas de uso.
`reports/release.json` identifica el commit y las comprobaciones. El plan gratuito puede
suspender la instancia cuando no se utiliza.

## Instalar y ejecutar

Requiere **Python 3.12**. Ejecuta desde `mantenimiento-predictivo/`. `requirements.in` fija las dependencias directas; `requirements.txt` fija también las transitivas probadas.

Linux/macOS:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip check
python -m streamlit run app.py --server.headless=true --server.maxUploadSize=10 --browser.gatherUsageStats=false
```

Windows PowerShell, sin necesidad de activar el entorno:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m streamlit run app.py --server.headless=true --server.maxUploadSize=10 --browser.gatherUsageStats=false
```

Abre la dirección que muestre Streamlit. En el entorno cloud preparado, el intérprete equivalente es `/workspace/.venvs/mantenimiento-predictivo/bin/python`.

## Probar la interfaz

1. Activa **«Probar con datos sintéticos»**: conserva el ejemplo original de 9 lecturas y 2 máquinas. La app explica que faltan datos para analizar o estimar; no inventa resultados.
2. Desactiva el ejemplo pequeño y activa **«Probar histórico de 90 días»** para explorar 10.800 lecturas de 5 máquinas. Puedes descargar ambos ejemplos o subir un CSV compatible.
3. En **Datos**, revisa las primeras lecturas, la serie temporal y los avisos de calidad.
4. En **Anomalías**, consulta el semáforo, los puntos marcados y el resumen por máquina y sensor. Ajusta la referencia, mínimo de lecturas y sensibilidad en la barra lateral.
5. En **Mantenimiento**, elige máquina y sensor, activa su umbral superior e introduce el límite acordado con mantenimiento. Para datos propios, la proyección permanece desactivada hasta configurar el umbral.

Los ajustes se conservan por máquina, sensor y archivo únicamente en la sesión. Para M-005 del ejemplo grande se proponen **82 °C** y **3,8 mm/s RMS**: son valores inventados y orientativos, **no normas ni dictámenes**.

El semáforo resume las últimas lecturas de la ventana seleccionada:

- **Verde:** sin indicios detectados en esa ventana; no garantiza ausencia de problemas.
- **Ámbar:** indicios recientes, calidad irregular o datos insuficientes; la frase adjunta explica la razón.
- **Rojo:** la última lectura alcanza un umbral superior configurado; revisar la señal sin afirmar una avería.

Las descargas de resultados y estimaciones son CSV. Se protegen celdas y cabeceras que puedan interpretarse como fórmulas (`=`, `+`, `-`, `@`); los números negativos se exportan como texto seguro. El gráfico puede reducir puntos para ser ágil: se indica esa reducción y la descarga conserva todas las lecturas.

## Contrato CSV conservado y privacidad

`load_csv()` mantiene el contrato y las pruebas de la Fase 1:

- UTF-8, separador coma, punto decimal y cabecera única.
- `timestamp`: ISO 8601; preferible zona explícita. Sin zona se interpreta como UTC.
- `asset_id`: identificador de máquina no vacío.
- Al menos un sensor: `temperature_c` (°C), `vibration_mm_s` (mm/s RMS), `pressure_bar` (bar).
- `operating_hours`: opcional, numérico y no negativo.
- Una lectura por máquina e instante; sin valores ausentes en los sensores presentes.
- Máximo **10 MiB** y **100.000 filas**. No se interpolan ni rellenan datos ausentes.

Los CSV subidos no se escriben en disco ni se registran en logs. Se procesan en memoria, sin `st.cache_data`, `st.cache_resource` ni caché global entre usuarios. El generador y los scripts de evaluación escriben solo datos sintéticos e informes al ejecutarlos explícitamente.

## Métodos y supuestos

### Indicios por sensor

`analysis.py` ofrece funciones puras, tipadas y sin Streamlit. Cada máquina y sensor se compara con la mediana y desviación absoluta mediana (MAD) de sus **lecturas anteriores**, excluyendo la actual.

Por defecto, la ventana contiene hasta **48 lecturas anteriores**, exige al menos **24** y marca desviaciones robustas superiores a **4,5**. La primera observación evaluable es la **25** de cada tramo. El resultado distingue «sin indicios» de «sin datos suficientes». Un suelo numérico evita divisiones por cero ante referencias constantes.

Una ventana de lecturas solo equivale a horas con muestreo horario regular. Se avisa si los intervalos difieren más del 10 % del intervalo mediano o hay huecos mayores de tres veces la referencia temporal. Ante separaciones largas se reinician la referencia móvil y el tramo de tendencia; no se crean lecturas ficticias.

### Análisis conjunto complementario

IsolationForest exige al menos **2 sensores** y, con los valores actuales, **193 lecturas por máquina**: 168 de referencia, 24 posteriores sin puntuar y la primera lectura evaluable. Utiliza **64 árboles**, `n_jobs=1`, semilla **42** y `contamination=0.01`. Ese parámetro configura el detector; no es una probabilidad de fallo.

El modelo y su normalización aprenden solo del prefijo inicial; las observaciones posteriores no los reentrenan. Su referencia se mantiene fija incluso si cambia el régimen operativo. Señala cambios conjuntos sin atribuir por sí solo qué sensor los causa. La baja precisión observada más abajo justifica mantenerlo como complemento revisado por una persona.

### Llegada orientativa al umbral

Theil–Sen usa las últimas **168 lecturas**, con mínimo **48** y como máximo **128 observaciones existentes repartidas en el tiempo** para acotar su coste cuadrático. La interfaz permite ajustar la ventana y un horizonte de hasta **90 días**; no fuerza una fecha fuera del horizonte.

Solo se proyectan **umbrales superiores** y tendencias claramente crecientes. Si el límite inferior de la pendiente no es positivo se informa **«Sin degradación apreciable»**. Se distingue también umbral ya alcanzado, falta de configuración, datos insuficientes y límites numéricos.

La confianza **0,95 corresponde a la pendiente**: no es una probabilidad de fallo ni un intervalo del 95 % calibrado para la fecha de llegada. La banda de fechas combina límites de pendiente y dispersión residual de forma orientativa; no se ha verificado su cobertura estadística con datos reales.

La proyección supone que continúan tendencia, carga, régimen y calibración recientes. Parte de la **última lectura del histórico**, no del reloj actual. Si existe `operating_hours`, se ajusta además sobre ese eje, sin convertir horas de uso a calendario suponiendo funcionamiento continuo. Un reinicio o descenso del contador en el histórico desactiva la proyección en horas de uso. Contadores sin variación suficiente, huecos y cambios de régimen limitan las conclusiones.

## Datos sintéticos y evaluación reproducible

Con el entorno activado:

```sh
python scripts/generate_synthetic.py
python scripts/evaluate_synthetic.py
python scripts/evaluate_forecast.py
python scripts/benchmark_analysis.py --rows 100000
```

En Windows puedes sustituir `python` por `.\.venv\Scripts\python.exe`. El benchmark de RSS usa `resource` y se ejecutó en **Linux**; para reproducir esa medición desde Windows utiliza WSL o un contenedor Linux.

El generador fija semilla 42: **5 máquinas × 90 días horarios**, ruido, ciclos suaves, **45 eventos de picos de 3 horas** y degradación gradual de temperatura/vibración de M-005 durante los últimos 30 días. `examples/synthetic/` contiene:

- `sensores_90d.csv`: 10.800 lecturas compatibles con el cargador.
- `etiquetas_90d.csv`: verdad por máquina/instante/sensor; `is_anomaly` identifica picos, mientras `is_degradation` identifica deriva gradual por separado.
- `metadata.json`: semilla, eventos, partición temporal y supuestos.

Las etiquetas nunca se pasan al detector. Se separan **30 días iniciales** y **60 días de prueba**. IsolationForest aprende solo de las primeras 168 lecturas; la referencia móvil se actualiza causalmente con el pasado disponible, incluido el periodo de prueba. Es evaluación online, sin anticipar sus observaciones futuras.

### Resultados ejecutados del periodo de prueba

Valores de `reports/evaluation.json`:

| Método | Verdaderos positivos | Falsos positivos | Falsos negativos | Precisión | Recall |
|---|---:|---:|---:|---:|---:|
| Mediana/MAD móvil | 195 | 5 | 0 | 97,50 % | 100,00 % |
| IsolationForest | 85 | 740 | 20 | 10,30 % | 80,95 % |

**Las unidades son distintas:** el método móvil se cuenta por máquina/instante/sensor (21.600 observaciones de prueba); IsolationForest por máquina/instante con algún sensor anómalo (7.200). No son cifras directamente intercambiables ni probabilidades de fallo.

De **35 eventos de prueba**, el método móvil detectó **35/35**, con demora media y máxima de **0 horas** entre detectados. IsolationForest detectó **30/35**, dejó **5 sin detectar** y tuvo demora media de **0,1 horas** y máxima de **1 hora** entre detectados. La demora se busca dentro del evento de tres horas y los no detectados se cuentan aparte. Con muestreo horario, «0 horas» significa señalar la primera lectura del evento, no anticipar un fallo.

Son cifras de **una sola simulación y semilla**. La deriva gradual, etiquetada aparte, puede contarse como falso positivo en esta evaluación de picos, especialmente con la referencia fija de IsolationForest. Su baja precisión no se oculta: hay que validar ese complemento antes de usar sus alertas en un taller. No existen etiquetas ni evaluación de fallos reales.

### Ejemplo de proyección ejecutado

`reports/forecast.json` registra M-005, temperatura y umbral orientativo de 82 °C:

- **343,64 horas de calendario** desde la última lectura; banda **292,92–399,41 horas**.
- Fecha nominal: **15 de abril de 2026, 06:38 UTC**; banda del 13 de abril, 03:54, al 17 de abril, 14:24 UTC.
- **257,73 horas de uso restantes**; contador nominal **3.176,98 horas acumuladas**, banda **3.138,94–3.218,80 horas acumuladas**.

El histórico termina el **31 de marzo de 2026 a las 23:00 UTC**. Son fechas posteriores al histórico sintético, aunque hayan pasado respecto al día en que se abra la app. Comparar la pendiente estimada con la del generador no acredita la cobertura de la banda ni valida predicciones de fallos.

## Pruebas y rendimiento medidos

Con el entorno activado:

```sh
python -m unittest discover -s tests -v
python -m pip check
```

Windows sin activación:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
```

La validación pasó **39 pruebas en 7,377 segundos**, incluidas las originales y las nuevas de anomalías inyectadas, causalidad, determinismo, series constantes/cortas, un sensor, una máquina, muestreo irregular, huecos, extremos numéricos, tendencias, contador, exportación segura y flujo completo con `AppTest`. `pip check` no encontró incompatibilidades.

`reports/benchmark.json` registra una ejecución en un proceso nuevo, Python 3.12.14, Linux, **100.000 filas, 5 máquinas y 3 sensores**, con CSV de 5.956.344 bytes:

| Etapa | Tiempo medido |
|---|---:|
| Lectura y validación CSV | 0,279 s |
| Detección de anomalías | 1,867 s |
| 15 estimaciones hasta umbral | 0,507 s |
| Exportación CSV segura | 1,921 s |
| Flujo completo | **4,574 s** |

Pico: **298,668 MiB RSS**, inferior al objetivo de 400 MiB. Incluye imports de Streamlit/dependencias, generación del CSV, carga, análisis, estimaciones y exportación. Es **un proceso y una ejecución**: no incluye un navegador ni demuestra capacidad para usuarios concurrentes. Hardware, número de máquinas, ventanas y contenido pueden cambiar estas cifras; no son un SLA para Render gratuito.

## Docker y Render

El Dockerfile copia `app.py`, `analysis.py`, `exports.py` y los ejemplos; `.dockerignore` permite los módulos nuevos. La app se ejecuta sin privilegios de root y respeta `PORT` de Render. Desde esta carpeta:

```sh
docker build -t mantenimiento-predictivo-fase2 .
docker run --rm -p 8501:8501 mantenimiento-predictivo-fase2
```

El mismo Dockerfile admite una construcción sin red colocando previamente en `.wheels/` las ruedas fijadas de `requirements.txt`, descargadas con HTTPS verificado. Se montan solo durante la instalación y no se copian como archivos de distribución a la imagen final. No se desactiva TLS ni se alteran versiones para resolver conectividad. `DEPLOY.md` y `../render.yaml` describen el servicio.

La construcción real pasó. La imagen mide **723,779 MiB** (tamaño de disco, distinto de la RAM).
En Docker con **una CPU y límite de 512 MiB**, el benchmark de 100.000 filas registró
**4,664 s** para el flujo completo y **339,750 MiB RSS** de pico. La detección tardó
**1,964 s**. Son mediciones de un proceso, no de concurrencia. Además pasaron salud HTTP,
ejecución sin privilegios y flujo `AppTest` del histórico grande con proyección de M-005.
Los resultados están en `reports/docker.json` y `reports/benchmark_docker.json`.

## Archivos de esta fase

- `analysis.py`: detección, calidad temporal y proyección robusta, sin Streamlit.
- `exports.py`: CSV protegido frente a fórmulas.
- `app.py`: cargador conservado e interfaz en español con tres pestañas.
- `scripts/`: generador, evaluación temporal, proyección y benchmark.
- `examples/synthetic/`: datos inventados y etiquetas; el CSV pequeño original permanece sin cambios.
- `reports/`: resultados JSON ejecutados con límites y parámetros.
- `tests/test_analysis.py`, `test_forecast.py`, `test_exports.py`, `test_phase2_ui.py`, `test_synthetic.py`: cobertura nueva, junto a las pruebas existentes.
- `requirements.in`, `requirements.txt`, `Dockerfile`, `.dockerignore` y este README: dependencias fijadas, empaquetado y documentación.

No se modifican `web-demo/` ni `desarrollo-app-web-normativa-ingenieria/`. La fase no añade autenticación, pagos, PDF ni integraciones externas.

## Propuesta de Fase 3

Validar con históricos reales autorizados y un responsable de mantenimiento: acordar unidades/umbrales, separar regímenes de carga, comprobar qué cambios merecen una revisión y medir falsas alertas y utilidad operativa. Repetir evaluación temporal por máquina y revisar los límites de proyección antes de formular promesas más fuertes. El PDF ejecutivo puede añadirse después de validar el contenido y las explicaciones que necesita ese responsable.

## Biblioteca internacional de datos industriales

La página incluye una biblioteca consultable **sin subir un CSV**, con seis fuentes
revisadas: AI4I 2020, Condition Monitoring of Hydraulic Systems, MetroPT-3,
Condition Based Maintenance of Naval Propulsion Plants, SECOM y el centro de
rodamientos de Case Western Reserve University. Permite buscar y filtrar por equipo,
consultar la fuente original y descargar los metadatos en JSON.

Se revisaron las APIs oficiales de UCI y sus fichas de licencia (CC BY 4.0), junto
con la página oficial de CWRU. Las condiciones de reutilización de CWRU quedan
pendientes de confirmar; una página accesible no equivale a permiso para redistribuir.
La fecha de revisión, DOI, autoría, procedencia y advertencias de adaptación figuran
en `resources/catalog.json`. No se incluyen registros de Zenodo cuyo contenido no
coincidía con el tema ni enlaces institucionales que devolvieron 404.

**Alcance:** se incorporan metadatos y conocimiento de preparación, no los conjuntos
completos ni entrenamiento adicional. Los datos nativos no son directamente
compatibles con el CSV de la aplicación: hay que verificar unidades, cronología,
identidad de equipos y etiquetas. No se inventan fechas ni se renombra aceleración
como velocidad de vibración. La biblioteca no consulta servicios externos durante
el análisis de archivos y no transmite a sus fuentes los datos subidos.

No representa todas las bases del mundo ni una validación con datos reales. El
siguiente paso útil es preparar un adaptador reproducible para un conjunto temporal,
por ejemplo MetroPT-3, y evaluar el modelo por periodos antes de afirmar mejoras.
