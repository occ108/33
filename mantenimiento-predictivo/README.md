# Mantenimiento Predictivo Ligero · Fase 1

Prototipo Streamlit para validar CSV y explorar series temporales por máquina.
No incluye todavía modelos, predicción de fallos, PDF, autenticación, pagos ni envíos comerciales.
La aplicación de normativa del directorio vecino se conserva como proyecto independiente.

## Preparar y ejecutar (Python 3.12)

Desde este directorio, en un equipo de desarrollo:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py --server.headless=true --server.maxUploadSize=10
```

En Windows, usa `.venv\Scripts\python.exe` en lugar de `.venv/bin/python`.
En el entorno cloud ya preparado, el intérprete está en
`/workspace/.venvs/mantenimiento-predictivo/bin/python`; no necesitas crear otro entorno.
Para iniciarlo aquí:

```sh
cd /workspace/33/mantenimiento-predictivo
/workspace/.venvs/mantenimiento-predictivo/bin/python -m streamlit run app.py --server.address=0.0.0.0 --server.port=8501 --server.headless=true --server.maxUploadSize=10 --browser.gatherUsageStats=false
```

El servidor de desarrollo no constituye un despliegue público ni ofrece todavía autenticación.
Usa datos sintéticos o anonimizados para esta fase.

## Validación

```sh
/workspace/.venvs/mantenimiento-predictivo/bin/python -m unittest discover -s tests -v
```

Activa «Probar con datos sintéticos». Deben aparecer 9 lecturas y 2 máquinas.
Selecciona una máquina y un sensor para ver la serie temporal. Las pruebas automáticas
comprueban el flujo de interfaz y el rechazo de entradas inválidas.

## Contrato CSV inicial

- UTF-8, delimitador coma, punto decimal, cabecera única.
- `timestamp`: fecha ISO 8601; preferible incluir `Z` o desplazamiento horario. Sin zona se interpreta como UTC.
- `asset_id`: identificador de máquina no vacío.
- Al menos uno: `temperature_c` (°C), `vibration_mm_s` (mm/s RMS), `pressure_bar` (bar).
- `operating_hours`: opcional, numérico no negativo.
- Una lectura por máquina e instante; sin valores ausentes en sensores presentes.
- Máximo 10 MiB y 100.000 filas. No hay persistencia de CSV configurada ni caché global de datos.

El ejemplo es sintético y sirve para probar la carga; no entrena ni valida un modelo.
Antes del análisis acordaremos unidades, frecuencia, equipos y significado de cada señal.

## Organización inicial

`app.py` contiene contrato de datos, función pura `load_csv`, interfaz `main` y punto de entrada.
Las siguientes fases extraerán el análisis a `analysis.py`, el PDF a `reports.py` y las
integraciones a módulos separados; no se crearán hasta necesitarlas.

`requirements.in` declara dependencias directas; `requirements.txt` fija el entorno probado.
