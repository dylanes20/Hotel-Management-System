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
