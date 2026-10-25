# Demostración pública de la fase 1

Versión estática para probar la carga y validación de CSV y los gráficos sin
necesitar una cuenta de alojamiento Python. Todo el procesamiento ocurre en el
navegador; no hay backend, almacenamiento compartido, autenticación, pagos ni ML.
El proyecto Streamlit de `../app.py` se mantiene por separado.

## Probar y publicar

Sirve este directorio con `python3 -m http.server 8000` para desarrollar.
No necesita instalar paquetes ni usa dependencias externas.

La rama `gh-pages` contiene solo los archivos estáticos en su raíz. El servicio
rawgit.hack permite abrirlos como web mediante una URL de CDN de esta forma:

`https://rawcdn.githack.com/occ108/33/COMMIT_DE_GH_PAGES/index.html`

Utiliza el SHA completo de la publicación. Cada versión tiene una URL inmutable;
una actualización requiere un nuevo commit y una nueva URL. La documentación del
servicio confirma la entrega de HTML, CSS y JavaScript con los tipos MIME adecuados.
Es un CDN externo para esta demostración, no el alojamiento del futuro SaaS Python.

Se intentó activar GitHub Pages, pero la integración devuelve HTTP 403 para crear
el sitio. El CDN sirve los archivos que ya son públicos y no necesita activar Pages.
La rama también queda preparada para activar Pages desde los ajustes del repositorio
en el futuro, con origen `gh-pages` y directorio raíz.

## Validación realizada

En Chromium: carga inicial con 9 lecturas y 2 máquinas; subida del CSV de ejemplo;
rechazo de fechas inválidas; selección de máquina y sensor; gráfica SVG;
descarga de ejemplo; diseño móvil sin desbordamiento horizontal.
El CSV sintético coincide con `../examples/sensores_demo.csv`.
