# Evidencias de la interfaz web

## Verificaciones ejecutadas

[Registro de verificación local](smoke-flask.txt). La prueba local solicita la
página y sus recursos con el cliente de Flask sin conectarse a MySQL. Los
resultados de la API previos a la GUI están en
[pytest_results.txt](../api/pytest_results.txt).

## Recorrido de integración en Omarchy

Para ver los datos actuales en modo de lectura, abre Flask con una cuenta
MySQL que solo tenga permiso SELECT. Para el recorrido CRUD usa
`hotel_management_api_test` y una cuenta limitada a sus siete tablas. La base
aislada debe tener al menos un huésped y una habitación disponible. El caso
de rechazo requiere una reserva con un pago o cargo asociado. Si aún faltan
estos registros, carga datos de demostración exclusivamente en la base
aislada antes del recorrido.

Desde la raíz, usa las variables de pruebas ya configuradas para arrancar
una instancia separada, en el puerto 5001:

```bash
source .venv/bin/activate
: "${HOTEL_API_TEST_DB_USER:?Configura el usuario de pruebas}"
: "${HOTEL_API_TEST_DB_PASSWORD:?Configura la contraseña de pruebas}"
HOTEL_API_DB_NAME=hotel_management_api_test \
HOTEL_API_DB_USER="$HOTEL_API_TEST_DB_USER" \
HOTEL_API_DB_PASSWORD="$HOTEL_API_TEST_DB_PASSWORD" \
HOTEL_API_DB_HOST="${HOTEL_API_TEST_DB_HOST:-127.0.0.1}" \
HOTEL_API_DB_PORT="${HOTEL_API_TEST_DB_PORT:-3306}" \
python -m flask --app backend:create_app run --port 5001
```

Abre `http://127.0.0.1:5001/`. Antes de hacer escrituras o borrados,
verifica el esquema con el procedimiento de
[preparación de las pruebas HTTP](../../API_TEST_REPORT.md).

| Caso | Acción | Evidencia esperada |
|---|---|---|
| GUI-01 | Abrir Huéspedes, Habitaciones y Reservas | Las tablas muestran los registros que devuelve la API. |
| GUI-02 | Crear una reserva con fechas libres y abrir sus detalles | HTTP 201 y 200. La fila existe en MySQL. |
| GUI-03 | Editar la tarifa y probar una salida anterior a la entrada | La edición responde HTTP 200 y se refleja en MySQL. El formulario rechaza las fechas inválidas. |
| GUI-04 | Abrir la confirmación de borrado, cancelar, volver a abrirla y confirmar | La cancelación conserva la fila. Confirmar devuelve HTTP 204 y elimina la fila de MySQL. |
| GUI-05 | Confirmar el borrado de una reserva con pago o cargo | HTTP 409, aviso en la interfaz y filas relacionadas intactas en MySQL. |
| GUI-07 | Registrar un huésped desde una reserva con fechas ya ingresadas | POST /api/guests 201. El huésped queda seleccionado y se conservan las fechas. Un documento duplicado muestra el error de la API. |
| GUI-06 | Repetir la navegación en una ventana estrecha | Menú y formulario utilizables. Las fichas se reorganizan en una columna. |

Guarda aquí las capturas o los registros reales del recorrido, identificados
por caso. Revisa que no muestren credenciales ni datos personales antes de
incorporarlos al repositorio. Los casos de navegador están pendientes.

## Rediseño Casa Albor

[Registro local del rediseño](smoke-casa-albor.txt). Comprueba la entrega de
la página, el formulario de huéspedes, el CSS, el JavaScript y los tres
archivos WebP mediante el cliente de Flask.

Las imágenes `albor-courtyard.webp`, `albor-suite.webp` y
`albor-room.webp` se generaron para este proyecto con OpenAI ImageGen.
Representan un hotel ficticio y se sirven localmente desde
`backend/static/images/`. Las imágenes de las fichas son ilustrativas.

## Flujo operativo ampliado

Repite el recorrido en la instancia aislada del puerto 5001.

| Caso | Acción y resultado que se debe registrar |
|---|---|
| GUI-08 | Seleccionar un intervalo ocupado y uno consecutivo. La habitación queda fuera del primer resultado y vuelve a aparecer para el segundo. |
| GUI-09 | Buscar un huésped por documento o registrar uno nuevo con fechas y tarifa ya ingresadas. La selección queda aplicada sin perder esos datos. Consultar y editar su ficha desde Huéspedes. |
| GUI-10 | Editar las fechas de una reserva. El sistema muestra habitaciones libres y conserva la actual si sigue disponible. |
| GUI-11 | Cancelar desde la ficha. El registro permanece como Cancelada y sus noches se liberan. Abrir por separado la confirmación de eliminar. |
| GUI-12 | Intentar guardar una habitación que otra sesión acaba de reservar. Registrar el 409 y la lista renovada de habitaciones. |

Pendiente ejecutar en navegador con MySQL y guardar las evidencias reales.

## Disponibilidad en las fichas de habitaciones

Abre **Habitaciones** en la instancia de pruebas del puerto 5001.

1. Deja las fechas vacías. Comprueba que la ficha muestre el nombre del tipo
   y el estado físico **Operativa**, **En mantenimiento** o **Fuera de servicio**.
2. Selecciona un intervalo que coincida con una reserva confirmada. La ficha
   debe mostrar **Reservada**. Usa como entrada la fecha de salida de esa
   reserva y comprueba **Disponible** si las noches siguientes están libres.
3. Crea, cambia las fechas o cancela una reserva en la base de pruebas.
   Vuelve a **Habitaciones** y verifica que se mantengan las fechas
   seleccionadas y se actualicen las fichas.
4. Comprueba que mantenimiento y fuera de servicio prevalezcan sobre el
   resultado por fechas.

La [ejecución local](rooms-availability-local.txt) verifica el renderizado
de las cinco etiquetas y el nombre del tipo con Node, y la entrega de los
controles de fechas con Flask. El recorrido en navegador con MySQL sigue
pendiente para este cambio.

## Imágenes del catálogo de demostración

`albor-individual.webp`, `albor-doble.webp`, `albor-suite-junior.webp` y
`albor-familiar.webp` se generaron con OpenAI ImageGen para el proyecto.
Son imágenes ilustrativas. Se sirven desde `backend/static/images/` y se
asignan por nombre de tipo. Otros tipos usan las imágenes locales existentes.

Para verificar el catálogo tras aplicar el seed, abre **Habitaciones** en la
instancia aislada. Comprueba número, tipo, piso, capacidad y tarifa, y luego
selecciona fechas para comparar las fichas con las opciones de **Nueva reserva**.
