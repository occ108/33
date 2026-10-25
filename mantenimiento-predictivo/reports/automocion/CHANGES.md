# Archivos principales

- automotive.py y catalog/automocion.json: vehículos/componentes/parámetros como datos.
- data_contract.py: carga y códigos de error, rangos y columnas opcionales.
- i18n.py y locales/: traducciones, formatos y glosario.
- vehicle_analysis.py: alertas inferiores y contador km sin alterar el motor superior.
- analysis.py: registro de sensores desde el catálogo; algoritmo industrial conservado.
- app.py y catalog.py: nueva presentación, estado por sesión y recursos plegados.
- assets/ y .streamlit/: identidad, favicon y tema.
- scripts/generate_vehicles.py, evaluate_vehicles.py, benchmark_automotive.py: evidencia reproducible.
- examples/vehicles/: flota sintética y etiquetas.
- tests/: catálogo, idiomas, nuevos contratos, regresiones de interfaz migradas.
- Dockerfile/.dockerignore: módulos y recursos nuevos.
- README.md: uso es/en/de, metodología y límites.

Los archivos de normativa y web-demo no se han modificado. Los cambios anteriores
no relacionados en DEPLOY.md y deploy_render.py se mantienen sin incorporar al commit.
