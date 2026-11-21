# Comprehensive Hotel Management and Administration System

Proyecto universitario de diseno e implementacion de una BD para **un hotel**, con siete tablas: `guest`, `room_type`, `room`, `reservation`, `payment`, `service` y `service_charge`.

## Estado y honestidad de las fuentes

Este repositorio es una **reconstruccion reproducible basada en `pj2.pdf`**, no una copia exacta de los scripts SQL usados inicialmente en Stage 2. El PDF reporta 18 casos `Passed` ejecutados manualmente en MySQL 8.0.33 (Docker: `mysqlcontainer2`); aqui se aporta un archivo SQL por caso y un ejecutor para repetirlos en un esquema aislado. No se ha verificado de nuevo su ejecucion en el MySQL del equipo del estudiante.

Los archivos `01_schema.sql`, `02_sample_data.sql` y `03_queries.sql` se recrearon respetando el esquema, los valores principales y las reglas documentadas. Los datos de ejemplo que no figuraban en el PDF son **ficticios**, construidos para poder reproducir los resultados esperados.

## Estructura

```text
hotel-management-reproducible/
  README.md
  database/01_schema.sql        # MySQL 8.0: 7 tablas, llaves, checks, indices
  database/02_sample_data.sql   # Fixtures ficticios de prueba
  database/03_queries.sql       # Disponibilidad, conflictos y balances
  tests/sql/TC-01.sql ... TC-18.sql  # Un SQL por caso documentado
  tests/run_all.py              # Runner secuencial y validacion de resultados
  tests/TC-12_manual.md         # Reinicio Docker (manual)
  docs/TEST_CASES.md            # Trazabilidad de los 18 tests
  docs/PROCEDIMIENTO_PASO_A_PASO.md # Explicacion de cada prueba
  docs/evidence/TC-01.png ... # Capturas del PDF, 18 imagenes
  docs/TRACEABILITY.md          # Diferencias PDF/codigo y limitaciones
  docs/pj2.pdf                  # Especificacion Stage 2, fuente primaria
  docs/README_Stage2_source.md # Documentacion anterior preservada
```

## Requisitos para ejecutar

- MySQL 8.0.16 o superior con `CHECK` activo (referencia: 8.0.33).
- Docker y el contenedor `mysqlcontainer2` funcionando (por defecto), o cliente `mysql` local.
- Python 3.9+ para ejecutar `tests/run_all.py` (solo biblioteca estandar).
- Permisos para crear/eliminar **solo la base de prueba `hotel_management_test`**.

## Ejecucion automatica de pruebas

En Ubuntu con contenedor Docker existente:

```bash
export HOTEL_MYSQL_MODE=docker
export HOTEL_MYSQL_CONTAINER=mysqlcontainer2
export HOTEL_MYSQL_USER=root
# Solo en tu terminal local, sin compartir passwords en GitHub:
read -rs -p 'Password MySQL: ' HOTEL_MYSQL_PASSWORD; echo
export HOTEL_MYSQL_PASSWORD
python3 tests/run_all.py --reset-test-db
unset HOTEL_MYSQL_PASSWORD
```

Para un servidor MySQL accesible mediante el cliente local:

```bash
export HOTEL_MYSQL_MODE=local
export HOTEL_MYSQL_HOST=127.0.0.1
export HOTEL_MYSQL_PORT=3306
export HOTEL_MYSQL_USER=root
read -rs -p 'Password MySQL: ' HOTEL_MYSQL_PASSWORD; echo
export HOTEL_MYSQL_PASSWORD
python3 tests/run_all.py --reset-test-db
unset HOTEL_MYSQL_PASSWORD
```

El runner recrea **unicamente `hotel_management_test`**, carga tablas y fixtures, y ejecuta los tests en orden. Valida 17 tests; TC-12 depende de reiniciar Docker y se explica en `tests/TC-12_manual.md`. Los tests de errores esperan los codigos **1048, 1062 y 3819**. TC-05 evidencia una limitacion, no un bloqueo completo; TC-11 es una prueba basica, no una prueba de estres.

**No ejecutes el reset contra una BD real con datos que quieras conservar.** No se recomienda subir contrasenas, claves, ni exportaciones con datos de personas reales.

## Manual: inspeccionar scripts

Si solo quieres revisar SQL, abre `database/01_schema.sql`, luego los SQL de cada prueba, y consulta `docs/TEST_CASES.md`. La carpeta `database/` usa el nombre `hotel_management` y sirve para desplegar el esquema nuevo; el runner sustituye dicho nombre por `hotel_management_test` para ejecutar pruebas sin afectar tu BD principal.

## Limitaciones de Stage 2

- No se garantizan reservas sin solapamiento ante inserciones directas (ver TC-05).
- No se implementan usuarios por rol, backups diarios, cifrado TLS ni pruebas de concurrencia.
- Stage 2 incluye pruebas SQL. El backend y los casos HTTP de Project Advance están en `backend/`. La interfaz gráfica y su integración están pendientes.

El documento original `docs/pj2.pdf` contiene la seccion 4 y las capturas de los tests manuales. Los scripts de esta entrega son una *reproduccion* de su comportamiento, no sus originales.

## Evidencias originales y guia

