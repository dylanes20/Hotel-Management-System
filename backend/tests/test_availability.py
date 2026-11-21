from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from sqlalchemy import URL, delete, insert, select

from backend import create_app, db
from backend.models import Guest, Reservation, Room, RoomType
from conftest import verify_test_database


RESERVATIONS = "/api/reservations"
AVAILABILITY = "/api/rooms/availability"


def available_rooms(client, start, end, exclude=None):
    params = {"check_in_date": start, "check_out_date": end}
    if exclude is not None:
        params["exclude_reservation_id"] = exclude
    response = client.get(AVAILABILITY, query_string=params)
    assert response.status_code == 200, response.json
    return {room["room_id"] for room in response.json}


def test_availability_validates_dates_without_mysql(monkeypatch):
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": URL.create("mysql+pymysql", database="hotel_management_api_test"),
    })

    def unexpected_connection(*args, **kwargs):
        raise AssertionError("Las fechas inválidas se deben rechazar antes de consultar MySQL.")

    with app.app_context():
        monkeypatch.setattr(db.engine, "connect", unexpected_connection)

    client = app.test_client()
    for params in (
        {},
        {"check_in_date": "2026-02-30", "check_out_date": "2026-03-01"},
        {"check_in_date": "2026-12-23", "check_out_date": "2026-12-20"},
        {"check_in_date": "2026-12-20", "check_out_date": "2026-12-23", "exclude_reservation_id": "0"},
    ):
        response = client.get(AVAILABILITY, query_string=params)
        assert response.status_code == 400
        assert "error" in response.json


def test_new_guest_can_be_selected_for_booking(client, reservation_data):
    suffix = uuid4().hex
    payload = {
        "full_name": "Huésped nuevo",
        "identification_number": suffix[:30],
        "phone": "3001234567",
        "email": f"{suffix}@example.test",
    }
    guest = client.post("/api/guests", json=payload)
    assert guest.status_code == 201, guest.json
    assert client.patch(guest.headers["Location"], json={"phone": "3001234568"}).status_code == 200
    assert client.get(guest.headers["Location"]).json["phone"] == "3001234568"

    duplicate_id = client.post("/api/guests", json=payload | {"email": None})
    assert duplicate_id.status_code == 409
    assert "identificación" in duplicate_id.json["error"]
    duplicate_email = client.post("/api/guests", json=payload | {"identification_number": uuid4().hex[:30]})
    assert duplicate_email.status_code == 409
    assert "correo electrónico" in duplicate_email.json["error"]

    selected_guest = client.get(guest.headers["Location"]).json
    booking = client.post(RESERVATIONS, json=reservation_data | {"guest_id": selected_guest["guest_id"]})
    assert booking.status_code == 201, booking.json
    assert booking.json["guest_id"] == selected_guest["guest_id"]


def test_availability_after_booking_edit_and_cancel(client, reservation_data):
    room_id = reservation_data["room_id"]
    assert room_id in available_rooms(client, "2026-12-20", "2026-12-23")
    created = client.post(RESERVATIONS, json=reservation_data)
    assert created.status_code == 201, created.json
    path = created.headers["Location"]
    reservation_id = created.json["reservation_id"]
    assert room_id not in available_rooms(client, "2026-12-22", "2026-12-25")
    assert room_id in available_rooms(client, "2026-12-23", "2026-12-25")
    assert room_id in available_rooms(client, "2026-12-22", "2026-12-25", exclude=reservation_id)

    assert client.patch(path, json={
        "check_in_date": "2026-12-24", "check_out_date": "2026-12-26",
    }).status_code == 200
    assert room_id in available_rooms(client, "2026-12-20", "2026-12-23")
    assert room_id not in available_rooms(client, "2026-12-24", "2026-12-26")

    assert client.patch(path, json={"status": "cancelled"}).status_code == 200
    assert client.get(path).json["status"] == "cancelled"
    assert room_id in available_rooms(client, "2026-12-24", "2026-12-26")
    assert client.delete(path).status_code == 204
    assert client.get(path).status_code == 404
    assert client.get(AVAILABILITY, query_string={
        "check_in_date": "2026-12-20", "check_out_date": "2026-12-23",
        "exclude_reservation_id": reservation_id,
    }).status_code == 404


