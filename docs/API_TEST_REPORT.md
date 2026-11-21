# Project Advance · Pruebas automatizadas de la API

## Resultado confirmado en Omarchy

La [salida de pytest](evidence/api/pytest_results.txt) registra **22 pruebas
aprobadas, 0 fallidas y 0 omitidas en 0,26 s**. El estudiante ejecutó la suite
contra `hotel_management_api_test` después de corregir el borrado con
referencias. Este registro precede a la incorporación de la GUI.

## Verificación previa sin MySQL

Entorno virtual del proyecto con pytest 9.2.0. La verificación de dependencias
con `python -m pip check` pasó. pytest recolectó **22 casos**.

| Ejecución | Ejecutados | Aprobados | Fallidos | Omitidos |
|---|---:|---:|---:|---:|
| Suite sin credenciales de integración | 9 | 9 | 0 | 13 |

Los nueve casos aprobados verifican respuestas HTTP y validación de campos
sin abrir una conexión SQL. Los 13 casos de integración se omitieron en esa ejecución local.
Esta sesión no puede acceder al socket de Docker ni al puerto de MySQL. La
ejecución no escribió en ninguna base. El [registro de pytest](evidence/api-pytest-sin-mysql.txt)
conserva la salida de esta ejecución con la ruta local sustituida por
`<proyecto>`.

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
