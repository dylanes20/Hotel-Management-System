from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import insert, select

from backend.models import Reservation, Room
from database.seed_demo_rooms import DEMO_ROOMS, seed_catalog


def test_seed_rejects_main_database_before_any_catalog_operation():
    connection = Mock(dialect=SimpleNamespace(name="mysql"))
    connection.scalar.return_value = "hotel_management"

    with pytest.raises(ValueError, match="hotel_management_api_test"):
        seed_catalog(connection, apply=True)

    connection.execute.assert_not_called()


def test_seed_is_repeatable_and_catalog_uses_mysql_values(client, test_connection, inventory):
    _, type_id, _ = inventory
    room_901 = select(Room.__table__).where(Room.room_number == "901")
    existing = test_connection.execute(room_901).mappings().one_or_none()
    if existing is None:
        test_connection.execute(insert(Room).values(room_number="901", room_type_id=type_id, floor=9))
        existing = test_connection.execute(room_901).mappings().one()

    reservations_901 = select(Reservation.__table__).where(
        Reservation.room_id == existing["room_id"],
    ).order_by(Reservation.reservation_id)
    existing_stays = test_connection.execute(reservations_901).all()

    before, planned, dry_run = seed_catalog(test_connection)
    assert before == dry_run
    assert seed_catalog(test_connection)[0] == before

    _, inserted, after = seed_catalog(test_connection, apply=True)
    assert inserted == planned
    assert len(after) == len(before) + len(inserted)
    assert seed_catalog(test_connection, apply=True)[1] == []
    assert test_connection.execute(room_901).mappings().one() == existing
    assert test_connection.execute(reservations_901).all() == existing_stays

    response = client.get("/api/rooms/overview")
    assert response.status_code == 200, response.json
    cards = {room["room_number"]: room for room in response.json}
    available = client.get("/api/rooms/availability", query_string={
        "check_in_date": "2027-01-10", "check_out_date": "2027-01-11",
    })
    assert available.status_code == 200, available.json
    available_numbers = {room["room_number"] for room in available.json}
    for number, floor, name, capacity, rate in DEMO_ROOMS:
        room = cards[number]
        assert (room["floor"], room["room_type_name"], room["capacity"], room["base_nightly_rate"]) == (
            floor, name, capacity, str(rate),
        )
        if number in inserted:
            assert number in available_numbers
