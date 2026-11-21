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
| GUI-06 | Repetir la navegación en una ventana estrecha | Menú y formulario utilizables. La tabla permite desplazamiento horizontal. |

Guarda aquí las capturas o los registros reales del recorrido, identificados
por caso. Revisa que no muestren credenciales ni datos personales antes de
incorporarlos al repositorio. Los seis casos de navegador están pendientes.
