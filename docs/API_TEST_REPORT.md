# Project Advance · Pruebas automatizadas de la API

## Resultado confirmado 

La [salida de pytest](evidence/api/pytest_results.txt) registra **22 pruebas
aprobadas, 0 fallidas y 0 omitidas en 0,26 s**. se ejecutó la suite
contra `hotel_management_api_test` después de corregir el borrado con
referencias. Este registro precede a la incorporación de la GUI.



## Casos y criterios de aceptación

| IDs | Casos | Resultado esperado | Estado |
|---|---|---|---|
| API-01 a API-03 | CRUD de huéspedes, habitaciones y reservas | POST 201 con Location, listado y lectura 200, PATCH y PUT 200, DELETE 204 y GET posterior 404 | Aprobados en Omarchy |
| API-04 | Identificación duplicada | POST 409 con error JSON | Aprobado en Omarchy |
| API-05 a API-09 | Fecha inexistente, salida igual a entrada, salida real sin entrada, tarifa con más de dos decimales y estado inválido | POST 400 con error JSON en cada caso | Aprobados en Omarchy |
| API-10 | Solapamiento al crear y editar, fechas contiguas y cancelación | 409 al solapar, 201 para fechas contiguas y para volver a reservar tras cancelar | Aprobado en Omarchy |
| API-11 | Habitación en mantenimiento | POST 409 | Aprobado en Omarchy |
| API-12 y API-13 | Borrar una reserva con pago o cargo asociado | DELETE 409 y la reserva sigue disponible por GET | Aprobados en Omarchy |
| API-14 | Ruta desconocida y método no permitido | 404 con error JSON y 405, sin conexión a MySQL | Aprobado |
| API-15 a API-21 | ID de solo lectura, nombre vacío, piso booleano, estado de habitación inválido, fecha inexistente, importe no finito e importe con tres decimales | La validación rechaza cada valor | Aprobados |
| API-22 | Tipos y valores por defecto de una reserva | Fecha e importe convertidos a tipos de Python, estado `booked` y fechas reales nulas | Aprobado |

## Cambios en las pruebas

Los tres CRUD comprueban directamente en MySQL que la fila exista después de
la creación, que el valor actualizado se almacene y que la fila desaparezca
tras el borrado. Estas consultas usan la misma transacción aislada del caso.
Se añadieron ocho casos de validación que funcionan sin servidor MySQL.
La ejecución sin MySQL no reveló errores en la aplicación.

## Preparación en Omarchy

Desde la raíz del proyecto, comprueba el entorno y el puerto:

```bash
source .venv/bin/activate
python -m pytest --version
docker port mysqlcontainer2 3306/tcp
```

Genera una copia temporal del SQL y verifica el destino antes de importarla:

```bash
test_sql=$(mktemp /tmp/hotel-api-test.XXXXXX.sql)
sed 's/\bhotel_management\b/hotel_management_api_test/g' database/01_schema.sql > "$test_sql"
rg -n '^(CREATE DATABASE|USE)\b|\bhotel_management\b' "$test_sql"
```

La revisión debe mostrar únicamente `CREATE DATABASE IF NOT EXISTS
hotel_management_api_test` y `USE hotel_management_api_test` como instrucciones
de destino. El archivo crea las siete tablas y no carga los datos de ejemplo.
Antes de importarlo, comprueba desde una sesión administrativa si el esquema
de pruebas ya existe:

```bash
docker exec -it mysqlcontainer2 mysql -u root -p
```

```sql
SELECT SCHEMA_NAME FROM information_schema.SCHEMATA
WHERE SCHEMA_NAME = 'hotel_management_api_test';
```

Si no existe, sal de MySQL, copia el SQL y vuelve a abrir el cliente:

```bash
docker cp "$test_sql" mysqlcontainer2:/tmp/hotel_management_api_test.sql
docker exec -it mysqlcontainer2 mysql -u root -p
```

