from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import select

from backend import db
from backend.models import Guest, Payment, Reservation, Room, Service, ServiceCharge


@pytest.mark.parametrize(("resource", "model"), [
    ("guests", Guest),
    ("rooms", Room),
    ("reservations", Reservation),
])
def test_crud(client, test_connection, inventory, reservation_data, resource, model):
    _, room_type_id, _ = inventory
    payloads = {
        "guests": ({"full_name": "Ana", "identification_number": uuid4().hex[:30]}, "full_name", "Ana Ruiz"),
        "rooms": ({"room_type_id": room_type_id, "room_number": uuid4().hex[:10], "floor": 1}, "floor", 2),
        "reservations": (reservation_data, "nightly_rate", "75.50"),
    }
    payload, field, new_value = payloads[resource]
    base = f"/api/{resource}"
    created = client.post(base, json=payload)
    assert created.status_code == 201, created.json
    path = created.headers["Location"]
    primary_key = model.__mapper__.primary_key[0]
    row_id = created.json[primary_key.key]
    row_query = select(model.__table__).where(primary_key == row_id)
    assert test_connection.execute(row_query).mappings().one()[primary_key.key] == row_id
    assert client.get(path).json == created.json
    assert created.json in client.get(base).json

    patched = client.patch(path, json={field: new_value})
    assert patched.status_code == 200
    assert client.get(path).json[field] == new_value
    stored_value = test_connection.execute(row_query).mappings().one()[field]
    if field == "nightly_rate":
        stored_value = str(stored_value)
    assert stored_value == new_value
    replaced = client.put(path, json=payload)
    assert replaced.status_code == 200
    assert client.get(path).json == created.json

    assert client.delete(path).status_code == 204
    assert test_connection.execute(row_query).first() is None
    assert client.get(path).status_code == 404
    assert client.delete(path).status_code == 404
    assert created.json not in client.get(base).json


def test_duplicate_guest(client):
    payload = {"full_name": "Ana", "identification_number": uuid4().hex[:30]}
    assert client.post("/api/guests", json=payload).status_code == 201
    duplicate = client.post("/api/guests", json=payload)
    assert duplicate.status_code == 409
    assert "error" in duplicate.json


@pytest.mark.parametrize("changes", [
    {"check_in_date": "2026-02-30"},
    {"check_in_date": "2026-12-23"},
    {"actual_check_out_date": "2026-12-23"},
    {"nightly_rate": "70.001"},
    {"status": "invalid"},
])
def test_invalid_reservation(client, reservation_data, changes):
    response = client.post("/api/reservations", json=reservation_data | changes)
    assert response.status_code == 400
    assert "error" in response.json


def test_overlap_on_create_and_update(client, reservation_data):
    base = "/api/reservations"
    first = client.post(base, json=reservation_data)
    assert first.status_code == 201
    assert client.post(base, json=reservation_data).status_code == 409
    adjacent = client.post(base, json=reservation_data | {
        "check_in_date": "2026-12-23", "check_out_date": "2026-12-25",
    })
    assert adjacent.status_code == 201
    assert client.patch(adjacent.headers["Location"], json={"check_in_date": "2026-12-22"}).status_code == 409
    assert client.patch(first.headers["Location"], json={"nightly_rate": "80.00"}).status_code == 200
    assert client.patch(first.headers["Location"], json={"status": "cancelled"}).status_code == 200
    assert client.post(base, json=reservation_data).status_code == 201


def test_unavailable_room(client, inventory, reservation_data):
    _, _, room_id = inventory
    assert client.patch(f"/api/rooms/{room_id}", json={"status": "maintenance"}).status_code == 200
    assert client.post("/api/reservations", json=reservation_data).status_code == 409


@pytest.mark.parametrize("dependency", ["payment", "service_charge"])
def test_delete_reservation_with_references(client, test_connection, reservation_data, dependency):
    created = client.post("/api/reservations", json=reservation_data)
    assert created.status_code == 201
    reservation_id = created.json["reservation_id"]
    if dependency == "payment":
        record = Payment(
            reservation_id=reservation_id, amount=70,
            payment_date=date(2026, 12, 20), payment_method="cash",
        )
    else:
        service = Service(name=uuid4().hex, standard_price=5)
        db.session.add(service)
        db.session.flush()
        record = ServiceCharge(
            reservation_id=reservation_id, service_id=service.service_id,
            service_date=date(2026, 12, 20), quantity=1, unit_price=5,
        )
    db.session.add(record)
    db.session.flush()
    related_table = record.__table__
    related_key = record.__mapper__.primary_key[0]
    related_id = getattr(record, related_key.key)
    db.session.commit()

    reservation_query = select(Reservation.__table__).where(
        Reservation.reservation_id == reservation_id,
    )
    related_query = select(related_table).where(related_key == related_id)
    original_reservation = test_connection.execute(reservation_query).mappings().one()
    original_related = test_connection.execute(related_query).mappings().one()

    path = created.headers["Location"]
    response = client.delete(path)
    assert response.status_code == 409, response.json
    assert response.json == {"error": "El registro tiene datos asociados y no se puede eliminar."}
    assert client.get(path).json == created.json
    assert test_connection.execute(reservation_query).mappings().one() == original_reservation
    assert test_connection.execute(related_query).mappings().one() == original_related