def test_availability_excludes_unavailable_room_and_keeps_completed_stay(client, reservation_data):
    room_id = reservation_data["room_id"]
    room_path = f"/api/rooms/{room_id}"
    created = client.post(RESERVATIONS, json=reservation_data)
    assert created.status_code == 201, created.json
    path = created.headers["Location"]
    for status in ("maintenance", "out_of_service"):
        assert client.patch(room_path, json={"status": status}).status_code == 200
        assert room_id not in available_rooms(client, "2026-12-23", "2026-12-25")

    assert client.patch(path, json={"status": "checked_out"}).status_code == 200
    assert client.patch(path, json={"status": "cancelled"}).status_code == 409
    assert client.patch(path, json={"check_out_date": "2026-12-24"}).status_code == 409
    assert client.patch(room_path, json={"status": "available"}).status_code == 200
    assert room_id not in available_rooms(client, "2026-12-22", "2026-12-24")
    assert client.post(RESERVATIONS, json=reservation_data).status_code == 409
    assert room_id in available_rooms(client, "2026-12-23", "2026-12-25")


def test_concurrent_requests_cannot_book_the_same_room(test_app):
    # Una transacción externa con savepoints ocultaría el inventario a las
    # dos conexiones HTTP. Se confirman fixtures propios y se limpian por ID.
    with test_app.app_context():
        engine = db.engine
    suffix = uuid4().hex
    with engine.begin() as connection:
        verify_test_database(connection)
        guest_id = connection.execute(insert(Guest).values(
            full_name="Huésped concurrencia", identification_number=suffix[:30],
        )).inserted_primary_key[0]
        type_id = connection.execute(insert(RoomType).values(
            name=suffix, capacity=2, base_nightly_rate=70,
        )).inserted_primary_key[0]
        room_id = connection.execute(insert(Room).values(
            room_type_id=type_id, room_number=suffix[:10], floor=1,
        )).inserted_primary_key[0]

    gate = Barrier(2)

    def book():
        gate.wait(timeout=10)
        return test_app.test_client().post(RESERVATIONS, json={
            "guest_id": guest_id, "room_id": room_id,
            "check_in_date": "2026-12-20", "check_out_date": "2026-12-23",
            "nightly_rate": "70.00",
        })

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = pool.submit(book), pool.submit(book)
            responses = [future.result(timeout=30) for future in (first, second)]
        assert sorted(response.status_code for response in responses) == [201, 409]
        rejected = next(response for response in responses if response.status_code == 409)
        assert "reserva para esas fechas" in rejected.json["error"]
        with engine.connect() as connection:
            assert len(connection.scalars(select(Reservation.reservation_id).where(
                Reservation.room_id == room_id,
            )).all()) == 1
    finally:
        with engine.begin() as connection:
            verify_test_database(connection)
            connection.execute(delete(Reservation).where(Reservation.room_id == room_id))
            connection.execute(delete(Room).where(Room.room_id == room_id))
            connection.execute(delete(RoomType).where(RoomType.room_type_id == type_id))
            connection.execute(delete(Guest).where(Guest.guest_id == guest_id))


def test_room_overview_reflects_stays_and_physical_status(client, test_connection, inventory, reservation_data):
    _, type_id, room_id = inventory
    room_path = f"/api/rooms/{room_id}"

    def room_card(start=None, end=None):
        params = {} if start is None else {"check_in_date": start, "check_out_date": end}
        response = client.get("/api/rooms/overview", query_string=params)
        assert response.status_code == 200, response.json
        return next(room for room in response.json if room["room_id"] == room_id)

    initial = room_card()
    type_name = test_connection.scalar(select(RoomType.name).where(RoomType.room_type_id == type_id))
    assert initial["room_type_name"] == type_name
    assert initial["display_status"] == "operational"
    start, end = "2026-12-20", "2026-12-23"
    assert room_card(start, end)["display_status"] == "available"

    created = client.post(RESERVATIONS, json=reservation_data)
    assert created.status_code == 201, created.json
    path = created.headers["Location"]
    reserved = room_card(start, end)
    assert reserved["display_status"] == "reserved"
    assert reserved["status"] == "available"
    assert room_card()["display_status"] == "operational"
    assert room_card(end, "2026-12-25")["display_status"] == "available"

    changed = client.patch(path, json={"check_in_date": "2026-12-23", "check_out_date": "2026-12-25"})
    assert changed.status_code == 200, changed.json
    assert room_card(start, end)["display_status"] == "available"
    assert room_card(end, "2026-12-25")["display_status"] == "reserved"

    for status in ("maintenance", "out_of_service"):
        assert client.patch(room_path, json={"status": status}).status_code == 200
        assert room_card(end, "2026-12-25")["display_status"] == status
        assert room_card()["display_status"] == status
    assert client.patch(room_path, json={"status": "available"}).status_code == 200

    assert client.patch(path, json={"status": "cancelled"}).status_code == 200
    assert room_card(end, "2026-12-25")["display_status"] == "available"