Para una instalación nueva del esquema y de la cuenta dedicada, ejecuta en
MySQL:

```sql
SOURCE /tmp/hotel_management_api_test.sql
SELECT DATABASE();
SHOW TABLES;
CREATE USER 'hotel_api_test'@'%' IDENTIFIED BY RANDOM PASSWORD;
GRANT SELECT, INSERT, UPDATE, DELETE ON hotel_management_api_test.guest TO 'hotel_api_test'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON hotel_management_api_test.room_type TO 'hotel_api_test'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON hotel_management_api_test.room TO 'hotel_api_test'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON hotel_management_api_test.reservation TO 'hotel_api_test'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON hotel_management_api_test.payment TO 'hotel_api_test'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON hotel_management_api_test.service TO 'hotel_api_test'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON hotel_management_api_test.service_charge TO 'hotel_api_test'@'%';
SHOW GRANTS FOR 'hotel_api_test'@'%';
```

Verifica que `SELECT DATABASE()` devuelva `hotel_management_api_test` y que
`SHOW TABLES` muestre las siete tablas. Conserva la contraseña generada en
privado. Si ya existe el esquema o el usuario, verifica sus tablas y permisos
antes de reutilizarlos. El usuario de pruebas solo debe tener permisos de
escritura sobre ese esquema. Para usar Docker desde el mismo equipo, publica
el puerto de MySQL en la interfaz de loopback.

## Ejecución de la suite

Define el puerto publicado, sustituye `3306` si corresponde y escribe la
contraseña generada cuando se solicite:

```bash
export HOTEL_API_TEST_DB_HOST=127.0.0.1
export HOTEL_API_TEST_DB_PORT=3306
export HOTEL_API_TEST_DB_USER=hotel_api_test
read -rsp 'Contraseña de MySQL para pruebas: ' HOTEL_API_TEST_DB_PASSWORD
printf '\n'
export HOTEL_API_TEST_DB_PASSWORD
```

Verifica la base y los permisos con la cuenta de pruebas antes de ejecutar el
CRUD:

```bash
python - <<'PY'
import os
import pymysql

with pymysql.connect(
    host=os.environ["HOTEL_API_TEST_DB_HOST"],
    port=int(os.environ["HOTEL_API_TEST_DB_PORT"]),
    user=os.environ["HOTEL_API_TEST_DB_USER"],
    password=os.environ["HOTEL_API_TEST_DB_PASSWORD"],
    database="hotel_management_api_test",
) as connection:
    with connection.cursor() as cursor:
        cursor.execute("SELECT DATABASE()")
        database = cursor.fetchone()[0]
        print(database)
        if database != "hotel_management_api_test":
            raise SystemExit("Destino incorrecto.")
        cursor.execute("SHOW GRANTS FOR CURRENT_USER()")
        for grant, in cursor:
            print(grant)
PY
```

Tras verificar el destino y autorizar las escrituras y borrados de filas de
prueba en ese esquema, ejecuta:

```bash
python -m pytest -q -rs backend/tests/test_api.py -k test_crud
python -m pytest -q -rs backend/tests
unset HOTEL_API_TEST_DB_PASSWORD
```

Las pruebas fijan el nombre del esquema, leen únicamente variables
`HOTEL_API_TEST_DB_*`, comprueban el destino efectivo y que las siete tablas
usen InnoDB antes de escribir. Cada caso usa sus propios datos y revierte la
transacción exterior incluso si falla una aserción. Los contadores de
autoincremento del esquema aislado pueden avanzar. Registra la última línea
de pytest para sustituir el resultado pendiente de integración en este informe.

## Corrección del borrado con referencias

En la ejecución desde Omarchy comunicada por el estudiante, se aprobaron
12 de 14 casos en 0,30 s. Fallaron los dos borrados de reservas con referencias:
MySQL devolvió `IntegrityError (1217)` y la API respondió HTTP 500.
El manejador ahora devuelve HTTP 409 para los códigos 1217 y 1451 y ejecuta
`rollback()` antes de responder. Los casos comparan todas las columnas de la
reserva y del pago o cargo antes y después del rechazo.

