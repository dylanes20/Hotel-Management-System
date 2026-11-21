import os
from uuid import uuid4

import pytest
from sqlalchemy import URL, text

from backend import create_app, db
from backend.models import Guest, Room, RoomType


TEST_DATABASE = "hotel_management_api_test"


@pytest.fixture(scope="session")
def test_app():
    user = os.getenv("HOTEL_API_TEST_DB_USER")
    if not user:
        pytest.skip("Configura HOTEL_API_TEST_DB_USER para ejecutar las pruebas MySQL.")
    url = URL.create(
        "mysql+pymysql",
        username=user,
        password=os.getenv("HOTEL_API_TEST_DB_PASSWORD"),
        host=os.getenv("HOTEL_API_TEST_DB_HOST", "127.0.0.1"),
        port=int(os.getenv("HOTEL_API_TEST_DB_PORT", "3306")),
        database=TEST_DATABASE,
        query={"charset": "utf8mb4"},
    )
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": url})

    @app.teardown_request
    def close_request_session(_error):
        db.session.remove()

    yield app
    with app.app_context():
        db.engine.dispose()


@pytest.fixture
def test_connection(test_app, monkeypatch):
    with test_app.app_context():
        engine = db.engine
        with engine.connect() as connection:
            transaction = connection.begin()
            if connection.scalar(text("SELECT DATABASE()")) != TEST_DATABASE:
                pytest.fail(f"Las pruebas requieren la base {TEST_DATABASE}.")

            tables = dict(connection.execute(text("""
                SELECT TABLE_NAME, ENGINE
                  FROM information_schema.TABLES
                 WHERE TABLE_SCHEMA = DATABASE()
            """)).all())
            for table in db.metadata.tables:
                if tables.get(table) != "InnoDB":
                    pytest.fail(f"{TEST_DATABASE}.{table} debe existir y usar InnoDB.")

            # Las confirmaciones de la API liberan savepoints dentro de esta
            # transacción. El rollback exterior descarta las filas de cada caso.
            with monkeypatch.context() as patch:
                patch.setitem(db.engines, None, connection)
                patch.setitem(db.session.session_factory.kw, "join_transaction_mode", "create_savepoint")
                try:
                    yield connection
                finally:
                    db.session.remove()
                    transaction.rollback()


@pytest.fixture
def client(test_app, test_connection):
    return test_app.test_client()


@pytest.fixture
def inventory(test_connection):
    suffix = uuid4().hex
    guest = Guest(full_name="Huésped de prueba", identification_number=suffix[:30])
    room_type = RoomType(name=suffix, capacity=2, base_nightly_rate=70)
    db.session.add_all([guest, room_type])
    db.session.flush()
    room = Room(room_type_id=room_type.room_type_id, room_number=suffix[:10], floor=1)
    db.session.add(room)
    db.session.flush()
    ids = guest.guest_id, room_type.room_type_id, room.room_id
    db.session.commit()
    return ids


@pytest.fixture
def reservation_data(inventory):
    guest_id, _, room_id = inventory
    return {
        "guest_id": guest_id,
        "room_id": room_id,
        "check_in_date": "2026-12-20",
        "check_out_date": "2026-12-23",
        "nightly_rate": "70.00",
    }