- [Procedimiento de cada test](docs/PROCEDIMIENTO_PASO_A_PASO.md)
- [Tabla de 18 pruebas con capturas enlazadas](docs/TEST_CASES.md)
- [Evidencia original: TC-05](docs/evidence/TC-05.png)

## Entrega en GitHub

Usa la [guía de recuperación y entrega](docs/PROJECT_ADVANCE_DELIVERY.md) para
trasladar el trabajo a un clon del repositorio original y revisar los
archivos antes de publicar.

## API REST de Project Advance

El backend se conecta a las tablas MySQL existentes. La fábrica de la API no
crea tablas ni ejecuta migraciones.

### Ejecutar en Omarchy

Desde la raíz del proyecto, crea un entorno virtual e instala las dependencias
con autorización:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cp -n backend/.env.example backend/.env
```

Configura `backend/.env` con el usuario MySQL y su contraseña. Las variables
exportadas tienen prioridad sobre ese archivo. Usa una cuenta con permisos
`SELECT`, `INSERT`, `UPDATE` y `DELETE` para las tablas del CRUD y `SELECT`
para `room_type`. No hacen falta permisos de DDL. Para una primera comprobación
de solo lectura, usa una cuenta con solo `SELECT`.

Flask se ejecuta en el host y necesita un puerto MySQL publicado por
`mysqlcontainer2`. Consulta el puerto con `docker port mysqlcontainer2 3306/tcp`
y ajusta `HOTEL_API_DB_PORT`. Los comandos siguientes arrancan el servidor de
desarrollo en la interfaz local y consultan los huéspedes:

```bash
python -m flask --app backend:create_app run
curl -i http://127.0.0.1:5000/api/guests
```

### Contrato HTTP

| Ruta | Métodos |
| --- | --- |
| `/api/guests`, `/api/rooms`, `/api/reservations` | `GET` lista; `POST` crea |
| `/api/guests/<id>`, `/api/rooms/<id>`, `/api/reservations/<id>` | `GET` consulta; `PUT` reemplaza; `PATCH` edita campos; `DELETE` elimina |

Las listas y consultas devuelven `200`. Una creación devuelve `201` con
`Location`, y un borrado exitoso devuelve `204`. Los errores JSON tienen un
campo `error`: `400` para datos inválidos, `404` para recursos ausentes,
`409` para conflictos y `415` cuando el cuerpo no se envía como JSON.

Los cuerpos usan los nombres de columnas del esquema. Los IDs primarios son de
solo lectura. Para crear una reserva se requieren `guest_id`, `room_id`,
`check_in_date`, `check_out_date` y `nightly_rate`. Las fechas usan
`AAAA-MM-DD` y los importes se devuelven como cadenas decimales. Las reservas
`booked` y `checked_in` requieren una habitación disponible y bloquean fechas
entre entrada (incluida) y salida (excluida). Las escrituras desde la API
comprueban el solapamiento dentro de una transacción. Una reserva con pagos o
cargos asociados devuelve `409` al intentar borrarla. Se puede conservar el
historial estableciendo `status` a `cancelled`.

### Pruebas HTTP con MySQL aislado

Provisiona una base vacía llamada exactamente `hotel_management_api_test`
con el esquema de `database/01_schema.sql`. Para preparar el SQL de prueba,
genera una copia que cambie el nombre de la base:

```bash
sed 's/\bhotel_management\b/hotel_management_api_test/g' database/01_schema.sql > /tmp/hotel_management_api_test.sql
```

Antes de importar, verifica que las sentencias `CREATE DATABASE` y `USE`
apunten a `hotel_management_api_test`. Importa la copia con una cuenta
administrativa y usa para pytest una cuenta con permisos de lectura y
escritura limitados a esa base. No se requiere importar datos de ejemplo.

Exporta `HOTEL_API_TEST_DB_USER` y `HOTEL_API_TEST_DB_PASSWORD` desde tu
sesión local. Si hace falta, ajusta `HOTEL_API_TEST_DB_HOST` y
`HOTEL_API_TEST_DB_PORT`. El nombre de la base de pruebas es fijo en el código.
Cada caso crea sus propias filas y revierte los cambios al terminar mediante
una transacción externa. Sin el usuario de pruebas, se omiten los casos que
requieren MySQL.

```bash
python -m pytest -q backend/tests
```

El [informe de pruebas de la API](docs/API_TEST_REPORT.md) detalla la configuración en Omarchy, los casos y los resultados.

## Interfaz web

La GUI usa HTML, CSS y JavaScript nativo, servidos por Flask. Solo requiere
las dependencias del backend. Desde la raíz del proyecto en Omarchy:

```bash
source .venv/bin/activate
python -m flask --app backend:create_app run
```

Abre `http://127.0.0.1:5000/` en el navegador. La interfaz toma la conexión
MySQL configurada para Flask. Huéspedes y habitaciones se pueden consultar y
buscar. En **Reservas** se pueden crear, abrir, editar y eliminar registros.
El borrado pide confirmación y muestra un aviso si la reserva tiene pagos o
cargos. Para probar escrituras, arranca Flask con la base aislada siguiendo
la [guía de verificación de la GUI](docs/evidence/gui/README.md).