La comprobación local con errores simulados confirmó el 409 y la llamada a
`rollback()` para ambos códigos. La ejecución posterior contra MySQL quedó registrada al inicio del informe. Con el destino aislado ya verificado y las variables
de pruebas exportadas, guarda la salida real de los 14 casos originales:

```bash
set -o pipefail
python -m pytest -q -rs backend/tests/test_api.py backend/tests/test_http.py 2>&1 |
  tee docs/evidence/api-pytest-mysql.txt
```

## Ampliación del flujo de recepción

La ejecución histórica de 22 aprobadas permanece en
[evidence/api/pytest_results.txt](evidence/api/pytest_results.txt).
La suite ampliada suma 28 casos. La ejecución actual registró
**11 aprobados, 0 fallidos y 17 omitidos**. Los omitidos necesitan MySQL
y se reservan para la base `hotel_management_api_test`.
[Salida de la ejecución local](evidence/api/pytest-operacion-local.txt).

| Caso | Comprobación | Estado en esta ejecución |
|---|---|---|
| API-23 | Fechas ausentes, inválidas o invertidas y exclusión inválida devuelven 400 antes de acceder a MySQL | Aprobado |
| API-24 | Alta, consulta y edición de huésped, conflictos por documento y correo, reserva con el huésped seleccionado | Omitido |
| API-25 | Disponibilidad, fechas consecutivas, exclusión al editar, cambio de fechas, cancelación y borrado permitido | Omitido |
| API-26 | Mantenimiento y fuera de servicio, preservación del intervalo de una estancia finalizada | Omitido |
| API-27 | Dos solicitudes simultáneas, una sola reserva almacenada, respuestas 201 y 409 | Omitido |
| GUI-H01 | Flask sirve la página, los controles nuevos y los recursos estáticos sin conectarse a MySQL | Aprobado |

Las pruebas ya existentes de solapamiento al crear y editar, reservas
consecutivas y borrado restringido por pagos o cargos siguen en la suite.
El caso concurrente utiliza conexiones distintas. Confirma filas de prueba
propias y las limpia por ID al terminar. Verifica el nombre del esquema y
las tablas InnoDB antes de crear o limpiar esos registros.

Después de verificar el destino y autorizar las escrituras de prueba, captura
la nueva ejecución en Omarchy. Conserva el archivo histórico de 22 casos:

```bash
source .venv/bin/activate
: "${HOTEL_API_TEST_DB_USER:?Configura el usuario aislado antes de ejecutar}"
set -o pipefail
python -m pytest -q -rs backend/tests 2>&1 | tee docs/evidence/api/pytest-operacion-mysql.txt
```

## Disponibilidad de habitaciones por intervalo

El [registro de Omarchy](evidence/api/pytest_results_final.txt) conserva las
**28 pruebas aprobadas en 0,38 s** antes de este cambio. El caso nuevo
`test_room_overview_reflects_stays_and_physical_status` comprueba en
`hotel_management_api_test` el nombre del tipo, los intervalos consecutivos,
los cambios de fechas, la cancelación y la prioridad del estado físico.
Está pendiente de ejecución contra MySQL. El [registro local](evidence/gui/rooms-availability-local.txt)
incluye la prueba de las fichas con Node y la ejecución sin MySQL.

## Catálogo de demostración

El [registro local](evidence/gui/demo-catalog-local.txt) incluye la prueba
JavaScript de la ficha, la verificación de las imágenes de Flask y el caso
que comprueba que el seed rechaza `hotel_management` antes de acceder a las
tablas. La prueba de integración del seed verifica previsualización,
idempotencia, conservación de la 901 y sus reservas, y los datos que devuelve
la API. Está pendiente de ejecución contra MySQL aislado.
