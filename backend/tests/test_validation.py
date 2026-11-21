from datetime import date
from decimal import Decimal

import pytest
from werkzeug.exceptions import BadRequest

from backend.models import Guest, Reservation, Room
from backend.validation import validated_fields


@pytest.mark.parametrize(("model", "payload"), [
    (Guest, {"guest_id": 1}),
    (Guest, {"full_name": " "}),
    (Room, {"floor": True}),
    (Room, {"status": "booked"}),
    (Reservation, {"check_in_date": "2026-02-30"}),
    (Reservation, {"nightly_rate": "NaN"}),
    (Reservation, {"nightly_rate": "70.001"}),
])
def test_invalid_fields(model, payload):
    with pytest.raises(BadRequest):
        validated_fields(model, payload)


def test_reservation_fields_are_typed_and_receive_defaults():
    fields = validated_fields(Reservation, {
        "guest_id": 1,
        "room_id": 2,
        "check_in_date": "2026-12-20",
        "check_out_date": "2026-12-23",
        "nightly_rate": "70.50",
    }, replacing=True)

    assert fields == {
        "guest_id": 1,
        "room_id": 2,
        "check_in_date": date(2026, 12, 20),
        "check_out_date": date(2026, 12, 23),
        "nightly_rate": Decimal("70.50"),
        "status": "booked",
        "actual_check_in_date": None,
        "actual_check_out_date": None,
    }
