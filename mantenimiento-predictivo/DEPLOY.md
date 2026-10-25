# Despliegue de la Fase 2

Servicio existente: https://mantenimiento-predictivo-demo.onrender.com

La configuración `../render.yaml` conserva el servicio Docker gratuito, región Frankfurt,
puerto dinámico y comprobación `/_stcore/health`. La rama de despliegue es
`deploy/mantenimiento-predictivo`. El estado de una publicación se verifica en Render;
una construcción local no demuestra que la instancia pública esté actualizada.

## Construir y probar

Desde `mantenimiento-predictivo/`:

```sh
docker build -t mantenimiento-predictivo:fase2 .
docker run --rm -p 8501:8501 --memory=512m mantenimiento-predictivo:fase2
```

El Dockerfile incorpora `app.py`, `analysis.py`, `exports.py` y los ejemplos sintéticos.
Se ejecuta con usuario sin privilegios. No incorpora tests, informes, archivos de usuario,
credenciales ni la herramienta de despliegue. Mantiene la verificación TLS y de artefactos.

## Construcción sin red en el contenedor

El daemon Docker de este entorno no resuelve los destinos de descarga. Para verificar
el Dockerfile real se descargaron wheels mediante pip y HTTPS verificado en el host:

```sh
python -m pip download --only-binary=:all: -r requirements.txt -d .wheels
docker build --network=none -t mantenimiento-predictivo:fase2 .
```

La carpeta `.wheels/` está ignorada por Git y excluida del ZIP. Se monta únicamente durante
la construcción y no queda en la imagen final. Cuando no existe, el mismo Dockerfile
instala desde el índice normal mediante HTTPS, como en Render. No se han desactivado
TLS, firmas ni comprobaciones de integridad. La imagen usa BuildKit para ese montaje.

Los resultados medidos se guardan en `reports/docker.json` y
`reports/benchmark_docker.json`, separados del benchmark del host.

## Publicar o reutilizar el servicio

La clave `RENDER_API_KEY` es un secreto de red usado únicamente hacia `api.render.com`.
Nunca se incorpora a la aplicación ni al contenedor. El identificador de Workspace empieza
por `tea-`; el identificador de usuario `usr-` no sirve para crear el servicio de esta cuenta.

```sh
python deploy_render.py --owner-id IDENTIFICADOR_DEL_WORKSPACE
```

El script comprueba servicios existentes antes de crear uno y solo solicita el plan `free`.
La publicación también puede configurarse con un Blueprint de Render y `render.yaml`.
No pegar claves en archivos ni en el chat. Los identificadores y URL del servicio pueden
guardarse en `/tmp/mantenimiento-render-state.json`; ese archivo no contiene la clave.

## Validación posterior a cada publicación

1. Confirmar el estado `live` del despliegue correspondiente al commit publicado.
2. Comprobar HTTPS de la página y `/_stcore/health`, que debe devolver `ok`.
3. El ejemplo pequeño debe mostrar 9 lecturas, 2 máquinas y explicar que faltan datos.
4. Activar «Probar histórico de 90 días»: 10.800 lecturas y 5 máquinas.
5. Seleccionar M-005, Temperatura y Mantenimiento: debe mostrar la estimación hasta el
   umbral orientativo de 82 °C, su banda y las horas de uso desde la última lectura.
6. Verificar las tres pestañas y descargar los CSV seguros.

La demostración no tiene autenticación y no ofrece garantías de seguridad industrial.
Los archivos y ajustes permanecen en la sesión, sin persistencia configurada ni caché global.
El plan gratuito puede suspender el proceso cuando no tiene uso. Las mediciones no validan
varios usuarios simultáneos ni sustituyen una revisión con datos reales.
