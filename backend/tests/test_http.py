from sqlalchemy import URL

from backend import create_app, db


def test_unknown_route_returns_json_without_connecting(monkeypatch):
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": URL.create(
            "mysql+pymysql", database="hotel_management_api_test",
        ),
    })
    def unexpected_connection(*args, **kwargs):
        raise AssertionError("Esta prueba HTTP debe ejecutarse sin conexión SQL.")

    with app.app_context():
        monkeypatch.setattr(db.engine, "connect", unexpected_connection)
    client = app.test_client()
    assert client.get("/api/unknown").status_code == 404
    assert "error" in client.get("/api/unknown").json
    assert client.post("/api/guests/1").status_code == 405
