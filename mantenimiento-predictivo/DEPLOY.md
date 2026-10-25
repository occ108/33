# Despliegue de la demostración en Render

Se ha preparado `../render.yaml` para un servicio Docker gratuito en Frankfurt.
El proveedor debe confirmar disponibilidad y condiciones del plan antes de crearlo.
La URL definitiva la asigna Render al crear el servicio; no existe todavía.

## Requisitos pendientes

1. Publicar los archivos nuevos del proyecto y `render.yaml` en la rama `deploy/mantenimiento-predictivo` del repositorio GitHub que se conectará a Render. No incluir secretos ni los archivos del proyecto de normativa en el commit del despliegue.
2. Vincular una cuenta Render al repositorio mediante su integración GitHub.
3. En Render, crear un Blueprint desde ese repositorio, seleccionar la rama `deploy/mantenimiento-predictivo` y revisar que el servicio usa el plan `free` antes de desplegar. El Blueprint usa `render.yaml` de la raíz.

Alternativamente, un agente puede crear el servicio mediante la API de Render si dispone de acceso a `api.render.com` y una credencial `RENDER_API_KEY` configurada de forma segura en los ajustes del entorno. No enviar claves por chat. La API de GitHub en `api.github.com` permite comprobar permisos y publicación.

### Despliegue mediante API

La clave de red se utiliza exclusivamente para autenticar las peticiones HTTPS
a `api.render.com`; no se incorpora al contenedor ni a las variables de la app.
El script requiere el identificador público del espacio de trabajo de Render
(`tea-…` o `usr-…`), visible en la URL de su panel o en sus ajustes.

```sh
python3 deploy_render.py --owner-id IDENTIFICADOR_DEL_ESPACIO
```

El script reutiliza un servicio coincidente o crea uno con el plan `free`;
rechaza servicios existentes con configuración incompatible y guarda únicamente
identificadores y URL en `/tmp/mantenimiento-render-state.json`.
Después hay que consultar el estado del despliegue y verificar HTTP y la interfaz.
Crear el recurso no implica que la aplicación esté lista.

En esta sesión, la consulta de servicios de Render funciona con la clave, pero
la consulta `/v1/owners` devuelve un bloqueo HTML de Cloudflare (HTTP 403).
Eso impide descubrir automáticamente el identificador del espacio de trabajo.
No se necesita otra clave para resolver ese dato.

## Verificación posterior al despliegue

- La URL HTTPS asignada debe responder y `/_stcore/health` devolver `ok`.
- Activar «Probar con datos sintéticos»: 9 lecturas y 2 máquinas.
- Cambiar de máquina y sensor y comprobar que el gráfico se actualiza.
- Subir `examples/sensores_demo.csv` y verificar el mismo resumen.

El servicio gratuito puede suspenderse cuando no tiene uso y tardar en arrancar.
La demostración no tiene autenticación ni almacenamiento persistente configurado.
Usar datos sintéticos o anonimizados. Es una demostración pública, no el SaaS de producción.

## Comprobación Docker local cuando haya un daemon disponible

Desde este directorio:

```sh
docker build -t mantenimiento-predictivo-demo .
docker run --rm -p 8501:8501 mantenimiento-predictivo-demo
```

El contenedor se ejecuta sin privilegios de root y solo incorpora aplicación,
dependencias y el CSV sintético. El daemon Docker del entorno de onboarding está
disponible, pero sus contenedores de construcción no resuelven destinos de red.
La construcción directa falla al intentar descargar dependencias. Se ha construido
una imagen de validación equivalente usando las mismas versiones descargadas por
pip mediante HTTPS verificado desde el entorno host, e instaladas sin conexión
en el contenedor. No se ha desactivado TLS ni alterado ninguna dependencia.

La imagen de validación ha superado arranque con `PORT=10000`, comprobación
HTTP de salud y ejecución de la interfaz con 9 lecturas y 2 máquinas, bajo un
límite de 512 MiB y usuario sin privilegios. Esto verifica el contenedor local;
el despliegue y la URL pública de Render siguen pendientes.
