"""Previsualiza o completa el catálogo ficticio de hotel_management_api_test."""
import argparse
import os
from decimal import Decimal

from sqlalchemy import URL, create_engine, insert, select, text
from sqlalchemy.exc import SQLAlchemyError

from backend.models import Room, RoomType


TEST_DATABASE = "hotel_management_api_test"
DEMO_ROOMS = (
    ("101", 1, "Individual", 1, Decimal("45.00")),
    ("102", 1, "Doble", 2, Decimal("75.00")),
    ("201", 2, "Suite Junior", 2, Decimal("110.00")),
    ("202", 2, "Familiar", 4, Decimal("135.00")),
)


def catalog_query():
    return select(
        Room.room_number, Room.floor, Room.status, Room.room_type_id,
        RoomType.name, RoomType.capacity, RoomType.base_nightly_rate,
    ).join(RoomType, Room.room_type_id == RoomType.room_type_id).order_by(Room.room_number)


def seed_catalog(connection, *, apply=False):
    if connection.dialect.name != "mysql" or connection.scalar(text("SELECT DATABASE()")) != TEST_DATABASE:
        raise ValueError(f"El seed requiere MySQL y el esquema {TEST_DATABASE}.")
    engines = dict(connection.execute(text("""
        SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME IN ('room', 'room_type')
    """)).all())
    if engines != {"room": "InnoDB", "room_type": "InnoDB"}:
        raise ValueError("room y room_type deben existir y usar InnoDB.")

    before = list(connection.execute(catalog_query()).mappings())
    existing = {room["room_number"]: room for room in before}
    if "901" not in existing:
        raise ValueError("No se encontró la habitación 901 en la base de pruebas.")

    plan = []
    for number, floor, name, capacity, rate in DEMO_ROOMS:
        room_type = connection.execute(select(
            RoomType.room_type_id, RoomType.capacity, RoomType.base_nightly_rate,
        ).where(RoomType.name == name)).one_or_none()
        if room_type is not None and (room_type.capacity, room_type.base_nightly_rate) != (capacity, rate):
            raise ValueError(f"El tipo {name} ya existe con capacidad o tarifa distinta.")
        if number in existing:
            current = existing[number]
            if room_type is None or (current["floor"], current["room_type_id"]) != (floor, room_type.room_type_id):
                raise ValueError(f"La habitación {number} ya existe con piso o tipo distinto.")
            continue
        plan.append((number, floor, name, capacity, rate, room_type.room_type_id if room_type else None))

    if not apply:
        return before, [number for number, *_ in plan], before

    for number, floor, name, capacity, rate, type_id in plan:
        if type_id is None:
            type_id = connection.execute(insert(RoomType).values(
                name=name, capacity=capacity, base_nightly_rate=rate,
            )).inserted_primary_key[0]
        connection.execute(insert(Room).values(
            room_type_id=type_id, room_number=number, floor=floor,
        ))
    after = list(connection.execute(catalog_query()).mappings())
    return before, [number for number, *_ in plan], after


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Inserta las habitaciones que falten.")
    args = parser.parse_args()
    user = os.getenv("HOTEL_API_TEST_DB_USER")
    if not user:
        parser.error("Exporta HOTEL_API_TEST_DB_USER con la cuenta de pruebas.")

    try:
        engine = create_engine(URL.create(
            "mysql+pymysql", database=TEST_DATABASE, username=user,
            password=os.getenv("HOTEL_API_TEST_DB_PASSWORD"),
            host=os.getenv("HOTEL_API_TEST_DB_HOST", "127.0.0.1"),
            port=int(os.getenv("HOTEL_API_TEST_DB_PORT", "3306")),
            query={"charset": "utf8mb4"},
        ))
        try:
            with engine.begin() as connection:
                before, additions, after = seed_catalog(connection, apply=args.apply)
        finally:
            engine.dispose()
    except ValueError as error:
        parser.exit(1, f"{error}\n")
    except SQLAlchemyError as error:
        code = getattr(getattr(error, "orig", None), "args", ())
        mysql_code = code[0] if code and isinstance(code[0], int) else "desconocido"
        parser.exit(1, f"No se pudo completar el seed (código MySQL: {mysql_code}). Verifica conexión y datos.\n")

    print(f"Destino verificado: {TEST_DATABASE}")
    print("Catálogo inicial:", ", ".join(room["room_number"] for room in before))
    print("Habitaciones insertadas:" if args.apply else "Habitaciones por insertar:", ", ".join(additions) or "ninguna")
    if args.apply:
        print("Catálogo final:", ", ".join(room["room_number"] for room in after))
    if len(after) > 5:
        print("El catálogo contiene habitaciones adicionales. Se conservaron todas.")


if __name__ == "__main__":
    main()
