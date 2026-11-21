from sqlalchemy import URL

from backend import create_app, db


def test_dashboard_serves_frontend_without_a_database_connection(monkeypatch):
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": URL.create(
            "mysql+pymysql", database="hotel_management_api_test",
        ),
    })

    def unexpected_connection(*args, **kwargs):
        raise AssertionError("Flask debe servir la interfaz sin abrir una conexión SQL.")

    with app.app_context():
        monkeypatch.setattr(db.engine, "connect", unexpected_connection)

    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    for section in ("guests", "rooms", "reservations"):
        assert f'data-section="{section}"' in page
    assert 'data-api="/api/reservations"' in page
    assert '<dialog id="reservation-dialog"' in page
    for filename, mimetype in (("hotel.css", "text/css"), ("hotel.js", "text/javascript")):
        path = f"/static/{filename}"
        assert path in page
        asset = client.get(path)
        assert asset.status_code == 200
        assert asset.mimetype == mimetype
        assert asset.data

    assert "Casa Albor" in page
    assert 'id="guest-form"' in page
    assert 'id="add-guest"' in page
    assert 'id="guest-search"' in page
    assert 'id="availability-message"' in page
    assert 'id="confirm-cancel"' in page
    assert 'id="confirm-delete"' in page
    assert 'id="room-dates"' in page
    for date_input in ("rooms-check-in", "rooms-check-out"):
        assert f'type="date" id="{date_input}"' in page
    for image in (
        "albor-courtyard.webp", "albor-suite.webp", "albor-room.webp",
        "albor-individual.webp", "albor-doble.webp", "albor-suite-junior.webp", "albor-familiar.webp",
    ):
        path = f"/static/images/{image}"
        assert path in page
        asset = client.get(path)
        assert asset.status_code == 200
        assert asset.mimetype == "image/webp"
        assert asset.data[8:12] == b"WEBP"
