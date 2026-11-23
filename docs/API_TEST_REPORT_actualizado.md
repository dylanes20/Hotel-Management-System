# Project Advance · Pruebas automatizadas de la API

## Resultado confirmado

Ejecutamos la suite completa de pruebas automatizadas de nuestra API y de la
integración con Flask en Omarchy, utilizando la base de datos aislada
`hotel_management_api_test`. Obtuvimos **31 pruebas aprobadas y 0 fallidas en 0,43 s**.

La evidencia de esta ejecución se encuentra en
[**pytest_results_final.txt**](evidence/api/pytest_results_final.txt).
Las pruebas cubren las operaciones CRUD, validaciones, disponibilidad de
habitaciones, integridad referencial y flujos asociados a la interfaz.


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
También implementamos casos de validación y verificaciones de las reglas
de negocio. La ejecución final se realizó con MySQL disponible, por lo que
pudimos comprobar tanto las validaciones como los casos de integración.

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

Las pruebas utilizan las variables `HOTEL_API_TEST_DB_*` y verifican el
esquema aislado antes de escribir. Cada caso utiliza datos propios y aplica
las medidas de aislamiento y limpieza correspondientes. Los contadores de
autoincremento del esquema aislado pueden avanzar. La salida comprobada de la
suite está archivada en `docs/evidence/api/pytest_results_final.txt`.

## Corrección del borrado con referencias

Implementamos el manejo de conflictos de integridad al intentar eliminar una
reserva que tiene pagos o cargos relacionados. Para los errores de MySQL
`IntegrityError` con códigos 1217 y 1451, la API devuelve **HTTP 409** y
ejecuta `rollback()` en lugar de dejar una transacción inválida.

Los casos de prueba comprueban que la solicitud de borrado se rechace y que
la reserva, junto con sus pagos o cargos, permanezca almacenada. Incluimos
estas verificaciones en la suite automatizada que aprobamos en Omarchy.

Para ejecutar individualmente las pruebas de la API y sus respuestas HTTP:

```bash
python -m pytest -v backend/tests/test_api.py backend/tests/test_http.py
```

## Ampliación del flujo de recepción

Ampliamos nuestras pruebas para verificar el registro de huéspedes desde la
interfaz, la consulta de disponibilidad y la gestión de reservas. Estos casos
forman parte de la ejecución final de **31 pruebas aprobadas**.

| Caso | Comprobación | Estado final |
|---|---|---|
| API-23 | Fechas ausentes, inválidas o invertidas y exclusión inválida devuelven HTTP 400 | Aprobado |
| API-24 | Alta, consulta y edición de huéspedes; conflictos por documento y correo; reserva con el huésped seleccionado | Aprobado |
| API-25 | Disponibilidad, fechas consecutivas, exclusión al editar, cambio de fechas, cancelación y borrado permitido | Aprobado |
| API-26 | Habitaciones en mantenimiento o fuera de servicio y conservación del intervalo histórico de una estancia finalizada | Aprobado |
| API-27 | Dos solicitudes simultáneas para una habitación: solo una reserva queda almacenada | Aprobado |
| GUI-H01 | Flask sirve la página, los controles y los recursos estáticos correctamente | Aprobado |

Las pruebas de solapamiento al crear y editar, reservas consecutivas y
borrado restringido por pagos o cargos también se mantienen en nuestra suite.
Para los escenarios que lo requieren, verificamos los resultados directamente
en la base de datos de pruebas.

Ejecutamos el conjunto completo desde la raíz del proyecto con:

```bash
source .venv/bin/activate
set -o pipefail
python -m pytest -q backend/tests -rs 2>&1 | tee docs/evidence/api/pytest_results_final.txt
```

Resultado registrado:

```text
...............................                                          [100%]
31 passed in 0.43s
```

## Disponibilidad de habitaciones por intervalo

Comprobamos que la disponibilidad de las habitaciones dependa de las fechas
seleccionadas y no únicamente del estado físico almacenado en `room`.
La prueba `test_room_overview_reflects_stays_and_physical_status` verifica
el nombre del tipo de habitación, los intervalos consecutivos, los cambios
de fechas, la cancelación y la prioridad de los estados de mantenimiento o
fuera de servicio.

Este caso quedó incluido en la ejecución completa de **31 pruebas aprobadas**
contra `hotel_management_api_test`. También realizamos una comprobación del
JavaScript utilizado para presentar los estados en las fichas.

## Catálogo de demostración

Incorporamos pruebas para el catálogo de cinco habitaciones y el script
`database/seed_demo_rooms.py`. Comprobamos que el script solo acepte la base
de datos de pruebas, que permita previsualizar las inserciones, que evite
duplicar habitaciones y que conserve la habitación 901 y sus reservas.

En Omarchy ejecutamos el script y verificamos el catálogo final:

```text
Destino verificado: hotel_management_api_test
Catálogo inicial: 901
Habitaciones insertadas: 101, 102, 201, 202
Catálogo final: 101, 102, 201, 202, 901
```

Las pruebas automatizadas correspondientes también se incluyeron en la
**suite final de 31 casos aprobados**. La evidencia completa está disponible
en [pytest_results_final.txt](evidence/api/pytest_results_final.txt).
